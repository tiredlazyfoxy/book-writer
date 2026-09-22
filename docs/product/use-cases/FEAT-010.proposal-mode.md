<!-- product-spec:start -->
# Use Cases — FEAT-010 Proposal mode

### UC-040 — Submit proposed edits
- **Feature:** FEAT-010 · **Actor:** ACT-005
- **Preconditions:** Book is in proposal mode; a chapter is open.
- **Main flow:**
  1. Co-author writes one or more edits.
  2. Co-author submits them as a proposal for the open chapter.
  3. System records the proposed edits, pending owner review.
- **Exception flow:** No chapter is open → submission refused. Book is in
  free mode → proposing does not apply; edits apply directly (UC-038)
  instead.
- **Postconditions:** Proposed edits exist, attributed to the submitting
  co-author, not yet part of the chapter.
- **Source:** `[confirmed: user]` interview 2026-07-20, "collaboration
  mode": "A co-author proposes one or more blocks for the open chapter.";
  renamed "block" → "edit": interview 2026-07-30, "finalization — 021 +
  014 + 015", challenge C2.

### UC-041 — Owner reviews and applies proposals
- **Feature:** FEAT-010 · **Actor:** ACT-004
- **Preconditions:** Open chapter has one or more pending proposed edits,
  from any co-author.
- **Main flow:**
  1. Owner reviews pending proposed edits across co-authors.
  2. Owner selects which proposed edits to apply.
  3. System applies the selected edits to the open chapter.
  4. Unselected proposed edits remain pending.
- **Exception flow:** Owner applies none of the pending proposals →
  chapter unchanged, proposals remain pending.
- **Postconditions:** Selected proposed edits are now part of the open
  chapter; the owner may take edits from several co-authors' proposals in
  the same review.
- **Source:** `[confirmed: user]` interview 2026-07-20, "collaboration
  mode": "The owner merges freely... Approval is a merge, not a binary
  accept."; renamed "block" → "edit": interview 2026-07-30, "finalization
  — 021 + 014 + 015", challenge C2.

### UC-042 — Change the book's collaboration mode
- **Feature:** FEAT-010 · **Actor:** ACT-004
- **Preconditions:** Owner authenticated; book exists.
- **Main flow:**
  1. Owner selects a different collaboration mode (free ↔ proposal).
  2. System applies the new mode.
- **Exception flow:** Book switched from proposal to free mode while
  proposals are pending → `_TBD: fate of pending proposals when switching
  to free mode — not stated_`.
- **Postconditions:** Book's collaboration mode updated; applies to
  whichever chapter is subsequently open.
- **Source:** `[confirmed: user]` interview 2026-07-20, "collaboration
  mode": "Yes, the owner can change it at any time."
<!-- product-spec:end -->
