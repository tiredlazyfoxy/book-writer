<!-- product-spec:start -->
# Stories — FEAT-007 Membership & visibility

### US-027 — Owner adds a co-author
- **Feature:** FEAT-007 · **Actor:** ACT-004 · **Realizes:** UC-026
- **Status:** delivered
- **Story:** As a book owner, I want to add a co-author, so that they can
  contribute to the book.
- **Acceptance criteria:**
  - **US-027.AC-1** — Given an author account not already a co-author,
    when the owner adds them, then that account gains co-author access to
    the book.
- **Source:** `[confirmed: user]` interview 2026-07-20, "ownership,
  membership & visibility": "Owner adds/removes co-authors."

### US-028 — Owner removes a co-author, content and attribution survive
- **Feature:** FEAT-007 · **Actor:** ACT-004 · **Realizes:** UC-027
- **Status:** delivered
- **Story:** As a book owner, I want to remove a co-author, so that they
  lose access while their contribution stays intact.
- **Acceptance criteria:**
  - **US-028.AC-1** — Given a current co-author, when the owner removes
    them, then their access to the book ends.
  - **US-028.AC-2** — Given a removed co-author's existing edits, when the
    book is viewed afterward, then those edits remain in the chapter.
  - **US-028.AC-3** — Given a removed co-author's existing edits, when the
    book is viewed afterward, then those edits are still attributed to
    them.
  - `_TBD: fate of a removed co-author's pending proposals — not stated_`
- **Source:** `[confirmed: user]` interview 2026-07-20, "ownership,
  membership & visibility": "Content and attribution both stay."

### US-029 — Owner switches a book between private and public
- **Feature:** FEAT-007 · **Actor:** ACT-004 · **Realizes:** UC-028
- **Status:** delivered
- **Story:** As a book owner, I want to set my book's visibility, so that I
  control who can read it.
- **Acceptance criteria:**
  - **US-029.AC-1** — Given a private book, when the owner sets it to
    public, then any logged-in user can open it read-only.
  - **US-029.AC-2** — Given a public book, when the owner sets it to
    private, then only the owner and co-authors can open it.
  - **US-029.AC-3** — Given a reader with a public book open, when the
    owner sets that book private, then the reader's next request for the
    book is refused.
- **Source:** `[confirmed: user]` interview 2026-07-20, "ownership,
  membership & visibility"; challenge C4; interview 2026-07-31,
  "finalization — 022".

### US-030 — Logged-in reader opens a public book read-only
- **Feature:** FEAT-007 · **Actor:** ACT-006 · **Realizes:** UC-029
- **Status:** delivered
- **Story:** As a logged-in reader, I want to open a public book, so that I
  can read it without being a member.
- **Acceptance criteria:**
  - **US-030.AC-1** — Given a public book and a logged-in user who is not a
    member, when they open it, then its content is shown.
  - **US-030.AC-2** — Given a public book and a logged-in user who is not a
    member, when they open it, then no edit action is available to them.
  - **US-030.AC-3** — Given a private book, when a logged-in non-member
    attempts to open it, then access is refused.
  - **US-030.AC-4** — Given a public book, when a user who is not logged in
    attempts to open it, then access is refused.
- **Source:** `[confirmed: user]` interview 2026-07-20, "ownership,
  membership & visibility"; challenge C4: "public = read-only to any
  logged-in user... not anonymous."; interview 2026-07-31, "finalization —
  022".

### US-031 — Co-author sees books shared with them
- **Feature:** FEAT-007 · **Actor:** ACT-005 · **Realizes:** UC-030
- **Status:** delivered
- **Story:** As a co-author, I want to see the books shared with me, so
  that I can find the ones I contribute to but don't own.
- **Acceptance criteria:**
  - **US-031.AC-1** — Given an authenticated co-author, when they open
    their shared-books list, then every book where they are a co-author
    (not owner) is shown.
- **Source:** `[inferred]` interview 2026-07-20, "ownership, membership &
  visibility" — basic access capability, not itself asked.

### US-118 — Reader browses public books they are not a member of
- **Feature:** FEAT-007 · **Actor:** ACT-006 · **Realizes:** UC-100
- **Status:** delivered
- **Story:** As a logged-in reader, I want to see which public books
  exist, so that I can find one to read without being sent a link.
- **Acceptance criteria:**
  - **US-118.AC-1** — Given a public, non-archived book owned by another
    author, when the reader views the public list, then that book is
    shown with its title and description.
  - **US-118.AC-2** — Given a book the reader owns, when they view the
    public list, then that book is absent from it.
  - **US-118.AC-3** — Given a book the reader co-authors, when they view
    the public list, then that book is absent from it.
  - **US-118.AC-4** — Given a private book, when the reader views the
    public list, then that book is absent from it.
  - **US-118.AC-5** — Given an archived public book, when the reader
    views the public list, then that book is absent from it.
  - **US-118.AC-6** — Given an archived public book, when the reader opens
    it by direct link, then it opens read-only.
  - **US-118.AC-7** — Given a book shown in the public list, when the
    reader follows it, then that book's reader view opens.
  - **US-118.AC-8** — Given no public book the reader may browse, when
    they view the public list, then the list states that it is empty.
- **Source:** `[confirmed: user]` interview 2026-07-31, "finalization —
  022"; challenge C-f22-1. AC-2..AC-5 are the four exclusions the
  delivered list enforces; AC-6 records the archive asymmetry resolved as
  a requirement (challenge C-f22-4).
<!-- product-spec:end -->
