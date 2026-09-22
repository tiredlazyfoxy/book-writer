# Fast feature 004 — deployment

| Status | Verifier | Date       |
|--------|----------|------------|
| done   | PASS     | 2026-08-07 |

DoD-11 met by the verifier. DoD-1..DoD-10 are `[manual/live]` and recorded as
requires-live-run — they are confirmed by the operator's Docker run, not by an agent.

## Files Changed

- `Dockerfile` — two-stage all-in-one image (node build stage → full python:3.13 runtime with nginx + supervisor).
- `.dockerignore` — trims the repo-root build context and keeps secrets out of the image.
- `docker/supervisord.conf` — runs uvicorn (127.0.0.1:8185) and nginx (:80) in one container, both logging to stdout/stderr.
- `nginx/prod.conf` — in-image server block: `/api/` proxy with the SSE trio plus the five SPA static locations.
- `nginx/dev.conf` — dev-compose front door proxying to the `backend` and `frontend` services, with HMR upgrade headers on `location /`.
- `docker-compose.prod.yml` — one `bookwriter` service, `8194:80`, `./data` bind mount, `/api/health` healthcheck.
- `docker-compose.dev.yml` — three stock-image services with source bind-mounts and named pip/node_modules volumes, no build step.
- `build.ps1` — Windows build machine: tag from git, build, save through 7z, stage to `$DOCKER_STORE`, optional `-Push` scp.
- `update.sh` — Linux deploy server: load image, refresh compose/.env, `docker compose up -d` (LF line endings).
- `.env.example` — commented env template for the values the DB's `$ENV_VAR` api_key pointers resolve against.
- `.gitignore` — appended `/data/` and `*.7z`.

## Skeleton

n/a — config-only feature, no signatures to freeze.

## Notes & Issues

- `backend/app/main.py` hardcodes `logging.basicConfig(level=logging.DEBUG)` — noisy for a production container; making it env-driven is a backend source change and is out of scope here.
- `backend/app/settings.py`'s `lancedb_dir` has no `BOOKWRITER_` env alias, unlike every sibling setting; worked around by setting the bare `LANCEDB_DIR` in both the image ENV and both compose files. Adding a `BOOKWRITER_LANCEDB_DIR` validation alias is a backend change, out of scope.
- A fresh container boots with zero tables and `db_ready=False` **by design** — schema is created only through the first-run setup API, so no eager `init_db()` belongs in any entrypoint, supervisord program, or wrapper script.
- All eleven DoD items are `[manual/live]`: no `docker build` / `docker compose` was run here. `cd backend && .venv/Scripts/python -m pytest` (1233 passed) and `cd frontend && npm run build` were run and are green (DoD-11).
