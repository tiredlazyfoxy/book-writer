/**
 * The chapter page's BODY region — 015.chapter-writing-free-mode / 006.chapter-page-body,
 * DoD-1 · DoD-2 · DoD-3 · DoD-4 · DoD-5 · DoD-6 · DoD-7 · DoD-8 · DoD-9 · DoD-10.
 * (DoD-11 is [manual/live] — the three build gates — and gets no test.)
 *
 * A NEW file beside 014's `ChapterPage.test.tsx`, which is not touched: everything here
 * is the third (body) trio, the Markdown draft, the explicit save and the read-only
 * branch. 014's chapter / sketch / prompt behaviour stays that file's subject.
 *
 * Bound to the frozen signatures in status.md -> `## Skeleton` (step 006, plus step 004's
 * api pair and step 005's editor seam, both consumed unchanged):
 *   const ChapterPage: FunctionComponent          // observer, ZERO props; reads :bookId
 *                                                 // and :id from the router
 *   class ChapterPageState { body; bodyStatus; bodyError;
 *                            bodyDraft; bodyServerErrors; bodySubmitStatus;
 *                            bodyBaseVersion; bodyEditorGeneration;
 *                            get bodyDirty; get canEditBody; get canSaveBody }
 *   loadChapterBody(state, bookId, chapterId, signal?): Promise<void>
 *   editBodyDraft(state, bookId, chapterId, text): void
 *   saveChapterBody(state, bookId, chapterId, signal?): Promise<void>
 *   getChapterText(bookId, chapterId, signal?): Promise<ChapterTextResponse>
 *   updateChapterText(bookId, chapterId, body: UpdateChapterTextRequest, signal?)
 *                                              : Promise<ChapterTextResponse>
 *   ChapterBodyEditor({ initialMarkdown, onChange, onSelectionChange, ariaLabel })
 *   resolveEditability(subject): Editability     // owns the read-only copy
 *
 * The frozen view surface this file queries (status.md -> step 006 -> "the view surface
 * contract"): the editor's accessible name is `Chapter body`; the save control's
 * accessible name is `Save body`; the load-failure alert is titled `Could not load the
 * chapter body` and carries the error verbatim; the save-failure alert is titled
 * `Could not save the chapter body` and lists the server's messages verbatim; a
 * non-`open` chapter renders its body through `react-markdown` with
 * `resolveEditability`'s reason and NO editor and NO save control.
 *
 * Every expected value comes from the SPEC, never from the page's code:
 *   - the body is its own sub-resource (`context.md` -> D13), so it is a THIRD trio that
 *     loads and fails independently of the chapter and prompt trios — DoD-1;
 *   - the editor is mounted only for an `open` chapter (D16) and is seeded with the
 *     stored body — DoD-2;
 *   - the base version is the one the BODY response carried and NOTHING else
 *     (`006.context.md` -> "Where the version comes from"), and the backend is the source
 *     of truth: after a save the surface shows what the SERVER returned, never the local
 *     draft (`context.md` -> cross-cutting frontend constraints) — DoD-3, US-040.AC-1;
 *   - the response's version becomes the next save's base, so sequential saves both land
 *     — DoD-4;
 *   - the save is gated on "dirty AND no save in flight", with NO emptiness rule — every
 *     string including `""` is a valid body (`context.md` -> the form-state shape) —
 *     DoD-5;
 *   - nothing reaches the server until the author saves (D1; US-107.AC-4's draft-until-
 *     saved) — DoD-6;
 *   - a refusal is the server's own message, surfaced verbatim and losing nothing typed;
 *     the proposal-mode refusal names FEAT-010 (D11) and the archived-book refusal is a
 *     403 (D10) — DoD-7;
 *   - `planned` / `closing` / `closed` render read-only with the reason `subject.ts`
 *     already owns — the client affordance half of US-038.AC-1 — DoD-8;
 *   - the 409 case below is SUPERSEDED: step 006's DoD-9 foresaw it in its own words —
 *     "(Step 007 turns this into the divergence view.)" — and step 007's DoD-6 now
 *     requires the 409 to re-fetch the server's body and open the divergence view against
 *     the author's draft, which is mutually exclusive with 006's "no re-fetch, surface a
 *     refusal" wording. The single case is restated against step 007's contract and
 *     retagged; it now serves 007's DoD-6 — US-041.AC-1, UC-039;
 *   - the editor re-syncs by REMOUNT (D15): the load seeds it, a keystroke never does —
 *     DoD-10.
 *
 * Two whole-module mocks, per `006.context.md` -> Testing:
 *   - `api/chapters` is replaced by a factory enumerating ALL TEN frozen exports — 014's
 *     eight plus step 004's two — because a factory replaces the whole module and an
 *     omitted export would be `undefined` for every importer, failing for the wrong
 *     reason;
 *   - `work/components/chapter/ChapterBodyEditor` (folder SINGULAR) is replaced by a
 *     trivial stub over its frozen four-prop seam: a labelled control whose value is the
 *     `initialMarkdown` prop and whose edits call `onChange` with a string. ProseMirror
 *     is never driven under jsdom — that is the feature's recorded testing decision, not
 *     a workaround. The stub records the `initialMarkdown` it saw at each MOUNT, which is
 *     how DoD-10 observes the generation counter BEHAVIOURALLY (remount / no remount)
 *     rather than by name.
 * `ApiError` is the REAL class from `api/client`: DoD-7 and DoD-9 need real 403 / 409
 * instances. A chapter refusal reaches the client as a plain-string `detail`, so the
 * refusal text is the error's message — the codex family's `detail.message` object path
 * is deliberately not modelled here (step 003 / 004 freeze notes).
 *
 * Queries are by ROLE or LABEL only — no test ids, nothing asserted about colour or DOM
 * shape. Copy the author reads is asserted as readable TEXT.
 *
 * `globals: false`: every primitive is imported explicitly.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { Route, Routes } from "react-router-dom";
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
import { resolveEditability } from "../../src/work/subject";
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
 * The editor stub. It honours the frozen four-prop seam and nothing else: the control's
 * accessible name is the `ariaLabel` prop, its value is the `initialMarkdown` prop, and
 * an edit calls `onChange` with a plain string. Each MOUNT appends the `initialMarkdown`
 * it was given to a log on `globalThis` (the factory is hoisted above every import, so it
 * may not close over a module-level binding).
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
      const holder = globalThis as unknown as { __chapterBodyEditorMounts?: string[] };
      holder.__chapterBodyEditorMounts = holder.__chapterBodyEditorMounts ?? [];
      holder.__chapterBodyEditorMounts.push(props.initialMarkdown);
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

/** The version the BODY response carries. */
const BODY_VERSION = 4;
/**
 * The version 014's CHAPTER response carries — deliberately different. A save composed
 * against this number would be composed against a payload that is not the body's, which
 * is exactly the stale-write bug the contract exists to prevent (`006.context.md`).
 */
const CHAPTER_VERSION = 99;

/** The frozen accessible names of the two body controls (status.md -> step 006). */
const EDITOR_LABEL = "Chapter body";
const SAVE_LABEL = "Save body";

/** The frozen alert titles. */
const LOAD_ERROR_TITLE = "Could not load the chapter body";
const SAVE_ERROR_TITLE = "Could not save the chapter body";

/** The three states in which a chapter body is read-only (D16, US-038.AC-1). */
const NON_OPEN_STATES: ChapterLifecycleState[] = ["planned", "closing", "closed"];

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
function renderPage(route: string = CHAPTER_ROUTE): void {
  renderWithProviders(
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
  const holder = globalThis as unknown as { __chapterBodyEditorMounts?: string[] };
  holder.__chapterBodyEditorMounts = holder.__chapterBodyEditorMounts ?? [];
  return holder.__chapterBodyEditorMounts;
}

interface Deferred<T> {
  promise: Promise<T>;
  resolve: (value: T) => void;
}

function deferred<T>(): Deferred<T> {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((res) => {
    resolve = res;
  });
  return { promise, resolve };
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
  editorMounts().length = 0;
  armLoads();
  armContinuityReads();
});

/* ------------------------------------------------------------- DoD-1 — the third trio */

describe("the chapter body loads as its own trio (DoD-1)", () => {
  it("DoD-1: loads the chapter body on mount and shows it", async () => {
    renderPage();

    const editor = await findEditor();
    expect(editor.value).toBe(STORED_BODY);

    expect(vi.mocked(chaptersApi.getChapterText)).toHaveBeenCalledTimes(1);
    const [bookId, chapterId] = vi.mocked(chaptersApi.getChapterText).mock.calls[0];
    expect(bookId).toBe(BOOK_ID);
    expect(chapterId).toBe(CHAPTER_ID);
  });

  it("DoD-1: a failed body load shows the body's OWN error and leaves the chapter and prompt sections whole", async () => {
    vi.mocked(chaptersApi.getChapterText).mockRejectedValue(
      new ApiError(500, "The chapter body is unavailable"),
    );

    renderPage();

    // Presence first: the body region's own error surface must actually be there.
    await screen.findByText(LOAD_ERROR_TITLE);
    expect(pageText()).toContain("The chapter body is unavailable");

    // ...and the other two trios are untouched by it.
    expect(pageText()).toContain(CHAPTER_TITLE);
    expect(hasFieldLabelled(/prompt/i)).toBe(true);
  });

  it("DoD-1: a failed CHAPTER load leaves the body section loaded and editable", async () => {
    vi.mocked(chaptersApi.getChapter).mockRejectedValue(new ApiError(500, "Chapter unavailable"));

    renderPage();

    const editor = await findEditor();
    expect(editor.value).toBe(STORED_BODY);
    expect(querySaveControl()).not.toBeNull();
  });

  it("DoD-1: a failed PROMPT load leaves the body section loaded and editable", async () => {
    vi.mocked(chaptersApi.getOwnChapterSystemPrompt).mockRejectedValue(
      new ApiError(500, "Prompt service unavailable"),
    );

    renderPage();

    const editor = await findEditor();
    expect(editor.value).toBe(STORED_BODY);
    expect(querySaveControl()).not.toBeNull();
  });
});

/* --------------------------------------------------- DoD-2 — the open chapter's editor */

describe("the open chapter's editor (DoD-2)", () => {
  it("DoD-2: mounts the editor seeded with the stored body and offers a save control", async () => {
    renderPage();

    const editor = await findEditor();
    expect(editor.value).toBe(STORED_BODY);
    expect(querySaveControl()).not.toBeNull();
  });

  it("DoD-2: an EMPTY stored body still mounts the editor — `\"\"` is a legitimate body", async () => {
    armLoads({ text: "" });

    renderPage();

    const editor = await findEditor();
    expect(editor.value).toBe("");
  });
});

/* --------------------------------------------------- DoD-3 / DoD-4 — the explicit save */

describe("saving the body (DoD-3, DoD-4)", () => {
  it("DoD-3: sends the draft with the version the BODY response carried, then shows the SERVER's text — US-040.AC-1", async () => {
    const typed = "The road bends east at dusk, and the horses refuse it.";
    const returned = "The road bends east at dusk, and the horses refuse it. (normalised)";
    vi.mocked(chaptersApi.updateChapterText).mockResolvedValue(
      makeBody({ text: returned, version: BODY_VERSION + 1 }),
    );

    renderPage();
    await findEditor();
    typeBody(typed);
    fireEvent.click(saveControl());

    await waitFor(() => {
      expect(vi.mocked(chaptersApi.updateChapterText)).toHaveBeenCalledTimes(1);
    });
    const [bookId, chapterId, payload] = vi.mocked(chaptersApi.updateChapterText).mock.calls[0];
    expect(bookId).toBe(BOOK_ID);
    expect(chapterId).toBe(CHAPTER_ID);
    // The BODY response's version — never 014's chapter version.
    expect(payload).toEqual({ text: typed, expected_version: BODY_VERSION });

    // The backend is the source of truth: the surface shows what came back.
    await waitFor(() => {
      expect(editorValue()).toBe(returned);
    });
    expect(editorValue()).not.toBe(typed);
  });

  it("DoD-4: the next save carries the version the previous response returned, so two sequential saves both succeed", async () => {
    let version = BODY_VERSION;
    vi.mocked(chaptersApi.updateChapterText).mockImplementation(async (_bookId, _chapterId, body) => {
      version += 1;
      return makeBody({ text: `${body.text} [saved]`, version });
    });

    renderPage();
    await findEditor();

    typeBody("first pass");
    fireEvent.click(saveControl());
    await waitFor(() => {
      expect(editorValue()).toBe("first pass [saved]");
    });

    typeBody("second pass");
    fireEvent.click(saveControl());
    await waitFor(() => {
      expect(vi.mocked(chaptersApi.updateChapterText)).toHaveBeenCalledTimes(2);
    });

    const firstPayload = vi.mocked(chaptersApi.updateChapterText).mock.calls[0][2];
    const secondPayload = vi.mocked(chaptersApi.updateChapterText).mock.calls[1][2];
    expect(firstPayload.expected_version).toBe(BODY_VERSION);
    expect(secondPayload.expected_version).toBe(BODY_VERSION + 1);

    await waitFor(() => {
      expect(editorValue()).toBe("second pass [saved]");
    });
    expect(pageText()).not.toContain(SAVE_ERROR_TITLE);
  });
});

/* ------------------------------------------- DoD-5 — when the save control is available */

describe("the save control's availability (DoD-5)", () => {
  it("DoD-5: available once the draft differs from the loaded body, unavailable while it matches", async () => {
    renderPage();
    await findEditor();

    // Presence first: the control exists AND is usable in the dirty case.
    typeBody("a different body");
    await waitFor(() => {
      expect(saveControl()).toBeEnabled();
    });

    // Back to the loaded body — nothing to save.
    typeBody(STORED_BODY);
    await waitFor(() => {
      expect(saveControl()).toBeDisabled();
    });
  });

  it("DoD-5: unavailable while a save is in flight", async () => {
    const pending = deferred<ChapterTextResponse>();
    vi.mocked(chaptersApi.updateChapterText).mockReturnValue(pending.promise);

    renderPage();
    await findEditor();

    typeBody("a different body");
    await waitFor(() => {
      expect(saveControl()).toBeEnabled();
    });

    fireEvent.click(saveControl());
    await waitFor(() => {
      expect(saveControl()).toBeDisabled();
    });

    pending.resolve(makeBody({ text: "a different body", version: BODY_VERSION + 1 }));
    await waitFor(() => {
      expect(editorValue()).toBe("a different body");
    });
  });

  it("DoD-5: saving an EMPTY body is allowed — there is no emptiness rule", async () => {
    vi.mocked(chaptersApi.updateChapterText).mockResolvedValue(
      makeBody({ text: "", version: BODY_VERSION + 1 }),
    );

    renderPage();
    await findEditor();

    typeBody("");
    await waitFor(() => {
      expect(saveControl()).toBeEnabled();
    });

    fireEvent.click(saveControl());
    await waitFor(() => {
      expect(vi.mocked(chaptersApi.updateChapterText)).toHaveBeenCalledTimes(1);
    });
    expect(vi.mocked(chaptersApi.updateChapterText).mock.calls[0][2]).toEqual({
      text: "",
      expected_version: BODY_VERSION,
    });
  });
});

/* --------------------------------------------- DoD-6 — nothing reaches the server early */

describe("editing writes nothing to the server (DoD-6)", () => {
  it("DoD-6: editing the body issues no write call", async () => {
    renderPage();

    // Presence first: the editor is mounted AND the keystroke reached the page.
    const editor = await findEditor();
    expect(editor.value).toBe(STORED_BODY);
    typeBody("an unsaved thought");
    await waitFor(() => {
      expect(editorValue()).toBe("an unsaved thought");
    });

    expect(vi.mocked(chaptersApi.updateChapterText)).not.toHaveBeenCalled();
  });
});

/* ------------------------------------------------------------- DoD-7 — refused by 403 */

describe("a refused save (DoD-7)", () => {
  it("DoD-7: a 403 proposal-mode refusal naming FEAT-010 is surfaced and the draft survives — D11", async () => {
    const refusal =
      "Proposal mode holds a co-author's changes for review, and FEAT-010 is not built yet.";
    vi.mocked(chaptersApi.updateChapterText).mockRejectedValue(new ApiError(403, refusal));

    renderPage();
    await findEditor();
    typeBody("a co-author's paragraph");
    fireEvent.click(saveControl());

    await screen.findByText(SAVE_ERROR_TITLE);
    expect(pageText()).toContain(refusal);
    expect(pageText()).toContain("FEAT-010");
    expect(editorValue()).toBe("a co-author's paragraph");
  });

  it("DoD-7: a 403 archived-book refusal is surfaced and the draft survives — D10", async () => {
    const refusal = "This book is archived, so its chapters cannot be written to.";
    vi.mocked(chaptersApi.updateChapterText).mockRejectedValue(new ApiError(403, refusal));

    renderPage();
    await findEditor();
    typeBody("a paragraph written into an archive");
    fireEvent.click(saveControl());

    await screen.findByText(SAVE_ERROR_TITLE);
    expect(pageText()).toContain(refusal);
    expect(editorValue()).toBe("a paragraph written into an archive");
  });
});

/* ------------------------------------------------------- DoD-8 — the read-only branch */

describe("a chapter that is not open (DoD-8)", () => {
  for (const state of NON_OPEN_STATES) {
    it(`DoD-8: on a ${state} chapter the body is read-only with a stated reason and offers no save control and no editor — US-038.AC-1`, async () => {
      armLoads({ state });

      renderPage();

      // Presence first: the stored body and the author-facing reason are both on screen.
      await waitFor(() => {
        expect(pageText()).toContain(STORED_BODY);
      });
      const reason = resolveEditability({
        kind: "chapter",
        entityId: CHAPTER_ID,
        chapterState: state,
      }).readOnlyReason;
      expect(reason).not.toBeNull();
      expect((reason ?? "").length).toBeGreaterThan(0);
      expect(pageText()).toContain(reason ?? "");

      // ...and only then the two absences.
      expect(queryEditor()).toBeNull();
      expect(editorMounts()).toHaveLength(0);
      expect(querySaveControl()).toBeNull();
    });
  }
});

/* ------------------------------------------- the 409: step 007's DoD-6, superseding 006's DoD-9 */

/**
 * SUPERSEDED CASE. Step 006's DoD-9 ("a 409 leaves the stored body untouched on screen and
 * surfaces a refusal, without re-fetching") carried the planner's own parenthetical
 * "(Step 007 turns this into the divergence view.)". Step 007's DoD-6 now requires that same
 * 409 to re-fetch the server's body and open the divergence view against the author's draft,
 * and its DoD-11 requires that view to replace the editor and the save control while open.
 * The two readings cannot both hold on one code path, so this case is restated against the
 * step-007 contract and retagged — it defends 007's DoD-6 (US-041.AC-1, UC-039) and 006's
 * DoD-9 is retired by supersession, not dropped.
 *
 * Names come from the frozen step-007 view surface (status.md -> `## Skeleton` -> "### Step
 * 007" -> "the frozen view surface"). The step-007 spec's own coverage of this behaviour
 * lives in `ChapterPageReconcile.test.tsx`; this case is kept only so that the 006 file no
 * longer asserts a contract the feature has moved past.
 */
describe("a stale save opens the divergence view (step 007 DoD-6, superseding step 006 DoD-9)", () => {
  it("007 DoD-6 (supersedes 006 DoD-9): a 409 re-fetches the server's body and opens the divergence view against the draft — US-041.AC-1, UC-039", async () => {
    // The restore buffer is device-local and survives between cases in this file; this case
    // both starts and ends from a clean store so it neither inherits nor leaves a buffer.
    localStorage.clear();

    const typed = "my own ending";
    const serverMoved = "someone else's ending, already saved";
    vi.mocked(chaptersApi.getChapterText)
      .mockResolvedValueOnce(makeBody())
      .mockResolvedValueOnce(makeBody({ text: serverMoved, version: BODY_VERSION + 5 }));
    vi.mocked(chaptersApi.updateChapterText).mockRejectedValue(
      new ApiError(409, "This chapter has moved on since you loaded it."),
    );

    renderPage();
    await findEditor();
    typeBody(typed);
    fireEvent.click(saveControl());

    // Presence first: the divergence view is on screen, naming both sides.
    await screen.findByRole("heading", { name: "Unsaved changes diverged" });
    await screen.findByText("This chapter's body changed since your draft");
    expect(screen.getByText("Current server version")).toBeInTheDocument();
    expect(screen.getByText("Your draft")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Keep the server version" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Keep my draft" })).toBeInTheDocument();

    // It shows the SERVER's current body beside the author's draft.
    expect(pageText()).toContain(serverMoved);
    expect(pageText()).toContain(typed);

    // The server's body was re-fetched for the view.
    await waitFor(() => {
      expect(vi.mocked(chaptersApi.getChapterText)).toHaveBeenCalledTimes(2);
    });

    // No auto-merge and no silent overwrite: exactly one save was attempted, and nothing was
    // written on the author's behalf.
    expect(vi.mocked(chaptersApi.updateChapterText)).toHaveBeenCalledTimes(1);
    expect(pageText()).not.toContain(`${serverMoved}${typed}`);
    expect(pageText()).not.toContain(`${typed}${serverMoved}`);

    localStorage.clear();
  });
});

/* -------------------------------------------------- DoD-10 — the generation counter */

describe("the editor's generation counter (DoD-10)", () => {
  it("DoD-10: the editor is mounted with the LOADED body, and a keystroke does not remount it — D15", async () => {
    renderPage();

    // The load bumps the generation, so the editor mounts holding the server's body.
    await findEditor();
    await waitFor(() => {
      expect(editorMounts()).toEqual([STORED_BODY]);
    });

    // A keystroke originates INSIDE the editor and must not remount it.
    typeBody("a keystroke");
    await waitFor(() => {
      expect(editorValue()).toBe("a keystroke");
    });
    expect(editorMounts()).toEqual([STORED_BODY]);
  });
});
