# fast/006.dev-file-logging — Plan

## Goal

Give the backend an opt-in development file sink: when `BOOKWRITER_LOG_DIR` names a directory,
logs are written to `<dir>/bookwriter.log` and rolled at each process start (`.log → .log.1 → …`),
bounded by a backup count. `./start.ps1 -app` points it at a git-ignored `logs/` folder at the
repo root; everything else (pytest, Docker) stays console-only.

## Source files

- `backend/app/logging_config.py` — NEW; the single public `configure_logging` entry point and all handler setup
- `backend/app/settings.py` — two new settings fields (`log_dir`, `log_backup_count`) plus docstring
- `backend/app/main.py` — replace the inline `basicConfig` block with one `configure_logging(...)` call
- `.gitignore` — ignore the new `logs/` directory
- `start.ps1` — the `-Backend` branch exports `BOOKWRITER_LOG_DIR`

## Test files

- `backend/tests/test_logging_config.py` — NEW

## Interface intent

### `backend/app/logging_config.py` (new module)

Exposes exactly **one** public function, `configure_logging`. It takes an optional log directory
(`Path | None`), a backup count (`int`) and a log level (`int`), and returns nothing. Keyword
arguments with sensible defaults are appropriate so `main.py` reads clearly. Responsibilities, in
order:

- **Console, always.** Install a `StreamHandler` on the root logger at the given level, using the
  existing format string `"%(asctime)s [%(levelname)s] %(name)s: %(message)s"`. Preserve the
  current third-party quieting: `aiosqlite`, `httpx` and `httpcore` are set to `WARNING`. Console
  behaviour must be indistinguishable from today's.
- **Directory `None` → console only.** Create no directory, install no file handler, touch no
  filesystem.
- **Directory given → file sink.** Create the directory with `parents=True, exist_ok=True`, then
  install a `logging.handlers.RotatingFileHandler` on `<dir>/bookwriter.log` with `maxBytes=0`
  (size-based rotation disabled — the handler never rolls itself) and the given `backupCount`,
  sharing the same formatter and level as the console handler.
- **Roll at start.** If the target file already exists and is non-empty at construction time, call
  the handler's `doRollover()` exactly once, so the previous run's content becomes
  `bookwriter.log.1` and a fresh empty `bookwriter.log` begins. This deliberately reuses the
  stdlib's own `.1 → .2 → …` renaming and its pruning of backups beyond `backupCount` rather than
  reimplementing either. An absent or empty file is not rolled.
- **Attach to uvicorn by name.** Attach the file handler to the root logger **and** explicitly to
  the loggers named `uvicorn` and `uvicorn.error`. uvicorn sets `propagate = False` on its own
  loggers, so root attachment alone would silently drop the startup/shutdown/traceback lines.
  **Do not attach to `uvicorn.access`** — per-request noise is out of scope by decision.
- **Idempotent.** Tag every handler this module installs with a module-private marker attribute.
  Before installing anything, remove previously-tagged handlers from the root logger and from the
  uvicorn loggers (closing them). Repeated calls in one process must leave the handler count
  unchanged — the tests call it several times.
- **Non-fatal on rollover failure.** If `doRollover()` raises `OSError` (for example another
  process holds the file open on Windows), swallow it, emit a warning on the console and continue
  by appending to the existing file. A locked log file must never stop the app from booting.

### `backend/app/settings.py`

Add two fields to `Settings`, in the existing `Field(default=..., validation_alias=...)` style used
by `db_path` and `node_id` (**not** the alias-less `lancedb_dir` shape):

- a log directory field, `Path | None`, alias `BOOKWRITER_LOG_DIR`, **default `None`**;
- a backup-count field, `int`, alias `BOOKWRITER_LOG_BACKUP_COUNT`, default `10`, constrained
  `ge=0`.

Extend the class docstring's bulleted field list with both, matching the existing entries' wording.

**The directory default is `None`, not the repo `logs/` path.** The unset variable is exactly what
keeps the pytest suite and the containers console-only; a path default would silently enable the
file sink everywhere and is wrong.

### `backend/app/main.py`

Replace the `logging.basicConfig(...)` block **and** the third-party quieting loop with a single
`configure_logging(...)` call whose arguments come from `get_settings()` (`get_settings` is already
imported; add the import of the new module). Keep the same level as today. Everything from
`logger = logging.getLogger(__name__)` downward is unchanged.

### `.gitignore`

Add a root-anchored `/logs/` entry alongside the existing `/data/`-style entries. No `.gitkeep` is
committed — the directory is created by the app at startup.

### `start.ps1`

In the `-Backend` branch **only**, before the uvicorn invocation, set
`$env:BOOKWRITER_LOG_DIR` to the repo-root `logs` directory (built from `$PSScriptRoot`) and echo
it with a `Write-Host "  Logging to: ..."` line matching the style of the existing `-Test` DB echo.
No other branch and no other script sets this variable.

## Definition of done

1. **[test]** Called with no log directory, `configure_logging` installs no file handler and
   creates no directory on disk.
2. **[test]** Called with a log directory, the directory is created and emitted log records land in
   `<log_dir>/bookwriter.log`.
3. **[test]** A second `configure_logging` call against a non-empty `bookwriter.log` rolls the
   previous content into `bookwriter.log.1` and starts a fresh `bookwriter.log`: the first run's
   content is present in `.1` and absent from the new `bookwriter.log`.
4. **[test]** Rolling more times than the configured backup count never leaves more than
   `backup_count` numbered backup files.
5. **[test]** Repeated `configure_logging` calls do not accumulate handlers on the root logger —
   the root handler count is the same after the second and subsequent calls as after the first.
6. **[test]** `Settings` reads `BOOKWRITER_LOG_DIR` and `BOOKWRITER_LOG_BACKUP_COUNT` from the
   environment, and defaults to `None` / `10` respectively when they are unset.
7. **[manual/live]** The whole existing backend suite still passes — confirmed by the verifier's
   full-suite run (`cd backend && .venv/Scripts/python -m pytest`) rather than by a dedicated test.
   Several existing tests import `app.main`, which now runs `configure_logging` at import time, so
   a regression there shows up as a suite failure.
8. **[manual/live]** `./start.ps1 -app`, run twice with a stop in between, creates `logs/` at the
   repo root, leaves the current run in `logs/bookwriter.log` and the previous run in
   `logs/bookwriter.log.1`, and `git status` stays clean.
9. **[manual/live]** The log file contains the uvicorn startup lines and
   `Application startup complete …` but **no** per-request access lines; console output is
   unchanged from today.

### Notes for the test-coder

- **DoD-7 needs no test of its own** — it is satisfied by the verifier's full-suite run, not by a
  dedicated test case. The coverage contract is DoD-1..6.
- `configure_logging` mutates **process-global** logging state. Every case must capture and restore
  the root logger's handler list (and the `uvicorn` / `uvicorn.error` loggers' handlers) afterwards,
  so one case cannot leak handlers into another or into the rest of the suite.
- Use `tmp_path` for the log directory — never the real repo `logs/`.
- `get_settings()` is `@lru_cache`d; for DoD-6 construct `Settings()` directly with
  `monkeypatch.setenv` / `monkeypatch.delenv`, as `backend/tests/test_settings.py` already does.
- File handlers hold the file open on Windows; close/remove handlers before asserting on file
  contents or letting `tmp_path` be torn down.

## Out of scope

- Structured/JSON logging, log shipping, per-request correlation ids.
- Any change to `Dockerfile`, `docker-compose.dev.yml`, `docker-compose.prod.yml`, `nginx/`, or the
  frontend.
- Capturing `uvicorn.access` into the file.
- Retention by age or total size, and any cleanup job for `logs/`.
- Changing *what* is logged, or the INFO/DEBUG level policy.
- Changing `backend/tests/conftest.py`.
