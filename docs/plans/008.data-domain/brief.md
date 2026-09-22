# 008.data-domain — Book-domain persistence
<!-- roadmap:start -->
- **Stage:** 2.data-foundation · **Track:** multi-step · **Size:** L
- **Depends on:** `007.database-consistency`

## Definition
Stand up persistence for the whole book domain in one pass: every entity
table in the FEAT-006..018 map (Book, BookMember, Chapter, ChapterChange,
ChapterTextRevision, ChapterNoteChangeset, Flag, CodexEntry,
CodexEntryVersion, Chat, ChatMessage) gets a session-free `db/` module and a
JSONL import/export codec. Also stand up the five FEAT-020 instance-global
assistant-config tables (`AssistantMode`, `SubAgent`, `mode_tool`,
`subagent_tool`, `mode_subagent`) with the same per-table `db/` module +
codec treatment. Register `CodexEntry` as the first `VECTOR_SOURCE_REGISTRY`
source. Nothing user-visible ships — this is the data floor every later
domain feature stands on.

## Scope
**In:** all domain tables + keys drawn whole per `domain-model.md`; one
db-access module per entity; JSONL import(UPSERT)/export codecs for every
table; `TABLE_REGISTRY` ordering (FK order); codec round-trip; codex
vector-source registration (empty index). The FEAT-020 config tables:
`AssistantMode` (natural-key PK `key`, the fixed five, seeded), `SubAgent`
(snowflake, unique `name`, `disabled`, nullable `(llm_server_id,
model_name)` moving together), `mode_tool` / `subagent_tool` /
`mode_subagent` (surrogate snowflake PK + unique natural pair, `BookMember`
shape) — one `db/` module + codec each; `TABLE_REGISTRY` global-config block
before `books`: `users, llm_servers, assistant_modes, sub_agents,
mode_tools, subagent_tools, mode_subagents, books, …`; seed the five
`AssistantMode` rows (idempotent UPSERT on `key`).
**Out:** any route, service business-logic, or UI; incremental index
maintenance behaviour (wired when codex ships, `013.codex`); field-level
refinement of later-stage tables beyond what the map fixes. The
`TOOL_REGISTRY` catalogue itself (code, not a table, never exported —
belongs to the runtime, `011`/`013`); all admin CRUD / route / UI for
assistant config (→ `012.assistant-config-editor`).

## Open questions for the planner
- Confirm which later-stage nullable columns land now vs. deferred —
  `domain-model.md` "Landing the continuity columns early" says the Stage-4
  continuity columns land at Stage 2, nullable and unused.
- `AssistantMode`'s natural-key PK is a deliberate exception to the
  snowflake convention (justified in `assistant-config.md`) — confirm the
  codec emits/parses `key` verbatim; confirm the mode-seed lands here vs.
  `012.assistant-config-editor`.
<!-- roadmap:end -->
