### Realizes
FEAT-012, FEAT-016 (see the ids in `plan.md` header). This file is background for a
build session with **no conversation history** — read it and `plan.md` and start.

## Size, honestly

Orchestrator triage put this at ~1600-2000 LoC before D2 pulled the consistency
check in; the user chose ultra anyway (design-note D0). This plan does **not**
narrow scope to fit the ultra band. Treat it as one continuous build run, not a
step sequence — the Implementation outline orders work, it does not gate it.

## What exists today (landed at Stage 2 / feature 014 / feature 015) — do not rebuild

**Tables**, all present, columns nullable-and-unused where noted:
- `Chapter`: `state` (`planned|open|closing|closed` — `closing` UNUSED until this
  feature), `summary: str|None`, `summary_status: SummaryStatus|None`
  (`draft|approved|stale`), `version: int`, `text`, `sketch`.
- `ChapterNoteChangeset` (table `chapter_note_changesets`): `id`, `chapter_id`
  (FK, **unique** — 1:1), `added`/`modified`/`deleted` (free text),
  `status: NoteStatus|None` (`draft|approved|stale`), timestamps. **No `book_id`.**
- `Flag` (table `flags`): `id`, `chapter_id` (FK), `origin: FlagOrigin`
  (`check|person`), `comment`, `status: FlagStatus` (`open|resolved`),
  `created_by`/`created_at`, `resolved_by`/`resolved_at` (null until resolved).
  **No `book_id`** — resolve through the chapter.
- `Book.active_notes: str` — required, `""` at creation, **read by nothing
  today**. `Book.collaboration_mode: CollaborationMode` (`free|proposal`).

**JSONL codecs already registered** for `chapter_note_changesets` and `flags` in
`TABLE_REGISTRY` (`services/db_import_export.py`) — no import/export work here.

**The chapter service today** (`services/chapters.py`):
```
async def open_chapter(access: BookAccess, chapter_id: str) -> ChapterResponse
async def close_chapter(access: BookAccess, chapter_id: str) -> ChapterResponse
async def reopen_chapter(access: BookAccess, chapter_id: str) -> ChapterResponse
```
`close_chapter` today: refuses unless `state == open`, then sets `state =
closed` **directly** (skips `closing`) — a comment in the module names this
feature as the owner of the `closing` destination. `_require_open_slot_free`
already treats `closing` as slot-holding (forward-compatible, currently
unreachable). `ChapterErrorReason` (frozen taxonomy): `not_found`,
`not_planned`, `invalid_reorder_set`, `chapter_not_open`, `stale_version`,
`book_archived`, `proposal_mode_refused`, `chapter_not_closed`,
`another_chapter_open`. `_CHAPTER_ERROR_STATUS` in `routes/chapters.py` maps
each to a status; this feature adds no new member (`close_chapter`'s new
`open→closing` destination and `cancel_close`'s no-op reuse existing reasons).

`ChapterResponse` / `ChapterTextResponse` (`models/schemas/chapters.py`)
**deliberately omit `summary`/`summary_status`** — a docstring names this
feature as the owner. This plan adds both fields to `ChapterResponse`.

**Authorization** (`services/authz.py`): `Capability` enum + `_CAPABILITY_MATRIX:
dict[Capability, frozenset[AccessRole]]` + `authz.require(access, capability)`.
Existing members relevant here: `set_chapter_state` ({owner}, unchanged by this
feature), `write_chapter_text` ({owner, co_author}). No `raise_flag` /
`resolve_flag` / continuity capability exists yet. Collaboration-mode and
archived-book gates are **service-level checks**, not matrix rows (the matrix
has no vocabulary for either) — this feature's `edit_state_notes` proposal-mode
refusal and archived-book refusal follow that same layering, not a matrix
dimension.

**Mode determination is already wired for this feature** (`services/
assistant_runtime.py`, feature 015): a chapter in `closing` already resolves to
the `close-chapter` `AssistantMode` — this feature is what makes that mapping
reachable, by being the first thing that ever puts a chapter into `closing`.

**Tool registry** (`services/tools.py`): `TOOL_REGISTRY: list[ToolDef]`, frozen
dataclass `ToolDef(name, description, args_schema, callable, binder)`. Context-
bearing tools are built via `ToolContext` + a `binder: Callable[[ToolContext],
Callable]`. Existing `ToolContext` fields: `book_id: int`, `access: BookAccess |
None`, `subject: ResolvedSubject | None`, `emit_frame: FrameEmitter | None`.
`ResolvedSubject` carries a `.chapter` member. Chapter tools from feature 015
(`services/chapter_tools.py`) — read saved body, replace whole body, replace
selection, append — are the shape this feature's close-tools module copies:
mode-gated, registered in `TOOL_REGISTRY`, **shipped unreachable** until an
admin assigns them to a mode's `mode_tool` rows (no seeding here either).

**No server-initiated non-streaming turn entry point exists.**
`services/chat_turn.py::run_turn(context, prompt) -> AsyncGenerator[TurnFrame,
None]` is the sole turn runner — an author-driven SSE generator. This feature
does **not** add a second turn runner: the close procedure is an ordinary turn
in this runner, with a **new deterministic step invoked once the generator
reaches natural completion** (success or an `error` frame) for a close-chapter
turn. A true client disconnect/cancellation skips that step — recovery is the
new `close/cancel` endpoint. `run_turn`'s own signature does not change.

**Non-streaming LLM call precedents exist but are NOT the pattern here**
(`services/embedding.py::embed_batch`, `services/subagent_delegation.py::
_delegate`) — design-note D1 explicitly rejected a direct `chat_with_tools`
call in that shape; the close procedure is an ordinary streamed turn instead.

## Frontend, as built

**Routes** (`frontend/src/work/routes.tsx`) — no new route is added by this
feature (design-note D8): everything hangs off `/work/:bookId/state` and
`/work/:bookId/chapter/:id`, which already exist.

**`BookStatePage.tsx` + `bookStatePageState.ts`** — renders book fields,
members, the caller's system prompt, and two **stubs** naming this feature as
owner: a "State notes" stub and a "Per-chapter continuity" stub. Existing
trios: `bookDetail`/`Status`/`Error`, `systemPrompt`/`Status`/`Error` (+draft/
serverErrors/submitStatus). This feature adds two more trios (state notes,
per-chapter continuity) plus their effects, following the same shape.

**`ChapterPage.tsx` + `chapterPageState.ts`** — header with lifecycle `Badge`,
one transition control, sketch editor (`planned` only), body editor (`open`
only, `@mantine/tiptap`, remount-by-key for external writes), the caller's
chapter prompt. Transition contract:
```ts
export type ChapterTransition = "open" | "close" | "reopen";
get offeredTransition(): ChapterTransition | null   // closing/unloaded → null today
get transitionUnavailableReason(): string | null
```
The `closing` placeholder text today, verbatim: *"This chapter is closing. The
close approval step is not built yet, so its state cannot be changed here."*
This feature replaces that with the in-progress view + cancel control, and adds
`"cancel"` to `ChapterTransition`. No confirmation dialog exists today (this
feature adds one before `close`); the transition control is offered to every
member regardless of role today — server 403/409 surface through
`transitionError`, unchanged.

**Draft-until-saved / restore buffer** (`restoreBuffer.ts`) — **does not apply**
to anything this feature adds: state notes, summaries, changesets and warnings
are all short server round-trips through their own async trios, not large
content-pane artifacts with a version token. No buffer involvement.

**The module tier** (`src/work/`, plain functions, none reactive):
`restoreBuffer.ts`, `activeChat.ts`, `contentSubject.ts` (canvas targets +
selection), `chapterUndo.ts`. This feature adds a **fifth sibling**,
`closeTurn.ts` — the registry that lets `ChapterPage`'s close/cancel controls
reach the chat pane's turn-posting logic without React context or a
cross-page callback (the same problem `contentSubject.ts` already solved for
canvas writes; this is the same shape applied to "post a turn").

**`api/chapters.ts` exports today** (all `(bookId, ..., signal?)`):
`listChapters`, `getChapter`, `createChapter`, `updateChapterSketch`,
`removeChapter`, `reorderChapters`, `get/updateOwnChapterSystemPrompt`,
`getChapterText`, `updateChapterText`, `openChapterState`,
`closeChapterState` (currently posts straight `open→closed`; this feature
changes only the **server's** behavior behind it, not its signature),
`reopenChapterState`.

**Test harness**: `renderWithProviders(ui, { route? })`
(`tests/support/render.tsx`); `api/` modules are mocked directly
(`vi.mock("../../src/api/chapters", () => ({...}))`), never `fetch`.

## The four divergences from `docs/product/` this feature bakes in

Full reasoning is in `plan.md` → Decisions taken and in `outcome.md`. Load-bearing
summary for anyone building without that context:

1. **No approval gate.** A clean run closes the chapter and writes both
   artifacts `approved` in the same step — no review/edit/approve surface.
   Contradicts UC-048, US-050.AC-1/AC-2, US-051.AC-1 as product states them.
2. **Consistency check is IN** (UC-064/065/080), though `brief.md` /
   `roadmap.md` say "mapped later" — the user confirmed it in, in this
   session, against that exact wording.
3. **US-053.AC-2 not satisfied** — a co-author's state-note edit in
   proposal-mode is refused (403), not held as a proposal (FEAT-010 doesn't
   exist yet).
4. **`POST /close` deletes prior `origin=check` flags** rather than resolving
   them — chosen inside a product `_TBD:` domain-continuity.md leaves open.

## Assistant-runtime facts this feature depends on, unchanged by it

- Four-layer system-prompt composition (base/mode/author/chapter) — untouched.
- Three-case tool gating: mode-bearing subject → exactly its `mode_tool` rows
  (zero rows = empty allowlist, not the whole registry). The five new tools
  this feature adds are **unreachable until an admin assigns them** to
  `close-chapter` — same as feature 015's four chapter tools shipped.
  Seeding no `mode_tool` rows is deliberate and is not this feature's job.
- `chat_with_tools` owns the tool loop; canvas frames ride the same
  `asyncio.Queue` `run_turn` already pumps — no manual-loop swap needed here
  either, because none of this feature's tools stream token-by-token.
- The five SSE frames (`thinking`/`delta`/`done`/`error`/`canvas`) are
  unchanged; this feature adds no new frame type.
