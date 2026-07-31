<!-- product-spec:start -->
# Use Cases — FEAT-009 Chapter writing

(File retains its original slug, `chapter-writing-blocks`, per the
merge-fence filename-stability rule — the domain noun was renamed
"block" → "edit" in the 2026-07-30 finalization pass, the file was not.)

### UC-035 — Open a chapter for writing
- **Feature:** FEAT-009 · **Actor:** ACT-004
- **Preconditions:** Chapter is in the planned state; no other chapter is
  currently open.
- **Main flow:**
  1. Owner selects a planned chapter.
  2. Owner opens it.
  3. System transitions the chapter planned → open.
- **Exception flow:** Another chapter is currently open or closing →
  opening is **refused**; the owner closes that chapter through the
  continuity gate first (same rule as reopen, UC-037, by symmetry). Closes
  the prior `_TBD:` on this flow. Non-owner attempts to open → refused.
- **Postconditions:** Selected chapter is open; at most one chapter open
  across the book.
- **Source:** `[confirmed: user]` interview 2026-07-20, "writing — blocks &
  concurrency" / "book structure — chapters, states, sketches": "Owner
  only... At most one open chapter per book." Exception flow:
  `[confirmed: user]` interview 2026-07-24, "augment round 7", divergence
  4 — closes CF1 by symmetry with UC-037's reopen refusal.

### UC-036 — Close the open chapter
- **Feature:** FEAT-009 · **Actor:** ACT-004
- **Preconditions:** A chapter is currently open.
- **Main flow:**
  1. Owner selects the open chapter.
  2. Owner requests it closed.
  3. System transitions the chapter open → **closing**.
  4. System drafts and checks the chapter's continuity (UC-047) during the
     closing window.
  5. On a **clean run** (a drafted summary, a drafted state-note
     changeset, a proposed resulting note set, and no blocking check flag),
     system transitions the chapter closing → closed and marks both
     artifacts approved in the same step.
- **Exception flow:** Non-owner attempts to close → refused. The run is
  stopped by the owner, fails, or produces a blocking check flag → the
  chapter returns to **open** and every draft artifact is discarded.
  `closing` exists only for the duration of the run; a chapter is never
  left parked in it. A `closing` chapter holds the book's one-open-chapter
  slot for the duration (US-038.AC-4, delivered).
- **Postconditions:** Chapter is closed (not editable); no chapter open or
  closing until another is opened.
- **Note (finalization, 2026-07-30; updated 2026-07-31):** Steps 1–2 and
  the postcondition above (an ungated `open → closed`) shipped in
  `docs/plans/015.chapter-writing-free-mode/`. Step 3 (the **closing**
  state) and step 5 (the clean-run close, design-note D4) shipped in
  `docs/plans/016.chapter-close-continuity/`. Step 4 — drafting the
  chapter's continuity data (UC-047) — remains **deferred**: the
  mechanism is built, but its tools ship unreachable until an admin
  assigns them to the `close-chapter` mode (FEAT-020), and the plan's
  live-run criterion was never exercised (see UC-047's note). This is why
  UC-036 stays `partially delivered`.
- **Source:** `[confirmed: user]` interview 2026-07-20, "book structure —
  chapters, states, sketches": "closed (written, not editable)."
  Continuity precondition — `[confirmed: user]` interview 2026-07-20,
  "Augment round 2", "summaries & state notes": "Approval required to
  close... Closing means continuity is complete."; challenge C17
  (FEAT-012). **Closing state:** `[confirmed: user]` interview 2026-07-24,
  "augment round 7", divergence 6 (C-r7-4) — a fourth chapter state that
  holds the one-open-chapter slot and refuses writes while continuity
  awaits approval. **Delivery record:** `[confirmed: user]` interview
  2026-07-30, "finalization — 021 + 014 + 015". **Step 5 + exception flow
  amended to the shipped clean-run close (design-note D4), resolving
  CF2:** `[confirmed: user]` interview 2026-07-31, finalization of plan
  016, challenge C-f16-3.

### UC-037 — Reopen a closed chapter
- **Feature:** FEAT-009 · **Actor:** ACT-004
- **Preconditions:** Chapter is in the closed state.
- **Main flow:**
  1. Owner selects a closed chapter.
  2. Owner reopens it.
  3. System checks that no chapter in the book is currently open or
     closing.
  4. System transitions the selected chapter closed → open.
- **Exception flow:** Another chapter is currently open or closing → the
  reopen is **refused**, with the reason; the owner closes that chapter
  through the continuity gate (UC-036) first. This closes **CF1**,
  product's own round-5 coherence finding (the reopen no longer
  auto-closes past the FEAT-012 approval gate). Non-owner attempts to
  reopen → refused.
- **Postconditions:** Selected chapter is open. Editing it now produces a
  variant — see FEAT-014.
- **Source:** `[confirmed: user]` interview 2026-07-20, "book structure —
  chapters, states, sketches": "Reopening a chapter implies closing the
  currently-open one." Superseded by `[confirmed: user]` interview
  2026-07-24, "augment round 7", divergence 4: "a reopen is refused while
  any chapter in the book is open or closing. The owner closes the
  current chapter properly, through the continuity gate, first."

### UC-038 — Add an edit to the open chapter (free mode)
- **Feature:** FEAT-009 · **Actor:** ACT-004, ACT-005
- **Preconditions:** A chapter is open; book is in free mode.
- **Main flow:**
  1. Member writes an edit — free text, any length, no internal structure.
  2. Member saves it.
  3. System appends the edit to the end of the open chapter's body.
- **Alternate flow:** Two members compose edits concurrently and the
  chapter's body moved between one member composing and saving → that
  save is **refused**; the member re-issues it against the current body.
  Both members' edits end up in the chapter once each save lands.
- **Exception flow:** No chapter is open → add refused.
- **Postconditions:** New edit's text is appended to the open chapter's
  body, attributed to its author; the edit is not separately addressable
  once appended.
- **Source:** `[confirmed: user]` interview 2026-07-20, "writing — blocks &
  concurrency": "the process of the chapter writing is... by some blocks."
  Rewritten: `[confirmed: user]` interview 2026-07-24, "augment round 7",
  divergence 5 (C-r7-2) — "a block is a change that merges into the
  chapter's single body and stops existing as an object. Concurrency is
  per chapter, on a chapter version." Closes the block-contents `_TBD:`.
  Renamed "block" → "edit": `[confirmed: user]` interview 2026-07-30,
  "finalization — 021 + 014 + 015", challenge C2. This use case shipped —
  see FEAT-009's `**Delivered:**` line.

### UC-039 — Save an edit to a chapter whose body changed underneath
- **Feature:** FEAT-009 · **Actor:** ACT-004, ACT-005
- **Preconditions:** A chapter is open.
- **Main flow:**
  1. Member A composes an edit against the chapter's current body.
  2. Member B's edit to the same chapter applies first.
  3. Member A attempts to save.
  4. System refuses the save because it was composed against an older
     body; member A is shown the current body against their own text.
  5. Member A reconciles the two manually and saves again.
  6. Member A's reconciled text becomes the chapter's next applied change.
- **Exception flow:** The system never merges automatically and never
  silently discards either member's text.
- **Postconditions:** The chapter's body reflects member B's change and,
  once reconciled, member A's change; nothing either member wrote is
  silently lost.
- **Source:** `[confirmed: user]` interview 2026-07-20, "writing — blocks &
  concurrency": "warn-then-later-write-wins rule applies only when two
  co-authors edit the same block." Retitled and rewritten:
  `[confirmed: user]` interview 2026-07-24, "augment round 7", divergence
  5 (C-r7-2) — concurrency is per chapter body and version, not per block;
  a stale save is refused and reconciled by hand, never auto-merged or
  discarded.
<!-- product-spec:end -->
