# Architecture Folder

Finalized architecture and design documentation for BookWriter. This is the authoritative ground truth other agents read; keep it precise and current.

## Scope

BookWriter is a multi-user app for LLM-assisted authoring of long-form texts. These docs cover technology, structure and conventions — **and, since 2026-07-24, the book domain's architecture.**

**Covered now** (the Stage-2 architect gate, 2026-07-24): the entity map for `FEAT-006..018` drawn whole (`domain-model.md` — the index — plus the five `domain-*.md` area files), book-scoped authorization (`authorization.md`), the retrieval/embedding pipeline (`retrieval.md`), and the frontend workspace topology (`frontend-workspace.md`).

**One FEAT-013 slice now covered (2026-07-24): FEAT-020** — the admin assistant config (modes, sub-agents, the code-defined tool registry, the selection tables) **and** the runtime that consumes it (prompt composition, tool gating, the `chat_with_tools` loop, sub-agent delegation, model resolution). It lives in `assistant-config.md`.

**Not covered — do not infer it:** the **rest of the FEAT-013 assistant** (context/content assembly, the shared-canvas SSE protocol, the main-chat model selection, web search, token budgets). It is undesigned and gets its own session before Stage 5 — see `domain-chat.md` for the full boundary. `Chat` / `ChatMessage` appear in the entity map; the rest of their subsystem does not exist on paper.

The standing rule survives: don't invent the domain *model* here — derive it from `docs/product/`, and cite what you derived it from. A design doc realizing product requirements carries a header naming them:

```
**Realizes:** FEAT-013, UC-054, UC-078
```

Start from `docs/product/quick-reference.md` (the canonical id registry) and `docs/product/relationships.md` (the dependency graph, build order, accepted overlaps and conflicts — note the `FEAT-012 → FEAT-017` inversion). `features.md` holds the FEAT blocks only; **the dependency graph moved to `relationships.md` in product round 5.** Where a requirement carries a `_TBD:`, it is genuinely undecided: raise it, don't resolve it by choosing a design.

Where this architecture **diverged from** `docs/product/`, the divergence is recorded in `domain-model.md` → "Product divergences" — **four items**, all **reconciled by `/product-spec` round 7 (2026-07-24)** and retained there as decision history. One of them (CF1) resolves a coherence finding product left open. Never edit `docs/product/` to close one.

The root-level `product.md` is a human-facing business narrative, **not** development guidance — ignore it; the canonical product layer is `docs/product/`.

## Contents and reading order

For the document catalogue and reading order, see `README.md` (the canonical index). Note the backend layer is now an index plus a `backend/` sub-tree: `backend.md` holds the cross-cutting rules and decision history, with `backend/persistence.md`, `backend/auth-ids.md`, `backend/features.md` and `backend/book-domain.md` under it.

## Write-rules

- This folder holds **final, approved** documentation only. Drafts and planning live in `docs/plans/`.
- State decisions **with reasoning** — "we chose X because Y," never a bare assertion.
- Be explicit about what is **out of scope**, and about which product requirements a doc does *not* yet cover.
- **Cite product ids.** A doc designing for the book domain carries a `**Realizes:** FEAT-###, UC-###` header. `docs/product/` is read-only from here — never edit it to fit a design; if a requirement is wrong or missing, surface it for `/product-spec`.
- **Line limit: keep each file under ~400 lines.** If a topic outgrows that, split off the largest subsystem into its own cohesive file (e.g. carve a `frontend-*.md` deep-dive out of `frontend.md`) and link it from the parent and from this index. `quick-reference.md`, once it exists, is the one intentional exception — it is dense by design.
- Never silently overwrite an existing doc — surface changes so the diff is easy to review.
- Build/test commands are the root `CLAUDE.md`'s job; reference them, don't duplicate them here.
- Do not add a new top-level doc unilaterally — it must be called out in the briefing; otherwise surface the need in the hand-back.
