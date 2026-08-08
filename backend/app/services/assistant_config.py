"""Assistant-configuration service — the mode half + the tool catalogue
(step 002) and the sub-agent CRUD half (step 003).

Business-logic layer: **no** ``session`` / ``AsyncSession`` / ``select()`` /
``session.exec()`` / ``session.add()`` here (see ``docs/architecture/backend.md``
— layer separation). Every read and write goes through the session-free
``app.db`` namespace modules (``assistant_modes``, ``mode_tools``,
``mode_subagents``, ``sub_agents``). Domain refusals raise the typed
:class:`AssistantConfigError`, discriminated by :class:`AssistantConfigErrorReason`
so step 005's route maps each case to its HTTP status; the route stays HTTP-only
and 403 keeps coming from ``require_role(admin)`` itself.

This service **stores** configuration; it never runs it. Mode determination,
prompt composition wiring, tool gating and sub-agent delegation are
``013.codex``'s (``context.md`` → "The seam this feature does not touch").

Inbound dependency (``context.md`` → "Inbound dependency"): ``TOOL_REGISTRY`` is
owned by ``services/tools.py`` (feature 011, step 002) and is **read** here —
never defined, extended or re-declared. :func:`resolve_tools` and
:func:`build_tool_bindings` are deliberately **not** called: the former's
skip-and-log treatment of an unknown name is the opposite of what this config
edge needs, and its ``None ⇒ whole registry`` branch is the ``013`` seam.
Membership is checked against ``TOOL_REGISTRY`` directly.

Steps 003 and 004 extend **this same** enum and exception with the sub-agent
reasons — do not add a second error type, and do not narrow the vocabulary to
modes. Step 003 has appended its six reasons below.

The sub-agent model-pair invariant is a **local copy** of
``services/chats.py:142-177 _validate_model_pair`` — same rule set, same order,
this feature's own error enum. It is deliberately **not** imported from
``services/chats.py`` and ``chats.py`` is deliberately **not** refactored to
share one: two services each owning one small invariant is this codebase's
existing shape, and a cross-service private import would couple the author-facing
chat feature to the admin config feature for four lines
(``003.context.md`` → "The model-pair invariant").

Skeleton (012 steps 002, 003, 004): the error taxonomy is frozen and the function
signatures are frozen. Steps 002, 003 and 004 are implemented — step 004 filled
the two replace-set writers and the disable/enable setter, and wired both
selection lists into :func:`create_sub_agent` / :func:`update_sub_agent`.
"""

import enum
import json
from datetime import datetime, timezone

from app.db import (
    assistant_modes,
    llm_servers,
    mode_subagents,
    mode_tools,
    sub_agents,
    subagent_tools,
)
from app.models.assistant_mode import AssistantMode
from app.models.mode_subagent import ModeSubagent
from app.models.mode_tool import ModeTool
from app.models.schemas.assistant_config import (
    AssistantModeResponse,
    AssistantModesListResponse,
    CreateSubAgentRequest,
    SubAgentResponse,
    SubAgentsListResponse,
    ToolResponse,
    ToolsListResponse,
    UpdateAssistantModeRequest,
    UpdateSubAgentRequest,
)
from app.models.sub_agent import SubAgent
from app.models.subagent_tool import SubagentTool
from app.services.tools import TOOL_REGISTRY


class AssistantConfigErrorReason(str, enum.Enum):
    """Discriminator for :class:`AssistantConfigError` — the whole feature's
    refusal taxonomy (modes *and* sub-agents).

    Hyphenated string values, the ``services/llm_servers.py:47`` shape. Step 005's
    route owns the reason → status map: ``mode_not_found`` /
    ``sub_agent_not_found`` → 404, ``name_taken`` → **409** (the
    ``services/admin.py:109-113 username_taken`` precedent), everything else → 400.

    **Open on purpose.** Step 002 introduced the first four members; step 003
    appends the six sub-agent CRUD reasons below. Step 004 adds **no** new member —
    it reuses ``mode_not_found`` for an unknown ``mode_key`` in a sub-agent's mode
    selection, plus the already-defined ``unknown_tool`` / ``sub_agent_disabled`` /
    ``sub_agent_not_found``.
    """

    mode_not_found = "mode-not-found"
    unknown_tool = "unknown-tool"
    unknown_sub_agent = "unknown-sub-agent"
    sub_agent_disabled = "sub-agent-disabled"
    # Step 003 — sub-agent CRUD.
    sub_agent_not_found = "sub-agent-not-found"
    name_taken = "name-taken"
    blank_name = "blank-name"
    invalid_model_pair = "invalid-model-pair"
    unknown_or_inactive_server = "unknown-or-inactive-server"
    model_not_enabled = "model-not-enabled"


class AssistantConfigError(Exception):
    """Raised by the assistant-config service for every domain refusal.

    Carries an :class:`AssistantConfigErrorReason` discriminator (``reason``) plus
    a human-readable ``message``; step 005's route branches on ``reason`` to pick
    the status. Mirrors :class:`app.services.llm_servers.LlmServerError`.

    One exception for the **whole** service surface — steps 003 and 004 reuse it.
    """

    def __init__(self, reason: AssistantConfigErrorReason, message: str = "") -> None:
        self.reason = reason
        self.message = message
        super().__init__(message)


async def list_tools() -> ToolsListResponse:
    """Return the read-only tool catalogue — every ``TOOL_REGISTRY`` entry mapped
    to a ``ToolResponse``, in **registry declaration order** (UC-095 step 3).

    A pure read of a module-level literal: no DB access. ``async`` only for
    consistency with the rest of this service's surface (so step 005's handler
    awaits it like every other call). Must be correct for a registry of zero, one
    or many entries — nothing may hard-code the count (the registry has grown
    since this surface was written and will keep changing).

    Only ``name`` and ``description`` are surfaced; ``args_schema`` and
    ``callable`` never reach the wire, nor does any key derived from them.
    """
    return ToolsListResponse(
        items=[
            ToolResponse(name=tool.name, description=tool.description)
            for tool in TOOL_REGISTRY
        ]
    )


async def _to_mode_response(mode: AssistantMode) -> AssistantModeResponse:
    """Build the :class:`AssistantModeResponse` for one ``AssistantMode`` row.

    Loads the mode's ``mode_tool`` rows (``mode_tools.list_by_mode``) and its
    ``mode_subagent`` rows (``mode_subagents.list_by_mode``) through the ``db``
    namespace modules and hand-maps them into the DTO — never ``model_dump()`` of
    an ORM row (``services/llm_servers.py:80`` precedent). ``sub_agent_id`` is
    stringified; ``key`` is emitted verbatim.

    Internal (leading underscore): used by both :func:`list_modes` and
    :func:`save_mode`. Not part of the tested surface.

    A pure hand-map of the stored link rows: a stored ``tool_name`` is reported as
    selected even if its tool has since left ``TOOL_REGISTRY`` — the read edge does
    not filter against the catalogue (skip-and-log for a retired tool is the
    runtime's job, ``013.codex``; refusing an unknown *new* name is
    :func:`save_mode`'s).
    """
    tool_rows = await mode_tools.list_by_mode(mode.key)
    link_rows = await mode_subagents.list_by_mode(mode.key)
    return AssistantModeResponse(
        key=mode.key,
        system_prompt=mode.system_prompt,
        tool_names=[row.tool_name for row in tool_rows],
        sub_agent_ids=[str(row.sub_agent_id) for row in link_rows],
        created_at=mode.created_at,
        modified_at=mode.modified_at,
    )


async def list_modes() -> AssistantModesListResponse:
    """Return every assistant mode with its current configuration, ordered by
    position in ``db.assistant_modes.DEFAULT_MODE_KEYS`` (UC-095; US-110.AC-1).

    ``assistant_modes.list_all`` is **unordered** (no ``ORDER BY``), so the fixed
    presentation order is imposed here from the imported ``DEFAULT_MODE_KEYS``
    tuple — the five keys are never re-declared in this module or in a DTO.

    A row whose ``key`` is not in ``DEFAULT_MODE_KEYS`` (which seeding cannot
    produce, but a DB import could) sorts **last, by key** — never dropped, never
    raising.
    """
    order = assistant_modes.DEFAULT_MODE_KEYS

    def _position(mode: AssistantMode) -> tuple[int, str]:
        # A known key sorts by its fixed position; anything else lands in one
        # trailing bucket and is ordered by key within it.
        if mode.key in order:
            return (order.index(mode.key), "")
        return (len(order), mode.key)

    rows = sorted(await assistant_modes.list_all(), key=_position)
    return AssistantModesListResponse(
        items=[await _to_mode_response(row) for row in rows]
    )


async def save_mode(
    mode_key: str, req: UpdateAssistantModeRequest
) -> AssistantModeResponse:
    """Full-replace one mode's prompt, tool selection and sub-agent selection, and
    return the freshly rebuilt DTO (UC-095; US-110.AC-1, US-111.AC-1, US-112.AC-1).

    ``mode_key`` is already a string — no conversion. Order of operations, with
    **all validation before any write** so a rejected save leaves the mode's
    stored configuration untouched:

    1. Load the mode (``assistant_modes.get_by_id``); no row →
       ``mode_not_found`` (404).
    2. Every ``req.tool_names`` entry must name a ``TOOL_REGISTRY`` tool; the
       first unknown name → ``unknown_tool`` (400). Refused here even though the
       runtime skips-and-logs (``context.md`` → "Planner-derived decisions").
    3. Every ``req.sub_agent_ids`` entry must parse as an id — a ``ValueError`` /
       ``TypeError`` from ``int(...)`` is caught and reported as
       ``unknown_sub_agent``, never escaping as a 500 — must name an existing
       ``SubAgent`` (``sub_agents.get_by_id``; else ``unknown_sub_agent``, 400),
       and must not be ``disabled`` (else ``sub_agent_disabled``, 400).
    4. Set ``system_prompt`` (a blank string is stored as-is) and ``modified_at``
       (``datetime.now(timezone.utc)`` — there is no ORM ``onupdate``), then
       persist via ``assistant_modes.update``.
    5. Replace-set the tools: ``mode_tools.delete_by_mode`` then one
       ``mode_tools.create`` per requested name, **de-duplicated** so a repeated
       name cannot violate ``uq_mode_tool_mode_key_tool_name``.
    6. Replace-set the sub-agents the same way:
       ``mode_subagents.delete_by_mode`` then one ``mode_subagents.create`` per
       id, de-duplicated against ``uq_mode_subagent_mode_key_sub_agent_id``.
    7. Return :func:`_to_mode_response` of the saved mode.

    An empty ``tool_names`` is accepted and leaves the mode with zero
    ``mode_tool`` rows — empty means *no tools*
    (``context.md`` → scope decision 1).
    """
    # 1. Load — the mode must already exist (it is one of the seeded fixed five).
    mode = await assistant_modes.get_by_id(mode_key)
    if mode is None:
        raise AssistantConfigError(
            AssistantConfigErrorReason.mode_not_found,
            f"Assistant mode '{mode_key}' not found.",
        )

    # 2. Validate every requested tool name against the catalogue itself. No count
    #    is assumed: an empty registry simply makes every name unknown.
    known_tool_names = {tool.name for tool in TOOL_REGISTRY}
    for tool_name in req.tool_names:
        if tool_name not in known_tool_names:
            raise AssistantConfigError(
                AssistantConfigErrorReason.unknown_tool,
                f"Unknown tool '{tool_name}'.",
            )

    # 3. Validate every requested sub-agent id: it must parse, exist, and be
    #    enabled. An unparsable id is an unknown id, never a 500.
    requested_sub_agent_ids: list[int] = []
    for raw_sub_agent_id in req.sub_agent_ids:
        try:
            sub_agent_id = int(raw_sub_agent_id)
        except (ValueError, TypeError):
            raise AssistantConfigError(
                AssistantConfigErrorReason.unknown_sub_agent,
                f"Unknown sub-agent '{raw_sub_agent_id}'.",
            )
        sub_agent = await sub_agents.get_by_id(sub_agent_id)
        if sub_agent is None:
            raise AssistantConfigError(
                AssistantConfigErrorReason.unknown_sub_agent,
                f"Unknown sub-agent '{raw_sub_agent_id}'.",
            )
        if sub_agent.disabled:
            raise AssistantConfigError(
                AssistantConfigErrorReason.sub_agent_disabled,
                f"Sub-agent '{sub_agent.name}' is disabled and cannot be attached.",
            )
        requested_sub_agent_ids.append(sub_agent_id)

    # Everything above validates; nothing below can be reached by a refused save,
    # so a rejected request leaves the stored configuration untouched (DoD-7/8/9).

    # 4. Scalars. A blank prompt is stored as-is; ``None`` clears it.
    mode.system_prompt = req.system_prompt
    mode.modified_at = datetime.now(timezone.utc)
    await assistant_modes.update(mode)

    # 5. Replace-set the tool selection (``dict.fromkeys`` de-duplicates while
    #    keeping the requested order, so the unique constraint cannot be hit).
    await mode_tools.delete_by_mode(mode_key)
    for tool_name in dict.fromkeys(req.tool_names):
        await mode_tools.create(ModeTool(mode_key=mode_key, tool_name=tool_name))

    # 6. Replace-set the sub-agent selection the same way.
    await mode_subagents.delete_by_mode(mode_key)
    for sub_agent_id in dict.fromkeys(requested_sub_agent_ids):
        await mode_subagents.create(
            ModeSubagent(mode_key=mode_key, sub_agent_id=sub_agent_id)
        )

    # 7. Rebuild from what was just stored.
    return await _to_mode_response(mode)


def _parse_sub_agent_id(sub_agent_id: str) -> int:
    """Coerce a wire ``sub_agent_id`` string to the ``int`` row id.

    **The service owns the parse** — ``sub_agent_id`` is a ``str`` at the JSON
    boundary (``context.md`` → "Every id is a ``str`` at the JSON boundary";
    snowflakes exceed the JS safe-integer range) and step 005's route hands it over
    as-is rather than declaring an ``int`` path param, because deciding what a
    malformed id *means* is business logic and ``routes/`` is HTTP-only. This
    deliberately diverges from the ``routes/admin/llm_servers.py:103 server_id:
    int`` precedent, which step 005 overrides for this feature.

    A value that is not a well-formed id is treated as a **missing** sub-agent —
    ``sub_agent_not_found`` (404, step 005's DoD-7), never an escaping
    ``ValueError`` as a 500. Mirrors ``services/chats.py:133 _parse_chat_id``;
    sync, like it, because no DB access is involved.

    Distinct from step 002's ``unknown_sub_agent``: that reason answers an
    unparsable id **inside a mode's selection body** (where the sub-agent is a
    referenced entity, → 400); this one answers an unparsable id **in the path**
    (where the sub-agent is the addressed resource, → 404).

    Internal (leading underscore); shared by :func:`update_sub_agent` and, from
    step 004, the disable/enable setter.
    """
    try:
        return int(sub_agent_id)
    except (ValueError, TypeError):
        raise AssistantConfigError(
            AssistantConfigErrorReason.sub_agent_not_found,
            "Sub-agent not found.",
        )


async def _validate_model_pair(
    llm_server_id: str | None, model_name: str | None
) -> int | None:
    """Validate a sub-agent's ``(llm_server_id, model_name)`` pair and return the
    resolved integer server id, or ``None`` when the pair is unset (US-113.AC-5,
    US-113.AC-6).

    Mirrors ``services/chats.py:142-177`` in **rule set and order** — a local copy
    under this feature's own enum, not an import (see the module docstring):

    1. exactly one of the two set → ``invalid_model_pair`` (400);
    2. both ``None`` → the assignment is *inherit the main chat's model*; return
       ``None`` ("no server") — this is a recorded configured state, not an
       omission;
    3. ``int(llm_server_id)`` raising ``ValueError`` / ``TypeError`` →
       ``unknown_or_inactive_server`` (400), never a 500;
    4. ``llm_servers.get_by_id`` returning ``None``, **or** a row whose
       ``is_active`` is false → ``unknown_or_inactive_server`` (400);
    5. ``model_name`` absent from the server's ``json.loads(enabled_models)`` →
       ``model_not_enabled`` (400) — ``enabled_models`` is a JSON-encoded
       ``list[str]`` in a TEXT column, decoded here at the **service edge**, never
       in ``db/``;
    6. otherwise return the parsed server id.

    Internal (leading underscore); shared by :func:`create_sub_agent` and
    :func:`update_sub_agent`, and called **before any write** in both.

    Accepted consequence, recorded not solved (``context.md`` → scope decision 3):
    a server deactivated *after* an assignment was stored leaves that assignment
    unusable at runtime. Nothing here re-validates or rewrites stored assignments.
    """
    # 1. The pair moves together — exactly one set is never a valid state.
    if (llm_server_id is None) != (model_name is None):
        raise AssistantConfigError(
            AssistantConfigErrorReason.invalid_model_pair,
            "llm_server_id and model_name must both be set or both be null.",
        )
    # 2. Both unset — the recorded *inherit the main chat's model* state.
    if llm_server_id is None:
        return None
    # 3. An unparsable server id is an unknown server, never an escaping ValueError.
    try:
        server_id = int(llm_server_id)
    except (ValueError, TypeError):
        raise AssistantConfigError(
            AssistantConfigErrorReason.unknown_or_inactive_server,
            f"Unknown server '{llm_server_id}'.",
        )
    # 4. Missing and deactivated are the same refusal — the config edge only ever
    #    stores a pair that is usable *now*.
    server = await llm_servers.get_by_id(server_id)
    if server is None or not server.is_active:
        raise AssistantConfigError(
            AssistantConfigErrorReason.unknown_or_inactive_server,
            "Server is unknown or inactive.",
        )
    # 5. ``enabled_models`` is a JSON-encoded list[str] in a TEXT column, decoded
    #    here at the service edge.
    if model_name not in json.loads(server.enabled_models):
        raise AssistantConfigError(
            AssistantConfigErrorReason.model_not_enabled,
            f"Model '{model_name}' is not enabled on this server.",
        )
    # 6. Resolved.
    return server_id


async def _to_sub_agent_response(sub_agent: SubAgent) -> SubAgentResponse:
    """Build the :class:`SubAgentResponse` for one ``SubAgent`` row.

    Loads the sub-agent's ``subagent_tool`` rows
    (``subagent_tools.list_by_sub_agent``) and its ``mode_subagent`` rows
    (``mode_subagents.list_by_sub_agent``) through the ``db`` namespace modules and
    hand-maps them into the DTO — never ``model_dump()`` of an ORM row
    (``services/llm_servers.py:80`` precedent). ``id`` and ``llm_server_id`` are
    **stringified**; ``mode_keys`` comes from the link rows, since there is no
    ``accessible_modes`` column.

    Both link lists are empty until step 004 supplies their write path; the shape is
    fixed here so the response never changes.

    Internal (leading underscore): the shared builder for the lister, the creator
    and the updater. Not part of the tested surface.
    """
    tool_rows = await subagent_tools.list_by_sub_agent(sub_agent.id)
    link_rows = await mode_subagents.list_by_sub_agent(sub_agent.id)
    return SubAgentResponse(
        id=str(sub_agent.id),
        name=sub_agent.name,
        system_prompt=sub_agent.system_prompt,
        disabled=sub_agent.disabled,
        llm_server_id=(
            None if sub_agent.llm_server_id is None else str(sub_agent.llm_server_id)
        ),
        model_name=sub_agent.model_name,
        tool_names=[row.tool_name for row in tool_rows],
        mode_keys=[row.mode_key for row in link_rows],
        created_at=sub_agent.created_at,
        modified_at=sub_agent.modified_at,
    )


async def list_sub_agents() -> SubAgentsListResponse:
    """Return **every** sub-agent with its current configuration, ordered by
    ``name`` (UC-096; US-114.AC-3).

    Includes **disabled** sub-agents — hiding them would make a disabled sub-agent
    unfindable and therefore un-re-enableable. Each entry carries its ``disabled``
    flag so the surface can mark it. ``sub_agents.list_all`` already orders by
    ``name`` ascending and filters nothing.
    """
    rows = await sub_agents.list_all()
    return SubAgentsListResponse(
        items=[await _to_sub_agent_response(row) for row in rows]
    )


async def _validate_selections(tool_names: list[str], mode_keys: list[str]) -> None:
    """Validate a sub-agent's two selection lists **before any write** of the save.

    The caller-side half of the replace-set operation: the two writers
    (:func:`_replace_sub_agent_tools` / :func:`_replace_sub_agent_modes`) write and
    do not validate, because "every validation before any write" spans a whole save
    — the create path must store the ``SubAgent`` row first (it needs the snowflake
    id) and a save replaces *two* link sets, so a refusal discovered inside the
    second writer would leave a stored row or a half-replaced selection, which
    DoD-6 forbids (``004.context.md`` → Gotchas). Hoisting the checks here keeps
    both callers' refusals total.

    - Every ``tool_names`` entry must name a ``TOOL_REGISTRY`` tool; the first
      unknown name → ``unknown_tool`` (400). Membership is checked against the
      registry directly, never via ``resolve_tools`` (which skips unknown names);
      no count is assumed, so zero, one or many entries all behave.
    - Every ``mode_keys`` entry must name a stored ``AssistantMode``
      (``assistant_modes.get_by_id``); the first unknown key → ``mode_not_found``
      (400) — **step 002's reason reused, there is no new enum member**.

    Both empty lists validate trivially: empty means *none*
    (``context.md`` → scope decision 1).

    Internal (leading underscore) and not frozen — the step-004 record leaves the
    shape of the caller-side validation to the coder, provided no frozen signature
    changes.
    """
    known_tool_names = {tool.name for tool in TOOL_REGISTRY}
    for tool_name in tool_names:
        if tool_name not in known_tool_names:
            raise AssistantConfigError(
                AssistantConfigErrorReason.unknown_tool,
                f"Unknown tool '{tool_name}'.",
            )
    for mode_key in mode_keys:
        if await assistant_modes.get_by_id(mode_key) is None:
            raise AssistantConfigError(
                AssistantConfigErrorReason.mode_not_found,
                f"Assistant mode '{mode_key}' not found.",
            )


async def create_sub_agent(req: CreateSubAgentRequest) -> SubAgentResponse:
    """Create a sub-agent and return its :class:`SubAgentResponse` (UC-096;
    US-113.AC-1, US-113.AC-5, US-113.AC-6).

    **All validation happens before any write.** Order:

    1. Trim ``req.name``; an empty result → ``blank_name`` (400, UC-096 exception
       flow). Trimming happens **before** the collision check too, so ``" x "`` and
       ``"x"`` cannot both be stored.
    2. ``sub_agents.get_by_name`` on the trimmed name; a hit → ``name_taken``
       (**409**, the ``services/admin.py:109-113`` precedent). ``SubAgent.name`` is
       also ``unique=True`` at the DB level, but this pre-check is what turns the
       collision into a typed 409 instead of an ``IntegrityError`` surfacing as a
       500.
    3. :func:`_validate_model_pair` on ``req.llm_server_id`` / ``req.model_name``.
    4. :func:`_validate_selections` on ``req.tool_names`` / ``req.mode_keys`` —
       ``unknown_tool`` / ``mode_not_found``. Runs **before** the row is stored, so
       a refused create leaves nothing behind (DoD-6). No disabled guard is needed
       here: a created sub-agent is always ``disabled=False``.
    5. Store the row via ``sub_agents.create`` with the trimmed ``name``,
       ``req.system_prompt`` verbatim (``""`` included — only the name is
       blank-checked), the resolved server id, ``disabled=False``, and **both**
       ``created_at`` and ``modified_at`` set to ``datetime.now(timezone.utc)``
       (there is no ORM ``onupdate`` in this codebase). The snowflake ``id`` comes
       from ``default_factory=generate_id`` and must **not** be supplied.
    6. Apply both replace-sets against the freshly minted row id
       (:func:`_replace_sub_agent_tools`, then :func:`_replace_sub_agent_modes`) —
       the row must exist first because its snowflake id is the link rows' FK.
    7. Return :func:`_to_sub_agent_response` of the created row, which now carries
       both selections (UC-096 steps 4–5; US-113.AC-1).
    """
    # 1. Trim first, so the blank check and the collision check both see the value
    #    that would actually be stored.
    name = req.name.strip()
    if not name:
        raise AssistantConfigError(
            AssistantConfigErrorReason.blank_name,
            "Sub-agent name must not be blank.",
        )

    # 2. Typed 409 instead of an IntegrityError from the unique index.
    if await sub_agents.get_by_name(name) is not None:
        raise AssistantConfigError(
            AssistantConfigErrorReason.name_taken,
            f"Sub-agent name '{name}' is already taken.",
        )

    # 3. The pair moves together and must be usable now.
    resolved_server_id = await _validate_model_pair(req.llm_server_id, req.model_name)

    # 4. Both selections are checked here, not inside the writers, so a bad name or
    #    key refuses the create outright instead of leaving a stored row behind.
    await _validate_selections(req.tool_names, req.mode_keys)

    # Everything above validates; nothing is written by a refused create.

    # 5. Store. The snowflake ``id`` comes from ``default_factory=generate_id``.
    now = datetime.now(timezone.utc)
    row = await sub_agents.create(
        SubAgent(
            name=name,
            system_prompt=req.system_prompt,
            disabled=False,
            llm_server_id=resolved_server_id,
            model_name=req.model_name,
            created_at=now,
            modified_at=now,
        )
    )

    # 6. Replace-sets need the row's snowflake id, so they follow the insert.
    await _replace_sub_agent_tools(row.id, req.tool_names)
    await _replace_sub_agent_modes(row.id, req.mode_keys)

    # 7. Rebuild from what was just stored.
    return await _to_sub_agent_response(row)


async def update_sub_agent(
    sub_agent_id: str, req: UpdateSubAgentRequest
) -> SubAgentResponse:
    """Full-replace one sub-agent's editable scalars **and both selection sets**,
    and return its refreshed :class:`SubAgentResponse` (UC-097; US-114.AC-1,
    US-114.AC-2, US-114.AC-4).

    ``sub_agent_id`` arrives as the **wire string** and is parsed here via
    :func:`_parse_sub_agent_id`; ``db.sub_agents.get_by_id`` still takes an ``int``,
    so the string→int edge is exactly this service boundary.

    **All validation happens before any write.** Order:

    1. :func:`_parse_sub_agent_id`, then ``sub_agents.get_by_id``; an unparsable id
       **or** no row → ``sub_agent_not_found`` (404, UC-097's precondition; step
       005's DoD-7 requires the malformed-id case to answer 404, not 422 or 500).
    2. The same trim + ``blank_name`` check as create.
    3. The same ``sub_agents.get_by_name`` collision check, **excluding the row
       being updated**: a hit whose ``id`` equals the **parsed** id is a self-match,
       not a collision, so saving a sub-agent without renaming it succeeds
       (US-114.AC-1). Any other hit → ``name_taken`` (409).
    4. :func:`_validate_model_pair` — re-run unconditionally. Unlike
       ``services/chats.py:update_chat:276-280`` there is **no** "only when one of
       the two is present" branch: writes here are full-replace ``PUT``s, both
       fields are always present, and ``null`` + ``null`` is a meaningful value
       (``003.context.md`` → "Deliberate divergence, recorded").
    5. The **disabled guard**, keyed on emptiness: a **non-empty** ``req.mode_keys``
       on a row whose ``disabled`` is true → ``sub_agent_disabled`` (400).
       Disabling *is* being detached from every mode (US-114.AC-2), so granting an
       attachment in the same breath would contradict the invariant; step 002
       already refuses the symmetric case from the mode side and the two guards
       share one reason. An **empty** ``mode_keys`` is accepted — it agrees with
       the invariant — which is what keeps a disabled sub-agent's name, prompt,
       tools and model editable (UC-097).
    6. :func:`_validate_selections` on ``req.tool_names`` / ``req.mode_keys`` —
       ``unknown_tool`` / ``mode_not_found``, before the first ``delete_by_*`` so a
       refused save leaves the scalars **and** both existing link sets untouched
       (DoD-6).
    7. Assign name / prompt / the pair, refresh ``modified_at``
       (``datetime.now(timezone.utc)`` — refreshed for a links-only save too), and
       persist via ``sub_agents.update`` (row-in / ``None``-out). ``disabled`` is
       **not** touched — enable/disable is :func:`set_sub_agent_disabled`.
    8. Apply both replace-sets (:func:`_replace_sub_agent_tools`, then
       :func:`_replace_sub_agent_modes`): a tool or mode present before and absent
       from this request is gone (US-114.AC-1), and the mode replace touches only
       this sub-agent's slice of ``mode_subagent`` (US-112.AC-2).
    9. Return :func:`_to_sub_agent_response` of the saved row.
    """
    # 1. An unparsable id and a missing row are the same answer: not found.
    parsed_id = _parse_sub_agent_id(sub_agent_id)
    row = await sub_agents.get_by_id(parsed_id)
    if row is None:
        raise AssistantConfigError(
            AssistantConfigErrorReason.sub_agent_not_found,
            f"Sub-agent '{sub_agent_id}' not found.",
        )

    # 2. Same trim-then-blank-check as create.
    name = req.name.strip()
    if not name:
        raise AssistantConfigError(
            AssistantConfigErrorReason.blank_name,
            "Sub-agent name must not be blank.",
        )

    # 3. The row being updated is excluded — an unchanged name is not a collision.
    existing = await sub_agents.get_by_name(name)
    if existing is not None and existing.id != parsed_id:
        raise AssistantConfigError(
            AssistantConfigErrorReason.name_taken,
            f"Sub-agent name '{name}' is already taken.",
        )

    # 4. Re-run unconditionally: full-replace always carries both fields, and
    #    null + null is a meaningful value rather than an omission.
    resolved_server_id = await _validate_model_pair(req.llm_server_id, req.model_name)

    # 5. The disabled guard keys on emptiness: an empty selection agrees with
    #    "attached to nothing" and is accepted, a non-empty one contradicts it.
    if row.disabled and req.mode_keys:
        raise AssistantConfigError(
            AssistantConfigErrorReason.sub_agent_disabled,
            f"Sub-agent '{row.name}' is disabled and cannot be attached to a mode.",
        )

    # 6. Both selections are checked before the first delete_by_*, so a refusal
    #    cannot leave a half-replaced selection.
    await _validate_selections(req.tool_names, req.mode_keys)

    # Everything above validates; nothing is written by a refused update.

    # 7. Assign and persist. ``disabled`` is never touched here.
    row.name = name
    row.system_prompt = req.system_prompt
    row.llm_server_id = resolved_server_id
    row.model_name = req.model_name
    row.modified_at = datetime.now(timezone.utc)
    await sub_agents.update(row)

    # 8. Replace-set both link sets — full replace, not a merge.
    await _replace_sub_agent_tools(parsed_id, req.tool_names)
    await _replace_sub_agent_modes(parsed_id, req.mode_keys)

    # 9. Rebuild from what was just stored.
    return await _to_sub_agent_response(row)


async def _replace_sub_agent_tools(sub_agent_id: int, tool_names: list[str]) -> None:
    """Replace-set this sub-agent's ``subagent_tool`` rows: delete them all, then
    create one row per **distinct** requested name (US-114.AC-1).

    ``subagent_tools.delete_by_sub_agent(sub_agent_id)`` followed by one
    ``subagent_tools.create(SubagentTool(...))`` per name, de-duplicated
    (``dict.fromkeys`` keeps the requested order) so a repeated checkbox cannot
    violate ``uq_subagent_tool_sub_agent_id_tool_name`` — the
    :func:`save_mode` step-5 idiom. An empty ``tool_names`` leaves the sub-agent
    with zero rows: empty means *none* (``context.md`` → scope decision 1).

    **This helper writes; it does not validate.** Every name must already have been
    checked against ``TOOL_REGISTRY`` by the caller (unknown → ``unknown_tool``,
    400) *before* the first ``delete_by_*`` of the save. Validation is hoisted into
    :func:`create_sub_agent` / :func:`update_sub_agent` rather than living here
    because a self-contained validate-then-write helper cannot satisfy "every
    validation before any write" — the create path must write the ``SubAgent`` row
    first (it needs the snowflake id), and a mid-save refusal would then leave a
    stored row or a half-replaced selection, which DoD-6 forbids
    (``004.context.md`` → Gotchas).

    Internal (leading underscore); ``sub_agent_id`` is the **``int`` row id**, not
    the wire string.
    """
    await subagent_tools.delete_by_sub_agent(sub_agent_id)
    # ``dict.fromkeys`` keeps the requested order while collapsing repeats, so a
    # duplicated checkbox cannot reach the unique constraint.
    for tool_name in dict.fromkeys(tool_names):
        await subagent_tools.create(
            SubagentTool(sub_agent_id=sub_agent_id, tool_name=tool_name)
        )


async def _replace_sub_agent_modes(sub_agent_id: int, mode_keys: list[str]) -> None:
    """Replace-set this sub-agent's ``mode_subagent`` rows: delete its slice, then
    create one row per **distinct** requested mode key (US-112.AC-2, US-114.AC-1).

    ``mode_subagents.delete_by_sub_agent(sub_agent_id)`` followed by one
    ``mode_subagents.create(ModeSubagent(...))`` per key, de-duplicated against
    ``uq_mode_subagent_mode_key_sub_agent_id``.

    **This writes the same row set step 002's mode saver writes** — one row set,
    two editors. ``delete_by_sub_agent`` removes only this sub-agent's slice, so
    other sub-agents' links to the same modes survive; there is no direction of
    truth, last write wins for the slice it owns (``004.context.md`` → "The one
    table two steps write").

    **This helper writes; it does not validate.** Every key must already have been
    checked against the stored ``AssistantMode`` rows
    (``assistant_modes.get_by_id``; unknown → ``mode_not_found``, the step-002
    reason reused — **no new enum member exists for this**), and the
    disabled-sub-agent guard must already have run, both *before* the first
    ``delete_by_*`` of the save. Same reasoning as
    :func:`_replace_sub_agent_tools`.

    Internal (leading underscore); ``sub_agent_id`` is the **``int`` row id**.
    """
    # Only this sub-agent's slice is cleared — other sub-agents' links to the same
    # modes survive (US-112.AC-2).
    await mode_subagents.delete_by_sub_agent(sub_agent_id)
    for mode_key in dict.fromkeys(mode_keys):
        await mode_subagents.create(
            ModeSubagent(mode_key=mode_key, sub_agent_id=sub_agent_id)
        )


async def set_sub_agent_disabled(
    sub_agent_id: str, disabled: bool
) -> SubAgentResponse:
    """Disable or re-enable a sub-agent and return its refreshed
    :class:`SubAgentResponse` (UC-097 alternate flow; US-114.AC-2, US-114.AC-3).

    ``sub_agent_id`` arrives as the **wire string** and is parsed by the frozen
    :func:`_parse_sub_agent_id`, exactly as :func:`update_sub_agent` does — an
    unparsable id and a missing row are the same answer, ``sub_agent_not_found``
    (404). Order:

    1. :func:`_parse_sub_agent_id`, then ``sub_agents.get_by_id``; no row →
       ``sub_agent_not_found``.
    2. Set ``disabled`` to the requested value and refresh ``modified_at``
       (``datetime.now(timezone.utc)`` — no ORM ``onupdate``), persist via
       ``sub_agents.update`` (row-in / ``None``-out).
    3. **When disabling** — additionally delete every ``mode_subagent`` row for
       this sub-agent (``mode_subagents.delete_by_sub_agent``): disabling *is*
       being detached from every mode (US-114.AC-2). Its ``subagent_tool`` rows are
       **kept** — the tool selection is the sub-agent's own configuration, not a
       mode's grant, and UC-097's disable flow speaks only of modes. The
       ``SubAgent`` row itself is kept, and so are ``llm_server_id`` /
       ``model_name``.
    4. **When enabling** — the flag and ``modified_at`` and **nothing else**. The
       links deleted at disable time are *not* restored: they were deleted, not
       suppressed, so a re-enabled sub-agent is attached to no mode until a mode or
       this sub-agent selects it again (US-114.AC-3).
    5. Return :func:`_to_sub_agent_response` of the saved row.

    Idempotent by construction: disabling an already-disabled sub-agent, or
    enabling an already-enabled one, is a valid no-op save (``modified_at`` still
    refreshes).

    **There is no hard-delete counterpart anywhere in this feature** — no
    ``db.sub_agents.delete``, no service delete, no delete route
    (``context.md`` → scope decision 6). Do not add one.
    """
    # 1. An unparsable id and a missing row are the same answer: not found.
    parsed_id = _parse_sub_agent_id(sub_agent_id)
    row = await sub_agents.get_by_id(parsed_id)
    if row is None:
        raise AssistantConfigError(
            AssistantConfigErrorReason.sub_agent_not_found,
            f"Sub-agent '{sub_agent_id}' not found.",
        )

    # 2. The flag plus a fresh ``modified_at`` — there is no ORM ``onupdate``.
    row.disabled = disabled
    row.modified_at = datetime.now(timezone.utc)
    await sub_agents.update(row)

    # 3. Disabling *is* detachment from every mode. The ``subagent_tool`` rows, the
    #    model pair and the row itself are all kept; enabling restores nothing.
    if disabled:
        await mode_subagents.delete_by_sub_agent(parsed_id)

    # 4/5. Enabling is the flag and the timestamp and nothing else; rebuild from
    #      what was just stored.
    return await _to_sub_agent_response(row)
