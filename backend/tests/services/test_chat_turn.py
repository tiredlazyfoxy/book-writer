"""Tests for the streaming turn orchestrator and its helpers (feature 011, step 003).

Bound to the frozen skeleton (status.md -> Skeleton -> Step 003), in
``app.services.chat_turn``:
    def build_sampling_options(sampling: ChatSamplingParams, backend_type: str)
        -> dict[str, object]
    @dataclass(frozen=True) class TurnContext { chat: Chat; server: LlmServer;
        resolved_key: str | None }
    @dataclass(frozen=True) class TurnFrame  { event: str; data: BaseModel }
    async def prepare_turn(access, chat_id: str) -> TurnContext
    async def run_turn(context: TurnContext, prompt: str | None)
        -> AsyncGenerator[TurnFrame, None]
and the frame payload DTOs in ``app.models.schemas.chats``
(``ThinkingFrame`` / ``DeltaFrame`` / ``DoneFrame`` / ``ErrorFrame``).

No network / no real LLM. The client-construction path is the seam: the tests
substitute a fake ``LLMClient`` (async context manager) whose ``chat_with_tools``
drives the supplied ``on_delta`` with a scripted list of chunks then returns (or
raises), and monkeypatch it in at ``create_model_client``
(003.context.md -> "Testing this step without a network"). ``prepare_turn`` runs
against the real ``db`` fixture with rows seeded through the db layer.

Expected values come from the SPEC ONLY -- the step DoD (DoD-2..DoD-11), the
Interface intent, and the feature ``context.md`` decisions -- never from
implementation internals. ``asyncio_mode = "auto"``.

Extended by feature 021, step 004 (the composition switch): the turn now
composes the prompt belonging to **the chat's own author** -- the
``BookAuthorPrompt`` row for ``(chat.book_id, chat.author_id)`` -- as the
composer's renamed ``author`` layer, and ``Book.system_prompt`` no longer
influences composition at all. Its DoD-4 / DoD-5 / DoD-6 / DoD-7 coverage lives
at the bottom of this module; feature 011's ``__DoD11`` guard is superseded in
place (same assertions, third-layer sentinel moved off the retired column onto
the author's row). Sources: ``021/004.composition-switch.md`` -> Interface
intent + DoD, ``021/context.md`` decisions 2 and 3.
"""

import datetime
import inspect
from pathlib import Path

import aiohttp
import pytest
from llm import LLMError

from app.db import book_author_prompts, books, chat_messages, chats, llm_servers, users
from app.db.engine import DbConfig, init_db, init_engine, set_db_ready
from app.models.book import Book, BookState, CollaborationMode, Visibility
from app.models.book_author_prompt import BookAuthorPrompt
from app.models.chat import Chat, ChatMessage
from app.models.llm_server import LlmServer
from app.models.schemas.chats import (
    ChatSamplingParams,
    DeltaFrame,
    DoneFrame,
    ErrorFrame,
    ThinkingFrame,
)
from app.models.user import User, UserRole
from app.services import auth, chat_turn
from app.services.assistant_runtime import BASE_TOOL_NAMES
from app.services.authz import AccessRole, BookAccess
from app.services.chat_turn import TurnContext
from app.services.chats import ChatError, ChatErrorReason
from app.services.db_import_export import export_all, import_all
from app.services.llm_servers import LlmServerError, LlmServerErrorReason
from app.services.prompt_composition import BASE_SYSTEM_PROMPT, compose_system_prompt


# ---------------------------------------------------------------------------
# The fake LLM client -- the substituted construction seam.
# ---------------------------------------------------------------------------


class _FakeClient:
    """A stand-in for ``llm.LLMClient`` used as an async context manager.

    ``chat_with_tools`` drives ``on_delta`` with the scripted chunks exactly the
    way the real library does (calling it, awaiting the result if it is
    awaitable -- see ``llm/llm_client.py``), records the call kwargs, then either
    raises the configured exception or returns the configured final string.
    ``entered`` / ``exited`` flag the async-context-manager lifecycle so a test
    can assert the session was closed on every path.
    """

    def __init__(self, *, chunks=None, exc=None, return_value=""):
        self._chunks = list(chunks or [])
        self._exc = exc
        self._return_value = return_value
        self.entered = False
        self.exited = False
        self.call: dict | None = None
        self.construct_args: tuple | None = None

    async def __aenter__(self):
        self.entered = True
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.exited = True
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
            "max_loops": max_loops,
            "options": options,
            "stream": stream,
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
    """Monkeypatch ``create_model_client`` (the frozen seam) to yield ``fake``.

    Patched on the service module the namespace import resolves through; also on
    ``chat_turn`` itself (``raising=False``) in case of a direct import.
    """

    def factory(server, resolved_key, model):
        fake.construct_args = (server, resolved_key, model)
        return fake

    monkeypatch.setattr(
        "app.services.llm_servers.create_model_client", factory
    )
    monkeypatch.setattr(
        "app.services.chat_turn.create_model_client", factory, raising=False
    )
    return fake


# ---------------------------------------------------------------------------
# Seeding helpers (008/009 style: rows constructed through the db layer).
# ---------------------------------------------------------------------------


async def _seed_user(username: str) -> User:
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


async def _seed_server(
    *,
    backend_type: str = "openai",
    enabled_models: str = '["gpt-x"]',
    is_active: bool = True,
    api_key: str | None = "sk-stored",
) -> LlmServer:
    return await llm_servers.create(
        LlmServer(
            name="S",
            backend_type=backend_type,
            base_url="https://api.example.com/v1",
            api_key=api_key,
            enabled_models=enabled_models,
            is_active=is_active,
        )
    )


async def _seed_chat(
    *,
    book_id: int,
    author_id: int,
    llm_server_id: int | None,
    model_name: str | None,
) -> Chat:
    return await chats.create(
        Chat(
            book_id=book_id,
            author_id=author_id,
            title="A Chat",
            llm_server_id=llm_server_id,
            model_name=model_name,
        )
    )


def _access(book_id: int, user_id: int) -> BookAccess:
    return BookAccess(
        book_id=book_id,
        user_id=user_id,
        role=AccessRole.owner,
        book_state=BookState.active,
        visibility=Visibility.private,
        collaboration_mode=CollaborationMode.free,
    )


async def _context(
    *,
    backend_type: str = "openai",
    system_prompt: str = "",
    author_prompt: str | None = None,
    resolved_key: str | None = "resolved-secret",
    model_name: str = "gpt-x",
    username: str = "author",
) -> TurnContext:
    """Seed a full world (user/book/server/chat) and build a TurnContext directly.

    Building the frozen ``TurnContext`` by hand isolates ``run_turn`` from
    ``prepare_turn`` (the skeleton froze the turn as those two entry points).

    ``system_prompt`` seeds the (dormant since feature 021) ``Book.system_prompt``
    column; ``author_prompt`` seeds the chat author's own ``BookAuthorPrompt``
    row, which is what the turn composes as its ``author`` layer. ``None`` means
    "this author has no row at all".
    """
    user = await _seed_user(username)
    book = await _seed_book(user.id, system_prompt=system_prompt)
    server = await _seed_server(backend_type=backend_type)
    chat = await _seed_chat(
        book_id=book.id,
        author_id=user.id,
        llm_server_id=server.id,
        model_name=model_name,
    )
    if author_prompt is not None:
        await book_author_prompts.create(
            BookAuthorPrompt(
                book_id=book.id, user_id=user.id, system_prompt=author_prompt
            )
        )
    return TurnContext(chat=chat, server=server, resolved_key=resolved_key)


async def _run(context: TurnContext, prompt: str | None):
    return [frame async for frame in chat_turn.run_turn(context, prompt)]


async def _messages(chat_id: int) -> list[ChatMessage]:
    return await chat_messages.list_by_chat_ordered(chat_id)


# ---------------------------------------------------------------------------
# DoD-2 — user message persisted BEFORE the assistant call; survives a failure
# ---------------------------------------------------------------------------


# DoD-2 (UC-056, US-060.AC-2): a turn with a prompt persists the user message
# before the assistant call; when the assistant fails, that user message remains
# stored exactly once and no assistant message is written.
async def test_user_message_survives_failure_once_no_assistant__DoD2_US060_AC2(
    db: DbConfig, monkeypatch
):
    context = await _context()
    _install_client(monkeypatch, _FakeClient(exc=LLMError("upstream 500")))

    frames = await _run(context, "my question")

    stored = await _messages(context.chat.id)
    users_msgs = [m for m in stored if m.role == "user"]
    assistant_msgs = [m for m in stored if m.role == "assistant"]
    assert len(users_msgs) == 1
    assert users_msgs[0].content == "my question"
    assert assistant_msgs == []
    # And the failure surfaced as a single error frame (no done).
    assert [f.event for f in frames] == ["error"]


# ---------------------------------------------------------------------------
# DoD-3 — a retry (no prompt) re-runs over stored history, no duplicate user msg
# ---------------------------------------------------------------------------


# DoD-3 (UC-056, US-060.AC-1/AC-2): a retry -- run_turn with prompt=None --
# re-runs the assistant over the already-stored history without re-sending or
# duplicating the user message; the conversation gains only the new assistant
# message.
async def test_retry_reruns_over_history_without_duplicating_user__DoD3_US060(
    db: DbConfig, monkeypatch
):
    context = await _context()
    # Simulate a prior (failed) turn: a stored user message, no assistant reply.
    await chat_messages.create(
        ChatMessage(
            chat_id=context.chat.id,
            role="user",
            content="stored question",
            position=0,
        )
    )
    fake = _install_client(monkeypatch, _FakeClient(chunks=["a reply"]))

    frames = await _run(context, None)

    stored = await _messages(context.chat.id)
    users_msgs = [m for m in stored if m.role == "user"]
    assistant_msgs = [m for m in stored if m.role == "assistant"]
    # The user message was neither duplicated nor re-created.
    assert len(users_msgs) == 1
    assert users_msgs[0].content == "stored question"
    # Exactly one new assistant message was appended.
    assert len(assistant_msgs) == 1
    assert assistant_msgs[0].content == "a reply"
    # The stored history was replayed to the model.
    assert any(
        m.get("content") == "stored question" for m in fake.call["messages"]
    )
    # The turn completed.
    assert frames[-1].event == "done"


# ---------------------------------------------------------------------------
# DoD-4 — success persists one assistant message: content = content deltas,
#          reasoning = thinking deltas, at the next position
# ---------------------------------------------------------------------------


# DoD-4 (US-058.AC-1; decision 8): a successful turn persists exactly one
# assistant message whose content is assembled from the streamed CONTENT deltas
# and whose reasoning is assembled from the THINKING deltas, at the next position.
async def test_success_persists_assistant_content_and_reasoning__DoD4_US058_AC1(
    db: DbConfig, monkeypatch
):
    context = await _context()
    # Split stream: reasoning inside <think>, answer as content.
    chunks = ["<think>", "reason-A", "</think>", "answer-B"]
    _install_client(monkeypatch, _FakeClient(chunks=chunks))

    await _run(context, "ask")

    stored = await _messages(context.chat.id)
    assistant_msgs = [m for m in stored if m.role == "assistant"]
    user_msgs = [m for m in stored if m.role == "user"]
    assert len(assistant_msgs) == 1
    reply = assistant_msgs[0]
    assert reply.content == "answer-B"
    assert reply.reasoning == "reason-A"
    # Appended at the position after the just-persisted user message.
    assert reply.position == user_msgs[0].position + 1


# ---------------------------------------------------------------------------
# DoD-5 — frame vocabulary and routing
# ---------------------------------------------------------------------------


# DoD-5 (US-058.AC-1, US-060.AC-1): the frame stream uses exactly the names
# thinking / delta / done / error; thinking text rides `thinking`, content rides
# `delta`, and a successful turn terminates with a single `done` carrying the
# persisted assistant message.
async def test_success_frames_route_by_channel_and_end_with_done__DoD5_US058_AC1(
    db: DbConfig, monkeypatch
):
    context = await _context()
    chunks = ["<think>", "why-so", "</think>", "the-answer"]
    _install_client(monkeypatch, _FakeClient(chunks=chunks))

    frames = await _run(context, "ask")

    events = [f.event for f in frames]
    assert set(events) <= {"thinking", "delta", "done"}
    assert events.count("done") == 1
    assert events[-1] == "done"
    assert "error" not in events

    thinking_text = "".join(
        f.data.text for f in frames if f.event == "thinking"
    )
    delta_text = "".join(f.data.text for f in frames if f.event == "delta")
    assert thinking_text == "why-so"
    assert delta_text == "the-answer"
    for f in frames:
        if f.event == "thinking":
            assert isinstance(f.data, ThinkingFrame)
        elif f.event == "delta":
            assert isinstance(f.data, DeltaFrame)

    done = frames[-1]
    assert isinstance(done.data, DoneFrame)
    assert done.data.message.content == "the-answer"
    assert done.data.message.reasoning == "why-so"


# DoD-5 (US-060.AC-1): a failed turn terminates with a single `error` frame and
# no `done`.
async def test_failure_terminates_with_single_error_frame__DoD5_US060_AC1(
    db: DbConfig, monkeypatch
):
    context = await _context()
    _install_client(monkeypatch, _FakeClient(exc=LLMError("boom")))

    frames = await _run(context, "ask")

    events = [f.event for f in frames]
    assert events.count("error") == 1
    assert events[-1] == "error"
    assert "done" not in events
    assert isinstance(frames[-1].data, ErrorFrame)


# ---------------------------------------------------------------------------
# DoD-6 — sampling options only for llama-swap; none for openai
# ---------------------------------------------------------------------------


# DoD-6 (decision 4): build_sampling_options emits the chat's sampling params for
# a llama-swap server and NOTHING for an openai server.
def test_sampling_options_llama_swap_only__DoD6():
    sampling = ChatSamplingParams(temperature=0.3, top_p=0.5)

    openai_opts = chat_turn.build_sampling_options(sampling, "openai")
    assert openai_opts == {}

    swap_opts = chat_turn.build_sampling_options(sampling, "llama-swap")
    assert swap_opts != {}
    assert swap_opts["temperature"] == 0.3
    assert swap_opts["top_p"] == 0.5


# ---------------------------------------------------------------------------
# DoD-7 — client bound to (server, model) with resolved key; closed on both paths
# ---------------------------------------------------------------------------


# DoD-7 (assistant-config.md -> Model resolution): prepare_turn resolves the
# server api key through $ENV_VAR indirection, exposing the resolved secret on the
# TurnContext (and never the pointer).
async def test_prepare_turn_resolves_key_via_env_indirection__DoD7(
    db: DbConfig, monkeypatch
):
    monkeypatch.setenv("TURN_KEY_ENV", "live-secret-value")
    user = await _seed_user("keyholder")
    book = await _seed_book(user.id)
    server = await _seed_server(api_key="$TURN_KEY_ENV")
    chat = await _seed_chat(
        book_id=book.id,
        author_id=user.id,
        llm_server_id=server.id,
        model_name="gpt-x",
    )

    context = await chat_turn.prepare_turn(_access(book.id, user.id), str(chat.id))

    assert context.resolved_key == "live-secret-value"
    assert context.server.id == server.id
    assert context.chat.model_name == "gpt-x"


# DoD-7: run_turn constructs the client bound to the chat's (server, model) with
# the resolved key, and closes it (async __aexit__ runs) on the SUCCESS path.
async def test_client_bound_and_closed_on_success__DoD7(db: DbConfig, monkeypatch):
    context = await _context(model_name="gpt-x", resolved_key="resolved-secret")
    fake = _install_client(monkeypatch, _FakeClient(chunks=["ok"]))

    await _run(context, "ask")

    server_arg, key_arg, model_arg = fake.construct_args
    assert server_arg.id == context.server.id
    assert key_arg == "resolved-secret"
    assert model_arg == "gpt-x"
    assert fake.entered is True
    assert fake.exited is True


# DoD-7: the client is closed (async __aexit__ runs) on the FAILURE path too.
async def test_client_closed_on_failure__DoD7(db: DbConfig, monkeypatch):
    context = await _context()
    fake = _install_client(monkeypatch, _FakeClient(exc=LLMError("boom")))

    await _run(context, "ask")

    assert fake.entered is True
    assert fake.exited is True


# ---------------------------------------------------------------------------
# DoD-8 — pre-stream refusals raise typed service errors, nothing persisted
# ---------------------------------------------------------------------------


# DoD-8 (UC-054 exception flow): prepare_turn refuses a chat with no model pair,
# raising the typed error before anything is persisted. (The HTTP-status mapping
# is asserted in tests/routes/test_chat_turn.py.)
async def test_prepare_turn_refuses_no_model_pair__DoD8(db: DbConfig):
    user = await _seed_user("nopair")
    book = await _seed_book(user.id)
    chat = await _seed_chat(
        book_id=book.id, author_id=user.id, llm_server_id=None, model_name=None
    )

    with pytest.raises(ChatError) as exc:
        await chat_turn.prepare_turn(_access(book.id, user.id), str(chat.id))
    assert exc.value.reason == ChatErrorReason.invalid_model_pair
    assert await _messages(chat.id) == []


# DoD-8 (UC-054 exception flow): prepare_turn refuses a chat whose server is
# inactive with the unknown_or_inactive_server reason; nothing is persisted.
async def test_prepare_turn_refuses_inactive_server__DoD8(db: DbConfig):
    user = await _seed_user("downserver")
    book = await _seed_book(user.id)
    server = await _seed_server(is_active=False)
    chat = await _seed_chat(
        book_id=book.id,
        author_id=user.id,
        llm_server_id=server.id,
        model_name="gpt-x",
    )

    with pytest.raises(ChatError) as exc:
        await chat_turn.prepare_turn(_access(book.id, user.id), str(chat.id))
    assert exc.value.reason == ChatErrorReason.unknown_or_inactive_server
    assert await _messages(chat.id) == []


# DoD-8 (UC-054 exception flow): prepare_turn refuses when the server's key env
# var is unset, raising LlmServerError(env_not_set); nothing is persisted.
async def test_prepare_turn_refuses_unset_key_env__DoD8(db: DbConfig, monkeypatch):
    monkeypatch.delenv("TURN_MISSING_KEY", raising=False)
    user = await _seed_user("nokey")
    book = await _seed_book(user.id)
    server = await _seed_server(api_key="$TURN_MISSING_KEY")
    chat = await _seed_chat(
        book_id=book.id,
        author_id=user.id,
        llm_server_id=server.id,
        model_name="gpt-x",
    )

    with pytest.raises(LlmServerError) as exc:
        await chat_turn.prepare_turn(_access(book.id, user.id), str(chat.id))
    assert exc.value.reason == LlmServerErrorReason.env_not_set
    assert await _messages(chat.id) == []


# ---------------------------------------------------------------------------
# DoD-9 — every library failure surfaces as one error frame (no hung stream)
# ---------------------------------------------------------------------------


# DoD-9 (UC-056, US-060.AC-1): each library failure class surfaces as exactly one
# error frame and the generator terminates -- connection error, LLMError,
# ValueError (tool pre-flight), RuntimeError (raising tool / max_loops), and an
# empty response.
@pytest.mark.parametrize(
    "fake",
    [
        _FakeClient(exc=aiohttp.ClientConnectionError("no route")),
        _FakeClient(exc=LLMError("non-2xx")),
        _FakeClient(exc=ValueError("tool/definition mismatch")),
        _FakeClient(exc=RuntimeError("a tool raised / max_loops exhausted")),
        _FakeClient(chunks=[], return_value=""),  # empty response
    ],
    ids=["connection", "llm_error", "value_error", "runtime_error", "empty"],
)
async def test_library_failures_yield_single_error_frame__DoD9_US060_AC1(
    db: DbConfig, monkeypatch, fake
):
    context = await _context()
    _install_client(monkeypatch, fake)

    frames = await _run(context, "ask")

    events = [f.event for f in frames]
    assert events.count("error") == 1
    assert events[-1] == "error"
    assert "done" not in events
    assert isinstance(frames[-1].data, ErrorFrame)
    # No assistant message was written on any failure path.
    stored = await _messages(context.chat.id)
    assert [m for m in stored if m.role == "assistant"] == []


# ---------------------------------------------------------------------------
# DoD-11 — system prompt from base + book system_prompt; the null-mode allowlist
# ---------------------------------------------------------------------------


# DoD-11 (assistant-config.md; decision 9): the turn composes its system prompt
# from the base constant plus the third-layer prompt (mode/chapter absent) and
# offers exactly BASE_TOOL_NAMES because the mode is null.
#
# Updated by 013.codex step 009. The original clause read "offers the WHOLE
# TOOL_REGISTRY"; 013.codex context.md decision 6 (landed in step 007) replaced
# "null mode == the whole registry" with the code-defined BASE_TOOL_NAMES
# allowlist, and the two coincided only while the registry held a single entry.
# Step 009 adds the two bound codex entries, so the null-mode truth is now
# BASE_TOOL_NAMES.
#
# Superseded in place by 021 step 004: the third layer is no longer the book's
# `system_prompt` but the chat author's own prompt row (021/004 DoD-4/DoD-6), so
# the same sentinel is seeded there. Assertion strength is unchanged.
async def test_system_prompt_and_whole_registry_offered__DoD11(
    db: DbConfig, monkeypatch
):
    context = await _context(author_prompt="AUTHOR_RULES_XYZ")
    fake = _install_client(monkeypatch, _FakeClient(chunks=["ok"]))

    await _run(context, "ask")

    system = fake.call["system"]
    assert BASE_SYSTEM_PROMPT in system
    assert "AUTHOR_RULES_XYZ" in system

    # The null-mode allowlist is offered: the tool callable map and the OpenAI
    # tool definitions both cover exactly BASE_TOOL_NAMES.
    base_names = set(BASE_TOOL_NAMES)
    assert set(fake.call["tools"].keys()) == base_names
    assert {d["function"]["name"] for d in fake.call["tools_definitions"]} == base_names
    assert "web_search" in fake.call["tools"]


# ===========================================================================
# Feature 021, step 004 — the composition switch (BOOK becomes AUTHOR)
#
# The turn composes the prompt of the chat's OWN author, read from the
# BookAuthorPrompt row for (chat.book_id, chat.author_id), as the composer's
# `author` layer. `Book.system_prompt` is dormant: still written, still
# exported, read by nothing.
# ===========================================================================


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


async def _seed_prompt(book_id: int, user_id: int, text: str) -> BookAuthorPrompt:
    """Seed one author's own prompt row for one book (021 step 001's db module)."""
    return await book_author_prompts.create(
        BookAuthorPrompt(book_id=book_id, user_id=user_id, system_prompt=text)
    )


async def _two_author_contexts(
    prompt_a: str, prompt_b: str
) -> tuple[TurnContext, TurnContext]:
    """Two authors of ONE book, each with their own chat and their own prompt.

    The owner (author A) and a second author (author B) share a single book;
    each holds a different stored prompt. Returns (context_a, context_b).
    """
    author_a = await _seed_user("author-a")
    author_b = await _seed_user("author-b")
    book = await _seed_book(author_a.id)
    server = await _seed_server()
    chat_a = await _seed_chat(
        book_id=book.id,
        author_id=author_a.id,
        llm_server_id=server.id,
        model_name="gpt-x",
    )
    chat_b = await _seed_chat(
        book_id=book.id,
        author_id=author_b.id,
        llm_server_id=server.id,
        model_name="gpt-x",
    )
    await _seed_prompt(book.id, author_a.id, prompt_a)
    await _seed_prompt(book.id, author_b.id, prompt_b)
    return (
        TurnContext(chat=chat_a, server=server, resolved_key="resolved-secret"),
        TurnContext(chat=chat_b, server=server, resolved_key="resolved-secret"),
    )


async def _system_of(monkeypatch, context: TurnContext) -> str:
    """Run one turn against a fresh fake client and return the `system` it saw."""
    fake = _install_client(monkeypatch, _FakeClient(chunks=["ok"]))
    frames = await _run(context, "ask")
    assert frames[-1].event == "done"
    return fake.call["system"]


async def _seed_http_author(username: str) -> tuple[User, str]:
    """Seed an author with real credentials on the app's engine; return (user, token).

    Copied from tests/routes/test_books.py's `_seed_user` / `_seed_author`: the
    schema is built (idempotent `init_db`), the user gets a real bcrypt pwdhash
    and a per-user signing key, readiness is flipped, and a real access token is
    minted (auth in route tests is real).
    """
    await init_db()
    user = await users.create(
        User(
            username=username,
            role=UserRole.author,
            pwdhash=auth.hash_password("password123"),
            jwt_signing_key=auth.generate_signing_key(),
            last_key_update=_now(),
        )
    )
    set_db_ready(True)
    return user, auth.create_access_token(user)


# ---------------------------------------------------------------------------
# DoD-4 — the turn composes the prompt of the chat's OWN author
# ---------------------------------------------------------------------------


# 021/004 DoD-4: two authors of one book, each holding a different stored prompt,
# produce two DIFFERENT composed prompts -- each turn carries its own chat's
# author's text and nothing of the other's. (This deliberately reverses UC-093 /
# US-108's "one book prompt applied to every chat in the book".)
async def test_two_authors_of_one_book_get_different_prompts__DoD4(
    db: DbConfig, monkeypatch
):
    context_a, context_b = await _two_author_contexts(
        "AUTHOR_A_RULES", "AUTHOR_B_RULES"
    )

    system_a = await _system_of(monkeypatch, context_a)
    system_b = await _system_of(monkeypatch, context_b)

    # Each turn composed its own author's prompt as the author layer...
    assert system_a == compose_system_prompt(
        base=BASE_SYSTEM_PROMPT, author="AUTHOR_A_RULES"
    )
    assert system_b == compose_system_prompt(
        base=BASE_SYSTEM_PROMPT, author="AUTHOR_B_RULES"
    )
    # ...and nothing of the other author's.
    assert "AUTHOR_B_RULES" not in system_a
    assert "AUTHOR_A_RULES" not in system_b
    # Same book, two different composed prompts.
    assert system_a != system_b
    assert context_a.chat.book_id == context_b.chat.book_id
    assert context_a.chat.author_id != context_b.chat.author_id


# 021/004 DoD-4: the prompt is looked up for the chat's (book, author) pair, so a
# prompt the SAME author holds in a DIFFERENT book never reaches this book's turn.
async def test_authors_prompt_in_another_book_is_not_used__DoD4(
    db: DbConfig, monkeypatch
):
    context = await _context(author_prompt="THIS_BOOKS_RULES")
    other_book = await _seed_book(context.chat.author_id)
    await _seed_prompt(other_book.id, context.chat.author_id, "OTHER_BOOKS_RULES")

    system = await _system_of(monkeypatch, context)

    assert system == compose_system_prompt(
        base=BASE_SYSTEM_PROMPT, author="THIS_BOOKS_RULES"
    )
    assert "OTHER_BOOKS_RULES" not in system


# ---------------------------------------------------------------------------
# DoD-5 — an author with no prompt row composes with no author layer at all
# ---------------------------------------------------------------------------


# 021/004 DoD-5: a turn whose author has no prompt row composes with NO author
# layer -- no `### AUTHOR` heading, no section, no extra separator -- and every
# other layer is unaffected (the base layer is exactly what it is with no author
# argument at all).
async def test_author_without_prompt_row_gets_no_author_layer__DoD5(
    db: DbConfig, monkeypatch
):
    context = await _context(author_prompt=None)

    system = await _system_of(monkeypatch, context)

    assert system == compose_system_prompt(base=BASE_SYSTEM_PROMPT)
    assert "### AUTHOR" not in system
    assert BASE_SYSTEM_PROMPT in system


# 021/004 DoD-5 (Interface intent: "No row, or a blank prompt, contributes
# nothing"): a stored-but-blank prompt composes exactly like no row at all.
@pytest.mark.parametrize(
    "stored", ["", "   ", "\n\t  \n"], ids=["empty", "spaces", "mixed_ws"]
)
async def test_blank_stored_prompt_composes_like_no_row__DoD5(
    db: DbConfig, monkeypatch, stored
):
    context = await _context(author_prompt=stored)

    system = await _system_of(monkeypatch, context)

    assert system == compose_system_prompt(base=BASE_SYSTEM_PROMPT)
    assert "### AUTHOR" not in system


# ---------------------------------------------------------------------------
# DoD-6 — Book.system_prompt no longer influences composition
# ---------------------------------------------------------------------------


# 021/004 DoD-6 (021/context.md decision 2 -- the column goes dormant): setting
# Book.system_prompt to a distinctive value changes nothing in the composed
# prompt; the author's own text is what is composed.
async def test_book_column_does_not_reach_composition__DoD6(
    db: DbConfig, monkeypatch
):
    context = await _context(
        system_prompt="DISTINCTIVE_BOOK_COLUMN_VALUE", author_prompt="AUTHOR_RULES"
    )

    system = await _system_of(monkeypatch, context)

    assert "DISTINCTIVE_BOOK_COLUMN_VALUE" not in system
    assert system == compose_system_prompt(
        base=BASE_SYSTEM_PROMPT, author="AUTHOR_RULES"
    )


# 021/004 DoD-6: with no author prompt at all, a distinctive Book.system_prompt
# still contributes nothing -- the composed prompt is byte-for-byte what an empty
# column produces, so the column cannot be the third layer by any path.
async def test_book_column_value_changes_nothing__DoD6(db: DbConfig, monkeypatch):
    with_value = await _context(
        system_prompt="DISTINCTIVE_BOOK_COLUMN_VALUE", username="author-with"
    )
    without_value = await _context(system_prompt="", username="author-without")

    system_with = await _system_of(monkeypatch, with_value)
    system_without = await _system_of(monkeypatch, without_value)

    assert system_with == system_without
    assert "DISTINCTIVE_BOOK_COLUMN_VALUE" not in system_with
    assert system_with == compose_system_prompt(base=BASE_SYSTEM_PROMPT)


# ---------------------------------------------------------------------------
# DoD-7 — the column is nevertheless still alive
# ---------------------------------------------------------------------------


# 021/004 DoD-7: a book created through the ordinary path (POST /api/books) still
# carries `system_prompt` -- the required column is still written at creation
# (services/books.py is out of scope and keeps writing ""), so it is dormant, not
# dropped.
async def test_created_book_still_carries_the_column__DoD7(http_client):
    _, token = await _seed_http_author("dormant-column-owner")

    resp = await http_client.post(
        "/api/books",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "A Book",
            "description": "a description",
            "collaboration_mode": "free",
            "visibility": "private",
        },
    )
    assert resp.status_code == 201, resp.text

    row = await books.get_by_id(int(resp.json()["id"]))
    assert row is not None
    # Present and non-null: a required str, written "" at creation.
    assert isinstance(row.system_prompt, str)
    assert row.system_prompt == ""


# 021/004 DoD-7: the column still round-trips through export and import -- the
# archive is imported into a FRESH database, so the value can only be there if
# export wrote it and import read it back (021/context.md decision 2: keep the
# JSONL codec so existing exports still import).
async def test_column_round_trips_through_export_and_import__DoD7(
    db: DbConfig, tmp_path: Path
):
    owner = await _seed_user("archivist")
    book = await _seed_book(owner.id, system_prompt="DORMANT_BUT_ARCHIVED")

    archive = await export_all()

    # A pristine database: nothing of the original rows is present.
    await init_engine(DbConfig(db_path=tmp_path / "restored.db"))
    await init_db()
    assert await books.get_by_id(book.id) is None

    await import_all(archive)

    restored = await books.get_by_id(book.id)
    assert restored is not None
    assert restored.system_prompt == "DORMANT_BUT_ARCHIVED"
