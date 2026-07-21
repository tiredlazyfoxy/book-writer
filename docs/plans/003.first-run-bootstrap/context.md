# Feature 003 — first-run-bootstrap (feature-wide context)

## Goal & scope

Bring an **unconfigured** BookWriter instance to a usable state. On first run
with no usable admin, an operator either **(a) creates** a fresh DB + first
admin (and lands signed-in) or **(b) imports** an existing DB export to
bootstrap (then logs in normally). Cross-layer: backend (`User` model + minimal
auth primitives + setup service + setup routes) **and** frontend (the first-run
wizard in the login entry).

Delivers **FEAT-001** — `UC-001`/`US-001` (create DB + first admin) and
`UC-002`/`US-002` (import DB to bootstrap). Read
`docs/product/use-cases/FEAT-001.first-run-bootstrap.md` and
`docs/product/stories/FEAT-001.first-run-bootstrap.md`; every `[test]` DoD item
cites the `US-###.AC-#` it verifies.

The settled boundary is `brief.md` (Definition + Scope In/Out). **Out of scope
(do not widen):** ongoing user management (feature 005); the export *side*
(feature 007 — 003 only *consumes* an export to import); full session mechanics
beyond issuing the first admin's token (feature 004 — no login endpoint, no
token-verification dependency/middleware, no rotation-on-login, no logout here).

## Substrate — this feature amends features 001 & 002

Features `001.backend-scaffold` and `002.frontend-scaffold` are the substrate.
Several files here are **edited**, not created — this is expected cross-feature
amendment, **not** scope drift. Per-step context files flag each amendment.

Backend interfaces already delivered (from 001, treat as given):

- `app/db/engine.py` — `DbConfig` dataclass; `init_engine(config)` (module-level
  async engine singleton; makes `data/` dir; does **not** create tables);
  `init_db()` (runs the model-registration hook then `SQLModel.metadata.create_all`
  + an idempotent additive `ALTER` seam); a **model-registration hook** that
  imports `app.models.*` table modules so they register on `SQLModel.metadata`
  before `create_all` (empty in 001 — **003 adds the `user` import**);
  `get_standalone_session()` (the sole session primitive; raises if the engine
  is uninitialized).
- `app/db/import_export_queries.py` — `export_table(model_class, callback)`,
  `upsert_batch(items)`, `run_vector_rebuild()` (session-free primitives).
- `app/services/db_import_export.py` — `TABLE_REGISTRY` (an **ordered** list of
  `(zip_filename, model_class, to_dict_fn, from_dict_fn)`, **empty** in 001, FK
  order), `BATCH_SIZE = 100`, `export_all() -> bytes`, `import_all(zip_bytes)`
  (calls `init_db()` first, streams line-by-line into `upsert_batch`, then
  `run_vector_rebuild()`; UPSERT/idempotent).
- `app/main.py` — the FastAPI `app` singleton + a startup **lifespan** that in
  001 calls `init_engine` → `init_db` → vector-init. The eager `init_db`/
  `create_all` in that lifespan is a **recorded seam** (001 `context.md`) that
  **003 removes** — schema creation is deferred to the setup flows.
- `app/db/health.py` `ping()` — readiness probe (`SELECT 1`); works on an open
  engine even with zero tables (so the health contract survives the deferral).
- Test harness (from 001): `pytest` + `pytest-asyncio` `asyncio_mode="auto"`;
  in-process `httpx.AsyncClient` over `ASGITransport`; `tests/conftest.py`
  provides a temp-SQLite `DbConfig` fixture (runs `init_engine` + `init_db`) and
  an `http_client` fixture.

Frontend interfaces already delivered (from 002, treat as given):

- `src/api/client.ts` — `request<T>(url, {method?, body?, signal?})` (default
  GET; sets `Content-Type: application/json`; injects `Authorization: Bearer
  <getToken()>` **only when a token is present**; JSON-stringifies `body`; `204`
  → `undefined`; else `res.json() as T`); `ApiError(status, message, details?)`;
  `throwApiError(res)` (message from a `{detail}` body); `authHeaders()` (headers
  incl. Bearer-when-present, for streaming/multipart callers that bypass
  `request`).
- `src/auth.ts` — module-level, `localStorage`-backed: `getToken()` (reads
  `localStorage["token"]`, or `null`) + a `logout()` stub. **No** import from
  `src/api/` (one-way `api/` → `auth.ts`). **003 adds `setToken()`.**
- `login/main.tsx` + `login/Login.tsx` — the **bare placeholder** login entry
  (002 decision 1: no form, no auth). **003 rebuilds `Login.tsx`** into the
  real first-run wizard; `main.tsx` (which mounts `<Login/>` under a
  `MantineProvider defaultColorScheme="dark"`) is unchanged.
- The login entry is **outside React Router**; navigation uses
  `window.location.href` (sanctioned by `frontend.md`).

## Cross-cutting rules (apply in every step)

- **Backend 4-layer separation** (`backend.md`): `routes/` HTTP only (no business
  logic, no DB); `services/` orchestration — **no `session`/`AsyncSession`/
  `select()`/`session.exec()`/`session.add()`**; `db/` session-free, one module
  per entity, ORM types never leak; `models/` SQLModel tables + Pydantic schemas
  (schemas under `models/schemas/`), no logic. Dependency direction
  `routes → services + db`; `services → db`; `db → models`. Namespace imports
  (`from app.db import users` → `await users.get_by_username(...)`;
  `from app.services import auth as auth_service`).
- **`app/main.py` is the composition root**, not a route — its lifespan may call
  the `db/` layer directly for startup readiness detection (see step 002). This
  is not a routes-layer violation.
- **Typed discipline**: Pydantic `BaseModel` for all API I/O; `SQLModel` for
  tables; no free dicts. Frontend DTOs are hand-written `.d.ts` in `src/types/`
  matching backend schemas 1:1; no `any`, no zod.
- **Auth scheme** (`backend.md`): bcrypt password hashing; **per-user** JWT
  (HS256) signed with that user's own `jwt_signing_key`; payload carries
  `user_id`, `username`, `role`, and a ~30-day `exp`. 003 introduces only the
  **minimal** subset needed to hash the admin password and mint its first
  token — verification, rotation-on-login, and logout are feature 004's.
- **Import/export contract** (`backend.md` / root `CLAUDE.md`): every persistent
  model needs a JSONL codec pair + one **ordered** `TABLE_REGISTRY` tuple **in
  the same change** that adds the model; `users` is **first** in FK order.
  Import is streaming UPSERT; `init_db()` runs before import; the LanceDB index
  is **rebuilt from source rows on import, not exported**.
- **Frontend MobX rules** (`frontend.md`): `observer` on every component; state
  objects hold observable fields + pure `get` computeds and **never** effectful
  methods; effectful ops are external `(state, args, signal)` functions using
  `runInAction`; the async trio is `<name>` / `<name>Status:
  'idle'|'loading'|'ready'|'error'` / `<name>Error`; forms are drafts-in-state +
  `get`-computed validation — **no Mantine `useForm`**. The login entry is
  exempt from `<Page>State`/router machinery but **still** binds `observer`,
  the no-`useForm` rule, and the external-effect-fn rule (uses a
  `<Component>State` class, per decision 9 below).

## Unconfigured detection — the readiness flag (decision 1)

`needs_setup = not db_ready`. `db_ready` is a **process-level flag** in
`db/engine.py`:

- Read via `is_db_ready()`, written via `set_db_ready(value)`.
- **Initialized at startup by admin-existence**: the lifespan queries whether
  ≥1 admin user exists (`db.users.admin_exists()`, which returns `False`
  gracefully if the `users` table is missing) and sets the flag accordingly.
  This is more robust than the reference's file-existence check.
- Flipped to `True` at the **end** of a successful `create_database` or
  `import_database`; left `False` when either is refused.

Because the flag is process-global, backend tests must reset it between tests
(via `set_db_ready(False)`) — a test-harness concern noted where relevant.

## Confirmed decisions (do not re-open)

1. **Unconfigured signal = no admin account exists** (see readiness flag above).
2. **Drop the separate `salt` column** — bcrypt embeds its own salt; store only
   `pwdhash`.
3. **Validation lives in the service, not the route** — `create_database`
   enforces min length **8** and password==confirm and the already-configured
   refusal, raising a typed `SetupError` the route maps to HTTP 4xx. Routes stay
   HTTP-only.
4. **Graceful import rejection** — `import_database` wraps the import; a corrupt/
   invalid archive raises `SetupError` → route returns **400**, and
   `set_db_ready` is **not** called (instance remains unconfigured). Full
   transactional rollback of a partial import is **not** required (noted as a
   possible enhancement); the required outcome is "refused + remains
   unconfigured."
5. **Roles = `admin` / `author`.** `UserRole` = {admin, author}; the first admin
   is `admin`. No editor/player from the reference.
6. **`User.id` = autoincrement integer.** The import codec still serializes/
   upserts explicit ids (bootstrap imports into an empty instance, so no
   collision). The system-wide ID strategy is an open `/architect` question
   (see `outcome.md`) — 003 does not lock it.
7. **Min length = 8** (resolves `US-001.AC-3`'s `_TBD`) — to be back-propagated
   to `docs/product/` via `/product-spec` (see `outcome.md`).
8. **Create auto-signs-in; import does not.** `POST /setup/create` returns
   `{token}` (frontend stores it, redirects to `/`); `POST /setup/import`
   returns `{needs_setup:false}` with **no** token — the operator then logs in
   with a restored account.
9. **Frontend first-run UI rebuilt to BookWriter conventions** — lives in the
   login entry, `observer`-wrapped, a `<Component>State` class (drafts + a
   status trio + `get`-computed confirm-match/min-length), external
   `(state, args, signal)` effect functions hitting `src/api/auth.ts`, **no**
   Mantine `useForm`; navigation via `window.location.href`. Do **not** copy the
   reference's plain-`useState` component.

## Reference project

`D:/GitRoot/_TextGens/LLMRPTextOnlyProject` implements FEAT-001 with the same
stack. **Adapt, don't copy** — decisions 1–9 override several reference choices
(admin-existence detection, no `salt`, autoincrement id, admin/author roles,
service-side validation, graceful import rejection, rebuilt login component).
Per-step context files cite concrete `path:line` anchors.

## Files touched across the feature

```
backend/
  app/
    models/user.py                       (001 create)
    models/schemas/auth.py               (004 create)
    db/users.py                          (001 create)
    db/engine.py                         (002 amend — 001 file)
    services/auth.py                     (001 create)
    services/setup.py                    (003 create)
    services/db_import_export.py         (003 amend — 001 file: User codec + registry)
    routes/auth.py                       (004 create)
    main.py                              (002 amend lifespan; 004 amend router mount — 001 file)
  tests/
    db/test_users.py                     (001, test-coder)
    services/test_auth.py                (001, test-coder)
    test_startup_detection.py            (002, test-coder)
    conftest.py                          (002 extend — readiness reset; 001 file)
    services/test_setup.py               (003, test-coder)
    routes/test_setup.py                 (004, test-coder)
frontend/
  src/types/auth.d.ts                    (005 create)
  src/api/auth.ts                        (005 create)
  src/auth.ts                            (005 amend — add setToken; 002 file)
  login/Login.tsx                        (005 rebuild — 002 placeholder)
  login/loginState.ts                    (005 create)
```

`tests/conftest.py` and `app/main.py` are each edited by two features/steps —
same role editing one file incrementally across dependent steps. Precedent:
001's conftest (002+003) and 002's `App.tsx` (001+003). Not a scope breach.
