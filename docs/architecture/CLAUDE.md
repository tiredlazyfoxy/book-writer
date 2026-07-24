# Architecture Folder

Finalized architecture and design documentation for BookWriter. This is the authoritative ground truth other agents read; keep it precise and current.

## Scope

BookWriter is a multi-user app for LLM-assisted authoring of long-form texts. These docs cover technology, structure and conventions — **and, since 2026-07-24, the book domain's architecture.**

**Covered now** (the Stage-2 architect gate, 2026-07-24): the entity map for `FEAT-006..018` drawn whole (`domain-model.md` — the index — plus the five `domain-*.md` area files), book-scoped authorization (`authorization.md`), the retrieval/embedding pipeline (`retrieval.md`), and the frontend workspace topology (`frontend-workspace.md`).

**Not covered — do not infer it:** the **internals of the FEAT-013 assistant**. Context assembly, the tool/function-call protocol, the agent loop, sub-agent scoped checks (UC-088), the SSE event protocol for shared-canvas writes, prompt design, token budgets, model selection, and web-search wiring (UC-087) are undesigned and get their own session before Stage 5. `Chat` / `ChatMessage` appear in the entity map (`domain-chat.md`); their subsystem does not exist on paper.

The standing rule survives: don't invent the domain *model* here — derive it from `docs/product/`, and cite what you derived it from. A design doc realizing product requirements carries a header naming them:

```
**Realizes:** FEAT-013, UC-054, UC-078
```

Start from `docs/product/quick-reference.md` (the canonical id registry) and `docs/product/relationships.md` (the dependency graph, build order, accepted overlaps and conflicts — note the `FEAT-012 → FEAT-017` inversion). `features.md` holds the FEAT blocks only; **the dependency graph moved to `relationships.md` in product round 5.** Where a requirement carries a `_TBD:`, it is genuinely undecided: raise it, don't resolve it by choosing a design.

Where this architecture **diverged from** `docs/product/`, the divergence is recorded in `domain-model.md` → "Product divergences" — **four items**, all **reconciled by `/product-spec` round 7 (2026-07-24)** and retained there as decision history. One of them (CF1) resolves a coherence finding product left open. Never edit `docs/product/` to close one.

The root-level `product.md` is a human-facing business narrative, **not** development guidance — ignore it; the canonical product layer is `docs/product/`.

## Contents

- `README.md` — project purpose, tech overview, reading order (the index).
- `system-overview.md` — component topology (backend, the four SPAs, Login, nginx), the frontend route map, the REST + SSE contract, ports, request and streaming flow.
- `backend.md` — 4-layer backend rules, dependency direction, typing discipline, the `pyproject.toml` dependency block, DB engine (async SQLite + `create_all` + `ALTER` migrations), LanceDB sidecar, config/secrets, JWT (per-user key) + bcrypt auth, the pytest/httpx harness, and the book domain's backend impact.
- `frontend.md` — React/TypeScript/MobX/Mantine/Vite conventions, `src/` structure, the `api/` layer + SSE, theming, and the full MobX hard rules.
- `domain-model.md` — **the book-domain index**: scope, the whole entity map, inherited conventions, the recorded divergences from `docs/product/`, and the recorded gaps. Every `domain-*.md` links back to it.
  - `domain-book.md` — `Book`, `BookMember`, the book lifecycle state machine, visibility, the moderation fields, the system-prompt fields, `active_notes`, cloning.
  - `domain-chapter.md` — `Chapter` and its four-state machine (`planned` → `open` → `closing` → `closed`), CF1, `ChapterChange` (the unified write path), placement, variants-as-apply, `ChapterTextRevision`, the `version` / 409 / CF-r6 concurrency rules.
  - `domain-continuity.md` — `ChapterNoteChangeset`, the active note set, the summary lifecycle and the `draft` / `approved` / `stale` continuity status, `Flag` (author-facing: "warning").
  - `domain-codex.md` — `CodexEntry`, `CodexEntryVersion`, kinds/naming/archival/history/copy.
  - `domain-chat.md` — `Chat` / `ChatMessage`, **entities only**; states the deferred-subsystem boundary in full.
- `authorization.md` — book-scoped roles, the enforcement point, the capability × role matrix, failure modes.
- `retrieval.md` — the embedding/vector pipeline: corpora, chunking, incremental maintenance, dimensions, failure modes.
- `frontend-workspace.md` — the five Vite entries, the route map, the working page, the restore buffer.
- `dev-environment.md` — ports, the `start.ps1` launcher, the Vite `/api` proxy, Docker Compose dev/prod + nginx, environment variables, DB-path override.
- `quick-reference.md` — a dense agent-first index of concrete endpoints, DTOs, and patterns **as they land**. It indexes shipped code, not design intent, so nothing from the 2026-07-24 design pass is in it yet; append new endpoints/DTOs here as each book-domain feature ships.

## Reading order

1. `README.md` — the shape of the system.
2. `system-overview.md` — how the pieces connect and talk.
3. `backend.md` / `frontend.md` — read the side you're working in first.
4. Book-domain work: `domain-model.md` (the index) first, then the `domain-*.md` for your area, then `authorization.md`, then `retrieval.md` or `frontend-workspace.md`.
5. `dev-environment.md` — to run, configure, or deploy.

## Write-rules

- This folder holds **final, approved** documentation only. Drafts and planning live in `docs/plans/`.
- State decisions **with reasoning** — "we chose X because Y," never a bare assertion.
- Be explicit about what is **out of scope**, and about which product requirements a doc does *not* yet cover.
- **Cite product ids.** A doc designing for the book domain carries a `**Realizes:** FEAT-###, UC-###` header. `docs/product/` is read-only from here — never edit it to fit a design; if a requirement is wrong or missing, surface it for `/product-spec`.
- **Line limit: keep each file under ~400 lines.** If a topic outgrows that, split off the largest subsystem into its own cohesive file (e.g. carve a `frontend-*.md` deep-dive out of `frontend.md`) and link it from the parent and from this index. `quick-reference.md`, once it exists, is the one intentional exception — it is dense by design.
- Never silently overwrite an existing doc — surface changes so the diff is easy to review.
- Build/test commands are the root `CLAUDE.md`'s job; reference them, don't duplicate them here.
- Do not add a new top-level doc unilaterally — it must be called out in the briefing; otherwise surface the need in the hand-back.
