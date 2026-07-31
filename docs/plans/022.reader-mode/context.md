# Context — 022.reader-mode

Self-sufficient feature-wide facts. No conversation history assumed. Evidence sources:
`docs/.cache/ultra/022.reader-mode/harvest.md` (two harvester reports, exact quoted signatures) and
`docs/.cache/ultra/022.reader-mode/design-notes.md` (D1..D16, decisions + rejected options).

## Goal

A logged-in user who is not a member of a public book can find it, open it, get an ordered table of
contents of its written chapters, follow one, and read that chapter's saved text read-only — with no edit
affordance anywhere. A private book refuses them; a logged-out visitor is sent to log in.

## Product basis — realizes FEAT-007 (reader half): UC-029, US-030

**UC-029 — Read a public book** (ACT-006). Preconditions: book visibility public, reader logged in, not a
member. Main flow: reader opens the book → system shows table of contents (chapter names with links) →
reader selects a chapter → system returns that chapter's text, read-only. Exception flow: private book →
refused; not logged in → refused, no anonymous surface. Postconditions: read-only, nothing beyond TOC and
chapter text (no codex, state notes, flags, book-state view, settings, chat — the book's codex is never
included, members-only even on a public book). Carries two open `_TBD:` markers: whether public books are
discoverable, and whether "table of contents" needs its own id (kept as a facet of UC-029, no new id).

**US-030 — Logged-in reader opens a public book read-only.** Status: partially delivered.
- **US-030.AC-1** — Given a public book and a logged-in non-member, when they open it, then its content is
  shown.
- **US-030.AC-2** — Given the same, when they open it, then no edit action is available.
- **US-030.AC-3** — Given a private book, when a logged-in non-member attempts to open it, then access is
  refused.
- **US-030.AC-4** — Given a public book, when a user who is not logged in attempts to open it, then access
  is refused.

## Current code state (from harvest.md)

- `GET /api/books/{book_id}/read` exists today in `routes/books.py:125-138` → `services/books.py::get_reader_book:187-202`.
  Its body: `ReaderBookResponse(title=book.title, chapters=[])` — **hardcoded empty list, unconditionally**.
  `ReaderBookResponse` (`models/schemas/books.py:108-127`) is `{title: str, chapters: list[str]}`.
- `authz.book_access` / `resolve_book_access` (`services/authz.py:206-255`) already produce `BookAccess`
  and already 404 a private book with no relationship (existence hiding) before any service runs, and 401
  comes from `get_current_user` upstream. `Capability.read_book` already admits
  `{owner, co_author, reader}` (`_CAPABILITY_MATRIX`, `authz.py:121-123`).
- Chapter reads (`routes/chapters.py`) already reuse `read_book`; none of the three chapter read paths call
  `_require_not_archived` — reads are never archive-gated (feature `015` decision D10, inherited unchanged
  here — see Decisions taken D10 in `plan.md`, distinct feature-022 D10 about the public→private flip).
- `db/chapters.py` has exactly five functions; `list_by_book(book_id)` returns every row, no state filter.
- `ChapterState` (`models/chapter.py:24-31`): `planned | open | closing | closed`.
- **No discovery surface exists anywhere.** `db/books.py` has exactly five functions; the only two
  list-shaped ones (`list_by_owner`, `list_shared`) are hard-scoped to `owner_id` / an explicit
  `BookMember` row. No route queries `visibility == public`. `BookshelfPage` renders exactly "My books" and
  "Shared with me". **`/read` has zero references anywhere in `frontend/src`.**
- The frontend `read/` entry is 2 files, 36 lines total (harvest §2 of report 2): a Mantine-themed stub
  `App.tsx` with no router, no gate, no data, and a 9-line `main.tsx` calling `createRoot` unconditionally.
  `vite.config.ts` already carries the `read` Rollup input and the `spaFallback` `/read` branch (feature
  010) — neither needs touching.
- No `ReaderBookResponse` type or any `.../read` call exists anywhere in `frontend/src/` — the backend DTO
  widening in this feature breaks zero frontend consumers.

## Architecture constraints that bind

- **4-layer backend separation** (`CLAUDE.md`): `routes/` HTTP-only; `services/` business logic, no
  `session`/`select()`/ORM; `db/` session-free data access; `models/` tables + Pydantic schemas. Import
  direction `routes → services + db`, `services → db`.
- **Existence hiding**: a private book with no caller relationship is **404**, produced once in
  `resolve_book_access`, never re-derived. A not-reader-visible chapter is also **404** here (this
  feature's own D5), for the same enumeration-oracle reason `authorization.md` → "Failure modes" states for
  books and `quick-reference.md:125` states for the codex.
- **Refusal plumbing house pattern**: a service-local `<X>ErrorReason(str, enum.Enum)` + `<X>Error(Exception)`
  with `__init__(self, reason, message="")`, mapped in the route via a module-local `dict[Reason, int]` and
  `_map_<x>_error`, mirroring `services/chapters.py` / `routes/chapters.py:94-103`.
- **Frontend**: MobX only, `observer` on every component, no custom hooks, no `useCallback`/`useMemo`/
  `useReducer`, `useEffect` only at page level. State = async-resource trio (`data`/`dataStatus:
  'idle'|'loading'|'ready'|'error'`/`dataError`), external `(state, args, signal)` load functions using
  `runInAction`, `useState(() => new ...State())`. Page = route = fresh state instance
  (`key={param}` remount). All HTTP in `src/api/`.
- **The reader is its own Vite entry** (`frontend-workspace.md` → "Why the reader is its own entry"):
  ACT-006 shares nothing with authoring; serving the authoring bundle would ship every editing surface to
  someone who may never see any of it, making "does a reader have an edit affordance?" a build-time
  property instead of a runtime one. `@mantine/tiptap` and every save control must never be imported under
  `src/read/`.
- **Bootstrap idiom to copy verbatim**: `work/main.tsx` runs its gate outside React, before `createRoot`;
  `work/App.tsx` uses `<BrowserRouter basename="/work">`, never `createBrowserRouter`; `work/routes.tsx`
  wraps item routes in a `useParams()` reader that applies `key={param}`.
- **Crossing Vite entries is a full page load** (`frontend-workspace.md` → "Accepted costs") — the
  bookshelf's link into `/read` is a plain `<a href>`, never a react-router `<Link>`.
- **`react-markdown`'s no-plugin default is inherited, not re-decided** — `import Markdown from
  "react-markdown"` then `<Markdown>{text}</Markdown>`, no `remarkPlugins`/`rehypePlugins`/`components` prop.

## Pointers

- Harvest: `docs/.cache/ultra/022.reader-mode/harvest.md` — exact quoted signatures, the entire delivered
  `read/` entry, the `work` bootstrap trio, the `BookHubPage` page-state pattern to copy.
- Design notes: `docs/.cache/ultra/022.reader-mode/design-notes.md` — D1..D16, every rejected option and
  why. `plan.md` → `## Decisions taken` transcribes these.
- Roadmap brief: `docs/plans/022.reader-mode/brief.md` — note its Scope Out excludes discovery; D13
  overrides that with the user's confirmed decision to build discovery here.
