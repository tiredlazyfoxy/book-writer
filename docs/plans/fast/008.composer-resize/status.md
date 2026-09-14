# Fast feature 008 — composer-resize

| Status  | Verifier | Date |
|---------|----------|------|
| done    | PASS     | 2026-09-14 |

## Files Changed

- `frontend/src/work/workspaceLayout.ts` — composer height constants, the two pure
  geometry helpers (`clampComposerHeight` / `composerHeightFromDrag`), the read's
  minimum-only third-field fallback, and the merging partial write.
- `frontend/src/work/components/chat/chatPaneState.ts` — constructor seeding of
  `composerHeight` clamped against `window.innerHeight`, and the three external
  resize operations (`beginComposerResize` / `endComposerResize` /
  `nudgeComposerHeight`).
- `frontend/src/work/components/chat/ComposerResizeHandle.tsx` — NEW: the
  `observer` separator with the pixel value triple, the pointer-down entry to the
  drag and the ArrowUp-grows / ArrowDown-shrinks keyboard path.
- `frontend/src/work/components/chat/Composer.tsx` — `autosize` / `minRows` /
  `maxRows` removed; `styles={{ input: { height: state.composerHeight, resize:
  "none" } }}` added. Nothing else moved.
- `frontend/src/work/components/chat/ChatPane.tsx` — renders
  `<ComposerResizeHandle/>` between `<MessageList/>` and `<Composer/>`.

## Skeleton

### Frozen interface (2026-09-14)

**`frontend/src/work/workspaceLayout.ts`** (pure module — no class, no MobX, no DOM)

- `frontend/src/work/workspaceLayout.ts` — `export const MIN_COMPOSER_HEIGHT_PX = 64` — new (real value, not a stub)
- `frontend/src/work/workspaceLayout.ts` — `export const DEFAULT_COMPOSER_HEIGHT_PX = 96` — new (real value)
- `frontend/src/work/workspaceLayout.ts` — `export const MAX_COMPOSER_HEIGHT_FRACTION = 0.5` — new (real value)
- `frontend/src/work/workspaceLayout.ts` — `export const COMPOSER_HEIGHT_KEYBOARD_STEP = 24` — new (real value)
- `frontend/src/work/workspaceLayout.ts` — `export interface WorkspaceLayout { navCollapsed: boolean; chatWidth: number; composerHeight: number }` — changed (was `{ navCollapsed: boolean; chatWidth: number }`); `composerHeight` is PIXELS
- `frontend/src/work/workspaceLayout.ts` — `export function clampComposerHeight(candidate: number, viewportHeight: number): number` — new (throws)
- `frontend/src/work/workspaceLayout.ts` — `export function composerHeightFromDrag(startHeight: number, startY: number, clientY: number, viewportHeight: number): number` — new (throws)
- `frontend/src/work/workspaceLayout.ts` — `export function readWorkspaceLayout(): WorkspaceLayout` — unchanged signature; returns the third field (stub value `Number.NaN`, see below)
- `frontend/src/work/workspaceLayout.ts` — `export function writeWorkspaceLayout(patch: Partial<WorkspaceLayout>): void` — changed (was `writeWorkspaceLayout(layout: WorkspaceLayout): void`). This is the feature's one signature widening; unchanged existing exports: `WORKSPACE_LAYOUT_KEY`, `CHAT_WIDTH_CSS_VAR`, `DEFAULT_CHAT_WIDTH_FRACTION`, `MIN_CHAT_WIDTH_FRACTION`, `MAX_CHAT_WIDTH_FRACTION`, `CHAT_WIDTH_KEYBOARD_STEP`, `clampChatWidth`, `chatWidthFromPointer`, `chatWidthCss`.

**`frontend/src/work/components/chat/chatPaneState.ts`**

- `frontend/src/work/components/chat/chatPaneState.ts` — `new ChatPaneState()` — **unchanged, recorded for the test-coder**: the constructor takes **no arguments**. It hydrates in the constructor, so storage must be seeded *before* construction.
- `frontend/src/work/components/chat/chatPaneState.ts` — `ChatPaneState.composerHeight: number` — new observable field (pixels)
- `frontend/src/work/components/chat/chatPaneState.ts` — `ChatPaneState.composerResizing: boolean` — new observable field (initial `false`)
- `frontend/src/work/components/chat/chatPaneState.ts` — `ChatPaneState.composerResizeDispose: (() => void) | null` — new **non-observable** slot (initial `null`); added to the `makeAutoObservable` exclusion map beside the untouched `start` / `stop` / `setActive`
- `frontend/src/work/components/chat/chatPaneState.ts` — `export function beginComposerResize(state: ChatPaneState, clientY: number): void` — new (throws)
- `frontend/src/work/components/chat/chatPaneState.ts` — `export function endComposerResize(state: ChatPaneState): void` — new (throws)
- `frontend/src/work/components/chat/chatPaneState.ts` — `export function nudgeComposerHeight(state: ChatPaneState, delta: number): void` — new (throws)

**`frontend/src/work/components/chat/ComposerResizeHandle.tsx`** (NEW file)

- `frontend/src/work/components/chat/ComposerResizeHandle.tsx` — `export interface ComposerResizeHandleProps { state: ChatPaneState }` — new
- `frontend/src/work/components/chat/ComposerResizeHandle.tsx` — `export const ComposerResizeHandle: (props: ComposerResizeHandleProps) => ReactElement` (an `observer` component; usage `<ComposerResizeHandle state={state} />`) — new (render body throws)

**Unchanged interfaces (no signature work needed — left entirely to the coder)**

- `frontend/src/work/components/chat/Composer.tsx` — `ComposerProps { state; onSend; onStop; onRetry }` unchanged. The plan's edit (`autosize`/`minRows`/`maxRows` off, `styles={{ input: { height: state.composerHeight, resize: "none" } }}` on) is behaviour, not interface — **not touched by the skeleton**.
- `frontend/src/work/components/chat/ChatPane.tsx` — props unchanged; rendering `<ComposerResizeHandle/>` between `<MessageList/>` and `<Composer/>` is wiring, not interface — **not touched by the skeleton**, so the existing chat-pane specs keep rendering a working pane through the red gate.

**Stub-value conventions the coder must replace (and the test-coder must not rely on)**

- `readWorkspaceLayout()` returns `composerHeight: Number.NaN`. It is deliberately **total and non-throwing** (its live caller `workspaceShellState.ts` runs on every workspace mount); `NaN` is the unimplemented marker because no expected height can be accidentally satisfied by it. The coder replaces it with `DEFAULT_COMPOSER_HEIGHT_PX` plus the per-field `typeof === "number"` read clamped to `MIN_COMPOSER_HEIGHT_PX` only.
- `ChatPaneState.composerHeight` is initialised to `Number.NaN` for the same reason — the constructor must not throw (every chat spec builds one). The coder replaces it with the constructor seeding `clampComposerHeight(readWorkspaceLayout().composerHeight, window.innerHeight)`.
- `writeWorkspaceLayout` keeps its pre-feature body (`setItem(KEY, JSON.stringify(patch))`, errors swallowed) so its three existing full-record call sites keep working. **The merge over `readWorkspaceLayout()` is unimplemented.**

**Caller-compile edits (out of Source-files scope): None.** `frontend/src/work/components/shell/workspaceShellState.ts` was **not** touched: its three `writeWorkspaceLayout({ navCollapsed, chatWidth })` call sites (`:148`, `:220`, `:231`) satisfy `Partial<WorkspaceLayout>` unchanged, as the plan intended.

**Compile gate:** `cd frontend && npx tsc --noEmit` clean; `cd frontend && npm run test:types` also clean (the existing `tests/work/workspaceLayout.test.ts` still typechecks against the widened writer).

## Tests

### Tests (2026-09-14)

- `frontend/tests/work/workspaceLayout.test.ts` — covers DoD-1, DoD-2, DoD-3,
  DoD-4, DoD-5, DoD-6 — the composer constants (64 / 96 / 0.5 / 24, one unchanged
  key), the delta-based directional drag geometry and its clamps, the
  minimum-wins / unknown-ceiling clamp rules, the merging partial write under one
  key, and the read's per-field fallback with the maximum applied at use, not at
  read.
  - **Extended, not rewritten.** The file's pre-existing cases belong to
    **fast/005** and keep their own `DoD-1 … DoD-7` names; the fast/008 cases are
    the ones naming the *composer* (added below a banner comment). Nothing the 005
    cases assert about `navCollapsed` / `chatWidth` was weakened — five of them
    gained the third field in their total-record `toEqual`s, and the 005 garbage
    case gained a garbage `composerHeight`. The "exactly one storage key" case is
    unchanged and still holds under a partial write. The two id generations are
    documented in the file header.
- `frontend/tests/work/composerResize.test.tsx` — **new** — covers DoD-7, DoD-8,
  DoD-9, DoD-10, DoD-11 — constructor seeding clamped against a pinned
  `window.innerHeight` of `800`, the handle's `separator` / "Resize composer" /
  pixel value triple, ArrowUp-grows / ArrowDown-shrinks by `24` with both bounds,
  per-nudge persistence that leaves a seeded `navCollapsed` + `chatWidth` intact,
  and the fixed-height non-autosizing `<textarea>` alongside the surviving 023
  Send/Stop and Ctrl/Cmd+Enter contract.
  - **Repair pass (2026-09-14), TEST fault.** DoD-6's non-finite plant now uses
    `null` and `1e999` (both JSON-legal; `1e999` parses to `Infinity`) instead of
    bare `NaN` / `Infinity` tokens, which are not JSON and therefore fall under
    fast/005's frozen unparseable-entry-defaults-everything contract rather than
    DoD-6's per-field one. In `composerResize.test.tsx` every DoD-11 case now primes
    turn status and prompt text **before** the render instead of mutating the
    observable afterwards: Send and Stop became two separate primed renders, the
    long-prompt case types its forty lines before mounting so "does not autosize"
    can actually fail, and the post-mount height-mutation case was dropped — it was
    not a DoD-11 clause, and DoD-9 already demonstrates the reactive path.
  - No API call is exercised; `src/api/chats` is mocked module-factory form only so
    no import reaches the network. No `ChatPane` mount, no pointer drag.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓,
  DoD-8 ✓, DoD-9 ✓, DoD-10 ✓, DoD-11 ✓, DoD-12 [manual/live, no test],
  DoD-13 [manual/live, no test], DoD-14 [manual/live, no test],
  DoD-15 [manual/live, no test], DoD-16 [manual/live, no test]
- Deliberately not automated, per the plan's list: the pointer drag (DoD-13), the
  flex chain (DoD-12), breakpoint behaviour (DoD-15), `resize: "none"` and internal
  scrolling (DoD-14), and mounting `ChatPane` to prove the handle's position
  (DoD-12).

## Notes & Issues

- `Composer.tsx`'s prose doc comments still describe the input as autosizing
  ("as the input autosizes 2→6 rows", "as the textarea grows from 2 rows to 6").
  Left verbatim because the plan says nothing else in that file moves; worth a
  comment-only follow-up.
- `frontend/src/work/components/shell/workspaceShellState.ts` was **not** touched,
  as the plan required — its three full-record call sites satisfy the widened
  `Partial<WorkspaceLayout>` writer unchanged.

## Bug Fixes

- **2026-09-14 — the handle was unhittable.** Reported live: "there is the draggable
  ruler but resize doesn't work." Diagnosis: the drag machinery is sound —
  `beginComposerResize` + a dispatched `pointermove` moves 96 → 196 exactly as
  DoD-2 specifies, the window listeners fire, and a height change re-renders the
  textarea's inline height; no Mantine rule overrides it. The defect was the
  target: a bare, fully transparent 6px strip floating inside the pane `Stack`'s
  `gap="sm"`, so ~30px of blank space sat between transcript and composer with only
  a 6px band live and nothing marking where it was.
  Fix, in `ComposerResizeHandle.tsx` only: the strip is now 12px with
  `marginBlock: -3` (reclaiming the gap, so the layout footprint stays 6px and the
  flex chain is untouched) and carries a visible 2px rule in
  `--mantine-color-default-border`, `pointerEvents: "none"` so it cannot swallow the
  pointer-down. No change to the geometry, the state, the persistence or any frozen
  signature. `npm test` 777/777, `npm run build` and `npx tsc --noEmit` clean.
