# Feature 015 — chapter-writing-free-mode

| Step | File                                    | Status  | Verifier | Date |
|------|-----------------------------------------|---------|----------|------|
| 001  | `001.chapter-body-service.md`           | done    | PASS     | 2026-07-30 |
| 002  | `002.chapter-state-transitions.md`      | done    | PASS     | 2026-07-30 |
| 003  | `003.chapter-write-routes.md`           | done    | PASS     | 2026-07-30 |
| 004  | `004.chapter-write-api.md`              | done    | PASS     | 2026-07-30 |
| 005  | `005.chapter-body-editor.md`            | done    | PASS     | 2026-07-30 |
| 006  | `006.chapter-page-body.md`              | done    | PASS     | 2026-07-30 |
| 007  | `007.chapter-buffer-reconciliation.md`  | done    | PASS     | 2026-07-30 |
| 008  | `008.chapter-state-controls.md`         | done    | PASS     | 2026-07-30 |
| 009  | `009.chapter-canvas-protocol.md`        | done    | PASS     | 2026-07-30 |
| 010  | `010.chapter-tools.md`                  | done    | PASS     | 2026-07-30 |
| 011  | `011.work-module-tier-chapter.md`       | done    | PASS     | 2026-07-30 |
| 012  | `012.chapter-canvas-wiring.md`          | done    | PASS     | 2026-07-30 |
| 013  | `013.chapter-prompt-composition.md`     | done    | PASS     | 2026-07-30 |

## Files Changed

### Step 001 — chapter body DTOs, the two write capabilities, the read/save service
- `backend/app/models/schemas/chapters.py` — `ChapterTextResponse` / `UpdateChapterTextRequest` (declarative; landed with the skeleton, unchanged here)
- `backend/app/services/authz.py` — `Capability.set_chapter_state` / `write_chapter_text` + their two matrix rows (declarative; landed with the skeleton, unchanged here)
- `backend/app/services/chapters.py` — filled the six 015 bodies: `_require_not_archived`, `_require_writable_mode`, `_to_text_response`, `_compute_placement`, `get_chapter_text`, `save_chapter_text`; added the imports they need (`chapter_changes` / `chapter_text_revisions` db modules, `BookState`, `CollaborationMode`, `ChangeStatus`, `ChapterChange`, `ChapterTextRevision`)

### Step 002 — open / close / reopen in the chapter service
- `backend/app/services/chapters.py` — filled the four step-002 bodies: `_require_open_slot_free` (loads `db/chapters.list_by_book`, skips the acted-on row by id, refuses on any other chapter in `open` **or** `closing`), `open_chapter` (`not_planned` refusal, slot guard, → `open`), `close_chapter` (`chapter_not_open` refusal, → `closed` directly), `reopen_chapter` (`chapter_not_closed` refusal, slot guard, → `open`). No import added, no signature changed, no new reason or capability minted; all three touch `state` + `modified_at` only

### Step 003 — the body and transition handlers on the chapter router
- `backend/app/routes/chapters.py` — filled the five step-003 handler bodies: `get_chapter_text`, `update_chapter_text`, `open_chapter`, `close_chapter`, `reopen_chapter`. Each is one `try` around its single `chapters_service` call, with `except authz.BookAuthorizationError → _map_authz_error` first and `except chapters_service.ChapterError → _map_chapter_error` second — the module's existing idiom. No signature, path, method, decorator or docstring changed; the six appended `_CHAPTER_ERROR_STATUS` rows and the two added imports were already complete from the skeleton and were verified, not rewritten. No second router, prefix or mapper; `main.py` untouched; no business logic, capability check, DB access or state inspection in the module

### Step 004 — the body DTOs and the five write functions in `api/chapters.ts`
- `frontend/src/types/chapters.d.ts` — `ChapterTextResponse` / `UpdateChapterTextRequest` (declarative; landed complete with the skeleton, verified against the wire contract and left unchanged here — `state` reuses 014's `ChapterLifecycleState`, `version` / `expected_version` are `number`)
- `frontend/src/api/chapters.ts` — filled the five step-004 bodies, each a single `request<T>` call off the existing `const BASE` with `signal` forwarded: `getChapterText` (`GET …/text`), `updateChapterText` (`PUT …/text`, the only one with a request body), `openChapterState` / `closeChapterState` / `reopenChapterState` (`POST …/open` | `…/close` | `…/reopen`, no request body). Deleted the skeleton's `unimplemented` sink. No signature, docstring, import or path changed; no error handling, retry or refusal parsing added; 014's eight functions untouched, `listChapters` / `reorderChapters` still resolving to the whole `ChapterListResponse` envelope

### Step 005 — the editor dependency set and the `ChapterBodyEditor` component
- `frontend/package.json` — **unchanged by this step**: the six pinned dependencies (`@mantine/tiptap@^7.17`, `@tiptap/react` / `@tiptap/pm` / `@tiptap/starter-kit` / `@tiptap/extension-link` at `^2.27.2`, `tiptap-markdown@^0.8.10`) landed complete with the skeleton. Verified against the declared ranges and left alone — no version moved, no package added, no install run
- `frontend/src/work/components/chapter/ChapterBodyEditor.tsx` — filled the single component body and deleted the `unimplemented` sink. `useEditor` (the library's own hook, no deps array → the instance is created once, so `initialMarkdown` is read exactly once per mount, D15) with `immediatelyRender: true`, `extensions: [StarterKit, Link, Markdown]`, `content: initialMarkdown`, and `editorProps.attributes = { role: "textbox", "aria-label": ariaLabel }` so the ProseMirror-owned editable node carries the accessible name. `onUpdate` → `onChange((editor.storage.markdown as MarkdownStorage).getMarkdown())` — Markdown out, never HTML/JSON; `onSelectionUpdate` → `onSelectionChange("")` on an empty selection, otherwise `doc.textBetween(from, to, "\n")` — the callback always fires. Renders `RichTextEditor` → `Toolbar` (two `ControlsGroup`s: `Bold` / `Italic`, then `H2` / `BulletList`) → `Content`. No `useEffect`, no `useState`, no ref, no `setContent`, no `editable` flag, no fifth prop, no `api/` import, no local styling; the frozen stylesheet import, the prop interface and the component signature are byte-identical to the freeze

### Step 006 — the chapter page's body region: load, edit, save
- `frontend/src/work/pages/chapterPageState.ts` — filled the six step-006 bodies and deleted the `unimplemented` sink; added the `UpdateChapterTextRequest` type import the save payload needs. `bodyDirty` (`bodyDraft !== (body?.text ?? "")`), `canEditBody` (`body?.state === "open"` — the **body response's** state, never `chapter.state`), `canSaveBody` (`bodyStatus === "ready"` && `canEditBody` && `bodyDirty` && `bodySubmitStatus !== "loading"`, no emptiness rule). `loadChapterBody` — the `loadChapter` shape one field down, seeding `body` / `bodyDraft` / **`bodyBaseVersion = response.version`** and bumping `bodyEditorGeneration` in **the one place this step bumps it**; touches neither other trio. `editBodyDraft` — one `runInAction` setting `bodyDraft`, **no** generation bump, no HTTP; the two frozen ids stay unread (voided with a comment naming step 007's buffer key). `saveChapterBody` — returns without contacting the server when `bodyBaseVersion === null`, else sends `{ text: bodyDraft, expected_version: bodyBaseVersion }` and re-seeds `body` / `bodyDraft` / `bodyBaseVersion` **from the response** with no generation bump; an `ApiError` (a `409` included, as an ordinary refusal) puts `err.message` into `bodyServerErrors` (4xx → `text`, 5xx → `form`, the `saveSketch` rule) and leaves the draft, the body and the base version untouched. No `clientErrors`, no conflict field, no `isReconciling`, no `applyDraft`, no buffer call; `makeAutoObservable(this)` keeps its no-argument form
- `frontend/src/work/pages/ChapterPage.tsx` — added the body section as a **sibling** of the chapter and prompt sections (never inside the chapter's success path) and joined the third load to the single mount `useEffect` / single `AbortController`; one added inner handler (`handleSaveBody`). Branches: loading (`Loader` + `Loading…`), load error (`Alert` "Could not load the chapter body" carrying `bodyError`), `open` (save-error `Alert` "Could not save the chapter body" listing `Object.values(bodyServerErrors)`, `ChapterBodyEditor` `key={state.bodyEditorGeneration}` / `initialMarkdown={state.bodyDraft}` / `onChange` → `editBodyDraft` / `onSelectionChange` a no-op / `ariaLabel="Chapter body"`, `Button` "Save body" `disabled={!state.canSaveBody}`), non-`open` (`resolveEditability(...).readOnlyReason` verbatim + the stored body through `react-markdown`'s default export with **no plugins**, and **no editor and no save control**). Three imports added (`react-markdown`, `ChapterBodyEditor` from `components/chapter/` — singular, `resolveEditability` from `../subject`, consumed not modified). 014's sections, its one `useState` instance and its existing handlers are unchanged; no `useCallback`/`useMemo`/`useReducer`, no custom hook, no context, no `useForm`

### Step 007 — the body's restore buffer and both reconciliation entrances
- `frontend/src/work/pages/chapterPageState.ts` — filled the one step-007 body and deleted the re-added `unimplemented` sink; added the single import line (`clearBuffer` / `readBuffer` / `restoreBufferKey` / `writeBuffer` from `../restoreBuffer`, consumed **unmodified**). `loadChapterBody` — **the load-time entrance**: after the body arrives, `readBuffer(restoreBufferKey(bookId, "chapter", chapterId))` (total read, no defensive parsing), `stale = buffered !== null && buffered.baseVersion !== body.version`; the draft is the buffered one when a buffer exists and the server's text otherwise, `bodyBaseVersion` is **the server's `version` in every branch**, the generation is bumped, and a mismatch puts the loaded response into `bodyConflict` + raises `isReconcilingBody` with **no save attempted**. `editBodyDraft` — reads the two frozen ids at last: after the draft write it calls `writeBuffer(key, text, state.bodyBaseVersion ?? "")` and records a `"saved-after-eviction"` result's `evictedKeys` in `evictedBufferKeys`, emptying the holder otherwise; still synchronous and server-free. `saveChapterBody` — two additions only: success now empties `evictedBufferKeys` and calls `clearBuffer(key)` after the re-seed, and the `catch` is re-shaped to `if (!(err instanceof ApiError)) throw err` + a **`409` branch** that re-fetches through `getChapterText` into `bodyConflict`, raises `isReconcilingBody` and resets `bodySubmitStatus` to `"idle"`, leaving the draft, the buffer and `bodyBaseVersion` untouched (a failed re-fetch falls back to the ordinary `form` refusal surface); every other `ApiError` keeps step 006's 4xx→`text` / 5xx→`form` surface verbatim. `resolveBodyConflict` — `"server"`: `clearBuffer`, adopt `bodyConflict` as `body` **and** its `version` as `bodyBaseVersion`, re-seed `bodyDraft` from it, bump the generation, clear `bodyConflict` / `evictedBufferKeys` / `bodyServerErrors`, lower the flag, contact nothing; `"draft"`: **adopt the server's `body` + `version` FIRST**, leave the view, and only then `await saveChapterBody(...)` — no draft re-seed, no generation bump. No signature, field, computed or existing effect changed; `makeAutoObservable(this)` still no-argument; no `bufferKey` computed, no `BufferedDraft` widening, no sketch or prompt buffer, no third merged outcome
- `frontend/src/work/pages/ChapterPage.tsx` — added the divergence view and the eviction notice **inside the existing body `Stack`** (never an early `return`, so the chapter, sketch and prompt sections keep rendering) and two inner handlers (`handleKeepServerBody` / `handleKeepDraftBody`). Branch order inside the body section is now loading → load-error → **`state.isReconcilingBody`** → the `canEditBody` fork, so the divergence view replaces both the editor and `Save body` while open. The view: `Title` **`Unsaved changes diverged`**, a `color="yellow"` `Alert` titled **`This chapter's body changed since your draft`** saying nothing has been merged and to choose a version, then `Group grow` over two `Paper withBorder` panes — **`Current server version`** (`state.bodyConflict?.text ?? ""`) and **`Your draft`** (`state.bodyDraft`), both as `pre-wrap` raw text, never through `react-markdown` — each with exactly one `Button` (**`Keep the server version`** / **`Keep my draft`**), neither pre-selected, no third control. The eviction notice is a `color="yellow"` `Alert` titled **`Other unsaved drafts were removed`** rendered whenever `evictedBufferKeys` is non-empty, independently of the divergence flag, naming each evicted key as text. One import added (`Paper`) plus `resolveBodyConflict`; no modal / drawer / overlay / portal / focus trap, no `red`, no diff library, no highlighting, no merged pane; the single mount `useEffect`, its one `AbortController` and every 014 / step-006 branch are unchanged

### Step 008 — open / close / reopen on the chapter page
- `frontend/src/work/pages/chapterPageState.ts` — filled the two step-008 computeds and the three transition effects, and deleted the re-added `unimplemented` sink. `offeredTransition` — a `switch` over **`this.chapter?.state`** (the CHAPTER's, never `body.state` and never a caller-role signal): `planned` → `"open"`, `open` → `"close"`, `closed` → `"reopen"`, and `null` for `closing` **and** for the not-yet-loaded / failed-load case, so exactly one control is ever offered. `transitionUnavailableReason` — `null` when `chapter === null` or a transition IS offered, otherwise the frozen sentence verbatim (`This chapter is closing. The close approval step is not built yet, so its state cannot be changed here.`). The three effects (`openChapterState` / `closeChapterState` / `reopenChapterState`) each `await` one module-private `runChapterTransition(state, bookId, chapterId, thunk, signal)` — **not exported, not a fourth effect**, and the api call arrives as a thunk so the `chaptersApi` namespace is read at call time. Its one contract: `transitionStatus = "loading"` + `transitionError = null`; on `ApiError` `transitionError = err.message` (plain-string `detail` — **no `serverRefusalText`, no `details.detail.message` path**) with the `"Could not change the chapter state."` fallback, `transitionStatus = "error"` and **nothing else touched anywhere**; on success `state.chapter = response` **whole** (never a local `state.chapter.state` patch) and then a **hand-written body re-read** through `chaptersApi.getChapterText` setting `body` / `bodyStatus` only — deliberately **not** `loadChapterBody`, so the body draft, the restore buffer, `bodyBaseVersion`, `bodyEditorGeneration` and the three reconciliation fields are all untouched; a failed re-read lands in `bodyError` / `bodyStatus = "error"` while `transitionStatus` stays `"ready"` and `transitionError` stays `null`. No import added, no signature, field, computed or existing effect changed; `makeAutoObservable(this)` still no-argument
- `frontend/src/work/pages/ChapterPage.tsx` — added the one transition control **inside the chapter header's existing `Group`, beside the ordinal and the state `Badge`**, rendered only when `state.offeredTransition !== null` (never rendered-and-disabled; `disabled` carries `transitionStatus === "loading"` alone), with the visible action word from a module-private `TRANSITION_LABELS` record (`Open` / `Close` / `Reopen`) and `aria-label={\`${label} chapter: ${chapter.title}\`}` — the visible label contained in the accessible name. Directly beneath that group, still inside the header `Stack`: the `color="red"` `Alert` titled **`Could not change the chapter state`** carrying `state.transitionError` verbatim, and `state.transitionUnavailableReason` as a dimmed `Text` (the `sketchDisabledReason` shape) with **no control beside it**. One added inner handler (`handleTransition`) dispatching on `state.offeredTransition` to exactly the matching effect, with no fallback. Three added effect imports plus a `ChapterTransition` type import; **no `useCallback`/`useMemo`, no new `useEffect`, no new `AbortController`, no `Modal`/`Drawer`/`Dialog` and no confirmation of any kind**. 014's, step 006's and step 007's branches are otherwise unchanged; the page docstring's "no chapter-state transition control (step 008)" line was replaced by the delivered contract. `ChaptersPage.tsx`, `chaptersPageState.ts`, `BookHubPage.tsx` and the navigator were not opened (D19)

### Step 009 — the `op` frame field, the selection on the wire, the chapter branch of `determine_mode`
- `backend/app/models/schemas/chats.py` — **unchanged by this step**: `CanvasOp`, `CanvasFrame.op = "replace"` and `TurnRequest.selection_text` are declarations and landed complete with the skeleton. Verified rather than rewritten (`CanvasField` still exactly `("name", "body")` — no `"text"` member; a frame built with no `op` carries `"replace"`, one built with `"append"` / `"replace_selection"` carries what it was given)
- `backend/app/services/tools.py` — **unchanged by this step**: `ToolContext.selection_text` is a defaulted frozen-dataclass field and landed complete with the skeleton. `ToolContext(book_id=…)` still constructs; no role, mode or book-state field was added (`access` already carries all three); no registry entry added
- `backend/app/services/assistant_runtime.py` — filled the two unimplemented bodies. `_mode_for_chapter_state` — `None` state → `None`, otherwise `_CHAPTER_STATE_MODES.get(state.value if isinstance(state, ChapterState) else str(state))`, so `open` → `write-chapter`, `closing` → `close-chapter`, and `planned` / `closed` fall through the absent keys to `None` (the mode-key constant is read, never inlined). `_chapter_within_book` — `_entry_within_book`'s three-way rule verbatim on the chapter side: `int(subject_id)` inside `try/except (TypeError, ValueError)` → `None`, `await chapters.get_by_id(...)`, and `None` for an unknown row **or** one whose `book_id` differs from `access.book_id`, so `resolve_subject`'s chapter branch answers `NO_SUBJECT` and the cross-book read is refused **by resolution**. `ResolvedSubject.chapter`, `_CHAPTER_STATE_MODES`, `resolve_subject`'s chapter branch and `determine_mode`'s restructured guard (`entry` → `chapter` → fall-through, i.e. "resolved to nothing at all") landed with the skeleton and were preserved exactly. Tool gating untouched: `allowed_tool_names(None)` still returns exactly `("web_search",)`; nothing seeds an `AssistantMode` or `mode_tool` row
- `backend/app/services/chat_turn.py` — wired the selection through, both legs, deleting both `Skeleton (015 step 009): … UNIMPLEMENTED` markers. `prepare_turn` now passes `selection_text=request.selection_text if request is not None else None` onto the returned `TurnContext` (a `None` request keeps the 011 answer); `run_turn` now passes `selection_text=context.selection_text` on the `tools_service.ToolContext(...)` construction it already builds for the codex tools, beside `book_id` / `access` / `subject` / `emit_frame`. No signature changed, no validation, no persistence, no second carrier; `TurnFrame` and the `emit_frame` closure untouched. `services/codex_tools.py` and `routes/chats.py` were not opened

### Step 010 — the four chapter tools and the assistant's refusal mirror
- `backend/app/services/chapter_tools.py` — filled the two private helpers, the four tool callables and the four binders; deleted every `NotImplementedError` and every `Skeleton (015 step 010): UNIMPLEMENTED` marker. `_resolved_chapter` returns `context.subject.chapter` (a `None` subject → `None`), reading **only** the context: no book comparison, so a cross-book chapter stays refused by `resolve_subject` (DoD-9), and no `app.db` module, `services/chapters.py` or `codex_tools.py` is imported — the import block is byte-identical to the freeze. `_refuse_write` runs the **four** rules in the frozen order: no chapter subject → `_NOT_A_CHAPTER_MESSAGE`; `state != ChapterState.open` → `_CHAPTER_NOT_OPEN_MESSAGE.format(state=…)` with `.value` so the model reads `planned` rather than `ChapterState.planned` (a raw string still compares equal — `ChapterState` is a `str` enum); `access.book_state == BookState.archived` → `_BOOK_ARCHIVED_MESSAGE`; `access.role == AccessRole.co_author` **and** `collaboration_mode == CollaborationMode.proposal` → `_PROPOSAL_MODE_MESSAGE`. Both of the last two are field reads off `ToolContext.access` — no new plumbing, no second `BookAccess`, and a context with **no** access is refused by neither. **No fifth rule**: `context.selection_text` is never read. `read_chapter_text` returns `chapter.text` verbatim (no header) for a resolved chapter in **every** state and under an archived book / proposal-mode co-author — subject resolution only, never `_refuse_write`. The three writes are written out separately (no shared private emitter was added): refusal → return the string and emit **nothing**; no `emit_frame` → `_NO_STREAM_MESSAGE`; then **exactly one** `await emit_frame("canvas", CanvasFrame(subject_kind="chapter", subject_id=str(chapter.id), field="body", text=text, op=…))` with `op` `replace` / `replace_selection` / `append`, then the matching confirmation. Never-raise: each enumerated failure is its own named branch and an outer `except Exception` + `logger.warning(exc_info=True)` is the last line of defence only (`CancelledError` is a `BaseException` and still propagates). The four binders are one `functools.partial(fn, context)` each. **Nothing persists**: no table, no session, no `select()`, no seed. The module docstring's Skeleton paragraph was replaced by the shipped never-raise contract; no signature, constant, description, schema or docstring above it moved
- `backend/app/services/tools.py` — **unchanged by this step**: the four appended `ToolDef` entries (`read_chapter_text` / `set_chapter_text` / `update_selection` / `add_text`, all `binder`-bearing with `callable=None`) and the `chapter_tools` import block landed complete with the skeleton. Verified, not rewritten — 8 distinct names in the frozen order, the four new ones at indexes 4–7, `llm.pydantic_to_openai_tool` building for all four, and `build_tool_bindings(TOOL_REGISTRY, None)` still yielding exactly `['web_search']` in both maps. No existing entry, builder, ordering rule or `ToolContext` field touched; no `mode_tool` / `AssistantMode` row seeded anywhere

### Step 011 — the module tier learns about chapters
- `frontend/src/types/chats.d.ts` — **unchanged by this step**: `CanvasOp` and `CanvasFrame.op?` are declarations and landed complete with the skeleton. Verified, not rewritten — three values in the backend's order, `op` optional as the mirror of the backend's `"replace"` default, `CanvasField` still exactly `"name" | "body"`, and `TurnRequest` / `TurnSubject` untouched (step 012's)
- `frontend/src/work/subject.ts` — filled the **one** unimplemented case: `resolveEditability`'s `"chapter"` → `open` now returns `{ editable: "whole", readOnlyReason: null, editableRegions: ["chapter-text", "chapter-own-prompt"] }`. `editable` and `readOnlyReason` are byte-unchanged (which is what keeps `checkWritePermission(open, "whole")` allowing the body write); `"chapter-sketch"` is deliberately absent (UC-033's window is `planned` only). `planned` / `closing` / `closed` / the chapter `default` and the codex, Book-state, list and outer-default rows are untouched with their author-facing reason strings verbatim; `checkWritePermission`, `WriteRegion`, `LoadedSubject`, `SubjectKind` and `resolveSubjectPaneTarget` were not touched at all
- `frontend/src/work/contentSubject.ts` — filled the three step-011 widenings and deleted the `unimplemented` sink. **The selection registry**: one module-level `{ owner, selection }` slot; `setContentSelection` is a plain assignment where the newest caller wins outright, `currentContentSelection` reads the slot at call time (`null` when nothing is registered), and `clearContentSelection` is **identity-guarded on the page's own `ContentSubjectSource`**, so a superseded owner's clear is a no-op. `unregisterContentSubject` gained **exactly one line** — `clearContentSelection(source)` after its byte-unchanged subject clear. **The dispatcher**: resolves `const op = frame.op ?? "replace"` once at the top (the single place the backend default is mirrored), passes it as the third argument to a matching target's applier, and — with no target — drops **and logs** (`console.warn`) any frame whose resolved op is not `"replace"` **before** anything reaches a buffer key (D18), then buffers under `restoreBufferKey(bookId, frame.subject_kind, frame.subject_id)` inheriting `readBuffer(key)?.baseVersion ?? ""`. The kind-AND-id match, the `subject_id === null` drop and the `frame.field !== "body"` condition are unchanged (a chapter's body is also the `"body"` field). `CanvasDraftApplier`'s third optional parameter, `ContentSubject`, `ContentSubjectSource`, `ContentSubjectRegistration`, `registerContentSubject` and `currentContentSubject` are as frozen; `restoreBuffer.ts` is called, never modified
- `frontend/src/work/chapterUndo.ts` — filled all four bodies and deleted the `unimplemented` sink and the `void MAX_SNAPSHOTS` line. A module-level `Map<string, string[]>` keyed by the `(bookId, chapterId)` pair with a **NUL separator**, so no two pairs can collide — **in memory only, nothing reaches `localStorage`**. `pushChapterUndoSnapshot` appends and `splice`s the oldest away past `MAX_SNAPSHOTS` (20, still module-private); `popChapterUndoSnapshot` pops most-recent-first and returns `null` on an empty/absent stack (deleting the emptied entry), so a popped `""` stays distinguishable from "nothing to undo"; `chapterUndoDepth` is `?.length ?? 0` and never throws for an unknown pair; `clearChapterUndo` deletes one pair only. Nothing here clears on save (D6); no signature, docstring or the cap moved
- **Not modified, checked:** `frontend/src/work/pages/CodexEntryPage.tsx` and `frontend/src/work/pages/codexEntryPageState.ts` (DoD-13) — the shipped two-parameter codex applier satisfies the widened three-parameter type unedited; `frontend/src/work/restoreBuffer.ts`; every file under `frontend/tests/`

### Step 012 — the page applies canvas frames, pushes undo, and sends its selection
- `frontend/src/work/pages/chapterPageState.ts` — filled the two bound members and the two external effects, and deleted the `unimplemented` sink. `subjectSource` returns `{ kind: "chapter", entityId: this.chapterId, chapterState: this.chapter?.state }` — the object 014 built inline, read at CALL time and keyed on the **route's** id. `applyDraft` ignores a `"name"` frame outright, resolves `op ?? "replace"`, reads `bodyDraft` / `selectedText` **once**, and then: **THE REFUSAL FIRST** — a `"replace_selection"` frame whose selection is `null` **or** whose selected text the draft no longer contains puts the frame's text in `unappliedSelectionWrite` and **returns having changed nothing** (no undo push, no draft write, no buffer write, no generation bump; **no append fallback and never position zero**) — then the four frozen steps **in order**: `pushChapterUndoSnapshot(bookId, chapterId, draft)` on the **pre-write** text, the operation applied purely (`replace` → the text; `append` → `draft + text`; `replace_selection` → the **first** occurrence spliced), `editBodyDraft(this, bookId, chapterId, next)` — **step 006's single draft-edit path, so the restore buffer is written exactly as a keystroke writes it** — and only then `bodyEditorGeneration += 1` plus `unappliedSelectionWrite = null`. **Nothing reaches the server.** `setChapterSelection` stores `""` as `null` and calls `setContentSelection(state.subjectSource, state.selectedText)` — the same identity token the page registers with, which is what makes the unmount's shipped `clearContentSelection` land; it takes no ids and writes no buffer, no `localStorage` and no request (D5). `undoAssistantBodyWrite` pops, **returns changing nothing on `null`**, sets the popped text through the **same** `editBodyDraft` path and bumps the generation — **and pushes nothing**. Two imports added (`pushChapterUndoSnapshot` / `popChapterUndoSnapshot` from `../chapterUndo`, `setContentSelection` from `../contentSubject`, both **consumed unmodified**); no signature, field, computed or existing effect moved, and the four-key `makeAutoObservable` annotation is as frozen
- `frontend/src/work/pages/ChapterPage.tsx` — the mount effect now calls `registerContentSubject(state.subjectSource, state.applyDraft)` and `unregisterContentSubject(state.subjectSource)`, the inline `const source` closure and its `ContentSubjectSource` type import deleted (the instance owns the token, so the editor's render-time selection callback can reach it); the editor's `onSelectionChange` calls `setChapterSelection(state, selectedText)` in place of step 006's no-op, its other three props and `key={state.bodyEditorGeneration}` unchanged. Added the **undo control** beside `Save body` **in the same `Group`** — a `Button` whose accessible name and visible label are both exactly `Undo the assistant's last write`, `disabled={chapterUndoDepth(book, chapterId) === 0}` (read **directly from the module**, never through a `get` computed over a non-observable `Map`; the paired bump of the observable `bodyEditorGeneration` the same component reads for the editor's `key` is what schedules the re-render), **rendered-and-disabled** rather than absent when the stack is empty — and the **unapplied-write surface**: a `color="yellow"` `Alert` titled exactly `The assistant's write was not applied`, carrying the refused text verbatim plus one sentence saying nothing was selected so nothing was changed, rendered whenever `state.unappliedSelectionWrite !== null` **inside the body `Stack`, independently of every body branch**, exactly where step 007's eviction notice sits. One added inner handler (`handleUndoAssistantWrite`); two added imports (`chapterUndoDepth`, plus the two new effects). **No new `useEffect`, no second `AbortController`, no `useCallback`/`useMemo`, no custom hook, no context, no confirmation dialog**; 014's, step 006's, 007's and 008's branches are otherwise untouched, and the docstring's step-012 "must NOT render" paragraph was replaced by the delivered contract
- `frontend/src/types/chats.d.ts` — **unchanged by this step**: `TurnRequest.selection_text?: string | null` is declarative and landed complete with the skeleton. Verified rather than rewritten — a **flat** fifth field beside `subject_kind` / `subject_id` / `codex_kind`, and the frontend-only `TurnSubject` helper still exactly its three members
- `frontend/src/api/chats.ts` — two changes. (1) `streamChatTurn`'s body is now `{ prompt, ...subject, ...(selectionText == null ? {} : { selection_text: selectionText }) }`, so the key is **absent** unless there is a selection and a turn with a subject and none posts exactly the four fields `013` posted; the `void selectionText` sink and both SKELETON markers are gone and nothing else in the function moved (`refreshAuthToken()` first, the `streamPost` seam, the generic-event routing and the frame handlers are byte-unchanged; **`api/sse.ts` was not opened**). (2) **The authorised one-line-class fix** to the module-private `canvasFrame(data)` narrowing: it rebuilt the frame from four fields and **discarded `op`**, so every frame arriving over a live SSE stream read as `"replace"` — see `## Notes & Issues`. `op` is now narrowed and carried through; an **absent** one is left absent, which is exactly how the DTO expresses the backend's `"replace"` default (`dispatchCanvasFrame` applies it in its single place) so a codex frame is rebuilt with the shape it has always had; an unrecognised value drops the frame like any other malformed field rather than degrading to a whole-body overwrite
- `frontend/src/work/components/chat/chatPaneState.ts` — the send and the retry paths each gained **one argument**: `currentContentSelection() ?? undefined`, read **at send time / at retry time** in the same call site that already reads `turnSubject()`. Plus the one import. **`ChatPaneState` gained no selection field**, `turnSubject()` was not widened, no observer relationship to the content pane was created and nothing is passed down through the shell — the panes stay independent because nothing links them but a function call (UC-083)
- **Not modified, checked:** `frontend/src/work/contentSubject.ts`, `subject.ts`, `chapterUndo.ts`, `restoreBuffer.ts` and `api/sse.ts` (all **called**, none edited); `frontend/src/work/pages/CodexEntryPage.tsx` and `codexEntryPageState.ts` (untouched across the whole feature); `frontend/src/work/components/chapter/ChapterBodyEditor.tsx`; every file under `frontend/tests/`

### Step 013 — the caller's own chapter prompt as composition layer 4
- `backend/app/services/chat_turn.py` — filled `compose_turn_system_prompt` and landed the delegation, deleting both `Skeleton (015 step 013)` markers. The function loads the four layers off `TurnContext` alone and returns `prompt_composition.compose_system_prompt(base=BASE_SYSTEM_PROMPT, mode=…, author=…, chapter=…)`: the `mode_system_prompt(context.subject.mode_key)` read and the `book_author_prompts.get_by_book_and_user(chat.book_id, chat.author_id)` read moved here verbatim from `run_turn`, and **layer 4** is `chapter_author_prompts.get_by_chapter_and_user(context.subject.chapter.id, chat.author_id)` guarded by `context.subject.chapter is not None` alone — **no chapter-state check** (a prompt is the author's instruction, not chapter content) and **no `BookAccess`**: the identity is the chat's own author, layer 3's shape reused exactly (same identity, same direct `services → db` read, same absence of an access resolution), so another member's row for the same chapter is unreachable, the owner included. `Chapter.system_prompt` is not read. **No emptiness check was written**: a missing row and a `""` prompt both pass `None` / `""` into the composer's existing skip rule. `run_turn` now holds exactly `system = await compose_turn_system_prompt(context)` at that site; `mode_key = context.subject.mode_key` stays read there for step 3's tool gating, which is untouched. No signature changed, no import added (the skeleton's `chapter_author_prompts` namespace import is now live), and the two docstrings' Skeleton/`chapter stays null` paragraphs were replaced by the delivered contract
- **Not modified, checked:** `backend/app/services/prompt_composition.py` (called, never opened — its four-parameter signature, its label order and its skip rule are as harvested), `backend/app/db/chapter_author_prompts.py`, `backend/app/services/assistant_runtime.py`, `backend/app/routes/chats.py`; every file under `backend/tests/`

## Skeleton

### Step 001 — frozen interface (2026-07-30)

**`backend/app/models/schemas/chapters.py`** — two new DTOs beside 014's five; **none of 014's five is
touched** (`ChapterResponse` gains no `text`, D13).

- `backend/app/models/schemas/chapters.py` — `class ChapterTextResponse(BaseModel)` — **new** — fields in
  declaration order: `chapter_id: str`, `state: ChapterState`, `text: str`, `version: int`,
  `modified_at: datetime | None`
- `backend/app/models/schemas/chapters.py` — `class UpdateChapterTextRequest(BaseModel)` — **new** —
  `text: str` (no constraint — `""` is valid), `expected_version: int` (required; no force flag)

**`backend/app/services/authz.py`** — two appended `Capability` members + two appended
`_CAPABILITY_MATRIX` rows. No existing member, value, row or function changed; `BookAccess` gains no
field. Matrix and enum are both 15 wide (13 → 15).

- `backend/app/services/authz.py` — `Capability.set_chapter_state = "set_chapter_state"` — **new** —
  matrix row `frozenset({AccessRole.owner})` (open / close / reopen, UC-035..037 — one member for the one
  matrix row)
- `backend/app/services/authz.py` — `Capability.write_chapter_text = "write_chapter_text"` — **new** —
  matrix row `frozenset({AccessRole.owner, AccessRole.co_author})` (write into the open chapter, UC-038)

**`backend/app/services/chapters.py`** — 014's `_resolve_chapter`, `_to_response` and its six entry
points are reused **unchanged** (docstring amendments only, no signature or behavior change).

- `backend/app/services/chapters.py` — `ChapterErrorReason` — **changed** — four members **appended**
  after 014's three (which keep their names, values and order):
  `chapter_not_open = "chapter-not-open"`, `stale_version = "stale-version"`,
  `book_archived = "book-archived"`, `proposal_mode_refused = "proposal-mode-refused"`.
  Step 002 appends `chapter_not_closed` / `another_chapter_open`. `ChapterError.__init__(reason, message)`
  is unchanged.
- `backend/app/services/chapters.py` — `@dataclass(frozen=True) class _Placement` — **new** —
  `kind: PlacementKind`, `line_from: int | None`, `line_to: int | None`, `text: str`
- `backend/app/services/chapters.py` — `def _require_not_archived(access: BookAccess) -> None` — **new**
- `backend/app/services/chapters.py` — `def _require_writable_mode(access: BookAccess) -> None` — **new**
  (chapter-local; `services/codex.py` is copied in shape, never imported)
- `backend/app/services/chapters.py` — `def _to_text_response(chapter: Chapter) -> ChapterTextResponse` —
  **new**
- `backend/app/services/chapters.py` — `def _compute_placement(loaded_text: str, new_text: str) -> _Placement`
  — **new** (pure; sync)
- `backend/app/services/chapters.py` — `async def get_chapter_text(access: BookAccess, chapter_id: str) -> ChapterTextResponse`
  — **new**
- `backend/app/services/chapters.py` — `async def save_chapter_text(access: BookAccess, chapter_id: str, request: UpdateChapterTextRequest) -> ChapterTextResponse`
  — **new**

Imports added to `services/chapters.py`: `from dataclasses import dataclass`,
`from app.models.chapter_change import PlacementKind`, plus `ChapterTextResponse` /
`UpdateChapterTextRequest` on the existing `app.models.schemas.chapters` import.

- Caller-compile edits (out of Source-files scope): **None.** Every change is additive; no existing
  signature moved, so no call site needed touching.

#### Compile gate

- `cd backend && .venv/Scripts/python -c "import app.main"` → clean (no backend typecheck exists).
- `inspect.signature` / `model_fields` smoke check → all nine symbols above resolve as frozen.
- Regression: `python -m pytest tests/services/test_chapters.py tests/routes/test_chapters.py tests/services/test_authz.py` → **92 passed**.

#### Red-gate profile

- **Green by construction (declarative — expect PASS at the red gate, not a NotImplementedError):**
  **DoD-14**. The two `Capability` members and their two `_CAPABILITY_MATRIX` rows are complete now, and
  so is "no existing capability's role set changed". Likewise, a spec that only constructs
  `ChapterTextResponse` / `UpdateChapterTextRequest` or reads a `ChapterErrorReason` member will not fail
  — Pydantic DTOs, enum members and matrix rows are data, and a skeleton cannot leave them unimplemented.
- **Must be red (`NotImplementedError` from the stub):** **DoD-1 through DoD-13.** Every one of them
  drives `get_chapter_text` or `save_chapter_text`, both of which raise immediately, so the four private
  helpers are never reached. Expect the failure to surface as `NotImplementedError` on the entry point,
  **not** as an assertion mismatch and **not** as a `ChapterError`.
- A red-gate failure of the shape "expected `ChapterError(stale_version)`, got `NotImplementedError`" is
  the **correct** red for DoD-7/9/11/12; a test that passes there would mean it is not exercising the
  service.
- The stubs return no plausible value anywhere — `_compute_placement` and `_to_text_response` raise
  rather than returning an empty `_Placement` or a zeroed response, so no assertion can be accidentally
  satisfied.

### Step 002 — frozen interface (2026-07-30)

**`backend/app/services/chapters.py` is the only file touched.** 014's `_resolve_chapter` /
`_to_response` / six entry points and step 001's `_require_not_archived` / `_require_writable_mode` /
`_to_text_response` / `_compute_placement` / `get_chapter_text` / `save_chapter_text` are reused
**unchanged** — no signature moved, so no caller needed touching. **No new `Capability`** (all three
transitions take step 001's owner-only `Capability.set_chapter_state`), **no new `db/` function**, no
new DTO.

- `backend/app/services/chapters.py` — `ChapterErrorReason` — **changed** — two members **appended**
  after the existing seven, which keep their names, values and order (the enum is now **9** wide):
  `chapter_not_closed = "chapter-not-closed"` (reopen precondition → **409**),
  `another_chapter_open = "another-chapter-open"` (the one-open slot is held → **409**).
  `ChapterError.__init__(reason, message)` unchanged. The open transition mints **no** reason — it
  reuses 014's `not_planned`; the close transition reuses step 001's `chapter_not_open`. Both call
  sites supply their own message.
- `backend/app/services/chapters.py` — `async def _require_open_slot_free(access: BookAccess, chapter: Chapter) -> None`
  — **new** — the shared one-open guard. Loads `db/chapters.list_by_book(access.book_id)`, skips the
  acted-on row by `id`, raises `ChapterError(another_chapter_open)` if any other chapter is
  `ChapterState.open` **or** `ChapterState.closing` (D8's carve-out / CF1). Called by `open_chapter`
  and `reopen_chapter` — one guard, so DoD-3/4 and DoD-12/13 assert the same rule.
- `backend/app/services/chapters.py` — `async def open_chapter(access: BookAccess, chapter_id: str) -> ChapterResponse`
  — **new** — `require(set_chapter_state)` → `_require_not_archived` → `_resolve_chapter` →
  `not_planned` unless `planned` → `_require_open_slot_free` → `state = open` + `modified_at` →
  `chapters.update` → `_to_response`.
- `backend/app/services/chapters.py` — `async def close_chapter(access: BookAccess, chapter_id: str) -> ChapterResponse`
  — **new** — same prefix → `chapter_not_open` unless `open` → `state = closed` (**never** `closing`)
  + `modified_at` → `chapters.update` → `_to_response`. No slot guard: a close only releases the slot.
- `backend/app/services/chapters.py` — `async def reopen_chapter(access: BookAccess, chapter_id: str) -> ChapterResponse`
  — **new** — same prefix → `chapter_not_closed` unless `closed` → `_require_open_slot_free` →
  `state = open` + `modified_at` → `chapters.update` → `_to_response`.

No import was added — `Chapter`, `ChapterState`, `chapters`, `datetime`/`timezone`, `authz` and
`Capability` were all already imported by 014 / step 001.

- Caller-compile edits (out of Source-files scope): **None.** Every change is additive.

#### Compile gate

- `cd backend && .venv/Scripts/python -c "import app.main"` → clean (no backend typecheck exists).
- `inspect.signature` smoke check → the four symbols resolve as frozen and all four are `async`; the
  enum reports 9 members with the original seven unmoved; each stub raises `NotImplementedError`.
- Regression: `python -m pytest tests/services/test_chapters.py tests/services/test_chapter_text.py tests/routes/test_chapters.py` → **120 passed**.

#### Red-gate profile

- **Green by construction (declarative — expect PASS at the red gate, not a `NotImplementedError`):**
  nothing in the DoD list *in full*, but note that **the two new `ChapterErrorReason` members arrive
  complete**. Enum members are data; a skeleton cannot leave them unimplemented. So any assertion that
  merely *names* `ChapterErrorReason.chapter_not_closed` / `another_chapter_open` (or reads its value)
  resolves now — the red must come from the call that is supposed to *raise* it, never from an
  `AttributeError` on the enum. A spec whose only failure is a missing enum member is failing for the
  wrong reason.
- **Must be red (`NotImplementedError` from the stub):** **DoD-1 through DoD-18.** Every one drives
  `open_chapter`, `close_chapter` or `reopen_chapter`, all three of which raise immediately, so
  `_require_open_slot_free` is never reached and no state is ever written.
  - Caveat for **DoD-2, DoD-8 and DoD-16** (the authorization refusals): `authz.require` is **not**
    stubbed — it is shipped 009/014 code — but the entry point that would call it raises before
    reaching it, so these are red as `NotImplementedError`, **not** as
    `authz.BookAuthorizationError`. Expect the same for **DoD-15** (archived) and **DoD-18**
    (not-found): the guards and the resolver exist and work, yet the stub never calls them, so the
    red is `NotImplementedError` rather than `ChapterError(book_archived)` / `ChapterError(not_found)`.
  - A red-gate failure of the shape "expected `ChapterError(another_chapter_open)`, got
    `NotImplementedError`" is the **correct** red for DoD-3/4/12/13; a test that passes there would
    mean it is not exercising the service.
  - **DoD-17** ("state and `modified_at` only") and **DoD-5** ("at most one open across a sequence")
    are the two items that could pass vacuously against a stub — a stub writes nothing, so "nothing
    else changed" and "never two open" are trivially true. They must be written so the transition's
    own success assertion runs first (the state actually became `open` / `closed`), which is what
    makes them red here.
- The stubs return no plausible value anywhere: all four raise, so no assertion can be accidentally
  satisfied and no `ChapterResponse` with a wrong `state` can leak into a comparison.

### Step 003 — frozen interface (2026-07-30)

**`backend/app/routes/chapters.py` is the only file touched.** 014's `router`
(`APIRouter(prefix="/api/books", tags=["chapters"])`), its `_map_chapter_error` /
`_map_authz_error` helpers and its six handlers are reused **unchanged**. **No second router, no
second prefix, no second mapper, and `main.py` is not touched** — the router is already included.
No new DTO, no new service function, no new capability.

Imports added (one line each, into the existing `app.models.schemas.chapters` import block):
`ChapterTextResponse`, `UpdateChapterTextRequest`.

**The error→status map is real, not stubbed** — the 014 precedent recorded in its own status.md
("the error→status map + helper are real"). It cannot satisfy an assertion on its own, because all
five new handler bodies raise.

- `backend/app/routes/chapters.py` — `_CHAPTER_ERROR_STATUS: dict[chapters_service.ChapterErrorReason, int]`
  — **changed** — six rows **appended** after 014's three, which keep their keys, values and order.
  The map is now **9** wide and covers **every** `ChapterErrorReason` member (verified
  programmatically — 9 members, 9 rows, no missing key, no extra key):
  - `chapter_not_open` → `409`, `chapter_not_closed` → `409`, `another_chapter_open` → `409`,
    `stale_version` → `409`
  - `book_archived` → `403`, `proposal_mode_refused` → `403` — routed through
    **`_map_chapter_error`**, never `_map_authz_error`, so the service's typed message survives to
    the client verbatim (D11 / DoD-6 requires FEAT-010 to be named in the refusal text)
  - 014's `not_found` → `404`, `not_planned` → `409`, `invalid_reorder_set` → `400` — untouched

Handlers — five, appended **after** 014's six, in this **declaration order**, which is part of the
freeze. Every one takes `access: authz.BookAccess = Depends(authz.book_access)` as its last
parameter; **no handler declares `book_id`**; the response model is the **return annotation** and
`response_model=` appears nowhere in the module (only in its docstring's prose). All five are
`async` and all five bodies raise `NotImplementedError`:

- `@router.get("/{book_id}/chapters/{chapter_id}/text")` — `async def get_chapter_text(chapter_id: str, access: authz.BookAccess = Depends(authz.book_access)) -> ChapterTextResponse` — **new** — 200
  - calls `chapters_service.get_chapter_text(access, chapter_id)`
- `@router.put("/{book_id}/chapters/{chapter_id}/text")` — `async def update_chapter_text(chapter_id: str, payload: UpdateChapterTextRequest, access: authz.BookAccess = Depends(authz.book_access)) -> ChapterTextResponse` — **new** — 200
  - calls `chapters_service.save_chapter_text(access, chapter_id, payload)`. The **only** handler
    with a request body. `PUT` per D1 — the request replaces the whole resource.
- `@router.post("/{book_id}/chapters/{chapter_id}/open")` — `async def open_chapter(chapter_id: str, access: authz.BookAccess = Depends(authz.book_access)) -> ChapterResponse` — **new** — 200
  - calls `chapters_service.open_chapter(access, chapter_id)`
- `@router.post("/{book_id}/chapters/{chapter_id}/close")` — `async def close_chapter(chapter_id: str, access: authz.BookAccess = Depends(authz.book_access)) -> ChapterResponse` — **new** — 200
  - calls `chapters_service.close_chapter(access, chapter_id)`
- `@router.post("/{book_id}/chapters/{chapter_id}/reopen")` — `async def reopen_chapter(chapter_id: str, access: authz.BookAccess = Depends(authz.book_access)) -> ChapterResponse` — **new** — 200
  - calls `chapters_service.reopen_chapter(access, chapter_id)`

Each handler's body is one `try` around its **single** service call, with
`except authz.BookAuthorizationError → _map_authz_error` **first**, then
`except chapters_service.ChapterError → _map_chapter_error` — the module's existing idiom, which
the coder fills in.

Structural notes that are part of the freeze:

- **The three transitions take no request-body parameter at all** — they are commands, not
  representations (`003.context.md`). Confirmed in the mounted OpenAPI: `POST …/open`, `…/close`
  and `…/reopen` each carry **no `requestBody`** and only the `chapter_id` / `book_id` path params.
- **All five paths are `/{chapter_id}/<literal>`**, so none can shadow or be shadowed by anything in
  the family and 014's `/order`-before-`/{chapter_id}` rule is untouched. `chapters.router.routes`
  reports index 2 = `PUT …/chapters/order` (unmoved) and indices 6–10 = the five new routes in the
  order above.
- **`chapter_id` is `str`** on all five, matching 014 — the *service's* `_resolve_chapter` parses it
  and answers `not_found` for a non-numeric id.
- No business logic, no capability check, no DB access, no `session`/`select()` in this module.

#### Compile gate

- `cd backend && .venv/Scripts/python -c "import app.main"` → clean (root `CLAUDE.md` declares **no
  backend typecheck**, so the gate is import + smoke).
- Route-table smoke: the chapters router reports **11** routes in the declaration order above; the
  mounted OpenAPI reports the five new path/method pairs with `200` bound to `ChapterTextResponse`
  (×2) / `ChapterResponse` (×3), a request body on `PUT …/text` **only**.
- Map smoke: `ChapterErrorReason` has 9 members, `_CHAPTER_ERROR_STATUS` has 9 rows, set-equal.
- `inspect.signature` on the five handlers matches the freeze; all five are coroutine functions.
- Regression: `python -m pytest tests/routes/test_chapters.py tests/services/test_chapters.py
  tests/services/test_chapter_text.py tests/services/test_chapter_states.py` → **151 passed**.

#### Red-gate profile

- **Green by construction — produced by the dependency or the framework *before* any handler body
  runs, so a PASS there is not evidence the step is done:**
  - **DoD-15** — `401` with no token, all five routes: `Depends(authz.book_access)`.
  - **DoD-14** — `404` on a private book the caller has no relationship to, all five routes: the
    same dependency, and it is inherited, never re-derived here.
  - **DoD-17, first half** — `422` on a malformed `PUT …/text` body (missing `text`, missing
    `expected_version`, wrong type): step 001's `UpdateChapterTextRequest` validates before the
    body. Its "nothing is stored" clause is also vacuously true — nothing can be stored yet.
  - **DoD-17, second half** — "the three transitions accept a request with **no body at all**" is
    green *as a route declaration*: no `requestBody` exists, so no `422` is possible. **Write it as
    "not 422"**, because the handler behind it still raises — an assertion of `200` there is red,
    correctly.
- **Must be red (`NotImplementedError` → a 500 from the handler body):** **DoD-1 through DoD-13 and
  DoD-16.** Every one of them needs a handler body that reaches the service.
  - Caveat for the `403` items — **DoD-6** (proposal mode), **DoD-7** (archived), **DoD-8 / DoD-10**
    (co-author transitions) and **DoD-13** (non-member of a public book): `authz.require`, the
    archived gate and the mode gate are all shipped 001/002 code and all work, but the handler
    raises before calling the service, so these are red as a **500**, not as `403`. Same for the
    `409` items (**DoD-3, 5, 9, 11, 12**) and for **DoD-16**'s foreign-book `404` — that `404` is
    the *service's* resolver, not the dependency, so unlike DoD-14 it is **not** green here.
  - A red-gate failure of the shape "expected `409`, got `500`" is the **correct** red; a test that
    passes on a status-code assertion other than the four green-by-construction ones above is not
    exercising the handler.
- The stubs return no plausible value anywhere — all five raise, so no `ChapterTextResponse` or
  `ChapterResponse` with a wrong `state`, `text` or `version` can leak into a comparison. The one
  non-raising addition is the status map, which is data and cannot satisfy an assertion by itself.

- Caller-compile edits (out of Source-files scope): **None.** Every change is additive — no existing
  signature, path, method or map row moved, so no call site and no existing test needed touching.

### Step 004 — frozen interface (2026-07-30)

**Two files, both 014's, both extended — nothing renamed, nothing re-exported.** 014's seven DTOs and
its wire-level `ChapterLifecycleState` union are untouched; 014's eight `api/chapters.ts` functions are
untouched, **including `listChapters` / `reorderChapters` still resolving to the whole
`ChapterListResponse` envelope** (the sanctioned departure from `api/codex.ts` survives, DoD-6).
`src/work/subject.ts` is neither imported nor edited. No new module, no new `types/` alias — the
timestamp reuses `common.d.ts`'s `ISODateString`, imported by the file already.

**DTOs — `frontend/src/types/chapters.d.ts`** (appended after `UpdateChapterAuthorPromptRequest`;
declarative, wire-exact `snake_case`, ids `string`, no `any`, field order mirrors
`backend/app/models/schemas/chapters.py:104-154` exactly):

- `frontend/src/types/chapters.d.ts` — `export interface ChapterTextResponse` — **new** —
  `chapter_id: string`, `state: ChapterLifecycleState`, `text: string`, `version: number`,
  `modified_at: ISODateString | null`
  - `state` **reuses 014's `ChapterLifecycleState`** — no second union is declared, and the identically
    valued `ChapterState` in `work/subject.ts` is not reached for.
  - **`version` is `number`.** The string-id rule covers snowflakes, not a counter;
    `restoreBuffer.ts`'s `BufferBaseVersion = number | string` already accepts `number` for this field.
    Do not widen it.
  - No `book_id` (it is in the path) and **no `can_write`** (D14).
- `frontend/src/types/chapters.d.ts` — `export interface UpdateChapterTextRequest` — **new** —
  `text: string`, `expected_version: number`
  - No constraint on `text` (`""` is a legitimate body); `expected_version` required, **no force flag**.

**API — `frontend/src/api/chapters.ts`** (five appended functions; every body is **UNIMPLEMENTED** and
throws through a module-private `unimplemented(fn, ..._args): never` sink, which also consumes the
frozen parameter lists so they satisfy `noUnusedParameters` — the coder replaces each body with its
`request<T>` call and deletes the sink). Book id **first**, `signal?: AbortSignal` **last**, everything
through the shared `request<T>` from `./client`, paths built off the existing module-level
`const BASE = "/api/books"`. Two type imports added to the existing `../types/chapters` block
(`ChapterTextResponse`, `UpdateChapterTextRequest`); no other import added.

- `export async function getChapterText(bookId: string, chapterId: string, signal?: AbortSignal): Promise<ChapterTextResponse>`
  — **new** — `GET ${BASE}/${bookId}/chapters/${chapterId}/text`, 200, no request body
- `export async function updateChapterText(bookId: string, chapterId: string, body: UpdateChapterTextRequest, signal?: AbortSignal): Promise<ChapterTextResponse>`
  — **new** — **`PUT`** `${BASE}/${bookId}/chapters/${chapterId}/text`, 200. The **only** one of the
  five with a request body. Resolves to the response **unmodified** — no unwrap, no reshape (DoD-3).
- `export async function openChapterState(bookId: string, chapterId: string, signal?: AbortSignal): Promise<ChapterResponse>`
  — **new** — **`POST`** `${BASE}/${bookId}/chapters/${chapterId}/open`, 200, **no request body**
- `export async function closeChapterState(bookId: string, chapterId: string, signal?: AbortSignal): Promise<ChapterResponse>`
  — **new** — **`POST`** `${BASE}/${bookId}/chapters/${chapterId}/close`, 200, **no request body**
- `export async function reopenChapterState(bookId: string, chapterId: string, signal?: AbortSignal): Promise<ChapterResponse>`
  — **new** — **`POST`** `${BASE}/${bookId}/chapters/${chapterId}/reopen`, 200, **no request body**

**Naming decision (`004.context.md`).** Each of the five is named for *what it acts on* — the chapter's
`Text` or the chapter's `State` — in this module's own `<verb>Chapter<Field>` shape, the one
`updateChapterSketch` already uses. The text pair therefore matches 014's `updateChapterSketch` and the
backend handler names 1:1. The three transitions carry the `State` suffix rather than being
`openChapter` / `closeChapter` / `reopenChapter`: in an app whose vocabulary is panes, routes and
subjects, `openChapter(...)` reads as *navigating to* a chapter, which is exactly the misreading the
step context asks to avoid. `api/books.ts`'s `archiveBook` / `unarchiveBook` is the shape precedent for
a bodiless `POST` command returning the resource; only the noun differs, because there the whole book is
acted on and here it is one field of the chapter. Namespace-imported callers read
`chaptersApi.openChapterState(...)`.

Structural notes that are part of the freeze:

- **No error handling, no retry, no refusal parsing in this layer.** `request<T>` normalizes a non-2xx
  into `ApiError(status, message, details)`; the pages branch on `err.status === 409` vs `403` and read
  the server's reason text off it. Nothing here catches, inspects or re-wraps.
  - Carried forward from step 003's note: `_map_chapter_error` puts the refusal text on the wire as a
    **plain-string `detail`**, so a chapter refusal is `err.details.detail` (a string), **not**
    `err.details.detail.message` — that object path is the *codex* route family's. Step 006 must not
    copy `serverRefusalText` verbatim. This layer stores nothing about it either way.
- **`version` / `expected_version` are `number` end to end** — no `String(...)`, no `parseInt` anywhere
  in the two files.
- All five resolve to the server's shape as-is; **the api layer never unwraps a chapter response**, and
  the one place unwrapping was ever considered (the list envelope) stays un-unwrapped.

#### Compile gate

- `cd frontend && npx tsc --noEmit` → clean.
- `cd frontend && npm run build` (`tsc && vite build`) → clean, built in ~7s, all five entries emitted.
- `cd frontend && npm run test:types` → clean (014's `tests/user/chaptersApi.test.ts` still compiles
  against the unchanged eight).
- `npm test` was **not** run — the verifier owns it.

#### Red-gate profile

- **Green by construction (expect PASS at the red gate; a PASS there is *not* evidence the step is
  done):**
  - **DoD-6** — "014's eight functions are unchanged and the list function still returns the envelope".
    Structural: those functions are shipped 014 code, this step never opened them, and `listChapters`
    still resolves to `ChapterListResponse`. A spec asserting the envelope (`can_reorder` present, not a
    bare array) passes now and must keep passing — it is a regression guard, not a red-gate subject.
  - **DoD-7** — `npm run build` / `npm run test:types`. Both already pass against the stubs; a `.d.ts`
    is declarative and arrives **complete**, so the two new DTOs have nothing left unimplemented.
    Anything that merely *constructs* a `ChapterTextResponse` / `UpdateChapterTextRequest` literal, or
    reads a field off one, compiles and succeeds today.
- **Must be red (an `Error` with message `not implemented: <fn>` from the sink):** **DoD-1 through
  DoD-5.** All five stubs throw **before** touching `request<T>`, so:
  - **DoD-1 / DoD-2 / DoD-4** — the mocked `request` is **never called**; expect
    `expect(vi.mocked(request)).toHaveBeenCalledWith(...)` to fail with *zero* calls recorded. That
    "received: number of calls: 0" is the **correct** red for the path, the method, the forwarded
    signal and the bodiless transitions.
  - **DoD-3** — the save's returned shape cannot be compared at all: the call rejects instead of
    resolving. Expect the rejection, not a mismatch on `text` / `version`.
  - **DoD-5** — arming the mocked `request` to reject with a real `ApiError(409 | 403, …)` will **not**
    produce that error, because the stub never reaches the mock; the rejection is the plain
    `Error("not implemented: …")`. A spec asserting `err instanceof ApiError` fails here **correctly**.
    `ApiError` itself is real shipped `client.ts` code and is not stubbed — a spec that only constructs
    one will not fail, so the assertion must be on what the api function propagates.
  - A red-gate failure of the shape "expected `ApiError`/a recorded call, got `not implemented:
    updateChapterText`" is the **right** red; any of DoD-1..5 passing would mean the spec is not
    exercising the new function.
- **No plausible value is returned anywhere.** The sink's return type is `never` and every stub routes
  through it, so no `ChapterTextResponse` with a zeroed `version` or an empty `text`, and no
  `ChapterResponse` with a wrong `state`, can leak into a comparison. The only non-throwing additions
  are the two interfaces, which are erased at runtime and cannot satisfy an assertion by themselves.

- Caller-compile edits (out of Source-files scope): **None.** Every change is additive — no existing
  signature, DTO field or export moved, so no call site and no existing spec needed touching.

### Step 005 — frozen interface (2026-07-30)

**Two files, exactly the step's Source list**: `frontend/package.json` (six added dependencies) and the
**new** `frontend/src/work/components/chapter/ChapterBodyEditor.tsx`. `frontend/package-lock.json` also
changed — it is the build artifact of the install, not a source edit. No script, no dev dependency, no
engine field, no `vitest.config.ts`, no entry `main.tsx`, no `frontend/tests/support/`.

#### The dependency set — versions pinned, and the ranges read to justify them

The rule was *"read the peer range `@mantine/tiptap` declares for the Mantine major already in
`frontend/package.json`, and pin inside it"*. What was actually read (`npm view`, not assumed):

- `frontend/package.json` carries `@mantine/core` / `form` / `hooks` at **`^7.17`**, resolving to
  **7.17.8** (`npm ls @mantine/core` → `7.17.8`). `frontend.md`'s "v7.17" snapshot is confirmed.
- **`@mantine/tiptap@7.17.8` declares:** `"@mantine/core": "7.17.8"` (**exact**),
  `"@mantine/hooks": "7.17.8"` (exact), `"@tiptap/react": ">=2.1.12"`,
  `"@tiptap/extension-link": ">=2.1.12"`, `react`/`react-dom` `^18.x || ^19.x`.
- **The TipTap peer range is open at the top (`>=2.1.12`), so it does not by itself pick a major** —
  `@mantine/tiptap@8.3.18` declares the *identical* string. The major was therefore decided by the
  **second half of the rule**, which is decisive: `tiptap-markdown@0.9.0` peers `"@tiptap/core":
  "^3.0.1"` and `tiptap-markdown@0.8.10` (the last of the 0.8 line) peers `"@tiptap/core": "^2.0.3"`.
  A TipTap-2-targeting release **does** exist, so this is **not** the blocker case, and TipTap **2** is
  the major `@mantine/tiptap@7` was published against. **Pinned: TipTap 2.**
- `@tiptap/react@2.27.2` peers `react: ^17 || ^18 || ^19` → React 19.1 is in range, and
  `@tiptap/pm ^2.7.0` / `@tiptap/core ^2.7.0`, both satisfied at 2.27.2.

Pinned (installed, lockfile written, `npm install` exit 0 with **no** `ERESOLVE` and no peer warning):

| Package | Range in `package.json` | Resolved | Why it is in the set |
|---|---|---|---|
| `@mantine/tiptap` | `^7.17` | 7.17.8 | the widget; range written to match its three Mantine siblings so the exact-version peer can never split |
| `@tiptap/react` | `^2.27.2` | 2.27.2 | the React binding — declared peer of `@mantine/tiptap` |
| `@tiptap/pm` | `^2.27.2` | 2.27.2 | the ProseMirror bundle — declared peer of `@tiptap/react` |
| `@tiptap/starter-kit` | `^2.27.2` | 2.27.2 | the starter extension set |
| `@tiptap/extension-link` | `^2.27.2` | 2.27.2 | declared peer of `@mantine/tiptap` (its link control) |
| `tiptap-markdown` | `^0.8.10` | 0.8.10 | serialize/parse. **`^0.8.10` on a `0.x` means `>=0.8.10 <0.9.0`**, which is exactly the TipTap-2 line — the caret cannot drift onto 0.9.x/TipTap 3 |

`@tiptap/core@2.27.2` is present hoisted (via `@tiptap/starter-kit`) and satisfies `tiptap-markdown`'s
peer; it is deliberately **not** a direct dependency — nothing in the component imports it by name.

**Verified by construction, not by assumption** — a throwaway probe module (created inside `src/`,
typechecked, bundled through a throwaway `vite build --lib`, then **deleted**; neither file remains and
neither is in git status) proved that the whole set resolves, typechecks under this repo's `strict` +
`noUnusedLocals` tsconfig, and bundles: 921 KB JS + 10.6 KB CSS, rollup exit 0.

**Import specifiers the coder should use — harvested from that probe, all verified to compile:**
`import { RichTextEditor } from "@mantine/tiptap"` · `import { useEditor } from "@tiptap/react"` ·
`import StarterKit from "@tiptap/starter-kit"` (default) · `import Link from "@tiptap/extension-link"`
(default) · `import { Markdown } from "tiptap-markdown"` plus
`import type { MarkdownStorage } from "tiptap-markdown"`.
Markdown out is `(editor.storage.markdown as MarkdownStorage).getMarkdown()` — `tiptap-markdown@0.8.10`
declares **no** global augmentation of `Editor.storage`, so that cast is how the call stays free of
`any`. The accessible name reaches the ProseMirror-owned node through
`editorProps: { attributes: { "aria-label": …, role: "textbox" } }`, which typechecks against this major.
`RichTextEditor.Toolbar` / `.ControlsGroup` / `.Bold` / `.Italic` / `.H2` / `.BulletList` all resolve.

#### The frozen prop seam — `frontend/src/work/components/chapter/ChapterBodyEditor.tsx` (new file, new folder)

- `frontend/src/work/components/chapter/ChapterBodyEditor.tsx` — `export interface ChapterBodyEditorProps`
  — **new** — exactly four props, in declaration order:
  - `initialMarkdown: string` — read **ONCE at mount** (D15). Never watched; a later value reaches the
    document only because the page remounted the component under a new key.
  - `onChange: (markdown: string) => void` — the document serialized back to **Markdown** (never HTML,
    never ProseMirror JSON) on every author edit.
  - `onSelectionChange: (selectedText: string) => void` — the **plain text** of the current selection on
    every selection move. **An empty selection is the empty string `""`, and the callback still fires**
    — it is not skipped, and the parameter is not optional and not nullable. (D5: the page holds the
    selection client-side and sends its text as a flat field; nothing is persisted.)
  - `ariaLabel: string` — the accessible name of the **editable region**, so it is reachable by
    role/label. Named `ariaLabel` rather than `label` because it is an accessible name, not a visible
    form label; queries in this project are by role or label only, never by test-id.
- `frontend/src/work/components/chapter/ChapterBodyEditor.tsx` —
  `export const ChapterBodyEditor: React.FunctionComponent<ChapterBodyEditorProps>` — **new** — declared
  as
  `observer(function ChapterBodyEditor({ initialMarkdown, onChange, onSelectionChange, ariaLabel }: ChapterBodyEditorProps): ReactElement)`.
  Body is **UNIMPLEMENTED**: it routes all four props through a module-private
  `unimplemented(fn: string, ..._args: unknown[]): never` sink that throws
  `Error("not implemented: ChapterBodyEditor")` (the same sink shape step 004 used; the coder deletes
  it). The sink also consumes the frozen parameter list so `noUnusedParameters` stays satisfied.
- `frontend/src/work/components/chapter/ChapterBodyEditor.tsx` — `import "@mantine/tiptap/styles.css"`
  — **part of the freeze.** The **component** imports the stylesheet, not `work/main.tsx`, so the style
  ships with the only bundle that uses it and no entry file enters this feature's scope.

**Absent on purpose, and must stay absent** (each is a named decision, not an omission):

- **no `editable` / read-only prop** (D16 — a `planned` / `closing` / `closed` body renders through
  `react-markdown` on the page; this component mounts only for an `open` chapter);
- **no `ref`, no imperative `setContent`, no `useEffect`** (D15 — external draft writes re-sync by
  **remount** on a page-owned key counter);
- **no page state, no `bookId` / `chapterId`, no save concern, no `api/` import, no HTTP.** It is a leaf
  that knows nothing about chapters, books, saving or the assistant;
- **no fifth prop.** Steps 006 / 007 / 012 mock this module against exactly these four.

Only these two exports exist in the module. **`ChapterBodyEditorProps` is exported** precisely so the
three mocking specs can type their stub against it.

**Folder note:** the step's Source list says `components/chapter/` (singular) and that path is what
006 / 007 / 012 will `vi.mock`, so it was created verbatim. It now sits **beside 014's existing
`components/chapters/`** (plural, holding `ChapterOrderList.tsx`) — two sibling folders one letter
apart. Not a conflict and not a blocker; flagged so nobody "tidies" one into the other and silently
breaks three mock paths.

- Caller-compile edits (out of Source-files scope): **None.** The component is new and nothing imports
  it yet; the six dependencies are additive and no existing package, script or config moved.

#### Compile gate

- `cd frontend && npx tsc --noEmit` → clean.
- `cd frontend && npm run build` (`tsc && vite build`) → clean, built in ~7s, all five entries emitted.
- `cd frontend && npm run test:types` → clean.
- `npm install` → 70 packages added, **no `ERESOLVE`, no unmet peer**. `npm audit`'s 2 high-severity
  findings are **pre-existing** (`react-router` advisory) and unrelated to this set.
- `npm test` was **not** run — the verifier owns it.

#### Red-gate profile

**Only DoD-2, DoD-3 and DoD-4 are `[test]`. DoD-1 and DoD-5 … DoD-8 are `[manual/live]`** and get no
spec: the Markdown round-trip (DoD-5), the selection callbacks (DoD-6) and the theme inheritance
(DoD-7) are exactly the behaviours jsdom cannot drive (ProseMirror needs `Range.getClientRects` and real
layout rectangles), which is why `005.context.md` puts them there.

- **Already satisfied by the skeleton, so they will NOT go red — do not read a PASS as progress:**
  - **DoD-1** — the install and the majors landed with this freeze; `npm run build` passes **now**. It
    stays a `[manual/live]` check that the pinned ranges are the ones recorded above.
  - **DoD-8** — `npm run test:types` passes now.
  - `ChapterBodyEditorProps` is an interface: erased at runtime, complete by construction, and cannot
    satisfy or fail any assertion by itself. A spec that only imports the type proves nothing.
- **Must be red** — the component **throws on render**: `Error("not implemented: ChapterBodyEditor")`.
  React re-throws it out of `render()`, so RTL's `render(...)` itself blows up before any query runs.
  - **DoD-2** — expect the failure to be that thrown error, **not** a "unable to find an element with
    the label" query miss. A query-miss failure would mean the spec never reached the component.
  - **DoD-3** — same: the toolbar cannot render, so the control-by-role assertions never execute.
  - **DoD-4** — **this is the one that can pass vacuously.** A component that throws makes no network
    call and holds no state, so "no fetch happened" is trivially true against the stub. The spec must
    assert the successful mount **first** (the labelled editable region exists), and only then that
    nothing was requested — otherwise it is green at the red gate for the wrong reason.
  - There is no `api/` import in this module at all, so a `vi.mock` of an api module is not what makes
    DoD-4 meaningful; the mount assertion is.
- **No plausible value is returned anywhere.** The single sink's return type is `never`, so no element
  tree, no empty editor and no `""` Markdown can leak into a comparison, and the change/selection
  callbacks are never invoked — a spec asserting "`onChange` was called with Markdown" fails with zero
  calls recorded, which is the correct red.
- **jsdom caveat carried forward for the test-coder:** if mounting the real component later fails under
  jsdom for ProseMirror reasons, the minimal DOM stubs go **at the top of that spec's own file** —
  `frontend/tests/support/` and `vitest.config.ts` are in **no** step's source or test list. Faking
  editor internals to assert an emitted Markdown string is explicitly forbidden (it would test the
  test).

### Step 006 — frozen interface (2026-07-30)

**One file changed: `frontend/src/work/pages/chapterPageState.ts`.** The step's second Source file,
`frontend/src/work/pages/ChapterPage.tsx`, is **deliberately UNCHANGED by this freeze** — its only
symbol is `ChapterPage()` (zero props, unchanged), so it has no signature to freeze; its body section
is behaviour and is the coder's. The view surface it must present is specified below and is part of
the freeze because **queries in this project are by role or label only**, so an unfrozen accessible
name would break the air gap.

014's members are untouched: the chapter trio, the prompt trio, the sketch editor state, all six
existing computeds and all four existing effects (`loadChapter` / `saveSketch` / `loadSystemPrompt` /
`saveSystemPrompt`) keep their names, types, order and behaviour. Every addition is appended.
`frontend/src/work/subject.ts` is **consumed, not modified** (and not imported by anything new in the
state module — the read-only reason is the view's, see below). `restoreBuffer.ts` and
`contentSubject.ts` are untouched.

One import added: `ChapterTextResponse` on the existing `../../types/chapters` type-import block.
**`UpdateChapterTextRequest` is deliberately NOT imported yet** — a type used only by a throwing stub
would trip `noUnusedLocals`; the coder adds it when it writes the payload (shape fixed below).

#### The body trio — a THIRD trio, no aggregation type

- `frontend/src/work/pages/chapterPageState.ts` — `ChapterPageState.body: ChapterTextResponse | null = null` — **new**
- `frontend/src/work/pages/chapterPageState.ts` — `ChapterPageState.bodyStatus: "idle" | "loading" | "ready" | "error" = "idle"` — **new**
- `frontend/src/work/pages/chapterPageState.ts` — `ChapterPageState.bodyError: string | null = null` — **new**

`frontend.md`'s rule that three loadables means **three trios and no aggregation type** is honoured:
there is no combined status, no `pageStatus`, no `allLoaded`. The body is **not** folded into 014's
chapter trio — different endpoints (D13), independent failure in both directions (DoD-1).

#### The body draft state — the `021` form shape, no validation layer

- `frontend/src/work/pages/chapterPageState.ts` — `ChapterPageState.bodyDraft = ""` — **new** — the
  **Markdown** draft (D2). Written by exactly one function, `editBodyDraft`.
- `frontend/src/work/pages/chapterPageState.ts` — `ChapterPageState.bodyServerErrors: Record<string, string> = {}` — **new**
- `frontend/src/work/pages/chapterPageState.ts` — `ChapterPageState.bodySubmitStatus: "idle" | "loading" | "ready" | "error" = "idle"` — **new**
  - This is the step's "save status". It is named `…SubmitStatus` and carries the same four-value
    union as `sketchSubmitStatus` / `systemPromptSubmitStatus`, because `context.md` → "Form state
    shape" names the `021` shape as *a draft field, a `…ServerErrors` holder, a `…SubmitStatus`*, and
    the two siblings in this very file already use it. It is **not** the codex template's
    `"idle" | "saving" | "saved" | "error"`.
- `frontend/src/work/pages/chapterPageState.ts` — `ChapterPageState.bodyBaseVersion: number | null = null` — **new**
  - **The version comes from the BODY response and from nowhere else.** 014's `chapter.version` is
    never read — not here, not by the save. `null` before the first successful body load.
  - A **`number`**, not an ISO string — the one deliberate difference from the
    `codexEntryPageState.ts` template, and the case `restoreBuffer.ts`'s
    `BufferBaseVersion = number | string` has always had for step 007.
- `frontend/src/work/pages/chapterPageState.ts` — `ChapterPageState.bodyEditorGeneration = 0` — **new**
  - The **editor generation counter** (D15): a plain observable number the **view** keys
    `ChapterBodyEditor` on and reads for nothing else — never rendered, never compared, never
    persisted. Bumped by every **external** draft write; **never** by a keystroke.
  - **This step bumps it in exactly ONE place: `loadChapterBody`.** The save does **not** bump it (the
    draft it re-seeds is the one the editor already holds; remounting there would drop the caret for
    nothing). Steps 007 and 012 bump it from their own external writes.

**No `clientErrors`, no `errors` union** — every string, `""` included, is a valid body.

#### The three pure `get` computeds (all three throw in the skeleton)

- `frontend/src/work/pages/chapterPageState.ts` — `get bodyDirty(): boolean` — **new** — the draft
  differs from the loaded body; a not-yet-loaded body compares as `""`.
- `frontend/src/work/pages/chapterPageState.ts` — `get canEditBody(): boolean` — **new** — `true`
  **only** when **`this.body?.state === "open"`**. It reads the **BODY response's** state, never
  `chapter.state`: the body region gates itself without depending on which trio resolved first, which
  is exactly why `ChapterTextResponse` carries `state`.
- `frontend/src/work/pages/chapterPageState.ts` — `get canSaveBody(): boolean` — **new** —
  `bodyStatus === "ready"` **and** `canEditBody` **and** `bodyDirty` **and**
  `bodySubmitStatus !== "loading"` (DoD-5). **No emptiness check** — saving an empty body is allowed.

There is deliberately **no fourth computed** for the read-only reason: the Interface intent assigns
that to the **view** (`resolveEditability`, called in `ChapterPage.tsx`).

#### The three external effects — `(state, bookId, chapterId, …, signal?)`

Every body is **UNIMPLEMENTED**: each routes its frozen parameter list through a module-private
`function unimplemented(fn: string, ..._args: unknown[]): never` sink that throws
`Error("not implemented: <fn>")` (the sink shape steps 004 and 005 used). The sink also satisfies
`noUnusedParameters`; **the coder deletes it with the last stub.**

- `export async function loadChapterBody(state: ChapterPageState, bookId: string, chapterId: string, signal?: AbortSignal): Promise<void>`
  — **new** — `bodyStatus = "loading"` / `bodyError = null` → `chaptersApi.getChapterText(bookId,
  chapterId, signal)` → return silently on `signal?.aborted` → `runInAction`: `body = response`,
  `bodyDraft = response.text`, **`bodyBaseVersion = response.version`**, `bodyEditorGeneration += 1`
  (the one bump), `bodyStatus = "ready"`. `ApiError` → `bodyError = err.message` /
  `bodyStatus = "error"` with `body` left `null`; anything else rethrows. Touches **nothing** in the
  other two trios (DoD-1).
- `export function editBodyDraft(state: ChapterPageState, bookId: string, chapterId: string, text: string): void`
  — **new** — **the single entry point every body-draft change routes through.** Sets
  `state.bodyDraft = text` under `runInAction` and **does not bump** the generation counter (D15 /
  DoD-10). Synchronous and server-free — nothing reaches the server until the save control is used
  (DoD-6) — hence **no `signal` and no `Promise`**.
  - **It takes the two ids it does not yet read on purpose.** Step 007's restore-buffer key is
    `restoreBufferKey(bookId, "chapter", chapterId)` and `ChapterPageState` holds neither id (014's
    deliberate departure from `codexEntryPageState.ts`), so a two-argument signature would have to be
    broken next step. This matches the Interface intent's stated `(state, bookId, chapterId, …)` shape.
- `export async function saveChapterBody(state: ChapterPageState, bookId: string, chapterId: string, signal?: AbortSignal): Promise<void>`
  — **new** — payload `{ text: state.bodyDraft, expected_version: state.bodyBaseVersion }` typed
  `UpdateChapterTextRequest`, read off the state so the editor is the single source of the submitted
  value; `bodyBaseVersion === null` → return without contacting the server. Clears
  `bodyServerErrors`, `bodySubmitStatus = "loading"`, awaits
  `chaptersApi.updateChapterText(bookId, chapterId, body, signal)`, then **re-seeds `body`,
  `bodyDraft` and `bodyBaseVersion` from the RESPONSE** (DoD-3, DoD-4) with
  `bodySubmitStatus = "ready"` and **no generation bump**. On `ApiError`: the message lands in
  `bodyServerErrors` (**4xx → the `text` key, 5xx → the general `form` key**, the `saveSketch` rule
  verbatim), `bodySubmitStatus = "error"`, and **`bodyDraft` / `body` / `bodyBaseVersion` are all left
  untouched** (DoD-7, DoD-9); anything that is not an `ApiError` rethrows.
  - **A `409` is an ordinary refusal here** — same branch, same surface, no re-fetch, no auto-merge.
  - **The refusal text is `err.message`.** `client.ts:throwApiError` already prefers a string `detail`,
    and `routes/chapters.py:_map_chapter_error` puts a chapter refusal on the wire as a
    **plain-string `detail`**. `CodexEntryPage`'s `serverRefusalText` / `details.detail.message` object
    path is the **codex** family's and must not be copied (step 004's freeze note). No such helper is
    added to this module.

#### `ChapterPage.tsx` — the view surface contract (frozen copy; no code written)

The page keeps its one `useState` instance and its **single** mount `useEffect` with its **one**
`AbortController`; the effect gains `void loadChapterBody(state, book, chapterId, ctrl.signal)`
alongside the two existing loads and aborts with them. The body section is a **SIBLING** of the
chapter section and the prompt section — never nested inside the chapter's success path, or DoD-1's
independence cannot hold. Handlers stay inner functions (no `useCallback`/`useMemo`).

Frozen accessible surface (role/label queryable; the wording below is the contract):

| Element | Frozen name / text |
|---|---|
| Section heading | `Chapter body` |
| Body loading branch | a `Loader` plus the text `Loading…` (the chapter trio's wording) |
| Body load-error branch | `Alert` titled **`Could not load the chapter body`**, carrying `state.bodyError` verbatim |
| Editor (`state === "open"` only) | `<ChapterBodyEditor key={state.bodyEditorGeneration} initialMarkdown={state.bodyDraft} onChange={…editBodyDraft…} onSelectionChange={…} ariaLabel="Chapter body" />` |
| Save control (`open` only) | `Button` with the accessible name **`Save body`**, `disabled={!state.canSaveBody}` |
| Save-error surface | `Alert` titled **`Could not save the chapter body`**, listing `Object.values(state.bodyServerErrors)` verbatim (the sketch surface's shape) |
| Non-`open` branch | the body through `react-markdown`'s **default export**, **no plugins configured** (D16 — inherit `frontend.md`'s default), plus the read-only reason as readable text, and **no editor and no save control at all** |

- The generation counter is read **only** to build the editor's `key` — nowhere else.
- `onSelectionChange` is a **no-op today**: all four props of the frozen seam are required, and D5's
  selection wiring is **step 012's**. Do not add a `selectedText` field to the state here.
- The read-only reason is
  `resolveEditability({ kind: "chapter", entityId: <the route's chapter id>, chapterState: state.body.state }).readOnlyReason`,
  rendered **verbatim** — the wording belongs to `work/subject.ts` and **no new string is written**.
  It is derived from the **body response's** state, like `canEditBody`, not from `chapter.state`
  (which is what 014's separate `sketchDisabledReason` uses — the two are independent and both stay).

#### Absent on purpose, and must stay absent (each is a named decision)

- **no `conflict` / `conflictEntry` field, no `isReconciling` flag, no `resolveConflict` effect, no
  re-fetch after a `409`** — step 007's, and they arrive **with** their consumers (`006.context.md`);
- **no `applyDraft` bound property and no canvas/undo/selection hook** — step 012's. `makeAutoObservable(this)`
  therefore keeps its **no-arguments** form; no `{ applyDraft: false }` exclusion is added;
- **no restore-buffer call, no `bufferKey`, no `evictedBufferKeys`** — step 007's; `restoreBuffer.ts`
  is in no step's Source list;
- **no aggregation type over the three trios**, no `clientErrors`, no `errors` union, no
  `serverRefusalText` helper, no emptiness rule anywhere;
- **no change to `work/subject.ts`** (step 011 widens the `open` case; not this step) and **no edit to
  `ChapterBodyEditor.tsx`** — its four-prop seam is step 005's freeze and gains no fifth prop.

- Caller-compile edits (out of Source-files scope): **None.** Every change is additive — no existing
  signature, field, computed or effect moved, so no call site and no existing spec needed touching.

#### Compile gate

- `cd frontend && npx tsc --noEmit` → clean.
- `cd frontend && npm run build` (`tsc && vite build`) → clean, built in ~7s, all five entries emitted.
- `cd frontend && npm run test:types` → clean (014's `tests/work/ChapterPage.test.tsx` still compiles
  against the unchanged 014 surface).
- Runtime smoke (isolated MobX probe, nothing written into the repo): a class with these fields and
  these three throwing getters **constructs** under `makeAutoObservable` — computeds are lazy, so the
  page still renders 014's sections — and each getter throws `not implemented: …` **on read**.
- `npm test` was **not** run — the verifier owns it.

#### Red-gate profile

DoD-1 … DoD-10 are `[test]`; **DoD-11 is `[manual/live]`** (`npm run build` / `npm test` /
`npm run test:types`) and gets no spec. Note that `npm run build` and `npm run test:types` already
pass against this skeleton — a PASS there is not evidence the step is done.

- **Green by construction (declarative — arrives complete, cannot go red):**
  - The eight new observable **fields**. `new ChapterPageState()` succeeds and a spec that only reads
    `bodyDraft` (`""`), `bodyStatus` (`"idle"`), `bodyBaseVersion` (`null`), `bodyServerErrors` (`{}`)
    or `bodyEditorGeneration` (`0`) passes now. Data cannot be left unimplemented; the red must come
    from the effect that is supposed to **change** one of them.
  - 014's existing page surface — the title, the state badge, the sketch section and the prompt
    section — is shipped code and keeps passing. Any assertion about them is a regression guard.
- **Must be red, and in one of exactly two shapes:**
  1. **Through the page (the specs' normal route).** `ChapterPage.tsx` is unchanged, so **there is no
     body section at all**: no third api call is issued, no editor is mounted, no save control and no
     read-only body exist. Expect **query misses** ("unable to find a role/label…") and
     `expect(vi.mocked(getChapterText)).toHaveBeenCalled…` failing with **zero calls** — that is the
     correct red for **DoD-1, 2, 3, 4, 5, 6, 8, 9, 10**. It is *not* a `not implemented` throw,
     because nothing reaches the state module yet.
  2. **Driving an effect or a computed directly.** `loadChapterBody` / `saveChapterBody` reject with
     `Error("not implemented: …")`, `editBodyDraft` throws synchronously, and `bodyDirty` /
     `canEditBody` / `canSaveBody` throw **on read**. A spec that touches any of them fails with that
     message.
- **The four items that can pass VACUOUSLY against this skeleton — write the presence assertion
  FIRST or they are green at the red gate for the wrong reason:**
  - **DoD-6** ("editing the body issues no write call") — trivially true when no editor exists. Assert
    the labelled editor is mounted **and** that its change callback ran, *then* that
    `updateChapterText` was never called.
  - **DoD-8** ("`planned` / `closing` / `closed` renders read-only with a reason and offers no save
    control and no editor") — the "no editor, no save control" half is trivially true today. Assert
    the stored body text **and** the reason are on screen first.
  - **DoD-5** ("the save control is unavailable while the draft matches the loaded body and while a
    save is in flight") — "unavailable" is trivially true when no control is rendered. Assert the
    control **exists and is enabled** in the dirty case first.
  - **DoD-1**'s independence — "a body failure does not blank the chapter/prompt sections" is
    trivially true. Assert the **body error surface itself** appears (and, in the mirror direction,
    that the body section still renders when one of the other two fails).
  - **DoD-9** (`409` leaves the stored body untouched on screen) has the same hazard on its
    "overwrites nothing" half: assert the visible refusal **and** that the draft is still the author's
    text.
- **DoD-10** needs the generation counter observed **behaviourally**, not by name: the stubbed editor
  **remounts** (re-reads its initial-Markdown prop) when the body loads, and does **not** remount on a
  keystroke. Today the load never completes, so the remount never happens — that is the red.
- **No plausible value is returned anywhere.** The single sink's return type is `never`, so no
  computed can leak a `false` that satisfies "the save control is unavailable", and no effect can leak
  a settled trio, a seeded draft or a base version into a comparison.
- **Carried-forward mocking notes for the test-coder** (from `006.context.md`, restated because they
  bind to this freeze): the `vi.mock` of `../../src/api/chapters` must enumerate **every** export the
  page imports — 014's eight **plus** `getChapterText` and `updateChapterText` — or the mock is
  stripped and the page fails for the wrong reason; the `vi.mock` of
  `../../src/work/components/chapter/ChapterBodyEditor` substitutes a stub typed against the exported
  `ChapterBodyEditorProps` (**four props**, `ariaLabel` is the accessible name of the editable
  region). The folder is `components/chapter/` (**singular**) — 014's unrelated
  `components/chapters/` (plural) sits beside it.

### Step 007 — frozen interface (2026-07-30)

**One file changed: `frontend/src/work/pages/chapterPageState.ts`.** The step's second Source file,
`frontend/src/work/pages/ChapterPage.tsx`, is **deliberately UNCHANGED by this freeze** — exactly as in
step 006: its only symbol is `ChapterPage()` (zero props, unchanged), so it has no signature to freeze.
Its divergence view and eviction notice are behaviour and are the coder's; the **accessible surface**
they must present is frozen as prose below, because **queries in this project are by role or label
only**, so an unfrozen accessible name would break the air gap.

**`frontend/src/work/restoreBuffer.ts` is CONSUMED, NEVER MODIFIED** — it is in no step's Source list
and was not opened for edit. Everything this step needs already exists there:
`restoreBufferKey(bookId, subjectKind, subjectId)` (the `"chapter"` `SubjectKind` member is already
declared in `work/subject.ts`), the total `readBuffer(key) -> BufferedDraft | null`,
`writeBuffer(key, draft, baseVersion) -> WriteResult` and `clearBuffer(key)`, with
`BufferBaseVersion = number | string` — **this step is the first writer of that union's `number`
branch.** No widening was needed and none was made.

014's members, step 006's body trio, `bodyDraft`, `bodyServerErrors`, `bodySubmitStatus`,
`bodyBaseVersion`, `bodyEditorGeneration`, all three body computeds and all three body effects keep
their **names, types, parameter lists and order**. Every addition is appended. `work/subject.ts`,
`contentSubject.ts` and `ChapterBodyEditor.tsx` are untouched.

**No import was added.** `readBuffer` / `writeBuffer` / `clearBuffer` / `restoreBufferKey` are used by
**no** stub — a type or value imported only for a throwing body trips `noUnusedLocals` — so the coder
adds that one import line when it writes the buffer calls. Same rule step 006 applied to
`UpdateChapterTextRequest`.

#### The reconciliation side — a LOCAL union, not the codex one

- `frontend/src/work/pages/chapterPageState.ts` — `export type ChapterReconciliationSide = "server" | "draft"` — **new**
  - Declared here rather than imported from `codexEntryPageState.ts`'s identically-valued
    `ReconciliationSide`: that union lives in another **page's** state module, and importing it would
    pull the codex page state (and `api/codex`) into this page's module graph — a real hazard for a
    spec that whole-module-mocks `api/chapters` and would then also load `api/codex`. Two string
    literals are not worth a page→page dependency. The **name differs** (`Chapter…`) so the two are
    never confused in prose or in an import list.

#### The reconciliation state — three appended fields (declarative, arrive complete)

- `frontend/src/work/pages/chapterPageState.ts` — `ChapterPageState.bodyConflict: ChapterTextResponse | null = null` — **new**
  - The **server's current body**, re-fetched after a `409` — or the body that just loaded, when the
    buffer's base version no longer matches it — held **BESIDE** `bodyDraft`, never merged into it and
    never written over it. `null` whenever the page is not reconciling.
  - Named `bodyConflict`, not codex's `conflictEntry`: every body-region member of this class carries
    the `body…` prefix (three trios share one class), and the page has three editable regions of which
    exactly **one** is reconcilable.
- `frontend/src/work/pages/chapterPageState.ts` — `ChapterPageState.isReconcilingBody = false` — **new**
  - The flag that makes the page render the **divergence view instead of the editor**. Raised by
    **both** entrances, lowered by `resolveBodyConflict` whichever side is taken.
- `frontend/src/work/pages/chapterPageState.ts` — `ChapterPageState.evictedBufferKeys: string[] = []` — **new**
  - The keys the most recent buffer write had to evict (`WriteResult.status ===
    "saved-after-eviction"`), so the author can be told **which other items' drafts were lost**. Empty
    after a plain `"saved"`. Surfacing only — the eviction policy is `restoreBuffer.ts`'s, is already
    implemented and unit-tested, and **never evicts the key being written**, so this chapter's own
    buffer is never the victim. The name is codex's verbatim; there is exactly one buffer on this page.

`makeAutoObservable(this)` keeps its **no-arguments** form — no bound property was added (`applyDraft`
is still step 012's). **No new computed**: `ChapterPageState` owns neither the book id nor the chapter
id (014's deliberate departure), so a `bufferKey` computed of the `codexEntryPageState.ts` kind is
**impossible here** and the key is built inside each effect from its own `(bookId, chapterId)`
arguments — which is precisely why step 006 froze those two ids onto `editBodyDraft`.

#### The three shipped effects — signatures UNCHANGED, contracts extended

None of the three is re-stubbed. They are shipped, verified step-006 code, and the skeleton rule is
that existing behaviour is preserved and only *new* behaviour is left unimplemented; making a keystroke
or a body load throw would break a passing path to manufacture a red. Their **docstrings** now carry
the step-007 contract (the coder's instructions); their bodies are byte-identical to step 006's.

- `export async function loadChapterBody(state, bookId, chapterId, signal?): Promise<void>` —
  **unchanged signature**, extended contract. **The LOAD-TIME ENTRANCE — the load-bearing one.** After
  the body arrives, read `readBuffer(restoreBufferKey(bookId, "chapter", chapterId))` (reads are
  **total** — absent / non-JSON / wrong-shaped is `null`, never a throw) and branch:
  **no buffer** → step 006's behaviour, unchanged; **`buffer.baseVersion === response.version`** →
  restore `bodyDraft = buffer.draft` and **bump `bodyEditorGeneration`**; **a mismatch** → buffered
  draft into `bodyDraft`, the loaded response into `bodyConflict`, `isReconcilingBody = true`, and
  **NO SAVE IS ATTEMPTED**. `bodyBaseVersion` stays the **server's** `version` in every branch — it is
  the version the next save must carry, not the one the draft forked from.
- `export function editBodyDraft(state, bookId, chapterId, text): void` — **unchanged signature**,
  extended contract; **this is where the two frozen ids are finally read.** On **every** body-draft
  change, `writeBuffer(restoreBufferKey(bookId, "chapter", chapterId), text, state.bodyBaseVersion ?? "")`
  and **inspect the `WriteResult`**: `"saved-after-eviction"` → its `evictedKeys` into
  `evictedBufferKeys`; anything else → empty that holder. The base version written is the **numeric
  `Chapter.version` the body response carried**. The `?? ""` fallback is the project's established
  no-base-version marker for a chapter buffer (D18; `editCodexDraft`'s `?? ""`) and is **unreachable
  through the view** — the editor mounts only for a body that has loaded. Still synchronous and
  server-free: `localStorage` only.
- `export async function saveChapterBody(state, bookId, chapterId, signal?): Promise<void>` —
  **unchanged signature**, extended contract, in exactly **two** places: **on success, CLEAR the
  buffer** and empty `evictedBufferKeys` (the re-seeding from the response is unchanged); and **a `409`
  becomes the SAVE-TIME ENTRANCE** — re-fetch via `chaptersApi.getChapterText`, hold it in
  `bodyConflict`, raise `isReconcilingBody`, and leave the draft, the buffer and `bodyBaseVersion`
  untouched. **Never an auto-merge, never a silent overwrite.** Every other `ApiError` — D10's and
  D11's `403`s included — keeps the ordinary `bodyServerErrors` surface unchanged.

#### The one new effect — `(state, side, …, signal?)`, mirroring `resolveCodexConflict`

Its body is **UNIMPLEMENTED**: it routes its frozen parameter list through a re-added module-private
`function unimplemented(fn: string, ..._args: unknown[]): never` sink throwing
`Error("not implemented: resolveBodyConflict")` (the sink shape steps 004/005/006 used; step 006's
coder deleted it, this freeze re-adds it). **The coder deletes it with the stub.**

- `frontend/src/work/pages/chapterPageState.ts` —
  `export async function resolveBodyConflict(state: ChapterPageState, side: ChapterReconciliationSide, bookId: string, chapterId: string, signal?: AbortSignal): Promise<void>`
  — **new**
  - **`side` is second**, mirroring `resolveCodexConflict(state, side, signal?)` and the step file's
    literal `(state, side, …, signal?)`; the two ids occupy the `…` slot because this state owns
    neither and the buffer key needs both — the same reason `editBodyDraft` carries them. `signal` is
    trailing and optional, as every effect in this module has it.
  - **`"server"`** → discard the draft: `clearBuffer(restoreBufferKey(bookId, "chapter", chapterId))`,
    adopt `bodyConflict` as `body`, re-seed `bodyDraft` **and** `bodyBaseVersion` from it, **bump
    `bodyEditorGeneration`** (the draft was replaced from outside the editor — D15), clear
    `bodyConflict` / `evictedBufferKeys` / `bodyServerErrors`, lower the flag. Nothing of the
    abandoning author's text is written anywhere (US-041.AC-3).
  - **`"draft"`** → keep the draft: **adopt the server's VERSION FIRST** (`body` and `bodyBaseVersion`
    become `bodyConflict`'s, so the base version is now the **current** one), leave the view
    (`bodyConflict = null`, `isReconcilingBody = false`), and **only then** re-save through
    `saveChapterBody`, which now carries a version the server agrees with (US-041.AC-2). `bodyDraft` is
    **not** re-seeded and the generation is **not** bumped — the editor already holds this text.
  - **THE ORDERING IS THE POINT** (`007.context.md`, `013.codex`'s realization): re-saving before
    adopting the server's version sends the stale version again, the server refuses `409` again, and
    the page walks straight back into this view — an infinite loop that reads as a server bug.
  - **There is no third, merged outcome.** The union has exactly two members and no `"merge"` /
    `"both"` case exists to be filled in later; a merged body is something the author types.

#### `ChapterPage.tsx` — the frozen view surface (no code written)

The page keeps its one `useState` instance, its **single** mount `useEffect` and its **one**
`AbortController` — **no new effect, no new load, no new mount work.** The divergence view and the
eviction notice live **inside the existing body `Stack`**, so the chapter section, the sketch section
and the prompt section keep rendering: the view **never** becomes an early `return` from the component
(the way `CodexEntryPage`'s does) — DoD-11's "does not block the rest of the page". Handlers stay inner
functions (no `useCallback`/`useMemo`).

**Branch placement (part of the freeze).** Inside the body section the order is: loading → load-error →
**`state.isReconcilingBody`** → the existing `state.canEditBody` fork. The divergence branch is checked
**before** that fork, so it replaces the editor *and* its `Save body` control while it is open, and a
stale buffer on a no-longer-`open` chapter still reaches the view rather than setting a flag nothing
renders.

Frozen accessible surface (role/label queryable; the wording below **is** the contract — three later
specs bind to it):

| Element | Frozen name / text |
|---|---|
| Divergence heading | a heading reading **`Unsaved changes diverged`** (level unconstrained; `CodexEntryPage`'s wording verbatim — no new vocabulary) |
| Divergence explainer | `Alert` titled **`This chapter's body changed since your draft`**, whose text says the body changed on the server while the draft was unsaved, that **nothing has been merged**, and to choose which version to keep |
| Server pane heading | **`Current server version`** |
| Server pane content | `state.bodyConflict?.text ?? ""` as **readable text**, `whiteSpace: "pre-wrap"` — the raw Markdown, **not** through `react-markdown`: the two sides are compared literally, and rendering one of them would hide exactly the differences the author is choosing between |
| Server-side control | `Button` with the accessible name **`Keep the server version`** → `resolveBodyConflict(state, "server", book, chapterId)` |
| Draft pane heading | **`Your draft`** |
| Draft pane content | `state.bodyDraft`, same readable `pre-wrap` rendering |
| Draft-side control | `Button` with the accessible name **`Keep my draft`** → `resolveBodyConflict(state, "draft", book, chapterId)` |
| Eviction notice | `Alert` titled **`Other unsaved drafts were removed`**, rendered inside the body section whenever `state.evictedBufferKeys.length > 0` (independently of the divergence flag), stating that storage was full and these buffered drafts were removed to keep this one, then **each evicted key as readable text** |

**Tone is a design requirement, not a preference** (`frontend-work-drafts.md`; DoD-11):

- **Not a modal.** No Mantine `Modal`, `Drawer`, `Dialog` or `Overlay`, no portal, no focus trap, no
  backdrop — plain in-flow layout (`Stack` / `Paper withBorder` / `Group grow` is the codex precedent).
- **Not styled as a failure.** Both alerts are `color="yellow"`, **never `red`**; the divergence view is
  the normal landing for the navigated-away-mid-turn path, not a rare error condition.
- **Exactly two choices, neither pre-selected.** Two plain `Button`s and nothing else: no radio group,
  no `defaultChecked`, no `data-autofocus`, no `disabled`, and no visual "recommended" emphasis that
  would amount to a default. **No third control** — no merge, no save, no cancel, no discard.
- **No diff library, no character-level highlighting, no third merged pane.** An LLM-assisted merge is
  a Stage-5 capability.
- While the view is open the `ChapterBodyEditor` is **not mounted** and the `Save body` control is
  **not rendered**; the two side controls are the view's only controls.

#### Absent on purpose, and must stay absent (each is a named decision)

- **No widening of `BufferedDraft` to a multi-field shape**, and **no buffer for the sketch or the
  prompt** — the principal-text-field rule. An unsaved sketch is lost on an unload and the divergence
  view compares **bodies only**; both consequences are already sanctioned (014 excluded both fields
  deliberately).
- **No edit to `restoreBuffer.ts`** — consumed unmodified; if the chapter had needed something it does
  not offer, that was a blocker to route back, not a local widening. It needed nothing.
- **No `applyDraft`, no canvas/undo/selection wiring** — step 012's; `makeAutoObservable(this)` stays
  no-argument and `onSelectionChange` stays the page's no-op.
- **No chapter-state transition control** — step 008's.
- **No `serverRefusalText` helper** and no `details.detail.message` object path: a chapter refusal is a
  **plain-string `detail`** and reaches the page as `err.message` (steps 003/004 freeze notes).
- **No auto-save, no debounce, no polling, no re-fetch except the `409`'s single one.**

- Caller-compile edits (out of Source-files scope): **None.** Every change is additive — no existing
  signature, field, computed or effect moved, so no call site and no existing spec needed touching.

#### Compile gate

- `cd frontend && npx tsc --noEmit` → clean.
- `cd frontend && npm run build` (`tsc && vite build`) → clean, built in ~8s, all five entries emitted.
  (The ~763 kB `work` chunk warning is step 005/006's TipTap set and pre-dates this step.)
- `cd frontend && npm run test:types` → clean.
- `npm test` was **not** run — the verifier owns it.

#### Red-gate profile

DoD-1 … DoD-11 are `[test]`; **DoD-12 is `[manual/live]`** (`npm run build` / `npm test` /
`npm run test:types`) and gets no spec. Two of those three already pass against this skeleton — a PASS
there is not evidence the step is done.

**The shape of the red is different from every previous step of this feature, and the test-coder must
expect it.** Only **one** symbol throws (`resolveBodyConflict`), and it is **unreachable through the
page**, because no control renders that calls it. `loadChapterBody`, `editBodyDraft` and
`saveChapterBody` are shipped, working code left intact on purpose (a skeleton preserves existing
behaviour), so a spec driving the page will see step 006's behaviour: the body loads, the editor mounts
and seeds from the **server's** text, a keystroke lands in the draft, a save succeeds, and a `409`
surfaces as an ordinary refusal. The red therefore arrives as:

1. **Nothing in `localStorage`** — `readBuffer(restoreBufferKey(bookId, "chapter", chapterId))` is
   `null` after editing (DoD-1), and a seeded buffer is **still there** after a successful save (DoD-4).
2. **The server's body on screen where the buffered draft was expected** (DoD-2).
3. **Query misses for the divergence surface** — no `Unsaved changes diverged` heading, no
   `Keep the server version` / `Keep my draft` controls, no
   `This chapter's body changed since your draft` alert (DoD-5, DoD-6, DoD-7, DoD-8, DoD-9, DoD-11) —
   and, for DoD-10, no `Other unsaved drafts were removed` alert.
4. **`Error("not implemented: resolveBodyConflict")`** — *only* for a spec that calls the effect
   directly rather than clicking a control. Either route is a correct red for DoD-7/8/9; the clicking
   route is the idiomatic one and fails at the query.

**Green by construction (declarative — arrives complete, cannot go red):**

- The three new observable **fields**. `new ChapterPageState()` succeeds and a spec that only reads
  `bodyConflict` (`null`), `isReconcilingBody` (`false`) or `evictedBufferKeys` (`[]`) passes now. Data
  cannot be left unimplemented; the red must come from the entrance that is supposed to **change** one.
- `ChapterReconciliationSide` is a type: erased at runtime, complete by construction, and cannot
  satisfy or fail an assertion by itself.
- **`restoreBuffer.ts` is fully implemented shipped code.** `writeBuffer` / `readBuffer` /
  `clearBuffer` / `restoreBufferKey` all work **now**, including the real eviction policy. A spec that
  seeds, reads or evicts buffers *directly* proves nothing about this step — every buffer assertion
  must be about what **the page** did, and DoD-10's "the current chapter's buffer is never the victim"
  is `restoreBuffer.ts`'s own guarantee, already true, so it must ride on an assertion that the page
  **surfaced** the eviction.
- Step 006's whole body surface — the load, the editor, the save, the read-only branch, the `409`
  refusal alert — is shipped and keeps passing. Any assertion about it is a regression guard.

**The items that can pass VACUOUSLY against this skeleton — write the presence assertion FIRST or they
are green at the red gate for the wrong reason:**

- **DoD-3** ("nothing reaches the server as a result of buffering") — **the worst of them**: today
  nothing is buffered at all, so "no write call" is trivially true. Assert the edit landed **and** that
  the buffer now holds it, *then* that `updateChapterText` was never called.
- **DoD-4** ("a successful save clears the buffer") — a buffer that was never written is trivially
  "cleared". The spec must establish a buffer **through the page** (edit, then read it back) before the
  save, so the assertion has something to lose.
- **DoD-5**'s "with no save attempted" half — trivially true when no divergence path exists at all.
  Assert the divergence view's two controls are on screen **first**, then that `updateChapterText` was
  never called.
- **DoD-7**'s "nothing of the abandoning author's text is written" half — trivially true against a page
  that cannot resolve anything. Assert the resolution **happened** (the view is gone and the server's
  body is on screen) first.
- **DoD-10**'s "the current chapter's buffer is never the victim" half — see above: it is already true
  and is not this step's to prove. The step's part is that the author is **told**, by name, which keys
  went.
- **DoD-11**'s "is not a modal" and "neither pre-selected" halves — both trivially true when no view
  renders. Assert the two named controls **exist and are enabled** first, then the negative properties.
- **DoD-6**'s "no silent overwrite" half — assert the divergence view appeared **and** the author's
  draft is still the author's text, not merely that nothing was overwritten.

**No plausible value is returned anywhere.** The single sink's return type is `never`, so
`resolveBodyConflict` can leak no settled state, no adopted version and no cleared flag into a
comparison; and the three new fields hold `null` / `false` / `[]`, none of which can satisfy an
assertion that the divergence view opened or that keys were evicted.

**Mocking notes carried forward for the test-coder** (they bind to this freeze): the `vi.mock` of
`../../src/api/chapters` must still enumerate **all ten** exports; the `vi.mock` of
`../../src/work/components/chapter/ChapterBodyEditor` (**singular** folder) substitutes the same
four-prop stub step 006 used. **`restoreBuffer.ts` is NOT mocked** — jsdom provides `localStorage`, the
module's own unit behaviour is covered elsewhere, and DoD-10 needs the **real** eviction policy driven
by oversized sibling entries. Clear `localStorage` between tests. `ApiError` is imported real for
DoD-6's genuine `409`, constructed with a plain refusal **message** (not the codex family's
`detail.message` object path). DoD-2 and DoD-5 need the buffer **seeded before the page mounts**, with
a base version that matches the served `version` and one that does not — and the seeded record must be
a real `writeBuffer(...)` write, so its `writtenAt` stamp and shape are the ones `readBuffer` accepts.

### Step 008 — frozen interface (2026-07-30)

**One file changed: `frontend/src/work/pages/chapterPageState.ts`.** The step's second Source file,
`frontend/src/work/pages/ChapterPage.tsx`, is **deliberately UNCHANGED by this freeze** — exactly as in
steps 006 and 007: its only symbol is `ChapterPage()` (zero props, unchanged), so it has no signature to
freeze. Its transition control, its refusal surface and its `closing` reason are behaviour and are the
coder's; the **accessible surface** they must present is frozen as prose below, because **queries in
this project are by role or label only**, so an unfrozen accessible name would break the air gap.

**D19 holds absolutely: `ChaptersPage.tsx`, `chaptersPageState.ts`, `BookHubPage.tsx` and the navigator
were not opened.** One action, one surface.

014's members, step 006's body trio / draft / base version / generation counter / three computeds /
three effects and step 007's `ChapterReconciliationSide`, three reconciliation fields and
`resolveBodyConflict` all keep their **names, types, parameter lists and order**. Every addition is
appended. `restoreBuffer.ts`, `contentSubject.ts`, `work/subject.ts`, `ChapterBodyEditor.tsx` and
`api/chapters.ts` are **consumed, never modified**.

**No import was added** — `chaptersApi` (namespace), `ApiError`, `runInAction`, `ChapterResponse` and
`ChapterTextResponse` are all already imported by 014 / steps 006 / 007. Step 004's three transition
functions (`openChapterState` / `closeChapterState` / `reopenChapterState`, each resolving to 014's
`ChapterResponse`) are shipped and are reached through the existing `chaptersApi` namespace.

#### The transition union — a LOCAL type

- `frontend/src/work/pages/chapterPageState.ts` — `export type ChapterTransition = "open" | "close" | "reopen"` — **new**
  - The state machine admits **exactly one** transition per state, so this names *which* one is on
    offer, never a set. There is no `"none"` member — the absence is `null`, so a `closing` chapter
    cannot accidentally be handed a fourth control to render.

#### The transition state — two appended fields, separate from the body's and the sketch's

- `frontend/src/work/pages/chapterPageState.ts` — `ChapterPageState.transitionStatus: "idle" | "loading" | "ready" | "error" = "idle"` — **new**
  - Its own status. **Not** `bodySubmitStatus`, **not** `sketchSubmitStatus`, **not** `chapterStatus`: a
    transition is a command against the chapter row, not a save of either editor's draft, and it must
    never make an editor look like it is loading or saving.
- `frontend/src/work/pages/chapterPageState.ts` — `ChapterPageState.transitionError: string | null = null` — **new**
  - **A single string, not a `Record<string, string>`.** The `…ServerErrors` shape exists for forms with
    fields to key a refusal by; a transition is a **bodiless `POST`** with no fields at all. Deliberately
    the one place in this class that departs from the `021` form shape, because the thing it holds is not
    a form refusal.
  - The text is **`err.message`** — `routes/chapters.py:_map_chapter_error` puts the chapter family's
    refusal on the wire as a **plain-string `detail`**, which `client.ts:throwApiError` already prefers.
  - **CORRECTION APPLIED TO `008.context.md`.** That file points at `CodexEntryPage`'s
    `serverRefusalText(err)` helper reading `err.details.detail.message` and calls it "the harvested
    shape". That is the **codex** route family's *object*-shaped detail. The chapter routes emit a
    **plain-string `detail`** — established and verified at step 003, and steps 006 / 007 already read
    the refusal that way. **No `serverRefusalText` helper is added to this module and no
    `details.detail.message` path is read.** Everything else `008.context.md` says about that paragraph
    (the server-side-nuance precedent, the accepted cost) stands unchanged.
  - This holder is where D14's accepted cost is paid: a co-author sees a control the server will refuse
    `403`, and this is what makes the refusal legible instead of mysterious. The archived-book `403`
    (D10) and the another-chapter-open `409` land in the same holder.

`makeAutoObservable(this)` keeps its **no-arguments** form (no bound property was added — `applyDraft` is
still step 012's).

#### The two pure `get` computeds (both throw in the skeleton)

- `frontend/src/work/pages/chapterPageState.ts` — `get offeredTransition(): ChapterTransition | null` — **new**
  - Derived from **the loaded CHAPTER's state alone** — `this.chapter?.state` (D14). **Not** `body.state`
    (which is what `canEditBody` reads) and **not** a caller-role signal: the control renders beside the
    chapter's own state badge, which `lifecycleStateLabel` reads off `chapter.state`, and the two must
    never disagree.
  - `planned` → `"open"` · `open` → `"close"` · `closed` → `"reopen"` · **`closing` → `null`**.
  - **`null` before the first successful chapter load and on a failed one** — there is no state to derive
    an offer from, and the chapter section is showing its own loading / error branch there.
  - **Exactly ONE control is ever rendered — never three with two disabled.** A disabled control invites
    "why"; an absent one with the state shown beside it does not.
- `frontend/src/work/pages/chapterPageState.ts` — `get transitionUnavailableReason(): string | null` — **new**
  - Non-`null` **exactly** when the chapter has loaded and `offeredTransition` is `null` — which the state
    machine makes exactly the `closing` case. `null` for `planned` / `open` / `closed` (a control is
    offered there, so there is nothing to explain) and `null` before the first successful chapter load.
  - **The frozen sentence, verbatim — a role/label query and a screen reader both reach it:**

    > `This chapter is closing. The close approval step is not built yet, so its state cannot be changed here.`

  - It **names the close gate as not yet built** (`016.chapter-close-continuity`'s), rather than merely
    restating the state — `closing` is a state the author cannot currently produce (D8) and will not
    recognise, which is why it is the one case that gets a stated reason rather than silence.
  - This page's **OWN** sentence, deliberately: `work/subject.ts`'s `closing` reason
    (*"…while its owner approves continuity for this body — it is read-only until the review
    completes"*) is about the **body** being read-only and promises a review flow that does not exist
    yet. The precedent for a page-owned sentence is `sketchDisabledReason`'s `open` case.

There is deliberately **no third computed** for the control's label: the accessible name is the view's
and is frozen below.

#### The three external effects — `(state, bookId, chapterId, signal?)`

Every body is **UNIMPLEMENTED**: each routes its frozen parameter list through a re-added module-private
`function unimplemented(fn: string, ..._args: unknown[]): never` sink throwing
`Error("not implemented: <fn>")` (the sink shape steps 004 / 005 / 006 / 007 used; step 007's coder
deleted it, this freeze re-adds it). It also satisfies `noUnusedParameters`. **The coder deletes it with
the last stub.** The two computeds route through the same sink and therefore throw **on read**.

- `export async function openChapterState(state: ChapterPageState, bookId: string, chapterId: string, signal?: AbortSignal): Promise<void>` — **new** — calls `chaptersApi.openChapterState(bookId, chapterId, signal)` (UC-035 / US-036.AC-1)
- `export async function closeChapterState(state: ChapterPageState, bookId: string, chapterId: string, signal?: AbortSignal): Promise<void>` — **new** — calls `chaptersApi.closeChapterState(...)`; the server writes **`closed`** directly (D8) — US-038.AC-1
- `export async function reopenChapterState(state: ChapterPageState, bookId: string, chapterId: string, signal?: AbortSignal): Promise<void>` — **new** — calls `chaptersApi.reopenChapterState(...)` (UC-037 / US-039.AC-1)

**Naming.** The three mirror step 004's api functions **1:1**, carrying the `State` suffix for the reason
004 recorded: in an app whose vocabulary is panes, routes and subjects, `openChapter(...)` reads as
*navigating to* a chapter. There is no collision — the api layer is reached through the `chaptersApi`
namespace, and the page imports these three from `./chapterPageState`.

**The ONE shared contract** (identical in all three; only the api call differs):

1. `transitionStatus = "loading"`, `transitionError = null`;
2. await the api call → 014's `ChapterResponse`;
3. return silently when `signal?.aborted`;
4. **on success re-seed the chapter trio AND the body trio from the server**, then
   `transitionStatus = "ready"`;
5. on `ApiError`: `transitionError = err.message` (fallback `"Could not change the chapter state."` on an
   empty message), `transitionStatus = "error"`, **and nothing else changes anywhere**. Anything that is
   not an `ApiError` rethrows, as everywhere else in this module.

**The re-seed, and why it is not a local patch (DoD-7).** A successful transition changes four things at
once — `resolveEditability`'s verdict for the body, whether the editor is mounted at all (D16), which
control is offered next, and 014's sketch editor's enablement — and re-seeding is what makes all four
follow with no navigation and no manual reload:

- the **chapter trio** takes the transition's own `ChapterResponse` **whole** (`state.chapter = response`),
  exactly as `saveSketch` adopts its PATCH response. **Never patch `state.chapter.state` locally** — the
  backend is the source of truth, and a locally patched state would leave the **body** response's own
  `state` field disagreeing with it;
- the **body trio** is re-read from the server (`chaptersApi.getChapterText`) and `state.body` /
  `state.bodyStatus` are set from *that* response, so `canEditBody` — which reads `body.state` — follows
  too.

**What the re-seed must NOT touch (DoD-8), and why `loadChapterBody` is NOT called:**

- **`bodyDraft`** — a successful transition must no more destroy unsaved work than a refused one;
- **the restore buffer** — not written, not cleared; steps 006's and 007's rules own it;
- **`bodyBaseVersion`** — a transition writes `state` + `modified_at` only and never bumps
  `Chapter.version` (step 002's freeze), so there is nothing to move;
- **`bodyEditorGeneration`** — nothing wrote the draft from outside the editor, so there is nothing for
  TipTap to be remounted to see;
- **`bodyConflict` / `isReconcilingBody` / `evictedBufferKeys`**, and the sketch and prompt drafts and
  their `…ServerErrors` holders.

`loadChapterBody` would break every one of those — it re-seeds the draft, bumps the generation counter
and re-runs the load-time buffer entrance, which could open the divergence view for a body nobody
re-read. **It is not called from a transition.**

If the **body re-read** itself fails with an `ApiError`, that is a body load failure and it lands in the
body trio's own surface (`bodyError` / `bodyStatus = "error"`) — the page already has one. The transition
itself succeeded, so `transitionStatus` stays `"ready"` and `transitionError` stays `null`.

#### `ChapterPage.tsx` — the frozen view surface (no code written)

The page keeps its one `useState` instance, its **single** mount `useEffect` and its **one**
`AbortController` — **no new effect, no new load, no new mount work.** Handlers stay inner functions (no
`useCallback` / `useMemo`). Whether the view uses one inner handler dispatching on
`state.offeredTransition` or three is the coder's; what is frozen is that it calls **exactly the effect
matching `state.offeredTransition`** and never a different one.

**Placement (part of the freeze).** The control renders **inside the chapter header's existing `Group`,
beside the ordinal and the state `Badge`** — literally beside the chapter's state, which is what makes an
absent control legible rather than mysterious. The refusal surface and the `closing` reason render
directly beneath that group, still inside the chapter header `Stack`. All three live **inside the chapter
section's success branch** (they need `chapter.title` and `chapter.state`); this is not a fourth
independent trio and no independence rule applies to it.

Frozen accessible surface (role/label queryable; the wording below **is** the contract):

| Element | Frozen name / text |
|---|---|
| Transition control | **exactly one** `Button`, rendered only when `state.offeredTransition !== null`. Visible text is the action word — `Open` / `Close` / `Reopen` — and `aria-label` carries the **full accessible name**, naming both the action and the chapter: `Open chapter: {chapter.title}` · `Close chapter: {chapter.title}` · `Reopen chapter: {chapter.title}` (the title verbatim, after `: `) — DoD-9 |
| Transition control, in flight | `disabled={state.transitionStatus === "loading"}` — the only disablement on it, and never a substitute for the absence rule: a transition that is **not offered** is **not rendered**, never rendered-and-disabled |
| Refusal surface | `Alert` `color="red"` titled **`Could not change the chapter state`**, carrying `state.transitionError` verbatim as readable text; rendered whenever `state.transitionError !== null` (DoD-5, DoD-6) |
| `closing` reason | `state.transitionUnavailableReason` as readable text (a dimmed `Text`, the `sketchDisabledReason` shape) whenever it is non-`null` — **and no control at all beside it** (DoD-4) |

- **The accessible name contains the visible label** (`Open` ⊂ `Open chapter: …`), so the `aria-label`
  is a widening, not a replacement — the same shape 014's state `Badge` already uses on this page.
- **No confirmation dialog, of any kind** — no `Modal`, no `Drawer`, no `Dialog`, no "are you sure",
  including for close. Closing is reversible by reopening, and the gate is `016`'s (D8).
- **No second control anywhere**: no "open" on the chapters list, no transition on the book hub, no
  duplicate in the navigator (D19).

#### Absent on purpose, and must stay absent (each is a named decision)

- **No caller-role signal, in any form** — no `can_manage_state` on a DTO, no fetch of the chapter
  **list** for 014's `can_reorder` hint, no book-detail read, no React context (D14). The control is
  offered to **every member**, gated on **chapter state only**, and the server's `403` is the answer.
- **No three controls with two disabled**, and no "why is this disabled" tooltip — the state machine
  admits one transition, so one is rendered.
- **No local patch of `chapter.state`**, no optimistic transition, and **no `loadChapterBody` call** from
  a transition (see above).
- **No touch of the body draft, the buffer, the base version or the generation counter**, on success or
  on refusal.
- **No `serverRefusalText` helper** and no `details.detail.message` object path — see the correction
  above.
- **No new api function**, no change to `api/chapters.ts`, `work/subject.ts`, `restoreBuffer.ts`,
  `contentSubject.ts` or `ChapterBodyEditor.tsx`.
- **No `closing`-producing path anywhere** — nothing in this feature writes that state (D8); the
  `closing` branch exists only to be *read*.

- Caller-compile edits (out of Source-files scope): **None.** Every change is additive — no existing
  signature, field, computed or effect moved, so no call site and no existing spec needed touching.

#### Compile gate

- `cd frontend && npx tsc --noEmit` → clean.
- `cd frontend && npm run build` (`tsc && vite build`) → clean, built in ~8s, all five entries emitted.
  (The ~765 kB `work` chunk warning is step 005's TipTap set and pre-dates this step.)
- `cd frontend && npm run test:types` → clean.
- `npm test` was **not** run — the verifier owns it.

#### Red-gate profile

DoD-1 … DoD-9 are `[test]`; **DoD-10 is `[manual/live]`** (`npm run build` / `npm test` /
`npm run test:types`) and gets no spec. Two of those three already pass against this skeleton — a PASS
there is not evidence the step is done.

**The shape of the red.** `ChapterPage.tsx` is unchanged, so **there is no transition control on the page
at all**: no `Open chapter: …` / `Close chapter: …` / `Reopen chapter: …` button, no
`Could not change the chapter state` alert, and no `closing` reason. A spec driving the page therefore
fails at the **query** ("unable to find a role/button with the name…"), and
`expect(vi.mocked(openChapterState)).toHaveBeenCalled…` fails with **zero calls**. A spec that instead
drives the module directly gets `Error("not implemented: openChapterState" | "closeChapterState" |
"reopenChapterState")`, and reading `state.offeredTransition` or `state.transitionUnavailableReason`
throws `not implemented: get …` **on read**. Either route is a correct red; the clicking route is the
idiomatic one and fails at the query.

**Green by construction (declarative or shipped — arrives complete, cannot go red):**

- The two new observable **fields**. `new ChapterPageState()` succeeds and a spec that only reads
  `transitionStatus` (`"idle"`) or `transitionError` (`null`) passes now. Data cannot be left
  unimplemented; the red must come from the effect that is supposed to **change** one.
- `ChapterTransition` is a type: erased at runtime, complete by construction, and cannot satisfy or fail
  an assertion by itself.
- **`api/chapters.ts`'s three transition functions are shipped step-004 code and work.** A spec that
  calls `openChapterState` from the **api** module proves nothing about this step — every assertion must
  be about what **the page** did. `ApiError` is likewise real shipped `client.ts` code.
- Steps 006's and 007's whole body surface — the load, the editor, the save, the read-only branch, the
  divergence view, the eviction notice — is shipped and keeps passing. Any assertion about it is a
  regression guard. 014's title / ordinal / state badge / sketch / prompt sections likewise.

**The items that can pass VACUOUSLY against this skeleton — write the presence assertion FIRST or they
are green at the red gate for the wrong reason:**

- **DoD-8** — *"a refused transition never clears or alters the body draft, and never clears the restore
  buffer"* — **the worst of them by a distance.** Today nothing is refused because nothing can be
  attempted, so "the draft is intact" and "the buffer is intact" are trivially true. The spec must
  establish the draft **through the page** (the editor's change callback ran, and the buffer now holds
  it), then **use the control**, then assert the refusal is **on screen**, and only then that the draft
  and the buffer are unchanged.
- **DoD-4** — *"no transition control is offered and a stated reason is shown"* — the "no control" half
  is trivially true everywhere today. Assert the **stated reason is on screen** first (and that it names
  the close gate as not yet built), and pair it with the contrast case — an `open` chapter **does** offer
  its one control — so "no control" is evidence about `closing` rather than about the page.
- **DoD-5** — *"surfaces the server's message and leaves the chapter's state on screen unchanged"* — the
  "unchanged" half is trivially true. Assert the **refusal message** is visible first, then that the
  state badge still reads its original word.
- **DoD-6** — same hazard, doubled: *"leaves both this chapter's state and the body region unchanged"*.
  Assert the visible `409` refusal first, then the badge **and** the body region (the editor still
  mounted for an `open` chapter, its draft still the author's text).
- **DoD-2** — *"the page then shows the chapter as `closed` with the body read-only and no save
  control"* — the "no save control" half is trivially true if the close never happens. Assert the state
  on screen became **`Closed`** *and* the stored body is rendered read-only **first**, then the absence
  of `Save body`.
- **DoD-1** — *"with the body editor now mounted"* — assert the transition happened (the state on screen
  became `Open`) **and** the labelled editor is present; a spec that only asserts the api function was
  called is red today but proves nothing about the re-seed.
- **DoD-7** — *"re-seeds the chapter AND the body from the server"* — non-vacuous, and it is the item
  that catches a local `state` patch: assert a **second** `getChapterText` call after the transition
  **and** that the body region followed the new state. A spec that asserts only the chapter badge would
  pass against a locally patched `chapter.state`.
- **DoD-3** and **DoD-9** are pure query items and are non-vacuous — the control does not exist, so the
  name lookup misses.

**No plausible value is returned anywhere.** The single sink's return type is `never`, so no effect can
leak a re-seeded trio, a settled status or a cleared error into a comparison, and neither computed can
leak a `null` that satisfies "no control is offered" — reading it **throws**. The two new fields hold
`"idle"` / `null`, neither of which can satisfy an assertion that a transition happened or that a
refusal was surfaced.

**Mocking notes carried forward for the test-coder** (they bind to this freeze):

- the `vi.mock` of `../../src/api/chapters` must now enumerate **all THIRTEEN** exports — 014's eight
  (`listChapters`, `getChapter`, `createChapter`, `updateChapterSketch`, `removeChapter`,
  `reorderChapters`, `getOwnChapterSystemPrompt`, `updateOwnChapterSystemPrompt`) **plus** step 004's
  five (`getChapterText`, `updateChapterText`, `openChapterState`, `closeChapterState`,
  `reopenChapterState`). Steps 006 / 007 said "all ten"; the three transitions make it thirteen. A
  missing export strips the mock and the page fails for the wrong reason;
- the `vi.mock` of `../../src/work/components/chapter/ChapterBodyEditor` (**singular** folder — 014's
  unrelated `components/chapters/` sits beside it) substitutes the same four-prop stub steps 006 / 007
  used, typed against the exported `ChapterBodyEditorProps`;
- `getChapter` **and** `getChapterText` must both be re-armed to return the **post-transition** state
  after the transition resolves, or DoD-7's re-seed is not observable — the chapter response the
  transition itself resolves to is what the chapter trio adopts, and the body trio comes from the
  **second** `getChapterText` call;
- `ApiError` is imported **real** from `../../src/api/client`; DoD-5 needs a `403` carrying a message and
  DoD-6 a `409`, both constructed with a **plain refusal message** (never the codex family's
  `detail.message` object path);
- **`restoreBuffer.ts` is NOT mocked** (jsdom provides `localStorage`); clear `localStorage` between
  tests, and DoD-8's buffer half needs a buffer written **through the page** before the refusal;
- a chapter in `closing` is reached by **arming the mocked api to return one** — nothing in this feature
  produces that state (D8).

### Step 009 — frozen interface (2026-07-30)

Backend only. Four source files, all pre-existing and all widened **additively**. No file was created,
nothing was renamed, `services/codex_tools.py` was **not touched**, `routes/chats.py` was **not touched**
(its serializer is generic over `frame.event`), and **no seed call was added** — all five `AssistantMode`
rows are already written by `seed_default_modes()`.

**`backend/app/models/schemas/chats.py`**

- `CanvasOp = Literal["replace", "append", "replace_selection"]` — **new**, complete. Declared
  immediately below the untouched `CanvasField`. The frame-operation discriminator (D17): the whole
  field, the end of it, or the author's current selection.
- `CanvasField = Literal["name", "body"]` — **unchanged, and deliberately so.** A chapter's body **is**
  the `"body"` field; no `"text"` member exists (DoD-3).
- `class CanvasFrame(BaseModel)` — **changed**, one field appended:
  `subject_kind: SubjectKind`, `subject_id: str | None`, `field: CanvasField`, `text: str`,
  **`op: CanvasOp = "replace"`**. Was the same four fields with no `op`. The default is the contract:
  `CanvasFrame(subject_kind=…, subject_id=…, field=…, text=…)` still constructs and carries
  `op == "replace"`, which is what every emission before this step meant.
- `class TurnRequest(BaseModel)` — **changed**, one field appended:
  `prompt: str | None = None`, `subject_kind: SubjectKind | None = None`, `subject_id: str | None = None`,
  `codex_kind: CodexKind | None = None`, **`selection_text: str | None = None`**. A **fifth flat field** —
  no subject object exists on this request and none was introduced. **Text only**: no offsets, no line
  numbers, no range object, no anchor id (D5).

**`backend/app/services/tools.py`**

- `@dataclass(frozen=True) class ToolContext` — **changed**, one defaulted field appended:
  `book_id: int`, `access: authz.BookAccess | None = None`, `subject: "ResolvedSubject | None" = None`,
  `emit_frame: FrameEmitter | None = None`, **`selection_text: str | None = None`**.
  `ToolContext(book_id=…)` still constructs. **No role, mode or book-state field was added** —
  `access` already carries all three, which is what keeps step 010 cheap.
- `ToolBinder`, `ToolDef`, `TOOL_REGISTRY`, `resolve_tools`, `build_tool_bindings` — **unchanged**. No
  registry entry was added (the chapter tools are step 010's).

**`backend/app/services/assistant_runtime.py`**

- `@dataclass(frozen=True) class ResolvedSubject` — **changed**, one defaulted field inserted between
  `entry` and `mode_key`: `kind: SubjectKind | None = None`, `entry: CodexEntry | None = None`,
  **`chapter: Chapter | None = None`**, `mode_key: str | None = None`. Every construction in the repo is
  by keyword, so the insertion binds unchanged; `NO_SUBJECT = ResolvedSubject()` is unchanged.
- `_CHAPTER_STATE_MODES: dict[str, str] = {ChapterState.open.value: "write-chapter", ChapterState.closing.value: "close-chapter"}`
  — **new**, complete, declared beside `_CODEX_KIND_MODES` (not inlined). `planned` and `closed` are
  **absent by design**: a missing key is no mode.
- `def _mode_for_chapter_state(state: ChapterState | str | None) -> str | None` — **new**, UNIMPLEMENTED
  (raises). The leaf of the chapter branch; the enum-or-string tolerance mirrors `_mode_for_codex_kind`.
- `async def _chapter_within_book(access: authz.BookAccess, subject_id: str) -> Chapter | None` — **new**,
  UNIMPLEMENTED (raises). The chapter twin of `_entry_within_book`, same three-way rule (non-numeric id /
  unknown id / another book's row → `None`), so DoD-9's cross-book refusal is copied from the codex shape
  rather than invented as a second check.
- `async def resolve_subject(access, subject_kind=None, subject_id=None, codex_kind=None) -> ResolvedSubject`
  — **signature unchanged**; body gains one `elif subject_kind == "chapter" and subject_id is not None`
  branch that calls the unimplemented `_chapter_within_book` and returns `NO_SUBJECT` when it yields
  `None`. A chapter subject **with no id** keeps its pre-015 answer (itself, no row, no mode).
- `def determine_mode(subject: ResolvedSubject) -> str | None` — **signature unchanged**; body
  restructured so the chapter branch is reachable. Was
  `if subject.entry is None: return None` / `return _mode_for_codex_kind(subject.entry.kind)`; is now
  `if subject.entry is not None: return _mode_for_codex_kind(subject.entry.kind)` /
  `if subject.chapter is not None: return _mode_for_chapter_state(subject.chapter.state)` / `return None`.
  **This is the trap the step context names**: the old guard keyed off "no codex entry", and a chapter
  subject carries a null `entry` by construction, so leaving it would have made the chapter branch
  unreachable while every codex case still answered correctly. The fall-through now means "resolved to
  nothing at all". Codex behaviour and no-subject behaviour are **bit-identical**.
- `BASE_TOOL_NAMES`, `mode_system_prompt`, `allowed_tool_names`, `resolve_turn_tools` — **unchanged**.
  Tool gating is not touched: a null mode still yields exactly `("web_search",)`.
- New imports: `chapters` added to the `app.db` namespace import; `from app.models.chapter import Chapter, ChapterState`.

**`backend/app/services/chat_turn.py`**

- `@dataclass(frozen=True) class TurnContext` — **changed**, one defaulted field appended:
  `chat`, `server`, `resolved_key`, `subject`, `access`, **`selection_text: str | None = None`**.
  Not named in Interface intent but **structurally required and therefore frozen here**: `prepare_turn`
  parses the `TurnRequest` and `run_turn` builds the `ToolContext`, and this record is the only carrier
  between them. Defaulted, so every existing keyword construction (011's and 013's tests included) binds
  unchanged.
- `prepare_turn(access, chat_id, request=None) -> TurnContext` and
  `run_turn(context, prompt) -> AsyncGenerator[TurnFrame, None]` — **signatures unchanged**. The
  `TurnRequest.selection_text → TurnContext.selection_text → ToolContext.selection_text` plumbing is
  **left UNIMPLEMENTED on purpose** (DoD-4 must be able to go red); both sites carry a
  `Skeleton (015 step 009): … UNIMPLEMENTED` marker naming exactly what the coder adds.
- `TurnFrame` and the `emit_frame` closure — **unchanged**.

Caller-compile edits (out of Source-files scope): **None.** Every widening is a defaulted field or a
private helper, so no call site anywhere in `app/` needed adapting.

#### Red-gate profile

**Declarative members arrive complete and cannot be stubbed.** Pydantic fields, `Literal` members and
frozen-dataclass fields are declarations, not behaviour: `CanvasOp`'s three members, `CanvasFrame.op`'s
`"replace"` default, `TurnRequest.selection_text`, `ToolContext.selection_text`, `TurnContext.selection_text`,
`ResolvedSubject.chapter` and `_CHAPTER_STATE_MODES` are all **final as written**. There is nothing to
leave unimplemented in them, and the coder's diff for those lines is empty.

Consequences for the DoD list:

- **Green by construction** (the freeze itself satisfies them; they are regression / declaration
  assertions, not behaviour to write): **DoD-1** (a frame built without `op` carries `"replace"`; one
  built with `"append"` / `"replace_selection"` carries what it was given), **DoD-2** (the untouched
  codex emission still produces the same `subject_kind` / `subject_id` / `field` / `text` — see the
  known-collateral note below about its *key-set* half), **DoD-3** (`CanvasField` still admits exactly
  `"name"` / `"body"`), **DoD-5** (nothing persists the selection — no code path exists at all),
  **DoD-11** (a turn with no subject is untouched: `NO_SUBJECT` and the fall-through are unchanged), and
  **DoD-12** (a seeding assertion over `seed_default_modes()`, which this step neither calls nor changes).
- **Must be red** — every one raises `NotImplementedError` from a named leaf, so it fails **loudly**, not
  by returning a plausible value: **DoD-6** (`open` → `write-chapter`), **DoD-7** (`closing` →
  `close-chapter`), **DoD-8** (`planned` / `closed` → no mode, therefore exactly `("web_search",)`) and
  **DoD-9** (a chapter in another book → no subject) all route through `_chapter_within_book` and/or
  `_mode_for_chapter_state`. Note that DoD-8's *expected* answer is `None`, so the "no chapter handling
  at all" stub would have gone **green by accident** — raising in `resolve_subject`'s chapter branch is
  what makes it a real assertion.
- **DoD-4** is red **only if it binds the plumbing.** Constructing `ToolContext(book_id=…, selection_text="x")`
  and reading it back is green by construction (a dataclass field). What is unimplemented is the
  *transfer*: a `TurnRequest` carrying `selection_text` produces a `ToolContext` whose `selection_text`
  is still `None`. A test that exercises request → context is red; one that only exercises the record is
  not.
- **DoD-10** (codex resolution and codex mode determination unchanged) is green and must **stay** green —
  it is the regression assertion over the restructured `determine_mode`.

#### Baseline (recorded before the coder starts)

Compile gate: `cd backend && .venv/Scripts/python -c "import app.main"` → **ok**, plus `model_fields` /
`dataclasses.fields` / `inspect.signature` smoke checks over every symbol frozen above → all as recorded.

`cd backend && .venv/Scripts/python -m pytest` → **1062 passed, 2 failed** (was 1064 passed, 0 failed on
the same tree with the four source files reverted; the two affected suites alone were `36 passed`
before). Both failures are **pre-existing `013.codex` tests**, both accounted for:

1. `tests/services/test_assistant_runtime.py::test_chapter_subject_has_no_mode_yet__DoD6` — passes
   `subject_kind="chapter", subject_id="12345"` and so hits the unimplemented `_chapter_within_book`.
   **Self-healing: no edit needed anywhere.** Once the coder implements it, an unknown chapter id yields
   `None` → `NO_SUBJECT` → `mode_key is None`, and `determine_mode(ResolvedSubject(kind="chapter"))`
   (chapter `None`) still returns `None`. Both of that test's assertions hold under the finished
   implementation.
2. `tests/routes/test_chat_turn_canvas.py::test_canvas_frame_reaches_the_stream_between_deltas__DoD2` —
   asserts `set(payload) == {"subject_kind", "subject_id", "field", "text"}`, i.e. the canvas payload's
   **exact key set**. `op` is now a fifth key. **This one does not self-heal** and is recorded under
   `## Notes & Issues` below: it needs a one-line update in a `013` test file that no `015` role owns.

### Step 010 — frozen interface (2026-07-30)

Backend only, exactly the step's two Source files: the **new**
`backend/app/services/chapter_tools.py` and four appended `TOOL_REGISTRY` entries in
`backend/app/services/tools.py`. **`backend/app/services/codex_tools.py` was neither imported,
generalised nor opened** — `chapter_tools.py` is its sibling, mirrored file for file, not its extension.
Nothing else in `tools.py` moved: no existing entry, no builder, no resolution or ordering rule, and
**not `ToolContext`** (step 009 widened it, and `access` already carries `role` / `book_state` /
`collaboration_mode`, so the refusal mirror is field reads and **no new plumbing** — no role, mode or
book-state field was added and no second `BookAccess` is resolved). **No `mode_tool` row and no
`AssistantMode` row is seeded, and no seed call was added** — the four ship *unreachable* by design
(D4).

#### `backend/app/services/tools.py` — four appended `ToolDef` entries

`TOOL_REGISTRY` goes **4 → 8**. The four are appended **after** `write_codex_draft`, in this declaration
order, which is part of the freeze (`services/assistant_config.py:list_tools` renders the catalogue in
registry order). Every one is **bound** — `binder` set, `callable` **`None`** — because each needs the
turn's book, its resolved chapter subject, the caller's access and the frame emitter, none of which a
plain module function can know. The four names collide with nothing: the registry's other four are
`web_search` / `codex_search` / `codex_read_entry` / `write_codex_draft`, and every synthetic
sub-agent tool is prefixed (`subagent_delegation.DELEGATION_TOOL_PREFIX`).

One import block added, from the new sibling module: `AddTextArgs`, `ReadChapterTextArgs`,
`SetChapterTextArgs`, `UpdateSelectionArgs`, `bind_add_text`, `bind_read_chapter_text`,
`bind_set_chapter_text`, `bind_update_selection`.

| # | `name` | `args_schema` | `binder` | frame `op` |
|---|---|---|---|---|
| 5 | `read_chapter_text` | `ReadChapterTextArgs` | `bind_read_chapter_text` | — (emits nothing) |
| 6 | `set_chapter_text` | `SetChapterTextArgs` | `bind_set_chapter_text` | `replace` |
| 7 | `update_selection` | `UpdateSelectionArgs` | `bind_update_selection` | `replace_selection` |
| 8 | `add_text` | `AddTextArgs` | `bind_add_text` | `append` |

The four names are `context.md` → D4's table verbatim and are **stable**: a `mode_tool.tool_name` is a
string reference into this registry, so renaming one later silently unselects it in every admin's mode.

#### The four descriptions — frozen text, part of the contract

`ToolDef.description` is what the model reads to decide whether and how to call a tool, and three of
these carry a fact the model would otherwise get wrong. Getting them wrong makes the model attempt a
placement negotiation the protocol deliberately does not support. **Verbatim, as committed:**

- `read_chapter_text` — *"Read the chapter the author currently has open and return its body text. This
  returns the SAVED body — the text as it was last saved to the server — so if the author has edited
  since their last save, their unsaved draft is newer than what you get back."* (the **saved**-body fact,
  D4's accepted limitation)
- `set_chapter_text` — *"Replace the whole body of the chapter the author currently has open. Send the
  complete new body in one call; it replaces everything that is there. Nothing is saved: the text only
  appears in the author's editor, where they read it, edit it and decide whether to keep it."*
- `update_selection` — *"Replace the text the author currently has selected in the open chapter with the
  text you send. The selection is the author's own and was supplied with this turn: do not describe
  where the text should go, do not quote the surrounding text as an anchor, and do not ask for line
  numbers or character offsets — there is no way to address a position. Send only the replacement text.
  Nothing is saved: it only appears in the author's editor."* (the **author's-current-selection** fact
  plus all three prohibitions, D5)
- `add_text` — *"Add text to the END of the body of the chapter the author currently has open. The end is
  the only place it can put text: it cannot insert anywhere else, so use the whole-body tool or the
  selection tool for that. Nothing is saved: the text only appears in the author's editor."* (the
  **end-only** fact)

#### `backend/app/services/chapter_tools.py` (new) — the frozen symbols

**Argument schemas** (declarative, complete — Pydantic `BaseModel` subclasses; every field description
is model-facing and frozen with the class):

- `class ReadChapterTextArgs(BaseModel)` — **new** — **no fields.** The chapter is the one the author has
  open, so there is nothing for the model to supply; a chapter-id or book-id field would be the second
  source of truth the no-subject-argument rule exists to prevent. `ToolDef.args_schema` is required, so
  the schema is declared rather than omitted, and the bound callable correspondingly has **zero** free
  parameters. **Interpretation recorded:** Interface intent's *"Each tool has a Pydantic argument schema
  — one text field each"* is read as *every tool has a schema; each **write** takes one text field*,
  because the read tool has no text to be given. DoD-1 only requires "a Pydantic argument schema"; this
  is the only reading under which the no-subject-argument rule survives. Verified: the OpenAI tool
  definition builds from an empty schema (`properties: {}`).
- `class SetChapterTextArgs(BaseModel)` — **new** — `text: str` (one field)
- `class UpdateSelectionArgs(BaseModel)` — **new** — `text: str` (one field). **The selection is not an
  argument** — it is the author's own and rides on `ToolContext.selection_text`.
- `class AddTextArgs(BaseModel)` — **new** — `text: str` (one field). No position, anchor or
  "after which paragraph" field exists, in any schema in this module.

**Private helpers** (both UNIMPLEMENTED — a bare `raise NotImplementedError(...)`):

- `def _resolved_chapter(context: "ToolContext") -> Chapter | None` — **new** — the chapter the turn's
  subject resolved to. `None` for no subject, a non-chapter subject, **and** a chapter that did not
  resolve inside this book — the cross-book case is answered by `resolve_subject` returning `NO_SUBJECT`
  before this module sees it, which is why there is **no book comparison here and must not be one**
  (DoD-9: refused by subject resolution, not by a check inside the tool). Reads `context.subject` only:
  **no database access**.
- `def _refuse_write(context: "ToolContext") -> str | None` — **new** — **the refusal mirror**, the
  chapter counterpart of `codex_tools.py::_refuse_write`. Returns **a string the model reads**, or `None`
  when the write is allowed, and it **NEVER raises**. Note the signature takes **only** the context — the
  codex twin's second `field` parameter exists for its fact-has-no-name rule, which has no chapter
  counterpart. **Exactly four rules, in this order:**
  1. the subject is not a chapter (`_resolved_chapter` is `None`) → `_NOT_A_CHAPTER_MESSAGE`;
  2. the chapter is not `open` → `_CHAPTER_NOT_OPEN_MESSAGE`, which **names the state**
     (`{state}` placeholder);
  3. `context.access.book_state` is `archived` → `_BOOK_ARCHIVED_MESSAGE` (D10);
  4. `context.access.role` is `co_author` **and** `context.access.collaboration_mode` is `proposal` →
     `_PROPOSAL_MODE_MESSAGE`, which **names FEAT-010** as unbuilt (D11). The **owner is never refused
     for mode**; the branch is `role == co_author`, never "not owner".

  Rules 3 and 4 are field reads off `ToolContext.access`. A context carrying **no** access is not refused
  by 3 or 4 — it can name neither an archived book nor a co-author — which is `codex_tools.py`'s reading
  of the same situation. **There is deliberately no fifth rule**: an absent `context.selection_text` is
  *not* a refusal (see the note under `## Notes & Issues`).

**The four tool callables** (all `async`, all taking the context **positionally first** so
`functools.partial(fn, context)` leaves exactly the schema's fields free — all UNIMPLEMENTED):

- `async def read_chapter_text(context: "ToolContext") -> str` — **new** — returns the resolved chapter's
  **saved** body. Subject to `_resolved_chapter` but **NOT** to `_refuse_write`: a `planned` / `closing` /
  `closed` chapter reads, an archived book's chapter reads, a co-author in a proposal-mode book reads.
  Touches no database — the body comes off the row the turn already resolved.
- `async def set_chapter_text(context: "ToolContext", text: str) -> str` — **new** — one frame,
  `op="replace"`.
- `async def update_selection(context: "ToolContext", text: str) -> str` — **new** — one frame,
  `op="replace_selection"`.
- `async def add_text(context: "ToolContext", text: str) -> str` — **new** — one frame, `op="append"`.

Each of the three writes emits **exactly one** frame through `context.emit_frame`, event **`"canvas"`**,
payload a `CanvasFrame` carrying `subject_kind="chapter"`, `subject_id=str(<resolved chapter>.id)`,
`field="body"`, the given `text` and its own `op`. **`CanvasField` was not widened** (D17). Emission goes
onto the same queue `run_turn` already pumps — **no manual `chat`-in-a-loop driver, no second
transport**. On every refusal path **no frame is emitted at all**.

**The four binders** (all UNIMPLEMENTED — each will be one `functools.partial(fn, context)`):

- `def bind_read_chapter_text(context: "ToolContext") -> Callable[..., object]` — **new** — the returned
  callable has **zero** free parameters.
- `def bind_set_chapter_text(context: "ToolContext") -> Callable[..., object]` — **new** — free
  parameters exactly `text`.
- `def bind_update_selection(context: "ToolContext") -> Callable[..., object]` — **new** — same.
- `def bind_add_text(context: "ToolContext") -> Callable[..., object]` — **new** — same.

**Module-level string constants** (declarative, complete — the module's frozen vocabulary, for the reason
`codex_tools.py` gives: the never-raise contract makes them the *only* signal the model gets, so the
wording must not drift between call sites). Refusals read *"Chapter draft refused: …"*, errors
*"Chapter draft error: …"* / *"Chapter error: …"*:
`_NOT_A_CHAPTER_MESSAGE`, `_CHAPTER_NOT_OPEN_MESSAGE` (formats `{state}`), `_BOOK_ARCHIVED_MESSAGE`,
`_PROPOSAL_MODE_MESSAGE` (names FEAT-010), `_NO_STREAM_MESSAGE`, `_DELIVERY_FAILED_MESSAGE`,
`_WRITE_FAILED_MESSAGE`, `_NO_CHAPTER_TO_READ_MESSAGE`, `_READ_FAILED_MESSAGE`,
`_WHOLE_BODY_WRITTEN_MESSAGE`, `_SELECTION_WRITTEN_MESSAGE`, `_APPENDED_MESSAGE`, plus
`_CANVAS_EVENT = "canvas"`, `_CANVAS_SUBJECT_KIND = "chapter"`, `_CANVAS_FIELD = "body"`.

**Structural properties that are part of the freeze:**

- **No `app.db` module is imported and none may be.** There is no code path from a chat turn to the
  `chapters`, `chapter_changes` or `chapter_text_revisions` tables, and **that absence is the guarantee,
  not a check** (DoD-4). `services/chapters.py` is likewise not imported.
- **No `session` / `AsyncSession` / `select()` / `session.exec()` / `session.add()`** anywhere — the
  services-layer rule.
- **`ToolContext` is quoted and `TYPE_CHECKING`-only imported**: `services/tools.py` imports *this*
  module, so a runtime import would be a cycle (the `codex_tools.py` discipline).
- **The stub bodies carry NO `try` / `except`.** Each raises `NotImplementedError` immediately. This is
  deliberate: the coder's never-raise outer guard would otherwise swallow the stub's own
  `NotImplementedError` and return `_WRITE_FAILED_MESSAGE` — a plausible refusal string that would
  satisfy DoD-5/6/7/8's "returns a string, emits no frame, raises nothing" **by accident**. The
  never-raise guard of the module's constraint 3 is the coder's to add.

- Caller-compile edits (out of Source-files scope): **None.** Every change is additive — the module is
  new, the four registry entries are appended, and no existing signature, name or ordering moved. One
  **pre-existing test** breaks on the widened registry; it is recorded under `## Notes & Issues` and was
  **not** edited (no `015` role owns it).

#### Compile gate

- `cd backend && .venv/Scripts/python -c "import app.main"` → **ok** (root `CLAUDE.md` declares **no
  backend typecheck**, so the gate is import + smoke).
- Registry smoke: 8 entries, names all distinct, in the frozen order; each of the four new ones has
  `callable is None` and `binder is not None` and a `BaseModel` `args_schema`;
  `llm.pydantic_to_openai_tool(name, description, args_schema)` builds for all four (`read_chapter_text`
  → `properties: []`, the other three → `['text']`).
- `inspect.signature` over all ten `chapter_tools` symbols matches the freeze; the four tool callables
  are coroutine functions, the two helpers and the four binders are sync.
- Gating smoke: `build_tool_bindings(TOOL_REGISTRY, None)` still yields exactly `['web_search']` in both
  maps, the four new names being *skipped and logged* like the three codex ones (DoD-10's path, green by
  construction).

#### Baseline (recorded before the coder starts)

- **Before this freeze:** `cd backend && .venv/Scripts/python -m pytest` → **1081 passed, 0 failed**
  (5m23s). This is step 009's delivered number, re-measured on the current tree.
- **After this freeze:** **1080 passed, 1 failed** (5m26s). The single failure is
  `tests/services/test_tools.py::test_registry_has_single_web_search_entry__DoD3`, which pins
  `TOOL_REGISTRY`'s **exact name set** to the four pre-015 names. It is a `011.chat-panel` test file that
  no `015` role owns, it does **not** self-heal, and it is recorded under `## Notes & Issues` with the
  one-line resolution. **No other test regressed from widening the registry** — every other suite derives
  its tool names from `TOOL_REGISTRY` rather than pinning them.

#### Red-gate profile

DoD-13 is `[manual/live]` (a real model, a real admin selection and a real streamed turn); **DoD-1 …
DoD-12 are `[test]`**.

- **Green by construction — declarative, arriving complete, so a PASS there is NOT evidence the step is
  done:**
  - **DoD-1** — *"All four tools are in `TOOL_REGISTRY` with distinct, stable names that collide with no
    existing entry, each carrying exactly one of a callable or a binder, and each with a Pydantic
    argument schema."* Every clause is data: registry entries, names, `binder`/`callable` and
    `args_schema` are declarations a skeleton cannot leave unimplemented. This one is green **now** and
    must simply stay green.
  - **DoD-12** — *"With no `mode_tool` rows … a turn whose subject is the book's `open` chapter is
    offered **none** of these four tools."* This step seeds nothing and changes no gating code, so
    `allowed_tool_names("write-chapter")` returns `()` today and will keep returning it. Green now; it is
    the assertion of a **negative** and is a regression guard, not behaviour to write.
  - Anything that merely *reads* a description string, constructs a `SetChapterTextArgs` /
    `UpdateSelectionArgs` / `AddTextArgs` / `ReadChapterTextArgs`, or names one of the module's message
    constants, resolves now. **A spec whose only failure would be an `AttributeError` on a constant is
    failing for the wrong reason.**
- **Must be red (`NotImplementedError` from a named stub — never a plausible value):** **DoD-2 … DoD-11.**
  - **DoD-2** (read returns the saved body in every state incl. `closed`), **DoD-3** (each write emits
    exactly one frame with the chapter id, `"body"`, the text and its own op) — red at the **binder**,
    because the binders raise too: `bind_set_chapter_text(ctx)` itself raises before any callable is
    produced. Expect `NotImplementedError: chapter_tools.bind_*`; calling the module function directly
    (`await chapter_tools.set_chapter_text(ctx, text="x")`) raises
    `NotImplementedError: chapter_tools.set_chapter_text`. Either entrance is a correct red.
  - **DoD-5** (no chapter subject), **DoD-6** (`planned` / `closing` / `closed`, refusal **names the
    state**), **DoD-7** (archived book), **DoD-8** (co-author in proposal mode names FEAT-010; the same
    call as **owner** succeeds), **DoD-9** (read refused on another book's chapter) — all four refusal
    rules and the read's subject rule route through `_resolved_chapter` / `_refuse_write`, both of which
    raise. A red-gate failure of the shape *"expected a refusal string, got `NotImplementedError`"* is the
    **correct** red.
  - **DoD-11** (*"No refusal path anywhere in this module raises"*) — this is the one that would be
    **inverted** by a careless stub. Against these stubs every call raises, so a spec asserting "does not
    raise" fails, which is exactly right. It must **not** be written as `try: … except: pass`.
  - **DoD-4** (*no write tool touches the database*) is the **vacuous-pass** item: a stub that raises
    writes nothing, so "the chapter's stored body, version and `modified_at` are unchanged and no
    `ChapterChange` / `ChapterTextRevision` row exists" is trivially true. It must assert the write's own
    success **first** (the frame was emitted, the confirmation came back) and only then read the three
    tables back — otherwise it is green at the red gate for the wrong reason.
  - **DoD-10** (*a tool offered with no tool context is skipped and logged rather than raising*) is
    **green by construction** in the direction that matters: `build_tool_bindings` skips a binder-bearing
    entry **before** calling the binder when `context is None`, and that is shipped `013` code this step
    does not touch. Listed here rather than above because the assertion still has bite as a regression
    guard over the four new entries.
- **No plausible value is returned anywhere.** Every callable, binder and helper raises; nothing returns
  `None`, `""`, an empty refusal or a `CanvasFrame`, so no assertion on a string, a frame or a tool
  result can be accidentally satisfied. The only non-raising additions are the four schemas, the four
  descriptions and the message constants — all data, and none of them reachable without going through a
  raising symbol.

### Step 011 — frozen interface (2026-07-30)

Frontend only. **Exactly the four Source files**, three pre-existing and widened additively plus one
new module. `frontend/src/work/restoreBuffer.ts` is **called, not changed** (not in the list, not
opened for edit). **`frontend/src/work/pages/CodexEntryPage.tsx` and
`frontend/src/work/pages/codexEntryPageState.ts` were NOT modified** — the whole point of the
type-level widening below (DoD-13's second half). `frontend/tests/**` was not touched by this role.

**`frontend/src/types/chats.d.ts`** — the **frame twin only**.

- `export type CanvasOp = "replace" | "append" | "replace_selection"` — **new**, complete. Declared
  immediately below the untouched `CanvasField`, mirroring `backend/app/models/schemas/chats.py`'s own
  placement (step 009's freeze) — same three values, same order.
- `export interface CanvasFrame` — **changed**, one field **appended**:
  `subject_kind: SubjectKind`, `subject_id: string | null`, `field: CanvasField`, `text: string`,
  **`op?: CanvasOp`**. Was the same four fields with no `op`.
  - **The `?` IS the mirror of the backend default.** `CanvasFrame.op: CanvasOp = "replace"` is a
    defaulted Pydantic field, so `op` is always present on the wire; a `.d.ts` carries no runtime
    default, so an **omitted `op` MEANS `"replace"`** and the default is applied at the single place
    that reads it — `contentSubject.ts` resolves `frame.op ?? "replace"`. A frame literal written with
    no `op`, and one written with each of the three values, must all compile.
- `export type CanvasField = "name" | "body"` — **unchanged, deliberately** (D17). No `"text"` member
  on either side of the wire.
- `TurnRequest` (`:159-164` → now `:177-182`) and the frontend-only `TurnSubject` helper — **not
  touched**: they are **step 012's** and gain nothing here.

**`frontend/src/work/subject.ts`** — `resolveEditability`'s `"chapter"` branch and the region
vocabulary it needs, and nothing else.

- `export type EditableRegion` — **changed** — one member **appended** after `014`'s five, which keep
  their names and order: `"none" | "whole" | "book-state-notes" | "chapter-sketch" |
  "chapter-own-prompt" | ` **`"chapter-text"`**. Six wide.
  - **Why the widening was necessary, and why it is the minimum.** `014` recorded *"there is
    deliberately NO `"chapter-text"` member … naming it separately would change the answer `open` gives
    today for no behaviour this feature ships"* — `015` **does** ship that behaviour, and the `open`
    verdict now has to say two things `"whole"` alone cannot: the body text is editable, and the
    **sketch is not** (UC-033 confines sketch edits to `planned`, the exact opposite window). One
    member, for the one region this feature ships. **Nothing else was added** — no `"chapter-summary"`,
    no `"chapter-title"`, no member for a write path nothing routes.
- `export interface Editability` — **shape unchanged** (`editable`, `readOnlyReason`,
  `editableRegions?`). Only the `editableRegions` doc comment moved, to record that the `open` chapter
  is now the **second** verdict that enumerates regions and that, unlike `planned`'s, its enumeration
  sits beside `editable: "whole"` rather than narrowing an `editable: "none"`.
- `export type WriteRegion = "whole" | "book-state-notes"` — **UNCHANGED**, and this is load-bearing.
  A chapter body write is still `checkWritePermission(chapter, "whole")` — `"whole"` **is** the body on
  a chapter — so no `"chapter-text"` write region is minted.
- `export function checkWritePermission(subject: LoadedSubject, region: WriteRegion): WriteDecision`
  — **byte-untouched.** Because `open` keeps `editable: "whole"`, it still **allows** a body write, and
  `planned` / `closing` / `closed` still refuse one, with no edit at all.
- `export function resolveEditability(subject: LoadedSubject): Editability` — **signature unchanged**;
  exactly one `case` of one `switch` changes and it is **UNIMPLEMENTED**:
  - **`open`** must return `{ editable: "whole", readOnlyReason: null, editableRegions:
    ["chapter-text", "chapter-own-prompt"] }`. `editable` and `readOnlyReason` **stay exactly as they
    are**; the missing part is the region list, naming the chapter's **body text** and the caller's
    **own chapter prompt**, and **NOT** `"chapter-sketch"`.
  - **`planned`, `closing`, `closed`, the `default` chapter case, and the codex / Book-state / list /
    outer-default rows are untouched, author-facing reason strings VERBATIM.** `planned` keeps
    `editable: "none"`, its `["chapter-sketch", "chapter-own-prompt"]` list and its sentence *"This
    chapter is still planned and cannot be edited until it is opened for writing."*
  - The branch carries a `SKELETON (015 step 011): UNIMPLEMENTED` comment naming the one field to add.
    **It could not be made to throw**: `resolveEditability` is shipped `010`/`014` code that
    `chapterPageState.ts`, `ChapterPage.tsx` and `codexEntryPageState.ts` all call on every render, so
    the existing verdict had to be preserved and the red for DoD-1/2 is a **missing field**, not an
    exception (see the red-gate profile).

**`frontend/src/work/contentSubject.ts`** — three widenings, **none of which costs the codex path a
line**. `ContentSubject`, `ContentSubjectSource`, `ContentSubjectRegistration`,
`registerContentSubject` and `currentContentSubject` are **unchanged**.

- `export type CanvasDraftApplier` — **changed** — one **optional third parameter** appended:
  `(field: CanvasField, text: string, op?: CanvasOp) => void`. Was `(field: CanvasField, text: string)
  => void`.
  - **A two-parameter function is assignable to a three-parameter type**, so
    `CodexEntryPageState.applyDraft = (field: CodexDraftField, text: string): void` satisfies the
    widened type **unedited** (`CodexDraftField` is `"name" | "body"`, i.e. `CanvasField`). Verified by
    `tsc`: neither codex file was opened.
  - `op` is optional **for assignability only**. {@link dispatchCanvasFrame} **always passes a third
    argument**, resolving an omitted `frame.op` to `"replace"` first, so a chapter page reads a real
    `CanvasOp` with no fallback of its own. **Consequence for specs: after the coder's fill, a codex
    frame's applier is called `(field, text, "replace")` — three arguments, not two.**
- `export function setContentSelection(source: ContentSubjectSource, selection: string | null): void`
  — **new**, UNIMPLEMENTED (throws `Error("not implemented: setContentSelection")`). The open page
  calls it whenever the author's selection moves; **newest caller wins outright**, exactly as
  `registerContentSubject` does. `selection` is the selected **text**, `null` when nothing is selected;
  `""` is stored as given and interpreted by nobody here.
- `export function currentContentSelection(): string | null` — **new**, UNIMPLEMENTED (throws). What
  the chat pane calls at **send time**, exactly as it already calls `currentContentSubject()`. `null`
  when nothing is registered / nothing is selected / the owning page has gone.
- `export function clearContentSelection(source: ContentSubjectSource): void` — **new**, UNIMPLEMENTED
  (throws). **Identity-guarded on the same token as the subject registry**: a clear only lands while
  `source` is still the selection's owner, so a superseded page's late unmount — or a trailing
  selection event — is a **no-op**. This matters more here than for the subject, because a selection
  setter fires constantly.
- **The identity token is the page's own `ContentSubjectSource`** — the same reference it already
  registers and unregisters with. No second token, no handle to thread, no `useCallback`.
- `export function unregisterContentSubject(source: ContentSubjectSource): void` — **signature
  unchanged**; its existing identity-guarded subject clear is preserved **byte-for-byte** and it must
  gain **exactly one line**, `clearContentSelection(source)`, so unregistering the subject clears the
  selection too. **Left out of the skeleton on purpose**: `clearContentSelection` throws, and every
  shipped page unmount runs through this function. Marked `SKELETON (015 step 011): UNIMPLEMENTED`.
- `export function dispatchCanvasFrame(bookId: string, frame: CanvasFrame): void` — **signature
  unchanged**; the body is `013`'s, **preserved byte-for-byte**, and carries a `SKELETON (015 step
  011): UNIMPLEMENTED` block naming the coder's entire diff:
  1. the matching target receives the operation —
     `target.applyDraft(frame.field, frame.text, frame.op ?? "replace")`;
  2. the fallback key's **`"codex-entry"` literal becomes `frame.subject_kind`** —
     `restoreBufferKey(bookId, frame.subject_kind, frame.subject_id)`, inheriting `readBuffer(key)
     ?.baseVersion ?? ""` exactly as today. **This is the one hardcoded thing that has to change**;
  3. a targetless frame whose resolved operation is **not** `"replace"` is **dropped and logged before
     anything is written to any buffer key** (D18).
  - **Unchanged and deliberately so:** the kind-AND-id match (`entityId ?? null` vs `subject_id`, so
    UC-076's blank entry still matches null-to-null), the `subject_id === null` drop, and — critically
    — the **`frame.field !== "body"` condition**, because a chapter's body is *also* the `"body"` field
    (D17), so it already admits both kinds and needs no widening.
  - **Routing on `subject_kind` is not a registry of per-kind handlers.** There are two kinds and a
    third is not on the roadmap (`011.context.md`).
- `function unimplemented(fn: string, ..._args: unknown[]): never` — module-private skeleton sink
  (throws), also consuming the frozen parameter lists so they satisfy `noUnusedParameters`. The coder
  deletes it.

**`frontend/src/work/chapterUndo.ts`** — **NEW FILE**; the module tier's **fourth** member beside
`restoreBuffer.ts` / `activeChat.ts` / `contentSubject.ts`, sanctioned by D6 and recorded in
`outcome.md`. **Plain module functions matching its three siblings** — no class, no MobX, no
reactivity, no React, no `src/api/` import — and **in memory only**: nothing reaches `localStorage`,
nothing survives a reload, the module survives page navigation because it is module-level. All four
bodies are UNIMPLEMENTED (throw `Error("not implemented: <fn>")` through the same private sink).

- `export function pushChapterUndoSnapshot(bookId: string, chapterId: string, body: string): void`
  — **new**. `body` is the draft **as it is about to be overwritten** (the caller snapshots before
  applying). `""` is a legitimate snapshot. At most **20** per pair; a push onto a full stack drops the
  **oldest**.
- `export function popChapterUndoSnapshot(bookId: string, chapterId: string): string | null` — **new**.
  Removes and returns the **most recent** snapshot for the pair, `null` when the stack is empty.
  **`null` vs `""` is the reason the return is nullable** — a popped empty body is `""`, not "nothing
  to undo".
- `export function chapterUndoDepth(bookId: string, chapterId: string): number` — **new**. `0` for a
  pair never pushed to; never throws for an unknown pair (an undo control reads it to enable itself).
- `export function clearChapterUndo(bookId: string, chapterId: string): void` — **new**. Drops one
  pair's stack, leaves every other pair untouched; clearing an empty pair is a no-op.
- **Pairs are independent**: `(bookId, chapterId)`, so the same chapter number in another book is a
  different stack.
- `const MAX_SNAPSHOTS = 20` — **module-private on purpose.** Nothing outside needs it, and an exported
  constant would invite a spec to assert the constant instead of the behaviour. The cap is part of this
  freeze, not of the module's API.
- **The stack is NOT cleared on save** — nothing in this module or in step 012's intent calls
  `clearChapterUndo` from a save path (D6: an author may want to undo an assistant write after saving).

Caller-compile edits (out of Source-files scope): **None.** Every widening is an appended union member,
an appended optional interface field, an optional trailing parameter or a new module, so no call site in
`src/` needed adapting. The two source readers of `resolveEditability`
(`chapterPageState.ts:sketchDisabledReason`, `ChapterPage.tsx:bodyReadOnlyReason`) read
**`readOnlyReason` only**, and `open`'s stays `null`.

#### Compile gate and baseline (recorded before the test-coder and the coder start)

- `cd frontend && npx tsc --noEmit` → **clean**.
- `cd frontend && npm run build` (`tsc && vite build`) → **clean**, built in 7.7s, all five entries
  emitted.
- `cd frontend && npm run test:types` → **clean** (the shipped `013` specs still compile against the
  widened `CanvasDraftApplier` and the widened `CanvasFrame`).
- `npm test` was **NOT** run — the verifier owns it. **Recorded baseline: 546 passed** (the last green
  frontend run, after step 010). Any regression on the codex path is a drop from that number; see
  "Known collateral" for the two assertions that are *expected* to move once the **coder** lands the
  behaviour (they are green today, against this skeleton).

#### Red-gate profile

- **Green by construction — a PASS there is NOT evidence the step is done:**
  - **DoD-12** — the `.d.ts` change is **declarative and arrives complete**. `CanvasOp`'s three members
    and `CanvasFrame.op` are final as written; there is nothing to leave unimplemented. Assert it the
    way `011.context.md` prescribes — frame literals of each operation plus one with `op` omitted — and
    let **`npm run test:types`** be the gate that they compile. Do not import runtime values from a
    declaration file. `CanvasField` still admitting exactly `"name"` / `"body"` is likewise green and is
    a regression assertion.
  - **DoD-3** — `checkWritePermission` is **byte-untouched** and `open` keeps `editable: "whole"`, so
    "allows a body write on `open`, refuses on `planned` / `closing` / `closed`" passes **today**. It is
    the regression guard that proves the region widening did not move the write path, and it must keep
    passing. The body write region is **`"whole"`**.
  - **DoD-5** — "a frame whose subject does not match the registered target is not delivered to it" is
    shipped `013` behaviour (the kind-AND-id match), untouched here. Regression guard.
  - **DoD-6, the type half** — "an applier taking only two parameters still satisfies the registry" is a
    **compile-time** claim about the widened `CanvasDraftApplier`, complete now and gated by
    `npm run test:types`.
  - **DoD-13** — `npm run build` and `npm run test:types` already pass against this skeleton; the "was
    not modified" half is a **verifier observation**, not a spec assertion.
- **Must be red, and the shape of the red matters:**
  - **DoD-1 / DoD-2** — the `open` verdict's `editableRegions` is **absent**, so the red is
    `undefined`, **not** a thrown error. `resolveEditability` could not be stubbed to throw (shipped
    code, called on every chapter and codex render), so this is the one place where the red is a missing
    field. Expect *"expected `["chapter-text","chapter-own-prompt"]`, received `undefined`"*.
    - **DoD-2 is the vacuous-pass trap of this step.** `expect(result.editableRegions ?? [])
      .not.toContain("chapter-sketch")` passes **today**, against the absent field. Write DoD-2 so it
      cannot: assert the **exact** array (`toEqual(["chapter-text", "chapter-own-prompt"])`, or
      `toHaveLength(2)` plus the two members) in the same case that denies the sketch.
  - **DoD-4** — the matching target's applier is called with **two** arguments today, so
    `toHaveBeenCalledWith(field, text, op)` fails on the recorded 2-argument call. That mismatch is the
    **correct** red for "receives its text, its field and its operation".
  - **DoD-7** — a chapter frame with `op: "replace"` and no target is buffered under the **codex-entry**
    key today, so `readBuffer(restoreBufferKey(bookId, "chapter", id))` comes back `null`. Expect
    *"expected the text, received `undefined`/`null`"*. Assert the **chapter** key positively; also
    assert the inherited `baseVersion` (whatever already sits at that key, `""` when there is none).
  - **DoD-8** — a chapter `append` / `replace_selection` frame with no target is buffered today (the
    dispatcher ignores `op`), so *"nothing is written to any buffer key"* fails. Assert over **all**
    restore-buffer keys, not just the chapter's, or the codex-key write will slip through.
  - **DoD-9** — all three selection functions throw
    (`Error("not implemented: setContentSelection" | "currentContentSelection" |
    "clearContentSelection")`), so every leg is red. Note that "returns nothing after that owner
    unregisters" additionally depends on the one line `unregisterContentSubject` still lacks.
  - **DoD-10 / DoD-11** — all four `chapterUndo.ts` functions throw. `popChapterUndoSnapshot` and
    `chapterUndoDepth` raise rather than returning `null` / `0`, so "nothing when empty" and "the
    control is unavailable when the stack is empty" cannot pass against an empty module.
    - **DoD-11 carries the second vacuous-pass trap**: *"nothing the module holds is written to
      `localStorage`"* is trivially true of a module that throws. It must assert a successful
      **push → depth → pop** round trip **first**, and only then inspect `localStorage` (and it must
      scope that inspection so the restore buffer's own keys, if any, are not mistaken for this
      module's).
- **No plausible value is returned anywhere in the new surface.** Every new function routes through a
  `never`-returning sink, so no `null`, `0`, `""` or empty region list can satisfy an assertion by
  accident. The two non-throwing additions are **data**: the `.d.ts` types (erased at runtime) and the
  `"chapter-text"` union member (also erased) — neither can satisfy a behavioural assertion on its own.

#### Known collateral — two shipped assertions this step's *coder* will invalidate

Both are **green today** (the skeleton changed no behaviour) and go red only when the coder lands the
frozen contract. Recorded here so neither is mistaken for a regression at the verify run:

1. `frontend/tests/work/subject.test.ts` — the `014` case titled *"DoD-12: `open` keeps the answer it
   gives today — editable whole, no reason, **no region list**"* asserts
   `expect(result.editableRegions).toBeUndefined()`. That third assertion is **superseded by this
   step's DoD-1/2** (its first two — `editable === "whole"`, `readOnlyReason === null` — stay true and
   must be kept). **This file is in step 011's Test files list**, so the test-coder owns the fix: update
   that one assertion in place; restructure and rename nothing else in the file.
2. `frontend/tests/work/contentSubject.test.ts` — three `013` assertions read
   `expect(applyDraft).toHaveBeenCalledWith("body" | "name", <text>)`, i.e. **exactly two arguments**.
   The dispatcher will pass three (`…, "replace"`). **This file is in NO 015 step's Test files list**,
   so no role in this feature owns it — see `## Notes & Issues`.

### Step 012 — frozen interface (2026-07-30)

Frontend only, **exactly the five Source files** — but three of them barely move:

| File | This freeze |
|---|---|
| `frontend/src/work/pages/chapterPageState.ts` | the whole freeze: 2 ids, 2 fields, a changed constructor, 2 bound members, 2 effects |
| `frontend/src/work/pages/ChapterPage.tsx` | **ONE mechanical line** — the changed constructor call. The view surface is frozen as prose below and is the coder's, exactly as in steps 006 / 007 / 008 |
| `frontend/src/types/chats.d.ts` | one appended optional field on `TurnRequest` (declarative, arrives complete) |
| `frontend/src/api/chats.ts` | one appended optional parameter on `streamChatTurn`, marked UNIMPLEMENTED |
| `frontend/src/work/components/chat/chatPaneState.ts` | **DELIBERATELY UNCHANGED** — see below |

**Not opened at all:** `work/contentSubject.ts`, `work/subject.ts`, `work/chapterUndo.ts`,
`work/restoreBuffer.ts`, `api/sse.ts`, `components/chapter/ChapterBodyEditor.tsx` — all **consumed**,
none modified. **`CodexEntryPage.tsx` and `codexEntryPageState.ts` were NOT opened for edit** (the
whole feature's rule); the codex page is read-only prior art here. `frontend/tests/**` untouched.

#### `chapterPageState.ts` — the two ids the module tier forced onto the instance

The registry hands `subjectSource` and `applyDraft` across the module boundary and then calls them with
a **fixed argument list that carries no ids**. A bound callback can only reach the pair through `this`,
so `ChapterPageState` now stores it. **014's every-effect-takes-the-pair shape is kept intact** — no
frozen effect signature moved.

- `frontend/src/work/pages/chapterPageState.ts` — `ChapterPageState.bookId: string` (`readonly`,
  non-observable) — **new**
- `frontend/src/work/pages/chapterPageState.ts` — `ChapterPageState.chapterId: string` (`readonly`,
  non-observable) — **new**
- `frontend/src/work/pages/chapterPageState.ts` — `constructor(bookId: string, chapterId: string)` —
  **changed** (was `constructor()`), and
  `makeAutoObservable(this, { bookId: false, chapterId: false, subjectSource: false, applyDraft: false })`
  — **changed** (was the no-argument `makeAutoObservable(this)`; steps 006–008 each recorded "keeps its
  no-arguments form", and **this is the step that changes it**, for exactly the reason
  `codexEntryPageState.ts` does: MobX would otherwise try to make a bound method observable).
  - **Both parameters are REQUIRED, not defaulted.** A `""` default would silently build the wrong
    restore-buffer key and the wrong undo-stack pair; the compiler catching the one call site is worth
    more. There is exactly one call site in `src/` and **no spec constructs `ChapterPageState` directly**
    (checked: the only occurrences were the docstring and `ChapterPage.tsx:148`), so nothing under
    `frontend/tests/` needed touching.

#### `chapterPageState.ts` — the selection and the refusal report (two observable fields)

- `frontend/src/work/pages/chapterPageState.ts` — `ChapterPageState.selectedText: string | null = null`
  — **new** — the author's current selection **text**. Written by exactly one function,
  {@link setChapterSelection}. **`""` is stored as `null`**, so "nothing is selected" has one
  representation. Never persisted, never buffered, never saved (D5).
- `frontend/src/work/pages/chapterPageState.ts` —
  `ChapterPageState.unappliedSelectionWrite: string | null = null` — **new** — the **text** a
  `replace_selection` frame carried when there was no selection to replace; `null` when there is nothing
  to report. Cleared by the next frame that DOES apply.

#### `chapterPageState.ts` — the two bound members the module tier holds (both throw)

Both are bound arrow properties on the instance, both excluded from `makeAutoObservable`.

- `frontend/src/work/pages/chapterPageState.ts` —
  `readonly subjectSource: ContentSubjectSource = () => ContentSubject` — **new**, UNIMPLEMENTED
  (throws `Error("not implemented: ChapterPageState.subjectSource")`).
  - Contract: return `{ kind: "chapter", entityId: this.chapterId, chapterState: this.chapter?.state }`
    — **the object 014 already builds inline in the mount effect, unchanged**, read at CALL time so the
    lifecycle state is current, and keyed on the **route's** chapter id so a turn sent before the load
    resolves still names the right chapter.
  - **Why it moved out of the effect and onto the instance — this is the load-bearing decision of the
    step.** It is the **identity token** for four call sites: `registerContentSubject`,
    `unregisterContentSubject`, `setContentSelection` and (transitively)
    `clearContentSelection`. The selection is pushed from the editor's `onSelectionChange` **during
    render**, where the mount effect's local `const source` is not in scope, and `useCallback` is banned
    and a second `useState` is not permitted for it. A bound property on a per-route instance gives all
    four the same stable reference with no new hook and no second registry. **DoD-8's "leaving the page
    clears it" depends on this**: `unregisterContentSubject(source)`'s shipped
    `clearContentSelection(source)` line only fires when the two tokens are the same reference.
- `frontend/src/work/pages/chapterPageState.ts` —
  `readonly applyDraft = (field: CanvasField, text: string, op?: CanvasOp): void` — **new**,
  UNIMPLEMENTED (throws `Error("not implemented: ChapterPageState.applyDraft")`).
  - Structurally satisfies step 011's `CanvasDraftApplier`. `op` is optional only because that type
    declares it so (a two-parameter codex applier must stay assignable); `dispatchCanvasFrame` **always**
    passes a real `CanvasOp`, having resolved an omitted `frame.op` to `"replace"` first.
  - **A `"name"` frame is IGNORED** — a chapter has no name on the canvas; its body IS the `"body"`
    field (D17). Nothing changes, nothing is reported.
  - **THE REFUSAL COMES FIRST.** A `"replace_selection"` frame is **not applied** when
    `selectedText === null`, **or** when `selectedText` is a string the current draft no longer contains:
    record the frame's text in `unappliedSelectionWrite` and **return, having changed nothing — no undo
    push, no draft write, no buffer write, no generation bump**. **No fallback to append, ever, and never
    applied at position zero.** Page-level, not tool-level, on purpose (step 010 froze the tool with
    exactly four refusal rules and no selection rule — see `## Notes & Issues`).
    - *The "selection no longer present in the draft" leg is the one judgement this freeze adds.* The
      plan names only the no-selection case; an `indexOf` miss is the same failure one step further on
      (a location nobody chose), and leaving it unfrozen invites an accidental splice at index `-1`.
      No DoD exercises it.
  - **THE APPLY ORDER IS FROZEN AS FOUR STEPS, in this order:**
    1. `pushChapterUndoSnapshot(this.bookId, this.chapterId, this.bodyDraft)` — **the pre-write draft,
       before anything is applied**. Applying first stores the post-write text and makes undo a no-op.
    2. apply the operation to the draft — `"replace"` → the frame's text becomes the whole draft;
       `"append"` → the text goes at the END of the current draft; `"replace_selection"` → the text
       replaces the **first occurrence** of `selectedText` within the draft.
    3. `editBodyDraft(this, this.bookId, this.chapterId, next)` — **step 006's single draft-edit path**,
       so the restore buffer is written exactly as a keystroke writes it and an eviction surfaces
       exactly as a keystroke's does. Bypassing it loses the assistant's draft on a reload.
    4. `this.bodyEditorGeneration += 1` — so TipTap remounts on the NEW draft (D15). Bumping before
       applying remounts on the old one.
    - then `unappliedSelectionWrite = null` — a frame that landed supersedes a report of one that did not.
  - **Nothing reaches the server.** An assistant write is a draft edit and nothing else.

#### `chapterPageState.ts` — the two external effects (both throw)

Both are **synchronous and server-free**, so neither takes a `signal` and neither returns a `Promise`.
Both route their frozen parameter list through a module-private
`function unimplemented(fn: string, ..._args: unknown[]): never` sink (the shape steps 004–011 used).
**The coder deletes the sink with the last stub.**

- `export function setChapterSelection(state: ChapterPageState, selectedText: string): void` — **new**.
  - `selectedText` is `ChapterBodyEditor`'s own value **verbatim** — step 005 froze
    `onSelectionChange: (selectedText: string) => void`, reporting **`""` for an empty selection** — so
    the prop binds with no wrapper logic in the view.
  - Contract: `runInAction` → `state.selectedText = selectedText === "" ? null : selectedText`; then
    `setContentSelection(state.subjectSource, state.selectedText)`.
  - **Takes NO ids, deliberately** — the one effect in this module that does not. A selection is keyed by
    nothing, buffered under nothing and stored nowhere that needs a key, and the registry's identity
    token is `state.subjectSource`. (Contrast `editBodyDraft`, which took its two ids a step early
    precisely because a key was coming.)
- `export function undoAssistantBodyWrite(state: ChapterPageState, bookId: string, chapterId: string): void`
  — **new**.
  - Contract: `popChapterUndoSnapshot(bookId, chapterId)`; `null` → **return, changing nothing**;
    otherwise set the popped text as the draft **through the same `editBodyDraft` path**, then bump
    `bodyEditorGeneration`.
  - **IT PUSHES NOTHING.** Re-snapshotting would make the stack un-walkable.
  - Carries the module's `(state, bookId, chapterId)` shape, so the page passes the pair exactly as it
    does to every other effect; the instance's own copies exist for the **callbacks**, which are handed
    no arguments at all.

#### `frontend/src/types/chats.d.ts` — the turn-request twin only

- `export interface TurnRequest` — **changed**, one field **appended**: `prompt: string | null`,
  `subject_kind?`, `subject_id?`, `codex_kind?`, **`selection_text?: string | null`**. Mirrors the
  backend field step 009 shipped (`models/schemas/chats.py:228`, `selection_text: str | None = None`),
  in the same position and with the same optionality.
- **A FLAT FIELD, and the frontend-only `TurnSubject` helper (`:144-148`) gains NOTHING** — it has no
  backend counterpart, a selection is not part of the subject's identity (the same chapter can be in
  view with any selection or none), and putting it there would give the client a shape the wire does not
  have. **DoD-9 asserts the flat placement.**
- `CanvasFrame`, `CanvasOp`, `CanvasField`, `SubjectKind` — **untouched** (step 011's / D17's).

#### `frontend/src/api/chats.ts` — one appended parameter, marked UNIMPLEMENTED

- `export async function streamChatTurn(bookId: string, chatId: string, prompt: string | null, handlers: TurnStreamHandlers, subject?: TurnSubject, selectionText?: string | null): Promise<AbortController>`
  — **changed** (was the same five parameters with no `selectionText`).
  - A **separate parameter**, not a member of `subject`, for the same reason the wire field is flat.
  - **UNIMPLEMENTED**: the shipped body is preserved byte-for-byte and `selectionText` is consumed by a
    `void selectionText;` line (`noUnusedParameters` is on) with a `SKELETON (015 step 012):
    UNIMPLEMENTED` marker. **It could not be made to throw** — `streamChatTurn` is shipped `011` / `013`
    code that every turn in the app goes through. The coder's entire diff is one conditional spread on
    `body`.
  - **Frozen contract for that diff:** `selection_text` is added **when and only when** `selectionText`
    is neither `undefined` nor `null`; the key is otherwise **ABSENT from the posted body**, so a turn
    with a subject and no selection posts exactly the four fields `013` posted and a turn with nothing
    registered still posts exactly `{ prompt }`.
  - **No other change**: `TurnStreamHandlers`, the `refreshAuthToken()`-first ordering, the `streamPost`
    seam (it owns its own `AbortController`; no `signal` parameter is added), the generic-event routing
    and `canvasFrame` / `frameText` are untouched. **`api/sse.ts` was not opened.**

#### `chatPaneState.ts` — deliberately UNCHANGED by this freeze

**No signature in that module moves.** `sendChatTurn(state, bookId, text)`,
`retryChatTurn(state, bookId)` and the module-private `turnSubject(): TurnSubject | undefined` keep
their exact shapes; the change is **behaviour inside two call sites**, which is the coder's. Frozen
contract:

- both `chatsApi.streamChatTurn(...)` calls gain a **sixth argument**,
  `currentContentSelection() ?? undefined`, read **at send time and at retry time**, in the same call
  site that already reads the subject (`turnSubject()`);
- **`ChatPaneState` gains NO selection field**, no observer relationship to the content pane, and
  nothing is passed down through the shell. `turnSubject()` is **not** widened — the selection is not a
  subject field. The panes stay independent because nothing links them but a function call.

#### `ChapterPage.tsx` — the one mechanical edit, and the frozen view surface

**The only edit made:** `const [state] = useState(() => new ChapterPageState(book, chapterId));`, with
the two existing `const book` / `const chapterId` lines moved **above** it so the ids are in scope. No
other line of the file changed; the mount effect, every branch and the docstring are as step 008 left
them. (The docstring's "no canvas / undo / selection wiring (step 012)" paragraph is now the coder's to
replace.)

Everything below is **frozen prose, not written code** — the pattern steps 006 / 007 / 008 used, and it
is part of the freeze because **queries in this project are by role or label only**, so an unfrozen
accessible name would break the air gap.

| Element | Frozen name / text |
|---|---|
| Mount registration | `registerContentSubject(state.subjectSource, state.applyDraft)` — **the same call 014 makes, now with the second argument**. The inline `const source` closure is deleted; `state.subjectSource` replaces it at both the register and the unregister site |
| Unmount cleanup | `unregisterContentSubject(state.subjectSource)` then `ctrl.abort()` — order unchanged. The shipped `clearContentSelection(source)` inside it is what clears the selection (DoD-8) |
| Editor's selection prop | `onSelectionChange={(selectedText) => setChapterSelection(state, selectedText)}` — replaces step 006's `() => {}` no-op. **The only change to the `ChapterBodyEditor` element**; its other three props and the `key={state.bodyEditorGeneration}` are unchanged |
| **Undo control** | a `Button` whose accessible name is exactly **`Undo the assistant's last write`**, rendered **beside `Save body` in the same `Group`** (so it exists only where the editor does), `disabled={chapterUndoDepth(book, chapterId) === 0}`, `onClick` → `undoAssistantBodyWrite(state, book, chapterId)` |
| **Unapplied-write surface** | an `Alert` `color="yellow"` titled exactly **`The assistant's write was not applied`**, rendered whenever `state.unappliedSelectionWrite !== null`, carrying that text **verbatim** plus one sentence saying nothing was selected, so nothing was changed. Rendered **inside the body `Stack`, independently of every body branch**, exactly where and how step 007's eviction notice is |

- **The undo control's label is frozen because of what it promises.** It undoes **the assistant's last
  write**, not "the last change": the author's own typing is undone inside the editor by ProseMirror's
  history (D6), and a generic label would promise an affordance that does not exist and leave the two
  undo paths reading as inconsistent.
- **The control is RENDERED-AND-DISABLED, not absent, when the stack is empty.** That is the opposite of
  step 008's transition control, deliberately: a transition that is not offered has a *reason* rendered
  beside it, whereas "there is nothing to undo yet" needs no sentence, and a control that appears only
  after the first assistant write would move the save control under the author's cursor. DoD-7's
  "unavailable" therefore means **present and disabled**.
- **The depth is read directly from the module, NOT through a computed.** `chapterUndoDepth` reads a
  plain module-level `Map` with no observable inside it, so a `get` computed over it would be cached and
  **never invalidated** inside an `observer` — a real bug, not a style point. The direct read is current
  because every push and every pop is paired with a bump of the **observable**
  `state.bodyEditorGeneration`, which the same component already reads for the editor's `key`; that read
  is what schedules the re-render.
- **No new `useEffect`, no second `AbortController`, no `useCallback` / `useMemo`, no custom hook, no
  context, no confirmation dialog.** The undo handler and the selection handler are inner functions.

#### Compile gate and baseline (recorded before the test-coder and the coder start)

- `cd frontend && npx tsc --noEmit` → **clean**.
- `cd frontend && npm run build` (`tsc && vite build`) → **clean**, built in 7.6s, all five entries
  emitted (the ~768 kB `work` chunk warning is step 006's, unchanged).
- `cd frontend && npm run test:types` → **clean** — every shipped spec still compiles: nothing
  constructs `ChapterPageState` directly, and `streamChatTurn`'s sixth parameter is optional, so `013`'s
  five-argument call sites and their mocks are unaffected.
- Runtime smoke (isolated MobX probe, nothing written into the repo): a class with these fields, this
  constructor and these two excluded bound members **constructs** — `makeAutoObservable` accepts the
  four-key annotation object, the ids survive, the shipped computeds still evaluate — and each bound
  member throws `not implemented: …` **on call**.
- `npm test` was **NOT** run — the verifier owns it. **Recorded baseline: 602 passed** (the last green
  frontend run, after step 011). Any regression on the **chat-pane** or the **codex** path is a drop
  from that number; nothing in this freeze changes a shipped behaviour, so 602 should hold at the red
  gate.

#### Red-gate profile

DoD-1 … DoD-10 are `[test]`; **DoD-11 and DoD-12 are `[manual/live]`** and get no spec. Note that
`npm run build` and `npm run test:types` (half of DoD-12) already pass against this skeleton — a PASS
there is not evidence the step is done.

- **Green by construction — a PASS is NOT evidence of anything:**
  - **The `.d.ts` change.** `TurnRequest.selection_text` is declarative and arrives complete. Assert it
    the way step 011's `CanvasOp` was asserted — a request literal carrying `selection_text` beside
    `subject_kind` / `subject_id` / `codex_kind` compiles, one without it still compiles — and let
    **`npm run test:types`** be the gate. **Do not import runtime values from a declaration file.**
    `TurnSubject` still admitting exactly its three members is likewise green and is a **regression
    assertion**: a spec that adds `selection_text` to a `TurnSubject` literal must fail to compile.
  - **The four new observable/plain fields.** `selectedText` (`null`), `unappliedSelectionWrite`
    (`null`), `bookId`, `chapterId` all read correctly today. Data cannot be left unimplemented; the red
    must come from the function that is supposed to **change** one of them.
  - **Every shipped surface** — 014's sections, step 006's editor and `Save body`, step 007's divergence
    view and eviction notice, step 008's transition control — keeps passing. Those are regression guards.
- **Must be red, and in one of exactly three shapes:**
  1. **Through the page (the specs' normal route).** `ChapterPage.tsx`'s view is unchanged, so there is
     **no undo control, no unapplied-write alert, and `onSelectionChange` is still a no-op**, and the
     registration still passes **no** `applyDraft`. Expect **query misses** ("unable to find a
     role/label…") and — for DoD-1 / DoD-2 — a `canvas` frame delivered through the **real**
     `dispatchCanvasFrame` falling through to the **restore-buffer fallback** instead of reaching the
     page, because the registration has no callback. That is the correct red for **DoD-1, 2, 3, 4, 5, 6,
     7, 8**.
  2. **Driving a member directly.** `state.applyDraft(...)`, `state.subjectSource()`,
     `setChapterSelection(...)` and `undoAssistantBodyWrite(...)` all throw
     `Error("not implemented: …")` synchronously.
  3. **Through the chat pane (DoD-9).** `chatPaneState` passes no sixth argument and `streamChatTurn`
     drops the one it now accepts, so the mocked stream function is handed a request body with **no
     `selection_text` key**. Expect *"expected `selection_text` to be the selected text, received
     `undefined`"*.
- **The items that can pass VACUOUSLY against this skeleton — write the presence assertion FIRST or they
  are green at the red gate for the wrong reason:**
  - **DoD-4** ("an applied frame … reaches the server not at all") — trivially true when no frame is
    ever applied. Assert the **draft actually changed** (through the stubbed editor's re-read initial
    Markdown) **and** the restore buffer was written, *then* that `updateChapterText` was never called.
  - **DoD-6** ("a replace-selection frame with no active selection changes nothing … never appended and
    never applied at position zero") — "changes nothing" is trivially true today. Assert the **reporting
    surface appears** first — that is the half that cannot pass vacuously — and only then that the draft
    is byte-identical and contains the frame's text at neither end.
  - **DoD-7**'s first half ("the undo control is unavailable when the stack is empty") — trivially true
    when no control is rendered. Assert the control **exists and is ENABLED after one assistant write**
    first; and drive the 20-deep half through the module (`pushChapterUndoSnapshot` ×21 then 21 pops), not
    through the label.
  - **DoD-10** ("the selection is never saved") — trivially true when nothing sets a selection. Assert
    that `currentContentSelection()` **returns the selected text** first, then that no write call was
    made and that a subsequent save's payload has exactly `text` + `expected_version`.
  - **DoD-1**'s second half ("a chapter that is not `open` registers a subject but offers no writable
    target") — "no writable target" is trivially true today. Assert the **subject is registered** (the
    turn carries `subject_kind: "chapter"` with the right id) in the same case.
  - **DoD-5** ("the editor remounts on an applied frame and on an undo, and does NOT remount on a
    keystroke") must be observed **behaviourally** — the stubbed editor re-reads its `initialMarkdown`
    prop — never by reading `bodyEditorGeneration` by name.
- **No plausible value is returned anywhere in the new surface.** Every new function routes through a
  `never`-returning sink. The two non-throwing additions are **data**: the `.d.ts` field (erased at
  runtime) and the two `null` fields — neither can satisfy a behavioural assertion on its own. The one
  UNIMPLEMENTED-but-non-throwing site is `streamChatTurn`'s `void selectionText;`, whose red is a
  **missing key** on the request body, not an exception.
- **Carried-forward mocking notes for the test-coder** (from `012.context.md`, restated because they
  bind to this freeze): mock the whole `../../src/api/chapters` module (all ten exports) and the
  `../../src/work/components/chapter/ChapterBodyEditor` module (a stub typed against the exported
  four-prop `ChapterBodyEditorProps`, which **must drive `onSelectionChange` as well as `onChange`**);
  use `contentSubject.ts`, `chapterUndo.ts` and `restoreBuffer.ts` **real**, and deliver frames by
  calling the real `dispatchCanvasFrame` — that is what makes DoD-1's registration assertion mean
  something. Clear `localStorage` **and** the undo stacks (`clearChapterUndo`) between tests. For
  DoD-9 mock `api/chats.ts`'s `streamChatTurn` and assert the **request body it was handed** — do not
  open a real stream and do not use `support/sseFixture.ts`.
- **One live-path gap is recorded in `## Notes & Issues`** (`api/chats.ts`'s `canvasFrame` narrowing
  discards `op`, so every frame arriving over SSE reads as `"replace"`). It is invisible to DoD-2 /
  DoD-3 / DoD-5 / DoD-6 because the specs call the dispatcher directly, and it is **DoD-11**'s to catch.
  The orchestrator has to decide whether step 012's `api/chats.ts` scope widens by one line.

- Caller-compile edits (out of Source-files scope): **None.** The one changed signature
  (`ChapterPageState`'s constructor) has exactly one call site and it is inside a Source file
  (`ChapterPage.tsx`); `streamChatTurn`'s new parameter is optional, so its two shipped call sites in
  `chatPaneState.ts` and every mock of it still compile untouched.

### Step 013 — frozen interface (2026-07-30)

Backend only. **One source file, `backend/app/services/chat_turn.py`** — exactly the step's Source list.
`services/prompt_composition.py` was **not opened for edit**: its fourth parameter has existed since
`011` step 002 and this step only fills it (DoD-7). No DTO, no route, no table, no capability, no new
`db/` function.

**Severability check — passed, the step is not blocked.** `backend/app/db/chapter_author_prompts.py`
exists and exposes exactly what step 013 depends on:
`async def get_by_chapter_and_user(chapter_id: int, user_id: int) -> ChapterAuthorPrompt | None`
(harvested, verified by `inspect.signature`). `ChapterAuthorPrompt` carries `id`, `chapter_id`,
`user_id`, `system_prompt: str` (required; `""` is a real stored value), `created_at`, `modified_at`.
014's half is fully delivered, so nothing here needs deferring.

**`backend/app/services/chat_turn.py`**

- `async def compose_turn_system_prompt(context: TurnContext) -> str` — **new**, UNIMPLEMENTED (raises
  `NotImplementedError`). The turn's side of the composer, lifted out of `run_turn` so the composition
  path is callable **as a function**, with no stream, no fake client and no `chat_with_tools`. It loads
  the four layers and returns `prompt_composition.compose_system_prompt(base=…, mode=…, author=…,
  chapter=…)`'s result:
  1. `base` — `prompt_composition.BASE_SYSTEM_PROMPT`;
  2. `mode` — `await assistant_runtime.mode_system_prompt(context.subject.mode_key)`;
  3. `author` — `await book_author_prompts.get_by_book_and_user(context.chat.book_id,
     context.chat.author_id)` → its `.system_prompt`, or `None` when there is no row (unchanged, 021);
  4. `chapter` — **the new layer**: when and only when `context.subject.chapter is not None`,
     `await chapter_author_prompts.get_by_chapter_and_user(context.subject.chapter.id,
     context.chat.author_id)` → its `.system_prompt`, or `None`.

  **Why a `TurnContext` in and a `str` out, and nothing else in the signature:** every input the four
  layers need is already on that record (`chat.book_id`, `chat.author_id`, `subject.mode_key`,
  `subject.chapter`, shipped by step 009), so no identity, id or access argument is threaded — which is
  precisely the point of DoD-2. **No `BookAccess` parameter exists on this function**, deliberately:
  layer 4 reuses layer 3's shape exactly — same identity (the chat's own author), same direct `services
  → db` read, same absence of an access resolution, for the reason `assistant-runtime.md` states (the
  turn is already scoped to that author by `services/chats.py`'s ownership guard, so a second
  resolution would re-derive an identity that cannot differ).

- `async def run_turn(context, prompt) -> AsyncGenerator[TurnFrame, None]` — **signature unchanged**,
  body **deliberately left as shipped**: it still composes base + mode + author inline. Wiring it to the
  new function at skeleton time would have made every existing turn raise, so the inline block carries a
  `Skeleton (015 step 013): … UNIMPLEMENTED` marker instead. **The delegation is part of the frozen
  contract**: the coder moves the `mode_prompt` read and the two composition statements into
  `compose_turn_system_prompt`, adds layer 4 there, and leaves exactly
  `system = await compose_turn_system_prompt(context)` at that site. `mode_key` stays read in `run_turn`
  — step 3's tool gating still needs it, and tool gating is **not** touched by this step.

- `prepare_turn`, `TurnContext`, `TurnFrame`, `build_sampling_options`, `ThinkSplitter`, `MAX_LOOPS` —
  **unchanged**. `TurnContext` gains no field: step 009 already put `subject.chapter` within reach.

- New import: `chapter_author_prompts` added to the existing `from app.db import …` namespace import.
  Unused until the coder fills the body; it is the frozen `services → db` edge and no other module is
  imported by this step.

**`backend/app/services/prompt_composition.py` — untouched, and here is the frozen shape the tests may
rely on** (harvested, not changed):
`def compose_system_prompt(base: str | None = None, mode: str | None = None, author: str | None = None,
chapter: str | None = None) -> str`, rendering each non-blank layer as `### <LABEL>\n<text.strip()>`
joined by a blank line, labels `BASE` / `MODE` / `AUTHOR` / `CHAPTER` in that fixed order, and skipping
any layer that is `None`, empty or whitespace-only. **That skip rule is what DoD-3 rests on — no new
code implements it.**

Caller-compile edits (out of Source-files scope): **None.** The only new symbol is additive and has no
call site yet; no existing signature changed.

#### Red-gate profile

All seven DoD items are `[test]`. The one unimplemented leaf is `compose_turn_system_prompt`, which
raises `NotImplementedError` — it never returns a plausible string, so no assertion over a composed
prompt can pass by accident.

- **Must be red — any test that calls `compose_turn_system_prompt`**: **DoD-1** (the caller's own chapter
  prompt composes as the fourth layer, after base / mode / author, **in that order** — an assertion that
  only checks presence would pass on a wrong order, so bind it to the full composed string), **DoD-2**
  (another member's row for the same chapter is never read, the owner included), **DoD-3** (no row, and a
  row whose prompt is `""`, both contribute nothing — no `### CHAPTER`, no separator, no blank block),
  **DoD-5** (the prompt is read for a chapter in **every** state, `planned` and `closed` included), and
  **DoD-6** (a chapter whose dormant `Chapter.system_prompt` holds text contributes nothing).
- **DoD-4 is a regression clause over today's behaviour** — a turn whose subject is a codex entry, a
  list, book state or nothing composes exactly what it composes today, with no fourth layer. It is
  **red only because the function it must call does not exist yet**; the moment the body lands it is
  green by construction, since the first three layers are moved verbatim. Bind it to
  `compose_turn_system_prompt`, not to the inline block in `run_turn` — a test that drives `run_turn`
  would be green against the stub and would prove nothing.
- **DoD-7 is a pure preservation clause and is green from the start** — `prompt_composition.py` is in no
  source list and was not edited. Its `inspect.signature`, its four parameter names/order/defaults, its
  labels and its skip rule are recorded above; assert against them and the assertion holds before and
  after the coder's diff. Its existing suite (`backend/tests/services/test_prompt_composition.py`) is
  the second net.
- **Regression net for the delegation** the freeze cannot express as a signature: the shipped
  `backend/tests/services/test_chat_turn.py` drives a real `run_turn` against a fake client and asserts
  the composed `system` for the author layer (021 step 004's DoD-4/5/6). If the coder implements the new
  function but forgets to call it from `run_turn`, those stay green — so the orchestrator should read
  "DoD-4 green" as covering the *function*, and treat the `run_turn` delegation as a code-review item.

#### Baseline (recorded before the coder starts)

Compile gate: `cd backend && .venv/Scripts/python -c "import app.main"` → **ok**, plus
`inspect.signature` smoke checks over `chat_turn.compose_turn_system_prompt`,
`prompt_composition.compose_system_prompt`, `chapter_author_prompts.get_by_chapter_and_user`,
`chat_turn.prepare_turn` / `run_turn`, and `dataclasses.fields` over `TurnContext` / `ResolvedSubject`
→ all exactly as recorded above; calling the stub raises `NotImplementedError`.

`cd backend && .venv/Scripts/python -m pytest -q` → **1121 passed, 0 failed** (420s), on the tree
**with this skeleton applied** — identical to the baseline step 010 recorded, so the skeleton costs
nothing and any later failure in the composition path is a real regression. The two `013.codex`
failures step 009 recorded are gone (fixed during steps 009/010), and none of the 015 steps' suites
regressed.

## Tests

### Step 001 — tests (2026-07-30)

- `backend/tests/services/test_chapter_text.py` — covers DoD-1 … DoD-14 — the body DTOs, the two write
  capabilities, and `get_chapter_text` / `save_chapter_text` asserted against the spec (D7, D9, D10, D11).
  Service layer only: `BookAccess` built directly, rows seeded and read back through `db/chapters.py`,
  `db/chapter_changes.py`, `db/chapter_text_revisions.py`; no route, no client, no JWT, no network.
  - DoD-1 — read returns stored body / state / version / string id for owner, co-author and on an
    **archived** book (never archive-gated), `""` reads back as `""`, response field set = the wire contract
  - DoD-2 — a co-author's save into an `open` free-mode chapter lands immediately, version +1 exactly
  - DoD-3 — the `ChapterChange` author is the **saving member**, per save
  - DoD-4 — starts-with → `append` (null bounds, appended remainder); otherwise → `range`
    (`line_from` 1, `line_to` = `len(loaded.splitlines())`, whole new body), incl. trailing-newline count
  - DoD-5 — D9's three degenerate cases (empty loaded → append-whole; cleared → range carrying `""`;
    unchanged → append carrying `""` and still bumps), plus `UpdateChapterTextRequest` accepting `""`
  - DoD-6 — exactly one change (applied, `base_version` = submitted, `applied_by`/`applied_at` stamped)
    and one revision (`applied_change_id`, `text_before` = pre-save body), read back; chain over two saves
  - DoD-7 — stale (behind **and** ahead) refused with the stale reason; body, version, change and
    revision counts unchanged
  - DoD-8 — re-issued merged body against the **current** version lands and becomes the body
  - DoD-9 — `planned` / `closing` / `closed` refused with the not-open reason, nothing written
  - DoD-10 — reader and non-member refused the save by the authorization error; reader still reads on a
    public book
  - DoD-11 — co-author in a `proposal` book refused (reason + message naming FEAT-010), nothing written;
    the owner's save succeeds
  - DoD-12 — owner and co-author saves on an `archived` book refused with the archived reason and write
    nothing; the shared `_require_not_archived` guard (the one the 002 transitions call) refuses/passes;
    the gate precedes the state and version checks
  - DoD-13 — a foreign-book chapter and an unknown id are **not-found** on both entry points, for a
    capability-holding caller
  - DoD-14 — `set_chapter_state` = {owner}, `write_chapter_text` = {owner, co-author} in
    `_CAPABILITY_MATRIX` and through `require`; the 009-frozen rows keep their documented role sets and
    every `Capability` member still has exactly one row
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓, DoD-10 ✓,
  DoD-11 ✓, DoD-12 ✓, DoD-13 ✓, DoD-14 ✓ (no `[manual/live]` items in this step)

### Step 002 — tests (2026-07-30)

- `backend/tests/services/test_chapter_states.py` — covers DoD-1 … DoD-18 — `open_chapter` /
  `close_chapter` / `reopen_chapter` asserted against the spec (D8, D10, "The close seam", CF1).
  Service layer only: `BookAccess` built directly, rows seeded and read back through `db/chapters.py`,
  `db/chapter_changes.py`, `db/chapter_text_revisions.py`, `db/flags.py`; every starting state
  (including `closing`) written straight through `db/chapters.py`, never via a transition. No route,
  no client, no JWT, no network; no property-testing dependency.
  - DoD-1 — the owner opens a `planned` chapter in a book with nothing open → `open`, response +
    stored row, a `planned` bystander untouched
  - DoD-2 — a co-author's open is refused by the authorization error; state unchanged
  - DoD-3 — open refused with the another-chapter-open reason while another chapter is `open`, both
    states kept; plus the guard is **book-scoped** (another book's open chapter does not hold the slot)
  - DoD-4 — open refused the same way while another chapter is **`closing`** (seeded row)
  - DoD-5 — the sequence open A → close A → open B → close B → reopen A, each step asserting the
    transition's own success **first** and then that at most one chapter is `open`
  - DoD-6 — open on `open` / `closing` / `closed` refused with the not-planned reason, nothing changes
  - DoD-7 — close writes **`closed`** directly (never `closing`); `summary` / `summary_status`
    unchanged and no flag, change or revision row written
  - DoD-8 — a co-author's close is refused by the authorization error; the chapter stays `open`
  - DoD-9 — close on `planned` / `closing` / `closed` refused with the not-open reason, nothing changes
  - DoD-10 — after a close no chapter is `open` or `closing`, and a different `planned` chapter then
    opens successfully
  - DoD-11 — the owner reopens a `closed` chapter → `open`, body preserved, bystander untouched
  - DoD-12 — reopen refused with the another-chapter-open reason while a different chapter is `open`;
    that chapter's state and body unaffected
  - DoD-13 — reopen refused the same way while a different chapter is **`closing`** (seeded row)
  - DoD-14 — reopen on `planned` / `open` / `closing` refused with the not-closed reason
  - DoD-15 — all three refused with the archived reason on an `archived` book; no state changes
  - DoD-16 — a reader and a caller with no relationship refused all three by the authorization error
  - DoD-17 — one spec per transition: the success assertion runs **first**, then `text` / `version` /
    `ordinal` / `title` / `sketch` are compared unchanged, `modified_at` is stamped, and both
    `chapter_changes` / `chapter_text_revisions` listings are empty
  - DoD-18 — a foreign-book chapter (in three states) and an unknown id are **not-found** on all three,
    for a capability-holding caller; the foreign row is untouched
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓, DoD-10 ✓,
  DoD-11 ✓, DoD-12 ✓, DoD-13 ✓, DoD-14 ✓, DoD-15 ✓, DoD-16 ✓, DoD-17 ✓, DoD-18 ✓ (no `[manual/live]`
  items in this step)
- US-038.AC-3 is cited nowhere in this file; the only `closing` assertions are DoD-4 / DoD-13 (and the
  `closing` parametrize case of DoD-6 / DoD-9 / DoD-14), all against seeded rows.

### Step 003 — tests (2026-07-30)

Two new route-level spec files, split by concern per `003.context.md` → "Testing". Both drive the real
`app.main.app` through the `http_client` fixture (httpx `ASGITransport`, real lifespan, no network) with
**real auth** — seeded user rows and minted JWTs; the per-file `_now` / `_auth_header` / `_seed_user` /
`_seed_author` / `_create_book` / `_add_co_author` helpers are copied from
`backend/tests/routes/test_book_settings.py`, not imported. The `db` fixture is deliberately not
requested. A chapter's starting state, body and version are written straight through
`app.db.chapters` — the body specs never call `POST …/open` to reach a precondition, and `closing` is
reachable no other way (D8). Book archive state comes from `POST /api/books/{id}/archive`;
collaboration mode from the book create route.

- `backend/tests/routes/test_chapter_text.py` — covers DoD-1 … DoD-7 and the **body half** of DoD-13 …
  DoD-17 — `GET`/`PUT …/chapters/{id}/text` asserted against the step DoD, the status taxonomy, D1, D10
  and D11.
  - DoD-1 — `GET` returns 200 with the stored text, state, version and the chapter id **as a string**
    (`ChapterTextResponse`-validated); a second spec reads the same body on an **archived** book
  - DoD-2 — `PUT` with the current version → 200 with the new body, version +1 exactly, and a following
    `GET` agrees (US-040.AC-1, UC-038)
  - DoD-3 — a re-used (now stale) version → **409**; the following `GET` shows the landed body and its
    version unchanged (US-041.AC-1, UC-039)
  - DoD-4 — co-author saves, owner's stale save is refused, owner re-issues a body carrying **both**
    members' text against the **current** version → 200 and that is what `GET` returns
    (US-041.AC-2, US-040.AC-4)
  - DoD-5 — `PUT` on `planned` / `closing` / `closed` → **409**, body and version unchanged
    (parametrized; US-040.AC-3 + the "no longer editable" half of US-038.AC-1)
  - DoD-6 — a co-author's `PUT` lands 200 in a **free**-mode book; in a **proposal**-mode book it is
    **403** whose refusal detail names **FEAT-010**, nothing is stored, and the **owner**'s save
    still returns 200 (D11). The DoD fixes the status and the presence of FEAT-010 in the reason and
    nothing about the payload's JSON shape, so the reason is read as the flat refusal detail this
    route family puts on the wire and no assertion pins that structure.
  - DoD-7 — `PUT` on an `archived` book → **403**; the read still works and the body is untouched (D10)
  - DoD-13 — logged-in non-member of a **public** book: **200** from `GET`, **403** from `PUT`
  - DoD-14 — stranger to a **private** book: **404** from `GET` and `PUT` (parametrized)
  - DoD-15 — no token: **401** from `GET` and `PUT` (parametrized)
  - DoD-16 — a chapter of **another** book, caller owning **both active** books: **404** from `GET` and
    `PUT`, and the foreign row is untouched
  - DoD-17 — missing `text`, missing `expected_version`, non-numeric version, non-string text → **422**
    and the stored body/version are unchanged (parametrized)
- `backend/tests/routes/test_chapter_states.py` — covers DoD-8 … DoD-12 and the **transition half** of
  DoD-7 and DoD-13 … DoD-17 — `POST …/{open,close,reopen}` asserted against the step DoD, the status
  taxonomy, D8, D10 and "The close seam". Every cross-cutting item is parametrized over the three
  transitions with the chapter seeded in the state that transition **requires**, so a 401/403/404 can
  never be a state-machine 409 in disguise.
  - DoD-8 — the owner opens a `planned` chapter → 200, state `open`, stored row agrees (US-036.AC-1); a
    co-author is **403** and the state is unchanged (US-036.AC-2)
  - DoD-9 — open refused **409** while another chapter is `open` **or** `closing` (parametrized seeded
    holder); both chapters keep their states (US-037.AC-2, US-038.AC-4)
  - DoD-10 — the owner closes the `open` chapter → 200, state **`closed`** (never `closing`)
    (US-038.AC-1); a co-author is **403** and the chapter stays `open` (US-038.AC-2)
  - DoD-11 — the owner reopens a `closed` chapter with nothing else open → 200, state `open`
    (US-039.AC-1); with a different chapter `open` → **409**, and that chapter's state, body and version
    are unaffected (US-039.AC-2)
  - DoD-12 — reopen on `planned` / `open` / `closing` → **409**; close on `planned` / `closing` /
    `closed` → **409** (both parametrized), state unchanged
  - DoD-7 — all three transitions **403** on an `archived` book, state unchanged (D10)
  - DoD-13 — a logged-in non-member of a **public** book: **403** on all three, state unchanged
  - DoD-14 — a stranger to a **private** book: **404** on all three
  - DoD-15 — no token: **401** on all three
  - DoD-16 — a chapter of **another** book, caller owning **both active** books: **404** on all three,
    foreign row untouched
  - DoD-17 — a **bodiless** `POST` on all three is asserted **not 422** (no request body is declared);
    the transition's own outcome is DoD-8/10/11's subject, not this item's
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓, DoD-10 ✓,
  DoD-11 ✓, DoD-12 ✓, DoD-13 ✓, DoD-14 ✓, DoD-15 ✓, DoD-16 ✓, DoD-17 ✓ (no `[manual/live]` items in
  this step)
- Per the skeleton's red-gate profile: DoD-14, DoD-15 and DoD-17's malformed-body half are
  **green by construction** (dependency / framework, before any handler body). DoD-16's foreign-book
  `404` is **not** — it is the service's resolver — and DoD-17's bodiless-transition specs still reach a
  raising handler, which is why they assert "not 422" rather than 200.
- US-038.AC-3 is cited nowhere in either file; every use of `closing` is a directly seeded row.

### Step 004 — tests (2026-07-30)

One new frontend spec beside 014's `tests/user/chaptersApi.test.ts`, following its idiom exactly: the
module under test **is** the api layer, so `../../src/api/client` is whole-module mocked through
`vi.mock` + `importOriginal` — only `request` is replaced, so **`ApiError` stays the real class** for
DoD-5. `globals: false`, so `describe` / `it` / `expect` / `vi` are imported from `"vitest"`; `beforeEach`
re-arms `vi.mocked(request)`. No `fetch`, no network, no page render. Every path and method asserted is
`context.md` → "Endpoints added" verbatim; ids are string snowflakes beyond 2^53 and
`version` / `expected_version` are numbers.

- `frontend/tests/user/chaptersWriteApi.test.ts` — covers DoD-1 … DoD-6 — the five write functions'
  path, method, body, forwarded signal and error propagation, plus the 014 regression guard.
  - DoD-1 — `GET …/text`, `PUT …/text`, `POST …/open`, `POST …/close`, `POST …/reopen`, each with the
    book id and chapter id interpolated into their own segments (a second book/chapter pair proves the
    ids are the ones passed, not remembered). An absent `method` counts as `GET`, per fetch semantics.
  - DoD-2 — each of the five forwards the exact `AbortSignal` instance it was given; omitting it
    forwards none (the trailing-optional-signal convention).
  - DoD-3 — `updateChapterText` sends `{ text, expected_version }` as the request body (`""` text is a
    legitimate save; `expected_version` stays a **number**), and both text functions resolve to the
    server's `ChapterTextResponse` **unmodified** — `chapter_id` / `state` / `text` / `version` /
    `modified_at` all as returned, no unwrap and no reshape.
  - DoD-4 — all three transitions send **no** request body (`opts.body` undefined) and resolve to the
    `ChapterResponse` whose `state` is the server's.
  - DoD-5 — a rejection from the wrapper propagates as the *same* real `ApiError` with its status
    intact: `409` (stale save; open with another chapter open; reopen a non-closed chapter) and `403`
    (archived / proposal-mode; co-author close) are asserted separately so the two the pages branch on
    are distinguishable, plus a `404` propagation on the read.
  - DoD-6 — all eight of 014's exports still present; `listChapters` still resolves to the **whole
    envelope** (`can_reorder` carried, `Array.isArray` false) for both hint values; `listChapters` /
    `getChapter` / `updateChapterSketch` / `reorderChapters` still on their 014 paths and methods —
    the regression guard against a tidy-up pass unwrapping the envelope.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 [manual/live, no test]
- Per the skeleton's red-gate profile: DoD-6 is **green by construction** (a regression guard over
  shipped 014 code, expected to pass at the red gate and to keep passing); DoD-1 … DoD-5 must be red
  with "zero calls recorded" / "expected ApiError, got `not implemented: …`".

### Step 005 — tests (2026-07-30)

One new frontend spec, the step's whole Test-files list. **Nothing is mocked** — the component
imports no `api/` module, so a whole-module mock would prove nothing; DoD-4 is carried by real
`fetch` / `XMLHttpRequest.open` spies placed **after** the mount assertion. `globals: false`, so
`describe` / `it` / `expect` / `vi` / `afterEach` come from `"vitest"`; rendering is
`renderWithProviders` (no `route` — the component touches no router). Queries are by **role or
label only**. The two ProseMirror-only jsdom stubs (`Range.prototype.getClientRects` /
`getBoundingClientRect`, `document.elementFromPoint`) are installed **at the top of this spec's own
file** — `frontend/tests/support/` and `vitest.config.ts` were not touched.

- `frontend/tests/work/ChapterBodyEditor.test.tsx` — covers DoD-2, DoD-3, DoD-4 — the frozen
  four-prop seam asserted against the step DoD only.
  - DoD-2 — the component mounts and an editable region is reachable **by its accessible label**;
    the label is the `ariaLabel` **prop** (a second name reaches it and the first no longer does, so
    nothing is hard-coded); the region carries the initial Markdown's **rendered** content (heading,
    paragraph and list-item text present, the `#` / `-` markers absent); an **empty** initial
    Markdown (`""`, a legitimate body) still mounts the labelled region.
  - DoD-3 — the formatting controls are buttons and **every** button carries a non-empty accessible
    name (`queryAllByRole("button", { name: /\S/ })` equal in length to `getAllByRole("button")`),
    with at least two controls; same for an empty body. **Which** controls exist is asserted
    nowhere — the step says "a small formatting toolbar" and names none, so pinning Bold/Italic/H2
    would assert more than the spec requires.
  - DoD-4 — the leaf contract, written **non-vacuously** per the skeleton's flag: the successful
    mount is asserted **first** (the labelled region exists and contains the body text), and only
    then that `fetch` and `XMLHttpRequest.prototype.open` were never called and `onChange` never
    fired — on mount **and** after `unmount()`.
- Coverage: DoD-1 [manual/live, no test], DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 [manual/live, no test],
  DoD-6 [manual/live, no test], DoD-7 [manual/live, no test], DoD-8 [manual/live, no test]
- Per the skeleton's red-gate profile: all three items must go red as the thrown
  `Error("not implemented: ChapterBodyEditor")` surfacing out of `render(...)`, **not** as a
  "unable to find an element with the label" query miss — a query-miss failure would mean the spec
  never reached the component. Nothing here asserts the emitted Markdown, typing or selection
  (DoD-5 / DoD-6), and no editor internal is faked.

### Step 006 — tests (2026-07-30)

One new frontend spec, the step's whole Test-files list, created beside 014's
`frontend/tests/work/ChapterPage.test.tsx` — **which is not touched**. Two whole-module mocks per
`006.context.md` → Testing: `../../src/api/chapters` enumerating **all ten** frozen exports (014's
eight plus step 004's `getChapterText` / `updateChapterText`), and
`../../src/work/components/chapter/ChapterBodyEditor` (**singular** folder) replaced by a stub over
the frozen four-prop seam — a labelled control whose value is the `initialMarkdown` prop, whose edit
calls `onChange` with a string, and which records the `initialMarkdown` it saw at **each mount** so
DoD-10 observes the generation counter behaviourally rather than by name. ProseMirror is never driven
under jsdom (the feature's recorded testing decision). `ApiError` is the **real** class from
`api/client`, constructed with a plain refusal **message** — the codex family's `detail.message`
object path is deliberately not modelled (step 003 / 004 freeze notes). `globals: false`, so
`describe` / `it` / `expect` / `vi` / `beforeEach` are imported from `"vitest"`; rendering is a local
`renderPage(route)` over `renderWithProviders` with a `<Routes><Route path="/:bookId/chapter/:id" …/></Routes>`
shim so `useParams()` resolves both ids. Queries are by **role or label only**; copy the author reads
is asserted as readable text. The frozen accessible surface asserted is status.md → step 006's:
`Chapter body` (editor), `Save body` (control), `Could not load the chapter body` /
`Could not save the chapter body` (alert titles).

- `frontend/tests/work/ChapterPageBody.test.tsx` — covers DoD-1 … DoD-10 — the third trio, the
  Markdown draft, the explicit save and the read-only branch.
  - DoD-1 — the mount load calls `getChapterText(bookId, chapterId, …)` and the body is shown; then
    **independence in all three directions**, each written presence-first: a failed **body** load shows
    the body's own titled error carrying the message verbatim while the chapter title and the prompt
    field survive; a failed **chapter** load and a failed **prompt** load each leave the body editor
    mounted with the stored body and its save control present.
  - DoD-2 — an `open` chapter mounts the labelled editor seeded with the stored body and offers the
    save control; an **empty** stored body (`""`, a legitimate body) still mounts it.
  - DoD-3 — the save sends `{ text: <draft>, expected_version: <the BODY response's version> }`; the
    chapter response's `version` is deliberately a different number, so a save composed from it fails
    the assertion. Afterwards the surface shows the text the **server returned**, explicitly not the
    local draft (US-040.AC-1).
  - DoD-4 — two sequential saves against an echoing server: the second carries the version the **first
    response** returned, both land, the surface ends on the second server text and no save-error
    surface appears.
  - DoD-5 — written dirty-first: the control **exists and is enabled** once the draft differs, then
    disabled when the draft is restored to the loaded body; disabled while a save is in flight
    (deferred promise); and an **empty** save is enabled and sends `text: ""` (no emptiness rule).
  - DoD-6 — presence-first: the editor is mounted, the keystroke reaches the page (the editor's value
    becomes the typed text), and only then is `updateChapterText` asserted never called.
  - DoD-7 — a `403` carrying the proposal-mode refusal that names **FEAT-010** (D11) and a `403`
    carrying the archived-book refusal (D10): each surfaces the server's message verbatim under the
    frozen save-error title and leaves the author's draft intact.
  - DoD-8 — parametrized over `planned` / `closing` / `closed`, presence-first: the stored body and
    `resolveEditability`'s author-facing `readOnlyReason` are both on screen (the reason is taken from
    `work/subject.ts`, never re-typed as new copy here), and only then no editor is mounted at all
    (zero mounts recorded) and no save control exists — US-038.AC-1's client half.
  - DoD-9 — a `409` surfaces a visible refusal **and** overwrites nothing: the author's text is still
    in the editor and the body was not silently re-fetched (`getChapterText` still called exactly
    once). The divergence view is step 007's and is asserted nowhere.
  - DoD-10 — behavioural: after the load the stub recorded exactly one mount **carrying the loaded
    body**, and a keystroke changes the editor's value **without** adding a mount (D15).
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓,
  DoD-10 ✓, DoD-11 [manual/live, no test]
- Per the skeleton's red-gate profile: `ChapterPage.tsx` is unchanged, so the red arrives as query
  misses and zero recorded calls rather than a `not implemented` throw. The four items flagged as
  vacuously-passable (DoD-5, DoD-6, DoD-8, DoD-1's independence half, DoD-9's "overwrites nothing"
  half) are each structured presence-assertion-first, as recorded above. Nothing here touches
  `bodyEditorGeneration`, `bodyBaseVersion` or any other state field by name; every assertion goes
  through the rendered surface or the mocked api calls.

#### Harness repair (2026-07-30) — Test-files scope widened, **user-authorised**

The verify run returned Fault **SPEC**: DoD-1 makes the page issue a third `api/chapters` call on
mount, and a whole-module `vi.mock` factory must enumerate every export the subject imports — 014's
shipped page spec enumerates only the eight that existed when it was written, so the two exports this
feature added resolved to `undefined` there and every mount in that file rejected inside its mount
effect (assertions all still passed; the runner exited 1 on 27 unhandled rejections, failing DoD-11).

The **user authorised** widening step 006's Test files to include
`frontend/tests/work/ChapterPage.test.tsx` and lifted `006.context.md`'s "do not modify 014's spec"
**for its module-mock factories only**. Applied there, and nowhere else in that file — **no
assertion, no `it`/`describe` title and no expected value was changed**:

- `frontend/tests/work/ChapterPage.test.tsx` — mock factories only — its `api/chapters` factory now
  enumerates all **ten** exports, with `getChapterText` / `updateChapterText` armed in `beforeEach`
  from a local `makeBody()` fixture: an **empty body in a non-`open` state**, chosen because the
  frozen surface mounts the editor and the `Save body` control only for an `open` body — so the
  resolving load adds no control, no editable region and no text to any mount in that file and every
  existing assertion keeps its original meaning.
- Same file — a `vi.mock` over `../../src/work/components/chapter/ChapterBodyEditor` (**singular**
  folder) with the same trivial four-prop stub this step's own spec uses. The verifier flagged this
  as a latent hazard: that file mounted no editor only because the body load never resolved, and a
  resolving load would drive real TipTap under jsdom — the flakiness the feature's recorded testing
  decision exists to avoid.
- `frontend/tests/work/ChapterPageBody.test.tsx` — unchanged; the step's own spec was not at fault.

### Step 007 — tests (2026-07-30)

One new frontend spec, the step's whole Test-files list, created beside step 006's
`frontend/tests/work/ChapterPageBody.test.tsx` — **which is not touched**. The same two whole-module
mocks step 006 used: `../../src/api/chapters` enumerating **all ten** frozen exports, and
`../../src/work/components/chapter/ChapterBodyEditor` (**singular** folder) replaced by the same stub
over the frozen four-prop seam (a labelled control whose value is `initialMarkdown`, whose edit calls
`onChange`, recording the `initialMarkdown` seen at each **mount**). **`restoreBuffer.ts` is NOT
mocked** — it is consumed for real through jsdom's `localStorage`, cleared in `beforeEach` (and by
`tests/setup.ts`'s `afterEach`); DoD-10 drives the **real** eviction policy with oversized sibling
buffers rather than stubbing the module. `ApiError` is the **real** class, constructed with a plain
refusal **message** (a chapter refusal is a plain-string `detail`). `globals: false`; rendering is a
local `renderPage(route)` over `renderWithProviders` with a
`<Routes><Route path="/:bookId/chapter/:id" …/></Routes>` shim. Queries are by **role or label only**.
The frozen accessible surface asserted is status.md → step 007's: `Unsaved changes diverged`,
`This chapter's body changed since your draft`, `Current server version`, `Your draft`,
`Keep the server version`, `Keep my draft`, `Other unsaved drafts were removed` — plus step 006's
`Chapter body` and `Save body`.

- `frontend/tests/work/ChapterPageReconcile.test.tsx` — covers DoD-1 … DoD-11 — the restore buffer,
  both reconciliation entrances, the two-sided resolution and the eviction notice.
  - DoD-1 — presence-first: the editor is mounted and the keystroke lands, then the draft is read back
    from `restoreBufferKey(bookId, "chapter", chapterId)` with the **body response's** version as its
    base (explicitly *not* 014's chapter `version`), and no neighbouring key (another chapter, the
    codex kind) was written — UC-092 / US-107.AC-1.
  - DoD-2 — a buffer seeded **before mount** through a real `writeBuffer`, base version **equal** to
    the served one: the editor shows the **buffered** draft, not the server's body, and the stub
    recorded a mount carrying it (the generation bump observed behaviourally); no divergence view —
    US-107.AC-1 / US-107.AC-2.
  - DoD-3 — presence-first: the edit landed **and** the buffer holds it, then the page is unmounted
    (navigating away), the buffer still holds it, and `updateChapterText` (and `updateChapterSketch`)
    were never called — US-107.AC-4 / US-103.AC-3.
  - DoD-4 — presence-first: a buffer established **through the page**, then a successful save, then the
    key reads back `null`; the page is remounted against the stored body and shows the **server's**
    text with no restore and no divergence view.
  - DoD-5 — the **load-time entrance**: a buffer seeded before mount with a base version the server has
    moved past opens the whole divergence surface directly, showing both sides; only then the
    load-bearing negative — **`updateChapterText` was never called** — plus `getChapterText` called
    exactly once (no second round trip on this entrance).
  - DoD-6 — the **save-time entrance**: a genuine `409` re-fetches (`getChapterText` twice), the
    divergence view shows the server's moved body **against the author's intact draft**, exactly one
    save was attempted, and neither concatenation of the two sides appears — no auto-merge, no silent
    overwrite — UC-039 / US-041.AC-1.
  - DoD-7 — presence-first: after `Keep the server version` the view is **gone** and the editor is back
    holding the **server's** body; only then the buffer reads `null` and `updateChapterText` was never
    called — nothing of the abandoning author's text is written — US-041.AC-3.
  - DoD-8 — after `Keep my draft` the second save carries
    `{ text: <draft>, expected_version: <the SERVER's new version> }` — the ordering that makes the
    re-save non-stale — it succeeds, the view is gone and the chapter shows the reconciled text —
    US-041.AC-2.
  - DoD-9 — the end-to-end gap flow: Ana composes a body carrying **both** members' text, her stale
    save is refused, both sides are shown, she keeps her draft, and the re-issued payload (against the
    current version) and the resulting chapter body both contain Bea's text **and** her own —
    US-040.AC-4.
  - DoD-10 — the **real** eviction policy: sibling chapter buffers are written with increasing
    written-at stamps until the store is at capacity, then one oversized keystroke forces the page's
    own buffer write to evict. Presence-first: the eviction notice is on screen **and names the oldest
    sibling key**; only then the invariant — this chapter's buffer survived holding the draft and is
    never named among the casualties.
  - DoD-11 — presence-first: both named controls exist and are enabled, then the negatives — no editor
    and no `Save body` while the view is open; no `dialog` / `alertdialog` role and the chapter title
    and prompt field still render (inline, not a modal, does not block the page); no radio, no
    checkbox, no merge / both / cancel / discard control (exactly two choices); and neither control is
    marked chosen (`aria-pressed` / `aria-checked`) or holds focus (neither pre-selected).
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓, DoD-10 ✓,
  DoD-11 ✓, DoD-12 [manual/live, no test]
- Per the skeleton's red-gate profile, the red here is **not** a `not implemented` throw for most
  items: step 006's three effects are shipped, so the red arrives as an empty `localStorage`
  (DoD-1/3/4/10), the server's body where the buffered draft was expected (DoD-2), and query misses for
  the divergence and eviction surfaces (DoD-5 … DoD-9, DoD-11). Every one of the seven vacuity-prone
  halves the profile flagged is written presence-assertion-first, as recorded above. Nothing here
  touches `bodyConflict`, `isReconcilingBody`, `evictedBufferKeys`, `bodyBaseVersion` or
  `bodyEditorGeneration` by name; every assertion goes through the rendered surface, the mocked api
  calls, or the real buffer the page wrote.

#### Scope widening — one superseded step-006 case restated (2026-07-30)

The verify run returned FAIL / Fault **SPEC** on DoD-12's `npm test` clause only: one **step 006** case
asserted a contract step 007 replaces. Step 006's DoD-9 required a `409` to leave the stored body on
screen, surface a refusal and **not** re-fetch — and carried the planner's own parenthetical
**"(Step 007 turns this into the divergence view.)"**. Step 007's DoD-6 requires that same `409` to
re-fetch the server's body and open the divergence view, and DoD-11 requires that view to replace the
editor and the `Save body` control. The second body read, the unmounted editor and the suppressed
save-error surface the step-007 contract mandates are exactly the three things the old case forbade;
the two cannot both hold on one code path. **Orchestrator-authorised** on the planner's own wording,
step 007's Test files were widened to include `frontend/tests/work/ChapterPageBody.test.tsx` **solely**
to restate that one case.

- `frontend/tests/work/ChapterPageBody.test.tsx` — **one case restated** — the `409` case now covers
  step 007's **DoD-6** (superseding step 006's **DoD-9**, which is retired by supersession, not
  dropped): a genuine `409` re-fetches (`getChapterText` twice) and opens the frozen divergence surface
  (`Unsaved changes diverged`, `This chapter's body changed since your draft`, `Current server version`,
  `Your draft`, `Keep the server version`, `Keep my draft`) showing the server's moved body against the
  author's draft, with exactly one save attempted and neither concatenation of the two sides present.
  Its `describe`/`it` titles and its file-header bullet name the supersession, so the provenance is
  legible without the plan in hand.
- Nothing else in that file was touched — no other case, title, fixture or expected value, including
  step 006's harness repair to the mock factories. The restated case clears `localStorage` at its start
  **and** its end (the file's `beforeEach` does not), so the buffer the page now writes on a keystroke
  neither is inherited by nor leaks into a neighbouring case.
- `frontend/tests/work/ChapterPageReconcile.test.tsx` — unchanged; step 007's DoD-6 coverage above
  remains its own, and the restated 006 case duplicates rather than replaces it.

### Step 008 — tests (2026-07-30)

One new frontend spec, the step's whole Test-files list, created beside step 006's
`frontend/tests/work/ChapterPageBody.test.tsx` and step 007's
`frontend/tests/work/ChapterPageReconcile.test.tsx` — **neither is touched**. The same two
whole-module mocks, with the api factory now enumerating **all THIRTEEN** frozen exports (014's
eight plus step 004's five — the three transitions are what makes it thirteen), and
`../../src/work/components/chapter/ChapterBodyEditor` (**singular** folder) replaced by the same
four-prop stub. **`restoreBuffer.ts` is NOT mocked** — it is the real module over jsdom's
`localStorage`, which `tests/setup.ts` clears in its global `afterEach`, so DoD-8's buffer is the
one the page actually wrote. `ApiError` is the **real** class, constructed with a plain refusal
**message** (a chapter refusal is a plain-string `detail` — the correction the step-008 freeze
applied to `008.context.md`; no `serverRefusalText` / `details.detail.message` path is modelled).
`globals: false`; rendering is a local `renderPage(route)` over `renderWithProviders` with a
`<Routes><Route path="/:bookId/chapter/:id" …/></Routes>` shim. Queries are by **role or label
only**. The frozen accessible surface asserted is status.md → step 008's
(`Open chapter: {title}` / `Close chapter: {title}` / `Reopen chapter: {title}`,
`Could not change the chapter state`, and the `closing` sentence **verbatim**), plus 014's state
`Badge` word (`Planned` / `Open` / `Closing` / `Closed`, carried as text **and** `aria-label`) and
step 006's `Chapter body` / `Save body`.

- `frontend/tests/work/ChapterPageStateControls.test.tsx` — covers DoD-1 … DoD-9 — the one
  state-gated transition control, its refusal surface, the `closing` reason and the re-seed.
  - DoD-1 — presence-first: a `planned` chapter offers **exactly one** control and it is the open
    one (the other two names reach nothing); using it calls **`openChapterState(bookId, chapterId,
    …)`** and neither sibling; the state on screen then reads `Open` **and** the labelled body
    editor is mounted holding the stored body — US-036.AC-1, UC-035.
  - DoD-2 — presence-first: an `open` chapter's only control is close and the body is editable
    (editor + save control present); after the close the state reads **`Closed`** (never
    `Closing` — D8) and the stored body is still on screen as read-only text, and **only then**
    the two negatives — no editor, no `Save body` — US-038.AC-1.
  - DoD-3 — presence-first: a `closed` chapter's only control is reopen; using it calls
    `reopenChapterState` and the state on screen then reads `Open` — US-039.AC-1, UC-037.
  - DoD-4 — presence-first per the profile's flag: the frozen `closing` sentence is on screen
    **verbatim** and names the close gate as *not built yet*, and only then is **no** transition
    control offered (all three names miss, and none is rendered-and-disabled). Paired with the
    **contrast case** — an `open` chapter does offer its one control and states no such reason —
    so "no control" is evidence about `closing` rather than about the page. `closing` is reached
    by arming the api to answer with it; nothing in this feature produces that state (D8).
  - DoD-5 — two refusals, each presence-first: a co-author's open (`403`) and a close on an
    **archived** book (`403`, D10). Each asserts the server's message on screen under the frozen
    title **first**, then that the state badge still reads its original word and has not moved —
    US-036.AC-2, US-038.AC-2, D14's accepted cost.
  - DoD-6 — a `409` on **open** (another chapter holds the slot) and a `409` on **reopen**: the
    refusal is asserted visible first, then the state is unchanged **and** the body region is
    untouched — the stored body still rendered, still not editable, and **no second
    `getChapterText`** (no re-seed on a refusal) — US-037.AC-2, US-039.AC-2, US-038.AC-4.
  - DoD-7 — the re-seed, written so a locally patched `chapter.state` cannot satisfy it: from a
    `planned` chapter (read-only body, exactly one body read) a successful open produces a
    **second `getChapterText`** carrying the same ids, the state reads `Open`, the body region's
    **editability** has followed (the labelled editor is now mounted and its save control present,
    where the read-only branch had neither), and the offered control has itself followed to close
    — all with no navigation and no manual reload. The chapter's stored body text is held
    **constant** across both reads (a transition writes `state` / `modified_at` only and never
    `Chapter.text` — step 002's contract), and the only claim about the draft is that a success
    leaves it **unchanged**, consistent with DoD-8 and `008.context.md` → "Re-seeding after a
    transition".
  - DoD-8 — the profile's worst vacuity hazard, written in three presence stages: a real draft is
    established **through the page** (the editor's value becomes the typed text), the **real**
    restore buffer is read back holding it, the close is then **refused** and the refusal is
    asserted on screen — and only then that the draft is still the author's text and the buffer
    entry still exists holding it, with nothing saved.
  - DoD-9 — parametrized over `planned` / `open` / `closed`: each control is reachable by role and
    label, its accessible name carries **both** the action word and the chapter title, and the
    visible label is widened by the name rather than replaced. Plus a non-fixed-string case — a
    second chapter's control is named for **that** chapter and the first name no longer reaches
    anything.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓,
  DoD-10 [manual/live, no test]
- Per the skeleton's red-gate profile: `ChapterPage.tsx` is unchanged, so the red arrives as query
  misses on the three control names, on `Could not change the chapter state` and on the `closing`
  sentence, and as **zero recorded calls** on the three api transitions — not as a
  `not implemented` throw (no spec here drives an effect or reads a computed directly). Every one
  of the six vacuity-prone items the profile flagged (DoD-8 worst, then DoD-4, DoD-5, DoD-6,
  DoD-2, DoD-1) is written presence-assertion-first, as recorded above. Nothing here touches
  `transitionStatus`, `transitionError`, `offeredTransition` or `transitionUnavailableReason` by
  name; every assertion goes through the rendered surface, the mocked api calls or the real buffer
  the page wrote.

### Step 009 — tests (2026-07-30)

One new backend service spec, plus **one authorised one-assertion widening** of a delivered `013.codex`
route spec (justified below). **No LLM server is contacted and no live turn is run** — `chat_with_tools`
is called nowhere in the new file; subject resolution, `determine_mode`, `allowed_tool_names`, the
tool-context construction and the frame type are exercised **directly, as functions**. Chapters in every
state (`closing` included — reachable no other way, D8) are written straight through `db/chapters.py`
against the `db` fixture; `BookAccess` is constructed directly; no route, no client, no JWT, no network.
Test names carry the DoD id alone — this half of the feature cites no product id.

- `backend/tests/services/test_chapter_turn_context.py` — covers DoD-1 … DoD-12 — the `op` frame field,
  the selection on the wire, and the **new** chapter branch of `determine_mode`, asserted against the
  step DoD, D5, D17 and "Mode seeding".
  - DoD-1 — a frame built with the pre-015 four-field shape carries `op == "replace"` (and serializes
    it); `append` / `replace_selection` / `replace` are each carried back verbatim; `CanvasOp` is
    exactly those three and a fourth operation is rejected
  - DoD-2 — the untouched codex emission compared **field by field** (one `canvas` frame, same
    `subject_kind` / `subject_id` / `field` / `text`) plus `op == "replace"`, for a `body` and a `name`
    write; a second spec pins the refusal behaviour unchanged — an archived entry refused with a
    non-empty string and **no** frame, and a co-author's proposal-mode refusal still naming **FEAT-010**.
    Codex logic is not re-tested beyond that
  - DoD-3 — `CanvasField` still admits exactly `"name"` / `"body"`; `field="text"` is rejected
  - DoD-4 — a request with **no** selection is valid and prepares a context carrying `None`; a
    selection-bearing `TurnRequest` reaches `prepare_turn`'s `TurnContext`, and that text is what the
    per-turn `ToolContext` exposes (default `None`). The `run_turn` → `ToolContext` leg is **not** driven
    here — a live turn is forbidden by the step's testing rule; the tool-side read is step 010's
  - DoD-5 — a selection-bearing turn (the request asserted to hold the text **first**) leaves no chapter
    change and no revision, leaves the chapter's `text` / `version` / `state` untouched, and no stored
    chat message holds the selection
  - DoD-6 — an `open` chapter resolves onto the subject (the row's id asserted) and maps to
    **`write-chapter`**, both through `resolve_subject` and through `determine_mode` on a hand-built
    subject
  - DoD-7 — the same for a directly seeded `closing` chapter → **`close-chapter`**
  - DoD-8 — parametrized `planned` / `closed`: the row **is** resolved (so this is "no mode", not "no
    chapter"), the mode is `None`, and `allowed_tool_names` returns **exactly `("web_search",)`** —
    equal to `BASE_TOOL_NAMES`, not `()`, and not the (multi-entry) registry
  - DoD-9 — **two books**: a `subject_id` naming a chapter in another book resolves to no subject at all
    (`chapter` / `kind` / `entry` / `mode_key` all null, no mode), while the very same row resolves
    normally from its own book — so the refusal is provably the cross-book rule, not a missing row
  - DoD-10 — parametrized regression: a codex entry of each kind still resolves its `edit-*` mode
    through `resolve_subject` **and** through `determine_mode` on a hand-built subject; the chapter
    member stays null for a codex subject
  - DoD-11 — `TurnRequest.model_validate({})` still complete with the new field absent; a subject-less
    resolution yields no subject / no chapter / no mode; `NO_SUBJECT` unchanged; a null mode still yields
    `BASE_TOOL_NAMES`; `prepare_turn` with no request carries no subject and no selection
  - DoD-12 — a **seeding assertion, not seeding work**: zero mode rows before, then the shipped
    instance-setup path (`services/setup.py::create_database`) leaves rows keyed **`write-chapter`** and
    **`close-chapter`**. Nothing here calls `seed_default_modes()`. A second, declarative spec pins that
    those two keys are exactly the values `_CHAPTER_STATE_MODES` maps (`open` / `closing`, with
    `planned` / `closed` absent), so the seeding assertion guards the keys actually returned
- `backend/tests/routes/test_chat_turn_canvas.py` — **WIDENED, one assertion only** — covers DoD-2
  - `test_canvas_frame_reaches_the_stream_between_deltas__DoD2` (a delivered `013.codex` spec) asserted
    the serialized canvas payload's **exact** key set `{subject_kind, subject_id, field, text}`. D17 adds
    `op` **with a default**, so behaviour is unchanged but that exact-key assertion breaks permanently.
    Step 009's own **DoD-2** — *"a frame identical to today's **apart from the defaulted operation
    field**"* — and `009.context.md`'s naming of the codex emission as a **regression surface** supersede
    the older wording. The expected key set now includes `"op"` and `payload["op"] == "replace"` is
    asserted, which turns the collision into a **stronger** regression assertion. **Nothing else in that
    file was touched** — no other assertion, title, fixture or expected value; no other case in it
    breaks.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓, DoD-10 ✓,
  DoD-11 ✓, DoD-12 ✓ (no `[manual/live]` items in this step)
- Per the skeleton's red-gate profile: **DoD-1, 2, 3, 5, 11, 12** are green by construction (declarative
  fields, an untouched codex path, and pre-existing seeding) and were **not** contorted into a red;
  **DoD-6, 7, 8, 9** drive `_chapter_within_book` / `_mode_for_chapter_state` and are expected red as
  `NotImplementedError`; **DoD-4** is red on the *transfer* (`prepare_turn` leaves `selection_text`
  `None`), not on the dataclass field. DoD-10's assertions must **stay** green — they are the regression
  guard over the restructured `determine_mode`.
- US-038.AC-3 is cited nowhere; every use of `closing` is a directly seeded row.

### Step 010 — tests (2026-07-30)

One new backend service spec, plus **one authorised one-assertion widening** of a delivered `011.chat-panel`
service spec (justified below). **No LLM server is contacted and no live turn is run** — the `ToolContext`
is built directly and the four tools are invoked **as functions**, with an in-memory recording sink standing
in for the turn's queue (the `emit_frame` slot takes a callable), which is what keeps DoD-3's "exactly one
frame" precise. Chapters in every state (`closing` included — reachable no other way, D8) are written
straight through `db/chapters.py` against the `db` fixture; `BookAccess` is constructed directly, so D10's
archived book and D11's proposal-mode co-author are expressed on the context rather than over HTTP. No
route, no client, no JWT, no network. Test names carry the DoD id alone — this half of the feature cites no
product id.

- `backend/tests/services/test_chapter_tools.py` — covers DoD-1 … DoD-12 — the four chapter tools, the
  refusal mirror's four rules, the no-database structural property and the shipped-unreachable state.
  - DoD-1 — the four names are present, no name repeats anywhere in the registry, and the four are
    **disjoint** from the pre-015 four (`web_search` / `codex_search` / `codex_read_entry` /
    `write_codex_draft`, all still present); parametrized per tool: **exactly one** of `callable` /
    `binder` is set (an XOR, not "which one"), and `args_schema` is a `BaseModel` subclass — the one that
    tool declares
  - DoD-2 — parametrized over `planned` / `open` / `closing` / `closed`: the read tool's answer contains
    the body **read back from `db/chapters.py`**, so it is the *saved* body and not a fixture echo. A
    second spec asserts the read is **not** subject to the write refusals — it still returns the body on
    an archived book and for a co-author in a proposal-mode book (Interface intent)
  - DoD-3 — parametrized per write tool: exactly one frame, event `canvas`, a `CanvasFrame` carrying
    `subject_kind="chapter"`, `subject_id == str(chapter.id)`, `field == "body"` (D17 — `CanvasField` was
    not widened), the text it was given, and its own op — `replace` / `replace_selection` / `append`; a
    second call with different text proves the payload reports what it was given. A companion spec runs
    all three over one chapter and pins that the three ops are three distinct values
  - DoD-4 — **the load-bearing one.** Parametrized per write tool, and again across a sequence of all
    three: the write's **own success is asserted first** (one frame carrying the text and op, plus a
    non-empty confirmation string), and only then the chapter is read back through `db/chapters.py`
    (`text`, `version`, `modified_at`, `state` all unchanged) and `db/chapter_changes.py` /
    `db/chapter_text_revisions.py` are listed and asserted **empty**
  - DoD-5 — parametrized per write tool over seven non-chapter subjects (`None`, `NO_SUBJECT`, a codex
    entry, `book-state`, `chapters`, `chats`, and a `chapter`-kind subject that resolved to **no row**):
    a non-empty **string** back and **zero** frames each time, with a resolved open chapter writing in the
    same spec so the refusal is provably the missing subject
  - DoD-6 — parametrized per write tool × `planned` / `closing` / `closed`: a refusal string that
    **names the state** (`state.value in result.lower()`), no frame; an `open` sibling in the same book
    writes, so the refusal is the state rule
  - DoD-7 — parametrized per write tool: `access.book_state = archived` refuses with a string and no
    frame (D10 in the assistant's vocabulary), while the identical call on an active book writes
  - DoD-8 — parametrized per write tool: a **co-author** in a `proposal`-mode book is refused with a
    string naming **FEAT-010**, no frame; the **owner** of the same book emits its one frame and gets a
    confirmation with no FEAT-010 in it; and the same co-author in a free-mode book writes, so the rule is
    the collaboration mode and not the role alone (D11)
  - DoD-9 — the foreign chapter is resolved through the **real** `resolve_subject`, which yields no
    chapter; the read tool over that subject returns a string containing none of the other book's body,
    while the very same row resolves and reads normally from **its own** book — refused by resolution, not
    by a check inside the tool
  - DoD-10 — `build_tool_bindings(resolve_tools(<the four>), None)` raises nothing and builds none of the
    four (definitions and callables both, key sets equal); with a context all four **are** built, each
    binding's free parameters equal to its schema's fields
  - DoD-11 — all four tools × thirteen contexts (every refusal rule one at a time, plus no access
    context, no emitter, a **failing** emitter standing in for a closed queue, and an absent selection):
    every call returns a non-empty string. Deliberately **not** wrapped in `try/except` — an exception
    fails the test, which is the point
  - DoD-12 — the fresh-install path (`services/setup.py::create_database`, which seeds the modes and no
    selections), `db/mode_tools.list_by_mode("write-chapter")` asserted **empty**, the book's `open`
    chapter resolved and `determine_mode` giving `write-chapter`; `allowed_tool_names` then returns `()`
    (an empty allowlist, not the registry), `resolve_tools` gives nothing, and the four are asserted to be
    in the registry all the same — so the absence is the gating, not a missing registration
- `backend/tests/services/test_tools.py` — **WIDENED, one assertion only** — covers DoD-1
  - `test_registry_has_single_web_search_entry__DoD3` (a delivered `011.chat-panel` spec, already amended
    twice by `013.codex`) pins `TOOL_REGISTRY`'s **exact name set**. Step 010's **DoD-1** requires the four
    chapter tools to be in that registry with names colliding with no existing entry, so the pinned set is
    superseded by this step's own contract; the expected set now carries `read_chapter_text` /
    `set_chapter_text` / `update_selection` / `add_text` beside the four it already had. The test's intent —
    the catalogue is pinned, not open-ended — is unchanged and is now stronger. **Nothing else in that file
    was touched**, and no other case in it breaks (`build_tool_bindings(TOOL_REGISTRY)` with no context
    still yields exactly one definition, the four new entries being bound and therefore skipped).
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓, DoD-10 ✓,
  DoD-11 ✓, DoD-12 ✓, DoD-13 [manual/live, no test]
- Per the skeleton's red-gate profile: **DoD-1 and DoD-12** are green by construction (declarative
  `ToolDef` entries / schemas / descriptions, and an empty allowlist is pre-existing behaviour) and were
  **not** contorted into a red. Everything else drives a raising stub — `_resolved_chapter` /
  `_refuse_write`, the four callables or the four binders — so the expected red is `NotImplementedError`,
  never a plausible refusal string. DoD-4 and DoD-11 are the two that could invert against a stub, and are
  written accordingly: DoD-4 asserts the write's own success **before** reading the three tables back, and
  DoD-11 carries no `try/except` anywhere.
- One clause is **asserted only in part**: DoD-10's *"skipped **and logged**"*. The skip is asserted; the
  log is not, because `build_tool_bindings` is shipped `013` code that no `015` role owns and any
  assertion on its logger name/level/message would couple the spec to an implementation detail — and a
  wording mismatch there would raise a CODE fault against a file the coder is not touching.

### Step 011 — tests (2026-07-30)

Four frontend spec files — the step's three plus one **authorised widening**. All are **module tests,
not component tests**: no `renderWithProviders`, no api mocks, no rendering anywhere. `globals: false`,
so every primitive is imported from `"vitest"`. Bound to the `## Skeleton` → "Step 011" freeze
(`CanvasOp` + `CanvasFrame.op?`, the `"chapter-text"` `EditableRegion` member, the widened
`CanvasDraftApplier`, the three selection-registry functions, the marked `dispatchCanvasFrame` /
`unregisterContentSubject` diffs, and `chapterUndo.ts`'s four functions).

- `frontend/tests/work/subject.test.ts` — **EXTENDED** (014's file; nothing restructured or renamed) —
  covers DoD-1, DoD-2, DoD-3 — the `open` chapter's region verdict and the unchanged write path
  - DoD-1 — the `open` verdict keeps `editable: "whole"` / `readOnlyReason: null` and now names
    `"chapter-text"` and `"chapter-own-prompt"`; `planned` keeps its two regions **and its reason string
    verbatim**; `closing` / `closed` keep `editable: "none"`, their own distinct author-facing reasons and
    no region
  - DoD-2 — **vacuity-proofed as the freeze requires**: the `open` verdict's enumeration is pinned
    exactly (`arrayContaining` + `toHaveLength(2)`) **before** the sketch is denied, so an absent
    `editableRegions` cannot pass; plus the sketch region belongs to `planned` and to `planned` alone
    (UC-033's window is the exact opposite of the body's)
  - DoD-3 — `checkWritePermission(open, "whole")` allows the body write; `planned` / `closing` /
    `closed` refuse it with a stated reason. `"whole"` **is** the body write region — no `"chapter-text"`
    write region is asserted anywhere
  - **One superseded 014 assertion updated in place**: the case titled *"DoD-12: `open` keeps the answer
    it gives today — editable whole, no reason, no region list"* asserted
    `expect(result.editableRegions).toBeUndefined()`. 015's DoD-1/2 require the `open` verdict to
    enumerate `editableRegions` **beside** `editable: "whole"` (the skeleton's own "the `open` chapter's
    verdict now enumerates regions" note), relaxing 014's "absent for every other verdict" invariant. The
    assertion is now `toHaveLength(2)`; the case's first two assertions (`"whole"`, `null`) are untouched,
    as is every other 014 case, and an in-file comment records the supersession
- `frontend/tests/work/contentSubjectChapter.test.ts` — **NEW** — covers DoD-4, DoD-5, DoD-6, DoD-7,
  DoD-8, DoD-9, DoD-12 — the generalized dispatcher, the selection registry and the frame DTO. Uses the
  **real** `restoreBuffer.ts` (jsdom `localStorage`, cleared by `tests/setup.ts`), so DoD-7 / DoD-8
  assert against **real buffer state**, never a mock's call log. The module-level registry is reset
  through the frozen API alone, in `try/catch` so harness hygiene can never turn a case red
  - DoD-4 — a matching chapter target's applier receives `(field, text, op)` for each of the three
    operations, and the delivered frame is buffered nowhere
  - DoD-5 — another chapter's id, a codex frame against a chapter target, and an unregistered previous
    target all receive nothing
  - DoD-6 — a codex frame still reaches its matching target (with the operation resolved to `"replace"`)
    and is still buffered under the `"codex-entry"` key when there is none; a **two-parameter**
    `CanvasDraftApplier` is declared, registered and dispatched to — the type half is gated by
    `npm run test:types`, which is exactly why `CodexEntryPage` needs no edit (D17)
  - DoD-7 — a targetless `replace` chapter frame lands under `restoreBufferKey(bookId, "chapter", id)`
    (and only that key), inheriting a base version already at that key and `""` when there is none; an
    **omitted** operation is buffered the same way; a list registration counts as no target
  - DoD-8 — a targetless `append` / `replace_selection` frame writes to **no** buffer key at all
    (asserted over every `RESTORE_BUFFER_KEY_PREFIX` key, so a codex-key write cannot slip through) and
    leaves a pre-existing buffered draft byte-identical; the same frame **is** delivered when a target
    is registered, so the drop is the targetless case only
  - DoD-9 — the registration discipline verbatim: the current owner's selection is returned, a later set
    replaces it, `null` clears it, the **newest setter wins outright**, a clear from a **superseded**
    owner is a no-op while the real owner's clear lands, `unregisterContentSubject` clears the selection
    too (asserting the selection was really held first), a late unregister from a superseded page does
    not, and `""` is stored as given
  - DoD-12 — **type-level**, as prescribed: frame literals for each of the three operations plus one
    with the operation **omitted**, `CanvasOp` / `CanvasField` arrays, and two `@ts-expect-error`
    negatives (a fourth operation; a `"text"` field member — D17), all gated by `npm run test:types`. No
    runtime value is imported from a declaration file. The replace **default** is asserted behaviourally:
    a frame with no operation reaches the applier as `"replace"`
- `frontend/tests/work/chapterUndo.test.ts` — **NEW** — covers DoD-10, DoD-11 — pure module tests
  - DoD-10 — a push is held and reported by the depth; pops return **most-recent-first** and remove what
    they return; an empty stack pops `null` and reports depth `0` without throwing; `""` is a legitimate
    snapshot and pops back as `""` (not `null`); exactly 20 pushes are all kept; the 21st…25th drop the
    **oldest**, leaving the 20 most recent in order
  - DoD-11 — **vacuity-proofed as the freeze requires**: two chapters in one book, and the same chapter
    id in two books, each **prove they hold what they were given first** and only then that neither sees
    the other's; draining one pair leaves the other intact; `clearChapterUndo` drops one pair and leaves
    the rest untouched (a never-pushed pair is a no-op). The `localStorage` case pushes, asserts the
    **depth is non-zero**, and only then asserts the key set is unchanged and no stored value contains
    the snapshot — then pops both snapshots back **from memory** (D6)
  - The cap `20` is a **local constant taken from the step file**, not imported: the skeleton keeps
    `MAX_SNAPSHOTS` module-private precisely so a spec asserts the behaviour, not the constant
- `frontend/tests/work/contentSubject.test.ts` — **WIDENED, three assertions only** — covers DoD-6
  (the codex-path regression half)
  - Three delivered `013` assertions read `expect(applyDraft).toHaveBeenCalledWith("body" | "name",
    <text>)` — an **exact two-argument** match. The frozen dispatcher always passes a third argument
    (`frame.op ?? "replace"`), so each expected argument list gains `"replace"`. **This is the design,
    not a regression**: **D17** widens the applier's *type* by one **optional** parameter precisely so a
    two-parameter implementation stays valid, and step 011's **DoD-6** requires exactly that ("an applier
    taking only two parameters still satisfies the registry") — the pinned two-argument **call shape** is
    superseded by DoD-4 ("its text, its field and its operation"). The cases' intent — the frame's field
    and text reach the applier — is unchanged. **Nothing else in that file was touched**, and no other
    case in it breaks (the buffer-fallback, non-matching-subject and register/unregister cases never
    inspect the applier's arity)
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓, DoD-10 ✓,
  DoD-11 ✓, DoD-12 ✓, DoD-13 [manual/live, no test]
- Per the skeleton's red-gate profile: **DoD-3, DoD-5, DoD-12 and the type half of DoD-6** are green by
  construction (a byte-untouched `checkWritePermission`, shipped `013` match behaviour, and declarative
  `.d.ts` / type-assignability claims) and were **not** contorted into a red — they are regression
  guards. Everything else drives either the missing `editableRegions` field (DoD-1/2: expect *received
  `undefined`*, not a throw) or a raising stub (`setContentSelection` / `currentContentSelection` /
  `clearContentSelection` and all four `chapterUndo` functions), or the not-yet-generalized dispatcher
  (DoD-4: a recorded two-argument call; DoD-7: the chapter key reading back `null`; DoD-8: a buffer
  written under the codex key).
- No test asserts an internal call, a private field, a log line, or the module-private `MAX_SNAPSHOTS`;
  no source file was read by this role.

### Step 012 — tests (2026-07-30)

- `frontend/tests/work/ChapterPageCanvas.test.tsx` — **new file** — covers DoD-1 … DoD-10 — the chapter
  page as a **writable** canvas target: registration with an apply-draft callback, the three operations,
  the pre-write undo snapshot, the draft-edit path, remount-on-external-write, the refused
  selection-less frame, the undo control and the 20-deep stack, the selection registry, the flat
  `selection_text` on the turn request, and the save that carries only the text and the version.
  Nothing else under `frontend/tests/` was touched.
  - DoD-1 — mount registers `{kind: "chapter", entityId}` **and** a frame delivered through the REAL
    `dispatchCanvasFrame` reaches the draft (the writable half); unmount clears the registration; each of
    `planned` / `closing` / `closed` registers the subject (asserted first) yet the assistant's text
    never lands in the body
  - DoD-2 — `replace` sets the whole draft; `append` keeps the existing text first and ends with the
    frame's; `replace_selection` yields exactly `STORED_BODY.replace(selection, text)`
  - DoD-3 — one case per operation: undo restores **exactly** the pre-frame text (the order's observable
    consequence — applying first would make it a no-op); a case where the pre-write draft is the
    author's own unsaved typing; a two-write case undoing most-recent-first
  - DoD-4 — presence first (the draft moved **and** the buffer holds it at
    `restoreBufferKey(book, "chapter", chapter)` with `baseVersion === ` the body response's version),
    then `updateChapterText` never called; plus a keystroke-equivalence case comparing the two records
  - DoD-5 — observed through the stub's **mount log** only: an applied frame remounts on the NEW text,
    an undo remounts on the restored text, a keystroke does not remount
  - DoD-6 — the frozen alert `The assistant's write was not applied` and the refused text appear FIRST,
    then the draft is byte-identical and the text is at neither end (`startsWith` / `endsWith` both
    false — never appended, never at position zero); a second case where the author cleared the
    selection (`""`) while the model wrote; a third asserting no remount and undo depth `0`
  - DoD-7 — presence first: the control exists and is **enabled** after one assistant write, then
    **present and disabled** once the stack empties and before any write; the 20-deep half is driven
    through the module (21 pushes → depth 20, 20 pops newest-first, the oldest never returned, then
    `null`)
  - DoD-8 — the registry follows the editor's `onSelectionChange`, an emptied selection registers as
    `null`, and unmounting the page clears it
  - DoD-9 — the turn's request body is captured at the `api/sse.streamPost` seam with the REAL
    `api/chats` above it (no stream opened, `support/sseFixture.ts` unused): `selection_text` is a
    **top-level** key beside `subject_kind` / `subject_id`, no `subject` key exists and **no field is an
    object**; nothing selected → the key is absent; the pane holds no copy (a second send and a retry
    each carry the selection as it is at that moment); nothing in view → `{ prompt }` exactly; plus a
    declarative `TurnRequest` literal pair gated by `npm run test:types`
  - DoD-10 — presence first (`currentContentSelection()` returns the selection and a frame was applied),
    then no write call; and a save whose payload is `toEqual({ text, expected_version })` exactly
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓, DoD-10 ✓,
  DoD-11 [manual/live, no test], DoD-12 [manual/live, no test]
- Mocks per the freeze: whole-module `api/chapters` (all ten exports) and
  `work/components/chapter/ChapterBodyEditor` (**singular** folder) — the stub drives **both**
  `onChange` and `onSelectionChange` (a second labelled control, `Chapter body selection`) and logs its
  `initialMarkdown` at every mount. `contentSubject.ts`, `chapterUndo.ts` and `restoreBuffer.ts` are
  **real**; `api/sse.streamPost` and `api/client`'s `request` / `refreshAuthToken` are stubbed so no
  network is reached, and `ApiError` stays real. `localStorage` and the undo stacks are cleared around
  every case.
- Every vacuous-pass trap named in the red-gate profile (DoD-1's second half, DoD-4, DoD-6, DoD-7's
  first half, DoD-10) is written **presence-first**. No test reads `bodyEditorGeneration`,
  `selectedText` or `unappliedSelectionWrite` by name, asserts an internal call, or inspects DOM shape;
  queries are by role or label only, bound to the frozen accessible names. No source file was read by
  this role.

### Step 013 — tests (2026-07-30)

One new backend service spec. **No LLM server is contacted**: the composition path is exercised **as a
function** through the frozen `chat_turn.compose_turn_system_prompt(context)` and every assertion is
over the composed string — `chat_with_tools` is called nowhere and `run_turn` is never driven (the
skeleton's red-gate profile: a spec driving `run_turn` would be green against the stub and prove
nothing). Chapters in every state (`closing` and `planned` included — reachable no other way, D8),
prompt rows, mode rows and chats are seeded straight through the sibling `db/` modules against the `db`
fixture; `TurnContext` / `ResolvedSubject` are built by hand; no route, no client, no JWT, no network,
and **no `BookAccess` is constructed anywhere** — this step's function takes none, which is DoD-2's
point. Test names carry the DoD id alone: this step cites no product id.

- `backend/tests/services/test_chapter_prompt_composition.py` — covers DoD-1 … DoD-7 — the caller's own
  chapter prompt as composition layer 4, asserted against the step DoD, `013.context.md` ("Whose
  prompt, and why no `BookAccess`") and `context.md` → D12.
  - DoD-1 — with all four layers populated the composed prompt equals the **whole expected string**
    (base → mode → author → chapter, each `### <LABEL>\n<text.strip()>`, joined by a blank line), plus a
    second spec pinning strict `### BASE` < `### MODE` < `### AUTHOR` < `### CHAPTER` ordering and the
    chapter text appearing exactly once under its heading — presence alone would pass on a wrong order
  - DoD-2 — **two members, different rows on the same chapter**, both directions: a co-author's chat
    composes the co-author's text and never the owner's; the **owner's** chat composes the owner's and
    never the co-author's; and a chapter on which only another member holds a row composes **no** chapter
    layer at all (the other's row is not a fallback)
  - DoD-3 — a chapter with **no** row composes the surviving layers only, with no `### CHAPTER` and no
    trailing separator; a row whose prompt is `""` is **byte-for-byte identical** to having no row (two
    chapters, same context); and with the chapter layer the only candidate an empty row yields exactly
    the base section — no separator, no blank block
  - DoD-4 — regression clause, parametrized over **codex entry / chapters list / book state / explicit
    `NO_SUBJECT` / the record's default subject**: each composes exactly base (+ mode where the subject
    carries one) + author, with no `### CHAPTER` — **while the caller holds a chapter prompt row in the
    same book**, so the absence is provably the not-a-chapter rule
  - DoD-5 — parametrized `planned` / `open` / `closing` / `closed`, each seeded directly through
    `db/chapters.py`: all four compose the caller's chapter prompt (exact string), so the state machine
    does not gate it
  - DoD-6 — a chapter whose **dormant `Chapter.system_prompt`** holds text and whose
    `ChapterAuthorPrompt` row is **absent** composes neither (base section only, no `### CHAPTER`, no
    trace of the column text); a second spec adds the row and shows the row is composed while the column
    still contributes nothing — superseded, not a fallback
  - DoD-7 — preservation of `services/prompt_composition.py`: `inspect.signature` reports exactly
    `[base, mode, author, chapter]`, all defaulting to `None`, no `*args` / `**kwargs`; the four labels,
    their fixed order and the `### <LABEL>\n<text.strip()>` + blank-line-join rendering are asserted
    literally; the skip rule DoD-3 rests on (absent / empty / whitespace-only → nothing) is asserted;
    and `BASE_SYSTEM_PROMPT` is still a non-empty `str`
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓ (all seven are `[test]`)
- Per the skeleton's red-gate profile, DoD-7 is **green by construction** (a preservation clause over a
  file in no source list) and DoD-4 is red only until the function has a body; DoD-1, 2, 3, 5 and 6 each
  bind the new fourth-layer path. No test asserts an internal call, a private helper or any structure
  the spec does not promise. No source file was read by this role.

## Notes & Issues

- Step 001: `_require_not_archived` and `_require_writable_mode` run **before** `_resolve_chapter`, per
  the fixed guard order, so on an archived book an unknown/foreign chapter id answers `book_archived`
  (403) rather than `not_found` (404). Intended by `context.md`'s ordering; noted because step 003's
  route status map inherits it.
- Step 001: the two 015 refusal messages are the service's own strings (`services/codex.py` copied in
  shape only). The proposal-mode message names FEAT-010 as unbuilt, matching D11's requirement that the
  client surfaces the text verbatim.
- Step 001: the `## Tests` section of this file was read incidentally while reading `status.md` for the
  `## Skeleton` record — its DoD-tagged inventory only, no test source. Implementation was written from
  the step file and `context.md`.
- Step 002: the guard order (`require` → archived → resolve) means the archived refusal precedes
  not-found on all three transitions too — the same inheritance step 001 noted, now on the transition
  handlers step 003 maps.
- Step 002: `_require_open_slot_free` raises one shared message for both call sites ("Another chapter of
  this book is already open…"), since the reason, not the wording, is what the route maps and the client
  branches on.
- Step 003: verified programmatically rather than assumed — `router.routes` reports 11 routes with
  `PUT …/chapters/order` still at index 2 and the five new ones at 6–10 in the frozen order;
  `_CHAPTER_ERROR_STATUS` is set-equal to the 9-member `ChapterErrorReason`; the mounted OpenAPI binds
  `200` to `ChapterTextResponse` (×2) / `ChapterResponse` (×3) and declares a request body on
  `PUT …/text` **only**, so the three transitions accept a bodiless `POST`.
- Step 003: `_map_chapter_error` passes `err.message` through as a **plain-string** `detail` (014's
  shape, unchanged here). D11 / DoD-6 asks the client to surface the FEAT-010 refusal text; on the wire
  that text is `detail` (a string), not `detail.message` — `003.context.md` and `context.md` describe the
  frontend reading `details.detail.message`, which is the *codex* route family's object-detail shape.
  Nothing in this HTTP-only step may change it (the mapper is frozen 014 code); flagged so step 004/006
  parse the chapter refusal as a string rather than copying `serverRefusalText`'s object path verbatim.
- Step 003: the `## Tests` section of this file was read incidentally while reading `status.md` for the
  `## Skeleton` record — its DoD-tagged inventory only, no test source. Implementation was written from
  the step file, `003.context.md` and `context.md`.
- Step 005: the toolbar is deliberately the **four** controls the freeze named as verified — `Bold`,
  `Italic`, `H2`, `BulletList`, in two `ControlsGroup`s. Each carries `@mantine/tiptap`'s own default
  `aria-label` ("Bold", "Italic", "Heading 2", "Bullet list" — `RichTextEditorLabels`), so a later
  surface asserts against them by role/name with no `labels` override here. "Small formatting toolbar"
  is the step's own wording; widening the set later is additive.
- Step 005: `Link` from `@tiptap/extension-link` is registered as an **extension** although no link
  control is in the toolbar. Reason: `StarterKit` carries no link mark, so without it `tiptap-markdown`
  would drop `[text](url)` on the round-trip (DoD-5). It is also `@mantine/tiptap`'s declared peer, so
  the pinned dependency is used rather than left dangling.
- Step 005: `immediatelyRender: true` is passed explicitly. `@tiptap/react@2.27` would default to the
  same behaviour in a browser/jsdom (`isSSR = typeof window === "undefined"`), but stating it keeps the
  document present on the **first** render — DoD-2 asserts the initial Markdown's rendered content — and
  it selects the non-null `Editor` overload of `useEditor`.
- Step 005: `npm install` was **not** run and neither `package.json` nor `package-lock.json` was
  touched — the skeleton had already installed and pinned the set; only the component body changed.
- Step 006: the body load-error branch ships the frozen `Alert` **and no `Retry` control**. The frozen
  view-surface table names no retry for the body (unlike 014's chapter branch, which has one), and a
  second button named "Retry" would be ambiguous whenever both trios fail. `loadChapterBody` is
  re-entrant, so step 007 or 008 can add one without touching the effect.
- Step 006: the body loading branch reuses the chapter trio's wording (`Loading…`) exactly as the freeze
  specifies, so **two** elements read `Loading…` while both trios are in flight. Deliberate, per the
  frozen surface — not a duplicate to be renamed.
- Step 006: `editBodyDraft`'s `bookId` / `chapterId` are `void`-ed rather than `_`-prefixed, because
  `noUnusedParameters` is on and the freeze fixes the parameter *names* (step 007 reads them for
  `restoreBufferKey(bookId, "chapter", chapterId)`).
- Step 006: `npm run build` now emits a ~763 kB `work` chunk and trips Vite's 500 kB chunk warning — the
  TipTap set shipped in step 005 becomes reachable for the first time here (nothing imported the editor
  before). Informational only; the build passes and chunk-splitting is nobody's step in this feature.
- Step 006: the `## Tests` section of this file was **not** read; the `## Skeleton` record was read
  through the end of the step-006 entry only. Implementation was written from the step file,
  `006.context.md` and `context.md`.
- Step 007: a buffer holding the `""` no-base-version marker (D18's dropped-canvas-frame fallback, step
  012's) can never equal a numeric `Chapter.version`, so it reads as **stale at load and opens the
  divergence view** rather than restoring silently. That is the designed outcome — the author lands on
  the normal path, not on a failure — and it is recorded here because step 012 inherits it.
- Step 007: the `409` re-fetch has its own failure branch. When `getChapterText` itself refuses after the
  save's `409`, there is no server body to show beside the draft, so the page falls back to the ordinary
  refusal surface (`bodyServerErrors.form`) with the draft, the buffer and `bodyBaseVersion` still
  untouched — it never opens a half-populated divergence view. The frozen contract does not name this
  case; the fallback was chosen to preserve "never a silent overwrite" in it.
- Step 007: the generation counter is bumped on **every** body load, including the mismatch branch, not
  only on a restore. Step 006's load already bumped unconditionally and the editor is unmounted while the
  divergence view is open, so the extra bump is unobservable — but it keeps one rule ("an external draft
  write remounts the editor") instead of a special case.
- Step 007: three step-006 docstrings that read "step 007 adds…" were rewritten to describe the shipped
  behaviour, and the class docstring's "this page has no buffer" clause was corrected. Comment-only; no
  signature, field or branch moved.
- Step 007: the `## Tests` section of this file was **not** read; the `## Skeleton` record was read
  through the end of the step-007 entry only. Implementation was written from the step file,
  `007.context.md` and `context.md`.
- **Step 009 — a `013.codex` route test contradicts this step's DoD-2, and no `015` role owns the file.**
  - **What the plan asks for:** step 009's DoD-2 — *"The existing codex canvas emission still produces a
    frame identical to today's **apart from the defaulted operation field** — same subject kind, same
    subject id, same field, same text"* — and D17's *"every existing codex emission is unchanged … and no
    codex emission site is edited."* Both are satisfied: `codex_tools.py` was not touched and the emitted
    values are identical.
  - **What conflicts:** `backend/tests/routes/test_chat_turn_canvas.py::test_canvas_frame_reaches_the_stream_between_deltas__DoD2`
    (shipped by `013.codex`) asserts the serialized canvas payload's **exact key set**:
    `assert set(payload) == {"subject_kind", "subject_id", "field", "text"}`. Adding `op` — the one thing
    this step exists to add — makes that a five-key payload, so the assertion fails **permanently**, not
    just against the stub. It is the only failure in the suite that does not self-heal when the coder
    fills the stubs.
  - **Why the skeleton did not just fix it:** it is a **test file**, and not one of step 009's Test files
    (`backend/tests/services/test_chapter_turn_context.py` is the only one). The skeleton writes no
    tests; the test-coder owns only this step's list; the coder owns only Source files. Nobody in `015`'s
    pipeline owns a `013` test file, and the change is a behavioural assertion, not a mechanical
    call-site adaptation.
  - **Suggested resolutions, with tradeoffs.** (1) *Orchestrator authorises a one-line update in place* —
    change the expected set to `{"subject_kind", "subject_id", "field", "text", "op"}` and add
    `assert payload["op"] == "replace"`, which turns the collision into a **stronger** regression
    assertion and is the smallest possible diff; it does mean editing a delivered feature's test.
    (2) *Leave it failing until `/architect` or a bug-fix pass absorbs the widened frame* — keeps
    ownership clean but leaves the backend suite red for the rest of `015`, which will mask real
    regressions in steps 010 and 013. (3) *Re-freeze `op` as an out-of-band field* (e.g. a separate
    event name) — rejected upstream by D17 and by `009.context.md`'s three-option comparison; it would
    also force route and dispatcher changes the step is scoped to avoid. **(1) is the recommendation**;
    it is a decision for the orchestrator, not for the skeleton.
- Step 009: the `run_turn → ToolContext` leg of DoD-4 cannot be driven without a live turn, so it was
  wired **deliberately and structurally**, not to a test: `tools_service.ToolContext(...)` in `run_turn`
  now carries `selection_text=context.selection_text` beside the four fields it already passed. The
  `prepare_turn` leg (`TurnRequest.selection_text → TurnContext.selection_text`) is the half a
  request→context test can observe.
- Step 009: verified by direct smoke run rather than assumed — `determine_mode` over a `Chapter` in each
  of the four states answers `None` / `write-chapter` / `close-chapter` / `None`; the three codex kinds
  and both no-subject shapes are bit-identical to before; `allowed_tool_names(None)` is exactly
  `('web_search',)` while `allowed_tool_names('write-chapter')` is `()` (no `mode_tool` rows seeded —
  D4's designed state, the tools ship unreachable). Against a throwaway DB, a chapter of another book, a
  non-numeric id and an unknown id all resolve to `NO_SUBJECT`, and a chapter subject with **no** id
  keeps its pre-015 answer (itself, no row, no mode).
- Step 009: `backend/tests/routes/test_chat_turn_canvas.py` already shows as modified in the working
  tree — the collateral the entry above describes appears to have been resolved by option (1) outside
  this role. Observed from `git diff --stat` only; the file was neither opened nor edited here.
- Step 009: the `## Tests` section of this file was **not** read; the `## Skeleton` record was read
  through the step-009 entry only. Implementation was written from the step file, `009.context.md` and
  `context.md`.
- **Step 010 — an `011.chat-panel` service test pins `TOOL_REGISTRY`'s exact name set, and no `015` role
  owns the file.**
  - **What the plan asks for:** step 010's Interface intent — *"four new `ToolDef` entries in
    `TOOL_REGISTRY`, with stable string names"* — and DoD-1. Both are satisfied: the four are appended,
    the names are distinct and collide with nothing.
  - **What conflicts:** `backend/tests/services/test_tools.py::test_registry_has_single_web_search_entry__DoD3`
    (shipped by `011`, already amended twice by `013.codex` steps 009 and 010) asserts
    `{t.name for t in tools.TOOL_REGISTRY} == {"web_search", "codex_search", "codex_read_entry",
    "write_codex_draft"}`. Adding the four chapter entries — the one thing this step exists to do — makes
    that assertion fail **permanently**, not just against the stubs. It is the only failure the freeze
    introduces (1081 passed → 1080 passed, 1 failed) and it does **not** self-heal when the coder fills
    the bodies.
  - **Why the skeleton did not just fix it:** it is a **test file**, and not one of step 010's Test files
    (`backend/tests/services/test_chapter_tools.py` is the only one). The skeleton writes no tests; the
    test-coder owns only this step's list; the coder owns only Source files. The change is a behavioural
    assertion, not a mechanical call-site adaptation.
  - **Suggested resolutions, with tradeoffs.** (1) *Orchestrator authorises a one-line update in place* —
    add `"read_chapter_text"`, `"set_chapter_text"`, `"update_selection"`, `"add_text"` to the expected
    set. Smallest possible diff, keeps the test's stated intent ("the registry's contents are pinned, not
    open-ended") intact, and is **exactly what `013.codex` steps 009 and 010 already did to this same
    assertion** — the in-file comment records both amendments. (2) *Leave it failing for the rest of
    `015`* — keeps ownership clean but leaves the backend suite red through steps 011–013, masking real
    regressions. (3) *Loosen the assertion to a superset check* — removes the collision permanently but
    also removes the test's bite, which is the property `011` wrote it for. **(1) is the recommendation**;
    it is a decision for the orchestrator, not for the skeleton.
- Step 010: **the refusal mirror has exactly four rules and an absent selection is not one of them.**
  Step 009's `ToolContext.selection_text` docstring reads *"``None`` when nothing is selected, which is
  also the whole test a selection-write tool applies before refusing"* — a forward-looking remark from
  that freeze, not a plan mandate. Step 010's Interface intent enumerates four refusals and DoD-5 … DoD-8
  cover exactly those four; no criterion gates on the selection. So `update_selection` neither reads
  `context.selection_text` nor refuses on it: the `replace_selection` frame is applied to the author's
  **live** selection by the client, which knows it better than the turn does, and adding a fifth rule
  would have made DoD-3's "each of the three write tools emits exactly one frame" fail for a context
  built without a selection. Flagged so a later step (012) does not read the omission as an oversight.
- Step 010: `ReadChapterTextArgs` is a **field-less** Pydantic schema. Interface intent's *"Each tool has
  a Pydantic argument schema — one text field each"* was read as *every tool has a schema; each **write**
  takes one text field*, because the read tool has no text to be given and any field it could carry would
  be a chapter/book id — the second source of truth the no-subject-argument rule exists to prevent.
  DoD-1 requires only "a Pydantic argument schema". Verified rather than assumed:
  `llm.pydantic_to_openai_tool` builds a valid definition from it (`properties: {}`), and the bound
  callable's zero free parameters match the empty field set the client's `inspect.signature` pre-flight
  compares against.
- Step 010: the four binders are frozen **UNIMPLEMENTED** (they raise) rather than shipped as one-line
  `functools.partial` calls, because binding is behaviour. Consequence for the red gate, stated so it is
  not read as a defect: `build_tool_bindings(tools, context)` **raises** when one of the four is in
  `tools`. No shipped path reaches it — the four are unreachable until an admin selects them (D4), and
  `allowed_tool_names("write-chapter")` is `()` — but a spec that binds before calling will go red at the
  bind, not at the call. Both are correct reds.
- Step 010: `services/chapter_tools.py` imports `functools`, `authz`, `BookState`, `CollaborationMode`,
  `ChapterState` and `CanvasFrame` that the **stubs do not yet reference** — they are the symbols the
  frozen docstrings name and the coder's bodies need, carried so the coder does not reach for a different
  one (e.g. `role != owner` instead of `role == co_author`). The project configures **no linter**, so
  nothing flags them; they stop being unused the moment the bodies land.
- Step 010: the `## Tests` section of this file was **not** read; the `## Skeleton` record was read
  through the step-009 entry only. The freeze was written from the step file, `010.context.md`,
  `context.md`, `services/tools.py`, `services/codex_tools.py`, `services/assistant_runtime.py` and the
  `Chapter` / `BookAccess` models.
- Step 010 (coder): the "not open" refusal names the state as **`chapter.state.value`**, not the enum.
  Python 3.11+ formats a `str`-mixin enum as `ChapterState.planned`, which would have put a class name
  into a model-facing string; the same enum-or-string tolerance step 009 used in
  `_mode_for_chapter_state` is applied, so a row carrying a raw `"planned"` reads identically.
- Step 010 (coder): `read_chapter_text` returns `chapter.text` **verbatim** — no header, no framing, and
  no special string for an empty body. The freeze declares no header constant (unlike
  `codex_tools.py:_entry_header`) and DoD-2 asks for the saved body text, so an empty chapter reads back
  as `""`. Flagged rather than invented around.
- Step 010 (coder): the three write bodies are **written out three times** rather than routed through a
  shared private emitter helper. A helper would have been a symbol the freeze does not name, and the
  parallel-not-shared shape is the same argument `010.context.md` makes for not generalising
  `codex_tools.py` — recorded so the duplication is not read as an oversight.
- Step 010 (coder): the outer `except Exception` in each of the four callables is the **last** line of
  defence, never the mechanism: every enumerated refusal and failure returns from its own named branch
  first, so the guard can only catch something nobody enumerated (and it logs with `exc_info=True` when
  it does). Verified by smoke run — the enumerated paths never reach it.
- Step 011 (coder): D18's *"dropped and **logged**"* is implemented as `console.warn`. It is the **first
  `console.*` call anywhere in `frontend/src/`** — the project has no logger module, no linter and no
  logging convention, so there was nothing to follow. Flagged rather than invented around: if a logging
  seam is ever added, this is its first caller.
- Step 011 (coder): the targetless non-`replace` drop is checked **after** the `subject_id === null` drop
  and **before** the `frame.field !== "body"` condition, because D18 requires it to fire *before anything
  is written to any buffer key*. One observable consequence: a targetless `append` / `replace_selection`
  frame on the `"name"` field is now **logged** where it used to be dropped silently. No buffer key's
  contents change in any ordering; a frame naming no subject at all is still dropped without a log.
- Step 011 (coder): `frontend/src/types/chats.d.ts` needed **no edit** — `CanvasOp` and `CanvasFrame.op?`
  arrived complete from the skeleton (DoD-12 is declarative). The file shows as modified in the working
  tree from that freeze, not from this role.
- Step 011 (coder): the undo module keys its `Map` on `` `${bookId}\u0000${chapterId}` ``. A NUL is the
  one separator no snowflake id can contain, so `("1", "23")` and `("12", "3")` can never collide onto one
  stack. Recorded because the separator is invisible in the source line.
- Step 011 (coder): the skeleton's "Known collateral" item 2
  (`frontend/tests/work/contentSubject.test.ts` asserting **two-argument** `applyDraft` calls, which the
  filled dispatcher now makes three) is real and is **not** in any `015` step's Test files list. That file
  already shows as modified in the working tree, so it appears to have been resolved outside this role —
  observed from `git status --porcelain` only; no test file was opened or edited here.
- Step 011 (coder): the `## Tests` section of this file was **not** read; the `## Skeleton` record was read
  through the end of the step-011 entry only. Implementation was written from the step file,
  `011.context.md` and `context.md`.
- Step 010 (coder): verified by direct smoke run rather than assumed — registry is 8 distinct names with
  the four new ones at indexes 4–7, all `binder`-bearing with `callable is None` and an OpenAI tool
  definition that builds; the bound read has **zero** free parameters and the three bound writes exactly
  `text`; the read returns the saved body in all four chapter states and under an archived book and a
  proposal-mode co-author; each write emits **exactly one** `canvas` frame carrying `"555"` / `"body"` /
  the given text / its own `op`; all four refusals return a string with **no** frame emitted, an owner in
  the same proposal-mode book succeeds, a context with no emitter and one whose emitter raises both
  return strings, a context with `selection_text=None` still writes, and
  `build_tool_bindings(TOOL_REGISTRY, None)` still yields exactly `['web_search']` in both maps.
- Step 010 (coder): the `## Tests` section of this file was **not** read; the `## Skeleton` record was
  read through the step-010 entry (plus the pre-existing `## Notes & Issues`). Implementation was written
  from the step file, `010.context.md` and `context.md`; `services/codex_tools.py` was read for its
  emission and refusal *shape* only and was neither imported nor edited. `pytest` was not run — the
  verifier owns it.
- **Step 011 (skeleton) — known collateral in a spec no 015 role owns.**
  `frontend/tests/work/contentSubject.test.ts` (a delivered `013.codex` spec) carries **three**
  assertions of the form `expect(applyDraft).toHaveBeenCalledWith("body" | "name", <text>)` — an
  **exact two-argument** match. Step 011 freezes `dispatchCanvasFrame` as always passing a **third**
  argument (`frame.op ?? "replace"`), because `CanvasDraftApplier` widens by one optional parameter and
  DoD-4 requires the operation to reach the target. Those three assertions therefore go red **when the
  coder lands the behaviour** (they are green against the skeleton, and the recorded baseline of 546
  passed is unaffected today). The fix is mechanical — append `"replace"` to each expected argument
  list; the cases' intent (the frame's field and text reach the applier) is unchanged and still holds.
  **That file is in no 015 step's Test files list**, so neither the test-coder nor the coder may touch
  it under the pipeline's ownership rules — the orchestrator/user has to allow the three-line update, in
  the same way step 009's `test_chat_turn_canvas.py` key-set assertion was handled. The alternative
  considered and **rejected**: making the dispatcher pass a third argument only for non-`replace`
  frames, which would preserve the arity but give the applier a conditional signature and contradict
  "the target receives the text, the field and the operation".
- **Step 011 (skeleton) — the `open` chapter's verdict now enumerates regions beside `editable:
  "whole"`.** `014` shipped an `editableRegions` list only for `planned`, whose `editable` is `"none"`,
  and its doc said the field is *"absent for every other verdict"*. `015`'s DoD-1/2 cannot be expressed
  that way: the `open` chapter must report its **body text** editable and its **sketch** not, while
  `checkWritePermission(open, "whole")` keeps allowing the body write (DoD-3) — which requires
  `editable` to stay `"whole"`. So the invariant is relaxed to "a verdict may enumerate regions to spell
  out what it means", the vocabulary gains exactly one member (`"chapter-text"`), and `WriteRegion` /
  `checkWritePermission` are untouched. The one shipped `014` assertion this supersedes
  (`subject.test.ts`, `open` … "no region list") is in **this step's own Test files list** and is the
  test-coder's to update.
- **Step 012 (skeleton) — the live `canvas` frame's `op` is DROPPED before it reaches the dispatcher,
  and no `015` step's Source list contains the line that drops it.**
  - **What the plan asks for:** step 012's Interface intent — *"`frontend/src/api/chats.ts` — the
    turn-request body it builds carries the new field. **No other change**: the SSE reader, the frame
    handlers and the streaming conventions are untouched"* — and `012.context.md`'s *"this step likewise
    touches neither `sse.ts` nor the frame handlers — only the request body's shape."*
  - **What conflicts:** `api/chats.ts`'s module-private narrowing function `canvasFrame(data: unknown):
    CanvasFrame | null` (`:194-221`, shipped by `013.codex` step 013) rebuilds the frame from **four**
    enumerated fields — `subject_kind`, `subject_id`, `field`, `text` — and returns an object literal
    with exactly those four. It was written before `CanvasOp` existed and step 011's Source list did not
    include `api/chats.ts`, so **`op` is silently discarded on every live frame**. Consequence:
    `dispatchCanvasFrame` resolves `frame.op ?? "replace"` to `"replace"` for *every* frame that arrives
    over SSE, so `add_text` and `update_selection` behave as `set_chapter_text` in the running app.
  - **Why this is not visible at the red or the verify gate:** `012.context.md` prescribes that the specs
    deliver frames *"by calling the real dispatcher"* with frame literals built in the test, which
    bypasses `canvasFrame` entirely. **DoD-2, DoD-3, DoD-5 and DoD-6 can all pass green while the live
    path is broken.** The only criterion that would catch it is **DoD-11**, which is `[manual/live]`.
  - **Why the skeleton did not just fix it:** it is a one-line behavioural change (narrow `raw.op` to a
    `CanvasOp` and carry it onto the returned literal) inside a function the step's Interface intent
    explicitly places out of scope. Widening the returned object is implementation, not a signature, and
    "no other change" is a plan instruction, not an oversight I may reinterpret.
  - **Suggested resolutions, with tradeoffs.** (1) *Orchestrator widens step 012's `api/chats.ts` scope
    by one sentence* — `canvasFrame` also narrows and forwards `op` (absent / not one of the three values
    → omit the field, which already means `"replace"`). Smallest diff, lands in a file already in the
    Source list, and makes DoD-11 achievable. (2) *Leave it and let DoD-11's live run find it* — keeps
    the plan's wording intact but ships a feature whose two relative operations are dead on the live
    path, discovered only during manual verification. (3) *Defer to a bug-fix pass after 015 completes* —
    honest, but the fix belongs with the step that introduces the consumers. **(1) is the
    recommendation**; it is a decision for the orchestrator, not for the skeleton.
- Step 012 (skeleton): the `## Tests` section of this file was **not** read; the `## Skeleton` record was
  read through the end of the step-011 entry, plus the pre-existing `## Notes & Issues`. The freeze was
  written from the step file, `012.context.md`, `context.md`, root `CLAUDE.md` and the shipped
  `chapterPageState.ts` / `ChapterPage.tsx` / `contentSubject.ts` / `chapterUndo.ts` /
  `codexEntryPageState.ts` / `chats.d.ts` / `api/chats.ts` / `chatPaneState.ts` /
  `ChapterBodyEditor.tsx` sources. `npm test` was not run — the verifier owns it.
- **Step 012: the `canvasFrame` narrowing fix WAS made, on the orchestrator's explicit authorisation** —
  the skeleton's open item immediately above (resolution (1)). The step's Interface intent says
  `api/chats.ts` gets "no other change" beyond the request body, but the shipped module-private
  `canvasFrame(data)` rebuilt the frame from four fields and **discarded `op`**, so on the live path
  every SSE frame would have read as `"replace"` and `add_text` / `update_selection` would have silently
  degraded into whole-body replaces — defeating steps 009–012 in production while every `[test]`
  criterion stayed green, because the specs deliver frames by calling the real dispatcher and bypass this
  function entirely. `api/chats.ts` was already in the Source list; nothing else in it moved.
- Step 012: the fix carries `op` through **without** materialising a default — an absent `op` is left
  absent on the rebuilt frame. Two reasons: the `.d.ts` twin declares `op` optional precisely to mirror
  the backend's default, and `dispatchCanvasFrame` is documented as "the single place the default is
  applied", so adding a second default here would duplicate it; and it keeps a codex frame's rebuilt
  shape byte-identical to `013`'s, which the backend's own step-009 collision (a spec asserting the exact
  key set) shows is worth preserving. An `op` present but **not** one of the three known values drops the
  frame, like any other malformed field — the skeleton's note suggested treating it as `"replace"`, which
  would be exactly the silent whole-body overwrite the protocol refuses.
- Step 012: `applyDraft` gained **no chapter-state gate**. The freeze lists its rules exhaustively (a
  `"name"` frame ignored, the selection refusal, the four ordered steps) and none of them is "refuse
  unless the chapter is `open`"; a registration that varied with the loaded state would also need an
  effect watching that state, which `frontend.md` forbids. DoD-1's "a chapter that is not `open` …
  offers no writable target" is therefore satisfied where it is visible — the editor, the save control
  and the undo control are all inside the `canEditBody` branch, so a non-`open` chapter presents no
  writable surface at all.
- Step 012: the refusal's second leg — a selection the draft **no longer contains** — is the freeze's own
  addition and no DoD exercises it. It is implemented as one `indexOf` miss handled identically to the
  no-selection case, which is what keeps an accidental splice at index `-1` (a write at the end of the
  draft) impossible.
- Step 012: the undo control carries BOTH an `aria-label` and identical visible text
  (`Undo the assistant's last write`), so the frozen accessible name is exact while the visible label is
  still contained in it — step 008's rule for the transition control, applied where the two strings
  happen to coincide.
- Step 012: the `## Tests` section of this file was **not** read; the `## Skeleton` record was read
  through the end of the step-012 entry, plus the pre-existing `## Notes & Issues`. Implementation was
  written from the step file, `012.context.md`, `context.md` and root `CLAUDE.md`. `npm test` and
  `npm run test:types` were **not** run — the verifier owns them; `npx tsc --noEmit` and `npm run build`
  are both clean (all five entries emitted; the ~769 kB `work` chunk warning is step 006's, unchanged).
