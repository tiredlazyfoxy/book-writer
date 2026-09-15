# Feature 025 — Codex listing tools

| Status  | Verifier | Date |
|---------|----------|------|
| done    | PASS     | 2026-09-15 |

## Files Changed

Implemented by the coder:

- `backend/app/services/codex_tools.py` — `_excerpt`, the shared `_render_codex_listing` /
  `_render_listing_row` helpers and their `_LIST_*` strings; the four listing tools' bodies
- `backend/app/services/tools.py` — the four new registry entries' real `description` prose
  (each names `codex_read_entry` and `codex_search`; `codex_list_facts` says "lore")
- `backend/app/db/mode_tools.py` — `DEFAULT_MODE_TOOL_NAMES` widened with the four listing names
  under `edit-character` / `edit-location` / `edit-fact` / `write-chapter`; `close-chapter` and
  `seed_default_mode_tools()` untouched
- `backend/app/db/assistant_modes.py` — one new listing-tool paragraph in each of those same four
  seeded prompts; `close-chapter` untouched
- `frontend/src/admin/components/assistant-config/ToolPicker.tsx` — the grouped picker's body
  (Codex → Book → Web → Other, empty groups dropped, catalogue order preserved)
- `frontend/src/admin/components/assistant-config/ModeEditorModal.tsx` — inline tool-checkbox block
  replaced by `<ToolPicker>`; `toggleTool` now the `onToggle` prop (props/signature unchanged)
- `frontend/src/admin/components/sub-agents/SubAgentFormModal.tsx` — same replacement and wiring
- `frontend/src/types/assistantConfig.d.ts` — the `AssistantTool` doc comment's "exactly two fields"
  claim corrected to three

Landed by the skeleton, read and verified by the coder, not edited:

- `backend/app/models/schemas/assistant_config.py` — `ToolResponse.group`
- `backend/app/services/assistant_config.py` — `list_tools()` maps `group` through
- `frontend/src/api/assistantConfig.ts` — `TOOL_GROUP_LABELS`
- `backend/app/services/subagent_delegation.py` — the synthetic delegation `ToolDef`'s
  `group="delegation"` (never in `TOOL_REGISTRY`, so it never reaches the wire or the picker)

## Skeleton

### Frozen interface (2026-09-15)

**`backend/app/services/codex_tools.py`**

- `backend/app/services/codex_tools.py` — `def _excerpt(text: str, limit: int = 60) -> str` — new (body UNIMPLEMENTED)
- `backend/app/services/codex_tools.py` — `class CodexListEntriesArgs(BaseModel)` (zero fields) — new
- `backend/app/services/codex_tools.py` — `class CodexListCharactersArgs(BaseModel)` (zero fields) — new
- `backend/app/services/codex_tools.py` — `class CodexListLocationsArgs(BaseModel)` (zero fields) — new
- `backend/app/services/codex_tools.py` — `class CodexListFactsArgs(BaseModel)` (zero fields) — new
- `backend/app/services/codex_tools.py` — `async def codex_list_entries(context: "ToolContext") -> str` — new (body UNIMPLEMENTED)
- `backend/app/services/codex_tools.py` — `async def codex_list_characters(context: "ToolContext") -> str` — new (body UNIMPLEMENTED)
- `backend/app/services/codex_tools.py` — `async def codex_list_locations(context: "ToolContext") -> str` — new (body UNIMPLEMENTED)
- `backend/app/services/codex_tools.py` — `async def codex_list_facts(context: "ToolContext") -> str` — new (body UNIMPLEMENTED)
- `backend/app/services/codex_tools.py` — `def bind_codex_list_entries(context: "ToolContext") -> Callable[..., object]` — new (implemented: `functools.partial(codex_list_entries, context)`)
- `backend/app/services/codex_tools.py` — `def bind_codex_list_characters(context: "ToolContext") -> Callable[..., object]` — new (implemented: `functools.partial(codex_list_characters, context)`)
- `backend/app/services/codex_tools.py` — `def bind_codex_list_locations(context: "ToolContext") -> Callable[..., object]` — new (implemented: `functools.partial(codex_list_locations, context)`)
- `backend/app/services/codex_tools.py` — `def bind_codex_list_facts(context: "ToolContext") -> Callable[..., object]` — new (implemented: `functools.partial(codex_list_facts, context)`)

The `TYPE_CHECKING` + quoted `"ToolContext"` import-cycle guard is unchanged and followed verbatim;
no new module-level import was added. Every string the four tools return (header line, empty-listing
sentence, `Codex error: ` text) is the coder's — the skeleton declares none of them.

**`backend/app/services/tools.py`**

- `backend/app/services/tools.py` — `@dataclass(frozen=True) class ToolDef` — changed: gains `group: str`, required, positioned after `args_schema` and before `callable`/`binder`. Frozen field order: `name: str`, `description: str`, `args_schema: type[BaseModel]`, `group: str`, `callable: Callable[..., object] | None = None`, `binder: ToolBinder | None = None` (was the same list without `group`).
- `backend/app/services/tools.py` — `TOOL_REGISTRY: list[ToolDef]` — changed: all 14 existing entries gain `group=` per the plan's table (`web_search` → `"web"`; `codex_search`, `codex_read_entry`, `write_codex_draft`, `create_codex_entry` → `"codex"`; the nine chapter/close tools → `"book"`), and four new entries are appended in this order: `codex_list_entries`, `codex_list_characters`, `codex_list_locations`, `codex_list_facts` — each `args_schema=CodexList*Args`, `group="codex"`, `binder=bind_codex_list_*`. Registry length 14 → 18.
- **The four new entries' `description=` strings are PLACEHOLDERS** (`"UNIMPLEMENTED (skeleton 025): this text is the coder's."`). They exist only so the dataclass constructs. The coder writes the real prose: each must name `codex_read_entry` and `codex_search`, and `codex_list_facts`'s must contain the word "lore" while its `kind` filter stays `fact` (DoD-11, DoD-13).
- The `from app.services.codex_tools import (...)` block gains the four args classes and the four binders.

**`backend/app/models/schemas/assistant_config.py`**

- `backend/app/models/schemas/assistant_config.py` — `class ToolResponse(BaseModel)` — changed: `name: str`, `description: str`, `group: str` (was the first two only).

**`backend/app/services/assistant_config.py`**

- `backend/app/services/assistant_config.py` — `async def list_tools() -> ToolsListResponse` — **signature unchanged**. The one-line pass-through `ToolResponse(name=..., description=..., group=tool.group)` was wired because `ToolResponse.group` is required and the call would not construct otherwise.

**`frontend/src/types/assistantConfig.d.ts`**

- `frontend/src/types/assistantConfig.d.ts` — `export interface AssistantTool { name: string; description: string; group: string; }` — changed (was the first two fields). The doc comment gains a `group` paragraph; correcting its "**exactly two** fields" sentence is still the coder's (DoD-23).

**`frontend/src/api/assistantConfig.ts`**

- `frontend/src/api/assistantConfig.ts` — `export const TOOL_GROUP_LABELS: Record<string, string>` — new, complete (not a stub): `codex: "Codex access"`, `book: "Book access"`, `web: "Web access"`. Placed immediately before `modeLabel`, beside `MODE_LABELS`. No `"other"` key, by design.

**`frontend/src/admin/components/assistant-config/ToolPicker.tsx` (new file)**

- `frontend/src/admin/components/assistant-config/ToolPicker.tsx` — `interface ToolPickerProps { tools: AssistantTool[]; selected: Set<string>; onToggle: (name: string, checked: boolean) => void; emptyMessage: string; }` — new, **module-private (not exported)**.
- `frontend/src/admin/components/assistant-config/ToolPicker.tsx` — `export const ToolPicker = observer(function ToolPicker({ tools, selected, onToggle, emptyMessage }: ToolPickerProps) { ... })` — new. Wrapped in `observer`. **Body UNIMPLEMENTED**: it discards the four props (`void tools;` … — `noUnusedParameters` is on in `tsconfig.json`) and returns `null`. The coder replaces the whole body; the `void` statements go with it.

Deliberately NOT touched (the coder's; no signature to freeze): `ModeEditorModal.tsx` and
`SubAgentFormModal.tsx` (exported signatures and props interfaces unchanged, `<ToolPicker>` not yet
wired in), `backend/app/db/mode_tools.py`, `backend/app/db/assistant_modes.py`.

### Caller-compile edits (out of Source-files scope)

- `backend/app/services/subagent_delegation.py` (~line 293) — the synthetic delegation `ToolDef(...)` is the only `ToolDef` construction outside `tools.py`, and `group` is now required, so it would no longer construct. Added `group="delegation"` plus a comment; nothing else in the file changed. A delegation tool is never in `TOOL_REGISTRY`, so it never reaches `list_tools()`, the admin catalogue or the grouped picker — it does not bear on DoD-6 (which is about the 18 registry rows) and introduces no fourth wire group. If the coder prefers a different key it is a one-token change with no other call site.

### Compile gate (2026-09-15)

- Backend (no static type-checker configured): `cd backend && .venv/Scripts/python -c "import app.services.subagent_delegation, app.services.tools, app.services.codex_tools, app.services.assistant_config, app.main"` — clean. `len(TOOL_REGISTRY) == 18`; the distinct registry groups are exactly `{"book", "codex", "web"}`.
- Frontend: `cd frontend && npx tsc --noEmit` — clean (exit 0).
- **Known, expected red, left for the coder (outline step 7):** `cd frontend && npm run test:types` reports three `TS2741: Property 'group' is missing … AssistantTool` errors — `tests/admin/AssistantModesPage.test.tsx:91`, `tests/admin/SubAgentsPage.test.tsx:112` and **`tests/admin/assistantConfigApi.test.ts:100`**, the third of which the plan's Test-files list does not mention. Test files are not the skeleton's to touch.
- **Also expected red:** three existing backend tests construct `ToolDef(...)` without `group` and will now fail at import — `backend/tests/services/test_assistant_runtime.py:178`, `backend/tests/services/test_subagent_delegation.py:222` and `:240`. Neither file is in the plan's Test-files list. (The skeleton ran no tests.)

## Tests

### Tests (2026-09-15)

- `backend/tests/services/test_codex_list_tools.py` (new) — covers DoD-1, DoD-2, DoD-3, DoD-4, DoD-5,
  DoD-11 — the excerpt boundary (parameterized: empty / whitespace-only / whitespace-heavy / raw-long-
  but-short-collapsed / exactly-60 / 61 / 61-after-collapsing), kind filtering + archived exclusion +
  `list_by_book` order pass-through + no cap (fixture of `max(search limits, 25) + 5`), the render
  contract (`entry_id=<id> | <name>` / `entry_id=<id> | <excerpt>`, header first and stating the
  count, full body never present), the empty listing as a plain sentence (empty book / empty kind in a
  populated book / archived-only), the `Codex error: `-prefixed failure path over all four tools × two
  exception types, and `codex_list_facts` saying "lore" while still filtering `fact`.
- `backend/tests/services/test_tools.py` (extended) — covers DoD-6 —
  `test_every_registry_entry_declares_a_valid_group__025_DoD6`: 18 entries, every `group` in
  `{"codex","book","web"}`, all three in use. The group assignment table is **not** duplicated
  (DoD-18 is `[verify]`).
- `backend/tests/routes/admin/test_assistant_config.py` (extended) — covers DoD-7 —
  `test_tools_catalogue_carries_group_in_registry_order__025_DoD7`: `(name, group)` pairs equal the
  registry's, in declaration order; every group in the wire vocabulary; 200 admin / 403 author /
  401 anonymous unchanged.
- `frontend/tests/admin/toolPicker.test.tsx` (new) — covers DoD-8, DoD-9, and DoD-10's toggle-callback
  clause — fixed Codex/Book/Web/Other order from a scrambled catalogue, unrecognised groups falling
  into the one trailing Other (never dropped), empty groups rendering no heading at all, Other
  suppressed when every group is known, catalogue order preserved within a group; every checkbox
  reachable unambiguously by accessible name, no heading folded into or acting as a checkbox, no
  select-all control; `onToggle(name, true)` / `onToggle(name, false)`.
- `frontend/tests/admin/AssistantModesPage.test.tsx` (extended) — covers DoD-10 (ModeEditorModal half)
  — the shared worked selection saves as that exact `tool_names` payload, the draft's `selectedTools`
  is a string `Set` whose replacement is observed as the checkbox re-rendering both ways, and
  `"No tools are available to select. This mode will run with no tools."` renders verbatim in full.
- `frontend/tests/admin/SubAgentsPage.test.tsx` (extended) — covers DoD-10 (SubAgentFormModal half) —
  the same worked selection against the same `SHARED_SELECTION` value, the same Set-replacement
  observation, and `"No tools are available to select. This sub-agent will run with no tools."`
  verbatim in full.

Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓, DoD-10 ✓,
DoD-11 ✓; DoD-12…DoD-24 [verify, no test]; DoD-25…DoD-27 [manual/live, no test].
Deliberately not tested (per `plan.md` -> `## Test plan`): 13 items.

### Fixture repairs forced by the re-frozen signatures (no assertion weakened)

- `frontend/tests/admin/AssistantModesPage.test.tsx` — `makeTool` now takes a required `group`; the
  three fixtures sit in three different groups (`web` / `book` / `codex`).
- `frontend/tests/admin/SubAgentsPage.test.tsx` — same repair, same three groups.
- `frontend/tests/admin/assistantConfigApi.test.ts` — `makeTool` gains `group` (defaulted; the wire
  module passes it through and no assertion there depends on the value). Not in the plan's Test-files
  list; repaired anyway, per the skeleton's compile-gate note.
- `backend/tests/services/test_assistant_runtime.py` — the synthetic `_EXTRA_TOOL` `ToolDef` declares
  `group="book"`.
- `backend/tests/services/test_subagent_delegation.py` — `_NOTE_TOOL` and `_COLLIDING_TOOL` likewise.

### Existing assertions updated to the new contract (risks 1 and 2 in `plan.md`)

- `backend/tests/services/test_tools.py::test_registry_has_single_web_search_entry__DoD3` — read and
  confirmed: it pins an EXACT registry name set (was 14). Widened to the 18 names by adding the four
  listing tools; still exact, still a set equality, nothing loosened.
- `backend/tests/routes/admin/test_assistant_config.py::test_tools_catalogue_name_and_description_only_admin_gated__DoD10_UC095`
  — its `set(entry.keys()) == {"name","description"}` contradicted DoD-7's widened wire object;
  updated to `{"name","description","group"}`. Still an exact key-set assertion.
- `backend/tests/routes/admin/test_assistant_config.py::test_no_api_key_or_tool_internals_in_any_response__DoD12`
  — the sibling occurrence of the same exact key-set assertion on every `GET /tools` item (that test
  is numbered against an EARLIER plan's DoD-12, unrelated to this feature's; not renumbered, not
  retagged). Widened the same way; everything it asserts about API keys and tool internals is
  untouched.
- `backend/tests/services/test_assistant_config_modes.py::test_list_tools_payload_exposes_only_name_and_description__DoD11_UC095`
  — the third and fourth occurrences of the same exact key-set assertion (`ToolResponse.model_fields`
  and each serialized wire item). Both widened to `{"name","description","group"}`, both still exact.
  Its `__DoD11_UC095` tag belongs to feature 012's numbering; not renumbered, not retagged. The
  no-`args_schema` / no-`callable` clause is untouched.
- `backend/tests/services/test_chapter_tools.py::test_open_chapter_turn_is_offered_the_seeded_four__DoD12`
  — the module-level `WRITE_CHAPTER_DEFAULT_TOOLS` literal held the pre-025 eight names; widened to
  `plan.md`'s twelve-name target tuple. The set equality and the derived `len(...)` assertion stay
  exact; `CHAPTER_TOOL_NAMES` and the empty-allowlist clauses are untouched. Its `__DoD12` tag belongs
  to feature 024's numbering, not this feature's.
- `backend/tests/db/test_mode_tools_seed.py` — `EXPECTED_TOOLS` widened to `plan.md`'s target tuples
  (the four listing names appended to `edit-character` / `edit-location` / `edit-fact` /
  `write-chapter`; `close-chapter` untouched). Every assertion in the file is unchanged; no new
  coverage added there.

## Notes & Issues

- Rendered contract as built (the strings are the coder's, per the skeleton record): header
  `This book's codex holds {count} {label}:` (`label` = `entries` / `character entries` /
  `location entries` / `fact (lore) entries`, singular when the count is 1), rows
  `entry_id={id} | {name or 60-char excerpt}`, empty `This book's codex has no {label} yet.`,
  failure `Codex error: this book's codex could not be listed.`
- The four tools share one private `_render_codex_listing(context, kind)` body — they differ only in
  the `kind` they pass and the noun they use, and four copies of the render contract could drift.
- The "Tools" section heading stayed in both modals (it labels the section, not the picker); only the
  `<Stack>`/`<ScrollArea.Autosize>`/`<Checkbox>` block moved into `ToolPicker`.
- `ToolPicker`'s display order is `TOOL_GROUP_LABELS`' own key order, so adding a group there is the
  single edit that places it; membership is tested with `Object.keys(...).includes(...)` rather than
  `in`, so a group named after an `Object.prototype` member cannot be mistaken for a known one.
- `backend/app/services/codex_tools.py`'s module docstring keeps its "Skeleton (025) … UNIMPLEMENTED"
  provenance note, following the `fast/007` note left in place after `create_codex_entry` shipped.
- Out of scope, not touched, worth recording: the sub-agent picker in `ModeEditorModal` and the
  accessible-modes picker in `SubAgentFormModal` are still duplicated the same way the tool picker
  was; both modals' `tools` prop doc still says "the registry has one entry today" (stale since 013).
