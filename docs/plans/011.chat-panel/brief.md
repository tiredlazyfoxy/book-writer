# 011.chat-panel — Chat pane & assistant
<!-- roadmap:start -->
- **Stage:** 3.workspace · **Track:** multi-step · **Size:** L
- **Delivers:** FEAT-013 (chat + assistant + web)
- **Depends on:** `010.working-page`

## Definition
Make the chat pane live: create/list/pick/continue/archive chats (private
to their author), render the conversation, converse with the assistant,
and let the assistant consult the web (google-search MCP). This is the
first feature to build the FEAT-013 assistant subsystem.

## Scope
**In:** UC-053 (start a chat), UC-081/082 (manage/continue, archive),
UC-087 (web search); US-056/061/095/096/101. Chat CRUD backend +
chat-pane UI; the assistant request/response loop and the web-search tool.
**Out:** shared-canvas writes into chapters/codex (`013.codex` does
codex-from-chat; chapter composition-from-chat is mapped later); scoped
consistency checks (UC-088); meaning-search over the book (arrives with
codex/chapters).

## Open questions for the planner
- The FEAT-013 assistant subsystem — context assembly, the
  tool/function-call protocol (the user's "MCP" framing, not yet in the
  arch docs), the agent loop, the SSE shared-canvas event protocol, model
  selection, web-search wiring — is undesigned (`domain-chat.md` "Out of
  scope"). These decisions are made during planning and reconciled to
  `docs/architecture/` after. Model selection is an open product `_TBD:`.
<!-- roadmap:end -->
