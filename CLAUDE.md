# BookWriter

LLM-assisted authoring of long-form texts (books and other large documents) — a multi-user web app with a FastAPI backend and two React SPAs.

> This file is the primary guidance for agents and contributors. It covers the tech stack, how to build and test, project layout, and the enforced conventions. Full detail lives in `docs/architecture/`.

This repository documents **technology and conventions only**. The book/document domain model (entities, generation pipeline) is deliberately **not** designed here and is deferred to a later session. Do not invent domain entities.

## DEV Environment

- **OS**: Windows 11
- **Preferred shell**: PowerShell (use PowerShell over bash when possible)
- **Path separators**: forward slashes (`/`) for all paths and file names, in both PowerShell and bash

## Prod Environment

- Docker Compose
- Static nginx for the frontend, reverse-proxying `/api` to the backend

## Tech Stack

| Area | Choice |
|------|--------|
| Backend language | Python 3.13 |
| Backend framework | FastAPI (async) + uvicorn |
| Relational DB | SQLite via SQLModel + aiosqlite (async) |
| Vector DB | LanceDB sidecar (semantic search) |
| Validation | Pydantic 2 + pydantic-settings |
| Auth | PyJWT (HS256, per-user key) + bcrypt |
| LLM client | `llm-client` git dependency (module `llm`) |
| Backend tests | pytest + pytest-asyncio + httpx |
| Frontend language | TypeScript 5.8 (strict) |
| Frontend framework | React 19 |
| Bundler | Vite 6 (multi-page, `appType:"mpa"`) |
| UI | Mantine v7 + @tabler/icons-react + react-markdown |
| State | MobX 6 + mobx-react-lite only |
| Routing | react-router-dom 7 |

## Build & Test Commands

Agents (coder, fast-coder, verifiers, fixers) read commands from this section. If the area you're touching isn't covered here, ask before inventing a command.

- **Backend dev server**: `cd backend && .venv/Scripts/uvicorn app.main:app --port 8185 --reload`
- **Backend tests**: `cd backend && .venv/Scripts/python -m pytest`
  - No separate static type-check is configured for the backend.
  - **Python path convention**: always invoke Python via `.venv/Scripts/python` (Windows venv layout); never call `python` from PATH inside this project.
- **Frontend dev server**: `cd frontend && npm run dev` (Vite on port 8194)
- **Frontend build (= typecheck + bundle)**: `cd frontend && npm run build`
  - Internally runs `tsc && vite build`. Treat this as the frontend typecheck-and-bundle command.
- **Frontend typecheck only (no bundle)**: `cd frontend && npx tsc --noEmit`
- **Linter**: none configured — do not run lint commands unless added here later.

## Project Structure

```
BookWriter/
  backend/            FastAPI app: app/{routes,services,db,models}/, tests/, pyproject.toml, .venv
  frontend/           Vite MPA: index.html + admin/index.html + login/index.html;
                      src/{api,types,utils,components,user,admin,login}/, theme.ts, global.css
  nginx/              dev.conf + prod.conf
  docs/               architecture/ + plans/
  docker-compose.dev.yml, docker-compose.prod.yml
  start.ps1, build.ps1
  .env.local          (gitignored)
  CLAUDE.md
```

- `docs/architecture/` — finalized architecture and design documentation
- `docs/plans/` — feature planning and the planner/coder pipeline contract (tracked in git)
- Every project subfolder has its own `CLAUDE.md` for context.
- Planning docs go to `docs/plans/`, **not** `~/.claude/plans/`.

## API Typing — Full Stack

- **All API contracts are strictly typed on both sides** — no `any`, no untyped data.
- **Backend**: Pydantic `BaseModel` for all request/response schemas.
- **Frontend**: hand-written TypeScript `.d.ts` interfaces in `src/types/` matching backend schemas exactly.
- **No free dictionaries** on the backend, **no `any`** on the frontend.

## Backend Layer Separation (enforced)

Strict 4-layer separation under `backend/app/`:

- **`routes/`** — HTTP only: parse request, call a service, return response. No business logic, no DB queries.
- **`services/`** — business logic and orchestration. **No `session`, `AsyncSession`, `select()`, `session.exec()`, or `session.add()`** allowed here.
- **`db/`** — session-free data-access layer. All sessions created internally; ORM types never leak out. One module per entity.
- **`models/`** — SQLModel tables + Pydantic schemas (under `models/schemas/`). No logic.

Dependency direction: `routes → services + db`; `services → db` (never import routes); `db → models` only.

Import style — namespace modules: `from app.db import users` then `await users.get_by_id(id)`. Services imported as `from app.services import auth as auth_service`.

Typing discipline: Pydantic `BaseModel` for all API/tool schemas, `SQLModel` for tables, `TypedDict` for internal data passing — no free dictionaries, no untyped data.

See `docs/architecture/backend.md`.

## Frontend Conventions (enforced, summary)

- **MobX only.** No Redux, Zustand, React-Query, React-Context, or runtime schema validation (no zod).
- **`observer` on every component** — no exceptions.
- State lives in a `<Page>State` / `<Component>State` class next to the component. All effectful operations are external functions `(state, args, signal)` using `runInAction`. Async resources are a trio (`data` / `dataStatus: 'idle'|'loading'|'ready'|'error'` / `dataError`).
- Page = route = fresh state instance (React Router `key={id}` forces remount). Each page loads its own data by URL id; deep-linkable; no cross-page callbacks; backend is the source of truth. URL query params are the filter/sort/mode persistence layer.
- No custom `useX` hooks. `useState` only to hold a stable state-class instance. `useEffect` only at page level (mount-load / unmount-cleanup). No `useCallback` / `useMemo` / `useReducer`.
- Forms: drafts in state, validation as `get` computeds, server errors merged separately (do **not** use Mantine `useForm`).
- All HTTP isolated in `src/api/`. Tests mock the `api/` module, not `fetch`.

See `docs/architecture/frontend.md`.

## DB Import/Export

- **Every DB-persistent model must have JSONL import/export support** — gzipped JSONL files (`.jsonl.gz`).
- Update the import/export logic in the **same change** whenever a model is added or altered. Not optional.
- Import is **UPSERT** (idempotent) and streaming (line-by-line, batched); export streams per-row. No bulk in-memory load.
- The LanceDB vector index is **rebuilt from source rows on import, not exported**.

## Config & Secrets

- Local config in `.env.local` (gitignored).
- Provider / LLM-server settings are stored **in the database**, not in a config file.
- API keys use `$ENV_VAR` indirection: a stored value like `api_key = "$OPENAI_API_KEY"` is resolved from the environment at use time. Raw key values are **never returned** in API responses.
- The SQLite DB path is overridable via the `BOOKWRITER_DB_PATH` environment variable.
