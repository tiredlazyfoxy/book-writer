# Feature 010 — working-page

| Step | File                                     | Status  | Verifier | Date |
|------|------------------------------------------|---------|----------|------|
| 001  | `001.work-entry-scaffold.md`             | done    | PASS     | 2026-07-25 |
| 002  | `002.workspace-shell.md`                 | done    | PASS     | 2026-07-25 |
| 003  | `003.book-state-landing.md`              | done    | PASS     | 2026-07-25 |
| 004  | `004.content-pane-subject-and-buffer.md` | done    | PASS     | 2026-07-25 |

## Files Changed

### Step 001 — work entry scaffold
- `frontend/src/work/workGate.ts` — filled auth-only resolver + enforcer bodies
- `frontend/src/work/App.tsx` — MantineProvider(dark) > BrowserRouter(basename="/work") > WorkRoutes
- `frontend/src/work/routes.tsx` — observer route table with terminal catch-all NotFoundPage
- `frontend/src/work/pages/NotFoundPage.tsx` — not-found page with plain `<a href="/">` back to bookshelf
- `frontend/src/read/App.tsx` — Mantine-themed reader placeholder (no router/gate/data)
- `frontend/src/user/pages/BookshelfPage.tsx` — title cell wrapped in plain `<a href="/work/<id>">`
- `frontend/vite.config.ts` — verified `work`/`read` inputs + spaFallback branches (skeleton-written, unchanged)
- `frontend/work/index.html`, `frontend/read/index.html` — verified entry HTML (skeleton-written, unchanged)
- `frontend/src/work/main.tsx`, `frontend/src/read/main.tsx` — verified bootstrap (skeleton-written, unchanged)

### Step 002 — workspace shell
- `frontend/src/work/components/shell/navItems.ts` — populated the seven UC-090 nav entries + filled `workNavHref` / `isWorkNavItemActive` (segment-boundary active match, extra-segment aware)
- `frontend/src/work/components/shell/WorkNavigator.tsx` — `NavLink`+`RouterLink` render of the seven entries, active via the predicate, one `useLocation`
- `frontend/src/work/components/shell/ChatPaneSlot.tsx` — placeholder naming `011.chat-panel` as owner
- `frontend/src/work/components/shell/workspaceShellState.ts` — filled `loadWorkspaceBook` (async-trio loader, abort-guard, `ApiError` → author-facing message)
- `frontend/src/work/components/shell/WorkspaceShell.tsx` — three-region `AppShell` (navigator / `<Outlet/>` centre / chat slot), mount-only book load, title + loading + error chrome
- `frontend/src/work/routes.tsx` — verified frozen `/:bookId` + nested catch-all wiring (skeleton-written, unchanged)

### Step 003 — book-state landing view
- `frontend/src/work/pages/bookStatePageState.ts` — filled the five `get` computeds (labels reuse `COLLABORATION_MODE_OPTIONS`/`VISIBILITY_OPTIONS`, local `BookState` label map, member list/count) + `loadBookState` async-trio loader (mirrors `loadWorkspaceBook`)
- `frontend/src/work/pages/BookStatePage.tsx` — `observer` page: mount-load, four regions (book fields with inline timestamp format, members, state-notes empty state, `016.chapter-close-continuity` empty state using "warning"), loading/error trio states
- `frontend/src/work/routes.tsx` — verified frozen index-redirect + `state` child wiring (skeleton-written, unchanged)

### Step 004 — content-pane subject model and restore buffer
- `frontend/src/work/subject.ts` — filled `resolveSubjectPaneTarget` (`chats`→"chat", else "content"), `resolveEditability` (the `frontend-workspace.md` table: `open` chapter + non-archived codex editable whole; `closing`/`planned`/`closed` chapter, archived codex, every list read-only with author-facing reasons; Book state = `book-state-notes`), and the writer-agnostic `checkWritePermission` deriving allow/deny from `resolveEditability`
- `frontend/src/work/restoreBuffer.ts` — filled `restoreBufferKey` (prefixed `(bookId, kind, id)` key), total `readBuffer` (null on absent/non-JSON/wrong-shape, never throws), `writeBuffer` (stamps ISO `writtenAt`; on quota, evicts own-prefix buffers oldest-first one-at-a-time with retry between, never the current key, names evicted keys), `clearBuffer`
- `frontend/src/work/pages/SubjectPlaceholderPage.tsx` — verified skeleton-written placeholder compiles (unchanged)
- `frontend/src/work/routes.tsx` — verified skeleton-written nine child routes + item wrappers + owner labels compile (unchanged)

## Skeleton

### Step 001 — frozen interface (2026-07-25)
- `frontend/src/work/workGate.ts` — `type WorkAccessDecision = { allowed: true } | { allowed: false; redirectTo: string }` — new
- `frontend/src/work/workGate.ts` — `resolveWorkAccess(): WorkAccessDecision` — new (auth-only; body throws)
- `frontend/src/work/workGate.ts` — `enforceWorkAccess(): boolean` — new (body throws)
- `frontend/src/work/App.tsx` — `App` — new (`observer`-wrapped no-prop FC; body throws)
- `frontend/src/work/routes.tsx` — `WorkRoutes` — new (`observer`-wrapped no-prop FC; body throws)
- `frontend/src/work/pages/NotFoundPage.tsx` — `NotFoundPage` — new (`observer`-wrapped no-prop FC; body throws)
- `frontend/src/read/App.tsx` — `App` — new (`observer`-wrapped no-prop FC; body throws)
- `frontend/src/work/main.tsx` — no exported symbol; bootstrap wiring (mirror of `src/admin/main.tsx`), gates via `enforceWorkAccess()` before `createRoot`
- `frontend/src/read/main.tsx` — no exported symbol; bootstrap wiring (mirror of `src/login/main.tsx`), no gate/router
- `frontend/work/index.html`, `frontend/read/index.html` — new entry HTML (title + module src only); written in full (no behavior)
- `frontend/vite.config.ts` — added `work` / `read` Rollup inputs and `/work` / `/read` `spaFallback` branches before the catch-all `else`; written in full (mechanical)
- `frontend/src/user/pages/BookshelfPage.tsx` — **no interface change made.** The plain-anchor to `/work/<id>` is pure render behavior with no new/changed symbol; writing it now would satisfy DoD-4's assertion and defeat true-red. Left for the coder to fill.
- Caller-compile edits (out of Source-files scope): None.

### Step 002 — frozen interface (2026-07-25)

`frontend/src/work/components/shell/navItems.ts`
- `type WorkPaneTarget = "content" | "chat"` — new
- `interface WorkNavItem { path: string; label: string; icon: Icon; extraActiveSegments?: readonly string[]; paneTarget: WorkPaneTarget }` — new (`Icon` from `@tabler/icons-react`)
- `const WORK_NAV_ITEMS: readonly WorkNavItem[]` — new; declared **empty**, so DoD-1 fails true-red. Coder populates the seven entries (Book state · Characters · Locations · Facts · Chapters · Variants · Chats) with labels, icons, extra segments (Chapters → `/chapter`), pane targets (Chats → `"chat"`, rest `"content"`).
- `workNavHref(bookId: string, item: WorkNavItem): string` — new (body throws)
- `isWorkNavItemActive(pathname: string, bookId: string, item: WorkNavItem): boolean` — new (body throws)

`frontend/src/work/components/shell/WorkNavigator.tsx`
- `interface WorkNavigatorProps { bookId: string }` — new
- `WorkNavigator` — new (`observer`-wrapped FC taking `WorkNavigatorProps`; body throws)

`frontend/src/work/components/shell/ChatPaneSlot.tsx`
- `ChatPaneSlot` — new (`observer`-wrapped no-prop FC; body throws)

`frontend/src/work/components/shell/workspaceShellState.ts`
- `class WorkspaceShellState` — new; observable fields frozen: `bookDetail: BookDetailResponse | null`, `bookDetailStatus: "idle"|"loading"|"ready"|"error"`, `bookDetailError: string | null`, `navbarOpened: boolean`; `makeAutoObservable(this)` in ctor, no methods.
- `loadWorkspaceBook(state: WorkspaceShellState, bookId: string, signal?: AbortSignal): Promise<void>` — new (body throws)

`frontend/src/work/components/shell/WorkspaceShell.tsx`
- `WorkspaceShell` — new (`observer`-wrapped no-prop FC; reads `:bookId` via router; body throws)

`frontend/src/work/routes.tsx`
- `WorkRoutes` — changed (was: single terminal `path="*"` → `NotFoundPage`). Now: `/:bookId` → `WorkspaceRoute` with a nested `path="*"` → `NotFoundPage`; terminal top-level `path="*"` → `NotFoundPage` **preserved**. Route wiring only; reachable behavior lives in the throwing `WorkspaceShell`, so no DoD assertion is satisfied by the wiring.
- `WorkspaceRoute()` — new module-local wrapper (not exported); reads `:bookId`, renders `<WorkspaceShell key={bookId} />` (mirrors `BookSettingsRoute`).
- Caller-compile edits (out of Source-files scope): None.

Typecheck: `npx tsc --noEmit` clean (exit 0).

### Step 003 — frozen interface (2026-07-25)

`frontend/src/work/pages/bookStatePageState.ts`
- `class BookStatePageState` — new; observable trio frozen: `bookDetail: BookDetailResponse | null`, `bookDetailStatus: "idle"|"loading"|"ready"|"error"`, `bookDetailError: string | null`; `makeAutoObservable(this)` in ctor. NO fetch methods, NO setters.
- `get collaborationModeLabel(): string` — new computed (body throws)
- `get visibilityLabel(): string` — new computed (body throws)
- `get lifecycleStateLabel(): string` — new computed (body throws)
- `get memberList(): BookMemberResponse[]` — new computed (body throws)
- `get memberCount(): number` — new computed (body throws)
- `loadBookState(state: BookStatePageState, bookId: string, signal?: AbortSignal): Promise<void>` — new external loader (body throws)

`frontend/src/work/pages/BookStatePage.tsx`
- `BookStatePage` — new (`observer`-wrapped no-prop FC; reads `:bookId` via router; body throws)

`frontend/src/work/routes.tsx`
- `WorkRoutes` — changed (was: `/:bookId` shell + nested `path="*"` → `NotFoundPage`; terminal `path="*"` → `NotFoundPage`). Now the `/:bookId` shell route also nests `<Route index element={<Navigate to="state" replace />} />` and `<Route path="state" element={<BookStatePage />} />` **ahead of** its preserved nested catch-all; terminal top-level catch-all preserved. Route wiring only; the rendered `BookStatePage` throws, so no DoD assertion is satisfied by the wiring.
- Caller-compile edits (out of Source-files scope): None.

Typecheck: `npx tsc --noEmit` clean (exit 0); `npm run build` clean.

### Step 004 — frozen interface (2026-07-25)

`frontend/src/work/subject.ts` (new module)
- `type SubjectKind = "book-state" | "chapters" | "chapter" | "characters" | "locations" | "facts" | "codex-entry" | "variants" | "chapter-variants" | "chats"` — new (three codex lists are distinct kinds; `codex-entry` is the single entry; `chapter-variants` is one chapter's variants)
- `type ChapterState = "planned" | "open" | "closing" | "closed"` — new
- `interface LoadedSubject { kind: SubjectKind; entityId?: string; chapterState?: ChapterState; codexArchived?: boolean }` — new
- `type EditableRegion = "none" | "whole" | "book-state-notes"` — new
- `interface Editability { editable: EditableRegion; readOnlyReason: string | null }` — new
- `type WriteRegion = "whole" | "book-state-notes"` — new
- `interface WriteDecision { allowed: boolean; reason?: string }` — new
- `resolveSubjectPaneTarget(subject: LoadedSubject): WorkPaneTarget` — new (`WorkPaneTarget` reused from `components/shell/navItems`; body throws)
- `resolveEditability(subject: LoadedSubject): Editability` — new (implements `frontend-workspace.md`'s table; body throws)
- `checkWritePermission(subject: LoadedSubject, region: WriteRegion): WriteDecision` — new — the single author/assistant write gate (US-097.AC-2 / US-059.AC-3); nothing calls it yet; body throws

`frontend/src/work/restoreBuffer.ts` (new module, `auth.ts`-style plain functions)
- `const RESTORE_BUFFER_KEY_PREFIX = "bookwriter.restore-buffer"` — new
- `type BufferBaseVersion = number | string` — new (chapter `version` number or codex `modified_at` string)
- `interface BufferedDraft { draft: string; baseVersion: BufferBaseVersion; writtenAt: string }` — new (`writtenAt` = ISO string, stamped by write)
- `type WriteResult = { status: "saved" } | { status: "saved-after-eviction"; evictedKeys: string[] } | { status: "failed" }` — new
- `restoreBufferKey(bookId: string, subjectKind: SubjectKind, subjectId: string): string` — new (body throws)
- `readBuffer(key: string): BufferedDraft | null` — new (total return type; never throws once filled; stub body throws)
- `writeBuffer(key: string, draft: string, baseVersion: BufferBaseVersion): WriteResult` — new (stamps `writtenAt`, oldest-first self-eviction on quota; body throws)
- `clearBuffer(key: string): void` — new (body throws)

`frontend/src/work/pages/SubjectPlaceholderPage.tsx` (new)
- `interface SubjectPlaceholderPageProps { heading: string; owner: string }` — new
- `SubjectPlaceholderPage` — new (`observer`-wrapped FC taking `SubjectPlaceholderPageProps`). **Written in full** — read-only empty state (heading + "delivered by {owner}"), structural, no logic a DoD asserts as behavior.

`frontend/src/work/routes.tsx`
- `WorkRoutes` — changed. Added nine children under `/:bookId` ahead of the preserved nested catch-all: `chapters`, `chapter/:id`, `characters`, `locations`, `facts`, `codex/:id`, `variants`, `variants/:chapterId`, `chats` — each `<SubjectPlaceholderPage>` with verbatim owner labels (chapters/chapter → `014.chapter-skeleton`; characters/locations/facts/codex → `013.codex`; variants/variants item → `018.chapter-history-variants`; chats → `011.chat-panel`). **No `chat/:id` route.** Terminal top-level catch-all preserved. Route wiring written in full (structural).
- `ChapterItemRoute()`, `CodexEntryItemRoute()`, `ChapterVariantsItemRoute()` — new module-local wrappers (not exported); read the path param and render `<SubjectPlaceholderPage key={param} …/>` (the `frontend.md` path-param remount rule; shell above does not remount).
- Caller-compile edits (out of Source-files scope): None.

Typecheck: `npx tsc --noEmit` clean (exit 0); `npm run build` clean.

## Tests

### Step 001 — tests (2026-07-25)
- `frontend/tests/work/workGate.test.ts` — covers DoD-1, DoD-2 — resolver allows on token / denies with `/login/` and never navigates (pure); enforcer navigates once on deny, not on allow, returns the boolean outcome.
- `frontend/tests/work/routes.test.tsx` — covers DoD-3 — entry root (`/`) renders the not-found page (back anchor to `/`), the sole link on screen proving the terminal top-level catch-all is terminal. (Deep-path case dropped: superseded by step 002's `/:bookId` + splat in-pane not-found, covered in `tests/work/WorkspaceShell.test.tsx`.)
- `frontend/tests/user/BookshelfPage.test.tsx` — covers DoD-4 — owned and shared rows each expose a plain `<a>` whose href is exactly `/work/<id>` (rendered without a Router to prove it is not a react-router link); first repo mock of an `src/api/*` module.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 [manual/live, no test], DoD-6 [manual/live, no test], DoD-7 [manual/live, no test]

### Step 002 — tests (2026-07-25)
- `frontend/tests/work/navItems.test.ts` — covers DoD-1, DoD-2, DoD-3 — `WORK_NAV_ITEMS` is the seven UC-090 labels in order; `workNavHref` builds each basename-stripped subject href; `isWorkNavItemActive` matches own path / `/`-delimited descendant / Chapters' `/chapter` extra segment / Variants' per-chapter path, and rejects siblings and bare prefixes.
- `frontend/tests/work/WorkNavigator.test.tsx` — covers DoD-1, DoD-2 — renders exactly seven ordered in-SPA router links with the author-facing labels and their `/bk-1/<segment>` hrefs.
- `frontend/tests/work/WorkspaceShell.test.tsx` — covers DoD-4, DoD-5, DoD-6, DoD-7 — three regions (navigator, content-pane outlet inside `main`, chat-slot naming `011.chat-panel`); single load rendering the title with a no-title pending state; a rejected `ApiError(403)` load replaces the content without crash/blank; subject navigation under one `:bookId` fires exactly one load.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 [manual/live, no test]

### Step 003 — tests (2026-07-25)
- `frontend/tests/work/BookStatePage.test.tsx` — covers DoD-1, DoD-2, DoD-3, DoD-4, DoD-5 — `/:bookId` (via `WorkRoutes`) redirects to `state` (pathname probe) and the Book-state view renders; the page renders every `BookDetailResponse` field (title, description, "Free"/"Private"/state labels, both timestamps, owner + co-author); the state-notes labelled empty state shows on a successful load (wire gap, not a failure); the continuity empty state names `016.chapter-close-continuity` and the page says "warning" never "flag"; the trio shows a loading state on pending and an author-facing error (non-blank) on `ApiError`.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 [manual/live, no test]

### Step 004 — tests (2026-07-25)
- `frontend/tests/work/subject.test.ts` — covers DoD-1, DoD-2, DoD-3, DoD-4 (subject/pane half) — `open` chapter editable (whole, no reason) vs `closing`/`planned`/`closed` read-only with a stated reason; non-archived codex editable vs archived read-only, Book state state-notes-only, every list kind read-only; the writer-agnostic write gate denies read-only subjects identically on repeat calls, allows the editable ones, and allows Book state's notes but denies its whole; `resolveSubjectPaneTarget` maps `chats` → "chat" and every other kind → "content".
- `frontend/tests/work/restoreBuffer.test.ts` — covers DoD-7, DoD-8, DoD-9, DoD-10, DoD-11, DoD-12 — write/read round-trip of draft/baseVersion/writtenAt (numeric + string base version); reload survival via `resetModules` + re-import against the same store; per-item keying and clear-only-own-key; device-local write with no `fetch` and a prefixed localStorage key; quota eviction oldest-first (fake-timed stamps, stubbed quota-throwing `setItem`) reported in `saved-after-eviction`, current key kept, foreign key untouched; total read returns null (no throw) on absent/unparseable/wrong-shape entries.
- `frontend/tests/work/subjectRoutes.test.tsx` — covers DoD-4 (route half), DoD-5, DoD-6 — each list route renders its verbatim owner label inside the content pane (`main`, scoped past the chat slot); each item route renders its placeholder (no not-found back-anchor in pane); a `/:bookId/chat/<id>` path falls through to the in-pane not-found page and shows no chat placeholder in the content pane.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓, DoD-10 ✓, DoD-11 ✓, DoD-12 ✓, DoD-13 [manual/live, no test]

## Notes & Issues

_populated by the coder when worth saying_
