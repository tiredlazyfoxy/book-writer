# Feature 026 — memos

| Step | File                            | Status  | Verifier | Date |
|------|---------------------------------|---------|----------|------|
| 001  | `001.memo-table.md`             | done    | PASS     | 2026-09-15 |
| 002  | `002.memo-service.md`           | done    | PASS     | 2026-09-15 |
| 003  | `003.memo-routes.md`            | done    | PASS     | 2026-09-15 |
| 004  | `004.memo-reorder.md`           | done    | PASS     | 2026-09-15 |
| 005  | `005.memo-state-axes.md`        | done    | PASS     | 2026-09-15 |
| 006  | `006.memos-prompt-layer.md`     | done    | PASS     | 2026-09-15 |
| 007  | `007.memos-in-delegation.md`    | done    | PASS     | 2026-09-15 |
| 008  | `008.create-memo-tool.md`       | done    | PASS     | 2026-09-15 |
| 009  | `009.memos-api-and-navigator.md`| done    | PASS     | 2026-09-15 |
| 010  | `010.memos-list-page.md`        | done    | PASS     | 2026-09-15 |
| 011  | `011.memos-list-reorder.md`     | done    | PASS     | 2026-09-15 |

## Files Changed

### Step 001 — the `memos` table, its `db/` module, registration and JSONL codec
- `backend/app/models/memo.py` — the `Memo` SQLModel table, no unique constraint (skeleton-written, unchanged)
- `backend/app/db/memos.py` — session-free `create` / `get_by_id` / `list_for_author` / `update`; no delete, no timestamp policy
- `backend/app/db/engine.py` — `Memo` added to the MODEL-REGISTRATION SEAM (skeleton-written, unchanged)
- `backend/app/services/db_import_export.py` — `_memo_to_dict` / `_dict_to_memo` codec pair and the `memos` registry entry at index 11

### Step 002 — the memo schemas and the read / create / update service
- `backend/app/models/schemas/memos.py` — the four memo DTOs (skeleton-written, unchanged)
- `backend/app/services/memos.py` — `_require_member` / `_to_memo_response` / `_resolve_memo` / `list_memos` / `create_memo` / `update_memo_body` implemented, plus a module-private `_next_ordinal` helper (the single append rule, reused by steps 005 and 008)

### Step 003 — the list / create / body-update memo routes
- `backend/app/routes/memos.py` — `_map_memo_error` plus the `list_memos` / `create_memo` / `update_memo_body` handler bodies implemented; the router, the two-entry reason→status map, the frozen signatures and the load-bearing declaration order (the `/{memo_id}` PUT last, with step 004's insertion-point comment above it) are skeleton-written and unchanged
- `backend/app/main.py` — router import and `include_router` (skeleton-written, unchanged)

### Step 004 — reorder: the whole-set service rule and `PUT …/memos/order`
- `backend/app/services/memos.py` — `reorder_memos` body implemented: loads the caller's non-archived set, refuses a wrong length / duplicate / absent id whole as one `invalid_reorder_set` before any write, then rewrites ordinals `1..N` per row through `db.memos.update`; no `authz.require`, no `Capability`, no `book_state` read, no bulk `db/` writer
- `backend/app/routes/memos.py` — `reorder_memos` handler body implemented: delegates and maps `MemoError` through `_map_memo_error` (HTTP only)
- `backend/app/models/schemas/memos.py` — `ReorderMemosRequest` skeleton-written, unchanged

### Step 005 — the two axes: activate / deactivate, archive / restore
- `backend/app/services/memos.py` — the four state-axis bodies implemented: each guards membership, resolves through the existing `_resolve_memo` (one `404`-shaped refusal), writes exactly one flag and stamps `modified_at`; archive leaves **both** `active` and `ordinal` alone (the gap is never renumbered), restore appends last through step 002's `_next_ordinal` and preserves `active`; all four are idempotent `200` no-ops that write nothing — not even `modified_at` — when the memo is already in the requested state (restore's no-op leaves `ordinal` alone too); no new reason, no `409`, no delete, no `book_state` read
- `backend/app/routes/memos.py` — the four no-body `POST` handler bodies implemented: delegate and map `MemoError` through the unchanged `_map_memo_error` / `_MEMO_ERROR_STATUS` (HTTP only); declaration order and signatures skeleton-written and unchanged

### Step 006 — the `MEMOS` prompt layer: fourth position, rendered once
- `backend/app/services/prompt_composition.py` — the skeleton's `NotImplementedError` guard removed and `("MEMOS", memos)` inserted between `("AUTHOR", author)` and `("CHAPTER", chapter)`, so the rendered order is `BASE`, `MODE`, `AUTHOR`, `MEMOS`, `CHAPTER`; the label is an inline literal like the other four and the existing blank/absent skip rule covers it unchanged; the module stays pure (no session, no clock, no knowledge of what a memo is) and the docstring keeps its frozen-signature / no-compatibility-alias statement with `author` third
- `backend/app/services/chat_turn.py` — `render_memos_section` implemented: pure, renders the bodies **in the order given** (no sort, rank, budget or truncation), skips a body blank after stripping so an empty memo leaves no stray separator, joins the survivors with a module-level `_MEMO_SEPARATOR` horizontal rule (`\n\n---\n\n`) so two memos cannot read as one, and returns `None` when nothing survives; `compose_turn_system_prompt` now does **one** unconditional `memos_db.list_for_author(chat.book_id, chat.author_id)` read (archived excluded at the read, `active` filtered in memory, no `BookAccess` built) beside the mode / author / chapter reads and returns the section on the frozen `ComposedTurnPrompt` so step 007 needs no second read; a stale `# Layer 4` comment above the chapter read corrected to `# Layer 5`; no SSE frame, `run_turn` signature or tool gating changed

### Step 007 — the memo section rides on `ParentTurn` into delegation
- `backend/app/services/subagent_delegation.py` — `_compose_delegated_system`'s body implemented: it calls `prompt_composition.compose_system_prompt(memos=memos_section)` with the **memos layer alone** (no base / mode / author / chapter argument is ever passed, so no other layer can thread into a nested call), returns `sub_agent_prompt` **verbatim** when the composer yields `""` — byte-identical to the pre-026 nested system, no empty section and no stray separator — and otherwise joins the two with `_DELEGATED_SECTION_JOIN`. The composer keeps sole ownership of the `MEMOS` label, the strip and the empty-layer skip rule, so the child's section cannot drift from the parent's and that rule stays written once. The module still performs **no memos read of its own** — no memo `db/` import, no call to the turn's section renderer; the section arrives on `ParentTurn` or not at all. The synthetic-tool derivation and its collision guard, the sub-agent's own tool allowlist, its own model resolution, its own `max_loops` and `run_delegation`'s short-error-string guard are untouched
- `backend/app/services/chat_turn.py` — no change needed beyond the skeleton's wiring: `run_turn` already passes step 006's `memos_section` local into `ParentTurn(...)`; no second read, no re-render
- `backend/app/services/assistant_runtime.py` — no change needed beyond the skeleton's docstring note that `parent` also carries the turn's already-rendered `MEMOS` section and that `resolve_turn_tools` merely passes it through; mode determination, `allowed_tool_names`, the resolution rules and `BASE_TOOL_NAMES` untouched

### Step 008 — the `create_memo` tool: registry entry, base set, seeded modes
- `backend/app/services/memo_tools.py` — the skeleton's `create_memo` body implemented: the refusal chain is an absent `context.access` and **nothing else** (no archived-book link, no proposal-mode link), then one call to `memo_service.create_memo(access, CreateMemoRequest(body=body))` so the append-at-`max + 1` rule and the `active` default stay in step 002 alone — no ordinal is recomputed here and `context.subject` is never read. It **never raises**: a `MemoError` (a non-member today, anything the service adds later) comes back as the refusal template, and an outer `except Exception` returns the failure string while letting `asyncio.CancelledError` propagate. Schema, signatures, binder and the four message constants are the skeleton's and unchanged
- `backend/app/services/assistant_runtime.py` — `BASE_TOOL_NAMES` widened from `("web_search",)` to `("web_search", "create_memo")`, with the comment recording why both halves exist (BASE covers the mode-less surfaces, including the memos list itself; the seeded `mode_tool` rows keep US-129.AC-5's visible refusal reachable, BASE not overriding a mode's allowlist). Nothing else moved: no `ResolvedSubject` member, no `determine_mode` branch, no change to the three gating cases
- `backend/app/db/mode_tools.py` — `DEFAULT_MODE_TOOL_NAMES` gains `create_memo` in **all five** tuples, appended last in each to keep the tuples in `TOOL_REGISTRY` order; comment records why `close-chapter` gets it though it is denied `create_codex_entry` (a memo is the author's private note, not book content), and that this reaches fresh installs only. `seed_default_mode_tools()` and its per-mode `if await list_by_mode(mode_key): continue` idempotence untouched
- `backend/app/db/assistant_modes.py` — the same US-130 paragraph added to all five `DEFAULT_MODE_SYSTEM_PROMPTS` entries: `create_memo` is the author's private standing note, called **only on their direct request, never unasked**, saved immediately with no draft and no save step. One wording across the five so the guidance cannot drift. `DEFAULT_MODE_KEYS` and `seed_default_modes()`'s check-then-create logic untouched
- `backend/app/services/tools.py` — no change needed beyond the skeleton's import line and 19th `TOOL_REGISTRY` entry (`create_memo`, group `"book"`, `CreateMemoArgs`, binder set, no plain callable); `ToolContext` still holds exactly seven fields

### Step 009 — memos on the client's edges: types, api, nav entry, route, subject
- `frontend/src/api/memos.ts` — the only file with work in it: all eight bodies implemented as thin `request<T>` forwarders over the frozen method/path pairs (`GET …/memos?include_archived=<flag>`, `POST …/memos`, `PUT …/memos/{memoId}`, `PUT …/memos/order`, `POST …/memos/{memoId}/{activate,deactivate,archive,restore}`), ids interpolated as **strings** (no `Number(...)`), `signal?` forwarded on every call, the four state verbs sending **no** body; `listMemos` is the only unwrapper (`.items` → plain array) while `reorderMemos` resolves to the envelope declared inline at the call site (the `api/chapters.ts:reorderChapters` shape). No state, no MobX, no `try`/`catch` — `ApiError` propagates. The skeleton's module-private `stub(name, args): never` helper was **deleted** with the last body
- `frontend/src/types/memos.d.ts` — the four wire DTOs, ids `string`, no `user_id`, envelope unmodelled (skeleton-written, unchanged)
- `frontend/src/work/components/shell/navItems.ts` — the eighth `WORK_NAV_ITEMS` entry (`/memos`, "Memos", `IconNotes`, `paneTarget: "content"`, no `extraActiveSegments`); helpers untouched (skeleton-written, unchanged)
- `frontend/src/work/routes.tsx` — `<Route path="memos" element={<MemosListPage />} />` mounted directly, no `key={…}` wrapper, no `memos/:id` and no `memos/new` (skeleton-written, unchanged)
- `frontend/src/work/pages/MemosListPage.tsx` — the deliberate placeholder naming step 010 as its owner; no state, no api call, no `useEffect` (skeleton-written, unchanged)
- `frontend/src/work/subject.ts` — `SubjectKind` gains `"memos"` (eleventh, last) and `resolveEditability` gains the constant `{ editable: "whole", readOnlyReason: null }` memos branch; no new `EditableRegion` member, no `WriteRegion` widening, `checkWritePermission` untouched (skeleton-written, unchanged)
- `frontend/src/types/chats.d.ts` — the wire twin's `SubjectKind` gains `"memos"` and its "same ten members" claim now reads eleven (skeleton-written, unchanged)
- `frontend/src/work/components/shell/WorkNavigator.tsx` — **comment text only**, authorized for this step: both stale entry counts corrected to eight — the docstring's "renders the seven `WORK_NAV_ITEMS`" (the count the step-009 skeleton note flagged) and the render body's "023: ONE shape for all seven entries", whose substantive claim (one shape, no `paneTarget` branch) is kept intact. The two are corrected together so the file cannot give a future reader contradictory counts. No code, no markup, no behaviour changed

### Step 010 — the memos list page: create-and-focus, blur-save, the two axes
- `frontend/src/work/pages/memosListPageState.ts` — the class's four `get` computeds (`workingMemos` / `archivedMemos`, `ordinal`-ascending client-side filters over the one merged list; `displayedBodies`, draft-else-server resolved by `undefined` so `""` is a legitimate typed value; `isEmpty`) plus all six effect bodies. `loadMemos` makes the **one** `listMemos(bookId, true, signal)` call — archived included, so `showArchived` refetches nothing; `createMemo` posts `{ body: "" }` and appends the SERVER's row, writing its id to `focusMemoId`; `saveMemoBody` drops the row's draft on success **and** on failure so the field falls back to server truth; `setMemoActive` picks `activateMemo` / `deactivateMemo` by the requested flag. Every effect uses `runInAction` before and after each await, is abort-guarded, reseeds from the returned row, routes `ApiError` to `memosError` (load/create) or `actionStatus[id]`/`actionError[id]` (the four row writes), and rethrows anything else; `actionStatus` / `actionError` / `bodyDrafts` are always replaced as whole new objects. Two module-private helpers (`replaceMemo`, `dropDraft`) hold the two repeated one-liners. The skeleton's `stub(name, ...args): never` helper was **deleted** with the last body
- `frontend/src/work/components/memos/MemoRow.tsx` — the presentational `observer` row: `Textarea` (accessible name `<label> body`, `autosize`, `autoFocus` from the prop, `onFocus` → `onBodyFocus`, `onChange` → draft, **`onBlur`** → `onSaveBody` only when `body !== memo.body`), `Switch` (`<label> active`, `checked={memo.active}`, so OFF is reported as `aria-checked="false"`), an `Off` `Badge` while `!memo.active`, an archive **or** restore `ActionIcon` (`Archive memo N` / `Restore memo N`) rendered only when its handler is supplied, and a row `Alert` (`<label> error`) while `error !== null`. Every accessible name derives from `memoLabel(position)` with `position` the row's 1-based index in the list it is rendered in. No `useEffect`, no api import, no Save control, no delete control, no reorder affordance. Stub helper **deleted**
- `frontend/src/work/pages/MemosListPage.tsx` — step 009's placeholder body replaced (exported signature unchanged): the `Memos` heading, a `New memo` button, the `Show archived` switch written straight to `state.showArchived` in its change handler (pure client-side filter), the working list and — only while the toggle is on — an `Archived` section whose positions restart at 1, plus labelled loading / error (with a load-only Retry) / `No memos yet.` states. One shared `renderRow` wires both lists so they cannot drift; `onBodyChange` writes a whole new `bodyDrafts` object and `onBodyFocus` clears `focusMemoId`, both ordinary handlers. The skeleton's single page-level `useEffect` (subject register / load / unregister + abort) is unchanged; stub helper **deleted**

### Step 011 — reorder in the memos list: drag and arrows, one persist path
- `frontend/src/work/pages/memosListPageState.ts` — the fifth computed plus both reorder effects. `displayedWorkingMemos` resolves `pendingOrder` against `workingMemos` while a reorder is in flight (a row the sequence does not name keeps its ordinal place at the end) and returns `workingMemos` otherwise, so it can never contain an archived memo. `applyMemoOrder` is the **only** caller of `memosApi.reorderMemos`: it sets `pendingOrder` / `reorderStatus = "loading"` / `reorderError = null` before the await (a rendering optimism — `state.memos` is untouched), calls the api **once** with the whole `{ memo_ids }`, re-seeds by **merging** the returned working rows over their local twins (archived rows kept), and on `ApiError` sets `reorderError` (falling back to `"Could not reorder the memos."`) with `reorderStatus = "error"` and drops `pendingOrder` — the rollback, no refetch; a `finally` leaves `pendingOrder` `null` on every other exit path and anything that is not an `ApiError` rethrows. `moveMemo` computes the fully swapped id list out of `displayedWorkingMemos`, returns without a write when the memo is absent or already at that end, and **delegates** to `applyMemoOrder`. `runInAction` before and after each await, abort-guarded; no row state (`bodyDrafts` / `focusMemoId` / `actionStatus` / `actionError` / `showArchived`) is touched. The skeleton's `stub(name, ...args): never` helper was **deleted** with the last body
- `frontend/src/work/components/memos/MemoOrderList.tsx` — the drag surface and the arrow controls, copied from `components/chapters/ChapterOrderList.tsx`: `DndContext collisionDetection={closestCenter} onDragEnd={handleDragEnd}` wrapping `SortableContext items={memoIds} strategy={verticalListSortingStrategy}`, with a module-private `observer` `SortableMemoRow` calling `@dnd-kit`'s own `useSortable({ id: memo.id, disabled: reordering })`. Each row renders the drag handle (`Drag memo N to reorder`), the up control (`Move memo N up`, disabled when `reordering || position === 1`) and the down control (`Move memo N down`, disabled when `reordering || position === total`), then the page's row through `renderMemo(memo, position)`; every name is built from step 010's `memoLabel(position)` — one convention per row. `handleDragEnd` ignores a drop with no `over`, onto itself or naming an unknown id, and otherwise calls `onReorder(arrayMove(memoIds, from, to))`: `onReorder` is the module's **only** api-reaching path, the arrows reach the same `PUT` through `onMove` → `moveMemo` → `applyMemoOrder`. Presentational — no state class, no `bookId`, no api import, no `useState` / `useEffect` / `useCallback` / `useMemo`; nothing archived appears here. Stub helper **deleted**
- `frontend/src/work/pages/MemosListPage.tsx` — the three additions the skeleton's docstring fixed, exported signature and step-010 render otherwise unchanged: the working list now renders through `<MemoOrderList memos={state.displayedWorkingMemos} reordering={state.reorderStatus === "loading"} renderMemo={(memo, position) => renderRow(memo, position - 1, false)} onReorder={…applyMemoOrder…} onMove={…moveMemo…} />` inside the same `state.isEmpty` branch, so `renderRow` stays THE one row wiring; a list-level reorder `Alert` rendered only when `state.reorderError !== null` — named by `aria-label` `Reorder error` with **no** `title` prop (`MemoRow`'s shape: Mantine wires `aria-labelledby` to a `title` headline and that wins the accessible-name computation, so the two mechanisms together left the surface unreachable under its contracted name), the headline `Could not reorder the memos` and `state.reorderError` rendered as the alert's own text, never sharing a holder with `memosError` or a row's `actionError`; and nothing else — the archived section keeps its plain `state.archivedMemos.map(...)` rendering with no drag handle, no arrows and no path by which its ids could reach a persist call

## Skeleton

### Step 001 — frozen interface (2026-09-15)

**`backend/app/models/memo.py`** — new module. Declarative table, written in full
(field declarations *are* the signature); no unimplemented body.

- `backend/app/models/memo.py` — `class Memo(SQLModel, table=True)`, `__tablename__ = "memos"`, **no `__table_args__`** — new
  - `id: int = Field(default_factory=generate_id, primary_key=True)`
  - `book_id: int = Field(foreign_key="books.id")`
  - `user_id: int = Field(foreign_key="users.id")`
  - `body: str`
  - `ordinal: int`
  - `active: bool = Field(default=True)`
  - `archived: bool = Field(default=False)`
  - `created_at: datetime | None = Field(default=None)`
  - `modified_at: datetime | None = Field(default=None)`

**`backend/app/db/memos.py`** — new module, four functions, no `delete`. Bodies
`raise NotImplementedError`.

- `backend/app/db/memos.py` — `async def create(row: Memo) -> Memo` — new
- `backend/app/db/memos.py` — `async def get_by_id(memo_id: int) -> Memo | None` — new
- `backend/app/db/memos.py` — `async def list_for_author(book_id: int, user_id: int, include_archived: bool = False) -> list[Memo]` — new
- `backend/app/db/memos.py` — `async def update(row: Memo) -> Memo` — new

**`backend/app/db/engine.py`** — registration only.

- `backend/app/db/engine.py` — `_register_models()` gains `import app.models.memo  # noqa: F401` as the last line of the MODEL-REGISTRATION SEAM — changed (import list only; `ADDITIVE_COLUMNS` and the ADDITIVE MIGRATION SEAM untouched)

**`backend/app/services/db_import_export.py`** — codec pair + one registry entry.
Codec bodies `raise NotImplementedError`.

- `backend/app/services/db_import_export.py` — `def _memo_to_dict(memo: Memo) -> dict[str, object]` — new
- `backend/app/services/db_import_export.py` — `def _dict_to_memo(data: dict[str, object]) -> Memo` — new
- `backend/app/services/db_import_export.py` — `TABLE_REGISTRY` gains `("memos", Memo, _memo_to_dict, _dict_to_memo)` at **index 11** (immediately after the `chapter_author_prompts` tuple, immediately before `("chapters", Chapter, …)`) — changed. Module-level `from app.models.memo import Memo` added.

Frozen export key set for the codec pair: `{"id", "book_id", "user_id", "body",
"ordinal", "active", "archived", "created_at", "modified_at"}` — ids emitted as
`str(...)` and parsed string-or-legacy-number; timestamps `.isoformat()` /
`datetime.fromisoformat`, both nullable.

- Caller-compile edits (out of Source-files scope): None. Nothing in `backend/app/` referenced any of these symbols before this step.

Verification: `cd backend && .venv/Scripts/python -c "import app.main"` clean;
`TABLE_REGISTRY` label list is 21 entries with exactly one `memos` at index 11,
between `chapter_author_prompts` and `chapters`. (Backend has no separate
typecheck — import is the gate.)

### Step 002 — frozen interface (2026-09-15)

**`backend/app/models/schemas/memos.py`** — new module. Declarative Pydantic
DTOs, written in full (field declarations *are* the signature); no unimplemented
body. **No reorder request DTO** — that is step 004's, added to this module when
it has a caller.

- `backend/app/models/schemas/memos.py` — `class CreateMemoRequest(BaseModel)` — new
  - `body: str` — no constraint of any kind (`""` is legitimate input, never a 422)
- `backend/app/models/schemas/memos.py` — `class UpdateMemoRequest(BaseModel)` — new
  - `body: str` — and nothing else: no `expected_modified_at`, no `active` / `archived` flags
- `backend/app/models/schemas/memos.py` — `class MemoResponse(BaseModel)` — new
  - `id: str`
  - `book_id: str`
  - `body: str`
  - `ordinal: int`
  - `active: bool`
  - `archived: bool`
  - `created_at: UtcDateTime | None`
  - `modified_at: UtcDateTime | None`
  - **no `user_id` field** — the subject is always the caller (`context.md` → "The wire contract")
- `backend/app/models/schemas/memos.py` — `class MemoListResponse(BaseModel)` — new
  - `items: list[MemoResponse]`

`UtcDateTime` is `app.models.schemas.common.UtcDateTime` (the `CodexEntryResponse`
timestamp precedent); both stamps are nullable because the `Memo` columns are.

**`backend/app/services/memos.py`** — new module. Eight frozen symbols; every
function body `raise NotImplementedError("026 step 002 — skeleton stub")`.

- `backend/app/services/memos.py` — `class MemoErrorReason(str, enum.Enum)` with exactly two members — new
  - `not_a_member = "not-a-member"`
  - `not_found = "not-found"` (one reason for all four sources; step 004 adds the third member)
- `backend/app/services/memos.py` — `class MemoError(Exception)` — new
  - `def __init__(self, reason: MemoErrorReason, message: str = "") -> None` — sets `self.reason` / `self.message`
- `backend/app/services/memos.py` — `def _require_member(access: authz.BookAccess) -> None` — new
- `backend/app/services/memos.py` — `def _to_memo_response(row: Memo) -> MemoResponse` — new
- `backend/app/services/memos.py` — `async def _resolve_memo(access: authz.BookAccess, memo_id: str) -> Memo` — new
- `backend/app/services/memos.py` — `async def list_memos(access: authz.BookAccess, include_archived: bool = False) -> MemoListResponse` — new
- `backend/app/services/memos.py` — `async def create_memo(access: authz.BookAccess, req: CreateMemoRequest) -> MemoResponse` — new
- `backend/app/services/memos.py` — `async def update_memo_body(access: authz.BookAccess, memo_id: str, req: UpdateMemoRequest) -> MemoResponse` — new

Frozen properties beyond the signatures:

- **`BookAccess` is the first parameter of every entry point**, and no entry
  point takes a user id or a book id as a separate parameter — the scoping is
  structural (`context.md` → decision 3).
- The wire `memo_id` is a **`str`** and is parsed inside `_resolve_memo`, not in
  the route: a non-numeric id is `not_found`, never FastAPI's `422`.
- The create/update entry points take the **request DTO**, not a bare string
  (the `codex_service.create_entry(access, CreateCodexEntryRequest(...))`
  precedent) — step 008's tool constructs a `CreateMemoRequest` the same way.
- No `authz.require`, no `Capability`, no `_CAPABILITY_MATRIX` row; module
  imports are `enum`, `from app.db import memos`, `app.models.memo.Memo`, the
  four DTOs, and `from app.services import authz`. **No `session` /
  `AsyncSession` / `select()` / `session.exec()` / `session.add()`** appears in
  the module (the only textual match is the layer-rule sentence in the
  docstring, copied from `services/book_author_prompts.py`).
- `BookAccess.book_state` and `BookAccess.collaboration_mode` are **not read**.
- No private `_next_ordinal` helper is frozen: the append rule is stated as
  `create_memo`'s contract, and factoring it into a private helper is the
  coder's call (step 005's restore reuses whatever this step's implementation
  lands, per `005.memo-state-axes.md`).

- Caller-compile edits (out of Source-files scope): None. Nothing in `backend/app/` referenced either module before this step; `backend/app/main.py` is untouched (the router is step 003's).

Verification: `cd backend && .venv/Scripts/python -c "import app.main"` clean,
and the eight service signatures plus the four DTO field lists were re-read back
through `inspect.signature` / `model_fields`. (Backend has no separate
typecheck — import is the gate.)

### Step 003 — frozen interface (2026-09-15)

**`backend/app/routes/memos.py`** — new module. Router, reason → status map, one
mapping helper and three handlers. The helper and all three handler bodies
`raise NotImplementedError("026 step 003 — skeleton stub")`.

- `backend/app/routes/memos.py` — `router = APIRouter(prefix="/api/books", tags=["memos"])` — new
- `backend/app/routes/memos.py` — `_MEMO_ERROR_STATUS: dict[memos_service.MemoErrorReason, int]` — new
  - `MemoErrorReason.not_a_member: status.HTTP_403_FORBIDDEN`
  - `MemoErrorReason.not_found: status.HTTP_404_NOT_FOUND`
  - exactly **two** entries at this step; step 004 adds the third (invalid reorder set → 400)
- `backend/app/routes/memos.py` — `def _map_memo_error(err: memos_service.MemoError) -> HTTPException` — new
- `backend/app/routes/memos.py` — `@router.get("/{book_id}/memos")` →
  `async def list_memos(include_archived: bool = False, access: authz.BookAccess = Depends(authz.book_access)) -> MemoListResponse` — new
- `backend/app/routes/memos.py` — `@router.post("/{book_id}/memos", status_code=status.HTTP_201_CREATED)` →
  `async def create_memo(payload: CreateMemoRequest, access: authz.BookAccess = Depends(authz.book_access)) -> MemoResponse` — new
- `backend/app/routes/memos.py` — `@router.put("/{book_id}/memos/{memo_id}")` →
  `async def update_memo_body(memo_id: str, payload: UpdateMemoRequest, access: authz.BookAccess = Depends(authz.book_access)) -> MemoResponse` — new

Frozen properties beyond the signatures:

- **Declaration order is load-bearing and frozen**: the `/{memo_id}` `PUT` is the
  **last** route in the module, and a comment above it marks the insertion point
  where step 004's `PUT /{book_id}/memos/order` goes — FastAPI matches in
  declaration order, so a literal `order` segment declared after `/{memo_id}`
  would be swallowed as a memo id (the `routes/chapters.py` comment convention).
  Step 005's four `/{memo_id}/<verb>` routes belong beside the last route.
- **No handler declares `book_id`** — `Depends(authz.book_access)` consumes the
  path param entirely; `book_id` still appears in OpenAPI as a path parameter,
  contributed by the dependency.
- **Response models are the return annotations**, never `response_model=`.
- `memo_id` is typed **`str`** and is passed to the service **verbatim**; the
  route performs no parsing, so a non-numeric id is the service's `not_found`
  → 404, never FastAPI's 422.
- `include_archived` is a **query** parameter, `bool`, **default `False`**, not
  required (the `routes/codex.py` list precedent).
- **No `authz.require`, no `Capability`, no `_map_authz_error`**, and **no
  archived-book refusal** (the named carve-out — unlike `routes/chapters.py`).
- **`401` and the private-book `404` are never re-derived here** — both come from
  the dependency. The only statuses this module produces are 403 and 404 (from
  the map), 200 and 201 (from the annotations / `status_code=`).
- **No `DELETE`** on any memo path; the framework's own 405 is the answer.
- Module imports are `fastapi` (`APIRouter`, `Depends`, `HTTPException`,
  `status`), the four DTOs from `app.models.schemas.memos`,
  `from app.services import authz` and `from app.services import memos as
  memos_service`. No `db` import, no `session` / `select()`.

**`backend/app/main.py`** — registration only, and **real, not stubbed**.

- `backend/app/main.py` — `from app.routes import memos` added to the route import
  block (alphabetical, between `health` and `reader`) — changed
- `backend/app/main.py` — `app.include_router(memos.router)` added after
  `app.include_router(chapter_author_prompts.router)`, beside the other
  book-scoped routers — changed. Include order is not load-bearing against the
  other `/api/books` routers: every memo path carries the literal `memos`
  segment.

- Caller-compile edits (out of Source-files scope): None. Nothing referenced
  `app.routes.memos` before this step.

Verification: `cd backend && .venv/Scripts/python -c "import app.main"` clean; the
live app's OpenAPI carries `/api/books/{book_id}/memos` with `get` + `post` (POST
declaring **201**) and `/api/books/{book_id}/memos/{memo_id}` with `put` (200),
`include_archived` present as an optional query param defaulting to `false`, and
the router's own declaration order ending with the `/{memo_id}` route. (Backend
has no separate typecheck — import is the gate.)

### Step 004 — frozen interface (2026-09-15)

Three existing modules, one addition each. Everything declarative is written in
full; the two added bodies `raise NotImplementedError("026 step 004 — skeleton stub")`.

**`backend/app/models/schemas/memos.py`** — one added DTO, declarative.

- `backend/app/models/schemas/memos.py` — `class ReorderMemosRequest(BaseModel)` — new
  - `memo_ids: list[str]` — the **full** ordered id list of the caller's non-archived memos
  - **no ordinals and no partial-move shape**: positions are the server's to write (`1..N`), so "move memo X to position k" is not expressible on this wire
  - declared **between `UpdateMemoRequest` and `MemoResponse`** (requests before responses — the `schemas/chapters.py` layout)

**`backend/app/services/memos.py`** — one added enum member + one added entry point.

- `backend/app/services/memos.py` — `MemoErrorReason` gains a **third** member — changed (was exactly two)
  - `invalid_reorder_set = "invalid-reorder-set"` — deliberately **not** `not_found`: the caller is told their *set* is wrong, not that a resource is missing. The enum is now exactly `[not_a_member, not_found, invalid_reorder_set]`.
- `backend/app/services/memos.py` — `async def reorder_memos(access: authz.BookAccess, req: ReorderMemosRequest) -> MemoListResponse` — new
- `backend/app/services/memos.py` — module-level import list gains `ReorderMemosRequest` — changed (import only)

**`backend/app/routes/memos.py`** — one added handler + one added map entry.

- `backend/app/routes/memos.py` — `_MEMO_ERROR_STATUS` gains a **third** entry — changed (was exactly two)
  - `MemoErrorReason.invalid_reorder_set: status.HTTP_400_BAD_REQUEST` — **400, not 422**
- `backend/app/routes/memos.py` — `@router.put("/{book_id}/memos/order")` →
  `async def reorder_memos(payload: ReorderMemosRequest, access: authz.BookAccess = Depends(authz.book_access)) -> MemoListResponse` — new
- `backend/app/routes/memos.py` — module-level import list gains `ReorderMemosRequest` — changed (import only)

Frozen properties beyond the signatures:

- **Declaration order is frozen and load-bearing.** The `order` route is declared
  at step 003's insertion point — after `POST /{book_id}/memos`, **before**
  `PUT /{book_id}/memos/{memo_id}`, which remains the **last** route in the
  module. The insertion-point comment was replaced by a permanent
  ordering-is-load-bearing comment in `routes/chapters.py`'s convention. Verified
  live: `router.routes` is `GET /memos`, `POST /memos`, `PUT /memos/order`,
  `PUT /memos/{memo_id}`.
- **No `authz.require`, no `Capability`, no `_CAPABILITY_MATRIX` row** — the one
  deliberate difference from `services/chapters.py::reorder_chapters`, which is
  owner-only via `Capability.set_chapter_order`. Memo order is the author's own:
  membership (`_require_member`) plus `access.user_id` scoping is the whole rule
  (`004.context.md` → "The one difference from the chapters precedent").
- **No bulk `db/` writer was added.** `db/memos.py` is untouched by this step; the
  `1..N` rewrite loops the ordinary per-row `db.memos.update`, keeping the rule in
  the service (`004.context.md`).
- The entry point takes the **request DTO**, not a bare `list[str]` — the
  `reorder_chapters(access, request)` precedent and step 002's frozen convention
  that every memo entry point takes `(access, …DTO)`.
- `BookAccess` remains the first parameter and no user id or book id is a separate
  parameter; `book_state` and `collaboration_mode` stay unread (the archived-book
  carve-out holds for reorder too).
- The handler declares **no `book_id`** (the dependency consumes it), the response
  model is the **return annotation**, and `400` joins `403` / `404` / `200` as the
  only statuses this module produces.

- Caller-compile edits (out of Source-files scope): **None** in `backend/app/`. One
  *existing test* now fails on the widened enum — see `## Notes & Issues` → "Step
  004 skeleton"; the skeleton agent may not edit test files, so it was left alone.

Verification: `cd backend && .venv/Scripts/python -c "import app.main"` clean; the
live app's `app.openapi()["paths"]` carries `/api/books/{book_id}/memos/order`
(`put`, 200 → `MemoListResponse`, `book_id` as its only path parameter) as a path
**distinct from** `/api/books/{book_id}/memos/{memo_id}` (`put`), so the literal
segment is not captured as a memo id; `MemoErrorReason` reads
`['not-a-member', 'not-found', 'invalid-reorder-set']` and `_MEMO_ERROR_STATUS`
reads `{403, 404, 400}` respectively. (Backend has no separate typecheck — import
is the gate.) `tests/routes/test_memos.py` and `tests/services/test_memos.py`:
44 passed, 1 failed — the single hard-coded-enum spec noted below.

### Step 005 — frozen interface (2026-09-15)

Two existing modules, four additions each. Everything declarative is written in
full; all eight added bodies `raise NotImplementedError("026 step 005 — skeleton stub")`.
**No schema module is touched** — all four verbs take no body and return the
existing `MemoResponse`.

**`backend/app/services/memos.py`** — four added entry points, no other change.

- `backend/app/services/memos.py` — `async def activate_memo(access: authz.BookAccess, memo_id: str) -> MemoResponse` — new
- `backend/app/services/memos.py` — `async def deactivate_memo(access: authz.BookAccess, memo_id: str) -> MemoResponse` — new
- `backend/app/services/memos.py` — `async def archive_memo(access: authz.BookAccess, memo_id: str) -> MemoResponse` — new
- `backend/app/services/memos.py` — `async def restore_memo(access: authz.BookAccess, memo_id: str) -> MemoResponse` — new
- Declared in that order, **after** `reorder_memos` (last in the module). No import
  change, no new helper, no new exception type.

**`backend/app/routes/memos.py`** — four added handlers, no other change.

- `backend/app/routes/memos.py` — `@router.post("/{book_id}/memos/{memo_id}/activate")` →
  `async def activate_memo(memo_id: str, access: authz.BookAccess = Depends(authz.book_access)) -> MemoResponse` — new
- `backend/app/routes/memos.py` — `@router.post("/{book_id}/memos/{memo_id}/deactivate")` →
  `async def deactivate_memo(memo_id: str, access: authz.BookAccess = Depends(authz.book_access)) -> MemoResponse` — new
- `backend/app/routes/memos.py` — `@router.post("/{book_id}/memos/{memo_id}/archive")` →
  `async def archive_memo(memo_id: str, access: authz.BookAccess = Depends(authz.book_access)) -> MemoResponse` — new
- `backend/app/routes/memos.py` — `@router.post("/{book_id}/memos/{memo_id}/restore")` →
  `async def restore_memo(memo_id: str, access: authz.BookAccess = Depends(authz.book_access)) -> MemoResponse` — new
- No `status_code=` on any of the four — the default **200** is the contract.

Frozen properties beyond the signatures:

- **`MemoErrorReason` is UNCHANGED at exactly three members**
  (`not_a_member` / `not_found` / `invalid_reorder_set`), and `_MEMO_ERROR_STATUS`
  is UNCHANGED at exactly three entries (403 / 404 / 400). This step adds **no
  reason, no map entry and no status**: every refusal these four verbs can produce
  already exists. In particular there is **no `409`** — a verb applied to a memo
  already in the requested state is a **200 no-op** returning the row unchanged
  (`context.md` → "Planner-derived: repeat state calls are 200 no-ops"). This
  deliberately does **not** copy `POST /api/books/{book_id}/archive`'s 409.
- **No request body on any of the four.** Verified live: the OpenAPI operation for
  each carries no `requestBody`, its only parameters are the two path params
  (`memo_id` plus the `book_id` the dependency declares), and its 200 content is
  `$ref: MemoResponse`.
- **`memo_id` is the wire `str`, passed through unparsed** — the route does not
  `int()` it, so a non-numeric id is the service's `not_found` → 404, never
  FastAPI's 422. Frozen from step 003.
- **The four service entry points take `(access, memo_id)` and nothing else** — no
  user id, no book id, no DTO, no flag argument. A flag parameter would make one
  function write both axes and re-open the enum-vs-two-booleans decision; the
  four-verb shape is the contract (`SubAgent`'s `disable` / `enable` precedent).
- **Every one resolves through the existing module-private `_resolve_memo`**, so
  the single `404`-shaped refusal (unknown / non-numeric / another author's /
  another book's) covers all four identically — US-124.AC-1 stays structural. No
  second resolver was added.
- **Restore reuses step 002's `_next_ordinal`** — the single append rule. No second
  next-ordinal computation exists anywhere.
- **No `DELETE` route, at any path**, and no delete function in `db/memos.py`.
  Verified live: no `/memos` path in the OpenAPI document carries a `delete`
  operation.
- **`book_state` and `collaboration_mode` stay unread** in the service — the
  archived-book carve-out holds for all four verbs.
- **Declaration order.** The four are declared **after** `PUT …/memos/order` and
  **immediately above** `PUT …/memos/{memo_id}`, which remains the **last** route in
  the module (step 004's frozen ordering property is preserved). Their extra path
  segment means they cannot collide with it either way.
- **`db/memos.py` is untouched** by this step: the flag writes go through the
  existing per-row `db.memos.update`.

Module-docstring corrections made with this step's additions (all three were false
statements, not scope creep):

- `backend/app/services/memos.py` — the skeleton marker said `reorder_memos` is
  UNIMPLEMENTED; it is implemented. Now names steps 002/004 as implemented and this
  step's four entry points as the unimplemented ones.
- `backend/app/routes/memos.py` — same correction for step 004's `reorder_memos`
  handler.
- `backend/app/routes/memos.py` — "**Only two statuses are this module's to
  produce**" followed by three (403 / 404 / 400) → "three", and the matching "the
  service's two typed reasons" → "three". The substantive rules those docstrings
  record (the archived-book carve-out, the no-capability rule, the append rule, the
  ordering rule, the one-refusal rule) are untouched.

- Caller-compile edits (out of Source-files scope): **None.** This step is purely
  additive — no existing signature changed, so no call site moved, and no
  previously-green test went red.

Verification: `cd backend && .venv/Scripts/python -c "import app.main"` clean. The
live app's `app.openapi()["paths"]` carries all four new verb paths as distinct
entries — `/api/books/{book_id}/memos/{memo_id}/activate`, `/deactivate`,
`/archive`, `/restore`, each `post` → 200 `MemoResponse`, each with no
`requestBody` — alongside `/api/books/{book_id}/memos` (`get`, `post`),
`/api/books/{book_id}/memos/order` (`put`) and `/api/books/{book_id}/memos/{memo_id}`
(`put`), which still resolve distinctly; no `/memos` path has a `delete`.
`MemoErrorReason` still reads `['not-a-member', 'not-found', 'invalid-reorder-set']`
and `_MEMO_ERROR_STATUS` still reads `{403, 404, 400}`. (Backend has no separate
typecheck — import is the gate.) The five existing memo suites
(`tests/db/test_memos.py`, `tests/services/test_memos.py`,
`tests/services/test_memos_order.py`, `tests/routes/test_memos.py`,
`tests/routes/test_memos_order.py`): **86 passed**, 0 failed.

### Step 006 — frozen interface (2026-09-15)

**`backend/app/services/prompt_composition.py`** — one added parameter, nothing
else. The module stays pure: no session, no clock, no knowledge of what a memo is.

- `backend/app/services/prompt_composition.py` — `def compose_system_prompt(base: str | None = None, mode: str | None = None, author: str | None = None, memos: str | None = None, chapter: str | None = None) -> str` — changed (was `compose_system_prompt(base: str | None = None, mode: str | None = None, author: str | None = None, chapter: str | None = None) -> str`)

Frozen properties beyond the signature:

- **`author` is still the third positional parameter** and `base` / `mode` keep
  positions 1 and 2 — DoD-5's property is preserved, not broken. `memos` is
  **fourth**, `chapter` moves to **fifth**.
- **No compatibility alias of any kind** — not for the new parameter, not for the
  moved one; the module docstring's "deliberately no alias" statement survives and
  now covers 026 as well as 021.
- The docstring is updated to describe **five** layers with memos fourth, and
  states that the composer receives an **already-rendered string** and never a
  list of memos (step file → Interface intent).
- The section **label** `MEMOS` and its rendered position are **behaviour, not
  signature** — left to the coder, exactly as 021 step 004 left the `AUTHOR`
  label. Labels stay inline literals; no label constant was introduced.
- **Stub shape:** the four pre-existing layers keep their behaviour unchanged; a
  non-blank `memos` argument raises `NotImplementedError("026 step 006 — skeleton
  stub: the MEMOS layer is not composed yet")`. A blank or absent `memos` takes
  the existing path, so every call that predates this feature still composes
  exactly as before.

**`backend/app/services/chat_turn.py`** — one new pure function, one new frozen
record, one changed return type.

- `backend/app/services/chat_turn.py` — `def render_memos_section(memos: Sequence[Memo]) -> str | None` — new (body `raise NotImplementedError`)
- `backend/app/services/chat_turn.py` — `@dataclass(frozen=True) class ComposedTurnPrompt` — new
  - `system: str`
  - `memos_section: str | None`
- `backend/app/services/chat_turn.py` — `async def compose_turn_system_prompt(context: TurnContext) -> ComposedTurnPrompt` — changed (was `async def compose_turn_system_prompt(context: TurnContext) -> str`)

Frozen properties beyond the signatures:

- **`render_memos_section` is module-level, synchronous and pure** — no db read,
  no session, no clock. It renders the rows **in the order given** and never
  sorts, ranks, truncates or budgets (`context.md` → decision 8).
- **The caller supplies the already-filtered working list.** The `active` filter
  and the archived exclusion live in `compose_turn_system_prompt`, *not* in the
  renderer: the renderer's only skip rule is **a body that is blank after
  stripping** (UC-103's empty memo must not leave a stray separator). A
  test binding to this function must pass the rows it wants rendered.
- **`None` is the no-layer value** — returned for an empty sequence and for a
  sequence whose every body is blank. `compose_system_prompt`'s
  empty-contributes-nothing rule does the rest; the renderer never emits a
  header, a separator or a blank block of its own.
- The **separator between two memo bodies** is behaviour, not signature — the
  coder's call; the only fixed requirement is that two memos cannot read as one.
- **The db import is `from app.db import memos as memos_db`** in `chat_turn.py`
  (the file's own `llm_servers as llm_servers_db` precedent, and it keeps the
  module from being shadowed by `render_memos_section`'s `memos` parameter). The
  frozen read is `memos_db.list_for_author(chat.book_id, chat.author_id)` —
  step 001's signature, archived excluded by its default — called **directly**,
  with **no `BookAccess` built** and **unconditional on the subject**, beside the
  three reads the mode / author / chapter layers already do. Monkeypatching
  either `app.db.memos.list_for_author` or `chat_turn.memos_db.list_for_author`
  reaches the same module object.

**Why the return type changed — the decision step 007 binds to.** Step 007 needs
the *same* rendered section on
`subagent_delegation.ParentTurn`, and `context.md` → decision 7 forbids a second
read ("rendered exactly once per turn and passed to **both** the composer and
delegation"). The section is produced inside `compose_turn_system_prompt`, so the
only shapes that keep it reachable from `run_turn` without re-reading are (a)
returning it beside the prompt, or (b) splitting the read into its own function
that `run_turn` calls and then threads *into* the composition. (b) was rejected:
it moves the memos read out of the composer that the step file explicitly puts it
in ("the turn reads the memos itself", inside the composition path), and it makes
a future caller able to compose a turn prompt with no memos at all. (a) is frozen:
`compose_turn_system_prompt` returns a frozen `ComposedTurnPrompt` typed record —
the codebase's `TurnContext` / `TurnFrame` / `ParentTurn` shape, not a tuple and
not a dict. `run_turn`'s own signature is unchanged; it now binds `composed`,
`system` and `memos_section` locals, the last of which is what step 007 hands to
`ParentTurn`.

- Caller-compile edits (out of Source-files scope): **None.** The only caller of
  `compose_turn_system_prompt` in `backend/app/` is `run_turn`, in the same file
  (Source-files scope). Every in-app call of `compose_system_prompt` is
  keyword-only, so the inserted fourth parameter moves no argument.

**For the red gate — what the stub does and does not exercise.** The turn half
renders **nothing**: `compose_turn_system_prompt` performs **zero** memos reads and
passes `memos=None`, marked in-place as the coder's slot. Consequently DoD-1, -2,
-4, -7, -8 and -9 fail against the skeleton (DoD-9's read count is 0, not 1), while
DoD-3 and DoD-6 — both *negative* assertions that nothing is contributed — pass
trivially, as any negative assertion must against an unimplemented layer. A pure
composer test that passes a non-blank `memos=` errors with `NotImplementedError`
rather than silently composing a four-layer prompt.

Verification: `cd backend && .venv/Scripts/python -c "import app.main"` clean;
`inspect.signature` read back all three frozen signatures and
`dataclasses.fields(ComposedTurnPrompt)` reads `[('system', str), ('memos_section',
str | None)]` with `frozen=True`;
`compose_system_prompt(base=…, author=…, chapter=…)` still renders `### BASE` /
`### AUTHOR` / `### CHAPTER` unchanged. (Backend has no separate typecheck — import
is the gate. Tests are the verifier's to run.)

### Step 007 — frozen interface (2026-09-15)

Three existing modules. `ParentTurn` gains **one** field, `_delegate`'s nested
`system` becomes a composed value through one new module-private function, and
the other two files are pass-through wiring. Exactly one body is a stub.

**`backend/app/services/subagent_delegation.py`** — one added field, one added
private function, one added constant, one changed call site.

- `backend/app/services/subagent_delegation.py` — `@dataclass(frozen=True) class ParentTurn` — changed (was `ParentTurn(server, resolved_key, model, tool_context=None)`)
  - `server: LlmServer`
  - `resolved_key: str | None`
  - `model: str`
  - `tool_context: ToolContext | None = None`
  - `memos_section: str | None = None` — **new; declared last and defaulted**, so every existing `ParentTurn(server=…, resolved_key=…, model=…[, tool_context=…])` construction keeps binding with its current meaning (no section ⇒ the sub-agent's own prompt alone, exactly as before). It is the same optional string step 006 renders — `ComposedTurnPrompt.memos_section`.
- `backend/app/services/subagent_delegation.py` — `def _compose_delegated_system(sub_agent_prompt: str, memos_section: str | None) -> str` — new (module-private, **synchronous**, pure: no db read, no session, no clock)
- `backend/app/services/subagent_delegation.py` — `_DELEGATED_SECTION_JOIN = "\n\n"` — new module-level constant (the composer's own blank-line section join)
- `backend/app/services/subagent_delegation.py` — `_delegate`'s nested `system=` argument is now `system=_compose_delegated_system(sub_agent.system_prompt, parent.memos_section)` — changed (was `system=sub_agent.system_prompt`)
- Module imports gain `from app.services import prompt_composition`. **No memo import of any kind** is added — not the `db/` memos module, not `chat_turn`.
- **Unchanged signatures:** `delegation_tool_name`, `build_delegation_tools(mode_key, parent)`, `run_delegation(sub_agent, parent, task)`, `_delegate(sub_agent, parent, task)`, `_subagent_tools`, `_resolve_model`, `DelegationArgs`, `SUBAGENT_MAX_LOOPS`, `DELEGATION_TOOL_PREFIX`.

**The composition shape — the resolution both the test-coder and the coder bind
to.** The step file says compose through step 006's composer and forbids
hand-assembling a second rendering (`007.context.md` → "compose, do not
concatenate"), while DoD-4 requires that with **no** active memos the nested
system is the sub-agent's prompt *alone*, unchanged. Those pull against each
other, because `compose_system_prompt` gives **every** surviving layer its
`### LABEL` header: passing the sub-agent's prompt as the `base` layer would
render `### BASE` + the prompt, which is not "its own prompt alone" — and would
put a base-labelled layer into a nested call DoD-2 says carries none.
**Frozen resolution:** `_compose_delegated_system` calls the composer with the
**memos layer alone and no other layer** — `compose_system_prompt(memos=memos_section)` —
and joins that result to the sub-agent's own prompt:

| `memos_section` | result |
|---|---|
| `None`, or blank after stripping | `sub_agent_prompt` **verbatim** — not stripped, not re-wrapped, no header, no separator: byte-identical to the pre-026 nested system (DoD-4) |
| non-blank | `sub_agent_prompt` + `_DELEGATED_SECTION_JOIN` + `compose_system_prompt(memos=memos_section)` — the sub-agent's prompt, a blank line, then the composer's own `### MEMOS` section (DoD-1, DoD-3) |

Why this satisfies every clause: the composer still owns the `MEMOS` **label**,
the **strip** and the **empty-layer skip rule**, so nothing about the section's
rendering is hand-rolled and the child's section cannot drift from the parent's
(the gotcha); the composer's empty-string return for a blank layer is what makes
the no-memos path byte-identical to today (DoD-4); and no `base` / `mode` /
`author` / `chapter` argument is ever passed, so no other layer can thread
through (DoD-2). The single blank-line join is the **only** byte this module
chooses about the section, and it is the composer's own section join, so the
run-up to `### MEMOS` reads in the child exactly as it does in the parent.

Frozen properties beyond the signatures:

- **The module performs no memos read of its own** (DoD-5): it imports no memo
  module and calls no memo function; the section arrives on `ParentTurn` or not
  at all. The reasoning is recorded in the **module docstring** — one DB read
  per turn, and (the load-bearing half) parent and every sub-agent are
  guaranteed an **identical** set even if `create_memo` adds one mid-turn — and
  restated on the `memos_section` field and in `_compose_delegated_system`'s
  docstring.
- **Token note for a DoD-5 spec:** the module source deliberately contains **no**
  occurrence of the strings `app.db.memos` or `render_memos_section` — the
  prohibition prose is worded around them ("the `db/` data-access module for
  that table", "`chat_turn.py`'s section renderer") precisely so a textual
  assertion cannot false-positive on the docstring. The identifier
  `memos_section` does of course appear (it is the carried field), so a spec
  must key on those module/function tokens, on the module's imports, or on a
  monkeypatched `db/memos.list_for_author` spy counting **one** call per turn —
  never on the bare substring `memos`.
- **Everything else is untouched:** the synthetic-tool derivation and its
  collision guard, the sub-agent's own `subagent_tool` allowlist, its own model
  resolution (`_resolve_model`), its own `SUBAGENT_MAX_LOOPS`, the one-client
  `async with`, and the rule that **every** delegation failure comes back to the
  parent as a short error string rather than raising — `run_delegation`'s broad
  `except` is unchanged (DoD-7).

**`backend/app/services/chat_turn.py`** — wiring only, **real, not stubbed**: no
signature change, no new read, no re-render.

- `backend/app/services/chat_turn.py` — `run_turn`'s `subagent_delegation.ParentTurn(...)` construction gains `memos_section=memos_section` — changed. `memos_section` is the local step 006 already binds from `composed.memos_section`; nothing is read or rendered a second time.

**`backend/app/services/assistant_runtime.py`** — pass-through only.

- `backend/app/services/assistant_runtime.py` — `async def resolve_turn_tools(mode_key: str | None, parent: subagent_delegation.ParentTurn) -> list[ToolDef]` — **unchanged signature**; its docstring now states that `parent` also carries the turn's already-rendered `MEMOS` section and that this function merely passes it through. Mode determination, `allowed_tool_names`, the resolution rules and `BASE_TOOL_NAMES` (step 008's) are untouched.

**For the red gate — what the stub does and does not exercise.**
`_compose_delegated_system` **preserves** the pre-026 behaviour and leaves only
the new path unimplemented: a `None`/blank `memos_section` returns
`sub_agent_prompt` verbatim, and a **non-blank** one raises
`NotImplementedError("026 step 007 — skeleton stub: the carried MEMOS section is
not composed into the delegated prompt yet")`, marked in place as the coder's
slot. Consequently DoD-1, -3 and -6 fail against the skeleton for the right
reason — with a section present, `_delegate` raises before `chat_with_tools` is
reached, so the mocked client records **no** nested call and every assertion on
its `system` argument fails — while `run_delegation`'s broad `except` still turns
that into the short error string, which is exactly why DoD-7's section-present
half is green and is not a trivially-passing negative. DoD-2, DoD-4 and DoD-5 —
the three clauses this step must *preserve* rather than add — pass against the
skeleton, as preserved-behaviour clauses must.

- Caller-compile edits (out of Source-files scope): **None.** The only
  `ParentTurn` construction in `backend/app/` is `run_turn`'s, inside this step's
  Source files, and the new field is defaulted and declared last, so
  `backend/tests/services/test_subagent_delegation.py`'s
  `ParentTurn(server=…, resolved_key=…, model=…)` helper keeps binding unchanged.
  `resolve_turn_tools` and `build_delegation_tools` keep their signatures, so no
  call site moved.

Verification: `cd backend && .venv/Scripts/python -c "import app.main"` clean;
`dataclasses.fields(ParentTurn)` reads
`[server, resolved_key, model, tool_context=None, memos_section: str | None = None]`
with `frozen=True`; `inspect.signature(_compose_delegated_system)` reads
`(sub_agent_prompt: str, memos_section: str | None) -> str`;
`_compose_delegated_system("P", None)` and `_compose_delegated_system("P", "   ")`
both return `"P"`, and a non-blank section raises `NotImplementedError`. (Backend
has no separate typecheck — import is the gate. Tests are the verifier's to run.)

### Step 008 — frozen interface (2026-09-15)

**`backend/app/services/memo_tools.py`** — new module, the `chapter_tools.py`
three-shape template: one args schema (declarative, written in full), one
callable (body `raise NotImplementedError("026 step 008 — skeleton stub")`), one
one-line binder.

- `backend/app/services/memo_tools.py` — `class CreateMemoArgs(BaseModel)` — new
  - `body: str = Field(description=...)` — **required, no default**; the single field, so the bound callable has exactly one free parameter. No subject field, no id field, no book field (`quick-reference.md` names this schema `CreateMemoArgs(body: str)`)
- `backend/app/services/memo_tools.py` — `async def create_memo(context: "ToolContext", body: str) -> str` — new
- `backend/app/services/memo_tools.py` — `def bind_create_memo(context: "ToolContext") -> Callable[..., object]` — new — `return functools.partial(create_memo, context)`

Private refusal/confirmation constants declared for the coder to return (wording
is the coder's to keep or adjust; **no test may bind to it**):
`_NO_ACCESS_MESSAGE`, `_REFUSED_MESSAGE` (a `{message}` template for a
`MemoError`), `_CREATE_FAILED_MESSAGE`, `_CREATED_MESSAGE`.

Frozen properties beyond the signatures:

- The context is **positionally first** and the schema's field is the only other
  parameter, so `functools.partial(create_memo, context)` leaves `body` as the
  binding's one free parameter (the `llm` client's
  `inspect.signature(func).parameters` contract).
- **Never raises** is the contract, so the frozen return type is `str` on every
  path — success, refusal and failure alike. The stub *does* raise, which is what
  makes DoD-1..DoD-4, DoD-8 and DoD-9 red.
- **The refusal chain is `access` absent and nothing else**, stated at length in
  the module docstring: **no archived-book link** (`authorization.md` → the named
  carve-out; `context.md` → decision 4) and **no proposal-mode link**, unlike
  `chapter_tools.py:_refuse_write`'s four links. Any other refusal is
  `services/memos.py`'s, surfaced by catching `MemoError`.
- **`context.subject` is never read** — docstring-stated; `book_id` comes from the
  context and the author from `access.user_id`.
- The module imports `from app.models.schemas.memos import CreateMemoRequest` and
  `from app.services import memos as memo_service` — both **unused by the stub
  and deliberately present**: step 002's `create_memo(access, CreateMemoRequest)`
  is the entry point the body must call, so the ordinal rule and the `active`
  default are never recomputed here. No `app.db` import, and no `session` /
  `AsyncSession` / `select()` / `session.exec()` / `session.add()` anywhere in the
  module.
- `ToolContext` is imported under `TYPE_CHECKING` only (the `chapter_tools.py`
  cycle guard), so `tools.py` may import this module at runtime.

**`backend/app/services/tools.py`** — one import line and one registry entry,
both written in full. Declarative wiring (step 001's `db_import_export` registry
entry precedent: the record *is* the interface; the behaviour behind it stays
unimplemented).

- `backend/app/services/tools.py` — `from app.services.memo_tools import CreateMemoArgs, bind_create_memo` — changed (import block only)
- `backend/app/services/tools.py` — `TOOL_REGISTRY` gains a 19th entry, appended last — changed
  - `ToolDef(name="create_memo", description=<model-facing text>, args_schema=CreateMemoArgs, group="book", binder=bind_create_memo)` — **binder set, `callable` left unset** (the exactly-one-of rule)
  - group is the **existing** `"book"` — no new group, valid-group set not widened (`context.md` → decision 9)
- `backend/app/services/tools.py` — `class ToolContext` — **untouched**: still exactly seven fields (`book_id`, `access`, `subject`, `emit_frame`, `selection_text`, `active_notes_proposal`, `codex_creates_this_turn`). `ToolDef`, `ToolBinder`, `resolve_tools` and `build_tool_bindings` are untouched too.

**Deliberately NOT written by the skeleton — the coder's, so the clauses that
pin them go red at the gate:**

- `backend/app/services/assistant_runtime.py` — **untouched.** `BASE_TOOL_NAMES`
  still reads `("web_search",)`; widening it to `("web_search", "create_memo")` is
  the coder's (DoD-6). The symbol already exists, so a test binds to it either
  way — nothing needed it changed to compile. Nothing else in the module moves:
  no `ResolvedSubject` member, no `determine_mode` branch, no change to the three
  gating cases.
- `backend/app/db/mode_tools.py` — **untouched.** `DEFAULT_MODE_TOOL_NAMES` gains
  `create_memo` in all five tuples as the coder's work (DoD-7);
  `seed_default_mode_tools()` keeps its per-mode idempotence.
- `backend/app/db/assistant_modes.py` — **untouched.** The US-130 guidance in the
  five `DEFAULT_MODE_SYSTEM_PROMPTS` entries is the coder's (DoD-11);
  `seed_default_modes()`'s check-then-create logic is unchanged.

- Caller-compile edits (out of Source-files scope): **None.** Nothing in
  `backend/app/` referenced `memo_tools` before this step, and no existing
  signature changed — the registry entry is additive and `ToolContext` gained no
  field, so every `ToolContext(...)` construction and every `resolve_tools` /
  `build_tool_bindings` call site binds unchanged.

Verification: `cd backend && .venv/Scripts/python -c "import app.main"` clean;
`TOOL_REGISTRY` reads 19 entries with the `create_memo` entry carrying
`group="book"`, `args_schema=CreateMemoArgs`, a binder and **no** plain callable;
`dataclasses.fields(ToolContext)` still reads **7**;
`inspect.signature(create_memo)` reads `(context: 'ToolContext', body: str) -> str`
and `inspect.signature(bind_create_memo)` reads
`(context: 'ToolContext') -> Callable[..., object]`;
`CreateMemoArgs.model_fields` reads one required `body: str`. (Backend has no
separate typecheck — import is the gate. Tests are the verifier's to run.)

### Step 009 — frozen interface (2026-09-15)

Frontend step. **17 frozen symbols** across seven files: four DTO interfaces, eight
api functions, one navigator entry, one route, one page component, and two
`SubjectKind` widenings. Everything declarative (the `.d.ts`, the nav row, the
route, the placeholder page, the subject branch) is written **in full** — there is
nothing to leave unimplemented in a type, a table row or a placeholder; only the
**eight api function bodies** are stubs.

**`frontend/src/types/memos.d.ts`** — new module. Hand-written wire DTOs, wire-exact
`snake_case`, ids `string`, no `any`. Declarations, complete as written.

- `frontend/src/types/memos.d.ts` — `export interface CreateMemoRequest` — new
  - `body: string` — no constraint; `""` is legitimate input, never a 422
- `frontend/src/types/memos.d.ts` — `export interface UpdateMemoRequest` — new
  - `body: string` — and nothing else: no `expected_modified_at`, no `active` / `archived`
- `frontend/src/types/memos.d.ts` — `export interface ReorderMemosRequest` — new
  - `memo_ids: string[]` — the **full** ordered id list of the caller's non-archived memos
- `frontend/src/types/memos.d.ts` — `export interface MemoResponse` — new
  - `id: string`
  - `book_id: string`
  - `body: string`
  - `ordinal: number`
  - `active: boolean`
  - `archived: boolean`
  - `created_at: ISODateString | null`
  - `modified_at: ISODateString | null`
  - **no `user_id` field** — the backend does not send one (step 002's frozen `MemoResponse`)

Field-for-field against the backend twins frozen in steps 002 / 004; `ISODateString`
is `types/common.d.ts`'s (the `CodexEntryResponse` precedent), nullable on both
stamps because the backend columns are. The `{ items: [...] }` envelope (backend
`MemoListResponse`) is **deliberately not modelled** here.

**`frontend/src/api/memos.ts`** — new module. Eight exported functions, one per
endpoint; every body throws through a module-private `stub(name, args): never`
helper (`026 step 009 — skeleton stub: …`), which the coder deletes with the last
stub body.

- `frontend/src/api/memos.ts` — `export async function listMemos(bookId: string, includeArchived: boolean, signal?: AbortSignal): Promise<MemoResponse[]>` — new
- `frontend/src/api/memos.ts` — `export async function createMemo(bookId: string, body: CreateMemoRequest, signal?: AbortSignal): Promise<MemoResponse>` — new
- `frontend/src/api/memos.ts` — `export async function updateMemoBody(bookId: string, memoId: string, body: UpdateMemoRequest, signal?: AbortSignal): Promise<MemoResponse>` — new
- `frontend/src/api/memos.ts` — `export async function reorderMemos(bookId: string, body: ReorderMemosRequest, signal?: AbortSignal): Promise<{ items: MemoResponse[] }>` — new
- `frontend/src/api/memos.ts` — `export async function activateMemo(bookId: string, memoId: string, signal?: AbortSignal): Promise<MemoResponse>` — new
- `frontend/src/api/memos.ts` — `export async function deactivateMemo(bookId: string, memoId: string, signal?: AbortSignal): Promise<MemoResponse>` — new
- `frontend/src/api/memos.ts` — `export async function archiveMemo(bookId: string, memoId: string, signal?: AbortSignal): Promise<MemoResponse>` — new
- `frontend/src/api/memos.ts` — `export async function restoreMemo(bookId: string, memoId: string, signal?: AbortSignal): Promise<MemoResponse>` — new
- `frontend/src/api/memos.ts` — `const BASE = "/api/books"` — new (module-level, the `api/codex.ts` / `api/chats.ts` shape)

Frozen properties beyond the signatures:

- **Method + path per function**, from the wire contract (`context.md`) and steps
  003 / 004 / 005: `GET {BASE}/{bookId}/memos?include_archived=<flag>`,
  `POST {BASE}/{bookId}/memos`, `PUT {BASE}/{bookId}/memos/{memoId}`,
  `PUT {BASE}/{bookId}/memos/order`, and `POST {BASE}/{bookId}/memos/{memoId}/<verb>`
  for `activate` / `deactivate` / `archive` / `restore`. Each is stated in its own
  docstring; the coder implements exactly those.
- **`listMemos` is the ONLY function that unwraps `.items`** and the only one whose
  return type is a plain array — DoD-8's "unwraps the `items` envelope on the list
  call **only**". `reorderMemos` therefore resolves to the **envelope**
  `{ items: MemoResponse[] }`, declared inline at the call site (envelopes are not
  modelled in `.d.ts`), the `api/chapters.ts:reorderChapters` shape.
- **`includeArchived` is a required `boolean`**, not optional — the caller always
  states which list it wants (the `api/chats.ts:listChats(bookId, archived, signal?)`
  precedent), and DoD-8 pins that the flag is sent.
- **`signal?: AbortSignal` is the trailing parameter of every function**, and ids are
  interpolated as **strings** — no `Number(...)` anywhere on this surface.
- **The four state verbs send NO request body** and take `(bookId, memoId, signal?)`
  only — no flag argument, matching step 005's frozen four-verb service shape.
- **No state, no MobX, no error swallowing**: `ApiError` from `client.request<T>`
  propagates to the caller. **No `DELETE` function at any path.**

**`frontend/src/work/components/shell/navItems.ts`** — one added table row; the two
pure helpers and the `WorkNavItem` / `WorkPaneTarget` types are **untouched**.

- `frontend/src/work/components/shell/navItems.ts` — `WORK_NAV_ITEMS` gains an **eighth** entry, **last**, after Chats — changed (was exactly seven)
  - `{ path: "/memos", label: "Memos", icon: IconNotes, paneTarget: "content" }`
  - **no `extraActiveSegments`** — there is no item route to light up for
  - `IconNotes` added to the existing `@tabler/icons-react` import
- `workNavHref` / `isWorkNavItemActive` — **unchanged**: an entry with no
  `extraActiveSegments` was already the common case, so the memos entry needs no
  matcher change. `paneTarget: "content"` makes it an **ordinary router link** — no
  pane-control exception is reintroduced.

**`frontend/src/work/routes.tsx`** — one added route, mounted directly.

- `frontend/src/work/routes.tsx` — `<Route path="memos" element={<MemosListPage />} />`, declared after the `chats` route and before the nested `path="*"` catch-all — new
- **No `key={…}` wrapper and no wrapper component** — that is the item-route remount
  rule, and no memo id appears in any URL. **No `memos/:id` and no `memos/new` route**
  is declared, so an address under `/memos/` falls through to the nested
  `NotFoundPage` inside the shell.
- `import { MemosListPage } from "./pages/MemosListPage";` added.

**`frontend/src/work/pages/MemosListPage.tsx`** — new module. **Written complete, not
stubbed**: the placeholder IS this step's deliverable (`context.md` → "One mechanical
note on step 009 vs 010"), and **step 010 replaces the body**.

- `frontend/src/work/pages/MemosListPage.tsx` — `export const MemosListPage = observer(function MemosListPage() { … })` — new
  - **no props** — `observer`-wrapped, like every other subject page
  - renders `<Title order={3}>Memos</Title>` (an accessible heading named "Memos")
    plus a dimmed owner label, `"This view is delivered by 026.memos step 010."`
  - **no state class, no api call, no `useEffect`, no memo rendering** — all of that
    is step 010's

**`frontend/src/work/subject.ts`** — one widened union, one added branch. Nothing else
in the module is touched.

- `frontend/src/work/subject.ts` — `SubjectKind` gains `"memos"` as its **eleventh and last** member — changed (was ten)
- `frontend/src/work/subject.ts` — `resolveEditability(subject: LoadedSubject): Editability` gains a `case "memos"` returning the **constant** `{ editable: "whole", readOnlyReason: null }` — changed (signature unchanged)
- **No `EditableRegion` member is minted** (still exactly six) and **`WriteRegion` is
  not widened** (still `"whole" | "book-state-notes"`) — DoD-7.
- **`checkWritePermission` is byte-untouched**, so its answer is unchanged for every
  existing subject kind.
- **Every other list kind keeps its verdict and its wording verbatim** —
  `{ editable: "none", readOnlyReason: "This is a list view and cannot be edited." }`
  for `chapters` / `characters` / `locations` / `facts` / `variants` /
  `chapter-variants` / `chats`; the chapter, codex and book-state rows and the
  `default` fallback are untouched. The `memos` case is declared **below** that
  group, not folded into it.
- **`resolveSubjectPaneTarget` is untouched** — it already answers `"content"` for
  every kind but `"chats"`, which is the right answer for memos.

**`frontend/src/types/chats.d.ts`** — the wire twin, kept structurally identical.

- `frontend/src/types/chats.d.ts` — `SubjectKind` gains `"memos"` as its **eleventh and last** member — changed (was ten). Its "same ten members, same order" comment now reads **eleven**, so the file's own identity claim stays true. `TurnSubject.subject_kind` picks the new member up with no change.

- Caller-compile edits (out of Source-files scope): **None.** Every change is
  additive: the two unions gained a member (no exhaustive `switch` over `SubjectKind`
  exists outside `subject.ts`, whose `default` arm already covers the widening), the
  nav table gained a row, and the two new modules had no callers before this step.
  `src/work/components/shell/WorkNavigator.tsx` maps `WORK_NAV_ITEMS` generically and
  needed no edit; only its prose docstring still says "seven" — a comment, left alone
  as out of scope (see `## Notes & Issues` → "Step 009 skeleton").

Verification: `cd frontend && npx tsc --noEmit` — **clean**. `cd frontend && npm run
test:types` (`tsconfig.test.json`, the only program covering `tests/`) — **clean**, so
no existing spec fails to *compile* against the widened unions; one existing spec now
**asserts** a stale count, recorded under `## Notes & Issues`. Tests are the
verifier's to run.

### Step 010 — frozen interface (2026-09-15)

Frontend step. **16 frozen symbols** across three files: one state class (eight
observable fields) plus its four `get` computeds, six external effect functions, one
row component with its props interface and its label helper, and the page component
with its private subject-kind constant. **Nothing renders and nothing runs**: every effect body, every
computed and both component bodies throw through a module-private
`stub(name, ...args): never` helper (`026 step 010 — skeleton stub: …`), which the
coder deletes with the last stub body. Only declarations are written in full — the
observable field initializers, the props interface, {@link memoLabel}'s string, and
the page's `useState` / `useEffect` wiring.

**`frontend/src/work/pages/memosListPageState.ts`** — new module. One class plus six
`(state, bookId, …, signal?)` effect functions, the `chatsListPageState.ts` shape.

- `frontend/src/work/pages/memosListPageState.ts` — `export class MemosListPageState` — new
  - `memos: MemoResponse[] = []` — **every** memo the caller owns in this book, archived and non-archived merged by the ONE load
  - `memosStatus: "idle" | "loading" | "ready" | "error" = "idle"`
  - `memosError: string | null = null`
  - `showArchived = false` — pure client-side filter; never a refetch
  - `bodyDrafts: Record<string, string> = {}` — typed-but-not-yet-blurred body by memo id; absence means "show the server's value"; whole new object on every write
  - `focusMemoId: string | null = null` — the memo whose body field takes focus next
  - `actionStatus: Record<string, "idle" | "loading" | "error"> = {}` — per-row write status; whole new object (`{ ...state.actionStatus, [id]: "loading" }`), never a mutation
  - `actionError: Record<string, string | null> = {}` — per-row author-facing failure message; whole new object
  - `constructor()` — `makeAutoObservable(this)`, no arguments
  - `get workingMemos(): MemoResponse[]` — non-archived, `ordinal` ascending
  - `get archivedMemos(): MemoResponse[]` — archived, `ordinal` ascending
  - `get displayedBodies(): Record<string, string>` — per memo id: the draft when one exists, else the server's `body`. One computed rather than a per-row method, so the class stays observable data + pure `get` computeds. `""` is a legitimate value, never "absent"
  - `get isEmpty(): boolean` — `workingMemos` is empty (the page's labelled empty state)
- `frontend/src/work/pages/memosListPageState.ts` — `export async function loadMemos(state: MemosListPageState, bookId: string, signal?: AbortSignal): Promise<void>` — new
- `frontend/src/work/pages/memosListPageState.ts` — `export async function createMemo(state: MemosListPageState, bookId: string, signal?: AbortSignal): Promise<void>` — new
- `frontend/src/work/pages/memosListPageState.ts` — `export async function saveMemoBody(state: MemosListPageState, bookId: string, memoId: string, body: string, signal?: AbortSignal): Promise<void>` — new
- `frontend/src/work/pages/memosListPageState.ts` — `export async function setMemoActive(state: MemosListPageState, bookId: string, memoId: string, active: boolean, signal?: AbortSignal): Promise<void>` — new
- `frontend/src/work/pages/memosListPageState.ts` — `export async function archiveMemo(state: MemosListPageState, bookId: string, memoId: string, signal?: AbortSignal): Promise<void>` — new
- `frontend/src/work/pages/memosListPageState.ts` — `export async function restoreMemo(state: MemosListPageState, bookId: string, memoId: string, signal?: AbortSignal): Promise<void>` — new

Frozen properties beyond the signatures (each stated in its own docstring):

- **One load, include-archived ON**: `loadMemos` calls `memosApi.listMemos(bookId, true, signal)`
  **once**; `showArchived` filters what is already loaded. Toggling refetches nothing.
- **No user id crosses the wire**: the only identity in every call is the book id from
  the URL — the api module's eight functions take no user argument (step 009's freeze).
- **`createMemo` posts `{ body: "" }`**, appends the row the SERVER returned, and writes
  that row's id into `focusMemoId`. It never mints a local row and never withholds an
  empty body.
- **`saveMemoBody` is called from the row's `onBlur` only, and only when the displayed
  body differs from `memo.body`.** There is no debounce, no autosave timer and no
  beforeunload flush — one write path.
- **`setMemoActive(…, true)` → `memosApi.activateMemo`, `(…, false)` → `memosApi.deactivateMemo`.**
  Two verbs, one axis; the focus-loss `PUT` carries `body` and nothing else.
- **Every effect reseeds from the server's return** — the returned `MemoResponse`
  replaces the local row (or is appended); nothing keeps an optimistic value. On an
  `ApiError` in `saveMemoBody` the row's **draft entry is dropped too**, so the field
  falls back to server truth while `actionError[memoId]` carries the message.
- **Error routing**: `loadMemos` / `createMemo` → `memosError` (the load trio);
  `saveMemoBody` / `setMemoActive` / `archiveMemo` / `restoreMemo` → `actionStatus[id]`
  = `"error"` + `actionError[id]`, leaving the list intact. Anything that is not an
  `ApiError` **rethrows**, in all six.
- **`runInAction` before AND after each await**, abort-guarded (`if (signal?.aborted) return;`).
- **Imports the coder adds**: `runInAction` from `mobx`, `* as memosApi` from
  `../../api/memos`, `ApiError` from `../../api/client`. They are omitted from the stub
  because `noUnusedLocals` rejects an unused import.

**`frontend/src/work/components/memos/MemoRow.tsx`** — new module (new folder
`components/memos/`). A presentational `observer` row: no state class, no `bookId`, no
api import, no effect, **no `useEffect`**.

- `frontend/src/work/components/memos/MemoRow.tsx` — `export function memoLabel(position: number): string` — new — returns `` `Memo ${position}` ``; **written in full** (the naming scheme IS the contract)
- `frontend/src/work/components/memos/MemoRow.tsx` — `export interface MemoRowProps` — new
  - `memo: MemoResponse` — the row as the SERVER last returned it; the save comparison's left side
  - `position: number` — **1-based index within the list this row is rendered in**, NOT `memo.ordinal` (ordinals carry gaps — archiving never renumbers — and would make the names unstable)
  - `body: string` — the displayed body (`state.displayedBodies[memo.id]`)
  - `busy: boolean` — `actionStatus[memo.id] === "loading"`
  - `error: string | null` — `actionError[memo.id]`
  - `autoFocus: boolean` — `state.focusMemoId === memo.id`
  - `onBodyChange: (body: string) => void` — draft write, every keystroke
  - `onSaveBody: (body: string) => void` — the blur-save, called **only** when `body !== memo.body`
  - `onSetActive: (active: boolean) => void` — receives the REQUESTED state
  - `onArchive?: () => void` — working rows only; `undefined` renders **no** archive control (not a disabled one), the `ChapterOrderList` `dragHandle?` precedent
  - `onRestore?: () => void` — archived section only; same absent-means-absent rule
  - `onBodyFocus?: () => void` — reported from the body field's `onFocus` so the page clears `focusMemoId`; an ordinary handler, not an effect
- `frontend/src/work/components/memos/MemoRow.tsx` — `export const MemoRow: (props: MemoRowProps) => ReactElement` (`observer(function MemoRow(props: MemoRowProps): ReactElement)`) — new

**The accessible-name scheme — FROZEN, because the specs bind to it.** Every name is
built from `memoLabel(position)`, i.e. the row's **1-based position in the list it is
rendered in**; the working list and the archived section each number from **1**. A memo
has no title and `""` is a legitimate body (UC-103), so a position-derived name is the
only handle that cannot break on an empty memo:

| Element | Role | Accessible name (position 1) |
|---|---|---|
| body field (`Textarea`) | `textbox` | `Memo 1 body` |
| on/off control (`Switch`) | `switch` | `Memo 1 active` — with `checked={memo.active}`, so the OFF state is reported as `aria-checked="false"` rather than by styling |
| off marker (`Badge`, only when `!memo.active`) | — | `aria-label` `Memo 1 is off`, text `Off` |
| archive control (`ActionIcon`, working rows) | `button` | `Archive memo 1` |
| restore control (`ActionIcon`, archived section) | `button` | `Restore memo 1` |
| row error (`Alert role="alert"`, only when `error !== null`) | `alert` | `aria-label` `Memo 1 error`, text = `error` |

The name is **stable across a toggle** (it does not change when the memo is switched
off) so a spec can address one row before and after; the state travels on
`aria-checked`.

**`frontend/src/work/pages/MemosListPage.tsx`** — step 009's placeholder body replaced.

- `frontend/src/work/pages/MemosListPage.tsx` — `export const MemosListPage: () => ReactElement` (`observer(function MemosListPage(): ReactElement)`) — changed (was the step-009 placeholder with the same no-props signature; the **signature is unchanged**, only the body)
- `frontend/src/work/pages/MemosListPage.tsx` — `const LIST_SUBJECT_KIND: SubjectKind = "memos"` — new (module-private, the `CodexListPage` / `ChaptersPage` shape)

Frozen properties:

- **No props** — `bookId` from `useParams()`; `const [state] = useState(() => new MemosListPageState())`.
- **ONE page-level `useEffect`, deps `[state]`**, written in full: `new AbortController()`,
  a `const source = () => ({ kind: LIST_SUBJECT_KIND })` closure, `registerContentSubject(source)`
  with **no** apply-draft callback (a list is never a canvas target), `void loadMemos(state, bookId ?? "", ctrl.signal)`,
  and a cleanup calling `unregisterContentSubject(source)` then `ctrl.abort()`.
- **Page-level accessible names**: heading `Memos` (`heading` role — step 009's route
  spec binds to it), create control `New memo`, archive toggle `Show archived`.
- **Row wiring**: `state.workingMemos` → `MemoRow` with `onArchive` and no `onRestore`;
  `state.archivedMemos` → `MemoRow` with `onRestore` and no `onArchive`, rendered only
  while `state.showArchived`. `onBodyChange` writes a whole new `state.bodyDrafts`
  object and `onBodyFocus` clears `state.focusMemoId` — assigned directly in the
  handler, the way `ChatsListPage` assigns `showArchived`.
- **Deliberately not frozen, because they must not exist**: a Save control or any
  dirty/"unsaved changes" badge (US-125.AC-2), a delete control (US-128.AC-3), a memo
  detail link, a restore-buffer write / `baseVersion` / divergence view / `409` path,
  and any reorder affordance (step 011's). No `useCallback` / `useMemo` / `useReducer`,
  no React context, no Mantine `useForm`, no custom `useX` hook appears in any of the
  three files.

- Caller-compile edits (out of Source-files scope): **None.** The two new modules had no
  callers before this step, and `MemosListPage`'s exported signature is unchanged, so
  `work/routes.tsx` needed no edit.

Verification: `cd frontend && npx tsc --noEmit` — **clean**. `cd frontend && npm run build`
— **clean**. `cd frontend && npm run test:types` — **clean**. Tests are the verifier's to run.

**Red-gate consequence the orchestrator should brief** (recorded here because it is a
property of the stub, not a defect): `MemosListPage` now **throws on render**, so while
the stubs stand, step 009's `frontend/tests/work/routes.test.tsx` DoD-4 case
("`/:bookId/memos` … renders the memos page", which asserts the `Memos` heading) fails
too. It returns green when the coder fills the render. See `## Notes & Issues` →
"Step 010 skeleton" for the second-order hazard in that same spec.

### Step 011 — frozen interface (2026-09-15)

Frontend step, the feature's last. **8 frozen symbols** across three files: one component
with its props interface, one exported direction type, three observable fields, one `get`
computed and two external effect functions. **Nothing reorders and nothing renders yet**:
`MemoOrderList`, `displayedWorkingMemos`, `moveMemo` and `applyMemoOrder` all throw
through a module-private `stub(name, ...args): never` helper
(`026 step 011 — skeleton stub: …`), one per file, which the coder deletes with the last
stub body. Only the declarations are written in full — the props interface, the direction
type and the three field initializers.

**`frontend/src/work/components/memos/MemoOrderList.tsx`** — new module. The drag surface
and the arrow controls; `components/chapters/ChapterOrderList.tsx` copied, with ONE
deliberate divergence recorded below.

- `frontend/src/work/components/memos/MemoOrderList.tsx` — `export interface MemoOrderListProps` — new
  - `memos: MemoResponse[]` — the WORKING list in display order (`state.displayedWorkingMemos`); never an archived row, in any filter state
  - `reordering: boolean` — `state.reorderStatus === "loading"`; disables the sortable rows AND every arrow
  - `renderMemo: (memo: MemoResponse, position: number) => ReactElement` — the page's row wiring; `position` is **1-based within this list**
  - `onReorder: (memoIds: string[]) => void` — **THE persist path**; receives the complete ordered id list
  - `onMove: (memoId: string, direction: MemoMoveDirection) => void` — the arrows' handler
- `frontend/src/work/components/memos/MemoOrderList.tsx` — `export const MemoOrderList: (props: MemoOrderListProps) => ReactElement` (`observer(function MemoOrderList(props: MemoOrderListProps): ReactElement)`) — new

**The one divergence from the `ChapterOrderList` template, and why.** `ChapterOrderList`
takes `{ state, bookId }` and imports its effects; `MemoOrderList` is **presentational**
and takes neither. A memo row needs eleven props (body, busy, error, autofocus and five
handlers) and the **archived section renders the same `MemoRow`** through the page's
`renderRow`; handing the order list the state class would fork that wiring in two and let
the working list and the archived section drift — which step 010's `renderRow` docstring
exists to prevent. The render prop keeps ONE row wiring, and it is also what "pass the two
functions down" means literally. Consequence for the coder: `MemoOrderList` imports
`memoLabel` (for the arrow names) and never imports `../../api/memos`,
`memosListPageState`'s effects, or `MemosListPageState`.

**The arrow / handle accessible names — FROZEN, because the specs bind to them.** Step 010
froze the scheme (`memoLabel(position)` → `Memo 1`, from the row's **1-based position in
the list it is rendered in**, never `memo.ordinal`). The arrows use that **same**
convention, verb-first like `Archive memo 1` / `Restore memo 1` — there is not a second
naming scheme anywhere in the row:

| Element | Role | Accessible name (position 1) | `disabled` |
|---|---|---|---|
| up arrow (`ActionIcon`, `IconArrowUp`) | `button` | `Move memo 1 up` — `` `Move ${memoLabel(position).toLowerCase()} up` `` | `reordering` OR `position === 1` |
| down arrow (`ActionIcon`, `IconArrowDown`) | `button` | `Move memo 1 down` — `` `Move ${memoLabel(position).toLowerCase()} down` `` | `reordering` OR `position === memos.length` |
| drag handle (`ActionIcon`, `IconGripVertical`) | `button` | `Drag memo 1 to reorder` — `` `Drag ${memoLabel(position).toLowerCase()} to reorder` `` | — (`useSortable`'s `disabled` carries it) |

Frozen properties beyond the signatures (each stated in its docstring):

- **`DndContext collisionDetection={closestCenter} onDragEnd={handleDragEnd}`** wrapping
  **`SortableContext items={memoIds} strategy={verticalListSortingStrategy}`**, where
  `memoIds = props.memos.map((memo) => memo.id)`.
- A **module-private `SortableMemoRow`** (not exported, not frozen) calling `@dnd-kit`'s
  **own** `useSortable({ id: memo.id, disabled: reordering })` — a library hook, which is
  explicitly not a breach of the no-custom-hooks rule (that rule forbids *authoring*
  hooks). It is not wrapped in a hook of ours and holds none of our state.
- **`handleDragEnd`** ignores a drop with no `over`, onto itself, or naming an unknown id,
  and otherwise calls **`onReorder(arrayMove(memoIds, from, to))`** — the full new
  sequence, through the same entry point the arrows reach via `onMove` → `moveMemo` →
  `applyMemoOrder`. **The component has exactly one api-reaching path** (`onReorder`); it
  never computes a one-step swap itself and never imports an api function, so a second
  persist path cannot be written without changing this freeze.
- **Each memo renders through step 010's `MemoRow`**, via `renderMemo` — the component
  owns no memo state of its own: no `useState`, no `useEffect`, no `useCallback` /
  `useMemo` / `useReducer`, no React context, no custom `useX` of ours. `observer` on this
  component and on `SortableMemoRow`.
- **Nothing archived is ever here**: no archived row, no archive/restore control, and no
  archived id in the list handed to `onReorder` (DoD-7).
- **Imports the coder adds** (omitted from the stub because `noUnusedLocals` rejects an
  unused import): `DndContext` / `closestCenter` and `type DragEndEvent` from
  `@dnd-kit/core`; `SortableContext` / `arrayMove` / `useSortable` /
  `verticalListSortingStrategy` from `@dnd-kit/sortable`; `ActionIcon` / `Group` / `Stack`
  from `@mantine/core`; `IconArrowUp` / `IconArrowDown` / `IconGripVertical` from
  `@tabler/icons-react`; `memoLabel` from `./MemoRow`; `CSSProperties` from `react`.
  **No package change** — both `@dnd-kit` packages are runtime deps since feature 014.

**`frontend/src/work/pages/memosListPageState.ts`** — three observable fields, one
computed, one exported type and two effect functions ADDED. Step 010's class members and
all six of its effects are byte-untouched apart from one stale docstring clause (below).

- `frontend/src/work/pages/memosListPageState.ts` — `export type MemoMoveDirection = "up" | "down"` — new (the `ChapterMoveDirection` shape)
- `frontend/src/work/pages/memosListPageState.ts` — `MemosListPageState` gains three fields — changed (was eight fields, four computeds)
  - `reorderStatus: "idle" | "loading" | "ready" | "error" = "idle"` — the reorder's own status, apart from `memosStatus` and `actionStatus`
  - `reorderError: string | null = null` — the LIST-level refusal message, never sharing a holder with `memosError` or `actionError`
  - `pendingOrder: string[] | null = null` — the id sequence being arranged; non-`null` exactly while `reorderStatus === "loading"`
- `frontend/src/work/pages/memosListPageState.ts` — `get displayedWorkingMemos(): MemoResponse[]` — new (the class's **fifth** computed)
- `frontend/src/work/pages/memosListPageState.ts` — `export async function moveMemo(state: MemosListPageState, bookId: string, memoId: string, direction: MemoMoveDirection, signal?: AbortSignal): Promise<void>` — new
- `frontend/src/work/pages/memosListPageState.ts` — `export async function applyMemoOrder(state: MemosListPageState, bookId: string, memoIds: string[], signal?: AbortSignal): Promise<void>` — new

Frozen properties beyond the signatures:

- **One persist path.** `applyMemoOrder` is the ONLY function on this surface that calls
  `memosApi.reorderMemos`, and it calls it **once**, with the whole list:
  `memosApi.reorderMemos(bookId, { memo_ids: memoIds }, signal)`. `moveMemo` computes the
  fully swapped id list locally out of `displayedWorkingMemos` and **delegates** — it
  never calls an api function and never re-implements the pending order, the re-seed or
  the error handling (DoD-1, and the premise DoD-4's `[manual/live]` drag check rides on).
- **What is submitted**: the complete ordered id list of the caller's **non-archived**
  memos — the ids of `displayedWorkingMemos`, nothing added, nothing left out, never a
  single moved id, never an archived id, and never the archived section's ids while
  `showArchived` is on (a view filter is not a list). `applyMemoOrder` submits what it is
  handed: it does not filter, pad or dedupe. Backend step 004 answers **400** to a short
  list, a long one, a duplicate, an archived id or another author's id.
- **A no-op move persists nothing**: `moveMemo` returns without calling `applyMemoOrder`
  when the memo is absent from the working list or already at that end, so a disabled
  control clicked anyway produces no write.
- **Optimism is a RENDERING optimism only** (DoD-5): `applyMemoOrder` sets
  `pendingOrder = [...memoIds]`, `reorderStatus = "loading"`, `reorderError = null` BEFORE
  the await; `state.memos` is not touched until the server answers.
- **Success re-seeds from the server and is a MERGE, not a replacement** (DoD-2):
  `reorderMemos` returns the **working** memos only (`{ items }`), so each returned row
  replaces its local twin — carrying the server's new ordinal — while the archived rows in
  `state.memos` are kept, and an archived memo cannot vanish because a reorder happened.
  Then `pendingOrder = null`, `reorderStatus = "ready"`, so the list renders the SERVER's
  order rather than the local computation.
- **Failure discards the pending order, and that IS the rollback** (DoD-6): on `ApiError`,
  `reorderError = err.message || "Could not reorder the memos."`,
  `reorderStatus = "error"`, `pendingOrder = null` — and **no refetch**, because
  `state.memos` was never mutated, so dropping the pending sequence alone snaps the view
  back to server truth with no partial order surviving. Anything that is not an `ApiError`
  rethrows. `pendingOrder` is left `null` on EVERY exit path, aborts included.
  Abort-guarded before every write (`if (signal?.aborted) return;`), `runInAction` before
  AND after each await.
- **`displayedWorkingMemos`** resolves to `pendingOrder` mapped back onto the loaded rows
  while one is in flight, and to `workingMemos` (the server's ordinal order) otherwise. A
  memo the pending sequence does not name keeps its ordinal place at the end rather than
  vanishing. Built from `workingMemos`, so **it can never contain an archived memo**. Pure.
- **A reorder touches nothing else**: `bodyDrafts`, `focusMemoId`, `actionStatus`,
  `actionError`, `showArchived` and the load trio's status are never written by either
  function, so a refused reorder leaves every row's own state alone.

**Note for whoever writes the specs** — the list renders by the **server's ordinal**
(`workingMemos` sorts on `ordinal`, which is what backend step 004 rewrites to `1..N`). A
mock whose resolved `{ items }` express a new order must give those rows the matching
ordinals; returning rows in a new array order while keeping their old ordinals would not
express a reordered server state.

**`frontend/src/work/pages/MemosListPage.tsx`** — **signature unchanged and body
deliberately unchanged**; the module's docstring now carries the exact wiring contract.

- `frontend/src/work/pages/MemosListPage.tsx` — `export const MemosListPage: () => ReactElement` — **unchanged** (no props, `observer`; step 010's render is intact)

Why the body is not wired here: `MemoOrderList`'s stub throws, so rendering it would make
the whole page throw and would turn **step 010's entire green spec file red** — a
regression in a `done` step, and a red gate failing for the wrong reason. Left as it is,
step 011's specs fail because the arrows do not exist and no reorder call is made, which
is the right reason, and step 010 stays green. The three things the coder adds, frozen in
the page's own docstring:

1. The working list renders through `<MemoOrderList memos={state.displayedWorkingMemos}
   reordering={state.reorderStatus === "loading"} renderMemo={(memo, position) =>
   renderRow(memo, position - 1, false)} onReorder={(memoIds) => { void
   applyMemoOrder(state, book, memoIds); }} onMove={(memoId, direction) => { void
   moveMemo(state, book, memoId, direction); }} />` inside the same `state.isEmpty` branch.
   `renderRow` stays THE one row wiring, shared with the archived section.
2. A LIST-level reorder `Alert`, rendered when `state.reorderError !== null`, `aria-label`
   **`Reorder error`** (role `alert`), title `Could not reorder the memos`, text
   `state.reorderError` — its own surface, never sharing a holder with `memosError` or a
   row's `actionError` (DoD-6).
3. Nothing else. **The archived section is NOT reorderable**: rendered exactly as it
   already is — no `MemoOrderList`, no drag handle, no arrows — and its ids never reach a
   persist call even while `state.showArchived` is on (DoD-7).

- Caller-compile edits (out of Source-files scope): **None.** The new module has no callers
  yet, the three added fields and the added computed are additive, both new functions are
  new exports, and `MemosListPage`'s exported signature is unchanged, so `work/routes.tsx`
  needed no edit. Two comment-only edits inside the Source files: the `MemosListPageState`
  class docstring's "and any reorder state (step 011's)" clause (it had become untrue) and
  the page docstring's wiring contract above.

Verification: `cd frontend && npx tsc --noEmit` — **clean**. `cd frontend && npm run build`
— **clean**. `cd frontend && npm run test:types` — **clean**. Tests are the verifier's to
run.


## Tests

### Step 001 — tests (2026-09-15)

- `backend/tests/db/test_memos.py` — covers DoD-1..DoD-11 — many memos per `(book, author)` asserted
  at the database level (two/three successful inserts, no constraint to violate); create defaults
  (`active` true / `archived` false) and full column round trip through `create` → `get_by_id`;
  `body = ""` stored and returned as `""`; `list_for_author` scoped strictly to the requested
  `(book_id, user_id)` pair in both directions; the include-archived flag off by default and on by
  request; inactive rows listed exactly like active ones; ascending `ordinal` order including across
  gaps; `update` persisting a changed body, returning stored state and setting **no** timestamps of
  its own; the two flags persisted independently across deactivate / archive / restore / activate
  and all four combinations storable; and the structural absence of any delete function (public
  callables defined in the module are exactly `create`, `get_by_id`, `list_for_author`, `update`).
- `backend/tests/test_data_domain_memos.py` — covers DoD-12, DoD-13, DoD-14 — codec round trip over
  the frozen key set with ids emitted as strings and legacy numeric ids still parsing, the
  falsy-but-legal `""` / `False` / `False` values surviving as themselves, null timestamps
  round-tripping as null; exactly one `memos` entry in `TABLE_REGISTRY` immediately after
  `chapter_author_prompts` and immediately before `chapters`, bound to `Memo` + the codec pair; the
  `memos` table present and queryable on a freshly initialised database with an all-`ok` consistency
  report.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓,
  DoD-10 ✓, DoD-11 ✓, DoD-12 ✓, DoD-13 ✓, DoD-14 ✓ (no `[manual/live]` items in this step).

#### Re-bind of the eight registry-order specs (the `## Notes & Issues` gap below)

One line inserted per file — `    "memos",` between `"chapter_author_prompts",` and `"chapters",` in
the hard-coded canonical label list; nothing else changed in any of them:
`backend/tests/test_data_domain_assistant_core.py`, `…_assistant_links.py`, `…_book.py`,
`…_chapter.py`, `…_chapter_changes.py`, `…_chat.py` (`FULL_CANONICAL_ORDER`), `…_codex.py`,
`…_continuity.py`.

### Step 002 — tests (2026-09-15)

- `backend/tests/services/test_memos.py` — covers DoD-1..DoD-11 — one spec module, bound to the
  step-002 frozen skeleton (`MemoErrorReason` / `MemoError` / `_require_member` / `list_memos` /
  `create_memo` / `update_memo_body` and the four DTOs), using the `db` fixture with local
  `_seed_user` / `_seed_book` / `_seed_memo` / `_access` helpers and a directly constructed
  `BookAccess` (no HTTP at this layer). What it asserts, by item:
  - **DoD-1** — first memo is ordinal 1 and later ones append (1, 2, 3); the append rule computed
    over the caller's **non-archived** memos (live 1, 2 plus an archived 3 gives the next memo
    ordinal **3**, not 4); the ordinal scoped per `(book, author)` so another author's ordinal 9 in
    the same book and the caller's ordinal 7 in another book both leave the next at 1; an
    all-archived list giving 1.
  - **DoD-2** — a created memo is `active` / not `archived` on both the DTO and the stored row, with
    both timestamps stamped.
  - **DoD-3** — `body = ""` creates, stores and lists as `""`; `CreateMemoRequest(body="")`
    constructs; the body update may also clear to `""`.
  - **DoD-4** — both directions: a co-author sees none of the owner's memos, and the book's **owner**
    sees none of a co-author's two memos (US-124.AC-2); plus list scoping to `access.book_id`.
  - **DoD-5** — archived excluded by default, included with the flag (and flagged `archived` in the
    DTO); an **inactive** memo listed exactly like an active one (the two axes are independent).
  - **DoD-6** — rows stored 3/1/2 come back 1, 2, 3; ordinal order holds across an archive gap, both
    live-only (1, 4, 7) and archive-inclusive (1, 2, 4, 7).
  - **DoD-7** — body update writes the body, stamps `modified_at` past a fixed past anchor, leaves
    `created_at`, `ordinal` (7), `active` (False) and `archived` untouched on DTO and row; a second
    test shows an archived memo stays archived; `UpdateMemoRequest` has exactly `{"body"}`.
  - **DoD-8** — all four sources (non-numeric id, unknown id, another author's memo, another book's
    memo) collected in one loop: each `not_found`, and the set of
    `(type, reason, message)` fingerprints has length **1** — sameness, not merely "each raises";
    neither foreign row is written; a matching positive case shows the resolver admits the caller's
    own memo.
  - **DoD-9** — `reader` and `none` refused with `not_a_member` on **all three** entry points (with
    nothing created and the owner's memo untouched); `_require_member` called directly raises for
    both roles and admits owner and co-author; `list(MemoErrorReason)` is exactly
    `[not_a_member, not_found]`; a co-author is admitted on all three entry points.
  - **DoD-10** — `MemoResponse.model_fields` is exactly the eight wire fields with no `user_id` and
    no `user`-named field; on real create / update / list responses every `id` and `book_id` is a
    `str` and `user_id` is absent.
  - **DoD-11** — create **and** body-update both succeed with `book_state=BookState.archived` (the
    carve-out), and the list answers there too.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓,
  DoD-10 ✓, DoD-11 ✓ (no `[manual/live]` items in this step).

### Step 003 — tests (2026-09-15)

- `backend/tests/routes/test_memos.py` — covers DoD-1..DoD-13 — one spec module driving the real
  `app.main.app` in-process through the `http_client` fixture (httpx `ASGITransport`, no network),
  with local `_seed_user` / `_seed_author` / `_seed_book` / `_seed_public_book` / `_add_co_author` /
  `_seed_memo` / `_auth_header` helpers copied from `tests/routes/test_book_author_prompts.py`; auth
  is real (seeded user row + minted JWT). Bound to the step-003 frozen skeleton: `GET`/`POST`
  `/api/books/{book_id}/memos` and `PUT /api/books/{book_id}/memos/{memo_id}`, envelope key `items`,
  string ids, no `user_id`. What it asserts, by item:
  - **DoD-1** — both directions: a co-author sees only their own memo, and the book's **owner** sees
    none of the co-author's (US-124.AC-2).
  - **DoD-2** — no query parameter at all omits the archived memo while still listing an
    inactive-but-live one (the two axes are independent).
  - **DoD-3** — `include_archived=true` returns the archived row flagged `archived`, and an explicit
    `false` behaves like omitting it.
  - **DoD-4** — rows stored with ordinals 7 / 1 / 4 come back 1, 4, 7 — ordinal order across an
    archive gap.
  - **DoD-5** — `POST` answers **201** with string `id` / `book_id` and no `user_id`, and the created
    memo is **last** in the following list.
  - **DoD-6** — the created memo is `active` and not `archived`, on the 201 response and on read-back.
  - **DoD-7** — `POST {"body": ""}` is asserted **not 422** and **201**, with `""` stored and listed.
  - **DoD-8** — `PUT` answers 200 with the new body while `id`, `book_id`, `ordinal` (7), `active`
    (False), `archived` and `created_at` are unchanged (only `modified_at` may move).
  - **DoD-9** — all four unreachable ids (another author's memo, a memo of another book, an id
    belonging to nobody, a non-numeric id) in one loop: each **404**, and the set of JSON-normalised
    response bodies has length **1** — sameness, not merely "each is a 404"; neither foreign row was
    written.
  - **DoD-10** — three separate tests, three separate fixtures: no `Authorization` header → **401**
    on all three routes; a logged-in stranger to a **private** book → **404** from the dependency on
    all three; a logged-in reader on a **public** book → **403** on all three, with the owner's memo
    untouched.
  - **DoD-11** — the book's state is set to `archived` via `books.update` after seeding, then `POST`
    answers **201** and `PUT` answers **200** — the carve-out's route-level proof.
  - **DoD-12** — `DELETE` on both paths answers **405** and the memo survives.
  - **DoD-13** — path resolution read from `app.openapi()["paths"]` (the top-level `app.routes` list
    keeps included routers wrapped): the collection path carries `get` + `post`, the item path
    carries `put`, and neither carries `delete`.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓,
  DoD-10 ✓, DoD-11 ✓, DoD-12 ✓, DoD-13 ✓ (no `[manual/live]` items in this step).

### Step 004 — tests (2026-09-15)

- `backend/tests/services/test_memos_order.py` — covers DoD-1, DoD-2, DoD-3, DoD-4, DoD-5, DoD-8 —
  the service half, bound to the step-004 frozen skeleton (`ReorderMemosRequest(memo_ids: list[str])`,
  `MemoErrorReason.invalid_reorder_set`, `reorder_memos(access, req) -> MemoListResponse`), using the
  `db` fixture with local `_seed_user` / `_seed_book` / `_seed_memo` / `_access` helpers copied from
  `tests/services/test_memos.py` and a directly constructed `BookAccess` (no HTTP at this layer).
  Archived rows are seeded by writing the flag through `db/memos.py` — step 005's routes do not exist.
  By item:
  - **DoD-1** — a three-memo list submitted as C/A/B lands ordinals 1/2/3 on both the returned
    envelope and the stored rows; a four-memo full reversal lands 1..4.
  - **DoD-2** — `list_memos` after a reorder returns exactly the submitted sequence.
  - **DoD-3** — four separate refusals, one test each (too short, too long, a duplicated id, an id
    outside the caller's non-archived set): each raises `invalid_reorder_set`, and after each the
    stored ordinals are still 1/2/3 with `modified_at` still at the seeded past anchor — nothing
    written. A fifth test pins the reason as *not* `not_found`.
  - **DoD-4** — another author's id, another book's id and an id belonging to nobody collected in one
    loop: each `invalid_reorder_set`, and the set of `(type, reason, message)` fingerprints has length
    **1** — no existence oracle; plus a "too long" probe leaving the foreign row's ordinal and
    timestamp untouched.
  - **DoD-5** — both halves: an archived id inside the submitted list is refused; a successful reorder
    of the survivors renumbers only them while the archived row keeps its ordinal (the gap is not
    reclaimed) and stays archived; a third test shows the valid set is the live memos alone.
  - **DoD-8** — a reorder succeeds with `book_state=BookState.archived`.
- `backend/tests/routes/test_memos_order.py` — covers DoD-1..DoD-8 (route half) — one spec module
  driving the real `app.main.app` in-process through `http_client`, with local `_seed_user` /
  `_seed_author` / `_seed_book` / `_seed_public_book` / `_add_co_author` / `_seed_memo` /
  `_auth_header` helpers and a real JWT. By item:
  - **DoD-1** — `PUT …/memos/order` answers **200** with the `items` envelope, ordinals 1..N in the
    submitted order, string ids and no `user_id`; the stored rows confirm the rewrite.
  - **DoD-2** — the plain `GET` after the reorder returns the submitted order.
  - **DoD-3** — all four invalid sets in one loop, each **400**, and after each refusal both the
    stored ordinals and the author's listed order are unchanged.
  - **DoD-4** — a co-author's memo id, another book's memo id and a nobody id each **400** with
    JSON-normalised response bodies collapsing to a set of length **1**; the foreign rows unwritten.
  - **DoD-5** — the archived id in the list is 400; the survivors-only reorder is 200 and leaves the
    archived ordinal at 2 beside the new live 2.
  - **DoD-6** — a well-formed reorder body succeeds while the same path carrying the *body-update*
    shape is a **422** and explicitly neither 404 nor 200 (had `/{memo_id}` captured it, `{"body": …}`
    would have been a valid update of a memo named `order`); a real memo id on `/{memo_id}` still
    answers 200 with the new body; and `app.openapi()["paths"]` carries `…/memos/order` as a path
    distinct from `…/memos/{memo_id}`.
  - **DoD-7** — three fixtures: no `Authorization` header → **401**; a stranger to a **private** book
    → **404**; a logged-in non-member of a **public** book → **403**, with nothing written in either
    refusal.
  - **DoD-8** — the book's state set to `archived` via `books.update`, then the reorder answers 200.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓ (no
  `[manual/live]` items in this step).

#### Repair (2026-09-15) — Fault TEST, `backend/tests/services/test_memos_order.py`

The two DoD-3 specs for the **too-short** and **duplicated-id** shapes expressed the
"nothing is written" half as `all((await _stored(row.id)).modified_at == ANCHOR for row in …)`.
An `await` inside a generator expression makes it an *async* generator, so `all()` raised
`TypeError: 'async_generator' object is not iterable` inside the test body — the clause could
never evaluate, for any implementation. It was masked at the red gate because the stub's
`NotImplementedError` fired first. Both are now three explicit per-row awaits
(`assert (await _stored(first.id)).modified_at == ANCHOR`, and likewise for `second`/`third`),
the idiom already used successfully in the DoD-5 archived-ordinal spec. The clause is unchanged
in strength — same three rows, same anchor comparison — only made executable. No other file
touched.

#### Re-bind of the step-002 enum spec (the `## Notes & Issues` gap below)

One line added — `MemoErrorReason.invalid_reorder_set,` to the expected list in
`backend/tests/services/test_memos.py::test_service_reasons_are_membership_and_one_not_found__DoD9`.
Nothing else in that file changed; the test name is deliberately left alone so step 002's DoD-9 tag
stays intact.

### Step 005 — tests (2026-09-15)

- `backend/tests/services/test_memos_state.py` — covers DoD-1..DoD-12 except DoD-11's 405 half —
  the service half, bound to the step-005 frozen skeleton (`activate_memo` / `deactivate_memo` /
  `archive_memo` / `restore_memo`, each `(access, memo_id: str) -> MemoResponse`), using the `db`
  fixture with local `_seed_user` / `_seed_book` / `_seed_memo` / `_access` / `_stored` helpers
  copied from `tests/services/test_memos_order.py` and a directly constructed `BookAccess`. A
  module-level `VERBS` tuple drives the cross-verb specs. By item:
  - **DoD-1** — a deactivated memo is still returned by the ordinary (non-archived) `list_memos`,
    in place alongside its sibling.
  - **DoD-2** — deactivate writes `active` False on the DTO and the row while `archived`, `ordinal`
    (7) and `body` are untouched, `created_at` stays at the anchor and `modified_at` is stamped
    past it; a second spec shows the flag on the ordinary read.
  - **DoD-3** — activate writes `active` True with `archived` / `ordinal` (4) / `body` untouched
    and `modified_at` stamped; a second spec shows activate does **not** reach the archive axis
    (an archived memo switched on is still archived).
  - **DoD-4** — deactivating the caller's only active memo succeeds and leaves the memo listed with
    nothing active; a second spec deactivates the last *active* of two.
  - **DoD-5** — the archived memo is absent from the default list and present, flagged `archived`,
    in the include-archived list; plus archive writing `archived` and stamping `modified_at` with
    `body` intact.
  - **DoD-6** — three memos 1/2/3, the **middle** archived then restored: ordinal **4**, explicitly
    `!= 2`, so old-slot and append-last give different answers; survivors still 1 and 3 and the
    restored memo last in the list. Two more: the max is taken over **non-archived** memos only
    (live 1 and 5 beside a still-archived 9 gives **6**), and a restore into an empty working list
    gives **1**.
  - **DoD-7** — archiving the middle of three renumbers nothing (stored 1 / 2 / 3, each materialized
    with its own explicit `await`), the archived row keeps ordinal 2, and the working list reads
    `[1, 3]` with the gap visible; a second spec archives the **last** memo with the same result.
  - **DoD-8** — the four-memo case: one memo archived while ON and one while OFF, both restored,
    each returning with the flag it went in with (asserted on the archive response too, not only
    after restore), plus two bystanders whose flags never move; a second spec shows restore does not
    switch a memo back on.
  - **DoD-9** — all four verbs × four unreachable ids (non-numeric, unknown, another author's,
    another book's) in one loop: each raises `not_found`, and the set of
    `(type, reason, message)` fingerprints has length **1** — sameness across all sixteen; neither
    foreign row was written (`modified_at` still at the anchor). Plus a positive counterpart (each
    verb admits the caller's own memo) and a spec pinning `MemoErrorReason` at exactly the same
    three members step 004 left it at — this step adds none.
  - **DoD-10** — four per-verb no-op specs (activate on active, deactivate on inactive, archive on
    archived — each returning the row with `active` / `archived` / `ordinal` / `body` / `created_at`
    unchanged) plus a fifth showing every verb repeated twice never raises. The fourth, restore on a
    **non-archived** memo, is now a full no-op spec — `ordinal` included; see the note below.
  - **DoD-11** (service half) — after each of the four verbs in turn the memo is still the sole
    entry of the include-archived read and still stored: nothing removes a memo.
  - **DoD-12** — all four verbs succeed with `book_state=BookState.archived`.
- `backend/tests/routes/test_memos_state.py` — covers DoD-1..DoD-6, DoD-9, DoD-10, DoD-11, DoD-12 —
  the route half, driving the real `app.main.app` in-process through `http_client` (httpx
  `ASGITransport`, no network) with local `_seed_user` / `_seed_author` / `_seed_book` /
  `_seed_private_book` / `_add_co_author` / `_seed_memo` / `_auth_header` helpers and a real JWT.
  All four verbs are called with **no request body**. By item:
  - **DoD-1** — `POST …/deactivate` is 200 and the plain `GET` still lists the memo.
  - **DoD-2** — the 200 body is a `MemoResponse` with `active` false, string `id` / `book_id` and
    **no `user_id`**, `ordinal` 7 / `archived` / `body` unchanged; the following `GET` and the
    stored row agree.
  - **DoD-3** — `POST …/activate` on an inactive memo is 200 with `active` true and `archived` /
    `ordinal` / `body` unchanged.
  - **DoD-4** — deactivating the only active memo answers **200**, and the memo stays listed with
    `active` false.
  - **DoD-5** — after `POST …/archive` the memo is absent from the default `GET` and present,
    flagged `archived`, under `?include_archived=true`.
  - **DoD-6** — the same middle-of-three construction: archive then restore answers 200 with ordinal
    **4** (explicitly `!= 2`), and the `GET` reads ordinals `[1, 3, 4]` with the restored memo last.
  - **DoD-9** — four verbs × four unreachable ids: each **404** (a non-numeric id included — never a
    422), and the set of JSON-normalised response bodies has length **1**; neither foreign row was
    written.
  - **DoD-10** — four per-verb no-op specs, each asserting `200` and explicitly `!= 409` with the
    row unchanged (the restore-on-a-live-memo one now including `ordinal`), plus a fifth calling
    every verb twice and requiring 200 both times.
  - **DoD-11** — `DELETE` answers **405** on all six memo paths (collection, item and each of the
    four verb paths) with the memo surviving; no verb removes the memo from the include-archived
    read; and `app.openapi()["paths"]` carries no `delete` on any `/memos` path while all four verb
    paths exist as `post`.
  - **DoD-12** — the book's state set to `archived` via `books.update`, then all four verbs answer
    200 in sequence.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓ (service), DoD-8 ✓
  (service), DoD-9 ✓, DoD-10 ✓, DoD-11 ✓, DoD-12 ✓ (no `[manual/live]` items in this step).

#### Closed — the restore-on-a-live-memo ordinal (DoD-10) is now asserted (2026-09-15)

The previously-flagged non-assertion is **closed**. DoD-10 says a verb applied to a memo already in
that state returns "the row unchanged"; the restore contract says restore writes `ordinal = max + 1`.
The two readings collided only for **restore on a non-archived memo**. Resolution (orchestrator's
reading, reviewed by the red-gate verifier): that case is a **full no-op, `ordinal` included** —
DoD-10 carries no carve-out for restore, and the alternative would let an idempotent-looking verb
silently relocate a live memo in the author's list. DoD-6 continues to govern restore of a genuinely
archived memo (append last, `max + 1`).

Both DoD-10 restore specs were extended accordingly and renamed:
- `tests/services/test_memos_state.py::test_restore_on_a_live_memo_is_a_full_no_op__DoD10`
- `tests/routes/test_memos_state.py::test_restore_on_a_live_memo_answers_200_unchanged__DoD10`

Each now seeds **three** live memos at ordinals 1 / 2 / 3 and restores the **middle** one, so
"unchanged" (2) and "appended last" (4) give different answers and the assertion is meaningful; the
two bystanders are checked to still read 1 and 3 (each materialized with its own explicit `await`)
and the list still reads `[1, 2, 3]` in the original order. No prior assertion was removed or
weakened.

### Step 006 — tests (2026-09-15)

- `backend/tests/services/test_memo_prompt_composition.py` — **new** — covers DoD-1..DoD-9 — one spec
  module in three parts, bound to the step-006 frozen skeleton (`compose_system_prompt(base, mode,
  author, memos, chapter)`, `render_memos_section(memos) -> str | None`, `ComposedTurnPrompt(system,
  memos_section)`, `compose_turn_system_prompt(context) -> ComposedTurnPrompt`) plus step 001's `Memo`
  row and `db/memos.py` used only to seed and to spy. The composer and renderer halves are **pure** (no
  fixture); the turn half uses the `db` fixture with local `_seed_user` / `_seed_book` /
  `_add_co_author` / `_seed_server` / `_seed_chat` / `_seed_chapter` / `_seed_entry` / `_seed_mode` /
  `_seed_author_prompt` / `_seed_chapter_prompt` / `_seed_memo` helpers copied in idiom from
  `tests/services/test_chapter_prompt_composition.py`. The composition path is exercised **as a
  function** — `run_turn` is never driven, `chat_with_tools` is never called, **no network**. By item:
  - **DoD-1** — the renderer keeps every body it is handed, exactly once, with a **non-empty separator
    between two bodies** (the one fixed requirement: two memos cannot read as one); and a three-memo
    turn puts each body exactly once **between `### MEMOS` and `### CHAPTER`**.
  - **DoD-2** — the renderer renders **in the order given**: the rows are handed over with ordinals that
    disagree with the order given and the same rows are then handed over reversed, so a sorting or
    ranking renderer lands the wrong order in one of the two; and a turn whose memos were **created**
    3 / 1 / 2 composes them 1, 2, 3.
  - **DoD-3** — the excluded rows are asserted **beside an active one in the same composition**: the
    active body **is** present (in `system` and in `memos_section`) while the inactive and the archived
    bodies are in neither. A second spec pins the archived-**and**-active row as excluded too (archived
    wins; the two axes are independent).
  - **DoD-4** — the five-layer composition bound to the **whole string**
    (`### BASE` / `### MODE` / `### AUTHOR` / `### MEMOS` / `### CHAPTER`), the label pinned as exactly
    `MEMOS` and counted once with strict index ordering across all five, and the layer stripped before
    rendering exactly as every other layer is.
  - **DoD-5** — `inspect.signature` reads `["base", "mode", "author", "memos", "chapter"]` with
    `author` at index **2**, every default `None` and no `*args` / `**kwargs` catch-all; plus the
    call-site half — three positionals still bind base/mode/author, five bind the full order with memos
    fourth and chapter fifth.
  - **DoD-6** — four specs, each carrying a **positive control** so none is trivially green: the
    renderer skips blank-after-strip bodies (result byte-identical to rendering the survivors alone, and
    **not** `None`) and returns `None` only when nothing survives; the composer's blank/absent memos
    layer is byte-identical to omitting it **while a non-blank one demonstrably changes the output**;
    and two turn specs (all memos inactive-or-archived, and all active bodies blank) assert
    `memos_section is None` with the exact expected prompt, against a **second author on the same book
    with one active memo** whose turn does render `### MEMOS`.
  - **DoD-7** — parametrized over four cases — chapter subject with a mode prompt and with none, codex
    subject with a mode prompt and with none — each asserting the section is present with the body. No
    mode can be missing it.
  - **DoD-8** — a co-author's turn carries their own memo and neither the owner's memo on the same book
    nor their own memo on **another** book (checked in `system` and in `memos_section`); the reverse
    direction (the **owner** never receives a co-author's memos); and another book's memos alone render
    **no section** — they are not a fallback.
  - **DoD-9** — `db/memos.list_for_author` is wrapped by a counting delegate installed with
    `monkeypatch.setattr` on the module object `chat_turn` holds (the real function still runs, so the
    prompt is the real one): exactly **one** call across the turn, `### MEMOS` and each body appearing
    exactly once, and `f"### MEMOS\n{memos_section.strip()}" in system` — the value exposed for
    delegation **is** the one the composer rendered (context.md decision 7).
- `backend/tests/services/test_prompt_composition.py` — **rewritten in place** (its own 011/021 DoD
  numbering kept, not renumbered to step 006's):
  - `test_composes_all_four_layers_in_fixed_order__DoD1` → `test_composes_all_five_layers_in_fixed_order__DoD1`
    — five sentinels, each once, strictly ordered base < mode < author < memos < chapter.
  - `test_third_parameter_is_named_author__DoD3` — the parameter list is now
    `["base", "mode", "author", "memos", "chapter"]`; `book` is still absent and there is still no
    `**kwargs` catch-all (no alias for the inserted or the moved layer).
  - `test_third_positional_argument_is_the_author_layer__DoD3` — **the preserved fact**, strengthened
    rather than weakened: three positionals still bind base/mode/author (asserted against both the
    keyword form and the exact rendered string), and five positionals bind the full five-layer order.
  - Two `__DoD2` skip-rule specs gained a blank `memos=` argument, showing the
    empty-contributes-nothing rule extends to the new layer unchanged. Module docstring updated to five
    layers. Everything else in the file is untouched.
- `backend/tests/services/test_chapter_prompt_composition.py` — **rewritten in place** (its own 015
  step-013 DoD numbering kept):
  - Re-bound to the new return type: a local `_system(context)` helper returns
    `(await compose_turn_system_prompt(context)).system`, and every one of the file's call sites goes
    through it. **No assertion was weakened** — the existing DoD-2..DoD-6 specs seed no memos, so their
    exact-string expectations are unchanged and still exact.
  - `test_chapter_prompt_is_the_fourth_layer_in_order__DoD1` → `test_chapter_prompt_is_the_fifth_layer_in_order__DoD1`
    — now seeds an active memo, and pins the chapter layer **last**: the prompt starts with the exact
    base+mode+author prefix, **ends with** the exact `### CHAPTER` section, and carries exactly one
    `### MEMOS` section between them.
  - `test_chapter_layer_follows_base_mode_and_author__DoD1` → `test_chapter_layer_follows_base_mode_author_and_memos__DoD1`
    — the same strict index ordering, now across all five headings.
  - `test_composer_signature_is_unchanged__DoD7` → `test_composer_signature_keeps_author_third__DoD7`
    — reconciled with the five-parameter signature while pinning explicitly what 026 **preserves**:
    `base` at 0, `mode` at 1, `author` at **2**, all defaults `None`, no catch-all.
  - `test_non_chapter_subject_composes_no_fourth_layer__DoD4` → `test_non_chapter_subject_composes_no_fifth_layer__DoD4`
    — name only: the chapter layer this regression clause pins as absent is now the **fifth**, not the
    fourth. Its assertions are byte-for-byte unchanged.
  - `test_composer_skip_rule_is_unchanged__DoD7` gained a blank `memos=` argument;
    `test_composer_behaviour_is_unchanged__DoD7` is untouched (the four pre-existing layers compose
    exactly as before when memos is absent). A local `_seed_memo` helper and the `Memo` / `db.memos`
    imports were added.
  - Post-verify cosmetic sweep (2026-09-15): the remaining section comments that still called the
    chapter layer the *fourth* now say **fifth**, and the expected-string builder note lists
    `BASE / MODE / AUTHOR / MEMOS / CHAPTER`. Comments, docstrings and one test name only — **no
    assertion added, removed or altered** in either file.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓ (no
  `[manual/live]` items in this step).
- **Deliberately not asserted**, because the spec leaves it to the coder: the separator between two
  memo bodies (only "two memos cannot read as one" is fixed) and any per-memo decoration. Multi-memo
  sections are therefore pinned by presence, count, order and position — never by exact bytes.
- **Blast radius checked, none found:** `tests/services/test_chat_turn.py` and
  `tests/services/test_assistant_runtime.py` also call `compose_system_prompt`, but every call there is
  keyword-only and seeds no memos, so the inserted fourth parameter moves no argument and those specs
  are unaffected. No test file outside this step's list needed an edit.

### Step 007 — tests (2026-09-15)

- `backend/tests/services/test_memo_delegation.py` — **new** — covers DoD-1, DoD-2, DoD-3, DoD-4,
  DoD-5, DoD-6, DoD-7 — the carried `MEMOS` section reaching a delegated sub-agent's nested `system`.
  Bound to the frozen Step 007 record (`ParentTurn.memos_section`, unchanged `build_delegation_tools` /
  `run_delegation`) plus Step 006's `ComposedTurnPrompt` and the five-layer `compose_system_prompt`.
  The nested-call harness is `test_subagent_delegation.py`'s: `create_model_client` is monkeypatched
  with a factory yielding a fake async-context-manager client recording `chat_with_tools`'s `system`
  kwarg — **no network**. Rows seeded through `db/` against the `db` fixture.
  - Expected child string is **never hand-assembled**: a local `_expected_child(prompt, section)` calls
    `compose_system_prompt(memos=section)` and joins it to the sub-agent's prompt with a blank line,
    returning the prompt verbatim when the composer yields `""` — the frozen table in the skeleton
    record. So a spec cannot claim the child's section differs in shape from the parent's.
  - **DoD-1** — three memos created 3/1/2 (insertion order disagreeing with ordinal order); the section
    the parent's own `compose_turn_system_prompt` produced is carried on `ParentTurn`; each body appears
    in the nested `system` exactly once and in ascending ordinal order, with one `### MEMOS`.
  - **DoD-2** — staged against a parent turn that demonstrably carries all five layers (mode, author and
    chapter prompts seeded and their headings asserted present in the parent's prompt), so the child's
    exclusions are an exclusion and not an empty world: the nested `system` equals prompt + section,
    carries none of `BASE_SYSTEM_PROMPT` / mode / author / chapter sentinel text, none of their
    headings, and `count("###") == 1`.
  - **DoD-3** — inactive, archived, and archived-but-active rows alongside one active row: asserted as
    the **identity of the section** (`f"### MEMOS\n{memos_section.strip()}"` appears in both the
    parent's `system` and the child's) rather than by re-deriving the expected text; the active body is
    present in both and the excluded ones in neither.
  - **DoD-4** — parametrized over three carriers of "no section" (the value a memo-less turn composes,
    an explicit `None`, and a `ParentTurn` constructed **without** the field): the nested `system` is
    `== SUBAGENT_PROMPT` exactly — no empty section, no stray separator, no trailing blank line.
  - **DoD-5** — two forms, neither a source grep (the module legitimately carries `memos_section` and
    discusses memos in prose, per the skeleton's token note): (a) a structural check that no name bound
    in `subagent_delegation`'s namespace is a module named `app.db.memos` or a symbol whose
    `__module__` is `app.db.memos`, and that `render_memos_section` is not an attribute of it; (b) a
    counting wrapper installed on `db/memos.list_for_author` **after** the parent's composition — a
    whole delegation performs **zero** reads, with the carried memo still reaching the child (so the
    zero is not the zero of a delegation that never ran) and a positive control proving the counter
    registers a real composition's one read.
  - **DoD-6** — a memo row is created through `db/` **between** the parent's composition and the
    delegated call: the child's `system` still equals prompt + the parent's section, the mid-turn body
    is in neither prompt nor section, and a positive control (a later composition does carry it) proves
    the row is real and a second read would have picked it up.
  - **DoD-7** — parametrized 2×2 (`LLMError` / `RuntimeError`) × (section present / absent): the tool
    returns a non-empty string that is not the nested answer, and never raises.
- `backend/tests/services/test_subagent_delegation.py` — **rewritten in place**, one test (its own
  013-step-008 DoD numbering kept, not renumbered to step 007's):
  - `test_nested_system_is_the_subagent_prompt_alone__DoD5` →
    `test_nested_system_is_the_subagent_prompt_plus_memos_only__DoD5`. Two halves in one test: with no
    section carried the nested `system` is still `"SUBAGENT_RULES_ONLY"` verbatim (the old literal,
    preserved as 026 DoD-4), and with `memos_section="REMEMBER_THIS_MEMO"` it is that prompt + a blank
    line + `compose_system_prompt(memos=...)`. The **surviving half of the original intent** — no base,
    mode, author or chapter layer threads through — is asserted over **both** nested systems (026
    DoD-2). Module docstring updated with `ParentTurn`'s two trailing fields. Nothing else in the file
    is touched.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓ (no `[manual/live]` items in
  this step).
- **Deliberately not asserted**, because the spec leaves it to the coder: the separator *between two
  memo bodies* (step 006's rule) and any per-memo decoration — multi-memo nested sections are pinned by
  presence, count and order. The single blank-line join between the sub-agent's prompt and the section
  **is** asserted, because the skeleton record freezes it (`_DELEGATED_SECTION_JOIN`, the composer's own
  section join) as the one byte this module chooses.

### Step 008 — tests (2026-09-15)

- `backend/tests/services/test_memo_tools.py` — **new** — covers DoD-1, DoD-2, DoD-3, DoD-4, DoD-5,
  DoD-6, DoD-8, DoD-9, DoD-10 (the `ToolContext` / args-schema / binder half), DoD-12. Bound to the
  frozen Step 008 record (`CreateMemoArgs`, `create_memo(context, body) -> str`, `bind_create_memo`)
  plus the unchanged `ToolContext` / `TOOL_REGISTRY` / `BASE_TOOL_NAMES` / `allowed_tool_names`
  signatures. The `ToolContext` is built directly with a constructed `BookAccess` and the tool is
  invoked as a plain function — **no network, no live model**; rows go through `db/` against the `db`
  fixture. Local `_seed_user` / `_seed_book` / `_seed_memo` / `_seed_entry` / `_seed_mode` /
  `_seed_mode_tool` / `_access` / `_ctx` helpers, copied in idiom from `test_memos.py` and
  `test_chapter_tools.py` (no shared factory module exists).
  - **DoD-1** — one call, one row for `context.access.user_id` in `context.book_id`, visible through
    `memo_service.list_memos`; a second member of the same book who did not run the turn has nothing.
  - **DoD-2** — the created row is `active=True`, `archived=False`.
  - **DoD-3** — two halves: it lands last at ordinal 3 behind existing 1 and 2; and, in two
    identically-seeded books *including an archived gap* (the case that makes the rule non-obvious),
    the tool's ordinal equals a manual `memo_service.create_memo`'s — the expression of "reaches the
    append rule **through the memo service** rather than recomputing it".
  - **DoD-4** — parametrized over the three subject shapes (`NO_SUBJECT`, a `memos`-kind subject, an
    unrelated codex-entry subject), plus a dedicated cross-book test: with a subject whose entry lives
    in a *different* book, the memo lands in the route's book and the subject's book stays empty.
  - **DoD-5** — *preserved-behaviour guard*. A mode seeded without the row does not resolve
    `create_memo` (neither in `allowed_tool_names` nor through `resolve_tools`); the same mode **with**
    the row does, so the guard cannot pass vacuously.
  - **DoD-6** — `BASE_TOOL_NAMES` is exactly `{web_search, create_memo}` (membership, not order);
    `allowed_tool_names(None)` carries the tool; and each mode-less subject the clause names
    (no subject / memos / book-state / chapters / variants / chats) determines no mode and lands on
    that allowlist.
  - **DoD-8** — four never-raises paths, each asserted by **shape and consequence, never by wording**
    (the skeleton declares the message constants off-limits): absent `access`, a non-member caller
    (`reader` and `none`), a service-level `MemoError` (the service is monkeypatched so the refusal is
    unambiguously the service's), and an unexpected `RuntimeError`. Each answers a non-blank `str` and
    leaves **no memo row**. One further test asserts only that a confirmation and a refusal are not the
    same string — the minimum that makes a refusal readable.
  - **DoD-9** — the copied-chain catcher: the tool **succeeds** on `BookState.archived`, succeeds in
    `CollaborationMode.proposal`, and succeeds with both at once — the two links `chapter_tools.py`'s
    chain has and this one must not.
  - **DoD-10** (this file's half) — `ToolContext`'s field names are asserted as the **named set of
    seven** it had before this step, not as a count copied from `assistant-config.md` /
    `quick-reference.md`, both of which still say "six" (stale — see Notes & Issues below).
    `CreateMemoArgs` is one required `body`; `bind_create_memo(ctx)` leaves exactly `{"body"}` free.
  - **DoD-12** — *preserved-behaviour guard*: the schema module declares exactly the seven `*Frame`
    payloads `assistant-runtime.md` names (scanned by `__module__`, so an import cannot false-positive);
    `ToolCallFrame` / `ToolResultFrame` / `CanvasFrame` field sets are unwidened; and the tool emits
    nothing onto a recording emitter on the success path or the refusal path.
- `backend/tests/services/test_tools.py` — **added to**; no existing assertion changed in strength.
  - New `test_create_memo_registry_entry__026_DoD10` — the entry declares name `create_memo`, group
    `"book"`, `args_schema=CreateMemoArgs`, `binder=bind_create_memo` and **no** plain callable; the
    description is asserted non-blank only (wording is the coder's).
  - Two **forced widenings of pre-existing exact sets**, in the file's established precedent (fast/007,
    025): `"create_memo"` added to the pinned registry-name set, and the group test's
    `len(TOOL_REGISTRY)` 18 → 19. That test is renamed
    `test_every_registry_entry_declares_a_valid_group__025_DoD6__026_DoD10` because it now also carries
    DoD-10's "every registry entry still declares a valid group" and "the valid-group set is not
    widened". Both widenings are already satisfied by the skeleton's registry entry.
- `backend/tests/db/test_mode_tools_seed.py` — **added to**; no existing assertion changed in strength.
  - `MEMO_TOOL = "create_memo"` appended to **all five** `EXPECTED_TOOLS` tuples — the same two-part
    widening fast/007 and 025 made, so the file's pre-existing exact-set DoD-4 tests now also fail until
    the coder seeds it.
  - **DoD-7** — three tests: `DEFAULT_MODE_TOOL_NAMES` names the tool once for each of the five modes;
    a fresh install's seeded rows carry it for all five; and an **existing install is not backfilled** —
    a mode pre-loaded with its own rows is left entirely untouched by the seed (no top-up, not one row),
    while the four mode-less-of-rows modes seed normally. That is `context.md` → decision 10 stated as a
    test rather than as a defect.
  - **DoD-11** — the guidance is asserted in `DEFAULT_MODE_SYSTEM_PROMPTS` (parametrized over the five
    keys) **and** in the rows a fresh `seed_default_modes()` writes — "ships in the *seeded* prompts" is
    the clause. Asserted by **substance, tolerant of wording**: the prompt speaks of memos, ties
    creation to the author's own request, and carries the restrictive/never-unasked half. No sentence is
    pinned, and nothing claims a model obeys it — US-130 is prompt-enforced and inherits US-121.AC-3's
    caveat.
    - **Repaired after the first verify run (Fault: TEST, `[write-chapter]` + the seeded-rows test).**
      Two independent defects, both in the check and neither in the prompts: (a) it matched a **closed
      list of accepted phrasings**, which is an assertion the DoD does not make and one a blind coder
      cannot satisfy — they cannot know which turns of phrase the list admits, so a good sentence in an
      unlisted grammatical form read as a failure. It now keys on word **stems** matched on word
      boundaries (`\bask` covers asks / asked / asking but not "task"; `\bnot\b` is the negation, not
      "note"). (b) It scanned the **whole** prompt, so on four modes it was partly satisfied by
      pre-existing prose about asking and not acting unprompted that has nothing to do with memos. The
      scan is now scoped to the memo guidance itself — each memo-mentioning sentence plus its two
      neighbours, wide enough for guidance split across sentences, narrow enough that chapter or codex
      prose cannot carry the clause. Neither repair weakens it: both halves of the substance are still
      required, and "memo is mentioned at all" is still not sufficient.
    - **Tightened again after the re-verify PASS, on the verifier's advisory.** Counterfactual prompts
      — a memo mention stripped of its guidance — were correctly rejected on four modes but *accepted*
      on `write-chapter`, whose codex-creation rule packs a restriction word and a request stem into the
      sentence immediately before the memo paragraph, so the neighbour window let adjacent codex prose
      satisfy the clause. Not a false green (the shipped prompt passes on its own words) but a latent
      hole: a future prompt could drop its memo guidance unnoticed, which is the vacuity DoD-11 exists
      to prevent. **The rule now anchors one half:** both halves must still appear in the window, *and*
      at least one of them must appear in a sentence that actually **mentions a memo**. The window is
      deliberately **not** narrowed — narrowing would re-break guidance legitimately split across
      sentences ("Never create one unasked. Create a memo only when the author asks."), which is why
      the window exists; the anchor lets the memo sentence carry one half and a neighbour the other.
      Also widened the restriction vocabulary by `solely` / `exclusively` (the "only" family a coder may
      reach for), which costs nothing in precision.
    - **Third and final correction — the sentence window and its token anchor were replaced by a
      PARAGRAPH scope** (re-confirm returned FAIL / Fault TEST on the anchor). The anchor required one
      half to sit in a sentence literally containing "memo", which DoD-11 does not ask for, and it
      rejected the **default tool-paragraph shape** the neighbouring tool paragraphs already use: first
      sentence names and defines the tool, second states the rule with a **pronoun** referring back
      ("`create_memo` saves a standing memo… Call it only when they have directly asked you to note
      something down"). Four spec-conformant phrasings failed that way — the same "a blind coder cannot
      satisfy this, and no failure message could tell them the fix is to repeat a noun" fault as the
      original phrase list, in a different costume. The anchor was also still too loose: a memo
      paragraph carrying only the *request* half borrowed the restriction half from the adjacent
      codex-creation rule. **Both halves are now required in the blank-line-delimited paragraph that
      mentions the memo** — the unit a tool is actually documented in. It dominates the window on every
      axis tested: all five shipped prompts pass, every guidance-free memo mention is rejected, the four
      pronoun forms pass, guidance split across sentences still passes, and the request-half-only
      borrowing the window admitted is now rejected. Everything the earlier tightening got right is
      kept: both halves required, substance over wording, and the `solely` / `exclusively` patterns.
      Residual, stated rather than patched around: a prompt written with **no blank line at all** is one
      paragraph, so its scope is the whole prompt. None of the five is written that way, and inventing a
      further rule for a shape that does not exist would be the third over-fit of this clause.
- **Two files outside step 008's Test files list, re-bound on the orchestrator's call** (the same call
  made at step 001 for the eight `test_data_domain_*` modules, and for the same reason: each pinned an
  exact set that a DoD item *mandates* changing, so leaving them red would report two failures that are
  nobody's fault and would bury a real one). Both edits are mechanical re-bindings — the expected set
  widens and nothing else; no assertion deleted, relaxed, re-subjected or renumbered.
  - `backend/tests/services/test_assistant_runtime.py` —
    `test_no_mode_allows_exactly_base_tool_names__DoD11`, one literal:
    `set(BASE_TOOL_NAMES) == {"web_search"}` → `{"web_search", "create_memo"}` (026 DoD-6). The two
    lines below it (`set(fake.call["tools"].keys()) == set(BASE_TOOL_NAMES)` and the paired
    `tools_definitions` length) compare against `BASE_TOOL_NAMES` **itself**, and the test's
    `_widen_registry` helper **appends** to `TOOL_REGISTRY` rather than replacing it, so the
    `create_memo` entry and its binder survive and those two need no edit — the same equality
    `test_codex_canvas_tools.py` already relies on for a no-mode turn. That test's own subject — a null
    mode is the base allowlist and **not** the whole registry — is untouched.
  - `backend/tests/services/test_chapter_tools.py` — `WRITE_CHAPTER_DEFAULT_TOOLS` gains
    `"create_memo"` (026 DoD-7 seeds it into all five modes). Twelve names become thirteen; the derived
    `len(...)` / exact-set / resolve-for-the-turn assertions in
    `test_open_chapter_turn_is_offered_the_seeded_four__DoD12` all move with the set and stay exact.
  - `backend/tests/services/test_chapter_turn_context.py` —
    `test_planned_and_closed_chapters_get_the_base_allowlist__DoD8`, added to the widened scope after
    the first verify run: the third file to pin the base set by literal. `names == ("web_search",)` →
    `set(names) == {"web_search", "create_memo"}` plus `len(names) == 2`. **Membership rather than
    tuple order**, because DoD-6 fixes the base set's *contents* and leaves its order to the coder; the
    adjacent `names == BASE_TOOL_NAMES` still pins the value exactly, and the two wrong answers the
    test rules out (not empty, not the whole registry) are untouched. DoD-6 names a `planned` or
    `closed` chapter as a mode-less surface that must resolve the tool, so the old literal asserted a
    fact the step deliberately changes.
  - None of the three files is named by `008.create-memo-tool.md`, so this bullet is the only record of
    the trail.
  - **Not done, deliberately:** folding the three files' expected base set into one shared constant.
    It cannot be a tidy-up — backend tests have no shared constants module (`context.md` → "Testing
    facts": *"there is no shared factory module"*; `conftest.py` supplies fixtures only), so it would
    mean inventing a cross-suite import convention this feature has no mandate for, in three files two
    of which are outside the step. The recurrence is real; it wants its own change.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓, DoD-10 ✓,
  DoD-11 ✓, DoD-12 ✓ (no `[manual/live]` items in this step).
- **Expected at the red gate** (from the skeleton's own report, not from reading code): DoD-5, DoD-10
  and DoD-12 are green by construction — DoD-10's registry entry is skeleton-written, and DoD-5 / DoD-12
  are preserved-behaviour clauses true before this step. They are written as honest regression guards
  and were deliberately **not** contorted to force a red. DoD-1, -2, -3, -4, -8, -9 go red on the stub's
  `NotImplementedError`; DoD-6, -7, -11 go red on the three modules the skeleton left untouched.
- **Deliberately not asserted**: the wording of `_NO_ACCESS_MESSAGE` / `_REFUSED_MESSAGE` /
  `_CREATE_FAILED_MESSAGE` / `_CREATED_MESSAGE` and of the registry entry's description (the skeleton
  record puts all five outside the test surface); the *order* of `BASE_TOOL_NAMES`; and any claim that a
  model honours the US-130 guidance.

### Step 009 — tests (2026-09-15)

Frontend step. All four files bind to the Step 009 frozen interface above; `globals: false`, so every
spec imports its primitives from `"vitest"` explicitly. Run by `cd frontend && npm test`; typechecked
only by `cd frontend && npm run test:types`.

- `frontend/tests/work/memosApi.test.ts` — **new** — covers **DoD-8**. Mocks `../../src/api/client`
  module-factory form with an `importOriginal` spread (never `fetch`, never the memos module itself),
  so the url / method / body / signal handed to `request<T>` is the observable contract and the **real**
  `ApiError` class survives for the propagation case. Idiom copied verbatim from the sibling api spec
  `frontend/tests/user/chaptersApi.test.ts` (`onlyCall()`, `methodOf()`, snowflake-string id fixtures
  beyond 2^53).
  - Method + path per function, from `context.md` → "The wire contract": the list `GET`, the create
    `POST`, the `PUT …/memos/order` bulk path (asserted as **not** a `/{memo_id}` path), the
    `PUT …/memos/{memo_id}` body update, and the four `POST …/memos/{memo_id}/<verb>` state calls,
    parametrized over `activate` / `deactivate` / `archive` / `restore`.
  - **Ids as strings** — every id fixture is a snowflake string past 2^53 and must reach the url
    verbatim, which no `Number(...)` round-trip survives.
  - **The include-archived flag is sent on the list call** — both `?include_archived=false` and
    `?include_archived=true`, so a hard-coded value fails.
  - **The envelope is unwrapped on the list call only** — `listMemos` resolves to the bare array
    (including the empty-list case), and `reorderMemos` resolves to `{ items: … }` and is asserted
    **not** to be an array, the frozen `api/chapters.ts:reorderChapters` shape.
  - The four state verbs send **no** request body; `signal?` is the trailing argument of every function
    and is optional; an `ApiError` from the wrapper propagates unswallowed (list and update both).
- `frontend/tests/work/navItems.test.ts` — **added to** — covers **DoD-1, DoD-2, DoD-3**. Items are
  looked up by their author-facing **label**, the file's existing idiom (the skeleton does not freeze
  the `path` string form).
  - **DoD-1** — Memos is the **eighth** entry, last, and sits immediately after Chats; the first seven
    are unchanged in label and order (pinned against a `LEGACY_LABELS` constant kept separately for
    exactly that clause).
  - **DoD-2** — `paneTarget` is `"content"` (an ordinary router link, no pane-control exception), and
    `workNavHref` builds `/bk-1/memos` — and `/other-book/memos`, so the href tracks the book id.
  - **DoD-3** — active for the memos path; **not** active for any of the seven siblings' paths; and no
    sibling is active for the memos path (both directions, since one-way would pass on a matcher that
    lights everything up).
  - **Stale assertions repaired** (authorized in the brief; this file is in the step's Test files
    list): the 010-era `toHaveLength(7)` → `8` and the seven-label `EXPECTED_LABELS` → eight, with
    `Memos: "/bk-1/memos"` added to `EXPECTED_HREFS` so the pre-existing DoD-2 loop covers it too. No
    assertion weakened; the two amended titles now cite both features' DoD ids.
- `frontend/tests/work/subject.test.ts` — **added to** — covers **DoD-5, DoD-6, DoD-7**. A pure unit
  spec; no router, no render.
  - **DoD-5** — two exhaustive `Record<Union, true>` tables, one over `src/work/subject`'s
    `SubjectKind` and one over `src/types/chats`'s twin. A missing **or** extra member fails to compile
    under `npm run test:types`; at runtime the two key sets are compared sorted and pinned at eleven,
    and three cross-assignments pin the unions as **mutually assignable** — i.e. equal, not merely
    overlapping.
  - **DoD-6** — the memos kind answers `{ editable: "whole", readOnlyReason: null }`, and the verdict is
    asserted **constant** across four differently-populated `LoadedSubject`s (bare, with an `entityId`,
    with a `chapterState`, with `codexArchived`) — the "branch decides nothing" clause. Second half:
    all seven existing list kinds still answer `"none"` with the read-only reason **verbatim**
    (`009.context.md`), plus a guard that the chapter / codex / book-state verdicts are untouched.
  - **DoD-7** — `Record<EditableRegion, true>` names exactly the six members (a seventh would fail to
    compile) and `Record<WriteRegion, true>` exactly the two; `checkWritePermission` is re-asserted
    unchanged for the four chapter states, both codex-entry shapes, both Book-state regions and every
    existing read-only list kind. Nothing asserts a memos **write** verdict — DoD-7 scopes the clause to
    existing kinds.
- `frontend/tests/work/routes.test.tsx` — **added to** — covers **DoD-4**. Renders through
  `renderWithProviders` with a basename-stripped `route`, asserting by role and accessible name, scoped
  to the `main` landmark (the navigator also carries a "Memos" link and the chat pane renders beside
  the content).
  - `/bk-1/memos` resolves inside the workspace shell and renders the memos page — the `Memos` heading
    plus this step's owner label naming step 010 — and the not-found page's back-to-bookshelf anchor
    (href `"/"`) is **absent** from the content pane, so the catch-all did not answer.
  - `/bk-1/memos/m-1` and `/bk-1/memos/new` each fall through to the **nested** in-pane not-found page
    (the `href="/"` anchor is present, the Memos heading absent) — there is no item route and no create
    route (`context.md` → decision 12).
  - **Harness only**: five `api/` modules (`books`, `chats`, `codex`, `flags`, `continuity`) are mocked
    module-factory form, copied verbatim from the sibling spec `tests/work/subjectRoutes.test.tsx`,
    because mounting any `/:bookId/…` route brings the shell's own loads up. Nothing asserts on them,
    and the pre-existing entry-root test is unchanged. `api/memos` is **not** mocked — this step's
    placeholder page makes no call.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓,
  DoD-9 [manual/live, no test].
- **Expected at the red gate** (from the skeleton's own report, not from reading code): **DoD-8 is the
  only genuinely red clause** — all eight api bodies are stubs that throw. DoD-1..DoD-7 are green by
  construction: the nav row, the route, the placeholder page, the two union widenings and the subject
  branch are all **written in full** by the skeleton (there is nothing to leave unimplemented in a type,
  a table row or a placeholder, and the placeholder page *is* this step's deliverable). They are written
  as honest regression guards and were deliberately **not** contorted to force a red.
- **Scope-widening trail — one new test file.** `frontend/tests/work/memosApi.test.ts` is **not** in
  `009.memos-api-and-navigator.md`'s Test files list, which names only the three existing `tests/work/`
  specs. DoD-8 nonetheless requires an api-module spec and `009.context.md` describes it explicitly
  ("an api-module spec mocks `../../src/api/client` (not `fetch`) and asserts the url, method and body
  each function hands to `request<T>`"), so the omission is a gap in the list rather than an intent to
  skip the clause. Created **on the orchestrator's explicit authorization**.
  - **Placement follows the repo's AREA convention, deliberately — no new `tests/api/` directory.**
    Specs are grouped by area, not by layer: an api spec lives in its area folder under a
    `<resource>Api.test.ts` name (`tests/user/chaptersApi.test.ts`,
    `tests/admin/assistantConfigApi.test.ts`). Memos are a work-area resource, so the spec sits in
    `tests/work/` beside the other three step-009 specs. A top-level `tests/api/` was drafted first and
    **rejected**: it would have been this feature inventing a fourth organizing principle for one file.
    Recorded here so nobody re-derives the question later. The relative import depth is identical under
    either placement (`../../src/api/client`), so nothing in the file changed beyond the header note.
- **Two further files outside step 009's Test files list, re-bound on the orchestrator's call** after
  the red gate (the same call made at steps 001 and 008, and for the same reason: each pinned an exact
  count that **DoD-1 mandates changing**, so leaving them red would report failures that are nobody's
  fault and would bury a real one). Both edits are mechanical widenings — the expected count and label
  list move by one and nothing else; no assertion deleted, relaxed, re-subjected or renumbered, and
  each file keeps its own earlier-feature `__DoD<N>` numbering.
  - `frontend/tests/work/WorkNavigator.test.tsx` (023.chat-ux-revision DoD-8) —
    `renders all seven entries as links in UC-090 order` → `all eight … — Chats and Memos included`,
    `toHaveLength(7)` → `8`, `NAV_LABELS` gains `"Memos"` eighth and `NAV_HREFS` gains
    `Memos: "/bk-1/memos"` so the sibling `each entry is an in-SPA router link…` test (which loops
    `NAV_LABELS` against `NAV_HREFS`) covers the new entry instead of comparing against `undefined`.
  - `frontend/tests/work/WorkNavigatorRail.test.tsx` (fast/005.workspace-layout DoD-8 · DoD-9) — the
    same `NAV_LABELS` / `NAV_HREFS` widening, plus two count literals: the expanded
    `the seven router-link entries` → `eight` (`toHaveLength(7)` → `8`) and the collapsed
    `exactly seven links are findable by accessible name` → `exactly eight` (`toHaveLength(7)` → `8`).
    Everything the file says about THE RAIL ITSELF — accessible-name reachability while collapsed,
    href parity between the two modes, the `classNames` wiring — is untouched.
  - Test-name prose was updated alongside each literal so no name contradicts its own assertion (the
    step-006 precedent); the header docstrings carry a one-line note naming 026 DoD-1 as the cause.
  - **Not touched, deliberately:** `frontend/src/work/components/shell/WorkNavigator.tsx`'s docstring
    still says "seven". It is a **source** file — the coder's, not the test-coder's — and the step-009
    skeleton record already flags it under `## Notes & Issues`.
- **Deliberately not asserted**: the exact `path` string stored on the nav entry (looked up by label
  instead — the skeleton does not freeze its form); which `@tabler/icons-react` icon the entry carries
  (the skeleton allows a better fit than `IconNotes`); the placeholder page's exact owner sentence
  (matched as `/step 010/i`, since the step file pins only "naming step 010 as its owner"); the memos
  kind's `resolveSubjectPaneTarget` answer and its `checkWritePermission` verdict (neither is a DoD-6 /
  DoD-7 clause); and anything about the visual half of DoD-9.

### Step 010 — tests (2026-09-15)

Frontend step. Both files bind to the Step 010 frozen interface above (and step 009's DTOs / api
module); `globals: false`, so every spec imports its primitives from `"vitest"` explicitly. Run by
`cd frontend && npm test`; typechecked only by `cd frontend && npm run test:types`.

- `frontend/tests/work/MemosListPage.test.tsx` — **new** — covers **DoD-1 … DoD-16** (all sixteen are
  `[test]`; the step has no `[manual/live]` item). **18 `it` blocks in 6 `describe` groups**, each title
  citing its DoD id and product id. The block count exceeds the clause count because **two clauses carry
  two cases each — not because any clause is uncovered**: **DoD-5** splits into the focus-loss save and
  the identical-draft negative (a draft equal to the server's value must save nothing), and **DoD-16**
  into the failed save and the failed toggle. Every other clause is one block. The page is mounted under its own `/:bookId/memos` route (the
  `ChatsListPage` precedent) so nothing but the page under test is on screen; routes are
  basename-stripped. `../../src/api/memos` is mocked **wholesale**, module-factory form, never `fetch`;
  `ApiError` is the **real** class from `../../src/api/client`. Queries are **by role and accessible
  name only — never a test id**.
  - **Bound to the frozen accessible-name scheme**, which is the spec's only handle on an icon control:
    `Memo <position> body` (`textbox`), `Memo <position> active` (`switch`, `checked` = `memo.active`),
    `Memo <position> is off` (marker aria-label), `Archive memo <position>` / `Restore memo <position>`
    (`button`), `Memo <position> error` (`alert`), plus page-level `Memos` / `New memo` /
    `Show archived`. **Position is the 1-based index in the list the row is rendered in**, and the
    fixtures make that load-bearing: ordinals carry a **gap** (`m-2` is ordinal 4 at working position 2,
    the archived `m-9` is ordinal 3), so a name derived from `memo.ordinal` fails every row query.
  - **The server double is a real round trip**: a mutable `serverMemos` list answers all eight api
    functions — create appends an empty row with the next ordinal (handed back **first** in the array,
    so "last" can only be satisfied by ordering on `ordinal`), restore re-appends with a fresh highest
    ordinal, and `updateMemoBody` returns a **normalised** body (a ` [server]` suffix) so "the row shows
    what the server returned" is observable rather than indistinguishable from the local draft.
  - **DoD-1** create appends last (working position 3, body order pinned); **DoD-2** the created row's
    body field `toHaveFocus()` with no further action; **DoD-3** it renders `toBeChecked()` with no off
    marker; **DoD-4** it is empty (`value === ""`), addressable anyway (body-independent naming),
    immediately typeable via bare `user.keyboard` with no intervening click, the create payload is
    exactly `{ body: "" }`, and **no `alert` and no `Memo 3 error` exists** — an empty body is never a
    failure.
  - **DoD-5** two tests: typing + `user.tab()` calls `updateMemoBody(BOOK_ID, "m-1", { body: … })`
    **once** (and **not** on a keystroke), after which the field shows the server's normalised value,
    not the draft; paired with the negative — a draft made dirty then reverted by hand saves **nothing**.
  - **DoD-6** absence asserted across four states so the clause cannot pass vacuously: after load
    (with the rendered body list pinned first, proving the list is non-empty), mid-edit (field focused),
    with a **dirty** draft, and with the archived section revealed —
    `queryAllByRole("button", { name: /save/i })` is empty each time.
  - **DoD-7** switching off calls `deactivateMemo` for that memo and the row **stays** in the working
    list, in place; **DoD-8** a loaded-off row is `not.toBeChecked()` and carries the `Memo 2 is off`
    marker while the active sibling carries neither — the state travels on role/name, not styling;
    **DoD-9** the same stable name addresses the row across the axis, `activateMemo` is called and the
    switch is checked with the marker gone; **DoD-10** the **only** active memo switches off with no
    `alert`, no row error, **`activateMemo` never called** (nothing restored behind the author) and both
    rows still rendered.
  - **DoD-11** archive calls `archiveMemo` and the row leaves the working list (the survivor renumbers
    to position 1 — asserted by body value, not by name, precisely because positions renumber);
    **DoD-12** revealing the archived section (hidden by default) exposes `Restore memo 1` — the
    archived section numbers from 1 in its own right — and restoring returns the row to the working
    list **last**, proven by `Archive memo 3` existing, the full body order, and **no** restore control
    remaining; **DoD-13** `Archive memo 1` / `Archive memo 2` both exist while
    `/delete|remove|trash|discard/i` matches **zero** buttons, in both the default and the
    archived-revealed view.
  - **DoD-14** `listMemos` is called **exactly once**, with `BOOK_ID` and the include-archived flag
    **`true`**, the archived row is filtered out client-side by default, and toggling **on then off**
    leaves the call count at 1.
  - **DoD-15** no user id crosses the wire: the list call is `(BOOK_ID, boolean, undefined|AbortSignal)`
    with `length <= 3`; `updateMemoBody`'s and `createMemo`'s payload key sets are **exactly**
    `["body"]`; a state verb is `(BOOK_ID, memoId, undefined|AbortSignal)` with `length <= 3`. The only
    identity anywhere is the book from the URL.
  - **DoD-16** two tests, one per write kind: a rejected `updateMemoBody` / `deactivateMemo`
    (real `ApiError(500|403, …)`) surfaces `getByRole("alert", { name: "Memo 1 error" })` carrying the
    message, **no** `Memo 2 error` is raised against the innocent row, and the row falls back to
    **server truth** — the body field shows the server's value (the optimistic draft dropped) and the
    switch stays checked with no off marker. The list survives both failures.
- `frontend/tests/work/routes.test.tsx` — **added to (harness only)** — see the scope-widening trail
  below. **No assertion in the file changed.**
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓,
  DoD-10 ✓, DoD-11 ✓, DoD-12 ✓, DoD-13 ✓, DoD-14 ✓, DoD-15 ✓, DoD-16 ✓.
- **Expected at the red gate** (from the skeleton's own report, not from reading code): **all sixteen
  clauses are genuinely red** — the skeleton stubs both component bodies and every effect and computed,
  so any spec that renders the page throws at `render()`. Nothing here is green by construction.
- **Scope-widening trail — one harness repair outside step 010's Test files list.**
  `frontend/tests/work/routes.test.tsx` (step 009's DoD-4 spec) mocked five `api/` modules but **not
  `api/memos`**, which was correct against step 009's placeholder page: it called nothing. From step 010
  on the memos page is real and loads on mount, so `/bk-1/memos` would reach the genuine
  `memosApi.listMemos` → `client.request` → `fetch`. `client.ts` wraps only **non-2xx responses** into
  `ApiError` and never a transport failure, so jsdom's fetch rejection would be **rethrown** by the
  page's loader as an unhandled rejection instead of landing in its error field — a failure with no
  owner. Repaired **on the orchestrator's explicit authorization**, in the same module-factory idiom as
  the five existing mocks: a sixth `vi.mock("../../src/api/memos", …)` enumerating all eight exports,
  plus `vi.mocked(memosApi.listMemos).mockResolvedValue([])` in the existing `beforeEach` (an empty list
  is enough — nothing in that file asserts on memo content). **No assertion added, removed, relaxed or
  renumbered**; the file's DoD-4 case is red only because the stubs throw, and clears when the coder
  fills the render (the skeleton record says exactly this).
- **Scope-widening trail, second entry — one DELETION (not a widening), after the verify run.** The
  verify run returned **FAIL / Fault TEST** on a single stale assertion in
  `frontend/tests/work/routes.test.tsx`: all sixteen of step 010's own clauses passed, and the only
  failure was step 009's `/:bookId/memos` case asserting `getByText(/step 010/i)` — the **transitional
  marker** the step-009 placeholder carried, naming step 010 as the page's future owner. Removed **on
  the orchestrator's explicit authorization**, and recorded here as a deletion so a later reader does
  not read it as lost coverage.
  - **Why a deletion is right here, when every other repair in this feature was a widening.** Deleting
    an assertion normally hides a defect; this one pinned something the spec **no longer permits**.
    `context.md` → "One mechanical note on step 009 vs 010" fixes the marker's lifecycle explicitly:
    step 009 creates the placeholder, **step 010 replaces that body with the real page**. From step 010
    onward an implementation still showing the marker would be shipping a stub label the plan ordered
    removed. The assertion bound to a transitional state, not to a requirement.
  - **Exactly one assertion removed, nothing else.** Step 009's DoD-4 clause stays fully covered: the
    same test still asserts the memos page resolves inside the content-pane `main` landmark (the
    `Memos` heading) and that it is **not** the catch-all (no `href="/"` back-to-bookshelf anchor in
    the pane); the second case (`/memos/m-1` and `/memos/new` falling through to the nested not-found
    page), the six harness mocks and their `beforeEach` arming are untouched. The file's header prose
    and an inline note at the deletion site carry the `context.md` citation that authorizes it.
- **Deliberately not asserted**: which widget kind carries the `Show archived` toggle (a helper accepts
  either a labelled control or a named button — the frozen contract is the **name**, and the clause is
  about the filter's behaviour); the literal `aria-checked` attribute on the switch (asserted through
  `toBeChecked()` on the `switch` role instead, so the clause does not couple to a Mantine DOM detail);
  the page's empty / loading / error wording, its subject registration, `memoLabel` called directly, and
  any reorder affordance — none is a step-010 `[test]` clause (reorder is step 011's).

### Step 011 — tests (2026-09-15)

Frontend step, the feature's last. One **new** spec file, bound to the Step 011 frozen interface above
(plus steps 009/010 for the api, DTO and row contracts, consumed unchanged); `globals: false`, so every
primitive is imported from `"vitest"`. Run by `cd frontend && npm test`; typechecked only by
`cd frontend && npm run test:types`. **Step 010's `MemosListPage.test.tsx` is untouched** — the two
steps' coverage stays attributable, and that file must keep passing unchanged.

- `frontend/tests/work/MemosListPageReorder.test.tsx` — **new** — covers **DoD-1, DoD-2, DoD-3, DoD-5,
  DoD-6, DoD-7, DoD-8**. **10 `it` blocks in 7 `describe` groups**, each title citing its DoD id and
  product id. The block count exceeds the clause count because three clauses carry two cases each:
  **DoD-1** (the up move and its down mirror), **DoD-3** (the two ends of a three-memo list, plus a
  one-memo working list offering neither direction) and **DoD-7** (the control contrast, and the
  submitted id list under the show-archived filter). The page is mounted under its own `/:bookId/memos`
  route; `../../src/api/memos` is mocked **wholesale**, module-factory form, never `fetch`; `ApiError`
  is the **real** class from `../../src/api/client`; queries are **by role and accessible name only**.
  - **Bound to the frozen accessible names**: `Move memo <position> up` / `Move memo <position> down` /
    `Drag memo <position> to reorder` (`button`) and the LIST-level `Reorder error` (`alert`), plus step
    010's `Memo <position> body` / `Archive memo <position>` / `Restore memo <position>` /
    `Show archived`. **Position is the 1-based index in the list the row is rendered in, never
    `memo.ordinal`** — and the fixtures make that load-bearing: the three working memos are ordinals
    1 / 4 / 7 with the archived one at ordinal 3 between them, so any name derived from `ordinal` fails
    every query.
  - **The server double is a real round trip**: a mutable `serverMemos` list answers `listMemos`
    (include-archived, one load) and `reorderMemos`, which applies the submitted sequence, rewrites the
    **working** ordinals `1..N` (what backend step 004 does) and answers with the `{ items }` envelope
    carrying the working rows only. A `deferred<T>()` helper supplies the controllable promise DoD-5 /
    DoD-6 / DoD-8 need.
  - **DoD-1** (the load-bearing clause) an arrow click shifts that memo exactly one position and calls
    `reorderMemos` **exactly once** with `(BOOK_ID, { memo_ids: [<whole ordered list>] })` — asserted on
    the **call count** and the **complete id list** (length 3, the same set sorted), not on rendered
    order, so a component with two persist paths or a double submit fails even though the screen would
    look right. Both directions are covered, and `expectNoOtherMemoWrite()` pins that the move triggered
    no create / update / activate / deactivate / archive / restore call.
  - **DoD-2** the double answers with an order of its own — the exact **reverse**, which differs from the
    clicked move's local computation — so a page rendering its optimistic result instead of the server's
    returned order fails. The server's order is asserted after the await and again after `settle()` (it
    is not re-overwritten), and the archived memo is still there afterwards.
  - **DoD-3** `Move memo 1 up` disabled, `Move memo 3 down` disabled, the middle memo's pair both
    **enabled** (so the negatives are not vacuous), exactly six arrows on screen for three rows, each
    named for its own memo; plus a one-memo working list where both directions are disabled.
  - **DoD-5** with the call deferred and **unresolved**, the moved order is already on screen, exactly
    one call has been made and no `Reorder error` alert exists; resolving then settles on the server's
    answer.
  - **DoD-6** a deferred call rejected with a real `ApiError(400, …)`: the attempted order is on screen
    while in flight, then `getByRole("alert", { name: "Reorder error" })` carries the message and the
    rendered order snaps back to the server's **whole** original list — re-asserted after `settle()`, so
    **no partial order survives** — with no row-level `Memo <n> error` raised and the controls live
    again.
  - **DoD-7** written so its negative half cannot pass vacuously: in the **same** spec the working rows
    are asserted to **carry** their controls (six arrows, three handles, each present by name) and the
    archived section, once revealed, to bring **none** — the counts stay 6 / 3 while a fourth row and its
    `Restore memo 1` are on screen. The second case clicks an arrow **with the filter on** and pins the
    payload to `{ memo_ids: ["m-2", "m-1", "m-3"] }`, never containing the archived `m-9`: a view filter
    does not change what the working list is.
  - **DoD-8** the middle memo's arrows are enabled **before** the click (so "disabled" is a change), then
    with the call in flight all six are disabled; a second arrow clicked anyway (`fireEvent`, since the
    control is disabled) leaves the call count at **1**; resolving returns the controls to life.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 **[manual/live, no test]**, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓,
  DoD-8 ✓.
- **DoD-4 (US-126.AC-1, the drag gesture) carries no test, deliberately.** jsdom has no pointer-event
  pipeline `@dnd-kit`'s sensor can drive; `frontend/tests/work/ChaptersPageReorder.test.tsx` records the
  same resolution. The gesture is verified live; the persistence it funnels into is DoD-1's single-call
  assertion, which both affordances share.
- **Deliberately not asserted**: any `@dnd-kit` internal (no sortable markup, live region or
  `aria-roledescription` probe), the drag handle's disabled mechanism (`useSortable` carries it, and the
  frozen table gives the handle no `disabled` column — DoD-8 is asserted on the arrows and on the call
  count, which is what "a second reorder cannot interleave" means), the relative placement of the
  archived section (asserted as a count and a set, not an order), which widget kind carries
  `Show archived`, and whether a failure refetches (the clause requires rollback, not a mechanism).

## Notes & Issues

### Step 005 — the idempotent no-op writes nothing

The planner left it open whether a repeat state call re-stamps `modified_at`. All four verbs
take the strict reading of DoD-10 ("the row unchanged") and return early without any write, so a
no-op leaves `modified_at` — and, for restore, `ordinal` — exactly as it was. Consistent across the
four.

### Step 004 skeleton — one step-002 spec hard-codes the two-member `MemoErrorReason`

Not an interface problem; a blast-radius gap, and the same shape as the step-001
note above. The step file mandates a **third** `MemoErrorReason` member
(`invalid_reorder_set`), and step 002's own frozen record anticipated it
("step 004 adds the third member") — but
`backend/tests/services/test_memos.py::test_service_reasons_are_membership_and_one_not_found__DoD9`
asserts the enum is **exactly** `[not_a_member, not_found]`, so widening it turns
that one previously-green test red:

| File | Test | Assertion |
|---|---|---|
| `backend/tests/services/test_memos.py` | `test_service_reasons_are_membership_and_one_not_found__DoD9` | `list(MemoErrorReason) == [not_a_member, not_found]` |

Nothing else is affected: the other 44 specs in `tests/services/test_memos.py`
and `tests/routes/test_memos.py` still pass, since the new reason is raised only
by the (unimplemented) reorder path and the new route is reached by no existing
spec.

The repair is one line — add `MemoErrorReason.invalid_reorder_set,` to that
expected list. The skeleton agent may not edit test files and this file is **not**
in step 004's Test files list, so the edit was **not** made. Whoever owns it next
(test-coder, if step 004's Test files list is widened to include it, or the
orchestrator) must apply it, or step 004's verify run will report one
pre-existing-test failure that is not the coder's fault. The alternative —
narrowing the enum back to two members — is not viable: the third reason is
mandated by the step file and by `context.md` → "The wire contract" (a reorder
list that is not exactly the caller's non-archived set is a `400`, which cannot
be carried by `not_found`).

### Step 001 skeleton — eight existing `test_data_domain_*.py` modules hard-code the registry label list

Not an interface problem; a blast-radius gap the plan does not name. Adding the
`memos` tuple to `TABLE_REGISTRY` (mandated by the step file and by
`docs/architecture/backend/book-domain.md`) makes **eight already-passing
registry-order tests fail**, because each of these modules defines its own
literal copy of the canonical label list:

| File | Symbol | Failing test |
|---|---|---|
| `backend/tests/test_data_domain_assistant_core.py` | `CANONICAL_ORDER` | `test_table_registry_order__DoD5` |
| `backend/tests/test_data_domain_assistant_links.py` | `CANONICAL_ORDER` | `test_table_registry_order__DoD6` |
| `backend/tests/test_data_domain_book.py` | `CANONICAL_ORDER` | `test_table_registry_order__DoD5` |
| `backend/tests/test_data_domain_chapter.py` | `CANONICAL_ORDER` | `test_table_registry_order__DoD3` |
| `backend/tests/test_data_domain_chapter_changes.py` | `CANONICAL_ORDER` | `test_table_registry_order__DoD4` |
| `backend/tests/test_data_domain_chat.py` | `FULL_CANONICAL_ORDER` | `test_full_table_registry_equals_canonical_order__DoD4` |
| `backend/tests/test_data_domain_codex.py` | `CANONICAL_ORDER` | `test_table_registry_order__DoD4` |
| `backend/tests/test_data_domain_continuity.py` | `CANONICAL_ORDER` | `test_table_registry_order__DoD5` |

The repair is one line per file — insert `    "memos",` between
`"chapter_author_prompts",` and `"chapters",` in that literal list. Nothing else
in those modules is affected (all other import/export tests still pass: export
and import iterate the registry per-row, so the unimplemented `_memo_to_dict` /
`_dict_to_memo` are never reached while no `memos` rows exist).

The skeleton agent may not edit test files, and these eight are **not** in step
001's Test files list, so the edits were **not** made. Whoever owns them next
(test-coder, given the step's Test files list is widened, or the orchestrator)
must apply the eight inserts, or the step-001 verify run will report eight
pre-existing-test failures that are not the coder's fault. Suggested resolution:
add the eight paths to step 001's Test files list; the alternative — leaving them
red — is not viable because the registry position is architecturally fixed and
cannot be changed to satisfy them.

### Step 009 skeleton — the backend `SubjectKind` literal does NOT carry `memos` (blocker to surface)

`009.context.md` states that `backend/app/models/schemas/chats.py`'s `SubjectKind`
`Literal` — the **third** copy of this list — "is step 006's file, not this step's,
and **it already carries `memos` by the time this runs**; if it does not, that is a
blocker to surface, not a file to edit from here."

**It does not.** As of this step the backend literal still reads exactly ten members
(`book-state` … `chats`), and no step file in this feature lists
`backend/app/models/schemas/chats.py` in its Source files — steps 006 / 007 / 008 are
`done` and touched `prompt_composition.py`, `chat_turn.py`, `subagent_delegation.py`,
`assistant_runtime.py`, `memo_tools.py`, `tools.py`, `db/mode_tools.py` and
`db/assistant_modes.py`, none of them `schemas/chats.py`. `context.md` decision 11
nevertheless requires `memos` in **all three** copies.

Consequence, stated precisely: **nothing in step 009 is blocked** — the frontend union
is not compiled against the backend one, and DoD-5 pins only the two frontend copies,
both of which now carry `memos`. What breaks is later and at **runtime**: a turn
started from the memos page sends `subject_kind: "memos"`, which the backend refuses
at the schema boundary with a **422**, exactly as an unknown kind should be refused.
That lands on step 010 / 011 (or on a live run), not here.

Suggested resolutions, with tradeoffs:

- **Add the member to `backend/app/models/schemas/chats.py` as a one-line follow-up
  under step 006's number** (a bug-fix pass, or a `006b` step). Honest about which
  layer owns it; costs one extra pass and a re-verify of step 006.
- **Widen step 010's Source files to include the backend schema.** Cheapest in passes,
  but puts a backend literal inside a frontend step and makes step 010's file list
  cross the layer line.
- **Leave it.** Not viable: `context.md` decision 11 is explicit that `memos` joins the
  literal in all three places, and the wire would refuse the kind the page sends.

The skeleton agent did **not** edit the backend file — it is in no step's Source list
and `009.context.md` names this a blocker to surface rather than a file to edit.

### Step 009 skeleton — one existing nav spec hard-codes the seven-entry table

Not an interface problem; the ordinary red-gate consequence of DoD-1. The step file
mandates an **eighth** `WORK_NAV_ITEMS` entry, and
`frontend/tests/work/navItems.test.ts` — which **is** in step 009's Test files list —
asserts `toHaveLength(7)` and an exact seven-label `EXPECTED_LABELS` array, so both
assertions now fail:

| File | Assertion |
|---|---|
| `frontend/tests/work/navItems.test.ts` | `expect(WORK_NAV_ITEMS).toHaveLength(7)` |
| `frontend/tests/work/navItems.test.ts` | `expect(WORK_NAV_ITEMS.map((item) => item.label)).toEqual([...EXPECTED_LABELS])` (seven labels) |

The file is the **test-coder's**, and it is in this step's Test files list, so the fix
is theirs and needs no widening of any list: extend the count to 8 and append
`"Memos"` to `EXPECTED_LABELS` while adding the DoD-1..DoD-3 assertions. Recorded here
only so the red-gate run does not read these two as a surprise. The file **compiles**
(`npm run test:types` is clean); only the assertions are stale.

Minor, same file family: `frontend/src/work/components/shell/WorkNavigator.tsx`'s
docstring still says "renders the seven `WORK_NAV_ITEMS`". It is a comment in a file
outside step 009's Source list and it compiles unchanged, so it was left alone;
whoever next edits that component should correct it to eight.

### Step 010 skeleton — `routes.test.tsx` does not mock `api/memos`, and that bites twice

**Step:** 010 (`010.memos-list-page.md`). Not a blocker and not a reason to change the
freeze — recorded so neither the red gate nor the verify run reads it as a defect in
this step's work.

`frontend/tests/work/routes.test.tsx` (step 009's file, in **009's** Test list, not
010's) renders `<WorkRoutes />` at `/bk-1/memos` and asserts the `Memos` heading for
its DoD-4 case. It mocks `api/books`, `api/chats`, `api/codex`, `api/flags` and
`api/continuity` — but **not `api/memos`**, because step 009's placeholder page called
nothing. Two consequences:

1. **During the red window** the page is a throwing stub, so that case fails with the
   skeleton's `026 step 010 — skeleton stub: MemosListPage is not implemented`. Expected;
   it clears when the coder fills the render.
2. **After implementation** the page's mount `useEffect` calls the **real**
   `memosApi.listMemos` → `client.request` → `fetch`. `client.ts` does **not** wrap a
   transport failure into an `ApiError` (only non-2xx responses go through
   `throwApiError`), so a jsdom fetch rejection would be rethrown by `loadMemos` as an
   unhandled rejection rather than being swallowed into `memosError`.

Resolutions, for whoever owns the file next (the test-coder — it is their domain, and
this skeleton touched no test file):

- **Preferred:** add `vi.mock("../../src/api/memos", () => ({ …eight exports… }))` to
  `routes.test.tsx`, the same module-factory form the other five already use. Cheap,
  local, and consistent with "specs mock the `api/` module wholesale, never `fetch`".
- **Alternative:** have `loadMemos` treat any thrown value as a load failure. Rejected
  by this skeleton: `026/context.md` fixes the contract as "`ApiError` is swallowed,
  anything else rethrows", and widening it to keep one unmocked spec quiet would hide
  real programming errors across the whole feature.
