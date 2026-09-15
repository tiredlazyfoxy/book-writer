# Feature 025 — Codex listing tools

Ultra track. Single continuous build, no step boundaries. See `context.md` for feature-wide facts.

## Goal

Give the assistant four new tools to enumerate the codex (all entries, or filtered to characters /
locations / facts) instead of only searching or reading-by-id, and give the admin tool-picker a
`group`-based layout so the 18-entry registry no longer renders as one flat checkbox column.

## Source areas

- `backend/app/services/codex_tools.py` — four new listing tools, their binders, four zero-field args
  schemas, the private excerpt helper.
- `backend/app/services/tools.py` — `ToolDef.group` field; the four new `TOOL_REGISTRY` entries; the
  `group=` value added to all 18 entries.
- `backend/app/services/assistant_config.py` — `list_tools()` maps `group` through.
- `backend/app/db/mode_tools.py` — `DEFAULT_MODE_TOOL_NAMES` constant, module-level only.
- `backend/app/db/assistant_modes.py` — `DEFAULT_MODE_SYSTEM_PROMPTS` constant, module-level only.
- `backend/app/models/schemas/assistant_config.py` — `ToolResponse.group`.
- `frontend/src/admin/components/assistant-config/` — new `ToolPicker.tsx`; `ModeEditorModal.tsx`
  loses its duplicated tool-checkbox JSX, wires `<ToolPicker>` instead.
- `frontend/src/admin/components/sub-agents/SubAgentFormModal.tsx` — same wiring, no new component.
- `frontend/src/api/assistantConfig.ts` — `TOOL_GROUP_LABELS`.
- `frontend/src/types/assistantConfig.d.ts` — `AssistantTool.group`, doc comment correction.

## Test files

- `backend/tests/services/test_codex_list_tools.py` (new)
- `backend/tests/services/test_tools.py` (extend)
- `backend/tests/routes/admin/test_assistant_config.py` (extend)
- `backend/tests/db/test_mode_tools_seed.py` (extend — existing assertions may need updating for the
  widened `DEFAULT_MODE_TOOL_NAMES` tuples; no new `[test]` DoD lives here)
- `frontend/tests/admin/toolPicker.test.tsx` (new)
- `frontend/tests/admin/AssistantModesPage.test.tsx` (extend — mock tool fixtures need `group`)
- `frontend/tests/admin/SubAgentsPage.test.tsx` (extend — mock tool fixtures need `group`)

## Interface

### `backend/app/services/codex_tools.py`

Follow the module's `TYPE_CHECKING` + quoted `"ToolContext"` import-cycle guard exactly (see existing
`codex_search` et al.). Each tool resolves the book from `context.book_id` only — no model-supplied
arguments.

```python
async def codex_list_entries(context: "ToolContext") -> str:
async def codex_list_characters(context: "ToolContext") -> str:
async def codex_list_locations(context: "ToolContext") -> str:
async def codex_list_facts(context: "ToolContext") -> str:
```

Each: calls `codex_entries.list_by_book(context.book_id, kind=<kind or None>, include_archived=False)`
and renders the short-form listing. `codex_list_entries` passes `kind=None`; the other three pass
their `CodexKind` member. Returns the rendered string on success, the plain "no entries yet" sentence
when the list is empty, or a `"Codex error: "`-prefixed string on failure. **Never raises.**

Binders — one line each, following `bind_codex_search`:

```python
def bind_codex_list_entries(context: "ToolContext") -> Callable[..., object]:
    return functools.partial(codex_list_entries, context)
def bind_codex_list_characters(context: "ToolContext") -> Callable[..., object]:
    return functools.partial(codex_list_characters, context)
def bind_codex_list_locations(context: "ToolContext") -> Callable[..., object]:
    return functools.partial(codex_list_locations, context)
def bind_codex_list_facts(context: "ToolContext") -> Callable[..., object]:
    return functools.partial(codex_list_facts, context)
```

Args schemas — four named, zero-field classes, following `ReadContinuityContextArgs`
(`app/services/close_tools.py:278`), **not** one shared class (a shared class stamps one `title` onto
every tool's `parameters` object):

```python
class CodexListEntriesArgs(BaseModel):
    """No fields: always lists this book's whole codex."""

class CodexListCharactersArgs(BaseModel):
    """No fields: always lists this book's character entries."""

class CodexListLocationsArgs(BaseModel):
    """No fields: always lists this book's location entries."""

class CodexListFactsArgs(BaseModel):
    """No fields: always lists this book's fact (lore) entries."""
```

Private excerpt helper:

```python
def _excerpt(text: str, limit: int = 60) -> str:
```

Collapses whitespace runs to a single space, trims, takes the first `limit` characters, appends `…`
**only** when the collapsed text was longer than `limit`.

Each tool's `description` (registered in `tools.py`) must name `codex_read_entry` (how to get the
full body) and `codex_search` (search vs. enumerate). `codex_list_facts`'s description must contain
the word "lore" while the `kind` it filters on stays `fact`.

Render contract, all four tools:
1. Header line naming what was listed and the **count**.
2. One line per entry, in `list_by_book`'s own order (the tools impose no ordering, no cap): named
   entry → `entry_id=<id> | <name>`; unnamed entry (`name is None`, e.g. facts) → `entry_id=<id> |
   <excerpt>`.
3. Empty result → a plain sentence stating this book's codex has no entries of that kind yet. Never
   an empty string, never a bare header, never `Codex error:`-prefixed.
4. Failure → a string beginning `Codex error: `, matching the module's existing convention. Never
   raises.

### `backend/app/services/tools.py`

`ToolDef` gains `group: str`, **required, no default**, positioned after `args_schema` and before
`callable`/`binder` (a required field cannot follow a defaulted one):

```python
@dataclass(frozen=True)
class ToolDef:
    name: str
    description: str
    args_schema: type[BaseModel]
    group: str
    callable: Callable[..., object] | None = None
    binder: ToolBinder | None = None
```

All 18 `TOOL_REGISTRY` entries declare `group=` one of `"codex"` / `"book"` / `"web"`:

- `"codex"`: `codex_search`, `codex_read_entry`, `write_codex_draft`, `create_codex_entry`,
  `codex_list_entries`, `codex_list_characters`, `codex_list_locations`, `codex_list_facts`
- `"book"`: `read_chapter_text`, `set_chapter_text`, `update_selection`, `add_text`,
  `draft_chapter_summary`, `draft_chapter_notes`, `propose_active_notes`, `raise_check_flag`,
  `read_continuity_context`
- `"web"`: `web_search`

Four new `ToolDef(...)` entries added to `TOOL_REGISTRY`, `binder=bind_codex_list_*` each, following
the existing `codex_search` construction shape (description + `args_schema=CodexList*Args` +
`group="codex"` + `binder=bind_codex_list_*`).

### `backend/app/models/schemas/assistant_config.py`

```python
class ToolResponse(BaseModel):
    name: str
    description: str
    group: str
```

### `backend/app/services/assistant_config.py`

```python
async def list_tools() -> ToolsListResponse:
```

Signature unchanged. Body maps `group` through:
`ToolResponse(name=tool.name, description=tool.description, group=tool.group)` for every
`TOOL_REGISTRY` entry, declaration order preserved, still no DB access.

### `backend/app/db/mode_tools.py`

`DEFAULT_MODE_TOOL_NAMES` target shape — each of `edit-character`, `edit-location`, `edit-fact`,
`write-chapter` gains all four new tool names appended to its existing tuple; `close-chapter`
unchanged:

```python
DEFAULT_MODE_TOOL_NAMES: dict[str, tuple[str, ...]] = {
    "edit-character": (
        "web_search", "codex_search", "codex_read_entry", "write_codex_draft",
        "create_codex_entry", "codex_list_entries", "codex_list_characters",
        "codex_list_locations", "codex_list_facts",
    ),
    "edit-location": (
        "web_search", "codex_search", "codex_read_entry", "write_codex_draft",
        "create_codex_entry", "codex_list_entries", "codex_list_characters",
        "codex_list_locations", "codex_list_facts",
    ),
    "edit-fact": (
        "web_search", "codex_search", "codex_read_entry", "write_codex_draft",
        "create_codex_entry", "codex_list_entries", "codex_list_characters",
        "codex_list_locations", "codex_list_facts",
    ),
    "write-chapter": (
        "web_search", "codex_search", "codex_read_entry", "create_codex_entry",
        "read_chapter_text", "set_chapter_text", "update_selection", "add_text",
        "codex_list_entries", "codex_list_characters", "codex_list_locations", "codex_list_facts",
    ),
    "close-chapter": (
        "draft_chapter_summary", "draft_chapter_notes", "propose_active_notes",
        "raise_check_flag", "read_continuity_context",
    ),
}
```

`seed_default_mode_tools()` (line 138) is **unchanged** — body, and its mode-level idempotency unit.

### `backend/app/db/assistant_modes.py`

`DEFAULT_MODE_SYSTEM_PROMPTS` — each of the `edit-character`, `edit-location`, `edit-fact`,
`write-chapter` prompts gains one new paragraph naming the listing tools, following the house pattern
("one paragraph per different tool, different guard"). `close-chapter` untouched. Exact wording is
the coder's; no signature to freeze here (this is prose content, not a symbol).

### `frontend/src/types/assistantConfig.d.ts`

```ts
export interface AssistantTool {
  name: string;
  description: string;
  group: string;
}
```

Doc comment's "carries **exactly two** fields" claim must be corrected to reflect three.

### `frontend/src/api/assistantConfig.ts`

```ts
export const TOOL_GROUP_LABELS: Record<string, string> = {
  codex: "Codex access",
  book: "Book access",
  web: "Web access",
};
```

Placed beside `MODE_LABELS`, same shape, same doc-comment style (runtime const, so it lives in the
`.ts` api module rather than the `.d.ts` file — the `BACKEND_OPTIONS`/`MODE_LABELS` precedent). No
`"other"` key: `ToolPicker` supplies the literal `"Other"` heading itself for any `group` not present
in this map.

### `frontend/src/admin/components/assistant-config/ToolPicker.tsx` (new)

```tsx
interface ToolPickerProps {
  tools: AssistantTool[];
  selected: Set<string>;
  onToggle: (name: string, checked: boolean) => void;
  emptyMessage: string;
}

export const ToolPicker = observer(function ToolPicker({
  tools, selected, onToggle, emptyMessage,
}: ToolPickerProps) {
```

`ToolPickerProps` is **module-private** (not exported), following the house style of
`ModeEditorModalProps` / `SubAgentFormModalProps`. Renders `emptyMessage` verbatim when `tools` is
empty (identical shape to the existing empty-catalogue block: `<Text size="sm" c="dimmed">`). Groups
`tools` by `.group` in the fixed display order Codex (`"codex"`) → Book (`"book"`) → Web (`"web"`) →
Other (any `group` not a key of `TOOL_GROUP_LABELS`, heading literal `"Other"`). A group with zero
tools renders nothing — no heading, no container. Catalogue order is preserved within each group.
Each tool renders the same `<Checkbox>` shape the two modals use today (`label`, `description`,
`checked={selected.has(tool.name)}`, `onChange` calling `onToggle(tool.name, e.currentTarget.checked)`
). No select-all control; no group heading is a checkbox or is folded into one's accessible name.

### `frontend/src/admin/components/assistant-config/ModeEditorModal.tsx` and `frontend/src/admin/components/sub-agents/SubAgentFormModal.tsx`

Exported component signatures and props interfaces (`ModeEditorModalProps`, `SubAgentFormModalProps`)
are **unchanged**. Each replaces its inline `<Stack>`/`<ScrollArea.Autosize>`/`<Checkbox>` tool block
with `<ToolPicker tools={tools} selected={draft.selectedTools} onToggle={...} emptyMessage={...} />`,
where the toggle logic still rebuilds `draft.selectedTools` as a **new** `Set` (replaced, not
mutated) — same behavior `toggleTool` has today, wired through the new prop instead of inlined into
`Checkbox.onChange`. The two full empty-catalogue strings, used verbatim as each modal's
`emptyMessage`:

- `ModeEditorModal`: `"No tools are available to select. This mode will run with no tools."`
- `SubAgentFormModal`: `"No tools are available to select. This sub-agent will run with no tools."`

## Implementation outline

1. `services/codex_tools.py`: add `_excerpt`, the four zero-field args schemas, the four tool
   functions and their binders, following the existing codex-tool conventions verbatim.
2. `services/tools.py`: add `ToolDef.group`; add `group=` to all 14 existing registry entries; add
   the four new `TOOL_REGISTRY` entries.
3. `models/schemas/assistant_config.py` + `services/assistant_config.py`: thread `group` through
   `ToolResponse` and `list_tools()`.
4. `db/mode_tools.py` + `db/assistant_modes.py`: extend `DEFAULT_MODE_TOOL_NAMES` and
   `DEFAULT_MODE_SYSTEM_PROMPTS` per above; leave `seed_default_mode_tools()` untouched.
5. `types/assistantConfig.d.ts` + `api/assistantConfig.ts`: add `AssistantTool.group` (+ doc-comment
   fix) and `TOOL_GROUP_LABELS`.
6. New `ToolPicker.tsx`; wire it into `ModeEditorModal.tsx` and `SubAgentFormModal.tsx`, removing the
   duplicated JSX.
7. Update `AssistantModesPage.test.tsx` and `SubAgentsPage.test.tsx` mock tool fixtures with a
   `group` value so `tsc`/`test:types` stay green.

## Definition of done

1. `[test]` Excerpt helper collapses whitespace runs to a single space, trims, cuts to 60 chars,
   appends `…` only when the collapsed text exceeded 60 (parameterized: exactly-60, 61,
   whitespace-heavy, empty).
2. `[test]` Each per-kind tool returns only its kind and excludes the other two; `codex_list_entries`
   returns all three kinds; archived entries excluded from all four; entry order matches whatever
   `list_by_book` returned (no ordering imposed); a fixture larger than any search-style limit proves
   there is no cap.
3. `[test]` Render contract: header line names what was listed and states the count; named entry →
   `entry_id=<id> | <name>`; unnamed entry → `entry_id=<id> | <excerpt>`; full body never appears.
4. `[test]` Empty listing renders the plain "no entries of this kind yet" sentence — never an empty
   string, never a bare header, never `Codex error:`-prefixed.
5. `[test]` Any failure path returns a string beginning `Codex error: `; no listing tool raises.
6. `[test]` All 18 `TOOL_REGISTRY` entries declare a `group` in `{"codex","book","web"}`.
7. `[test]` `GET /api/admin/assistant-config/tools` returns `group` for every tool, same values and
   declaration order as the registry, behind the existing admin-only authorization (status codes and
   auth requirement unchanged).
8. `[test]` `ToolPicker` groups in fixed order Codex/Book/Web/Other; an unrecognised `group` renders
   under Other and is never dropped; a group with no tools renders nothing at all (no heading, no
   container); catalogue order preserved within a group.
9. `[test]` Every tool checkbox stays reachable by its accessible name after grouping; no group
   heading is folded into a checkbox's accessible name; no heading is itself a checkbox; no
   select-all control exists.
10. `[test]` Both `ModeEditorModal` and `SubAgentFormModal` save the same `tool_names` payload for a
    given selection; `selectedTools` stays a `Set<string>` replaced (not mutated) on each toggle; the
    toggle callback fires with `(name, checked)`; both empty-catalogue messages render verbatim in
    full.
11. `[test]` `codex_list_facts`'s description contains the word "lore" while its `kind` filter stays
    `fact`.
12. `[verify]` The four new tools exist in `TOOL_REGISTRY` under their exact names.
13. `[verify]` Each of the four descriptions names `codex_read_entry` and `codex_search`.
14. `[verify]` `DEFAULT_MODE_TOOL_NAMES` gains the four listing-tool names under `edit-character`,
    `edit-location`, `edit-fact`, `write-chapter`; `close-chapter` unchanged.
15. `[verify]` `DEFAULT_MODE_SYSTEM_PROMPTS` gains one new paragraph naming the listing tools in each
    of those same four prompts; `close-chapter` unchanged.
16. `[verify]` `seed_default_mode_tools()`'s body and its mode-level idempotency unit are unchanged.
17. `[verify]` `ToolDef.group: str` is required (no default), positioned after `args_schema` and
    before `callable`/`binder`.
18. `[verify]` The 18-row group assignment table matches this plan tool-for-tool.
19. `[verify]` `ToolResponse` carries `group`; `list_tools()` maps it through in declaration order.
20. `[verify]` `ToolPicker` renders exactly one checkbox per catalogue tool, nothing hard-coded.
21. `[verify]` The existing 0/1/3-tool catalogue assertions in both admin page specs still hold.
22. `[verify]` `TOOL_GROUP_LABELS` is defined for `codex`/`book`/`web`, matching `MODE_LABELS`'s shape
    and doc-comment style.
23. `[verify]` `AssistantTool.group: string` is added and its doc comment's "exactly two fields"
    claim is corrected.
24. `[verify]` `ModeEditorModal` and `SubAgentFormModal` render `<ToolPicker>` in place of the
    duplicated JSX; that inline markup no longer exists in either file.
25. `[manual/live]` On an existing database the four tools are registered but selected in no mode
    until an admin ticks them for `edit-character`, `edit-location`, `edit-fact`, `write-chapter` —
    accepted consequence, not a defect.
26. `[manual/live]` `frontend/src/types/assistantConfig.d.ts:AssistantTool` declares `group: string`
    and the frontend typechecks: `cd frontend && npm run build` and `cd frontend && npm run
    test:types` both pass.
27. `[manual/live]` `ToolPicker` is wrapped in `observer`, and `cd frontend && npm test` passes.

## Test plan

**Tested:**
- DoD-1 — excerpt helper whitespace/cut/ellipsis boundary — edge semantics, boundary condition (60
  vs 61 chars) a coder is likely to get off-by-one.
- DoD-2 — kind filtering, archived exclusion, order pass-through, no cap — invariant over the four
  tools' shared filtering contract.
- DoD-3 — render contract for named vs unnamed entries — contract the model depends on to parse the
  listing; a `fact`'s `name is None` case is easy to get backwards.
- DoD-4 — empty-listing sentence — edge semantics with a real failure mode (misreading "nothing
  found" as an error, see design notes).
- DoD-5 — failure path never raises — invariant; a raising tool aborts the whole assistant turn.
- DoD-6 — every registry entry has a valid `group` — invariant over a 18-row table a human will edit
  again.
- DoD-7 — `GET /tools` wire contract + auth — seam between backend DTO and the admin route,
  end-to-end.
- DoD-8 — `ToolPicker` grouping algorithm — the feature's core algorithm (ordering, Other fallback,
  empty-group suppression).
- DoD-9 — accessible names survive grouping — a11y invariant with a real, non-obvious failure mode
  (`getByRole` ambiguity, not a miss — see design notes).
- DoD-10 — both modals' save payload + Set-replace + callback contract — state-machine invariant
  (MobX replace-not-mutate) plus a contract two call sites must share identically.
- DoD-11 — `codex_list_facts` "lore" wording vs `fact` kind — vocabulary decision the user chose to
  pin with a real test (kept as `[test]` by explicit user call, not `[verify]`).

**Not tested (deliberate):**
- DoD-12, the four tools present in `TOOL_REGISTRY` under exact names — symbol existence.
- DoD-13, each description naming `codex_read_entry`/`codex_search` — asserts prose content; fails on
  any rewording; DoD-11 already covers the one wording constraint worth pinning.
- DoD-14, `DEFAULT_MODE_TOOL_NAMES` gaining the four names under the four edit-*/write-chapter modes
  — config constant, no logic.
- DoD-15, `DEFAULT_MODE_SYSTEM_PROMPTS` naming the listing tools in those same four prompts — config
  constant / prose content.
- DoD-16, `seed_default_mode_tools()` unchanged — asserting an absence; existing tests already pin
  the function's behavior.
- DoD-17, `ToolDef.group` required + field position — would not compile otherwise.
- DoD-18, the 18-row group table tool-for-tool — duplicates the registry into a test file; DoD-6
  already catches the real failure (an invalid or missing `group`).
- DoD-19, `ToolResponse`/`list_tools()` carrying `group` — DTO field and a one-line pass-through, both
  covered end-to-end by DoD-7.
- DoD-20, `ToolPicker` one-checkbox-per-tool with nothing hard-coded — covered by DoD-8.
- DoD-21, the existing 0/1/3-tool catalogue assertions still holding — pre-existing suite, run by the
  verifier as part of the full test run.
- DoD-22, `TOOL_GROUP_LABELS` definition — trivial constant mirroring an existing precedent
  (`MODE_LABELS`).
- DoD-23, `AssistantTool` doc-comment correction — no runtime behavior to assert.
- DoD-24, `ToolPicker` wired into both modals in place of the duplicated JSX — exercised end-to-end
  by DoD-8/9/10's rendering tests, which already run against both modals.

## Decisions taken

- **Ultra track, not multi-step or fast** — ~350 LoC across three layers, but every design decision
  was already settled before the build starts; nothing for the user to decide *between* pieces.
  Rejected: keeping the step cycle (buys nothing when no question is open); `/fast-feature` (over its
  ~300 LoC ceiling).
- **Four distinct tool names, not one `codex_list` with a `kind` argument** — distinct names are
  easier for a weak model to pick than an enum value. User decision, not open.
- **No cap, no pagination** — the context-flooding risk was raised with the user, who chose
  completeness. Consequence: `db/codex_entries.py:list_by_book` stays untouched, no `limit`/`offset`.
- **`group` declared backend-side, required, no default** — rejected a frontend `name → group` map,
  which would silently miss every tool added later. Positioning after `args_schema`, before
  `callable`/`binder` is load-bearing (a required field cannot follow a defaulted one).
- **`seed_default_mode_tools()` not modified** — rejected a per-`(mode, tool)` additive backfill,
  which could resurrect a tool an admin deliberately removed. Accepted consequence: existing
  databases need an admin operating step (see `context.md`).
- **Excerpt helper: new, private, 60 characters** — rejected unifying with the frontend's 120-char
  `bodyExcerpt` in `CodexListPage.tsx`: different layer, different budget (a human reading a list
  pane vs. a model's context window).
- **Grouping is visual only** — no select-all-in-group, no collapse, no group state anywhere.
  Rejected: group-level selection controls, the user's explicit call. "Other" is a trailing catch-all
  so an unrecognised group is rendered, never dropped.
- **Extract the tool picker only** — rejected also extracting the sub-agent picker in
  `ModeEditorModal` and the accessible-modes picker in `SubAgentFormModal`: both duplicated the same
  way, both widen the change past budget; named and left alone.
- **No new `db/` query** — `list_by_book` already orders deterministically and excludes archived rows
  by default; `mode_tools.py`/`assistant_modes.py` touched only for their default constants.
- **Zero-field args schema risk is void, not an escape valve** — the original plan flagged this as an
  open risk; `pydantic_to_openai_tool` simply calls `model_json_schema()`, and
  `ReadContinuityContextArgs` is already a production zero-field schema. No special-casing needed.
- **Four named zero-field schema classes, not one shared `EmptyArgs`** — `model_json_schema()` puts
  the class name into the `parameters` object's `title`; a shared class would stamp the same title on
  all four tools, and every other registry tool already has its own schema class.
- **Empty result is a plain sentence, not an error string** — the module has three string categories
  (`Codex error:` / `Codex ... refused:` / plain); ordinary "nothing found" is deliberately none of
  the first two, following the `No codex entries found for "{query}".` precedent.
- **Selective test plan re-sorted for the ultra track**: the step-track draft carried 36 `[test]`
  items and 0 `[verify]`; this plan re-sorts to 11 `[test]` / 13 `[verify]` / 3 `[manual/live]`
  against the rubric (algorithm/invariant/contract/seam vs. symbol-existence/config-constant/
  compile-time-guaranteed).
- **The lore-wording test kept as `[test]`, user's call** — guards a vocabulary decision (author's
  word "lore" vs. enum value `fact`), not a line of implementation; accepted cost is a test that fails
  on any rewording of that one description.
- **Two corrections carried from the conversion**: the empty-catalogue strings are
  `"No tools are available to select. This mode/sub-agent will run with no tools."` in full (the
  step-track draft recorded only the trailing substring); the frontend mock tool fixtures in
  `AssistantModesPage.test.tsx`/`SubAgentsPage.test.tsx` must gain a `group` field or `tsc` fails
  under `npm run test:types` — neither was listed as work in the original steps.

## Out of scope

- Any change to `backend/app/db/codex_entries.py`. No `limit`/`offset` added to `list_by_book`.
- Pagination, result caps or `limit`/`offset` anywhere.
- A get-by-id tool. `codex_read_entry` already exists and already takes an id.
- Any change to `seed_default_mode_tools()`'s body or its mode-level idempotency unit.
- Deduplicating the sub-agent picker in `ModeEditorModal` or the accessible-modes picker in
  `SubAgentFormModal`. Name them, leave them.
- Unifying the new 60-char backend excerpt with the frontend's 120-char `bodyExcerpt` in
  `work/pages/CodexListPage.tsx`, or changing the latter.
- `close-chapter`'s seeded tools and prompt.
- Editing `docs/plans/roadmap.md` or anything in `docs/architecture/` / `docs/product/`.

## Risks

- `test_tools.py::test_registry_has_single_web_search_entry__DoD3` is stale-named from an earlier,
  smaller registry (14 → 18 entries here); its body was never opened during harvesting — the coder
  must read it before assuming it still passes, rather than leaving it for the verifier to flag as a
  mystery regression.
- `tests/db/test_mode_tools_seed.py` may carry assertions tied to the old (shorter)
  `DEFAULT_MODE_TOOL_NAMES` tuples (e.g. exact tool counts per mode); widening those tuples could
  break an existing assertion that was not written against this change.
- None identified beyond the above — the zero-field schema path is confirmed safe by production
  precedent (`ReadContinuityContextArgs`), and no new `db/` query or layer-boundary crossing is
  introduced.
