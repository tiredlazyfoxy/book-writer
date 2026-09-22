/**
 * Side-chat actions — 027.side-chats / 005.side-chat-actions-state,
 * DoD-1 · DoD-2 · DoD-3 · DoD-4 · DoD-5 · DoD-6 · DoD-7 · DoD-8 · DoD-9 · DoD-10 · DoD-11.
 *
 * A state-only spec (no rendering): construct `ChatPaneState`, seed via `runInAction`
 * (`chats` with `active_side_chat_id`, `activeChatId`, `messages` with `side_chat_id`,
 * `messagesStatus`, `turnStatus`, and — for the close-turn case — the plain observable
 * `closeTurnActive`), mock `../../src/api/chats` wholesale, resolve / reject each api
 * function per case, `await` the effect, then assert on the state and on the mock's
 * call arguments (`context.md` -> "Shared frontend facts", "Testing facts").
 *
 * Bound to the frozen step-005 skeleton (status.md -> `## Skeleton`):
 *   ChatPaneState.sideChatActionStatus: "idle" | "busy" | "error"
 *   ChatPaneState.sideChatActionError: string | null
 *   ChatPaneState.sideChatDeleteConfirm: string | null
 *   get sideChatActionsEnabled(): boolean
 *   get canStartSideChat(): boolean
 *   get canFinishSideChat(): boolean
 *   startSideChat(state, bookId, signal?): Promise<void>
 *   finishSideChat(state, bookId, signal?): Promise<void>
 *   injectSideChat(state, bookId, sideChatId, signal?): Promise<void>
 *   deleteSideChat(state, bookId, sideChatId, signal?): Promise<void>
 *   requestDeleteSideChat(state, sideChatId): void
 *   dismissDeleteSideChat(state): void
 * and step 004's `activeSideChatId` / `renderedTranscript`; the api side is step 004's
 *   chatsApi.startSideChat(bookId, chatId, signal?): Promise<ChatResponse>
 *   chatsApi.finishSideChat(bookId, chatId, sideChatId, signal?): Promise<ChatResponse>
 *   chatsApi.injectSideChat(bookId, chatId, sideChatId, signal?): Promise<ChatDetailResponse>
 *   chatsApi.deleteSideChat(bookId, chatId, sideChatId, signal?): Promise<void>
 *   chatsApi.getChat(bookId, chatId, signal?): Promise<ChatDetailResponse>
 *
 * Expected values come from the spec (`005.md` Interface intent + DoD; `context.md`
 * D-D "product D1 is client-side", D-F "backend is the source of truth"), never from code:
 *   - `sideChatActionsEnabled` is false with no active chat, while streaming, while a
 *     close turn is active, or while the action status is busy; true otherwise (D1);
 *   - `canStartSideChat` = enabled && no side chat active; `canFinishSideChat` =
 *     enabled && a side chat active (UC-110 / UC-111 preconditions);
 *   - every effect calls its api with the active chat id, then shows what the server
 *     returned: `chats` patched by id, `messages` swapped whole (D-F);
 *   - `finishSideChat` leaves `messages` alone — the group turns finished through
 *     `renderedTranscript` only (US-137.AC-1);
 *   - `deleteSideChat` reloads through `getChat` and clears the confirmation slot on
 *     success and on error (US-140.AC-3);
 *   - an `ApiError` is swallowed into the trio (`error` + message), `chats` / `messages`
 *     untouched; any other rejection propagates (D-F);
 *   - while busy every computed is false and no effect reaches the api (D1).
 *
 * `globals: false`: every primitive is imported explicitly.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { runInAction } from "mobx";
import { ApiError } from "../../src/api/client";
import type {
  ChatDetailResponse,
  ChatMessageResponse,
  ChatResponse,
  ChatSamplingParams,
} from "../../src/types/chats";
import type {
  RenderedTranscriptItem,
  RenderedTranscriptSideChatItem,
} from "../../src/work/components/chat/chatPaneState";
import {
  ChatPaneState,
  deleteSideChat,
  dismissDeleteSideChat,
  finishSideChat,
  injectSideChat,
  requestDeleteSideChat,
  startSideChat,
} from "../../src/work/components/chat/chatPaneState";

// The api module the state layer imports: whole-module factory, EVERY export enumerated
// (the step-004 list — the four side-chat functions and `getChat` included).
vi.mock("../../src/api/chats", () => ({
  listChats: vi.fn(),
  createChat: vi.fn(),
  updateChat: vi.fn(),
  getChat: vi.fn(),
  listModelOptions: vi.fn(),
  titleChat: vi.fn(),
  startSideChat: vi.fn(),
  finishSideChat: vi.fn(),
  injectSideChat: vi.fn(),
  deleteSideChat: vi.fn(),
  streamChatTurn: vi.fn(),
}));

import * as chatsApi from "../../src/api/chats";

const BOOK_ID = "bk-1";
const CHAT_ID = "c-1";
const SIDE_A = "sc-A";
const SIDE_B = "sc-B";

function makeSampling(): ChatSamplingParams {
  return {
    temperature: 0.8,
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
}

function makeChat(activeSideChatId: string | null, id: string = CHAT_ID): ChatResponse {
  return {
    id,
    book_id: BOOK_ID,
    author_id: "u-1",
    title: "Chat one",
    llm_server_id: "s-1",
    model_name: "m-1",
    sampling: makeSampling(),
    archived: false,
    created_at: "2026-01-01T00:00:00Z",
    modified_at: "2026-01-01T00:00:00Z",
    active_side_chat_id: activeSideChatId,
  };
}

function makeMessage(
  id: string,
  position: number,
  sideChatId: string | null,
  role: string = position % 2 === 0 ? "user" : "assistant",
): ChatMessageResponse {
  return {
    id,
    chat_id: CHAT_ID,
    role,
    content: `content of ${id}`,
    reasoning: null,
    position,
    created_at: "2026-01-01T00:00:00Z",
    side_chat_id: sideChatId,
    tool_trace: null,
  };
}

/**
 * Build a position-ordered message list from a shorthand: each entry is the
 * `side_chat_id` of that row (`null` = main line). Ids are `m-0`, `m-1`, … in order.
 */
function messagesFrom(shape: Array<string | null>): ChatMessageResponse[] {
  return shape.map((sideChatId, index) => makeMessage(`m-${index}`, index, sideChatId));
}

/** Seed an active chat with a ready message history and an idle turn. */
function seed(
  state: ChatPaneState,
  messages: ChatMessageResponse[],
  activeSideChatId: string | null,
  turnStatus: "idle" | "streaming" = "idle",
): void {
  runInAction(() => {
    state.chats = [makeChat(activeSideChatId)];
    state.activeChatId = CHAT_ID;
    state.messages = messages;
    state.messagesStatus = "ready";
    state.turnStatus = turnStatus;
    state.turnError = null;
    state.streamingContent = "";
    state.streamingThinking = "";
  });
}

/** Narrow a transcript item to a group, failing loudly if it is not one. */
function asGroup(item: RenderedTranscriptItem): RenderedTranscriptSideChatItem {
  expect(item.kind).toBe("sideChat");
  if (item.kind !== "sideChat") throw new Error("expected a sideChat item");
  return item;
}

/** The `kind` sequence of a transcript. */
function kindsOf(items: RenderedTranscriptItem[]): string[] {
  return items.map((item) => item.kind);
}

/** The active chat's entry in `state.chats`, or fail loudly. */
function activeChatEntry(state: ChatPaneState): ChatResponse {
  const entry = state.chats.find((c) => c.id === CHAT_ID);
  if (entry === undefined) throw new Error("active chat missing from state.chats");
  return entry;
}

/** Total number of api calls across the five functions the effects may reach. */
function apiCallCount(): number {
  return (
    vi.mocked(chatsApi.startSideChat).mock.calls.length +
    vi.mocked(chatsApi.finishSideChat).mock.calls.length +
    vi.mocked(chatsApi.injectSideChat).mock.calls.length +
    vi.mocked(chatsApi.deleteSideChat).mock.calls.length +
    vi.mocked(chatsApi.getChat).mock.calls.length
  );
}

beforeEach(() => {
  vi.resetAllMocks();
});

describe("canStartSideChat (DoD-1)", () => {
  it("DoD-1: canStartSideChat is true with an active chat whose active_side_chat_id is null, an idle turn, no close turn and status idle (UC-110 precondition)", () => {
    const state = new ChatPaneState();
    seed(state, messagesFrom([null, null]), null);

    expect(state.sideChatActionStatus).toBe("idle");
    expect(state.closeTurnActive).toBeNull();
    expect(state.canStartSideChat).toBe(true);
  });

  it("DoD-1: canStartSideChat is false when the active chat's active_side_chat_id is set (US-135.AC-2)", () => {
    const state = new ChatPaneState();
    seed(state, messagesFrom([null, SIDE_A]), SIDE_A);

    expect(state.sideChatActionsEnabled).toBe(true);
    expect(state.canStartSideChat).toBe(false);
  });
});

describe("canStartSideChat while streaming (DoD-2)", () => {
  it("DoD-2: canStartSideChat is false while turnStatus === 'streaming' (US-135.AC-3)", () => {
    const state = new ChatPaneState();
    seed(state, messagesFrom([null]), null, "streaming");

    expect(state.canStartSideChat).toBe(false);
  });
});

describe("canFinishSideChat (DoD-3)", () => {
  it("DoD-3: canFinishSideChat is true when the active chat's active_side_chat_id is set and actions are enabled (UC-111 precondition)", () => {
    const state = new ChatPaneState();
    seed(state, messagesFrom([null, SIDE_A]), SIDE_A);

    expect(state.sideChatActionsEnabled).toBe(true);
    expect(state.canFinishSideChat).toBe(true);
  });

  it("DoD-3: canFinishSideChat is false when no side chat is active", () => {
    const state = new ChatPaneState();
    seed(state, messagesFrom([null]), null);

    expect(state.sideChatActionsEnabled).toBe(true);
    expect(state.canFinishSideChat).toBe(false);
  });

  it("DoD-3: canFinishSideChat is false while streaming even though a side chat is active (UC-111 exception flow)", () => {
    const state = new ChatPaneState();
    seed(state, messagesFrom([null, SIDE_A]), SIDE_A, "streaming");

    expect(state.canFinishSideChat).toBe(false);
  });
});

describe("sideChatActionsEnabled — D1 on the client (DoD-4)", () => {
  it("DoD-4: sideChatActionsEnabled is false while closeTurnActive !== null (UC-112 / UC-113 exception flows)", () => {
    const state = new ChatPaneState();
    seed(state, messagesFrom([null]), null);
    runInAction(() => {
      state.closeTurnActive = { bookId: BOOK_ID, chapterId: "ch-1" };
    });

    expect(state.sideChatActionsEnabled).toBe(false);
    expect(state.canStartSideChat).toBe(false);
  });

  it("DoD-4: sideChatActionsEnabled is false while sideChatActionStatus === 'busy'", () => {
    const state = new ChatPaneState();
    seed(state, messagesFrom([null]), null);
    runInAction(() => {
      state.sideChatActionStatus = "busy";
    });

    expect(state.sideChatActionsEnabled).toBe(false);
  });

  it("DoD-4: sideChatActionsEnabled is false when there is no active chat", () => {
    const state = new ChatPaneState();
    runInAction(() => {
      state.chats = [makeChat(null)];
      state.activeChatId = null;
      state.messages = [];
      state.messagesStatus = "ready";
      state.turnStatus = "idle";
    });

    expect(state.sideChatActionsEnabled).toBe(false);
    expect(state.canStartSideChat).toBe(false);
    expect(state.canFinishSideChat).toBe(false);
  });

  it("DoD-4: sideChatActionsEnabled is false while streaming", () => {
    const state = new ChatPaneState();
    seed(state, messagesFrom([null]), null, "streaming");

    expect(state.sideChatActionsEnabled).toBe(false);
  });

  it("DoD-4: sideChatActionsEnabled is true with an active chat, an idle turn, no close turn and status idle — and stays true after an error", () => {
    const state = new ChatPaneState();
    seed(state, messagesFrom([null]), null);

    expect(state.sideChatActionsEnabled).toBe(true);

    // 'error' is not 'busy': the gate reopens so the author can retry.
    runInAction(() => {
      state.sideChatActionStatus = "error";
      state.sideChatActionError = "Side chat already active.";
    });
    expect(state.sideChatActionsEnabled).toBe(true);
  });
});

describe("startSideChat (DoD-5)", () => {
  it("DoD-5: startSideChat calls the start api once with the book id and the active chat id; afterwards activeSideChatId is the returned chat's active_side_chat_id and the status is idle (UC-110 steps 1-2)", async () => {
    const state = new ChatPaneState();
    seed(state, messagesFrom([null, null]), null);
    vi.mocked(chatsApi.startSideChat).mockResolvedValue(makeChat(SIDE_A));

    await startSideChat(state, BOOK_ID);

    expect(vi.mocked(chatsApi.startSideChat)).toHaveBeenCalledTimes(1);
    const [bookArg, chatArg] = vi.mocked(chatsApi.startSideChat).mock.calls[0];
    expect(bookArg).toBe(BOOK_ID);
    expect(chatArg).toBe(CHAT_ID);

    expect(state.activeSideChatId).toBe(SIDE_A);
    expect(activeChatEntry(state).active_side_chat_id).toBe(SIDE_A);
    expect(state.sideChatActionStatus).toBe("idle");
    expect(state.sideChatActionError).toBeNull();
    expect(state.canStartSideChat).toBe(false);
    expect(state.canFinishSideChat).toBe(true);
  });

  it("DoD-5: startSideChat forwards the signal it was given to the api", async () => {
    const state = new ChatPaneState();
    seed(state, messagesFrom([null]), null);
    vi.mocked(chatsApi.startSideChat).mockResolvedValue(makeChat(SIDE_A));
    const controller = new AbortController();

    await startSideChat(state, BOOK_ID, controller.signal);

    expect(vi.mocked(chatsApi.startSideChat)).toHaveBeenCalledTimes(1);
    expect(vi.mocked(chatsApi.startSideChat).mock.calls[0][2]).toBe(controller.signal);
  });

  it("DoD-5: startSideChat leaves the message list alone — starting adds no rows", async () => {
    const state = new ChatPaneState();
    const messages = messagesFrom([null, null]);
    seed(state, messages, null);
    vi.mocked(chatsApi.startSideChat).mockResolvedValue(makeChat(SIDE_A));

    await startSideChat(state, BOOK_ID);

    expect(state.messages.slice()).toEqual(messages);
  });

  it("DoD-5: startSideChat calls no api when a side chat is already active (canStartSideChat false)", async () => {
    const state = new ChatPaneState();
    seed(state, messagesFrom([null, SIDE_A]), SIDE_A);

    await startSideChat(state, BOOK_ID);

    expect(vi.mocked(chatsApi.startSideChat)).not.toHaveBeenCalled();
    expect(state.activeSideChatId).toBe(SIDE_A);
    expect(state.sideChatActionStatus).toBe("idle");
  });
});

describe("finishSideChat (DoD-6)", () => {
  it("DoD-6: finishSideChat calls the finish api with the current activeSideChatId; afterwards activeSideChatId is null, messages are the same content, and the former group renders active: false, expanded: false (US-137.AC-1)", async () => {
    const state = new ChatPaneState();
    const messages = messagesFrom([null, SIDE_A, SIDE_A]);
    seed(state, messages, SIDE_A);
    vi.mocked(chatsApi.finishSideChat).mockResolvedValue(makeChat(null));

    // Before: the group is the active one.
    expect(asGroup(state.renderedTranscript[1]).active).toBe(true);
    expect(asGroup(state.renderedTranscript[1]).expanded).toBe(true);

    await finishSideChat(state, BOOK_ID);

    expect(vi.mocked(chatsApi.finishSideChat)).toHaveBeenCalledTimes(1);
    const [bookArg, chatArg, sideArg] = vi.mocked(chatsApi.finishSideChat).mock.calls[0];
    expect(bookArg).toBe(BOOK_ID);
    expect(chatArg).toBe(CHAT_ID);
    expect(sideArg).toBe(SIDE_A);

    expect(state.activeSideChatId).toBeNull();
    expect(activeChatEntry(state).active_side_chat_id).toBeNull();
    expect(state.sideChatActionStatus).toBe("idle");
    expect(state.sideChatActionError).toBeNull();

    // Messages are untouched — same array content, side_chat_id stamps intact.
    expect(state.messages.slice()).toEqual(messages);

    const items = state.renderedTranscript;
    expect(kindsOf(items)).toEqual(["message", "sideChat"]);
    const group = asGroup(items[1]);
    expect(group.sideChatId).toBe(SIDE_A);
    expect(group.messages.map((m) => m.key)).toEqual(["m-1", "m-2"]);
    expect(group.active).toBe(false);
    expect(group.expanded).toBe(false);
  });

  it("DoD-6: finishSideChat forwards the signal it was given to the api", async () => {
    const state = new ChatPaneState();
    seed(state, messagesFrom([null, SIDE_A]), SIDE_A);
    vi.mocked(chatsApi.finishSideChat).mockResolvedValue(makeChat(null));
    const controller = new AbortController();

    await finishSideChat(state, BOOK_ID, controller.signal);

    expect(vi.mocked(chatsApi.finishSideChat).mock.calls[0][3]).toBe(controller.signal);
  });

  it("DoD-6: finishSideChat calls no api when no side chat is active (canFinishSideChat false)", async () => {
    const state = new ChatPaneState();
    seed(state, messagesFrom([null]), null);

    await finishSideChat(state, BOOK_ID);

    expect(vi.mocked(chatsApi.finishSideChat)).not.toHaveBeenCalled();
    expect(state.sideChatActionStatus).toBe("idle");
  });
});

describe("injectSideChat (DoD-7)", () => {
  it("DoD-7: injectSideChat calls the inject api with the given id; afterwards messages equal the response's (every formerly grouped row side_chat_id null) and renderedTranscript shows them as message items in order (US-139.AC-1)", async () => {
    const state = new ChatPaneState();
    seed(state, messagesFrom([null, SIDE_A, SIDE_A, null]), null);
    const detail: ChatDetailResponse = {
      chat: makeChat(null),
      messages: messagesFrom([null, null, null, null]),
    };
    vi.mocked(chatsApi.injectSideChat).mockResolvedValue(detail);

    // Before: a finished group sits in the middle.
    expect(kindsOf(state.renderedTranscript)).toEqual(["message", "sideChat", "message"]);

    await injectSideChat(state, BOOK_ID, SIDE_A);

    expect(vi.mocked(chatsApi.injectSideChat)).toHaveBeenCalledTimes(1);
    const [bookArg, chatArg, sideArg] = vi.mocked(chatsApi.injectSideChat).mock.calls[0];
    expect(bookArg).toBe(BOOK_ID);
    expect(chatArg).toBe(CHAT_ID);
    expect(sideArg).toBe(SIDE_A);

    expect(state.messages.slice()).toEqual(detail.messages);
    expect(state.messages.every((m) => m.side_chat_id === null)).toBe(true);
    expect(activeChatEntry(state)).toEqual(detail.chat);
    expect(state.sideChatActionStatus).toBe("idle");
    expect(state.sideChatActionError).toBeNull();

    const items = state.renderedTranscript;
    expect(kindsOf(items)).toEqual(["message", "message", "message", "message"]);
    expect(
      items.map((item) => (item.kind === "message" ? item.message.key : item.sideChatId)),
    ).toEqual(["m-0", "m-1", "m-2", "m-3"]);
  });

  it("DoD-7: injecting the ACTIVE side chat also clears activeSideChatId from the response's chat", async () => {
    const state = new ChatPaneState();
    seed(state, messagesFrom([null, SIDE_A, SIDE_A]), SIDE_A);
    const detail: ChatDetailResponse = {
      chat: makeChat(null),
      messages: messagesFrom([null, null, null]),
    };
    vi.mocked(chatsApi.injectSideChat).mockResolvedValue(detail);

    await injectSideChat(state, BOOK_ID, SIDE_A);

    expect(state.activeSideChatId).toBeNull();
    expect(kindsOf(state.renderedTranscript)).toEqual(["message", "message", "message"]);
  });

  it("DoD-7: injectSideChat forwards the signal it was given to the api", async () => {
    const state = new ChatPaneState();
    seed(state, messagesFrom([SIDE_A]), null);
    vi.mocked(chatsApi.injectSideChat).mockResolvedValue({
      chat: makeChat(null),
      messages: messagesFrom([null]),
    });
    const controller = new AbortController();

    await injectSideChat(state, BOOK_ID, SIDE_A, controller.signal);

    expect(vi.mocked(chatsApi.injectSideChat).mock.calls[0][3]).toBe(controller.signal);
  });
});

describe("deleteSideChat (DoD-8)", () => {
  it("DoD-8: deleteSideChat calls the delete api once and then getChat once; afterwards messages equal the reload's, chats carries the reloaded chat, and sideChatDeleteConfirm is null (US-140.AC-3)", async () => {
    const state = new ChatPaneState();
    seed(state, messagesFrom([null, SIDE_A, SIDE_A, null]), null);
    requestDeleteSideChat(state, SIDE_A);
    expect(state.sideChatDeleteConfirm).toBe(SIDE_A);

    const reloaded: ChatDetailResponse = {
      chat: { ...makeChat(null), modified_at: "2026-02-02T00:00:00Z" },
      messages: [makeMessage("m-0", 0, null), makeMessage("m-3", 3, null)],
    };
    vi.mocked(chatsApi.deleteSideChat).mockResolvedValue(undefined);
    vi.mocked(chatsApi.getChat).mockResolvedValue(reloaded);

    await deleteSideChat(state, BOOK_ID, SIDE_A);

    expect(vi.mocked(chatsApi.deleteSideChat)).toHaveBeenCalledTimes(1);
    const [bookArg, chatArg, sideArg] = vi.mocked(chatsApi.deleteSideChat).mock.calls[0];
    expect(bookArg).toBe(BOOK_ID);
    expect(chatArg).toBe(CHAT_ID);
    expect(sideArg).toBe(SIDE_A);

    expect(vi.mocked(chatsApi.getChat)).toHaveBeenCalledTimes(1);
    const [reloadBook, reloadChat] = vi.mocked(chatsApi.getChat).mock.calls[0];
    expect(reloadBook).toBe(BOOK_ID);
    expect(reloadChat).toBe(CHAT_ID);

    expect(state.messages.slice()).toEqual(reloaded.messages);
    expect(state.messages.map((m) => m.id)).toEqual(["m-0", "m-3"]);
    expect(activeChatEntry(state)).toEqual(reloaded.chat);
    expect(state.sideChatDeleteConfirm).toBeNull();
    expect(state.sideChatActionStatus).toBe("idle");
    expect(state.sideChatActionError).toBeNull();
    expect(kindsOf(state.renderedTranscript)).toEqual(["message", "message"]);
  });

  it("DoD-8: deleting the ACTIVE side chat leaves activeSideChatId null from the reloaded chat", async () => {
    const state = new ChatPaneState();
    seed(state, messagesFrom([null, SIDE_A]), SIDE_A);
    requestDeleteSideChat(state, SIDE_A);
    vi.mocked(chatsApi.deleteSideChat).mockResolvedValue(undefined);
    vi.mocked(chatsApi.getChat).mockResolvedValue({
      chat: makeChat(null),
      messages: messagesFrom([null]),
    });

    await deleteSideChat(state, BOOK_ID, SIDE_A);

    expect(state.activeSideChatId).toBeNull();
    expect(state.messages.map((m) => m.id)).toEqual(["m-0"]);
    expect(state.sideChatDeleteConfirm).toBeNull();
  });

  it("DoD-8: deleteSideChat forwards the signal it was given to both the delete and the reload", async () => {
    const state = new ChatPaneState();
    seed(state, messagesFrom([SIDE_A]), null);
    vi.mocked(chatsApi.deleteSideChat).mockResolvedValue(undefined);
    vi.mocked(chatsApi.getChat).mockResolvedValue({ chat: makeChat(null), messages: [] });
    const controller = new AbortController();

    await deleteSideChat(state, BOOK_ID, SIDE_A, controller.signal);

    expect(vi.mocked(chatsApi.deleteSideChat).mock.calls[0][3]).toBe(controller.signal);
    expect(vi.mocked(chatsApi.getChat).mock.calls[0][2]).toBe(controller.signal);
  });
});

describe("requestDeleteSideChat / dismissDeleteSideChat (DoD-9)", () => {
  it("DoD-9: requestDeleteSideChat sets sideChatDeleteConfirm to the given id and calls no api (US-140.AC-1)", () => {
    const state = new ChatPaneState();
    seed(state, messagesFrom([null, SIDE_A]), null);
    expect(state.sideChatDeleteConfirm).toBeNull();

    requestDeleteSideChat(state, SIDE_A);

    expect(state.sideChatDeleteConfirm).toBe(SIDE_A);
    expect(apiCallCount()).toBe(0);
  });

  it("DoD-9: dismissDeleteSideChat sets sideChatDeleteConfirm back to null, calls no api, and leaves messages and chats unchanged (US-140.AC-2)", () => {
    const state = new ChatPaneState();
    seed(state, messagesFrom([null, SIDE_A, SIDE_A]), null);
    requestDeleteSideChat(state, SIDE_A);
    const messagesBefore = state.messages;
    const chatsBefore = state.chats;
    const snapshot = state.messages.slice();

    dismissDeleteSideChat(state);

    expect(state.sideChatDeleteConfirm).toBeNull();
    expect(apiCallCount()).toBe(0);
    expect(state.messages).toBe(messagesBefore);
    expect(state.chats).toBe(chatsBefore);
    expect(state.messages.slice()).toEqual(snapshot);
    expect(state.messages).toHaveLength(3);
    expect(kindsOf(state.renderedTranscript)).toEqual(["message", "sideChat"]);
  });

  it("DoD-9: a second request replaces the pending id rather than stacking", () => {
    const state = new ChatPaneState();
    seed(state, messagesFrom([SIDE_A, null, SIDE_B]), null);

    requestDeleteSideChat(state, SIDE_A);
    requestDeleteSideChat(state, SIDE_B);

    expect(state.sideChatDeleteConfirm).toBe(SIDE_B);
    expect(apiCallCount()).toBe(0);
  });
});

describe("ApiError is swallowed into the trio; anything else propagates (DoD-10)", () => {
  const REFUSAL = "Side chat already active.";

  it("DoD-10: startSideChat on an ApiError sets status 'error' and the error's message, chats / messages untouched (D-F)", async () => {
    const state = new ChatPaneState();
    seed(state, messagesFrom([null]), null);
    const messagesBefore = state.messages;
    const chatsBefore = state.chats;
    vi.mocked(chatsApi.startSideChat).mockRejectedValue(new ApiError(409, REFUSAL));

    await startSideChat(state, BOOK_ID);

    expect(state.sideChatActionStatus).toBe("error");
    expect(state.sideChatActionError).toBe(REFUSAL);
    expect(state.messages).toBe(messagesBefore);
    expect(state.chats).toBe(chatsBefore);
    expect(state.activeSideChatId).toBeNull();
  });

  it("DoD-10: finishSideChat on an ApiError sets status 'error' and the error's message, chats / messages untouched", async () => {
    const state = new ChatPaneState();
    seed(state, messagesFrom([null, SIDE_A]), SIDE_A);
    const messagesBefore = state.messages;
    const chatsBefore = state.chats;
    vi.mocked(chatsApi.finishSideChat).mockRejectedValue(
      new ApiError(409, "Side chat is not the active one."),
    );

    await finishSideChat(state, BOOK_ID);

    expect(state.sideChatActionStatus).toBe("error");
    expect(state.sideChatActionError).toBe("Side chat is not the active one.");
    expect(state.messages).toBe(messagesBefore);
    expect(state.chats).toBe(chatsBefore);
    expect(state.activeSideChatId).toBe(SIDE_A);
  });

  it("DoD-10: injectSideChat on an ApiError sets status 'error' and the error's message, chats / messages untouched", async () => {
    const state = new ChatPaneState();
    seed(state, messagesFrom([null, SIDE_A, SIDE_A]), null);
    const messagesBefore = state.messages;
    const chatsBefore = state.chats;
    vi.mocked(chatsApi.injectSideChat).mockRejectedValue(new ApiError(404, "Side chat not found."));

    await injectSideChat(state, BOOK_ID, SIDE_A);

    expect(state.sideChatActionStatus).toBe("error");
    expect(state.sideChatActionError).toBe("Side chat not found.");
    expect(state.messages).toBe(messagesBefore);
    expect(state.chats).toBe(chatsBefore);
    expect(kindsOf(state.renderedTranscript)).toEqual(["message", "sideChat"]);
  });

  it("DoD-10: deleteSideChat on an ApiError sets status 'error' and the error's message, chats / messages untouched, no reload, and the confirmation slot is cleared", async () => {
    const state = new ChatPaneState();
    seed(state, messagesFrom([null, SIDE_A, SIDE_A]), null);
    requestDeleteSideChat(state, SIDE_A);
    const messagesBefore = state.messages;
    const chatsBefore = state.chats;
    vi.mocked(chatsApi.deleteSideChat).mockRejectedValue(new ApiError(404, "Side chat not found."));

    await deleteSideChat(state, BOOK_ID, SIDE_A);

    expect(state.sideChatActionStatus).toBe("error");
    expect(state.sideChatActionError).toBe("Side chat not found.");
    expect(state.messages).toBe(messagesBefore);
    expect(state.chats).toBe(chatsBefore);
    expect(state.messages).toHaveLength(3);
    expect(vi.mocked(chatsApi.getChat)).not.toHaveBeenCalled();
    expect(state.sideChatDeleteConfirm).toBeNull();
  });

  it("DoD-10: a non-ApiError rejection from startSideChat propagates", async () => {
    const state = new ChatPaneState();
    seed(state, messagesFrom([null]), null);
    vi.mocked(chatsApi.startSideChat).mockRejectedValue(new Error("boom"));

    await expect(startSideChat(state, BOOK_ID)).rejects.toThrow("boom");
  });

  it("DoD-10: a non-ApiError rejection from finishSideChat propagates", async () => {
    const state = new ChatPaneState();
    seed(state, messagesFrom([null, SIDE_A]), SIDE_A);
    vi.mocked(chatsApi.finishSideChat).mockRejectedValue(new Error("boom"));

    await expect(finishSideChat(state, BOOK_ID)).rejects.toThrow("boom");
  });

  it("DoD-10: a non-ApiError rejection from injectSideChat propagates", async () => {
    const state = new ChatPaneState();
    seed(state, messagesFrom([SIDE_A]), null);
    vi.mocked(chatsApi.injectSideChat).mockRejectedValue(new Error("boom"));

    await expect(injectSideChat(state, BOOK_ID, SIDE_A)).rejects.toThrow("boom");
  });

  it("DoD-10: a non-ApiError rejection from deleteSideChat propagates", async () => {
    const state = new ChatPaneState();
    seed(state, messagesFrom([SIDE_A]), null);
    requestDeleteSideChat(state, SIDE_A);
    vi.mocked(chatsApi.deleteSideChat).mockRejectedValue(new Error("boom"));

    await expect(deleteSideChat(state, BOOK_ID, SIDE_A)).rejects.toThrow("boom");
    expect(vi.mocked(chatsApi.getChat)).not.toHaveBeenCalled();
  });
});

describe("the busy window gates every computed and every effect (DoD-11)", () => {
  it("DoD-11: while startSideChat is in flight the status is 'busy', the three computeds are false, and a second call to any effect calls no api (D1)", async () => {
    const state = new ChatPaneState();
    seed(state, messagesFrom([null, SIDE_A, SIDE_A, null]), null);
    // Never resolves: the action stays in its busy window for the whole test.
    vi.mocked(chatsApi.startSideChat).mockReturnValue(new Promise<ChatResponse>(() => {}));

    const pending = startSideChat(state, BOOK_ID);
    void pending;

    expect(state.sideChatActionStatus).toBe("busy");
    expect(state.sideChatActionsEnabled).toBe(false);
    expect(state.canStartSideChat).toBe(false);
    expect(state.canFinishSideChat).toBe(false);
    expect(vi.mocked(chatsApi.startSideChat)).toHaveBeenCalledTimes(1);
    const before = apiCallCount();

    await startSideChat(state, BOOK_ID);
    await finishSideChat(state, BOOK_ID);
    await injectSideChat(state, BOOK_ID, SIDE_A);
    await deleteSideChat(state, BOOK_ID, SIDE_A);

    expect(apiCallCount()).toBe(before);
    expect(vi.mocked(chatsApi.startSideChat)).toHaveBeenCalledTimes(1);
    expect(vi.mocked(chatsApi.finishSideChat)).not.toHaveBeenCalled();
    expect(vi.mocked(chatsApi.injectSideChat)).not.toHaveBeenCalled();
    expect(vi.mocked(chatsApi.deleteSideChat)).not.toHaveBeenCalled();
    expect(vi.mocked(chatsApi.getChat)).not.toHaveBeenCalled();
    expect(state.sideChatActionStatus).toBe("busy");
  });

  it("DoD-11: while finishSideChat is in flight with a side chat active, both can… computeds are false and a second finish calls no api", async () => {
    const state = new ChatPaneState();
    seed(state, messagesFrom([null, SIDE_A]), SIDE_A);
    vi.mocked(chatsApi.finishSideChat).mockReturnValue(new Promise<ChatResponse>(() => {}));

    void finishSideChat(state, BOOK_ID);

    expect(state.sideChatActionStatus).toBe("busy");
    expect(state.sideChatActionsEnabled).toBe(false);
    expect(state.canStartSideChat).toBe(false);
    expect(state.canFinishSideChat).toBe(false);

    await finishSideChat(state, BOOK_ID);
    await injectSideChat(state, BOOK_ID, SIDE_A);
    await deleteSideChat(state, BOOK_ID, SIDE_A);

    expect(vi.mocked(chatsApi.finishSideChat)).toHaveBeenCalledTimes(1);
    expect(vi.mocked(chatsApi.injectSideChat)).not.toHaveBeenCalled();
    expect(vi.mocked(chatsApi.deleteSideChat)).not.toHaveBeenCalled();
  });

  it("DoD-11: a seeded 'busy' status alone makes every effect a no-op at the api", async () => {
    const state = new ChatPaneState();
    seed(state, messagesFrom([null, SIDE_A]), null);
    runInAction(() => {
      state.sideChatActionStatus = "busy";
    });

    await startSideChat(state, BOOK_ID);
    await finishSideChat(state, BOOK_ID);
    await injectSideChat(state, BOOK_ID, SIDE_A);
    await deleteSideChat(state, BOOK_ID, SIDE_A);

    expect(apiCallCount()).toBe(0);
  });
});
