<!-- product-spec:start -->
# Stories — FEAT-008 Chapter skeleton & sketches

### US-032 — Member adds a chapter to the skeleton
- **Feature:** FEAT-008 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-031
- **Status:** delivered
- **Story:** As a book member, I want to add a chapter with a sketch, so
  that I can grow the book's skeleton ahead of writing.
- **Acceptance criteria:**
  - **US-032.AC-1** — Given an authenticated member of the book, when they
    add a chapter with a sketch, then a new chapter exists in the planned
    state with that sketch.
- **Source:** `[confirmed: user]` interview 2026-07-20, "book structure —
  chapters, states, sketches": "Any member adds, owner orders." Delivered:
  `docs/plans/014.chapter-skeleton/` (2026-07-30).

### US-033 — Owner reorders chapters
- **Feature:** FEAT-008 · **Actor:** ACT-004 · **Realizes:** UC-032
- **Status:** delivered
- **Story:** As a book owner, I want to set the chapter order, so that the
  skeleton reads front-to-back the way I intend.
- **Acceptance criteria:**
  - **US-033.AC-1** — Given a book with two or more chapters, when the
    owner sets a new chapter order, then the skeleton reflects that order.
  - **US-033.AC-2** — Given a co-author (not the owner), when they attempt
    to reorder chapters, then the action is refused.
- **Source:** `[confirmed: user]` interview 2026-07-20, "book structure —
  chapters, states, sketches": "owner orders." Delivered:
  `docs/plans/014.chapter-skeleton/` (2026-07-30); AC-2 (owner-only
  reorder) confirmed delivered.

### US-034 — Member edits the sketch of a planned chapter
- **Feature:** FEAT-008 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-033
- **Status:** delivered
- **Story:** As a book member, I want to edit the sketch of any planned
  chapter, so that co-authors can build the skeleton in parallel.
- **Acceptance criteria:**
  - **US-034.AC-1** — Given a chapter in the planned state, when a member
    edits its sketch, then the sketch is updated.
  - **US-034.AC-2** — Given a chapter that is open or closed, when a member
    attempts to edit its sketch, then the edit is refused.
- **Source:** `[confirmed: user]` interview 2026-07-20, "book structure —
  chapters, states, sketches": "Any co-author may edit the sketch of any
  unwritten chapter, in parallel." Delivered:
  `docs/plans/014.chapter-skeleton/` (2026-07-30).

### US-035 — Member removes a planned chapter
- **Feature:** FEAT-008 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-034
- **Status:** delivered
- **Story:** As a book member, I want to remove a planned chapter, so that
  I can prune the skeleton before it's written.
- **Acceptance criteria:**
  - **US-035.AC-1** — Given a chapter in the planned state, when a member
    removes it, then it no longer appears in the skeleton.
  - **US-035.AC-2** — Given a chapter that is open or closed, when a member
    attempts to remove it, then the removal is refused.
- **Source:** `[inferred]` interview 2026-07-20, "book structure —
  chapters, states, sketches" — removal permission mirrors add; not
  separately confirmed. Delivered: `docs/plans/014.chapter-skeleton/`
  (2026-07-30).
<!-- product-spec:end -->
