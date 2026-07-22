# Quick Reference

Dense, agent-first index of concrete endpoints, DTOs, and patterns as they land. Append here as the system grows; this file is intentionally terse and is the one file exempt from the folder's ~400-line limit. For the reasoning behind each shape, follow the pointers into `backend.md` / `system-overview.md`.

## Endpoints

| Method | Path | Success | Body | Flow |
|--------|------|---------|------|------|
| `GET` | `/api/health` | `200` | `{"status":"ok","db":"ready"}` | `routes/health.py` → `services/health.py check_health()` → `db/health.py ping()` → `HealthResponse` |
| `GET` | `/api/auth/status` | `200` | — | `AuthStatusResponse{needs_setup}` — `needs_setup = not is_db_ready()` (admin existence) |
| `POST` | `/api/auth/setup/create` | `200` | `CreateDBRequest{admin_username, password, password_confirm}` | `LoginResponse{token}` — creates schema + first admin, auto sign-in |
| `POST` | `/api/auth/setup/import` | `200` | multipart, field `file` | `AuthStatusResponse` — restores archive, **no token** |

- `/api/health` — the first concrete endpoint and the canonical four-layer example. Readiness originates from `db.health.ping()` (a `SELECT 1`-style probe), **not** a route-level constant. When the DB is not ready the service maps it to `{"status":"error","db":"unavailable"}`. Passes on a cold instance (zero tables) — `SELECT 1` still succeeds.
- `/api/auth/setup/*` (feature 003) — the front door of a cold instance; schema creation is deferred to these flows. See `backend.md` startup lifecycle.

## DTOs

| DTO | Module | Shape |
|-----|--------|-------|
| `HealthResponse` | `app/models/schemas/health.py` | Pydantic `BaseModel`: `status: str`, `db: str` |
| `AuthStatusResponse` | `app/models/schemas/` (auth) | Pydantic `BaseModel`: `needs_setup: bool` |
| `CreateDBRequest` | `app/models/schemas/` (auth) | Pydantic `BaseModel`: `admin_username: str`, `password: str`, `password_confirm: str` |
| `LoginResponse` | `app/models/schemas/` (auth) | Pydantic `BaseModel`: `token: str` |

## Tables & enums

| Name | Module | Shape |
|------|--------|-------|
| `User` | `app/models/` (`db/users.py`) | SQLModel table — **first persistent entity**. `id` (app-generated snowflake, string in JSON — **migrated**, `fast/001`; only the `user_id` token claim still int, deferred to feature 004), `username` (unique, indexed), `pwdhash` (nullable bcrypt; **null == disabled**, no `disabled` bool), `role: UserRole`, `jwt_signing_key` (nullable), `last_login`, `last_key_update`. No `salt` column. See `backend.md` → Domain models. |
| `UserRole` | `app/models/` | enum — `admin` \| `author` |

## Conventions

- **Entity ids = Snowflake 64-bit ints** — 41-bit ms timestamp (fixed epoch) / 10-bit node id (`BOOKWRITER_NODE_ID`, default 0) / 12-bit sequence; app-generated via `app/ids.py` `generate_id()`. **Serialized as strings** in JSON/JSONL/DTOs (they exceed JS 2^53; a number loses precision); `from_dict` also accepts a legacy JSON number. Frontend `.d.ts` types ids as `string`. See `backend.md` → Conventions — entity ID strategy.

## Frontend `src/api/` pattern

- `client.ts` — `request<T>(url, opts?)`: Bearer auth from `auth.ts` `getToken()`, `Content-Type: application/json`, JSON-stringified body, `AbortSignal` pass-through, `204 → undefined`, non-2xx normalized to `ApiError(status, message, details?)` via `throwApiError` (reads `{ detail }`). Also exports `authHeaders()`.
- `sse.ts` — `streamPost(url, body, handlers): AbortController`: hand-rolled fetch-POST SSE reader (NOT `EventSource`).
- Resource modules `api/<resource>.ts` namespace-import and call `request<T>`. Example: `api/health.ts` `getHealth(signal?)` → `request<HealthResponse>("/api/health", { signal })`.

## Frontend MobX page-state — reference example

`src/user/pages/HealthPage.tsx` + `healthPageState.ts` is the canonical page-state convention example; mirror it for new page work:

- async-resource **trio**: `health` / `healthStatus` / `healthError`
- external effectful `loadHealth(state, signal)` using `runInAction`
- `observer` on the component
- stable instance via `useState(() => new HealthPageState())`
- mount `useEffect([])` — loads on mount, aborts on unmount

Full rules live in `frontend.md`.
