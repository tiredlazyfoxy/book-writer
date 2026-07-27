import { request, refreshAuthToken } from "./client";
import { streamPost } from "./sse";
import type {
  CanvasFrame,
  ChatDetailResponse,
  ChatResponse,
  CreateChatRequest,
  ModelOptionResponse,
  SubjectKind,
  TurnRequest,
  TurnSubject,
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
 * - `onError` carries the failure message;
 * - `onCanvas` carries the assistant's shared-canvas draft (013 step 010/013).
 *   OPTIONAL: `011.chat-panel`'s four-handler callers stay valid, and a caller
 *   that has no canvas target simply omits it. It reaches this interface through
 *   `sse.ts`'s EXISTING generic-event routing — `sse.ts` is NOT modified.
 */
export interface TurnStreamHandlers {
  onThinking: (text: string) => void;
  onDelta: (text: string) => void;
  onDone: () => void;
  onError: (message: string) => void;
  onCanvas?: (frame: CanvasFrame) => void;
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
 * `subject` (013 step 013) carries the content pane's current subject onto the
 * wire — the three optional fields of `TurnRequest`, supplied together or not at
 * all. OMITTED when no content subject is registered, in which case the posted
 * body is exactly `{ prompt }` and `011.chat-panel`'s shipped behaviour is
 * unchanged. The caller (`chatPaneState`) reads the subject from
 * `work/contentSubject.ts` at SEND time and maps it to these wire fields; this
 * module never imports from an entry's domain modules.
 *
 * SEAM (deliberate — documented per the step): `streamPost` OWNS and RETURNS its
 * own `AbortController` and takes NO `signal`, so this one api function breaks the
 * repo's trailing-`signal` convention. The caller `await`s the returned controller,
 * stores it, and cancels via an explicit stop rather than passing a signal in.
 * `subject` is therefore the trailing argument, and NO `signal` parameter is added.
 */
export async function streamChatTurn(
  bookId: string,
  chatId: string,
  prompt: string | null,
  handlers: TurnStreamHandlers,
  subject?: TurnSubject,
): Promise<AbortController> {
  // DoD-9: renew a possibly-stale access token BEFORE opening the stream, since
  // `streamPost` uses raw `fetch` + `authHeaders()` and never re-enters `client.ts`'s
  // on-401 silent refresh. Awaited first so the stream opens with a fresh token.
  await refreshAuthToken();

  // The three subject fields ride along only when the caller supplied them, so a
  // turn sent with nothing registered posts exactly `{ prompt }`.
  const body: TurnRequest = { prompt, ...subject };

  // `streamPost` owns and returns its own `AbortController` (no `signal` in); the
  // caller stores the returned controller and cancels via an explicit stop.
  return streamPost(
    `${BASE}/${bookId}/chats/${chatId}/turn`,
    body,
    {
      onEvent: (event, data) => {
        // `thinking` / `delta` both arrive via `onEvent` with `data: unknown`;
        // narrow to the frame's text here so no `any` reaches the state layer.
        if (event === "thinking") handlers.onThinking(frameText(data));
        else if (event === "delta") handlers.onDelta(frameText(data));
        else if (event === "canvas") {
          // `canvas` reaches us through `sse.ts`'s EXISTING generic-event routing
          // (any name that is not `done` / `error` goes to `onEvent`), so `sse.ts`
          // is unmodified. A malformed payload is dropped, never forwarded.
          const frame = canvasFrame(data);
          if (frame !== null) handlers.onCanvas?.(frame);
        }
      },
      onDone: () => handlers.onDone(),
      onError: (message) => handlers.onError(message),
    },
  );
}

/**
 * Narrow a raw `canvas` `data: unknown` payload to a {@link CanvasFrame}, or
 * `null` when it is not one — so no untyped payload reaches the state layer and a
 * malformed frame is dropped rather than dispatched. `subject_id` is
 * required-but-nullable: an ABSENT id is malformed, only an explicit `null` is
 * UC-076's blank entry.
 */
function canvasFrame(data: unknown): CanvasFrame | null {
  if (data === null || typeof data !== "object") return null;
  const raw = data as {
    subject_kind?: unknown;
    subject_id?: unknown;
    field?: unknown;
    text?: unknown;
  };

  const subjectKind = raw.subject_kind;
  const subjectId = raw.subject_id;
  const field = raw.field;
  const text = raw.text;

  if (typeof subjectKind !== "string") return null;
  if (subjectId !== null && typeof subjectId !== "string") return null;
  if (field !== "name" && field !== "body") return null;
  if (typeof text !== "string") return null;

  return {
    // The backend validates `subject_kind` against its own literal union at the
    // schema boundary, so the wire value is taken as the kind it declares.
    subject_kind: subjectKind as SubjectKind,
    subject_id: subjectId,
    field,
    text,
  };
}

/** Narrow a raw `thinking` / `delta` `data: unknown` payload to its `text` chunk. */
function frameText(data: unknown): string {
  if (data !== null && typeof data === "object" && "text" in data) {
    const text = (data as { text: unknown }).text;
    if (typeof text === "string") return text;
  }
  return "";
}
