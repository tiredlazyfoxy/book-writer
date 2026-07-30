/**
 * The working page's chapter item — 014.chapter-skeleton / 008.work-chapter-item,
 * DoD-1 · DoD-2 · DoD-3 · DoD-4 · DoD-5 · DoD-6 · DoD-7 · DoD-8 · DoD-9 · DoD-10 ·
 * DoD-11 · DoD-14.
 * (DoD-12 / DoD-13 are the subject model — `subject.test.ts`. DoD-15 and DoD-16 are
 *  [manual/live] — two members on one chapter, and the two build gates — and have no test.)
 *
 * Bound to the frozen signatures in status.md -> `## Skeleton` (step 008, and step 005
 * for the api/DTO contract consumed unchanged):
 *   const ChapterPage: FunctionComponent   // observer, ZERO props; reads :bookId and :id
 *                                          // from the router
 *   class ChapterPageState { chapter; chapterStatus; chapterError;
 *                            sketchDraft; sketchServerErrors; sketchSubmitStatus;
 *                            systemPrompt; systemPromptStatus; systemPromptError;
 *                            systemPromptDraft; systemPromptServerErrors;
 *                            systemPromptSubmitStatus;
 *                            get lifecycleStateLabel; get canEditSketch;
 *                            get sketchDisabledReason; get sketchDirty; get canSaveSketch;
 *                            get systemPromptDirty; get canSaveSystemPrompt }
 *   loadChapter(state, bookId, chapterId, signal?): Promise<void>
 *   saveSketch(state, bookId, chapterId, signal?): Promise<void>
 *   loadSystemPrompt(state, bookId, chapterId, signal?): Promise<void>
 *   saveSystemPrompt(state, bookId, chapterId, signal?): Promise<void>
 *   getChapter(bookId, chapterId, signal?): Promise<ChapterResponse>
 *   updateChapterSketch(bookId, chapterId, body: UpdateChapterSketchRequest, signal?)
 *                                            : Promise<ChapterResponse>
 *   getOwnChapterSystemPrompt(bookId, chapterId, signal?)
 *                                            : Promise<ChapterAuthorPromptResponse>
 *   updateOwnChapterSystemPrompt(bookId, chapterId,
 *                                body: UpdateChapterAuthorPromptRequest, signal?)
 *                                            : Promise<ChapterAuthorPromptResponse>
 *   registerContentSubject / unregisterContentSubject / currentContentSubject
 *   WorkRoutes   // `chapter/:id` child -> <ChapterPage key={id} />
 *
 * Every expected value comes from the spec, never from the page's code:
 *   - the route shows the chapter's title, ordinal and readable state, and the
 *     `014.chapter-skeleton` placeholder is gone (`008` Interface intent) — DoD-1;
 *   - only a `planned` chapter's sketch may be edited (UC-033 / US-034.AC-1,
 *     `domain-chapter.md`), and the backend is the source of truth: after a save the
 *     editor shows what the SERVER returned, never the optimistic draft (`context.md` ->
 *     cross-cutting frontend constraints), which is why the stored value deliberately
 *     differs from the typed one — DoD-2;
 *   - on `open` / `closing` / `closed` the sketch editor is disabled with a STATED
 *     REASON (readable text, never a visual state) and offers no save — DoD-3, the
 *     client affordance half of US-034.AC-2;
 *   - the client affordance never substitutes for the server's answer: a refused save
 *     surfaces the server's own message and loses nothing typed — DoD-4 (US-034.AC-2,
 *     the `409` of `context.md` -> status taxonomy) and DoD-8;
 *   - the sketch save is gated on "dirty AND no save in flight", with NO emptiness
 *     check — every string including `""` is a valid sketch (`008.context.md`) — DoD-5;
 *   - the caller's own chapter prompt loads on mount alongside the chapter — DoD-6;
 *   - `""` with `modified_at: null` is the NORMAL starting state of every chapter for
 *     every author (`context.md` -> "A missing row is a 200 with an empty prompt, never
 *     a 404"), so it renders an empty EDITABLE field, never an error branch — DoD-7;
 *   - an empty prompt save is legal and clears it, and there is NO DELETE verb on the
 *     wire (`context.md` -> the wire contract), so no delete control may be offered
 *     anywhere on the surface — DoD-9;
 *   - the prompt has NO lifecycle gate — it is writable on a chapter in every state —
 *     and the copy says it is the caller's own and not shared with co-authors (D1) —
 *     DoD-10. Per D7 the copy is NOT asserted to promise any effect on the assistant:
 *     the prompt is stored and served and composed into nothing until `015`;
 *   - the two trios are independent: either one may fail without taking the other's
 *     surface with it — DoD-11;
 *   - the page registers itself as the content-pane subject on mount and unregisters on
 *     unmount, and a change of `:id` produces a FRESH page state (the `key={id}` on
 *     `ChapterItemRoute`), never the previous chapter's drafts — DoD-14.
 *
 * The chapter's BODY TEXT is `015.chapter-writing-free-mode`'s and `ChapterResponse`
 * does not carry it, so nothing here asserts on it.
 *
 * `api/chapters` is mocked module-factory form (never `fetch`). A factory replaces the
 * WHOLE module, so all TEN frozen exports are enumerated — 014's eight (including the
 * four this page never calls) plus the body read/save pair `015`/004 added; omitting one
 * strips it to `undefined` and the page would fail for the wrong reason
 * (`008.context.md` -> Testing). `ApiError` is the REAL class from
 * `api/client`: DoD-4 and DoD-8 both need one. `api/books` and `api/chats` are mocked
 * because DoD-1 mounts the whole `WorkRoutes` table, whose shell loads the book and owns
 * the chat pane.
 *
 * Queries are by ROLE or LABEL only — no test ids, nothing asserted about colour. Both
 * editors are located by their accessible labelling (sketch / prompt), and DoD-3's
 * "stated reason" is asserted as readable TEXT.
 *
 * `globals: false`: every primitive is imported explicitly.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { Link, Route, Routes } from "react-router-dom";
import type { ChangeEvent } from "react";
import type {
  ChapterAuthorPromptResponse,
  ChapterLifecycleState,
  ChapterResponse,
  ChapterTextResponse,
} from "../../src/types/chapters";
import type { BookDetailResponse } from "../../src/types/books";
import { ApiError } from "../../src/api/client";
import * as chaptersApi from "../../src/api/chapters";
import * as booksApi from "../../src/api/books";
import * as chatsApi from "../../src/api/chats";
import { ChapterPage } from "../../src/work/pages/ChapterPage";
import { WorkRoutes } from "../../src/work/routes";
import type { ContentSubjectSource } from "../../src/work/contentSubject";
import {
  currentContentSubject,
  registerContentSubject,
  unregisterContentSubject,
} from "../../src/work/contentSubject";
import { renderWithProviders } from "../support/render";

// A module-factory mock replaces the WHOLE module. All TEN frozen exports of
// `api/chapters` are enumerated, not just the ones this page's 014 surface calls: a
// factory that omitted one would leave it `undefined` for every module importing this
// namespace. The last two are the body read/save pair (`015`/004's freeze); the page's
// body region (`015`/006) issues the read on mount, so it must resolve here rather than
// blow up in the mount effect. Nothing in THIS file asserts on either of them — they are
// harness only, armed benignly in `beforeEach` below.
vi.mock("../../src/api/chapters", () => ({
  listChapters: vi.fn(),
  getChapter: vi.fn(),
  createChapter: vi.fn(),
  updateChapterSketch: vi.fn(),
  removeChapter: vi.fn(),
  reorderChapters: vi.fn(),
  getOwnChapterSystemPrompt: vi.fn(),
  updateOwnChapterSystemPrompt: vi.fn(),
  getChapterText: vi.fn(),
  updateChapterText: vi.fn(),
}));

/**
 * The body editor (`015`/005) is stubbed over its frozen four-prop seam, exactly as the
 * body region's own spec stubs it: a control whose accessible name is `ariaLabel`, whose
 * value is `initialMarkdown`, and whose edits call `onChange` with a plain string.
 * ProseMirror is never driven under jsdom — the feature's recorded testing decision.
 * Nothing in this file queries it; the stub exists so that a body load which RESOLVES
 * cannot pull the real editor into this file's mounts.
 */
vi.mock("../../src/work/components/chapter/ChapterBodyEditor", async () => {
  const { createElement } = await import("react");

  interface StubProps {
    initialMarkdown: string;
    onChange: (markdown: string) => void;
    onSelectionChange: (selectedText: string) => void;
    ariaLabel: string;
  }

  function ChapterBodyEditor(props: StubProps) {
    return createElement("textarea", {
      "aria-label": props.ariaLabel,
      value: props.initialMarkdown,
      onChange: (event: ChangeEvent<HTMLTextAreaElement>) => props.onChange(event.target.value),
    });
  }

  return { ChapterBodyEditor };
});

// DoD-1 mounts the whole `WorkRoutes` table: its `/:bookId` shell loads the book, and
// `WorkRoutes` also imports the Book-state page, which reads the two option arrays and
// both book-level prompt calls. Enumerate every export so no route hits an `undefined`.
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
const CHAPTER_ID = "ch-1";
const OTHER_CHAPTER_ID = "ch-2";
const CHAPTER_ROUTE = `/${BOOK_ID}/chapter/${CHAPTER_ID}`;
const OTHER_CHAPTER_ROUTE = `/${BOOK_ID}/chapter/${OTHER_CHAPTER_ID}`;

/** The distinctive ordinal DoD-1 looks for; no other fixture number collides with it. */
const ORDINAL = 7;
const CHAPTER_TITLE = "The Long Road";
const STORED_SKETCH = "A road, a river, and a rumour of war.";
const STORED_PROMPT = "Write in close third person, past tense.";

/** A fully-typed ChapterResponse fixture; callers override the fields they assert on. */
function makeChapter(overrides: Partial<ChapterResponse> = {}): ChapterResponse {
  return {
    id: CHAPTER_ID,
    book_id: BOOK_ID,
    ordinal: ORDINAL,
    title: CHAPTER_TITLE,
    state: "planned",
    sketch: STORED_SKETCH,
    version: 0,
    created_at: "2026-01-02T08:00:00Z",
    modified_at: "2026-03-04T09:00:00Z",
    ...overrides,
  };
}

/** A fully-typed `ChapterAuthorPromptResponse` fixture (step 005's DTO, unchanged). */
function makePrompt(overrides: Partial<ChapterAuthorPromptResponse> = {}): ChapterAuthorPromptResponse {
  return {
    chapter_id: CHAPTER_ID,
    system_prompt: STORED_PROMPT,
    modified_at: "2026-07-01T12:00:00Z",
    ...overrides,
  };
}

/**
 * The body read's benign answer — harness only, asserted on nowhere in this file. It is
 * deliberately an EMPTY body in a NON-`open` state: `015`/006's frozen surface mounts the
 * editor and the `Save body` control only for an `open` body, so this default adds no
 * control, no editable region and no text to any mount here, and every assertion in this
 * file goes on meaning exactly what it meant before the body region existed.
 */
function makeBody(): ChapterTextResponse {
  return {
    chapter_id: CHAPTER_ID,
    state: "planned",
    text: "",
    version: 0,
    modified_at: null,
  };
}

function makeDetail(): BookDetailResponse {
  return {
    id: BOOK_ID,
    owner_id: "u-owner-77",
    title: "The Winds of Winter",
    description: "A sprawling saga.",
    collaboration_mode: "free",
    visibility: "private",
    state: "active",
    created_at: "2018-05-01T10:00:00Z",
    modified_at: "2026-11-30T15:00:00Z",
    members: [],
  };
}

/** The lifecycle word each state must be readable as, in the spec's own vocabulary. */
const STATE_WORD: Record<ChapterLifecycleState, RegExp> = {
  planned: /planned/i,
  open: /open/i,
  closing: /closing/i,
  closed: /closed/i,
};

/** The three states in which the sketch is frozen (`domain-chapter.md`, US-034.AC-2). */
const NON_PLANNED_STATES: ChapterLifecycleState[] = ["open", "closing", "closed"];

/* ------------------------------------------------------------------ server double */

/** What the server currently holds, keyed by chapter id. */
let serverChapters: Record<string, ChapterResponse> = {};
let serverPrompts: Record<string, string> = {};

function setServerChapter(chapter: ChapterResponse): void {
  serverChapters[chapter.id] = chapter;
}

/* ------------------------------------------------------------------------ harness */

/**
 * Mounts the page under a route carrying BOTH real path params, so `useParams()`
 * resolves `bookId` and `id`. A `<Link>` beside the outlet lets DoD-14 change `:id`
 * through the router, exactly as the navigator does.
 */
function renderPage(route: string = CHAPTER_ROUTE): { unmount: () => void } {
  const result = renderWithProviders(
    <>
      <Routes>
        <Route path="/:bookId/chapter/:id" element={<ChapterPage />} />
      </Routes>
      <Link to={OTHER_CHAPTER_ROUTE}>go to the next chapter</Link>
    </>,
    { route },
  );
  return { unmount: result.unmount };
}

/**
 * Mounts the REAL work route table at a chapter route, beside a `<Link>` to the sibling
 * chapter. This is the arrangement DoD-14's second half needs: the mechanism the DoD
 * names is `routes.tsx`'s `ChapterItemRoute` wrapper and its `key={id}`
 * (`008.context.md` -> "The route swap, precisely"), which only the real route table
 * carries — a page mounted directly as a route element has no keying to exercise.
 */
function renderRouteTable(route: string = CHAPTER_ROUTE): void {
  renderWithProviders(
    <>
      <WorkRoutes />
      <Link to={OTHER_CHAPTER_ROUTE}>go to the next chapter</Link>
    </>,
    { route },
  );
}

function pageText(): string {
  return document.body.textContent ?? "";
}

/** Everything that could name a field for its author. */
function labelTextFor(field: HTMLTextAreaElement): string {
  const parts: string[] = [
    field.getAttribute("aria-label") ?? "",
    field.getAttribute("placeholder") ?? "",
    field.getAttribute("name") ?? "",
  ];
  const labels = field.labels;
  if (labels !== null) {
    for (const label of Array.from(labels)) parts.push(label.textContent ?? "");
  }
  return parts.join(" ");
}

/** The multi-line editor whose own labelling names the given region. */
function queryEditor(word: RegExp): HTMLTextAreaElement | null {
  const areas = Array.from(document.querySelectorAll("textarea"));
  return areas.find((area) => word.test(labelTextFor(area))) ?? null;
}

function querySketchEditor(): HTMLTextAreaElement | null {
  return queryEditor(/sketch/i);
}

function queryPromptEditor(): HTMLTextAreaElement | null {
  return queryEditor(/prompt/i);
}

function sketchEditor(): HTMLTextAreaElement {
  const editor = querySketchEditor();
  if (editor === null) throw new Error("no sketch editor is rendered");
  return editor;
}

function promptEditor(): HTMLTextAreaElement {
  const editor = queryPromptEditor();
  if (editor === null) throw new Error("no system-prompt editor is rendered");
  return editor;
}

/**
 * One editor's own section: the largest ancestor of the editor that does not also
 * contain the OTHER editor. Structure-agnostic — it works for a fieldset, a card or a
 * plain `div`, and never assumes a DOM shape the spec does not promise.
 */
function sectionFor(editor: HTMLElement, other: HTMLElement | null): HTMLElement {
  let best: HTMLElement = editor;
  let node: HTMLElement | null = editor.parentElement;
  while (node !== null && node !== document.body) {
    if (other !== null && node.contains(other)) break;
    best = node;
    node = node.parentElement;
  }
  return best;
}

function sketchSection(): HTMLElement {
  return sectionFor(sketchEditor(), queryPromptEditor());
}

function promptSection(): HTMLElement {
  return sectionFor(promptEditor(), querySketchEditor());
}

function accessibleText(button: HTMLButtonElement): string {
  return `${button.textContent ?? ""} ${button.getAttribute("aria-label") ?? ""}`;
}

function buttonsIn(root: ParentNode): HTMLButtonElement[] {
  return Array.from(root.querySelectorAll("button"));
}

/**
 * The save control belonging to one editor: a page-wide button whose accessible name
 * names both "save" and the region, or failing that a `save` button inside the editor's
 * own section. `null` when the surface offers no save for that region.
 */
function findSave(word: RegExp, editor: HTMLTextAreaElement | null, other: HTMLTextAreaElement | null): HTMLButtonElement | null {
  const named = buttonsIn(document.body).filter(
    (button) => /save/i.test(accessibleText(button)) && word.test(accessibleText(button)),
  );
  if (named.length > 0) return named[0];
  if (editor === null) return null;
  const scoped = buttonsIn(sectionFor(editor, other)).filter((button) =>
    /save/i.test(accessibleText(button)),
  );
  return scoped[0] ?? null;
}

function findSketchSave(): HTMLButtonElement | null {
  return findSave(/sketch/i, querySketchEditor(), queryPromptEditor());
}

function findPromptSave(): HTMLButtonElement | null {
  return findSave(/prompt/i, queryPromptEditor(), querySketchEditor());
}

function sketchSaveControl(): HTMLButtonElement {
  const button = findSketchSave();
  if (button === null) throw new Error("no save control is offered for the sketch editor");
  return button;
}

function promptSaveControl(): HTMLButtonElement {
  const button = findPromptSave();
  if (button === null) throw new Error("no save control is offered for the prompt editor");
  return button;
}

/**
 * True when the author cannot save right now. The DoD says only that saving is
 * *unavailable*, so an absent control counts exactly as a disabled one does.
 */
function sketchSaveUnavailable(): boolean {
  const button = findSketchSave();
  return button === null || button.disabled;
}

function promptSaveUnavailable(): boolean {
  const button = findPromptSave();
  return button === null || button.disabled;
}

function typeInto(field: HTMLTextAreaElement, value: string): void {
  fireEvent.change(field, { target: { value } });
}

/** Waits for the chapter load to settle with the given text in the sketch editor. */
async function waitForSketch(value: string): Promise<HTMLTextAreaElement> {
  await waitFor(() => {
    expect(querySketchEditor()).not.toBeNull();
    expect(sketchEditor().value).toBe(value);
  });
  return sketchEditor();
}

/** Waits for the prompt load to settle with the given text in the prompt editor. */
async function waitForPrompt(value: string): Promise<HTMLTextAreaElement> {
  await waitFor(() => {
    expect(queryPromptEditor()).not.toBeNull();
    expect(promptEditor().value).toBe(value);
  });
  return promptEditor();
}

/**
 * Clear the module-level content-subject registration through the frozen API alone: the
 * newest registration wins outright, so a sentinel is always clearable by its identity.
 * Harness hygiene only — never an assertion (DoD-14 asserts the registry itself).
 */
const RESET_SOURCE: ContentSubjectSource = () => ({ kind: "chats" });
function resetSubjectRegistry(): void {
  try {
    registerContentSubject(RESET_SOURCE);
    unregisterContentSubject(RESET_SOURCE);
  } catch {
    /* the registry is unavailable; DoD-14 will say so itself */
  }
}

beforeEach(() => {
  resetSubjectRegistry();
  serverChapters = {};
  serverPrompts = {};
  setServerChapter(makeChapter());
  serverPrompts[CHAPTER_ID] = STORED_PROMPT;

  // `restoreMocks` wipes implementations between tests — re-arm the whole server double.
  vi.mocked(chaptersApi.getChapter).mockImplementation(async (_bookId, chapterId) => {
    const chapter = serverChapters[chapterId];
    if (chapter === undefined) throw new ApiError(404, "Chapter not found");
    return chapter;
  });

  // The default save stores the draft verbatim and answers with the stored row; the
  // cases that need the server's answer to DIFFER from the draft override it in-test.
  vi.mocked(chaptersApi.updateChapterSketch).mockImplementation(
    async (_bookId, chapterId, body) => {
      const chapter = serverChapters[chapterId];
      if (chapter === undefined) throw new ApiError(404, "Chapter not found");
      const updated: ChapterResponse = {
        ...chapter,
        sketch: body.sketch,
        modified_at: "2026-07-29T11:00:00Z",
      };
      serverChapters[chapterId] = updated;
      return updated;
    },
  );

  // A missing row is a 200 with an empty prompt, never a 404 (`context.md`).
  vi.mocked(chaptersApi.getOwnChapterSystemPrompt).mockImplementation(
    async (_bookId, chapterId) => {
      const stored = serverPrompts[chapterId];
      return {
        chapter_id: chapterId,
        system_prompt: stored ?? "",
        modified_at: stored === undefined ? null : "2026-07-01T12:00:00Z",
      };
    },
  );

  vi.mocked(chaptersApi.updateOwnChapterSystemPrompt).mockImplementation(
    async (_bookId, chapterId, body) => {
      serverPrompts[chapterId] = body.system_prompt;
      return {
        chapter_id: chapterId,
        system_prompt: body.system_prompt,
        modified_at: "2026-07-29T11:30:00Z",
      };
    },
  );

  // The body region loads on mount (`015`/006). Pure harness mocking: the read resolves
  // with an empty, non-`open` body so nothing rejects unhandled and no body control joins
  // the surface; the write is armed only so it can never reject if it is ever reached.
  vi.mocked(chaptersApi.getChapterText).mockResolvedValue(makeBody());
  vi.mocked(chaptersApi.updateChapterText).mockResolvedValue(makeBody());

  // Pure harness mocking for DoD-1's whole-route mount.
  vi.mocked(chaptersApi.listChapters).mockResolvedValue({ chapters: [], can_reorder: false });
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

/* ------------------------------------------------------------------------- DoD-1 */

describe("ChapterPage — the chapter header", () => {
  it("DoD-1: the page shows the chapter's title, ordinal and readable state", async () => {
    setServerChapter(makeChapter({ state: "closing" }));

    renderPage();

    // The load addresses the book AND the chapter in the URL.
    await waitFor(() => expect(vi.mocked(chaptersApi.getChapter)).toHaveBeenCalled());
    const [bookIdArg, chapterIdArg] = vi.mocked(chaptersApi.getChapter).mock.calls[0];
    expect(bookIdArg).toBe(BOOK_ID);
    expect(chapterIdArg).toBe(CHAPTER_ID);

    expect(await screen.findByText(CHAPTER_TITLE)).toBeInTheDocument();
    await waitFor(() => {
      const text = pageText();
      // The ordinal, as a standalone number (no other fixture value is 7).
      expect(text).toMatch(new RegExp(`\\b${ORDINAL}\\b`));
      // The lifecycle state as READABLE TEXT — a colour is not a state.
      expect(text).toMatch(STATE_WORD.closing);
    });
  });

  it("DoD-1: the /work/:bookId/chapter/:id route renders this page, not the 014.chapter-skeleton placeholder", async () => {
    // The whole WORK route table, at the basename-stripped chapter route.
    renderWithProviders(<WorkRoutes />, { route: CHAPTER_ROUTE });

    // Scope to the content pane (`main`): the chat pane renders beside it.
    const main = await screen.findByRole("main");

    // This page is what resolved there: the chapter loaded for the routed ids, its
    // title is on screen, and the two editors this step introduces are present.
    await waitFor(() => expect(vi.mocked(chaptersApi.getChapter)).toHaveBeenCalled());
    expect(vi.mocked(chaptersApi.getChapter).mock.calls[0][1]).toBe(CHAPTER_ID);
    expect(await within(main).findByText(CHAPTER_TITLE)).toBeInTheDocument();
    await waitFor(() => {
      expect(querySketchEditor()).not.toBeNull();
      expect(queryPromptEditor()).not.toBeNull();
    });

    // The placeholder is gone from the content pane.
    expect(within(main).queryByText(/014\.chapter-skeleton/)).toBeNull();
  });
});

/* ---------------------------------------------------------- DoD-2 · DoD-3 (sketch) */

describe("ChapterPage — the sketch editor", () => {
  it("DoD-2: on a `planned` chapter the sketch editor is enabled and seeded with the stored sketch", async () => {
    renderPage();

    const editor = await waitForSketch(STORED_SKETCH);
    expect(editor).toBeEnabled();
    expect(editor.readOnly).toBe(false);

    // It genuinely accepts text.
    typeInto(editor, `${STORED_SKETCH} And a wedding.`);
    await waitFor(() => expect(sketchEditor().value).toBe(`${STORED_SKETCH} And a wedding.`));
  });

  it("DoD-2: saving sends the draft, and the editor then shows what the SERVER returned rather than the local draft", async () => {
    renderPage();
    const editor = await waitForSketch(STORED_SKETCH);

    typeInto(editor, "What the author typed.");
    await waitFor(() => expect(sketchSaveUnavailable()).toBe(false));

    // The stored value deliberately differs from the draft, so "shows the server's
    // answer" is distinguishable from "kept the draft".
    vi.mocked(chaptersApi.updateChapterSketch).mockResolvedValue(
      makeChapter({ sketch: "What the server stored." }),
    );

    fireEvent.click(sketchSaveControl());

    await waitFor(() => expect(vi.mocked(chaptersApi.updateChapterSketch)).toHaveBeenCalled());
    const [bookIdArg, chapterIdArg, bodyArg] =
      vi.mocked(chaptersApi.updateChapterSketch).mock.calls[0];
    expect(bookIdArg).toBe(BOOK_ID);
    expect(chapterIdArg).toBe(CHAPTER_ID);
    // No version token rides along: sketch edits are last-write-wins (D6).
    expect(bodyArg).toEqual({ sketch: "What the author typed." });

    await waitFor(() => expect(sketchEditor().value).toBe("What the server stored."));
  });

  it("DoD-3: on `open`, `closing` and `closed` the sketch editor is disabled with a stated reason and offers no save", async () => {
    const reasons: string[] = [];

    for (const state of NON_PLANNED_STATES) {
      setServerChapter(makeChapter({ state }));

      const page = renderPage();

      const editor = await waitForSketch(STORED_SKETCH);

      // Not editable...
      expect(editor.disabled || editor.readOnly).toBe(true);

      // ...with a STATED REASON in readable text, not a visual state. Asserted
      // STRUCTURALLY — present and non-empty. The spec constrains no vocabulary: DoD-3
      // asks only that a reason be stated, and the frozen wording contract sources the
      // `closing` / `closed` sentences from `work/subject.ts`'s `resolveEditability`
      // VERBATIM (which DoD-12 independently freezes), so their words are not knowable
      // here and are not this spec's to pin.
      const reason = (sketchSection().textContent ?? "").replace(STORED_SKETCH, "").trim();
      expect(reason.length).toBeGreaterThan(15);
      reasons.push(reason);

      // ...and no save is offered at all.
      expect(findSketchSave()).toBeNull();

      page.unmount();
    }

    // Each of the three states states its OWN reason — one blanket sentence would not be
    // the author-facing copy each state carries (`008.context.md`: `closing` / `closed`
    // reuse their own `resolveEditability` strings; `open`'s is the page's own).
    expect(new Set(reasons).size).toBe(NON_PLANNED_STATES.length);
  });
});

/* ------------------------------------------------------------------ DoD-4 (refusal) */

describe("ChapterPage — a refused sketch save", () => {
  it("DoD-4: the server's message is surfaced and the draft is left intact", async () => {
    renderPage();
    const editor = await waitForSketch(STORED_SKETCH);

    typeInto(editor, "Typed but refused — do not lose me.");
    await waitFor(() => expect(sketchSaveUnavailable()).toBe(false));

    // The server is the authority: a chapter that left `planned` between load and save
    // is refused with `409` (`context.md` -> status taxonomy).
    vi.mocked(chaptersApi.updateChapterSketch).mockRejectedValue(
      new ApiError(409, "Only a planned chapter's sketch may be edited"),
    );

    fireEvent.click(sketchSaveControl());

    // The server's own words reach the author...
    await waitFor(() =>
      expect(pageText()).toContain("Only a planned chapter's sketch may be edited"),
    );
    // ...and nothing typed is lost.
    expect(sketchEditor().value).toBe("Typed but refused — do not lose me.");
  });
});

/* -------------------------------------------------------------- DoD-5 (sketch gate) */

describe("ChapterPage — the sketch save gate", () => {
  it("DoD-5: the save control is unavailable while the draft still matches the loaded value", async () => {
    renderPage();
    await waitForSketch(STORED_SKETCH);

    expect(sketchSaveUnavailable()).toBe(true);

    // Editing opens the gate...
    typeInto(sketchEditor(), `${STORED_SKETCH} And a wedding.`);
    await waitFor(() => expect(sketchSaveUnavailable()).toBe(false));

    // ...and restoring the loaded value closes it again.
    typeInto(sketchEditor(), STORED_SKETCH);
    await waitFor(() => expect(sketchSaveUnavailable()).toBe(true));
  });

  it("DoD-5: the save control is unavailable while a save is in flight", async () => {
    renderPage();
    const editor = await waitForSketch(STORED_SKETCH);

    typeInto(editor, "Edited text.");
    await waitFor(() => expect(sketchSaveUnavailable()).toBe(false));

    // A save that never settles keeps the submit in flight.
    vi.mocked(chaptersApi.updateChapterSketch).mockReturnValue(
      new Promise<ChapterResponse>(() => {}),
    );
    fireEvent.click(sketchSaveControl());

    await waitFor(() => expect(sketchSaveUnavailable()).toBe(true));
    expect(vi.mocked(chaptersApi.updateChapterSketch)).toHaveBeenCalledTimes(1);
  });

  it("DoD-5: emptying the sketch is a legal save — `\"\"` is a valid sketch", async () => {
    renderPage();
    const editor = await waitForSketch(STORED_SKETCH);

    typeInto(editor, "");
    await waitFor(() => expect(sketchSaveUnavailable()).toBe(false));

    fireEvent.click(sketchSaveControl());

    await waitFor(() => expect(vi.mocked(chaptersApi.updateChapterSketch)).toHaveBeenCalled());
    expect(vi.mocked(chaptersApi.updateChapterSketch).mock.calls[0][2]).toEqual({ sketch: "" });
    await waitFor(() => expect(sketchEditor().value).toBe(""));
  });
});

/* ------------------------------------------------- DoD-6 · DoD-7 (the own prompt) */

describe("ChapterPage — the caller's own chapter prompt", () => {
  it("DoD-6: on mount the page loads the caller's own chapter prompt and shows its text in the editor", async () => {
    renderPage();

    // Addressed to the book AND chapter in the URL. The endpoint names no user, so the
    // value is the caller's own by construction (D1).
    await waitFor(() =>
      expect(vi.mocked(chaptersApi.getOwnChapterSystemPrompt)).toHaveBeenCalled(),
    );
    const [bookIdArg, chapterIdArg] =
      vi.mocked(chaptersApi.getOwnChapterSystemPrompt).mock.calls[0];
    expect(bookIdArg).toBe(BOOK_ID);
    expect(chapterIdArg).toBe(CHAPTER_ID);

    const editor = await waitForPrompt(STORED_PROMPT);
    expect(editor).toBeEnabled();
  });

  it("DoD-7: a member with no stored prompt gets an empty, EDITABLE field — a normal state, not an error state", async () => {
    // The normal starting state of every chapter for every author: 200 with an empty
    // prompt and no row yet, never a failure.
    vi.mocked(chaptersApi.getOwnChapterSystemPrompt).mockResolvedValue(
      makePrompt({ system_prompt: "", modified_at: null }),
    );

    renderPage();

    const editor = await waitForPrompt("");
    expect(editor).toBeEnabled();
    expect(editor.readOnly).toBe(false);

    // No failure copy and no retry inside the prompt section — an empty prompt is not
    // an error...
    expect(promptSection().textContent ?? "").not.toMatch(
      /failed|could not|couldn'?t|unavailable/i,
    );
    expect(
      buttonsIn(promptSection()).filter((button) => /retry|try again/i.test(accessibleText(button))),
    ).toHaveLength(0);

    // ...and the field genuinely accepts text.
    typeInto(editor, "A first prompt.");
    await waitFor(() => expect(promptEditor().value).toBe("A first prompt."));
  });
});

/* ------------------------------------------------- DoD-8 · DoD-9 (saving the prompt) */

describe("ChapterPage — saving the caller's own chapter prompt", () => {
  it("DoD-8: saving sends the draft and the editor then shows what the SERVER returned", async () => {
    renderPage();
    const editor = await waitForPrompt(STORED_PROMPT);

    typeInto(editor, "What the author typed.");
    await waitFor(() => expect(promptSaveUnavailable()).toBe(false));

    // The stored value deliberately differs from the draft.
    vi.mocked(chaptersApi.updateOwnChapterSystemPrompt).mockResolvedValue(
      makePrompt({ system_prompt: "What the server stored." }),
    );

    fireEvent.click(promptSaveControl());

    await waitFor(() =>
      expect(vi.mocked(chaptersApi.updateOwnChapterSystemPrompt)).toHaveBeenCalled(),
    );
    const [bookIdArg, chapterIdArg, bodyArg] =
      vi.mocked(chaptersApi.updateOwnChapterSystemPrompt).mock.calls[0];
    expect(bookIdArg).toBe(BOOK_ID);
    expect(chapterIdArg).toBe(CHAPTER_ID);
    expect(bodyArg).toEqual({ system_prompt: "What the author typed." });

    await waitFor(() => expect(promptEditor().value).toBe("What the server stored."));
  });

  it("DoD-8: a refused prompt save surfaces the server's message and leaves the draft intact", async () => {
    renderPage();
    const editor = await waitForPrompt(STORED_PROMPT);

    typeInto(editor, "Typed but refused — do not lose me.");
    await waitFor(() => expect(promptSaveUnavailable()).toBe(false));

    vi.mocked(chaptersApi.updateOwnChapterSystemPrompt).mockRejectedValue(
      new ApiError(403, "You are not a member of this book"),
    );

    fireEvent.click(promptSaveControl());

    await waitFor(() => expect(pageText()).toContain("You are not a member of this book"));
    expect(promptEditor().value).toBe("Typed but refused — do not lose me.");
  });

  it("DoD-9: emptying the prompt is a legal save that clears it", async () => {
    renderPage();
    const editor = await waitForPrompt(STORED_PROMPT);

    typeInto(editor, "");
    await waitFor(() => expect(promptSaveUnavailable()).toBe(false));

    fireEvent.click(promptSaveControl());

    await waitFor(() =>
      expect(vi.mocked(chaptersApi.updateOwnChapterSystemPrompt)).toHaveBeenCalled(),
    );
    expect(vi.mocked(chaptersApi.updateOwnChapterSystemPrompt).mock.calls[0][2]).toEqual({
      system_prompt: "",
    });
    await waitFor(() => expect(promptEditor().value).toBe(""));
  });

  it("DoD-9: no delete control is offered anywhere on the surface — an empty save is the only way to clear the prompt", async () => {
    renderPage();
    const editor = await waitForPrompt(STORED_PROMPT);

    // Make both sections fully rendered before looking (a save control is offered).
    typeInto(editor, "Edited text.");
    await waitFor(() => expect(promptSaveUnavailable()).toBe(false));
    await waitForSketch(STORED_SKETCH);

    // There is no DELETE verb on the prompt path, so the surface may not offer one —
    // and nothing else on this page deletes anything either (the chapter itself is
    // removed from the LIST surface, step 006).
    const destructive = buttonsIn(document.body).filter((button) =>
      /delete|remove|discard/i.test(accessibleText(button)),
    );
    expect(destructive).toHaveLength(0);
  });
});

/* --------------------------------------------------------------- DoD-10 (own, always) */

describe("ChapterPage — the prompt has no lifecycle gate and is the caller's own", () => {
  it("DoD-10: the prompt editor is enabled on a chapter in EVERY state, including `open` and `closed`", async () => {
    const states: ChapterLifecycleState[] = ["planned", "open", "closing", "closed"];
    for (const state of states) {
      setServerChapter(makeChapter({ state }));

      const page = renderPage();

      const editor = await waitForPrompt(STORED_PROMPT);
      expect(editor).toBeEnabled();
      expect(editor.readOnly).toBe(false);

      // It genuinely accepts text in this state, and a save becomes available.
      typeInto(editor, `A prompt written while the chapter is ${state}.`);
      await waitFor(() => expect(promptSaveUnavailable()).toBe(false));

      page.unmount();
    }
  });

  it("DoD-10: the surface states that the prompt is the caller's own and is not shared with co-authors", async () => {
    renderPage();
    await waitForPrompt(STORED_PROMPT);

    const regionText = promptSection().textContent ?? "";
    expect(regionText).toMatch(/prompt/i);
    // The honest line (D1): this prompt belongs to the caller and co-authors neither
    // see nor share it.
    expect(regionText).toMatch(
      /(your own|yours alone|only you|only yours|your personal|private to you|not shared|no[- ]one else|each author|every author|per[\s-]author)/i,
    );
    // ...and it is never framed as one prompt the whole book or chapter shares.
    expect(regionText).not.toMatch(/book[\s-]wide/i);
    expect(regionText).not.toMatch(/applies to (all|every|everyone)/i);
  });
});

/* ------------------------------------------------------- DoD-11 (independent trios) */

describe("ChapterPage — the two trios fail independently", () => {
  it("DoD-11: a failed prompt load renders its own error branch without breaking the chapter view", async () => {
    vi.mocked(chaptersApi.getOwnChapterSystemPrompt).mockRejectedValue(
      new ApiError(500, "Prompt service unavailable"),
    );

    renderPage();

    await waitFor(() =>
      expect(vi.mocked(chaptersApi.getOwnChapterSystemPrompt)).toHaveBeenCalled(),
    );

    // Half one — the prompt section is in its own error branch (the spec pins no
    // wording), and no prompt editor is bound to data that was never read.
    await waitFor(() =>
      expect(pageText()).toMatch(
        /(Prompt service unavailable|failed|could not|couldn'?t|unavailable|error|retry|try again)/i,
      ),
    );
    expect(queryPromptEditor()).toBeNull();

    // Half two — the chapter loaded fine and its whole view is intact: header and a
    // working sketch editor.
    expect(await screen.findByText(CHAPTER_TITLE)).toBeInTheDocument();
    expect(pageText()).toMatch(STATE_WORD.planned);
    const editor = await waitForSketch(STORED_SKETCH);
    expect(editor).toBeEnabled();
    typeInto(editor, "Still editable.");
    await waitFor(() => expect(sketchSaveUnavailable()).toBe(false));
  });

  it("DoD-11: a failed chapter load does not hide the prompt section's own state", async () => {
    vi.mocked(chaptersApi.getChapter).mockRejectedValue(
      new ApiError(500, "Chapter service unavailable"),
    );

    renderPage();

    await waitFor(() => expect(vi.mocked(chaptersApi.getChapter)).toHaveBeenCalled());

    // Half one — the chapter trio is in its own error branch: something failure-shaped
    // is on screen and the chapter's own content is not.
    await waitFor(() =>
      expect(pageText()).toMatch(
        /(Chapter service unavailable|failed|could not|couldn'?t|unavailable|error|retry|try again)/i,
      ),
    );
    expect(screen.queryByText(CHAPTER_TITLE)).toBeNull();

    // Half two — the prompt loaded on its own and its section is fully usable.
    const editor = await waitForPrompt(STORED_PROMPT);
    expect(editor).toBeEnabled();
    typeInto(editor, "Written even though the chapter failed to load.");
    await waitFor(() => expect(promptSaveUnavailable()).toBe(false));
  });
});

/* -------------------------------------------- DoD-14 (content subject · fresh state) */

describe("ChapterPage — the content-pane subject and a change of :id", () => {
  it("DoD-14: the page registers itself as the content-pane subject on mount and unregisters on unmount", async () => {
    // Nothing is registered before the page mounts.
    expect(currentContentSubject()).toBeNull();

    const page = renderPage();

    // Registered on mount, as THIS chapter — the pane model's editability answer must
    // be about the chapter on screen.
    await waitFor(() => expect(currentContentSubject()?.kind).toBe("chapter"));
    expect(currentContentSubject()?.entityId).toBe(CHAPTER_ID);

    // Once the load settles the subject carries the chapter's lifecycle state, which is
    // what makes the `planned` editability verdict reachable.
    await waitForSketch(STORED_SKETCH);
    await waitFor(() => expect(currentContentSubject()?.chapterState).toBe("planned"));

    page.unmount();

    expect(currentContentSubject()).toBeNull();
  });

  it("DoD-14: changing :id produces a FRESH page state, not the previous chapter's drafts", async () => {
    setServerChapter(
      makeChapter({
        id: OTHER_CHAPTER_ID,
        ordinal: 8,
        title: "Salt and Smoke",
        sketch: "A harbour at dawn.",
      }),
    );
    serverPrompts[OTHER_CHAPTER_ID] = "Keep the second chapter terse.";

    // Through the REAL route table: the fresh-state claim is a claim about the route —
    // `ChapterItemRoute`'s `key={id}` is what remounts the page — so the harness must
    // not bypass the wrapper that carries it.
    renderRouteTable();

    const editor = await waitForSketch(STORED_SKETCH);
    await waitForPrompt(STORED_PROMPT);

    // Unsaved drafts in BOTH editors of the first chapter.
    typeInto(editor, "An unsaved draft for the first chapter.");
    typeInto(promptEditor(), "An unsaved prompt draft for the first chapter.");
    await waitFor(() =>
      expect(sketchEditor().value).toBe("An unsaved draft for the first chapter."),
    );

    // Navigate to the sibling chapter through the router.
    fireEvent.click(screen.getByRole("link", { name: /go to the next chapter/i }));

    // The second chapter is loaded...
    await waitFor(() =>
      expect(
        vi
          .mocked(chaptersApi.getChapter)
          .mock.calls.some((call) => call[1] === OTHER_CHAPTER_ID),
      ).toBe(true),
    );
    expect(await screen.findByText("Salt and Smoke")).toBeInTheDocument();

    // ...and both editors show the SECOND chapter's stored values — neither the first
    // chapter's drafts nor its loaded values survived the remount.
    await waitForSketch("A harbour at dawn.");
    await waitForPrompt("Keep the second chapter terse.");
  });
});
