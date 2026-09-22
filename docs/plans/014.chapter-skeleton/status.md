# Feature 014 — chapter-skeleton

| Step | File                                    | Status  | Verifier | Date |
|------|-----------------------------------------|---------|----------|------|
| 001  | `001.chapter-author-prompt-table.md`    | done    | PASS     | 2026-07-29 |
| 002  | `002.chapter-service.md`                | done    | PASS     | 2026-07-29 |
| 003  | `003.chapter-routes.md`                 | done    | PASS     | 2026-07-29 |
| 004  | `004.chapter-prompt-service-routes.md`  | done    | PASS     | 2026-07-29 |
| 005  | `005.chapters-api-and-book-hub.md`      | done    | PASS     | 2026-07-29 |
| 006  | `006.work-chapters-list.md`             | done    | PASS     | 2026-07-29 |
| 007  | `007.chapter-reorder.md`                | done    | PASS     | 2026-07-29 |
| 008  | `008.work-chapter-item.md`              | done    | PASS     | 2026-07-30 |

## Files Changed

### Step 001 — the `ChapterAuthorPrompt` table, its `db/` module, registration, codec, and the two `db/chapters.py` writes

- `backend/app/db/chapter_author_prompts.py` — bodies filled: `create` / `get_by_chapter_and_user` /
  `update`, each opening its own standalone session; no timestamps set at this layer
- `backend/app/db/chapters.py` — bodies filled: `update` (add/commit/refresh, returns nothing, the
  `db/books.py` idiom) and `delete` (`True`/`False`, the `db/book_members.py` shape keyed on the PK)
- `backend/app/services/db_import_export.py` — bodies filled for the
  `_chapter_author_prompt_to_dict` / `_dict_to_chapter_author_prompt` pair (string ids out,
  string-or-legacy-number in, isoformat-or-`None` timestamps)
- `backend/app/models/chapter_author_prompt.py` — no change needed; the skeleton landed the table
  declaratively (frozen model shape, unique `(chapter_id, user_id)`)
- `backend/app/db/engine.py` — no change needed; the skeleton already added
  `import app.models.chapter_author_prompt` to the MODEL-REGISTRATION SEAM. ADDITIVE MIGRATION SEAM
  left `pass`

### Step 002 — chapter DTOs, the chapter service, and the four chapter capabilities

- `backend/app/services/chapters.py` — bodies filled for all eight symbols: `_to_response`
  (hand-mapped, `id` / `book_id` as `str`, no `text` / `summary` / `summary_status` /
  `system_prompt`), `_resolve_chapter` (parse-then-load, `not_found` for unknown, non-numeric and
  foreign-book ids — the `services/codex.py:_resolve_entry` shape), `list_chapters`, `get_chapter`,
  `add_chapter` (next ordinal = current highest + 1, `planned`, `text=""`, both timestamps),
  `update_sketch` (`not_planned` refusal, sketch + `modified_at` only, no version bump),
  `remove_chapter` (`not_planned` refusal, no renumbering), `reorder_chapters` (whole-list
  validation before any write, then per-row `ordinal` + `modified_at` only)
- `backend/app/models/schemas/chapters.py` — no change needed; the skeleton landed the five DTOs
  declaratively (frozen field sets, `title`'s `strip_whitespace` + `min_length=1` rule)
- `backend/app/services/authz.py` — no change needed; the skeleton already added the four
  `Capability` members and their four `_CAPABILITY_MATRIX` rows (`set_chapter_order` owner-only).
  `read_book` and every other existing member/row/function untouched

### Step 003 — the `/api/books/{book_id}/chapters` route family

- `backend/app/routes/chapters.py` — bodies filled for all six handlers, each one `try` around a
  **single** service call (`list_chapters` / `add_chapter` / `reorder_chapters` / `get_chapter` /
  `update_sketch` / `remove_chapter`) with `except authz.BookAuthorizationError → _map_authz_error`
  first, then `except chapters_service.ChapterError → _map_chapter_error`. `delete_chapter` awaits
  and returns nothing (204, empty body). No business logic, no capability check, no DB access; the
  frozen router prefix, six route registrations, handler signatures, return annotations, reason →
  status map and both mappers are untouched, and the `PUT …/chapters/order` declaration stays ahead
  of the three `/{chapter_id}` routes
- `backend/app/main.py` — no change needed; the skeleton already landed the `from app.routes import
  chapters` import and `app.include_router(chapters.router)` after `books`. Step 004's prompt router
  was deliberately **not** pre-mounted

### Step 004 — the per-author chapter prompt: DTOs, service, route pair

- `backend/app/services/chapter_author_prompts.py` — bodies filled for all five symbols:
  `_require_member` (`owner` / `co_author` pass, anything else → `not_a_member`; no capability check,
  no matrix row, no collaboration-mode check), `_resolve_chapter` (parse-then-load; unknown,
  non-numeric and foreign-book ids all → `not_found`, re-expressed here rather than imported from
  step 002), `_to_prompt_response` (the sole DTO construction site — `None` row → `""` + `None`, a
  row renders its stored text and real `modified_at`, neither state normalised into the other),
  `get_prompt` (guard → resolve → look up `(chapter.id, access.user_id)`; no row is a success), and
  `upsert_prompt` (guard → resolve → create stamping **both** timestamps, or update in place
  stamping `modified_at` only and preserving `created_at`). No chapter-state check, no mode check,
  no read or write of `Chapter.system_prompt`; the user id comes only from `access.user_id`
- `backend/app/routes/chapter_author_prompts.py` — bodies filled for both handlers, each one `try`
  around a **single** service call (`get_prompt` / `upsert_prompt`) with
  `except ChapterAuthorPromptError → _map_prompt_error`. No business logic, no capability check, no
  DB access; the frozen router prefix, both route registrations, handler signatures, return
  annotations, reason → status map and the mapper are untouched, and no `status_code=` was added
  (`PUT` answers `200`)
- `backend/app/models/schemas/chapter_author_prompts.py` — no change needed; the skeleton landed the
  two DTOs declaratively (frozen field sets, `chapter_id` as `str`, no `user_id`)
- `backend/app/main.py` — no change needed; the step-004 skeleton already landed both the
  `from app.routes import chapter_author_prompts` import and
  `app.include_router(chapter_author_prompts.router)` immediately after `book_author_prompts`.
  Step 003's two lines untouched
- Neither `backend/app/services/chat_turn.py` nor `backend/app/services/prompt_composition.py` was
  read, imported or modified (D7, DoD-16)

### Step 005 — chapter DTOs, `api/chapters.ts`, and the read-only Shell book hub

- `frontend/src/api/chapters.ts` — bodies filled for all eight functions through the shared
  `request<T>` wrapper off a `const BASE = "/api/books"`: `GET …/chapters` (**resolves to the whole
  `ChapterListResponse` envelope — not unwrapped, `can_reorder` survives**), `GET …/chapters/{id}`,
  `POST …/chapters`, `PATCH …/chapters/{id}`, `DELETE …/chapters/{id}` (`request<void>`, nothing
  reads a body — `client.request` already turns `204` into `undefined`), `PUT …/chapters/order`
  (envelope again), and `GET`/`PUT …/chapters/{id}/system-prompt`. Every call forwards `signal`;
  the skeleton's `unimplemented` sink deleted and `import { request } from "./client"` added
- `frontend/src/user/pages/bookHubPageState.ts` — bodies filled for `loadBookDetail` (through the
  **existing** `booksApi.getBookDetail`; `api/books.ts` gains nothing) and `loadChapterList` (stores
  the **whole envelope** in `chapterList`, never `.chapters`). Each is the
  `bookSettingsPageState.ts:loadBookSettings` shape verbatim — `runInAction` to `loading`, abort
  guard before every write, `ApiError` → `…Error` + `"error"`, anything else rethrown — and each
  touches only its own trio, so the two fail independently. Stub sink deleted; `runInAction` /
  `booksApi` / `chaptersApi` / `ApiError` imports added
- `frontend/src/user/pages/BookHubPage.tsx` — body filled: one `useState(() => new
  BookHubPageState())`, `useParams()` for `bookId`, exactly ONE `useEffect([state])` spinning a
  single `AbortController` that starts both loads and aborts on unmount. Renders the book title as
  an `h3`, a `Table` of chapters **sorted by `ordinal`** (a copy — the observable array is never
  mutated) with the ordinal, a title link to `/work/:bookId/chapter/:chapterId` and a readable-text
  state `Badge` per row, a "No chapters yet." line on an empty list, each trio's own `Loader` and
  `Alert` branch, and a prominent `Anchor` to `/work/:bookId`. Both work links are plain `<a href>`
  (separate Vite entry). **No add / remove / reorder control and no editable field anywhere** (D2)
- `frontend/src/types/chapters.d.ts` — no change needed; the skeleton landed all seven DTOs plus
  `ChapterLifecycleState` declaratively (a `.d.ts` has nothing to implement)
- `frontend/src/user/routes.tsx` — no change needed; the skeleton already landed `BookHubRoute`
  (`key={bookId}`) and `<Route path="/books/:bookId">` after the settings route. `/`, `/health` and
  `/books/:bookId/settings` untouched
- `frontend/src/api/books.ts` and `frontend/src/work/subject.ts` were **not** opened for edit

### Step 006 — the working page's chapter list: add and remove

- `frontend/src/work/pages/chaptersPageState.ts` — bodies filled for all five `get` computeds and
  all three effect functions; the skeleton's `unimplemented` sink deleted and the
  `runInAction` / `chaptersApi` / `ApiError` / `CreateChapterRequest` imports added.
  `orderedChapters` is an ordinal-ascending **sorted copy** (`[]` before the first load and on
  error — the observable envelope is never mutated); `canReorder` reads `chapterList.can_reorder`
  and is **read but unused in this step** (step 007's, not dead code); `addClientErrors` rejects a
  **whitespace-only** title via `.trim()`, not truthiness; `canSubmitAdd` combines it with
  `addSubmitStatus !== "loading"`; `canRemoveChapter` returns a predicate true only for `planned`.
  `loadChapters` is the `bookStatePageState.ts:loadBookState` shape verbatim and stores the WHOLE
  envelope. `addChapter` sends the drafts **verbatim** (no trim — DoD-3's "exactly those values"),
  seeds the create response into the envelope and then **re-seeds by reloading** (the sanctioned
  "create response plus a reload"; never an optimistic splice), and clears both drafts on **success
  only** — an `ApiError` lands in `addServerErrors` (4xx → `title`, 5xx → `form`, the
  `saveSystemPrompt` idiom) with both drafts intact. `removeChapter` sets `removingChapterId`,
  drops that chapter's refusal, deletes, re-seeds by reloading, and on an `ApiError` stores the
  message **keyed by chapter id** leaving the list untouched; `removingChapterId` is cleared in a
  `finally` on every exit path
- `frontend/src/work/pages/ChaptersPage.tsx` — body filled: one `useState(() => new
  ChaptersPageState())`, `useParams()` for `bookId`, exactly ONE `useEffect([state])` spinning a
  single `AbortController` that registers `() => ({ kind: "chapters" })` through
  `registerContentSubject` with **no `applyDraft`**, starts `loadChapters`, and on cleanup
  `unregisterContentSubject(source)` then `ctrl.abort()`. Renders the error branch (retry, and
  **neither rows nor the add form**), the loading branch, `state.orderedChapters` through ONE row
  structure (a `Stack` of `Paper` rows — a sortable list can wrap it in step 007) with the ordinal,
  a react-router title link to `/:bookId/chapter/:id` and a `Badge` whose text **and** `aria-label`
  carry the readable lifecycle word (`planned` → "Planned"), a "No chapters yet." empty state
  alongside a usable add form, the add form (labelled `Title` / multi-line `Sketch`, submit gated on
  `canSubmitAdd`, every `addServerErrors` value surfaced in one `Alert`), and a per-chapter remove
  `Button` rendered **only** when `state.canRemoveChapter(chapter)` whose accessible name is
  `Remove "<title>"`, with `removeServerErrors[chapter.id]` rendered **inside that chapter's row**.
  Module-private `CHAPTER_STATE_LABELS` (not exported — the freeze declares no label map). Handlers
  are inner functions; no `useCallback` / `useMemo` / `useReducer`, no custom hook, no context, no
  Mantine `useForm`
- `frontend/src/work/routes.tsx` — no change needed; the skeleton already swapped the `chapters`
  child route to `<ChaptersPage />` and added its import. `chapter/:id` / `ChapterItemRoute` (step
  008's) and every other child route untouched
- `frontend/src/work/contentSubject.ts`, `frontend/src/work/subject.ts`,
  `frontend/src/work/components/shell/navItems.ts` and `WorkNavigator.tsx` were **not** opened for
  edit — this step calls them

### Step 007 — reordering the skeleton: move buttons and drag-and-drop

- `frontend/src/work/pages/chaptersPageState.ts` — **additions only**; the list trio, the add-form
  state, the remove state, all five step-006 computeds and all three step-006 effects are
  byte-untouched. The step-007 skeleton sink was deleted and the four frozen step-007 bodies filled:
  `canMoveUp` / `canMoveDown` each read `orderedChapters` once, fold in
  `reorderStatus === "loading"` (so every row's control goes disabled while a `PUT` is in flight —
  DoD-7) and answer `false` at their end of the list, for a chapter that is not in the list and
  before the first load; **neither folds in `canReorder`** (absence, not disabling, is
  `ChapterOrderList`'s branch). `moveChapter` computes the new **full** id sequence locally by
  swapping with the neighbour and persists through `applyChapterOrder` — it makes **no api call of
  its own**, which is what makes DoD-6 structural; an absent chapter or an end-of-list move is a
  no-op that persists nothing. `applyChapterOrder` sets `pendingOrder` / `reorderStatus = "loading"`
  / `reorderError = null`, calls `chaptersApi.reorderChapters(bookId, { chapter_ids }, signal)`
  **once**, and re-seeds the list trio from the returned envelope; on an `ApiError` the message lands
  in `reorderError`, `reorderStatus = "error"`, and the list is re-seeded from a fresh
  `loadChapters` so the rendered order returns to the server's (DoD-5). **`pendingOrder` is discarded
  on both success and failure** (cleared in the outcome `runInAction`, with the `finally` covering
  the abort / rethrow paths), and nothing in the add-form or remove state is ever read or written
  here (DoD-8)
- `frontend/src/work/components/chapters/ChapterOrderList.tsx` — body filled and step 006's row
  markup **moved** in (not duplicated): one module-private `ChapterRow` (`observer`) is the single
  row markup — dimmed ordinal, title as `Anchor component={Link} to={"/{bookId}/chapter/{id}"}`, a
  `Badge` whose text **and** `aria-label` carry the readable lifecycle word from a module-private
  `CHAPTER_STATE_LABELS` map, a remove `Button` rendered only when `state.canRemoveChapter(chapter)`
  with accessible name `Remove "<title>"` and `disabled` while `state.removingChapterId ===
  chapter.id`, and `state.removeServerErrors[chapter.id]` rendered **inside that row**. The ↑ / ↓
  controls (accessible names `Move "<title>" up` / `… down`, `disabled` off
  `canMoveUp` / `canMoveDown`, each calling `moveChapter(...)` and nothing else) render **only when
  `state.canReorder`**. When `canReorder` is true the rows go through `DndContext` +
  `SortableContext` with a per-row `useSortable` handle whose drag-end handler builds the new
  **full** id sequence (`arrayMove`) and calls `applyChapterOrder` — the **same** persist path the
  buttons reach (DoD-6). When `canReorder` is false the component returns a plain `Stack` of rows
  with **no `DndContext`, no handle and no disabled arrows** (DoD-4). Rendered order is a plain
  `const`: `pendingOrder` resolved against `orderedChapters` when non-`null`, otherwise
  `orderedChapters`. `observer` on all three components; `@dnd-kit`'s hooks are called directly and
  are never wrapped in a hook of ours; no `useState` / `useEffect` / `useCallback` / `useMemo` /
  `useReducer`, no context, no Mantine `useForm`
- `frontend/src/work/pages/ChaptersPage.tsx` — **no change needed**; the skeleton already removed the
  inline row rendering, landed `<ChapterOrderList state={state} bookId={id} />` inside the existing
  loading / empty / list branch and added the `state.reorderError` `Alert` under the heading. The
  single `useEffect`, the subject registration, the error branch, the add form and `handleAddSubmit`
  are untouched
- `frontend/package.json` and `frontend/package-lock.json` — **not opened, and no `npm` command that
  mutates them was run**; both dependencies were already installed and declared
- `frontend/src/api/chapters.ts`, `frontend/src/types/chapters.d.ts`, `frontend/src/work/routes.tsx`,
  `contentSubject.ts`, `subject.ts` and `components/shell/**` were **not** opened for edit — this
  step calls them
- Gates: `cd frontend && npm run build` **clean** (7211 modules, 6.95s) and
  `cd frontend && npm run test:types` **clean**. `npm test` deliberately not run — the verifier owns
  it

### Step 008 — the chapter item page: sketch editor, own prompt editor, and the `planned` editability rule

- `frontend/src/work/subject.ts` — **only** `resolveEditability`'s `"chapter"` → `planned` case
  changed: it now returns `editableRegions: ["chapter-sketch", "chapter-own-prompt"]` alongside the
  `readOnlyReason` string it already carried, **verbatim**, and `editable: "none"` (the body-text
  verdict). `open` / `closing` / `closed` and the codex, Book-state, list and default cases are
  byte-untouched, reason strings included; `checkWritePermission`'s signature **and body** are
  byte-untouched, so DoD-13's `checkWritePermission(planned, "whole")` refusal holds structurally.
  The only other edit is the removal of the now-stale `SKELETON (014/008)` paragraph from
  `resolveEditability`'s docstring. `EditableRegion` / `Editability` / `WriteRegion` were landed
  declaratively by the skeleton and needed no change
- `frontend/src/work/pages/chapterPageState.ts` — sink deleted; the `runInAction` / `chaptersApi` /
  `ApiError` / `UpdateChapterSketchRequest` / `UpdateChapterAuthorPromptRequest` imports and a
  module-private `LIFECYCLE_STATE_LABELS` map (not exported — no label map was frozen; the words are
  `ChapterOrderList`'s, so the two surfaces cannot diverge) added. All seven computeds filled:
  `lifecycleStateLabel` (`""` before the first load), `canEditSketch` (`chapter?.state ===
  "planned"` — `false` before a load, on a failed load and for the other three states),
  `sketchDisabledReason` (`null` **exactly when** `canEditSketch`; `closing` / `closed` reuse
  `resolveEditability(...).readOnlyReason` **verbatim** — the module is imported, never changed, the
  `codexEntryPageState.ts` precedent — `open` gets the one sentence this page owns, and the
  not-yet-loaded case says so rather than naming a state it has not got), `sketchDirty`,
  `canSaveSketch` (loaded **and** editable **and** dirty **and** not in flight; no emptiness check),
  `systemPromptDirty` and `canSaveSystemPrompt` (both `bookStatePageState`'s verbatim — **no**
  emptiness check and **no** lifecycle gate). All four effects filled as the
  `bookStatePageState.ts` load/save pair one level down with a chapter id added: `loadChapter` seeds
  `sketchDraft` from `chapter.sketch`, `saveSketch` sends `{ sketch: state.sketchDraft }` verbatim
  (no trim, no `expected_version`) and **re-seeds both `chapter` and `sketchDraft` from the
  response**, `loadSystemPrompt` seeds from `prompt.system_prompt` (an empty prompt is a normal
  loaded value), `saveSystemPrompt` sends `{ system_prompt: … }` and re-seeds from the response. A
  refused save lands the message in its own `…ServerErrors` map (4xx → the field key, 5xx → `form`)
  and **leaves the draft untouched**; each effect touches only its own trio, so the two fail
  independently. No buffer, no `baseVersion`, no stale/divergence path, no `409` branch, no `text`
  field, no delete state
- `frontend/src/work/pages/ChapterPage.tsx` — body filled: one `useState(() => new
  ChapterPageState())`, `useParams()` for `bookId` **and** `id`, exactly ONE `useEffect([state])`
  spinning a single `AbortController` that registers the closure
  `() => ({ kind: "chapter", entityId: id, chapterState: state.chapter?.state })` through
  `registerContentSubject` with **no `applyDraft`**, starts **both** loads, and on cleanup
  `unregisterContentSubject(source)` then `ctrl.abort()`. Renders the chapter trio's own
  loading / error (with a `Retry` that re-runs `loadChapter` only) / ready branches — title as an
  `h3`, the ordinal, and a `Badge` whose text **and** `aria-label` carry
  `state.lifecycleStateLabel` — then the **sketch section** (heading `Chapter sketch`, `Textarea`
  labelled `Sketch` bound to `sketchDraft` and `disabled={!state.canEditSketch}`,
  `state.sketchDisabledReason` rendered as readable `<Text>` whenever non-null, every
  `sketchServerErrors` value in one `Alert`, and a `Save sketch` button rendered **only** when
  `canEditSketch` and disabled off `canSaveSketch`), and then the **prompt section** as a SIBLING of
  the chapter branch — never nested in its success path, so a failed chapter load cannot hide it and
  vice versa (DoD-11) — with its own loading / error / ready branches, one line of copy saying the
  prompt is the author's own and **not shared with co-authors** (and claiming nothing about the
  assistant — D7), a `Textarea` labelled `System prompt` with **no disabled state in any lifecycle
  state**, its `systemPromptServerErrors` surface and a `Save system prompt` button gated on
  `canSaveSystemPrompt`. The two save controls carry **distinct accessible names**. No body text, no
  delete control, no restore-buffer or divergence surface, no state-transition control. `observer`
  applied; handlers are inner functions; no `useCallback` / `useMemo` / `useReducer`, no custom
  hook, no context, no Mantine `useForm`
- `frontend/src/work/routes.tsx` — **no change needed**; the skeleton already swapped
  `ChapterItemRoute`'s element to `<ChapterPage key={id} />` and added the import. The wrapper, its
  `key={id}`, step 006's `chapters` line and every other child route are untouched
- `frontend/src/work/contentSubject.ts`, `frontend/src/api/chapters.ts`,
  `frontend/src/types/chapters.d.ts`, `bookStatePageState.ts`, `BookStatePage.tsx`,
  `chaptersPageState.ts`, `ChaptersPage.tsx` and `components/chapters/**` were **not** opened for
  edit — this step calls them
- Gates: `cd frontend && npm run build` **clean** (7213 modules, 5.98s) and
  `cd frontend && npm run test:types` **clean**. `npm test` deliberately not run — the verifier owns
  it

## Skeleton

### Step 001 — frozen interface (2026-07-29)

Model (declarative — a table is a type, not behavior; nothing left unimplemented):

- `backend/app/models/chapter_author_prompt.py` — `class ChapterAuthorPrompt(SQLModel, table=True)` — new
  - `__tablename__ = "chapter_author_prompts"`
  - `__table_args__ = (UniqueConstraint("chapter_id", "user_id", name="uq_chapter_author_prompt_chapter_id_user_id"),)`
  - `id: int = Field(default_factory=generate_id, primary_key=True)`
  - `chapter_id: int = Field(foreign_key="chapters.id")`
  - `user_id: int = Field(foreign_key="users.id")`
  - `system_prompt: str` — required, NOT NULL; `""` is a value, never coerced to `None`
  - `created_at: datetime | None = Field(default=None)`
  - `modified_at: datetime | None = Field(default=None)`
  - Module docstring states both required things: why a table and not a column on `Chapter` (the
    prompt is per-author, one column holds one author's), and that it supersedes the dormant
    `Chapter.system_prompt` (D1).

`db/` module (session-free, three functions only — bodies raise `NotImplementedError`):

- `backend/app/db/chapter_author_prompts.py` — `async def create(row: ChapterAuthorPrompt) -> ChapterAuthorPrompt` — new
- `backend/app/db/chapter_author_prompts.py` — `async def get_by_chapter_and_user(chapter_id: int, user_id: int) -> ChapterAuthorPrompt | None` — new
- `backend/app/db/chapter_author_prompts.py` — `async def update(row: ChapterAuthorPrompt) -> ChapterAuthorPrompt` — new
  - No `list_*`, no `delete`, no `get_by_id` — the module is deliberately three functions wide.
  - No timestamp policy at this layer: `create` does **not** stamp `created_at`, `update` does **not**
    stamp `modified_at`. Step 004's service owns both.

`db/chapters.py` — two additions; `create` / `get_by_id` / `list_by_book` untouched (bodies raise
`NotImplementedError`):

- `backend/app/db/chapters.py` — `async def update(row: Chapter) -> None` — new
  - Returns **nothing**, resolving the choice `001.context.md` left to the skeleton: `db/books.py`'s
    `update` is the named precedent and returns `None`, and the step file says "return nothing".
    Body is add / commit / refresh only — no read-back, no timestamp, no not-found branch.
- `backend/app/db/chapters.py` — `async def delete(chapter_id: int) -> bool` — new
  - `True` when a row was removed, `False` when nothing matched; a missing id is not an error.
    Keyed on the **primary key** (`db/book_members.py:delete`'s boolean shape, whose key is a natural
    pair — the shape is copied, the key is not).

Registration:

- `backend/app/db/engine.py` — `_register_models()` gains `import app.models.chapter_author_prompt  # noqa: F401`,
  placed after `app.models.chapter` — changed (signature unchanged). **ADDITIVE MIGRATION SEAM left
  `pass`, untouched** — a brand-new table needs no migration statement.

JSONL codec (bodies raise `NotImplementedError`):

- `backend/app/services/db_import_export.py` — `def _chapter_author_prompt_to_dict(prompt: ChapterAuthorPrompt) -> dict[str, object]` — new
- `backend/app/services/db_import_export.py` — `def _dict_to_chapter_author_prompt(data: dict[str, object]) -> ChapterAuthorPrompt` — new
  - Both defined immediately after the `book_author_prompts` pair, mirroring the registry adjacency.
- `backend/app/services/db_import_export.py` — `TABLE_REGISTRY` gains
  `("chapter_author_prompts", ChapterAuthorPrompt, _chapter_author_prompt_to_dict, _dict_to_chapter_author_prompt)`
  at **index 10, immediately after `book_author_prompts`** (and therefore immediately *before*
  `chapters`) — changed. Placement is the step file's and `001.context.md`'s explicit, twice-stated
  directive. See the caveat below.
- `backend/app/services/db_import_export.py` — one import line added:
  `from app.models.chapter_author_prompt import ChapterAuthorPrompt`.
- **The `chapters` codec pair is untouched**: `_chapter_to_dict` still emits `system_prompt` and
  `_dict_to_chapter` still reads it (D1, DoD-12).

Exported dict keys frozen for the new codec pair (`id`, `chapter_id`, `user_id` as `str`; ids parse
string-or-legacy-number; `""` stays `""`; datetimes isoformat-or-`None`):
`{"id", "chapter_id", "user_id", "system_prompt", "created_at", "modified_at"}`.

Caveat on the registry position — **not a blocker, one line to move if the orchestrator prefers**:
`001.context.md` justifies "immediately after `book_author_prompts`" partly with "it references
`chapters` and `users`, **both already earlier**". That premise is false — `chapters` sits at index 10
today, i.e. *after* `book_author_prompts`, so the frozen position puts a child table one slot ahead of
its parent, against the list's documented FK-dependency-order invariant. It is inert (no
`PRAGMA foreign_keys=ON` anywhere in the backend, and import is UPSERT per table), the context's
**second** stated reason — keeping the two per-author-prompt tables adjacent — is unaffected, and
DoD-8 only asserts "after `book_author_prompts`", which holds either way. Moving the entry one slot
later (after `chapters`) would satisfy DoD-8, the FK invariant and the context's own rationale, at the
cost of the adjacency. Frozen as written; flagging so it is a decision, not an oversight.

Compile gate (root `CLAUDE.md` declares **no backend typecheck**, so the gate is import + smoke):
`import app.main` succeeds; `inspect.signature` reports the five frozen `db/` signatures above;
`init_engine` + `init_db()` on a throwaway file creates `chapter_author_prompts` with
`CONSTRAINT uq_chapter_author_prompt_chapter_id_user_id UNIQUE (chapter_id, user_id)`, both FKs and
`system_prompt VARCHAR NOT NULL` — via the registration seam alone, with the migration seam still
`pass`.

Red-gate profile to expect:

- **DoD-6 and DoD-8 are GREEN by construction** against these stubs — the registration import and the
  registry entry are declarative and arrive complete (the 021 step-001 precedent). Neither is evidence
  the step is done. DoD-1..5, 7, 9, 10, 11 must be RED (every body raises `NotImplementedError`);
  DoD-12 is a preservation clause and is green by construction too.
- **8 pre-existing tests now fail, all the same superseded guard** — `TABLE_REGISTRY` grew, and each of
  these pins the sequence as it stood when written. They are **outside this step's Test files list** and
  are the test-coder's scope extension (exactly the 021 step-001 pattern): a one-line
  `"chapter_author_prompts"` insert into each `CANONICAL_ORDER` / `FULL_CANONICAL_ORDER`, no assertion
  logic rewritten. Baseline: `801 passed, 8 failed`.
  - `tests/test_data_domain_assistant_core.py::test_table_registry_order__DoD5`
  - `tests/test_data_domain_assistant_links.py::test_table_registry_order__DoD6`
  - `tests/test_data_domain_book.py::test_table_registry_order__DoD5`
  - `tests/test_data_domain_chapter.py::test_table_registry_order__DoD3`
  - `tests/test_data_domain_chapter_changes.py::test_table_registry_order__DoD4`
  - `tests/test_data_domain_chat.py::test_full_table_registry_equals_canonical_order__DoD4`
  - `tests/test_data_domain_codex.py::test_table_registry_order__DoD4`
  - `tests/test_data_domain_continuity.py::test_table_registry_order__DoD5`

Structural notes that are part of the freeze:

- `backend/app/models/chapter.py` is **untouched** — no schema change, `system_prompt` left exactly as
  it is (`001.context.md`).
- No bulk-ordinal writer was added to `db/chapters.py`; the reorder transaction is step 002's, expressed
  as repeated `update` calls inside one service operation.
- No service, no route, no DTO and no `Capability` member was created by this step.

- Caller-compile edits (out of Source-files scope): None — every symbol is new, and `import app.main`
  is clean.

### Step 002 — frozen interface (2026-07-29)

**Blocker check cleared:** `Capability.read_book` **is** a member of `_CAPABILITY_MATRIX`
(`backend/app/services/authz.py`, row = `{owner, co_author, reader}`). Its row is read and left
untouched, exactly as `002.context.md` requires.

DTOs — `backend/app/models/schemas/chapters.py` (new module; declarative, nothing left
unimplemented):

- `class CreateChapterRequest(BaseModel)` — new
  - `title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]`
  - `sketch: str`
  - The non-blank rule is the field's, so the framework answers **422** on `""` **and** on a
    whitespace-only title, and never reaches the service. There was **no existing declarative
    string-constraint precedent anywhere in `backend/app`** — `strip_whitespace=True, min_length=1`
    is the choice made here; its side effect is that the stored title is the **stripped** value.
    `sketch` carries no constraint (`""` is legitimate).
- `class UpdateChapterSketchRequest(BaseModel)` — new — `sketch: str` (no version token, D6)
- `class ReorderChaptersRequest(BaseModel)` — new — `chapter_ids: list[str]`
- `class ChapterResponse(BaseModel)` — new — `id: str`, `book_id: str`, `ordinal: int`, `title: str`,
  `state: ChapterState`, `sketch: str`, `version: int`, `created_at: datetime | None`,
  `modified_at: datetime | None`
  - No `text`, no `summary`, no `summary_status`, no `system_prompt`.
- `class ChapterListResponse(BaseModel)` — new — `chapters: list[ChapterResponse]`,
  `can_reorder: bool`

Capabilities — `backend/app/services/authz.py` (four members + four rows; **nothing else touched** —
no existing member, no existing row, no existing function, no new `BookAccess` field, no chapter→book
resolver):

- `Capability.add_chapter = "add_chapter"` — new — `frozenset({owner, co_author})`
- `Capability.edit_chapter_sketch = "edit_chapter_sketch"` — new — `frozenset({owner, co_author})`
- `Capability.remove_chapter = "remove_chapter"` — new — `frozenset({owner, co_author})`
- `Capability.set_chapter_order = "set_chapter_order"` — new — `frozenset({owner})` (owner-only,
  US-033.AC-2)
- `Capability`'s class docstring gained "and the 014 chapter-skeleton capabilities" — changed (member
  set otherwise identical). Matrix is 13 rows; `read_book` unchanged.

Service — `backend/app/services/chapters.py` (new module; **every body raises
`NotImplementedError`**):

- `class ChapterErrorReason(str, enum.Enum)` — new — exactly three members:
  `not_found = "chapter-not-found"`, `not_planned = "chapter-not-planned"`,
  `invalid_reorder_set = "invalid-reorder-set"`
  - Route status map for step 003: `not_found` → 404, `not_planned` → 409,
    `invalid_reorder_set` → 400.
- `class ChapterError(Exception)` — new — `__init__(self, reason: ChapterErrorReason, message: str = "") -> None`,
  setting `self.reason` / `self.message` (the `services/books.py:BookError` shape verbatim).
- `def _to_response(chapter: Chapter) -> ChapterResponse` — new (private)
- `async def _resolve_chapter(access: BookAccess, chapter_id: str) -> Chapter` — new (private)
  - Unknown id, **non-numeric** id, and a `book_id != access.book_id` mismatch are all
    `ChapterError(not_found)`. `chapter_id` is `str` at the service boundary and parsed inside —
    the `services/codex.py:_resolve_entry` precedent.
- `async def list_chapters(access: BookAccess) -> ChapterListResponse` — new
- `async def get_chapter(access: BookAccess, chapter_id: str) -> ChapterResponse` — new
- `async def add_chapter(access: BookAccess, request: CreateChapterRequest) -> ChapterResponse` — new
- `async def update_sketch(access: BookAccess, chapter_id: str, request: UpdateChapterSketchRequest) -> ChapterResponse` — new
- `async def remove_chapter(access: BookAccess, chapter_id: str) -> None` — new
- `async def reorder_chapters(access: BookAccess, request: ReorderChaptersRequest) -> ChapterListResponse` — new

Structural notes that are part of the freeze:

- **No entry point takes a book id** — every one takes `BookAccess` and reads `access.book_id`.
- **`authz.require(...)` is the first line of all six entry points**, before any db read; the
  resolver runs after it (`002.context.md`).
- Nothing here reads or writes `Chapter.system_prompt` (D1), bumps `version` (D6), or touches
  `state` / `text` on the reorder path (D5). No collaboration-mode check exists in this module —
  none of the four rows is *(mode)*-qualified, so `services/codex.py`'s proposal refusal is
  deliberately **not** copied.
- No bulk-ordinal writer was added to `db/chapters.py` (out of scope anyway): reorder is repeated
  `db/chapters.update` calls after full up-front validation.

Compile gate (root `CLAUDE.md` declares **no backend typecheck**, so the gate is import + smoke):
`cd backend && .venv/Scripts/python -c "import app.main"` succeeds; `inspect.signature` reports the
eight service signatures above; `model_fields` reports the five DTO field sets above;
`CreateChapterRequest(title="   ")` raises `ValidationError` while `title="  T  "` normalizes to
`"T"`.

Red-gate profile to expect:

- **The five DTOs are complete by construction** — declarative types arrive whole. So is the
  *refusal* half of the authorization DoD items (DoD-3's reader / non-member refusals and DoD-9's
  co-author reorder refusal): `authz.require` raises `BookAuthorizationError` before the body's
  `NotImplementedError`. Neither is evidence the step is done.
- Every other assertion — DoD-1, 2, 4..8, 10..14 and the *permitted* half of DoD-3 — must be RED with
  `NotImplementedError`.
- No pre-existing test should change behaviour: only additive symbols landed, and `import app.main`
  is clean.

- Caller-compile edits (out of Source-files scope): None — every symbol is new or additive, and no
  existing signature changed.

### Step 003 — frozen interface (2026-07-29)

Router — `backend/app/routes/chapters.py` (new module):

- `router = APIRouter(prefix="/api/books", tags=["chapters"])` — new
  - **The prefix is `/api/books`, not `/api/books/{book_id}/chapters`.** All four existing
    book-scoped routers (`books`, `chats`, `codex`, `book_author_prompts`) declare `prefix="/api/books"`
    and carry `{book_id}/…` in each decorator path; `book_author_prompts` is the named placement
    precedent and this copies it exactly. The effective path family is identical either way.

Error mapping (declarative map + two pure translation helpers — real, not stubbed, matching the
`routes/books.py` / `routes/codex.py` skeleton precedent where "the error→status map + helper are
real"; neither can satisfy an assertion on its own, because all six handler bodies raise):

- `backend/app/routes/chapters.py` — `_CHAPTER_ERROR_STATUS: dict[chapters_service.ChapterErrorReason, int]` — new
  - `not_found` → `404`, `not_planned` → `409`, `invalid_reorder_set` → `400`. Exactly the three
    members `ChapterErrorReason` has; no fourth entry.
- `backend/app/routes/chapters.py` — `def _map_chapter_error(err: chapters_service.ChapterError) -> HTTPException` — new
  - `detail=err.message` — the plain-string shape (`routes/books.py`), not `routes/codex.py`'s
    structured `TypedDict` detail: this client has one refusal to render and nothing to branch on.
- `backend/app/routes/chapters.py` — `def _map_authz_error(err: authz.BookAuthorizationError) -> HTTPException` — new
  - `403` with `detail=str(err)`. **Module-private, byte-identical to the copies in
    `routes/books.py`, `routes/chats.py` and `routes/codex.py`** — see the note below.

Handlers — six, in this **declaration order**, which is part of the freeze (DoD-16). Every one takes
`access: authz.BookAccess = Depends(authz.book_access)` as its last parameter and **no handler
declares `book_id`**. Bodies raise `NotImplementedError`:

- `@router.get("/{book_id}/chapters")` — `async def list_chapters(access: authz.BookAccess = Depends(authz.book_access)) -> ChapterListResponse` — new — 200
- `@router.post("/{book_id}/chapters", status_code=status.HTTP_201_CREATED)` — `async def create_chapter(payload: CreateChapterRequest, access: authz.BookAccess = Depends(authz.book_access)) -> ChapterResponse` — new — **201**
- `@router.put("/{book_id}/chapters/order")` — `async def reorder_chapters(payload: ReorderChaptersRequest, access: authz.BookAccess = Depends(authz.book_access)) -> ChapterListResponse` — new — 200
  - **Declared third, before all three `/{chapter_id}` routes.** Verified below.
- `@router.get("/{book_id}/chapters/{chapter_id}")` — `async def get_chapter(chapter_id: str, access: authz.BookAccess = Depends(authz.book_access)) -> ChapterResponse` — new — 200
- `@router.patch("/{book_id}/chapters/{chapter_id}")` — `async def update_chapter_sketch(chapter_id: str, payload: UpdateChapterSketchRequest, access: authz.BookAccess = Depends(authz.book_access)) -> ChapterResponse` — new — 200
- `@router.delete("/{book_id}/chapters/{chapter_id}", status_code=status.HTTP_204_NO_CONTENT)` — `async def delete_chapter(chapter_id: str, access: authz.BookAccess = Depends(authz.book_access)) -> None` — new — **204**, no body

Each handler's body is one `try` around its **single** service call —
`list_chapters(access)` / `add_chapter(access, payload)` / `reorder_chapters(access, payload)` /
`get_chapter(access, chapter_id)` / `update_sketch(access, chapter_id, payload)` /
`remove_chapter(access, chapter_id)` — with `except authz.BookAuthorizationError → _map_authz_error`
first, then `except chapters_service.ChapterError → _map_chapter_error`.

Mount — `backend/app/main.py` (changed; two lines, nothing else):

- `from app.routes import chapters` — added between the `books` and `chats` imports (alphabetical
  position in the existing import block).
- `app.include_router(chapters.router)` — added **after `books`, before `chats`**, i.e. among the
  book-scoped sub-resources and ahead of the `admin_*` group. New sequence:
  `health, auth, books, chapters, chats, codex, book_author_prompts, admin_users, admin_llm_servers,
  admin_db, admin_assistant_config`. **Step 004's prompt router was deliberately NOT pre-mounted.**

Structural notes that are part of the freeze:

- **Response models are return annotations only** — `response_model=` appears nowhere in the module.
- **`{book_id}` is never re-declared**; `chapter_id: str` is the only path param any handler takes,
  and it is `str` because the service parses it (`_resolve_chapter`, which answers `not_found` for a
  non-numeric id).
- **No business logic, no capability check, no DB access** in this module. `404` for a private book
  and `401` for no token are the dependency's; `403` is the service's `authz.require`; `404` for
  another book's chapter is the service's resolver (D4).
- `PATCH` (not `PUT`) on the chapter id, per the step file: the body carries one field of a larger
  resource.

Compile gate (root `CLAUDE.md` declares **no backend typecheck**, so the gate is import + smoke):
`cd backend && .venv/Scripts/python -c "import app.main"` succeeds. The OpenAPI schema reports exactly
the six paths/methods with `201` on create, `204` on delete and `200` elsewhere, each bound to the
step-002 DTOs; `chapters.router.routes` reports the declaration order above with
`PUT …/chapters/order` at index 2, ahead of the three `/{chapter_id}` routes; and
`PUT /api/books/17/chapters/order` matches the chapters router in the mounted app.

Red-gate profile to expect:

- **DoD-13 (`401` without a token) and DoD-12 (`404` on a private book) are GREEN by construction** —
  both are produced by `Depends(authz.book_access)` before any handler body runs. Neither is evidence
  the step is done.
- **DoD-3's blank-title `422` and DoD-17's malformed bodies are GREEN by construction too** —
  framework validation from the step-002 request models, again before the body. DoD-3's "nothing is
  stored" half and DoD-17's likewise, since nothing can be stored at all yet.
- **DoD-16 (route ordering) is GREEN by construction** — declaration order is the interface.
- Every other assertion — DoD-1, 2, 4..11, 14, 15 — must be RED with `NotImplementedError` (a 500 from
  the handler body), including the `403` items (DoD-9, DoD-11): the body raises before the service is
  reached, so no `BookAuthorizationError` is produced at the route layer yet.
- No pre-existing test should change behaviour: only additive symbols landed and one router was
  mounted on paths nothing else claims.

Note for the orchestrator — **"the existing shared helper" does not exist as a shared symbol.**
`003.context.md` and the briefing describe `_map_authz_error` as "the existing shared helper", but
there is no shared module: `routes/books.py`, `routes/chats.py` and `routes/codex.py` each carry a
private, byte-identical copy (`403` + `detail=str(err)`), and `routes/book_author_prompts.py`
documents its *absence*. The duplication **is** the idiom, so a fourth private copy is what was
frozen rather than inventing a shared `routes/_errors.py` module (which is a refactor of three
existing files, outside this step's Source files). Flagging so it reads as a decision, not a miss.

- Caller-compile edits (out of Source-files scope): None — every symbol is new, `main.py` is inside
  the step's Source files, and `import app.main` is clean.

### Step 004 — frozen interface (2026-07-29)

DTOs — `backend/app/models/schemas/chapter_author_prompts.py` (new module; declarative, nothing left
unimplemented):

- `class UpdateChapterAuthorPromptRequest(BaseModel)` — new — `system_prompt: str`
  - Required, no constraint: `""` is valid input (it is how an author clears a prompt). A body
    missing the field is the framework's `422`.
- `class ChapterAuthorPromptResponse(BaseModel)` — new — `chapter_id: str`, `system_prompt: str`,
  `modified_at: datetime | None`
  - **Exactly three fields. No `user_id`**, no `created_at`, no `book_id`. `chapter_id` is a
    **string** (snowflake). `system_prompt` is never nullable; `modified_at` is the only field
    separating "never written" from "written, then cleared".

Service — `backend/app/services/chapter_author_prompts.py` (new module; **every function body raises
`NotImplementedError`**):

- `class ChapterAuthorPromptErrorReason(str, enum.Enum)` — new — **exactly two** members:
  `not_a_member = "not-a-member"`, `not_found = "chapter-not-found"`
  - Route status map: `not_a_member` → **403**, `not_found` → **404**. Do not widen: no token, an
    invisible book and a missing book are the `book_access` dependency's and never reach this
    service; a missing prompt *row* is a success.
- `class ChapterAuthorPromptError(Exception)` — new —
  `__init__(self, reason: ChapterAuthorPromptErrorReason, message: str = "") -> None`, setting
  `self.reason` / `self.message` (the `services/book_author_prompts.py:BookAuthorPromptError` shape
  verbatim).
- `def _require_member(access: authz.BookAccess) -> None` — new (private)
  - `owner` / `co_author` pass; anything else raises `not_a_member`. No capability check, no matrix
    row, no collaboration-mode check. Called **first** by both entry points, before any row is read.
- `async def _resolve_chapter(access: authz.BookAccess, chapter_id: str) -> Chapter` — new (private)
  - Unknown id, non-numeric id and a `chapter.book_id != access.book_id` mismatch are all
    `ChapterAuthorPromptError(not_found)`. `chapter_id` is `str` at the service boundary and parsed
    inside — the step-002 `_resolve_chapter` shape, re-expressed here rather than imported
    (`004.context.md`).
- `def _to_prompt_response(chapter_id: int, row: ChapterAuthorPrompt | None) -> ChapterAuthorPromptResponse` — new (private)
  - The **sole** DTO construction site. `row is None` → `""` + `None`; a row renders its stored text
    and its real `modified_at`. Neither "no prompt" state is normalised into the other.
- `async def get_prompt(access: authz.BookAccess, chapter_id: str) -> ChapterAuthorPromptResponse` — new
- `async def upsert_prompt(access: authz.BookAccess, chapter_id: str, req: UpdateChapterAuthorPromptRequest) -> ChapterAuthorPromptResponse` — new
  - Third parameter is named **`req`** (the 021 name), not `payload` — the route's body param is
    `payload`, the service's is `req`.

Routes — `backend/app/routes/chapter_author_prompts.py` (new module):

- `router = APIRouter(prefix="/api/books", tags=["chapter-author-prompts"])` — new
  - Prefix is `/api/books`, with `{book_id}/chapters/{chapter_id}/system-prompt` in each decorator —
    the placement precedent every book-scoped router follows (`routes/book_author_prompts.py`,
    and step 003's `routes/chapters.py`).
- `_PROMPT_ERROR_STATUS: dict[chapter_author_prompts_service.ChapterAuthorPromptErrorReason, int]` — new
  - `not_a_member` → `403`, `not_found` → `404`. Exactly the two members the enum has.
- `def _map_prompt_error(err: chapter_author_prompts_service.ChapterAuthorPromptError) -> HTTPException` — new
  - `detail=err.message` (plain-string shape). **Real, not stubbed**, following step 003's precedent
    in this same feature ("the error→status map + helper are real"); it cannot satisfy any assertion
    on its own because both handler bodies raise.
  - **No `_map_authz_error` in this module** — the service raises no `BookAuthorizationError`,
    because this step adds no `Capability`.

Handlers — two, in this declaration order; bodies raise `NotImplementedError`:

- `@router.get("/{book_id}/chapters/{chapter_id}/system-prompt")` — `async def get_chapter_system_prompt(chapter_id: str, access: authz.BookAccess = Depends(authz.book_access)) -> ChapterAuthorPromptResponse` — new — 200
- `@router.put("/{book_id}/chapters/{chapter_id}/system-prompt")` — `async def update_chapter_system_prompt(chapter_id: str, payload: UpdateChapterAuthorPromptRequest, access: authz.BookAccess = Depends(authz.book_access)) -> ChapterAuthorPromptResponse` — new — **200, not 201** (no `status_code=` argument on either decorator)

Each handler's body is one `try` around its **single** service call —
`get_prompt(access, chapter_id)` / `upsert_prompt(access, chapter_id, payload)` — with
`except chapter_author_prompts_service.ChapterAuthorPromptError → _map_prompt_error`.

Mount — `backend/app/main.py` (changed; **two lines, and step 003's two are untouched**):

- `from app.routes import chapter_author_prompts` — added between the `books` and `chapters` imports
  (alphabetical position: `chapter_` sorts before `chapters`).
- `app.include_router(chapter_author_prompts.router)` — added **immediately after
  `book_author_prompts`**, keeping the two per-author-prompt routers adjacent and staying ahead of
  the `admin_*` group. New sequence: `health, auth, books, chapters, chats, codex,
  book_author_prompts, chapter_author_prompts, admin_users, admin_llm_servers, admin_db,
  admin_assistant_config`.

Structural notes that are part of the freeze:

- **`{book_id}` is never re-declared** by either handler — it is consumed entirely by
  `Depends(authz.book_access)`. `chapter_id: str` is the only path param, and it is `str` because
  the service parses it.
- **Response models are return annotations only** — `response_model=` appears nowhere.
- **No `DELETE` and no `POST` handler** on the path; both are refused by the framework (405).
- **`services/authz.py` is untouched** — no `Capability` member, no `_CAPABILITY_MATRIX` row (row
  ownership is not a matrix row).
- **No chapter-state check anywhere in this step** — step 002's `not_planned` refusal is deliberately
  not copied (DoD-8), and neither is `services/codex.py`'s collaboration-mode refusal.
- Nothing reads or writes `Chapter.system_prompt` (D1); neither `services/chat_turn.py` nor
  `services/prompt_composition.py` is imported or touched (D7, DoD-16).
- The user id is nowhere an argument or a path segment: both entry points take `BookAccess` and read
  `access.user_id`.

Compile gate (root `CLAUDE.md` declares **no backend typecheck**, so the gate is import + smoke):
`cd backend && .venv/Scripts/python -c "import app.main"` succeeds. `inspect.signature` reports the
five service signatures above; `model_fields` reports the two DTO field sets above; the generated
OpenAPI carries `/api/books/{book_id}/chapters/{chapter_id}/system-prompt` with exactly `get` and
`put`, both `200` (plus the framework's `422`), bound to `ChapterAuthorPromptResponse`; route
matching in the mounted app resolves `GET`/`PUT` on that URL to this router's two handlers,
answers `PARTIAL` (→ **405**) for `DELETE` and `POST`, and step 003's chapters router matches the
path not at all (no shadowing in either direction).

Red-gate profile to expect:

- **DoD-11 (`401` without a token) and DoD-10 (`404` on a private book) are GREEN by construction** —
  both are produced by `Depends(authz.book_access)` before any handler body runs.
- **DoD-14 (no `DELETE`, no `POST`) and DoD-15 (malformed `PUT` body → `422`) are GREEN by
  construction too** — framework method rejection and framework body validation, both before the
  body. Neither is evidence the step is done.
- **DoD-13 (the response exposes no user identifier) is partly green by construction** — the DTO
  field set is declarative; any assertion that also reads a live response body is RED.
- Every other assertion — DoD-1..9, DoD-12 — must be RED with `NotImplementedError` (a 500 from the
  handler body), **including the `403` item (DoD-9)**: the handler body raises before the service is
  reached, so no `ChapterAuthorPromptError` is produced yet.
- No pre-existing test should change behaviour: only additive symbols landed, and one router was
  mounted on a path nothing else claims.

- Caller-compile edits (out of Source-files scope): None — every symbol is new, `main.py` is inside
  the step's Source files, and `import app.main` is clean.

### Step 005 — frozen interface (2026-07-29)

**The two naming decisions the plan delegated to this agent are recorded first — steps 006, 007 and
008 bind to them.**

**Naming decision 1 — the wire chapter-state union is `ChapterLifecycleState`.**
`frontend/src/work/subject.ts`'s `ChapterState` is untouched, un-imported and unchanged; nothing in
`work/` imports from `types/chapters.d.ts` as a result of this step. Reasoning: the two types are
structurally identical today but belong to different layers, and the pane model is explicitly allowed
to diverge (`005.context.md`; `016` / `018`). Renaming the *wire* side rather than the pane side is
what keeps `work/subject.ts` untouched, and `Lifecycle` names the thing itself (`domain-chapter.md`'s
`planned → open → closing → closed` machine) rather than the layer — every type in `types/` is a wire
type, so a `Wire` suffix would be noise on exactly one of them. Step 008, which will hold both names
in one file, gets an unambiguous read at the conversion site
(`ChapterResponse.state` → `LoadedSubject.chapterState`).

**Naming decision 2 — the existing book-detail read is `booksApi.getBookDetail(bookId, signal?)`**
(`frontend/src/api/books.ts`, `Promise<BookDetailResponse>`), the same function
`bookSettingsPageState.ts:loadBookSettings` already calls. Bound, not invented; **`api/books.ts` was
not opened for edit and gains no function.**

DTOs — `frontend/src/types/chapters.d.ts` (new module; declarative, nothing left unimplemented —
`.d.ts`). Field sets mirror the step-002 / step-004 backend DTOs wire-exactly, `snake_case`, ids
`string`, `ISODateString` reused from `./common` (no second alias declared):

- `export type ChapterLifecycleState = "planned" | "open" | "closing" | "closed"` — new
- `export interface ChapterResponse` — new — `id: string`, `book_id: string`, `ordinal: number`,
  `title: string`, `state: ChapterLifecycleState`, `sketch: string`, `version: number`,
  `created_at: ISODateString | null`, `modified_at: ISODateString | null`
  - No `text`, no `summary`, no `summary_status`, no `system_prompt`.
- `export interface ChapterListResponse` — new — `chapters: ChapterResponse[]`, `can_reorder: boolean`
  - Modelled here **because it is not unwrapped** (contrast `types/codex.d.ts`, which deliberately
    does not model its envelope).
- `export interface CreateChapterRequest` — new — `title: string`, `sketch: string` (no `ordinal`)
- `export interface UpdateChapterSketchRequest` — new — `sketch: string` (no version token, D6)
- `export interface ReorderChaptersRequest` — new — `chapter_ids: string[]`
- `export interface ChapterAuthorPromptResponse` — new — `chapter_id: string`, `system_prompt: string`,
  `modified_at: ISODateString | null` — `books.d.ts`'s `BookAuthorPromptResponse` one level down;
  **no `user_id`**, no `created_at`, no `book_id`.
- `export interface UpdateChapterAuthorPromptRequest` — new — `system_prompt: string`

API — `frontend/src/api/chapters.ts` (new module; **every body is UNIMPLEMENTED** and throws through a
module-private `unimplemented(fn, ..._args): never` sink, which also consumes the frozen parameter
lists so they satisfy `noUnusedParameters`; the coder adds `import { request } from "./client"` and
deletes the sink). Book id first, `signal?: AbortSignal` trailing, `const BASE`-style paths through
`client.request<T>` — the `api/codex.ts` shape, with the one sanctioned departure:

- `export async function listChapters(bookId: string, signal?: AbortSignal): Promise<ChapterListResponse>` — new
  - **Returns the WHOLE envelope, never a bare array** (DoD-8, `context.md`). `GET /api/books/{bookId}/chapters`.
- `export async function getChapter(bookId: string, chapterId: string, signal?: AbortSignal): Promise<ChapterResponse>` — new — `GET …/chapters/{chapterId}`
- `export async function createChapter(bookId: string, body: CreateChapterRequest, signal?: AbortSignal): Promise<ChapterResponse>` — new — `POST …/chapters` (201)
- `export async function updateChapterSketch(bookId: string, chapterId: string, body: UpdateChapterSketchRequest, signal?: AbortSignal): Promise<ChapterResponse>` — new — **`PATCH`** `…/chapters/{chapterId}`
- `export async function removeChapter(bookId: string, chapterId: string, signal?: AbortSignal): Promise<void>` — new — `DELETE …/chapters/{chapterId}`, `204`
  - Named `removeChapter` (not `deleteChapter`): `api/books.ts:removeMember` is the repo's only
    frontend `DELETE` precedent and the step file's own word is "remove". Resolves to nothing —
    `client.request` already turns `204` into `undefined` without parsing (DoD-9), so no body is read.
- `export async function reorderChapters(bookId: string, body: ReorderChaptersRequest, signal?: AbortSignal): Promise<ChapterListResponse>` — new — `PUT …/chapters/order`, returns the envelope
- `export async function getOwnChapterSystemPrompt(bookId: string, chapterId: string, signal?: AbortSignal): Promise<ChapterAuthorPromptResponse>` — new — `GET …/chapters/{chapterId}/system-prompt`
- `export async function updateOwnChapterSystemPrompt(bookId: string, chapterId: string, body: UpdateChapterAuthorPromptRequest, signal?: AbortSignal): Promise<ChapterAuthorPromptResponse>` — new — `PUT …/chapters/{chapterId}/system-prompt` (200)
  - The prompt pair mirrors `api/books.ts`'s `getOwnSystemPrompt` / `updateOwnSystemPrompt` one level
    down and keeps the `…Own…` naming (the endpoint has no way to name a user). The `Chapter`
    qualifier is added deliberately so that a module importing both pairs **by name** cannot be
    ambiguous about which level it addresses — the same anti-collision principle as decision 1.
    Namespace-imported callers read `chaptersApi.getOwnChapterSystemPrompt(...)`.

State — `frontend/src/user/pages/bookHubPageState.ts` (new module; fields declarative and complete,
**both effect bodies UNIMPLEMENTED** through the same throwing sink):

- `export class BookHubPageState` — new — `constructor()` calls `makeAutoObservable(this)`; **no
  effectful methods**, no `get` computeds, and (D2, read-only page) **no draft field, no
  `…ServerErrors`, no `…SubmitStatus`**. Two independent trios:
  - `detail: BookDetailResponse | null = null` · `detailStatus: "idle" | "loading" | "ready" | "error" = "idle"` · `detailError: string | null = null`
  - `chapterList: ChapterListResponse | null = null` · `chapterListStatus: "idle" | "loading" | "ready" | "error" = "idle"` · `chapterListError: string | null = null`
    - Named `chapterList`, holding the **whole envelope** — not `chapters` holding an array. The name
      is what stops a later `state.chapters.map(...)` from re-introducing the unwrap `can_reorder`
      would not survive (DoD-8, and steps 006/007 depend on it).
- `export async function loadBookDetail(state: BookHubPageState, bookId: string, signal?: AbortSignal): Promise<void>` — new
  - Loads through the **existing** `booksApi.getBookDetail` (naming decision 2). Touches only the
    detail trio.
- `export async function loadChapterList(state: BookHubPageState, bookId: string, signal?: AbortSignal): Promise<void>` — new
  - Loads through `chaptersApi.listChapters` and stores the envelope. Touches only the chapter trio.
    An empty `chapters` array is a successful load, never an error (DoD-2).
  - The two functions are separate precisely so the trios fail independently (DoD-5).

Page — `frontend/src/user/pages/BookHubPage.tsx` (new module):

- `export const BookHubPage = observer(function BookHubPage() { … })` — new — **zero props**;
  the body is UNIMPLEMENTED and **throws on render**.
  - Frozen contract for the coder: one `useState(() => new BookHubPageState())`, `useParams()` for
    `bookId`, exactly ONE page-level `useEffect([state])` spinning a single `AbortController` that
    starts BOTH loads and aborts on unmount. Renders the book title as the heading, chapters in
    ordinal order with a **readable-text** state badge each (queries are by role/label — a colour is
    not a badge), an empty-state line, each trio's own loading and error branch, a per-chapter link to
    `/work/:bookId/chapter/:chapterId`, and a prominent link to `/work/:bookId`. Both work links are
    plain `<a href>` — `/work` is a separate Vite entry, so it is a full page load, not a
    react-router navigation (`BookshelfPage.tsx` precedent).
  - **Read-only (D2): no add form, no remove control, no reorder control, no editable field, and
    nothing else on the page** (DoD-3).

Routes — `frontend/src/user/routes.tsx` (changed; declarative, complete as written):

- `function BookHubRoute()` — new (module-private) — reads `useParams().bookId` and returns
  `<BookHubPage key={bookId} />`, the `BookSettingsRoute` pattern verbatim (DoD-6).
- `<Route path="/books/:bookId" element={<BookHubRoute />} />` — new, declared **after**
  `/books/:bookId/settings`. React Router 7 ranks matches by specificity, not declaration order, so
  the hub cannot shadow the settings route either way; the ordering states the intent. `/`, `/health`
  and the settings route are otherwise **untouched**, and the `UserRoutes` signature is unchanged.

Structural notes that are part of the freeze:

- **`frontend/src/api/books.ts` gains nothing** and was not edited — the hub reuses `getBookDetail`.
- **`frontend/src/work/subject.ts` is untouched** and does not import the wire union.
- No component other than `BookHubPage` was created; no `frontend/src/user/components/**` file was
  added (the hub renders a heading, a list, badges, two error branches, an empty state and two links,
  and nothing else — `005.context.md`'s size note).
- `src/types/chapters.d.ts` declares no runtime value (a `.d.ts` cannot), so any option/label table a
  later step wants lives in a `.ts` module, per the `api/books.ts` precedent.

Compile gate: `cd frontend && npm run build` (= `tsc && vite build`) — **clean**, 7202 modules, built
in 6.96s. `npm test` deliberately not run (no specs exist yet); `npm run test:types` likewise covers
`tests/`, which is the test-coder's.

Red-gate profile to expect:

- **DoD-7, DoD-8, DoD-9 must all be RED**: every `api/chapters.ts` body throws
  `api/chapters.ts: <fn> is UNIMPLEMENTED (skeleton 014/005).` — no path is built, no method is set,
  no signal is forwarded and nothing is returned, so nothing can accidentally satisfy an assertion.
- **DoD-1 … DoD-6 must all be RED**: `BookHubPage` throws during render, so every page assertion fails
  at `render()`. The route registration itself is declarative and arrives complete — a test asserting
  only that `/books/:bookId` *resolves to something* would be green by construction and is not
  evidence the step is done; DoD-1's real content (title + ordered chapters + state) cannot be.
- The two state effect functions throw as rejected promises (`void load…(…)` in the page), but the
  page never reaches them — it throws first. No trio can reach a plausible `"ready"`.
- No pre-existing test should change behaviour: every symbol is new, the only edited file is
  `routes.tsx` (one import, one wrapper, one additional `<Route>`), and the build is clean.

- Caller-compile edits (out of Source-files scope): **None** — every symbol is new, `routes.tsx` is
  inside this step's Source files, and no existing signature changed.

### Step 006 — frozen interface (2026-07-29)

State — `frontend/src/work/pages/chaptersPageState.ts` (new module; observable fields declarative and
complete, **every `get` computed and every external effect body UNIMPLEMENTED** through a
module-private `unimplemented(fn, ..._args): never` sink that also consumes the frozen parameter lists
so they satisfy `noUnusedParameters`; the coder adds the `runInAction` / `chaptersApi` / `ApiError` /
`CreateChapterRequest` imports and deletes the sink):

- `export class ChaptersPageState` — new — `constructor()` calls `makeAutoObservable(this)`; **no
  effectful methods, no setters**. Observable fields, in declaration order:
  - `chapterList: ChapterListResponse | null = null` · `chapterListStatus: "idle" | "loading" | "ready" | "error" = "idle"` · `chapterListError: string | null = null`
    - Holds the **WHOLE envelope**, never `.chapters` — `can_reorder` survives for step 007 without a
      second load (`context.md`; step 005's `listChapters` deliberately does not unwrap). An empty
      `chapters` array is a successful load.
  - `addTitleDraft = ""` · `addSketchDraft = ""`
  - `addServerErrors: Record<string, string> = {}` — the `021` shape, keyed by **field name**
    (`title` / `sketch`) plus the general `form` key.
  - `addSubmitStatus: "idle" | "loading" | "ready" | "error" = "idle"`
  - `removingChapterId: string | null = null` — the id whose removal is in flight, `null` otherwise.
    **There is deliberately no separate remove submit status**: at most one removal runs at a time and
    the id already says which row it belongs to.
  - `removeServerErrors: Record<string, string> = {}` — **keyed by CHAPTER ID**, not by field name.
    This is the one `…ServerErrors` map in the feature keyed by row; the keying is what lets DoD-9's
    refusal render beside the chapter it concerns instead of as a page banner.
- Pure `get` computeds (all five bodies throw):
  - `get orderedChapters(): ChapterResponse[]` — new — ordinal-ascending **sorted copy**; `[]` before
    the first successful load and on error.
  - `get canReorder(): boolean` — new — read straight off `chapterList.can_reorder`, `false` until
    loaded. **Read but unused in step 006** (the computed exists; nothing renders off it yet) — step
    007 is the consumer. Not dead code.
  - `get addClientErrors(): Record<string, string>` — new — the `…ServerErrors` map's shape:
    `{ title: <message> }` when the title draft is blank **or whitespace-only** (DoD-5), `{}`
    otherwise. The sketch contributes nothing — an empty sketch is legitimate. **This is the ONE
    client-validation computed in feature 014**; the prompt/sketch editors keep the `021` no-client-
    validation shape.
  - `get canSubmitAdd(): boolean` — new — no client errors **and** `addSubmitStatus !== "loading"`.
    Deliberately **not** gated on `chapterListStatus`: DoD-10's "no add form bound to stale data" is
    the page's render branch (the form is absent in the error branch), not a condition of this
    computed.
  - `get canRemoveChapter(): (chapter: ChapterResponse) => boolean` — new — **a computed returning a
    predicate**, not a method: the rules say state is observable data + pure `get` computeds, and a
    per-chapter question needs a parameter. `true` only for `state === "planned"`. Call site reads
    `state.canRemoveChapter(chapter)`. Drives the affordance (DoD-8) and never substitutes for the
    server's answer (DoD-9).
- External effect functions — `(state, bookId, …, signal?)`, `runInAction`, **no optimistic
  mutation**; after a write the list is re-seeded from the server:
  - `export async function loadChapters(state: ChaptersPageState, bookId: string, signal?: AbortSignal): Promise<void>` — new
    - The `bookStatePageState.ts:loadBookState` shape verbatim (loading → abort guard → `ApiError` →
      `…Error` + `"error"`, else rethrow). Also the retry path behind the error branch (DoD-10) and
      the re-seed path both writes below call.
  - `export async function addChapter(state: ChaptersPageState, bookId: string, signal?: AbortSignal): Promise<void>` — new
    - Body built from the drafts, `chaptersApi.createChapter`, then re-seed from the server (create
      response + reload, or the reload alone). Clears both drafts on **success only**; an `ApiError`
      lands in `addServerErrors` with `addSubmitStatus = "error"` and **leaves both drafts intact**
      (DoD-6). The chapter lands last because the server appends (DoD-4).
    - Takes **no arguments beyond `bookId`** — the drafts are read off `state`, so the form is the
      single source of the submitted values (DoD-3).
  - `export async function removeChapter(state: ChaptersPageState, bookId: string, chapterId: string, signal?: AbortSignal): Promise<void>` — new
    - Sets `removingChapterId`, clears that chapter's `removeServerErrors` entry, calls
      `chaptersApi.removeChapter` (resolves to nothing — `204`), re-seeds from the server, and clears
      `removingChapterId` on every exit path. On an `ApiError` the message is stored under
      **`chapterId`** and **the list is left untouched** (DoD-9).
    - Name-shadows `chaptersApi.removeChapter` only across a namespace import
      (`import * as chaptersApi`), so there is no collision; the page imports these three names from
      this module alone.

Page — `frontend/src/work/pages/ChaptersPage.tsx` (new module):

- `export const ChaptersPage = observer(function ChaptersPage(): ReactElement { … })` — new — **zero
  props**; the body is UNIMPLEMENTED and **throws on render**.
  - Frozen contract for the coder (full prose in the module docstring): one
    `useState(() => new ChaptersPageState())`, `useParams()` for `bookId`, exactly ONE page-level
    `useEffect([state])` that spins a single `AbortController`, builds a stable
    `source = () => ({ kind: "chapters" })`, calls `registerContentSubject(source)` **with NO
    `applyDraft`** (a list subject is read-only in the pane model; add/remove are page chrome), starts
    `loadChapters`, and on cleanup calls `unregisterContentSubject(source)` then `ctrl.abort()`
    (DoD-12) — the `CodexListPage` registration verbatim.
  - Renders: the trio's loading and error branches (the error branch carrying a retry and **neither
    rows nor the add form**, DoD-10); `state.orderedChapters` with ordinal, title linked to
    `/work/:bookId/chapter/:id`, and a **readable state badge** whose label contains the lifecycle
    word itself (`planned` → "Planned", …) so it is reachable by accessible name; an empty state
    alongside a usable add form (DoD-2); the add form (labelled title field, labelled multi-line
    sketch field, submit gated on `canSubmitAdd`, `addServerErrors` surface); and a per-chapter remove
    control rendered **only** when `state.canRemoveChapter(chapter)`, whose **accessible name names
    the chapter** (e.g. `Remove "<title>"`), with `state.removeServerErrors[chapter.id]` rendered
    beside that chapter.
  - **Rendering shape for step 007:** the rows go through ONE structure a sortable list can wrap;
    step 007 lifts the row rendering wholesale into `components/chapters/ChapterOrderList.tsx`. No
    drag surface is designed here.
  - Handlers are inner functions closing over the state; no `useCallback` / `useMemo` / `useReducer`,
    no custom `useX` hook, no React context, no Mantine `useForm`.

Routes — `frontend/src/work/routes.tsx` (changed; **exactly one route line plus its import**):

- `<Route path="chapters" element={<ChaptersPage />} />` — changed (was
  `<Route path="chapters" element={<SubjectPlaceholderPage heading="Chapters" owner="014.chapter-skeleton" />} />`)
- `import { ChaptersPage } from "./pages/ChaptersPage";` — added after the `BookStatePage` import.
- **`chapter/:id` is untouched**, `ChapterItemRoute` (and its `key={id}`) included — that is step
  008's. `SubjectPlaceholderPage` is still imported and still used by `chapter/:id`, `variants` and
  `variants/:chapterId`. No other child route changed. **No `key` on the chapters route**: it takes no
  path param of its own, and the shell above it already remounts on `:bookId`.

Structural notes that are part of the freeze:

- **`frontend/src/work/contentSubject.ts` and `frontend/src/work/subject.ts` are UNTOUCHED** — this
  step calls them. `subject.ts` already carries the `"chapters"` `SubjectKind` member and the
  read-only list verdict.
- **`components/shell/navItems.ts` and `WorkNavigator.tsx` are UNTOUCHED** — the Chapters entry with
  `extraActiveSegments: ["/chapter"]` already exists; nothing in the navigator changes in this whole
  feature.
- No component file was created under `frontend/src/work/components/**` — `ChapterOrderList.tsx` is
  step 007's.
- No exported label map for the lifecycle states was frozen (the intent names no such symbol); the
  badge's readable text is a render detail, constrained above so both sides agree on the word.

Compile gate: `cd frontend && npm run build` (= `tsc && vite build`) — **clean**, 7205 modules, built
in 7.12s. `npm test` deliberately not run (this step's spec does not exist yet); `npm run test:types`
covers `tests/`, which is the test-coder's.

Red-gate profile to expect:

- **Every DoD `[test]` item must be RED.** `ChaptersPage` throws during render, so DoD-1..12 all fail
  at `render()` — including DoD-11 and DoD-12, which reach the page through the route.
- The route registration itself is declarative and arrives complete: a test asserting only that
  `/work/:bookId/chapters` *no longer renders the placeholder* could pass on the absence alone, which
  is **not** evidence the step is done — DoD-11's real content (this page rendering) cannot pass.
- The five computeds and the three effect functions throw, so no trio can reach a plausible
  `"ready"`, no draft can clear and no list can mutate.
- No pre-existing test should change behaviour: both new modules are new, and `routes.tsx`'s only
  change swaps one placeholder element that no shipped spec asserts on.

- Caller-compile edits (out of Source-files scope): **None** — both new modules are new, `routes.tsx`
  is inside this step's Source files, and no existing signature changed.

### Step 007 — frozen interface (2026-07-29)

**Dependencies — already installed; NO install was performed by this agent.**
`frontend/package.json` already declares `"@dnd-kit/core": "^6.3.1"` and
`"@dnd-kit/sortable": "^10.0.0"`; `frontend/package-lock.json` already resolves both plus the
transitives; and `node_modules` carries **`@dnd-kit/core` 6.3.1, `@dnd-kit/sortable` 10.0.0,
`@dnd-kit/accessibility` 3.1.1, `@dnd-kit/utilities` 3.2.2**. Neither `package.json` nor
`package-lock.json` was run against `npm`, opened for edit or hand-touched — both were already
modified in the working tree before this session and are byte-identical to how they arrived. The
step file's "add the two dependencies" line is therefore **already satisfied**; the coder must not
re-run `npm install` either.

State — `frontend/src/work/pages/chaptersPageState.ts` (**ADDITIONS ONLY**; the list trio, the
add-form state, the remove state, all five step-006 `get` computeds and all three step-006 effect
functions are byte-untouched and still implemented). The step-007 additions are frozen with
**UNIMPLEMENTED bodies** through a re-introduced module-private
`unimplemented(fn, ..._args): never` sink — the step-006 coder deleted the step-005/006 one, this
is a fresh copy carrying the `(skeleton 014/007)` marker, and the step-007 coder deletes it:

- `export type ChapterMoveDirection = "up" | "down"` — new
  - Exported so the move effect's fourth parameter is a named union rather than an inline literal
    pair the test-coder has to re-spell. There is no per-chapter move endpoint (D3).
- `export class ChaptersPageState` — changed (**additive only**; `makeAutoObservable(this)`, no
  effectful methods, no setters, all as before). Three new observable fields, declared after
  `removeServerErrors`:
  - `reorderStatus: "idle" | "loading" | "ready" | "error" = "idle"` — new
  - `reorderError: string | null = null` — new — the **third independent error surface**, beside
    `chapterListError`, `addServerErrors` and `removeServerErrors`. A single holder, not a map:
    a reorder concerns the whole list, so there is no row to key it by (contrast
    `removeServerErrors`). DoD-8 is what the separation buys.
  - `pendingOrder: string[] | null = null` — new — the id sequence being arranged; non-`null`
    **exactly while `reorderStatus === "loading"`**, and **discarded on BOTH success and failure**
    (DoD-5). Ids, not chapters, so it cannot drift from the envelope's rows. A rendering optimism
    only — nothing in the list trio is mutated until the server answers.
- Two new pure `get` computeds (both bodies throw), each returning a **predicate**, matching the
  step-006 `canRemoveChapter` shape (a per-chapter question needs a parameter, and the rules allow
  only observable data plus pure `get` computeds):
  - `get canMoveUp(): (chapter: ChapterResponse) => boolean` — new
  - `get canMoveDown(): (chapter: ChapterResponse) => boolean` — new
  - Both are `false` at their end of `orderedChapters` (DoD-3), `false` for a chapter not in the
    list, `false` before the first load, **and `false` for every row while
    `reorderStatus === "loading"`** so a second move cannot race the first (DoD-7). Folding the
    in-flight condition in is a decision, recorded here: it makes
    `disabled={!state.canMoveUp(chapter)}` the single source of the ↑/↓ disabled answer and keeps
    it consistent with `pendingOrder` rendering a different sequence during flight.
  - **Neither folds in `canReorder`** — when the caller may not reorder the controls are ABSENT,
    not disabled (DoD-4), and absence is `ChapterOrderList`'s branch. `canReorder` itself is
    unchanged from step 006; **this step is what finally consumes it.**
- Two new external effect functions — `(state, bookId, …, signal?)`, `runInAction`, no optimistic
  state mutation, re-seed from the server (both bodies throw):
  - `export async function moveChapter(state: ChaptersPageState, bookId: string, chapterId: string, direction: ChapterMoveDirection, signal?: AbortSignal): Promise<void>` — new
    - Computes the new **full** id sequence locally (swap with the neighbour in `direction`) and
      persists through `applyChapterOrder` — it performs **no api call of its own**, which is what
      makes "one persist path" (DoD-6) structural rather than a convention. An impossible move
      (chapter absent, or already at that end) is a no-op that persists nothing.
  - `export async function applyChapterOrder(state: ChaptersPageState, bookId: string, chapterIds: string[], signal?: AbortSignal): Promise<void>` — new
    - Takes the **whole ordered id list** (what a drag-end handler produces), sets
      `pendingOrder` / `reorderStatus = "loading"` / `reorderError = null`, calls
      `chaptersApi.reorderChapters(bookId, { chapter_ids: chapterIds }, signal)` **once**, and
      re-seeds the list trio from the returned envelope. On an `ApiError`: the message lands in
      `reorderError`, `reorderStatus = "error"`, and the list is re-seeded from a **fresh
      `loadChapters`** so the rendered order returns to the server's (DoD-5, US-033.AC-2);
      anything else rethrows. `pendingOrder` is cleared on every exit path.
    - Named `applyChapterOrder`, not `reorderChapters`: `chaptersApi.reorderChapters` is reached
      through the `import * as chaptersApi` namespace so a same-name export would not collide, but
      the page imports these names bare and a bare `reorderChapters` would read ambiguously beside
      the mocked api function in a spec.

Component — `frontend/src/work/components/chapters/ChapterOrderList.tsx` (new module; the first
file under `frontend/src/work/components/chapters/`):

- `export interface ChapterOrderListProps` — new — `state: ChaptersPageState`, `bookId: string`
  - `bookId` is a **prop**, not a `useParams()` read: route reads and `useEffect` are page-level
    only, and the row's chapter link plus all three effect calls need it. This is the
    `components/chat/ChatPane.tsx` shape — a non-page component that takes `bookId` and calls the
    external `(state, bookId, …)` effects directly. No callback props: routing every handler
    through the page would give the drag path and the button path two different call sites, which
    is exactly what DoD-6 forbids.
- `export const ChapterOrderList = observer(function ChapterOrderList({ state, bookId }: ChapterOrderListProps): ReactElement { … })` — new
  - **The body is UNIMPLEMENTED and THROWS ON RENDER** through a module-private `unimplemented`
    sink. See the red-gate profile below for why the row markup was deliberately NOT relocated by
    this agent.
  - `import { DndContext } from "@dnd-kit/core"` and `import { SortableContext } from "@dnd-kit/sortable"`
    are **real imports at their frozen sites**, consumed by the sink call. That is what makes
    `tsc` and `vite build` resolve, typecheck and bundle both new packages (DoD-11) before a line
    of drag code exists — the build went 7205 → **7211 modules**, which is the two packages
    landing in the `work` chunk.
  - Frozen render contract (full prose in the module docstring, which the coder implements and may
    not widen):
    - **The rows are step 006's, MOVED — not duplicated, not redesigned.** Per chapter: the
      ordinal; the title as `Anchor component={Link} to={`/${bookId}/chapter/${chapter.id}`}`; a
      lifecycle `Badge` whose text **and** `aria-label` carry the readable word, from a
      module-private `{ planned: "Planned", open: "Open", closing: "Closing", closed: "Closed" }`
      map (no exported label map is frozen anywhere in feature 014); a remove `Button` rendered
      **only** when `state.canRemoveChapter(chapter)`, accessible name `Remove "<title>"`,
      disabled while `state.removingChapterId === chapter.id`, calling
      `removeChapter(state, bookId, chapter.id)`; and `state.removeServerErrors[chapter.id]`
      rendered **inside that chapter's row** (DoD-9 · step-006 DoD-7/8/9).
    - **Order rendered:** `state.pendingOrder` resolved against the chapters when it is non-`null`,
      otherwise `state.orderedChapters`. Resolved as a plain `const` in the render body — **no
      third computed is frozen for it**, because the interface intent names exactly two new
      computeds and a `const` derivation is what `ChaptersPage` already does for
      `orderedChapters` / `addServerErrors`.
    - **Move controls, only when `state.canReorder`:** accessible names `Move "<title>" up` and
      `Move "<title>" down` — the name must carry **the chapter and the direction**
      (`getByRole("button", { name: /move .* up/i })` is the spec's query shape; an unlabelled
      icon button is untestable). `disabled={!state.canMoveUp(chapter)}` /
      `disabled={!state.canMoveDown(chapter)}`. Each calls
      `moveChapter(state, bookId, chapter.id, "up" | "down")` and nothing else.
    - **Drag affordance, only when `state.canReorder`:** `DndContext` wrapping a `SortableContext`
      over the rendered ids, with a per-row sortable handle; the drag-end handler produces the new
      **full** id sequence and calls `applyChapterOrder(state, bookId, nextIds)` — the same effect
      the buttons reach through `moveChapter` (DoD-6, DoD-10).
    - **When `state.canReorder` is false: no move control, no `DndContext`, no drag handle, no
      disabled arrows** — a plain ordered list with all row content intact (DoD-4). The hint
      mirrors the server and never replaces it (DoD-5).
    - `@dnd-kit`'s sortable-item and sensor hooks are **library** hooks — calling them directly in
      the row is not a breach of the no-custom-hooks rule (which forbids *authoring* hooks). **Do
      not wrap them in a local hook of our own.** All state stays on `ChaptersPageState`: no
      `useState`, no `useEffect`, no `useCallback` / `useMemo` / `useReducer`, no React context, no
      Mantine `useForm`, and nothing in the drag library's own local state.

Page — `frontend/src/work/pages/ChaptersPage.tsx` (changed; the exported symbol and its zero-prop
shape are **unchanged** — `export const ChaptersPage = observer(function ChaptersPage(): ReactElement`):

- The inline row rendering is **gone**: `renderChapterRow`, the module-private
  `CHAPTER_STATE_LABELS`, the `handleRemove` handler and the `removeChapter` import were removed,
  together with the imports that served only the row (`Link`, `Anchor`, `Badge`, `Paper`, and the
  `ChapterLifecycleState` / `ChapterResponse` type imports). `noUnusedLocals` makes that removal
  mandatory, not cosmetic.
- `<ChapterOrderList state={state} bookId={id} />` now stands where the row `Stack` stood, inside
  the same `listLoading ? … : chapters.length === 0 ? … : …` branch — so the loading branch, the
  "No chapters yet." empty state and the add form are untouched and the component is never handed
  an empty list.
- A `state.reorderError` `Alert` ("Could not reorder the chapters") was added directly under the
  page heading — the list-level reorder surface the intent names, independent of
  `chapterListError`, `addServerErrors` and `removeServerErrors` (DoD-8).
- **Nothing else about the page changed**: the single `useEffect([state])`, the
  `registerContentSubject` / `unregisterContentSubject` pair with no `applyDraft`, the
  `AbortController`, the error branch with its retry, the add form and `handleAddSubmit` are
  byte-identical.

Structural notes that are part of the freeze:

- **`frontend/src/api/chapters.ts` and `frontend/src/types/chapters.d.ts` are UNTOUCHED** — step
  005 already froze `reorderChapters(bookId, body, signal?)` and `ReorderChaptersRequest`
  (`chapter_ids: string[]`); this step calls them and adds nothing to either module.
- **`frontend/src/work/routes.tsx`, `contentSubject.ts`, `subject.ts`, `components/shell/**` are
  UNTOUCHED** — the chapters route, the subject registration and the navigator all already do what
  this step needs.
- No new api function, no new DTO, no third `…ServerErrors` map keyed by row, and no per-chapter
  move endpoint anywhere (D3).

Compile gate: `cd frontend && npm run build` (= `tsc && vite build`) — **clean**, 7211 modules,
built in 7.08s. `npm test` deliberately not run (per the briefing, and this step's spec does not
exist yet); `npm run test:types` covers `tests/`, which is the test-coder's.

Red-gate profile to expect:

- **Every step-007 DoD `[test]` item must be RED.** `ChapterOrderList` throws on render and
  `ChaptersPage` renders it for any non-empty list, so DoD-1..9 all fail at `render()` — including
  DoD-4 (the "no move control, no drag affordance" item) and DoD-9 (the "rows still carry
  everything step 006 rendered" item), which is the whole reason the row markup was **not**
  relocated by this agent. Relocating it would have made both of those pass by construction, and
  DoD-4 is one half of US-033.AC-2.
- The two computeds and the two effects throw as well, so no reorder can reach a plausible
  `"ready"`, no `pendingOrder` can be set and no api call can be made.
- **KNOWN, EXPECTED CONSEQUENCE — step 006's `frontend/tests/work/ChaptersPage.test.tsx` goes RED
  until the step-007 coder lands the move.** Its assertions all render a non-empty list, which now
  routes through the throwing component. This is the same shape as step 001's eight superseded
  registry guards, with one difference: **nothing in the spec needs changing.** It is the
  *implementation* that is missing, not the test — the coder filling `ChapterOrderList` restores
  every one of those assertions, and DoD-9 exists precisely to prove it. **The test-coder must not
  touch that file**, and a red-gate run that reports it as failing is reporting expected state.
- No other pre-existing test should change behaviour: `ChapterOrderList` is new, the state module
  gained only additive symbols, and no other module was opened.

- Caller-compile edits (out of Source-files scope): **None.** `ChaptersPage.tsx` and
  `chaptersPageState.ts` are both inside this step's Source files, `ChapterOrderList.tsx` is new,
  and no existing exported signature changed — `ChaptersPage`'s zero-prop shape and all eight
  step-006 state exports are as they were, so nothing outside the step needed a compile fix.

### Step 008 — frozen interface (2026-07-29)

**The two decisions the plan delegated to this agent are recorded first, with their reasoning.**

#### Delegated decision 1 — the new `EditableRegion` members are `"chapter-sketch"` and `"chapter-own-prompt"`; `WriteRegion` is left ALONE

`frontend/src/work/subject.ts`, as harvested, declared
`EditableRegion = "none" | "whole" | "book-state-notes"` and
`WriteRegion = "whole" | "book-state-notes"` — neither named a sketch or a prompt.

- **`EditableRegion` gains exactly two members**, `"chapter-sketch"` and `"chapter-own-prompt"`,
  following `"book-state-notes"`'s `<subject>-<region>` kebab shape. `own` is load-bearing: decision
  D1 made the chapter system prompt **per-author**, so there is no shared chapter prompt for a region
  to name, and `"chapter-system-prompt"` would have read as one.
- **No `"chapter-text"` member was added**, although the DoD talks about the chapter's "body text".
  On a chapter the body **is** the whole subject — an `open` chapter's existing `"whole"` verdict is
  precisely the body-writable one — so naming the body separately would have forced `open`'s answer to
  change, which DoD-12 forbids ("`open`, `closing` and `closed` keep the answers they give today").
  **DoD-13's body-text write is therefore `checkWritePermission(plannedChapter, "whole")`.**
- **`WriteRegion` is byte-unchanged.** The plan allowed widening it; nothing in this feature justifies
  it. Feature 014 routes **neither** save through the write gate — the sketch's refusal is the
  server's `409` on a non-`planned` chapter (`context.md` → status taxonomy) and the prompt has no
  state gate at all — and `checkWritePermission`'s body (which the step file forbids touching:
  "amend `resolveEditability`'s `"chapter"` branch, and nothing else in the file") compares
  `region === editability.editable`, so a `"chapter-sketch"` write region could only ever be
  **refused**. Vocabulary a gate can only refuse is worse than no vocabulary. Whoever first routes a
  sketch or own-prompt write through the gate adds the member together with the `editableRegions`
  lookup it needs; that is recorded in the `WriteRegion` docstring.
  *Tradeoff accepted:* the gate is momentarily narrower than editability. It is not incoherent —
  `"none"` is already an `EditableRegion` that is not a `WriteRegion` — and no DoD in this step asks
  the gate to permit anything.

#### Delegated decision 2 — `Editability` gains an OPTIONAL `editableRegions?: EditableRegion[]`; `editable` keeps its single-region meaning

```ts
export interface Editability {
  editable: EditableRegion;
  readOnlyReason: string | null;
  editableRegions?: EditableRegion[];   // NEW, optional
}
```

- **`editable` is the WHOLE-SUBJECT verdict** and stays one region. A partially editable subject
  answers `"none"` there — nothing about it is editable wholesale — and enumerates its regions in
  `editableRegions`. The documented invariant: **when `editableRegions` is absent, the editable set is
  `editable === "none" ? [] : [editable]`.**
- **Why optional and additive, not `editable: EditableRegion[]`.** Turning `editable` into an array
  would change the returned object for *every* verdict — `open` → `["whole"]`, Book state →
  `["book-state-notes"]` — which contradicts DoD-12's "keep the answers they give today", breaks
  `codexEntryPageState.ts:isReadOnly` (`this.editability.editable === "none"`, the only consumer in
  `src/`), and would force the test-coder to restructure the codex / Book-state / list cases of
  `frontend/tests/work/subject.test.ts`, which `008.context.md` forbids ("touching only the
  `resolveEditability` chapter cases and the `checkWritePermission` body-text case"). The optional
  field changes **no existing verdict's object shape at all**.
- **Why `editable: "none"` for a `planned` chapter is honest, not a fudge.** `readOnlyReason` on a
  chapter is the reason its **body** is read-only, and the `planned` chapter's body *is* still
  read-only with the string it already carried. `editable: "none"` + that reason is exactly the answer
  the body deserves; `editableRegions` names the two exceptions. It is also what makes DoD-13 hold
  **without `checkWritePermission` being touched**: `"whole" !== "none"`, so the body write is refused
  and carries the planned reason.

#### `frontend/src/work/subject.ts` — changed

- `export type EditableRegion` — **changed** — was `"none" | "whole" | "book-state-notes"`, now
  `"none" | "whole" | "book-state-notes" | "chapter-sketch" | "chapter-own-prompt"`.
- `export interface Editability` — **changed** — `editable: EditableRegion` and
  `readOnlyReason: string | null` untouched; **added** `editableRegions?: EditableRegion[]`.
- `export type WriteRegion` — **unchanged** (`"whole" | "book-state-notes"`); docstring only.
- `export function resolveEditability(subject: LoadedSubject): Editability` — **signature unchanged**;
  the `"chapter"` branch's `planned` case is the one thing that changes, and it is **UNIMPLEMENTED**.
  The verdict the coder must return, exactly:

  ```ts
  {
    editable: "none",
    readOnlyReason:
      "This chapter is still planned and cannot be edited until it is opened for writing.",
    editableRegions: ["chapter-sketch", "chapter-own-prompt"],
  }
  ```

  The `readOnlyReason` string is the one the branch **already carried**, verbatim — it is the body
  text's reason and it is copy the author reads. The skeleton leaves the branch returning today's
  pre-amendment object (preserved behaviour) **without** `editableRegions` (the new, unimplemented
  half), with an in-file `SKELETON (014/008)` block spelling the above out.
- `open` / `closing` / `closed` and the `codex-entry`, `book-state` and every list case are
  **byte-untouched**, their reason strings included.
- `export function checkWritePermission(subject, region): WriteDecision` — **signature and body
  byte-untouched.** DoD-13 is satisfied structurally by the verdict above.

#### `frontend/src/work/pages/chapterPageState.ts` — new module

Observable fields declarative and complete; **every `get` computed and every external effect body is
UNIMPLEMENTED** through a module-private `unimplemented(fn, ..._args): never` sink carrying the
`(skeleton 014/008)` marker (it also consumes the frozen parameter lists so they satisfy
`noUnusedParameters`). The coder adds the `runInAction` / `chaptersApi` / `ApiError` /
`UpdateChapterSketchRequest` / `UpdateChapterAuthorPromptRequest` imports and **deletes the sink**.

- `export class ChapterPageState` — new — `constructor()` calls `makeAutoObservable(this)`; **no
  effectful methods, no setters**. Observable fields, in declaration order — this is
  `bookStatePageState.ts` copied field-for-field with a chapter id added, and the second editor:
  - `chapter: ChapterResponse | null = null` · `chapterStatus: "idle" | "loading" | "ready" | "error" = "idle"` · `chapterError: string | null = null`
  - `sketchDraft = ""`
  - `sketchServerErrors: Record<string, string> = {}` — keyed by **field name** (`sketch`) plus the
    general `form` key. **No `clientErrors`, no `errors` union** (`021`'s shape; every string
    including `""` is a valid sketch).
  - `sketchSubmitStatus: "idle" | "loading" | "ready" | "error" = "idle"`
  - `systemPrompt: ChapterAuthorPromptResponse | null = null` · `systemPromptStatus: "idle" | "loading" | "ready" | "error" = "idle"` · `systemPromptError: string | null = null`
  - `systemPromptDraft = ""`
  - `systemPromptServerErrors: Record<string, string> = {}` — keyed by `system_prompt` plus `form`.
    Same shape, same absence of a client layer.
  - `systemPromptSubmitStatus: "idle" | "loading" | "ready" | "error" = "idle"`
  - **The state owns NEITHER id.** Both arrive as arguments on every effect (the plan fixes the
    signature), and the page — which has them from `useParams` — builds the content-pane subject. A
    deliberate departure from `codexEntryPageState.ts`, whose constructor stores its ids only because
    its restore-buffer key needs them; this page has no buffer.
  - **No `text` / body field, no buffer key, no `baseVersion`, no reconciliation field, no `409`
    field, no delete state.**
- Pure `get` computeds (all seven bodies throw):
  - `get lifecycleStateLabel(): string` — new — the lifecycle word capitalised: `planned` → `"Planned"`,
    `open` → `"Open"`, `closing` → `"Closing"`, `closed` → `"Closed"`; `""` before the first
    successful load. **Word-for-word what `ChapterOrderList`'s state badge already renders** (step 006's
    freeze), so the two surfaces cannot diverge, and it is text rather than a colour (DoD-1).
  - `get canEditSketch(): boolean` — new — `true` **only** when the loaded chapter's `state` is
    `"planned"`; `false` before the first load, on a failed load, and for `open` / `closing` /
    `closed` (DoD-3). A client affordance that never substitutes for the server's `409` (DoD-4).
  - `get sketchDisabledReason(): string | null` — new — `null` **exactly when** `canEditSketch` is
    `true`, a non-empty author-facing sentence otherwise. DoD-3's "with a stated reason" is
    **readable text**, never a visual state. Wording contract: `closing` / `closed` reuse
    `work/subject.ts:resolveEditability`'s reason **verbatim** (that module owns the chapter's
    read-only copy — the `codexEntryPageState.ts` precedent); `open` has no such reason to reuse (an
    `open` chapter is editable *whole*, in its body), so that one sentence is this page's own and must
    say the sketch is fixed once the chapter has been opened for writing.
  - `get sketchDirty(): boolean` — new — draft `!==` the loaded chapter's `sketch`; a not-yet-loaded
    chapter compares as `""`.
  - `get canSaveSketch(): boolean` — new — chapter loaded **and** `canEditSketch` **and** `sketchDirty`
    **and** `sketchSubmitStatus !== "loading"` (DoD-5). **No emptiness check** — `""` is a legal save.
  - `get systemPromptDirty(): boolean` — new — `bookStatePageState.systemPromptDirty` verbatim.
  - `get canSaveSystemPrompt(): boolean` — new — `systemPromptStatus === "ready"` **and**
    `systemPromptSubmitStatus !== "loading"` **and** `systemPromptDirty`;
    `bookStatePageState.canSaveSystemPrompt` verbatim. **No emptiness check** (DoD-9) and
    **NO lifecycle-state gate** — the prompt is writable on a chapter in every state, `open` and
    `closed` included (DoD-10).
- External effect functions — `(state, bookId, chapterId, signal?)`, `runInAction`, no optimistic
  mutation, re-seed from the server (all four bodies throw). Ordered load / save, chapter then prompt:
  - `export async function loadChapter(state: ChapterPageState, bookId: string, chapterId: string, signal?: AbortSignal): Promise<void>` — new
    - `chaptersApi.getChapter`, the `bookStatePageState.ts:loadBookState` shape verbatim
      (loading → abort guard → `ApiError` → `chapterError` + `"error"`, else rethrow), and it
      **seeds `sketchDraft` from `chapter.sketch`**. Also the retry path behind the chapter error
      branch. Touches nothing in the prompt trio (DoD-11).
  - `export async function saveSketch(state: ChapterPageState, bookId: string, chapterId: string, signal?: AbortSignal): Promise<void>` — new
    - Body `{ sketch: state.sketchDraft }` read off the state verbatim — no trimming, no emptiness
      check, **no `expected_version`** (D6). Calls `chaptersApi.updateChapterSketch`, then **re-seeds
      BOTH `chapter` and `sketchDraft` from the RESPONSE body** (DoD-2 — the editor shows what the
      server returned). On `ApiError`: message into `sketchServerErrors` (4xx → `sketch`, 5xx →
      `form`), `sketchSubmitStatus = "error"`, **`sketchDraft` untouched** (DoD-4).
    - Named `saveSketch`, not `updateChapterSketch`: the page imports these four names bare, and a
      bare `updateChapterSketch` would read as `api/chapters.ts`'s function.
  - `export async function loadSystemPrompt(state: ChapterPageState, bookId: string, chapterId: string, signal?: AbortSignal): Promise<void>` — new
    - `chaptersApi.getOwnChapterSystemPrompt`; seeds `systemPromptDraft` from `prompt.system_prompt`.
      An empty prompt is a **normal loaded value, never an error state** (DoD-7). Touches nothing in
      the chapter trio (DoD-11).
  - `export async function saveSystemPrompt(state: ChapterPageState, bookId: string, chapterId: string, signal?: AbortSignal): Promise<void>` — new
    - Body `{ system_prompt: state.systemPromptDraft }`; `chaptersApi.updateOwnChapterSystemPrompt`;
      re-seeds both from the response (DoD-8). On `ApiError`: message into `systemPromptServerErrors`
      (4xx → `system_prompt`, 5xx → `form`), `systemPromptSubmitStatus = "error"`,
      **`systemPromptDraft` untouched**. No `409` path.
    - The prompt pair keeps `bookStatePageState.ts`'s names **verbatim** (`loadSystemPrompt` /
      `saveSystemPrompt`) — `008.context.md` says "copy that field-for-field with a chapter id
      added", and the two modules are never imported into one file, so there is no collision to
      disambiguate (contrast the *api* layer, where step 005 added the `Chapter` qualifier precisely
      because both levels can be imported by name into one module).
  - The four are separate functions precisely so the two trios load and fail independently (DoD-11).

#### `frontend/src/work/pages/ChapterPage.tsx` — new module

- `export const ChapterPage = observer(function ChapterPage(): ReactElement { … })` — new — **zero
  props**; the body is UNIMPLEMENTED and **throws on render** through a module-private sink.
- Frozen contract for the coder (full prose in the module docstring, summarised here):
  - One `useState(() => new ChapterPageState())`, `useParams()` for `bookId` **and** `id`, and
    **exactly ONE** page-level `useEffect([state])` spinning a single `AbortController` that starts
    **both** `loadChapter(...)` and `loadSystemPrompt(...)` and aborts both on unmount.
  - The same effect builds a stable
    `const source: ContentSubjectSource = () => ({ kind: "chapter", entityId: id, chapterState: state.chapter?.state })`
    and calls `registerContentSubject(source)` with **NO `applyDraft`** — `CanvasField` is
    `"name" | "body"`, both codex fields, so neither the sketch nor the prompt is a canvas region —
    then `unregisterContentSubject(source)` before `ctrl.abort()` in the cleanup (DoD-14). The source
    is a **closure, not a `get contentSubject` on the state**, because the state owns neither id (see
    above); `ChaptersPage`'s inline source is the precedent. `contentSubject.ts` is **called, never
    changed**. The `ChapterResponse.state` → `LoadedSubject.chapterState` conversion is the site step
    005's naming decision 1 anticipated: `ChapterLifecycleState` and `ChapterState` are structurally
    identical, so it needs no cast.
  - Renders: title, ordinal and `state.lifecycleStateLabel` (DoD-1); **each trio's own** loading and
    error branch, neither nested inside the other's success path (DoD-11); a **sketch section** —
    labelled multi-line editor bound to `sketchDraft`, `disabled={!state.canEditSketch}`, save gated on
    `canSaveSketch` and rendered only where a save is possible (DoD-3 — a non-`planned` chapter
    "offers no save"), `sketchServerErrors` surface (DoD-4), and `state.sketchDisabledReason` rendered
    as readable text whenever it is non-null; a **system-prompt section** — labelled multi-line editor
    bound to `systemPromptDraft` with **no disabled state in any lifecycle state** (DoD-10), save gated
    on `canSaveSystemPrompt`, `systemPromptServerErrors` surface, and **one** line of copy saying the
    prompt is the caller's **own** and is not shared with co-authors. That line must **not** promise
    the prompt affects the assistant today (D7 — composition is `015`'s).
  - **Must NOT render**: the chapter's body text in any form (`015`'s; `ChapterResponse` does not carry
    it), any delete control (DoD-9), any restore-buffer or divergence surface, any state-transition
    control.
  - Both editors reachable by **accessible label**; every state and reason is readable text — the
    specs query by role or label only.
  - `observer` applied. Handlers are inner functions closing over the state; no `useCallback` /
    `useMemo` / `useReducer`, no custom `useX` hook, no React context, no Mantine `useForm`.

#### `frontend/src/work/routes.tsx` — changed (**exactly one element plus its import**)

- `function ChapterItemRoute()` — **changed** — was
  `return <SubjectPlaceholderPage key={id} heading="Chapter" owner="014.chapter-skeleton" />;`, now
  `return <ChapterPage key={id} />;`. **The wrapper and its `key={id}` are kept** — they already
  existed and they are what makes DoD-14's fresh-state-on-`:id`-change true.
- `import { ChapterPage } from "./pages/ChapterPage";` — added between the `BookStatePage` and
  `ChaptersPage` imports.
- **`<Route path="chapter/:id" element={<ChapterItemRoute />} />` itself is unchanged**, step 006's
  `chapters` line is untouched, and no other child route changed. `SubjectPlaceholderPage` is still
  imported and still used by `variants` and `variants/:chapterId`.

#### Structural notes that are part of the freeze

- **`bookStatePageState.ts` and `BookStatePage.tsx` are byte-untouched.** The two pages share neither
  a state class nor a component; `021`'s book-level editor ships exactly as it was (`008.context.md`).
- **`frontend/src/work/contentSubject.ts` is byte-untouched** — this step calls it. `ContentSubject`
  already extends `LoadedSubject`, so the widened `EditableRegion` reaches it for free.
- **`frontend/src/api/chapters.ts` and `frontend/src/types/chapters.d.ts` gain nothing** — step 005
  already froze `getChapter`, `updateChapterSketch`, `getOwnChapterSystemPrompt` and
  `updateOwnChapterSystemPrompt` and every DTO this page needs.
- **`frontend/src/work/components/**` gains no file.** The page renders a header, two trio branches
  and two editors; nothing here is shared with the list surface.
- No exported label map for the lifecycle states was frozen (step 006 made the same call); the wording
  is constrained on `lifecycleStateLabel` above so both surfaces agree.

Compile gate: `cd frontend && npm run build` (= `tsc && vite build`) — **clean**, 7212 modules, built
in 6.69s. `npm test` deliberately **not** run (per the briefing); `npm run test:types` covers `tests/`,
which is the test-coder's.

Red-gate profile to expect:

- **DoD-1 … DoD-11 and DoD-14 must all be RED.** `ChapterPage` throws during render, so every page
  assertion fails at `render()` — including DoD-14, which reaches the page through the route. The
  route registration itself is declarative and arrives complete: a test asserting only that
  `/work/:bookId/chapter/:id` *no longer renders the placeholder* would pass on the absence alone and
  is **not** evidence the step is done; DoD-1's real content cannot pass.
- The seven computeds and the four effects throw, so no trio can reach a plausible `"ready"`, no draft
  can seed or re-seed, and no api call can be made.
- **DoD-12 must be RED** on the `editableRegions` half: `resolveEditability` on a `planned` chapter
  returns today's object, which carries no `editableRegions` at all. Its `open` / `closing` / `closed`
  half is a **regression guard** and is green by construction — that is the point of the item.
- **DoD-13 is a REGRESSION GUARD and will be GREEN at the red gate.** It asserts that
  `checkWritePermission(plannedChapter, "whole")` still refuses, which is true before and after the
  amendment — deliberately so: the whole design of decision 2 above is to make the body-write refusal
  survive *without* touching the gate. A red-gate run reporting DoD-13 as passing is reporting
  expected state, not a missing red.
- **KNOWN, EXPECTED CONSEQUENCE — the existing `frontend/tests/work/subject.test.ts` will need its
  `planned` case updated by the test-coder** (`008.context.md` authorises exactly that: "touching only
  the `resolveEditability` chapter cases and the `checkWritePermission` body-text case"). Nothing else
  in that spec changes: no other verdict's object shape moved. `npm run test:types` was not run here —
  it covers `tests/`, which is the test-coder's.
- No other pre-existing test should change behaviour: both page modules are new, `routes.tsx`'s only
  change swaps one placeholder element that no shipped spec asserts on, and `subject.ts`'s change is
  additive at the type level.

- Caller-compile edits (out of Source-files scope): **None.** `Editability` gained an **optional**
  field and `EditableRegion` was **widened**, so the only `src/` consumer of either —
  `frontend/src/work/pages/codexEntryPageState.ts` (`get editability`, `get isReadOnly` reading
  `editability.editable === "none"`) — compiles and behaves unchanged. Both new modules are new and
  `routes.tsx` is inside this step's Source files.

## Tests

### Step 001 — tests (2026-07-29)

- `backend/tests/db/test_chapter_author_prompts.py` — covers DoD-1, DoD-2, DoD-3, DoD-4, DoD-5 —
  the prompt `db/` module: intact `(chapter, user)` round trip incl. `""`, cross-pair misses,
  the DATABASE-raised unique-constraint refusal, per-pair row independence, and `update`
  reflecting stored state.
- `backend/tests/db/test_chapters.py` — covers DoD-9, DoD-10, DoD-11 — `db/chapters.py`'s new
  `update` (sketch + ordinal + title persist, repeatable) and `delete` (removes and reports one;
  a missing / already-deleted id reports nothing removed and raises nothing).
- `backend/tests/test_data_domain_chapter_author_prompts.py` — covers DoD-6, DoD-7, DoD-8, DoD-12 —
  the table present and queryable after the ordinary `init_db()` path with a drift-clean report,
  the codec pair round trip (string ids, `""`, null timestamps, legacy numeric ids), exactly one
  `TABLE_REGISTRY` entry after `book_author_prompts`, and the untouched `chapters` codec still
  round-tripping `system_prompt`.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓,
  DoD-10 ✓, DoD-11 ✓, DoD-12 ✓
- Sanctioned scope extension (orchestrator-approved, mirroring feature `021` step 001): the
  superseded `TABLE_REGISTRY` order guards took a one-line `"chapter_author_prompts"` insert
  between `book_author_prompts` and `chapters`, with no assertion logic rewritten, in
  `backend/tests/test_data_domain_{assistant_core,assistant_links,book,chapter,chapter_changes,chat,codex,continuity}.py`.

### Step 002 — tests (2026-07-29)

- `backend/tests/services/test_chapters.py` — covers DoD-1 … DoD-14 — the chapter service's
  whole decision surface at the service layer: `BookAccess` built directly (frozen dataclass),
  users / books / chapters seeded through the sibling `db/` modules with the `db` fixture, no
  route, no client, no JWT, no network.
  - DoD-1 — `add_chapter` yields a `planned` chapter with the submitted sketch (incl. `""`) and a
    following `list_chapters` includes it.
  - DoD-2 — append is **next ordinal after the current highest**: 1 on an empty book, 8 after a
    lone chapter at 7, 4 after the middle of three was removed (the gap survives — never count+1),
    and 6 regardless of creation order.
  - DoD-3 — a co-author adds / edits a sketch / removes; a reader and a non-member are refused on
    all three by `BookAuthorizationError` with nothing written.
  - DoD-4 — the sketch lands, `version` is unchanged, `UpdateChapterSketchRequest` has exactly one
    field (no version token), and the second of two sequential edits wins.
  - DoD-5 — `open` / `closing` / `closed` refused with `not_planned`; the stored sketch and state
    are untouched.
  - DoD-6 — a `planned` chapter is removed, gone from `list_chapters` and from the db; siblings
    survive; the call returns `None`.
  - DoD-7 — `open` / `closing` / `closed` removal refused with `not_planned`; the chapter survives.
  - DoD-8 — reorder rewrites ordinals to `1..N` in the submitted order, in the returned envelope,
    in a following `list_chapters` and in the stored rows; a gapped set normalizes.
  - DoD-9 — a co-author's reorder raises `BookAuthorizationError` and no ordinal moves.
  - DoD-10 — omitted / unknown / duplicated / foreign-book ids each raise
    `invalid_reorder_set` and leave **every** ordinal (both books') exactly as it was.
  - DoD-11 — reorder succeeds with an `open` chapter present; its `state`, `text` and `version`
    are unchanged and only `ordinal` moved (D5).
  - DoD-12 — another book's chapter is `not_found` on `get_chapter`, `update_sketch` and
    `remove_chapter`, for an owner **and** for a co-author (both hold the capability, so the
    refusal cannot be authorization); an unknown id likewise.
  - DoD-13 — ordering by ordinal ascending and scoped to the access context's book;
    `can_reorder` true for the owner, false for a co-author, and false for a reader **only if**
    the reader reaches the list (whether they do is deliberately not asserted — `002.context.md`).
  - DoD-14 — `ChapterResponse.model_fields` equals the wire contract set exactly (no `text`, no
    `summary`, no `summary_status`); every response from all six entry points is a
    `ChapterResponse` / `ChapterListResponse`, never a `Chapter`, with `id` and `book_id` as `str`.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓,
  DoD-10 ✓, DoD-11 ✓, DoD-12 ✓, DoD-13 ✓, DoD-14 ✓
- Two tests are synchronous and DTO-shape-only (`UpdateChapterSketchRequest` field set,
  `ChapterResponse` field set) — the skeleton's red-gate profile already records that the five DTOs
  are complete by construction, so those two are expected GREEN pre-implementation and are not
  evidence the step is done.

### Step 003 — tests (2026-07-29)

- `backend/tests/routes/test_chapters.py` — covers DoD-1 … DoD-17 — the six-handler
  `/api/books/{book_id}/chapters` family end to end against the real `app.main.app` over
  `httpx.ASGITransport`, with real JWT auth (seeded user rows + minted tokens) and the
  `_now` / `_auth_header` / `_seed_user` / `_seed_author` / `_create_book` / `_add_co_author`
  helpers copied per-file from `tests/routes/test_book_settings.py`.
  - DoD-1 — `GET` collection → `200`, ordinal-ascending (seeded deliberately out of order),
    `id` / `book_id` as strings, no `text`, field set == the wire contract, scoped to the
    addressed book.
  - DoD-2 (US-032.AC-1, UC-031) — `POST` → **`201`**, `planned`, submitted sketch; a following
    `GET` lists it **appended last**.
  - DoD-3 — blank title (`""` and whitespace-only) → `422` with an empty collection after;
    an empty **sketch** → `201`.
  - DoD-4 (US-034.AC-1) — `PATCH` on `planned` → `200` with the new sketch; a following
    `GET` on that chapter returns the same value.
  - DoD-5 (US-034.AC-2) — `PATCH` on `open` / `closing` / `closed` → **`409`**, stored sketch
    unchanged (state forced straight through `app.db.chapters`).
  - DoD-6 (US-035.AC-1) — `DELETE` on `planned` → **`204`** with an empty body; gone from the
    collection, sibling survives.
  - DoD-7 (US-035.AC-2) — `DELETE` on `open` / `closing` / `closed` → **`409`**, chapter still
    stored and still listed.
  - DoD-8 (US-033.AC-1) — owner `PUT /order` → `200`; the returned envelope and a following
    `GET` carry the submitted order, ordinals rewritten `1..N`.
  - DoD-9 (US-033.AC-2) — co-author `PUT /order` → **`403`**, stored ordinals and listed order
    unchanged.
  - DoD-10 — omitted / unknown / repeated / another book's id → **`400`** (not `422`), with
    **both** books' stored ordinals and the listed order byte-for-byte unchanged.
  - DoD-11 — a co-author `POST`s, `PATCH`es and `DELETE`s successfully; a logged-in non-member
    of a **public** book gets `403` on all three and changes nothing.
  - DoD-12 — a stranger to a **private** book gets `404` from all six routes (parameterised).
  - DoD-13 — no token → `401` from all six routes (parameterised, against a public book so the
    refusal cannot be existence hiding).
  - DoD-14 — another book's chapter → `404` on read / sketch / delete, with the caller a member
    of **both** books (so it is provably book-scoping, not authorization) and the foreign
    chapter untouched in its own book.
  - DoD-15 — `can_reorder` `true` for the owner, `false` for a co-author, same book.
  - DoD-16 — `PUT /order` answers `200` with the **list envelope** and applies the order, while
    `GET …/chapters/order` resolves "order" as an unknown chapter id → `404`; the literal is
    not shadowed.
  - DoD-17 — missing-field and wrong-type bodies on `POST` / `PATCH` / `PUT /order` → `422`
    with no chapter added, no ordinal moved and no sketch rewritten.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓,
  DoD-10 ✓, DoD-11 ✓, DoD-12 ✓, DoD-13 ✓, DoD-14 ✓, DoD-15 ✓, DoD-16 ✓, DoD-17 ✓
- Harness note: the `db` fixture is deliberately **not** requested anywhere in this module.
  Both it and `http_client` initialize the *process-global* engine, so requesting both would
  repoint the engine away from the one the app's lifespan built. The two places that must
  reach past the routes — forcing a non-`planned` state (DoD-5, DoD-7) and reading stored
  ordinals — call `app.db.chapters` directly against the app's own engine, exactly as the
  inherited `_add_co_author` helper already calls `app.db.book_members`.

### Step 004 — tests (2026-07-29)

- `backend/tests/services/test_chapter_author_prompts.py` — covers DoD-2, DoD-4, DoD-5, DoD-6,
  DoD-7, DoD-8 — the prompt service's row-ownership and storage behaviour at the service layer:
  `BookAccess` built directly (frozen dataclass), users / books / chapters seeded through the
  sibling `db/` modules with the `db` fixture, no route, no client, no JWT, no network.
  - DoD-2 (service half) — a member with no row reads `""` + `None` and the read creates nothing.
  - DoD-4 — an owner and a co-author hold independent prompts on the **same** chapter; each reads
    only their own, and the owner's rewrite leaves the co-author's row (text + both timestamps)
    byte-identical.
  - DoD-5 — one author, two chapters of one book: writing one leaves the other's row untouched and
    invents no row on an unwritten chapter.
  - DoD-6 — the first write stamps **both** timestamps; a second write updates in place — same
    surrogate id, exactly **one** row for the pair, `created_at` preserved against a backdated
    anchor, `modified_at` advanced past it.
  - DoD-7 — `""` accepted as a first write and as a clear, read back empty, the row surviving;
    and "a row holding `\"\"`" stays distinguishable from "no row" — same `system_prompt`, a real
    `modified_at` versus `null`.
  - DoD-8 — read **and** write succeed on `open` / `closing` / `closed` chapters (parameterised,
    state written straight through `app.db.chapters`), for an owner and for a co-author, with the
    chapter's own `state` unchanged by the prompt write.
- `backend/tests/routes/test_chapter_author_prompts.py` — covers DoD-1, DoD-3, DoD-9 … DoD-15 —
  the `GET`/`PUT …/chapters/{chapter_id}/system-prompt` pair end to end against the real
  `app.main.app` over `httpx.ASGITransport`, with real JWT auth and the
  `_now` / `_auth_header` / `_seed_user` / `_seed_author` / `_create_book` / `_add_co_author`
  helpers copied per-file from `tests/routes/test_book_settings.py`.
  - DoD-1 — `GET` → `200` with the caller's own stored text and a string `chapter_id`, while a
    co-author's `GET` on the same URL answers with theirs.
  - DoD-2 (HTTP half) — `GET` with no row → **`200`** / `""` / `null` for owner and co-author,
    never `404`.
  - DoD-3 — `PUT` stores and echoes the text, a following `GET` agrees, and the update path
    answers `200` (not `201`) with the later value winning.
  - DoD-9 — a logged-in non-member of a **public** book → `403` on both verbs, no row stored and
    the owner's prompt still unwritten.
  - DoD-10 — a stranger to a **private** book → `404` on both verbs, nothing stored.
  - DoD-11 — no token → `401` on both verbs (asserted against a **public** book, so the refusal
    cannot be existence hiding).
  - DoD-12 — an unknown id, and a chapter of **another book** addressed through this one → `404`
    on both verbs with the caller a member of both books; nothing stored, and the foreign chapter
    still promptless in its own book.
  - DoD-13 — both response bodies carry exactly `{chapter_id, system_prompt, modified_at}` and no
    user-ish key; the request DTO has one field; a `PUT` body carrying an extra `user_id` writes
    only the caller's row and leaves the other member's intact.
  - DoD-14 — `DELETE` and `POST` on the path → **`405`** (framework), stored prompt surviving.
  - DoD-15 — a `PUT` body missing the field, and one naming the wrong field → `422`, with nothing
    stored.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓,
  DoD-10 ✓, DoD-11 ✓, DoD-12 ✓, DoD-13 ✓, DoD-14 ✓, DoD-15 ✓, DoD-16 [manual/live, no test]
- Harness note: the route module deliberately never requests the `db` fixture — it and
  `http_client` both initialize the process-global engine. The two places that reach past the
  routes (seeding chapters, reading stored prompt rows) call `app.db.chapters` /
  `app.db.chapter_author_prompts` directly against the app's own engine, as the inherited
  `_add_co_author` helper does.

### Step 005 — tests (2026-07-29)

- `frontend/tests/user/BookHubPage.test.tsx` — covers DoD-1, DoD-2, DoD-3, DoD-4, DoD-5, DoD-6 —
  the read-only Shell book hub. Both api modules mocked module-factory form (`api/chapters` a
  plain factory over all eight frozen exports; `api/books` an `importOriginal` spread with
  `vi.fn()` overrides so no export can be stripped and no call can escape). `ApiError` real from
  `api/client`. Queries are by role or text only — no test ids, nothing asserted about colour.
  - DoD-1 — the book title renders as the page heading, both loads address the `:bookId` in the
    URL, every chapter is listed with the per-chapter links in ordinal document order, and each
    chapter's row shows its own lifecycle state as readable text
    (`planned` / `open` / `closing` / `closed`).
  - DoD-2 — an empty `chapters` array renders an empty state: the heading still renders, no
    chapter link exists, an "no chapters yet"-shaped line is on screen, and nothing
    failure-shaped or retry-shaped is (an empty book is a successful load).
  - DoD-3 — negative, by role: no `button` and no `menuitem` named add / new / create / remove /
    delete / reorder / move / up / down / edit / rename / sketch / save / drag; no link carrying
    such a name other than the sanctioned `/work/…` ways out; and no `textbox` / `searchbox` /
    `combobox` / `listbox` / `checkbox` / `radio` / `switch` / `spinbutton` / `slider` role
    anywhere, with no enabled, writable input / textarea / select / contenteditable in fact.
  - DoD-4 — a link to `/work/:bookId` and one to `/work/:bookId/chapter/:chapterId` per chapter,
    asserted on the exact `href`s, all of them plain anchors (separate Vite entry).
  - DoD-5 — two cases, one per direction: a rejected `listChapters` renders a failure branch with
    no chapter links while the book heading and the book work-link stay whole; a rejected
    `getBookDetail` renders a failure branch with no title heading while all four chapters still
    list in full.
  - DoD-6 — the REAL `UserRoutes` table is mounted at `/books/<id>` and navigated to a second
    book: the second book's heading and chapter arrive, both api calls are re-issued for the new
    id, and none of the first book's chapters or its heading survives the change.
- `frontend/tests/user/chaptersApi.test.ts` — covers DoD-7, DoD-8, DoD-9 — the api module itself,
  so `request` in `../../src/api/client` is mocked (never `fetch`, never the chapters module) via
  an `importOriginal` spread that keeps the real `ApiError`; the url, method, body and forwarded
  signal handed to `request` are the assertions.
  - DoD-7 — one case per frozen function, each pinning the path and method from `context.md` →
    "Endpoints": `GET`/`POST` on `…/chapters`, `GET`/`PATCH`/`DELETE` on `…/chapters/{id}`, `PUT`
    on `…/chapters/order` (not a `/{chapter_id}` path), `GET`/`PUT` on
    `…/chapters/{id}/system-prompt`; each forwards the caller's `AbortSignal`, an omitted signal
    stays undefined, the book id in the path is the one passed, and an `ApiError` from the
    wrapper propagates unchanged with its status.
  - DoD-8 — `listChapters` resolves to the ENVELOPE, not a bare array: `can_reorder` survives
    both `true` and `false`, `chapters` is the array beside it, and an empty book still resolves
    to an envelope. `reorderChapters` likewise answers the envelope.
  - DoD-9 — `removeChapter` resolves (to `undefined`) when the wrapper resolves with no value at
    all, sends no body, needs no signal, and still propagates a refusal rather than swallowing it
    into an empty resolution.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓,
  DoD-10 [manual/live, no test]
- Harness note: `globals: false`, so every primitive is imported from `"vitest"`; `restoreMocks`
  wipes implementations, so `beforeEach` re-arms every `vi.mocked(...)`. The page spec uses a
  local `renderPage(route)` wrapping `renderWithProviders` with a
  `<Routes><Route path="/books/:bookId" …/></Routes>` shim for DoD-1..5, and mounts the real
  `UserRoutes` under its own `MemoryRouter` for DoD-6 — the route's `:bookId` keying is the thing
  under test there, so a hand-keyed shim would have proved nothing.

### Step 006 — tests (2026-07-29)

- `frontend/tests/work/ChaptersPage.test.tsx` — covers DoD-1 … DoD-12 — the working
  page's chapter list (add + remove). `api/chapters` mocked module-factory form over
  **all eight** frozen exports (the five this step never calls included, so a later
  step's page cannot fail for the wrong reason); `api/books` + `api/chats` likewise, so
  DoD-11's whole-`WorkRoutes` mount resolves locally. `ApiError` is the REAL class from
  `api/client`. The mock is a small **server double** — `listChapters` always answers the
  current server list as the whole envelope, `createChapter` appends with the next
  ordinal and hands the new row back **first** in the array, `removeChapter` deletes —
  so any legal re-seed strategy (create response + reload, or reload alone) satisfies the
  assertions while an optimistic splice does not. Queries are by role or label only.
  - DoD-1 — the server answers in scrambled array order; the page loads for the routed
    `:bookId` and renders all four chapters in **ordinal** document order, each linking to
    `/chapter/<id>`, each row reading its **own** lifecycle word (`Planned` / `Open` /
    `Closing` / `Closed`) and not a neighbour's.
  - DoD-2 — an empty `chapters` array is a successful load: an empty-state line, no rows,
    nothing failure-shaped, no retry — and a **usable** add form (both fields enabled and
    accepting text, the submit control opening once a title is typed).
  - DoD-3 (US-032.AC-1) — two cases. Page: submitting sends exactly
    `{title, sketch}` for the routed book, and the chapter then shown carries the
    **server's** title and **server-assigned id**, is `planned`, and the typed title is
    nowhere on screen. State: after `addChapter`, `orderedChapters`' last entry is the
    server row — server id, `state === "planned"`, `sketch ===` the submitted sketch (the
    list does not render `sketch`, so the state layer is where that half is observable),
    server title. An optimistic splice fails both halves.
  - DoD-4 (UC-031) — the server returns the new chapter **first** in the array with the
    highest ordinal; it must still render **last**, after both pre-existing chapters.
  - DoD-5 — two cases: the submit control is unavailable while the title is blank, while
    only a sketch is filled, and for `"   "` / `"\t \n "` (whitespace-only is not filled),
    opens on a real title and closes again when emptied; and it is unavailable while a
    create that never settles is in flight, with exactly one call issued.
  - DoD-6 — two cases: a refused add (real `ApiError`) puts the **server's own message**
    on screen, leaves **both** drafts byte-identical and adds nothing to the list; and a
    successful add clears both drafts.
  - DoD-7 (US-035.AC-1) — removing a `planned` chapter calls `removeChapter(bookId,
    chapterId)` and that chapter is gone from the rendered list while its neighbour
    survives.
  - DoD-8 (US-035.AC-2, client affordance) — with all four states on screen, the
    `planned` chapter **does** offer a remove control (so the negatives are not vacuous)
    and `open` / `closing` / `closed` offer none, by accessible name **and** by any
    remove-shaped button inside their row.
  - DoD-9 (US-035.AC-2, server authority) — both chapters look `planned` to the client,
    so the affordance is offered and the **server** refuses (`409`, real `ApiError`): the
    message is rendered beside the chapter it concerns — every leaf element actually
    showing it is inside that chapter's row, the neighbour's row says nothing, so a
    page-level banner fails — and both chapters stay in the list.
  - DoD-10 — a rejected load renders a failure-shaped branch with a retry control, no
    title/sketch field, no submit and no rows; clicking retry re-loads and the page
    recovers with the add form back.
  - DoD-11 — the real `WorkRoutes` table at `/bk-1/chapters`: inside the `main` landmark
    the chapters load fires for the routed id, a chapter link and the add form's title
    field render, and no `014.chapter-skeleton` placeholder survives in the pane.
  - DoD-12 — nothing is registered before mount; on mount `currentContentSubject()` is
    `{kind: "chapters"}` with no `entityId` (a list names no entity), it survives the load
    settling, and unmount clears it to `null`.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓,
  DoD-9 ✓, DoD-10 ✓, DoD-11 ✓, DoD-12 ✓, DoD-13 [manual/live, no test]
- **Sanctioned scope extension (orchestrator-approved, mirroring feature `014` step 001's
  `TABLE_REGISTRY` order guards):** `frontend/tests/work/subjectRoutes.test.tsx`
  (010.working-page / 004, DoD-5) parameterised `["/bk-1/chapters",
  /014\.chapter-skeleton/]` and asserted the **placeholder** renders at that route —
  precisely what step 006's DoD-11 removes. That single `LIST_ROUTES` row was deleted and
  nothing else: no assertion logic rewritten, no other row touched, and the
  `/bk-1/chapter/ch-1` row in `ITEM_ROUTES` deliberately left in place (that placeholder
  is step 008's and is still correct today). The step-006 skeleton record's "no
  pre-existing test should change behaviour" line did not account for this row.
- Harness note: `globals: false`, so every primitive is imported from `"vitest"`;
  `restoreMocks` wipes implementations, so `beforeEach` re-arms the whole server double
  and resets the module-level content-subject registry through the frozen
  register/unregister pair. A chapter's "row" is located structure-agnostically (the
  largest ancestor of its link mentioning no other chapter), never by DOM shape or a test
  id, so step 007 may re-shape the rows without touching these assertions.

### Step 007 — tests (2026-07-29)

- `frontend/tests/work/ChaptersPageReorder.test.tsx` — covers DoD-1 … DoD-9 — reordering the
  skeleton through the ↑/↓ controls (D3 fixes the buttons as the tested path). A **new** spec
  file, deliberately separate from step 006's `ChaptersPage.test.tsx`, which is untouched.
  `api/chapters` mocked module-factory form over **all eight** frozen exports; `ApiError` is the
  REAL class from `api/client`. The mock is a small **server double** — `listChapters` answers
  the current server list as the whole envelope, `reorderChapters` applies the submitted
  sequence and rewrites ordinals `1..N` — so either legal re-seed strategy (the returned
  envelope, or a fresh load) satisfies the assertions while a local splice does not. Queries are
  by role or label only; a move control is reached by its accessible name, which must carry the
  chapter and the direction.
  - DoD-1 (US-033.AC-1) — a ↓ move sends the **full** ordered id list with that chapter one
    position later, for the routed book; and the order then rendered is the **server's** — the
    envelope the `PUT` answers with carries a fifth chapter a co-author appended meanwhile, so
    only a page that re-seeds from the server can render it.
  - DoD-2 — the ↑ move is the mirror image, and the submitted list is the **complete** current
    set: four ids, every chapter named exactly once, none dropped and none invented.
  - DoD-3 — two cases, mounting `ChapterOrderList` alone on its two frozen props: ↑ unavailable
    on the first chapter and ↓ on the last while the two middle chapters offer both (so the
    negatives are not vacuous); and a one-chapter book offers neither. "Unavailable" counts an
    absent control exactly as a disabled one.
  - DoD-4 (US-033.AC-2, client affordance) — with `can_reorder` false: **no** move control in
    either direction for any chapter, nothing drag-shaped by name, nothing natively draggable,
    and none of the sortable / announcement markup a drag context renders — absence, not
    disabledness — while the rest of the list renders normally (ordinal order, per-chapter
    links, each row's own lifecycle word, the planned chapter's remove control).
  - DoD-5 (US-033.AC-2, server authority) — the hint said yes and the **server** refuses (`403`,
    real `ApiError`): the server's own message reaches the author **and** the rendered order
    returns to the server's `[A, B, C]` rather than keeping the attempted `[B, A, C]`.
  - DoD-6 — one persist path: after a settled move the api's reorder function has been called
    **exactly once**, with the whole ordered id list and the routed book id, and
    `createChapter` / `updateChapterSketch` / `removeChapter` were not called at all. Asserted
    on the mock's call count and payload, never on rendered order alone.
  - DoD-7 — a reorder that never settles leaves **every** move control disabled, and a click on
    a second one issues no second call (still exactly one).
  - DoD-8 — with drafts typed into the add form and a refused removal already showing beside its
    chapter, a refused reorder surfaces its own message while both drafts stay byte-identical,
    the removal refusal still stands inside its own row, and both chapters remain listed.
  - DoD-9 — every row still carries its title, its own lifecycle word (planned ≠ closed), its
    `/chapter/<id>` link, and the `planned` chapter's remove control — which still removes.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓,
  DoD-10 [manual/live, no test], DoD-11 [manual/live, no test]
- Harness note: `globals: false`, so every primitive is imported from `"vitest"`; `restoreMocks`
  wipes implementations, so `beforeEach` re-arms the whole server double. Seven of the nine
  items drive the whole `ChaptersPage` (the single composition site); DoD-3 mounts
  `ChapterOrderList` directly on `{ state, bookId }` so the component's frozen props are bound
  by at least one test. Step 006's spec was **not** touched.
- Re-route fix (verifier TEST fault, DoD-4 + DoD-7): the "every move control on screen" census
  matched accessible names by an unqualified `/move/i`, which also captured the frozen
  `Remove "<title>"` control ("Remove" contains those letters). It is now
  direction-qualified — chapter **and** direction, the same shape the per-chapter helper uses —
  so DoD-4's "no move control" and DoD-7's "the move controls are disabled" no longer say
  anything about the remove control, which step-006 DoD-8 requires to stay offered on a
  `planned` chapter. One helper changed; no assertion was weakened and no other test touched.

### Step 008 — tests (2026-07-29)

- `frontend/tests/work/ChapterPage.test.tsx` — **new** — covers DoD-1 … DoD-11 and DoD-14 — the
  chapter item page: header, sketch editor, the caller's own chapter prompt, trio independence and
  the content-pane subject. `api/chapters` mocked module-factory form over **all eight** frozen
  exports (the four this page never calls included); `api/books` + `api/chats` likewise, because
  DoD-1's second case mounts the whole `WorkRoutes` table. `ApiError` is the **real** class from
  `api/client` (DoD-4 and DoD-8 both need one). The mock is a small **server double** keyed by
  chapter id, so a page that re-seeds from the response satisfies the assertions while an
  optimistic draft does not. A local `renderPage(route)` wrapper mounts the page under
  `<Route path="/:bookId/chapter/:id">` — both real path params — beside a `<Link>` to a sibling
  chapter, which is how DoD-14 changes `:id`. Queries are by **role or label only**: both editors
  are located by their accessible labelling (`sketch` / `prompt`), a save control by its
  accessible name or its own section, and every reason/state is asserted as readable text.
  - DoD-1 — two cases: the header renders the title, the ordinal (a standalone `7`, distinct from
    every other fixture number) and the lifecycle word; and the `/work/:bookId/chapter/:id` route
    resolves to this page inside `main`, with the `014.chapter-skeleton` placeholder gone.
  - DoD-2 (US-034.AC-1) — a `planned` chapter's sketch editor is enabled and seeded with the
    stored sketch and accepts text; saving sends `(bookId, chapterId, { sketch })` with **no
    version token** (D6), and the editor then shows the value the **server** returned, which
    deliberately differs from the draft.
  - DoD-3 (US-034.AC-2, client affordance) — looped over `open` / `closing` / `closed`: the sketch
    editor is not editable, a **stated reason** is readable text in its own section, and **no save
    control is offered at all**.
  - DoD-4 (US-034.AC-2, server authority) — a real `ApiError(409, …)` refusal: the server's own
    message reaches the author and the typed draft is byte-intact.
  - DoD-5 — three cases: unavailable while the draft matches the loaded value (and available again
    only after an edit, then unavailable again once restored); unavailable while a never-settling
    save is in flight, with exactly one call issued; and **emptying the sketch is a legal save**
    that sends `{ sketch: "" }`.
  - DoD-6 — the mount loads the caller's own chapter prompt for the routed book **and** chapter
    (the endpoint names no user, so the value is the caller's by construction) and shows it.
  - DoD-7 — `""` + `modified_at: null` renders an **empty, enabled, non-readonly** field that
    accepts text, with no failure copy and no retry inside the prompt section: a normal state, not
    an error state.
  - DoD-8 — saving sends `(bookId, chapterId, { system_prompt })` and the editor then shows the
    **server's** answer; a second case refuses with `ApiError(403, …)` and asserts the message
    surfaces while the draft survives.
  - DoD-9 — an empty prompt save is legal, sends `{ system_prompt: "" }` and clears the field;
    and **no delete/remove/discard control exists anywhere on the surface** (there is no `DELETE`
    verb on the prompt path).
  - DoD-10 — looped over **all four** lifecycle states: the prompt editor is enabled, non-readonly,
    accepts text and opens its save gate — no lifecycle gate anywhere; plus the section's copy
    states the prompt is the caller's **own** and not shared with co-authors, and never frames it
    as book-wide. **Per D7 nothing asserts the prompt affects the assistant** — it is stored and
    served and composed into nothing until `015`.
  - DoD-11 — both directions, armed independently: a rejected prompt load leaves the chapter
    header and a working sketch editor whole; a rejected chapter load leaves the prompt section
    loaded and fully usable.
  - DoD-14 — registration: nothing registered before mount, `kind: "chapter"` with this chapter's
    `entityId` on mount, `chapterState` once the load settles, and `null` after unmount; fresh
    state: unsaved drafts typed into **both** editors, then a router navigation to the sibling
    `:id`, after which both editors show the **second** chapter's stored values.
- `frontend/tests/work/subject.test.ts` — **extended** — covers DoD-12, DoD-13 — appended as one
  step-008 block at the end of the file. **Nothing pre-existing was restructured, renamed or
  removed**; the file's own DoD-1 chapter loop (`closing` / `planned` / `closed` are read-only with
  a stated reason) still holds verbatim under the amendment and was left untouched.
  - DoD-12 — four cases: a `planned` chapter's `editableRegions` is **exactly**
    `["chapter-sketch", "chapter-own-prompt"]`; its **body text** stays read-only —
    `editable: "none"` with the `readOnlyReason` string the branch already carried, asserted
    **verbatim** from the step-008 skeleton freeze; `open` keeps `whole` / `null` and enumerates
    **no** regions; `closing` and `closed` keep `none` + their own non-empty author-facing reason,
    gain no editable region, and stay distinct from the `planned` reason.
  - DoD-13 — `checkWritePermission(plannedChapter, "whole")` (the body **is** the whole subject on
    a chapter — the skeleton's decision 1) still refuses, with a stated reason. **A regression
    guard: green at the red gate by design.**
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓,
  DoD-10 ✓, DoD-11 ✓, DoD-12 ✓, DoD-13 ✓ (regression guard), DoD-14 ✓,
  DoD-15 [manual/live, no test], DoD-16 [manual/live, no test]
- Harness note: `globals: false`, so every primitive is imported from `"vitest"`; `restoreMocks`
  wipes implementations, so `beforeEach` re-arms the whole server double and resets the
  module-level content-subject registry through the frozen register/unregister pair only.
  Two strings the spec does not pin — `closing`'s and `closed`'s read-only reasons — are asserted
  structurally (non-empty, distinct from `planned`'s) rather than verbatim: only the `planned`
  reason was recorded in the freeze, and reading `subject.ts` to harvest the other two is barred by
  the air gap.
- Sanctioned scope extension (orchestrator, 2026-07-30), one collateral file outside the step's Test
  files list: `frontend/tests/work/subjectRoutes.test.tsx` — the `ITEM_ROUTES` row asserting that
  `/bk-1/chapter/ch-1` renders the `014.chapter-skeleton` **placeholder** is retired (DoD-1 replaces
  it with the real `ChapterPage`), deleted rather than moved to a block below per step 006's sibling
  precedent since `ChapterPage.test.tsx` DoD-1 already owns that route assertion; the stale
  `014.chapter-skeleton` clause in the module docstring's owner-label list went with it. The
  `variants` row, the parameterisation and every other assertion in that file are untouched.
- Re-route fix (verifier TEST fault, DoD-3 + DoD-14), `ChapterPage.test.tsx` only:
  - **DoD-3** over-constrained the disabled-reason's **vocabulary** (a word-stem regex) on top of
    the three halves the item actually asks for. Nothing in DoD-3, the Interface intent or
    US-034.AC-2 constrains the wording, and the constraint was unsatisfiable: the freeze sources
    the `closing` / `closed` sentences from `resolveEditability` **verbatim** (DoD-12 freezes them
    independently), and the `closing` string carries none of those stems. The reason is now
    asserted **structurally** — present, non-empty readable text, and **distinct per state** — the
    same treatment the `closing` / `closed` reasons already get in `subject.test.ts`. Nothing was
    weakened: "disabled", "a reason is stated" and "no save is offered" all still assert.
  - **DoD-14**'s fresh-state half mounted the page **directly as a route element**, bypassing
    `routes.tsx`'s `ChapterItemRoute` and its `key={id}` — which `008.context.md` names as the
    mechanism that makes the clause true. A zero-prop page with one state-keyed effect cannot
    remount on a param change without it, so the harness had removed the very thing under test. It
    now drives the **real work route table** (a new `renderRouteTable(route)` helper, the same
    arrangement as DoD-1's route case) and changes `:id` through a router navigation. The
    register/unregister half is untouched.

## Notes & Issues

- Step 001: `backend/app/db/chapters.py`'s module docstring still claimed "bodies are UNIMPLEMENTED"
  after step 008 shipped its three functions; corrected in this step to "signatures are frozen" now
  that nothing in the file is a stub.
- Step 001: smoke-verified against a throwaway DB through the ordinary `init_engine` + `init_db()`
  path — `chapter_author_prompts` is created with `system_prompt VARCHAR NOT NULL`, both FKs and
  `CONSTRAINT uq_chapter_author_prompt_chapter_id_user_id UNIQUE (chapter_id, user_id)`, and a
  duplicate `(chapter_id, user_id)` insert raises `IntegrityError` from the database.
- Step 002: the per-function "Skeleton (014 step 002): UNIMPLEMENTED." docstring lines in
  `services/chapters.py` were dropped as each body landed (and the module docstring's
  "every function body is UNIMPLEMENTED" clause with them) — they would otherwise assert something
  false. `services/books.py` still carries such stale lines; not touched, out of scope.
- Step 002: smoke-verified against a throwaway DB through the real `db/` layer — append ordinals
  (1, 2, 3, then 4 after the middle chapter was removed, i.e. the gap survives), owner/co-author
  `can_reorder`, the `not_planned` refusals, the `invalid_reorder_set` refusal on a short list,
  `1..N` rewriting with an `open` chapter keeping its state/text/version, the co-author reorder
  `BookAuthorizationError`, and `not_found` for unknown and non-numeric ids.
- Step 003: the module docstring's "the six handler bodies are UNIMPLEMENTED" clause was dropped as
  the bodies landed — it would otherwise assert something false (same treatment as step 002's
  per-function skeleton lines).
- Step 003: smoke-verified by calling the six handler coroutines directly against a throwaway DB with
  a hand-built `BookAccess` — 201/200/204 on the success paths, `can_reorder` true for the owner and
  false for a co-author, 403 on a reader's create and a co-author's reorder, 400 on a short reorder
  list, 404 for unknown / non-numeric (`"order"`) / another book's chapter id on read+sketch+delete,
  409 on sketch and delete of an `open` chapter. The generated OpenAPI reports exactly the six paths
  with `201` on create, `204` on delete and `200` elsewhere, in the frozen declaration order.
- Step 004: the "every function body is UNIMPLEMENTED" / "both handler bodies are UNIMPLEMENTED"
  clauses in the two module docstrings, and the per-function `Skeleton (014 step 004): UNIMPLEMENTED.`
  lines, were dropped as each body landed — they would otherwise assert something false (same
  treatment as steps 002 and 003).
- Step 004: smoke-verified against a throwaway DB through the real `db/` layer with hand-built
  `BookAccess` objects — no row reads `""` + `null`; the first write stamps both timestamps; a second
  write reuses the same row id, preserves a backdated `created_at` and advances `modified_at`; `""`
  stores and reads back with a real `modified_at` (distinguishable from "no row"); an owner's and a
  co-author's prompts on the same chapter stay independent; a second chapter of the same book is
  unaffected; read and write both succeed on a `closed` chapter and leave its `state` alone; a reader
  is refused `not_a_member` on both verbs; unknown, non-numeric and another book's chapter ids are
  `not_found` on both verbs with nothing stored. The generated OpenAPI reports exactly `get` and `put`
  on the path, both `200` (plus `422`), bound to `ChapterAuthorPromptResponse`; `DELETE` and `POST`
  match only partially (framework 405).
- Step 001: the skeleton's flagged `TABLE_REGISTRY` position (`chapter_author_prompts` immediately
  before `chapters`, i.e. a child table ahead of its parent) was left exactly as frozen. Inert today
  (no `PRAGMA foreign_keys=ON`, import is per-table UPSERT), but it is the orchestrator's call, not
  this step's.
- Step 006: the freeze allowed either re-seed shape ("the create response plus a reload, or the
  reload alone"). The **first** was implemented: on a successful add the create response is appended
  to the envelope and `loadChapters` then re-seeds the whole list. Either way the rendered list is
  the server's — nothing is spliced from a draft — but the transient between the two writes shows
  the created chapter rather than nothing.
- Step 006: `addChapter` sends `addTitleDraft` **untrimmed** — DoD-3 says the create call carries
  "exactly those values", and the backend's `CreateChapterRequest` already strips the title
  (step 002's `strip_whitespace=True`). The client rule only gates submission.
- Step 006: `state.canReorder` is implemented and deliberately **not read by the page** — step 007
  is its consumer. Do not remove it as dead code.
- Step 007: the sortable handle passes `disabled: state.reorderStatus === "loading"` to
  `useSortable`, so a drag cannot race an in-flight reorder either. The freeze names the in-flight
  condition only for the ↑ / ↓ controls (DoD-7); extending it to the drag keeps the two affordances
  from diverging, which is the invariant the whole step is built around. Recorded because it goes
  one word beyond the literal freeze.
- Step 007: `resolveRenderedOrder` keeps a chapter the pending sequence does not name (one that
  arrived from a concurrent load) at the end of the rendered list rather than dropping it. The
  pending order is a rendering optimism over ids, so it can briefly disagree with the envelope; a
  filter would make a chapter vanish mid-flight.
- Step 007: `applyChapterOrder`'s failure path issues a `listChapters` **read** after the refused
  `PUT` (the snap-back, DoD-5). DoD-6's "only chapter write" is unaffected — the `PUT` is still the
  single write, and it is still made exactly once.
- Step 008: the freeze's `sketchDisabledReason` contract reads two ways for the **before-first-load**
  case — "`null` **exactly when** `canEditSketch` is `true`, a non-empty sentence otherwise" versus
  "before the first successful load there is nothing loaded to state a reason about". The **first**
  (the stated invariant) was implemented: not-yet-loaded returns a sentence saying the chapter has
  not loaded. It is inert on screen — the page renders the chapter trio's loading branch instead of
  the sketch section until the load resolves — so the choice affects only a direct read of the
  computed.
- Step 008: the page's two save controls are named `Save sketch` and `Save system prompt` rather than
  both `Save` (the `BookStatePage` wording). Two identically named buttons on one surface would make
  every role-by-name query ambiguous, and the freeze names neither.
- Step 008: each editor surfaces **every** value of its `…ServerErrors` map in one `Alert` (the
  step-006 add-form idiom) rather than splitting the field key into Mantine's `error` prop and the
  `form` key into an alert. Rendering both would put the same refusal on screen twice.
- Step 008 (post-verify correction): the prompt `Textarea`'s **placeholder** first read "Write the
  instructions your assistant should follow for this chapter" — `BookStatePage`'s `021` placeholder
  with "book" → "chapter". True at the book level, where the prompt **is** composed; false one level
  down, where D7 defers composition to `015`, so it promised the prompt acts on the assistant today.
  Reworded to "Your own standing instructions for this chapter, saved with it." — what the field
  **is**, asserting nothing about what reads it. Placeholder only: no logic, no signature and no
  other string changed, and `BookStatePage.tsx` was not opened (its wording is true there).
