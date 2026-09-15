"""Tests for the `create_memo` assistant tool (feature 026, step 008).

Bound to the frozen skeleton (`status.md` -> `## Skeleton` -> "Step 008 — frozen
interface (2026-09-15)"), in `app.services.memo_tools`::

    class CreateMemoArgs(BaseModel) { body: str }        # required, no default
    async def create_memo(context: "ToolContext", body: str) -> str
    def bind_create_memo(context: "ToolContext") -> Callable[..., object]

in `app.services.tools` (UNCHANGED by this step)::

    @dataclass class ToolContext { book_id; access; subject; emit_frame;
        selection_text; active_notes_proposal; codex_creates_this_turn }
    @dataclass(frozen=True) class ToolDef { name; description; args_schema;
        group; callable=None; binder=None }
    TOOL_REGISTRY: list[ToolDef]

in `app.services.assistant_runtime` (UNCHANGED signatures)::

    BASE_TOOL_NAMES: tuple[str, ...]
    @dataclass(frozen=True) class ResolvedSubject { kind; entry; chapter; mode_key }
    NO_SUBJECT: ResolvedSubject
    def determine_mode(subject) -> str | None
    async def allowed_tool_names(mode_key: str | None) -> tuple[str, ...]

and, reached THROUGH the tool rather than asserted for its own sake, step 002's
`app.services.memos.create_memo(access, CreateMemoRequest)` plus its `MemoError`
/ `MemoErrorReason`.

Expected values come from the SPEC ONLY -- `008.create-memo-tool.md` -> Interface
intent + Definition of done (DoD-1..DoD-12), `008.context.md` ("The one thing NOT
to copy", "Why both halves", "Deliberate absences to preserve"), `context.md` ->
decisions 2, 4, 9 and 10, `docs/architecture/authorization.md` -> the archived-book
carve-out, and `docs/architecture/assistant-runtime.md` -> "The SSE frame
vocabulary" -- never from implementation internals.

Two wording rules this module keeps deliberately:

- The skeleton records `_NO_ACCESS_MESSAGE` / `_REFUSED_MESSAGE` /
  `_CREATE_FAILED_MESSAGE` / `_CREATED_MESSAGE` as the coder's to word and states
  that **no test may bind to them**. Nothing here asserts a refusal's or a
  confirmation's TEXT. A refusal is asserted by its *shape and consequence*: a
  non-blank string comes back, nothing was raised, and **no memo row exists**.
- DoD-11 (the seeded US-130 guidance) is deliberately NOT here: it belongs to the
  seeding spec, `backend/tests/db/test_mode_tools_seed.py`, alongside the rest of
  the seeding contract. DoD-10's registry-entry half lives in
  `backend/tests/services/test_tools.py`, beside the registry's other assertions.

Test approach (`008.context.md` -> "Test seeding"): the `ToolContext` is built
directly with a constructed `BookAccess` and the tool is invoked as a plain
function. **No network, no live model, no LLM server is contacted.** Rows are
written through the `db/` layer against the `db` fixture's throwaway temp SQLite;
`asyncio_mode = "auto"`, so async tests need no decorator.
"""

import dataclasses
import inspect

import pytest

from app.db import assistant_modes, books, codex_entries, mode_tools, users
from app.db import memos as memos_db
from app.db.engine import DbConfig
from app.models.assistant_mode import AssistantMode
from app.models.book import Book, BookState, CollaborationMode, Visibility
from app.models.codex_entry import CodexEntry, CodexKind
from app.models.memo import Memo
from app.models.mode_tool import ModeTool
from app.models.schemas import chats as chat_schemas
from app.models.schemas.memos import CreateMemoRequest
from app.models.user import User, UserRole
from app.services import assistant_runtime
from app.services import memo_tools
from app.services import memos as memo_service
from app.services import tools as tools_module
from app.services.assistant_runtime import NO_SUBJECT, ResolvedSubject
from app.services.authz import AccessRole, BookAccess
from app.services.memo_tools import CreateMemoArgs, bind_create_memo
from app.services.memos import MemoError, MemoErrorReason
from app.services.tools import ToolContext

TOOL_NAME = "create_memo"
TOOL_GROUP = "book"  # context.md -> decision 9: the EXISTING group, not a new one

BODY = "Halden never says the word 'winter' out loud."


# ---------------------------------------------------------------------------
# The recording emitter -- the FrameEmitter shape: an awaited (event, payload).
#
# `008.context.md` -> "Deliberate absences to preserve": this tool emits NO frame
# of its own; `tool_call` / `tool_result` come from the generic wrapper around
# every bound tool, which is not in play when the callable is invoked directly.
# So a recorder here must stay EMPTY on every path (DoD-12).
# ---------------------------------------------------------------------------


class _Recorder:
    def __init__(self) -> None:
        self.frames: list[tuple[str, object]] = []

    async def __call__(self, event, data) -> None:
        self.frames.append((event, data))


# ---------------------------------------------------------------------------
# Seeding helpers -- local, copied in idiom from tests/services/test_memos.py and
# tests/services/test_chapter_tools.py (context.md: "there is no shared factory
# module -- every test module defines its own").
# ---------------------------------------------------------------------------


async def _seed_user(username: str = "author") -> User:
    return await users.create(User(username=username, role=UserRole.author))


async def _seed_book(
    owner_id: int,
    *,
    title: str = "A Book",
    state: BookState = BookState.active,
    collaboration_mode: CollaborationMode = CollaborationMode.free,
) -> Book:
    return await books.create(
        Book(
            title=title,
            description="desc",
            owner_id=owner_id,
            collaboration_mode=collaboration_mode,
            visibility=Visibility.private,
            state=state,
            system_prompt="",
            active_notes="",
        )
    )


async def _seed_memo(
    *,
    book_id: int,
    user_id: int,
    body: str = "seeded memo",
    ordinal: int = 1,
    active: bool = True,
    archived: bool = False,
) -> Memo:
    return await memos_db.create(
        Memo(
            book_id=book_id,
            user_id=user_id,
            body=body,
            ordinal=ordinal,
            active=active,
            archived=archived,
        )
    )


async def _seed_entry(book_id: int, author_id: int) -> CodexEntry:
    return await codex_entries.create(
        CodexEntry(
            book_id=book_id,
            kind=CodexKind.character,
            name="Halden",
            body="a codex body",
            archived=False,
            author_id=author_id,
        )
    )


async def _seed_mode(key: str, system_prompt: str | None = None) -> AssistantMode:
    return await assistant_modes.create(
        AssistantMode(key=key, system_prompt=system_prompt)
    )


async def _seed_mode_tool(mode_key: str, tool_name: str) -> ModeTool:
    return await mode_tools.create(ModeTool(mode_key=mode_key, tool_name=tool_name))


def _access(
    book_id: int,
    user_id: int,
    *,
    role: AccessRole = AccessRole.owner,
    book_state: BookState = BookState.active,
    collaboration_mode: CollaborationMode = CollaborationMode.free,
) -> BookAccess:
    """The access context the `book_access` dependency would have resolved."""
    return BookAccess(
        book_id=book_id,
        user_id=user_id,
        role=role,
        book_state=book_state,
        visibility=Visibility.private,
        collaboration_mode=collaboration_mode,
    )


def _ctx(
    book_id: int,
    user_id: int,
    *,
    subject=NO_SUBJECT,
    emitter=None,
    role: AccessRole = AccessRole.owner,
    book_state: BookState = BookState.active,
    collaboration_mode: CollaborationMode = CollaborationMode.free,
    with_access: bool = True,
    selection_text: str | None = None,
) -> ToolContext:
    """A per-turn ToolContext built directly -- no route, no HTTP, no turn."""
    return ToolContext(
        book_id=book_id,
        access=(
            _access(
                book_id,
                user_id,
                role=role,
                book_state=book_state,
                collaboration_mode=collaboration_mode,
            )
            if with_access
            else None
        ),
        subject=subject,
        emit_frame=emitter,
        selection_text=selection_text,
    )


async def _stored(book_id: int, user_id: int) -> list[Memo]:
    """That author's memo rows in that book, archived included, ordinal order."""
    rows = await memos_db.list_for_author(book_id, user_id, True)
    return sorted(rows, key=lambda row: row.ordinal)


def _assert_answer(result: object) -> str:
    """Every path answers with a STRING -- never an exception, never None."""
    assert isinstance(result, str), f"the tool answered {type(result).__name__}"
    assert result.strip() != ""
    return result


# ===========================================================================
# DoD-1 (US-129.AC-1) -- the tool creates a memo for the turn's author in the
#                        route's book, and it appears in that author's list
# ===========================================================================


async def test_tool_creates_a_memo_in_the_authors_list__DoD1(db: DbConfig):
    # DoD-1: one call, one row -- for `context.access.user_id` in
    # `context.book_id` -- and the author's own list shows it with the body the
    # model supplied.
    author = await _seed_user("tool-author")
    book = await _seed_book(author.id, title="Tool Book")
    recorder = _Recorder()

    answer = await memo_tools.create_memo(
        _ctx(book.id, author.id, emitter=recorder), BODY
    )

    _assert_answer(answer)

    rows = await _stored(book.id, author.id)
    assert len(rows) == 1
    assert rows[0].body == BODY
    assert rows[0].book_id == book.id
    assert rows[0].user_id == author.id

    # It appears in that author's list, through the ordinary read path.
    listed = await memo_service.list_memos(_access(book.id, author.id))
    assert [item.body for item in listed.items] == [BODY]


async def test_tool_creates_for_the_turns_author_only__DoD1(db: DbConfig):
    # DoD-1: the row belongs to the turn's author -- a co-author of the same book
    # who did not run the turn has nothing in their own list afterwards.
    author = await _seed_user("turn-author")
    other = await _seed_user("other-member")
    book = await _seed_book(author.id, title="Shared Book")

    await memo_tools.create_memo(_ctx(book.id, author.id), BODY)

    assert len(await _stored(book.id, author.id)) == 1
    assert await _stored(book.id, other.id) == []


# ===========================================================================
# DoD-2 (US-129.AC-2) -- the created memo is ACTIVE
# ===========================================================================


async def test_tool_created_memo_is_active__DoD2(db: DbConfig):
    # DoD-2: a tool-created memo reaches the assistant on the next turn without
    # the author switching anything on -- `active` true (and not archived).
    author = await _seed_user("active-author")
    book = await _seed_book(author.id, title="Active Book")

    await memo_tools.create_memo(_ctx(book.id, author.id), BODY)

    rows = await _stored(book.id, author.id)
    assert len(rows) == 1
    assert rows[0].active is True
    assert rows[0].archived is False


# ===========================================================================
# DoD-3 (US-129.AC-3) -- at the END of the list, by the same append rule a
#                        manual create uses (reached THROUGH the memo service,
#                        never recomputed here)
# ===========================================================================


async def test_tool_memo_lands_at_the_end_of_the_list__DoD3(db: DbConfig):
    # DoD-3: with memos already standing at ordinals 1 and 2, the tool's memo is
    # ordinal 3 and is LAST in the author's list.
    author = await _seed_user("append-author")
    book = await _seed_book(author.id, title="Append Book")
    await _seed_memo(book_id=book.id, user_id=author.id, body="one", ordinal=1)
    await _seed_memo(book_id=book.id, user_id=author.id, body="two", ordinal=2)

    await memo_tools.create_memo(_ctx(book.id, author.id), BODY)

    listed = await memo_service.list_memos(_access(book.id, author.id))
    assert [item.body for item in listed.items] == ["one", "two", BODY]
    assert listed.items[-1].ordinal == 3


async def test_tool_append_matches_a_manual_create_exactly__DoD3(db: DbConfig):
    # DoD-3, the point of the clause: the tool reaches the append rule THROUGH
    # the memo service rather than recomputing an ordinal. Two identically-seeded
    # books -- one with the archived gap that makes the rule non-obvious
    # (context.md -> decision 2: max is taken over the NON-archived list) -- get
    # the same answer from the tool and from a manual create.
    author = await _seed_user("parity-author")
    by_tool = await _seed_book(author.id, title="By Tool")
    by_hand = await _seed_book(author.id, title="By Hand")

    for book in (by_tool, by_hand):
        await _seed_memo(book_id=book.id, user_id=author.id, body="a", ordinal=1)
        await _seed_memo(book_id=book.id, user_id=author.id, body="b", ordinal=2)
        await _seed_memo(
            book_id=book.id, user_id=author.id, body="c", ordinal=3, archived=True
        )

    await memo_tools.create_memo(_ctx(by_tool.id, author.id), BODY)
    manual = await memo_service.create_memo(
        _access(by_hand.id, author.id), CreateMemoRequest(body=BODY)
    )

    tool_rows = await _stored(by_tool.id, author.id)
    tool_made = [row for row in tool_rows if row.body == BODY]
    assert len(tool_made) == 1
    assert tool_made[0].ordinal == manual.ordinal


# ===========================================================================
# DoD-4 (US-129.AC-4) -- the tool reads NO subject, and always creates into the
#                        book the ROUTE named
# ===========================================================================

# The three subject shapes the clause names. `memos` is mode-less, exactly like
# the chapters / variants / chats lists (context.md -> decision 11), and the
# "unrelated" case is a codex entry -- filled in per-test so it can be seeded in
# a DIFFERENT book than the route's.
SUBJECT_IDS = ["no-subject", "memos-list", "unrelated-subject"]


@pytest.mark.parametrize("subject_id", SUBJECT_IDS)
async def test_tool_creates_regardless_of_subject__DoD4(db: DbConfig, subject_id: str):
    # DoD-4: with no subject resolved, with the memos list as the subject, and
    # with an unrelated subject, the memo is created just the same.
    author = await _seed_user(f"subject-author-{subject_id}")
    book = await _seed_book(author.id, title="Route Book")
    elsewhere = await _seed_book(author.id, title="Some Other Book")

    if subject_id == "no-subject":
        subject = NO_SUBJECT
    elif subject_id == "memos-list":
        subject = ResolvedSubject(kind="memos", mode_key=None)
    else:
        entry = await _seed_entry(elsewhere.id, author.id)
        subject = ResolvedSubject(
            kind="codex-entry", entry=entry, mode_key="edit-character"
        )

    answer = await memo_tools.create_memo(
        _ctx(book.id, author.id, subject=subject), BODY
    )

    _assert_answer(answer)
    rows = await _stored(book.id, author.id)
    assert len(rows) == 1
    assert rows[0].body == BODY


async def test_tool_creates_into_the_routes_book_not_the_subjects__DoD4(db: DbConfig):
    # DoD-4, the load-bearing half: `book_id` comes from the tool context -- which
    # comes from the route -- and NEVER from the resolved subject. A subject
    # belonging to a different book does not move the memo.
    author = await _seed_user("cross-book-author")
    route_book = await _seed_book(author.id, title="The Route's Book")
    subject_book = await _seed_book(author.id, title="The Subject's Book")
    entry = await _seed_entry(subject_book.id, author.id)

    await memo_tools.create_memo(
        _ctx(
            route_book.id,
            author.id,
            subject=ResolvedSubject(
                kind="codex-entry", entry=entry, mode_key="edit-character"
            ),
        ),
        BODY,
    )

    in_route_book = await _stored(route_book.id, author.id)
    assert len(in_route_book) == 1
    assert in_route_book[0].book_id == route_book.id

    # Nothing landed in the subject's book.
    assert await _stored(subject_book.id, author.id) == []


# ===========================================================================
# DoD-5 (US-129.AC-5) -- a mode whose `mode_tool` rows EXCLUDE `create_memo`
#                        does not resolve it
#
# A PRESERVED-BEHAVIOUR clause: gating already means what it says, so this is an
# honest regression guard rather than a clause that must go red. It is what keeps
# the visible refusal reachable at all -- BASE does not override a mode's
# allowlist (`008.context.md` -> "Why both halves").
# ===========================================================================


async def test_mode_without_the_row_does_not_resolve_the_tool__DoD5(db: DbConfig):
    # DoD-5: an administrator edits a mode down and removes `create_memo`; that
    # mode's resolved allowlist then does not contain it, and `resolve_tools`
    # hands the turn no such tool -- so the request is refused visibly rather
    # than silently succeeding.
    await _seed_mode("edit-character")
    await _seed_mode_tool("edit-character", "web_search")
    await _seed_mode_tool("edit-character", "codex_search")

    allowed = await assistant_runtime.allowed_tool_names("edit-character")

    assert TOOL_NAME not in allowed
    assert set(allowed) == {"web_search", "codex_search"}

    resolved = tools_module.resolve_tools(allowed)
    assert TOOL_NAME not in [tool.name for tool in resolved]


async def test_mode_with_the_row_does_resolve_the_tool__DoD5(db: DbConfig):
    # DoD-5's other half, so the guard above cannot pass vacuously: the same mode
    # WITH the row resolves the tool.
    await _seed_mode("edit-character")
    await _seed_mode_tool("edit-character", "web_search")
    await _seed_mode_tool("edit-character", TOOL_NAME)

    allowed = await assistant_runtime.allowed_tool_names("edit-character")

    assert TOOL_NAME in allowed
    assert TOOL_NAME in [tool.name for tool in tools_module.resolve_tools(allowed)]


# ===========================================================================
# DoD-6 -- BASE_TOOL_NAMES widens to exactly two, so every MODE-LESS surface
#          resolves an allowlist containing `create_memo`
#          (architecture -- assistant-runtime.md -> "BASE_TOOL_NAMES widens to
#          two entries")
# ===========================================================================


def test_base_tool_names_holds_exactly_the_two__DoD6():
    # DoD-6: exactly `web_search` and `create_memo` -- no more, no fewer, no
    # duplicate. The order is deliberately not asserted; the membership is the
    # contract.
    names = assistant_runtime.BASE_TOOL_NAMES

    assert set(names) == {"web_search", TOOL_NAME}
    assert len(names) == 2


async def test_mode_less_surface_resolves_create_memo__DoD6(db: DbConfig):
    # DoD-6: a null mode -- gating case 2 -- resolves to the base allowlist, and
    # `create_memo` is in it. Without this half, asking for a memo would fail on
    # the memos list itself (`008.context.md` -> "Why both halves").
    allowed = await assistant_runtime.allowed_tool_names(None)

    assert TOOL_NAME in allowed
    assert set(allowed) == set(assistant_runtime.BASE_TOOL_NAMES)
    assert TOOL_NAME in [tool.name for tool in tools_module.resolve_tools(allowed)]


# The mode-less surfaces the clause names: the memos list, Book state, the
# chapters / variants / chats lists, a `planned` or `closed` chapter, and no
# subject at all. None of them is mode-bearing (context.md -> decision 11: no
# `ResolvedSubject` member and no `determine_mode` branch is added), so each
# falls to the base allowlist.
MODE_LESS_SUBJECTS = [
    ("no-subject", NO_SUBJECT),
    ("memos", ResolvedSubject(kind="memos", mode_key=None)),
    ("book-state", ResolvedSubject(kind="book-state", mode_key=None)),
    ("chapters", ResolvedSubject(kind="chapters", mode_key=None)),
    ("variants", ResolvedSubject(kind="variants", mode_key=None)),
    ("chats", ResolvedSubject(kind="chats", mode_key=None)),
]


@pytest.mark.parametrize(
    "subject", [pair[1] for pair in MODE_LESS_SUBJECTS], ids=[p[0] for p in MODE_LESS_SUBJECTS]
)
async def test_every_mode_less_subject_gets_create_memo__DoD6(
    db: DbConfig, subject: ResolvedSubject
):
    # DoD-6: each mode-less surface determines NO mode and therefore resolves the
    # base allowlist -- which now carries `create_memo`.
    mode_key = assistant_runtime.determine_mode(subject)
    assert mode_key is None

    allowed = await assistant_runtime.allowed_tool_names(mode_key)
    assert TOOL_NAME in allowed


# ===========================================================================
# DoD-8 (UC-102 / US-129.AC-5) -- the tool NEVER raises: every failure comes back
#                                 as a refusal string the model can read
#
# The refusal MESSAGES are the coder's to word (skeleton: "no test may bind to
# it"), so a refusal is asserted by shape and consequence: a non-blank string
# came back, nothing was raised, and NO memo row exists.
# ===========================================================================


async def test_absent_access_is_a_refusal_string_not_an_exception__DoD8(db: DbConfig):
    # DoD-8: the one link in this tool's refusal chain -- `context.access` is
    # None -- answers with a string and writes nothing.
    author = await _seed_user("no-access-author")
    book = await _seed_book(author.id, title="No Access Book")
    recorder = _Recorder()

    answer = await memo_tools.create_memo(
        _ctx(book.id, author.id, with_access=False, emitter=recorder), BODY
    )

    _assert_answer(answer)
    assert await _stored(book.id, author.id) == []
    assert recorder.frames == []


@pytest.mark.parametrize("role", [AccessRole.reader, AccessRole.none])
async def test_non_member_caller_is_a_refusal_string__DoD8(db: DbConfig, role):
    # DoD-8: a caller who is not a member is the memo service's `not-a-member`
    # refusal; the tool surfaces it as a string rather than letting it abort the
    # turn.
    owner = await _seed_user(f"owner-{role.value}")
    stranger = await _seed_user(f"stranger-{role.value}")
    book = await _seed_book(owner.id, title="Members Only")

    answer = await memo_tools.create_memo(
        _ctx(book.id, stranger.id, role=role), BODY
    )

    _assert_answer(answer)
    assert await _stored(book.id, stranger.id) == []
    assert await _stored(book.id, owner.id) == []


async def test_service_level_refusal_is_a_refusal_string__DoD8(db: DbConfig, monkeypatch):
    # DoD-8: a typed refusal raised by the memo service -- whatever its reason --
    # reaches the model as a readable string, not as an exception. The service is
    # substituted so the refusal is unambiguously the SERVICE's, not one the tool
    # derived for itself.
    author = await _seed_user("refused-author")
    book = await _seed_book(author.id, title="Refused Book")

    async def _refuse(access, req):
        raise MemoError(MemoErrorReason.not_found, "the service said no")

    monkeypatch.setattr(memo_service, "create_memo", _refuse)

    answer = await memo_tools.create_memo(_ctx(book.id, author.id), BODY)

    _assert_answer(answer)
    assert await _stored(book.id, author.id) == []


async def test_unexpected_failure_is_still_a_string__DoD8(db: DbConfig, monkeypatch):
    # DoD-8's headline -- "the tool NEVER raises": a raising tool aborts the whole
    # turn, so even an error nobody anticipated comes back as a string.
    author = await _seed_user("boom-author")
    book = await _seed_book(author.id, title="Boom Book")

    async def _boom(access, req):
        raise RuntimeError("the database fell over")

    monkeypatch.setattr(memo_service, "create_memo", _boom)

    answer = await memo_tools.create_memo(_ctx(book.id, author.id), BODY)

    _assert_answer(answer)
    assert await _stored(book.id, author.id) == []


async def test_success_and_refusal_do_not_read_alike__DoD8(db: DbConfig):
    # DoD-8: a refusal must be distinguishable from a confirmation, or the model
    # cannot "read and respond to" it. The WORDING of neither is asserted -- only
    # that they are not the same string.
    author = await _seed_user("distinct-author")
    book = await _seed_book(author.id, title="Distinct Book")

    refusal = await memo_tools.create_memo(
        _ctx(book.id, author.id, with_access=False), BODY
    )
    confirmation = await memo_tools.create_memo(_ctx(book.id, author.id), BODY)

    _assert_answer(refusal)
    _assert_answer(confirmation)
    assert confirmation != refusal


# ===========================================================================
# DoD-9 -- the tool SUCCEEDS on an archived book: there is no archived-book link
#          in its refusal chain (architecture -- authorization.md -> "The one
#          named exception: memos stay writable on an archived book";
#          context.md -> decision 4)
#
# This is the clause that catches a refusal chain copied from `chapter_tools.py`,
# whose chain runs chapter-resolved -> chapter open -> archived book -> proposal
# mode. `create_memo` has NO archived-book link and NO proposal-mode link.
# ===========================================================================


async def test_archived_book_still_creates_the_memo__DoD9(db: DbConfig):
    # DoD-9: a memo is the author's private note ABOUT a book they set aside, so
    # the assistant is refused by the same rule as the author -- which here means
    # not refused at all.
    author = await _seed_user("archived-book-author")
    book = await _seed_book(
        author.id, title="Set Aside", state=BookState.archived
    )

    answer = await memo_tools.create_memo(
        _ctx(book.id, author.id, book_state=BookState.archived), BODY
    )

    _assert_answer(answer)
    rows = await _stored(book.id, author.id)
    assert len(rows) == 1
    assert rows[0].body == BODY
    assert rows[0].active is True


async def test_proposal_mode_still_creates_the_memo__DoD9(db: DbConfig):
    # DoD-9's companion absence: `chapter_tools.py`'s chain also refuses in
    # proposal collaboration mode. A memo has no second reader and no review, so
    # collaboration mode does not apply to it (`008.context.md` -> "The one thing
    # NOT to copy").
    author = await _seed_user("proposal-author")
    book = await _seed_book(
        author.id, title="Proposal Book", collaboration_mode=CollaborationMode.proposal
    )

    answer = await memo_tools.create_memo(
        _ctx(
            book.id,
            author.id,
            collaboration_mode=CollaborationMode.proposal,
        ),
        BODY,
    )

    _assert_answer(answer)
    assert len(await _stored(book.id, author.id)) == 1


async def test_archived_book_and_proposal_mode_together_still_create__DoD9(
    db: DbConfig,
):
    # DoD-9: both of the neighbouring chain's non-chapter links at once, so a
    # partially-copied chain cannot slip through either.
    author = await _seed_user("both-links-author")
    book = await _seed_book(
        author.id,
        title="Both Links",
        state=BookState.archived,
        collaboration_mode=CollaborationMode.proposal,
    )

    answer = await memo_tools.create_memo(
        _ctx(
            book.id,
            author.id,
            book_state=BookState.archived,
            collaboration_mode=CollaborationMode.proposal,
        ),
        BODY,
    )

    _assert_answer(answer)
    assert len(await _stored(book.id, author.id)) == 1


# ===========================================================================
# DoD-10 -- `ToolContext` still has the fields it had before this step
#           (architecture -- quick-reference.md -> TOOL_REGISTRY)
#
# The registry entry's own half of DoD-10 (name / group / binder / no plain
# callable, and every entry declaring a valid group) lives in
# tests/services/test_tools.py, beside the registry's other assertions.
#
# The field list is `008.context.md` -> "Where each thing lives today", which
# records SEVEN fields as of this step. `assistant-config.md` and
# `quick-reference.md` still say "six" -- a stale count, predating the field a
# later fast feature added and never recorded. The clause is "no field was
# added", so it is expressed by NAMING the expected set rather than by a number
# copied out of a doc.
# ===========================================================================

TOOL_CONTEXT_FIELDS_BEFORE_THIS_STEP = {
    "book_id",
    "access",
    "subject",
    "emit_frame",
    "selection_text",
    "active_notes_proposal",
    "codex_creates_this_turn",
}


def test_tool_context_gained_no_field__DoD10():
    # DoD-10: `book_id` and `access` are already on the context, so this tool
    # needs nothing added -- and nothing was.
    fields = dataclasses.fields(ToolContext)
    names = {field.name for field in fields}

    assert names == TOOL_CONTEXT_FIELDS_BEFORE_THIS_STEP
    assert len(fields) == len(TOOL_CONTEXT_FIELDS_BEFORE_THIS_STEP)


def test_args_schema_is_a_single_required_body__DoD10():
    # DoD-10: the schema `quick-reference.md` names -- `CreateMemoArgs(body: str)`.
    # One field, required, and no subject / id / book field: the tool takes its
    # book and its author from the context, never from the model.
    fields = CreateMemoArgs.model_fields

    assert set(fields) == {"body"}
    assert fields["body"].is_required()


def test_binder_leaves_body_as_the_only_free_parameter__DoD10():
    # DoD-10: the binder closes over the context, so the bound callable's free
    # parameters are exactly the args schema's fields -- the invariant the `llm`
    # client checks with `inspect.signature`.
    bound = bind_create_memo(_ctx(1, 2))

    params = set(inspect.signature(bound).parameters)
    assert params == set(CreateMemoArgs.model_fields)


# ===========================================================================
# DoD-12 -- the SSE frame vocabulary is unchanged: still seven frames, none
#           widened, and this tool emits nothing itself
#           (architecture -- assistant-runtime.md -> "The SSE frame vocabulary")
#
# A PRESERVED-BEHAVIOUR clause: true before this step, asserted here as an honest
# regression guard. `tool_call` / `tool_result` visibility comes free from the
# generic wrapper around every bound tool, which is exactly why this tool needs
# no frame of its own.
# ===========================================================================

# assistant-runtime.md -> "The SSE frame vocabulary": seven named frames as
# shipped -- thinking / delta / done / error (011), canvas (013), and
# tool_call / tool_result (024).
SEVEN_FRAME_PAYLOADS = {
    "ThinkingFrame",
    "DeltaFrame",
    "DoneFrame",
    "ErrorFrame",
    "CanvasFrame",
    "ToolCallFrame",
    "ToolResultFrame",
}


def test_frame_vocabulary_is_still_seven__DoD12():
    # DoD-12: no eighth frame payload joined the schema module for this feature.
    declared = {
        name
        for name in dir(chat_schemas)
        if name.endswith("Frame")
        and getattr(getattr(chat_schemas, name), "__module__", None)
        == chat_schemas.__name__
    }

    assert declared == SEVEN_FRAME_PAYLOADS


def test_no_tool_frame_was_widened__DoD12():
    # DoD-12: "none widened". The two tool frames carry exactly what
    # assistant-runtime.md declares -- `ToolCallFrame(tool_name, arguments)` and
    # `ToolResultFrame(tool_name, result, ok)` -- so this tool contributed no
    # field to either.
    assert set(chat_schemas.ToolCallFrame.model_fields) == {"tool_name", "arguments"}
    assert set(chat_schemas.ToolResultFrame.model_fields) == {
        "tool_name",
        "result",
        "ok",
    }
    # And the canvas frame, the only other tool-emitted frame, is untouched too.
    assert set(chat_schemas.CanvasFrame.model_fields) == {
        "subject_kind",
        "subject_id",
        "field",
        "op",
        "text",
    }


async def test_the_tool_emits_no_frame_of_its_own__DoD12(db: DbConfig):
    # DoD-12: on success AND on refusal, the tool puts nothing on the turn's
    # queue -- unlike the canvas tools, which emit for themselves.
    author = await _seed_user("silent-author")
    book = await _seed_book(author.id, title="Silent Book")

    success_recorder = _Recorder()
    await memo_tools.create_memo(
        _ctx(book.id, author.id, emitter=success_recorder), BODY
    )
    assert success_recorder.frames == []

    refusal_recorder = _Recorder()
    await memo_tools.create_memo(
        _ctx(book.id, author.id, with_access=False, emitter=refusal_recorder), BODY
    )
    assert refusal_recorder.frames == []
