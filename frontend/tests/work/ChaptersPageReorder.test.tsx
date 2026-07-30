/**
 * Reordering the chapter skeleton — 014.chapter-skeleton / 007.chapter-reorder,
 * DoD-1 · DoD-2 · DoD-3 · DoD-4 · DoD-5 · DoD-6 · DoD-7 · DoD-8 · DoD-9.
 * (DoD-10 — the drag gesture — and DoD-11 — the three build gates — are
 * [manual/live] and have no test here: `context.md` -> D3 fixes the ↑/↓ BUTTONS as
 * the tested path, and `007.context.md` explains why jsdom cannot drive `@dnd-kit`'s
 * pointer sensor. DoD-6 is what makes testing the buttons test the drag's write path
 * too — both affordances funnel into ONE persist call.)
 *
 * Deliberately a SEPARATE file from step 006's `ChaptersPage.test.tsx` so the two
 * steps' coverage stays attributable; that file is untouched and must keep passing
 * unchanged (step-007 DoD-9 is what proves the row move dropped nothing).
 *
 * Bound to the frozen signatures in status.md -> `## Skeleton` (step 007, plus steps
 * 005/006 for the api, DTO and state contracts consumed unchanged):
 *   type ChapterMoveDirection = "up" | "down"
 *   class ChaptersPageState { … reorderStatus; reorderError; pendingOrder;
 *                             get canMoveUp; get canMoveDown }
 *   moveChapter(state, bookId, chapterId, direction, signal?): Promise<void>
 *   applyChapterOrder(state, bookId, chapterIds, signal?): Promise<void>
 *   interface ChapterOrderListProps { state: ChaptersPageState; bookId: string }
 *   const ChapterOrderList: observer component taking those props
 *   const ChaptersPage: FunctionComponent   // observer, zero props; reads :bookId
 *   loadChapters(state, bookId, signal?): Promise<void>
 *   reorderChapters(bookId, body: ReorderChaptersRequest, signal?)
 *                                                : Promise<ChapterListResponse>
 *
 * Every expected value comes from the spec, never from the page's code:
 *   - a move sends the FULL ordered id list with that chapter shifted one position —
 *     there is no per-chapter move endpoint and a partial list is refused
 *     (`context.md` -> D3) — DoD-1 (US-033.AC-1), DoD-2;
 *   - after a move the rendered order is the order the SERVER returned, never the
 *     attempted one: the list is re-seeded from the server, and `pendingOrder` is a
 *     rendering optimism that is discarded on both outcomes (`007.context.md` ->
 *     "The pending order must snap back") — DoD-1, DoD-5;
 *   - ↑ is unavailable on the first chapter and ↓ on the last, so a one-chapter book
 *     offers neither — DoD-3;
 *   - when the list envelope's `can_reorder` is false the move controls and the drag
 *     affordance are ABSENT, not disabled, while the rest of the list renders
 *     normally — DoD-4 (US-033.AC-2, client affordance);
 *   - the hint can go stale, so the server stays the authority: a refusal is surfaced
 *     AND the rendered order returns to the server's — DoD-5 (US-033.AC-2, server
 *     authority);
 *   - one persist path: the api's reorder function is the only chapter WRITE a move
 *     triggers, called exactly once, with the whole ordered id list. Asserted on the
 *     mock's call count and payload, not on rendered order alone — a double-submit
 *     would otherwise pass (`007.context.md` -> Testing) — DoD-6;
 *   - the controls are disabled while a reorder is in flight so a second move cannot
 *     race the first — DoD-7;
 *   - the three error surfaces are independent: a reorder failure disturbs neither
 *     the add form's drafts nor the per-chapter removal messages — DoD-8;
 *   - the rows still carry title, state, chapter link and the `planned` chapter's
 *     remove control after the markup moved into `ChapterOrderList` — DoD-9.
 *
 * `api/chapters` is mocked module-factory form (never `fetch`). A factory replaces
 * the WHOLE module, so all EIGHT frozen exports are enumerated — omitting one strips
 * it to `undefined` and the page would fail for the wrong reason. `ApiError` is the
 * REAL class from `api/client`: DoD-5 and DoD-8 need one so the refusal surfaces the
 * way it will in production.
 *
 * Queries are by ROLE or LABEL only — no test ids, nothing asserted about colour.
 * A move control is reached by its accessible name, which names the chapter and the
 * direction (`getByRole("button", { name: /move .* up/i })`).
 *
 * `globals: false`: every primitive is imported explicitly.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { Route, Routes } from "react-router-dom";
import type {
  ChapterListResponse,
  ChapterResponse,
} from "../../src/types/chapters";
import { ApiError } from "../../src/api/client";
import * as chaptersApi from "../../src/api/chapters";
import {
  ChaptersPageState,
  loadChapters,
} from "../../src/work/pages/chaptersPageState";
import { ChapterOrderList } from "../../src/work/components/chapters/ChapterOrderList";
import { ChaptersPage } from "../../src/work/pages/ChaptersPage";
import { renderWithProviders } from "../support/render";

// A module-factory mock replaces the WHOLE module. All EIGHT frozen exports of
// `api/chapters` are enumerated, not just the reorder function this step drives: a
// factory that omitted one would leave it `undefined` for the page importing this
// namespace, and the page would fail for the wrong reason.
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

/* ----------------------------------------------------------------------- fixtures */

const BOOK_ID = "bk-1";
const CHAPTERS_ROUTE = `/${BOOK_ID}/chapters`;

/** A fully-typed ChapterResponse fixture; callers override the fields they assert on. */
function makeChapter(
  overrides: Partial<ChapterResponse> & { id: string; ordinal: number; title: string },
): ChapterResponse {
  return {
    book_id: BOOK_ID,
    state: "planned",
    sketch: "",
    version: 0,
    created_at: "2026-01-02T08:00:00Z",
    modified_at: "2026-03-04T09:00:00Z",
    ...overrides,
  };
}

// Four `planned` chapters with mutually non-substring titles, so a row and a control
// can be identified by title alone.
const CH_A = makeChapter({ id: "ch-a", ordinal: 1, title: "The Long Road" });
const CH_B = makeChapter({ id: "ch-b", ordinal: 2, title: "Salt and Smoke" });
const CH_C = makeChapter({ id: "ch-c", ordinal: 3, title: "A Bridge in Winter" });
const CH_D = makeChapter({ id: "ch-d", ordinal: 4, title: "Last Light" });

/** A chapter only the SERVER knows about — see DoD-1. */
const CH_FROM_SERVER = makeChapter({
  id: "ch-server",
  ordinal: 5,
  title: "Ashes of Morning",
});

// One chapter per lifecycle state, for DoD-4 and DoD-9.
const LC_PLANNED = makeChapter({
  id: "lc-1",
  ordinal: 1,
  title: "The Long Road",
  state: "planned",
});
const LC_OPEN = makeChapter({
  id: "lc-2",
  ordinal: 2,
  title: "A Bridge in Winter",
  state: "open",
});
const LC_CLOSING = makeChapter({
  id: "lc-3",
  ordinal: 3,
  title: "The Quiet House",
  state: "closing",
});
const LC_CLOSED = makeChapter({
  id: "lc-4",
  ordinal: 4,
  title: "Last Light",
  state: "closed",
});

/** The lifecycle word each state must be readable as, per the spec's own vocabulary. */
const STATE_WORD: Record<ChapterResponse["state"], RegExp> = {
  planned: /planned/i,
  open: /open/i,
  closing: /closing/i,
  closed: /closed/i,
};

/* ------------------------------------------------------------------ server double */

/**
 * The chapters the server currently holds, in the server's own order.
 * `listChapters` always answers from here as the WHOLE envelope, and the default
 * `reorderChapters` applies the submitted sequence and rewrites ordinals `1..N`
 * (`context.md` -> D3) — so any legal re-seed strategy (the returned envelope, or a
 * fresh load) satisfies the assertions while a purely local splice does not.
 */
let serverChapters: ChapterResponse[] = [];
let serverCanReorder = true;

function setServerChapters(chapters: ChapterResponse[]): void {
  serverChapters = [...chapters];
}

function envelope(): ChapterListResponse {
  return { chapters: [...serverChapters], can_reorder: serverCanReorder };
}

/** The submitted sequence applied to the server's rows, ordinals rewritten `1..N`. */
function applyOrder(chapterIds: string[]): ChapterResponse[] {
  const byId = new Map(serverChapters.map((chapter) => [chapter.id, chapter]));
  return chapterIds.map((id, index) => {
    const chapter = byId.get(id);
    if (chapter === undefined) throw new Error(`the server holds no chapter "${id}"`);
    return { ...chapter, ordinal: index + 1 };
  });
}

/* ------------------------------------------------------------------------ harness */

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/** Mounts the whole page under its own `:bookId` route so `useParams()` resolves. */
function renderPage(route: string = CHAPTERS_ROUTE): { unmount: () => void } {
  const result = renderWithProviders(
    <Routes>
      <Route path="/:bookId/chapters" element={<ChaptersPage />} />
    </Routes>,
    { route },
  );
  return { unmount: result.unmount };
}

/** Mounts `ChapterOrderList` alone, bound to its two frozen props. */
async function renderOrderList(): Promise<ChaptersPageState> {
  const state = new ChaptersPageState();
  await loadChapters(state, BOOK_ID);
  renderWithProviders(<ChapterOrderList state={state} bookId={BOOK_ID} />, {
    route: CHAPTERS_ROUTE,
  });
  return state;
}

/** Every rendered chapter link, in document order. */
function chapterLinks(): HTMLElement[] {
  return screen
    .queryAllByRole("link")
    .filter((anchor) => (anchor.getAttribute("href") ?? "").includes("/chapter/"));
}

function queryChapterLink(title: string): HTMLElement | null {
  const wanted = new RegExp(escapeRegExp(title), "i");
  return chapterLinks().find((anchor) => wanted.test(anchor.textContent ?? "")) ?? null;
}

/** Asserts the chapters are on screen in exactly this order. */
function expectRenderedOrder(expected: ChapterResponse[]): void {
  const rendered = chapterLinks().map((anchor) => anchor.textContent ?? "");
  expect(rendered).toHaveLength(expected.length);
  expected.forEach((chapter, index) => {
    expect(rendered[index]).toContain(chapter.title);
  });
}

/**
 * The rendered row for one chapter: the largest ancestor of its link whose text still
 * mentions no OTHER chapter on screen. Structure-agnostic — it works for a card, a
 * list item or a table row, and never assumes a DOM shape the spec does not promise.
 */
function rowFor(title: string, allTitles: string[]): HTMLElement {
  const others = allTitles.filter((other) => other !== title);
  const link = queryChapterLink(title);
  if (link === null) throw new Error(`no chapter link is rendered for "${title}"`);
  let best: HTMLElement = link;
  let node: HTMLElement | null = best.parentElement;
  while (node !== null && node !== document.body) {
    const text = node.textContent ?? "";
    if (others.some((other) => text.includes(other))) break;
    best = node;
    node = node.parentElement;
  }
  return best;
}

/**
 * The ↑ / ↓ control of one chapter, located by its accessible NAME: the spec requires
 * the name to carry the chapter and the direction, so this is the query shape
 * `007.context.md` -> Testing names.
 */
function queryMoveControl(title: string, direction: "up" | "down"): HTMLButtonElement | null {
  const named = new RegExp(`move\\b.*${escapeRegExp(title)}.*\\b${direction}\\b`, "i");
  return (screen.queryAllByRole("button", { name: named })[0] as HTMLButtonElement | undefined) ?? null;
}

function moveControl(title: string, direction: "up" | "down"): HTMLButtonElement {
  const button = queryMoveControl(title, direction);
  if (button === null) throw new Error(`no "move ${direction}" control is offered for "${title}"`);
  return button;
}

/**
 * True when that move is not on offer right now. DoD-3 says the control is
 * *unavailable* at the ends, so an absent control counts exactly as a disabled one.
 */
function moveIsUnavailable(title: string, direction: "up" | "down"): boolean {
  const button = queryMoveControl(title, direction);
  return button === null || button.disabled;
}

/**
 * Every move control on screen, whichever chapter it names — matched by the same
 * chapter-plus-DIRECTION name shape the per-chapter helper uses. The qualification is
 * load-bearing: the frozen remove-control name is `Remove "<title>"`, and an
 * unqualified /move/i would capture it, since "Remove" contains those letters.
 */
function allMoveControls(): HTMLButtonElement[] {
  const found = [
    ...screen.queryAllByRole("button", { name: /move\b.*\bup\b/i }),
    ...screen.queryAllByRole("button", { name: /move\b.*\bdown\b/i }),
  ] as HTMLButtonElement[];
  return [...new Set(found)];
}

/** The remove control belonging to one chapter — located by its accessible NAME. */
function queryRemoveControl(title: string): HTMLElement | null {
  const named = new RegExp(`(remove|delete).*${escapeRegExp(title)}`, "i");
  return screen.queryAllByRole("button", { name: named })[0] ?? null;
}

function removeControl(title: string): HTMLElement {
  const button = queryRemoveControl(title);
  if (button === null) throw new Error(`no remove control is offered for "${title}"`);
  return button;
}

function titleField(): HTMLInputElement | HTMLTextAreaElement {
  const found = screen.queryAllByRole("textbox", { name: /title/i })[0];
  if (found === undefined) throw new Error("no title field is rendered on the add form");
  return found as HTMLInputElement | HTMLTextAreaElement;
}

function sketchField(): HTMLTextAreaElement {
  const found = screen.queryAllByRole("textbox", { name: /sketch/i })[0];
  if (found === undefined) throw new Error("no sketch field is rendered on the add form");
  return found as HTMLTextAreaElement;
}

function typeInto(field: HTMLInputElement | HTMLTextAreaElement, value: string): void {
  fireEvent.change(field, { target: { value } });
}

function pageText(): string {
  return document.body.textContent ?? "";
}

/** Lets any already-resolved promise chain settle before a "still only once" assertion. */
async function settle(): Promise<void> {
  await Promise.resolve();
  await Promise.resolve();
  await Promise.resolve();
}

beforeEach(() => {
  serverChapters = [];
  serverCanReorder = true;

  // `restoreMocks` wipes implementations between tests — re-arm the whole double.
  vi.mocked(chaptersApi.listChapters).mockImplementation(async () => envelope());

  vi.mocked(chaptersApi.reorderChapters).mockImplementation(async (_bookId, body) => {
    serverChapters = applyOrder(body.chapter_ids);
    return envelope();
  });

  vi.mocked(chaptersApi.removeChapter).mockImplementation(async (_bookId, chapterId) => {
    serverChapters = serverChapters.filter((chapter) => chapter.id !== chapterId);
  });
});

/* ------------------------------------------------------ DoD-1 · DoD-2 (the moves) */

describe("ChaptersPage — moving a chapter with the ↑ / ↓ controls", () => {
  it("DoD-1 (US-033.AC-1): moving a chapter DOWN sends the FULL ordered id list with it one position later, and the order then shown is the SERVER's", async () => {
    setServerChapters([CH_A, CH_B, CH_C, CH_D]);

    // The server is the authority on what the list now is: while this move was in
    // flight a co-author appended a fifth chapter, so the envelope the PUT answers
    // with carries it. Only a page that re-seeds from the server can render it.
    vi.mocked(chaptersApi.reorderChapters).mockImplementation(async (_bookId, body) => {
      serverChapters = [...applyOrder(body.chapter_ids), CH_FROM_SERVER];
      return envelope();
    });

    renderPage();
    await waitFor(() => expect(chapterLinks()).toHaveLength(4));

    fireEvent.click(moveControl(CH_B.title, "down"));

    // The whole ordered set went over the wire, for the book in the URL, with B one
    // position later — never a partial list and never a per-chapter move.
    await waitFor(() => expect(vi.mocked(chaptersApi.reorderChapters)).toHaveBeenCalled());
    const [bookIdArg, bodyArg] = vi.mocked(chaptersApi.reorderChapters).mock.calls[0];
    expect(bookIdArg).toBe(BOOK_ID);
    expect(bodyArg).toEqual({ chapter_ids: [CH_A.id, CH_C.id, CH_B.id, CH_D.id] });

    // The rendered order afterwards is the server's answer, in full.
    await waitFor(() =>
      expectRenderedOrder([CH_A, CH_C, CH_B, CH_D, CH_FROM_SERVER]),
    );
  });

  it("DoD-2: moving a chapter UP is the mirror image, and the list it sends is the COMPLETE current set", async () => {
    setServerChapters([CH_A, CH_B, CH_C, CH_D]);

    renderPage();
    await waitFor(() => expect(chapterLinks()).toHaveLength(4));

    fireEvent.click(moveControl(CH_C.title, "up"));

    await waitFor(() => expect(vi.mocked(chaptersApi.reorderChapters)).toHaveBeenCalled());
    const [bookIdArg, bodyArg] = vi.mocked(chaptersApi.reorderChapters).mock.calls[0];
    expect(bookIdArg).toBe(BOOK_ID);
    expect(bodyArg).toEqual({ chapter_ids: [CH_A.id, CH_C.id, CH_B.id, CH_D.id] });

    // Complete: every current chapter is named exactly once, none is dropped and
    // none is invented — a set the server would refuse otherwise (D3).
    const sent = bodyArg.chapter_ids;
    expect(sent).toHaveLength(4);
    expect([...sent].sort()).toEqual([CH_A.id, CH_B.id, CH_C.id, CH_D.id].sort());

    await waitFor(() => expectRenderedOrder([CH_A, CH_C, CH_B, CH_D]));
  });
});

/* ----------------------------------------------------------- DoD-3 (the two ends) */

describe("ChapterOrderList — the ends of the list", () => {
  it("DoD-3: ↑ is unavailable on the FIRST chapter and ↓ on the LAST, while the middle offers both", async () => {
    setServerChapters([CH_A, CH_B, CH_C, CH_D]);

    await renderOrderList();
    await waitFor(() => expect(chapterLinks()).toHaveLength(4));

    // The first chapter cannot move up; it can still move down.
    expect(moveIsUnavailable(CH_A.title, "up")).toBe(true);
    expect(moveIsUnavailable(CH_A.title, "down")).toBe(false);

    // The last chapter cannot move down; it can still move up.
    expect(moveIsUnavailable(CH_D.title, "down")).toBe(true);
    expect(moveIsUnavailable(CH_D.title, "up")).toBe(false);

    // The middle chapters offer both, so the negatives above are not vacuous.
    for (const chapter of [CH_B, CH_C]) {
      expect(moveIsUnavailable(chapter.title, "up")).toBe(false);
      expect(moveIsUnavailable(chapter.title, "down")).toBe(false);
    }
  });

  it("DoD-3: a one-chapter book offers NEITHER direction", async () => {
    setServerChapters([CH_A]);

    await renderOrderList();
    await waitFor(() => expect(chapterLinks()).toHaveLength(1));

    expect(moveIsUnavailable(CH_A.title, "up")).toBe(true);
    expect(moveIsUnavailable(CH_A.title, "down")).toBe(true);
  });
});

/* --------------------------------------------- DoD-4 (the client-side affordance) */

describe("ChaptersPage — a caller who may not reorder", () => {
  it("DoD-4 (US-033.AC-2, client affordance): with can_reorder false NO move control and NO drag affordance is rendered, while the rest of the list renders normally", async () => {
    setServerChapters([LC_PLANNED, LC_OPEN, LC_CLOSING, LC_CLOSED]);
    serverCanReorder = false;
    const titles = [LC_PLANNED, LC_OPEN, LC_CLOSING, LC_CLOSED].map((c) => c.title);

    renderPage();
    await waitFor(() => expect(chapterLinks()).toHaveLength(4));

    // Absence, not disabledness: there is no move control at all, in either
    // direction, for any chapter.
    expect(allMoveControls()).toHaveLength(0);
    for (const chapter of [LC_PLANNED, LC_OPEN, LC_CLOSING, LC_CLOSED]) {
      expect(queryMoveControl(chapter.title, "up")).toBeNull();
      expect(queryMoveControl(chapter.title, "down")).toBeNull();
    }

    // ...and no drag affordance either: nothing drag-shaped by name, nothing
    // natively draggable, and none of the sortable/announcement markup the drag
    // library renders around a sortable list.
    expect(
      screen.queryAllByRole("button", { name: /(drag|reorder|sort|handle)/i }),
    ).toHaveLength(0);
    expect(document.body.querySelectorAll('[draggable="true"]')).toHaveLength(0);
    expect(document.body.querySelectorAll("[aria-roledescription]")).toHaveLength(0);
    expect(document.body.querySelectorAll('[id^="DndDescribedBy"]')).toHaveLength(0);
    expect(document.body.querySelectorAll('[id^="DndLiveRegion"]')).toHaveLength(0);

    // The rest of the list is untouched: every chapter, in ordinal order, linked,
    // with its own state readable, and the planned chapter's remove control intact.
    expectRenderedOrder([LC_PLANNED, LC_OPEN, LC_CLOSING, LC_CLOSED]);
    for (const chapter of [LC_PLANNED, LC_OPEN, LC_CLOSING, LC_CLOSED]) {
      const row = rowFor(chapter.title, titles);
      expect(row.textContent ?? "").toMatch(STATE_WORD[chapter.state]);
      expect(
        within(row)
          .getAllByRole("link")
          .some((anchor) => (anchor.getAttribute("href") ?? "").includes(`/chapter/${chapter.id}`)),
      ).toBe(true);
    }
    expect(queryRemoveControl(LC_PLANNED.title)).not.toBeNull();
  });
});

/* ----------------------------------------------- DoD-5 (the server is the authority) */

describe("ChaptersPage — a refused reorder", () => {
  it("DoD-5 (US-033.AC-2, server authority): the refusal is surfaced AND the rendered order returns to the SERVER's", async () => {
    // The hint said the caller may reorder — it can go stale between the load and the
    // click, so the buttons are on offer and the server is what refuses.
    setServerChapters([CH_A, CH_B, CH_C]);

    renderPage();
    await waitFor(() => expect(chapterLinks()).toHaveLength(3));

    const REFUSAL = "Only the book's owner may set the chapter order";
    vi.mocked(chaptersApi.reorderChapters).mockRejectedValue(new ApiError(403, REFUSAL));

    fireEvent.click(moveControl(CH_A.title, "down"));

    // The server's own words reach the author...
    await waitFor(() => expect(pageText()).toContain(REFUSAL));

    // ...and the order on screen is the one the server still holds, NOT the attempted
    // [B, A, C]: keeping the attempt would leave the author looking at an order the
    // server does not have.
    await waitFor(() => expectRenderedOrder([CH_A, CH_B, CH_C]));
  });
});

/* -------------------------------------------------------- DoD-6 (one persist path) */

describe("ChaptersPage — one persist path per move", () => {
  it("DoD-6: a move calls the api's reorder function EXACTLY ONCE with the whole ordered id list, and triggers no other chapter write", async () => {
    setServerChapters([CH_A, CH_B, CH_C, CH_D]);

    renderPage();
    await waitFor(() => expect(chapterLinks()).toHaveLength(4));

    fireEvent.click(moveControl(CH_D.title, "up"));

    await waitFor(() => expectRenderedOrder([CH_A, CH_B, CH_D, CH_C]));
    await settle();

    // Exactly one persist call — a double-submit would render the same order.
    expect(vi.mocked(chaptersApi.reorderChapters)).toHaveBeenCalledTimes(1);
    const [bookIdArg, bodyArg] = vi.mocked(chaptersApi.reorderChapters).mock.calls[0];
    expect(bookIdArg).toBe(BOOK_ID);
    expect(bodyArg).toEqual({ chapter_ids: [CH_A.id, CH_B.id, CH_D.id, CH_C.id] });

    // ...and it is the ONLY chapter write the move triggered.
    expect(vi.mocked(chaptersApi.createChapter)).not.toHaveBeenCalled();
    expect(vi.mocked(chaptersApi.updateChapterSketch)).not.toHaveBeenCalled();
    expect(vi.mocked(chaptersApi.removeChapter)).not.toHaveBeenCalled();
  });
});

/* ------------------------------------------------------------- DoD-7 (no racing) */

describe("ChaptersPage — a reorder in flight", () => {
  it("DoD-7: the move controls are disabled while a reorder is in flight, so a second move cannot race the first", async () => {
    setServerChapters([CH_A, CH_B, CH_C, CH_D]);

    renderPage();
    await waitFor(() => expect(chapterLinks()).toHaveLength(4));

    // A reorder that never settles keeps one in flight.
    vi.mocked(chaptersApi.reorderChapters).mockReturnValue(
      new Promise<ChapterListResponse>(() => {}),
    );

    fireEvent.click(moveControl(CH_A.title, "down"));

    await waitFor(() => {
      const controls = allMoveControls();
      expect(controls.length).toBeGreaterThan(0);
      for (const control of controls) expect(control.disabled).toBe(true);
    });

    // A second move cannot get out while the first is unanswered.
    fireEvent.click(moveControl(CH_C.title, "down"));
    await settle();
    expect(vi.mocked(chaptersApi.reorderChapters)).toHaveBeenCalledTimes(1);
  });
});

/* --------------------------------------------- DoD-8 (three independent surfaces) */

describe("ChaptersPage — the three error surfaces are independent", () => {
  it("DoD-8: a reorder failure disturbs neither the add form's drafts nor a per-chapter removal message", async () => {
    setServerChapters([CH_A, CH_B]);

    renderPage();
    await waitFor(() => expect(chapterLinks()).toHaveLength(2));

    // Something typed into the add form, unsubmitted.
    const TYPED_TITLE = "A chapter the author is still writing down";
    const TYPED_SKETCH = "Two brothers meet on the ice and neither speaks.";
    typeInto(titleField(), TYPED_TITLE);
    typeInto(sketchField(), TYPED_SKETCH);
    await waitFor(() => expect(titleField().value).toBe(TYPED_TITLE));

    // A refused removal, whose message belongs to one chapter.
    const REMOVE_REFUSAL = "This chapter is no longer planned and cannot be removed";
    vi.mocked(chaptersApi.removeChapter).mockRejectedValue(new ApiError(409, REMOVE_REFUSAL));
    fireEvent.click(removeControl(CH_B.title));
    await waitFor(() => expect(pageText()).toContain(REMOVE_REFUSAL));

    // Now a refused reorder, the third surface.
    const REORDER_REFUSAL = "Only the book's owner may set the chapter order";
    vi.mocked(chaptersApi.reorderChapters).mockRejectedValue(new ApiError(403, REORDER_REFUSAL));
    fireEvent.click(moveControl(CH_A.title, "down"));
    await waitFor(() => expect(pageText()).toContain(REORDER_REFUSAL));

    // Nothing typed is lost...
    expect(titleField().value).toBe(TYPED_TITLE);
    expect(sketchField().value).toBe(TYPED_SKETCH);
    // ...the removal refusal still stands beside its chapter...
    expect(pageText()).toContain(REMOVE_REFUSAL);
    expect(rowFor(CH_B.title, [CH_A.title, CH_B.title]).textContent ?? "").toContain(
      REMOVE_REFUSAL,
    );
    // ...and both chapters are still listed, in the server's order.
    expectRenderedOrder([CH_A, CH_B]);
  });
});

/* ----------------------------------------- DoD-9 (the rows survived the move here) */

describe("ChapterOrderList — the row content step 006 rendered", () => {
  it("DoD-9: every row still carries its title, its state, its chapter link, and the remove control on a planned chapter", async () => {
    setServerChapters([LC_PLANNED, LC_OPEN, LC_CLOSING, LC_CLOSED]);
    const chapters = [LC_PLANNED, LC_OPEN, LC_CLOSING, LC_CLOSED];
    const titles = chapters.map((chapter) => chapter.title);

    renderPage();
    await waitFor(() => expect(chapterLinks()).toHaveLength(4));

    // Title, ordinal order, per-chapter link and own lifecycle word — the whole row
    // content, unchanged by the markup's move into `ChapterOrderList`.
    expectRenderedOrder(chapters);
    for (const chapter of chapters) {
      const row = rowFor(chapter.title, titles);
      expect(row.textContent ?? "").toContain(chapter.title);
      expect(row.textContent ?? "").toMatch(STATE_WORD[chapter.state]);
      expect(
        within(row)
          .getAllByRole("link")
          .some((anchor) => (anchor.getAttribute("href") ?? "").includes(`/chapter/${chapter.id}`)),
      ).toBe(true);
    }
    // "Planned" and "Open" are not interchangeable.
    expect(rowFor(LC_PLANNED.title, titles).textContent ?? "").not.toMatch(/closed/i);
    expect(rowFor(LC_CLOSED.title, titles).textContent ?? "").not.toMatch(/planned/i);

    // The remove control survived the move too, and still removes.
    fireEvent.click(removeControl(LC_PLANNED.title));
    await waitFor(() => expect(vi.mocked(chaptersApi.removeChapter)).toHaveBeenCalled());
    const [bookIdArg, chapterIdArg] = vi.mocked(chaptersApi.removeChapter).mock.calls[0];
    expect(bookIdArg).toBe(BOOK_ID);
    expect(chapterIdArg).toBe(LC_PLANNED.id);
    await waitFor(() => expect(queryChapterLink(LC_PLANNED.title)).toBeNull());
  });
});
