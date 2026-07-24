# Backend — Shipped Feature Records

Part of the backend architecture — see `../backend.md` for the index.

These are the as-shipped records for features 003/004/006/007 — the `User` and `LlmServer` domain models, the LLM-server connection subsystem, and database consistency & management.

## Domain models

### User

**Realizes:** FEAT-001, UC-001, UC-002

`User` is the **first persistent entity** in the system. SQLModel table, one `db/` module (`db/users.py`). Fields:

| Field | Type / notes |
|-------|--------------|
| `id` | **Application-generated 64-bit snowflake**, serialized as a **string** at JSON boundaries. Declared `id: int = Field(default_factory=generate_id, primary_key=True)` (`fast/001.snowflake-ids`). Matches the system-wide standard (see `auth-ids.md` → "Conventions — entity ID strategy"). The only non-conformant point left is the `user_id` **JWT token claim**, still int, deferred to feature 004. |
| `username` | unique, indexed |
| `pwdhash` | nullable bcrypt hash. **`null` == disabled account** — there is deliberately **no separate `disabled` boolean**; feature 005 relies on this null-means-disabled convention. |
| `role` | `UserRole` enum — `admin` \| `author` |
| `jwt_signing_key` | nullable per-user HS256 signing key |
| `last_login` | timestamp of last successful login |
| `last_key_update` | timestamp the signing key was last rotated |

There is **no `salt` column** — bcrypt embeds its own salt in the hash.

Deliberate divergences from the reference project: **no `salt` column**, and **admin/author roles only** (the reference's role set is not mirrored). The former id-type divergence is **resolved** — `User.id` is now the app-generated snowflake standard (`fast/001.snowflake-ids`); only the `user_id` token-claim serialization remains, deferred to feature 004.

### LlmServer

**Realizes:** FEAT-004, UC-010..014

`LlmServer` is the second persistent entity — one row per configured LLM/embedding backend. SQLModel table (`models/llm_server.py`), one `db/` module (`db/llm_servers.py`). Fields:

| Field | Type / notes |
|-------|--------------|
| `id` | **Application-generated 64-bit snowflake**, serialized as a **string** at JSON boundaries. Declared `id: int = Field(default_factory=generate_id, primary_key=True)` (imports `from app.ids import generate_id`) — **conformant** to the system-wide standard (see `auth-ids.md` → "Conventions — entity ID strategy"), not an exception. |
| `name` | display name |
| `backend_type` | bare `str`, **validated at the service** against `{"llama-swap", "openai"}` (not a DB enum) |
| `base_url` | server base URL; must include `/v1` (the `llm` client appends `/models` raw — see below) |
| `api_key` | nullable; a raw literal key **or** a `$ENV_VAR` indirection token; **never returned raw** (see `has_api_key` masking below) |
| `enabled_models` | JSON-encoded `list[str]` stored in a **TEXT** column; decoded to `list[str]` only at the **service edge**, never in db/ or the table |
| `is_active` | soft on/off |
| `is_embedding` | at most one row true — enforced by clear-all-then-set (below) |
| `embedding_model` | nullable; the model name used when `is_embedding` is true |
| `created_at` / `modified_at` | timestamps |

## LLM server connections

**Realizes:** FEAT-004, UC-010..014

The first LLM-backed subsystem: admin-managed CRUD over `LlmServer` rows plus a live connection probe. It spans all four layers — `models/llm_server.py`, session-free `db/llm_servers.py`, `services/{llm_servers,secrets}.py`, and `routes/admin/llm_servers.py`.

### Secret handling — `$ENV` resolver + `has_api_key` masking

`services/secrets.py::resolve_env_ref` is the **single shared indirection point** for the `$ENV_VAR` pattern described under "Configuration & secrets" in `persistence.md`: `None → None`, a `$VAR` token → `os.environ[VAR]` (raising a typed `env_not_set` error when unset), a literal → verbatim. It is resolved **only at use time** (probe / embed), never at rest. On the wire, `LlmServerResponse` carries **no `api_key`** — only a computed `has_api_key: bool` (`api_key is not None and api_key != ""`). The stored token/literal never leaves the service edge.

### Probe / test-connection

The first wiring of the `llm` client. `probe_models` is fused and synchronous: it resolves the key, constructs the backend-typed client, and calls `list_models()`, returning a **sorted `list[str]`**. Failure taxonomy — `aiohttp.ClientError` (unreachable host), `llm.LLMError` (HTTP / auth failure), and `ValueError` (keyless OpenAI) — all funnel to a typed **probe-failed** error, surfaced at the route as **502**. `base_url` **must** include `/v1`: the client appends `/models` raw with no auto-append.

### Embedding designation — clear-all-then-set

Embedding role is per-row (`is_embedding` + `embedding_model`), and **at most one row** may hold it. Designation is enforced **clear-all-then-set**: `db.clear_all_embedding()` clears the flag on every row before the target row is set. That function is the **one sanctioned raw `sqlalchemy.update()`** inside `db/` — justified because a single bulk clear is the correct primitive and per-row iteration would be wasteful and racier.

### First DELETE pattern

`db.delete(id) -> bool` returns whether a row matched; the route maps a match to **204** and a miss to **404**. This is the codebase's first delete and the pattern later deletes follow.

### Route surface — `/api/admin/llm-servers`

Nine endpoints, every one behind `Depends(require_role(admin))`. The **static `/embedding` routes are declared before `/{server_id}`** so path capture doesn't swallow them. Error → status taxonomy: missing-field / invalid-backend-type / env-not-set → **400**, not-found → **404**, probe-failed → **502**, delete + clear-embedding → **204**, non-admin → **403**. See `quick-reference.md` for the endpoint and DTO table.

## Database consistency & management

**Realizes:** FEAT-005, UC-015..020

Admin-facing tooling to inspect the live database against the models the code expects, remediate drift, back up / restore the whole DB as an archive, and rebuild the vector sidecar. It spans `db/schema.py`, `services/db_admin.py`, and `routes/admin/db.py`, and reuses the feature-003/004 import/export codecs.

### Schema-drift introspection

`db/schema.py` reads the **actual** structure of the live database: it uses SQLAlchemy `inspect()` over the async engine (via `run_sync`, since the inspector is a sync API) to enumerate tables and their columns as they physically exist. `services/db_admin.py` compares that against the **expected** structure — `SQLModel.metadata`, the models layer's declared tables — to produce a per-table report of **ok / drift / missing**, each entry carrying its **missing-column** and **extra-column** lists (drift = the table exists but its columns diverge; missing = the expected table is absent from the live DB).

This keeps the layer split intact via a **sanctioned exception**: DDL and introspection live in `db/` (the same rule that put 006's raw-SQL `clear_all_embedding` there), while the service reads the *expected* shape straight from `SQLModel.metadata` — a **non-session models-layer read**, not a persistence access, so it does not violate the "no session in services" rule.

### Remediation

Two repair primitives, both in `db/schema.py`:

- **`create_table`** — creates a single missing table from `SQLModel.metadata.tables[name]` via `table.create`. This is used rather than `create_all` because `create_all` offers no **single-table** create; the admin repairs one named table at a time.
- **`sync_table_schema`** — reconciles a drifting table with `ALTER TABLE … ADD COLUMN` / `DROP COLUMN` to match the metadata.

Two SQLite constraints are recorded because they shape the behavior, with their reasons:

- **ADD COLUMN cannot be `NOT NULL` without a default.** SQLite forbids adding a non-nullable column to a populated table with no default, so added columns are created **nullable regardless of the metadata column's nullability**. Reconciling nullability fully would require a table rebuild, which is out of scope here.
- **DROP COLUMN requires SQLite ≥ 3.35.** Satisfied by the sqlite bundled with Python 3.13, so no fallback path is built.

### Admin export / import

- **`GET /api/admin/db/export`** returns a downloadable zip archive — `Content-Disposition: attachment`, `application/zip`. This is the **first non-JSON admin response** in the system; every prior admin endpoint returned JSON.
- **`POST /api/admin/db/import`** accepts a multipart `UploadFile` field `file` and **pre-validates the archive before any mutation**. `validate_archive` opens the upload as a zip and confirms every expected member — named by a `TABLE_REGISTRY` entry, i.e. the bare table name carrying gzipped-JSONL content — is present and gz/JSONL-parseable. Any failure raises `DbAdminError(invalid-archive)` → **400** with the **DB left unmutated**. Only after validation passes does it UPSERT via `import_all` (the shared feature-003 import path).

State explicitly: **the admin import path does NOT flip `set_db_ready`.** Readiness is a first-run concern owned by `services.setup` (feature 003); an admin restoring into an already-configured instance must not re-enter setup state. This is the system's **first admin write-import surface**, distinct from the setup-import front door.

### Typed error → status map

`DbAdminError.case` maps to HTTP status in `routes/admin/db.py`:

- `not-in-metadata` / `table-not-missing` / `invalid-archive` / `no-embedding-provider` → **400**
- `unknown-table` → **404**
- non-admin → **403**

All six endpoints are behind `Depends(require_role(admin))`, and the **static routes are declared before `/tables/{name}/...`** so path capture doesn't swallow them (the same ordering rule as the LLM-server routes).

### Vector-rebuild wiring

`POST /api/admin/db/vector/rebuild` and the post-import rebuild share **one path**: `run_vector_rebuild()` → `db.vector.rebuild_index()`. Both the explicit admin trigger and the implicit post-restore refresh converge on the same operation, so there is a single place where the sidecar is regenerated.

### The vector-pipeline boundary (deliberately partial — **closed 2026-07-24**)

**Status:** this boundary is the one the 2026-07-24 architect pass closed. The record below describes what feature 007 shipped and why it stopped where it did; `retrieval.md` is now the current design and supersedes the "DEFERRED" bullet.

Feature 007 delivers the rebuild **operation**, the index **reset**, and the **empty `VECTOR_SOURCE_REGISTRY`** seam — but **not** the embed-content bridge. Concretely:

- `VECTOR_SOURCE_REGISTRY` is a module-level list that Stage-2 vector-backed domain features append `(model_class, text_extractor)` entries to. It is **empty in Stage 1**, so a rebuild today resets the sidecar and indexes **0 rows**.
- `services/db_admin.py::rebuild_vector_index()` **validates the 006 embedding designation** — `get_embedding_server()` must return a row *and* its `embedding_model` must be set — raising `DbAdminError(no-embedding-provider)` (→ 400) otherwise. With the empty registry it then resets the index and returns **0**.
- The **embed-content bridge is DEFERRED** to the first vector-backed domain model (the Stage-2 codex, behind the architect gate): **no** `embed_texts`, **no** `services/embedding.py`, **no** vector-dimension detection/cache is built now.

Chosen so that the operation and its real dependency on the 006 embedding designation exist and are exercised, while the large embedding pipeline stays scoped out until there is actual searchable content to embed. Users and llm_servers are configuration, not searchable content — there is nothing to index yet.

### Convergence note — a future refactor (not built)

A shared `validate_archive` could later unify two currently-separate refusal paths: 003's setup-import (`services.setup.import_database` → `SetupError`) and 007's admin-import (`db_admin.import_database` → `DbAdminError(invalid-archive)`). Both wrap the same `import_all` and differ only in the readiness-flip and the error type. Recorded as a deferred refactor, deliberately not built now.
