# fast/010.transcript-autoscroll — Intended documentation changes

Applied at finalization by the architect. Grouped by target file.

## `docs/architecture/frontend-workspace.md`

### 1. The known gap is closed

- **Section:** "#### Three known defects and one known gap" — the closing
  paragraph at :329, *"**Gap: the transcript does not auto-scroll to the newest
  message**, and it is now conspicuous …"*.
- **Change:** Remove the gap paragraph and retitle the section to **"Three known
  defects"**. Replace it with a short statement of the shipped contract, in the
  chat-pane prose: the transcript **follows the bottom while content arrives if
  the author is within ~one line of it (64px)**, **preserves the position
  silently when they are scrolled up** — with **no jump-to-latest affordance of
  any kind**, deliberately — and **always starts at the bottom** on mount,
  reload, chat switch, send and retry. Name the two decisions that are not
  self-evident: **Send and retry re-pin** (an explicit "done reading back"
  gesture) and **nothing is persisted** (which is what "always to bottom on
  reload" means).
- **Reason:** The list exists so a gap is recorded once rather than rediscovered;
  leaving a closed one in it is worse than never listing it. The *replacement* is
  needed because "why does it snap down when I send" and "why is there no
  new-message button" are the two questions this behaviour will produce, and both
  answers are decisions rather than accidents.

### 2. Chat pane — where the follow lives, and why it is not in the leaf

- **Section:** "Chat pane (feature 011, reshaped by feature `023.chat-ux-revision`)",
  near the parts table and the vertical-contract paragraph at :311.
- **Change:** Record that the follow is a **second `autorun` inside
  `WorkspaceShell`'s existing mount effect**, disposed in the existing cleanup
  beside the `--work-chat-width` disposer — *not* an effect in `MessageList`,
  which still holds none. Record that `MessageList` contributes exactly two
  things: it hands the `ScrollArea`'s **viewport** element to `ChatPaneState`
  through `viewportRef` (a **callback ref, which is a plain prop and not a hook**)
  and reports scroll position through `onScrollPositionChange`. Note that the
  `ScrollArea`'s own `ref` targets the **root, non-scrolling wrapper**, so
  `viewportRef` is the only handle on the element that scrolls.
- **Reason:** `frontend.md:248` sanctioned this mechanism in the abstract and this
  document named it as the answer at :329; now that it is built, the document
  should say where it actually is. The root-vs-viewport distinction is the single
  most likely wrong turn for the next person who touches this pane, and it costs
  one sentence to prevent.

### 3. Chat pane — the pinned flag is non-observable on purpose

- **Section:** the same chat-pane area, beside the paragraph on `ChatPaneState`
  holding no book id (:331), which is the document's existing home for
  "pane-state shape decisions and their reasoning".
- **Change:** Record that the transcript's **pinned flag, viewport element and
  pending-frame handle are non-observable slots** on `ChatPaneState` (the
  `makeAutoObservable` exclusion map, beside `fast/008`'s
  `composerResizeDispose`), for two reasons: the flag is rewritten on every scroll
  event at pointer rate, and — the load-bearing one — the follow `autorun` reads
  it, so an observable flag would make the autorun **re-enter itself on its own
  programmatic scroll**. Record alongside it that the programmatic scroll's own
  scroll event **is deliberately not suppressed**: it recomputes to pinned-true
  and terminates, and a suppression flag would also swallow a genuine user scroll
  landing in the same frame.
- **Reason:** Both are things a reader will read as omissions and "fix". The
  non-observable slot looks like a missed annotation; the unsuppressed feedback
  loop looks like a bug. Each is a decision with a failure mode behind it.

## `docs/architecture/frontend.md`

### 4. The `autorun` rule gains its worked example — and the deferral it requires

- **Section:** "React hook rules", the bullet at :248 — *"For rare imperative
  side-effects on observable change (e.g. auto-scroll while streaming), use a
  single `autorun` started in the mount `useEffect` and disposed on cleanup."*
- **Change:** Keep the rule and attach the now-built example
  (`fast/010.transcript-autoscroll`), adding the two mechanics the bare rule does
  not imply:
  - **An `autorun` fires synchronously on mutation, *before* React re-renders.**
    Any side-effect that must read post-render DOM geometry has to be **deferred
    to `requestAnimationFrame`**, or it measures the pre-update layout and lands
    short. This is the repo's **first `requestAnimationFrame` use anywhere**.
  - **Deferral implies coalescing.** A stream mutates per token; the pending frame
    handle is stored and a second schedule is skipped, so a turn costs one frame
    per paint rather than one per delta.
  - The autorun is added **inside the page's existing mount effect**, never as a
    second effect — `WorkspaceShell` now runs two.
- **Reason:** This is the first time the rule was actually exercised, and the two
  mechanics are exactly what the next person will get wrong: an autorun that reads
  `scrollHeight` inline looks correct, typechecks, and is off by the height of
  whatever just arrived.

### 5. A callback ref is a plain prop, not a hook — the repo's first DOM handle

- **Section:** "React hook rules", beside the **"No custom `useX` hooks"** bullet
  (:247) and its existing "calling a third-party library's hooks is not authoring
  one" clause.
- **Change:** Add the parallel clarification: **taking a DOM handle through a
  callback ref prop is not a hook either.** `fast/010` is the **first DOM handle
  anywhere under `frontend/src/`** (there were zero `useRef` hits before it), and
  it is taken as `viewportRef={(el) => …}` — an ordinary JSX attribute — with **no
  `useRef`, no `useCallback` and no `useEffect`**. Note the consequence the
  implementation must tolerate: an inline callback ref has a fresh identity every
  render, so React detaches with `null` and re-attaches on **every** render; the
  receiving operation must therefore **store the node and do nothing else** — no
  re-pin, no cancel — or it will fight its own re-renders.
- **Reason:** The no-hooks rules are strict enough that a coder facing "I need the
  scrolling element" will reach for the two forbidden tools (`useRef` +
  `useEffect`) or freeze. The sanctioned answer costs one line, and the
  identity-churn consequence is a real trap that will otherwise be rediscovered
  through a bug that only appears while streaming.

### 6. Testing — the pure-geometry split is now an idiom, and the jsdom scroll boundary

- **Section:** "Testing", beside the existing `@dnd-kit` / ProseMirror
  "faking the library's callbacks would test the test" reasoning.
- **Change:** Record that **three features now split their geometry into a pure,
  DOM-free module purely to make it testable** — `fast/005` (`chatWidthFromPointer`),
  `fast/008` (`clampComposerHeight` / `composerHeightFromDrag`) and `fast/010`
  (the pin threshold predicate and bottom-position helper) — so it is the house
  answer to "this behaviour depends on layout", not three one-offs. Add the
  scroll-specific boundary: **jsdom reports `scrollHeight` and `clientHeight` as
  `0` on every element**, so any scroll-position assertion runs against a stub
  installed with `Object.defineProperty` per element, and real pinning is a
  `[manual/live]` criterion. Add the rAF note: jsdom's
  `requestAnimationFrame` is **timer-backed**, so a pending frame is flushed by
  awaiting a real timeout of ~two frame budgets; **mixing `vi.useFakeTimers()`
  with it is a known hang** and is not the house idiom.
- **Reason:** The pure-split now has enough instances to be stated as a rule
  rather than inferred from three plans. The rAF flushing detail has no precedent
  anywhere in the repo, so the next feature that defers to a frame will either
  re-derive it or hang its suite on fake timers.

## Observations

- A deferred side-effect adds a **second thing to unwind at unmount**: alongside the `autorun` disposer, the pending `requestAnimationFrame` must be cancelled and the DOM handle dropped in the same cleanup, or a frame scheduled on the last mutation fires against a detached node. Possible impact: one clause on the `autorun` bullet in `frontend.md` → "React hook rules" (outcome section 4), beside "disposed on cleanup".

---
Status: Applied 2026-09-14
Applied items: 6 (one modified)
Rejected items: 0

Notes:

- Sections 1–3 landed in `docs/architecture/frontend-workspace.md` → Chat pane; the section heading became "Three known defects" and the gap paragraph was removed. Sections 4–5 landed in `docs/architecture/frontend.md` → "React hook rules", with the `## Observations` entry folded into section 4's worked example as its third mechanic (cancel the pending frame and drop the DOM handle in the same cleanup), exactly where that entry proposed it.
- **Section 6 was applied in modified form.** Its pure-geometry-idiom and jsdom-scroll-boundary parts were written as stated. Its `requestAnimationFrame` sentence was not: the claims that *"mixing `vi.useFakeTimers()` with it is a known hang"* and that a frame is flushed by *"awaiting a real timeout of ~two frame budgets"* were drafted before any test for this feature existed, and no hang and no timing figure were observed during delivery. Recording an unobserved failure and an invented figure as established fact is not something an architecture doc may do. What was written instead is only what is verified — jsdom's `requestAnimationFrame` is real and timer-backed, `fast/010` is the repo's first use of it, and because it is timer-backed `vi.useFakeTimers()` changes its behaviour, so a deferred spec should await a real frame or drive the frame explicitly. It is phrased as a hazard and a house idiom, not as a reported bug, and carries no specific timeout figure.
- `quick-reference.md` was deliberately not touched: this feature adds no endpoint, DTO, table or status code. `docs/product/` was not touched and no `**Realizes:**` header was added — the feature closes an architectural gap, not a product requirement.

