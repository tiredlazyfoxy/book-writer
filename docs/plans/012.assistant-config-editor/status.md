# Feature 012 — assistant-config-editor

| Step | File                                | Status  | Verifier | Date |
|------|-------------------------------------|---------|----------|------|
| 001  | `001.db-layer-completion.md`        | done    | PASS     | 2026-07-26 |
| 002  | `002.mode-config-service.md`        | done    | PASS     | 2026-07-26 |
| 003  | `003.subagent-crud.md`              | done    | PASS     | 2026-07-26 |
| 004  | `004.subagent-links-and-disable.md` | done    | PASS     | 2026-07-26 |
| 005  | `005.admin-routes.md`               | done    | PASS     | 2026-07-26 |
| 006  | `006.frontend-api-and-nav.md`       | done    | PASS     | 2026-07-26 |
| 007  | `007.modes-page.md`                 | done    | PASS     | 2026-07-26 |
| 008  | `008.subagents-page.md`             | done    | PASS     | 2026-07-26 |

## Files Changed

### Step 001 — db-layer completion and the seed-on-import fix

- `backend/app/db/assistant_modes.py` — `update(row) -> None` (row-in / `None`-out)
- `backend/app/db/sub_agents.py` — `list_all` (name-ascending, unfiltered), `get_by_name`, `update`
- `backend/app/db/mode_tools.py` — `delete_by_mode` count-returning bulk delete
- `backend/app/db/subagent_tools.py` — `delete_by_sub_agent` count-returning bulk delete
- `backend/app/db/mode_subagents.py` — `list_by_sub_agent` reverse lookup, `delete_by_mode`, `delete_by_sub_agent`
- `backend/app/services/setup.py` — `import_database` now calls `assistant_modes.seed_default_modes()` after the import succeeds and before `set_db_ready(True)`

### Step 002 — mode configuration service, DTOs and the tool catalogue

- `backend/app/models/schemas/assistant_config.py` — the five frozen DTOs (`ToolResponse`,
  `ToolsListResponse`, `AssistantModeResponse`, `AssistantModesListResponse`,
  `UpdateAssistantModeRequest`); declarative only, no body to fill
- `backend/app/services/assistant_config.py` — bodies filled for `list_tools` (hand-map of
  `TOOL_REGISTRY`, declaration order, `name`+`description` only), `_to_mode_response` (pure hand-map
  of the stored `mode_tool` / `mode_subagent` rows, ids stringified, no registry filtering at the
  read edge), `list_modes` (`DEFAULT_MODE_KEYS` position sort, unknown keys last by key) and
  `save_mode` (validate-then-write: load → tool names → sub-agent ids parse/exist/enabled → scalars
  + `modified_at` → two de-duplicated replace-sets → rebuilt DTO). Imports added for the bodies:
  `datetime`/`timezone`, `ModeTool`, `ModeSubagent`, `ToolResponse`. No frozen signature changed.

### Step 003 — sub-agent create / list / update

- `backend/app/models/schemas/assistant_config.py` — **unchanged by this step**: the four sub-agent
  DTOs (`SubAgentResponse`, `SubAgentsListResponse`, `CreateSubAgentRequest`,
  `UpdateSubAgentRequest`) are declarative and were complete at the freeze; there was no body to
  fill.
- `backend/app/services/assistant_config.py` — bodies filled for the six step-003 functions:
  `_parse_sub_agent_id` (sync `int()`, `ValueError`/`TypeError` → `sub_agent_not_found`),
  `_validate_model_pair` (local copy of `services/chats.py:142-177`'s rule order under this
  feature's enum: half-set → `invalid_model_pair`; both `None` → `None`; unparsable id, missing
  server and `is_active` false → `unknown_or_inactive_server`; model absent from
  `json.loads(enabled_models)` → `model_not_enabled`), `_to_sub_agent_response` (hand-map plus
  `subagent_tools.list_by_sub_agent` / `mode_subagents.list_by_sub_agent`, `id` and
  `llm_server_id` stringified), `list_sub_agents` (`sub_agents.list_all`, unfiltered — disabled rows
  included), `create_sub_agent` (trim → `blank_name` → `get_by_name` → `name_taken` → model pair →
  `disabled=False` + both timestamps → DTO) and `update_sub_agent` (parse+load → trim/blank →
  name collision **excluding the row's own id** → model pair re-run unconditionally → assign +
  `modified_at` → `sub_agents.update`; `disabled` untouched). All validation precedes any write in
  both writers. Imports added for the bodies: `json`, `db.llm_servers`, `db.subagent_tools`. No
  frozen signature changed; step 002's four bodies untouched.

### Step 004 — sub-agent link replace-sets and disable / enable

- `backend/app/models/schemas/assistant_config.py` — **unchanged by this step**: `tool_names: list[str] = []`
  and `mode_keys: list[str] = []` were already on `CreateSubAgentRequest` / `UpdateSubAgentRequest` at
  the freeze (declarative, nothing to fill); verified per-instance defaults and no `model_` warning
  under `-W error`.
- `backend/app/services/assistant_config.py` — bodies filled for the three step-004 functions plus the
  selection wiring:
  - `_replace_sub_agent_tools` — `subagent_tools.delete_by_sub_agent` then one
    `subagent_tools.create(SubagentTool(...))` per `dict.fromkeys`-deduplicated name; writes only, no
    validation.
  - `_replace_sub_agent_modes` — `mode_subagents.delete_by_sub_agent` (this sub-agent's slice only)
    then one `mode_subagents.create(ModeSubagent(...))` per deduplicated key — the same row set
    step 002's `save_mode` writes; writes only, no validation.
  - `set_sub_agent_disabled` — `_parse_sub_agent_id` + `get_by_id` (else `sub_agent_not_found`), sets
    the flag and `modified_at`, `sub_agents.update`; **on disable only**, additionally
    `mode_subagents.delete_by_sub_agent`. `subagent_tool` rows, the model pair and the row itself are
    kept; enabling restores nothing. Returns the rebuilt DTO.
  - `_validate_selections` — new **private, non-frozen** helper (the step-004 record leaves the
    caller-side validation shape to the coder): tool names against `TOOL_REGISTRY` →
    `unknown_tool`, mode keys against `assistant_modes.get_by_id` → `mode_not_found` (step 002's
    reason reused). **No enum member added** — still ten.
  - `create_sub_agent` — now validates both selections before the insert, then applies both
    replace-sets against the freshly minted snowflake id.
  - `update_sub_agent` — now carries the emptiness-keyed **disabled guard** (non-empty `mode_keys` on
    a `disabled` row → `sub_agent_disabled`; empty accepted), validates both selections before the
    first `delete_by_*`, and applies both replace-sets after the scalar save.
  - Import added for the bodies: `SubagentTool`. No frozen signature changed; steps 002's and 003's
    bodies otherwise untouched, and no hard-delete function was added anywhere.

### Step 005 — the admin route surface

- `backend/app/routes/admin/assistant_config.py` — bodies filled for all **eight** frozen handlers.
  Each is HTTP-only: one `await assistant_config_service.<fn>(...)` inside a
  `try` / `except AssistantConfigError` → `raise _map_assistant_config_error(err)`, returned
  directly (the DTO is the return annotation; no `response_model=`, no re-wrapping). `list_tools`,
  `list_modes` and `list_sub_agents` call the reader of the same name; `save_mode` passes
  `(mode_key, payload)`; `create_sub_agent` / `update_sub_agent` pass `(payload)` /
  `(sub_agent_id, payload)`; `disable_sub_agent` and `enable_sub_agent` both call
  `set_sub_agent_disabled(sub_agent_id, True | False)` — the boolean is the route's constant, no
  request DTO. `mode_key` and `sub_agent_id` are handed to the service **verbatim** — no parse, no
  coercion, no pre-validation, so an ill-formed id is the service's `sub_agent_not_found` (404),
  never a 422 or a 500. No `db/` access, no conditional about configuration state, no handler
  raising 401/403 (both come from `require_role`). No new import was needed and no frozen signature
  changed; the module-level status map and `_map_assistant_config_error` were already real at the
  freeze and were left untouched.
- `backend/app/main.py` — **unchanged by this step**: the import
  (`from app.routes.admin import assistant_config as admin_assistant_config`) and the bare
  `app.include_router(admin_assistant_config.router)` were both written at the freeze and verified
  correct; there was nothing to fill.
- Verified by introspection (no pytest run): `import app.main` clean; the generated OpenAPI shows
  the family at `/api/admin/assistant-config` with exactly **7 paths / 8 operations**, `POST
  /sub-agents` at **201** and the other seven at 200, and **zero** `delete` operations; the reason
  map covers all **10** `AssistantConfigErrorReason` members with no gap.

### Step 006 — frontend wire contract, nav entries, routes and page shells

- `frontend/src/api/assistantConfig.ts` — bodies filled for `modeLabel` and all **eight** endpoint
  functions; `import { request } from "./client";` added (the freeze left it out for
  `noUnusedLocals`), and the eight `void <param>;` scaffolding lines plus their `throw` messages
  removed.
  - `modeLabel(key)` — reads `MODE_LABELS[key]` and returns it only when it is a `string`,
    otherwise the **raw key** (DoD-7). Deliberately not a bare `MODE_LABELS[key]` index and not
    `?? key` alone: the `typeof` guard also keeps an inherited `Object.prototype` name
    (`toString`, `constructor`) from leaking a non-string through a `string` return type. Sync;
    `MODE_LABELS` was already real at the freeze and is untouched.
  - `listTools` / `listModes` / `listSubAgents` — `await request<{ items: … }>(…, { signal })` with
    an **inline** envelope type, returning `res.items` (the `llmServers.listServers` shape). No
    envelope interface was added to the `.d.ts`.
  - `saveMode` — `PUT ${BASE}/modes/${modeKey}` with `body`; `createSubAgent` — `POST
    ${BASE}/sub-agents` with `body`; `updateSubAgent` — `PUT ${BASE}/sub-agents/${id}` with `body`;
    `disableSubAgent` / `enableSubAgent` — `POST ${BASE}/sub-agents/${id}/disable|/enable` with
    **no `body` key at all** (step 005's zero-body POSTs). Ids and the mode key are interpolated
    verbatim — no parse, no coercion, no encoding helper.
  - **No `try`/`catch` anywhere in the module**, and no default-value fallback: `ApiError` from
    `request` propagates verbatim so callers branch on 409 vs 400 (DoD-6). The api layer does not
    inspect status codes, including `createSubAgent`'s 201.
  - Only the module's stale "Skeleton:" header paragraph was reworded to describe the shipped
    behaviour; no frozen signature changed.
- `frontend/src/types/assistantConfig.d.ts`, `frontend/src/admin/components/shell/navItems.ts`,
  `frontend/src/admin/routes.tsx`, `frontend/src/admin/pages/AssistantModesPage.tsx`,
  `frontend/src/admin/pages/SubAgentsPage.tsx` — **unchanged by this step**: the six wire
  interfaces, the two appended `ADMIN_NAV_ITEMS` entries (`IconSparkles` / `IconRobot`), the two
  flat routes above `path="*"`, and the two fetch-free `observer` shells (each exported **named and
  default**) were all written concretely at the freeze and verified correct; there was nothing to
  fill. The pages remain free of any page-state class, `useState`, `useEffect` or api import, per
  `006.context.md`.
- Gates: `cd frontend && npx tsc --noEmit` clean and `cd frontend && npm run build` (`tsc && vite
  build`) succeeds. `npm test` / `npm run test:types` not run — the verifier owns tests.

### Step 007 — the five-mode editor surface

- `frontend/src/admin/pages/assistantModesPageState.ts` — body filled for `loadModesPage`: the
  standard loader shape with all **three** trios moved together — `runInAction` sets the three
  statuses to `"loading"` and clears the three errors → one `Promise.all` over
  `listModes` / `listTools` / `listSubAgents` (parallel, each passed `signal`) →
  `if (signal?.aborted) return;` → `runInAction` commits the three trios to `"ready"`. `catch`:
  aborted-guard, then `err instanceof ApiError` → **all three** error fields get the message and all
  three statuses go `"error"` (the page renders `modesError ?? toolsError ?? subAgentsError`, and
  `modesStatus` is what suppresses the table — DoD-2); anything else **rethrows**. Imports added for
  the body: `runInAction`, `* as assistantConfigApi`, `ApiError`. The class is untouched; no
  mutation action was added.
- `frontend/src/admin/components/assistant-config/modeEditorDraft.ts` — constructor seeding
  (`systemPrompt = mode.system_prompt ?? ""`, `selectedTools = new Set(mode.tool_names)`,
  `selectedSubAgents = new Set(mode.sub_agent_ids)`; the `void mode;` scaffold removed), the three
  computeds (`clientErrors` returns `{}` — a mode has no required field, so Save is never blocked
  client-side; `errors` is `{...clientErrors, ...serverErrors}`, server wins; `canSubmit` is
  `submitStatus !== "loading"` and no client errors), and `submitModeEditor`'s body in the
  `serverFormDraft.ts:63-118` order: clear `serverErrors` + status `"loading"` → `saveMode(modeKey,
  { system_prompt: draft.systemPrompt || null, tool_names: Array.from(...), sub_agent_ids:
  Array.from(...) }, signal)` — **empty prompt sent as `null`**, empty selections sent as `[]` and
  never omitted → `catch`: `ApiError` → `serverErrors = { form: … }` (every status lands on the one
  `form` key: 400 / 404 / other all mean the cached catalogue or sub-agent list is stale) + status
  `"error"` + **return**; non-`ApiError` → aborted-guard, status `"error"`, **rethrow** → status
  `"ready"` → `onSaved()`. Imports added for the bodies: `runInAction`, `* as assistantConfigApi`,
  `ApiError`.
- `frontend/src/admin/components/assistant-config/ModeEditorModal.tsx` — modal body filled: the
  `form` `<Alert color="red">` as the `Stack`'s **first child** (`ServerFormModal.tsx:56`), then the
  frozen read-only `modeLabel` heading, then the repo's first `<Textarea>` (autosize,
  `minRows={6}` / `maxRows={16}`, described as optional), then the two pickers in the established
  idiom (`ScrollArea.Autosize mah={360}` → `Stack gap="xs"` → one `Checkbox` each; tools labelled
  with `name` + `description`, sub-agents with `name`). Both toggles go through small inner handlers
  that **reassign a fresh `Set`** — never mutate in place. `disabled` sub-agents are filtered out of
  the picker; a selected `sub_agent_id` with no entry in the loaded list is still offered, labelled
  with the **raw id**, so a stale cache is visible rather than silently dropping the selection
  (`007.context.md` → "The sub-agent name problem"). Each picker renders an explanatory dimmed line
  instead of a blank box when it has nothing to offer — nothing assumes a catalogue size. Save
  carries `disabled={!draft.canSubmit}`. Imports added: `Alert`, `Checkbox`, `ScrollArea`,
  `Textarea`. Props, draft wiring and `handleSubmit` untouched.
- `frontend/src/admin/pages/AssistantModesPage.tsx` — the two skeleton seams filled: `Prompt` /
  `Tools` / `Sub-agents` `Table.Th` headers between `Mode` and the `w={60}` action column, and the
  three matching cells — prompt **presence** as `Yes` / `No` (the `LlmServersPage.tsx:140`
  `has_api_key` precedent; an empty prompt is a valid saved state, so only presence is shown),
  `mode.tool_names.length` and `mode.sub_agent_ids.length`. Everything else — the state/effect/
  `refresh` wiring, the edit target in component-local `useState`, the `!loading && !error` table
  guard, the row's `aria-label="Edit mode"` `ActionIcon`, the conditional modal mount, and **both**
  the named and default exports — was frozen and is untouched.
- Gates: `cd frontend && npx tsc --noEmit` clean and `cd frontend && npm run build` (`tsc && vite
  build`) succeeds. `npm test` / `npm run test:types` not run — the verifier owns tests. No frozen
  signature changed, and no file outside the step's four Source files was modified.

### Step 008 — the sub-agent management surface

- `frontend/src/admin/pages/subAgentsPageState.ts` — bodies filled for all three effect functions.
  `loadSubAgentsPage`: the standard loader shape with all **four** trios moved together —
  `runInAction` sets the four statuses `"loading"` and clears the four errors → one `Promise.all`
  over `assistantConfigApi.listSubAgents` / `listTools` / `listModes` **and**
  `llmServersApi.listServers` (parallel, each passed `signal`) → `if (signal?.aborted) return;` →
  `runInAction` commits the four trios to `"ready"`. `catch`: aborted-guard, then
  `err instanceof ApiError` → all four error fields get the message and all four statuses go
  `"error"` (the page renders `subAgentsError ?? toolsError ?? modesError ?? serversError`, and
  `subAgentsStatus` is what suppresses the table — DoD-2); anything else **rethrows**.
  `disableSubAgentAction` / `enableSubAgentAction`: the `llmServersPageState.ts:67` shape minus the
  deletion — api call → aborted-guard → **re-run `loadSubAgentsPage`** (no optimistic update, no
  row patched in place); on `ApiError` record the message into `subAgentsError`, otherwise rethrow.
  No delete action exists. Imports added for the bodies: `runInAction`, `* as assistantConfigApi`,
  `* as llmServersApi`, `ApiError`. The class is untouched.
- `frontend/src/admin/components/sub-agents/subAgentFormDraft.ts` — constructor seeding (on edit:
  `name`, `system_prompt`, and the model pair copied **as a pair**; both `Set`s from `tool_names` /
  `mode_keys`; the `void subAgent;` scaffold removed), the five computeds and both external
  functions. `modelOptions` prepends the frozen **`Inherit the main chat's model`** choice (always
  present, even with zero servers) and then flattens only `is_active` servers' `enabled_models`,
  one entry per (server, model) pair labelled **`<server name> / <model>`** so two models on one
  server — and one model name on two servers — stay distinguishable; inactive servers and
  empty-`enabled_models` servers contribute nothing (DoD-6). `modelValue` re-encodes the draft's
  pair, or the inherit sentinel when it is unset, so the picker is never a blank box.
  `clientErrors` has exactly one rule — a blank/whitespace `name` under the **wire** key `name`;
  `errors` is `{...clientErrors, ...serverErrors}` (server wins); `canSubmit` is
  `submitStatus !== "loading"` and no client errors. `applyModelOption` is the pair's **only**
  writer: one `runInAction` sets **both** halves for a concrete option and clears **both** for the
  sentinel, for Mantine's `null` clear and for anything malformed — a half-set pair is unreachable
  from the UI (DoD-5). `submitSubAgentForm` follows the `serverFormDraft.ts:63-118` order: clear
  `serverErrors` + status `"loading"` → `createSubAgent(body)` when `subAgentId === null`, else
  `updateSubAgent(subAgentId, body)`, with **both** model fields always explicitly present
  (`null` + `null` = inherit, DoD-4) and both selections always sent, `[]` when empty →
  `catch`: `ApiError` → **409 → `{ name }`**, **400 → `{ name }` when the message identifies a
  blank name, else `{ form }`**, anything else → `{ form }`, status `"error"`, **return** (the
  modal stays open with the input intact and `onSaved` is not called — DoD-7); non-`ApiError` →
  aborted-guard, status `"error"`, **rethrow** → status `"ready"` → `onSaved()`. The `(server id,
  model name)` `<Select>` encoding and its inherit sentinel are module-private helpers
  (`INHERIT_VALUE` / `INHERIT_LABEL` / `encodeModelValue` / `decodeModelValue`) and never reach the
  wire. Imports added for the bodies: `runInAction`, `* as assistantConfigApi`, `ApiError`.
- `frontend/src/admin/components/sub-agents/SubAgentFormModal.tsx` — modal body filled: the `form`
  `<Alert color="red">` as the `Stack`'s **first child** (`ServerFormModal.tsx:56`), the name
  `<TextInput>` bound to `draft.errors.name`, the system-prompt `<Textarea>` (autosize,
  `minRows={6}` / `maxRows={16}`), the model `<Select>` driven by `draft.modelOptions` /
  `draft.modelValue` / `applyModelOption`, then the tool picker and the accessible-modes picker in
  the established idiom (`ScrollArea.Autosize mah={360}` → `Stack gap="xs"` → one `Checkbox` each;
  tools labelled `name` + `description`, modes labelled via `modeLabel`). Both toggles go through
  small inner handlers that **reassign a fresh `Set`**. An empty tool catalogue renders an
  explanatory dimmed line instead of a blank box, and nothing hard-codes a tool count (DoD-13); the
  mode picker degrades the same way. Save carries `disabled={!draft.canSubmit}`. There is **no
  `disabled` control** — disable/enable is a row action because it cascades. Imports added:
  `Alert`, `Checkbox`, `ScrollArea`, `Select`, `Text`, `TextInput`, `Textarea`, `modeLabel`,
  `applyModelOption`. Props, draft wiring and `handleSubmit` untouched.
- `frontend/src/admin/pages/SubAgentsPage.tsx` — the skeleton seams filled: `Model` / `Tools` /
  `Modes` `Table.Th` headers between `Name` and the `w={60}` action column; the disabled marking in
  the name cell (a `Badge` reading **Disabled** beside the name — the row is still listed, UC-097
  step 1 / US-114.AC-3); and the three matching cells — the model assignment as
  `<server name> / <model>` resolved against `state.servers` (degrading to the raw id for a
  since-removed server) or **inherits main chat** when both wire fields are `null`,
  `subAgent.tool_names.length`, and `subAgent.mode_keys.length`. Everything else — the
  state/effect/`refresh` wiring, `handleDisable` / `handleEnable`, the three-state form target in
  component-local `useState`, the `!loading && !error` table guard, the whole row `Menu`
  (`aria-label="Sub-agent actions"`, `Edit`, and the `disabled`-conditional `Enable` / `Disable`,
  **with no Delete item** — DoD-12), the conditional modal mount, and **both** the named and default
  exports — was frozen and is untouched. Import added: `Badge`.
- Gates: `cd frontend && npx tsc --noEmit` clean and `cd frontend && npm run build` (`tsc && vite
  build`) succeeds. `npm test` / `npm run test:types` not run — the verifier owns tests. No frozen
  signature changed, and no file outside the step's four Source files was modified.

## Skeleton

### Step 001 — frozen interface (2026-07-26)

All nine are `async`, session-free, and live in the module named. Call them as namespace
imports (`from app.db import sub_agents` → `await sub_agents.get_by_name(...)`).

- `backend/app/db/assistant_modes.py` — `async def update(row: AssistantMode) -> None` — new
- `backend/app/db/sub_agents.py` — `async def list_all() -> list[SubAgent]` — new
- `backend/app/db/sub_agents.py` — `async def get_by_name(name: str) -> SubAgent | None` — new
- `backend/app/db/sub_agents.py` — `async def update(row: SubAgent) -> None` — new
- `backend/app/db/mode_tools.py` — `async def delete_by_mode(mode_key: str) -> int` — new
- `backend/app/db/subagent_tools.py` — `async def delete_by_sub_agent(sub_agent_id: int) -> int` — new
- `backend/app/db/mode_subagents.py` — `async def list_by_sub_agent(sub_agent_id: int) -> list[ModeSubagent]` — new
- `backend/app/db/mode_subagents.py` — `async def delete_by_mode(mode_key: str) -> int` — new
- `backend/app/db/mode_subagents.py` — `async def delete_by_sub_agent(sub_agent_id: int) -> int` — new
- `backend/app/services/setup.py` — `async def import_database(archive_bytes: bytes) -> None` — **unchanged**; step 001's change here is behavioral only (the seed call added inside the body). No stub written; the existing signature and its `SetupError` refusal contract stand as-is.
- Unchanged and untouched by this step, for reference when writing calls: `assistant_modes.DEFAULT_MODE_KEYS: tuple[str, ...]`, `assistant_modes.seed_default_modes() -> None`, `assistant_modes.get_by_id(key: str) -> AssistantMode | None`, `assistant_modes.create(row: AssistantMode) -> AssistantMode`, `assistant_modes.list_all() -> list[AssistantMode]`, `sub_agents.create(row: SubAgent) -> SubAgent`, `sub_agents.get_by_id(sub_agent_id: int) -> SubAgent | None`, `mode_tools.create/get_by_id/list_by_mode`, `subagent_tools.create/get_by_id/list_by_sub_agent`, `mode_subagents.create/get_by_id/list_by_mode`, `setup.create_database(admin_username: str, password: str, password_confirm: str) -> User`.
- Notes on the two deliberate contract choices, so no one "fixes" them later: the two `update`s are **row-in / `None`-out** (mirroring `db/llm_servers.py:62`), and the three bulk deletes return a **count** (`int`), not `bool` — `0` is a normal, non-error result and must not raise.
- Caller-compile edits (out of Source-files scope): None. All nine symbols are additive; no existing signature changed.
- Compile gate: `cd backend && .venv/Scripts/python -c "import app.main"` clean (backend has no separate typecheck). Bodies `raise NotImplementedError`.

### Step 002 — frozen interface (2026-07-26)

Two new modules. **DTO field names are wire-exact `snake_case`** and are the contract step 006's
`.d.ts` mirrors. Every id crosses the wire as a `str`.

`backend/app/models/schemas/assistant_config.py` — DTOs only, no logic:

- `class ToolResponse(BaseModel)` — `name: str`, `description: str` — new. **Exactly two fields**;
  no `args_schema`, no `callable`, no key derived from either.
- `class ToolsListResponse(BaseModel)` — `items: list[ToolResponse]` — new
- `class AssistantModeResponse(BaseModel)` — `key: str`, `system_prompt: str | None`,
  `tool_names: list[str]`, `sub_agent_ids: list[str]`, `created_at: datetime | None`,
  `modified_at: datetime | None` — new
- `class AssistantModesListResponse(BaseModel)` — `items: list[AssistantModeResponse]` — new
- `class UpdateAssistantModeRequest(BaseModel)` — `system_prompt: str | None`,
  `tool_names: list[str]`, `sub_agent_ids: list[str]` — new. **All three required in the body**
  (no defaults — verified `is_required() == True` for all three); their *values* may be
  `null` / `[]`.

`backend/app/services/assistant_config.py`:

- `class AssistantConfigErrorReason(str, enum.Enum)` — new — members
  `mode_not_found = "mode-not-found"`, `unknown_tool = "unknown-tool"`,
  `unknown_sub_agent = "unknown-sub-agent"`, `sub_agent_disabled = "sub-agent-disabled"`
- `class AssistantConfigError(Exception)` — new — `__init__(self, reason: AssistantConfigErrorReason, message: str = "") -> None`, attributes `reason` / `message`
- `async def list_tools() -> ToolsListResponse` — new
- `async def _to_mode_response(mode: AssistantMode) -> AssistantModeResponse` — new, **internal**
- `async def list_modes() -> AssistantModesListResponse` — new
- `async def save_mode(mode_key: str, req: UpdateAssistantModeRequest) -> AssistantModeResponse` — new

Contract shapes fixed here so neither test-coder nor coder re-decides them:

- **Names.** The error type is feature-wide and mode-agnostic — `AssistantConfigErrorReason` /
  `AssistantConfigError`. Steps 003/004 **append members to this same enum**; they add no second
  error type and must not rename it.
- **`list_tools` is `async`** although it touches no DB — consistency with the rest of the service
  surface, per the step's "no `async` need beyond consistency". Callers `await` it.
- **DTO/param naming**: the catalogue reader is `list_tools` (mirrors `list_users` / `list_chats`),
  the DTOs are `ToolResponse` / `ToolsListResponse` / `AssistantModeResponse` /
  `AssistantModesListResponse` / `UpdateAssistantModeRequest` (the
  `LlmServerResponse` / `LlmServersListResponse` precedent). The saver's first parameter is
  `mode_key` (positional), the second `req`.
- **Plural DTO fields for singular columns**: the row columns are `mode_tool.tool_name` and
  `mode_subagent.sub_agent_id`; the DTO fields are `tool_names` and `sub_agent_ids`.
- **`sub_agent_ids` are strings on the wire, `int` in the row**; `key` / `mode_key` is a string
  everywhere and is emitted verbatim.
- **`_to_mode_response` is `async`** (it loads both link sets through `db/`) and takes the ORM
  `AssistantMode` row, not a key — it is the shared builder for the list and the save path.
- Timestamps are `datetime | None` (the columns are nullable), matching `LlmServerResponse`.
- No sub-agent DTO in this step, by design; the mode payload is id-only.
- `TOOL_REGISTRY` / `ToolDef` are **read** from `app.services.tools`, never redefined; `resolve_tools`
  and `build_tool_bindings` are not called. `models/schemas/tools.py` untouched.
- Caller-compile edits (out of Source-files scope): None. Both modules are new and nothing imports
  them yet (step 005 adds the route).
- Compile gate: `cd backend && .venv/Scripts/python -c "import app.main"` clean (backend has no
  separate typecheck). All four service bodies `raise NotImplementedError`, including the internal
  `_to_mode_response`.

### Step 003 — frozen interface (2026-07-26)

Both modules **already existed** (step 002) and are only extended: four new DTOs, six new enum
members, five new service functions. Nothing from step 002 was renamed, re-signed or re-bodied —
the mode surface is untouched. **DTO field names are wire-exact `snake_case`** and are the contract
step 006's `.d.ts` mirrors. Every id crosses the wire as a `str`.

`backend/app/models/schemas/assistant_config.py` — DTOs only, no logic. All four carry
`model_config = ConfigDict(protected_namespaces=())` where they hold `model_name` (the response and
both requests do; the list envelope does not need it):

- `class SubAgentResponse(BaseModel)` — new — `model_config = ConfigDict(protected_namespaces=())`,
  then `id: str`, `name: str`, `system_prompt: str` (**non-nullable**, unlike the mode's),
  `disabled: bool`, `llm_server_id: str | None`, `model_name: str | None`, `tool_names: list[str]`,
  `mode_keys: list[str]`, `created_at: datetime | None`, `modified_at: datetime | None`
- `class SubAgentsListResponse(BaseModel)` — new — `items: list[SubAgentResponse]`
- `class CreateSubAgentRequest(BaseModel)` — new — `model_config = ConfigDict(protected_namespaces=())`,
  then `name: str`, `system_prompt: str`, `llm_server_id: str | None`, `model_name: str | None`
- `class UpdateSubAgentRequest(BaseModel)` — new — identical four fields and the same
  `model_config`. **No `disabled` field** (step 004 owns enable/disable).

`backend/app/services/assistant_config.py`:

- `class AssistantConfigErrorReason(str, enum.Enum)` — **changed** (extended, not renamed, not
  replaced): the step-002 members `mode_not_found` / `unknown_tool` / `unknown_sub_agent` /
  `sub_agent_disabled` stand unchanged, and six members are appended —
  `sub_agent_not_found = "sub-agent-not-found"`, `name_taken = "name-taken"`,
  `blank_name = "blank-name"`, `invalid_model_pair = "invalid-model-pair"`,
  `unknown_or_inactive_server = "unknown-or-inactive-server"`,
  `model_not_enabled = "model-not-enabled"`. Ten members total.
- `class AssistantConfigError(Exception)` — **unchanged**; `__init__(self, reason:
  AssistantConfigErrorReason, message: str = "") -> None` is reused verbatim for every sub-agent
  refusal. No second error type exists.
- `def _parse_sub_agent_id(sub_agent_id: str) -> int` — new, **internal**, **sync** (no DB access;
  mirrors `services/chats.py:133 _parse_chat_id`)
- `async def _validate_model_pair(llm_server_id: str | None, model_name: str | None) -> int | None`
  — new, **internal**
- `async def _to_sub_agent_response(sub_agent: SubAgent) -> SubAgentResponse` — new, **internal**
- `async def list_sub_agents() -> SubAgentsListResponse` — new
- `async def create_sub_agent(req: CreateSubAgentRequest) -> SubAgentResponse` — new
- `async def update_sub_agent(sub_agent_id: str, req: UpdateSubAgentRequest) -> SubAgentResponse`
  — new

Contract shapes fixed here so neither test-coder nor coder re-decides them:

- **Every request field is required in the body — no defaults** (verified `is_required() == True`
  for all four on both requests, matching step 002's `UpdateAssistantModeRequest`). A caller must
  pass the model pair **explicitly**, including the inherit case:
  `CreateSubAgentRequest(name=..., system_prompt=..., llm_server_id=None, model_name=None)`.
  Omitting either is a Pydantic `ValidationError`, not a defaulted `None`. This is the full-replace
  shape (`context.md` → "Writes are full-replace"), deliberately *not*
  `CreateChatRequest`/`UpdateChatRequest`'s all-defaulted partial shape. Step 004's two new list
  fields are the only ones that will carry a default (empty), so this record stays true afterwards.
- **`update_sub_agent` takes `sub_agent_id: str` and the service owns the parse**, via the frozen
  internal `_parse_sub_agent_id`. An id that is not well-formed is treated as a **missing**
  sub-agent — `sub_agent_not_found` → **404**, never a 422 and never a `ValueError` escaping as a
  500 (`005.admin-routes.md` → "Path params" and its DoD-7; `context.md:214` "Every id is a `str`
  at the JSON boundary"). This **deliberately overrides** the `routes/admin/llm_servers.py:103
  server_id: int` precedent for this feature: an `int` path param would put the malformed-id
  decision in FastAPI (422) or the `int()` call in `routes/`, and `routes/` is HTTP-only. `db/` is
  untouched — `sub_agents.get_by_id(sub_agent_id: int)` stays `int`, so the string→int edge is
  exactly this service boundary. **Step 004's disable/enable setter takes the same `str` shape** and
  reuses `_parse_sub_agent_id`.
  - *Reason vocabulary, so the two parse failures are not conflated:* an unparsable id **in the
    path** (the addressed resource) → `sub_agent_not_found` (404); an unparsable id **inside a
    mode's `sub_agent_ids` body list** (a referenced entity) → `unknown_sub_agent` (400), which is
    step 002's already-implemented behavior and is unchanged.
  - *Re-freeze note (2026-07-26):* this entry originally froze `sub_agent_id: int` with no parse
    helper. That was unsatisfiable against step 005's DoD-7 without putting business logic in
    `routes/`; corrected before the test-coder bound to it. Nothing else in the step-003 freeze
    changed.
- **The mode-side link list is named `mode_keys`** on the sub-agent DTO — plural DTO field for the
  singular `mode_subagent.mode_key` column, matching step 002's `tool_names` / `sub_agent_ids`.
  There is no `accessible_modes` anything.
- **Both link lists ship in the response from this step**, empty until step 004 writes them, so the
  response shape never changes. Assert present-and-empty here; do not assert populated.
- **`system_prompt: str` is non-nullable on all three sub-agent DTOs** (the column is required),
  unlike `AssistantModeResponse.system_prompt`. `""` is accepted and stored verbatim — only `name`
  is blank-checked.
- **`_validate_model_pair` is a local copy**, `async` (it reads `db.llm_servers`), with
  `services/chats.py:142-177`'s exact rule order; `json.loads(server.enabled_models)` is decoded at
  the service edge. Nothing is imported from `services/chats.py` and `chats.py` is not refactored.
- **Three internals are frozen** (`_parse_sub_agent_id`, `_validate_model_pair`,
  `_to_sub_agent_response`). The name trim + blank + collision check is inline in the two public
  functions; if the coder prefers a further private helper that is their call, provided no frozen
  signature changes.
- **`name_taken` is the feature's only 409** (`services/admin.py:109-113` precedent); step 005 maps
  `mode_not_found` / `sub_agent_not_found` → 404, `name_taken` → 409, the rest → 400.
- Caller-compile edits (out of Source-files scope): None. Every symbol is additive; the enum grew by
  appending members, so step 002's four members keep their values and nothing that reads them
  changed. No route imports this service yet (step 005 adds it).
- Compile gate: `cd backend && .venv/Scripts/python -c "import app.main"` clean (backend has no
  separate typecheck), and the four DTOs import clean under `-W error` — the `protected_namespaces`
  setting is doing its job, no `model_` warning. All five new service bodies
  `raise NotImplementedError`, including all three internals; step 002's four bodies were left
  implemented and untouched.

### Step 004 — frozen interface (2026-07-26)

Both modules are only **extended**: two request DTOs gain two fields each, and the service gains
three functions. **No new enum member** — `mode_not_found` (step 002) is reused for an unknown
`mode_key` in a sub-agent's mode selection, alongside the already-defined `unknown_tool`,
`sub_agent_disabled` and `sub_agent_not_found`; the enum still has **ten** members with unchanged
values. Nothing from steps 002/003 was renamed, re-signed or re-bodied.

`backend/app/models/schemas/assistant_config.py` — DTOs only, no logic:

- `class CreateSubAgentRequest(BaseModel)` — **changed** (extended): the four step-003 fields stand
  unchanged, and two are appended — `tool_names: list[str] = []`, `mode_keys: list[str] = []`
- `class UpdateSubAgentRequest(BaseModel)` — **changed** (extended): identical two additions
- `class SubAgentResponse(BaseModel)` — **unchanged**. It already carries `tool_names` and
  `mode_keys` (step 003); the response shape does not move in this step. `SubAgentsListResponse`,
  and every mode-side DTO, likewise untouched.

`backend/app/services/assistant_config.py`:

- `async def _replace_sub_agent_tools(sub_agent_id: int, tool_names: list[str]) -> None` — new,
  **internal**
- `async def _replace_sub_agent_modes(sub_agent_id: int, mode_keys: list[str]) -> None` — new,
  **internal**
- `async def set_sub_agent_disabled(sub_agent_id: str, disabled: bool) -> SubAgentResponse` — new
- `async def create_sub_agent(req: CreateSubAgentRequest) -> SubAgentResponse` — **signature
  unchanged**; only the request's shape grew. Same for
  `async def update_sub_agent(sub_agent_id: str, req: UpdateSubAgentRequest) -> SubAgentResponse`.
  Both bodies remain step 003's and do **not** yet consume the two new lists — that wiring is the
  coder's body work, not a signature change.
- `class AssistantConfigErrorReason` / `class AssistantConfigError` / `_parse_sub_agent_id` /
  `_validate_model_pair` / `_to_sub_agent_response` / `list_sub_agents` — **unchanged**.

Contract shapes fixed here so neither test-coder nor coder re-decides them:

- **The two new request fields are the feature's only defaulted fields** (verified
  `is_required() == False` for both on both requests; the other four remain `True`). This is the
  deliberate divergence step 003's record anticipated: an omitted selection means *no selection*, so
  step 003's tests and any caller that passes only the four scalars keep working and get a sub-agent
  with no links. The default is a `[]` literal — Pydantic deep-copies it per instance (verified: two
  instances do not share the list), so it is **not** a shared-mutable bug and must not be "fixed".
- **Field names are `tool_names` and `mode_keys`** — the same names the response already uses, so
  request and response are symmetric and step 006's `.d.ts` mirrors one vocabulary. Not
  `accessible_modes`, not `mode_key_list`.
- **The two replace-set helpers write; they do not validate.** Validation of the tool names and of
  the mode keys, plus the disabled guard, is **hoisted into the two callers** and must complete
  before the *first* write of the save. Reason, recorded so it is not "simplified" back: a
  self-contained validate-then-write helper cannot satisfy "every validation before any write" —
  `create_sub_agent` must write the `SubAgent` row first (it needs the snowflake id) and a save
  replaces *two* link sets, so a refusal discovered inside the second helper would leave a stored
  row or a half-replaced selection, which DoD-6 forbids (`004.context.md` → Gotchas). The step's
  interface intent describes validation as part of each replace-set *operation*; that is preserved
  as an operation, split across caller-side validation and these writers. Whether the caller-side
  validation is inline or in a further private helper is the **coder's call**, provided no frozen
  signature changes — the step-003 precedent.
- **De-duplication lives in the two helpers**, `dict.fromkeys` over the requested order — the
  `save_mode` steps 5–6 idiom — so `uq_subagent_tool_sub_agent_id_tool_name` and
  `uq_mode_subagent_mode_key_sub_agent_id` cannot be violated by a repeated value.
- **The helpers take `sub_agent_id: int`** (the row id), not the wire string: they are internal and
  run after the parse or after `sub_agents.create`. Only the public
  `set_sub_agent_disabled` takes `sub_agent_id: str`, reusing `_parse_sub_agent_id` exactly as
  `update_sub_agent` does — an ill-formed id and a missing row are both `sub_agent_not_found` (404),
  never a 422 and never an escaping `ValueError`. This is the shape the step-003 record already
  anticipated.
- **The setter is a flag setter, not a toggle** — the caller passes the desired `disabled` value, so
  disabling an already-disabled sub-agent is a valid no-op save. It returns the **rebuilt
  `SubAgentResponse`**, like every other writer in this service.
- **The disabled guard is `update_sub_agent`'s, and it keys on emptiness**: a **non-empty**
  `mode_keys` on a currently `disabled` row → `sub_agent_disabled`; an **empty** one is accepted, so
  a disabled sub-agent's name, prompt, tools and model stay editable (US-114.AC-2, UC-097). No
  helper is frozen for it — it is one condition in the validation phase. `create_sub_agent` needs no
  guard: a created sub-agent is always `disabled=False`.
- **No hard delete exists or may be added** — no `db.sub_agents.delete`, no service delete, no
  delete route (`context.md` → scope decision 6). Disable is the only removal-shaped operation, and
  it keeps the row, keeps the `subagent_tool` rows and keeps the model pair; only the
  `mode_subagent` rows go, and re-enabling restores none of them.
- Caller-compile edits (out of Source-files scope): **None.** The three service symbols are
  additive, and both DTO additions are **defaulted**, so every existing construction site —
  including step 003's tests — still compiles and behaves identically. No route imports this service
  yet (step 005 adds it).
- Compile gate: `cd backend && .venv/Scripts/python -c "import app.main"` clean (backend has no
  separate typecheck), and both requests import and instantiate clean under `-W error` — no
  `model_` warning, `protected_namespaces` still doing its job. All three new bodies
  `raise NotImplementedError`; steps 002's and 003's bodies were left implemented and untouched,
  including `create_sub_agent` / `update_sub_agent`, which therefore still ignore the two new
  fields until the coder wires them.

### Step 005 — frozen interface (2026-07-26)

One new module plus two lines in the composition root. The service surface (steps 002–004) is
**unchanged** — no signature there was touched, and no DTO moved. `routes/` stays HTTP-only: every
handler parses, calls exactly one `services/assistant_config` function, and returns.

`backend/app/routes/admin/assistant_config.py` — new module:

- `router = APIRouter(prefix="/api/admin/assistant-config", tags=["admin-assistant-config"])` — new.
  The router owns its prefix; `include_router` adds none (the `llm_servers.py:44` shape).
- `_ASSISTANT_CONFIG_ERROR_STATUS: dict[assistant_config_service.AssistantConfigErrorReason, int]` —
  new, module-level, **real (not a stub)**. All **ten** reasons mapped, verified exhaustive against
  the enum: `mode-not-found` → 404, `sub-agent-not-found` → 404, `name-taken` → **409**,
  `blank-name` / `invalid-model-pair` / `unknown-or-inactive-server` / `model-not-enabled` /
  `unknown-tool` / `unknown-sub-agent` / `sub-agent-disabled` → 400. No 403 entry — that comes from
  `require_role` itself.
- `def _map_assistant_config_error(err: assistant_config_service.AssistantConfigError) -> HTTPException`
  — new, **real (not a stub)**, the `llm_servers.py:55-61` shape (`status_code` from the map,
  `detail=err.message`).

The eight handlers, in **declaration order** (order is load-bearing — static before `{param}` within
each family). Every one carries the trailing
`caller: User = Depends(auth_service.require_role(UserRole.admin))` parameter, which is **part of the
frozen signature**:

- `@router.get("/tools")` → `async def list_tools(caller=...) -> ToolsListResponse` — new
- `@router.get("/modes")` → `async def list_modes(caller=...) -> AssistantModesListResponse` — new
- `@router.put("/modes/{mode_key}")` →
  `async def save_mode(mode_key: str, payload: UpdateAssistantModeRequest, caller=...) -> AssistantModeResponse` — new
- `@router.get("/sub-agents")` → `async def list_sub_agents(caller=...) -> SubAgentsListResponse` — new
- `@router.post("/sub-agents", status_code=status.HTTP_201_CREATED)` →
  `async def create_sub_agent(payload: CreateSubAgentRequest, caller=...) -> SubAgentResponse` — new
- `@router.put("/sub-agents/{sub_agent_id}")` →
  `async def update_sub_agent(sub_agent_id: str, payload: UpdateSubAgentRequest, caller=...) -> SubAgentResponse` — new
- `@router.post("/sub-agents/{sub_agent_id}/disable")` →
  `async def disable_sub_agent(sub_agent_id: str, caller=...) -> SubAgentResponse` — new. **No body.**
- `@router.post("/sub-agents/{sub_agent_id}/enable")` →
  `async def enable_sub_agent(sub_agent_id: str, caller=...) -> SubAgentResponse` — new. **No body.**

`backend/app/main.py`:

- `from app.routes.admin import assistant_config as admin_assistant_config` — added beside the other
  admin router imports (alphabetically before `db as admin_db`).
- `app.include_router(admin_assistant_config.router)` — added **bare**, last in the mount block
  (the `main.py:82` shape). Nothing else in `main.py` changed; `lifespan`, logging and the seven
  existing mounts are untouched.

Contract shapes fixed here so neither test-coder nor coder re-decides them:

- **`sub_agent_id` is `str` on all four param routes, handed to the service verbatim.** No `int`
  annotation, no `int()` in `routes/`, no `Path(...)` constraint, no regex. An ill-formed id must
  reach `assistant_config_service` and come back as `sub_agent_not_found` → **404**, never FastAPI's
  422 and never a 500 (the step's DoD-7; `context.md:214` "Every id is a `str` at the JSON
  boundary"). This **deliberately overrides** the `routes/admin/llm_servers.py:103 server_id: int`
  precedent for this feature, exactly as the step-003 freeze anticipated. `mode_key` is likewise a
  plain `str` (the mode's natural PK) with no enum or `Literal` narrowing — an unknown key is the
  service's `mode_not_found` → 404, not a 422.
- **`POST /sub-agents` → 201**, `status_code=status.HTTP_201_CREATED`. Not specified by the step;
  frozen from the codebase-wide create precedent (`routes/admin/llm_servers.py:72`,
  `routes/admin/users.py:68`, `routes/books.py:77`, `routes/chats.py:131` — every create POST is
  201). **The other three POSTs are not creates and return the default 200** — disable/enable are
  state transitions returning the rebuilt `SubAgentResponse`, and 204 would throw away the body the
  step's table requires ("the updated sub-agent DTO").
- **Disable and enable are two separate zero-body endpoints**, not one endpoint with a
  `{"disabled": bool}` payload — the step's table fixes both paths and neither has a Body column.
  Each calls `set_sub_agent_disabled(sub_agent_id, True | False)`; the boolean is the route's
  constant, and there is no request DTO for either (none exists in
  `models/schemas/assistant_config.py`, and none may be added — that module is not this step's).
- **Response models are return annotations**; `response_model=` appears nowhere. Every response type
  is an existing step-002/003 DTO — this step adds **no** schema and touches
  `models/schemas/assistant_config.py` not at all.
- **`caller` is bound but not threaded into the service.** Every service function's signature is
  caller-free; the dependency exists solely to gate (non-admin → 403, no token → 401, both raised
  inside `auth_service.require_role` / `get_current_user`). **No handler raises 403 or 401**, and the
  status map has no entry for either.
- **Handler names shadow the service function names on purpose** (`list_tools`, `list_modes`,
  `save_mode`, `list_sub_agents`, `create_sub_agent`, `update_sub_agent`) — the service is
  namespace-imported as `assistant_config_service`, so there is no collision; `disable_sub_agent` /
  `enable_sub_agent` both wrap the single `set_sub_agent_disabled`.
- **Declaration order is frozen and load-bearing**: `/tools`, `/modes`, `/modes/{mode_key}`,
  `/sub-agents` (GET then POST), `/sub-agents/{sub_agent_id}`, `.../disable`, `.../enable`. Do not
  reorder. No `/sub-agents/{sub_agent_id}/{anything}` catch-all route exists, and none may be added.
- **No single-mode GET and no DELETE anywhere** — both deliberate (`context.md` → scope decision 6;
  UC-097 "No hard delete"). Verified against the generated OpenAPI: the family exposes exactly seven
  paths / eight operations and **zero** `delete` operations.
- Caller-compile edits (out of Source-files scope): **None.** The module is new and purely additive;
  the two `main.py` lines are inside this step's Source files.
- Compile gate: `cd backend && .venv/Scripts/python -c "import app.main"` clean (backend has no
  separate typecheck). Additionally verified by introspection — the eight registrations resolve to
  the paths/methods above with `create_sub_agent` at 201, the reason map covers all ten enum members
  with no gap, and `app.openapi()` shows the family mounted at the right prefix with no DELETE. All
  eight handler bodies are `raise NotImplementedError`; the map and `_map_assistant_config_error` are
  real, per the `routes/admin/llm_servers.py` skeleton precedent. No pytest run.

### Step 006 — frozen interface (2026-07-26)

The first frontend surface. Four new files plus two append-only edits. **The types, the nav
entries, the routes and the two page shells are written concretely** — they *are* the deliverable.
Only the api module's function **bodies** are stubs (`throw new Error("not implemented: <fn>")`).
Nothing pre-existing was renamed, re-signed or reformatted: `AdminNavItem`, `ADMIN_NAV_ITEMS`'
`readonly` type, `isNavItemActive`, `AdminNav.tsx` and the three existing routes are untouched.

`frontend/src/types/assistantConfig.d.ts` — new, **types only, zero runtime values**. Wire-exact
`snake_case`, mirroring steps 002–004's DTOs one-for-one; **every id is `string`**; both timestamps
use `ISODateString` from `./common`. **No list-envelope interface exists** — the `{ items: [...] }`
envelopes are unwrapped in the api module (`context.md` → frontend constraints):

- `export interface AssistantTool { name: string; description: string }` — new (mirrors
  `ToolResponse`; **exactly two fields** — no `args_schema`, no `callable`)
- `export interface AssistantMode { key: string; system_prompt: string | null; tool_names: string[]; sub_agent_ids: string[]; created_at: ISODateString | null; modified_at: ISODateString | null }` — new (mirrors `AssistantModeResponse`)
- `export interface UpdateAssistantModeRequest { system_prompt: string | null; tool_names: string[]; sub_agent_ids: string[] }` — new. **All three required** (no `?`), matching the backend's
  `is_required() == True`; their *values* may be `null` / `[]`.
- `export interface SubAgent { id: string; name: string; system_prompt: string; disabled: boolean; llm_server_id: string | null; model_name: string | null; tool_names: string[]; mode_keys: string[]; created_at: ISODateString | null; modified_at: ISODateString | null }` — new (mirrors
  `SubAgentResponse`; `system_prompt` is **non-nullable**, unlike the mode's)
- `export interface CreateSubAgentRequest { name: string; system_prompt: string; llm_server_id: string | null; model_name: string | null; tool_names?: string[]; mode_keys?: string[] }` — new
- `export interface UpdateSubAgentRequest { … identical six fields … }` — new. **No `disabled`
  field** — enable/disable are their own zero-body endpoints.

`frontend/src/api/assistantConfig.ts` — new. `const BASE = "/api/admin/assistant-config"`
(module-private). Namespace-imported (`import * as assistantConfigApi from "../../api/assistantConfig"`);
`signal?` is the **trailing** argument of all eight endpoint functions:

- `export const MODE_LABELS: Record<string, string>` — new, **real (not a stub)**, the
  `api/llmServers.ts:32 BACKEND_OPTIONS` precedent. Total over the backend's five
  `DEFAULT_MODE_KEYS`: `edit-character` → "Edit character", `edit-location` → "Edit location",
  `edit-fact` → "Edit fact", `write-chapter` → "Write chapter", `close-chapter` → "Close chapter".
- `export function modeLabel(key: string): string` — new, **stub**. The degrade-to-raw-key lookup
  (DoD-7's "returns the raw key for an unknown one"); **sync**, not `async`.
- `export async function listTools(signal?: AbortSignal): Promise<AssistantTool[]>` — new
- `export async function listModes(signal?: AbortSignal): Promise<AssistantMode[]>` — new
- `export async function saveMode(modeKey: string, body: UpdateAssistantModeRequest, signal?: AbortSignal): Promise<AssistantMode>` — new
- `export async function listSubAgents(signal?: AbortSignal): Promise<SubAgent[]>` — new
- `export async function createSubAgent(body: CreateSubAgentRequest, signal?: AbortSignal): Promise<SubAgent>` — new
- `export async function updateSubAgent(id: string, body: UpdateSubAgentRequest, signal?: AbortSignal): Promise<SubAgent>` — new
- `export async function disableSubAgent(id: string, signal?: AbortSignal): Promise<SubAgent>` — new
- `export async function enableSubAgent(id: string, signal?: AbortSignal): Promise<SubAgent>` — new

`frontend/src/admin/components/shell/navItems.ts` — **changed, append-only**:

- `ADMIN_NAV_ITEMS` — **changed**: two entries appended after `/database`, in this order —
  `{ path: "/assistant-modes", label: "Assistant modes", icon: IconSparkles }` then
  `{ path: "/sub-agents", label: "Sub-agents", icon: IconRobot }`. Neither carries `exact` (single
  segment, so the `/`-delimited descendant rule is right for them). Five entries total, in display
  order: Users `/`, LLM Servers `/llm-servers`, Database `/database`, Assistant modes, Sub-agents.
- `IconSparkles` / `IconRobot` added to the existing `@tabler/icons-react` import (both verified
  present in the installed package). `export interface AdminNavItem`,
  `ADMIN_NAV_ITEMS: readonly AdminNavItem[]` and `isNavItemActive(pathname, item)` — **unchanged**.
  Only the array's doc comment moved ("three" → "five").

`frontend/src/admin/routes.tsx` — **changed, append-only**: two flat `<Route>` elements added
**above** `path="*"`, in nav order — `<Route path="/assistant-modes" element={<AssistantModesPage />} />`
then `<Route path="/sub-agents" element={<SubAgentsPage />} />` — plus their two imports. No
`<Outlet/>`, no layout route, no nested route; the three existing routes and the catch-all are
untouched.

`frontend/src/admin/pages/AssistantModesPage.tsx` / `SubAgentsPage.tsx` — new, **real (not stubs)**:

- `export const AssistantModesPage = observer(function AssistantModesPage() …)` +
  `export default AssistantModesPage;` — new
- `export const SubAgentsPage = observer(function SubAgentsPage() …)` +
  `export default SubAgentsPage;` — new
- Each renders exactly `Container size="lg" py="md"` → `Title order={3}` ("Assistant modes" /
  "Sub-agents"). No props, no page-state class, no `useState`, no `useEffect`, no api import.

Contract shapes fixed here so neither test-coder nor coder re-decides them:

- **Both pages are exported twice — named *and* default.** The step file says "default-exported",
  but **every** page in this repo is a named `export const <Name>Page = observer(...)` and there is
  no `export default` anywhere in `frontend/src`. Rather than pick one and break the other, both
  exist: `routes.tsx` imports the **named** export (matching its three sibling imports), and the
  default satisfies the step's stated shape. Either binding compiles for the test-coder; steps
  007/008 must keep **both** when they replace the shells. This is the only contract shape where the
  plan and the codebase disagreed.
- **Type names follow `types/llmServers.d.ts`, not the backend class names**: the row types are
  `AssistantTool` / `AssistantMode` / `SubAgent` (the `LlmServer` precedent — no `…Response`
  suffix), while the request types keep the backend names verbatim
  (`UpdateAssistantModeRequest` / `CreateSubAgentRequest` / `UpdateSubAgentRequest`, the
  `CreateLlmServerRequest` precedent). `AssistantModesListResponse` / `SubAgentsListResponse` /
  `ToolsListResponse` have **no frontend counterpart** by design.
- **Optionality mirrors the backend's `is_required()` exactly.** `tool_names?` and `mode_keys?` are
  the **only** optional fields in the whole file — they are the backend's only defaulted fields
  (step 004's record). The four sub-agent scalars and all three mode-update fields are required, so
  the model pair must be passed explicitly, `null` + `null` meaning *inherit*.
- **`mode_keys` on the sub-agent, `sub_agent_ids` on the mode** — the two ends of the same
  `mode_subagent` row set, named exactly as the backend DTOs name them. No `accessible_modes`.
- **The label surface is a const *plus* a function.** A bare `Record` cannot "return the raw key for
  an unknown one" (DoD-7), so the degrade lives in `modeLabel(key)`. `MODE_LABELS` is frozen
  **real** (data, the step-005 status-map precedent) and `modeLabel` is frozen **stubbed**, so
  DoD-7's unknown-key half is honestly red. Callers should read labels through `modeLabel`, not by
  indexing the record.
- **`modeLabel` is sync**; every endpoint function is `async` and returns a `Promise`.
- **Envelope unwrapping is body work.** `listTools` / `listModes` / `listSubAgents` return plain
  arrays; the coder writes `request<{ items: … }>(…)` with an **inline** response type. Nothing may
  add an envelope interface to the `.d.ts`.
- **`ApiError` is neither caught nor re-wrapped in this module** (DoD-6) — `request` throws it and
  it propagates verbatim, so callers branch on `status` (409 name-taken vs 400).
- **Paths interpolate the string id/key directly** — `${BASE}/modes/${modeKey}`,
  `${BASE}/sub-agents/${id}`, `.../disable`, `.../enable`. No parse, no coercion, no encoding
  helper. `disableSubAgent` / `enableSubAgent` send **no body** (step 005: zero-body POSTs), and
  `createSubAgent` is the family's only 201 — a status the api layer does not inspect.
- **`import { request } from "./client";` is deliberately absent from the skeleton** and is the
  coder's to add: `noUnusedLocals` rejects an import no stub body uses. For the same reason the
  eight stub messages interpolate `BASE` and each body opens with `void <param>;` lines — both are
  scaffolding the coder deletes when filling the body, and neither is part of the frozen contract.
- Caller-compile edits (out of Source-files scope): **None.** Every change is additive; no existing
  signature moved, and `AdminNav.tsx` renders the two new entries generically with no edit.
- Compile gate: `cd frontend && npx tsc --noEmit` clean. `npm test` / `npm run build` deliberately
  **not** run (the verifier owns tests); the two pre-existing nav specs
  (`tests/admin/navItems.test.ts`, `tests/admin/AdminNav.test.tsx`) are expected to fail against the
  now-five-entry array until the test-coder extends their pins — that is this step's Test-files
  scope, not the skeleton's.

### Step 007 — frozen interface (2026-07-26)

Three new files plus a full replacement of the step-006 `AssistantModesPage` shell. Nothing outside
this step's Source files was touched; the step-006 api module, the `.d.ts`, `navItems.ts` and
`routes.tsx` are **unchanged**.

`frontend/src/admin/pages/assistantModesPageState.ts` — new:

- `export class AssistantModesPageState` — new. `makeAutoObservable(this)` in a **zero-argument
  constructor**; **no methods, no computeds** (`llmServersPageState.ts:18-26`). **Three** async
  trios, field names frozen:
  - `modes: AssistantMode[] = []`, `modesStatus: "idle" | "loading" | "ready" | "error" = "idle"`, `modesError: string | null = null`
  - `tools: AssistantTool[] = []`, `toolsStatus: "idle" | "loading" | "ready" | "error" = "idle"`, `toolsError: string | null = null`
  - `subAgents: SubAgent[] = []`, `subAgentsStatus: "idle" | "loading" | "ready" | "error" = "idle"`, `subAgentsError: string | null = null`
- `export async function loadModesPage(state: AssistantModesPageState, signal?: AbortSignal): Promise<void>`
  — new, **stub**. The only effect function in the module.

`frontend/src/admin/components/assistant-config/modeEditorDraft.ts` — new:

- `export class ModeEditorDraft` — new. `constructor(mode: AssistantMode, tools: AssistantTool[], subAgents: SubAgent[])`, `makeAutoObservable(this)` last. Fields:
  `systemPrompt: string = ""`, `selectedTools: Set<string>`, `selectedSubAgents: Set<string>`,
  `tools: AssistantTool[]`, `subAgents: SubAgent[]`, `serverErrors: Record<string, string> = {}`,
  `submitStatus: "idle" | "loading" | "ready" | "error" = "idle"`.
- `get clientErrors(): Record<string, string>` — new, **stub** (keys are **wire** field names)
- `get errors(): Record<string, string>` — new, **stub** (`{...clientErrors, ...serverErrors}`, server wins)
- `get canSubmit(): boolean` — new, **stub** (`submitStatus !== "loading"` and no client errors)
- `export async function submitModeEditor(draft: ModeEditorDraft, modeKey: string, onSaved: () => void, signal?: AbortSignal): Promise<void>`
  — new, **stub**

`frontend/src/admin/components/assistant-config/ModeEditorModal.tsx` — new:

- `interface ModeEditorModalProps` — **module-private** (not exported, the `ServerFormModal.tsx:17`
  precedent) — `opened: boolean`, `mode: AssistantMode`, `tools: AssistantTool[]`,
  `subAgents: SubAgent[]`, `onClose: () => void`, `onSaved: () => void`
- `export const ModeEditorModal = observer(function ModeEditorModal({...}: ModeEditorModalProps) …)` — new

`frontend/src/admin/pages/AssistantModesPage.tsx` — **changed** (the step-006 shell replaced; both
exports preserved):

- `export const AssistantModesPage = observer(function AssistantModesPage() …)` — **changed**
  (was a fetch-free `Container` + `Title` shell); still **no props**.
- `export default AssistantModesPage;` — **unchanged**, deliberately kept.

Contract shapes fixed here so neither test-coder nor coder re-decides them:

- **The loader is named `loadModesPage` and takes `(state, signal?)`** — one call loads all three
  resources in parallel and commits all three trios. There is **no second loader** and **no mutation
  action in page state**: a save runs from the draft (`submitModeEditor`) and the page re-calls
  `loadModesPage` through its local `refresh()`.
- **Three separate error fields, not one.** The page's single red `Text` renders
  `state.modesError ?? state.toolsError ?? state.subAgentsError` — written concretely here so DoD-2
  has one place to look.
- **The table is rendered only when `!loading && !error`.** The `LlmServersPage` precedent renders
  its table on error too; that would contradict DoD-2 ("an error message **and no table**"), so this
  page deliberately diverges. `loading` is `modesStatus === "idle" || modesStatus === "loading"`.
- **The edit target is component-local `useState<AssistantMode | undefined>(undefined)`** —
  `undefined` = closed, a mode = editing. **No `null` case** and **no header action button**: modes
  are seeded and fixed, nothing is created (`007.context.md` → differences table).
- **The row's edit control is an `ActionIcon` carrying `aria-label="Edit mode"`** in the trailing
  `w={60}` column, one per row. The accessible name is **part of the frozen contract** — it is how a
  test opens the editor; do not remove or reword it. (This is a deliberate addition over the
  `LlmServersPage` `Menu` precedent, which offers no accessible name.)
- **The modal is mounted conditionally** (`{editTarget !== undefined && <ModeEditorModal opened … />}`),
  so every open constructs a fresh `ModeEditorDraft`. `onSaved={refresh}`; the modal closes itself
  when `draft.submitStatus === "ready"` (the `ServerFormModal.tsx:42-46` handler shape, written
  concretely here).
- **The draft stores `tools` and `subAgents`.** The intent mandates both constructor parameters;
  storing them is what makes them meaningful (and satisfies `noUnusedParameters`). The pickers may
  read either `draft.tools` / `draft.subAgents` or the modal's props — they are the same arrays.
- **`selectedTools` holds tool *names*; `selectedSubAgents` holds sub-agent *ids* (wire strings).**
  Both are `Set<string>` in the draft and `string[]` on the wire — serialize with `Array.from(...)`
  at submit time only. Every toggle **reassigns a fresh `Set`** in the component's `onChange`; there
  is no toggle method on the draft (`modelsModalDraft.ts:12-13`).
- **Empty prompt is sent as `null`** (`draft.systemPrompt || null`), and an empty selection is sent
  as `[]` — never omitted. All three body fields are required by
  `UpdateAssistantModeRequest` (step 006's `.d.ts`).
- **Every server status maps to the single `form` key** — 400 (unknown tool / unknown or disabled
  sub-agent), 404, and anything else. This modal has no field a server error lands on: all of those
  mean the page's cached catalogue or sub-agent list is stale, a whole-form condition
  (`007.context.md` → "Error mapping for this modal"). `form` renders as an `<Alert color="red">` at
  the modal top (`ServerFormModal.tsx:56`).
- **`clientErrors` is normally empty** — a mode has no required field; an empty prompt and empty
  selections are all valid (`context.md` → scope decision 1, US-110.AC-4). It is frozen as a
  computed anyway to keep the draft shape uniform. It is **stubbed, not returned empty**, so it
  cannot accidentally satisfy an assertion.
- **`ModeEditorModalProps` is not exported** and neither is any prop type — bind to the component,
  not to the interface.

Where the skeleton/behavior line was drawn (so the coder knows exactly what is left):

- **Written concretely (wiring/structure, no domain behavior):** every class field and initializer,
  both constructors, all four external/computed signatures, the page's `useState` + `useEffect` +
  `refresh` + edit-target + conditional modal mount, the page layout down to
  `Container` → header `Group`/`Title` → error `Text c="red"` → `Loader` **or**
  `Table striped highlightOnHover` with the `Mode` column, the `w={60}` action column and the row
  `key`, the modal's `Modal`/`Stack`/read-only `modeLabel(mode.key)` heading/Cancel/Save shell and
  its `handleSubmit` (abort controller → `submitModeEditor` → close on `"ready"`).
- **Left to the coder (marked `SKELETON SEAM` in-file):** `loadModesPage`'s body; the draft's seeding
  from `mode` (a `void mode;` scaffold line marks it, and `selectedTools` / `selectedSubAgents` are
  initialized empty); the three computed bodies; `submitModeEditor`'s body; the page's three summary
  cells (prompt-set, tool count, sub-agent count) **and their three `Table.Th` headers**; and the
  modal body's `form` `<Alert>`, the system-prompt `<Textarea>` (the repo's first — autosized,
  described as optional), the two `ScrollArea.Autosize mah={360}` → `Stack gap="xs"` → `Checkbox`
  pickers (empty-catalogue explanatory state; **`disabled` sub-agents excluded**), and
  `disabled={!draft.canSubmit}` on Save.
- The three computeds **throw** rather than returning a plausible value, so a modal body that reads
  `draft.errors` / `draft.canSubmit` before the coder fills them fails loudly. `void <param>;` lines
  in the two stub bodies and in the draft constructor exist only to satisfy `noUnusedParameters` —
  they are scaffolding the coder deletes, not part of the contract (the step-006 idiom).
- Caller-compile edits (out of Source-files scope): **None.** `routes.tsx` imports the unchanged
  named `AssistantModesPage` export and the component still takes no props; the default export was
  preserved, so nothing else moved.
- Compile gate: `cd frontend && npx tsc --noEmit` clean. `npm test` / `npm run test:types` /
  `npm run build` deliberately **not** run — the verifier owns tests.

### Step 008 — frozen interface (2026-07-26)

Three new files plus a full replacement of the step-006 `SubAgentsPage` shell. Nothing outside this
step's Source files was touched; the step-006 api module (`api/assistantConfig.ts`), the `.d.ts`,
`api/llmServers.ts`, `navItems.ts`, `routes.tsx` and every step-007 file are **unchanged**. This
step adds **no** type and **no** api function — the model picker feeds off the existing
`llmServersApi.listServers` (`context.md` → "No new model-options endpoint").

`frontend/src/admin/pages/subAgentsPageState.ts` — new:

- `export class SubAgentsPageState` — new. `makeAutoObservable(this)` in a **zero-argument
  constructor**; **no methods, no computeds** (`llmServersPageState.ts:18-26`). **Four** async
  trios, field names frozen:
  - `subAgents: SubAgent[] = []`, `subAgentsStatus: "idle" | "loading" | "ready" | "error" = "idle"`, `subAgentsError: string | null = null`
  - `tools: AssistantTool[] = []`, `toolsStatus: "idle" | "loading" | "ready" | "error" = "idle"`, `toolsError: string | null = null`
  - `modes: AssistantMode[] = []`, `modesStatus: "idle" | "loading" | "ready" | "error" = "idle"`, `modesError: string | null = null`
  - `servers: LlmServer[] = []`, `serversStatus: "idle" | "loading" | "ready" | "error" = "idle"`, `serversError: string | null = null`
    (`LlmServer` imported as a type from `../../types/llmServers` — the only cross-module type this
    page borrows)
- `export async function loadSubAgentsPage(state: SubAgentsPageState, signal?: AbortSignal): Promise<void>`
  — new, **stub**
- `export async function disableSubAgentAction(state: SubAgentsPageState, subAgentId: string, signal?: AbortSignal): Promise<void>`
  — new, **stub**
- `export async function enableSubAgentAction(state: SubAgentsPageState, subAgentId: string, signal?: AbortSignal): Promise<void>`
  — new, **stub**

`frontend/src/admin/components/sub-agents/subAgentFormDraft.ts` — new:

- `export interface ModelOption { value: string; label: string }` — new. The Mantine `<Select>` data
  shape; `value` is the **module-private encoding** of the `(server id, model name)` pair plus one
  inherit sentinel, and it never reaches the wire.
- `export class SubAgentFormDraft` — new.
  `constructor(subAgent: SubAgent | null, tools: AssistantTool[], modes: AssistantMode[], servers: LlmServer[])`,
  `makeAutoObservable(this)` last. Fields: `name: string = ""`, `systemPrompt: string = ""`,
  `selectedTools: Set<string>`, `selectedModes: Set<string>`, `llmServerId: string | null = null`,
  `modelName: string | null = null`, `tools: AssistantTool[]`, `modes: AssistantMode[]`,
  `servers: LlmServer[]`, `serverErrors: Record<string, string> = {}`,
  `submitStatus: "idle" | "loading" | "ready" | "error" = "idle"`. **No `disabled` field.**
- `get modelOptions(): ModelOption[]` — new, **stub**
- `get modelValue(): string` — new, **stub** (the `<Select>`'s current value)
- `get clientErrors(): Record<string, string>` — new, **stub** (keys are **wire** field names)
- `get errors(): Record<string, string>` — new, **stub** (`{...clientErrors, ...serverErrors}`, server wins)
- `get canSubmit(): boolean` — new, **stub**
- `export function applyModelOption(draft: SubAgentFormDraft, value: string | null): void` — new,
  **stub**. **Sync**, returns `void`.
- `export async function submitSubAgentForm(draft: SubAgentFormDraft, subAgentId: string | null, onSaved: () => void, signal?: AbortSignal): Promise<void>`
  — new, **stub**. `subAgentId === null` means **create**.

`frontend/src/admin/components/sub-agents/SubAgentFormModal.tsx` — new:

- `interface SubAgentFormModalProps` — **module-private** (not exported, the `ServerFormModal.tsx:17`
  precedent) — `opened: boolean`, `subAgent: SubAgent | null`, `tools: AssistantTool[]`,
  `modes: AssistantMode[]`, `servers: LlmServer[]`, `onClose: () => void`, `onSaved: () => void`
- `export const SubAgentFormModal = observer(function SubAgentFormModal({...}: SubAgentFormModalProps) …)` — new

`frontend/src/admin/pages/SubAgentsPage.tsx` — **changed** (the step-006 shell replaced; both
exports preserved):

- `export const SubAgentsPage = observer(function SubAgentsPage() …)` — **changed** (was a
  fetch-free `Container` + `Title` shell); still **no props**.
- `export default SubAgentsPage;` — **unchanged**, deliberately kept (step 006 froze both exports,
  step 007 kept both).

Accessibility handles frozen as the stable hooks for the row actions — **bind to these**:

- **`aria-label="Sub-agent actions"`** on each row's trailing `ActionIcon` (`IconDots`) — the
  accessible name that opens that row's `Menu`. Part of the frozen contract; do not remove or
  reword. (A deliberate addition over the `LlmServersPage` `Menu` precedent, which offers no
  accessible name — the same reason step 007 froze `aria-label="Edit mode"`.)
- The menu items' visible texts are frozen: **`Edit`**, and **`Disable`** *or* **`Enable`** (exactly
  one of the two per row, chosen by `subAgent.disabled`). **There is no third item and no Delete
  item** (DoD-12).
- The header action button's visible text is frozen: **`New sub-agent`**.
- The modal title is frozen: **`New sub-agent`** on create, **`Edit sub-agent`** on edit; the modal
  is a Mantine `<Modal>` (rendered inline and synchronously under `MantineProvider env="test"`).
- The inherit choice's visible label is frozen as **`Inherit the main chat's model`** (built inside
  `modelOptions`, so it does not exist until the coder fills that computed).

Contract shapes fixed here so neither test-coder nor coder re-decides them:

- **One loader, two mutation actions, no delete.** `loadSubAgentsPage(state, signal?)` loads all
  four resources in **one `Promise.all`** and commits all four trios; `disableSubAgentAction` /
  `enableSubAgentAction` call the api then **re-run the loader** (the
  `llmServersPageState.ts:67 deleteServerAction` shape minus the deletion) — **no optimistic
  update** anywhere. No delete action exists in this module and none may be added.
- **The servers trio is loaded through `api/llmServers`**, not a new endpoint. The `is_active`
  filter is applied where the options are built (`modelOptions`), never at load time, so the state
  holds the raw list. A spec must therefore mock **two** api modules.
- **Four separate error fields, not one.** The page's single red `Text` renders
  `state.subAgentsError ?? state.toolsError ?? state.modesError ?? state.serversError` — written
  concretely, so DoD-2 has one place to look.
- **The table is rendered only when `!loading && !error`** (the step-007 divergence from
  `LlmServersPage`, for DoD-2's "an error message **and no table**"). `loading` is
  `subAgentsStatus === "idle" || subAgentsStatus === "loading"`.
- **The form target is component-local `useState<SubAgent | null | undefined>(undefined)`** — the
  **full three-state** version (`LlmServersPage.tsx:50-54`): `undefined` = closed, `null` = create,
  a row = edit. The modal is mounted **conditionally**, so every open constructs a fresh
  `SubAgentFormDraft`; `onSaved={refresh}`, and the modal closes itself when
  `draft.submitStatus === "ready"` (the `ServerFormModal.tsx:42-46` handler shape, written
  concretely).
- **The model pair is two coupled draft fields with exactly one writer.** `applyModelOption` sets
  **both** `llmServerId` and `modelName` for a concrete option and clears **both** for inherit (and
  for Mantine's `null` clear). No component may assign either field directly; that is what makes a
  half-set pair unreachable from the UI (DoD-5), and why `applyModelOption` is an external function
  rather than a draft method (the draft holds fields + pure computeds only).
- **The `<Select>` value encoding is private to `subAgentFormDraft.ts`.** `modelOptions` produces
  it, `modelValue` reproduces the draft's current one, `applyModelOption` consumes it. It is **not
  exported and not part of the contract** — bind to option **labels**, never to option values.
  `modelValue` returns a plain `string` (never `null`) so the inherit choice is the default
  selection rather than a blank box.
- **`modelOptions` filters on `is_active` and always includes the inherit choice** — inactive
  servers contribute nothing (US-113.AC-5, DoD-6), a server with an empty `enabled_models`
  contributes nothing, and the inherit entry is present even with zero servers.
- **`clientErrors` has exactly one rule**: a blank/whitespace `name` → a `name` error (wire key).
  An empty prompt, an empty tool set, an empty mode set and the inherit model choice are all valid,
  so nothing else can block Save (DoD-8, DoD-13). It is **stubbed, not returned empty**, so it
  cannot accidentally satisfy an assertion.
- **`selectedTools` holds tool *names*; `selectedModes` holds mode *keys*.** Both are `Set<string>`
  in the draft and `string[]` on the wire — serialize with `Array.from(...)` at submit time only.
  Every toggle **reassigns a fresh `Set`** in the component's `onChange`; there is no toggle method
  on the draft (`modelsModalDraft.ts:12-13`).
- **Both model fields are always explicitly present in the body**, `null` + `null` meaning
  *inherit* (DoD-4), and both selections are sent as `[]` when empty, never omitted — the
  full-replace shape.
- **No `disabled` anywhere on the write path**: not a draft field, not a form control, not a body
  field. `UpdateSubAgentRequest` has no such field (step 003), and disable/enable are the two
  zero-body endpoints reached from the row menu.
- **`SubAgentFormModalProps` is not exported** and neither is any prop type — bind to the
  component, not to the interface. `ModelOption` *is* exported, as `modelOptions`' return type.

Where the skeleton/behavior line was drawn (so the coder knows exactly what is left):

- **Written concretely (wiring/structure, no domain behavior):** every class field and initializer,
  both constructors' signatures, all frozen external/computed signatures; the page's `useState` +
  `useEffect` + `refresh` + `handleDisable` / `handleEnable` (each spinning its own
  `AbortController` and `void`ing the call) + the three-state form target + the conditional modal
  mount; the page layout down to `Container size="lg" py="md"` → header `Group` (Title + the
  **"New sub-agent"** `Button`) → error `Text c="red"` → `Loader` **or**
  `Table striped highlightOnHover` with the `Name` header and cell, the row `key`, the `w={60}`
  trailing column and **the whole row `Menu`** (`aria-label="Sub-agent actions"`, `Edit`, and the
  `disabled`-conditional `Enable` / `Disable`, with no Delete item); and the modal's
  `Modal`/`Stack`/Cancel/Save shell plus its `handleSubmit` (abort controller →
  `submitSubAgentForm` → close on `"ready"`).
- **Left to the coder (marked `SKELETON SEAM` in-file):** `loadSubAgentsPage`'s and both mutation
  actions' bodies; the draft's seeding from `subAgent` (a `void subAgent;` scaffold marks it, and
  both `Set`s are initialized empty); all five computed bodies; `applyModelOption`'s and
  `submitSubAgentForm`'s bodies (including the 409/400 status→field mapping); the page's three
  summary cells (model assignment, tool count, mode count) **and their three `Table.Th` headers**,
  plus the visible **disabled marking** in the name cell; and the modal body's `form` `<Alert>`,
  name `<TextInput>`, prompt `<Textarea>`, model `<Select>`, the two `ScrollArea.Autosize mah={360}`
  → `Stack gap="xs"` → `Checkbox` pickers (empty-catalogue explanatory state; modes labelled via
  `modeLabel`), and `disabled={!draft.canSubmit}` on Save.
- Every stub **throws** rather than returning a plausible value — the five computeds included, so a
  modal body reading `draft.modelOptions` / `draft.errors` / `draft.canSubmit` before the coder
  fills them fails loudly. `void <param>;` lines in the stub bodies and in the draft constructor
  exist only to satisfy `noUnusedParameters`; they are scaffolding the coder deletes, not part of
  the contract (the step-006/007 idiom). For the same reason the runtime imports the stubs do not
  use (`runInAction`, `* as assistantConfigApi`, `* as llmServersApi`, `ApiError`, `modeLabel`,
  `applyModelOption`) are **deliberately absent** and are the coder's to add — `noUnusedLocals`
  rejects them today.
- Caller-compile edits (out of Source-files scope): **None.** `routes.tsx` imports the unchanged
  named `SubAgentsPage` export and the component still takes no props; the default export was
  preserved, so nothing else moved.
- Compile gate: `cd frontend && npx tsc --noEmit` clean. `npm test` / `npm run test:types` /
  `npm run build` deliberately **not** run — the verifier owns tests.

### Feedback round 1, item F1 — re-freeze (2026-08-08)

Additive only. **No existing signature, field, route path, enum member or export changed**, and
nothing was removed or renamed. `build_consistency_report()`'s body was deliberately **not
touched** — the fourth status is the coder's work, and the new DTO field's empty default keeps
every existing construction site compiling and every existing input producing the same three
statuses it does today. `services/setup.py` untouched; `db_admin` still never calls `set_db_ready`.

`backend/app/models/schemas/db_admin.py`:

- `class TableReportEntry(BaseModel)` — **changed** (widened + extended). `status` is now
  `Literal["ok", "drift", "missing", "seed-missing"]` (was `Literal["ok", "drift", "missing"]`),
  and one field is appended: `missing_seed_keys: list[str] = []`. `name`, `missing_columns` and
  `extra_columns` are unchanged and still required. The class docstring now describes the fourth
  status, the new field, and the precedence rule.
- `ConsistencyReport` / `VectorRebuildResponse` — **unchanged**.

`backend/app/services/db_admin.py`:

- `class DbAdminErrorCase(str, enum.Enum)` — **changed** (extended, not renamed): the five existing
  members keep their exact values, and one is appended —
  `not_seedable = "not-seedable"`. **Six members total.** Documented in the enum docstring as: a
  named table is real but has no seed registry entry, or its schema is `missing`/`drift` and
  therefore cannot receive rows.
- `class SeedSpec(TypedDict)` — new — `required_keys: tuple[str, ...]`,
  `seeder: Callable[[], Awaitable[None]]`. A `TypedDict`, not a free dictionary (`CLAUDE.md` → "no
  untyped data").
- `_SEEDABLE_TABLES: dict[str, SeedSpec]` — new, module-level, **real (not a stub)** — a literal
  with exactly **one** entry, `"assistant_modes"` → `SeedSpec(required_keys=assistant_modes.DEFAULT_MODE_KEYS, seeder=assistant_modes.seed_default_modes)`.
  Same "declaration, not a body" precedent as the route module's `_DB_ADMIN_ERROR_STATUS`.
- `async def seed_table_rows(name: str) -> None` — new. Body `raise NotImplementedError`.
- `build_consistency_report` / `create_missing_table` / `sync_table_schema` / `export_database` /
  `validate_archive` / `import_database` / `rebuild_vector_index` / `DbAdminError` —
  **unchanged**, bodies untouched.
- Import added for the registry: `from app.db import assistant_modes` (folded into the existing
  `from app.db import llm_servers, schema, vector` line), plus
  `from collections.abc import Awaitable, Callable` and `from typing import TypedDict`.

`backend/app/routes/admin/db.py`:

- `@router.post("/tables/{name}/seed", status_code=status.HTTP_204_NO_CONTENT)` →
  `async def seed_table_rows(name: str, caller: User = Depends(auth_service.require_role(UserRole.admin))) -> None`
  — new. Declared **last**, after `create` and `sync` and after every static path, so route ordering
  is preserved. The `try` / `except db_admin.DbAdminError as err: raise _map_db_admin_error(err)`
  wrapper is part of the frozen shape and **is written**; the service call it wraps is the stub.
- `_DB_ADMIN_ERROR_STATUS` — **changed** (extended): one entry appended,
  `db_admin.DbAdminErrorCase.not_seedable: status.HTTP_400_BAD_REQUEST`. All **six** cases now
  mapped, verified exhaustive against the enum. Real, not a stub. The module docstring's
  error→status sentence was updated to match.
- The six existing handlers and `_map_db_admin_error` — **unchanged**.

`frontend/src/types/db.d.ts`:

- `export type TableStatus` — **changed** (widened): `"ok" | "drift" | "missing" | "seed-missing"`.
- `export interface TableReportEntry` — **changed** (extended): one field appended,
  `missing_seed_keys: string[];` — **required, no `?`**, mirroring the backend DTO, which always
  serialises it (the default is a *backend* construction convenience, never an absent wire field).
  No `any`. `ConsistencyReport` / `VectorRebuildResponse` unchanged.

`frontend/src/api/db.ts`:

- `export async function seedTable(name: string, signal?: AbortSignal): Promise<void>` — new.
  Mirrors `createTable` / `syncTable` (`POST ${BASE}/tables/${encodeURIComponent(name)}/seed`, 204,
  no body). Body **throws**.

`frontend/src/admin/pages/databasePageState.ts`:

- `export async function seedTableAction(state: DatabasePageState, name: string, signal?: AbortSignal): Promise<void>`
  — new. Mirrors `createTableAction` / `syncTableAction`. Body **throws**.
- `class DatabasePageState` — **unchanged**: **no new field**. F1's decision D-d rules out a new
  response DTO and forbids extending `rebuildResult`; the reloaded report is the confirmation, and
  `actionError` stays the single shared error slot.

Contract shapes fixed here so neither test-coder nor coder re-decides them:

- **Naming mirrors the existing pairs exactly** — `seed_table_rows` beside `create_missing_table` /
  `sync_table_schema`; `seedTable` beside `createTable` / `syncTable`; `seedTableAction` beside
  `createTableAction` / `syncTableAction`.
- **`missing_seed_keys` carries a default on the backend and is required on the wire.** The default
  exists so `build_consistency_report()`'s four existing `TableReportEntry(...)` construction sites
  compile untouched; Pydantic deep-copies the `[]` per instance (verified: two instances do not
  share the list), so this is **not** a shared-mutable bug and must not be "fixed". The response
  always contains the key, so the `.d.ts` field is non-optional.
- **The registry is a literal, not a plugin system**, and holds exactly one entry. A table with no
  entry is never `seed-missing` and refuses `seed_table_rows` with `not_seedable`. `024.chat-agent-loop`
  adds an entry rather than re-opening this design.
- **`seed_table_rows` returns `None` and the route is 204** (D-d) — no created-count, no response
  DTO anywhere in the chain. Its refusals are `unknown_table` → 404 and `not_seedable` → 400; it has
  **no** `table_not_missing`-style refusal, because seeding an already-complete table is a
  successful no-op (F1 point 6).
- **`seed_default_modes()` is called, not reimplemented** — it is reached only through the
  registry's `seeder`, and its signature (`async def seed_default_modes() -> None`) is untouched.
- Caller-compile edits (out of Source-files scope): **`frontend/src/admin/pages/DatabasePage.tsx`** —
  one line. Widening `TableStatus` broke the inline status→colour lookup at `:126-130`
  (`TS2339: Property 'seed-missing' does not exist on type '{ ok; drift; missing }'`), so the object
  literal gained the key `"seed-missing": "orange"`. That is the **entire** edit: no `Seed` button,
  no new render branch, no export change, nothing else in the file moved — the rendering work is the
  coder's. The colour is a placeholder the coder may restyle. Without it the frontend does not
  compile at all, so this was the minimal edit to keep the file compiling.
- Compile gate: `cd backend && .venv/Scripts/python -c "import app.main"` clean (backend has no
  separate typecheck); `cd frontend && npx tsc --noEmit` and `cd frontend && npm run test:types`
  both clean. Additionally verified by introspection — the generated OpenAPI shows the family's
  **seven** operations with `/tables/{name}/seed` registered **after** `create` and `sync` at 204;
  the widened `Literal` reaches the schema as `enum: ["ok","drift","missing","seed-missing"]`; the
  DTO's four existing fields stay required and `missing_seed_keys` is the only optional one. No
  pytest run and no `npm test` — the verifier owns tests.

## Tests

### Step 001 — tests (2026-07-26)

- `backend/tests/db/test_assistant_config_db.py` — covers DoD-1, DoD-2, DoD-3, DoD-4, DoD-5, DoD-6,
  DoD-7 — the nine new session-free `db/` functions: both row-in/`None`-out updates (prompt set and
  cleared to `None`, changed `modified_at`, changed sub-agent scalars), `sub_agents.list_all`
  name-ascending and unfiltered (disabled rows included), `get_by_name` exact-match/`None`, and all
  three count-returning bulk deletes (correct count, correct slice, other owners' rows intact,
  `0` without raising when nothing matched).
- `backend/tests/services/test_setup_mode_seed.py` — covers DoD-8, DoD-9 — `setup.import_database`
  on a fresh unconfigured instance leaves all five `DEFAULT_MODE_KEYS` rows; and, importing an
  archive carrying a **prompt-bearing partial** mode set (three of the five, two deliberately
  absent), the stored prompts survive untouched with no duplicate row while the two missing keys
  arrive as seeded null-prompt rows — exactly five afterwards.
  (2026-07-26 rework: the DoD-9 arrangement previously archived all five modes, which import's
  UPSERT alone satisfied, so it could not demonstrate the clause.)
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓,
  DoD-10 [manual/live, no test]

### Step 002 — tests (2026-07-26)

- `backend/tests/services/test_assistant_config_modes.py` — covers DoD-1 … DoD-11 — the mode half of
  `services/assistant_config.py` plus the tool catalogue: `list_modes` returning the fixed five in
  the spec's `DEFAULT_MODE_KEYS` order with prompt, tool names, string sub-agent ids and both
  timestamps (and an import-only foreign key sorting last, by key); `save_mode` storing a prompt and
  reading it back; `null` and `""` both accepted and round-tripping verbatim; tool and sub-agent
  selections stored exactly and **replaced** (not merged) on re-save; an empty tool list and an
  unconfigured mode both reporting zero tools rather than the registry; `unknown-tool`,
  `unknown-sub-agent` (missing id, unparsable id, `""`), `sub-agent-disabled` and `mode-not-found`
  refusals — each rejected save compared against a **before/after `db/` snapshot** (prompt +
  `modified_at` + tool rows + link rows) to prove nothing was written; de-duplication of a repeated
  tool name and of a repeated sub-agent id (one link row per distinct value); and the catalogue
  mirroring `TOOL_REGISTRY` in declaration order with a payload whose entry keys are exactly
  `{name, description}` (no `args_schema` / `callable` / derived key).
- Registry-count independence: every tool-name expectation is derived from the imported
  `TOOL_REGISTRY` (`ALL_TOOL_NAMES`), never from a literal or a count; the three cases that need at
  least one valid tool name to have bite carry a `skipif(len(TOOL_REGISTRY) == 0)` guard, which does
  not trigger today. Order **within** `tool_names` / `sub_agent_ids` is deliberately not asserted —
  the spec fixes the order of the mode list only.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓,
  DoD-10 ✓, DoD-11 ✓, DoD-12 [manual/live, no test]

### Step 003 — tests (2026-07-26)

- `backend/tests/services/test_assistant_config_subagents.py` — covers DoD-1 … DoD-11 — the
  sub-agent half of `services/assistant_config.py`: a create storing name + prompt and returning a
  **string** `id`, `disabled` false, both link lists present-and-empty and both timestamps set (plus
  `""` accepted as a prompt — only the name is blank-checked); the no-model create recording
  `llm_server_id` / `model_name` as **null/null**, the inherit-the-main-chat's-model state, passed
  explicitly because no request field has a default; an active server + a model listed in its
  `enabled_models` stored as an `int` FK on the row and a `str` on the wire; the **half-set** pair
  (server-without-model and model-without-server) refused `invalid-model-pair` **on create and on
  update**; a non-existent server, an existing-but-inactive server and an unparsable server id all
  refused `unknown-or-inactive-server`, a model absent from an active server's `enabled_models`
  (and an empty `enabled_models`) refused `model-not-enabled`, on create and on update;
  a duplicate name — bare and space-padded — refused `name-taken` on create **and** on update, with
  a padded unique name proving the trim-before-collision-check; blank / whitespace-only names
  (`""`, `" "`, `"   "`, tab+newline) refused `blank-name` on create **and** on update; an update
  that does not rename succeeding twice over (no self-collision, a second sub-agent present so the
  check has a real other row); an update storing a changed name + prompt with `modified_at`
  strictly advancing and `created_at` unmoved, and the model pair switching null/null → pair →
  another model → back to null/null; a missing id **and** three ill-formed ids
  (`"not-an-id"`, `"12x"`, `""`) refused `sub-agent-not-found`; and the lister returning every
  sub-agent name-ascending (created out of order) **including a disabled one that sorts in the
  middle**, each carrying its `disabled` flag, with an empty instance listing none.
- Every refusal clause that the DoD marks "nothing is written" / "the existing rows are unchanged"
  (DoD-4, DoD-6, DoD-7, and by extension the rejected updates of DoD-5/DoD-10) compares a
  **before/after `db/` snapshot** of *every* sub-agent row — id, name, prompt, `disabled`, the model
  pair, both timestamps and both link-row sets — so it bites on a row that should not exist, a field
  that should not have moved, and a refreshed `modified_at` alike; the create refusals additionally
  assert `sub_agents.get_by_name(<refused name>) is None`.
- Binding notes: `update_sub_agent` is called with the id as a **`str`** per the re-frozen
  signature; `disabled` is arranged only through `db/` (the update request has no such field, step
  004 owns enable/disable); `LlmServer` rows are seeded with `enabled_models` as its **JSON string**
  (the `tests/services/test_chats.py:_seed_server` idiom), decoded at the service edge. Timestamp
  comparisons normalize to naive UTC (the service writes aware `datetime.now(timezone.utc)`, SQLite
  returns naive — status note under step 002), and a 50 ms sleep makes "`modified_at` advances" a
  strict comparison rather than a resolution gamble. The link lists are asserted
  present-and-empty only, never populated, per the frozen record.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓,
  DoD-10 ✓, DoD-11 ✓, DoD-12 [manual/live, no test]

### Step 004 — tests (2026-07-26)

- `backend/tests/services/test_assistant_config_subagent_links.py` — covers DoD-1 … DoD-13 — the
  sub-agent link sets and disable/enable: a create carrying both selections storing them on the row
  set and returning them (DTO + `db/` rows + lister); the **one row set, two editors** pair — a
  sub-agent-side write read back through the **mode** surface (`list_modes` / `mode_subagents.
  list_by_mode`) and a mode-side `save_mode` link appearing in the sub-agent's `mode_keys`, with a
  sub-agent-side re-save replacing only that sub-agent's slice while a second sub-agent's link to the
  same mode survives; replace-not-merge on update for the mode selection and (registry-guarded) for
  the tool selection, with a retained value beside the dropped one so the replace is not a wipe; an
  **omitted**, an explicitly-empty-on-create and an explicitly-empty-on-update selection all accepted
  with zero link rows of that kind and no mode gaining a sub-agent; `unknown-tool` and the **reused**
  `mode-not-found` refusals on create **and** on update, each against a **before/after `db/`
  snapshot** of every sub-agent row (scalars, model pair, both timestamps, both link sets) plus a
  service-side re-read, and each refused body carrying a new name, new prompt and an otherwise valid
  selection so a partial write is caught; de-duplication of a repeated mode key and of a repeated
  tool name, on create and on update, with one row per distinct value at both the sub-agent and the
  mode end; the disable cascade — two referencing modes both losing the link, a co-linked second
  sub-agent's rows intact, the `SubAgent` row and its `subagent_tool` rows kept (arranged with
  non-registry stored tool names so the clause bites at any registry size) and `modified_at`
  refreshed; re-enable restoring **no** links and moving nothing else (name, prompt, model pair,
  tools, `created_at`), then the sub-agent being selectable again from **both** editors; and the
  disabled-guard asymmetry — a non-empty `mode_keys` on a disabled row refused `sub-agent-disabled`
  with a snapshot-verified no-write, the same save with an empty `mode_keys` succeeding and still
  landing name, prompt, model and the replaced tool set while `disabled` stays true; disable **and**
  enable on a missing id and on three ill-formed ids refused `sub-agent-not-found`.
- Binding notes: the two new request fields are exercised **omitted** (the default) as well as
  explicitly; `set_sub_agent_disabled` is called with the id as a **`str`**; the two internal
  replace-set helpers are never called directly (they write but do not validate — the public
  create/update surface is the only entry point). The disabled row for DoD-12 is arranged through
  `db/` so that clause does not depend on the setter under test. Registry-count independence: every
  tool-name expectation is derived from the imported `TOOL_REGISTRY`; the two cases needing a real
  tool name for bite carry `skipif(len(TOOL_REGISTRY) == 0)` (does not trigger today), and DoD-9's
  survive-a-disable rows are seeded via `db/` with deliberately non-registry names. Order **within**
  `tool_names` / `mode_keys` is not asserted — the spec fixes no order for a sub-agent's selections.
  Timestamp comparisons normalize to naive UTC with a 50 ms sleep for strictness.
- Expected-red note: DoD-5's clause ("an empty tool selection and an empty mode selection are both
  accepted and result in zero link rows") already holds against the skeleton, because step 003's
  create/update are implemented and ignore the two new lists. Its test is written honestly for the
  clause — it would catch a regression where an empty selection raised or wrote rows — and is
  expected **green** at the red gate.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓,
  DoD-10 ✓, DoD-11 ✓, DoD-12 ✓, DoD-13 ✓, DoD-14 [manual/live, no test]

### Step 005 — tests (2026-07-26)

- `backend/tests/routes/admin/test_assistant_config.py` — covers DoD-1 … DoD-12 — the
  `/api/admin/assistant-config` route family end-to-end over the real `app.main.app`
  (`http_client`, in-process ASGI, real JWTs): `GET /modes` returning the five seeded modes each with
  its prompt and both (empty) selections, and `PUT /modes/{mode_key}` storing prompt + tool set +
  sub-agent set, returning the updated mode and being read back by a second `GET /modes`; the two
  **whole-family authorization sweeps** — all **eight** endpoints enumerated (not sampled) in one
  table, answering **403** to an authenticated `author` and **401** with no bearer token, reads and
  writes alike, against **real existing** mode keys and sub-agent ids so a refusal cannot be a
  disguised not-found (both targets arranged through `db/`, not through the create endpoint, so a
  broken create cannot fail an authorization clause for a non-authorization reason, and the table is
  cross-checked for equality against the app's generated operation set, so a dropped or added
  endpoint fails the sweep instead of silently shrinking it); `POST /sub-agents` → **201** with a
  **string** `id`, listed by
  `GET /sub-agents`; a duplicate name → **409** on create **and** on update; a blank and a
  whitespace-only name → **400** on create **and** on update, and both half-set model-pair
  directions → **400**; the 404 family — unknown `mode_key`, and a well-formed-but-missing
  `sub_agent_id` on `PUT` / `disable` / `enable`, plus the clause the `str` path param exists for:
  three genuinely non-numeric ids (`"not-an-id"`, `"12x"`, `"1e5"`) on all three param endpoints,
  asserted **404** (so a 422 or a 500 fails the test); an unknown tool name → **400** on the mode
  save and on the sub-agent save (create and update); `disable` → 200 with `disabled` true and an
  empty `mode_keys`, the two modes that referenced it no longer listing it in `sub_agent_ids`, then
  `enable` → 200 with `disabled` false and **still** no modes; `GET /tools` returning entries whose
  keys are exactly `{name, description}` and refusing an author (403) and an anonymous caller (401).
- DoD-11 is asserted against the **operations the running app actually exposes** — its generated
  OpenAPI path/method map filtered to the family prefix (the family must be mounted, **and** no path
  in it may carry a `delete` operation) — not against one probed URL, with a behavioural confirmation
  that a `DELETE` on a sub-agent path is non-2xx and leaves the row listed.
  (2026-07-26 rework, red-gate TEST fault: this first read `app.routes`, which under FastAPI 0.139.2
  keeps `include_router`-included routes wrapped and so is empty for a correctly mounted family —
  unsatisfiable, and it would have masked the very regression it exists to catch. The formulation
  — mounted **and** DELETE-free, plus the probe — is unchanged; only the enumerated surface moved.
  The same OpenAPI operation map now backs the DoD-2/DoD-3 sweep cross-check.)
- DoD-12 is a secret sweep over **all eight** responses (tools, modes list, mode save, sub-agent
  list/create/update/disable/enable), collected with a sub-agent bound to a seeded server whose
  stored `api_key` carries a distinctive marker: recursively, no key name containing
  `api_key`/`apikey`/`api-key`/`secret`/`args_schema`/`callable`, no string value containing the
  marker (raw **or** partially masked) and no `***`; plus the catalogue entries' keys being exactly
  `{name, description}` — the `ToolDef.args_schema` / `ToolDef.callable` half.
- Binding/arrangement notes: bound to the Step-005 frozen record — `sub_agent_id` and `mode_key` are
  `str`, `POST /sub-agents` is the family's only 201, `disable`/`enable` are **zero-body** POSTs, and
  every request body sends the four required sub-agent scalars explicitly (only `tool_names` /
  `mode_keys` are defaulted and are therefore sent only when the clause needs them). Mode rows are
  arranged with `db.assistant_modes.seed_default_modes()` (the HTTP surface never seeds — that is
  `services/setup.py`'s, step 001), the model-pair fixture with `db.llm_servers.create`, and the
  sweep / DoD-11 target rows with `db.sub_agents.create`; module-local
  `_auth_header` / `_seed_user` / `_seed_admin` copied from `tests/routes/admin/test_llm_servers.py`,
  plus a `_seed_author`. Clauses that are *about* creating (DoD-1/4/5/6/8/12) still arrange through
  `POST /sub-agents`; clauses that merely need a target do not. Registry-count independence: every tool-name expectation is derived from the
  imported `TOOL_REGISTRY` (`ALL_TOOL_NAMES`), never a literal or a count, and the two `[:1]`
  selections degrade to `[]` on an empty registry rather than failing. Order **within**
  `tool_names` / `sub_agent_ids` / `mode_keys` is not asserted; the mode **list** is asserted as a
  set of the five spec keys, since step 005 fixes no ordering of its own.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓,
  DoD-10 ✓, DoD-11 ✓, DoD-12 ✓, DoD-13 [manual/live, no test]

### Step 006 — tests (2026-07-26)

- `frontend/tests/admin/assistantConfigApi.test.ts` — covers DoD-3, DoD-4, DoD-5, DoD-6, DoD-7 — the
  wire module at its own HTTP boundary: `api/client` is mocked with the `importOriginal` spread
  idiom (only `request` replaced, so the **real** `ApiError` class survives — never `fetch`, and
  never the `api/assistantConfig` module itself), and every case asserts the URL, method, body and
  `AbortSignal` handed to `request` plus the value returned. `listModes` / `listSubAgents` /
  `listTools` GET `/modes` · `/sub-agents` · `/tools` and return the **unwrapped** `.items` array
  (an empty envelope → a plain `[]`, and the tool entries' `name` / `description` read back
  verbatim); `saveMode` PUTs `${BASE}/modes/<key>` with the update payload as the body and tracks
  the key it was given; `createSubAgent` POSTs `/sub-agents`, `updateSubAgent` PUTs
  `/sub-agents/<id>`, and `disableSubAgent` / `enableSubAgent` POST `.../disable` · `.../enable`
  with **no body**, each returning the DTO `request` resolved; every one is called with a supplied
  signal and asserted to forward that exact instance, and two calls omit it (the trailing-optional
  binding). DoD-6 rejects `request` with a real `ApiError` and asserts the **identical instance**
  propagates — `instanceof ApiError` with `status` 409 on create and 400 on the mode save (the
  branch callers need), plus a list call that must not swallow a failure into an empty array.
  DoD-7 pins `MODE_LABELS`' key set as exactly the five system mode keys, `modeLabel` returning a
  non-empty human label ≠ the raw key for each (and the step's own worked example,
  `edit-character` → "Edit character"), and the raw key back for two unknown keys.
- `frontend/tests/admin/assistantConfigNav.test.tsx` — covers DoD-2 (first half) — the two new
  entries' own `isNavItemActive` behaviour only: each active for its own path, and not for the
  other's nor for `/`. Deliberately carries no table pin and no render — those belong to the two
  pre-existing specs (`006.context.md` → "Testing notes for this step").
- `frontend/tests/admin/navItems.test.ts` — **pre-existing, extended** — covers DoD-1 — a new
  `ADMIN_NAV_ITEMS` describe pins the table at **exactly five** entries and asserts an ordered
  full-table equality of `{path, label}` — Users `/`, LLM Servers `/llm-servers`, Database
  `/database`, Assistant modes `/assistant-modes`, Sub-agents `/sub-agents` — so the three
  pre-existing entries stay asserted by name and path, plus an icon on every entry. The file's
  fast/002 DoD-6 `isNavItemActive` cases are untouched.
- `frontend/tests/admin/AdminNav.test.tsx` — **pre-existing, extended** — covers DoD-2 (second
  half) — the rendered-link pin goes 3 → **5** (every label asserted by name with its href, still a
  full pin, not a `.some()`/subset), the two existing "exactly one active" cases now also assert the
  two new links inactive, and two new cases assert that at `/assistant-modes` and at `/sub-agents`
  exactly the matching link carries `data-active="true"`.
- Pin-integrity note (DoD-1/DoD-2's explicit instruction): `navItems.test.ts` did **not** in fact
  enumerate the array before this step — it only exercised `isNavItemActive` — so the pin was
  **added** at the new length rather than relaxed; `AdminNav.test.tsx`'s existing
  `toHaveLength(3)` + three-label pin was **extended** to five. Nothing was weakened anywhere.
- Binding notes: bound to the step-006 frozen record — `signal?` trailing on all eight endpoint
  functions, `modeLabel` sync (a bare `Record` cannot satisfy DoD-7's fallback half, so the
  unknown-key clause is asserted through the function), ids passed and asserted as **strings**
  (a fixture id beyond 2^53), and no list-envelope type referenced anywhere. `RequestOptions` is
  never imported by name — the options bag is typed as `Parameters<typeof request>[1]`, so the spec
  binds to the frozen `request` signature itself. Read assertions treat an **omitted** `method` as a
  GET (fetch semantics) and accept nothing else; write assertions require the explicit verb.
- Expected-red note: `MODE_LABELS` is frozen **real** data, so DoD-7's key-set case is expected
  **green** at the red gate; every other case fails against the stubbed bodies (the eight endpoint
  functions and `modeLabel`), and the two extended nav specs fail only until the coder's appended
  entries land — the entries themselves were written at the freeze, so those cases may already be
  green.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓,
  DoD-8 [manual/live, no test], DoD-9 [manual/live, no test]

### Step 007 — tests (2026-07-26)

- `frontend/tests/admin/AssistantModesPage.test.tsx` — covers DoD-1 … DoD-10 — the five-mode
  editor surface across its three frozen seams (the page, the draft + `submitModeEditor`, and
  `ModeEditorModal` rendered directly): the mount load calling **all three** list endpoints and
  rendering **one body row per mode in the api's order** (a deliberately non-seeded,
  non-alphabetical order) with each row's label from the real `MODE_LABELS` and its tool /
  sub-agent **counts** in the two cells before the trailing action column (three modes with
  pairwise-distinct count pairs, so a swapped column fails); a failing load asserted twice — the
  loader **resolves** (does not throw), leaves `modes` empty and lands a non-empty author-facing
  string in one of the three error fields, and the page renders readable text beside its heading
  with **no `table`** at all; the editor opened from a row showing that mode's stored prompt, its
  selected tool and sub-agent boxes **checked** and the unselected ones **unchecked** (plus the
  draft's own seeding — prompt, both `Set`s, and `null` → `""`); an edited prompt saving **once**
  with that mode's key and the new text, then a **second** `listModes` (no optimistic update) and
  the modal closing; an emptied prompt sending `system_prompt: **null**` (explicitly `not.toBe("")`)
  with `clientErrors` empty, `canSubmit` true and Save **enabled**; tool toggles in both directions
  sending exactly the checked set and unchecking **every** tool sending a **present** `tool_names`
  key whose value is `[]`; the same for sub-agent **ids**; a `disabled` sub-agent having **no
  checkbox** and being absent from the saved `sub_agent_ids`; a failing save mapping to the single
  **`form`** key with `submitStatus === "error"` and `onSaved` never called, and at page level
  rendering a `role="alert"` **above** the prompt field while the modal stays **open** with the
  typed prompt and the toggled checkbox intact and `listModes` **not** re-called; and an empty tool
  catalogue offering no tool, still rendering readable copy, still saving with `tool_names: []`,
  with a one-entry and a three-entry catalogue each offering exactly its own entries.
- Binding notes: bound to the step-007 frozen record — the row action is found by its frozen
  `aria-label="Edit mode"` (scoped to the row that shows the mode's label), the modal's system
  prompt by `role="textbox"` (its only free-text control), the pickers by `role="checkbox"` with a
  name regex over the tool name / sub-agent name, and the `form` error by `role="alert"` (the
  frozen `<Alert>`), never by class or DOM structure. `../../src/api/assistantConfig` is mocked with
  the **`importOriginal` spread** — only the eight endpoint functions are replaced, so `MODE_LABELS`
  and `modeLabel` stay **real**: a bare factory would either make render throw (the
  `BookshelfPage.test.tsx:34-41` caveat) or assert a fixture label back to itself. `fetch` and
  `api/client` are never mocked; the real `ApiError` is used. Sub-agent ids are strings beyond 2^53.
  Order **within** `tool_names` / `sub_agent_ids` is not asserted (the spec fixes no order there) —
  only membership, via a sorted compare.
- Unpinned-wording note: the spec fixes no text for the load-failure message nor for the
  empty-catalogue empty state, so those two clauses assert "readable text rendered, not blank"
  (heading stripped) rather than a literal — the repo precedent at `work/BookStatePage.test.tsx:227`
  and `work/ChatPane.test.tsx:534`. Every DoD clause that *is* pinned (the `null` prompt, the `[]`
  selections, the counts, the checked/unchecked states, the `form` key, the no-refresh) is asserted
  literally.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓,
  DoD-10 ✓, DoD-11 [manual/live, no test], DoD-12 [manual/live, no test]

### Step 008 — tests (2026-07-26)

- `frontend/tests/admin/SubAgentsPage.test.tsx` — covers DoD-1 … DoD-13 — the sub-agent
  management surface across its three frozen seams (the page, the draft + `applyModelOption` /
  `submitSubAgentForm`, and `SubAgentFormModal` rendered directly): the mount load calling **all
  four** list endpoints (`listSubAgents` / `listTools` / `listModes` and `llmServers.listServers`)
  and rendering one row per sub-agent **including the disabled one**, whose **name cell** must
  render differently from an identically-configured enabled row's (a markup differential, since the
  spec pins no marking wording — an unmarked row renders identically and fails); a failing load
  asserted twice — the loader **resolves**, leaves `subAgents` empty and lands a non-empty
  author-facing string in one of the four error fields, and the page renders readable text **outside
  the title and the header button** with **no `table`**; "New sub-agent" opening an empty form (title
  `New sub-agent`, both fields blank, every checkbox unchecked) and a name + prompt + one tool + one
  mode saving **once** through `createSubAgent` with exactly those four values, then a **second**
  `listSubAgents` and the modal closing; a create that never touches the picker sending
  `llm_server_id` and `model_name` as **present-and-null**; the model coupling asserted four ways —
  a concrete choice setting **both** draft fields and both wire fields, inherit clearing **both**,
  **every** offered option (plus Mantine's `null` clear) leaving the pair coupled
  (`llmServerId === null` iff `modelName === null`), and the same round trip driven through the
  rendered `<Select>`; the offered options being **exactly** inherit + both active servers' models
  (an **inactive** server carrying `enabled_models` contributing nothing, inherit still offered with
  zero servers, and the opened picker showing the active models but not the inactive one's); a 409
  landing on the **`name`** key alone (`serverErrors` keys `["name"]`, no `form` key,
  `submitStatus === "error"`, `onSaved` never called) and, at page level, the name input
  `aria-invalid` while the prompt is not, the modal still open with both typed values intact and
  `listSubAgents` **not** re-called; a blank and a whitespace-only name being the draft's one client
  error with `canSubmit` false and Save **disabled** and **no** api call on click, versus a real name
  clearing it (so the control is not simply always disabled); an existing sub-agent seeding name,
  prompt, model pair, tool set and mode set — asserted both on the draft and through the row's
  `Edit` item (title `Edit sub-agent`, the `<Select>` showing the assigned model, the right boxes
  checked) — and an edited save calling `updateSubAgent` **once** with that id and the edited values
  plus a refresh; all **five** modes offered by their frozen `MODE_LABELS` labels with the stored
  `mode_keys` checked and the other three unchecked, and a toggle saved as `mode_keys`; the row
  menu's `Disable` calling `disableSubAgent` with that id and refreshing, a disabled row offering
  `Enable` instead (and not `Disable`), and both external actions asserted at state level to call
  their endpoint **and re-run the loader** (the re-loaded list, not a patched row); and an empty tool
  catalogue offering no tool, still submitting with `tool_names: []`, and rendering copy the
  one-entry catalogue does not, with one- and three-entry catalogues each offering exactly their own
  entries.
- Binding notes: bound to the step-008 frozen record — the row menu is opened by its frozen
  `aria-label="Sub-agent actions"` (scoped to the row showing that name), its items asserted by the
  frozen texts `Edit` / `Disable` / `Enable`, the header button and the two modal titles by their
  frozen strings, and the inherit choice by its frozen label `Inherit the main chat's model`. The
  `<Select>` **value encoding is never touched**: the pair an option carries is discovered by
  applying it through the frozen `applyModelOption` on a throwaway draft, so DoD-5/DoD-6 assert
  `(llm_server_id, model_name)` outcomes rather than any private encoding. The three form controls
  are found by the Interface intent's own shapes — the single-line `TextInput` (the one textbox that
  is neither the `Textarea` nor the `Select`'s `aria-haspopup="listbox"` target), the `Textarea`, and
  the `Select` — each asserted to be unique, never by class or DOM position. **Both** api modules are
  mocked with the `importOriginal` spread (`assistantConfig` and `llmServers`), so `MODE_LABELS` /
  `modeLabel` and `llmServers`' runtime option constants stay **real**; `fetch` and `api/client` are
  never mocked and the real `ApiError` is used. Ids are strings beyond 2^53. Order **within**
  `tool_names` / `mode_keys` is not asserted where more than one value is involved (the spec fixes no
  order) — only membership, via a sorted compare.
- DoD-12 is asserted four ways rather than by one probe: the row menu's item set is pinned as
  **exactly** `["Disable","Edit"]` (enabled) / `["Edit","Enable"]` (disabled); no rendered button's
  text or `aria-label` matches `/delete|remove|destroy/i`; **neither** `api/assistantConfig` nor
  `subAgentsPageState` exports a symbol matching that pattern (so no delete function exists to call);
  and after a full interaction sweep (Edit → Cancel, Disable, New → Cancel) every api function that
  was called is in the page's own allowed set.
- Unpinned-wording note: the spec fixes no text for the load-failure message, the disabled marking
  or the empty-catalogue state, so those three clauses are **differential** rather than
  literal — the failure message must survive stripping the title and the buttons (a bare `Loader`
  leaves nothing); the disabled row's name-cell markup must differ from an otherwise identical
  enabled row's; and the empty catalogue must render at least one word the one-entry catalogue does
  not. Every clause the DoD *does* pin (the `null` model pair, the `[]` selections, the `name` error
  key, the five mode labels, the frozen menu/labels, the no-refresh) is asserted literally.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓,
  DoD-10 ✓, DoD-11 ✓, DoD-12 ✓, DoD-13 ✓, DoD-14 [manual/live, no test],
  DoD-15 [manual/live, no test]

### Feedback round 1 — repro tests (2026-08-08)

- `backend/tests/services/test_db_admin_seed.py` — reproduces: F1 — a present, schema-clean
  `assistant_modes` holding zero rows is reported `ok` and no service call can seed it —
  defends 001.db-layer-completion (`seed_default_modes` reachable on an existing DB). Ten
  tests over F1 points 1-7: `seed-missing` detection with the exact absent
  `DEFAULT_MODE_KEYS`, the partial and fully-seeded cases, the precedence rule (drift and
  missing always outrank rows), the no-regression guard for every non-registry table
  (`missing_seed_keys == []` whatever the status), an unrecognised key neither reported nor
  removed, `seed_table_rows` creating the five / idempotent no-op / preserving an
  admin-edited `system_prompt`, and the `unknown_table` / `not_seedable` refusals.
- `backend/tests/routes/admin/test_db_seed.py` — reproduces: F1 — no admin endpoint reseeds
  the modes. Three tests: `POST /api/admin/db/tables/assistant_modes/seed` → 204 with an
  empty body and the report flipping `seed-missing` → `ok`; 404 for an unknown name and 400
  for `not_seedable` (parameterized); 403 for a non-admin caller.
  `backend/tests/routes/admin/test_db.py` was **not** edited.
- `backend/tests/services/test_db_admin_import_seed.py` — reproduces: F2 — the admin-surface
  `db_admin.import_database` leaves modes unseeded. Three tests: an archive without mode rows
  ends with all five keys; an archive carrying prompt-bearing rows keeps them verbatim with
  exactly five rows and no duplicates; a refused (corrupt) import raises `invalid_archive`
  and seeds nothing. Archives built with the real `export_all()`, the
  `test_setup_mode_seed.py` idiom.
- `frontend/tests/admin/DatabasePage.test.tsx` — reproduces: F1 (frontend) — no `Seed`
  affordance, api call or state action exists. Six tests: `seedTable` POSTs to
  `/api/admin/db/tables/{name}/seed` with no body; `seedTableAction` clears `actionError`,
  seeds and reloads the report; an `ApiError` lands in `actionError` and is never thrown; the
  `Seed` button shows for a `seed-missing` row and for no other status; the existing
  `missing` → `Create` / `drift` → `Sync` visibility rules still hold (regression guard);
  pressing `Seed` seeds that table and re-reads the report. First spec for this page — adapted
  from `AssistantModesPage.test.tsx` + `renderWithProviders`, queried by role + accessible
  name (no `data-testid` added anywhere).
- `frontend/tests/admin/AssistantModesPage.test.tsx` — **extended only**, two tests appended
  for F3 (empty state states there are no modes and names the Database page's `Seed`
  remediation, with the table gone; a non-empty list still renders the table and its
  `aria-label="Edit mode"` control). **No existing test was weakened, rewritten or deleted**
  and every prior assertion is preserved verbatim.
- No test written for: F4 (reshape — docstring/comment corrections only; behaviour is
  preserved by the existing suite).
- Deviation to note: the `seedTable` URL assertion mocks `api/client::request` and imports the
  real `api/db` via `vi.importActual`, the repo's api-layer precedent
  (`tests/admin/assistantConfigApi.test.ts`). Every other frontend test in the file mocks the
  `api/db` module, never `fetch`.

#### Correction round — pre-existing tests reconciled to F1 (2026-08-08)

Thirteen delivered-feature tests asserted that in a DB built by `init_db()` alone **every**
metadata table reports `ok`. F1 makes that false for exactly one table: the sole
seed-registry entry, `assistant_modes`, is `seed-missing` until its five `DEFAULT_MODE_KEYS`
rows exist. No repro test from round 1 was touched, and **no assertion was weakened,
sampled or dropped** — every whole-report loop still pins a status per table.

- `backend/tests/services/test_db_admin_report.py` — `test_all_match__DoD1_US015_AC1` now
  arranges a fully consistent DB (`assistant_modes.seed_default_modes()`) before asserting
  every table `ok` with empty column diffs; "all match" means schema **and** required rows.
  The other four tests (missing / drift / column diffs) are untouched — schema outranks rows.
- `backend/tests/services/test_db_admin_remediation.py` — `test_create_missing__DoD1_US016_AC1`
  and `test_sync_drops_extra_columns__DoD4_US017_AC2` now pick their target via a new
  `_pick_table_outside_seed_registry()` helper, so `ok` after `create` / `sync` is a pure
  schema verdict. Per D-c, schema remediation on a seedable table lands it on `seed-missing`
  and seeding is a separate action; the tests do **not** demand that `create` / `sync` seeds,
  and they still assert exactly as strongly that `create` makes a missing table exist with
  the right columns and that `sync` drops the extra column.
- Ten whole-report drift-clean guards —
  `backend/tests/test_data_domain_{assistant_core,assistant_links,book,book_author_prompts,chapter,chapter_author_prompts,chapter_changes,chat,codex,continuity}.py`
  — each seeds the default modes before building the report, so the per-table
  `status == "ok"` loop and the named subject-table assertions stay verbatim: a fully
  bootstrapped DB still has zero drift anywhere.

## Feedback

### Round 1 (2026-08-08)

- **F1 bug** — `backend/app/services/db_admin.py`, `frontend/src/api/db.ts`,
  `frontend/src/admin/pages/databasePageState.ts`,
  `frontend/src/admin/pages/DatabasePage.tsx` — the `seed-missing` status and its `Seed`
  remediation now work end to end.
  - `db_admin.py`: new module-private `async def _missing_seed_keys(name: str) -> list[str]`
    (not frozen — the coder's helper) returns the `_SEEDABLE_TABLES` entry's `required_keys`
    that have no row, **in registry order**, via `assistant_modes.list_all()`; `[]` for a
    table with no registry entry, so an unrecognised key is never reported and never removed.
    `build_consistency_report()` calls it **only** in the present-and-schema-clean branch and
    emits `seed-missing` when it is non-empty, else `ok` — schema outranks rows absolutely, so
    `missing` and `drift` entries are untouched and keep `missing_seed_keys == []`.
    `seed_table_rows(name)` filled: not in `SQLModel.metadata` → `unknown_table` (404, mirrors
    `sync_table_schema`, deliberately not `not_in_metadata`); no registry entry, or a report
    status of `missing` / `drift` → the new `not_seedable` (400); otherwise
    `await spec["seeder"]()` — `assistant_modes.seed_default_modes()` **called, not
    reimplemented** — so a fully-seeded table is a successful no-op. Docstrings for
    `build_consistency_report` / `_missing_seed_keys` describe the precedence rule.
  - `api/db.ts`: `seedTable` body — `request<void>(POST ${BASE}/tables/{name}/seed)`, identical
    to `createTable` / `syncTable`.
  - `databasePageState.ts`: `seedTableAction` body — clear `actionError` → `dbApi.seedTable` →
    aborted-guard → `loadReport` → friendly `ApiError` catch into `actionError`; no rethrow, no
    new state field.
  - `DatabasePage.tsx`: `handleSeed` + a `size="xs"` `Seed` button rendered **only** for
    `entry.status === "seed-missing"`; `Create` (`missing`) and `Sync` (`drift`) unchanged. No
    toast, no modal, no confirmation. The skeleton's placeholder status→colour entry
    `"seed-missing": "orange"` was kept as-is — it sits correctly between `drift`'s yellow and
    `missing`'s red in the page's existing palette.
  - Verified by a throwaway scratch script (never pytest): empty table → `seed-missing` with all
    five keys; two-of-five seeded → the three absent keys only; an unrecognised extra key
    neither reported nor removed and an edited `system_prompt` preserved through a seed; second
    seed a no-op; every other table still `ok` with `missing_seed_keys == []`; a drifted and a
    dropped `assistant_modes` both refuse with `not_seedable`; an unknown name refuses with
    `unknown_table`.
- **F2 bug** — `backend/app/services/db_admin.py` — `import_database` now ends with
  `await assistant_modes.seed_default_modes()`, after `db_import_export.import_all(...)` and
  outside/after `validate_archive`, so a refused archive still raises before anything is seeded.
  Docstring updated to state the seed and its position. `set_db_ready` is still never called
  here, and `services/setup.py` is untouched. Verified on a scratch DB: a fresh instance
  restored from an archive with no mode rows ends with all five keys; archived rows keep their
  `system_prompt` and gain no duplicate; a corrupt archive leaves zero rows.
- **F3 bug** — `frontend/src/admin/pages/AssistantModesPage.tsx` — when the load succeeds and
  `state.modes.length === 0`, the page renders a dimmed `Text` empty state
  (`CodexListPage.tsx:162-168` idiom) instead of the header-only table: "No assistant modes are
  configured. Open the Database page and use the Seed action on the assistant_modes row of the
  consistency report to create them." — one flat text node, naming F1's remediation by its UI
  location. The table branch is now `state.modes.length > 0`; loading, error and populated
  branches, the per-row edit `ActionIcon`, the modal wiring, `observer`, the page state and both
  exports are unchanged, and no `useState` was added. `SubAgentsPage.tsx` untouched.
- **F4 reshape** — `backend/app/routes/admin/assistant_config.py`,
  `backend/app/db/assistant_modes.py`, `backend/app/db/sub_agents.py`,
  `backend/app/db/mode_tools.py`, `backend/app/db/subagent_tools.py`,
  `backend/app/db/mode_subagents.py`, `backend/app/services/assistant_config.py` — comments and
  docstrings only; **zero** code, signature, import or logic change in all seven files. Each
  "…bodies are UNIMPLEMENTED" sentence was replaced by a one-line description of what the module
  actually contains (the eight implemented handlers; the mode CRUD + seeder; the sub-agent CRUD
  with no delete; the three link-table modules' lookups and count-returning bulk deletes). In
  `services/assistant_config.py::list_tools` only the false parenthetical was replaced — the
  sentence's point ("nothing may hard-code the count") survives verbatim.

## Notes & Issues

- Feedback round 1: `backend/tests/services/test_setup_mode_seed.py`'s module docstring declares
  the admin import surface (`services/db_admin.py`) deliberately out of scope — F2 makes that
  sentence false. Test files are off-limits to the coder (the air gap), so it is left for the
  verifier/orchestrator to route.
- Feedback round 1: two more stale skeleton claims sit **outside** F4's seven named locations and
  were therefore left alone — `backend/app/services/db_admin.py`'s module docstring ("Skeleton
  (step 001): … the body is UNIMPLEMENTED") and
  `frontend/src/admin/pages/AssistantModesPage.tsx`'s ("the coder fills the three summary
  cells…"). Both are the same defect class as F4; a follow-up item could sweep them.
- Feedback round 1: `SeedSpec` carries a seeder but no row-key **reader**, so `_missing_seed_keys`
  resolves the live keys with an explicit `if name == "assistant_modes"` branch (each entity has
  its own `db/` module and the registry deliberately holds one entry). A second registry entry
  will need its own branch there; a registered table with no branch degrades to "never
  `seed-missing`", never to a false positive. Widening `SeedSpec` was not done — it is a frozen
  skeleton type.
- Feedback round 1: no persistent model was added or altered (the change is one Pydantic
  response DTO field plus service logic), so `CLAUDE.md`'s JSONL import/export rule requires no
  change — confirmed, not assumed.
- Step 001: the three bulk deletes are select-then-`session.delete` loops returning `len(rows)`, not a raw
  `sqlalchemy.delete()` — keeps `db/` imports unchanged and leaves `llm_servers.clear_all_embedding` the
  only raw-SQLAlchemy spot (feature 006 decision D5).
- Step 001: the import-path seed sits **outside** `import_database`'s `try`, so a seed failure is not
  mis-reported as "the import archive is invalid or corrupt"; `create_database` likewise does not wrap it.
- Step 002: `db/assistant_modes.seed_default_modes` creates rows without `created_at`, so every seeded
  mode reports `created_at: null` until its first save (which sets only `modified_at`). Out of scope here
  (that seed is feature 008's / step 001's) and harmless — the DTO field is nullable — but the mode list
  will show a null creation time forever unless a later change backfills it.
- Step 002: `modified_at` round-trips from SQLite as a **naive** datetime even though the service writes
  `datetime.now(timezone.utc)` — codebase-wide behavior (no `TIMESTAMP(timezone=True)` anywhere), not
  introduced here.
