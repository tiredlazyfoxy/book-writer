<!-- product-spec:start -->
# Stories — FEAT-016 Consistency check & chapter flags

### US-072 — Owner runs a consistency check on demand
- **Feature:** FEAT-016 · **Actor:** ACT-004 · **Realizes:** UC-064
- **Status:** deferred
- **Story:** As a book owner, I want to run a consistency check whenever I
  choose, so that I can catch contradictions before they compound.
- **Acceptance criteria:**
  - **US-072.AC-1** — Given a book with no contradictions, when the owner
    runs the check, then the result is clean and no flags are created.
  - **US-072.AC-2** — Given a book with a contradiction between a chapter
    and a state note, when the owner runs the check, then a flag is
    created for it.
- **Note (finalization, 2026-07-31):** the mechanism is built —
  `docs/plans/016.chapter-close-continuity/` delivered the close-chapter
  turn, its five tools and the deterministic post-turn finalize step, all
  test-covered. It is **deferred** because the tools ship unreachable
  until an administrator assigns them to the `close-chapter` mode (a
  FEAT-020 capability), and because the plan's one end-to-end live-run
  criterion was never exercised. Remaining to deliver: that mode/tool
  assignment, then one live run.
- **Source:** `[confirmed: user]` interview 2026-07-20, "consistency check &
  chapter flags": "if all is clear — nothing to do, if something is wrong,
  it must be flagged." Deferred, mechanism built: `[confirmed: user]`
  interview 2026-07-31, finalization of plan 016, challenge C-f16-1.

### US-073 — Closing a fixed chapter runs the consistency check
- **Feature:** FEAT-016 · **Actor:** ACT-004 · **Realizes:** UC-065
- **Status:** deferred
- **Story:** As a book owner, I want closing a fixed chapter to run the
  consistency check, so that I can't close over an inconsistency by
  accident.
- **Acceptance criteria:**
  - **US-073.AC-1** — Given a fixed chapter being closed, when the owner
    initiates closing, then the consistency check runs before the chapter
    closes.
- **Note (finalization, 2026-07-31):** the mechanism is built —
  `docs/plans/016.chapter-close-continuity/` delivered the close-chapter
  turn, its five tools and the deterministic post-turn finalize step, all
  test-covered. It is **deferred** because the tools ship unreachable
  until an administrator assigns them to the `close-chapter` mode (a
  FEAT-020 capability), and because the plan's one end-to-end live-run
  criterion was never exercised. Remaining to deliver: that mode/tool
  assignment, then one live run.
- **Source:** `[confirmed: user]` interview 2026-07-20, "consistency check &
  chapter flags": "When owner is closing the chapter they need to run the
  consistency check." Deferred, mechanism built: `[confirmed: user]`
  interview 2026-07-31, finalization of plan 016, challenge C-f16-1.

### US-074 — Owner responds to consistency findings by re-fixing or applying flags
- **Feature:** FEAT-016 · **Actor:** ACT-004 · **Realizes:** UC-066
- **Status:** partially delivered
- **Delivered:** docs/plans/016.chapter-close-continuity/ (2026-07-31)
- **Story:** As a book owner, I want to either fix the chapter again or
  apply the check's flags, so that I control how a flag gets resolved.
- **Acceptance criteria:**
  - **US-074.AC-1** — Given a consistency check produced flags, when
    the owner chooses to fix the chapter again, then the chapter returns
    to open for editing (FEAT-014) instead of closing.
  - **US-074.AC-2** — Given a consistency check produced flags, when
    the owner applies the flags instead, then the chapter closes carrying
    the applied flags.
- **Note (finalization, 2026-07-31):** AC-1 delivered — stopping or
  cancelling the close run returns the chapter to open (design-note D4).
  AC-2 deferred with UC-066 — the "apply flags" act belonged to the
  owner-approval review stage design-note D3 removed; no such surface
  shipped.
- **Source:** `[confirmed: user]` interview 2026-07-20, "consistency check &
  chapter flags": "after the warnings, or fix the chapter again or apply
  the flags." Delivery split, vocabulary ("warning" → "flag") and title:
  `[confirmed: user]` interview 2026-07-31, finalization of plan 016,
  challenges C-f16-2, C-f16-4.

### US-075 — Member raises a flag with a comment
- **Feature:** FEAT-016 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-067
- **Status:** delivered
- **Delivered:** docs/plans/016.chapter-close-continuity/ (2026-07-31)
- **Story:** As a book member, I want to raise a flag with a comment on a
  chapter, so that I can note a problem for the owner to see.
- **Acceptance criteria:**
  - **US-075.AC-1** — Given a member viewing a chapter, when they raise a
    flag with a comment, then the flag is recorded on the chapter with
    that comment.
- **Source:** `[confirmed: user]` interview 2026-07-20, "consistency check &
  chapter flags": "members can flag too, with a comment."

### US-076 — A flag records whether it came from a check or a person
- **Feature:** FEAT-016 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-067
- **Status:** delivered
- **Delivered:** docs/plans/016.chapter-close-continuity/ (2026-07-31)
- **Story:** As a book member, I want each flag to show its origin, so
  that I know whether it's a check finding or a person's note.
- **Acceptance criteria:**
  - **US-076.AC-1** — Given a flag raised by the consistency check, when a
    member views it, then its origin shows as the consistency check.
  - **US-076.AC-2** — Given a flag raised by a member, when a member views
    it, then its origin shows as that person.
- **Source:** `[confirmed: user]` interview 2026-07-20, "consistency check &
  chapter flags": "a flag shows whether it came from a consistency check or
  a person; they carry different weight."

### US-077 — Owner resolves a flag
- **Feature:** FEAT-016 · **Actor:** ACT-004 · **Realizes:** UC-068
- **Status:** delivered
- **Delivered:** docs/plans/016.chapter-close-continuity/ (2026-07-31)
- **Story:** As a book owner, I want to resolve a flag once it's been
  dealt with, so that outstanding issues stay visible and dealt-with ones
  don't.
- **Acceptance criteria:**
  - **US-077.AC-1** — Given an unresolved flag, when the owner resolves
    it, then the flag's status becomes resolved.
- **Source:** `[confirmed: user]` interview 2026-07-20, "consistency check &
  chapter flags": "Flags are resolved."

### US-091 — The check warns when a chapter references something absent from the codex
- **Feature:** FEAT-016 · **Actor:** ACT-004 · **Realizes:** UC-080
- **Status:** deferred
- **Story:** As a book owner, I want the consistency check to warn me when a
  chapter or state note references something with no codex entry, so that I
  can decide whether to add one.
- **Acceptance criteria:**
  - **US-091.AC-1** — Given a chapter or state note that names an entity
    with no corresponding codex entry, when the consistency check runs,
    then a flag about the missing entity is raised.
  - **US-091.AC-2** — Given a book where every referenced entity has a
    codex entry, when the consistency check runs, then no missing-entity
    flag is raised.
- **Note (finalization, 2026-07-31):** the mechanism is built —
  `docs/plans/016.chapter-close-continuity/` delivered the close-chapter
  turn, its five tools and the deterministic post-turn finalize step, all
  test-covered. It is **deferred** because the tools ship unreachable
  until an administrator assigns them to the `close-chapter` mode (a
  FEAT-020 capability), and because the plan's one end-to-end live-run
  criterion was never exercised. Remaining to deliver: that mode/tool
  assignment, then one live run.
- **Source:** `[confirmed: user]` interview 2026-07-20, "codex" round 4:
  "consistency check on chapter must at least warn about missin entity."
  Deferred, mechanism built: `[confirmed: user]` interview 2026-07-31,
  finalization of plan 016, challenge C-f16-1. Vocabulary ("warning" →
  "flag"): `[confirmed: user]` interview 2026-07-31, challenge C-f16-4.

### US-092 — An archived codex entry does not silently break existing state notes
- **Feature:** FEAT-016 · **Actor:** ACT-004 · **Realizes:** UC-080
- **Status:** deferred
- **Story:** As a book owner, I want to be warned when a state note
  references an archived codex entry, so that the reference isn't silently
  left dangling.
- **Acceptance criteria:**
  - **US-092.AC-1** — Given a state note that references an archived codex
    entry, when the consistency check runs, then a flag about the
    archived reference is raised.
- **Note (finalization, 2026-07-31):** the mechanism is built —
  `docs/plans/016.chapter-close-continuity/` delivered the close-chapter
  turn, its five tools and the deterministic post-turn finalize step, all
  test-covered. It is **deferred** because the tools ship unreachable
  until an administrator assigns them to the `close-chapter` mode (a
  FEAT-020 capability), and because the plan's one end-to-end live-run
  criterion was never exercised. Remaining to deliver: that mode/tool
  assignment, then one live run.
- **Source:** `[confirmed: user]` interview 2026-07-20, "codex" round 4:
  "Archine not delete, but consistency check on chapter must at least warn
  about missin entity." Deferred, mechanism built: `[confirmed: user]`
  interview 2026-07-31, finalization of plan 016, challenge C-f16-1.
  Vocabulary ("warning" → "flag"): `[confirmed: user]` interview
  2026-07-31, challenge C-f16-4.
<!-- product-spec:end -->
