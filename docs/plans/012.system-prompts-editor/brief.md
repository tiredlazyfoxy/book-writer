# 012.system-prompts-editor — Book & chapter system prompts (placeholder)
<!-- roadmap:start -->
- **Stage:** 3.workspace · **Track:** multi-step · **Size:** M
- **Delivers:** FEAT-019 (placeholder)
- **Depends on:** `010.working-page`, `009.books`

## Definition
A custom system-prompts editor: set the book's system prompt (owner-only,
applies to every chat in the book) and a chapter's system prompt (any
member, narrows the book's). This is a placeholder brief — its detailed
spec and architecture are not yet produced; the roadmap reserves the slot
before codex so the prompt fields have an editing surface before the
assistant/codex features consume them.

## Scope
**In (provisional):** UC-093/094, US-108/109 — book + chapter
`system_prompt` edit surfaces, per the owner-only / any-member
authorization split.
**Out:** how prompts are assembled into a chat (assistant subsystem);
whether they reach the FEAT-016 consistency check (they do not —
instructions, not content).

## Open questions for the planner
- Placeholder: FEAT-019's authorization rule and the `**Realizes:**
  FEAT-019` headers are a deferred follow-up not yet in
  `authorization.md` / `domain-book.md` / `domain-chapter.md`
  (`domain-model.md` divergence 3). The editor's spec/architecture are to
  be produced before planning — confirm scope, surface (Shell settings vs.
  working page), and design first.
<!-- roadmap:end -->
