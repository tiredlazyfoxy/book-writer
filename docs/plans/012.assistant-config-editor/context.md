# 012.assistant-config-editor — feature context

Feature-wide context. Step-specific facts live in each `<SSS>.context.md`; nothing is repeated
between the two files. The feature *definition* is `brief.md` (read-only, `/roadmap`'s file).

## Goal

The admin-only, **instance-global** editor for the FEAT-020 assistant configuration — two halves
over one shared link table:

- **Modes** — the five fixed, seeded `AssistantMode` rows. Edit each one's `system_prompt`, its
  selected tools, and its selected sub-agents.
- **Sub-agents** — admin-created `SubAgent` CRUD: name, system prompt, its own tool selection, its
  accessible-modes selection, an optional `(llm_server_id, model_name)` assignment, and
  disable-not-delete.

This feature **stores configuration**. It does not run it.

## Out of scope — say so, do not build it

| Excluded | Owner | Why |
|---|---|---|
| The runtime that consumes this config — mode determination, prompt composition wiring, tool gating, sub-agent delegation, model resolution | `013.codex` | `assistant-config.md` → "Runtime consumption"; this feature ends at the stored row |
| Tool **implementations** | the owning feature of each tool | The registry is code; tools ship with the feature that needs them (`assistant-config.md` → "Tool registry") |
| Author-facing book / chapter system prompts | book prompt → `fast/003.book-system-prompt`; chapter prompt → `014.chapter-skeleton` (FEAT-019) | Different author, different surface |
| Main-chat model selection | deferred FEAT-013 | FEAT-020 resolves the model question for **sub-agents only** (`assistant-config.md` → "Model resolution") |
| Any change to `resolve_tools`, `prompt_composition.compose_system_prompt`, or `chat_with_tools` | `013.codex` | See "The seam this feature does not touch" below |
| Any new table, column, codec or `TABLE_REGISTRY` entry | — | See "Persistence obligations" below |

## Scope decisions (user-confirmed — do not reopen)

1. **An unconfigured mode grants NO tools.** Zero `mode_tool` rows for a mode is an **empty
   allowlist**, not "everything". The admin must explicitly select tools per mode. This closes the
   product-open `_TBD:` recorded at `assistant-config.md` → "Out of scope" ("whether a mode's tools
   default on or off"). Reason: there must be a way to express *"this mode gets no tools"*, and
   overloading empty to mean *all* makes that state unrepresentable while also making the
   safe-by-default direction the dangerous one. Recorded for the architect in `outcome.md`.

2. **Two sibling admin nav entries** — "Assistant modes" and "Sub-agents", each a **flat
   single-segment route**, exactly matching the existing Users / LLM Servers / Database shape. No
   tabs, no master/detail, no nested routes, no `<Outlet/>`. This is also what keeps steps 007 and
   008 in separate files with no contention.

3. **Sub-agent model validation mirrors `services/chats.py:_validate_model_pair` exactly** —
   half-set refused; the server must exist **and** be `is_active`; `model_name` must appear in that
   server's decoded `enabled_models`. **Accepted consequence, recorded not solved:** deactivating a
   server later leaves stored sub-agent assignments unusable at runtime. Nothing in this feature
   re-validates or rewrites stored assignments when a server changes.

4. **The mode-seeding gap is fixed in step 001.** `db/assistant_modes.py:seed_default_modes()` is
   today called **only** from `services/setup.py:57` (`create_database`). The other first-run path,
   `import_database` (`setup.py:69-87`), never seeds — so an instance bootstrapped by DB import
   would show an empty mode editor. Step 001 calls the existing idempotent seed on the import path
   too. The seed is already UPSERT-safe by `key`, which is precisely *why* the mode PK is the
   natural key (`assistant-config.md` → "Why the primary key is the `key` string").

5. **Duplicate sub-agent name → 409**, following the `services/admin.py:109-113` `username_taken`
   precedent. **Blank name → 400. Half-set model pair → 400.**

6. **Disable-not-delete.** There is **no hard-delete route for sub-agents at all**. Disabling
   detaches the sub-agent from every mode (deletes its `mode_subagent` rows); re-enabling restores
   nothing (US-114.AC-3).

## Planner-derived decisions (not user-confirmed — derived from the architecture, stated with reasoning)

These are settled for this plan; a coder may not re-decide them.

- **Unknown tool names and unknown sub-agent ids are refused at write time (400)**, even though the
  *runtime* skips-and-logs a selection whose tool has since left the registry
  (`assistant-config.md` → "Tool registry"). The two are compatible and address different moments:
  the catalogue is the source of truth, so there is no reason to accept a name it never contained;
  skip-and-log exists for a tool **retired after** a valid selection was stored.
- **A `disabled` sub-agent may not be attached to a mode** — refused 400 from either editor. Reason:
  disabling is defined as detaching from every mode (US-114.AC-2), so accepting an attachment while
  disabled would contradict the same invariant in the same request. US-114.AC-3 only requires that
  a **re-enabled** sub-agent can be selected again.
- **Writes are full-replace (`PUT`), not partial (`PATCH`).** A mode save replaces prompt + tool set
  + sub-agent set; a sub-agent save replaces every editable field. Reason: the link sets already use
  **replace-set** semantics (delete-all-then-recreate for that owner, per `assistant-config.md`), the
  editors always submit a whole form, and under full-replace "absent" is not a state. This
  deliberately does **not** mirror `services/chats.py:update_chat:276-280`'s partial-PATCH quirk
  (re-validate the model pair only when one of the two fields is present) — that quirk exists to
  stop a partial patch wiping an existing pair, and full-replace cannot produce that situation.
  Both model fields are therefore always explicitly present, `null`+`null` meaning *inherit*.
- **No new model-options endpoint.** The sub-agent model picker feeds off the **existing**
  `GET /api/admin/llm-servers` surface (`services/llm_servers.py:102 get_all_servers()`), whose
  `LlmServerResponse` already carries decoded `enabled_models: list[str]` and `is_active`, and whose
  frontend api module (`src/api/llmServers.ts:listServers`) already exists and is already
  admin-gated. Chosen over duplicating `services/chats.py:287-306 list_model_options` because it
  adds **zero** backend surface and zero new frontend types for an admin page that is already
  entitled to the richer payload. The `is_active` filter is applied where the options are built.

## Product ids

**Delivered here (storage side):** UC-095, UC-096, UC-097; US-110.AC-1, US-110.AC-2, US-110.AC-4
(the *stored* empty-prompt state), US-111.AC-1, US-112.AC-1, US-112.AC-2, US-113.AC-1..AC-6,
US-114.AC-1..AC-4.

**Delivered by `013.codex`, deliberately NOT covered by a `[test]` DoD item here — this is not a
coverage gap:**

| AC | Why it is not testable in this feature |
|---|---|
| US-110.AC-3 — "when the assistant **runs** in that mode, the prompt is applied" | Runtime prompt composition. Nothing here loads `AssistantMode.system_prompt` into `prompt_composition.compose_system_prompt`'s `mode` layer. |
| US-111.AC-2 — "an unselected tool is **unavailable** to it" | Runtime tool gating. Nothing here calls `resolve_tools`. |
| US-112.AC-3 — "it may **delegate** only to sub-agents in that set" | Runtime delegation. There are no synthetic delegation tools in this feature. |

A verifier reading the coverage contract should expect these three ACs to be **absent** by design.
The storage-side halves of the same requirements *are* covered (steps 002 and 004).

## The seam this feature does not touch

`services/tools.py:78-103 resolve_tools(allowed_names)` treats `None` as *"the whole registry"*.
That branch is the seam mode-gating replaces. **`012` does not change it** — this feature only
persists the per-mode allowlist that `013` will pass in. Likewise, nothing here loads a mode's
prompt into `services/prompt_composition.py:compose_system_prompt`. Both wirings are `013`'s, and
`011.chat-panel`'s `context.md` already names `013.codex` as their owner. Recorded in `outcome.md`.

## Inbound dependency — `011.chat-panel` step 002

`backend/app/services/tools.py` (`ToolDef`, `TOOL_REGISTRY`, `resolve_tools`, `build_tool_bindings`)
and `backend/app/models/schemas/tools.py` (`WebSearchArgs`) are **delivered** — they are
`011.chat-panel` step 002's output, and that step reads `done` / PASS (2026-07-25) in
`docs/plans/011.chat-panel/status.md`.

- **`012` reads `TOOL_REGISTRY`; it never creates or redefines it.** Step 002 of this feature must
  not add a `ToolDef`, a registry, or a tool.
- **Gate — now satisfied.** Steps 002 onward were held until `docs/plans/011.chat-panel/status.md`
  read `done` for its step 002, because `011` step 002 is the sole owner of that module and a
  second definition here would have forked the registry. That precondition **is met**, so steps
  **002 onward are unblocked**. The gate was always the status table, never a snapshot of the
  working tree.
- **Step 001 was never blocked** — it touches only `db/` and `services/setup.py`.
- `TOOL_REGISTRY` has exactly **one** entry today (`web_search`). Every surface built here must be
  correct for zero, one, or many entries; nothing may hard-code the count.

## Architecture sources

- `docs/architecture/assistant-config.md` — **the primary design source.** The config model, the
  natural-key PK rationale, the three link tables, replace-set semantics, persistence obligations,
  and the runtime slice `013` will build.
- `docs/architecture/authorization.md` → "Global assistant configuration (FEAT-020) — admin only" —
  `require_role(admin)`, same configuration class as LLM servers, never a `BookAccess` capability.
- `docs/architecture/backend.md` (+ the `backend/` sub-tree) — the enforced 4-layer rule.
- `docs/architecture/backend/features.md` — the `routes/admin/llm_servers.py` route/error/DTO
  precedent every backend step here copies.
- `docs/architecture/frontend.md` — the enforced MobX / Mantine / `api/` rules steps 006–008 obey.
- `docs/product/use-cases/FEAT-020.assistant-modes-subagents.md` and
  `docs/product/stories/FEAT-020.assistant-modes-subagents.md` — UC-095/096/097, US-110..US-114.

## Tables — all five already exist, built by `008.data-domain`. Create none.

| Model class | Module | `__tablename__` |
|---|---|---|
| `AssistantMode` | `backend/app/models/assistant_mode.py` | `assistant_modes` |
| `SubAgent` | `backend/app/models/sub_agent.py` | `sub_agents` |
| `ModeTool` | `backend/app/models/mode_tool.py` | `mode_tool` *(singular)* |
| `SubagentTool` | `backend/app/models/subagent_tool.py` | `subagent_tool` *(singular)* |
| `ModeSubagent` | `backend/app/models/mode_subagent.py` | `mode_subagent` *(singular)* |

Watch the casing: `SubAgent` (capital A) but `SubagentTool` / `ModeSubagent` (lowercase). The
`TABLE_REGISTRY` labels are **plural** and deliberately differ from `__tablename__`. All five are
registered at the `init_db` model-registration seam, `backend/app/db/engine.py:66-70`.

Shapes every backend step assumes:

- `AssistantMode`: `key: str` **primary key** (natural key, *not* a snowflake), `system_prompt: str
  | None`, `created_at`, `modified_at`. **No `__table_args__`** — "the fixed five" is a seeding
  fact, not a DB constraint.
- `SubAgent`: snowflake `id`, `name` (unique + indexed), `system_prompt: str` (**required,
  non-null**), `disabled: bool = False`, `llm_server_id: int | None` (FK → `llm_servers.id`),
  `model_name: str | None`, timestamps. **There is no `accessible_modes` column** — mode access
  *is* the `mode_subagent` link table. The model-pair invariant is documented in
  `models/sub_agent.py:35-37` as a **service** rule, not a DB one.
- Each link table: snowflake `id` PK plus a `UniqueConstraint` on its natural pair —
  `uq_mode_tool_mode_key_tool_name`, `uq_subagent_tool_sub_agent_id_tool_name`,
  `uq_mode_subagent_mode_key_sub_agent_id`. `tool_name` is a **string reference into
  `TOOL_REGISTRY`, never an FK**.

## Persistence obligations — nothing to do, and that is the point

Root `CLAUDE.md` requires import/export to move in the same change as any model change. **This
feature adds no table and no column**, so it owes **no codec change and no `TABLE_REGISTRY`
change**. All ten codecs already exist in `services/db_import_export.py`
(`_assistant_mode_to_dict:161` … `_dict_to_mode_subagent:327`), and the registry order at
`:958-966` is pinned by `tests/test_data_domain_assistant_core.py:309` and
`tests/test_data_domain_assistant_links.py:357`. This is stated explicitly so the rule is visibly
**satisfied**, not silently skipped. **No step may touch `services/db_import_export.py`.**

## Replace-set semantics (steps 002 and 004)

A selection save is **delete-all-then-recreate for that owner**, per `assistant-config.md`. That is
why the db layer needs `delete_by_mode` / `delete_by_sub_agent` rather than per-row deletes. Applies
to all three link tables:

- mode's tools → `mode_tools.delete_by_mode(key)` then one `create` per selected name
- mode's sub-agents → `mode_subagents.delete_by_mode(key)` then one `create` per selected id
- sub-agent's tools → `subagent_tools.delete_by_sub_agent(id)` then one `create` per name
- sub-agent's modes → `mode_subagents.delete_by_sub_agent(id)` then one `create` per key

**The mode↔sub-agent link is one row set with two editors** (US-112.AC-2). `mode_subagents` is
written from the mode side (`delete_by_mode`) and from the sub-agent side (`delete_by_sub_agent`);
there is no second table and no direction-of-truth ambiguity.

## Cross-cutting backend constraints (steps 001–005)

- **Four-layer separation is enforced.** `routes/` is HTTP only; `services/` may never touch a
  session, `select()`, `session.add()` or `session.exec()`; `db/` is session-free, one module per
  entity, opening its own session via `get_standalone_session()`; `models/` is tables plus
  `models/schemas/` DTOs with no logic. Namespace imports throughout (`from app.db import
  sub_agents` → `await sub_agents.get_by_id(...)`).
- **Timestamps are set explicitly in the service** with `datetime.now(timezone.utc)`. There is no
  ORM `onupdate` anywhere in this codebase.
- **Every id is a `str` at the JSON boundary** — snowflakes exceed the JS safe-integer range.
  `AssistantMode.key` is already a string and is emitted verbatim.
- **DTOs are hand-mapped**, never `model_dump()` of an ORM row — the
  `services/llm_servers.py:80 _to_response` precedent.
- **A Pydantic model carrying a `model_name` field must set
  `model_config = ConfigDict(protected_namespaces=())`** — the `models/schemas/chats.py:146-162`
  precedent. Without it Pydantic warns on the `model_` prefix.
- **Typed service errors, mapped at the route.** One reason enum + one exception per service, the
  `services/llm_servers.py:47/66` shape (hyphenated string enum values); the route owns a
  module-level `dict[Reason, int]` plus a `_map_*` helper, the
  `routes/admin/llm_servers.py:46-61` shape. 403 comes from `require_role` itself, never from the
  handler.

## Cross-cutting frontend constraints (steps 006–008)

- **`observer` on every component**, no exceptions. State is a `<Page>State` class of observable
  data plus pure `get` computeds; every effectful operation is an external
  `(state, args, signal)` function using `runInAction`; every loadable is an async trio
  (`x` / `xStatus: "idle"|"loading"|"ready"|"error"` / `xError`).
- **No custom `useX` hooks**, no `useCallback` / `useMemo` / `useReducer`, no React context, no
  Mantine `useForm`, no zod. `useState` only to own a stable state instance (and, per the
  `LlmServersPage.tsx:50-54` precedent, to hold **modal targets** — those live in component-local
  `useState`, *not* in page state). `useEffect` only once at page level with deps `[state]`.
- **All HTTP lives in `src/api/`**; `signal?: AbortSignal` is always the trailing argument; list
  envelopes are unwrapped **in the api module**, not modelled in the type. Wire DTOs are
  hand-written `.d.ts` in `src/types/`, wire-exact `snake_case`, **ids typed `string`**, no `any`,
  no runtime validation. Runtime constants (option arrays) live in the `.ts` api module, **never**
  in a `.d.ts` (`api/llmServers.ts:27-31`).
- **Loader body shape** (`llmServersPageState.ts:33`): `runInAction` set loading + clear error →
  `await` the api call → `if (signal?.aborted) return;` → `runInAction` commit. `catch` →
  aborted-guard → `err instanceof ApiError` ? `runInAction` set error : **rethrow**. Mutations
  re-call the loader; **no optimistic updates**.
- **Draft convention** — a split `*Draft.ts` beside the modal (the newer feature-006 convention,
  `components/llm-servers/serverFormDraft.ts`), never the older in-file `components/users/*` style.
  A draft owns its fields, `serverErrors: Record<string,string>`, `submitStatus`, and three
  computeds: `clientErrors` (**keys are WIRE field names**), `errors` (`{...clientErrors,
  ...serverErrors}`, server wins), `canSubmit`. `submit*Form(draft, id | null, onSaved, signal)`
  order: clear serverErrors + status loading → api → `catch (err instanceof ApiError)` → write
  `serverErrors` + status error + **return**; non-`ApiError` → aborted-guard, status error,
  **rethrow** → status ready → `onSaved()`.
- **Multi-select idiom** — `ScrollArea.Autosize mah={360}` → `Stack gap="xs"` → one `Checkbox` per
  item, `checked={draft.selected.has(x)}`, `onChange` **reassigning a fresh `Set`** (never mutating
  in place — an observability requirement, `modelsModalDraft.ts:12-13`). The repo has **no**
  `MultiSelect`, `Checkbox.Group`, `Chip`, `Drawer`, `Textarea` or confirmation dialog. Copy
  `components/llm-servers/ModelsModal.tsx:48-64`.
- **Page layout template** (`LlmServersPage.tsx`): `Container size="lg" py="md"` → header `Group`
  (Title + action `Button`) → error `Text c="red"` → `Loader` **or** `Table striped
  highlightOnHover` with a trailing 60px `Menu` / `ActionIcon IconDots` column. Modals are mounted
  **conditionally** so each open constructs a fresh draft.
- **`ApiError`** — `src/api/client.ts:6`, `class ApiError extends Error { constructor(public
  status: number, message: string, public details?: unknown) }`. `request<T>` injects the bearer
  token, returns `undefined as T` for 204, and does one silent refresh on 401.

## Testing facts shared by every step

**Backend (001–005)** — one `backend/tests/conftest.py` provides autouse `_reset_db_ready` (`:33`),
`db(tmp_path) -> DbConfig` (`:47`, temp SQLite + `init_engine` + `init_db`) for db/service tests,
and `http_client` (`:62`, in-process ASGI over the real `app.main.app` with `BOOKWRITER_DB_PATH`
monkeypatched) for route tests. `asyncio_mode = "auto"`, so async tests need no decorator.
**There are no shared user fixtures** — each suite defines module-local `_`-prefixed async helpers;
copy `backend/tests/routes/admin/test_llm_servers.py`'s `_auth_header(token):81`,
`_seed_user(...):101` (real bcrypt hash + `generate_signing_key()` + `last_key_update`, then
`set_db_ready(True)`) and `_seed_admin(http_client, username="root"):128`. Layout:
`tests/routes/admin/`, `tests/services/`, `tests/db/`, plus flat `tests/test_data_domain_*.py`.
Naming: `test_<behavior>__DoD<N>[_US###_AC#]`. **No network in any test.** Existing coverage of the
five tables is `test_data_domain_assistant_core.py`, `test_data_domain_assistant_links.py`,
`test_data_domain_mode_seed.py`; **there are no tests for an assistant-config service or route**,
because neither exists.

**Frontend (006–008)** — `vitest.config.ts` is jsdom with **`globals: false`**, so every spec
imports `describe/it/expect/vi` from `"vitest"`; `restoreMocks: true`, `setupFiles:
["./tests/setup.ts"]`. Render **only** via `renderWithProviders(ui, { route? })`
(`tests/support/render.tsx:29`) — `MantineProvider env="test"` makes Menus and Modals render inline
and **synchronously**, so no `waitFor` is needed for them; routes passed in are basename-stripped.
Specs **mock the `src/api/*` module with a module factory**, never `fetch`, and the factory **must
supply every named export the rendered subtree touches — including runtime option constants — or
render throws** (the caveat recorded at `tests/user/BookshelfPage.test.tsx:34-41`). Set
implementations in `beforeEach` via `vi.mocked(...)`, because `restoreMocks` wipes them. Typed
fixture factories, not partials. `frontend/tests/admin/` currently holds only shell-level specs
(`AdminNav`, `AdminShell`, `adminGate`, `AdminUserMenu`, `navItems`, `routes`) — **no admin page
test exists at all**; step 007 writes the first. Copy the idiom from
`frontend/tests/user/BookshelfPage.test.tsx`.

## Build and test gates (root `CLAUDE.md` — cite, never invent)

- **Backend steps 001–005:** `cd backend && .venv/Scripts/python -m pytest`. There is **no separate
  backend typecheck**.
- **Frontend steps 006–008:** `cd frontend && npm run build` (= `tsc && vite build`),
  `cd frontend && npm test`, `cd frontend && npm run test:types`.
  `frontend/tsconfig.json` has `include: ["src"]`, so a broken spec can never break the bundle;
  `npm run test:types` is the only program covering `tests/`.
- **No linter is configured.** Do not run one.

## Steps

| Step | File | Layer | Depends on |
|---|---|---|---|
| 001 | `001.db-layer-completion.md` | backend `db/` + `services/setup.py` | none |
| 002 | `002.mode-config-service.md` | backend `models/schemas/` + `services/` | 001 (+ `011` step 002) |
| 003 | `003.subagent-crud.md` | backend `models/schemas/` + `services/` | 002 |
| 004 | `004.subagent-links-and-disable.md` | backend `models/schemas/` + `services/` | 003 |
| 005 | `005.admin-routes.md` | backend `routes/admin/` + `main.py` | 004 |
| 006 | `006.frontend-api-and-nav.md` | frontend types + api + shell | 005 |
| 007 | `007.modes-page.md` | frontend admin page | 006 |
| 008 | `008.subagents-page.md` | frontend admin page | 006 |

Steps 001–005 run **in order**. 007 and 008 both depend on 006 and are **independent of each
other**.
