# fast/006.dev-file-logging — Context

## What this feature is

A development-time file sink for the backend's standard-library logging. A `logs/` directory
at the repo root (git-ignored) receives `bookwriter.log`, rolled at each process start so the
previous run's output is preserved as `bookwriter.log.1`, `.2`, … up to a backup count.
The sink is **opt-in via an environment variable** and is off by default, so only
`./start.ps1 -app` turns it on.

There is no `brief.md` for this feature; the user's request and the design decisions below
were settled directly with the user before planning.

## Settled design decisions (do not re-open)

1. **Rotation style — one fixed filename, rolled at process start.** `bookwriter.log` is the
   live file; on each start the previous content shifts down the `.1 → .2 → …` chain, bounded
   by a backup count (default 10). This is *not* one timestamped file per run. Reason: a stable
   path for tailing/grepping, and the stdlib `RotatingFileHandler` already implements the
   renaming and the pruning of the oldest backup.
2. **Enablement — env-var-gated, default off.** File logging activates only when
   `BOOKWRITER_LOG_DIR` names a directory. `start.ps1 -app` sets it to `<repo>/logs`. Nothing
   else sets it, which is precisely why pytest, the `Dockerfile` and `docker-compose.dev.yml`
   need no change and stay console-only.
3. **Capture scope — app loggers plus `uvicorn` and `uvicorn.error`.** `uvicorn.access` is
   deliberately excluded: per-request lines would dominate the file. Console output stays
   exactly as it is today.

## Files involved

| File | Role |
|------|------|
| `backend/app/logging_config.py` | NEW — the whole logging setup: console handler, optional rotating file handler, third-party quieting, idempotency |
| `backend/app/settings.py` | two new fields: `log_dir` and `log_backup_count` |
| `backend/app/main.py` | replaces the inline `basicConfig` block with one `configure_logging(...)` call |
| `.gitignore` | root-anchored `/logs/` entry |
| `start.ps1` | `-Backend` branch exports `BOOKWRITER_LOG_DIR` |
| `backend/tests/test_logging_config.py` | NEW — the test file for this feature |

## Facts distilled from the codebase

- **`backend/app/main.py` currently configures logging inline** (around lines 44–54): a
  `logging.basicConfig` with level `DEBUG`, format
  `"%(asctime)s [%(levelname)s] %(name)s: %(message)s"` and a single `StreamHandler`, followed
  by a loop that sets `aiosqlite`, `httpx` and `httpcore` to `WARNING`, then
  `logger = logging.getLogger(__name__)`. This whole block — and only this block — is what the
  new call replaces. `import logging` (line 17) and `from app.settings import get_settings`
  (line 42) are already present, so no new import of settings is needed.
- **`backend/app/settings.py`** holds `class Settings(BaseSettings)` with
  `model_config = SettingsConfigDict(env_file=".env.local", env_file_encoding="utf-8",
  extra="ignore")`. Existing fields use the `Field(default=..., validation_alias="BOOKWRITER_...")`
  pattern (`db_path` → `BOOKWRITER_DB_PATH`, `node_id` → `BOOKWRITER_NODE_ID` with `ge=0, le=1023`,
  plus `google_search_api_key` / `google_search_engine_id`). One field, `lancedb_dir`, has **no**
  alias and reads a bare `LANCEDB_DIR` — do not copy that shape. A module constant
  `_BACKEND_ROOT = Path(__file__).resolve().parent.parent` exists. The class docstring carries a
  bulleted list documenting every field and is expected to be kept in sync. `get_settings()` is
  `@lru_cache`d, so tests that care about env vars construct `Settings()` directly.
- **`start.ps1`**'s `-Backend` branch pushes into `backend/`, optionally sets
  `BOOKWRITER_DB_PATH` for `-Test`, then runs `.venv\Scripts\uvicorn app.main:app --port 8185
  --reload`. The new env export goes in the same branch, before the uvicorn invocation.
- **`.gitignore`** already ignores `backend/data/`, `/data/`, `docs/.cache/` and friends; the
  root-anchored `/logs/` entry follows the same style. No `.gitkeep` is committed — the
  directory is created by the app at startup.
- **`backend/tests/conftest.py`** provides `db`, `http_client` (drives `app.main.app`
  in-process through `httpx.ASGITransport`, running the real lifespan) and an autouse
  `_reset_db_ready`. It needs **no** change: with `BOOKWRITER_LOG_DIR` unset the default `None`
  keeps the suite console-only. Several tests import `app.main`, so `configure_logging` does run
  during the suite — with no file handler.
- **Test-style precedent:** `backend/tests/test_settings.py` constructs `Settings()` directly and
  uses `monkeypatch.setenv` / `monkeypatch.delenv` for env-sensitive cases (because
  `get_settings` is cached). Test names carry a `__DoD<N>` suffix and a `# DoD-N:` comment above.
- **Harness:** `pytest` + `pytest-asyncio` with `asyncio_mode = "auto"` (`backend/pyproject.toml`).
  Run with `cd backend && .venv/Scripts/python -m pytest`. No backend static typecheck exists.

## Architectural placement

`app/settings.py` and `app/ids.py` are cross-cutting top-level modules that sit outside the
`routes` / `services` / `db` / `models` layering (`docs/architecture/backend.md` → "Layer
separation"; `ids.py` is named there as a sanctioned exception). `app/logging_config.py` follows
that same precedent and does not violate the layer rule.

## External references

- `logging.handlers.RotatingFileHandler` — stdlib. With `maxBytes=0` size-based rotation is
  disabled, so the handler never rolls on its own; an explicit `doRollover()` call is the only
  thing that rolls it. `doRollover()` performs the `.1 → .2 → …` renaming and deletes the oldest
  backup beyond `backupCount`.
- `docs/architecture/backend.md` → "Logging" — the section this feature extends (see `outcome.md`).

## Known behaviour to expect (not a bug)

Under `uvicorn --reload` the reloader **parent** process does not import the app; the spawned
**child** does. Every code-change reload therefore re-imports `app.main`, re-runs
`configure_logging`, and rolls the log file. During heavy editing the backups turn over quickly
and old runs fall off the end of the chain. This is an accepted consequence of rotate-at-process-start;
`BOOKWRITER_LOG_BACKUP_COUNT` raises the depth for anyone who needs more history. Do not "fix"
this by suppressing the roll.

## Constraints

- The default for `log_dir` is `None`, **not** the repo `logs/` path. The unset variable is the
  mechanism that keeps pytest and the containers console-only — a path default would silently
  turn file logging on everywhere.
- `configure_logging` mutates process-global logging state. It must be idempotent (repeated calls
  must not stack handlers), and tests must restore the root logger's handler state after each case.
- A locked or unwritable log file must never prevent the app from booting.
