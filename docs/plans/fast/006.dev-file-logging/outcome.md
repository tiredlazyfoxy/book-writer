# fast/006.dev-file-logging — Intended documentation changes

Applied at finalization by the architect. Plans never edit `docs/architecture/` directly.

## `docs/architecture/backend.md`

### Section: "Logging"

**Intended change.** The section currently reads as two bullets — "Python standard `logging`,
default output to console" and the `INFO`-for-requests / `DEBUG`-for-full-flow level policy.
Extend it with the development file sink now that one exists:

- Logging setup moved out of `app/main.py` into a cross-cutting `app/logging_config.py` exposing a
  single `configure_logging(...)` entry point, called once from the composition root. It follows
  the `app/settings.py` / `app/ids.py` precedent of a top-level module outside the
  `routes`/`services`/`db`/`models` layering.
- The console handler remains the default and the only always-on sink; the third-party quieting
  (`aiosqlite`, `httpx`, `httpcore` → `WARNING`) is unchanged, just relocated.
- **The file sink is off unless `BOOKWRITER_LOG_DIR` names a directory.** Two new settings:
  `BOOKWRITER_LOG_DIR` (`Path | None`, default `None`) and `BOOKWRITER_LOG_BACKUP_COUNT`
  (`int`, default `10`). Only `start.ps1 -app` sets the directory, to a git-ignored `logs/` at the
  repo root — which is why the pytest suite and the containers remain console-only with no change
  to `conftest.py`, the `Dockerfile` or `docker-compose.dev.yml`.
- **Rotate-on-process-start semantics.** One fixed filename `bookwriter.log`, rolled once at
  startup via `RotatingFileHandler` with `maxBytes=0` and an explicit `doRollover()`, so the
  previous run lands in `.log.1` and older runs shift down to the backup-count limit. A stable
  path was chosen over per-run timestamped files so tailing and grepping have a fixed target, and
  the stdlib handler already implements the renaming and pruning. Rollover failure (a locked file
  on Windows) is swallowed with a console warning — logging must never block boot.
- **`uvicorn` and `uvicorn.error` are attached to the file handler by name**, because uvicorn sets
  `propagate = False` on its loggers and root attachment alone drops the startup/shutdown lines.
  **`uvicorn.access` is deliberately excluded** — per-request lines would swamp the file.
- Note the accepted consequence under `--reload`: the reloader child re-imports the app on every
  code change, so each reload rolls the file and backups turn over quickly during editing.
  `BOOKWRITER_LOG_BACKUP_COUNT` raises the depth.

**Reason.** The Logging section presently asserts console output as the whole story. After this
feature there is a second, env-gated sink with non-obvious semantics (rotate at start, uvicorn
attachment by name, `uvicorn.access` excluded on purpose, default-off so containers are unaffected)
— each of which a later reader would otherwise misread as an oversight or "fix" incorrectly.

### Section: config/secrets settings inventory

If the two new settings belong in the settings inventory that `backend/persistence.md` carries
(config/secrets), add `BOOKWRITER_LOG_DIR` and `BOOKWRITER_LOG_BACKUP_COUNT` there alongside
`BOOKWRITER_DB_PATH` / `BOOKWRITER_NODE_ID` / `LANCEDB_DIR`. **Reason:** the inventory is the place
a reader looks for the full env-var surface; two new variables that change runtime behaviour must
not be discoverable only from source.

## Observations

- `backup_count=0` is a legal setting (`ge=0`) but the stdlib handler then keeps no backups and appends to the live file instead of truncating it, so `bookwriter.log` grows unbounded across runs. Possible impact: mention the `>= 1` recommendation next to `BOOKWRITER_LOG_BACKUP_COUNT` in `backend.md` → "Logging".
- The file handler is one shared instance attached to three loggers (root, `uvicorn`, `uvicorn.error`); the idempotency marker is per-handler, so a re-run detaches it from all three and closes it once. Possible impact: worth a sentence in `backend.md` → "Logging" so a later change does not attach a second, separate file handler per logger and double every uvicorn line.

---
Status: Applied 2026-08-09
Applied items: 4
Rejected items: 0

Notes:
- The "Logging" item landed as written in `docs/architecture/backend.md`, plus a dated decision-history entry there recording rotate-at-start-on-a-fixed-filename and the default-off `BOOKWRITER_LOG_DIR` gating.
- The `backup_count=0` observation was **folded into the rotation bullet** as a clause with the `>= 1` guidance rather than given its own bullet — it is a footnote to rotation, not a peer of it.
- The shared-handler observation landed as one sentence in the same section.
- The "config/secrets settings inventory" item was **retargeted**: the new variables went to the `| Variable | Purpose |` table under `docs/architecture/dev-environment.md` → "Environment variables", not to `backend/persistence.md`, which mentions `BOOKWRITER_DB_PATH` only in passing as a property of the DB file and is not the env-var inventory. Four already-shipped variables missing from that table (`BOOKWRITER_NODE_ID`, `LANCEDB_DIR`, `BOOKWRITER_GOOGLE_SEARCH_API_KEY`, `BOOKWRITER_GOOGLE_SEARCH_ENGINE_ID`) were filled in the same pass.
