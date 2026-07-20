<!-- product-spec:start -->
# Stories — FEAT-009 Chapter writing in blocks

### US-036 — Owner opens a chapter for writing
- **Feature:** FEAT-009 · **Actor:** ACT-004 · **Realizes:** UC-035
- **Status:** proposed
- **Story:** As a book owner, I want to open a planned chapter, so that
  writing can begin on it.
- **Acceptance criteria:**
  - **US-036.AC-1** — Given a chapter in the planned state and no chapter
    currently open, when the owner opens it, then the chapter's state
    becomes open.
  - **US-036.AC-2** — Given a co-author (not the owner), when they attempt
    to open a chapter, then the action is refused.
- **Source:** `[confirmed: user]` interview 2026-07-20, "book structure —
  chapters, states, sketches": "Owner only."

### US-037 — Only one chapter can be open at a time
- **Feature:** FEAT-009 · **Actor:** ACT-004 · **Realizes:** UC-035
- **Status:** proposed
- **Story:** As a book owner, I want the system to enforce a single open
  chapter, so that writing stays serial and coordinated.
- **Acceptance criteria:**
  - **US-037.AC-1** — Given any sequence of open/close/reopen actions, when
    the book's chapters are inspected, then at most one chapter is in the
    open state.
  - `_TBD: whether opening a chapter while another is already open is
    refused or auto-closes the other — not stated_`
- **Source:** `[confirmed: user]` interview 2026-07-20, "book structure —
  chapters, states, sketches": "At most one open chapter per book."

### US-038 — Owner closes the open chapter
- **Feature:** FEAT-009 · **Actor:** ACT-004 · **Realizes:** UC-036
- **Status:** proposed
- **Story:** As a book owner, I want to close the open chapter, so that it
  becomes final and no longer editable.
- **Acceptance criteria:**
  - **US-038.AC-1** — Given an open chapter, when the owner closes it, then
    the chapter's state becomes closed and it is no longer editable.
  - **US-038.AC-2** — Given a co-author, when they attempt to close the
    open chapter, then the action is refused.
  - **US-038.AC-3** — Given an open chapter whose summary or state-note
    changeset is not approved, when the owner attempts to close it, then
    the close is refused and the chapter remains open.
- **Source:** `[confirmed: user]` interview 2026-07-20, "book structure —
  chapters, states, sketches": "closed (written, not editable)." AC-3 —
  `[confirmed: user]` interview 2026-07-20, "Augment round 2", "summaries &
  state notes": "Approval required to close."; challenge C17 (FEAT-012).

### US-039 — Owner reopens a closed chapter
- **Feature:** FEAT-009 · **Actor:** ACT-004 · **Realizes:** UC-037
- **Status:** proposed
- **Story:** As a book owner, I want to reopen a closed chapter, so that I
  can revise it even after moving on.
- **Acceptance criteria:**
  - **US-039.AC-1** — Given a closed chapter and no chapter currently open,
    when the owner reopens it, then its state becomes open.
  - **US-039.AC-2** — Given a closed chapter and a different chapter
    currently open, when the owner reopens the closed one, then the
    previously open chapter becomes closed and the reopened one becomes
    open.
- **Note:** Editing the reopened chapter creates a variant — see FEAT-014.
- **Source:** `[confirmed: user]` interview 2026-07-20, "book structure —
  chapters, states, sketches": "Reopening a chapter implies closing the
  currently-open one."

### US-040 — Co-author adds a block in free mode
- **Feature:** FEAT-009 · **Actor:** ACT-005 · **Realizes:** UC-038
- **Status:** proposed
- **Story:** As a co-author, I want to add a block directly to the open
  chapter in free mode, so that my contribution lands immediately.
- **Acceptance criteria:**
  - **US-040.AC-1** — Given a chapter open and the book in free mode, when
    a co-author saves a new block, then the block is added to the open
    chapter immediately.
  - **US-040.AC-2** — Given a chapter open and the book in free mode, when
    a co-author saves a new block, then the block is attributed to them.
  - **US-040.AC-3** — Given no chapter is open, when a member attempts to
    add a block, then the add is refused.
  - **US-040.AC-4** — Given two members add different blocks to the open
    chapter at the same time, when both saves complete, then both blocks
    exist in the chapter.
- **Source:** `[confirmed: user]` interview 2026-07-20, "writing — blocks &
  concurrency": "the process of the chapter writing is... by some blocks."
  `_TBD: what a block contains (format, length, structure)._`

### US-041 — Concurrent edits to the same block warn the second author
- **Feature:** FEAT-009 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-039
- **Status:** proposed
- **Story:** As a book member, I want to be warned when the block I'm
  editing changed underneath me, so that I don't silently overwrite
  someone else's work.
- **Acceptance criteria:**
  - **US-041.AC-1** — Given a block that a second member is editing, when
    another member's save to the same block completes first, then the
    second member is warned the block changed underneath them before their
    save is accepted.
  - **US-041.AC-2** — Given a warned member chooses to overwrite, when they
    save, then their version becomes the block's current version.
  - **US-041.AC-3** — Given a warned member chooses to abandon, when they
    discard their edit, then the block keeps the version already saved by
    the other member.
- **Source:** `[confirmed: user]` interview 2026-07-20, "writing — blocks &
  concurrency": "warn-then-later-write-wins rule applies only when two
  co-authors edit the same block."
<!-- product-spec:end -->
