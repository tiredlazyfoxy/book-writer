# Feature 027 — side-chats

| Step | File                                  | Status  | Verifier | Date |
|------|---------------------------------------|---------|----------|------|
| 001  | `001.side-chat-columns.md`            | done    | PASS     | 2026-09-21 |
| 002  | `002.turn-filter-start-finish.md`     | done    | PASS     | 2026-09-21 |
| 003  | `003.side-chat-inject-delete.md`      | done    | PASS     | 2026-09-21 |
| 004  | `004.side-chat-api-and-grouping.md`   | done    | PASS     | 2026-09-21 |
| 005  | `005.side-chat-actions-state.md`      | done    | PASS     | 2026-09-21 |
| 006  | `006.side-chat-group-rendering.md`    | done    | PASS     | 2026-09-21 |
| 007  | `007.side-chat-pane-controls.md`      | done    | PASS     | 2026-09-21 |

## Files Changed

### Step 001 — side-chat columns, the additive seam, the `db/` functions and the JSONL codec
- `backend/app/models/chat.py` — `Chat.active_side_chat_id` / `ChatMessage.side_chat_id` nullable int columns (placed by the skeleton; verified, unchanged)
- `backend/app/db/engine.py` — `ADDITIVE_COLUMNS` entries for both columns (placed by the skeleton; verified, unchanged)
- `backend/app/db/chat_messages.py` — bodies of `list_transcript`, `side_chat_exists`, `clear_side_chat`, `delete_by_side_chat`; module docstring records the bulk `sa_update` / `sa_delete` shape beside the D-D sanction
- `backend/app/services/db_import_export.py` — `active_side_chat_id` / `side_chat_id` keys in the chat and chat-message codecs (string-or-null out, `.get` + `int` in)

### Step 002 — the two DTO fields, the capture-once transcript filter, start + finish
- `backend/app/models/schemas/chats.py` — `ChatResponse.active_side_chat_id` / `ChatMessageResponse.side_chat_id` required-nullable string fields (placed by the skeleton; verified, unchanged)
- `backend/app/services/chats.py` — real mappings in `_to_chat_response` / `_to_message_response` (skeleton placeholders removed); `_parse_side_chat_id`, `start_side_chat` (mints via `generate_id`), `finish_side_chat` (pointer checked before rows, no message row touched); `from app.ids import generate_id` added
- `backend/app/services/chat_turn.py` — `run_turn` captures `active_side_chat_id` once before any await, stamps it on both `ChatMessage` inserts (user + assistant, retry path included) and loads history via `chat_messages.list_transcript`
- `backend/app/routes/chats.py` — `_CHAT_ERROR_STATUS` entries and the start / finish handlers (placed by the skeleton; verified, unchanged)

### Step 003 — inject + delete of a side chat
- `backend/app/services/chats.py` — bodies of `inject_side_chat` (existence checked before mutating, `clear_side_chat`, pointer cleared only when it equalled the id, `chats.update` always, detail returned through `get_chat`) and `delete_side_chat` (same check, `delete_by_side_chat`, no renumbering, returns nothing)
- `backend/app/routes/chats.py` — inject (200 `ChatDetailResponse`) and delete (204, no body) handlers placed by the skeleton; verified registered with those methods and status codes, unchanged

### Step 004 — the `.d.ts` fields, the four api functions and the `renderedTranscript` grouping
- `frontend/src/types/chats.d.ts` — `ChatResponse.active_side_chat_id` / `ChatMessageResponse.side_chat_id` required-nullable string fields (placed by the skeleton; verified, unchanged)
- `frontend/src/api/chats.ts` — bodies of `startSideChat`, `finishSideChat`, `injectSideChat` (POST-no-body `request<T>` calls, the `titleChat` shape) and `deleteSideChat` (the `llmServers.deleteServer` DELETE shape); signal forwarded, no request body
- `frontend/src/work/components/chat/chatPaneState.ts` — `RenderedMessage.sideChatId` mapped from `m.side_chat_id` and from `activeSideChatId` for the streaming placeholder; both optimistic `ChatMessageResponse` literals (`sendChatTurn`, close-turn) stamped with `state.activeSideChatId`; `activeSideChatId` computed; `renderedTranscript` single-pass grouping (a run breaks on any id change, no contiguity check — D-B); `toggleSideChatGroup` whole-object rewrite of `expandedSideChats`

### Step 005 — the action trio, the three `can…` computeds and the four effect functions
- `frontend/src/work/components/chat/chatPaneState.ts` — `sideChatActionsEnabled` (four "is X active at all" clauses, no book-id comparison), `canStartSideChat` / `canFinishSideChat`; `startSideChat` / `finishSideChat` (patch the `state.chats` entry by id with the returned chat; `messages` untouched on finish), `injectSideChat` (whole-array `messages` swap + chat patch), `deleteSideChat` (delete then `getChat` reload — the `finishTurn` idiom — clearing `sideChatDeleteConfirm` on both outcomes), `requestDeleteSideChat` / `dismissDeleteSideChat`; every effect guards on its computed inside the function, so a call while `busy` reaches no api

### Step 006 — the `MessageRow` extraction, `SideChatGroup` and the `MessageList` branch
- `frontend/src/work/components/chat/MessageRow.tsx` — body filled by moving `MessageList`'s per-message map JSX verbatim (user `Box data-role="user"` + `Paper` bubble; assistant `Stack data-role="assistant"` with `ThinkingBlock` / `ToolCallTrace` / `chat-markdown` `Markdown`), `msg` renamed to the `message` prop; reasoning lookup and `toggleToolCallRow` wiring unchanged
- `frontend/src/work/components/chat/SideChatGroup.tsx` — bordered `Paper` `role="group"` `aria-label="Side chat"`; header `Group` with the active / `Side chat · N messages` label `Text`, ONE swapping expand-collapse `ActionIcon` (finished groups only), and the Inject / Delete `ActionIcon`s disabled on `!sideChatActionsEnabled || bookId === undefined`; body maps `MessageRow` only when `group.expanded` (plain conditional — no `Collapse` / `Accordion`)
- `frontend/src/work/components/chat/MessageList.tsx` — maps `state.renderedTranscript` and branches on `item.kind`; `bookId` destructured and passed to each group; `ScrollArea` / `viewportRef` / `onScrollPositionChange` / styles untouched; the now-unused `Box` / `Paper` / `Text` / `Markdown` / `ThinkingBlock` / `ToolCallTrace` / `toggleToolCallRow` imports removed

### Step 007 — the Start / Finish slot, the delete `Modal`, the error `Alert` and the composer hint
- `frontend/src/work/components/chat/ChatPane.tsx` — ONE swapping `ActionIcon` before `New chat` (`aria-label` / icon / `disabled` / handler all switch on `activeSideChatId === null`; outside the `openedPanel` discriminator); the `@mantine/core` `Modal` delete confirmation (`Keep it` / `Delete side chat`, pending id read at click time, body naming the permanent message removal and the kept saved work); the `sideChatActionStatus === "error"` `Alert` beside the existing ones; `<MessageList state={state} bookId={bookId} />`
- `frontend/src/work/components/chat/Composer.tsx` — one `Text` hint `Replying in the side chat` above the `Textarea`, gated only on `activeSideChatId !== null`; the read-only rule, `canSend`, the two `Alert`s and the Send / Stop slot byte-identical

## Notes & Issues

- Step 004: `renderedTranscript`'s local `active` needed an explicit `: boolean` annotation — inferring it inside the loop tripped TS7022 (circular inference through the group literal). Behaviour unaffected.
- Step 001: `backend/app/db/llm_servers.py` module + `clear_all_embedding` docstrings still call it "the one sanctioned raw `sqlalchemy.update()` spot inside `db/`"; `chat_messages.clear_side_chat` / `delete_by_side_chat` are now a second (out of this step's Source files — not edited).

## Skeleton

### Step 001 — frozen interface (2026-09-20)

Model columns (declarative data, added whole — a column is not behaviour):
- `backend/app/models/chat.py` — `Chat.active_side_chat_id: int | None = Field(default=None)` — new (no FK, no index; docstring bullet per D-A)
- `backend/app/models/chat.py` — `ChatMessage.side_chat_id: int | None = Field(default=None)` — new (no FK, no index; docstring records that "finished" is derived, not stored — D-A)

Additive seam (declarative data, added whole; appended, not reordered):
- `backend/app/db/engine.py` — `ADDITIVE_COLUMNS` gains `("chat_messages", "side_chat_id")  # feature 027` and `("chats", "active_side_chat_id")  # feature 027` — changed (was the single `("chat_messages", "tool_trace")` entry)

`db/` functions (bodies `raise NotImplementedError`; the coder fills them, signatures are frozen):
- `backend/app/db/chat_messages.py` — `async def list_transcript(chat_id: int, active_side_chat_id: int | None) -> list[ChatMessage]` — new
- `backend/app/db/chat_messages.py` — `async def side_chat_exists(chat_id: int, side_chat_id: int) -> bool` — new
- `backend/app/db/chat_messages.py` — `async def clear_side_chat(chat_id: int, side_chat_id: int) -> int` — new (returns changed-row count)
- `backend/app/db/chat_messages.py` — `async def delete_by_side_chat(chat_id: int, side_chat_id: int) -> int` — new (returns deleted-row count; the module docstring carries the D-D hard-delete sanction note)
- Positional call convention: `list_transcript(chat_id, sid)`; the other three `(chat_id, side_chat_id)`. Parameter names are part of the frozen contract.

JSONL codec (signatures unchanged, NOT stubbed — the coder adds the keys; nothing here is edited by the skeleton):
- `backend/app/services/db_import_export.py` — `_chat_to_dict(chat: Chat) -> dict[str, object]` — unchanged signature; gains key `"active_side_chat_id"` as `str | None` on the wire (`str(x) if x is not None else None`)
- `backend/app/services/db_import_export.py` — `_dict_to_chat(data: dict[str, object]) -> Chat` — unchanged signature; restores `active_side_chat_id` via `data.get("active_side_chat_id")`, `int(...)` when present, `None` when the key is absent (legacy archive)
- `backend/app/services/db_import_export.py` — `_chat_message_to_dict(message: ChatMessage) -> dict[str, object]` — unchanged signature; gains key `"side_chat_id"` as `str | None` on the wire
- `backend/app/services/db_import_export.py` — `_dict_to_chat_message(data: dict[str, object]) -> ChatMessage` — unchanged signature; restores `side_chat_id` via `data.get("side_chat_id")`, `int(...)` when present, `None` when absent
- No `TABLE_REGISTRY` change (no new table).

Caller-compile edits (out of Source-files scope): None. All four `db/` functions are new; no existing symbol changed shape.
Gate: `cd backend && .venv/Scripts/python -c "import app.main"` — OK. Existing `tests/db/test_chat_messages.py`, `tests/db/test_chats.py`, `tests/services/test_db_import_export*.py` still pass against the new columns.

### Step 002 — frozen interface (2026-09-20)

DTO fields (declarative, added whole; both **required-nullable**, no default — the `llm_server_id` shape):
- `backend/app/models/schemas/chats.py` — `ChatResponse.active_side_chat_id: str | None` — new (appended after `modified_at`)
- `backend/app/models/schemas/chats.py` — `ChatMessageResponse.side_chat_id: str | None` — new (placed before the defaulted `tool_trace`)

Mappers (signatures unchanged; **placeholder, not the real mapping** — kept true-red for DoD-1's seeded-row half):
- `backend/app/services/chats.py` — `_to_chat_response(chat: Chat) -> ChatResponse` — unchanged signature; now passes `active_side_chat_id=None` with a `# Skeleton (027 step 002)` comment. The coder replaces the placeholder with `str(chat.active_side_chat_id) if chat.active_side_chat_id is not None else None`.
- `backend/app/services/chats.py` — `_to_message_response(message: ChatMessage) -> ChatMessageResponse` — unchanged signature; now passes `side_chat_id=None` with the same comment. The coder replaces it with `str(message.side_chat_id) if message.side_chat_id is not None else None`. This is the single mapper behind the `done` frame (`chat_turn.py:1069`) and the detail reload (D-E) — no second mapping site.
- `ChatResponse(` / `ChatMessageResponse(` are constructed **only** in these two mappers (grepped under `backend/`, tests included) — no other caller-compile edit exists.

Error taxonomy (declarative, added whole):
- `backend/app/services/chats.py` — `ChatErrorReason.side_chat_already_active = "side-chat-already-active"`, `ChatErrorReason.side_chat_not_found = "side-chat-not-found"`, `ChatErrorReason.side_chat_not_active = "side-chat-not-active"` — new members (kebab-case values, appended after `invalid_sampling`)
- `backend/app/routes/chats.py` — `_CHAT_ERROR_STATUS` gains `side_chat_already_active → 409`, `side_chat_not_found → 404`, `side_chat_not_active → 409` — changed (was five entries). `_map_chat_error` unchanged: `HTTPException(status_code=…, detail=err.message)`, no detail object.

Service functions (bodies `raise NotImplementedError`; the coder fills them, signatures frozen; positioned after `update_chat`, before `list_model_options`):
- `backend/app/services/chats.py` — `def _parse_side_chat_id(side_chat_id: str) -> int` — new, module-private (the `_parse_chat_id` twin; sync, not async; raises `ChatError(ChatErrorReason.side_chat_not_found, …)` on a non-numeric string; step 003 reuses it)
- `backend/app/services/chats.py` — `async def start_side_chat(access: authz.BookAccess, chat_id: str) -> ChatResponse` — new
- `backend/app/services/chats.py` — `async def finish_side_chat(access: authz.BookAccess, chat_id: str, side_chat_id: str) -> ChatResponse` — new
- Call convention: positional `(access, chat_id)` / `(access, chat_id, side_chat_id)`; wire ids are `str`, parsed inside the service. `generate_id` is **not yet imported** in `services/chats.py` — the coder adds `from app.ids import generate_id` (the models' import style) when filling `start_side_chat`.

Route handlers (HTTP-only glue, written whole — they contain no behaviour; the service stub raises; registered **after** `title_chat`, i.e. after the static `model-options` route, beside `turn` / `title`):
- `backend/app/routes/chats.py` — `@router.post("/{book_id}/chats/{chat_id}/side-chats", status_code=status.HTTP_201_CREATED)` `async def start_side_chat(chat_id: str, access: authz.BookAccess = Depends(authz.book_access)) -> ChatResponse` — new; body = `try: return await chats_service.start_side_chat(access, chat_id)` + the standard `BookAuthorizationError → _map_authz_error` / `ChatError → _map_chat_error` pair. No request body.
- `backend/app/routes/chats.py` — `@router.post("/{book_id}/chats/{chat_id}/side-chats/{side_chat_id}/finish")` `async def finish_side_chat(chat_id: str, side_chat_id: str, access: authz.BookAccess = Depends(authz.book_access)) -> ChatResponse` — new (200); body delegates to `chats_service.finish_side_chat(access, chat_id, side_chat_id)` with the same two `except` arms. No request body.
- Wire paths: `POST /api/books/{book_id}/chats/{chat_id}/side-chats` (201) and `POST /api/books/{book_id}/chats/{chat_id}/side-chats/{side_chat_id}/finish` (200). Verified registered via `router.routes`.

`services/chat_turn.py::run_turn` — **no signature change** (`async def run_turn(context: TurnContext, prompt: str | None) -> AsyncGenerator[TurnFrame, None]`), **nothing edited by the skeleton**. The coder fills exactly three internal touch points (D-C, capture-once):
1. `chat_turn.py:831` — immediately after `chat = context.chat` (before any further `await`), capture `active_side_chat_id = chat.active_side_chat_id` into one local. Read the pointer **once**; never re-read it at the sites below.
2. `chat_turn.py:841` (user row, inside `if prompt is not None:`) and `chat_turn.py:1053` (assistant row, both the normal path and the retry path where no user row exists) — pass `side_chat_id=<captured>` on each `ChatMessage(...)` insert.
3. `chat_turn.py:938` — replace `chat_messages.list_by_chat_ordered(chat.id)` with `chat_messages.list_transcript(chat.id, <captured>)` (step 001's frozen positional signature). The `{"role": m.role, "content": m.content}` mapping and everything after it are unchanged.
- The other two `list_by_chat_ordered` callers (`services/chats.py:get_chat`, `services/chat_titling.py`) stay **unfiltered** and are not touched (D-C).
- No change to `TurnRequest`, `DoneFrame`, any SSE frame, composition, tools or delegation.

Caller-compile edits (out of Source-files scope): None.
Gate: `cd backend && .venv/Scripts/python -c "import app.main"` — OK. `tests/routes/test_chats.py` + `tests/services/test_chat_turn.py` — 44 passed against the new required-nullable fields (both DTOs are constructed only via the two mappers).

### Step 003 — frozen interface (2026-09-20)

Service functions (bodies `raise NotImplementedError`; the coder fills them, signatures frozen; positioned after step 002's `finish_side_chat`, before `list_model_options`):
- `backend/app/services/chats.py` — `async def inject_side_chat(access: authz.BookAccess, chat_id: str, side_chat_id: str) -> ChatDetailResponse` — new. Docstring fixes the contract: resolve via `_resolve_owned_chat` (→ `chat_not_found` 404), parse via `_parse_side_chat_id` (non-numeric → `side_chat_not_found` 404), existence checked **before** mutating (`chat.active_side_chat_id == sid` or `chat_messages.side_chat_exists(chat.id, sid)`, else `side_chat_not_found`), then `chat_messages.clear_side_chat(chat.id, sid)`, clear the pointer **only if** it equalled `sid`, `chats.update(chat)` **always** (so `modified_at` bumps for a finished side chat too), return the same shape `get_chat` builds — all rows, position order, same mappers (call the same mapping, not a second implementation).
- `backend/app/services/chats.py` — `async def delete_side_chat(access: authz.BookAccess, chat_id: str, side_chat_id: str) -> None` — new. Same resolution / parse / pre-mutation existence check; then `chat_messages.delete_by_side_chat(chat.id, sid)` (the chat family's first hard delete — sanction note is the `db/chat_messages.py` module docstring, D-D), pointer cleared only if it equalled `sid`, `chats.update(chat)` always. Writes `chat_messages` rows and the `chats` pointer only; **no renumbering** of surviving positions. Returns nothing.
- Call convention: positional `(access, chat_id, side_chat_id)`; wire ids are `str`, parsed inside the service. A `0` return from `clear_side_chat` / `delete_by_side_chat` is **not** a 404 signal (active side chat with zero rows, DoD-10).
- No new `ChatErrorReason` member, no `_CHAT_ERROR_STATUS` change, no DTO change — step 002's taxonomy covers both routes (`side_chat_not_found` only).

Route handlers (HTTP-only glue, written whole; registered after step 002's `finish_side_chat` handler, i.e. after the static `model-options` route):
- `backend/app/routes/chats.py` — `@router.post("/{book_id}/chats/{chat_id}/side-chats/{side_chat_id}/inject")` `async def inject_side_chat(chat_id: str, side_chat_id: str, access: authz.BookAccess = Depends(authz.book_access)) -> ChatDetailResponse` — new (200); body = `try: return await chats_service.inject_side_chat(access, chat_id, side_chat_id)` + the standard `BookAuthorizationError → _map_authz_error` / `ChatError → _map_chat_error` pair. No request body.
- `backend/app/routes/chats.py` — `@router.delete("/{book_id}/chats/{chat_id}/side-chats/{side_chat_id}", status_code=status.HTTP_204_NO_CONTENT)` `async def delete_side_chat(chat_id: str, side_chat_id: str, access: authz.BookAccess = Depends(authz.book_access)) -> None` — new (204, **no body**; the `routes/chapters.py::delete_chapter` precedent); body = `await chats_service.delete_side_chat(access, chat_id, side_chat_id)` (return value unused) + the same two `except` arms. No request body.
- Wire paths: `POST /api/books/{book_id}/chats/{chat_id}/side-chats/{side_chat_id}/inject` (200 `ChatDetailResponse`) and `DELETE /api/books/{book_id}/chats/{chat_id}/side-chats/{side_chat_id}` (204, `response_model=None`). Verified registered via `router.routes` with those methods / status codes.

Caller-compile edits (out of Source-files scope): None. Both service functions and both handlers are new; no existing symbol changed shape.
Gate: `cd backend && .venv/Scripts/python -c "import app.main"` — OK. `tests/routes/test_chats.py` + `tests/services/test_chat_turn.py` still pass.

### Step 004 — frozen interface (2026-09-20)

Wire types (declarative, added whole; both **required-nullable**, never `?:` — the `llm_server_id` convention):
- `frontend/src/types/chats.d.ts` — `ChatResponse.active_side_chat_id: string | null` — new (appended after `modified_at`)
- `frontend/src/types/chats.d.ts` — `ChatMessageResponse.side_chat_id: string | null` — new (placed after `created_at`, before `tool_trace`)

Api functions (bodies `throw new Error("not implemented")`; the coder fills the `request<T>` calls — `titleChat` is the POST-no-body shape, `llmServers.ts::deleteServer` the DELETE shape; placed after `titleChat`, before `TurnStreamHandlers`; `streamChatTurn` untouched):
- `frontend/src/api/chats.ts` — `export async function startSideChat(bookId: string, chatId: string, signal?: AbortSignal): Promise<ChatResponse>` — new (`POST /api/books/{bookId}/chats/{chatId}/side-chats`)
- `frontend/src/api/chats.ts` — `export async function finishSideChat(bookId: string, chatId: string, sideChatId: string, signal?: AbortSignal): Promise<ChatResponse>` — new (`POST …/side-chats/{sideChatId}/finish`)
- `frontend/src/api/chats.ts` — `export async function injectSideChat(bookId: string, chatId: string, sideChatId: string, signal?: AbortSignal): Promise<ChatDetailResponse>` — new (`POST …/side-chats/{sideChatId}/inject`)
- `frontend/src/api/chats.ts` — `export async function deleteSideChat(bookId: string, chatId: string, sideChatId: string, signal?: AbortSignal): Promise<void>` — new (`DELETE …/side-chats/{sideChatId}`, 204)
- The module's full export list is now `listChats`, `createChat`, `updateChat`, `getChat`, `listModelOptions`, `titleChat`, `startSideChat`, `finishSideChat`, `injectSideChat`, `deleteSideChat`, `TurnStreamHandlers` (type), `streamChatTurn` — a spec's `vi.mock("../../src/api/chats", …)` factory must list every function.

Rendered-message shape (type change):
- `frontend/src/work/components/chat/chatPaneState.ts` — `RenderedMessage.sideChatId: string | null` — new field on the existing exported interface (appended after `toolTrace`). `renderedMessages` still compiles: both object literals (the persisted map and the streaming placeholder) carry `sideChatId: null` with a `// Skeleton (027 step 004)` comment — **placeholders, not the mapping**; the coder replaces them with `m.side_chat_id` and `this.activeSideChatId` respectively.

Transcript item union (new exported types, declared right after `RenderedMessage`; the `kind` literals and field names are the contract step 006 binds to):
- `frontend/src/work/components/chat/chatPaneState.ts` — `export type RenderedTranscriptMessageItem = { kind: "message"; message: RenderedMessage }` — new
- `frontend/src/work/components/chat/chatPaneState.ts` — `export type RenderedTranscriptSideChatItem = { kind: "sideChat"; sideChatId: string; messages: RenderedMessage[]; active: boolean; expanded: boolean }` — new
- `frontend/src/work/components/chat/chatPaneState.ts` — `export type RenderedTranscriptItem = RenderedTranscriptMessageItem | RenderedTranscriptSideChatItem` — new

`ChatPaneState` members:
- `frontend/src/work/components/chat/chatPaneState.ts` — `expandedSideChats: Record<string, boolean> = {}` — new ordinary observable field (declared after `expandedToolCallRows`; **not** in the `makeAutoObservable` exclusion map, which is unchanged)
- `frontend/src/work/components/chat/chatPaneState.ts` — `get activeSideChatId(): string | null` — new computed (declared after `activeChat`); body throws
- `frontend/src/work/components/chat/chatPaneState.ts` — `get renderedTranscript(): RenderedTranscriptItem[]` — new computed (declared after `renderedMessages`); body throws
- Construction is unaffected: MobX computeds are lazy, so `new ChatPaneState()` and every existing computed (`renderedMessages` included) still work; only reading the two new getters throws.

External effect function (body throws; declared right after `toggleToolCallRow`):
- `frontend/src/work/components/chat/chatPaneState.ts` — `export function toggleSideChatGroup(state: ChatPaneState, sideChatId: string): void` — new. Positional `(state, sideChatId)`.

Source-file compile consequences inside scope (recorded so the coder knows they are placeholders): the two optimistic `ChatMessageResponse` literals in `sendChatTurn` and the close-turn path gained `side_chat_id: null` with a `// Skeleton (027 step 004)` comment — the coder decides the optimistic row's stamp (step 004/005 territory), the skeleton did not.

Caller-compile edits (out of Source-files scope) — **test fixtures only**, each a single added line `active_side_chat_id: null,` (after `modified_at`) or `side_chat_id: null,` (after `created_at`); no assertion changed:
- `frontend/tests/work/canvasWiring.test.tsx` — `makeChat` +`active_side_chat_id`
- `frontend/tests/work/ChapterPageCanvas.test.tsx` — `makeChat` +`active_side_chat_id`
- `frontend/tests/work/ChapterPageClose.test.tsx` — `makeChat` +`active_side_chat_id`
- `frontend/tests/work/ChatConversation.test.tsx` — `makeChat` +`active_side_chat_id`; `makeMessage` +`side_chat_id`
- `frontend/tests/work/ChatModelPicker.test.tsx` — `makeChat` defaults +`active_side_chat_id`
- `frontend/tests/work/ChatPane.test.tsx` — `makeChat` defaults +`active_side_chat_id`
- `frontend/tests/work/chatPaneSettings.test.ts` — `makeChat` defaults +`active_side_chat_id`
- `frontend/tests/work/ChatsListPage.test.tsx` — `makeChat` defaults +`active_side_chat_id`
- `frontend/tests/work/chatsNavigatorEntry.test.tsx` — `makeChat` +`active_side_chat_id`
- `frontend/tests/work/chatStreaming.test.ts` — `makeChat` +`active_side_chat_id`; `makeMessage` +`side_chat_id`
- `frontend/tests/work/Composer.test.tsx` — `CHAT` literal +`active_side_chat_id`
- `frontend/tests/work/composerResize.test.tsx` — `CHAT` literal +`active_side_chat_id`
- `frontend/tests/work/subjectRoutes.test.tsx` — inline `listChats` fixture +`active_side_chat_id`
- `frontend/tests/work/transcriptAutoscroll.test.tsx` — `CHAT` literal +`active_side_chat_id`; `makeMessage` +`side_chat_id`
- `frontend/tests/work/WorkspaceShell.test.tsx` — `makeChat` +`active_side_chat_id`
- No `src/` file outside the three Source files needed an edit (`src/admin/**` `llm_server_id` hits are sub-agent DTOs, not `ChatResponse`).

Gate: `cd frontend && npm run build` — OK (tsc + vite). `cd frontend && npm run test:types` — OK. `npm test` not run (skeleton runs before the tests exist).

### Step 005 — frozen interface (2026-09-20)

`ChatPaneState` observable fields (declarative, added whole; ordinary observables — **not** in the `makeAutoObservable` exclusion map, which is unchanged; declared after `expandedSideChats` under a `// --- Side-chat actions (027 step 005) ---` divider):
- `frontend/src/work/components/chat/chatPaneState.ts` — `sideChatActionStatus: "idle" | "busy" | "error" = "idle"` — new (the action trio's status; **no `data` member** by design — results land in `chats` / `messages`)
- `frontend/src/work/components/chat/chatPaneState.ts` — `sideChatActionError: string | null = null` — new
- `frontend/src/work/components/chat/chatPaneState.ts` — `sideChatDeleteConfirm: string | null = null` — new (the side-chat id awaiting confirmation, or `null`)

`ChatPaneState` computeds (bodies `throw new Error("not implemented")`; declared right after `activeSideChatId`; MobX computeds are lazy, so construction and every existing computed still work — only reading these three throws):
- `frontend/src/work/components/chat/chatPaneState.ts` — `get sideChatActionsEnabled(): boolean` — new. Contract: `false` when `activeChat === null`, while `turnStatus === "streaming"`, while `closeTurnActive !== null`, or while `sideChatActionStatus === "busy"`; `true` otherwise (D1). Phrased "is a close active at all", never a book-id comparison (no `bookId` on the class).
- `frontend/src/work/components/chat/chatPaneState.ts` — `get canStartSideChat(): boolean` — new. Contract: `sideChatActionsEnabled && activeSideChatId === null`.
- `frontend/src/work/components/chat/chatPaneState.ts` — `get canFinishSideChat(): boolean` — new. Contract: `sideChatActionsEnabled && activeSideChatId !== null`.

External effect functions (bodies `throw new Error("not implemented")`; declared right after `toggleSideChatGroup`, before `turnStreamHandlers`; positional `(state, bookId[, sideChatId][, signal])`; parameter names are part of the contract):
- `frontend/src/work/components/chat/chatPaneState.ts` — `export async function startSideChat(state: ChatPaneState, bookId: string, signal?: AbortSignal): Promise<void>` — new. Guards **inside** on `canStartSideChat` and `activeChatId !== null` (returns, no api call); `busy` → `chatsApi.startSideChat(bookId, activeChatId, signal)` → replace the matching `state.chats` entry by id with the returned `ChatResponse` (whole object) → `idle`; `ApiError` → `error` + message, `chats` / `messages` untouched; anything else rethrows.
- `frontend/src/work/components/chat/chatPaneState.ts` — `export async function finishSideChat(state: ChatPaneState, bookId: string, signal?: AbortSignal): Promise<void>` — new. Guards inside on `canFinishSideChat`; calls `chatsApi.finishSideChat(bookId, activeChatId, activeSideChatId, signal)` with the **current** `activeSideChatId`; success patches `state.chats` with the returned chat, **`state.messages` untouched**; same `ApiError` / rethrow rule.
- `frontend/src/work/components/chat/chatPaneState.ts` — `export async function injectSideChat(state: ChatPaneState, bookId: string, sideChatId: string, signal?: AbortSignal): Promise<void>` — new. Guards inside on `sideChatActionsEnabled` and an active chat id; calls `chatsApi.injectSideChat(bookId, activeChatId, sideChatId, signal)`; success swaps `state.messages` **whole** with the response's `messages` and patches `state.chats` with the response's `chat`; same error rule.
- `frontend/src/work/components/chat/chatPaneState.ts` — `export async function deleteSideChat(state: ChatPaneState, bookId: string, sideChatId: string, signal?: AbortSignal): Promise<void>` — new. Guards inside on `sideChatActionsEnabled` and an active chat id; calls `chatsApi.deleteSideChat(bookId, activeChatId, sideChatId, signal)` (no body), then reloads via the existing `chatsApi.getChat(bookId, activeChatId, signal)` (the `finishTurn` reload idiom) and swaps `state.messages` whole + patches `state.chats` from the reload; **clears `sideChatDeleteConfirm` to `null` on success and on error**; same `ApiError` / rethrow rule.
- `frontend/src/work/components/chat/chatPaneState.ts` — `export function requestDeleteSideChat(state: ChatPaneState, sideChatId: string): void` — new. Sets `sideChatDeleteConfirm = sideChatId` inside `runInAction`; calls no api.
- `frontend/src/work/components/chat/chatPaneState.ts` — `export function dismissDeleteSideChat(state: ChatPaneState): void` — new. Sets `sideChatDeleteConfirm = null` inside `runInAction`; calls no api; `messages` / `chats` unchanged.
- Name-clash check: the module imports the api as a namespace (`import * as chatsApi from "../../../api/chats"`), so the four state functions share their names with step 004's api functions without collision; inside the module the api is always reached as `chatsApi.<name>`. Steps 006/007 bind to these module exports.
- A spec's `vi.mock("../../src/api/chats", …)` factory must still list every api export (step 004's list) including `getChat`, which `deleteSideChat` calls.

Caller-compile edits (out of Source-files scope): None. Every symbol is new; no existing signature changed shape.
Gate: `cd frontend && npm run build` — OK (tsc + vite). `cd frontend && npm run test:types` — OK. `npm test` not run (skeleton runs before the tests exist).

### Step 006 — frozen interface (2026-09-20)

`MessageRow` (new file; body `throw new Error("not implemented")` — a pure extraction, so the coder moves the JSX rather than writing new behaviour):
- `frontend/src/work/components/chat/MessageRow.tsx` — `export interface MessageRowProps { state: ChatPaneState; message: RenderedMessage }` — new
- `frontend/src/work/components/chat/MessageRow.tsx` — `export const MessageRow = observer(function MessageRow(props: MessageRowProps) { … })` — new. Contract (docstring): renders exactly the JSX of today's `MessageList.tsx:81-154` per-message map body — the `user` branch as `Box data-role="user"` (flex, `justifyContent: "flex-end"`) wrapping the filled `Paper` bubble (`maxWidth: "70%"`, theme `filled` / `contrast` tokens, `pre-wrap` `Text`); the `assistant` branch as `Stack data-role="assistant"` with `ThinkingBlock` (only when `message.reasoning` is non-null and non-empty), `ToolCallTrace` (always; `rows={message.toolTrace}`, `expanded={state.expandedToolCallRows}`, `rowKeyPrefix={message.key}`, `onToggle={(rowKey) => toggleToolCallRow(state, rowKey)}`), and `Box className="chat-markdown" fz="sm"` around `<Markdown>`. Reasoning expansion is the existing lookup: `message.streaming ? state.liveThinkingExpanded : (state.expandedReasoning[message.key] ?? false)`, toggle writes the same slot back. **The `key` prop is the parent's** — `MessageRow` does not set one on its root. Imports the coder will need: `Box`, `Paper`, `Stack`, `Text` from `@mantine/core`, `Markdown` from `react-markdown`, `ThinkingBlock`, `ToolCallTrace`, `toggleToolCallRow`. No `useEffect`, no local state.

`SideChatGroup` (new file; body `throw new Error("not implemented")`):
- `frontend/src/work/components/chat/SideChatGroup.tsx` — `export interface SideChatGroupProps { state: ChatPaneState; bookId: string | undefined; group: RenderedTranscriptSideChatItem }` — new (`bookId` is **required-but-undefinable**, not `?:` — the caller always passes it, possibly `undefined`)
- `frontend/src/work/components/chat/SideChatGroup.tsx` — `export const SideChatGroup = observer(function SideChatGroup(props: SideChatGroupProps) { … })` — new. Contract (docstring; every name is a test handle, D-F):
  - container: bordered `Paper` / `Box` with `role="group"` and `aria-label="Side chat"` for BOTH active and finished groups;
  - header `Group`: label `Text` reading `Side chat` when `group.active`, `Side chat · N messages` (N = `group.messages.length`, the product-D7 placeholder) when finished;
  - expand / collapse control (`ActionIcon` or `UnstyledButton`) rendered ONLY when `!group.active`; ONE control whose `aria-label` swaps — `Expand side chat` while `!group.expanded`, `Collapse side chat` while `group.expanded`; click → `toggleSideChatGroup(state, group.sideChatId)`;
  - two `ActionIcon`s `aria-label="Inject side chat"` and `aria-label="Delete side chat"`, both `disabled` when `!state.sideChatActionsEnabled || bookId === undefined`; Inject → `void injectSideChat(state, bookId, group.sideChatId)`; Delete → `requestDeleteSideChat(state, group.sideChatId)` (no api call; the confirmation `Modal` is step 007's);
  - body: `group.messages.map((message) => <MessageRow key={message.key} state={state} message={message} />)` rendered ONLY when `group.expanded`; collapsed = header only. Conditional rendering — **no Mantine `Collapse`, no `Accordion`** (inventory rule). Icons: any `@tabler/icons-react` icon (e.g. `IconChevronDown` / `IconChevronRight` as `ThinkingBlock` uses; new icon imports are fine — the inventory rule is Mantine-only).
  - No `useEffect`, no local state, no hooks; expansion lives in `state.expandedSideChats` via `toggleSideChatGroup`.

`MessageList` (props change only; **render body untouched by the skeleton**):
- `frontend/src/work/components/chat/MessageList.tsx` — `export interface MessageListProps { state: ChatPaneState; bookId?: string }` — changed (was `{ state: ChatPaneState }`). `bookId` is optional **as a forward-only split only** (docstring says so): `ChatPane.tsx` is step 007's source file, so step 007 changes `ChatPane.tsx:274` to `<MessageList state={state} bookId={bookId} />`; until then the group's Inject / Delete render disabled.
- `frontend/src/work/components/chat/MessageList.tsx` — `export const MessageList = observer(function MessageList({ state }: MessageListProps) { … })` — signature unchanged. **The coder's edit**, recorded here so it is not read as skeleton-frozen rendering: destructure `bookId` too, and replace the `state.renderedMessages.map((msg) => { … })` block at :81-154 (inside the existing `<Stack gap="sm" p="xs">`) with `state.renderedTranscript.map((item) => item.kind === "message" ? <MessageRow key={item.message.key} state={state} message={item.message} /> : <SideChatGroup key={item.sideChatId} state={state} bookId={bookId} group={item} />)`. Everything else — `ScrollArea type="auto"`, `viewportRef={(el) => attachTranscriptViewport(state, el)}`, `onScrollPositionChange={() => noteTranscriptScroll(state)}`, the `flex: 1` / `minHeight: 0` style, the outer `Stack`, and the loading / empty behaviour (there is none beyond an empty map today) — stays byte-identical. After the move the file's `Box`, `Paper`, `Text`, `Markdown`, `ThinkingBlock`, `ToolCallTrace`, `toggleToolCallRow` imports become unused and go; `ScrollArea`, `Stack`, `attachTranscriptViewport`, `noteTranscriptScroll` stay.
- The existing rendering was left in place deliberately so the tree still builds and the existing pane specs keep passing until the coder switches the map; the `state.renderedTranscript` getter is still step 004's throwing stub at this point.

Binding summary for the test-coder: `MessageRow` and `SideChatGroup` are default-less named exports; `SideChatGroup` reads `state.sideChatActionsEnabled` (step 005 computed) and calls `toggleSideChatGroup` (004), `injectSideChat` / `requestDeleteSideChat` (005) — all from `./chatPaneState`; `MessageList` reads `state.renderedTranscript` (004). A spec's `vi.mock("../../src/api/chats", …)` factory must list every api export (step 004's list, `getChat` included).

Caller-compile edits (out of Source-files scope): None. `bookId?` is optional, so `ChatPane.tsx:274` (`<MessageList state={state} />`) compiles unchanged; no test file needed an edit.
Gate: `cd frontend && npm run build` — OK (tsc + vite). `cd frontend && npm run test:types` — OK. `npm test` not run (skeleton runs before the tests exist).

### Step 007 — frozen interface (2026-09-20)

**No signature changes; no new exported symbols; no stubs written.** Both Source files compile as they stand and their JSX is untouched by the skeleton. This entry freezes the *UI contract* — accessible names, exact strings, and which step-005/006 symbol each control binds to — which is the surface the test-coder queries and the coder fills.

Props (unchanged; quoted verbatim as the frozen surface):
- `frontend/src/work/components/chat/ChatPane.tsx` — `export interface ChatPaneProps { bookId: string; state: ChatPaneState }` — unchanged
- `frontend/src/work/components/chat/ChatPane.tsx` — `export const ChatPane = observer(function ChatPane({ bookId, state }: ChatPaneProps) { … })` — unchanged
- `frontend/src/work/components/chat/Composer.tsx` — `export interface ComposerProps { state: ChatPaneState; onSend: () => void; onStop: () => void; onRetry: () => void }` — unchanged
- `frontend/src/work/components/chat/Composer.tsx` — `export const Composer = observer(function Composer({ state, onSend, onStop, onRetry }: ComposerProps) { … })` — unchanged

`ChatPane` — the Start / Finish header slot (coder implements; test-coder binds by role + name):
- **One** `ActionIcon` inserted in the header `Group gap={4} wrap="nowrap"` **immediately before** the existing `aria-label="New chat"` icon (`ChatPane.tsx:239-241`); it does **not** join the `openedPanel` discriminator (opens no popover). A `Tooltip` wrapper is allowed (in the Mantine inventory) but not required — today's `New chat` control is a bare `ActionIcon`, not a `Tooltip` + `ActionIcon` (the step file's "copying its Tooltip shape" is inaccurate; harvest B.5).
- When `state.activeSideChatId === null`: `aria-label="Start side chat"`, `disabled={!state.canStartSideChat}`, `onClick` → `void startSideChat(state, bookId)` (step 005's module export from `./chatPaneState`; `bookId` is the `ChatPaneProps` prop).
- When `state.activeSideChatId !== null`: `aria-label="Finish side chat"`, `disabled={!state.canFinishSideChat}`, `onClick` → `void finishSideChat(state, bookId)`.
- **Swap, never both**: one element whose `aria-label`, icon, `disabled` and handler all switch on `activeSideChatId === null`; at no time do both names exist in the accessibility tree. Icon choice is the coder's (any `@tabler/icons-react` icon).
- No signal is passed (the pane's existing effect-fn calls pass none); the `can…` computeds carry the D1 gating (streaming / close active / busy / no active chat) — the pane adds no gate of its own.

`ChatPane` — the delete confirmation:
- `@mantine/core` `Modal` (the `ChapterPage.tsx:376-400` precedent; `@mantine/modals` is not installed) with `opened={state.sideChatDeleteConfirm !== null}`, `onClose={() => dismissDeleteSideChat(state)}`, `title="Delete this side chat?"` (the title names the action; exact wording is the coder's, but it must contain "side chat" and must not be the bare word "Close" — Mantine's own dismiss control is named `Close`).
- Body text (one or two `Text`s) stating that the side chat's **messages are removed permanently** and that **anything saved during it — codex entries, chapter edits, memos — is kept**. Test-coder asserts on substrings (`/permanently/i`, `/kept/i`), not exact sentences.
- Two `Button`s with **exact** labels: `Keep it` → `dismissDeleteSideChat(state)`; `Delete side chat` → `void deleteSideChat(state, bookId, state.sideChatDeleteConfirm)` with the pending id **read at click time** (guard `!== null` inside the handler; the effect clears the slot itself on both outcomes). `Keep it` calls no api and leaves `messages` / `chats` untouched.
- Renders as `role="dialog"` (`ModalBaseContent` sets it); the dialog's accessible name is the title via `aria-labelledby`. `renderWithProviders` (`frontend/tests/support/render.tsx`) sets Mantine `env="test"`, which disables portals and transitions — the dialog renders **inline and synchronously**, so `screen.getByRole("dialog")` (or `findByRole`, as `ChapterPageStateControls.test.tsx:328` does) finds it in the RTL container; buttons are located by name inside it (`within(dialog).getByRole("button", { name: "Delete side chat" })`). When `sideChatDeleteConfirm === null` the `Modal` mounts nothing (`keepMounted` defaults to `false`), so `queryByRole("dialog")` is `null`.
- Name-clash note for the test-coder: `Delete side chat` is also the `aria-label` of `SideChatGroup`'s per-group Delete icon (step 006). Inside the dialog query with `within(dialog)`; outside it, the pane spec should not need the group icon at all (it seeds `sideChatDeleteConfirm` directly).

`ChatPane` — the action error banner:
- `{state.sideChatActionStatus === "error" && <Alert color="red">{state.sideChatActionError}</Alert>}` (placement: with the pane's other `Alert`s, after the header `Group`); absent when `"idle"` or `"busy"`. The pane's existing turn / load error surfaces are untouched.
- **Verified from `node_modules/@mantine/core` 7.17.8** (`esm/components/Alert/Alert.mjs:86`): `Alert` renders `role="alert"` on its root **by default** — `getByRole("alert")` works with no extra prop. Caveat: the pane's three existing `Alert`s (`serverErrors.model`, `serverErrors.form`, `chatsError`) and the composer's two (`composerReadOnlyReason`, `turnError` when `retryOffered`) also carry `role="alert"`; a spec must leave those at their defaults (null / not offered) so `queryByRole("alert")` resolves to at most the side-chat one, and should assert on the alert's text content (`toHaveTextContent(state.sideChatActionError)`). The `Alert`'s accessible **name** (its `title`) is deliberately **not** frozen — the test-coder must not query it by name.

`ChatPane` — the `MessageList` wiring:
- `ChatPane.tsx:274` becomes `<MessageList state={state} bookId={bookId} />` — the one-line binding of step 006's optional `MessageListProps.bookId?: string`; this is what makes the group's Inject / Delete icons enabled.

`Composer` — the side-chat hint:
- `{state.activeSideChatId !== null && <Text size="xs" c="dimmed">Replying in the side chat</Text>}` rendered **above the `Textarea`** (after the two existing `Alert`s, before `<Textarea …>`) — exact text `Replying in the side chat`; nothing rendered otherwise. Sizing / colour props are the coder's; the string is frozen. `Text` joins the file's `@mantine/core` import.
- **No gate change**: `disabled={streaming || closeReadOnly}` on the `Textarea`, `disabled={!state.canSend || closeReadOnly}` on Send, the keyboard path's `if (!state.canSend || closeReadOnly) return;` and the read-only `Alert` at `:73-77` are byte-identical before and after. The `Message the assistant` textbox and the `Send` control stay present and enabled whether or not a side chat is active (DoD-10). No `Badge`, no second gate.

Binding summary for the test-coder: `ChatPane` reads `state.activeSideChatId` (004), `state.canStartSideChat` / `state.canFinishSideChat` / `state.sideChatActionStatus` / `state.sideChatActionError` / `state.sideChatDeleteConfirm` (005), and calls `startSideChat` / `finishSideChat` / `deleteSideChat` / `dismissDeleteSideChat` (005) from `./chatPaneState`; `Composer` reads only `state.activeSideChatId`. A spec makes a side chat active by setting the active chat's `active_side_chat_id` in `state.chats[]` (the computed reads it). Any spec importing the chats api must list every export in its `vi.mock("../../src/api/chats", …)` factory (step 004's list, `getChat` included — `deleteSideChat` reloads through it).

Caller-compile edits (out of Source-files scope): None. No signature changed; no file outside the two Source files was touched.
Gate: `cd frontend && npm run build` — OK (tsc + vite). `cd frontend && npm run test:types` — OK. `npm test` not run (skeleton runs before the tests exist).

## Tests

### Step 001 — tests (2026-09-20)
- `backend/tests/db/test_chat_messages_side_chats.py` — covers DoD-1..DoD-8 — the two nullable columns round-trip via `chats.create` / `chat_messages.create` + `get_by_id`; `ADDITIVE_COLUMNS` membership; the four new `chat_messages.*` functions against seeded raw-int chat ids (main line, two side chats, a foreign chat carrying the same id)
  - `test_columns_default_to_none__DoD1`, `test_side_chat_id_round_trips_as_int__DoD1`, `test_active_side_chat_id_round_trips_as_int__DoD1`
  - `test_additive_columns_lists_both_side_chat_columns__DoD2`
  - `test_list_transcript_with_active_side_chat__DoD3`
  - `test_list_transcript_main_line_only__DoD4`, `test_list_transcript_empty_chat__DoD4`
  - `test_side_chat_exists_true_when_a_row_carries_it__DoD5`, `test_side_chat_exists_false_when_no_row_in_this_chat__DoD5`
  - `test_clear_side_chat_nulls_exactly_the_target_rows__DoD6`
  - `test_delete_by_side_chat_removes_exactly_the_target_rows__DoD7`, `test_delete_by_side_chat_next_position_follows_survivors__DoD7`
  - `test_clear_side_chat_returns_zero_when_nothing_matches__DoD8`, `test_delete_by_side_chat_returns_zero_when_nothing_matches__DoD8`
- `backend/tests/services/test_db_import_export_side_chats.py` — covers DoD-9, DoD-10 — direct `_chat_to_dict` / `_dict_to_chat` / `_chat_message_to_dict` / `_dict_to_chat_message` calls (no db); wire form `str | None`, restored `int | None`; legacy dict with the key deleted restores `None` with the other fields intact
  - `test_chat_codec_emits_string_and_restores_int__DoD9`, `test_chat_codec_emits_null_and_restores_none__DoD9`, `test_message_codec_emits_string_and_restores_int__DoD9`, `test_message_codec_emits_null_and_restores_none__DoD9`
  - `test_legacy_chat_dict_without_key_restores_none__DoD10`, `test_legacy_message_dict_without_key_restores_none__DoD10`
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓, DoD-10 ✓ (no `[manual/live]` items in this step)
- Caller fix (out of the step's Test-files list, pre-existing pin stale against the frozen interface): `backend/tests/test_data_domain_chat.py` — `test_chat_and_message_field_sets_pinned__DoD10` — `CHAT_FIELDS` gains `active_side_chat_id`, `CHAT_MESSAGE_FIELDS` gains `side_chat_id` (each tagged `# feature 027 — side-chat columns`); nothing else in that file changed

### Step 002 — tests (2026-09-20)
- `backend/tests/routes/test_chat_side_chats.py` — covers DoD-1..DoD-7 — HTTP through `http_client` with real JWTs (helpers copied from `tests/routes/test_chats.py`); `POST …/side-chats` (201), `POST …/side-chats/{sid}/finish` (200), `GET …/chats/{chat_id}` detail; a "finished" side chat is seeded as rows with `side_chat_id=<int>` and a null pointer, an "active" one via the POST
  - `test_detail_null_side_chat_fields_without_side_chat__DoD1`, `test_detail_shows_seeded_row_side_chat_id_as_decimal_string__DoD1`
  - `test_start_side_chat_sets_pointer_and_detail_agrees__DoD2`
  - `test_start_side_chat_on_empty_chat_is_allowed__DoD3`
  - `test_second_start_while_active_is_409_pointer_unchanged__DoD4`
  - `test_finish_active_side_chat_clears_pointer_keeps_rows__DoD5`, `test_finish_active_side_chat_with_zero_rows_clears_pointer__DoD5`
  - `test_finish_finished_side_chat_is_409__DoD6`, `test_finish_unknown_side_chat_id_is_404__DoD6`, `test_finish_non_numeric_side_chat_id_is_404__DoD6`
  - `test_start_and_finish_on_other_authors_chat_are_404__DoD7` (co-author of the same book, not the chat owner), `test_start_and_finish_by_stranger_are_404__DoD7`
- `backend/tests/services/test_chat_turn_side_chats.py` — covers DoD-8..DoD-14 — `chat_turn.run_turn` with the fake client (`_FakeClient` / `_install_client` copied from `tests/services/test_chat_turn.py`); the pointer is set by mutating `context.chat.active_side_chat_id` and persisting via `chats.update`; rows read back unfiltered via `chat_messages.list_by_chat_ordered`; sentinel strings per transcript region (`MAIN-BEFORE-FACT`, `MAIN-AFTER-FACT`, `SIDE-A-FACT`, `SIDE-B-FACT`) asserted present/absent in `fake.call["messages"]` contents
  - `test_turn_inside_active_side_chat_stamps_both_rows__DoD8`, `test_turn_without_side_chat_leaves_both_rows_main_line__DoD8`
  - `test_side_chat_turn_sees_preceding_main_line__DoD9` — asserts `MAIN-BEFORE-FACT` present AND, as the red-gate companion (UC-115 step 1 / DoD-12), a finished side chat B seeded in the same scenario (`SIDE-B-FACT`, rows stamped `SID_B`, pointer `SID_A`) absent from `fake.call["messages"]`
  - `test_side_chat_turn_sees_its_own_earlier_messages__DoD10` — asserts `SIDE-A-FACT` and `main opener` present AND, as the red-gate companion (UC-115 step 1 / DoD-12), finished side chat B's `SIDE-B-FACT` (seeded before A's own exchange) absent
  - `test_main_line_turn_after_finish_excludes_side_chat__DoD11`
  - `test_side_chat_b_excludes_finished_side_chat_a__DoD12`
  - `test_retry_inside_active_side_chat_stamps_assistant_row__DoD13` (`prompt=None`)
  - `test_done_frame_message_carries_side_chat_id_string__DoD14`, `test_done_frame_message_side_chat_id_is_none_on_main_line__DoD14`
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓, DoD-10 ✓, DoD-11 ✓, DoD-12 ✓, DoD-13 ✓, DoD-14 ✓ (no `[manual/live]` items in this step)

### Step 003 — tests (2026-09-20)
- `backend/tests/routes/test_chat_side_chats_inject_delete.py` — covers DoD-1, 2, 4, 5, 6, 7, 9, 10 — HTTP through `http_client` with real JWTs (helpers copied from `tests/routes/test_chats.py` / `tests/routes/test_chat_side_chats.py`); `POST …/side-chats/{sid}/inject` (200 `ChatDetailResponse`), `DELETE …/side-chats/{sid}` (204, `resp.content == b""`), `GET …/chats/{chat_id}` detail read-back as `(content, position, side_chat_id)` snapshots; a finished side chat is seeded as rows with `side_chat_id=<int>` and a null pointer, an active one via `POST …/side-chats`; the codex entry for DoD-7 goes through `POST /api/books/{book_id}/codex` (`kind: location`) and `GET /api/books/{book_id}/codex/{entry_id}`
  - `test_inject_finished_side_chat_rows_become_main_line_in_place__DoD1`
  - `test_inject_active_side_chat_clears_pointer_and_rows__DoD2`
  - `test_inject_unknown_side_chat_id_is_404_and_changes_nothing__DoD4`, `test_inject_non_numeric_side_chat_id_is_404_and_changes_nothing__DoD4`, `test_inject_on_other_authors_chat_is_404_and_changes_nothing__DoD4` (co-author of the same book, not the chat owner; asserts `!= 403`)
  - `test_delete_finished_side_chat_removes_its_rows_keeps_positions__DoD5`
  - `test_delete_active_side_chat_clears_pointer_and_removes_rows__DoD6`
  - `test_codex_entry_created_during_side_chat_survives_delete__DoD7`
  - `test_delete_unknown_side_chat_id_is_404_and_deletes_nothing__DoD9`, `test_delete_non_numeric_side_chat_id_is_404_and_deletes_nothing__DoD9`, `test_delete_on_other_authors_chat_is_404_and_deletes_nothing__DoD9`
  - `test_inject_active_side_chat_with_zero_rows_clears_pointer__DoD10`, `test_delete_active_side_chat_with_zero_rows_clears_pointer__DoD10`
- `backend/tests/services/test_chat_turn_side_chats_inject.py` — covers DoD-3, 8, 11 — `chats_service.inject_side_chat` / `delete_side_chat` called directly with a `BookAccess` built for the chat's own author (`_access` copied from `tests/services/test_assistant_runtime.py`), then `chat_turn.run_turn` with the fake client (`_FakeClient` / `_install_client` copied from `tests/services/test_chat_turn.py`); the turn runs on a `TurnContext` rebuilt from `chats.get_by_id` so it captures the persisted pointer; sentinels (`MAIN-BEFORE-FACT`, `MAIN-AFTER-FACT`, `SIDE-A-FACT`, `SIDE-A-REPLY-FACT`, `SIDE-B-FACT`) asserted present/absent in `fake.call["messages"]`; rows read back unfiltered via `chat_messages.list_by_chat_ordered`
  - `test_main_line_turn_after_inject_sees_injected_messages__DoD3` (finished side chat), `test_main_line_turn_after_injecting_active_side_chat_sees_it__DoD3` (active side chat; a separate finished side chat stays excluded)
  - `test_turn_after_deleting_finished_side_chat_sees_nothing_of_it__DoD8`, `test_turn_after_deleting_active_side_chat_sees_nothing_of_it__DoD8`
  - `test_turn_after_delete_appends_at_max_plus_one_no_renumbering__DoD11` (positions 0..4, side chat at 1..3 deleted → survivors 0, 4; new rows at 5, 6; ascending)
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓, DoD-10 ✓, DoD-11 ✓ (no `[manual/live]` items in this step)

### Step 004 — tests (2026-09-20)
- `frontend/tests/work/sideChatApi.test.ts` — covers DoD-1 — mocks `../../src/api/client`'s `request` via `importOriginal` (real `ApiError` kept), does **not** mock `api/chats`; each of the four functions asserted to make exactly one `request(url, init)` call with the D-D method + URL (`POST …/side-chats`, `POST …/side-chats/{sid}/finish`, `POST …/side-chats/{sid}/inject`, `DELETE …/side-chats/{sid}`), no `body`, the forwarded `signal`, and to resolve with the mocked value (`undefined` for delete)
  - `DoD-1: startSideChat POSTs …/chats/{chatId}/side-chats once …`, `DoD-1: finishSideChat POSTs …/finish once …`, `DoD-1: injectSideChat POSTs …/inject once …`, `DoD-1: deleteSideChat DELETEs …/side-chats/{sideChatId} once … resolves undefined`
  - `DoD-1: every function works without a signal and interpolates the ids it was given`, `DoD-1: a refusal from the wrapper propagates as the very same ApiError, status intact`
- `frontend/tests/work/sideChatGrouping.test.ts` — covers DoD-2..DoD-10 — state-only (no rendering); mocks `../../src/api/chats` with the full 11-function factory (four side-chat functions included); seeds `chats` / `activeChatId` / `messages` / `messagesStatus` / `turnStatus` via `runInAction`, reads `renderedMessages`, `renderedTranscript`, `activeSideChatId`, `expandedSideChats`, calls `toggleSideChatGroup(state, id)`; asserts on `kind`, `sideChatId`, `messages.length`, per-message `key` order, `active`, `expanded`, `streaming`
  - `DoD-2: a main-line row renders sideChatId null and a side-chat row renders the row's id`
  - `DoD-3: [main, main, A, A, main, B, B, B] yields message, message, sideChat(A,2), message, sideChat(B,3) …`, `DoD-3: a group carries the SAME rendered entries renderedMessages yields (value-equal, every per-message derivation intact — not a reduced form)` — reworked 2026-09-21 after verify run 1: deep value equality (`toEqual`) against a separately-read `renderedMessages`, plus the per-message fields spelled out (key, content, role, streaming, `sideChatId`); the earlier reference-identity (`toBe`) form asserted a property DoD-3 does not state and that an unobserved MobX computed cannot provide
  - `DoD-4: [A, A, B, B] produces TWO sideChat items, not one`, `DoD-4: [main, A, A, B, B, main] keeps the two groups apart …`
  - `DoD-5: … active: true and expanded: true when expandedSideChats has no entry`, `DoD-5: … stays expanded: true even when expandedSideChats[id] is explicitly false`, `DoD-5: with a finished group and the active group in the same transcript, only the active one is active`
  - `DoD-6: … active: false and expanded: false with no toggle`, `DoD-6: a finished group stays collapsed by default while a different side chat is active`
  - `DoD-7: one call expands the group, a second call collapses it again`, `DoD-7: toggling one finished group leaves the other groups unaffected`, `DoD-7: the toggle writes a new expandedSideChats object …`
  - `DoD-8: … the in-flight bubble is the LAST message inside the active group and there is no trailing message item`, `DoD-8: … side chat active that has no rows yet, the in-flight bubble opens the active group on its own`, `DoD-8: … NO side chat active, the in-flight bubble is a trailing message item`, `DoD-8: … a finished group last, the bubble is NOT appended to that finished group`
  - `DoD-9: activeSideChatId is the active chat's active_side_chat_id`, `DoD-9: … null when the active chat's field is null`, `DoD-9: … null when there is no active chat …`, `DoD-9: … reads the ACTIVE chat's field, not another chat's`
  - `DoD-10: a list with no side-chat rows yields only message items, one per row, in order`, `DoD-10: an empty message list yields an empty transcript`
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓, DoD-10 ✓ (no `[manual/live]` items in this step)

### Step 005 — tests (2026-09-20)
- `frontend/tests/work/sideChatActions.test.ts` — covers DoD-1..DoD-11 — state-only (no rendering); mocks `../../src/api/chats` with the full 11-function factory and drives it via `vi.mocked(chatsApi.*)` (`vi.resetAllMocks()` in `beforeEach`); `ApiError` real from `../../src/api/client`; seeds `chats` / `activeChatId` / `messages` / `messagesStatus` / `turnStatus` (and `closeTurnActive` / `sideChatActionStatus` directly) via `runInAction`; asserts on `sideChatActionStatus`, `sideChatActionError`, `sideChatDeleteConfirm`, the three computeds, `activeSideChatId`, `renderedTranscript`, `state.messages` / `state.chats` (reference identity for "untouched", `.slice()` content for "equals"), and the mocks' positional call args (`bookId`, active chat id, side-chat id, forwarded `signal`)
  - `DoD-1: canStartSideChat is true with an active chat whose active_side_chat_id is null, an idle turn, no close turn and status idle`, `DoD-1: canStartSideChat is false when the active chat's active_side_chat_id is set`
  - `DoD-2: canStartSideChat is false while turnStatus === 'streaming'`
  - `DoD-3: canFinishSideChat is true when … active_side_chat_id is set and actions are enabled`, `DoD-3: canFinishSideChat is false when no side chat is active`, `DoD-3: canFinishSideChat is false while streaming even though a side chat is active`
  - `DoD-4: sideChatActionsEnabled is false while closeTurnActive !== null`, `DoD-4: … false while sideChatActionStatus === 'busy'`, `DoD-4: … false when there is no active chat`, `DoD-4: … false while streaming`, `DoD-4: … true with an active chat, an idle turn, no close turn and status idle — and stays true after an error`
  - `DoD-5: startSideChat calls the start api once with the book id and the active chat id; afterwards activeSideChatId is the returned chat's … and the status is idle`, `DoD-5: startSideChat forwards the signal …`, `DoD-5: startSideChat leaves the message list alone`, `DoD-5: startSideChat calls no api when a side chat is already active`
  - `DoD-6: finishSideChat calls the finish api with the current activeSideChatId; afterwards activeSideChatId is null, messages are the same content, and the former group renders active: false, expanded: false`, `DoD-6: finishSideChat forwards the signal …`, `DoD-6: finishSideChat calls no api when no side chat is active`
  - `DoD-7: injectSideChat calls the inject api with the given id; afterwards messages equal the response's … and renderedTranscript shows them as message items in order`, `DoD-7: injecting the ACTIVE side chat also clears activeSideChatId from the response's chat`, `DoD-7: injectSideChat forwards the signal …`
  - `DoD-8: deleteSideChat calls the delete api once and then getChat once; afterwards messages equal the reload's, chats carries the reloaded chat, and sideChatDeleteConfirm is null`, `DoD-8: deleting the ACTIVE side chat leaves activeSideChatId null from the reloaded chat`, `DoD-8: deleteSideChat forwards the signal it was given to both the delete and the reload`
  - `DoD-9: requestDeleteSideChat sets sideChatDeleteConfirm to the given id and calls no api`, `DoD-9: dismissDeleteSideChat sets sideChatDeleteConfirm back to null, calls no api, and leaves messages and chats unchanged`, `DoD-9: a second request replaces the pending id rather than stacking`
  - `DoD-10: startSideChat on an ApiError …`, `DoD-10: finishSideChat on an ApiError …`, `DoD-10: injectSideChat on an ApiError …`, `DoD-10: deleteSideChat on an ApiError … no reload, and the confirmation slot is cleared` (each: status `'error'`, message equal, `messages` / `chats` reference-equal to before); `DoD-10: a non-ApiError rejection from startSideChat / finishSideChat / injectSideChat / deleteSideChat propagates` (four tests, `rejects.toThrow("boom")`)
  - `DoD-11: while startSideChat is in flight the status is 'busy', the three computeds are false, and a second call to any effect calls no api` (pending `new Promise(() => {})`), `DoD-11: while finishSideChat is in flight … a second finish calls no api`, `DoD-11: a seeded 'busy' status alone makes every effect a no-op at the api`
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓, DoD-10 ✓, DoD-11 ✓ (no `[manual/live]` items in this step)

### Step 006 — tests (2026-09-20)
- `frontend/tests/work/SideChatGroup.test.tsx` — covers DoD-2..DoD-6 — renders `<SideChatGroup state bookId group />` through `renderWithProviders`, the `group` prop taken from `state.renderedTranscript` (narrowed by the `kind === "sideChat"` guard); mocks `../../src/api/chats` with the full 11-function factory (`vi.resetAllMocks()` in `beforeEach`); seeds `chats` / `activeChatId` / `messages` / `messagesStatus` / `turnStatus` via `runInAction`; queries by role + accessible name (`group` "Side chat"; buttons `Expand side chat` / `Collapse side chat` / `Inject side chat` / `Delete side chat`) and by text (`Side chat`, `Side chat · N messages`, message contents); `within(group)` for inside assertions, `queryByText` for absence. DoD-4 renders via a test-land `observer` host that re-reads `renderedTranscript` each render (the component takes `group` as a plain prop, so a toggle yields a fresh item)
  - `DoD-2: an active group is a role=group named Side chat whose header reads 'Side chat' and whose messages are visible`, `DoD-2: an active group offers neither 'Expand side chat' nor 'Collapse side chat'`
  - `DoD-3: a finished two-message group shows 'Side chat · 2 messages', an 'Expand side chat' control, and none of its contents`, `DoD-3: N is the group's own message count — a three-message finished group reads 'Side chat · 3 messages'`
  - `DoD-4: clicking 'Expand side chat' reveals the messages and swaps the control to 'Collapse side chat'; clicking that hides them again`, `DoD-4: only ONE expand-or-collapse control exists at a time`
  - `DoD-5: a finished group with an idle turn renders 'Inject side chat' and 'Delete side chat', both enabled`, `DoD-5: an active group with an idle turn renders both controls enabled too`, `DoD-5: while turnStatus === 'streaming' both controls are present but disabled`, `DoD-5: with no book id … both controls render disabled` (006.context.md forward-only split)
  - `DoD-6: clicking 'Inject side chat' on an enabled group calls the inject api once with the book id, the chat id and that group's side-chat id` (`vi.mocked(chatsApi.injectSideChat).mockResolvedValue({ chat, messages: [] })`; first three positional args asserted `("bk-1", "c-1", "sc-A")`), `DoD-6: clicking 'Delete side chat' sets sideChatDeleteConfirm to that group's id and calls NO api` (all five mutating/reload mocks asserted not called; `state.messages` length unchanged)
- `frontend/tests/work/MessageListSideChats.test.tsx` — covers DoD-1, DoD-7, DoD-8, DoD-9 — renders `<MessageList state bookId="bk-1" />` through `renderWithProviders`; same api mock factory and seeding idiom; assertions by role + name, by text, `within(group)` / `group.contains(el)` for inside/outside, `container.querySelector('[data-role="user"|"assistant"]')` as the existing regression handle, ThinkingBlock control located exactly as `ChatConversation.test.tsx` does (`getByText(/thinking/i)` → `closest("button")`)
  - `DoD-1: [main, main, A, A, main] renders exactly one role=group named Side chat; both A messages are inside it, the three main-line messages are outside it` (A active, so expanded), `DoD-1: a finished run is also one group named Side chat; expanded via its control, its messages are inside it and the main line stays outside` (expanded through `state.expandedSideChats`)
  - `DoD-7: a transcript whose rows all carry side_chat_id null — as injected rows do — renders no group and no Inject / Delete control`, `DoD-7: main-line rows beside a real group are not inside any group and carry no controls of their own` (exactly one Inject / one Delete, both inside the group)
  - `DoD-8: the user's text is in a data-role=user box and the assistant's markdown in a data-role=assistant block`, `DoD-8: an assistant row with reasoning shows the ThinkingBlock control` (inside the assistant block), `DoD-8: a row without reasoning shows no ThinkingBlock control`
  - `DoD-9: while streaming with side chat A active, the streaming content is inside the Side chat group`, `DoD-9: … no A rows yet, the bubble alone opens the group and renders inside it`, `DoD-9: while streaming with NO side chat active, the bubble renders outside any group` (the contrast)
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓ (no `[manual/live]` items in this step)

### Step 007 — tests (2026-09-20)
- `frontend/tests/work/ChatPaneSideChat.test.tsx` — covers DoD-1..DoD-9 — renders `<ChatPane bookId="bk-1" state />` through `renderWithProviders`; mocks `../../src/api/chats` with the full 11-function factory (benign defaults in `beforeEach` for `listChats` / `listModelOptions` / `titleChat` / `streamChatTurn`); `primePane` seeds `chats` (one chat, `active_side_chat_id` the variable) / `chatsStatus: "ready"` / `activeChatId` / `modelOptions: []` + `modelOptionsStatus: "ready"` / two main-line `messages` / `messagesStatus: "ready"` / `turnStatus` via `runInAction`, so no group and no loader renders; `sideChatDeleteConfirm`, `sideChatActionStatus`, `sideChatActionError` seeded directly. Queries: header controls by `role="button"` + name (`Start side chat` / `Finish side chat`), the dialog by `findByRole("dialog")` with buttons `within(dialog)` (`Keep it` / `Delete side chat` — the latter is also step 006's group icon name), the error banner by TEXT only (`getByText` / `queryByText`, never role/name); `userEvent` clicks; `waitFor` on the mocks' positional call args
  - `DoD-1: with the active chat's active_side_chat_id null, a control named 'Start side chat' is present and no 'Finish side chat' control exists` (also exactly one Start control)
  - `DoD-2: with the active chat's active_side_chat_id set — as after a reload, no client memory — a control named 'Finish side chat' is present and no 'Start side chat' control exists` (localStorage empty)
  - `DoD-3: 'Start side chat' is disabled while turnStatus === 'streaming'`, `DoD-3: 'Start side chat' is enabled when the turn is idle`
  - `DoD-4: 'Finish side chat' is disabled while turnStatus === 'streaming'`, `DoD-4: 'Finish side chat' is enabled when the turn is idle`
  - `DoD-5: clicking 'Start side chat' calls the start api once with the book id and the active chat id, and the slot then shows what the server returned` (`("bk-1", "c-1")`; resolved chat carries `active_side_chat_id: "sc-9"` → slot swaps to Finish), `DoD-5: clicking 'Finish side chat' calls the finish api once with the book id, the active chat id and the active side-chat id, and the slot swaps back to Start` (`("bk-1", "c-1", "sc-9")`)
  - `DoD-6: with sideChatDeleteConfirm set, a dialog is open whose text says the messages are removed permanently and that saved work is kept, with 'Keep it' and 'Delete side chat' buttons` (`toHaveTextContent(/permanently/i)` + `/kept/i`; no api called), `DoD-6: with sideChatDeleteConfirm null, no dialog is rendered`
  - `DoD-7: clicking 'Keep it' closes the dialog, clears sideChatDeleteConfirm, calls NO api, and leaves messages and chats unchanged` (reference identity + `.slice()` content)
  - `DoD-8: clicking the dialog's 'Delete side chat' calls the delete api once with the book id, the active chat id and the pending side-chat id` (`("bk-1", "c-1", "sc-9")`; `deleteSideChat` resolved `undefined`, `getChat` resolved with a detail; slot clears and dialog closes afterwards)
  - `DoD-9: with sideChatActionStatus 'error', an alert containing sideChatActionError's text is rendered` (`getByText("Side chat already active.")`), `DoD-9: with sideChatActionStatus 'idle', no such alert exists`, `DoD-9: the banner shows the error's own text, not a fixed string`
- `frontend/tests/work/ComposerSideChatHint.test.tsx` — covers DoD-10 — renders `<Composer state onSend={vi.fn()} onStop={vi.fn()} onRetry={vi.fn()} />` through `renderWithProviders` with `Composer.test.tsx`'s `primeState` shape (`pendingPrompt` non-empty, `turnStatus: "idle"`), the active chat's `active_side_chat_id` toggled in `chats[]`; same 11-function api mock factory; asserts `getByText("Replying in the side chat")` / `queryByText(...)` null, and in both cases `getByRole("textbox", { name: "Message the assistant" })` and `getByRole("button", { name: "Send" })` `toBeEnabled()`
  - `DoD-10: with a side chat active the composer shows 'Replying in the side chat', and the input and Send are present and enabled`
  - `DoD-10: with no side chat active the composer shows no such hint, and the input and Send are present and enabled just the same`
  - `DoD-10: the hint follows the server pointer — the same composer shows it once the active chat's active_side_chat_id is set, and drops it once it is cleared` (mutations in `act(() => runInAction(...))`)
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓, DoD-10 ✓, DoD-11 [manual/live, no test — end-to-end start / two turns / finish / inject / delete-with-codex-survival / leave-and-return, outstanding for the verifier's live-run record]

## Ultra phase

- orient: done 2026-09-20
- harvest: done — docs/.cache/ultra/027.side-chats/harvest.md (2 reports)
- skeleton: done — steps 001, 002, 003, 004, 005, 006, 007
- tests: done — steps 001, 002, 003, 004, 005, 006, 007
- red-gate: FAIL (run 1) — 002 TEST (DoD-9/DoD-10 presence-only); pre-existing tests/test_data_domain_chat.py field-set pin extended (recorded under Tests → Step 001)
- red-gate: PASS (run 2)
- code: done — steps 001, 002, 003, 004, 005, 006, 007
- verify: FAIL (run 1) — 004 TEST (DoD-3 second case asserts reference identity across MobX computed reads); 001-003, 005-007 PASS
- verify: PASS (run 2) — all seven steps; `[manual/live]` outstanding: 007 DoD-11
