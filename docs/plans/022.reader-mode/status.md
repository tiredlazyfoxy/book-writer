# Feature 022 — reader-mode

| Status | Verifier | Date       |
|--------|----------|------------|
| done   | PASS     | 2026-07-31 |

## Files Changed

### Backend

- `backend/app/models/schemas/reader.py` — the five reader DTOs (arrived complete from the skeleton;
  verified against the frozen record, unchanged).
- `backend/app/services/reader.py` — filled all three function bodies; added the module-private
  `_resolve_reader_chapter(access, chapter_id)` helper (mirrors `services/chapters.py::_resolve_chapter`
  and folds the `READER_VISIBLE_STATES` gate into it, so all five refusal sources collapse to one
  `ReaderError(chapter_not_found)` — D5); extended the frozen import block with `db.books` / `db.chapters`,
  `Chapter`, `Capability`, `authz`, `ReaderChapterRef`, `PublicBookRef`.
- `backend/app/db/books.py` — filled `list_public_for_reader` with the four-clause query
  (`visibility == public` ∧ `state == active` ∧ `owner_id != user_id` ∧ correlated `NOT EXISTS` over
  `book_members`), `order_by(Book.id)`; added `exists` / `BookState` / `Visibility` imports.
- `backend/app/routes/reader.py` — arrived complete; error mapping confirmed complete (both reasons → 404,
  `BookAuthorizationError` → 403, in that order on both handlers). Unchanged.
- `backend/app/routes/books.py` — arrived complete (`GET /public` declared between `/shared` and
  `/{book_id}`, delegating to `reader_service.list_public_books`). Unchanged.
- `backend/app/main.py` — arrived complete (`reader.router` registered). Unchanged.
- `backend/app/models/schemas/books.py` — **deleted** the interim `INTERIM COMPATIBILITY RE-EXPORT` alias
  line (DoD-12); reworded `BookDetailResponse`'s cross-reference so the literal name `ReaderBookResponse`
  no longer appears anywhere in the module while the pointer at `app.models.schemas.reader` stays
  unambiguous.
- `backend/app/services/books.py` — reworded the module-docstring move note so the literal name
  `get_reader_book` no longer appears in the module (DoD-12); no code change.

### Frontend

- `frontend/src/types/reader.d.ts` — the five interfaces (arrived complete; verified, unchanged).
- `frontend/src/api/reader.ts` — filled all three bodies as thin `request<T>` delegations over
  `BASE = "/api/books"`.
- `frontend/src/read/readGate.ts` — filled `resolveReadAccess` / `enforceReadAccess` as a verbatim
  structural mirror of `work/workGate.ts` (auth-only, redirect `"/login/"` via `navigateTo`).
- `frontend/src/read/main.tsx`, `App.tsx`, `routes.tsx` — arrived complete; verified (gate before
  `createRoot`; `basename="/read"`; exactly the three routes). Unchanged.
- `frontend/src/read/pages/tableOfContentsPageState.ts` — filled `loadReaderBook`; added the module-private
  `readerBookRefusal(err)` that picks the D9 refusal copy from `ApiError.status` (404 / 403 / fallback).
- `frontend/src/read/pages/readerChapterPageState.ts` — filled `loadReaderChapter`; added the
  module-private `readerChapterRefusal(err)`, whose 404 copy deliberately does not speculate about which of
  the five collapsed sources fired (D5).
- `frontend/src/read/pages/TableOfContentsPage.tsx` — implemented: one page-level mount effect + one
  `AbortController`, title heading, chapters rendered in server order as `<Anchor component={Link}
  to={/:bookId/:chapterId}>`, loading / labelled-empty / error branches. No edit affordance.
- `frontend/src/read/pages/ReaderChapterPage.tsx` — implemented: same page shape, back link to the table of
  contents, body via `<Markdown>{chapter.text}</Markdown>` (no plugins, no `components` prop). No textbox,
  no save/edit control, no editor import.
- `frontend/src/read/pages/NotFoundPage.tsx` — implemented: static not-found copy + plain `<a href="/">`
  back to the bookshelf; discloses nothing about the attempted address.
- `frontend/src/user/pages/bookshelfPageState.ts` — added the third load block inside the existing
  `loadBookshelf` (its own `try`/`catch`, `publicStatus` / `publicError` added to the opening
  `runInAction`); added the `readerApi` namespace import. `loadBookshelf` / `createBookAction` signatures
  unchanged.
- `frontend/src/user/pages/BookshelfPage.tsx` — added the third "Public books" section below "Shared with
  me", fed by a new module-private `renderPublicList` (title + description columns, labelled empty state,
  each row a plain `<a href={/read/${book.id}}>` — a cross-entry full page load, D16).

### Not touched, as required

`frontend/vite.config.ts` (DoD-19), `backend/app/services/authz.py` (D7), `backend/app/db/chapters.py`
(D6), and everything under `backend/tests/` / `frontend/tests/`.

## Skeleton

### Frozen interface (2026-07-31)

Every signature below is the contract the test-coder binds to and the coder may not change. All plan
`## Interface` signatures were committed **verbatim** — no divergence, with one exception recorded under
"Notes & Issues → DoD-12 vs DoD-13" (an interim one-line re-export, not a signature change).

#### Backend — new files

`backend/app/models/schemas/reader.py` (new module — five DTOs, declarative, arrive **complete**):

- `class ReaderChapterRef(BaseModel)` — `id: str`, `title: str` — new
- `class ReaderBookResponse(BaseModel)` — `title: str`, `chapters: list[ReaderChapterRef]` — **moved**
  here from `models/schemas/books.py` (was `title: str`, `chapters: list[str]`); `chapters` **widened**
- `class ReaderChapterResponse(BaseModel)` — `id: str`, `title: str`, `text: str` — new
- `class PublicBookRef(BaseModel)` — `id: str`, `title: str`, `description: str` — new
- `class PublicBookListResponse(BaseModel)` — `items: list[PublicBookRef]` — new
- No other field may be added to any of the five: each exclusion is the structural half of UC-029.

`backend/app/services/reader.py` (new module):

- `class ReaderErrorReason(str, enum.Enum)` — new — members `book_not_found = "book_not_found"`,
  `chapter_not_found = "chapter_not_found"`, **values verbatim from the plan** (underscored), knowingly
  not re-spelled to the hyphenated `BookErrorReason` / `ChapterErrorReason` house style — neither value
  ever reaches the wire, so fidelity to the frozen interface wins.
- `class ReaderError(Exception)` — new — `def __init__(self, reason: ReaderErrorReason, message: str = "") -> None`,
  sets `self.reason` / `self.message`, calls `super().__init__(message)`. `ChapterError`'s shape exactly.
- `READER_VISIBLE_STATES: frozenset[ChapterState] = frozenset({ChapterState.open, ChapterState.closed})`
  — new. **Declared with its value** (a declarative constant, like the route status maps): a bare
  annotation would raise `ImportError` for anything importing the name.
- `async def get_reader_book(access: BookAccess) -> ReaderBookResponse` — new — body UNIMPLEMENTED
  (`raise NotImplementedError`)
- `async def get_reader_chapter(access: BookAccess, chapter_id: str) -> ReaderChapterResponse` — new —
  body UNIMPLEMENTED
- `async def list_public_books(caller: User) -> PublicBookListResponse` — new — body UNIMPLEMENTED
- Imports frozen: `ChapterState` from `app.models.chapter`, `BookAccess` from `app.services.authz`,
  `User` from `app.models.user`, the three DTOs from `app.models.schemas.reader`.

`backend/app/routes/reader.py` (new module — router + wiring arrive **complete**; behavior is in the
service, which throws):

- `router = APIRouter(prefix="/api/books", tags=["reader"])`
- `_READER_ERROR_STATUS: dict[reader_service.ReaderErrorReason, int]` — both members → `404`
- `def _map_reader_error(err: reader_service.ReaderError) -> HTTPException` — new
- `def _map_authz_error(err: authz.BookAuthorizationError) -> HTTPException` — new (→ 403)
- `GET /{book_id}/read` → `async def get_reader_book(access: authz.BookAccess = Depends(authz.book_access)) -> ReaderBookResponse` — new
- `GET /{book_id}/read/chapters/{chapter_id}` → `async def get_reader_chapter(chapter_id: str, access: authz.BookAccess = Depends(authz.book_access)) -> ReaderChapterResponse` — new
- Both handlers catch `authz.BookAuthorizationError` → `_map_authz_error`, `reader_service.ReaderError`
  → `_map_reader_error`, in that order. `{book_id}` is consumed entirely by the dependency and is never
  re-declared on a handler.

#### Backend — delivered files, changed

- `backend/app/models/schemas/books.py` — `class ReaderBookResponse` **removed** (moved). The
  `BookDetailResponse` docstring cross-reference now points at
  `app.models.schemas.reader.ReaderBookResponse`. See Notes & Issues for the interim re-export line.
- `backend/app/services/books.py` — `async def get_reader_book(access)` **removed**; the
  `ReaderBookResponse` import dropped from the `models.schemas.books` import block; module docstring
  records the move. Every other function is untouched.
- `backend/app/routes/books.py` — `GET /{book_id}/read` handler **removed**; `ReaderBookResponse` import
  dropped; `from app.models.schemas.reader import PublicBookListResponse` and
  `from app.services import reader as reader_service` added.
  - `GET /public` → `async def list_public_books(caller: User = Depends(auth_service.get_current_user)) -> PublicBookListResponse` — new,
    delegating to `reader_service.list_public_books(caller)` (arrives **complete** — one delegation
    line; the service throws). **Declared immediately after `GET /shared` and before `GET /{book_id}`**
    (D15). Verified against the live OpenAPI path order: `/api/books` → `/api/books/shared` →
    `/api/books/public` → `/api/books/{book_id}` → …
- `backend/app/db/books.py` — `async def list_public_for_reader(user_id: int) -> list[Book]` — new —
  body UNIMPLEMENTED (`raise NotImplementedError`). The four-clause intent + `order_by(Book.id)` is in
  the docstring.
- `backend/app/main.py` — `from app.routes import reader` + `app.include_router(reader.router)` placed
  after `chapters.router`. Include order is deliberately **not** load-bearing here (comment in file).

#### Frontend — new files

`frontend/src/types/reader.d.ts` (new — five interfaces, verbatim from the plan, arrive **complete**):

- `export interface ReaderChapterRef { id: string; title: string }`
- `export interface ReaderBookResponse { title: string; chapters: ReaderChapterRef[] }`
- `export interface ReaderChapterResponse { id: string; title: string; text: string }`
- `export interface PublicBookRef { id: string; title: string; description: string }`
- `export interface PublicBookListResponse { items: PublicBookRef[] }`

`frontend/src/api/reader.ts` (new — `const BASE = "/api/books"`; all three bodies **throw**):

- `export async function getReaderBook(bookId: string, signal?: AbortSignal): Promise<ReaderBookResponse>` — new
- `export async function getReaderChapter(bookId: string, chapterId: string, signal?: AbortSignal): Promise<ReaderChapterResponse>` — new
- `export async function listPublicBooks(signal?: AbortSignal): Promise<PublicBookListResponse>` — new

`frontend/src/read/readGate.ts` (new — structural mirror of `work/workGate.ts`; both fn bodies **throw**):

- `export type ReadAccessDecision = { allowed: true } | { allowed: false; redirectTo: string }` — new (complete)
- `export function resolveReadAccess(): ReadAccessDecision` — new — UNIMPLEMENTED
- `export function enforceReadAccess(): boolean` — new — UNIMPLEMENTED

`frontend/src/read/routes.tsx` (new — route table is declarative and arrives **complete**):

- `function TableOfContentsRoute()` — new (module-private) — `useParams().bookId` → `<TableOfContentsPage key={bookId} />`
- `function ReaderChapterRoute()` — new (module-private) — `useParams().chapterId` → `<ReaderChapterPage key={chapterId} />`
- `export const ReadRoutes = observer(function ReadRoutes() { … })` — new — exactly three `<Route>`s:
  `/:bookId`, `/:bookId/:chapterId`, `*` → `<NotFoundPage />`. No index route. **No fourth route may
  ever be added** (UC-029 postcondition).

`frontend/src/read/pages/` (new — all three components take **zero props** and **throw on render**;
both state classes are complete, both load functions throw):

- `export class TableOfContentsPageState` — new — `book: ReaderBookResponse | null = null`,
  `bookStatus: "idle" | "loading" | "ready" | "error" = "idle"`, `bookError: string | null = null`,
  `constructor() { makeAutoObservable(this) }`
- `export async function loadReaderBook(state: TableOfContentsPageState, bookId: string, signal?: AbortSignal): Promise<void>` — new — UNIMPLEMENTED
- `export const TableOfContentsPage = observer(function TableOfContentsPage() { … })` — new — UNIMPLEMENTED, throws on render
- `export class ReaderChapterPageState` — new — `chapter: ReaderChapterResponse | null = null`,
  `chapterStatus: "idle" | "loading" | "ready" | "error" = "idle"`, `chapterError: string | null = null`,
  `constructor() { makeAutoObservable(this) }`
- `export async function loadReaderChapter(state: ReaderChapterPageState, bookId: string, chapterId: string, signal?: AbortSignal): Promise<void>` — new — UNIMPLEMENTED
- `export const ReaderChapterPage = observer(function ReaderChapterPage() { … })` — new — UNIMPLEMENTED, throws on render
- `export const NotFoundPage = observer(function NotFoundPage() { … })` — new — UNIMPLEMENTED, throws on render
- The D9 refusal-message mapping (`ApiError.status` 404 / 403 / else) belongs in the **load functions**,
  not the components — stated in each load function's docstring.

#### Frontend — delivered files, changed

- `frontend/src/read/main.tsx` — rewritten to the frozen shape (arrives **complete**):
  `if (enforceReadAccess()) { createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>) }`.
  Gate outside React, before `createRoot` (DoD-14).
- `frontend/src/read/App.tsx` — rewritten (arrives **complete**): `export const App = observer(function App() { … })`,
  zero props, `MantineProvider theme={theme} defaultColorScheme="dark"` → `<BrowserRouter basename="/read">`
  → `<ReadRoutes />` (DoD-15). The delivered placeholder markup is gone.
- `frontend/src/user/pages/bookshelfPageState.ts` — `BookshelfPageState` gains the third trio:
  `publicBooks: PublicBookRef[] = []`, `publicStatus: "idle" | "loading" | "ready" | "error" = "idle"`,
  `publicError: string | null = null`; `import type { PublicBookRef } from "../../types/reader"` added.
  **`loadBookshelf` / `createBookAction` signatures are unchanged and their bodies untouched** — the
  third load block is the coder's, described in `loadBookshelf`'s docstring.
- `frontend/src/user/pages/BookshelfPage.tsx` — **not touched**: the third section needs no signature
  change (the page takes zero props and `renderList` is module-private). Entirely the coder's.

#### Not touched, deliberately

- `frontend/vite.config.ts` — untouched (DoD-19): the `read` Rollup input and the `spaFallback` `/read`
  branch already exist. Confirmed by `git status`.
- `backend/tests/**`, `frontend/tests/**` — untouched (test-coder's domain, including the delivered
  `backend/tests/routes/test_book_read.py`).
- `backend/app/services/authz.py` — untouched: no new `Capability`, no `_CAPABILITY_MATRIX` row (D7).
- `backend/app/db/chapters.py` — untouched: the state filter is service-side (D6).

#### Compile gate

- `cd backend && .venv/Scripts/python -m pytest --collect-only -q` — **clean**, 1220 tests collected
  (same count as the pre-skeleton baseline; nothing dropped).
- `cd frontend && npx tsc --noEmit` — **clean**.
- `cd frontend && npm run build` (`tsc && vite build`) — **clean**, built in 8.0s.
- Route order verified live via `app.openapi()["paths"]`: `/api/books/public` is emitted **before**
  `/api/books/{book_id}` (DoD-11), and both reader paths are registered (DoD-10).

#### Red-gate profile to expect

- **DoD-1..DoD-7 (backend) must all be RED.** Every reader service function raises
  `NotImplementedError` (→ 500), so no status code, no key set and no ordering can accidentally match.
  `db/books.py::list_public_for_reader` likewise. The routes, the DTOs and the error→status map arrive
  complete, so a test asserting only "the URL resolves to something" would be green by construction —
  that is why the DoD items assert payload shape and status, not mere reachability.
- **DoD-8, DoD-9 (frontend) must both be RED.** `TableOfContentsPage` and `ReaderChapterPage` throw
  during render, so every assertion fails at `render()`. If a test mocks `api/reader` instead, the pages
  still throw. The `api/reader.ts` bodies throw independently, so a page test that does *not* mock the
  api module fails there too.
- **The delivered `backend/tests/routes/test_book_read.py` is RED during the skeleton phase** (its two
  200-expecting tests hit the now-unimplemented service). That is expected; DoD-13 is a *verify-run*
  criterion, checked after the coder fills the bodies. It **collects** cleanly — see Notes & Issues.

## Tests

### Tests (2026-07-31)

Nine tests, one per `[test]` DoD item (DoD-1..DoD-9). Nothing beyond them: the plan's
`## Test plan` -> "Not tested (deliberate)" list is honoured in full.

- `backend/tests/services/test_reader.py` — covers DoD-1, DoD-6
  - DoD-1 — `get_reader_book` returns exactly the `open` + `closed` chapters, ascending by
    `ordinal` (rows seeded 3, 5, 1, 4, 2 so insertion order ≠ ordinal order); `planned` and
    `closing` absent by title and by id.
  - DoD-6 — `list_public_books` returns exactly the stranger's `active` `public` book;
    the caller's own book, a co-authored book, a private book and an `archived` book are each
    excluded (one clause different per row).
- `backend/tests/routes/test_reader.py` — covers DoD-2, DoD-3, DoD-4, DoD-5, DoD-7
  - DoD-2 — `GET /{book_id}/read` keys are exactly `{title, chapters}`, each ref exactly
    `{id, title}`; `sketch`/`summary`/`state`/`ordinal`/`version` asserted absent.
  - DoD-3 — parameterized over the five refusal sources (`planned`, `closing`, unknown id,
    non-numeric id, another book's chapter) → 404 each, with the reader-visible 200 and its
    exact `{id, title, text}` key set asserted on every parameterization.
  - DoD-4 — the same non-member caller: 404 from both reader routes on a private book,
    200 from both on a public one.
  - DoD-5 — parameterized over the three routes (`/{id}/read`, `/{id}/read/chapters/{cid}`,
    `/api/books/public`) → 401 with no token.
  - DoD-7 — each `GET /api/books/public` item's keys are exactly `{id, title, description}`;
    `owner_id`/`visibility`/`state`/`collaboration_mode`/timestamps asserted absent.
- `frontend/tests/read/TableOfContentsPage.test.tsx` — covers DoD-8 — chapters render as
  `/:bookId/:chapterId` links in server order, and a 404 load renders refusal copy with no
  chapter links (never a blank pane). `api/reader` mocked module-factory form, never `fetch`.
- `frontend/tests/read/ReaderChapterPage.test.tsx` — covers DoD-9 — the saved body renders
  and no edit affordance exists: no input-bearing role, nothing editable in fact, no
  save/edit control by role.

Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓,
DoD-10..DoD-20 [verify, no test], DoD-21 [manual/live, no test].

Deliberately not tested (per plan `## Test plan`): 10 items — DTO field declarations, route
wiring / `main.py` registration, `api/reader.ts`, `read/main.tsx` + `App.tsx` + `routes.tsx`,
`readGate.ts`, the bookshelf "Public books" section and its `href`, both empty-state messages,
the `<Markdown>` pass-through, the `authz.require` call, `NotFoundPage` and the back-link.

Authorized re-bind to a delivered test file (user decision, option 1 of "DoD-12 vs DoD-13"):
`backend/tests/routes/test_book_read.py:55` was split into
`from app.models.schemas.books import BookDetailResponse` +
`from app.models.schemas.reader import ReaderBookResponse`. **Nothing else in that file
changed** — every assertion, including `set(body.keys()) == {"title", "chapters"}` and
`isinstance(body["chapters"], list)`, is byte-identical. The interim compatibility re-export in
`models/schemas/books.py` is now unreferenced by the suite and is the coder's to delete
(DoD-12).

Authorized mock completion in a delivered test file (user decision, frontend analogue of the
above): `frontend/tests/user/BookshelfPage.test.tsx` gained a module-factory `vi.mock` for
`../../src/api/reader` (all three exports as `vi.fn()`, `listPublicBooks` defaulted in
`beforeEach` to `{ items: [] }`), because D16 made `loadBookshelf` load the third trio from
that module and, unmocked, it reached the real `request` → `fetch` and produced 3 unhandled
errors under jsdom. **No assertion changed** — every `expect` is byte-identical and no test
was added.

## Notes & Issues

### DoD-12 vs DoD-13 — the plan's two criteria cannot both hold as written (skeleton, 2026-07-31)

**What the plan asks for.** DoD-12: "`ReaderBookResponse` no longer appears in
`models/schemas/books.py`". DoD-13: "The delivered `backend/tests/routes/test_book_read.py` still passes
unchanged." Interface §`models/schemas/reader.py`: "`ReaderBookResponse` moves out of
`models/schemas/books.py` … so it must keep passing untouched."

**What conflicts.** `backend/tests/routes/test_book_read.py:55` reads
`from app.models.schemas.books import BookDetailResponse, ReaderBookResponse`, and line 238 calls
`ReaderBookResponse.model_validate(body)`. Removing the name from `models/schemas/books.py` turns that
into a collection-time `ImportError` — the file cannot pass, let alone pass *unchanged*. The plan's own
analysis of this test (plan.md:62-66) reasons only about its two assertions, which do survive the
widening; the import line appears to have been overlooked. (Both assertions really do still hold: a
freshly created book has zero chapters, so `chapters == []` and `set(body.keys()) == {"title",
"chapters"}` are unaffected.)

**Interim measure taken, so the suite still collects.** `models/schemas/books.py` no longer *defines*
`ReaderBookResponse`; it carries **one commented alias line**,
`from app.models.schemas.reader import ReaderBookResponse as ReaderBookResponse`, marked
`INTERIM COMPATIBILITY RE-EXPORT` and pointing here. This is not a signature and adds no behavior — the
name resolves to the same, moved class. It keeps `pytest --collect-only` at the full 1220 tests so the
test-coder and the red-gate verifier inherit a working build. **It does, however, fail DoD-12 as
literally worded**, so it must not survive to the verify run.

**Resolution needed before the verify run — pick one:**

1. **Fix the test's import** (`from app.models.schemas.reader import ReaderBookResponse`) and delete the
   alias line. Cleanest end state; DoD-12 passes; DoD-13 passes in substance but the file is no longer
   byte-identical, so DoD-13's wording needs relaxing to "still passes, with its import path updated".
   Requires authorising someone (test-coder or coder) to touch a delivered test file.
2. **Keep the alias line permanently** and reword DoD-12 to "`ReaderBookResponse` is no longer *defined*
   in `models/schemas/books.py`". Zero test churn, DoD-13 holds verbatim; cost is a compatibility shim
   with exactly one consumer, which is the kind of thing that outlives its reason.
3. **Do not move the DTO** — keep `ReaderBookResponse` defined in `models/schemas/books.py` and widen it
   in place. Drops DoD-12 entirely and weakens D3's "the reader surface is answerable from two files";
   the service and route moves are unaffected.

The skeleton did **not** pick between these — option 2 is merely the shape the interim line happens to
take because it was the only one that keeps the build green without editing a test file. Note also that
`models/schemas/books.py`'s `BookDetailResponse` docstring referenced `ReaderBookResponse` by name; the
skeleton repointed that cross-reference at `app.models.schemas.reader.ReaderBookResponse`, which a
literal grep for DoD-12 will also see.

### Two names the plan left to the skeleton

Both are new symbols the plan's Interface named only by role, so the skeleton chose house-convention
names; they are now frozen: `loadReaderBook(state, bookId, signal?)` and
`loadReaderChapter(state, bookId, chapterId, signal?)` (the plan said "an external
`load<X>(state, args, signal)`"). Trio field names follow `BookHubPageState`: `book`/`bookStatus`/
`bookError` and `chapter`/`chapterStatus`/`chapterError`.

### DoD-12 vs DoD-13 — resolved (coder, 2026-07-31)

The conflict recorded above was resolved by **option 1, by user decision**, relayed by the orchestrator:
the test-coder re-pointed `backend/tests/routes/test_book_read.py`'s import at
`app.models.schemas.reader` (one import line, user-approved; every assertion byte-identical), and the coder
deleted the interim `INTERIM COMPATIBILITY RE-EXPORT` line from `backend/app/models/schemas/books.py`.
DoD-12 now holds literally — a plain `grep ReaderBookResponse backend/app/models/schemas/books.py` and
`grep get_reader_book backend/app/services/books.py` both return nothing, so the two prose
cross-references the skeleton left (the `BookDetailResponse` docstring and the `services/books.py` module
docstring) were reworded to name the new module path instead of the moved symbol. DoD-13 holds in
substance: the file still passes, with its import path updated.

### DoD-5's 401 test was green at the red gate — accepted (coder, 2026-07-31)

Recorded so a resumed session does not read it as a red-gate defect. DoD-5's "no token → 401 from all three
routes" was already satisfied when the skeleton landed: the 401 comes entirely from the pre-existing
`get_current_user` / `book_access` dependencies, and the skeleton deliberately delivers route wiring
**complete** (only the service bodies threw). The user accepted this — the test stays and is asserted at
the verify run; it is a contract test for the auth gate, not a test of anything this feature implements.
