<!-- product-spec:start -->
# Use Cases — FEAT-012 Chapter summaries & state notes

### UC-047 — System drafts a chapter's summary and state-note changes on close
- **Feature:** FEAT-012 · **Actor:** ACT-004
- **Preconditions:** Owner has initiated closing the open chapter (UC-036).
- **Main flow:**
  1. Owner initiates closing the chapter.
  2. System drafts a summary of the chapter's content.
  3. System drafts the chapter's state-note changeset (notes added, modified,
     deleted).
  4. Draft is presented to the owner for review (UC-048).
- **Postconditions:** Chapter has a draft summary and draft state-note
  changeset, pending owner approval; chapter is not yet closed.
- **Source:** `[confirmed: user]` interview 2026-07-20, "Augment round 2",
  "summaries & state notes": "LLM proposes, owner approves. On closing a
  chapter the system drafts them."

### UC-048 — Owner reviews and approves a chapter's continuity data
- **Feature:** FEAT-012 · **Actor:** ACT-004
- **Preconditions:** Chapter has a drafted summary and state-note changeset
  (UC-047) pending approval.
- **Main flow:**
  1. Owner reviews the drafted summary and state-note changeset.
  2. Owner edits either as needed.
  3. Owner approves.
  4. System marks the chapter's continuity data approved; closing (UC-036)
     may proceed.
- **Exception flow:** Owner approves with the summary left empty →
  `_TBD: whether an empty summary blocks approval is not stated in the
  interview._`
- **Postconditions:** Chapter's continuity data is approved.
- **Source:** `[confirmed: user]` interview 2026-07-20, "Augment round 2",
  "summaries & state notes": "LLM proposes, owner approves... the owner
  reviews, edits and accepts."

### UC-049 — View the book's current state notes
- **Feature:** FEAT-012 · **Actor:** ACT-004, ACT-005
- **Preconditions:** None (an empty state-note set is valid).
- **Main flow:**
  1. Member opens the book's state notes.
  2. System shows the current live set of state notes.
- **Postconditions:** Member sees current truth, not a historical
  accumulation.
- **Source:** `[confirmed: user]` interview 2026-07-20, "Augment round 2",
  "summaries & state notes": "There is one live set of state notes... Chapter
  N sees current truth."

### UC-050 — Edit state notes
- **Feature:** FEAT-012 · **Actor:** ACT-004, ACT-005
- **Preconditions:** Book has a collaboration mode set (free or proposal,
  FEAT-010).
- **Main flow:**
  1. Member adds, modifies or deletes a state note.
  2. In free mode: system applies the change to the live set immediately.
  3. In proposal mode: system holds the change as a proposal; owner applies
     it (FEAT-010 mechanism).
- **Exception flow:** Member deletes a note that a later chapter's
  changeset recorded as modified → not resolved here; FEAT-016's
  consistency check (UC-064) surfaces the inconsistency as a flag — see
  FEAT-016.
- **Postconditions:** Live state-note set reflects the applied change (free
  mode) or holds a pending proposal (proposal mode).
- **Source:** `[confirmed: user]` interview 2026-07-20, "Augment round 2",
  "summaries & state notes": "Follows the book's collaboration mode — free
  mode any member edits directly, proposal mode they propose and the owner
  applies."

### UC-051 — View a chapter's state-note changeset
- **Feature:** FEAT-012 · **Actor:** ACT-004, ACT-005
- **Preconditions:** Chapter has closed at least once and has a recorded
  changeset.
- **Main flow:**
  1. Member selects a chapter.
  2. System shows which state notes that chapter added, modified or
     deleted.
- **Postconditions:** Member sees the chapter's recorded delta, distinct
  from the current live set.
- **Source:** `[confirmed: user]` interview 2026-07-20, "Augment round 2",
  "summaries & state notes": "each chapter records which notes it added,
  modified or deleted."

### UC-052 — Reopening a chapter flags its continuity data stale
- **Feature:** FEAT-012 · **Actor:** ACT-004
- **Preconditions:** Owner reopens a closed chapter (UC-037).
- **Main flow:**
  1. Owner reopens a closed chapter.
  2. System flags the chapter's summary and state-note changeset stale.
  3. Chapter returns to the open state (per UC-037).
- **Exception flow:** Chapter being reopened has no approved continuity
  data on record → `_TBD: not addressed in the interview._`
- **Postconditions:** Chapter's continuity data is marked stale; re-closing
  requires re-approval (UC-048). Whether later chapters' changesets built
  on this chapter's deltas are consistent is checked by FEAT-016's
  consistency check (UC-064/UC-065), not by this use case — see FEAT-016.
- **Source:** `[confirmed: user]` interview 2026-07-20, "Augment round 2",
  "summaries & state notes": "Flagged stale, owner must re-confirm." /
  "The cascade — not decided yet"; challenge C12, closed by FEAT-016
  (round 3).

### UC-079 — State note references a named codex entry
- **Feature:** FEAT-012 · **Actor:** ACT-004, ACT-005
- **Preconditions:** A named codex entry (character or location, FEAT-017)
  exists in the book.
- **Main flow:**
  1. Member writes or edits a state note (UC-050).
  2. Member names the codex entry the note is about.
  3. System records the reference alongside the note.
- **Postconditions:** State note carries a reference to the named entry; the
  note remains free text otherwise — no entity model beyond this reference.
- **Source:** `[confirmed: user]` interview 2026-07-20, "codex" round 4: "A
  state note may reference a codex entry."; "Identity vs. change."
<!-- product-spec:end -->
