# 010.working-page — Working-page SPA shell
<!-- roadmap:start -->
- **Stage:** 3.workspace · **Track:** multi-step · **Size:** L
- **Delivers:** FEAT-013 (workspace shell)
- **Depends on:** `009.books`

## Definition
Build the working-page SPA shell an author opens for a book: the new
`work/` Vite entry, the three-region layout (navigator · content pane ·
chat-pane slot), the navigator (Book state · Characters · Locations ·
Facts · Chapters · Variants · Chats), the Book-state landing view, and the
draft-until-saved content pane with its per-item localStorage restore
buffer. The chat-pane slot exists but is empty; lists render read-only
until their owning feature fills them.

## Scope
**In:** UC-090 (navigator), UC-091/US-106 (book-state landing),
UC-092/US-107 (restore buffer), UC-083/US-097 (content-pane subject: list
or item, the editable-vs-read-only rule); the `work` (+ stub `read`)
entries, routing, spaFallback, nginx.
**Out:** the chat pane's behaviour (`011.chat-panel`); codex/chapter
editing content (`013.codex`/`014.chapter-skeleton`); the reader SPA's full
build; pane resize/orientation mechanics.

## Open questions for the planner
- None — fully specified in `frontend-workspace.md`.
<!-- roadmap:end -->
