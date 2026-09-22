# Context — fast/005.workspace-layout

Feature-wide context for the single plan in `plan.md`. Distilled from the
orchestrator's briefing (harvest and design discussion complete; every open
decision user-confirmed). Read this before `plan.md`.

## What this feature is

Layout ergonomics for the working page (`/work/:bookId`): the left navigator
becomes collapsible to an icon-only rail behind a pin control, the right chat
pane becomes resizable by dragging its left edge, and both preferences persist
device-locally across reloads. **Frontend only** — five source files, all under
`frontend/src/work/` plus one appended block in `frontend/global.css`. No
backend, no API, no DTO, no route, no product id.

## Provenance — why this is a fast feature and not a bug fix

The user raised it through `/bug-fixer`. It is **not** a bug: it is new scope
that three delivered documents explicitly excluded.

- `docs/plans/010.working-page/brief.md` → **Scope Out**: "pane resize/orientation
  mechanics".
- `docs/architecture/frontend-workspace.md:329` → **Out of scope**: "Pane
  orientation, resize/divider behaviour and ratio persistence. Product routes
  these to `/architect` but this pass does not settle them."
- `docs/product/vision.md:155-159` lists the same as a product non-goal, routed
  to `/architect`.

A bug fix "adds no new scope; repairs the existing contract" (`docs/plans/CLAUDE.md`).
There is no contract here to repair — the shell's widths were hardcoded on
purpose. The user confirmed routing to `/fast-feature`.

There is **no `brief.md`** and no roadmap row: this feature was not roadmapped,
and `005` was minted by `/fast-feature`, not by `/roadmap`. This plan must not
edit `docs/plans/roadmap.md`.

**Nothing that step `010.working-page/002.workspace-shell` delivered may break.**
Its DoD-4/5/6/7 — three regions render, the book loads exactly once, a failed
load surfaces an author-facing message, and subject navigation does not remount
the shell — must keep holding, and its spec `frontend/tests/work/WorkspaceShell.test.tsx`
must keep passing **unmodified**.

## What already exists (verified by the harvester — do not re-harvest)

### `frontend/src/work/components/shell/WorkspaceShell.tsx` (110 lines)

The **only** layout file in the repo. A Mantine `AppShell` with both widths
hardcoded:

- `navbar={{ width: 220, breakpoint: "sm", collapsed: { mobile: !state.navbarOpened } }}`
- `aside={{ width: 320, breakpoint: "md", collapsed: { desktop: false, mobile: true } }}`

The header holds a `Burger` (`hiddenFrom="sm"`) bound to `state.navbarOpened`;
the navbar holds `<WorkNavigator bookId onShowChatList/>`; the aside holds
`<ChatPaneSlot bookId state/>`; main holds `<Outlet/>` or an error `Alert`.

**One** mount-only `useEffect` (deps `[state, chatPaneState]`) starts
`loadWorkspaceBook` + `loadChatPane`, registers the close-turn controller, and
on cleanup unregisters, aborts, and calls `stopChatTurn`. This feature adds a
single `autorun` **inside that existing effect** and adds no second effect.

### `frontend/src/work/components/shell/workspaceShellState.ts`

`class WorkspaceShellState` under `makeAutoObservable`, holding the book async
trio (`bookDetail` / `bookDetailStatus` / `bookDetailError`) plus `navbarOpened`,
with the external `loadWorkspaceBook(state, bookId, signal)` beside it.

### `frontend/src/work/components/shell/WorkNavigator.tsx`

`WorkNavigatorProps` is `{ bookId: string; onShowChatList: () => void }`. It
renders a `<Stack gap={4}>` of Mantine `NavLink`s built from `WORK_NAV_ITEMS` in
`navItems.ts` (`path`, `label`, `icon`, `extraActiveSegments?`, `paneTarget`).
Six entries are router links; the `paneTarget === "chat"` entry renders as
`component="button"`.

### `frontend/src/work/activeChat.ts` — the template to copy

The persistence-tier shape this feature's new module follows: module-level plain
functions, an exported key-prefix const, a `read*` that **never throws**
(try/catch around both the `localStorage` access and `JSON.parse`, a shape check,
a fallback), and a `write*` that swallows storage errors. No class, no MobX, no
`src/api/` import.

### `frontend/global.css`

The single sanctioned stylesheet — it already carries an `.md-body` block. CSS
modules, Tailwind and styled-components stay banned (`frontend.md` → Theming).

## Architecture rules that constrain every decision below

From `docs/architecture/frontend.md`:

- **`observer` on every component**, no exceptions.
- **State is data + `get` computeds, never effectful methods.** All effectful
  work is an external `(state, args, signal)` function — this feature's toggle,
  drag-begin, drag-end and nudge functions live in the same tier as
  `loadWorkspaceBook`.
- **No custom `useX` hooks**, no `useCallback` / `useMemo` / `useReducer`.
  `useEffect` **only at page level** — and `frontend-workspace.md` records that
  the shell keyed on `:bookId` **is** the page-level mount for this rule.
- **"For rare imperative side-effects on observable change, use a single
  `autorun` started in the mount `useEffect` and disposed on cleanup."** That
  sentence is the sanction for how the drag drives the CSS variable.
- `@mantine/hooks` is a listed dependency, but **`useMediaQuery` is not used
  anywhere in the repo** and this feature does not introduce it — breakpoint
  behaviour stays pure CSS.

From `docs/architecture/frontend-work-drafts.md` → "The module tier — five
members": `restoreBuffer.ts`, `activeChat.ts`, `contentSubject.ts`,
`chapterUndo.ts`, `closeTurn.ts`. The doc states outright that they are recorded
together "so a sixth is added on purpose rather than by precedent".
**`workspaceLayout.ts` is that sixth**, and its sanction is a *different*
exception from the drafts one: the drafts tier holds not-yet-saved data, while a
pane width is **device-ergonomics view preference** — arguably URL-able under
`frontend.md`'s "query params are the persistence layer" rule, but deliberately
device-local because it describes *this screen*, not *this book*, and must not
travel in a shared link. `outcome.md` carries the doc row.

## Locked decisions (user-confirmed — do not re-litigate)

| Decision | Choice |
|---|---|
| Collapsed navigator shape | A **narrow icon-only rail** (~54px) with labels hidden and a `Tooltip` on hover. Expanded stays 220px. Explicitly **not** a hover-expand overlay. |
| Toggle affordance | A pin ("fix") icon in the header — `IconPinned` when expanded, `IconPinnedOff` when collapsed. The content pane reclaims the width. |
| Chat pane resize | A drag handle on the pane's **left** edge. |
| Width unit | A **fraction of viewport width**, default `0.35`, clamped to `[0.15, 0.60]`. |
| Persistence | **One global `localStorage` key**, not per-book, holding `{ navCollapsed, chatWidth }`, in the module tier beside `activeChat.ts`. |

## The four implementation constraints that are not obvious

These are the reason this plan is long for its size. Each is a trap that
compiles, typechecks and passes tests while being wrong.

1. **Mantine's `rem()` mangles a bare `var()`.**
   `@mantine/core/esm/core/utils/units-converters/rem.mjs` returns a string
   verbatim **only** when it starts with `calc(`, `clamp(` or `rgba(`; any other
   string containing a comma is split on commas and reassembled wrongly. So the
   aside width must be `calc(var(--work-chat-width, 35vw))`. The obvious
   `var(--work-chat-width, 35vw)` compiles, typechecks and silently emits garbage
   CSS **with no test failure**. The assignment site carries a comment and
   `status.md` carries a note.

2. **The aside width prop string is constant; the drag drives a CSS variable.**
   `WorkspaceShell` must **never** read `state.chatWidthFraction` in its own JSX
   — only `ChatResizeHandle` may. If the shell observes the fraction, every
   `pointermove` re-renders the whole content pane and the design collapses.
   `asideWidthCss` is therefore frozen at construction from the **stored** value
   and excluded from `makeAutoObservable`; freezing it from the stored value (not
   the default) is also what kills the flash of a 35% pane before first paint.

3. **No `window` `"resize"` listener anywhere.** The width is a `vw` length, so
   the browser reflows on viewport change for free. `window.innerWidth` is read
   only inside the live `pointermove` handler.

4. **Breakpoints need no JavaScript.** Mantine forces
   `--app-shell-navbar-width: 100%` below `navbar.breakpoint` (in both the open
   and the collapsed branch) and `--app-shell-aside-width: 100%` below
   `aside.breakpoint`. `navbarOpened` (the mobile drawer) and `navCollapsed`
   (the desktop rail width) are **orthogonal and never active at the same
   viewport**. No responsive `{ base, sm }` width object is needed.

## Why the label hiding is CSS and not JavaScript

Three rules appended to `global.css` inside `@media (min-width: 48em)`
(Mantine's default `sm`; `theme.ts` sets no custom `breakpoints`), applied via
`NavLink`'s `classNames`. Two independent reasons, both real:

- Mantine's `NavLink` **always renders the body span**. Dropping the `label`
  prop leaves an empty flex spacer that left-shifts the icon instead of centring
  it.
- A JS boolean **cannot be breakpoint-aware** without `useMediaQuery`, which is
  banned repo-wide. A JS-hidden label would therefore also blank the full-width
  **mobile drawer**, where the labels must stay.

Every `NavLink` also gains `aria-label={item.label}` **unconditionally**, in
both branches. Mantine spreads `...others` onto the root anchor, so this
preserves `getByRole("link", { name })` in collapsed mode and leaves
`textContent` untouched in expanded mode — which is what keeps the existing
`WorkNavigator.test.tsx` passing unmodified.

## Why the drag is not tested and the keyboard path is

jsdom has no layout engine (`getBoundingClientRect` returns zeros), no
`PointerEvent` and no `setPointerCapture`. A jsdom "drag" would synthesise
coordinates and then call our own `chatWidthFromPointer` with them — it would
test the test. This is the **same reasoning `frontend.md` already records twice**:
for `@dnd-kit`'s pointer sensor (feature `014`) and for ProseMirror (feature
`015`), both of which left the gesture `[manual/live]`.

So the design splits the drag into three separately-verifiable parts:

- the **geometry** is the pure `chatWidthFromPointer`, unit-tested with no DOM;
- the **persistence** and the **CSS-variable wiring** are exercised through the
  **keyboard path** (`ArrowLeft` / `ArrowRight` on the handle), which jsdom
  drives natively;
- only the **gesture itself** is `[manual/live]`.

`beginChatResize` attaches its listeners to **`window`**, not via
`setPointerCapture` — jsdom implements neither `setPointerCapture` nor
`PointerEvent`, and window listeners keep tracking when the pointer outruns a
6px handle, so the choice is right for both the browser and the test harness.

## Gotchas the coder and the test-coder will hit

- **`tests/setup.ts` clears `localStorage` in `afterEach`**, and
  `WorkspaceShellState` hydrates **in its constructor**. A rehydration test must
  therefore seed storage **before** `renderWithProviders`, not after.
- **React `StrictMode` double-invokes the mount effect.** The `autorun`
  re-creation is idempotent and `endChatResize` is idempotent, so the existing
  effect stays safe — but **no non-idempotent listener attach may be added to
  it**.
- **`restoreBuffer.ts`'s eviction sweep only touches keys prefixed
  `RESTORE_BUFFER_KEY_PREFIX`**, so the layout key can never be evicted.
  Conversely, a quota-exhausting chapter write makes `writeWorkspaceLayout`
  throw-and-swallow, silently reverting to defaults on the next load — the same
  contract `activeChat.ts` already accepts. This is a **second, independent**
  reason to write storage on `pointerup` rather than on every `pointermove`.
- **`ChatResizeHandle`'s absolute positioning relies on `AppShell.Aside` being
  `position: fixed`**, verified in `@mantine/core/styles.css`.
- **`vitest.config.ts` leaves `css: false`**, so `global.css` resolves to an
  empty module under test and no media query ever evaluates. The rail's visual
  label hiding is therefore unobservable in jsdom by construction — only the
  `classNames` wiring is testable.
- **`tests/setup.ts` stubs `matchMedia` to never match**, and `visibleFrom` /
  `hiddenFrom` are pure CSS. Breakpoint behaviour is unobservable under test.
- The shell spec must reuse the existing `api/books` + `api/chats` + `api/flags`
  + `api/continuity` module-mock block from
  `frontend/tests/work/WorkspaceShell.test.tsx`; without it a shell mount fires
  real fetches.
- `IconPinned` and `IconPinnedOff` are both present in `@tabler/icons-react`
  3.45.0 (verified).

## Scope-check note for the verifier — this is not a promotion signal

Five source files, ~260–300 LoC, three test files. One logical change: the
working page's layout chrome. There is **no cross-layer coordination** (frontend
only, no API, no DTO, no route), **no ordering dependency** between the parts
(the pure module, the rail and the handle are independently authorable and only
meet in `WorkspaceShell.tsx`'s prop wiring), and **no design ambiguity** — every
decision is locked in the table above. Three test files rather than the nominal
one or two is a consequence of the three natural seams (pure module · navigator ·
shell), not of three features hiding in one.

## Non-negotiables the coder must not "improve"

1. **`calc(var(--work-chat-width, 35vw))`** — never the bare `var(...)` form.
2. **`WorkspaceShell.tsx` never reads `state.chatWidthFraction`.**
3. **No `window` `"resize"` listener**, anywhere.
4. **No second `useEffect`** in `WorkspaceShell.tsx`, and no `useMediaQuery`.
5. **`collapsed` on `WorkNavigatorProps` stays optional** with a `false` default
   — making it required breaks existing call sites and `npm run test:types`.
6. **Do not touch `ChatPaneSlot`'s props or anything under
   `src/work/components/chat/`** — that pane's contents are
   `011.chat-panel/004`'s. The handle is shell chrome, not pane content.
7. **Do not edit `docs/architecture/`** — intended doc changes go in
   `outcome.md` for the architect to apply.
