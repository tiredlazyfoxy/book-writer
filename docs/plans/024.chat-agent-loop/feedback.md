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
  without the entry's name changing.
  **DIAGNOSED 2026-08-09 — the premise is wrong; no link in the chain is broken.** The
  subject was a **fact** entry, and `field="name"` against a fact is a deliberate,
  spec-mandated refusal: `backend/app/services/codex_tools.py:397-400` returns
  `_CANVAS_FACT_NAME_MESSAGE` ("a fact entry has no name — write its body instead") and
  `write_codex_draft` returns that string at `:676-680` **without emitting a `canvas` frame
  at all** — which is exactly the observed symptom. The rule is architecture, not accident:
  `docs/architecture/domain-codex.md:18,27` ("`name` is nullable because a fact does not have
  one") realizing **US-078.AC-2**.
  Every other link is implemented, tested and passing for `field="name"` on a
  character/location subject: `CanvasFrame` carries `field` as a
  `CanvasField = Literal["name","body"]` discriminator
  (`backend/app/models/schemas/chats.py:380,401-443`); the `canvasFrame()` narrower accepts
  `"name"` (`frontend/src/api/chats.ts:288`); `dispatchCanvasFrame` forwards any field
  (`frontend/src/work/contentSubject.ts:319`); and `editCodexDraft` really does branch
  `if (field === "name") state.nameDraft = text`
  (`frontend/src/work/pages/codexEntryPageState.ts:447-458`).
  Contrary to this item's original speculation, `field="name"` **is** covered by existing
  tests on both paths — the working case
  (`backend/tests/services/test_codex_canvas_tools.py:304-340`,
  `frontend/tests/work/canvasWiring.test.tsx:585`,
  `frontend/tests/work/contentSubject.test.ts:203-205`) and the fact refusal itself
  (`test_fact_refuses_name_but_allows_body__DoD10_US078_AC2`, `:575-591`).
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
- STATUS: BLOCKED
- Changes: — (nothing applied; no code change is warranted as filed)
- Blocked because: the code is correct. Closing this item as written would mean **changing
  product behaviour** — letting a fact entry carry a name — which contradicts
  `docs/architecture/domain-codex.md:18,27` and **US-078.AC-2**. That is a `/product-spec`
  decision, not a bug fix, and it is outside 024's contract either way.
  **Follow-up — the real question is which of these the author wants:**
  1. *Nothing.* "The Managed Democracy" is a world concept the assistant filed as a **fact**,
     and facts genuinely have no name — the body is the content. Correct as built → mark
     this REJECTED.
  2. *The assistant should have said so.* The refusal string reaches the **model** as a tool
     result, but whether the model relayed "facts can't have a name" into its chat reply is
     prompt/model behaviour, not this chain. Note that 024 now renders tool traces, so the
     refusal is at least *visible* in the pane. If the assistant stayed silent, that is a
     system-prompt item against `DEFAULT_MODE_SYSTEM_PROMPTS`, not this feature.
  3. *It should have been a character/location.* If the assistant mis-categorised a nameable
     entity as a fact, the defect is upstream in entry creation — a separate item against
     whichever feature owns `create_codex_entry`.
  4. *Facts should be nameable.* Genuinely new behaviour → `/product-spec` to revise
     US-078.AC-2, then a new feature. Not feedback.

### F3 — A fact's page heading is dead chrome   [kind: reshape]   [target: plan.md]

- Reported: "in the top of the lore edit page i see 'fact' or 'new fact' title. Which is not
  editable - just waste of space."
- Expected: no heading at all for a fact. For a **named** kind the heading carries the entry's
  actual name and stays.
- Evidence: `CodexEntryPage.tsx` computed `heading` as `state.entry.name || kindHeading`, so a
  fact — whose `name` is always null by US-078.AC-2 — fell through to the literal kind word
  "Fact" (or "New fact" when blank). A non-editable line reading like a title the author cannot
  change, directly above an editor that has no name field, which is the misleading part.
- Areas: `frontend/src/work/pages/CodexEntryPage.tsx` (the 024/D7 header row only).
- Constraints: the Save/Discard `ActionIcon`s and their `aria-label`s are unchanged and stay
  right-aligned. Signature: frozen — no state or props change.
- Out of scope: the name field itself (already correctly gated on `requiresName` since delivery),
  the tool's refusal path, and the `edit-fact` prompt text — all three were already correct.
- STATUS: DONE
- Changes: `CodexEntryPage.tsx` — `heading` is now `null` unless `state.requiresName`, and the
  `<Title>` renders only when non-null; the header `Group`'s `justify` flips to `flex-end` in
  that case so the action icons stay pinned right instead of collapsing left. `kindHeading`
  survives as the fallback for a named entry whose name is still blank.
  **Applied directly at the author's explicit instruction** ("direct edit, no tests needed, no
  sub-agents") — so this item did NOT run the B2 pipeline: no repro test, no red gate, no
  verifier. Verified by hand instead: `npx tsc --noEmit` clean, and
  `codexEntryPage.test.tsx` + `canvasWiring.test.tsx` pass 64/64. No existing test asserts the
  heading text, which is why removing it broke nothing.

### F4 — Every assistant mode shipped with a blank prompt layer   [kind: bug]   [target: plan.md]

- Reported: found while diagnosing F2 — "when i do ask llm to apply the fact, it calls both set
  title and set content mcp, which is also not right".
- Expected: the mode prompts 024/D4 wrote must actually reach the model on a database that
  predates 024, not only on a fresh one.
- Evidence: all five rows in this instance carried `system_prompt` of length 0 — `close-chapter`,
  `edit-character`, `edit-fact`, `edit-location`, `write-chapter` — while their `mode_tool` rows
  were present (8/4/4/4/8). Cause: `seed_default_modes()`
  (`backend/app/db/assistant_modes.py:205-210`) writes a prompt **only when the row does not
  exist** (`if await get_by_id(key) is None`), which is the correct rule for protecting an
  admin's edit but means 024's prompts skipped every row that already existed. The Admin seed
  action calls the same seeder, so it could not have fixed it either.
  This is the actual root cause of F2: the model was never told the subject was a fact, nor that
  a fact has no name. Note the `BASE` layer (`services/prompt_composition.py:35-39`) is
  hard-coded and *was* always sent — so the model had its general identity, but no mode scoping.
- STATUS: DONE
- Changes: **data fix, no code change.** The five blank prompts were backfilled from
  `DEFAULT_MODE_SYSTEM_PROMPTS` (957–1439 chars each) against
  `backend/data/bookwriter.db`, filling only rows whose prompt was NULL or whitespace so an
  edited prompt could not be overwritten. Backup at
  `backend/data/bookwriter.db.bak-before-prompt-backfill`.
- **OPEN — deliberately not decided here:** whether `seed_default_modes()` should also fill a
  *blank* prompt on an existing row. As it stands, any database predating a prompt-carrying
  feature stays silently unprompted and nothing surfaces it — this was found only because the
  model misbehaved. Same class of gap as the `tool_trace` column in F1. Changing it alters a
  deliberate rule and is the author's call, not a repair.
