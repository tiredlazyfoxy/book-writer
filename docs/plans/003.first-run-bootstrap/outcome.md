# Outcome — 003.first-run-bootstrap

Intended documentation changes to apply at finalization. Grouped by target file
for the architect. The coder appends `## Observations` at the bottom.

## `docs/architecture/backend.md`

- **Section: a new "Domain models" / "User" subsection (or under
  Authentication).** Add: `User` is the **first persistent entity** — fields
  `id` (autoincrement integer PK), `username` (unique, indexed), `pwdhash`
  (nullable bcrypt hash — **null == disabled account**, no separate `disabled`
  bool), `role` (`UserRole` enum = `admin` | `author`), `jwt_signing_key`
  (nullable per-user HS256 key), `last_login`, `last_key_update`. Reason: records
  the first realized entity + the "disabled == null pwdhash" convention that
  feature 005 depends on; carries a `**Realizes:** FEAT-001, UC-001, UC-002`
  header. Note the deliberate divergence from the reference (no `salt` column;
  autoincrement id, not snowflake; admin/author roles).

- **Section: Authentication.** Clarify that 003 delivers only the **minimal**
  auth subset — bcrypt `hash_password`/`verify_password`, per-user
  `generate_signing_key`, and `create_token(user)` (HS256 over the user's own
  key; payload `user_id`/`username`/`role`/`exp≈+30d`). Token *verification*,
  rotation-on-login, and logout remain feature 004. Reason: keeps the auth
  section honest about what exists vs. what's still pending.

- **Section: Relational storage / startup lifecycle.** Record the **startup
  lifecycle change**: the lifespan no longer runs `create_all` eagerly; a cold
  instance boots with an open engine and **zero tables**, and schema creation is
  **deferred to the setup flows** (`create_database` / `import_database`, each of
  which calls `init_db()`). Unconfigured state is detected from **admin
  existence** (`db.users.admin_exists()` → the `is_db_ready`/`set_db_ready`
  process flag; `needs_setup = not is_db_ready()`), not file existence. Reconcile
  the **health-readiness note**: `GET /api/health` still passes on a cold
  instance because `db.health.ping()`'s `SELECT 1` succeeds on an open engine
  with no tables. Reason: this supersedes the 001 "eager `create_all`" seam and
  is a system-wide behavioral change.

- **Section: DB import/export.** Record that `users` is the **first**
  `TABLE_REGISTRY` entry (FK order) with a `to_dict`/`from_dict` codec, and that
  the codec **includes credentials** (`pwdhash`, `jwt_signing_key`) so restored
  accounts can authenticate. Reason: establishes the codec pattern for the first
  model and flags the security consideration below.

## `docs/architecture/system-overview.md`

- **Section: REST contract / endpoints.** Add the first-run setup endpoints under
  `/api/auth`: `GET /api/auth/status` → `AuthStatusResponse{needs_setup}`;
  `POST /api/auth/setup/create` (JSON `CreateDBRequest`) → `LoginResponse{token}`
  (auto-sign-in); `POST /api/auth/setup/import` (multipart `file`) →
  `AuthStatusResponse` (no token). Reason: first real endpoints; front door of a
  cold instance. Also note the frontend first-run wizard lives in the **login
  entry** and navigates via `window.location.href`.

## `docs/architecture/quick-reference.md` (create if still absent)

- Add the setup endpoints (above) and the DTOs `AuthStatusResponse`,
  `CreateDBRequest`, `LoginResponse`, plus the `User` table shape and `UserRole`
  enum. Reason: the architect deferred creating `quick-reference.md` until real
  endpoints/models existed — 003 is the first to produce them.

## `docs/product/` (via `/product-spec` only — read-only from here)

- **`stories/FEAT-001.first-run-bootstrap.md` — `US-001.AC-3`.** The
  `_TBD: minimum length value not specified_` is resolved to **8 characters**
  (decision 7). Back-propagate via `/product-spec` (product docs are writable
  only by that pipeline). Reason: 003 implements min-8; the product doc should
  stop carrying the `_TBD`.

## Open questions for `/architect` (raise, do not resolve in a plan)

- **System-wide ID strategy.** 003 uses **autoincrement integer** ids for `User`
  (decision 6), and the import codec upserts explicit ids (safe because bootstrap
  imports into an empty instance). Autoincrement vs. snowflake/distributed ids
  affects cross-instance import identity and **every future model** — this must
  be an explicit `/architect` decision; 003 must not be read as locking it.

- **Export credential-redaction policy.** DB exports currently carry credentials
  (`pwdhash`, `jwt_signing_key`) — required so imported accounts authenticate,
  but a security exposure. The architect / feature 007 (export side) should set a
  redaction/handling policy for exported credential material.

- **Partial-import rollback.** `import_database` refuses a corrupt archive and
  leaves the instance unconfigured (`set_db_ready` not called), but does **not**
  transactionally roll back a partially-written import (decision 4). Whether full
  rollback is needed is a possible enhancement for the architect to weigh.

## Observations

- Feature 001 / step 004's `test_db_import_export.py::test_export_all_returns_valid_empty_zip__DoD1`
  asserted an **empty** `TABLE_REGISTRY` (`list(TABLE_REGISTRY) == []`) and an
  empty `export_all()` archive (`namelist() == []`). That precondition is
  **superseded** by feature 003 step 003, which registers the first persistent
  model (`users`) as the registry's first entry — so the registry is non-empty
  and `export_all()` now emits a `users` member. The stale assertion and module
  docstring are reconciled **in-scope** in step 003 (test updated, not deleted;
  see step 003 DoD-8). The file's other three tests do not depend on emptiness
  and remain valid.

- Feature 003 step 004 added empty `__init__.py` package markers across the
  backend `tests/` tree (`tests/`, `tests/db/`, `tests/services/`,
  `tests/routes/`). Reason: step 004's `tests/routes/test_setup.py` shares the
  module basename `test_setup` with step 003's `tests/services/test_setup.py`;
  under the declared full-suite command (`cd backend &&
  .venv/Scripts/python -m pytest`, pytest default prepend import mode) two
  same-basename files with no package markers abort collection with `import file
  mismatch`. The markers make each module fully-qualified
  (`tests.routes.test_setup` vs `tests.services.test_setup`), so same-basename
  test modules across directories coexist. Adopting `--import-mode=importlib`
  project-wide is a possible future alternative, but the chosen fix is package
  markers.

---
Status: Applied 2026-07-22 (PARTIAL — backend-only)
Applied items: 6
Rejected items: 0
Deferred items: 2

This was a **partial (backend-only)** finalization. Steps 001–004 are done + PASS;
frontend step 005 is still pending, so frontend-dependent items were deferred.

Applied to `docs/architecture/`:
- **backend.md** — new "Domain models" → "User" subsection (`Realizes: FEAT-001,
  UC-001, UC-002`); Authentication "What feature 003 delivers (minimal subset)"
  note (bcrypt + per-user key + `create_token`; verification/rotation/logout ⇒
  feature 004); deferred-schema startup lifecycle (zero tables on boot, admin-
  existence readiness, cold-instance health still passes, supersedes feature-001
  eager `create_all`); DB import/export (`users` first `TABLE_REGISTRY` entry,
  supersedes empty-registry precondition).
- **system-overview.md** — first-run setup endpoints under `/api/auth` (`status`,
  `setup/create`, `setup/import`). No frontend-wizard note added (deferred).
- **quick-reference.md** — three setup endpoints, DTOs (`AuthStatusResponse`,
  `CreateDBRequest`, `LoginResponse`), `User` table shape, `UserRole` enum.

Three design decisions recorded:
1. **System-wide Snowflake ID standard** (universal, no permanent exceptions) — new
   "Conventions — entity ID strategy" note in backend.md + a dated 2026-07-22
   "Decision history" entry. `User`'s shipped autoincrement PK is documented as a
   **known deviation / migration debt** (PK type, import-codec explicit-id handling,
   `user_id` token claim), not as the convention.
2. **Two-mode export policy** — today's export INCLUDES credentials (secret-grade,
   "full/backup" mode, required by US-002); a sanitized credential-free mode is the
   TARGET for feature 007 (not yet built).
3. **Partial-import rollback = accepted limitation** — streaming idempotent UPSERT;
   corrupt import raises `SetupError`, leaves instance unconfigured, recovered by
   retry; no transactional rollback.

Deferred (not applied here):
- (a) Frontend first-run-wizard / login-entry / `window.location.href` note in
  system-overview.md — pending step 005; a later finalization applies it.
- (b) `US-001.AC-3` min-length `_TBD` → 8 back-propagation — routed to
  `/product-spec`; `docs/product/` left untouched.
