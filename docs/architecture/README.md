# BookWriter — Architecture

BookWriter is a multi-user web application for **LLM-assisted authoring of long-form texts** — books and other large documents. Authors work in browser SPAs; an admin SPA manages users and LLM-provider settings (and, per FEAT-011, will gain a moderation surface whose architecture is not yet designed); a FastAPI backend orchestrates persistence, authentication, and LLM calls.

**What this folder covers, as of 2026-07-29.** Technology, structure and conventions — *and* the book domain: the entity map for `FEAT-006..018`, book-scoped authorization, the retrieval/embedding pipeline, the frontend workspace topology, and — since features `009.books`, `011.chat-panel`, `012.assistant-config-editor`, `013.codex` and `021.per-author-system-prompt` shipped — the as-built record of everything they delivered.

**A substantial part of the FEAT-013 assistant is now designed *and* built.** `assistant-config.md` holds the FEAT-020 **configuration model** (modes, sub-agents, the code-defined tool registry, the selection tables). `assistant-runtime.md` holds the **runtime**: mode determination, the four-layer system-prompt composition, tool gating, the `chat_with_tools` loop, sub-agent delegation, **per-chat model selection**, **web search**, the five-frame SSE vocabulary, and the **shared-canvas write protocol for codex entries**.

**What genuinely remains deferred — do not infer it:**

- **Context / content assembly** — building, ordering, ranking and truncating retrieved book/chapter/codex material into the prompt (US-057, UC-085/086/078 internals). A working chat pane invites the reading that the context model shipped with it; it did not.
- **The shared-canvas write protocol for chapters** (UC-055) — the codex half shipped, the chapter half has not.
- **Token-level canvas streaming** — the draft currently arrives whole, not token by token.
- **Token budgeting and truncation.**

See `domain-chat.md` for the full boundary and `assistant-runtime.md` → "Out of scope" for the same list with its reasoning.

`docs/product/` remains the requirements source of record — what must be true, never how.

## Tech overview

A Python 3.13 FastAPI (async) backend persists data in SQLite through the SQLModel ORM (async, via aiosqlite) with a LanceDB sidecar for semantic search. Authentication is JWT (HS256) with a **per-user signing key** and bcrypt password hashing. LLM communication is handled by the shared `llm-client` git dependency (OpenAI-compatible and llama-swap backends). The frontend is a Vite multi-page build producing React 19 + TypeScript 5.8 SPAs — Shell, Working page, Reader and Admin — plus a standalone Login page, using MobX for state and Mantine for UI. The client talks to the backend over REST at `/api/...`, with Server-Sent Events for streaming responses.

Two gaps between that description and the repository, stated here so no one reads them as shipped: the **reader (`read/`) entry is a stub** — a table-of-contents placeholder with no router and no gate, landed only so the fifth Rollup input had something to serve — and **nginx and both Docker Compose files do not exist in this repository yet**. The serving layer is designed but not built; see `dev-environment.md`.

## Documents

- `docs/product/` — the requirements source of record that this architecture realizes; start at `quick-reference.md` (the canonical id registry) and `relationships.md` (the dependency graph and build order).
- `README.md` — this index: project purpose, tech overview, reading order.
- `quick-reference.md` — the **dense, agent-first index of concrete endpoints, DTOs, tables and patterns as they land**, with the status taxonomy for each route family. Terse by design and the **one file exempt from the folder's ~400-line limit**. Every endpoint/DTO table referenced from `backend/features.md` lives here. Not to be confused with `docs/product/quick-reference.md`, the product id registry.
- `system-overview.md` — component topology (backend, the four SPAs, Login, nginx), the frontend route map, the REST + SSE contract shape, ports, request and streaming flow.
- `backend.md` — the backend **index**: the 4-layer rules, dependency direction, typing discipline, the `pyproject.toml` dependency block, the LLM-client rule, logging, the pytest/httpx test harness, and the backend decision history. The detail lives in four area files under `backend/`:
  - `backend/persistence.md` — relational storage & the deferred-schema startup lifecycle, gzip-JSONL import/export (codecs, `TABLE_REGISTRY`, credential policy), the LanceDB vector sidecar, and config/secrets.
  - `backend/auth-ids.md` — the per-user-key JWT + bcrypt auth scheme and the system-wide snowflake entity-ID strategy (spec, string-at-JSON-boundary serialization, migration stance).
  - `backend/features.md` — the as-shipped records for `User`/`LlmServer`, LLM-server connections (FEAT-004), and database consistency & management (FEAT-005).
  - `backend/book-domain.md` — the book domain's backend impact: module map, the ~12-codec table registry, Stage-4-columns-at-Stage-2, and the 409 concurrency rule.
- `frontend.md` — React/TypeScript/MobX/Mantine/Vite conventions, the `src/` structure, the `api/` layer and SSE pattern, theming, and the full MobX hard rules.

**Book domain (2026-07-24):**

- `domain-model.md` — **the index**: scope, the whole entity map, the conventions every entity inherits, the recorded product divergences and gaps. Start here.
  - `domain-book.md` — `Book`, `BookMember`, the book lifecycle, visibility, the moderation fields, cloning.
  - `domain-chapter.md` — `Chapter` and its four-state machine (`planned` → `open` → `closing` → `closed`), `ChapterChange` (the one write path), variants-as-apply, `ChapterTextRevision`, the `version` / 409 concurrency rules.
  - `domain-continuity.md` — note changesets, the active note set, summaries and their `draft` / `approved` / `stale` status, flags ("warnings").
  - `domain-codex.md` — `CodexEntry` and its version history.
  - `domain-chat.md` — `Chat` / `ChatMessage`, **entities only**, with the deferred-subsystem boundary (points at `assistant-config.md` for the slice now designed).
  - `assistant-config.md` — **FEAT-020, the configuration model only**: `AssistantMode`, `SubAgent`, the code-defined `TOOL_REGISTRY`, the three selection tables, the replace-set save semantics and the admin write-edge validation. Instance-global admin config, not `Book`-rooted.
  - `assistant-runtime.md` — **the runtime that consumes that configuration**: the as-built modules, mode determination and the `TurnRequest` wire shape, the four-layer prompt composition, the three-case tool gating, the `chat_with_tools` protocol, sub-agent delegation, model resolution, the five-frame SSE vocabulary, and the codex shared-canvas write. Carved out of `assistant-config.md` on 2026-07-29.
- `authorization.md` — roles, the book-access enforcement point, the capability × role matrix, the two row-ownership rules (chats and per-author prompts), and the admin-only global assistant config (FEAT-020).
- `retrieval.md` — the embedding/vector pipeline: which corpora are indexed when, chunking, incremental maintenance, dimension handling, failure modes.
- `frontend-workspace.md` — the five-entry map, the per-entry route map, the working page and its three panes.
  - `frontend-work-drafts.md` — the working page's **device-local draft tier**: the restore buffer, the three module-state members (`restoreBuffer.ts` / `activeChat.ts` / `contentSubject.ts`), the canvas target registry and reconciliation. Carved out of `frontend-workspace.md` on 2026-07-29.

**Operations:**

- `dev-environment.md` — ports, the `start.ps1` launcher, the Vite `/api` proxy, Docker Compose dev/prod with nginx, environment variables, and the DB-path override.

## Reading order

1. `README.md` — this file, for the shape of the system.
2. `system-overview.md` — how the pieces fit and talk to each other.
3. `backend.md` (the backend index, with its `backend/*.md` area files) and `frontend.md` — the enforced conventions for each side; read the one you're working in first.
4. **Working in the book domain?** `domain-model.md` first — it is the index and holds the shape everything else assumes — then the `domain-*.md` file for the area you're touching, then `authorization.md`, then `retrieval.md` or `frontend-workspace.md` depending on the side you're on.
5. **Working on the assistant?** The pair splits by concern: `assistant-config.md` if you are touching the **admin editor, the stored configuration or the tool catalogue**; `assistant-runtime.md` if you are touching **a turn** — prompt composition, tool gating, delegation, model resolution or an SSE frame. `domain-chat.md` carries the entities and the deferred boundary.
6. **Working on the working page?** `frontend-workspace.md` for entries, routes and panes; `frontend-work-drafts.md` if you are touching **unsaved state** — the restore buffer, the active-chat pointer, the canvas target registry or reconciliation.
7. **Need a concrete endpoint, DTO, column or status code?** `quick-reference.md` — it is the index, and it is faster than reading the design doc that explains why.
8. `dev-environment.md` — when you need to run, configure, or deploy the app.

## Rules

- This folder is for **final, approved** documentation only. Draft and planning docs belong in `docs/plans/`.
- Keep docs concise and current. See `CLAUDE.md` in this folder for write-rules and the per-file line limit.
