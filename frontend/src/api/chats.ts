import { request, refreshAuthToken } from "./client";
import { streamPost } from "./sse";
import type {
  ChatDetailResponse,
  ChatResponse,
  CreateChatRequest,
  ModelOptionResponse,
  UpdateChatRequest,
} from "../types/chats";

// Chat resource module (author-owned `/api/books/{book_id}/chats` surface). All
// JSON HTTP goes through `client.request` (which injects Bearer when a token
// exists). Namespace-imported by callers (`import * as chatsApi from
// "../../../api/chats"`); `signal?` is always the trailing arg. The `{book_id}` /
// `{chat_id}` paths interpolate the STRING snowflake id directly. One `PATCH`
// (`updateChat`) serves archive, restore and settings alike.
//
// Skeleton (011/004): exact signatures frozen. Bodies are thin `request<T>`
// forwarders (the `api/books.ts` precedent) — no behaviour a DoD asserts, since
// every spec mocks this module. The list envelopes (`{ items: [...] }`) are NOT
// modelled in `types/chats.d.ts`; they are unwrapped here at the call.

const BASE = "/api/books";

/**
 * `GET /api/books/{bookId}/chats?archived=<flag>` — the caller's own chats for a
 * book, most-recently-modified first. Unwraps `.items` from the list envelope.
 */
export async function listChats(
  bookId: string,
  archived: boolean,
  signal?: AbortSignal,
): Promise<ChatResponse[]> {
  const res = await request<{ items: ChatResponse[] }>(
    `${BASE}/${bookId}/chats?archived=${archived}`,
    { signal },
  );
  return res.items;
}

/** `POST /api/books/{bookId}/chats` — create a chat; returns the new chat. */
export async function createChat(
  bookId: string,
  body: CreateChatRequest,
  signal?: AbortSignal,
): Promise<ChatResponse> {
  return request<ChatResponse>(`${BASE}/${bookId}/chats`, { method: "POST", body, signal });
}

/**
 * `PATCH /api/books/{bookId}/chats/{chatId}` — update a chat (title / archived /
 * model pair / sampling); the single call behind archive, restore and settings.
 * Returns the updated chat.
 */
export async function updateChat(
  bookId: string,
  chatId: string,
  body: UpdateChatRequest,
  signal?: AbortSignal,
): Promise<ChatResponse> {
  return request<ChatResponse>(`${BASE}/${bookId}/chats/${chatId}`, {
    method: "PATCH",
    body,
    signal,
  });
}

/**
 * `GET /api/books/{bookId}/chats/{chatId}` — one chat plus its position-ordered
 * messages.
 */
export async function getChat(
  bookId: string,
  chatId: string,
  signal?: AbortSignal,
): Promise<ChatDetailResponse> {
  return request<ChatDetailResponse>(`${BASE}/${bookId}/chats/${chatId}`, { signal });
}

/**
 * `GET /api/books/{bookId}/chats/model-options` — the author-visible
 * `(server, model)` options. Unwraps `.items` from the list envelope.
 */
export async function listModelOptions(
  bookId: string,
  signal?: AbortSignal,
): Promise<ModelOptionResponse[]> {
  const res = await request<{ items: ModelOptionResponse[] }>(
    `${BASE}/${bookId}/chats/model-options`,
    { signal },
  );
  return res.items;
}

/**
 * Typed callbacks for the four turn-stream frames, narrowed from `streamPost`'s
 * raw `unknown` payloads so no `any` reaches the state layer:
 * - `onThinking` / `onDelta` carry the frame's text chunk (both arrive via
 *   `streamPost`'s `onEvent` as `data: unknown` and are narrowed to `{ text }` here);
 * - `onDone` signals the terminal `done` frame. NOTE: `sse.ts:streamPost` calls its
 *   own `onDone()` with NO payload, so the `done` frame's persisted-message DTO does
 *   NOT flow through here — the state layer obtains the persisted message by
 *   reloading the chat (`chatPaneState.loadChatMessages`), not from this callback;
 * - `onError` carries the failure message.
 */
export interface TurnStreamHandlers {
  onThinking: (text: string) => void;
  onDelta: (text: string) => void;
  onDone: () => void;
  onError: (message: string) => void;
}

/**
 * Open the streaming turn for a chat — `POST {book}/chats/{chat}/turn` read as SSE.
 * Awaits `refreshAuthToken()` FIRST (DoD-9): `streamPost` uses raw `fetch` +
 * `authHeaders()` and never triggers `client.ts`'s on-401 silent refresh, so a
 * stale access token must be renewed before the stream opens. `prompt` is the
 * author's text for a fresh turn, or `null` for a retry (the user message is
 * already persisted server-side, so nothing is re-sent). Dispatches each frame to
 * `handlers`, narrowing the `thinking` / `delta` `data: unknown` payloads to
 * `{ text }`.
 *
 * SEAM (deliberate — documented per the step): `streamPost` OWNS and RETURNS its
 * own `AbortController` and takes NO `signal`, so this one api function breaks the
 * repo's trailing-`signal` convention. The caller `await`s the returned controller,
 * stores it, and cancels via an explicit stop rather than passing a signal in.
 *
 * SKELETON (011/005): signature frozen; body throws so DoD-9's await-before-stream
 * stays red until the coder fills it.
 */
export async function streamChatTurn(
  bookId: string,
  chatId: string,
  prompt: string | null,
  handlers: TurnStreamHandlers,
): Promise<AbortController> {
  // DoD-9: renew a possibly-stale access token BEFORE opening the stream, since
  // `streamPost` uses raw `fetch` + `authHeaders()` and never re-enters `client.ts`'s
  // on-401 silent refresh. Awaited first so the stream opens with a fresh token.
  await refreshAuthToken();

  // `streamPost` owns and returns its own `AbortController` (no `signal` in); the
  // caller stores the returned controller and cancels via an explicit stop.
  return streamPost(
    `${BASE}/${bookId}/chats/${chatId}/turn`,
    { prompt },
    {
      onEvent: (event, data) => {
        // `thinking` / `delta` both arrive via `onEvent` with `data: unknown`;
        // narrow to the frame's text here so no `any` reaches the state layer.
        if (event === "thinking") handlers.onThinking(frameText(data));
        else if (event === "delta") handlers.onDelta(frameText(data));
      },
      onDone: () => handlers.onDone(),
      onError: (message) => handlers.onError(message),
    },
  );
}

/** Narrow a raw `thinking` / `delta` `data: unknown` payload to its `text` chunk. */
function frameText(data: unknown): string {
  if (data !== null && typeof data === "object" && "text" in data) {
    const text = (data as { text: unknown }).text;
    if (typeof text === "string") return text;
  }
  return "";
}
