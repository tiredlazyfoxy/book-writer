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
"""

import inspect

import aiohttp
import pytest
from llm import LLMError

from app.db import books, chat_messages, chats, llm_servers, users
from app.db.engine import DbConfig
from app.models.book import Book, BookState, CollaborationMode, Visibility
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
from app.services import chat_turn
from app.services.authz import AccessRole, BookAccess
from app.services.chat_turn import TurnContext
from app.services.chats import ChatError, ChatErrorReason
from app.services.llm_servers import LlmServerError, LlmServerErrorReason
from app.services.prompt_composition import BASE_SYSTEM_PROMPT
from app.services.tools import TOOL_REGISTRY


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
    resolved_key: str | None = "resolved-secret",
    model_name: str = "gpt-x",
) -> TurnContext:
    """Seed a full world (user/book/server/chat) and build a TurnContext directly.

    Building the frozen ``TurnContext`` by hand isolates ``run_turn`` from
    ``prepare_turn`` (the skeleton froze the turn as those two entry points).
    """
    user = await _seed_user("author")
    book = await _seed_book(user.id, system_prompt=system_prompt)
    server = await _seed_server(backend_type=backend_type)
    chat = await _seed_chat(
        book_id=book.id,
        author_id=user.id,
        llm_server_id=server.id,
        model_name=model_name,
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
# DoD-11 — system prompt from base + book system_prompt; whole TOOL_REGISTRY
# ---------------------------------------------------------------------------


# DoD-11 (assistant-config.md; decision 9): the turn composes its system prompt
# from the base constant plus the book's system_prompt (mode/chapter absent) and
# offers the WHOLE TOOL_REGISTRY because the mode is null.
async def test_system_prompt_and_whole_registry_offered__DoD11(
    db: DbConfig, monkeypatch
):
    context = await _context(system_prompt="BOOK_RULES_XYZ")
    fake = _install_client(monkeypatch, _FakeClient(chunks=["ok"]))

    await _run(context, "ask")

    system = fake.call["system"]
    assert BASE_SYSTEM_PROMPT in system
    assert "BOOK_RULES_XYZ" in system

    # The whole registry (null mode) is offered: the tool callable map and the
    # OpenAI tool definitions both cover exactly the registry's tool names.
    registry_names = {t.name for t in TOOL_REGISTRY}
    assert set(fake.call["tools"].keys()) == registry_names
    assert len(fake.call["tools_definitions"]) == len(TOOL_REGISTRY)
    assert "web_search" in fake.call["tools"]
