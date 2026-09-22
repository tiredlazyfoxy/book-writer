/**
 * The working page's chapter list — 014.chapter-skeleton / 006.work-chapters-list,
 * DoD-1 · DoD-2 · DoD-3 · DoD-4 · DoD-5 · DoD-6 · DoD-7 · DoD-8 · DoD-9 · DoD-10 ·
 * DoD-11 · DoD-12.  (DoD-13 is [manual/live] — the two build gates — and has no test.)
 *
 * Bound to the frozen signatures in status.md -> `## Skeleton` (step 006, and step 005
 * for the api/DTO contract consumed unchanged):
 *   class ChaptersPageState { chapterList; chapterListStatus; chapterListError;
 *                             addTitleDraft; addSketchDraft; addServerErrors;
 *                             addSubmitStatus; removingChapterId; removeServerErrors;
 *                             get orderedChapters; get canReorder; get addClientErrors;
 *                             get canSubmitAdd; get canRemoveChapter }
 *   loadChapters(state, bookId, signal?): Promise<void>
 *   addChapter(state, bookId, signal?): Promise<void>          // reads the drafts off state
 *   removeChapter(state, bookId, chapterId, signal?): Promise<void>
 *   const ChaptersPage: FunctionComponent   // observer, zero props; reads :bookId via router
 *   WorkRoutes                              // `chapters` child -> <ChaptersPage/>
 *   listChapters(bookId, signal?): Promise<ChapterListResponse>   // the WHOLE envelope
 *   createChapter(bookId, body: CreateChapterRequest, signal?): Promise<ChapterResponse>
 *   removeChapter(bookId, chapterId, signal?): Promise<void>
 *
 * Every expected value comes from the spec, never from the page's code:
 *   - chapters render in ORDINAL order with each state readable, so the fixture list
 *     deliberately arrives scrambled (`006` Interface intent) — DoD-1;
 *   - an empty book is a SUCCESSFUL load: an empty state plus a usable add form, never
 *     an error (`context.md` -> the list envelope; step 005's DoD-2) — DoD-2;
 *   - the backend is the source of truth: after a write the surface shows what the SERVER
 *     returned, never an optimistic splice (`context.md` -> cross-cutting frontend
 *     constraints; `006.context.md` -> "No optimistic mutation"), which is why the stored
 *     title deliberately differs from the typed one — DoD-3 (US-032.AC-1);
 *   - `ordinal` is server-assigned and a new chapter is APPENDED (`context.md` -> the wire
 *     contract; UC-031), so it renders last even though the server hands it back first in
 *     the array — DoD-4;
 *   - the title must not be blank and a whitespace-only title does not count as filled
 *     (`006.context.md` -> "The add form is the one form here with client validation"),
 *     and a submit already in flight closes the gate too — DoD-5;
 *   - a refused add surfaces the server's own message and loses nothing typed; the drafts
 *     clear only on success — DoD-6;
 *   - only a `planned` chapter may be removed, which is a CLIENT AFFORDANCE (DoD-8,
 *     US-035.AC-2) that never substitutes for the server's answer (DoD-9, US-035.AC-2):
 *     a refusal is rendered BESIDE the chapter it concerns — never as a page-level banner,
 *     which would leave the author guessing in a long list (`006.context.md` -> "Why the
 *     removal affordance is computed and the refusal is still surfaced");
 *   - a failed load renders the trio's error branch with a way to retry and NO add form
 *     bound to stale data — DoD-10;
 *   - `/work/:bookId/chapters` renders this page and the `014.chapter-skeleton`
 *     placeholder is gone — DoD-11;
 *   - the page registers itself as the content-pane subject on mount and unregisters on
 *     unmount, with NO draft applier (a list subject is read-only in the pane model) —
 *     DoD-12.
 *
 * `api/chapters` is mocked module-factory form (never `fetch`). A factory replaces the
 * WHOLE module, so every one of the eight frozen exports is enumerated — including the
 * five this step never calls; omitting one strips it to `undefined` and a later step's
 * page would fail for the wrong reason (`006.context.md` -> Testing). `ApiError` is the
 * REAL class from `api/client`: DoD-6 and DoD-9 both need one so the message surfaces the
 * way it will in production. `api/books` and `api/chats` are mocked because DoD-11 mounts
 * the whole `WorkRoutes` table, whose shell loads the book and owns the chat pane.
 *
 * Queries are by ROLE or LABEL only — no test ids, nothing asserted about colour. The
 * state badge is located by the lifecycle word its readable text carries (`planned` ->
 * "Planned"), and the remove control by its accessible name, which names its chapter.
 *
 * `globals: false`: every primitive is imported explicitly.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { Route, Routes } from "react-router-dom";
import { runInAction } from "mobx";
import type { ChapterResponse } from "../../src/types/chapters";
import type { BookDetailResponse } from "../../src/types/books";
import { ApiError } from "../../src/api/client";
import * as chaptersApi from "../../src/api/chapters";
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
import {
  ChaptersPageState,
  addChapter,
  loadChapters,
} from "../../src/work/pages/chaptersPageState";
import { ChaptersPage } from "../../src/work/pages/ChaptersPage";
import { WorkRoutes } from "../../src/work/routes";
import type { ContentSubjectSource } from "../../src/work/contentSubject";
import {
  currentContentSubject,
  registerContentSubject,
  unregisterContentSubject,
} from "../../src/work/contentSubject";
import { renderWithProviders } from "../support/render";

// A module-factory mock replaces the WHOLE module. All EIGHT frozen exports of
// `api/chapters` are enumerated, not just the three this step calls: a factory that
// omitted one would leave it `undefined` for every module importing this namespace.
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

// DoD-11 mounts the whole `WorkRoutes` table: its `/:bookId` shell loads the book and
// `WorkRoutes` also imports the Book-state page, which reads the two option arrays and
// both prompt calls. Enumerate every export so no route can hit an `undefined` one.
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

// The `/:bookId` shell owns the chat pane and starts a chat load on mount. Pure harness
// mocking — no assertion in this file depends on it.
vi.mock("../../src/api/chats", () => ({
  listChats: vi.fn(),
  createChat: vi.fn(),
  updateChat: vi.fn(),
  getChat: vi.fn(),
  listModelOptions: vi.fn(),
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
    summary: null,
    summary_status: null,
    ...overrides,
  };
}

// Four chapters, one per lifecycle state, with mutually non-substring titles so a row can
// be identified by its title alone.
const CH_PLANNED = makeChapter({
  id: "ch-1",
  ordinal: 1,
  title: "The Long Road",
  state: "planned",
});
const CH_OPEN = makeChapter({
  id: "ch-2",
  ordinal: 2,
  title: "A Bridge in Winter",
  state: "open",
});
const CH_CLOSING = makeChapter({
  id: "ch-3",
  ordinal: 3,
  title: "The Quiet House",
  state: "closing",
});
const CH_CLOSED = makeChapter({
  id: "ch-4",
  ordinal: 4,
  title: "Last Light",
  state: "closed",
});

/** A second `planned` chapter, so removal cases have a neighbour to compare against. */
const CH_PLANNED_TWO = makeChapter({
  id: "ch-5",
  ordinal: 2,
  title: "Salt and Smoke",
  state: "planned",
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
 * The chapters the server currently holds. `listChapters` always answers from here, so a
 * page that re-seeds from the server (the create response plus a reload, or the reload
 * alone) is satisfied either way, while an optimistic splice is not.
 */
let serverChapters: ChapterResponse[] = [];
let serverCanReorder = false;

function setServerChapters(chapters: ChapterResponse[]): void {
  serverChapters = [...chapters];
}

/* ------------------------------------------------------------------------ harness */

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/** Mounts the page under its own `:bookId` route so `useParams().bookId` resolves. */
function renderPage(route: string = CHAPTERS_ROUTE): { unmount: () => void } {
  const result = renderWithProviders(
    <Routes>
      <Route path="/:bookId/chapters" element={<ChaptersPage />} />
    </Routes>,
    { route },
  );
  return { unmount: result.unmount };
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

function chapterLink(title: string): HTMLElement {
  const anchor = queryChapterLink(title);
  if (anchor === null) throw new Error(`no chapter link is rendered for "${title}"`);
  return anchor;
}

/**
 * The rendered row for one chapter: the largest ancestor of its link whose text still
 * mentions no OTHER chapter on screen. Structure-agnostic — it works for a table row, a
 * list item or a card, and never assumes a DOM shape the spec does not promise.
 */
function rowFor(title: string, allTitles: string[]): HTMLElement {
  const others = allTitles.filter((other) => other !== title);
  let best: HTMLElement = chapterLink(title);
  let node: HTMLElement | null = best.parentElement;
  while (node !== null && node !== document.body) {
    const text = node.textContent ?? "";
    if (others.some((other) => text.includes(other))) break;
    best = node;
    node = node.parentElement;
  }
  return best;
}

/** The labelled title field of the add form, or `null` when no add form is rendered. */
function queryTitleField(): HTMLInputElement | HTMLTextAreaElement | null {
  const found = screen.queryAllByRole("textbox", { name: /title/i });
  return (found[0] as HTMLInputElement | HTMLTextAreaElement | undefined) ?? null;
}

function titleField(): HTMLInputElement | HTMLTextAreaElement {
  const field = queryTitleField();
  if (field === null) throw new Error("no title field is rendered on the add form");
  return field;
}

/** The labelled multi-line sketch field of the add form. */
function querySketchField(): HTMLTextAreaElement | null {
  const found = screen.queryAllByRole("textbox", { name: /sketch/i });
  return (found[0] as HTMLTextAreaElement | undefined) ?? null;
}

function sketchField(): HTMLTextAreaElement {
  const field = querySketchField();
  if (field === null) throw new Error("no sketch field is rendered on the add form");
  return field;
}

/** The add form's submit control, or `null` when none is offered. */
function findSubmit(): HTMLButtonElement | null {
  const buttons = screen.queryAllByRole("button", { name: /(add|create)/i });
  return (buttons[0] as HTMLButtonElement | undefined) ?? null;
}

function submitControl(): HTMLButtonElement {
  const button = findSubmit();
  if (button === null) throw new Error("no submit control is offered on the add form");
  return button;
}

/**
 * True when the author cannot submit right now. DoD-5 says only that submitting is
 * *unavailable*, so an absent control counts exactly as a disabled one does.
 */
function submitIsUnavailable(): boolean {
  const button = findSubmit();
  return button === null || button.disabled;
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

/** The retry affordance of the list trio's error branch. */
function queryRetryControl(): HTMLElement | null {
  return screen.queryAllByRole("button", { name: /(retry|try again|reload|refresh)/i })[0] ?? null;
}

function typeInto(field: HTMLInputElement | HTMLTextAreaElement, value: string): void {
  fireEvent.change(field, { target: { value } });
}

function pageText(): string {
  return document.body.textContent ?? "";
}

/**
 * The leaf-most elements whose text carries `message` — i.e. where the message is
 * actually rendered, not merely inherited by an ancestor. DoD-9 uses this to prove the
 * refusal is rendered beside its chapter and NOWHERE else.
 */
function leavesShowing(message: string): HTMLElement[] {
  return Array.from(document.body.querySelectorAll<HTMLElement>("*")).filter((element) => {
    if (!(element.textContent ?? "").includes(message)) return false;
    return !Array.from(element.children).some((child) =>
      (child.textContent ?? "").includes(message),
    );
  });
}

/** A fully-typed BookDetailResponse fixture — only DoD-11's shell load reads it. */
function makeDetail(): BookDetailResponse {
  return {
    id: BOOK_ID,
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

/**
 * Clear the module-level content-subject registration through the frozen API alone: the
 * newest registration wins outright, so a sentinel is always clearable by its identity.
 * Harness hygiene only — never an assertion (DoD-12 asserts the registry itself).
 */
const RESET_SOURCE: ContentSubjectSource = () => ({ kind: "chats" });
function resetSubjectRegistry(): void {
  try {
    registerContentSubject(RESET_SOURCE);
    unregisterContentSubject(RESET_SOURCE);
  } catch {
    /* the registry is unavailable; DoD-12 will say so itself */
  }
}

beforeEach(() => {
  armContinuityReads();
  resetSubjectRegistry();
  serverChapters = [];
  serverCanReorder = false;

  // `restoreMocks` wipes implementations between tests — re-arm the whole server double.
  // `listChapters` always answers the CURRENT server list, as the whole envelope.
  vi.mocked(chaptersApi.listChapters).mockImplementation(async () => ({
    chapters: [...serverChapters],
    can_reorder: serverCanReorder,
  }));

  // The server appends: the new chapter gets the next ordinal. It is handed back FIRST in
  // the array so that "renders last" can only be satisfied by ordering on `ordinal`.
  vi.mocked(chaptersApi.createChapter).mockImplementation(async (_bookId, body) => {
    const highest = serverChapters.reduce((max, chapter) => Math.max(max, chapter.ordinal), 0);
    const created = makeChapter({
      id: `ch-server-${highest + 1}`,
      ordinal: highest + 1,
      title: body.title,
      sketch: body.sketch,
      state: "planned",
    });
    serverChapters = [created, ...serverChapters];
    return created;
  });

  vi.mocked(chaptersApi.removeChapter).mockImplementation(async (_bookId, chapterId) => {
    serverChapters = serverChapters.filter((chapter) => chapter.id !== chapterId);
  });

  // Pure harness mocking for DoD-11's whole-route mount.
  vi.mocked(booksApi.getBookDetail).mockResolvedValue(makeDetail());
  vi.mocked(booksApi.getOwnSystemPrompt).mockResolvedValue({
    book_id: BOOK_ID,
    system_prompt: "",
    modified_at: null,
  });
  vi.mocked(booksApi.updateOwnSystemPrompt).mockResolvedValue({
    book_id: BOOK_ID,
    system_prompt: "",
    modified_at: null,
  });
  vi.mocked(chatsApi.listChats).mockResolvedValue([]);
  vi.mocked(chatsApi.listModelOptions).mockResolvedValue([]);
});

/* ------------------------------------------------------------- DoD-1 · DoD-2 (load) */

describe("ChaptersPage — loading the book's chapters", () => {
  it("DoD-1: on mount the page loads the book's chapters and renders them in ORDINAL order, each with its state readable", async () => {
    // The server answers in a deliberately scrambled array order: only ordering on
    // `ordinal` can produce the expected document order.
    setServerChapters([CH_CLOSING, CH_PLANNED, CH_CLOSED, CH_OPEN]);

    renderPage();

    // The load addresses the book in the URL.
    await waitFor(() => expect(vi.mocked(chaptersApi.listChapters)).toHaveBeenCalled());
    expect(vi.mocked(chaptersApi.listChapters).mock.calls[0][0]).toBe(BOOK_ID);

    const ordered = [CH_PLANNED, CH_OPEN, CH_CLOSING, CH_CLOSED];
    const titles = ordered.map((chapter) => chapter.title);

    // Every chapter is on screen, in ordinal document order.
    await waitFor(() => expect(chapterLinks()).toHaveLength(ordered.length));
    const renderedOrder = chapterLinks().map((anchor) => anchor.textContent ?? "");
    for (const [index, chapter] of ordered.entries()) {
      expect(renderedOrder[index]).toContain(chapter.title);
      // Each row links to that chapter's own working-page route.
      expect(chapterLink(chapter.title).getAttribute("href") ?? "").toContain(
        `/chapter/${chapter.id}`,
      );
    }

    // Each row reads its OWN lifecycle state, and not a neighbour's.
    for (const chapter of ordered) {
      const row = rowFor(chapter.title, titles);
      expect(row.textContent ?? "").toMatch(STATE_WORD[chapter.state]);
    }
    // "Planned" and "Open" are not interchangeable: the planned chapter's row must not
    // read as closed, and the closed one's must not read as planned.
    expect(rowFor(CH_PLANNED.title, titles).textContent ?? "").not.toMatch(/closed/i);
    expect(rowFor(CH_CLOSED.title, titles).textContent ?? "").not.toMatch(/planned/i);
  });

  it("DoD-2: a book with no chapters renders an empty state and a USABLE add form, not an error", async () => {
    setServerChapters([]);

    renderPage();

    await waitFor(() => expect(vi.mocked(chaptersApi.listChapters)).toHaveBeenCalled());

    // An empty book is a successful load: an empty state, no rows...
    await waitFor(() =>
      expect(pageText()).toMatch(/(no chapters|not have any chapters|nothing yet|none yet|is empty)/i),
    );
    expect(chapterLinks()).toHaveLength(0);

    // ...nothing failure-shaped and no retry affordance...
    expect(pageText()).not.toMatch(/(failed|could not|couldn'?t load|unavailable)/i);
    expect(queryRetryControl()).toBeNull();

    // ...and the add form is present AND usable: both fields accept text and the submit
    // control opens once a title is typed.
    expect(titleField()).toBeEnabled();
    expect(sketchField()).toBeEnabled();
    typeInto(titleField(), "A first chapter");
    typeInto(sketchField(), "Where it all begins.");
    await waitFor(() => expect(titleField().value).toBe("A first chapter"));
    expect(sketchField().value).toBe("Where it all begins.");
    await waitFor(() => expect(submitIsUnavailable()).toBe(false));
  });
});

/* ------------------------------------------------------- DoD-3 · DoD-4 · DoD-6 (add) */

describe("ChaptersPage — adding a chapter", () => {
  const TYPED_TITLE = "A chapter as the author typed it";
  const TYPED_SKETCH = "Two brothers meet on the ice and neither speaks.";
  // What the SERVER stores, deliberately different from the draft, so "shows the server's
  // answer" is distinguishable from "spliced the draft in optimistically".
  const STORED_TITLE = "A chapter as the server stored it";
  const SERVER_ID = "ch-from-the-server";

  /** The server normalises the title and assigns the id / ordinal; the sketch is echoed. */
  function armServerRewrite(): void {
    vi.mocked(chaptersApi.createChapter).mockImplementation(async (_bookId, body) => {
      const highest = serverChapters.reduce((max, chapter) => Math.max(max, chapter.ordinal), 0);
      const created = makeChapter({
        id: SERVER_ID,
        ordinal: highest + 1,
        title: STORED_TITLE,
        sketch: body.sketch,
        state: "planned",
      });
      serverChapters = [created, ...serverChapters];
      return created;
    });
  }

  it("DoD-3 (US-032.AC-1): submitting sends exactly the typed title and sketch, and the chapter then shown is the SERVER's, planned", async () => {
    setServerChapters([CH_PLANNED]);
    armServerRewrite();

    renderPage();
    await waitFor(() => expect(chapterLinks()).toHaveLength(1));

    typeInto(titleField(), TYPED_TITLE);
    typeInto(sketchField(), TYPED_SKETCH);
    await waitFor(() => expect(submitIsUnavailable()).toBe(false));

    fireEvent.click(submitControl());

    // Exactly those values reached the create call, for the book in the URL.
    await waitFor(() => expect(vi.mocked(chaptersApi.createChapter)).toHaveBeenCalled());
    const [bookIdArg, bodyArg] = vi.mocked(chaptersApi.createChapter).mock.calls[0];
    expect(bookIdArg).toBe(BOOK_ID);
    expect(bodyArg).toEqual({ title: TYPED_TITLE, sketch: TYPED_SKETCH });

    // The chapter now on screen came from the SERVER: it carries the server's title and
    // the server-assigned id, not the draft.
    await waitFor(() => expect(queryChapterLink(STORED_TITLE)).not.toBeNull());
    expect(chapterLink(STORED_TITLE).getAttribute("href") ?? "").toContain(
      `/chapter/${SERVER_ID}`,
    );
    expect(queryChapterLink(TYPED_TITLE)).toBeNull();

    // ...and it is `planned`.
    const row = rowFor(STORED_TITLE, [CH_PLANNED.title, STORED_TITLE]);
    expect(row.textContent ?? "").toMatch(/planned/i);
  });

  it("DoD-3 (US-032.AC-1): the added chapter in state is the server's row — planned, server id, carrying the SUBMITTED sketch", async () => {
    // The state layer holds the whole chapter, including the `sketch` the list does not
    // render; this is where "carrying the submitted sketch" is observable.
    setServerChapters([CH_PLANNED]);
    armServerRewrite();

    const state = new ChaptersPageState();
    await loadChapters(state, BOOK_ID);
    runInAction(() => {
      state.addTitleDraft = TYPED_TITLE;
      state.addSketchDraft = TYPED_SKETCH;
    });

    await addChapter(state, BOOK_ID);

    const added = state.orderedChapters[state.orderedChapters.length - 1];
    expect(added.id).toBe(SERVER_ID);
    expect(added.state).toBe("planned");
    expect(added.sketch).toBe(TYPED_SKETCH);
    // The server's own title, never the draft — no optimistic splice.
    expect(added.title).toBe(STORED_TITLE);
  });

  it("DoD-4 (UC-031): a newly added chapter appears LAST, even though the server hands it back first", async () => {
    setServerChapters([CH_PLANNED, CH_PLANNED_TWO]);
    armServerRewrite();

    renderPage();
    await waitFor(() => expect(chapterLinks()).toHaveLength(2));

    typeInto(titleField(), TYPED_TITLE);
    typeInto(sketchField(), TYPED_SKETCH);
    await waitFor(() => expect(submitIsUnavailable()).toBe(false));

    fireEvent.click(submitControl());

    await waitFor(() => expect(chapterLinks()).toHaveLength(3));
    const rendered = chapterLinks().map((anchor) => anchor.textContent ?? "");
    expect(rendered[0]).toContain(CH_PLANNED.title);
    expect(rendered[1]).toContain(CH_PLANNED_TWO.title);
    expect(rendered[2]).toContain(STORED_TITLE);
  });

  it("DoD-5: the submit control is unavailable while the title is blank, and a WHITESPACE-ONLY title does not count as filled", async () => {
    setServerChapters([]);

    renderPage();
    await waitFor(() => expect(queryTitleField()).not.toBeNull());

    // Blank from the start.
    expect(submitIsUnavailable()).toBe(true);

    // A sketch alone is not enough — the title is the field with the rule.
    typeInto(sketchField(), "A sketch with no title.");
    await waitFor(() => expect(sketchField().value).toBe("A sketch with no title."));
    expect(submitIsUnavailable()).toBe(true);

    // Whitespace only is still blank.
    typeInto(titleField(), "   ");
    await waitFor(() => expect(titleField().value).toBe("   "));
    expect(submitIsUnavailable()).toBe(true);

    // Mixed whitespace, including a line break. The title field is SINGLE-line (the
    // Interface intent's "multi-line" qualifier attaches to the sketch alone), and a
    // single-line input's value sanitization strips line breaks — so what the element
    // stores is deliberately not asserted here. DoD-5's claim is about submittability.
    typeInto(titleField(), "\t \n ");
    await waitFor(() => expect(submitIsUnavailable()).toBe(true));

    // A real title opens the gate...
    typeInto(titleField(), "A real title");
    await waitFor(() => expect(submitIsUnavailable()).toBe(false));

    // ...and emptying it closes it again.
    typeInto(titleField(), "");
    await waitFor(() => expect(submitIsUnavailable()).toBe(true));
  });

  it("DoD-5: the submit control is unavailable while a submit is in flight", async () => {
    setServerChapters([]);

    renderPage();
    await waitFor(() => expect(queryTitleField()).not.toBeNull());

    typeInto(titleField(), "A real title");
    await waitFor(() => expect(submitIsUnavailable()).toBe(false));

    // A create that never settles keeps the submit in flight.
    vi.mocked(chaptersApi.createChapter).mockReturnValue(new Promise<ChapterResponse>(() => {}));
    fireEvent.click(submitControl());

    await waitFor(() => expect(submitIsUnavailable()).toBe(true));
    expect(vi.mocked(chaptersApi.createChapter)).toHaveBeenCalledTimes(1);
  });

  it("DoD-6: a refused add surfaces the server's message and leaves BOTH drafts intact", async () => {
    setServerChapters([CH_PLANNED]);

    renderPage();
    await waitFor(() => expect(chapterLinks()).toHaveLength(1));

    typeInto(titleField(), TYPED_TITLE);
    typeInto(sketchField(), TYPED_SKETCH);
    await waitFor(() => expect(submitIsUnavailable()).toBe(false));

    const REFUSAL = "You may not add chapters to this book";
    vi.mocked(chaptersApi.createChapter).mockRejectedValue(new ApiError(403, REFUSAL));

    fireEvent.click(submitControl());

    // The server's own words reach the author...
    await waitFor(() => expect(pageText()).toContain(REFUSAL));
    // ...nothing typed is lost, in either field...
    expect(titleField().value).toBe(TYPED_TITLE);
    expect(sketchField().value).toBe(TYPED_SKETCH);
    // ...and nothing was added to the list.
    expect(chapterLinks()).toHaveLength(1);
  });

  it("DoD-6: the drafts clear only on SUCCESS", async () => {
    setServerChapters([CH_PLANNED]);
    armServerRewrite();

    renderPage();
    await waitFor(() => expect(chapterLinks()).toHaveLength(1));

    typeInto(titleField(), TYPED_TITLE);
    typeInto(sketchField(), TYPED_SKETCH);
    await waitFor(() => expect(submitIsUnavailable()).toBe(false));

    fireEvent.click(submitControl());

    await waitFor(() => expect(queryChapterLink(STORED_TITLE)).not.toBeNull());
    await waitFor(() => expect(titleField().value).toBe(""));
    expect(sketchField().value).toBe("");
  });
});

/* ------------------------------------------------- DoD-7 · DoD-8 · DoD-9 (removal) */

describe("ChaptersPage — removing a chapter", () => {
  it("DoD-7 (US-035.AC-1): removing a planned chapter calls the remove function and the chapter is gone afterwards", async () => {
    setServerChapters([CH_PLANNED, CH_PLANNED_TWO]);

    renderPage();
    await waitFor(() => expect(chapterLinks()).toHaveLength(2));

    fireEvent.click(removeControl(CH_PLANNED.title));

    await waitFor(() => expect(vi.mocked(chaptersApi.removeChapter)).toHaveBeenCalled());
    const [bookIdArg, chapterIdArg] = vi.mocked(chaptersApi.removeChapter).mock.calls[0];
    expect(bookIdArg).toBe(BOOK_ID);
    expect(chapterIdArg).toBe(CH_PLANNED.id);

    // Gone from the rendered list; its neighbour survives.
    await waitFor(() => expect(queryChapterLink(CH_PLANNED.title)).toBeNull());
    expect(queryChapterLink(CH_PLANNED_TWO.title)).not.toBeNull();
  });

  it("DoD-8 (US-035.AC-2, client affordance): an open, closing or closed chapter offers NO remove control", async () => {
    setServerChapters([CH_PLANNED, CH_OPEN, CH_CLOSING, CH_CLOSED]);
    const titles = [CH_PLANNED, CH_OPEN, CH_CLOSING, CH_CLOSED].map((chapter) => chapter.title);

    renderPage();
    await waitFor(() => expect(chapterLinks()).toHaveLength(4));

    // The affordance exists at all — otherwise the negatives below would be vacuous.
    expect(queryRemoveControl(CH_PLANNED.title)).not.toBeNull();

    for (const chapter of [CH_OPEN, CH_CLOSING, CH_CLOSED]) {
      // No control named for that chapter...
      expect(queryRemoveControl(chapter.title)).toBeNull();
      // ...and nothing remove-shaped anywhere in its row either.
      const row = rowFor(chapter.title, titles);
      expect(within(row).queryAllByRole("button", { name: /(remove|delete)/i })).toHaveLength(0);
    }
  });

  it("DoD-9 (US-035.AC-2, server authority): a refused removal shows the server's message BESIDE that chapter, which stays in the list", async () => {
    // Both chapters look `planned` to the client, so the affordance is offered; the server
    // is what refuses (a co-author opened it from another session between load and click).
    setServerChapters([CH_PLANNED, CH_PLANNED_TWO]);
    const titles = [CH_PLANNED.title, CH_PLANNED_TWO.title];

    renderPage();
    await waitFor(() => expect(chapterLinks()).toHaveLength(2));

    const REFUSAL = "This chapter is no longer planned and cannot be removed";
    vi.mocked(chaptersApi.removeChapter).mockRejectedValue(new ApiError(409, REFUSAL));

    fireEvent.click(removeControl(CH_PLANNED.title));

    // The server's own words reach the author...
    await waitFor(() => expect(pageText()).toContain(REFUSAL));

    // ...beside the chapter they concern, and NOT as a page-level banner: every place the
    // message is actually rendered sits inside that chapter's row.
    const refusedRow = rowFor(CH_PLANNED.title, titles);
    expect(refusedRow.textContent ?? "").toContain(REFUSAL);
    const showing = leavesShowing(REFUSAL);
    expect(showing.length).toBeGreaterThan(0);
    for (const element of showing) {
      expect(refusedRow.contains(element)).toBe(true);
    }
    // The innocent neighbour's row says nothing about it.
    expect(rowFor(CH_PLANNED_TWO.title, titles).textContent ?? "").not.toContain(REFUSAL);

    // ...and the refused chapter is still in the list, alongside its neighbour.
    expect(queryChapterLink(CH_PLANNED.title)).not.toBeNull();
    expect(queryChapterLink(CH_PLANNED_TWO.title)).not.toBeNull();
    expect(chapterLinks()).toHaveLength(2);
  });
});

/* -------------------------------------------------------------- DoD-10 (load error) */

describe("ChaptersPage — a failed list load", () => {
  it("DoD-10: the error branch renders with a way to retry, and NO add form bound to stale data", async () => {
    vi.mocked(chaptersApi.listChapters).mockRejectedValue(
      new ApiError(500, "Chapters are unavailable"),
    );

    renderPage();

    await waitFor(() => expect(vi.mocked(chaptersApi.listChapters)).toHaveBeenCalled());

    // The trio's error branch: something failure-shaped on screen (the spec pins no
    // wording) and a way to retry.
    await waitFor(() =>
      expect(pageText()).toMatch(
        /(Chapters are unavailable|failed|could not|couldn'?t|unavailable|error|retry|try again)/i,
      ),
    );
    const retry = queryRetryControl();
    expect(retry).not.toBeNull();

    // No add form bound to a list that was never read, and no rows.
    expect(queryTitleField()).toBeNull();
    expect(querySketchField()).toBeNull();
    expect(findSubmit()).toBeNull();
    expect(chapterLinks()).toHaveLength(0);

    // The retry really retries: a second load succeeds and the page recovers.
    setServerChapters([CH_PLANNED]);
    vi.mocked(chaptersApi.listChapters).mockImplementation(async () => ({
      chapters: [...serverChapters],
      can_reorder: serverCanReorder,
    }));

    fireEvent.click(retry as HTMLElement);

    await waitFor(() => expect(queryChapterLink(CH_PLANNED.title)).not.toBeNull());
    // ...and the add form is back once there is a real list behind it.
    expect(queryTitleField()).not.toBeNull();
  });
});

/* -------------------------------------------------------------------- DoD-11 (route) */

describe("the /work/:bookId/chapters route", () => {
  it("DoD-11: the route renders this page and no longer renders the 014.chapter-skeleton placeholder", async () => {
    setServerChapters([CH_PLANNED, CH_OPEN]);

    // The whole WORK route table, at the basename-stripped chapters route.
    renderWithProviders(<WorkRoutes />, { route: CHAPTERS_ROUTE });

    // Scope to the content pane (`main`): the chat pane renders beside it.
    const main = await screen.findByRole("main");

    // This page is what resolved there: the book's chapters are listed, loaded for the
    // routed book id...
    await waitFor(() => expect(vi.mocked(chaptersApi.listChapters)).toHaveBeenCalled());
    expect(vi.mocked(chaptersApi.listChapters).mock.calls[0][0]).toBe(BOOK_ID);
    expect(await within(main).findByRole("link", { name: new RegExp(escapeRegExp(CH_PLANNED.title), "i") })).toBeInTheDocument();
    // ...and the add form this step introduces is present.
    expect(within(main).queryAllByRole("textbox", { name: /title/i }).length).toBeGreaterThan(0);

    // The placeholder is gone from the content pane.
    expect(within(main).queryByText(/014\.chapter-skeleton/)).toBeNull();
  });
});

/* ---------------------------------------------------------- DoD-12 (content subject) */

describe("ChaptersPage — the content-pane subject", () => {
  it("DoD-12: the page registers itself as the content-pane subject on mount and unregisters on unmount", async () => {
    setServerChapters([CH_PLANNED]);

    // Nothing is registered before the page mounts.
    expect(currentContentSubject()).toBeNull();

    const page = renderPage();

    // Registered on mount, as the chapters LIST — a list names no entity.
    await waitFor(() => expect(currentContentSubject()?.kind).toBe("chapters"));
    expect(currentContentSubject()?.entityId ?? null).toBeNull();

    // Still registered once the load has settled.
    await waitFor(() => expect(queryChapterLink(CH_PLANNED.title)).not.toBeNull());
    expect(currentContentSubject()?.kind).toBe("chapters");

    page.unmount();

    expect(currentContentSubject()).toBeNull();
  });
});
