# Feature 006 — llm-server-connections

| Step | File                             | Status  | Verifier | Date |
|------|----------------------------------|---------|----------|------|
| 001  | `001.model-db-importexport.md`   | done    | PASS     | 2026-07-23 |
| 002  | `002.schemas-secrets-service.md` | done    | PASS     | 2026-07-23 |
| 003  | `003.probe-connection.md`        | done    | PASS     | 2026-07-23 |
| 004  | `004.admin-routes-wiring.md`     | done    | PASS     | 2026-07-23 |
| 005  | `005.frontend-base.md`           | done    | PASS     | 2026-07-23 |
| 006  | `006.frontend-modals.md`         | done    | PASS     | 2026-07-23 |

## Files Changed

### Step 001 — LlmServer model + db module + import/export codec
- `backend/app/db/llm_servers.py` — implemented the session-free data-access bodies (get_by_id/get_all/get_active/create/update, first-delete-returns-bool, clear_all_embedding via raw `sqlalchemy.update()`, get_embedding_server)
- `backend/app/services/db_import_export.py` — implemented the `_llm_server_to_dict` / `_dict_to_llm_server` codec bodies (enabled_models kept as JSON string, api_key verbatim, datetimes via isoformat)

### Step 003 — probe / test-connection (first `llm`-client wiring)
- `backend/app/services/llm_servers.py` — implemented `_create_client` (branch on backend_type → `OpenAIAPIClient`/`LlamaSwapAPIClient`, `bearer_token=resolved_key`) + `probe_models` (raw get_by_id → not_found; function-local `secrets.resolve_env_ref` before the try so env_not_set propagates; construct client, `await list_models()`, return sorted; catch `aiohttp.ClientError`/`LLMError`/`ValueError` → probe_failed; persists nothing)

### Step 002 — schemas + `$ENV` resolver + service (CRUD / enable / embedding / masking)
- `backend/app/services/secrets.py` — implemented `resolve_env_ref` (None→None, `$VAR`→`os.environ[VAR]` else `LlmServerError(env_not_set)`, literal verbatim)
- `backend/app/services/llm_servers.py` — implemented the hand-written `_to_response` mapper + CRUD/enable/embedding bodies (missing-field before invalid-backend-type on create; api_key `""`→clear / None→unchanged on update; clear-all-then-set embedding; `datetime.now(timezone.utc)` stamps)
- `backend/app/models/schemas/llm_servers.py` — DTO definitions left as frozen by the skeleton (no body changes needed)

### Step 006 — Admin SPA LLM-servers modals (form / models / embedding)
- `frontend/src/admin/components/llm-servers/serverFormDraft.ts` — filled `submitServerForm` (create when serverId null with `api_key: apiKey || null`; else update omitting api_key when empty; ApiError→`serverErrors.form`, "ready"+onSaved on success; mobx/ApiError/api imports added)
- `frontend/src/admin/components/llm-servers/modelsModalDraft.ts` — filled `probeModelsAction` (probe→available, error sets probeError+available=[] but leaves selected) and `submitEnabledModels` (setEnabledModels with sorted Array.from(selected); saveError trio; onSaved)
- `frontend/src/admin/components/llm-servers/embeddingModalDraft.ts` — filled `probeModelsAction` (same shape) and `submitEmbedding` (guards selected non-null; setEmbedding; saveError trio; onSaved)
- `frontend/src/admin/components/llm-servers/ServerFormModal.tsx` — no body change needed (skeleton shell already complete + compiling)
- `frontend/src/admin/components/llm-servers/ModelsModal.tsx` — no body change needed (skeleton shell already complete + compiling)
- `frontend/src/admin/components/llm-servers/EmbeddingModal.tsx` — no body change needed (skeleton shell already complete + compiling)
- `frontend/src/admin/pages/LlmServersPage.tsx` — no body change needed (skeleton already wired component-local formTarget/modelsTarget/embeddingTarget useState, header/menu actions, and the three conditional modal mounts)

### Step 005 — Admin SPA LLM-servers base (types + api + list page + nav)
- `frontend/src/api/llmServers.ts` — filled the 8 resource fn bodies over `request<T>` (listServers unwraps `.items`, probeModels unwraps `.models`, enabled-models/embedding bodies wrapped; added `LlmServersListResponse`/`AvailableModels` type imports)
- `frontend/src/admin/pages/llmServersPageState.ts` — implemented `loadServers`/`deleteServerAction`/`clearEmbeddingAction` mirroring loadUsers/disableUserAction (runInAction trio, aborted guards, ApiError-narrow, reload-after-mutation)
- `frontend/src/admin/pages/LlmServersPage.tsx` — reshaped the table to Name(+teal embedding badge)/Type/Base URL/Key(presence)/Models/Active(+menu) columns, inactive rows dimmed, per-row Delete + conditional Clear-Embedding, step-006 modal seams left
- `frontend/src/types/llmServers.d.ts` — DTOs left as frozen by skeleton (no field changes needed)
- `frontend/src/admin/routes.tsx` — sibling `/llm-servers` route already present from skeleton (left as-is)
- `frontend/src/admin/App.tsx` — `Users | LLM Servers` nav + token-gate-first already present from skeleton (left as-is)

### Step 004 — admin routes + router wiring (HTTP surface)
- `backend/app/routes/admin/llm_servers.py` — filled the 9 handler bodies behind the frozen router/gates/error-map (list→get_all_servers; create/update/delete/enabled-models/embedding/available-models wrapped in try/except mapping `LlmServerError` via `_map_llm_server_error`; get-embedding + list + clear-embedding raise nothing; unwrapped `EnabledModelsRequest.enabled_models` and `SetEmbeddingRequest.model`; 204 handlers return None)
- `backend/app/main.py` — router include already present from skeleton (left as-is)
- `backend/app/routes/admin/__init__.py` — pure docstring marker (left as-is)

## Rewrites

### Session 2026-07-23 — snowflake ids + export key redaction (review.md R1, R2)
- R1 LlmServer → snowflake ids (mirror User) — `backend/app/models/llm_server.py`, `backend/app/models/schemas/llm_servers.py`, `backend/app/services/llm_servers.py`, `frontend/src/types/llmServers.d.ts`, `frontend/src/api/llmServers.ts`, `frontend/src/admin/pages/llmServersPageState.ts`, `frontend/src/admin/pages/LlmServersPage.tsx`, `frontend/src/admin/components/llm-servers/{serverFormDraft.ts,modelsModalDraft.ts,embeddingModalDraft.ts}`, `backend/tests/db/test_llm_servers.py`, `backend/tests/services/test_llm_servers.py`, `backend/tests/routes/admin/test_llm_servers.py` — PK changed to `id: int = Field(default_factory=generate_id, primary_key=True)` (added `from app.ids import generate_id`), mirroring `User`. DTO edge stringified: `LlmServerResponse.id: str`, `EmbeddingConfigResponse.server_id: str | None`; `_to_response`/`get_embedding_config` emit `str(server.id)`. All internal db/service/route param types stay `int` (routes keep `server_id: int` path params; FastAPI coerces). Frontend id wire type `number → string` on the DTOs, api-fn params, and page/draft `serverId`/delete-id params (modal `.tsx` pass `server.id` transparently). Tests: service test now asserts `isinstance(resp.id, str)` and converts DTO ids back with `int(resp.id)` at db/service call boundaries (mirrors `test_admin_users.py`); `config.server_id == created.id` comparisons hold in the new string form; route test unchanged at runtime (ids string end-to-end, `NONEXISTENT_ID` still valid); db-layer round-trip/delete/embedding coverage intact. No import/export codec change (already `str(id)`/`int(raw_id)`).
- R2 Export redacts raw-literal LLM api keys (keeps $ENV tokens) — `backend/app/services/db_import_export.py`, `backend/tests/services/test_db_import_export_llm_servers.py` — `_llm_server_to_dict` now emits `api_key` only when `None` or `$`-prefixed (a `$ENV_VAR` pointer), otherwise `None`; `_dict_to_llm_server` unchanged; `_user_to_dict`/`_dict_to_user` untouched. Test `test_api_key_exported_verbatim_not_masked__DoD5` inverted → `test_api_key_redacted_on_export__R2`, now asserting (a) a raw literal `"sk-secret"` is redacted to `None` on export + restores as `None`, and (b) a `$ENV` token is preserved verbatim + restores unchanged. The all-fields round-trip test seeds a `$ENV` token (survives), so round-trip coverage stays intact. **This intentionally supersedes step-001 DoD-5's "api_key preserved verbatim … not masked" clause and D6** — the inverted assertion is the new policy, not a regression; codec api_key handling is still fully exercised (redaction + `$ENV` preservation).

## Skeleton

### Step 001 — frozen interface (2026-07-23)

**`backend/app/models/llm_server.py`** — new module. `class LlmServer(SQLModel, table=True)`, `__tablename__ = "llm_servers"`. Fields (declarative table, no behavior):
- `id: int | None = Field(default=None, primary_key=True)` (autoincrement int PK per D1)
- `name: str`
- `backend_type: str`
- `base_url: str`
- `api_key: str | None = Field(default=None)`
- `enabled_models: str = "[]"`
- `is_active: bool = True`
- `is_embedding: bool = False`
- `embedding_model: str | None = Field(default=None)`
- `created_at: datetime | None = Field(default=None)`
- `modified_at: datetime | None = Field(default=None)`

**`backend/app/db/llm_servers.py`** — new module. Session-free async data access:
- `async def get_by_id(server_id: int) -> LlmServer | None` — new
- `async def get_all() -> list[LlmServer]` — new
- `async def get_active() -> list[LlmServer]` — new
- `async def create(server: LlmServer) -> LlmServer` — new
- `async def update(server: LlmServer) -> None` — new
- `async def delete(server_id: int) -> bool` — new (first delete pattern; `False` = no row matched)
- `async def clear_all_embedding() -> None` — new (sanctioned raw `sqlalchemy.update()` spot, D5)
- `async def get_embedding_server() -> LlmServer | None` — new

**`backend/app/services/db_import_export.py`** — amended (codec pair + registry tuple):
- `def _llm_server_to_dict(server: LlmServer) -> dict[str, object]` — new
- `def _dict_to_llm_server(data: dict[str, object]) -> LlmServer` — new
- `TABLE_REGISTRY` appended with `("llm_servers", LlmServer, _llm_server_to_dict, _dict_to_llm_server)` after the `users` entry (D6). Added `from app.models.llm_server import LlmServer` import.

**`backend/app/db/engine.py`** — amended (registration hook only): added `import app.models.llm_server  # noqa: F401` next to the existing `app.models.user` import in `_register_models()`.

- Caller-compile edits (out of Source-files scope): None.

### Step 002 — frozen interface (2026-07-23)

**`backend/app/models/schemas/llm_servers.py`** — new module. Plain Pydantic `BaseModel`s (no `model_config`):
- `CreateLlmServerRequest` — `name: str`, `backend_type: str`, `base_url: str`, `api_key: str | None = None`, `is_active: bool = True` — new
- `UpdateLlmServerRequest` — `name: str | None = None`, `backend_type: str | None = None`, `base_url: str | None = None`, `api_key: str | None = None`, `is_active: bool | None = None` (all optional) — new
- `LlmServerResponse` — `id: int`, `name: str`, `backend_type: str`, `base_url: str`, `has_api_key: bool`, `enabled_models: list[str]`, `is_active: bool`, `is_embedding: bool`, `embedding_model: str | None`, `created_at: datetime | None`, `modified_at: datetime | None` (NO `api_key`; `id` is `int`, not str-coerced) — new
- `LlmServersListResponse` — `items: list[LlmServerResponse]` — new
- `AvailableModelsResponse` — `models: list[str]` — new
- `EnabledModelsRequest` — `enabled_models: list[str]` — new
- `SetEmbeddingRequest` — `model: str` — new
- `EmbeddingConfigResponse` — `server_id: int | None`, `server_name: str | None`, `base_url: str | None`, `backend_type: str | None`, `model: str | None`, `has_api_key: bool` (all-`None` indicator when no embedding server) — new

**`backend/app/services/llm_servers.py`** — new module. Typed error + backend-type constant + CRUD/enable/embedding service:
- `_VALID_BACKEND_TYPES: set[str] = {"llama-swap", "openai"}` (module constant, D2) — new
- `class LlmServerErrorReason(str, enum.Enum)` — frozen 5 cases: `invalid_backend_type = "invalid-backend-type"`, `missing_field = "missing-field"`, `not_found = "not-found"`, `env_not_set = "env-not-set"`, `probe_failed = "probe-failed"` — new
- `class LlmServerError(Exception)` — `__init__(self, reason: LlmServerErrorReason, message: str = "") -> None`; exposes `.reason`, `.message` — new
- `def _to_response(server: LlmServer) -> LlmServerResponse` (private, sync mapper) — new
- `async def get_all_servers() -> LlmServersListResponse` (ordered by name, wrapped in list envelope) — new
- `async def get_server(server_id: int) -> LlmServerResponse` (single-get helper; not-found → error) — new
- `async def create_server(req: CreateLlmServerRequest) -> LlmServerResponse` — new
- `async def update_server(server_id: int, req: UpdateLlmServerRequest) -> LlmServerResponse` — new
- `async def delete_server(server_id: int) -> None` (delete `False` → not-found error) — new
- `async def set_enabled_models(server_id: int, models: list[str]) -> LlmServerResponse` (bare `list[str]`, mirrors reference/DoD-style; route unwraps `EnabledModelsRequest.enabled_models`) — new
- `async def set_embedding_server(server_id: int, model: str) -> LlmServerResponse` (bare `model: str` per DoD-6 `set_embedding_server(id, model)`; route unwraps `SetEmbeddingRequest.model`) — new
- `async def clear_embedding_server() -> None` — new
- `async def get_embedding_config() -> EmbeddingConfigResponse` (all-`None` indicator when none) — new

**`backend/app/services/secrets.py`** — new module. Shared `$ENV` resolver (D3):
- `def resolve_env_ref(value: str | None) -> str | None` (sync; `None`→`None`, `$VAR`→`os.environ[VAR]` else raises `LlmServerError(env_not_set)`, literal→verbatim) — new

**Import-direction decision (cycle avoidance):** `secrets.py` imports `LlmServerError` / `LlmServerErrorReason` **from** `services/llm_servers.py` at module level; `services/llm_servers.py` does **NOT** import `secrets` (its step-002 functions never resolve a key). The module graph is acyclic in both import orders (verified). Step 003's probe must reach the resolver via a **function-local** `from app.services import secrets` to preserve acyclicity. This deviates from the briefing's "import the resolver in llm_servers this step" — that import is unnecessary for step 002 and would create the cycle; deferred to step 003 as a function-local import.

- Caller-compile edits (out of Source-files scope): None (all three files are new; no existing caller imports them yet).

### Step 003 — frozen interface (2026-07-23)

**`backend/app/services/llm_servers.py`** — amended (two new symbols added; step-002 functions untouched):
- `def _create_client(server: LlmServer, resolved_key: str | None) -> LLMClient` — new (private, **sync**). The monkeypatch construction seam; `resolved_key` is an explicit param (never resolved inside) so a fake client can capture it (US-021.AC-1). Body: `raise NotImplementedError`.
- `async def probe_models(server_id: int) -> list[str]` — new. Body: `raise NotImplementedError`.
- Module-level imports added: `import aiohttp` and `from llm import LLMClient, LLMError, LlamaSwapAPIClient, OpenAIAPIClient` (external deps, no cycle). `from app.services import secrets` deliberately NOT added at module level (cycle) — the coder adds it function-local inside `probe_models`.

- Caller-compile edits (out of Source-files scope): None (no existing caller imports these new symbols yet).

### Step 004 — frozen interface (2026-07-23)

**`backend/app/routes/admin/llm_servers.py`** — new module. `router = APIRouter(prefix="/api/admin/llm-servers", tags=["admin-llm-servers"])`. Per-endpoint gate `caller: User = Depends(auth_service.require_role(UserRole.admin))` (LAST param). Response models via return annotation (no `response_model=`). Bodies `raise NotImplementedError`.

Error→status map (REAL, frozen structure):
- `_LLM_SERVER_ERROR_STATUS: dict[llm_servers_service.LlmServerErrorReason, int]` — `missing_field`→400, `invalid_backend_type`→400, `env_not_set`→400, `not_found`→404, `probe_failed`→502 — new
- `def _map_llm_server_error(err: llm_servers_service.LlmServerError) -> HTTPException` — new

Nine endpoints, frozen in this declaration order (D5 — static `/embedding` before `/{server_id}`):
- `@router.get("")` — `async def list_servers(caller: User = ...) -> LlmServersListResponse` — 200 — new
- `@router.post("", status_code=201)` — `async def create_server(payload: CreateLlmServerRequest, caller: User = ...) -> LlmServerResponse` — new
- `@router.get("/embedding")` — `async def get_embedding_config(caller: User = ...) -> EmbeddingConfigResponse` — 200 — new
- `@router.delete("/embedding", status_code=204)` — `async def clear_embedding_config(caller: User = ...) -> None` — new
- `@router.put("/{server_id}")` — `async def update_server(server_id: int, payload: UpdateLlmServerRequest, caller: User = ...) -> LlmServerResponse` — 200 — new
- `@router.delete("/{server_id}", status_code=204)` — `async def delete_server(server_id: int, caller: User = ...) -> None` — new
- `@router.get("/{server_id}/available-models")` — `async def get_available_models(server_id: int, caller: User = ...) -> AvailableModelsResponse` — 200 — new
- `@router.put("/{server_id}/enabled-models")` — `async def set_enabled_models(server_id: int, payload: EnabledModelsRequest, caller: User = ...) -> LlmServerResponse` — 200 — new
- `@router.put("/{server_id}/embedding", status_code=204)` — `async def set_embedding_server(server_id: int, payload: SetEmbeddingRequest, caller: User = ...) -> None` — new

**`backend/app/main.py`** — amended (composition root, wiring only): added `from app.routes.admin import llm_servers as admin_llm_servers` and `app.include_router(admin_llm_servers.router)` after the `admin_users` include (no include-time prefix/tags).

**`backend/app/routes/admin/__init__.py`** — unchanged (pure docstring marker; does not aggregate).

- Caller-compile edits (out of Source-files scope): None.

### Step 005 — frozen interface (2026-07-23)

**`frontend/src/types/llmServers.d.ts`** — new module (pure `.d.ts`, no runtime values, no `any`):
- `export type LlmBackendType = "openai" | "llama-swap";` — new
- `interface LlmServer` — new: `id: number; name: string; backend_type: LlmBackendType; base_url: string; has_api_key: boolean; enabled_models: string[]; is_active: boolean; is_embedding: boolean; embedding_model: string | null; created_at: ISODateString | null; modified_at: ISODateString | null;` (NO `api_key`)
- `interface LlmServersListResponse { items: LlmServer[]; }` — new
- `interface CreateLlmServerRequest { name: string; backend_type: LlmBackendType; base_url: string; api_key?: string | null; is_active?: boolean; }` — new
- `interface UpdateLlmServerRequest { name?: string; backend_type?: LlmBackendType; base_url?: string; api_key?: string | null; is_active?: boolean; }` — new
- `interface AvailableModels { models: string[]; }` — new
- `interface EnabledModelsRequest { enabled_models: string[]; }` — new
- `interface SetEmbeddingRequest { model: string; }` — new
- `interface EmbeddingConfig { server_id: number | null; server_name: string | null; base_url: string | null; backend_type: string | null; model: string | null; has_api_key: boolean; }` — new
- Imports `ISODateString` from `./common`.

**`frontend/src/api/llmServers.ts`** — new module. `const BASE = "/api/admin/llm-servers";` over shared `request<T>`; `signal?` last on every fn; bodies throw (coder fills, incl. `.items`/`.models` unwrapping):
- `export interface BackendOption { value: LlmBackendType; label: string; }` — new
- `export const BACKEND_OPTIONS: BackendOption[]` — new (runtime option list; lives here not in the `.d.ts` — see note below)
- `export async function listServers(signal?: AbortSignal): Promise<LlmServer[]>` — new (GET, unwrap `.items`)
- `export async function createServer(body: CreateLlmServerRequest, signal?: AbortSignal): Promise<LlmServer>` — new (POST)
- `export async function updateServer(id: number, body: UpdateLlmServerRequest, signal?: AbortSignal): Promise<LlmServer>` — new (PUT `${BASE}/${id}`)
- `export async function deleteServer(id: number, signal?: AbortSignal): Promise<void>` — new (DELETE `${BASE}/${id}`)
- `export async function probeModels(id: number, signal?: AbortSignal): Promise<string[]>` — new (GET `${BASE}/${id}/available-models`, unwrap `.models`)
- `export async function setEnabledModels(id: number, models: string[], signal?: AbortSignal): Promise<LlmServer>` — new (PUT `${BASE}/${id}/enabled-models`, body `{ enabled_models: models }`)
- `export async function setEmbedding(id: number, model: string, signal?: AbortSignal): Promise<void>` — new (PUT `${BASE}/${id}/embedding`, body `{ model }`)
- `export async function clearEmbedding(signal?: AbortSignal): Promise<void>` — new (DELETE `${BASE}/embedding`)

**`frontend/src/admin/pages/llmServersPageState.ts`** — new module. Async trio only + external effect fns (`runInAction`/`ApiError`-narrow; bodies throw):
- `export class LlmServersPageState` — new: `servers: LlmServer[] = []; serversStatus: "idle" | "loading" | "ready" | "error" = "idle"; serversError: string | null = null;` + `makeAutoObservable(this)` in ctor; NO effectful methods.
- `export async function loadServers(state: LlmServersPageState, signal?: AbortSignal): Promise<void>` — new
- `export async function deleteServerAction(state: LlmServersPageState, id: number, signal?: AbortSignal): Promise<void>` — new
- `export async function clearEmbeddingAction(state: LlmServersPageState, signal?: AbortSignal): Promise<void>` — new

**`frontend/src/admin/pages/LlmServersPage.tsx`** — new module. `export const LlmServersPage` — `observer`-wrapped page; `useState(() => new LlmServersPageState())`; page-level `useEffect` (deps `[state]`) mount-load/unmount-abort; `refresh`/`handleDelete`/`handleClearEmbedding` inner fns; table with backend-type / has_api_key-presence / enabled-model-count / embedding badges + per-row Delete + conditional Clear-Embedding menu items. Header `Add server` button is a step-006 modal SEAM (currently wired to `refresh`).

**`frontend/src/admin/routes.tsx`** — amended: added `import { LlmServersPage } from "./pages/LlmServersPage";` and sibling `<Route path="/llm-servers" element={<LlmServersPage />} />` (users route kept).

**`frontend/src/admin/App.tsx`** — amended: added `NavLink` import and a minimal `<Group gap="md">` nav (`Users` → `/`, `LLM Servers` → `/llm-servers`) inside the existing header Group. Token gate + minimal layout kept firing first; no shared sidebar/shell framework introduced.

**Note (DoD-5 divergence, sanctioned):** the step's DoD-5 says the backend-type option list lives in `types/llmServers.d.ts`, but a `.d.ts` cannot export a runtime array. Per the `ROLE_OPTIONS`-in-`api/admin.ts` precedent, `BACKEND_OPTIONS` (+ its `BackendOption` interface) is placed in `api/llmServers.ts`. The `.d.ts` keeps only the `LlmBackendType` union.

- Typecheck: `cd frontend && npx tsc --noEmit` → clean.
- Caller-compile edits (out of Source-files scope): None.

### Step 006 — frozen interface (2026-07-23)

All seven files under `frontend/src/admin/`. Draft classes: observable fields + pure
`get` computeds are REAL structure; the async external effect fns throw
`new Error("not implemented")` (coder fills). Modal components render the wired
`observer` shell (props bound, draft seeded, probe-on-open effects present); the
coder fills the effect-fn bodies. `npx tsc --noEmit` → clean (no `any`).

**`components/llm-servers/serverFormDraft.ts`** — new module:
- `export class ServerFormDraft` — fields `name: string`, `backendType: LlmBackendType` (default `"openai"`), `baseUrl: string`, `apiKey: string`, `isActive: boolean` (default `true`), `serverErrors: Record<string, string>`, `submitStatus: "idle" | "loading" | "ready" | "error"`; `constructor(server: LlmServer | null)` (non-null seeds name/backend_type/base_url/is_active; `apiKey` stays `""`, never seeded); `get clientErrors(): Record<string, string>`; `get errors(): Record<string, string>`; `get canSubmit(): boolean`. `makeAutoObservable(this)` in ctor; no effectful methods.
- `export async function submitServerForm(draft: ServerFormDraft, serverId: number | null, onSaved: () => void, signal?: AbortSignal): Promise<void>` — body throws.

**`components/llm-servers/ServerFormModal.tsx`** — new module:
- `export const ServerFormModal` — `observer`, props `{ opened: boolean; server: LlmServer | null; onClose: () => void; onSaved: () => void; onSelectModels: (server: LlmServer) => void; }`. `useState(() => new ServerFormDraft(server))`. Fields: TextInput name/base_url, `<Select data={BACKEND_OPTIONS}>` backend_type, `<PasswordInput>` api_key, `<Switch>` is_active; edit-mode-only "Select Models" button (`onClose()` then `onSelectModels(server)`); Save → `submitServerForm`, `onClose` on `submitStatus === "ready"`.

**`components/llm-servers/modelsModalDraft.ts`** — new module:
- `export class ModelsModalDraft` — fields `available: string[]` (default `[]`), `selected: Set<string>`, `filter: string`, `probeStatus`/`saveStatus` (`"idle" | "loading" | "ready" | "error"`), `probeError: string | null`, `saveError: string | null`; `constructor(initialEnabled: string[])` seeds `selected = new Set(initialEnabled)`; `get canSubmit(): boolean`. `makeAutoObservable(this)` in ctor.
- `export async function probeModelsAction(draft: ModelsModalDraft, serverId: number, signal?: AbortSignal): Promise<void>` — body throws.
- `export async function submitEnabledModels(draft: ModelsModalDraft, serverId: number, onSaved: () => void, signal?: AbortSignal): Promise<void>` — body throws.

**`components/llm-servers/ModelsModal.tsx`** — new module:
- `export const ModelsModal` — `observer`, props `{ opened: boolean; server: LlmServer; onClose: () => void; onSaved: () => void; }`. `useState(() => new ModelsModalDraft(server.enabled_models))`. Probe-on-open `useEffect` (deps `[draft, server.id]`, aborts on cleanup). Renders `Array.from(new Set([...draft.available, ...server.enabled_models])).sort()` as `<Checkbox>` rows (reassign fresh `Set` on toggle) in a `<ScrollArea.Autosize>`; Save → `submitEnabledModels`, `onClose` on `saveStatus === "ready"`.

**`components/llm-servers/embeddingModalDraft.ts`** — new module:
- `export class EmbeddingModalDraft` — fields `available: string[]` (default `[]`), `selected: string | null`, `filter: string`, `probeStatus`/`saveStatus`, `probeError: string | null`, `saveError: string | null`; `constructor(initialModel: string | null)` seeds `selected`; `get canSubmit(): boolean` (`selected !== null && saveStatus !== "loading"`). `makeAutoObservable(this)` in ctor.
- `export async function probeModelsAction(draft: EmbeddingModalDraft, serverId: number, signal?: AbortSignal): Promise<void>` — body throws.
- `export async function submitEmbedding(draft: EmbeddingModalDraft, serverId: number, onSaved: () => void, signal?: AbortSignal): Promise<void>` — body throws.

**`components/llm-servers/EmbeddingModal.tsx`** — new module:
- `export const EmbeddingModal` — `observer`, props `{ opened: boolean; server: LlmServer; onClose: () => void; onSaved: () => void; }`. `useState(() => new EmbeddingModalDraft(server.embedding_model))`. Probe-on-open `useEffect`. Renders `available ∪ current-model` (`.sort()`) as a single-select `<Radio.Group value={draft.selected ?? ""}>` of `<Radio>` rows; Submit → `submitEmbedding`, `onClose` on `saveStatus === "ready"`.

**`pages/LlmServersPage.tsx`** — amended (step-005 structure/handlers preserved):
- Added component-local `useState`: `formTarget: LlmServer | null | undefined` (undefined=closed, null=create, server=edit), `modelsTarget: LlmServer | null`, `embeddingTarget: LlmServer | null`.
- Header "Add server" → `setFormTarget(null)` (was wired to `refresh`).
- Per-row Menu items added: Edit → `setFormTarget(server)`, Select Models → `setModelsTarget(server)`, Set Embedding → `setEmbeddingTarget(server)` (Clear-Embedding + Delete kept).
- Mounted the three modals conditionally at the bottom: `ServerFormModal` (`formTarget !== undefined`, `onClose` resets to undefined, `onSelectModels` sets `modelsTarget`), `ModelsModal`/`EmbeddingModal` (truthy-target), all `onSaved={refresh}`.
- Imports added: `LlmServer` type; the three modal components; `IconEdit`/`IconListCheck`/`IconStar`.

- Typecheck: `cd frontend && npx tsc --noEmit` → clean.
- Caller-compile edits (out of Source-files scope): None.

## Tests

### Step 001 — tests (2026-07-23)

- `backend/tests/db/test_llm_servers.py`
  - `test_create_round_trips_every_field_and_appears_in_get_all__DoD1` — covers DoD-1 (US-010.AC-1) — create with all fields set round-trips through get_by_id and appears in get_all.
  - `test_delete_removes_row_and_reports_match__DoD2` — covers DoD-2 (US-013.AC-2) — delete(id) removes the row (get_by_id → None) and returns True.
  - `test_delete_nonmatching_id_returns_false__DoD2` — covers DoD-2 (US-013.AC-2) — delete on a non-matching id returns False.
  - `test_embedding_flag_lifecycle__DoD3` — covers DoD-3 (D5) — get_embedding_server returns None/single flagged row; clear_all_embedding clears is_embedding on every row.
  - `test_get_all_ordered_by_name__DoD4` — covers DoD-4 (D1/D5) — get_all returns rows ordered by name.
  - `test_get_active_excludes_inactive_and_is_name_ordered__DoD4` — covers DoD-4 (D1/D5) — get_active returns only is_active rows, name-ordered, excluding inactive.
- `backend/tests/services/test_db_import_export_llm_servers.py`
  - `test_llm_server_codec_round_trips_all_fields__DoD5` — covers DoD-5 (D6) — codec round-trips all fields.
  - `test_enabled_models_kept_as_json_string__DoD5` — covers DoD-5 (D6) — enabled_models kept as its JSON string, not decoded.
  - `test_api_key_exported_verbatim_not_masked__DoD5` — covers DoD-5 (D6) — api_key exported verbatim (not masked).
  - `test_table_registry_has_llm_servers_after_users__DoD5` — covers DoD-5 (D6) — TABLE_REGISTRY has an "llm_servers"/LlmServer tuple positioned after the users entry.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓

### Step 002 — tests (2026-07-23)

- `backend/tests/services/test_secrets.py` — covers DoD-8 (US-021.AC-1) — the shared `$ENV` resolver
  - `test_resolve_none_returns_none__DoD8_US021_AC1` — None → None.
  - `test_resolve_env_ref_returns_environ_value__DoD8_US021_AC1` — `"$FOO"` → `os.environ["FOO"]` (monkeypatch-set).
  - `test_resolve_literal_returns_verbatim__DoD8_US021_AC1` — a literal (incl. `""`) returned verbatim.
  - `test_resolve_unset_env_ref_raises_env_not_set__DoD8_US021_AC1` — `"$FOO"` with FOO unset raises `LlmServerError(env_not_set)`.
- `backend/tests/services/test_llm_servers.py` — covers DoD-1,2,3,4,5,6,7,9,10 — CRUD / enable / embedding / masking
  - `test_create_server_persists_and_reflects_fields__DoD1_US010_AC1` — covers DoD-1 — create persists + response reflects supplied fields (has_api_key True, id int).
  - `test_create_server_invalid_backend_type_rejected__DoD2_US010_AC2` — covers DoD-2 — invalid backend_type → `invalid_backend_type`, no row created.
  - `test_create_server_empty_required_field_rejected__DoD3_US010_AC3` — covers DoD-3 — empty name/backend_type/base_url each → `missing_field`.
  - `test_update_server_applies_fields_and_keeps_key_when_omitted__DoD4_US013_AC1` — covers DoD-4 — provided fields applied; omitted api_key leaves stored key unchanged.
  - `test_update_server_empty_api_key_clears_it__DoD4_US013_AC1` — covers DoD-4 — `api_key == ""` clears key (has_api_key False, stored None).
  - `test_set_enabled_models_persists_decoded_list__DoD5_US012_AC1` — covers DoD-5 — subset persisted; response/refetch expose decoded `list[str]`.
  - `test_set_embedding_server_records_and_reports__DoD6_US014_AC1` — covers DoD-6 — designation sets is_embedding+model; get_embedding_config reports server+model.
  - `test_set_embedding_server_replaces_prior__DoD7_US014_AC2` — covers DoD-7 — designating B clears A (exactly one flagged).
  - `test_to_response_masks_api_key__DoD9_US021_AC2` — covers DoD-9 — response has no api_key field; has_api_key = (api_key is not None and != "").
  - `test_update_server_not_found__DoD10_D7`, `test_delete_server_not_found__DoD10_D7`, `test_set_enabled_models_not_found__DoD10_D7`, `test_set_embedding_server_not_found__DoD10_D7` — cover DoD-10 — each on a non-existent id → `not_found`.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓, DoD-10 ✓

### Step 003 — tests (2026-07-23)

- `backend/tests/services/test_llm_servers_probe.py` — probe / test-connection; `_create_client` monkeypatched as the seam (real `llm` library never touched); server rows seeded via `db.llm_servers.create`
  - `test_probe_returns_sorted_models_and_leaves_record_unchanged__DoD1_US011_AC1` — covers DoD-1 (US-011.AC-1) — fake `list_models()` yields a known unsorted list → probe returns it sorted; re-fetch confirms enabled_models/is_embedding + other fields untouched.
  - `test_probe_construction_client_error_is_probe_failed__DoD2_US011_AC2` — covers DoD-2 (US-011.AC-2) — `_create_client` raising `aiohttp.ClientError` → `LlmServerError(probe_failed)`, no list returned.
  - `test_probe_list_models_client_error_is_probe_failed__DoD2_US011_AC2` — covers DoD-2 (US-011.AC-2) — fake `list_models()` raising `aiohttp.ClientError` → `LlmServerError(probe_failed)`.
  - `test_probe_llm_error_is_probe_failed__DoD3_D8` — covers DoD-3 (D8) — `list_models()` raising `llm.LLMError` → `probe_failed`.
  - `test_probe_value_error_is_probe_failed__DoD3_D8` — covers DoD-3 (D8) — `_create_client` raising `ValueError` (keyless OpenAI) → `probe_failed`.
  - `test_probe_resolves_env_key_at_use_time__DoD4_US021_AC1` — covers DoD-4 (US-021.AC-1) — env set: fake factory captures `resolved_key`; asserts it equals the resolved `os.environ` secret.
  - `test_probe_unset_env_key_raises_env_not_set_before_client__DoD4_US021_AC1` — covers DoD-4 (US-021.AC-1) — env unset: raises `env_not_set` and the fake `_create_client` call-counter stays 0 (no client constructed).
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓

### Step 004 — tests (2026-07-23)

- `backend/tests/routes/admin/test_llm_servers.py` — end-to-end admin HTTP surface for the nine `/api/admin/llm-servers` endpoints; in-process via the `http_client` fixture; users seeded with the local `_seed_user`/`_seed_admin` helpers; servers created through the real `POST` route; probe endpoint tests monkeypatch the `app.services.llm_servers._create_client` seam (real `llm` library never touched).
  - `test_list_author_403_admin_200__DoD1_D7` — covers DoD-1 (D7 gating) — GET "" author-token → 403, admin-token → 200.
  - `test_create_201_then_listed__DoD2_US010_AC1` — covers DoD-2 (US-010.AC-1) — POST valid server → 201, then appears in GET "".
  - `test_create_invalid_backend_type_400__DoD3_US010_AC2` — covers DoD-3 (US-010.AC-2) — backend_type "anthropic" → 400.
  - `test_create_empty_required_field_400__DoD4_US010_AC3` — covers DoD-4 (US-010.AC-3) — empty name → 400.
  - `test_update_reflects_new_values__DoD5_US013_AC1` — covers DoD-5 (US-013.AC-1) — PUT "/{id}" updates fields; GET "" reflects them.
  - `test_delete_204_and_gone_then_nonexistent_404__DoD6_US013_AC2` — covers DoD-6 (US-013.AC-2) — DELETE "/{id}" → 204 and gone; DELETE nonexistent → 404.
  - `test_set_enabled_models_persists__DoD7_US012_AC1` — covers DoD-7 (US-012.AC-1) — PUT "/{id}/enabled-models" persists the list; GET "" shows it.
  - `test_available_models_200_sorted__DoD8_US011_AC1` — covers DoD-8 (US-011.AC-1) — fake `_create_client` → 200 and AvailableModelsResponse.models is the fake's list SORTED.
  - `test_available_models_probe_failure_502__DoD9_US011_AC2` — covers DoD-9 (US-011.AC-2) — fake raising `aiohttp.ClientError` → 502, no model list.
  - `test_embedding_designate_replace_clear__DoD10_US014_AC1_AC2` — covers DoD-10 (US-014.AC-1/AC-2, D5) — designate A (GET /embedding reflects), designate B replaces A, DELETE /embedding clears to all-None.
  - `test_no_api_key_in_responses_has_api_key_present__DoD11_US021_AC2` — covers DoD-11 (US-021.AC-2) — no POST/GET "" body has `api_key`; each carries `has_api_key`.
  - `test_mutations_nonexistent_server_404__DoD12_D7` — covers DoD-12 (D7 not-found) — PUT/DELETE/enabled-models/embedding on a non-existent id → 404.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓, DoD-10 ✓, DoD-11 ✓, DoD-12 ✓

## Notes & Issues

_populated by the coder when worth saying_
