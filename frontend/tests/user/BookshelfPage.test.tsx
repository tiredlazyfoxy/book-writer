/**
 * Bookshelf -> work links — 010.working-page / 001.work-entry-scaffold, DoD-4.
 *
 * Bound to the frozen signatures in the plans' `## Skeleton` records:
 *   const BookshelfPage: FunctionComponent   // observer, no props (009 step 006)
 *   listOwnedBooks(signal?): Promise<BookListResponse>   (009 step 006, api/books)
 *   listSharedBooks(signal?): Promise<BookListResponse>
 *   interface BookResponse { id; owner_id; title; description; collaboration_mode;
 *                            visibility; state; created_at; modified_at }
 *   interface BookListResponse { items: BookResponse[] }
 *
 * This is the repo's FIRST spec to mock an `src/api/*` module. Per the frontend
 * rule we mock the `api/books` module (never `fetch`), module-factory form with
 * `vi.fn()` members, then `vi.mocked(...).mockResolvedValue(...)` per case —
 * the same idiom existing specs use for `../../src/auth`.
 *
 * The step spec ("Interface intent" + DoD-4): each owned AND shared row's title
 * cell becomes a **plain anchor** to `/work/<book.id>` — a full page load across
 * Vite entries, deliberately NOT a react-router `<Link>`. The href must be exactly
 * `/work/<id>`. To prove the anchor is a plain `<a>` and not a router link, the
 * page is rendered with NO `Router` ancestor: a react-router `<Link>` would throw
 * without one, and even under a router `basename="/user"` could not yield this
 * literal cross-entry href. A clean render with the exact href is the proof.
 *
 * `globals: false`: every primitive is imported explicitly.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import type { BookResponse } from "../../src/types/books";
import * as booksApi from "../../src/api/books";
import { BookshelfPage } from "../../src/user/pages/BookshelfPage";
import { renderWithProviders } from "../support/render";

// A module-factory mock replaces the WHOLE module, so it must supply every named
// export the rendered subtree reaches — not just the two list calls this spec
// drives. The create-book modal pulls the Select option constants
// COLLABORATION_MODE_OPTIONS / VISIBILITY_OPTIONS from this same module; omitting
// them makes render throw before any anchor assertion. Their shapes come from the
// feature-009 step-006 `## Skeleton` record (CollaborationModeOption[] /
// VisibilityOption[]) with the frozen literal unions ("free" | "proposal",
// "private" | "public"); labels are inert here.
vi.mock("../../src/api/books", () => ({
  listOwnedBooks: vi.fn(),
  listSharedBooks: vi.fn(),
  createBook: vi.fn(),
  COLLABORATION_MODE_OPTIONS: [
    { value: "free", label: "Free" },
    { value: "proposal", label: "Proposal" },
  ],
  VISIBILITY_OPTIONS: [
    { value: "private", label: "Private" },
    { value: "public", label: "Public" },
  ],
}));

/** A fully-typed BookResponse fixture; only id + title vary per row. */
function makeBook(id: string, title: string): BookResponse {
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
  };
}

beforeEach(() => {
  // `restoreMocks` wipes implementations between tests — default to empty lists.
  vi.mocked(booksApi.listOwnedBooks).mockResolvedValue({ items: [] });
  vi.mocked(booksApi.listSharedBooks).mockResolvedValue({ items: [] });
});

describe("BookshelfPage — work links", () => {
  it("DoD-4: an owned book row's title is a plain anchor to /work/<id>", async () => {
    vi.mocked(booksApi.listOwnedBooks).mockResolvedValue({
      items: [makeBook("b-owned", "Owned Novel")],
    });

    renderWithProviders(<BookshelfPage />);

    const link = await screen.findByRole("link", { name: "Owned Novel" });
    expect(link).toHaveAttribute("href", "/work/b-owned");
    expect(link.tagName).toBe("A");
  });

  it("DoD-4: a shared book row's title is a plain anchor to /work/<id>", async () => {
    vi.mocked(booksApi.listSharedBooks).mockResolvedValue({
      items: [makeBook("b-shared", "Shared Saga")],
    });

    renderWithProviders(<BookshelfPage />);

    const link = await screen.findByRole("link", { name: "Shared Saga" });
    expect(link).toHaveAttribute("href", "/work/b-shared");
    expect(link.tagName).toBe("A");
  });

  it("DoD-4: owned and shared rows each get their own /work/<id> anchor", async () => {
    vi.mocked(booksApi.listOwnedBooks).mockResolvedValue({
      items: [makeBook("b-owned", "Owned Novel")],
    });
    vi.mocked(booksApi.listSharedBooks).mockResolvedValue({
      items: [makeBook("b-shared", "Shared Saga")],
    });

    renderWithProviders(<BookshelfPage />);

    expect(await screen.findByRole("link", { name: "Owned Novel" })).toHaveAttribute(
      "href",
      "/work/b-owned",
    );
    expect(await screen.findByRole("link", { name: "Shared Saga" })).toHaveAttribute(
      "href",
      "/work/b-shared",
    );
  });
});
