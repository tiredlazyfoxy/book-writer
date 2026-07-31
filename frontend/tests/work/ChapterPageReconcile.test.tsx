/**
 * The chapter body's RESTORE BUFFER and BOTH reconciliation entrances —
 * 015.chapter-writing-free-mode / 007.chapter-buffer-reconciliation,
 * DoD-1 · DoD-2 · DoD-3 · DoD-4 · DoD-5 · DoD-6 · DoD-7 · DoD-8 · DoD-9 · DoD-10 · DoD-11.
 * (DoD-12 is [manual/live] — the three build gates — and gets no test.)
 *
 * A NEW file beside step 006's `ChapterPageBody.test.tsx`, which is not touched: everything
 * here is the buffer, the two entrances into the divergence view, the resolution and the
 * eviction notice. The load / edit / save surface itself stays step 006's subject.
 *
 * Bound to the frozen signatures in status.md -> `## Skeleton` (step 007, plus steps 004 /
 * 005 / 006 consumed unchanged):
 *   const ChapterPage: FunctionComponent            // observer, ZERO props; reads :bookId
 *                                                   // and :id from the router
 *   type ChapterReconciliationSide = "server" | "draft"
 *   class ChapterPageState { … bodyConflict; isReconcilingBody; evictedBufferKeys }
 *   loadChapterBody(state, bookId, chapterId, signal?): Promise<void>   // load entrance
 *   editBodyDraft(state, bookId, chapterId, text): void                 // buffer write
 *   saveChapterBody(state, bookId, chapterId, signal?): Promise<void>   // 409 entrance
 *   resolveBodyConflict(state, side, bookId, chapterId, signal?): Promise<void>
 *   getChapterText / updateChapterText                                  // step 004
 *   ChapterBodyEditor({ initialMarkdown, onChange, onSelectionChange, ariaLabel })
 *   restoreBufferKey(bookId, subjectKind, subjectId) / readBuffer(key) /
 *   writeBuffer(key, draft, baseVersion) -> WriteResult   // CONSUMED, never modified
 *
 * The frozen view surface this file queries (status.md -> step 007 -> "the frozen view
 * surface"), plus step 006's editor / save names:
 *   `Unsaved changes diverged`                        (divergence heading)
 *   `This chapter's body changed since your draft`    (divergence explainer alert)
 *   `Current server version` / `Your draft`           (the two pane headings)
 *   `Keep the server version` / `Keep my draft`       (the two side controls)
 *   `Other unsaved drafts were removed`               (eviction notice alert)
 *   `Chapter body` (editor) · `Save body` (save control)
 *
 * Every expected value comes from the SPEC, never from the page's code:
 *   - the buffer key is `(bookId, "chapter", chapterId)` and its base version is the
 *     numeric `Chapter.version` the BODY response carried — `007.context.md`,
 *     `context.md` -> "Frontend facts", UC-092 / US-107.AC-1 — DoD-1;
 *   - a buffer whose base version MATCHES the served version restores the buffered draft
 *     rather than the server's body — US-107.AC-1 / US-107.AC-2 — DoD-2;
 *   - the buffer is device-local: nothing reaches the server because of it —
 *     US-107.AC-4 / US-103.AC-3 — DoD-3;
 *   - a successful save clears it, so the next visit shows the server's body — DoD-4;
 *   - a MISMATCHED base version opens the divergence view at LOAD time with NO save
 *     attempted; `frontend-work-drafts.md` -> "Two entrances, not one" makes this the
 *     load-bearing entrance — DoD-5;
 *   - a 409 re-fetches the server's body and opens the SAME view — no auto-merge, no
 *     silent overwrite — UC-039 / US-041.AC-1 — DoD-6;
 *   - the resolution takes ONE SIDE WHOLE (`domain-chapter.md`: "no automatic merge at
 *     MVP"): the server's side discards the draft and clears the buffer, writing nothing
 *     of the abandoning author's text — US-041.AC-3 — DoD-7; the draft's side adopts the
 *     server's VERSION FIRST and re-saves against it — US-041.AC-2 — DoD-8;
 *   - a draft holding both members' text, reconciled by keeping the draft, lands as the
 *     chapter's body — US-040.AC-4 through `context.md` -> "Known product gaps" — DoD-9;
 *   - an eviction is data loss on some OTHER item and is never silent; the current
 *     chapter's own buffer is never the victim — DoD-10;
 *   - the divergence view is a normal landing, not an error state: inline, not a modal,
 *     exactly two choices, neither pre-selected — `frontend-work-drafts.md` — DoD-11.
 *
 * Two whole-module mocks, per `007.context.md` -> Testing (the same pair step 006 used):
 *   - `api/chapters` is replaced by a factory enumerating ALL TEN frozen exports — an
 *     omitted export would be `undefined` for every importer and fail for the wrong reason;
 *   - `work/components/chapter/ChapterBodyEditor` (folder SINGULAR) is replaced by a
 *     trivial stub over its frozen four-prop seam. ProseMirror is never driven under jsdom
 *     — the feature's recorded testing decision.
 * `restoreBuffer.ts` is deliberately NOT mocked: jsdom provides `localStorage`, the
 * module's own unit behaviour is covered by `restoreBuffer.test.ts`, and DoD-10 exercises
 * the REAL eviction policy by filling the store with oversized sibling buffers.
 * `ApiError` is the REAL class from `api/client` — DoD-6 needs a genuine 409, constructed
 * with a plain refusal MESSAGE (a chapter refusal arrives as a plain-string `detail`, not
 * the codex family's `detail.message` object path).
 *
 * Queries are by ROLE or LABEL only — no test ids, nothing asserted about colour or DOM
 * shape. Copy the author reads is asserted as readable TEXT. Every item the skeleton's
 * red-gate profile flagged as vacuity-prone (DoD-3, DoD-4, DoD-5's "no save attempted",
 * DoD-6's "no silent overwrite", DoD-7's "nothing written", DoD-10's "never the victim",
 * DoD-11's "not a modal" / "neither pre-selected") is written PRESENCE-FIRST.
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
import * as flagsApi from "../../src/api/flags";
import * as continuityApi from "../../src/api/continuity";
import { readBuffer, restoreBufferKey, writeBuffer } from "../../src/work/restoreBuffer";
import { ChapterPage } from "../../src/work/pages/ChapterPage";
import { renderWithProviders } from "../support/render";

// A module-factory mock replaces the WHOLE module: all TEN frozen exports of
// `api/chapters` are enumerated, including the six this region never calls.
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

// HARNESS ONLY, added by `016.chapter-close-continuity`: the chapter page's mount now
// also reads the chapter's warnings and its note changeset (`plan.md` -> Interface for
// `chapterPageState.ts`; DoD-12). Enumerated in factory form and armed benignly in
// `beforeEach` so the mount cannot reach the network. NOTHING in this file asserts on
// either, and no assertion here changed.
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
 * The editor stub over the frozen four-prop seam: the control's accessible name is the
 * `ariaLabel` prop, its value is the `initialMarkdown` prop, and an edit calls `onChange`
 * with a plain string. Each MOUNT appends the `initialMarkdown` it was given to a log on
 * `globalThis` (the factory is hoisted above every import, so it may not close over a
 * module-level binding).
 */
vi.mock("../../src/work/components/chapter/ChapterBodyEditor", async () => {
  const { createElement, useRef } = await import("react");

  interface StubProps {
    initialMarkdown: string;
    onChange: (markdown: string) => void;
    onSelectionChange: (selectedText: string) => void;
    ariaLabel: string;
  }

  function ChapterBodyEditor(props: StubProps) {
    const recorded = useRef(false);
    if (!recorded.current) {
      recorded.current = true;
      const holder = globalThis as unknown as { __chapterReconcileMounts?: string[] };
      holder.__chapterReconcileMounts = holder.__chapterReconcileMounts ?? [];
      holder.__chapterReconcileMounts.push(props.initialMarkdown);
    }
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

/** The version the BODY response carries — the one and only base version (D13 / step 006). */
const BODY_VERSION = 4;
/** 014's CHAPTER response carries a deliberately different number; it is never the base. */
const CHAPTER_VERSION = 99;
/** The version the server has moved on to by the time a stale save is refused. */
const SERVER_VERSION = 9;

/** The frozen accessible names of step 006's two body controls. */
const EDITOR_LABEL = "Chapter body";
const SAVE_LABEL = "Save body";

/** The frozen accessible surface of step 007's divergence view and eviction notice. */
const DIVERGENCE_HEADING = "Unsaved changes diverged";
const DIVERGENCE_EXPLAINER = "This chapter's body changed since your draft";
const SERVER_PANE_HEADING = "Current server version";
const DRAFT_PANE_HEADING = "Your draft";
const KEEP_SERVER_LABEL = "Keep the server version";
const KEEP_DRAFT_LABEL = "Keep my draft";
const EVICTION_TITLE = "Other unsaved drafts were removed";

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
    summary: null,
    summary_status: null,
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

interface ArmOptions {
  state?: ChapterLifecycleState;
  text?: string;
  version?: number;
}

/** Arms all three of the page's loads to succeed. */
function armLoads(options: ArmOptions = {}): void {
  const state = options.state ?? "open";
  vi.mocked(chaptersApi.getChapter).mockResolvedValue(makeChapter({ state }));
  vi.mocked(chaptersApi.getOwnChapterSystemPrompt).mockResolvedValue(makePrompt());
  vi.mocked(chaptersApi.getChapterText).mockResolvedValue(
    makeBody({
      state,
      text: options.text ?? STORED_BODY,
      version: options.version ?? BODY_VERSION,
    }),
  );
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

/** Everything that could name a field for its author (014's spec's idiom). */
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

/** True when some multi-line field on the page names the given region. */
function hasFieldLabelled(word: RegExp): boolean {
  return Array.from(document.querySelectorAll("textarea")).some((area) =>
    word.test(labelTextFor(area)),
  );
}

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

function saveControl(): HTMLElement {
  const control = querySaveControl();
  if (control === null) throw new Error("no save control is rendered for the chapter body");
  return control;
}

/** Types into the mocked editor, exactly as an author's keystroke would. */
function typeBody(text: string): void {
  const editor = queryEditor();
  if (editor === null) throw new Error("no chapter-body editor is mounted");
  fireEvent.change(editor, { target: { value: text } });
}

/** The `initialMarkdown` the stub saw at each mount — one entry per mount. */
function editorMounts(): string[] {
  const holder = globalThis as unknown as { __chapterReconcileMounts?: string[] };
  holder.__chapterReconcileMounts = holder.__chapterReconcileMounts ?? [];
  return holder.__chapterReconcileMounts;
}

/* --------------------------------------------------------- the divergence view's surface */

function queryDivergenceHeading(): HTMLElement | null {
  return screen.queryByRole("heading", { name: DIVERGENCE_HEADING });
}

async function findDivergenceView(): Promise<void> {
  await screen.findByRole("heading", { name: DIVERGENCE_HEADING });
  await screen.findByText(DIVERGENCE_EXPLAINER);
  expect(screen.getByText(SERVER_PANE_HEADING)).toBeInTheDocument();
  expect(screen.getByText(DRAFT_PANE_HEADING)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: KEEP_SERVER_LABEL })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: KEEP_DRAFT_LABEL })).toBeInTheDocument();
}

function keepServerControl(): HTMLElement {
  return screen.getByRole("button", { name: KEEP_SERVER_LABEL });
}

function keepDraftControl(): HTMLElement {
  return screen.getByRole("button", { name: KEEP_DRAFT_LABEL });
}

/**
 * Fills the restore-buffer store with oversized SIBLING buffers (other chapters of the
 * same book) until the next write of the same size can only land by evicting one. The
 * REAL eviction policy is exercised — nothing is stubbed — so the returned list is in
 * oldest-first order and its head is the buffer the page's own next write must sacrifice.
 */
function fillBufferStoreWithSiblings(chunkSize: number): string[] {
  const chunk = "x".repeat(chunkSize);
  const live: string[] = [];
  vi.useFakeTimers();
  try {
    for (let i = 0; i < 40; i += 1) {
      // Strictly increasing written-at stamps, so "oldest" is unambiguous.
      vi.setSystemTime(new Date(Date.UTC(2026, 0, 1 + i)));
      const key = restoreBufferKey(BOOK_ID, "chapter", `sibling-${i}`);
      const result = writeBuffer(key, chunk, 1);
      if (result.status === "saved") {
        live.push(key);
        continue;
      }
      // The store is at capacity: this write only landed by evicting the oldest.
      if (result.status === "saved-after-eviction") {
        for (const evicted of result.evictedKeys) {
          const at = live.indexOf(evicted);
          if (at >= 0) live.splice(at, 1);
        }
        live.push(key);
      }
      return live;
    }
    return live;
  } finally {
    vi.useRealTimers();
  }
}

/**
 * HARNESS ONLY (`016.chapter-close-continuity`): the page's two new mount reads answer
 * benignly — no warnings, an empty changeset. Nothing here is asserted on.
 */
function armContinuityReads(): void {
  vi.mocked(flagsApi.listFlags).mockResolvedValue({ items: [] });
  vi.mocked(continuityApi.getChapterChangeset).mockResolvedValue({
    chapter_id: CHAPTER_ID,
    added: "",
    modified: "",
    deleted: "",
    status: null,
    created_at: null,
    modified_at: null,
  });
}

beforeEach(() => {
  localStorage.clear();
  editorMounts().length = 0;
  armLoads();
  armContinuityReads();
});

/* ------------------------------------------------- DoD-1 — the buffer key and its version */

describe("editing writes the restore buffer (DoD-1)", () => {
  it("DoD-1: buffers the draft under (bookId, \"chapter\", chapterId) with the BODY response's version — UC-092, US-107.AC-1", async () => {
    const typed = "The road bends east at dusk, and the horses refuse it.";

    renderPage();

    // Presence first: the editor is mounted and the keystroke reached the page.
    const editor = await findEditor();
    expect(editor.value).toBe(STORED_BODY);
    typeBody(typed);
    await waitFor(() => {
      expect(editorValue()).toBe(typed);
    });

    // The draft is buffered under this chapter's own key...
    await waitFor(() => {
      expect(readBuffer(BUFFER_KEY)?.draft).toBe(typed);
    });
    // ...with the version the BODY response carried — never 014's chapter version.
    expect(readBuffer(BUFFER_KEY)?.baseVersion).toBe(BODY_VERSION);
    expect(readBuffer(BUFFER_KEY)?.baseVersion).not.toBe(CHAPTER_VERSION);

    // Keyed per item: no neighbouring key was written.
    expect(readBuffer(restoreBufferKey(BOOK_ID, "chapter", "ch-other"))).toBeNull();
    expect(readBuffer(restoreBufferKey(BOOK_ID, "codex-entry", CHAPTER_ID))).toBeNull();
  });
});

/* ------------------------------------------------------- DoD-2 — restoring a fresh buffer */

describe("returning to a chapter with a matching buffer (DoD-2)", () => {
  it("DoD-2: restores the BUFFERED draft rather than the server's body — US-107.AC-1, US-107.AC-2", async () => {
    const buffered = "An unsaved paragraph the author left behind.";
    // Seeded BEFORE the page mounts, through a real write, with a base version that
    // MATCHES the version the server will serve.
    writeBuffer(BUFFER_KEY, buffered, BODY_VERSION);

    renderPage();

    const editor = await findEditor();
    await waitFor(() => {
      expect(editorValue()).toBe(buffered);
    });
    expect(editor).toBeInTheDocument();
    // The server's body is NOT what the author is looking at.
    expect(editorValue()).not.toBe(STORED_BODY);
    // The editor was (re)mounted holding the restored draft — the external write re-syncs
    // the document by remount (D15), never by an effect.
    expect(editorMounts()).toContain(buffered);

    // A fresh buffer is a restore, not a divergence.
    expect(queryDivergenceHeading()).toBeNull();
  });
});

/* ----------------------------------------------- DoD-3 — buffering never reaches the server */

describe("buffering is device-local (DoD-3)", () => {
  it("DoD-3: editing and navigating away issue no write call — US-107.AC-4, US-103.AC-3", async () => {
    const typed = "A thought committed to nothing but this device.";

    const view = renderPage();

    // Presence first: the edit landed AND the buffer now holds it — otherwise "no write
    // call" would be trivially true.
    await findEditor();
    typeBody(typed);
    await waitFor(() => {
      expect(editorValue()).toBe(typed);
    });
    await waitFor(() => {
      expect(readBuffer(BUFFER_KEY)?.draft).toBe(typed);
    });

    // Navigating away: the page unmounts.
    view.unmount();

    // The draft is still device-local, and nothing was ever written to the server.
    expect(readBuffer(BUFFER_KEY)?.draft).toBe(typed);
    expect(vi.mocked(chaptersApi.updateChapterText)).not.toHaveBeenCalled();
    expect(vi.mocked(chaptersApi.updateChapterSketch)).not.toHaveBeenCalled();
  });
});

/* ---------------------------------------------------- DoD-4 — a successful save clears it */

describe("a successful save clears the buffer (DoD-4)", () => {
  it("DoD-4: after a save the buffer is gone, and a later return shows the server's body with no restore", async () => {
    const typed = "A draft on its way to the server.";
    const stored = "A draft on its way to the server. (stored)";
    vi.mocked(chaptersApi.updateChapterText).mockResolvedValue(
      makeBody({ text: stored, version: BODY_VERSION + 1 }),
    );

    const view = renderPage();

    // Presence first: establish a real buffer THROUGH the page, so the clear has
    // something to lose.
    await findEditor();
    typeBody(typed);
    await waitFor(() => {
      expect(readBuffer(BUFFER_KEY)?.draft).toBe(typed);
    });

    fireEvent.click(saveControl());
    await waitFor(() => {
      expect(vi.mocked(chaptersApi.updateChapterText)).toHaveBeenCalledTimes(1);
    });

    // The save cleared it.
    await waitFor(() => {
      expect(readBuffer(BUFFER_KEY)).toBeNull();
    });

    // A later return shows the SERVER's body, with nothing restored over it.
    view.unmount();
    editorMounts().length = 0;
    vi.mocked(chaptersApi.getChapterText).mockResolvedValue(
      makeBody({ text: stored, version: BODY_VERSION + 1 }),
    );

    renderPage();
    await findEditor();
    await waitFor(() => {
      expect(editorValue()).toBe(stored);
    });
    expect(editorValue()).not.toBe(typed);
    expect(queryDivergenceHeading()).toBeNull();
  });
});

/* --------------------------------------- DoD-5 — the LOAD-TIME entrance, the load-bearing one */

describe("a buffer whose base version no longer matches (DoD-5)", () => {
  it("DoD-5: opens the divergence view directly at load time, with NO save attempted", async () => {
    const buffered = "The paragraph the author was in the middle of.";
    // Seeded BEFORE the page mounts, with a base version the server has moved past.
    writeBuffer(BUFFER_KEY, buffered, BODY_VERSION - 1);

    renderPage();

    // Presence first: the whole divergence surface is on screen, showing both sides.
    await findDivergenceView();
    expect(pageText()).toContain(STORED_BODY);
    expect(pageText()).toContain(buffered);

    // ...and only THEN the load-bearing negative: the mismatch was detected before
    // anything was attempted against the server.
    expect(vi.mocked(chaptersApi.updateChapterText)).not.toHaveBeenCalled();
    // The body was fetched once, by the ordinary load — no second round trip is needed
    // on this entrance.
    expect(vi.mocked(chaptersApi.getChapterText)).toHaveBeenCalledTimes(1);
  });
});

/* ------------------------------------------------------ DoD-6 — the SAVE-TIME entrance (409) */

describe("a 409 from the save (DoD-6)", () => {
  it("DoD-6: re-fetches the server's body and opens the divergence view against the author's draft — UC-039, US-041.AC-1", async () => {
    const typed = "My own ending, written while the chapter moved.";
    const serverMoved = "Someone else's ending, already saved.";
    vi.mocked(chaptersApi.getChapterText)
      .mockResolvedValueOnce(makeBody())
      .mockResolvedValueOnce(makeBody({ text: serverMoved, version: SERVER_VERSION }));
    vi.mocked(chaptersApi.updateChapterText).mockRejectedValue(
      new ApiError(409, "This chapter has moved on since you loaded it."),
    );

    renderPage();
    await findEditor();
    typeBody(typed);
    fireEvent.click(saveControl());

    // Presence first: the divergence view opened, and it shows the SERVER's current body
    // beside the author's draft.
    await findDivergenceView();
    expect(pageText()).toContain(serverMoved);
    expect(pageText()).toContain(typed);

    // The server's body was re-fetched for this view.
    await waitFor(() => {
      expect(vi.mocked(chaptersApi.getChapterText)).toHaveBeenCalledTimes(2);
    });

    // No auto-merge and no silent overwrite: exactly one save was attempted, the author's
    // text is intact, and nothing was written on their behalf.
    expect(vi.mocked(chaptersApi.updateChapterText)).toHaveBeenCalledTimes(1);
    expect(pageText()).not.toContain(`${serverMoved}${typed}`);
    expect(pageText()).not.toContain(`${typed}${serverMoved}`);
  });
});

/* --------------------------------------------------------- DoD-7 — taking the server's side */

describe("keeping the server's version (DoD-7)", () => {
  it("DoD-7: discards the draft, clears the buffer and shows the server's body — nothing of the author's text is written — US-041.AC-3", async () => {
    const buffered = "A paragraph the author is about to abandon.";
    writeBuffer(BUFFER_KEY, buffered, BODY_VERSION - 1);

    renderPage();
    await findDivergenceView();

    fireEvent.click(keepServerControl());

    // Presence first: the resolution actually happened — the view is gone and the
    // chapter is back to editing the SERVER's body.
    await waitFor(() => {
      expect(queryDivergenceHeading()).toBeNull();
    });
    const editor = await findEditor();
    await waitFor(() => {
      expect(editorValue()).toBe(STORED_BODY);
    });
    expect(editor).toBeInTheDocument();
    expect(editorValue()).not.toBe(buffered);

    // ...and only then the two negatives: the buffer is gone and nothing of the
    // abandoning author's text reached the server.
    await waitFor(() => {
      expect(readBuffer(BUFFER_KEY)).toBeNull();
    });
    expect(vi.mocked(chaptersApi.updateChapterText)).not.toHaveBeenCalled();
  });
});

/* ---------------------------------------------------------- DoD-8 — taking the draft's side */

describe("keeping my draft (DoD-8)", () => {
  it("DoD-8: re-saves the draft against the NEW version and the chapter then shows the reconciled text — US-041.AC-2", async () => {
    const typed = "The ending I intend to keep.";
    const serverMoved = "The ending someone else saved first.";
    vi.mocked(chaptersApi.getChapterText)
      .mockResolvedValueOnce(makeBody())
      .mockResolvedValueOnce(makeBody({ text: serverMoved, version: SERVER_VERSION }));
    vi.mocked(chaptersApi.updateChapterText)
      .mockRejectedValueOnce(new ApiError(409, "This chapter has moved on since you loaded it."))
      .mockResolvedValue(makeBody({ text: typed, version: SERVER_VERSION + 1 }));

    renderPage();
    await findEditor();
    typeBody(typed);
    fireEvent.click(saveControl());
    await findDivergenceView();

    fireEvent.click(keepDraftControl());

    // The re-save carries the version the SERVER now holds — adopting it first is what
    // makes the second save non-stale (`007.context.md`).
    await waitFor(() => {
      expect(vi.mocked(chaptersApi.updateChapterText)).toHaveBeenCalledTimes(2);
    });
    const secondPayload = vi.mocked(chaptersApi.updateChapterText).mock.calls[1][2];
    expect(secondPayload).toEqual({ text: typed, expected_version: SERVER_VERSION });

    // It succeeded: the view is gone and the chapter shows the reconciled text.
    await waitFor(() => {
      expect(queryDivergenceHeading()).toBeNull();
    });
    await findEditor();
    await waitFor(() => {
      expect(editorValue()).toBe(typed);
    });
  });
});

/* ------------------------------------------------- DoD-9 — a draft holding both members' text */

describe("a reconciled body holding both members' text (DoD-9)", () => {
  it("DoD-9: a draft containing both members' text, kept over the server's, lands as the chapter's body — US-040.AC-4", async () => {
    const original = "The gate stood open at dawn.";
    const beasText = "Bea wrote: the sentries had already gone.";
    const anasText = "Ana wrote: the road beyond was empty.";
    const merged = `${beasText}\n\n${anasText}`;

    vi.mocked(chaptersApi.getChapterText)
      .mockResolvedValueOnce(makeBody({ text: original }))
      // Bea's save landed while Ana was writing.
      .mockResolvedValueOnce(makeBody({ text: beasText, version: SERVER_VERSION }));
    vi.mocked(chaptersApi.updateChapterText)
      .mockRejectedValueOnce(new ApiError(409, "This chapter has moved on since you loaded it."))
      .mockResolvedValue(makeBody({ text: merged, version: SERVER_VERSION + 1 }));

    renderPage();
    await findEditor();
    // Ana composes a body carrying both members' text — the system never merges for her.
    typeBody(merged);
    fireEvent.click(saveControl());

    // Her stale save is refused and both sides are shown.
    await findDivergenceView();
    expect(pageText()).toContain(beasText);
    expect(pageText()).toContain(anasText);

    fireEvent.click(keepDraftControl());

    // The re-issued body carries BOTH members' text and is saved against the current
    // version.
    await waitFor(() => {
      expect(vi.mocked(chaptersApi.updateChapterText)).toHaveBeenCalledTimes(2);
    });
    const payload = vi.mocked(chaptersApi.updateChapterText).mock.calls[1][2];
    expect(payload.expected_version).toBe(SERVER_VERSION);
    expect(payload.text).toContain(beasText);
    expect(payload.text).toContain(anasText);

    // ...and it is what the chapter now shows.
    await findEditor();
    await waitFor(() => {
      expect(editorValue()).toContain(beasText);
    });
    expect(editorValue()).toContain(anasText);
  });
});

/* ---------------------------------------------------------------- DoD-10 — an eviction */

describe("a buffer write that had to evict (DoD-10)", () => {
  it("DoD-10: names the evicted keys, and the current chapter's own buffer is never the victim", async () => {
    const chunkSize = 400_000;
    const siblings = fillBufferStoreWithSiblings(chunkSize);
    // The store must actually be full for the page's own write to force an eviction.
    expect(siblings.length).toBeGreaterThan(0);
    const oldestSibling = siblings[0];

    renderPage();
    await findEditor();

    // One oversized keystroke: the page's buffer write can only land by evicting.
    const bigDraft = "y".repeat(chunkSize);
    typeBody(bigDraft);

    // Presence first: the author is TOLD, and told which drafts went.
    await screen.findByText(EVICTION_TITLE);
    await waitFor(() => {
      expect(pageText()).toContain(oldestSibling);
    });

    // ...and only then the invariant: this chapter's own buffer survived and is never
    // named among the casualties.
    expect(readBuffer(BUFFER_KEY)?.draft).toBe(bigDraft);
    expect(pageText()).not.toContain(BUFFER_KEY);
    expect(readBuffer(oldestSibling)).toBeNull();
  });
});

/* -------------------------------------------- DoD-11 — the divergence view's shape and tone */

describe("the divergence view's shape (DoD-11)", () => {
  it("DoD-11: renders inline in place of the editor, is not a modal, and offers exactly two choices with neither pre-selected", async () => {
    const buffered = "The paragraph that forked.";
    writeBuffer(BUFFER_KEY, buffered, BODY_VERSION - 1);

    renderPage();

    // Presence first: the two named choices exist and are both usable.
    await findDivergenceView();
    expect(keepServerControl()).toBeEnabled();
    expect(keepDraftControl()).toBeEnabled();

    // It replaces the editor and its save control while it is open.
    expect(queryEditor()).toBeNull();
    expect(querySaveControl()).toBeNull();

    // It is not a modal, and it does not block the rest of the page: the chapter's other
    // regions keep rendering beside it.
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(screen.queryByRole("alertdialog")).toBeNull();
    expect(pageText()).toContain(CHAPTER_TITLE);
    expect(hasFieldLabelled(/prompt/i)).toBe(true);

    // Exactly two choices — no third outcome, and no merge: the system never produces a
    // merged body (`domain-chapter.md`: "no automatic merge at MVP").
    expect(screen.queryAllByRole("radio")).toHaveLength(0);
    expect(screen.queryAllByRole("checkbox")).toHaveLength(0);
    expect(screen.queryByRole("button", { name: /merge/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /both/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /cancel/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /discard/i })).toBeNull();

    // Neither is pre-selected: neither is marked as chosen, and neither has taken focus.
    for (const control of [keepServerControl(), keepDraftControl()]) {
      expect(control).not.toHaveAttribute("aria-pressed", "true");
      expect(control).not.toHaveAttribute("aria-checked", "true");
      expect(control).not.toBe(document.activeElement);
    }
  });
});
