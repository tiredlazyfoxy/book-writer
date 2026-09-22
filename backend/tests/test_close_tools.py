"""The close-chapter tools' refusal chain (feature 016.chapter-close-continuity)
— DoD-7.

Bound to the frozen signatures in `status.md` -> `## Skeleton`, in
`app.services.close_tools`::

    async def draft_chapter_summary(context: ToolContext, summary: str) -> str
    async def draft_chapter_notes(context, added: str, modified: str,
                                  deleted: str) -> str
    async def propose_active_notes(context, active_notes: str) -> str
    async def raise_check_flag(context, comment: str) -> str
    async def read_continuity_context(context) -> str

and in `app.services.tools`::

    @dataclass class ToolContext { book_id; access; subject; emit_frame;
                                   selection_text; active_notes_proposal }

with `assistant_runtime.ResolvedSubject` and the frozen `authz.BookAccess` /
`AccessRole` consumed unchanged.

Every expected value comes from the SPEC — `plan.md` -> Interface (the close-tools
module's refusal chain, verbatim: "(1) a non-chapter subject, (2) a chapter not in
`closing`, (3) an archived book, (4) a caller who does not hold
`Capability.set_chapter_state`"), DoD-7, and Decisions taken D7 — never from
implementation internals:

  - every refusal is a RETURNED STRING; nothing in the module raises, exactly as
    `chapter_tools.py` established (a raising tool aborts the turn);
  - a refusal leaves the database and the tool context untouched — no summary
    written, no changeset row, no flag row, and no active-notes proposal recorded;
  - the fourth rule is the one this feature adds beyond that precedent: a
    co-author's call on the owner's close run is refused even though their own
    chat also resolves to `close-chapter` mode;
  - the chain is walked IN ORDER, so a context violating several rules at once
    still comes back as a plain refusal string rather than falling over on a rule
    whose subject does not exist;
  - the success contrast, which keeps every refusal above from being vacuous: on a
    `closing` chapter of an active book, called by the owner, each tool does its
    own job — the summary and its `draft` status are written, the changeset is
    upserted `draft`, the proposal is held in the CONTEXT and never persisted (D7),
    and a `check` flag is created open and attributed to the caller.

`read_continuity_context` is read-only and this file asserts only that it always
answers with a non-empty string and never raises; which rules gate a read is not
something DoD-7 fixes.

Async tests use `asyncio_mode = "auto"`; the `db` fixture (conftest) supplies an
initialized throwaway temp-SQLite engine. No LLM server is contacted and no turn is
run: the `ToolContext` is built directly and the tools are invoked as functions.
Chapters are written straight through `db/chapters.py` in the state each case needs.
"""

import pytest

from app.db import books, chapter_note_changesets, chapters, codex_entries, flags, users
from app.db.engine import DbConfig
from app.models.book import Book, BookState, CollaborationMode, Visibility
from app.models.chapter import Chapter, ChapterState, SummaryStatus
from app.models.chapter_notes import NoteStatus
from app.models.codex_entry import CodexEntry, CodexKind
from app.models.flag import FlagOrigin, FlagStatus
from app.models.user import User, UserRole
from app.services import close_tools
from app.services.assistant_runtime import ResolvedSubject
from app.services.authz import AccessRole, BookAccess
from app.services.tools import ToolContext

SUMMARY = "The gate holds until the fourth month, and then it does not."
ADDED = "Halden commands the north gate."
MODIFIED = "The winter is now in its fourth month."
DELETED = "The gate is intact."
PROPOSAL = "Halden commanded the north gate until it fell."
FINDING = "Chapter two says the gate never fell."

# The four state-changing close tools. `read_continuity_context` is read-only and
# is exercised separately.
WRITE_TOOL_NAMES = (
    "draft_chapter_summary",
    "draft_chapter_notes",
    "propose_active_notes",
    "raise_check_flag",
)

# The three chapter states that are NOT `closing` — rule 2's whole domain.
NON_CLOSING_STATES = [ChapterState.planned, ChapterState.open, ChapterState.closed]


# ---------------------------------------------------------------------------
# Seeding helpers
# ---------------------------------------------------------------------------


async def _seed_user(username: str) -> User:
    return await users.create(User(username=username, role=UserRole.author))


async def _seed_book(
    owner_id: int, *, title: str = "A Book", active_notes: str = "the live notes"
) -> Book:
    return await books.create(
        Book(
            title=title,
            description="d",
            owner_id=owner_id,
            collaboration_mode=CollaborationMode.free,
            visibility=Visibility.private,
            state=BookState.active,
            system_prompt="",
            active_notes=active_notes,
        )
    )


async def _seed_chapter(
    book_id: int,
    *,
    state: ChapterState = ChapterState.closing,
    ordinal: int = 1,
    title: str = "Chapter One",
) -> Chapter:
    return await chapters.create(
        Chapter(
            book_id=book_id,
            ordinal=ordinal,
            title=title,
            state=state,
            sketch="",
            text="the body",
            version=1,
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


def _access(
    book_id: int,
    user_id: int,
    *,
    role: AccessRole = AccessRole.owner,
    book_state: BookState = BookState.active,
) -> BookAccess:
    return BookAccess(
        book_id=book_id,
        user_id=user_id,
        role=role,
        book_state=book_state,
        visibility=Visibility.private,
        collaboration_mode=CollaborationMode.free,
    )


def _chapter_subject(chapter: Chapter) -> ResolvedSubject:
    return ResolvedSubject(kind="chapter", chapter=chapter, mode_key="close-chapter")


def _ctx(
    book_id: int,
    user_id: int,
    *,
    subject: object,
    role: AccessRole = AccessRole.owner,
    book_state: BookState = BookState.active,
) -> ToolContext:
    """The turn's tool context, built directly — no turn, no queue, no network."""
    return ToolContext(
        book_id=book_id,
        access=_access(book_id, user_id, role=role, book_state=book_state),
        subject=subject,
    )


async def _call(name: str, context) -> object:
    """Invoke a close tool by its registry name with its own frozen arguments."""
    if name == "draft_chapter_summary":
        return await close_tools.draft_chapter_summary(context, summary=SUMMARY)
    if name == "draft_chapter_notes":
        return await close_tools.draft_chapter_notes(
            context, added=ADDED, modified=MODIFIED, deleted=DELETED
        )
    if name == "propose_active_notes":
        return await close_tools.propose_active_notes(context, active_notes=PROPOSAL)
    if name == "raise_check_flag":
        return await close_tools.raise_check_flag(context, comment=FINDING)
    raise AssertionError(f"unknown close tool {name!r}")


async def _assert_nothing_happened(chapter_id: int, book_id: int, context) -> None:
    """A refusal writes nothing anywhere and records no proposal."""
    stored = await chapters.get_by_id(chapter_id)
    assert stored is not None
    assert stored.summary is None
    assert stored.summary_status is None
    assert await chapter_note_changesets.get_by_chapter(chapter_id) is None
    assert list(await flags.list_by_chapter(chapter_id)) == []
    assert context.active_notes_proposal is None
    book = await books.get_by_id(book_id)
    assert book is not None
    assert book.active_notes == "the live notes"


def _assert_refusal(result: object) -> None:
    assert isinstance(result, str)
    assert result.strip() != ""


# ---------------------------------------------------------------------------
# The success contrast — without it every refusal below is vacuous
# ---------------------------------------------------------------------------


# DoD-7 (the contrast case): on a `closing` chapter of an active book, called by
# the owner, every close tool passes the chain and does its own job. This is what
# makes each refusal below evidence about its rule rather than about the tools.
async def test_the_four_tools_pass_the_chain_and_do_their_job__DoD7(db: DbConfig):
    owner = await _seed_user("close-tools-owner")
    book = await _seed_book(owner.id)
    chapter = await _seed_chapter(book.id, state=ChapterState.closing)
    context = _ctx(book.id, owner.id, subject=_chapter_subject(chapter))

    for name in WRITE_TOOL_NAMES:
        result = await _call(name, context)
        assert isinstance(result, str)
        assert result.strip() != ""

    stored = await chapters.get_by_id(chapter.id)
    assert stored is not None
    assert stored.summary == SUMMARY
    assert stored.summary_status is SummaryStatus.draft

    changeset = await chapter_note_changesets.get_by_chapter(chapter.id)
    assert changeset is not None
    assert changeset.added == ADDED
    assert changeset.modified == MODIFIED
    assert changeset.deleted == DELETED
    assert changeset.status is NoteStatus.draft

    # D7: the proposal is held in the CONTEXT, never persisted, until finalize.
    assert context.active_notes_proposal == PROPOSAL
    book_row = await books.get_by_id(book.id)
    assert book_row is not None
    assert book_row.active_notes == "the live notes"

    raised = list(await flags.list_by_chapter(chapter.id))
    assert len(raised) == 1
    assert raised[0].origin is FlagOrigin.check
    assert raised[0].status is FlagStatus.open
    assert raised[0].comment == FINDING
    assert raised[0].created_by == owner.id


# DoD-7: `draft_chapter_notes` UPSERTS — a second call on the same chapter updates
# the one changeset row rather than creating a second one.
async def test_draft_chapter_notes_upserts_the_single_changeset__DoD7(db: DbConfig):
    owner = await _seed_user("close-tools-upsert-owner")
    book = await _seed_book(owner.id)
    chapter = await _seed_chapter(book.id, state=ChapterState.closing)
    context = _ctx(book.id, owner.id, subject=_chapter_subject(chapter))

    await close_tools.draft_chapter_notes(
        context, added=ADDED, modified=MODIFIED, deleted=DELETED
    )
    first = await chapter_note_changesets.get_by_chapter(chapter.id)
    assert first is not None

    await close_tools.draft_chapter_notes(
        context, added="A revised fact", modified="", deleted=""
    )

    second = await chapter_note_changesets.get_by_chapter(chapter.id)
    assert second is not None
    assert second.id == first.id
    assert second.added == "A revised fact"
    assert second.modified == ""
    assert second.deleted == ""
    assert second.status is NoteStatus.draft


# ---------------------------------------------------------------------------
# Rule 1 — a non-chapter subject
# ---------------------------------------------------------------------------


# DoD-7 (rule 1): a close tool invoked when the turn's subject is not a resolved
# chapter returns a refusal string, writes nothing and raises nothing.
@pytest.mark.parametrize("name", WRITE_TOOL_NAMES)
async def test_a_non_chapter_subject_is_refused__DoD7_rule1(db: DbConfig, name: str):
    owner = await _seed_user(f"rule1-owner-{name}")
    book = await _seed_book(owner.id)
    chapter = await _seed_chapter(book.id, state=ChapterState.closing)
    entry = await _seed_entry(book.id, owner.id)

    subjects = [
        None,
        ResolvedSubject(kind="codex-entry", entry=entry, mode_key="edit-character"),
        ResolvedSubject(kind="book-state", mode_key=None),
        ResolvedSubject(kind="chapters", mode_key=None),
        # A chapter-KIND subject that resolved to no row is still no chapter.
        ResolvedSubject(kind="chapter", chapter=None, mode_key="close-chapter"),
    ]

    for subject in subjects:
        context = _ctx(book.id, owner.id, subject=subject)
        _assert_refusal(await _call(name, context))
        await _assert_nothing_happened(chapter.id, book.id, context)


# ---------------------------------------------------------------------------
# Rule 2 — the chapter is not in `closing`
# ---------------------------------------------------------------------------


# DoD-7 (rule 2): the close tools are reachable only while the chapter is actually
# `closing` — the window `POST /close` opens and finalize or cancel ends. A
# `planned`, `open` or `closed` chapter is refused, and nothing is written.
@pytest.mark.parametrize("name", WRITE_TOOL_NAMES)
@pytest.mark.parametrize(
    "state", NON_CLOSING_STATES, ids=[s.value for s in NON_CLOSING_STATES]
)
async def test_a_chapter_not_closing_is_refused__DoD7_rule2(
    db: DbConfig, name: str, state: ChapterState
):
    owner = await _seed_user(f"rule2-owner-{name}-{state.value}")
    book = await _seed_book(owner.id)
    chapter = await _seed_chapter(book.id, state=state)
    context = _ctx(book.id, owner.id, subject=_chapter_subject(chapter))

    _assert_refusal(await _call(name, context))
    await _assert_nothing_happened(chapter.id, book.id, context)
    # The state itself is untouched by the refusal.
    stored = await chapters.get_by_id(chapter.id)
    assert stored is not None
    assert stored.state is state


# ---------------------------------------------------------------------------
# Rule 3 — an archived book
# ---------------------------------------------------------------------------


# DoD-7 (rule 3): an archived book refuses every close tool, even on a `closing`
# chapter and for the owner. The identical call on an ACTIVE book succeeds, so the
# refusal is the book's state and nothing else.
@pytest.mark.parametrize("name", WRITE_TOOL_NAMES)
async def test_an_archived_book_is_refused__DoD7_rule3(db: DbConfig, name: str):
    owner = await _seed_user(f"rule3-owner-{name}")
    book = await _seed_book(owner.id)
    chapter = await _seed_chapter(book.id, state=ChapterState.closing)

    archived_context = _ctx(
        book.id,
        owner.id,
        subject=_chapter_subject(chapter),
        book_state=BookState.archived,
    )
    _assert_refusal(await _call(name, archived_context))
    await _assert_nothing_happened(chapter.id, book.id, archived_context)

    # The contrast: active book, same call, same caller, same chapter.
    active_context = _ctx(
        book.id, owner.id, subject=_chapter_subject(chapter), book_state=BookState.active
    )
    result = await _call(name, active_context)
    assert isinstance(result, str)
    assert result.strip() != ""


# ---------------------------------------------------------------------------
# Rule 4 — a caller who does not hold `Capability.set_chapter_state`
# ---------------------------------------------------------------------------


# DoD-7 (rule 4 — the rule this feature adds): a caller who does not hold
# `set_chapter_state` — the same capability that gated the close request itself —
# is refused, even though a co-author's own chat also resolves to `close-chapter`
# mode while the owner's chapter sits in `closing`. The refusal is a string, not a
# raise, and it is not a blanket refusal: the OWNER's identical call succeeds.
@pytest.mark.parametrize("name", WRITE_TOOL_NAMES)
@pytest.mark.parametrize(
    "role",
    [AccessRole.co_author, AccessRole.reader, AccessRole.none],
    ids=["co_author", "reader", "none"],
)
async def test_a_caller_without_set_chapter_state_is_refused__DoD7_rule4(
    db: DbConfig, name: str, role: AccessRole
):
    owner = await _seed_user(f"rule4-owner-{name}-{role.value}")
    other = await _seed_user(f"rule4-caller-{name}-{role.value}")
    book = await _seed_book(owner.id)
    chapter = await _seed_chapter(book.id, state=ChapterState.closing)

    refused_context = _ctx(
        book.id, other.id, subject=_chapter_subject(chapter), role=role
    )
    _assert_refusal(await _call(name, refused_context))
    await _assert_nothing_happened(chapter.id, book.id, refused_context)

    # The contrast: the owner, on the same chapter of the same book, is allowed.
    owner_context = _ctx(book.id, owner.id, subject=_chapter_subject(chapter))
    result = await _call(name, owner_context)
    assert isinstance(result, str)
    assert result.strip() != ""


# ---------------------------------------------------------------------------
# The chain is walked IN ORDER — several violations at once still refuse cleanly
# ---------------------------------------------------------------------------


# DoD-7 (the chain, in order): the rules are checked in the order the spec fixes,
# so an EARLIER violation is answered before a later rule is consulted — which is
# what lets rule 1 stand in front of rules 2..4, all of which need the chapter or
# the access rule 1 may not have. Every combination of simultaneous violations
# still comes back as a plain refusal string with nothing written and nothing
# raised.
@pytest.mark.parametrize("name", WRITE_TOOL_NAMES)
async def test_simultaneous_violations_still_refuse_cleanly__DoD7(
    db: DbConfig, name: str
):
    owner = await _seed_user(f"chain-owner-{name}")
    other = await _seed_user(f"chain-caller-{name}")
    book = await _seed_book(owner.id)
    chapter = await _seed_chapter(book.id, state=ChapterState.closing)
    open_chapter = await _seed_chapter(
        book.id, state=ChapterState.open, ordinal=2, title="Chapter Two"
    )

    combinations = [
        # rule 1 + rule 4: no chapter to check a state on, and no capability.
        dict(subject=None, role=AccessRole.co_author, book_state=BookState.active),
        # rule 1 + rule 3 + rule 4.
        dict(subject=None, role=AccessRole.none, book_state=BookState.archived),
        # rule 2 + rule 3.
        dict(
            subject=_chapter_subject(open_chapter),
            role=AccessRole.owner,
            book_state=BookState.archived,
        ),
        # rule 2 + rule 4.
        dict(
            subject=_chapter_subject(open_chapter),
            role=AccessRole.co_author,
            book_state=BookState.active,
        ),
        # rule 3 + rule 4.
        dict(
            subject=_chapter_subject(chapter),
            role=AccessRole.co_author,
            book_state=BookState.archived,
        ),
        # all four at once.
        dict(subject=None, role=AccessRole.reader, book_state=BookState.archived),
    ]

    for combination in combinations:
        context = _ctx(book.id, other.id, **combination)
        _assert_refusal(await _call(name, context))
        await _assert_nothing_happened(chapter.id, book.id, context)
        await _assert_nothing_happened(open_chapter.id, book.id, context)


# ---------------------------------------------------------------------------
# `read_continuity_context` never raises
# ---------------------------------------------------------------------------


# DoD-7: the read-only tool answers with a non-empty string in every one of the
# chain's situations and raises nothing — a raising tool aborts the turn.
async def test_read_continuity_context_never_raises__DoD7(db: DbConfig):
    owner = await _seed_user("read-context-owner")
    other = await _seed_user("read-context-caller")
    book = await _seed_book(owner.id)
    chapter = await _seed_chapter(book.id, state=ChapterState.closing)
    open_chapter = await _seed_chapter(
        book.id, state=ChapterState.open, ordinal=2, title="Chapter Two"
    )

    contexts = [
        _ctx(book.id, owner.id, subject=_chapter_subject(chapter)),
        _ctx(book.id, owner.id, subject=None),
        _ctx(book.id, owner.id, subject=_chapter_subject(open_chapter)),
        _ctx(
            book.id,
            owner.id,
            subject=_chapter_subject(chapter),
            book_state=BookState.archived,
        ),
        _ctx(
            book.id,
            other.id,
            subject=_chapter_subject(chapter),
            role=AccessRole.co_author,
        ),
    ]

    for context in contexts:
        result = await close_tools.read_continuity_context(context)
        assert isinstance(result, str)
        assert result.strip() != ""
