# Feature 004 — authentication-session

| Step | File                                          | Status  | Verifier | Date |
|------|-----------------------------------------------|---------|----------|------|
| 001  | `001.token-core-auth-dependency.md`           | done    | PASS     | 2026-07-22 |
| 002  | `002.authentication-session-service.md`       | done    | PASS     | 2026-07-22 |
| 003  | `003.auth-routes-schemas.md`                   | done    | PASS     | 2026-07-22 |
| 004  | `004.frontend-token-storage-refresh-client.md` | done    | PASS     | 2026-07-22 |
| 005  | `005.frontend-login-form-route-gates.md`       | done    | PASS     | 2026-07-22 |

## Files Changed

### Step 001 — Token core + auth dependency
- `backend/app/services/auth.py` — implemented `create_access_token`, `create_refresh_token`, `decode_token_unverified`, `verify_token_signature`, `get_current_user`, `maybe_rotate_signing_key` (bodies for the frozen stubs); added token-lifetime / rotation-window constants.

### Step 002 — Authentication & session service
- `backend/app/services/rate_limit.py` — filled the in-memory per-username failure store: module-global `_failures` dict, `_prune` helper, `is_locked` / `record_failure` / `clear` / `reset` (aware-UTC, `MAX_FAILURES=5` / `FAILURE_WINDOW=15min`).
- `backend/app/services/auth.py` — filled `authenticate_user` (rate-limit gate → load → verify → clear/rotate/last_login/persist) and `refresh_access_token` (unverified id → load → verify sig+`type=="refresh"` → rotate-if-stale/persist → new access token); all refusals raise generic `AuthError`.
- `backend/app/db/users.py` — filled `update` mirroring the `create` session pattern (`session.add`/commit/refresh, returns the user).

### Step 003 — Auth routes + schemas (HTTP surface)
- `backend/app/routes/auth.py` — filled the four stubbed handler bodies: `login` (authenticate → mint access+refresh → `TokenResponse`; `AuthError`→401), `refresh` (`refresh_access_token` → `TokenResponse` echoing incoming refresh; `AuthError`→401), `me` (`MeResponse(id=str(user.id), …)`), and `create_db` success (mint access+refresh for the created admin → `TokenResponse`). All 401s use one generic detail `"Invalid credentials"`.
- `backend/app/models/schemas/auth.py` — no change needed; skeleton already declared `LoginRequest`/`RefreshRequest`/`TokenResponse`/`MeResponse` with frozen fields and retired `LoginResponse` (confirmed).

### Step 004 — Frontend token storage + silent-refresh client
- `frontend/src/auth.ts` — filled dual-token bodies: `setTokens`/`setAccessToken` (localStorage writes), `getToken`/`getRefreshToken` (reads), `getCurrentUser` (base64url JWT-payload decode, `user_id` kept a string, guarded `JSON.parse`, returns `null` on any parse failure), and real `logout` (clears both keys + `window.location.href = "/login/"`).
- `frontend/src/api/client.ts` — filled the `silentRefreshRetry` interceptor: one direct `fetch` to `/api/auth/refresh` with `{refresh_token}` (no `api/auth` import — cycle avoidance), `setAccessToken` + single retry on success, `logout()` + surfaced `ApiError(401)` on no-refresh-token / non-2xx / throw; added a module `isRefreshing` loop-guard plus refresh-path exclusion in `request`'s 401 seam. Added `getRefreshToken`/`setAccessToken`/`logout` + `TokenResponse` imports.
- `frontend/src/types/auth.d.ts` — no change needed; skeleton already declared `TokenResponse`/`MeResponse`/`RefreshRequest`/`LoginRequest`/`UserRole` with frozen fields (confirmed).
- `frontend/src/api/auth.ts` — no change needed; skeleton already declared `login`/`refresh` and re-pointed `setupCreate` to `TokenResponse` (confirmed).
- All DoD items are `[manual/live]`; behavior (login token storage, silent refresh, refresh-failure logout, `getCurrentUser` decode) requires a live run to confirm. Gate `cd frontend && npm run build` (tsc + vite) is clean.

### Step 005 — Frontend login form + protected-route gates
- `frontend/src/login/loginState.ts` — filled the `handleLogin(state, signal?)` effect fn body (`authApi.login` → `setTokens(access, refresh)` → `window.location.href="/"`; on `ApiError` set the login trio to `error`/refusal message, no navigation; abort-guarded). `canSubmitLogin`, the login-form observable fields, and `submitCreate`'s pair storage were already in place from the skeleton — confirmed, not duplicated.
- `frontend/src/login/Login.tsx` — confirmed the `needsSetup === false` branch renders the real login form (username/password bound to `loginState`, submit gated by `canSubmitLogin`/`loginStatus`, refusal via `loginError`); updated the stale header comment that still referenced the removed 003 "proceed to login" placeholder.
- `frontend/src/user/App.tsx` — confirmed the mount-time `getToken() === null → /login/` gate is in place before routed content.
- `frontend/src/admin/App.tsx` — confirmed the same mount-time token gate is in place, kept self-contained for feature-005's later layout growth.
- All DoD items are `[manual/live]`; login authentication + token storage, refusal-without-navigation, logout redirect, and the no-token SPA redirect require a live run to confirm. Gate `cd frontend && npm run build` (tsc + vite) is clean.

## Skeleton

### Step 001 — frozen interface (2026-07-22)

`backend/app/services/auth.py`:
- `create_access_token(user: User) -> str` — new (replaces access half of removed `create_token(user: User) -> str`)
- `create_refresh_token(user: User) -> str` — new (replaces refresh half of removed `create_token`)
- `decode_token_unverified(token: str) -> int` — new. Reads `user_id` claim with signature verification off; returns it as `int`. Frozen failure contract: raises `jwt.InvalidTokenError` (unreadable token / missing claim) or `ValueError` (non-int claim string); `get_current_user` maps to 401.
- `verify_token_signature(token: str, signing_key: str) -> dict` — new. Verifies sig + expiry against the supplied per-user key; returns decoded claims. Frozen failure contract: propagates PyJWT-native `jwt.ExpiredSignatureError` (expired) vs `jwt.InvalidTokenError` / `jwt.InvalidSignatureError` (bad/rotated-key signature) — does NOT convert to HTTP; callers distinguish.
- `async get_current_user(credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme)) -> User` — new. Module-level `_bearer_scheme = HTTPBearer()`. Async FastAPI dependency; returns `User` on success, raises `HTTPException` 401 on any failure (missing/malformed token, unknown user, bad/rotated signature, expired, wrong `type`, disabled user).
- `maybe_rotate_signing_key(user: User) -> bool` — new. Mutates `user` in memory if the key is stale (>~30 days by `last_key_update`); returns whether rotation occurred. Does NOT persist (caller persists via `users.update`, added in step 002).
- Removed: `create_token(user: User) -> str` (003's single minter). Feature-003 primitives `hash_password` / `verify_password` / `generate_signing_key` left intact.
- Token payload rule (frozen): `user_id` claim serialized as `str(user.id)` in both access and refresh payloads; access payload `{user_id, username, role, type:"access", exp:+30min}`, refresh payload `{user_id, type:"refresh", exp:+30days}`.
- Caller-compile edits (out of Source-files scope): None made. Note: `backend/app/routes/auth.py:51` still calls `auth_service.create_token(admin)`; it is resolved at call time so all modules import cleanly, but the `POST /setup/create` endpoint (and any test exercising it) will fail at runtime until step 003 re-points it to `create_access_token` / `TokenResponse`. Not edited — routes are out of this step's scope (step 003's amend), per briefing.

### Step 002 — frozen interface (2026-07-22)

`backend/app/services/rate_limit.py` (NEW module — session-free, module-global in-memory store):
- `MAX_FAILURES = 5` — frozen threshold constant.
- `FAILURE_WINDOW = timedelta(minutes=15)` — frozen window constant.
- `is_locked(username: str) -> bool` — new. True iff ≥ `MAX_FAILURES` failures inside the trailing `FAILURE_WINDOW`.
- `record_failure(username: str) -> None` — new. Records one failure at "now", prunes that username's attempts older than the window.
- `clear(username: str) -> None` — new. Drops the username's failure record (called on successful login).
- `reset() -> None` — new. Clears the whole store (test-isolation seam).

`backend/app/services/auth.py` (AMEND — step-001 functions left intact):
- `class AuthError(Exception)` — new. Generic typed refusal for every login/refresh failure. **Placement: in `services/auth.py`** (not a separate errors module) — the route reaches it via `from app.services import auth as auth_service` → `auth_service.AuthError`, introducing no new import path or layer boundary. Plain `Exception` subclass, no distinguishing detail (single generic 401 mapping in step 003; no enumeration leak).
- `async authenticate_user(username: str, password: str) -> User` — new. Returns the authenticated `User`; raises `AuthError` on any refusal (locked / unknown / disabled / bad password).
- `async refresh_access_token(refresh_token: str) -> str` — new. Returns a new access token string; raises `AuthError` on any refusal (malformed / bad-or-rotated signature / expired / wrong `type` / unknown / disabled).

`backend/app/db/users.py` (AMEND):
- `async update(user: User) -> User` — new. Session-free persistence of an existing user's mutable fields (`jwt_signing_key`, `last_key_update`, `last_login`); opens/closes its own session via `get_standalone_session()`; returns the refreshed row. Mirrors the existing `create`/`get_by_id` session pattern. `id` is a stable app-generated snowflake, so this is an UPDATE of the existing row, not an insert.
- Caller-compile edits (out of Source-files scope): None. All three modules plus `app.main` import cleanly; new symbols have no existing callers.

### Step 003 — frozen interface (2026-07-22)

`backend/app/models/schemas/auth.py` (AMEND):
- `class LoginRequest(BaseModel)` — new. Fields: `username: str`, `password: str`. Body of `POST /api/auth/login`.
- `class RefreshRequest(BaseModel)` — new. Field: `refresh_token: str`. Body of `POST /api/auth/refresh`.
- `class TokenResponse(BaseModel)` — new. Fields: `access_token: str`, `refresh_token: str`. Response of `login`, `refresh`, and `setup/create`. **Replaces** the retired `LoginResponse{token: str}`.
- `class MeResponse(BaseModel)` — new. Fields: `id: str`, `username: str`, `role: UserRole`. **`id` is a STRING on the wire** (snowflake convention) even though `User.id` is an `int` in Python — the coder MUST build `MeResponse(id=str(user.id), username=user.username, role=user.role)`. `role` typed as `app.models.user.UserRole` (str-enum → serializes to its value); new import `from app.models.user import UserRole` added to the schemas module.
- Removed: `class LoginResponse(BaseModel)` (`token: str`) — 003's single-token setup result. No in-scope route references it anymore.

`backend/app/routes/auth.py` (AMEND):
- `async login(payload: LoginRequest) -> TokenResponse` — new. `@router.post("/login")`. Body stubbed `raise NotImplementedError`. Coder wiring: `authenticate_user(payload.username, payload.password)` → `create_access_token` + `create_refresh_token` → `TokenResponse`; `AuthError` → `HTTPException(401, <generic>)`.
- `async refresh(payload: RefreshRequest) -> TokenResponse` — new. `@router.post("/refresh")`. Body stubbed. Coder wiring: `refresh_access_token(payload.refresh_token)` → `TokenResponse(access_token=new, refresh_token=payload.refresh_token)` (echo incoming); `AuthError` → 401.
- `async me(user: User = Depends(auth_service.get_current_user)) -> MeResponse` — new. `@router.get("/me")`. Body stubbed. Coder builds `MeResponse(id=str(user.id), username=user.username, role=user.role)`. New import `from app.models.user import User`; `Depends` added to the fastapi import.
- `async create_db(payload: CreateDBRequest) -> TokenResponse` — **changed** (was `-> LoginResponse`). Response model re-pointed off the retired `LoginResponse`; the existing `create_database(...)` call + `SetupError`→400 mapping is preserved intact, and the terminal `return LoginResponse(token=auth_service.create_token(admin))` (which referenced the REMOVED `create_token`) is replaced with `raise NotImplementedError` (coder mints access+refresh for `admin` → `TokenResponse`). This resolves the step-001 breakage note (the dead `create_token` call site).
- Caller-compile edits (out of Source-files scope): None. `app.routes.auth`, `app.models.schemas.auth`, and `app.main` import cleanly; the auth router mounts with all 6 routes (`status`, `setup/create`, `login`, `refresh`, `me`, `setup/import`) and correct `response_model`s.
- **`LoginResponse` reference flag (out of scope — for the test-coder):** `backend/tests/routes/test_setup.py` still imports and validates `LoginResponse` (lines ~15, 49, 82, 96–97) — it is this step's test scope (`003.context.md`: test-coder amends it to assert `access_token` + `refresh_token`). Not touched here. No non-test backend module references `LoginResponse`.

### Step 004 — frozen interface (2026-07-22)

Frontend TS step; no test runner. Gate: `cd frontend && npx tsc --noEmit` — CLEAN.

`frontend/src/types/auth.d.ts` (AMEND):
- `type UserRole = "admin" | "author"` — new. Mirrors backend `UserRole` (str-enum values).
- `interface LoginRequest { username: string; password: string }` — new. Body of `POST /api/auth/login` (mirrors backend `LoginRequest`).
- `interface RefreshRequest { refresh_token: string }` — new. Body of `POST /api/auth/refresh`.
- `interface TokenResponse { access_token: string; refresh_token: string }` — new. Response of `login` / `refresh` / `setup/create`. **Replaces** retired `LoginResponse { token: string }`.
- `interface MeResponse { id: string; username: string; role: UserRole }` — new. **`id` is `string`** (snowflake serialized as string on the wire). `GET /api/auth/me`.
- `interface AuthStatusResponse` / `interface CreateDBRequest` — kept unchanged.
- Removed: `interface LoginResponse { token: string }`.

`frontend/src/auth.ts` (AMEND — dual-token; still NO import from `src/api/`; type-only import of `UserRole` from `./types/auth`):
- `const ACCESS_TOKEN_KEY = "access_token"` / `const REFRESH_TOKEN_KEY = "refresh_token"` — new exported storage keys (replace the single `"token"` key).
- `interface CurrentUser { user_id: string; username: string; role: UserRole }` — new. Decoded access-token identity for display; `user_id` kept a **string** (no `Number()`/`parseInt`).
- `setTokens(accessToken: string, refreshToken: string): void` — new pair-setter (replaces `setToken(token: string): void`).
- `setAccessToken(accessToken: string): void` — new. Access-only setter (post-refresh).
- `getToken(): string | null` — **changed body/contract** (now returns the ACCESS token from `ACCESS_TOKEN_KEY`; signature identical to 003).
- `getRefreshToken(): string | null` — new.
- `getCurrentUser(): CurrentUser | null` — new. Client-side JWT-decode of the access token.
- `logout(): void` — **changed** (was localStorage-clear stub). Frozen contract: clears both tokens, redirects to `/login/` via `window.location.href`.
- All bodies `throw new Error("not implemented")` (params consumed via `void` to satisfy `noUnusedParameters`); coder fills them.
- Removed: `setToken(token: string): void`.

`frontend/src/api/auth.ts` (AMEND — thin `request`-delegating bodies, matching the existing file pattern):
- `login(body: LoginRequest, signal?: AbortSignal): Promise<TokenResponse>` — new. `POST /api/auth/login`.
- `refresh(body: RefreshRequest, signal?: AbortSignal): Promise<TokenResponse>` — new. `POST /api/auth/refresh` (public fn; the `client.ts` interceptor uses its OWN direct fetch, not this — cycle avoidance).
- `setupCreate(body: CreateDBRequest, signal?: AbortSignal): Promise<TokenResponse>` — **changed** (was `Promise<LoginResponse>`).
- `getAuthStatus(signal?)` / `setupImport(file, signal?)` — kept unchanged.

`frontend/src/api/client.ts` (AMEND):
- `request<T>(url: string, opts?: RequestOptions): Promise<T>` — signature **FROZEN UNCHANGED**. Body gains a 401 seam: on a `401` for a request that carried a token, delegates to `silentRefreshRetry`. Non-token / non-401 paths preserve existing behavior.
- `async silentRefreshRetry<T>(url: string, opts: RequestOptions): Promise<T>` — new **private** interceptor seam, body `throw new Error("not implemented")` (params `void`-consumed). **Coder implements the body**: one refresh via a DIRECT `fetch` to `/api/auth/refresh` with `{ refresh_token: getRefreshToken() }` (NOT `api/auth.refresh` — avoids `client → api/auth` cycle), then `setAccessToken` + one retry of `request<T>(url, opts)` (loop-guarded); on refresh failure / no refresh token → `logout()` + surface the original `ApiError`. The `getRefreshToken`/`setAccessToken`/`logout` imports from `../auth` are the coder's to add.
- `ApiError`, `RequestOptions`, `authHeaders`, `throwApiError` — unchanged.

Caller-compile edits (out of Source-files scope):
- `frontend/src/login/loginState.ts` — forced by the `setToken`→`setTokens` and `setupCreate: LoginResponse`→`TokenResponse` signature changes. Mechanical: import `setTokens` instead of `setToken`; `setToken(res.token)` → `setTokens(res.access_token, res.refresh_token)`; updated the matching doc-comment. `res` is now `TokenResponse` (has `access_token`/`refresh_token`). The full pair-storage / login-form migration remains **step 005's** job; this is only the minimal edit to keep `tsc` green. Nothing else in `frontend/` referenced the changed symbols.

### Step 005 — frozen interface (2026-07-22)

Frontend TS step; no test runner. Gate: `cd frontend && npx tsc --noEmit` — CLEAN.

`frontend/src/login/loginState.ts` (AMEND — `LoginState` class + module-level effect fn):
- `loginUsername: string = ""` — new observable field (login-form username draft).
- `loginPassword: string = ""` — new observable field (login-form password draft).
- `loginStatus: LoadStatus = "idle"` — new observable field (login submit status; `LoadStatus = "idle"|"loading"|"ready"|"error"`, the existing file alias — mirrors the wizard submit trio).
- `loginError: string | null = null` — new observable field (login refusal message).
- `get canSubmitLogin(): boolean` — new pure computed. True when not mid-submit AND `loginUsername.trim()` non-empty AND `loginPassword` non-empty. Implemented (trivial pure derivation, mirrors sibling `canSubmitCreate`).
- `export async function handleLogin(state: LoginState, signal?: AbortSignal): Promise<void>` — new module-level effect fn. Body `throw new Error("not implemented")` (params `void`-consumed). Coder wiring: `authApi.login({username: state.loginUsername, password: state.loginPassword}, signal)` → `setTokens(res.access_token, res.refresh_token)` → `window.location.href = "/"`; on `ApiError` record generic refusal into the login trio (`loginStatus="error"`, `loginError`), no navigation; early-return on `signal?.aborted`.
- `submitCreate` — CONFIRMED already storing the pair via `setTokens(res.access_token, res.refresh_token)` (step-004 skeleton caller-fix, line 114). Unchanged this step.

`frontend/src/login/Login.tsx` (AMEND — `observer` component, unchanged signature `export const Login`):
- Imports `handleLogin` from `./loginState`; adds inner handler `const onSubmitLogin = () => { void handleLogin(state); }`.
- The `needsSetup === false` branch now renders the real login form shell (username/password bound to `state.loginUsername`/`state.loginPassword` via `runInAction`, submit `disabled={!state.canSubmitLogin}`, `loading={state.loginStatus === "loading"}`, refusal via `state.loginError` → `Alert`) — replaces the 003 "Instance configured — proceed to login" placeholder. No plain `useState` fields, no Mantine `useForm`. The `needsSetup === true` wizard branch and the `Login` component signature are unchanged.

`frontend/src/user/App.tsx` (AMEND — `export const App` signature unchanged):
- New import `import { getToken } from "../auth";`.
- Mount-time gate at the top of the component body, before any routed content: `if (getToken() === null) { window.location.href = "/login/"; return null; }`. Existing `MantineProvider` + `BrowserRouter` + `UserRoutes` structure preserved.

`frontend/src/admin/App.tsx` (AMEND — `export const App` signature unchanged):
- New import `import { getToken } from "../auth";`.
- Same mount-time gate (`if (getToken() === null) { window.location.href = "/login/"; return null; }`) at the top of the component body. Existing structure preserved. Frozen minimally so feature-005's later layout growth can keep it.

- Caller-compile edits (out of Source-files scope): None.

## Tests

### Step 001 — tests (2026-07-22)

- `backend/tests/services/test_tokens.py` — NEW — bound to frozen Step-001 skeleton:
  - `test_access_token_claims_verify_with_user_key__DoD1_US003_AC1` — covers DoD-1 — access token verifies with the user's key; claims carry `user_id == str(user.id)` (STRING form), `username`, `role`, `type=="access"`.
  - `test_get_current_user_accepts_valid_access_token__DoD1_US003_AC1` — covers DoD-1 — a valid access token authenticates through `get_current_user`, returning the issued-for User.
  - `test_expired_access_token_fails_verification__DoD2_US004_AC2` — covers DoD-2 — expired access token → `verify_token_signature` raises `jwt.ExpiredSignatureError`.
  - `test_expired_access_token_rejected_by_get_current_user__DoD2_US004_AC2` — covers DoD-2 — expired access token → `get_current_user` raises `HTTPException` 401.
  - `test_refresh_token_rejected_by_get_current_user__DoD3_US003_AC1` — covers DoD-3 — a `type=="refresh"` token is refused by `get_current_user` (401); only access authenticates.
  - `test_maybe_rotate_rotates_when_stale_and_invalidates_old_token__DoD4_US003_AC1` — covers DoD-4 — stale (>~30d) key rotates (returns True, key changes) and a pre-rotation token no longer verifies (`jwt.InvalidSignatureError`).
  - `test_maybe_rotate_no_rotation_when_key_fresh__DoD4_US003_AC1` — covers DoD-4 — fresh key does NOT rotate (returns False, key unchanged): rotation window respected.
  - `test_get_current_user_rejects_pre_rotation_key_token__DoD4_US003_AC1` — covers DoD-4 — token signed with a pre-rotation key → `get_current_user` 401 when stored user carries a different key.
  - `test_get_current_user_rejects_disabled_user__DoD5_US004_AC1` — covers DoD-5 — disabled user (`pwdhash is None`) rejected 401 despite a valid signature + access type.
- `backend/tests/services/test_auth.py` — AMENDED — retired the obsolete `create_token` decode test (create_token removed in step 001); kept `test_hash_then_verify_password` and added `test_generate_signing_key_nonempty_and_unique` to retain direct coverage of the still-intact 003 primitives.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓ (all `[test]`; no `[manual/live]` items in this step).

### Step 002 — tests (2026-07-22)

- `backend/tests/services/test_login_auth.py` — NEW — bound to frozen Step-002 skeleton (`services/rate_limit.py`, `authenticate_user`, `refresh_access_token`, `AuthError`, `db.users.update`) + Step-001 helpers:
  - `test_valid_login_returns_user_and_clears_counter__DoD1_US003_AC1` — covers DoD-1 — valid creds return the matching `User`; the failure counter is cleared (proven via 4 pre + success + 4 post staying below threshold).
  - `test_wrong_password_raises_and_records_failure__DoD2_US003_AC2` — covers DoD-2 — wrong password raises `AuthError` and records exactly one failure (1 + MAX_FAILURES-1 locks).
  - `test_unknown_disabled_and_bad_pw_raise_same_generic_error__DoD2_US003_AC2` — covers DoD-2 — unknown username, disabled user (`pwdhash=None`), and bad password all raise the SAME `AuthError` type with no distinguishing detail (no enumeration).
  - `test_lockout_refuses_even_valid_credentials_then_clears__DoD3_US003_AC3` — covers DoD-3 — after MAX_FAILURES wrong attempts, valid creds are still refused; after `clear`, valid login succeeds and resets the counter.
  - `test_successful_login_rotates_stale_key_and_persists__DoD4_US003_AC1` — covers DoD-4 — stale-key login rotates + persists the key (re-fetch shows change) and sets `last_login`.
  - `test_successful_login_does_not_rotate_fresh_key__DoD4_US003_AC1` — covers DoD-4 — fresh-key user is not rotated on login (persisted key unchanged).
  - `test_refresh_returns_new_access_token_accepted_as_same_user__DoD5_US003_AC1` — covers DoD-5 — valid refresh yields a NEW access token that `get_current_user` accepts as the same user.
  - `test_refresh_with_expired_refresh_token_raises__DoD6_US004_AC2` — covers DoD-6 — expired refresh token → `AuthError`.
  - `test_refresh_for_disabled_user_raises__DoD7_US004_AC1` — covers DoD-7 — refresh for a disabled user (`pwdhash=None`) → `AuthError`.
  - Module autouse fixture `_reset_rate_limit` calls `rate_limit.reset()` before each test (module-global store isolation).
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓ (all `[test]`; no `[manual/live]` items in this step).

### Step 003 — tests (2026-07-22)

- `backend/tests/routes/test_auth.py` — NEW — in-process `http_client` (ASGITransport) against `app.main.app`, bound to frozen Step-003 skeleton (`LoginRequest`/`RefreshRequest`/`TokenResponse`/`MeResponse`, routes under `/api/auth`):
  - `test_login_valid_credentials_returns_token_pair__DoD1_US003_AC1` — covers DoD-1 — `POST /login` valid creds → 200 + `TokenResponse` with non-empty `access_token` AND `refresh_token`.
  - `test_login_invalid_credentials_401_no_tokens__DoD2_US003_AC2` — covers DoD-2 — `POST /login` wrong password → 401, no tokens in body.
  - `test_login_lockout_refuses_valid_creds_same_message__DoD3_US003_AC3` — covers DoD-3 — after `MAX_FAILURES` (5) failures, valid creds refused 401 with the SAME generic message as bad creds.
  - `test_me_valid_access_token_returns_string_id__DoD4_US003_AC1` — covers DoD-4 — `GET /me` valid access token → 200 + `MeResponse`; wire `id` is a JSON STRING == `str(user.id)`, plus username/role.
  - `test_me_expired_access_token_401__DoD5_US004_AC2` — covers DoD-5 — `GET /me` with PyJWT-crafted expired access token → 401.
  - `test_me_missing_authorization_header_401__DoD6_US004_AC1` — covers DoD-6 — `GET /me` with no `Authorization` header → 401.
  - `test_refresh_valid_token_returns_fresh_access__DoD7_US003_AC1` — covers DoD-7 — `POST /refresh` valid refresh → 200 + `TokenResponse` with fresh `access_token` (incoming refresh echoed).
  - `test_refresh_disabled_user_401__DoD8_US004_AC1` — covers DoD-8 — `POST /refresh` for a disabled user (`pwdhash=None`) → 401.
  - Autouse `_reset_rate_limit` fixture calls `rate_limit.reset()` per test; login cases configure a known admin via `POST /setup/create`, /me + /refresh cases seed a `User` via `db.users.create` (schema via `init_db`, readiness via `set_db_ready(True)`).
- `backend/tests/routes/test_setup.py` — AMENDED — retired the `LoginResponse` import + `token` assertion; `test_create_valid_returns_token_pair__DoD2_US001_AC1` now validates `TokenResponse` with non-empty `access_token` + `refresh_token` (feature-004 Step-003 DoD-9). All other setup assertions (status, refusals, valid/corrupt import) left intact.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓ (all `[test]`; no `[manual/live]` items in this step).

## Notes & Issues

_populated by the coder when worth saying_

### Skeleton — Step 004 UNBLOCKED + FROZEN (2026-07-22)

- The blocker below is **RESOLVED**: feature 003's frontend substrate (`api/auth.ts`, `types/auth.d.ts`, `login/loginState.ts`) has since been delivered. Step 004's interface is now frozen as a true amendment — see the `## Skeleton → Step 004 — frozen interface` section above. `npx tsc --noEmit` is clean. One mechanical caller-compile edit was made to `login/loginState.ts` (recorded there). The original blocked note is retained below for history.

### Skeleton — Step 004 BLOCKED: frontend substrate missing (unmet dependency) (2026-07-22)

- **Step:** 004 (`004.frontend-token-storage-refresh-client.md`).
- **What intent asked for (quotes):** "`src/api/auth.ts` (amend) … **setupCreate** (amend) — now returns `TokenResponse` (was `{token}`); `getAuthStatus` / `setupImport` unchanged." "`src/types/auth.d.ts` (amend) — replace the login-response `{token}` shape … Keep the existing status and create-DB request shapes." 004.context.md: "Any 003 caller of `setToken` (in `login/loginState.ts`) is migrated … in **step 005**."
- **What conflicts / why a clean freeze is impossible:** Two of the four in-scope source files — `frontend/src/api/auth.ts` and `frontend/src/types/auth.d.ts` — **do not exist**, and neither does `frontend/src/login/loginState.ts`. The plan writes Step 004 as an *amendment* of a frontend substrate delivered by the dependency `003.first-run-bootstrap`, but that feature's **step 005 (`005.frontend-first-run-wizard.md`) is `pending`** (see `docs/plans/003.first-run-bootstrap/status.md`). Git history confirms only feature 002's frontend scaffold ever touched `frontend/src`; the first-run-bootstrap frontend (which creates `api/auth.ts` with `getAuthStatus`/`setupCreate`/`setupImport`, `types/auth.d.ts` with the status/create-DB/login shapes, and `login/loginState.ts`) was never committed. Consequences: the login-response `{token}` shape to "replace" is absent; `setupCreate` to "re-point" is absent; `getAuthStatus`/`setupImport` to "keep unchanged" are absent; the status/create-DB request DTOs to "keep" are absent; and the `loginState.ts` caller the briefing expects a compile-fix for is absent. Freezing any of these would require **inventing feature-003-step-005's contract** (another feature's design) and would **invert the documented `003 → 004` dependency order** — both outside the skeleton role. No code was written; the compile gate was not run.
- **Cleanly-freezable subset (unblocked, deferred pending resolution):** the parts of Step 004 that do NOT depend on the missing substrate — `types/auth.d.ts`'s three new wire DTOs (`TokenResponse`, `MeResponse{id: string,…}`, `RefreshRequest`), `auth.ts`'s dual-token amend (`getToken`/`getRefreshToken`/`getCurrentUser`/pair+access setters/real `logout`), `api/auth.ts`'s `login`/`refresh`, and `client.ts`'s silent-refresh seam — are fully specified by this step + the confirmed backend step-003 contract and could be frozen once the substrate question is settled.
- **Suggested resolutions (tradeoffs):**
  1. **Run `003.first-run-bootstrap` step 005 first** (its skeleton → test → coder), landing `api/auth.ts` / `types/auth.d.ts` / `login/loginState.ts`, then re-run this Step-004 skeleton as the true amendment the plan describes. Cleanest; honors dependency order; no invented signatures. Cost: unblocks 003.005 out of the current session's focus.
  2. **Re-scope Step 004** (planner edit) so it *creates* only the symbols it actually owns (the four bullets above) and drops the "keep/re-point setupCreate/getAuthStatus/setupImport" and "status/create-DB shapes" language, explicitly deferring those to 003.005. Lets 004 proceed now, but risks a file-ownership collision when 003.005 later also creates `api/auth.ts` / `types/auth.d.ts`, and leaves the "setupCreate → TokenResponse" DoD unowned.
  3. **Fold 003.005 into this feature** (planner decision) — absorb the wizard substrate into 004. Largest scope change; consolidates the frontend auth surface but rewrites the plan boundary.
