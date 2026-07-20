<!-- product-spec:start -->
# Stories — FEAT-012 Chapter summaries & state notes

### US-049 — Continuity data is drafted when a chapter closes
- **Feature:** FEAT-012 · **Actor:** ACT-004 · **Realizes:** UC-047
- **Status:** proposed
- **Story:** As a book owner, I want the chapter's summary and state-note
  changes drafted automatically when I close it, so that I don't write
  continuity data from scratch.
- **Acceptance criteria:**
  - **US-049.AC-1** — Given the owner initiates closing a chapter, when the
    close begins, then the system produces a draft summary of the chapter.
  - **US-049.AC-2** — Given the owner initiates closing a chapter, when the
    close begins, then the system produces a draft state-note changeset
    (notes added, modified, deleted) for the chapter.
- **Source:** `[confirmed: user]` interview 2026-07-20, "Augment round 2",
  "summaries & state notes": "LLM proposes, owner approves. On closing a
  chapter the system drafts them."

### US-050 — Owner approves a chapter's summary and state-note changes
- **Feature:** FEAT-012 · **Actor:** ACT-004 · **Realizes:** UC-048
- **Status:** proposed
- **Story:** As a book owner, I want to review, edit and approve the
  drafted summary and state notes, so that continuity data reflects what
  actually happened.
- **Acceptance criteria:**
  - **US-050.AC-1** — Given a drafted summary or state-note changeset, when
    the owner edits it, then the edited version replaces the draft.
  - **US-050.AC-2** — Given a reviewed summary and state-note changeset,
    when the owner approves, then the chapter's continuity data is marked
    approved.
- **Source:** `[confirmed: user]` interview 2026-07-20, "Augment round 2",
  "summaries & state notes": "the owner reviews, edits and accepts."

### US-051 — A chapter cannot close without approved continuity data
- **Feature:** FEAT-012 · **Actor:** ACT-004 · **Realizes:** UC-048
- **Status:** proposed
- **Story:** As a book owner, I want closing blocked until continuity data
  is approved, so that every closed chapter has complete, checked
  continuity.
- **Acceptance criteria:**
  - **US-051.AC-1** — Given a chapter whose summary or state-note changeset
    is not approved, when the owner attempts to close it, then the close
    is refused and the chapter remains open.
- **Source:** `[confirmed: user]` interview 2026-07-20, "Augment round 2",
  "summaries & state notes": "Approval required to close... The closed
  chapter is closed. All summaries are done, all notes are taken."

### US-052 — Member views the book's current state notes
- **Feature:** FEAT-012 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-049
- **Status:** proposed
- **Story:** As a book member, I want to view the current state notes, so
  that I know what's currently true before writing.
- **Acceptance criteria:**
  - **US-052.AC-1** — Given the book has state notes, when a member opens
    the state-notes view, then the current live set is shown.
- **Source:** `[confirmed: user]` interview 2026-07-20, "Augment round 2",
  "summaries & state notes": "There is one live set of state notes...
  Chapter N sees current truth."

### US-053 — Member edits state notes according to the collaboration mode
- **Feature:** FEAT-012 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-050
- **Status:** proposed
- **Story:** As a book member, I want to edit state notes under the book's
  collaboration mode, so that changes follow the same rules as block
  writing.
- **Acceptance criteria:**
  - **US-053.AC-1** — Given the book is in free mode, when a member adds,
    modifies or deletes a state note, then the change applies to the live
    set immediately.
  - **US-053.AC-2** — Given the book is in proposal mode, when a co-author
    adds, modifies or deletes a state note, then the change is held as a
    proposal until the owner applies it.
- **Source:** `[confirmed: user]` interview 2026-07-20, "Augment round 2",
  "summaries & state notes": "Follows the book's collaboration mode."

### US-054 — Member views what a chapter changed in the state notes
- **Feature:** FEAT-012 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-051
- **Status:** proposed
- **Story:** As a book member, I want to see which state notes a chapter
  added, modified or deleted, so that I can trace when a fact changed.
- **Acceptance criteria:**
  - **US-054.AC-1** — Given a chapter with a recorded state-note changeset,
    when a member views that chapter's changeset, then the notes it added,
    modified and deleted are shown.
- **Source:** `[confirmed: user]` interview 2026-07-20, "Augment round 2",
  "summaries & state notes": "each chapter records which notes it added,
  modified or deleted."

### US-055 — Reopening a chapter marks its continuity data stale
- **Feature:** FEAT-012 · **Actor:** ACT-004 · **Realizes:** UC-052
- **Status:** proposed
- **Story:** As a book owner, I want a reopened chapter's continuity data
  flagged stale, so that I know to re-check it before closing again.
- **Acceptance criteria:**
  - **US-055.AC-1** — Given a closed chapter with approved continuity data,
    when the owner reopens it, then its summary and state-note changeset
    are flagged stale.
  - **US-055.AC-2** — Given a chapter flagged stale, when the owner
    attempts to close it again without re-approving, then the close is
    refused (per US-051).
- **Note:** Whether the staleness cascades to later chapters' changesets is
  checked by FEAT-016's consistency check (US-072/US-073), not by these
  criteria — see FEAT-016.
- **Source:** `[confirmed: user]` interview 2026-07-20, "Augment round 2",
  "summaries & state notes": "Flagged stale, owner must re-confirm."

### US-090 — A state note names the codex entry it is about
- **Feature:** FEAT-012 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-079
- **Status:** proposed
- **Story:** As a book member, I want to name the codex entry a state note
  is about, so that the note's change is traceable to a stable identity.
- **Acceptance criteria:**
  - **US-090.AC-1** — Given a named codex entry exists, when a member writes
    or edits a state note about it, then the note carries a reference to
    that entry.
- **Source:** `[confirmed: user]` interview 2026-07-20, "codex" round 4: "A
  state note may reference a codex entry."
<!-- product-spec:end -->
