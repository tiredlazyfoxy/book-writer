<!-- product-spec:start -->
# Stories — FEAT-017 Codex

### US-078 — Member creates a codex entry of a given kind
- **Feature:** FEAT-017 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-069
- **Status:** proposed
- **Story:** As a book member, I want to create a codex entry of a chosen
  kind, so that I can record a character, location or fact in the book's
  reference volume.
- **Acceptance criteria:**
  - **US-078.AC-1** — Given a member on the book, when they create an entry
    of kind character or location, then the entry is created with a name.
  - **US-078.AC-2** — Given a member on the book, when they create an entry
    of kind fact, then the entry is created with no name.
- **Source:** `[confirmed: user]` interview 2026-07-20, "codex" round 4:
  "Characters and locations are seperated because they have 'names'."; "What
  does having a name buy them functionally? Both — named entries carry
  state-note history AND are name-addressable. Facts do neither."

### US-079 — Codex entries follow the book's collaboration mode
- **Feature:** FEAT-017 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-069,
  UC-070
- **Status:** proposed
- **Story:** As a book member, I want codex entries to follow the book's
  collaboration mode, so that authoring an entry works the same as
  authoring a state note.
- **Acceptance criteria:**
  - **US-079.AC-1** — Given the book is in free mode, when a member creates
    or edits an entry, then the change applies immediately.
  - **US-079.AC-2** — Given the book is in proposal mode, when a co-author
    creates or edits an entry, then the change is held as a proposal until
    the owner applies it.
- **Source:** `[confirmed: user]` interview 2026-07-20, "codex" round 4:
  "Who may create and edit them? Follows the book's collaboration mode (same
  rule as state notes, US-053)."

### US-080 — Member browses and searches the codex
- **Feature:** FEAT-017 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-071
- **Status:** proposed
- **Story:** As a book member, I want to browse and search the codex, so
  that I can find an entry without scanning the whole list.
- **Acceptance criteria:**
  - **US-080.AC-1** — Given the codex has entries, when a member searches
    it, then matching entries are returned.
- **Source:** `[inferred]` interview 2026-07-20, "codex" round 4 — basic
  access capability implied by the codex growing beyond what can be shown
  wholesale (challenge C26); not itself asked.

### US-081 — Member archives a codex entry rather than deleting it
- **Feature:** FEAT-017 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-072
- **Status:** proposed
- **Story:** As a book member, I want to archive a codex entry instead of
  deleting it, so that removed lore stays recoverable.
- **Acceptance criteria:**
  - **US-081.AC-1** — Given an active codex entry, when a member archives
    it, then the entry is removed from active use but not deleted.
  - `_TBD: whether archiving a codex entry can be undone._`
- **Source:** `[confirmed: user]` interview 2026-07-20, "codex" round 4:
  "Archine not delete" [archive not delete].

### US-082 — Member views an entry's edit history
- **Feature:** FEAT-017 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-073
- **Status:** proposed
- **Story:** As a book member, I want to view a codex entry's edit history,
  so that I can see how it changed over time.
- **Acceptance criteria:**
  - **US-082.AC-1** — Given an entry with at least one prior version, when a
    member opens its edit history, then its past versions are shown.
- **Source:** `[confirmed: user]` interview 2026-07-20, "codex" round 4: "we
  keep edit history of every entity."; "View and restore."

### US-083 — Member restores an entry to an earlier version
- **Feature:** FEAT-017 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-074
- **Status:** proposed
- **Story:** As a book member, I want to restore a codex entry to an earlier
  version, so that I can undo an unwanted change.
- **Acceptance criteria:**
  - **US-083.AC-1** — Given an entry's edit history contains an earlier
    version, when a member restores it, then the entry's current content
    becomes that version.
- **Source:** `[confirmed: user]` interview 2026-07-20, "codex" round 4:
  "View and restore."

### US-084 — Member copies codex entries from another book they belong to
- **Feature:** FEAT-017 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-075
- **Status:** proposed
- **Story:** As a book member, I want to copy codex entries from another
  book I belong to, so that I can reuse established lore in a sequel.
- **Acceptance criteria:**
  - **US-084.AC-1** — Given a member belongs to a source and a target book,
    when they copy selected entries from the source, then copies of those
    entries are added to the target book's codex.
  - `_TBD: whether copying entries between books carries their edit
    history._`
- **Source:** `[confirmed: user]` interview 2026-07-20, "codex" round 4:
  "Per book, but we can copy/import/export - kind of for sequels etc.";
  "Copy between books, yes."

### US-085 — The codex is invisible to readers and non-members
- **Feature:** FEAT-017 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-071
- **Status:** proposed
- **Story:** As a book owner, I want the codex hidden from readers and
  non-members, so that behind-the-scenes lore isn't exposed alongside the
  public book.
- **Acceptance criteria:**
  - **US-085.AC-1** — Given a public book, when a reader (ACT-006) or any
    non-member views it, then the codex is not shown to them.
- **Source:** `[confirmed: user]` interview 2026-07-20, "codex" round 4:
  "Can a Reader (ACT-006) of a public book see the codex? No — members
  only."
<!-- product-spec:end -->
