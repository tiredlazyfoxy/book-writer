# 013.codex — Codex authoring, search & chat access
<!-- roadmap:start -->
- **Stage:** 4.codex · **Track:** multi-step · **Size:** L
- **Delivers:** FEAT-017 (core), FEAT-018, FEAT-020 (mode runtime)
- **Depends on:** `010.working-page`, `011.chat-panel`, `012.assistant-config-editor`

## Definition
Author, edit, browse and search codex entries (characters / locations /
facts) in the content pane; keep them embedded in the vector index
incrementally and via full rebuild; expose the codex to the assistant
(codex access + codex search tools); and let the assistant write/rewrite a
codex entry on the shared canvas from a chat. Codex entries are the first
mode-bearing subject, so this feature also builds the FEAT-020 mode
runtime on top of `011`'s loop scaffold: mode determination, mode-tool
gating, and sub-agent delegation.

## Scope
**In:** UC-069/070/071 (create/edit/browse/search); retrieval codex
corpus + incremental index maintenance (`retrieval.md`); UC-078 (assistant
reaches codex); FEAT-018 UC-076/077 (codex from chat, shared-canvas
write). Mode determination (codex `kind` → `edit-character` /
`edit-location` / `edit-fact`); mode-tool gating (mode `mode_tool`
allowlist → `pydantic_to_openai_tool`, built on `011`'s loop scaffold);
sub-agent delegation as synthetic tools (nested bounded `chat_with_tools`,
tools-only, one level deep); sub-agent model resolution via
`services/llm_servers.py`; register the codex access / search tools into
`TOOL_REGISTRY` as the first mode-gated tools.
**Out:** codex archive/restore (`017.codex-archive-restore`); codex
version history/restore (`019.codex-history`); cross-book copy (UC-075,
mapped later); chapter/summary/notes corpora (later stages). Chapter modes
`write-chapter` / `close-chapter` (the engine extends in `015`/`016`); the
still-deferred FEAT-013 pieces (SSE shared-canvas internals, context
assembly).

## Open questions for the planner
- The assistant/MCP half (codex access + search tools, shared-canvas SSE
  write) sits in the undesigned FEAT-013 subsystem — design during
  planning (see `011.chat-panel`). UC-078's relevance criterion is an
  open product `_TBD:` (challenge C27); `retrieval.md` deliberately picks
  no threshold.
- This feature is now a large L: codex CRUD + incremental embedding + the
  FEAT-020 mode-runtime engine + codex-from-chat shared-canvas write —
  strong candidate for a planner split (codex authoring vs. mode-runtime
  engine vs. codex-from-chat). Flagged, not pre-split at roadmap level.
<!-- roadmap:end -->
