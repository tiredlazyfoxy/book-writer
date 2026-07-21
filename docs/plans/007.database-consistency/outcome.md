# Outcome — Feature 007 database-consistency

Intended `docs/architecture/` changes after this feature ships. The architect applies
these at finalization; the coder appends `## Observations` below.

## `docs/architecture/backend.md`

- **New section: "Database consistency & management"** — header
  `**Realizes:** FEAT-005, UC-015..020`. Document:
  - **Schema-drift introspection** — `db/schema.py` uses SQLAlchemy `inspect()` (over the
    async engine via `run_sync`) to read the live DB's actual structure and compares it, in
    `services/db_admin.py`, against `SQLModel.metadata` to produce a per-table
    ok / drift / missing report with missing/extra column lists. Note the sanctioned
    exception: DDL/introspection lives in `db/` (like 006's raw-SQL `clear_all_embedding`),
    while services read expected structure from `SQLModel.metadata` (a non-session models-
    layer read).
  - **Remediation** — single-table `create_table` (from `SQLModel.metadata.tables[name]`
    via `table.create` — the single-table create `create_all` doesn't offer) and
    `sync_table_schema` (ALTER ADD COLUMN nullable / ALTER DROP COLUMN). Record the two
    SQLite constraints: **ADD COLUMN cannot be NOT NULL without a default** (columns are
    added nullable), and **DROP COLUMN requires SQLite ≥3.35** (satisfied by Python 3.13's
    bundled sqlite).
  - **Admin export/import** — `GET /api/admin/db/export` returns a downloadable zip
    (`Content-Disposition: attachment`); `POST /api/admin/db/import` accepts a multipart
    `UploadFile` field `file`, **pre-validates** the archive (`validate_archive`: zip-opens
    + each expected `<table>.jsonl.gz` gz/JSONL-parseable → `DbAdminError(invalid-archive)`
    → 400, DB unmutated) then UPSERTs via `import_all`. **The admin path does NOT flip
    `set_db_ready`** — that is first-run-only (`services.setup`). This is the first non-JSON
    admin response and the first admin write-import surface.
  - **Vector-rebuild wiring** — `POST /api/admin/db/vector/rebuild` and the post-import
    rebuild share one path: `run_vector_rebuild()` → `db.vector.rebuild_index()`.

- **Key architectural decision — the vector-pipeline boundary (D6).** 007 delivers the
  rebuild **OPERATION** + the LanceDB index **reset** + an **EMPTY `VECTOR_SOURCE_REGISTRY`**
  seam (documented as the list Stage-2 vector-backed domain features append
  `(model_class, text_extractor)` entries to). The **embed-content bridge is DEFERRED** to
  the first vector-backed domain model (Stage-2 codex, behind the architect gate): no
  `embed_texts`, no `services/embedding.py`, no vector-dimension detection/cache is built
  now. `rebuild_vector_index()` validates the 006 embedding designation
  (`get_embedding_server()` + `embedding_model` set) and, with the empty registry, resets
  the index and returns 0 rows. State this explicitly so the boundary is unambiguous when
  Stage 2 begins.

- **Convergence observation (not done now).** A shared `validate_archive` could later unify
  003's setup-import refusal path (`services.setup.import_database` → `SetupError`) and
  007's admin-import refusal path (`db_admin.import_database` → `DbAdminError(invalid-
  archive)`). Both wrap the same `import_all`; only the readiness-flip and error type
  differ. Recorded as a future refactor, not built.

- **Export-credential-redaction item is now LIVE.** The pending architect concern (from
  003: the `users` codec exports plaintext `pwdhash` / `jwt_signing_key`, and 006's
  `llm_servers` codec the resolved/stored `api_key`) becomes **admin-reachable** the moment
  007 ships the export **download**. Flag that 007 raises the priority of the export-
  redaction decision — the JSONL now leaves the server through an admin's browser.

## `docs/architecture/frontend.md`

- **Admin SPA grew a `Database` section** — nav is now `Users | LLM Servers | Database`;
  new `admin/pages/DatabasePage.tsx` + `databasePageState.ts` (report async trio + external
  actions).
- **`api/db.ts` introduces the frontend's first blob-download and multipart-upload
  plumbing** — both **bypass `request<T>`** (JSON-only): `exportDatabase()` reads
  `res.blob()` and triggers a browser save; `importDatabase(file)` posts `FormData` field
  `file` (mirroring 003's `setupImport`). Both still read the Bearer token from `auth.ts`.
  Note this as the sanctioned exception to "all HTTP goes through `request<T>`."

## `docs/product/`

- **No back-propagation.** FEAT-005 is fully specified and confirmed
  (`[confirmed: user]`, 2026-07-20); no requirement gap was found while planning.
