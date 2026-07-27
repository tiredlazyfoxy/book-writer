"""Tests for sub-agent delegation as synthetic tools (feature 013, step 008).

Bound to the frozen skeleton (``status.md`` -> ``## Skeleton`` -> Step 008), in
``app.services.subagent_delegation``::

    SUBAGENT_MAX_LOOPS = 3
    DELEGATION_TOOL_PREFIX = "ask_"
    @dataclass(frozen=True) class ParentTurn {
        server: LlmServer; resolved_key: str | None; model: str }
    class DelegationArgs(BaseModel) { task: str }
    def delegation_tool_name(sub_agent_name: str) -> str
    async def build_delegation_tools(mode_key: str | None,
                                     parent: ParentTurn) -> list[ToolDef]
    async def run_delegation(sub_agent: SubAgent, parent: ParentTurn,
                             task: str) -> str

in ``app.services.assistant_runtime``::

    async def resolve_turn_tools(mode_key: str | None,
                                 parent: ParentTurn) -> list[ToolDef]

and in ``app.services.chat_turn`` (unchanged step-007 signatures)::

    @dataclass(frozen=True) class TurnContext { chat, server, resolved_key,
        subject: ResolvedSubject = NO_SUBJECT }
    async def run_turn(context, prompt) -> AsyncGenerator[TurnFrame, None]

No network: the client-construction seam
``app.services.llm_servers.create_model_client`` is monkeypatched with a factory
recording its ``(server, resolved_key, model)`` arguments and yielding a fake
async-context-manager client whose ``chat_with_tools`` kwargs, ``__aenter__`` and
``__aexit__`` are all observable -- the shape features 011 / 013-step-007 already
use. ``TOOL_REGISTRY`` holds only ``web_search`` today, so the tests that need a
second (or a deliberately colliding) catalogue entry monkeypatch the registry --
both in ``app.services.tools`` and in ``app.services.subagent_delegation``, which
imports the name directly.

Rows are seeded through the ``db/`` layer against the real temp-SQLite ``db``
fixture; ``asyncio_mode = "auto"``.

Expected values come from the SPEC ONLY -- ``008.subagent-delegation.md``'s
DoD-1..DoD-15 and Interface intent, ``008.context.md`` and ``context.md`` --
never from implementation internals. DoD-16 is ``[manual/live]``: no test.
"""

import inspect
import logging

import aiohttp
import pytest
from llm import LLMError
from pydantic import BaseModel

from app.db import (
    assistant_modes,
    books,
    chats,
    llm_servers,
    mode_subagents,
    mode_tools,
    sub_agents,
    subagent_tools,
    users,
)
from app.db.engine import DbConfig
from app.models.assistant_mode import AssistantMode
from app.models.book import Book, BookState, CollaborationMode, Visibility
from app.models.chat import Chat
from app.models.llm_server import LlmServer
from app.models.mode_subagent import ModeSubagent
from app.models.mode_tool import ModeTool
from app.models.sub_agent import SubAgent
from app.models.subagent_tool import SubagentTool
from app.models.user import User, UserRole
from app.services import assistant_runtime, chat_turn, subagent_delegation
from app.services import tools as tools_module
from app.services.assistant_runtime import BASE_TOOL_NAMES, ResolvedSubject
from app.services.chat_turn import TurnContext
from app.services.subagent_delegation import (
    DELEGATION_TOOL_PREFIX,
    SUBAGENT_MAX_LOOPS,
    ParentTurn,
    build_delegation_tools,
    delegation_tool_name,
)
from app.services.tools import ToolDef, build_tool_bindings

# The nested call's scripted final string. A delegation that succeeds returns
# exactly this to the parent; every error path must return something else.
NESTED_ANSWER = "NESTED_SUBAGENT_ANSWER"

# The parent turn's inherited triple (US-113.AC-6).
PARENT_KEY = "PARENT_RESOLVED_KEY"
PARENT_MODEL = "parent-model"

# An id no LlmServer row carries.
MISSING_SERVER_ID = 424242424242


# ---------------------------------------------------------------------------
# The fake LLM client + the recording construction seam.
# ---------------------------------------------------------------------------


class _FakeClient:
    """A stand-in for ``llm.LLMClient`` used as an async context manager.

    Records every ``chat_with_tools`` call's kwargs and counts context-manager
    entries / exits, so "entered as ``async with`` and exited on every path"
    (DoD-15) is observable.
    """

    def __init__(self, *, result: str = NESTED_ANSWER, exc=None, chunks=None):
        self._result = result
        self._exc = exc
        self._chunks = list(chunks or [])
        self.calls: list[dict] = []
        self.entered = 0
        self.exited = 0

    async def __aenter__(self):
        self.entered += 1
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.exited += 1
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
        self.calls.append(
            {
                "messages": messages,
                "tools_definitions": tools_definitions,
                "tools": tools,
                "system": system,
                "max_loops": max_loops,
                "options": options,
            }
        )
        if on_delta is not None:
            for chunk in self._chunks:
                result = on_delta(chunk)
                if inspect.isawaitable(result):
                    await result
        if self._exc is not None:
            raise self._exc
        return self._result


class _FactoryCall:
    """One recorded ``create_model_client(server, resolved_key, model)`` call."""

    def __init__(self, server, resolved_key, model):
        self.server = server
        self.resolved_key = resolved_key
        self.model = model


class _ClientFactory:
    """The monkeypatched ``create_model_client``.

    Records its arguments and hands back a **fresh** ``_FakeClient`` per call, so
    "one client per delegation" (DoD-15) is observable.
    """

    def __init__(self, *, result: str = NESTED_ANSWER, exc=None, chunks=None,
                 factory_exc=None):
        self._result = result
        self._exc = exc
        self._chunks = chunks
        self._factory_exc = factory_exc
        self.calls: list[_FactoryCall] = []
        self.clients: list[_FakeClient] = []

    def __call__(self, server, resolved_key, model):
        self.calls.append(_FactoryCall(server, resolved_key, model))
        if self._factory_exc is not None:
            raise self._factory_exc
        client = _FakeClient(result=self._result, exc=self._exc, chunks=self._chunks)
        self.clients.append(client)
        return client


def _install_factory(monkeypatch, factory: _ClientFactory) -> _ClientFactory:
    """Patch the frozen construction seam (``008.context.md`` -> Model
    construction: delegation goes through ``create_model_client``)."""
    monkeypatch.setattr("app.services.llm_servers.create_model_client", factory)
    monkeypatch.setattr(
        "app.services.chat_turn.create_model_client", factory, raising=False
    )
    return factory


# ---------------------------------------------------------------------------
# Extra registry entries. TOOL_REGISTRY holds only ``web_search`` today, so a
# second entry is needed wherever exclusion must be demonstrated, and an
# ``ask_``-named entry wherever a real/synthetic name collision must be.
# ---------------------------------------------------------------------------


class _NoteArgs(BaseModel):
    text: str


def _note_tool(text: str) -> str:
    return f"noted: {text}"


_NOTE_TOOL = ToolDef(
    name="note_tool",
    description="Record a short note for the author.",
    args_schema=_NoteArgs,
    callable=_note_tool,
)


class _ExpertArgs(BaseModel):
    question: str


def _expert_tool(question: str) -> str:
    return f"expert: {question}"


# A REAL registry tool whose name is exactly what the sub-agent named "Expert"
# derives to. The registry is the code-defined source of truth, so this one wins.
_COLLIDING_TOOL = ToolDef(
    name="ask_expert",
    description="A real, code-defined registry tool.",
    args_schema=_ExpertArgs,
    callable=_expert_tool,
)


def _widen_registry(monkeypatch, *extra: ToolDef) -> None:
    widened = [*tools_module.TOOL_REGISTRY, *extra]
    monkeypatch.setattr(tools_module, "TOOL_REGISTRY", widened)
    monkeypatch.setattr(subagent_delegation, "TOOL_REGISTRY", widened, raising=False)


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


async def _seed_server(name: str = "S") -> LlmServer:
    return await llm_servers.create(
        LlmServer(
            name=name,
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


async def _seed_sub_agent(
    name: str,
    *,
    system_prompt: str = "SUBAGENT_ONLY_PROMPT",
    disabled: bool = False,
    llm_server_id: int | None = None,
    model_name: str | None = None,
) -> SubAgent:
    return await sub_agents.create(
        SubAgent(
            name=name,
            system_prompt=system_prompt,
            disabled=disabled,
            llm_server_id=llm_server_id,
            model_name=model_name,
        )
    )


async def _link_sub_agent(mode_key: str, sub_agent_id: int) -> ModeSubagent:
    return await mode_subagents.create(
        ModeSubagent(mode_key=mode_key, sub_agent_id=sub_agent_id)
    )


async def _select_tool(sub_agent_id: int, tool_name: str) -> SubagentTool:
    return await subagent_tools.create(
        SubagentTool(sub_agent_id=sub_agent_id, tool_name=tool_name)
    )


async def _parent_turn(server_name: str = "parent-server") -> ParentTurn:
    """The parent-turn value a delegation may inherit from."""
    server = await _seed_server(server_name)
    return ParentTurn(server=server, resolved_key=PARENT_KEY, model=PARENT_MODEL)


async def _turn_context(
    *,
    subject: ResolvedSubject | None = None,
    book_prompt: str = "",
) -> TurnContext:
    """Seed a full world and build a ``TurnContext`` directly (step 007's shape)."""
    user = await _seed_user()
    book = await _seed_book(user.id, system_prompt=book_prompt)
    server = await _seed_server()
    chat = await _seed_chat(book.id, user.id, server.id)
    if subject is None:
        return TurnContext(chat=chat, server=server, resolved_key="resolved-secret")
    return TurnContext(
        chat=chat, server=server, resolved_key="resolved-secret", subject=subject
    )


async def _run(context: TurnContext, prompt: str | None = "ask"):
    return [frame async for frame in chat_turn.run_turn(context, prompt)]


def _names(tools: list[ToolDef]) -> set[str]:
    return {tool.name for tool in tools}


def _definition_names(definitions) -> set[str]:
    """The tool names carried by ``llm.pydantic_to_openai_tool`` definitions."""
    return {definition["function"]["name"] for definition in definitions}


def _app_warnings(caplog) -> list[str]:
    return [
        record.getMessage()
        for record in caplog.records
        if record.name.startswith("app.")
    ]


def _find(tools: list[ToolDef], name: str) -> list[ToolDef]:
    return [tool for tool in tools if tool.name == name]


# ---------------------------------------------------------------------------
# DoD-1 — synthetic tools land in the SAME definitions and callable maps
# ---------------------------------------------------------------------------


# DoD-1 (US-112.AC-3; the `llm` client's pre-flight): a mode's non-disabled
# sub-agents appear as synthetic tools in the same definitions and callable maps
# as the real registry tools, and every definition name has a matching callable
# key -- a mismatch makes the client raise ValueError at pre-flight.
async def test_synthetic_tools_share_the_real_tool_maps__DoD1_US112_AC3(
    db: DbConfig, monkeypatch
):
    await _seed_mode("edit-character", "MODE_RULES")
    await _seed_mode_tool("edit-character", "web_search")
    agent = await _seed_sub_agent("Continuity Checker")
    await _link_sub_agent("edit-character", agent.id)
    parent = await _parent_turn()

    combined = await assistant_runtime.resolve_turn_tools("edit-character", parent)

    assert _names(combined) == {"web_search", "ask_continuity_checker"}

    definitions, bindings = build_tool_bindings(combined)

    # One pair of maps, built together, with identical key sets.
    assert _definition_names(definitions) == {"web_search", "ask_continuity_checker"}
    assert set(bindings.keys()) == _definition_names(definitions)
    for name in _definition_names(definitions):
        assert name in bindings

    synthetic = _find(combined, "ask_continuity_checker")[0]
    # The description names the sub-agent so the model can choose sensibly.
    assert "Continuity Checker" in synthetic.description
    assert synthetic.args_schema is subagent_delegation.DelegationArgs
    # `task` is the single free keyword parameter -- the `llm` client dispatches
    # func(**kwargs) validated against inspect.signature.
    assert set(inspect.signature(synthetic.callable).parameters) == {"task"}
    assert set(subagent_delegation.DelegationArgs.model_fields) == {"task"}


# DoD-1 (US-112.AC-3): the same is true of a live turn -- the parent's
# `chat_with_tools` receives one tools_definitions / tools pair holding both the
# real and the synthetic tool.
async def test_turn_offers_real_and_synthetic_together__DoD1_US112_AC3(
    db: DbConfig, monkeypatch
):
    await _seed_mode("edit-character", "MODE_RULES")
    await _seed_mode_tool("edit-character", "web_search")
    agent = await _seed_sub_agent("Continuity Checker")
    await _link_sub_agent("edit-character", agent.id)
    context = await _turn_context(
        subject=ResolvedSubject(kind="codex-entry", mode_key="edit-character")
    )
    factory = _install_factory(monkeypatch, _ClientFactory(chunks=["ok"]))

    frames = await _run(context)

    assert frames[-1].event == "done"
    call = factory.clients[0].calls[0]
    assert set(call["tools"].keys()) == {"web_search", "ask_continuity_checker"}
    assert _definition_names(call["tools_definitions"]) == set(call["tools"].keys())


# ---------------------------------------------------------------------------
# DoD-2 — a disabled sub-agent is excluded even with a stale link row
# ---------------------------------------------------------------------------


# DoD-2 (US-114.AC-2): a `disabled` sub-agent is excluded even when a stale
# mode_subagent row still references it -- observed against a NON-EMPTY build, so
# the exclusion cannot pass by an empty list.
async def test_disabled_subagent_is_excluded__DoD2_US114_AC2(db: DbConfig):
    await _seed_mode("edit-character", "MODE_RULES")
    await _seed_mode_tool("edit-character", "web_search")
    live = await _seed_sub_agent("Helper One")
    ghost = await _seed_sub_agent("Ghost Agent", disabled=True)
    await _link_sub_agent("edit-character", live.id)
    # The stale link row: still present, pointing at a disabled sub-agent.
    await _link_sub_agent("edit-character", ghost.id)
    parent = await _parent_turn()

    built = await build_delegation_tools("edit-character", parent)

    # The enabled sibling IS built; the disabled one is not a hole in it.
    assert _names(built) == {"ask_helper_one"}
    assert "ask_ghost_agent" not in _names(built)

    combined = await assistant_runtime.resolve_turn_tools("edit-character", parent)
    _definitions, bindings = build_tool_bindings(combined)
    assert set(bindings.keys()) == {"web_search", "ask_helper_one"}
    assert "ask_ghost_agent" not in bindings


# ---------------------------------------------------------------------------
# DoD-3 — a sub-agent outside the mode's set is not built and not invokable
# ---------------------------------------------------------------------------


# DoD-3 (US-112.AC-3): a sub-agent that is NOT in the mode's set is not built and
# cannot be invoked -- asserted as the difference against a sibling that IS in it.
async def test_subagent_outside_the_mode_is_not_built__DoD3_US112_AC3(db: DbConfig):
    await _seed_mode("edit-character", "MODE_RULES")
    await _seed_mode("edit-fact", "OTHER_MODE_RULES")
    await _seed_mode_tool("edit-character", "web_search")
    insider = await _seed_sub_agent("Insider")
    outsider = await _seed_sub_agent("Outsider")
    await _link_sub_agent("edit-character", insider.id)
    # Linked to a DIFFERENT mode only.
    await _link_sub_agent("edit-fact", outsider.id)
    parent = await _parent_turn()

    built = await build_delegation_tools("edit-character", parent)

    assert _names(built) == {"ask_insider"}
    assert "ask_outsider" not in _names(built)

    combined = await assistant_runtime.resolve_turn_tools("edit-character", parent)
    _definitions, bindings = build_tool_bindings(combined)
    # Not in the callable map => the model cannot invoke it.
    assert set(bindings.keys()) == {"web_search", "ask_insider"}
    assert "ask_outsider" not in bindings

    # And the other mode does build it -- the difference is the mode's set alone.
    other = await build_delegation_tools("edit-fact", parent)
    assert _names(other) == {"ask_outsider"}


# ---------------------------------------------------------------------------
# DoD-4 — no mode means no synthetic delegation tools at all
# ---------------------------------------------------------------------------


# DoD-4 (assistant-config.md: delegation is a mode concept): with NO mode no
# synthetic delegation tools are built, even though a mode elsewhere selects a
# sub-agent -- the turn's maps are exactly the BASE_TOOL_NAMES selection.
@pytest.mark.parametrize("subject_kind", ["chats", "book-state"])
async def test_no_mode_builds_no_synthetic_tools__DoD4(
    db: DbConfig, monkeypatch, subject_kind
):
    await _seed_mode("edit-character", "MODE_RULES")
    agent = await _seed_sub_agent("Continuity Checker")
    await _link_sub_agent("edit-character", agent.id)
    parent = await _parent_turn()

    assert await build_delegation_tools(None, parent) == []

    context = await _turn_context(
        subject=ResolvedSubject(kind=subject_kind, mode_key=None)
    )
    factory = _install_factory(monkeypatch, _ClientFactory(chunks=["ok"]))

    frames = await _run(context)

    assert frames[-1].event == "done"
    call = factory.clients[0].calls[0]
    assert set(call["tools"].keys()) == set(BASE_TOOL_NAMES)
    assert _definition_names(call["tools_definitions"]) == set(BASE_TOOL_NAMES)
    assert not [
        name for name in call["tools"] if name.startswith(DELEGATION_TOOL_PREFIX)
    ]


# ---------------------------------------------------------------------------
# DoD-5 — the nested call gets the sub-agent's own system_prompt ALONE
# ---------------------------------------------------------------------------


# DoD-5 (assistant-config.md -> Sub-agent delegation): invoking a synthetic tool
# runs a nested chat_with_tools whose `system` is the sub-agent's own
# system_prompt alone -- the parent's composed base / mode / book prompt does not
# appear in it.
async def test_nested_system_is_the_subagent_prompt_alone__DoD5(
    db: DbConfig, monkeypatch
):
    from app.services.prompt_composition import BASE_SYSTEM_PROMPT

    await _seed_mode("edit-character", "MODE_RULES_ABC")
    agent = await _seed_sub_agent(
        "Continuity Checker", system_prompt="SUBAGENT_RULES_ONLY"
    )
    await _link_sub_agent("edit-character", agent.id)
    parent = await _parent_turn()
    factory = _install_factory(monkeypatch, _ClientFactory())

    built = await build_delegation_tools("edit-character", parent)
    tool = _find(built, "ask_continuity_checker")[0]

    result = await tool.callable(task="check the timeline")

    # The nested call's final string is what the parent gets back.
    assert result == NESTED_ANSWER

    system = factory.clients[0].calls[0]["system"]
    assert system == "SUBAGENT_RULES_ONLY"
    assert BASE_SYSTEM_PROMPT not in (system or "")
    assert "MODE_RULES_ABC" not in (system or "")


# ---------------------------------------------------------------------------
# DoD-6 — the nested tools are the sub-agent's allowlist, never a delegation
# ---------------------------------------------------------------------------


# DoD-6 (structural one-level bound): the nested call's tools are exactly the
# sub-agent's subagent_tool allowlist resolved against TOOL_REGISTRY, and NO
# synthetic delegation tool is ever passed into it.
async def test_nested_tools_are_the_allowlist_without_delegation__DoD6(
    db: DbConfig, monkeypatch
):
    _widen_registry(monkeypatch, _NOTE_TOOL)
    await _seed_mode("edit-character", "MODE_RULES")
    alpha = await _seed_sub_agent("Alpha Agent")
    beta = await _seed_sub_agent("Beta Agent")
    await _link_sub_agent("edit-character", alpha.id)
    await _link_sub_agent("edit-character", beta.id)
    # Alpha selects web_search only -- note_tool exists in the catalogue and must
    # not leak in.
    await _select_tool(alpha.id, "web_search")
    await _select_tool(beta.id, "note_tool")
    parent = await _parent_turn()
    factory = _install_factory(monkeypatch, _ClientFactory())

    built = await build_delegation_tools("edit-character", parent)
    assert _names(built) == {"ask_alpha_agent", "ask_beta_agent"}

    await _find(built, "ask_alpha_agent")[0].callable(task="do the thing")

    call = factory.clients[0].calls[0]
    nested_tools = call["tools"] or {}
    assert set(nested_tools.keys()) == {"web_search"}
    assert _definition_names(call["tools_definitions"] or []) == {"web_search"}
    # Not another sub-agent's selection, and never a delegation tool.
    assert "note_tool" not in nested_tools
    assert "ask_alpha_agent" not in nested_tools
    assert "ask_beta_agent" not in nested_tools
    assert not [
        name for name in nested_tools if name.startswith(DELEGATION_TOOL_PREFIX)
    ]


# ---------------------------------------------------------------------------
# DoD-7 — an unknown subagent_tool name is skipped and logged
# ---------------------------------------------------------------------------


# DoD-7 (assistant-config.md: the catalogue is the source of truth): a
# subagent_tool row naming a tool absent from TOOL_REGISTRY is skipped and
# logged, and the delegation still runs with the remaining tools.
async def test_unknown_subagent_tool_is_skipped_and_logged__DoD7(
    db: DbConfig, monkeypatch, caplog
):
    await _seed_mode("edit-character", "MODE_RULES")
    agent = await _seed_sub_agent("Alpha Agent")
    await _link_sub_agent("edit-character", agent.id)
    await _select_tool(agent.id, "web_search")
    await _select_tool(agent.id, "no_such_tool")
    parent = await _parent_turn()
    factory = _install_factory(monkeypatch, _ClientFactory())

    built = await build_delegation_tools("edit-character", parent)

    with caplog.at_level(logging.DEBUG):
        result = await _find(built, "ask_alpha_agent")[0].callable(task="go")

    assert result == NESTED_ANSWER
    call = factory.clients[0].calls[0]
    assert set((call["tools"] or {}).keys()) == {"web_search"}
    assert "no_such_tool" not in (call["tools"] or {})
    assert any("no_such_tool" in message for message in _app_warnings(caplog))


# ---------------------------------------------------------------------------
# DoD-8 — a fully assigned sub-agent gets its own server and model
# ---------------------------------------------------------------------------


# DoD-8 (US-113.AC-5): a sub-agent with both llm_server_id and model_name set
# gets a client constructed for THAT server and model, through the existing
# construction path (services/llm_servers.py:create_model_client).
async def test_assigned_server_and_model_are_used__DoD8_US113_AC5(
    db: DbConfig, monkeypatch
):
    own_server = await _seed_server("subagent-server")
    await _seed_mode("edit-character", "MODE_RULES")
    agent = await _seed_sub_agent(
        "Alpha Agent", llm_server_id=own_server.id, model_name="sub-model"
    )
    await _link_sub_agent("edit-character", agent.id)
    parent = await _parent_turn()
    factory = _install_factory(monkeypatch, _ClientFactory())

    built = await build_delegation_tools("edit-character", parent)
    result = await _find(built, "ask_alpha_agent")[0].callable(task="go")

    assert result == NESTED_ANSWER
    assert len(factory.calls) == 1
    assert factory.calls[0].server.id == own_server.id
    assert factory.calls[0].model == "sub-model"
    # Explicitly not the parent's assignment.
    assert factory.calls[0].server.id != parent.server.id
    assert factory.calls[0].model != PARENT_MODEL


# ---------------------------------------------------------------------------
# DoD-9 — a null assignment inherits the parent's server, key and model
# ---------------------------------------------------------------------------


# DoD-9 (US-113.AC-6): a sub-agent with a null assignment inherits the parent
# turn's server, resolved key AND model. Interface intent: its own pair is used
# "when both are set, otherwise the parent's".
@pytest.mark.parametrize(
    "assignment",
    ["both_null", "server_only", "model_only"],
)
async def test_null_assignment_inherits_the_parent__DoD9_US113_AC6(
    db: DbConfig, monkeypatch, assignment
):
    spare = await _seed_server("spare-server")
    await _seed_mode("edit-character", "MODE_RULES")
    kwargs: dict = {"llm_server_id": None, "model_name": None}
    if assignment == "server_only":
        kwargs = {"llm_server_id": spare.id, "model_name": None}
    elif assignment == "model_only":
        kwargs = {"llm_server_id": None, "model_name": "sub-model"}
    agent = await _seed_sub_agent("Alpha Agent", **kwargs)
    await _link_sub_agent("edit-character", agent.id)
    parent = await _parent_turn()
    factory = _install_factory(monkeypatch, _ClientFactory())

    built = await build_delegation_tools("edit-character", parent)
    result = await _find(built, "ask_alpha_agent")[0].callable(task="go")

    assert result == NESTED_ANSWER
    assert len(factory.calls) == 1
    assert factory.calls[0].server.id == parent.server.id
    assert factory.calls[0].resolved_key == PARENT_KEY
    assert factory.calls[0].model == PARENT_MODEL


# ---------------------------------------------------------------------------
# DoD-10 — a missing / unusable assigned server returns an error string
# ---------------------------------------------------------------------------


# DoD-10 (012 outcome item 4's accepted consequence): a sub-agent whose assigned
# LlmServer no longer exists returns an error string to the parent rather than
# raising -- no client is constructed at all.
async def test_missing_assigned_server_returns_error_string__DoD10(
    db: DbConfig, monkeypatch
):
    await _seed_mode("edit-character", "MODE_RULES")
    agent = await _seed_sub_agent(
        "Alpha Agent", llm_server_id=MISSING_SERVER_ID, model_name="ghost-model"
    )
    await _link_sub_agent("edit-character", agent.id)
    parent = await _parent_turn()
    factory = _install_factory(monkeypatch, _ClientFactory())

    built = await build_delegation_tools("edit-character", parent)
    # No pytest.raises: a raising tool would abort the whole parent loop.
    result = await _find(built, "ask_alpha_agent")[0].callable(task="go")

    assert isinstance(result, str)
    assert result.strip() != ""
    assert result != NESTED_ANSWER
    assert factory.calls == []


# DoD-10: an assigned server that is unusable (its construction path raises)
# returns an error string too, never a raise.
async def test_unusable_assigned_server_returns_error_string__DoD10(
    db: DbConfig, monkeypatch
):
    broken = await _seed_server("broken-server")
    await _seed_mode("edit-character", "MODE_RULES")
    agent = await _seed_sub_agent(
        "Alpha Agent", llm_server_id=broken.id, model_name="sub-model"
    )
    await _link_sub_agent("edit-character", agent.id)
    parent = await _parent_turn()
    factory = _install_factory(
        monkeypatch, _ClientFactory(factory_exc=ValueError("unusable server"))
    )

    built = await build_delegation_tools("edit-character", parent)
    result = await _find(built, "ask_alpha_agent")[0].callable(task="go")

    assert isinstance(result, str)
    assert result.strip() != ""
    assert result != NESTED_ANSWER
    assert len(factory.calls) == 1


# ---------------------------------------------------------------------------
# DoD-11 — the nested loop bound is the module's OWN constant
# ---------------------------------------------------------------------------


# DoD-11: the nested call is bounded by the module's own loop constant,
# independent of chat_turn.MAX_LOOPS -- asserted against the constant, not a
# literal, and the two constants are distinct so tuning one cannot move the
# other.
async def test_nested_call_uses_its_own_loop_bound__DoD11(db: DbConfig, monkeypatch):
    await _seed_mode("edit-character", "MODE_RULES")
    agent = await _seed_sub_agent("Alpha Agent")
    await _link_sub_agent("edit-character", agent.id)
    parent = await _parent_turn()
    factory = _install_factory(monkeypatch, _ClientFactory())

    built = await build_delegation_tools("edit-character", parent)
    await _find(built, "ask_alpha_agent")[0].callable(task="go")

    assert factory.clients[0].calls[0]["max_loops"] == SUBAGENT_MAX_LOOPS
    assert SUBAGENT_MAX_LOOPS != chat_turn.MAX_LOOPS


# ---------------------------------------------------------------------------
# DoD-12 — a collision with a REAL registry name loses; the real tool survives
# ---------------------------------------------------------------------------


# DoD-12 (the registry is the code-defined source of truth): a synthetic name
# colliding with a real registry tool name is skipped and logged, and the real
# tool survives in the maps.
async def test_registry_name_collision_skips_the_synthetic__DoD12(
    db: DbConfig, monkeypatch, caplog
):
    _widen_registry(monkeypatch, _COLLIDING_TOOL)
    await _seed_mode("edit-character", "MODE_RULES")
    await _seed_mode_tool("edit-character", "web_search")
    await _seed_mode_tool("edit-character", "ask_expert")
    colliding = await _seed_sub_agent("Expert")
    survivor = await _seed_sub_agent("Helper Two")
    await _link_sub_agent("edit-character", colliding.id)
    await _link_sub_agent("edit-character", survivor.id)
    parent = await _parent_turn()

    # The derivation rule is what makes this a collision.
    assert delegation_tool_name("Expert") == "ask_expert"

    with caplog.at_level(logging.DEBUG):
        built = await build_delegation_tools("edit-character", parent)

    assert _names(built) == {"ask_helper_two"}
    assert any(
        "ask_expert" in message or "Expert" in message
        for message in _app_warnings(caplog)
    )

    combined = await assistant_runtime.resolve_turn_tools("edit-character", parent)
    definitions, bindings = build_tool_bindings(combined)

    # The REAL tool survives -- exactly one entry, and it is the registry's.
    assert len(_find(combined, "ask_expert")) == 1
    assert _find(combined, "ask_expert")[0].callable is _expert_tool
    assert bindings["ask_expert"] is _expert_tool
    assert _definition_names(definitions) == {
        "web_search",
        "ask_expert",
        "ask_helper_two",
    }
    assert set(bindings.keys()) == _definition_names(definitions)


# ---------------------------------------------------------------------------
# DoD-13 — two sub-agents deriving to one name produce ONE tool
# ---------------------------------------------------------------------------


# DoD-13: two sub-agents whose names derive to the same tool name produce one
# tool, with the second skipped and logged.
async def test_duplicate_derived_name_builds_one_tool__DoD13(db: DbConfig, caplog):
    await _seed_mode("edit-character", "MODE_RULES")
    first = await _seed_sub_agent("Continuity Checker")
    second = await _seed_sub_agent("continuity  checker")
    solo = await _seed_sub_agent("Solo Agent")
    await _link_sub_agent("edit-character", first.id)
    await _link_sub_agent("edit-character", second.id)
    await _link_sub_agent("edit-character", solo.id)
    parent = await _parent_turn()

    # Both names derive to the same tool name -- that is what collides.
    assert (
        delegation_tool_name("Continuity Checker")
        == delegation_tool_name("continuity  checker")
        == "ask_continuity_checker"
    )

    with caplog.at_level(logging.DEBUG):
        built = await build_delegation_tools("edit-character", parent)

    assert len(_find(built, "ask_continuity_checker")) == 1
    assert _names(built) == {"ask_continuity_checker", "ask_solo_agent"}
    assert len(built) == 2
    assert any(
        "ask_continuity_checker" in message
        or "continuity  checker" in message
        or "Continuity Checker" in message
        for message in _app_warnings(caplog)
    )


# ---------------------------------------------------------------------------
# DoD-14 — every nested failure returns an error string, never a raise
# ---------------------------------------------------------------------------


# DoD-14 (the web_search contract): any failure inside the nested call --
# transport error, LLM error, a raising nested tool (wrapped as RuntimeError) and
# loop exhaustion (also RuntimeError) -- returns an error string to the parent
# loop and never raises.
@pytest.mark.parametrize(
    "exc",
    [
        aiohttp.ClientConnectionError("no route"),
        aiohttp.ClientError("transport failed"),
        LLMError("upstream 500"),
        RuntimeError("max_loops exhausted"),
        RuntimeError("tool 'web_search' raised"),
    ],
    ids=["conn", "transport", "llm", "loop_exhausted", "tool_raised"],
)
async def test_nested_failure_returns_error_string__DoD14(
    db: DbConfig, monkeypatch, exc
):
    await _seed_mode("edit-character", "MODE_RULES")
    agent = await _seed_sub_agent("Alpha Agent")
    await _link_sub_agent("edit-character", agent.id)
    parent = await _parent_turn()
    _install_factory(monkeypatch, _ClientFactory(exc=exc))

    built = await build_delegation_tools("edit-character", parent)
    # No pytest.raises: a raising tool aborts the whole parent loop.
    result = await _find(built, "ask_alpha_agent")[0].callable(task="go")

    assert isinstance(result, str)
    assert result.strip() != ""
    assert result != NESTED_ANSWER


# ---------------------------------------------------------------------------
# DoD-15 — one client per delegation, exited on EVERY path
# ---------------------------------------------------------------------------


# DoD-15 (LLMClient has no standalone close()): the nested client is constructed
# per delegation and exited through its async context manager on the success
# path.
async def test_client_is_entered_and_exited_on_success__DoD15(
    db: DbConfig, monkeypatch
):
    await _seed_mode("edit-character", "MODE_RULES")
    agent = await _seed_sub_agent("Alpha Agent")
    await _link_sub_agent("edit-character", agent.id)
    parent = await _parent_turn()
    factory = _install_factory(monkeypatch, _ClientFactory())

    built = await build_delegation_tools("edit-character", parent)
    tool = _find(built, "ask_alpha_agent")[0]

    assert await tool.callable(task="first") == NESTED_ANSWER

    assert len(factory.clients) == 1
    assert factory.clients[0].entered == 1
    assert factory.clients[0].exited == 1

    # Per delegation: a second invocation constructs a second, distinct client.
    assert await tool.callable(task="second") == NESTED_ANSWER
    assert len(factory.clients) == 2
    assert factory.clients[0] is not factory.clients[1]
    for client in factory.clients:
        assert client.entered == 1
        assert client.exited == 1


# DoD-15: and on the failure path too -- __aexit__ ran even though the nested
# call blew up.
async def test_client_is_exited_on_failure__DoD15(db: DbConfig, monkeypatch):
    await _seed_mode("edit-character", "MODE_RULES")
    agent = await _seed_sub_agent("Alpha Agent")
    await _link_sub_agent("edit-character", agent.id)
    parent = await _parent_turn()
    factory = _install_factory(
        monkeypatch, _ClientFactory(exc=LLMError("upstream 500"))
    )

    built = await build_delegation_tools("edit-character", parent)
    result = await _find(built, "ask_alpha_agent")[0].callable(task="go")

    assert result != NESTED_ANSWER
    assert len(factory.clients) == 1
    assert factory.clients[0].entered == 1
    assert factory.clients[0].exited == 1
