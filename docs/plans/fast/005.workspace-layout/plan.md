# fast/005.workspace-layout — Collapsible navigator rail & resizable chat pane

## Goal

Make the working page's two side regions adjustable and remembered: the left
navigator collapses to an icon-only rail behind a pin control, and the right
chat pane is resized by dragging its left edge, with both preferences persisted
device-locally under one global `localStorage` key.

## Source files

This list **is** the coder's scope; nothing else is touched.

- `frontend/src/work/workspaceLayout.ts` — **NEW.** The module tier's sixth
  member: the layout preference's key, constants, pure geometry helpers, and its
  total read / best-effort write.
- `frontend/src/work/components/shell/workspaceShellState.ts` — **modify.** The
  shell state gains the collapse flag, the width fraction, the resize lifecycle
  and the derived widths, plus four external effect functions.
- `frontend/src/work/components/shell/ChatResizeHandle.tsx` — **NEW.** The
  chat pane's drag/keyboard divider, as shell chrome.
- `frontend/src/work/components/shell/WorkNavigator.tsx` — **modify.** An
  optional collapsed mode: tooltips, rail class names, unconditional
  `aria-label`.
- `frontend/src/work/components/shell/WorkspaceShell.tsx` — **modify.** Wire the
  widths, the pin control, the handle and the CSS-variable `autorun`.
- `frontend/global.css` — **modify, append only.** Three rail rules inside a
  `min-width: 48em` media query.

## Test files

Disjoint from Source files. This list **is** the test-coder's scope.

- `frontend/tests/work/workspaceLayout.test.ts`
- `frontend/tests/work/WorkNavigatorRail.test.tsx`
- `frontend/tests/work/workspaceShellLayout.test.tsx`

**Not in scope for either role:** `frontend/tests/work/WorkspaceShell.test.tsx`
and `frontend/tests/work/WorkNavigator.test.tsx` must keep passing
**unmodified** — see DoD-22. `workspaceShellLayout.test.tsx` reuses the
`api/books` + `api/chats` + `api/flags` + `api/continuity` module-mock block from
the former, but does not edit it.

## Interface intent

Prose only, per `docs/plans/CLAUDE.md`. `fast-skeleton` derives and freezes the
exact signatures. Where a literal value is given below it **is** the contract —
the skeleton must not round it, rename it, or move it.

### `frontend/src/work/workspaceLayout.ts` — NEW

Module-level plain functions in the `activeChat.ts` / `restoreBuffer.ts` tier:
**no class, no MobX, no reactivity, no import from `src/api/`, and no DOM
access** (the pure helpers take their inputs as arguments so they are testable
without a window).

Exported constants:

- `WORKSPACE_LAYOUT_KEY` — the single global storage key, the string
  `"bookwriter.workspace-layout"`. One key for the whole workspace, deliberately
  **not** per book: a pane width describes this screen, not this book.
- `CHAT_WIDTH_CSS_VAR` — the string `"--work-chat-width"`, the CSS custom
  property the pane width is driven through.
- `DEFAULT_CHAT_WIDTH_FRACTION` = `0.35`, `MIN_CHAT_WIDTH_FRACTION` = `0.15`,
  `MAX_CHAT_WIDTH_FRACTION` = `0.6`, `CHAT_WIDTH_KEYBOARD_STEP` = `0.02`.

Exported shape:

- `WorkspaceLayout` — the persisted record: a boolean `navCollapsed` and a
  number `chatWidth`. `chatWidth` is a **fraction of viewport width**, always
  within the min/max bounds. Document in-file that it is device-local view
  preference, deliberately not in the URL and not on the server.

Exported functions:

- `clampChatWidth` — takes a number fraction, returns a number fraction bounded
  by the min and max constants. Pure. A non-finite input (`NaN`, `Infinity`,
  `-Infinity`) yields the default rather than a bound.
- `chatWidthFromPointer` — takes the pointer's client X coordinate and the
  viewport width, both numbers, and returns the clamped number fraction. The
  pane is **right-anchored**, so the fraction is the distance from the pointer to
  the right edge over the viewport width. A non-positive viewport width yields
  the default. This is the drag's **entire geometry**, extracted precisely so it
  can be verified with no DOM.
- `chatWidthCss` — takes a number fraction and returns the CSS length string the
  custom property is set to: `0.35` becomes `"35vw"`. It **rounds to two decimal
  places** so a keyboard-nudged value can never emit float noise such as
  `"35.000000000000004vw"`.
- `readWorkspaceLayout` — takes nothing, returns a `WorkspaceLayout`. It
  **never throws** and is **total**: a missing entry, an unreadable storage, a
  non-JSON string, a JSON `null`, an array, a bare string or number, and a
  wrong-typed field all resolve to defaults. It clamps `chatWidth` on read, and
  its fallback is **per field** — a valid `navCollapsed` sitting beside a garbage
  `chatWidth` keeps the boolean and defaults the number.
- `writeWorkspaceLayout` — takes a `WorkspaceLayout`, returns nothing. Stores it
  under the one key as JSON and **swallows storage errors** (quota, private
  mode), exactly as `activeChat.ts`'s writer does.

### `frontend/src/work/components/shell/workspaceShellState.ts` — modify

Two new exported numeric constants: `NAV_EXPANDED_WIDTH` = `220` (today's
hardcoded value, now named) and `NAV_RAIL_WIDTH` = `54`.

`WorkspaceShellState` keeps its existing four fields — `bookDetail`,
`bookDetailStatus`, `bookDetailError`, `navbarOpened` — **untouched**, and gains:

- `navCollapsed` — an observable boolean, the desktop rail flag. Orthogonal to
  `navbarOpened`, which stays the mobile drawer flag.
- `chatWidthFraction` — an observable number, the live width fraction.
- `resizing` — an observable boolean, true only while a pointer drag is in
  flight.
- `asideWidthCss` — a **readonly, non-observable** string, computed once in the
  constructor.
- `resizeDispose` — a non-observable slot holding either the current drag's
  detach closure or nothing.

The **constructor** hydrates `navCollapsed` and `chatWidthFraction` from
`readWorkspaceLayout()`, then bakes the **stored** width into `asideWidthCss` as
`calc(var(--work-chat-width, <stored>vw))` — frozen at construction, so the
markup renders at the remembered width on the very first paint and there is no
flash of the default. It then calls `makeAutoObservable` with `asideWidthCss`
and `resizeDispose` explicitly excluded from observability.

> **The `calc(...)` wrapper is mandatory, not stylistic.** Mantine's `rem()`
> passes a string through verbatim only when it starts with `calc(`, `clamp(` or
> `rgba(`; any other comma-bearing string is split on commas and mangled. A bare
> `var(--work-chat-width, 35vw)` compiles, typechecks and emits garbage CSS with
> **no test failure**. The coder puts a comment at this assignment site and a
> note in `status.md`.

Two `get` computeds — derivations, never setters:

- `navbarWidth` — a number: the rail width when collapsed, the expanded width
  otherwise.
- `chatWidthCssValue` — a string: `chatWidthCss` applied to the live fraction.
  Only the `autorun` and the handle observe this.

Four external effect functions, in the same tier as the existing
`loadWorkspaceBook` (top-level, `(state, …)`-shaped, no methods on the class):

- `toggleNavCollapsed` — takes the state, flips `navCollapsed`, and persists.
- `beginChatResize` — takes the state. Sets `resizing`, suppresses text
  selection and pins the `col-resize` cursor on `document.body`, and attaches
  `pointermove`, `pointerup` and `pointercancel` listeners to **`window`** —
  deliberately **not** `setPointerCapture`, because jsdom implements neither that
  nor `PointerEvent`, and window listeners keep tracking when the pointer
  outruns the 6px handle. It stores the detach closure on `resizeDispose`. It is
  **idempotent**: called again while a drag is already live it is a no-op.
- The `pointermove` handler does **only** one thing: assign
  `chatWidthFromPointer` of the event's client X and `window.innerWidth` to
  `state.chatWidthFraction`. **No storage write**, no other state change.
- `endChatResize` — takes the state. Detaches the listeners, restores the body
  styles, clears `resizing`, and writes storage **once**. **Idempotent and safe
  when no drag is in flight**, because the shell's unmount cleanup calls it
  unconditionally.
- `nudgeChatWidth` — takes the state and a number delta, applies the clamped
  delta to `chatWidthFraction`, and persists.

`toggleNavCollapsed`, `endChatResize` and `nudgeChatWidth` each persist the
**whole** record — both `navCollapsed` and `chatWidth` read off current state —
so no writer can clobber the other field.

### `frontend/src/work/components/shell/ChatResizeHandle.tsx` — NEW

An `observer` component whose props are just the shell state instance. It owns
**no state, no effect and no hook** — it is a leaf that reads computeds and calls
external functions, per `frontend.md`'s component rules.

It renders exactly one Mantine `Box`:

- Accessibility: `role="separator"`, `aria-orientation="vertical"`,
  `aria-label="Resize chat pane"`, and `aria-valuemin` / `aria-valuemax` /
  `aria-valuenow` as **integer percents** — 15, 60, and the current fraction
  rounded to a whole percent. `tabIndex={0}` so it is focusable.
- `visibleFrom="md"`, matching the aside's own breakpoint — there is no pane to
  resize below it.
- `onPointerDown` calls `preventDefault()` and then `beginChatResize`.
- `onKeyDown`: `ArrowLeft` **widens** the pane by `+CHAT_WIDTH_KEYBOARD_STEP` and
  `ArrowRight` **narrows** it by the same step, both through `nudgeChatWidth`,
  both calling `preventDefault()`. (Left widens because the pane grows leftward
  from the right edge.) Any other key is ignored.
- Inline style: absolutely positioned, `insetBlock: 0`, `insetInlineStart: 0`,
  `width: 6`, `cursor: "col-resize"`, `touchAction: "none"`, `zIndex: 1`. This
  relies on `AppShell.Aside` being `position: fixed`, which it is.

**The keyboard path is what makes resize verifiable in jsdom at all** — see
`context.md` → "Why the drag is not tested and the keyboard path is".

### `frontend/src/work/components/shell/WorkNavigator.tsx` — modify

- The props gain `collapsed` as an **optional boolean defaulting to `false`**.
  Optional is load-bearing: making it required breaks the existing call sites and
  `npm run test:types`.
- **Every** `NavLink` — both the six router-link entries and the `paneTarget:
  "chat"` button entry — gains `aria-label` set to the item's label,
  **unconditionally, in both modes**. Mantine spreads unknown props onto the root
  anchor, so this preserves `getByRole("link", { name })` when the visible label
  is hidden and leaves `textContent` untouched when it is not.
- When `collapsed`, each entry is additionally wrapped in a Mantine `Tooltip`
  carrying the item's label, positioned to the right, with an arrow and a short
  open delay (200ms), and the `NavLink` is given `classNames` mapping its root,
  section and body slots to `work-nav-rail-root`, `work-nav-rail-section` and
  `work-nav-rail-body`.
- Nothing else changes: the item list, the ordering, the active-match predicate,
  the hrefs and the chat entry's `component="button"` behaviour are all
  untouched.

### `frontend/global.css` — modify, append only

Append three rules **inside** an `@media (min-width: 48em)` block — Mantine's
default `sm` breakpoint; `theme.ts` sets no custom `breakpoints`:

- `.work-nav-rail-body` → `display: none`
- `.work-nav-rail-section` → `margin-inline-end: 0`
- `.work-nav-rail-root` → `justify-content: center` and `padding-inline: 0`

**Label hiding is CSS, not JavaScript**, for two independent reasons: Mantine's
`NavLink` always renders the body span, so dropping the `label` prop leaves an
empty flex spacer that left-shifts the icon; and a JS boolean cannot be
breakpoint-aware without `useMediaQuery` (banned repo-wide), so a JS-hidden
label would also blank the full-width mobile drawer, where labels must stay.

### `frontend/src/work/components/shell/WorkspaceShell.tsx` — modify

- `AppShell` gains a transition duration of `0` while `state.resizing` and the
  Mantine default `200` otherwise, so `AppShell.Main`'s `transition-property:
  padding` does not rubber-band 200ms behind the pointer.
- `navbar.width` becomes `state.navbarWidth`. `navbar.breakpoint` and
  `navbar.collapsed` are unchanged.
- `aside.width` becomes `state.asideWidthCss`. `aside.breakpoint` and
  `aside.collapsed` are unchanged.
- The header `Group` gains, **between the `Burger` and the title**, a `Tooltip`
  wrapping a subtle `ActionIcon` with `visibleFrom="sm"`. Its `aria-label` and
  the tooltip's label are the same string — "Pin navigator open" when collapsed,
  "Collapse navigator" when expanded — and it carries `aria-pressed` set to the
  negation of `navCollapsed`. Clicking it calls `toggleNavCollapsed`. Its icon is
  `IconPinned` when expanded and `IconPinnedOff` when collapsed.
- The navbar renders `WorkNavigator` with the existing `bookId` and
  `onShowChatList` props plus `collapsed` bound to `state.navCollapsed`.
- The aside renders `ChatResizeHandle` **before** `ChatPaneSlot`.
  **`ChatPaneSlot`'s props are untouched** — the handle is shell chrome, not pane
  content, and `011.chat-panel` owns the pane's contents.
- The **existing** mount `useEffect` — no new effect, deps unchanged — gains a
  single `autorun` that sets the CSS custom property named by
  `CHAT_WIDTH_CSS_VAR` on `document.documentElement` to `state.chatWidthCssValue`.
  Its cleanup disposes the autorun, removes the property, and calls
  `endChatResize` **before** the existing cleanup lines (unregister, abort,
  `stopChatTurn`). This is exactly `frontend.md`'s sanctioned "a single `autorun`
  started in the mount `useEffect` and disposed on cleanup" pattern.

> **`WorkspaceShell` must never read `state.chatWidthFraction` in its own JSX.**
> Only `ChatResizeHandle` may observe the live fraction. If the shell observes
> it, every `pointermove` re-renders the whole content pane and the whole design
> collapses. The aside's width prop string is **constant**; the drag drives the
> CSS variable imperatively through the autorun.

## Definition of done

### The persistence module

1. **DoD-1** `[test]` With empty storage, `readWorkspaceLayout()` returns
   `navCollapsed: false` and `chatWidth: 0.35`, and the exported constants are
   exactly `WORKSPACE_LAYOUT_KEY === "bookwriter.workspace-layout"`,
   `CHAT_WIDTH_CSS_VAR === "--work-chat-width"`,
   `DEFAULT_CHAT_WIDTH_FRACTION === 0.35`, `MIN_CHAT_WIDTH_FRACTION === 0.15`,
   `MAX_CHAT_WIDTH_FRACTION === 0.6`, `CHAT_WIDTH_KEYBOARD_STEP === 0.02`.
2. **DoD-2** `[test]` A write followed by a read round-trips both fields, and the
   write touches **exactly one** storage key, which is `WORKSPACE_LAYOUT_KEY`.
3. **DoD-3** `[test]` Every one of `"not json"`, `"null"`, `"[]"`, `'"str"'`,
   `"42"`, `"{}"` and an object with wrong-typed fields reads back as the
   defaults, and **none of them throws**.
4. **DoD-4** `[test]` The fallback is **per field**: stored
   `{"navCollapsed":true,"chatWidth":"wide"}` reads back as `navCollapsed: true`
   with `chatWidth: 0.35`.
5. **DoD-5** `[test]` `chatWidth` is clamped on read — `0.95` reads back `0.6`,
   `0.01` reads back `0.15`, and `NaN` / `Infinity` read back `0.35` — and
   `clampChatWidth` passes `0.15` and `0.6` through unchanged.
6. **DoD-6** `[test]` `chatWidthFromPointer` is right-anchored and clamped:
   `(700, 1000)` is `0.3`, `(100, 1000)` is `0.6`, `(990, 1000)` is `0.15`, and
   `(500, 0)` is `0.35`.
7. **DoD-7** `[test]` `chatWidthCss(0.35)` is exactly `"35vw"`, and a
   keyboard-nudged value emits no float noise (a two-decimal-rounded `vw`
   string, never `"35.000000000000004vw"`).

### The navigator rail

8. **DoD-8** `[test]` Expanded (the default, `collapsed` omitted) the navigator
   still renders the **six** router-link entries with their visible labels — the
   regression guard for step `010/002`'s DoD-1/DoD-2.
9. **DoD-9** `[test]` Collapsed, the navigator still renders exactly **six**
   links findable by accessible name, with the **same `href`s** as in expanded
   mode.
10. **DoD-10** `[test]` Collapsed, the Chats entry is still **not** a link and
    still invokes `onShowChatList` when activated (US-105.AC-3 holds in both
    modes).
11. **DoD-11** `[test]` The rail class names (`work-nav-rail-root`,
    `work-nav-rail-section`, `work-nav-rail-body`) are present on the entries
    when collapsed and **absent** when expanded.

### The shell

12. **DoD-12** `[test]` The header carries a pin control whose accessible name is
    "Collapse navigator" when expanded and "Pin navigator open" when collapsed;
    activating it flips both the name and `aria-pressed`, and
    `readWorkspaceLayout().navCollapsed` becomes `true`.
13. **DoD-13** `[test]` A layout record seeded into storage **before** the shell
    renders is honoured on first render: a stored `navCollapsed: true` renders
    the pin control in its collapsed state, and a stored `chatWidth` is reflected
    by the handle's `aria-valuenow`.
14. **DoD-14** `[test]` The shell renders a `role="separator"` element with
    accessible name "Resize chat pane", `aria-valuemin` 15, `aria-valuemax` 60
    and, at defaults, `aria-valuenow` 35.
15. **DoD-15** `[test]` Pressing `ArrowLeft` on the focused handle at the default
    width widens the pane: `aria-valuenow` becomes 37,
    `readWorkspaceLayout().chatWidth` becomes `0.37`, and
    `document.documentElement`'s `--work-chat-width` is `"37vw"` — which is what
    proves the `autorun` is wired.
16. **DoD-16** `[test]` The keyboard path clamps: from a seeded `0.59`, two
    `ArrowLeft` presses leave `aria-valuenow` at 60 rather than exceeding it.
17. **DoD-17** `[test]` Unmounting the shell removes the `--work-chat-width`
    property from `document.documentElement`.

### Live-only

18. **DoD-18** `[manual/live]` Dragging the handle in a real browser resizes the
    chat pane continuously, tracks the pointer when it leaves the 6px strip,
    stops on pointer-up (and on pointer-cancel), and persists the final width
    across a reload. While dragging, **the content pane does not re-render per
    pointer move** — the width travels through the CSS variable only. See
    "Deliberately not automated" below for why this is not a test.
19. **DoD-19** `[manual/live]` At a desktop viewport the collapsed navigator is a
    centred icon-only rail with the labels hidden and a tooltip on hover, and the
    content pane reclaims the freed width; below the `sm` breakpoint the mobile
    drawer still shows the full-width labelled entries regardless of
    `navCollapsed`.
20. **DoD-20** `[manual/live]` Below the `md` breakpoint the resize handle is not
    shown, and the aside behaves exactly as it did before this feature.
21. **DoD-21** `[manual/live]` The aside's generated width is valid CSS in the
    browser — the `calc(var(--work-chat-width, 35vw))` wrapper survives Mantine's
    `rem()` converter, and the pane opens at the stored width with **no flash of
    the default width** before first paint.
22. **DoD-22** `[manual/live]` `cd frontend && npm run build` clean,
    `cd frontend && npm test` green, `cd frontend && npm run test:types` clean —
    and `frontend/tests/work/WorkspaceShell.test.tsx` and
    `frontend/tests/work/WorkNavigator.test.tsx` pass **unmodified**, so step
    `010/002`'s DoD-4/5/6/7 still hold.

### Deliberately not automated — the verifier gates this list in both directions

The test-coder must **not** write these, and the verifier must not ask for them:

- **The pointer drag itself.** jsdom has no layout engine
  (`getBoundingClientRect` returns zeros), no `PointerEvent` and no
  `setPointerCapture`. A drag test would synthesise coordinates and then call our
  own `chatWidthFromPointer` with them — it would test the test. The geometry is
  covered as a pure function (DoD-6); persistence and the CSS-variable wiring are
  covered through the keyboard path (DoD-15). Same precedent `frontend.md`
  already sets for `@dnd-kit` and for ProseMirror. → DoD-18.
- **The visual label hiding in the rail.** `vitest.config.ts` leaves
  `css: false`, so `global.css` resolves to an empty module and no media query
  ever evaluates. Only the `classNames` wiring is testable (DoD-11). → DoD-19.
- **Breakpoint behaviour.** `tests/setup.ts` stubs `matchMedia` to never match,
  and `visibleFrom` / `hiddenFrom` are pure CSS. → DoD-20.
- **The rendered px / `vw` values inside Mantine's generated `<style>` block.**
  Asserting on those tests Mantine's `rem()` converter, not this feature.
  → DoD-21.

## Out of scope

1. **Pane *orientation*** — vertical/horizontal split, or moving the chat pane.
   `frontend-workspace.md`'s out-of-scope bullet covered orientation and resize
   together; this feature settles resize only.
2. **A resizable *navigator*** — the navigator has exactly two widths, rail and
   expanded. No drag handle on the left edge.
3. **Per-book or server-side layout preferences.** One global key, device-local,
   by locked decision.
4. **Collapsing the chat pane entirely**, a double-click-to-reset gesture, or a
   snap-back animation.
5. **Anything under `frontend/src/work/components/chat/`** and any change to
   `ChatPaneSlot`'s props — `011.chat-panel` owns the pane's contents.
6. **`navItems.ts`** — the item list, its order, its icons and the active-match
   predicate are untouched.
7. **Any backend change, any `src/api/` or `src/types/` change, any route
   change.**
8. **`useMediaQuery` or any other `@mantine/hooks` introduction**, and any
   `window` `"resize"` listener.
9. **Editing `docs/architecture/`** — intended doc changes are recorded in
   `outcome.md` for the architect to apply.
10. **Editing `docs/plans/roadmap.md`** — this feature was not roadmapped;
    recording it there is `/roadmap`'s.
