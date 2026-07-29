# Quick Reference

Dense, agent-first index of concrete endpoints, DTOs, and patterns as they land. **Current through features 003–013 and 021 (2026-07-29).** Append here as the system grows; this file is intentionally terse and is the one file exempt from the folder's ~400-line limit. For the reasoning behind each shape, follow the pointers into `backend.md`, `backend/features.md`, `system-overview.md` and the domain files.

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
| `GET` | `/api/books/{book_id}` | `200` | — → `BookDetailResponse` | members-only detail (owner + co-author) with the `members` list |
| `GET` | `/api/books/{book_id}/read` | `200` | — → `ReaderBookResponse` | the **reader-safe projection** — see below |
| `POST` | `/api/books/{book_id}/archive` | `200` | — → `BookResponse` | owner-only; already archived → **409** |
| `POST` | `/api/books/{book_id}/unarchive` | `200` | — → `BookResponse` | owner-only; not archived → **409** |
| `POST` | `/api/books/{book_id}/transfer` | `200` | `TransferOwnershipRequest` → `BookResponse` | owner-only; target is not a co-author → **409**, ownership unchanged |
| `POST` | `/api/books/{book_id}/members` | `200` | `AddMemberRequest` → `BookDetailResponse` | owner-only; duplicate membership → **409** |
| `DELETE` | `/api/books/{book_id}/members/{user_id}` | `200` | — → `BookDetailResponse` | owner-only; target is not a member → **404** |
| `PATCH` | `/api/books/{book_id}/visibility` | `200` | `SetVisibilityRequest` → `BookResponse` | owner-only |

- **Reader-safe projection.** `GET /{book_id}/read` returns `ReaderBookResponse` — **exactly** `{title, chapters}`. The exclusion is **structural** (a separate DTO), not a filter: `members`, `owner_id`, `id`, `state`, `visibility`, `collaboration_mode`, `description`, `system_prompt`, `active_notes` and the moderation triple are all absent. `chapters` is an **empty placeholder TOC** until chapter content exists.
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

- **404, not 403, for another author's chat.** A chat is private to `Chat.author_id` — from co-authors, the book's owner and admins alike. The rule is a **service-level ownership check** in `services/chats.py` layered on the `book_access` dependency; **no `Capability` member was added** and `_CAPABILITY_MATRIX` is unchanged, because the matrix maps capability → role and has no notion of "author of *this row*". Answering 404 means existence is never confirmed. Later chat-touching features copy this. See `domain-chat.md`, `authorization.md`.
- **Error taxonomy** (`ChatErrorReason`): `chat_not_found` → **404**; `invalid_model_pair` / `unknown_or_inactive_server` / `model_not_enabled` / `invalid_sampling` → **400**. The turn additionally maps `LlmServerError(env_not_set)` → **400**.
- **Pre-stream vs post-open.** `prepare_turn` runs the refusals (no model pair, missing/inactive server, unresolvable `$ENV` key, chat not owned) **before the first frame**, so they answer as ordinary HTTP status codes with nothing persisted. A failure **after** the stream opens surfaces as an `error` frame over HTTP **200** — never a 500 and never a hung stream.
- **The five SSE frames** (`event: <name>` / `data: <payload JSON>`; the route serializer is **generic over the event name**, so widening the vocabulary needs no route change):

| Frame | Payload | Meaning |
|---|---|---|
| `thinking` | `ThinkingFrame{text}` | a chunk routed to the thinking channel by `ThinkSplitter` (`<think>` … `</think>`, split by BookWriter itself) |
| `delta` | `DeltaFrame{text}` | a chunk of assistant content |
| `done` | `DoneFrame{message: ChatMessageResponse}` | terminal success, carrying the persisted assistant message |
| `error` | `ErrorFrame{message}` | terminal failure after the stream opened |
| `canvas` | `CanvasFrame{subject_kind, subject_id, field, text}` | **feature 013** — a shared-canvas draft for the open codex entry; persists nothing |

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
| `ReaderBookResponse` | `title: str`, `chapters: list[str]` — the reader-safe projection; separate DTO, not a filtered `BookResponse` |
| `TransferOwnershipRequest` | `target_user_id: str` |
| `AddMemberRequest` | `target_user_id: str` |
| `SetVisibilityRequest` | `visibility: Visibility` |

### Chats and the turn (features 011 / 013) — `app/models/schemas/chats.py`

| DTO | Shape |
|-----|-------|
| `ChatSamplingParams` | `temperature=0.8`, `top_p=0.95`, `top_k=40`, `repeat_penalty=1.1`, `min_p=0.05`, `max_tokens: int \| None = None`, `seed: int \| None = None`, `presence_penalty=0.0`, `frequency_penalty=0.0`, `enable_thinking=True`. **`top_k` / `repeat_penalty` / `min_p` are persisted but cannot reach either backend** under `llm-client` v0.1.4 — see `assistant-runtime.md` |
| `CreateChatRequest` | all optional: `title`, `llm_server_id`, `model_name`, `sampling` |
| `UpdateChatRequest` | all optional: `title`, `archived`, `llm_server_id`, `model_name`, `sampling` |
| `ChatResponse` | `id: str`, `book_id: str`, `author_id: str`, `title: str`, `llm_server_id: str \| None`, `model_name: str \| None`, `sampling: ChatSamplingParams`, `archived: bool`, `created_at`, `modified_at` |
| `ChatListResponse` | `items: list[ChatResponse]` |
| `ChatMessageResponse` | `id: str`, `chat_id: str`, `role: str`, `content: str`, `reasoning: str \| None`, `position: int`, `created_at` |
| `ChatMessageListResponse` | `items: list[ChatMessageResponse]` — declared; no route returns it yet |
| `ChatDetailResponse` | `chat: ChatResponse`, `messages: list[ChatMessageResponse]` |
| `ModelOptionResponse` | `server_id: str`, `server_name: str`, `model_name: str` |
| `ModelOptionListResponse` | `items: list[ModelOptionResponse]` |
| `TurnRequest` | `prompt: str \| None = None` (absent = retry) + the subject triple `subject_kind: SubjectKind \| None`, `subject_id: str \| None`, `codex_kind: CodexKind \| None`, all optional-and-absent, so `{}` is a complete body |
| `SubjectKind` | module-level `Literal` — `book-state` \| `chapters` \| `chapter` \| `characters` \| `locations` \| `facts` \| `codex-entry` \| `variants` \| `chapter-variants` \| `chats`; value-for-value with `frontend/src/work/subject.ts` |
| `ThinkingFrame` / `DeltaFrame` | `text: str` |
| `DoneFrame` | `message: ChatMessageResponse` |
| `ErrorFrame` | `message: str` |
| `CanvasField` | module-level `Literal["name", "body"]` — types the wire frame **and** `WriteCodexDraftArgs.field`, so the two cannot drift |
| `CanvasFrame` | `subject_kind: SubjectKind`, `subject_id: str \| None` (**required but nullable** — `None` is UC-076's blank entry), `field: CanvasField`, `text: str` |

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

## Tables & enums

| Name | Module | Shape |
|------|--------|-------|
| `User` | `app/models/` (`db/users.py`) | SQLModel table — **first persistent entity**. `id` (app-generated snowflake, string in JSON — **migrated**, `fast/001`; only the `user_id` token claim still int, deferred to feature 004), `username` (unique, indexed), `pwdhash` (nullable bcrypt; **null == disabled**, no `disabled` bool), `role: UserRole`, `jwt_signing_key` (nullable), `last_login`, `last_key_update`. No `salt` column. See `backend/features.md` → Domain models. |
| `UserRole` | `app/models/` | enum — `admin` \| `author` |
| `LlmServer` | `app/models/llm_server.py` (`db/llm_servers.py`) | SQLModel table — **second persistent entity** (feature 006). `id` (app-generated snowflake, `default_factory=generate_id`, string in JSON — **conformant**), `name`, `backend_type` (bare `str`, validated at service against `{"llama-swap","openai"}`), `base_url` (must include `/v1`), `api_key` (nullable; raw literal or `$ENV_VAR` token; never returned raw, masked as `has_api_key`), `enabled_models` (JSON-encoded `list[str]` in a TEXT column, decoded at service edge), `is_active`, `is_embedding` (≤1 row, clear-all-then-set), `embedding_model`, `created_at`, `modified_at`. See `backend/features.md` → LLM server connections. |
| `AssistantMode` | `app/models/` (`db/assistant_modes.py`) | FEAT-020 — **instance-global admin config**, seeded. **PK is `key`** (string ∈ `{edit-character, edit-location, edit-fact, write-chapter, close-chapter}`) **not a snowflake** — deliberate exception so seeded rows + links survive cross-instance import. `system_prompt` (nullable; null/empty valid), timestamps. Not admin-creatable. See `assistant-config.md`. |
| `SubAgent` | `app/models/` (`db/sub_agents.py`) | FEAT-020 — admin-created delegated worker. `id` (snowflake, string in JSON), `name` (**unique at DB level**), `system_prompt`, `disabled` (bool, disable-not-delete), `llm_server_id` (nullable FK → `LlmServer`) + `model_name` (nullable) — **both null = inherit main chat's model**, both set = specific, half-set invalid. See `assistant-config.md`. |
| `mode_tool` / `subagent_tool` / `mode_subagent` | `app/models/` (`db/mode_tools.py` / `db/subagent_tools.py` / `db/mode_subagents.py`) | FEAT-020 selection link tables. Surrogate snowflake PK + unique natural pair (`BookMember` pattern). `mode_tool(mode_key, tool_name)`, `subagent_tool(sub_agent_id, tool_name)`, `mode_subagent(mode_key, sub_agent_id)`. `tool_name` references `TOOL_REGISTRY` **by string, not FK**. `mode_subagent` is **one row per pair, edited from both mode and sub-agent views**; disabling a sub-agent deletes its `mode_subagent` rows. See `assistant-config.md`. |
| `TOOL_REGISTRY` | code — **`backend/app/services/tools.py`** | **Not a table** — a module-level `list[ToolDef]` of **frozen dataclasses**, mirroring `TABLE_REGISTRY` / `VECTOR_SOURCE_REGISTRY`. Selections persist by string `name`; the catalogue is **never exported**. `ToolDef` = `name: str`, `description: str`, `args_schema: type[BaseModel]`, `callable: Callable[..., object] \| None = None`, `binder: ToolBinder \| None = None` — **exactly one of `callable` / `binder`** is set. Feature 011 shipped one entry (`web_search`, plain `callable`, args `WebSearchArgs`); feature 013 widened `ToolDef` with the binder + `ToolContext` seam and added three **bound** entries — `codex_search` (`CodexSearchArgs`), `codex_read_entry` (`CodexEntryReadArgs`) and `write_codex_draft` (`WriteCodexDraftArgs`), all in `services/codex_tools.py`. `ToolBinder = Callable[[ToolContext], Callable[..., object]]`; `ToolContext` = `book_id: int` + defaulted `access: BookAccess \| None`, `subject: ResolvedSubject \| None`, `emit_frame: FrameEmitter \| None`. `build_tool_bindings(tools, context=None)` **skips and logs** a bound tool with no context, preserving the client's every-definition-has-a-binding invariant. See `assistant-config.md` (the catalogue's place in the config model) and `assistant-runtime.md` (gating and binding at turn time). |
| `Book` | `app/models/book.py` (`db/books.py`) | Feature 008 (table) + 009 (behaviour). `id` (snowflake), `title`, `description`, `owner_id` FK → `users.id`, `collaboration_mode: CollaborationMode` (`free`\|`proposal`), `visibility: Visibility` (`private`\|`public`), `state: BookState` (`active`\|`archived`\|`quarantined`\|`destroyed`), `moderation_reason` / `moderated_by` / `moderated_at` (all nullable, unwritten — Stage-6 columns landed at Stage 2), `system_prompt` (**dormant — retained, written `""` at creation, exported, and read by nothing** since feature 021; there is no DROP COLUMN path — see `domain-book.md`), `active_notes` (materialised, **not on the wire**), `created_at` / `modified_at`. |
| `BookMember` | `app/models/book_member.py` (`db/book_members.py`) | `id` (snowflake PK), `book_id`, `user_id`, `role: MemberRole`, `created_at`. **Unique `(book_id, user_id)`** carries "one membership per user per book". `MemberRole` is a single-value `(str, Enum)` — `co_author`. **The owner is not a member row** — ownership is `Book.owner_id`. |
| `BookAuthorPrompt` | `app/models/book_author_prompt.py` (`db/book_author_prompts.py`) | Feature 021. Surrogate **snowflake PK**, `book_id` FK → `books.id`, `user_id` FK → `users.id`, `system_prompt` (**required**, NOT NULL; `""` = "no prompt", never coerced to `None`), `created_at` / `modified_at`. **Unique `(book_id, user_id)`** (`uq_book_author_prompt_book_id_user_id`). `TABLE_REGISTRY` index **9**, immediately after `book_members`. Replaces `Book.system_prompt`. See `domain-book.md`. |
| Chapter family | `app/models/{chapter,chapter_change,chapter_text_revision,chapter_notes,flag}.py` | **Tables only.** Feature 008 created `chapters`, `chapter_changes`, `chapter_text_revisions`, `chapter_note_changesets` and `flags` (with their `db/` modules and codecs) as the data floor; **no service, no route and no frontend surface is built**. Columns and the state machine are in `domain-chapter.md` / `domain-continuity.md` — not duplicated here, because nothing has shipped against them. |
| `CodexEntry` | `app/models/codex_entry.py` (`db/codex_entries.py`) | Feature 008 (table) + 013 (behaviour). `id` (snowflake), `book_id`, `kind: CodexKind` (`character`\|`location`\|`fact`), `name` (**nullable — a fact has none**), `body`, `archived`, **`author_id`** FK → `users.id` (**required**, the original creator), **`modified_by`** FK → `users.id` (**nullable**, the most recent editor, maintained by `services/codex.py`), `created_at` / `modified_at`. `modified_at` doubles as the **version token** (409 on mismatch). The **first and only** `VECTOR_SOURCE_REGISTRY` entry (`source_kind = codex_entry`). See `domain-codex.md`, `retrieval.md`. |
| `CodexEntryVersion` | `app/models/codex_entry_version.py` (`db/codex_entry_versions.py`) | `id` (snowflake), `entry_id` FK → `CodexEntry.id`, **`generation`** (non-null `int`, **1-based** within its entry, from `codex_entry_versions.next_generation`), `name` / `body` / `kind` **as they stood**, `author_id` (the editing user), `created_at`. Written by feature 013 on **every edit**, carrying the **prior** content; **no row on create**, so an unedited entry has no history. `019.codex-history` builds the read/restore surface on top. |
| `Chat` | `app/models/chat.py` (`db/chats.py`) | Feature 008 (table) + 011 (columns + behaviour). `id`, `book_id`, `author_id` (**private to that author**), `title`, **`llm_server_id`** (nullable FK → `llm_servers.id`), **`model_name`** (nullable) — **the pair moves together**, both null or both set, half-set refused — **`sampling_params`** (non-nullable TEXT holding JSON, gated by `ChatSamplingParams`, default = the serialized defaults), `archived`, `created_at` / `modified_at`. **No subject FK** — a chat is not bound to a chapter or codex entry. |
| `ChatMessage` | `app/models/chat.py` (`db/chat_messages.py`) | `id`, `chat_id`, `role`, `content`, **`reasoning`** (nullable — the model's thinking, when the server surfaced any), **`position`** (non-null `int`, the explicit ordinal alongside `created_at`; `next_position` = `0` empty / `max+1`), `created_at`. |

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

## Frontend MobX page-state — reference example

`src/user/pages/HealthPage.tsx` + `healthPageState.ts` is the canonical page-state convention example; mirror it for new page work:

- async-resource **trio**: `health` / `healthStatus` / `healthError`
- external effectful `loadHealth(state, signal)` using `runInAction`
- `observer` on the component
- stable instance via `useState(() => new HealthPageState())`
- mount `useEffect([])` — loads on mount, aborts on unmount

Full rules live in `frontend.md`.
