# 016.chapter-close-continuity — Chapter close & continuity

## Goal

Let an owner close a chapter through an ordinary assistant chat turn that
drafts the summary and state-note changeset, proposes the resulting live note
set, and runs a consistency check — with the server deciding the outcome
deterministically when the turn ends. Members gain read/edit surfaces for
state notes, a chapter's changeset and summary, and warnings (flags); reopening
a chapter marks its continuity data stale.

## Realizes

FEAT-012: UC-047, UC-048 (partial — no approval gate, see Decisions taken),
UC-049, UC-050, UC-051, UC-052, UC-089, UC-091; US-049, US-052, US-053
(partial), US-054, US-055, US-104, US-106.AC-2/AC-3.
FEAT-016: UC-064, UC-065, UC-067, UC-068, UC-080; US-072, US-073, US-074
(partial — AC-1 only), US-075, US-076, US-077, US-091, US-092.

## Source areas

- `backend/app/models/schemas/` — continuity + flags DTOs; `ChapterResponse` extension
- `backend/app/services/` — authz, chapters, continuity, flags, close_tools, tools
- `backend/app/routes/` — continuity, flags, chapters (`close/cancel`)
- `backend/app/db/` — `chapter_note_changesets.py`, `flags.py` additions
- `backend/app/main.py` — router registration only
- `frontend/src/types/` — continuity.d.ts, flags.d.ts, chapters.d.ts extension
- `frontend/src/api/` — continuity.ts, flags.ts, chapters.ts extension
- `frontend/src/work/pages/` — `BookStatePage`/state, `ChapterPage`/state
- `frontend/src/work/components/` — chat pane state, chapter warnings/close-confirm UI
- `frontend/src/work/*.ts` — module-tier sibling only: new `closeTurn.ts`

## Test files

- `backend/tests/test_chapter_close.py`
- `backend/tests/test_flags.py`
- `backend/tests/test_close_tools.py`
- `backend/tests/test_continuity.py`
- `frontend/tests/work/ChapterPageClose.test.tsx`

## Interface

### `backend/app/services/authz.py` (extend)

```python
class Capability(str, Enum):
    ...
    raise_flag = "raise_flag"        # {owner, co_author}
    resolve_flag = "resolve_flag"    # {owner}
    edit_state_notes = "edit_state_notes"  # {owner, co_author}, mode-qualified in continuity.py
```
`_CAPABILITY_MATRIX` gains the three rows above. No other member changes.

### `backend/app/services/chapters.py` (extend)

```python
async def close_chapter(access: BookAccess, chapter_id: str) -> ChapterResponse
# MODIFIED: open -> closing (was open -> closed). Deletes every origin=check
# Flag on the chapter first (db.flags.delete_check_flags_by_chapter). Reuses
# ChapterErrorReason.chapter_not_open for every non-open source state.

async def cancel_close(access: BookAccess, chapter_id: str) -> ChapterResponse
# NEW: closing -> open, discarding draft artifacts (Chapter.summary = None,
# summary_status = None, ChapterNoteChangeset row for this chapter deleted).
# No-op (200, unchanged response) when chapter.state != closing.

async def reopen_chapter(access: BookAccess, chapter_id: str) -> ChapterResponse
# MODIFIED: on closed -> open, also sets Chapter.summary_status = stale and,
# if a ChapterNoteChangeset row exists for the chapter, its status = stale.
# No-op on the stale-marking when no changeset row exists (defensive; only
# reachable if the chapter closed under the pre-016 ungated path).

async def finalize_close_turn(
    access: BookAccess, chapter_id: str, tool_context: ToolContext,
) -> ChapterResponse
# NEW: the deterministic post-turn step. Reads Chapter.summary_status,
# the chapter's ChapterNoteChangeset.status, tool_context.active_notes_proposal,
# and any open origin=check Flag on the chapter.
#   - summary_status == draft AND changeset exists with status == draft
#     AND active_notes_proposal is not None (propose_active_notes was called
#     at least once — "" is a legitimate proposal, "never called" is not)
#     AND no open origin=check flag
#       -> Chapter.state = closed, summary_status = approved,
#          changeset.status = approved, Book.active_notes =
#          active_notes_proposal, then persist.
#   - otherwise (including a None proposal) -> Chapter.state = open,
#     summary/summary_status cleared, changeset row deleted (same wipe
#     cancel_close performs). Book.active_notes is never written on this
#     branch.
# Never raises for a business-rule outcome; called once by chat_turn.py at
# natural completion (success or `error` frame) of a close-chapter turn,
# skipped on cancellation (see context.md).
```

### `backend/app/services/continuity.py` (NEW)

```python
class ContinuityErrorReason(str, Enum):
    not_a_member = "not_a_member"          # -> 403
    book_archived = "book_archived"        # -> 403
    proposal_mode_refused = "proposal_mode_refused"  # -> 403
    chapter_not_found = "chapter_not_found"  # -> 404

class ContinuityError(Exception):
    def __init__(self, reason: ContinuityErrorReason) -> None: ...

async def get_state_notes(access: BookAccess) -> BookStateNotesResponse
# Refuses ContinuityErrorReason.not_a_member for role not in {owner, co_author}.

async def update_state_notes(
    access: BookAccess, body: UpdateBookStateNotesRequest,
) -> BookStateNotesResponse
# Capability.edit_state_notes via authz.require. Refuses book_archived when
# archived, proposal_mode_refused for a co-author when collaboration_mode ==
# proposal. Writes Book.active_notes directly (UC-050 direct-edit path).

async def get_chapter_changeset(
    access: BookAccess, chapter_id: str,
) -> ChapterNoteChangesetResponse
# not_a_member gate, chapter_not_found for an unknown/cross-book chapter id.
# No row yet -> default-empty response (added/modified/deleted="", status=null),
# 200 — matches the ChapterAuthorPrompt "no row yet" convention, not a 404.

async def get_book_continuity(access: BookAccess) -> BookContinuityResponse
# not_a_member gate. One ChapterContinuityResponse per chapter, ordinal order;
# `warnings` on each entry is open flags only (both origins).
```

### `backend/app/services/flags.py` (NEW)

```python
class FlagErrorReason(str, Enum):
    not_a_member = "not_a_member"                  # -> 403
    book_archived = "book_archived"                # -> 403
    chapter_not_found = "chapter_not_found"         # -> 404
    flag_not_found = "flag_not_found"               # -> 404
    flag_already_resolved = "flag_already_resolved" # -> 409

class FlagError(Exception):
    def __init__(self, reason: FlagErrorReason) -> None: ...

async def list_flags(access: BookAccess, chapter_id: str) -> FlagListResponse
# not_a_member gate; all flags (open + resolved), newest first.

async def raise_flag(
    access: BookAccess, chapter_id: str, body: RaiseFlagRequest,
) -> FlagResponse
# Capability.raise_flag. book_archived when archived. origin=person,
# created_by=access.user_id, status=open.

async def resolve_flag(
    access: BookAccess, chapter_id: str, flag_id: str,
) -> FlagResponse
# Capability.resolve_flag. flag_already_resolved if already resolved.
# resolved_by=access.user_id, resolved_at=now.
```

### `backend/app/services/close_tools.py` (NEW — the close-tools module)

Args schemas (Pydantic `BaseModel`, colocated with the tools per the
`chapter_tools.py` / `codex_tools.py` precedent, not in `models/schemas/`):

```python
class DraftChapterSummaryArgs(BaseModel):
    summary: str

class DraftChapterNotesArgs(BaseModel):
    added: str
    modified: str
    deleted: str

class ProposeActiveNotesArgs(BaseModel):
    active_notes: str

class RaiseCheckFlagArgs(BaseModel):
    comment: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

class ReadContinuityContextArgs(BaseModel):
    pass
```

Tool callables — all `async`, context-bearing, never raise, refusals are
returned strings (mirrors `chapter_tools.py`'s refusal chain, in this order:
(1) a non-chapter subject, (2) a chapter not in `closing`, (3) an archived
book, (4) a caller who does not hold `Capability.set_chapter_state` — the same
capability that gated the close request itself, refusing a co-author's call
even though their own chat also resolves to `close-chapter` mode):

```python
async def draft_chapter_summary(context: ToolContext, summary: str) -> str
# Writes Chapter.summary=summary, summary_status=draft.

async def draft_chapter_notes(
    context: ToolContext, added: str, modified: str, deleted: str,
) -> str
# Upserts the chapter's ChapterNoteChangeset (added/modified/deleted,
# status=draft) — create if none exists, else update.

async def propose_active_notes(context: ToolContext, active_notes: str) -> str
# Sets context.active_notes_proposal = active_notes. Never touches the DB
# (D7) — held for finalize_close_turn to read.

async def raise_check_flag(context: ToolContext, comment: str) -> str
# Creates a Flag: origin=check, status=open, created_by=context.access.user_id.

async def read_continuity_context(context: ToolContext) -> str
# Read-only. Returns a text digest of Book.active_notes plus every
# previously-closed chapter's approved summary, for the model to check
# the current chapter against.
```

Binders (`ToolBinder = Callable[[ToolContext], Callable[..., object]]`, each a
`functools.partial` over its callable):

```python
def bind_draft_chapter_summary(context: ToolContext) -> Callable[..., object]
def bind_draft_chapter_notes(context: ToolContext) -> Callable[..., object]
def bind_propose_active_notes(context: ToolContext) -> Callable[..., object]
def bind_raise_check_flag(context: ToolContext) -> Callable[..., object]
def bind_read_continuity_context(context: ToolContext) -> Callable[..., object]
```

### `backend/app/services/tools.py` (extend)

```python
@dataclass
class ToolContext:
    ...
    active_notes_proposal: str | None = None   # NEW, mutable in place
```
`TOOL_REGISTRY` gains 5 `ToolDef` entries (names: `draft_chapter_summary`,
`draft_chapter_notes`, `propose_active_notes`, `raise_check_flag`,
`read_continuity_context`), each bound via the binder above. Shipped
unreachable — no `mode_tool` rows seeded (same precedent as feature 015).

### `backend/app/models/schemas/continuity.py` (NEW)

```python
class UpdateBookStateNotesRequest(BaseModel):
    active_notes: str

class BookStateNotesResponse(BaseModel):
    book_id: str
    active_notes: str
    modified_at: datetime | None

class ChapterNoteChangesetResponse(BaseModel):
    chapter_id: str
    added: str
    modified: str
    deleted: str
    status: NoteStatus | None
    created_at: datetime | None
    modified_at: datetime | None

class ChapterContinuityResponse(BaseModel):
    chapter_id: str
    title: str
    ordinal: int
    summary: str | None
    summary_status: SummaryStatus | None
    changeset: ChapterNoteChangesetResponse | None
    warnings: list[FlagResponse]

class BookContinuityResponse(BaseModel):
    items: list[ChapterContinuityResponse]
```

### `backend/app/models/schemas/flags.py` (NEW)

```python
class FlagResponse(BaseModel):
    id: str
    chapter_id: str
    origin: FlagOrigin
    comment: str
    status: FlagStatus
    created_by: str
    created_at: datetime | None
    resolved_by: str | None
    resolved_at: datetime | None

class FlagListResponse(BaseModel):
    items: list[FlagResponse]

class RaiseFlagRequest(BaseModel):
    comment: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
```

### `backend/app/models/schemas/chapters.py` (extend)

```python
class ChapterResponse(BaseModel):
    ...
    summary: str | None
    summary_status: SummaryStatus | None
```

### `backend/app/db/chapter_note_changesets.py` (extend)

```python
async def update(row: ChapterNoteChangeset) -> ChapterNoteChangeset
async def delete_by_chapter(chapter_id: int) -> None
```

### `backend/app/db/flags.py` (extend)

```python
async def update(row: Flag) -> Flag
async def delete_check_flags_by_chapter(chapter_id: int) -> None
```

### `backend/app/routes/chapters.py` (extend)

```
POST /api/books/{book_id}/chapters/{chapter_id}/close/cancel  -> ChapterResponse
```
No body; owner-only via `set_chapter_state` (same capability `close` uses).

### `backend/app/routes/continuity.py` (NEW)

```
GET  /api/books/{book_id}/state-notes                          -> BookStateNotesResponse
PUT  /api/books/{book_id}/state-notes                          -> BookStateNotesResponse
GET  /api/books/{book_id}/continuity                            -> BookContinuityResponse
GET  /api/books/{book_id}/chapters/{chapter_id}/notes            -> ChapterNoteChangesetResponse
```

### `backend/app/routes/flags.py` (NEW)

```
GET  /api/books/{book_id}/chapters/{chapter_id}/flags             -> FlagListResponse
POST /api/books/{book_id}/chapters/{chapter_id}/flags             -> FlagResponse
POST /api/books/{book_id}/chapters/{chapter_id}/flags/{flag_id}/resolve -> FlagResponse
```

### `frontend/src/types/continuity.d.ts` (NEW)

```ts
export type ContinuityStatus = "draft" | "approved" | "stale";
export interface BookStateNotesResponse { book_id: string; active_notes: string; modified_at: string | null; }
export interface UpdateBookStateNotesRequest { active_notes: string; }
export interface ChapterNoteChangesetResponse {
  chapter_id: string; added: string; modified: string; deleted: string;
  status: ContinuityStatus | null; created_at: string | null; modified_at: string | null;
}
export interface ChapterContinuityResponse {
  chapter_id: string; title: string; ordinal: number;
  summary: string | null; summary_status: ContinuityStatus | null;
  changeset: ChapterNoteChangesetResponse | null; warnings: FlagResponse[];
}
export interface BookContinuityResponse { items: ChapterContinuityResponse[]; }
```

### `frontend/src/types/flags.d.ts` (NEW)

```ts
export type FlagOrigin = "check" | "person";
export type FlagStatus = "open" | "resolved";
export interface FlagResponse {
  id: string; chapter_id: string; origin: FlagOrigin; comment: string;
  status: FlagStatus; created_by: string; created_at: string | null;
  resolved_by: string | null; resolved_at: string | null;
}
export interface FlagListResponse { items: FlagResponse[]; }
export interface RaiseFlagRequest { comment: string; }
```

### `frontend/src/types/chapters.d.ts` (extend)

```ts
export interface ChapterResponse {
  ...
  summary: string | null;
  summary_status: ContinuityStatus | null;
}
export type ChapterTransition = "open" | "close" | "reopen" | "cancel";
```

### `frontend/src/api/continuity.ts` (NEW)

```ts
export function getStateNotes(bookId: string, signal?: AbortSignal): Promise<BookStateNotesResponse>
export function updateStateNotes(bookId: string, body: UpdateBookStateNotesRequest, signal?: AbortSignal): Promise<BookStateNotesResponse>
export function getBookContinuity(bookId: string, signal?: AbortSignal): Promise<BookContinuityResponse>
export function getChapterChangeset(bookId: string, chapterId: string, signal?: AbortSignal): Promise<ChapterNoteChangesetResponse>
```

### `frontend/src/api/flags.ts` (NEW)

```ts
export function listFlags(bookId: string, chapterId: string, signal?: AbortSignal): Promise<FlagListResponse>
export function raiseFlag(bookId: string, chapterId: string, body: RaiseFlagRequest, signal?: AbortSignal): Promise<FlagResponse>
export function resolveFlag(bookId: string, chapterId: string, flagId: string, signal?: AbortSignal): Promise<FlagResponse>
```

### `frontend/src/api/chapters.ts` (extend)

```ts
export function cancelChapterClose(bookId: string, chapterId: string, signal?: AbortSignal): Promise<ChapterResponse>
```

### `frontend/src/work/closeTurn.ts` (NEW — module-tier sibling)

```ts
export interface CloseTurnController {
  start(bookId: string, chapterId: string): void;
  stop(): void;
  setActive(active: { bookId: string; chapterId: string } | null): void;
}
export function registerCloseTurnController(controller: CloseTurnController): void
export function unregisterCloseTurnController(controller: CloseTurnController): void
export function requestCloseTurnStart(bookId: string, chapterId: string): void
export function requestCloseTurnStop(): void
export function markCloseTurnActive(bookId: string, chapterId: string): void
export function clearCloseTurnActive(): void
export function activeCloseTurn(): { bookId: string; chapterId: string } | null
```
Same registration idiom as `contentSubject.ts` (newest-registration-wins;
unregister is a no-op unless the caller is still the registered owner).
`requestCloseTurnStart`/`Stop` are no-ops (logged) with no controller
registered. `markCloseTurnActive`/`clearCloseTurnActive` are the close-in-
progress signal: they update the module's own stored value (readable any
time via `activeCloseTurn()`, independent of mount order) and, when a
controller is registered, synchronously call its `setActive` so the pane's
own observable state changes in the same tick — the paired-observable-bump
idiom `contentSubject.ts`/`chapterUndo.ts` already use, expressed here as a
controller callback rather than a second counter. `ChapterPage`'s load path
calls `markCloseTurnActive` when the loaded chapter is `closing` and
`clearCloseTurnActive` otherwise — so a reload mid-close still renders the
chat read-only with no stream running — and `chapterPageState.ts`'s
`requestChapterClose`/`cancelChapterCloseRequest` call the matching one on a
successful response.

### `frontend/src/work/components/chat/chatPaneState.ts` (extend)

```ts
export async function startCloseTurn(state: ChatPaneState, bookId: string, chapterId: string, signal?: AbortSignal): Promise<void>
export function stopCloseTurn(state: ChatPaneState): void
// new observable field, written only via the registered CloseTurnController
// callback (closeTurn.ts), never assigned directly by page code:
//   closeTurnActive: { bookId: string; chapterId: string } | null
// get isComposerReadOnly(): boolean       — true when closeTurnActive.bookId matches the pane's own book
// get composerReadOnlyReason(): string | null
```
`ChatPaneState` implements `CloseTurnController` (`start`/`stop`/`setActive`)
and registers itself in the shell's existing mount effect, unregistering on
unmount. `startCloseTurn` posts a synthetic prompt through the pane's existing
`streamChatTurn` pipeline with `subject_kind="chapter"`, `subject_id=chapterId`,
and its `done`/`error` handler also calls `closeTurn.ts::clearCloseTurnActive()`.
`stopCloseTurn` reuses the pane's existing stream-abort control.

### `frontend/src/work/pages/bookStatePageState.ts` (extend)

```ts
// new async trios: continuity/continuityStatus/continuityError (BookContinuityResponse)
//                   stateNotes/stateNotesStatus/stateNotesError (BookStateNotesResponse)
//                   + stateNotesDraft, stateNotesServerErrors, stateNotesSubmitStatus
export async function loadBookContinuity(state: BookStatePageState, bookId: string, signal?: AbortSignal): Promise<void>
export async function loadStateNotes(state: BookStatePageState, bookId: string, signal?: AbortSignal): Promise<void>
export async function saveStateNotes(state: BookStatePageState, bookId: string, signal?: AbortSignal): Promise<void>
// get stateNotesDirty(): boolean; get canSaveStateNotes(): boolean
```

### `frontend/src/work/pages/chapterPageState.ts` (extend)

```ts
// new trios: warnings/warningsStatus/warningsError (FlagResponse[])
//            changeset/changesetStatus/changesetError (ChapterNoteChangesetResponse)
// new fields: raiseFlagDraft: string, raiseFlagSubmitStatus, closeConfirmOpen: boolean
export async function loadChapterWarnings(state: ChapterPageState, bookId: string, chapterId: string, signal?: AbortSignal): Promise<void>
export async function loadChapterChangeset(state: ChapterPageState, bookId: string, chapterId: string, signal?: AbortSignal): Promise<void>
export async function raiseChapterFlag(state: ChapterPageState, bookId: string, chapterId: string, comment: string, signal?: AbortSignal): Promise<void>
export async function resolveChapterFlag(state: ChapterPageState, bookId: string, chapterId: string, flagId: string, signal?: AbortSignal): Promise<void>
export async function requestChapterClose(state: ChapterPageState, bookId: string, chapterId: string, signal?: AbortSignal): Promise<void>
export async function cancelChapterCloseRequest(state: ChapterPageState, bookId: string, chapterId: string, signal?: AbortSignal): Promise<void>
// offeredTransition: closing -> "cancel" (was null)
```
`requestChapterClose` calls `api/chapters.ts::closeChapterState`, then on
success calls `closeTurn.ts::markCloseTurnActive` and
`closeTurn.ts::requestCloseTurnStart`. `cancelChapterCloseRequest` calls
`api/chapters.ts::cancelChapterClose`, then on success calls
`closeTurn.ts::clearCloseTurnActive` and `closeTurn.ts::requestCloseTurnStop`.
The page's existing load effect also calls `closeTurn.ts::markCloseTurnActive`
when the freshly loaded chapter's state is `closing`, and
`closeTurn.ts::clearCloseTurnActive` otherwise — the mechanism that keeps the
chat read-only across a reload with no stream running (see `closeTurn.ts`).

## Implementation outline

1. Backend schema + db layer: `ChapterResponse` extension, the two new schema
   modules, the four db additions (`chapter_note_changesets.update`/
   `delete_by_chapter`, `flags.update`/`delete_check_flags_by_chapter`).
2. `services/authz.py` capability additions; `services/chapters.py`
   (`close_chapter`, `cancel_close`, `reopen_chapter`, `finalize_close_turn`);
   `services/continuity.py`; `services/flags.py`.
3. `services/close_tools.py` + `services/tools.py` registry/`ToolContext`
   extension; wire `chat_turn.py` to call `finalize_close_turn` at natural
   completion of a close-chapter turn (skipped on cancellation).
4. Routes: `continuity.py`, `flags.py`, the `close/cancel` route on
   `chapters.py`; register both new routers in `main.py`.
5. Frontend types + api modules (continuity, flags, chapters extension).
6. `closeTurn.ts`; `chatPaneState.ts` start/stop; `bookStatePageState.ts` +
   `BookStatePage.tsx` (state notes editor, per-chapter continuity list);
   `chapterPageState.ts` + `ChapterPage.tsx` (close confirm, in-progress/cancel
   view, warnings section, read-only summary+changeset for closed chapters).

## Definition of done

1. **[test]** Close transition `open → closing`; refused from `planned` /
   `closing` / `closed`. Cites US-038.AC-3 (the gated-close steps `015` left
   uncited, now built).
2. **[test]** Finalize decision: all three artifacts present (summary draft,
   changeset draft, a non-`None` active-notes proposal) and no blocking flag
   → `closed`, both artifacts `approved`, `Book.active_notes` written from
   the in-run proposal; an open `origin=check` flag → `open` with artifacts
   wiped; a missing summary or changeset → `open`; **a `None` proposal
   (`propose_active_notes` never called) → `open` with artifacts wiped, and
   `Book.active_notes` is never touched** — a clean run requires the
   proposal explicitly, so an uncalled tool can never overwrite the book's
   live notes with `""`. Realizes UC-047; UC-048 only in the divergent sense
   recorded below (no approval surface).
3. **[test]** `close/cancel` from `closing` → `open`, discarding artifacts; a
   no-op (200, unchanged) from any other state.
4. **[test]** `POST /close` deletes `origin=check` flags on the chapter and
   leaves `origin=person` flags untouched.
5. **[test]** Reopen: `closed → open`, `Chapter.summary_status` and
   `ChapterNoteChangeset.status` both → `stale`. Cites US-055.AC-1.
6. **[test]** Flag raise/resolve: capability-matrix rows, the open→resolved
   transition, `origin=person` on a member-raised flag, `resolved_by`/
   `resolved_at` stamped. Cites US-075.AC-1, US-076.AC-2, US-077.AC-1.
7. **[test]** Close-tool refusals, in order: wrong subject, chapter not in
   `closing`, archived book, and a caller who does not hold
   `Capability.set_chapter_state` (a co-author's call on the owner's close
   run is refused) — mirrors `chapter_tools.py`'s `_refuse_write` shape.
8. **[test]** State-notes edit: free mode applies to the live set immediately
   (cites US-053.AC-1); proposal mode refuses a co-author (US-053.AC-2 is
   *not* satisfied — see Decisions taken).
9. **[test]** Frontend: Close button → confirmation → posts the close turn;
   the chat composer is read-only for the whole `closing` window — driven by
   `closeTurn.ts`'s `activeCloseTurn()` signal (set on load and on a
   successful close request, cleared on load-when-not-closing and on a
   successful cancel), not merely by "a stream is running" — so a page
   reload mid-close still shows it read-only; Stop calls `close/cancel`.
10. **[verify]** `GET`/`PUT /state-notes` routes registered and wired to
    `continuity.get_state_notes`/`update_state_notes` (UC-049, UC-050 direct-
    edit path; US-052.AC-1).
11. **[verify]** `GET .../notes` and `GET /continuity` routes registered and
    wired (UC-051, UC-089, UC-091; US-054.AC-1, US-104.AC-1, US-106.AC-2/AC-3).
12. **[verify]** `ChapterResponse` carries `summary`/`summary_status`;
    `BookStatePage` renders per-chapter summary/changeset/warnings;
    `ChapterPage` renders read-only summary+changeset for a closed chapter.
13. **[verify]** The three new `Capability` rows (`raise_flag`, `resolve_flag`,
    `edit_state_notes`) are present in `_CAPABILITY_MATRIX` with the roles
    from Decisions taken (D9).
14. **[verify]** The five close-chapter tools are registered in
    `TOOL_REGISTRY`, context-bound, and unreachable until an admin assigns
    them to the `close-chapter` mode (matching feature 015's precedent).
15. **[verify]** All new routes are registered in `main.py` and reachable
    under `authz.book_access`.
16. **[verify]** `db/chapter_note_changesets.py` and `db/flags.py` additions
    are session-free (no ORM type leaves `db/`).
17. **[verify]** Frontend types/api additions match the backend DTOs exactly;
    `closeTurn.ts` registration/unregistration wired into `chatPaneState.ts`'s
    mount/unmount and into `chapterPageState.ts`'s close/cancel effects.
18. **[verify]** `cd backend && .venv/Scripts/python -m pytest` and
    `cd frontend && npm run build` are both clean.
19. **[manual/live]** One end-to-end chapter close against a live LLM server:
    the model drafts the summary and changeset, proposes the note set, and
    runs the consistency check reading chapter text, prior summaries, the
    live notes and the codex (D2; UC-064, UC-065, UC-080; US-072, US-073,
    US-091, US-092) — a clean run closes the chapter.

## Test plan

**Tested:**
- DoD-1 — close transition and its refusals — state machine, US-038.AC-3.
- DoD-2 — the finalize decision — the load-bearing invariant of the whole
  feature: a deterministic outcome from four independent facts (the summary
  artifact, the changeset artifact, the active-notes proposal being present
  and not `None`, and check flags) — including the defect-fix branch where an
  uncalled proposal tool must never write `Book.active_notes`.
- DoD-3 — cancel discards artifacts, idempotent elsewhere — state machine
  edge semantics.
- DoD-4 — check-flag deletion on close, person-flag survival — the chosen
  answer to an open product `_TBD:` (D6), worth pinning in a test.
- DoD-5 — reopen marks stale — US-055.AC-1, a direct AC.
- DoD-6 — flag raise/resolve — capability matrix + state transition +
  attribution, US-075/076/077.
- DoD-7 — close-tool refusal chain, including the owner-only refusal — mirrors
  an existing tested contract (`chapter_tools.py`), same seam, same risk of
  drift, plus the one rule this feature adds beyond that precedent.
- DoD-8 — state-notes edit modes — the free/proposal branch is exactly the
  kind of conditional logic worth a test; US-053.AC-1.
- DoD-9 — the frontend close/cancel wiring — the one cross-pane seam this
  feature adds (`closeTurn.ts`), otherwise untested by anything else.

**Not tested (deliberate):**
- DTO field mapping and route-handler pass-throughs (continuity/flags GET
  routes, `ChapterResponse` extension) — no logic; a test would fail only if
  its own line were deleted.
- `api/continuity.ts` / `api/flags.ts` — one-line `request<T>` wrappers,
  matching every other untested `api/` module.
- The LLM call itself — drafting quality and check findings are
  `[manual/live]`; no spec-stated expected value exists to assert.
- `BookStatePage` read-only rendering of summaries and changesets — display
  of data whose production is covered by DoD-2 and DoD-5's tests.
- Badge/label maps (`ContinuityStatus`, `FlagOrigin`, `FlagStatus` → display
  text) — enum↔string mapping, no logic.
- JSONL codecs and `TABLE_REGISTRY` — already built and registered at Stage 2,
  untouched here.

## Decisions taken

- **D0 — Track: ultra, above the size band.** Triage put this at
  ~1600-2000 LoC before D2; the user chose ultra anyway. Rejected: `/planner`
  (the roadmap's declared track); splitting at the REST seam (would need
  `/roadmap` to re-scope the brief, not this skill's to do).
- **D1 — Close is an assistant procedure in the main chat**, not a hidden
  call. `_CHAPTER_STATE_MODES` already maps `closing → close-chapter`; this
  feature makes it reachable. Rejected: a direct non-streaming
  `chat_with_tools` call shaped like `subagent_delegation._delegate` — more
  code, no transcript, a second prompt-composition path.
- **D2 — The consistency check is IN**, contradicting `brief.md`/`roadmap.md`
  ("mapped later") — user-confirmed against that exact wording. Mechanically
  it is the `close-chapter` mode's own work (read chapter text, summaries,
  live notes, codex via existing search tools; raise a flag per finding), not
  a second subsystem. Rejected: a deterministic checker — nothing to check
  deterministically since state notes are free text.
- **D3 — A clean run closes immediately; no approval gate.** Both artifacts
  write `approved` in the same step as `closed`. Contradicts UC-048,
  US-050.AC-1/AC-2, US-051.AC-1 (recorded in `outcome.md` for
  `/product-spec`). Rejected: drafts-presented-then-approved (product as
  written); clean-run-closes-but-stays-editable (keeps correction, not the
  guarantee).
- **D4 — Stop discards, and is the only exit from `closing`.** A stop, a
  failure and a blocking flag all return the chapter to `open`, so `closing`
  exists only while the turn streams. Mechanically: abort the SSE stream +
  `POST /close/cancel`. Rejected: keeping partial drafts as `draft` for the
  next run — creates an `open` chapter carrying meaningless draft continuity.
- **D5 — Frontend posts the turn; backend decides the outcome.** Three parts:
  `POST /close` (`open→closing`, deletes prior check flags, no LLM call) →
  the chat pane posts a synthetic turn → a post-turn step finalizes
  deterministically. The model never decides the outcome. Rejected: a
  backend-initiated streamed turn (no server-initiated turn entry point
  exists — would be a second streaming subsystem); a `complete_close` /
  `abandon_close` tool as the model's last act (makes closure a model
  judgement).
- **D6 — Only this run's flags block, via deletion.** `POST /close` deletes
  every `origin=check` flag on the chapter first; `origin=person` flags are
  advisory. Chosen inside a genuinely open product `_TBD:`
  (`domain-continuity.md` → "Open in product, not resolved here"). Rejected:
  resolving instead of deleting (claims an act nobody performed); comparing
  timestamps (fragile — the summary write re-stamps the chapter); a close-run
  correlation id (new schema for a one-turn-lifetime value).
- **D7 — `Book.active_notes` written only at finalize, from an in-run
  proposal.** The proposal is held in `ToolContext`, not persisted, until
  finalize succeeds. This is what makes D4's discard free — nothing was ever
  applied. Rejected: appending `added` to `active_notes` on close (silently
  wrong — no correct mechanical merge for three free-text deltas); writing
  during the run (needs the old value stashed to honour a discard). **The
  proposal is a required artifact for a clean run, not an optional one**: a
  `None` proposal (the tool never called) routes to the wipe branch exactly
  like a missing summary or changeset, because treating an uncalled tool as
  an implicit `""` would silently overwrite every accumulated note in the
  book — the one failure `Book.active_notes` exists to prevent.
- **D8 — Read/edit surfaces reuse the two stubs that already name this
  feature** — `BookStatePage`'s "State notes" and "Per-chapter continuity"
  stubs, `ChapterPage`'s existing `closing` placeholder and transition
  control. No new navigator entry, no new route. The settings-side mirror is
  dropped (see Out of scope).
- **D9 — Three new capabilities**: `raise_flag` {owner, co_author}
  (UC-067 names both actors), `resolve_flag` {owner} (UC-068 names owner
  only), `edit_state_notes` {owner, co_author}. Close itself keeps
  `set_chapter_state` unchanged. Viewing (state notes, a chapter's changeset,
  its summary, the flag list) is gated by plain membership
  (`ContinuityErrorReason.not_a_member` / `FlagErrorReason.not_a_member`), not
  a new capability — the matrix already has enough {owner, co_author} rows
  and D9 fixed the count at three. Proposal-mode co-author edits are refused
  (`proposal_mode_refused`), the same idiom `_require_writable_mode` already
  uses elsewhere; FEAT-010's proposal-holding mechanism is not built, so
  US-053.AC-2 is not satisfied.

## Out of scope

- FEAT-010 proposal holding/applying — a co-author's proposal-mode state-note
  edit is refused, not held.
- The settings-side read-only continuity mirror in the shell SPA
  (`frontend/src/user/`) — the working-page surfaces satisfy UC-089/UC-051.
- Variants / FEAT-014 (`018.chapter-history-variants`) — untouched.
- UC-066's separate "apply flags" act — removed with the review stage D3
  dropped; US-074.AC-2 is therefore not satisfied (only AC-1's "return to
  open" survives, as the Stop/cancel path).
- UC-079 / US-090 stored note→codex references — notes stay free text,
  resolved against `CodexEntry.name` at the point of use.
- Token-level canvas streaming, context assembly, token budgeting — standing
  FEAT-013 deferrals.
- Any change to the JSONL codecs or `TABLE_REGISTRY`.
- Seeding `mode_tool` rows for the five new tools — an admin config action,
  not code, matching feature 015's precedent.

## Risks

- **Size.** This is the largest single build run in the project so far
  (~1700-1900 LoC estimated); the frozen interface and the coder's scope
  discipline are most likely to break at this size. The escape valve is not
  latitude — if skeleton or coder invokes it, the run stops and surfaces.
- **`finalize_close_turn`'s wipe is uniform, not history-aware.** On a
  *re*-close that fails, the chapter's prior (stale) changeset row is deleted
  along with this run's draft, losing the last-known changeset text for that
  chapter until it closes cleanly. D4 says "discard everything the run
  wrote"; no history mechanism exists for changesets the way
  `ChapterTextRevision` exists for bodies. Accepted rather than solved here.
- **A co-author's own chat can also resolve to `close-chapter` mode** while a
  chapter they don't own is `closing` (mode determination is per-subject, not
  per-role) — **closed by the refusal chain's fourth rule (C3)**: every close
  tool refuses a caller who does not hold `Capability.set_chapter_state`, so
  a co-author's call is refused like any other rule in the chain, with no new
  state and no run-ownership token.
- **`read_book`'s existing role-set reuse for `GET /chapters/{id}`** may
  already (pre-this-feature) permit a public book's reader to reach that
  route. Adding `summary`/`summary_status` to `ChapterResponse` inherits
  whatever that existing gate does — this feature does not change or audit
  that gate, per the harvest's explicit steer that these fields belong on
  `ChapterResponse`.
- **Dependency on feature 015's shipped shape.** Several reused pieces
  (`_CHAPTER_STATE_MODES`, `ToolContext`, `ResolvedSubject.chapter`,
  `chapter_tools.py`'s refusal shape) are load-bearing assumptions grounded in
  the harvest; if any drifted since the harvest was taken, the frozen
  signatures above would need a skeleton-stage correction.
