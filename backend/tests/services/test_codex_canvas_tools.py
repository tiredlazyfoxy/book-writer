"""Tests for the shared-canvas write tool (feature 013, step 010).

Bound to the frozen skeleton (``status.md`` -> ``## Skeleton`` -> Step 010).

In ``app.models.schemas.chats``::

    CanvasField = Literal["name", "body"]
    class CanvasFrame(BaseModel) { subject_kind: SubjectKind;
                                   subject_id: str | None;
                                   field: CanvasField;
                                   text: str }

in ``app.services.codex_tools``::

    class WriteCodexDraftArgs(BaseModel)  { field: CanvasField; text: str }
    async def write_codex_draft(context, field: CanvasField, text: str) -> str
    def bind_write_codex_draft(context: ToolContext) -> Callable[..., object]

in ``app.services.tools``::

    FrameEmitter = Callable[[str, BaseModel], Awaitable[None]]
    @dataclass(frozen=True) class ToolContext {
        book_id: int
        access: authz.BookAccess | None = None
        subject: ResolvedSubject | None = None
        emit_frame: FrameEmitter | None = None }
    TOOL_REGISTRY: list[ToolDef]   # web_search, codex_search, codex_read_entry,
                                   # write_codex_draft

and in ``app.services.chat_turn``::

    @dataclass(frozen=True) class TurnContext { chat, server, resolved_key,
        subject, access: authz.BookAccess | None = None }

Expected values come from the SPEC ONLY -- ``010.shared-canvas-write.md`` ->
Interface intent + Definition of done (DoD-1..DoD-12), ``010.context.md``, and
``context.md`` -> "The shared-canvas write design" + decision 3 -- never from
implementation internals.

Test approach: the tool is exercised directly with a RECORDING emitter (the
``(event_name, payload)`` pair the frozen ``FrameEmitter`` alias defines), so
"exactly one frame whose event is ``canvas``" is observable without a live
stream; DoD-2 / DoD-3 live end to end in
``backend/tests/routes/test_chat_turn_canvas.py``. Rows are seeded through the
``db/`` layer against the real temp-SQLite ``db`` fixture. No network anywhere;
``asyncio_mode = "auto"``.

The load-bearing negative of the whole step -- "there is no code path from a
chat to the ``codex_entries`` table at all" -- is asserted in the route file
(DoD-3), because it is a property of a whole turn, not of one call.
"""

import inspect

from app.db import assistant_modes, books, chats, codex_entries, llm_servers, mode_tools, users
from app.db.engine import DbConfig
from app.models.assistant_mode import AssistantMode
from app.models.book import Book, BookState, CollaborationMode, Visibility
from app.models.chat import Chat
from app.models.codex_entry import CodexEntry, CodexKind
from app.models.llm_server import LlmServer
from app.models.mode_tool import ModeTool
from app.models.schemas.chats import CanvasFrame
from app.models.user import User, UserRole
from app.services import chat_turn, codex_tools
from app.services import tools as tools_module
from app.services.assistant_runtime import BASE_TOOL_NAMES, NO_SUBJECT, ResolvedSubject
from app.services.authz import AccessRole, BookAccess
from app.services.chat_turn import TurnContext
from app.services.codex_tools import WriteCodexDraftArgs
from app.services.tools import ToolContext

DRAFT = "Halden keeps the north gate through the long winter."
NAME_DRAFT = "Halden of the North Gate"


# ---------------------------------------------------------------------------
# The recording emitter -- the frozen FrameEmitter shape: (event, payload).
# ---------------------------------------------------------------------------


class _Recorder:
    """Records every ``await emit_frame(event, payload)`` call.

    ``exc`` makes the emitter FAIL, standing in for the queue failure DoD-11
    names (the emitter closed over by ``chat_turn`` is the put-onto-the-queue
    path itself, so a queue failure surfaces here).
    """

    def __init__(self, *, exc: Exception | None = None) -> None:
        self.frames: list[tuple[str, object]] = []
        self._exc = exc

    async def __call__(self, event, data) -> None:
        if self._exc is not None:
            raise self._exc
        self.frames.append((event, data))


# ---------------------------------------------------------------------------
# Seeding helpers (rows built through the db layer).
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


async def _seed_entry(
    book_id: int,
    author_id: int,
    kind: CodexKind = CodexKind.character,
    *,
    name: str | None = "Halden",
    body: str = "entry body",
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


async def _seed_mode(key: str, system_prompt: str | None = "MODE_RULES") -> AssistantMode:
    return await assistant_modes.create(
        AssistantMode(key=key, system_prompt=system_prompt)
    )


async def _seed_mode_tool(mode_key: str, tool_name: str) -> ModeTool:
    return await mode_tools.create(ModeTool(mode_key=mode_key, tool_name=tool_name))


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


def _ctx(
    book_id: int,
    *,
    subject=None,
    emitter=None,
    role: AccessRole = AccessRole.owner,
    collaboration_mode: CollaborationMode = CollaborationMode.free,
    with_access: bool = True,
) -> ToolContext:
    return ToolContext(
        book_id=book_id,
        access=(
            _access(book_id, role=role, collaboration_mode=collaboration_mode)
            if with_access
            else None
        ),
        subject=subject,
        emit_frame=emitter,
    )


def _entry_subject(entry: CodexEntry, mode_key: str = "edit-character") -> ResolvedSubject:
    return ResolvedSubject(kind="codex-entry", entry=entry, mode_key=mode_key)


def _assert_refusal(result, recorder: _Recorder) -> None:
    """A refusal: a non-empty STRING back, and NOT ONE frame emitted."""
    assert isinstance(result, str)
    assert result.strip() != ""
    assert recorder.frames == []


async def _run(context: TurnContext, prompt: str | None = "ask"):
    return [frame async for frame in chat_turn.run_turn(context, prompt)]


# ---------------------------------------------------------------------------
# The fake LLM client -- feature 011's substituted construction seam.
# ---------------------------------------------------------------------------


class _FakeClient:
    """A stand-in for ``llm.LLMClient`` used as an async context manager."""

    def __init__(self, *, chunks=None, return_value=""):
        self._chunks = list(chunks or [])
        self._return_value = return_value
        self.call: dict | None = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def chat_with_tools(
        self,
        messages,
        *,
        tools_definitions=None,
        tools=None,
        system=None,
        max_loops=None,
        options=None,
        stream=False,
        on_delta=None,
        response_format=None,
        **kwargs,
    ):
        self.call = {
            "messages": messages,
            "tools_definitions": tools_definitions,
            "tools": tools,
            "system": system,
        }
        if on_delta is not None:
            for chunk in self._chunks:
                result = on_delta(chunk)
                if inspect.isawaitable(result):
                    await result
        return self._return_value


def _install_client(monkeypatch, fake: _FakeClient) -> _FakeClient:
    def factory(server, resolved_key, model):
        return fake

    monkeypatch.setattr("app.services.llm_servers.create_model_client", factory)
    monkeypatch.setattr(
        "app.services.chat_turn.create_model_client", factory, raising=False
    )
    return fake


# ---------------------------------------------------------------------------
# DoD-1 — exactly one `canvas` frame carrying kind / id / field / text
# ---------------------------------------------------------------------------


# DoD-1 (US-086.AC-1, US-087.AC-1): invoking the tool with an EDITABLE codex-entry
# subject pushes EXACTLY ONE frame, whose event name is `canvas` and whose payload
# carries the subject kind, the subject id, the field written and the text.
async def test_editable_entry_emits_exactly_one_canvas_frame__DoD1_US086_AC1(
    db: DbConfig,
):
    user = await _seed_user()
    book = await _seed_book(user.id)
    entry = await _seed_entry(book.id, user.id)
    recorder = _Recorder()

    await codex_tools.write_codex_draft(
        _ctx(book.id, subject=_entry_subject(entry), emitter=recorder),
        field="body",
        text=DRAFT,
    )

    # Exactly one frame -- not zero, not two.
    assert len(recorder.frames) == 1
    event, payload = recorder.frames[0]
    assert event == "canvas"

    assert isinstance(payload, CanvasFrame)
    assert payload.subject_kind == "codex-entry"
    assert payload.subject_id == str(entry.id)
    assert payload.field == "body"
    assert payload.text == DRAFT

    # A second, independent write of the `name` field carries that field's own
    # text -- the payload reports what was written, not a fixed value.
    name_recorder = _Recorder()
    await codex_tools.write_codex_draft(
        _ctx(book.id, subject=_entry_subject(entry), emitter=name_recorder),
        field="name",
        text=NAME_DRAFT,
    )
    assert len(name_recorder.frames) == 1
    assert name_recorder.frames[0][0] == "canvas"
    assert name_recorder.frames[0][1].field == "name"
    assert name_recorder.frames[0][1].text == NAME_DRAFT


# ---------------------------------------------------------------------------
# DoD-4 — a non-empty confirmation string keeps the tool loop going
# ---------------------------------------------------------------------------


# DoD-4 (the `llm` loop contract): on success the tool returns a NON-EMPTY
# confirmation string to the model, so `chat_with_tools` keeps looping rather
# than terminating -- and that confirmation is distinguishable from a refusal.
async def test_success_returns_non_empty_confirmation_string__DoD4(db: DbConfig):
    user = await _seed_user()
    book = await _seed_book(user.id)
    entry = await _seed_entry(book.id, user.id)
    archived = await _seed_entry(book.id, user.id, archived=True, name="Retired")

    ok = await codex_tools.write_codex_draft(
        _ctx(book.id, subject=_entry_subject(entry), emitter=_Recorder()),
        field="body",
        text=DRAFT,
    )

    assert isinstance(ok, str)
    assert ok.strip() != ""

    # A confirmation is not a refusal: the refused path answers differently.
    refused = await codex_tools.write_codex_draft(
        _ctx(book.id, subject=_entry_subject(archived), emitter=_Recorder()),
        field="body",
        text=DRAFT,
    )
    assert ok != refused


# ---------------------------------------------------------------------------
# DoD-5 — an archived entry is read-only for the assistant too
# ---------------------------------------------------------------------------


# DoD-5 (frontend-workspace.md -- a read-only subject refuses the author and the
# assistant alike): with an ARCHIVED entry as the subject the write is refused, a
# string is returned and NO canvas frame is emitted.
async def test_archived_entry_refused_with_no_frame__DoD5(db: DbConfig):
    user = await _seed_user()
    book = await _seed_book(user.id)
    archived = await _seed_entry(
        book.id, user.id, name="Retired Character", body="old body", archived=True
    )
    recorder = _Recorder()

    result = await codex_tools.write_codex_draft(
        _ctx(book.id, subject=_entry_subject(archived), emitter=recorder),
        field="body",
        text=DRAFT,
    )

    _assert_refusal(result, recorder)

    # A live sibling in the same book IS written -- the refusal is the archived
    # rule, not a blanket refusal.
    live = await _seed_entry(book.id, user.id, name="Live", body="body")
    live_recorder = _Recorder()
    await codex_tools.write_codex_draft(
        _ctx(book.id, subject=_entry_subject(live), emitter=live_recorder),
        field="body",
        text=DRAFT,
    )
    assert len(live_recorder.frames) == 1


# ---------------------------------------------------------------------------
# DoD-6 — a non-codex-entry subject, or no subject at all, is refused
# ---------------------------------------------------------------------------


# DoD-6 (frontend-workspace.md -> content-pane editability table): a book-state, a
# list, a chapter or an ABSENT subject each refuses the write with a string and
# emits no frame.
async def test_non_codex_entry_and_absent_subjects_refused__DoD6(db: DbConfig):
    user = await _seed_user()
    book = await _seed_book(user.id)

    non_entry_subjects = [
        # book state
        ResolvedSubject(kind="book-state", mode_key=None),
        # the list views
        ResolvedSubject(kind="chapters", mode_key=None),
        ResolvedSubject(kind="characters", mode_key=None),
        ResolvedSubject(kind="locations", mode_key=None),
        ResolvedSubject(kind="facts", mode_key=None),
        ResolvedSubject(kind="variants", mode_key=None),
        ResolvedSubject(kind="chapter-variants", mode_key=None),
        ResolvedSubject(kind="chats", mode_key=None),
        # a chapter
        ResolvedSubject(kind="chapter", mode_key="write-chapter"),
        # no subject at all -- both spellings of "absent"
        NO_SUBJECT,
        None,
    ]

    for subject in non_entry_subjects:
        for field in ("name", "body"):
            recorder = _Recorder()
            result = await codex_tools.write_codex_draft(
                _ctx(book.id, subject=subject, emitter=recorder),
                field=field,
                text=DRAFT,
            )
            _assert_refusal(result, recorder)


# ---------------------------------------------------------------------------
# DoD-7 / DoD-8 — the proposal-mode nuance, applied server-side (decision 3)
# ---------------------------------------------------------------------------


# DoD-7 (context.md decision 3; US-079.AC-2 knowingly unmet): a CO-AUTHOR in a
# PROPOSAL-mode book is refused, and the returned string names FEAT-010 as the
# unbuilt mechanism. No frame is emitted.
async def test_co_author_in_proposal_mode_refused_naming_feat010__DoD7_US079_AC2(
    db: DbConfig,
):
    user = await _seed_user()
    book = await _seed_book(user.id, collaboration_mode=CollaborationMode.proposal)
    entry = await _seed_entry(book.id, user.id)
    recorder = _Recorder()

    result = await codex_tools.write_codex_draft(
        _ctx(
            book.id,
            subject=_entry_subject(entry),
            emitter=recorder,
            role=AccessRole.co_author,
            collaboration_mode=CollaborationMode.proposal,
        ),
        field="body",
        text=DRAFT,
    )

    _assert_refusal(result, recorder)
    # The reason names the unbuilt mechanism by its product id.
    assert "FEAT-010" in result

    # The same co-author in a FREE-mode book is not refused -- the rule is the
    # collaboration mode, not the role alone.
    free_book = await _seed_book(user.id, title="Free")
    free_entry = await _seed_entry(free_book.id, user.id)
    free_recorder = _Recorder()
    await codex_tools.write_codex_draft(
        _ctx(
            free_book.id,
            subject=_entry_subject(free_entry),
            emitter=free_recorder,
            role=AccessRole.co_author,
            collaboration_mode=CollaborationMode.free,
        ),
        field="body",
        text=DRAFT,
    )
    assert len(free_recorder.frames) == 1


# DoD-8 (context.md decision 3): the OWNER of a proposal-mode book is NOT refused
# -- the draft is emitted exactly as in a free-mode book.
async def test_owner_in_proposal_mode_is_not_refused__DoD8(db: DbConfig):
    user = await _seed_user()
    book = await _seed_book(user.id, collaboration_mode=CollaborationMode.proposal)
    entry = await _seed_entry(book.id, user.id)
    recorder = _Recorder()

    result = await codex_tools.write_codex_draft(
        _ctx(
            book.id,
            subject=_entry_subject(entry),
            emitter=recorder,
            role=AccessRole.owner,
            collaboration_mode=CollaborationMode.proposal,
        ),
        field="body",
        text=DRAFT,
    )

    assert isinstance(result, str)
    assert result.strip() != ""
    assert len(recorder.frames) == 1
    event, payload = recorder.frames[0]
    assert event == "canvas"
    assert payload.subject_id == str(entry.id)
    assert payload.text == DRAFT
    assert "FEAT-010" not in result


# ---------------------------------------------------------------------------
# DoD-9 — a blank entry has no row yet, so the frame carries a NULL id
# ---------------------------------------------------------------------------


# DoD-9 (UC-076 -- a blank entry has no row yet): with a BLANK entry as the
# subject (kind "codex-entry", no row) the write is ALLOWED and the frame carries
# a NULL subject id.
async def test_blank_entry_allowed_with_null_subject_id__DoD9_UC076(db: DbConfig):
    user = await _seed_user()
    book = await _seed_book(user.id)

    for mode_key in ("edit-character", "edit-location"):
        recorder = _Recorder()
        blank = ResolvedSubject(kind="codex-entry", entry=None, mode_key=mode_key)

        result = await codex_tools.write_codex_draft(
            _ctx(book.id, subject=blank, emitter=recorder),
            field="body",
            text=DRAFT,
        )

        assert isinstance(result, str)
        assert result.strip() != ""
        assert len(recorder.frames) == 1
        event, payload = recorder.frames[0]
        assert event == "canvas"
        assert payload.subject_kind == "codex-entry"
        # No row yet -- the id is null, never an empty string or a placeholder.
        assert payload.subject_id is None
        assert payload.field == "body"
        assert payload.text == DRAFT


# ---------------------------------------------------------------------------
# DoD-10 — a fact has no name (US-078.AC-2 symmetry)
# ---------------------------------------------------------------------------


# DoD-10 (US-078.AC-2 symmetry): writing a `name` to a FACT subject is refused;
# writing a `body` to the same subject is allowed. Both halves asserted, for an
# existing fact row and for a blank fact (whose kind rides on the turn's mode).
async def test_fact_refuses_name_but_allows_body__DoD10_US078_AC2(db: DbConfig):
    user = await _seed_user()
    book = await _seed_book(user.id)
    fact = await _seed_entry(book.id, user.id, CodexKind.fact, name=None, body="a fact")

    fact_subjects = [
        _entry_subject(fact, mode_key="edit-fact"),
        ResolvedSubject(kind="codex-entry", entry=None, mode_key="edit-fact"),
    ]

    for subject in fact_subjects:
        # (a) a name is refused -- and nothing is emitted.
        name_recorder = _Recorder()
        refused = await codex_tools.write_codex_draft(
            _ctx(book.id, subject=subject, emitter=name_recorder),
            field="name",
            text=NAME_DRAFT,
        )
        _assert_refusal(refused, name_recorder)

        # (b) a body to the very same subject IS allowed.
        body_recorder = _Recorder()
        allowed = await codex_tools.write_codex_draft(
            _ctx(book.id, subject=subject, emitter=body_recorder),
            field="body",
            text=DRAFT,
        )
        assert isinstance(allowed, str)
        assert allowed.strip() != ""
        assert len(body_recorder.frames) == 1
        assert body_recorder.frames[0][0] == "canvas"
        assert body_recorder.frames[0][1].field == "body"

    # The refusal is the FACT rule: a character accepts a name.
    character = await _seed_entry(book.id, user.id, CodexKind.character)
    character_recorder = _Recorder()
    await codex_tools.write_codex_draft(
        _ctx(book.id, subject=_entry_subject(character), emitter=character_recorder),
        field="name",
        text=NAME_DRAFT,
    )
    assert len(character_recorder.frames) == 1
    assert character_recorder.frames[0][1].field == "name"


# ---------------------------------------------------------------------------
# DoD-11 — the tool never raises, on any path
# ---------------------------------------------------------------------------


# DoD-11 (the `web_search` contract -- a raising tool aborts the whole loop): the
# tool NEVER raises. A failing emitter (the queue failure), a MISSING emitter, a
# missing access context and every refusal path each come back as a string.
async def test_never_raises_including_queue_failure__DoD11(db: DbConfig):
    user = await _seed_user()
    book = await _seed_book(user.id)
    entry = await _seed_entry(book.id, user.id)
    archived = await _seed_entry(book.id, user.id, name="Retired", archived=True)
    fact = await _seed_entry(book.id, user.id, CodexKind.fact, name=None)
    subject = _entry_subject(entry)

    # (a) the queue fails while the frame is being put on it.
    failing = _Recorder(exc=RuntimeError("queue is closed"))
    queue_failure = await codex_tools.write_codex_draft(
        _ctx(book.id, subject=subject, emitter=failing),
        field="body",
        text=DRAFT,
    )
    assert isinstance(queue_failure, str)
    assert queue_failure.strip() != ""

    # (b) there is no emitter at all.
    no_emitter = await codex_tools.write_codex_draft(
        _ctx(book.id, subject=subject, emitter=None),
        field="body",
        text=DRAFT,
    )
    assert isinstance(no_emitter, str)
    assert no_emitter.strip() != ""

    # (c) every other path -- no access context, and each refusal -- returns a
    #     string too. Nothing here may raise.
    other_calls = [
        _ctx(book.id, subject=subject, emitter=_Recorder(), with_access=False),
        _ctx(book.id, subject=_entry_subject(archived), emitter=_Recorder()),
        _ctx(book.id, subject=None, emitter=_Recorder()),
        _ctx(book.id, subject=NO_SUBJECT, emitter=_Recorder()),
        _ctx(book.id, subject=ResolvedSubject(kind="book-state"), emitter=_Recorder()),
        _ctx(
            book.id,
            subject=_entry_subject(entry),
            emitter=_Recorder(),
            role=AccessRole.co_author,
            collaboration_mode=CollaborationMode.proposal,
        ),
    ]
    for context in other_calls:
        for field in ("name", "body"):
            result = await codex_tools.write_codex_draft(
                context, field=field, text=DRAFT
            )
            assert isinstance(result, str)
            assert result.strip() != ""

    # ...including the fact/name refusal.
    fact_result = await codex_tools.write_codex_draft(
        _ctx(book.id, subject=_entry_subject(fact, "edit-fact"), emitter=_Recorder()),
        field="name",
        text=NAME_DRAFT,
    )
    assert isinstance(fact_result, str)
    assert fact_result.strip() != ""


# ---------------------------------------------------------------------------
# DoD-12 — reachable only when the running mode SELECTS the tool
# ---------------------------------------------------------------------------


# DoD-12 (US-111.AC-2): the tool is reachable only when the running mode selects
# it. A mode whose `mode_tool` rows name `write_codex_draft` offers it to the
# model -- bound to the turn's own subject; a sibling mode without that row builds
# NO `write_codex_draft` definition and no callable, and neither does a no-mode
# turn.
async def test_mode_gating_decides_whether_write_tool_is_built__DoD12_US111_AC2(
    db: DbConfig, monkeypatch
):
    user = await _seed_user()
    book = await _seed_book(user.id)
    server = await _seed_server()
    chat = await _seed_chat(book.id, user.id, server.id)
    entry = await _seed_entry(book.id, user.id)

    await _seed_mode("edit-character")
    await _seed_mode_tool("edit-character", "write_codex_draft")
    # A sibling mode selects something else entirely.
    await _seed_mode("edit-fact")
    await _seed_mode_tool("edit-fact", "web_search")

    fake = _install_client(monkeypatch, _FakeClient(chunks=["ok"]))
    access = _access(book.id, user_id=user.id)

    selecting = TurnContext(
        chat=chat,
        server=server,
        resolved_key="resolved-secret",
        subject=_entry_subject(entry),
        access=access,
    )
    frames = await _run(selecting)

    assert frames[-1].event == "done"
    assert "write_codex_draft" in fake.call["tools"]
    assert "write_codex_draft" in {
        d["function"]["name"] for d in fake.call["tools_definitions"]
    }
    # Bound so the `llm` client can dispatch it: exactly the schema's fields are
    # free parameters.
    bound = fake.call["tools"]["write_codex_draft"]
    assert set(inspect.signature(bound).parameters) == set(
        WriteCodexDraftArgs.model_fields
    )

    # The mode that does not select it builds neither the definition nor the
    # callable (and no stray delegation / codex key rides along).
    not_selecting = TurnContext(
        chat=chat,
        server=server,
        resolved_key="resolved-secret",
        subject=ResolvedSubject(kind="codex-entry", entry=entry, mode_key="edit-fact"),
        access=access,
    )
    frames = await _run(not_selecting)

    assert frames[-1].event == "done"
    assert "write_codex_draft" not in fake.call["tools"]
    assert "write_codex_draft" not in str(fake.call["tools_definitions"])
    assert not [k for k in fake.call["tools"] if k.startswith("ask_")]

    # A no-mode turn (BASE_TOOL_NAMES) does not offer it either.
    no_mode = TurnContext(
        chat=chat,
        server=server,
        resolved_key="resolved-secret",
        subject=ResolvedSubject(kind="chats", mode_key=None),
        access=access,
    )
    frames = await _run(no_mode)

    assert frames[-1].event == "done"
    assert set(fake.call["tools"].keys()) == set(BASE_TOOL_NAMES)
    assert "write_codex_draft" not in fake.call["tools"]

    # The tool is a registry entry like any other, so gating has something to
    # gate (the catalogue itself is pinned in tests/services/test_tools.py).
    assert "write_codex_draft" in {t.name for t in tools_module.TOOL_REGISTRY}
