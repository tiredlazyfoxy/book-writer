/**
 * The chapter page as a WRITABLE canvas target — 015.chapter-writing-free-mode /
 * 012.chapter-canvas-wiring, DoD-1 · DoD-2 · DoD-3 · DoD-4 · DoD-5 · DoD-6 · DoD-7 ·
 * DoD-8 · DoD-9 · DoD-10.
 * (DoD-11 and DoD-12 are [manual/live] — a live turn calling the three write tools, and
 * the three build gates — and get no test.)
 *
 * A NEW file beside `ChapterPageBody.test.tsx` (step 006), `ChapterPageReconcile.test.tsx`
 * (step 007) and `ChapterPageStateControls.test.tsx` (step 008); none of those is touched.
 * Its subject is the loop this step closes: the page registers itself as a writable canvas
 * target, applies the assistant's three operations to its draft after snapshotting for
 * undo, offers an undo control, and the chat pane carries the author's selection.
 *
 * Bound to the frozen signatures in status.md -> `## Skeleton` (step 012, plus steps
 * 004/005/006/007/011, all consumed unchanged):
 *   const ChapterPage: FunctionComponent            // observer, ZERO props; :bookId, :id
 *   class ChapterPageState { constructor(bookId, chapterId);
 *                            selectedText: string | null; unappliedSelectionWrite: string | null;
 *                            readonly subjectSource: ContentSubjectSource;
 *                            readonly applyDraft(field, text, op?): void }
 *   setChapterSelection(state, selectedText: string): void
 *   undoAssistantBodyWrite(state, bookId, chapterId): void
 *   contentSubject: registerContentSubject(source, applyDraft?) ·
 *                   unregisterContentSubject(source) · currentContentSubject() ·
 *                   dispatchCanvasFrame(bookId, frame) · setContentSelection(source, sel) ·
 *                   currentContentSelection(): string | null · clearContentSelection(source)
 *   chapterUndo: pushChapterUndoSnapshot(bookId, chapterId, body) ·
 *                popChapterUndoSnapshot(bookId, chapterId): string | null ·
 *                chapterUndoDepth(bookId, chapterId): number ·
 *                clearChapterUndo(bookId, chapterId)
 *   restoreBuffer: restoreBufferKey(bookId, subjectKind, subjectId) · readBuffer(key)
 *   types/chats: interface TurnRequest { prompt; subject_kind?; subject_id?; codex_kind?;
 *                                        selection_text? }        // a FLAT field
 *   api/chats: streamChatTurn(bookId, chatId, prompt, handlers, subject?, selectionText?)
 *   chatPaneState: ChatPaneState · sendChatTurn(state, bookId, text) ·
 *                  retryChatTurn(state, bookId)
 *   api/chapters: getChapterText · updateChapterText (+ 014's eight)
 *   ChapterBodyEditor({ initialMarkdown, onChange, onSelectionChange, ariaLabel })
 *
 * The frozen view surface this file queries (status.md -> step 012, plus step 006's two
 * shipped names): the editor's accessible name is `Chapter body`; the save control's is
 * `Save body`; the undo control's is exactly `Undo the assistant's last write`; the
 * unapplied-write alert is titled exactly `The assistant's write was not applied` and
 * carries the refused text verbatim.
 *
 * Every expected value comes from the SPEC, never from the page's code:
 *   - the page registers as the content-pane subject WITH an apply-draft callback and
 *     unregisters on unmount; a chapter that is not `open` is a subject but not a writable
 *     target (step file DoD-1) — DoD-1;
 *   - the three operations of D17: `replace` sets the whole draft, `append` goes at its
 *     END, `replace_selection` replaces the currently-selected text inside it — DoD-2;
 *   - the apply ORDER is snapshot -> apply -> draft-edit path -> generation bump
 *     (`012.context.md` -> "The apply order is not arbitrary"): applying before
 *     snapshotting would store the post-write text and make undo a no-op, so undo must
 *     restore EXACTLY the text that was on screen before the frame — DoD-3;
 *   - an applied frame routes through step 006's single draft-edit path, so the restore
 *     buffer is written exactly as a keystroke writes it, and NOTHING reaches the server
 *     (D4's "nothing reaches the server until the author saves") — DoD-4;
 *   - external draft writes re-sync the editor by REMOUNT (D15), and a keystroke — which
 *     originates inside the editor — never does — DoD-5;
 *   - a `replace_selection` frame with no active selection is REFUSED, not placed:
 *     `012.context.md` -> "Why a selection frame with no selection is refused rather than
 *     placed" ("writing at a location nobody chose ... a refusal is loud"). No fallback to
 *     append, ever, and never applied at position zero — DoD-6;
 *   - the undo stack is 20 deep per (book, chapter), in memory, assistant writes only
 *     (D6) — DoD-7;
 *   - the selection lives in the module-level registry and is cleared when the owning page
 *     goes (D5) — DoD-8;
 *   - the selection rides the turn request as a FLAT field beside `subject_kind` /
 *     `subject_id` / `codex_kind`, never inside a subject object, and the pane keeps no
 *     copy of its own — it reads the registry at SEND time (`012.context.md` -> "The chat
 *     pane reads the selection at send time and holds none") — DoD-9;
 *   - a selection is client-side only and is NEVER persisted or saved (D5): a body save
 *     carries the text and the version and nothing else — DoD-10.
 *
 * Mocking, per `012.context.md` -> Testing:
 *   - `api/chapters` is replaced by a factory enumerating ALL TEN frozen exports;
 *   - `work/components/chapter/ChapterBodyEditor` (folder SINGULAR) is replaced by a stub
 *     over its frozen four-prop seam. It drives BOTH callbacks: a labelled control whose
 *     value is `initialMarkdown` and whose edits call `onChange`, plus a second labelled
 *     control that reports a selection through `onSelectionChange` (DoD-2 / DoD-6 / DoD-8
 *     all need it). ProseMirror is never driven under jsdom — the feature's recorded
 *     testing decision. Each MOUNT appends its `initialMarkdown` to a log, which is how
 *     DoD-5 observes the generation counter BEHAVIOURALLY rather than by name;
 *   - `contentSubject.ts`, `chapterUndo.ts` and `restoreBuffer.ts` are used REAL: frames
 *     are delivered by calling the real `dispatchCanvasFrame`, which is what makes DoD-1's
 *     registration assertion mean something;
 *   - for DoD-9 the turn's transport is doubled BELOW `api/chats` (`api/sse.streamPost`,
 *     which owns the AbortController), so the assertion is about the REQUEST BODY the app
 *     actually posts — no real stream is opened and `support/sseFixture.ts` is not used;
 *   - `api/client` keeps its real `ApiError` while `request` / `refreshAuthToken` are
 *     stubbed, so nothing reaches the network.
 * `tests/setup.ts` clears `localStorage` globally; the undo stacks are module-level and
 * are cleared here between cases.
 *
 * Queries are by ROLE or LABEL only — no test ids, nothing asserted about colour or DOM
 * shape. `globals: false`: every primitive is imported explicitly.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { runInAction } from "mobx";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { Route, Routes } from "react-router-dom";
import type { ChangeEvent } from "react";
import type {
  ChapterAuthorPromptResponse,
  ChapterLifecycleState,
  ChapterResponse,
  ChapterTextResponse,
} from "../../src/types/chapters";
import type {
  CanvasFrame,
  CanvasOp,
  ChatResponse,
  ChatSamplingParams,
  TurnRequest,
} from "../../src/types/chats";
import type { SSEHandlers } from "../../src/api/sse";
import * as sse from "../../src/api/sse";
import * as client from "../../src/api/client";
import * as chaptersApi from "../../src/api/chapters";
import {
  currentContentSelection,
  currentContentSubject,
  dispatchCanvasFrame,
} from "../../src/work/contentSubject";
import {
  chapterUndoDepth,
  clearChapterUndo,
  popChapterUndoSnapshot,
  pushChapterUndoSnapshot,
} from "../../src/work/chapterUndo";
import { readBuffer, restoreBufferKey } from "../../src/work/restoreBuffer";
import {
  ChatPaneState,
  retryChatTurn,
  sendChatTurn,
} from "../../src/work/components/chat/chatPaneState";
import { ChapterPage } from "../../src/work/pages/ChapterPage";
import { renderWithProviders } from "../support/render";

// A module-factory mock replaces the WHOLE module: all TEN frozen exports of
// `api/chapters` are enumerated, including the ones this file never calls.
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
 * The editor stub, over the frozen four-prop seam. Two labelled controls:
 *   - the body control — accessible name `ariaLabel`, value `initialMarkdown`, edits call
 *     `onChange` (an author's keystroke);
 *   - the selection control — accessible name `<ariaLabel> selection`, whose value is
 *     reported through `onSelectionChange` (the author moving the caret / selecting).
 *     The frozen seam reports an EMPTY selection as `""`, so `""` is drivable too.
 * Each MOUNT appends the `initialMarkdown` it was given to a log on `globalThis` (the
 * factory is hoisted above every import, so it may not close over a module-level binding).
 */
vi.mock("../../src/work/components/chapter/ChapterBodyEditor", async () => {
  const { createElement, Fragment, useRef } = await import("react");

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
    return createElement(
      Fragment,
      null,
      createElement("textarea", {
        key: "body",
        "aria-label": props.ariaLabel,
        value: props.initialMarkdown,
        onChange: (event: ChangeEvent<HTMLTextAreaElement>) => props.onChange(event.target.value),
      }),
      createElement("textarea", {
        key: "selection",
        "aria-label": `${props.ariaLabel} selection`,
        onChange: (event: ChangeEvent<HTMLTextAreaElement>) =>
          props.onSelectionChange(event.target.value),
      }),
    );
  }

  return { ChapterBodyEditor };
});

// BELOW `api/chats` (which stays REAL, so the posted body is the real one): the stream
// transport. `streamPost` owns the AbortController — the frozen seam — so the turn request
// is observable without a stream ever being opened.
vi.mock("../../src/api/sse", () => ({
  streamPost: vi.fn(),
}));

// `request` / `refreshAuthToken` are stubbed so no case reaches the network; everything
// else (notably the real `ApiError` class) is the actual module.
vi.mock("../../src/api/client", async () => {
  const actual = await vi.importActual<typeof import("../../src/api/client")>(
    "../../src/api/client",
  );
  return { ...actual, request: vi.fn(), refreshAuthToken: vi.fn(async () => {}) };
});

/* ----------------------------------------------------------------------- fixtures */

const BOOK_ID = "bk-77";
const CHAPTER_ID = "ch-42";
const CHAPTER_ROUTE = `/${BOOK_ID}/chapter/${CHAPTER_ID}`;
const CHAT_ID = "c-1";

const CHAPTER_TITLE = "The Long Road";
const STORED_PROMPT = "Write in close third person, past tense.";
const STORED_BODY = "The road bends east at dusk, and the horses know it.";

/** The version the BODY response carries (step 006: the save's base comes from here). */
const BODY_VERSION = 4;
/** 014's chapter response version — deliberately different, and never the save's base. */
const CHAPTER_VERSION = 99;

/** What the assistant writes, per operation. */
const ASSISTANT_WHOLE = "A different road entirely, and no horses at all.";
const ASSISTANT_TAIL = " Behind them, the lanterns went out one by one.";
const ASSISTANT_REPLACEMENT = "the horses refuse it.";

/** A phrase that occurs exactly once in the stored body. */
const SELECTED = "the horses know it.";
/** A second, distinct selection — used to prove the registry follows the caret. */
const OTHER_SELECTION = "bends east at dusk";

/** The frozen accessible names (status.md -> step 006 and step 012). */
const EDITOR_LABEL = "Chapter body";
const SELECTION_LABEL = `${EDITOR_LABEL} selection`;
const SAVE_LABEL = "Save body";
const UNDO_LABEL = "Undo the assistant's last write";
const UNAPPLIED_TITLE = "The assistant's write was not applied";

/** The three states in which a chapter body is read-only (D16). */
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
    ...overrides,
  };
}

function makePrompt(): ChapterAuthorPromptResponse {
  return {
    chapter_id: CHAPTER_ID,
    system_prompt: STORED_PROMPT,
    modified_at: "2026-07-01T12:00:00Z",
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

/** A canvas frame for THIS chapter's body, unless overridden. */
function makeFrame(overrides: Partial<CanvasFrame> = {}): CanvasFrame {
  return {
    subject_kind: "chapter",
    subject_id: CHAPTER_ID,
    field: "body",
    text: ASSISTANT_WHOLE,
    op: "replace",
    ...overrides,
  };
}

function makeSampling(): ChatSamplingParams {
  return {
    temperature: 0.8,
    top_p: 0.95,
    top_k: 40,
    repeat_penalty: 1.1,
    min_p: 0.05,
    max_tokens: null,
    seed: null,
    presence_penalty: 0,
    frequency_penalty: 0,
    enable_thinking: true,
  };
}

function makeChat(): ChatResponse {
  return {
    id: CHAT_ID,
    book_id: BOOK_ID,
    author_id: "u-1",
    title: "Chat one",
    llm_server_id: "s-1",
    model_name: "m-1",
    sampling: makeSampling(),
    archived: false,
    created_at: "2026-01-01T00:00:00Z",
    modified_at: "2026-01-01T00:00:00Z",
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
function renderPage(route: string = CHAPTER_ROUTE) {
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

/** Types into the mocked editor, exactly as an author's keystroke would. */
function typeBody(text: string): void {
  const editor = queryEditor();
  if (editor === null) throw new Error("no chapter-body editor is mounted");
  fireEvent.change(editor, { target: { value: text } });
}

/** Reports a selection through the editor's frozen `onSelectionChange` seam. */
function selectInEditor(text: string): void {
  const control = screen.getByRole("textbox", { name: SELECTION_LABEL });
  fireEvent.change(control, { target: { value: text } });
}

function querySaveControl(): HTMLElement | null {
  return screen.queryByRole("button", { name: SAVE_LABEL });
}

function saveControl(): HTMLElement {
  const control = querySaveControl();
  if (control === null) throw new Error("no save control is rendered for the chapter body");
  return control;
}

function queryUndoControl(): HTMLElement | null {
  return screen.queryByRole("button", { name: UNDO_LABEL });
}

function undoControl(): HTMLElement {
  const control = queryUndoControl();
  if (control === null) throw new Error("no undo control is rendered beside the body editor");
  return control;
}

/** The `initialMarkdown` the stub saw at each mount — one entry per mount. */
function editorMounts(): string[] {
  const holder = globalThis as unknown as { __chapterBodyEditorMounts?: string[] };
  holder.__chapterBodyEditorMounts = holder.__chapterBodyEditorMounts ?? [];
  return holder.__chapterBodyEditorMounts;
}

function chapterBufferKey(): string {
  return restoreBufferKey(BOOK_ID, "chapter", CHAPTER_ID);
}

/** One captured POST-and-stream, as the mocked `streamPost` received it. */
interface CapturedPost {
  url: string;
  body: TurnRequest;
  handlers: SSEHandlers;
}

const posts: CapturedPost[] = [];

function lastPost(): CapturedPost {
  if (posts.length === 0) throw new Error("no turn stream has been opened yet");
  return posts[posts.length - 1];
}

/** The body the app actually posted for the latest turn. */
function lastBody(): TurnRequest {
  return lastPost().body;
}

function lastRawBody(): Record<string, unknown> {
  return lastBody() as unknown as Record<string, unknown>;
}

/** Seed an active chat with a ready history and an idle turn (the shell's job in prod). */
function primeActiveChat(state: ChatPaneState): void {
  runInAction(() => {
    state.chats = [makeChat()];
    state.activeChatId = CHAT_ID;
    state.messages = [];
    state.messagesStatus = "ready";
    state.turnStatus = "idle";
    state.turnError = null;
    state.streamingContent = "";
    state.streamingThinking = "";
  });
}

/** Open a turn from a primed pane and return the pane state. */
async function openTurn(prompt = "Rewrite this paragraph"): Promise<ChatPaneState> {
  const state = new ChatPaneState();
  primeActiveChat(state);
  await sendChatTurn(state, BOOK_ID, prompt);
  return state;
}

/** No body write of any kind reached the server (D4 — nothing persists until the save). */
function expectNoWriteCall(): void {
  expect(vi.mocked(chaptersApi.updateChapterText)).not.toHaveBeenCalled();
}

beforeEach(() => {
  editorMounts().length = 0;
  posts.length = 0;
  localStorage.clear();
  clearChapterUndo(BOOK_ID, CHAPTER_ID);
  armLoads();

  // `restoreMocks` / `clearMocks` wipe implementations between tests — re-arm the two the
  // send path touches.
  vi.mocked(client.refreshAuthToken).mockImplementation(async () => {});
  vi.mocked(sse.streamPost).mockImplementation(
    (url: string, body: object, handlers: SSEHandlers) => {
      posts.push({ url, body: body as TurnRequest, handlers });
      return new AbortController();
    },
  );
});

afterEach(() => {
  clearChapterUndo(BOOK_ID, CHAPTER_ID);
  localStorage.clear();
});

/* --------------------------------------------- DoD-1 — registration as a WRITABLE target */

describe("the chapter page registers itself as a writable canvas target (DoD-1)", () => {
  it("DoD-1: registers the chapter as the content-pane subject WITH an apply-draft callback on mount", async () => {
    renderPage();
    await findEditor();

    // The subject half of the registration.
    await waitFor(() => {
      expect(currentContentSubject()?.kind).toBe("chapter");
    });
    expect(currentContentSubject()?.entityId).toBe(CHAPTER_ID);

    // The WRITABLE half: a frame for this chapter, delivered through the real dispatcher,
    // reaches the page's draft — which can only happen if an applier was registered.
    dispatchCanvasFrame(BOOK_ID, makeFrame({ text: ASSISTANT_WHOLE, op: "replace" }));

    await waitFor(() => {
      expect(editorValue()).toBe(ASSISTANT_WHOLE);
    });
  });

  it("DoD-1: unregisters on unmount, so a later frame no longer reaches the page", async () => {
    const page = renderPage();
    await findEditor();
    await waitFor(() => {
      expect(currentContentSubject()?.entityId).toBe(CHAPTER_ID);
    });

    page.unmount();

    expect(currentContentSubject()).toBeNull();
    // The frame now has no target at all; it is not applied to anything on screen.
    dispatchCanvasFrame(BOOK_ID, makeFrame({ text: ASSISTANT_WHOLE, op: "replace" }));
    expect(queryEditor()).toBeNull();
    expectNoWriteCall();
  });

  for (const state of NON_OPEN_STATES) {
    it(`DoD-1: a ${state} chapter registers a SUBJECT but offers no writable target`, async () => {
      armLoads({ state });

      renderPage();

      // Presence first: the chapter really is registered as the subject, so a turn about it
      // still names it.
      await waitFor(() => {
        expect(currentContentSubject()?.kind).toBe("chapter");
      });
      expect(currentContentSubject()?.entityId).toBe(CHAPTER_ID);
      await waitFor(() => {
        expect(pageText()).toContain(STORED_BODY);
      });

      // ...and only then: nothing writable. The assistant's text never lands in the body.
      dispatchCanvasFrame(BOOK_ID, makeFrame({ text: ASSISTANT_WHOLE, op: "replace" }));

      await waitFor(() => {
        expect(pageText()).toContain(STORED_BODY);
      });
      expect(pageText()).not.toContain(ASSISTANT_WHOLE);
      expect(queryEditor()).toBeNull();
      expectNoWriteCall();
    });
  }
});

/* ------------------------------------------------- DoD-2 — the three canvas operations */

describe("the three canvas operations reach the body draft (DoD-2)", () => {
  it("DoD-2: a `replace` frame sets the WHOLE body draft", async () => {
    renderPage();
    await findEditor();
    expect(editorValue()).toBe(STORED_BODY);

    dispatchCanvasFrame(BOOK_ID, makeFrame({ text: ASSISTANT_WHOLE, op: "replace" }));

    await waitFor(() => {
      expect(editorValue()).toBe(ASSISTANT_WHOLE);
    });
  });

  it("DoD-2: an `append` frame adds its text to the END of the draft, keeping what was there", async () => {
    renderPage();
    await findEditor();

    dispatchCanvasFrame(BOOK_ID, makeFrame({ text: ASSISTANT_TAIL, op: "append" }));

    await waitFor(() => {
      expect(editorValue()).toContain(ASSISTANT_TAIL);
    });
    const draft = editorValue();
    // The author's text is still there, first; the assistant's is at the end.
    expect(draft.startsWith(STORED_BODY)).toBe(true);
    expect(draft.endsWith(ASSISTANT_TAIL)).toBe(true);
  });

  it("DoD-2: a `replace_selection` frame replaces exactly the currently-selected text", async () => {
    renderPage();
    await findEditor();

    selectInEditor(SELECTED);
    dispatchCanvasFrame(
      BOOK_ID,
      makeFrame({ text: ASSISTANT_REPLACEMENT, op: "replace_selection" }),
    );

    await waitFor(() => {
      expect(editorValue()).toBe(STORED_BODY.replace(SELECTED, ASSISTANT_REPLACEMENT));
    });
    // Exactly the selection went — the rest of the body is untouched.
    expect(editorValue()).toContain("The road bends east at dusk");
    expect(editorValue()).not.toContain(SELECTED);
  });
});

/* ---------------------------------- DoD-3 — the pre-write snapshot, and what undo restores */

describe("every applied frame snapshots the PRE-WRITE draft first (DoD-3)", () => {
  const CASES: { op: CanvasOp; text: string }[] = [
    { op: "replace", text: ASSISTANT_WHOLE },
    { op: "append", text: ASSISTANT_TAIL },
    { op: "replace_selection", text: ASSISTANT_REPLACEMENT },
  ];

  for (const { op, text } of CASES) {
    it(`DoD-3: undo after a \`${op}\` frame restores exactly the text that was there before it`, async () => {
      renderPage();
      await findEditor();
      selectInEditor(SELECTED);

      const before = editorValue();
      expect(before).toBe(STORED_BODY);

      dispatchCanvasFrame(BOOK_ID, makeFrame({ text, op }));
      await waitFor(() => {
        expect(editorValue()).not.toBe(before);
      });

      fireEvent.click(undoControl());

      // Exactly the PRE-write draft. Applying before snapshotting would have stored the
      // post-write text and made this a no-op.
      await waitFor(() => {
        expect(editorValue()).toBe(before);
      });
    });
  }

  it("DoD-3: the snapshot is the author's own unsaved text, not the loaded body", async () => {
    renderPage();
    await findEditor();

    const typed = "A paragraph the author typed and never saved.";
    typeBody(typed);
    await waitFor(() => {
      expect(editorValue()).toBe(typed);
    });

    dispatchCanvasFrame(BOOK_ID, makeFrame({ text: ASSISTANT_WHOLE, op: "replace" }));
    await waitFor(() => {
      expect(editorValue()).toBe(ASSISTANT_WHOLE);
    });

    fireEvent.click(undoControl());

    await waitFor(() => {
      expect(editorValue()).toBe(typed);
    });
  });

  it("DoD-3: two assistant writes undo one at a time, most recent first", async () => {
    renderPage();
    await findEditor();

    dispatchCanvasFrame(BOOK_ID, makeFrame({ text: "first assistant pass", op: "replace" }));
    await waitFor(() => {
      expect(editorValue()).toBe("first assistant pass");
    });
    dispatchCanvasFrame(BOOK_ID, makeFrame({ text: "second assistant pass", op: "replace" }));
    await waitFor(() => {
      expect(editorValue()).toBe("second assistant pass");
    });

    fireEvent.click(undoControl());
    await waitFor(() => {
      expect(editorValue()).toBe("first assistant pass");
    });

    fireEvent.click(undoControl());
    await waitFor(() => {
      expect(editorValue()).toBe(STORED_BODY);
    });
  });
});

/* --------------------- DoD-4 — the draft-edit path is used, and the server is not touched */

describe("an applied frame is a draft edit and nothing else (DoD-4)", () => {
  it("DoD-4: the frame changes the draft AND writes the restore buffer, and no save call results", async () => {
    renderPage();
    await findEditor();

    dispatchCanvasFrame(BOOK_ID, makeFrame({ text: ASSISTANT_WHOLE, op: "replace" }));

    // Presence first: the draft really moved, and the buffer really was written.
    await waitFor(() => {
      expect(editorValue()).toBe(ASSISTANT_WHOLE);
    });
    await waitFor(() => {
      expect(readBuffer(chapterBufferKey())?.draft).toBe(ASSISTANT_WHOLE);
    });
    // The buffer's base version is the one the BODY response carried, as for any edit.
    expect(readBuffer(chapterBufferKey())?.baseVersion).toBe(BODY_VERSION);

    // ...and only then the negative: an assistant write reaches the server not at all.
    expectNoWriteCall();
  });

  it("DoD-4: the buffer record is indistinguishable from the one a keystroke writes", async () => {
    renderPage();
    await findEditor();

    dispatchCanvasFrame(BOOK_ID, makeFrame({ text: ASSISTANT_WHOLE, op: "replace" }));
    await waitFor(() => {
      expect(readBuffer(chapterBufferKey())?.draft).toBe(ASSISTANT_WHOLE);
    });
    const viaCanvas = {
      draft: readBuffer(chapterBufferKey())?.draft,
      baseVersion: readBuffer(chapterBufferKey())?.baseVersion,
    };

    // The very same text, typed by the author instead.
    typeBody(ASSISTANT_WHOLE);
    await waitFor(() => {
      expect(readBuffer(chapterBufferKey())?.draft).toBe(ASSISTANT_WHOLE);
    });
    const viaKeystroke = {
      draft: readBuffer(chapterBufferKey())?.draft,
      baseVersion: readBuffer(chapterBufferKey())?.baseVersion,
    };

    expect(viaCanvas).toEqual(viaKeystroke);
    expectNoWriteCall();
  });
});

/* ---------------------------------------------- DoD-5 — the editor re-syncs by REMOUNT */

describe("the editor remounts on external draft writes only (DoD-5)", () => {
  it("DoD-5: an applied frame remounts the editor on the NEW draft — D15", async () => {
    renderPage();
    await findEditor();
    await waitFor(() => {
      expect(editorMounts()).toEqual([STORED_BODY]);
    });

    dispatchCanvasFrame(BOOK_ID, makeFrame({ text: ASSISTANT_WHOLE, op: "replace" }));

    await waitFor(() => {
      expect(editorMounts()).toHaveLength(2);
    });
    // It remounted holding the text the frame produced, not the one it replaced.
    expect(editorMounts()[1]).toBe(ASSISTANT_WHOLE);
  });

  it("DoD-5: an undo remounts the editor on the restored draft", async () => {
    renderPage();
    await findEditor();

    dispatchCanvasFrame(BOOK_ID, makeFrame({ text: ASSISTANT_WHOLE, op: "replace" }));
    await waitFor(() => {
      expect(editorMounts()).toHaveLength(2);
    });

    fireEvent.click(undoControl());

    await waitFor(() => {
      expect(editorMounts()).toHaveLength(3);
    });
    expect(editorMounts()[2]).toBe(STORED_BODY);
  });

  it("DoD-5: a keystroke does NOT remount the editor — it originates inside it", async () => {
    renderPage();
    await findEditor();
    await waitFor(() => {
      expect(editorMounts()).toEqual([STORED_BODY]);
    });

    typeBody("a keystroke");

    await waitFor(() => {
      expect(editorValue()).toBe("a keystroke");
    });
    expect(editorMounts()).toEqual([STORED_BODY]);
  });
});

/* ---------------------------- DoD-6 — a selection frame with no selection is REFUSED */

describe("a replace-selection frame with no active selection changes nothing (DoD-6)", () => {
  const ORPHAN_TEXT = "a sentence nobody chose a place for";

  it("DoD-6: it is reported to the author, and the draft is byte-identical", async () => {
    renderPage();
    await findEditor();
    expect(editorValue()).toBe(STORED_BODY);

    dispatchCanvasFrame(BOOK_ID, makeFrame({ text: ORPHAN_TEXT, op: "replace_selection" }));

    // Presence first: the report the author reads, carrying the refused text verbatim.
    await screen.findByText(UNAPPLIED_TITLE);
    expect(pageText()).toContain(ORPHAN_TEXT);

    // ...and only then the negatives. Nothing changed, and nothing was placed anywhere.
    expect(editorValue()).toBe(STORED_BODY);
    expect(editorValue()).not.toContain(ORPHAN_TEXT);
    // Never appended...
    expect(editorValue().endsWith(ORPHAN_TEXT)).toBe(false);
    // ...and never applied at position zero.
    expect(editorValue().startsWith(ORPHAN_TEXT)).toBe(false);
    expectNoWriteCall();
  });

  it("DoD-6: a selection the author cleared while the model was writing is still no selection", async () => {
    renderPage();
    await findEditor();

    // The author selects, then clears the selection — the seam reports `""`.
    selectInEditor(SELECTED);
    selectInEditor("");

    dispatchCanvasFrame(BOOK_ID, makeFrame({ text: ORPHAN_TEXT, op: "replace_selection" }));

    await screen.findByText(UNAPPLIED_TITLE);
    expect(pageText()).toContain(ORPHAN_TEXT);
    expect(editorValue()).toBe(STORED_BODY);
    expect(editorValue().startsWith(ORPHAN_TEXT)).toBe(false);
    expect(editorValue().endsWith(ORPHAN_TEXT)).toBe(false);
  });

  it("DoD-6: the refusal leaves the editor unremounted and the undo stack untouched", async () => {
    renderPage();
    await findEditor();
    await waitFor(() => {
      expect(editorMounts()).toEqual([STORED_BODY]);
    });

    dispatchCanvasFrame(BOOK_ID, makeFrame({ text: ORPHAN_TEXT, op: "replace_selection" }));

    await screen.findByText(UNAPPLIED_TITLE);
    // Nothing was changed, so there is nothing to undo and nothing to re-render from.
    expect(editorMounts()).toEqual([STORED_BODY]);
    expect(chapterUndoDepth(BOOK_ID, CHAPTER_ID)).toBe(0);
  });
});

/* --------------------------------------------------- DoD-7 — the undo control's depth */

describe("the undo control and the 20-deep stack (DoD-7)", () => {
  it("DoD-7: the control is available after an assistant write and unavailable when the stack is empty", async () => {
    renderPage();
    await findEditor();

    // Presence first: after ONE assistant write the control is there and usable.
    dispatchCanvasFrame(BOOK_ID, makeFrame({ text: ASSISTANT_WHOLE, op: "replace" }));
    await waitFor(() => {
      expect(undoControl()).toBeEnabled();
    });

    // Undoing it empties the stack, and the control is then unavailable.
    fireEvent.click(undoControl());
    await waitFor(() => {
      expect(editorValue()).toBe(STORED_BODY);
    });
    await waitFor(() => {
      expect(undoControl()).toBeDisabled();
    });
  });

  it("DoD-7: the control is unavailable before any assistant write", async () => {
    renderPage();
    await findEditor();

    // The control exists beside the save control...
    expect(saveControl()).not.toBeNull();
    expect(undoControl()).toBeInTheDocument();
    // ...and offers nothing, because nothing has been written.
    expect(undoControl()).toBeDisabled();
  });

  it("DoD-7: after 20 assistant writes only the most recent 20 states are reachable — D6", () => {
    // Driven through the module: 21 snapshots for one (book, chapter) pair.
    for (let i = 1; i <= 21; i += 1) {
      pushChapterUndoSnapshot(BOOK_ID, CHAPTER_ID, `state ${i}`);
    }

    expect(chapterUndoDepth(BOOK_ID, CHAPTER_ID)).toBe(20);

    // The 20 most recent come back, newest first...
    const reachable: (string | null)[] = [];
    for (let i = 0; i < 20; i += 1) {
      reachable.push(popChapterUndoSnapshot(BOOK_ID, CHAPTER_ID));
    }
    expect(reachable[0]).toBe("state 21");
    expect(reachable[19]).toBe("state 2");
    // ...and the oldest was dropped to make room, not kept.
    expect(reachable).not.toContain("state 1");

    // Nothing beyond the twentieth is reachable.
    expect(chapterUndoDepth(BOOK_ID, CHAPTER_ID)).toBe(0);
    expect(popChapterUndoSnapshot(BOOK_ID, CHAPTER_ID)).toBeNull();
  });
});

/* ------------------------------------- DoD-8 — the selection registry follows the caret */

describe("moving the selection updates the module-level registry (DoD-8)", () => {
  it("DoD-8: the current selection is what the editor last reported", async () => {
    renderPage();
    await findEditor();

    selectInEditor(SELECTED);
    await waitFor(() => {
      expect(currentContentSelection()).toBe(SELECTED);
    });

    // The author moves the selection.
    selectInEditor(OTHER_SELECTION);
    await waitFor(() => {
      expect(currentContentSelection()).toBe(OTHER_SELECTION);
    });
  });

  it("DoD-8: an emptied selection registers as no selection at all", async () => {
    renderPage();
    await findEditor();

    selectInEditor(SELECTED);
    await waitFor(() => {
      expect(currentContentSelection()).toBe(SELECTED);
    });

    selectInEditor("");

    await waitFor(() => {
      expect(currentContentSelection()).toBeNull();
    });
  });

  it("DoD-8: leaving the page clears the selection", async () => {
    const page = renderPage();
    await findEditor();

    selectInEditor(SELECTED);
    await waitFor(() => {
      expect(currentContentSelection()).toBe(SELECTED);
    });

    page.unmount();

    expect(currentContentSelection()).toBeNull();
  });
});

/* ------------------------------------ DoD-9 — the selection rides the turn as a flat field */

describe("a turn carries the current selection as a FLAT field (DoD-9)", () => {
  it("DoD-9: the request body carries `selection_text` beside the subject fields, and is flat", async () => {
    renderPage();
    await findEditor();
    selectInEditor(SELECTED);
    await waitFor(() => {
      expect(currentContentSelection()).toBe(SELECTED);
    });

    await openTurn("rewrite this as a threat");

    const body = lastBody();
    expect(body.selection_text).toBe(SELECTED);
    // Beside the subject fields, not inside them.
    expect(body.subject_kind).toBe("chapter");
    expect(body.subject_id).toBe(CHAPTER_ID);

    const raw = lastRawBody();
    expect(Object.keys(raw)).toContain("selection_text");
    expect(Object.keys(raw)).not.toContain("subject");
    // No nested object anywhere on the request: every field is flat, as the wire is.
    for (const [key, value] of Object.entries(raw)) {
      expect(`${key} is an object: ${typeof value === "object" && value !== null}`).toBe(
        `${key} is an object: false`,
      );
    }
  });

  it("DoD-9: a turn sent with nothing selected carries no selection at all", async () => {
    renderPage();
    await findEditor();

    // Presence first: the subject IS on the request, so the absence below is about the
    // selection and not about a turn that carried nothing.
    await openTurn("what happens next?");
    expect(lastBody().subject_kind).toBe("chapter");
    expect(lastBody().subject_id).toBe(CHAPTER_ID);

    expect(Object.keys(lastRawBody())).not.toContain("selection_text");
    expect(lastBody().selection_text ?? null).toBeNull();
  });

  it("DoD-9: the selection is read at SEND time — the pane holds no copy of its own", async () => {
    renderPage();
    await findEditor();

    selectInEditor(SELECTED);
    const state = new ChatPaneState();
    primeActiveChat(state);
    await sendChatTurn(state, BOOK_ID, "first");
    expect(lastBody().selection_text).toBe(SELECTED);

    // The author moves the selection; the SAME pane sends again.
    selectInEditor(OTHER_SELECTION);
    runInAction(() => {
      state.turnStatus = "idle";
      state.streamingContent = "";
      state.streamingThinking = "";
    });
    await sendChatTurn(state, BOOK_ID, "second");

    expect(posts).toHaveLength(2);
    expect(lastBody().selection_text).toBe(OTHER_SELECTION);
  });

  it("DoD-9: a retry carries the selection as it is at RETRY time", async () => {
    renderPage();
    await findEditor();

    selectInEditor(SELECTED);
    const state = await openTurn("first attempt");
    expect(lastBody().selection_text).toBe(SELECTED);

    selectInEditor(OTHER_SELECTION);
    runInAction(() => {
      state.turnStatus = "error";
      state.turnError = "boom";
    });

    await retryChatTurn(state, BOOK_ID);

    expect(posts).toHaveLength(2);
    expect(lastBody().selection_text).toBe(OTHER_SELECTION);
  });

  it("DoD-9: with no chapter page in view the request has neither subject nor selection", async () => {
    // No content page is mounted at all — the shell before any subject loads.
    await openTurn("hello");

    expect(Object.keys(lastRawBody())).toEqual(["prompt"]);
    expect(lastBody().prompt).toBe("hello");
  });

  it("DoD-9 (the DTO twin): the selection is declarable beside the three subject fields, and is optional", () => {
    // Compile-level regression guard for `TurnRequest`'s frozen shape: the selection is a
    // FLAT optional field on the request — `npm run test:types` is the real gate.
    const withSelection: TurnRequest = {
      prompt: "rewrite this",
      subject_kind: "chapter",
      subject_id: CHAPTER_ID,
      selection_text: SELECTED,
    };
    const withoutSelection: TurnRequest = { prompt: "rewrite this" };

    expect(withSelection.selection_text).toBe(SELECTED);
    expect(withSelection.subject_kind).toBe("chapter");
    expect(withoutSelection.selection_text ?? null).toBeNull();
  });
});

/* ----------------------------------------------- DoD-10 — the selection is never saved */

describe("the selection never reaches the server (DoD-10)", () => {
  it("DoD-10: applying frames and moving selections produce no write call", async () => {
    renderPage();
    await findEditor();

    // Presence first: there IS a selection, and a frame WAS applied.
    selectInEditor(SELECTED);
    await waitFor(() => {
      expect(currentContentSelection()).toBe(SELECTED);
    });
    dispatchCanvasFrame(
      BOOK_ID,
      makeFrame({ text: ASSISTANT_REPLACEMENT, op: "replace_selection" }),
    );
    await waitFor(() => {
      expect(editorValue()).toBe(STORED_BODY.replace(SELECTED, ASSISTANT_REPLACEMENT));
    });
    selectInEditor(OTHER_SELECTION);
    await waitFor(() => {
      expect(currentContentSelection()).toBe(OTHER_SELECTION);
    });

    // ...and only then the negative.
    expectNoWriteCall();
  });

  it("DoD-10: a subsequent body save sends only the text and the version", async () => {
    const expected = STORED_BODY.replace(SELECTED, ASSISTANT_REPLACEMENT);
    vi.mocked(chaptersApi.updateChapterText).mockResolvedValue(
      makeBody({ text: expected, version: BODY_VERSION + 1 }),
    );

    renderPage();
    await findEditor();

    selectInEditor(SELECTED);
    await waitFor(() => {
      expect(currentContentSelection()).toBe(SELECTED);
    });
    dispatchCanvasFrame(
      BOOK_ID,
      makeFrame({ text: ASSISTANT_REPLACEMENT, op: "replace_selection" }),
    );
    await waitFor(() => {
      expect(editorValue()).toBe(expected);
    });

    fireEvent.click(saveControl());

    await waitFor(() => {
      expect(vi.mocked(chaptersApi.updateChapterText)).toHaveBeenCalledTimes(1);
    });
    const [bookId, chapterId, payload] = vi.mocked(chaptersApi.updateChapterText).mock.calls[0];
    expect(bookId).toBe(BOOK_ID);
    expect(chapterId).toBe(CHAPTER_ID);
    // Exactly the text and the version — the selection is not part of a save.
    expect(payload).toEqual({ text: expected, expected_version: BODY_VERSION });
  });
});
