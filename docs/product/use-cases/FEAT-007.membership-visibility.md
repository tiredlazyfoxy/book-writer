<!-- product-spec:start -->
# Use Cases — FEAT-007 Membership & visibility

### UC-026 — Add a co-author
- **Feature:** FEAT-007 · **Actor:** ACT-004
- **Preconditions:** Owner authenticated; book exists.
- **Main flow:**
  1. Owner selects an author account to add.
  2. Owner confirms.
  3. System grants that account co-author access to the book.
- **Postconditions:** Selected account is now a co-author of the book.
- **Source:** `[confirmed: user]` interview 2026-07-20, "ownership,
  membership & visibility": "Owner adds/removes co-authors."

### UC-027 — Remove a co-author
- **Feature:** FEAT-007 · **Actor:** ACT-004
- **Preconditions:** Owner authenticated; target is a current co-author.
- **Main flow:**
  1. Owner selects a co-author to remove.
  2. Owner confirms removal.
  3. System revokes that account's access to the book.
- **Exception flow:** Target is the book's only co-author → `[inferred]`
  removal proceeds; the book continues with just the owner (ownership is
  independent of co-author count; not separately confirmed). Target has
  pending proposals (proposal mode) at the time of removal →
  `_TBD: fate of a removed co-author's pending proposals — not stated_`.
- **Postconditions:** Co-author's access revoked; their existing edits and
  attribution remain in the book.
- **Source:** `[confirmed: user]` interview 2026-07-20, "ownership,
  membership & visibility": "Content and attribution both stay."; interview
  2026-07-30, "finalization — 021 + 014 + 015" (formerly "block", now
  "edit")

### UC-028 — Set book visibility (private / public)
- **Feature:** FEAT-007 · **Actor:** ACT-004
- **Preconditions:** Owner authenticated; book exists.
- **Main flow:**
  1. Owner selects private or public visibility.
  2. System applies the visibility setting.
- **Exception flow:** Book switched from public to private while a reader
  currently has it open → the reader's next request for the book or any of
  its chapters is refused; what they have already been shown is not
  withdrawn. There is no notification to the reader and no live
  invalidation of an open view. `[confirmed: user]` interview 2026-07-31,
  "finalization — 022".
- **Postconditions:** Private = owner + co-authors only; public = read-only
  to any logged-in user. Only the owner may clone a private book — see
  FEAT-015.
- **Source:** `[confirmed: user]` interview 2026-07-20, "ownership,
  membership & visibility"; challenge C4; interview 2026-07-31,
  "finalization — 022".

### UC-029 — Read a public book
- **Feature:** FEAT-007 · **Actor:** ACT-006
- **Preconditions:** Book visibility is public; reader is logged in and not
  a member of the book.
- **Main flow:**
  1. Reader opens the book.
  2. System shows the book's table of contents — the titles of the book's
     **written** chapters, in reading order, each linking to that
     chapter's text. Chapters that have not been written are never
     listed, and a chapter's sketch is never shown to a reader through any
     surface. `[confirmed: user]` interview 2026-07-31, "finalization —
     022"; challenge C-f22-2.
  3. Reader selects a chapter.
  4. System returns that chapter's text, read-only.
- **Exception flow:** Book is private → access refused. Reader is not
  logged in (anonymous) → access refused; no anonymous surface exists. A
  visitor who arrives at the reader surface is sent to log in rather than
  shown a refusal page. Chapter is in the middle of being closed when the
  reader looks → it is transiently absent from the table of contents and
  a link to it is refused, until the close completes; it then reappears.
  Accepted deliberately — no reader-facing information is disclosed by
  the gap. `[confirmed: user]` interview 2026-07-31, "finalization —
  022"; challenge C-f22-3.
- **Postconditions:** None (read-only); reader cannot modify content.
  Nothing beyond the table of contents and chapter text is shown — no
  codex (FEAT-017), state notes, flags, book-state view, settings or chat;
  the book's codex is never included, members-only even on a public book.
  Public books **are** discoverable — a logged-in reader browses them; see
  UC-100. (Resolved 2026-07-31; this `_TBD:` was closed by delivery, and
  the requirement is specified retroactively — challenge C-f22-1.)
- **Note:** "Table of contents" is the domain term for the reader-facing
  chapter index (chosen 2026-07-23 over "glossary", which collided with
  this product-spec's own `glossary.md`). Resolved 2026-07-31 — the table
  of contents stays a facet of UC-029; the recorded default was upheld and
  no new id was minted.
- **Source:** `[confirmed: user]` interview 2026-07-20, "ownership,
  membership & visibility"; challenge C4: "public = read-only to any
  logged-in user... not anonymous." Codex exclusion: `[confirmed: user]`
  interview 2026-07-20, "codex" round 4: "Can a Reader (ACT-006) of a
  public book see the codex? No — members only." Table of contents /
  scope: `[confirmed: user]` interview 2026-07-23, "Augment round 5", "SPA
  pages — the plain surfaces around the working page", "Reader mode
  (ACT-006)": "the book by chapters (read chapter text, read-only) + a
  chapter index (chapter names with links); nothing more — no codex /
  notes / flags / book-state / settings / chat." Finalization,
  2026-07-31, "finalization — 022"; challenges C-f22-1, C-f22-2, C-f22-3.

### UC-030 — List books shared with me
- **Feature:** FEAT-007 · **Actor:** ACT-005
- **Preconditions:** Co-author authenticated.
- **Main flow:**
  1. Co-author opens their shared-books list.
  2. System returns books where they are a co-author, not owner.
- **Postconditions:** None (read-only).
- **Source:** `[inferred]` interview 2026-07-20, "ownership, membership &
  visibility" — a basic access capability implied by having memberships;
  not itself asked.

### UC-100 — Browse public books
- **Feature:** FEAT-007 · **Actor:** ACT-006
- **Preconditions:** Reader is logged in.
- **Main flow:**
  1. Reader opens their bookshelf.
  2. System lists the public books the reader neither owns nor co-authors,
     each by title and description.
  3. Reader selects one.
  4. System opens that book's reader view (UC-029).
- **Alternate flow:** No such book exists → the list states that it is
  empty, rather than showing an empty area.
- **Postconditions:** None (read-only). The listing carries a book's title
  and description only — nothing about its owner, its members, its state
  or its collaboration mode.
- **Note:** An **archived** public book is absent from the listing but
  still opens by direct link — archiving withdraws a book from discovery
  without revoking read access, consistent with UC-023's archive being
  preserved and reversible (challenge C-f22-4). The listing deliberately
  carries no owner identity; search, filter, sort and pagination are not
  required and none is claimed (challenge C-f22-5).
- **Source:** `[confirmed: user]` interview 2026-07-31, "finalization —
  022"; challenge C-f22-1. Specified retroactively — the behaviour was
  built in plan `022` before it was specified; the disposition is
  recorded rather than erased.
<!-- product-spec:end -->
