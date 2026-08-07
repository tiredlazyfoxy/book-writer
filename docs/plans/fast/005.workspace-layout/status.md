# Fast feature 005 — workspace-layout

| Status | Verifier | Date |
|--------|----------|------|
| done   | PASS     | 2026-08-07 |

## Files Changed

- `frontend/src/work/workspaceLayout.ts` — **new**; the module tier's sixth member: the one
  global layout key, the four bounds, the pure geometry/format helpers and the total read /
  best-effort write.
- `frontend/src/work/components/shell/workspaceShellState.ts` — constructor hydrates from storage
  and bakes the stored width into `asideWidthCss`; `navbarWidth` / `chatWidthCssValue` computeds;
  the four external effect functions (toggle · begin · end · nudge).
- `frontend/src/work/components/shell/ChatResizeHandle.tsx` — **new**; the aside's left-edge
  divider: `role="separator"` with integer-percent bounds, pointer-down to `beginChatResize`, and
  the `ArrowLeft`-widens / `ArrowRight`-narrows keyboard path.
- `frontend/src/work/components/shell/WorkNavigator.tsx` — unconditional `aria-label` on every
  entry, plus the `Tooltip` wrapper and `work-nav-rail-*` `classNames` when `collapsed`.
- `frontend/src/work/components/shell/WorkspaceShell.tsx` — the widths, the drag-time
  `transitionDuration`, the header pin `ActionIcon`, `collapsed` on the navigator,
  `ChatResizeHandle` before `ChatPaneSlot`, and the CSS-variable `autorun` inside the existing
  mount effect.
- `frontend/global.css` — appended three rail rules inside `@media (min-width: 48em)`.

## Skeleton

### Frozen interface (2026-08-07)

Every signature below is the contract the test-coder binds to and the coder may not change.
Every literal from `## Interface intent` was committed verbatim. Bodies throw
`Error("<name>: unimplemented (fast/005 skeleton)")` unless marked **implemented**; parameters are
touched with `void x;` only to satisfy `noUnusedParameters` — the coder deletes those lines.

#### `frontend/src/work/workspaceLayout.ts` — NEW (all symbols new)

Constants — **implemented** (structural, the `ACTIVE_CHAT_KEY_PREFIX` precedent); each keeps its
inferred literal type:

- `export const WORKSPACE_LAYOUT_KEY = "bookwriter.workspace-layout"`
- `export const CHAT_WIDTH_CSS_VAR = "--work-chat-width"`
- `export const DEFAULT_CHAT_WIDTH_FRACTION = 0.35`
- `export const MIN_CHAT_WIDTH_FRACTION = 0.15`
- `export const MAX_CHAT_WIDTH_FRACTION = 0.6`
- `export const CHAT_WIDTH_KEYBOARD_STEP = 0.02`

Shape — **implemented** (declaration only):

- `export interface WorkspaceLayout { navCollapsed: boolean; chatWidth: number }` — exactly these two
  fields, in this order; no third field.

Functions — bodies throw:

- `export function clampChatWidth(fraction: number): number`
- `export function chatWidthFromPointer(clientX: number, viewportWidth: number): number` — viewport is
  an **argument**, never read from `window`, so it is bindable with no DOM.
- `export function chatWidthCss(fraction: number): string`
- `export function readWorkspaceLayout(): WorkspaceLayout` — no parameters; return type is total.
- `export function writeWorkspaceLayout(layout: WorkspaceLayout): void`

#### `frontend/src/work/components/shell/workspaceShellState.ts` — modified (additive only)

New module constants — **implemented**:

- `export const NAV_EXPANDED_WIDTH = 220` — new
- `export const NAV_RAIL_WIDTH = 54` — new

`class WorkspaceShellState` — the four existing fields (`bookDetail`, `bookDetailStatus`,
`bookDetailError`, `navbarOpened`) and `loadWorkspaceBook` are **untouched and still implemented**.
Added:

- `navCollapsed: boolean = false` — new, observable
- `chatWidthFraction: number = DEFAULT_CHAT_WIDTH_FRACTION` — new, observable
- `resizing: boolean = false` — new, observable
- `readonly asideWidthCss: string` — new, assigned in the constructor, **non-observable**
- `resizeDispose: (() => void) | null = null` — new, **non-observable**
- `constructor()` — changed (was `makeAutoObservable(this)`): now assigns `asideWidthCss` and calls
  `makeAutoObservable(this, { asideWidthCss: false, resizeDispose: false })`. That exclusion map is
  part of the frozen surface. Skeleton assigns the **default-width** form
  `` `calc(var(${CHAT_WIDTH_CSS_VAR}, 35vw))` `` so the class stays constructible; **hydrating
  `navCollapsed` / `chatWidthFraction` from `readWorkspaceLayout()` and baking the STORED width into
  that string is the coder's** (DoD-13). The `calc(...)` wrapper is mandatory — a bare
  `var(--work-chat-width, 35vw)` typechecks and emits garbage CSS through Mantine's `rem()` with no
  test failure. The assignment site carries that comment; never unwrap it.
- `get navbarWidth(): number` — new, throws
- `get chatWidthCssValue(): string` — new, throws

New external effect functions (`loadWorkspaceBook`'s tier — top level, never methods), bodies throw:

- `export function toggleNavCollapsed(state: WorkspaceShellState): void`
- `export function beginChatResize(state: WorkspaceShellState): void`
- `export function endChatResize(state: WorkspaceShellState): void`
- `export function nudgeChatWidth(state: WorkspaceShellState, delta: number): void`

#### `frontend/src/work/components/shell/ChatResizeHandle.tsx` — NEW

- `export interface ChatResizeHandleProps { state: WorkspaceShellState }` — new; the shell state is
  the only prop.
- `export const ChatResizeHandle = observer(function ChatResizeHandle({ state }: ChatResizeHandleProps): ReactElement)`
  — new; body throws. The explicit `: ReactElement` return annotation exists only so a
  throw-only body satisfies `observer`'s component type; it is not a constraint on the coder's JSX.
  The accessible contract the tests bind to (`role="separator"`, name `"Resize chat pane"`,
  `aria-valuemin` 15 / `aria-valuemax` 60 / `aria-valuenow` as an integer percent, `tabIndex={0}`,
  `ArrowLeft` widens / `ArrowRight` narrows) is **behaviour, not yet present** — it is spelled out in
  the file's doc comment for the coder and comes from the plan, not from this record.

#### `frontend/src/work/components/shell/WorkNavigator.tsx` — modified

- `export interface WorkNavigatorProps` — changed: gains `collapsed?: boolean` (**optional**, third
  member; `bookId: string` and `onShowChatList: () => void` unchanged).
- `export const WorkNavigator = observer(function WorkNavigator({ bookId, onShowChatList, collapsed = false }: WorkNavigatorProps))`
  — changed (was `({ bookId, onShowChatList })`). The `false` default is load-bearing. The rendering
  body is **unchanged 010/002 + 011/004 behaviour** — the unconditional `aria-label`, the `Tooltip`
  wrapper and the `work-nav-rail-root` / `work-nav-rail-section` / `work-nav-rail-body` `classNames`
  are all still unimplemented (DoD-9/10/11 red).

#### Files in Source scope with **no frozen interface**

- `frontend/src/work/components/shell/WorkspaceShell.tsx` — **untouched.** It has no props and no
  signature changes; every change the plan asks for (`transitionDuration`, `navbar.width`,
  `aside.width`, the pin control, rendering `ChatResizeHandle` before `ChatPaneSlot`, the `autorun`
  inside the existing mount `useEffect`) is body wiring and therefore the coder's. Leaving it untouched
  is deliberate: it keeps `tests/work/WorkspaceShell.test.tsx` passing unmodified (DoD-22) and keeps
  DoD-14/15/17 honestly red.
- `frontend/global.css` — **untouched.** CSS carries no signatures and is not typechecked; the three
  rail rules inside `@media (min-width: 48em)` are appended by the coder.

#### Verification

- `cd frontend && npx tsc --noEmit` — clean.
- `cd frontend && npm run test:types` — clean (confirms the optional `collapsed` broke no call site).
- `cd frontend && npx vitest run tests/work/WorkspaceShell.test.tsx tests/work/WorkNavigator.test.tsx`
  — 7 passed, both unmodified (DoD-22's regression half already holds).

#### Caller-compile edits (out of Source-files scope)

None. No file outside the plan's Source files was read-modified; `ChatPaneSlot.tsx` and `navItems.ts`
were read only.

## Tests

### Tests (2026-08-07)

- `frontend/tests/work/workspaceLayout.test.ts` — covers DoD-1, DoD-2, DoD-3, DoD-4, DoD-5, DoD-6,
  DoD-7 — the pure module: default/constant literals, one-key round-trip, the total read on seven
  garbage shapes, per-field fallback, clamping on read and in `clampChatWidth`, the right-anchored
  pointer geometry, and the two-decimal `vw` string.
- `frontend/tests/work/WorkNavigatorRail.test.tsx` — covers DoD-8, DoD-9, DoD-10, DoD-11 — expanded
  mode still shows six labelled router links; collapsed keeps six links reachable by accessible name
  with identical hrefs, keeps the Chats entry a control that calls `onShowChatList`, and wires the
  three rail class names only when collapsed.
- `frontend/tests/work/workspaceShellLayout.test.tsx` — covers DoD-12, DoD-13, DoD-14, DoD-15,
  DoD-16, DoD-17 — the pin control's name/`aria-pressed`/persistence, first-render rehydration from
  storage seeded **before** the render, the separator's percent bounds, the `ArrowLeft`-widens
  keyboard path (valuenow 37 · stored 0.37 · `--work-chat-width: 37vw`), its clamp at 60, and the
  custom property's removal on unmount. Reuses `WorkspaceShell.test.tsx`'s `api/books` + `api/chats`
  + `api/flags` + `api/continuity` module-mock block verbatim; that file is not edited.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓,
  DoD-10 ✓, DoD-11 ✓, DoD-12 ✓, DoD-13 ✓, DoD-14 ✓, DoD-15 ✓, DoD-16 ✓, DoD-17 ✓,
  DoD-18 [manual/live, no test], DoD-19 [manual/live, no test], DoD-20 [manual/live, no test],
  DoD-21 [manual/live, no test], DoD-22 [manual/live, no test].
- No pointer drag is simulated (DoD-18 stays live-only): the geometry is unit-tested via
  `chatWidthFromPointer`, persistence and the autorun via the keyboard path.

## Notes & Issues

- **The `calc(...)` wrapper on the aside width is load-bearing, never stylistic.** Re-verified
  against `@mantine/core/esm/core/utils/units-converters/rem.mjs` in this repo's installed 7.x:
  a string is returned verbatim only when it starts with `calc(` / `clamp(` or contains `rgba(`;
  every other comma-bearing string is split on its commas and reassembled per-part. The aside width
  therefore stays `calc(var(--work-chat-width, <stored>vw))`. The bare `var(...)` form compiles,
  typechecks and emits garbage CSS **with no test failure** — the assignment site in
  `workspaceShellState.ts` and the `aside` prop in `WorkspaceShell.tsx` both carry the warning.
  Traced the value's path to confirm it survives: `assignAsideVariables` → `isPrimitiveSize` (a
  string qualifies) → `getBaseSize` → `rem`, landing on `--app-shell-aside-width` unmodified.
- **`endChatResize` guards on `resizeDispose`, not on `resizing`.** With no drag in flight it
  returns immediately, so the shell's unconditional unmount call detaches nothing, restores
  nothing and — deliberately — **writes nothing**. Persisting on every unmount would be a storage
  write per page leave for no gained information; `toggleNavCollapsed` and `nudgeChatWidth` already
  persist at the moment the user changes something.
- **No rounding was added to `nudgeChatWidth`.** `0.35 + 0.02 === 0.37` is exact in IEEE-754
  doubles (verified), so a keyboard nudge from the default stores a clean `0.37`. `chatWidthCss`
  still does the two-decimal rounding for the emitted `vw` string, which is where float noise
  would otherwise surface after a longer nudge chain.
- `document.documentElement.style.setProperty` / `removeProperty` for a `--custom-property` is
  supported by the installed jsdom (verified directly), so the `autorun`'s effect is observable
  without a real browser.
- Not fixed, out of scope: the `work` bundle is 668 kB and trips Vite's 500 kB chunk warning. This
  is pre-existing and unrelated to this feature.
