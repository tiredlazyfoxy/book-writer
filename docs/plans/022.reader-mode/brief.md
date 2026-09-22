# 022.reader-mode — Reader mode
<!-- roadmap:start -->
- **Stage:** 7.reader · **Track:** multi-step · **Size:** M
- **Delivers:** FEAT-007 (reader half): UC-029, US-030
- **Depends on:** `009.books`, `015.chapter-writing-free-mode`

## Definition
A logged-in user who is not a member of a public book can finally read it. They
open the book's reader page and get an ordered table of contents — the titles of
the chapters that have been written — and following one shows that chapter's
text, read-only, with no edit affordance anywhere on the page. A private book
refuses them, and a logged-out visitor is sent to log in, because public means
read-only to any *logged-in* user and there is no anonymous surface anywhere in
the system. Nothing else about the book is reachable from here: no codex, state
notes, flags, book state, settings or chat. This closes FEAT-007's last gap —
`009.books` shipped the access-controlled backend projection, and today
`frontend/src/read/` is a 47-line placeholder that says the reader is not built.

## Scope
**In:**
- The `read` Vite entry becomes a real SPA: an auth gate that sends a logged-out
  visitor to log in, a router, and the two designed routes — `/read/:bookId`
  (table of contents) and `/read/:bookId/:chapterId` (chapter text).
- The table of contents lists the book's `closed` and `open` chapters in
  reading order, by title, each linking to its text.
- The chapter page renders the chapter's **saved** body read-only.
- The reader-facing projection carries what a linked table of contents needs —
  chapter **ids**, not just names. `ReaderBookResponse.chapters` is
  `list[str]` today and returns `[]` unconditionally.
- Refusals are shown as refusals: a private book, a book that does not resolve,
  and a chapter that is not reader-visible each produce an author-facing
  message rather than a blank page or a crash.

**Out:**
- **Discovering, browsing or searching public books.** Product carries this as
  an open `_TBD:` and no surface exists on either side; a reader arrives by a
  direct link. If it is wanted it is its own feature, after `/product-spec`
  mints a use case for it.
- **`planned` chapters, and every sketch.** A sketch is the author's working
  material; it must not reach a reader through any route or DTO.
- Everything on UC-029's exclusion list — codex, state notes, flags, book
  state, settings, chat. **There must never be a third route** under `/read`.
- **Anonymous access.** Public is read-only to logged-in users only.
- **The nginx `/read` static root.** `nginx/` and both `docker-compose*.yml` do
  not exist in this repository; the static root is added when that serving
  layer is first created, not retrofitted here.
- The Shell's `/books/:bookId` book hub and its read-only codex / continuity
  mirrors — separate unbuilt surfaces on a different entry.
- Any change to authorization. `Capability.read_book` already admits the
  `reader` role and both chapter read paths already use it.

## Open questions for the planner
- **Which route owns the table of contents.** Two candidates already exist and
  overlap: `GET /api/books/{book_id}/read` (reader-safe DTO, but `chapters` is
  a name-only placeholder) and `GET /api/books/{book_id}/chapters` (already
  admits readers via `read_book`, but returns full `ChapterResponse` — which
  carries `sketch` and `summary` and would leak both to a reader). One of them
  should own it; a reader-safe shape is required either way.
- **Where the `closed` + `open` filter lives** — in the reader projection, or
  as a filter on the shared chapter read path — and whether the chapter text a
  reader gets comes from the same `.../chapters/{id}/text` route the author
  uses. No state filter exists anywhere in the codebase today.
- **What the reader entry does for a member.** Does a logged-in owner or
  co-author who navigates to `/read/:bookId` get the reader view, or get
  redirected into the workspace?
- **The public→private flip.** Product leaves `_TBD:` whether a reader with the
  book open loses access immediately or finishes their view. Minimum
  behaviour — the next request refuses — needs stating either way.
- **Which gate idiom the entry copies.** `frontend/src/work/workGate.ts` is a
  66-line auth-only `resolve`/`enforce` pair (book membership is not in the
  JWT), and `work/`'s `App`/`routes`/`main` trio is the router idiom. Whether
  the reader needs any book-level pre-check at all, given the backend refuses
  on its own, is the planner's to settle.
<!-- roadmap:end -->
