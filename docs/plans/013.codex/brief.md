# 013.codex — Codex authoring, search & chat access
<!-- roadmap:start -->
- **Stage:** 4.codex · **Track:** multi-step · **Size:** L
- **Delivers:** FEAT-017 (core), FEAT-018
- **Depends on:** `010.working-page`, `011.chat-panel`

## Definition
Author, edit, browse and search codex entries (characters / locations /
facts) in the content pane; keep them embedded in the vector index
incrementally and via full rebuild; expose the codex to the assistant
(codex access + codex search tools); and let the assistant write/rewrite a
codex entry on the shared canvas from a chat.

## Scope
**In:** UC-069/070/071 (create/edit/browse/search); retrieval codex
corpus + incremental index maintenance (`retrieval.md`); UC-078 (assistant
reaches codex); FEAT-018 UC-076/077 (codex from chat, shared-canvas
write).
**Out:** codex archive/restore (`017.codex-archive-restore`); codex
version history/restore (`019.codex-history`); cross-book copy (UC-075,
mapped later); chapter/summary/notes corpora (later stages).

## Open questions for the planner
- The assistant/MCP half (codex access + search tools, shared-canvas SSE
  write) sits in the undesigned FEAT-013 subsystem — design during
  planning (see `011.chat-panel`). UC-078's relevance criterion is an
  open product `_TBD:` (challenge C27); `retrieval.md` deliberately picks
  no threshold.
<!-- roadmap:end -->
