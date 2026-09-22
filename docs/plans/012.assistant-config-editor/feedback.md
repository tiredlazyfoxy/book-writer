# Feedback — 012.assistant-config-editor

## Round 1 — 2026-08-08 — Assistant modes are unreachable on an existing database

**Context for the whole round.** The admin opened `/admin/assistant-modes` on a running
instance and saw no modes and nothing to click. Confirmed at the data level: in
`backend/data/bookwriter.db` the `assistant_modes` table holds **zero rows** (as do
`mode_tool`, `mode_subagent`, `sub_agents`, `subagent_tool`). The page is behaving
correctly — `list_modes` returns `items: []` faithfully — but `seed_default_modes()` has
only two call sites, `services/setup.py::create_database` and
`services/setup.py::import_database`, and **both run only during first-run bootstrap**.
`main.py`'s `lifespan()` never seeds, and no action on the admin DB surface
(`/api/admin/db/*`) reseeds either. An instance bootstrapped before the seed call landed
therefore has no path back: the mode rows never appear, and because the edit affordance is
per-row and there is no create-mode control, the page offers nothing to act on.

**Round decisions** (settled with the author; recorded so no agent re-decides them):

- **D-a — the recovery is an explicit admin action, not a startup seed.** Author's choice
  over seeding in `lifespan()`. Consequence accepted: an operator on the empty page is not
  self-healed by a restart, which is exactly why F3 below is in the same round and must
  name the remediation by its UI label.
- **D-b — this round seeds rows only, never content.** The five rows are created with
  `system_prompt = None` and no `mode_tool` rows, exactly as today's `seed_default_modes()`
  does. Default prompt text and default per-mode tool sets belong to
  `024.chat-agent-loop`'s decision D4 (`DEFAULT_MODE_SYSTEM_PROMPTS`,
  `DEFAULT_MODE_TOOL_NAMES`, `seed_default_mode_tools()`) and must **not** be written here.
  024 stays valid and inherits the call sites this round adds.
- **D-c — the check and its fix live in the consistency report, as a new row status plus a
  per-row action.** Author's decision, taken over the orchestrator's recommendation of a
  standalone button. The concern raised and overruled, recorded so the trade-off is not
  rediscovered later: `TableReportEntry.status` was a *schema* vocabulary
  (`Literal["ok","drift","missing"]`), and this widens it to cover row health as well, so
  one field now answers two questions. The mitigation is the explicit precedence rule in
  F1 — schema always outranks rows, so the two meanings can never contend for the same
  row.
- **D-d — the action returns 204, like its neighbours.** Superseded the earlier
  created-count DTO once D-c made this a per-row action: `Create` and `Sync` both return
  204 and confirm themselves by the report reloading with the row flipped to `ok`. The
  seed action does exactly the same, so no new response DTO is introduced and
  `DatabasePageState.rebuildResult` is not extended.

---

### F1 — No operator-reachable way to seed the five assistant modes into an existing database   [kind: bug]   [target: 001.db-layer-completion.md]

- Reported: "I open the /admin/assistant-modes and ... no modes, no ability to edit
  anything - either it's a bug or something was not finished"
- Expected: the database-consistency report **detects** the missing seed rows and **offers
  the fix in place**, as a new row status with a matching per-row action — the same shape
  as today's `missing` → `Create` and `drift` → `Sync` pairs.

  1. **Detection.** `TableReportEntry.status` gains a fourth value, `"seed-missing"`: the
     table exists with a correct schema, but one or more of its required seed rows are
     absent. The entry also gains `missing_seed_keys: list[str]`, empty for every other
     table and every other status, listing exactly which keys are absent — for
     `assistant_modes`, the members of `DEFAULT_MODE_KEYS` with no row.
  2. **Precedence — schema outranks rows, always.** A table absent from the database is
     `missing`; a present table with column drift is `drift`; only a table that is present
     *and* schema-clean is ever reported `seed-missing`; a present, schema-clean, fully
     seeded table is `ok`. The four values stay mutually exclusive, so one `status` field
     never has to express two conditions at once, and seeding is never offered against a
     table that cannot receive rows.
  3. **What "not right" means.** Presence of keys, not a row count: every key in
     `DEFAULT_MODE_KEYS` must have a row. A row carrying an unrecognised key (possible via
     an imported archive) is **not** an error and must not be reported or removed —
     `list_modes` already sorts unknown keys last and never drops them.
  4. **Which tables are checked.** A small explicit registry in `services/db_admin.py`
     maps a table name to its required seed keys and its seeder. It holds exactly **one**
     entry today — `assistant_modes` → `DEFAULT_MODE_KEYS` /
     `assistant_modes.seed_default_modes`. Every table without an entry is never reported
     `seed-missing`. The registry exists so `024.chat-agent-loop` and later features can
     add an entry rather than re-open this design; it is not a plugin system.
  5. **The fix.** A new admin route in the existing `/tables/{name}/…` family seeds the
     named table, mirroring `create_missing_table` / `sync_table_schema`: admin-gated,
     **204 No Content**, no request body, no response DTO. `DatabasePage.tsx` renders a
     `Seed` button in the Actions column when a row's status is `seed-missing`, wired
     through the api module and a state action function built on `createTableAction`'s
     idiom (clear `actionError` → call → reload the report → friendly-catch). The row
     flipping to `ok` on that reload is the admin's confirmation.
  6. **Idempotency and refusals.** Seeding an already-complete table is a **no-op that
     still returns 204** — `seed_default_modes()` is idempotent by construction and
     refusing would add ceremony with no user value (this deliberately does *not* copy
     `create_missing_table`'s `table_not_missing` refusal). A name not in the schema
     metadata is the existing `unknown_table` → 404. A real table with no registry entry,
     or one whose schema is `missing`/`drift` and therefore cannot receive rows, is a new
     `DbAdminErrorCase` → 400.
  7. **The end state.** After pressing `Seed`, the `assistant_modes` row reads `ok` and
     `/admin/assistant-modes` lists all five modes, each with a working edit control.
     Existing rows — including an admin-edited `system_prompt` and any `mode_tool` /
     `mode_subagent` selection — are untouched throughout.
- Evidence: `sqlite3` against `backend/data/bookwriter.db` → `SELECT key FROM
  assistant_modes` returns zero rows; `mode_tool`, `mode_subagent`, `sub_agents`,
  `subagent_tool` all count 0. `seed_default_modes()` (`backend/app/db/assistant_modes.py:72`)
  is called only from `backend/app/services/setup.py:57` (`create_database`) and
  `backend/app/services/setup.py:93` (`import_database`); `backend/app/main.py`'s
  `lifespan()` (lines 57-88) contains no seed call; `backend/app/services/db_admin.py` does
  not import `app.db.assistant_modes` at all.
- Areas: `backend/app/services/db_admin.py`, `backend/app/routes/admin/db.py`,
  `backend/app/models/schemas/db_admin.py`, `frontend/src/api/db.ts`,
  `frontend/src/admin/pages/DatabasePage.tsx`,
  `frontend/src/admin/pages/databasePageState.ts`,
  `frontend/src/types/` (the db-admin wire types module).
- Constraints: preserve — `seed_default_modes()` keeps its exact signature
  (`async def seed_default_modes() -> None`) and its check-then-create idempotency, and is
  **called, not reimplemented**; the report's existing three statuses keep their exact
  present meaning and every currently-`ok` / `drift` / `missing` table still reports the
  same value it does today; `db_admin` must still **not** call `set_db_ready` (its own
  docstring's rule, first-run only, owned by `services/setup.py`); the two existing
  `setup.py` call sites are unchanged; route ordering in `routes/admin/db.py` keeps static
  paths declared before `/tables/{name}/...`, and the new route sits inside that family
  without shadowing `create` or `sync`; the new route carries
  `Depends(auth_service.require_role(UserRole.admin))` like every sibling; the frontend
  `.d.ts` mirrors the widened `status` union and the new field exactly, with no `any`.
  Signature — **may change** (additive only: a widened `Literal` on an existing DTO, one
  new DTO field with an empty default, a new service function, a new route, a new
  `DbAdminErrorCase` member, a new frontend api function and state action; no existing
  signature is altered and no existing field is removed or renamed).
- Out of scope: seeding prompt text or tool rows (D-b — that is `024.chat-agent-loop`);
  seeding at application startup (D-a); any create/delete-mode capability — the five keys
  stay fixed; sub-agent seeding (there are no default sub-agents, and zero rows there is a
  correct state); a second registry entry for any table other than `assistant_modes`;
  removing or reporting unrecognised mode keys; a confirmation modal (no action on this
  page has one).
- STATUS: DONE
- Changes: `backend/app/models/schemas/db_admin.py` — `TableReportEntry.status` widened to
  `Literal["ok","drift","missing","seed-missing"]`, new `missing_seed_keys: list[str] = []`
  (defaulted, so every existing construction site is untouched).
  `backend/app/services/db_admin.py` — new `not_seedable` `DbAdminErrorCase`; typed one-entry
  seed registry (`class SeedSpec(TypedDict)` + `_SEEDABLE_TABLES = {"assistant_modes": …}`);
  new module-private `_missing_seed_keys(name)` returning the registry entry's absent
  `required_keys` **in registry order** by key presence, `[]` for an unregistered table (so an
  unrecognised key is never reported and never removed); `build_consistency_report()` calls it
  **only** inside the present-and-schema-clean branch, so `missing` / `drift` never consult
  rows and keep `missing_seed_keys == []`; `seed_table_rows(name)` filled — not in
  `SQLModel.metadata` → `unknown_table` (404, mirroring `sync_table_schema`), no registry entry
  or a `missing`/`drift` schema → `not_seedable` (400), otherwise `await spec["seeder"]()`,
  i.e. `assistant_modes.seed_default_modes()` **called, not reimplemented**, so an
  already-complete table is a successful no-op.
  `backend/app/routes/admin/db.py` — `POST /tables/{name}/seed` → 204, no body, no response
  DTO, admin-gated, declared **last** in the `/tables/{name}/…` family (shadowing neither
  `create` nor `sync`); `not_seedable → 400` added to `_DB_ADMIN_ERROR_STATUS`.
  `frontend/src/types/db.d.ts` — `TableStatus` widened and `missing_seed_keys: string[]` added,
  mirroring the backend DTO exactly, no `any`. `frontend/src/api/db.ts` — `seedTable(name,
  signal?)`. `frontend/src/admin/pages/databasePageState.ts` — `seedTableAction`, mirroring
  `createTableAction`/`syncTableAction` (clear `actionError` → call → reload the report →
  friendly-catch), no new state field. `frontend/src/admin/pages/DatabasePage.tsx` — `handleSeed`
  and a `size="xs"` `Seed` button rendered only for `seed-missing`; `Create` (`missing`) and
  `Sync` (`drift`) unchanged; no toast, modal or confirmation.

### F2 — The admin DB-import path leaves modes unseeded, reproducing the same dead end   [kind: bug]   [target: 001.db-layer-completion.md]

- Reported: raised during diagnosis of F1 and confirmed by the author as in scope for this
  round.
- Expected: `services/db_admin.import_database` — the admin-surface import, a *different*
  function from the first-run `services/setup.import_database` — seeds the default modes
  after the import completes, in the same idiom as the bootstrap path. Importing an archive
  whose `assistant_modes` rows are absent leaves the instance with all five keys present;
  importing an archive that already carries mode rows leaves those rows exactly as archived
  (prompts preserved, no duplicates, no extra rows beyond the fixed five).
- Evidence: `backend/app/services/db_admin.py:237-247` — `import_database` is
  `await validate_archive(...)` then `await db_import_export.import_all(...)`, with no seed
  call and no `assistant_modes` import in the module.
  `backend/tests/services/test_setup_mode_seed.py:37-41` states outright that "the admin
  import surface (`services/db_admin.py`) is deliberately out of scope" — the gap was known
  and left open.
- Areas: `backend/app/services/db_admin.py`.
- Constraints: preserve — import stays idempotent; `set_db_ready` is still never called
  here; `validate_archive`'s refusal contract for a corrupt archive is unchanged, and a
  refused import must not seed. Signature — **frozen**
  (`async def import_database(archive_bytes: bytes) -> None`).
- Out of scope: changing what `db_import_export.import_all` does; seeding any table other
  than `assistant_modes`.
- STATUS: DONE
- Changes: `backend/app/services/db_admin.py` — `import_database` now ends with
  `await assistant_modes.seed_default_modes()`, placed after `db_import_export.import_all(...)`
  and therefore after `validate_archive`, so a refused archive still raises before anything is
  seeded. Signature unchanged; `set_db_ready` still never called here; `services/setup.py` and
  its two existing call sites untouched. Docstring updated to state the seed and its position.

### F3 — The modes page renders a bare table header with no explanation when there are no modes   [kind: bug]   [target: 007.modes-page.md]

- Reported: "no modes, no ability to edit anything" — the page gave the author no way to
  tell a broken page from an empty one.
- Expected: when the load succeeds and the mode list is empty, `AssistantModesPage` renders
  an explanatory empty state instead of a header-only table. The message must state that no
  assistant modes are configured **and name the F1 remediation by its UI location** — the
  Database page's consistency report, where the `assistant_modes` row offers a `Seed`
  action — so the page is self-diagnosing under D-a's no-startup-seed choice. The loading,
  error and populated branches are unchanged, and a non-empty list renders exactly as it
  does today.
- Evidence: `frontend/src/admin/pages/AssistantModesPage.tsx:69-112` — the
  `!loading && !error` guard renders `<Table>` unconditionally and `<Table.Tbody>` maps
  `state.modes`; nothing branches on `state.modes.length === 0`.
- Areas: `frontend/src/admin/pages/AssistantModesPage.tsx`.
- Constraints: preserve — the three existing render branches (loader while loading, red
  `Text` on error, populated table) behave identically; the per-row edit `ActionIcon` and
  the modal wiring are untouched; component stays an `observer` with no page-state change
  and no new `useState`. No admin page has an empty-state precedent, so follow the repo's
  nearest idiom (`frontend/src/work/pages/CodexListPage.tsx:162-165`). Signature —
  **frozen** (no exported symbol changes; both the named and default export stay).
- Out of scope: an empty state for `SubAgentsPage` — zero sub-agents is a correct, expected
  state there (none ship by default) and that page already has a visible "New sub-agent"
  control, so it is neither broken nor a dead end.
- STATUS: DONE
- Changes: `frontend/src/admin/pages/AssistantModesPage.tsx` — when the load succeeds and
  `state.modes.length === 0`, a dimmed `Text` empty state (the `CodexListPage.tsx` idiom)
  replaces the header-only table: "No assistant modes are configured. Open the Database page
  and use the Seed action on the assistant_modes row of the consistency report to create
  them." — naming F1's remediation by its UI location, as D-a requires. The table branch is now
  `state.modes.length > 0`; the loading, error and populated branches, the per-row edit
  `ActionIcon`, the modal wiring, `observer`, the page state and both the named and default
  exports are unchanged, and no `useState` was added. `SubAgentsPage.tsx` untouched.

### F4 — Six modules still claim their bodies are UNIMPLEMENTED   [kind: reshape]   [target: 012.assistant-config-editor]

- Reported: author accepted this while the files are open; surfaced during the harvest as
  actively misleading to anyone reading the code or to a future agent.
- Expected: each stale skeleton sentence is replaced with an accurate one-line description
  of what the module does. No behaviour changes anywhere — comments and docstrings only.
- Evidence: `backend/app/routes/admin/assistant_config.py:44-48` ("the handler bodies are
  UNIMPLEMENTED" — all eight have real bodies); `backend/app/db/assistant_modes.py:11`,
  `backend/app/db/sub_agents.py:9`, `backend/app/db/mode_tools.py:9`,
  `backend/app/db/subagent_tools.py:9`, `backend/app/db/mode_subagents.py:9` (all
  "Skeleton (008 step 00N): signatures are frozen; bodies are UNIMPLEMENTED" — all bodies
  are real).
- Areas: the six files named above.
- Constraints: preserve — **observable behaviour must not change at all**; no signature,
  no logic, no import is touched. Also correct, while in
  `services/assistant_config.py`, the stale claim that the tool registry holds "exactly
  one, `web_search`" — it holds thirteen — but change no code there either. Signature —
  **frozen**.
- Out of scope: any other docstring or comment cleanup outside these files; the
  MobX-strict-mode direct-assignment warnings in `ModeEditorModal.tsx` /
  `SubAgentFormModal.tsx` (a pre-existing repo-wide pattern shared with
  `ServerFormModal.tsx`, not this feature's defect — raise separately if it should be
  fixed).
- STATUS: DONE
- Changes: comments and docstrings only across all seven locations — **zero** code, signature,
  import or logic change, confirmed by the verifier against `git diff -U0` (every changed line
  lies inside a docstring). `backend/app/routes/admin/assistant_config.py`,
  `backend/app/db/assistant_modes.py`, `backend/app/db/sub_agents.py`,
  `backend/app/db/mode_tools.py`, `backend/app/db/subagent_tools.py`,
  `backend/app/db/mode_subagents.py` — each "…bodies are UNIMPLEMENTED" sentence replaced by a
  one-line description of what the module actually contains (the eight implemented handlers;
  the mode CRUD + seeder; the sub-agent CRUD with no delete; the three link-table modules'
  lookups and count-returning bulk deletes). `backend/app/services/assistant_config.py` —
  in `list_tools`'s docstring only the false "(today there is exactly one, `web_search`)"
  parenthetical was replaced; the sentence's point, "nothing may hard-code the count",
  survives verbatim.
- Follow-ups left open (same defect class, outside this item's declared Areas — worth a
  sweep in a later round): `backend/app/services/db_admin.py`'s module docstring and
  `frontend/src/admin/pages/AssistantModesPage.tsx`'s both still carry stale skeleton claims;
  and `backend/tests/services/test_setup_mode_seed.py`'s docstring still declares the admin
  import surface out of scope, which F2 made false (a test file — off-limits to the coder
  under the air gap).
