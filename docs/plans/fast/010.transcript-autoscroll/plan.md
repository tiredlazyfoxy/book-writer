# fast/010.transcript-autoscroll — The chat transcript follows the newest message

## Goal

Make the chat pane's transcript **follow the bottom while an answer streams in,
if the author was already at the bottom**; **preserve the scroll position
silently if they were scrolled up**; and **always start at the bottom** on mount,
reload, chat switch and send. Closes the known gap recorded at
`frontend-workspace.md:329`.

## Source files

This list **is** the coder's scope; nothing else is touched.

- `frontend/src/work/components/chat/transcriptScroll.ts` — **NEW.** The pure,
  DOM-free, MobX-free scroll geometry: the 64px threshold constant, the
  "is it pinned" predicate, and the "what scrollTop is the bottom" helper.
- `frontend/src/work/components/chat/chatPaneState.ts` — **modify.** Two or three
  non-observable slots, one pure `get` computed, and the external scroll
  operations; plus the two re-pin call sites inside `loadChatMessages` and
  `sendChatTurn` (and `retryChatTurn`).
- `frontend/src/work/components/chat/MessageList.tsx` — **modify.** Two props on
  the existing `<ScrollArea>`, and a docblock correction. **No change to the
  rendered element tree.**
- `frontend/src/work/components/shell/WorkspaceShell.tsx` — **modify.** A second
  `autorun` **inside the existing mount effect**, and its disposer beside
  `disposeChatWidthVar()` in the existing cleanup.

**Explicitly not in scope, and it matters:**
`frontend/src/work/chatPaneController.ts` must **not** be touched — the shell's
registered `openChat` already calls `loadChatMessages`, which is where the re-pin
lives. Neither is `frontend/src/work/workspaceLayout.ts` — nothing here is
persisted, by locked decision. Neither is anything else under `components/shell/`
beyond the single autorun above.

## Test files

Disjoint from Source files. This list **is** the test-coder's scope.

- `frontend/tests/work/transcriptScroll.test.ts` — **NEW.** Covers DoD-1 … DoD-4
  (the pure module). No DOM, no rendering, no mocks.
- `frontend/tests/work/transcriptAutoscroll.test.tsx` — **NEW.** Covers
  DoD-5 … DoD-13 (the state operations against a stubbed element, the growth
  signature, and the `MessageList` wiring).

Every other spec under `frontend/tests/` must keep passing **unmodified** — see
DoD-17. Four of them were verified against this design and are listed there by
name.

## Interface intent

Prose only, per `docs/plans/CLAUDE.md`. `fast-skeleton` derives and freezes the
exact signatures. **Where a literal value appears below it *is* the contract** —
the skeleton must not round it, rename it, or move it.

> **Instructions to `fast-skeleton`:**
>
> 1. Record `ChatPaneState`'s **constructor signature** in `## Skeleton` even
>    though this feature does not change it. The test-coder must construct one and
>    may not read source.
> 2. Record the **exact signature of `loadChatMessages`** and — because DoD-12
>    drives it — the **`api/chats` functions it calls, with their signatures and
>    return DTO names**, so the test-coder can write a whole-module `vi.mock`
>    factory blind. Without that the air gap makes DoD-12 unwritable.
> 3. Record the type of the new non-observable slots, including the element type
>    of the transcript viewport, since a test must be able to declare a stub of
>    the same type.

### `frontend/src/work/components/chat/transcriptScroll.ts` — NEW

A **pure module**: no class, no MobX, no DOM access, no imports from the state.
Every value it needs arrives as a plain number. It is pure for exactly the reason
`fast/008` extracted its drag geometry and `fast/005` its width geometry — it is
the only way to verify the 64px contract with no layout engine.

It is sited beside its only consumer in `components/chat/` rather than in the
`src/work/` module tier, because it is chat-pane geometry with no persistence and
no cross-page reach; `workspaceLayout.ts` is the tier for device-local persisted
layout, and this feature persists nothing.

New exported constant:

- **`TRANSCRIPT_PIN_THRESHOLD_PX`** = `64` — the distance from the bottom, in CSS
  pixels, within which the transcript counts as "at the bottom". The
  user-locked value; roughly one line of prose of slack. See `context.md` for why
  neither exact-bottom nor ~200px was chosen.

New exported functions:

- **A pinned predicate** — takes `scrollTop`, `scrollHeight` and `clientHeight`,
  all plain numbers, and returns a boolean. It computes the distance from the
  bottom (`scrollHeight − clientHeight − scrollTop`) and answers **true when that
  distance is less than or equal to `TRANSCRIPT_PIN_THRESHOLD_PX`**. The boundary
  is **inclusive**: a distance of exactly `64` is pinned.
  - **Degenerate input resolves to pinned, never to unpinned.** If any of the
    three numbers is not finite (`NaN`, `±Infinity`), the answer is `true`.
    Reason, and it is a deliberate safety direction rather than defensiveness: an
    unreadable measurement must not silently strand the author away from a reply
    that is streaming in. The failure mode of a wrong `true` is one unwanted
    scroll to the bottom; the failure mode of a wrong `false` is a feature that
    appears not to work at all. It also means **jsdom's all-zero geometry reads as
    pinned**, which is the correct default for a fresh pane.
  - A viewport with nothing to scroll (`scrollHeight ≤ clientHeight`) yields a
    non-positive distance and is therefore pinned, with no special case.
- **A bottom-position helper** — takes `scrollHeight` and `clientHeight` and
  returns the `scrollTop` value that puts the viewport at its bottom:
  `scrollHeight − clientHeight`, **floored at `0`**. A non-finite input yields
  `0`. Returning `0` for unreadable geometry is safe because it coincides with the
  case where there is nothing to scroll; assigning a non-finite value to
  `scrollTop` would be meaningless.

### `frontend/src/work/components/chat/chatPaneState.ts` — modify

The file's header rule holds: **observable data and pure `get` computeds only, no
effectful methods.** Everything effectful below is a top-level function beside
`loadChatPane` / `sendChatTurn` / `stopChatTurn`.

`ChatPaneState` keeps every existing field untouched and gains **non-observable
slots only**, added to the existing `makeAutoObservable` exclusion map beside
`composerResizeDispose`; the `start`, `stop` and `setActive` entries stay exactly
as they are:

- **the transcript viewport element** — the scrolling `HTMLDivElement` handed over
  by `MessageList`'s callback ref, or `null` when nothing is attached. Initialized
  to `null`.
- **the pinned flag** — a boolean, **initialized `true`**, so a fresh pane follows
  from its very first render with no scroll event needed.
- **the pending follow frame handle** — the `requestAnimationFrame` id currently
  scheduled, or nothing. Used to coalesce.

**All of these must be non-observable**, and the reason is load-bearing rather
than stylistic: the pinned flag is rewritten on every scroll event at pointer
rate, and the follow `autorun` reads it — an observable flag would both fire the
pane's observers continuously and make the autorun **re-enter itself on its own
programmatic scroll**. See `context.md` → "Why both new state slots are
non-observable".

One new pure `get` computed:

- **A transcript growth signature** — a value that changes whenever the transcript
  grows, derived from the four observables that can grow it: the length of
  `messages`, of `streamingContent`, of `streamingThinking`, and of
  `streamingToolTrace`.
  - It must be **a string joining the four counts with a separator**, **not their
    sum**. A sum can cancel: `finishTurn` appends one persisted message *and*
    clears `streamingContent` in the same action, so two changes can net to the
    same number, the computed's value would not change, and **MobX would not
    re-run the autorun that depends on it** — the transcript would fail to follow
    at exactly the moment the final answer lands. This is the whole reason the
    computed exists rather than four bare reads.
  - It reads `messages.length`, **not `renderedMessages.length`** —
    `renderedMessages` is a presentation derivation whose shape can change without
    the transcript growing, and rebuilding that array from a non-rendering context
    is wasted work.

Five new external functions:

- **An attach operation** — takes the state and an element or `null`, and stores
  it in the viewport slot. That is **all** it does.
  - It must **not** re-pin, and must **not** cancel the pending frame. Reason: an
    inline callback ref has a new function identity on every render, so React
    detaches with `null` and re-attaches the same node **on every single render of
    `MessageList` — which is once per streaming delta**. A re-pin there would yank
    a scrolled-up author back down mid-stream; a cancel there would kill the very
    frame that is about to follow.
  - It must therefore be **tolerant of repeated `null`-then-node churn**. It is
    correct under churn by construction, because detach and re-attach happen
    synchronously inside one React commit and a pending frame reads the viewport
    slot only when it fires, which is after that commit.
- **A note-scroll operation** — takes the state, reads the live element's
  `scrollTop` / `scrollHeight` / `clientHeight`, and assigns the pinned predicate's
  answer to the pinned flag. A no-op when no viewport is attached (it leaves the
  flag alone rather than guessing). This is what `onScrollPositionChange` calls; it
  deliberately **ignores the `{x, y}` argument** and measures the element, because
  the predicate needs all three numbers and the element is the truth.
- **A synchronous scroll-to-bottom operation** — takes the state; if a viewport is
  attached **and** the pinned flag is set, it writes the bottom-position helper's
  result to the viewport's `scrollTop`. Otherwise it does nothing. This is the
  single place the contract is enforced, and it is synchronous **so that the
  geometry wiring is testable with no timing at all**.
- **A follow operation** — takes the state; this is what the shell's `autorun`
  calls.
  - Returns immediately when the pinned flag is clear — a scrolled-up author
    schedules nothing at all, which *is* "the position is preserved".
  - Returns immediately when a frame is already pending — **this is the
    coalescing**, and without it a fast token stream queues one frame per delta.
  - Otherwise schedules a `requestAnimationFrame`; the frame clears the stored
    handle and then calls the synchronous operation above, which **re-checks**
    pinned and the viewport (the author may have scrolled during the frame).
  - **The deferral is mandatory, not stylistic.** A MobX `autorun` fires
    synchronously on mutation, *before* React re-renders, so measuring
    `scrollHeight` at that instant yields the pre-update height and the scroll
    lands short of the new bottom by exactly the height of what just arrived.
- **A release operation** — takes the state; cancels any pending frame and clears
  the viewport slot. Called from `WorkspaceShell`'s existing cleanup.

**The programmatic scroll's own scroll event is left alone, deliberately.**
Writing `scrollTop` fires `onScrollPositionChange`, which re-runs the note-scroll
operation. Because the write lands at the bottom, that recomputes to
**pinned = true** and the loop terminates on its first iteration. Do **not** add a
suppression flag — it would also swallow a genuine user scroll landing in the same
frame, which is the one event that must never be missed.

Three re-pin call sites, all of which force the pinned flag **true** and then
schedule a follow (a single shared force-and-follow helper is the natural shape;
the skeleton decides whether that is one exported function or the pin flag plus
the follow operation):

- **`loadChatMessages`**, on the success path, right after the transcript is
  replaced. This one site covers **mount, reload and chat switch**, including the
  `chatPaneController.openChat` path — which is why `chatPaneController.ts` needs
  no change, and why this is what satisfies *"on reload — always to bottom"*.
- **`sendChatTurn`**, at the point the send is **accepted** (after validation and
  the settings flush, when the turn actually begins). Locked decision 1 — Send is
  an explicit "done reading back" gesture. **The signature does not change**: the
  file's own `023 EXTENDS THE CONTRACT, SIGNATURE UNCHANGED` comment (:1185) still
  binds.
- **`retryChatTurn`**, at the equivalent point. **This is a deliberate call, not an
  oversight**: retry is the same "I just asked for output" gesture as send, it is
  reached from the same composer, and an author who retries expects to watch the
  new attempt exactly as they would a first one. Treating it differently would be
  an inconsistency nobody could explain.

If the shell's autorun also fires for the same mutation, the coalescing makes the
two schedules **one frame**, so the explicit call costs nothing and keeps the
state operation correct even when no shell is mounted.

### `frontend/src/work/components/chat/MessageList.tsx` — modify

Two props on the **existing** `<ScrollArea>` (:51-64) and one docblock fix.
Nothing else in the file moves.

- **`viewportRef`** — a **callback ref** handing the node to the attach operation.
  `ScrollArea.d.ts:25` types it `React.ForwardedRef<HTMLDivElement>`, which accepts
  a callback. **This prop, and not the component's own `ref`, is the only handle on
  the scrolling element** — the component's `ref` targets the root, non-scrolling
  wrapper, and using it is the single most likely wrong turn in this feature.
  - **A callback ref is a plain prop, not a hook.** It breaks none of
    `frontend.md`'s React rules: no `useRef`, no `useCallback` (which is forbidden
    anyway), no `useEffect`, no custom `useX`. Stated because this is the first DOM
    handle anywhere under `frontend/src/`.
- **`onScrollPositionChange`** — calls the note-scroll operation. The `{x, y}`
  argument is ignored on purpose (see Interface intent above).

**The rendered element tree does not change** — props only, no wrapper, no
sentinel element, no `id`, no `data-*`. That property is what keeps four existing
specs green (DoD-17), so it is a contract, not an incidental.

The docblock at **:39-43** currently states that the auto-scroll side-effect
"belongs, **if shipped**, in a single pane-level mount `autorun`". Correct it: the
side-effect **is** shipped by `fast/010`, it lives in `WorkspaceShell`'s existing
mount `autorun`, and this leaf still holds **no `useEffect`** — it only hands its
viewport element to the pane state and reports scroll position. The leaf rule is
unchanged; only the "if" is stale.

### `frontend/src/work/components/shell/WorkspaceShell.tsx` — modify

**A second `autorun` inside the existing mount `useEffect`** (:60-108), placed
beside the `--work-chat-width` autorun at :89-91. It reads the pane state's
transcript growth signature and calls the follow operation.

Its disposer goes in the **existing cleanup** (:92-107), beside
`disposeChatWidthVar()`, together with a call to the release operation.

**Forbidden here, explicitly:**

- **No new `useEffect`** and **no change to the deps array** (`[state,
  chatPaneState]`). `WorkspaceShell.test.tsx`'s `getBookDetail` call-count guards
  (`:236`, `:245-246`, `:272`, `:279`) count API invocations, not effects, so a
  second autorun *inside the existing effect* is safe while a second effect is
  exactly the thing that would re-run those loads.
- No change to the ordering or content of anything else in the effect or cleanup.

`import { autorun } from "mobx"` (:3) and `useEffect` (:1) already exist; this
feature adds no import from `mobx` or `react`.

## Definition of done

`[test]` items are the coverage contract: the test-coder must cover each with a
test citing its id. `[manual/live]` items carry no automated test and the verifier
records them as requires-live-run.

### The pure module — `frontend/tests/work/transcriptScroll.test.ts`

1. **DoD-1** `[test]` `TRANSCRIPT_PIN_THRESHOLD_PX` is exactly `64`.
2. **DoD-2** `[test]` The pinned predicate answers on both sides of the threshold,
   with an **inclusive** boundary. With `clientHeight` `500` and `scrollHeight`
   `2000` (so the bottom is `scrollTop` `1500`): `1500` → pinned; `1436`
   (distance exactly `64`) → pinned; `1435` (distance `65`) → **not** pinned;
   `0` → **not** pinned.
3. **DoD-3** `[test]` Degenerate input resolves to **pinned**, never to unpinned:
   a `NaN` or `Infinity` in **any** of the three arguments → pinned; all three
   zero (jsdom's real geometry) → pinned; `scrollHeight` below `clientHeight` →
   pinned.
4. **DoD-4** `[test]` The bottom-position helper: `(2000, 500)` → `1500`;
   `clientHeight` greater than or equal to `scrollHeight` → `0` (never negative);
   a non-finite argument → `0`.

### The state operations — `frontend/tests/work/transcriptAutoscroll.test.tsx`

These use a **hand-made stub element** (`document.createElement("div")` with
`scrollHeight` / `clientHeight` defined via `Object.defineProperty`, and
`scrollTop` defined as a getter/setter pair over a local so writes can be
counted). jsdom computes no layout, so this is the only way — see `context.md` →
"Harness facts".

5. **DoD-5** `[test]` Attach and release. With no viewport attached, the
   synchronous scroll operation is a no-op and **does not throw**. After attaching
   a stub element it writes to that element. After the release operation it no
   longer writes to it.
6. **DoD-6** `[test]` A **freshly constructed** `ChatPaneState` is pinned by
   default: attach a stub (`scrollHeight` `2000`, `clientHeight` `500`,
   `scrollTop` `0`) and call the synchronous scroll operation with **no prior
   scroll notification at all** — `scrollTop` becomes `1500`.
7. **DoD-7** `[test]` The note-scroll operation unpins and re-pins from live
   geometry. With the same stub: set `scrollTop` to `0`, note the scroll, then
   call the synchronous scroll operation — **zero writes occur and `scrollTop`
   stays `0`** (the position is preserved). Then set `scrollTop` to `1500`, note
   the scroll again, and the synchronous operation writes `1500`.
8. **DoD-8** `[test]` The force-re-pin path overrides an unpinned viewport: after
   scrolling to `0` and noting it (state now unpinned), the re-pin operation
   followed by a frame flush leaves `scrollTop` at `1500`.
9. **DoD-9** `[test]` The follow operation is **deferred and coalesced**: it
   performs **no write synchronously**, and after N rapid calls (N ≥ 3) followed by
   a single frame flush, **exactly one** write to `scrollTop` has occurred.
10. **DoD-10** `[test]` The follow operation performs **no write at all**, even
    after a frame flush, while the state is unpinned.
11. **DoD-11** `[test]` The transcript growth signature changes for **each** of the
    four growth sources independently (appending to `messages`, to
    `streamingContent`, to `streamingThinking`, to `streamingToolTrace`), and — the
    case the string shape exists for — it **also changes when one message is
    appended while `streamingContent` is cleared in the same mutation**, which a
    sum would not.
12. **DoD-12** `[test]` `loadChatMessages` re-pins: with `api/chats` mocked, an
    attached stub scrolled to `0` and noted (state unpinned), a completed
    `loadChatMessages` followed by a frame flush leaves `scrollTop` at the bottom.
    This is the automated half of *"on reload — always to bottom"*, and it also
    covers the chat-switch and `chatPaneController.openChat` paths, which both run
    through this function.
13. **DoD-13** `[test]` `MessageList` hands its **scrolling viewport** to the
    state: rendering it with a `ChatPaneState` leaves a non-null viewport element
    attached, and unmounting leaves none. (The node handed over must be the
    `ScrollArea`'s viewport, not its root wrapper — assert on the attached
    element's relationship to the rendered tree, not merely on non-nullness, if
    that can be done without depending on Mantine's internal class names.)

### Live-only

14. **DoD-14** `[manual/live]` **Send and retry snap to bottom.** Scroll the
    transcript up, send a message: the view snaps to the bottom, the author's own
    message lands in view, and the reply streams in below it. The same for the
    retry banner's retry.
    *Not automated by design*: mocking the whole send path (settings flush +
    `streamPost` + the terminal `getChat` reload) to observe one boolean write
    would rebuild `chatStreaming.test.ts`'s harness for no confidence this feature
    does not already have — the operation those two call sites invoke is covered
    by DoD-8.
15. **DoD-15** `[manual/live]` **The live behaviour, end to end, in a browser.**
    (a) Sitting at the bottom, a streaming answer keeps the newest text in view
    continuously, with no visible stutter and no scroll-jank from per-token
    frames. (b) Scrolled up, a reply arriving below the fold **does not move the
    view at all**, and **nothing is rendered to announce it** — no pill, badge,
    button or count (locked decision 2). (c) Scrolling back to within ~one line of
    the bottom re-engages the follow. (d) Reloading the page lands at the bottom.
    (e) Switching chats from the chats list lands at the bottom of the new one.
16. **DoD-16** `[manual/live]` **Structural inspection of the diff.** No new
    `useEffect` anywhere; no `useRef`; `MessageList` still holds no effect; the
    shell's mount effect deps array is unchanged; the new autorun sits **inside**
    the existing effect and its disposer **inside** the existing cleanup beside
    `disposeChatWidthVar()`; no suppression flag for the programmatic scroll
    event; no `behavior: "smooth"` and no `scrollIntoView`; nothing is persisted
    anywhere (no `localStorage`, no URL param, no `workspaceLayout.ts` change);
    `sendChatTurn`'s signature is unchanged; `MessageList`'s `flex: 1` +
    `minHeight: 0` and the rest of the pane's vertical chain are untouched.
17. **DoD-17** `[manual/live]` `cd frontend && npm run build` clean,
    `cd frontend && npm test` green, `cd frontend && npm run test:types` clean —
    and every spec under `frontend/tests/` **other than the two in the Test files
    list** passes **unmodified**, specifically including `ChatConversation.test.tsx`,
    `chatStreaming.test.ts`, `ChatPane.test.tsx` and `WorkspaceShell.test.tsx`.
    This is the observable consequence of `MessageList`'s rendered element tree
    being unchanged and of the shell gaining no second effect.

### Deliberately not automated — the verifier gates this list in both directions

The test-coder must **not** write these, and the verifier must not ask for them:

- **Real pinning during a live stream, and the flex chain.** jsdom has no layout
  engine: `scrollHeight` and `clientHeight` are `0` on every element, so nothing
  scrolls and no pin distance is real. Every geometric assertion in DoD-5 … DoD-12
  runs against a **stubbed** element by necessity. `frontend-workspace.md:311`
  already states that a break in the pane's flex chain is silent under test. →
  DoD-15, DoD-16.
- **A genuine user scroll arriving through `onScrollPositionChange`.** Mantine owns
  that listener; firing a jsdom `scroll` event to prove Mantine calls our handler
  would test Mantine, and the handler itself is covered by DoD-7. → DoD-15.
- **The full send / retry path.** → DoD-14, with its reasoning above.
- **The absence of a jump-to-latest affordance.** Asserting that an unnamed element
  is absent is an assertion about nothing; it is an inspection item. → DoD-15,
  DoD-16.
- **Scroll smoothness and per-token frame cost.** Frame timing is not observable in
  jsdom; the coalescing *contract* is covered by DoD-9. → DoD-15.

## Out of scope

1. **A jump-to-latest button, pill, badge, unread count or any other new-message
   indicator.** Locked decision 2 — when scrolled up, **nothing** is rendered.
2. **Persisting the scroll position** anywhere — `localStorage`, URL param,
   server. *"On reload always to bottom"* is the absence of persistence, and
   `workspaceLayout.ts` is therefore untouched.
3. **Scroll anchoring on *prepend*.** There is no history pagination; the
   transcript only grows at the bottom.
4. **Smooth or animated scrolling**, and `scrollIntoView` on a sentinel element —
   the latter would add an element to the tree and break DoD-17's property.
5. **The horizontal axis.** `onScrollPositionChange`'s `x` is ignored.
6. **The three known defects at `frontend-workspace.md:320-327`** (the unresolvable
   model option, the archived-chat empty pane, the missing temperature validation
   message). This feature closes the *gap*, not the defects.
7. **`chatPaneController.ts`** — the re-pin lives in `loadChatMessages`, which it
   already calls.
8. **`workspaceLayout.ts`** — nothing is persisted.
9. **Anything under `components/shell/` other than the single autorun and disposer
   added to `WorkspaceShell.tsx`'s existing effect**; and every file under
   `components/chat/` not named in Source files.
10. **Any backend change, any `src/api/` or `src/types/` change, any route change,
    any new dependency.**
11. **Editing `docs/architecture/`** — intended doc changes are recorded in
    `outcome.md` for the architect to apply.
12. **Editing `docs/plans/roadmap.md`** — this feature was not roadmapped;
    recording it there is `/roadmap`'s.
