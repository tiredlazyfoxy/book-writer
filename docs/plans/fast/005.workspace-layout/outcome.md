# Outcome — fast feature 005 workspace-layout

Intended documentation changes once this feature ships, for the architect to
apply at finalization. Grouped by target file. The coder appends
`## Observations` at the bottom when implementation lands.

**No new top-level document is proposed.** Both follow-ups land in existing
files, and neither pushes its file past the folder's ~400-line rule.

## `docs/architecture/frontend-work-drafts.md`

- **Section "The module tier — five members"** — the table and its heading.
  **Change:** retitle to six members and add a row for
  `src/work/workspaceLayout.ts` — *holds:* the workspace's collapse flag and
  chat-pane width fraction; *persisted:* `localStorage`, under **one global key**
  (`bookwriter.workspace-layout`), not per book.
  **Reason:** the section states outright that the members are recorded together
  "so a sixth is added on purpose rather than by precedent". This is that sixth,
  and leaving the count at five makes the file wrong the moment the feature
  lands.

- **Same section — add a short sanction subsection**, in the shape the fourth
  and fifth members already have ("The fourth member, sanctioned on purpose",
  "The fifth member, sanctioned on the same terms").
  **Change:** record that `workspaceLayout.ts` is a **different exception from
  the drafts one**. The drafts tier exists for *not-yet-saved data* — large,
  private, expensive to lose. A pane width and a collapse flag are
  **device-ergonomics view preference**: small, and arguably URL-able under
  `frontend.md`'s "query params are the persistence layer" rule. They are
  deliberately kept **device-local and out of the URL** because they describe
  *this screen*, not *this book*, and must not travel in a shared link or force a
  co-author into someone else's pane geometry. Record the three shape decisions
  with them: **one global key** rather than per-book (the same screen serves
  every book), a **fraction of viewport width** rather than pixels (so the layout
  survives a monitor change with no resize listener), and **`localStorage` rather
  than `sessionStorage`** (a remembered layout that resets per tab is worse than
  none).
  **Reason:** every other member of this tier carries an explicit sanction; a
  sixth added without one turns the tier's discipline into precedent-following,
  which is exactly what the section says it exists to prevent.

- **Same section — one interaction worth a clause.**
  **Change:** note that `restoreBuffer.ts`'s quota eviction sweep only touches
  keys under `RESTORE_BUFFER_KEY_PREFIX`, so the layout key is **never an
  eviction victim**; conversely a quota-exhausting draft write makes
  `writeWorkspaceLayout` throw-and-swallow, silently reverting the layout to
  defaults on the next load — the same best-effort contract `activeChat.ts`
  already accepts, and a second reason the width is written on pointer-up rather
  than on every pointer move.
  **Reason:** the tier's quota story is documented for the buffer only; a reader
  adding a seventh member needs to know which side of the eviction line it lands
  on.

## `docs/architecture/frontend-workspace.md`

- **The "Out of scope" list, first bullet (line 329)** — currently reads
  *"Pane orientation, resize/divider behaviour and ratio persistence. Product
  routes these to `/architect` but this pass does not settle them."*
  **Change:** the bullet is now **stale and must be narrowed**. Resize/divider
  behaviour and ratio persistence are **settled and shipped**; only **pane
  orientation** remains out of scope. Keep orientation in the list, with the same
  routing note.
  **Reason:** the sentence is a live instruction to the next planner that this
  ground is unclaimed. Leaving it would invite a second, different resize
  mechanism.

- **The "working page" section — add the settled mechanics**, as a short
  subsection beside the three-region diagram (the diagram itself needs no
  change).
  **Change:** record, with reasoning:
  - **The navigator has two widths, not a continuum** — a 220px expanded state
    and a ~54px icon-only rail, toggled by a header pin control. Chosen over a
    hover-expand overlay by the user: a rail that changes width on hover makes
    the content pane's edge move under the pointer.
  - **The chat pane's width is a fraction of the viewport**, defaulting to
    `0.35` and clamped to `[0.15, 0.60]`, driven at drag time through a **CSS
    custom property** (`--work-chat-width`) set by a single `autorun` in the
    shell's **existing** mount effect. The width prop on `AppShell.Aside` is a
    **constant string** and the shell never observes the live fraction — that is
    what keeps a pointer drag from re-rendering the content pane, and it is the
    load-bearing part of the design.
  - **The `calc()` wrapper is mandatory.** Mantine's `rem()` passes a string
    through verbatim only when it starts with `calc(`, `clamp(` or `rgba(`;
    every other comma-bearing string is split on commas and mangled. So the width
    is `calc(var(--work-chat-width, 35vw))`, never the bare `var(...)` form. This
    is worth a documented line because the wrong form **compiles, typechecks and
    emits garbage CSS with no test failure**.
  - **No `window` "resize" listener exists** — a `vw` length reflows for free.
  - **Breakpoints stay pure CSS.** Mantine forces a 100% navbar below
    `navbar.breakpoint` and a 100% aside below `aside.breakpoint`, so the mobile
    drawer flag (`navbarOpened`) and the desktop rail flag (`navCollapsed`) are
    orthogonal and never active at the same viewport. No `useMediaQuery` was
    introduced.
  - **The rail hides its labels in CSS, not JavaScript** (`global.css`, inside
    `min-width: 48em`, via `NavLink` `classNames`), because Mantine's `NavLink`
    always renders the body span and a JS boolean cannot be breakpoint-aware
    without the banned `useMediaQuery`.
  - **The drag gesture is a `[manual/live]` criterion**, on the exact reasoning
    `frontend.md` already records for `@dnd-kit` and ProseMirror. The geometry is
    extracted as a pure function and the persistence and CSS-variable wiring are
    verified through a keyboard path on the handle.
  **Reason:** these are layout mechanics with real traps in them, and the next
  person to touch `WorkspaceShell.tsx` will otherwise re-derive them wrongly —
  most likely by making the shell observe the width fraction, or by dropping the
  `calc()`.

## `docs/architecture/frontend.md`

- **"React hook rules" — the `autorun` sentence.** It currently reads *"For rare
  imperative side-effects on observable change (e.g. auto-scroll while
  streaming), use a single `autorun` started in the mount `useEffect` and
  disposed on cleanup."*
  **Change:** optionally add the workspace layout's CSS-variable write as a
  **second worked instance** of that rule — an `autorun` that pushes an
  observable value onto a CSS custom property so that high-frequency updates
  bypass React entirely.
  **Reason:** the rule had one example and read as narrowly about scrolling; a
  second, structurally different instance makes it a pattern. Low priority — the
  architect may reasonably decide the `frontend-workspace.md` entry above is
  enough and skip this.

## Follow-up for `/roadmap` — **not this feature's to write**

- `docs/plans/roadmap.md` has no row for this feature: it was not roadmapped, and
  `005` was minted by `/fast-feature`. Recording `fast/005.workspace-layout` as
  delivered is `/roadmap`'s job. **This plan must not edit `roadmap.md`.**

## Follow-ups spotted at planning (seeds for the coder's `## Observations`)

Not this feature's work; recorded so they are not lost.

- **`docs/product/vision.md:155-159`** still lists pane resize and ratio
  persistence as a product non-goal routed to `/architect`. It is now built.
  `docs/product/` is **read-only** from planning and from architecture — closing
  this is `/product-spec`'s, and the orchestrator should surface it rather than
  anyone editing the file.
- **`docs/plans/010.working-page/brief.md`** → Scope Out still says "pane
  resize/orientation mechanics". A delivered brief is history and should be left
  as written; noted only so a future reader does not treat it as a live
  exclusion.
- **Mantine's `rem()` mangling of comma-bearing strings** is a repo-wide hazard,
  not a workspace one — it applies to every `AppShell` dimension prop and every
  `Box` size that might one day be given a `var()`. Worth a line wherever the
  frontend conventions record Mantine gotchas, if such a place is ever created.

<!-- coder appends ## Observations below -->

## Observations

- Mantine's `rem()` pass-through rule is narrower than "starts with a function":
  `calc(` and `clamp(` are matched with `startsWith`, but `rgba(` with `includes`.
  Anything else holding a comma is split and reassembled per-part, so a `var()`
  with a fallback is mangled in **any** Mantine size prop, not just the
  `AppShell` width used here. Possible impact: if the `frontend-workspace.md`
  entry the plan already specifies is written as workspace-local, consider
  stating the rule once in general terms wherever Mantine gotchas are recorded —
  it applies repo-wide.
- The aside width string survives Mantine untouched via
  `assignAsideVariables` → `isPrimitiveSize` (a plain string qualifies) →
  `getBaseSize` → `rem`, landing on `--app-shell-aside-width`. Because
  `aside.collapsed.mobile` is true, Mantine still forces `100%` below the `md`
  breakpoint, so the custom property is inert on mobile with no JS involved.
  Possible impact: worth one clause in `frontend-workspace.md`'s new
  "settled mechanics" subsection, as the concrete reason no responsive
  `{ base, md }` width object was needed.
- `endChatResize` is guarded on `resizeDispose` rather than on `resizing`, which
  makes the shell's unconditional unmount call a true no-op — including no
  storage write. Possible impact: if `frontend-workspace.md` records the resize
  lifecycle, note that the width is persisted at the moment of change
  (pointer-up, keyboard nudge, pin toggle) and never on unmount.
- `0.35 + 0.02 === 0.37` is exact in IEEE-754, so the keyboard path stores clean
  fractions from the default; the two-decimal rounding lives only in
  `chatWidthCss`, where a longer nudge chain would otherwise emit float noise
  into the CSS variable. Possible impact: none doc-side unless the architect
  records the rounding rule, in which case it belongs on the CSS string, not on
  the stored fraction.
