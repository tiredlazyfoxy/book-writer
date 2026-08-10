# Quick Reference

Dense, agent-first index of concrete endpoints, DTOs, and patterns as they land. **Current through features 003–016, 021, 022, `023.chat-ux-revision` and `024.chat-agent-loop` (2026-08-10).** Append here as the system grows; this file is intentionally terse and is the one file exempt from the folder's ~400-line limit. For the reasoning behind each shape, follow the pointers into `backend.md`, `backend/features.md`, `system-overview.md` and the domain files.

This is `docs/architecture/quick-reference.md` — **not** `docs/product/quick-reference.md`, which is the product id registry. Every endpoint/DTO table referenced from `backend/features.md` lives here.

## Endpoints

| Method | Path | Success | Body | Flow |
|--------|------|---------|------|------|
| `GET` | `/api/health` | `200` | `{"status":"ok","db":"ready"}` | `routes/health.py` → `services/health.py check_health()` → `db/health.py ping()` → `HealthResponse` |
| `GET` | `/api/auth/status` | `200` | — | `AuthStatusResponse{needs_setup}` — `needs_setup = not is_db_ready()` (admin existence) |
| `POST` | `/api/auth/setup/create` | `200` | `CreateDBRequest{admin_username, password, password_confirm}` | `LoginResponse{token}` — creates schema + first admin, auto sign-in |
| `POST` | `/api/auth/setup/import` | `200` | multipart, field `file` | `AuthStatusResponse` — restores archive, **no token** |

### `/api/admin/llm-servers` (feature 006) — all `Depends(require_role(admin))`

| Method | Path | Success | Body → Response | Notes |
|--------|------|---------|-----------------|-------|
| `GET` | `/api/admin/llm-servers` | `200` | — → `LlmServersListResponse` | list |
| `POST` | `/api/admin/llm-servers` | `201` | `CreateLlmServerRequest` → `LlmServerResponse` | missing-field / invalid-backend-type → 400 |
| `GET` | `/api/admin/llm-servers/embedding` | `200` | — → `EmbeddingConfigResponse` | all-`null` when none designated; static route, declared before `/{server_id}` |
| `DELETE` | `/api/admin/llm-servers/embedding` | `204` | — | clears the embedding designation |
| `PUT` | `/api/admin/llm-servers/{server_id}` | `200` | `UpdateLlmServerRequest` → `LlmServerResponse` | not-found → 404; empty `api_key` clears, omitted keeps |
| `DELETE` | `/api/admin/llm-servers/{server_id}` | `204` | — | not-found → 404 (first DELETE pattern) |
| `GET` | `/api/admin/llm-servers/{server_id}/available-models` | `200` | — → `AvailableModelsResponse` | live probe; unreachable/auth/keyless → **502**; sorted models |
| `PUT` | `/api/admin/llm-servers/{server_id}/enabled-models` | `200` | `EnabledModelsRequest` → `LlmServerResponse` | not-found → 404 |
| `PUT` | `/api/admin/llm-servers/{server_id}/embedding` | `204` | `SetEmbeddingRequest` | clear-all-then-set; env-not-set → 400, not-found → 404 |

- Non-admin caller on any of the nine → **403**. `server_id` path params are `int` (FastAPI coerces the stringified id). See `backend/features.md` → LLM server connections.

### `/api/admin/db` (feature 007) — all `Depends(require_role(admin))`

| Method | Path | Success | Body → Response | Notes |
|--------|------|---------|-----------------|-------|
| `GET` | `/api/admin/db/report` | `200` | — → `ConsistencyReport` | per-table ok/drift/missing |
| `GET` | `/api/admin/db/export` | `200` | — → zip download | `Content-Disposition: attachment`, `application/zip`; first non-JSON admin response |
| `POST` | `/api/admin/db/import` | `204` | multipart, field `file` | pre-validated; `invalid-archive` → 400, DB unmutated; does NOT flip `set_db_ready` |
| `POST` | `/api/admin/db/vector/rebuild` | `200` | — → `VectorRebuildResponse` | `no-embedding-provider` → 400; empty registry → 0 rows |
| `POST` | `/api/admin/db/tables/{name}/create` | `204` | — | `not-in-metadata` / `table-not-missing` → 400 |
| `POST` | `/api/admin/db/tables/{name}/sync` | `204` | — | `unknown-table` → 404 (ALTER ADD/DROP COLUMN) |

- Static routes (`/report`, `/export`, `/import`, `/vector/rebuild`) declared **before** `/tables/{name}/...`; non-admin caller → **403**. See `backend/features.md` → Database consistency & management.

- `/api/health` — the first concrete endpoint and the canonical four-layer example. Readiness originates from `db.health.ping()` (a `SELECT 1`-style probe), **not** a route-level constant. When the DB is not ready the service maps it to `{"status":"error","db":"unavailable"}`. Passes on a cold instance (zero tables) — `SELECT 1` still succeeds.
- `/api/auth/setup/*` (feature 003) — the front door of a cold instance; schema creation is deferred to these flows. See `backend/persistence.md` startup lifecycle.

### `/api/books` (feature 009) — author-scoped, `Depends(auth_service.get_current_user)` / `Depends(authz.book_access)`

| Method | Path | Success | Body → Response | Notes |
|--------|------|---------|-----------------|-------|
| `POST` | `/api/books` | `201` | `CreateBookRequest` → `BookResponse` | caller becomes `owner_id`; defaults `state=active`, `system_prompt=""`, `active_notes=""`, moderation triple `null` |
| `GET` | `/api/books` | `200` | — → `BookListResponse` | books **owned** by the caller (UC-022) |
| `GET` | `/api/books/shared` | `200` | — → `BookListResponse` | books co-authored, **excluding** owned (UC-030); static route, declared **before** `/{book_id}` |
| `GET` | `/api/books/public` | `200` | — → `PublicBookListResponse` | **feature 022** — reader-safe discovery list (UC-100, US-118): `public` + `active` books the caller neither owns nor co-authors. **Static route, declared before `/{book_id}`** — the same static-before-dynamic constraint the `/shared` row records. Gated by `Depends(auth_service.get_current_user)` — **authentication alone, no `book_access`** (there is no `book_id` to resolve a role against; see `authorization.md`) |
| `GET` | `/api/books/{book_id}` | `200` | — → `BookDetailResponse` | members-only detail (owner + co-author) with the `members` list |
| `GET` | `/api/books/{book_id}/read` | `200` | — → `ReaderBookResponse` | the **reader-safe projection** — see below. Since **feature 022** `chapters` is `list[ReaderChapterRef]` (a populated table of contents), and the handler lives in **`routes/reader.py`**, not `routes/books.py`; the URL is unchanged by the move |
| `GET` | `/api/books/{book_id}/read/chapters/{chapter_id}` | `200` | — → `ReaderChapterResponse` | **feature 022** — one reader-visible chapter's saved body (UC-029). A chapter that is not reader-visible answers **404, not 403**, indistinguishable across five sources — see `authorization.md` → "The reader surface" |
| `POST` | `/api/books/{book_id}/archive` | `200` | — → `BookResponse` | owner-only; already archived → **409** |
| `POST` | `/api/books/{book_id}/unarchive` | `200` | — → `BookResponse` | owner-only; not archived → **409** |
| `POST` | `/api/books/{book_id}/transfer` | `200` | `TransferOwnershipRequest` → `BookResponse` | owner-only; target is not a co-author → **409**, ownership unchanged |
| `POST` | `/api/books/{book_id}/members` | `200` | `AddMemberRequest` → `BookDetailResponse` | owner-only; duplicate membership → **409** |
| `DELETE` | `/api/books/{book_id}/members/{user_id}` | `200` | — → `BookDetailResponse` | owner-only; target is not a member → **404** |
| `PATCH` | `/api/books/{book_id}/visibility` | `200` | `SetVisibilityRequest` → `BookResponse` | owner-only |

- **The reader-safe projection is three DTOs, and the exclusion is structural** — separate DTOs, not a filtered `BookResponse` and not a field filter. That is the load-bearing claim: a reader surface built by *removing* fields leaks the next field somebody adds; one built from its own types cannot.
  - `ReaderBookResponse` is **exactly** `{title, chapters}`, with `chapters: list[ReaderChapterRef]` and each ref **exactly** `{id, title}` — no `sketch`, `summary`, `state`, `ordinal` or `version`, and none of `members`, `owner_id`, `id`, `visibility`, `collaboration_mode`, `description`, `system_prompt`, `active_notes` or the moderation triple.
  - `ReaderChapterResponse` is **exactly** `{id, title, text}`.
  - `PublicBookRef` is **exactly** `{id, title, description}` — no `owner_id`, `visibility`, `state`, `collaboration_mode` or timestamps. **The owner's display name is deliberately absent** (feature 022, D14): carrying it needs a `users` join and answers a question — "does a public book expose its author's username?" — nobody has asked.
  - The table of contents is **populated** as of feature 022; the pre-022 note that it was an empty placeholder no longer holds.
- **The reader surface is its own module pair (feature 022): `routes/reader.py` + `services/reader.py`.** The delivered `GET /{book_id}/read` route and its `get_reader_book` service **moved out of** `routes/books.py` / `services/books.py` into it, URLs unchanged. Reason: UC-029 is an exclusion list, and "what can ACT-006 reach" must be answerable from two files rather than from a twelve-route books module. `services/reader.py` also holds `ReaderErrorReason` (`book_not_found`, `chapter_not_found`), `ReaderError(reason, message="")` — `services/chapters.py::ChapterError`'s shape exactly — and `READER_VISIBLE_STATES = {open, closed}`. `main.py` registers `reader.router`; **include order is deliberately not load-bearing** here, because neither reader path collides with anything else.
- **`db/books.py::list_public_for_reader(user_id: int) -> list[Book]`** (feature 022) backs `GET /public`. **Four clauses, all of which must hold:** `visibility == public` ∧ `state == active` ∧ `owner_id != user_id` ∧ a correlated `NOT EXISTS` over `book_members` for `(Book.id, user_id)` — the negative of `list_shared`'s join. Ordered by `Book.id`. The four exclusions are enforced **in the query**, not in the authorization layer.
- **Status taxonomy** — the pattern every later book-scoped family copies:
  - **401** — no token (from `get_current_user`, behind `authz.book_access`).
  - **404** — the book does not exist, **or** the caller resolves to `AccessRole.none` (a private book they have no relationship to). **Existence hiding**, produced once in `authz.resolve_book_access`, never re-derived per route.
  - **403** — the caller is a member/reader but the capability is outside `_CAPABILITY_MATRIX[capability]` (e.g. a public book's reader calling `GET /{book_id}`, or a co-author calling any of the six owner-only mutations).
  - **409** — lifecycle/membership conflicts (the four cases above).
- Target user ids cross the wire as **strings** (`TransferOwnershipRequest.target_user_id`, `AddMemberRequest.target_user_id`, the `DELETE .../members/{user_id}` path param); the **service** resolves string → int, routes stay HTTP-only. See `authorization.md` and `domain-book.md`.

### `/api/books/{book_id}/chats` + the streaming turn (feature 011) — every route `Depends(authz.book_access)`

| Method | Path | Success | Body → Response | Notes |
|--------|------|---------|-----------------|-------|
| `GET` | `/api/books/{book_id}/chats/model-options` | `200` | — → `ModelOptionListResponse` | active servers × `enabled_models`, no api key; static route, declared **before** the `{chat_id}` routes |
| `POST` | `/api/books/{book_id}/chats` | `201` | `CreateChatRequest` → `ChatResponse` | omitted/empty `title` defaults to `"New chat"` |
| `GET` | `/api/books/{book_id}/chats` | `200` | `?archived=false` → `ChatListResponse` | caller-private; most-recently-modified first |
| `GET` | `/api/books/{book_id}/chats/{chat_id}` | `200` | — → `ChatDetailResponse` | chat + `position`-ordered messages |
| `PATCH` | `/api/books/{book_id}/chats/{chat_id}` | `200` | `UpdateChatRequest` → `ChatResponse` | partial; a title-only or archive-only body never wipes an existing model pair |
| `POST` | `/api/books/{book_id}/chats/{chat_id}/turn` | `200` | `TurnRequest` → `StreamingResponse` (`text/event-stream`) | see the frame table below |
| `POST` | `/api/books/{book_id}/chats/{chat_id}/title` | `200` | **no body** → `ChatTitleResponse{title, changed}` | **feature `023`** — background chat titling (UC-101 / US-119). Registered **after** the static `model-options` route, alongside `turn`. **May legitimately do nothing**: outside the exactly-1 / exactly-5 user-message trigger, or on any failure, it answers the existing title with `changed: false` — a `200` is not a claim that a title was written. See `domain-chat.md` → "Background chat titling" |

- **404, not 403, for another author's chat.** A chat is private to `Chat.author_id` — from co-authors, the book's owner and admins alike. The rule is a **service-level ownership check** in `services/chats.py` layered on the `book_access` dependency; **no `Capability` member was added** and `_CAPABILITY_MATRIX` is unchanged, because the matrix maps capability → role and has no notion of "author of *this row*". Answering 404 means existence is never confirmed. Later chat-touching features copy this. See `domain-chat.md`, `authorization.md`.
- **Error taxonomy** (`ChatErrorReason`): `chat_not_found` → **404**; `invalid_model_pair` / `unknown_or_inactive_server` / `model_not_enabled` / `invalid_sampling` → **400**. The turn additionally maps `LlmServerError(env_not_set)` → **400**.
- **Pre-stream vs post-open.** `prepare_turn` runs the refusals (no model pair, missing/inactive server, unresolvable `$ENV` key, chat not owned) **before the first frame**, so they answer as ordinary HTTP status codes with nothing persisted. A failure **after** the stream opens surfaces as an `error` frame over HTTP **200** — never a 500 and never a hung stream.
- **The seven SSE frames** (`event: <name>` / `data: <payload JSON>`; the route serializer is **generic over the event name**, so widening the vocabulary needs no route change):

| Frame | Payload | Meaning |
|---|---|---|
| `thinking` | `ThinkingFrame{text}` | a chunk routed to the thinking channel by `ThinkSplitter` (`<think>` … `</think>`, split by BookWriter itself) |
| `delta` | `DeltaFrame{text}` | a chunk of assistant content |
| `done` | `DoneFrame{message: ChatMessageResponse}` | terminal success, carrying the persisted assistant message |
| `error` | `ErrorFrame{message}` | terminal failure after the stream opened |
| `canvas` | `CanvasFrame{subject_kind, subject_id, field, op, text}` | **features 013 / 015** — a shared-canvas draft for the open codex entry **or chapter**; persists nothing. `op` was added by 015; a widened frame must be carried through **`api/chats.ts`'s `canvasFrame` narrowing** as well as the `.d.ts` twin, or the new field is silently dropped on the client |
| `tool_call` | `ToolCallFrame{tool_name, arguments}` | **feature `024`** — a tool is about to run. Emitted **generically by the wrapper around every bound tool**, not by the tool itself (unlike `canvas`), so a new tool gets visibility for free. **Arguments arrive whole, not streamed** |
| `tool_result` | `ToolResultFrame{tool_name, result, ok}` | **feature `024`** — that tool's outcome; `ok=false` is a tool that raised, converted to an error string. A **failed frame emission is swallowed** — the model, the trace and the caller still get the real result |

  Frame semantics, the tool loop, mode gating and the canvas write live in **`assistant-runtime.md`**. Note the deployment requirement in `backend/features.md` — llama.cpp must run with `--reasoning-format none` or thinking is silently lost.

### `/api/admin/assistant-config` (feature 012) — all `Depends(require_role(admin))`

| Method | Path | Success | Body → Response | Notes |
|--------|------|---------|-----------------|-------|
| `GET` | `/api/admin/assistant-config/tools` | `200` | — → `ToolsListResponse` | the code catalogue, declaration order, `name` + `description` only |
| `GET` | `/api/admin/assistant-config/modes` | `200` | — → `AssistantModesListResponse` | `DEFAULT_MODE_KEYS` position sort, unknown keys last |
| `PUT` | `/api/admin/assistant-config/modes/{mode_key}` | `200` | `UpdateAssistantModeRequest` → `AssistantModeResponse` | **full replace**; all three body fields required, values may be `null` / `[]` |
| `GET` | `/api/admin/assistant-config/sub-agents` | `200` | — → `SubAgentsListResponse` | unfiltered — `disabled` rows included |
| `POST` | `/api/admin/assistant-config/sub-agents` | `201` | `CreateSubAgentRequest` → `SubAgentResponse` | |
| `PUT` | `/api/admin/assistant-config/sub-agents/{sub_agent_id}` | `200` | `UpdateSubAgentRequest` → `SubAgentResponse` | **full replace**; no `disabled` field |
| `POST` | `/api/admin/assistant-config/sub-agents/{sub_agent_id}/disable` | `200` | **no body** → `SubAgentResponse` | also deletes that sub-agent's `mode_subagent` rows |
| `POST` | `/api/admin/assistant-config/sub-agents/{sub_agent_id}/enable` | `200` | **no body** → `SubAgentResponse` | restores nothing that disable removed |

- Declaration order is **load-bearing** (static before `{param}` within each family) and must not be reordered.
- **Status taxonomy:** **400** for an unknown tool name, an unknown or `disabled` sub-agent, an unknown mode key, a blank name, a half-set model pair, `unknown-or-inactive-server`, `model-not-enabled`; **404** for an absent mode (`mode_not_found`) or sub-agent (`sub_agent_not_found`); **409** for a **duplicate sub-agent name** (`name_taken`) — the **first 409 outside user administration**, following the `services/admin.py` `username_taken` precedent; **403** / **401** come from `require_role` / `get_current_user`, never from a handler.
- `sub_agent_id` and `mode_key` are plain **`str`** path params, handed to the service verbatim. An ill-formed id is `sub_agent_not_found` → **404**, never FastAPI's 422 — a deliberate override of the `routes/admin/llm_servers.py` `server_id: int` precedent, so the malformed-id decision stays out of `routes/`.
- **Two deliberate absences:** **no single-mode `GET`** (the list is small and always loaded whole) and **no `DELETE` anywhere** (disable-not-delete). Verified against the generated OpenAPI: seven paths, eight operations, **zero** `delete` operations. See `assistant-config.md`.

### `/api/books/{book_id}/codex` (feature 013) — every route `Depends(authz.book_access)`

| Method | Path | Success | Body → Response | Notes |
|--------|------|---------|-----------------|-------|
| `POST` | `/api/books/{book_id}/codex` | `201` | `CreateCodexEntryRequest` → `CodexEntryResponse` | writes **no** version row |
| `GET` | `/api/books/{book_id}/codex` | `200` | `?kind=&q=&include_archived=false` → `CodexEntryListResponse` | `q` is the case-insensitive name-or-body needle; name-ascending (nulls last) then id |
| `GET` | `/api/books/{book_id}/codex/{entry_id}` | `200` | — → `CodexEntryResponse` | `entry_id` is the wire **string** id |
| `PUT` | `/api/books/{book_id}/codex/{entry_id}` | `200` | `UpdateCodexEntryRequest` → `CodexEntryResponse` | writes a `CodexEntryVersion` carrying the **prior** name/body/kind, then mutates |

- **Status taxonomy** (`CodexErrorReason` → status): `entry_not_found` → **404** (an unknown id, a non-numeric id and **another book's entry** are all the same refusal); `name_required` / `name_not_allowed` / `entry_archived` → **400**; `proposal_mode_unsupported` → **403**; `stale_modified_at` → **409**. A non-member of a private book gets **404** from all four routes (existence hiding); a public book's reader gets **403**.
- **Two 403 producers, distinguished by their detail body, not their status.** An `authz` denial carries `detail` as a plain **string**; a `CodexError` carries `detail` as a `CodexErrorDetail` **object** — `{"detail": {"reason": "<CodexErrorReason value>", "message": "<text>"}}` — so a client can branch on the reason.
- **Optimistic concurrency:** `UpdateCodexEntryRequest.expected_modified_at` is **required but nullable** (an omitted field must not silently pass the check). `modified_at` is the entry's **version token** and the same value the frontend restore buffer stores as its `baseVersion` (`domain-codex.md`, `frontend-work-drafts.md`).
- **Deliberate absences:** **no `DELETE`** (archive-not-delete — and archive itself is `017.codex-archive-restore`'s), **no history endpoints** (`019.codex-history`'s, though the version rows are written here), **no cross-book copy**.

### `/api/books/{book_id}/system-prompt` (feature 021) — `Depends(authz.book_access)`

| Method | Path | Success | Body → Response | Notes |
|--------|------|---------|-----------------|-------|
| `GET` | `/api/books/{book_id}/system-prompt` | `200` | — → `BookAuthorPromptResponse` | the **caller's own** prompt; no row yet → `system_prompt: ""`, `modified_at: null` (not a 404) |
| `PUT` | `/api/books/{book_id}/system-prompt` | `200` | `UpdateBookAuthorPromptRequest` → `BookAuthorPromptResponse` | the upsert; **200 on both** the create and the update path |

- **Response shape:** `book_id` (string snowflake), `system_prompt` (never nullable), `modified_at` (`null` when the author has no row). **No `user_id`** — the subject is always the caller, and returning an id would invite the reading that another author's prompt is addressable here. It is not: neither service entry point takes a user id.
- **Status taxonomy:** **401** no token; **404** a private book the caller has no relationship to (from `resolve_book_access`, not re-derived); **403** a logged-in non-member of a book they can see (`not_a_member`, the router's only mapped reason); **200** for a member acting on their own prompt. No `Capability` member was added.
- **Deliberate absences:** **no `DELETE`** — `""` *is* "no prompt", so a required column with `""` as a legal value needs no deletion verb (a `DELETE` is refused by the framework as **405**); **no `POST`** — `PUT` is the upsert; **no field on `BookDetailResponse`** — a per-caller value cannot ride on a book-shaped DTO.

### `/api/books/{book_id}/chapters` (feature 014) — every route `Depends(authz.book_access)`

| Method | Path | Success | Body → Response | Notes |
|--------|------|---------|-----------------|-------|
| `GET` | `/api/books/{book_id}/chapters` | `200` | — → `ChapterListResponse` | ordinal-ordered, plus `can_reorder` |
| `POST` | `/api/books/{book_id}/chapters` | `201` | `CreateChapterRequest` → `ChapterResponse` | server-assigned ordinal — a new chapter is **appended**; blank/whitespace `title` → **422** from the field constraint, never reaching the service |
| `PUT` | `/api/books/{book_id}/chapters/order` | `200` | `ReorderChaptersRequest` → `ChapterListResponse` | **owner-only**; the **full** id list, validated whole before any write, then ordinals rewritten `1..N`. Static segment declared **before** the three `/{chapter_id}` routes |
| `GET` | `/api/books/{book_id}/chapters/{chapter_id}` | `200` | — → `ChapterResponse` | `chapter_id` is the wire **string** id, parsed in the service |
| `PATCH` | `/api/books/{book_id}/chapters/{chapter_id}` | `200` | `UpdateChapterSketchRequest` → `ChapterResponse` | sketch only; **no version token**, and `Chapter.version` is **not** bumped |
| `DELETE` | `/api/books/{book_id}/chapters/{chapter_id}` | `204` | — | **no ordinal renumbering** — removal leaves a gap |
| `GET` | `/api/books/{book_id}/chapters/{chapter_id}/system-prompt` | `200` | — → `ChapterAuthorPromptResponse` | the **caller's own** prompt; no row yet → `system_prompt: ""`, `modified_at: null` (not a 404) |
| `PUT` | `/api/books/{book_id}/chapters/{chapter_id}/system-prompt` | `200` | `UpdateChapterAuthorPromptRequest` → `ChapterAuthorPromptResponse` | the upsert; **200 on both** the create and the update path |

- **Status taxonomy** (`ChapterErrorReason` → status): `chapter-not-found` → **404** (an unknown id, a **non-numeric** id and **another book's chapter** are all the same refusal); `chapter-not-planned` → **409** on the sketch and delete paths (the caller *has* the capability, the resource is in the wrong state — **not** 403); `invalid-reorder-set` → **400** (a structurally valid body that failed a cross-row invariant; `422` would misreport where validation happened). The prompt pair has its own two reasons: `not-a-member` → **403**, `chapter-not-found` → **404**.
- **401** no token and **404** for a private book come from `Depends(authz.book_access)` and are never re-derived. **403** on the four skeleton mutations comes from `authz.require`; `set_chapter_order` is **owner-only** (US-033.AC-2), the other three are `{owner, co_author}`. The two read paths reuse **`read_book`** unchanged.
- **The prompt pair adds no `Capability` and no `_CAPABILITY_MATRIX` row** — it is the third **row-ownership** rule, scoped to `access.user_id`, with a separate `chapter.book_id == access.book_id` check. No chapter-state gate and no collaboration-mode gate on it. See `authorization.md`.
- **No `chapter_access` dependency** — the routes nest under `{book_id}` so `book_access` binds unchanged.
- **`can_reorder` is a caller-relative affordance hint**: the client mirrors it to show or hide the control and **never enforces on it**; the server re-checks on every `PUT`.
- **Deliberate absences:** **no per-chapter move endpoint** (one bulk `PUT`, so concurrent callers cannot interleave into an ordinal set nobody chose); **no `DELETE` / `POST` on the prompt path** (`""` *is* "no prompt", `PUT` is the upsert; both refused as **405**); **no chapter field on any book DTO**; **no ordinal renumbering on delete**.

### The chapter body and state transitions (feature 015) — every route `Depends(authz.book_access)`

| Method | Path | Success | Body → Response | Notes |
|--------|------|---------|-----------------|-------|
| `GET` | `/api/books/{book_id}/chapters/{chapter_id}/text` | `200` | — → `ChapterTextResponse` | the **saved** body; readable in every state |
| `PUT` | `/api/books/{book_id}/chapters/{chapter_id}/text` | `200` | `UpdateChapterTextRequest` → `ChapterTextResponse` | whole body + `expected_version`; writes one `ChapterChange` + one `ChapterTextRevision`, then bumps `version` |
| `POST` | `/api/books/{book_id}/chapters/{chapter_id}/open` | `200` | **no body** → `ChapterResponse` | `planned → open`; **owner-only** |
| `POST` | `/api/books/{book_id}/chapters/{chapter_id}/close` | `200` | **no body** → `ChapterResponse` | **`open → closing`** since `016` (was `open → closed` at Stage 2); also deletes the chapter's `origin=check` flags first. **Owner-only** |
| `POST` | `/api/books/{book_id}/chapters/{chapter_id}/reopen` | `200` | **no body** → `ChapterResponse` | `closed → open`; **owner-only** |

- **`POST` for the transitions** (commands with no body), **`PUT` for the body** (whole-resource replace). **No partial or line-addressed write endpoint exists** — placement is computed server-side (`append` when the new body starts with the loaded one, else `range` over lines `1..N`). See `domain-chapter.md`.
- **Two new `Capability` members:** open/close/reopen a chapter (UC-035..037, **owner only**, one member for the one matrix row) and write into the open chapter (UC-038, **owner + co-author**, with the `(mode)` qualifier layered in `services/chapters.py`, not in the matrix).
- **Status taxonomy:** **401** no token; **404** a private book with no relationship (from `book_access`, not re-derived) and a chapter that does not exist or belongs to another book; **403** a capability failure, any reader, the **proposal-mode co-author** refusal (typed reason naming FEAT-010), and the **archived-book** refusal; **409** every state-machine and version refusal — a body write to a non-`open` chapter, a stale `expected_version`, opening a non-`planned` chapter, reopening a non-`closed` chapter, closing a non-`open` chapter, and opening **or** reopening while any chapter is `open` or `closing` (CF1, both transitions); **422** a malformed body.
- **`403` vs `409` is load-bearing:** archive is an **access** answer (no member holds the write capability), the state machine is a **resource-state** answer (the caller has the capability). See `authorization.md`.
- **Deliberate absences:** **no `can_write` on the body response and no `can_manage_state` on `ChapterResponse`** (a caller-relative hint rides a **list envelope**, not a resource representation — `021`'s rule); **no new table, no new codec, no migration** (`chapter_changes` / `chapter_text_revisions` shipped with `008` and got their first writer here); **chapter text is not vector-indexed**.
- **Four chapter tools** joined `TOOL_REGISTRY` (`services/chapter_tools.py`) — read the saved body, replace the whole body, replace the selection, append to end — **mode-gated, and since feature `024` seeded onto `write-chapter` by default**, so the assistant can write into the chapter editor on a fresh install. (They shipped unreachable at `015`; D4 reversed that deliberately. The empty-allowlist rule is unchanged — an admin who edits a mode down to zero tools gets zero tools.) See `assistant-runtime.md`.

### Chapter close & continuity (feature 016) — every route `Depends(authz.book_access)`

| Method | Path | Success | Body → Response | Notes |
|--------|------|---------|-----------------|-------|
| `POST` | `/api/books/{book_id}/chapters/{chapter_id}/close/cancel` | `200` | **no body** → `ChapterResponse` | `closing → open`, discarding drafted artifacts; a **200 no-op** (unchanged response) from any other state. **Owner-only**, same `set_chapter_state` capability `close` uses |
| `GET` | `/api/books/{book_id}/state-notes` | `200` | — → `BookStateNotesResponse` | members only |
| `PUT` | `/api/books/{book_id}/state-notes` | `200` | `UpdateBookStateNotesRequest` → `BookStateNotesResponse` | the UC-050 **direct-edit** path; writes `Book.active_notes` |
| `GET` | `/api/books/{book_id}/continuity` | `200` | — → `BookContinuityResponse` | one entry per chapter, **ordinal order**; each entry's `warnings` is **open flags only**, both origins |
| `GET` | `/api/books/{book_id}/chapters/{chapter_id}/notes` | `200` | — → `ChapterNoteChangesetResponse` | **no row yet → default-empty 200** (`added`/`modified`/`deleted` = `""`, `status: null`), matching the `ChapterAuthorPrompt` convention — **not** a 404 |
| `GET` | `/api/books/{book_id}/chapters/{chapter_id}/flags` | `200` | — → `FlagListResponse` | all flags, open **and** resolved, newest first |
| `POST` | `/api/books/{book_id}/chapters/{chapter_id}/flags` | `200` | `RaiseFlagRequest` → `FlagResponse` | `origin=person`, `status=open`, `created_by` = caller |
| `POST` | `/api/books/{book_id}/chapters/{chapter_id}/flags/{flag_id}/resolve` | `200` | **no body** → `FlagResponse` | stamps `resolved_by` / `resolved_at`; **owner-only** |

- **Three new `Capability` members:** `raise_flag` {owner, co_author} (UC-067), `resolve_flag` {owner} (UC-068), `edit_state_notes` {owner, co_author} (UC-050, with the `(mode)` qualifier layered in `services/continuity.py`, not in the matrix). **Close added none** — it reuses `set_chapter_state`. **Viewing continuity data needs no capability**, only membership. See `authorization.md`.
- **Two new error taxonomies, both this feature's own.** `ContinuityErrorReason`: `not_a_member` / `book_archived` / `proposal_mode_refused` → **403**, `chapter_not_found` → **404**. `FlagErrorReason`: `not_a_member` / `book_archived` → **403**, `chapter_not_found` / `flag_not_found` → **404**, `flag_already_resolved` → **409**.
- **No new `ChapterErrorReason` member was needed** — `close_chapter` and `cancel_close` reuse `chapter_not_open` for every wrong-state source.
- **The close is not an endpoint pair.** `POST …/close` only opens the window; the chapter reaches `closed` through a **deterministic post-turn step** (`services/chapters.py::finalize_close_turn`) run by the close-chapter assistant turn, never by a route. See `domain-continuity.md` → "The close procedure, as built".
- **Five close tools** joined `TOOL_REGISTRY` (`services/close_tools.py`) — `draft_chapter_summary`, `draft_chapter_notes`, `propose_active_notes`, `raise_check_flag`, `read_continuity_context` — **mode-gated, and since feature `024` seeded onto `close-chapter` by default**, so the close procedure is **live on a fresh install** (it previously could not execute at all until an admin assigned them). Accepted risk: a model-driven close run now writes real artifacts on an unconfigured instance. `ToolContext` gained a **sixth** field, `active_notes_proposal: str | None`, mutated in place. See `assistant-runtime.md`.
- **Deliberate absences:** **no summary editor and no approval endpoint** (no approval gate ships); **no `DELETE` on a flag** (resolve, not delete — while a *close run* deletes its own prior `origin=check` flags server-side); **no settings-side continuity surface** (working page only, D8); **no new table, no new codec, no migration** — `chapter_note_changesets` and `flags` shipped with `008` and got their first writers here.

## DTOs

| DTO | Module | Shape |
|-----|--------|-------|
| `HealthResponse` | `app/models/schemas/health.py` | Pydantic `BaseModel`: `status: str`, `db: str` |
| `AuthStatusResponse` | `app/models/schemas/` (auth) | Pydantic `BaseModel`: `needs_setup: bool` |
| `CreateDBRequest` | `app/models/schemas/` (auth) | Pydantic `BaseModel`: `admin_username: str`, `password: str`, `password_confirm: str` |
| `LoginResponse` | `app/models/schemas/` (auth) | Pydantic `BaseModel`: `token: str` |
| `LlmServerResponse` | `app/models/schemas/llm_servers.py` | `id: str` (**string**, snowflake — not int), `name: str`, `backend_type: str`, `base_url: str`, `has_api_key: bool`, `enabled_models: list[str]`, `is_active: bool`, `is_embedding: bool`, `embedding_model: str \| None`, `created_at`, `modified_at` — **no `api_key`** |
| `CreateLlmServerRequest` | `app/models/schemas/llm_servers.py` | `name: str`, `backend_type: str`, `base_url: str`, `api_key: str \| None = None`, `is_active: bool = True` |
| `UpdateLlmServerRequest` | `app/models/schemas/llm_servers.py` | all optional: `name`, `backend_type`, `base_url`, `api_key`, `is_active` |
| `AvailableModelsResponse` | `app/models/schemas/llm_servers.py` | `models: list[str]` (sorted) |
| `EnabledModelsRequest` | `app/models/schemas/llm_servers.py` | `enabled_models: list[str]` |
| `SetEmbeddingRequest` | `app/models/schemas/llm_servers.py` | `model: str` |
| `EmbeddingConfigResponse` | `app/models/schemas/llm_servers.py` | `server_id: str \| None` (**string**, snowflake), `server_name`, `base_url`, `backend_type`, `model: str \| None`, `has_api_key: bool` — all-`None` when no embedding server |
| `LlmServersListResponse` | `app/models/schemas/llm_servers.py` | `items: list[LlmServerResponse]` |
| `ConsistencyReport` | `app/models/schemas/db_admin.py` | `tables: list[TableReportEntry]` |
| `TableReportEntry` | `app/models/schemas/db_admin.py` | `name: str`, `status: 'ok' \| 'drift' \| 'missing'`, `missing_columns: list[str]`, `extra_columns: list[str]` |
| `VectorRebuildResponse` | `app/models/schemas/db_admin.py` | `indexed_rows: int` |

### Books (feature 009) — `app/models/schemas/books.py`

| DTO | Shape |
|-----|-------|
| `CreateBookRequest` | `title: str`, `description: str`, `collaboration_mode: CollaborationMode`, `visibility: Visibility` |
| `BookResponse` | `id: str`, `owner_id: str`, `title`, `description`, `collaboration_mode`, `visibility`, `state: BookState`, `created_at`, `modified_at` — **no** `system_prompt` / `active_notes` / moderation fields |
| `BookListResponse` | `items: list[BookResponse]` |
| `BookMemberResponse` | `user_id: str`, `role: MemberRole`, `created_at: datetime \| None` |
| `BookDetailResponse` | **subclasses `BookResponse`**, adds `members: list[BookMemberResponse]` |
| `TransferOwnershipRequest` | `target_user_id: str` |
| `AddMemberRequest` | `target_user_id: str` |
| `SetVisibilityRequest` | `visibility: Visibility` |

**`ReaderBookResponse` no longer lives in this module** — feature 022 **moved** it to `app/models/schemas/reader.py` (below) and widened `chapters` from `list[str]` to `list[ReaderChapterRef]`. It is still a separate DTO, never a filtered `BookResponse`.

### The reader surface (feature 022) — `app/models/schemas/reader.py`

A **new module**, holding all five reader DTOs together so the reader-safe projection is answerable from one file.

| DTO | Shape |
|-----|-------|
| `ReaderChapterRef` | `id: str`, `title: str` — nothing else |
| `ReaderBookResponse` | `title: str`, `chapters: list[ReaderChapterRef]` — **moved** here from `books.py`; `chapters` widened from `list[str]` |
| `ReaderChapterResponse` | `id: str`, `title: str`, `text: str` |
| `PublicBookRef` | `id: str`, `title: str`, `description: str` — **no** `owner_id` / `visibility` / `state` / `collaboration_mode` / timestamps, and no owner display name (D14) |
| `PublicBookListResponse` | `items: list[PublicBookRef]` |

**No field may be added to any of the five**: each exclusion is the structural half of UC-029, and a widened DTO is how a reader surface silently stops being one.

### Chats and the turn (features 011 / 013 / `023` / `024`) — `app/models/schemas/chats.py`

| DTO | Shape |
|-----|-------|
| `ChatSamplingParams` | `temperature=0.8`, `top_p=0.95`, `top_k=40`, `repeat_penalty=1.1`, `min_p=0.05`, `max_tokens: int \| None = None`, `seed: int \| None = None`, `presence_penalty=0.0`, `frequency_penalty=0.0`, `enable_thinking=True`. **`top_k` / `repeat_penalty` / `min_p` are persisted but cannot reach either backend** under `llm-client` v0.1.4 — see `assistant-runtime.md` |
| `CreateChatRequest` | all optional: `title`, `llm_server_id`, `model_name`, `sampling` |
| `UpdateChatRequest` | all optional: `title`, `archived`, `llm_server_id`, `model_name`, `sampling` |
| `ChatResponse` | `id: str`, `book_id: str`, `author_id: str`, `title: str`, `llm_server_id: str \| None`, `model_name: str \| None`, `sampling: ChatSamplingParams`, `archived: bool`, `created_at`, `modified_at` |
| `ChatListResponse` | `items: list[ChatResponse]` |
| `ChatMessageResponse` | `id: str`, `chat_id: str`, `role: str`, `content: str`, `reasoning: str \| None`, `position: int`, `created_at`, and **since `024`: `tool_trace: list[ToolTraceEntry] \| None`** (required-nullable on the frontend twin; filled by `services/chats.py::_to_message_response`, the single mapper behind both the `done` frame and the post-turn reload) |
| `ChatTitleResponse` | **feature `023`** — `title: str`, `changed: bool`. `changed: false` with the existing title is the legitimate no-op answer |
| `ChatMessageListResponse` | `items: list[ChatMessageResponse]` — declared; no route returns it yet |
| `ChatDetailResponse` | `chat: ChatResponse`, `messages: list[ChatMessageResponse]` |
| `ModelOptionResponse` | `server_id: str`, `server_name: str`, `model_name: str` |
| `ModelOptionListResponse` | `items: list[ModelOptionResponse]` |
| `TurnRequest` | `prompt: str \| None = None` (absent = retry) + the **four** flat subject fields `subject_kind: SubjectKind \| None`, `subject_id: str \| None`, `codex_kind: CodexKind \| None` and (feature 015) the author's **current selection text** — all optional-and-absent, so `{}` is a complete body. **No subject object**; the selection is **text only, no offsets, never persisted** |
| `SubjectKind` | module-level `Literal` — `book-state` \| `chapters` \| `chapter` \| `characters` \| `locations` \| `facts` \| `codex-entry` \| `variants` \| `chapter-variants` \| `chats`; value-for-value with `frontend/src/work/subject.ts` |
| `ThinkingFrame` / `DeltaFrame` | `text: str` |
| `DoneFrame` | `message: ChatMessageResponse` |
| `ErrorFrame` | `message: str` |
| `CanvasField` | module-level `Literal["name", "body"]` — types the wire frame **and** `WriteCodexDraftArgs.field`, so the two cannot drift. **Deliberately NOT widened by feature 015**: a chapter's body *is* the `"body"` field, and a `"text"` member would give one concept two names |
| `CanvasFrame` | `subject_kind: SubjectKind`, `subject_id: str \| None` (**required but nullable** — `None` is UC-076's blank entry), `field: CanvasField`, **`op`** (feature 015 — replace / append / replace-selection, **defaulted to replace**, which is what made the widening free), `text: str` |
| `ToolCallFrame` | **feature `024`** — `tool_name: str`, `arguments: dict[str, Any]` (frontend twin: `Record<string, unknown>`). Needs its **own client-side narrowing** beside `canvasFrame`'s — a malformed payload is dropped **whole** |
| `ToolResultFrame` | **feature `024`** — `tool_name: str`, `result: str`, `ok: bool`. Same two-seam rule; note `ok: false` and `result: ""` are **falsy but valid** and must survive narrowing |
| `ToolTraceEntry` | **feature `024`** — `tool_name: str`, `arguments: dict[str, Any]`, `result: str`, `ok: bool`. The persisted form of one call/result pair |
| `ToolTrace` | **feature `024`** — `entries: list[ToolTraceEntry]`, plus `parse_column` / `to_column`: the **only** reader and writer of `ChatMessage.tool_trace`. `parse_column` **tolerates an unparseable stored value** (returns nothing rather than raising) — the one JSON-in-TEXT gate that does, see `backend/persistence.md` |

DTOs holding `model_name` carry `model_config = ConfigDict(protected_namespaces=())` — the documented Pydantic fix, verified warning-free.

### Assistant configuration (feature 012) — `app/models/schemas/assistant_config.py`

| DTO | Shape |
|-----|-------|
| `ToolResponse` | `name: str`, `description: str` — **exactly two fields**; no `args_schema`, no `callable` |
| `ToolsListResponse` | `items: list[ToolResponse]` |
| `AssistantModeResponse` | `key: str`, `system_prompt: str \| None`, `tool_names: list[str]`, `sub_agent_ids: list[str]`, `created_at`, `modified_at` |
| `AssistantModesListResponse` | `items: list[AssistantModeResponse]` |
| `UpdateAssistantModeRequest` | `system_prompt: str \| None`, `tool_names: list[str]`, `sub_agent_ids: list[str]` — **all three required in the body**; values may be `null` / `[]` |
| `SubAgentResponse` | `id: str`, `name: str`, `system_prompt: str` (**non-nullable**, unlike the mode's), `disabled: bool`, `llm_server_id: str \| None`, `model_name: str \| None`, `tool_names: list[str]`, `mode_keys: list[str]`, `created_at`, `modified_at` |
| `SubAgentsListResponse` | `items: list[SubAgentResponse]` |
| `CreateSubAgentRequest` | `name`, `system_prompt`, `llm_server_id`, `model_name` (**all four required — the model pair must be passed explicitly, including the inherit case `null` + `null`**), plus `tool_names: list[str] = []`, `mode_keys: list[str] = []` |
| `UpdateSubAgentRequest` | identical six fields. **No `disabled`** — enable/disable are their own zero-body endpoints |

Plural DTO fields for singular columns: `mode_tool.tool_name` → `tool_names`, `mode_subagent.sub_agent_id` → `sub_agent_ids`, `mode_subagent.mode_key` → `mode_keys`.

### Codex (feature 013) — `app/models/schemas/codex.py`

| DTO | Shape |
|-----|-------|
| `CreateCodexEntryRequest` | `kind: CodexKind`, `name: str \| None = None`, `body: str` |
| `UpdateCodexEntryRequest` | `name: str \| None = None`, `body: str`, `expected_modified_at: datetime \| None` (**required but nullable**). **`kind` is absent by design** — not updatable |
| `CodexEntryResponse` | `id: str`, `book_id: str`, `kind: CodexKind`, `name: str \| None`, `body: str`, `archived: bool`, `author_id: str`, `modified_by: str \| None`, `created_at`, `modified_at` |
| `CodexEntryListResponse` | `items: list[CodexEntryResponse]` |
| `CodexErrorDetail` | **`TypedDict` in `app/routes/codex.py`**, not a schema — `reason: str`, `message: str`. The `detail` body of every `CodexError` refusal; a `TypedDict` satisfies the no-free-dictionaries rule without putting a Pydantic model in `routes/` |

### Per-author system prompt (feature 021) — `app/models/schemas/book_author_prompts.py`

| DTO | Shape |
|-----|-------|
| `UpdateBookAuthorPromptRequest` | `system_prompt: str` — required, no default; `""` is valid input |
| `BookAuthorPromptResponse` | `book_id: str`, `system_prompt: str` (never nullable; `""` = "no prompt"), `modified_at: datetime \| None`. **No `user_id`**, and no other field a caller could vary |

### Chapters and the per-chapter prompt (feature 014) — `app/models/schemas/{chapters,chapter_author_prompts}.py`

| DTO | Shape |
|-----|-------|
| `CreateChapterRequest` | `title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]`, `sketch: str`. The non-blank rule is the **field's**, so `""` and a whitespace-only title answer **422** and never reach the service; the stored title is the **stripped** value. `sketch` carries no constraint (`""` is legitimate). **No ordinal** — a new chapter is appended |
| `UpdateChapterSketchRequest` | `sketch: str` — **no version token**: sketch edits are last-write-wins and do not bump `Chapter.version`, which tracks the body only |
| `ReorderChaptersRequest` | `chapter_ids: list[str]` — the **full** ordered set; a list that is not exactly the book's current chapter set is refused **400** |
| `ChapterResponse` | `id: str`, `book_id: str`, `ordinal: int`, `title: str`, `state: ChapterState`, `sketch: str`, `version: int`, `created_at`, `modified_at`, and **since `016`: `summary: str \| None`, `summary_status: SummaryStatus \| None`**. Still **no `text`** (the body is a sub-resource) and **no `system_prompt`** (its own route). The summary rides the resource rather than a sub-resource because it is small, read-only and read wherever the chapter is |
| `ChapterListResponse` | `chapters: list[ChapterResponse]`, **`can_reorder: bool`** — a caller-relative affordance hint, mirrored by the client and never enforced on |
| `UpdateChapterAuthorPromptRequest` | `system_prompt: str` — required, no constraint; `""` is how an author clears a prompt |
| `ChapterAuthorPromptResponse` | **exactly three fields** — `chapter_id: str`, `system_prompt: str` (never nullable), `modified_at: datetime \| None`. **No `user_id`** (the subject is always the caller), no `created_at`, no `book_id` |

### The chapter body (feature 015) — `app/models/schemas/chapters.py`

| DTO | Shape |
|-----|-------|
| `ChapterTextResponse` | `chapter_id: str`, `state: ChapterState`, `text: str`, **`version: int` — a JSON *number*, not a string** (the string-id rule exists for snowflakes past 2^53; a counter is not one), `modified_at`. `state` rides along deliberately: the version and the state that qualify a save must arrive **with the payload they qualify**. **No `can_write`** |
| `UpdateChapterTextRequest` | `text: str`, `expected_version: int` — the whole body, every time. **No placement, no line numbers, no partial write**: placement is computed server-side |

The body is a **sub-resource, not a field on `ChapterResponse`** — `014` has one `_to_response` serving both the list and the item, so a body added for the item would be a body on every row.

### Continuity and flags (feature 016) — `app/models/schemas/{continuity,flags}.py`

| DTO | Shape |
|-----|-------|
| `UpdateBookStateNotesRequest` | `active_notes: str` — the whole live set, every time; `""` is valid |
| `BookStateNotesResponse` | `book_id: str`, `active_notes: str`, `modified_at: datetime \| None` |
| `ChapterNoteChangesetResponse` | `chapter_id: str`, `added: str`, `modified: str`, `deleted: str`, `status: NoteStatus \| None`, `created_at`/`modified_at: datetime \| None`. **A `null` status with three empty strings is the "no row yet" shape**, returned `200` |
| `ChapterContinuityResponse` | `chapter_id: str`, `title: str`, `ordinal: int`, `summary: str \| None`, `summary_status: SummaryStatus \| None`, `changeset: ChapterNoteChangesetResponse \| None`, `warnings: list[FlagResponse]` |
| `BookContinuityResponse` | `items: list[ChapterContinuityResponse]` |
| `FlagResponse` | `id: str`, `chapter_id: str`, `origin: FlagOrigin` (`check`\|`person`), `comment: str`, `status: FlagStatus` (`open`\|`resolved`), `created_by: str`, `created_at: datetime \| None`, `resolved_by: str \| None`, `resolved_at: datetime \| None` |
| `FlagListResponse` | `items: list[FlagResponse]` |
| `RaiseFlagRequest` | `comment: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]` — the non-blank rule is the **field's**, so an empty comment answers **422** and never reaches the service (the `CreateChapterRequest.title` precedent) |

- The `ChapterContinuityResponse.warnings` **field name is a survival from the reversed round-6 vocabulary**; the term everywhere else — entity, table, DTO names, UI strings — is **flag** (`domain-continuity.md`). Do not read the field name as a second concept.
- **No DTO carries an approval verb or an approver**, because no approval gate ships.

## Tables & enums

| Name | Module | Shape |
|------|--------|-------|
| `User` | `app/models/` (`db/users.py`) | SQLModel table — **first persistent entity**. `id` (app-generated snowflake, string in JSON — **migrated**, `fast/001`; only the `user_id` token claim still int, deferred to feature 004), `username` (unique, indexed), `pwdhash` (nullable bcrypt; **null == disabled**, no `disabled` bool), `role: UserRole`, `jwt_signing_key` (nullable), `last_login`, `last_key_update`. No `salt` column. See `backend/features.md` → Domain models. |
| `UserRole` | `app/models/` | enum — `admin` \| `author` |
| `LlmServer` | `app/models/llm_server.py` (`db/llm_servers.py`) | SQLModel table — **second persistent entity** (feature 006). `id` (app-generated snowflake, `default_factory=generate_id`, string in JSON — **conformant**), `name`, `backend_type` (bare `str`, validated at service against `{"llama-swap","openai"}`), `base_url` (must include `/v1`), `api_key` (nullable; raw literal or `$ENV_VAR` token; never returned raw, masked as `has_api_key`), `enabled_models` (JSON-encoded `list[str]` in a TEXT column, decoded at service edge), `is_active`, `is_embedding` (≤1 row, clear-all-then-set), `embedding_model`, `created_at`, `modified_at`. See `backend/features.md` → LLM server connections. |
| `AssistantMode` | `app/models/` (`db/assistant_modes.py`) | FEAT-020 — **instance-global admin config**, seeded. **PK is `key`** (string ∈ `{edit-character, edit-location, edit-fact, write-chapter, close-chapter}`) **not a snowflake** — deliberate exception so seeded rows + links survive cross-instance import. `system_prompt` (nullable; null/empty valid), timestamps. Not admin-creatable. See `assistant-config.md`. |
| `SubAgent` | `app/models/` (`db/sub_agents.py`) | FEAT-020 — admin-created delegated worker. `id` (snowflake, string in JSON), `name` (**unique at DB level**), `system_prompt`, `disabled` (bool, disable-not-delete), `llm_server_id` (nullable FK → `LlmServer`) + `model_name` (nullable) — **both null = inherit main chat's model**, both set = specific, half-set invalid. See `assistant-config.md`. |
| `mode_tool` / `subagent_tool` / `mode_subagent` | `app/models/` (`db/mode_tools.py` / `db/subagent_tools.py` / `db/mode_subagents.py`) | FEAT-020 selection link tables. Surrogate snowflake PK + unique natural pair (`BookMember` pattern). `mode_tool(mode_key, tool_name)`, `subagent_tool(sub_agent_id, tool_name)`, `mode_subagent(mode_key, sub_agent_id)`. `tool_name` references `TOOL_REGISTRY` **by string, not FK**. `mode_subagent` is **one row per pair, edited from both mode and sub-agent views**; disabling a sub-agent deletes its `mode_subagent` rows. See `assistant-config.md`. |
| `TOOL_REGISTRY` | code — **`backend/app/services/tools.py`** | **Not a table** — a module-level `list[ToolDef]` of **frozen dataclasses**, mirroring `TABLE_REGISTRY` / `VECTOR_SOURCE_REGISTRY`. Selections persist by string `name`; the catalogue is **never exported**. `ToolDef` = `name: str`, `description: str`, `args_schema: type[BaseModel]`, `callable: Callable[..., object] \| None = None`, `binder: ToolBinder \| None = None` — **exactly one of `callable` / `binder`** is set. Feature 011 shipped one entry (`web_search`, plain `callable`, args `WebSearchArgs`); feature 013 widened `ToolDef` with the binder + `ToolContext` seam and added three **bound** entries — `codex_search` (`CodexSearchArgs`), `codex_read_entry` (`CodexEntryReadArgs`) and `write_codex_draft` (`WriteCodexDraftArgs`), all in `services/codex_tools.py`. **Feature 015 added four more bound entries** in `services/chapter_tools.py` — read the saved chapter body, replace the whole body, replace the author's selection, append to end — and `ToolContext` gained a **fifth field**, the author's selection text. **Feature 016 added five more** in `services/close_tools.py` — `draft_chapter_summary`, `draft_chapter_notes`, `propose_active_notes`, `raise_check_flag`, `read_continuity_context` — and `ToolContext` gained a **sixth field**, `active_notes_proposal: str \| None`, **mutated in place** and read once by `finalize_close_turn` (`None` ≠ `""` — see `assistant-runtime.md`). **Since feature `024` the five modes seed with a default tool set** (and a non-blank `system_prompt`), so the codex, chapter and close tools are reachable on a fresh install — reversing the "all nine ship unreachable" stance 013 set and 015/016 followed. The gating rule is unchanged: a mode an admin edits down to zero rows still resolves to nothing, and registration alone grants nothing. `ToolBinder = Callable[[ToolContext], Callable[..., object]]`; `ToolContext` = `book_id: int` + defaulted `access: BookAccess \| None`, `subject: ResolvedSubject \| None`, `emit_frame: FrameEmitter \| None`. `build_tool_bindings(tools, context=None)` **skips and logs** a bound tool with no context, preserving the client's every-definition-has-a-binding invariant. See `assistant-config.md` (the catalogue's place in the config model) and `assistant-runtime.md` (gating and binding at turn time). |
| `Book` | `app/models/book.py` (`db/books.py`) | Feature 008 (table) + 009 (behaviour). `id` (snowflake), `title`, `description`, `owner_id` FK → `users.id`, `collaboration_mode: CollaborationMode` (`free`\|`proposal`), `visibility: Visibility` (`private`\|`public`), `state: BookState` (`active`\|`archived`\|`quarantined`\|`destroyed`), `moderation_reason` / `moderated_by` / `moderated_at` (all nullable, unwritten — Stage-6 columns landed at Stage 2), `system_prompt` (**dormant — retained, written `""` at creation, exported, and read by nothing** since feature 021; there is no DROP COLUMN path — see `domain-book.md`), `active_notes` (materialised, **not on the wire**), `created_at` / `modified_at`. **Feature 022 added one `db/books.py` read, `list_public_for_reader(user_id)`** — the four-clause public-discovery query behind `GET /api/books/public`; clauses and reasoning in the `/api/books` section above. No column changed. |
| `BookMember` | `app/models/book_member.py` (`db/book_members.py`) | `id` (snowflake PK), `book_id`, `user_id`, `role: MemberRole`, `created_at`. **Unique `(book_id, user_id)`** carries "one membership per user per book". `MemberRole` is a single-value `(str, Enum)` — `co_author`. **The owner is not a member row** — ownership is `Book.owner_id`. |
| `BookAuthorPrompt` | `app/models/book_author_prompt.py` (`db/book_author_prompts.py`) | Feature 021. Surrogate **snowflake PK**, `book_id` FK → `books.id`, `user_id` FK → `users.id`, `system_prompt` (**required**, NOT NULL; `""` = "no prompt", never coerced to `None`), `created_at` / `modified_at`. **Unique `(book_id, user_id)`** (`uq_book_author_prompt_book_id_user_id`). `TABLE_REGISTRY` index **9**, immediately after `book_members`. Replaces `Book.system_prompt`. See `domain-book.md`. |
| Chapter family | `app/models/{chapter,chapter_change,chapter_text_revision,chapter_notes,flag}.py` | Feature 008 created `chapters`, `chapter_changes`, `chapter_text_revisions`, `chapter_note_changesets` and `flags` (with their `db/` modules and codecs) as the data floor. **Feature 014 built the skeleton half of `chapters`** — service, routes and both frontend surfaces — and added `db/chapters.py`'s `update` / `delete`. `Chapter.system_prompt` is **dormant** since 014 (superseded by `ChapterAuthorPrompt`, read by nothing, **codec retained** so pre-014 archives import). **Feature 015 built the body half**: `Chapter.text` (**Markdown**) and `version`, plus the **first writers** of `chapter_changes` and `chapter_text_revisions` — one row of each per save, written **`ChapterChange` → `ChapterTextRevision` → `Chapter`** with **no transaction** (none exists in `db/`; history before mutation). `chapter_changes.status` `pending` / `rejected` are **still unreached** (FEAT-010's and `018`'s). **Feature 016 gave `chapter_note_changesets` and `flags` their first readers and writers** — one changeset row per chapter (upserted by the close tools, `approved` by `finalize_close_turn`, `stale` on reopen, deleted on a discard), and flags raised `origin=person` by members or `origin=check` by the close run, with every `origin=check` flag on the chapter **deleted** at the start of the next run. It also gave `Chapter.summary` / `summary_status` and `state = closing` their first traffic, with **no migration**: those columns landed nullable at Stage 2 for exactly this. `db/` additions: `chapter_note_changesets.update` / `delete_by_chapter`, `flags.update` / `delete_check_flags_by_chapter`. Columns and the state machine live in `domain-chapter.md` / `domain-continuity.md`. |
| `ChapterAuthorPrompt` | `app/models/chapter_author_prompt.py` (`db/chapter_author_prompts.py`) | Feature 014. Surrogate **snowflake PK**, `chapter_id` FK → `chapters.id`, `user_id` FK → `users.id`, `system_prompt` (**required**, NOT NULL; `""` = "no prompt", never coerced to `None`), `created_at` / `modified_at`. **Unique `(chapter_id, user_id)`** (`uq_chapter_author_prompt_chapter_id_user_id`). `TABLE_REGISTRY` index **10**, immediately after `book_author_prompts` — and therefore immediately **before** its parent `chapters`: the one sanctioned exception to the registry's FK-dependency order, kept for adjacency and inert because no `PRAGMA foreign_keys=ON` exists and import is a per-table UPSERT (`backend/book-domain.md`). `db/` module is **three functions wide** — `create` / `get_by_chapter_and_user` / `update`, no `delete`, no `list_*`. Supersedes `Chapter.system_prompt`. See `domain-chapter.md`. |
| `CodexEntry` | `app/models/codex_entry.py` (`db/codex_entries.py`) | Feature 008 (table) + 013 (behaviour). `id` (snowflake), `book_id`, `kind: CodexKind` (`character`\|`location`\|`fact`), `name` (**nullable — a fact has none**), `body`, `archived`, **`author_id`** FK → `users.id` (**required**, the original creator), **`modified_by`** FK → `users.id` (**nullable**, the most recent editor, maintained by `services/codex.py`), `created_at` / `modified_at`. `modified_at` doubles as the **version token** (409 on mismatch). The **first and only** `VECTOR_SOURCE_REGISTRY` entry (`source_kind = codex_entry`). See `domain-codex.md`, `retrieval.md`. |
| `CodexEntryVersion` | `app/models/codex_entry_version.py` (`db/codex_entry_versions.py`) | `id` (snowflake), `entry_id` FK → `CodexEntry.id`, **`generation`** (non-null `int`, **1-based** within its entry, from `codex_entry_versions.next_generation`), `name` / `body` / `kind` **as they stood**, `author_id` (the editing user), `created_at`. Written by feature 013 on **every edit**, carrying the **prior** content; **no row on create**, so an unedited entry has no history. `019.codex-history` builds the read/restore surface on top. |
| `Chat` | `app/models/chat.py` (`db/chats.py`) | Feature 008 (table) + 011 (columns + behaviour). `id`, `book_id`, `author_id` (**private to that author**), `title`, **`llm_server_id`** (nullable FK → `llm_servers.id`), **`model_name`** (nullable) — **the pair moves together**, both null or both set, half-set refused — **`sampling_params`** (non-nullable TEXT holding JSON, gated by `ChatSamplingParams`, default = the serialized defaults), `archived`, `created_at` / `modified_at`. **No subject FK** — a chat is not bound to a chapter or codex entry. |
| `ChatMessage` | `app/models/chat.py` (`db/chat_messages.py`) | `id`, `chat_id`, `role`, `content`, **`reasoning`** (nullable — the model's thinking, when the server surfaced any), **`position`** (non-null `int`, the explicit ordinal alongside `created_at`; `next_position` = `0` empty / `max+1`), `created_at`, and **since `024`: `tool_trace`** (nullable TEXT holding JSON, gated by the Pydantic `ToolTrace`; `NULL` when the turn called no tool). **`tool_trace` is the first column to use `db/engine.py`'s `ADDITIVE_COLUMNS` seam** — a new column on an existing table needs an entry there in the same change, or existing installs break on every INSERT (`backend/persistence.md`). |

## Conventions

- **Entity ids = Snowflake 64-bit ints** — 41-bit ms timestamp (fixed epoch) / 10-bit node id (`BOOKWRITER_NODE_ID`, default 0) / 12-bit sequence; app-generated via `app/ids.py` `generate_id()`. **Serialized as strings** in JSON/JSONL/DTOs (they exceed JS 2^53; a number loses precision); `from_dict` also accepts a legacy JSON number. Frontend `.d.ts` types ids as `string`. See `backend/auth-ids.md` → Conventions — entity ID strategy.

## Frontend `src/api/` pattern

- `client.ts` — `request<T>(url, opts?)`: Bearer auth from `auth.ts` `getToken()`, `Content-Type: application/json`, JSON-stringified body, `AbortSignal` pass-through, `204 → undefined`, non-2xx normalized to `ApiError(status, message, details?)` via `throwApiError` (reads `{ detail }`). Also exports `authHeaders()`.
- `sse.ts` — `streamPost(url, body, handlers): AbortController`: hand-rolled fetch-POST SSE reader (NOT `EventSource`).
- Resource modules `api/<resource>.ts` namespace-import and call `request<T>`. Example: `api/health.ts` `getHealth(signal?)` → `request<HealthResponse>("/api/health", { signal })`.
- `api/db.ts` (feature 007) adds the first **blob-download** (`exportDatabase()` → `res.blob()` browser save) and **multipart-upload** (`importDatabase(file)` → `FormData` field `file`, no JSON `Content-Type`) helpers, both **bypassing `request<T>`** (JSON-only) while still reading `getToken()` Bearer — the sanctioned exception alongside `sse.ts`.
- **Feature 011 established two seams around streaming. Both are deliberate departures from the module's conventions; copy them rather than re-deriving.**
  - `client.ts` exports **`refreshAuthToken(): Promise<void>`**, a reusable entry point a streaming caller **awaits before opening the stream**. It shares the extracted `performTokenRefresh` with `request<T>`'s on-401 `silentRefreshRetry`, so there is exactly **one** refresh path and one `logout()` fallback. It exists because `sse.ts:streamPost` **bypasses `request<T>`** and therefore misses the silent on-401 refresh entirely — without the explicit await, a stream opened on a stale token fails with no retry. `api/chats.ts:streamChatTurn` awaits it first, then calls `streamPost`.
  - **`streamPost` owns and returns its own `AbortController` and takes no `signal`.** `streamChatTurn(bookId, chatId, prompt, handlers, subject?) → Promise<AbortController>` therefore breaks the module-wide trailing-`signal?: AbortSignal` convention: the caller stores the returned controller and aborts through it. Consequence to know: the page-level mount `AbortController` does **not** cancel a live turn — the shell's unmount cleanup must call the state's stop effect explicitly.
  - `streamPost`'s `done` branch calls `onDone?.()` with **no argument**, discarding the parsed payload — so `DoneFrame.message` is unreachable through this seam and the state **reloads** the chat instead. `canvas` rides `streamPost`'s existing generic-event branch, so feature 013 added a frame without opening `sse.ts` at all.
  - Full rules and the MobX side live in `frontend.md`; the working page's draft/canvas tier is `frontend-work-drafts.md`.
- **Feature 015 added a second client seam for canvas frames, and it is the one that bites.** `api/chats.ts` holds a **module-private `canvasFrame` narrowing** that rebuilds the frame **field by field**; a backend field declared in `types/chats.d.ts` but not added there is **silently dropped**, invisibly to page specs (which call the real dispatcher rather than crossing the wire). Widening a frame is **two edits, not one**.

## Frontend stack and module tier

- **Runtime dependencies, by the feature that added them:** `@dnd-kit/core` + `@dnd-kit/sortable` (feature `014`, drag-and-drop); **`@mantine/tiptap` over TipTap/ProseMirror + `tiptap-markdown` (feature `015`, the chapter body editor)**; `react-markdown` (feature `011`, still **no plugins configured**). TipTap's major is pinned to **`@mantine/tiptap`'s declared peer range for the Mantine major** — a rule, not a version string, because the range moves with Mantine. The editor's stylesheet is imported **from the component**, so it ships with the only bundle that uses it.
- **`Chapter.text` is Markdown; the codex entry body is not.** Markdown stops at chapter text, and `CodexEntryPage` was not reworked.
- **`src/work/`'s module tier has six members:** `restoreBuffer.ts` (010), `activeChat.ts` (011), `contentSubject.ts` (013 — canvas targets, plus 015's selection registry), **`chapterUndo.ts` (015 — assistant-write undo snapshots per `(book, chapter)`, capped at 20, in memory only)**, **`closeTurn.ts` (016 — the close-turn controller registration plus the active close turn's `(book, chapter)`, in memory only; `contentSubject.ts`'s registration idiom applied to "post a turn")**, **`chatPaneController.ts` (`023` — the shell's open-a-chat entry point, called by the chats list page; in memory only, and the tier's first member holding neither draft nor subject)**. Full sanctions in `frontend-work-drafts.md`.
- **Feature 016 buffers nothing.** State notes, summaries, changesets and flags are all short round-trips with **no version token**, so none of them enters the restore buffer — a sanctioned exclusion on the chapter sketch's reasoning.
- **Two conventions feature 015 froze:** an external write into a controlled third-party editor is applied by **remount on a bumped key**, never by an effect; and a heavy third-party widget is **mocked in page specs** behind a frozen four-prop seam, with its own behaviour covered by `[manual/live]` criteria. Both in `frontend.md`.

## Frontend MobX page-state — reference example

`src/user/pages/HealthPage.tsx` + `healthPageState.ts` is the canonical page-state convention example; mirror it for new page work:

- async-resource **trio**: `health` / `healthStatus` / `healthError`
- external effectful `loadHealth(state, signal)` using `runInAction`
- `observer` on the component
- stable instance via `useState(() => new HealthPageState())`
- mount `useEffect([])` — loads on mount, aborts on unmount

Full rules live in `frontend.md`.
