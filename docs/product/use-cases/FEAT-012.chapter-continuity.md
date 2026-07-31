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
- **Note (finalization, 2026-07-31):** the mechanism is built —
  `docs/plans/016.chapter-close-continuity/` delivered the close-chapter
  turn, its five tools and the deterministic post-turn finalize step, all
  test-covered. It is **deferred** because the tools ship unreachable
  until an administrator assigns them to the `close-chapter` mode (a
  FEAT-020 capability), and because the plan's one end-to-end live-run
  criterion was never exercised. Remaining to deliver: that mode/tool
  assignment, then one live run.
- **Source:** `[confirmed: user]` interview 2026-07-20, "Augment round 2",
  "summaries & state notes": "LLM proposes, owner approves. On closing a
  chapter the system drafts them." Precondition named:
  `[confirmed: user]` interview 2026-07-24, "augment round 7", divergence
  6 (C-r7-4). Deferred, mechanism built: `[confirmed: user]` interview
  2026-07-31, finalization of plan 016, challenge C-f16-1.

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
- **Note (finalization, 2026-07-31):** `_TBD: UC-048's preconditions assume
  a chapter sits in closing with drafted continuity pending approval. The
  shipped close procedure (plan 016, design-note D4) has no such resting
  state — a run either closes the chapter or returns it to open,
  discarding the drafts. When the approval surface is built, this use
  case's preconditions and UC-036's step 5 must be re-specified
  together._` Deferred, not withdrawn — the approval surface is future
  work, not abandoned (challenge C-f16-2).
- **Source:** `[confirmed: user]` interview 2026-07-20, "Augment round 2",
  "summaries & state notes": "LLM proposes, owner approves... the owner
  reviews, edits and accepts." Step 4: `[confirmed: user]` interview
  2026-07-24, "augment round 7", divergence 6. Re-specification `_TBD:`
  added: `[confirmed: user]` interview 2026-07-31, finalization of plan
  016, challenge C-f16-2.

### UC-049 — View the book's current state notes
- **Feature:** FEAT-012 · **Actor:** ACT-004, ACT-005
- **Delivered:** docs/plans/016.chapter-close-continuity/ (2026-07-31)
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
- **Delivered:** docs/plans/016.chapter-close-continuity/ (2026-07-31)
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
- **Note (finalization, 2026-07-31):** Free-mode direct edit (step 2)
  delivered. Proposal-mode holding (step 3) is not built — a proposal-mode
  state-note edit is refused, since FEAT-010's proposal-holding mechanism
  does not yet exist for this artifact (`relationships.md`, FEAT-012 →
  FEAT-010).
- **Source:** `[confirmed: user]` interview 2026-07-20, "Augment round 2",
  "summaries & state notes": "Follows the book's collaboration mode — free
  mode any member edits directly, proposal mode they propose and the owner
  applies." Delivery split: `[confirmed: user]` interview 2026-07-31,
  finalization of plan 016.

### UC-051 — View a chapter's state-note changeset
- **Feature:** FEAT-012 · **Actor:** ACT-004, ACT-005
- **Delivered:** docs/plans/016.chapter-close-continuity/ (2026-07-31)
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
- **Delivered:** docs/plans/016.chapter-close-continuity/ (2026-07-31)
- **Preconditions:** Owner reopens a closed chapter (UC-037).
- **Main flow:**
  1. Owner reopens a closed chapter.
  2. System flags the chapter's summary and state-note changeset stale.
  3. Chapter returns to the open state (per UC-037).
- **Exception flow:** Chapter being reopened has no approved continuity
  data on record — **unreachable**: a chapter reaches `closed` only via a
  clean close run, which necessarily produced and approved both
  artifacts; therefore a closed chapter always has approved continuity on
  record.
- **Postconditions:** Chapter's continuity data is marked stale; re-closing
  re-runs the close procedure, which drafts a fresh summary and changeset
  (UC-048's approval surface is deferred, not part of the shipped flow).
  Whether later chapters' changesets built on this chapter's deltas are
  consistent is checked by FEAT-016's consistency check (UC-064/UC-065),
  not by this use case — see FEAT-016.
- **Source:** `[confirmed: user]` interview 2026-07-20, "Augment round 2",
  "summaries & state notes": "Flagged stale, owner must re-confirm." /
  "The cascade — not decided yet"; challenge C12, closed by FEAT-016
  (round 3). Exception flow closed as unreachable: `[confirmed: user]`
  interview 2026-07-24, "augment round 7", divergence 6. Postcondition and
  exception-flow justification restated for the shipped clean-run close:
  `[confirmed: user]` interview 2026-07-31, finalization of plan 016,
  challenge C-f16-2.

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
- **Delivered:** docs/plans/016.chapter-close-continuity/ (2026-07-31)
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
- **Delivered:** docs/plans/016.chapter-close-continuity/ (2026-07-31)
- **Preconditions:** Author is a member of the book; the working page is
  open.
- **Main flow:**
  1. On opening the book's working SPA, Book state is shown first in the
     content pane.
  2. It shows the book's own fields. `_TBD: exact field list — deferred to
     /architect, book object; do not invent._`
  3. For each chapter it shows title, its summary (UC-089), its
     after-chapter state-note changeset (UC-049, UC-051), and any active
     flags in context (FEAT-016).
  4. The author may edit state notes here (UC-050), per the book's
     collaboration mode.
- **Postconditions:** Book state is the landing surface; it aggregates
  existing continuity views plus flags-in-context plus book fields; a
  read-only, members-only mirror lives under Book settings (round 5).
  Distinct from **Chapters** (read/write prose) — Book state is the
  continuity picture, not a duplicate of it.
- **Note (finalization, 2026-07-31):** Partially delivered — steps 1–4
  ship as described. Step 2's book-level field list stays `_TBD:` (see
  US-106.AC-4), which is the only open gap.
- **Source:** `[confirmed: user]` interview 2026-07-23, "Augment round 6",
  "Book state — the landing view": "A per-chapter continuity overview...
  Book state is first, the home you see on opening the book to work."
  Vocabulary ("warning" → "flag"): `[confirmed: user]` interview
  2026-07-31, finalization of plan 016, challenge C-f16-4.
<!-- product-spec:end -->
