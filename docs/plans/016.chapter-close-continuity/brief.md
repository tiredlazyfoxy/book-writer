# 016.chapter-close-continuity — Chapter close & continuity
<!-- roadmap:start -->
- **Stage:** 5.chapters · **Track:** multi-step · **Size:** L
- **Delivers:** FEAT-012, FEAT-016 (flags)
- **Depends on:** `015.chapter-writing-free-mode`

## Definition
Turn chapter close into the continuity procedure: on close, draft the
chapter's summary and its state-note changeset for owner review/approval
(close is now gated on approval); view current state notes and a
chapter's changeset; mark continuity stale on reopen; and raise/resolve
flags ("warnings") on a chapter.

## Scope
**In:** UC-047..052, UC-089; US-049..055, US-104. Summary + note-changeset
draft/approve lifecycle; the approval close-gate (amends
`015.chapter-writing-free-mode`); Flag entity + raise/resolve
(UC-067/068).
**Out:** the LLM consistency check (FEAT-016 UC-064/065/080, mapped
later); variants (`018.chapter-history-variants`); proposal-mode review of
notes.

## Open questions for the planner
- Summary/state-note drafting is an LLM generation — decide whether it
  reuses a direct model call (like embedding) or the assistant subsystem;
  design during planning.
<!-- roadmap:end -->
