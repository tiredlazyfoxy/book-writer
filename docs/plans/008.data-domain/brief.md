# 008.data-domain — Book-domain persistence
<!-- roadmap:start -->
- **Stage:** 2.data-foundation · **Track:** multi-step · **Size:** L
- **Depends on:** `007.database-consistency`

## Definition
Stand up persistence for the whole book domain in one pass: every entity
table in the FEAT-006..018 map (Book, BookMember, Chapter, ChapterChange,
ChapterTextRevision, ChapterNoteChangeset, Flag, CodexEntry,
CodexEntryVersion, Chat, ChatMessage) gets a session-free `db/` module and a
JSONL import/export codec. Register `CodexEntry` as the first
`VECTOR_SOURCE_REGISTRY` source. Nothing user-visible ships — this is the
data floor every later domain feature stands on.

## Scope
**In:** all domain tables + keys drawn whole per `domain-model.md`; one
db-access module per entity; JSONL import(UPSERT)/export codecs for every
table; `TABLE_REGISTRY` ordering (FK order); codec round-trip; codex
vector-source registration (empty index).
**Out:** any route, service business-logic, or UI; incremental index
maintenance behaviour (wired when codex ships, `013.codex`); field-level
refinement of later-stage tables beyond what the map fixes.

## Open questions for the planner
- Confirm which later-stage nullable columns land now vs. deferred —
  `domain-model.md` "Landing the continuity columns early" says the Stage-4
  continuity columns land at Stage 2, nullable and unused.
<!-- roadmap:end -->
