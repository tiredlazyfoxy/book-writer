# Fast feature 006 — dev-file-logging

| Status | Verifier | Date |
|--------|----------|------|
| done   | PASS     | 2026-08-09 |

## Files Changed

- `backend/app/logging_config.py` — NEW; `configure_logging` implemented: console handler + third-party quieting, opt-in `RotatingFileHandler` (`maxBytes=0`) rolled once at start, uvicorn/uvicorn.error attachment, marker-based idempotency, non-fatal rollover failure
- `backend/app/settings.py` — `log_dir` / `log_backup_count` fields + docstring entries (landed by skeleton, unchanged here)
- `backend/app/main.py` — `configure_logging(...)` call site replacing the inline `basicConfig` block (landed by skeleton, verified, unchanged here)
- `.gitignore` — root-anchored `/logs/` entry
- `start.ps1` — `-Backend` branch sets and echoes `$env:BOOKWRITER_LOG_DIR` = `<repo>/logs`

## Skeleton

### Frozen interface (2026-08-09)

- `backend/app/logging_config.py` — `configure_logging(log_dir: Path | None = None, backup_count: int = 10, level: int = logging.DEBUG) -> None` — new (module is new; this is its only public symbol). Parameters are positional-or-keyword with defaults, so both `configure_logging(tmp_path)` and `configure_logging(log_dir=tmp_path, backup_count=3)` bind.
- `backend/app/settings.py` — `Settings.log_dir: Path | None = Field(default=None, validation_alias="BOOKWRITER_LOG_DIR")` — new field (declarative, committed in full).
- `backend/app/settings.py` — `Settings.log_backup_count: int = Field(default=10, ge=0, validation_alias="BOOKWRITER_LOG_BACKUP_COUNT")` — new field (declarative, committed in full).
- `backend/app/main.py` — call site wired: the inline `logging.basicConfig(...)` block and the `aiosqlite`/`httpx`/`httpcore` quieting loop are replaced by `configure_logging(log_dir=_log_settings.log_dir, backup_count=_log_settings.log_backup_count, level=logging.DEBUG)` with `_log_settings = get_settings()`; `from app.logging_config import configure_logging` added. Everything from `logger = logging.getLogger(__name__)` downward is unchanged.
- Caller-compile edits (out of Source-files scope): None.

Stub form: `configure_logging` has an empty body (docstring only), **not** a `raise NotImplementedError`. `app.main` calls it at import time and much of the backend suite imports `app.main`, so a raising stub would break ~1200 unrelated tests at the red gate. Consequence for the red gate: DoD-1 (no file handler / no directory when `log_dir is None`) and DoD-5 (repeated calls do not accumulate root handlers) are **vacuously satisfied** by the no-op stub and may show green there; DoD-2, DoD-3, DoD-4 and DoD-6 are the discriminating cases.

The `.gitignore` and `start.ps1` entries in the plan's Source files carry no signature and were deliberately left untouched for the coder.

## Tests

### Tests (2026-08-09)

- `backend/tests/test_logging_config.py` — covers DoD-1..DoD-6 — console-only when `log_dir is None`, file sink creation + record capture, roll-at-start into `.log.1` (content present in `.1`, absent from the fresh `.log`), backup pruning bounded by `backup_count`, root-handler idempotency, and the two `Settings` fields (env override + `None`/`10` defaults).
- Global-state safety: an autouse fixture snapshots/restores the handler lists, levels and `propagate` flags of the root, `uvicorn` and `uvicorn.error` loggers plus the `aiosqlite`/`httpx`/`httpcore` levels; handlers are flushed, detached and closed before any file content assertion or `tmp_path` teardown.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓ (two cases), DoD-7 [manual/live, no test], DoD-8 [manual/live, no test], DoD-9 [manual/live, no test]

## Notes & Issues

- `backend/tests/conftest.py` needed no change: with `BOOKWRITER_LOG_DIR` unset the suite stays console-only. `pytest --collect-only -q` collects 1290 tests with zero errors after the change.
- `start.ps1` builds the path as `"$PSScriptRoot/logs"`; `$PSScriptRoot` itself expands with backslashes, so the literal is mixed-separator on Windows. Harmless — `pathlib.Path` normalises it — but the surrounding `-Test` DB line has the same shape and neither was normalised.
- `backup_count=0` is accepted by the `ge=0` constraint; the stdlib `RotatingFileHandler.doRollover()` then keeps no numbered backups and simply appends to the live file rather than truncating it. Consistent with "never more than `backup_count` backups", just worth knowing.
