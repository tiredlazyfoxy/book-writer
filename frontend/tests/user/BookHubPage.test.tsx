/**
 * The read-only Shell book hub — 014.chapter-skeleton / 005.chapters-api-and-book-hub,
 * DoD-1 · DoD-2 · DoD-3 · DoD-4 · DoD-5 · DoD-6.
 * (DoD-7..9 are the api module's — `chaptersApi.test.ts`. DoD-10 is [manual/live].)
 *
 * Bound to the frozen signatures in status.md -> `## Skeleton` (step 005):
 *   const BookHubPage: FunctionComponent           // observer, no props; reads :bookId
 *   const UserRoutes: FunctionComponent            // gains /books/:bookId, keyed on bookId
 *   listChapters(bookId, signal?): Promise<ChapterListResponse>
 *   getBookDetail(bookId, signal?): Promise<BookDetailResponse>   // existing, api/books
 *   type ChapterLifecycleState = "planned" | "open" | "closing" | "closed"
 *   interface ChapterResponse { id; book_id; ordinal; title; state; sketch; version;
 *                               created_at; modified_at }
 *   interface ChapterListResponse { chapters: ChapterResponse[]; can_reorder: boolean }
 *
 * Both api modules are mocked module-factory form (never `fetch`). `api/chapters` gets a
 * plain factory enumerating all EIGHT frozen exports; `api/books` gets an `importOriginal`
 * SPREAD with `vi.fn()` overrides for every call-shaped export, because a factory that
 * silently stripped an export the page (or its module graph) imports would make the page
 * fail to render for the wrong reason. `ApiError` is the real class from `api/client`.
 *
 * Expected values come from the spec, never from the page's code:
 *   - the hub renders the book's title as its heading and the chapters in ordinal order
 *     with each chapter's state shown (Interface intent) — DoD-1;
 *   - an empty `chapters` array is a SUCCESSFUL load, so it renders an empty state, never
 *     an error and never a blank list (`## Skeleton`, DoD-2) — DoD-2;
 *   - the hub is READ-ONLY (`context.md` -> D2): no add / remove / reorder / edit control
 *     and no editable field anywhere — DoD-3;
 *   - the work links are `/work/:bookId` and `/work/:bookId/chapter/:chapterId`, plain
 *     anchors because `/work` is a separate Vite entry (`## Skeleton`) — DoD-4;
 *   - the two trios load and fail INDEPENDENTLY, so each failure renders its own error
 *     branch and leaves the other resource's content whole — DoD-5;
 *   - the route is keyed on `:bookId`, so changing it is a fresh page state that re-loads
 *     both resources rather than showing the previous book's chapters — DoD-6.
 *
 * The spec pins no exact copy, so state badges are matched on the wire vocabulary
 * (`planned` / `open` / `closing` / `closed`), the empty state and the error branches on
 * their meaning, and every control assertion is BY ROLE — never by test id, never by
 * colour, never by DOM shape.
 *
 * `globals: false`: every primitive is imported explicitly.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { Link, MemoryRouter, Route, Routes } from "react-router-dom";
import type { BookDetailResponse } from "../../src/types/books";
import type {
  ChapterLifecycleState,
  ChapterListResponse,
  ChapterResponse,
} from "../../src/types/chapters";
import { ApiError } from "../../src/api/client";
import * as booksApi from "../../src/api/books";
import * as chaptersApi from "../../src/api/chapters";
import { BookHubPage } from "../../src/user/pages/BookHubPage";
import { UserRoutes } from "../../src/user/routes";
import { renderWithProviders } from "../support/render";

// Plain module factory: the WHOLE `api/chapters` module, enumerating all eight frozen
// exports so nothing the page's module graph imports can be `undefined`.
vi.mock("../../src/api/chapters", () => ({
  listChapters: vi.fn(),
  getChapter: vi.fn(),
  createChapter: vi.fn(),
  updateChapterSketch: vi.fn(),
  removeChapter: vi.fn(),
  reorderChapters: vi.fn(),
  getOwnChapterSystemPrompt: vi.fn(),
  updateOwnChapterSystemPrompt: vi.fn(),
}));

// `importOriginal` spread + `vi.fn()` overrides for every call-shaped export: no export
// can be stripped (option constants included), and no call can escape to the network.
vi.mock("../../src/api/books", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../src/api/books")>();
  return {
    ...actual,
    getBookDetail: vi.fn(),
    getOwnSystemPrompt: vi.fn(),
    updateOwnSystemPrompt: vi.fn(),
    listOwnedBooks: vi.fn(),
    listSharedBooks: vi.fn(),
    createBook: vi.fn(),
    archiveBook: vi.fn(),
    unarchiveBook: vi.fn(),
    transferOwnership: vi.fn(),
    addMember: vi.fn(),
    removeMember: vi.fn(),
    setVisibility: vi.fn(),
  };
});

/** Snowflake ids as they cross the wire: strings beyond 2^53. */
const BOOK_ID = "9007199254740993";
const OTHER_BOOK_ID = "9007199254740995";
const BOOK_TITLE = "The Winds of Winter";
const OTHER_BOOK_TITLE = "A Dream of Spring";
const HUB_ROUTE = `/books/${BOOK_ID}`;

/** Distinct chapter titles, one per lifecycle state, in ordinal order. */
const CH1 = { id: "5001", title: "The Ravens Depart", state: "planned" as const };
const CH2 = { id: "5002", title: "Winter at Castle Black", state: "open" as const };
const CH3 = { id: "5003", title: "The Long Retreat", state: "closing" as const };
const CH4 = { id: "5004", title: "Dawn Over the Wall", state: "closed" as const };
const ALL_TITLES = [CH1.title, CH2.title, CH3.title, CH4.title];

function makeDetail(overrides: Partial<BookDetailResponse> = {}): BookDetailResponse {
  return {
    id: BOOK_ID,
    owner_id: "u-owner-77",
    title: BOOK_TITLE,
    description: "A sprawling saga told across nine kingdoms.",
    collaboration_mode: "free",
    visibility: "private",
    state: "active",
    created_at: "2018-05-01T10:00:00Z",
    modified_at: "2026-07-01T15:00:00Z",
    members: [],
    ...overrides,
  };
}

function makeChapter(
  id: string,
  ordinal: number,
  title: string,
  state: ChapterLifecycleState,
  bookId: string = BOOK_ID,
): ChapterResponse {
  return {
    id,
    book_id: bookId,
    ordinal,
    title,
    state,
    sketch: `A sketch for ${title}.`,
    version: 1,
    created_at: "2026-01-02T09:00:00Z",
    modified_at: "2026-01-03T09:00:00Z",
  };
}

/** The book's chapters as the server returns them: ordered by ordinal ascending. */
function makeChapterList(overrides: Partial<ChapterListResponse> = {}): ChapterListResponse {
  return {
    chapters: [
      makeChapter(CH1.id, 1, CH1.title, CH1.state),
      makeChapter(CH2.id, 2, CH2.title, CH2.state),
      makeChapter(CH3.id, 3, CH3.title, CH3.state),
      makeChapter(CH4.id, 4, CH4.title, CH4.state),
    ],
    can_reorder: false,
    ...overrides,
  };
}

/** Mounts the page under its own route so `useParams().bookId` resolves. */
function renderPage(route: string = HUB_ROUTE): void {
  renderWithProviders(
    <Routes>
      <Route path="/books/:bookId" element={<BookHubPage />} />
    </Routes>,
    { route },
  );
}

function pageText(): string {
  return document.body.textContent ?? "";
}

/** Every rendered link's `href`, in document order. */
function linkHrefs(): string[] {
  return screen.queryAllByRole("link").map((el) => el.getAttribute("href") ?? "");
}

/** The per-chapter working-page links, in document order. */
function chapterLinkHrefs(): string[] {
  return linkHrefs().filter((href) => href.includes("/chapter/"));
}

/**
 * A chapter's own row: the largest ancestor of its title that still mentions no OTHER
 * chapter. Defined without assuming any DOM shape — the spec pins none.
 */
function rowFor(title: string): HTMLElement {
  const others = ALL_TITLES.filter((other) => other !== title);
  let node: HTMLElement = screen.getByText(title);
  while (node.parentElement !== null && node.parentElement !== document.body) {
    const parent: HTMLElement = node.parentElement;
    const text = parent.textContent ?? "";
    if (others.some((other) => text.includes(other))) break;
    node = parent;
  }
  return node;
}

/**
 * Every control the reader could actually change: text-bearing inputs, textareas,
 * selects and contenteditable regions that are neither disabled nor read-only.
 */
function editableControls(): HTMLElement[] {
  const nodes = Array.from(
    document.querySelectorAll<HTMLElement>("input, textarea, select, [contenteditable='true']"),
  );
  return nodes.filter((node) => {
    if (node instanceof HTMLInputElement) {
      if (["hidden", "button", "submit", "reset", "image"].includes(node.type)) return false;
      return !node.disabled && !node.readOnly;
    }
    if (node instanceof HTMLTextAreaElement) return !node.disabled && !node.readOnly;
    if (node instanceof HTMLSelectElement) return !node.disabled;
    return true;
  });
}

/** Anything that reads as a failure, since the spec pins no error wording. */
const FAILURE_COPY = /(failed|could not|couldn'?t|unable|unavailable|error|retry|try again)/i;

beforeEach(() => {
  // `restoreMocks` wipes implementations between tests — default both trios to the
  // happy path; individual cases override.
  vi.mocked(booksApi.getBookDetail).mockResolvedValue(makeDetail());
  vi.mocked(chaptersApi.listChapters).mockResolvedValue(makeChapterList());
});

describe("BookHubPage — the read-only book hub", () => {
  it("DoD-1: /books/:bookId renders the book's title as the heading and both loads address that book", async () => {
    renderPage();

    expect(await screen.findByRole("heading", { name: BOOK_TITLE })).toBeInTheDocument();

    // Both resources are loaded for the book named in the URL.
    await waitFor(() => expect(vi.mocked(chaptersApi.listChapters)).toHaveBeenCalled());
    expect(vi.mocked(chaptersApi.listChapters).mock.calls[0][0]).toBe(BOOK_ID);
    expect(vi.mocked(booksApi.getBookDetail)).toHaveBeenCalled();
    expect(vi.mocked(booksApi.getBookDetail).mock.calls[0][0]).toBe(BOOK_ID);
  });

  it("DoD-1: every chapter is listed, in ordinal order", async () => {
    renderPage();

    for (const title of ALL_TITLES) {
      expect(await screen.findByText(title)).toBeInTheDocument();
    }

    // Document order is ordinal order (the per-chapter links carry the chapter ids).
    expect(chapterLinkHrefs()).toEqual([
      `/work/${BOOK_ID}/chapter/${CH1.id}`,
      `/work/${BOOK_ID}/chapter/${CH2.id}`,
      `/work/${BOOK_ID}/chapter/${CH3.id}`,
      `/work/${BOOK_ID}/chapter/${CH4.id}`,
    ]);
  });

  it("DoD-1: each chapter shows its own lifecycle state as readable text", async () => {
    renderPage();
    await screen.findByText(CH1.title);

    // The state badge is text, not a colour — and it belongs to its own chapter's row.
    expect(rowFor(CH1.title).textContent ?? "").toMatch(/planned/i);
    expect(rowFor(CH2.title).textContent ?? "").toMatch(/open/i);
    expect(rowFor(CH3.title).textContent ?? "").toMatch(/closing/i);
    expect(rowFor(CH4.title).textContent ?? "").toMatch(/closed/i);
  });

  it("DoD-2: a book with no chapters renders an empty state — not an error and not a blank list", async () => {
    // An empty array is a SUCCESSFUL load: the normal starting state of every new book.
    vi.mocked(chaptersApi.listChapters).mockResolvedValue({ chapters: [], can_reorder: false });

    renderPage();

    // The book itself still renders...
    expect(await screen.findByRole("heading", { name: BOOK_TITLE })).toBeInTheDocument();
    // ...no chapter is listed...
    await waitFor(() => expect(chapterLinkHrefs()).toEqual([]));
    // ...an empty state says so...
    expect(pageText()).toMatch(
      /(no chapters|no chapter|nothing here|nothing yet|none yet|empty|hasn'?t|doesn'?t have any|not have any)/i,
    );
    // ...and it is not a failure branch: nothing failure-shaped, no retry offered.
    expect(pageText()).not.toMatch(FAILURE_COPY);
    expect(screen.queryAllByRole("button", { name: /retry|try again/i })).toHaveLength(0);
  });

  it("DoD-3: the hub offers no control that adds, removes, reorders or edits a chapter", async () => {
    renderPage();
    await screen.findByText(CH1.title);

    // Every mutation affordance, asked for BY ROLE — buttons and menu items alike.
    const mutating =
      /add|new|create|remove|delete|reorder|re-order|move|up|down|edit|rename|sketch|save|drag/i;
    expect(screen.queryAllByRole("button", { name: mutating })).toHaveLength(0);
    expect(screen.queryAllByRole("menuitem", { name: mutating })).toHaveLength(0);

    // A link may only be a way OUT to the working page (DoD-4) — never a mutation here.
    const mutatingLinks = screen
      .queryAllByRole("link", { name: mutating })
      .filter((link) => !(link.getAttribute("href") ?? "").startsWith("/work/"));
    expect(mutatingLinks).toHaveLength(0);
  });

  it("DoD-3: the hub presents no editable field — every chapter is read-only", async () => {
    renderPage();
    await screen.findByText(CH1.title);

    // No input-bearing role is offered anywhere on the surface...
    for (const role of [
      "textbox",
      "searchbox",
      "combobox",
      "listbox",
      "checkbox",
      "radio",
      "switch",
      "spinbutton",
      "slider",
    ] as const) {
      expect(screen.queryAllByRole(role)).toHaveLength(0);
    }

    // ...and nothing on the page is editable in fact, either.
    expect(editableControls()).toEqual([]);
  });

  it("DoD-4: the hub links to the working page for the book and to each chapter's working-page route", async () => {
    renderPage();
    await screen.findByText(CH1.title);

    const hrefs = linkHrefs();

    // The prominent way into the working page.
    expect(hrefs).toContain(`/work/${BOOK_ID}`);
    // One link per chapter, to that chapter's working-page route.
    expect(hrefs).toContain(`/work/${BOOK_ID}/chapter/${CH1.id}`);
    expect(hrefs).toContain(`/work/${BOOK_ID}/chapter/${CH2.id}`);
    expect(hrefs).toContain(`/work/${BOOK_ID}/chapter/${CH3.id}`);
    expect(hrefs).toContain(`/work/${BOOK_ID}/chapter/${CH4.id}`);

    // `/work` is a separate Vite entry, so these are plain anchors (a full page load).
    for (const link of screen.getAllByRole("link")) {
      expect(link.tagName).toBe("A");
    }
  });

  it("DoD-5: a failed chapter load renders its own error branch and leaves the book heading whole", async () => {
    vi.mocked(chaptersApi.listChapters).mockRejectedValue(
      new ApiError(500, "Chapters are unavailable"),
    );

    renderPage();

    await waitFor(() => expect(vi.mocked(chaptersApi.listChapters)).toHaveBeenCalled());

    // The chapter trio is in its own error branch...
    await waitFor(() => expect(pageText()).toMatch(FAILURE_COPY));
    expect(chapterLinkHrefs()).toEqual([]);
    // ...and the book detail, which loaded fine, is untouched by it.
    expect(await screen.findByRole("heading", { name: BOOK_TITLE })).toBeInTheDocument();
    expect(linkHrefs()).toContain(`/work/${BOOK_ID}`);
  });

  it("DoD-5: a failed book-detail load renders its own error branch and leaves the chapter list whole", async () => {
    vi.mocked(booksApi.getBookDetail).mockRejectedValue(new ApiError(500, "Book is unavailable"));

    renderPage();

    await waitFor(() => expect(vi.mocked(booksApi.getBookDetail)).toHaveBeenCalled());

    // The detail trio is in its own error branch — no title heading is rendered...
    await waitFor(() => expect(pageText()).toMatch(FAILURE_COPY));
    expect(screen.queryByRole("heading", { name: BOOK_TITLE })).toBeNull();

    // ...and the chapters, which loaded fine, are listed in full regardless.
    for (const title of ALL_TITLES) {
      expect(await screen.findByText(title)).toBeInTheDocument();
    }
    expect(chapterLinkHrefs()).toHaveLength(4);
  });

  it("DoD-6: changing :bookId re-loads both resources and never shows the previous book's chapters", async () => {
    // Two books with disjoint content, so "re-loaded" is distinguishable from "reused".
    const otherList: ChapterListResponse = {
      chapters: [makeChapter("6001", 1, "A Wholly Different Chapter", "planned", OTHER_BOOK_ID)],
      can_reorder: true,
    };
    vi.mocked(booksApi.getBookDetail).mockImplementation(async (bookId: string) =>
      bookId === BOOK_ID
        ? makeDetail()
        : makeDetail({ id: OTHER_BOOK_ID, title: OTHER_BOOK_TITLE }),
    );
    vi.mocked(chaptersApi.listChapters).mockImplementation(async (bookId: string) =>
      bookId === BOOK_ID ? makeChapterList() : otherList,
    );

    // The real Shell route table, so the route's own `:bookId` keying is what is under test.
    renderWithProviders(
      <MemoryRouter initialEntries={[HUB_ROUTE]}>
        <UserRoutes />
        <Link to={`/books/${OTHER_BOOK_ID}`}>Go to the other book</Link>
      </MemoryRouter>,
    );

    expect(await screen.findByRole("heading", { name: BOOK_TITLE })).toBeInTheDocument();
    expect(await screen.findByText(CH1.title)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("link", { name: "Go to the other book" }));

    // The second book's own content arrives...
    expect(await screen.findByRole("heading", { name: OTHER_BOOK_TITLE })).toBeInTheDocument();
    expect(await screen.findByText("A Wholly Different Chapter")).toBeInTheDocument();

    // ...both resources were re-loaded for the new id...
    await waitFor(() =>
      expect(
        vi.mocked(chaptersApi.listChapters).mock.calls.some(([id]) => id === OTHER_BOOK_ID),
      ).toBe(true),
    );
    expect(
      vi.mocked(booksApi.getBookDetail).mock.calls.some(([id]) => id === OTHER_BOOK_ID),
    ).toBe(true);

    // ...and nothing of the previous book survives the change.
    for (const title of ALL_TITLES) {
      expect(screen.queryByText(title)).toBeNull();
    }
    expect(screen.queryByRole("heading", { name: BOOK_TITLE })).toBeNull();
    expect(chapterLinkHrefs()).toEqual([`/work/${OTHER_BOOK_ID}/chapter/6001`]);
  });
});
