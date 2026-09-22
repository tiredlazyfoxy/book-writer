# Feature 001 — backend-scaffold

| Step | File                                | Status  | Verifier | Date |
|------|-------------------------------------|---------|----------|------|
| 001  | `001.packaging-settings-skeleton.md`| done    | PASS     | 2026-07-21 |
| 002  | `002.db-engine-core.md`             | done    | PASS     | 2026-07-21 |
| 003  | `003.app-factory-health-e2e.md`     | done    | PASS     | 2026-07-21 |
| 004  | `004.import-export-mechanism.md`    | done    | PASS     | 2026-07-21 |

## Files Changed

### Step 001 — Packaging, settings & layer skeleton
- `backend/app/settings.py` — implemented `Settings` (env_file `.env.local`, `BOOKWRITER_DB_PATH`-aliased `db_path`, defaulted `lancedb_dir`) and cached `get_settings()`
- `backend/pyproject.toml` — verified verbatim dependency block (skeleton-written; unchanged)
- `backend/.gitignore` — verified entries (skeleton-written; unchanged)

### Step 002 — Async DB engine & session-free db/ core
- `backend/app/db/engine.py` — implemented `init_engine` (mkdir parent, `sqlite+aiosqlite` async engine, store `_config`/`_engine` singletons), `init_db` (registration hook → `create_all` → try/except additive `ALTER` migration seam, no-op now), `get_standalone_session` (fresh `AsyncSession`, clear `RuntimeError` when uninitialized), and `_register_models` no-op hook with marked seam
- `backend/app/db/health.py` — implemented `ping()` (own session via `get_standalone_session()`, `SELECT 1` probe, returns bool; no session/ORM leak)
- `backend/app/db/vector.py` — implemented `init_vector` (mkdir dir, `lancedb.connect` off-thread, store `_vector_dir`/`_db` singletons)

### Step 003 — App factory, lifespan & health end-to-end
- `backend/app/main.py` — implemented the `lifespan` startup body: `get_settings()` → `DbConfig(db_path=settings.db_path)` → `init_engine` → `init_db` (create_all seam) → `init_vector(settings.lancedb_dir)`; frozen logging/`app`/router wiring untouched (added namespace imports for `db.engine`/`db.vector`/`get_settings`)
- `backend/app/services/health.py` — implemented `check_health()`: awaits `db.health.ping()` and maps the bool onto `HealthResponse` (`ok`/`ready` when True, `error`/`unavailable` when False); no session/`select()`
- `backend/app/routes/health.py` — implemented `get_health()`: delegates to `health_service.check_health()` and returns its `HealthResponse`; HTTP only
- `backend/app/models/schemas/health.py` — verified `HealthResponse` (skeleton-written; unchanged)

### Step 004 — JSONL import/export mechanism hook
- `backend/app/db/import_export_queries.py` — implemented session-free primitives: `export_table` (own session via `engine.get_standalone_session()`, `session.stream(select(...))` per-row, awaits awaitable callbacks, no serialization), `upsert_batch` (empty-batch no-op, `session.merge` per item + single commit), `run_vector_rebuild` (debug-logged no-op hook)
- `backend/app/services/db_import_export.py` — implemented registry-driven serialization: `export_all` (in-memory `zipfile` + per-entry gzip-JSONL member streamed through `export_table`; empty registry yields a valid zero-member zip), `import_all` (namespace `engine.init_db()` first, per-entry gzip-JSONL stream batched to `BATCH_SIZE` via `upsert_batch`, then `run_vector_rebuild()`; empty-registry idempotent no-op that still runs `init_db()`); `TABLE_REGISTRY`/`BATCH_SIZE` left as skeleton-written

## Skeleton

### Step 001 — frozen interface (2026-07-21)
- `backend/app/settings.py` — `class Settings(BaseSettings)` with frozen fields `db_path: Path`, `lancedb_dir: Path` — new. (Coder wires defaults, `env_file=".env.local"`, and the `BOOKWRITER_DB_PATH` override; field names + types are frozen.)
- `backend/app/settings.py` — `get_settings() -> Settings` — new. Returns the shared cached instance; body raises `NotImplementedError`.
- Declarative / non-code source files (no signature to freeze): `backend/pyproject.toml` (written complete — verbatim dependency block incl. `llm-client @ git+...@v0.1.4`), `backend/.gitignore`, and the six package `__init__.py` files (`app`, `app/routes`, `app/services`, `app/db`, `app/models`, `app/models/schemas`) — docstring only, no logic.
- Caller-compile edits (out of Source-files scope): None. (Greenfield step — no existing callers.)

### Step 002 — frozen interface (2026-07-21)
- `backend/app/db/engine.py` — `@dataclass class DbConfig` with fields `db_path: Path` (required), `echo: bool = False` — new. Exact shape per `backend.md`; no default on `db_path` (tests inject it).
- `backend/app/db/engine.py` — `async def init_engine(config: DbConfig) -> None` — new. Body raises `NotImplementedError`.
- `backend/app/db/engine.py` — `async def init_db() -> None` — new. Body raises `NotImplementedError`.
- `backend/app/db/engine.py` — `async def get_standalone_session() -> AsyncSession` — new. The only session primitive `db/` uses; raises when engine uninitialized. Import: `from sqlmodel.ext.asyncio.session import AsyncSession`. Body raises `NotImplementedError`.
- `backend/app/db/engine.py` — `def _register_models() -> None` — new. Empty model-registration hook with a marked seam comment for future `import app.models.*  # noqa: F401` lines. Body raises `NotImplementedError`.
- `backend/app/db/engine.py` — module-level singletons `_config: DbConfig | None = None`, `_engine: AsyncEngine | None = None` (`from sqlalchemy.ext.asyncio import AsyncEngine`) — new.
- `backend/app/db/health.py` — `async def ping() -> bool` — new. Session-free readiness probe returning a plain bool; opens/closes its own session via `get_standalone_session()`. Body raises `NotImplementedError`.
- `backend/app/db/vector.py` — `async def init_vector(vector_dir: Path) -> None` — new. LanceDB connect/init stub against the given directory (fed from `Settings.lancedb_dir`); module-level `_vector_dir: Path | None`, `_db: Any` singletons. Body raises `NotImplementedError`.
- Caller-compile edits (out of Source-files scope): None. (No existing callers of the `db/` core yet; step 003 wires `main.py`/routes to these.)

### Step 003 — frozen interface (2026-07-21)
- `backend/app/models/schemas/health.py` — `class HealthResponse(BaseModel)` with frozen fields `status: str`, `db: str` — new. Declarative schema, written complete (no body to leave unimplemented). Field names + types are the frozen contract the route returns (`{"status": "ok", "db": "ready"}`).
- `backend/app/services/health.py` — `async def check_health() -> HealthResponse` — new. No params; orchestrates readiness by calling `db.health.ping()` (import: `from app.db import health`) and assembling a `HealthResponse`. Body raises `NotImplementedError`.
- `backend/app/routes/health.py` — module-level `router = APIRouter(prefix="/api", tags=["health"])` and `@router.get("/health")` handler `async def get_health() -> HealthResponse` — new. Frozen route path is `GET /api/health` (verified registered via OpenAPI). Uses `from app.services import health as health_service`. Handler body raises `NotImplementedError`.
- `backend/app/main.py` — module-level `app = FastAPI(title="BookWriter Backend", version="0.1.0", lifespan=lifespan)` singleton with `logging.basicConfig(level=DEBUG, ...)` at import, noisy loggers (aiosqlite/httpx/httpcore) quieted to WARNING, and `app.include_router(health.router)` (namespace import `from app.routes import health`) — new/wiring frozen so `app` imports and `/api/health` mounts. `lifespan(app: FastAPI) -> AsyncIterator[None]` (`@asynccontextmanager`) is defined and attached but its startup body raises `NotImplementedError` (coder wires `DbConfig` from `Settings` → `init_engine` → `init_db` → `init_vector`). `.env.local` is loaded via `Settings` (pydantic-settings `env_file`), so no separate dotenv call.
- Caller-compile edits (out of Source-files scope): None. (No existing callers; step 003 is the first to wire `main.py`/routes to the step 001/002 primitives.)

### Step 004 — frozen interface (2026-07-21)
- `backend/app/db/import_export_queries.py` — `async def export_table(model_class: type[T], callback: Callable[[T], None | Awaitable[None]]) -> None` — new. Generic session-free per-row export; `T = TypeVar("T", bound=SQLModel)`; imports `from collections.abc import Awaitable, Callable` and `from sqlmodel import SQLModel`. Body raises `NotImplementedError`.
- `backend/app/db/import_export_queries.py` — `async def upsert_batch(items: list[SQLModel]) -> None` — new. Streaming UPSERT primitive (merge-per-item + single commit). Body raises `NotImplementedError`.
- `backend/app/db/import_export_queries.py` — `async def run_vector_rebuild() -> None` — new. LanceDB rebuild hook (no-op now). Body raises `NotImplementedError`.
- `backend/app/services/db_import_export.py` — `TABLE_REGISTRY: list[RegistryEntry] = []` — new, written complete (empty). **Element/tuple shape (frozen):** `RegistryEntry = tuple[str, type[SQLModel], Callable[[SQLModel], dict[str, object]], Callable[[dict[str, object]], SQLModel]]` = `(zip_filename, model_class, to_dict_fn, from_dict_fn)` in FK dependency (import) order. Extension contract: add one ordered tuple + its codec pair per new persistent model.
- `backend/app/services/db_import_export.py` — `BATCH_SIZE = 100` — new, written complete (module constant).
- `backend/app/services/db_import_export.py` — `async def export_all() -> bytes` — new. Returns a zip archive (`<table>.jsonl.gz` per registry entry, per-row streamed through gzip via `export_table`). Body raises `NotImplementedError`.
- `backend/app/services/db_import_export.py` — `async def import_all(zip_bytes: bytes) -> None` — new. Calls `init_db()` first, streams JSONL per entry, flushes `BATCH_SIZE` batches via `upsert_batch`, then `run_vector_rebuild()`. Param name frozen as `zip_bytes`. Body raises `NotImplementedError`.
- Bound to step 002 engine APIs exactly (`init_db()`, `get_standalone_session()`, `SQLModel.metadata`) — all async; the two service entrypoints are async accordingly. Namespace binding `from app.db import import_export_queries` declared in the service module for the coder.
- Caller-compile edits (out of Source-files scope): None. (New modules; no existing callers — the import/export flow is not yet wired into any route or startup path.)

## Tests

### Step 001 — tests (2026-07-21)
- `backend/tests/test_settings.py` — covers DoD-1 — `Settings().db_path` reflects the `BOOKWRITER_DB_PATH` env override
- `backend/tests/test_settings.py` — covers DoD-2 — `Settings().db_path` falls back to the dev default `backend/data/bookwriter.db` when the env var is unset
- `backend/tests/test_settings.py` — covers DoD-3 — `get_settings()` returns the same shared instance across calls
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 [manual/live, no test], DoD-5 [manual/live, no test]

### Step 002 — tests (2026-07-21)
- `backend/tests/conftest.py` — created; non-autouse async `db` fixture builds a throwaway temp-SQLite `DbConfig`, calls `init_engine` + `init_db`, yields the config (each requesting test gets an isolated DB). No `event_loop` override; relies on `asyncio_mode="auto"`. Left room for step-003's `http_client` fixture.
- `backend/tests/db/test_engine.py` — covers DoD-1 — repeated `init_db()` after fixture init is a safe idempotent no-op leaving the DB ready (`ping()` True)
- `backend/tests/db/test_engine.py` — covers DoD-2 — `ping()` returns `True` once the engine is initialized
- `backend/tests/db/test_engine.py` — covers DoD-3 — `get_standalone_session()` raises a non-placeholder error when engine singletons are reset to `None` (uninitialized)
- `backend/tests/db/test_engine.py` — covers DoD-4 — `init_engine`+`init_db` against an injected `DbConfig.db_path` materializes the SQLite file at exactly that path
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 [manual/live, no test]

### Step 003 — tests (2026-07-21)
- `backend/tests/conftest.py` — extended; added non-autouse async `http_client` fixture wrapping `app.main.app` in `httpx.ASGITransport`, yielding `httpx.AsyncClient(base_url="http://test")` in-process (no network). Sets `BOOKWRITER_DB_PATH` to a temp path and clears the cached `Settings` before driving the app's startup lifespan explicitly via `app.router.lifespan_context(app)` (httpx ASGITransport does not emit lifespan events; no `asgi-lifespan` dep), so startup really runs against a throwaway DB and never touches the real `backend/data/bookwriter.db`. Step-002 `db` fixture left intact.
- `backend/tests/routes/test_health.py` — covers DoD-1 — `GET /api/health` returns HTTP 200 with body exactly `{"status": "ok", "db": "ready"}`, in-process via `http_client`.
- `backend/tests/routes/test_health.py` — covers DoD-2 — response conforms to the `HealthResponse` schema (keys exactly `{status, db}`, both str, re-validates through the model; happy-path values `ok`/`ready`).
- `backend/tests/routes/test_health.py` — covers DoD-2 — readiness reflects an actually-initialized DB: within the running lifespan `db.health.ping()` is `True` and the endpoint reports `db == "ready"`.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 [manual/live, no test]
- Limitation: black-box HTTP cannot fully distinguish a `ping()`-derived `"ready"` from a route-hardcoded constant. Per the brief, tests cover the observable contract (200 + exact body + schema fields) and corroborate readiness against the real initialized DB via the public `ping()` probe, but a pure black-box test cannot prove the value originated from `ping()` rather than a literal.

### Step 004 — tests (2026-07-21)
- `backend/tests/services/test_db_import_export.py` — covers DoD-1 — `export_all()` over the empty registry returns `bytes` that open as a valid zip (via stdlib `zipfile`) with zero entries; asserts `TABLE_REGISTRY` empty as the spec precondition
- `backend/tests/services/test_db_import_export.py` — covers DoD-2 — `import_all(export_all())` completes without error and re-importing is an idempotent no-op; DB stays usable (`ping()` True)
- `backend/tests/services/test_db_import_export.py` — covers DoD-2 — `import_all()` invokes `init_db()` as part of its flow, asserted via a spy on the public `app.db.engine.init_db` (observable effect insufficient: empty registry creates no tables)
- `backend/tests/services/test_db_import_export.py` — covers DoD-3 — empty-archive round-trip leaves the DB usable (`ping()` True) and is safe to re-run
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 [manual/live, no test]
- Note: no `tests/services/__init__.py` created — sibling suites (`tests/db`, `tests/routes`) collect without one, so it is not needed for collection.

## Notes & Issues
- Step 001: Python 3.13 is not installed on this machine (only 3.11/3.14 via `py`); provisioned `backend/.venv` with `py -3.14` — 3.14 satisfies `requires-python = ">=3.13"`. Editable install `-e .[dev]` succeeded, including the `llm-client @ git+...@v0.1.4` git dep (built `llm_client-0.1.4`). Import smoke of all six packages passed.
- Step 001: dev-default `db_path`/`lancedb_dir` are anchored absolutely off `settings.py`'s location (mirrors the reference project's `Path(__file__).resolve()` pattern), so they resolve to `backend/data/bookwriter.db` and `backend/data/vector` regardless of CWD.
