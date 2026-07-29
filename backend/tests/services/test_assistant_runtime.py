"""Tests for the FEAT-020 mode runtime: subject resolution, mode determination,
the mode prompt layer and real ``mode_tool`` gating (feature 013, step 007).

Bound to the frozen skeleton (``status.md`` -> ``## Skeleton`` -> Step 007), in
``app.services.assistant_runtime``::

    BASE_TOOL_NAMES: tuple[str, ...] = ("web_search",)
    @dataclass(frozen=True) class ResolvedSubject {
        kind: SubjectKind | None = None
        entry: CodexEntry | None = None
        mode_key: str | None = None }
    NO_SUBJECT: ResolvedSubject
    async def resolve_subject(access, subject_kind=None, subject_id=None,
                              codex_kind=None) -> ResolvedSubject
    def determine_mode(subject: ResolvedSubject) -> str | None
    async def mode_system_prompt(mode_key: str | None) -> str | None
    async def allowed_tool_names(mode_key: str | None) -> tuple[str, ...]

in ``app.models.schemas.chats``::

    SubjectKind = Literal[...]
    class TurnRequest { prompt, subject_kind, subject_id, codex_kind }

and in ``app.services.chat_turn``::

    @dataclass(frozen=True) class TurnContext { chat, server, resolved_key,
        subject: ResolvedSubject = NO_SUBJECT }
    async def prepare_turn(access, chat_id: str, request: TurnRequest | None = None)
        -> TurnContext
    async def run_turn(context, prompt) -> AsyncGenerator[TurnFrame, None]

No network / no real LLM: the client-construction seam (``create_model_client``)
is monkeypatched with a fake async-context-manager client that records the
``chat_with_tools`` kwargs, exactly as feature 011's turn tests do. Rows are
seeded through the ``db/`` layer against the real temp-SQLite ``db`` fixture;
``asyncio_mode = "auto"``.

Expected values come from the SPEC ONLY -- the step's DoD-1..DoD-13,
``007.mode-runtime-gating.md`` -> Interface intent, ``context.md`` decision 6
(a null mode gets ``BASE_TOOL_NAMES``, not the whole registry) and
``assistant-config.md``'s mode table -- never from implementation internals.

Superseded-guard update (feature 021, step 004 -- the composition switch): the
composer's third layer is renamed ``book`` -> ``author`` (label ``BOOK`` ->
``AUTHOR``) and the turn now composes the prompt of *the chat's own author*,
read from ``BookAuthorPrompt``, instead of ``Book.system_prompt``
(``021/context.md`` decision 3; ``021/004`` DoD-1/DoD-4/DoD-6). Every assertion
below is preserved verbatim in strength; only the keyword and the row the
third-layer sentinel is seeded into moved. Nothing about mode resolution, the
mode layer or tool gating -- this module's own subject -- changed.
"""

import inspect
import logging

import pytest
from pydantic import BaseModel

from app.db import (
    assistant_modes,
    book_author_prompts,
    books,
    chat_messages,
    chats,
    codex_entries,
    llm_servers,
    mode_tools,
    users,
)
from app.db.engine import DbConfig
from app.models.assistant_mode import AssistantMode
from app.models.book import Book, BookState, CollaborationMode, Visibility
from app.models.book_author_prompt import BookAuthorPrompt
from app.models.chat import Chat
from app.models.codex_entry import CodexEntry, CodexKind
from app.models.llm_server import LlmServer
from app.models.mode_tool import ModeTool
from app.models.schemas.chats import TurnRequest
from app.models.user import User, UserRole
from app.services import assistant_runtime, chat_turn
from app.services import tools as tools_module
from app.services.assistant_runtime import (
    BASE_TOOL_NAMES,
    NO_SUBJECT,
    ResolvedSubject,
)
from app.services.authz import AccessRole, BookAccess
from app.services.chat_turn import TurnContext
from app.services.prompt_composition import BASE_SYSTEM_PROMPT, compose_system_prompt
from app.services.tools import ToolDef


# ---------------------------------------------------------------------------
# The fake LLM client -- the substituted construction seam (011's shape).
# ---------------------------------------------------------------------------


class _FakeClient:
    """A stand-in for ``llm.LLMClient`` used as an async context manager.

    ``chat_with_tools`` records the call kwargs (``system`` /
    ``tools_definitions`` / ``tools`` are what this step asserts on), drives
    ``on_delta`` with the scripted chunks, then returns.
    """

    def __init__(self, *, chunks=None, exc=None, return_value=""):
        self._chunks = list(chunks or [])
        self._exc = exc
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
            "options": options,
        }
        if on_delta is not None:
            for chunk in self._chunks:
                result = on_delta(chunk)
                if inspect.isawaitable(result):
                    await result
        if self._exc is not None:
            raise self._exc
        return self._return_value


def _install_client(monkeypatch, fake: _FakeClient) -> _FakeClient:
    """Monkeypatch ``create_model_client`` (the frozen 011 seam) to yield ``fake``."""

    def factory(server, resolved_key, model):
        return fake

    monkeypatch.setattr("app.services.llm_servers.create_model_client", factory)
    monkeypatch.setattr(
        "app.services.chat_turn.create_model_client", factory, raising=False
    )
    return fake


# ---------------------------------------------------------------------------
# An extra registry tool, so "a registry tool the mode did not select" exists.
# ``TOOL_REGISTRY`` holds only ``web_search`` today (007.context.md); DoD-9 needs
# a second catalogue entry to be a real exclusion, so the tests that need one
# monkeypatch the registry the way step 009 will widen it.
# ---------------------------------------------------------------------------


class _NoteArgs(BaseModel):
    text: str


def _note_tool(text: str) -> str:
    return f"noted: {text}"


_EXTRA_TOOL = ToolDef(
    name="note_tool",
    description="Record a short note for the author.",
    args_schema=_NoteArgs,
    callable=_note_tool,
)


def _widen_registry(monkeypatch) -> None:
    monkeypatch.setattr(
        tools_module,
        "TOOL_REGISTRY",
        [*tools_module.TOOL_REGISTRY, _EXTRA_TOOL],
    )


# ---------------------------------------------------------------------------
# Seeding helpers (rows built through the db layer).
# ---------------------------------------------------------------------------


async def _seed_user(username: str = "author") -> User:
    return await users.create(User(username=username, role=UserRole.author))


async def _seed_book(owner_id: int, *, system_prompt: str = "") -> Book:
    return await books.create(
        Book(
            title="A Book",
            description="d",
            owner_id=owner_id,
            collaboration_mode=CollaborationMode.free,
            visibility=Visibility.private,
            state=BookState.active,
            system_prompt=system_prompt,
            active_notes="",
        )
    )


async def _seed_entry(
    book_id: int,
    author_id: int,
    kind: CodexKind,
    *,
    name: str | None = None,
    body: str = "entry body",
) -> CodexEntry:
    return await codex_entries.create(
        CodexEntry(
            book_id=book_id,
            kind=kind,
            name=name,
            body=body,
            archived=False,
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


async def _seed_mode(key: str, system_prompt: str | None = None) -> AssistantMode:
    return await assistant_modes.create(
        AssistantMode(key=key, system_prompt=system_prompt)
    )


async def _seed_mode_tool(mode_key: str, tool_name: str) -> ModeTool:
    return await mode_tools.create(ModeTool(mode_key=mode_key, tool_name=tool_name))


def _access(book_id: int, user_id: int) -> BookAccess:
    return BookAccess(
        book_id=book_id,
        user_id=user_id,
        role=AccessRole.owner,
        book_state=BookState.active,
        visibility=Visibility.private,
        collaboration_mode=CollaborationMode.free,
    )


async def _turn_context(
    *,
    subject: ResolvedSubject | None = None,
    author_prompt: str = "",
) -> TurnContext:
    """Seed a full world and build a ``TurnContext`` directly.

    Building the frozen record by hand isolates ``run_turn`` from
    ``prepare_turn``; ``subject`` is the new fourth field.

    ``author_prompt`` seeds the chat author's own ``BookAuthorPrompt`` row --
    the source of the composer's third layer since feature 021 step 004. It was
    ``book_prompt`` (a ``Book.system_prompt`` value) before the switch.
    """
    user = await _seed_user()
    book = await _seed_book(user.id)
    server = await _seed_server()
    chat = await _seed_chat(book.id, user.id, server.id)
    if author_prompt:
        await book_author_prompts.create(
            BookAuthorPrompt(
                book_id=book.id, user_id=user.id, system_prompt=author_prompt
            )
        )
    if subject is None:
        return TurnContext(chat=chat, server=server, resolved_key="resolved-secret")
    return TurnContext(
        chat=chat, server=server, resolved_key="resolved-secret", subject=subject
    )


async def _run(context: TurnContext, prompt: str | None = "ask"):
    return [frame async for frame in chat_turn.run_turn(context, prompt)]


# ---------------------------------------------------------------------------
# DoD-1 — the three codex kinds map to the three edit modes
# ---------------------------------------------------------------------------


# DoD-1 (assistant-config.md -> Mode determination; UC-095 runtime half): a turn
# whose subject is a codex entry of kind character / location / fact resolves the
# mode edit-character / edit-location / edit-fact respectively.
@pytest.mark.parametrize(
    ("kind", "expected_mode"),
    [
        (CodexKind.character, "edit-character"),
        (CodexKind.location, "edit-location"),
        (CodexKind.fact, "edit-fact"),
    ],
    ids=["character", "location", "fact"],
)
async def test_codex_entry_kind_resolves_its_edit_mode__DoD1_UC095(
    db: DbConfig, kind, expected_mode
):
    user = await _seed_user()
    book = await _seed_book(user.id)
    entry = await _seed_entry(book.id, user.id, kind, name="N")

    resolved = await assistant_runtime.resolve_subject(
        _access(book.id, user.id),
        subject_kind="codex-entry",
        subject_id=str(entry.id),
    )

    assert resolved.kind == "codex-entry"
    assert resolved.entry is not None
    assert resolved.entry.id == entry.id
    assert resolved.mode_key == expected_mode
    # The pure mapping agrees with the resolved record.
    assert assistant_runtime.determine_mode(resolved) == expected_mode


# ---------------------------------------------------------------------------
# DoD-2 — a blank entry (no id) resolves the mode from the request's codex kind
# ---------------------------------------------------------------------------


# DoD-2 (UC-076 -- a blank entry has no row yet): a codex-entry subject with NO id
# resolves its mode from the request's codex_kind, carrying no entry row.
@pytest.mark.parametrize(
    ("codex_kind", "expected_mode"),
    [
        (CodexKind.character, "edit-character"),
        (CodexKind.location, "edit-location"),
        (CodexKind.fact, "edit-fact"),
    ],
    ids=["character", "location", "fact"],
)
async def test_blank_entry_resolves_mode_from_request_kind__DoD2_UC076(
    db: DbConfig, codex_kind, expected_mode
):
    user = await _seed_user()
    book = await _seed_book(user.id)

    resolved = await assistant_runtime.resolve_subject(
        _access(book.id, user.id),
        subject_kind="codex-entry",
        subject_id=None,
        codex_kind=codex_kind,
    )

    assert resolved.kind == "codex-entry"
    # No row exists yet, so none was loaded.
    assert resolved.entry is None
    assert resolved.mode_key == expected_mode


# ---------------------------------------------------------------------------
# DoD-3 — for an existing entry the ROW's kind decides; the request's is ignored
# ---------------------------------------------------------------------------


# DoD-3 (context.md -> shared-canvas design point 1): for an existing entry the
# row's kind decides the mode and a conflicting codex_kind in the request is
# ignored.
@pytest.mark.parametrize(
    ("row_kind", "request_kind", "expected_mode"),
    [
        (CodexKind.character, CodexKind.fact, "edit-character"),
        (CodexKind.location, CodexKind.character, "edit-location"),
        (CodexKind.fact, CodexKind.location, "edit-fact"),
    ],
    ids=["character_row", "location_row", "fact_row"],
)
async def test_existing_entry_row_kind_wins_over_request__DoD3(
    db: DbConfig, row_kind, request_kind, expected_mode
):
    user = await _seed_user()
    book = await _seed_book(user.id)
    entry = await _seed_entry(book.id, user.id, row_kind, name="N")

    resolved = await assistant_runtime.resolve_subject(
        _access(book.id, user.id),
        subject_kind="codex-entry",
        subject_id=str(entry.id),
        codex_kind=request_kind,
    )

    assert resolved.entry is not None
    assert resolved.entry.kind == row_kind
    assert resolved.mode_key == expected_mode


# ---------------------------------------------------------------------------
# DoD-4 — another book's entry: no subject, no mode, nothing loaded
# ---------------------------------------------------------------------------


# DoD-4 (US-085.AC-1): a subject id naming an entry in ANOTHER book resolves to no
# subject and no mode -- the foreign row is never loaded, so none of its content
# can reach the turn.
async def test_other_books_entry_is_not_loaded__DoD4_US085_AC1(db: DbConfig):
    user = await _seed_user()
    book = await _seed_book(user.id)
    other_owner = await _seed_user("stranger")
    other_book = await _seed_book(other_owner.id)
    foreign = await _seed_entry(
        other_book.id,
        other_owner.id,
        CodexKind.character,
        name="Foreign",
        body="SECRET_FOREIGN_BODY",
    )

    resolved = await assistant_runtime.resolve_subject(
        _access(book.id, user.id),
        subject_kind="codex-entry",
        subject_id=str(foreign.id),
    )

    # No cross-book content was loaded.
    assert resolved.entry is None
    # And no subject at all -- not merely an absent mode.
    assert resolved.kind is None
    assert resolved.mode_key is None
    assert assistant_runtime.determine_mode(resolved) is None


# ---------------------------------------------------------------------------
# DoD-5 — book state, lists, chats and an absent subject all resolve to no mode
# ---------------------------------------------------------------------------


# DoD-5 (assistant-config.md: subjects outside the five fall outside the mode
# set): the book-state subject, every list subject and the chats subject resolve
# to no mode.
@pytest.mark.parametrize(
    "subject_kind",
    [
        "book-state",
        "characters",
        "locations",
        "facts",
        "chapters",
        "variants",
        "chapter-variants",
        "chats",
    ],
)
async def test_non_mode_subjects_resolve_to_no_mode__DoD5(db: DbConfig, subject_kind):
    user = await _seed_user()
    book = await _seed_book(user.id)

    resolved = await assistant_runtime.resolve_subject(
        _access(book.id, user.id), subject_kind=subject_kind
    )

    assert resolved.mode_key is None
    assert assistant_runtime.determine_mode(resolved) is None


# DoD-5: an ABSENT subject (no subject fields at all) resolves to no subject and
# no mode.
async def test_absent_subject_resolves_to_no_mode__DoD5(db: DbConfig):
    user = await _seed_user()
    book = await _seed_book(user.id)

    resolved = await assistant_runtime.resolve_subject(_access(book.id, user.id))

    assert resolved.kind is None
    assert resolved.entry is None
    assert resolved.mode_key is None
    assert assistant_runtime.determine_mode(resolved) is None
    assert NO_SUBJECT.mode_key is None
    assert assistant_runtime.determine_mode(NO_SUBJECT) is None


# ---------------------------------------------------------------------------
# DoD-6 — a chapter subject has no mode in THIS feature
# ---------------------------------------------------------------------------


# DoD-6 (write-chapter / close-chapter belong to 015 / 016): a chapter subject
# resolves to no mode here.
async def test_chapter_subject_has_no_mode_yet__DoD6(db: DbConfig):
    user = await _seed_user()
    book = await _seed_book(user.id)

    resolved = await assistant_runtime.resolve_subject(
        _access(book.id, user.id), subject_kind="chapter", subject_id="12345"
    )

    assert resolved.mode_key is None
    assert assistant_runtime.determine_mode(resolved) is None
    assert assistant_runtime.determine_mode(ResolvedSubject(kind="chapter")) is None


# ---------------------------------------------------------------------------
# DoD-7 — the mode prompt reaches compose_system_prompt as the MODE layer
# ---------------------------------------------------------------------------


# DoD-7 (US-110.AC-3; assistant-config.md -> composition order): the resolved
# mode's system_prompt is looked up and reaches compose_system_prompt as its mode
# layer, and the composed prompt carries base, then mode, then the author layer,
# in that order. (The third layer was the book's until feature 021 step 004.)
async def test_mode_prompt_is_the_mode_layer_in_order__DoD7_US110_AC3(
    db: DbConfig, monkeypatch
):
    await _seed_mode("edit-character", "MODE_RULES_ABC")
    context = await _turn_context(
        subject=ResolvedSubject(kind="codex-entry", mode_key="edit-character"),
        author_prompt="AUTHOR_RULES_XYZ",
    )
    fake = _install_client(monkeypatch, _FakeClient(chunks=["ok"]))

    assert await assistant_runtime.mode_system_prompt("edit-character") == (
        "MODE_RULES_ABC"
    )

    await _run(context)

    system = fake.call["system"]
    assert BASE_SYSTEM_PROMPT in system
    assert "MODE_RULES_ABC" in system
    assert "AUTHOR_RULES_XYZ" in system
    # base, then mode, then author.
    assert (
        system.index(BASE_SYSTEM_PROMPT)
        < system.index("MODE_RULES_ABC")
        < system.index("AUTHOR_RULES_XYZ")
    )
    # The mode prompt entered the composer as the `mode` layer (and only there).
    assert system == compose_system_prompt(
        base=BASE_SYSTEM_PROMPT, mode="MODE_RULES_ABC", author="AUTHOR_RULES_XYZ"
    )


# ---------------------------------------------------------------------------
# DoD-8 — a null / empty / whitespace mode prompt contributes NO section
# ---------------------------------------------------------------------------


# DoD-8 (US-110.AC-4): a mode whose system_prompt is null, empty or whitespace
# contributes no section at all -- the composed prompt is exactly what it would be
# with no mode layer (no header, no blank block).
@pytest.mark.parametrize(
    "stored_prompt", [None, "", "   ", "\n\t  \n"], ids=["null", "empty", "spaces", "ws"]
)
async def test_blank_mode_prompt_contributes_no_section__DoD8_US110_AC4(
    db: DbConfig, monkeypatch, stored_prompt
):
    await _seed_mode("edit-fact", stored_prompt)
    context = await _turn_context(
        subject=ResolvedSubject(kind="codex-entry", mode_key="edit-fact"),
        author_prompt="AUTHOR_RULES_XYZ",
    )
    fake = _install_client(monkeypatch, _FakeClient(chunks=["ok"]))

    assert await assistant_runtime.mode_system_prompt("edit-fact") is None

    await _run(context)

    system = fake.call["system"]
    assert system == compose_system_prompt(
        base=BASE_SYSTEM_PROMPT, author="AUTHOR_RULES_XYZ"
    )
    assert BASE_SYSTEM_PROMPT in system
    assert "AUTHOR_RULES_XYZ" in system


# DoD-8 (US-110.AC-4): a mode key with no AssistantMode row, and an absent key,
# both yield no mode prompt -- so neither can contribute a section.
async def test_missing_or_absent_mode_row_yields_no_prompt__DoD8_US110_AC4(
    db: DbConfig,
):
    assert await assistant_runtime.mode_system_prompt("edit-location") is None
    assert await assistant_runtime.mode_system_prompt(None) is None


# ---------------------------------------------------------------------------
# DoD-9 — with a mode, ONLY that mode's mode_tool rows are offered
# ---------------------------------------------------------------------------


# DoD-9 (US-111.AC-2): with a mode, only that mode's mode_tool rows are built into
# the tool definitions; a registry tool the mode did not select is absent from
# BOTH the definitions and the callable map.
async def test_mode_gating_offers_only_selected_tools__DoD9_US111_AC2(
    db: DbConfig, monkeypatch
):
    _widen_registry(monkeypatch)
    await _seed_mode("edit-character", "MODE_RULES")
    await _seed_mode_tool("edit-character", "web_search")
    # A sibling mode's selection must not leak into this mode's allowlist.
    await _seed_mode_tool("edit-location", "note_tool")
    context = await _turn_context(
        subject=ResolvedSubject(kind="codex-entry", mode_key="edit-character")
    )
    fake = _install_client(monkeypatch, _FakeClient(chunks=["ok"]))

    assert await assistant_runtime.allowed_tool_names("edit-character") == (
        "web_search",
    )

    frames = await _run(context)

    assert set(fake.call["tools"].keys()) == {"web_search"}
    assert "note_tool" not in fake.call["tools"]
    assert len(fake.call["tools_definitions"]) == 1
    assert "web_search" in str(fake.call["tools_definitions"])
    assert "note_tool" not in str(fake.call["tools_definitions"])
    assert frames[-1].event == "done"


# ---------------------------------------------------------------------------
# DoD-10 — zero mode_tool rows means ZERO tools, not the whole registry
# ---------------------------------------------------------------------------


# DoD-10 (012's settled rule): a mode with zero mode_tool rows yields zero tools
# -- an empty allowlist, not the whole registry.
async def test_mode_with_no_tool_rows_offers_nothing__DoD10(db: DbConfig, monkeypatch):
    _widen_registry(monkeypatch)
    await _seed_mode("edit-fact", "MODE_RULES")
    # Another mode has selections; this one has none.
    await _seed_mode_tool("edit-character", "web_search")
    context = await _turn_context(
        subject=ResolvedSubject(kind="codex-entry", mode_key="edit-fact")
    )
    fake = _install_client(monkeypatch, _FakeClient(chunks=["ok"]))

    assert await assistant_runtime.allowed_tool_names("edit-fact") == ()

    frames = await _run(context)

    assert not fake.call["tools"]
    assert not fake.call["tools_definitions"]
    assert "web_search" not in (fake.call["tools"] or {})
    assert frames[-1].event == "done"


# ---------------------------------------------------------------------------
# DoD-11 — no mode means exactly BASE_TOOL_NAMES (decision 6)
# ---------------------------------------------------------------------------


# DoD-11 (context.md decision 6): with NO mode, exactly BASE_TOOL_NAMES is
# allowed -- so web_search survives on the chats view and the book-state view, and
# a null mode is NOT the whole registry.
@pytest.mark.parametrize("subject_kind", ["chats", "book-state"])
async def test_no_mode_allows_exactly_base_tool_names__DoD11(
    db: DbConfig, monkeypatch, subject_kind
):
    _widen_registry(monkeypatch)
    context = await _turn_context(
        subject=ResolvedSubject(kind=subject_kind, mode_key=None)
    )
    fake = _install_client(monkeypatch, _FakeClient(chunks=["ok"]))

    assert await assistant_runtime.allowed_tool_names(None) == BASE_TOOL_NAMES
    assert set(BASE_TOOL_NAMES) == {"web_search"}

    frames = await _run(context)

    # Set equality: exactly the base allowlist, not the (widened) registry.
    assert set(fake.call["tools"].keys()) == set(BASE_TOOL_NAMES)
    assert len(fake.call["tools_definitions"]) == len(set(BASE_TOOL_NAMES))
    assert "web_search" in fake.call["tools"]
    assert "note_tool" not in fake.call["tools"]
    assert "note_tool" not in str(fake.call["tools_definitions"])
    assert frames[-1].event == "done"


# ---------------------------------------------------------------------------
# DoD-12 — an unknown mode_tool name is skipped and logged; the turn still runs
# ---------------------------------------------------------------------------


# DoD-12 (assistant-config.md -> the catalogue is the source of truth): a
# mode_tool row naming a tool absent from TOOL_REGISTRY is skipped and logged, and
# the turn still runs with the remaining tools.
async def test_unknown_mode_tool_is_skipped_and_logged__DoD12(
    db: DbConfig, monkeypatch, caplog
):
    await _seed_mode("edit-location", "MODE_RULES")
    await _seed_mode_tool("edit-location", "web_search")
    await _seed_mode_tool("edit-location", "no_such_tool")
    context = await _turn_context(
        subject=ResolvedSubject(kind="codex-entry", mode_key="edit-location")
    )
    fake = _install_client(monkeypatch, _FakeClient(chunks=["ok"]))

    # Both rows are in the allowlist -- the catalogue, not the allowlist, is what
    # drops the unknown name.
    assert set(await assistant_runtime.allowed_tool_names("edit-location")) == {
        "web_search",
        "no_such_tool",
    }

    with caplog.at_level(logging.WARNING):
        frames = await _run(context)

    # The turn still ran, with the remaining tool.
    assert frames[-1].event == "done"
    assert set(fake.call["tools"].keys()) == {"web_search"}
    assert len(fake.call["tools_definitions"]) == 1
    # Skipped AND logged.
    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert any("no_such_tool" in r.getMessage() for r in warnings)
    assert any(r.name.startswith("app.") for r in warnings)


# ---------------------------------------------------------------------------
# DoD-13 — a turn with no subject fields behaves exactly as 011 shipped it
# ---------------------------------------------------------------------------


# DoD-13 (backward compatibility): TurnRequest's three subject fields are all
# optional-and-absent, so `{}` and `{"prompt": ...}` are still complete bodies.
def test_turn_request_subject_fields_are_optional__DoD13():
    empty = TurnRequest.model_validate({})
    assert empty.prompt is None
    assert empty.subject_kind is None
    assert empty.subject_id is None
    assert empty.codex_kind is None

    prompt_only = TurnRequest.model_validate({"prompt": "hello"})
    assert prompt_only.prompt == "hello"
    assert prompt_only.subject_kind is None
    assert prompt_only.subject_id is None
    assert prompt_only.codex_kind is None


# DoD-13 (backward compatibility): prepare_turn with a subject-less request -- and
# with no request at all -- yields a context carrying no subject and no mode.
async def test_prepare_turn_without_subject_carries_no_mode__DoD13(db: DbConfig):
    user = await _seed_user()
    book = await _seed_book(user.id)
    server = await _seed_server()
    chat = await _seed_chat(book.id, user.id, server.id)
    access = _access(book.id, user.id)

    plain = await chat_turn.prepare_turn(access, str(chat.id))
    assert plain.subject.kind is None
    assert plain.subject.entry is None
    assert plain.subject.mode_key is None

    with_request = await chat_turn.prepare_turn(
        access, str(chat.id), TurnRequest(prompt="hello")
    )
    assert with_request.subject.kind is None
    assert with_request.subject.entry is None
    assert with_request.subject.mode_key is None


# DoD-13 (backward compatibility): a turn sent with no subject fields at all
# behaves exactly as 011 shipped it -- base + the author's system prompt with no
# mode layer (the third layer was the book's until feature 021 step 004),
# web_search offered (the BASE_TOOL_NAMES allowlist), the reply streamed and
# persisted, ending in one `done`.
async def test_subjectless_turn_behaves_as_shipped__DoD13(db: DbConfig, monkeypatch):
    context = await _turn_context(author_prompt="AUTHOR_RULES_XYZ")
    fake = _install_client(monkeypatch, _FakeClient(chunks=["the-answer"]))

    frames = await _run(context, "ask")

    system = fake.call["system"]
    assert system == compose_system_prompt(
        base=BASE_SYSTEM_PROMPT, author="AUTHOR_RULES_XYZ"
    )
    assert set(fake.call["tools"].keys()) == set(BASE_TOOL_NAMES)
    assert "web_search" in fake.call["tools"]

    events = [f.event for f in frames]
    assert events.count("done") == 1
    assert events[-1] == "done"
    assert "error" not in events

    stored = await chat_messages.list_by_chat_ordered(context.chat.id)
    assert [m.content for m in stored if m.role == "user"] == ["ask"]
    assert [m.content for m in stored if m.role == "assistant"] == ["the-answer"]
