# 010.working-page — feature context

Feature-wide context. Step-specific facts live in each `<SSS>.context.md`; nothing is repeated
between the two files. The feature definition is `brief.md` (read-only).

## Goal

Ship the working-page SPA shell an author opens for a book: the `work` Vite entry (plus a stub
`read` entry), the three-region layout (navigator · content pane · empty chat-pane slot), the
seven-entry navigator, the Book-state landing view, the content-pane subject model, and the
per-item `localStorage` restore buffer.

## Scope decisions (user-confirmed — do not reopen)

1. **Frontend-only.** No file under `backend/` is touched by any step. Every navigator section other
   than the book itself has no backing endpoint (feature 008 landed tables and `db/` modules only;
   the mounted routers are `health, auth, books, admin_users, admin_llm_servers, admin_db`), so the
   lists are empty-state placeholders naming their owning feature.
2. **The restore buffer ships as a pure module.** Nothing editable is wired to it in this feature —
   nothing is editable until `013.codex` / `015.chapter-writing-free-mode`. It is unit-tested
   against US-107.AC-1..4 as a module.
3. **nginx is out of scope.** `nginx/` and both `docker-compose*.yml` do **not exist in this
   repository**; the root `CLAUDE.md` project-structure block is aspirational there.
   `frontend/vite.config.ts` is the only serving surface this feature touches.
4. **Four steps**, in order: `001.work-entry-scaffold` → `002.workspace-shell` →
   `003.book-state-landing` → `004.content-pane-subject-and-buffer`.

### Deliberately deferred (say so, don't build it)

| Deferred | Owner | Why |
|---|---|---|
| US-106.AC-2 / AC-3 — per-chapter title + summary + after-chapter notes, active warnings beside the chapter | `016.chapter-close-continuity` | No backing data and no endpoint exists |
| The stale-base **reconciliation / divergence view** for a buffered draft | the first editable subject (`013.codex` / `015.chapter-writing-free-mode`) | Nothing is editable here, so there is no draft to reconcile |
| Everything inside the chat pane | `011.chat-panel` | The slot exists and stays empty (`frontend-workspace.md`) |
| Chapter / codex / variants item content | `014.chapter-skeleton`, `013.codex`, `018.chapter-history-variants` | No endpoints; routes exist, views are placeholders |
| nginx serving of `/work` and `/read` | whichever feature first creates the serving layer | That layer does not exist in the repo |

**Known deviation from `frontend-workspace.md`'s current wording.** That document says the manual
reconciliation path "**ships with the buffer** and is not optional". This feature ships the buffer
without it, by the user's explicit decision — there is no editable subject to reconcile against. The
wording change is recorded for the architect in `outcome.md`; do not treat the doc sentence as a
missing deliverable.

## Architecture sources

- `docs/architecture/frontend-workspace.md` — the primary design source: five Vite entries, the
  `/work` route map, the three regions, the navigator, the editability table, the buffer design.
- `docs/architecture/frontend.md` — the enforced MobX / Mantine / `api/` rules every step obeys,
  including the sanctioned persisted-state exception the buffer relies on.
- `docs/architecture/domain-chapter.md` — the `planned|open|closing|closed` state machine and the
  version / 409 contract the buffer records a base version against.
- `docs/architecture/domain-book.md` — the `Book` field list the landing view aggregates.

## The `/work` route map (all four steps touch `src/work/routes.tsx`)

| Route | Content pane | Added by |
|---|---|---|
| `/work/:bookId` | redirect → `/work/:bookId/state` | 003 |
| `/work/:bookId/state` | Book state (landing view, US-106.AC-1) | 003 |
| `/work/:bookId/chapters`, `/chapter/:id` | chapter list / one chapter | 004 |
| `/work/:bookId/characters`, `/locations`, `/facts`, `/codex/:id` | codex lists by `kind` / one entry | 004 |
| `/work/:bookId/variants`, `/variants/:chapterId` | variants list / one chapter's variants | 004 |
| `/work/:bookId/chats` | chat list — picking one opens in the **chat pane**, route stays put | 004 |
| `*` | not-found (terminal catch-all) | 001 |

**The chat id is never in the URL.** The chat pane resolves its own active chat per book and does
not participate in routing.

## Cross-cutting constraints

- **The `work` entry follows the *admin* SPA pattern, never the user SPA's.** `src/user/App.tsx`'s
  render-phase `window.location.href` redirect is the old, untestable pattern: no `basename`, and
  `UserRoutes` is not `observer`-wrapped. The admin pattern (gate enforced outside React in
  `main.tsx`, `basename` on `BrowserRouter`, `observer`-wrapped route table with a terminal
  catch-all) is the one to mirror.
- **This feature introduces the repo's first `<Outlet/>`.** `AdminShell` takes `children` and states
  in a comment that it "introduces no `<Outlet/>` into a repo that has none". The workspace shell
  cannot do that: `frontend-workspace.md` requires it to be keyed on `:bookId` and to **not remount**
  when the subject route changes, which `children` cannot express. The split is deliberate — admin
  keeps `children`, work uses `<Outlet/>` — and is recorded in `outcome.md`.
- **`observer` on every component**, no exceptions. State is data + `get` computeds; every load is an
  external `(state, args, signal)` function using `runInAction`; every loadable is an async trio
  (`x` / `xStatus` / `xError`). No custom `useX` hooks, no `useCallback` / `useMemo` / `useReducer`;
  `useEffect` only at the page/shell mount, empty deps.
- **Links:** react-router `<Link>` / `<NavLink>` for navigation *inside* the `work` SPA (the
  `basename="/work"` resolves them); a **plain `<a href>`** for anything crossing entries (the
  bookshelf → `/work/:bookId` link is a full page load, an accepted cost in
  `frontend-workspace.md`). Never `navigateTo` for in-SPA navigation — that helper is the mockable
  seam for cross-SPA redirects only.
- **All HTTP stays in `src/api/`.** No new `api/` module is needed: `api/books.ts` already exports
  `getBookDetail(bookId, signal?)`.
- **"Warning" is the author-facing word for a flag.** Entity, table, DTO and API stay `flag`; every
  string an author reads says *warning*.

## Known wire gap — `BookResponse`

`domain-book.md` lists `system_prompt` and `active_notes` on the `Book` entity, but
`src/types/books.d.ts`'s `BookResponse` / `BookDetailResponse` carry **neither**. The Book-state
landing view can therefore only render what the DTO actually carries; the state-notes region ships
as a labelled empty state. Recorded for the architect in `outcome.md`.

## Testing facts shared by every step

- `frontend/vitest.config.ts`: jsdom, **`globals: false`** — every spec imports `describe/it/expect/vi`
  from `"vitest"`; `include: ["tests/**/*.test.{ts,tsx}"]`; `restoreMocks` / `clearMocks` true.
- `frontend/tests/setup.ts` adds jest-dom matchers, stubs `matchMedia` / `ResizeObserver` /
  `scrollIntoView`, and in `afterEach` runs `cleanup()` + **`localStorage.clear()`**.
- `frontend/tests/support/render.tsx` exports `renderWithProviders(ui, { route? })` — wraps in
  `<MantineProvider theme={theme} env="test">` (the `env="test"` disables portals and transitions and
  is load-bearing) and, when `route` is given, in `<MemoryRouter initialEntries={[route]}>`. Routes
  passed in are **basename-stripped** (`/:bookId/state`, not `/work/:bookId/state`).
- Existing specs mock only `../../src/auth` and `../../src/utils/navigate`, module-factory form with
  `vi.fn()` members, then `vi.mocked(...).mockReturnValue(...)`. **No spec yet mocks an `src/api/*`
  module** — this feature establishes that convention (first use is step 001; see `001.context.md`).
- There are no `tests/user/` specs today; step 001 creates that folder.

## Build and test gates (root `CLAUDE.md`)

Frontend only. Every step's DoD carries these:

- `cd frontend && npm run build` — `tsc` + `vite build`, must be clean.
- `cd frontend && npm test` — Vitest, must be green.
- `cd frontend && npm run test:types` — typechecks `tests/` via `tsconfig.test.json`; required in
  every step, since every step adds specs.

`frontend/tsconfig.json` has `include: ["src"]` only, so a broken spec can never break the bundle —
`npm run test:types` is the only program covering `tests/`.

## Step sizing

`002` runs to the top of the 50–200 line band and `004` will likely exceed it slightly. Both are the
user's explicit call: `004` deliberately carries the subject model and the buffer together because
the buffer's key scheme is expressed in the subject vocabulary. Do not split either.

## Product ids

Delivered here: **UC-090 / US-105** (navigator; AC-1 partially — lists are empty states, AC-3 by
routing structure), **UC-091 / US-106.AC-1** (Book state is the landing view), **UC-092 / US-107**
(restore buffer, AC-1..AC-4, against the module), **UC-083 / US-097.AC-1/AC-2/AC-3** (content-pane
subject and the editable-vs-read-only rule). Deferred: US-106.AC-2/AC-3, US-105.AC-2/AC-4 beyond
routing. US-106.AC-4 is `_TBD:` in product — `domain-book.md`'s field list is the substitute.
