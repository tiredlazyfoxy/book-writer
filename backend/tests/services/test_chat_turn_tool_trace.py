"""Tool-call trace: the wrapper's frames + the persisted trace (feature 024).

Covers DoD-1 and DoD-2 of `docs/plans/024.chat-agent-loop/plan.md`.

Bound to the frozen skeleton (`status.md` -> `## Skeleton`):

    app.services.chat_turn:
        def _wrap_tool_with_trace(
            name: str,
            func: Callable[..., object],
            emit_frame: FrameEmitter,
            trace: list[ToolTraceEntry],
        ) -> Callable[..., Awaitable[str]]

    app.models.schemas.chats:
        class ToolCallFrame(BaseModel)   { tool_name; arguments }
        class ToolResultFrame(BaseModel) { tool_name; result; ok }
        class ToolTraceEntry(BaseModel)  { tool_name; arguments; result; ok }
        class ToolTrace(BaseModel)       { entries } + parse_column / to_column

    app.models.chat:
        ChatMessage.tool_trace: str | None

`FrameEmitter = Callable[[str, BaseModel], Awaitable[None]]`
(`app/services/tools.py`), so a frame is emitted as `await emit_frame(event, payload)`
with the event names `tool_call` / `tool_result` (`plan.md` -> Interface,
`context.md` -> "Backend runtime shape").

Expected values come from the SPEC ONLY -- `plan.md` -> Definition of done /
Interface, and `context.md` -> "Standing constraints" ("a tool never raises" must
survive being wrapped) and "Backend runtime shape" -- never from implementation
internals.

DoD-1 is exercised directly against the wrapper (the unit whose contract it is).
DoD-2 is exercised END TO END over the real turn, through the shipped SSE endpoint
(`POST /api/books/{book_id}/chats/{chat_id}/turn`), driven in-process against
`app.main.app` via the `http_client` fixture -- the harness of
`tests/routes/test_chat_turn_canvas.py`, whose fake `LLMClient` INVOKES the tool
callables it was handed. That is what makes the ordering + persistence clause
bite: the trace under assertion is assembled by a real turn, and the column is read
back from the database afterwards.

No network, no live server, no real LLM. `asyncio_mode = "auto"`.
"""

import inspect
import json

import pytest

from app.db import (
    assistant_modes,
    books,
    chat_messages,
    chats,
    codex_entries,
    llm_servers,
    mode_tools,
    users,
)
from app.db.engine import init_db, set_db_ready
from app.models.book import Book, BookState, CollaborationMode, Visibility
from app.models.chat import Chat
from app.models.codex_entry import CodexEntry, CodexKind
from app.models.llm_server import LlmServer
from app.models.mode_tool import ModeTool
from app.models.schemas.chats import (
    ToolCallFrame,
    ToolResultFrame,
    ToolTrace,
    ToolTraceEntry,
)
from app.models.user import User, UserRole
from app.services import auth
from app.services.chat_turn import _wrap_tool_with_trace

# ===========================================================================
# DoD-1 -- the wrapper: a `tool_call` frame before, a `tool_result` frame after,
#          and a raising tool becomes an error string (ok=False), never an
#          exception.
# ===========================================================================


class _Recorder:
    """Records the frames a wrapper emits, in emission order.

    Doubles as the `FrameEmitter` the wrapper is handed: an async callable
    taking `(event, payload)`. `order` interleaves emissions with the wrapped
    call itself, so "before" / "after" is observable rather than inferred.
    """

    def __init__(self, *, fail_on: str | None = None) -> None:
        self.frames: list[tuple[str, object]] = []
        self.order: list[str] = []
        self._fail_on = fail_on

    async def __call__(self, event: str, payload: object) -> None:
        self.order.append(f"emit:{event}")
        if self._fail_on == event:
            raise RuntimeError(f"frame emission failed for {event}")
        self.frames.append((event, payload))

    def events(self) -> list[str]:
        return [event for event, _ in self.frames]

    def payload(self, event: str) -> object:
        matching = [data for name, data in self.frames if name == event]
        assert matching, f"no `{event}` frame was emitted"
        return matching[0]


TOOL_ANSWER = "3 entries matched: Halden, Northgate, the long winter."


def _sync_tool_factory(recorder: _Recorder):
    def tool(**kwargs: object) -> str:
        recorder.order.append("call")
        return TOOL_ANSWER

    return tool


def _async_tool_factory(recorder: _Recorder):
    async def tool(**kwargs: object) -> str:
        recorder.order.append("call")
        return TOOL_ANSWER

    return tool


@pytest.mark.parametrize(
    "factory", [_sync_tool_factory, _async_tool_factory], ids=["sync", "async"]
)
async def test_wrapper_emits_call_before_and_result_after__DoD1(factory):
    # DoD-1: the wrapper emits a `tool_call` frame BEFORE invoking the tool and a
    # `tool_result` frame AFTER it, carrying the tool's name, the call's keyword
    # arguments and the tool's own answer -- for a sync and for an awaitable tool
    # alike (plan.md -> Interface: "awaiting it if awaitable").
    recorder = _Recorder()
    trace: list[ToolTraceEntry] = []
    wrapped = _wrap_tool_with_trace(
        "codex_search", factory(recorder), recorder, trace
    )

    returned = await wrapped(query="Halden", limit=3)

    # The frames bracket the call: emitted before, tool runs, emitted after.
    assert recorder.order == ["emit:tool_call", "call", "emit:tool_result"]
    assert recorder.events() == ["tool_call", "tool_result"]

    call_frame = recorder.payload("tool_call")
    assert isinstance(call_frame, ToolCallFrame)
    assert call_frame.tool_name == "codex_search"
    assert call_frame.arguments == {"query": "Halden", "limit": 3}

    result_frame = recorder.payload("tool_result")
    assert isinstance(result_frame, ToolResultFrame)
    assert result_frame.tool_name == "codex_search"
    assert result_frame.result == TOOL_ANSWER
    assert result_frame.ok is True

    # The tool's own answer is what reaches the caller (the model), unaltered.
    assert returned == TOOL_ANSWER

    # Exactly one trace entry, mirroring the two frames.
    assert len(trace) == 1
    entry = trace[0]
    assert isinstance(entry, ToolTraceEntry)
    assert entry.tool_name == "codex_search"
    assert entry.arguments == {"query": "Halden", "limit": 3}
    assert entry.result == TOOL_ANSWER
    assert entry.ok is True


def _raising_sync(recorder: _Recorder):
    def tool(**kwargs: object) -> str:
        recorder.order.append("call")
        raise RuntimeError("the tool exploded")

    return tool


def _raising_async(recorder: _Recorder):
    async def tool(**kwargs: object) -> str:
        recorder.order.append("call")
        raise ValueError("the async tool exploded")

    return tool


@pytest.mark.parametrize(
    "factory", [_raising_sync, _raising_async], ids=["sync", "async"]
)
async def test_raising_tool_becomes_error_string_not_an_exception__DoD1(factory):
    # DoD-1 (context.md -> "A tool never raises"): a wrapped tool that raises
    # yields an error-string result with ok=False instead of propagating -- the
    # exception never reaches `chat_with_tools`'s dispatch loop, which would abort
    # the whole turn.
    recorder = _Recorder()
    trace: list[ToolTraceEntry] = []
    wrapped = _wrap_tool_with_trace(
        "write_codex_draft", factory(recorder), recorder, trace
    )

    returned = await wrapped(field="body", text="a draft")

    # It returned rather than raised, and what it returned is a non-empty string.
    assert isinstance(returned, str)
    assert returned.strip() != ""

    # Both frames were still emitted, in order, and the result frame says NOT ok.
    assert recorder.events() == ["tool_call", "tool_result"]
    result_frame = recorder.payload("tool_result")
    assert isinstance(result_frame, ToolResultFrame)
    assert result_frame.tool_name == "write_codex_draft"
    assert result_frame.ok is False
    assert isinstance(result_frame.result, str)
    assert result_frame.result.strip() != ""

    # The failure is recorded in the trace as a failed entry, not dropped.
    assert len(trace) == 1
    assert trace[0].tool_name == "write_codex_draft"
    assert trace[0].ok is False
    assert trace[0].result.strip() != ""


@pytest.mark.parametrize("failing_event", ["tool_call", "tool_result"])
async def test_failed_frame_emission_never_propagates__DoD1(failing_event):
    # DoD-1 (plan.md -> Interface: "Catches any exception from `func` **or** from
    # either `emit_frame` call ... never re-raises"): a frame emission that blows
    # up must not escape the wrapper either -- the caller still gets a string back.
    recorder = _Recorder(fail_on=failing_event)
    trace: list[ToolTraceEntry] = []
    wrapped = _wrap_tool_with_trace(
        "web_search", _sync_tool_factory(recorder), recorder, trace
    )

    returned = await wrapped(query="the long winter")

    assert isinstance(returned, str)


# ===========================================================================
# DoD-2 -- ordering across several calls in ONE turn, and the assembled trace
#          persisted onto the assistant ChatMessage (null when no tool ran).
#
# End to end over the real turn, through the shipped SSE endpoint.
# ===========================================================================

DRAFT_ONE = "Halden keeps the north gate through the long winter."
DRAFT_TWO = "Halden keeps the north gate, and has since the siege."


class _ScriptedToolClient:
    """A fake `LLMClient` that invokes a SCRIPTED SEQUENCE of tool calls.

    Streams a prose chunk, then calls each `(tool_name, kwargs)` in `calls` in
    order against the `tools` map it was handed -- i.e. the WRAPPED map -- then
    streams a closing chunk and returns. `invoked` / `results` record what
    actually happened, so a test cannot pass against a turn that never reached a
    tool.
    """

    def __init__(self, calls, *, return_value="Working on it. Done."):
        self._calls = list(calls)
        self._return_value = return_value
        self.tools = None
        self.tool_definition_names: set[str] = set()
        self.invoked: list[str] = []
        self.results: list[str] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def chat_with_tools(
        self, messages, *, tools_definitions=None, tools=None, on_delta=None, **kwargs
    ):
        self.tools = tools
        self.tool_definition_names = {
            d["function"]["name"] for d in (tools_definitions or [])
        }

        async def _drive(chunk: str) -> None:
            if on_delta is None:
                return
            result = on_delta(chunk)
            if inspect.isawaitable(result):
                await result

        await _drive("Working on it. ")

        for name, args in self._calls:
            assert tools is not None and name in tools, (
                f"the turn did not offer `{name}`; offered: "
                f"{sorted(tools or {})}"
            )
            result = tools[name](**args)
            if inspect.isawaitable(result):
                result = await result
            self.invoked.append(name)
            self.results.append(result)

        await _drive("Done.")
        return self._return_value


def _install_client(monkeypatch, fake) -> None:
    def factory(server, resolved_key, model):
        return fake

    monkeypatch.setattr("app.services.llm_servers.create_model_client", factory)
    monkeypatch.setattr(
        "app.services.chat_turn.create_model_client", factory, raising=False
    )


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _seed_author(username: str) -> tuple[User, str]:
    await init_db()
    user = await users.create(
        User(
            username=username,
            role=UserRole.author,
            pwdhash=auth.hash_password("password123"),
            jwt_signing_key=auth.generate_signing_key(),
        )
    )
    set_db_ready(True)
    return user, auth.create_access_token(user)


async def _seed_private_book(owner_id: int) -> Book:
    return await books.create(
        Book(
            title="A Book",
            description="d",
            owner_id=owner_id,
            collaboration_mode=CollaborationMode.free,
            visibility=Visibility.private,
            state=BookState.active,
            system_prompt="",
            active_notes="",
        )
    )


async def _seed_server(*, api_key: str) -> LlmServer:
    return await llm_servers.create(
        LlmServer(
            name="S",
            backend_type="openai",
            base_url="https://api.example.com/v1",
            api_key=api_key,
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


async def _seed_entry(book_id: int, author_id: int) -> CodexEntry:
    return await codex_entries.create(
        CodexEntry(
            book_id=book_id,
            kind=CodexKind.character,
            name="Halden",
            body="the original body",
            archived=False,
            author_id=author_id,
        )
    )


async def _select_write_tool(mode_key: str = "edit-character") -> None:
    """Give the running mode the `mode_tool` row that unlocks the write tool."""
    await assistant_modes.seed_default_modes()
    await mode_tools.create(ModeTool(mode_key=mode_key, tool_name="write_codex_draft"))


def _parse_sse(body: str) -> list[tuple[str | None, str | None]]:
    """Parse an SSE body into a list of ``(event, data)`` pairs."""
    frames: list[tuple[str | None, str | None]] = []
    for block in body.split("\n\n"):
        if not block.strip():
            continue
        event = None
        data = None
        for line in block.split("\n"):
            if line.startswith("event:"):
                event = line[len("event:"):].strip()
            elif line.startswith("data:"):
                data = line[len("data:"):].strip()
        frames.append((event, data))
    return frames


async def _assistant_message(chat_id: int):
    stored = await chat_messages.list_by_chat_ordered(chat_id)
    assistants = [m for m in stored if m.role == "assistant"]
    assert len(assistants) == 1, f"expected one assistant message, got {len(assistants)}"
    return assistants[0]


async def _run_turn(http_client, monkeypatch, fake, *, env_var: str, username: str):
    """Seed a world, run one real turn against `fake`, return (response, chat)."""
    monkeypatch.setenv(env_var, "resolved-secret")
    author, token = await _seed_author(username)
    book = await _seed_private_book(author.id)
    server = await _seed_server(api_key=f"${env_var}")
    chat = await _seed_chat(book.id, author.id, server.id)
    entry = await _seed_entry(book.id, author.id)
    await _select_write_tool("edit-character")

    _install_client(monkeypatch, fake)

    resp = await http_client.post(
        f"/api/books/{book.id}/chats/{chat.id}/turn",
        headers=_auth_header(token),
        json={
            "prompt": "draft Halden's body twice",
            "subject_kind": "codex-entry",
            "subject_id": str(entry.id),
        },
    )
    assert resp.status_code == 200, resp.text
    return resp, chat


async def test_trace_order_preserved_and_persisted__DoD2(http_client, monkeypatch):
    # DoD-2: two tool calls in ONE turn keep their order -- on the wire (a
    # `tool_call` always followed by its own `tool_result` before the next call,
    # per context.md's sequential-dispatch fact) and in the trace persisted onto
    # the assistant ChatMessage's `tool_trace` column, which reflects exactly what
    # streamed.
    fake = _ScriptedToolClient(
        [
            ("write_codex_draft", {"field": "body", "text": DRAFT_ONE}),
            ("write_codex_draft", {"field": "body", "text": DRAFT_TWO}),
        ]
    )
    resp, chat = await _run_turn(
        http_client, monkeypatch, fake, env_var="TRACE_KEY_1", username="trace_author_1"
    )

    # The turn really reached the tools -- otherwise nothing below would bite.
    assert fake.invoked == ["write_codex_draft", "write_codex_draft"]
    assert all(isinstance(r, str) and r.strip() != "" for r in fake.results)

    frames = _parse_sse(resp.text)
    events = [event for event, _ in frames]
    assert events[-1] == "done"
    assert "error" not in events

    # Strict alternation, in call order: call/result, call/result.
    tool_events = [e for e in events if e in ("tool_call", "tool_result")]
    assert tool_events == ["tool_call", "tool_result", "tool_call", "tool_result"]

    call_payloads = [json.loads(d) for e, d in frames if e == "tool_call"]
    result_payloads = [json.loads(d) for e, d in frames if e == "tool_result"]
    assert [p["tool_name"] for p in call_payloads] == [
        "write_codex_draft",
        "write_codex_draft",
    ]
    assert [p["arguments"]["text"] for p in call_payloads] == [DRAFT_ONE, DRAFT_TWO]
    assert [p["ok"] for p in result_payloads] == [True, True]
    assert [p["result"] for p in result_payloads] == fake.results

    # The persisted column carries the same trace, in the same order.
    assistant = await _assistant_message(chat.id)
    assert assistant.tool_trace is not None
    entries = ToolTrace.parse_column(assistant.tool_trace)
    assert entries is not None
    assert len(entries) == 2
    assert [e.tool_name for e in entries] == ["write_codex_draft", "write_codex_draft"]
    assert [e.arguments["text"] for e in entries] == [DRAFT_ONE, DRAFT_TWO]
    assert [e.arguments["field"] for e in entries] == ["body", "body"]
    assert [e.result for e in entries] == fake.results
    assert [e.ok for e in entries] == [True, True]


async def test_trace_is_null_when_no_tool_ran__DoD2(http_client, monkeypatch):
    # DoD-2: a turn during which no tool ran persists `tool_trace` as NULL -- not
    # an empty list, not an empty string.
    fake = _ScriptedToolClient([])
    resp, chat = await _run_turn(
        http_client, monkeypatch, fake, env_var="TRACE_KEY_2", username="trace_author_2"
    )

    assert fake.invoked == []
    events = [event for event, _ in _parse_sse(resp.text)]
    assert events[-1] == "done"
    assert "tool_call" not in events
    assert "tool_result" not in events

    assistant = await _assistant_message(chat.id)
    assert assistant.tool_trace is None
    assert ToolTrace.parse_column(assistant.tool_trace) is None
