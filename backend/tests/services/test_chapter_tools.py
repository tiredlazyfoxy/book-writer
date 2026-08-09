"""Tests for the four chapter tools and the assistant's refusal mirror
(feature 015, step 010).

Bound to the frozen skeleton (``status.md`` -> ``## Skeleton`` -> Step 010), in
``app.services.chapter_tools``::

    class ReadChapterTextArgs(BaseModel)   # no fields
    class SetChapterTextArgs(BaseModel)  { text: str }
    class UpdateSelectionArgs(BaseModel) { text: str }
    class AddTextArgs(BaseModel)         { text: str }

    async def read_chapter_text(context) -> str
    async def set_chapter_text(context, text: str) -> str
    async def update_selection(context, text: str) -> str
    async def add_text(context, text: str) -> str

    def bind_read_chapter_text(context) -> Callable[..., object]
    def bind_set_chapter_text(context)  -> Callable[..., object]
    def bind_update_selection(context)  -> Callable[..., object]
    def bind_add_text(context)          -> Callable[..., object]

in ``app.services.tools``::

    @dataclass(frozen=True) class ToolContext { book_id; access; subject;
                                                emit_frame; selection_text }
    @dataclass(frozen=True) class ToolDef { name; description; args_schema;
                                            callable=None; binder=None }
    TOOL_REGISTRY: list[ToolDef]     # + read_chapter_text / set_chapter_text /
                                     #   update_selection / add_text
    def resolve_tools(allowed_names) -> list[ToolDef]
    def build_tool_bindings(tools, context: ToolContext | None = None)
        -> tuple[list[dict[str, object]], dict[str, Callable[..., object]]]

and in ``app.services.assistant_runtime`` (shipped by step 009)::

    @dataclass(frozen=True) class ResolvedSubject { kind; entry; chapter; mode_key }
    async def resolve_subject(access, subject_kind=None, subject_id=None, ...)
    def determine_mode(subject) -> str | None
    async def allowed_tool_names(mode_key: str | None) -> tuple[str, ...]

Expected values come from the SPEC ONLY -- ``010.chapter-tools.md`` -> Interface
intent + Definition of done (DoD-1..DoD-12), ``010.context.md`` ("The four rules
the mirror enforces", "Descriptions are part of the contract", "The tools ship
unreachable"), and ``context.md`` -> D4 / D5 / D10 / D11 / D17 -- never from
implementation internals.

DoD-12's "The tools ship unreachable" premise was deliberately reversed by feature
024 (chat-agent-loop) decision D4, which seeds every mode's default tool rows; see
the amended note above that test. The empty-allowlist RULE it guards is unchanged
and is still asserted there.

Test approach (``010.context.md`` -> "Testing"): **no LLM server is contacted and
no live turn is run**. The ``ToolContext`` is built directly and the tools are
invoked as functions, with an in-memory recording sink standing in for the turn's
queue -- which is what keeps DoD-3's "exactly one frame" precise. Chapters in each
state (``closing`` included -- reachable no other way, D8) are written straight
through ``db/chapters.py`` against the ``db`` fixture's throwaway temp SQLite;
``asyncio_mode = "auto"``; no network anywhere.

DoD-13 is ``[manual/live]`` (a real model, a real admin selection and a real
streamed turn) and has no test here. This step's DoD items cite no product id
(``context.md`` -> "Known product gaps"), so test names carry the DoD id alone.
"""

import inspect

from pydantic import BaseModel

from app.db import (
    books,
    chapter_changes,
    chapter_text_revisions,
    chapters,
    codex_entries,
    mode_tools,
    users,
)
from app.db.engine import DbConfig
from app.models.book import Book, BookState, CollaborationMode, Visibility
from app.models.chapter import Chapter, ChapterState
from app.models.codex_entry import CodexEntry, CodexKind
from app.models.schemas.chats import CanvasFrame
from app.models.user import User, UserRole
from app.services import assistant_runtime, chapter_tools, setup
from app.services import tools as tools_module
from app.services.assistant_runtime import NO_SUBJECT, ResolvedSubject
from app.services.authz import AccessRole, BookAccess
from app.services.chapter_tools import (
    AddTextArgs,
    ReadChapterTextArgs,
    SetChapterTextArgs,
    UpdateSelectionArgs,
)
from app.services.tools import ToolContext

import pytest

BODY = "The north gate held.\nThe winter did not.\n"
DRAFT = "Halden keeps the north gate through the long winter."
SELECTION = "the paragraph the author had highlighted"

# context.md -> D4's table, verbatim: the four tool names this step registers.
READ_TOOL = "read_chapter_text"
WHOLE_BODY_TOOL = "set_chapter_text"
SELECTION_TOOL = "update_selection"
APPEND_TOOL = "add_text"
CHAPTER_TOOL_NAMES = {READ_TOOL, WHOLE_BODY_TOOL, SELECTION_TOOL, APPEND_TOOL}

# The registry's pre-015 contents -- the entries the four must not collide with.
PRE_EXISTING_TOOL_NAMES = {
    "web_search",
    "codex_search",
    "codex_read_entry",
    "write_codex_draft",
}

# Each write tool with the frame operation the spec assigns it (DoD-3).
WRITE_TOOLS = [
    (WHOLE_BODY_TOOL, "replace"),
    (SELECTION_TOOL, "replace_selection"),
    (APPEND_TOOL, "append"),
]
WRITE_TOOL_IDS = [name for name, _ in WRITE_TOOLS]

WRITE_SCHEMAS = {
    WHOLE_BODY_TOOL: SetChapterTextArgs,
    SELECTION_TOOL: UpdateSelectionArgs,
    APPEND_TOOL: AddTextArgs,
}
ALL_SCHEMAS = dict(WRITE_SCHEMAS, **{READ_TOOL: ReadChapterTextArgs})


def _write_tool(name: str):
    """The module-level callable behind a write tool's registry name."""
    return getattr(chapter_tools, name)


# ---------------------------------------------------------------------------
# The recording emitter -- the FrameEmitter shape: an awaited (event, payload).
# ---------------------------------------------------------------------------


class _Recorder:
    """Records every ``await emit_frame(event, payload)`` call.

    ``exc`` makes the sink FAIL, standing in for the turn queue failing while a
    frame is being put onto it (DoD-11).
    """

    def __init__(self, *, exc: Exception | None = None) -> None:
        self.frames: list[tuple[str, object]] = []
        self._exc = exc

    async def __call__(self, event, data) -> None:
        if self._exc is not None:
            raise self._exc
        self.frames.append((event, data))


# ---------------------------------------------------------------------------
# Seeding helpers (rows built through the db/ layer, as a service spec does).
# ---------------------------------------------------------------------------


async def _seed_user(username: str = "author") -> User:
    return await users.create(User(username=username, role=UserRole.author))


async def _seed_book(
    owner_id: int,
    *,
    title: str = "A Book",
    collaboration_mode: CollaborationMode = CollaborationMode.free,
) -> Book:
    return await books.create(
        Book(
            title=title,
            description="d",
            owner_id=owner_id,
            collaboration_mode=collaboration_mode,
            visibility=Visibility.private,
            state=BookState.active,
            system_prompt="",
            active_notes="",
        )
    )


async def _seed_chapter(
    book_id: int,
    *,
    state: ChapterState = ChapterState.open,
    ordinal: int = 1,
    title: str = "Chapter One",
    text: str = BODY,
) -> Chapter:
    """A chapter written straight through db/chapters.py in the given state.

    A tool spec must not depend on the transition path to reach a state, and
    `closing` is reachable no other way in this feature (context.md -> D8).
    """
    return await chapters.create(
        Chapter(
            book_id=book_id,
            ordinal=ordinal,
            title=title,
            state=state,
            sketch="",
            text=text,
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
    *,
    user_id: int = 2,
    role: AccessRole = AccessRole.owner,
    book_state: BookState = BookState.active,
    collaboration_mode: CollaborationMode = CollaborationMode.free,
) -> BookAccess:
    """A BookAccess built directly -- the frozen dataclass, no resolve, no HTTP."""
    return BookAccess(
        book_id=book_id,
        user_id=user_id,
        role=role,
        book_state=book_state,
        visibility=Visibility.private,
        collaboration_mode=collaboration_mode,
    )


def _chapter_subject(chapter: Chapter, mode_key: str = "write-chapter"):
    return ResolvedSubject(kind="chapter", chapter=chapter, mode_key=mode_key)


def _ctx(
    book_id: int,
    *,
    subject=None,
    emitter=None,
    role: AccessRole = AccessRole.owner,
    book_state: BookState = BookState.active,
    collaboration_mode: CollaborationMode = CollaborationMode.free,
    with_access: bool = True,
    selection_text: str | None = SELECTION,
) -> ToolContext:
    return ToolContext(
        book_id=book_id,
        access=(
            _access(
                book_id,
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


def _assert_refusal(result, recorder: _Recorder) -> None:
    """A refusal: a non-empty STRING back, and NOT ONE frame emitted."""
    assert isinstance(result, str)
    assert result.strip() != ""
    assert recorder.frames == []


def _assert_one_frame(recorder: _Recorder) -> CanvasFrame:
    assert len(recorder.frames) == 1
    event, payload = recorder.frames[0]
    assert event == "canvas"
    assert isinstance(payload, CanvasFrame)
    return payload


def _registry_entry(name: str):
    matches = [tool for tool in tools_module.TOOL_REGISTRY if tool.name == name]
    assert len(matches) == 1, f"{name} is not a single registry entry"
    return matches[0]


# ---------------------------------------------------------------------------
# DoD-1 — the four are registered, distinctly named, bound and schema-bearing
# ---------------------------------------------------------------------------


# DoD-1: all four tools are in TOOL_REGISTRY with distinct, stable names that
# collide with no existing entry, each carrying EXACTLY ONE of a callable or a
# binder, and each with a Pydantic argument schema.
def test_four_chapter_tools_are_registered_with_distinct_names__DoD1():
    registry_names = [tool.name for tool in tools_module.TOOL_REGISTRY]

    # Present, by the exact names D4's table fixes (a mode_tool row is a string
    # reference into this registry, so the names are the contract).
    assert CHAPTER_TOOL_NAMES <= set(registry_names)

    # Distinct: no name appears twice anywhere in the registry...
    assert len(registry_names) == len(set(registry_names))
    # ...and none of the four collides with an entry that was already there.
    assert CHAPTER_TOOL_NAMES.isdisjoint(PRE_EXISTING_TOOL_NAMES)
    assert PRE_EXISTING_TOOL_NAMES <= set(registry_names)


# DoD-1: each of the four carries exactly one of a callable or a binder, and a
# Pydantic argument schema.
@pytest.mark.parametrize("name", sorted(CHAPTER_TOOL_NAMES))
def test_each_chapter_tool_is_singly_bound_with_a_schema__DoD1(name):
    entry = _registry_entry(name)

    # Exactly one of the two -- never both, never neither.
    assert (entry.callable is None) != (entry.binder is None)

    # A Pydantic argument schema, and the one this tool declares.
    assert isinstance(entry.args_schema, type)
    assert issubclass(entry.args_schema, BaseModel)
    assert entry.args_schema is ALL_SCHEMAS[name]


# ---------------------------------------------------------------------------
# DoD-2 — the read tool returns the SAVED body, in every chapter state
# ---------------------------------------------------------------------------


# DoD-2 (Interface intent -- a `closed` chapter can be read): the read tool
# returns the chapter's SAVED body text for a resolved chapter subject, in every
# chapter state including `closed`.
@pytest.mark.parametrize(
    "state",
    [
        ChapterState.planned,
        ChapterState.open,
        ChapterState.closing,
        ChapterState.closed,
    ],
    ids=["planned", "open", "closing", "closed"],
)
async def test_read_returns_the_saved_body_in_every_state__DoD2(db: DbConfig, state):
    user = await _seed_user()
    book = await _seed_book(user.id)
    saved_body = f"SAVED_BODY_{state.value.upper()}\nsecond line\n"
    chapter = await _seed_chapter(book.id, state=state, text=saved_body)
    recorder = _Recorder()

    result = await chapter_tools.read_chapter_text(
        _ctx(book.id, subject=_chapter_subject(chapter), emitter=recorder)
    )

    assert isinstance(result, str)
    # The body the model gets back is the one the server has stored.
    stored = await chapters.get_by_id(chapter.id)
    assert stored is not None
    assert stored.text == saved_body
    assert saved_body in result


# DoD-2 (Interface intent -- the read is NOT subject to the write refusals): the
# same read succeeds on an archived book and for a co-author in a proposal-mode
# book, both of which refuse every write.
async def test_read_is_not_subject_to_the_write_refusals__DoD2(db: DbConfig):
    user = await _seed_user()

    archived_book = await _seed_book(user.id, title="Archived")
    archived_chapter = await _seed_chapter(archived_book.id, text="ARCHIVED_BOOK_BODY")
    archived_result = await chapter_tools.read_chapter_text(
        _ctx(
            archived_book.id,
            subject=_chapter_subject(archived_chapter),
            emitter=_Recorder(),
            book_state=BookState.archived,
        )
    )
    assert "ARCHIVED_BOOK_BODY" in archived_result

    proposal_book = await _seed_book(
        user.id, title="Proposal", collaboration_mode=CollaborationMode.proposal
    )
    proposal_chapter = await _seed_chapter(proposal_book.id, text="PROPOSAL_BOOK_BODY")
    proposal_result = await chapter_tools.read_chapter_text(
        _ctx(
            proposal_book.id,
            subject=_chapter_subject(proposal_chapter),
            emitter=_Recorder(),
            role=AccessRole.co_author,
            collaboration_mode=CollaborationMode.proposal,
        )
    )
    assert "PROPOSAL_BOOK_BODY" in proposal_result


# ---------------------------------------------------------------------------
# DoD-3 — each write emits EXACTLY ONE frame, with its own operation
# ---------------------------------------------------------------------------


# DoD-3 (context.md -> D17; CanvasField was NOT widened): each of the three write
# tools emits exactly one canvas frame carrying the chapter's id, the "body"
# field, the text it was given and its own operation -- replace,
# replace-selection and append respectively.
@pytest.mark.parametrize(("name", "op"), WRITE_TOOLS, ids=WRITE_TOOL_IDS)
async def test_each_write_emits_exactly_one_frame_with_its_op__DoD3(
    db: DbConfig, name, op
):
    user = await _seed_user()
    book = await _seed_book(user.id)
    chapter = await _seed_chapter(book.id, state=ChapterState.open)
    recorder = _Recorder()

    await _write_tool(name)(
        _ctx(book.id, subject=_chapter_subject(chapter), emitter=recorder),
        text=DRAFT,
    )

    # Exactly one frame -- not zero, not two.
    payload = _assert_one_frame(recorder)
    assert payload.subject_kind == "chapter"
    assert payload.subject_id == str(chapter.id)
    # A chapter's body IS the "body" field -- there is no "text" member (D17).
    assert payload.field == "body"
    assert payload.text == DRAFT
    assert payload.op == op

    # The payload reports what it was given, not a fixed value: a second,
    # independent call with different text carries that text.
    other = _Recorder()
    await _write_tool(name)(
        _ctx(book.id, subject=_chapter_subject(chapter), emitter=other),
        text="a completely different draft",
    )
    second = _assert_one_frame(other)
    assert second.text == "a completely different draft"
    assert second.op == op


# DoD-3: the three operations are distinct -- the same text through the three
# tools produces three different operations on three otherwise identical frames.
async def test_the_three_writes_carry_three_distinct_ops__DoD3(db: DbConfig):
    user = await _seed_user()
    book = await _seed_book(user.id)
    chapter = await _seed_chapter(book.id, state=ChapterState.open)

    ops = []
    for name, _ in WRITE_TOOLS:
        recorder = _Recorder()
        await _write_tool(name)(
            _ctx(book.id, subject=_chapter_subject(chapter), emitter=recorder),
            text=DRAFT,
        )
        payload = _assert_one_frame(recorder)
        assert payload.subject_id == str(chapter.id)
        assert payload.field == "body"
        assert payload.text == DRAFT
        ops.append(payload.op)

    assert ops == [op for _, op in WRITE_TOOLS]
    assert len(set(ops)) == 3


# ---------------------------------------------------------------------------
# DoD-4 — no write tool touches the database (the structural property)
# ---------------------------------------------------------------------------


# DoD-4 (Interface intent -- "there is no code path from a chat turn to the
# `chapters`, `chapter_changes` or `chapter_text_revisions` tables, and that
# absence is the guarantee"): after every write tool runs, the chapter's stored
# body, its version and its modified timestamp are unchanged, and no
# ChapterChange and no ChapterTextRevision row exists.
#
# The write's OWN success is asserted first -- otherwise "nothing was written"
# would be satisfied by a tool that did nothing at all.
@pytest.mark.parametrize(("name", "op"), WRITE_TOOLS, ids=WRITE_TOOL_IDS)
async def test_a_write_tool_leaves_all_three_tables_untouched__DoD4(
    db: DbConfig, name, op
):
    user = await _seed_user()
    book = await _seed_book(user.id)
    chapter = await _seed_chapter(book.id, state=ChapterState.open, text=BODY)

    before = await chapters.get_by_id(chapter.id)
    assert before is not None
    recorder = _Recorder()

    result = await _write_tool(name)(
        _ctx(book.id, subject=_chapter_subject(chapter), emitter=recorder),
        text=DRAFT,
    )

    # (a) the write really happened: one frame, and a non-empty confirmation
    #     string back to the model.
    payload = _assert_one_frame(recorder)
    assert payload.text == DRAFT
    assert payload.op == op
    assert isinstance(result, str)
    assert result.strip() != ""

    # (b) and yet nothing reached the database.
    after = await chapters.get_by_id(chapter.id)
    assert after is not None
    assert after.text == before.text == BODY
    assert after.version == before.version
    assert after.modified_at == before.modified_at
    assert after.state is before.state

    assert list(await chapter_changes.list_by_chapter(chapter.id)) == []
    assert list(await chapter_text_revisions.list_by_chapter(chapter.id)) == []


# DoD-4: the same holds across a SEQUENCE of writes -- three drafts through the
# three tools leave the stored chapter and both history tables exactly as they
# were seeded.
async def test_a_sequence_of_writes_still_stores_nothing__DoD4(db: DbConfig):
    user = await _seed_user()
    book = await _seed_book(user.id)
    chapter = await _seed_chapter(book.id, state=ChapterState.open, text=BODY)
    before = await chapters.get_by_id(chapter.id)
    assert before is not None

    for index, (name, _) in enumerate(WRITE_TOOLS):
        recorder = _Recorder()
        await _write_tool(name)(
            _ctx(book.id, subject=_chapter_subject(chapter), emitter=recorder),
            text=f"{DRAFT} ({index})",
        )
        # Each one landed its frame...
        assert len(recorder.frames) == 1

    # ...and none of them landed a row.
    after = await chapters.get_by_id(chapter.id)
    assert after is not None
    assert after.text == BODY
    assert after.version == before.version
    assert after.modified_at == before.modified_at
    assert list(await chapter_changes.list_by_chapter(chapter.id)) == []
    assert list(await chapter_text_revisions.list_by_chapter(chapter.id)) == []


# ---------------------------------------------------------------------------
# DoD-5 — no chapter subject: a refusal STRING, no frame, no raise
# ---------------------------------------------------------------------------


# DoD-5 (010.context.md -- refusal rule 1, "the subject is not a chapter"): a
# write tool invoked when the turn has no chapter subject returns a refusal
# string, emits no frame and raises nothing.
@pytest.mark.parametrize(("name", "op"), WRITE_TOOLS, ids=WRITE_TOOL_IDS)
async def test_write_with_no_chapter_subject_is_refused__DoD5(db: DbConfig, name, op):
    user = await _seed_user()
    book = await _seed_book(user.id)
    entry = await _seed_entry(book.id, user.id)
    chapter = await _seed_chapter(book.id, state=ChapterState.open)

    subjects = [
        None,
        NO_SUBJECT,
        ResolvedSubject(kind="codex-entry", entry=entry, mode_key="edit-character"),
        ResolvedSubject(kind="book-state", mode_key=None),
        ResolvedSubject(kind="chapters", mode_key=None),
        ResolvedSubject(kind="chats", mode_key=None),
        # A chapter-KIND subject that resolved to no row is still no chapter.
        ResolvedSubject(kind="chapter", chapter=None, mode_key="write-chapter"),
    ]

    for subject in subjects:
        recorder = _Recorder()
        result = await _write_tool(name)(
            _ctx(book.id, subject=subject, emitter=recorder), text=DRAFT
        )
        _assert_refusal(result, recorder)

    # The refusal is the missing subject, not a blanket refusal: the same tool
    # with a resolved open chapter writes.
    allowed = _Recorder()
    await _write_tool(name)(
        _ctx(book.id, subject=_chapter_subject(chapter), emitter=allowed), text=DRAFT
    )
    assert len(allowed.frames) == 1


# ---------------------------------------------------------------------------
# DoD-6 — planned / closing / closed: refused by the same rule as the author
# ---------------------------------------------------------------------------


# DoD-6 (domain-chapter.md -- `closing` and `closed` refuse all writes to `text`,
# from a member and from the assistant alike; `planned` has no body yet): a write
# tool invoked on a chapter that is `planned`, `closing` or `closed` returns a
# refusal string NAMING the chapter's state, emits no frame and raises nothing.
@pytest.mark.parametrize(
    "state",
    [ChapterState.planned, ChapterState.closing, ChapterState.closed],
    ids=["planned", "closing", "closed"],
)
@pytest.mark.parametrize(("name", "op"), WRITE_TOOLS, ids=WRITE_TOOL_IDS)
async def test_write_on_a_non_open_chapter_is_refused_naming_the_state__DoD6(
    db: DbConfig, name, op, state
):
    user = await _seed_user()
    book = await _seed_book(user.id)
    chapter = await _seed_chapter(book.id, state=state)
    recorder = _Recorder()

    result = await _write_tool(name)(
        _ctx(book.id, subject=_chapter_subject(chapter), emitter=recorder), text=DRAFT
    )

    _assert_refusal(result, recorder)
    # The model is told WHICH state refused it.
    assert state.value in result.lower()

    # The refusal is the state rule: an `open` sibling in the same book writes.
    open_chapter = await _seed_chapter(
        book.id, state=ChapterState.open, ordinal=2, title="Chapter Two"
    )
    allowed = _Recorder()
    await _write_tool(name)(
        _ctx(book.id, subject=_chapter_subject(open_chapter), emitter=allowed),
        text=DRAFT,
    )
    assert len(allowed.frames) == 1


# ---------------------------------------------------------------------------
# DoD-7 — an archived book refuses every write (D10, in the tool vocabulary)
# ---------------------------------------------------------------------------


# DoD-7 (context.md -> D10, read off ToolContext.access.book_state): a write tool
# invoked on an ARCHIVED book returns a refusal string, emits no frame and raises
# nothing.
@pytest.mark.parametrize(("name", "op"), WRITE_TOOLS, ids=WRITE_TOOL_IDS)
async def test_write_on_an_archived_book_is_refused__DoD7(db: DbConfig, name, op):
    user = await _seed_user()
    book = await _seed_book(user.id)
    chapter = await _seed_chapter(book.id, state=ChapterState.open)
    recorder = _Recorder()

    result = await _write_tool(name)(
        _ctx(
            book.id,
            subject=_chapter_subject(chapter),
            emitter=recorder,
            book_state=BookState.archived,
        ),
        text=DRAFT,
    )

    _assert_refusal(result, recorder)

    # The refusal is the book's archived state, not the chapter or the caller:
    # the identical call on an active book writes.
    active = _Recorder()
    await _write_tool(name)(
        _ctx(
            book.id,
            subject=_chapter_subject(chapter),
            emitter=active,
            book_state=BookState.active,
        ),
        text=DRAFT,
    )
    assert len(active.frames) == 1


# ---------------------------------------------------------------------------
# DoD-8 — a co-author in a proposal-mode book (D11); the owner is unaffected
# ---------------------------------------------------------------------------


# DoD-8 (context.md -> D11, read off access.role + access.collaboration_mode): a
# write tool invoked by a CO-AUTHOR in a PROPOSAL-mode book returns a refusal
# string naming FEAT-010 as unbuilt, emits no frame and raises nothing; the same
# call as the OWNER succeeds.
@pytest.mark.parametrize(("name", "op"), WRITE_TOOLS, ids=WRITE_TOOL_IDS)
async def test_co_author_in_proposal_mode_is_refused_naming_feat010__DoD8(
    db: DbConfig, name, op
):
    user = await _seed_user()
    book = await _seed_book(user.id, collaboration_mode=CollaborationMode.proposal)
    chapter = await _seed_chapter(book.id, state=ChapterState.open)
    recorder = _Recorder()

    refused = await _write_tool(name)(
        _ctx(
            book.id,
            subject=_chapter_subject(chapter),
            emitter=recorder,
            role=AccessRole.co_author,
            collaboration_mode=CollaborationMode.proposal,
        ),
        text=DRAFT,
    )

    _assert_refusal(refused, recorder)
    # The reason names the unbuilt mechanism by its product id.
    assert "FEAT-010" in refused

    # The OWNER of the same proposal-mode book is not refused.
    owner_recorder = _Recorder()
    allowed = await _write_tool(name)(
        _ctx(
            book.id,
            subject=_chapter_subject(chapter),
            emitter=owner_recorder,
            role=AccessRole.owner,
            collaboration_mode=CollaborationMode.proposal,
        ),
        text=DRAFT,
    )
    payload = _assert_one_frame(owner_recorder)
    assert payload.subject_id == str(chapter.id)
    assert payload.text == DRAFT
    assert isinstance(allowed, str)
    assert "FEAT-010" not in allowed

    # ...and the rule is the collaboration mode, not the role alone: the same
    # co-author writes in a FREE-mode book.
    free_book = await _seed_book(user.id, title="Free")
    free_chapter = await _seed_chapter(free_book.id, state=ChapterState.open)
    free_recorder = _Recorder()
    await _write_tool(name)(
        _ctx(
            free_book.id,
            subject=_chapter_subject(free_chapter),
            emitter=free_recorder,
            role=AccessRole.co_author,
            collaboration_mode=CollaborationMode.free,
        ),
        text=DRAFT,
    )
    assert len(free_recorder.frames) == 1


# ---------------------------------------------------------------------------
# DoD-9 — the read tool is refused on another book's chapter, BY RESOLUTION
# ---------------------------------------------------------------------------


# DoD-9: the read tool is refused on a chapter in ANOTHER book -- by subject
# resolution rather than by a check inside the tool. The turn's subject is
# resolved the way a real turn resolves it, and the cross-book chapter never
# becomes a subject at all, so the tool has nothing to read.
async def test_read_of_another_books_chapter_is_refused_by_resolution__DoD9(
    db: DbConfig,
):
    user = await _seed_user()
    book = await _seed_book(user.id)
    stranger = await _seed_user("stranger")
    other_book = await _seed_book(stranger.id, title="Their Book")
    foreign = await _seed_chapter(
        other_book.id, state=ChapterState.open, text="SECRET_FOREIGN_BODY"
    )

    # Resolution refuses first: the foreign id yields no chapter subject.
    resolved = await assistant_runtime.resolve_subject(
        _access(book.id, user_id=user.id),
        subject_kind="chapter",
        subject_id=str(foreign.id),
    )
    assert resolved.chapter is None

    recorder = _Recorder()
    result = await chapter_tools.read_chapter_text(
        _ctx(book.id, subject=resolved, emitter=recorder)
    )

    # A string back, and not one character of the other book's chapter.
    assert isinstance(result, str)
    assert result.strip() != ""
    assert "SECRET_FOREIGN_BODY" not in result
    assert recorder.frames == []

    # The row exists and reads perfectly from ITS OWN book, so the refusal above
    # is the cross-book rule and not a missing row.
    own = await assistant_runtime.resolve_subject(
        _access(other_book.id, user_id=stranger.id),
        subject_kind="chapter",
        subject_id=str(foreign.id),
    )
    assert own.chapter is not None
    own_result = await chapter_tools.read_chapter_text(
        _ctx(other_book.id, subject=own, emitter=_Recorder())
    )
    assert "SECRET_FOREIGN_BODY" in own_result


# ---------------------------------------------------------------------------
# DoD-10 — offered with no tool context, a bound tool is skipped, not raised
# ---------------------------------------------------------------------------


# DoD-10 (the existing bound-tool rule, exercised for these four): building the
# bindings for the four with NO tool context skips them rather than raising --
# and with a context they bind, each free parameter set being exactly its args
# schema's fields, so the skip is the missing-context rule and not an absence.
async def test_bound_chapter_tools_are_skipped_without_a_context__DoD10(db: DbConfig):
    user = await _seed_user()
    book = await _seed_book(user.id)
    selected = tools_module.resolve_tools(sorted(CHAPTER_TOOL_NAMES))
    assert {tool.name for tool in selected} == CHAPTER_TOOL_NAMES

    # (a) no context -- nothing raises, and none of the four is built.
    definitions, callables = tools_module.build_tool_bindings(selected, None)
    assert set(callables.keys()).isdisjoint(CHAPTER_TOOL_NAMES)
    assert {
        d["function"]["name"] for d in definitions
    }.isdisjoint(CHAPTER_TOOL_NAMES)
    # The two maps stay in step, as the client's pre-flight requires.
    assert {d["function"]["name"] for d in definitions} == set(callables.keys())

    # (b) with a context they ARE built, bound to that turn.
    context = _ctx(book.id, subject=None, emitter=_Recorder())
    with_context_definitions, with_context_callables = tools_module.build_tool_bindings(
        selected, context
    )
    assert set(with_context_callables.keys()) == CHAPTER_TOOL_NAMES
    assert {
        d["function"]["name"] for d in with_context_definitions
    } == CHAPTER_TOOL_NAMES

    # Each binding leaves exactly its schema's fields free, so the `llm` client
    # can dispatch it from the model's arguments alone.
    for name, schema in ALL_SCHEMAS.items():
        bound = with_context_callables[name]
        assert set(inspect.signature(bound).parameters) == set(schema.model_fields)


# ---------------------------------------------------------------------------
# DoD-11 — no refusal path anywhere in the module raises
# ---------------------------------------------------------------------------


# DoD-11 (a raising tool aborts the turn -- codex_tools.py's rule): no refusal
# path anywhere in this module raises. Every failure and every refusal, across
# all four tools and every refusal rule, comes back as a string. Nothing here is
# wrapped in try/except: an exception fails the test, which is the point.
async def test_no_path_in_any_of_the_four_tools_raises__DoD11(db: DbConfig):
    user = await _seed_user()
    book = await _seed_book(user.id)
    entry = await _seed_entry(book.id, user.id)
    open_chapter = await _seed_chapter(book.id, state=ChapterState.open)
    planned = await _seed_chapter(book.id, state=ChapterState.planned, ordinal=2)
    closing = await _seed_chapter(book.id, state=ChapterState.closing, ordinal=3)
    closed = await _seed_chapter(book.id, state=ChapterState.closed, ordinal=4)
    open_subject = _chapter_subject(open_chapter)

    contexts = [
        # every refusal rule, one at a time
        _ctx(book.id, subject=None, emitter=_Recorder()),
        _ctx(book.id, subject=NO_SUBJECT, emitter=_Recorder()),
        _ctx(
            book.id,
            subject=ResolvedSubject(kind="codex-entry", entry=entry),
            emitter=_Recorder(),
        ),
        _ctx(book.id, subject=ResolvedSubject(kind="book-state"), emitter=_Recorder()),
        _ctx(book.id, subject=_chapter_subject(planned), emitter=_Recorder()),
        _ctx(book.id, subject=_chapter_subject(closing), emitter=_Recorder()),
        _ctx(book.id, subject=_chapter_subject(closed), emitter=_Recorder()),
        _ctx(
            book.id,
            subject=open_subject,
            emitter=_Recorder(),
            book_state=BookState.archived,
        ),
        _ctx(
            book.id,
            subject=open_subject,
            emitter=_Recorder(),
            role=AccessRole.co_author,
            collaboration_mode=CollaborationMode.proposal,
        ),
        # and every failure: no access context, no emitter, a failing queue,
        # and no selection text with a selection-shaped call.
        _ctx(book.id, subject=open_subject, emitter=_Recorder(), with_access=False),
        _ctx(book.id, subject=open_subject, emitter=None),
        _ctx(
            book.id,
            subject=open_subject,
            emitter=_Recorder(exc=RuntimeError("queue is closed")),
        ),
        _ctx(book.id, subject=open_subject, emitter=_Recorder(), selection_text=None),
    ]

    for context in contexts:
        for name in (WHOLE_BODY_TOOL, SELECTION_TOOL, APPEND_TOOL):
            result = await _write_tool(name)(context, text=DRAFT)
            assert isinstance(result, str)
            assert result.strip() != ""

        read_result = await chapter_tools.read_chapter_text(context)
        assert isinstance(read_result, str)
        assert read_result.strip() != ""


# ---------------------------------------------------------------------------
# DoD-12 — the gating is the mode's `mode_tool` rows, not the registration
# ---------------------------------------------------------------------------

# Feature 024 (chat-agent-loop), decision D4, DELIBERATELY REVERSES this clause's
# premise. This test was written as "the four ship UNREACHABLE": a fresh install
# seeded no `mode_tool` row, so `write-chapter` resolved to an empty allowlist and
# the four chapter tools could not be reached. D4 ("seed all five modes' prompts
# and tool rows, by explicit author decision") makes `create_database` seed
# `write-chapter`'s default set, so the four are reachable on a fresh install --
# that reversal is the feature, and 024/plan.md records it for `outcome.md`.
#
# What D4 explicitly does NOT change (024/context.md -> "Standing constraints":
# "The empty-allowlist rule itself is untouched -- only the seeded *starting
# state* changes") is the RULE this test really guards: zero rows means an empty
# allowlist, and registration alone grants nothing. Both halves are still asserted
# below, now on a mode whose rows have been cleared. The test's name moved with
# its premise; the `__DoD12` tag is intact.

# 024/context.md -> "Default per-mode tool selections" (authoritative): the set
# `write-chapter` is seeded with on a fresh database.
WRITE_CHAPTER_DEFAULT_TOOLS = {
    "web_search",
    "codex_search",
    "codex_read_entry",
    "read_chapter_text",
    "set_chapter_text",
    "update_selection",
    "add_text",
}


async def test_open_chapter_turn_is_offered_the_seeded_four__DoD12(db: DbConfig):
    # A fresh install: the modes AND their default selections are seeded
    # (024/plan.md -> DoD-4).
    await setup.create_database("root", "password123", "password123")
    seeded = [row.tool_name for row in await mode_tools.list_by_mode("write-chapter")]
    assert set(seeded) == WRITE_CHAPTER_DEFAULT_TOOLS
    assert len(seeded) == len(WRITE_CHAPTER_DEFAULT_TOOLS)

    user = await _seed_user()
    book = await _seed_book(user.id)
    chapter = await _seed_chapter(book.id, state=ChapterState.open)

    resolved = await assistant_runtime.resolve_subject(
        _access(book.id, user_id=user.id),
        subject_kind="chapter",
        subject_id=str(chapter.id),
    )
    mode = assistant_runtime.determine_mode(resolved)
    assert mode == "write-chapter"

    names = await assistant_runtime.allowed_tool_names(mode)

    # The allowlist is exactly the mode's seeded rows -- still driven by the rows,
    # still not the whole registry.
    assert set(names) == WRITE_CHAPTER_DEFAULT_TOOLS
    assert CHAPTER_TOOL_NAMES <= set(names)
    # ...and every one of them resolves for the turn.
    assert {tool.name for tool in tools_module.resolve_tools(list(names))} == set(names)

    # All four ARE in the registry (DoD-1) -- registration and selection are still
    # two different things, which the clearing below proves.
    assert CHAPTER_TOOL_NAMES <= {tool.name for tool in tools_module.TOOL_REGISTRY}

    # The empty-allowlist rule is UNTOUCHED by D4: with the mode's rows removed,
    # registration alone grants nothing again.
    await mode_tools.delete_by_mode("write-chapter")
    cleared = await assistant_runtime.allowed_tool_names(mode)
    assert cleared == ()
    assert set(cleared).isdisjoint(CHAPTER_TOOL_NAMES)
    assert tools_module.resolve_tools(list(cleared)) == []
