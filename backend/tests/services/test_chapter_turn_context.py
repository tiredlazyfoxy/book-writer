"""Tests for the chapter canvas protocol (feature 015, step 009).

Three things this step adds, asserted from the SPEC alone
(``009.chapter-canvas-protocol.md`` -> Interface intent + DoD-1..DoD-12,
``009.context.md``, ``context.md`` -> D4 / D5 / D17 / "Mode seeding"):

    1. the ``canvas`` frame's operation discriminator, defaulted to replace;
    2. the author's selection carried on the turn request into the per-turn
       tool context, and persisted nowhere;
    3. the chapter branch of ``determine_mode`` -- which does not exist before
       this step.

Bound to the frozen skeleton (``status.md`` -> ``## Skeleton`` -> Step 009):

in ``app.models.schemas.chats``::

    CanvasOp = Literal["replace", "append", "replace_selection"]
    CanvasField = Literal["name", "body"]                    # UNCHANGED
    class CanvasFrame(BaseModel) { subject_kind; subject_id; field; text;
                                   op: CanvasOp = "replace" }
    class TurnRequest(BaseModel) { prompt; subject_kind; subject_id;
                                   codex_kind; selection_text: str | None = None }

in ``app.services.tools``::

    @dataclass(frozen=True) class ToolContext { book_id; access; subject;
                                                emit_frame;
                                                selection_text: str | None = None }

in ``app.services.assistant_runtime``::

    @dataclass(frozen=True) class ResolvedSubject { kind; entry;
                                                    chapter: Chapter | None = None;
                                                    mode_key }
    _CHAPTER_STATE_MODES: dict[str, str]
    async def resolve_subject(access, subject_kind=None, subject_id=None,
                              codex_kind=None) -> ResolvedSubject
    def determine_mode(subject: ResolvedSubject) -> str | None
    async def allowed_tool_names(mode_key: str | None) -> tuple[str, ...]
    BASE_TOOL_NAMES: tuple[str, ...]

and in ``app.services.chat_turn``::

    @dataclass(frozen=True) class TurnContext { chat; server; resolved_key;
        subject; access; selection_text: str | None = None }
    async def prepare_turn(access, chat_id: str, request: TurnRequest | None = None)
        -> TurnContext

Test approach (``009.context.md`` -> "Testing"): **no LLM server is contacted
and no live turn is run** -- ``chat_with_tools`` is called nowhere in this file.
Subject resolution, ``determine_mode``, ``allowed_tool_names``, the tool-context
construction and the frame type are exercised **directly, as functions**.
Chapters in each state (``closing`` included -- reachable no other way, D8) are
written straight through ``db/chapters.py`` against the ``db`` fixture's
throwaway temp SQLite; ``asyncio_mode = "auto"``; no network anywhere.

Scope notes:
    - ``services/codex_tools.py`` is NOT this step's source (``009.context.md``);
      its emission and its refusal strings are a **regression surface** here
      (DoD-2), as is codex mode determination (DoD-10). Neither is re-tested
      beyond "unchanged".
    - **Nothing in this file seeds an ``AssistantMode`` row.** DoD-12 asserts
      that a freshly initialised instance already carries the two chapter mode
      keys, because a mode key with no row fails *silently* (``context.md`` ->
      "Mode seeding").
    - DoD-4's ``TurnContext -> ToolContext`` leg is exercised as far as the
      no-live-turn rule allows: the request -> per-turn context transfer through
      ``prepare_turn``, and the tool context's own reading of the selection.
    - This step's DoD items cite no product id (``context.md`` -> "Known product
      gaps"), so test names carry the DoD id alone.
"""

from typing import get_args

import pytest
from pydantic import ValidationError

from app.db import (
    assistant_modes,
    books,
    chapter_changes,
    chapter_text_revisions,
    chapters,
    chat_messages,
    chats,
    codex_entries,
    llm_servers,
    users,
)
from app.db.engine import DbConfig, is_db_ready
from app.models.book import Book, BookState, CollaborationMode, Visibility
from app.models.chapter import Chapter, ChapterState
from app.models.chat import Chat
from app.models.codex_entry import CodexEntry, CodexKind
from app.models.llm_server import LlmServer
from app.models.schemas.chats import CanvasField, CanvasFrame, CanvasOp, TurnRequest
from app.models.user import User, UserRole
from app.services import assistant_runtime, chat_turn, codex_tools, setup
from app.services import tools as tools_module
from app.services.assistant_runtime import (
    BASE_TOOL_NAMES,
    NO_SUBJECT,
    ResolvedSubject,
)
from app.services.authz import AccessRole, BookAccess
from app.services.tools import ToolContext

DRAFT = "Halden keeps the north gate through the long winter."
SELECTION = "the paragraph the author had highlighted"
BODY = "line one\nline two\n"


# ---------------------------------------------------------------------------
# The recording emitter -- the FrameEmitter shape: an awaited (event, payload).
# ---------------------------------------------------------------------------


class _Recorder:
    """Records every ``await emit_frame(event, payload)`` call."""

    def __init__(self) -> None:
        self.frames: list[tuple[str, object]] = []

    async def __call__(self, event, data) -> None:
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
    state: ChapterState,
    ordinal: int = 1,
    title: str = "Chapter One",
    text: str = BODY,
) -> Chapter:
    """A chapter written straight through db/chapters.py in the given state.

    A body spec must not depend on the transition path to reach a state, and
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


async def _seed_entry(
    book_id: int,
    author_id: int,
    kind: CodexKind = CodexKind.character,
    *,
    name: str | None = "Halden",
    body: str = "the original body",
    archived: bool = False,
) -> CodexEntry:
    return await codex_entries.create(
        CodexEntry(
            book_id=book_id,
            kind=kind,
            name=name,
            body=body,
            archived=archived,
            author_id=author_id,
        )
    )


async def _seed_server() -> LlmServer:
    return await llm_servers.create(
        LlmServer(
            name="S",
            backend_type="openai",
            base_url="https://api.example.com/v1",
            api_key="sk-stored",
            enabled_models='["gpt-x"]',
            is_active=True,
        )
    )


async def _seed_chat(book_id: int, author_id: int, server_id: int) -> Chat:
    return await chats.create(
        Chat(
            book_id=book_id,
            author_id=author_id,
            title="A Chat",
            llm_server_id=server_id,
            model_name="gpt-x",
        )
    )


def _access(
    book_id: int,
    *,
    user_id: int = 2,
    role: AccessRole = AccessRole.owner,
    collaboration_mode: CollaborationMode = CollaborationMode.free,
) -> BookAccess:
    return BookAccess(
        book_id=book_id,
        user_id=user_id,
        role=role,
        book_state=BookState.active,
        visibility=Visibility.private,
        collaboration_mode=collaboration_mode,
    )


def _entry_subject(
    entry: CodexEntry, mode_key: str = "edit-character"
) -> ResolvedSubject:
    return ResolvedSubject(kind="codex-entry", entry=entry, mode_key=mode_key)


# ---------------------------------------------------------------------------
# DoD-1 — the operation discriminator, defaulted to replace
# ---------------------------------------------------------------------------


# DoD-1 (context.md -> D17): a canvas frame constructed WITHOUT an operation
# carries the replace operation -- the default is what keeps every existing
# emitter correct -- and one constructed with append or replace-selection carries
# exactly what it was given.
def test_frame_defaults_to_replace_and_keeps_a_given_op__DoD1():
    # The pre-015 construction shape: four fields, no `op`.
    defaulted = CanvasFrame(
        subject_kind="chapter", subject_id="12345", field="body", text=DRAFT
    )
    assert defaulted.op == "replace"

    for given in ("append", "replace_selection", "replace"):
        frame = CanvasFrame(
            subject_kind="chapter",
            subject_id="12345",
            field="body",
            text=DRAFT,
            op=given,
        )
        assert frame.op == given

    # The default survives serialization -- what an emitter meant reaches the
    # wire, rather than being dropped as "unset".
    assert defaulted.model_dump()["op"] == "replace"

    # A three-valued discriminator: exactly these three operations, no more.
    assert set(get_args(CanvasOp)) == {"replace", "append", "replace_selection"}

    # ...and nothing outside the three is accepted.
    with pytest.raises(ValidationError):
        CanvasFrame(
            subject_kind="chapter",
            subject_id="12345",
            field="body",
            text=DRAFT,
            op="prepend",
        )


# ---------------------------------------------------------------------------
# DoD-2 — the existing codex emission is unchanged apart from the default
# ---------------------------------------------------------------------------


# DoD-2 (context.md -> D17; 009.context.md -> the codex emission is a regression
# surface): the existing codex canvas emission still produces a frame identical
# to today's apart from the defaulted operation field -- same subject kind, same
# subject id, same field, same text -- with the operation reading as replace,
# which is what every emission before this step meant.
async def test_codex_emission_is_todays_frame_plus_a_defaulted_op__DoD2(db: DbConfig):
    user = await _seed_user()
    book = await _seed_book(user.id)
    entry = await _seed_entry(book.id, user.id)
    recorder = _Recorder()

    result = await codex_tools.write_codex_draft(
        ToolContext(
            book_id=book.id,
            access=_access(book.id),
            subject=_entry_subject(entry),
            emit_frame=recorder,
        ),
        field="body",
        text=DRAFT,
    )

    # Still exactly one frame, still named `canvas`.
    assert len(recorder.frames) == 1
    event, payload = recorder.frames[0]
    assert event == "canvas"
    assert isinstance(payload, CanvasFrame)

    # Field by field, the frame today's codex tool emitted.
    assert payload.subject_kind == "codex-entry"
    assert payload.subject_id == str(entry.id)
    assert payload.field == "body"
    assert payload.text == DRAFT
    # ...plus the one new field, at its default.
    assert payload.op == "replace"

    # The tool still answers the model with a non-empty confirmation string.
    assert isinstance(result, str)
    assert result.strip() != ""

    # A `name` write is likewise untouched.
    name_recorder = _Recorder()
    await codex_tools.write_codex_draft(
        ToolContext(
            book_id=book.id,
            access=_access(book.id),
            subject=_entry_subject(entry),
            emit_frame=name_recorder,
        ),
        field="name",
        text="Halden of the North Gate",
    )
    assert len(name_recorder.frames) == 1
    assert name_recorder.frames[0][1].field == "name"
    assert name_recorder.frames[0][1].text == "Halden of the North Gate"
    assert name_recorder.frames[0][1].op == "replace"


# DoD-2: the codex tools' refusal behaviour and refusal strings are unchanged --
# an archived entry is still refused with a non-empty string and NO frame, and a
# co-author's write in a proposal-mode book is still refused with a string naming
# FEAT-010.
async def test_codex_write_refusals_are_unchanged__DoD2(db: DbConfig):
    user = await _seed_user()
    book = await _seed_book(user.id)
    archived = await _seed_entry(book.id, user.id, name="Retired", archived=True)
    recorder = _Recorder()

    refused = await codex_tools.write_codex_draft(
        ToolContext(
            book_id=book.id,
            access=_access(book.id),
            subject=_entry_subject(archived),
            emit_frame=recorder,
        ),
        field="body",
        text=DRAFT,
    )
    assert isinstance(refused, str)
    assert refused.strip() != ""
    assert recorder.frames == []

    proposal_book = await _seed_book(
        user.id, title="Proposal", collaboration_mode=CollaborationMode.proposal
    )
    proposal_entry = await _seed_entry(proposal_book.id, user.id)
    proposal_recorder = _Recorder()

    proposal_refusal = await codex_tools.write_codex_draft(
        ToolContext(
            book_id=proposal_book.id,
            access=_access(
                proposal_book.id,
                role=AccessRole.co_author,
                collaboration_mode=CollaborationMode.proposal,
            ),
            subject=_entry_subject(proposal_entry),
            emit_frame=proposal_recorder,
        ),
        field="body",
        text=DRAFT,
    )
    assert isinstance(proposal_refusal, str)
    assert "FEAT-010" in proposal_refusal
    assert proposal_recorder.frames == []


# ---------------------------------------------------------------------------
# DoD-3 — CanvasField is NOT widened
# ---------------------------------------------------------------------------


# DoD-3 (context.md -> D17 / consequence 4): `CanvasField` still admits exactly
# "name" and "body" -- a chapter's body IS the "body" field, and no "text" member
# was added.
def test_canvas_field_admits_exactly_name_and_body__DoD3():
    assert set(get_args(CanvasField)) == {"name", "body"}

    for field in ("name", "body"):
        frame = CanvasFrame(
            subject_kind="chapter", subject_id="12345", field=field, text=DRAFT
        )
        assert frame.field == field

    with pytest.raises(ValidationError):
        CanvasFrame(
            subject_kind="chapter", subject_id="12345", field="text", text=DRAFT
        )


# ---------------------------------------------------------------------------
# DoD-4 — the selection on the wire, and into the per-turn tool context
# ---------------------------------------------------------------------------


# DoD-4 (context.md -> D5): a turn request carrying NO selection is valid, and one
# carrying selection text makes that text readable from the per-turn tool
# context. The selection is a fifth FLAT field -- text only, no offsets, no line
# numbers, no anchor.
async def test_selection_on_the_request_reaches_the_tool_context__DoD4(db: DbConfig):
    user = await _seed_user()
    book = await _seed_book(user.id)
    server = await _seed_server()
    chat = await _seed_chat(book.id, user.id, server.id)
    access = _access(book.id, user_id=user.id)

    # (a) no selection is a valid request, on the model and through the turn.
    without = TurnRequest(prompt="hello")
    assert without.selection_text is None
    plain = await chat_turn.prepare_turn(access, str(chat.id), without)
    assert plain.selection_text is None

    # (b) a selection-bearing request carries its text into the per-turn context.
    carrying = TurnRequest(prompt="rewrite this", selection_text=SELECTION)
    assert carrying.selection_text == SELECTION
    context = await chat_turn.prepare_turn(access, str(chat.id), carrying)
    assert context.selection_text == SELECTION

    # (c) ...and the tool context a bound tool reads exposes exactly that text,
    #     so a tool needs no re-derivation of anything.
    tool_context = ToolContext(
        book_id=book.id,
        access=access,
        subject=context.subject,
        selection_text=context.selection_text,
    )
    assert tool_context.selection_text == SELECTION
    # Absent by default -- a tool context built without one reads None.
    assert ToolContext(book_id=book.id).selection_text is None


# ---------------------------------------------------------------------------
# DoD-5 — the selection is never written anywhere
# ---------------------------------------------------------------------------


# DoD-5 (context.md -> D5 -- client-supplied turn context, never persisted): a
# turn carrying selection text leaves no row that holds it, and creates no
# chapter change and no revision.
async def test_selection_is_persisted_nowhere__DoD5(db: DbConfig):
    user = await _seed_user()
    book = await _seed_book(user.id)
    server = await _seed_server()
    chat = await _seed_chat(book.id, user.id, server.id)
    chapter = await _seed_chapter(book.id, state=ChapterState.open)
    access = _access(book.id, user_id=user.id)

    request = TurnRequest(prompt="rewrite this", selection_text=SELECTION)
    # The turn really did carry the selection -- otherwise "nothing holds it"
    # would be true of a turn that never had one.
    assert request.selection_text == SELECTION

    await chat_turn.prepare_turn(access, str(chat.id), request)

    # No chapter change and no revision were created.
    assert await chapter_changes.list_by_chapter(chapter.id) == []
    assert await chapter_text_revisions.list_by_chapter(chapter.id) == []

    # The chapter itself is untouched -- the selection never became a body.
    stored = await chapters.get_by_id(chapter.id)
    assert stored is not None
    assert stored.text == BODY
    assert stored.version == 1
    assert stored.state is ChapterState.open

    # And no stored message holds the selection either.
    messages = await chat_messages.list_by_chat_ordered(chat.id)
    assert all(SELECTION not in (message.content or "") for message in messages)


# ---------------------------------------------------------------------------
# DoD-6 — an `open` chapter resolves the write-chapter mode
# ---------------------------------------------------------------------------


# DoD-6 (009.context.md -- a branch that does not exist before this step):
# `determine_mode` resolves a chapter subject in state `open` to `write-chapter`.
async def test_open_chapter_resolves_write_chapter__DoD6(db: DbConfig):
    user = await _seed_user()
    book = await _seed_book(user.id)
    chapter = await _seed_chapter(book.id, state=ChapterState.open)

    resolved = await assistant_runtime.resolve_subject(
        _access(book.id, user_id=user.id),
        subject_kind="chapter",
        subject_id=str(chapter.id),
    )

    # The chapter row really was resolved onto the subject.
    assert resolved.kind == "chapter"
    assert resolved.chapter is not None
    assert resolved.chapter.id == chapter.id

    assert assistant_runtime.determine_mode(resolved) == "write-chapter"

    # The mapping is the chapter's STATE, not the resolution path: the same row
    # handed to determine_mode directly answers the same way.
    assert (
        assistant_runtime.determine_mode(
            ResolvedSubject(kind="chapter", chapter=chapter)
        )
        == "write-chapter"
    )


# ---------------------------------------------------------------------------
# DoD-7 — a `closing` chapter resolves the close-chapter mode
# ---------------------------------------------------------------------------


# DoD-7 (context.md -> "The close seam"): `determine_mode` resolves a chapter
# subject in state `closing` to `close-chapter`. The state is seeded directly --
# nothing in this feature writes `closing` (D8).
async def test_closing_chapter_resolves_close_chapter__DoD7(db: DbConfig):
    user = await _seed_user()
    book = await _seed_book(user.id)
    chapter = await _seed_chapter(book.id, state=ChapterState.closing)

    resolved = await assistant_runtime.resolve_subject(
        _access(book.id, user_id=user.id),
        subject_kind="chapter",
        subject_id=str(chapter.id),
    )

    assert resolved.kind == "chapter"
    assert resolved.chapter is not None
    assert resolved.chapter.id == chapter.id

    assert assistant_runtime.determine_mode(resolved) == "close-chapter"
    assert (
        assistant_runtime.determine_mode(
            ResolvedSubject(kind="chapter", chapter=chapter)
        )
        == "close-chapter"
    )


# ---------------------------------------------------------------------------
# DoD-8 — `planned` / `closed` have no mode, so the BASE allowlist applies
# ---------------------------------------------------------------------------


# DoD-8 (009.context.md -- FEAT-020's five modes name five activities, and
# neither of these is one of them): a chapter in `planned` or `closed` resolves to
# NO mode, and `allowed_tool_names` therefore returns the base allowlist --
# concretely, exactly `("web_search",)`: not an empty list and not the whole
# registry.
@pytest.mark.parametrize(
    "state",
    [ChapterState.planned, ChapterState.closed],
    ids=["planned", "closed"],
)
async def test_planned_and_closed_chapters_get_the_base_allowlist__DoD8(
    db: DbConfig, state
):
    user = await _seed_user()
    book = await _seed_book(user.id)
    chapter = await _seed_chapter(book.id, state=state)

    resolved = await assistant_runtime.resolve_subject(
        _access(book.id, user_id=user.id),
        subject_kind="chapter",
        subject_id=str(chapter.id),
    )

    # The row IS the subject -- this is "no mode", not "no chapter".
    assert resolved.chapter is not None
    assert resolved.chapter.id == chapter.id

    mode = assistant_runtime.determine_mode(resolved)
    assert mode is None

    names = await assistant_runtime.allowed_tool_names(mode)

    # The concrete value, not the concept.
    assert names == ("web_search",)
    assert names == BASE_TOOL_NAMES
    # Neither of the two wrong answers: not empty, and not the whole registry.
    assert names != ()
    registry_names = {tool.name for tool in tools_module.TOOL_REGISTRY}
    assert len(registry_names) > 1
    assert set(names) != registry_names


# ---------------------------------------------------------------------------
# DoD-9 — a chapter in ANOTHER book resolves to no subject
# ---------------------------------------------------------------------------


# DoD-9 (assistant-runtime.md's cross-book rule, applied to chapters): a
# subject_id naming a chapter in another book resolves to NO SUBJECT, and
# therefore to no mode -- refused by resolution, not by a later check. Two books
# exist, so "no subject" is provably the cross-book rule and not a missing row.
async def test_chapter_in_another_book_resolves_to_no_subject__DoD9(db: DbConfig):
    user = await _seed_user()
    book = await _seed_book(user.id)
    stranger = await _seed_user("stranger")
    other_book = await _seed_book(stranger.id, title="Their Book")
    foreign = await _seed_chapter(
        other_book.id,
        state=ChapterState.open,
        title="Their Chapter",
        text="SECRET_FOREIGN_BODY",
    )
    access = _access(book.id, user_id=user.id)

    resolved = await assistant_runtime.resolve_subject(
        access, subject_kind="chapter", subject_id=str(foreign.id)
    )

    # No cross-book content was loaded...
    assert resolved.chapter is None
    # ...and no subject at all -- not merely an absent mode.
    assert resolved.kind is None
    assert resolved.entry is None
    assert resolved.mode_key is None
    assert assistant_runtime.determine_mode(resolved) is None

    # The row exists and is perfectly resolvable from ITS OWN book, so the
    # refusal above is the cross-book rule and not a missing row.
    own = await assistant_runtime.resolve_subject(
        _access(other_book.id, user_id=stranger.id),
        subject_kind="chapter",
        subject_id=str(foreign.id),
    )
    assert own.chapter is not None
    assert own.chapter.id == foreign.id
    assert assistant_runtime.determine_mode(own) == "write-chapter"


# ---------------------------------------------------------------------------
# DoD-10 — codex resolution and codex mode determination are unchanged
# ---------------------------------------------------------------------------


# DoD-10 (regression over the restructured determine_mode): a codex entry of each
# kind still resolves to the mode it resolves to today.
@pytest.mark.parametrize(
    ("kind", "expected_mode"),
    [
        (CodexKind.character, "edit-character"),
        (CodexKind.location, "edit-location"),
        (CodexKind.fact, "edit-fact"),
    ],
    ids=["character", "location", "fact"],
)
async def test_codex_entry_still_resolves_its_edit_mode__DoD10(
    db: DbConfig, kind, expected_mode
):
    user = await _seed_user()
    book = await _seed_book(user.id)
    entry = await _seed_entry(book.id, user.id, kind, name="N")

    resolved = await assistant_runtime.resolve_subject(
        _access(book.id, user_id=user.id),
        subject_kind="codex-entry",
        subject_id=str(entry.id),
    )

    assert resolved.kind == "codex-entry"
    assert resolved.entry is not None
    assert resolved.entry.id == entry.id
    # The chapter member stays empty for a codex subject.
    assert resolved.chapter is None
    assert resolved.mode_key == expected_mode
    assert assistant_runtime.determine_mode(resolved) == expected_mode

    # The pure mapping is unchanged too: an entry handed over directly still maps
    # by its kind, with no chapter row anywhere in sight.
    assert (
        assistant_runtime.determine_mode(
            ResolvedSubject(kind="codex-entry", entry=entry)
        )
        == expected_mode
    )


# ---------------------------------------------------------------------------
# DoD-11 — a turn with no subject at all is unaffected
# ---------------------------------------------------------------------------


# DoD-11 (backward compatibility): a turn with no subject at all is unaffected by
# every change in this step -- no subject, no chapter, no mode, the base
# allowlist, and a request whose new field is simply absent.
async def test_subjectless_turn_is_unaffected__DoD11(db: DbConfig):
    user = await _seed_user()
    book = await _seed_book(user.id)
    server = await _seed_server()
    chat = await _seed_chat(book.id, user.id, server.id)
    access = _access(book.id, user_id=user.id)

    # The empty body is still a complete request, and the new field is absent.
    empty = TurnRequest.model_validate({})
    assert empty.prompt is None
    assert empty.subject_kind is None
    assert empty.subject_id is None
    assert empty.codex_kind is None
    assert empty.selection_text is None

    resolved = await assistant_runtime.resolve_subject(access)
    assert resolved.kind is None
    assert resolved.entry is None
    assert resolved.chapter is None
    assert resolved.mode_key is None
    assert assistant_runtime.determine_mode(resolved) is None

    # The no-subject sentinel is unchanged, chapter member included.
    assert NO_SUBJECT.chapter is None
    assert assistant_runtime.determine_mode(NO_SUBJECT) is None

    # No mode still means exactly the base allowlist.
    assert await assistant_runtime.allowed_tool_names(None) == BASE_TOOL_NAMES

    # And a subject-less turn prepares exactly as before, carrying no selection.
    context = await chat_turn.prepare_turn(access, str(chat.id))
    assert context.subject.kind is None
    assert context.subject.chapter is None
    assert context.subject.mode_key is None
    assert context.selection_text is None


# ---------------------------------------------------------------------------
# DoD-12 — the two chapter mode keys already have rows (a seeding ASSERTION)
# ---------------------------------------------------------------------------


# DoD-12 (context.md -> "Mode seeding"): a freshly initialised database has an
# AssistantMode row keyed `write-chapter` and one keyed `close-chapter` -- the two
# keys the chapter branch returns. NOTHING in this step (or this file) seeds them:
# the assertion exists because a mode key with no row fails silently -- an empty
# mode prompt, an empty tool allowlist, and no error anywhere.
async def test_fresh_instance_carries_both_chapter_mode_rows__DoD12(db: DbConfig):
    # Before the instance is initialised there are no mode rows at all, so the
    # assertion below cannot be satisfied by a leftover row.
    assert await assistant_modes.list_all() == []
    assert is_db_ready() is False

    await setup.create_database("root", "password123", "password123")

    write_chapter = await assistant_modes.get_by_id("write-chapter")
    close_chapter = await assistant_modes.get_by_id("close-chapter")

    assert write_chapter is not None
    assert write_chapter.key == "write-chapter"
    assert close_chapter is not None
    assert close_chapter.key == "close-chapter"


# DoD-12: the two keys asserted above are exactly the two the chapter branch can
# return -- so the seeding assertion guards the keys actually in use, rather than
# two strings that merely look right.
def test_chapter_branch_returns_only_the_seeded_keys__DoD12():
    assert set(assistant_runtime._CHAPTER_STATE_MODES.values()) == {
        "write-chapter",
        "close-chapter",
    }
    assert (
        assistant_runtime._CHAPTER_STATE_MODES[ChapterState.open.value]
        == "write-chapter"
    )
    assert (
        assistant_runtime._CHAPTER_STATE_MODES[ChapterState.closing.value]
        == "close-chapter"
    )
    # `planned` and `closed` are absent by design: a missing key is no mode.
    assert ChapterState.planned.value not in assistant_runtime._CHAPTER_STATE_MODES
    assert ChapterState.closed.value not in assistant_runtime._CHAPTER_STATE_MODES
