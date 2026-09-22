# Outcome — fast feature 008 composer-resize

Intended documentation changes once this feature ships, for the architect to apply
at finalization. Grouped by target file. The coder appends `## Observations` at the
bottom when implementation lands.

**No new top-level document is proposed.** Every follow-up lands in an existing
file, and none pushes its file past the folder's ~400-line rule.

## `docs/architecture/frontend-workspace.md`

This file is the primary target, and it is currently **wrong in two places** about
the chat pane — one stale from `fast/005`, one that this feature makes stale.

- **The "Out of scope" list, first bullet (line 359)** — currently reads *"Pane
  orientation, resize/divider behaviour and ratio persistence. Product routes these
  to `/architect` but this pass does not settle them; they are layout mechanics
  with no dependency on anything above."*
  **Change:** narrow the bullet to **pane orientation only**. Resize/divider
  behaviour and ratio persistence are settled and shipped — **twice now**: the chat
  pane's **width** by `fast/005.workspace-layout` and the composer's **height** by
  this feature.
  **Reason:** `fast/005.outcome.md` already asked for this narrowing and it was
  never applied, so the bullet is now two features stale. It reads as a live
  instruction to the next planner that this ground is unclaimed, which is exactly
  how a third, differently-shaped resize mechanism gets built.

- **The "Chat pane" section — add a short "Resizing" subsection** recording that
  the pane now has **two splitters, on two axes, with two different mechanisms**,
  and why they differ:
  - **Width** (`fast/005`) — a fraction of viewport width, `0.35` default, clamped
    to `[0.15, 0.60]`, driven at drag time through a **CSS custom property** set by
    an `autorun`, with `WorkspaceShell` deliberately never observing the live
    fraction.
  - **Height of the composer** (this feature) — a **pixel** height, `96` default,
    clamped to `[64px, 0.5 × viewport height]`, held as a **plain observable on
    `ChatPaneState`** and read directly by `Composer` and the handle. **No CSS
    variable and no `autorun`.**
  - **Why the mechanisms differ, stated plainly**, because copying the wrong one is
    the obvious mistake: `005`'s indirection existed solely to keep the heavy
    `AppShell` from re-rendering per `pointermove`. `Composer` already re-renders
    per keystroke on `state.pendingPrompt`, so a per-move re-render of that subtree
    costs the same as typing, and the indirection would buy nothing while putting a
    second shape in one pane.
  - **Why the two bounds are expressed in different units** — a width fraction
    survives a monitor change with no resize listener; a composer height is
    meaningful in *text lines*, so its floor is a pixel value (`64` ≈ two lines) and
    only its ceiling is viewport-relative.
  **Reason:** two splitters with two mechanisms in one pane is exactly the kind of
  thing a later reader assumes is an inconsistency to "clean up".

- **The paragraph on the pane's vertical contract (line 311)** — currently states
  the aside is fixed-height, the transcript is the single growing child (`flex: 1`
  plus `minHeight: 0`), and the composer is non-shrinking.
  **Change:** add one clause: the composer's height is now **author-chosen**, and
  the `0.5 × viewport height` ceiling is precisely what keeps this contract
  satisfiable — the transcript shrinks, and cannot be squeezed out. Keep the
  existing warning that a break in the chain is silent under test; this feature
  relied on it and left the chain a `[manual/live]` criterion for the same reason.
  **Reason:** the contract is the load-bearing invariant this feature pushes
  against, and the next person to change the composer needs the ceiling's purpose
  stated where the contract is, not in a plan file.

- **The composer's description in the chat-pane parts table (line 296) and the
  `rightSection` note (line 313).**
  **Change:** the composer is **no longer autosizing** — `autosize` / `minRows` /
  `maxRows` are gone and the inner input carries an explicit height plus
  `resize: "none"`. Note that `rightSectionWidth` and
  `rightSectionPointerEvents="all"` were **kept**, and that the Send / Stop
  accessible-name contract is untouched.
  **Reason:** `frontend.md`'s `rightSection` recipe (fact 3) justifies the explicit
  width by *"the default section width derives from the input-height variable,
  which an autosizing `Textarea` has no fixed value for"*. That premise is now
  false, which makes the width look removable — and removing it would
  non-obviously change the input's text padding. Record that it stays and why.

## `docs/architecture/frontend-work-drafts.md`

- **The module-tier section, `workspaceLayout.ts`'s row and sanction** (added by
  `fast/005`'s outcome).
  **Change:** record that the record now carries a **third field**,
  `composerHeight`, and — the part worth documenting — that the key now has **two
  independent writers in two different state classes**: `WorkspaceShellState` owns
  `navCollapsed` + `chatWidth`, `ChatPaneState` owns `composerHeight`, and neither
  holds the other's fields. The writer therefore takes a **partial patch and merges
  it over the read record**, which is what makes clobbering impossible without
  either owner knowing about the other.
  **Reason:** "one key, several owners" is the interesting property of this tier's
  newest member and the thing a seventh member will have to obey. A writer that
  takes a whole record would force every future owner to re-read and spread — the
  same merge, written N times, in the wrong place.

## `docs/architecture/frontend.md`

- **The `rightSection` recipe, fact 3** (line 171) — *"The default section width
  derives from the input-height variable, which an autosizing `Textarea` has no
  fixed value for."*
  **Change:** generalize the fact so it no longer depends on autosizing: an
  explicit `rightSectionWidth` is what makes both the slot and the input's own text
  padding deterministic, **whether or not** the input autosizes. Note that the repo's
  one `rightSection` call site is now a **fixed-height** textarea and still sets it.
  **Reason:** a reader checking the recipe against the shipped code will find the
  stated premise no longer true and may conclude the rule lapsed.
  *Low priority — the architect may reasonably fold this into the
  `frontend-workspace.md` entry above and skip it here.*

## Follow-up for `/roadmap` — **not this feature's to write**

- `docs/plans/roadmap.md` has no row for this feature: it was not roadmapped, and
  `008` was minted by `/fast-feature`. Recording `fast/008.composer-resize` as
  delivered is `/roadmap`'s job. **This plan must not edit `roadmap.md`.**

## Follow-ups spotted at planning (seeds for the coder's `## Observations`)

Not this feature's work; recorded so they are not lost.

- **`fast/005`'s outcome was never applied to `frontend-workspace.md`'s out-of-scope
  bullet.** The architect should treat the first entry above as covering both
  features, not just this one — otherwise the bullet stays stale for a third round.
- **`docs/product/vision.md:155-159`** still lists pane resize and ratio persistence
  as a product non-goal routed to `/architect`. It has now been built twice.
  `docs/product/` is **read-only** from planning and from architecture — closing this
  is `/product-spec`'s, and the orchestrator should surface it rather than anyone
  editing the file.
- **Transcript auto-scroll** (`frontend-workspace.md` → "Gap") becomes more
  conspicuous with a tall composer: less transcript is visible, so a streaming turn
  writes below the fold sooner. Still out of scope, still sanctioned as *one
  `autorun` in the pane-level mount effect*; noted only so the connection is on the
  record when someone finally builds it.
- **A composer drag in flight at workspace unmount is not cleaned up by the shell**,
  because `WorkspaceShell.tsx` was kept out of scope for one cleanup line. It is a
  non-problem — a drag holds the pointer so a route change cannot occur mid-drag,
  and the listeners live on `window` so the eventual `pointerup` still runs the
  restore. Recorded so it is not later mistaken for an oversight.

<!-- coder appends ## Observations below -->

## Observations

- The chat pane's vertical child order is now `MessageList` -> `ComposerResizeHandle`
  -> `Composer`, and the handle is an ORDINARY FLOW CHILD (`height: 6`,
  `flexShrink: 0`, no positioning) — unlike `ChatResizeHandle`, which is absolutely
  positioned over the aside's edge. Possible impact: name the handle in
  `frontend-workspace.md`'s chat-pane parts table and in the vertical-contract
  paragraph, so the non-shrinking children are listed as two, not one.
- `readWorkspaceLayout` now clamps `composerHeight` to the MINIMUM only, and the
  `MAX_COMPOSER_HEIGHT_FRACTION` ceiling is applied at three points of use (the
  `ChatPaneState` constructor, the drag's move handler, the keyboard nudge) — the
  module stays DOM-free. Possible impact: state the read-clamps-minimum /
  use-clamps-maximum split in `frontend-work-drafts.md`'s `workspaceLayout.ts` row
  beside the two-writer note, since it is the reason the module needs no window.
