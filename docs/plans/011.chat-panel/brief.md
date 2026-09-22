# 011.chat-panel — Chat pane & assistant
<!-- roadmap:start -->
- **Stage:** 3.workspace · **Track:** multi-step · **Size:** L
- **Delivers:** FEAT-013 (chat + assistant + web)
- **Depends on:** `010.working-page`

## Definition
Make the chat pane live: create/list/pick/continue/archive chats (private
to their author), render the conversation, converse with the assistant,
and let the assistant consult the web (google-search MCP). This is the
first feature to build the FEAT-013 assistant subsystem — the chat surface
plus the assistant-loop scaffold (`TOOL_REGISTRY`, `chat_with_tools`,
system-prompt composition framework) that later mode-bearing features
build on.

## Scope
**In:** UC-053 (start a chat), UC-081/082 (manage/continue, archive),
UC-087 (web search); US-056/061/095/096/101. Chat CRUD backend +
chat-pane UI; the assistant request/response loop and the web-search tool.
The assistant-loop scaffold: `TOOL_REGISTRY` (`ToolDef` + module-level
list, like `VECTOR_SOURCE_REGISTRY`) with web search as its first tool; the
`chat_with_tools` loop; system-prompt composition framework
`base → mode → book → chapter` (empty layers skipped) — at this feature
only the base + book layers are ever non-empty (no mode subject, no
chapter subject yet).
**Out:** shared-canvas writes into chapters/codex (`013.codex` does
codex-from-chat; chapter composition-from-chat is mapped later); scoped
consistency checks (UC-088); meaning-search over the book (arrives with
codex/chapters). Everything mode-keyed: mode determination, mode-tool
gating, sub-agent delegation, sub-agent model resolution — all deferred to
`013.codex`, the first feature with a mode-bearing subject.

## Open questions for the planner
- The still-deferred FEAT-013 pieces: context/content assembly, the SSE
  shared-canvas write protocol, web-search-tool internals, main-chat model
  selection, token budgeting. These are made during planning and
  reconciled to `docs/architecture/` after. Model selection is an open
  product `_TBD:`.
- Record the `chat_with_tools`-now / manual-SSE-loop-later seam — the loop
  is a replaceable interior, swappable when the shared-canvas SSE protocol
  arrives, without touching the config model, tool registry, gating or
  delegation.
<!-- roadmap:end -->
