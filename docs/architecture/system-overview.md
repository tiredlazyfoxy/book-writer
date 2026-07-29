# System Architecture Overview

BookWriter is a single FastAPI backend serving four React SPAs (Shell, Working page, Reader, Admin) plus a standalone Login page. In production nginx serves the static frontend builds and reverse-proxies API traffic to the backend. This document describes the component topology and the client↔server contract.

**Book-domain coverage.** As of 2026-07-29 the book domain is designed whole (`domain-model.md`, `authorization.md`, `retrieval.md`, `frontend-workspace.md` + `frontend-work-drafts.md`) and partly **built**: books and membership, the chat panel and its streaming turn, the FEAT-020 admin config editor, the codex with its retrieval pipeline, and the per-author system prompt. The FEAT-013 assistant is now covered across two files — `assistant-config.md` (the configuration model) and `assistant-runtime.md` (mode determination, prompt composition, tool gating, the tool/agent loop, sub-agent delegation, **per-chat model selection**, **web search**, the five SSE frames, and the **shared-canvas write for codex entries**). **Still uncovered — do not infer it:** context / content assembly, the shared-canvas protocol for **chapters** (UC-055), token-level canvas streaming, and token budgeting. See `domain-chat.md` for the full boundary, and `docs/product/` (start at `quick-reference.md`, then `relationships.md`) for the requirements source of record.

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

**Its own bundle.** The three-region authoring workspace: navigator, content pane (the real editor, draft-until-saved) and chat pane. As built it carries the Book-state landing view, the codex list and entry pages, and a **live streaming chat pane** (list, per-chat model and sampling settings, transcript, collapsible thinking, retry) — the chat-pane slot is no longer a placeholder. Chapter and variant subjects are still placeholders. It is separated because it is the heavy editor surface and the one most working sessions live in. See `frontend-workspace.md` for entries/routes/panes and `frontend-work-drafts.md` for the draft tier.

### Reader SPA (served at `/read`)

ACT-006's surface, and **only** that: a book's table of contents and chapter text, read-only (UC-029). No codex, notes, flags, book state, settings or chat. It is a separate entry because a reader shares no surface with authoring, so the exclusion is enforced at build time rather than at runtime.

**As built it is a stub** — a table-of-contents placeholder with **no router and no gate** (feature 010 landed it only so the fifth Rollup input had something to serve). What enforces UC-029's exclusion list today is the **backend** `ReaderBookResponse` projection alone (feature 009). Whoever builds the reader entry inherits both halves and must not assume the frontend gate already exists.

### Admin SPA (served at `/admin`)

Its current concerns are user management, LLM-provider/server settings, database administration, and — since feature 012 — the FEAT-020 **assistant configuration** (modes and sub-agents). Not an exhaustive list. FEAT-011 (content moderation) requires an admin read-only moderation view over book content with quarantine/destroy; that is a planned Stage-6 admin capability whose surface is not yet designed. `authorization.md` fixes only its boundary: separate, admin-only, read-only, and reaching the codex. Same tech stack and conventions as the Shell SPA, but a **separate Vite entry point and build**. Shares only the login/auth flow with the other SPAs.

### Login page (served at `/login`)

A standalone entry point — a single screen with a small local form. No React Router, no `<Page>State` machinery. Produces the JWT that every SPA carries.

### nginx — designed, not yet created

In production, nginx serves the five static builds and reverse-proxies `/api` to the backend, so everything is same-origin (no CORS needed in prod). In development nginx is not required; Vite's dev server proxies `/api` instead.

**`nginx/` and both `docker-compose*.yml` are absent from this repository** — verified at feature 010. The topology diagram above is the intended shape, not a description of files on disk. Consequence to carry: the `/work` and `/read` static roots must be added **when that serving layer is first created**, not retrofitted afterwards. See `dev-environment.md`.

## Frontend route map

The client-side routes each entry owns, with what is **built** marked. Reasoning for the split and the full per-entry tables are in `frontend-workspace.md`.

| Entry | Route | Surface | Built? |
|---|---|---|---|
| Shell | `/` | Bookshelf — owned (UC-022) + shared (UC-030) books; create (UC-021) | **yes** (009) |
| Shell | `/books/:bookId` | Book hub — chapter skeleton (UC-031..034), open/close/reopen (UC-035..037) | no |
| Shell | `/books/:bookId/settings` | Archive, transfer, co-authors, visibility, collaboration mode, **the caller's own system prompt** (021) | **yes** (009, 021) |
| Shell | `/books/:bookId/codex` | Read-only codex browse (UC-071), members-only | no |
| Shell | `/books/:bookId/continuity` | Read-only summaries + note changesets (UC-089, UC-051), members-only | no |
| Work | `/work/:bookId/state` (landing) | Book state (UC-091), **plus the caller's own system prompt** (021) | **yes** (010, 021) |
| Work | `/work/:bookId/characters`, `/locations`, `/facts` | Codex lists, one per `kind` | **yes** (013) |
| Work | `/work/:bookId/codex/new?kind=<character\|location\|fact>` | A **blank** codex entry — UC-076 needs one openable before any row exists, and `/codex/:id` cannot express "no id yet"; declared **ahead of** `codex/:id` | **yes** (013) |
| Work | `/work/:bookId/codex/:id` | One codex entry | **yes** (013) |
| Work | `/work/:bookId/chapters`, `/chapter/:id`, `/variants`, `/variants/:chapterId` | Chapter and variant subjects | no — placeholders |
| Work | `/work/:bookId/chats` | **Redirect only**, to `/state` | **yes** (011) |
| Read | `/read/:bookId`, `/read/:bookId/:chapterId` | Table of contents + chapter text, read-only (UC-029) | no — the entry is a **stub**, no router, no gate |
| Admin | `/admin/users`, `/llm-servers`, `/database` | Users, LLM servers, database | **yes** (005–007) |
| Admin | `/admin/assistant-modes`, `/admin/sub-agents` | FEAT-020 mode editor and sub-agent management — two **flat** routes beside the existing three | **yes** (012) |
| Login | `/login` | Sign in | **yes** |

- **The content-pane subject is a nested route**; the workspace shell is keyed on `:bookId` so it survives subject navigation.
- **The active chat is not in the URL at all.** The chat pane re-resolves it from a device-local per-book pointer, falling back to the most recent chat by timestamp — chats are server-persisted, so a remount costs a reload, not a conversation.
- **`/work/:bookId/chats` is a redirect, and the Chats navigator entry is a control over pane state, not a router link** (feature 011). Product settles it: US-095.AC-1 and UC-081 step 1 both put the list in the **chat pane**. The route survives only so the previously documented deep link neither 404s nor renders a chat surface in the content pane.

## Client↔server contract

- **Transport**: REST over `/api/...`. Request and response bodies are JSON; every shape is a Pydantic model on the backend and a matching TypeScript DTO on the frontend.
- **Streaming**: Server-Sent Events (SSE) for long-running LLM generation. The frontend reads the stream with a `fetch`-based reader parsing `event:` / `data:` frames — **not** the browser `EventSource` API, because requests need `POST` bodies and a `Bearer` auth header. See `frontend.md` (`api/sse.ts`).
- **Auth**: JWT (HS256) in the `Authorization: Bearer <token>` header. The token is issued at login and carried by both SPAs. See `backend/auth-ids.md` for the per-user signing-key scheme.
- **Errors**: non-2xx responses carry a JSON body; the frontend normalizes them into a typed `ApiError` (status + message + optional structured field details). Book-domain endpoints add two cases on top of the existing taxonomy: a private book the caller has no relationship to answers **404** (existence hiding), and a chapter write carrying a stale base version answers **409**. See `authorization.md` → "Failure modes" and `domain-chapter.md` → "Concurrency".

### First-run setup endpoints (feature 003)

The first real endpoints — the **front door of a cold, unconfigured instance** — live under `/api/auth`:

| Method | Path | Request | Success response |
|--------|------|---------|------------------|
| `GET` | `/api/auth/status` | — | `AuthStatusResponse{needs_setup: bool}` |
| `POST` | `/api/auth/setup/create` | JSON `CreateDBRequest{admin_username, password, password_confirm}` | `LoginResponse{token}` (auto sign-in) |
| `POST` | `/api/auth/setup/import` | multipart, field `file` | `AuthStatusResponse` (no token) |

`create` provisions the schema and the first admin, then returns a token so the caller is signed in immediately; `import` restores an archive and leaves the caller unauthenticated (they log in afterward). See `backend/persistence.md` for the deferred-schema startup lifecycle these endpoints drive.

### REST route families, as shipped

The index only — **the method/path/DTO/status tables live in `quick-reference.md`** and are deliberately not duplicated here.

| Family | Feature | Gate |
|---|---|---|
| `/api/health`, `/api/auth/...` | 003 | open / setup |
| `/api/admin/users` | 005 | `require_role(admin)` |
| `/api/admin/llm-servers` | 006 | `require_role(admin)` |
| `/api/admin/db` | 007 | `require_role(admin)` |
| `/api/books/...` — create, list owned/shared, detail, the reader projection, the six settings mutations | 009 | `get_current_user` / `authz.book_access` |
| `/api/books/{id}/chats` + `/chats/{chat_id}/turn` (the SSE stream) | 011 | `authz.book_access` + a service-level row-ownership check |
| `/api/admin/assistant-config` — eight endpoints | 012 | `require_role(admin)` |
| `/api/books/{id}/codex` — four endpoints | 013 | `authz.book_access` |
| `/api/books/{id}/system-prompt` — `GET` / `PUT` | 021 | `authz.book_access` |

Book-scoped families all sit behind the same `authz.book_access` dependency, which resolves a typed `BookAccess` and produces **401** (no token) and **404** (existence hiding) before any handler runs; the service then decides the capability (**403**). See `authorization.md`.

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

## Streaming flow — concrete as of feature 013

The one streaming surface is the chat turn, `POST /api/books/{book_id}/chats/{chat_id}/turn`.

1. The frontend awaits `client.ts`'s **`refreshAuthToken()`** and then calls the SSE helper in `api/chats.ts` (a `POST` with `Bearer` auth). The explicit refresh exists because `sse.ts:streamPost` bypasses `request<T>` and so misses its silent on-401 retry.
2. The backend's `prepare_turn` runs the **pre-stream refusals** (chat ownership, model pair, server active, `$ENV` key resolvable) and answers them as ordinary HTTP status codes **before the first frame**, with nothing persisted.
3. Only then does `run_turn` open the stream: it persists the user message first, composes the system prompt, resolves the turn's tools, and drives `chat_with_tools`, pushing frames onto one `asyncio.Queue`.
4. **Five named frames** reach the wire — **`thinking`**, **`delta`**, **`done`**, **`error`** (feature 011) and **`canvas`** (feature 013, the shared-canvas codex draft). The route serializer is `event: <name>` / `data: <payload JSON>` and is **generic over the event name**, which is why the fifth frame needed no route change. A failure *after* the stream opens is an `error` frame over HTTP 200 — never a 500, never a hung stream. Payload shapes are in `quick-reference.md`; the protocol and its reasoning are in **`assistant-runtime.md`**.
5. The `fetch`-reader parses the frames and pushes updates into observable state via `runInAction`, so the UI streams live.
6. **The stream is cancelled through the `AbortController` `streamPost` owns and returns**, not through the page's mount `AbortSignal` — a deliberate departure from the `api/` layer's trailing-`signal` convention. The shell's unmount cleanup must call the stop effect explicitly.

**Deployment requirement:** assistant *thinking* is visible only when llama.cpp runs with **`--reasoning-format none`**; without it the feature degrades **silently** to content-only. The reason is inside the `llm-client` dependency — see `backend/features.md` → "Deployment requirement".
