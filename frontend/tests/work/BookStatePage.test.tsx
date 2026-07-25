/**
 * Book-state landing view — 010.working-page / 003.book-state-landing,
 * DoD-1 · DoD-2 · DoD-3 · DoD-4 · DoD-5.
 *
 * Bound to the frozen signatures in status.md -> `## Skeleton` (step 003):
 *   const BookStatePage: FunctionComponent   // observer, no props; reads :bookId via router
 *   class BookStatePageState { bookDetail; bookDetailStatus; bookDetailError;
 *                              get collaborationModeLabel; get visibilityLabel;
 *                              get lifecycleStateLabel; get memberList; get memberCount }
 *   loadBookState(state, bookId, signal?) : Promise<void>          // calls getBookDetail
 *   WorkRoutes  // /:bookId index -> <Navigate to="state" replace/>, state -> <BookStatePage/>
 *
 * The page reads `:bookId` from the router, so DoD-2..5 mount it under a
 * `Route path="/:bookId/state"`; routes are basename-stripped (`/bk-1/state`,
 * not `/work/bk-1/state`). DoD-1 renders the whole WORK route table (`WorkRoutes`)
 * at `/bk-1` and observes the redirect landing on `state`.
 *
 * `api/books` is mocked module-factory form (never `fetch`). A factory replaces the
 * WHOLE module, and this page reads THREE exports from it — `getBookDetail` (the
 * loader), and `COLLABORATION_MODE_OPTIONS` / `VISIBILITY_OPTIONS` (the author-facing
 * labels). The two option arrays are SPEC DATA copied verbatim from `src/api/books.ts`
 * (`context.md` -> "reuse them for the author-facing labels"), so the factory supplies
 * their real value/label pairs. `ApiError` is the real class from `api/client`.
 *
 * Expected values come from the spec, never from the page's code:
 *   - the redirect target and landing view are US-106.AC-1 / the step's route map;
 *   - the rendered fields are exactly what `BookDetailResponse` carries (DoD-2 /
 *     `domain-book.md` minus the wire gap);
 *   - the state-notes empty state exists even on a SUCCESSFUL load, because it is the
 *     `BookResponse` wire gap (`context.md`), not a load failure (DoD-3);
 *   - the per-chapter region names `016.chapter-close-continuity` as owner and the page
 *     never says "flag" — "warning" is the author-facing word (DoD-4 /
 *     `frontend-workspace.md`);
 *   - the trio never blanks the pane: a pending load shows a loading state, a failed one
 *     an author-facing error (DoD-5).
 *
 * `globals: false`: every primitive is imported explicitly.
 */
import type { ReactElement } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import type { BookDetailResponse } from "../../src/types/books";
import { ApiError } from "../../src/api/client";
import * as booksApi from "../../src/api/books";
import { BookStatePage } from "../../src/work/pages/BookStatePage";
import { WorkRoutes } from "../../src/work/routes";
import { renderWithProviders } from "../support/render";

// A module-factory mock replaces the WHOLE module. The page's render subtree reaches
// `getBookDetail` (the loader) plus `COLLABORATION_MODE_OPTIONS` / `VISIBILITY_OPTIONS`
// (the label sources). The two arrays are the real spec-data pairs from
// `src/api/books.ts` — a factory that dropped them would strip the page's labels.
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

const OWNER_ID = "u-owner-77";
const CO_AUTHOR_ID = "u-coauthor-42";
const BOOK_TITLE = "The Winds of Winter";
const BOOK_DESCRIPTION = "A sprawling saga told across nine kingdoms.";

/** A fully-typed BookDetailResponse fixture; callers override the fields they assert on. */
function makeDetail(overrides: Partial<BookDetailResponse> = {}): BookDetailResponse {
  return {
    id: "bk-1",
    owner_id: OWNER_ID,
    title: BOOK_TITLE,
    description: BOOK_DESCRIPTION,
    collaboration_mode: "free",
    visibility: "private",
    state: "active",
    created_at: "2018-05-01T10:00:00Z",
    modified_at: "2026-11-30T15:00:00Z",
    members: [{ user_id: CO_AUTHOR_ID, role: "co_author", created_at: "2021-06-02T09:00:00Z" }],
    ...overrides,
  };
}

/** Mounts the page directly under a `:bookId` route so `useParams().bookId` resolves. */
function renderPage(route: string): void {
  renderWithProviders(
    <Routes>
      <Route path="/:bookId/state" element={<BookStatePage />} />
    </Routes>,
    { route },
  );
}

/** Reports the router's current pathname, so the redirect target is observable. */
function LocationProbe(): ReactElement {
  const location = useLocation();
  return <span data-testid="pathname">{location.pathname}</span>;
}

beforeEach(() => {
  // `restoreMocks` wipes the implementation between tests — default to a resolved detail;
  // pending / rejected cases override in-test.
  vi.mocked(booksApi.getBookDetail).mockResolvedValue(makeDetail());
});

describe("BookStatePage", () => {
  it("DoD-1: opening the working page at /:bookId redirects to /:bookId/state and the Book-state view renders", async () => {
    // Render the whole WORK route table at the bare `/:bookId` entry. A `LocationProbe`
    // shares the MemoryRouter so the redirect target is directly observable. The index
    // route redirects (replace) to `state`; landing there proves it is not a back-trap.
    renderWithProviders(
      <MemoryRouter initialEntries={["/bk-1"]}>
        <WorkRoutes />
        <LocationProbe />
      </MemoryRouter>,
    );

    await waitFor(() =>
      expect(screen.getByTestId("pathname").textContent).toBe("/bk-1/state"),
    );

    // The Book-state view itself is up: its per-chapter continuity region names its
    // owning feature — a marker unique to this page (not the shell chrome).
    expect(await screen.findByText(/016\.chapter-close-continuity/)).toBeInTheDocument();
  });

  it("DoD-2: renders every field BookDetailResponse carries — title, description, mode/visibility/state labels, both timestamps, owner and co-author", async () => {
    // `archived` is a distinctive lifecycle token (the continuity region mentions
    // "warnings", so `active` would collide); years 2018/2026 distinguish the two
    // timestamps; ids distinguish owner from co-author.
    vi.mocked(booksApi.getBookDetail).mockResolvedValue(makeDetail({ state: "archived" }));

    renderPage("/bk-1/state");

    // The book's own fields.
    expect(await screen.findByText(BOOK_TITLE)).toBeInTheDocument();
    expect(screen.getByText(BOOK_DESCRIPTION)).toBeInTheDocument();

    const pageText = document.body.textContent ?? "";
    // Collaboration-mode + visibility labels come from the spec option arrays.
    expect(pageText).toContain("Free"); // collaboration_mode "free" -> "Free"
    expect(pageText).toContain("Private"); // visibility "private" -> "Private"
    // Lifecycle state rendered human-readably (spec pins no exact wording; the derived
    // label carries the state token, not a raw unrelated word).
    expect(pageText).toMatch(/archiv/i); // state "archived"
    // Both timestamps rendered (any reasonable date format includes the year).
    expect(pageText).toMatch(/2018/); // created_at
    expect(pageText).toMatch(/2026/); // modified_at
    // Owner and co-author members both shown.
    expect(pageText).toContain(OWNER_ID);
    expect(pageText).toContain(CO_AUTHOR_ID);
  });

  it("DoD-3: the state-notes region is a labelled empty state — present on a SUCCESSFUL load, not a load failure and not omitted", async () => {
    renderPage("/bk-1/state");

    // A successful load (the title is on screen), yet the state-notes region still shows
    // its empty state: the notes are not yet exposed by the API (the BookResponse wire
    // gap), not a fetch error.
    expect(await screen.findByText(BOOK_TITLE)).toBeInTheDocument();

    // A spec-faithful page names "state notes" in TWO elements — the region label AND
    // the mandated message — so match without assuming uniqueness (getAllByText).
    expect(screen.getAllByText(/state notes/i).length).toBeGreaterThan(0);
    expect(document.body.textContent ?? "").toMatch(/not yet (available|exposed)/i);
  });

  it("DoD-4: the per-chapter continuity region names 016.chapter-close-continuity as owner, and the page says 'warning' never 'flag'", async () => {
    renderPage("/bk-1/state");

    // Labelled empty state naming its owning feature literally.
    expect(await screen.findByText(/016\.chapter-close-continuity/)).toBeInTheDocument();

    // "Warning" is the author-facing word; "flag" must never appear anywhere on the page.
    const pageText = document.body.textContent ?? "";
    expect(pageText).toMatch(/warning/i);
    expect(pageText).not.toMatch(/flag/i);
  });

  it("DoD-5: a pending load shows a loading state, not the book fields and not a blank pane", async () => {
    // A promise that never settles keeps the trio in its loading state.
    vi.mocked(booksApi.getBookDetail).mockReturnValue(new Promise<BookDetailResponse>(() => {}));

    renderPage("/bk-1/state");

    // The load was kicked off, the book's own fields are NOT shown yet (not ready)...
    expect(vi.mocked(booksApi.getBookDetail)).toHaveBeenCalled();
    expect(screen.queryByText(BOOK_TITLE)).toBeNull();
    // ...and the pane is not blank — the loading state is on screen.
    expect((document.body.textContent ?? "").trim()).not.toBe("");
  });

  it("DoD-5: a failed load (ApiError) shows an author-facing error rather than a blank pane", async () => {
    vi.mocked(booksApi.getBookDetail).mockRejectedValue(new ApiError(500, "Server error"));

    renderPage("/bk-1/state");

    await waitFor(() => expect(vi.mocked(booksApi.getBookDetail)).toHaveBeenCalled());

    // The ready view never appears...
    await waitFor(() => expect(screen.queryByText(BOOK_TITLE)).toBeNull());
    // ...and the pane is not blank — an author-facing error is rendered instead. The spec
    // pins no exact error wording, so DoD-5 asserts the pane is not blank.
    expect((document.body.textContent ?? "").trim()).not.toBe("");
  });
});
