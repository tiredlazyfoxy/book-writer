# Context — fast/010.transcript-autoscroll

Feature-wide context for the single plan in `plan.md`. Distilled from the
orchestrator's briefing (harvest complete; every open decision user-confirmed).
Read this before `plan.md`.

## What this feature is

The chat pane's transcript **follows the newest content when the author is
already at the bottom**, **preserves the author's position when they are scrolled
up**, and **always starts at the bottom** on load, reload or chat switch.

**Frontend only** — four source files, all under `frontend/src/work/`. No
backend, no API, no DTO, no route, no product id, no new dependency, nothing
persisted.

There is **no `brief.md`** and no roadmap row: this feature was not roadmapped,
and `010` was minted by `/fast-feature`, not by `/roadmap`. This plan must not
edit `docs/plans/roadmap.md`.

## This closes a recorded gap, it does not repair a defect

`docs/architecture/frontend-workspace.md:329` records it as a **known gap**, not a
bug: the transcript has *never* auto-scrolled. Before feature `023`'s flex repair
the region was capped at 320px and was rarely the element that scrolled; now it
fills the pane, so a streaming turn writes below the fold with nothing following
it. `fast/008` listed it as out-of-scope item 4 and `fast/009`'s plan named it
too. This feature closes it.

The mechanism is **not open for redesign** — the architecture already chose it,
twice, before the feature existed:

- `frontend.md:248` — *"For rare imperative side-effects on observable change
  (e.g. auto-scroll while streaming), use a single `autorun` started in the mount
  `useEffect` and disposed on cleanup."*
- `frontend.md:244` — `useEffect` is **forbidden in leaf components**.
- `MessageList.tsx:39-43`, the leaf's own docblock — *"the one sanctioned
  imperative side-effect — auto-scroll while streaming — belongs, if shipped, in a
  single pane-level mount `autorun`, never in this leaf."*
- `frontend-workspace.md:329` names the same mechanism.

So the follow lives in an `autorun` inside **`WorkspaceShell`'s existing mount
`useEffect`**, reusing that one effect. That file already does exactly this: the
`--work-chat-width` autorun at `WorkspaceShell.tsx:89-91`, disposed in the
existing cleanup at `:92-107`. The new disposer goes beside `disposeChatWidthVar()`.

## Locked decisions (user-confirmed — do not re-litigate)

| Decision | Choice |
|---|---|
| Send snaps to bottom | **Yes.** A scrolled-up author who hits Send is re-pinned, so they see their own message land and the reply arrive. Send is an explicit "done reading back" gesture. |
| Jump-to-latest affordance | **None.** No pill, no badge, no unread button, no count. When scrolled up and a reply arrives below the fold, **nothing** is rendered — the position is preserved silently. This is exactly what was asked for and it is what keeps the feature small. |
| Pin threshold | **64 CSS pixels** from the bottom counts as "at the bottom". |
| Persistence | **None.** "On reload — always to bottom" is the *absence* of persistence. No `localStorage`, no URL param, no `workspaceLayout.ts` field. |

**Why 64px and not one of the two obvious alternatives.** Exact-bottom
(`scrollTop + clientHeight === scrollHeight`) is brittle: fractional scroll
heights and browser zoom routinely leave 1–2px, which would silently unpin and
make auto-follow look broken for no reason the author can see. A generous ~200px
would yank the author down when they had deliberately scrolled back a little.
~64px is roughly one line of prose of slack — enough to absorb subpixel error,
not enough to override a real intent to read back.

## Why the geometry is a pure module and not `onBottomReached`

Mantine's `ScrollArea` (v7.17.8) offers `onBottomReached` / `onTopReached`
alongside `viewportRef` and `onScrollPositionChange`. This feature deliberately
uses the latter pair plus **our own pure threshold predicate**, for three reasons:

1. **The 64px threshold is a user-locked contract**, so we must own it. Mantine's
   is internal and can move between minor versions.
2. **`onBottomReached` is an edge trigger.** It tells you that you *arrived* at
   the bottom; it gives no way to ask *"am I at the bottom right now"*, which is
   precisely the query the follow needs on every transcript growth.
3. **A pure predicate over three plain numbers is testable with no layout
   engine** — which is the entire reason `fast/008` split `clampComposerHeight`
   and `composerHeightFromDrag` out of its drag, and why `fast/005` split
   `chatWidthFromPointer` out of its own. **Three features is a settled idiom.**

## Why both new state slots are non-observable

`ChatPaneState` gains two (optionally three) **non-observable** slots, added to
the existing `makeAutoObservable` exclusion map beside `composerResizeDispose`.
This is not a micro-optimization; observability would break the feature two ways:

- The pinned flag is written on **every scroll event, at pointer rate**. Making
  it observable would fire the pane's observers continuously while the author
  merely scrolls.
- Worse, the follow `autorun` reads the pinned flag. If it were observable, the
  autorun's own programmatic scroll would change it and **re-enter itself**.

`composerResizeDispose: false` (added by `fast/008`) is the precedent for a
non-observable slot on this class — copy its shape, and leave the other three
entries (`start`, `stop`, `setActive`) exactly as they are.

## The two mechanics that are easy to get wrong

### 1. The follow must be deferred to after paint

A MobX `autorun` fires **synchronously on mutation, before React re-renders**.
Measuring `scrollHeight` at that instant yields the **pre-update** height, so
scrolling to it lands short of the new bottom — by exactly the height of the
content that just arrived. The follow must therefore be scheduled with
`requestAnimationFrame`.

It must also **coalesce**: a streaming turn mutates `streamingContent` per token,
and one frame per delta would queue hundreds of redundant scroll writes. Store
the pending frame handle and skip (or cancel) a second schedule.

**This is the repo's first `requestAnimationFrame` use anywhere under
`frontend/`.** That is why the plan spells out how a test flushes a pending frame
instead of assuming a house idiom exists.

### 2. The programmatic scroll fires its own scroll event — and that is fine

Writing `viewport.scrollTop` fires `onScrollPositionChange`, which recomputes the
pinned flag. Because the write lands at the bottom, the recomputation yields
**pinned = true**, so the loop is self-consistent and terminates immediately.

This is recorded so that **the coder does not invent a suppression flag** ("ignore
the next scroll event") — such a guard would also swallow a genuine user scroll
that happens to land in the same frame, which is the one event that must never be
missed. And so the **verifier does not read the feedback as a defect**.

## What already exists (verified by the harvester — do not re-harvest)

### `frontend/src/work/components/chat/MessageList.tsx`

`export interface MessageListProps { state: ChatPaneState; }` (:45-47);
`export const MessageList = observer(function MessageList({ state }: MessageListProps)`
(:49). Renders `<ScrollArea type="auto" style={{ flex: 1, minHeight: 0 }}>`
(:51-64) wrapping `<Stack gap="sm" p="xs">` mapping `state.renderedMessages`.
**No `ref` is attached anywhere in the file today**, and there are **zero
`useRef` hits anywhere under `frontend/src/`** — this feature introduces the
repo's first DOM handle.

### Mantine `ScrollArea` — `@mantine/core@7.17.8`, read from its `.d.ts`

- `viewportRef?: React.ForwardedRef<HTMLDivElement>` (`ScrollArea.d.ts:25`) —
  **the scrolling element is the internal viewport div and is reachable only
  through this prop.** The component's own `ref` targets the **root, non-scrolling
  wrapper**; using it is the single most likely wrong turn in this feature.
- `onScrollPositionChange?: (position: { x: number; y: number }) => void` (:28-32)
- `viewportProps?: React.ComponentPropsWithRef<'div'>` (:27)
- `onBottomReached?` / `onTopReached?` (:33-36) — present, deliberately unused.

### `frontend/src/work/components/chat/chatPaneState.ts`

`class ChatPaneState implements CloseTurnController` (:208), zero-arg constructor
(:354). Class docblock rule: **"holds observable data + pure `get` computeds
ONLY"** — everything effectful is a top-level function beside `loadChatPane` /
`sendChatTurn` / `stopChatTurn`.

`makeAutoObservable` exclusion map, verbatim (:373-378):

```ts
makeAutoObservable(this, {
  start: false,
  stop: false,
  setActive: false,
  composerResizeDispose: false,
});
```

Observable fields this feature reads: `messages: ChatMessageResponse[]` (:265),
`streamingContent: string` (:270), `streamingThinking: string` (:272),
`streamingToolTrace: ToolTraceRow[]` (:281); plus `activeChatId` (:218),
`messagesStatus`, `turnStatus` (:284). `get renderedMessages(): RenderedMessage[]`
(:610) derives the full transcript including the live bubble and is what
`MessageList` iterates.

Exported operations (all in this file):

```
loadChatPane(state, bookId, signal?)            // 652 — calls loadChatMessages at :707
pickChat(state, bookId, chatId)                 // 717
loadChatMessages(state, bookId, chatId, signal?) // 1104 — resets messages + streaming buffers
sendChatTurn(state, bookId, text)               // 1197 — SIGNATURE FROZEN, see :1185
retryChatTurn(state, bookId)                    // 1318
stopChatTurn(state)                             // 1361
beginComposerResize / endComposerResize / nudgeComposerHeight // 1708 / 1769 / 1791
```

`sendChatTurn` carries the comment **"023 EXTENDS THE CONTRACT, SIGNATURE
UNCHANGED"** (:1185). This feature must not change it either.

Module-private seams: `turnStreamHandlers` (:1415) — `onThinking` appends to
`streamingThinking` (:1421-1426), `onDelta` appends to `streamingContent`
(:1427-1433), `onDone` → `finishTurn` (:1434-1436); `finishTurn` (:1500) swaps
`state.messages = reloaded` and clears the streaming buffers (:1509-1520).

### `frontend/src/work/components/shell/WorkspaceShell.tsx`

`useState(() => new ChatPaneState())` (:58). **One** mount `useEffect(() => {…},
[state, chatPaneState])` at :60-108, containing in order: the close-turn
controller registration, the `chatPaneController` literal whose `openChat` calls
`pickChat` then `void loadChatMessages(…)` (:73-81), that controller's
registration, `void loadWorkspaceBook(…)`, `void loadChatPane(…)`, then
`const disposeChatWidthVar = autorun(() => {…})` (:89-91), then the cleanup
(:92-107) which calls `disposeChatWidthVar()`, removes the CSS property,
`endChatResize(state)`, both unregisters, `ctrl.abort()`, and
`stopChatTurn(chatPaneState)`.

`import { autorun } from "mobx"` is already at :3; `useEffect` at :1. **Both
imports this feature needs already exist.**

### Two files that deliberately need no change

- **`frontend/src/work/chatPaneController.ts`** — the shell's registered
  `openChat` already calls `pickChat` **then** `loadChatMessages`, so "a different
  chat was picked" flows through `loadChatMessages`, which is where the re-pin
  lives. The controller is untouched.
- **`frontend/src/work/workspaceLayout.ts`** — holds nothing scroll-related, and
  scroll pinning is **not persisted** by locked decision. Untouched.

## Architecture rules that constrain every decision

From `docs/architecture/frontend.md`:

- **`observer` on every component**, no exceptions.
- **State is data + pure `get` computeds, never effectful methods.** The two (or
  three) new operations are top-level `(state, …)` functions.
- **No custom `useX` hooks**, no `useCallback` / `useMemo` / `useReducer`.
  **A callback ref is a plain prop, not a hook** — `viewportRef={(el) => …}` is an
  ordinary JSX attribute and breaks none of these rules. Stated explicitly
  because this is the first DOM handle under `frontend/src/` and the coder will
  otherwise hesitate or reach for `useRef` + `useEffect`, both of which are wrong
  here.
- **`useEffect` only at page level**, forbidden in leaf components. `MessageList`
  gets **no** effect, and `WorkspaceShell` gets **no second** effect.
- **`autorun` for rare imperative side-effects on observable change** (:248) —
  this feature is the example that line was written about.

From `docs/architecture/frontend-workspace.md` → Chat pane:

- **The pane's vertical contract** (:311): the aside is fixed-height, the pane
  root fills it, the **transcript is the single growing child** (`flex: 1` **plus
  `minHeight: 0`**), the composer is non-shrinking. *"A pane change that breaks
  this chain breaks it silently — jsdom has no layout engine, so no test will
  catch it."* This feature must not touch that chain, and the fact that it did
  not is an inspection item, not a test.
- **`ChatPaneState` holds no book id** (:331) — it is book-scoped by remount
  (`key={bookId}`). Nothing here needs one.

## Why this is not a promotion candidate

Four source files, ~115 LoC, two new test files. **One logical change** — the
transcript follows the bottom. **No cross-layer coordination**: frontend only, no
API, no DTO, no route, no backend. **No ordering dependency**: the pure module,
the state operations, the `MessageList` props and the shell autorun are
independently authorable and meet only at trivial wiring. **No design ambiguity**:
the three decisions are locked above and the mechanism was fixed by the
architecture before the feature existed.

## Harness facts the test-coder needs

- `frontend/vitest.config.ts:21-23`: `environment: "jsdom"`, **`globals: false`**
  (every spec imports its own `describe` / `it` / `expect` / `vi` from
  `"vitest"`), `setupFiles: ["./tests/setup.ts"]`.
- `frontend/tests/setup.ts` stubs exactly `window.matchMedia`,
  `globalThis.ResizeObserver` and `Element.prototype.scrollIntoView`, plus
  `afterEach(cleanup + localStorage.clear)`. **There is no `scrollTo` stub, no
  `scrollTop` / `scrollHeight` / `clientHeight` stub and no rAF stub.**
- **jsdom computes no layout**: `scrollHeight` and `clientHeight` are `0` on every
  element, always. Any test asserting real pinning geometry must stub them
  **per element**:
  `Object.defineProperty(el, "scrollHeight", { value: 2000, writable: true, configurable: true })`.
  Established precedent for per-target `Object.defineProperty`:
  `ChapterBodyEditor.test.tsx:99` (`document.elementFromPoint`) and
  `composerResize.test.tsx:98` (`window.innerHeight`).
- To **count** scroll writes, define `scrollTop` with a getter/setter pair over a
  local variable rather than a plain value.
- **jsdom provides a real, timer-backed `requestAnimationFrame` /
  `cancelAnimationFrame`.** Flush a pending frame by awaiting a real timeout of at
  least two frame budgets (~32ms). **Do not reach for `vi.useFakeTimers()`** —
  jsdom drives rAF from its own timer loop and mixing the two is a known source of
  hangs. Fake timers are used in only two unrelated files
  (`ChapterPageReconcile.test.tsx`, `restoreBuffer.test.ts`), so there is no
  global interference to inherit and no idiom to copy.
- `frontend/tests/support/render.tsx` exports `renderWithProviders(ui, { route? })`;
  its `env="test"` is load-bearing (no portals, no transitions). `MessageList`
  takes the state instance as a prop, so rendering it needs **no API mock**.
- Specs mock `src/api/*` with whole-module `vi.mock` factories, **never `fetch`**.

## Existing specs — verified safe, and the one property that keeps them safe

Adding props to the existing `<ScrollArea>` with **no change to the rendered
element tree** breaks nothing:

- `ChatConversation.test.tsx` — queries by text/role/`querySelectorAll("strong")`.
- `chatStreaming.test.ts` — renders nothing; drives `ChatPaneState` directly.
- `ChatPane.test.tsx` — text/role/`getByLabelText("Model")`.
- `WorkspaceShell.test.tsx` — role/testid/`findByText` plus `getBookDetail`
  **call-count** guards at `:236`, `:245-246`, `:272`, `:279`. Those count **API
  invocations**, not effects or autoruns, and **nothing in the suite spies on
  `autorun` count or on disposer invocation**. A second `autorun` *inside the
  existing effect* is therefore safe; **a new `useEffect` would be the risk**, and
  the plan forbids one explicitly.

## Non-negotiables the coder must not "improve"

1. **No jump-to-latest affordance of any kind** — no pill, badge, button, count or
   toast. Locked decision 2.
2. **Nothing is persisted.** No `localStorage`, no URL param, no
   `workspaceLayout.ts` change.
3. **No `useEffect` in `MessageList`**, no `useRef`, no second `useEffect` in
   `WorkspaceShell`, and **no change to the shell effect's deps array**.
4. **`sendChatTurn`'s signature is frozen.**
5. **No suppression flag for the programmatic scroll's own scroll event** — see
   "The two mechanics" above.
6. **No smooth / animated scrolling** (`behavior: "smooth"`), and **no
   `scrollIntoView`** on a sentinel element. A direct `scrollTop` write on the
   viewport is the mechanism; a sentinel would add an element to the tree and
   break the "element tree unchanged" property that keeps four specs green.
7. **The rendered element tree of `MessageList` does not change** — new props
   only.
8. **`MessageList`'s `flex: 1` + `minHeight: 0`** are untouched, as is everything
   else in the pane's vertical chain.
9. **Do not touch `chatPaneController.ts` or `workspaceLayout.ts`.**
10. **Do not edit `docs/architecture/`** — intended doc changes go in `outcome.md`
    for the architect to apply.
