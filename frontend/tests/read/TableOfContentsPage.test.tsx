/**
 * The reader's table of contents — feature 022 (ultra track), DoD-8 only.
 * (DoD-9 is `ReaderChapterPage.test.tsx`. The gate, the route table, the api module
 * and the bookshelf section are deliberately NOT tested — `plan.md` -> `## Test plan`.)
 *
 * Bound to the frozen signatures in status.md -> `## Skeleton`:
 *   const TableOfContentsPage: FunctionComponent   // observer, ZERO props; reads :bookId
 *   getReaderBook(bookId, signal?): Promise<ReaderBookResponse>
 *   getReaderChapter(bookId, chapterId, signal?): Promise<ReaderChapterResponse>
 *   listPublicBooks(signal?): Promise<PublicBookListResponse>
 *   interface ReaderChapterRef { id: string; title: string }
 *   interface ReaderBookResponse { title: string; chapters: ReaderChapterRef[] }
 *
 * `api/reader` is mocked module-factory form, enumerating all THREE frozen exports so
 * nothing the page's module graph imports can be `undefined` — never `fetch`
 * (root `CLAUDE.md`). `ApiError` is the real class from `api/client`.
 *
 * Expected values come from the SPEC, never from the page's code:
 *   - the reader SPA's routes are `/:bookId` and `/:bookId/:chapterId` under
 *     `basename="/read"` (`plan.md` -> Interface), so a chapter link's in-SPA target is
 *     `/:bookId/:chapterId` — asserted basename-stripped, as the test render always is;
 *   - the chapters are listed in the order the server sent them, which is the reader's
 *     reading order (DoD-1: ascending `ordinal`) — the page re-sorts nothing;
 *   - a refused load renders an author-facing refusal message, NEVER a blank pane
 *     (D9: 404 -> "not available to read", chosen in the load function).
 *
 * The spec pins no exact refusal copy beyond its meaning, so the message is matched on
 * meaning; nothing is matched by test id, colour or DOM shape.
 *
 * `globals: false`: every primitive is imported explicitly.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { Route, Routes } from "react-router-dom";
import type { ReaderBookResponse } from "../../src/types/reader";
import { ApiError } from "../../src/api/client";
import * as readerApi from "../../src/api/reader";
import { TableOfContentsPage } from "../../src/read/pages/TableOfContentsPage";
import { renderWithProviders } from "../support/render";

// The WHOLE `api/reader` module, enumerating all three frozen exports.
vi.mock("../../src/api/reader", () => ({
  getReaderBook: vi.fn(),
  getReaderChapter: vi.fn(),
  listPublicBooks: vi.fn(),
}));

/** Snowflake ids as they cross the wire: strings beyond 2^53. */
const BOOK_ID = "9007199254740993";
const BOOK_TITLE = "The Winds of Winter";

/** The reader-visible chapters, in the server's ascending-ordinal order. */
const CH1 = { id: "5001", title: "The Ravens Depart" };
const CH2 = { id: "5002", title: "Winter at Castle Black" };
const CH3 = { id: "5003", title: "Dawn Over the Wall" };

const TOC: ReaderBookResponse = {
  title: BOOK_TITLE,
  chapters: [CH1, CH2, CH3],
};

/** Mounts the page under its own route so `useParams().bookId` resolves. */
function renderPage() {
  return renderWithProviders(
    <Routes>
      <Route path="/:bookId" element={<TableOfContentsPage />} />
    </Routes>,
    { route: `/${BOOK_ID}` },
  );
}

function pageText(): string {
  return document.body.textContent ?? "";
}

/** Every link that targets a chapter of this book, in document order. */
function chapterLinkHrefs(): string[] {
  return screen
    .queryAllByRole("link")
    .map((el) => el.getAttribute("href") ?? "")
    .filter((href) => href.includes(`/${BOOK_ID}/`));
}

/** Anything that reads as a refusal, since the spec pins no exact wording. */
const REFUSAL_COPY =
  /(not available|unavailable|no access|not allowed|refused|cannot|can'?t|could not|couldn'?t|unable|failed|error|not found)/i;

beforeEach(() => {
  vi.mocked(readerApi.getReaderBook).mockResolvedValue(TOC);
});

describe("TableOfContentsPage — the reader's table of contents", () => {
  it("DoD-8: lists the chapters as /:bookId/:chapterId links in order, and refuses visibly on 404", async () => {
    // --- The served case: every chapter is a link, in the order it arrived. -------
    const served = renderPage();

    expect(await screen.findByText(CH1.title)).toBeInTheDocument();
    expect(screen.getByText(CH2.title)).toBeInTheDocument();
    expect(screen.getByText(CH3.title)).toBeInTheDocument();

    // The book named in the URL is the one loaded.
    await waitFor(() => expect(vi.mocked(readerApi.getReaderBook)).toHaveBeenCalled());
    expect(vi.mocked(readerApi.getReaderBook).mock.calls[0][0]).toBe(BOOK_ID);

    // One link per chapter, to that chapter's in-SPA route, in reading order.
    expect(chapterLinkHrefs()).toEqual([
      `/${BOOK_ID}/${CH1.id}`,
      `/${BOOK_ID}/${CH2.id}`,
      `/${BOOK_ID}/${CH3.id}`,
    ]);

    served.unmount();

    // --- The refused case: 404 renders a message, never a blank pane. ------------
    vi.mocked(readerApi.getReaderBook).mockRejectedValue(new ApiError(404, "Not Found"));

    renderPage();

    await waitFor(() => expect(pageText()).toMatch(REFUSAL_COPY));
    // The pane carries readable copy...
    expect(pageText().trim().length).toBeGreaterThan(0);
    // ...and no chapter of a book the reader was refused.
    expect(chapterLinkHrefs()).toEqual([]);
    expect(screen.queryByText(CH1.title)).toBeNull();
    expect(screen.queryByText(CH2.title)).toBeNull();
    expect(screen.queryByText(CH3.title)).toBeNull();
  });
});
