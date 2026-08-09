# Feedback — 024.chat-agent-loop

## Round 1 — 2026-08-09 — the additive migration seam was left unfilled

### F1 — `tool_trace` never reaches an existing database   [kind: bug]   [target: plan.md]

- Reported: running the app against an existing database fails every chat message
  insert with
  `sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) table chat_messages
  has no column named tool_trace`, on the INSERT
  `INSERT INTO chat_messages (id, chat_id, role, content, reasoning, position, created_at, tool_trace)`.
  The failure hits a plain **user** message, so chat is unusable end to end, not
  merely the trace feature.
- Expected: adding a column to a model must also reach databases that already
  exist. `backend/app/db/engine.py:121-126` carries a first-party
  **"ADDITIVE MIGRATION SEAM"** whose own comment states the procedure —
  *"apply idempotent in-code `ALTER TABLE <table> ADD COLUMN <col> <type>`
  statements here as the schema evolves. Each wrapped in try/except so a re-run
  is a no-op once the column already exists."* Feature 024 added
  `ChatMessage.tool_trace` (`backend/app/models/chat.py:92`) and left that seam
  empty. After the fix, `init_db()` run against a database whose `chat_messages`
  table predates 024 must leave that table carrying a nullable `tool_trace`
  column, and running it again must change nothing.
- Evidence: `SQLModel.metadata.create_all` creates missing tables only and never
  alters an existing one — stated first-party at `backend/app/models/book.py:60-71`
  ("there is no supported DROP COLUMN path… `create_all`… never alters an existing
  table"). A fresh database is unaffected, which is why the full suite is green;
  the defect is only observable against a database created before 024.
- Areas: `backend/app/db/engine.py` (the seam). `backend/app/db/schema.py`'s
  existing primitives (`introspect`, `add_columns`) may be reused rather than
  re-implemented if that is cleaner.
- Constraints: preserve `async def init_db() -> None` exactly — the signature is
  frozen and has two callers (`services/setup.py:57` `create_database`,
  `services/db_import_export.py:1158` `import_all`). Preserve first-run behaviour
  on a fresh database. The seam must be **idempotent**: a second run is a no-op,
  never an error. SQLite permits `ADD COLUMN` only for nullable columns — which is
  all `tool_trace` needs. Signature: frozen.
- Out of scope: calling `init_db()` (or any schema reconciliation) at application
  startup. `backend/app/main.py`'s `lifespan()` deliberately does not do this and
  its docstring records why — changing it is new behaviour and an `/architect`
  decision, not this repair. Also out of scope: feature 007's admin-triggered
  `sync_table_schema` path, which already works and remains the operator remedy
  for an instance that is already running.
- STATUS: DONE
- Changes: `backend/app/db/engine.py` — the seam now carries a declaration table
  `ADDITIVE_COLUMNS = (("chat_messages", "tool_trace"),)` applied by a private
  `_apply_additive_columns(sync_conn)` under `run_sync` inside the seam's existing
  `_engine.begin()` block. Idempotency is by reflection (`inspect(sync_conn)`), so a
  column already present emits no DDL at all rather than raising-and-swallowing; the
  `try/except OperationalError` survives only as a lost-race backstop. The SQL type is
  compiled from `SQLModel.metadata` rather than hardcoded, so the DDL cannot drift from
  the model. Raw DDL was chosen over reusing `db/schema.py`'s `add_columns` because
  `schema.py` imports `engine`, so reuse would invert the `db/` layering. Adding the next
  column is one appended line. `init_db()`'s signature, both its callers, and first-run
  behaviour are unchanged; `main.py` untouched. Verified: repro red→green (4 of 5 runs
  red pre-fix), backend 1294 passed / 1 failed (pre-existing environmental), frontend
  740 passed / 0 failed, plan DoD-1..DoD-12 no regression.

---

## Round 2 — 2026-08-09 — codex draft writes the wrong field

### F2 — `write_codex_draft(field="name")` does not change the entry name   [kind: bug]   [target: plan.md]

- Reported: "on editing the lore fact i have call `{"field": "name", "text": "The Managed
  Democracy"}` — but name was not changed".
- Expected: a `write_codex_draft` call naming `field="name"` must apply `text` to the
  codex entry's **name**, reaching the working page's content pane the same way a `body`
  write already does. Feature 024's `context.md` records this path as already built and
  tested end to end (`write_codex_draft` → `canvas` frame → `CodexEntryPage.applyDraft`,
  covered by `canvasWiring.test.tsx` / `contentSubject.test.ts`) — 024 only made it
  *reachable* by seeding the tool. So either the `name` branch is broken somewhere along
  that chain, or it was never wired for `name` the way it was for `body`.
- Evidence: the tool call above was issued against a lore/fact codex entry and returned
  without the entry's name changing. **Not yet diagnosed** — no harvest has been run, so
  the failing link (tool handler → frame payload → `applyDraft` → the name field's draft
  state) is not yet identified. That diagnosis is the first step of applying this item.
- Areas: to be confirmed by harvest. Candidates: `backend/app/services/codex_tools.py`
  (the `write_codex_draft` handler and its `field` dispatch), the `canvas` frame payload
  in `backend/app/services/chat_turn.py` / `models/schemas/`, and on the client
  `frontend/src/work/pages/CodexEntryPage.tsx` (`applyDraft`) plus
  `frontend/src/work/.../contentSubject.ts`.
- Constraints: preserve the working `body` path exactly — it is delivered, tested and
  must not regress. Signature: to be determined at harvest; prefer frozen.
- Out of scope: any change to the canvas transport itself, and anything on feature 024's
  `## Out of scope` list (context assembly, token-level canvas streaming, modifying
  `chat_with_tools`).
- STATUS: TBD
- Changes: —
