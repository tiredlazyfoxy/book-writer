import { makeAutoObservable, runInAction } from "mobx";
import * as chatsApi from "../../../api/chats";
import { ApiError } from "../../../api/client";
import type {
  ChatMessageResponse,
  ChatResponse,
  ChatSamplingParams,
  CreateChatRequest,
  ModelOptionResponse,
  TurnSubject,
  UpdateChatRequest,
} from "../../../types/chats";
import {
  clearActiveChatId,
  readActiveChatId,
  writeActiveChatId,
} from "../../activeChat";
import {
  currentContentSelection,
  currentContentSubject,
  dispatchCanvasFrame,
} from "../../contentSubject";

/**
 * State for the chat pane (`ChatPane`), owned by `WorkspaceShell` via
 * `useState(() => new ChatPaneState())` and passed explicitly down the tree
 * (frontend.md — no React context). Two async-resource trios (chats,
 * model-options), the device-local active-chat pointer id, the archived-view
 * flag, the new-chat and settings drafts, a `serverErrors` map, and per-action
 * submit statuses.
 *
 * Per the MobX hard rules this class holds observable data + pure `get` computeds
 * ONLY — no effectful methods. Loading, picking, creating, archiving and
 * saving-settings live in the external `(state, …, signal)` functions below.
 *
 * SKELETON (011/004): observable fields + draft/computed shapes are frozen; the
 * getter bodies and the external effect-fn bodies throw for the coder to fill.
 */

/** The model-picker + temperature subset a `ChatSettingsPanel` edits. */
export interface ChatModelSettingsDraft {
  /** The chosen `(server, model)` option key ({@link modelOptionKey}), or none. */
  optionKey: string | null;
  temperature: number;
}

/** The new-chat draft — the settings subset plus a title. */
export interface NewChatDraft extends ChatModelSettingsDraft {
  title: string;
}

/**
 * One entry rendered by `MessageList`: a persisted message or the single in-flight
 * assistant bubble. `role` is the backend's free string (`"user"` / `"assistant"`).
 * `reasoning` is the assistant's thinking (`null` when there is none). `streaming`
 * marks the in-flight bubble, whose thinking expansion is driven by
 * `ChatPaneState.liveThinkingExpanded`; a persisted message uses
 * `ChatPaneState.expandedReasoning[key]` (collapsed by default).
 */
export interface RenderedMessage {
  /** Stable React key — the message id, or a fixed sentinel for the in-flight bubble. */
  key: string;
  role: string;
  content: string;
  reasoning: string | null;
  streaming: boolean;
}

/** Stable React key for the single in-flight assistant bubble (no persisted id yet). */
const STREAMING_MESSAGE_KEY = "__streaming__";

/** The temperature default and bounds surfaced by the picker (feature decision 6). */
export const DEFAULT_TEMPERATURE = 0.8;
export const MIN_TEMPERATURE = 0;
export const MAX_TEMPERATURE = 2;

/**
 * The default sampling set for a brand-new chat (feature decision 6). Only
 * `temperature` is overridden from the new-chat draft; the rest are the recommended
 * defaults the backend also carries. An existing chat's sampling is round-tripped
 * from its own stored values, NOT this constant (decision 4).
 */
const DEFAULT_SAMPLING: ChatSamplingParams = {
  temperature: DEFAULT_TEMPERATURE,
  top_p: 0.95,
  top_k: 40,
  repeat_penalty: 1.1,
  min_p: 0.05,
  max_tokens: null,
  seed: null,
  presence_penalty: 0,
  frequency_penalty: 0,
  enable_thinking: true,
};

/**
 * Canonical encoding of a `(server, model)` option as a single picker value.
 * Pure/structural (the `restoreBufferKey` precedent) — not the model pair itself,
 * which the create/update requests carry as `llm_server_id` + `model_name`.
 */
export function modelOptionKey(option: ModelOptionResponse): string {
  return `${option.server_id}::${option.model_name}`;
}

/** The picker key for a chat's stored `(server, model)` pair, or `null` if unset. */
function optionKeyForChat(chat: ChatResponse): string | null {
  if (chat.llm_server_id === null || chat.model_name === null) return null;
  return `${chat.llm_server_id}::${chat.model_name}`;
}

/** A chat's sort key — most-recently-modified first (created_at fallback, then 0). */
function chatTimestamp(chat: ChatResponse): number {
  const stamp = chat.modified_at ?? chat.created_at;
  if (stamp === null) return 0;
  const ms = Date.parse(stamp);
  return Number.isNaN(ms) ? 0 : ms;
}

/**
 * Resolve which chat should be active for a book: the stored device-local pointer
 * when it still names a non-archived chat, otherwise the most recent non-archived
 * chat by timestamp, otherwise none.
 */
function resolveActiveChatId(state: ChatPaneState, bookId: string): string | null {
  const active = state.chats.filter((c) => !c.archived);
  const stored = readActiveChatId(bookId);
  if (stored !== null && active.some((c) => c.id === stored)) return stored;
  if (active.length === 0) return null;
  const mostRecent = active
    .slice()
    .sort((a, b) => chatTimestamp(b) - chatTimestamp(a))[0];
  return mostRecent.id;
}

/** Seed the settings draft from the current active chat (model pair + temperature). */
function seedSettingsDraft(state: ChatPaneState): void {
  const chat = state.activeChat;
  if (chat === null) return;
  state.settingsDraft.optionKey = optionKeyForChat(chat);
  state.settingsDraft.temperature = chat.sampling.temperature;
}

export class ChatPaneState {
  chats: ChatResponse[] = [];
  chatsStatus: "idle" | "loading" | "ready" | "error" = "idle";
  chatsError: string | null = null;

  modelOptions: ModelOptionResponse[] = [];
  modelOptionsStatus: "idle" | "loading" | "ready" | "error" = "idle";
  modelOptionsError: string | null = null;

  /** The active-chat id (from the device-local pointer / fallback), or none. */
  activeChatId: string | null = null;
  /** Whether the list shows archived chats (restore view) instead of active ones. */
  showArchived = false;

  newChatDraft: NewChatDraft = {
    title: "",
    optionKey: null,
    temperature: DEFAULT_TEMPERATURE,
  };
  settingsDraft: ChatModelSettingsDraft = {
    optionKey: null,
    temperature: DEFAULT_TEMPERATURE,
  };

  /** Server-side refusal messages, keyed by field name or a general `form` key. */
  serverErrors: Record<string, string> = {};

  createStatus: "idle" | "loading" | "ready" | "error" = "idle";
  archiveStatus: "idle" | "loading" | "ready" | "error" = "idle";
  settingsStatus: "idle" | "loading" | "ready" | "error" = "idle";

  // --- Conversation half (step 005) ---

  /** The active chat's stored messages (position-ordered), an async-resource trio. */
  messages: ChatMessageResponse[] = [];
  messagesStatus: "idle" | "loading" | "ready" | "error" = "idle";
  messagesError: string | null = null;

  /** The in-flight turn's content buffer — `delta` frames appended as they arrive. */
  streamingContent = "";
  /** The in-flight turn's thinking buffer — `thinking` frames appended as they arrive. */
  streamingThinking = "";

  /** The current turn's lifecycle: idle, streaming, or failed. */
  turnStatus: "idle" | "streaming" | "error" = "idle";
  /** The failed turn's author-facing message (set when `turnStatus === "error"`). */
  turnError: string | null = null;

  /** Whether the LIVE (in-flight) thinking region is expanded (auto-collapses on the first delta). */
  liveThinkingExpanded = false;
  /** Per persisted-message reasoning expansion, keyed by message id (collapsed by default). */
  expandedReasoning: Record<string, boolean> = {};

  /** The composer's pending prompt text (cleared only once a send is accepted). */
  pendingPrompt = "";

  /** The live turn's abort handle — owned and returned by `streamPost` — or none. */
  turnController: AbortController | null = null;

  constructor() {
    makeAutoObservable(this);
  }

  /** The chats to show given `showArchived` — active list or the archived view. */
  get visibleChats(): ChatResponse[] {
    return this.chats
      .filter((c) => c.archived === this.showArchived)
      .slice()
      .sort((a, b) => chatTimestamp(b) - chatTimestamp(a));
  }

  /** The active chat object (resolved from `activeChatId`), or `null`. */
  get activeChat(): ChatResponse | null {
    if (this.activeChatId === null) return null;
    return this.chats.find((c) => c.id === this.activeChatId) ?? null;
  }

  /** Whether the new-chat draft can be submitted (a model chosen, temp in range). */
  get canCreateChat(): boolean {
    if (this.createStatus === "loading") return false;
    if (this.newChatDraft.optionKey === null) return false;
    const t = this.newChatDraft.temperature;
    return Number.isFinite(t) && t >= MIN_TEMPERATURE && t <= MAX_TEMPERATURE;
  }

  /** Merged client + server error map for the new-chat / settings surfaces. */
  get errors(): Record<string, string> {
    const client: Record<string, string> = {};
    const t = this.newChatDraft.temperature;
    if (!Number.isFinite(t) || t < MIN_TEMPERATURE || t > MAX_TEMPERATURE) {
      client.temperature = `Temperature must be between ${MIN_TEMPERATURE} and ${MAX_TEMPERATURE}.`;
    }
    // Server refusals override live client validation (the createBookDraft precedent).
    return { ...client, ...this.serverErrors };
  }

  /**
   * Whether the composer may submit: a non-empty (trimmed) `pendingPrompt`, a chat
   * active, and no turn already in flight.
   *
   * SKELETON (011/005): unimplemented — body throws.
   */
  get canSend(): boolean {
    return (
      this.pendingPrompt.trim() !== "" &&
      this.activeChat !== null &&
      this.turnStatus !== "streaming"
    );
  }

  /**
   * Whether a retry is offered — i.e. the last turn failed (`turnStatus === "error"`).
   *
   * SKELETON (011/005): unimplemented — body throws.
   */
  get retryOffered(): boolean {
    return this.turnStatus === "error";
  }

  /**
   * The rendered conversation sequence: the persisted `messages` mapped to
   * {@link RenderedMessage}, plus the single in-flight assistant bubble (fed from
   * `streamingContent` / `streamingThinking`) appended while a turn streams.
   *
   * SKELETON (011/005): unimplemented — body throws.
   */
  get renderedMessages(): RenderedMessage[] {
    const rendered: RenderedMessage[] = this.messages.map((m) => ({
      key: m.id,
      role: m.role,
      content: m.content,
      reasoning: m.reasoning,
      streaming: false,
    }));
    // The single in-flight assistant bubble, fed from the streaming buffers, is
    // appended only while a turn streams (it carries no persisted id yet).
    if (this.turnStatus === "streaming") {
      rendered.push({
        key: STREAMING_MESSAGE_KEY,
        role: "assistant",
        content: this.streamingContent,
        reasoning: this.streamingThinking === "" ? null : this.streamingThinking,
        streaming: true,
      });
    }
    return rendered;
  }
}

/**
 * Load the pane (unimplemented — coder fills). Intent: fetch the book's chats and
 * the model options into their trios, then resolve the active chat — the stored
 * pointer when it still names a visible chat, otherwise the most recent chat by
 * timestamp, otherwise none. Abort-guarded; an `ApiError` becomes an author-facing
 * message in the matching error trio, anything else rethrows.
 *
 * SKELETON: unimplemented — body throws.
 */
export async function loadChatPane(
  state: ChatPaneState,
  bookId: string,
  signal?: AbortSignal,
): Promise<void> {
  runInAction(() => {
    state.chatsStatus = "loading";
    state.chatsError = null;
    state.modelOptionsStatus = "loading";
    state.modelOptionsError = null;
  });

  try {
    const chats = await chatsApi.listChats(bookId, false, signal);
    if (signal?.aborted) return;
    runInAction(() => {
      state.chats = chats;
      state.chatsStatus = "ready";
      state.activeChatId = resolveActiveChatId(state, bookId);
      seedSettingsDraft(state);
    });
  } catch (err) {
    if (signal?.aborted) return;
    if (err instanceof ApiError) {
      runInAction(() => {
        state.chatsError = err.message;
        state.chatsStatus = "error";
      });
    } else {
      throw err;
    }
  }

  try {
    const options = await chatsApi.listModelOptions(bookId, signal);
    if (signal?.aborted) return;
    runInAction(() => {
      state.modelOptions = options;
      state.modelOptionsStatus = "ready";
    });
  } catch (err) {
    if (signal?.aborted) return;
    if (err instanceof ApiError) {
      runInAction(() => {
        state.modelOptionsError = err.message;
        state.modelOptionsStatus = "error";
      });
    } else {
      throw err;
    }
  }

  // Load the initially-resolved active chat's messages so the conversation renders
  // on mount (the pick flow loads on subsequent picks).
  if (!signal?.aborted && state.activeChatId !== null) {
    await loadChatMessages(state, bookId, state.activeChatId, signal);
  }
}

/**
 * Pick a chat (unimplemented — coder fills). Intent: set `state.activeChatId` and
 * write the device-local per-book pointer. Nothing navigates.
 *
 * SKELETON: unimplemented — body throws.
 */
export function pickChat(state: ChatPaneState, bookId: string, chatId: string): void {
  runInAction(() => {
    state.activeChatId = chatId;
    seedSettingsDraft(state);
  });
  writeActiveChatId(bookId, chatId);
}

/**
 * Create a chat from the new-chat draft (unimplemented — coder fills). Intent:
 * POST the draft's title / model pair / sampling, insert the new chat into the
 * list, make it active, write the pointer, reset the draft. Abort-guarded;
 * `ApiError` → `serverErrors`, else rethrow.
 *
 * SKELETON: unimplemented — body throws.
 */
export async function createChatFromDraft(
  state: ChatPaneState,
  bookId: string,
  signal?: AbortSignal,
): Promise<void> {
  const draft = state.newChatDraft;
  const option = state.modelOptions.find((o) => modelOptionKey(o) === draft.optionKey) ?? null;
  const title = draft.title.trim();
  const body: CreateChatRequest = {
    title: title === "" ? null : title,
    llm_server_id: option ? option.server_id : null,
    model_name: option ? option.model_name : null,
    sampling: { ...DEFAULT_SAMPLING, temperature: draft.temperature },
  };

  runInAction(() => {
    state.serverErrors = {};
    state.createStatus = "loading";
  });

  try {
    const created = await chatsApi.createChat(bookId, body, signal);
    if (signal?.aborted) return;
    runInAction(() => {
      state.chats = [created, ...state.chats];
      state.activeChatId = created.id;
      state.newChatDraft.title = "";
      state.newChatDraft.optionKey = null;
      state.newChatDraft.temperature = DEFAULT_TEMPERATURE;
      seedSettingsDraft(state);
      state.createStatus = "ready";
    });
    writeActiveChatId(bookId, created.id);
  } catch (err) {
    if (signal?.aborted) return;
    if (err instanceof ApiError) {
      runInAction(() => {
        state.serverErrors = { form: err.message || "Could not create the chat." };
        state.createStatus = "error";
      });
      return;
    }
    throw err;
  }
}

/**
 * Archive or restore a chat (unimplemented — coder fills). Intent: PATCH
 * `archived`, update the list, and when the archived chat was active re-resolve
 * the active chat rather than leaving a dangling pointer. Abort-guarded;
 * `ApiError` → an author-facing message, else rethrow.
 *
 * SKELETON: unimplemented — body throws.
 */
export async function setChatArchived(
  state: ChatPaneState,
  bookId: string,
  chatId: string,
  archived: boolean,
  signal?: AbortSignal,
): Promise<void> {
  runInAction(() => {
    state.chatsError = null;
    state.archiveStatus = "loading";
  });

  try {
    const updated = await chatsApi.updateChat(bookId, chatId, { archived }, signal);
    if (signal?.aborted) return;
    runInAction(() => {
      state.chats = state.chats.map((c) => (c.id === updated.id ? updated : c));
      state.archiveStatus = "ready";
      // Archiving the active chat must not leave a dangling pointer: re-resolve
      // against the just-updated list (the archived chat is no longer visible) and
      // rewrite/clear the device-local pointer to match.
      if (archived && state.activeChatId === chatId) {
        const next = resolveActiveChatId(state, bookId);
        state.activeChatId = next;
        seedSettingsDraft(state);
        if (next === null) clearActiveChatId(bookId);
        else writeActiveChatId(bookId, next);
      }
    });
  } catch (err) {
    if (signal?.aborted) return;
    if (err instanceof ApiError) {
      runInAction(() => {
        state.chatsError = err.message;
        state.archiveStatus = "error";
      });
      return;
    }
    throw err;
  }
}

/**
 * Save the active chat's settings (unimplemented — coder fills). Intent: PATCH the
 * active chat's model pair + sampling from `settingsDraft`, carrying every
 * non-temperature sampling param through from the loaded chat unchanged (decision
 * 4), and reflect the new values. Abort-guarded; `ApiError` → `serverErrors`,
 * else rethrow.
 *
 * SKELETON: unimplemented — body throws.
 */
export async function saveChatSettings(
  state: ChatPaneState,
  bookId: string,
  signal?: AbortSignal,
): Promise<void> {
  const chat = state.activeChat;
  if (chat === null) return;

  const option =
    state.modelOptions.find((o) => modelOptionKey(o) === state.settingsDraft.optionKey) ?? null;
  const body: UpdateChatRequest = {
    llm_server_id: option ? option.server_id : null,
    model_name: option ? option.model_name : null,
    // Only `temperature` is editable; every other stored param is carried through
    // from the loaded chat unchanged so an edit never silently resets it (decision 4).
    sampling: { ...chat.sampling, temperature: state.settingsDraft.temperature },
  };

  runInAction(() => {
    state.serverErrors = {};
    state.settingsStatus = "loading";
  });

  try {
    const updated = await chatsApi.updateChat(bookId, chat.id, body, signal);
    if (signal?.aborted) return;
    runInAction(() => {
      state.chats = state.chats.map((c) => (c.id === updated.id ? updated : c));
      seedSettingsDraft(state);
      state.settingsStatus = "ready";
    });
  } catch (err) {
    if (signal?.aborted) return;
    if (err instanceof ApiError) {
      runInAction(() => {
        state.serverErrors = { form: err.message || "Could not save settings." };
        state.settingsStatus = "error";
      });
      return;
    }
    throw err;
  }
}

/**
 * Load a chat's stored messages (unimplemented — coder fills). Intent: abort any
 * live turn (`stopChatTurn`) and reset the streaming buffers / turn status so no
 * stray in-flight text leaks onto the newly opened chat, then fetch
 * `chatsApi.getChat(bookId, chatId)` into the messages trio (position-ordered).
 * Abort-guarded; an `ApiError` becomes `messagesError`, anything else rethrows.
 *
 * SKELETON (011/005): unimplemented — body throws.
 */
export async function loadChatMessages(
  state: ChatPaneState,
  bookId: string,
  chatId: string,
  signal?: AbortSignal,
): Promise<void> {
  // Abort any live turn and reset the streaming/turn state so no stray in-flight
  // text from the previous chat leaks onto the newly opened one.
  stopChatTurn(state);
  runInAction(() => {
    state.messagesStatus = "loading";
    state.messagesError = null;
    state.turnStatus = "idle";
    state.turnError = null;
    state.streamingContent = "";
    state.streamingThinking = "";
    state.liveThinkingExpanded = false;
    state.expandedReasoning = {};
  });

  try {
    const detail = await chatsApi.getChat(bookId, chatId, signal);
    if (signal?.aborted) return;
    // A detail fetch that resolves without a payload object (or without a
    // messages array) must not throw: normalise to an empty transcript and
    // surface it through the messages trio like the sibling loads, so the
    // pane-load path can never abort on a missing/empty detail payload.
    const messages = Array.isArray(detail?.messages) ? detail.messages : [];
    runInAction(() => {
      state.messages = messages;
      state.messagesStatus = "ready";
    });
  } catch (err) {
    if (signal?.aborted) return;
    if (err instanceof ApiError) {
      runInAction(() => {
        state.messagesError = err.message;
        state.messagesStatus = "error";
      });
      return;
    }
    throw err;
  }
}

/**
 * The content pane's subject as the turn request's three wire fields, read from
 * `work/contentSubject.ts` at SEND time — never stored on `ChatPaneState`, which
 * has no subject field, so a turn sent after the author navigates carries the
 * subject they are looking at NOW (UC-083 / US-086.AC-1 / US-087.AC-1).
 *
 * `undefined` when nothing is registered, which posts exactly `{ prompt }` and
 * leaves `011.chat-panel`'s shipped behaviour untouched. A list subject maps to
 * its kind with a null id (UC-090 — a list is a subject too); a blank codex entry
 * maps to a null id with the `/codex/new?kind=` kind (UC-076).
 */
function turnSubject(): TurnSubject | undefined {
  const subject = currentContentSubject();
  if (subject === null) return undefined;
  return {
    subject_kind: subject.kind,
    subject_id: subject.entityId ?? null,
    codex_kind: subject.codexKind ?? null,
  };
}

/**
 * Send the author's prompt as a new turn (unimplemented — coder fills). Intent:
 * append the user message optimistically, clear the pending prompt (accepted) and
 * the streaming buffers, set `turnStatus = "streaming"`, open the stream via
 * `chatsApi.streamChatTurn(bookId, activeChat.id, text, handlers)` and store the
 * returned `AbortController` on `state.turnController`. The handlers append
 * `thinking` frames to `streamingThinking` and `delta` frames to `streamingContent`
 * through `runInAction` (the first `delta` auto-collapses `liveThinkingExpanded`);
 * `done` replaces the in-flight bubble with the persisted message (reloading, since
 * the frame payload is not forwarded) and re-enables the composer; `error` sets
 * `turnError` / `turnStatus = "error"`, preserving every prior message.
 *
 * SKELETON (011/005): unimplemented — body throws.
 */
export async function sendChatTurn(
  state: ChatPaneState,
  bookId: string,
  text: string,
): Promise<void> {
  const chat = state.activeChat;
  const prompt = text.trim();
  // A send with no active chat or an empty prompt is not accepted, so the composer
  // keeps the (possibly whitespace) text — a failed send never eats the input.
  if (chat === null || prompt === "") return;

  const optimistic: ChatMessageResponse = {
    id: `pending-user-${Date.now()}`,
    chat_id: chat.id,
    role: "user",
    content: prompt,
    reasoning: null,
    position: state.messages.length,
    created_at: null,
  };

  runInAction(() => {
    state.messages = [...state.messages, optimistic];
    // The send is accepted: clear the composer input now (not before).
    state.pendingPrompt = "";
    state.streamingContent = "";
    state.streamingThinking = "";
    state.liveThinkingExpanded = false;
    state.turnStatus = "streaming";
    state.turnError = null;
  });

  const controller = await chatsApi.streamChatTurn(
    bookId,
    chat.id,
    prompt,
    turnStreamHandlers(state, bookId, chat.id),
    // Read at SEND time, so the turn carries whatever the content pane is showing
    // right now — nothing about the subject is stored on the pane.
    turnSubject(),
    // The author's current selection, read from the SAME registry at the SAME
    // moment (015/012; D5). The pane holds no selection field either, and gains no
    // observer relationship to the content pane: the two stay independent because
    // nothing links them but this function call.
    currentContentSelection() ?? undefined,
  );
  runInAction(() => {
    state.turnController = controller;
  });
}

/**
 * Retry the failed turn (unimplemented — coder fills). Intent: open the SAME turn
 * stream with NO prompt (`streamChatTurn(bookId, activeChat.id, null, handlers)`),
 * so the already-persisted user message is neither re-sent nor duplicated, wiring
 * the same frame handlers as {@link sendChatTurn}.
 *
 * SKELETON (011/005): unimplemented — body throws.
 */
export async function retryChatTurn(state: ChatPaneState, bookId: string): Promise<void> {
  const chat = state.activeChat;
  if (chat === null) return;

  runInAction(() => {
    state.streamingContent = "";
    state.streamingThinking = "";
    state.liveThinkingExpanded = false;
    state.turnStatus = "streaming";
    state.turnError = null;
  });

  // Retry re-opens the SAME turn with NO prompt: the user message is already
  // persisted server-side, so nothing is re-sent or duplicated.
  const controller = await chatsApi.streamChatTurn(
    bookId,
    chat.id,
    null,
    turnStreamHandlers(state, bookId, chat.id),
    // Re-read at RETRY time too: the author may have navigated between the failed
    // send and the retry, and the retry must carry the current subject.
    turnSubject(),
    // The selection is re-read at RETRY time for the same reason and from the same
    // registry — the author may have selected, moved or cleared it since the failed
    // send (015/012).
    currentContentSelection() ?? undefined,
  );
  runInAction(() => {
    state.turnController = controller;
  });
}

/**
 * Stop the live turn (unimplemented — coder fills). Intent: abort
 * `state.turnController` (if any) and clear it; `streamPost` swallows the resulting
 * `AbortError`, so no error frame fires. Used when switching the active chat and by
 * the shell's unmount cleanup.
 *
 * SKELETON (011/005): unimplemented — body throws.
 */
export function stopChatTurn(state: ChatPaneState): void {
  if (state.turnController !== null) {
    // `streamPost` swallows the resulting `AbortError`, so no error frame fires.
    state.turnController.abort();
  }
  runInAction(() => {
    state.turnController = null;
    state.streamingContent = "";
    state.streamingThinking = "";
    state.liveThinkingExpanded = false;
    // A user-initiated stop re-enables the composer; an already-failed turn keeps
    // its error/retry surface.
    if (state.turnStatus === "streaming") {
      state.turnStatus = "idle";
      state.turnError = null;
    }
  });
}

/**
 * The frame handlers shared by {@link sendChatTurn} and {@link retryChatTurn},
 * all observable writes wrapped in `runInAction`:
 * - `thinking` — append to `streamingThinking`, keep the live region expanded;
 * - `delta` — append to `streamingContent`; the FIRST content delta of the turn
 *   auto-collapses the live thinking region (the author may re-expand it);
 * - `done` — reload the chat's messages once (the persisted assistant message does
 *   NOT arrive in the frame; `sse.ts:streamPost` discards the `done` payload),
 *   replacing the in-flight bubble with the stored message and re-enabling the composer;
 * - `error` — set `turnError` / `turnStatus = "error"`, preserving every prior message;
 * - `canvas` — hand the frame straight to `work/contentSubject.ts`'s dispatcher
 *   (013 step 013). The pane owns NO canvas state and no subject state: it neither
 *   inspects nor buffers the draft, and the registry decides between the open
 *   page's apply-draft callback and the restore-buffer fallback.
 */
function turnStreamHandlers(
  state: ChatPaneState,
  bookId: string,
  chatId: string,
): chatsApi.TurnStreamHandlers {
  return {
    onThinking: (text: string) => {
      runInAction(() => {
        state.streamingThinking += text;
        state.liveThinkingExpanded = true;
      });
    },
    onDelta: (text: string) => {
      runInAction(() => {
        // The first content delta collapses the live thinking region exactly once.
        if (state.streamingContent === "") state.liveThinkingExpanded = false;
        state.streamingContent += text;
      });
    },
    onDone: () => {
      void finishTurn(state, bookId, chatId);
    },
    onError: (message: string) => {
      runInAction(() => {
        state.turnStatus = "error";
        state.turnError = message || "The turn failed.";
        state.turnController = null;
      });
    },
    onCanvas: (frame) => {
      dispatchCanvasFrame(bookId, frame);
    },
  };
}

/**
 * Complete a streamed turn: reload the chat's persisted messages once (the `done`
 * frame payload is discarded by `streamPost`), then atomically swap them in and
 * clear the streaming bubble so there is exactly one persisted assistant message —
 * no duplicate and no orphaned in-flight bubble.
 */
async function finishTurn(state: ChatPaneState, bookId: string, chatId: string): Promise<void> {
  let reloaded: ChatMessageResponse[] | null = null;
  try {
    const detail = await chatsApi.getChat(bookId, chatId);
    reloaded = detail.messages;
  } catch {
    // Keep the optimistic transcript if the reload fails; the turn still completed.
    reloaded = null;
  }
  runInAction(() => {
    if (reloaded !== null) state.messages = reloaded;
    state.streamingContent = "";
    state.streamingThinking = "";
    state.liveThinkingExpanded = false;
    state.turnStatus = "idle";
    state.turnError = null;
    state.turnController = null;
  });
}
