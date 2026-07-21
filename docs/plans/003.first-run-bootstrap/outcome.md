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
