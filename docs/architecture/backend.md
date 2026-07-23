# Backend Architecture

FastAPI application (Python 3.13, async) with SQLite storage via SQLModel, a LanceDB sidecar for semantic search, JWT auth, and LLM integration via the `llm-client` dependency. This document defines the enforced structure, typing discipline, persistence approach, config/secrets pattern, auth scheme, and test harness.

**Book-domain coverage.** The book/document entity model is **not** defined here — it lives in `domain-model.md` (the index) and the five `domain-*.md` area files under it, with `authorization.md` (book-scoped access) and `retrieval.md` (the embedding/vector bridge). This document carries only the backend-side consequences of that design: the module map, the widened registries, and the concurrency contract, all below. **Still uncovered anywhere: the internals of the FEAT-013 assistant** — context assembly, the tool/function-call protocol, the agent loop, sub-agent scoped checks (UC-088), the SSE event protocol for shared-canvas writes, prompt design, token budgets, model selection, and web-search wiring (UC-087). Those get their own design session before Stage 5.

## Layer separation (enforced)

The application under `backend/app/` is split into four layers with a strict dependency direction:

- **`routes/`** — HTTP only: parse the request, call a service, return the response. No business logic, no DB queries.
- **`services/`** — business logic and orchestration. **No `session`, `AsyncSession`, `select()`, `session.exec()`, or `session.add()` anywhere in this layer.** Services call the `db/` layer for all persistence.
- **`db/`** — the session-free data-access layer. All sessions are created and closed internally; `AsyncSession`, `select()`, and ORM row types **never leak out**. One module per entity (e.g. `users.py`). Public functions accept and return model objects or plain types.
- **`models/`** — SQLModel table definitions plus Pydantic schemas (schemas under `models/schemas/`). No logic.

### Dependency direction

```
routes ──► services ──► db ──► models
   └──────────────────► db
```

- Routes depend on services and db.
- Services depend on db — **never** import from routes.
- The db layer depends only on models — **never** on services or routes.
- No `session` / `AsyncSession` / connection objects, and no `select()` / `session.exec()` / `session.add()`, outside `db/`.

Because the db layer is session-free and DB-agnostic, the entire persistence backend could be swapped without touching services or routes.

`GET /api/health` is the first concrete endpoint and the canonical example of this four-layer flow: `routes/health.py` → `services/health.py` → `db/health.py` → `HealthResponse`, with DB-readiness sourced from `db.health.ping()` rather than a route-level constant. See `quick-reference.md` for its concrete shape.

### Import style — namespace modules

Import the module, not the symbols:

```python
from app.db import users            # then: await users.get_by_id(user_id)
from app.services import auth as auth_service   # then: auth_service.create_token(user)
```

This keeps call sites self-documenting (`users.get_by_id(...)`, `auth_service.create_token(...)`).

## Typing discipline

**No free dictionaries. No untyped data. Everything is typed.**

| Layer | Model type | Usage |
|-------|-----------|-------|
| API request/response | Pydantic `BaseModel` | all endpoint I/O |
| Database tables | `SQLModel` (`table=True`) | ORM models (SQLAlchemy + Pydantic) |
| LLM tool schemas | Pydantic `BaseModel` | parameter schemas for function calling |
| Internal data passing | `TypedDict` | in-process data between functions |

## `pyproject.toml` dependencies

The backend is packaged as `bookwriter-backend` with setuptools + a local `.venv` (Windows `Scripts/` layout). The dependency block:

```toml
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.34",
    "sqlmodel>=0.0.22",
    "aiosqlite>=0.21",
    "pyjwt[crypto]>=2.10",
    "pydantic>=2.10",
    "pydantic-settings>=2.7",
    "python-multipart>=0.0.20",
    "bcrypt>=4.0",
    "llm-client @ git+https://github.com/Iezious/PythonLLMClient.git@v0.1.4",
    "python-dotenv>=1.0",
    "lancedb>=0.6",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-asyncio>=0.25", "httpx>=0.28"]
```

The `llm-client` entry is a **shared external library** — keep the git URL and `@v0.1.4` tag verbatim. It imports as the module `llm` and supports OpenAI-compatible and llama-swap backends.

## Relational storage — SQLite via SQLModel (async)

- Async engine over `sqlite+aiosqlite:///`, sessions managed entirely inside `db/`.
- Schema is created with `SQLModel.metadata.create_all` (wrapped as `init_db()`). Schema evolution is handled by **in-code `ALTER TABLE` migrations** run at startup — **there is no Alembic**. Keep migrations idempotent and additive.
- **Startup lifecycle — deferred schema creation (feature 003).** The lifespan **no longer runs `create_all` eagerly**. A cold instance boots with an **open engine and zero tables**; schema creation is **deferred to the setup flows** — `create_database` and `import_database` each call `init_db()` before writing. This **supersedes the feature-001 "eager `create_all` on boot"** seam described previously. Unconfigured state is detected from **admin existence**, not file existence: `db.users.admin_exists()` feeds a process-level readiness flag (`is_db_ready()` / `set_db_ready()`), and `needs_setup = not is_db_ready()`. Note the reconciled health behavior: `GET /api/health` **still passes on a cold instance** because `db.health.ping()`'s `SELECT 1` succeeds against an open engine even with zero tables — readiness for health and configured-for-setup are distinct concerns.
- Injectable config so tests can point at a throwaway DB:

  ```python
  @dataclass
  class DbConfig:
      db_path: Path       # SQLite file path (injectable for tests)
      echo: bool = False  # SQLAlchemy echo for debugging
  ```

- The DB file path is overridable at runtime via the `BOOKWRITER_DB_PATH` environment variable (dev default `backend/data/bookwriter.db`).

### DB import/export

Every persistent model has gzipped-JSONL (`.jsonl.gz`) import/export, packaged in a zip. This is part of defining a model — extend the import/export logic in the same change that adds or alters a model.

- **Export** streams per row: the db layer iterates rows and invokes a `callback(row)`; the service serializes each to JSONL into the gzip stream. No bulk `SELECT *` into memory.
- **Import** streams line-by-line: the service reads JSONL, accumulates a batch (e.g. 100), and calls an `upsert_batch(items)` on the db layer. Import is **UPSERT** — idempotent, safe to re-run. `init_db()` creates/reshapes tables before import.
- **Extension point.** A persistent model plugs in by adding its `to_dict`/`from_dict` codec pair plus one ordered `TABLE_REGISTRY` tuple (shape `(zip_filename, model_class, to_dict_fn, from_dict_fn)`) in FK dependency (import) order, in `services/db_import_export.py`. The session-free `db/` primitives (`export_table`, `upsert_batch`) need no per-model change. **`users` is the first `TABLE_REGISTRY` entry** (feature 003), carrying the first `to_dict`/`from_dict` codec; feature 001's "empty `TABLE_REGISTRY`" precondition is **superseded** now that a model is registered. **`llm_servers` is the second entry** (feature 004), registered after `users`.
- **Entity id serialization.** Entity ids serialize as **strings** in JSONL — the `to_dict` codec emits `id` as a JSON string, and `from_dict` accepts **either a string or a legacy JSON number** (parsing via `int(...)`). This is the system-wide 64-bit id rule (snowflake ids exceed JS's 2^53, so a number would lose precision); the number-or-string acceptance keeps pre-snowflake archives importable. **Realized in code for the `users` codec** (`_user_to_dict` emits `str(user.id)`; `_dict_to_user` parses string-or-number) by `fast/001.snowflake-ids`. See "Conventions — entity ID strategy".

Two settled policies govern how credentials cross the import/export boundary:

- **Export credential policy.** The `users` codec (and export) **includes credentials** — `pwdhash` and `jwt_signing_key` — so restored accounts can authenticate, as required by US-002 (restore-and-login). This makes today's export the **"full / backup" mode, and it is secret-grade**: an export archive must be handled as a secret because it carries live credential material. `LlmServer.api_key`, however, is **redacted on export** (feature 004): a `$ENV` token is a *pointer*, not a secret, so `$`-prefixed values (and `None`) are exported verbatim, while a **raw literal key is emitted as `null`** — an operator re-enters it after restore. This is a **scoped early slice** of the feature-007 sanitized-export target, applied to LLM keys only; the broader two-mode split (full vs. sanitized) covering `User` credentials is **still not built** — `pwdhash` / `jwt_signing_key` continue to export verbatim in today's full/backup mode. Feature 007's export **download** endpoint (`GET /api/admin/db/export`) now makes that full/backup archive **admin-reachable through a browser**, which **raises the priority** of the still-unbuilt sanitized-export mode for `User` credentials — the archive, which carries live `pwdhash` / `jwt_signing_key`, now leaves the server through an admin's browser. The **only remaining plaintext-export concern is `User.pwdhash` / `jwt_signing_key`**: `LlmServer.api_key` is already redacted on export (a raw literal is emitted as `null`; a `$ENV` pointer is kept), per the feature-006 rewrite.
- **Partial-import rollback — accepted limitation.** Import is a streaming, idempotent UPSERT. A corrupt or failed import raises `SetupError`, leaves the instance **unconfigured** (`set_db_ready` is **not** called), and is recovered by **retrying with a valid archive** — the idempotent UPSERT overwrites any partial rows. There is **no transactional rollback** of a partially-written import. This is a **deliberately accepted limitation**, justified by the idempotent-UPSERT plus unconfigured-on-failure design: a half-written instance is never treated as ready, and a clean retry converges it.

## Vector storage — LanceDB sidecar

LanceDB (`lancedb>=0.6`) provides semantic search alongside SQLite. It is a **sidecar index**: it is **rebuilt from the SQLite source rows on import, not exported**. Treat SQLite as the source of truth; LanceDB is a derived index that can always be regenerated. As of feature 007, `db/vector.py` exposes a real **`rebuild_index()`** that connects to the configured LanceDB dir, **drops/recreates the sidecar tables (a full reset)**, and iterates a module-level **`VECTOR_SOURCE_REGISTRY`**. The rebuild-on-import contract stands as described; the sidecar is always regenerated from SQLite source rows and is never exported.

**The registry is no longer empty.** `CodexEntry` is the first vector-backed model and registers at Stage 2, closing the embed-content bridge feature 007 deferred. The registry entry shape also **widens** — from `(model_class, text_extractor)` to a typed entry carrying a source-kind discriminator, a row selector and a **chunker** — because one source row now produces many vectors. `services/embedding.py` (the module 007 explicitly did not build) becomes the single point where text becomes vectors, resolving the FEAT-004 designated embedding server. Full design, including chunking, incremental maintenance, dimension handling and failure modes: **`retrieval.md`**.

## LLM client

LLM communication goes exclusively through the `llm-client` dependency, imported as the module `llm`. It supports OpenAI-compatible servers and llama-swap. Tool schemas are generated from Pydantic models (`pydantic_to_openai_tool()`) rather than hand-written JSON. Do not make direct outbound HTTP calls to LLM providers from application code — route them through `llm`.

## Configuration & secrets

- Local config lives in `.env.local` (gitignored), loaded via `python-dotenv` / `pydantic-settings`.
- **Provider and LLM-server settings are stored in the database**, not in a settings file, so they can be managed at runtime through the Admin SPA.
- API keys use `$ENV_VAR` indirection: a stored value such as `api_key = "$OPENAI_API_KEY"` is resolved from the environment **at use time**. Raw key values are **never returned** in API responses — the API surfaces the indirection token, not the secret.

## Authentication — per-user JWT key + bcrypt

- Passwords are hashed with **bcrypt**.
- Tokens are **JWT, HS256**, but signed with a **per-user signing key** rather than one global application secret. Each user record carries its own signing key; a token is verified against the key of the user it claims to be. There is no shared global secret to leak or rotate app-wide.
- The per-user key is **rotated roughly every 30 days on login**: when a user logs in and their key is older than the rotation window, a fresh key is generated, which transparently invalidates that user's older tokens.
- Tokens are stateless and carried in `Authorization: Bearer <token>`; both SPAs share the same login flow and token. Role information (user vs admin) is carried in the token / user record and gate-checked in `routes/` (or a shared dependency) before delegating to services.

### What feature 003 delivers (minimal subset)

Feature 003 ships only the **minimal** auth primitives needed for first-run bootstrap, not the full scheme above:

- bcrypt `hash_password` / `verify_password`;
- per-user `generate_signing_key`;
- `create_token(user)` — an HS256 token signed with the user's **own** `jwt_signing_key`, payload `user_id` / `username` / `role` / `exp` (≈ +30 days).

Token **verification**, **rotation-on-login**, and **logout** are **not** in 003 — they remain **feature 004**. Until 004 lands, the described per-user-key verification and 30-day rotation are design intent, not shipped behavior.

## Conventions — entity ID strategy

**Realizes:** (system-wide convention)

**The system-wide standard for entity primary-key ids is Snowflake ids, used universally ("anywhere"), with no permanent exceptions.** Rationale: node-aware, globally-unique, time-ordered ids keep cross-instance import/export identity unambiguous as the system grows and as archives move between instances — chosen over autoincrement integers, whose values collide across instances and force id remapping on import. Every new persistent entity uses snowflake ids.

### Concrete Snowflake spec

- **64-bit, Twitter-style layout.** A snowflake id is a 64-bit integer partitioned as **41-bit millisecond timestamp** (since a fixed custom epoch) + **10-bit node id** (0–1023) + **12-bit per-millisecond sequence** (0–4095). The **high bit stays 0** so every id is positive. This yields ~69 years of timestamp range, up to 1024 nodes, and 4096 ids per millisecond per node — chosen because it is the well-understood, proven partitioning that satisfies globally-unique, roughly time-ordered ids within a 64-bit signed range.
- **Custom epoch.** Timestamps are measured from a **fixed project epoch**. The constant is **realized in code** as `EPOCH_MS = 1704067200000` (`2024-01-01T00:00:00Z`) in `app/ids.py`. It is **fixed once and never changed** — moving the epoch re-collides historical ids, so it is a permanent constant of the system, not a tunable.
- **Node id from config.** The 10-bit node id comes from the **`node_id` setting** — realized as `Settings.node_id`, sourced from env **`BOOKWRITER_NODE_ID`** (default `0`, range 0–1023 via `ge`/`le` validation) through the existing pydantic-settings config — the same override pattern as `BOOKWRITER_DB_PATH`. `generate_id()` reads the node id at call time. A distinct node id per instance is what keeps ids unique across instances that generate concurrently.
- **Generator location.** A single cross-cutting utility module **`app/ids.py`** exposes **`generate_id() -> int`** — realized in code (`fast/001.snowflake-ids`) as a monotonic per-millisecond snowflake with a lock-guarded sequence, spin-wait on sequence overflow, and a backwards-clock clamp; the frozen bit-layout constants (`TIMESTAMP_BITS=41`, `NODE_ID_BITS=10`, `SEQUENCE_BITS=12`, `NODE_ID_SHIFT=12`, `TIMESTAMP_SHIFT=22`, `MAX_NODE_ID=1023`, `MAX_SEQUENCE=4095`) live alongside it. It is deliberately **not one of the four layers** — it is a shared helper (like a stdlib utility), called at the entity-construction site. This is the **sanctioned exception** to the "one `db/` module per entity" rule, justified because ids are domain-agnostic and shared by every entity; a per-entity id module would be meaningless duplication.
- **Assignment point — application-generated.** Ids are **generated in the application at entity construction, before insert** — they exist prior to persistence and do **not** rely on DB autoincrement or a post-insert `refresh()` to learn the id. This is **locked**: app-generated, not DB-assigned, because cross-instance uniqueness and time-ordering come from the generator, not the database. The mechanism is now **settled and realized** as a model field with `default_factory=generate_id` — `User` declares `id: int = Field(default_factory=generate_id, primary_key=True)` (`fast/001.snowflake-ids`). The earlier db-layer-on-`None` alternative was **not** chosen.

### 64-bit id JSON serialization convention (system-wide)

**This applies to every entity, not just `User`.** Entity ids are **64-bit ints in Python but are serialized as strings at every JSON boundary** — the export/import JSONL codecs, API request/response DTOs, and the frontend `.d.ts` types. Reason: snowflake ids exceed JavaScript's `Number.MAX_SAFE_INTEGER` (2^53), so a JSON *number* would **silently lose precision** when parsed by any JS/JSON consumer. A JSON **string** preserves the full 64 bits exactly. The frontend therefore types entity ids as `string` (see `frontend.md`).

**Import back-compat.** `from_dict` codecs must accept **both a JSON string and a legacy JSON number** for `id`, parsing via `int(...)`, so **pre-snowflake export archives** — which carry small autoincrement int ids as JSON numbers — still import. Legacy small ints will not collide with time-based snowflakes (which sit far above them in value), so mixed archives are safe.

**Realized migration — one caveat remaining.** The first shipped entity, `User` (feature 003), now uses an **application-generated 64-bit snowflake PK**, delivered by `fast/001.snowflake-ids`. Two of the three migration touch-points are complete: the PK column (`id: int = Field(default_factory=generate_id, primary_key=True)`) and the import codec (string-out, string-or-legacy-number-in). The **one remaining touch-point** is the `user_id` **JWT token claim**, which is **still an int** and **deferred to feature 004** — so `User` is fully conformant except on that single token-claim serialization point. Do **not** read the token claim's current int form as the convention; the convention is snowflake, string-serialized at every JSON boundary. See the Decision history entries (2026-07-22).

**Migration stance — fresh-install, model-only.** The `User`→snowflake migration assumed **no deployed `User` data** (fresh-install stance), so it was a **model-only** change: the PK moved from DB-autoincrement to app-generated snowflake, with **no in-place PK data migration**. This is fortunate — `create_all` cannot alter an existing PK, and there is no Alembic, so an in-place PK-type conversion has no seam here anyway. Fresh installs get the new schema directly from `create_all`; any pre-existing dev DB must be **recreated or re-imported from an archive**, and import stays back-compatible with legacy int-id archives per the serialization convention above.

## Domain models

### User

**Realizes:** FEAT-001, UC-001, UC-002

`User` is the **first persistent entity** in the system. SQLModel table, one `db/` module (`db/users.py`). Fields:

| Field | Type / notes |
|-------|--------------|
| `id` | **Application-generated 64-bit snowflake**, serialized as a **string** at JSON boundaries. Declared `id: int = Field(default_factory=generate_id, primary_key=True)` (`fast/001.snowflake-ids`). Matches the system-wide standard (see "Conventions — entity ID strategy"). The only non-conformant point left is the `user_id` **JWT token claim**, still int, deferred to feature 004. |
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
| `id` | **Application-generated 64-bit snowflake**, serialized as a **string** at JSON boundaries. Declared `id: int = Field(default_factory=generate_id, primary_key=True)` (imports `from app.ids import generate_id`) — **conformant** to the system-wide standard (see "Conventions — entity ID strategy"), not an exception. |
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

`services/secrets.py::resolve_env_ref` is the **single shared indirection point** for the `$ENV_VAR` pattern described under "Configuration & secrets": `None → None`, a `$VAR` token → `os.environ[VAR]` (raising a typed `env_not_set` error when unset), a literal → verbatim. It is resolved **only at use time** (probe / embed), never at rest. On the wire, `LlmServerResponse` carries **no `api_key`** — only a computed `has_api_key: bool` (`api_key is not None and api_key != ""`). The stored token/literal never leaves the service edge.

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

## Book domain — backend impact

**Realizes:** FEAT-006..018 (backend-side consequences only)

The entity definitions, their reasoning and their lifecycles live in `domain-model.md` (the index) and its area files — `domain-book.md`, `domain-chapter.md`, `domain-continuity.md`, `domain-codex.md`, `domain-chat.md`. This section records what the design costs *this* document's structures.

### Module map

The existing four-layer split absorbs the domain without change — one `db/` module per entity, one service per aggregate, routes under `/api`:

| Layer | Modules |
|---|---|
| `models/` | `book.py`, `book_member.py`, `chapter.py`, `chapter_change.py`, `chapter_text_revision.py`, `chapter_notes.py`, `codex_entry.py`, `codex_entry_version.py`, `flag.py`, `chat.py` (+ `models/schemas/` DTOs per resource) |
| `db/` | one module per table, session-free, same shape as `db/users.py` / `db/llm_servers.py` |
| `services/` | per aggregate — books (lifecycle, membership, visibility, mode), chapters (skeleton, state machine, the merge path), codex, continuity, flags — plus **`services/authz.py`** (the capability table) and **`services/embedding.py`** (text → vectors) |
| `routes/` | HTTP only, under `/api`; the book-access dependency resolves a typed `BookAccess`, the service decides the capability |

Two cross-cutting additions worth naming because they are shared rather than per-entity:

- **`services/authz.py`** — one `require(access, capability)` entry point so the capability × role matrix has a single implementation. See `authorization.md` → "Enforcement".
- **`services/embedding.py`** — the single point where text becomes vectors. See `retrieval.md`.

### The book-domain table registry

`TABLE_REGISTRY` (`services/db_import_export.py`) gains a codec pair per new table, appended **in FK dependency (import) order** after the two existing entries:

```
users, llm_servers,                       # existing
books, book_members,
chapters, chapter_changes, chapter_text_revisions, chapter_note_changesets,
codex_entries, codex_entry_versions,
flags,
chats, chat_messages
```

**Flag this plainly: that is roughly a dozen new codec pairs.** The rule in the root `CLAUDE.md` is not optional and not deferrable — "update the import/export logic in the **same change** whenever a model is added or altered". Every one of these tables owes its `to_dict` / `from_dict` pair (ids emitted as **strings**, accepted as string-or-legacy-number) and its ordered registry tuple in the change that introduces the model. Batching them up "for later" would leave an instance whose export silently loses a book.

Order matters because import is a streaming UPSERT with no transactional rollback: a child row arriving before its parent has nothing to attach to.

### Vector registry

`VECTOR_SOURCE_REGISTRY` is **no longer empty** — `CodexEntry` registers at Stage 2, with chapter text, summaries and notes following for UC-086. See "Vector storage" above and `retrieval.md`.

### Stage-4 columns land at Stage 2

The book domain's later-stage **columns are created with their tables**, nullable and unused, rather than added when the behaviour ships: `Chapter.state = closing`, `Chapter.summary_status`, `Book.moderation_reason` / `moderated_by` / `moderated_at`, and the `ChapterNoteChangeset` table with its `status`.

The reason is this document's own SQLite constraint, recorded under "Remediation": **`ADD COLUMN` cannot be `NOT NULL` without a default on a populated table**, so a column added later against live book data arrives nullable regardless of what the model declares, and reconciling nullability would need a table rebuild. Landing them now costs a wider `CREATE TABLE` that nothing queries and makes Stage 4 pure behaviour with **no DDL at all**. See `domain-chapter.md` → "Landing the continuity columns early".

### Chapter concurrency — the 409 rule

`Chapter.version` is bumped on every applied change, and a write carrying a stale `base_version` is **refused with 409**, never merged server-side. This is a service-layer rule (the merge is a single transaction: snapshot → apply placement → bump version), and it is what US-041's concurrent-edit warning is built from. Full reasoning, including why a uniform refusal was chosen over a placement-dependent one, is in `domain-chapter.md` → "Concurrency".

### Schema drift — no new code

FEAT-005's consistency report (`db/schema.py` + `services/db_admin.py`) compares the live database against `SQLModel.metadata`. Every table above lands in that metadata by being declared, so **the drift report covers the new tables with no change to the FEAT-005 code at all** — the ok / drift / missing report and the per-table create/sync remediation extend to the book domain for free. This is the payoff of having built drift detection against metadata rather than against a hand-maintained table list.

## Logging

- Python standard `logging`, default output to console.
- `INFO` for incoming API requests and key lifecycle events; `DEBUG` for full flow (LLM request/response, tool calls, internal results).

## Test harness — pytest + httpx (in-process ASGI)

- Runner: `pytest` with `pytest-asyncio` in `asyncio_mode="auto"` (async tests need no per-test decorator).
- Tests exercise the app **in-process** via `httpx.AsyncClient` over `ASGITransport` — no live server, no real network.
- A fixture provides a temporary-SQLite `DbConfig` so each test run gets an isolated throwaway database; the app's db layer is initialized against it.
- Run with `cd backend && .venv/Scripts/python -m pytest` (see the root `CLAUDE.md` for the canonical command).

## Decision history

- **2026-07-22 — System-wide entity ID strategy = Snowflake ids.** Standardized on node-aware, globally-unique, time-ordered snowflake ids for **all** entities ("anywhere," no permanent exceptions), to keep cross-instance import/export identity unambiguous. This **reverses the implicit choice** made when feature 003 shipped `User` with an **autoincrement integer PK**, and therefore creates known migration debt: `User` must migrate its PK type, its import-codec explicit-id handling, and its `user_id` token claim. Recorded here because the decision overturns a shipped choice and carries follow-up work. See "Conventions — entity ID strategy" and the `User` domain model.
- **2026-07-22 — Concrete Snowflake design + serialization convention (refines the entry above).** Settled the implementation specifics so the migration can be planned: a **64-bit id** with a **41-bit ms timestamp / 10-bit node id / 12-bit sequence** layout (high bit 0) over a **fixed custom epoch** (fixed once, never changed); the node id from a new **`node_id` setting** via env **`BOOKWRITER_NODE_ID`** (default `0`); a cross-cutting **`app/ids.py` `generate_id()`** generator (the sanctioned exception to one-module-per-entity); and **application-generated ids at entity construction** (locked — not DB-assigned; `default_factory=generate_id` recommended, db-layer-on-None acceptable). Adopted the system-wide rule that **entity ids serialize as strings at every JSON boundary** (JSONL codecs, API DTOs, frontend `.d.ts`) because snowflakes exceed JS's 2^53 and a JSON number would lose precision, with **from_dict accepting number-or-string** for legacy-int-archive back-compat. Set the `User` migration as **fresh-install / model-only** — no in-place PK data migration (none is possible: `create_all` cannot alter a PK, no Alembic), reframing `User` from unscoped debt to a scoped, planned migration. See "Conventions — entity ID strategy" and the `User` domain model.
- **2026-07-23 — `LlmServer` conformed to the snowflake id standard; literal LLM `api_key` redacted on export (feature 006 + rewrite).** Feature 006 originally shipped `LlmServer` with an autoincrement-int PK and a verbatim `api_key` export; a same-day rewrite brought both into line with the settled conventions. `LlmServer.id` is now `id: int = Field(default_factory=generate_id, primary_key=True)` (mirroring `User`), string-serialized at the DTO/frontend edge — chosen for **consistency with the system-wide snowflake standard** and to keep cross-instance import identity unambiguous. On export, a raw literal `api_key` is now replaced with `null` while `$ENV` pointer tokens are kept — chosen because a **secret-grade literal key should not land in an archive**, whereas an `$ENV` pointer safely can (it names an environment variable, not a secret). `User` credential export is unchanged. See "LLM server connections", the `LlmServer` domain model, and the "DB import/export" export credential policy.
- **2026-07-23 — Vector-pipeline boundary for the DB-consistency feature (feature 007).** Feature 007 shipped the vector-rebuild **operation** + full index **reset** + the **empty `VECTOR_SOURCE_REGISTRY`** seam (the list Stage-2 vector-backed domain features append `(model_class, text_extractor)` entries to), wired through `run_vector_rebuild()` → `db.vector.rebuild_index()` and validating the 006 embedding designation (`no-embedding-provider` → 400). It **deliberately deferred** the embed-content bridge — no `embed_texts`, no `services/embedding.py`, no vector-dimension detection/cache — to the first vector-backed domain model (the Stage-2 codex, behind the architect gate). Reasoning: with an empty registry a rebuild indexes 0 rows, so building the embedding pipeline now would be dead code; users and llm_servers are configuration, not searchable content, so nothing yet needs embedding. This keeps the operation and its real 006 dependency exercised while the large pipeline stays scoped out until there is content to index. See "Database consistency & management" and "Vector storage — LanceDB sidecar".
- **2026-07-24 — First book-domain architecture pass; the vector-pipeline boundary closed.** The Stage-2 architect gate settled the `FEAT-006..018` entity map (`domain-model.md` plus the `domain-*.md` area files), book-scoped authorization (`authorization.md`), the embedding/vector bridge (`retrieval.md`) and the frontend workspace (`frontend-workspace.md`). Backend consequences recorded above: one `db/` module per new entity plus two cross-cutting services (`services/authz.py`, `services/embedding.py`); ~12 new `TABLE_REGISTRY` codec pairs in FK order; `VECTOR_SOURCE_REGISTRY` no longer empty (`CodexEntry` first) with its entry shape **widened** from `(model_class, text_extractor)` to carry a source kind, a row selector and a chunker, because one row now yields many vectors; and the `Chapter.version` / 409 concurrency rule. FEAT-005's drift report needed no change — it reads `SQLModel.metadata`, so new tables are covered by declaration alone. **Deliberately still undesigned:** FEAT-013's assistant internals (`domain-chat.md` states the boundary). See the documents named above.
- **2026-07-22 — Snowflake design implemented for `User` (`fast/001.snowflake-ids`).** The settled design above is now **realized in code**. `app/ids.py` ships `generate_id()` (monotonic per-ms snowflake, lock-guarded sequence, spin-wait on overflow, backwards-clock clamp) with the pinned `EPOCH_MS = 1704067200000` and frozen bit-layout constants; the node id comes from `Settings.node_id` (env `BOOKWRITER_NODE_ID`, default 0, range 0–1023). `User`'s PK is `id: int = Field(default_factory=generate_id, primary_key=True)` (the db-layer-on-`None` alternative was not taken), and the `users` import codec emits `id` as a JSON string while accepting a legacy JSON number on import. **One touch-point remains open:** the `user_id` **JWT token claim** is still an int and its int→string serialization is **deferred to feature 004**. This closes the loop from the two design-decision entries above to their realization. See "Conventions — entity ID strategy" and the `User` domain model.
