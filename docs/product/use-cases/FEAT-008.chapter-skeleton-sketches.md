<!-- product-spec:start -->
# Use Cases — FEAT-008 Chapter skeleton & sketches

### UC-031 — Add a chapter
- **Feature:** FEAT-008 · **Actor:** ACT-004, ACT-005
- **Preconditions:** Authenticated member (owner or co-author) of the book.
- **Main flow:**
  1. Member adds a new chapter with a sketch.
  2. System appends it to the skeleton in the *planned* state.
- **Postconditions:** New chapter exists, state planned, carrying the
  sketch; its position in the order remains the owner's to set.
- **Source:** `[confirmed: user]` interview 2026-07-20, "book structure —
  chapters, states, sketches": "Any member adds, owner orders."

### UC-032 — Reorder chapters
- **Feature:** FEAT-008 · **Actor:** ACT-004
- **Preconditions:** Owner authenticated; book has 2 or more chapters.
- **Main flow:**
  1. Owner rearranges the chapter sequence.
  2. System applies the new order.
- **Exception flow:** A chapter is currently open when reorder is requested
  → reorder is **allowed**. Reordering changes only a chapter's position
  in the sequence — it never reads or writes a body, never changes a
  state, and never bumps a chapter's version.
- **Postconditions:** Skeleton order updated.
- **Source:** `[confirmed: user]` interview 2026-07-20, "book structure —
  chapters, states, sketches": "owner orders."; reorder-while-open `_TBD:`
  closed per `docs/.cache/product/spec-plan.finalization.md` §D,
  docs/plans/014.chapter-skeleton/ (2026-07-30)

### UC-033 — Edit a chapter sketch
- **Feature:** FEAT-008 · **Actor:** ACT-004, ACT-005
- **Preconditions:** Chapter is in the *planned* state.
- **Main flow:**
  1. Member opens a planned chapter's sketch.
  2. Member edits it.
  3. System saves the sketch.
- **Exception flow:** Chapter is open or closed (not planned) → sketch edit
  refused. Two members edit the same sketch concurrently →
  **last-write-wins**: no version token, no divergence warning, no
  refusal — the later save simply overwrites the earlier one. (The
  warn-then-reconcile contract applies to the chapter body, which carries
  a version; a sketch has none.)
- **Postconditions:** Sketch content updated (planned chapters only).
- **Source:** `[confirmed: user]` interview 2026-07-20, "book structure —
  chapters, states, sketches": "Any co-author may edit the sketch of any
  unwritten chapter, in parallel."; concurrent-sketch-edit `_TBD:` closed
  per `docs/.cache/product/spec-plan.finalization.md` §D,
  docs/plans/014.chapter-skeleton/ (2026-07-30)

### UC-034 — Remove a planned chapter
- **Feature:** FEAT-008 · **Actor:** ACT-004, ACT-005
- **Preconditions:** Chapter is in the planned state.
- **Main flow:**
  1. Member selects a planned chapter.
  2. Member requests removal.
  3. System removes it from the skeleton.
- **Exception flow:** Chapter is open or closed → removal refused; only
  planned chapters can be removed.
- **Postconditions:** Chapter no longer exists in the skeleton.
- **Source:** `[inferred]` interview 2026-07-20, "book structure — chapters,
  states, sketches" — removal permission mirrors add ("any member"); not
  separately confirmed who may remove.
<!-- product-spec:end -->
