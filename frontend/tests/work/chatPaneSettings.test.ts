/**
 * Chat pane settings flush + popover discriminator — 023.chat-ux-revision,
 * DoD-4 · DoD-5.
 *
 * Bound to the frozen signatures in status.md -> `## Skeleton` (023):
 *   ChatPaneState (additions): openedPanel: "model" | "settings" | null;
 *                              get settingsDirty; get modelLabel
 *   sendChatTurn(state, bookId, text): Promise<void>   // signature unchanged
 *   api/chats: updateChat / streamChatTurn / titleChat / listChats / createChat /
 *              getChat / listModelOptions
 *
 * Every expected value comes from the SPEC -- `plan.md` -> Definition of done
 * (DoD-4, DoD-5), its Interface section for `chatPaneState.ts`, and decisions D7 / D8
 * -- never from code:
 *   - DoD-4 is an ORDERING contract at the send seam. `prepare_turn` reads the chat's
 *     STORED model pair, so a dirty settings draft must be persisted BEFORE the turn
 *     stream is opened; a clean draft must issue no update call at all; and a flush
 *     that fails must abort the send outright -- no stream opened -- leaving the
 *     author-facing message `saveChatSettings` already produces.
 *   - DoD-5's testable half at state level is the CLEAR: an accepted send clears
 *     `openedPanel` from either open panel. The "opening one closes the other" half is
 *     structural -- `openedPanel` is a single discriminator that can hold at most one
 *     panel by construction, and the popover open/close RENDERING is on `plan.md` ->
 *     Test plan -> "Not tested (deliberate)" -- so asserting it here would be a
 *     tautology rather than a behaviour check.
 *
 * `../../src/api/chats` is mocked module-factory form (never `fetch`), enumerating
 * every export the state layer imports. `globals: false`.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { runInAction } from "mobx";
import type { ChatResponse, ChatSamplingParams, ModelOptionResponse } from "../../src/types/chats";
import { ApiError } from "../../src/api/client";
import * as chatsApi from "../../src/api/chats";
import {
  ChatPaneState,
  modelOptionKey,
  sendChatTurn,
} from "../../src/work/components/chat/chatPaneState";

// Whole-module factory: every export the pane state reaches through its namespace
// import must be enumerated, or it is stripped to `undefined`.
vi.mock("../../src/api/chats", () => ({
  listChats: vi.fn(),
  createChat: vi.fn(),
  updateChat: vi.fn(),
  getChat: vi.fn(),
  listModelOptions: vi.fn(),
  streamChatTurn: vi.fn(),
  titleChat: vi.fn(),
}));

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

/** The chat's PERSISTED state: server `s-1`, model `m-1`, temperature 0.8. */
function makeChat(overrides: Partial<ChatResponse> = {}): ChatResponse {
  return {
    id: CHAT_ID,
    book_id: BOOK_ID,
    author_id: "u-1",
    title: "Chat one",
    llm_server_id: "s-1",
    model_name: "m-1",
    sampling: makeSampling(),
    archived: false,
    created_at: "2026-01-01T00:00:00Z",
    modified_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

const CURRENT_OPTION: ModelOptionResponse = {
  server_id: "s-1",
  server_name: "Local Llama",
  model_name: "m-1",
};
const OTHER_OPTION: ModelOptionResponse = {
  server_id: "s-2",
  server_name: "OpenAI",
  model_name: "m-2",
};

/**
 * Seed an active chat whose settings draft MATCHES what is persisted — i.e. a clean
 * pane, ready to send. Individual tests dirty the draft they want to test.
 */
function primeCleanPane(state: ChatPaneState): void {
  runInAction(() => {
    state.chats = [makeChat()];
    state.activeChatId = CHAT_ID;
    state.modelOptions = [CURRENT_OPTION, OTHER_OPTION];
    state.messages = [];
    state.messagesStatus = "ready";
    state.turnStatus = "idle";
    state.turnError = null;
    state.pendingPrompt = "hello";
    state.settingsDraft.optionKey = modelOptionKey(CURRENT_OPTION);
    state.settingsDraft.temperature = 0.8;
  });
}

/**
 * Record the ORDER in which the two api seams are reached. `updateChat` resolves with
 * the persisted row; `streamChatTurn` resolves with a controller, as the frozen seam
 * does.
 */
function recordOrder(order: string[]): void {
  vi.mocked(chatsApi.updateChat).mockImplementation(async (_bookId, _chatId, body) => {
    order.push("update");
    const chat = makeChat();
    return {
      ...chat,
      llm_server_id: body.llm_server_id ?? chat.llm_server_id,
      model_name: body.model_name ?? chat.model_name,
      sampling: body.sampling ?? chat.sampling,
    };
  });
  vi.mocked(chatsApi.streamChatTurn).mockImplementation(() => {
    order.push("stream");
    return Promise.resolve(new AbortController());
  });
}

beforeEach(() => {
  // `restoreMocks` wipes implementations between tests — benign defaults.
  vi.mocked(chatsApi.getChat).mockResolvedValue({ chat: makeChat(), messages: [] });
  vi.mocked(chatsApi.titleChat).mockResolvedValue({ title: "Chat one", changed: false });
  vi.mocked(chatsApi.streamChatTurn).mockResolvedValue(new AbortController());
});

describe("settings are flushed before the turn stream opens (DoD-4)", () => {
  it("DoD-4: a dirty settings draft is persisted via the update call BEFORE the stream is opened (D8)", async () => {
    const state = new ChatPaneState();
    primeCleanPane(state);
    const order: string[] = [];
    recordOrder(order);

    // Dirty the draft: a different model pair and a different temperature.
    runInAction(() => {
      state.settingsDraft.optionKey = modelOptionKey(OTHER_OPTION);
      state.settingsDraft.temperature = 1.4;
    });
    expect(state.settingsDirty).toBe(true);

    await sendChatTurn(state, BOOK_ID, "hello");

    // The ordering IS the contract: the backend turn reads the STORED pair.
    expect(order).toEqual(["update", "stream"]);

    // ...and the update really carried the edited settings.
    const call = vi.mocked(chatsApi.updateChat).mock.calls[0];
    expect(call[0]).toBe(BOOK_ID);
    expect(call[1]).toBe(CHAT_ID);
    expect(call[2].llm_server_id).toBe("s-2");
    expect(call[2].model_name).toBe("m-2");
    expect(call[2].sampling?.temperature).toBe(1.4);
  });

  it("DoD-4: a clean settings draft issues no update call — only the stream is opened", async () => {
    const state = new ChatPaneState();
    primeCleanPane(state);
    const order: string[] = [];
    recordOrder(order);

    // Nothing was edited: the draft equals what is persisted.
    expect(state.settingsDirty).toBe(false);

    await sendChatTurn(state, BOOK_ID, "hello");

    expect(vi.mocked(chatsApi.updateChat)).not.toHaveBeenCalled();
    expect(order).toEqual(["stream"]);
  });

  it("DoD-4: a failed flush aborts the send — no stream is opened and an author-facing error is present", async () => {
    const state = new ChatPaneState();
    primeCleanPane(state);
    const order: string[] = [];
    recordOrder(order);
    vi.mocked(chatsApi.updateChat).mockRejectedValue(new ApiError(400, "Bad request"));

    runInAction(() => {
      state.settingsDraft.temperature = 1.4;
    });
    expect(state.settingsDirty).toBe(true);

    // The refusal is an author-facing message, not a thrown exception.
    await expect(sendChatTurn(state, BOOK_ID, "hello")).resolves.toBeUndefined();

    // No turn was opened against settings that never reached the server.
    expect(vi.mocked(chatsApi.streamChatTurn)).not.toHaveBeenCalled();
    expect(order).toEqual([]);

    // The author is told why.
    expect(state.settingsStatus).toBe("error");
    expect(typeof state.serverErrors.form).toBe("string");
    expect((state.serverErrors.form ?? "").length).toBeGreaterThan(0);
  });
});

describe("sending clears whichever popover is open (DoD-5)", () => {
  // Parameterized over BOTH panels: "sending a message clears both" (DoD-5).
  for (const panel of ["model", "settings"] as const) {
    it(`DoD-5: an accepted send clears openedPanel from "${panel}" (D7)`, async () => {
      const state = new ChatPaneState();
      primeCleanPane(state);
      recordOrder([]);
      runInAction(() => {
        state.openedPanel = panel;
      });

      await sendChatTurn(state, BOOK_ID, "hello");

      // The turn was accepted...
      expect(vi.mocked(chatsApi.streamChatTurn)).toHaveBeenCalledTimes(1);
      // ...so no popover is left hanging over the conversation.
      expect(state.openedPanel).toBeNull();
    });
  }
});
