<!-- product-spec:start -->
# Stories — FEAT-009 Chapter writing

(File retains its original slug, `chapter-writing-blocks`, per the
merge-fence filename-stability rule — the domain noun was renamed
"block" → "edit" in the 2026-07-30 finalization pass, the file was not.)

### US-036 — Owner opens a chapter for writing
- **Feature:** FEAT-009 · **Actor:** ACT-004 · **Realizes:** UC-035
- **Status:** delivered
- **Story:** As a book owner, I want to open a planned chapter, so that
  writing can begin on it.
- **Acceptance criteria:**
  - **US-036.AC-1** — Given a chapter in the planned state and no chapter
    currently open, when the owner opens it, then the chapter's state
    becomes open.
  - **US-036.AC-2** — Given a co-author (not the owner), when they attempt
    to open a chapter, then the action is refused.
- **Source:** `[confirmed: user]` interview 2026-07-20, "book structure —
  chapters, states, sketches": "Owner only." Delivered:
  `docs/plans/015.chapter-writing-free-mode/` (2026-07-30).

### US-037 — Only one chapter can be open at a time
- **Feature:** FEAT-009 · **Actor:** ACT-004 · **Realizes:** UC-035
- **Status:** delivered
- **Story:** As a book owner, I want the system to enforce a single open
  chapter, so that writing stays serial and coordinated.
- **Acceptance criteria:**
  - **US-037.AC-1** — Given any sequence of open/close/reopen actions, when
    the book's chapters are inspected, then at most one chapter is in the
    open state.
  - **US-037.AC-2** — Given a chapter that is open or closing, when the
    owner attempts to open or reopen a different chapter, then the
    attempt is refused and both chapters keep their current states.
- **Source:** `[confirmed: user]` interview 2026-07-20, "book structure —
  chapters, states, sketches": "At most one open chapter per book."
  AC-2: `[confirmed: user]` interview 2026-07-24, "augment round 7",
  divergence 4 — closes the prior `_TBD:`. Delivered:
  `docs/plans/015.chapter-writing-free-mode/` (2026-07-30).

### US-038 — Owner closes the open chapter
- **Feature:** FEAT-009 · **Actor:** ACT-004 · **Realizes:** UC-036
- **Status:** partially delivered
- **Story:** As a book owner, I want to close the open chapter, so that it
  becomes final and no longer editable.
- **Acceptance criteria:**
  - **US-038.AC-1** — Given an open chapter, when the owner closes it, then
    the chapter's state becomes closed and it is no longer editable.
  - **US-038.AC-2** — Given a co-author, when they attempt to close the
    open chapter, then the action is refused.
  - **US-038.AC-3** — Given an open chapter whose summary or state-note
    changeset is not approved, when the owner requests to close it, then
    the chapter enters the **closing** state — not open, not closed — and
    still refuses writes.
  - **US-038.AC-4** — Given a chapter in the closing state, when the
    owner attempts to open or reopen a different chapter, then the
    attempt is refused — closing still counts as the book's one open
    chapter.
- **Note (finalization, 2026-07-30):** AC-1, AC-2 and AC-4 delivered in
  `docs/plans/015.chapter-writing-free-mode/`. **AC-3 deferred** to plan
  `016.chapter-close-continuity` (challenge C6) — the requirement stands,
  only its delivery slipped; it is not withdrawn.
- **Source:** `[confirmed: user]` interview 2026-07-20, "book structure —
  chapters, states, sketches": "closed (written, not editable)." AC-3 —
  `[confirmed: user]` interview 2026-07-20, "Augment round 2", "summaries &
  state notes": "Approval required to close."; challenge C17 (FEAT-012).
  AC-3 rewritten and AC-4 added: `[confirmed: user]` interview 2026-07-24,
  "augment round 7", divergence 6 (C-r7-4) — the closing state holds the
  one-open-chapter slot and refuses writes; a refused close no longer
  leaves the chapter "open". Delivery record: `[confirmed: user]`
  interview 2026-07-30, "finalization — 021 + 014 + 015", challenge C6.

### US-039 — Owner reopens a closed chapter
- **Feature:** FEAT-009 · **Actor:** ACT-004 · **Realizes:** UC-037
- **Status:** delivered
- **Story:** As a book owner, I want to reopen a closed chapter, so that I
  can revise it even after moving on.
- **Acceptance criteria:**
  - **US-039.AC-1** — Given a closed chapter and no chapter currently open,
    when the owner reopens it, then its state becomes open.
  - **US-039.AC-2** — Given a closed chapter and a different chapter
    currently open, when the owner attempts to reopen the closed one,
    then the attempt is **refused** and the open chapter is unaffected.
- **Note:** Editing the reopened chapter creates a variant — see FEAT-014.
- **Source:** `[confirmed: user]` interview 2026-07-20, "book structure —
  chapters, states, sketches": "Reopening a chapter implies closing the
  currently-open one." AC-2 rewritten (reverses the auto-close):
  `[confirmed: user]` interview 2026-07-24, "augment round 7", divergence
  4 — closes CF1. Delivered: `docs/plans/015.chapter-writing-free-mode/`
  (2026-07-30).

### US-040 — Co-author adds an edit in free mode
- **Feature:** FEAT-009 · **Actor:** ACT-005 · **Realizes:** UC-038
- **Status:** delivered
- **Story:** As a co-author, I want to add an edit directly to the open
  chapter in free mode, so that my contribution lands immediately.
- **Acceptance criteria:**
  - **US-040.AC-1** — Given a chapter open and the book in free mode, when
    a co-author saves a new edit, then the edit is added to the open
    chapter immediately.
  - **US-040.AC-2** — Given a chapter open and the book in free mode, when
    a co-author saves a new edit, then the edit is attributed to them.
  - **US-040.AC-3** — Given no chapter is open, when a member attempts to
    add an edit, then the add is refused.
  - **US-040.AC-4** — Given two members compose edits concurrently and
    the chapter's body moved underneath the later save, when the later
    save is re-issued against the current body, then both members'
    edits end up in the chapter. **Note:** satisfied by the author
    reconciling through AC-5 below, not by an automatic merge — the
    system performs no merge.
  - **US-040.AC-5** — Given a member's save is composed against a chapter
    body that has since changed, when they save, then the save is
    refused, both the current body and the member's own text are shown,
    and a save re-issued against the current body is accepted.
- **Source:** `[confirmed: user]` interview 2026-07-20, "writing — blocks &
  concurrency": "the process of the chapter writing is... by some blocks."
  AC-4 rewritten: `[confirmed: user]` interview 2026-07-24, "augment round
  7", divergence 5 — concurrency is per chapter, not per block. Closes the
  block-contents `_TBD:`. Renamed "block" → "edit": `[confirmed: user]`
  interview 2026-07-30, "finalization — 021 + 014 + 015", challenge C2.
  AC-5 added (split from AC-4, names the mechanism): `[confirmed: user]`
  interview 2026-07-30, "challenges (2026-07-30)", challenge C3 —
  `domain-chapter.md` is explicit there is no automatic merge at MVP.
  Delivered: `docs/plans/015.chapter-writing-free-mode/` (2026-07-30).

### US-041 — A save against a changed chapter body warns the author
- **Feature:** FEAT-009 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-039
- **Status:** delivered
- **Story:** As a book member, I want to be warned when the chapter body I
  composed against changed underneath me, so that I don't silently
  overwrite someone else's work.
- **Acceptance criteria:**
  - **US-041.AC-1** — Given a member's save is composed against a chapter
    body that has since changed, when they attempt to save, then the save
    is refused and the author is shown the divergence before anything is
    written.
  - **US-041.AC-2** — Given the author reconciles the divergence and
    saves, when the save completes, then their reconciled text becomes
    the chapter's current body.
  - **US-041.AC-3** — Given the author abandons the save instead, when
    they discard it, then the chapter keeps the other member's text and
    nothing of the abandoning author's is written.
- **Source:** `[confirmed: user]` interview 2026-07-20, "writing — blocks &
  concurrency": "warn-then-later-write-wins rule applies only when two
  co-authors edit the same block." Retitled and rewritten:
  `[confirmed: user]` interview 2026-07-24, "augment round 7", divergence
  5 (C-r7-2) — the chapter body and version model, not per-block
  last-write-wins. Delivered: `docs/plans/015.chapter-writing-free-mode/`
  (2026-07-30).
<!-- product-spec:end -->
