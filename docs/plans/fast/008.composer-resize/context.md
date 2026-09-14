# Context — fast/008.composer-resize

Feature-wide context for the single plan in `plan.md`. Distilled from the
orchestrator's briefing (harvest complete; every open decision user-confirmed).
Read this before `plan.md`.

## What this feature is

The chat pane's prompt input becomes **vertically adjustable by dragging its top
edge**, and the chosen height is remembered across reloads. **Frontend only** —
five source files, all under `frontend/src/work/`. No backend, no API, no DTO,
no route, no product id, no new dependency.

There is **no `brief.md`** and no roadmap row: this feature was not roadmapped,
and `008` was minted by `/fast-feature`, not by `/roadmap`. This plan must not
edit `docs/plans/roadmap.md`.

## Locked decisions (user-confirmed — do not re-litigate)

| Decision | Choice |
|---|---|
| Sizing model | **Fixed height, not autosize.** Once dragged, the textarea is exactly that tall and scrolls internally. `autosize` / `minRows` / `maxRows` come off. |
| Minimum | **~2 text lines = 64px.** |
| Maximum | **50% of viewport height**, expressed as a fraction so the transcript can never be squeezed out — mirroring how chat *width* is clamped to 15–60% of viewport width. |
| Persistence | **Global**, in the existing single `bookwriter.workspace-layout` key, as a third field beside `navCollapsed` and `chatWidth`. **Not per book.** |

## Why the live height is a plain observable, and not a CSS custom property

`fast/005` drove the chat pane's *width* through a CSS custom property written by
an `autorun`, and deliberately forbade `WorkspaceShell` from ever reading the live
fraction in its own JSX. That indirection existed for exactly one reason: the
shell is the heaviest component in the entry, and observing a value that changes
on every `pointermove` would re-render the whole content pane per move.

**None of that applies here.** The live height lives as an observable on
`ChatPaneState`, read directly by `Composer` and by the new handle. `Composer`
already receives that state and already re-renders **per keystroke** on
`state.pendingPrompt`, so a per-`pointermove` re-render of that same subtree costs
the same as ordinary typing. Adding a CSS variable plus an `autorun` would buy
nothing and would put a second, differently-shaped resize mechanism in the same
pane. Recorded because the obvious move is to copy `005` wholesale.

## Two owners, one key — why `writeWorkspaceLayout` becomes a merge

`bookwriter.workspace-layout` now has **two independent writers living in
different state classes**:

- `WorkspaceShellState` owns `navCollapsed` and `chatWidth` (`fast/005`);
- `ChatPaneState` owns `composerHeight` (this feature).

Neither holds the other's fields, and neither should. If `writeWorkspaceLayout`
keeps taking a whole record, every writer has to re-read the record and spread it
before writing — the same merge, written three times, in the wrong place — and
`workspaceShellState.ts` would have to be dragged into this feature's scope
purely to satisfy a new required field.

So **`writeWorkspaceLayout` takes a partial patch and merges it over the current
stored record** (over `readWorkspaceLayout()`, which is already total, so a
corrupt store cannot survive a partial write). The existing shell call sites pass
a full `{ navCollapsed, chatWidth }` object, which still satisfies a partial
parameter, so **`workspaceShellState.ts` needs no change and stays out of scope.**
This is the one signature widening this feature makes.

## Why the maximum is applied at use and not at read

`readWorkspaceLayout()` takes no arguments and touches no DOM — that is what makes
it testable with no window, and it is the shape `fast/005` froze. `chatWidth` is a
*fraction*, so it can be fully clamped on read. `composerHeight` is in **pixels**,
and its upper bound depends on the viewport height, which `readWorkspaceLayout`
has no business knowing.

Therefore: **read clamps to the minimum only; the viewport-dependent maximum is
applied at every point of use** — the `ChatPaneState` constructor, the drag move
handler, and the keyboard nudge, all three of which legitimately have
`window.innerHeight`. A stored height larger than half of *this* screen is not
corrupt data; it is a height chosen on a bigger monitor, and it is corrected the
moment it is used.

## What already exists (verified by the harvester — do not re-harvest)

### `frontend/src/work/workspaceLayout.ts` — the module tier's sixth member

Pure module: no class, no MobX, no DOM. All geometry taken as arguments. Exports
today: `WORKSPACE_LAYOUT_KEY` (`"bookwriter.workspace-layout"`),
`CHAT_WIDTH_CSS_VAR`, `DEFAULT_CHAT_WIDTH_FRACTION` = `0.35`,
`MIN_CHAT_WIDTH_FRACTION` = `0.15`, `MAX_CHAT_WIDTH_FRACTION` = `0.6`,
`CHAT_WIDTH_KEYBOARD_STEP` = `0.02`; the `WorkspaceLayout` shape
(`navCollapsed`, `chatWidth`); `clampChatWidth`, `chatWidthFromPointer`,
`chatWidthCss`; `readWorkspaceLayout` (total, never throws, **falls back per
field**) and `writeWorkspaceLayout` (swallows storage errors).

### `frontend/src/work/components/chat/Composer.tsx` (159 lines)

The whole file is the input. Root `<Stack gap="xs" style={{ flexShrink: 0 }}>`
(:72) holding optional alert banners then the `<Textarea>` (:90) with `autosize`
(:93), `minRows={2}` (:94), `maxRows={6}` (:95), `value={state.pendingPrompt}`,
`disabled={streaming || closeReadOnly}`, `rightSectionWidth={40}`,
`rightSectionPointerEvents="all"`,
`rightSectionProps={{ style: { alignItems: "flex-end", paddingBottom: 4 } }}`,
`rightSection` = the Stop `ActionIcon` while streaming else the Send
`ActionIcon`, `onChange` (:141) and `onKeyDown` (:144-155) where Ctrl/Cmd+Enter
sends and plain Enter is a newline. **No `mah` / `mih` anywhere.**

### `frontend/src/work/components/chat/ChatPane.tsx`

Root `<Stack gap="sm" h="100%" mih={0}>` (:97). Inside `{state.activeChat && …}`
at :193-203 it renders `<MessageList/>` then `<Composer/>`.

### `frontend/src/work/components/chat/chatPaneState.ts` (1479 lines)

`class ChatPaneState` at :201; `makeAutoObservable(this, { start: false, stop:
false, setActive: false })` in the constructor (:309-319); `pendingPrompt = ""`
at :286. File header doc: **"observable data + pure `get` computeds ONLY — no
effectful methods."** Every operation is an external module-level
`(state, …, signal?)` function mutating through `runInAction` — `loadChatPane`
(:573), `sendChatTurn` (:995), `stopChatTurn` (:1159). **The pane holds no book
id**: it is book-scoped by remount.

### `frontend/src/work/components/shell/ChatResizeHandle.tsx` (77 lines)

The precedent handle (`fast/005`): `role="separator"`,
`aria-orientation="vertical"`, `aria-label="Resize chat pane"`,
`aria-valuemin/max/now`, `tabIndex={0}`, `visibleFrom="md"`, `onPointerDown` →
`beginChatResize`, `onKeyDown` ArrowLeft/ArrowRight → `nudgeChatWidth`, style
`{ position: "absolute", insetBlock: 0, insetInlineStart: 0, width: 6, cursor:
"col-resize", touchAction: "none", zIndex: 1 }`.

**The one structural difference to copy carefully:** that handle is *absolutely
positioned* over the aside's edge. This one is an **ordinary flow child** of the
pane's `Stack`, between the transcript and the composer, so it needs
`flexShrink: 0` and no positioning at all.

### `frontend/src/work/components/shell/workspaceShellState.ts:162-232`

`beginChatResize` / `endChatResize` / `nudgeChatWidth` — the drag lifecycle to
copy: listeners on **`window`** (`pointermove` / `pointerup` / `pointercancel`)
and **not** `setPointerCapture` (jsdom implements neither that nor
`PointerEvent`, and window listeners keep tracking when the pointer outruns a 6px
strip); `document.body.style.userSelect = "none"` plus a cursor override, both
saved and restored by a `resizeDispose` closure; begin and end both idempotent;
storage written **once on pointer-up**, never per move.

## Architecture rules that constrain every decision

From `docs/architecture/frontend.md`:

- **`observer` on every component**, no exceptions.
- **State is data + `get` computeds, never effectful methods.** All effectful work
  is an external top-level `(state, …)` function using `runInAction`. This feature
  adds three, beside `loadChatPane` / `sendChatTurn` / `stopChatTurn`.
- **No custom `useX` hooks**, no `useCallback` / `useMemo` / `useReducer`.
  `useEffect` only at page level — the new handle owns no hook at all.
- **A child that receives a state instance does not also acquire a lifecycle**
  (`ChatPane` runs no effect). The handle adds none either.

From `docs/architecture/frontend-workspace.md` → the chat pane:

- **The pane's vertical contract**, stated there *because feature `023`'s feedback
  round 1 found it broken*: the aside is fixed-height, the pane root fills it, the
  **transcript is the single growing child** (`flex: 1` **plus `minHeight: 0`**,
  `MessageList.tsx:51-65`), and the composer is **non-shrinking**. A taller
  composer must **shrink the transcript, never overflow**. The doc says it
  outright: *"A pane change that breaks this chain breaks it silently — jsdom has
  no layout engine, so no test will catch it."* That is why the chain is a
  `[manual/live]` criterion here, not a `[test]` one.
- **The send/stop control lives in ONE `rightSection` slot**, and the accessible
  names **`Send` / `Stop` are a documented test contract, not decoration.**
- `frontend.md`'s four `rightSection` facts still bind — in particular
  `rightSectionPointerEvents="all"` (a control there is otherwise dead to the
  pointer, and **jsdom does not hit-test, so no `fireEvent` test catches it**) and
  the **explicit `rightSectionWidth`**. Fact 3 justified the explicit width by the
  input having no fixed height under `autosize`; the input now *has* a fixed
  height, but the explicit width still keeps the slot and the text padding
  deterministic. **Do not remove it as newly redundant.**

## The non-obvious constraints

Each of these compiles, typechecks and passes tests while being wrong.

1. **`resize: "none"` is mandatory on the input.** A `<textarea>` with a fixed
   height keeps the browser's **native bottom-right resize grip**, which would sit
   directly under the Send icon in the `rightSection` and compete with our handle
   for the same gesture. It is invisible in jsdom.
2. **Dropping `autosize` must not drop the explicit `rightSectionWidth` or
   `rightSectionPointerEvents`.** See above.
3. **The drag geometry must stay delta-based, not absolute.** Pointer-down records
   the start height and the start `clientY`; each move computes `startHeight +
   (startY - clientY)`. An absolute formula ("viewport bottom minus `clientY`")
   would make the composer jump to the pointer on the first move, because the
   handle is not at the composer's exact top edge (there is a `Stack` gap above
   it). Delta-based also means the pure function needs no element geometry — which
   is the only reason it is testable at all.
4. **The start height and start Y are closure locals inside
   `beginComposerResize`, not fields on the state.** The move handler is created
   in that function and closes over them. Putting them on the state would add two
   fields that must then be excluded from `makeAutoObservable` and would re-render
   the pane at pointer-down for no reason.
5. **The maximum must never win over the minimum.** On a very short viewport,
   `0.5 × viewportHeight` can fall *below* 64px. The clamp resolves that in favour
   of the minimum; a composer thinner than two lines is unusable, and a short
   viewport is the rarer problem.

## Harness facts the test-coder needs

- `frontend/vitest.config.ts`: jsdom, **`globals: false`** — every spec imports its
  own `describe` / `it` / `expect` / `vi` from `"vitest"`.
- `./tests/setup.ts` stubs `matchMedia` (never matches), `ResizeObserver` and
  `scrollIntoView`, and runs `afterEach(() => { cleanup(); localStorage.clear(); })`.
  **`localStorage` is real jsdom, not mocked.**
- **`ChatPaneState` hydrates in its constructor**, so a rehydration test must seed
  storage **before** constructing the state, not after.
- **`window.innerHeight` is assignable in jsdom** and defaults to `768` (so the
  default maximum under test is `384`). A spec that asserts on `aria-valuemax` or
  on a clamped height should **set `window.innerHeight` explicitly** rather than
  rely on the default.
- **`styles={{ input: … }}` on a Mantine `Textarea` lands as an inline `style` on
  the `<textarea>` element**, so the applied height is readable through the
  element's own inline style.
- `frontend/tests/support/render.tsx` exports `renderWithProviders(ui, { route? })`;
  its `env="test"` is load-bearing (no portals, no transitions).
- Specs mock `src/api/*` with whole-module `vi.mock` factories, **never `fetch`**.
  **This feature's component spec should need no API mock at all** — both new
  surfaces (`ComposerResizeHandle`, `Composer`) take the state instance as a prop,
  so a hand-constructed `ChatPaneState` renders them in isolation with no load
  path. That is why `ChatPane.tsx`'s wiring is a `[manual/live]` inspection item
  rather than a mounted-pane test.
- **`frontend/tests/work/workspaceLayout.test.ts` will break** the moment
  `WorkspaceLayout` gains a third field — it asserts the written object's shape and
  that exactly one key is written. That is why it is in the Test files list.

## A gap that is deliberately not closed

A composer drag in flight when the workspace unmounts is **not** cleaned up by the
shell — `WorkspaceShell.tsx` is out of scope and would be pulled in for one
cleanup line. It is a non-problem in practice for two reasons: a drag holds the
pointer, so a route change cannot occur mid-drag; and the listeners live on
**`window`**, so the eventual `pointerup` still runs `endComposerResize`,
detaching the listeners and restoring the body styles even though the state object
is by then orphaned. The only residue is one harmless storage write.

## Scope-check note for the verifier — this is not a promotion signal

Five source files, ~180 LoC, two test files. One logical change: the composer's
height. **No cross-layer coordination** (frontend only — no API, no DTO, no route,
no backend). **No ordering dependency** — the pure helpers, the state ops, the
handle and the two component edits are independently authorable and only meet at
`ChatPane.tsx`'s two-line wiring. **No design ambiguity** — every decision is
locked in the table above.

## Non-negotiables the coder must not "improve"

1. **`autosize`, `minRows` and `maxRows` all come off.** Do not keep `maxRows` "as
   a safety net" — it reintroduces autosizing.
2. **`resize: "none"` stays on the input.**
3. **`rightSectionWidth={40}`, `rightSectionPointerEvents="all"` and
   `rightSectionProps` are untouched**, as are the Send/Stop accessible names and
   the Ctrl/Cmd+Enter key handling.
4. **`MessageList`'s `flex: 1` + `minHeight: 0` and `Composer`'s root
   `flexShrink: 0` are untouched**, as are `ChatPane`'s root `h="100%" mih={0}`
   and its `Stack` `gap`.
5. **No CSS custom property and no `autorun`** for the height — see above.
6. **No `window` `"resize"` listener**, anywhere. The clamp re-applies at the next
   use.
7. **No `setPointerCapture`** — window listeners, per the `005` precedent.
8. **Storage is written once at the end of a drag**, never per `pointermove`.
9. **Do not touch `workspaceShellState.ts`** — the partial-patch write exists
   precisely so it needs no change.
10. **Do not edit `docs/architecture/`** — intended doc changes go in `outcome.md`
    for the architect to apply.
