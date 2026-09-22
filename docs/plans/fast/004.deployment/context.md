# Context — fast/004.deployment

Feature-wide context for the single plan in `plan.md`. Distilled from the
orchestrator's briefing (harvester report at HEAD `f6e3068`, plus user-confirmed
decisions). Read this before `plan.md`.

## What this feature is

The **serving layer**: the artifacts that let BookWriter be built into a
container image, distributed to a Linux server, and run there against an
external database folder — plus the Windows build script and the Linux update
script that drive that loop. Nothing under `backend/app/` or `frontend/src/`
changes; every file in scope is a build/run configuration artifact or a shell
script.

## Provenance of the feature number

There is **no `brief.md`** for this feature. The number `004` was minted by
`/fast-feature`, not by `/roadmap` — the serving layer currently sits under
**"Mapped later"** in `docs/plans/roadmap.md` as:

> The serving layer (no product id) — `nginx/` and both `docker-compose*.yml` do
> not exist. Nothing can be deployed until they are, and they must carry static
> roots for `/work` and `/read` as well as `/`, `/admin` and `/login`.

**Follow-up for `/roadmap` (not this feature's to write):** move that bullet out
of *Mapped later* and record `fast/004.deployment` as delivered. This plan must
not edit `roadmap.md`.

Neighbouring folders: `fast/001.snowflake-ids` and `fast/002.admin-ui-retune`
are delivered; **`fast/003.book-system-prompt` is retired** (stale `brief.md`,
no `status.md`) — leave it entirely alone.

## Repo state this plan assumes (verified at HEAD `f6e3068`)

- Repo root contains only `.claude/`, `.git/`, `.gitignore`, `backend/`,
  `CLAUDE.md`, `docs/`, `frontend/`, `product.md`, `start.ps1`.
- **No `nginx/`, no `docker-compose*.yml`, no `Dockerfile`, no `.dockerignore`
  anywhere in the tree.** Every source file in this plan is new except
  `.gitignore`.
- **`build.ps1` does not exist**, despite root `CLAUDE.md` listing it in the
  Project Structure block — a stale doc reference this feature makes true.
- Root `.gitignore` already covers `.venv/`, `node_modules/`, `frontend/dist/`,
  `*.db`, `.env`, `.env.local`, `backend/data/`, `docker-compose.override.yml`,
  `docs/.cache/`. It does **not** cover `/data/` or `*.7z`.

## Backend facts that constrain the image

- `backend/pyproject.toml`: `requires-python >=3.13`, setuptools backend,
  `[tool.setuptools.packages.find] include = ["app*"]`. Runtime deps include
  `lancedb>=0.6` and the **git dependency**
  `llm-client @ git+https://github.com/Iezious/PythonLLMClient.git@v0.1.4` —
  therefore the runtime image **must have `git` installed at pip-install time**.
  That, plus `curl` for the healthcheck, is why the base is full `python:3.13`
  and not `-slim`.
- ASGI target is `app.main:app` (module-level `app = FastAPI(...)`; there is no
  `__main__` block). uvicorn must run with cwd `/app`.
- `backend/app/settings.py` (pydantic-settings, `env_file=".env.local"`, **no
  `env_prefix`**):

  | Field | Env var | Default |
  |---|---|---|
  | `db_path` | `BOOKWRITER_DB_PATH` | `<backend>/data/bookwriter.db` |
  | `lancedb_dir` | **`LANCEDB_DIR`** (bare field name — **no** `BOOKWRITER_` prefix) | `<backend>/data/vector` |
  | `node_id` | `BOOKWRITER_NODE_ID` | `0` |
  | `google_search_api_key` | `BOOKWRITER_GOOGLE_SEARCH_API_KEY` | None |
  | `google_search_engine_id` | `BOOKWRITER_GOOGLE_SEARCH_ENGINE_ID` | None |

- **Critical gotcha — the whole reason `LANCEDB_DIR` is called out three times in
  this plan.** Setting only `BOOKWRITER_DB_PATH` leaves the LanceDB vector index
  **outside** the mounted volume, so it is silently destroyed on every container
  replace and the semantic index has to be rebuilt. **Both** variables must be
  set, in the Dockerfile *and* in both compose files, and DoD-5 exists purely to
  prove it.
- **Schema is not created at boot.** The lifespan startup does not call
  `db/engine.py:init_db()`; that function exists but is never invoked on the
  boot path. Tables are created only through the first-run setup API
  (`services/setup.py:create_database` / `import_database`). A fresh container
  intentionally comes up with zero tables and `db_ready=False`, and the operator
  finishes bootstrap in the browser. **Do not add an eager `init_db()` to the
  entrypoint, supervisord, or a wrapper script** — it would defeat the
  `admin_exists()` readiness detection that drives the first-run UI.
- `init_engine()` and `init_vector()` both `mkdir(parents=True, exist_ok=True)`,
  so an empty bind-mounted `./data` is a perfectly valid starting state.
- `GET /api/health` (router prefix `/api`) returns 200 even when the app is
  unconfigured — safe as a container healthcheck.
- There is **no global JWT secret env var**: JWT keys are per-user and stored in
  the DB. LLM server `base_url` / `api_key` also live in the DB; api_key values
  are `$ENV_NAME` pointers resolved at call time by
  `app/services/secrets.py:resolve_env_ref` against `os.environ`. Consequence:
  the container must receive whatever env vars the admin referenced from the
  Admin SPA — hence `.env` / `.env.example` and the passthrough list.
- `app/main.py` hardcodes `logging.basicConfig(level=logging.DEBUG)` — noisy in
  production, but making it env-driven is a **backend source change** and is out
  of scope here. Record it as an observation, do not fix it.

## Frontend facts that constrain nginx

- `frontend/package.json`: `build: tsc && vite build`, `dev: vite --port 8194`.
  `package-lock.json` is present, so `npm ci` is viable in the build stage.
  React 19, Vite 6, TS 5.8.
- `frontend/vite.config.ts`: `appType: "mpa"`, **no `base`**, **no
  `build.outDir`** → output lands in `dist/` with absolute `/assets/...` URLs.
  Five Rollup inputs: `index.html`, `admin/index.html`, `login/index.html`,
  `work/index.html`, `read/index.html`. Dev proxy `/api` → `http://localhost:8185`.
- A custom **dev-only `spaFallback()` plugin** rewrites `/admin`, `/login`,
  `/work`, `/read` and a catch-all onto the matching `index.html`. **That plugin
  is exactly what `nginx/prod.conf` has to reproduce with per-location
  `try_files`** — it does not exist in a production build. `docs/architecture/dev-environment.md`
  warns explicitly that a three-entry `prod.conf` would **silently 404 `/work`
  and `/read`**; DoD-4 is the guard.
- `dist/` layout is `index.html` + four per-entry `index.html` files + a shared
  `assets/`. Therefore **one nginx `root` over `dist/`, not five** — separate
  per-entry roots would break the shared `/assets` chunk graph.
- Routers set `basename`: `/admin`, `/work`, `/read`, plus `/login`.
- **All API calls are same-origin relative paths** (`/api/...`), hardcoded per
  module. There is **no configurable API base URL and no `VITE_API_*` env var**,
  so the frontend needs zero build-time configuration and nginx must serve the
  SPA and proxy `/api` from the *same* origin. Auth is `Authorization: Bearer`
  from localStorage — no cookies, so no cookie/`SameSite` proxy concerns.
- `src/api/sse.ts:streamPost` consumes the assistant's SSE frames, so the `/api`
  proxy **must** set `proxy_buffering off` and a long `proxy_read_timeout`.
  DoD-7 is the guard.
- Vite 6 HMR uses a websocket with **no `server.hmr.path` configured**, so the
  dev nginx needs `proxy_http_version 1.1` + `Upgrade`/`Connection` headers on
  `location /` — a dedicated `/__vite_hmr` location (as in the reference
  project) does **not** apply here.

## Reference project — the distribution mechanism we mirror

`D:/GitRoot/_TextGens/LLMRPTextOnlyProject` has a proven, registry-free
distribution loop, and this feature copies its shape:

1. Build on Windows.
2. `docker save | 7z a -si` into `$DOCKER_STORE/<project>/*.7z` on a NAS share.
3. On the Linux server, `7z x -so | docker load`.
4. Copy `docker-compose.yml` next to the deploy dir, `docker compose up -d`.

**No Docker registry anywhere in the loop.** Version comes from
`git describe --tags --abbrev=0`, dual-tagged `:$version` and `:latest`;
archives always carry the `:latest` tag under a **fixed filename** so the
consuming script never has to discover a name. Archives are staged in
`$env:TEMP` and only then `Move-Item`'d onto the share — a partial-file guard
for network mounts — with `try/finally` cleanup. Both reference scripts share a
`--images` / `--config` / default-all switch split. Image namespace `iezious/`.
Its prod compose publishes one host port and bind-mounts `./data`.

**Where we deliberately differ from the reference:**

| Reference | Here | Why |
|---|---|---|
| Two images (`-api` + `-gate`) | **One all-in-one image** | Single service, single healthcheck, one artifact to move |
| Separate `fetch.sh` + a manual `docker compose up -d` | **One `update.sh`** that folds in the deploy | Fewer steps to get wrong on the server |
| Backend Dockerfile does `COPY pyproject.toml` + `pip install .` with no package present | **Stub-package trick** (see `plan.md`) | `packages.find include = ["app*"]` makes a zero-package install fragile — **do not copy the reference's version of this step** |

## Locked decisions (confirmed with the user)

| Decision | Choice | Why |
|---|---|---|
| Image layout | **Single all-in-one image** `iezious/bookwriter` | nginx + uvicorn in one container under supervisord; one service in compose |
| Distribution | **NAS share (`$DOCKER_STORE`)**, SSH optional | Mirrors the reference; a `-Push <user@host:/path>` switch adds scp for when the share is unreachable |
| Deploy target | Linux server | `update.sh` runs there |
| Published port | **`8194:80`** | Same browser URL in dev and prod (8194 is BookWriter's Vite port) |
| Dev compose | **Stock images + source bind-mounts, no build step** | Mirrors the reference, and **knowingly diverges** from `dev-environment.md`'s "dev compose will build the images from source": a rebuild loop is strictly worse than `start.ps1` for daily work. Record the divergence in `outcome.md`. |
| Verification | **All DoD items `[manual/live]`; no automated tests** | Dockerfile / compose / nginx / PowerShell / bash have no meaningful pytest or vitest surface. The `[test]` set is empty **by design**, not by omission. |

## Scope-check note for the verifier — this is NOT a promotion signal

Eleven files, all configuration, roughly 350–400 written lines including
comments. That is at or slightly over the nominal fast LoC budget, but the fast
criteria that matter are all satisfied: **no application source is touched**, so
there is no cross-layer coordination; there are **no ordering dependencies**
between the artifacts (each is independently authorable and the whole set is
exercised only at `docker build` time); and **every design decision is locked**
in the table above, so there is no mid-flight ambiguity. Declarative config
lines are not the same risk unit as branching application code. Do not read the
file count as a reason to promote.

## Non-negotiables the coder must not "improve"

1. **Set `LANCEDB_DIR` everywhere `BOOKWRITER_DB_PATH` is set.** Never one
   without the other.
2. **Five** static locations in `nginx/prod.conf`, not three.
3. **No eager schema creation** anywhere on the container boot path.
4. **`proxy_buffering off`** on the `/api` proxy.
5. **Do not touch `backend/app/**` or `frontend/src/**`.**
6. **Do not edit `docs/architecture/`, `docs/product/`, or `docs/plans/roadmap.md`** —
   intended doc changes go in `outcome.md` for the architect to apply.
