# Architecture Folder

Finalized architecture and design documentation for BookWriter. This is the authoritative ground truth other agents read; keep it precise and current.

## Scope

BookWriter is a multi-user app for LLM-assisted authoring of long-form texts. These docs cover **technology, structure, and conventions only** — the book/document domain model (entities and the generation pipeline) is deliberately deferred and must **not** be invented here.

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
- Be explicit about what is **out of scope** (notably: the book/document domain model).
- **Line limit: keep each file under ~400 lines.** If a topic outgrows that, split off the largest subsystem into its own cohesive file (e.g. carve a `frontend-*.md` deep-dive out of `frontend.md`) and link it from the parent and from this index. `quick-reference.md`, once it exists, is the one intentional exception — it is dense by design.
- Never silently overwrite an existing doc — surface changes so the diff is easy to review.
- Build/test commands are the root `CLAUDE.md`'s job; reference them, don't duplicate them here.
- Do not add a new top-level doc unilaterally — it must be called out in the briefing; otherwise surface the need in the hand-back.
