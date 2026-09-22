<!-- product-spec:start -->
# Stories — FEAT-010 Proposal mode

### US-042 — Co-author submits proposed edits
- **Feature:** FEAT-010 · **Actor:** ACT-005 · **Realizes:** UC-040
- **Status:** proposed
- **Story:** As a co-author, I want to submit proposed edits for the open
  chapter, so that the owner can review my contribution before it lands.
- **Acceptance criteria:**
  - **US-042.AC-1** — Given the book in proposal mode with a chapter open,
    when a co-author submits one or more edits as a proposal, then those
    edits are recorded as pending, attributed to that co-author.
  - **US-042.AC-2** — Given no chapter is open, when a co-author attempts
    to submit a proposal, then the submission is refused.
- **Source:** `[confirmed: user]` interview 2026-07-20, "collaboration
  mode": "A co-author proposes one or more blocks for the open chapter.";
  renamed "block" → "edit": interview 2026-07-30, "finalization — 021 +
  014 + 015", challenge C2.

### US-043 — Owner applies proposals selectively
- **Feature:** FEAT-010 · **Actor:** ACT-004 · **Realizes:** UC-041
- **Status:** proposed
- **Story:** As a book owner, I want to apply proposed edits selectively
  across co-authors, so that I can merge only what I want.
- **Acceptance criteria:**
  - **US-043.AC-1** — Given pending proposed edits from more than one
    co-author, when the owner selects a subset of those edits to apply,
    then only the selected edits become part of the open chapter.
  - **US-043.AC-2** — Given pending proposed edits, when the owner applies
    none of them, then the chapter is unchanged and the proposals remain
    pending.
- **Source:** `[confirmed: user]` interview 2026-07-20, "collaboration
  mode": "The owner merges freely... Approval is a merge, not a binary
  accept."; renamed "block" → "edit": interview 2026-07-30, "finalization
  — 021 + 014 + 015", challenge C2.

### US-044 — Owner changes the collaboration mode
- **Feature:** FEAT-010 · **Actor:** ACT-004 · **Realizes:** UC-042
- **Status:** proposed
- **Story:** As a book owner, I want to change the book's collaboration
  mode at any time, so that I can adapt how co-authors contribute.
- **Acceptance criteria:**
  - **US-044.AC-1** — Given a book in free mode, when the owner switches it
    to proposal mode, then subsequent edit contributions to the open
    chapter require owner application before they land.
  - **US-044.AC-2** — Given a book in proposal mode, when the owner
    switches it to free mode, then subsequent edit contributions to the
    open chapter land immediately on save.
  - `_TBD: fate of proposals already pending at the moment of a switch to
    free mode — not stated_`
- **Source:** `[confirmed: user]` interview 2026-07-20, "collaboration
  mode": "Yes, the owner can change it at any time."; renamed "block" →
  "edit": interview 2026-07-30, "finalization — 021 + 014 + 015",
  challenge C2.
<!-- product-spec:end -->
