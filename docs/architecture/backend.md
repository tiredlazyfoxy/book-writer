# Backend Architecture

FastAPI application (Python 3.13, async) with SQLite storage via SQLModel, a LanceDB sidecar for semantic search, JWT auth, and LLM integration via the `llm-client` dependency. This document defines the enforced structure, typing discipline, persistence approach, config/secrets pattern, auth scheme, and test harness. It does **not** define any book/document domain model — that is deferred.

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
- Schema is created with `SQLModel.metadata.create_all`. Schema evolution is handled by **in-code `ALTER TABLE` migrations** run at startup — **there is no Alembic**. Keep migrations idempotent and additive.
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

## Vector storage — LanceDB sidecar

LanceDB (`lancedb>=0.6`) provides semantic search alongside SQLite. It is a **sidecar index**: it is **rebuilt from the SQLite source rows on import, not exported**. Treat SQLite as the source of truth; LanceDB is a derived index that can always be regenerated.

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

## Logging

- Python standard `logging`, default output to console.
- `INFO` for incoming API requests and key lifecycle events; `DEBUG` for full flow (LLM request/response, tool calls, internal results).

## Test harness — pytest + httpx (in-process ASGI)

- Runner: `pytest` with `pytest-asyncio` in `asyncio_mode="auto"` (async tests need no per-test decorator).
- Tests exercise the app **in-process** via `httpx.AsyncClient` over `ASGITransport` — no live server, no real network.
- A fixture provides a temporary-SQLite `DbConfig` so each test run gets an isolated throwaway database; the app's db layer is initialized against it.
- Run with `cd backend && .venv/Scripts/python -m pytest` (see the root `CLAUDE.md` for the canonical command).
