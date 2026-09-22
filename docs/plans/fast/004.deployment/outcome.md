# Outcome — fast feature 004 deployment

Intended documentation changes once this feature ships, for the architect to
apply at finalization. Grouped by target file. The coder appends
`## Observations` at the bottom when implementation lands.

**Note on the new top-level doc.** `docs/architecture/deployment.md` does not
exist today, and `docs/architecture/CLAUDE.md` requires a new top-level document
to be explicitly authorized. It **is** authorized by the orchestrator's briefing
for this feature. The justification: `dev-environment.md` is already ~5.3 KB
against a ~400-line per-folder norm, the deployment story (image layout,
distribution loop, URL routing table) is a distinct operational concern from the
developer's local loop, and the reference project splits the same two topics the
same way.

## `docs/architecture/deployment.md` — **NEW top-level document**

- **New file, whole.** Contents, in this order:
  - **Image layout** — one all-in-one image `iezious/bookwriter`, built from the
    repo root by a two-stage Dockerfile: a `node:22-alpine` stage that runs
    `npm ci` + `npm run build` into `dist/`, and a full `python:3.13` runtime
    stage (full, not slim, because `git` is needed for the `llm-client` VCS
    dependency and `curl` for the healthcheck). Record the stub-package trick in
    the pip layer and *why* it exists (`packages.find include = ["app*"]`), and
    record that Debian's default nginx site must be removed or it collides on
    `listen 80`.
  - **The single-container process split** — supervisord runs uvicorn bound to
    `127.0.0.1:8185` (loopback only; nginx is the sole client) and nginx on
    `:80`. Both log to stdout/stderr so `docker logs` works. Reason: readers
    otherwise assume a two-container split, as in the reference project.
  - **URL routing table** — the five static locations (`/admin`, `/login`,
    `/work`, `/read`, `/`) each with its `try_files` target, plus `/api/` →
    `127.0.0.1:8185`. State that this table is the production replacement for
    the dev-only `spaFallback()` Vite plugin, that `/assets` resolves through
    `location /` off a **single** root, and that the `/api` location carries
    `proxy_buffering off` + `proxy_cache off` + `proxy_read_timeout 300s`
    because `src/api/sse.ts` streams SSE.
  - **State and the external data folder** — `./data:/app/data` holds both
    `bookwriter.db` and `vector/`. Call out prominently that the LanceDB
    directory is configured by the **bare `LANCEDB_DIR`** env var (no
    `BOOKWRITER_` prefix, unlike every sibling setting), and that setting only
    `BOOKWRITER_DB_PATH` silently loses the vector index on every container
    replace. Also state that the image performs **no schema bootstrap**: a fresh
    container boots with zero tables and `db_ready=false` by design, and the
    operator completes first-run setup in the browser.
  - **Distribution flow** — registry-free: build on Windows → `docker save |
    7z a -si` → `$DOCKER_STORE/bookwriter/bookwriter-latest.7z` on a share →
    `7z x -so | docker load` on the Linux server → `docker compose up -d`.
    Version from `git describe --tags --abbrev=0`, dual-tagged `:$version` and
    `:latest`; archives always carry `:latest` under a fixed filename. Archives
    are staged in `$env:TEMP` and moved onto the share (partial-file guard).
    `build.ps1 -Push <user@host:/path>` adds an optional scp path. Document the
    `--images` / `--config` / default-all switch split shared by both scripts.
  - **Published port** — `8194:80`, chosen so the browser URL is identical in
    dev and prod, and note the collision with `start.ps1 -ui`.
  - **Files table** — `Dockerfile`, `.dockerignore`, `docker/supervisord.conf`,
    `nginx/prod.conf`, `nginx/dev.conf`, `docker-compose.prod.yml`,
    `docker-compose.dev.yml`, `build.ps1`, `update.sh`, `.env.example`, each
    with a one-line role.
  - **Secrets** — no global JWT secret exists (per-user keys live in the DB);
    LLM `base_url`/`api_key` live in the DB with `$ENV_VAR` indirection resolved
    by `app/services/secrets.py:resolve_env_ref`, so `.env` exists solely to
    supply the values those references point at. `.env.example` is the template;
    `update.sh` creates `.env` from it when absent and warns.

## `docs/architecture/dev-environment.md`

- **The "Docker & production — designed, not yet created" section** — replace it
  **whole** with a short as-built summary that links to `deployment.md` for
  detail. Reason: the section describes an intent that this feature has now
  superseded with a concrete implementation; leaving both would give two
  competing descriptions.
- **Same section — record the dev-compose divergence.** The doc says the dev
  compose "will build the images from source"; it was built instead as **stock
  images (`python:3.13`, `node:22-slim`, `nginx:alpine`) with source
  bind-mounts and no build step**, with named volumes for the pip cache and for
  `node_modules` (the latter shielding the host's Windows `node_modules` from a
  Linux install). Rationale to record: a rebuild loop is strictly worse than
  `start.ps1` for daily work, and the reference project made the same call.
  Reason: an undocumented divergence between doc and repo is the failure mode
  this file exists to prevent.
- **The `start.ps1` description** — correct the stale claim that `start.ps1 -test`
  runs pytest. It only repoints `BOOKWRITER_DB_PATH`. Reason: a reader following
  the doc would expect a test run that never happens.
- **The warning that a three-entry `prod.conf` would silently 404 `/work` and
  `/read`** — keep it, but restate it as satisfied: `nginx/prod.conf` now ships
  all five locations, and DoD-4 guards it. Reason: the warning was written
  against a file that did not exist; it should survive as a maintenance
  constraint, not as an open risk.

## `docs/architecture/README.md`

- **The gap paragraph** — remove the clause "nginx and both Docker Compose files
  do not exist in this repository yet". Reason: it is now false.
- **The document index, Operations group** — add `deployment.md` with its
  one-line description, and add it to the reading order alongside
  `dev-environment.md`. Reason: a new top-level doc that is not indexed is
  invisible.

## `docs/architecture/system-overview.md`

- **The nginx description** — it says nginx serves **three** static roots.
  It is **five**: `/`, `/admin`, `/login`, `/work`, `/read`. Reason: the reader
  and working SPAs both ship, and the count is the exact thing that silently
  404s if it is wrong.

## Root `CLAUDE.md`

- **Project Structure block** — remove **both** `PLANNED — NOT YET CREATED`
  markers (on `nginx/` and on the two `docker-compose*.yml` lines), and remove
  the paragraph below the tree that says those files do not exist and must not
  be assumed. Reason: both are now false, and the paragraph actively instructs
  agents to distrust real files.
- **Project Structure block** — add `Dockerfile`, `docker/` (supervisord
  config), `.dockerignore`, `update.sh` and `.env.example` to the tree. Note
  that `build.ps1` — previously listed but absent — is now real. Reason: the
  tree is the first thing an agent reads for orientation.
- **Optionally, Build & Test Commands** — a short "Deployment" line pointing at
  `build.ps1` / `update.sh` / `docker compose -f docker-compose.prod.yml up -d`
  and at `docs/architecture/deployment.md`. Reason: the file states that agents
  read commands from that section and must ask before inventing one.

## Follow-up for `/roadmap` — **not this feature's to write**

- `docs/plans/roadmap.md` — move the "The serving layer (no product id)" bullet
  out of **Mapped later**, and record `fast/004.deployment` as delivered. This
  plan must not edit `roadmap.md`; `/roadmap` owns it.

## Follow-ups spotted at planning (seeds for the coder's `## Observations`)

These are **not** this feature's work; they were found while harvesting and are
recorded so they are not lost.

- **`LANCEDB_DIR` has no `BOOKWRITER_` prefix** while every sibling setting in
  `backend/app/settings.py` does. It is a trap: it will be mis-set by anyone who
  pattern-matches the other names. Fix by adding a `BOOKWRITER_LANCEDB_DIR`
  alias (validation alias, keeping the old name working) — a backend source
  change, deliberately out of scope here.
- **`app/main.py` hardcodes `logging.basicConfig(level=logging.DEBUG)`**, which
  is wrong for a production container. Should become env-driven; a backend
  source change, out of scope here.
- **`db/engine.py:init_db()` exists but is never called on the boot path.** That
  is intentional today (the first-run setup API owns schema creation), but a
  dead-looking function is an invitation for someone to "fix" it by wiring it
  into startup — which would break `admin_exists()` readiness detection. Worth
  a comment on the function or a line in the backend doc.
- **`start.ps1` uses `npx vite` while root `CLAUDE.md` documents `npm run dev`.**
  Known, previously flagged, left alone by user preference.

<!-- coder appends ## Observations below -->

## Observations

- The image installs `nginx` + `supervisor` from Debian and must `rm -f /etc/nginx/sites-enabled/default`, because Debian's `nginx.conf` includes both `conf.d/*.conf` and `sites-enabled/*` and the stock site collides on `listen 80`. Possible impact: state this explicitly in the new `docs/architecture/deployment.md` "Image layout" section — it is the kind of step that gets dropped as cosmetic during a base-image change.
- `.gitignore` now carries `/data/` and `*.7z`, and the deploy server's `./data` folder (created by `update.sh`) is the only stateful thing on the host. Possible impact: mention in `deployment.md` "State and the external data folder" that backing up the host `./data` folder is the whole backup story, since nothing else outside the image persists.
- `docker-compose.dev.yml` publishes `8194:80`, exactly the port `start.ps1 -ui` uses on the host; the collision is warned about only in a comment header in that file. Possible impact: repeat the warning in `docs/architecture/dev-environment.md` where `start.ps1` is described, so a reader hits it before starting both.
- `update.sh` creates `.env` from `.env.example` when absent, but `docker-compose.prod.yml` declares `env_file: [.env]` unconditionally — running `docker compose up -d` by hand in a fresh deploy directory (without `update.sh --config` first) fails on the missing file. Possible impact: note in `deployment.md` "Distribution flow" that `update.sh` is the supported entry point on the server, not a bare `docker compose up`.
