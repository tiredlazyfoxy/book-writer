"""Sub-agent delegation — a mode's allowed sub-agents as **synthetic tools**
(feature 013, step 008).

Business-logic layer: **no** ``session`` / ``AsyncSession`` / ``select()`` /
``session.exec()`` / ``session.add()`` here (``docs/architecture/backend.md`` —
layer separation). Everything is read through the session-free ``app.db``
modules the FEAT-020 tables already ship (:mod:`app.db.mode_subagents`,
:mod:`app.db.sub_agents`, :mod:`app.db.subagent_tools`,
:mod:`app.db.llm_servers`). **``services/assistant_config.py`` is never
imported** — the runtime reads the FEAT-020 ``db/`` modules directly
(``013.codex/context.md``), and no db helper is added by this step.

What this module is (``assistant-config.md`` → "Sub-agent delegation"):

- :func:`build_delegation_tools` turns a mode's ``mode_subagent`` rows into one
  :class:`~app.services.tools.ToolDef` per **invokable** (non-``disabled``)
  sub-agent, which :func:`app.services.assistant_runtime.resolve_turn_tools`
  hands to ``build_tool_bindings`` **together with** the real ``TOOL_REGISTRY``
  tools — one combined list, so the two maps the ``llm`` client pre-flights
  always carry identical key sets;
- :func:`run_delegation` is what one such tool *does*: a nested, bounded
  ``chat_with_tools`` for that one sub-agent, with its own ``system_prompt``
  **alone**, its own ``subagent_tool`` allowlist resolved against
  ``TOOL_REGISTRY``, its own (or the parent's) model, and
  :data:`SUBAGENT_MAX_LOOPS` rounds.

Three constraints shape every signature here:

1. **No per-request context argument.** The ``llm`` client decodes a tool call's
   JSON arguments and applies them as ``func(**kwargs)``, validated against
   ``inspect.signature(func).parameters``. A tool callable therefore accepts
   **exactly** the ``args_schema`` field names as keyword parameters and nothing
   else — so everything a delegation needs (the sub-agent row, the parent turn's
   server / key / model) is bound with ``functools.partial`` at build time.
   :func:`run_delegation` takes those two **positionally first**, precisely so
   ``functools.partial(run_delegation, sub_agent, parent)`` leaves ``task`` — the
   single :class:`DelegationArgs` field — as the only free parameter.
2. **A tool that raises aborts the whole parent loop** (the client wraps it as
   ``RuntimeError``) and the error is never fed back to the model. So
   :func:`run_delegation` **never raises**: every failure — an unusable server
   assignment, an unreachable model, an exhausted nested loop — returns a short
   error string, exactly as ``services/web_search.py:web_search`` does.
3. **Delegation is one level deep by construction.** There is no
   ``subagent_subagent`` table: modes select sub-agents, sub-agents select
   **tools only**. The nested call's tool list comes from ``subagent_tool`` rows
   resolved against ``TOOL_REGISTRY`` and nothing else can enter it — a synthetic
   delegation tool is never passed into a nested call.

:class:`ParentTurn`, :data:`SUBAGENT_MAX_LOOPS`, :data:`DELEGATION_TOOL_PREFIX`
and :class:`DelegationArgs` are the frozen declarative contract (013 step 008);
:func:`delegation_tool_name`, :func:`build_delegation_tools` and
:func:`run_delegation` are its behaviour.
"""

import functools
import logging
import re
from dataclasses import dataclass

from pydantic import BaseModel, Field

from app.db import llm_servers as llm_servers_db
from app.db import mode_subagents, sub_agents, subagent_tools
from app.models.llm_server import LlmServer
from app.models.sub_agent import SubAgent
from app.services import llm_servers as llm_servers_service
from app.services import secrets
from app.services.tools import (
    TOOL_REGISTRY,
    ToolContext,
    ToolDef,
    build_tool_bindings,
)

logger = logging.getLogger(__name__)


# The **nested** loop bound: how many tool-call rounds one delegated sub-agent
# turn may take. Deliberately its own constant, separate from
# ``chat_turn.MAX_LOOPS`` (the parent turn's bound), so tuning the parent's loop
# never silently changes delegation depth — and so an exhausted nested loop
# (which the ``llm`` client raises as ``RuntimeError``) is a visible, named bound
# rather than a magic literal at the nested call site. A delegated task is
# narrower than a parent turn, hence the smaller number.
SUBAGENT_MAX_LOOPS = 3

# The fixed prefix every derived delegation tool name carries, marking it as a
# delegation rather than a code-defined ``TOOL_REGISTRY`` entry. Frozen so a
# caller can tell the two apart without a lookup.
DELEGATION_TOOL_PREFIX = "ask_"

# Tool-name sanitising: every run of characters outside ``[a-z0-9]`` (measured on
# the lowercased name, so anything non-ASCII collapses too) becomes a single
# ``_``, and the whole derived name is kept inside the conventional
# ``^[a-zA-Z0-9_-]{1,64}$`` shape.
_NON_ALNUM_RUN = re.compile(r"[^a-z0-9]+")
_MAX_TOOL_NAME_CHARS = 64

# The failure strings :func:`run_delegation` returns to the parent loop instead
# of raising — the model reads them as the tool's result. Deliberately short and
# free of internals: a resolved api key, a provider payload or a stack detail
# must never reach the model (the ``services/web_search.py`` contract).
_UNUSABLE_MODEL_MESSAGE = (
    "Delegation error: the sub-agent '{name}' has no usable model configured."
)
_DELEGATION_FAILED_MESSAGE = (
    "Delegation error: the sub-agent '{name}' could not complete the task."
)


@dataclass(frozen=True)
class ParentTurn:
    """What a delegation needs from the turn it is nested inside.

    A frozen typed record (the ``services/tools.py:ToolDef`` /
    ``services/assistant_runtime.py:ResolvedSubject`` precedent — no free
    dictionaries). Built once per turn by ``services/chat_turn.py:run_turn`` from
    the already-resolved :class:`~app.services.chat_turn.TurnContext`, and bound
    into every synthetic tool's callable:

    - ``server`` — the parent turn's active
      :class:`~app.models.llm_server.LlmServer`;
    - ``resolved_key`` — its api key with the ``$ENV`` indirection **already
      resolved** (``None`` when the server carries no key). Resolved once,
      before the stream opened, exactly as the parent's own client was;
    - ``model`` — the parent chat's model name.

    The first three fields are precisely
    :func:`app.services.llm_servers.create_model_client`'s arguments, because
    that is what they are for: a sub-agent whose ``(llm_server_id, model_name)``
    assignment is **null** inherits the parent's server, key and model
    (US-113.AC-6).

    - ``tool_context`` — the parent turn's
      :class:`~app.services.tools.ToolContext` (013 step 010). A sub-agent binds
      its **own** ``subagent_tool`` allowlist, and a *bound* registry entry
      (``codex_search`` / ``codex_read_entry`` / ``write_codex_draft``) can only
      be built when a context is available: without this field
      :func:`build_tool_bindings` skips them and a sub-agent silently loses a
      tool its configuration selects — the consequence 013 step 009 flagged for
      "wherever ``ToolContext`` next changes". **Defaulted**, so every existing
      ``ParentTurn(server=…, resolved_key=…, model=…)`` construction keeps
      binding and keeps its current meaning (no context ⇒ bound tools skipped,
      exactly as before).
    """

    server: LlmServer
    resolved_key: str | None
    model: str
    tool_context: ToolContext | None = None


# Arguments for every synthetic delegation tool. The class docstring below is
# **model-facing** — ``llm.pydantic_to_openai_tool`` copies it into the JSON
# schema's ``description`` — so the engineering notes live here instead:
#
# - the field name is load-bearing twice over (the ``models/schemas/tools.py``
#   rule): it is the JSON-schema property name the model sees *and* it must be
#   exactly the free keyword parameter of the bound callable, i.e.
#   ``functools.partial(run_delegation, sub_agent, parent)(task=...)``;
# - it lives in this module rather than ``models/schemas/tools.py`` because that
#   module is outside this step's Source files; it is a declarative Pydantic
#   schema either way, and it is the only tool-argument shape the delegation half
#   of this feature owns.
class DelegationArgs(BaseModel):
    """Arguments for delegating one task to a sub-agent.

    The caller describes *what it wants done*; the sub-agent's own configured
    instructions supply *how*.
    """

    task: str = Field(
        description=(
            "The task to hand to the sub-agent, described in plain language."
        )
    )


def delegation_tool_name(sub_agent_name: str) -> str:
    """Derive a stable, model-safe tool name from a sub-agent's ``name``.

    A ``SubAgent.name`` is a free admin-entered string, while tool names are
    conventionally ``^[a-zA-Z0-9_-]{1,64}$`` — so the name is **sanitised, not
    passed through**: lowercased, runs of non-alphanumeric characters collapsed,
    and :data:`DELEGATION_TOOL_PREFIX` prepended. Deriving rather than storing
    keeps :class:`~app.models.sub_agent.SubAgent` unchanged (no column, no
    codec, no feature-012 coordination) at the cost of possible collisions —
    which :func:`build_delegation_tools` makes explicit and observable rather
    than silent.

    Pure and deterministic: the same name always derives to the same tool name.
    ``"Continuity Checker"`` → ``"ask_continuity_checker"``.
    """
    slug = _NON_ALNUM_RUN.sub("_", sub_agent_name.lower()).strip("_")
    # Truncated (never rejected): an over-long admin name still yields a usable
    # tool name, and the truncation is deterministic, so two names that truncate
    # alike collide visibly through :func:`build_delegation_tools`' guard rather
    # than silently overwriting each other.
    return f"{DELEGATION_TOOL_PREFIX}{slug}"[:_MAX_TOOL_NAME_CHARS]


async def build_delegation_tools(
    mode_key: str | None, parent: ParentTurn
) -> list[ToolDef]:
    """Build the synthetic delegation tools for ``mode_key``.

    One :class:`~app.services.tools.ToolDef` per **invokable** sub-agent
    (US-112.AC-3):

    - reads the mode's ``mode_subagent`` rows (``db/mode_subagents.list_by_mode``)
      and loads each :class:`~app.models.sub_agent.SubAgent` by id
      (``db/sub_agents.get_by_id``) — a sub-agent outside the mode's set is never
      built and therefore cannot be invoked;
    - **excludes ``disabled`` sub-agents** — both because their links should
      already have been removed and because a stale link row must not become a
      hole (``assistant-config.md``); a link pointing at no row at all is skipped
      the same way;
    - names each tool via :func:`delegation_tool_name`, with a **collision
      guard**: a derived name that collides with a real ``TOOL_REGISTRY`` name,
      or with an earlier synthetic name in the same build, is **skipped and
      logged** — the code-defined registry is the source of truth and always
      wins;
    - gives each tool :class:`DelegationArgs` as its ``args_schema`` and a
      description that **carries the sub-agent's name verbatim**, so the model
      can choose between several sensibly;
    - binds ``parent`` and the sub-agent row into the callable
      (``functools.partial(run_delegation, sub_agent, parent)``), because the
      ``llm`` client passes no context argument.

    With **no** mode there are no synthetic tools at all — delegation is a mode
    concept (``assistant-config.md``). The result is concatenated with the real
    resolved tools by
    :func:`app.services.assistant_runtime.resolve_turn_tools` and the combined
    list is handed to ``build_tool_bindings`` in one call, so the client's
    pre-flight ("every ``tools_definitions`` name has a ``tools`` key") can never
    fail on a synthetic name.

    """
    if mode_key is None:
        # Delegation is a mode concept: no mode, no synthetic tools.
        return []
    links = await mode_subagents.list_by_mode(mode_key)
    if not links:
        # A mode that selected no sub-agent delegates to nothing.
        return []

    registry_names = {tool.name for tool in TOOL_REGISTRY}
    built: list[ToolDef] = []
    taken: set[str] = set()
    for link in links:
        sub_agent = await sub_agents.get_by_id(link.sub_agent_id)
        if sub_agent is None:
            # A link pointing at no row at all — the same "a stale row must not
            # become a hole" case as a disabled one.
            logger.warning(
                "build_delegation_tools: mode %r links sub-agent %s, which does "
                "not exist — skipped",
                mode_key,
                link.sub_agent_id,
            )
            continue
        if sub_agent.disabled:
            # A disabled sub-agent is invokable through neither its (deleted)
            # links nor a stale reference (US-114.AC-2).
            logger.warning(
                "build_delegation_tools: mode %r links disabled sub-agent %r — "
                "skipped",
                mode_key,
                sub_agent.name,
            )
            continue
        name = delegation_tool_name(sub_agent.name)
        if name in registry_names:
            # The code-defined registry is the source of truth and always wins.
            logger.warning(
                "build_delegation_tools: sub-agent %r derives tool name %r, "
                "which is a real TOOL_REGISTRY tool — skipped",
                sub_agent.name,
                name,
            )
            continue
        if name in taken:
            logger.warning(
                "build_delegation_tools: sub-agent %r derives tool name %r, "
                "already taken by an earlier sub-agent of mode %r — skipped",
                sub_agent.name,
                name,
                mode_key,
            )
            continue
        taken.add(name)
        built.append(
            ToolDef(
                name=name,
                description=(
                    f"Delegate one task to the sub-agent \"{sub_agent.name}\" "
                    f"and return its answer. Describe what you want done; "
                    f"{sub_agent.name} works from its own configured "
                    f"instructions."
                ),
                args_schema=DelegationArgs,
                # ``sub_agent`` and ``parent`` are bound here because the ``llm``
                # client dispatches ``func(**kwargs)`` with no context argument;
                # ``task`` stays the single free parameter.
                callable=functools.partial(run_delegation, sub_agent, parent),
            )
        )
    return built


async def run_delegation(sub_agent: SubAgent, parent: ParentTurn, task: str) -> str:
    """Run one sub-agent's nested turn for ``task`` and return its final text.

    The body of every synthetic delegation tool. ``sub_agent`` and ``parent`` are
    **bound at build time** (``functools.partial``), leaving ``task`` — the one
    :class:`DelegationArgs` field — as the only argument the model supplies.

    What it does (``assistant-config.md`` → "Sub-agent delegation" / "Model
    resolution"):

    1. resolves the sub-agent's tool allowlist from its ``subagent_tool`` rows
       (``db/subagent_tools.list_by_sub_agent``) against ``TOOL_REGISTRY`` —
       **tools only, never another sub-agent**, so the nested loop cannot itself
       delegate; a row naming a tool absent from the registry is skipped and
       logged;
    2. resolves the model: the sub-agent's own ``(llm_server_id, model_name)``
       when **both** are set — the server read through ``db/llm_servers.get_by_id``
       and its api key resolved at use time through
       ``services/secrets.py:resolve_env_ref`` — otherwise the parent's
       ``server`` / ``resolved_key`` / ``model`` (US-113.AC-6);
    3. constructs the client through
       :func:`app.services.llm_servers.create_model_client` (never the frozen
       ``_create_client`` test seam, which is bound to ``model=""``), entered as
       an ``async with`` so its session closes on every path — **one client per
       delegation**, not cached (``context.md``: ``LLMClient`` has no standalone
       ``close()``, so a cache would have to own client lifetimes across a whole
       turn);
    4. calls ``chat_with_tools`` with the sub-agent's ``system_prompt``
       **alone** — no base, mode, book or chapter composition — the resolved
       tool bindings and :data:`SUBAGENT_MAX_LOOPS`, and returns the final
       string to the parent.

    **It never raises.** Every failure — an unusable or missing server
    assignment, an unset ``$ENV`` key, a transport or LLM error, an exhausted
    nested loop — returns a short error string, because a raising tool is wrapped
    as ``RuntimeError`` by the ``llm`` client and aborts the **parent's** whole
    loop with the error never reaching the model
    (``services/web_search.py:web_search``'s contract, copied exactly). No
    resolved key ever appears in a returned string or a log line.
    """
    try:
        return await _delegate(sub_agent, parent, task)
    except Exception as exc:
        # Deliberately broad, exactly as ``web_search`` is: a transport failure
        # (raw ``aiohttp.ClientError``, never wrapped in ``LLMError``), an
        # ``LLMError``, a tool-binding ``ValueError`` and an exhausted nested loop
        # or raising nested tool (``RuntimeError``) are all recoverable for the
        # PARENT — but a delegation tool that raised would be wrapped as
        # ``RuntimeError`` by the ``llm`` client and abort the parent's whole
        # loop, with the error never reaching the model.
        logger.warning(
            "run_delegation: delegation to sub-agent %r failed: %s: %s",
            sub_agent.name,
            type(exc).__name__,
            exc,
        )
        return _DELEGATION_FAILED_MESSAGE.format(name=sub_agent.name)


async def _delegate(sub_agent: SubAgent, parent: ParentTurn, task: str) -> str:
    """The delegation itself. May raise — :func:`run_delegation` is the guard."""
    # The parent turn's context is passed through so a BOUND registry entry the
    # sub-agent selects can actually be built (013 step 010); with none it is
    # skipped and logged, exactly as before.
    tool_defs, tool_map = build_tool_bindings(
        await _subagent_tools(sub_agent), parent.tool_context
    )
    resolved = await _resolve_model(sub_agent, parent)
    if resolved is None:
        return _UNUSABLE_MODEL_MESSAGE.format(name=sub_agent.name)
    server, resolved_key, model = resolved

    # ONE client per delegation, entered as an ``async with`` so its aiohttp
    # session closes on every path including failure (``LLMClient`` has no
    # standalone ``close()``). Never ``_create_client`` — that seam is bound to
    # ``model=""`` for ``list_models()``.
    async with llm_servers_service.create_model_client(
        server, resolved_key, model
    ) as client:
        return await client.chat_with_tools(
            [{"role": "user", "content": task}],
            tools_definitions=tool_defs,
            tools=tool_map,
            # The sub-agent's own prompt ALONE — no base / mode / book / chapter
            # composition: a sub-agent is a self-contained configured worker
            # (``assistant-config.md`` → "Sub-agent delegation").
            system=sub_agent.system_prompt,
            # The module's OWN bound, independent of ``chat_turn.MAX_LOOPS``.
            max_loops=SUBAGENT_MAX_LOOPS,
        )


async def _subagent_tools(sub_agent: SubAgent) -> list[ToolDef]:
    """Resolve ``sub_agent``'s ``subagent_tool`` rows against ``TOOL_REGISTRY``.

    **Tools only** — the rows can name nothing but registry entries (there is no
    ``subagent_subagent`` table), so no synthetic delegation tool can ever enter
    a nested call and the loop is one level deep by construction. A row naming a
    tool the registry does not define is **skipped and logged**, never an error:
    the code-defined catalogue is the source of truth and a selection may outlive
    a removed tool (``assistant-config.md``).
    """
    rows = await subagent_tools.list_by_sub_agent(sub_agent.id)
    by_name = {tool.name: tool for tool in TOOL_REGISTRY}
    resolved: list[ToolDef] = []
    for row in rows:
        tool = by_name.get(row.tool_name)
        if tool is None:
            logger.warning(
                "run_delegation: sub-agent %r selects tool %r, which has no "
                "TOOL_REGISTRY entry — skipped",
                sub_agent.name,
                row.tool_name,
            )
            continue
        resolved.append(tool)
    return resolved


async def _resolve_model(
    sub_agent: SubAgent, parent: ParentTurn
) -> tuple[LlmServer, str | None, str] | None:
    """Resolve the ``(server, resolved_key, model)`` this delegation runs on.

    The sub-agent's own assignment when **both** ``llm_server_id`` and
    ``model_name`` are set; otherwise the parent turn's server, already-resolved
    key and model (US-113.AC-6). ``None`` — reported to the parent as a short
    error string — when the assigned server no longer exists, is inactive, or
    carries a ``$ENV`` key reference that cannot be resolved (``012``'s accepted
    consequence: a config row may outlive the server it names).
    """
    model_name = (sub_agent.model_name or "").strip()
    if sub_agent.llm_server_id is None or not model_name:
        # A null assignment inherits the parent turn's client parameters.
        return parent.server, parent.resolved_key, parent.model

    server = await llm_servers_db.get_by_id(sub_agent.llm_server_id)
    if server is None or not server.is_active:
        logger.warning(
            "run_delegation: sub-agent %r is assigned server %s, which is "
            "missing or inactive",
            sub_agent.name,
            sub_agent.llm_server_id,
        )
        return None
    try:
        # Resolved at USE time (``services/secrets.py``), exactly as the parent
        # turn's own key was. The resolved value is never logged or returned.
        resolved_key = secrets.resolve_env_ref(server.api_key)
    except Exception as exc:
        # ``LlmServerError(env_not_set)`` and anything else the resolver can
        # raise: an unset ``$ENV`` var is a config problem, not a turn failure.
        logger.warning(
            "run_delegation: sub-agent %r has an unresolvable server credential: "
            "%s",
            sub_agent.name,
            type(exc).__name__,
        )
        return None
    return server, resolved_key, model_name
