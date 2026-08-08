/**
 * Chats list page — 023.chat-ux-revision, DoD-7.
 *
 * Bound to the frozen signatures in status.md -> `## Skeleton` (023):
 *   class ChatsListPageState { chats; chatsStatus; chatsError; showArchived;
 *                              actionStatus; get isEmpty; get visibleChats }
 *   loadChats(state, bookId, signal?): Promise<void>
 *   archiveListChat(state, bookId, chatId, archived, signal?): Promise<void>
 *   const ChatsListPage = observer(function ChatsListPage() {…})   // NO props
 *   interface ChatPaneController { openChat: (chatId: string) => void }
 *   registerChatPaneController / unregisterChatPaneController / requestOpenChat
 *   api/chats: listChats(bookId, archived?, signal?) / updateChat(bookId, chatId, body, signal?)
 *
 * Every expected value comes from the SPEC -- `plan.md` -> DoD-7 (UC-082,
 * US-095.AC-2, US-096.AC-1/AC-2), its Interface section for `chatsListPageState.ts` /
 * `ChatsListPage.tsx`, and decision D5 -- never from code:
 *   - the page loads ITS OWN chats for the routed book (both the active and the
 *     archived set, merged, so `showArchived` is a client-side filter);
 *   - `visibleChats` is filtered by `showArchived`, most-recent-first;
 *   - picking a row opens that chat THROUGH THE REGISTERED PANE CONTROLLER and does
 *     NOT navigate — D5 chose the module registry precisely so the pane opens the
 *     chat without a route change;
 *   - archive/restore round-trips through the update call and flips the stored row.
 *
 * The page is mounted under its own `/:bookId/chats` route (the `CodexListPage`
 * precedent) rather than through the shell, so nothing but the page under test is on
 * screen. `../../src/api/chats` is mocked module-factory form (never `fetch`).
 * `globals: false`.
 */
import type { ReactElement } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { runInAction } from "mobx";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes, useLocation } from "react-router-dom";
import type { ChatResponse, ChatSamplingParams } from "../../src/types/chats";
import * as chatsApi from "../../src/api/chats";
import {
  ChatsListPageState,
  archiveListChat,
  loadChats,
} from "../../src/work/pages/chatsListPageState";
import { ChatsListPage } from "../../src/work/pages/ChatsListPage";
import {
  registerChatPaneController,
  unregisterChatPaneController,
  type ChatPaneController,
} from "../../src/work/chatPaneController";
import { renderWithProviders } from "../support/render";

// Whole-module factory: enumerate every export the page / state layer reaches.
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
    llm_server_id: "s-1",
    model_name: "m-1",
    sampling: makeSampling(),
    archived: false,
    created_at: modifiedAt,
    modified_at: modifiedAt,
    ...overrides,
  };
}

// Two active chats (most recent first is GAMMA) and one archived chat.
const GAMMA = makeChat("c-1", "Gamma chat", "2026-03-01T00:00:00Z");
const BETA = makeChat("c-2", "Beta chat", "2026-02-01T00:00:00Z");
const OLD_ONE = makeChat("c-9", "Retired chat", "2026-01-01T00:00:00Z", { archived: true });

/** Answer `listChats` by its `archived` flag, so a two-call load sees both sets. */
function mockList(active: ChatResponse[], archived: ChatResponse[] = []): void {
  vi.mocked(chatsApi.listChats).mockImplementation((_bookId, isArchived) =>
    Promise.resolve(isArchived ? archived : active),
  );
}

/** Reports the router's pathname, so the absence of navigation is observable. */
function LocationProbe(): ReactElement {
  const location = useLocation();
  return <span data-testid="pathname">{location.pathname}</span>;
}

/** Mount the page under its own route, beside a probe on the same router. */
function renderPage(): void {
  renderWithProviders(
    <>
      <Routes>
        <Route path="/:bookId/chats" element={<ChatsListPage />} />
      </Routes>
      <LocationProbe />
    </>,
    { route: `/${BOOK_ID}/chats` },
  );
}

/** Controllers registered by a test, unregistered again afterwards. */
let registered: ChatPaneController | null = null;

function installController(): ChatPaneController {
  const controller: ChatPaneController = { openChat: vi.fn() };
  registerChatPaneController(controller);
  registered = controller;
  return controller;
}

beforeEach(() => {
  mockList([GAMMA, BETA], [OLD_ONE]);
});

afterEach(() => {
  if (registered !== null) {
    unregisterChatPaneController(registered);
    registered = null;
  }
});

describe("the list page loads its own chats for the book (DoD-7)", () => {
  it("DoD-7: loadChats fetches the book's active AND archived sets, and visibleChats filters most-recent-first", async () => {
    const state = new ChatsListPageState();

    await loadChats(state, BOOK_ID);

    // Both sets were fetched for THIS book, so `showArchived` needs no refetch.
    const bookIds = vi.mocked(chatsApi.listChats).mock.calls.map((call) => call[0]);
    expect(bookIds.every((id) => id === BOOK_ID)).toBe(true);
    expect(state.chats.map((chat) => chat.id).sort()).toEqual(["c-1", "c-2", "c-9"]);
    expect(state.chatsStatus).toBe("ready");

    // Default view: the active chats, most recently modified first.
    expect(state.visibleChats.map((chat) => chat.id)).toEqual(["c-1", "c-2"]);
    expect(state.isEmpty).toBe(false);

    // Toggling is a CLIENT-SIDE filter over the already-loaded rows.
    const callsBefore = vi.mocked(chatsApi.listChats).mock.calls.length;
    runInAction(() => {
      state.showArchived = true;
    });
    expect(state.visibleChats.map((chat) => chat.id)).toEqual(["c-9"]);
    expect(vi.mocked(chatsApi.listChats).mock.calls.length).toBe(callsBefore);
  });

  it("DoD-7: mounting the page at /:bookId/chats loads that book's chats and renders their titles", async () => {
    renderPage();

    expect(await screen.findByText("Gamma chat")).toBeInTheDocument();
    expect(screen.getByText("Beta chat")).toBeInTheDocument();
    expect(vi.mocked(chatsApi.listChats).mock.calls[0][0]).toBe(BOOK_ID);
  });
});

describe("picking a row opens the chat in the pane, without navigating (DoD-7)", () => {
  it("DoD-7 (US-095.AC-2, D5): activating a row calls the registered controller's openChat for THAT chat and leaves the route unchanged", async () => {
    const user = userEvent.setup();
    const controller = installController();

    renderPage();
    // The second row is activated, so the id must be the row's own.
    await screen.findByText("Gamma chat");
    const target = screen.getByText("Beta chat");

    await user.click(target);

    expect(vi.mocked(controller.openChat)).toHaveBeenCalledTimes(1);
    expect(vi.mocked(controller.openChat)).toHaveBeenCalledWith("c-2");
    // The chat opens in the PANE: the content route does not move.
    expect(screen.getByTestId("pathname").textContent).toBe(`/${BOOK_ID}/chats`);
  });
});

describe("archive and restore round-trip from the list page (DoD-7)", () => {
  it("DoD-7 (UC-082, US-096.AC-1/AC-2): archiving then restoring a chat persists both ways and flips the stored row back", async () => {
    const state = new ChatsListPageState();
    await loadChats(state, BOOK_ID);
    expect(state.visibleChats.map((chat) => chat.id)).toEqual(["c-1", "c-2"]);

    // Archive: persisted, and the row leaves the active view.
    vi.mocked(chatsApi.updateChat).mockResolvedValue({ ...BETA, archived: true });
    await archiveListChat(state, BOOK_ID, "c-2", true);

    const archiveCall = vi.mocked(chatsApi.updateChat).mock.calls[0];
    expect(archiveCall[0]).toBe(BOOK_ID);
    expect(archiveCall[1]).toBe("c-2");
    expect(archiveCall[2].archived).toBe(true);
    expect(state.chats.find((chat) => chat.id === "c-2")?.archived).toBe(true);
    expect(state.visibleChats.map((chat) => chat.id)).toEqual(["c-1"]);

    // Restore: the round trip returns it to the active view, no duplicate row.
    vi.mocked(chatsApi.updateChat).mockResolvedValue({ ...BETA, archived: false });
    await archiveListChat(state, BOOK_ID, "c-2", false);

    const restoreCall = vi.mocked(chatsApi.updateChat).mock.calls[1];
    expect(restoreCall[1]).toBe("c-2");
    expect(restoreCall[2].archived).toBe(false);
    expect(state.chats.filter((chat) => chat.id === "c-2")).toHaveLength(1);
    expect(state.chats.find((chat) => chat.id === "c-2")?.archived).toBe(false);
    expect(state.visibleChats.map((chat) => chat.id)).toEqual(["c-1", "c-2"]);
  });
});
