/**
 * Work route table — 010.working-page / 001.work-entry-scaffold, DoD-3.
 *
 * Bound to the frozen signature in status.md -> `## Skeleton` (step 001):
 *   const WorkRoutes: FunctionComponent   // observer, no props
 *   const NotFoundPage: FunctionComponent // observer, no props
 *
 * At this step the route table declares ONLY the terminal catch-all rendering the
 * work not-found page (later steps nest the real routes into it). The spec
 * ("Interface intent") gives the not-found page "a not-found message and a plain
 * anchor back to the bookshelf at `/`" — that back anchor (href exactly "/") is
 * the page's identifying signal here. Its being the *only* link on screen proves
 * the catch-all is terminal: no route page's content sits beside it.
 *
 * Routes passed to `renderWithProviders` are basename-stripped (production's
 * `basename="/work"` never appears), so the work entry root is "/". The durable
 * assertion here is the entry root (no book id): "/" does not match `/:bookId`, so
 * it reaches the terminal top-level catch-all → NotFoundPage. (The unmatched
 * deep-path case is superseded from step 002 on: `/:bookId` + a splat child now
 * renders the workspace shell with an *in-pane* not-found, covered by that step's
 * shell nested-catch-all test in tests/work/WorkspaceShell.test.tsx.)
 *
 * `globals: false`: every primitive is imported explicitly.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import type { BookDetailResponse } from "../../src/types/books";
import * as booksApi from "../../src/api/books";
import * as chatsApi from "../../src/api/chats";
import * as codexApi from "../../src/api/codex";
import * as flagsApi from "../../src/api/flags";
import * as continuityApi from "../../src/api/continuity";
import * as memosApi from "../../src/api/memos";
import { WorkRoutes } from "../../src/work/routes";
import { renderWithProviders } from "../support/render";

// HARNESS ONLY, added by 026.memos step 009 for the DoD-4 block below: mounting a
// `/:bookId/...` route brings up the workspace shell, whose own loads must resolve
// locally rather than reach `api/client`. The module set and the module-factory form
// are copied verbatim from the sibling spec `tests/work/subjectRoutes.test.tsx`; the
// entry-root case above touches none of them. Never `fetch` — always the `api/` module.
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

vi.mock("../../src/api/chats", () => ({
  listChats: vi.fn(),
  createChat: vi.fn(),
  updateChat: vi.fn(),
  getChat: vi.fn(),
  listModelOptions: vi.fn(),
  streamChatTurn: vi.fn(),
  titleChat: vi.fn(),
}));

vi.mock("../../src/api/codex", () => ({
  listCodexEntries: vi.fn(),
  getCodexEntry: vi.fn(),
  createCodexEntry: vi.fn(),
  updateCodexEntry: vi.fn(),
}));

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

// HARNESS ONLY, added by 026.memos step 010 — the sixth module factory, in the same idiom
// as the five above. The DoD-4 block below mounts `/bk-1/memos`, and from step 010 on the
// memos page is REAL: it loads on mount through `api/memos`. Unmocked, that reaches
// `api/client` -> `fetch`, which jsdom rejects as a transport failure — and `client.ts`
// wraps only non-2xx responses into `ApiError`, so the page's loader would RETHROW it as an
// unhandled rejection instead of landing in its error field. Enumerate every export of the
// module (step 009's frozen `api/memos`), never `fetch`. NOTHING here is asserted on: no
// assertion in this file changed.
vi.mock("../../src/api/memos", () => ({
  listMemos: vi.fn(),
  createMemo: vi.fn(),
  updateMemoBody: vi.fn(),
  reorderMemos: vi.fn(),
  activateMemo: vi.fn(),
  deactivateMemo: vi.fn(),
  archiveMemo: vi.fn(),
  restoreMemo: vi.fn(),
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

beforeEach(() => {
  // `restoreMocks` wipes implementations between tests — the shell needs a resolved book
  // so it reaches `ready` and renders its `<Outlet/>`.
  vi.mocked(booksApi.getBookDetail).mockResolvedValue(makeDetail("bk-1"));
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
  vi.mocked(chatsApi.listChats).mockResolvedValue([]);
  vi.mocked(chatsApi.listModelOptions).mockResolvedValue([]);
  vi.mocked(codexApi.listCodexEntries).mockResolvedValue([]);
  vi.mocked(continuityApi.getStateNotes).mockResolvedValue({
    book_id: "bk-1",
    active_notes: "",
    modified_at: null,
  });
  vi.mocked(continuityApi.getBookContinuity).mockResolvedValue({ items: [] });
  vi.mocked(flagsApi.listFlags).mockResolvedValue({ items: [] });
  // 026.memos step 010: the memos page loads on mount; an empty list is enough here, where
  // nothing asserts on memo content.
  vi.mocked(memosApi.listMemos).mockResolvedValue([]);
});

describe("WorkRoutes", () => {
  it("DoD-3: the entry root (no book id) renders the not-found page", () => {
    renderWithProviders(<WorkRoutes />, { route: "/" });

    // The not-found page's back-to-bookshelf anchor identifies it ...
    expect(screen.getByRole("link")).toHaveAttribute("href", "/");
    // ... and it is the only link on screen: the catch-all is terminal, no route
    // page's content leaked in beside it.
    expect(screen.getAllByRole("link")).toHaveLength(1);
  });
});

/* ------------------------------------------------------------------------------------
 * 026.memos / 009.memos-api-and-navigator — the memos route. DoD-4.
 *
 * Bound to the frozen interface in status.md -> `## Skeleton` (026 step 009):
 *   <Route path="memos" element={<MemosListPage/>} />   // mounted DIRECTLY, no key wrapper
 *   const MemosListPage: FunctionComponent              // observer, no props; heading "Memos"
 *
 * Every expected value comes from the spec, never from code:
 *   - `frontend-workspace.md` -> "`/memos` has no item route" and `context.md` ->
 *     decision 12: creation appends into the list in place, so there is NO `/memos/:id`
 *     and NO `/memos/new`. An address under `/memos/` therefore falls through to the
 *     nested not-found page INSIDE the shell, whose back-to-bookshelf anchor (href "/",
 *     from 010 step 001) is the identifying signal;
 *   - the memos route resolves inside the workspace shell and renders the memos page in
 *     the content pane (the `main` landmark), identified by its "Memos" heading. The page's
 *     CONTENT is step 010's, not this clause's: `context.md` -> "One mechanical note on step
 *     009 vs 010" has step 010 replace the placeholder body outright, so nothing here binds
 *     to the transitional owner label any more (see the note at the assertion).
 *
 * Routes passed to `renderWithProviders` are basename-stripped, so the memos route is
 * `/bk-1/memos`, never `/work/bk-1/memos`. Assertions are scoped to `main` because the
 * navigator also carries a "Memos" link and the chat pane renders beside the content.
 * ---------------------------------------------------------------------------------- */

describe("WorkRoutes — the memos route (026 DoD-4)", () => {
  it("DoD-4: /:bookId/memos resolves inside the workspace shell and renders the memos page", async () => {
    renderWithProviders(<WorkRoutes />, { route: "/bk-1/memos" });

    const main = await screen.findByRole("main");

    // The memos page resolved in the content pane...
    expect(await within(main).findByRole("heading", { name: "Memos" })).toBeInTheDocument();
    // (The step-009 assertion on the placeholder's "step 010" owner label was DELETED by
    // 026.memos step 010: `context.md` -> "One mechanical note on step 009 vs 010" fixes that
    // marker's lifecycle — step 009 creates the placeholder, step 010 REPLACES its body with
    // the real page — so from step 010 on the spec REQUIRES the marker to be gone. It pinned a
    // transitional state, not a requirement. DoD-4's own substance is unchanged: the page
    // resolves in the content-pane landmark, and it is not the catch-all.)

    // ...and it is NOT the catch-all: the not-found page's back-to-bookshelf anchor
    // (href "/") is absent from the content pane.
    const backAnchors = within(main)
      .queryAllByRole("link")
      .filter((anchor) => anchor.getAttribute("href") === "/");
    expect(backAnchors).toHaveLength(0);
  });

  it("DoD-4: there is no /memos/:id route — a memo-id address falls through to the in-pane not-found page", async () => {
    renderWithProviders(<WorkRoutes />, { route: "/bk-1/memos/m-1" });

    const main = await screen.findByRole("main");

    await waitFor(() => {
      const links = within(main).queryAllByRole("link");
      expect(links.some((anchor) => anchor.getAttribute("href") === "/")).toBe(true);
    });
    // The memos page did not render for an item address.
    expect(within(main).queryByRole("heading", { name: "Memos" })).toBeNull();
  });

  it("DoD-4: there is no /memos/new route either — creation happens in the list, not on a page", async () => {
    renderWithProviders(<WorkRoutes />, { route: "/bk-1/memos/new" });

    const main = await screen.findByRole("main");

    await waitFor(() => {
      const links = within(main).queryAllByRole("link");
      expect(links.some((anchor) => anchor.getAttribute("href") === "/")).toBe(true);
    });
    expect(within(main).queryByRole("heading", { name: "Memos" })).toBeNull();
  });
});
