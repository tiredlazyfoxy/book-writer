# Feature 011 — chat-panel

| Step | File                                      | Status  | Verifier | Date |
|------|-------------------------------------------|---------|----------|------|
| 001  | `001.chat-crud-model-sampling.md`         | done    | PASS     | 2026-07-25 |
| 002  | `002.tool-registry-web-search-prompts.md` | done    | PASS     | 2026-07-25 |
| 003  | `003.streaming-turn-endpoint.md`          | done    | PASS     | 2026-07-25 |
| 004  | `004.chat-pane-list-and-settings.md`      | done    | PASS     | 2026-07-26 |
| 005  | `005.conversation-view-streaming.md`      | done    | PASS     | 2026-07-26 |

Steps 001–003 are backend and run immediately. Steps 004–005 are frontend and are **blocked until
`docs/plans/010.working-page/status.md` shows steps 002 and 004 `done`** — see `context.md` → "Hard
dependency".

## Files Changed

### Step 001 — chat CRUD, per-chat model and sampling
- `backend/app/db/chats.py` — filled `update` (bump `modified_at` + persist) and `list_by_book_and_author` (book+author+archived, most-recently-modified first)
- `backend/app/db/chat_messages.py` — filled `list_by_chat_ordered` (position asc) and `next_position` (`0` empty / `max+1`)
- `backend/app/services/chats.py` — filled all bodies: sampling parse/fallback, response mappers, ownership resolver (404-not-403), model-pair + sampling validation, create/list/get/update/model-options
- `backend/app/services/db_import_export.py` — extended chat/chat-message codecs with model pair (`llm_server_id` as str/null), `sampling_params`, and `reasoning`; `TABLE_REGISTRY` order unchanged

### Step 002 — tool registry, web search, prompt composition
- `backend/app/settings.py` — no body change needed; the two Google Custom Search fields were already present from the skeleton
- `backend/app/models/schemas/tools.py` — declarative `WebSearchArgs`, no body to fill
- `backend/app/services/web_search.py` — filled `web_search`: resolve api key + engine id via `resolve_env_ref`, one `httpx.AsyncClient` GET, render title/snippet/link per result, distinct "no results" on absent `items`, every failure mode caught → error string, resolved key never in output/logs
- `backend/app/services/tools.py` — filled `resolve_tools` (null→whole registry, allow-list filter, unknown skipped+logged) and `build_tool_bindings` (paired OpenAI defs + name→callable map, identical key sets)
- `backend/app/services/prompt_composition.py` — filled `compose_system_prompt`: non-empty layers in fixed base→mode→book→chapter order as labelled delimited sections, empty/whitespace/absent contributes nothing, all-empty → empty string

### Step 003 — streaming turn endpoint and the think splitter
- `backend/app/services/llm_servers.py` — filled `create_model_client` (delegates to the shared `_construct_client` branch, model-bound; `_create_client` unchanged)
- `backend/app/services/chat_turn.py` — filled `ThinkSplitter.feed`/`flush` (boundary-safe `<think>` splitter holding back partial tag prefixes), `build_sampling_options` (params for `llama-swap`, empty for `openai`), `prepare_turn` (ownership + model-pair + active-server + `$ENV` key pre-stream refusals), and `run_turn` (user-message-first persistence, prompt composition, whole-registry tools, `chat_with_tools` streaming through an `asyncio.Queue`, assistant message from content/thinking deltas, `thinking`/`delta`/`done`/`error` frames)

### Step 004 — chat pane: list, pick, new, archive, settings
- `frontend/src/types/chats.d.ts` — verified 1:1 with the step-001 wire shapes; no change needed (skeleton declarations already correct)
- `frontend/src/api/chats.ts` — verified thin `request<T>` forwarders (list envelopes unwrapped); no change needed
- `frontend/src/work/activeChat.ts` — filled read/write/clear: JSON-in-`localStorage` per-book pointer; reads never throw (absent/non-JSON/non-string/empty → `null`); write/clear best-effort (storage errors swallowed)
- `frontend/src/work/components/chat/chatPaneState.ts` — filled computeds (`visibleChats` filtered by `showArchived` + most-recent-first, `activeChat`, `canCreateChat`, merged `errors`) and effect fns (`loadChatPane`, `pickChat`, `createChatFromDraft`, `setChatArchived`, `saveChatSettings`); added module-private `DEFAULT_SAMPLING`, `optionKeyForChat`, `chatTimestamp`, `resolveActiveChatId`, `seedSettingsDraft`; temperature-only edits round-trip the loaded chat's other sampling params unchanged
- `frontend/src/work/components/chat/ChatPane.tsx` — header (title, show-list + new-chat controls, archived toggle), new-chat form, list, active-chat settings, general error Alert, step-005 conversation placeholder; ephemeral `useState` new-chat toggle, no effect
- `frontend/src/work/components/chat/ChatList.tsx` — visible-chats list with active marker, last-modified stamp, per-row archive/restore, empty state; picking calls `onPick`, nothing navigates
- `frontend/src/work/components/chat/ChatSettingsPanel.tsx` — model `Select` (server · model labels) + temperature `NumberInput` + validation; no-options message refuses composing; used by both new-chat and settings surfaces
- `frontend/src/work/components/shell/WorkspaceShell.tsx` — wired `onShowChatList` to reveal the active-chats list (`chatPaneState.showArchived = false`); state ownership + load effect already in place from skeleton
- `frontend/src/work/components/shell/WorkNavigator.tsx` — the `paneTarget === "chat"` entry now renders a `<button>` `NavLink` calling `onShowChatList` (no navigation); the six content entries unchanged
- `frontend/src/work/components/shell/ChatPaneSlot.tsx` — verified one-line adapter to `ChatPane`; no change needed
- `frontend/src/work/routes.tsx` — verified `/chats` redirects to the book-state route; no change needed

### Step 005 — conversation view, streaming send, collapsible thinking, retry
- `frontend/src/api/client.ts` — no body change needed; `performTokenRefresh` / `refreshAuthToken` were already the real behaviour-preserving extraction from the skeleton
- `frontend/src/api/chats.ts` — filled `streamChatTurn`: awaits `refreshAuthToken()` first, then `streamPost` against the turn endpoint with `{ prompt }`, dispatching the four frames; added module-private `frameText` narrowing the `thinking`/`delta` `unknown` payloads to their text chunk
- `frontend/src/work/components/chat/chatPaneState.ts` — filled `canSend` / `retryOffered` / `renderedMessages` computeds (in-flight bubble via a `__streaming__` sentinel key); filled `loadChatMessages` (stops any live turn + resets buffers, then `getChat` into the messages trio), `sendChatTurn` (optimistic user message, clears prompt on acceptance, opens the stream), `retryChatTurn` (same stream, `prompt=null`), `stopChatTurn` (abort + clear + re-enable composer); added module-private `turnStreamHandlers` (first delta auto-collapses live thinking) and `finishTurn` (reload once via `getChat` on `done`, atomic swap); `loadChatPane` now loads the initially-resolved active chat's messages, and `loadChatMessages` normalises a detail fetch that resolves without a payload/messages array to an empty transcript (surfaced through the messages trio) so the pane-load path can never throw a raw `.messages` dereference
- `frontend/src/work/components/chat/ChatPane.tsx` — pick handler now also calls `loadChatMessages`
- `frontend/src/work/components/chat/MessageList.tsx` — `observer` transcript: user text plain, assistant content through `react-markdown` (first repo use, no plugins), reasoning via `ThinkingBlock`, in-flight bubble from the buffers; own `ScrollArea.Autosize` bound
- `frontend/src/work/components/chat/ThinkingBlock.tsx` — controlled collapsible "Thinking" region; conditionally renders the reasoning text (absent from DOM when collapsed)
- `frontend/src/work/components/chat/Composer.tsx` — `Textarea` bound to `pendingPrompt`, send/stop controls, disabled while streaming, error banner with retry
- `frontend/src/work/components/shell/WorkspaceShell.tsx` — existing unmount cleanup also calls `stopChatTurn(chatPaneState)` (unmount-abort half of DoD-10)

## Skeleton

### Step 001 — frozen interface (2026-07-25)

**`backend/app/models/chat.py`** — new columns on existing tables (no new table):
- `Chat.llm_server_id: int | None = Field(default=None, foreign_key="llm_servers.id")` — new (mirrors `SubAgent`)
- `Chat.model_name: str | None = Field(default=None)` — new (mirrors `SubAgent`)
- `Chat.sampling_params: str = Field(default_factory=lambda: ChatSamplingParams().model_dump_json())` — new; non-nullable TEXT/JSON, default = serialized default `ChatSamplingParams`
- `ChatMessage.reasoning: str | None = Field(default=None)` — new

**`backend/app/models/schemas/chats.py`** — new file, DTOs only:
- `class ChatSamplingParams(BaseModel)` — `temperature: float = 0.8`, `top_p: float = 0.95`, `top_k: int = 40`, `repeat_penalty: float = 1.1`, `min_p: float = 0.05`, `max_tokens: int | None = None`, `seed: int | None = None`, `presence_penalty: float = 0.0`, `frequency_penalty: float = 0.0`, `enable_thinking: bool = True`
- `class CreateChatRequest(BaseModel)` — `title: str | None = None`, `llm_server_id: str | None = None`, `model_name: str | None = None`, `sampling: ChatSamplingParams | None = None` (`model_config = ConfigDict(protected_namespaces=())`)
- `class UpdateChatRequest(BaseModel)` — `title: str | None`, `archived: bool | None`, `llm_server_id: str | None`, `model_name: str | None`, `sampling: ChatSamplingParams | None` (all default `None`; `protected_namespaces=()`)
- `class ChatResponse(BaseModel)` — `id: str`, `book_id: str`, `author_id: str`, `title: str`, `llm_server_id: str | None`, `model_name: str | None`, `sampling: ChatSamplingParams`, `archived: bool`, `created_at: datetime | None`, `modified_at: datetime | None` (`protected_namespaces=()`)
- `class ChatListResponse(BaseModel)` — `items: list[ChatResponse]`
- `class ChatMessageResponse(BaseModel)` — `id: str`, `chat_id: str`, `role: str`, `content: str`, `reasoning: str | None`, `position: int`, `created_at: datetime | None`
- `class ChatMessageListResponse(BaseModel)` — `items: list[ChatMessageResponse]`
- `class ChatDetailResponse(BaseModel)` — `chat: ChatResponse`, `messages: list[ChatMessageResponse]` (return of the chat+messages fetch; see Notes)
- `class ModelOptionResponse(BaseModel)` — `server_id: str`, `server_name: str`, `model_name: str` (`protected_namespaces=()`)
- `class ModelOptionListResponse(BaseModel)` — `items: list[ModelOptionResponse]`

**`backend/app/db/chats.py`** — added, session-free (existing `create`/`get_by_id`/`list_by_book` unchanged):
- `async def update(row: Chat) -> Chat` — new; persists changed columns, bumps `modified_at`, returns the row
- `async def list_by_book_and_author(book_id: int, author_id: int, archived: bool) -> list[Chat]` — new; most-recently-modified first

**`backend/app/db/chat_messages.py`** — added, session-free (existing `create`/`get_by_id`/`list_by_chat` unchanged):
- `async def list_by_chat_ordered(chat_id: int) -> list[ChatMessage]` — new; `position` ascending
- `async def next_position(chat_id: int) -> int` — new; `0` for empty, else `max(position) + 1`

**`backend/app/services/chats.py`** — new file:
- `class ChatErrorReason(str, enum.Enum)` — `chat_not_found`, `invalid_model_pair`, `unknown_or_inactive_server`, `model_not_enabled`, `invalid_sampling`
- `class ChatError(Exception)` — `__init__(self, reason: ChatErrorReason, message: str = "")`; carries `.reason` / `.message`
- `def _parse_sampling(raw: str) -> ChatSamplingParams` — falls back to defaults on unparseable
- `def _to_chat_response(chat: Chat) -> ChatResponse`
- `def _to_message_response(message: ChatMessage) -> ChatMessageResponse`
- `async def _resolve_owned_chat(access: authz.BookAccess, chat_id: int) -> Chat` — ownership gate; raises `ChatError(chat_not_found)` (404, not 403)
- `async def create_chat(access: authz.BookAccess, req: CreateChatRequest) -> ChatResponse`
- `async def list_chats(access: authz.BookAccess, archived: bool) -> ChatListResponse`
- `async def get_chat(access: authz.BookAccess, chat_id: str) -> ChatDetailResponse`
- `async def update_chat(access: authz.BookAccess, chat_id: str, req: UpdateChatRequest) -> ChatResponse`
- `async def list_model_options(access: authz.BookAccess) -> ModelOptionListResponse`

**`backend/app/routes/chats.py`** — new file; `router = APIRouter(prefix="/api/books", tags=["chats"])`:
- `_CHAT_ERROR_STATUS: dict[ChatErrorReason, int]` + `_map_chat_error(err) -> HTTPException` + `_map_authz_error(err) -> HTTPException`
- `GET /{book_id}/chats/model-options` → `list_model_options(access) -> ModelOptionListResponse` (declared **before** the `{chat_id}` routes)
- `POST /{book_id}/chats` (201) → `create_chat(payload: CreateChatRequest, access) -> ChatResponse`
- `GET /{book_id}/chats` → `list_chats(archived: bool = False, access) -> ChatListResponse`
- `GET /{book_id}/chats/{chat_id}` → `get_chat(chat_id: str, access) -> ChatDetailResponse`
- `PATCH /{book_id}/chats/{chat_id}` → `update_chat(chat_id: str, payload: UpdateChatRequest, access) -> ChatResponse`
- Every endpoint takes `access: authz.BookAccess = Depends(authz.book_access)`

**`backend/app/main.py`** — `from app.routes import chats` + `app.include_router(chats.router)` (mounted bare, after `books.router`).

**`backend/app/services/db_import_export.py`** — a Source file, but **left unchanged by the skeleton**. The four chat codecs (`_chat_to_dict` / `_dict_to_chat` / `_chat_message_to_dict` / `_dict_to_chat_message`) keep their frozen 008 signatures (dict in/out) and existing bodies; they still compile and preserve existing behavior because the new columns are all defaulted. Extending them to emit/read the new fields (DoD-10) is behavior for the **coder** to fill, not a signature change. `TABLE_REGISTRY` order is unchanged.

- Caller-compile edits (out of Source-files scope): None.

### Step 002 — frozen interface (2026-07-25)

**`backend/app/settings.py`** — two new fields on `Settings` (nothing else changed):
- `google_search_api_key: str | None = Field(default=None, validation_alias="BOOKWRITER_GOOGLE_SEARCH_API_KEY")` — new; holds a `$ENV_VAR` pointer, resolved via `resolve_env_ref` at call time
- `google_search_engine_id: str | None = Field(default=None, validation_alias="BOOKWRITER_GOOGLE_SEARCH_ENGINE_ID")` — new

**`backend/app/models/schemas/tools.py`** — new file, declarative Pydantic only:
- `class WebSearchArgs(BaseModel)` — `query: str`, `num_results: int = Field(default=5, ge=1, le=10)`. Field names are load-bearing: they are exactly `web_search`'s keyword params.

**`backend/app/services/web_search.py`** — new file:
- `async def web_search(query: str, num_results: int = 5) -> str` — new; params match `WebSearchArgs` field names exactly (verified via `inspect.signature`). Body UNIMPLEMENTED (raises).
- module constant `_ENDPOINT = "https://www.googleapis.com/customsearch/v1"`

**`backend/app/services/tools.py`** — new file:
- `@dataclass(frozen=True) class ToolDef` — `name: str`, `description: str`, `args_schema: type[BaseModel]`, `callable: Callable[..., object]` (loose per context.md, accepts sync/async and closures/partials)
- `TOOL_REGISTRY: list[ToolDef]` — populated (declarative): one entry `ToolDef(name="web_search", description=<non-empty>, args_schema=WebSearchArgs, callable=web_search)`
- `def resolve_tools(allowed_names: Collection[str] | None) -> list[ToolDef]` — new; body UNIMPLEMENTED
- `def build_tool_bindings(tools: list[ToolDef]) -> tuple[list[dict[str, object]], dict[str, Callable[..., object]]]` — new; body UNIMPLEMENTED

**`backend/app/services/prompt_composition.py`** — new file:
- `BASE_SYSTEM_PROMPT: str` — populated non-empty constant (exact text unpinned by any DoD; skeleton owns it as declarative content)
- `def compose_system_prompt(base: str | None = None, mode: str | None = None, book: str | None = None, chapter: str | None = None) -> str` — new; body UNIMPLEMENTED

- Caller-compile edits (out of Source-files scope): None. All five files are additive; no existing symbol changed, so no callers required adaptation.

### Step 003 — frozen interface (2026-07-25)

**`backend/app/services/llm_servers.py`** — model-bound client construction beside `_create_client`:
- `def _construct_client(server: LlmServer, resolved_key: str | None, model: str) -> LLMClient` — new; the single `backend_type` → client-class branch (`"openai"` → `OpenAIAPIClient`, else `LlamaSwapAPIClient`), extracted so the mapping lives once. Populated (declarative construction, mirrors the delivered `_create_client` body).
- `def _create_client(server: LlmServer, resolved_key: str | None) -> LLMClient` — **unchanged** signature/name/behaviour; body now delegates to `_construct_client(server, resolved_key, model="")`. Still constructs with `model=""` (verified), still the monkeypatch seam.
- `def create_model_client(server: LlmServer, resolved_key: str | None, model: str) -> LLMClient` — new; sync; the chat-turn sibling bound to a real `model`. Body UNIMPLEMENTED (raises). Docstring pins: return value is an **async context manager** (`__aenter__`/`__aexit__`, no `close()`).

**`backend/app/services/chat_turn.py`** — new file:
- `MAX_LOOPS = 4` — module constant; bounded tool-call rounds per turn.
- `_TURN_FAILURE_EXCEPTIONS: tuple[type[Exception], ...]` — `(aiohttp.ClientError, LLMError, ValueError, RuntimeError)`; the failure-taxonomy surface (empty-result is an extra behavioural check, not a type).
- `Channel = Literal["thinking", "content"]`; `CHANNEL_THINKING: Channel = "thinking"`; `CHANNEL_CONTENT: Channel = "content"`.
- `class ThinkSplitter` — `__init__(self) -> None` (no frozen state; `pass`); `def feed(self, chunk: str) -> list[tuple[Channel, str]]` UNIMPLEMENTED; `def flush(self) -> list[tuple[Channel, str]]` UNIMPLEMENTED.
- `def build_sampling_options(sampling: ChatSamplingParams, backend_type: str) -> dict[str, object]` — new; params only for `"llama-swap"`, empty for `"openai"`. Body UNIMPLEMENTED (raises).
- `@dataclass(frozen=True) class TurnContext` — `chat: Chat`, `server: LlmServer`, `resolved_key: str | None` (the resolved output of `prepare_turn`).
- `@dataclass(frozen=True) class TurnFrame` — `event: str`, `data: BaseModel` (the SSE frame envelope the orchestrator yields; `event` ∈ `thinking`/`delta`/`done`/`error`, `data` is the matching schema payload).
- `async def prepare_turn(access: authz.BookAccess, chat_id: str) -> TurnContext` — new; the pre-stream refusals. Body UNIMPLEMENTED (raises).
- `async def run_turn(context: TurnContext, prompt: str | None) -> AsyncGenerator[TurnFrame, None]` — new; the frame-yielding orchestrator. Body UNIMPLEMENTED (raises, then unreachable `yield` so it compiles as an async generator — verified `isasyncgenfunction`).

**`backend/app/models/schemas/chats.py`** — new DTOs appended (declarative, nothing to implement):
- `class TurnRequest(BaseModel)` — `prompt: str | None = None` (absent = retry).
- `class ThinkingFrame(BaseModel)` — `text: str`.
- `class DeltaFrame(BaseModel)` — `text: str`.
- `class DoneFrame(BaseModel)` — `message: ChatMessageResponse`.
- `class ErrorFrame(BaseModel)` — `message: str`.

**`backend/app/routes/chats.py`** — one added endpoint + one added error map (existing routes unchanged):
- `_LLM_SERVER_ERROR_STATUS: dict[LlmServerErrorReason, int]` + `def _map_llm_server_error(err) -> HTTPException` — mirrors `routes/admin/llm_servers.py` (env_not_set → 400); the turn's pre-stream checks may raise `LlmServerError`.
- `POST /{book_id}/chats/{chat_id}/turn` → `run_chat_turn(chat_id: str, payload: TurnRequest, access) -> StreamingResponse` — declared **after** the static `model-options` route; calls `chat_turn.prepare_turn` (typed errors → 404/400 JSON via the three `_map_*` helpers), then returns a `StreamingResponse(media_type="text/event-stream")` whose inner generator serializes each `TurnFrame` as `event: <event>\ndata: <data.model_dump_json()>\n\n`. The SSE construction is the HTTP-layer concern (route); the frame-yielding orchestrator is the service.
- New imports: `AsyncGenerator`, `StreamingResponse`, `TurnRequest`, `from app.services import chat_turn`, `from app.services import llm_servers as llm_servers_service`.

- Caller-compile edits (out of Source-files scope): None. `_create_client` kept its exact signature/name/behaviour, so `probe_models` (its only caller) needed no change; `main.py` already mounts `chats.router` (the turn endpoint is on the same router).

### Step 004 — frozen interface (2026-07-26)

**`frontend/src/types/chats.d.ts`** — new file, hand-written wire DTOs (declarative, wire-exact `snake_case`, ids `string`, no envelope types):
- `interface ChatSamplingParams` — `temperature/top_p/top_k/repeat_penalty/min_p: number`, `max_tokens/seed: number | null`, `presence_penalty/frequency_penalty: number`, `enable_thinking: boolean`
- `interface CreateChatRequest` — `title?/llm_server_id?/model_name?: string | null`, `sampling?: ChatSamplingParams | null` (all optional)
- `interface UpdateChatRequest` — `title?/llm_server_id?/model_name?: string | null`, `archived?: boolean | null`, `sampling?: ChatSamplingParams | null` (all optional)
- `interface ChatResponse` — `id/book_id/author_id: string`, `title: string`, `llm_server_id/model_name: string | null`, `sampling: ChatSamplingParams`, `archived: boolean`, `created_at/modified_at: ISODateString | null`
- `interface ChatMessageResponse` — `id/chat_id: string`, `role/content: string`, `reasoning: string | null`, `position: number`, `created_at: ISODateString | null`
- `interface ChatDetailResponse` — `chat: ChatResponse`, `messages: ChatMessageResponse[]`
- `interface ModelOptionResponse` — `server_id/server_name/model_name: string`

**`frontend/src/api/chats.ts`** — new file; `const BASE = "/api/books"`; thin `request<T>` forwarders (the `api/books.ts` precedent — no DoD-asserted behaviour, every spec mocks this module). `signal?` trailing:
- `async listChats(bookId: string, archived: boolean, signal?: AbortSignal): Promise<ChatResponse[]>` — unwraps `.items`
- `async createChat(bookId: string, body: CreateChatRequest, signal?: AbortSignal): Promise<ChatResponse>`
- `async updateChat(bookId: string, chatId: string, body: UpdateChatRequest, signal?: AbortSignal): Promise<ChatResponse>`
- `async getChat(bookId: string, chatId: string, signal?: AbortSignal): Promise<ChatDetailResponse>`
- `async listModelOptions(bookId: string, signal?: AbortSignal): Promise<ModelOptionResponse[]>` — unwraps `.items`

**`frontend/src/work/activeChat.ts`** — new file; plain module functions in the `restoreBuffer.ts`/`auth.ts` tier (no class, no MobX, no `src/api/` import):
- `const ACTIVE_CHAT_KEY_PREFIX = "bookwriter.active-chat"`
- `activeChatKey(bookId: string): string` — pure key builder, **implemented** (structural)
- `readActiveChatId(bookId: string): string | null` — UNIMPLEMENTED (throws; contract: never throws once filled)
- `writeActiveChatId(bookId: string, chatId: string): void` — UNIMPLEMENTED (throws)
- `clearActiveChatId(bookId: string): void` — UNIMPLEMENTED (throws)

**`frontend/src/work/components/chat/chatPaneState.ts`** — new file:
- `interface ChatModelSettingsDraft` — `optionKey: string | null`, `temperature: number`
- `interface NewChatDraft extends ChatModelSettingsDraft` — adds `title: string`
- `const DEFAULT_TEMPERATURE = 0.8`, `const MIN_TEMPERATURE = 0`, `const MAX_TEMPERATURE = 2` (skeleton-owned; bounds unpinned by any DoD)
- `modelOptionKey(option: ModelOptionResponse): string` — pure `(server_id, model_name)` encoder, **implemented** (`server_id::model_name`)
- `class ChatPaneState` — observable: `chats: ChatResponse[]` + `chatsStatus: "idle"|"loading"|"ready"|"error"` + `chatsError: string | null`; `modelOptions: ModelOptionResponse[]` + `modelOptionsStatus` + `modelOptionsError`; `activeChatId: string | null`; `showArchived: boolean`; `newChatDraft: NewChatDraft`; `settingsDraft: ChatModelSettingsDraft`; `serverErrors: Record<string, string>`; `createStatus`/`archiveStatus`/`settingsStatus` (each the 4-value union). `makeAutoObservable`, no methods. Computeds (all UNIMPLEMENTED — throw): `get visibleChats(): ChatResponse[]`, `get activeChat(): ChatResponse | null`, `get canCreateChat(): boolean`, `get errors(): Record<string, string>`
- External effect fns (all UNIMPLEMENTED — throw):
  - `async loadChatPane(state: ChatPaneState, bookId: string, signal?: AbortSignal): Promise<void>`
  - `pickChat(state: ChatPaneState, bookId: string, chatId: string): void` (sync — set id + write pointer)
  - `async createChatFromDraft(state: ChatPaneState, bookId: string, signal?: AbortSignal): Promise<void>`
  - `async setChatArchived(state: ChatPaneState, bookId: string, chatId: string, archived: boolean, signal?: AbortSignal): Promise<void>`
  - `async saveChatSettings(state: ChatPaneState, bookId: string, signal?: AbortSignal): Promise<void>`

**`frontend/src/work/components/chat/ChatPane.tsx`** — new; `interface ChatPaneProps { bookId: string; state: ChatPaneState }`; `export const ChatPane = observer(function ChatPane(props: ChatPaneProps) …)` — body throws (DoD-asserted rendering is the coder's).

**`frontend/src/work/components/chat/ChatList.tsx`** — new; `interface ChatListProps { state: ChatPaneState; onPick: (chatId: string) => void; onSetArchived: (chatId: string, archived: boolean) => void }`; `ChatList = observer(...)` — body throws.

**`frontend/src/work/components/chat/ChatSettingsPanel.tsx`** — new; `interface ChatSettingsPanelProps { options: ModelOptionResponse[]; draft: ChatModelSettingsDraft; errors: Record<string, string> }`; `ChatSettingsPanel = observer(...)` — body throws. (Used twice; `NewChatDraft` is assignable to `draft` via extension.)

**`frontend/src/work/components/shell/ChatPaneSlot.tsx`** — **changed**: the 010 placeholder notice is removed; now a thin adapter. `interface ChatPaneSlotProps { bookId: string; state: ChatPaneState }`; `ChatPaneSlot = observer(({ bookId, state }) => <ChatPane bookId={bookId} state={state} />)`. (Chose the one-line-adapter option, not deletion.)

**`frontend/src/work/components/shell/WorkspaceShell.tsx`** — **changed**: owns `const [chatPaneState] = useState(() => new ChatPaneState())`; the EXISTING mount `useEffect` also runs `void loadChatPane(chatPaneState, bookId ?? "", ctrl.signal)` (deps `[state, chatPaneState]`); renders `<ChatPaneSlot bookId={id} state={chatPaneState} />` and passes `onShowChatList` to `<WorkNavigator>`. No second effect, no context.

**`frontend/src/work/components/shell/WorkNavigator.tsx`** — **changed**: `WorkNavigatorProps` gains `onShowChatList: () => void` (frozen). Body **preserved** (still renders all seven entries as links — 010 behaviour); routing the `paneTarget === "chat"` entry to the control is the DoD-5 behaviour left for the coder.

**`frontend/src/work/routes.tsx`** — **changed**: added `function ChatsRedirectRoute()` (reads `:bookId`, returns `<Navigate to={`/${bookId}/state`} replace />`); the `/chats` route element changed from `SubjectPlaceholderPage` to `<ChatsRedirectRoute />`. Every other route untouched.

- Caller-compile edits (out of Source-files scope): None. The only external caller of the changed surfaces is `WorkspaceShell` (itself a Source file); `ChatPaneSlot` / `WorkNavigator` prop changes are consumed there. No file outside the Source list required adaptation.

### Step 005 — frozen interface (2026-07-26)

**`frontend/src/api/client.ts`** — one added export + a behaviour-preserving refactor (existing `request<T>` / `authHeaders` / `ApiError` / `throwApiError` unchanged):
- `async function performTokenRefresh(): Promise<void>` — new, module-private; the single refresh path extracted verbatim from the old `silentRefreshRetry` body (missing-token / transport-fail / non-OK → `logout()` + `throw ApiError(401)`; success → `setAccessToken`). **Implemented** (behaviour-preserving extraction, not a stub).
- `silentRefreshRetry<T>(url, opts)` — **unchanged signature/behaviour**; body now `await performTokenRefresh()` then the same one-shot retry under the `isRefreshing` guard.
- `export async function refreshAuthToken(): Promise<void>` — **new**; thin real wrapper `await performTokenRefresh()`. The reusable entry point streaming callers await before opening a stream. Real (not throwing): no DoD pins its internals — DoD-9 (await-before-stream) is the `api/chats` seam, which stays red. Reuses the one refresh path + same `logout()` fallback (no second refresh path).

**`frontend/src/api/chats.ts`** — one added type + one added function (existing five forwarders unchanged; `const BASE = "/api/books"`):
- `interface TurnStreamHandlers` — `onThinking: (text: string) => void`, `onDelta: (text: string) => void`, `onDone: () => void`, `onError: (message: string) => void`. **`onDone` carries NO payload** — see the note below.
- `async function streamChatTurn(bookId: string, chatId: string, prompt: string | null, handlers: TurnStreamHandlers): Promise<AbortController>` — **new**; `prompt` = author text, `null` = retry. Body UNIMPLEMENTED (throws). Deliberately breaks the trailing-`signal` convention (returns the controller `streamPost` owns); seam documented in the module.

**`frontend/src/work/components/chat/chatPaneState.ts`** — conversation half added (existing step-004 fields / computeds / effect fns unchanged):
- `interface RenderedMessage` — `key: string`, `role: string`, `content: string`, `reasoning: string | null`, `streaming: boolean`.
- New observable fields on `ChatPaneState`: `messages: ChatMessageResponse[]` + `messagesStatus: "idle"|"loading"|"ready"|"error"` + `messagesError: string | null`; `streamingContent: string`; `streamingThinking: string`; `turnStatus: "idle"|"streaming"|"error"`; `turnError: string | null`; `liveThinkingExpanded: boolean`; `expandedReasoning: Record<string, boolean>`; `pendingPrompt: string`; `turnController: AbortController | null`.
- New computeds (all UNIMPLEMENTED — throw): `get canSend(): boolean`, `get retryOffered(): boolean`, `get renderedMessages(): RenderedMessage[]`.
- New external effect fns (all UNIMPLEMENTED — throw):
  - `async loadChatMessages(state: ChatPaneState, bookId: string, chatId: string, signal?: AbortSignal): Promise<void>`
  - `async sendChatTurn(state: ChatPaneState, bookId: string, text: string): Promise<void>`
  - `async retryChatTurn(state: ChatPaneState, bookId: string): Promise<void>`
  - `stopChatTurn(state: ChatPaneState): void` (sync)

**`frontend/src/work/components/chat/MessageList.tsx`** — new; `interface MessageListProps { state: ChatPaneState }`; `export const MessageList = observer(function MessageList(_props: MessageListProps) …)` — body throws.

**`frontend/src/work/components/chat/ThinkingBlock.tsx`** — new; `interface ThinkingBlockProps { text: string; expanded: boolean; onToggle: () => void }`; `ThinkingBlock = observer(...)` — body throws. Stateless / fully controlled.

**`frontend/src/work/components/chat/Composer.tsx`** — new; `interface ComposerProps { state: ChatPaneState; onSend: () => void; onStop: () => void; onRetry: () => void }`; `Composer = observer(...)` — body throws.

**`frontend/src/work/components/chat/ChatPane.tsx`** — **changed** (structural): the step-004 conversation placeholder `<Box>` replaced with `{state.activeChat && (<><MessageList state={state} /><Composer state={state} onSend/onStop/onRetry /></>)}`; added `handleSend`/`handleRetry`/`handleStop` wired to `sendChatTurn`/`retryChatTurn`/`stopChatTurn` (no `signal` — the stream owns its controller); dropped the now-unused `Box` import. `ChatPaneProps` unchanged. No new state, no new effect. The pick handler's message-load and any auto-scroll `autorun` are left to the coder (see notes).

- Caller-compile edits (out of Source-files scope): None. `refreshAuthToken` / `streamChatTurn` / the new state members are additive; `WorkspaceShell` (out of scope) still compiles unchanged.

## Tests

### Step 001 — tests (2026-07-25)

- `backend/tests/db/test_chats.py` — covers DoD-2, DoD-5 — db `update` persists changed columns + bumps `modified_at`; `list_by_book_and_author` filters by (book, author, archived) and orders most-recently-modified first.
- `backend/tests/db/test_chat_messages.py` — covers DoD-4 — `list_by_chat_ordered` sorts by `position` ascending and is chat-scoped; `next_position` returns 0 empty / max+1 otherwise.
- `backend/tests/services/test_chats.py` — covers DoD-1, DoD-2, DoD-3, DoD-4, DoD-5, DoD-6, DoD-7, DoD-8 — create stores author+book (string ids); list is caller-private; other-author fetch/update → `ChatError(chat_not_found)`; get returns position-ordered messages; archive/restore round-trip; model-pair validation (both-null/both-set/half-set/inactive-server/model-not-enabled); sampling defaults, partial defaults, `_parse_sampling` fallback, corrupt read-as-defaults, `top_k` survives unrelated update; model-options active-only triples with no api key.
- `backend/tests/routes/test_chats.py` — covers DoD-1, DoD-2, DoD-3, DoD-4, DoD-5, DoD-6, DoD-8, DoD-9 — end-to-end create/list/get/patch + model-options; caller-privacy across owner/co-author roles; other-author 404-not-403; position-ordered messages; archive/restore; half-set pair 400 + valid pair 201; default sampling in response; model-options active-only, no api key; non-member 404 from every route.
- `backend/tests/test_data_domain_chat.py` — covers DoD-10 (amended) — new-column codec round-trips (model pair as string/null, `sampling_params` JSON, `reasoning`), Chat/ChatMessage field-set pins include the new fields, registry order unchanged.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓, DoD-10 ✓, DoD-11 [manual/live, no test].

### Step 002 — tests (2026-07-25)

- `backend/tests/services/test_prompt_composition.py` — covers DoD-1, DoD-2 — base constant non-empty; four layers rendered in fixed order base→mode→book→chapter, each once; whitespace/empty/absent layer contributes nothing (identical to omitting it); base+book only = exactly two sections; all-empty/all-whitespace = empty string. Asserts ordering/skip behaviour via sentinels (delimiter format is skeleton-owned, unpinned by spec).
- `backend/tests/services/test_tools.py` — covers DoD-3, DoD-4, DoD-5 — `TOOL_REGISTRY` has exactly one `web_search` entry (non-empty description, `args_schema` is `WebSearchArgs`, `callable` is `web_search`); args-schema field names == callable keyword params via `inspect.signature`; `build_tool_bindings` yields OpenAI defs + name→callable map with identical key sets, defs carry name/description/JSON-schema, name maps to the real callable; null mode → whole registry, allow-list → just those, unknown name skipped not raised, only-unknown → empty.
- `backend/tests/services/test_web_search.py` — covers DoD-6, DoD-7, DoD-8, DoD-9 — httpx boundary mocked (patches `httpx.AsyncClient`, no network); results string contains each title/snippet/link; absent `items` → distinct "no results" string; `$ENV_VAR` indirection resolves (resolved secret in request, pointer not), resolved key never in output; every failure mode (env var unset, settings unconfigured, non-2xx, transport failure, malformed payload) returns an error string rather than raising; mocked boundary exercised exactly once.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓, DoD-10 [manual/live, no test], DoD-11 [manual/live, no test].

### Step 003 — tests (2026-07-25)

- `backend/tests/services/test_think_splitter.py` — covers DoD-1 — `ThinkSplitter` (plain object) under adversarial chunkings: tag split across two deltas, tag glued to payload on both sides in one delta, several think blocks in one stream, stream opening with a think block, no tags at all, unclosed tag at end of stream, held-back partial that is not a tag flushed verbatim, and a false tag-prefix across a chunk boundary; each asserts correct channel routing (via frozen `CHANNEL_THINKING`/`CHANNEL_CONTENT`) and the no-loss/no-duplication invariant (emitted text == original minus tag markers).
- `backend/tests/services/test_chat_turn.py` — covers DoD-2, DoD-3, DoD-4, DoD-5, DoD-6, DoD-7, DoD-8, DoD-9, DoD-11 — LLM boundary faked at the `create_model_client` seam (fake async-context-manager client whose `chat_with_tools` drives `on_delta` with scripted chunks then returns/raises); `run_turn` tests build `TurnContext` directly, `prepare_turn` tests run against the `db` fixture. Asserts: user message persisted before the assistant call and surviving a failure once with no assistant message (DoD-2); a no-prompt retry re-runs over stored history without duplicating the user message (DoD-3); a success persists one assistant message with content = joined content deltas / reasoning = joined thinking deltas at the next position (DoD-4); frame vocabulary `thinking`/`delta`/`done`/`error` routed by channel, one terminal `done` carrying the DTO on success and one `error` on failure (DoD-5); `build_sampling_options` params only for `llama-swap`, empty for `openai` (DoD-6); `prepare_turn` resolves the key via `$ENV` indirection and `run_turn` constructs the client bound to `(server, model)` with the resolved key and closes it (`__aexit__`) on both success and failure (DoD-7); `prepare_turn` typed refusals for no-model-pair / inactive server / unset key env with nothing persisted (DoD-8); five library-failure classes each yield a single `error` frame and no assistant message (DoD-9); system prompt composed from `BASE_SYSTEM_PROMPT` + book `system_prompt` and the whole `TOOL_REGISTRY` offered under null mode (DoD-11).
- `backend/tests/routes/test_chat_turn.py` — covers DoD-5, DoD-8, DoD-9, DoD-10 — end-to-end over the real app (`http_client`, real JWT), LLM faked at `create_model_client`. Asserts: a successful turn returns a `text/event-stream` whose named frames end in a single `done` carrying the persisted assistant message DTO, persisting user + assistant (DoD-5); a post-open library failure surfaces as an `error` frame over HTTP 200 (not a 500 / hung stream), user stored, no assistant (DoD-9); pre-stream refusals (no model pair, inactive server, missing server, unset key env) answer ordinary HTTP 400 with nothing persisted (DoD-8); another author's chat and a non-member each get 404 before any streaming and before anything is persisted (DoD-10).
- Patch seam note: `create_model_client` is monkeypatched at `app.services.llm_servers.create_model_client` (the namespace-import source per the enforced backend convention) and, belt-and-suspenders with `raising=False`, at `app.services.chat_turn.create_model_client` in case of a direct import.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓, DoD-10 ✓, DoD-11 ✓, DoD-12 [manual/live, no test], DoD-13 [manual/live, no test].

### Step 004 — tests (2026-07-26)

- `frontend/tests/work/activeChat.test.ts` — covers DoD-4 — the active-chat pointer: write/read round-trip; per-book keying (writing/clearing one book leaves another untouched; key varies by book id under the module prefix); device-local (write hits localStorage only, no fetch); a read never throws on absent/garbage/empty stored values.
- `frontend/tests/work/ChatPane.test.tsx` — covers DoD-1, DoD-2, DoD-3, DoD-6, DoD-7, DoD-8, DoD-9, DoD-10, DoD-11 — `../../src/api/chats` mocked module-factory form, shell-owned load driven per test then `<ChatPane>`/`<ChatSettingsPanel>` rendered with populated `ChatPaneState`. Asserts: `visibleChats` non-archived, most-recent-first + titles rendered + empty state (DoD-1); `pickChat` sets active id + per-book pointer with no api call / no navigation (DoD-2); load resolves active from a visible pointer, else the most recent, else none, incl. a not-in-list pointer falling back (DoD-3); `canCreateChat` needs a chosen option AND an in-range temperature, and a success creates via the api with the chosen (server, model)+temperature, becomes active, appears in the list (DoD-6); the picker shows each option's server + model name and no options refuses composing / renders a message (DoD-7); editing the active chat's model+temperature calls `updateChat` and the pane reflects the new values (DoD-8); archive drops from the active list, restore returns it, archiving the active chat re-resolves active with no dangling pointer (DoD-9); a temperature-only edit round-trips every other stored sampling param unchanged in the update body (DoD-10); a failed load records an error and renders non-blank, a failed action surfaces an error without throwing (DoD-11).
- `frontend/tests/work/chatsNavigatorEntry.test.tsx` — covers DoD-5 — `api/books` + `api/chats` mocked; a `LocationProbe` makes the route observable. Clicking Chats calls `onShowChatList` and does not change the route; the six content-pane entries still navigate and do not open the list; `/bk-1/chats` redirects to `/bk-1/state` with no chats-owner surface in the content pane (`main`).
- `frontend/tests/work/WorkNavigator.test.tsx` — covers DoD-5 (updated 2026-07-26 from a 010 test) — re-bound to the frozen step-004 `WorkNavigatorProps` (required `onShowChatList`, passed as a `vi.fn()` on every render). Asserts the new contract: exactly the **six** content-pane entries render as in-SPA router links in UC-090 order with their subject hrefs (Chats is no longer among the links); the Chats entry is a control — not a router link — that on activation calls `onShowChatList` once and leaves the route unchanged (`LocationProbe`). Old "seven router links" / no-`onShowChatList` assumptions removed.
- `frontend/tests/work/subjectRoutes.test.tsx` — covers DoD-5 (updated 2026-07-26 from a 010 test) — the `/bk-1/chats` case removed from the content-pane list-route table (it no longer renders an `011.chat-panel` placeholder in `main`); a new case asserts `/:bookId/chats` **redirects** to `/:bookId/state` (`LocationProbe` observes the pathname) with no `011.chat-panel` surface inside the content pane. Other subject-route assertions (chapters/codex/variants list + item routes, no `chat/:id` route) preserved. Added the `api/chats` module-factory mock (all five exports; `listChats`/`listModelOptions` resolve empty) because `WorkRoutes` now mounts the shell that owns the chat pane and loads on mount.
- `frontend/tests/work/WorkspaceShell.test.tsx` — updated 2026-07-26 from a 010 test to the step-004 contract — dropped the chat-pane slot's `011.chat-panel` owner-notice assertion (Interface intent removes it); the DoD-4 region test now asserts the third region via the aside (`complementary`) landmark and that no `011.chat-panel` notice remains. Shell's still-valid book-load assertions preserved (three regions, single book load, pending/error chrome, one-load-across-subject-nav). Added the `api/chats` module-factory mock (all five exports; `listChats`/`listModelOptions` resolve empty) since the shell now owns `ChatPaneState` and starts a chat load in its mount effect.
- `frontend/tests/work/BookStatePage.test.tsx` — (step-010 test, harness-mock sweep 2026-07-26) — no assertion change; added the `api/chats` module-factory mock (all five exports; `listChats`/`listModelOptions` resolve empty, others trivial resolved) because its DoD-1 case mounts the full `WorkRoutes` table at `/bk-1`, which now mounts the shell that owns `ChatPaneState` and starts a chat load on mount.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓, DoD-10 ✓, DoD-11 ✓, DoD-12 [manual/live, no test].

Harness-mock sweep note (2026-07-26): shell-mounting specs verified to mock `src/api/chats` — `WorkspaceShell.test.tsx`, `subjectRoutes.test.tsx`, `chatsNavigatorEntry.test.tsx`, `ChatPane.test.tsx`, and now `BookStatePage.test.tsx`. `routes.test.tsx` renders `WorkRoutes` only at `/` (top-level catch-all → NotFoundPage; never matches `/:bookId`), so it does not mount the shell and needs no mock.

### Step 005 — tests (2026-07-26)

- `frontend/tests/support/sseFixture.ts` — the repo's first SSE test fixture (support, not a spec). `installTurnStream(vi.mocked(streamChatTurn))` installs a capturing implementation: records each opened turn (args + the four `TurnStreamHandlers` callbacks), resolves with a fresh `AbortController` whose `abort` is spied, and exposes `thinking`/`delta`/`done`/`error` to fire scripted frames at the latest turn. Bound to the frozen `streamChatTurn(bookId, chatId, prompt: string|null, handlers): Promise<AbortController>` and payload-less `onDone`.
- `frontend/tests/work/chatStreaming.test.ts` — covers DoD-2, DoD-3, DoD-5, DoD-6, DoD-7, DoD-8, DoD-9, DoD-10 — state-level, `../../src/api/chats` mocked module-factory form + the fixture. Asserts: the author's message shows immediately and the in-flight bubble grows across delta frames fired one at a time (DoD-2); thinking frames keep the live region expanded and the first content delta auto-collapses it with thinking preserved (DoD-3); `done` reloads via `getChat` once and the streaming bubble becomes exactly one persisted assistant message with no duplicate/orphan (DoD-5); an `error` sets `turnError`, offers retry, and preserves the author's message (DoD-6); retry re-opens the stream with `prompt === null` on the same chat, does not duplicate the user message, and a success appends exactly one assistant message (DoD-7); `canSend` is false while streaming and true again after both `done` and `error`, and a second prompt continues the same chat retaining the prior exchange (DoD-8); the REAL `streamChatTurn` (via `importActual`, with `refreshAuthToken`/`streamPost` stubbed) awaits the refresh before opening the stream — order `["refresh","stream"]` (DoD-9); loading another chat aborts the live controller and clears the streaming buffers, and `stopChatTurn` aborts the stored controller (DoD-10).
- `frontend/tests/work/ChatConversation.test.tsx` — covers DoD-1, DoD-2, DoD-3, DoD-4, DoD-6, DoD-8 — component-level, `../../src/api/chats` mocked, observable state set directly (no network). Asserts: a reopened chat renders stored messages in position order with assistant content through react-markdown (`<strong>`) and user content plain/literal (DoD-1); MessageList renders the in-flight bubble from `streamingContent` (DoD-2); the live thinking region reflects `liveThinkingExpanded` — shown when expanded, hidden when collapsed (DoD-3); a persisted message's reasoning is collapsed by default and a thinking toggle reveals it, and `ThinkingBlock` (controlled) hides text when collapsed / shows when expanded / calls `onToggle` on activation (DoD-4); the Composer shows the error banner + a retry control wired to `onRetry` (DoD-6); the prompt input is disabled while streaming with a stop control wired to `onStop`, and enabled again when idle (DoD-8).
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓, DoD-10 ✓, DoD-11 [manual/live, no test], DoD-12 [manual/live, no test].

## Notes & Issues

- Step 001: added two module-private helpers in `services/chats.py` beyond the frozen set — `_validate_model_pair` (shared by create/update for the both-null/both-set + active-server + enabled-model checks) and `_parse_chat_id` (non-numeric path id → `chat_not_found`/404). No frozen signature, DTO, or route symbol changed.
- Step 001: `update_chat` treats the model pair non-destructively — it re-validates and applies only when at least one of `llm_server_id` / `model_name` is present in the body, so a title-only or archive-only PATCH never wipes an existing pair (a both-null body is a no-op, not a clear). Half-set still refused with 400.
- Step 001: create defaults an omitted/empty `title` to `"New chat"` (the Chat table's `title` is non-nullable; the spec names a default without pinning its value).
- Step 005 (CODE-fault fix, 2026-07-26): `loadChatMessages` guarded against a `getChat` result that resolves without a payload object or messages array — it now normalises to an empty transcript via `Array.isArray(detail?.messages) ? detail.messages : []` and surfaces it through `messages`/`messagesStatus`, replacing the raw `detail.messages` dereference that could throw an unguarded `TypeError` escaping `loadChatPane` (regressing the step-004 pane-load contract). Root-cause fix at the single shared read site, so both the eager `loadChatPane` load and the pick flow are covered.

### Skeleton note — step 004 UI-shape choices (2026-07-26)

- **`ChatPaneSlot` kept as a one-line adapter**, not deleted. Intent allowed either; the adapter preserves the aside's stable render seam (`WorkspaceShell` → `ChatPaneSlot` → `ChatPane`) and lets the shell keep passing props to one aside child. The 010 "owned by 011.chat-panel" notice is gone.
- **`onShowChatList: () => void`** is a zero-arg callback: the intent's "show the list" is a pane-state reveal, and the pane already has `bookId`/`state`; no argument is needed. `WorkNavigator`'s body still renders the Chats entry as a link (010 behaviour) so DoD-5 stays red until the coder routes it to the control.
- **Temperature bounds are skeleton-owned:** `MIN_TEMPERATURE = 0` / `MAX_TEMPERATURE = 2` and `DEFAULT_TEMPERATURE = 0.8`. No DoD pins the numeric range (DoD-6 says only "within range"); flag if a different range is wanted. `modelOptionKey` encodes an option as `` `${server_id}::${model_name}` `` — an internal picker value, unpinned by any DoD.
- **The new-chat title lives on `NewChatDraft`, not in `ChatSettingsPanel`.** The panel edits only the shared `{ optionKey, temperature }` subset (used twice); the title input is the new-chat form's, per intent ("no other sampling param is rendered").
- **`api/chats.ts` bodies are thin `request<T>` forwarders** (not throwing stubs): `noUnusedLocals` forbids importing `request`/`BASE` unused, and the `api/books.ts` precedent is real one-liners. Every step-004 spec mocks `../../src/api/chats`, so these forwarders implement no DoD-asserted behaviour.

### Skeleton note — `ChatDetailResponse` introduced (2026-07-25)

The Interface intent enumerates a chat response, a chat list envelope, a message
response, a message list envelope, and the model-option pair — but names no wrapper
for the `GET /{book_id}/chats/{chat_id}` "chat + messages" return that DoD-4
requires. The skeleton introduced `ChatDetailResponse { chat: ChatResponse;
messages: list[ChatMessageResponse] }` as the minimal composition of two named
DTOs to give that endpoint a return type. `ChatMessageListResponse` (the named
"message list envelope") is also declared per intent; this step's routes do not
return it (it stands for step 003 / future message-listing). No behavior implied.

### Skeleton note — DTO field name `model_name` + `enable_thinking` default (2026-07-25)

DTOs use `model_name` (aligned with the `Chat` / `SubAgent` column) rather than the
`model` spelling of `EmbeddingConfigResponse`, guarded by
`model_config = ConfigDict(protected_namespaces=())` on the affected schemas — the
documented Pydantic fix, verified warning-free under `-W error::UserWarning`.
`ChatSamplingParams.enable_thinking` defaults to `True`: decision 6 lists it as
"carried" without a literal, and the feature persists/renders thinking by default,
so `True` is the reading; flag if a different default is intended.

### Skeleton note — step 002 naming and loose callable typing (2026-07-25)

- `WebSearchArgs`' optional result-count field is named `num_results` (default 5,
  bounds `ge=1, le=10` — the Custom Search per-request max). Intent named it only
  as "an optional result count with a sane bound"; the field name is load-bearing
  (it is a JSON-schema property and `web_search`'s keyword param), so it is frozen
  here — flag if a different wire name is wanted.
- `ToolDef.callable` is typed `Callable[..., object]` (not `Any`, not
  `Awaitable[str]`): loose per `context.md` so a future context-bearing tool bound
  by a closure / `functools.partial` and a sync-or-async callable both fit, while
  staying off `Any` per the backend no-untyped-data rule. `build_tool_bindings`
  returns `list[dict[str, object]]` for the OpenAI tool definitions, mirroring
  `db_import_export`'s `dict[str, object]` rows rather than the client's raw
  `dict[str, Any]` — same reason.
- `BASE_SYSTEM_PROMPT` is populated with a real non-empty string. No DoD pins its
  exact text (only non-emptiness), so the skeleton owns it as declarative content;
  the coder may refine the wording without touching the frozen signature.

### Skeleton note — step 003 turn split, error reuse, frame envelope (2026-07-25)

- **Two-function turn split.** Interface intent describes the orchestrator as an
  8-step whole, but DoD-8/DoD-10 require the pre-stream refusals to surface as
  ordinary HTTP status codes *before the first frame*, and the route text says it
  "calls the service for the pre-stream checks ... and only then returns a
  streaming SSE response." The skeleton froze that boundary as two service entry
  points: `prepare_turn(access, chat_id) -> TurnContext` (refusable resolution) and
  `run_turn(context, prompt) -> AsyncGenerator[TurnFrame]` (persist + stream). The
  route calls the first outside the stream (typed error → JSON), the second inside
  `StreamingResponse`. This is the only clean freeze consistent with both the
  numbered intent and the HTTP-error requirement.
- **"No model pair set" reuses `ChatErrorReason.invalid_model_pair` (→ 400).**
  `services/chats.py` is **not** a step-003 source file, so no new
  `ChatErrorReason` member could be minted; the existing `invalid_model_pair`
  (both-null is not a runnable pair) and `unknown_or_inactive_server` cover the
  intent's "no model pair set" / "server missing or inactive" refusals, both 400 as
  DoD-8 wants. The unset-key-env refusal stays `LlmServerError(env_not_set)` (→ 400)
  and is mapped by the new route helper — the route now catches `ChatError` **and**
  `LlmServerError` on the turn path.
- **`prepare_turn` reuses step-001 privates by design.** It is expected to call
  `chats_service._resolve_owned_chat` (and `_parse_chat_id`) so the 404-not-403
  ownership rule lives in exactly one place, and `db.llm_servers.get_by_id` +
  `secrets.resolve_env_ref` for the server/key — the `probe_models` precedent. No
  signature of those was changed.
- **Frame envelope vs. payloads.** The orchestrator yields `TurnFrame(event, data)`
  (a frozen dataclass in `chat_turn.py`); `data` is one of the four payload models
  in `schemas/chats.py` (`ThinkingFrame`/`DeltaFrame`/`DoneFrame`/`ErrorFrame`).
  The route serializes `event: <event>\ndata: <data.model_dump_json()>\n\n`, so the
  wire JSON of each `data:` line is exactly its payload model (no free dict). The
  frame *names* are frozen strings on the route; step 005 binds to them.
- **`ThinkSplitter.__init__` does not throw** (a stub whose constructor raised
  could not be instantiated for the DoD-1 tests); only `feed`/`flush` raise. The
  channel vocabulary is `"thinking"` / `"content"` (`Channel` literal), distinct
  from the frame names `thinking` / `delta` the orchestrator maps them to.

### Skeleton note — step 005 seams (2026-07-26)

- **`done`-frame payload is not reachable — the state reloads.** `sse.ts:streamPost`
  (frozen; NOT a step-005 source file) special-cases the `done` frame and calls its
  own `onDone?.()` with **no argument**, discarding the parsed `data`. So the step-003
  `DoneFrame.message` (the persisted assistant `ChatMessageResponse`) cannot flow
  through `streamChatTurn`. `TurnStreamHandlers.onDone` is therefore frozen as
  `() => void`, and the "replace the in-flight bubble with the persisted message"
  behaviour (context.md frame map, DoD-5) is achieved by the state **reloading** the
  chat's messages via the existing `chatsApi.getChat` on `done` — canonical, no
  duplicate/orphan. Documented on `TurnStreamHandlers` and `loadChatMessages`/
  `sendChatTurn`. No frozen code changed; not an escape valve (a clean freeze exists).
- **`onDone(): void` not `onDone(message)`.** Following from the above — surfacing a
  message param that would always be absent given the frozen `streamPost` would be
  misleading. Only `thinking` / `delta` payloads (via `streamPost.onEvent`) are
  narrowed in `chats.ts`; `done` carries nothing, so no `any` and no unused param.
- **`refreshAuthToken` is a real thin wrapper, not a throwing stub.** It shares the
  extracted `performTokenRefresh` with the on-401 retry (one refresh path, same
  `logout()` fallback), so implementing it changes no `request<T>` behaviour and pins
  no DoD — DoD-9 asserts `streamChatTurn` **awaits** it before the stream, and
  `streamChatTurn` throws, so the await-before-stream contract stays red.
- **Out of step-005 scope — `WorkspaceShell.tsx` is not a Source file.** Interface
  intent says "the shell's unmount cleanup calls `stop`", but `WorkspaceShell.tsx` is
  not in this step's Source files, so the skeleton did not touch it and the coder
  cannot wire the unmount-`stopChatTurn` there without a scope expansion. The shell's
  current unmount `ctrl.abort()` aborts the `loadChatPane` signal only, **not** the
  turn stream (which owns a separate `AbortController`). The "switching the active
  chat mid-stream" half of DoD-10 is reachable in-scope (`loadChatMessages` aborts the
  prior turn via `stopChatTurn`); the literal "unmounting aborts the stream" half needs
  `WorkspaceShell.tsx` added to scope. **Flagged for the orchestrator** — not a
  compile blocker.
- **Initial active-chat message load + auto-scroll left to the coder.** The pick
  handler in `ChatPane` was NOT wired to `loadChatMessages` (that call would throw in
  the stub phase and regress step-004's pick tests); the coder adds the message-load
  on pick and for the initially-resolved active chat (cleanly inside `loadChatPane` or
  the pick flow, both in-scope). Auto-scroll is optional / not DoD-pinned and was not
  scaffolded; if shipped it needs a pane-level mount `autorun`, which sits in tension
  with ChatPane's "no new effect" — coder's call, no leaf `useEffect`.
