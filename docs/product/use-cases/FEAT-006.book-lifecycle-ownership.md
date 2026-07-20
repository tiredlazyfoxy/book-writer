<!-- product-spec:start -->
# Use Cases — FEAT-006 Book lifecycle & ownership

### UC-021 — Create a book
- **Feature:** FEAT-006 · **Actor:** ACT-002
- **Preconditions:** Author authenticated.
- **Main flow:**
  1. Author opens "create book".
  2. Author sets the book's collaboration mode (free or proposal) and
     visibility (private or public).
  3. Author submits.
  4. System creates the book with a chapter skeleton.
  5. Author becomes the book's owner.
- **Postconditions:** Book exists with exactly one owner, a collaboration
  mode, and a visibility setting.
- **Source:** `[confirmed: user]` interview 2026-07-20, "ownership,
  membership & visibility"; "collaboration mode": "on book creation the
  owner set the mode"

### UC-022 — List my books
- **Feature:** FEAT-006 · **Actor:** ACT-004
- **Preconditions:** Owner authenticated.
- **Main flow:**
  1. Owner opens their book list.
  2. System returns the books they own.
- **Postconditions:** None (read-only).
- **Source:** `[inferred]` interview 2026-07-20, "ownership, membership &
  visibility" — a basic access capability implied by owning books; not
  itself asked.

### UC-023 — Archive a book
- **Feature:** FEAT-006 · **Actor:** ACT-004
- **Preconditions:** Owner authenticated; book exists and is not archived.
- **Main flow:**
  1. Owner selects the book.
  2. Owner requests archive.
  3. System marks the book archived.
- **Exception flow:** Book has an open chapter at the time of archive →
  `_TBD: whether archiving force-closes the open chapter or is refused —
  not stated_`.
- **Postconditions:** Book status is archived; content and history
  preserved; never destroyed (see FEAT-011 for the sole exception).
- **Source:** `[confirmed: user]` interview 2026-07-20, "ownership,
  membership & visibility": "Archive only, no hard delete."

### UC-024 — Transfer ownership
- **Feature:** FEAT-006 · **Actor:** ACT-004
- **Preconditions:** Owner authenticated; book exists.
- **Main flow:**
  1. Owner selects a co-author to become the new owner.
  2. Owner confirms transfer.
  3. System reassigns ownership to that co-author.
- **Exception flow:** Selected target is not a current co-author (a
  non-member) → `_TBD: whether transfer to a non-member is refused outright
  or implicitly adds them as a co-author — not stated_`.
- **Postconditions:** Ownership transfers to the selected co-author.
- **Source:** `[confirmed: user]` interview 2026-07-20, "ownership,
  membership & visibility": "ownership can be transferred."

### UC-025 — Admin reassigns ownership of a book whose owner is disabled
- **Feature:** FEAT-006 · **Actor:** ACT-001
- **Preconditions:** Book's current owner account is disabled (FEAT-003).
- **Main flow:**
  1. Admin opens the book's ownership-recovery context.
  2. Admin selects a new owner for the book.
  3. System reassigns ownership.
- **Exception flow:** Book's owner account is not disabled (still active) →
  reassignment refused.
- **Postconditions:** Book has a new, active owner.
- **Source:** `[inferred]` — derived from FEAT-003's disable-not-delete rule
  combined with transferable ownership (interview 2026-07-20, "ownership,
  membership & visibility"); admin reassignment of a disabled owner's book
  was never itself asked in the interview.
<!-- product-spec:end -->
