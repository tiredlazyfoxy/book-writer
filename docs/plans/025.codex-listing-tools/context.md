# Feature 025 — Codex listing tools

Ultra track — single continuous build. No step files. This file plus `plan.md` are self-sufficient
for a build session with no conversation history.

## Provenance

First decomposed by `/planner` into three steps (`001.listing-tools`, `002.tool-group-metadata`,
`003.grouped-tool-picker`). Re-shaped into one ultra plan at the user's instruction on 2026-09-15; the
step files were deleted. Nothing they specified was dropped — see `plan.md` → "Decisions taken" for
what changed in the conversion (two corrections, one clarified risk, a re-sorted test plan).

## Goal

Give the assistant a way to **see** the whole codex, not just search it.

Today the codex tool set is `codex_search` (semantic, top-N), `codex_read_entry` (one entry by id,
full body), `write_codex_draft` and `create_codex_entry`. Nothing lets the model **enumerate** what
exists, so it cannot answer "who is in this book", and it cannot avoid creating a duplicate of an
entry it has never seen. This feature adds **four short-form listing tools**.

As a **second, separate concern** it groups the admin editor's tool checkboxes visually — the
registry reaches 18 tools with this feature and currently renders as one flat column.

**`codex_read_entry` already exists and already takes an id.** A get-by-id tool is *not* part of this
feature. This is the one place that says so.

## Scope

**In**

- Four new context-bearing codex tools: `codex_list_entries`, `codex_list_characters`,
  `codex_list_locations`, `codex_list_facts`.
- Seeded `mode_tool` defaults and seeded mode system-prompt wording for the new tools.
- A backend-declared `group` key on every `ToolDef`, carried through `ToolResponse`, `list_tools()`
  and the hand-written `.d.ts` twin.
- One shared, grouped `ToolPicker` component replacing the duplicated tool-checkbox JSX in the two
  admin modals.

**Out**

- Any change to `backend/app/db/codex_entries.py`. The data access this feature needs already exists.
- Pagination, result caps or `limit`/`offset` anywhere in this feature.
- A get-by-id tool (see above).
- Any change to `seed_default_mode_tools()`'s idempotency unit (see "Operating step" below).
- Deduplicating the *other* two duplicated pickers — the sub-agent picker in `ModeEditorModal` and
  the accessible-modes picker in `SubAgentFormModal`. Only the **tool** picker is extracted.
- Editing `docs/plans/roadmap.md` (stale; does not list 023/024 either) or `docs/architecture/*`.
  Intended architecture changes are recorded in `outcome.md` for the architect.

## Product ids

This capability maps to **no existing story**. There is no `US` for "the assistant lists the codex".
The closest **already-delivered** ids, cited here as *context only* — this feature does **not**
deliver them:

| Id | What it is |
|---|---|
| FEAT-017 / UC-071 | Browsing the codex (the human-facing list) |
| FEAT-013 / UC-078 | Composition chat draws on the codex |
| FEAT-018 | Codex authoring from the chat |
| FEAT-020 / UC-095 step 3, UC-096 step 4, US-111 | The admin tool catalogue and per-mode tool selection |

Recording new ids is **`/product-spec`'s job, afterwards** — the repo's own precedent is
US-120 / US-121 / US-122, recorded to product after feature `024` shipped. Consequently **every DoD
item in this feature cites its own `DoD-n` id only. Do not invent US ids.**

## Architecture this feature touches

Read-only here; the architect's:

- `docs/architecture/assistant-config.md` → "Tool registry — code-defined, not a table" (the `ToolDef`
  shape), "The three link tables", "The admin route surface".
- `docs/architecture/assistant-runtime.md` → "Tool gating" (seeded defaults since feature `024`), "A
  lore list resolves to its entries' mode", "The shared-canvas write for codex".
- `docs/architecture/domain-codex.md` → `CodexEntry`: three kinds one table, `name` **null for
  `fact`** by design, archived-never-deleted.

## Cross-cutting constraints

- **Backend layer separation** (root `CLAUDE.md`): `routes → services + db`, `services → db`. No
  `session` / `select()` / `AsyncSession` in `services/`. This feature touches `db/` only for
  module-level default constants — no new query, no db-layer logic change.
- **Typed contracts both sides**: Pydantic `BaseModel` for every backend schema, hand-written `.d.ts`
  twin on the frontend, no free dicts, no `any`.
- **Frontend conventions**: MobX only, `observer` on every component, no custom hooks, no
  `useCallback`/`useMemo`. State classes hold drafts; effectful operations are external functions.
- **A tool refusal is a string the model reads, never an exception.** A raising tool aborts the whole
  turn (`assistant-runtime.md`). Every tool in `services/codex_tools.py` returns `str` and never
  raises; the four new ones inherit that discipline verbatim.
- **Tools are identified by stable string `name`**, never by FK; `mode_tool` rows store the name. The
  catalogue is code and is never exported (`assistant-config.md`).

## Shared vocabulary

- **kind** — the `CodexEntry.kind` enum: `character` | `location` | `fact`. Canonical value and UI
  label are `fact` / "Fact" / "Facts" **everywhere in code**.
- **lore** — the *author's* word for an unnamed `fact` entry (`docs/product/glossary.md`,
  `assistant-runtime.md`'s "lore list" heading). **The enum value stays `fact`; only description prose
  says "lore".**
- **short form** — this feature's output contract: id plus name, or id plus a 60-character body
  excerpt for an unnamed entry. Never the full body. The model gets the full text via
  `codex_read_entry`.
- **group** — a stable machine key on `ToolDef` (`"codex"` | `"book"` | `"web"`), declared at the
  registry definition site. Display labels are the frontend's and never cross the wire.

## Operating step required after this feature ships

Stated here because it is a consequence of a user decision, not a defect.

`seed_default_mode_tools()` **stays exactly as it is**. Its idempotency unit is the **mode**, not the
row: a mode that already has any `mode_tool` row is skipped **entirely** — not changed to a per-
`(mode, tool)` additive backfill.

Consequence, accepted deliberately: **on an existing database the four new tools will be registered
but selected in no mode.** An admin must open the assistant-config editor and tick the new checkboxes
for `edit-character`, `edit-location`, `edit-fact` and `write-chapter`. This was chosen over a
backfill because a backfill could **resurrect a tool an admin deliberately removed**.

The same reasoning applies to `DEFAULT_MODE_SYSTEM_PROMPTS`: the seeded prompt wording reaches
**fresh installs only**; existing `AssistantMode` rows keep their stored prompt.

## Layers touched

One continuous build run, ordered backend-first (services → registry → wire contract) then frontend
(types → api constant → component → wiring). See `plan.md` → "Implementation outline" for the exact
order; no checkpoint between layers.

- Backend services: `app/services/codex_tools.py`, `app/services/tools.py`,
  `app/services/assistant_config.py`.
- Backend db constants only: `app/db/mode_tools.py`, `app/db/assistant_modes.py`.
- Backend schema: `app/models/schemas/assistant_config.py`.
- Frontend types + api: `frontend/src/types/assistantConfig.d.ts`, `frontend/src/api/assistantConfig.ts`.
- Frontend admin components: new `frontend/src/admin/components/assistant-config/ToolPicker.tsx`,
  edits to `ModeEditorModal.tsx` and `frontend/src/admin/components/sub-agents/SubAgentFormModal.tsx`.

## Build & test commands

From the root `CLAUDE.md` — cite, do not invent:

- Backend tests: `cd backend && .venv/Scripts/python -m pytest`
- Backend static type-check: **none configured.**
- Frontend typecheck + bundle: `cd frontend && npm run build`
- Frontend typecheck only: `cd frontend && npx tsc --noEmit`
- Frontend tests: `cd frontend && npm test`
- Frontend **test** typecheck: `cd frontend && npm run test:types` (the only program covering
  `tests/`; `npm run build` deliberately does not typecheck tests)
- Linter: **none configured** — do not run one.

Python is always invoked as `.venv/Scripts/python`.
