<!-- product-spec:start -->
# Stories — FEAT-016 Consistency check & chapter flags

### US-072 — Owner runs a consistency check on demand
- **Feature:** FEAT-016 · **Actor:** ACT-004 · **Realizes:** UC-064
- **Status:** proposed
- **Story:** As a book owner, I want to run a consistency check whenever I
  choose, so that I can catch contradictions before they compound.
- **Acceptance criteria:**
  - **US-072.AC-1** — Given a book with no contradictions, when the owner
    runs the check, then the result is clean and no flags are created.
  - **US-072.AC-2** — Given a book with a contradiction between a chapter
    and a state note, when the owner runs the check, then a flag is
    created for it.
- **Source:** `[confirmed: user]` interview 2026-07-20, "consistency check &
  chapter flags": "if all is clear — nothing to do, if something is wrong,
  it must be flagged."

### US-073 — Closing a fixed chapter runs the consistency check
- **Feature:** FEAT-016 · **Actor:** ACT-004 · **Realizes:** UC-065
- **Status:** proposed
- **Story:** As a book owner, I want closing a fixed chapter to run the
  consistency check, so that I can't close over an inconsistency by
  accident.
- **Acceptance criteria:**
  - **US-073.AC-1** — Given a fixed chapter being closed, when the owner
    initiates closing, then the consistency check runs before the chapter
    closes.
- **Source:** `[confirmed: user]` interview 2026-07-20, "consistency check &
  chapter flags": "When owner is closing the chapter they need to run the
  consistency check."

### US-074 — Owner responds to warnings by re-fixing or applying flags
- **Feature:** FEAT-016 · **Actor:** ACT-004 · **Realizes:** UC-066
- **Status:** proposed
- **Story:** As a book owner, I want to either fix the chapter again or
  apply the check's flags, so that I control how a warning gets resolved.
- **Acceptance criteria:**
  - **US-074.AC-1** — Given a consistency check produced warnings, when
    the owner chooses to fix the chapter again, then the chapter returns
    to open for editing (FEAT-014) instead of closing.
  - **US-074.AC-2** — Given a consistency check produced warnings, when
    the owner applies the flags instead, then the chapter closes carrying
    the applied flags.
- **Source:** `[confirmed: user]` interview 2026-07-20, "consistency check &
  chapter flags": "after the warnings, or fix the chapter again or apply
  the flags."

### US-075 — Member raises a flag with a comment
- **Feature:** FEAT-016 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-067
- **Status:** proposed
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
- **Status:** proposed
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
- **Status:** proposed
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
- **Status:** proposed
- **Story:** As a book owner, I want the consistency check to warn me when a
  chapter or state note references something with no codex entry, so that I
  can decide whether to add one.
- **Acceptance criteria:**
  - **US-091.AC-1** — Given a chapter or state note that names an entity
    with no corresponding codex entry, when the consistency check runs,
    then a flag warning about the missing entity is raised.
  - **US-091.AC-2** — Given a book where every referenced entity has a
    codex entry, when the consistency check runs, then no missing-entity
    flag is raised.
- **Source:** `[confirmed: user]` interview 2026-07-20, "codex" round 4:
  "consistency check on chapter must at least warn about missin entity."

### US-092 — An archived codex entry does not silently break existing state notes
- **Feature:** FEAT-016 · **Actor:** ACT-004 · **Realizes:** UC-080
- **Status:** proposed
- **Story:** As a book owner, I want to be warned when a state note
  references an archived codex entry, so that the reference isn't silently
  left dangling.
- **Acceptance criteria:**
  - **US-092.AC-1** — Given a state note that references an archived codex
    entry, when the consistency check runs, then a flag warning about the
    archived reference is raised.
- **Source:** `[confirmed: user]` interview 2026-07-20, "codex" round 4:
  "Archine not delete, but consistency check on chapter must at least warn
  about missin entity."
<!-- product-spec:end -->
