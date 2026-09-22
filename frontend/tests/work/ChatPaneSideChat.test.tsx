/**
 * Side-chat pane controls — 027.side-chats / 007.side-chat-pane-controls,
 * DoD-1 · DoD-2 · DoD-3 · DoD-4 · DoD-5 · DoD-6 · DoD-7 · DoD-8 · DoD-9.
 * (DoD-10 is `ComposerSideChatHint.test.tsx`'s; DoD-11 is [manual/live] — no test.)
 *
 * Renders `ChatPane` through `renderWithProviders` the way `ChatPane.test.tsx` and
 * `ChatModelPicker.test.tsx` do: the state is seeded directly via `runInAction` (chats /
 * activeChatId / messages / the three status trios / turnStatus), never through a load,
 * so the header renders without a loader and the api mock only ever sees the side-chat
 * calls the pane makes.
 *
 * Bound to the frozen step-007 interface (status.md -> `## Skeleton` -> "Step 007"):
 *   interface ChatPaneProps { bookId: string; state: ChatPaneState }
 *   the header slot: ONE control, `aria-label` "Start side chat" | "Finish side chat"
 *   the delete confirmation: a `role="dialog"` with buttons `Keep it` / `Delete side chat`
 *   the action error: an `Alert` rendering `sideChatActionError` while status is 'error'
 * and steps 004 / 005 for the state fields it reads:
 *   activeSideChatId (computed over the active chat's `active_side_chat_id`),
 *   sideChatActionStatus / sideChatActionError / sideChatDeleteConfirm (observables),
 *   canStartSideChat / canFinishSideChat (computeds, false while streaming — D1).
 * The api side is step 004's: chatsApi.startSideChat(bookId, chatId, signal?),
 *   finishSideChat(bookId, chatId, sideChatId, signal?), deleteSideChat(bookId, chatId,
 *   sideChatId, signal?), getChat(bookId, chatId, signal?).
 *
 * Every expected value comes from the SPEC (`007.side-chat-pane-controls.md` -> DoD +
 * Interface intent; `context.md` D-F), never from code:
 *   - a null pointer shows `Start side chat` and NO `Finish side chat`; a set pointer —
 *     as after a reload, no client memory — shows the reverse (DoD-1, DoD-2; UC-110,
 *     US-141.AC-1);
 *   - both are disabled while `turnStatus === "streaming"`, enabled when idle (DoD-3,
 *     DoD-4; US-135.AC-3, UC-111 exception flow / D1);
 *   - a click on Start calls the start api once with the active chat id; on Finish, the
 *     finish api once with the active chat id and the active side-chat id (DoD-5);
 *   - with `sideChatDeleteConfirm` set, a dialog says the messages are removed
 *     permanently and that saved work is kept, with `Keep it` and `Delete side chat`;
 *     with `null`, no dialog (DoD-6; US-140.AC-1);
 *   - `Keep it` closes it, calls no api, leaves `messages` / `chats` unchanged (DoD-7;
 *     US-140.AC-2);
 *   - the dialog's `Delete side chat` calls the delete api once with the pending id
 *     (DoD-8; US-140.AC-3);
 *   - status 'error' renders the error text; 'idle' renders no such alert (DoD-9; D-F).
 *
 * Query discipline (skeleton record): controls by role + accessible name; the dialog by
 * `role="dialog"` and its buttons `within(dialog)` — `Delete side chat` is ALSO the name
 * of step 006's per-group icon; the error banner by its TEXT, never by role/name, because
 * the pane's other `Alert`s share `role="alert"` and the banner's title is not frozen.
 *
 * `../../src/api/chats` is mocked module-factory form with EVERY export (step 004's
 * eleven) — never `fetch`. `globals: false`.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { runInAction } from "mobx";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type {
  ChatDetailResponse,
  ChatMessageResponse,
  ChatResponse,
  ChatSamplingParams,
} from "../../src/types/chats";
import { ChatPaneState } from "../../src/work/components/chat/chatPaneState";
import { ChatPane } from "../../src/work/components/chat/ChatPane";
import { renderWithProviders } from "../support/render";

// The whole api module, EVERY export enumerated (step 004's list, `getChat` included —
// the delete effect reloads through it).
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
const SIDE_ID = "sc-9";

const START_NAME = "Start side chat";
const FINISH_NAME = "Finish side chat";
const KEEP_NAME = "Keep it";
const DELETE_NAME = "Delete side chat";

/* ------------------------------------------------------------------ fixtures */

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

/** The active chat; `activeSideChatId` is the server pointer under test. */
function makeChat(activeSideChatId: string | null): ChatResponse {
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
    active_side_chat_id: activeSideChatId,
  };
}

/** A main-line row (no side-chat stamp), so no group renders in the transcript. */
function makeMessage(id: string, position: number, role: "user" | "assistant"): ChatMessageResponse {
  return {
    id,
    chat_id: CHAT_ID,
    role,
    content: `content of ${id}`,
    reasoning: null,
    position,
    created_at: "2026-01-01T00:00:00Z",
    side_chat_id: null,
    tool_trace: null,
  };
}

const MAIN_LINE: ChatMessageResponse[] = [
  makeMessage("m-0", 0, "user"),
  makeMessage("m-1", 1, "assistant"),
];

interface PrimeOptions {
  activeSideChatId?: string | null;
  turnStatus?: "idle" | "streaming";
  messages?: ChatMessageResponse[];
}

/**
 * A pane with an active chat, a ready message history, a ready (empty) model catalogue
 * and an idle turn — the header renders with no loader. The side-chat pointer is what
 * each case varies.
 */
function primePane(overrides: PrimeOptions = {}): ChatPaneState {
  const { activeSideChatId = null, turnStatus = "idle", messages = MAIN_LINE } = overrides;
  const state = new ChatPaneState();
  runInAction(() => {
    state.chats = [makeChat(activeSideChatId)];
    state.chatsStatus = "ready";
    state.activeChatId = CHAT_ID;
    state.modelOptions = [];
    state.modelOptionsStatus = "ready";
    state.modelOptionsError = null;
    state.messages = messages;
    state.messagesStatus = "ready";
    state.turnStatus = turnStatus;
    state.turnError = null;
  });
  return state;
}

function renderPane(state: ChatPaneState): void {
  renderWithProviders(<ChatPane bookId={BOOK_ID} state={state} />);
}

function queryStart(): HTMLElement | null {
  return screen.queryByRole("button", { name: START_NAME });
}

function queryFinish(): HTMLElement | null {
  return screen.queryByRole("button", { name: FINISH_NAME });
}

/** Total number of calls across every api function the pane's actions may reach. */
function apiCallCount(): number {
  return (
    vi.mocked(chatsApi.startSideChat).mock.calls.length +
    vi.mocked(chatsApi.finishSideChat).mock.calls.length +
    vi.mocked(chatsApi.injectSideChat).mock.calls.length +
    vi.mocked(chatsApi.deleteSideChat).mock.calls.length +
    vi.mocked(chatsApi.getChat).mock.calls.length +
    vi.mocked(chatsApi.updateChat).mock.calls.length +
    vi.mocked(chatsApi.createChat).mock.calls.length +
    vi.mocked(chatsApi.listChats).mock.calls.length +
    vi.mocked(chatsApi.titleChat).mock.calls.length +
    vi.mocked(chatsApi.streamChatTurn).mock.calls.length
  );
}

beforeEach(() => {
  // `restoreMocks` wipes implementations between tests — benign defaults so nothing the
  // pane might touch on render resolves to `undefined`.
  window.localStorage.clear();
  vi.mocked(chatsApi.listChats).mockResolvedValue([]);
  vi.mocked(chatsApi.listModelOptions).mockResolvedValue([]);
  vi.mocked(chatsApi.titleChat).mockResolvedValue({ title: "Chat one", changed: false });
  vi.mocked(chatsApi.streamChatTurn).mockResolvedValue(new AbortController());
});

/* ==================================================================== DoD-1 */

describe("no side chat active: the header offers Start, never Finish (DoD-1)", () => {
  it("DoD-1: with the active chat's active_side_chat_id null, a control named 'Start side chat' is present and no 'Finish side chat' control exists (UC-110 precondition)", () => {
    const state = primePane({ activeSideChatId: null });

    renderPane(state);

    // Presence first: the Start control is there...
    expect(screen.getByRole("button", { name: START_NAME })).toBeInTheDocument();
    // ...and only then the negative: the slot is ONE control, swapping, never both.
    expect(queryFinish()).toBeNull();
    expect(screen.getAllByRole("button", { name: START_NAME })).toHaveLength(1);
  });
});

/* ==================================================================== DoD-2 */

describe("a side chat active on the server: the header offers Finish, never Start (DoD-2)", () => {
  it("DoD-2: with the active chat's active_side_chat_id set — as after a reload, no client memory — a control named 'Finish side chat' is present and no 'Start side chat' control exists (US-141.AC-1, UC-114 step 3)", () => {
    // The pointer arrives on the chat itself; nothing was written client-side first.
    const state = primePane({ activeSideChatId: SIDE_ID });
    expect(window.localStorage.length).toBe(0);

    renderPane(state);

    expect(screen.getByRole("button", { name: FINISH_NAME })).toBeInTheDocument();
    expect(queryStart()).toBeNull();
    expect(screen.getAllByRole("button", { name: FINISH_NAME })).toHaveLength(1);
  });
});

/* ==================================================================== DoD-3 */

describe("Start side chat follows the turn state (DoD-3)", () => {
  it("DoD-3: 'Start side chat' is disabled while turnStatus === 'streaming' (US-135.AC-3)", () => {
    const state = primePane({ activeSideChatId: null, turnStatus: "streaming" });

    renderPane(state);

    expect(screen.getByRole("button", { name: START_NAME })).toBeDisabled();
  });

  it("DoD-3: 'Start side chat' is enabled when the turn is idle", () => {
    const state = primePane({ activeSideChatId: null, turnStatus: "idle" });

    renderPane(state);

    expect(screen.getByRole("button", { name: START_NAME })).toBeEnabled();
  });
});

/* ==================================================================== DoD-4 */

describe("Finish side chat follows the turn state (DoD-4)", () => {
  it("DoD-4: 'Finish side chat' is disabled while turnStatus === 'streaming' (UC-111 exception flow — D1)", () => {
    const state = primePane({ activeSideChatId: SIDE_ID, turnStatus: "streaming" });

    renderPane(state);

    expect(screen.getByRole("button", { name: FINISH_NAME })).toBeDisabled();
  });

  it("DoD-4: 'Finish side chat' is enabled when the turn is idle", () => {
    const state = primePane({ activeSideChatId: SIDE_ID, turnStatus: "idle" });

    renderPane(state);

    expect(screen.getByRole("button", { name: FINISH_NAME })).toBeEnabled();
  });
});

/* ==================================================================== DoD-5 */

describe("the header slot reaches the api (DoD-5)", () => {
  it("DoD-5: clicking 'Start side chat' calls the start api once with the book id and the active chat id, and the slot then shows what the server returned (UC-110 step 1)", async () => {
    const user = userEvent.setup();
    const state = primePane({ activeSideChatId: null });
    vi.mocked(chatsApi.startSideChat).mockResolvedValue(makeChat(SIDE_ID));

    renderPane(state);

    await user.click(screen.getByRole("button", { name: START_NAME }));

    await waitFor(() => {
      expect(vi.mocked(chatsApi.startSideChat)).toHaveBeenCalledTimes(1);
    });
    const [bookArg, chatArg] = vi.mocked(chatsApi.startSideChat).mock.calls[0];
    expect(bookArg).toBe(BOOK_ID);
    expect(chatArg).toBe(CHAT_ID);
    // Only the start api — no finish, no delete, no reload.
    expect(vi.mocked(chatsApi.finishSideChat)).not.toHaveBeenCalled();
    expect(vi.mocked(chatsApi.deleteSideChat)).not.toHaveBeenCalled();
    expect(vi.mocked(chatsApi.getChat)).not.toHaveBeenCalled();

    // The pane reflects the server's pointer: the one slot swapped to Finish.
    await screen.findByRole("button", { name: FINISH_NAME });
    expect(queryStart()).toBeNull();
  });

  it("DoD-5: clicking 'Finish side chat' calls the finish api once with the book id, the active chat id and the active side-chat id, and the slot swaps back to Start (UC-111 step 1)", async () => {
    const user = userEvent.setup();
    const state = primePane({ activeSideChatId: SIDE_ID });
    vi.mocked(chatsApi.finishSideChat).mockResolvedValue(makeChat(null));

    renderPane(state);

    await user.click(screen.getByRole("button", { name: FINISH_NAME }));

    await waitFor(() => {
      expect(vi.mocked(chatsApi.finishSideChat)).toHaveBeenCalledTimes(1);
    });
    const [bookArg, chatArg, sideArg] = vi.mocked(chatsApi.finishSideChat).mock.calls[0];
    expect(bookArg).toBe(BOOK_ID);
    expect(chatArg).toBe(CHAT_ID);
    expect(sideArg).toBe(SIDE_ID);
    expect(vi.mocked(chatsApi.startSideChat)).not.toHaveBeenCalled();
    expect(vi.mocked(chatsApi.deleteSideChat)).not.toHaveBeenCalled();

    await screen.findByRole("button", { name: START_NAME });
    expect(queryFinish()).toBeNull();
  });
});

/* ==================================================================== DoD-6 */

describe("the delete confirmation dialog (DoD-6)", () => {
  it("DoD-6: with sideChatDeleteConfirm set, a dialog is open whose text says the messages are removed permanently and that saved work is kept, with 'Keep it' and 'Delete side chat' buttons (US-140.AC-1)", async () => {
    const state = primePane({ activeSideChatId: null });
    runInAction(() => {
      state.sideChatDeleteConfirm = SIDE_ID;
    });

    renderPane(state);

    const dialog = await screen.findByRole("dialog");
    // The body's two promises, as substrings — the exact sentences are the coder's.
    expect(dialog).toHaveTextContent(/permanently/i);
    expect(dialog).toHaveTextContent(/kept/i);
    // Its two controls, exact labels, located INSIDE the dialog.
    expect(within(dialog).getByRole("button", { name: KEEP_NAME })).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: DELETE_NAME })).toBeInTheDocument();
    // Opening the confirmation alone reaches no api.
    expect(apiCallCount()).toBe(0);
  });

  it("DoD-6: with sideChatDeleteConfirm null, no dialog is rendered", () => {
    const state = primePane({ activeSideChatId: null });
    expect(state.sideChatDeleteConfirm).toBeNull();

    renderPane(state);

    expect(screen.queryByRole("dialog")).toBeNull();
    expect(screen.queryByRole("button", { name: KEEP_NAME })).toBeNull();
  });
});

/* ==================================================================== DoD-7 */

describe("Keep it dismisses without consequence (DoD-7)", () => {
  it("DoD-7: clicking 'Keep it' closes the dialog, clears sideChatDeleteConfirm, calls NO api, and leaves messages and chats unchanged (US-140.AC-2)", async () => {
    const user = userEvent.setup();
    const state = primePane({ activeSideChatId: null });
    runInAction(() => {
      state.sideChatDeleteConfirm = SIDE_ID;
    });
    const messagesBefore = state.messages;
    const chatsBefore = state.chats;
    const messagesSnapshot = state.messages.slice();
    const chatsSnapshot = state.chats.slice();

    renderPane(state);

    // Presence first: the dialog is really open before it is dismissed.
    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: KEEP_NAME }));

    await waitFor(() => {
      expect(screen.queryByRole("dialog")).toBeNull();
    });
    expect(state.sideChatDeleteConfirm).toBeNull();

    // No api of any kind — not delete, not a reload.
    expect(apiCallCount()).toBe(0);
    expect(vi.mocked(chatsApi.deleteSideChat)).not.toHaveBeenCalled();
    expect(vi.mocked(chatsApi.getChat)).not.toHaveBeenCalled();

    // The transcript and the chat list are exactly what they were.
    expect(state.messages).toBe(messagesBefore);
    expect(state.chats).toBe(chatsBefore);
    expect(state.messages.slice()).toEqual(messagesSnapshot);
    expect(state.chats.slice()).toEqual(chatsSnapshot);
    expect(state.messages).toHaveLength(2);
  });
});

/* ==================================================================== DoD-8 */

describe("Delete side chat in the dialog is the trigger (DoD-8)", () => {
  it("DoD-8: clicking the dialog's 'Delete side chat' calls the delete api once with the book id, the active chat id and the pending side-chat id (US-140.AC-3)", async () => {
    const user = userEvent.setup();
    const state = primePane({ activeSideChatId: null });
    runInAction(() => {
      state.sideChatDeleteConfirm = SIDE_ID;
    });
    const reloaded: ChatDetailResponse = {
      chat: makeChat(null),
      messages: MAIN_LINE,
    };
    vi.mocked(chatsApi.deleteSideChat).mockResolvedValue(undefined);
    vi.mocked(chatsApi.getChat).mockResolvedValue(reloaded);

    renderPane(state);

    const dialog = await screen.findByRole("dialog");
    // `within(dialog)`: the same name belongs to step 006's per-group icon elsewhere.
    await user.click(within(dialog).getByRole("button", { name: DELETE_NAME }));

    await waitFor(() => {
      expect(vi.mocked(chatsApi.deleteSideChat)).toHaveBeenCalledTimes(1);
    });
    const [bookArg, chatArg, sideArg] = vi.mocked(chatsApi.deleteSideChat).mock.calls[0];
    expect(bookArg).toBe(BOOK_ID);
    expect(chatArg).toBe(CHAT_ID);
    expect(sideArg).toBe(SIDE_ID);
    // The confirm is a delete, not a start / finish / inject.
    expect(vi.mocked(chatsApi.startSideChat)).not.toHaveBeenCalled();
    expect(vi.mocked(chatsApi.finishSideChat)).not.toHaveBeenCalled();
    expect(vi.mocked(chatsApi.injectSideChat)).not.toHaveBeenCalled();

    // The pending slot is cleared once the action has run, so the dialog goes away.
    await waitFor(() => {
      expect(state.sideChatDeleteConfirm).toBeNull();
    });
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).toBeNull();
    });
  });
});

/* ==================================================================== DoD-9 */

describe("the action error banner (DoD-9)", () => {
  const REFUSAL = "Side chat already active.";

  it("DoD-9: with sideChatActionStatus 'error', an alert containing sideChatActionError's text is rendered (D-F)", () => {
    const state = primePane({ activeSideChatId: null });
    runInAction(() => {
      state.sideChatActionStatus = "error";
      state.sideChatActionError = REFUSAL;
    });

    renderPane(state);

    // By TEXT: the pane's other alerts share `role="alert"` and the banner's title is
    // not frozen, so the text is the contract.
    expect(screen.getByText(REFUSAL)).toBeInTheDocument();
  });

  it("DoD-9: with sideChatActionStatus 'idle', no such alert exists", () => {
    const state = primePane({ activeSideChatId: null });
    runInAction(() => {
      state.sideChatActionStatus = "idle";
      state.sideChatActionError = null;
    });

    renderPane(state);

    expect(screen.queryByText(REFUSAL)).toBeNull();
  });

  it("DoD-9: the banner shows the error's own text, not a fixed string — a different message renders that message", () => {
    const other = "Side chat not found.";
    const state = primePane({ activeSideChatId: null });
    runInAction(() => {
      state.sideChatActionStatus = "error";
      state.sideChatActionError = other;
    });

    renderPane(state);

    expect(screen.getByText(other)).toBeInTheDocument();
    expect(screen.queryByText(REFUSAL)).toBeNull();
  });
});
