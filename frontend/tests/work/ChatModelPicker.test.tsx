/**
 * Chat pane model picker — fast/009.model-picker, DoD-1 · DoD-2 · DoD-3 · DoD-4 ·
 * DoD-5 · DoD-7 · DoD-10 · DoD-11 · DoD-12 · DoD-13.
 *
 * Bound to the frozen signatures in `docs/plans/fast/009.model-picker/status.md` ->
 * `## Skeleton`:
 *   class ChatPaneState { chats; chatsStatus; activeChatId; modelOptions;
 *     modelOptionsStatus; modelOptionsError; openedPanel: "model"|"settings"|null;
 *     modelSearch: string;                                    // 009, new
 *     settingsDraft; serverErrors; settingsStatus; messages; messagesStatus;
 *     turnStatus; get modelLabel; get filteredModelOptions }  // 009, new computed
 *   new ChatPaneState()                                       // no arguments
 *   pickChatModel(state, bookId, optionKey, signal?): Promise<void>   // 009, new
 *   loadChatPane(state, bookId, signal?): Promise<void>
 *   modelOptionKey(option) -> `${server_id}::${model_name}`
 *   interface ChatPaneProps { bookId: string; state: ChatPaneState }
 *   api/chats: listChats / createChat / updateChat / getChat / listModelOptions /
 *              streamChatTurn / titleChat
 *
 * Every expected value comes from the SPEC — `plan.md` -> Definition of done
 * (DoD-1..DoD-13), its Interface intent for `ChatPane.tsx`, and the accessible-handle
 * table in `## Skeleton` / `context.md` -> "Test handles" — never from code:
 *   - the header model button is `aria-label="Model"` and renders `state.modelLabel`;
 *   - the in-dropdown search field's accessible name is exactly `"Search models"`;
 *   - an option row's visible text is exactly `` `${server_name} · ${model_name}` ``
 *     (`·` is U+00B7, space-padded);
 *   - the three non-option lines are exactly `"No models available"`, the value of
 *     `state.modelOptionsError`, and exactly `"Nothing found"`;
 *   - a pick failure renders the value of `state.serverErrors["model"]` in the header
 *     region with the dropdown closed.
 *
 * `../../src/api/chats` is mocked module-factory form (never `fetch`), enumerating
 * every export the pane reaches. `globals: false`.
 *
 * NOTE on the option-row helper: the header button renders the SAME label shape as an
 * option row once the stored pair resolves, so every option lookup excludes the button
 * subtree — otherwise a plain `getByText` would be ambiguous rather than wrong.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { runInAction } from "mobx";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ApiError } from "../../src/api/client";
import type { ChatResponse, ChatSamplingParams, ModelOptionResponse } from "../../src/types/chats";
import * as chatsApi from "../../src/api/chats";
import { ChatPaneState, loadChatPane } from "../../src/work/components/chat/chatPaneState";
import { ChatPane } from "../../src/work/components/chat/ChatPane";
import { renderWithProviders } from "../support/render";

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

/* ------------------------------------------------------------------ fixtures */

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

/** The chat's PERSISTED state; by default server `s-1`, model `m-1`. */
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

// Three options. The FIRST overall (`OPT_LOCAL`) is deliberately NOT the first match
// of the `"openai"` needle, so DoD-4's "first of the currently FILTERED list" is
// distinguishable from "first of the catalogue".
const OPT_LOCAL: ModelOptionResponse = {
  server_id: "s-1",
  server_name: "Local Llama",
  model_name: "m-1",
};
const OPT_OPENAI: ModelOptionResponse = {
  server_id: "s-2",
  server_name: "OpenAI",
  model_name: "m-2",
};
const OPT_GPT: ModelOptionResponse = {
  server_id: "s-2",
  server_name: "OpenAI",
  model_name: "gpt-x",
};
const ALL_OPTIONS: ModelOptionResponse[] = [OPT_LOCAL, OPT_OPENAI, OPT_GPT];

/** The option-row / header label shape from the handle table (`·` is U+00B7). */
function optionLabel(option: ModelOptionResponse): string {
  return `${option.server_name} · ${option.model_name}`;
}

/* ------------------------------------------------------------------- handles */

/** The header model button — `aria-label="Model"`, unchanged from today. */
function modelButton(): HTMLElement {
  return screen.getByLabelText("Model");
}

/**
 * The in-dropdown search field, found by its ACCESSIBLE NAME `"Search models"`. The
 * spec fixes the name, not the role or the labelling mechanism, so every mechanism
 * that yields that name is accepted. `null` when the dropdown is closed.
 */
function querySearch(): HTMLElement | null {
  const found = [
    ...screen.queryAllByRole("textbox", { name: "Search models" }),
    ...screen.queryAllByRole("searchbox", { name: "Search models" }),
    ...screen.queryAllByLabelText("Search models"),
    ...screen.queryAllByPlaceholderText("Search models"),
  ];
  return found.length > 0 ? found[0] : null;
}

function getSearch(): HTMLElement {
  const input = querySearch();
  expect(input).not.toBeNull();
  return input as HTMLElement;
}

/** Elements rendering `label` OUTSIDE the header button — i.e. the option rows. */
function optionRows(label: string): HTMLElement[] {
  const button = modelButton();
  return screen.queryAllByText(label).filter((element) => !button.contains(element));
}

function optionRow(option: ModelOptionResponse): HTMLElement {
  const rows = optionRows(optionLabel(option));
  expect(rows).toHaveLength(1);
  return rows[0];
}

function isOptionRendered(option: ModelOptionResponse): boolean {
  return optionRows(optionLabel(option)).length > 0;
}

/** Document order of two rendered nodes — "the original order is preserved". */
function comesBefore(first: HTMLElement, second: HTMLElement): boolean {
  return (first.compareDocumentPosition(second) & Node.DOCUMENT_POSITION_FOLLOWING) !== 0;
}

/* -------------------------------------------------------------------- priming */

interface PrimeOptions {
  options?: ModelOptionResponse[];
  optionsStatus?: "idle" | "loading" | "ready" | "error";
  optionsError?: string | null;
  chat?: ChatResponse | null;
}

/** A pane with an active chat and a loaded (or failed) model catalogue. */
function primePane(overrides: PrimeOptions = {}): ChatPaneState {
  const {
    options = ALL_OPTIONS,
    optionsStatus = "ready",
    optionsError = null,
    chat = makeChat(),
  } = overrides;
  const state = new ChatPaneState();
  runInAction(() => {
    state.chats = chat === null ? [] : [chat];
    state.chatsStatus = "ready";
    state.activeChatId = chat === null ? null : chat.id;
    state.modelOptions = options;
    state.modelOptionsStatus = optionsStatus;
    state.modelOptionsError = optionsError;
    state.messages = [];
    state.messagesStatus = "ready";
    state.turnStatus = "idle";
    state.turnError = null;
  });
  return state;
}

/** `updateChat` echoes the picked pair back, as the server does. */
function mockUpdateEchoes(): void {
  vi.mocked(chatsApi.updateChat).mockImplementation(async (_bookId, _chatId, body) => {
    const chat = makeChat();
    return {
      ...chat,
      llm_server_id: body.llm_server_id ?? chat.llm_server_id,
      model_name: body.model_name ?? chat.model_name,
      sampling: body.sampling ?? chat.sampling,
    };
  });
}

beforeEach(() => {
  // `restoreMocks` wipes implementations between tests — benign defaults.
  window.localStorage.clear();
  vi.mocked(chatsApi.listChats).mockResolvedValue([]);
  vi.mocked(chatsApi.listModelOptions).mockResolvedValue([]);
  vi.mocked(chatsApi.getChat).mockResolvedValue({ chat: makeChat(), messages: [] });
  vi.mocked(chatsApi.titleChat).mockResolvedValue({ title: "Chat one", changed: false });
  vi.mocked(chatsApi.streamChatTurn).mockResolvedValue(new AbortController());
  mockUpdateEchoes();
});

/* ==================================================================== DoD-1 */

describe("one click opens a ready, focused model dropdown (009 DoD-1)", () => {
  it("009 DoD-1: a single click on the header model button renders the option list already — and focuses the search field", async () => {
    const user = userEvent.setup();
    const state = primePane();
    renderWithProviders(<ChatPane bookId={BOOK_ID} state={state} />);

    // Closed to begin with: no search field, no options.
    expect(querySearch()).toBeNull();
    expect(isOptionRendered(OPT_OPENAI)).toBe(false);

    await user.click(modelButton());

    // ONE click — the list is already there, no second click to expand it.
    for (const option of ALL_OPTIONS) {
      expect(isOptionRendered(option)).toBe(true);
    }
    // ...and the author can type straight away.
    expect(document.activeElement).toBe(getSearch());
  });
});

/* ==================================================================== DoD-2 */

describe("the search field filters the options (009 DoD-2)", () => {
  it("009 DoD-2: typing filters to case-insensitive substring matches of the option label, and clearing restores the full list in its original order", async () => {
    const user = userEvent.setup();
    const state = primePane();
    renderWithProviders(<ChatPane bookId={BOOK_ID} state={state} />);
    await user.click(modelButton());

    // Lower-case needle against the "OpenAI" half of the label: case-insensitive.
    await user.type(getSearch(), "openai");

    expect(isOptionRendered(OPT_OPENAI)).toBe(true);
    expect(isOptionRendered(OPT_GPT)).toBe(true);
    // A non-match is no longer RENDERED, not merely de-emphasised.
    expect(isOptionRendered(OPT_LOCAL)).toBe(false);

    // The needle also matches the model half of the label.
    await user.clear(getSearch());
    await user.type(getSearch(), "m-1");
    expect(isOptionRendered(OPT_LOCAL)).toBe(true);
    expect(isOptionRendered(OPT_OPENAI)).toBe(false);
    expect(isOptionRendered(OPT_GPT)).toBe(false);

    // An empty needle returns every option, in `modelOptions`' own order.
    await user.clear(getSearch());
    const local = optionRow(OPT_LOCAL);
    const openai = optionRow(OPT_OPENAI);
    const gpt = optionRow(OPT_GPT);
    expect(comesBefore(local, openai)).toBe(true);
    expect(comesBefore(openai, gpt)).toBe(true);
  });
});

/* ============================================================ DoD-3 · DoD-4 */

describe("picking a model closes the dropdown and moves the header label (009 DoD-3)", () => {
  it("009 DoD-3: clicking an option closes the dropdown and the header model button immediately shows that option", async () => {
    const user = userEvent.setup();
    const state = primePane();
    renderWithProviders(<ChatPane bookId={BOOK_ID} state={state} />);

    // The header starts on the stored pair.
    expect(modelButton().textContent ?? "").toContain("m-1");

    await user.click(modelButton());
    await user.click(optionRow(OPT_OPENAI));

    // Closed...
    expect(querySearch()).toBeNull();
    // ...and the name on top of the chat CHANGED.
    await waitFor(() => expect(modelButton().textContent ?? "").toContain("m-2"));
    expect(modelButton().textContent ?? "").not.toContain("m-1");
  });
});

describe("Enter picks the first option of the filtered list (009 DoD-4)", () => {
  it("009 DoD-4: Enter in the search field picks the first FILTERED option — dropdown closed, header updated, one update call", async () => {
    const user = userEvent.setup();
    const state = primePane();
    renderWithProviders(<ChatPane bookId={BOOK_ID} state={state} />);

    await user.click(modelButton());
    // `OPT_LOCAL` is first in the catalogue but filtered OUT, so a pick of `OPT_OPENAI`
    // can only come from the filtered list.
    await user.type(getSearch(), "openai");
    await user.keyboard("{Enter}");

    await waitFor(() => expect(vi.mocked(chatsApi.updateChat)).toHaveBeenCalledTimes(1));
    const call = vi.mocked(chatsApi.updateChat).mock.calls[0];
    expect(call[0]).toBe(BOOK_ID);
    expect(call[1]).toBe(CHAT_ID);
    expect(call[2].llm_server_id).toBe("s-2");
    expect(call[2].model_name).toBe("m-2");

    expect(querySearch()).toBeNull();
    expect(modelButton().textContent ?? "").toContain("m-2");
  });
});

/* ==================================================================== DoD-5 */

describe("Escape closes the dropdown and changes nothing (009 DoD-5)", () => {
  it("009 DoD-5: Escape closes the dropdown, leaves the header on the stored pair and issues no update call", async () => {
    const user = userEvent.setup();
    const state = primePane();
    renderWithProviders(<ChatPane bookId={BOOK_ID} state={state} />);

    await user.click(modelButton());
    expect(querySearch()).not.toBeNull();

    await user.keyboard("{Escape}");

    await waitFor(() => expect(querySearch()).toBeNull());
    // The model did NOT change, and nothing was persisted.
    expect(modelButton().textContent ?? "").toContain("m-1");
    expect(state.activeChat?.llm_server_id).toBe("s-1");
    expect(state.activeChat?.model_name).toBe("m-1");
    expect(vi.mocked(chatsApi.updateChat)).not.toHaveBeenCalled();
  });
});

/* ==================================================================== DoD-7 */

describe("a failed pick reverts the header and tells the author (009 DoD-7)", () => {
  it("009 DoD-7: when the update rejects, the header label reverts to the stored pair and an author-facing message is rendered with the dropdown closed", async () => {
    const user = userEvent.setup();
    const state = primePane();
    vi.mocked(chatsApi.updateChat).mockRejectedValue(new ApiError(400, "Bad request"));
    renderWithProviders(<ChatPane bookId={BOOK_ID} state={state} />);

    await user.click(modelButton());
    await user.click(optionRow(OPT_OPENAI));

    // The failure surfaces under the stable `"model"` key.
    await waitFor(() => expect(typeof state.serverErrors.model).toBe("string"));
    const message = state.serverErrors.model ?? "";
    expect(message.length).toBeGreaterThan(0);

    // The dropdown is already closed by the time the rejection lands...
    expect(querySearch()).toBeNull();
    // ...so the message has to be visible in the pane itself.
    expect(document.body.textContent ?? "").toContain(message);

    // And the label is back on what is actually stored.
    expect(state.activeChat?.llm_server_id).toBe("s-1");
    expect(state.activeChat?.model_name).toBe("m-1");
    expect(modelButton().textContent ?? "").toContain("m-1");
    expect(modelButton().textContent ?? "").not.toContain("m-2");
  });
});

/* =================================================================== DoD-10 */

describe("the three non-option dropdown states (009 DoD-10)", () => {
  it('009 DoD-10: an empty loaded catalogue still opens, shows exactly "No models available", and Enter picks nothing', async () => {
    const user = userEvent.setup();
    const state = primePane({ options: [] });
    renderWithProviders(<ChatPane bookId={BOOK_ID} state={state} />);

    await user.click(modelButton());

    // A dead button would be worse than a labelled empty state.
    expect(querySearch()).not.toBeNull();
    expect(screen.getByText("No models available")).toBeTruthy();

    await user.keyboard("{Enter}");
    expect(vi.mocked(chatsApi.updateChat)).not.toHaveBeenCalled();
  });

  it("009 DoD-10: a failed options load shows the modelOptionsError text in place of the list, and Enter picks nothing", async () => {
    const user = userEvent.setup();
    const state = primePane({
      options: [],
      optionsStatus: "error",
      optionsError: "Could not load model options",
    });
    renderWithProviders(<ChatPane bookId={BOOK_ID} state={state} />);

    await user.click(modelButton());

    expect(querySearch()).not.toBeNull();
    expect(screen.getByText("Could not load model options")).toBeTruthy();
    // The error line REPLACES the option list — it is not the empty-catalogue line.
    expect(screen.queryByText("No models available")).toBeNull();

    await user.keyboard("{Enter}");
    expect(vi.mocked(chatsApi.updateChat)).not.toHaveBeenCalled();
  });

  it('009 DoD-10: a needle that matches nothing shows exactly "Nothing found", and Enter picks nothing', async () => {
    const user = userEvent.setup();
    const state = primePane();
    renderWithProviders(<ChatPane bookId={BOOK_ID} state={state} />);

    await user.click(modelButton());
    await user.type(getSearch(), "zzz-no-such-model");

    expect(screen.getByText("Nothing found")).toBeTruthy();
    for (const option of ALL_OPTIONS) {
      expect(isOptionRendered(option)).toBe(false);
    }

    await user.keyboard("{Enter}");
    expect(vi.mocked(chatsApi.updateChat)).not.toHaveBeenCalled();
  });
});

/* =================================================================== DoD-11 */

describe("the openedPanel discriminator survives (009 DoD-11)", () => {
  it("009 DoD-11: opening the model dropdown takes the panel away from the settings popover, and moving the panel to settings closes the dropdown", async () => {
    const user = userEvent.setup();
    const state = primePane();
    runInAction(() => {
      state.openedPanel = "settings";
    });
    renderWithProviders(<ChatPane bookId={BOOK_ID} state={state} />);

    // With the settings popover open, the model dropdown is closed.
    expect(querySearch()).toBeNull();

    await user.click(modelButton());

    // Opening the dropdown closed the settings popover BY CONSTRUCTION: one panel.
    expect(state.openedPanel).toBe("model");
    expect(querySearch()).not.toBeNull();

    // And the mirror direction: the settings popover taking the panel closes the list.
    runInAction(() => {
      state.openedPanel = "settings";
    });
    await waitFor(() => expect(querySearch()).toBeNull());
    expect(isOptionRendered(OPT_OPENAI)).toBe(false);
  });
});

/* =================================================================== DoD-12 */

describe("the search needle never survives a close (009 DoD-12)", () => {
  it("009 DoD-12: a needle typed before a close does not reappear on the next open", async () => {
    const user = userEvent.setup();
    const state = primePane();
    renderWithProviders(<ChatPane bookId={BOOK_ID} state={state} />);

    await user.click(modelButton());
    await user.type(getSearch(), "openai");
    expect(isOptionRendered(OPT_LOCAL)).toBe(false);

    // Dismiss without picking...
    await user.keyboard("{Escape}");
    await waitFor(() => expect(querySearch()).toBeNull());

    // ...and reopen: an empty needle, and the whole catalogue back.
    await user.click(modelButton());

    expect(state.modelSearch).toBe("");
    expect((getSearch() as HTMLInputElement).value).toBe("");
    for (const option of ALL_OPTIONS) {
      expect(isOptionRendered(option)).toBe(true);
    }
  });
});

/* =================================================================== DoD-13 */

describe("opening the dropdown never refetches the catalogue (009 DoD-13)", () => {
  it("009 DoD-13: the list renders from the options loaded once at pane mount — opening triggers no model-options fetch", async () => {
    const user = userEvent.setup();
    const state = new ChatPaneState();
    vi.mocked(chatsApi.listChats).mockImplementation((_bookId, isArchived) =>
      Promise.resolve(isArchived ? [] : [makeChat()]),
    );
    vi.mocked(chatsApi.listModelOptions).mockResolvedValue(ALL_OPTIONS);

    await loadChatPane(state, BOOK_ID);
    const afterMount = vi.mocked(chatsApi.listModelOptions).mock.calls.length;
    expect(afterMount).toBe(1);

    renderWithProviders(<ChatPane bookId={BOOK_ID} state={state} />);
    await user.click(modelButton());

    // The options are on screen...
    for (const option of ALL_OPTIONS) {
      expect(isOptionRendered(option)).toBe(true);
    }
    // ...and not one of them cost a second request.
    expect(vi.mocked(chatsApi.listModelOptions).mock.calls.length).toBe(afterMount);
  });
});
