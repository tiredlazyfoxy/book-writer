# Quick Reference

Dense, agent-first index of concrete endpoints, DTOs, and patterns as they land. Append here as the system grows; this file is intentionally terse and is the one file exempt from the folder's ~400-line limit. For the reasoning behind each shape, follow the pointers into `backend.md` / `system-overview.md`.

## Endpoints

| Method | Path | Success | Body | Flow |
|--------|------|---------|------|------|
| `GET` | `/api/health` | `200` | `{"status":"ok","db":"ready"}` | `routes/health.py` → `services/health.py check_health()` → `db/health.py ping()` → `HealthResponse` |

- `/api/health` — the first concrete endpoint and the canonical four-layer example. Readiness originates from `db.health.ping()` (a `SELECT 1`-style probe), **not** a route-level constant. When the DB is not ready the service maps it to `{"status":"error","db":"unavailable"}`.

## DTOs

| DTO | Module | Shape |
|-----|--------|-------|
| `HealthResponse` | `app/models/schemas/health.py` | Pydantic `BaseModel`: `status: str`, `db: str` |

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
