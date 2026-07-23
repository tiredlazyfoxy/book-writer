# System Architecture Overview

BookWriter is a single FastAPI backend serving four React SPAs (Shell, Working page, Reader, Admin) plus a standalone Login page. In production nginx serves the static frontend builds and reverse-proxies API traffic to the backend. This document describes the component topology and the client↔server contract.

**Book-domain coverage.** As of 2026-07-24 the book domain has a **first architectural pass**: the entity map for `FEAT-006..018` (`domain-model.md`), book-scoped authorization (`authorization.md`), the retrieval/embedding bridge (`retrieval.md`), and the frontend workspace topology described below (`frontend-workspace.md`). **Still uncovered: the internals of the FEAT-013 assistant** — context assembly, the tool/function-call protocol, the agent loop, sub-agent scoped checks (UC-088), the SSE event protocol for shared-canvas writes, prompt design, token budgets, model selection, and web-search wiring (UC-087). Those get their own design session before Stage 5. See `docs/product/` (start at `quick-reference.md`, then `relationships.md`) for the requirements source of record.

## High-level topology

```
┌──────────────────────────────────────────────────────────┐
│                          nginx                            │
│   /        ──►  Shell SPA        (static build)           │
│   /work    ──►  Working page SPA (static build)           │
│   /read    ──►  Reader SPA       (static build)           │
│   /admin   ──►  Admin SPA        (static build)           │
│   /login   ──►  Login page       (static build)           │
│   /api     ──►  FastAPI backend  (reverse proxy)          │
└──────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────┐
│                     FastAPI backend                       │
│                                                          │
│   routes/  ──►  services/  ──►  db/  ──►  models/         │
│                    │                                     │
│                    ▼                                     │
│           ┌──────────────────┐   ┌────────────────────┐  │
│           │ SQLite (SQLModel │   │ LanceDB sidecar    │  │
│           │  + aiosqlite)    │   │ (semantic search)  │  │
│           └──────────────────┘   └────────────────────┘  │
│                    │                                     │
│                    ▼                                     │
│           ┌──────────────────┐                          │
│           │ llm-client (llm) │  OpenAI-compatible /     │
│           │                  │  llama-swap backends     │
│           └──────────────────┘                          │
└──────────────────────────────────────────────────────────┘
```

## Components

### Backend (FastAPI)

A single async FastAPI application. HTTP handlers live in `routes/`, delegate to `services/` for business logic, which in turn call the session-free `db/` layer; `models/` holds SQLModel tables and Pydantic schemas. Endpoints are mounted under `/api/...` as `APIRouter`s. Persistence is SQLite (async, via SQLModel + aiosqlite); a LanceDB sidecar provides semantic search and is rebuilt on import rather than exported. LLM calls go out through the `llm-client` dependency. See `backend.md` for the layer rules, `domain-model.md` (the book-domain index, with the `domain-*.md` area files under it) for the entities, and `authorization.md` for the book-scoped access model.

### Shell SPA (served at `/`)

The author-facing application outside the working page: bookshelf (UC-021/022/030), book hub and chapter skeleton (UC-031..037), book settings (UC-023/024/026/027/028/042), and the read-only codex (UC-071) and continuity (UC-051, UC-089) views. TypeScript + React 19 + MobX, built by Vite. Uses React Router with path-param remount; each page loads its own data by URL id. Shows an admin link for admin-privileged users.

### Working page SPA (served at `/work`)

**Its own bundle.** The two-pane authoring workspace: navigator, content pane (the real editor for chapter bodies and codex entries, draft-until-saved), and a chat-pane slot that stays empty until FEAT-013 lands at Stage 5. It is separated because it is the heavy editor surface and the one most working sessions live in. See `frontend-workspace.md`.

### Reader SPA (served at `/read`)

ACT-006's surface, and **only** that: a book's table of contents and chapter text, read-only (UC-029). No codex, notes, flags, book state, settings or chat. It is a separate entry because a reader shares no surface with authoring, so the exclusion is enforced at build time rather than at runtime.

### Admin SPA (served at `/admin`)

Its current concerns are user management and LLM-provider/server settings — not an exhaustive list. FEAT-011 (content moderation) requires an admin read-only moderation view over book content with quarantine/destroy; that is a planned Stage-6 admin capability whose surface is not yet designed. `authorization.md` fixes only its boundary: separate, admin-only, read-only, and reaching the codex. Same tech stack and conventions as the Shell SPA, but a **separate Vite entry point and build**. Shares only the login/auth flow with the other SPAs.

### Login page (served at `/login`)

A standalone entry point — a single screen with a small local form. No React Router, no `<Page>State` machinery. Produces the JWT that every SPA carries.

### nginx

In production, nginx serves the five static builds and reverse-proxies `/api` to the backend, so everything is same-origin (no CORS needed in prod). In development nginx is not required; Vite's dev server proxies `/api` instead (see `dev-environment.md`).

## Frontend route map

The client-side routes each entry owns. Reasoning for the split and for the `work` entry's single-route shape is in `frontend-workspace.md`.

| Entry | Route | Surface |
|---|---|---|
| Shell | `/` | Bookshelf — owned (UC-022) + shared (UC-030) books; create (UC-021) |
| Shell | `/books/:bookId` | Book hub — chapter skeleton (UC-031..034), open/close/reopen (UC-035..037) |
| Shell | `/books/:bookId/settings` | Archive, transfer, co-authors, visibility, collaboration mode |
| Shell | `/books/:bookId/codex` | Read-only codex browse (UC-071), members-only |
| Shell | `/books/:bookId/continuity` | Read-only summaries + note changesets (UC-089, UC-051), members-only |
| Work | `/work/:bookId/state` (landing), `/chapters`, `/chapter/:id`, `/characters`, `/locations`, `/facts`, `/codex/:id`, `/variants`, `/variants/:chapterId`, `/chats` | The working page. The content-pane subject is a **nested route**; the shell is keyed on `:bookId` so it survives subject navigation. The active chat is **not** in the URL — the chat pane re-resolves it from server-persisted chats |
| Read | `/read/:bookId` | Table of contents (UC-029) |
| Read | `/read/:bookId/:chapterId` | Chapter text, read-only |
| Admin | `/admin/...` | Users, LLM servers, database |
| Login | `/login` | Sign in |

## Client↔server contract

- **Transport**: REST over `/api/...`. Request and response bodies are JSON; every shape is a Pydantic model on the backend and a matching TypeScript DTO on the frontend.
- **Streaming**: Server-Sent Events (SSE) for long-running LLM generation. The frontend reads the stream with a `fetch`-based reader parsing `event:` / `data:` frames — **not** the browser `EventSource` API, because requests need `POST` bodies and a `Bearer` auth header. See `frontend.md` (`api/sse.ts`).
- **Auth**: JWT (HS256) in the `Authorization: Bearer <token>` header. The token is issued at login and carried by both SPAs. See `backend.md` for the per-user signing-key scheme.
- **Errors**: non-2xx responses carry a JSON body; the frontend normalizes them into a typed `ApiError` (status + message + optional structured field details). Book-domain endpoints add two cases on top of the existing taxonomy: a private book the caller has no relationship to answers **404** (existence hiding), and a chapter write carrying a stale base version answers **409**. See `authorization.md` → "Failure modes" and `domain-chapter.md` → "Concurrency".

### First-run setup endpoints (feature 003)

The first real endpoints — the **front door of a cold, unconfigured instance** — live under `/api/auth`:

| Method | Path | Request | Success response |
|--------|------|---------|------------------|
| `GET` | `/api/auth/status` | — | `AuthStatusResponse{needs_setup: bool}` |
| `POST` | `/api/auth/setup/create` | JSON `CreateDBRequest{admin_username, password, password_confirm}` | `LoginResponse{token}` (auto sign-in) |
| `POST` | `/api/auth/setup/import` | multipart, field `file` | `AuthStatusResponse` (no token) |

`create` provisions the schema and the first admin, then returns a token so the caller is signed in immediately; `import` restores an archive and leaves the caller unauthenticated (they log in afterward). See `backend.md` for the deferred-schema startup lifecycle these endpoints drive.

## Ports

| Service | Dev port | Notes |
|---------|----------|-------|
| FastAPI backend (uvicorn) | 8185 | `http://localhost:8185` |
| Vite dev server (Shell + Work + Read + Admin + Login) | 8194 | proxies `/api` → `http://localhost:8185` |

In production both are behind nginx on a single origin.

## Request flow (typical)

1. Browser loads a static SPA from nginx (prod) or the Vite dev server (dev).
2. A page mounts, its `<Page>State` is created, and a mount `useEffect` fires a load through `src/api/<resource>.ts`.
3. The `api/` client attaches the `Bearer` token and calls `/api/...`.
4. nginx (prod) or the Vite proxy (dev) forwards `/api` to the backend.
5. A `routes/` handler parses the request, calls a `services/` function, which reads/writes via `db/`, and returns a Pydantic response.
6. The frontend receives typed JSON and updates observable state.

## Streaming flow (typical)

1. The frontend calls an SSE helper in the relevant `api/` module (a `POST` with `Bearer` auth).
2. The backend runs an LLM generation via `llm-client` and emits SSE frames as tokens/events arrive.
3. The `fetch`-reader parses `event:` / `data:` frames and pushes updates into observable state via `runInAction`, so the UI streams live.
4. The stream is cancellable with the same `AbortSignal` the rest of the `api/` layer uses.
