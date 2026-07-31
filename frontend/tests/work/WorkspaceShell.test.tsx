/**
 * Workspace shell — 010.working-page / 002.workspace-shell, DoD-4 · DoD-5 · DoD-6 · DoD-7.
 *
 * Bound to the frozen signatures in status.md -> `## Skeleton` (step 002):
 *   const WorkspaceShell: FunctionComponent   // observer, no props; reads :bookId via router
 *   class WorkspaceShellState { bookDetail; bookDetailStatus; bookDetailError; navbarOpened }
 *   loadWorkspaceBook(state, bookId, signal?) : Promise<void>   // calls getBookDetail
 *
 * The shell reads `:bookId` from the router, so it is mounted under a
 * `Route path="/:bookId"` with nested subject routes; the shell renders `<Outlet/>`
 * in its content pane, so the nested child appears there. Routes are
 * basename-stripped (`/bk-1/state`, not `/work/bk-1/state`).
 *
 * The book load goes through `api/books.getBookDetail`, mocked module-factory form
 * (never `fetch`). The shell's subtree reaches only `getBookDetail` from that module,
 * so the `api/books` factory supplies that one export. Under 011.chat-panel / 004 the
 * shell also owns a `ChatPaneState` and starts a chat load in its mount effect, so
 * `api/chats` is mocked module-factory form too (every export enumerated, the two
 * list calls resolving empty) — no real fetch, no unhandled rejection. Errors are
 * constructed as the real `ApiError` from `api/client` — the 403/404 a non-member
 * receives.
 *
 * Expected values come from the spec: the title is whatever the mocked detail
 * carries (DoD-5); the chat-pane slot is the third region and, per 004's Interface
 * intent for `ChatPaneSlot`/`WorkspaceShell`, no longer renders an "owned by
 * 011.chat-panel" notice (retarget 2026-07-26); a failed load replaces the workspace
 * content without crashing or rendering blank (DoD-6); one book id yields exactly one
 * book load across a subject navigation (DoD-7).
 *
 * `globals: false`: every primitive is imported explicitly.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router-dom";
import type { BookDetailResponse } from "../../src/types/books";
import { ApiError } from "../../src/api/client";
import * as booksApi from "../../src/api/books";
import * as chatsApi from "../../src/api/chats";
import * as flagsApi from "../../src/api/flags";
import * as continuityApi from "../../src/api/continuity";

// HARNESS ONLY, added by `016.chapter-close-continuity`: the work surfaces this file
// mounts now read continuity data on mount — the Book-state landing reads the book's
// state notes and its per-chapter continuity, and a chapter surface reads that chapter's
// warnings and note changeset (`plan.md` -> Interface for `bookStatePageState.ts` /
// `chapterPageState.ts`). Whole-module factories (never `fetch`), armed with EMPTY
// fixtures in `beforeEach`, so those loads resolve locally instead of reaching the real
// HTTP client and leaving rejected promises behind. `vi.mock` is hoisted, so declaring
// these beside the imports they pair with is equivalent to declaring them below.
// NOTHING in this file asserts on either module — no assertion here changed.
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

/**
 * HARNESS ONLY (`016.chapter-close-continuity`): every continuity read the work surfaces
 * make on mount, answered with EMPTY fixtures. Nothing here is asserted on — the
 * Book-state surface's own content is on `plan.md` -> Test plan -> "Not tested
 * (deliberate)".
 */
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
import { WorkspaceShell } from "../../src/work/components/shell/WorkspaceShell";
import { renderWithProviders } from "../support/render";

// A module-factory mock replaces the WHOLE module. The shell's render subtree
// reaches only `getBookDetail` from `api/books` (the navigator resolves paths
// locally) — so that single export is all the factory must supply.
vi.mock("../../src/api/books", () => ({
  getBookDetail: vi.fn(),
}));

// The shell now owns the chat pane and starts a chat load on mount, reading through
// this module — enumerate every export it imports so no real fetch fires.
vi.mock("../../src/api/chats", () => ({
  listChats: vi.fn(),
  createChat: vi.fn(),
  updateChat: vi.fn(),
  getChat: vi.fn(),
  listModelOptions: vi.fn(),
}));

const BOOK_TITLE = "The Long Novel";

/** A fully-typed BookDetailResponse fixture; only id + title vary. */
function makeDetail(id: string, title: string): BookDetailResponse {
  return {
    id,
    owner_id: "u-1",
    title,
    description: "",
    collaboration_mode: "free",
    visibility: "private",
    state: "active",
    created_at: null,
    modified_at: null,
    members: [],
  };
}

/**
 * Mounts the shell under a `:bookId` route with two nested subject views, so the
 * shell's `<Outlet/>` has something to render and navigation between subjects can
 * be exercised.
 */
function renderShell(route: string): void {
  renderWithProviders(
    <Routes>
      <Route path="/:bookId" element={<WorkspaceShell />}>
        <Route path="state" element={<div data-testid="subject-state">state subject</div>} />
        <Route
          path="chapters"
          element={<div data-testid="subject-chapters">chapters subject</div>}
        />
      </Route>
    </Routes>,
    { route },
  );
}

beforeEach(() => {
  armContinuityReads();
  // `restoreMocks` wipes the implementation between tests — default to a resolved
  // detail; individual tests override for pending / rejected cases.
  vi.mocked(booksApi.getBookDetail).mockResolvedValue(makeDetail("bk-1", BOOK_TITLE));
  // The shell's chat-pane load resolves empty (no chats, no model options) so the
  // mount effect does not fire a real fetch or throw an unhandled rejection.
  vi.mocked(chatsApi.listChats).mockResolvedValue([]);
  vi.mocked(chatsApi.listModelOptions).mockResolvedValue([]);
});

describe("WorkspaceShell", () => {
  it("DoD-4: renders all three regions — navigator, content pane with the nested outlet, and the chat-pane region (no 011.chat-panel owner notice)", async () => {
    renderShell("/bk-1/state");

    // The nested-route outlet renders inside the content pane (the main landmark).
    const outletContent = await screen.findByTestId("subject-state");
    expect(within(screen.getByRole("main")).getByTestId("subject-state")).toBe(outletContent);

    // The navigator is present (its Book state entry is one of its links).
    expect(screen.getByRole("link", { name: "Book state" })).toBeInTheDocument();

    // The third region — the chat-pane slot — is present as the aside landmark, and
    // (per 004's Interface intent) no longer renders an "owned by 011.chat-panel"
    // notice: that slot placeholder is removed.
    expect(screen.getByRole("complementary")).toBeInTheDocument();
    expect(screen.queryByText(/011\.chat-panel/)).toBeNull();
  });

  it("DoD-5: loads the book exactly once and renders its title, showing no title while the load is pending", async () => {
    let resolveBook: (detail: BookDetailResponse) => void = () => {};
    const pending = new Promise<BookDetailResponse>((resolve) => {
      resolveBook = resolve;
    });
    vi.mocked(booksApi.getBookDetail).mockReturnValue(pending);

    renderShell("/bk-1/state");

    // While pending: the load has been kicked off, the shell chrome is up, and the
    // title is not shown yet — the loading state, not the ready state.
    expect(vi.mocked(booksApi.getBookDetail)).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("link", { name: "Book state" })).toBeInTheDocument();
    expect(screen.queryByText(BOOK_TITLE)).toBeNull();

    // Resolving the load surfaces the title...
    resolveBook(makeDetail("bk-1", BOOK_TITLE));
    expect(await screen.findByText(BOOK_TITLE)).toBeInTheDocument();

    // ...and the book was loaded exactly once, for this book id.
    expect(vi.mocked(booksApi.getBookDetail)).toHaveBeenCalledTimes(1);
    expect(vi.mocked(booksApi.getBookDetail).mock.calls[0][0]).toBe("bk-1");
  });

  it("DoD-6: a failed book load (the 403/404 a non-member gets) shows an author-facing message in place of the content, not a crash or blank", async () => {
    vi.mocked(booksApi.getBookDetail).mockRejectedValue(new ApiError(403, "Forbidden"));

    renderShell("/bk-1/state");

    await waitFor(() => expect(vi.mocked(booksApi.getBookDetail)).toHaveBeenCalledTimes(1));

    // The workspace content is replaced: the subject outlet is not shown, and the
    // ready-state title never appears.
    await waitFor(() => expect(screen.queryByTestId("subject-state")).toBeNull());
    expect(screen.queryByText(BOOK_TITLE)).toBeNull();

    // Not a crash and not blank: the shell rendered readable content (the message).
    expect(document.body.textContent?.trim()).not.toBe("");
  });

  it("DoD-7: navigating between two subjects under the same book id does not remount the shell — the book loads exactly once", async () => {
    const user = userEvent.setup();

    renderShell("/bk-1/state");

    // First subject loaded once.
    await screen.findByTestId("subject-state");
    expect(vi.mocked(booksApi.getBookDetail)).toHaveBeenCalledTimes(1);

    // Navigate to a sibling subject under the same book id via the in-SPA link.
    await user.click(screen.getByRole("link", { name: "Chapters" }));
    await screen.findByTestId("subject-chapters");

    // The shell did not remount: no second load fired.
    expect(vi.mocked(booksApi.getBookDetail)).toHaveBeenCalledTimes(1);
  });
});
