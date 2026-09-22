<!-- product-spec:start -->
# Use Cases — FEAT-017 Codex

### UC-069 — Create a codex entry
- **Feature:** FEAT-017 · **Actor:** ACT-004, ACT-005
- **Preconditions:** Member is on the book.
- **Main flow:**
  1. Member chooses an entry kind: character, location or fact.
  2. Member enters the entry's content.
  3. Free mode: system adds the entry to the codex immediately.
  4. Proposal mode: system holds the entry as a proposal until the owner
     applies it (FEAT-010 mechanism).
- **Postconditions:** Entry exists in the codex, of the chosen kind, per the
  book's collaboration mode. Character and location entries are named and
  addressable; fact entries are neither.
- **Source:** `[confirmed: user]` interview 2026-07-20, "codex" round 4: "the
  characters, locations, and just lore facts... Editable directly."; "Follows
  the book's collaboration mode (same rule as state notes, US-053)."

### UC-070 — Edit a codex entry
- **Feature:** FEAT-017 · **Actor:** ACT-004, ACT-005
- **Preconditions:** Entry exists, not archived.
- **Main flow:**
  1. Member selects an entry.
  2. Member changes its content.
  3. Free mode: system applies the change immediately.
  4. Proposal mode: system holds the change as a proposal until the owner
     applies it.
- **Postconditions:** Entry's content reflects the applied change (free mode)
  or holds a pending proposal (proposal mode); the prior version is retained
  in the entry's edit history (UC-073).
- **Source:** `[confirmed: user]` interview 2026-07-20, "codex" round 4:
  "Editable directly."; "we keep edit history of every entity."

### UC-071 — Browse and search the codex
- **Feature:** FEAT-017 · **Actor:** ACT-004, ACT-005
- **Preconditions:** Member is on the book.
- **Main flow:**
  1. Member opens the book's codex.
  2. Member searches or filters by kind.
  3. System returns matching entries.
- **Postconditions:** None (read-only).
- **Source:** `[inferred]` interview 2026-07-20, "codex" round 4 — a browse/
  search surface is implied by the codex growing beyond what can be shown
  wholesale (challenge C26); not itself asked.

### UC-072 — Archive a codex entry
- **Feature:** FEAT-017 · **Actor:** ACT-004, ACT-005
- **Preconditions:** Entry exists, not already archived.
- **Main flow:**
  1. Member selects an entry to archive.
  2. Member confirms.
  3. System archives the entry; it is not deleted.
- **Postconditions:** Entry is archived, removed from active use. Existing
  content referencing it (e.g. a state note, UC-079) is not silently broken
  — FEAT-016's consistency check warns about it (UC-080).
  `_TBD: whether archiving a codex entry can be undone._`
- **Source:** `[confirmed: user]` interview 2026-07-20, "codex" round 4:
  "Archine not delete" [archive not delete].

### UC-073 — View an entry's edit history
- **Feature:** FEAT-017 · **Actor:** ACT-004, ACT-005
- **Preconditions:** Entry has at least one prior version.
- **Main flow:**
  1. Member selects an entry.
  2. Member opens its edit history.
  3. System shows the entry's past versions.
- **Postconditions:** None (read-only).
- **Source:** `[confirmed: user]` interview 2026-07-20, "codex" round 4: "we
  keep edit history of every entity."; "What can a member do with an entry's
  edit history? View and restore."

### UC-074 — Restore an entry to an earlier version
- **Feature:** FEAT-017 · **Actor:** ACT-004, ACT-005
- **Preconditions:** Entry's edit history contains an earlier version
  (UC-073).
- **Main flow:**
  1. Member selects an earlier version from the entry's edit history.
  2. Member restores it.
  3. System replaces the entry's current content with the selected version.
- **Postconditions:** Entry's content matches the restored version; the
  restore itself becomes a new point in the edit history.
- **Source:** `[confirmed: user]` interview 2026-07-20, "codex" round 4:
  "View and restore."

### UC-075 — Copy codex entries from another book
- **Feature:** FEAT-017 · **Actor:** ACT-004, ACT-005
- **Preconditions:** Member belongs to both the source and target books.
- **Main flow:**
  1. Member opens the codex-copy action on the target book.
  2. Member selects a source book they belong to.
  3. Member selects which entries to copy.
  4. System adds copies of the selected entries to the target book's codex.
- **Postconditions:** Target book's codex gains the copied entries,
  independent of the source afterward.
  `_TBD: whether copying entries between books carries their edit history._`
- **Source:** `[confirmed: user]` interview 2026-07-20, "codex" round 4:
  "Per book, but we can copy/import/export - kind of for sequels etc.";
  "Copy between books, yes."
<!-- product-spec:end -->
