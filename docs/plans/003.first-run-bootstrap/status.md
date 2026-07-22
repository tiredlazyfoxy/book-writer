# Feature 003 — first-run-bootstrap

| Step | File                                      | Status  | Verifier | Date |
|------|-------------------------------------------|---------|----------|------|
| 001  | `001.user-model-auth-primitives.md`       | done    | PASS     | 2026-07-22 |
| 002  | `002.unconfigured-detection-startup.md`   | done    | PASS     | 2026-07-22 |
| 003  | `003.setup-service-user-codec.md`         | done    | PASS     | 2026-07-22 |
| 004  | `004.setup-routes-schemas.md`             | done    | PASS     | 2026-07-22 |
| 005  | `005.frontend-first-run-wizard.md`        | pending | —        | —    |

## Files Changed

### Step 001 — User model, db/users layer, auth primitives
- `backend/app/models/user.py` — `UserRole` enum + `User` SQLModel table (frozen shape; already declarative, no change needed).
- `backend/app/db/users.py` — session-free access layer: `create`, `get_by_username`, `get_by_id`, `admin_exists` (catches missing-table `OperationalError` → `False`).
- `backend/app/services/auth.py` — bcrypt `hash_password`/`verify_password`, `generate_signing_key`, per-user HS256 `create_token`.

### Step 002 — Unconfigured detection + startup lifespan amendment
- `backend/app/db/engine.py` — readiness flag `is_db_ready`/`set_db_ready` and `_register_models` importing `app.models.user` verified complete as frozen (no change needed beyond skeleton).
- `backend/app/main.py` — lifespan amended: removed eager `init_db`/`create_all`, added startup readiness detection via `users.admin_exists()` → `db_engine.set_db_ready(...)`; engine + vector init preserved; docstrings updated.

### Step 003 — Setup service + User import/export codec
- `backend/app/services/setup.py` — implemented `create_database` (already-configured → min-length → mismatch guards, then `init_db`/hash/signing-key/`users.create`/`set_db_ready`, returns admin) and `import_database` (wraps `db_import_export.import_all`; corrupt archive → `SetupError` without flipping readiness; success → `set_db_ready(True)`).
- `backend/app/services/db_import_export.py` — implemented `_user_to_dict`/`_dict_to_user` codec pair (role via `.value`/`UserRole(...)`, datetimes via isoformat, nullable via `.get`, credentials included, id preserved); registry tuple wiring left intact.

### Step 004 — Setup routes + schemas (HTTP surface)
- `backend/app/routes/auth.py` — implemented the three handler bodies: `GET /status` → `AuthStatusResponse(needs_setup=not is_db_ready())`; `POST /setup/create` calls `setup_service.create_database` then mints `auth_service.create_token(admin)` → `LoginResponse`, mapping `SetupError` → HTTP 400; `POST /setup/import` reads the multipart `file` bytes, calls `setup_service.import_database`, returns `AuthStatusResponse`, mapping `SetupError` → HTTP 400. Added `HTTPException` import.
- `backend/app/models/schemas/auth.py` — verified complete as frozen by skeleton (three BaseModel schemas); no change needed.
- `backend/app/main.py` — verified the `app.include_router(auth.router)` mount + `from app.routes import auth` import already present (added by skeleton); step-002 lifespan untouched; no change needed.

## Skeleton

### Step 001 — frozen interface (2026-07-22)

`backend/app/models/user.py` (new):
- `class UserRole(str, enum.Enum)` — members `admin = "admin"`, `author = "author"`.
- `class User(SQLModel, table=True)` — `__tablename__ = "users"`; fields:
  - `id: int | None = Field(default=None, primary_key=True)` (autoincrement)
  - `username: str = Field(unique=True, index=True)`
  - `pwdhash: str | None = Field(default=None)` (null = disabled)
  - `role: UserRole` (required, no default)
  - `jwt_signing_key: str | None = Field(default=None)`
  - `last_login: datetime | None = Field(default=None)`
  - `last_key_update: datetime | None = Field(default=None)`
  - No `salt` column; no `disabled` bool; no logic.

`backend/app/db/users.py` (new) — session-free, sessions opened internally:
- `async def create(user: User) -> User`
- `async def get_by_username(username: str) -> User | None`
- `async def get_by_id(user_id: int) -> User | None`
- `async def admin_exists() -> bool` (returns `False` gracefully when `users` table is missing)

`backend/app/services/auth.py` (new) — no session/select:
- `def hash_password(password: str) -> str`
- `def verify_password(password: str, pwdhash: str) -> bool`
- `def generate_signing_key() -> str`
- `def create_token(user: User) -> str` (per-user HS256; payload `user_id`, `username`, `role`, `exp` ~30d)

- Caller-compile edits (out of Source-files scope): None. All three files are new (001 create); no existing callers.

### Step 002 — frozen interface (2026-07-22)

`backend/app/db/engine.py` (amended — 001 file):
- `_db_ready: bool = False` — new module-level readiness flag (default `False`).
- `def is_db_ready() -> bool` — new; returns the current flag value.
- `def set_db_ready(value: bool) -> None` — new; sets the flag (getter/setter over the module global; implemented as the frozen interface, not a stub).
- `def _register_models() -> None` — changed (was: empty hook, `return` only). Now imports `app.models.user  # noqa: F401` so the `User` table registers on `SQLModel.metadata` before any `create_all`. `init_db()` itself is unchanged and still only runs on demand.

`backend/app/main.py` (amended — 001 file):
- No new signatures. The `app` singleton and `lifespan(app: FastAPI) -> AsyncIterator[None]` signature are intact and the module imports cleanly. The step's change here is purely behavioral (remove eager `init_db`, add `admin_exists()` → `set_db_ready(...)` detection inline in the lifespan) and belongs to the coder. Left untouched at skeleton time: the eager `init_db()` remains, so the deferred-schema behavior is correctly unimplemented (DoD-3 fails red until the coder removes it). No new helpers introduced.

- Caller-compile edits (out of Source-files scope): None. `is_db_ready`/`set_db_ready` are additive; the `_register_models` extension is internal to `db/engine.py`.

### Step 003 — frozen interface (2026-07-22)

`backend/app/services/setup.py` (new) — service layer, no `session`/`select()`:
- `class SetupError(Exception)` — new; typed refusal exception carrying a human-readable message (declarative subclass, implemented as the frozen interface, not a stub). Raised for every setup refusal (already-configured, password too short, mismatch, corrupt import).
- `MIN_PASSWORD_LENGTH = 8` — new module constant (decision 7; backs US-001.AC-3 validation).
- `async def create_database(admin_username: str, password: str, password_confirm: str) -> User` — new; body raises `NotImplementedError`. Returns the created `admin`-role `User`.
- `async def import_database(archive_bytes: bytes) -> None` — new; body raises `NotImplementedError`.

`backend/app/services/db_import_export.py` (amended — 001 file):
- `def _user_to_dict(user: User) -> dict[str, object]` — new codec (row→dict); body raises `NotImplementedError`. Param/return match the `RegistryEntry` `to_dict_fn` slot (`Callable[[SQLModel], dict[str, object]]`) that `export_all` invokes.
- `def _dict_to_user(data: dict[str, object]) -> User` — new codec (dict→row); body raises `NotImplementedError`. Param/return match the `RegistryEntry` `from_dict_fn` slot (`Callable[[dict[str, object]], SQLModel]`) that `import_all` invokes.
- `TABLE_REGISTRY: list[RegistryEntry]` — changed (was `[]`). Now `[("users", User, _user_to_dict, _dict_to_user)]` — the `users` tuple is the first (FK-order) entry; this tuple is REAL (references the frozen codec functions) so the registry is non-empty and importable. `export_all`/`import_all`/`BATCH_SIZE` unchanged.
- Added import `from app.models.user import User`.

- Caller-compile edits (out of Source-files scope): None. `setup.py` is new; the codec pair + registry entry are additive and no external code references `TABLE_REGISTRY` or the codecs.

### Step 004 — frozen interface (2026-07-22)

`backend/app/models/schemas/auth.py` (new) — Pydantic `BaseModel` schemas, no logic:
- `class AuthStatusResponse(BaseModel)` — field `needs_setup: bool`.
- `class CreateDBRequest(BaseModel)` — fields `admin_username: str`, `password: str`, `password_confirm: str`.
- `class LoginResponse(BaseModel)` — field `token: str`.

`backend/app/routes/auth.py` (new) — HTTP-only; `router = APIRouter(prefix="/api/auth", tags=["auth"])` (importable + mountable). Handler bodies raise `NotImplementedError`; return annotations set the `response_model`:
- `GET /api/auth/status` → `async def get_status() -> AuthStatusResponse`.
- `POST /api/auth/setup/create` → `async def create_db(payload: CreateDBRequest) -> LoginResponse`.
- `POST /api/auth/setup/import` → `async def import_db(file: UploadFile = File(...)) -> AuthStatusResponse` (multipart; field name `file`).
- Namespace imports frozen for the coder: `from app.db.engine import is_db_ready`, `from app.services import auth as auth_service`, `from app.services import setup as setup_service`.

`backend/app/main.py` (amended — 001 file):
- No new signatures. Added `from app.routes import auth` and a bare `app.include_router(auth.router)` after the health mount. The step-002 lifespan is untouched. Verified: OpenAPI resolves `/api/auth/status` (GET), `/api/auth/setup/create` (POST), `/api/auth/setup/import` (POST).

- Caller-compile edits (out of Source-files scope): None. All three routes are new/additive; `main.py` is in this step's Source files.

## Tests

### Step 001 — tests (2026-07-22)
- `backend/tests/services/test_auth.py` — covers DoD-1, DoD-2 — hash/verify round-trip (True correct, False wrong); create_token decodes with the user's own signing key to a payload carrying user_id and role.
- `backend/tests/db/test_users.py` — covers DoD-3, DoD-4, DoD-5 — create+get_by_username round-trips username and role; admin_exists reflects admin-role presence (False none / False author-only / True admin); admin_exists returns False gracefully against a missing `users` table (engine init without init_db).
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓

### Step 002 — tests (2026-07-22)
- `backend/tests/test_startup_detection.py` — covers DoD-1, DoD-2, DoD-3 — cold instance (engine, no init_db) reports is_db_ready()/admin_exists() both False; after schema + admin, set_db_ready(True) flips is_db_ready() True; startup lifespan leaves the `users` table absent (deferred schema).
- `backend/tests/conftest.py` — extended with an autouse `_reset_db_ready` fixture that calls `set_db_ready(False)` before each test (supports isolation for all step 002 tests; no DoD of its own).
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 [manual/live, no test]

### Step 003 — tests (2026-07-22)
- `backend/tests/services/test_setup.py` — covers DoD-1..DoD-7:
  - DoD-1 — create_database with valid creds builds schema, persists an admin user, returned admin has id + signing key, is_db_ready() True.
  - DoD-2 — with is_db_ready() set True (+ seeded admin), create_database raises SetupError and the attempted second admin never persists.
  - DoD-3 — sub-8-char password raises SetupError, is_db_ready() stays False, no admin created.
  - DoD-4 — password != confirm raises SetupError, is_db_ready() stays False, no admin created.
  - DoD-5 — import_database of a valid export_all() archive restores the user and flips is_db_ready() True.
  - DoD-6 — import_database(b"not a zip") raises SetupError, is_db_ready() stays False.
  - DoD-7 — users codec round-trips through export_all/import_all (username, role, pwdhash, jwt_signing_key survive) and re-import is idempotent (same id, no duplication).
- `backend/tests/services/test_db_import_export.py` — covers DoD-8 (amendment) — reconciled the feature-001 mechanism test to the now-registered `users` codec: `test_export_all_includes_registered_users_member__F003_DoD8` asserts `TABLE_REGISTRY` is non-empty with the `users` entry first (zip_filename `"users"`, model_class `User`) and `export_all()` yields an archive whose `namelist() == ["users"]` for a no-user-rows DB; retagged/renamed off the retired empty-registry precondition and module docstring updated. The three emptiness-independent tests (init_db invocation, empty-import idempotency, empty-archive round-trip) are preserved unchanged.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓

### Step 004 — tests (2026-07-22)
- `backend/tests/routes/test_setup.py` — covers DoD-1..DoD-7, all in-process via the `http_client` ASGITransport fixture:
  - DoD-1 — `GET /api/auth/status` returns `{needs_setup: true}` on a cold instance and `{needs_setup: false}` after a successful `POST /setup/create`.
  - DoD-2 (US-001.AC-1) — `POST /setup/create` with valid creds (password >= 8, matching confirm) returns HTTP 200 and a LoginResponse with a non-empty `token`.
  - DoD-3 (US-001.AC-2) — a second `POST /setup/create` after one succeeds (already-configured) is refused with a 4xx (not 200).
  - DoD-4 (US-001.AC-3) — `POST /setup/create` with a 7-char password returns HTTP 400 and no `token` in the body.
  - DoD-5 (US-001.AC-4) — `POST /setup/create` with password != password_confirm returns HTTP 400 and no `token` in the body.
  - DoD-6 (US-002.AC-1) — `POST /setup/import` (multipart `file`) with a valid archive (seeded user + `export_all()` in test setup) returns HTTP 200, `needs_setup: false`, and no `token`.
  - DoD-7 (US-002.AC-2) — `POST /setup/import` with `b"not a zip"` returns HTTP 400, and a subsequent `GET /status` still reports `{needs_setup: true}`.
- `backend/tests/__init__.py`, `backend/tests/db/__init__.py`, `backend/tests/services/__init__.py`, `backend/tests/routes/__init__.py` — covers DoD-8 (amendment) — empty package markers (zero code) that make the `tests/` tree a package so the two same-basename modules `tests.routes.test_setup` and `tests.services.test_setup` are fully-qualified and coexist under the declared full-suite command (`cd backend && .venv/Scripts/python -m pytest`, pytest prepend import mode) with no `import file mismatch` collection error. The full-suite verify run confirms collection is clean.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓

## Notes & Issues

_populated by the coder when worth saying_
