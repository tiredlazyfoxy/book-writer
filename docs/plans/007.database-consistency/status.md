# Feature 007 — database-consistency

| Step | File                               | Status  | Verifier | Date |
|------|------------------------------------|---------|----------|------|
| 001  | `001.schema-introspection-report.md` | done    | PASS     | 2026-07-23 |
| 002  | `002.remediation-create-sync.md`     | done    | PASS     | 2026-07-23 |
| 003  | `003.export-import-service.md`        | done    | PASS     | 2026-07-23 |
| 004  | `004.vector-rebuild.md`               | done    | PASS     | 2026-07-23 |
| 005  | `005.admin-db-routes-wiring.md`       | done    | PASS     | 2026-07-23 |
| 006  | `006.frontend-api-types.md`           | done    | PASS     | 2026-07-23 |
| 007  | `007.frontend-database-page.md`       | done    | PASS     | 2026-07-23 |

## Files Changed

### Step 001 — Schema introspection + drift report
- `backend/app/db/schema.py` — `introspect()` reflects live table/column structure via `inspect()` under `run_sync`
- `backend/app/services/db_admin.py` — `build_consistency_report()` diffs `SQLModel.metadata` against live structure into ok/drift/missing entries
- `backend/app/models/schemas/db_admin.py` — report DTOs (frozen skeleton; no body changes needed)

### Step 002 — Remediation: create-missing-table + sync-schema
- `backend/app/db/schema.py` — `create_table` (single-table `table.create` under `begin`/`run_sync`), `add_columns` (nullable `ALTER … ADD COLUMN` with SQLite-compiled types), `drop_columns` (`ALTER … DROP COLUMN`); shared `_exec_statements` helper + reusable `_sqlite_dialect`
- `backend/app/services/db_admin.py` — `create_missing_table` (metadata + absence preconditions → typed refusals) and `sync_table_schema` (reuses `build_consistency_report`, adds missing / drops extra columns)

### Step 003 — Admin export/import service + archive validation
- `backend/app/services/db_admin.py` — `export_database` (passthrough to `db_import_export.export_all`), `validate_archive` (in-memory zip + per-`TABLE_REGISTRY`-member gz + JSONL pre-validation → `DbAdminError(invalid_archive)`, no writes), `import_database` (validate-then-`import_all`, no `set_db_ready`); added `io`/`zipfile`/`gzip`/`json` imports + `db_import_export` namespace import

### Step 004 — Vector-index rebuild operation + empty source seam
- `backend/app/db/vector.py` — `rebuild_index()` ensures a live `_db` (reuse or lazy `init_vector(get_settings().lancedb_dir)`), drops every existing sidecar table via `asyncio.to_thread` (idempotent `ignore_missing`), iterates the empty `VECTOR_SOURCE_REGISTRY`, returns rows indexed (0 in Stage 1)
- `backend/app/db/import_export_queries.py` — `run_vector_rebuild()` now delegates to `vector.rebuild_index()` (shared post-import/admin path), discarding the returned count
- `backend/app/services/db_admin.py` — `rebuild_vector_index()` resolves `llm_servers.get_embedding_server()`, raises `DbAdminError(no_embedding_provider)` when absent or `embedding_model` unset, else returns `vector.rebuild_index()`; added `llm_servers`/`vector` namespace imports

### Step 005 — Admin DB routes + main wiring (HTTP surface)
- `backend/app/routes/admin/db.py` — filled the 6 frozen handler bodies: `get_report` returns `db_admin.build_consistency_report()`; `export_database` wraps `db_admin.export_database()` bytes in a `Response` (`application/zip` + `Content-Disposition: attachment`); `import_database` reads the multipart `file` and calls `db_admin.import_database` under `try/except → _map_db_admin_error`; `rebuild_vector_index` returns `VectorRebuildResponse(indexed_rows=...)`; `create_missing_table`/`sync_table_schema` delegate to their services — all typed refusals routed through the frozen error map

### Step 006 — Frontend db types + api (blob-download & multipart plumbing)
- `frontend/src/types/db.d.ts` — wire DTOs mirroring `db_admin.py` 1:1: `TableStatus` union, `TableReportEntry`, `ConsistencyReport`, `VectorRebuildResponse`
- `frontend/src/api/db.ts` — `/api/admin/db` resource module: `getConsistencyReport`/`createTable`/`syncTable`/`rebuildIndex` over shared `request<T>`; `exportDatabase` (net-new blob download: Bearer fetch → `res.blob()` → object-URL anchor save/revoke); `importDatabase` (net-new multipart mirroring `setupImport`, rejects on non-2xx)

### Step 007 — Admin SPA Database page + nav
- `frontend/src/admin/pages/databasePageState.ts` — `DatabasePageState` (report trio + `actionError`/`rebuildResult`, `makeAutoObservable`); external effect fns `loadReport`/`createTableAction`/`syncTableAction`/`importAction`/`rebuildAction`/`exportAction` with `runInAction` (friendly-fallback catches → `actionError` so `void`-invoked effects never leak)
- `frontend/src/admin/pages/DatabasePage.tsx` — `observer` page: mount-load/unmount-abort `useEffect`, component-local `importFile` `useState`, consistency table (status badge + drift column lists, per-row Create/Sync), Export/Import/Rebuild controls, inline report/action errors, rebuild-result line
- `frontend/src/admin/routes.tsx` — added `/database` route → `DatabasePage`
- `frontend/src/admin/App.tsx` — added `Database` nav link after LLM Servers

## Skeleton

### Step 001 — frozen interface (2026-07-23)
- `backend/app/db/schema.py` — `class TableStructure(TypedDict)` — new — fields: `name: str`, `columns: dict[str, str]` (live column name -> reflected type as string)
- `backend/app/db/schema.py` — `class DbStructure(TypedDict)` — new — field: `tables: dict[str, TableStructure]` (live table name -> its structure)
- `backend/app/db/schema.py` — `async def introspect() -> DbStructure` — new (session-free; opens/closes its own connection via `engine._engine`)
- `backend/app/models/schemas/db_admin.py` — `class TableReportEntry(BaseModel)` — new — fields: `name: str`, `status: Literal['ok','drift','missing']`, `missing_columns: list[str]`, `extra_columns: list[str]`
- `backend/app/models/schemas/db_admin.py` — `class ConsistencyReport(BaseModel)` — new — field: `tables: list[TableReportEntry]`
- `backend/app/services/db_admin.py` — `class DbAdminErrorCase(str, enum.Enum)` — new — closed set: `not_in_metadata="not-in-metadata"`, `unknown_table="unknown-table"`, `table_not_missing="table-not-missing"`, `invalid_archive="invalid-archive"`, `no_embedding_provider="no-embedding-provider"` (only report/validation cases raised this step; remainder reserved for steps 002–004)
- `backend/app/services/db_admin.py` — `class DbAdminError(Exception)` — new — `__init__(self, case: DbAdminErrorCase, message: str = "") -> None`; attributes `.case`, `.message`
- `backend/app/services/db_admin.py` — `async def build_consistency_report() -> ConsistencyReport` — new
- Caller-compile edits (out of Source-files scope): None.

### Step 002 — frozen interface (2026-07-23)
- `backend/app/db/schema.py` — `async def create_table(name: str) -> None` — new (session-free DDL; creates one table from `SQLModel.metadata.tables[name]` via `table.create(sync_conn)` under `engine._engine.begin()`/`run_sync`)
- `backend/app/db/schema.py` — `async def add_columns(name: str, columns: Sequence[str]) -> None` — new (`collections.abc.Sequence`; per column `ALTER TABLE <name> ADD COLUMN <col> <compiled-type>` using the metadata column type compiled against the SQLite dialect, e.g. `col.type.compile(dialect=sqlite.dialect())`; columns added **nullable** — D2; session-free via `engine._engine.begin()`/`run_sync`)
- `backend/app/db/schema.py` — `async def drop_columns(name: str, columns: Sequence[str]) -> None` — new (per column `ALTER TABLE <name> DROP COLUMN <col>`; session-free via `engine._engine.begin()`/`run_sync`)
- `backend/app/services/db_admin.py` — `async def create_missing_table(name: str) -> None` — new (validates `name` in `SQLModel.metadata` → else `DbAdminError(not_in_metadata)`; validates currently absent per `schema.introspect()` → else `DbAdminError(table_not_missing)`; on success calls `schema.create_table(name)`)
- `backend/app/services/db_admin.py` — `async def sync_table_schema(name: str) -> None` — new (reuses step-001 `build_consistency_report()` and selects the entry for `name`; calls `schema.add_columns(name, entry.missing_columns)` + `schema.drop_columns(name, entry.extra_columns)`; raises `DbAdminError(unknown_table)` if `name` is not in metadata or missing entirely from the live DB)
- Diff reuse: `sync_table_schema` binds to the frozen step-001 `build_consistency_report()` — no new shared helper frozen, no step-001 signature changed.
- Caller-compile edits (out of Source-files scope): None.

### Step 003 — frozen interface (2026-07-23)
- `backend/app/services/db_admin.py` — `async def export_database() -> bytes` — new (passthrough to `db_import_export.export_all()`; no transformation)
- `backend/app/services/db_admin.py` — `async def validate_archive(archive_bytes: bytes) -> None` — new (opens `archive_bytes` as a zip via `zipfile`; for each `db_import_export.TABLE_REGISTRY` entry confirms member name `entry[0]` — bare table name, never extension-appended — is present, gz-decodable, JSONL-parseable; any failure → `DbAdminError(DbAdminErrorCase.invalid_archive)`; no writes)
- `backend/app/services/db_admin.py` — `async def import_database(archive_bytes: bytes) -> None` — new (calls `validate_archive(archive_bytes)` first, then `db_import_export.import_all(archive_bytes)`; MUST NOT call `set_db_ready` — D4; returns `None`)
- Param name `archive_bytes` shared across `validate_archive`/`import_database`. Reuses frozen step-001 `DbAdminError` / `DbAdminErrorCase.invalid_archive` — no step-001/002 signature changed.
- Caller-compile edits (out of Source-files scope): None.

### Step 004 — frozen interface (2026-07-23)
- `backend/app/db/vector.py` — `VECTOR_SOURCE_REGISTRY: list[tuple[type, Callable[..., str]]] = []` — new (module-level; `collections.abc.Callable`; entry type `(model_class, text_extractor)`; **empty in Stage 1** — the Stage-2 embedding seam; do NOT add users/llm_servers)
- `backend/app/db/vector.py` — `async def rebuild_index() -> int` — new — body UNIMPLEMENTED (`raise NotImplementedError`). **Connection contract (frozen):** reuse module `_db` if already initialized, else lazily `await init_vector(get_settings().lancedb_dir)` (`from app.settings import get_settings`). Resets (drops/recreates) the sidecar index tables, iterates `VECTOR_SOURCE_REGISTRY`, returns rows indexed. Stage-1 empty registry → returns `0`.
- `backend/app/services/db_admin.py` — `async def rebuild_vector_index() -> int` — new — body UNIMPLEMENTED (`raise NotImplementedError`). **No-provider contract = OPTION (a) RAISE (frozen):** resolve `server = await llm_servers.get_embedding_server()`; if `server is None` OR `server.embedding_model` is falsy → `raise DbAdminError(DbAdminErrorCase.no_embedding_provider, <msg>)`; else `await vector.rebuild_index()` and return the count. Coder adds `from app.db import vector` and `from app.db import llm_servers`. (Rationale: post-import reset flows through `run_vector_rebuild → vector.rebuild_index` directly, not this gated method, so raising here does not harm post-import correctness.)
- `backend/app/db/import_export_queries.py` — `async def run_vector_rebuild() -> None` — **unchanged / frozen** (from feature 001). Signature NOT changed. Body left as the existing log-noop (preserves the green step-003 import tests); the coder adds `from app.db import vector` and makes the body `await vector.rebuild_index()`. The delegation is intentionally absent in the skeleton so DoD-4's monkeypatch red-gate fails for the right reason.
- **Test-setup mechanism for a temp LanceDB dir (frozen — brief the test-coder):** a test points LanceDB at a throwaway directory by calling `await vector.init_vector(tmp_path / "vector")` BEFORE invoking `db_admin.rebuild_vector_index()` / `vector.rebuild_index()`. `rebuild_index` reuses the pre-initialized module `_db`, so no settings monkeypatch is required. Tests monkeypatch `llm_servers.get_embedding_server` for the designated/none cases and `vector.rebuild_index` for the delegation assertion.
- Caller-compile edits (out of Source-files scope): None. No prior frozen signature changed; `settings.py` untouched.

### Step 005 — frozen interface (2026-07-23)
- `backend/app/models/schemas/db_admin.py` — `class VectorRebuildResponse(BaseModel)` — new — field: `indexed_rows: int` (planner-sanctioned rebuild-count wrapper for the `int` from `rebuild_vector_index()`)
- `backend/app/routes/admin/db.py` — `router = APIRouter(prefix="/api/admin/db", tags=["admin-db"])` — new module; NO router-level dependencies (admin gate is per-endpoint)
- `backend/app/routes/admin/db.py` — `_DB_ADMIN_ERROR_STATUS: dict[db_admin.DbAdminErrorCase, int]` + `def _map_db_admin_error(err: db_admin.DbAdminError) -> HTTPException` — new — REAL (branch on `.case`): `HTTPException(status_code=_DB_ADMIN_ERROR_STATUS[err.case], detail=err.message)`
- Handler bodies are all `raise NotImplementedError` (routes RESOLVE → 500 under test, not 404). Admin gate wired per-endpoint via `caller: User = Depends(auth_service.require_role(UserRole.admin))`.

Frozen route table (verb — path — success status — return type — error-case→status):
- `GET  /api/admin/db/report` — 200 — `-> ConsistencyReport` — (no error map) — `async def get_report(caller: User = Depends(auth_service.require_role(UserRole.admin))) -> ConsistencyReport`
- `GET  /api/admin/db/export` — 200 — `-> Response` (zip; `media_type="application/zip"`, `Content-Disposition: attachment; filename="bookwriter-export.zip"`; NO response_model) — `async def export_database(caller: User = Depends(...)) -> Response`
- `POST /api/admin/db/import` — 204 — `-> None` — multipart `file: UploadFile = File(...)`; `invalid_archive` → 400 — `async def import_database(file: UploadFile = File(...), caller: User = Depends(...)) -> None`
- `POST /api/admin/db/vector/rebuild` — 200 — `-> VectorRebuildResponse` — `no_embedding_provider` → 400 — `async def rebuild_vector_index(caller: User = Depends(...)) -> VectorRebuildResponse`
- `POST /api/admin/db/tables/{name}/create` — 204 — `-> None` — `name: str`; `not_in_metadata`/`table_not_missing` → 400 — `async def create_missing_table(name: str, caller: User = Depends(...)) -> None`
- `POST /api/admin/db/tables/{name}/sync` — 204 — `-> None` — `name: str`; `unknown_table` → 404 — `async def sync_table_schema(name: str, caller: User = Depends(...)) -> None`

Error-case → status map (frozen, module-level dict): `not_in_metadata` → 400, `table_not_missing` → 400, `invalid_archive` → 400, `no_embedding_provider` → 400, `unknown_table` → 404. Static paths declared BEFORE the `/tables/{name}/...` param paths.
- `backend/app/main.py` — added `from app.routes.admin import db as admin_db` + `app.include_router(admin_db.router)` (one import + one include; composition root)
- `backend/app/routes/admin/__init__.py` — no change needed (docstring-only package marker; does not aggregate — confirmed)
- Caller-compile edits (out of Source-files scope): None. No prior frozen signature changed.

## Tests

### Step 001 — tests (2026-07-23)
- `backend/tests/services/test_db_admin_report.py` — covers DoD-1, DoD-2, DoD-3, DoD-4 — asserts `build_consistency_report()` per-table status (ok/missing/drift) and drift column diffs against `SQLModel.metadata`
  - `test_all_match__DoD1_US015_AC1` — DoD-1: clean DB → entry for every metadata table, status `ok`, empty diff lists
  - `test_missing_table__DoD2_US015_AC1` — DoD-2: dropped table → status `missing`, empty diff lists
  - `test_drift_status__DoD3_US015_AC1` — DoD-3: extra column via raw ALTER → status `drift`
  - `test_drift_extra_column_diff__DoD4_US015_AC2` — DoD-4: `extra_columns` = added col, `missing_columns` empty, disjoint
  - `test_drift_missing_and_extra_column_diffs__DoD4_US015_AC2` — DoD-4: table rewritten to one unknown column → `missing_columns` = all metadata cols, `extra_columns` = probe col, disjoint
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 [manual/live, no test]

### Step 002 — tests (2026-07-23)
- `backend/tests/services/test_db_admin_remediation.py` — covers DoD-1, DoD-2, DoD-3, DoD-4 — asserts remediation (`create_missing_table` / `sync_table_schema`) then verifies post-state via a fresh `build_consistency_report()`; scenarios seeded with raw DDL against `engine._engine`, expected structure read from `SQLModel.metadata`
  - `test_create_missing__DoD1_US016_AC1` — DoD-1: dropped table (reports `missing`) → `create_missing_table` → fresh report shows `ok`, empty diffs
  - `test_create_missing_unknown_name_rejected__DoD2_US016` — DoD-2: bogus name → `DbAdminError` case `not_in_metadata`; report snapshot unchanged
  - `test_create_missing_already_present_rejected__DoD2_US016` — DoD-2: existing table → `DbAdminError` case `table_not_missing`; report snapshot unchanged
  - `test_sync_adds_missing_columns__DoD3_US017_AC1` — DoD-3: table rebuilt to one metadata column (drift, missing cols) → `sync_table_schema` → fresh report lists no `missing_columns`
  - `test_sync_drops_extra_columns__DoD4_US017_AC2` — DoD-4: extra column via raw ALTER (drift, extra col) → `sync_table_schema` → fresh report shows `ok`, extra dropped
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 [manual/live, no test]

### Step 003 — tests (2026-07-23)
- `backend/tests/services/test_db_admin_importexport.py` — covers DoD-1, DoD-2, DoD-3, DoD-4, DoD-5 — asserts `export_database()` ZIP shape (members derived from `db_import_export.TABLE_REGISTRY`), self-produced round-trip restore + idempotent double-import, corrupt-archive refusal with `DbAdminError(invalid_archive)` + DB-unchanged, and readiness-flag invariance across a successful import; rows seeded via the db `users` layer against the `db` conftest temp DB
  - `test_export_returns_valid_zip__DoD1_US018_AC1` — DoD-1: export returns non-empty bytes opening as a valid ZIP; every derived `TABLE_REGISTRY` member name in `namelist()`
  - `test_import_restores_rows__DoD2_US019_AC1` — DoD-2: seed → export → import → seeded row present via `users.get_by_username`
  - `test_import_is_idempotent__DoD3_US019_AC2` — DoD-3: single-row export imported twice → `len(users.get_all())` stays 1
  - `test_import_corrupt_archive_rejected__DoD4_US019_AC3` — DoD-4: non-zip bytes → `DbAdminError` case `invalid_archive`; row count unchanged (no partial write)
  - `test_import_does_not_flip_readiness__DoD5_D4` — DoD-5: `is_db_ready()` identical before/after a successful import
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓

### Step 004 — tests (2026-07-23)
- `backend/tests/services/test_db_admin_rebuild.py` — covers DoD-1, DoD-2, DoD-3, DoD-4, DoD-5 — asserts vector-rebuild service behavior against the frozen Step-004 signatures: valid-designation reset returns 0, idempotent double-rebuild, no-provider RAISE contract (None + unset embedding_model), and `run_vector_rebuild` delegation to `vector.rebuild_index`. Embedding server faked by monkeypatching `app.db.llm_servers.get_embedding_server`; temp LanceDB via `vector.init_vector(tmp_path / "vector")`; delegation asserted via a spy on `app.db.vector.rebuild_index`.
  - `test_rebuild_valid_designation_returns_zero__DoD1_US020_AC1` — DoD-1: valid designation + init_vector → `rebuild_vector_index() == 0` (empty registry)
  - `test_rebuild_twice_is_idempotent__DoD2_US020_AC1` — DoD-2: two consecutive rebuilds both return 0, no exception
  - `test_rebuild_no_provider_raises__DoD3_D6` — DoD-3(a): `get_embedding_server()` → None → `DbAdminError` case `no_embedding_provider`
  - `test_rebuild_unset_embedding_model_raises__DoD3_D6` — DoD-3(b): designated row with `embedding_model=None` → same raise
  - `test_run_vector_rebuild_delegates_to_rebuild_index__DoD4_D6` — DoD-4: spy on `vector.rebuild_index` invoked by `run_vector_rebuild()`
  - `test_vector_source_registry_is_empty__DoD5_D6` — DoD-5: optional guard that `VECTOR_SOURCE_REGISTRY == []` (Stage-1 empty seam)
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 [manual/live — optional empty-registry guard included, not a live assertion]

### Step 005 — tests (2026-07-23)
- `backend/tests/routes/admin/test_db.py` — covers DoD-1..DoD-9 — end-to-end admin DB-management HTTP surface via the `http_client` ASGITransport harness, bound to the frozen Step-005 route table; expected statuses/bodies from the step DoD + D5/D7. Users seeded on the process-global engine (`init_db` + `set_db_ready`); drift/missing scenarios via raw DDL against `engine._engine`; vector-rebuild isolated by monkeypatching `app.db.llm_servers.get_embedding_server` + `app.db.vector.rebuild_index`.
  - `test_report_returns_drift__DoD1_US015` — DoD-1: admin GET /report → 200; ALTER-seeded drift on `users` → entry `status == "drift"`, `drift_probe` in `extra_columns`
  - `test_create_missing_table_then_ok__DoD2_US016` — DoD-2: DROP `llm_servers` → POST /tables/llm_servers/create → 204 → report shows it `ok`; unknown name → 400
  - `test_sync_drifted_table_then_ok__DoD3_US017` — DoD-3: ALTER-drifted `users` → POST /tables/users/sync → 204 → report shows it `ok`
  - `test_export_downloadable_zip__DoD4_US018` — DoD-4: GET /export → 200, `application/zip`, `Content-Disposition: attachment`, non-empty bytes open as a ZIP
  - `test_import_restores_data__DoD5_US019` — DoD-5: seed "alice" → export → import (valid multipart `file`) → 204 → `users.get_by_username("alice")` not None
  - `test_import_is_idempotent__DoD6_US019` — DoD-6: same export imported twice via the endpoint → `len(users.get_all())` stays 1
  - `test_import_corrupt_archive_rejected__DoD7_US019` — DoD-7: corrupt (non-zip) `file` → 400, user count unchanged
  - `test_vector_rebuild_returns_indexed_rows__DoD8_US020` — DoD-8: monkeypatched valid designation → POST /vector/rebuild → 200, body `{"indexed_rows": 0}`
  - `test_gating_author_forbidden_all_endpoints__DoD9` — DoD-9: author token on all six endpoints → 403 (import call carries a valid `file` so only the guard fails)
  - `test_gating_admin_success_all_endpoints__DoD9` — DoD-9: admin token on all six endpoints → documented success status (report/export/rebuild 200, import/sync/create 204), each set up to genuinely succeed
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓

## Notes & Issues

_populated by the coder when worth saying_
