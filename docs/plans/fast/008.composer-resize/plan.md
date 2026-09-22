# fast/008.composer-resize — Vertically adjustable chat composer

## Goal

Make the chat pane's prompt input a **fixed-height, drag-resizable** box: the
author drags its top edge to choose a height between ~2 text lines and half the
viewport, and that height is remembered device-locally in the existing
`bookwriter.workspace-layout` key. A taller composer shrinks the transcript; it
never overflows the pane.

## Source files

This list **is** the coder's scope; nothing else is touched.

- `frontend/src/work/workspaceLayout.ts` — **modify.** The persisted record gains
  `composerHeight`; new constants and two pure geometry helpers; the writer
  becomes a merging partial patch.
- `frontend/src/work/components/chat/chatPaneState.ts` — **modify.** Two
  observables plus three external resize operations.
- `frontend/src/work/components/chat/ComposerResizeHandle.tsx` — **NEW.** The
  composer's drag / keyboard divider.
- `frontend/src/work/components/chat/Composer.tsx` — **modify.** Autosizing comes
  off; the height is applied to the inner input.
- `frontend/src/work/components/chat/ChatPane.tsx` — **modify.** Render the handle
  between the transcript and the composer.

**Explicitly not in scope, and it matters:**
`frontend/src/work/components/shell/workspaceShellState.ts` must **not** be
touched — the merging partial write exists so that it needs no change (see
`context.md` → "Two owners, one key"). Neither is
`frontend/src/work/components/shell/WorkspaceShell.tsx`, nor anything under
`components/shell/`.

## Test files

Disjoint from Source files. This list **is** the test-coder's scope.

- `frontend/tests/work/workspaceLayout.test.ts` — **existing, extended.** Covers
  DoD-1 … DoD-6 (the pure module). It **will fail unmodified** once
  `WorkspaceLayout` gains a third field: it asserts the written object's shape and
  that exactly one storage key is written. Extending it is part of this feature.
- `frontend/tests/work/composerResize.test.tsx` — **NEW.** Covers DoD-7 … DoD-11
  (the state seeding, the handle, the composer).

Every other spec under `frontend/tests/` must keep passing **unmodified** — see
DoD-16.

## Interface intent

Prose only, per `docs/plans/CLAUDE.md`. `fast-skeleton` derives and freezes the
exact signatures. **Where a literal value appears below it *is* the contract** —
the skeleton must not round it, rename it, or move it.

> **Instruction to `fast-skeleton`:** record `ChatPaneState`'s **constructor
> signature** in `## Skeleton` even though this feature does not change it. The
> test-coder must construct one and may not read source.

### `frontend/src/work/workspaceLayout.ts` — modify

Still a pure module: no class, no MobX, **no DOM access** — every helper takes its
geometry as an argument, which is the sole reason it is testable without a window.

New exported constants:

- `MIN_COMPOSER_HEIGHT_PX` = `64` — approximately two text lines. The user-stated
  floor.
- `DEFAULT_COMPOSER_HEIGHT_PX` = `96` — approximately three lines. Chosen over
  "default equals minimum" because the composer used to *auto-grow* from two rows
  to six, so a fixed box at exactly the floor would feel smaller than what authors
  have today; three lines is a comfortable starting area with the handle right
  there to change it.
- `MAX_COMPOSER_HEIGHT_FRACTION` = `0.5` — a fraction of **viewport height**, so
  the transcript can never be squeezed out.
- `COMPOSER_HEIGHT_KEYBOARD_STEP` = `24` — pixels per arrow press, roughly one
  text line.

Changed exported shape:

- `WorkspaceLayout` gains **`composerHeight`**, a number of **pixels** (not a
  fraction — the two bounds are expressed differently on purpose, and the reason
  is in `context.md`). Document in-file that it is device-local view preference,
  deliberately not in the URL and not on the server, and deliberately **not per
  book**.

New exported functions:

- **`clampComposerHeight`** — takes a candidate pixel height and a viewport
  height, both numbers; returns a bounded pixel height. Pure.
  - A non-finite candidate yields the default, then clamped by the same rules.
  - The lower bound is always `MIN_COMPOSER_HEIGHT_PX`.
  - The upper bound is `MAX_COMPOSER_HEIGHT_FRACTION × viewportHeight`, **but the
    minimum wins when that product falls below it** — a composer thinner than two
    lines is unusable.
  - A viewport height that is **not finite or not positive** means the upper bound
    is **unknown**, and the result is clamped against the minimum alone. A nonsense
    environment must not shrink a stored preference; the next real use re-clamps.
- **`composerHeightFromDrag`** — takes the height at pointer-down, the `clientY`
  at pointer-down, the current `clientY`, and the viewport height; returns the
  clamped pixel height. The geometry is **delta-based**: `startHeight + (startY −
  clientY)`, so **dragging upward grows** the composer and downward shrinks it.
  The result goes through `clampComposerHeight`. This is the drag's **entire
  geometry**, extracted precisely so it can be verified with no DOM and no layout
  engine — the same split `chatWidthFromPointer` already uses.

Changed exported functions:

- **`readWorkspaceLayout`** — unchanged shape (takes nothing, returns a total
  `WorkspaceLayout`, never throws) and unchanged per-field fallback discipline,
  now covering three fields. `composerHeight` is validated as a finite number and
  clamped **to the minimum only**; the viewport-dependent maximum is *not* applied
  here, because this function must stay DOM-free. A record carrying a valid
  `navCollapsed` and `chatWidth` beside a missing, non-numeric or non-finite
  `composerHeight` keeps the first two and defaults the third.
- **`writeWorkspaceLayout`** — **the one signature widening in this feature.** It
  now takes a **partial** `WorkspaceLayout` patch, merges it over
  `readWorkspaceLayout()`'s total record, and writes the merged whole under the
  single key as JSON. It still swallows storage errors (quota, private mode).
  Merging over the *read* record — not over the raw stored string — is what stops
  a corrupt store from surviving a partial write.

  Two independent state classes now own different fields of one key
  (`WorkspaceShellState` owns `navCollapsed` + `chatWidth`, `ChatPaneState` owns
  `composerHeight`), and a merging writer is what makes it impossible for either
  to clobber the other. The existing shell call sites pass a full
  `{ navCollapsed, chatWidth }` object and therefore still satisfy a partial
  parameter with **no change to `workspaceShellState.ts`**.

### `frontend/src/work/components/chat/chatPaneState.ts` — modify

The file's header rule holds: **observable data and pure `get` computeds only, no
effectful methods.** Everything effectful below is a top-level function beside
`loadChatPane` / `sendChatTurn` / `stopChatTurn`.

`ChatPaneState` keeps every existing field untouched and gains:

- **`composerHeight`** — an observable number of pixels, **seeded in the
  constructor** from `readWorkspaceLayout()`'s value passed through
  `clampComposerHeight` against `window.innerHeight`. This is where the
  viewport-dependent maximum is first applied, so a height chosen on a larger
  monitor is corrected on first render rather than overflowing the pane.
- **`composerResizing`** — an observable boolean, true only while a pointer drag
  is in flight.
- **`composerResizeDispose`** — a **non-observable** slot, initialized to nothing,
  holding the current drag's detach-and-restore closure. It is added to the
  existing `makeAutoObservable` exclusion map beside `start`, `stop` and
  `setActive`; those three entries stay exactly as they are.

No new `get` computed is needed.

Three new external functions:

- **`beginComposerResize`** — takes the state and the pointer-down `clientY`.
  - Captures the current `composerHeight` and that `clientY` as **closure
    locals**, not as fields on the state.
  - Sets `composerResizing`; suppresses text selection
    (`document.body.style.userSelect = "none"`) and pins a `row-resize` cursor on
    `document.body`, **saving the prior values** so they can be restored.
  - Attaches `pointermove`, `pointerup` and `pointercancel` listeners to
    **`window`** — deliberately **not** `setPointerCapture`, because jsdom
    implements neither that nor `PointerEvent`, and window listeners keep tracking
    when the pointer outruns the 6px strip.
  - Stores the detach-and-restore closure on `composerResizeDispose`.
  - **Idempotent**: called again while a drag is already live, it is a no-op.
  - The `pointermove` handler does **exactly one thing**: assign
    `composerHeightFromDrag(startHeight, startY, event.clientY,
    window.innerHeight)` to `state.composerHeight`. **No storage write**, no other
    state change.
- **`endComposerResize`** — takes the state. Detaches the listeners, restores the
  saved body styles, clears `composerResizing`, and persists the height **once**,
  as a partial patch carrying `composerHeight` alone. **Idempotent, and guarded on
  `composerResizeDispose` rather than on `composerResizing`**, so a call with no
  drag in flight is a true no-op — **including no storage write**.
- **`nudgeComposerHeight`** — takes the state and a pixel delta. Assigns
  `clampComposerHeight(state.composerHeight + delta, window.innerHeight)` and
  persists the same partial patch. This is the keyboard path, and it is what makes
  the persistence wiring verifiable in jsdom at all.

### `frontend/src/work/components/chat/ComposerResizeHandle.tsx` — NEW

An `observer` component whose only prop is the `ChatPaneState` instance. It owns
**no state, no effect and no hook** — a leaf that reads an observable and calls
external functions, per `frontend.md`'s component rules.

It renders exactly one Mantine `Box`:

- **Accessibility:** `role="separator"`, `aria-orientation="horizontal"`,
  `aria-label="Resize composer"`, `tabIndex={0}`, and the value triple in
  **pixels** — `aria-valuemin` is `MIN_COMPOSER_HEIGHT_PX`, `aria-valuemax` is
  `MAX_COMPOSER_HEIGHT_FRACTION × window.innerHeight` rounded to a whole number,
  `aria-valuenow` is the current `composerHeight` rounded to a whole number.
- **`visibleFrom="md"`** — matching the aside's own breakpoint and
  `ChatResizeHandle`'s; there is no pane to resize below it.
- **`onPointerDown`** calls `preventDefault()` and then `beginComposerResize` with
  the event's `clientY`.
- **`onKeyDown`**: `ArrowUp` **grows** the composer by `+COMPOSER_HEIGHT_KEYBOARD_STEP`
  and `ArrowDown` **shrinks** it by the same step, both through
  `nudgeComposerHeight`, both calling `preventDefault()`. (Up grows, because the
  composer grows upward from the pane's bottom — the same direction as the drag.)
  Any other key is ignored.
- **Inline style:** an **ordinary flow child**, not positioned — `height: 6`,
  `flexShrink: 0`, `cursor: "row-resize"`, `touchAction: "none"`. This is the one
  place it deliberately differs from `ChatResizeHandle`, which is absolutely
  positioned over the aside's edge.

### `frontend/src/work/components/chat/Composer.tsx` — modify

Two changes, and nothing else in the file moves:

- **`autosize`, `minRows` and `maxRows` come off the `<Textarea>`** (:93-95). The
  input is now exactly as tall as it is told and scrolls internally, which is the
  browser's default for a fixed-height textarea.
- **The `<Textarea>` gains `styles` targeting its inner `input`** with the height
  set to `state.composerHeight` pixels and **`resize: "none"`**. The `resize:
  "none"` is not cosmetic: a fixed-height `<textarea>` keeps the browser's native
  bottom-right grip, which would sit directly under the Send icon and compete with
  our handle for the same gesture.

**Untouched, deliberately:** the root `<Stack gap="xs" style={{ flexShrink: 0 }}>`
(:72), the alert banners, `value` / `onChange` (:141), the `onKeyDown` Ctrl/Cmd+Enter
send and plain-Enter newline (:144-155), `disabled`, `rightSectionWidth={40}`,
`rightSectionPointerEvents="all"`, `rightSectionProps`, and the Send / Stop
`ActionIcon` swap in its single slot. `rightSectionWidth` in particular must
**not** be removed as newly redundant — it keeps the slot and the input's text
padding deterministic.

### `frontend/src/work/components/chat/ChatPane.tsx` — modify

Inside the existing `{state.activeChat && …}` block (:193-203), render
`<ComposerResizeHandle/>` with the pane state **between `<MessageList/>` and
`<Composer/>`**. That is the whole change.

The root `<Stack gap="sm" h="100%" mih={0}>` (:97) is untouched — its `gap`
included.

## Definition of done

`[test]` items are the coverage contract: the test-coder must cover each with a
test citing its id. `[manual/live]` items carry no automated test and the verifier
records them as requires-live-run.

### The pure module — `frontend/tests/work/workspaceLayout.test.ts`

1. **DoD-1** `[test]` The new constants are exactly `MIN_COMPOSER_HEIGHT_PX ===
   64`, `DEFAULT_COMPOSER_HEIGHT_PX === 96`, `MAX_COMPOSER_HEIGHT_FRACTION ===
   0.5`, `COMPOSER_HEIGHT_KEYBOARD_STEP === 24`, and `WORKSPACE_LAYOUT_KEY` is
   still `"bookwriter.workspace-layout"`.
2. **DoD-2** `[test]` `composerHeightFromDrag` is delta-based and directional: at a
   viewport height of `800` (so the maximum is `400`), starting from a height of
   `200` at `clientY` `500`, a move to `400` gives `300` (upward **grows**) and a
   move to `600` gives `100` (downward **shrinks**).
3. **DoD-3** `[test]` `composerHeightFromDrag` clamps at both ends: from the same
   start, a move to `100` yields `400` rather than `600`, and a move to `700`
   yields `64` rather than `0`.
4. **DoD-4** `[test]` `clampComposerHeight` bounds correctly — anything below `64`
   becomes `64`; anything above `0.5 × viewportHeight` becomes that product; a
   non-finite candidate yields `96`; a viewport height of `0` or a negative or
   non-finite one clamps against the **minimum only** (a large candidate passes
   through); and when `0.5 × viewportHeight` falls **below** `64` (e.g. a viewport
   height of `100`) the **minimum wins**.
5. **DoD-5** `[test]` Persistence round-trips all three fields through exactly
   **one** storage key, which is `WORKSPACE_LAYOUT_KEY`; and the write is a
   **merging patch** — writing only `composerHeight` leaves a stored `navCollapsed`
   and `chatWidth` intact, and writing only `{ navCollapsed, chatWidth }` leaves a
   stored `composerHeight` intact.
6. **DoD-6** `[test]` `readWorkspaceLayout` keeps its per-field fallback across
   three fields and still never throws: a stored record with valid `navCollapsed`
   and `chatWidth` but a **missing** or **garbage** `composerHeight` reads back
   with the first two preserved and `composerHeight === 96`; a stored
   `composerHeight` of `10` reads back as `64` (clamped to the minimum); and a
   stored `composerHeight` far above any viewport reads back **unchanged**,
   because the maximum is applied at use, not at read.

### The state, the handle and the composer — `frontend/tests/work/composerResize.test.tsx`

7. **DoD-7** `[test]` A freshly constructed `ChatPaneState` seeds `composerHeight`
   from storage, clamped against the current viewport: with empty storage it is
   `96`; with a stored height far above half the viewport and `window.innerHeight`
   set to `800`, it is `400`. (Seed storage **before** constructing — the state
   hydrates in its constructor.)
8. **DoD-8** `[test]` The handle renders with `role="separator"`,
   `aria-orientation="horizontal"`, accessible name **"Resize composer"**,
   `aria-valuemin` `64`, `aria-valuemax` equal to half the viewport height rounded,
   and `aria-valuenow` equal to the current height.
9. **DoD-9** `[test]` The handle is keyboard operable: with focus on it, `ArrowUp`
   grows the height by exactly `24` and `ArrowDown` shrinks it by exactly `24`,
   both reflected in `aria-valuenow`; the same bounds hold as in DoD-4 (repeated
   `ArrowDown` stops at `64`, repeated `ArrowUp` stops at half the viewport).
10. **DoD-10** `[test]` Each keyboard nudge **persists**: after a nudge,
    `readWorkspaceLayout().composerHeight` equals the new height, while a
    `navCollapsed` and `chatWidth` seeded into storage beforehand are **unchanged**
    (the two-owner merge holds end to end).
11. **DoD-11** `[test]` The composer's `<textarea>` is rendered at exactly
    `state.composerHeight` pixels and **does not autosize**: entering a value many
    lines longer than the old six-row maximum leaves the rendered height unchanged.
    In the same render, the `Send` accessible name is present, it becomes `Stop`
    while a turn is streaming, Ctrl+Enter and Cmd+Enter send, and plain Enter does
    not — the `023` contract still holds.

### Live-only

12. **DoD-12** `[manual/live]` **The pane's vertical contract survives.** A
    composer dragged to its maximum **shrinks the transcript** and never overflows
    the aside; `MessageList`'s `flex: 1` + `minHeight: 0`, `Composer`'s root
    `flexShrink: 0` and `ChatPane`'s root `h="100%" mih={0}` are all present and
    unchanged in the diff. jsdom has no layout engine, so this is verified by
    **inspection plus a real browser**, never by a test. (This is the briefing's
    `[verify]` item, expressed in the two tags `docs/plans/CLAUDE.md` allows.)
13. **DoD-13** `[manual/live]` The pointer drag itself: dragging the handle resizes
    continuously, keeps tracking when the pointer leaves the 6px strip, stops on
    pointer-up **and** on pointer-cancel, does not select text mid-drag, restores
    the cursor afterwards, writes storage **once at the end** rather than per move,
    and the height survives a reload.
14. **DoD-14** `[manual/live]` With more text than fits, the textarea **scrolls
    internally** at its chosen height, and the browser's **native resize grip is
    absent** — so the only resize affordance is the handle.
15. **DoD-15** `[manual/live]` Below the `md` breakpoint the handle is not shown and
    the pane behaves exactly as it did before this feature.
16. **DoD-16** `[manual/live]` `cd frontend && npm run build` clean,
    `cd frontend && npm test` green, `cd frontend && npm run test:types` clean —
    and every spec under `frontend/tests/` **other than the two in the Test files
    list** passes unmodified, including the chat-pane specs that assert the
    `Send` / `Stop` contract.

### Deliberately not automated — the verifier gates this list in both directions

The test-coder must **not** write these, and the verifier must not ask for them:

- **The pointer drag.** jsdom has no layout engine, no `PointerEvent` and no
  `setPointerCapture`. A jsdom "drag" would synthesise coordinates and then feed
  them to our own `composerHeightFromDrag` — it would test the test. The geometry
  is covered as a pure function (DoD-2, DoD-3) and the persistence wiring through
  the keyboard path (DoD-9, DoD-10). Same precedent `frontend.md` records for
  `@dnd-kit` and ProseMirror, and `fast/005` for the width drag. → DoD-13.
- **The flex chain.** `frontend-workspace.md` states outright that a break in it is
  silent under test. → DoD-12.
- **Breakpoint behaviour.** `tests/setup.ts` stubs `matchMedia` to never match and
  `visibleFrom` is pure CSS. → DoD-15.
- **`resize: "none"` and internal scrolling.** Both are rendering behaviour jsdom
  does not implement. → DoD-14.
- **Mounting `ChatPane` to prove the handle sits between the transcript and the
  composer.** Both new surfaces take the state as a prop and are tested in
  isolation with no API mock; the ordering inside the pane is inspected. → DoD-12.

## Out of scope

1. **Horizontal / width resizing** — delivered by `fast/005`; this feature adds no
   second width mechanism.
2. **Per-book composer height.** One global key, device-local, by locked decision.
3. **Mobile.** The handle is desktop-only (`visibleFrom="md"`), exactly like
   `ChatResizeHandle`.
4. **Transcript auto-scroll.** A known, separately-tracked gap recorded in
   `frontend-workspace.md`; a taller composer makes it more visible but does not
   make it this feature's.
5. **Double-click-to-reset**, a snap-back animation, or collapsing the composer
   entirely.
6. **`workspaceShellState.ts`, `WorkspaceShell.tsx` and anything else under
   `components/shell/`** — the merging partial write exists so none of them needs
   to change.
7. **`MessageList.tsx`, `ThinkingBlock.tsx`, `ToolCallTrace.tsx`,
   `ChatSettingsPanel.tsx`** and every other file under `components/chat/` not
   named in Source files.
8. **Any backend change, any `src/api/` or `src/types/` change, any route change,
   any new dependency.**
9. **A CSS custom property or an `autorun` for the height** — see `context.md` for
   why `fast/005`'s indirection does not transfer.
10. **Editing `docs/architecture/`** — intended doc changes are recorded in
    `outcome.md` for the architect to apply.
11. **Editing `docs/plans/roadmap.md`** — this feature was not roadmapped;
    recording it there is `/roadmap`'s.
