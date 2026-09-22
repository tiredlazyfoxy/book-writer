# Feature 005 — user-management (feature-wide context)

## Goal & scope

Give an authenticated **admin** the ability to run the account lifecycle for the
whole instance from the Admin SPA: **list**, **create**, **reset-password**,
**change-role**, and **disable** user accounts. There is **no hard delete** —
disable is terminal (nulls the account's credentials) and the *only* re-enable
path is a password reset. Cross-layer:

- **Backend** — the `require_role(admin)` FastAPI guard (first built AND consumed
  here — deferred from feature 004), an admin user service (validation,
  self-guards, credential nulling/minting, the secret-excluding response mapping),
  the admin HTTP routes + schemas, and `db/users.get_all`.
- **Frontend** — the Admin SPA's first real pages: a users list with a per-row
  action menu, plus create / reset-password / change-role modals.

Delivers **FEAT-003** — `UC-005..009` / `US-005..009`. Read
`docs/product/use-cases/FEAT-003.user-management.md` and
`docs/product/stories/FEAT-003.user-management.md`; every `[test]` DoD item cites
the `US-###.AC-#` it verifies.

The settled boundary is `brief.md` (Definition + Scope In/Out). **Out of scope
(do not widen):** self-service profile management; book moderation (Stage 6). No
separate "enable" endpoint — re-enable happens *only* as a side effect of
password reset (US-007.AC-2).

## Architecture sources (read these)

- `docs/architecture/backend.md` — the enforced 4-layer rules (`routes/`
  HTTP-only; `services/` no `session`/`AsyncSession`/`select()`/`session.exec()`/
  `session.add()`; `db/` session-free, ORM never leaks, one module per entity;
  `models/` tables + schemas), typed discipline (Pydantic `BaseModel` for all
  API I/O; no free dicts), bcrypt hashing, per-user HS256 signing key, and the
  pytest/httpx in-process harness.
- `docs/architecture/frontend.md` — MobX hard rules (`observer` on every
  component; state = observable fields + pure `get` computeds, **never** effectful
  methods; effectful ops are external `(state, args, signal)` fns with
  `runInAction`; the async trio `<name>`/`<name>Status`/`<name>Error`; forms are
  drafts-in-state + `get`-computed validation + separate `serverErrors` —
  **no Mantine `useForm`**; `useState(() => new XState())`; page-level `useEffect`
  only); the `api/` layer (`request<T>` + `ApiError`, namespace-imported resource
  modules, `signal?` last, `types/` DTOs match wire JSON 1:1, no `any`, no zod).
- Root `CLAUDE.md` — backend tests `cd backend && .venv/Scripts/python -m
  pytest`; **no frontend test runner** — every frontend DoD item is
  `[manual/live]`.

## Substrate — delivered surfaces this feature builds on / amends

Features **003.first-run-bootstrap** and **004.authentication-session** are the
substrate. Several files here are **edited**, not created — expected
cross-feature amendment, **not** scope drift; per-step context files flag each.

Backend, treat as given:

- `app/models/user.py` (003) — `UserRole {admin, author}`; `User` table:
  application-generated 64-bit **snowflake** `id` (`default_factory=generate_id`
  from `app/ids.py`, generated at construction — **not** DB autoincrement; still
  an `int` column in Python); unique indexed `username`; **nullable** `pwdhash`
  (**null == account disabled** — no separate `disabled` flag); `role`;
  **nullable** `jwt_signing_key`; nullable `last_login` and `last_key_update`.
  **No `salt`.**
- `app/db/users.py` (003 + 004) — session-free: `create`, `get_by_username`,
  `get_by_id`, `admin_exists`, and **`update(user)`** (added in 004). **No
  `get_all` yet — step 001 adds it.** All mutations mutate the ORM object in the
  service, then call `update(user)`; there are no per-field db funcs and this
  feature adds none.
- `app/services/auth.py` (003 + 004) — `hash_password(password)` (no salt arg),
  `verify_password`, `generate_signing_key` (`secrets.token_hex(32)`), the
  access/refresh token mint + verify, and the **`get_current_user`** FastAPI auth
  dependency (rejects a user whose `pwdhash`/`jwt_signing_key` is null → 401).
  **Step 001 adds `require_role`** here — a dependency factory layered over
  `get_current_user`. `get_current_user` already establishes the sanctioned
  pattern that an **auth dependency living in `services/auth.py` raises the HTTP
  error directly** (this is not a routes-layer violation).
- `app/routes/auth.py` (003 + 004) — `APIRouter(prefix="/api/auth")`, mounted in
  `app/main.py`. `app/main.py` is the composition root that includes routers.
- 003's `create_database` enforces the **min-length-8 + password==confirm**
  policy in the service (decision 3 of 003). This feature reuses that policy for
  admin create/reset (see decision 4 below) rather than writing a third copy.
- Test harness (001/002): `pytest`/`pytest-asyncio` `asyncio_mode="auto"`;
  in-process `httpx.AsyncClient` over `ASGITransport`; `tests/conftest.py`
  provides a temp-SQLite `DbConfig` fixture + an `http_client` fixture; the
  process-global `db_ready` flag is reset between tests.

Frontend, treat as given:

- `src/api/client.ts` (002/004) — `request<T>(url, {method?, body?, signal?})`;
  injects `Authorization: Bearer <getToken()>`; `204` → `undefined`;
  `ApiError(status, message, details?)`.
- `src/auth.ts` (002/004) — dual-token storage; `getToken()`, `getCurrentUser()`,
  `logout()`. One-way `api/` → `auth.ts`.
- `src/admin/App.tsx` + admin entry (`admin/index.html`, `src/admin/main.tsx`)
  (002/004) — the Admin SPA mounts at `/admin` with a **mount-time token-gate**
  added in 004 (redirects to `/login/` when unauthenticated). Step 003 grows this
  App beyond its placeholder and **keeps the 004 token-gate**.

## Cross-cutting decisions (apply across steps)

Confirmed by the user; do not re-open.

1. **Roles = admin / author** (from 003; no editor/player). `require_role`
   ladder = `{author: 0, admin: 1}`; insufficient → **403**. `require_role` is
   built in step 001 and first consumed in step 002. Frontend role vocabulary is
   the `admin | author` union + a shared `ROLE_OPTIONS` list.
2. **Status taxonomy** (the route→status mapping): non-admin → **403**
   (`require_role`); username already taken → **409**; target user not found →
   **404**; self-guard (change own role / disable self) → **400**; password
   validation failure → **400**.
3. **Derived `active: bool` on `AdminUserResponse`** = `pwdhash is not None`,
   computed in the hand-built response mapping (not the ORM). **It is NOT a
   `User`-table column** — derived at response time only, so **no `User`-table
   change and no import/export codec change**. `AdminUserResponse` =
   `{id (int in Python, serialized as a string on the wire per the system-wide
   snowflake convention), username, role, last_login, active}`; still
   secret-excluding (US-005.AC-2). The UI reads `active` directly.
4. **Password validation in the SERVICE, not routes** — min length **8** +
   confirm-match, consistent with 003's policy. Reuse 003's setup password
   policy rather than writing a third copy (see step 001 context for placement);
   raise a typed error the route maps to **400**.
5. **Disable** nulls `pwdhash` + `jwt_signing_key` (**NO `salt`** — dropped in
   003); the row (id/username/role/last_login) is preserved → data + attribution
   intact (US-009.AC-2). Already-disabled (`pwdhash is None`) → **400**. Session
   invalidation is automatic via 004's per-request `get_current_user` checks
   (null signing key + null pwdhash → 401).
6. **Reset password** hashes a new `pwdhash`, generates a fresh `jwt_signing_key`,
   sets `last_key_update`, and **re-enables** a disabled account (the sole
   re-enable path); rotating the key invalidates the target's old sessions.
7. **Credential minting returns `(pwdhash, signing_key)`** — no salt;
   `hash_password` takes no salt arg (established in 003/004).
8. **`db/users.get_all()`** (ordered by username) is the only new db func; all
   mutations go through the existing `update(user)`.
9. **Self-guards live in the service** — the route threads the authenticated
   `caller: User` (from `require_role(admin)`) into the service function; the
   service compares `caller.id == user_id`. Routes stay HTTP-only (parse → call
   service → map typed error → return).
10. **Frontend**: modal open/target flags are **component-local `useState`**
    (not page state); drafts-in-state + `get`-computed validation + separate
    `serverErrors`; list refresh = re-call the loader after each mutation;
    `observer` on every component. **Keep the Admin SPA layout minimal** — host
    the users page + a simple header/nav; do **not** build a shared cross-SPA
    `AppLayout/Sidebar/Header` system yet (that can arrive when 006/007 add more
    admin pages).

## Reference project

`D:/GitRoot/_TextGens/LLMRPTextOnlyProject` implements the same capability with
the same stack — **adapt, don't copy**. Decisions 1–10 override several reference
choices: admin/author roles (not admin/editor/player), a derived `active` field
(replacing the reference's fragile `last_login===null && role!=="admin"` frontend
heuristic), password validation **in the service** (the reference leaks
match/length checks into route handlers — move them down), disable nulls **no**
`salt`, and a **minimal** admin layout (not the reference's full shared shell). On
entity ids, feature 005 now **follows** the reference's approach —
application-generated snowflake ids serialized as strings on the wire — per the
finalized system-wide convention. Per-step context files cite the reference file
paths the briefing harvested.

## Files touched across the feature

```
backend/
  app/
    services/auth.py                 (001 amend — add require_role; 004 file)
    services/admin.py                (001 create — admin user service + _to_response)
    models/schemas/admin.py          (001 create — the 4 DTOs incl. active)
    db/users.py                      (001 amend — add get_all; 003/004 file)
    routes/admin/__init__.py         (002 create — admin router package)
    routes/admin/users.py            (002 create — the 5 endpoints)
    main.py                          (002 amend — include the admin users router; 001 file)
  tests/
    services/test_admin_users.py     (001, test-coder — new)
    services/test_require_role.py    (001, test-coder — new)
    routes/admin/test_users.py       (002, test-coder — new)
frontend/
  src/types/admin.d.ts               (003 create — DTOs + role union)
  src/api/admin.ts                   (003 create — 5 resource fns)
  src/admin/routes.tsx               (003 create — route table)
  src/admin/App.tsx                  (003 amend — minimal layout + routes; keep 004 token-gate)
  src/admin/pages/UsersPage.tsx      (003 create; 004 amend — wire modals)
  src/admin/pages/usersPageState.ts  (003 create — list trio + loader + disable action)
  src/admin/components/users/CreateUserModal.tsx   (004 create)
  src/admin/components/users/SetPasswordModal.tsx  (004 create)
  src/admin/components/users/SetRoleModal.tsx      (004 create)
```

`services/auth.py`, `db/users.py`, and `main.py` are amended here (003/004 files);
`src/admin/App.tsx` grows beyond the 002/004 placeholder and `UsersPage.tsx` is
edited by two steps (003 base, 004 modal wiring). All are legitimate incremental
edits — each is flagged in its step context so it is not read as scope drift.
