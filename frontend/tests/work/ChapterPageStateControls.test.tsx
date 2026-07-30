/**
 * OPEN, CLOSE and REOPEN on the chapter item page —
 * 015.chapter-writing-free-mode / 008.chapter-state-controls,
 * DoD-1 · DoD-2 · DoD-3 · DoD-4 · DoD-5 · DoD-6 · DoD-7 · DoD-8 · DoD-9.
 * (DoD-10 is [manual/live] — the three build gates — and gets no test.)
 *
 * A NEW file beside step 006's `ChapterPageBody.test.tsx` and step 007's
 * `ChapterPageReconcile.test.tsx`, neither of which is touched: everything here is the ONE
 * state-transition control, its refusal surface and the `closing` reason. The body's load /
 * edit / save surface stays step 006's subject and the buffer stays step 007's; both appear
 * below only as the things a transition must move (DoD-7) or must not disturb (DoD-8).
 *
 * Bound to the frozen signatures in status.md -> `## Skeleton` (step 008, plus steps 004 /
 * 005 / 006 / 007 and 014 consumed unchanged):
 *   const ChapterPage: FunctionComponent            // observer, ZERO props; reads :bookId
 *                                                   // and :id from the router
 *   type ChapterTransition = "open" | "close" | "reopen"
 *   class ChapterPageState { … transitionStatus; transitionError;
 *                            get offeredTransition; get transitionUnavailableReason }
 *   openChapterState(state, bookId, chapterId, signal?): Promise<void>
 *   closeChapterState(state, bookId, chapterId, signal?): Promise<void>
 *   reopenChapterState(state, bookId, chapterId, signal?): Promise<void>
 *   chaptersApi.openChapterState / closeChapterState / reopenChapterState   // step 004
 *   chaptersApi.getChapter / getChapterText                                 // re-seed reads
 *   ChapterBodyEditor({ initialMarkdown, onChange, onSelectionChange, ariaLabel })
 *   restoreBufferKey(bookId, subjectKind, subjectId) / readBuffer(key)      // CONSUMED
 *
 * The frozen view surface this file queries (status.md -> step 008 -> "the frozen view
 * surface", plus 014's state `Badge` and step 006's two body controls):
 *   `Open chapter: {title}` / `Close chapter: {title}` / `Reopen chapter: {title}`
 *                                                     (the ONE transition control)
 *   `Could not change the chapter state`              (the refusal alert)
 *   `This chapter is closing. The close approval step is not built yet, so its state
 *    cannot be changed here.`                         (the `closing` reason, verbatim)
 *   `Planned` / `Open` / `Closing` / `Closed`         (014's state badge word — its text
 *                                                      AND its `aria-label`)
 *   `Chapter body` (editor) · `Save body` (save control)
 *
 * Every expected value comes from the SPEC, never from the page's code:
 *   - the offer is derived from the CHAPTER's state alone and exactly one control is ever
 *     rendered — `context.md` -> D14, `008.context.md` -> "Only one control is ever
 *     offered": `planned` -> open (US-036.AC-1 / UC-035) — DoD-1; `open` -> close
 *     (US-038.AC-1) — DoD-2; `closed` -> reopen (US-039.AC-1 / UC-037) — DoD-3;
 *   - close writes `closed` DIRECTLY and the body is then read-only with no save control —
 *     `context.md` -> D8, "The close seam", US-038.AC-1 — DoD-2;
 *   - `closing` offers NOTHING and states a reason naming the close gate as `016`'s —
 *     D8 — DoD-4;
 *   - the control is offered to every member and the server's refusal is what the author
 *     reads: a 403 (co-author, or an archived book — D10 / D14) — US-036.AC-2 /
 *     US-038.AC-2 — DoD-5; a 409 (another chapter holds the one open slot — CF1) —
 *     US-037.AC-2 / US-039.AC-2 / US-038.AC-4 — DoD-6;
 *   - a success re-seeds the chapter AND the body from the server, so the body region's
 *     editability follows with no navigation and no manual reload — `008.context.md` ->
 *     "Re-seeding after a transition" — DoD-7;
 *   - a refusal never destroys unsaved work: neither the body draft nor the restore buffer
 *     — `008.context.md` -> "DoD-8 exists because…" — DoD-8;
 *   - each control names both the action and the chapter, so it is reachable by role and
 *     label — DoD-9.
 *
 * Two whole-module mocks, per `008.context.md` -> Testing:
 *   - `api/chapters` is replaced by a factory enumerating ALL THIRTEEN frozen exports —
 *     014's eight plus step 004's five. Steps 006 / 007 enumerated ten; the three
 *     transitions make it thirteen, and an omitted export would be `undefined` for every
 *     importer and fail for the wrong reason;
 *   - `work/components/chapter/ChapterBodyEditor` (folder SINGULAR — 014's unrelated
 *     `components/chapters/` sits beside it) is replaced by the same trivial stub over its
 *     frozen four-prop seam. ProseMirror is never driven under jsdom — the feature's
 *     recorded testing decision.
 * `restoreBuffer.ts` is deliberately NOT mocked: jsdom provides `localStorage` and
 * `tests/setup.ts` clears it in a global `afterEach`, so DoD-8's buffer is the REAL one the
 * page wrote. `ApiError` is the REAL class from `api/client`, constructed with a plain
 * refusal MESSAGE — a chapter refusal arrives as a plain-string `detail`, never the codex
 * family's `detail.message` object path (steps 003 / 004 freeze notes, and the correction
 * recorded in the step-008 freeze against `008.context.md`).
 *
 * Queries are by ROLE or LABEL only — no test ids, nothing asserted about colour or DOM
 * shape. Copy the author reads is asserted as readable TEXT. Every item the skeleton's
 * red-gate profile flagged as vacuity-prone (DoD-8 worst, then DoD-4, DoD-5, DoD-6, DoD-2,
 * DoD-1) is written PRESENCE-FIRST: the control, the state and the draft are proved to
 * exist before anything is asserted absent or unchanged.
 *
 * `globals: false`: every primitive is imported explicitly.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { Route, Routes } from "react-router-dom";
import type { RenderResult } from "@testing-library/react";
import type { ChangeEvent } from "react";
import type {
  ChapterAuthorPromptResponse,
  ChapterLifecycleState,
  ChapterResponse,
  ChapterTextResponse,
} from "../../src/types/chapters";
import { ApiError } from "../../src/api/client";
import * as chaptersApi from "../../src/api/chapters";
import { readBuffer, restoreBufferKey } from "../../src/work/restoreBuffer";
import { ChapterPage } from "../../src/work/pages/ChapterPage";
import { renderWithProviders } from "../support/render";

// A module-factory mock replaces the WHOLE module: all THIRTEEN frozen exports of
// `api/chapters` are enumerated — 014's eight and step 004's five — including the ones
// this region never calls.
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
  openChapterState: vi.fn(),
  closeChapterState: vi.fn(),
  reopenChapterState: vi.fn(),
}));

/**
 * The editor stub over the frozen four-prop seam: the control's accessible name is the
 * `ariaLabel` prop, its value is the `initialMarkdown` prop, and an edit calls `onChange`
 * with a plain string.
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

/* ----------------------------------------------------------------------- fixtures */

const BOOK_ID = "bk-77";
const CHAPTER_ID = "ch-42";
const CHAPTER_ROUTE = `/${BOOK_ID}/chapter/${CHAPTER_ID}`;

const CHAPTER_TITLE = "The Long Road";
const STORED_PROMPT = "Write in close third person, past tense.";
const STORED_BODY = "The road bends east at dusk, and the horses know it.";

/** The version the BODY response carries (D13 / step 006) — never 014's chapter version. */
const BODY_VERSION = 4;
const CHAPTER_VERSION = 99;

/** Steps 006's two frozen body-control names. */
const EDITOR_LABEL = "Chapter body";
const SAVE_LABEL = "Save body";

/** Step 008's frozen refusal surface. */
const REFUSAL_TITLE = "Could not change the chapter state";

/** Step 008's frozen `closing` sentence, verbatim. */
const CLOSING_REASON =
  "This chapter is closing. The close approval step is not built yet, so its state cannot be changed here.";

/** 014's readable lifecycle words — the state badge's text AND its `aria-label`. */
const LIFECYCLE_WORDS = ["Planned", "Open", "Closing", "Closed"] as const;

/** The buffer key this page owns: `(bookId, "chapter", chapterId)`. */
const BUFFER_KEY = restoreBufferKey(BOOK_ID, "chapter", CHAPTER_ID);

function makeChapter(overrides: Partial<ChapterResponse> = {}): ChapterResponse {
  return {
    id: CHAPTER_ID,
    book_id: BOOK_ID,
    ordinal: 7,
    title: CHAPTER_TITLE,
    state: "open",
    sketch: "A road, a river, and a rumour of war.",
    version: CHAPTER_VERSION,
    created_at: "2026-01-02T08:00:00Z",
    modified_at: "2026-03-04T09:00:00Z",
    ...overrides,
  };
}

function makePrompt(overrides: Partial<ChapterAuthorPromptResponse> = {}): ChapterAuthorPromptResponse {
  return {
    chapter_id: CHAPTER_ID,
    system_prompt: STORED_PROMPT,
    modified_at: "2026-07-01T12:00:00Z",
    ...overrides,
  };
}

function makeBody(overrides: Partial<ChapterTextResponse> = {}): ChapterTextResponse {
  return {
    chapter_id: CHAPTER_ID,
    state: "open",
    text: STORED_BODY,
    version: BODY_VERSION,
    modified_at: "2026-07-20T10:00:00Z",
    ...overrides,
  };
}

/* ------------------------------------------------------------------------ harness */

/**
 * Arms all three of the page's loads to succeed with the chapter in `state` — the chapter
 * response and the BODY response carry the same state, exactly as the server would.
 */
function armLoads(state: ChapterLifecycleState, text: string = STORED_BODY): void {
  vi.mocked(chaptersApi.getChapter).mockResolvedValue(makeChapter({ state }));
  vi.mocked(chaptersApi.getOwnChapterSystemPrompt).mockResolvedValue(makePrompt());
  vi.mocked(chaptersApi.getChapterText).mockResolvedValue(makeBody({ state, text }));
}

/**
 * Re-arms the three reads with the POST-transition state, so a re-seed is observable:
 * the chapter read and the body read both answer the new state from here on.
 */
function armPostTransition(state: ChapterLifecycleState, text: string = STORED_BODY): void {
  vi.mocked(chaptersApi.getChapter).mockResolvedValue(makeChapter({ state }));
  vi.mocked(chaptersApi.getChapterText).mockResolvedValue(makeBody({ state, text }));
}

/** Mounts the page under a route carrying BOTH path params, so `useParams()` resolves. */
function renderPage(route: string = CHAPTER_ROUTE): RenderResult {
  return renderWithProviders(
    <Routes>
      <Route path="/:bookId/chapter/:id" element={<ChapterPage />} />
    </Routes>,
    { route },
  );
}

function pageText(): string {
  return document.body.textContent ?? "";
}

/* ------------------------------------------------------- the transition control's surface */

type TransitionAction = "Open" | "Close" | "Reopen";

/** The frozen accessible name: the action AND the chapter, the title verbatim after ": ". */
function transitionName(action: TransitionAction, title: string = CHAPTER_TITLE): string {
  return `${action} chapter: ${title}`;
}

/** Every transition control currently on the page — the offer is "exactly one, or none". */
function transitionControls(): HTMLElement[] {
  return screen.queryAllByRole("button", { name: /^(Open|Close|Reopen) chapter: / });
}

function queryTransitionControl(action: TransitionAction): HTMLElement | null {
  return screen.queryByRole("button", { name: transitionName(action) });
}

async function findTransitionControl(action: TransitionAction): Promise<HTMLElement> {
  return await screen.findByRole("button", { name: transitionName(action) });
}

/**
 * The lifecycle word(s) the chapter's own state badge is showing. 014's badge carries the
 * word as its `aria-label` AND as its text; a transition control's visible action word is
 * excluded, because its own accessible name is the long form.
 */
function chapterStateWords(): string[] {
  return LIFECYCLE_WORDS.filter((word) => {
    if (screen.queryAllByLabelText(word).length > 0) return true;
    return screen.queryAllByText(word).some((element) => element.closest("button") === null);
  });
}

async function expectStateShown(word: string): Promise<void> {
  await waitFor(() => {
    expect(chapterStateWords()).toContain(word);
  });
}

/* ---------------------------------------------------------------- the body's surface */

function queryEditor(): HTMLTextAreaElement | null {
  return screen.queryByRole("textbox", { name: EDITOR_LABEL }) as HTMLTextAreaElement | null;
}

async function findEditor(): Promise<HTMLTextAreaElement> {
  return (await screen.findByRole("textbox", { name: EDITOR_LABEL })) as HTMLTextAreaElement;
}

function editorValue(): string {
  const editor = queryEditor();
  if (editor === null) throw new Error("no chapter-body editor is mounted");
  return editor.value;
}

function querySaveControl(): HTMLElement | null {
  return screen.queryByRole("button", { name: SAVE_LABEL });
}

/** Types into the mocked editor, exactly as an author's keystroke would. */
function typeBody(text: string): void {
  const editor = queryEditor();
  if (editor === null) throw new Error("no chapter-body editor is mounted");
  fireEvent.change(editor, { target: { value: text } });
}

beforeEach(() => {
  vi.mocked(chaptersApi.openChapterState).mockResolvedValue(makeChapter({ state: "open" }));
  vi.mocked(chaptersApi.closeChapterState).mockResolvedValue(makeChapter({ state: "closed" }));
  vi.mocked(chaptersApi.reopenChapterState).mockResolvedValue(makeChapter({ state: "open" }));
  armLoads("open");
});

/* ------------------------------------------------------------- DoD-1 — a planned chapter */

describe("a planned chapter offers open (DoD-1)", () => {
  it("DoD-1: offers exactly one control — open — and using it opens the chapter with the body editor now mounted — US-036.AC-1, UC-035", async () => {
    armLoads("planned");

    renderPage();

    // Presence first: exactly one control is offered, and it is the open one.
    const control = await findTransitionControl("Open");
    expect(transitionControls()).toHaveLength(1);
    expect(queryTransitionControl("Close")).toBeNull();
    expect(queryTransitionControl("Reopen")).toBeNull();
    await expectStateShown("Planned");

    // The server answers with the opened chapter, and both reads now agree.
    vi.mocked(chaptersApi.openChapterState).mockResolvedValue(makeChapter({ state: "open" }));
    armPostTransition("open");

    fireEvent.click(control);

    // It called the OPEN function — and neither of the other two.
    await waitFor(() => {
      expect(vi.mocked(chaptersApi.openChapterState)).toHaveBeenCalledTimes(1);
    });
    const call = vi.mocked(chaptersApi.openChapterState).mock.calls[0];
    expect(call[0]).toBe(BOOK_ID);
    expect(call[1]).toBe(CHAPTER_ID);
    expect(vi.mocked(chaptersApi.closeChapterState)).not.toHaveBeenCalled();
    expect(vi.mocked(chaptersApi.reopenChapterState)).not.toHaveBeenCalled();

    // The chapter is now shown as open...
    await expectStateShown("Open");
    expect(chapterStateWords()).not.toContain("Planned");

    // ...and the body editor is mounted, holding the stored body — the editability
    // followed the new state with no navigation.
    const editor = await findEditor();
    expect(editor.value).toBe(STORED_BODY);
  });
});

/* ---------------------------------------------------------------- DoD-2 — an open chapter */

describe("an open chapter offers close (DoD-2)", () => {
  it("DoD-2: the only control is close, and using it shows the chapter as closed with the body read-only and no save control — US-038.AC-1", async () => {
    armLoads("open");

    renderPage();

    // Presence first: the one offered control is close, and the body is editable now.
    const control = await findTransitionControl("Close");
    expect(transitionControls()).toHaveLength(1);
    expect(queryTransitionControl("Open")).toBeNull();
    expect(queryTransitionControl("Reopen")).toBeNull();
    await findEditor();
    expect(querySaveControl()).not.toBeNull();
    await expectStateShown("Open");

    // The close writes `closed` DIRECTLY — never `closing` (D8, "The close seam").
    vi.mocked(chaptersApi.closeChapterState).mockResolvedValue(makeChapter({ state: "closed" }));
    armPostTransition("closed");

    fireEvent.click(control);

    await waitFor(() => {
      expect(vi.mocked(chaptersApi.closeChapterState)).toHaveBeenCalledTimes(1);
    });
    const call = vi.mocked(chaptersApi.closeChapterState).mock.calls[0];
    expect(call[0]).toBe(BOOK_ID);
    expect(call[1]).toBe(CHAPTER_ID);
    expect(vi.mocked(chaptersApi.openChapterState)).not.toHaveBeenCalled();
    expect(vi.mocked(chaptersApi.reopenChapterState)).not.toHaveBeenCalled();

    // The state on screen became `Closed` — not `Closing` — and the stored body is still
    // shown, now as read-only text...
    await expectStateShown("Closed");
    expect(chapterStateWords()).not.toContain("Closing");
    await waitFor(() => {
      expect(pageText()).toContain(STORED_BODY);
    });

    // ...and only THEN the two negatives: no editor and no save control remain.
    await waitFor(() => {
      expect(queryEditor()).toBeNull();
    });
    expect(querySaveControl()).toBeNull();
  });
});

/* -------------------------------------------------------------- DoD-3 — a closed chapter */

describe("a closed chapter offers reopen (DoD-3)", () => {
  it("DoD-3: the only control is reopen, and using it shows the chapter as open — US-039.AC-1, UC-037", async () => {
    armLoads("closed");

    renderPage();

    // Presence first: exactly one control, and it is the reopen one.
    const control = await findTransitionControl("Reopen");
    expect(transitionControls()).toHaveLength(1);
    expect(queryTransitionControl("Open")).toBeNull();
    expect(queryTransitionControl("Close")).toBeNull();
    await expectStateShown("Closed");

    vi.mocked(chaptersApi.reopenChapterState).mockResolvedValue(makeChapter({ state: "open" }));
    armPostTransition("open");

    fireEvent.click(control);

    await waitFor(() => {
      expect(vi.mocked(chaptersApi.reopenChapterState)).toHaveBeenCalledTimes(1);
    });
    const call = vi.mocked(chaptersApi.reopenChapterState).mock.calls[0];
    expect(call[0]).toBe(BOOK_ID);
    expect(call[1]).toBe(CHAPTER_ID);
    expect(vi.mocked(chaptersApi.openChapterState)).not.toHaveBeenCalled();
    expect(vi.mocked(chaptersApi.closeChapterState)).not.toHaveBeenCalled();

    await expectStateShown("Open");
    expect(chapterStateWords()).not.toContain("Closed");
  });
});

/* -------------------------------------------------------------- DoD-4 — a closing chapter */

describe("a closing chapter offers nothing, with a stated reason (DoD-4)", () => {
  it("DoD-4: states that the close approval step is not built yet, and offers no transition control at all", async () => {
    // Nothing in this feature writes `closing` (D8) — the state is reached by arming the
    // server to answer with one.
    armLoads("closing");

    renderPage();

    // Presence first: the REASON is on screen, verbatim, and it names the close gate as
    // not yet built rather than merely restating the state.
    await screen.findByText(CLOSING_REASON);
    expect(pageText()).toContain("not built yet");
    await expectStateShown("Closing");

    // ...and only then the absence: no transition control of any kind, and none of the
    // three rendered-and-disabled either.
    expect(transitionControls()).toHaveLength(0);
    expect(queryTransitionControl("Open")).toBeNull();
    expect(queryTransitionControl("Close")).toBeNull();
    expect(queryTransitionControl("Reopen")).toBeNull();
  });

  it("DoD-4: the contrast case — an open chapter does offer its one control and states no such reason", async () => {
    armLoads("open");

    renderPage();

    // So "no control" above is evidence about `closing`, not about the page.
    await findTransitionControl("Close");
    expect(transitionControls()).toHaveLength(1);
    expect(screen.queryByText(CLOSING_REASON)).toBeNull();
  });
});

/* ------------------------------------------------------------------ DoD-5 — a 403 refusal */

describe("a 403 from a transition (DoD-5)", () => {
  it("DoD-5: a co-author's open is refused — the server's message is surfaced and the state on screen is unchanged — US-036.AC-2", async () => {
    const refusal = "Only the book's owner can open, close or reopen a chapter.";
    armLoads("planned");
    vi.mocked(chaptersApi.openChapterState).mockRejectedValue(new ApiError(403, refusal));

    renderPage();

    // The control is offered to every member (D14) — that is the accepted cost this
    // refusal surface exists to pay.
    const control = await findTransitionControl("Open");
    await expectStateShown("Planned");

    fireEvent.click(control);

    // Presence first: the server's message is on screen, under the frozen title.
    await screen.findByText(REFUSAL_TITLE);
    await waitFor(() => {
      expect(pageText()).toContain(refusal);
    });

    // ...and only then: the chapter's state on screen is exactly what it was.
    expect(chapterStateWords()).toContain("Planned");
    expect(chapterStateWords()).not.toContain("Open");
  });

  it("DoD-5: a close on an archived book is refused the same way, and the chapter is still shown as open — US-038.AC-2, D10", async () => {
    const refusal = "This book is archived, so its chapters cannot be changed.";
    armLoads("open");
    vi.mocked(chaptersApi.closeChapterState).mockRejectedValue(new ApiError(403, refusal));

    renderPage();

    const control = await findTransitionControl("Close");
    await findEditor();
    await expectStateShown("Open");

    fireEvent.click(control);

    await screen.findByText(REFUSAL_TITLE);
    await waitFor(() => {
      expect(pageText()).toContain(refusal);
    });

    expect(chapterStateWords()).toContain("Open");
    expect(chapterStateWords()).not.toContain("Closed");
  });
});

/* ------------------------------------------------------------------ DoD-6 — a 409 refusal */

describe("a 409 from open or reopen (DoD-6)", () => {
  it("DoD-6: an open refused because another chapter holds the slot leaves this chapter's state and body region unchanged — US-037.AC-2, US-038.AC-4", async () => {
    const refusal = "Another chapter of this book is already open.";
    armLoads("planned");
    vi.mocked(chaptersApi.openChapterState).mockRejectedValue(new ApiError(409, refusal));

    renderPage();

    const control = await findTransitionControl("Open");
    await expectStateShown("Planned");
    await waitFor(() => {
      expect(pageText()).toContain(STORED_BODY);
    });

    fireEvent.click(control);

    // Presence first: the server's message is on screen.
    await screen.findByText(REFUSAL_TITLE);
    await waitFor(() => {
      expect(pageText()).toContain(refusal);
    });

    // ...and only then: the state is unchanged and the body region was not re-seeded —
    // the stored body is still shown, still not editable, and no second body read
    // happened.
    expect(chapterStateWords()).toContain("Planned");
    expect(chapterStateWords()).not.toContain("Open");
    expect(pageText()).toContain(STORED_BODY);
    expect(queryEditor()).toBeNull();
    expect(querySaveControl()).toBeNull();
    expect(vi.mocked(chaptersApi.getChapterText)).toHaveBeenCalledTimes(1);
  });

  it("DoD-6: a reopen refused the same way leaves the closed chapter and its body region unchanged — US-039.AC-2", async () => {
    const refusal = "Another chapter of this book is already open.";
    armLoads("closed");
    vi.mocked(chaptersApi.reopenChapterState).mockRejectedValue(new ApiError(409, refusal));

    renderPage();

    const control = await findTransitionControl("Reopen");
    await expectStateShown("Closed");
    await waitFor(() => {
      expect(pageText()).toContain(STORED_BODY);
    });

    fireEvent.click(control);

    await screen.findByText(REFUSAL_TITLE);
    await waitFor(() => {
      expect(pageText()).toContain(refusal);
    });

    expect(chapterStateWords()).toContain("Closed");
    expect(chapterStateWords()).not.toContain("Open");
    expect(pageText()).toContain(STORED_BODY);
    expect(queryEditor()).toBeNull();
    expect(vi.mocked(chaptersApi.getChapterText)).toHaveBeenCalledTimes(1);
  });
});

/* -------------------------------------------------------------------- DoD-7 — the re-seed */

describe("a successful transition re-seeds the chapter AND the body (DoD-7)", () => {
  it("DoD-7: the body region's editability follows the new state with no navigation and no manual reload", async () => {
    // The chapter's stored body is held CONSTANT across both reads: a transition writes
    // `state` and `modified_at` only and never touches `Chapter.text` (step 002's frozen
    // contract, `context.md` -> "the close seam"), so a body whose text moved *because of*
    // a transition is not a server behaviour this contract can produce. What DoD-7 is
    // about is the re-READ and the editability that follows it, not the text's content.
    armLoads("planned");

    renderPage();

    // Presence first: the page is on a planned chapter, whose body is read-only.
    const control = await findTransitionControl("Open");
    await expectStateShown("Planned");
    await waitFor(() => {
      expect(pageText()).toContain(STORED_BODY);
    });
    expect(queryEditor()).toBeNull();
    expect(vi.mocked(chaptersApi.getChapterText)).toHaveBeenCalledTimes(1);

    vi.mocked(chaptersApi.openChapterState).mockResolvedValue(makeChapter({ state: "open" }));
    armPostTransition("open");

    fireEvent.click(control);

    // The BODY was re-read from the server — this is the assertion a locally patched
    // `chapter.state` cannot satisfy.
    await waitFor(() => {
      expect(vi.mocked(chaptersApi.getChapterText)).toHaveBeenCalledTimes(2);
    });
    const secondRead = vi.mocked(chaptersApi.getChapterText).mock.calls[1];
    expect(secondRead[0]).toBe(BOOK_ID);
    expect(secondRead[1]).toBe(CHAPTER_ID);

    // The chapter followed...
    await expectStateShown("Open");
    // ...and so did the body region's EDITABILITY: where the read-only branch had neither,
    // the labelled editor is now mounted and the save control is present — with no page
    // navigation in between.
    const editor = await findEditor();
    expect(querySaveControl()).not.toBeNull();
    // The author's body draft is left ALONE by the success path, exactly as it is by the
    // refusal path (DoD-8): it still reads as the chapter's stored body, untouched.
    expect(editor.value).toBe(STORED_BODY);

    // The one offered control followed too: an open chapter offers close.
    await findTransitionControl("Close");
    expect(transitionControls()).toHaveLength(1);
  });
});

/* ------------------------------------------------ DoD-8 — a refusal never destroys work */

describe("a refused transition leaves the draft and the buffer alone (DoD-8)", () => {
  it("DoD-8: after a refused close the body draft is still the author's text and the restore buffer still holds it", async () => {
    const typed = "The road bends east at dusk, and the horses refuse it.";
    const refusal = "Only the book's owner can open, close or reopen a chapter.";
    armLoads("open");
    vi.mocked(chaptersApi.closeChapterState).mockRejectedValue(new ApiError(403, refusal));

    renderPage();

    // Presence first, part one: a REAL draft, established through the page.
    await findEditor();
    typeBody(typed);
    await waitFor(() => {
      expect(editorValue()).toBe(typed);
    });

    // Presence first, part two: a REAL buffer entry, written by the page (step 007's
    // rule), carrying that draft.
    await waitFor(() => {
      expect(readBuffer(BUFFER_KEY)?.draft).toBe(typed);
    });

    // Now the refusal.
    const control = await findTransitionControl("Close");
    fireEvent.click(control);

    // Presence first, part three: the refusal actually happened and is on screen.
    await screen.findByText(REFUSAL_TITLE);
    await waitFor(() => {
      expect(pageText()).toContain(refusal);
    });
    await waitFor(() => {
      expect(vi.mocked(chaptersApi.closeChapterState)).toHaveBeenCalledTimes(1);
    });

    // ...and only THEN the two things that must have survived it: the unsaved draft the
    // author is still looking at, and the buffer that protects it.
    expect(editorValue()).toBe(typed);
    expect(readBuffer(BUFFER_KEY)).not.toBeNull();
    expect(readBuffer(BUFFER_KEY)?.draft).toBe(typed);

    // The chapter is still open, so the editor is still the surface holding that draft.
    expect(chapterStateWords()).toContain("Open");
    expect(vi.mocked(chaptersApi.updateChapterText)).not.toHaveBeenCalled();
  });
});

/* --------------------------------------------------------- DoD-9 — the accessible names */

describe("each control names both the action and the chapter (DoD-9)", () => {
  const cases: Array<{ state: ChapterLifecycleState; action: TransitionAction }> = [
    { state: "planned", action: "Open" },
    { state: "open", action: "Close" },
    { state: "closed", action: "Reopen" },
  ];

  for (const { state, action } of cases) {
    it(`DoD-9: the ${state} chapter's control is reachable by role and label as "${action} chapter: <title>"`, async () => {
      armLoads(state);

      renderPage();

      const control = await findTransitionControl(action);
      // The name carries the ACTION and the CHAPTER — both, so a screen reader is not
      // left with a bare verb on a page full of other actions.
      const name = control.getAttribute("aria-label") ?? control.textContent ?? "";
      expect(name).toContain(action);
      expect(name).toContain(CHAPTER_TITLE);
      // The visible label is the action word, and the accessible name widens it rather
      // than replacing it.
      expect(control.textContent ?? "").toContain(action);
    });
  }

  it("DoD-9: the name carries the chapter it actually acts on, not a fixed string", async () => {
    const otherTitle = "A Shorter Road";
    armLoads("planned");

    const view = renderPage();
    await findTransitionControl("Open");
    view.unmount();

    vi.mocked(chaptersApi.getChapter).mockResolvedValue(
      makeChapter({ state: "planned", title: otherTitle }),
    );
    vi.mocked(chaptersApi.getChapterText).mockResolvedValue(makeBody({ state: "planned" }));

    renderPage();

    // The second chapter's control is named for the second chapter, and the first name no
    // longer reaches anything.
    await screen.findByRole("button", { name: transitionName("Open", otherTitle) });
    expect(queryTransitionControl("Open")).toBeNull();
  });
});
