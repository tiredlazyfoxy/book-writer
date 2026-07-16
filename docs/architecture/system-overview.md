# System Architecture Overview

BookWriter is a single FastAPI backend serving two React SPAs (User and Admin) plus a standalone Login page. In production nginx serves the static frontend builds and reverse-proxies API traffic to the backend. This document describes the component topology and the client↔server contract at the technology level; it does not describe any book/document domain.

## High-level topology

```
┌──────────────────────────────────────────────────────────┐
│                          nginx                            │
│   /        ──►  User SPA   (static build)                 │
│   /admin   ──►  Admin SPA  (static build)                 │
│   /login   ──►  Login page (static build)                 │
│   /api     ──►  FastAPI backend (reverse proxy)           │
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

A single async FastAPI application. HTTP handlers live in `routes/`, delegate to `services/` for business logic, which in turn call the session-free `db/` layer; `models/` holds SQLModel tables and Pydantic schemas. Endpoints are mounted under `/api/...` as `APIRouter`s. Persistence is SQLite (async, via SQLModel + aiosqlite); a LanceDB sidecar provides semantic search and is rebuilt on import rather than exported. LLM calls go out through the `llm-client` dependency. See `backend.md` for the layer rules.

### User SPA (served at `/`)

The author-facing application: TypeScript + React 19 + MobX, built by Vite. Uses React Router with path-param remount; each page loads its own data by URL id. Shows an admin link for admin-privileged users.

### Admin SPA (served at `/admin`)

User management and LLM-provider/server settings. Same tech stack and conventions as the User SPA, but a **separate Vite entry point and build**. Shares only the login/auth flow with the User SPA.

### Login page (served at `/login`)

A standalone entry point — a single screen with a small local form. No React Router, no `<Page>State` machinery. Produces the JWT that both SPAs carry.

### nginx

In production, nginx serves the three static builds and reverse-proxies `/api` to the backend, so everything is same-origin (no CORS needed in prod). In development nginx is not required; Vite's dev server proxies `/api` instead (see `dev-environment.md`).

## Client↔server contract

- **Transport**: REST over `/api/...`. Request and response bodies are JSON; every shape is a Pydantic model on the backend and a matching TypeScript DTO on the frontend.
- **Streaming**: Server-Sent Events (SSE) for long-running LLM generation. The frontend reads the stream with a `fetch`-based reader parsing `event:` / `data:` frames — **not** the browser `EventSource` API, because requests need `POST` bodies and a `Bearer` auth header. See `frontend.md` (`api/sse.ts`).
- **Auth**: JWT (HS256) in the `Authorization: Bearer <token>` header. The token is issued at login and carried by both SPAs. See `backend.md` for the per-user signing-key scheme.
- **Errors**: non-2xx responses carry a JSON body; the frontend normalizes them into a typed `ApiError` (status + message + optional structured field details).

## Ports

| Service | Dev port | Notes |
|---------|----------|-------|
| FastAPI backend (uvicorn) | 8185 | `http://localhost:8185` |
| Vite dev server (User + Admin + Login) | 8194 | proxies `/api` → `http://localhost:8185` |

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
