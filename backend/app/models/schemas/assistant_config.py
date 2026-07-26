"""Assistant-configuration request & response schemas (feature 012, step 002).

Declarative Pydantic schemas — the typed contracts for the admin assistant-config
surface (`/api/admin/...`, step 005). Plain typed data shapes, **no logic** (see
``docs/architecture/backend.md`` — ``models/`` is tables + schemas only). Mapping
is the service's job (``services/llm_servers.py:80 _to_response`` precedent);
nothing here is ever produced by ``model_dump()`` of an ORM row.

Wire conventions this module obeys (``context.md`` → cross-cutting backend
constraints):

- **Every id crosses the wire as a ``str``** — snowflakes exceed the JS
  safe-integer range. ``sub_agent_id`` is therefore ``str`` on the wire and
  ``int`` in the row; ``AssistantMode.key`` is already a string and is emitted
  verbatim.
- **List responses are ``items`` envelopes**, mirroring
  ``LlmServersListResponse``.
- The tool DTO carries **only** ``name`` and ``description``. ``ToolDef``'s
  ``args_schema`` and ``callable`` are internal and must never reach the wire,
  nor may any key derived from them.

Step 003 adds the sub-agent DTOs to this same module; step 002 deliberately
wrote **no** sub-agent DTO — a mode carries sub-agent **ids only**, which is
what keeps the two halves of the feature from importing each other's shapes
(``002.context.md`` → Gotchas). Step 004 adds the two selection lists to the two
sub-agent **request** DTOs only; :class:`SubAgentResponse` already carries both
lists and is **unchanged**, so the response shape never moved.

Every schema carrying a ``model_name`` field sets
``model_config = ConfigDict(protected_namespaces=())`` — the
``models/schemas/chats.py:146-162`` precedent; without it Pydantic warns on the
``model_`` prefix.

Skeleton (012 steps 002, 003, 004): field names/types are frozen. A schema is a
declarative type — there is nothing to leave unimplemented.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ToolResponse(BaseModel):
    """One entry of the read-only tool catalogue (``services/tools.py:TOOL_REGISTRY``).

    - ``name`` — the tool's stable registry name; the value stored in
      ``mode_tool.tool_name`` / ``subagent_tool.tool_name`` and the value a
      selection request sends back.
    - ``description`` — the model-facing description, shown beside the checkbox.

    **Nothing else.** ``ToolDef.args_schema`` and ``ToolDef.callable`` are
    internal (UC-095 step 3 needs only a selectable label).
    """

    name: str
    description: str


class ToolsListResponse(BaseModel):
    """List envelope for the tool catalogue — registry declaration order."""

    items: list[ToolResponse]


class AssistantModeResponse(BaseModel):
    """One assistant mode with its current configuration.

    - ``key`` — the mode's natural-key primary key, emitted verbatim (one of
      ``db.assistant_modes.DEFAULT_MODE_KEYS``).
    - ``system_prompt`` — nullable; ``None`` and ``""`` are both valid *configured*
      states and round-trip as stored (US-110.AC-4, storage side).
    - ``tool_names`` — the ``mode_tool`` selection for this mode. An empty list
      means **no tools**, never "the whole registry"
      (``context.md`` → scope decision 1).
    - ``sub_agent_ids`` — the ``mode_subagent`` selection, ids **as strings**.
      Ids only: no name, no nested sub-agent shape.
    - ``created_at`` / ``modified_at`` — nullable app-set timestamps.
    """

    key: str
    system_prompt: str | None
    tool_names: list[str]
    sub_agent_ids: list[str]
    created_at: datetime | None
    modified_at: datetime | None


class AssistantModesListResponse(BaseModel):
    """List envelope for the mode list — ``DEFAULT_MODE_KEYS`` order (US-110.AC-1)."""

    items: list[AssistantModeResponse]


class UpdateAssistantModeRequest(BaseModel):
    """Body of the mode save — a **full replace** of the mode's configuration.

    All three fields are **required in the body**; none has a default. Their
    *values* may be empty or null (``system_prompt: null``, ``tool_names: []``,
    ``sub_agent_ids: []``) — that is a configured state, not an omission. This is
    ``PUT``-style full-replace, not ``PATCH``: under full-replace "absent" is not
    a state, so this deliberately does **not** mirror
    ``UpdateLlmServerRequest``'s all-optional partial shape
    (``context.md`` → "Writes are full-replace").

    - ``system_prompt`` — the new prompt, or ``null`` to leave the mode with no
      prompt. A blank string is stored as-is.
    - ``tool_names`` — the complete new tool selection. Every name must exist in
      ``TOOL_REGISTRY`` (else the ``unknown-tool`` refusal). Repeats are
      de-duplicated by the service, not rejected.
    - ``sub_agent_ids`` — the complete new sub-agent selection, ids **as
      strings**. Each must parse, exist, and not be ``disabled``. Repeats are
      de-duplicated by the service.
    """

    system_prompt: str | None
    tool_names: list[str]
    sub_agent_ids: list[str]


class SubAgentResponse(BaseModel):
    """One admin-created sub-agent with its current configuration (UC-096, UC-097;
    US-113, US-114).

    - ``id`` — the row's snowflake, **as a string** (JS safe-integer range).
    - ``name`` — the unique, non-blank display name.
    - ``system_prompt`` — **non-nullable** (unlike ``AssistantModeResponse``'s):
      the column is required, and ``""`` is the closest thing to "no prompt".
    - ``disabled`` — the disable-not-delete flag. Carried on **every** entry so a
      disabled sub-agent stays findable and re-enableable (US-114.AC-3).
    - ``llm_server_id`` — nullable, **as a string** (``int`` FK in the row).
    - ``model_name`` — nullable. ``null`` + ``null`` on both model fields is the
      recorded *inherit the main chat's model* state (US-113.AC-6), not an
      unconfigured one.
    - ``tool_names`` — the ``subagent_tool`` selection for this sub-agent.
    - ``mode_keys`` — the ``mode_subagent`` selection read from the **sub-agent**
      side: the modes this sub-agent is accessible from (the same row set the mode
      editor writes, US-112.AC-2). There is no ``accessible_modes`` column.
    - ``created_at`` / ``modified_at`` — nullable app-set timestamps.

    Both link lists are present **from step 003 on** even though step 004 supplies
    their write path — they are simply empty until then, so the response shape
    never changes (``003.md`` → Interface intent).
    """

    model_config = ConfigDict(protected_namespaces=())

    id: str
    name: str
    system_prompt: str
    disabled: bool
    llm_server_id: str | None
    model_name: str | None
    tool_names: list[str]
    mode_keys: list[str]
    created_at: datetime | None
    modified_at: datetime | None


class SubAgentsListResponse(BaseModel):
    """List envelope for the sub-agent list — **name-ascending, unfiltered**.

    Disabled sub-agents are included; each entry's ``disabled`` flag lets the
    surface mark it (US-114.AC-3 — a disabled sub-agent must remain findable in
    order to be re-enabled).
    """

    items: list[SubAgentResponse]


class CreateSubAgentRequest(BaseModel):
    """Body of the sub-agent create (UC-096; US-113.AC-1).

    All four fields are **required in the body** — none has a default, matching
    :class:`UpdateAssistantModeRequest`'s full-replace shape. Their *values* may be
    null where typed nullable: ``llm_server_id: null`` + ``model_name: null`` is
    the explicit *inherit the main chat's model* choice, not an omission
    (``context.md`` → "Writes are full-replace"). This deliberately does **not**
    mirror ``CreateChatRequest``'s all-defaulted shape.

    - ``name`` — trimmed by the service; a blank result is refused
      (``blank-name``), a name held by another sub-agent is refused
      (``name-taken``).
    - ``system_prompt`` — required, non-null; ``""`` is stored as-is (only the
      **name** is blank-checked).
    - ``llm_server_id`` / ``model_name`` — the optional model pair, ids **as
      strings**. Both-null or both-set; a half-set pair is refused
      (``invalid-model-pair``), and a set pair must name an active server
      (``unknown-or-inactive-server``) whose ``enabled_models`` lists the model
      (``model-not-enabled``) — US-113.AC-5.
    - ``tool_names`` (step 004) — the sub-agent's own tool selection, a
      **replace-set**. Every name must exist in ``TOOL_REGISTRY`` (else
      ``unknown-tool``); repeats are de-duplicated by the service, not rejected.
    - ``mode_keys`` (step 004) — the modes this sub-agent is accessible from, a
      **replace-set** over the same ``mode_subagent`` rows the mode editor writes
      (US-112.AC-2). Every key must name an existing ``AssistantMode`` (else
      ``mode-not-found``); repeats are de-duplicated.

    There is no ``disabled`` field: a created sub-agent is always enabled.

    **The two step-004 lists are the only defaulted fields on this model**
    (default: empty), deliberately diverging from the "every field required"
    shape of the other four. Reason: step 003's callers and tests omit them and
    must keep working, and an omitted selection means *no selection*. Pydantic
    deep-copies the ``[]`` default per instance, so the literal is not shared.
    """

    model_config = ConfigDict(protected_namespaces=())

    name: str
    system_prompt: str
    llm_server_id: str | None
    model_name: str | None
    tool_names: list[str] = []
    mode_keys: list[str] = []


class UpdateSubAgentRequest(BaseModel):
    """Body of the sub-agent save — a **full replace** of every editable scalar
    (UC-097; US-114.AC-1, US-114.AC-4).

    The same four required fields as :class:`CreateSubAgentRequest`, under the same
    validation, plus the same two defaulted-to-empty step-004 selection lists.
    Switching a stored pair back to ``null`` + ``null`` is a meaningful
    edit (back to *inherit the main chat's model*), which is why the pair is always
    explicitly present and why this does **not** mirror ``UpdateChatRequest``'s
    partial-``PATCH`` shape or its "re-validate only when one field is present"
    quirk (``003.context.md`` → "Deliberate divergence, recorded").

    - ``tool_names`` — replaces the whole ``subagent_tool`` set for this sub-agent:
      a tool present before and absent here is gone (US-114.AC-1). Empty means
      *none*.
    - ``mode_keys`` — replaces the whole ``mode_subagent`` slice for this sub-agent,
      leaving other sub-agents' links to the same modes intact. A **non-empty**
      value on a currently ``disabled`` sub-agent is refused
      (``sub-agent-disabled``); an **empty** one is accepted, which is what keeps a
      disabled sub-agent's name, prompt, tools and model editable (US-114.AC-2).

    **No ``disabled`` field**, on purpose: enable/disable is its own step-004
    operation (:func:`app.services.assistant_config.set_sub_agent_disabled`),
    because disabling cascades (it detaches the sub-agent from every mode) and a
    plain field assignment would hide that.
    """

    model_config = ConfigDict(protected_namespaces=())

    name: str
    system_prompt: str
    llm_server_id: str | None
    model_name: str | None
    tool_names: list[str] = []
    mode_keys: list[str] = []
