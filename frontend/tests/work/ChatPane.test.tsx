/**
 * Chat pane — pick / resolve / create / archive / settings, and 023's inversion.
 * Retargeted by 023.chat-ux-revision (design-note D12), 023 DoD-8 · 023 DoD-9.
 *
 * WHAT CHANGED, AND WHAT DID NOT. This spec shipped with 011.chat-panel / step 004.
 * 023 removes the chat LIST and the new-chat FORM from the pane (management moves to
 * `ChatsListPage`) and narrows `ChatSettingsPanel` to temperature only, so the three
 * cases that rendered a pane list / passed `options=` to that panel are gone — the
 * arrangement they asserted no longer exists. Every other 011 case is PRESERVED
 * verbatim: `chatPaneState`'s exported surface survives this feature untouched
 * (`plan.md` -> Interface -> `chatPaneState.ts`, "every existing exported symbol from
 * the harvest is preserved unchanged"; DoD-16), and `plan.md` -> Out of scope keeps
 * 011's sampling carry-through rule. Those cases keep their original 011 DoD ids.
 *
 * Bound to the frozen signatures in status.md -> `## Skeleton`:
 *   class ChatPaneState { chats/chatsStatus/chatsError; modelOptions; activeChatId;
 *     showArchived; newChatDraft; settingsDraft; serverErrors;
 *     createStatus/archiveStatus/settingsStatus; messages/messagesStatus;
 *     get visibleChats; get activeChat; get canCreateChat; get errors;
 *     openedPanel; get settingsDirty; get modelLabel }            // 023 additions
 *   loadChatPane / pickChat / createChatFromDraft / setChatArchived /
 *   saveChatSettings / modelOptionKey                             // 011, unchanged
 *   createChatInstant(state, bookId, signal?): Promise<void>      // 023, new
 *   interface ChatPaneProps { bookId: string; state: ChatPaneState }
 *   api/chats: listChats / createChat / updateChat / getChat / listModelOptions /
 *              streamChatTurn / titleChat
 *
 * The air gap: expected values come from the spec — `plan.md` -> Definition of done
 * (023 DoD-8, 023 DoD-9), its Interface section for `ChatPane.tsx` /
 * `chatPaneState.ts`, decisions D6 / D1, and (for the preserved cases) 011's own step
 * 004 DoD — never from code. `../../src/api/chats` is mocked module-factory form
 * (never `fetch`), enumerating every export the subject imports. `globals: false`.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { runInAction } from "mobx";
import { screen } from "@testing-library/react";
import { ApiError } from "../../src/api/client";
import type { ChatResponse, ChatSamplingParams, ModelOptionResponse } from "../../src/types/chats";
import * as chatsApi from "../../src/api/chats";
import {
  ChatPaneState,
  DEFAULT_TEMPERATURE,
  MAX_TEMPERATURE,
  MIN_TEMPERATURE,
  createChatFromDraft,
  createChatInstant,
  loadChatPane,
  modelOptionKey,
  pickChat,
  saveChatSettings,
  setChatArchived,
} from "../../src/work/components/chat/chatPaneState";
import { readActiveChatId, writeActiveChatId } from "../../src/work/activeChat";
import { ChatPane } from "../../src/work/components/chat/ChatPane";
import { renderWithProviders } from "../support/render";

// A module-factory mock replaces the WHOLE api module — it must supply every named
// export the pane state imports, `titleChat` (023's post-turn auto-titling) included.
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

/** Full default sampling set (011 feature decision 6 recommended defaults). */
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

/** A fully-typed ChatResponse; callers override the fields they assert on. */
function makeChat(
  id: string,
  title: string,
  modifiedAt: string,
  overrides: Partial<ChatResponse> = {},
): ChatResponse {
  return {
    id,
    book_id: BOOK_ID,
    author_id: "u-1",
    title,
    llm_server_id: null,
    model_name: null,
    sampling: makeSampling(),
    archived: false,
    created_at: modifiedAt,
    modified_at: modifiedAt,
    ...overrides,
  };
}

function makeOption(serverId: string, serverName: string, modelName: string): ModelOptionResponse {
  return { server_id: serverId, server_name: serverName, model_name: modelName };
}

/**
 * Make `listChats` answer by its `archived` flag, so a load that fetches the active
 * set, the archived set, or both, all see the intended lists (no accidental dupes).
 */
function mockList(active: ChatResponse[], archived: ChatResponse[] = []): void {
  vi.mocked(chatsApi.listChats).mockImplementation((_bookId, isArchived) =>
    Promise.resolve(isArchived ? archived : active),
  );
}

// Three chats already in most-recently-modified-first order (as the server returns them).
const GAMMA = makeChat("c-1", "Gamma chat", "2026-03-01T00:00:00Z");
const BETA = makeChat("c-2", "Beta chat", "2026-02-01T00:00:00Z");
const ALPHA = makeChat("c-3", "Alpha chat", "2026-01-01T00:00:00Z");

beforeEach(() => {
  // The per-book active-chat pointer is device-local; clear it so each case resolves
  // from its own fixtures rather than a neighbour's leftovers.
  window.localStorage.clear();
  // `restoreMocks` wipes implementations between tests — default to empty resolved lists.
  vi.mocked(chatsApi.listChats).mockResolvedValue([]);
  vi.mocked(chatsApi.listModelOptions).mockResolvedValue([]);
});

/* ===================================================================== 023 DoD-8 */

describe("the chat pane no longer hosts a chat list (023 DoD-8)", () => {
  it("023 DoD-8: with several chats loaded the pane shows only the ACTIVE chat — no list to pick from (D1: management moved to ChatsListPage)", async () => {
    const state = new ChatPaneState();
    mockList([GAMMA, BETA, ALPHA]);
    await loadChatPane(state, BOOK_ID);
    expect(state.activeChat?.id).toBe("c-1");

    renderWithProviders(<ChatPane bookId={BOOK_ID} state={state} />);

    // The active chat is identified in the pane...
    expect(screen.getAllByText("Gamma chat").length).toBeGreaterThan(0);
    // ...and the other chats are NOT rendered: the list is gone from the pane.
    expect(screen.queryByText("Beta chat")).toBeNull();
    expect(screen.queryByText("Alpha chat")).toBeNull();
  });
});

/* ===================================================================== 023 DoD-9 */

describe("the pane's instant create resolves a default model pair (023 DoD-9)", () => {
  it("023 DoD-9 (UC-053, US-056.AC-1, D6): with an active chat, the new chat inherits that chat's model pair, becomes active and opens an empty transcript", async () => {
    const state = new ChatPaneState();
    const optFirst = makeOption("s-1", "Local Llama", "m-1");
    const optActive = makeOption("s-2", "OpenAI", "m-2");
    const active = makeChat("c-1", "Chat one", "2026-02-01T00:00:00Z", {
      llm_server_id: "s-2",
      model_name: "m-2",
    });
    runInAction(() => {
      state.chats = [active];
      state.activeChatId = "c-1";
      state.modelOptions = [optFirst, optActive];
      state.messages = [];
    });

    const created = makeChat("c-new", "New chat", "2026-05-05T00:00:00Z", {
      llm_server_id: "s-2",
      model_name: "m-2",
    });
    vi.mocked(chatsApi.createChat).mockResolvedValue(created);

    await createChatInstant(state, BOOK_ID);

    // No form: the pair defaults to the ACTIVE chat's, not to the first option.
    expect(vi.mocked(chatsApi.createChat)).toHaveBeenCalledTimes(1);
    const [bookArg, body] = vi.mocked(chatsApi.createChat).mock.calls[0];
    expect(bookArg).toBe(BOOK_ID);
    expect(body.llm_server_id).toBe("s-2");
    expect(body.model_name).toBe("m-2");

    // The new chat is the one now open, with nothing in it yet.
    expect(state.activeChatId).toBe("c-new");
    expect(state.activeChat?.id).toBe("c-new");
    expect(state.messages).toHaveLength(0);
    expect(state.chats.map((chat) => chat.id)).toContain("c-new");
  });

  it("023 DoD-9: with no active chat, the pair defaults to the first available model option", async () => {
    const state = new ChatPaneState();
    const optFirst = makeOption("s-1", "Local Llama", "m-1");
    const optOther = makeOption("s-2", "OpenAI", "m-2");
    runInAction(() => {
      state.chats = [];
      state.activeChatId = null;
      state.modelOptions = [optFirst, optOther];
    });
    vi.mocked(chatsApi.createChat).mockResolvedValue(
      makeChat("c-new", "New chat", "2026-05-05T00:00:00Z", {
        llm_server_id: "s-1",
        model_name: "m-1",
      }),
    );

    await createChatInstant(state, BOOK_ID);

    const body = vi.mocked(chatsApi.createChat).mock.calls[0][1];
    expect(body.llm_server_id).toBe("s-1");
    expect(body.model_name).toBe("m-1");
    expect(state.activeChatId).toBe("c-new");
  });

  it("023 DoD-9 (UC-054 exception flow): with no model options at all the create is refused with an author-facing message, and nothing is created", async () => {
    const state = new ChatPaneState();
    runInAction(() => {
      state.chats = [];
      state.activeChatId = null;
      state.modelOptions = [];
    });

    await expect(createChatInstant(state, BOOK_ID)).resolves.toBeUndefined();

    expect(vi.mocked(chatsApi.createChat)).not.toHaveBeenCalled();
    expect(state.activeChatId).toBeNull();
    expect(typeof state.serverErrors.form).toBe("string");
    expect((state.serverErrors.form ?? "").length).toBeGreaterThan(0);
  });
});

/* ============================================ preserved 011.chat-panel / 004 cases */

describe("the author's non-archived chats are ordered most recent first (011 DoD-1)", () => {
  it("011 DoD-1: visibleChats are the non-archived chats in most-recent-first order (UC-081)", async () => {
    const state = new ChatPaneState();
    mockList([GAMMA, BETA, ALPHA]);

    await loadChatPane(state, BOOK_ID);

    expect(state.visibleChats.map((chat) => chat.id)).toEqual(["c-1", "c-2", "c-3"]);
  });

  it("011 DoD-1: with no chats the pane renders an empty state, not a crash or blank", async () => {
    const state = new ChatPaneState();
    mockList([], []);
    await loadChatPane(state, BOOK_ID);

    renderWithProviders(<ChatPane bookId={BOOK_ID} state={state} />);

    expect(state.visibleChats).toHaveLength(0);
    expect(screen.queryByText("Gamma chat")).toBeNull();
    expect((document.body.textContent ?? "").trim()).not.toBe("");
  });
});

describe("picking a chat sets the pane's active chat + the per-book pointer (011 DoD-2)", () => {
  it("011 DoD-2: pickChat sets the active id and writes the pointer, without navigating or hitting the network (US-095.AC-2)", () => {
    const state = new ChatPaneState();

    pickChat(state, BOOK_ID, "c-2");

    // Opens in the CHAT PANE: active-chat state + the device-local per-book pointer.
    expect(state.activeChatId).toBe("c-2");
    expect(readActiveChatId(BOOK_ID)).toBe("c-2");

    // NOT the content pane: a pick is a pane-state change, not a route/fetch — no api call.
    expect(vi.mocked(chatsApi.listChats)).not.toHaveBeenCalled();
    expect(vi.mocked(chatsApi.getChat)).not.toHaveBeenCalled();
    expect(vi.mocked(chatsApi.createChat)).not.toHaveBeenCalled();
    expect(vi.mocked(chatsApi.updateChat)).not.toHaveBeenCalled();
  });
});

describe("on load, the active chat resolves from the pointer, else the most recent (011 DoD-3)", () => {
  it("011 DoD-3: a stored pointer that names a visible chat becomes the active chat", async () => {
    const state = new ChatPaneState();
    writeActiveChatId(BOOK_ID, "c-2");
    mockList([GAMMA, BETA, ALPHA]);

    await loadChatPane(state, BOOK_ID);

    expect(state.activeChatId).toBe("c-2");
    expect(state.activeChat?.id).toBe("c-2");
  });

  it("011 DoD-3: with no stored pointer, the most recent chat becomes active", async () => {
    const state = new ChatPaneState();
    mockList([GAMMA, BETA, ALPHA]);

    await loadChatPane(state, BOOK_ID);

    // c-1 (Gamma) has the most recent modified_at.
    expect(state.activeChat?.id).toBe("c-1");
  });

  it("011 DoD-3: a pointer that names a chat NOT in the list falls back to the most recent", async () => {
    const state = new ChatPaneState();
    writeActiveChatId(BOOK_ID, "c-does-not-exist");
    mockList([GAMMA, BETA, ALPHA]);

    await loadChatPane(state, BOOK_ID);

    expect(state.activeChat?.id).toBe("c-1");
  });

  it("011 DoD-3: an empty list resolves to no active chat", async () => {
    const state = new ChatPaneState();
    mockList([], []);

    await loadChatPane(state, BOOK_ID);

    expect(state.activeChatId).toBeNull();
    expect(state.activeChat).toBeNull();
  });
});

describe("creating a chat requires an option + an in-range temperature (011 DoD-6)", () => {
  it("011 DoD-6: canCreateChat requires both a chosen option AND a temperature in range", () => {
    const state = new ChatPaneState();
    const option = makeOption("s-1", "Local Llama", "qwen-72b");

    // Fresh draft: no option chosen -> cannot create.
    expect(state.canCreateChat).toBe(false);

    // A chosen option and an in-range temperature -> can create.
    runInAction(() => {
      state.modelOptions = [option];
      state.newChatDraft.optionKey = modelOptionKey(option);
      state.newChatDraft.temperature = DEFAULT_TEMPERATURE;
    });
    expect(state.canCreateChat).toBe(true);

    // Temperature above the range -> refused.
    runInAction(() => {
      state.newChatDraft.temperature = MAX_TEMPERATURE + 1;
    });
    expect(state.canCreateChat).toBe(false);

    // Temperature below the range -> refused.
    runInAction(() => {
      state.newChatDraft.temperature = MIN_TEMPERATURE - 1;
    });
    expect(state.canCreateChat).toBe(false);

    // In range again but no option chosen -> refused.
    runInAction(() => {
      state.newChatDraft.temperature = DEFAULT_TEMPERATURE;
      state.newChatDraft.optionKey = null;
    });
    expect(state.canCreateChat).toBe(false);
  });

  it("011 DoD-6: a successful create goes through the api with the chosen (server, model) + temperature, becomes active, and appears in the list (UC-053, US-056.AC-1)", async () => {
    const state = new ChatPaneState();
    const option = makeOption("s-1", "Local Llama", "qwen-72b");
    mockList([], []);
    vi.mocked(chatsApi.listModelOptions).mockResolvedValue([option]);
    await loadChatPane(state, BOOK_ID);

    runInAction(() => {
      state.newChatDraft.title = "Brainstorm";
      state.newChatDraft.optionKey = modelOptionKey(option);
      state.newChatDraft.temperature = DEFAULT_TEMPERATURE;
    });

    const created = makeChat("c-new", "Brainstorm", "2026-05-05T00:00:00Z", {
      llm_server_id: "s-1",
      model_name: "qwen-72b",
      sampling: makeSampling({ temperature: DEFAULT_TEMPERATURE }),
    });
    vi.mocked(chatsApi.createChat).mockResolvedValue(created);

    await createChatFromDraft(state, BOOK_ID);

    // Created through the api module with the chosen option + temperature.
    expect(vi.mocked(chatsApi.createChat)).toHaveBeenCalledTimes(1);
    const [bookArg, body] = vi.mocked(chatsApi.createChat).mock.calls[0];
    expect(bookArg).toBe(BOOK_ID);
    expect(body.title).toBe("Brainstorm");
    expect(body.llm_server_id).toBe("s-1");
    expect(body.model_name).toBe("qwen-72b");
    expect(body.sampling?.temperature).toBe(DEFAULT_TEMPERATURE);

    // Becomes active, writes the pointer, and appears in the list.
    expect(state.activeChatId).toBe("c-new");
    expect(readActiveChatId(BOOK_ID)).toBe("c-new");
    expect(state.visibleChats.map((chat) => chat.id)).toContain("c-new");
  });
});

describe("no model options refuses composing (011 DoD-7)", () => {
  it("011 DoD-7: with no model options available, a chat cannot be composed (UC-054 exception flow)", async () => {
    const state = new ChatPaneState();
    mockList([], []);
    vi.mocked(chatsApi.listModelOptions).mockResolvedValue([]);
    await loadChatPane(state, BOOK_ID);

    expect(state.modelOptions).toHaveLength(0);
    // Even with a valid temperature, no option can be chosen, so create is refused.
    runInAction(() => {
      state.newChatDraft.temperature = DEFAULT_TEMPERATURE;
    });
    expect(state.canCreateChat).toBe(false);
  });
});

describe("settings are editable on the active chat (011 DoD-8)", () => {
  it("011 DoD-8: changing the active chat's model + temperature calls update, and the pane reflects the new values", async () => {
    const state = new ChatPaneState();
    const optCurrent = makeOption("s-1", "Local Llama", "m-1");
    const optNext = makeOption("s-2", "OpenAI", "m-2");
    const active = makeChat("c-1", "Chat one", "2026-02-01T00:00:00Z", {
      llm_server_id: "s-1",
      model_name: "m-1",
      sampling: makeSampling({ temperature: 0.8 }),
    });

    writeActiveChatId(BOOK_ID, "c-1");
    mockList([active]);
    vi.mocked(chatsApi.listModelOptions).mockResolvedValue([optCurrent, optNext]);
    await loadChatPane(state, BOOK_ID);
    expect(state.activeChatId).toBe("c-1");

    // Edit the active chat's settings: switch model and change temperature.
    runInAction(() => {
      state.settingsDraft.optionKey = modelOptionKey(optNext);
      state.settingsDraft.temperature = 1.2;
    });

    vi.mocked(chatsApi.updateChat).mockImplementation(async (_bookId, _chatId, body) => ({
      ...active,
      llm_server_id: body.llm_server_id ?? active.llm_server_id,
      model_name: body.model_name ?? active.model_name,
      sampling: body.sampling ?? active.sampling,
    }));

    await saveChatSettings(state, BOOK_ID);

    // The update carried the new model pair + temperature to the api.
    const call = vi.mocked(chatsApi.updateChat).mock.calls[0];
    expect(call[0]).toBe(BOOK_ID);
    expect(call[1]).toBe("c-1");
    expect(call[2].llm_server_id).toBe("s-2");
    expect(call[2].model_name).toBe("m-2");
    expect(call[2].sampling?.temperature).toBe(1.2);

    // The pane reflects the new values on the active chat.
    expect(state.activeChat?.llm_server_id).toBe("s-2");
    expect(state.activeChat?.model_name).toBe("m-2");
    expect(state.activeChat?.sampling.temperature).toBe(1.2);
  });
});

describe("archive removes from the active list; restore returns it; active re-resolves (011 DoD-9)", () => {
  it("011 DoD-9: visibleChats shows the active set when not viewing archived, and the archived set when viewing archived (UC-082, US-096.AC-1)", () => {
    const state = new ChatPaneState();
    const active = makeChat("c-a", "Active chat", "2026-02-01T00:00:00Z", { archived: false });
    const archived = makeChat("c-b", "Archived chat", "2026-01-01T00:00:00Z", { archived: true });

    runInAction(() => {
      state.chats = [active, archived];
      state.showArchived = false;
    });
    // Archiving removes a chat from the ACTIVE list.
    expect(state.visibleChats.map((chat) => chat.id)).toContain("c-a");
    expect(state.visibleChats.map((chat) => chat.id)).not.toContain("c-b");

    runInAction(() => {
      state.showArchived = true;
    });
    // The ARCHIVED view shows the archived chat.
    expect(state.visibleChats.map((chat) => chat.id)).toContain("c-b");
    expect(state.visibleChats.map((chat) => chat.id)).not.toContain("c-a");
  });

  it("011 DoD-9: restoring a chat flips it back to the active set (US-096.AC-2)", async () => {
    const state = new ChatPaneState();
    const archived = makeChat("c-b", "Archived chat", "2026-01-01T00:00:00Z", { archived: true });

    runInAction(() => {
      state.chats = [archived];
      state.showArchived = true;
    });
    vi.mocked(chatsApi.updateChat).mockResolvedValue({ ...archived, archived: false });

    await setChatArchived(state, BOOK_ID, "c-b", false);

    // Restore goes through the api as an un-archive.
    const call = vi.mocked(chatsApi.updateChat).mock.calls[0];
    expect(call[1]).toBe("c-b");
    expect(call[2].archived).toBe(false);
    // And the chat is now back in the active set.
    expect(state.chats.find((chat) => chat.id === "c-b")?.archived).toBe(false);
  });

  it("011 DoD-9: archiving the ACTIVE chat re-resolves the active chat and leaves no dangling pointer", async () => {
    const state = new ChatPaneState();
    writeActiveChatId(BOOK_ID, "c-1");
    mockList([GAMMA, BETA]); // c-1 (most recent) is active, c-2 remains
    await loadChatPane(state, BOOK_ID);
    expect(state.activeChatId).toBe("c-1");

    vi.mocked(chatsApi.updateChat).mockResolvedValue({ ...GAMMA, archived: true });

    await setChatArchived(state, BOOK_ID, "c-1", true);

    // Archive goes through the api with archived: true.
    const call = vi.mocked(chatsApi.updateChat).mock.calls[0];
    expect(call[1]).toBe("c-1");
    expect(call[2].archived).toBe(true);

    // The archived chat left the active list...
    expect(state.visibleChats.map((chat) => chat.id)).not.toContain("c-1");
    // ...and the active chat re-resolved to the remaining most recent, pointer rewritten.
    expect(state.activeChatId).toBe("c-2");
    expect(readActiveChatId(BOOK_ID)).toBe("c-2");
  });
});

describe("only temperature is surfaced; every other sampling param round-trips unchanged (011 DoD-10)", () => {
  it("011 DoD-10: editing the temperature sends an update whose sampling carries every other param unchanged (023 keeps 011's carry-through rule)", async () => {
    const state = new ChatPaneState();
    const optCurrent = makeOption("s-1", "Local Llama", "m-1");
    // Distinctive non-default values for every param other than temperature.
    const stored = makeSampling({
      temperature: 0.8,
      top_p: 0.85,
      top_k: 99,
      repeat_penalty: 1.7,
      min_p: 0.3,
      max_tokens: 1234,
      seed: 42,
      presence_penalty: 0.5,
      frequency_penalty: 0.6,
      enable_thinking: false,
    });
    const active = makeChat("c-1", "Chat one", "2026-02-01T00:00:00Z", {
      llm_server_id: "s-1",
      model_name: "m-1",
      sampling: stored,
    });

    writeActiveChatId(BOOK_ID, "c-1");
    mockList([active]);
    vi.mocked(chatsApi.listModelOptions).mockResolvedValue([optCurrent]);
    await loadChatPane(state, BOOK_ID);

    // Change ONLY temperature (same model).
    runInAction(() => {
      state.settingsDraft.optionKey = modelOptionKey(optCurrent);
      state.settingsDraft.temperature = 1.5;
    });
    vi.mocked(chatsApi.updateChat).mockResolvedValue({
      ...active,
      sampling: { ...stored, temperature: 1.5 },
    });

    await saveChatSettings(state, BOOK_ID);

    const sampling = vi.mocked(chatsApi.updateChat).mock.calls[0][2].sampling;
    expect(sampling).toBeTruthy();
    // The edited param...
    expect(sampling?.temperature).toBe(1.5);
    // ...and every other stored param carried through unchanged.
    expect(sampling?.top_p).toBe(0.85);
    expect(sampling?.top_k).toBe(99);
    expect(sampling?.repeat_penalty).toBe(1.7);
    expect(sampling?.min_p).toBe(0.3);
    expect(sampling?.max_tokens).toBe(1234);
    expect(sampling?.seed).toBe(42);
    expect(sampling?.presence_penalty).toBe(0.5);
    expect(sampling?.frequency_penalty).toBe(0.6);
    expect(sampling?.enable_thinking).toBe(false);
  });
});

describe("a failed load or action surfaces an author-facing message, no crash (011 DoD-11)", () => {
  it("011 DoD-11: a failed load records an error and the pane renders a message, not a blank", async () => {
    const state = new ChatPaneState();
    vi.mocked(chatsApi.listChats).mockRejectedValue(new ApiError(500, "Server error"));

    await loadChatPane(state, BOOK_ID);

    // The trio landed in its error state with an author-facing message (ApiError, not rethrown).
    expect(state.chatsStatus).toBe("error");
    expect(typeof state.chatsError).toBe("string");
    expect((state.chatsError ?? "").length).toBeGreaterThan(0);

    renderWithProviders(<ChatPane bookId={BOOK_ID} state={state} />);
    // Not a crash and not blank: the shell rendered readable content.
    expect((document.body.textContent ?? "").trim()).not.toBe("");
  });

  it("011 DoD-11: a failed action (create) surfaces an error instead of throwing", async () => {
    const state = new ChatPaneState();
    const option = makeOption("s-1", "Local Llama", "qwen-72b");
    runInAction(() => {
      state.modelOptions = [option];
      state.newChatDraft.title = "X";
      state.newChatDraft.optionKey = modelOptionKey(option);
      state.newChatDraft.temperature = DEFAULT_TEMPERATURE;
    });
    vi.mocked(chatsApi.createChat).mockRejectedValue(new ApiError(400, "Bad request"));

    // An ApiError becomes an author-facing message, not a thrown exception.
    await expect(createChatFromDraft(state, BOOK_ID)).resolves.toBeUndefined();
    expect(state.createStatus).toBe("error");
  });
});
