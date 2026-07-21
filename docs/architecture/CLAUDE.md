# Architecture Folder

Finalized architecture and design documentation for BookWriter. This is the authoritative ground truth other agents read; keep it precise and current.

## Scope

BookWriter is a multi-user app for LLM-assisted authoring of long-form texts. These docs cover **technology, structure, and conventions** — how the system is built.

The book/document domain is **no longer deferred**. It is specified in `docs/product/` (18 features, 198 requirement ids as of 2026-07-20) — but only as requirements: what must be true, never how. Its architecture is still undesigned. **`FEAT-006..018` currently have zero coverage in this folder.**

So the rule changes shape rather than disappearing: don't invent the domain *model* here — derive it from `docs/product/`, and cite what you derived it from. A design doc realizing product requirements carries a header naming them:

```
**Realizes:** FEAT-013, UC-054, UC-078
```

Start from `docs/product/quick-reference.md` (the canonical id registry) and `docs/product/features.md` (the spine and its dependency graph — note the recorded build order and the `FEAT-012 → FEAT-017` inversion). Where a requirement carries a `_TBD:`, it is genuinely undecided: raise it, don't resolve it by choosing a design.

The root-level `product.md` is a human-facing business narrative, **not** development guidance — ignore it; the canonical product layer is `docs/product/`.

## Contents

- `README.md` — project purpose, tech overview, reading order (the index).
- `system-overview.md` — component topology (backend, User SPA, Admin SPA, Login, nginx), the REST + SSE contract, ports, request and streaming flow.
- `backend.md` — 4-layer backend rules, dependency direction, typing discipline, the `pyproject.toml` dependency block, DB engine (async SQLite + `create_all` + `ALTER` migrations), LanceDB sidecar, config/secrets, JWT (per-user key) + bcrypt auth, the pytest/httpx harness.
- `frontend.md` — React/TypeScript/MobX/Mantine/Vite conventions, `src/` structure, the `api/` layer + SSE, theming, and the full MobX hard rules.
- `dev-environment.md` — ports, the `start.ps1` launcher, the Vite `/api` proxy, Docker Compose dev/prod + nginx, environment variables, DB-path override.
- `quick-reference.md` — *(not yet created)* a dense agent-first index of concrete endpoints, DTOs, and patterns. Add it once real endpoints and models exist.

## Reading order

1. `README.md` — the shape of the system.
2. `system-overview.md` — how the pieces connect and talk.
3. `backend.md` / `frontend.md` — read the side you're working in first.
4. `dev-environment.md` — to run, configure, or deploy.

## Write-rules

- This folder holds **final, approved** documentation only. Drafts and planning live in `docs/plans/`.
- State decisions **with reasoning** — "we chose X because Y," never a bare assertion.
- Be explicit about what is **out of scope**, and about which product requirements a doc does *not* yet cover.
- **Cite product ids.** A doc designing for the book domain carries a `**Realizes:** FEAT-###, UC-###` header. `docs/product/` is read-only from here — never edit it to fit a design; if a requirement is wrong or missing, surface it for `/product-spec`.
- **Line limit: keep each file under ~400 lines.** If a topic outgrows that, split off the largest subsystem into its own cohesive file (e.g. carve a `frontend-*.md` deep-dive out of `frontend.md`) and link it from the parent and from this index. `quick-reference.md`, once it exists, is the one intentional exception — it is dense by design.
- Never silently overwrite an existing doc — surface changes so the diff is easy to review.
- Build/test commands are the root `CLAUDE.md`'s job; reference them, don't duplicate them here.
- Do not add a new top-level doc unilaterally — it must be called out in the briefing; otherwise surface the need in the hand-back.
