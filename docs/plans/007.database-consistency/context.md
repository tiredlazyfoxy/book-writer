# Feature 007 — Database consistency & management (feature-wide context)

## Goal & scope

Deliver **FEAT-005**: an admin-gated database-management surface. An admin views a
**per-table schema-drift report** and remediates — **create a missing table**, **sync a
drifted table's schema** (ALTER), **export** the database (downloadable gzipped-JSONL
zip), **import** an export into an already-configured instance (streaming UPSERT with
archive pre-validation), and **rebuild the LanceDB vector index**. Every capability is
admin-gated.

Product ids delivered: **FEAT-005**; **UC-015..020**; **US-015, US-016, US-017, US-018,
US-019, US-020**. Acceptance criteria live in
`docs/product/stories/FEAT-005.database-consistency.md` and use cases in
`docs/product/use-cases/FEAT-005.database-consistency.md`; each `[test]` DoD item below
cites one `US-###.AC-#` (or a numbered decision) verbatim.

## Cross-cutting conventions (see `docs/architecture/backend.md`, `frontend.md`)

- **Backend 4-layer separation** — `routes/` HTTP-only (parse → one service call → map
  typed error → return); `services/` business logic, **no `session`/`AsyncSession`/
  `select()`/`session.exec()`/`session.add()`**; `db/` session-free data access (sessions
  created internally, ORM types never leak); `models/` SQLModel tables + Pydantic schemas.
  Namespace imports (`from app.db import schema` → `await schema.introspect()`;
  `from app.services import db_admin`).
- **SQLAlchemy DDL/introspection is sanctioned in `db/` only** — `db/schema.py` may use
  `inspect()`, `run_sync`, `engine.connect()/begin()`, and compiled column types. This
  mirrors the 006 precedent (`db/llm_servers.py::clear_all_embedding` uses raw SQL in the
  db layer). Services read the **expected** structure from `SQLModel.metadata` (a models-
  layer read, not a session) — allowed from `services/`.
- **Typing discipline** — Pydantic `BaseModel` for all API I/O, `TypedDict` for internal
  data passing, no free dicts, no `any` on the frontend.
- **Admin gating (006/005 substrate)** — admin routers are
  `APIRouter(prefix="/api/admin/...")`, every endpoint `Depends(require_role(admin))`
  (ladder `{author:0, admin:1}`, 403 on shortfall); mounted via one
  `app.include_router(...)` in `main.py`; **static routes declared before `/{param}`
  routes**.
- **Frontend MobX rules** — page = route = fresh `<Page>State` (`makeAutoObservable`,
  async trio(s) only, no effectful methods); external `(state, …, signal)` effect fns with
  `runInAction`; page-level `useEffect` (mount-load / unmount-abort); `observer` on every
  component; `useState(() => new X())` for the state instance; modal/target flags
  component-local `useState`; all HTTP in `src/api/` over the shared `request<T>`
  (`204 → undefined`); hand-written `types/*.d.ts` matching wire JSON 1:1. **No frontend
  test runner exists** → all frontend DoD items are `[manual/live]`.

## Substrate that already exists (prose contracts from prior plans — conform, do not widen)

Cited plan files (read for the exact seam an individual step touches):

- **`docs/plans/001.backend-scaffold/`** — `002.db-engine-core.md` (`db/engine.py`:
  `init_db()`, `get_standalone_session()`, `init_engine(config)`, `is_db_ready()`/
  `set_db_ready()`, the model-registration hook, the additive `ALTER TABLE ADD COLUMN`
  seam), `004.import-export-mechanism.md` (`db/import_export_queries.py`: `export_table`,
  `upsert_batch`, **`run_vector_rebuild()` NO-OP STUB**; `services/db_import_export.py`:
  `export_all()`, `import_all()`, `TABLE_REGISTRY`), `001.packaging-settings-skeleton.md`
  (the `Settings` field naming the LanceDB directory — **reference it via `app/settings.py`,
  do not hardcode a name**), `002.db-engine-core.md` also covers `db/vector.py` (connect/
  init stub only).
- **`docs/plans/003.first-run-bootstrap/`** — `003.setup-service-user-codec.md`
  (`services/setup.py::import_database` wraps `import_all` in try/except → `SetupError`
  **and flips `set_db_ready`** — first-run semantics; **007 must NOT call
  `setup.import_database`**), `004.setup-routes-schemas.md` and `005.frontend-first-run-
  wizard.md` (the multipart receive shape: `POST /api/auth/setup/import` accepts a
  **multipart `UploadFile` field named `file`**; frontend `api/auth.ts::setupImport` uses
  `FormData` field `file`, no JSON content-type, Bearer via the token accessor, **bypassing
  `request<T>`** — mirror this shape; do not reuse the service).
- **`docs/plans/006.llm-server-connections/`** — `002.schemas-secrets-service.md`
  (`services/secrets.py::resolve_env_ref(raw)` resolves `$ENV`), `001.model-db-
  importexport.md` (`db/llm_servers.py::get_embedding_server()` returns the row flagged
  `is_embedding`; fields `is_embedding`, `embedding_model`; the `TABLE_REGISTRY` now holds
  `users` + `llm_servers`), `004.admin-routes-wiring.md` (the admin router / `main.py`
  include pattern, static-before-param ordering), `005.frontend-base.md` (admin SPA:
  `src/admin/App.tsx` `Users | LLM Servers` nav, `src/admin/routes.tsx` route table,
  `src/admin/pages/*` page + adjacent state file, `import * as x from '../../api/x'`).

**Everything schema-drift-related is net-new**: no `inspect()` / `PRAGMA` / reflection /
drift / single-table-create / archive-validation code exists anywhere. `run_vector_rebuild`
and `db/vector.py` are stubs whose bodies 007 implements.

## LOCKED design decisions (the frozen design — bind to these)

**D1 — Schema introspection & drift.** New db module `backend/app/db/schema.py` (session-
free; may use `inspect()`/`run_sync`) introspects the **actual** structure over the async
engine (`async with engine.connect() as conn: await conn.run_sync(lambda c: inspect(c)…)`)
→ table names + per-table column names (plus enough type info to add columns later). Service
`backend/app/services/db_admin.py` reads the **expected** structure from `SQLModel.metadata`
and computes, per expected table: `ok` (column sets match), `drift` (present but sets
differ), `missing` (absent from live DB). For a drifted table, `missing_columns = expected −
actual`, `extra_columns = actual − expected`. Report DTOs in
`backend/app/models/schemas/db_admin.py`. (US-015.)

**D2 — Remediation.** `db/schema.py` gains session-free DDL ops (via `engine.begin()`/
`run_sync`): `create_table(name)` creates ONE table from `SQLModel.metadata.tables[name]`
via `table.create(sync_conn)` (the single-table create `create_all` doesn't offer);
`add_columns(name, columns)` runs `ALTER TABLE ADD COLUMN` using each column's compiled type,
**added nullable** (SQLite can't ADD NOT NULL without a default — a hard constraint);
`drop_columns(name, columns)` runs `ALTER TABLE DROP COLUMN` (SQLite ≥3.35, satisfied by
Python 3.13's bundled sqlite). Service `create_missing_table(name)` (validate the table is in
metadata AND currently missing, else typed error) and `sync_table_schema(name)` (recompute
the diff, ADD missing + DROP extra so the table then reports ok). (US-016, US-017.)

**D3 — Admin export.** 007 owns the first export HTTP surface. `GET /api/admin/db/export`
(admin-gated) calls `export_all() -> bytes` and returns a downloadable response
(`Content-Disposition: attachment; filename=...zip`, a zip media type). (US-018.)

**D4 — Admin import.** `POST /api/admin/db/import` (admin-gated) accepts a **multipart
`UploadFile` field `file`** (mirror 003's receive shape), reads bytes, calls
`db_admin.import_database(bytes)`. That service **pre-validates the archive BEFORE any
mutation** via `validate_archive(bytes)` — verifies it opens as a zip (`zipfile.BadZipFile`
→ refuse) and each expected `<table>.jsonl.gz` member is gz-decodable and JSONL-parseable;
on failure raises a typed `DbAdminError(case=invalid-archive)` → route maps to **400**
(US-019.AC-3, DB unmutated). On success calls `import_all(bytes)` (idempotent UPSERT →
US-019.AC-1/AC-2). It must **NOT** flip `set_db_ready` (first-run only).

**D5 — Admin routes + wiring.** New router `backend/app/routes/admin/db.py` =
`APIRouter(prefix="/api/admin/db")`, every endpoint `Depends(require_role(admin))`, HTTP-
only. Endpoints: `GET /report`, `POST /tables/{name}/create`, `POST /tables/{name}/sync`,
`GET /export`, `POST /import`, `POST /vector/rebuild`. `DbAdminError.case` → status: 400
(invalid-archive / table-not-missing / not-in-metadata), 404 (unknown table), 200/204 as
appropriate, 403 from the guard. One `app.include_router(...)` in `main.py`. Static-before-
param ordering respected.

**D6 — Vector-index rebuild: OPERATION now, embed-content bridge DEFERRED (load-bearing
scope decision).** After 006 there is NO embedding-consumption path, `run_vector_rebuild()`
is a no-op stub, and there are NO vector-backed domain tables yet (users/llm_servers aren't
searchable content — that arrives in Stage 2 behind the architect gate). So 007 does **NOT**
build a codex/chapter embedding pipeline. Instead:
- `db/vector.py` gains a real `rebuild_index()`: connect to the configured LanceDB dir,
  **drop/recreate the sidecar index tables** (reset), iterate a module-level
  `VECTOR_SOURCE_REGISTRY` — an **empty list in Stage 1**, documented as the seam Stage-2
  domain features append `(model_class, text_extractor)` entries to — embedding+writing each
  source's rows. With an empty registry it resets the index and completes at **0 rows**.
- `run_vector_rebuild()` (in `db/import_export_queries.py`) delegates to
  `db.vector.rebuild_index()` so post-import rebuild and the admin button share one path.
- Service `rebuild_vector_index()` resolves `get_embedding_server()` and **validates
  `embedding_model` is set** (so the 006 dependency is real and the admin gets meaningful
  feedback), then calls the rebuild path and returns a count. In Stage 1 this resets the
  index and returns 0.
- **Do NOT build** `embed_texts` / `services/embedding.py` / vector-dimension detection or
  cache — explicitly deferred to the first vector-backed model (Stage 2 codex, behind the
  architect gate). US-020.AC-1 is satisfied at zero source rows (regenerated from current —
  zero — source rows).

**D7 — Frontend.** New `types/db.d.ts` (report DTOs 1:1 + request/response shapes),
`api/db.ts` (`getConsistencyReport`, `createTable(name)`, `syncTable(name)`,
`exportDatabase()` [**blob download** — fetch with Bearer via the auth accessor, read
`res.blob()`, trigger a browser save; net-new plumbing], `importDatabase(file)` [**multipart**
— `FormData` field `file`, mirror 003's `setupImport`, bypass `request<T>`], `rebuildIndex()`;
`signal?` last where applicable), a `DatabasePage.tsx` + `databasePageState.ts` (report async
trio + external actions), a nav entry `Database` in `admin/App.tsx`, and a route in
`admin/routes.tsx`. Keep the minimal admin layout (no heavyweight shared sidebar). 007 adds
**no new persistent model**, so `TABLE_REGISTRY` / import-export codecs are unchanged.

## Shared vocabulary

- **Expected structure** — tables/columns defined by `SQLModel.metadata` after the model-
  registration hook runs.
- **Actual structure** — tables/columns the live SQLite DB currently has (from `inspect()`).
- **`ok` / `drift` / `missing`** — the three per-table status values.
- **`missing_columns`** — expected − actual; **`extra_columns`** — actual − expected.
- **`DbAdminError`** — the feature's single typed service exception, carrying a `case`
  discriminator the route layer maps to a status.
- **`VECTOR_SOURCE_REGISTRY`** — the (empty in Stage 1) list of `(model_class,
  text_extractor)` entries the rebuild iterates; the Stage-2 embedding seam.

## Files touched across steps

- `backend/app/db/schema.py` — steps 001 (introspection + report read), 002 (DDL ops).
- `backend/app/services/db_admin.py` — steps 001 (report + `DbAdminError`), 002
  (remediation), 003 (export/import/validation), 004 (rebuild).
- `backend/app/models/schemas/db_admin.py` — step 001.
- `backend/app/db/vector.py`, `backend/app/db/import_export_queries.py` — step 004.
- `backend/app/routes/admin/db.py`, `backend/app/routes/admin/__init__.py`,
  `backend/app/main.py` — step 005.
- `frontend/src/types/db.d.ts`, `frontend/src/api/db.ts` — step 006.
- `frontend/src/admin/pages/DatabasePage.tsx`,
  `frontend/src/admin/pages/databasePageState.ts`, `frontend/src/admin/routes.tsx`,
  `frontend/src/admin/App.tsx` — step 007.
