# Feature 004 — authentication-session (feature-wide context)

## Goal & scope

Let a configured-instance user **log in** with username/password, **hold a
session**, and **log out**; expired or invalidated sessions force
re-authentication. Cross-layer:

- **Backend** — the auth service (token mint/verify, login orchestration,
  rate-limiting), the FastAPI **auth dependency** guarding protected routes, and
  the HTTP surface (`login`, `refresh`, `me`).
- **Frontend** — the Login-page **login form** → tokens, dual-token storage,
  a **silent-refresh** interceptor, and the **protected-route gates** the 002
  scaffold deferred.

Delivers **FEAT-002** — `UC-003`/`US-003` (log in) and `UC-004`/`US-004`
(log out / session expiry). Read
`docs/product/use-cases/FEAT-002.authentication-session.md` and
`docs/product/stories/FEAT-002.authentication-session.md`; every `[test]` DoD
item cites the `US-###.AC-#` it verifies.

The settled boundary is `brief.md` (Definition + Scope In/Out). **Out of scope
(do not widen):** user creation, roles management, and password reset — all
feature 005. The `require_role` admin-role gate is **deferred to feature 005**
(its first real consumer, with real ACs), so the roles ladder / admin gate is
005's to build — 004 ships only `get_current_user`.

## Architecture sources (read these)

- `docs/architecture/backend.md` — the enforced 4-layer rules
  (`routes/` HTTP-only; `services/` no `session`/`AsyncSession`/`select()`/
  `session.exec()`/`session.add()`; `db/` session-free, ORM never leaks;
  `models/` tables + schemas), typed discipline, bcrypt, per-user HS256 signing
  key, ~30-day key rotation on login, and the pytest/httpx in-process harness.
- `docs/architecture/frontend.md` — MobX hard rules; the **login entry
  exemption** (standalone entry, no React Router / no `<Page>State`, but
  `observer` on every component, no Mantine `useForm`, effectful ops are
  external `(state, args, signal)` fns, `window.location` nav allowed); the
  **`api/` layer** (`client.ts` `request<T>` + `ApiError` + Bearer from
  `auth.ts`; **no `fetch` outside `client.ts`/`sse.ts`**).
- Root `CLAUDE.md` — backend tests `cd backend && .venv/Scripts/python -m
  pytest`; **no frontend test runner** (all frontend DoD items are
  `[manual/live]`).

## Architecture OVERRIDES (approved user decisions this session — do NOT edit the docs)

Two authoritative docs are deliberately out of sync with this plan. **Do not
edit `docs/architecture/*` (architect's domain)** — the reconciliation is
recorded in `outcome.md` for a post-implementation `/architect` pass. These are
conscious, approved overrides, not drift:

1. `backend.md` documents a single **stateless 30-day JWT, no refresh**. This
   plan uses **short access token + refresh token** instead (see Token model).
2. `frontend.md`'s `client.ts` gains a **silent-refresh-on-401 interceptor** and
   `auth.ts` moves from single-token to **dual-token** storage — both new here.

## Token model (access + refresh, per-user-key JWT, stateless) — used by steps 001, 002, 003

- **Access token** — HS256, signed with the user's `jwt_signing_key`; payload
  `{user_id, username, role, type:"access", exp:+30min}`.
- **Refresh token** — HS256, signed with the **same** per-user key; payload
  `{user_id, type:"refresh", exp:+30days}`.
- `get_current_user` requires `type=="access"`; the refresh path requires
  `type=="refresh"`. A refresh token must never authenticate as an access
  token, and vice-versa.
- **Refresh** verifies the refresh token (sig + exp + `type=="refresh"`), checks
  the user is enabled, rotates the signing key **if stale (>30d)**, and issues a
  **new access token**. The refresh token itself is **not** rotated (rotating-
  refresh noted as future enhancement in `outcome.md`).
- Because both tokens are signed with the per-user key, **any key rotation (on
  login or on stale refresh) invalidates BOTH tokens** → forces re-login. This
  preserves the ~30-day session cap and realizes UC-003's alt flow.
- **`/api/auth/refresh` returns `TokenResponse`** with the new `access_token`
  and the incoming `refresh_token` **echoed** (after a stale-refresh rotation
  that echoed refresh token is already dead — intended: the client re-logs-in
  when its access next expires). This avoids adding a fourth schema.

## Session invalidation (logout & expiry) — decisions

- **Logout = client-drop + per-request checks** (no server logout endpoint,
  decision 2). Logout clears both tokens client-side and redirects to
  `/login/`. Server-side invalidation is via (a) the per-request enabled-check
  in `get_current_user` (a user with `pwdhash is None` → 401), and (b) key
  rotation. **Accepted caveat** (recorded in `outcome.md`): a copied refresh
  token stays valid until it expires or the key rotates.
- **Expiry** — an expired access token → `get_current_user` 401 (`US-004.AC-2`);
  an expired refresh token → refresh refused → re-login.

## Rate-limiting (decision 3) — used by step 002 (service) and step 003 (route)

- **5 failed attempts / 15-minute lockout, per username, in-memory** (resolves
  `US-003.AC-3`'s `_TBD`). On the 5th failure within the window, further
  attempts are refused for 15 minutes **regardless of credential validity**.
- The counter **clears on a successful login** (and naturally on window expiry).
- The refusal is the **same generic** `AuthError` → **401** as bad creds — no
  user enumeration, no lockout-specific message (invalid creds / unknown user /
  disabled / rate-limited all return the identical refusal).
- **Accepted caveats** (recorded in `outcome.md`, flagged for later hardening):
  per-username not per-IP, in-memory / per-worker, not persisted. The resolved
  `5/15min` threshold is back-propagated to `docs/product/` via `/product-spec`.

## Roles (decision 5)

- `UserRole = {admin, author}` (delivered by feature 003 — no editor/player).
- The `require_role` admin gate and its ladder (**author < admin** →
  `{author:0, admin:1}`) are **deferred to feature 005**; 004 does not build
  them. 004's only guard is `get_current_user` (authenticated-any-role).

## Layering discipline (decision 4 — override the reference)

The reference puts rate-limit state, `verify_password`, rotation, and
`users.update` **in the route**. BookWriter forbids that. **All** auth business
logic lives in the **service** layer (`services/auth.py`, `services/rate_limit.py`);
each route parses the request, calls a service function, maps a typed
`AuthError` to the HTTP status, and returns the response. This applies uniformly
to `login`, `refresh`, and `me`.

## Substrate — delivered surfaces this feature builds on / amends

Feature **003.first-run-bootstrap** (dependency) and **002.frontend-scaffold**
are the substrate. Several files here are **edited**, not created — expected
cross-feature amendment, **not** scope drift; per-step context files flag each.

Backend, delivered by 003 (treat as given):

- `app/models/user.py` — `UserRole {admin, author}`; `User` table: autoincrement
  int `id`; unique indexed `username`; **nullable** `pwdhash` (**null == account
  disabled** — no separate `disabled` flag); `role`; **nullable**
  `jwt_signing_key`; nullable `last_login` and `last_key_update`. No `salt`.
- `app/db/users.py` — session-free: `create`, `get_by_username`, `get_by_id`,
  `admin_exists`. **No `update` yet — step 002 adds it.**
- `app/services/auth.py` — `hash_password`, `verify_password`,
  `generate_signing_key` (`secrets.token_hex(32)`), and the **minimal**
  `create_token(user)` (single ~30-day JWT). **004 splits `create_token` into
  `create_access_token` / `create_refresh_token` and adds verification,
  rotation, the auth dependency, and login/refresh orchestration.**
- `app/routes/auth.py` — `APIRouter(prefix="/api/auth")` with `GET /status`,
  `POST /setup/create` (returns `LoginResponse{token}`), `POST /setup/import`.
  **004 adds `login`/`refresh`/`me` and re-points `setup/create` to
  `TokenResponse`.**
- `app/models/schemas/auth.py` — `AuthStatusResponse{needs_setup}`,
  `CreateDBRequest{admin_username, password, password_confirm}`,
  `LoginResponse{token}`. **004 retires `LoginResponse`, adds `TokenResponse`,
  `RefreshRequest`, `MeResponse`.**
- Test harness (001): `pytest`/`pytest-asyncio` `asyncio_mode="auto"`;
  in-process `httpx.AsyncClient` over `ASGITransport`; `tests/conftest.py`
  provides a temp-SQLite `DbConfig` fixture and an `http_client` fixture; the
  process-global `db_ready` flag is reset between tests.

Frontend, delivered by 002/003 (treat as given):

- `src/api/client.ts` (002) — `request<T>(url, {method?, body?, signal?})`;
  injects `Authorization: Bearer <getToken()>` only when a token is present;
  `204` → `undefined`; `ApiError(status, message, details?)`; `throwApiError`;
  `authHeaders()`. **004 adds the silent-refresh-on-401 interceptor.**
- `src/auth.ts` (002/003) — `getToken()` (reads `localStorage["token"]`),
  `setToken()`, `logout()` stub. No import from `src/api/` (one-way
  `api/` → `auth.ts` holds). **004 moves to dual-token storage + `getCurrentUser`
  + real `logout`.**
- `src/api/auth.ts` (003) — `getAuthStatus`, `setupCreate` (returns `{token}`),
  `setupImport`. **004 re-points `setupCreate` to `TokenResponse` and adds
  `login`/`refresh`.**
- `src/types/auth.d.ts` (003) — status shape, create-DB request shape,
  login-response `{token}`. **004 replaces the login shape with `TokenResponse`
  and adds `MeResponse`/`RefreshRequest`.**
- `login/Login.tsx` + `login/loginState.ts` (003) — the first-run wizard +
  a "proceed to login" placeholder when `needs_setup===false`. **004 replaces
  that placeholder with the real login form and updates create-token storage to
  the pair.**
- `src/user/App.tsx` + `src/admin/App.tsx` (002) — placeholders with **no**
  token gate. **004 adds the mount-time token-gate redirect.**
- The login entry is **outside React Router**; nav via `window.location.href`
  (sanctioned by `frontend.md`).

## Cross-cutting reference

`D:/GitRoot/_TextGens/LLMRPTextOnlyProject` implements the same capability with
the same stack — **adapt, don't copy**. Decisions 1–6 override several reference
choices: access+refresh (not single token), service-layer login/rate-limit
orchestration (not in-route), 5/15min store (not 4/60s), admin/author roles (not
admin/editor/player), and an `observer`+component-state login form (not plain
`useState`). Per-step context files cite reference file paths; the harvested
facts are the briefing's harvest report.

## Files touched across the feature

```
backend/
  app/
    services/auth.py                 (001 amend: token split + verify + dependency;
                                       002 amend: authenticate_user + refresh_access_token)
    services/rate_limit.py           (002 create)
    db/users.py                      (002 amend: add update)
    routes/auth.py                   (003 amend: login/refresh/me + re-point setup/create)
    models/schemas/auth.py           (003 amend: TokenResponse/RefreshRequest/MeResponse; retire LoginResponse)
  tests/
    services/test_tokens.py          (001, test-coder — new)
    services/test_auth.py            (001, test-coder — amend: retire create_token test)
    services/test_login_auth.py      (002, test-coder — new)
    routes/test_auth.py              (003, test-coder — new)
    routes/test_setup.py             (003, test-coder — amend: setup/create → TokenResponse)
frontend/
  src/auth.ts                        (004 amend: dual-token + getCurrentUser + logout)
  src/api/auth.ts                    (004 amend: login/refresh + setupCreate→TokenResponse)
  src/api/client.ts                  (004 amend: silent-refresh interceptor)
  src/types/auth.d.ts                (004 amend: TokenResponse/RefreshRequest/MeResponse)
  login/loginState.ts                (005 amend: login form state + handleLogin + pair storage)
  login/Login.tsx                    (005 amend: real login form when configured)
  src/user/App.tsx                   (005 amend: mount token gate)
  src/admin/App.tsx                  (005 amend: mount token gate)
```

`services/auth.py` is edited by steps 001 and 002 (distinct functions); several
003/002-feature files are amended here. All are legitimate cross-step /
cross-feature edits — each is called out in the relevant step context so it is
not read as scope drift.
