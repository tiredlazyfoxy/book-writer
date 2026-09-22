<!-- product-spec:start -->
# Use Cases — FEAT-011 Content moderation

### UC-043 — Admin opens a book in the moderation view
- **Feature:** FEAT-011 · **Actor:** ACT-001
- **Preconditions:** Admin authenticated.
- **Main flow:**
  1. Admin opens the moderation view.
  2. Admin selects any book, regardless of its visibility.
  3. System returns the book's content, including its codex (FEAT-017),
     read-only.
- **Postconditions:** None (read-only); admin gains no authoring access in
  the main interface.
- **Source:** `[confirmed: user]` interview 2026-07-20, "admin access &
  moderation": "admins can read all books... special read mode in the
  admin interface." Codex reach: `[confirmed: user]` interview 2026-07-20,
  "Augment round 4", "codex": "Yes — it's book content."

### UC-044 — Quarantine a book
- **Feature:** FEAT-011 · **Actor:** ACT-001
- **Preconditions:** Admin authenticated; book exists and is not already
  quarantined.
- **Main flow:**
  1. Admin selects a book in the moderation view.
  2. Admin quarantines it, giving a reason.
  3. System makes the book invisible to everyone, including its owner and
     co-authors.
- **Exception flow:** Book has an open chapter at the time of quarantine →
  `_TBD: whether the open chapter is force-closed or left as-is — not
  stated_`.
- **Postconditions:** Book invisible to all members; recoverable — distinct
  from destroy (UC-045), which is not.
- **Source:** `[confirmed: user]` interview 2026-07-20, "admin access &
  moderation": "quarantine makes the book invisible to everyone including
  its members — fast takedown, reversible mistake."

### UC-045 — Destroy a quarantined book
- **Feature:** FEAT-011 · **Actor:** ACT-001
- **Preconditions:** Book is quarantined.
- **Main flow:**
  1. Admin selects a quarantined book.
  2. Admin confirms destruction.
  3. System permanently destroys the book.
- **Exception flow:** Book was never quarantined → destroy refused;
  destruction requires the quarantine step first.
- **Postconditions:** Book permanently removed — the single sanctioned
  exception to FEAT-006's owner-facing archive-only, never-destroyed rule.
  **Limitation:** destruction does not reach clones — an independent clone
  of this book (FEAT-015), made before or after destruction, is unaffected;
  an admin moderates each book, including each clone, separately.
- **Source:** `[confirmed: user]` interview 2026-07-20, "admin access &
  moderation": "quarantine a whole book, then destroy it as a separate
  action... permanently."; clone limitation — challenge C22.

### UC-046 — Owner sees a removal notice
- **Feature:** FEAT-011 · **Actor:** ACT-004
- **Preconditions:** Book has been quarantined or destroyed by an admin.
- **Main flow:**
  1. Owner is shown a removal notice for the book, with the admin's stated
     reason.
- **Exception flow:** Owner attempts to open a quarantined book → the book
  remains invisible; the removal notice is shown instead of its content.
- **Postconditions:** Owner is informed the book was removed and why.
- **Source:** `[confirmed: user]` interview 2026-07-20, "admin access &
  moderation": "the owner sees a removal notice, with a reason. Not
  silent."
<!-- product-spec:end -->
