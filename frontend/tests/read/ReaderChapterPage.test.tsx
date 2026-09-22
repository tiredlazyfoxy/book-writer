/**
 * The reader's chapter page — feature 022 (ultra track), DoD-9 only.
 * (DoD-8 is `TableOfContentsPage.test.tsx`. The `<Markdown>` pass-through, the back-link,
 * `NotFoundPage`, the gate and the route table are deliberately NOT tested —
 * `plan.md` -> `## Test plan` -> "Not tested (deliberate)".)
 *
 * Bound to the frozen signatures in status.md -> `## Skeleton`:
 *   const ReaderChapterPage: FunctionComponent   // observer, ZERO props;
 *                                                // reads :bookId and :chapterId
 *   getReaderChapter(bookId, chapterId, signal?): Promise<ReaderChapterResponse>
 *   interface ReaderChapterResponse { id: string; title: string; text: string }
 *
 * `api/reader` is mocked module-factory form, enumerating all THREE frozen exports —
 * never `fetch` (root `CLAUDE.md`).
 *
 * Expected values come from the SPEC, never from the page's code:
 *   - the page renders the chapter's SAVED body, the text the server sent
 *     (US-030.AC-1, UC-029's "system returns that chapter's text, read-only");
 *   - it exposes NO edit affordance — no textbox and no save/edit control
 *     (US-030.AC-2, D11: the reader entry ships no editing surface at all).
 *
 * Every control assertion is BY ROLE, plus a direct check that nothing on the page is
 * editable in fact — never by test id, never by DOM shape.
 *
 * `globals: false`: every primitive is imported explicitly.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { Route, Routes } from "react-router-dom";
import type { ReaderChapterResponse } from "../../src/types/reader";
import * as readerApi from "../../src/api/reader";
import { ReaderChapterPage } from "../../src/read/pages/ReaderChapterPage";
import { renderWithProviders } from "../support/render";

// The WHOLE `api/reader` module, enumerating all three frozen exports.
vi.mock("../../src/api/reader", () => ({
  getReaderBook: vi.fn(),
  getReaderChapter: vi.fn(),
  listPublicBooks: vi.fn(),
}));

/** Snowflake ids as they cross the wire: strings beyond 2^53. */
const BOOK_ID = "9007199254740993";
const CHAPTER_ID = "5003";
const CHAPTER_TITLE = "Dawn Over the Wall";

/** Two plain paragraphs: the saved body, distinctive enough to find verbatim. */
const FIRST_PARAGRAPH = "The lantern guttered in the wind.";
const SECOND_PARAGRAPH = "She did not look back.";

const CHAPTER: ReaderChapterResponse = {
  id: CHAPTER_ID,
  title: CHAPTER_TITLE,
  text: `${FIRST_PARAGRAPH}\n\n${SECOND_PARAGRAPH}`,
};

/** Mounts the page under its own route so both params resolve. */
function renderPage(): void {
  renderWithProviders(
    <Routes>
      <Route path="/:bookId/:chapterId" element={<ReaderChapterPage />} />
    </Routes>,
    { route: `/${BOOK_ID}/${CHAPTER_ID}` },
  );
}

function pageText(): string {
  return document.body.textContent ?? "";
}

/**
 * Every control the reader could actually change: text-bearing inputs, textareas,
 * selects and contenteditable regions that are neither disabled nor read-only.
 */
function editableControls(): HTMLElement[] {
  const nodes = Array.from(
    document.querySelectorAll<HTMLElement>(
      "input, textarea, select, [contenteditable='true']",
    ),
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

/** Every affordance that would let a reader change the text. */
const EDITING = /save|edit|rename|write|compose|publish|discard|revert|delete|remove|draft|update/i;

beforeEach(() => {
  vi.mocked(readerApi.getReaderChapter).mockResolvedValue(CHAPTER);
});

describe("ReaderChapterPage — the read-only chapter", () => {
  it("DoD-9: renders the chapter's saved body and offers no edit affordance", async () => {
    renderPage();

    // The saved body is on the page, both paragraphs of it.
    expect(await screen.findByText(FIRST_PARAGRAPH)).toBeInTheDocument();
    expect(pageText()).toContain(SECOND_PARAGRAPH);

    // The chapter named in the URL is the one loaded.
    const call = vi.mocked(readerApi.getReaderChapter).mock.calls[0];
    expect(call[0]).toBe(BOOK_ID);
    expect(call[1]).toBe(CHAPTER_ID);

    // No input-bearing role is offered anywhere on the surface...
    for (const role of [
      "textbox",
      "searchbox",
      "combobox",
      "checkbox",
      "radio",
      "switch",
      "spinbutton",
      "slider",
    ] as const) {
      expect(screen.queryAllByRole(role)).toHaveLength(0);
    }

    // ...nothing on the page is editable in fact...
    expect(editableControls()).toEqual([]);

    // ...and no control offers to save or otherwise change the chapter.
    expect(screen.queryAllByRole("button", { name: EDITING })).toHaveLength(0);
    expect(screen.queryAllByRole("menuitem", { name: EDITING })).toHaveLength(0);
    expect(screen.queryAllByRole("link", { name: EDITING })).toHaveLength(0);
  });
});
