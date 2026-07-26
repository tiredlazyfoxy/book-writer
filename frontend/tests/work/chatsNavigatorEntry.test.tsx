/**
 * Chats navigator entry + /chats redirect —
 * 011.chat-panel / 004.chat-pane-list-and-settings, DoD-5.
 *
 * Bound to the frozen signatures in status.md -> `## Skeleton` (step 004):
 *   interface WorkNavigatorProps { bookId: string; onShowChatList: () => void }
 *   const WorkNavigator = observer(...)   // reads the pathname to mark the active entry
 *   const WorkRoutes: FunctionComponent   // /:bookId shell + subject children;
 *                                          //   /chats now redirects to /:bookId/state
 *
 * Every expected value comes from the spec (`004.md` DoD-5, `004.context.md` -> "Why
 * the navigator entry is a control, not a link", US-095.AC-1 / UC-081 step 1 /
 * US-105.AC-3), never from code:
 *   - the Chats entry opens the pane's list by calling `onShowChatList`, and does NOT
 *     navigate — the content-pane route is unchanged;
 *   - the six content-pane entries are untouched — they still navigate and do not open
 *     the list;
 *   - `/work/:bookId/chats` no longer renders a chats view in the content pane: it
 *     redirects to the book-state route.
 *
 * `renderWithProviders` supplies the `MantineProvider`; the `route` option wraps the
 * tree in one basename-stripped `MemoryRouter` (`/bk-1/chats`, not `/work/bk-1/chats`),
 * shared by a `LocationProbe` so the route is observable. `api/books` + `api/chats` are
 * mocked module-factory form (never `fetch`); the shell subtree reads `getBookDetail`
 * (book load) and the chat pane's api. `globals: false`.
 */
import type { ReactElement } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useLocation } from "react-router-dom";
import type { BookDetailResponse } from "../../src/types/books";
import * as booksApi from "../../src/api/books";
import * as chatsApi from "../../src/api/chats";
import { WorkNavigator } from "../../src/work/components/shell/WorkNavigator";
import { WorkRoutes } from "../../src/work/routes";
import { renderWithProviders } from "../support/render";

// The shell load reads `getBookDetail`; the Book-state landing (the redirect target)
// also reads the two option arrays — supplied as their real spec-data pairs.
vi.mock("../../src/api/books", () => ({
  getBookDetail: vi.fn(),
  COLLABORATION_MODE_OPTIONS: [
    { value: "free", label: "Free" },
    { value: "proposal", label: "Proposal" },
  ],
  VISIBILITY_OPTIONS: [
    { value: "private", label: "Private" },
    { value: "public", label: "Public" },
  ],
}));

// The chat pane (owned by the shell) loads through this module — enumerate every export.
vi.mock("../../src/api/chats", () => ({
  listChats: vi.fn(),
  createChat: vi.fn(),
  updateChat: vi.fn(),
  getChat: vi.fn(),
  listModelOptions: vi.fn(),
}));

/** A fully-typed BookDetailResponse fixture; only the id matters here. */
function makeDetail(id: string): BookDetailResponse {
  return {
    id,
    owner_id: "u-1",
    title: "The Long Novel",
    description: "",
    collaboration_mode: "free",
    visibility: "private",
    state: "active",
    created_at: null,
    modified_at: null,
    members: [],
  };
}

/** Reports the router's current pathname, so navigation (or the lack of it) is observable. */
function LocationProbe(): ReactElement {
  const location = useLocation();
  return <span data-testid="pathname">{location.pathname}</span>;
}

beforeEach(() => {
  vi.mocked(booksApi.getBookDetail).mockResolvedValue(makeDetail("bk-1"));
  vi.mocked(chatsApi.listChats).mockResolvedValue([]);
  vi.mocked(chatsApi.listModelOptions).mockResolvedValue([]);
});

describe("the Chats navigator entry opens the list without navigating (DoD-5)", () => {
  it("DoD-5: clicking Chats calls onShowChatList and does not change the route (US-105.AC-3)", async () => {
    const user = userEvent.setup();
    const onShowChatList = vi.fn();

    renderWithProviders(
      <>
        <WorkNavigator bookId="bk-1" onShowChatList={onShowChatList} />
        <LocationProbe />
      </>,
      { route: "/bk-1/state" },
    );

    expect(screen.getByTestId("pathname").textContent).toBe("/bk-1/state");

    await user.click(screen.getByText("Chats"));

    // The list is a pane-state reveal, not a route change.
    expect(onShowChatList).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId("pathname").textContent).toBe("/bk-1/state");
  });

  it("DoD-5: the six content-pane entries are untouched — clicking Characters navigates and does not open the list", async () => {
    const user = userEvent.setup();
    const onShowChatList = vi.fn();

    renderWithProviders(
      <>
        <WorkNavigator bookId="bk-1" onShowChatList={onShowChatList} />
        <LocationProbe />
      </>,
      { route: "/bk-1/state" },
    );

    await user.click(screen.getByText("Characters"));

    expect(screen.getByTestId("pathname").textContent).toBe("/bk-1/characters");
    expect(onShowChatList).not.toHaveBeenCalled();
  });
});

describe("/:bookId/chats redirects out of the content pane (DoD-5)", () => {
  it("DoD-5: the chats route redirects to the book-state route and renders no chats view in the content pane", async () => {
    renderWithProviders(
      <>
        <WorkRoutes />
        <LocationProbe />
      </>,
      { route: "/bk-1/chats" },
    );

    // The deep link neither 404s nor lands a chat surface in the content pane: it redirects.
    await waitFor(() => expect(screen.getByTestId("pathname").textContent).toBe("/bk-1/state"));

    // No chats-owner placeholder inside the content pane (that content-pane surface is gone).
    const main = await screen.findByRole("main");
    expect(within(main).queryByText(/011\.chat-panel/)).toBeNull();
  });
});
