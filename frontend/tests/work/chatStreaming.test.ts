/**
 * Chat conversation — state-level streaming — 011.chat-panel / 005,
 * DoD-2 · DoD-3 · DoD-5 · DoD-6 · DoD-7 · DoD-8 · DoD-9 · DoD-10.
 *
 * Bound to the frozen step-005 skeleton (status.md -> `## Skeleton`):
 *   interface RenderedMessage { key; role; content; reasoning; streaming }
 *   ChatPaneState fields: messages/messagesStatus/messagesError;
 *     streamingContent; streamingThinking; turnStatus ("idle"|"streaming"|"error");
 *     turnError; liveThinkingExpanded; expandedReasoning; pendingPrompt; turnController
 *   get canSend; get retryOffered; get renderedMessages
 *   loadChatMessages(state, bookId, chatId, signal?): Promise<void>
 *   sendChatTurn(state, bookId, text): Promise<void>
 *   retryChatTurn(state, bookId): Promise<void>
 *   stopChatTurn(state): void
 *   api/chats: streamChatTurn(bookId, chatId, prompt: string | null, handlers): Promise<AbortController>
 *              getChat(bookId, chatId, signal?): Promise<ChatDetailResponse>
 *   api/client: refreshAuthToken(): Promise<void>   api/sse: streamPost(url, body, handlers): AbortController
 *
 * The air gap: expected values come from the spec (`005.md` DoD, `005.context.md`
 * frame->state map, feature `context.md` decisions 7/8, UC-054 / US-058 / UC-056 /
 * US-060), never from code. `../../src/api/chats` is mocked module-factory form
 * (never `fetch`); `onDone` carries no payload, so `done` is realized by a `getChat`
 * reload. DoD-9 is the api module's OWN seam: the real `streamChatTurn` is exercised
 * (via `importActual`) against a mocked `refreshAuthToken` (client) + `streamPost`
 * (sse) to assert refresh-before-stream ordering. `globals: false`.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { runInAction } from "mobx";
import type {
  ChatMessageResponse,
  ChatResponse,
  ChatSamplingParams,
} from "../../src/types/chats";
import * as chatsApi from "../../src/api/chats";
import * as client from "../../src/api/client";
import * as sse from "../../src/api/sse";
import {
  ChatPaneState,
  loadChatMessages,
  retryChatTurn,
  sendChatTurn,
  stopChatTurn,
} from "../../src/work/components/chat/chatPaneState";
import { installTurnStream } from "../support/sseFixture";

// The api module the state layer sees: whole-module factory, every export enumerated.
// `titleChat` added by 023.chat-ux-revision: the post-turn title refresh is fired
// fire-and-forget from the module-private `finishTurn`, so a `done` frame reaches this
// export. MOCK COMPLETENESS ONLY — it exists so the call cannot explode; nothing in
// this file asserts on it, and no assertion here changed.
vi.mock("../../src/api/chats", () => ({
  listChats: vi.fn(),
  createChat: vi.fn(),
  updateChat: vi.fn(),
  getChat: vi.fn(),
  listModelOptions: vi.fn(),
  streamChatTurn: vi.fn(),
  titleChat: vi.fn(),
}));

// Below `api/chats` for the DoD-9 seam only: the real `streamChatTurn` awaits the
// refresh entry point, then calls `streamPost`. Both are stubbed so the ordering is
// observable. (The state-layer tests never reach these — they use mocked `api/chats`.)
vi.mock("../../src/api/sse", () => ({
  streamPost: vi.fn(() => new AbortController()),
}));
vi.mock("../../src/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../src/api/client")>();
  return { ...actual, refreshAuthToken: vi.fn(async () => {}) };
});

const BOOK_ID = "bk-1";
const CHAT_ID = "c-1";

function makeSampling(overrides: Partial<ChatSamplingParams> = {}): ChatSamplingParams {
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
    ...overrides,
  };
}

function makeChat(
  id: string = CHAT_ID,
  title = "Chat one",
  modifiedAt = "2026-01-01T00:00:00Z",
): ChatResponse {
  return {
    id,
    book_id: BOOK_ID,
    author_id: "u-1",
    title,
    llm_server_id: "s-1",
    model_name: "m-1",
    sampling: makeSampling(),
    archived: false,
    created_at: modifiedAt,
    modified_at: modifiedAt,
  };
}

function makeMessage(
  id: string,
  role: string,
  content: string,
  position: number,
  reasoning: string | null = null,
): ChatMessageResponse {
  return {
    id,
    chat_id: CHAT_ID,
    role,
    content,
    reasoning,
    position,
    created_at: "2026-01-01T00:00:00Z",
  };
}

const CHAT = makeChat();

/** Seed an active chat with a ready (possibly empty) message history and an idle turn. */
function primeActiveChat(state: ChatPaneState, messages: ChatMessageResponse[] = []): void {
  runInAction(() => {
    state.chats = [CHAT];
    state.activeChatId = CHAT_ID;
    state.messages = messages;
    state.messagesStatus = "ready";
    state.turnStatus = "idle";
    state.turnError = null;
    state.streamingContent = "";
    state.streamingThinking = "";
  });
}

beforeEach(() => {
  // `restoreMocks` wipes implementations between tests — give `getChat` a benign default.
  vi.mocked(chatsApi.getChat).mockResolvedValue({ chat: CHAT, messages: [] });
  // 023: the fire-and-forget post-turn title refresh resolves benignly (title
  // unchanged), so it can never leave a rejected promise behind a `done` frame. Not
  // asserted anywhere; these specs stay insensitive to its timing.
  vi.mocked(chatsApi.titleChat).mockResolvedValue({ title: CHAT.title, changed: false });
});

describe("sending a prompt streams content deltas incrementally (DoD-2)", () => {
  it("DoD-2: the author's message shows immediately and the assistant bubble grows across delta frames (UC-054, US-058.AC-1)", async () => {
    const state = new ChatPaneState();
    primeActiveChat(state, []);
    const fixture = installTurnStream(vi.mocked(chatsApi.streamChatTurn));

    await sendChatTurn(state, BOOK_ID, "Write me a poem");

    // The author's just-sent message is present immediately, before any assistant frame.
    expect(
      state.renderedMessages.some((m) => m.role === "user" && m.content === "Write me a poem"),
    ).toBe(true);

    // Fire deltas ONE AT A TIME and observe the in-flight bubble grow — not appear whole at the end.
    fixture.delta("Roses");
    expect(state.renderedMessages.find((m) => m.streaming)?.content).toBe("Roses");

    fixture.delta(" are red");
    expect(state.renderedMessages.find((m) => m.streaming)?.content).toBe("Roses are red");

    fixture.delta(" and blue");
    expect(state.renderedMessages.find((m) => m.streaming)?.content).toBe("Roses are red and blue");
  });
});

describe("thinking streams into a region that auto-collapses on the first content delta (DoD-3)", () => {
  it("DoD-3: thinking frames expand the live region; the first delta collapses it (context.md decisions 7/8)", async () => {
    const state = new ChatPaneState();
    primeActiveChat(state, []);
    const fixture = installTurnStream(vi.mocked(chatsApi.streamChatTurn));

    await sendChatTurn(state, BOOK_ID, "hi");

    fixture.thinking("Let me think");
    expect(state.liveThinkingExpanded).toBe(true);
    expect(state.streamingThinking).toContain("Let me think");

    fixture.thinking(" a bit more");
    expect(state.liveThinkingExpanded).toBe(true);
    expect(state.streamingThinking).toContain("a bit more");

    // The FIRST content delta auto-collapses the thinking region...
    fixture.delta("Here is the answer");
    expect(state.liveThinkingExpanded).toBe(false);
    // ...and the thinking text is preserved, not discarded.
    expect(state.streamingThinking).toContain("Let me think");
  });
});

describe("done replaces the in-flight bubble with the persisted message exactly once (DoD-5)", () => {
  it("DoD-5: on done the chat is reloaded and the streaming bubble becomes the one persisted assistant message, no duplicate or orphan (US-058.AC-1)", async () => {
    const state = new ChatPaneState();
    primeActiveChat(state, []);
    const fixture = installTurnStream(vi.mocked(chatsApi.streamChatTurn));

    const userMsg = makeMessage("m-1", "user", "hi", 0);
    const assistantMsg = makeMessage("m-2", "assistant", "Hello there", 1);
    vi.mocked(chatsApi.getChat).mockResolvedValue({ chat: CHAT, messages: [userMsg, assistantMsg] });

    await sendChatTurn(state, BOOK_ID, "hi");
    fixture.delta("Hello"); // an in-flight streaming bubble now exists
    fixture.done();

    await vi.waitFor(() => {
      const rendered = state.renderedMessages;
      // No orphaned streaming bubble remains.
      expect(rendered.some((m) => m.streaming)).toBe(false);
      // Exactly one assistant message, and it is the PERSISTED one.
      const assistants = rendered.filter((m) => m.role === "assistant");
      expect(assistants).toHaveLength(1);
      expect(assistants[0].content).toBe("Hello there");
      // No duplicated user message.
      expect(rendered.filter((m) => m.role === "user")).toHaveLength(1);
    });

    // The persisted message came from a single reload, not from the (payload-less) done frame.
    expect(vi.mocked(chatsApi.getChat)).toHaveBeenCalledTimes(1);
  });
});

describe("an error preserves the conversation and offers retry (DoD-6)", () => {
  it("DoD-6: an error frame sets the turn error, keeps the author's message, and offers retry (UC-056, US-060.AC-1, US-060.AC-2)", async () => {
    const state = new ChatPaneState();
    primeActiveChat(state, []);
    const fixture = installTurnStream(vi.mocked(chatsApi.streamChatTurn));

    await sendChatTurn(state, BOOK_ID, "my prompt");
    fixture.delta("partial answer");
    fixture.error("Model exploded");

    expect(state.turnStatus).toBe("error");
    expect(state.turnError).toBe("Model exploded");
    expect(state.retryOffered).toBe(true);
    // The conversation up to that point is preserved, including the author's just-sent message.
    expect(
      state.renderedMessages.some((m) => m.role === "user" && m.content === "my prompt"),
    ).toBe(true);
  });
});

describe("retry re-opens the turn without a prompt (DoD-7)", () => {
  it("DoD-7: retry opens the stream with no prompt, does not duplicate the user message, and appends exactly one assistant message (UC-056, US-060.AC-1)", async () => {
    const state = new ChatPaneState();
    const userMsg = makeMessage("m-1", "user", "original question", 0);
    primeActiveChat(state, [userMsg]);
    runInAction(() => {
      state.turnStatus = "error";
      state.turnError = "boom";
    });
    const fixture = installTurnStream(vi.mocked(chatsApi.streamChatTurn));

    const assistantMsg = makeMessage("m-2", "assistant", "the answer", 1);
    vi.mocked(chatsApi.getChat).mockResolvedValue({ chat: CHAT, messages: [userMsg, assistantMsg] });

    await retryChatTurn(state, BOOK_ID);

    // The stream re-opened on the same chat with NO prompt (the user text is never re-sent).
    expect(fixture.turns).toHaveLength(1);
    expect(fixture.last().prompt).toBeNull();
    expect(fixture.last().chatId).toBe(CHAT_ID);
    // The user message is not duplicated by the retry.
    expect(state.renderedMessages.filter((m) => m.role === "user")).toHaveLength(1);

    fixture.delta("the answer");
    fixture.done();

    await vi.waitFor(() => {
      expect(state.renderedMessages.filter((m) => m.role === "assistant")).toHaveLength(1);
      expect(state.renderedMessages.filter((m) => m.role === "user")).toHaveLength(1);
    });
  });
});

describe("the composer is gated while a turn is in flight (DoD-8)", () => {
  it("DoD-8: canSend is false while streaming and available again after done; a second prompt continues the same chat retaining the prior exchange (US-058.AC-2)", async () => {
    const state = new ChatPaneState();
    primeActiveChat(state, []);
    runInAction(() => {
      state.pendingPrompt = "first";
    });
    const fixture = installTurnStream(vi.mocked(chatsApi.streamChatTurn));

    // A non-empty prompt on an active idle chat can be sent.
    expect(state.canSend).toBe(true);

    await sendChatTurn(state, BOOK_ID, "first");
    // In flight -> composer disabled.
    expect(state.turnStatus).toBe("streaming");
    expect(state.canSend).toBe(false);

    const userMsg = makeMessage("m-1", "user", "first", 0);
    const assistantMsg = makeMessage("m-2", "assistant", "first answer", 1);
    vi.mocked(chatsApi.getChat).mockResolvedValue({ chat: CHAT, messages: [userMsg, assistantMsg] });
    fixture.done();
    await vi.waitFor(() => expect(state.turnStatus).toBe("idle"));

    // Re-enabled once the turn completes.
    runInAction(() => {
      state.pendingPrompt = "second";
    });
    expect(state.canSend).toBe(true);

    // A second prompt continues the SAME chat; the prior exchange is retained.
    await sendChatTurn(state, BOOK_ID, "second");
    expect(fixture.turns).toHaveLength(2);
    expect(fixture.last().chatId).toBe(CHAT_ID);
    expect(state.renderedMessages.some((m) => m.content === "first answer")).toBe(true);
    expect(
      state.renderedMessages.some((m) => m.role === "user" && m.content === "second"),
    ).toBe(true);
  });

  it("DoD-8: the composer is re-enabled after an error too", async () => {
    const state = new ChatPaneState();
    primeActiveChat(state, []);
    runInAction(() => {
      state.pendingPrompt = "retry me";
    });
    const fixture = installTurnStream(vi.mocked(chatsApi.streamChatTurn));

    await sendChatTurn(state, BOOK_ID, "retry me");
    expect(state.canSend).toBe(false);

    fixture.error("Model exploded");
    // An errored turn is not "in flight" — the composer is usable again.
    expect(state.turnStatus).toBe("error");
    runInAction(() => {
      state.pendingPrompt = "another try";
    });
    expect(state.canSend).toBe(true);
  });
});

describe("streamChatTurn awaits the token refresh before opening the stream (DoD-9)", () => {
  it("DoD-9: the refresh entry point resolves before streamPost is called (frontend.md -> SSE / streaming)", async () => {
    const order: string[] = [];
    vi.mocked(client.refreshAuthToken).mockImplementation(async () => {
      await Promise.resolve();
      order.push("refresh");
    });
    vi.mocked(sse.streamPost).mockImplementation(() => {
      order.push("stream");
      return new AbortController();
    });

    // The api module's OWN seam: exercise the real streamChatTurn (the mocked
    // `api/chats` above replaces it for the state layer, so import the actual here).
    const actual = await vi.importActual<typeof import("../../src/api/chats")>(
      "../../src/api/chats",
    );

    await actual.streamChatTurn(BOOK_ID, CHAT_ID, "hello", {
      onThinking: () => {},
      onDelta: () => {},
      onDone: () => {},
      onError: () => {},
    });

    // Refresh is awaited BEFORE the stream is opened, since streamPost bypasses client.ts's 401 refresh.
    expect(order).toEqual(["refresh", "stream"]);
  });
});

describe("switching the active chat mid-stream aborts the live stream (DoD-10)", () => {
  it("DoD-10: loading another chat aborts the live turn and leaves no stray buffer on the new chat", async () => {
    const state = new ChatPaneState();
    primeActiveChat(state, []);
    const fixture = installTurnStream(vi.mocked(chatsApi.streamChatTurn));

    await sendChatTurn(state, BOOK_ID, "on chat A");
    fixture.thinking("A-thinking");
    fixture.delta("A-content");
    expect(state.streamingContent).toContain("A-content");

    const controllerA = fixture.last().controller;

    // Switch to a different chat.
    vi.mocked(chatsApi.getChat).mockResolvedValue({
      chat: makeChat("c-2", "Chat B"),
      messages: [],
    });
    await loadChatMessages(state, BOOK_ID, "c-2");

    // The live stream on chat A was aborted...
    expect(controllerA.abort).toHaveBeenCalled();
    // ...and no stray buffer text is carried onto the newly opened chat.
    expect(state.streamingContent).toBe("");
    expect(state.streamingThinking).toBe("");
  });

  it("DoD-10: stopChatTurn aborts the stored live controller", async () => {
    const state = new ChatPaneState();
    primeActiveChat(state, []);
    const fixture = installTurnStream(vi.mocked(chatsApi.streamChatTurn));

    await sendChatTurn(state, BOOK_ID, "hi");
    const controller = fixture.last().controller;
    // The state stored the controller the stream owns (the frozen return-the-controller seam).
    expect(state.turnController).toBe(controller);

    stopChatTurn(state);
    expect(controller.abort).toHaveBeenCalled();
  });
});
