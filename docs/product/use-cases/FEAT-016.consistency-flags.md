<!-- product-spec:start -->
# Use Cases — FEAT-016 Consistency check & chapter flags

### UC-064 — Run a consistency check on demand
- **Feature:** FEAT-016 · **Actor:** ACT-004
- **Preconditions:** Owner authenticated; book exists.
- **Main flow:**
  1. Owner requests a consistency check on the book.
  2. System inspects the book's chapters, summaries and state notes for
     contradictions.
  3. System reports the result to the owner: clean, or one flag per
     suspect item (UC-066).
- **Exception flow:** No LLM server is enabled (FEAT-004) → the check is
  refused. `[inferred]` — basis: FEAT-016 depends on FEAT-004 for an
  enabled LLM server (spec-plan dependency edge); the interview does not
  state the refusal behavior directly.
- **Postconditions:** A clean result requires no action; nothing is
  rewritten automatically.
- **Note (finalization, 2026-07-31):** the mechanism is built —
  `docs/plans/016.chapter-close-continuity/` delivered the close-chapter
  turn, its five tools and the deterministic post-turn finalize step, all
  test-covered. It is **deferred** because the tools ship unreachable
  until an administrator assigns them to the `close-chapter` mode (a
  FEAT-020 capability), and because the plan's one end-to-end live-run
  criterion was never exercised. Remaining to deliver: that mode/tool
  assignment, then one live run.
- **Source:** `[confirmed: user]` interview 2026-07-20, "consistency check &
  chapter flags": "LLM checks the consistency and shows to the owner
  inconsistent notes or chapter content... on demand." Deferred, mechanism
  built: `[confirmed: user]` interview 2026-07-31, finalization of plan
  016, challenge C-f16-1.

### UC-065 — Run the consistency check when closing a fixed chapter
- **Feature:** FEAT-016 · **Actor:** ACT-004
- **Preconditions:** A fixed chapter (edited after reopening, FEAT-014) is
  being closed.
- **Main flow:**
  1. Owner initiates closing the fixed chapter.
  2. System runs the consistency check (UC-064) as part of closing.
  3. Owner reads the flags, if any.
  4. Owner fixes the chapter again, or applies the flags and closes
     (UC-066).
- **Exception flow:** No LLM server is enabled → same as UC-064; other
  check failures → `_TBD:` as recorded in FEAT-016.
- **Postconditions:** A fixed chapter closes only after the owner has
  acted on the check's result.
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
  consistency check 'kind of on demand' and, after the warnings, or fix the
  chapter again or apply the flags." Deferred, mechanism built:
  `[confirmed: user]` interview 2026-07-31, finalization of plan 016,
  challenge C-f16-1. Vocabulary ("warning" → "flag"): `[confirmed: user]`
  interview 2026-07-31, challenge C-f16-4.

### UC-066 — Apply flags from consistency findings
- **Feature:** FEAT-016 · **Actor:** ACT-004
- **Preconditions:** A consistency check has produced one or more flags.
- **Main flow:**
  1. Owner reviews the check's flags.
  2. Owner applies the flags to the chapters they concern.
  3. Chapter proceeds to close (UC-065), carrying the applied flags.
- **Exception flow:** The chapter's active variant changes (FEAT-014) after
  flags were raised → `_TBD: whether existing flags stay attached, are
  re-evaluated, or are cleared — not stated._`
- **Postconditions:** Flags are attached to the chapters they concern,
  visible to authors; nothing is rewritten by the check itself.
- **Note (finalization, 2026-07-31):** **Deferred** — the "apply flags" act
  belonged to the owner-approval review stage that design-note D3 removed;
  no review/edit/approve surface shipped in plan
  `016.chapter-close-continuity`. Not on the deferred-but-built list (see
  FEAT-016's finalization paragraph, `features.md`) — this act has no
  built mechanism at all, unlike UC-064/065/080.
- **Source:** `[confirmed: user]` interview 2026-07-20, "consistency check &
  chapter flags": "if something is wrong, it must be flagged... nothing is
  silently rewritten." Deferred: `[confirmed: user]` interview 2026-07-31,
  finalization of plan 016, challenge C-f16-2. Title vocabulary ("warnings"
  → "findings"): `[confirmed: user]` interview 2026-07-31, challenge
  C-f16-4.

### UC-067 — Member raises a flag on a chapter
- **Feature:** FEAT-016 · **Actor:** ACT-004, ACT-005
- **Delivered:** docs/plans/016.chapter-close-continuity/ (2026-07-31)
- **Preconditions:** Member is on the book; chapter exists.
- **Main flow:**
  1. Member selects a chapter.
  2. Member raises a flag with a comment.
  3. System records the flag, tagged as person-raised.
- **Postconditions:** Flag exists on the chapter, carrying its comment and
  origin (person); visible to book members.
- **Source:** `[confirmed: user]` interview 2026-07-20, "consistency check &
  chapter flags": "Are flags only consistency findings? General — members
  can flag too, with a comment."

### UC-068 — Resolve a flag
- **Feature:** FEAT-016 · **Actor:** ACT-004
- **Delivered:** docs/plans/016.chapter-close-continuity/ (2026-07-31)
- **Preconditions:** An unresolved flag exists on a chapter.
- **Main flow:**
  1. Owner reviews an unresolved flag.
  2. Owner resolves it.
  3. System marks the flag resolved.
- **Exception flow:** A later consistency check raises the same issue again
  after the flag was resolved →
  `_TBD: whether a new flag is raised, the old one reopened, or something
  else — not stated._` **Addendum (finalization, 2026-07-31):** each close
  run **deletes** every `origin=check` flag on the chapter before
  starting, so a check finding is never "re-raised" or "reopened" — it is
  simply produced afresh by each run. Person-raised flags are never
  touched by this and remain advisory. The `_TBD:` stays open because this
  answers only the check-flag case, not the general question.
- **Postconditions:** Flag is marked resolved; resolution does not undo
  whatever prompted the flag.
- **Source:** `[confirmed: user]` interview 2026-07-20, "consistency check &
  chapter flags": "Flags are resolved." Addendum: `[confirmed: user]`
  interview 2026-07-31, finalization of plan 016, challenge C-f16-2 /
  outcome.md.

### UC-080 — Consistency check warns about content with no codex entry behind it
- **Feature:** FEAT-016 · **Actor:** ACT-004
- **Preconditions:** A consistency check runs (UC-064 or UC-065); the book
  has a codex (FEAT-017).
- **Main flow:**
  1. System inspects chapters, summaries and state notes, alongside the
     codex.
  2. System finds content that names or implies an entity absent from the
     codex, or a state note that references an archived entry.
  3. System raises a flag about the missing or archived entity.
- **Postconditions:** A flag exists for the finding; nothing is blocked and
  no entry is created automatically — codex coverage stays optional.
- **Note (finalization, 2026-07-31):** the mechanism is built —
  `docs/plans/016.chapter-close-continuity/` delivered the close-chapter
  turn, its five tools and the deterministic post-turn finalize step, all
  test-covered. It is **deferred** because the tools ship unreachable
  until an administrator assigns them to the `close-chapter` mode (a
  FEAT-020 capability), and because the plan's one end-to-end live-run
  criterion was never exercised. Remaining to deliver: that mode/tool
  assignment, then one live run.
- **Source:** `[confirmed: user]` interview 2026-07-20, "codex" round 4:
  "consistency check on chapter must at least warn about missin entity
  (honestly not all the characters must be in the codex, but better to
  be)." — warns, never blocks. Deferred, mechanism built: `[confirmed:
  user]` interview 2026-07-31, finalization of plan 016, challenge
  C-f16-1. Vocabulary ("warning" → "flag"): `[confirmed: user]` interview
  2026-07-31, challenge C-f16-4.
<!-- product-spec:end -->
