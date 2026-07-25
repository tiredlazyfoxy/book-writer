/**
 * Content-pane subject routes — 010.working-page / 004.content-pane-subject-and-buffer,
 * DoD-4 (route half) · DoD-5 · DoD-6.
 *
 * Bound to the frozen signatures in status.md -> `## Skeleton` (step 004):
 *   const WorkRoutes: FunctionComponent   // observer; /:bookId shell + nine subject children
 *   interface SubjectPlaceholderPageProps { heading: string; owner: string }
 *   const SubjectPlaceholderPage: FunctionComponent<SubjectPlaceholderPageProps>
 *
 * The `/:bookId` shell (WorkspaceShell, from step 002) loads the book via
 * `api/books.getBookDetail` and renders its `<Outlet/>` inside the content pane
 * (the `main` landmark) once ready; each subject child renders a
 * `SubjectPlaceholderPage` there. Routes are basename-stripped (`/bk-1/chapters`,
 * not `/work/bk-1/chapters`).
 *
 * Every expected value comes from the spec, never from code:
 *   - the owner label each route names is pinned VERBATIM by the step file /
 *     `004.context.md` -> "Owner labels": chapters + one chapter -> `014.chapter-skeleton`;
 *     characters / locations / facts + one codex entry -> `013.codex`; variants + one
 *     chapter's variants -> `018.chapter-history-variants`; chats -> `011.chat-panel`
 *     (US-105.AC-1 / AC-2);
 *   - there is NO `chat/:id` route, so a chat-id path falls through to the in-pane
 *     not-found page (US-105.AC-3) — its back-to-bookshelf anchor (href "/") from
 *     step 001 identifies it;
 *   - the owner labels are asserted INSIDE the content pane (`main`), because the
 *     chat-pane slot also names `011.chat-panel` and must not be mistaken for the
 *     chats-list placeholder.
 *
 * `api/books` is mocked module-factory form (never `fetch`); the shell subtree reads
 * only `getBookDetail`, but `WorkRoutes` also imports the Book-state page, so the
 * two option arrays are supplied too (their real spec-data pairs) to keep the module
 * shape intact. `globals: false`.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import type { BookDetailResponse } from "../../src/types/books";
import * as booksApi from "../../src/api/books";
import { WorkRoutes } from "../../src/work/routes";
import { renderWithProviders } from "../support/render";

// A module-factory mock replaces the WHOLE module. `getBookDetail` powers the shell
// load; the option arrays are the real spec-data pairs (copied verbatim from
// `src/api/books.ts`) that the Book-state page — imported by `WorkRoutes` — depends on.
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

/** Render the whole WORK route table at a basename-stripped subject route. */
function renderAt(route: string): void {
  renderWithProviders(<WorkRoutes />, { route });
}

beforeEach(() => {
  // `restoreMocks` wipes the implementation between tests — the shell needs a resolved
  // book so it reaches `ready` and renders its `<Outlet/>` (the subject placeholder).
  vi.mocked(booksApi.getBookDetail).mockResolvedValue(makeDetail("bk-1"));
});

describe("subject list routes render a read-only empty state naming their owner (DoD-5)", () => {
  const LIST_ROUTES: Array<[string, RegExp]> = [
    ["/bk-1/chapters", /014\.chapter-skeleton/],
    ["/bk-1/characters", /013\.codex/],
    ["/bk-1/locations", /013\.codex/],
    ["/bk-1/facts", /013\.codex/],
    ["/bk-1/variants", /018\.chapter-history-variants/],
    ["/bk-1/chats", /011\.chat-panel/],
  ];

  for (const [route, ownerLabel] of LIST_ROUTES) {
    it(`DoD-5: ${route} renders, inside the content pane, an empty state naming ${ownerLabel.source}`, async () => {
      renderAt(route);
      // Scope to the content pane (`main`): the chat-pane slot also names
      // `011.chat-panel`, so only the placeholder inside `main` counts.
      const main = await screen.findByRole("main");
      expect(await within(main).findByText(ownerLabel)).toBeInTheDocument();
    });
  }
});

describe("subject item routes resolve into the content pane, not the catch-all (DoD-6)", () => {
  const ITEM_ROUTES: Array<[string, RegExp]> = [
    ["/bk-1/chapter/ch-1", /014\.chapter-skeleton/],
    ["/bk-1/codex/ce-1", /013\.codex/],
    ["/bk-1/variants/ch-9", /018\.chapter-history-variants/],
  ];

  for (const [route, ownerLabel] of ITEM_ROUTES) {
    it(`DoD-6: ${route} renders the placeholder naming ${ownerLabel.source}, not the not-found page`, async () => {
      renderAt(route);
      const main = await screen.findByRole("main");

      // The placeholder resolved inside the content pane...
      expect(await within(main).findByText(ownerLabel)).toBeInTheDocument();

      // ...and it is NOT the catch-all: the not-found page's back-to-bookshelf anchor
      // (href "/") is absent from the content pane.
      const backAnchors = within(main)
        .queryAllByRole("link")
        .filter((anchor) => anchor.getAttribute("href") === "/");
      expect(backAnchors).toHaveLength(0);
    });
  }
});

describe("no chat/:id route (DoD-4, route half)", () => {
  it("DoD-4: a /:bookId/chat/<id> path falls through to the in-pane not-found page", async () => {
    renderAt("/bk-1/chat/c-1");
    const main = await screen.findByRole("main");

    // The not-found page renders in the content pane: its back-to-bookshelf anchor
    // (href "/", from step 001) is the identifying signal.
    await waitFor(() => {
      const links = within(main).queryAllByRole("link");
      expect(links.some((anchor) => anchor.getAttribute("href") === "/")).toBe(true);
    });

    // No subject placeholder resolved for a chat id: the chat owner label does not
    // appear inside the content pane (it lives only in the chat-pane slot).
    expect(within(main).queryByText(/011\.chat-panel/)).toBeNull();
  });
});
