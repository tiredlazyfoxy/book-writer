# Feature 016 — chapter-close-continuity

| Status  | Verifier | Date       |
|---------|----------|------------|
| done    | PASS     | 2026-07-31 |

## Files Changed

**Backend — db**

- `backend/app/db/chapter_note_changesets.py` — `update` (add/commit/refresh, returns the row) and `delete_by_chapter` (unique `chapter_id`, missing row is a no-op)
- `backend/app/db/flags.py` — `update`, and `delete_check_flags_by_chapter` with the `origin=check` filter **in the query** so no row leaves `db/` for a caller to sift

**Backend — services**

- `backend/app/services/chapters.py` — `close_chapter` now `open → closing` and deletes the chapter's `origin=check` flags first (D6), reusing `chapter_not_open` for every other source state; `reopen_chapter` additionally marks `summary_status` and the changeset row `stale` (US-055.AC-1); `cancel_close` (200 no-op off `closing`); `finalize_close_turn` — the four-fact decision, with `active_notes_proposal is not None` never a truthiness test (D7). Reshaped: extracted the private `_wipe_close_artifacts` so the cancel path and finalize's failure branch are literally one wipe
- `backend/app/services/continuity.py` — the four entry points plus private `_require_member` / `_require_not_archived` / `_require_writable_mode` / `_resolve_chapter` / `_to_changeset_response` / `_to_flag_response`; viewing is plain membership (D9), `PUT` goes through `Capability.edit_state_notes`, no-row-yet answers a default-empty 200
- `backend/app/services/flags.py` — list (newest first, open **and** resolved) / raise (`origin=person`, attributed) / resolve (`resolved_by`+`resolved_at`, second resolve is 409), plus private gates, a `_resolve_flag` that enforces the chapter, `_to_response` and the total `_newest_first_key`
- `backend/app/services/close_tools.py` — the four-rule refusal chain (`_refuse_write` + `_resolved_chapter`), all model-facing refusal / error / confirmation strings, the five tool bodies (`propose_active_notes` touches no DB; `read_continuity_context` is subject to rule 1 alone, mirroring `chapter_tools.read_chapter_text`, and always returns a string)
- `backend/app/services/chat_turn.py` — private `_finalize_close_turn_if_needed`, called once at natural completion (success, `error` frame and empty-result alike) **before** the terminal frame is yielded so a cancellation skips it; guarded on the subject being a `closing` chapter **and** the caller holding `Capability.set_chapter_state`. `run_turn`'s signature is unchanged and no second turn runner exists

**Frontend — api**

- `frontend/src/api/continuity.ts` — the four `request<T>` wrappers
- `frontend/src/api/flags.ts` — the three `request<T>` wrappers (raise sends the body, resolve sends none)
- `frontend/src/api/chapters.ts` — `cancelChapterClose`; `closeChapterState`'s comment re-stated for the server's new `closing` destination

**Frontend — work module tier & chat pane**

- `frontend/src/work/closeTurn.ts` — both registries: newest-registration-wins controller with an identity-guarded unregister, and the stored active-close fact whose two writers also call the registered controller's `setActive` synchronously
- `frontend/src/work/components/chat/chatPaneState.ts` — `isComposerReadOnly` / `composerReadOnlyReason`, the three bound `CloseTurnController` members, `startCloseTurn` (synthetic prompt, subject fixed to the chapter) and `stopCloseTurn`. Added private `CLOSE_TURN_PROMPT` and `closeTurnStreamHandlers`, which wraps the existing handlers so `done`/`error` also clear the close signal
- `frontend/src/work/components/shell/WorkspaceShell.tsx` — register/unregister the pane as the close-turn controller in the effect that already owns its lifecycle
- `frontend/src/work/components/chat/Composer.tsx` — read-only composer plus its reason as readable text while a close runs; no pane-level Stop during a close (the chapter page's Stop is the exit)

**Frontend — pages**

- `frontend/src/work/pages/bookStatePageState.ts` — `stateNotesDirty` / `canSaveStateNotes` and the three effects (`loadBookContinuity`, `loadStateNotes`, `saveStateNotes`)
- `frontend/src/work/pages/BookStatePage.tsx` — the two stubs replaced: the state-notes editor and the read-only per-chapter continuity list (summary, three deltas, open warnings). The warnings block is **named as warnings** in the surface the author reads — a `Warnings` heading, a `No warnings on this chapter.` empty state and a per-item `Warning on {chapter}: …` accessible label — per `frontend-workspace.md`'s project rule that "warning" is the author-facing word for a flag; `flag` stays the entity / table / DTO / API name throughout (verifier FAIL, DoD-12 second clause)
- `frontend/src/work/pages/chapterPageState.ts` — `offeredTransition` routes `closing → "cancel"`; the six 016 effects; `loadChapter` now marks/clears the close signal from the loaded state (the reload-mid-close mechanism). Reshaped: `runChapterTransition` returns the server's `ChapterResponse | null` so the two close effects branch on the server's answer instead of sniffing a status field — the three 015 transitions ignore the return and are otherwise untouched
- `frontend/src/work/pages/ChapterPage.tsx` — the close confirmation (Mantine `Modal`, affirmative named `Close chapter`; the Close control posts nothing until it is used), the `cancel`/Stop wiring, the two new mount-effect loads, the read-only continuity section and the warnings section with its raise form and per-warning resolve

## Skeleton

### Frozen interface (2026-07-31)

Every signature below compiles today. New bodies raise `NotImplementedError`
(backend) / `throw new Error("not implemented")` (frontend); DTOs, enums, the
capability matrix rows and the `TOOL_REGISTRY` entries are **fully written**
(declarative data is its own interface). No behavior was implemented.

**Backend — schemas (declarative, complete)**

- `backend/app/models/schemas/flags.py` — `FlagResponse` (`id`, `chapter_id`, `origin: FlagOrigin`, `comment`, `status: FlagStatus`, `created_by`, `created_at`, `resolved_by`, `resolved_at`) — new
- `backend/app/models/schemas/flags.py` — `FlagListResponse(items: list[FlagResponse])` — new
- `backend/app/models/schemas/flags.py` — `RaiseFlagRequest(comment: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)])` — new
- `backend/app/models/schemas/continuity.py` — `UpdateBookStateNotesRequest(active_notes: str)` — new
- `backend/app/models/schemas/continuity.py` — `BookStateNotesResponse(book_id, active_notes, modified_at)` — new
- `backend/app/models/schemas/continuity.py` — `ChapterNoteChangesetResponse(chapter_id, added, modified, deleted, status: NoteStatus | None, created_at, modified_at)` — new
- `backend/app/models/schemas/continuity.py` — `ChapterContinuityResponse(chapter_id, title, ordinal, summary, summary_status: SummaryStatus | None, changeset: ChapterNoteChangesetResponse | None, warnings: list[FlagResponse])` — new
- `backend/app/models/schemas/continuity.py` — `BookContinuityResponse(items: list[ChapterContinuityResponse])` — new
- `backend/app/models/schemas/chapters.py` — `ChapterResponse` — changed: gains `summary: str | None` and `summary_status: SummaryStatus | None` (both **required**, not defaulted)

**Backend — db (session-free, stubs)**

- `backend/app/db/chapter_note_changesets.py` — `async def update(row: ChapterNoteChangeset) -> ChapterNoteChangeset` — new
- `backend/app/db/chapter_note_changesets.py` — `async def delete_by_chapter(chapter_id: int) -> None` — new
- `backend/app/db/flags.py` — `async def update(row: Flag) -> Flag` — new
- `backend/app/db/flags.py` — `async def delete_check_flags_by_chapter(chapter_id: int) -> None` — new

**Backend — authz (declarative, complete)**

- `backend/app/services/authz.py` — `Capability.raise_flag` / `.resolve_flag` / `.edit_state_notes` — new members
- `backend/app/services/authz.py` — `_CAPABILITY_MATRIX` rows: `raise_flag → {owner, co_author}`, `resolve_flag → {owner}`, `edit_state_notes → {owner, co_author}` (D9)

**Backend — chapters service**

- `backend/app/services/chapters.py` — `async def cancel_close(access: BookAccess, chapter_id: str) -> ChapterResponse` — new (stub)
- `backend/app/services/chapters.py` — `async def finalize_close_turn(access: BookAccess, chapter_id: str, tool_context: "ToolContext") -> ChapterResponse` — new (stub). `ToolContext` is a `TYPE_CHECKING`-only quoted annotation (cycle guard: `tools.py → close_tools.py`).
- `backend/app/services/chapters.py` — `_to_response` — changed: now maps `summary` / `summary_status` (mechanical, required by the DTO change)
- `backend/app/services/chapters.py` — `close_chapter(access, chapter_id) -> ChapterResponse` and `reopen_chapter(access, chapter_id) -> ChapterResponse` — signatures **unchanged**; bodies left exactly as 015 shipped them (the `open → closing`, check-flag deletion and stale-marking changes are the coder's)

**Backend — continuity service (new module)**

- `backend/app/services/continuity.py` — `class ContinuityErrorReason(str, Enum)`: `not_a_member` / `book_archived` / `proposal_mode_refused` / `chapter_not_found` — new, complete
- `backend/app/services/continuity.py` — `class ContinuityError(Exception)` — `__init__(self, reason: ContinuityErrorReason, message: str = "") -> None`, carrying `.reason` / `.message` — new, complete
- `backend/app/services/continuity.py` — `async def get_state_notes(access: BookAccess) -> BookStateNotesResponse` — new (stub)
- `backend/app/services/continuity.py` — `async def update_state_notes(access: BookAccess, body: UpdateBookStateNotesRequest) -> BookStateNotesResponse` — new (stub)
- `backend/app/services/continuity.py` — `async def get_chapter_changeset(access: BookAccess, chapter_id: str) -> ChapterNoteChangesetResponse` — new (stub)
- `backend/app/services/continuity.py` — `async def get_book_continuity(access: BookAccess) -> BookContinuityResponse` — new (stub)

**Backend — flags service (new module)**

- `backend/app/services/flags.py` — `class FlagErrorReason(str, Enum)`: `not_a_member` / `book_archived` / `chapter_not_found` / `flag_not_found` / `flag_already_resolved` — new, complete
- `backend/app/services/flags.py` — `class FlagError(Exception)` — `__init__(self, reason: FlagErrorReason, message: str = "") -> None` — new, complete
- `backend/app/services/flags.py` — `async def list_flags(access: BookAccess, chapter_id: str) -> FlagListResponse` — new (stub)
- `backend/app/services/flags.py` — `async def raise_flag(access: BookAccess, chapter_id: str, body: RaiseFlagRequest) -> FlagResponse` — new (stub)
- `backend/app/services/flags.py` — `async def resolve_flag(access: BookAccess, chapter_id: str, flag_id: str) -> FlagResponse` — new (stub)

**Backend — close tools (new module)**

- `backend/app/services/close_tools.py` — `DraftChapterSummaryArgs(summary: str)`, `DraftChapterNotesArgs(added, modified, deleted: str)`, `ProposeActiveNotesArgs(active_notes: str)`, `RaiseCheckFlagArgs(comment: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)])`, `ReadContinuityContextArgs` (no fields) — new, complete (model-facing `Field(description=…)` on every field)
- `backend/app/services/close_tools.py` — `async def draft_chapter_summary(context: "ToolContext", summary: str) -> str` — new (stub)
- `backend/app/services/close_tools.py` — `async def draft_chapter_notes(context: "ToolContext", added: str, modified: str, deleted: str) -> str` — new (stub)
- `backend/app/services/close_tools.py` — `async def propose_active_notes(context: "ToolContext", active_notes: str) -> str` — new (stub)
- `backend/app/services/close_tools.py` — `async def raise_check_flag(context: "ToolContext", comment: str) -> str` — new (stub)
- `backend/app/services/close_tools.py` — `async def read_continuity_context(context: "ToolContext") -> str` — new (stub)
- `backend/app/services/close_tools.py` — `bind_draft_chapter_summary` / `bind_draft_chapter_notes` / `bind_propose_active_notes` / `bind_raise_check_flag` / `bind_read_continuity_context`, each `(context: "ToolContext") -> Callable[..., object]` — new, **implemented** as `functools.partial(fn, context)` (declarative glue, mirroring `chapter_tools.py`; the registry must be well-formed for `build_tool_bindings`' pre-flight)
- The private four-rule refusal helper is **not** part of the frozen interface — the coder writes it, mirroring `chapter_tools.py:_refuse_write`.

**Backend — tools registry**

- `backend/app/services/tools.py` — `ToolContext` — changed: gains `active_notes_proposal: str | None = None`, and the decorator changed from `@dataclass(frozen=True)` to `@dataclass` (see divergence D-1 below)
- `backend/app/services/tools.py` — `TOOL_REGISTRY` gains 5 bound `ToolDef` entries: `draft_chapter_summary`, `draft_chapter_notes`, `propose_active_notes`, `raise_check_flag`, `read_continuity_context`. No `mode_tool` row seeded — shipped unreachable (015 precedent).

**Backend — routes**

- `backend/app/routes/chapters.py` — `POST /api/books/{book_id}/chapters/{chapter_id}/close/cancel` → `ChapterResponse` (200), handler `cancel_chapter_close(chapter_id, access)` — new
- `backend/app/routes/continuity.py` (new module) — `router = APIRouter(prefix="/api/books", tags=["continuity"])`; `_CONTINUITY_ERROR_STATUS` (`not_a_member`/`book_archived`/`proposal_mode_refused` → 403, `chapter_not_found` → 404); `_map_continuity_error`, `_map_authz_error`; handlers `get_state_notes`, `update_state_notes(payload)`, `get_book_continuity`, `get_chapter_changeset(chapter_id)` over `GET|PUT /{book_id}/state-notes`, `GET /{book_id}/continuity`, `GET /{book_id}/chapters/{chapter_id}/notes`
- `backend/app/routes/flags.py` (new module) — `router = APIRouter(prefix="/api/books", tags=["flags"])`; `_FLAG_ERROR_STATUS` (403/403/404/404/409); `_map_flag_error`, `_map_authz_error`; handlers `list_flags`, `raise_flag(payload)` (**201**), `resolve_flag(flag_id)` over `GET|POST /{book_id}/chapters/{chapter_id}/flags` and `POST …/flags/{flag_id}/resolve`
- `backend/app/main.py` — `continuity.router` and `flags.router` registered (after `codex.router`)

**Frontend — types (declarative, complete)**

- `frontend/src/types/flags.d.ts` (new) — `FlagOrigin`, `FlagStatus`, `FlagResponse`, `FlagListResponse`, `RaiseFlagRequest`
- `frontend/src/types/continuity.d.ts` (new) — `ContinuityStatus`, `BookStateNotesResponse`, `UpdateBookStateNotesRequest`, `ChapterNoteChangesetResponse`, `ChapterContinuityResponse`, `BookContinuityResponse`
- `frontend/src/types/chapters.d.ts` — `ChapterResponse` — changed: gains `summary: string | null` and `summary_status: ContinuityStatus | null` (both required)

**Frontend — api (stubs)**

- `frontend/src/api/continuity.ts` (new) — `getStateNotes(bookId, signal?)`, `updateStateNotes(bookId, body, signal?)`, `getBookContinuity(bookId, signal?)`, `getChapterChangeset(bookId, chapterId, signal?)`
- `frontend/src/api/flags.ts` (new) — `listFlags(bookId, chapterId, signal?)`, `raiseFlag(bookId, chapterId, body, signal?)`, `resolveFlag(bookId, chapterId, flagId, signal?)`
- `frontend/src/api/chapters.ts` — `cancelChapterClose(bookId, chapterId, signal?): Promise<ChapterResponse>` — new

**Frontend — `work/closeTurn.ts` (new module-tier sibling, stubs)**

- `interface CloseTurnController { start(bookId, chapterId): void; stop(): void; setActive(active: { bookId: string; chapterId: string } | null): void }` — complete
- `registerCloseTurnController(c: CloseTurnController): void`
- `unregisterCloseTurnController(c: CloseTurnController): void`
- `requestCloseTurnStart(bookId: string, chapterId: string): void`
- `requestCloseTurnStop(): void`
- `markCloseTurnActive(bookId: string, chapterId: string): void`
- `clearCloseTurnActive(): void`
- `activeCloseTurn(): { bookId: string; chapterId: string } | null`
- module slots `controller` and `activeClose` declared (referenced via `void` in `requestCloseTurnStop` so the skeleton compiles under `noUnusedLocals`; the coder removes those references)

**Frontend — `work/components/chat/chatPaneState.ts`**

- `class ChatPaneState implements CloseTurnController` — changed
- field `closeTurnActive: { bookId: string; chapterId: string } | null = null` — new
- `get isComposerReadOnly(): boolean` — new (stub returns `false`)
- `get composerReadOnlyReason(): string | null` — new (stub returns `null`)
- bound members `readonly start = (bookId: string, chapterId: string): void`, `readonly stop = (): void`, `readonly setActive = (active: { bookId: string; chapterId: string } | null): void` — new (stubs throw)
- constructor — changed: `makeAutoObservable(this, { start: false, stop: false, setActive: false })`
- `export async function startCloseTurn(state: ChatPaneState, bookId: string, chapterId: string, signal?: AbortSignal): Promise<void>` — new (stub)
- `export function stopCloseTurn(state: ChatPaneState): void` — new (stub)

**Frontend — `work/pages/bookStatePageState.ts`**

- fields — new: `continuity` / `continuityStatus` / `continuityError`; `stateNotes` / `stateNotesStatus` / `stateNotesError`; `stateNotesDraft`, `stateNotesServerErrors`, `stateNotesSubmitStatus`
- `get stateNotesDirty(): boolean` and `get canSaveStateNotes(): boolean` — new (stubs return `false`)
- `export async function loadBookContinuity(state, bookId, signal?): Promise<void>` — new (stub)
- `export async function loadStateNotes(state, bookId, signal?): Promise<void>` — new (stub)
- `export async function saveStateNotes(state, bookId, signal?): Promise<void>` — new (stub)

**Frontend — `work/pages/chapterPageState.ts`**

- `export type ChapterTransition = "open" | "close" | "reopen" | "cancel"` — changed (was `"open" | "close" | "reopen"`); see divergence D-2
- fields — new: `warnings: FlagResponse[]` / `warningsStatus` / `warningsError`; `changeset: ChapterNoteChangesetResponse | null` / `changesetStatus` / `changesetError`; `raiseFlagDraft: string`, `raiseFlagSubmitStatus`, `closeConfirmOpen: boolean`
- `export async function loadChapterWarnings(state, bookId, chapterId, signal?): Promise<void>` — new (stub)
- `export async function loadChapterChangeset(state, bookId, chapterId, signal?): Promise<void>` — new (stub)
- `export async function raiseChapterFlag(state, bookId, chapterId, comment: string, signal?): Promise<void>` — new (stub)
- `export async function resolveChapterFlag(state, bookId, chapterId, flagId: string, signal?): Promise<void>` — new (stub)
- `export async function requestChapterClose(state, bookId, chapterId, signal?): Promise<void>` — new (stub)
- `export async function cancelChapterCloseRequest(state, bookId, chapterId, signal?): Promise<void>` — new (stub)
- `get offeredTransition()` return type widens with the union; its **body is unchanged** (`closing → null` today) — routing `closing → "cancel"` is the coder's

**Caller-compile edits (out of the plan's Source areas):** None. The one caller
fix needed — `frontend/src/work/pages/ChapterPage.tsx`'s
`TRANSITION_LABELS: Record<ChapterTransition, string>` gaining a `cancel: "Stop"`
entry after the union widened — is **inside** the declared source area
`frontend/src/work/pages/`.

### Divergences from `plan.md` → `## Interface`

- **D-1 — `ToolContext` is no longer `@dataclass(frozen=True)`.** The plan
  declares `active_notes_proposal: str | None = None   # NEW, mutable in place`,
  and `propose_active_notes` assigns it; a frozen dataclass raises
  `FrozenInstanceError` on that assignment. Minimal adaptation: drop `frozen=True`
  from **`ToolContext` only** (`ToolDef` and every other frozen record are
  untouched). Verified safe: nothing in `app/` or `tests/` hashes a `ToolContext`
  or uses one as a dict/set key, and no construction site changes (all five
  non-`book_id` fields still default). The field set is exactly as the plan
  declares it.
- **D-2 — `ChapterTransition` stays in `work/pages/chapterPageState.ts`.** The
  plan lists it under `frontend/src/types/chapters.d.ts (extend)`. That file's own
  contract is "wire DTOs matching the backend Pydantic schemas 1:1"; a transition
  is a UI affordance with no wire counterpart, and moving the type would churn
  `ChapterPage.tsx` and existing tests' imports for nothing. The union is widened
  in place with `"cancel"`, which is the behavioural half the plan actually needs.
- **D-3 — `isComposerReadOnly` cannot compare book ids.** The plan states it as
  "true when `closeTurnActive.bookId` matches the pane's own book". `ChatPaneState`
  holds **no** `bookId` (every effect takes it as an argument, and
  `WorkspaceShell` already remounts the pane per book via `key={bookId}`), so
  there is nothing to compare against. The signature is frozen as declared; the
  coder resolves the predicate as "a close is active at all". **No `bookId` field
  was added to `ChatPaneState`** to manufacture the other side of a comparison
  that cannot disagree.
- **D-4 — timestamp fields use `ISODateString`, not bare `string`,** in the two
  new `.d.ts` modules. `ISODateString` *is* `string` (a house alias every other
  `types/*.d.ts` uses), so the shapes are structurally identical to the plan's.

### Build gates

- `cd backend && .venv/Scripts/python -m pytest --collect-only` — **clean**, 1144
  tests collected, no import errors. `app.openapi()` also builds, which validates
  every new response model and confirms all 8 new route registrations.
- `cd frontend && npx tsc --noEmit` — **clean**.

## Tests

### Tests (2026-07-31)

- `backend/tests/test_chapter_close.py` — covers DoD-1, DoD-2, DoD-3, DoD-4, DoD-5 —
  the gated `open → closing` transition and its refusals; the finalize decision table
  over all four facts (including the `None`-proposal wipe branch that must never write
  `Book.active_notes`, and `""` as a legitimate proposal); cancel discards / is a no-op
  elsewhere; the check-flag sweep on close with person flags surviving; the reopen
  stale-marking of both artifacts. (11 test functions, 17 parameterized cases.)
- `backend/tests/test_flags.py` — covers DoD-6 — `raise_flag` {owner, co_author}
  producing an open `origin=person` flag attributed to the caller; `resolve_flag`
  {owner} moving `open → resolved` with `resolved_by` / `resolved_at` stamped; reader
  and non-member refused on both; a second resolve is `flag_already_resolved`.
  (5 test functions, 11 parameterized cases.)
- `backend/tests/test_close_tools.py` — covers DoD-7 — the four-rule refusal chain
  (non-chapter subject · chapter not in `closing` · archived book · caller without
  `Capability.set_chapter_state`), each rule in isolation with its success contrast,
  plus simultaneous-violation combinations proving the chain is walked in order and
  never raises; refusals write nothing and record no proposal; `read_continuity_context`
  always answers with a string. (8 test functions, 40 parameterized cases.)
- `backend/tests/test_continuity.py` — covers DoD-8 — a free-mode state-notes edit
  applies to the live set immediately for owner and co-author (`""` included); a
  proposal-mode co-author is refused `proposal_mode_refused` with the live notes
  unchanged, while the owner in the same book and the same co-author in a free-mode
  book still edit. (5 test functions, 6 parameterized cases.)
- `frontend/tests/work/ChapterPageClose.test.tsx` — covers DoD-9 — `closeTurn.ts`'s
  signal (readable with no controller registered; delivered synchronously to a
  registered one; start/stop requests; no-op without a controller); the pane's
  `isComposerReadOnly` / `composerReadOnlyReason` driven by that signal alone;
  `startCloseTurn` posting a chapter-subject turn and the `done`/`error` ending
  clearing the signal; `stopCloseTurn` aborting; `requestChapterClose` /
  `cancelChapterCloseRequest` wiring and their refusal paths; `offeredTransition`
  `closing → "cancel"`; and in the DOM — the Close control asking for confirmation
  before posting, a reload on a `closing` chapter still marking the close active with
  no stream running, a non-closing load clearing a stale signal, and Stop posting to
  `close/cancel`. (17 tests.)

- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓,
  DoD-9 ✓; DoD-10..DoD-18 [verify, no test]; DoD-19 [manual/live, no test].
- Deliberately not tested (per plan `## Test plan`): 6 items — DTO mapping and route
  pass-throughs, `api/continuity.ts` / `api/flags.ts` wrappers, the LLM call itself,
  `BookStatePage` read-only rendering, badge/label maps, JSONL codecs /
  `TABLE_REGISTRY`.

### Fixture re-binding to the re-frozen `ChapterResponse` (2026-07-31)

`summary: null, summary_status: null` added to the chapter fixture in ten pre-existing
frontend test files — `tests/user/BookHubPage.test.tsx`, `tests/user/chaptersApi.test.ts`,
`tests/user/chaptersWriteApi.test.ts`, `tests/work/ChapterPage.test.tsx`,
`tests/work/ChapterPageBody.test.tsx`, `tests/work/ChapterPageCanvas.test.tsx`,
`tests/work/ChapterPageReconcile.test.tsx`, `tests/work/ChapterPageStateControls.test.tsx`,
`tests/work/ChaptersPage.test.tsx`, `tests/work/ChaptersPageReorder.test.tsx`.
Mechanical only — **no assertion was changed, weakened or removed** in any of them.

### Re-bindings of pre-existing tests to the superseded spec (2026-07-31)

Adjudicated by the orchestrator: `plan.md` supersedes the pre-016 close behavior these
three files encode, so they are re-bound rather than left contradicting. **Not new
coverage** — every claim each test made that this plan does not change is preserved.
Test-name renames keep each file's *originating* feature's DoD ids (015's), unrenumbered.

- `backend/tests/services/test_chapter_states.py` — re-bound to 016 DoD-1
  (US-038.AC-3). Module docstring updated. New private helper `_force_state` writes a
  post-close `closed` row straight through `db/chapters.py` (the file's own convention
  for reaching a state whose producer it does not test — here, the step that ENDS the
  `closing` window, which is 016's and lives in `tests/test_chapter_close.py`).
  - `test_close_goes_straight_to_closed__DoD7_US038_AC1` renamed to
    `test_close_opens_the_close_window__DoD7_US038_AC1`; asserts `closing` instead of
    `closed` (and `!= closed` instead of `!= closing`). Its other four claims — summary,
    summary_status, flags, `ChapterChange` and `ChapterTextRevision` all untouched by the
    close — are kept verbatim.
  - `test_at_most_one_open_across_a_sequence__DoD5_US037_AC1` — the two close steps now
    assert `closing` and each is followed by `_force_state(..., closed)` so the sequence
    can continue. Every `_open_ids` / `_states` invariant assertion is unchanged.
  - `test_close_releases_the_slot__DoD10` renamed to
    `test_slot_is_released_when_the_close_completes__DoD10`. The release claim is kept but
    correctly located: the close now leaves the chapter `closing`, which
    `_require_open_slot_free` has always treated as slot-holding, so the test now asserts
    both halves — while `closing` the slot is still held and a second open is refused
    `another_chapter_open`; once the chapter reaches `closed` the slot is free and the
    second chapter opens. Final `_states` assertion unchanged.
  - `test_close_touches_state_and_modified_at_only__DoD17` — the two state assertions
    become `closing`; all six "unchanged column" assertions and both "no history row"
    assertions are unchanged.
  - Unchanged and still correct: DoD-3, DoD-4, DoD-6, DoD-8, DoD-9, DoD-11..DoD-16,
    DoD-18.
- `backend/tests/routes/test_chapter_states.py` — re-bound to 016 DoD-1. Module docstring
  updated; `test_owner_closes_open_chapter__DoD10_US038_AC1` now asserts
  `body["state"] == "closing"` and a stored `ChapterState.closing`. Its 200, its
  `ChapterResponse.model_validate` and its id assertion are unchanged; no other test in
  the file moved (the status taxonomy, the owner-only 403, the slot 409s and the
  state-machine 409s are all still correct).
- `frontend/tests/work/ChapterPageStateControls.test.tsx` — re-bound to 016 DoD-1 +
  DoD-9. Header docstring updated. Harness: `api/chapters` factory gains
  `cancelChapterClose` (fourteen exports); `api/flags` and `api/continuity` are mocked and
  armed benignly so 016's two new mount reads cannot reach the network;
  `transitionControls()` now matches the frozen `<action> chapter: <title>` shape
  verb-agnostically; `beforeEach` arms `closeChapterState` with `closing`; a new
  `confirmClose()` helper clicks the confirmation's affirmative control. The obsolete
  `CLOSING_REASON` constant is deleted with the placeholder it named.
  - DoD-2 — now asserts the click alone posts nothing, then confirms; the resulting state
    is `Closing`, not `Closed`. Its "exactly one control and it is Close", "body editable
    with a save control before", "neither other endpoint called", "stored body still
    shown", "no editor and no save control after" claims are all kept.
  - DoD-4 — re-bound from "offers nothing behind the not-built-yet sentence" to "offers
    exactly one control, which posts to `close/cancel` and returns the chapter to `open`"
    (D4). Keeps "exactly one, and none of the other three", `Closing` shown, and adds the
    endpoint assertion the old placeholder made impossible. The contrast case keeps its
    point (the offer is state-derived) with the deleted sentence swapped for "the cancel
    endpoint was not called".
  - DoD-5's archived-close case — the refusal is now reached through the confirmation;
    the server's message, the refusal title and "still shown as Open" are unchanged, plus
    `not.toContain("Closing")` beside the existing `not.toContain("Closed")`.
  - DoD-8 — the refused close is now reached through the confirmation; every assertion
    about the surviving draft, the surviving restore buffer, the refusal on screen and
    `updateChapterText` never being called is unchanged.
  - Unchanged: DoD-1, DoD-3, DoD-6, DoD-7, DoD-9.
  - Not extended: step 008's DoD-9 (accessible names) still iterates
    planned/open/closed only — the `closing` chapter's Stop control has no frozen
    accessible name to assert, so no case was added for it.

### Re-bindings, round 2 — after the first verify run's TEST fault (2026-07-31)

Adjudicated by the orchestrator: implementation faithful on every clause; six further
pre-existing test files encoded superseded contracts or lacked harness for the page's new
mount reads. **Not new coverage.** Each file keeps its *originating* feature's DoD ids.

- `backend/tests/services/test_chapters.py` — `WIRE_FIELDS` widened by exactly `summary`
  and `summary_status` (`## Skeleton` re-froze `ChapterResponse` with both as REQUIRED;
  DoD-12). Module docstring and the DoD-14 comment updated. Both DoD-14 tests keep every
  other claim verbatim: string ids, the DTO/not-ORM check, and the body text still absent
  from the wire.
- `backend/tests/routes/test_chapters.py` — same two names added to that file's own
  `WIRE_FIELDS`; comment updated. `test_list_returns_ordinal_ascending_string_ids_no_text__DoD1`
  keeps its ordinal-ascending, string-id and `"text" not in chapter` claims unchanged.
- `backend/tests/services/test_tools.py` — `test_registry_has_single_web_search_entry__DoD3`'s
  pinned name set gains the five close tools (DoD-14), following that test's existing
  per-feature widening-comment convention. Its actual subject is untouched: `web_search`
  is still asserted FIRST, with its description, its args schema and its callable. The
  three other tests in the file needed no change (`build_tool_bindings` without a context
  still yields exactly the one unbound entry).
- `frontend/tests/work/BookStatePage.test.tsx` — re-bound to D8 / DoD-12, which replace
  the two placeholder stubs this file was written against. Harness: `api/continuity` mocked
  in factory form and armed benignly (state notes + one chapter's continuity carrying one
  open warning); two new helpers `labelTextForControl` / `queryStateNotesEditor`, and
  `queryPromptEditor`'s "sole textarea" fallback narrowed to "the sole textarea that is not
  the state-notes editor". Changed:
  - DoD-1 (010/003) — the "the Book-state view is up" marker moves from the per-chapter
    stub's literal `016.chapter-close-continuity` naming to the state-notes region. The
    redirect assertion is unchanged.
  - DoD-3 (010/003) — the region is now asserted present *and editable* instead of showing
    "not yet available". Keeps the successful-load precondition and the "state notes" naming.
  - DoD-4 (010/003) — the owner-naming assertion becomes a region-label assertion; the
    durable half, "the page says warning, never flag", is unchanged verbatim.
  - `expectBookStateContentIntact()` (shared by three 021/006 cases) — same owner-naming
    swap; its eight other assertions untouched.
  - 021/006 DoD-9 — the closed set of editable controls is widened by exactly one region
    (the state-notes editor) and stays CLOSED: still exactly two, both identified, so a
    third editable control anywhere on the surface fails it. Its half-one (the prompt
    editor is editable and accepts text) is unchanged.
  - Unchanged: DoD-2 and both DoD-5 cases (010/003); 021/006 DoD-1..DoD-8.
- `frontend/tests/work/ChapterPageCanvas.test.tsx` — **harness only, no assertion changed.**
  `api/flags` and `api/continuity` mocked in factory form and armed benignly by a new
  `armContinuityReads()` called from `beforeEach`, so the page's two new mount reads
  (`plan.md` -> Interface for `chapterPageState.ts`) resolve locally.
- `frontend/tests/work/ChapterPage.test.tsx`, `ChapterPageBody.test.tsx`,
  `ChapterPageReconcile.test.tsx` — the identical harness arming, for the same reason.
  **No assertion changed in any of the three.**

### Re-bindings, round 3 — harness arming only (2026-07-31)

- `frontend/tests/work/subjectRoutes.test.tsx` — **harness arming, not coverage; no
  assertion changed.** The file mounts the whole `WorkRoutes` table, whose Book-state and
  chapter surfaces now read continuity data on mount (`plan.md` -> Interface for
  `bookStatePageState.ts` / `chapterPageState.ts`). Without doubles those reads reached the
  real `api/client` and left rejected promises behind (`TypeError: RequestInit: Expected
  signal ... to be an instance of AbortSignal` — 2 in isolation, 4 in a full run), which is
  a false-positive risk even though the file's 8 tests passed. Added whole-module factory
  mocks for `api/flags` and `api/continuity` beside the file's existing `api/books` /
  `api/chats` / `api/codex` factories, plus an `armContinuityReads()` helper called from
  the file's existing `beforeEach` — answering with no state notes, no per-chapter
  continuity, no warnings and an empty changeset. The file's own DoD-citation convention
  is untouched, and nothing in it asserts on either module. This is the same arming applied
  in round 2 to `ChapterPageCanvas` / `ChapterPage` / `ChapterPageBody` /
  `ChapterPageReconcile`; `subjectRoutes` was the one file that pass missed.

### Re-bindings, round 4 — harness arming, class closed by sweep (2026-07-31)

**Harness arming only. No assertion was added, changed, removed or reworded in any file
below; no test was deleted; every file keeps its own originating feature's DoD citations.**

The failing instance was `frontend/tests/work/chatsNavigatorEntry.test.tsx` (renders
`/:bookId/state`, mocked only `api/books` + `api/chats`; the Book-state surface's new
mount reads therefore reached the real HTTP client and left 2 rejected promises behind —
`npm test` exit 1 despite 654/654 passing). Rounds 2 and 3 each closed one instance of
this class and each missed one more file, so this round closed the CLASS by sweep rather
than by instance.

**Sweep method.** Grep `frontend/tests/**` for every file referencing a work surface —
`src/work/routes`, `src/work/pages/`, `src/work/components/shell/`, or `WorkRoutes` — then
subtract those already carrying an `api/continuity` double. 18 files matched; the
difference was armed.

**Armed this round (7):** `chatsNavigatorEntry.test.tsx`, `WorkspaceShell.test.tsx`,
`codexListPage.test.tsx`, `codexEntryPage.test.tsx`, `ChaptersPage.test.tsx`,
`ChaptersPageReorder.test.tsx`, `canvasWiring.test.tsx`.

**Already armed in rounds 2–3 (8):** `ChapterPageCanvas`, `ChapterPage`, `ChapterPageBody`,
`ChapterPageReconcile`, `BookStatePage` (round 2); `subjectRoutes` (round 3); plus
`ChapterPageStateControls` and `ChapterPageClose`, armed when they were written.

**Deliberately NOT armed (3), with reason:**
- `routes.test.tsx` — renders `WorkRoutes` only at `/`, which matches the terminal
  catch-all and mounts `NotFoundPage`. No book surface mounts; the file mocks no api
  module at all and makes no request.
- `WorkNavigator.test.tsx` — renders the `WorkNavigator` component directly with props,
  never a route or a page; mocks no api module and makes no request.
- `navItems.test.ts` — a pure data-module test; nothing renders.

**What the arming is, identically in all 7:** whole-module factories for `api/flags`
(`listFlags` / `raiseFlag` / `resolveFlag`) and `api/continuity` (`getStateNotes` /
`updateStateNotes` / `getBookContinuity` / `getChapterChangeset`), plus an
`armContinuityReads()` helper called from each file's existing top-level `beforeEach`
(`restoreMocks` wipes implementations between tests, so factory-level defaults would not
survive). Every fixture is EMPTY — no state notes, no continuity items, no warnings, an
empty changeset — because `plan.md` -> Test plan puts the Book-state surface's own content
on the deliberate not-tested list. Nothing in any of the 7 files asserts on either module.

**Class-closure claim on the record:** after this sweep, every frontend test file that
mounts a work route, renders `WorkRoutes`, or routes to `/:bookId/state` or a chapter
surface carries doubles for both modules those pages now read on mount.

## Notes & Issues

### Coder (2026-07-31) — three places the plan left open, and how they were read

- **`read_continuity_context` and the refusal chain.** `close_tools.py`'s own module
  docstring settles it: the read-only tool is subject to **rule 1 alone**, exactly as
  `chapter_tools.read_chapter_text` is. It returns a digest (the book's `active_notes`
  plus every previously-closed chapter's **approved** summary, ordinal order; the
  closing chapter's own draft is excluded — it is what is being checked), always a
  non-empty string, and never raises.
- **`finalize_close_turn`'s call site is capability-gated.** A co-author's own chat
  also resolves to `close-chapter` while somebody else's chapter is `closing`, so an
  ordinary turn of theirs would otherwise finalize — and wipe — the owner's in-flight
  run. `chat_turn.py` skips the finalize for a caller who does not hold
  `Capability.set_chapter_state`, which is the same rule the close tools' fourth
  refusal applies to that turn's tool calls. `finalize_close_turn` itself stays
  refusal-free, as its frozen contract requires. Recorded under `## Observations`.
- **`isComposerReadOnly`** resolved per the Skeleton's divergence D-3 as "a close is
  active at all"; no `bookId` field was added to `ChatPaneState`.

### Coder (2026-07-31) — `closeChapterState` (page effect) is now unused by the page

`chapterPageState.ts`'s 015 `closeChapterState` is still exported and still correct,
but `ChapterPage` now goes through `requestChapterClose` (behind the confirmation)
instead. It was **not** removed: 015's contract for the bare transition did not move,
and removing an exported effect is out of this feature's scope. Its docstring now says
so. Worth a look when 015's surface is next revisited.

### Skeleton (2026-07-31) — `npm run test:types` now fails on pre-existing fixtures

Adding the two **required** (non-optional) fields `summary` / `summary_status` to
`ChapterResponse` — which `plan.md` → `## Interface` declares that way, and which
`DoD-12` requires — makes ten **existing** test files' chapter fixtures
incomplete. `npm run test:types` reports `TS2739` / `TS2322` in:

`tests/user/BookHubPage.test.tsx`, `tests/user/chaptersApi.test.ts`,
`tests/user/chaptersWriteApi.test.ts`, `tests/work/ChapterPage.test.tsx`,
`tests/work/ChapterPageBody.test.tsx`, `tests/work/ChapterPageCanvas.test.tsx`,
`tests/work/ChapterPageReconcile.test.tsx`,
`tests/work/ChapterPageStateControls.test.tsx`,
`tests/work/ChaptersPage.test.tsx`, `tests/work/ChaptersPageReorder.test.tsx`.

The fix is mechanical — `summary: null, summary_status: null` in each chapter
fixture — but **tests are not the skeleton's to edit**, and these files are in no
role's declared scope for this feature (the plan's Test files list names only
`frontend/tests/work/ChapterPageClose.test.tsx`).

This is **not** a build-gate failure for this feature as specified: `DoD-18` names
`pytest` and `npm run build`, and `npm run build` is unaffected because
`frontend/tsconfig.json` keeps `include: ["src"]` (a broken test can never break
the bundle). `npx tsc --noEmit` is likewise clean.

Suggested resolution, for the orchestrator to assign: let the **test-coder** add
the two fields to those ten fixtures while it writes
`ChapterPageClose.test.tsx` (it owns test files), or run a fixer pass over them
before the verify run. The alternative — declaring the two fields optional
(`summary?:`) — was **rejected**: the backend always sends them, and an optional
wire field would misdescribe the contract and hide a genuinely missing value.
