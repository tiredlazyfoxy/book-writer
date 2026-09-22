# Backend — Persistence, I/O & Config

Part of the backend architecture — see `../backend.md` for the index.

This file covers backend persistence: relational storage via async SQLite/SQLModel and the deferred-schema startup lifecycle, the gzip-JSONL import/export pipeline, the LanceDB vector sidecar, and the configuration/secrets pattern.

## Relational storage — SQLite via SQLModel (async)

- Async engine over `sqlite+aiosqlite:///`, sessions managed entirely inside `db/`.
- Schema is created with `SQLModel.metadata.create_all` (wrapped as `init_db()`). Schema evolution is handled by **in-code additive `ALTER TABLE` migrations run inside `init_db()`** — **there is no Alembic**. Keep migrations idempotent and additive. **They do *not* run at application startup**: this line previously said they did, which contradicted the very next bullet and is corrected here, because that false belief is exactly what let feature `024` ship a column that never reached an existing database. See "The additive-column seam" below.
- **Startup lifecycle — deferred schema creation (feature 003).** The lifespan **no longer runs `create_all` eagerly**. A cold instance boots with an **open engine and zero tables**; schema creation is **deferred to the setup flows** — `create_database` and `import_database` each call `init_db()` before writing. This **supersedes the feature-001 "eager `create_all` on boot"** seam described previously. Unconfigured state is detected from **admin existence**, not file existence: `db.users.admin_exists()` feeds a process-level readiness flag (`is_db_ready()` / `set_db_ready()`), and `needs_setup = not is_db_ready()`. Note the reconciled health behavior: `GET /api/health` **still passes on a cold instance** because `db.health.ping()`'s `SELECT 1` succeeds against an open engine even with zero tables — readiness for health and configured-for-setup are distinct concerns.
- **Both first-run paths seed the five `AssistantMode` rows** (feature `012.assistant-config-editor`, step 001). `services/setup.py::create_database` has done so since feature 008; `services/setup.py::import_database` now does too, after the import succeeds and before `set_db_ready(True)`. The seed is **idempotent by `key`**, so an archive that already contains configured modes converges instead of colliding — that convergence is the property the natural-key PK exists to provide (see "DB import/export" below). Before this, an instance bootstrapped by DB import had **no modes at all** and would show an empty admin editor; that is a bootstrap-lifecycle fact, not an implementation detail, which is why it is recorded here rather than in a feature note. The **admin** import surface (`services/db_admin.py` → `routes/admin/db.py`) is unaffected and still does **not** flip `set_db_ready` — it restores into an already-configured instance.
- Injectable config so tests can point at a throwaway DB:

  ```python
  @dataclass
  class DbConfig:
      db_path: Path       # SQLite file path (injectable for tests)
      echo: bool = False  # SQLAlchemy echo for debugging
  ```

- The DB file path is overridable at runtime via the `BOOKWRITER_DB_PATH` environment variable (dev default `backend/data/bookwriter.db`).

### The additive-column seam (feature `024.chat-agent-loop`)

**A new column on an existing table requires an `ADDITIVE_COLUMNS` entry in the same change — exactly as it requires an import/export codec update.** State it as the **non-optional obligation** it is, beside the codec rule below, because it is the same class of obligation and it was undocumented until it cost an outage: feature `024` added `ChatMessage.tool_trace`, the change was **complete by every rule the docs stated**, and **every `chat_messages` INSERT on an existing install failed** — including a plain user message, so chat was unusable end to end, not merely the new feature.

**Why.** `SQLModel.metadata.create_all` creates **missing tables** and never alters an existing one. A fresh database is unaffected, which is why the full test suite stayed green: the defect is only observable against a database created **before** the change.

**The mechanism**, briefly. A module-level declaration table in `db/engine.py` (`ADDITIVE_COLUMNS`, one `(table, column)` tuple per addition) applied inside the seam's existing transaction. Four properties are load-bearing:

- **Idempotent by introspection, not by error text.** Live columns are reflected first and a column already present emits **no DDL at all**; the error-catch survives only as a lost-race backstop.
- **The SQL type is compiled from the model metadata**, not written out, so the DDL cannot drift from the model.
- **Nullable only, no default** — all SQLite permits on `ADD COLUMN`.
- An entry whose **table is absent**, or whose **column is no longer in the model**, is **skipped and warned** rather than raising.

**Why raw DDL rather than reusing `db/schema.py`'s existing `introspect` / `add_columns` primitives:** `schema.py` imports `engine.py`, so calling into it from the seam would **invert the `db/` layering** and need a deferred import to dodge the cycle.

**Where it fires, and where it does not.** The seam runs only where `init_db()` is called — the two setup flows, `create_database` and `import_all`. It **never runs at application startup**: the lifespan defers schema creation deliberately (the bullet above). So an instance that is **already configured and running** picks up a new column only through **feature 007's admin schema-sync page** or a re-import. The two mechanisms are **complementary, not redundant** — the seam owns the fresh-create/import path, the admin sync owns the running instance.

**Open question, deliberately not closed in this pass:** *should schema reconciliation ever run at startup?* The trade-off in one line — self-healing instances, against the deliberate deferred-schema lifecycle in which a cold instance boots with an open engine and **zero tables by design**.

### DB import/export

Every persistent model has gzipped-JSONL (`.jsonl.gz`) import/export, packaged in a zip. This is part of defining a model — extend the import/export logic in the same change that adds or alters a model.

- **Export** streams per row: the db layer iterates rows and invokes a `callback(row)`; the service serializes each to JSONL into the gzip stream. No bulk `SELECT *` into memory.
- **Import** streams line-by-line: the service reads JSONL, accumulates a batch (e.g. 100), and calls an `upsert_batch(items)` on the db layer. Import is **UPSERT** — idempotent, safe to re-run. `init_db()` creates/reshapes tables before import.
- **Extension point.** A persistent model plugs in by adding its `to_dict`/`from_dict` codec pair plus one ordered `TABLE_REGISTRY` tuple (shape `(zip_filename, model_class, to_dict_fn, from_dict_fn)`) in FK dependency (import) order, in `services/db_import_export.py`. The session-free `db/` primitives (`export_table`, `upsert_batch`) need no per-model change. **`users` is the first `TABLE_REGISTRY` entry** (feature 003), carrying the first `to_dict`/`from_dict` codec; feature 001's "empty `TABLE_REGISTRY`" precondition is **superseded** now that a model is registered. **`llm_servers` is the second entry** (feature 004), registered after `users`.
- **Entity id serialization.** Entity ids serialize as **strings** in JSONL — the `to_dict` codec emits `id` as a JSON string, and `from_dict` accepts **either a string or a legacy JSON number** (parsing via `int(...)`). This is the system-wide 64-bit id rule (snowflake ids exceed JS's 2^53, so a number would lose precision); the number-or-string acceptance keeps pre-snowflake archives importable. **Realized in code for the `users` codec** (`_user_to_dict` emits `str(user.id)`; `_dict_to_user` parses string-or-number) by `fast/001.snowflake-ids`. See `auth-ids.md` → "Conventions — entity ID strategy".
- **Natural-key ids are emitted and parsed verbatim — the one exception beside the rule above.** `AssistantMode` is the **first codec whose PK is a natural key**: `_assistant_mode_to_dict` emits `key` as-is and `_dict_to_assistant_mode` parses it as-is, **never** through `int()`. The link tables that reference it (`mode_tool`, `mode_subagent`) carry `mode_key` the same way while still string-coercing their own snowflake `id` / `sub_agent_id`. This is not a softening of the snowflake rule: the seeded five modes are keyed by a stable natural string precisely so the seeded rows and their links survive cross-instance export/import (see `assistant-config.md`), and coercing that key to an integer would corrupt an all-digit key. Both rules therefore live side by side — snowflakes stringify, natural keys pass through untouched. Shipped by feature `008.data-domain`.
- **Registry size as shipped: 20 entries**, through `chat_messages`. Feature 008 landed 16 of them, feature 021 added `book_author_prompts`, feature 014 added `chapter_author_prompts`, and features 009–013 added none. The canonical printed order is in `book-domain.md` → "The book-domain table registry", which is its single home — **including the one sanctioned exception to its FK-dependency ordering**, `chapter_author_prompts`, which is registered ahead of its parent `chapters` for adjacency. That exception is inert (no `PRAGMA foreign_keys=ON`, and import is a per-table UPSERT), and its reasoning lives with the order rather than here.
- **Column additions still owe codec changes even when no table is added.** Feature `011.chat-panel` widened `chats` and `chat_messages` with `llm_server_id` (emitted string-or-null), `model_name`, `sampling_params` and `reasoning`, and extended both codecs in the same change; **`TABLE_REGISTRY` order was unchanged**, because no table was introduced. Recording the stability explicitly matters — a reader comparing the registry across those two features should see nothing move and know that is correct.
- **A superseded column keeps its codec.** `Book.system_prompt` is dormant after feature `021.per-author-system-prompt` (nothing reads it), but it **retains its `to_dict` / `from_dict` handling** so archives written before 021 still import. Dropping a codec is a breaking change to every existing archive, independent of whether any code still reads the column. **`Chapter.system_prompt` got the same treatment at feature `014.chapter-skeleton`** — superseded by `ChapterAuthorPrompt` and read by nothing, its codec is untouched so that archives written before 014 still import. Two instances make this the rule, not a one-off: **a column that goes dormant keeps its codec; only the reading stops.**

### JSON-in-TEXT gated by a Pydantic model — a sanctioned pattern

A structured value may be stored as **JSON in a TEXT column** provided a Pydantic model gates every read and write of it. `Chat.sampling_params` (feature `011.chat-panel`) is the second instance, following `LlmServer.enabled_models`.

It was chosen over **nine typed columns** because the sampling parameter set is expected to be revised: with a JSON column a revision is a Pydantic edit with **zero schema migration**, whereas typed columns would route every revision through FEAT-005's drift-and-sync tooling (and, on a populated table, through the nullable-`ADD COLUMN` constraint recorded in `features.md` → "Remediation").

State plainly what this is **not**: it is **not a free dictionary**, and does not weaken the root `CLAUDE.md` no-free-dictionaries rule. The column's contents are parsed into `ChatSamplingParams` on the way out and serialized from it on the way in; no code ever sees an untyped `dict`. The gate is the condition of the pattern, not an implementation detail of one column — a JSON TEXT column with no model in front of it is a violation.

**`ChatMessage.tool_trace` is the third instance** (feature `024.chat-agent-loop`, gated by `ToolTrace` / `ToolTraceEntry` — `domain-chat.md`), and it differs from its two siblings in exactly one way, recorded once so the next instance does not have to rediscover where it belongs: **it is the only one whose read tolerates an unparseable stored value.** The gate returns nothing rather than raising, mirroring what the chat service already does for `sampling_params` at the **service** layer rather than in the model.

The rule the trio now establishes: **the Pydantic gate is mandatory; whether the gate *tolerates* bad stored data is a per-column decision**, driven by whether a bad value should break the read. A corrupt sampling blob must not silently become defaults on a write path; a corrupt trace must not stop an author from reading their own conversation.

Two settled policies govern how credentials cross the import/export boundary:

- **Export credential policy.** The `users` codec (and export) **includes credentials** — `pwdhash` and `jwt_signing_key` — so restored accounts can authenticate, as required by US-002 (restore-and-login). This makes today's export the **"full / backup" mode, and it is secret-grade**: an export archive must be handled as a secret because it carries live credential material. `LlmServer.api_key`, however, is **redacted on export** (feature 004): a `$ENV` token is a *pointer*, not a secret, so `$`-prefixed values (and `None`) are exported verbatim, while a **raw literal key is emitted as `null`** — an operator re-enters it after restore. This is a **scoped early slice** of the feature-007 sanitized-export target, applied to LLM keys only; the broader two-mode split (full vs. sanitized) covering `User` credentials is **still not built** — `pwdhash` / `jwt_signing_key` continue to export verbatim in today's full/backup mode. Feature 007's export **download** endpoint (`GET /api/admin/db/export`) now makes that full/backup archive **admin-reachable through a browser**, which **raises the priority** of the still-unbuilt sanitized-export mode for `User` credentials — the archive, which carries live `pwdhash` / `jwt_signing_key`, now leaves the server through an admin's browser. The **only remaining plaintext-export concern is `User.pwdhash` / `jwt_signing_key`**: `LlmServer.api_key` is already redacted on export (a raw literal is emitted as `null`; a `$ENV` pointer is kept), per the feature-006 rewrite.
- **Partial-import rollback — accepted limitation.** Import is a streaming, idempotent UPSERT. A corrupt or failed import raises `SetupError`, leaves the instance **unconfigured** (`set_db_ready` is **not** called), and is recovered by **retrying with a valid archive** — the idempotent UPSERT overwrites any partial rows. There is **no transactional rollback** of a partially-written import. This is a **deliberately accepted limitation**, justified by the idempotent-UPSERT plus unconfigured-on-failure design: a half-written instance is never treated as ready, and a clean retry converges it.

## Vector storage — LanceDB sidecar

LanceDB (`lancedb>=0.6`) provides semantic search alongside SQLite. It is a **sidecar index**: it is **rebuilt from the SQLite source rows on import, not exported**. Treat SQLite as the source of truth; LanceDB is a derived index that can always be regenerated. As of feature 007, `db/vector.py` exposes a real **`rebuild_index()`** that connects to the configured LanceDB dir, **drops/recreates the sidecar tables (a full reset)**, and iterates a module-level **`VECTOR_SOURCE_REGISTRY`**. The rebuild-on-import contract stands as described; the sidecar is always regenerated from SQLite source rows and is never exported.

**The registry is no longer empty.** `CodexEntry` is the first vector-backed model, closing the embed-content bridge feature 007 deferred. The registry entry shape also **widened** — from `(model_class, text_extractor)` to a typed entry carrying a source-kind discriminator, a row selector and a **chunker** — because one source row now produces many vectors. `services/embedding.py` (the module 007 explicitly did not build) is the single point where text becomes vectors, resolving the FEAT-004 designated embedding server. Full design, including chunking, incremental maintenance, dimension handling and failure modes: **`retrieval.md`**.

It arrived in **two steps**, and the intermediate state shipped, so the sequence is recorded rather than smoothed over: feature `008.data-domain` created the `codex_entries` table as an ordinary data class and registered **no** vector source (the registry stayed empty through that whole feature); feature `013.codex` then registered the source, widened the entry shape and widened `db/vector.py` around it. **`VECTOR_SOURCE_REGISTRY` now holds exactly one entry, `codex_entry`.**

## Configuration & secrets

- Local config lives in `.env.local` (gitignored), loaded via `python-dotenv` / `pydantic-settings`.
- **Provider and LLM-server settings are stored in the database**, not in a settings file, so they can be managed at runtime through the Admin SPA.
- API keys use `$ENV_VAR` indirection: a stored value such as `api_key = "$OPENAI_API_KEY"` is resolved from the environment **at use time**. Raw key values are **never returned** in API responses — the API surfaces the indirection token, not the secret.

### Web search settings (feature `011.chat-panel`)

Two settings were added for the `web_search` tool, both on `backend/app/settings.py` and both following the existing `Field(default=..., validation_alias="BOOKWRITER_...")` convention: the Google Custom Search **api-key reference** and the **search-engine id**. Neither holds a secret directly — both hold **`$ENV_VAR` pointers**, resolved at use time through `services/secrets.py::resolve_env_ref`, the same single indirection point `LlmServer.api_key` uses. The resolved key never reaches the tool's output or the logs.

Record the transport plainly, because the requirement's wording invites the wrong reading: web search is a **direct `httpx` call to the Google Custom Search JSON API — not an MCP client**. The product's "MCP" phrasing is generic, and `assistant-config.md` defines tools as **plain backend functions** in a code-defined registry. The shipped shape is therefore complete as designed and must **not** be read as a missing MCP integration to be filled in later.
