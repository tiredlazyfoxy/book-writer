<!-- product-spec:start -->
# Actors

### ACT-001 — Administrator
- **One-line:** Sets up and operates the platform; moderates book content.
- **Goal:** Bootstrap an instance, manage user accounts, connect LLM servers,
  keep the database healthy; moderate book content through the admin
  interface; restore ownership of books whose owner is disabled.
- **Context:** Acts through the admin section once authenticated with the
  `admin` role.
- **Constraints:** Cannot change their own role; cannot disable their own
  account. Cannot participate in a book — no authoring access in the main
  interface; admin access to book content exists only as the moderation
  view (FEAT-011).
- **Source:** `[confirmed: user]` interview 2026-07-20, "features"; admin
  moderation — `[confirmed: user]` interview 2026-07-20, "admin access &
  moderation"; ownership recovery — `[inferred]`, derived from FEAT-003's
  disable-not-delete rule combined with transferable ownership (interview
  2026-07-20, "ownership, membership & visibility"); never itself asked.

### ACT-002 — Author
- **One-line:** A book-writing account; owns and co-authors books.
- **Goal:** Log in and hold an account; own and co-author books through the
  ACT-004/ACT-005 relationships.
- **Context:** Acts through the platform once authenticated with the `author`
  role.
- **Constraints:** No admin-section access. `[inferred]` — role separation
  implied by the admin/author split; not stated explicitly beyond the role
  names.
- **Source:** `[confirmed: user]` interview 2026-07-20, "FEAT-003 user
  management"

### ACT-003 — First-run operator
- **One-line:** Pre-auth actor who bootstraps an unconfigured instance.
- **Goal:** Get a usable instance running — either by creating a new database
  and first admin, or by importing an existing database export.
- **Context:** Acts before any user or database exists; becomes the first
  admin (`ACT-001`) on success.
- **Constraints:** Only available while the instance is unconfigured.
- **Source:** `[confirmed: user]` interview 2026-07-20, "FEAT-001 first-run
  bootstrap"

### ACT-004 — Book owner
- **One-line:** The author who created a book (or received it by transfer);
  controls its skeleton, membership, mode and visibility.
- **Goal:** Build the chapter skeleton, invite/remove co-authors, set
  collaboration mode and visibility, open/close/reopen chapters, archive or
  transfer the book.
- **Context:** A relationship to a specific book, not an account role — one
  ACT-002 Author account may be owner of some books and co-author of others
  at the same time.
- **Constraints:** Cannot destroy a book (archive only, never destroyed);
  ownership recoverable by an admin only if the owner's account is disabled.
- **Source:** `[confirmed: user]` interview 2026-07-20, "ownership,
  membership & visibility" / "book structure — chapters, states, sketches"

### ACT-005 — Co-author
- **One-line:** An author granted access to someone else's book; writes
  within the rules the owner sets.
- **Goal:** Add chapters and edit sketches, write blocks directly (free
  mode) or propose them (proposal mode) in the book's open chapter.
- **Context:** A relationship to a specific book, not an account role — the
  same ACT-002 Author account may be co-author on one book and owner on
  another.
- **Constraints:** Cannot set chapter order, open/close/reopen chapters,
  change visibility, or change collaboration mode — owner-only actions.
- **Source:** `[confirmed: user]` interview 2026-07-20, "ownership,
  membership & visibility"

### ACT-006 — Reader
- **One-line:** A logged-in user reading a public book they are not a
  member of.
- **Goal:** Read a public book's content.
- **Context:** Reaches a book through its visibility setting, not
  membership.
- **Constraints:** Read-only, no authoring access; cannot see a private
  book; must be logged in — no anonymous access.
- **Source:** `[confirmed: user]` interview 2026-07-20, "ownership,
  membership & visibility"; challenge C4
<!-- product-spec:end -->
