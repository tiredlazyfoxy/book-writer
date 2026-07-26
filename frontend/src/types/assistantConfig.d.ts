// Wire DTOs for the admin assistant-configuration endpoints
// (`/api/admin/assistant-config`) — pure shapes mirroring the backend Pydantic
// schemas (`app/models/schemas/assistant_config.py`) 1:1, in wire-exact
// `snake_case`. No methods, no classes, no runtime validation, NO runtime values.
// See docs/plans/012.assistant-config-editor (steps 002-004 froze the DTOs).
//
// NOTE ON id TYPES — every id crosses the wire as a `string`: the backend PKs are
// 64-bit snowflakes, which exceed the JS safe-integer range. `SubAgent.id` and
// `SubAgent.llm_server_id` are therefore `string` / `string | null`, and a mode's
// `sub_agent_ids` is a `string[]`. `AssistantMode.key` is a natural string PK and
// is emitted verbatim.
//
// NOTE ON ENVELOPES — the three list endpoints answer `{ "items": [...] }`. That
// envelope is unwrapped inside `api/assistantConfig.ts` and is deliberately NOT
// modelled here (context.md -> frontend constraints).
//
// NOTE ON RUNTIME CONSTANTS — the human-readable mode labels live in
// `api/assistantConfig.ts` (`MODE_LABELS` / `modeLabel`), not here: a declaration
// file cannot hold a value (the `api/llmServers.ts` `BACKEND_OPTIONS` precedent).

import type { ISODateString } from "./common";

/**
 * One entry of the backend tool catalogue — `GET /api/admin/assistant-config/tools`
 * row. Mirrors backend `ToolResponse`, which carries **exactly two** fields: the
 * `args_schema` and `callable` of the registry's `ToolDef` never cross the wire.
 */
export interface AssistantTool {
  name: string;
  description: string;
}

/**
 * One of the fixed five system modes — `GET /api/admin/assistant-config/modes` row
 * and the result of a mode save. Mirrors backend `AssistantModeResponse`.
 *
 * `key` is the natural primary key (`edit-character`, `edit-location`,
 * `edit-fact`, `write-chapter`, `close-chapter`). `tool_names` is the mode's
 * selected-tool allowlist — an **empty array means no tools**, never "all tools".
 * `sub_agent_ids` are string snowflakes. Both timestamps are nullable (a seeded
 * mode reports `created_at: null` until its first save).
 */
export interface AssistantMode {
  key: string;
  system_prompt: string | null;
  tool_names: string[];
  sub_agent_ids: string[];
  created_at: ISODateString | null;
  modified_at: ISODateString | null;
}

/**
 * `PUT /api/admin/assistant-config/modes/{mode_key}` request body — mirrors backend
 * `UpdateAssistantModeRequest`. Full-replace: all three fields are **required in the
 * body** (their values may be `null` / `[]`), and both selections replace the stored
 * sets rather than merging into them.
 */
export interface UpdateAssistantModeRequest {
  system_prompt: string | null;
  tool_names: string[];
  sub_agent_ids: string[];
}

/**
 * An admin-created sub-agent — `GET /api/admin/assistant-config/sub-agents` row and
 * the result of every sub-agent write. Mirrors backend `SubAgentResponse`.
 *
 * `system_prompt` is **non-nullable** here (unlike the mode's) — the column is
 * required and `""` is a valid stored value. `llm_server_id` + `model_name` are the
 * optional model assignment: both `null` means *inherit the main chat's model*.
 * `mode_keys` is the sub-agent-side view of the same `mode_subagent` row set that
 * `AssistantMode.sub_agent_ids` shows from the mode side.
 */
export interface SubAgent {
  id: string;
  name: string;
  system_prompt: string;
  disabled: boolean;
  llm_server_id: string | null;
  model_name: string | null;
  tool_names: string[];
  mode_keys: string[];
  created_at: ISODateString | null;
  modified_at: ISODateString | null;
}

/**
 * `POST /api/admin/assistant-config/sub-agents` request body — mirrors backend
 * `CreateSubAgentRequest`. The four scalars are **required** (the model pair must be
 * passed explicitly, `null` + `null` meaning *inherit*); the two selection lists are
 * the only defaulted fields — omitting one means *no selection*.
 */
export interface CreateSubAgentRequest {
  name: string;
  system_prompt: string;
  llm_server_id: string | null;
  model_name: string | null;
  tool_names?: string[];
  mode_keys?: string[];
}

/**
 * `PUT /api/admin/assistant-config/sub-agents/{id}` request body — mirrors backend
 * `UpdateSubAgentRequest`: the same six fields as the create body. There is **no
 * `disabled` field** — enable/disable are their own zero-body endpoints.
 */
export interface UpdateSubAgentRequest {
  name: string;
  system_prompt: string;
  llm_server_id: string | null;
  model_name: string | null;
  tool_names?: string[];
  mode_keys?: string[];
}
