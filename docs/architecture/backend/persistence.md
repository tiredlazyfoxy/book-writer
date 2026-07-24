# Backend — Persistence, I/O & Config

Part of the backend architecture — see `../backend.md` for the index.

This file covers backend persistence: relational storage via async SQLite/SQLModel and the deferred-schema startup lifecycle, the gzip-JSONL import/export pipeline, the LanceDB vector sidecar, and the configuration/secrets pattern.

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
- **Entity id serialization.** Entity ids serialize as **strings** in JSONL — the `to_dict` codec emits `id` as a JSON string, and `from_dict` accepts **either a string or a legacy JSON number** (parsing via `int(...)`). This is the system-wide 64-bit id rule (snowflake ids exceed JS's 2^53, so a number would lose precision); the number-or-string acceptance keeps pre-snowflake archives importable. **Realized in code for the `users` codec** (`_user_to_dict` emits `str(user.id)`; `_dict_to_user` parses string-or-number) by `fast/001.snowflake-ids`. See `auth-ids.md` → "Conventions — entity ID strategy".

Two settled policies govern how credentials cross the import/export boundary:

- **Export credential policy.** The `users` codec (and export) **includes credentials** — `pwdhash` and `jwt_signing_key` — so restored accounts can authenticate, as required by US-002 (restore-and-login). This makes today's export the **"full / backup" mode, and it is secret-grade**: an export archive must be handled as a secret because it carries live credential material. `LlmServer.api_key`, however, is **redacted on export** (feature 004): a `$ENV` token is a *pointer*, not a secret, so `$`-prefixed values (and `None`) are exported verbatim, while a **raw literal key is emitted as `null`** — an operator re-enters it after restore. This is a **scoped early slice** of the feature-007 sanitized-export target, applied to LLM keys only; the broader two-mode split (full vs. sanitized) covering `User` credentials is **still not built** — `pwdhash` / `jwt_signing_key` continue to export verbatim in today's full/backup mode. Feature 007's export **download** endpoint (`GET /api/admin/db/export`) now makes that full/backup archive **admin-reachable through a browser**, which **raises the priority** of the still-unbuilt sanitized-export mode for `User` credentials — the archive, which carries live `pwdhash` / `jwt_signing_key`, now leaves the server through an admin's browser. The **only remaining plaintext-export concern is `User.pwdhash` / `jwt_signing_key`**: `LlmServer.api_key` is already redacted on export (a raw literal is emitted as `null`; a `$ENV` pointer is kept), per the feature-006 rewrite.
- **Partial-import rollback — accepted limitation.** Import is a streaming, idempotent UPSERT. A corrupt or failed import raises `SetupError`, leaves the instance **unconfigured** (`set_db_ready` is **not** called), and is recovered by **retrying with a valid archive** — the idempotent UPSERT overwrites any partial rows. There is **no transactional rollback** of a partially-written import. This is a **deliberately accepted limitation**, justified by the idempotent-UPSERT plus unconfigured-on-failure design: a half-written instance is never treated as ready, and a clean retry converges it.

## Vector storage — LanceDB sidecar

LanceDB (`lancedb>=0.6`) provides semantic search alongside SQLite. It is a **sidecar index**: it is **rebuilt from the SQLite source rows on import, not exported**. Treat SQLite as the source of truth; LanceDB is a derived index that can always be regenerated. As of feature 007, `db/vector.py` exposes a real **`rebuild_index()`** that connects to the configured LanceDB dir, **drops/recreates the sidecar tables (a full reset)**, and iterates a module-level **`VECTOR_SOURCE_REGISTRY`**. The rebuild-on-import contract stands as described; the sidecar is always regenerated from SQLite source rows and is never exported.

**The registry is no longer empty.** `CodexEntry` is the first vector-backed model and registers at Stage 2, closing the embed-content bridge feature 007 deferred. The registry entry shape also **widens** — from `(model_class, text_extractor)` to a typed entry carrying a source-kind discriminator, a row selector and a **chunker** — because one source row now produces many vectors. `services/embedding.py` (the module 007 explicitly did not build) becomes the single point where text becomes vectors, resolving the FEAT-004 designated embedding server. Full design, including chunking, incremental maintenance, dimension handling and failure modes: **`retrieval.md`**.

## Configuration & secrets

- Local config lives in `.env.local` (gitignored), loaded via `python-dotenv` / `pydantic-settings`.
- **Provider and LLM-server settings are stored in the database**, not in a settings file, so they can be managed at runtime through the Admin SPA.
- API keys use `$ENV_VAR` indirection: a stored value such as `api_key = "$OPENAI_API_KEY"` is resolved from the environment **at use time**. Raw key values are **never returned** in API responses — the API surfaces the indirection token, not the secret.
