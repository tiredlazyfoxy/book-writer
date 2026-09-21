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
  pickChatModel,
  saveChatSettings,
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
    active_side_chat_id: null,
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

/* ===========================================================================
 * fast/009.model-picker — DoD-6 · DoD-8 · DoD-9 · DoD-11.
 *
 * Bound to the frozen signatures in `docs/plans/fast/009.model-picker/status.md` ->
 * `## Skeleton`:
 *   pickChatModel(state, bookId, optionKey, signal?): Promise<void>   // 009, new
 *   saveChatSettings(state, bookId, signal?): Promise<void>           // unchanged
 *   ChatPaneState.modelSearch / get filteredModelOptions              // 009, new
 *   failure surface: state.serverErrors["model"]; in-flight: state.settingsStatus
 *
 * Every expected value comes from `plan.md` -> Definition of done and its Interface
 * intent for `chatPaneState.ts` — never from code:
 *   - DoD-6: a pick issues exactly ONE update carrying ONLY the picked pair; no
 *     `sampling` / `title` / `archived` may ride along, and no message is sent;
 *   - DoD-8: the pick re-seeds only the MODEL half of `settingsDraft`, so the next
 *     send re-PATCHes nothing — while an unsent temperature edit survives the pick;
 *   - DoD-9: an unresolvable stored pair is LEFT ALONE — the request omits both
 *     fields rather than nulling them, and the label falls back to the stored
 *     `model_name` alone;
 *   - DoD-11: the existing "an accepted send clears whichever panel is open" holds.
 * =========================================================================== */

/** The pair `s-9 / m-9` is real but not offered by the loaded catalogue. */
const UNRESOLVABLE_KEY = "s-9::m-9";

describe("a model pick persists immediately and carries nothing else (009 DoD-6)", () => {
  it("009 DoD-6: a pick issues exactly one update whose body is ONLY the picked pair — no sampling, title or archived — and sends no message", async () => {
    const state = new ChatPaneState();
    primeCleanPane(state);
    const order: string[] = [];
    recordOrder(order);
    runInAction(() => {
      state.openedPanel = "model";
      state.modelSearch = "open";
      // An UNSENT creativity edit must not be smuggled to the server by a pick.
      state.settingsDraft.temperature = 1.4;
    });

    await pickChatModel(state, BOOK_ID, modelOptionKey(OTHER_OPTION));

    expect(vi.mocked(chatsApi.updateChat)).toHaveBeenCalledTimes(1);
    const [bookArg, chatArg, body] = vi.mocked(chatsApi.updateChat).mock.calls[0];
    expect(bookArg).toBe(BOOK_ID);
    expect(chatArg).toBe(CHAT_ID);
    expect(body.llm_server_id).toBe("s-2");
    expect(body.model_name).toBe("m-2");
    // "carrying ONLY llm_server_id and model_name" — an exact key set.
    expect(Object.keys(body).sort()).toEqual(["llm_server_id", "model_name"]);

    // A pick is not a turn.
    expect(order).toEqual(["update"]);
    expect(vi.mocked(chatsApi.streamChatTurn)).not.toHaveBeenCalled();

    // The pick closed the panel and cleared the needle.
    expect(state.openedPanel).toBeNull();
    expect(state.modelSearch).toBe("");
    // ...and the stored pair really moved.
    expect(state.activeChat?.llm_server_id).toBe("s-2");
    expect(state.activeChat?.model_name).toBe("m-2");
  });
});

describe("a persisted pick leaves the settings draft clean in its model half (009 DoD-8)", () => {
  it("009 DoD-8: after a successful pick with no temperature edit, sending issues NO further update call", async () => {
    const state = new ChatPaneState();
    primeCleanPane(state);
    recordOrder([]);

    await pickChatModel(state, BOOK_ID, modelOptionKey(OTHER_OPTION));
    expect(vi.mocked(chatsApi.updateChat)).toHaveBeenCalledTimes(1);

    // The model half of the draft now matches what is stored.
    expect(state.settingsDirty).toBe(false);

    vi.mocked(chatsApi.updateChat).mockClear();
    await sendChatTurn(state, BOOK_ID, "hello");

    // No re-PATCH of a model that is already stored.
    expect(vi.mocked(chatsApi.updateChat)).not.toHaveBeenCalled();
    expect(vi.mocked(chatsApi.streamChatTurn)).toHaveBeenCalledTimes(1);
  });

  it("009 DoD-8: after a pick FOLLOWED by a temperature edit, sending issues exactly one update whose sampling carries the new temperature and whose pair is the picked one", async () => {
    const state = new ChatPaneState();
    primeCleanPane(state);
    recordOrder([]);

    await pickChatModel(state, BOOK_ID, modelOptionKey(OTHER_OPTION));
    vi.mocked(chatsApi.updateChat).mockClear();

    // The creativity edit comes AFTER the pick and still travels on the send flush.
    runInAction(() => {
      state.settingsDraft.temperature = 1.4;
    });
    expect(state.settingsDirty).toBe(true);

    await sendChatTurn(state, BOOK_ID, "hello");

    expect(vi.mocked(chatsApi.updateChat)).toHaveBeenCalledTimes(1);
    const body = vi.mocked(chatsApi.updateChat).mock.calls[0][2];
    expect(body.sampling?.temperature).toBe(1.4);
    expect(body.llm_server_id).toBe("s-2");
    expect(body.model_name).toBe("m-2");
    expect(vi.mocked(chatsApi.streamChatTurn)).toHaveBeenCalledTimes(1);
  });

  it("009 DoD-8: a pick does not discard an UNSENT temperature edit made before it", async () => {
    const state = new ChatPaneState();
    primeCleanPane(state);
    recordOrder([]);
    runInAction(() => {
      state.settingsDraft.temperature = 1.4;
    });

    await pickChatModel(state, BOOK_ID, modelOptionKey(OTHER_OPTION));

    // Only the MODEL half was re-seeded.
    expect(state.settingsDraft.temperature).toBe(1.4);
    expect(state.settingsDraft.optionKey).toBe(modelOptionKey(OTHER_OPTION));
  });
});

describe("an unresolvable stored pair is left alone, not cleared (009 DoD-9)", () => {
  it("009 DoD-9: a settings flush omits llm_server_id and model_name entirely rather than sending nulls, and the label keeps the stored model_name", async () => {
    const state = new ChatPaneState();
    // The chat stores a pair the catalogue no longer offers (server deactivated /
    // model withdrawn); the loaded options are the two unrelated ones.
    runInAction(() => {
      state.chats = [makeChat({ llm_server_id: "s-9", model_name: "m-9" })];
      state.activeChatId = CHAT_ID;
      state.modelOptions = [CURRENT_OPTION, OTHER_OPTION];
      state.messages = [];
      state.messagesStatus = "ready";
      state.settingsDraft.optionKey = UNRESOLVABLE_KEY;
      state.settingsDraft.temperature = 1.4;
    });
    vi.mocked(chatsApi.updateChat).mockImplementation(async (_bookId, _chatId, body) => {
      const chat = makeChat({ llm_server_id: "s-9", model_name: "m-9" });
      return { ...chat, sampling: body.sampling ?? chat.sampling };
    });

    await saveChatSettings(state, BOOK_ID);

    expect(vi.mocked(chatsApi.updateChat)).toHaveBeenCalledTimes(1);
    const body = vi.mocked(chatsApi.updateChat).mock.calls[0][2];
    // OMITTED, not nulled — a null pair would wipe a real stored pair.
    expect(Object.prototype.hasOwnProperty.call(body, "llm_server_id")).toBe(false);
    expect(Object.prototype.hasOwnProperty.call(body, "model_name")).toBe(false);
    // The temperature half is unaffected.
    expect(body.sampling?.temperature).toBe(1.4);

    // The stored pair survives...
    expect(state.activeChat?.llm_server_id).toBe("s-9");
    expect(state.activeChat?.model_name).toBe("m-9");
    // ...and the header shows the stored model name alone rather than a blank.
    expect(state.modelLabel).toBe("m-9");
  });
});

describe("the openedPanel discriminator still yields to an accepted send (009 DoD-11)", () => {
  it('009 DoD-11: an accepted send still clears openedPanel from "model"', async () => {
    const state = new ChatPaneState();
    primeCleanPane(state);
    recordOrder([]);
    runInAction(() => {
      state.openedPanel = "model";
    });

    await sendChatTurn(state, BOOK_ID, "hello");

    expect(vi.mocked(chatsApi.streamChatTurn)).toHaveBeenCalledTimes(1);
    expect(state.openedPanel).toBeNull();
  });
});
