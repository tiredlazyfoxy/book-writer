# Outcome — 004.authentication-session

Intended documentation changes to apply at finalization. Grouped by target.
Everything below the `## Observations` marker is the coder's.

## `docs/architecture/backend.md`

- **Section "Authentication — per-user JWT key + bcrypt".** Change: replace the
  single **stateless 30-day JWT, no refresh** scheme with **access token
  (~30 min) + refresh token (~30 days)**, both HS256 signed with the user's
  per-user `jwt_signing_key`; `type` claim (`access` / `refresh`) separates them;
  `get_current_user` requires `type=="access"`, the refresh path requires
  `type=="refresh"`. Reason: user decision this session (recorded as an approved
  override in `context.md`) — short-lived access limits token-theft exposure
  while the refresh token preserves the ~30-day session cap.
- **Same section.** Add: the **refresh endpoint** (`POST /api/auth/refresh`)
  verifies the refresh token, checks the user is enabled, rotates the signing key
  if stale (>30d), and issues a **new access token** (refresh token not rotated);
  because both tokens use the per-user key, **any key rotation invalidates both**
  → forces re-login. Reason: realizes UC-003 alt flow and the session cap.
- **Same section.** Add: **session invalidation** is (a) the per-request
  enabled-check in `get_current_user` (`pwdhash is None` → 401) and (b) key
  rotation; there is **no server logout endpoint** (logout is client token-drop).
  Note the accepted caveat: a copied refresh token stays valid until it expires
  or the key rotates. Reason: decision 2.
- **Same section / Layer separation.** Add: login orchestration, refresh
  orchestration, and **rate-limiting** live entirely in the **service** layer
  (`services/auth.py`, `services/rate_limit.py`); routes are thin (parse → call
  one service fn → map `AuthError`→401). Reason: decision 4 (the reference put
  this in the route; BookWriter forbids it).
- **Same section.** Add: **rate-limiting** = 5 failed attempts / 15-minute
  lockout, **per username, in-memory**, returning the same generic 401 as bad
  creds (no enumeration). Record the **hardening caveats** as future work:
  per-IP (not just per-username), persistence across restarts, and cross-worker
  coordination (currently per-worker in-memory). Reason: decision 3.
- **Same section.** Add the guarded-route surface: `GET /api/auth/me`
  (behind `get_current_user`, returns `{id, username, role}`). Reason: `/me` is
  the first real guarded endpoint and the server-validated identity probe. The
  `require_role` admin-role ladder is **deferred to feature 005** (its first real
  consumer) — 005 documents the ladder when it lands its first admin-only route.

## `docs/architecture/frontend.md`

- **Section "API layer → `client.ts`".** Add: a **silent-refresh-on-401
  interceptor** — on a 401 for a token-carrying request, attempt one refresh via
  the stored refresh token and retry the original request once; on refresh
  failure call `logout()`. Note the interceptor issues its refresh `fetch`
  inside `client.ts` to avoid a `client → api/auth` import cycle. Reason: user
  decision (approved override recorded in `context.md`).
- **Section "The state ladder → Module-level globals" / `auth.ts`.** Change:
  `auth.ts` holds **two** tokens (access + refresh), exposes `getToken` (access),
  `getRefreshToken`, `getCurrentUser` (client-side JWT decode for display), and a
  real `logout` (clears both + redirects to `/login/`). Reason: the access+refresh
  model.

## `docs/architecture/system-overview.md`

- **Section "Client↔server contract → Auth".** Change the auth line from a single
  JWT issued at login to **access + refresh JWTs** (per-user-key HS256), access
  in `Authorization: Bearer`, refresh exchanged at `POST /api/auth/refresh`.
  Reason: the token-model change above.

## `docs/product/` (route to `/product-spec`, do not edit here)

- **FEAT-002** — upgrade its `[inferred]` provenance to **confirmed: user**
  (2026-07-21). Basis: the user confirmed FEAT-002 by requesting this plan and
  settling its decisions. Applies to UC-003, UC-004, US-003, US-004.
- **US-003.AC-3** — resolve the `_TBD: exact rate-limit threshold` to
  **"5 failed attempts / 15-minute lockout, per username"**.

## `docs/architecture/quick-reference.md` (once it exists)

- Add endpoints `POST /api/auth/login`, `POST /api/auth/refresh`,
  `GET /api/auth/me`, and DTOs `TokenResponse{access_token, refresh_token}`,
  `RefreshRequest{refresh_token}`, `MeResponse{id, username, role}`; note the
  retirement of `LoginResponse{token}` in favor of `TokenResponse` (also on
  `POST /api/auth/setup/create`).

## Future-work caveats (record; not blockers)

- Rate-limiter hardening: per-IP dimension, persistence across restarts,
  cross-worker coordination (currently in-memory / per-worker).
- Copied-refresh-token: stays valid until it expires or the key rotates (accepted
  consequence of client-drop logout).
- Rotating-refresh: refresh tokens are currently long-lived and not rotated on
  use — a possible future enhancement.

## Observations
