# fast/004.deployment — Container image, compose stacks, build & update scripts

## Goal

Give BookWriter a serving layer: a single all-in-one Docker image (nginx +
uvicorn under supervisord) built from the repo root, a production compose stack
that publishes `8194:80` and bind-mounts an external `./data` folder for the
SQLite DB and the LanceDB index, a build-free dev compose stack, and the
Windows `build.ps1` / Linux `update.sh` pair that ship the image through a
`$DOCKER_STORE` share without a Docker registry.

**No application source is touched.** Every file below is a build/run
configuration artifact or a shell script.

## Source files

All new and at the repo root unless noted. This list **is** the coder's scope.

- `Dockerfile` — two-stage all-in-one image (node build stage → python runtime).
- `.dockerignore` — keeps the repo-root build context small and secret-free.
- `docker/supervisord.conf` — process supervision for uvicorn + nginx inside the image.
- `nginx/prod.conf` — in-image server block: five SPA static roots + the `/api` proxy.
- `nginx/dev.conf` — dev-compose front door: proxies to the `backend` and `frontend` services.
- `docker-compose.prod.yml` — one service, published port, `./data` bind mount, healthcheck.
- `docker-compose.dev.yml` — three stock-image services with source bind-mounts, no build step.
- `build.ps1` — Windows build machine: build, tag, save, 7z, stage to `$DOCKER_STORE`, optional scp.
- `update.sh` — Linux deploy server: load image, refresh config, bring the stack up.
- `.env.example` — commented template of the env vars the container may need.
- `.gitignore` — **modify only**: append `/data/` and `*.7z`. Nothing else changes.

## Test files

**None.** See *Definition of done*: the `[test]` set is empty. Dockerfiles,
compose files, nginx config and PowerShell/bash scripts have no meaningful
pytest or vitest surface, and every DoD item is tagged `[manual/live]` by a
locked decision. The test-coder has nothing to write for this feature and the
red gate is a no-op.

## Interface intent

These artifacts are configuration, not functions, so the intent is given as
prose per file. Everything the coder must not guess is stated here.

### `Dockerfile` — the build context is the **repo root**

Two stages.

**Stage `web`** — base `node:22-alpine`, `WORKDIR /app`. Copy
`frontend/package.json` and `frontend/package-lock.json` first, run `npm ci`,
then copy the rest of `frontend/` and run `npm run build`. Output is `/app/dist`.
(The lockfile-first ordering is what makes the dependency layer cacheable.)

**Runtime stage** — base **full `python:3.13`, not `-slim`**: `curl` is needed
for the healthcheck and `git` for the `llm-client` VCS dependency. In this
order:

1. `apt-get update && apt-get install -y --no-install-recommends nginx supervisor && rm -rf /var/lib/apt/lists/*`.
2. `rm -f /etc/nginx/sites-enabled/default`. **Required, not cosmetic** —
   Debian's `nginx.conf` includes *both* `conf.d/*.conf` and `sites-enabled/*`,
   so leaving the stock default site in place collides on `listen 80`.
3. The cache-friendly dependency layer, exactly:

   ```
   WORKDIR /app
   COPY backend/pyproject.toml ./
   RUN mkdir -p app && touch app/__init__.py \
    && pip install --no-cache-dir . \
    && rm -rf app *.egg-info
   COPY backend/ .
   ```

   The stub `app/__init__.py` is **deliberate**: `[tool.setuptools.packages.find]
   include = ["app*"]` makes an install with zero packages present fragile, so
   the stub gives setuptools something to find. uvicorn later runs with cwd
   `/app` and imports `app.main` off the filesystem, so the installed
   distribution itself is not needed once its dependencies are in place — which
   is why the stub and the egg-info are removed in the same layer. **Do not
   copy the reference project's version of this step**, which omits the stub.
4. `COPY --from=web /app/dist /usr/share/nginx/html`.
5. `COPY nginx/prod.conf /etc/nginx/conf.d/bookwriter.conf`.
6. `COPY docker/supervisord.conf /etc/supervisord.conf`.
7. `RUN mkdir -p /app/data`.
8. `ENV BOOKWRITER_DB_PATH=/app/data/bookwriter.db` **and**
   `ENV LANCEDB_DIR=/app/data/vector`. Note the second name is **bare** — the
   settings field has no `BOOKWRITER_` prefix. Both are required; setting only
   the first leaves the vector index outside the mount.
9. `EXPOSE 80` and `CMD ["supervisord", "-c", "/etc/supervisord.conf"]`.

There is **no entrypoint script** and **no schema bootstrap** — the app is
designed to boot with zero tables and be finished in the browser.

### `docker/supervisord.conf`

`[supervisord]` with `nodaemon=true` and its own logfile discarded. Two
programs, both `autorestart=true`, and both with stdout/stderr redirected to
`/dev/stdout` / `/dev/stderr` with the matching `*_logfile_maxbytes=0`, so
`docker logs` shows everything:

- `[program:api]` — `uvicorn app.main:app --host 127.0.0.1 --port 8185` with
  `directory=/app`. **Loopback-bound on purpose** (only nginx inside the
  container reaches it) and **no `--reload`**.
- `[program:nginx]` — `nginx -g "daemon off;"`.

### `nginx/prod.conf`

A single `server { listen 80; server_name _; root /usr/share/nginx/html;
index index.html; }` containing:

- `location /api/` → `proxy_pass http://127.0.0.1:8185/api/;` plus
  `proxy_set_header Host $host;`, `proxy_set_header X-Real-IP $remote_addr;`,
  and the SSE trio `proxy_buffering off;`, `proxy_cache off;`,
  `proxy_read_timeout 300s;`.
- **Five** static locations, mirroring the dev `spaFallback()` plugin's branch
  order: `location /admin`, `location /login`, `location /work`,
  `location /read` — each `try_files $uri $uri/ /<name>/index.html;` — and then
  `location /` → `try_files $uri $uri/ /index.html;`.
- `/assets/...` needs **no block**; it resolves through `location /` off `root`.
  Do not add a per-entry root — the five entries share one `assets/` graph.

`docs/architecture/dev-environment.md` warns that a three-entry `prod.conf`
would silently 404 `/work` and `/read`. All five must be present.

### `nginx/dev.conf`

`listen 80`. Two locations:

- `location /api` → `proxy_pass http://backend:8185;` (compose service name),
  with `Host`, `X-Real-IP` and `X-Forwarded-For` headers.
- `location /` → `proxy_pass http://frontend:8194;` **with
  `proxy_http_version 1.1;` and the `Upgrade` / `Connection "upgrade"` header
  pair**, so Vite 6's HMR websocket passes through. BookWriter sets no
  `server.hmr.path`, so the reference project's dedicated `/__vite_hmr`
  location does **not** apply — the upgrade headers must be on `location /`.

### `docker-compose.prod.yml`

One service, `bookwriter`:

- `image: iezious/bookwriter:latest`
- `ports: ["8194:80"]`
- `env_file: [.env]` — plain short form, no compose version floor;
  `update.sh` guarantees `.env` exists before it runs `up`.
- `environment:` — `BOOKWRITER_DB_PATH=/app/data/bookwriter.db` and
  `LANCEDB_DIR=/app/data/vector` (repeated here on purpose: the compose file is
  the operator-visible contract, and it must not depend on the image's ENV).
- `volumes: ["./data:/app/data"]` — **this is the external db folder**, relative
  to wherever the compose file sits on the server, holding `bookwriter.db` and
  `vector/`.
- `healthcheck:` test `["CMD","curl","-f","http://localhost/api/health"]`,
  interval `30s`, timeout `10s`, retries `3`. It goes **through nginx on :80**,
  so a healthy container proves *both* processes are alive.
- `restart: unless-stopped`.

### `docker-compose.dev.yml` — stock images, **no build**

A header comment must warn that port `8194` **collides with `start.ps1 -ui`** —
run one or the other, never both.

- `backend` — `python:3.13`, `working_dir: /app`,
  `command: bash -c "pip install -e . && uvicorn app.main:app --host 0.0.0.0 --port 8185 --reload"`,
  volumes `./backend:/app` plus the named `backend-pip-cache:/root/.cache/pip`,
  `expose: ["8185"]`, and env `BOOKWRITER_DB_PATH=/app/data/bookwriter.db`,
  `LANCEDB_DIR=/app/data/vector`, plus host passthrough for
  `${OPENAI_API_KEY:-}`, `${LLAMA_SWAP_URL:-}`,
  `${BOOKWRITER_GOOGLE_SEARCH_API_KEY:-}`,
  `${BOOKWRITER_GOOGLE_SEARCH_ENGINE_ID:-}`.
- `frontend` — `node:22-slim`, `working_dir: /app`,
  `command: bash -c "npm install && npx vite --port 8194 --host 0.0.0.0"`,
  volumes `./frontend:/app` plus the named
  `frontend-node-modules:/app/node_modules` — that second mount **shields the
  host's Windows `node_modules` from the container's Linux install**, and
  omitting it breaks native modules on both sides. `expose: ["8194"]`.
- `nginx` — `nginx:alpine`, `ports: ["8194:80"]`, mounting
  `./nginx/dev.conf:/etc/nginx/conf.d/default.conf:ro`,
  `depends_on: [backend, frontend]`.
- Named volumes: `backend-pip-cache`, `frontend-node-modules`.

### `build.ps1` — the Windows build machine

`param([switch]$Images, [switch]$Config, [string]$Push)`, with
`$ErrorActionPreference = "Stop"`, coloured progress output, and `$LASTEXITCODE`
checked after **every** external call (docker, 7z, git, scp).

1. Neither `-Images` nor `-Config` given → do **both**.
2. `$version = git describe --tags --abbrev=0`. If there is no tag, abort with a
   clear message that hints `git tag v0.0.1`.
3. Validate that `$env:DOCKER_STORE` is set **and** that the path exists; ensure
   `$DOCKER_STORE/bookwriter/` exists.
4. `-Images`: `docker build -f Dockerfile -t "iezious/bookwriter:$version" -t "iezious/bookwriter:latest" .`
   — repo-root context, dual tag.
5. `-Images`: `docker save "iezious/bookwriter:latest" | 7z a -si "<temp>/bookwriter-latest.7z"`,
   staged under `$env:TEMP/bookwriter-build`, then `Move-Item` onto the store.
   Staging first is the **partial-file guard** for a network mount; a
   `try/finally` removes the temp dir on every exit path. The archive filename
   is **fixed** — `update.sh` never discovers a name.
6. `-Config`: copy `docker-compose.prod.yml` → `$DOCKER_STORE/bookwriter/docker-compose.yml`
   (note the rename) and `.env.example` → the same folder.
7. `-Push <user@host:/path>`: **after** the store write, `scp` the archive and
   the compose file to that destination. Absent → share-only, identical to the
   reference project's behaviour.

### `update.sh` — the Linux deploy server

`set -e`. Switches `--images`, `--config`, `--all` (the default when no switch
is given), plus `--no-restart`. An unrecognised argument prints usage and exits
`1`.

1. Require `$DOCKER_STORE`; set `STORE_DIR="$DOCKER_STORE/bookwriter"` and
   `SCRIPT_DIR` to the script's **own** directory (which is the deploy
   directory). Error out if `STORE_DIR` does not exist.
2. images: `7z x -so "$STORE_DIR/bookwriter-latest.7z" | docker load`.
3. config: `cp "$STORE_DIR/docker-compose.yml" "$SCRIPT_DIR/"`. If
   `$SCRIPT_DIR/.env` is **missing**, copy `.env.example` to `.env` and **warn
   loudly** that it must be filled in before the app is usable.
4. `mkdir -p "$SCRIPT_DIR/data"` — the external db folder.
5. Unless `--no-restart`: `docker compose up -d`, then `docker image prune -f`.
6. Finish by printing `docker compose ps`.

### `.env.example`

A commented template covering `OPENAI_API_KEY`, `LLAMA_SWAP_URL`,
`BOOKWRITER_GOOGLE_SEARCH_API_KEY`, `BOOKWRITER_GOOGLE_SEARCH_ENGINE_ID` and
`BOOKWRITER_NODE_ID`. The header **must** state that LLM provider/server
settings live **in the database**, configured through the Admin SPA, and that
this file only supplies the values the DB's `$ENV_VAR` references resolve
against (`app/services/secrets.py:resolve_env_ref`). Otherwise an operator will
look here for a `base_url` that does not belong here.

### `.dockerignore`

`.git`, `backend/.venv`, `backend/data`, `frontend/node_modules`,
`frontend/dist`, `docs/`, `*.md`, `.claude/`, `.env*`, `start.ps1`, `build.ps1`,
`update.sh`, `docker-compose.dev.yml`, `data/`, `*.7z`.

### `.gitignore` (modify)

Append `/data/` and `*.7z`. **Nothing else** — the existing entries stay
untouched and unreordered.

## Definition of done

Every item is `[manual/live]`. The `[test]` set is empty **by a locked
decision**, not by omission; the verifier records the whole set as
requires-live-run.

- **DoD-1** `[manual/live]` `docker build -t iezious/bookwriter:test .` from the
  repo root succeeds, and the `web` stage produces all five `index.html` files
  (`/`, `admin`, `login`, `work`, `read`) plus a shared `assets/` directory in
  the image at `/usr/share/nginx/html`.
- **DoD-2** `[manual/live]` `docker compose -f docker-compose.prod.yml up -d`
  against an empty `./data` starts exactly one container, which reaches
  `healthy` within roughly 90 seconds.
- **DoD-3** `[manual/live]` `GET http://<host>:8194/api/health` returns 200
  through nginx.
- **DoD-4** `[manual/live]` The deep links `/`, `/admin`, `/login`, `/work`,
  `/read` **and a nested route under each of `/work` and `/read`** all serve the
  correct SPA `index.html` with status 200, not 404.
- **DoD-5** `[manual/live]` First-run bootstrap completes in the browser (create
  database + admin account), and **both** `./data/bookwriter.db` and
  `./data/vector/` appear on the host — proving `LANCEDB_DIR` points inside the
  mount.
- **DoD-6** `[manual/live]` `docker compose down` followed by
  `docker compose up -d` preserves the admin account and a working login.
- **DoD-7** `[manual/live]` A chat turn streams incrementally in the browser
  rather than arriving as one buffered blob — proving `proxy_buffering off` on
  the `/api` location.
- **DoD-8** `[manual/live]` With a git tag present, `build.ps1` produces
  `$DOCKER_STORE/bookwriter/bookwriter-latest.7z`, `docker-compose.yml` and
  `.env.example`; `build.ps1 -Config` alone updates only the config files; and a
  missing `DOCKER_STORE` or a missing git tag aborts with a clear message rather
  than a stack trace.
- **DoD-9** `[manual/live]` On the server, `update.sh` loads the image, copies
  the compose file, creates `.env` from `.env.example` when absent (with a loud
  warning), and brings the stack up; `update.sh --config` alone touches no
  images.
- **DoD-10** `[manual/live]` `docker compose -f docker-compose.dev.yml up`
  serves the Vite dev server and a working `/api` through nginx on port 8194,
  with HMR live (an edit under `frontend/src/` updates the browser without a
  full reload).
- **DoD-11** `[manual/live]` The existing suites are unaffected:
  `cd backend && .venv/Scripts/python -m pytest` and
  `cd frontend && npm run build` are both green.

## Out of scope

1. **Any change under `backend/app/` or `frontend/src/`** — no application
   source is touched by this feature.
2. TLS, certificates, or an outer reverse proxy. The container serves plain
   HTTP on 8194; terminating TLS is the host's problem.
3. CI pipelines, Docker registry push, multi-arch builds, and running the
   container as a non-root user.
4. Making `app/main.py`'s hardcoded `logging.basicConfig(level=logging.DEBUG)`
   env-driven — that is a backend source change.
5. Adding a `BOOKWRITER_LANCEDB_DIR` alias to `backend/app/settings.py` to make
   the two env-var names symmetric — also a backend source change. The
   asymmetry is worked around by setting the bare `LANCEDB_DIR` everywhere.
6. Editing `docs/architecture/`, `docs/product/`, or `docs/plans/roadmap.md`
   directly. Intended doc changes are recorded in `outcome.md` for the architect
   to apply; the roadmap edit is `/roadmap`'s.
7. Backup and restore tooling for `./data` beyond the JSONL export/import that
   already exists in the app.
8. Any change to `start.ps1`, and any reconciliation of the documented-but-absent
   `npx vite` vs `npm run dev` discrepancy in it.
9. A container entrypoint that creates the schema, seeds an admin, or otherwise
   pre-empts the first-run setup API.
