# BookWriter — Architecture

BookWriter is a multi-user web application for **LLM-assisted authoring of long-form texts** — books and other large documents. Authors work in browser SPAs; an admin SPA manages users and LLM-provider settings (and, per FEAT-011, will gain a moderation surface whose architecture is not yet designed); a FastAPI backend orchestrates persistence, authentication, and LLM calls.

**What this folder covers, as of 2026-07-24.** Technology, structure and conventions — *and*, since the Stage-2 architect gate, a **first design pass over the book domain**: the entity map for `FEAT-006..018`, book-scoped authorization, the retrieval/embedding pipeline, and the frontend workspace topology.

**What is still uncovered: the internals of the FEAT-013 assistant.** Context assembly, the tool/function-call protocol, the agent loop, sub-agent scoped checks (UC-088), the SSE event protocol for shared-canvas writes, prompt design, token budgets, model selection, and web-search wiring (UC-087) are undesigned and get their own session before Stage 5. The `Chat` / `ChatMessage` entities are in the map; their subsystem is not. Do not infer it.

`docs/product/` remains the requirements source of record — what must be true, never how.

## Tech overview

A Python 3.13 FastAPI (async) backend persists data in SQLite through the SQLModel ORM (async, via aiosqlite) with a LanceDB sidecar for semantic search. Authentication is JWT (HS256) with a **per-user signing key** and bcrypt password hashing. LLM communication is handled by the shared `llm-client` git dependency (OpenAI-compatible and llama-swap backends). The frontend is a Vite multi-page build producing React 19 + TypeScript 5.8 SPAs — Shell, Working page, Reader and Admin — plus a standalone Login page, using MobX for state and Mantine for UI. The client talks to the backend over REST at `/api/...`, with Server-Sent Events for streaming responses.

## Documents

- `docs/product/` — the requirements source of record that this architecture realizes; start at `quick-reference.md` (the canonical id registry) and `relationships.md` (the dependency graph and build order).
- `README.md` — this index: project purpose, tech overview, reading order.
- `system-overview.md` — component topology (backend, the four SPAs, Login, nginx), the frontend route map, the REST + SSE contract shape, ports, request and streaming flow.
- `backend.md` — the 4-layer backend rules, dependency direction, typing discipline, the `pyproject.toml` dependency block, DB engine approach, LanceDB sidecar, config/secrets pattern, JWT/bcrypt auth, the pytest/httpx test harness, and the book domain's backend impact (module map, registries, the 409 concurrency rule).
- `frontend.md` — React/TypeScript/MobX/Mantine/Vite conventions, the `src/` structure, the `api/` layer and SSE pattern, theming, and the full MobX hard rules.

**Book domain (2026-07-24):**

- `domain-model.md` — **the index**: scope, the whole entity map, the conventions every entity inherits, the recorded product divergences and gaps. Start here.
  - `domain-book.md` — `Book`, `BookMember`, the book lifecycle, visibility, the moderation fields, cloning.
  - `domain-chapter.md` — `Chapter` and its four-state machine (`planned` → `open` → `closing` → `closed`), `ChapterChange` (the one write path), variants-as-apply, `ChapterTextRevision`, the `version` / 409 concurrency rules.
  - `domain-continuity.md` — note changesets, the active note set, summaries and their `draft` / `approved` / `stale` status, flags ("warnings").
  - `domain-codex.md` — `CodexEntry` and its version history.
  - `domain-chat.md` — `Chat` / `ChatMessage`, **entities only**, with the deferred-subsystem boundary.
- `authorization.md` — roles, the book-access enforcement point, and the capability × role matrix.
- `retrieval.md` — the embedding/vector pipeline: which corpora are indexed when, chunking, incremental maintenance, dimension handling, failure modes.
- `frontend-workspace.md` — the five-entry map, the per-entry route map, the working page, and the restore buffer.

**Operations:**

- `dev-environment.md` — ports, the `start.ps1` launcher, the Vite `/api` proxy, Docker Compose dev/prod with nginx, environment variables, and the DB-path override.

## Reading order

1. `README.md` — this file, for the shape of the system.
2. `system-overview.md` — how the pieces fit and talk to each other.
3. `backend.md` and `frontend.md` — the enforced conventions for each side; read the one you're working in first.
4. **Working in the book domain?** `domain-model.md` first — it is the index and holds the shape everything else assumes — then the `domain-*.md` file for the area you're touching, then `authorization.md`, then `retrieval.md` or `frontend-workspace.md` depending on the side you're on.
5. `dev-environment.md` — when you need to run, configure, or deploy the app.

## Rules

- This folder is for **final, approved** documentation only. Draft and planning docs belong in `docs/plans/`.
- Keep docs concise and current. See `CLAUDE.md` in this folder for write-rules and the per-file line limit.
