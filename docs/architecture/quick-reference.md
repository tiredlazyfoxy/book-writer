# Quick Reference

Dense, agent-first index of concrete endpoints, DTOs, and patterns as they land. Append here as the system grows; this file is intentionally terse and is the one file exempt from the folder's ~400-line limit. For the reasoning behind each shape, follow the pointers into `backend.md` / `system-overview.md`.

## Endpoints

| Method | Path | Success | Body | Flow |
|--------|------|---------|------|------|
| `GET` | `/api/health` | `200` | `{"status":"ok","db":"ready"}` | `routes/health.py` → `services/health.py check_health()` → `db/health.py ping()` → `HealthResponse` |
| `GET` | `/api/auth/status` | `200` | — | `AuthStatusResponse{needs_setup}` — `needs_setup = not is_db_ready()` (admin existence) |
| `POST` | `/api/auth/setup/create` | `200` | `CreateDBRequest{admin_username, password, password_confirm}` | `LoginResponse{token}` — creates schema + first admin, auto sign-in |
| `POST` | `/api/auth/setup/import` | `200` | multipart, field `file` | `AuthStatusResponse` — restores archive, **no token** |

### `/api/admin/llm-servers` (feature 006) — all `Depends(require_role(admin))`

| Method | Path | Success | Body → Response | Notes |
|--------|------|---------|-----------------|-------|
| `GET` | `/api/admin/llm-servers` | `200` | — → `LlmServersListResponse` | list |
| `POST` | `/api/admin/llm-servers` | `201` | `CreateLlmServerRequest` → `LlmServerResponse` | missing-field / invalid-backend-type → 400 |
| `GET` | `/api/admin/llm-servers/embedding` | `200` | — → `EmbeddingConfigResponse` | all-`null` when none designated; static route, declared before `/{server_id}` |
| `DELETE` | `/api/admin/llm-servers/embedding` | `204` | — | clears the embedding designation |
| `PUT` | `/api/admin/llm-servers/{server_id}` | `200` | `UpdateLlmServerRequest` → `LlmServerResponse` | not-found → 404; empty `api_key` clears, omitted keeps |
| `DELETE` | `/api/admin/llm-servers/{server_id}` | `204` | — | not-found → 404 (first DELETE pattern) |
| `GET` | `/api/admin/llm-servers/{server_id}/available-models` | `200` | — → `AvailableModelsResponse` | live probe; unreachable/auth/keyless → **502**; sorted models |
| `PUT` | `/api/admin/llm-servers/{server_id}/enabled-models` | `200` | `EnabledModelsRequest` → `LlmServerResponse` | not-found → 404 |
| `PUT` | `/api/admin/llm-servers/{server_id}/embedding` | `204` | `SetEmbeddingRequest` | clear-all-then-set; env-not-set → 400, not-found → 404 |

- Non-admin caller on any of the nine → **403**. `server_id` path params are `int` (FastAPI coerces the stringified id). See `backend/features.md` → LLM server connections.

### `/api/admin/db` (feature 007) — all `Depends(require_role(admin))`

| Method | Path | Success | Body → Response | Notes |
|--------|------|---------|-----------------|-------|
| `GET` | `/api/admin/db/report` | `200` | — → `ConsistencyReport` | per-table ok/drift/missing |
| `GET` | `/api/admin/db/export` | `200` | — → zip download | `Content-Disposition: attachment`, `application/zip`; first non-JSON admin response |
| `POST` | `/api/admin/db/import` | `204` | multipart, field `file` | pre-validated; `invalid-archive` → 400, DB unmutated; does NOT flip `set_db_ready` |
| `POST` | `/api/admin/db/vector/rebuild` | `200` | — → `VectorRebuildResponse` | `no-embedding-provider` → 400; empty registry → 0 rows |
| `POST` | `/api/admin/db/tables/{name}/create` | `204` | — | `not-in-metadata` / `table-not-missing` → 400 |
| `POST` | `/api/admin/db/tables/{name}/sync` | `204` | — | `unknown-table` → 404 (ALTER ADD/DROP COLUMN) |

- Static routes (`/report`, `/export`, `/import`, `/vector/rebuild`) declared **before** `/tables/{name}/...`; non-admin caller → **403**. See `backend/features.md` → Database consistency & management.

- `/api/health` — the first concrete endpoint and the canonical four-layer example. Readiness originates from `db.health.ping()` (a `SELECT 1`-style probe), **not** a route-level constant. When the DB is not ready the service maps it to `{"status":"error","db":"unavailable"}`. Passes on a cold instance (zero tables) — `SELECT 1` still succeeds.
- `/api/auth/setup/*` (feature 003) — the front door of a cold instance; schema creation is deferred to these flows. See `backend/persistence.md` startup lifecycle.

## DTOs

| DTO | Module | Shape |
|-----|--------|-------|
| `HealthResponse` | `app/models/schemas/health.py` | Pydantic `BaseModel`: `status: str`, `db: str` |
| `AuthStatusResponse` | `app/models/schemas/` (auth) | Pydantic `BaseModel`: `needs_setup: bool` |
| `CreateDBRequest` | `app/models/schemas/` (auth) | Pydantic `BaseModel`: `admin_username: str`, `password: str`, `password_confirm: str` |
| `LoginResponse` | `app/models/schemas/` (auth) | Pydantic `BaseModel`: `token: str` |
| `LlmServerResponse` | `app/models/schemas/llm_servers.py` | `id: str` (**string**, snowflake — not int), `name: str`, `backend_type: str`, `base_url: str`, `has_api_key: bool`, `enabled_models: list[str]`, `is_active: bool`, `is_embedding: bool`, `embedding_model: str \| None`, `created_at`, `modified_at` — **no `api_key`** |
| `CreateLlmServerRequest` | `app/models/schemas/llm_servers.py` | `name: str`, `backend_type: str`, `base_url: str`, `api_key: str \| None = None`, `is_active: bool = True` |
| `UpdateLlmServerRequest` | `app/models/schemas/llm_servers.py` | all optional: `name`, `backend_type`, `base_url`, `api_key`, `is_active` |
| `AvailableModelsResponse` | `app/models/schemas/llm_servers.py` | `models: list[str]` (sorted) |
| `EnabledModelsRequest` | `app/models/schemas/llm_servers.py` | `enabled_models: list[str]` |
| `SetEmbeddingRequest` | `app/models/schemas/llm_servers.py` | `model: str` |
| `EmbeddingConfigResponse` | `app/models/schemas/llm_servers.py` | `server_id: str \| None` (**string**, snowflake), `server_name`, `base_url`, `backend_type`, `model: str \| None`, `has_api_key: bool` — all-`None` when no embedding server |
| `LlmServersListResponse` | `app/models/schemas/llm_servers.py` | `items: list[LlmServerResponse]` |
| `ConsistencyReport` | `app/models/schemas/db_admin.py` | `tables: list[TableReportEntry]` |
| `TableReportEntry` | `app/models/schemas/db_admin.py` | `name: str`, `status: 'ok' \| 'drift' \| 'missing'`, `missing_columns: list[str]`, `extra_columns: list[str]` |
| `VectorRebuildResponse` | `app/models/schemas/db_admin.py` | `indexed_rows: int` |

## Tables & enums

| Name | Module | Shape |
|------|--------|-------|
| `User` | `app/models/` (`db/users.py`) | SQLModel table — **first persistent entity**. `id` (app-generated snowflake, string in JSON — **migrated**, `fast/001`; only the `user_id` token claim still int, deferred to feature 004), `username` (unique, indexed), `pwdhash` (nullable bcrypt; **null == disabled**, no `disabled` bool), `role: UserRole`, `jwt_signing_key` (nullable), `last_login`, `last_key_update`. No `salt` column. See `backend/features.md` → Domain models. |
| `UserRole` | `app/models/` | enum — `admin` \| `author` |
| `LlmServer` | `app/models/llm_server.py` (`db/llm_servers.py`) | SQLModel table — **second persistent entity** (feature 006). `id` (app-generated snowflake, `default_factory=generate_id`, string in JSON — **conformant**), `name`, `backend_type` (bare `str`, validated at service against `{"llama-swap","openai"}`), `base_url` (must include `/v1`), `api_key` (nullable; raw literal or `$ENV_VAR` token; never returned raw, masked as `has_api_key`), `enabled_models` (JSON-encoded `list[str]` in a TEXT column, decoded at service edge), `is_active`, `is_embedding` (≤1 row, clear-all-then-set), `embedding_model`, `created_at`, `modified_at`. See `backend/features.md` → LLM server connections. |

## Conventions

- **Entity ids = Snowflake 64-bit ints** — 41-bit ms timestamp (fixed epoch) / 10-bit node id (`BOOKWRITER_NODE_ID`, default 0) / 12-bit sequence; app-generated via `app/ids.py` `generate_id()`. **Serialized as strings** in JSON/JSONL/DTOs (they exceed JS 2^53; a number loses precision); `from_dict` also accepts a legacy JSON number. Frontend `.d.ts` types ids as `string`. See `backend/auth-ids.md` → Conventions — entity ID strategy.

## Frontend `src/api/` pattern

- `client.ts` — `request<T>(url, opts?)`: Bearer auth from `auth.ts` `getToken()`, `Content-Type: application/json`, JSON-stringified body, `AbortSignal` pass-through, `204 → undefined`, non-2xx normalized to `ApiError(status, message, details?)` via `throwApiError` (reads `{ detail }`). Also exports `authHeaders()`.
- `sse.ts` — `streamPost(url, body, handlers): AbortController`: hand-rolled fetch-POST SSE reader (NOT `EventSource`).
- Resource modules `api/<resource>.ts` namespace-import and call `request<T>`. Example: `api/health.ts` `getHealth(signal?)` → `request<HealthResponse>("/api/health", { signal })`.
- `api/db.ts` (feature 007) adds the first **blob-download** (`exportDatabase()` → `res.blob()` browser save) and **multipart-upload** (`importDatabase(file)` → `FormData` field `file`, no JSON `Content-Type`) helpers, both **bypassing `request<T>`** (JSON-only) while still reading `getToken()` Bearer — the sanctioned exception alongside `sse.ts`.

## Frontend MobX page-state — reference example

`src/user/pages/HealthPage.tsx` + `healthPageState.ts` is the canonical page-state convention example; mirror it for new page work:

- async-resource **trio**: `health` / `healthStatus` / `healthError`
- external effectful `loadHealth(state, signal)` using `runInAction`
- `observer` on the component
- stable instance via `useState(() => new HealthPageState())`
- mount `useEffect([])` — loads on mount, aborts on unmount

Full rules live in `frontend.md`.
