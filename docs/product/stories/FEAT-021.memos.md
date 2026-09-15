<!-- product-spec:start -->
# Stories — FEAT-021 Memos

### US-123 — Author creates a memo and writes in it immediately
- **Feature:** FEAT-021 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-103
- **Status:** proposed
- **Story:** As an author, I want a new memo to be created and immediately
  focused, so that I can start writing without an extra step.
- **Acceptance criteria:**
  - **US-123.AC-1** — Given the author creates a new memo, when it is
    created, then it appends as the last memo in their list.
  - **US-123.AC-2** — Given a newly created memo, when it is created,
    then it receives focus immediately.
  - **US-123.AC-3** — Given a newly created memo, when it is created,
    then it is active.
- **Source:** `[confirmed: user]` interview 2026-09-15, "augment round —
  memos", collected brief: "Last in the list, and immediately focused."

### US-124 — A memo is visible only to its author
- **Feature:** FEAT-021 · **Actor:** ACT-004, ACT-005 · **Realizes:**
  UC-103, UC-109
- **Status:** proposed
- **Story:** As an author, I want my memos visible to nobody else, so
  that I can keep private notes about the book.
- **Acceptance criteria:**
  - **US-124.AC-1** — Given a memo belonging to one member of a book,
    when another member of the same book views the book, then they see
    none of that member's memos.
  - **US-124.AC-2** — Given a memo belonging to a co-author, when the
    book's owner views the book, then they see none of that co-author's
    memos.
- **Source:** `[confirmed: user]` interview 2026-09-15, "augment round —
  memos", collected brief: "Visible ONLY to the memo author — per book
  per user; nobody sees another user's memos."

### US-125 — Author edits a memo in place; it saves when focus leaves
- **Feature:** FEAT-021 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-104
- **Status:** proposed
- **Story:** As an author, I want to edit a memo directly and have it save
  automatically, so that I never lose a note to a forgotten save.
- **Acceptance criteria:**
  - **US-125.AC-1** — Given an open memo, when the author edits its body
    and focus leaves the memo, then the edited body is saved.
  - **US-125.AC-2** — Given an open memo being edited, when focus has not
    yet left it, then no explicit save control is present.
- **Source:** `[confirmed: user]` interview 2026-09-15, "augment round —
  memos", collected brief: "In place, saved immediately on focus lost."

### US-126 — Author reorders memos by dragging and by arrows
- **Feature:** FEAT-021 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-105
- **Status:** proposed
- **Story:** As an author, I want to reorder my memos by dragging or by
  arrows, so that I can control the order they reach the assistant in.
- **Acceptance criteria:**
  - **US-126.AC-1** — Given two or more memos in the author's list, when
    the author drags one to a new position, then the list reflects the
    new order.
  - **US-126.AC-2** — Given two or more memos in the author's list, when
    the author uses an arrow control on one, then it moves one position
    in that direction.
- **Source:** `[confirmed: user]` interview 2026-09-15, "augment round —
  memos", collected brief: "Reorderable by drag-and-drop and by arrows."

### US-127 — Author switches a memo off without losing it
- **Feature:** FEAT-021 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-106
- **Status:** proposed
- **Story:** As an author, I want to switch a memo off without deleting
  it, so that I can pause its use without losing it.
- **Acceptance criteria:**
  - **US-127.AC-1** — Given an active memo, when the author switches it
    off, then it stays in the list.
  - **US-127.AC-2** — Given an active memo, when the author switches it
    off, then it is visibly marked off.
  - **US-127.AC-3** — Given an inactive memo, when the assistant is given
    context for a run, then that memo is excluded.
  - **US-127.AC-4** — Given an inactive memo, when the author switches it
    on, then it is included in context again.
  - **US-127.AC-5** — Given the author's only active memo, when they
    switch it off, then the switch succeeds and the author has no active
    memo.
- **Source:** `[confirmed: user]` interview 2026-09-15, "augment round —
  memos", challenges C2, C9.

### US-128 — Author archives a memo and can restore it
- **Feature:** FEAT-021 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-107
- **Status:** proposed
- **Story:** As an author, I want to archive a memo I no longer need on
  the list and restore it later, so that nothing is ever permanently
  lost.
- **Acceptance criteria:**
  - **US-128.AC-1** — Given a memo in the author's list, when they
    archive it, then it leaves the working list.
  - **US-128.AC-2** — Given an archived memo, when the author restores
    it, then it returns to the working list.
  - **US-128.AC-3** — Given a memo, when the author opens its header,
    then it offers archive and no delete.
- **Source:** `[confirmed: user]` interview 2026-09-15, "augment round —
  memos", challenge C7.

### US-129 — Author asks the assistant to create a memo
- **Feature:** FEAT-021 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-108
- **Status:** proposed
- **Story:** As an author, I want to ask the assistant to create a memo
  for me, so that I don't have to switch to the list to write it myself.
- **Acceptance criteria:**
  - **US-129.AC-1** — Given the author directly asks the assistant to
    create a memo, when the assistant does so, then a new memo exists in
    the author's list.
  - **US-129.AC-2** — Given the author directly asks the assistant to
    create a memo, when the assistant does so, then the new memo is
    active.
  - **US-129.AC-3** — Given the author directly asks the assistant to
    create a memo, when the assistant does so, then the new memo is at
    the end of the list.
  - **US-129.AC-4** — Given no memos list is open, when the author asks
    the assistant to create a memo, then it is created anyway.
  - **US-129.AC-5** — Given the current mode is not granted the
    create-memo tool, when the author asks the assistant to create a
    memo, then the request is refused, visibly.
- **Source:** `[confirmed: user]` interview 2026-09-15, "augment round —
  memos", collected brief: "by the AI via a 'create memo' tool to be
  added."

### US-130 — The assistant creates no memo unasked
- **Feature:** FEAT-021 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-108
- **Status:** proposed
- **Story:** As an author, I want the assistant to never create a memo I
  didn't ask for, so that my memo list only ever holds what I intended.
- **Acceptance criteria:**
  - **US-130.AC-1** — Given the author has not asked for a memo to be
    created, when the assistant identifies something that could warrant
    one, then no memo is created.
- **Note:** Enforced by the mode's seeded prompt guidance, not
  structurally — an administrator who rewrites the prompt can weaken it.
  Mirrors US-121.AC-3's Note.
- **Source:** `[confirmed: user]` interview 2026-09-15, "augment round —
  memos", challenge C3 (US-121.AC-3 precedent).

### US-131 — Every active memo reaches the assistant, in the author's order
- **Feature:** FEAT-021 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-109
- **Status:** proposed
- **Story:** As an author, I want every active memo to reach the
  assistant in the order I set, so that what I told it to remember
  arrives the way I organized it.
- **Acceptance criteria:**
  - **US-131.AC-1** — Given the author's set of active memos, when the
    assistant runs, then every one of them is present in its context.
  - **US-131.AC-2** — Given the author's chosen order of active memos,
    when the assistant receives them, then it receives them in that
    order.
  - **US-131.AC-3** — Given an inactive or archived memo, when the
    assistant runs, then it is not present in its context.
- **Source:** `[confirmed: user]` interview 2026-09-15, "augment round —
  memos", collected brief; challenge CP3 — narrowed statement only; where
  the memo block sits relative to chapter text, summaries or state notes
  is not asserted here (see `vision.md`).

### US-132 — Memos reach every mode and every sub-agent
- **Feature:** FEAT-021 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-109
- **Status:** proposed
- **Story:** As an author, I want my active memos to reach the assistant
  no matter which mode I'm in or whether it delegates to a sub-agent, so
  that my standing notes are never silently dropped.
- **Acceptance criteria:**
  - **US-132.AC-1** — Given the author's active memos, when the assistant
    runs in any of FEAT-020's five modes, then they are present in that
    run's context.
  - **US-132.AC-2** — Given the author's active memos, when the assistant
    delegates a task to a sub-agent, then they are present in the
    sub-agent's context too.
- **Source:** `[confirmed: user]` interview 2026-09-15, "augment round —
  memos", challenge C6.
<!-- product-spec:end -->
