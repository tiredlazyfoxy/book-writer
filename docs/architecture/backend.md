# Backend Architecture

FastAPI application (Python 3.13, async) with SQLite storage via SQLModel, a LanceDB sidecar for semantic search, JWT auth, and LLM integration via the `llm-client` dependency. This document is the **index** for the backend architecture: it holds the cross-cutting rules (layers, typing, dependencies, the LLM-client rule, logging, tests) and the decision history; the detailed area records live in the four files under `backend/`.

**Book-domain coverage.** The book/document entity model is **not** defined here — it lives in `domain-model.md` (the index) and the five `domain-*.md` area files under it, with `authorization.md` (book-scoped access) and `retrieval.md` (the embedding/vector bridge). The backend-side consequences of that design (module map, widened registries, the concurrency contract) live in `backend/book-domain.md`. The FEAT-013 assistant is now **partly** covered: the configuration model is in `assistant-config.md` and the runtime slice — mode determination, prompt composition, tool gating, the `chat_with_tools` loop, sub-agent delegation, model resolution and the SSE frame vocabulary — is in `assistant-runtime.md`. **Still uncovered — do not infer it:** context/content assembly, token-level canvas streaming, and token budgeting. See `domain-chat.md` for the full boundary.

## Backend documents

This file is the index and holds the cross-cutting rules (layers, typing, dependencies, the LLM-client rule, logging, tests) and the decision history. The detail lives in four area files:

- `backend/persistence.md` — relational storage & the deferred-schema startup lifecycle (including the mode seed on both first-run paths), gzip-JSONL import/export (codecs, the 19-entry `TABLE_REGISTRY`, natural-key ids, the gated JSON-in-TEXT pattern, credential policy), the LanceDB vector sidecar, and config/secrets including the web-search settings.
- `backend/auth-ids.md` — the per-user-key JWT + bcrypt auth scheme and the system-wide snowflake entity-ID strategy (spec, string-at-JSON-boundary serialization, migration stance).
- `backend/features.md` — the as-shipped route/DTO inventory: `User`/`LlmServer`, LLM-server connections (FEAT-004), database consistency & management (FEAT-005), the FEAT-020 admin config editor, the codex family, the retrieval subsystem, the per-author system prompt, and the `--reasoning-format none` deployment requirement.
- `backend/book-domain.md` — the backend-side consequences of the book domain: the as-shipped module map, the 19-entry table registry in canonical FK order, the vector registry, Stage-4-columns-at-Stage-2, and the 409 concurrency rule.

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

## LLM client

LLM communication goes exclusively through the `llm-client` dependency, imported as the module `llm`. It supports OpenAI-compatible servers and llama-swap. Tool schemas are generated from Pydantic models (`pydantic_to_openai_tool()`) rather than hand-written JSON. Do not make direct outbound HTTP calls to LLM providers from application code — route them through `llm`.

**Deployment requirement — llama.cpp must run with `--reasoning-format none`.** Assistant thinking is visible only when the server inlines reasoning into `content`; the streaming tool loop in `llm-client` never reads `reasoning_content`, so out-of-band reasoning is discarded inside the library. A server without the flag **degrades silently to content-only** — no error, no log, just a missing feature. Full reasoning and the consequence for `services/chat_turn.py`: `backend/features.md` → "Deployment requirement".

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
- **2026-07-25 — The data floor shipped (feature `008.data-domain`).** Sixteen tables and their codec pairs landed in one feature: the five FEAT-020 config tables plus eleven book-domain tables, with `TABLE_REGISTRY` reaching 18 entries in canonical FK order. Three choices are recorded because they are the ones a later reader would question. (1) The **FEAT-020 config block lands before `books`** — those five tables are instance-global, the same class as `users` / `llm_servers`, and a sub-agent's codec references an `LlmServer`; putting them inside the book block would break import order. (2) **Stage-4 columns landed at Stage 2**, nullable and unused (`Chapter.state = closing`, `Chapter.summary_status`, `Book.moderation_reason` / `moderated_by` / `moderated_at`, `chapter_note_changesets` and its `status`) — chosen because SQLite cannot `ADD COLUMN … NOT NULL` without a default on a populated table, so a column added later against live data arrives nullable anyway; landing them now makes Stage 4 pure behaviour with no DDL. (3) `AssistantMode` took a **natural-key PK** emitted and parsed **verbatim**, the first codec not to string-coerce its id — a deliberate narrow exception so the seeded five modes and their link rows survive cross-instance export/import. FEAT-005's drift report needed no change, as designed. See `backend/book-domain.md` and `backend/persistence.md`.
- **2026-07-25..26 — First slice of the FEAT-013 assistant runtime (feature `011.chat-panel`).** Shipped per-chat model + sampling selection (the `(llm_server_id, model_name)` pair mirroring `SubAgent`, plus `sampling_params` as gated JSON-in-TEXT), the code-defined `TOOL_REGISTRY` with `web_search` as its only entry, the four-layer prompt composer, and **the repo's first SSE endpoint** — the streaming chat turn. Two shapes were **deliberately temporary and are named as such**: (a) `chat_with_tools` is called from exactly one place (`services/chat_turn.py`) so a manual `chat`-in-a-loop driver could replace it without touching config, registry, gating or composition; (b) tool gating ran under an interim rule where **a null mode allows the whole registry**, because no mode-bearing subject existed yet. Both were addressed by feature 013: the null-mode widening was **replaced** by real gating (with a code-defined base allowlist for subjects that have no mode), while the `chat_with_tools` seam **survived** — the shared-canvas write did not force it open, at the accepted cost that a canvas draft arrives whole rather than streamed. See `assistant-runtime.md`.
- **2026-07-26 — The FEAT-020 admin config editor (feature `012.assistant-config-editor`).** The fourth admin route family: `/api/admin/assistant-config`, eight endpoints over the five config tables. Two decisions carry beyond it. A **duplicate sub-agent name answers 409** — the **first 409 outside user administration** — following `services/admin.py`'s `username_taken` precedent rather than inventing a taxonomy, because a uniqueness collision on a human-chosen name is the same failure in both places. And both save endpoints are **full-replace `PUT`, not partial `PATCH`**, so the `(llm_server_id, model_name)` pair is always explicitly present and `null` + `null` unambiguously means *inherit*; a partial PATCH cannot distinguish "leave it alone" from "clear it" on a paired field. This deliberately does not mirror `services/chats.py:update_chat`'s partial-PATCH shape. See `backend/features.md` and `assistant-config.md`.
- **2026-07-27 — The codex subsystem and the retrieval pipeline (feature `013.codex`).** Shipped the codex route family, the version rows, the embedding service and the widened LanceDB sidecar — closing the vector-pipeline boundary feature 007 opened, in code rather than only on paper. Two structural decisions are recorded. (1) **The embedder is injected into `db/vector.py` from the composition root** (`app/main.py`) rather than imported: `rebuild_index` must embed, `db → services` is forbidden by the layer rule, and one of `rebuild_index`'s two callers itself lives in `db/`. Injecting the batch embedder and dimension probe as callables at startup satisfies the requirement without inverting the dependency direction — a layer-rule workaround at the composition root, recorded so it does not read as drift. (2) **The incremental index never raises.** `services/codex_index.py` returns every failure — no provider, unreachable, dimension mismatch, sidecar error — as a typed outcome logged at warning level, because its caller is the author's save path, which must succeed regardless. The index is derived from SQLite, so any failure is recoverable by a rebuild; trading a hard failure for a recoverable gap is the right side of that asymmetry. See `retrieval.md`.
- **2026-07-29 — `Book.system_prompt` superseded by the per-author `BookAuthorPrompt` (feature `021.per-author-system-prompt`).** The book-wide prompt is replaced by one prompt per author per book, with its own table and its own route pair. The **column was retained, not dropped**: `db/engine.py` exposes only an *additive* migration seam and the project has no Alembic, so there is **no supported DROP COLUMN path** — a dead-but-documented column beats an unsupported migration. It is still required, still written `""` at book creation, and still round-trips through its JSONL codec so pre-021 archives import. This diverges from product FEAT-019 and the divergence is **open**, not reconciled — see `domain-model.md` → "Product divergences", item 5.
- **2026-07-24 — Split into `backend.md` + `backend/*.md`.** The single dense `backend.md` was carved into this index plus `backend/persistence.md`, `backend/auth-ids.md`, `backend/features.md` and `backend/book-domain.md`, following the folder's `domain-*.md` / `frontend-workspace.md` split convention and the ~400-line file rule. **Organisational only** — no design decision changed.
