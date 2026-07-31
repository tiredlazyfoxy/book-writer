/**
 * The gated chapter close on the working page — 016.chapter-close-continuity, DoD-9.
 *
 * The one cross-pane seam this feature adds: `work/closeTurn.ts`, the module-tier
 * registry that lets `ChapterPage`'s close and Stop controls reach the chat pane's
 * turn-posting logic without React context or a cross-page callback — the same shape
 * `contentSubject.ts` already uses for canvas writes.
 *
 * Bound to the frozen signatures in `status.md` -> `## Skeleton` (016), plus 014 / 015
 * pieces consumed unchanged:
 *   work/closeTurn:
 *     interface CloseTurnController { start(bookId, chapterId); stop();
 *                                     setActive({ bookId; chapterId } | null) }
 *     registerCloseTurnController(c) · unregisterCloseTurnController(c)
 *     requestCloseTurnStart(bookId, chapterId) · requestCloseTurnStop()
 *     markCloseTurnActive(bookId, chapterId) · clearCloseTurnActive()
 *     activeCloseTurn(): { bookId: string; chapterId: string } | null
 *   chatPaneState:
 *     class ChatPaneState implements CloseTurnController
 *       closeTurnActive: { bookId; chapterId } | null
 *       get isComposerReadOnly(): boolean · get composerReadOnlyReason(): string | null
 *       readonly start · readonly stop · readonly setActive
 *     startCloseTurn(state, bookId, chapterId, signal?): Promise<void>
 *     stopCloseTurn(state): void
 *   chapterPageState:
 *     type ChapterTransition = "open" | "close" | "reopen" | "cancel"
 *     class ChapterPageState { constructor(bookId, chapterId); … closeConfirmOpen;
 *                              get offeredTransition }
 *     requestChapterClose(state, bookId, chapterId, signal?): Promise<void>
 *     cancelChapterCloseRequest(state, bookId, chapterId, signal?): Promise<void>
 *   api/chapters: closeChapterState(bookId, chapterId, signal?) ·
 *                 cancelChapterClose(bookId, chapterId, signal?)
 *   api/chats: streamChatTurn(bookId, chatId, prompt, handlers, subject?, selectionText?)
 *   const ChapterPage: FunctionComponent   // observer, ZERO props; :bookId and :id
 *
 * Every expected value comes from the SPEC — `plan.md` -> Interface (`closeTurn.ts`,
 * `chatPaneState.ts`, `chapterPageState.ts`), DoD-9 and Decisions taken D4 / D5, and the
 * Skeleton record's divergence D-3 — never from the page's code:
 *   - the Close control asks for CONFIRMATION first: the click alone posts nothing
 *     (`plan.md` -> Implementation outline, "close confirm"; `context.md` -> "No
 *     confirmation dialog exists today (this feature adds one before `close`)");
 *   - a successful close request marks the close ACTIVE and asks the pane to post the
 *     turn (`requestChapterClose` -> `markCloseTurnActive` + `requestCloseTurnStart`);
 *   - the composer is read-only for the WHOLE `closing` window, driven by
 *     `activeCloseTurn()` and not by "a stream is running": the page's load path marks
 *     the signal active when the loaded chapter is `closing` and clears it otherwise, so
 *     a page RELOAD mid-close still renders the chat read-only with no stream open;
 *   - per Skeleton divergence D-3, `isComposerReadOnly` means "a close is active at
 *     all" — `ChatPaneState` holds no `bookId`, so nothing here asserts a book-id
 *     comparison;
 *   - Stop calls `close/cancel` (D4: a stop discards, and is the only exit from
 *     `closing` besides finalize), and a successful cancel clears the signal.
 *
 * Deliberately NOT asserted here (`plan.md` -> Test plan -> "Not tested"):
 * `api/continuity.ts` / `api/flags.ts` wrappers, `BookStatePage`'s read-only rendering,
 * and every badge / label map.
 *
 * Mocking follows the house rule — `api/` modules, never `fetch`. Each api module is
 * replaced by a module factory enumerating all its frozen exports, so an omitted one
 * cannot silently be `undefined`. `work/closeTurn.ts`, `chatPaneState.ts` and
 * `chapterPageState.ts` are used FOR REAL: they are the subject. The chapter body editor
 * is stubbed over its frozen four-prop seam (ProseMirror is never driven under jsdom).
 *
 * Queries are by ROLE or LABEL only. `globals: false`: every primitive is imported
 * explicitly.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { runInAction } from "mobx";
import { Route, Routes } from "react-router-dom";
import type { RenderResult } from "@testing-library/react";
import type { ChangeEvent } from "react";
import type {
  ChapterAuthorPromptResponse,
  ChapterLifecycleState,
  ChapterResponse,
  ChapterTextResponse,
} from "../../src/types/chapters";
import type { ChapterNoteChangesetResponse } from "../../src/types/continuity";
import type { ChatMessageResponse, ChatResponse } from "../../src/types/chats";
import type { TurnStreamHandlers } from "../../src/api/chats";
import { ApiError } from "../../src/api/client";
import * as chaptersApi from "../../src/api/chapters";
import * as chatsApi from "../../src/api/chats";
import * as flagsApi from "../../src/api/flags";
import * as continuityApi from "../../src/api/continuity";
import type { CloseTurnController } from "../../src/work/closeTurn";
import {
  activeCloseTurn,
  clearCloseTurnActive,
  markCloseTurnActive,
  registerCloseTurnController,
  requestCloseTurnStart,
  requestCloseTurnStop,
  unregisterCloseTurnController,
} from "../../src/work/closeTurn";
import {
  ChatPaneState,
  startCloseTurn,
  stopCloseTurn,
} from "../../src/work/components/chat/chatPaneState";
import {
  ChapterPageState,
  cancelChapterCloseRequest,
  requestChapterClose,
} from "../../src/work/pages/chapterPageState";
import { ChapterPage } from "../../src/work/pages/ChapterPage";
import { renderWithProviders } from "../support/render";

/* -------------------------------------------------------------------- api mocks */

// All FOURTEEN frozen exports of `api/chapters`: 014's eight, 015/004's five, and this
// feature's `cancelChapterClose`.
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
  cancelChapterClose: vi.fn(),
}));

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

vi.mock("../../src/api/chats", () => ({
  listChats: vi.fn(),
  createChat: vi.fn(),
  updateChat: vi.fn(),
  getChat: vi.fn(),
  listModelOptions: vi.fn(),
  streamChatTurn: vi.fn(),
}));

/** The editor stub over the frozen four-prop seam. */
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
const CHAT_ID = "c-1";
const CHAPTER_ROUTE = `/${BOOK_ID}/chapter/${CHAPTER_ID}`;
const CHAPTER_TITLE = "The Long Road";
const STORED_BODY = "The road bends east at dusk, and the horses know it.";

function makeChapter(overrides: Partial<ChapterResponse> = {}): ChapterResponse {
  return {
    id: CHAPTER_ID,
    book_id: BOOK_ID,
    ordinal: 7,
    title: CHAPTER_TITLE,
    state: "open",
    sketch: "A road, a river, and a rumour of war.",
    version: 99,
    created_at: "2026-01-02T08:00:00Z",
    modified_at: "2026-03-04T09:00:00Z",
    summary: null,
    summary_status: null,
    ...overrides,
  };
}

function makePrompt(): ChapterAuthorPromptResponse {
  return {
    chapter_id: CHAPTER_ID,
    system_prompt: "Write in close third person, past tense.",
    modified_at: "2026-07-01T12:00:00Z",
  };
}

function makeBody(state: ChapterLifecycleState): ChapterTextResponse {
  return {
    chapter_id: CHAPTER_ID,
    state,
    text: STORED_BODY,
    version: 4,
    modified_at: "2026-07-20T10:00:00Z",
  };
}

function makeChangeset(): ChapterNoteChangesetResponse {
  return {
    chapter_id: CHAPTER_ID,
    added: "",
    modified: "",
    deleted: "",
    status: null,
    created_at: null,
    modified_at: null,
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
    sampling: {
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
    },
    archived: false,
    created_at: "2026-01-01T00:00:00Z",
    modified_at: "2026-01-01T00:00:00Z",
  };
}

/* ------------------------------------------------------------------------ harness */

/** A recording stand-in for whatever the chat pane registers. */
function makeController(): CloseTurnController & {
  starts: Array<{ bookId: string; chapterId: string }>;
  stops: number;
  actives: Array<{ bookId: string; chapterId: string } | null>;
} {
  const starts: Array<{ bookId: string; chapterId: string }> = [];
  const actives: Array<{ bookId: string; chapterId: string } | null> = [];
  let stops = 0;
  return {
    starts,
    actives,
    get stops() {
      return stops;
    },
    start(bookId: string, chapterId: string) {
      starts.push({ bookId, chapterId });
    },
    stop() {
      stops += 1;
    },
    setActive(active: { bookId: string; chapterId: string } | null) {
      actives.push(active);
    },
  };
}

/** One opened turn, as the mocked `streamChatTurn` received it. */
interface CapturedTurn {
  bookId: string;
  chatId: string;
  prompt: string | null;
  handlers: TurnStreamHandlers;
  subject: unknown;
  controller: AbortController;
}

function installTurns(): CapturedTurn[] {
  const turns: CapturedTurn[] = [];
  vi.mocked(chatsApi.streamChatTurn).mockImplementation(
    async (bookId, chatId, prompt, handlers, subject?) => {
      const controller = new AbortController();
      vi.spyOn(controller, "abort");
      turns.push({ bookId, chatId, prompt, handlers, subject, controller });
      return controller;
    },
  );
  return turns;
}

/** Seed an active chat with a ready history and an idle turn. */
function primeActiveChat(state: ChatPaneState, messages: ChatMessageResponse[] = []): void {
  const chat = makeChat();
  runInAction(() => {
    state.chats = [chat];
    state.activeChatId = CHAT_ID;
    state.messages = messages;
    state.messagesStatus = "ready";
    state.turnStatus = "idle";
    state.turnError = null;
    state.streamingContent = "";
    state.streamingThinking = "";
  });
}

/** Arms every read the chapter page issues on mount, with the chapter in `state`. */
function armLoads(state: ChapterLifecycleState): void {
  vi.mocked(chaptersApi.getChapter).mockResolvedValue(makeChapter({ state }));
  vi.mocked(chaptersApi.getOwnChapterSystemPrompt).mockResolvedValue(makePrompt());
  vi.mocked(chaptersApi.getChapterText).mockResolvedValue(makeBody(state));
  vi.mocked(flagsApi.listFlags).mockResolvedValue({ items: [] });
  vi.mocked(continuityApi.getChapterChangeset).mockResolvedValue(makeChangeset());
}

function renderPage(): RenderResult {
  return renderWithProviders(
    <Routes>
      <Route path="/:bookId/chapter/:id" element={<ChapterPage />} />
    </Routes>,
    { route: CHAPTER_ROUTE },
  );
}

/**
 * Every transition control currently offered. 014/015 froze the accessible name as
 * `<Action> chapter: <title>`; this matches the shape without pinning the verb, so the
 * assertion is about WHICH endpoint the one offered control calls.
 */
function transitionControls(): HTMLElement[] {
  return screen.queryAllByRole("button", { name: new RegExp(`chapter: ${CHAPTER_TITLE}$`) });
}

async function findTheOneTransitionControl(): Promise<HTMLElement> {
  await waitFor(() => {
    expect(transitionControls()).toHaveLength(1);
  });
  return transitionControls()[0];
}

/** Harness hygiene: the module's signal and registration are module-level. */
const RESET_CONTROLLER: CloseTurnController = {
  start: () => {},
  stop: () => {},
  setActive: () => {},
};

function resetCloseTurn(): void {
  try {
    registerCloseTurnController(RESET_CONTROLLER);
    clearCloseTurnActive();
    unregisterCloseTurnController(RESET_CONTROLLER);
  } catch {
    /* the module is unavailable; the cases below say so themselves */
  }
}

beforeEach(() => {
  resetCloseTurn();
  vi.mocked(chaptersApi.closeChapterState).mockResolvedValue(makeChapter({ state: "closing" }));
  vi.mocked(chaptersApi.cancelChapterClose).mockResolvedValue(makeChapter({ state: "open" }));
  vi.mocked(chatsApi.getChat).mockResolvedValue({ chat: makeChat(), messages: [] });
  armLoads("open");
});

afterEach(resetCloseTurn);

/* ------------------------------------------- DoD-9 — the close-in-progress signal */

describe("closeTurn.ts carries the close-in-progress signal (DoD-9)", () => {
  it("DoD-9: the signal is readable with NO controller registered — mount order cannot lose it", () => {
    // The reload case: the page loads before the chat pane has registered anything.
    expect(activeCloseTurn()).toBeNull();

    markCloseTurnActive(BOOK_ID, CHAPTER_ID);

    expect(activeCloseTurn()).toEqual({ bookId: BOOK_ID, chapterId: CHAPTER_ID });

    clearCloseTurnActive();

    expect(activeCloseTurn()).toBeNull();
  });

  it("DoD-9: marking active reaches a registered controller SYNCHRONOUSLY, in the same tick", () => {
    const controller = makeController();
    registerCloseTurnController(controller);

    markCloseTurnActive(BOOK_ID, CHAPTER_ID);

    // No await, no flush: the pane's own observable changed in the same tick.
    expect(controller.actives).toEqual([{ bookId: BOOK_ID, chapterId: CHAPTER_ID }]);
    expect(activeCloseTurn()).toEqual({ bookId: BOOK_ID, chapterId: CHAPTER_ID });

    clearCloseTurnActive();

    expect(controller.actives).toEqual([{ bookId: BOOK_ID, chapterId: CHAPTER_ID }, null]);
    expect(activeCloseTurn()).toBeNull();

    unregisterCloseTurnController(controller);
  });

  it("DoD-9: start and stop requests reach the registered controller with the book and chapter", () => {
    const controller = makeController();
    registerCloseTurnController(controller);

    requestCloseTurnStart(BOOK_ID, CHAPTER_ID);
    expect(controller.starts).toEqual([{ bookId: BOOK_ID, chapterId: CHAPTER_ID }]);

    requestCloseTurnStop();
    expect(controller.stops).toBe(1);

    unregisterCloseTurnController(controller);
  });

  it("DoD-9: with no controller registered a start or stop request is a no-op, never a throw", () => {
    expect(() => requestCloseTurnStart(BOOK_ID, CHAPTER_ID)).not.toThrow();
    expect(() => requestCloseTurnStop()).not.toThrow();
    // ...and neither one invents a signal of its own.
    expect(activeCloseTurn()).toBeNull();
  });
});

/* ------------------------------ DoD-9 — the composer is read-only for the window */

describe("the chat composer is read-only while a close is active (DoD-9)", () => {
  it("DoD-9: the pane is writable until the signal is set, read-only with a stated reason while it is, and writable again once cleared", () => {
    const pane = new ChatPaneState();
    registerCloseTurnController(pane);

    // Presence first: nothing is read-only to begin with.
    expect(pane.isComposerReadOnly).toBe(false);
    expect(pane.composerReadOnlyReason).toBeNull();

    markCloseTurnActive(BOOK_ID, CHAPTER_ID);

    // Driven by the SIGNAL — no turn has been posted and no stream is open.
    expect(pane.isComposerReadOnly).toBe(true);
    expect(typeof pane.composerReadOnlyReason).toBe("string");
    expect((pane.composerReadOnlyReason ?? "").trim()).not.toBe("");
    expect(vi.mocked(chatsApi.streamChatTurn)).not.toHaveBeenCalled();

    clearCloseTurnActive();

    expect(pane.isComposerReadOnly).toBe(false);
    expect(pane.composerReadOnlyReason).toBeNull();

    unregisterCloseTurnController(pane);
  });
});

/* --------------------------------------------- DoD-9 — the pane posts the turn */

describe("the pane posts the close turn on the chapter (DoD-9)", () => {
  it("DoD-9: startCloseTurn opens a turn on the book's chat, subject to the CHAPTER being closed", async () => {
    const pane = new ChatPaneState();
    primeActiveChat(pane);
    const turns = installTurns();

    await startCloseTurn(pane, BOOK_ID, CHAPTER_ID);

    await waitFor(() => {
      expect(turns).toHaveLength(1);
    });
    expect(turns[0].bookId).toBe(BOOK_ID);
    expect(turns[0].chatId).toBe(CHAT_ID);
    // A synthetic prompt is posted — a close turn is an ordinary turn (D1/D5).
    expect(typeof turns[0].prompt).toBe("string");
    expect((turns[0].prompt ?? "").trim()).not.toBe("");
    // ...carrying the chapter as the turn's subject, which is what resolves the
    // `close-chapter` mode server-side.
    expect(turns[0].subject).toMatchObject({
      subject_kind: "chapter",
      subject_id: CHAPTER_ID,
    });
  });

  it("DoD-9: the turn ending — by done or by error — clears the close-in-progress signal", async () => {
    for (const ending of ["done", "error"] as const) {
      resetCloseTurn();
      vi.mocked(chatsApi.streamChatTurn).mockReset();

      const pane = new ChatPaneState();
      primeActiveChat(pane);
      registerCloseTurnController(pane);
      const turns = installTurns();

      markCloseTurnActive(BOOK_ID, CHAPTER_ID);
      await startCloseTurn(pane, BOOK_ID, CHAPTER_ID);
      await waitFor(() => {
        expect(turns).toHaveLength(1);
      });
      // Presence first: the close really is active while the turn runs.
      expect(activeCloseTurn()).toEqual({ bookId: BOOK_ID, chapterId: CHAPTER_ID });

      if (ending === "done") turns[0].handlers.onDone();
      else turns[0].handlers.onError("the model stopped answering");

      await waitFor(() => {
        expect(activeCloseTurn()).toBeNull();
      });
      expect(pane.isComposerReadOnly).toBe(false);

      unregisterCloseTurnController(pane);
    }
  });

  it("DoD-9: stopCloseTurn aborts the stream the pane opened", async () => {
    const pane = new ChatPaneState();
    primeActiveChat(pane);
    const turns = installTurns();

    await startCloseTurn(pane, BOOK_ID, CHAPTER_ID);
    await waitFor(() => {
      expect(turns).toHaveLength(1);
    });

    stopCloseTurn(pane);

    expect(turns[0].controller.abort).toHaveBeenCalled();
  });
});

/* -------------------------- DoD-9 — the page's close and cancel effects, wired */

describe("the chapter page's close and cancel effects drive the signal (DoD-9)", () => {
  it("DoD-9: a successful close request posts to close, marks the close active and asks the pane to start the turn", async () => {
    const controller = makeController();
    registerCloseTurnController(controller);
    const state = new ChapterPageState(BOOK_ID, CHAPTER_ID);

    await requestChapterClose(state, BOOK_ID, CHAPTER_ID);

    expect(vi.mocked(chaptersApi.closeChapterState)).toHaveBeenCalledTimes(1);
    const call = vi.mocked(chaptersApi.closeChapterState).mock.calls[0];
    expect(call[0]).toBe(BOOK_ID);
    expect(call[1]).toBe(CHAPTER_ID);

    expect(activeCloseTurn()).toEqual({ bookId: BOOK_ID, chapterId: CHAPTER_ID });
    expect(controller.starts).toEqual([{ bookId: BOOK_ID, chapterId: CHAPTER_ID }]);

    unregisterCloseTurnController(controller);
  });

  it("DoD-9: a REFUSED close request neither marks the close active nor starts a turn", async () => {
    const controller = makeController();
    registerCloseTurnController(controller);
    vi.mocked(chaptersApi.closeChapterState).mockRejectedValue(
      new ApiError(403, "Only the book's owner can close a chapter."),
    );
    const state = new ChapterPageState(BOOK_ID, CHAPTER_ID);

    await requestChapterClose(state, BOOK_ID, CHAPTER_ID);

    expect(vi.mocked(chaptersApi.closeChapterState)).toHaveBeenCalledTimes(1);
    expect(activeCloseTurn()).toBeNull();
    expect(controller.starts).toEqual([]);

    unregisterCloseTurnController(controller);
  });

  it("DoD-9: a successful cancel posts to close/cancel, clears the signal and asks the pane to stop — D4", async () => {
    const controller = makeController();
    registerCloseTurnController(controller);
    markCloseTurnActive(BOOK_ID, CHAPTER_ID);
    const state = new ChapterPageState(BOOK_ID, CHAPTER_ID);

    await cancelChapterCloseRequest(state, BOOK_ID, CHAPTER_ID);

    expect(vi.mocked(chaptersApi.cancelChapterClose)).toHaveBeenCalledTimes(1);
    const call = vi.mocked(chaptersApi.cancelChapterClose).mock.calls[0];
    expect(call[0]).toBe(BOOK_ID);
    expect(call[1]).toBe(CHAPTER_ID);

    expect(activeCloseTurn()).toBeNull();
    expect(controller.stops).toBe(1);

    unregisterCloseTurnController(controller);
  });

  it("DoD-9: a REFUSED cancel leaves the close active — the window is only closed by the server's yes", async () => {
    const controller = makeController();
    registerCloseTurnController(controller);
    markCloseTurnActive(BOOK_ID, CHAPTER_ID);
    vi.mocked(chaptersApi.cancelChapterClose).mockRejectedValue(
      new ApiError(403, "Only the book's owner can cancel a close."),
    );
    const state = new ChapterPageState(BOOK_ID, CHAPTER_ID);

    await cancelChapterCloseRequest(state, BOOK_ID, CHAPTER_ID);

    expect(activeCloseTurn()).toEqual({ bookId: BOOK_ID, chapterId: CHAPTER_ID });
    expect(controller.stops).toBe(0);

    unregisterCloseTurnController(controller);
  });

  it("DoD-9: a `closing` chapter offers the cancel transition — the Stop affordance D4 makes the only exit", () => {
    const state = new ChapterPageState(BOOK_ID, CHAPTER_ID);
    runInAction(() => {
      state.chapter = makeChapter({ state: "closing" });
      state.chapterStatus = "ready";
    });

    expect(state.offeredTransition).toBe("cancel");

    // The contrast: an `open` chapter still offers the close, not the cancel.
    runInAction(() => {
      state.chapter = makeChapter({ state: "open" });
    });
    expect(state.offeredTransition).toBe("close");
  });
});

/* --------------------------------------- DoD-9 — the page, end to end in the DOM */

describe("the chapter page's close surface (DoD-9)", () => {
  it("DoD-9: the Close control asks for confirmation first — the click alone posts nothing", async () => {
    armLoads("open");

    renderPage();

    const control = await findTheOneTransitionControl();
    expect(vi.mocked(chaptersApi.closeChapterState)).not.toHaveBeenCalled();

    fireEvent.click(control);

    // A confirmation intervenes: nothing has been posted...
    await screen.findByRole("dialog");
    expect(vi.mocked(chaptersApi.closeChapterState)).not.toHaveBeenCalled();
    // ...and no close has been marked active either.
    expect(activeCloseTurn()).toBeNull();
  });

  it("DoD-9: loading a chapter that is already `closing` marks the close active — a reload mid-close is still read-only, with no stream running", async () => {
    const pane = new ChatPaneState();
    registerCloseTurnController(pane);
    armLoads("closing");

    renderPage();

    await waitFor(() => {
      expect(activeCloseTurn()).toEqual({ bookId: BOOK_ID, chapterId: CHAPTER_ID });
    });
    expect(pane.isComposerReadOnly).toBe(true);
    // The read-only state is the SIGNAL, not a running turn: nothing was posted.
    expect(vi.mocked(chatsApi.streamChatTurn)).not.toHaveBeenCalled();

    unregisterCloseTurnController(pane);
  });

  it("DoD-9: loading a chapter that is NOT closing clears a stale signal, so the composer is writable again", async () => {
    const pane = new ChatPaneState();
    registerCloseTurnController(pane);
    // A signal left over from a previous chapter's close.
    markCloseTurnActive(BOOK_ID, "ch-some-other");
    expect(pane.isComposerReadOnly).toBe(true);

    armLoads("open");
    renderPage();

    await waitFor(() => {
      expect(activeCloseTurn()).toBeNull();
    });
    expect(pane.isComposerReadOnly).toBe(false);

    unregisterCloseTurnController(pane);
  });

  it("DoD-9: on a `closing` chapter the one offered control is Stop, and it posts to close/cancel — D4", async () => {
    armLoads("closing");

    renderPage();

    const control = await findTheOneTransitionControl();
    // Presence first: the load put the page into the close window.
    await waitFor(() => {
      expect(activeCloseTurn()).toEqual({ bookId: BOOK_ID, chapterId: CHAPTER_ID });
    });

    vi.mocked(chaptersApi.getChapter).mockResolvedValue(makeChapter({ state: "open" }));
    vi.mocked(chaptersApi.getChapterText).mockResolvedValue(makeBody("open"));

    fireEvent.click(control);

    await waitFor(() => {
      expect(vi.mocked(chaptersApi.cancelChapterClose)).toHaveBeenCalledTimes(1);
    });
    const call = vi.mocked(chaptersApi.cancelChapterClose).mock.calls[0];
    expect(call[0]).toBe(BOOK_ID);
    expect(call[1]).toBe(CHAPTER_ID);
    // Stop is not a close: the close endpoint was never called.
    expect(vi.mocked(chaptersApi.closeChapterState)).not.toHaveBeenCalled();

    // ...and the close window is over.
    await waitFor(() => {
      expect(activeCloseTurn()).toBeNull();
    });
  });
});
