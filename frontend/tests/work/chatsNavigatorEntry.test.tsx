/**
 * Chats navigator entry -> the /chats content-pane route.
 * Retargeted by 023.chat-ux-revision (design-note D12), DoD-8.
 *
 * This spec previously asserted 011's arrangement — the Chats entry called
 * `onShowChatList` without navigating, and `/:bookId/chats` redirected to the
 * book-state route. 023 inverts both deliberately, so the file is rewritten against
 * the new contract rather than weakened to keep the old one passing.
 *
 * Bound to the frozen signatures in status.md -> `## Skeleton` (023):
 *   interface WorkNavigatorProps { bookId: string; collapsed?: boolean }
 *   const ChatsListPage = observer(function ChatsListPage() {…})   // no props
 *   const WorkRoutes: FunctionComponent   // /:bookId shell + subject children;
 *                                         //   /chats renders the chats LIST PAGE
 *
 * Every expected value comes from the SPEC -- `plan.md` -> DoD-8 (and DoD-11's
 * companion `[verify]` clause: `ChatsRedirectRoute` is gone), the Interface section
 * for `routes.tsx` / `navItems.ts` / `WorkNavigator.tsx` -- never from code:
 *   - the Chats entry navigates to `/:bookId/chats` like every sibling entry;
 *   - that route RENDERS the chats list page in the content pane; it does not
 *     redirect anywhere;
 *   - the chat pane renders no chat list any more (chat management lives only on the
 *     list page) — asserted here at the whole-page level, inside the `complementary`
 *     landmark.
 * `plan.md` -> DoD-8 records that this knowingly contradicts US-105.AC-3 /
 * US-095.AC-1 / UC-081 step 1; `outcome.md` item 1 carries the reconciliation.
 *
 * `renderWithProviders` supplies the `MantineProvider`; the `route` option wraps the
 * tree in one basename-stripped `MemoryRouter`, shared by a `LocationProbe` so the
 * route is observable. `api/books` + `api/chats` (+ the continuity/flag reads the
 * work surfaces make on mount) are mocked module-factory form, never `fetch`.
 * `globals: false`.
 */
import type { ReactElement } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useLocation } from "react-router-dom";
import type { BookDetailResponse } from "../../src/types/books";
import type { ChatResponse, ChatSamplingParams } from "../../src/types/chats";
import * as booksApi from "../../src/api/books";
import * as chatsApi from "../../src/api/chats";
import * as flagsApi from "../../src/api/flags";
import * as continuityApi from "../../src/api/continuity";
import { WorkNavigator } from "../../src/work/components/shell/WorkNavigator";
import { WorkRoutes } from "../../src/work/routes";
import { renderWithProviders } from "../support/render";

// The shell load reads `getBookDetail`; the Book-state surface also reads the two
// option arrays — supplied as their real spec-data pairs — and, since
// 021.per-author-system-prompt / step 006, the caller's own prompt through the two
// prompt exports. A factory that omits one strips it to `undefined`, so all of them
// are enumerated.
vi.mock("../../src/api/books", () => ({
  getBookDetail: vi.fn(),
  getOwnSystemPrompt: vi.fn(),
  updateOwnSystemPrompt: vi.fn(),
  COLLABORATION_MODE_OPTIONS: [
    { value: "free", label: "Free" },
    { value: "proposal", label: "Proposal" },
  ],
  VISIBILITY_OPTIONS: [
    { value: "private", label: "Private" },
    { value: "public", label: "Public" },
  ],
}));

// The chat pane (owned by the shell) and the chats list page both load through this
// module — enumerate every export, including 023's `titleChat`.
vi.mock("../../src/api/chats", () => ({
  listChats: vi.fn(),
  createChat: vi.fn(),
  updateChat: vi.fn(),
  getChat: vi.fn(),
  listModelOptions: vi.fn(),
  streamChatTurn: vi.fn(),
  titleChat: vi.fn(),
}));

// HARNESS ONLY, added by `016.chapter-close-continuity`: the work surfaces this file
// mounts read continuity data on mount. Whole-module factories (never `fetch`), armed
// with EMPTY fixtures in `beforeEach`. NOTHING in this file asserts on either module.
vi.mock("../../src/api/flags", () => ({
  listFlags: vi.fn(),
  raiseFlag: vi.fn(),
  resolveFlag: vi.fn(),
}));

vi.mock("../../src/api/continuity", () => ({
  getStateNotes: vi.fn(),
  updateStateNotes: vi.fn(),
  getBookContinuity: vi.fn(),
  getChapterChangeset: vi.fn(),
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

function makeChat(id: string, title: string, modifiedAt: string): ChatResponse {
  return {
    id,
    book_id: "bk-1",
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

// Two chats the author owns; the list page must show BOTH, the pane header only the
// active one — which is what makes "no chat list in the pane" observable.
const GAMMA = makeChat("c-1", "Gamma chat", "2026-03-01T00:00:00Z");
const BETA = makeChat("c-2", "Beta chat", "2026-02-01T00:00:00Z");

/** Reports the router's current pathname, so navigation (or a redirect) is observable. */
function LocationProbe(): ReactElement {
  const location = useLocation();
  return <span data-testid="pathname">{location.pathname}</span>;
}

/** HARNESS ONLY: every continuity read the work surfaces make on mount, answered empty. */
function armContinuityReads(): void {
  vi.mocked(continuityApi.getStateNotes).mockResolvedValue({
    book_id: "bk-1",
    active_notes: "",
    modified_at: null,
  });
  vi.mocked(continuityApi.updateStateNotes).mockResolvedValue({
    book_id: "bk-1",
    active_notes: "",
    modified_at: null,
  });
  vi.mocked(continuityApi.getBookContinuity).mockResolvedValue({ items: [] });
  vi.mocked(flagsApi.listFlags).mockResolvedValue({ items: [] });
  vi.mocked(continuityApi.getChapterChangeset).mockResolvedValue({
    chapter_id: "ch-1",
    added: "",
    modified: "",
    deleted: "",
    status: null,
    created_at: null,
    modified_at: null,
  });
}

beforeEach(() => {
  window.localStorage.clear();
  vi.mocked(booksApi.getBookDetail).mockResolvedValue(makeDetail("bk-1"));
  armContinuityReads();
  vi.mocked(booksApi.getOwnSystemPrompt).mockResolvedValue({
    book_id: "bk-1",
    system_prompt: "",
    modified_at: null,
  });
  vi.mocked(booksApi.updateOwnSystemPrompt).mockResolvedValue({
    book_id: "bk-1",
    system_prompt: "",
    modified_at: null,
  });
  vi.mocked(chatsApi.listChats).mockImplementation((_bookId, isArchived) =>
    Promise.resolve(isArchived ? [] : [GAMMA, BETA]),
  );
  vi.mocked(chatsApi.listModelOptions).mockResolvedValue([]);
  vi.mocked(chatsApi.getChat).mockResolvedValue({ chat: GAMMA, messages: [] });
});

describe("the Chats navigator entry opens the chats route (DoD-8)", () => {
  it("DoD-8: clicking Chats navigates to /:bookId/chats", async () => {
    const user = userEvent.setup();

    renderWithProviders(
      <>
        <WorkNavigator bookId="bk-1" />
        <LocationProbe />
      </>,
      { route: "/bk-1/state" },
    );

    expect(screen.getByTestId("pathname").textContent).toBe("/bk-1/state");

    await user.click(screen.getByRole("link", { name: "Chats" }));

    expect(screen.getByTestId("pathname").textContent).toBe("/bk-1/chats");
  });
});

describe("/:bookId/chats renders the list page in the content pane (DoD-8)", () => {
  it("DoD-8: the chats route lands the list page and does NOT redirect", async () => {
    renderWithProviders(
      <>
        <WorkRoutes />
        <LocationProbe />
      </>,
      { route: "/bk-1/chats" },
    );

    const main = await screen.findByRole("main");
    // The author's chats are listed IN THE CONTENT PANE...
    expect(await within(main).findByText("Gamma chat")).toBeInTheDocument();
    expect(within(main).getByText("Beta chat")).toBeInTheDocument();

    // ...and the deep link stayed put: no redirect to the book-state route.
    expect(screen.getByTestId("pathname").textContent).toBe("/bk-1/chats");
  });

  it("DoD-8: the chat pane renders no chat list — only the active chat, management having moved to the page", async () => {
    renderWithProviders(<WorkRoutes />, { route: "/bk-1/chats" });

    // Wait until the pane has loaded and resolved an active chat.
    const aside = await screen.findByRole("complementary");
    await waitFor(() => expect(within(aside).getByText("Gamma chat")).toBeInTheDocument());

    // The OTHER chat is nowhere in the pane: there is no list to pick from there.
    expect(within(aside).queryByText("Beta chat")).toBeNull();
  });
});
