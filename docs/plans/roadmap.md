# Roadmap

BookWriter's foundation (FEAT-001..007, folders `001–007` + `fast/001`) is
delivered. The book domain (FEAT-006..019) was designed at the 2026-07-24
architect pass (`docs/architecture/domain-*.md`, `authorization.md`,
`retrieval.md`, `frontend-workspace.md`), so domain stages no longer carry an
`/architect` gate. The FEAT-020 slice of the assistant subsystem (config model
+ runtime: prompt composition, the tool/function-call protocol via
`chat_with_tools`, sub-agent delegation, sub-agent model resolution) is now
designed (`docs/architecture/assistant-config.md`). What remains undesigned in
**FEAT-013** — context/content assembly, the SSE shared-canvas write protocol,
web-search wiring, main-chat model selection, token budgeting — is resolved
during planning of the features that touch it (`011`, `013`, `018`, `019`, and
the drafting half of `016`) and reconciled back to `docs/architecture/` after.

No status column below — status is derived from folder state: `brief.md`
only = roadmapped, `+ status.md` = planned, all steps `done` + PASS =
delivered.

<!-- roadmap:start -->
## Stage map

| Stage | Goal | Exit criterion |
|---|---|---|
| 0 · Scaffold | Runnable walking skeleton through the whole stack | App boots; `npm run build` + `pytest` green; a health call flows browser→api/→FastAPI→layers |
| 1 · Foundation platform | The admin/auth platform stands | Operator bootstraps DB+admin; users log in; admin manages users, LLM servers, DB consistency |
| 2 · Data foundation & admin polish | Every book-domain entity is persisted and portable; the admin SPA nav is coherent | All FEAT-006..018 tables round-trip through gzipped JSONL export/import; codex registered as the first vector source; admin SPA left-menu / logout / switch-to-main-site work |
| 3 · Books, workspace & system prompts | An author manages books and works inside the two-pane workspace with chat | Create/manage books + co-authors/visibility; open the working page (navigator, book-state landing, content pane, restore buffer); manage chats and converse with the assistant (web search); edit book/chapter system prompts (placeholder); admin configures assistant modes, sub-agents & tools |
| 4 · Codex | The codex is authorable, searchable, and reachable by the assistant | Author/browse/search codex by kind; entries incrementally embedded; assistant reaches and writes codex from chat |
| 5 · Chapters (free mode) | Write a book chapter by chapter in free mode | Build a chapter skeleton, write chapters in blocks referencing the codex, close a chapter drafting its summary/notes/flags |
| 6 · Archive & history | Content is recoverable and its history is browsable | Archive/restore codex; browse chapter variants (view/compare/apply) and codex version history, surfaced in the content pane and via history tools |

## Stage 0 — Scaffold (briefed)

| Feature | Track | Size | Delivers | Depends on | Definition |
|---|---|---|---|---|---|
| `001.backend-scaffold` | multi-step | M | — | none | FastAPI backend as a runnable, testable 4-layer skeleton. |
| `002.frontend-scaffold` | multi-step | M | — | `001.backend-scaffold` | Vite MPA skeleton (3 entries) with MobX/Mantine/api-layer wired. |

## Stage 1 — Foundation platform (briefed)

| Feature | Track | Size | Delivers | Depends on | Definition |
|---|---|---|---|---|---|
| `003.first-run-bootstrap` | multi-step | M | FEAT-001 | `001.backend-scaffold`, `002.frontend-scaffold` | Bring an unconfigured instance to a usable state (create-DB+admin or import). |
| `004.authentication-session` | multi-step | M | FEAT-002 | `003.first-run-bootstrap` | Log in, hold a session, log out; expired/invalidated sessions force re-auth. |
| `005.user-management` | multi-step | M | FEAT-003 | `004.authentication-session` | Admin-gated account lifecycle: list, create, reset, role, disable. |
| `006.llm-server-connections` | multi-step | M/L | FEAT-004 | `005.user-management` | Admin registers/tests/manages LLM servers; probes models; designates embedding server+model. |
| `007.database-consistency` | multi-step | M/L | FEAT-005 | `006.llm-server-connections` | Schema-drift report + remediation; DB export/import; rebuild vector index. |

## Stage 2 — Data foundation & admin polish (briefed)

| Feature | Track | Size | Delivers | Depends on | Definition |
|---|---|---|---|---|---|
| `008.data-domain` | multi-step | L | — | `007.database-consistency` | Persist every book-domain entity + the five FEAT-020 assistant-config tables: one db module + JSONL codec per table; register codex as first vector source. |
| `fast/002.admin-ui-retune` | fast | S | — | `005.user-management` | Retune admin SPA nav: fix left menu, wire logout, add switch-to-main-site link. |

## Stage 3 — Books, workspace & system prompts (briefed)

| Feature | Track | Size | Delivers | Depends on | Definition |
|---|---|---|---|---|---|
| `009.books` | multi-step | L | FEAT-006, FEAT-007 | `008.data-domain` | Create/own/list/archive/transfer a book; manage co-authors and visibility. |
| `010.working-page` | multi-step | L | FEAT-013 (workspace shell) | `009.books` | Working-page SPA shell: navigator, book-state landing, draft-until-saved content pane with restore buffer. |
| `011.chat-panel` | multi-step | L | FEAT-013 (chat + assistant + web) | `010.working-page` | Live chat pane + assistant-loop scaffold: create/list/continue/archive chats; converse with the assistant; web search; `TOOL_REGISTRY` / `chat_with_tools` / prompt-composition framework. |
| `012.system-prompts-editor` | multi-step | M | FEAT-019 (placeholder) | `010.working-page`, `009.books` | Placeholder, author-facing only: edit a book's and a chapter's system prompt; spec/architecture to follow. |
| `020.assistant-config-editor` | multi-step | L | FEAT-020 | `008.data-domain` | Admin-only editor: five mode prompts + tool/sub-agent selection; sub-agent CRUD, disable, model assignment, tool selection. |

## Stage 4 — Codex (briefed)

| Feature | Track | Size | Delivers | Depends on | Definition |
|---|---|---|---|---|---|
| `013.codex` | multi-step | L | FEAT-017 (core), FEAT-018, FEAT-020 (mode runtime) | `010.working-page`, `011.chat-panel` | Author/edit/browse/search codex entries; incremental embedding; assistant reaches and writes codex from chat; FEAT-020 mode runtime (mode determination, tool gating, sub-agent delegation). |

## Stage 5 — Chapters (free mode) (briefed)

| Feature | Track | Size | Delivers | Depends on | Definition |
|---|---|---|---|---|---|
| `014.chapter-skeleton` | multi-step | M | FEAT-008 | `009.books` | Build a chapter skeleton: add/reorder/edit-sketch/remove a planned chapter. |
| `015.chapter-writing-free-mode` | multi-step | L | FEAT-009 | `014.chapter-skeleton`, `010.working-page` | Open/write/close/reopen a chapter in free mode via the block write path; 409 concurrency + restore-buffer reconciliation. |
| `016.chapter-close-continuity` | multi-step | L | FEAT-012, FEAT-016 (flags) | `015.chapter-writing-free-mode` | Close drafts and gates on approved summary/state-note changeset; view state notes/changeset; raise/resolve flags. |

## Stage 6 — Archive & history (briefed)

| Feature | Track | Size | Delivers | Depends on | Definition |
|---|---|---|---|---|---|
| `017.codex-archive-restore` | multi-step | M | FEAT-017 (UC-072) | `013.codex` | Archive/restore a codex entry; archive removes it from the vector index. |
| `018.chapter-history-variants` | multi-step | M/L | FEAT-014 | `015.chapter-writing-free-mode`, `010.working-page` | List/compare/apply a chapter's variants and prior revisions via the Variants navigator entry. |
| `019.codex-history` | multi-step | M | FEAT-017 (UC-073, UC-074) | `013.codex`, `010.working-page` | View a codex entry's edit history and restore an earlier version. |

## Build order (topological)

`001 → 002 → 003 → 004 → 005 → 006 → 007 → 008 → fast/002.admin-ui-retune →
009 → 010 → 011 → 012 → 020 → 013 → 014 → 015 → 016 → 017 → 018 → 019`

All dependencies point backward; acyclic. `fast/002.admin-ui-retune` depends
only on delivered foundation (`005.user-management`), so its position after
`008` is a sequencing choice, not a hard edge. `012.system-prompts-editor` is
placed before `013.codex` per the confirmed plan; `020.assistant-config-editor`
sits between them — its only hard edge is `008.data-domain` (far upstream), so
its Stage-3 position beside `012` (the admin half of "system prompts") is a
sequencing choice, not a hard edge. Numbers 008–019 (and `fast/002`) are
**allocated**, not indicative; `020` is likewise allocated.

## Mapped later (not in this reshape — numbers 019+ when mapped)

FEAT-010 proposal mode · FEAT-011 moderation · FEAT-015 book cloning ·
FEAT-016 full LLM consistency check (only the Flag entity/manual flags land in
`016.chapter-close-continuity`) · FEAT-019 book/chapter system prompts (beyond
the `012` placeholder editor) · UC-075 codex cross-book copy · FEAT-013
composing chapter blocks via chat (UC-054/055) · UC-088 scoped consistency
checks (the check itself; its sub-agent delegation plumbing now lands in
`013.codex`) · UC-025 admin ownership reassignment (unless folded into
`009.books`).

## Graph notes

- **Codex depends on chat:** `013.codex` depends on `011.chat-panel` because
  its chat-authoring half (FEAT-018) needs the assistant loop.
- `011.chat-panel`, `013.codex`, `018.chapter-history-variants`,
  `019.codex-history` (and the drafting half of `016`) each carry the
  **undesigned FEAT-013 assistant subsystem** — context/content assembly, the
  SSE shared-canvas event protocol, web search, main-chat model selection,
  token budgeting — as a planner open question; resolved during planning and
  reconciled to `docs/architecture/` after. No architect gate is placed on
  this. The tool/function-call protocol and sub-agent model selection are no
  longer in this set — designed in `assistant-config.md` (FEAT-020).
- The FEAT-020 mode runtime lands in `013.codex` (the first mode-bearing
  subjects — codex entries), not `011.chat-panel`; seeded modes plus the
  code-defined `TOOL_REGISTRY` let it run before `020`'s editor exists.
  FEAT-020 delivery spreads across `008` (config tables), `013` (mode
  runtime) and `020` (editor), with the loop scaffold laid in `011` and the
  runtime extended for chapter modes in `015`/`016`.
- `012.system-prompts-editor` is a **placeholder** — its spec and architecture
  are produced before it is planned (FEAT-019's authorization rule and
  `Realizes` headers are a deferred follow-up recorded in `domain-model.md`
  divergence 3).
- `fast/002.admin-ui-retune` is foundation polish (fixes the delivered admin
  SPA), grouped into Stage 2 for milestone purposes though it depends only on
  `005.user-management`; booked fast on the expectation it is one
  nav/logout pass.
- The book-domain architecture (`domain-*.md`, `authorization.md`,
  `retrieval.md`, `frontend-workspace.md`) is designed as of 2026-07-24; the
  old ⛔ architect gates on Stages 2–6 are dropped. Only the FEAT-013 assistant
  internals remain undesigned, handled as planner open questions per feature
  above.
<!-- roadmap:end -->
