# BookWriter — Architecture

BookWriter is a multi-user web application for **LLM-assisted authoring of long-form texts** — books and other large documents. Authors work in a browser SPA; an admin SPA manages users and LLM-provider settings; a FastAPI backend orchestrates persistence, authentication, and LLM calls.

This documentation set covers **technology, structure, and conventions only**. The book/document domain model — the concrete entities and the generation pipeline — is deliberately **out of scope here** and will be designed in a later session. Nothing in this folder should be read as prescribing domain entities.

## Tech overview

A Python 3.13 FastAPI (async) backend persists data in SQLite through the SQLModel ORM (async, via aiosqlite) with a LanceDB sidecar for semantic search. Authentication is JWT (HS256) with a **per-user signing key** and bcrypt password hashing. LLM communication is handled by the shared `llm-client` git dependency (OpenAI-compatible and llama-swap backends). The frontend is a Vite multi-page build producing two React 19 + TypeScript 5.8 SPAs (User and Admin) plus a standalone Login page, using MobX for state and Mantine for UI. The client talks to the backend over REST at `/api/...`, with Server-Sent Events for streaming responses.

## Documents

- `README.md` — this index: project purpose, tech overview, reading order.
- `system-overview.md` — component topology (backend, User SPA, Admin SPA, Login, nginx), the REST + SSE contract shape, ports, request and streaming flow.
- `backend.md` — the 4-layer backend rules, dependency direction, typing discipline, the `pyproject.toml` dependency block, DB engine approach, LanceDB sidecar, config/secrets pattern, JWT/bcrypt auth, and the pytest/httpx test harness.
- `frontend.md` — React/TypeScript/MobX/Mantine/Vite conventions, the `src/` structure, the `api/` layer and SSE pattern, theming, and the full MobX hard rules.
- `dev-environment.md` — ports, the `start.ps1` launcher, the Vite `/api` proxy, Docker Compose dev/prod with nginx, environment variables, and the DB-path override.

## Reading order

1. `README.md` — this file, for the shape of the system.
2. `system-overview.md` — how the pieces fit and talk to each other.
3. `backend.md` and `frontend.md` — the enforced conventions for each side; read the one you're working in first.
4. `dev-environment.md` — when you need to run, configure, or deploy the app.

## Rules

- This folder is for **final, approved** documentation only. Draft and planning docs belong in `docs/plans/`.
- Keep docs concise and current. See `CLAUDE.md` in this folder for write-rules and the per-file line limit.
