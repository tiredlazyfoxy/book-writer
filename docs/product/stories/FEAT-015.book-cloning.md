<!-- product-spec:start -->
# Stories — FEAT-015 Book cloning

### US-066 — Owner clones a book
- **Feature:** FEAT-015 · **Actor:** ACT-004 · **Realizes:** UC-061
- **Status:** proposed
- **Story:** As a book owner, I want to clone my book, so that I can
  explore an alternative storyline without disturbing the original.
- **Acceptance criteria:**
  - **US-066.AC-1** — Given a book the owner owns, when they clone it, then
    a new independent book is created with the owner as its owner.
- **Source:** `[confirmed: user]` interview 2026-07-20, "book cloning": "if
  we need fully new storyline — we can 'clone' and then re-do the story."

### US-067 — A clone is fully independent of its source
- **Feature:** FEAT-015 · **Actor:** ACT-004 · **Realizes:** UC-061
- **Status:** proposed
- **Story:** As a book owner, I want a clone to be fully independent of
  its source, so that changes in one book never affect the other.
- **Acceptance criteria:**
  - **US-067.AC-1** — Given a book has been cloned, when either the source
    or the clone is later edited, then the edit appears only in the book
    it was made in.
- **Source:** `[confirmed: user]` interview 2026-07-20, "book cloning":
  "Fully independent. No link, no sync, no comparison."

### US-068 — Co-author clones a public book and becomes its owner
- **Feature:** FEAT-015 · **Actor:** ACT-005 · **Realizes:** UC-062
- **Status:** proposed
- **Story:** As a co-author, I want to clone a public book I contribute
  to, so that I can own and continue my own version.
- **Acceptance criteria:**
  - **US-068.AC-1** — Given a co-author on a public book, when they clone
    it, then a new independent book is created with the cloning co-author
    as its owner.
- **Source:** `[confirmed: user]` interview 2026-07-20, "book cloning":
  "they become the owner."

### US-069 — Only the owner may clone a private book
- **Feature:** FEAT-015 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-062
- **Status:** proposed
- **Story:** As a book owner, I want only me to be able to clone my
  private book, so that my private content can't be copied out without my
  say.
- **Acceptance criteria:**
  - **US-069.AC-1** — Given a private book, when a co-author (not the
    owner) attempts to clone it, then the clone is refused.
- **Source:** `[confirmed: user]` interview 2026-07-20, "book cloning":
  "Only the owner can clone a private book."; challenge C21.

### US-070 — The cloner chooses which members carry over
- **Feature:** FEAT-015 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-063
- **Status:** proposed
- **Story:** As a cloner, I want to choose which members carry over to my
  clone, so that I control who has access to my new book.
- **Acceptance criteria:**
  - **US-070.AC-1** — Given a clone being created, when the cloner selects
    a subset of members to carry over, then only the selected members are
    added to the clone.
  - **US-070.AC-2** — Given a clone being created, when the cloner selects
    no members, then the clone has only the cloner as a member.
- **Source:** `[confirmed: user]` interview 2026-07-20, "book cloning": "it
  clones the members (optional, or not all)."

### US-071 — A clone carries content, continuity, mode and visibility
- **Feature:** FEAT-015 · **Actor:** ACT-004 · **Realizes:** UC-061
- **Status:** proposed
- **Story:** As a book owner, I want a clone to carry over its content and
  settings, so that I don't have to rebuild the book from scratch.
- **Acceptance criteria:**
  - **US-071.AC-1** — Given a book is cloned, when the clone is created,
    then it contains the source's chapters, blocks and sketches as of the
    clone time.
  - **US-071.AC-2** — Given a book is cloned, when the clone is created,
    then it contains the source's state notes and summaries as of the
    clone time.
  - **US-071.AC-3** — Given a book is cloned, when the clone is created,
    then it has the same collaboration mode as the source.
  - **US-071.AC-4** — Given a book is cloned, when the clone is created,
    then it has the same visibility setting as the source.
- **Source:** `[confirmed: user]` interview 2026-07-20, "book cloning":
  "Chapters, blocks and sketches · state notes and summaries · membership
  · collaboration mode and visibility."

### US-094 — A clone carries the source book's codex
- **Feature:** FEAT-015 · **Actor:** ACT-004 · **Realizes:** UC-061
- **Status:** proposed
- **Story:** As a book owner, I want my clone to carry the source book's
  codex, so that characters, locations and facts don't have to be rebuilt.
- **Acceptance criteria:**
  - **US-094.AC-1** — Given a book with codex entries is cloned, when the
    clone is created, then it contains copies of the source's codex
    entries as of the clone time.
- **Source:** `[inferred]` codex round 4 — the codex is per-book content
  (FEAT-017), consistent with the round-3 carry-over list (US-071); not
  separately asked.
<!-- product-spec:end -->
