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
| 008  | `008.chapter-state-controls.md`         | pending | —        | —    |
| 009  | `009.chapter-canvas-protocol.md`        | pending | —        | —    |
| 010  | `010.chapter-tools.md`                  | pending | —        | —    |
| 011  | `011.work-module-tier-chapter.md`       | pending | —        | —    |
| 012  | `012.chapter-canvas-wiring.md`          | pending | —        | —    |
| 013  | `013.chapter-prompt-composition.md`     | pending | —        | —    |

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
