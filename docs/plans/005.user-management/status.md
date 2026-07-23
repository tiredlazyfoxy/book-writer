# Feature 005 — user-management

| Step | File                              | Status  | Verifier | Date |
|------|-----------------------------------|---------|----------|------|
| 001  | `001.admin-guard-service-schemas.md` | done    | PASS     | 2026-07-22 |
| 002  | `002.admin-user-routes.md`        | done    | PASS     | 2026-07-22 |
| 003  | `003.admin-spa-users-base.md`     | done    | PASS     | 2026-07-23 |
| 004  | `004.user-mutation-modals.md`     | done    | PASS     | 2026-07-23 |

## Files Changed

### Step 001 — Admin guard + admin user service + schemas + `db.get_all`
- `backend/app/services/auth.py` — filled `validate_password_policy` (len<8 / confirm-mismatch → `PasswordPolicyError`) and `require_role` inner dependency (ladder `{author:0, admin:1}`, insufficient → 403)
- `backend/app/services/admin.py` — filled `_to_response` mapper + `list_users`/`create_user`/`set_user_password`/`set_user_role`/`disable_user`
- `backend/app/db/users.py` — filled `get_all` (session-free, ordered by username)
- `backend/app/models/schemas/admin.py` — confirmed the four DTO field sets (no change needed)

### Step 002 — Admin user HTTP routes (mount + 5 handlers)
- `backend/app/routes/admin/users.py` — filled the 5 handler bodies (parse → one `admin_service` call → return); added module-level `_ADMIN_ERROR_STATUS` map + `_map_admin_error` helper wiring `AdminError.reason` to 409/404/400 per decision 2
- `backend/app/routes/admin/__init__.py` — confirmed valid package marker (no change needed)
- `backend/app/main.py` — confirmed `admin_users.router` already mounted by skeleton (no change needed)

### Step 003 — Admin SPA users list + disable (frontend base)
- `frontend/src/admin/pages/usersPageState.ts` — filled `loadUsers` (loading → `adminApi.listUsers` → trio via `runInAction`, abort-guarded, `ApiError` → error state) and `disableUserAction` (`disableUser` then re-`loadUsers` refresh; `ApiError` recorded into `usersError` without wiping the list); added `runInAction`/`adminApi`/`ApiError` imports
- `frontend/src/types/admin.d.ts` — confirmed frozen DTOs (no change needed)
- `frontend/src/api/admin.ts` — confirmed 5 real `request` delegations + `ROLE_OPTIONS` (no change needed)
- `frontend/src/admin/routes.tsx` — confirmed `/` → `<UsersPage/>` (no change needed)
- `frontend/src/admin/App.tsx` — confirmed minimal layout with 004 token-gate preserved (no change needed)
- `frontend/src/admin/pages/UsersPage.tsx` — confirmed `observer` page: stable state, mount load/abort, list rows + per-row Disable `Menu` (no change needed)
- Gate: `cd frontend && npm run build` clean. All DoD items are `[manual/live]` — DoD-1/2/3 (list surface, redirect+403 error state, disable→inactive+refresh) require a live run against a configured instance.

### Step 004 — User-mutation modals (create / reset / role)
- `frontend/src/admin/components/users/CreateUserModal.tsx` — filled `submitCreate` (`runInAction`-guarded loading→`adminApi.createUser`→`onCreated()`; `ApiError` 409→`username` / 400→`password` / else→`form` `serverErrors`; abort-guarded; non-`ApiError` re-thrown); made inner `handleSubmit` async, closing via `onClose()` when `submitStatus === "ready"`; added `runInAction`/`adminApi`/`ApiError`/`AdminCreateUserRequest` imports
- `frontend/src/admin/components/users/SetPasswordModal.tsx` — filled `submitSetPassword` (loading→`adminApi.setUserPassword`→`onSaved()`; `ApiError` 400→`password` / else→`form`; abort-guarded; re-throw non-`ApiError`); async `handleSubmit` closes on `ready`; added the same imports (`AdminSetPasswordRequest`)
- `frontend/src/admin/components/users/SetRoleModal.tsx` — filled `submitSetRole` (loading→`adminApi.setUserRole`→`onSaved()`; `ApiError` 400 self-target→`form` / else→`form`; abort-guarded; re-throw non-`ApiError`); async `handleSubmit` closes on `ready`; added imports (`AdminSetRoleRequest`)
- `frontend/src/admin/pages/UsersPage.tsx` — no change needed (skeleton already wired the Create button, Set-Password/Change-Role menu items, component-local open/target flags, `refresh`, and the three modal mounts)
- Gate: `cd frontend && npm run build` clean (tsc + vite, EXIT 0). All DoD items are `[manual/live]`; DoD-1/2/3 (create/reset/role happy-path + refusal surfaces) require a live run against a configured instance.

## Skeleton

### Step 001 — frozen interface (2026-07-22)

`backend/app/models/schemas/admin.py` (create — Pydantic BaseModels, fully declared):
- `AdminUserResponse` — `id: str`, `username: str`, `role: UserRole`, `last_login: datetime | None`, `active: bool` — new. Secret-excluding (no `pwdhash`/`jwt_signing_key`/`salt`). **`id` is serialized as a STRING**: the service mapper must build `AdminUserResponse(id=str(user.id), …)` even though `User.id` is `int` in Python (snowflake convention; mirrors `MeResponse`).
- `AdminCreateUserRequest` — `username: str`, `password: str`, `password_confirm: str`, `role: UserRole` — new.
- `AdminSetPasswordRequest` — `password: str`, `password_confirm: str` — new.
- `AdminSetRoleRequest` — `role: UserRole` — new.

`backend/app/services/auth.py` (amend — 004 functions untouched):
- `require_role(min_role: UserRole) -> Callable[..., Awaitable[User]]` — new. Dependency **factory**: returns `async def dependency(user: User = Depends(get_current_user)) -> User`. The returned coroutine compares the caller's role against the ladder `{author:0, admin:1}`, returns the caller `User` if sufficient, else raises `HTTPException(403)`. Factory returns the closure (structural); the ladder logic in the inner `dependency` is the unimplemented body. Tests can call `require_role(admin)` then `await dep(user=<User>)` directly (DoD-13).
- `validate_password_policy(password: str, password_confirm: str) -> None` — new. Shared min-length-8 + confirm-match check; raises `PasswordPolicyError` on failure, else returns `None`.
- `PasswordPolicyError(Exception)` — new. Neutral, layer-safe error raised by the validator (auth cannot import admin).
- `MIN_PASSWORD_LENGTH = 8` — new module constant (mirrors `services/setup.MIN_PASSWORD_LENGTH`).

`backend/app/services/admin.py` (create — admin user service):
- `AdminErrorReason(str, enum.Enum)` — new. Members: `username_taken="username-taken"`, `not_found="not-found"`, `self_target="self-target"`, `already_disabled="already-disabled"`, `password_invalid="password-invalid"`.
- `AdminError(Exception)` — new. `__init__(self, reason: AdminErrorReason, message: str = "")`; sets `self.reason` + `self.message`. The discriminated domain error step 002's route maps to status (409/404/400/400/400). Home: `services/admin.py` (reached as `admin_service.AdminError` / `admin_service.AdminErrorReason`).
- `_to_response(user: User) -> AdminUserResponse` — new (private mapper; builds `id=str(user.id)`, derives `active = user.pwdhash is not None`, non-secret fields only).
- `async list_users() -> list[AdminUserResponse]` — new.
- `async create_user(req: AdminCreateUserRequest) -> AdminUserResponse` — new.
- `async set_user_password(user_id: int, req: AdminSetPasswordRequest) -> AdminUserResponse` — new.
- `async set_user_role(caller: User, user_id: int, req: AdminSetRoleRequest) -> AdminUserResponse` — new.
- `async disable_user(caller: User, user_id: int) -> AdminUserResponse` — new.

`backend/app/db/users.py` (amend — 003/004 functions untouched):
- `async get_all() -> list[User]` — new. Session-free; returns all users ordered by username; mirrors the existing `get_by_id`/`create` session pattern.

**Password-policy reuse choice:** 003's policy is **inlined** inside `services/setup.create_database` (not a standalone callable), so per 001.context.md the shared validator is **added to `services/auth.py`** (next to `hash_password`) as `validate_password_policy`, reused by `create_user`/`set_user_password` — avoiding a third inline copy. `setup.py` is left untouched (deferred convergence, an `outcome.md` observation). The validator raises `auth.PasswordPolicyError`; the admin service catches it and re-raises `AdminError(AdminErrorReason.password_invalid, …)` so the taxonomy stays in one place (DoD-14).

- Caller-compile edits (out of Source-files scope): None. `app/main.py` imports cleanly unchanged; the new admin router mount is step 002's job.

### Step 002 — frozen interface (2026-07-22)

`backend/app/routes/admin/__init__.py` (create — package marker, no aggregation):
- Module docstring only; each admin router owns its `/api/admin/...` prefix and is mounted individually by `app/main.py`. **Does not** re-export/aggregate the users router.

`backend/app/routes/admin/users.py` (create — HTTP layer, `APIRouter(prefix="/api/admin/users", tags=["admin-users"])` exported as `router`). Handlers gated by `Depends(auth_service.require_role(UserRole.admin))` (namespace import `from app.services import auth as auth_service`); bodies raise `NotImplementedError`. Frozen signatures:
- `async def list_users(caller: User = Depends(auth_service.require_role(UserRole.admin))) -> list[AdminUserResponse]` — `@router.get("")`, 200 (default) — new.
- `async def create_user(payload: AdminCreateUserRequest, caller: User = Depends(auth_service.require_role(UserRole.admin))) -> AdminUserResponse` — `@router.post("", status_code=status.HTTP_201_CREATED)`, 201 — new.
- `async def set_user_password(user_id: int, payload: AdminSetPasswordRequest, caller: User = Depends(auth_service.require_role(UserRole.admin))) -> None` — `@router.put("/{user_id}/password", status_code=status.HTTP_204_NO_CONTENT)`, 204 — new.
- `async def set_user_role(user_id: int, payload: AdminSetRoleRequest, caller: User = Depends(auth_service.require_role(UserRole.admin))) -> None` — `@router.put("/{user_id}/role", status_code=status.HTTP_204_NO_CONTENT)`, 204; threads `caller` into `admin_service.set_user_role(caller, user_id, payload)` for the self-guard — new.
- `async def disable_user(user_id: int, caller: User = Depends(auth_service.require_role(UserRole.admin))) -> None` — `@router.put("/{user_id}/disable", status_code=status.HTTP_204_NO_CONTENT)`, 204; threads `caller` into `admin_service.disable_user(caller, user_id)` — new.
- **Frozen typed-error → status map the coder must implement** (catch `admin_service.AdminError`, branch on `.reason`, raise `HTTPException`): `username-taken` → 409, `not-found` → 404, `self-target` → 400, `already-disabled` → 400, `password-invalid` → 400. Non-admin → 403 is produced by `require_role` itself (no handler role check). Path param `user_id` stays `int` (FastAPI parses the numeric snowflake string in the URL into a Python `int`).

`backend/app/main.py` (amend — 001/003/004 composition root; nothing else changed):
- Added import `from app.routes.admin import users as admin_users` (aliased — `users` name is already bound by `from app.db import users`).
- Added mount line `app.include_router(admin_users.router)` after `app.include_router(auth.router)`.

- Caller-compile edits (out of Source-files scope): None. `main.py` is an in-scope Source file for this step.
- Mount gate: no backend static typecheck configured; verified `app.routes.admin`, `app.routes.admin.users`, and `app.main` import cleanly and OpenAPI resolves all 5 routes with correct methods/paths/status codes (GET→200 `list[AdminUserResponse]`, POST→201 `AdminUserResponse`, the three PUTs→204 no-content).

### Step 003 — frozen interface (2026-07-22)

`frontend/src/types/admin.d.ts` (create — pure wire DTOs, fully declared; re-exports `UserRole`):
- `AdminUserResponse` — `{ id: string; username: string; role: UserRole; last_login: ISODateString | null; active: boolean }` — new. `id` is a **string** (snowflake serialized as string); `last_login` typed `ISODateString | null` (the `types/common` datetime convention); `active` read directly (decision 3).
- `AdminCreateUserRequest` — `{ username: string; password: string; password_confirm: string; role: UserRole }` — new.
- `AdminSetPasswordRequest` — `{ password: string; password_confirm: string }` — new.
- `AdminSetRoleRequest` — `{ role: UserRole }` — new.
- Role union: **reused** existing `UserRole` (`"admin" | "author"`) from `types/auth` — no duplicate union declared; `admin.d.ts` re-exports it (`export type { UserRole } from "./auth"`).

`frontend/src/api/admin.ts` (create — resource module over `client.request`, namespace-imported, `signal?` trailing; PUT paths interpolate the string id):
- `RoleOption` — `interface { value: UserRole; label: string }` — new.
- `ROLE_OPTIONS: RoleOption[]` — new. Fully declared const (`admin`/`author` value+label). **Placement:** lives in `api/admin.ts` (a `.d.ts` cannot hold a runtime value; a new standalone module is out of the 6-file scope) — the step-004 modals import it from here.
- `listUsers(signal?: AbortSignal): Promise<AdminUserResponse[]>` — new (GET `/api/admin/users`).
- `createUser(body: AdminCreateUserRequest, signal?: AbortSignal): Promise<AdminUserResponse>` — new (POST).
- `setUserPassword(userId: string, body: AdminSetPasswordRequest, signal?: AbortSignal): Promise<void>` — new (PUT `/{userId}/password`, 204→void).
- `setUserRole(userId: string, body: AdminSetRoleRequest, signal?: AbortSignal): Promise<void>` — new (PUT `/{userId}/role`).
- `disableUser(userId: string, signal?: AbortSignal): Promise<void>` — new (PUT `/{userId}/disable`).
- Note: the transport fns are thin real delegations to `request` (pure "how to call" — no behavior); only the page-state **effect** fns carry stubbed behavior (throw).

`frontend/src/admin/pages/usersPageState.ts` (create — list trio + external effects):
- `class UsersPageState` — observable fields fully declared: `users: AdminUserResponse[]` (default `[]`), `usersStatus: "idle" | "loading" | "ready" | "error"`, `usersError: string | null`; `makeAutoObservable(this)`. No effectful methods.
- `loadUsers(state: UsersPageState, signal?: AbortSignal): Promise<void>` — new external effect; **stub body throws** (coder fills: loading→`listUsers`→trio via `runInAction`).
- `disableUserAction(state: UsersPageState, userId: string, signal?: AbortSignal): Promise<void>` — new external effect; **stub body throws** (coder fills: `disableUser(userId)` then re-`loadUsers` as refresh). Threads the id as a `string`.

`frontend/src/admin/pages/UsersPage.tsx` (create — `observer` page component shell, compiles):
- `UsersPage` — `observer(function UsersPage())` — new. Owns `useState(() => new UsersPageState())`, mount `useEffect([state])` → `loadUsers` (abort on unmount), renders list (username / role `Badge` / last-login / active) + per-row `Menu` whose Disable item calls `disableUserAction` via a local `handleDisable(userId)`. Full JSX is the coder's to refine.

`frontend/src/admin/routes.tsx` (create — route table):
- `AdminRoutes` — `observer(function AdminRoutes())` — new. `<Routes>` mapping `/` (under the `/admin` basename) → `<UsersPage />`.

`frontend/src/admin/App.tsx` (amend — grown from the 004 placeholder; **004 mount token-gate preserved verbatim**):
- `App` — `observer(function App())` — changed. Still `if (getToken() === null) { window.location.href = "/login/"; return null }` first, then MantineProvider(dark) → `BrowserRouter basename="/admin"` → a minimal local header (`Group` + `Title`, no shared shell) → `<AdminRoutes />`. (was: single placeholder `Route path="*"` rendering a "coming soon" `Center`/`Title`.)

- Caller-compile edits (out of Source-files scope): None. `admin/main.tsx` imports `App` unchanged; `App` remains a zero-prop `observer` component.
- Compile gate: `cd frontend && npx tsc --noEmit` clean.

### Step 004 — frozen interface (2026-07-23)

**`serverErrors` shape (frozen, all three drafts):** `serverErrors: Record<string, string>` keyed by field name (`username` / `password` / `password_confirm` / `role`) plus a general `form` key for non-field refusals. The displayed `get errors(): Record<string, string>` merges client-validation errors with `serverErrors` (server overrides). Chosen over per-field `string | null` fields because the refusal set is small and open-keyed. Drafts hold **observable fields + `get` computeds only** — no effectful methods (BookWriter MobX rule; the reference's `reset()` is deliberately dropped, drafts are freshly constructed per open via conditional mount / `useState(() => new …Draft())`).

`frontend/src/admin/components/users/CreateUserModal.tsx` (create):
- `class CreateUserDraft` (module-private) — `makeAutoObservable`; observable `username=""`, `password=""`, `passwordConfirm=""`, `role: UserRole = "author"`, `serverErrors: Record<string,string> = {}`, `submitStatus: "idle"|"loading"|"ready"|"error" = "idle"`. Computeds: `get clientErrors(): Record<string,string>` (required username, min-8 password, confirm match), `get errors(): Record<string,string>` (client ∪ server), `get canSubmit(): boolean` (no client errors && not loading) — new.
- `submitCreate(draft: CreateUserDraft, onCreated: () => void, signal?: AbortSignal): Promise<void>` — exported effect; **body throws** (coder fills: `adminApi.createUser` → `onCreated()` + close; `ApiError` 409/400 → `serverErrors`). Imports the coder must add for the body: `import * as adminApi from "../../api/admin"` (or `{ createUser }`), `import { ApiError } from "../../api/client"`, `AdminCreateUserRequest` from `types/admin` — omitted from the stub because `noUnusedLocals` rejects unused imports — new.
- `CreateUserModalProps` — `{ opened: boolean; onClose: () => void; onCreated: () => void }` — new.
- `CreateUserModal` — `observer(function CreateUserModal(props: CreateUserModalProps))` — new. Holds `useState(() => new CreateUserDraft())`; renders `Modal` with username/password/confirm inputs + role `Select` (`ROLE_OPTIONS`) + submit. JSX is coder-refinable.

`frontend/src/admin/components/users/SetPasswordModal.tsx` (create):
- `class SetPasswordDraft` (module-private) — `makeAutoObservable`; observable `password=""`, `passwordConfirm=""`, `serverErrors`, `submitStatus`. Computeds: `get clientErrors` (min-8, confirm match), `get errors`, `get canSubmit` — new.
- `submitSetPassword(draft: SetPasswordDraft, userId: string, onSaved: () => void, signal?: AbortSignal): Promise<void>` — exported effect; **body throws** (coder fills: `adminApi.setUserPassword(userId, …)` → `onSaved()` + close; `ApiError` 400 → `serverErrors`) — new.
- `SetPasswordModalProps` — `{ opened: boolean; userId: string; username: string; onClose: () => void; onSaved: () => void }` — new.
- `SetPasswordModal` — `observer(function SetPasswordModal(props: SetPasswordModalProps))` — new.

`frontend/src/admin/components/users/SetRoleModal.tsx` (create):
- `class SetRoleDraft` (module-private) — `constructor(initialRole: UserRole)` sets `role` then `makeAutoObservable`; observable `role: UserRole`, `serverErrors`, `submitStatus`. Computeds: `get errors(): Record<string,string>` (server only — role is always valid), `get canSubmit(): boolean` (not loading) — new.
- `submitSetRole(draft: SetRoleDraft, userId: string, onSaved: () => void, signal?: AbortSignal): Promise<void>` — exported effect; **body throws** (coder fills: `adminApi.setUserRole(userId, …)` → `onSaved()` + close; `ApiError` 400 self-target / other → `serverErrors`) — new.
- `SetRoleModalProps` — `{ opened: boolean; userId: string; username: string; currentRole: UserRole; onClose: () => void; onSaved: () => void }` — new. `currentRole` seeds `SetRoleDraft`.
- `SetRoleModal` — `observer(function SetRoleModal(props: SetRoleModalProps))` — new. `useState(() => new SetRoleDraft(currentRole))`.

`frontend/src/admin/pages/UsersPage.tsx` (amend — step 003 base kept; list/`Menu`/Disable/mount-load unchanged):
- Added component-local modal flags: `useState(false)` (create), `useState<AdminUserResponse | null>(null)` (target), `useState<"password" | "role" | null>(null)` (action) — decision 10.
- Added local `refresh = () => void loadUsers(state, new AbortController().signal)` (= re-`loadUsers`; there is no page-state `refresh` helper) and `closeTarget = () => { setTarget(null); setAction(null) }`.
- Header `<Title>` wrapped in `<Group justify="space-between">` + a `Create user` `Button` (`IconPlus`) that opens the create modal.
- Per-row `Menu` gains **Set Password** (`IconKey`) and **Change Role** (`IconUserCog`) items alongside the existing **Disable**; each sets `target`/`action`.
- Renders `<CreateUserModal onCreated={refresh}/>` (always mounted, `opened` flag) and conditionally-mounted `<SetPasswordModal .../>` / `<SetRoleModal .../>` (mounted only when `target && action === …`, so each open gets a fresh draft — the drafts' reset-on-open) with `onSaved={refresh}`.
- New imports: `Button` (`@mantine/core`), `IconKey`/`IconPlus`/`IconUserCog` (`@tabler/icons-react`), `AdminUserResponse` type, the three modal components.

- Caller-compile edits (out of Source-files scope): None. `UsersPage.tsx` is an in-scope Source file (step-004 amend); no other caller touched. `usersPageState.ts` and `api/admin.ts` (incl. `ROLE_OPTIONS`) consumed read-only, unchanged.
- Compile gate: `cd frontend && npx tsc --noEmit` clean (EXIT 0). No test files this step (all DoD `[manual/live]`).

## Tests

### Step 001 — tests (2026-07-22)

- `backend/tests/services/test_require_role.py` — covers DoD-13 — require_role(admin) dependency admits an admin caller (returns it) and rejects an author caller with HTTPException 403.
- `backend/tests/services/test_admin_users.py` — covers DoD-1..DoD-12, DoD-14 — admin user service: create (author/admin, active+string-snowflake-id), taken-username refusal, password reset re-hash + re-enable, role change + self-target guard, disable nulls credentials + preserves identity fields + self-guard + already-disabled refusal, list_users ordering, secret-excluding response surface, password-policy refusals surfaced as AdminError(password_invalid).
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓, DoD-10 ✓, DoD-11 ✓, DoD-12 ✓, DoD-13 ✓, DoD-14 ✓

### Step 002 — tests (2026-07-22)

- `backend/tests/routes/admin/__init__.py` — new empty package marker (avoids `test_users.py` basename collision with `tests/db/` and `tests/services/`).
- `backend/tests/routes/admin/test_users.py` — covers DoD-1..DoD-12 — admin user HTTP surface over `http_client` (ASGITransport), seeding admin/author/target users + minting access tokens: author→403 vs admin→200 guard (DoD-1); list carries role/last_login/active (DoD-2); list secret-excluding + string ids (DoD-3); create→201 with role+active (DoD-4); duplicate username→409 (DoD-5); password reset→204 re-enables disabled (DoD-6); role change→204 + updated role (DoD-7); role self-target→400 (DoD-8); disable→204 + inactive (DoD-9); disable self→400 (DoD-10); mutations on non-existent id→404 (DoD-11); create/reset short-password & mismatched-confirm→400 (DoD-12).
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓, DoD-10 ✓, DoD-11 ✓, DoD-12 ✓

## Notes & Issues
- Step 001: `set_user_password` validates the password policy **before** the target lookup (per briefing's explicit sequence); ordering is behaviourally moot for the DoD cases (no test combines a missing target with an invalid password).
