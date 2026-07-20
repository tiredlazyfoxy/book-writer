<!-- product-spec:start -->
# Use Cases — FEAT-009 Chapter writing in blocks

### UC-035 — Open a chapter for writing
- **Feature:** FEAT-009 · **Actor:** ACT-004
- **Preconditions:** Chapter is in the planned state; no other chapter is
  currently open.
- **Main flow:**
  1. Owner selects a planned chapter.
  2. Owner opens it.
  3. System transitions the chapter planned → open.
- **Exception flow:** Another chapter is already open →
  `_TBD: whether opening a planned chapter while another is open is
  refused or auto-closes the other — not stated; only reopen (UC-037) was
  confirmed to auto-close_`. Non-owner attempts to open → refused.
- **Postconditions:** Selected chapter is open; at most one chapter open
  across the book.
- **Source:** `[confirmed: user]` interview 2026-07-20, "writing — blocks &
  concurrency" / "book structure — chapters, states, sketches": "Owner
  only... At most one open chapter per book."

### UC-036 — Close the open chapter
- **Feature:** FEAT-009 · **Actor:** ACT-004
- **Preconditions:** A chapter is currently open; its summary and
  state-note changes are approved (UC-048).
- **Main flow:**
  1. Owner selects the open chapter.
  2. Owner closes it.
  3. System transitions the chapter open → closed.
- **Exception flow:** Non-owner attempts to close → refused. Chapter's
  continuity data (summary, state-note changeset) is not yet approved →
  closing is refused.
- **Postconditions:** Chapter is closed (not editable); no chapter open
  until another is opened.
- **Source:** `[confirmed: user]` interview 2026-07-20, "book structure —
  chapters, states, sketches": "closed (written, not editable)."
  Continuity precondition — `[confirmed: user]` interview 2026-07-20,
  "Augment round 2", "summaries & state notes": "Approval required to
  close... Closing means continuity is complete."; challenge C17
  (FEAT-012).

### UC-037 — Reopen a closed chapter
- **Feature:** FEAT-009 · **Actor:** ACT-004
- **Preconditions:** Chapter is in the closed state.
- **Main flow:**
  1. Owner selects a closed chapter.
  2. Owner reopens it.
  3. System closes whichever chapter is currently open, if any.
  4. System transitions the selected chapter closed → open.
- **Exception flow:** Non-owner attempts to reopen → refused.
- **Postconditions:** Selected chapter is open; any previously open chapter
  is now closed. Editing it now produces a variant — see FEAT-014.
- **Source:** `[confirmed: user]` interview 2026-07-20, "book structure —
  chapters, states, sketches": "Reopening a chapter implies closing the
  currently-open one."

### UC-038 — Add a block to the open chapter (free mode)
- **Feature:** FEAT-009 · **Actor:** ACT-004, ACT-005
- **Preconditions:** A chapter is open; book is in free mode.
- **Main flow:**
  1. Member writes a block.
  2. Member saves it.
  3. System adds the block to the open chapter immediately.
- **Alternate flow:** Two members add different blocks to the open chapter
  at the same time → both blocks land; no conflict.
- **Exception flow:** No chapter is open → add refused.
- **Postconditions:** New block exists in the open chapter, attributed to
  its author.
- **Source:** `[confirmed: user]` interview 2026-07-20, "writing — blocks &
  concurrency": "the process of the chapter writing is... by some blocks."

### UC-039 — Edit a block that changed underneath
- **Feature:** FEAT-009 · **Actor:** ACT-004, ACT-005
- **Preconditions:** A chapter is open; a block exists in it.
- **Main flow:**
  1. Member A begins editing a block.
  2. Member B saves a change to that same block first.
  3. Member A attempts to save.
  4. System warns member A the block changed underneath them.
  5. Member A chooses to overwrite or abandon their edit.
- **Exception flow:** Member A abandons → their edit is discarded, the
  block keeps member B's version. Member A overwrites → their save applies
  and becomes the block's current version (later write wins).
- **Postconditions:** Block holds exactly one current version — whichever
  of the two writes was applied last.
- **Source:** `[confirmed: user]` interview 2026-07-20, "writing — blocks &
  concurrency": "warn-then-later-write-wins rule applies only when two
  co-authors edit the same block." `_TBD: what a block contains (format,
  length, structure)._`
<!-- product-spec:end -->
