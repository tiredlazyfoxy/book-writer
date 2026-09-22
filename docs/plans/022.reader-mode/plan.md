# Plan — 022.reader-mode

## Goal

A logged-in user who is not a member of a public book can find it, open it, get an ordered table of
contents of its written chapters, follow one, and read that chapter's saved text read-only — with no edit
affordance anywhere on the page. A private book refuses them; a logged-out visitor is sent to log in.

## Realizes

FEAT-007 (reader half) — UC-029, US-030 (AC-1..AC-4).

## Source areas

- `backend/app/routes/` — reader routes, the new `/public` route, removal of the delivered `/read` route.
- `backend/app/services/` — the new reader service, removal of `get_reader_book` from `services/books.py`.
- `backend/app/db/` — one new function on `db/books.py`.
- `backend/app/models/schemas/` — the new reader DTO module, removal of `ReaderBookResponse` from `books.py`.
- `backend/app/main.py` — registering `routes/reader.py`.
- `frontend/src/read/` — the whole reader SPA (currently a 2-file stub).
- `frontend/src/api/` — the new `reader.ts` module.
- `frontend/src/types/` — the new `reader.d.ts` module.
- `frontend/src/user/` — the bookshelf's third section and trio (delivered files, extended).

## Test files

- `backend/tests/routes/test_reader.py` (new)
- `backend/tests/services/test_reader.py` (new)
- `frontend/tests/read/TableOfContentsPage.test.tsx` (new)
- `frontend/tests/read/ReaderChapterPage.test.tsx` (new)

`backend/tests/routes/test_book_read.py` is delivered and stays — not in the test-coder's scope, must keep
passing unchanged (see Interface, and DoD verify list).

## Interface

### `backend/app/models/schemas/reader.py` (new)

```python
class ReaderChapterRef(BaseModel):
    id: str
    title: str

class ReaderBookResponse(BaseModel):        # MOVED here from models/schemas/books.py
    title: str
    chapters: list[ReaderChapterRef]        # WIDENED from list[str]

class ReaderChapterResponse(BaseModel):
    id: str
    title: str
    text: str

class PublicBookRef(BaseModel):
    id: str
    title: str
    description: str

class PublicBookListResponse(BaseModel):
    items: list[PublicBookRef]
```

`ReaderBookResponse` moves out of `models/schemas/books.py`. The delivered test
`test_read_projection_excludes_members_only_fields__DoD5_US030_AC2` asserts
`set(body.keys()) == {"title", "chapters"}` and `isinstance(body["chapters"], list)` — both still hold
after the widening (there are zero frontend consumers of the old shape), so it must keep passing untouched
— proof the delivered coverage is preserved, not weakened.

### `backend/app/services/reader.py` (new)

```python
class ReaderErrorReason(str, enum.Enum):
    book_not_found = "book_not_found"
    chapter_not_found = "chapter_not_found"

class ReaderError(Exception):
    def __init__(self, reason: ReaderErrorReason, message: str = "") -> None: ...

READER_VISIBLE_STATES: frozenset[ChapterState]   # = {ChapterState.open, ChapterState.closed}

async def get_reader_book(access: BookAccess) -> ReaderBookResponse: ...
async def get_reader_chapter(access: BookAccess, chapter_id: str) -> ReaderChapterResponse: ...
async def list_public_books(caller: User) -> PublicBookListResponse: ...
```

Mirrors `services/chapters.py::ChapterError`'s `(reason, message="")` shape (harvest §6). State filter and
`ordinal` sort run **in the service** over `db.chapters.list_by_book(book_id)`'s full list — no new
`db/chapters.py` function (D6).

### `backend/app/routes/reader.py` (new)

```python
@router.get("/{book_id}/read")
async def get_reader_book(
    access: authz.BookAccess = Depends(authz.book_access),
) -> ReaderBookResponse: ...

@router.get("/{book_id}/read/chapters/{chapter_id}")
async def get_reader_chapter(
    chapter_id: str,
    access: authz.BookAccess = Depends(authz.book_access),
) -> ReaderChapterResponse: ...
```

Both call `authz.require(access, Capability.read_book)` inside the service, catch
`authz.BookAuthorizationError` → 403 and `reader_service.ReaderError` → `_READER_ERROR_STATUS` in the route,
per `_map_chapter_error` (`routes/chapters.py:94-103`). Router prefix `/api/books`, registered in
`backend/app/main.py`. URLs are unchanged from the delivered `/read` route, which this replaces.

### `backend/app/routes/books.py` (delivered file, one route added, one removed)

```python
@router.get("/public")
async def list_public_books(
    caller: User = Depends(auth_service.get_current_user),
) -> PublicBookListResponse: ...
```

Declared immediately after `GET /shared` and before `GET /{book_id}` (D15 — static-before-dynamic must be
provable by reading this one file). Delegates to `reader_service.list_public_books(caller)`. Gated by
authentication alone — no `book_id` to resolve a role against (D14). The delivered `GET /{book_id}/read`
route is removed from this file (moved to `routes/reader.py`, D3).

### `backend/app/db/books.py` (delivered file, one function added)

```python
async def list_public_for_reader(user_id: int) -> list[Book]: ...
```

Returns rows where **all four** hold: `Book.visibility == Visibility.public` ∧ `Book.state ==
BookState.active` ∧ `Book.owner_id != user_id` ∧ no `BookMember` row for `(Book.id, user_id)` (a `NOT
EXISTS`, the negative of `list_shared`'s join). Order by `Book.id`.

### `frontend/src/types/reader.d.ts` (new)

```ts
export interface ReaderChapterRef { id: string; title: string; }
export interface ReaderBookResponse { title: string; chapters: ReaderChapterRef[]; }
export interface ReaderChapterResponse { id: string; title: string; text: string; }
export interface PublicBookRef { id: string; title: string; description: string; }
export interface PublicBookListResponse { items: PublicBookRef[]; }
```

### `frontend/src/api/reader.ts` (new)

```ts
export async function getReaderBook(bookId: string, signal?: AbortSignal): Promise<ReaderBookResponse>
export async function getReaderChapter(bookId: string, chapterId: string, signal?: AbortSignal): Promise<ReaderChapterResponse>
export async function listPublicBooks(signal?: AbortSignal): Promise<PublicBookListResponse>
```

Thin `request<T>` delegations, `BASE = "/api/books"`, matching `api/books.ts` / `api/chapters.ts`.

### `frontend/src/read/readGate.ts` (new)

```ts
export type ReadAccessDecision = { allowed: true } | { allowed: false; redirectTo: string };
export function resolveReadAccess(): ReadAccessDecision
export function enforceReadAccess(): boolean
```

Verbatim structural mirror of `work/workGate.ts` — auth-only (`getToken()`), redirect `"/login/"` via
`navigateTo` (`src/utils/navigate.ts`).

### `frontend/src/read/` SPA (rewrite the stub, add the rest)

- `main.tsx` — `if (enforceReadAccess()) { createRoot(...).render(<StrictMode><App/></StrictMode>) }`. Gate
  runs outside React, before `createRoot`.
- `App.tsx` — `MantineProvider theme={theme} defaultColorScheme="dark"` → `<BrowserRouter basename="/read">`
  → `<ReadRoutes/>`. `<BrowserRouter>`, not `createBrowserRouter`.
- `routes.tsx` (new) — `/:bookId` → `TableOfContentsPage` keyed on `bookId`; `/:bookId/:chapterId` →
  `ReaderChapterPage` keyed on `chapterId`; terminal `*` → `NotFoundPage`. Copies the
  `useParams()`-wrapper + `key={param}` idiom from `work/routes.tsx`.
- `pages/TableOfContentsPage.tsx` + `pages/tableOfContentsPageState.ts`
- `pages/ReaderChapterPage.tsx` + `pages/readerChapterPageState.ts`
- `pages/NotFoundPage.tsx`

Each page: one async-resource trio, `makeAutoObservable` in the constructor, an external
`load<X>(state, args, signal)` using `runInAction`, `observer` on the component, `useState(() => new
…State())`, one page-level `useEffect` with an `AbortController`. Copies `src/user/pages/BookHubPage.tsx` +
`bookHubPageState.ts` exactly (harvest §5).

Chapter body: `import Markdown from "react-markdown"` then `<Markdown>{chapter.text}</Markdown>` — no
plugins, no `components` prop (D11). `@mantine/tiptap` and every save/edit control must never be imported
anywhere under `frontend/src/read/`.

### `frontend/src/user/pages/` (delivered files, extended)

`bookshelfPageState.ts` gains a third async-resource trio `publicBooks` / `publicStatus` / `publicError`
loaded by the existing `loadBookshelf` in the same mount effect. `BookshelfPage.tsx` gains a third section
"Public books" below "Shared with me", each row linking via a plain `<a href={`/read/${book.id}`}>` — not a
react-router `<Link>` — matching the delivered `<a href={`/work/${book.id}`}>` idiom. Labelled empty state,
not a blank table.

## Implementation outline

1. Backend DTOs — `models/schemas/reader.py` with the five DTOs; remove `ReaderBookResponse` from
   `models/schemas/books.py`.
2. Backend service — `services/reader.py` (error types, `READER_VISIBLE_STATES`, the three functions);
   `db/books.py::list_public_for_reader`.
3. Backend routes — `routes/reader.py` (two routes + error mapping); remove `/read` route + service body
   from `routes/books.py` / `services/books.py`; add `GET /public` to `routes/books.py`; register
   `routes/reader.py` in `main.py`.
4. Frontend types + api — `types/reader.d.ts`, `api/reader.ts`.
5. Frontend reader SPA — `readGate.ts`, `main.tsx`, `App.tsx`, `routes.tsx`, both pages + states,
   `NotFoundPage`.
6. Frontend bookshelf extension — third trio in `bookshelfPageState.ts`, third section in
   `BookshelfPage.tsx`.

## Definition of done

1. `[test]` The table of contents contains exactly the book's `open` and `closed` chapters, in ascending
   `ordinal` order; `planned` and `closing` chapters are absent · US-030.AC-1
2. `[test]` `GET /{book_id}/read` response keys are exactly `{title, chapters}` and each chapter ref's keys
   are exactly `{id, title}` — no `sketch`, `summary`, `state`, `ordinal`, `version` · UC-029
3. `[test]` `GET /{book_id}/read/chapters/{chapter_id}`: a reader-visible chapter returns 200 with keys
   exactly `{id, title, text}`; a `planned` chapter, a `closing` chapter, an unknown id, a non-numeric id
   and a chapter belonging to another book all return the same 404 · UC-029
4. `[test]` A logged-in non-member of a private book gets 404 from both reader routes; the same caller on a
   public book gets 200 · US-030.AC-3
5. `[test]` A request with no token gets 401 from all three routes · US-030.AC-4
6. `[test]` `list_public_books` excludes the caller's own books, books they co-author, private books and
   non-`active` books, and includes another user's `active` `public` book · UC-029
7. `[test]` `GET /api/books/public` item keys are exactly `{id, title, description}` — no `owner_id`,
   `visibility`, `state`, `collaboration_mode`, timestamps · UC-029
8. `[test]` The table-of-contents page renders its chapters as links to `/:bookId/:chapterId` in order, and
   renders an author-facing refusal message (not a blank pane) when the load fails with 404 ·
   US-030.AC-1, US-030.AC-3
9. `[test]` The reader chapter page renders the chapter's saved body and exposes no edit affordance — no
   textbox and no save/edit control · US-030.AC-2
10. `[verify]` `routes/reader.py` is registered in `main.py`.
11. `[verify]` `GET /public` is declared before `GET /{book_id}` in `routes/books.py`.
12. `[verify]` `ReaderBookResponse` no longer appears in `models/schemas/books.py` and `get_reader_book` no
    longer appears in `services/books.py`.
13. `[verify]` The delivered `backend/tests/routes/test_book_read.py` still passes unchanged.
14. `[verify]` `enforceReadAccess()` is called before `createRoot` in `read/main.tsx`.
15. `[verify]` `basename="/read"` on the `BrowserRouter` in `read/App.tsx`.
16. `[verify]` Both reader routes plus the catch-all are declared in `read/routes.tsx`.
17. `[verify]` No `@mantine/tiptap` and no save/edit control is imported anywhere under `frontend/src/read/`.
18. `[verify]` The bookshelf's "Public books" section renders rows as `<a href="/read/<id>">`.
19. `[verify]` `vite.config.ts` is untouched (the `read` input and the `spaFallback` `/read` branch already
    exist).
20. `[verify]` `npm run build` and `npx tsc --noEmit` are clean.
21. `[manual/live]` As a logged-in non-member, reach a public book from the bookshelf's "Public books"
    section and deep-link both `/read/<id>` and `/read/<id>/<cid>` in the dev server.

## Test plan

**Tested:**
- DoD-1 — reader-visible chapter set + ordinal ordering — invariant: a wrong filter or sort silently leaks
  an author's working material or misorders reading order
- DoD-2 — `ReaderBookResponse` field exclusion — contract: the reader-safe projection is a structural
  guarantee, not a filter, and must stay exactly `{title, chapters}` / `{id, title}`
- DoD-3 — chapter route 404 collapse across five refusal sources — edge semantics: the enumeration-oracle
  design (D5) requires all five sources to be indistinguishable, which is easy to accidentally differentiate
- DoD-4 — private-vs-public book access — invariant: the authorization boundary this whole feature sits on
- DoD-5 — no-token 401 across all three routes — contract: the auth gate must hold uniformly
- DoD-6 — `list_public_books`'s four-condition exclusion — invariant: a multi-clause query (visibility,
  state, owner, membership NOT EXISTS) is exactly where a single wrong clause silently over- or
  under-includes
- DoD-7 — `PublicBookRef` field exclusion — contract: same structural-DTO guarantee as DoD-2, applied to
  discovery
- DoD-8 — TOC page rendering + refusal message — seam: the page/API integration point, and the one place a
  blank-pane regression would hide
- DoD-9 — reader chapter page body + no edit affordance — invariant: the build-time no-editor guarantee
  (D11) has a runtime-observable half (no textbox/save control) that a test can hold the line on

**Not tested (deliberate):**
- DTO field declarations — no logic; asserted over the wire by DoD-2 and DoD-7.
- Route wiring and `main.py` registration — framework wiring; `[verify]`, exercised transitively by DoD-1–7.
- `api/reader.ts` — three one-line `request<T>` delegations.
- `read/main.tsx`, `App.tsx`, `routes.tsx` — bootstrap and route table; framework wiring, `[verify]`.
- `resolveReadAccess` / `enforceReadAccess` — a verbatim structural mirror of the delivered `workGate.ts`;
  the behaviour it guards (US-030.AC-4) is asserted server-side by DoD-5, and a wrong redirect string is a
  one-line inspection.
- The bookshelf "Public books" section rendering and its `href` — the same table pattern as two delivered
  sibling sections; `[verify]`.
- Empty-state messages on the table of contents and the public list — `length === 0` string branches.
- `<Markdown>{text}</Markdown>` — third-party pass-through; DoD-9 fails without it.
- The `authz.require(access, Capability.read_book)` call — unreachable today: `resolve_book_access` already
  404s `AccessRole.none` and admin role resolution is deferred to FEAT-011, so a test would assert a branch
  that cannot be entered. Kept for spine consistency (D7).
- `NotFoundPage` and the chapter page's back-link — one static component and one `<a>`.

## Decisions taken

- **D1 — A member navigating to `/read/:bookId` gets the reader view.** No membership pre-check anywhere
  on the entry. Why: `Capability.read_book` already admits `{owner, co_author, reader}`, so it works for
  free and doubles as an author's "preview as a reader" path. Rejected: redirect a member into
  `/work/:bookId` — membership is not in the JWT, so this needs a probe request, a redirect path and its
  own error handling for a convenience nobody asked for.
- **D2 — The reader-visible chapter set is strictly `open` + `closed`.** `planned`/`closing` absent from
  the TOC and 404 from the chapter route. Why: the brief's and roadmap's stated scoping; a sketch is
  working material and must never reach a reader. Accepted cost: a chapter disappears from the TOC and
  404s for the duration of a close run (`open → closing → closed`), then reappears — no reader-facing
  information in the flicker, but real. Rejected: `open + closing + closed` — removes the flicker at the
  cost of diverging from the brief's stated set; the user kept the brief's wording.
- **D3 — The reader surface is its own module pair: `routes/reader.py` + `services/reader.py`.** The
  delivered `/read` route and service move in; URLs unchanged. Why: UC-029 is an exclusion list, and "what
  can ACT-006 reach" must be answerable from two files, not a twelve-route books module. Rejected: keep
  both in `routes/books.py` / `services/books.py` — zero churn, but interleaves the reader surface with
  member/owner routes.
- **D4 — Two reader routes, two purpose-built DTOs; the author's chapter routes are not reused.** Why: no
  existing route carries both a chapter's title and a reader-safe body — `ChapterTextResponse` has no
  title, `ChapterResponse` has a title but leaks `sketch`/`summary`. Widening `ReaderBookResponse.chapters`
  is free (zero frontend consumers, the delivered test's assertion still holds). Rejected: a single fat
  route returning the book with every chapter body inline — makes the TOC pay for every chapter body.
- **D5 — A not-reader-visible chapter answers 404, not 403, indistinguishable from four other refusals.**
  Why: a 403 would confirm the chapter exists at that id, letting a reader walk the id space to reconstruct
  the author's unwritten skeleton — the same enumeration-oracle reasoning `authorization.md` uses for a
  private book and the codex uses for an unknown/foreign entry id.
- **D6 — The state filter lives in the service over the full row list; no new `db/` function.** Why:
  `db/chapters.py`'s `list_by_book` takes no state filter and every state filter in the codebase today is
  service-side over the full list; book-sized chapter counts make a filtered query unjustified. Rejected: a
  `list_by_book_and_states` db function — only justified if row count made the full read expensive, which
  it does not.
- **D7 — Refusals are typed reasons mapped in the route, per house pattern.** `ReaderErrorReason` +
  `ReaderError(reason, message="")`, mapped via a module-local dict and `_map_reader_error`. Existence
  hiding is not re-derived — 404 for an unrelated private book and 401 for no token both come from upstream.
  `authz.require(access, Capability.read_book)` stays on both routes although unreachable today — it is the
  spine every book-scoped service binds to and the guard if the resolver ever admits another role. No new
  `Capability` and no new matrix row.
- **D8 — The reader entry copies `work`'s bootstrap idiom verbatim.** `readGate.ts` mirrors `workGate.ts`
  line for line, auth-only; `main.tsx` gates outside React before `createRoot`; `App.tsx` uses
  `<BrowserRouter basename="/read">`, never `createBrowserRouter`; `routes.tsx` uses the
  `useParams()`+`key={param}` wrapper idiom. No book-level pre-check on the client — the backend already
  refuses with 404, and a client pre-check would duplicate a rule that already has one implementation. Vite
  needs no change — `read` is already a Rollup input and `spaFallback` already branches `/read` (feature
  010).
- **D9 — Refusals render as author-facing messages, mapped from `ApiError.status`.** 404 → "not available
  to read", 403 → "no access", else → the `ApiError` message, chosen in the load function per
  `frontend.md`'s state/component split, never rendered as a blank pane.
- **D10 — The public→private flip: the next request refuses, nothing is invalidated.** A reader with the
  book open keeps the page already rendered; the next request (a chapter link, a reload) is refused 404 by
  `resolve_book_access`. No polling, no invalidation, no push channel — this is a decision about the gap
  UC-028's `_TBD:` leaves, not a resolution of the `_TBD:` itself (surfaced in `outcome.md`).
- **D11 — Read-only body rendering copies the delivered call exactly.** `import Markdown from
  "react-markdown"` then `<Markdown>{chapter.text}</Markdown>`, no plugins — inherited from
  `frontend-workspace.md`, not re-decided. `@mantine/tiptap` and every save control stay out of
  `src/read/` — the build-time property that makes "does a reader have an edit affordance?" answerable
  without running the app.
- **D13 — Public-book discovery is in this feature, against the brief's Scope Out.** `[confirmed: user]`,
  reaffirmed after the orchestrator raised it. A harvest established that no listing surface can surface a
  public book to a non-member today, and `/read` has zero references anywhere in the frontend — the reader
  as originally scoped would be reachable only by hand-typing a URL, which defeats ACT-006's non-member
  status. Cost: this resolves UC-029's discoverability `_TBD:` by implementation rather than raising it, a
  divergence from `docs/architecture/CLAUDE.md`'s "raise it, don't resolve it" rule — surfaced in
  `outcome.md` → Observations. Rejected: defer to feature `023` after `/product-spec` mints a use case (the
  brief's own recommendation, and the orchestrator's — rejected by the user); a `Read` link on
  already-listed public books only (~10 LoC, but serves only the owner's "view as reader" path, nothing for
  an actual non-member reader).
- **D14 — `GET /api/books/public`: a reader-safe list, four exclusions, authenticated but not book-scoped.**
  Cannot use `Depends(authz.book_access)` — no `book_id` to resolve a role against; uses
  `Depends(get_current_user)` like the two delivered list routes. The four-clause query (visibility ==
  public, state == active, owner_id != caller, no `BookMember` row) excludes the caller's own books (already
  visible in "My books" / "Shared with me" — disjointness across the three sections is a testable
  invariant) and non-`active` books (archived is still readable by direct link — this feature changes no
  authorization — but discovery-feed listing contradicts UC-023's "preserved and reversible"; filtering on
  `active` also excludes `quarantined`/`destroyed` for free). Fields deliberately absent: `owner_id`,
  `visibility`, `state`, `collaboration_mode`, timestamps. Rejected: carrying the owner's display name —
  useful, but needs a `users` join and answers a question ("does a public book expose its author's
  username?") nobody has asked.
- **D15 — The discovery route is declared in `routes/books.py`; its logic lives in `services/reader.py`.**
  `/public` and `/{book_id}` collide at the same path depth under the shared prefix; declaring `/public` in
  a second router would make `main.py`'s include order load-bearing and invisible, and the failure (a 422
  from `book_id: int` parsing `"public"`) would read as a bug in the wrong file. Declaring it beside
  `/shared` makes static-before-dynamic provable by reading one file. The tension with D3 is bounded: the
  route itself is ~12 lines of delegation; every line of reader logic and every reader DTO still lives in
  the reader module pair.
- **D16 — The bookshelf gains a third section, a third trio, a full-page-load link.** "Public books" below
  the two delivered sections, fed by a third trio in the delivered `bookshelfPageState.ts`. Each row links
  via a plain `<a href>`, not a `<Link>` — crossing Vite entries is a full page load. Labelled empty state,
  not a blank table.

## Out of scope

- Search / filter / pagination / sort on the public list.
- `planned` chapters and every sketch, through any route or DTO.
- Any third route under `/read` — no codex, state notes, flags, book state, settings or chat, ever.
- Anonymous access — public is read-only to logged-in users only.
- The nginx `/read` static root — `nginx/` and both `docker-compose*.yml` do not exist in this repository;
  retrofitted when that serving layer is first created.
- The Shell's `/books/:bookId` book hub and its read-only codex/continuity mirrors — a different, unbuilt
  entry.
- Any change to authorization — no new `Capability`, no `_CAPABILITY_MATRIX` row, no resolver change.
- Owner display names on the public list.
- Quarantined/destroyed book gates (deferred to FEAT-011).
- Archived-book read gating — reads are deliberately never archive-gated (feature `015` decision D10); this
  feature inherits that unchanged.

## Risks

- The nine-item `[test]` set is exact and gates `red-gate-verifier` — a test-coder adding a tenth test or
  missing one of the nine fails the gate; keep the DoD numbering stable through skeleton and test-coder
  hand-off.
- `READER_VISIBLE_STATES` and the 404 collapse (D5) both depend on `ChapterState` importing cleanly from
  `models/chapter.py` into `services/reader.py` — a stale import path would silently widen or narrow the
  reader-visible set.
- Declaration order in `routes/books.py` (`/public` before `/{book_id}`) is load-bearing and easy to get
  backwards during a later edit — no test catches it directly; only `[verify]` DoD-11 and the live 422
  failure mode would.
- The frontend build-time no-editor guarantee (`@mantine/tiptap` absent from `src/read/`) has no automated
  enforcement beyond `[verify]` inspection and `npm run build` — a future shared component that
  transitively imports the editor would slip past the test suite.
