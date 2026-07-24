<!-- product-spec:start -->
# Use Cases — FEAT-012 Chapter summaries & state notes

### UC-047 — System drafts a chapter's summary and state-note changes on close
- **Feature:** FEAT-012 · **Actor:** ACT-004
- **Preconditions:** Chapter has entered the **closing** state (UC-036).
- **Main flow:**
  1. Owner initiates closing the chapter.
  2. System drafts a summary of the chapter's content.
  3. System drafts the chapter's state-note changeset (notes added, modified,
     deleted).
  4. Draft is presented to the owner for review (UC-048).
- **Postconditions:** Chapter has a draft summary and draft state-note
  changeset, pending owner approval; chapter is in the closing state, not
  yet closed.
- **Source:** `[confirmed: user]` interview 2026-07-20, "Augment round 2",
  "summaries & state notes": "LLM proposes, owner approves. On closing a
  chapter the system drafts them." Precondition named:
  `[confirmed: user]` interview 2026-07-24, "augment round 7", divergence
  6 (C-r7-4).

### UC-048 — Owner reviews and approves a chapter's continuity data
- **Feature:** FEAT-012 · **Actor:** ACT-004
- **Preconditions:** Chapter has a drafted summary and state-note changeset
  (UC-047) pending approval.
- **Main flow:**
  1. Owner reviews the drafted summary and state-note changeset.
  2. Owner edits either as needed.
  3. Owner approves.
  4. System transitions the chapter **closing → closed**.
- **Exception flow:** Owner approves with the summary left empty →
  `_TBD: whether an empty summary blocks approval is not stated in the
  interview._`
- **Postconditions:** Chapter's continuity data is approved; chapter is
  closed.
- **Source:** `[confirmed: user]` interview 2026-07-20, "Augment round 2",
  "summaries & state notes": "LLM proposes, owner approves... the owner
  reviews, edits and accepts." Step 4: `[confirmed: user]` interview
  2026-07-24, "augment round 7", divergence 6.

### UC-049 — View the book's current state notes
- **Feature:** FEAT-012 · **Actor:** ACT-004, ACT-005
- **Preconditions:** None (an empty state-note set is valid).
- **Main flow:**
  1. Member opens the book's state notes.
  2. System shows the current live set of state notes.
- **Postconditions:** Member sees current truth, not a historical
  accumulation.
- **Source:** `[confirmed: user]` interview 2026-07-20, "Augment round 2",
  "summaries & state notes": "There is one live set of state notes... Chapter
  N sees current truth."

### UC-050 — Edit state notes
- **Feature:** FEAT-012 · **Actor:** ACT-004, ACT-005
- **Preconditions:** Book has a collaboration mode set (free or proposal,
  FEAT-010).
- **Main flow:**
  1. Member adds, modifies or deletes a state note.
  2. In free mode: system applies the change to the live set immediately.
  3. In proposal mode: system holds the change as a proposal; owner applies
     it (FEAT-010 mechanism).
- **Exception flow:** Member deletes a note that a later chapter's
  changeset recorded as modified → not resolved here; FEAT-016's
  consistency check (UC-064) surfaces the inconsistency as a flag — see
  FEAT-016.
- **Postconditions:** Live state-note set reflects the applied change (free
  mode) or holds a pending proposal (proposal mode).
- **Source:** `[confirmed: user]` interview 2026-07-20, "Augment round 2",
  "summaries & state notes": "Follows the book's collaboration mode — free
  mode any member edits directly, proposal mode they propose and the owner
  applies."

### UC-051 — View a chapter's state-note changeset
- **Feature:** FEAT-012 · **Actor:** ACT-004, ACT-005
- **Preconditions:** Chapter has closed at least once and has a recorded
  changeset.
- **Main flow:**
  1. Member selects a chapter.
  2. System shows which state notes that chapter added, modified or
     deleted.
- **Postconditions:** Member sees the chapter's recorded delta, distinct
  from the current live set.
- **Source:** `[confirmed: user]` interview 2026-07-20, "Augment round 2",
  "summaries & state notes": "each chapter records which notes it added,
  modified or deleted."

### UC-052 — Reopening a chapter flags its continuity data stale
- **Feature:** FEAT-012 · **Actor:** ACT-004
- **Preconditions:** Owner reopens a closed chapter (UC-037).
- **Main flow:**
  1. Owner reopens a closed chapter.
  2. System flags the chapter's summary and state-note changeset stale.
  3. Chapter returns to the open state (per UC-037).
- **Exception flow:** Chapter being reopened has no approved continuity
  data on record — **unreachable**: a chapter can only be closed once its
  continuity is approved (US-038.AC-3), so a closed chapter always has
  approved data on record.
- **Postconditions:** Chapter's continuity data is marked stale; re-closing
  requires re-approval (UC-048). Whether later chapters' changesets built
  on this chapter's deltas are consistent is checked by FEAT-016's
  consistency check (UC-064/UC-065), not by this use case — see FEAT-016.
- **Source:** `[confirmed: user]` interview 2026-07-20, "Augment round 2",
  "summaries & state notes": "Flagged stale, owner must re-confirm." /
  "The cascade — not decided yet"; challenge C12, closed by FEAT-016
  (round 3). Exception flow closed as unreachable: `[confirmed: user]`
  interview 2026-07-24, "augment round 7", divergence 6.

### UC-079 — State note references a named codex entry
- **Feature:** FEAT-012 · **Actor:** ACT-004, ACT-005
- **Preconditions:** A named codex entry (character or location, FEAT-017)
  exists in the book.
- **Main flow:**
  1. Member writes or edits a state note (UC-050).
  2. Member names the codex entry the note is about.
  3. System records the reference alongside the note.
- **Postconditions:** State note carries a reference to the named entry; the
  note remains free text otherwise — no entity model beyond this reference.
- **Source:** `[confirmed: user]` interview 2026-07-20, "codex" round 4: "A
  state note may reference a codex entry."; "Identity vs. change."

### UC-089 — View a chapter's summary
- **Feature:** FEAT-012 · **Actor:** ACT-004, ACT-005
- **Preconditions:** Chapter is closed and its summary is approved
  (UC-048).
- **Main flow:**
  1. Member opens the chapter's summary (e.g., from the continuity view).
  2. System shows the approved summary, read-only.
- **Postconditions:** None (read-only); editing the summary is UC-050, not
  this use case. Fills a gap: until this round, a summary could only be
  drafted (UC-047) and approved (UC-048), never viewed on its own.
- **Source:** `[confirmed: user]` interview 2026-07-23, "Augment round 5",
  "SPA pages — the plain surfaces around the working page": "Continuity
  view (under Book settings) — read-only page listing chapters + their
  summaries + post-chapter state-note changesets (UC-051 + a NEW
  view-summary UC — gap: no UC today for viewing a chapter summary, only
  draft UC-047 / approve UC-048)."

**Note (management location):** All editing of summaries and state notes
(UC-050) happens on the working SPA; the settings-side continuity view
(UC-051, UC-089) is a read-only, members-only surface. `[confirmed: user]`
interview 2026-07-23, "Augment round 5", "RULE (per author only =
members-only)": "all management/editing of codex, state notes, summaries
and flags happens ONLY on the working SPA."

### UC-091 — View Book state — the working-SPA landing view
- **Feature:** FEAT-012 · **Actor:** ACT-004, ACT-005
- **Preconditions:** Author is a member of the book; the working page is
  open.
- **Main flow:**
  1. On opening the book's working SPA, Book state is shown first in the
     content pane.
  2. It shows the book's own fields. `_TBD: exact field list — deferred to
     /architect, book object; do not invent._`
  3. For each chapter it shows title, its summary (UC-089), its
     after-chapter state-note changeset (UC-049, UC-051), and any active
     warnings in context (FEAT-016).
  4. The author may edit state notes here (UC-050), per the book's
     collaboration mode.
- **Postconditions:** Book state is the landing surface; it aggregates
  existing continuity views plus warnings-in-context plus book fields; a
  read-only, members-only mirror lives under Book settings (round 5).
  Distinct from **Chapters** (read/write prose) — Book state is the
  continuity picture, not a duplicate of it.
- **Source:** `[confirmed: user]` interview 2026-07-23, "Augment round 6",
  "Book state — the landing view": "A per-chapter continuity overview...
  Book state is first, the home you see on opening the book to work."
<!-- product-spec:end -->
