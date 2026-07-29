# Backend — Shipped Feature Records

Part of the backend architecture — see `../backend.md` for the index.

These are the as-shipped records for the backend's shipped route families and subsystems: features 003/004/006/007 (the `User` and `LlmServer` domain models, LLM-server connections, database consistency & management), and features 011/012/013/021 (the FEAT-020 assistant configuration, the codex and retrieval subsystems, and the per-author system prompt).

## Deployment requirement — llama.cpp must run with `--reasoning-format none`

**Realizes:** FEAT-013 (operational constraint). Recorded first because it is invisible in code and its failure mode is silent.

Assistant *thinking* is visible to an author **only when the llama.cpp server inlines reasoning into `content`** — that is, only when the server runs with `--reasoning-format none`. This is not a preference; it is the only shape BookWriter can consume.

The reason is inside the `llm-client` dependency. `chat_with_tools(stream=True)` routes through the library's `_stream_openai_tools_response`, which reads only `delta["tool_calls"]` and `delta["content"]` and **never** `delta["reasoning_content"]`. Reasoning sent out-of-band is therefore discarded *inside the library* and reaches neither the `on_delta` callback, nor the call's return value, nor the trace — there is no place in BookWriter's code where it could be recovered. The library does have a reasoning-aware parser, but it is reachable only from plain `chat()`, which has no tool loop and so cannot serve a turn.

The consequence, as shipped: BookWriter splits `<think>` / `</think>` **itself**, in `services/chat_turn.py`'s `ThinkSplitter`, out of the inlined content stream. A server configured **without** the flag does not error — it **degrades silently to content-only**, and the author simply never sees a thinking block. An operator has no signal that anything is wrong. That silent feature loss is why the requirement is documented at this level rather than left in a deployment script.

The index-level pointer is in `../backend.md` → "LLM client".

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

Nine endpoints, every one behind `Depends(require_role(admin))`. The **static `/embedding` routes are declared before `/{server_id}`** so path capture doesn't swallow them. Error → status taxonomy: missing-field / invalid-backend-type / env-not-set → **400**, not-found → **404**, probe-failed → **502**, delete + clear-embedding → **204**, non-admin → **403**. See **`docs/architecture/quick-reference.md`** for the endpoint and DTO table — that is this folder's dense agent-first index of concrete endpoints and DTOs, and is **not** `docs/product/quick-reference.md` (the product id registry). Every endpoint/DTO table referenced from this file lives there.

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

### The vector-pipeline boundary (deliberately partial — **closed on paper 2026-07-24, closed in code 2026-07-27**)

**Status:** this boundary is fully closed. The 2026-07-24 architect pass closed it *on paper* (`retrieval.md` is the current design and supersedes the "DEFERRED" bullet below); feature `013.codex` closed it **in code** — `services/embedding.py` exists, `db/vector.py` is widened, and the registry has its first entry. See "The retrieval subsystem" below for the as-shipped record. The record that follows describes what feature 007 shipped and why it stopped where it did.

Feature 007 delivers the rebuild **operation**, the index **reset**, and the **empty `VECTOR_SOURCE_REGISTRY`** seam — but **not** the embed-content bridge. Concretely:

- `VECTOR_SOURCE_REGISTRY` is a module-level list that Stage-2 vector-backed domain features append `(model_class, text_extractor)` entries to. It is **empty in Stage 1**, so a rebuild today resets the sidecar and indexes **0 rows**.
- `services/db_admin.py::rebuild_vector_index()` **validates the 006 embedding designation** — `get_embedding_server()` must return a row *and* its `embedding_model` must be set — raising `DbAdminError(no-embedding-provider)` (→ 400) otherwise. With the empty registry it then resets the index and returns **0**.
- The **embed-content bridge is DEFERRED** to the first vector-backed domain model (the Stage-2 codex, behind the architect gate): **no** `embed_texts`, **no** `services/embedding.py`, **no** vector-dimension detection/cache is built now.

Chosen so that the operation and its real dependency on the 006 embedding designation exist and are exercised, while the large embedding pipeline stays scoped out until there is actual searchable content to embed. Users and llm_servers are configuration, not searchable content — there is nothing to index yet.

### Convergence note — a future refactor (not built)

A shared `validate_archive` could later unify two currently-separate refusal paths: 003's setup-import (`services.setup.import_database` → `SetupError`) and 007's admin-import (`db_admin.import_database` → `DbAdminError(invalid-archive)`). Both wrap the same `import_all` and differ only in the readiness-flip and the error type. Recorded as a deferred refactor, deliberately not built now.

## Books and membership (feature `009.books`) — **as-shipped record owed**

**This is a known gap, not an oversight.** Feature `009.books` shipped the books/membership route family — book creation and listing, the detail and reader projections, the settings mutations (archive/unarchive, transfer, add/remove member, visibility) — together with `services/authz.py`, the authorization spine every later book-scoped family depends on. Every other shipped family is inventoried in this file; this one is not.

It is missing because **no `outcome.md` item asked for it**: 009's outcome targeted `authorization.md`, `domain-book.md`, `frontend-workspace.md` and `docs/product/`, and named this file nowhere. The record is therefore **owed**, and deliberately left blank rather than reconstructed from source at finalization time — writing it from a source read would risk stating something the feature did not actually ship.

Until it is written, the authoritative sources are `docs/plans/009.books/status.md` (`## Files Changed` and `## Skeleton`) and `authorization.md` for the capability matrix and the `book_access` dependency.

## Assistant configuration — the FEAT-020 admin editor

**Realizes:** FEAT-020. Shipped by feature `012.assistant-config-editor`.

The fourth admin route family: admin-managed configuration of assistant **modes** and **sub-agents**, and of which tools and sub-agents each may use. It spans all four layers —

- `db/assistant_modes.py`, `db/sub_agents.py`, `db/mode_tools.py`, `db/subagent_tools.py`, `db/mode_subagents.py` (session-free, one per table),
- `services/assistant_config.py` (the CRUD and the validate-then-write save path),
- `models/schemas/assistant_config.py` (the DTOs),
- `routes/admin/assistant_config.py` (HTTP only).

**Route family** — prefix `/api/admin/assistant-config`, eight endpoints, every one behind `Depends(require_role(admin))`: `GET /tools`, `GET /modes`, `PUT /modes/{mode_key}`, `GET /sub-agents`, `POST /sub-agents`, `PUT /sub-agents/{sub_agent_id}`, `POST /sub-agents/{sub_agent_id}/disable` and `.../enable`.

**Error → status taxonomy:** validation refusals — an unknown tool name, an unknown or disabled sub-agent, an unknown mode key, a blank name, a half-set model pair — → **400**; an absent mode or sub-agent → **404**; a **duplicate sub-agent name** → **409**; non-admin → **403**, produced by `require_role` rather than by the service.

The **409** is worth naming: it is the **first 409 outside user administration**, and it follows the `services/admin.py` `username_taken` precedent deliberately rather than inventing a taxonomy — a uniqueness collision on a human-chosen name is the same failure in both places and should answer the same way.

The configuration **model** — the fixed five modes, the natural-key PK, disable-not-delete on sub-agents, the code-defined `TOOL_REGISTRY`, the three selection tables and the replace-set save semantics — is **not duplicated here**. See `assistant-config.md`. The runtime that consumes this configuration is a different subsystem again: see `assistant-runtime.md`.

## The codex route family

**Realizes:** FEAT-017, FEAT-018. Shipped by feature `013.codex`.

The fifth route family and the first author-facing (non-admin) one after books. It spans `db/codex_entries.py` and `db/codex_entry_versions.py`, `services/codex.py` (CRUD, version rows, the collaboration-mode rule) and `services/codex_index.py` (incremental vector maintenance), `models/schemas/codex.py`, and `routes/codex.py`.

**Four endpoints:**

- `GET /api/books/{book_id}/codex` — list/search
- `POST /api/books/{book_id}/codex` — create
- `GET /api/books/{book_id}/codex/{entry_id}` — read one
- `PUT /api/books/{book_id}/codex/{entry_id}` — edit

**Error → status taxonomy:** **400** for a kind/name violation or an edit of an archived entry; **403** for a reader of a public book and for the proposal-mode refusal; **404** for a non-member of a private book (existence hiding, on all four routes) and for an entry that does not resolve inside the book; **409** for a stale `modified_at`.

**Deliberate absences** — each has an owner, so a later feature does not re-litigate them:

- **No DELETE.** A codex entry is *archived*, not deleted — and archive itself is `017.codex-archive-restore`'s, not this family's.
- **No history endpoints.** `019.codex-history` builds the view and restore surface; the `CodexEntryVersion` rows it will read are nevertheless **written here**, on every edit.
- **No cross-book copy.**

The entity model, versioning and collaboration-mode reasoning live in `domain-codex.md`; the vector side lives in `retrieval.md`. Neither is duplicated here.

## The retrieval subsystem

**Realizes:** FEAT-017 (search), UC-078. Shipped by feature `013.codex`.

`services/embedding.py` (the single point where text becomes vectors, resolving the FEAT-004 designated embedding server) and the widened `db/vector.py` (the LanceDB sidecar: chunk table, upsert/delete/search helpers, the widened `VECTOR_SOURCE_REGISTRY`), with `services/codex_index.py` as the incremental-maintenance composer.

**This closes the "bridge deferred to the first vector-backed domain model" note feature 007 left in this file** — see "The vector-pipeline boundary" above. It is now closed *in code*, not only on paper: the embed-content bridge exists, dimension probing exists, and the registry has its first entry.

Full design — chunking, incremental maintenance, dimension handling, the injected-embedder placement and the failure modes — is in `retrieval.md`.

## Per-author system prompt

**Realizes:** FEAT-019 (book half, as redefined). Shipped by feature `021.per-author-system-prompt`.

Replaces the book-wide system prompt with one prompt **per author, per book**. It spans `models/book_author_prompt.py`, `db/book_author_prompts.py`, `models/schemas/book_author_prompts.py`, `services/book_author_prompts.py` and `routes/book_author_prompts.py`.

**Two endpoints:** `GET` and `PUT /api/books/{book_id}/system-prompt`.

**Response shape:** `book_id`, `system_prompt`, and a nullable `modified_at`. There is **no `user_id`** on it, deliberately — the subject is always the caller, so returning an id would invite the reading that another author's prompt is addressable through this route. It is not.

**Error → status taxonomy:** **401** with no token; **404** for a private book the caller has no relationship to (produced by `resolve_book_access`, not re-derived here); **403** for a logged-in non-member of a book they can see; **200** for a member acting on their own prompt — on both the create and the update path.

**Deliberate absences**, each with its reason, because these are exactly what a later feature would otherwise re-open:

- **No DELETE.** The empty string *is* "no prompt"; a required column with `""` as a legal value needs no deletion verb.
- **No `POST`.** `PUT` is the upsert and answers **200** whether the row existed or not, so a client never has to know which case it is in.
- **No field on `BookDetailResponse`.** A per-caller value cannot ride on a book-shaped DTO — two authors reading the same book would need different bodies for the same resource. It gets its own endpoint for that reason.

The divergence this creates against `docs/product/` FEAT-019 is recorded in `domain-model.md` → "Product divergences" (the fifth item, still open).
