import { request, refreshAuthToken } from "./client";
import { streamPost } from "./sse";
import type {
  CanvasFrame,
  CanvasOp,
  ChatDetailResponse,
  ChatResponse,
  ChatTitleResponse,
  CreateChatRequest,
  ModelOptionResponse,
  SubjectKind,
  ToolCallFrame,
  ToolResultFrame,
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
 * `POST /api/books/{bookId}/chats/{chatId}/title` (023) — run the chat's
 * auto-titling pass. **No body**: the trigger policy (title at exactly the 1st and
 * 5th user message) is the backend's, not the caller's, so this call carries no
 * arguments beyond the ids. Returns the chat's title afterwards plus whether the
 * pass changed it; a titling failure comes back as `changed: false`, never as an
 * error.
 *
 * Skeleton (023): signature frozen; the body is the same thin `request<T>`
 * forwarder every sibling in this module is (no branching, no computed value —
 * the module's own frozen-at-skeleton convention, and no DoD asserts it: every
 * spec mocks this module).
 */
export async function titleChat(
  bookId: string,
  chatId: string,
  signal?: AbortSignal,
): Promise<ChatTitleResponse> {
  return request<ChatTitleResponse>(`${BASE}/${bookId}/chats/${chatId}/title`, {
    method: "POST",
    signal,
  });
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
  /**
   * The assistant is about to invoke a tool (024). OPTIONAL, exactly like
   * `onCanvas`: every pre-024 caller stays valid and a caller with nowhere to show
   * a trace simply omits it. Reaches this interface through `sse.ts`'s EXISTING
   * generic-event routing — `sse.ts` is NOT modified.
   */
  onToolCall?: (frame: ToolCallFrame) => void;
  /** That tool has returned (024). Same optionality and same routing. */
  onToolResult?: (frame: ToolResultFrame) => void;
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
 * `selectionText` (`015` step 012) carries the text the author currently has selected
 * in the content pane onto the wire as `TurnRequest.selection_text` — a FIFTH FLAT
 * FIELD beside the three subject ones, NOT a member of `subject`: a selection is not
 * part of the subject's identity, and `TurnSubject` gains nothing (`015/context.md` →
 * D5). Its own parameter for the same reason. `undefined` / `null` means nothing is
 * selected, and the key is then ABSENT from the posted body — a turn with a subject and
 * no selection posts exactly the four fields `013` posted. The caller
 * (`chatPaneState`) reads it from `work/contentSubject.ts`'s selection registry at SEND
 * time, in the same call site that already reads the subject; this module never imports
 * from an entry's domain modules.
 *
 * SEAM (deliberate — documented per the step): `streamPost` OWNS and RETURNS its
 * own `AbortController` and takes NO `signal`, so this one api function breaks the
 * repo's trailing-`signal` convention. The caller `await`s the returned controller,
 * stores it, and cancels via an explicit stop rather than passing a signal in. NO
 * `signal` parameter is added; `selectionText` simply takes the trailing position
 * `subject` used to hold.
 */
export async function streamChatTurn(
  bookId: string,
  chatId: string,
  prompt: string | null,
  handlers: TurnStreamHandlers,
  subject?: TurnSubject,
  selectionText?: string | null,
): Promise<AbortController> {
  // DoD-9: renew a possibly-stale access token BEFORE opening the stream, since
  // `streamPost` uses raw `fetch` + `authHeaders()` and never re-enters `client.ts`'s
  // on-401 silent refresh. Awaited first so the stream opens with a fresh token.
  await refreshAuthToken();

  // The three subject fields ride along only when the caller supplied them, so a
  // turn sent with nothing registered posts exactly `{ prompt }`. The selection is a
  // FIFTH FLAT FIELD beside them, added when and only when there IS one: a turn with
  // a subject and no selection posts exactly the four fields `013` posted, with no
  // `selection_text` key at all.
  const body: TurnRequest = {
    prompt,
    ...subject,
    ...(selectionText === undefined || selectionText === null
      ? {}
      : { selection_text: selectionText }),
  };

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
        } else if (event === "tool_call") {
          // 024: same shape as the `canvas` branch above — generic routing in,
          // narrowed here, a malformed payload DROPPED rather than forwarded.
          const frame = toolCallFrame(data);
          if (frame !== null) handlers.onToolCall?.(frame);
        } else if (event === "tool_result") {
          const frame = toolResultFrame(data);
          if (frame !== null) handlers.onToolResult?.(frame);
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
 *
 * `op` (`015` step 012) is CARRIED THROUGH. It has to be: this narrowing REBUILDS the
 * frame field by field, so an `op` dropped here would make every frame arriving over a
 * live stream read as a whole-body replace, silently degrading `add_text` and
 * `update_selection` and defeating the chapter canvas protocol on the only path that
 * matters — the real one. An absent `op` is left absent, which is exactly how the DTO
 * expresses the backend's `"replace"` default (`dispatchCanvasFrame` applies it in the
 * single place it belongs), so a codex frame is rebuilt with the same shape it has
 * always had.
 */
function canvasFrame(data: unknown): CanvasFrame | null {
  if (data === null || typeof data !== "object") return null;
  const raw = data as {
    subject_kind?: unknown;
    subject_id?: unknown;
    field?: unknown;
    text?: unknown;
    op?: unknown;
  };

  const subjectKind = raw.subject_kind;
  const subjectId = raw.subject_id;
  const field = raw.field;
  const text = raw.text;
  const op = raw.op;

  if (typeof subjectKind !== "string") return null;
  if (subjectId !== null && typeof subjectId !== "string") return null;
  if (field !== "name" && field !== "body") return null;
  if (typeof text !== "string") return null;

  // ABSENT (or explicitly null) is the backend's `"replace"` default, expressed the
  // way the DTO expresses it: the optional field is simply left off, and
  // `dispatchCanvasFrame` applies the default in the single place it belongs. A
  // recognised value is carried through. Anything else is MALFORMED and the frame is
  // dropped like any other malformed frame — reading an unknown operation as
  // `"replace"` would be exactly the silent whole-body overwrite this protocol exists
  // to refuse.
  let resolvedOp: CanvasOp | undefined;
  if (op === undefined || op === null) {
    resolvedOp = undefined;
  } else if (op === "replace" || op === "append" || op === "replace_selection") {
    resolvedOp = op;
  } else {
    return null;
  }

  return {
    // The backend validates `subject_kind` against its own literal union at the
    // schema boundary, so the wire value is taken as the kind it declares.
    subject_kind: subjectKind as SubjectKind,
    subject_id: subjectId,
    field,
    text,
    ...(resolvedOp === undefined ? {} : { op: resolvedOp }),
  };
}

/**
 * Narrow a raw `tool_call` `data: unknown` payload to a {@link ToolCallFrame}, or
 * `null` when it is not one (024).
 *
 * Mirrors {@link canvasFrame}'s discipline EXACTLY: narrow field by field from
 * `unknown` and return `null` — dropping the whole frame — on any type mismatch or
 * missing required field. A bad or absent field is NEVER defaulted; a malformed
 * frame is invisible, not partially rendered.
 *
 * `arguments` must be a non-null, non-array object; `tool_name` must be a string.
 */
function toolCallFrame(data: unknown): ToolCallFrame | null {
  if (data === null || typeof data !== "object") return null;
  const raw = data as { tool_name?: unknown; arguments?: unknown };

  const toolName = raw.tool_name;
  const args = raw.arguments;

  if (typeof toolName !== "string") return null;
  // An ARRAY is `typeof "object"` too, and `null` is as well — neither is an
  // arguments map. An ABSENT `arguments` is malformed, not "no arguments": a
  // tool called with none still carries `{}` on the wire, so defaulting here
  // would invent a call shape the backend never sent.
  if (args === null || typeof args !== "object" || Array.isArray(args)) return null;

  return { tool_name: toolName, arguments: args as Record<string, unknown> };
}

/**
 * Narrow a raw `tool_result` `data: unknown` payload to a {@link ToolResultFrame},
 * or `null` when it is not one (024). Same drop-on-mismatch discipline as
 * {@link toolCallFrame}: `tool_name` and `result` must be strings and `ok` must be
 * a boolean, or the whole frame is dropped.
 *
 * Both `result: ""` and `ok: false` are FALSY BUT VALID — a tool legitimately
 * returns nothing, and a failed call is exactly what `ok: false` reports — so
 * every check here is a `typeof` test, never a truthiness one.
 */
function toolResultFrame(data: unknown): ToolResultFrame | null {
  if (data === null || typeof data !== "object") return null;
  const raw = data as { tool_name?: unknown; result?: unknown; ok?: unknown };

  const toolName = raw.tool_name;
  const result = raw.result;
  const ok = raw.ok;

  if (typeof toolName !== "string") return null;
  if (typeof result !== "string") return null;
  if (typeof ok !== "boolean") return null;

  return { tool_name: toolName, result, ok };
}

/** Narrow a raw `thinking` / `delta` `data: unknown` payload to its `text` chunk. */
function frameText(data: unknown): string {
  if (data !== null && typeof data === "object" && "text" in data) {
    const text = (data as { text: unknown }).text;
    if (typeof text === "string") return text;
  }
  return "";
}
