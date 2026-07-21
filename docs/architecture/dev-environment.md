# Development Environment

How to run BookWriter locally, the ports and launcher, the dev proxy, Docker Compose for dev and prod, and the environment variables. Tech-level only; no domain content — the book/document domain is specified as requirements in `docs/product/` (FEAT-001..018) and its architecture is not yet designed.

## Prerequisites

- Python 3.13
- Node.js (LTS) + npm
- Git (the backend pulls the `llm-client` git dependency)

## Services & ports

| Service | Port | URL |
|---------|------|-----|
| FastAPI backend (uvicorn) | 8185 | `http://localhost:8185` |
| Vite dev server (User + Admin + Login) | 8194 | `http://localhost:8194` |

## Backend setup

- Local `.venv` in `backend/` (Windows `Scripts/` layout).
- Dependencies via `pyproject.toml` (`pip install -e .` — the `dev` extra adds pytest/httpx).
- Dev server: `cd backend && .venv/Scripts/uvicorn app.main:app --port 8185 --reload`.
- Tests: `cd backend && .venv/Scripts/python -m pytest`.

## Frontend setup

- `cd frontend && npm install`, then `npm run dev` (Vite on `:8194`).
- Build: `npm run build` (`tsc && vite build`). Typecheck only: `npx tsc --noEmit`.

## Vite `/api` proxy (dev)

The Vite dev server proxies `/api` to the backend so dev routing matches production (where nginx mounts the backend at `/api`):

```ts
// vite.config.ts
server: {
  port: 8194,
  proxy: { '/api': 'http://localhost:8185' },
}
```

With the proxy in place the frontend and backend are same-origin from the browser's view, so CORS is not normally needed in dev. If a workflow bypasses the proxy, enabling CORS on the backend for `http://localhost:8194` is the fallback.

## `start.ps1` launcher

`start.ps1` is a PowerShell launcher with switches for the common dev tasks:

- `-app` — start the backend (uvicorn on `:8185`).
- `-ui` — start the Vite dev server (on `:8194`).
- `-test` — run the backend test suite. This switch points the app at a throwaway test database by setting the DB-path environment variable (below) before invoking pytest, so tests never touch the dev database.

## Environment variables

Local values live in `.env.local` (gitignored), loaded via `python-dotenv` / `pydantic-settings`.

| Variable | Purpose |
|----------|---------|
| `BOOKWRITER_DB_PATH` | Overrides the SQLite DB file path. Dev default: `backend/data/bookwriter.db`. The `-test` switch points this at a temporary DB. |
| `OPENAI_API_KEY` | Resolved at use time via `$OPENAI_API_KEY` indirection from a stored provider config. Never returned in API responses. |
| `LLAMA_SWAP_URL` | Base URL of a llama-swap server, when that backend is used. |

Provider and LLM-server settings themselves are stored **in the database** (managed via the Admin SPA), not in environment variables — the env vars above hold only secrets (resolved by `$ENV_VAR` indirection) and the DB path. Additional provider secrets follow the same `$ENV_VAR` indirection pattern; keep their names provider-generic.

## Docker & production

- **Dev**: `docker-compose.dev.yml` builds the images from source.
- **Prod**: `docker-compose.prod.yml` runs pre-built images.
- **nginx** reverse-proxies in production: it serves the three static frontend builds (`/`, `/admin`, `/login`) and proxies `/api` to the backend, so everything is one origin and CORS is unnecessary. Config lives in `nginx/` (`dev.conf` and `prod.conf`).
- The SQLite database is a mounted volume in production so it survives container restarts; `BOOKWRITER_DB_PATH` points at the mounted path.
- Image names are project-specific; use BookWriter-neutral names (e.g. `bookwriter-api` for the backend and `bookwriter-gate` for the nginx/frontend image), or a placeholder until the registry is decided. *(Left as a placeholder — no registry/image naming was specified.)*
