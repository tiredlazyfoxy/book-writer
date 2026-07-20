<!-- product-spec:start -->
# Use Cases — FEAT-015 Book cloning

### UC-061 — Owner clones a book
- **Feature:** FEAT-015 · **Actor:** ACT-004
- **Preconditions:** Owner authenticated; book exists.
- **Main flow:**
  1. Owner requests to clone their book.
  2. Owner chooses which members, if any, carry over (UC-063).
  3. System creates a new, independent book carrying the source's chapters,
     blocks, sketches, state notes, summaries, codex (FEAT-017),
     collaboration mode and visibility.
  4. Cloning owner becomes the new book's owner.
- **Exception flow:** Book has an open chapter →
  `_TBD: whether the open chapter carries over as open or is closed first —
  not stated._` Book has unapproved continuity data on its open chapter →
  `_TBD: whether cloning is refused or proceeds with unapproved data — not
  stated._` Book is archived → `_TBD: whether an archived book can be
  cloned — not stated._`
- **Postconditions:** New book exists, fully independent — no link, no
  sync, no comparison with the source. Accepted cost: the two books can
  drift apart permanently; a fix common to both must be made in each
  separately.
- **Source:** `[confirmed: user]` interview 2026-07-20, "book cloning": "We
  can 'clone' the book if we want new variation to not overload the
  interface... Fully independent. No link, no sync, no comparison." Codex
  carry-over: `[inferred]` codex round 4 — the codex is per-book content
  (FEAT-017), consistent with this round-3 carry-over list; not separately
  asked.

### UC-062 — Co-author clones a public book
- **Feature:** FEAT-015 · **Actor:** ACT-005
- **Preconditions:** Co-author authenticated; book is public; co-author is
  a member of the book.
- **Main flow:**
  1. Co-author requests to clone the book.
  2. Co-author chooses which members, if any, carry over (UC-063).
  3. System creates a new, independent book, same content and settings as
     UC-061.
  4. Cloning co-author becomes the new book's owner.
- **Exception flow:** Book is private → cloning refused; only the owner may
  clone a private book (FEAT-007, challenge C21). Same open-chapter,
  unapproved-continuity and archived-book exceptions as UC-061 apply.
- **Postconditions:** New book exists, owned by the cloning co-author, fully
  independent of the source.
- **Source:** `[confirmed: user]` interview 2026-07-20, "book cloning": "We
  can also give the member the ability to create his own clone, in this
  case they become the owner."; challenge C21.

### UC-063 — Choose which members carry over to a clone
- **Feature:** FEAT-015 · **Actor:** ACT-004, ACT-005
- **Preconditions:** A clone is being created (UC-061 or UC-062).
- **Main flow:**
  1. Cloner is shown the source book's member list.
  2. Cloner selects which members, all, some or none, to carry over.
  3. System adds only the selected members to the new clone.
- **Postconditions:** Clone's membership reflects the cloner's selection;
  the cloner is always the new book's owner regardless of selection.
- **Source:** `[confirmed: user]` interview 2026-07-20, "book cloning": "if
  it clones by owner — it clones the members (optional, or not all)... they
  become the owner and can copy or not copy members."
<!-- product-spec:end -->
