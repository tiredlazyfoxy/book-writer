<!-- product-spec:start -->
# Stories — FEAT-006 Book lifecycle & ownership

### US-022 — Author creates a book and becomes its owner
- **Feature:** FEAT-006 · **Actor:** ACT-002 · **Realizes:** UC-021
- **Status:** proposed
- **Story:** As an author, I want to create a book with a collaboration
  mode and visibility, so that I become its owner and can start building
  it.
- **Acceptance criteria:**
  - **US-022.AC-1** — Given an authenticated author, when they submit a
    book with a chosen collaboration mode and visibility, then a book is
    created with that mode and visibility.
  - **US-022.AC-2** — Given an authenticated author submitting a new book,
    when the book is created, then that author becomes its owner.
- **Source:** `[confirmed: user]` interview 2026-07-20, "ownership,
  membership & visibility" / "collaboration mode"

### US-023 — Author sees the books they own
- **Feature:** FEAT-006 · **Actor:** ACT-004 · **Realizes:** UC-022
- **Status:** proposed
- **Story:** As a book owner, I want to see the books I own, so that I can
  find and manage them.
- **Acceptance criteria:**
  - **US-023.AC-1** — Given an authenticated owner, when they open their
    book list, then every book they own is shown.
- **Source:** `[inferred]` interview 2026-07-20, "ownership, membership &
  visibility" — basic access capability, not itself asked.

### US-024 — Owner archives a book
- **Feature:** FEAT-006 · **Actor:** ACT-004 · **Realizes:** UC-023
- **Status:** proposed
- **Story:** As a book owner, I want to archive a book, so that I can shelve
  it without losing its content.
- **Acceptance criteria:**
  - **US-024.AC-1** — Given a book that is not archived, when the owner
    archives it, then its status becomes archived.
  - **US-024.AC-2** — Given a book that is not archived, when the owner
    archives it, then its content is preserved.
  - `_TBD: outcome when a book with an open chapter is archived — not
    stated_`
- **Source:** `[confirmed: user]` interview 2026-07-20, "ownership,
  membership & visibility": "Archive only, no hard delete."

### US-025 — Owner transfers a book to a co-author
- **Feature:** FEAT-006 · **Actor:** ACT-004 · **Realizes:** UC-024
- **Status:** proposed
- **Story:** As a book owner, I want to transfer ownership to a co-author,
  so that the book can change lead author or I can step away.
- **Acceptance criteria:**
  - **US-025.AC-1** — Given a co-author of the book, when the owner
    transfers ownership to them, then that co-author becomes the book's
    owner.
  - `_TBD: outcome when the transfer target is not a current co-author —
    not stated_`
- **Source:** `[confirmed: user]` interview 2026-07-20, "ownership,
  membership & visibility": "ownership can be transferred."

### US-026 — Admin restores ownership of an orphaned book
- **Feature:** FEAT-006 · **Actor:** ACT-001 · **Realizes:** UC-025
- **Status:** proposed
- **Story:** As an admin, I want to reassign ownership of a book whose
  owner's account is disabled, so that the book outlives its account.
- **Acceptance criteria:**
  - **US-026.AC-1** — Given a book whose owner's account is disabled, when
    the admin reassigns ownership to another account, then that account
    becomes the book's owner.
  - **US-026.AC-2** — Given a book whose owner's account is still active,
    when the admin attempts to reassign ownership, then the reassignment
    is refused.
- **Source:** `[inferred]` — derived from FEAT-003's disable-not-delete rule
  combined with transferable ownership (interview 2026-07-20, "ownership,
  membership & visibility"); admin reassignment of a disabled owner's book,
  including refusal while the owner is still active, was never itself asked
  in the interview.
<!-- product-spec:end -->
