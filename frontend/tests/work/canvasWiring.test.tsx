/**
 * Subject -> chat wiring and canvas application — 013.codex /
 * 013.subject-chat-canvas-wiring, DoD-1 · DoD-2 · DoD-3 · DoD-4 · DoD-5 · DoD-6 ·
 * DoD-7 · DoD-8 · DoD-9 · DoD-10 · DoD-11 (all eleven are `[test]`; the step has no
 * `[manual/live]` item — the module-tier half of DoD-5/7/8/9 also has unit cases in
 * `contentSubject.test.ts`).
 *
 * Bound to the frozen signatures in status.md -> `## Skeleton` (step 013, plus 011/012):
 *   work/contentSubject: ContentSubject / ContentSubjectSource / CanvasDraftApplier;
 *     registerContentSubject(source, applyDraft?) · unregisterContentSubject(source)
 *     currentContentSubject(): ContentSubject | null
 *     dispatchCanvasFrame(bookId: string, frame: CanvasFrame): void
 *   types/chats: interface TurnRequest { prompt; subject_kind?; subject_id?; codex_kind? }
 *                interface TurnSubject / CanvasFrame / type CanvasField
 *   api/chats: streamChatTurn(bookId, chatId, prompt, handlers, subject?): Promise<AbortController>
 *              interface TurnStreamHandlers { onThinking; onDelta; onDone; onError; onCanvas? }
 *   api/sse: streamPost(url, body, handlers): AbortController      // UNCHANGED by this step
 *   chatPaneState: ChatPaneState · sendChatTurn(state, bookId, text) ·
 *                  retryChatTurn(state, bookId) · pickChat(state, bookId, chatId)
 *   codexEntryPageState: CodexEntryPageState · loadCodexEntry · editCodexDraft ·
 *                        readonly applyDraft(field, text) · get contentSubject
 *   CodexEntryPage({ mode }) · CodexListPage({ kind })
 *
 * The air gap: every expected value comes from the step file's Definition of done /
 * Interface intent, `013.context.md` ("Which subject fields go on the wire", "The
 * buffer fallback key") and `context.md` -> "The shared-canvas write design", never
 * from code:
 *   - DoD-1: a codex entry open => the POST body carries its subject kind, its id and
 *     its codex kind (and the subject is read at SEND time, so it is always current);
 *   - DoD-2: a BLANK entry => a null subject id and the kind chosen at `/codex/new`;
 *   - DoD-3: a list page => that list's subject kind and no id;
 *   - DoD-4: nothing registered => NO subject fields at all, and the turn still runs;
 *   - DoD-5: a matching `canvas` frame applies its text to that field of the draft;
 *   - DoD-6: applying a canvas draft marks the page dirty and writes the restore buffer
 *     exactly as a hand edit does, and NO save call is made (nothing persists);
 *   - DoD-7: a frame with no target registered is buffered at
 *     `bookwriter.restore-buffer:<bookId>:codex-entry:<id>`, and returning to that entry
 *     surfaces it;
 *   - DoD-8: a frame for another subject falls back to the buffer and does not overwrite
 *     the open entry;
 *   - DoD-9: register on mount, unregister on unmount, identity-guarded;
 *   - DoD-10: the content subject and the active chat are independent, both ways;
 *   - DoD-11: the canvas event reaches `onCanvas` through `sse.ts`'s existing
 *     generic-event routing (`onEvent(name, payload)`), with `sse.ts` unmodified — proved
 *     by running the REAL `sse.ts` over a raw `event: canvas` chunk, never by invoking
 *     `onEvent` by hand (which would pass against a special-cased `sse.ts` too).
 * Routes here are basename-stripped (`/bk-1/codex/ce-1`, not `/work/bk-1/codex/ce-1`).
 *
 * Mocking: `api/` modules, never `fetch`. `api/codex` is mocked module-factory form.
 * `api/chats` is deliberately NOT mocked — the REAL `streamChatTurn` runs, so the POST
 * body under assertion is the body the app actually sends; below it `api/sse.streamPost`
 * is mocked (the seam the skeleton nominates: it owns the `AbortController`) so the posted
 * body and the turn's handlers are observable — EXCEPT in the DoD-11 block, which restores
 * the REAL `sse.ts` through `vi.importActual` and feeds it raw SSE chunks over a streamed
 * fetch double, so `sse.ts`'s own parsing and branching actually run. The DoD-11 block is
 * therefore the one place `fetch` itself is doubled — deliberately, because the transport's
 * OWN routing is the clause under test there.
 * `api/client` keeps its real `ApiError` while `request` / `refreshAuthToken`
 * are stubbed. `restoreBuffer.ts` is used for real; `tests/setup.ts` clears `localStorage`
 * in `afterEach`, so buffers are seeded in the test that needs them. `contentSubject.ts`
 * is MODULE-LEVEL state and is reset through its own API before and after every test.
 * `globals: false`: every primitive is imported explicitly.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { runInAction } from "mobx";
import { screen, waitFor } from "@testing-library/react";
import type { RenderResult } from "@testing-library/react";
import { Route, Routes } from "react-router-dom";
import type { CodexEntryResponse, CodexKind } from "../../src/types/codex";
import type {
  CanvasFrame,
  ChatResponse,
  ChatSamplingParams,
  SubjectKind,
  TurnRequest,
} from "../../src/types/chats";
import type { SSEHandlers } from "../../src/api/sse";
import * as sse from "../../src/api/sse";
import * as client from "../../src/api/client";
import * as codexApi from "../../src/api/codex";
import * as chatsApi from "../../src/api/chats";
import {
  RESTORE_BUFFER_KEY_PREFIX,
  readBuffer,
  restoreBufferKey,
} from "../../src/work/restoreBuffer";
import type { ContentSubjectSource } from "../../src/work/contentSubject";
import {
  currentContentSubject,
  dispatchCanvasFrame,
  registerContentSubject,
  unregisterContentSubject,
} from "../../src/work/contentSubject";
import {
  ChatPaneState,
  pickChat,
  retryChatTurn,
  sendChatTurn,
} from "../../src/work/components/chat/chatPaneState";
import { readActiveChatId } from "../../src/work/activeChat";
import {
  CodexEntryPageState,
  editCodexDraft,
  loadCodexEntry,
} from "../../src/work/pages/codexEntryPageState";
import { CodexEntryPage } from "../../src/work/pages/CodexEntryPage";
import { CodexListPage } from "../../src/work/pages/CodexListPage";
import { renderWithProviders } from "../support/render";

// The codex api: a module-factory mock replaces the WHOLE module, so enumerate every
// export the entry / list pages reach through their namespace import.
vi.mock("../../src/api/codex", () => ({
  listCodexEntries: vi.fn(),
  getCodexEntry: vi.fn(),
  createCodexEntry: vi.fn(),
  updateCodexEntry: vi.fn(),
}));

// BELOW `api/chats` (which stays real, so the posted body is the real one): the stream
// transport. `streamPost` owns the AbortController — the frozen seam — and its `handlers`
// are where `sse.ts`'s generic `onEvent(name, payload)` branch delivers a `canvas` frame.
vi.mock("../../src/api/sse", () => ({
  streamPost: vi.fn(),
}));

// `request` / `refreshAuthToken` are stubbed so no test reaches the network; everything
// else (notably the real `ApiError` class) is the actual module.
vi.mock("../../src/api/client", async () => {
  const actual = await vi.importActual<typeof import("../../src/api/client")>(
    "../../src/api/client",
  );
  return { ...actual, request: vi.fn(), refreshAuthToken: vi.fn(async () => {}) };
});

/* ------------------------------------------------------------------ fixtures */

const BOOK_ID = "bk-1";
const ENTRY_ID = "ce-1";
const OTHER_ENTRY_ID = "ce-other-7";
const CHAT_ID = "c-1";

/** The `modified_at` every seeded entry loads at. */
const M1 = "2026-03-04T09:00:00Z";

function makeEntry(overrides: Partial<CodexEntryResponse> & { id: string }): CodexEntryResponse {
  return {
    book_id: BOOK_ID,
    kind: "character",
    name: "Aria Stormcrow",
    body: "A sellsword out of the reach.",
    archived: false,
    author_id: "u-owner-1",
    modified_by: null,
    created_at: "2026-01-02T08:00:00Z",
    modified_at: M1,
    ...overrides,
  };
}

const CHARACTER = makeEntry({ id: ENTRY_ID });
const LOCATION = makeEntry({
  id: "ce-2",
  kind: "location",
  name: "The Glass Ford",
  body: "A shallow crossing under white cliffs.",
});
const FACT = makeEntry({
  id: "ce-3",
  kind: "fact",
  name: null,
  body: "The moon is red every seventh night.",
});

const ENTRIES: Record<string, CodexEntryResponse | undefined> = {
  [CHARACTER.id]: CHARACTER,
  [LOCATION.id]: LOCATION,
  [FACT.id]: FACT,
};

const SERVER_BODY_RE = /out of the reach/;
/** The assistant's drafted body — the distinctive word is "lantern". */
const CANVAS_BODY = "A sellsword carrying a shuttered lantern.";
const CANVAS_BODY_RE = /shuttered lantern/;
/** The assistant's drafted name. */
const CANVAS_NAME = "Aria of the Reach";
/** A draft written for a DIFFERENT entry — the distinctive word is "granite". */
const OTHER_BODY = "A mason who cuts the granite Keep.";
const OTHER_BODY_RE = /granite Keep/;

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

function makeChat(id: string = CHAT_ID, title = "Chat one"): ChatResponse {
  return {
    id,
    book_id: BOOK_ID,
    author_id: "u-1",
    title,
    llm_server_id: "s-1",
    model_name: "m-1",
    sampling: makeSampling(),
    archived: false,
    created_at: "2026-01-01T00:00:00Z",
    modified_at: "2026-01-01T00:00:00Z",
  };
}

const CHAT = makeChat();

/** A canvas frame for the open character entry's body, unless overridden. */
function makeFrame(overrides: Partial<CanvasFrame> = {}): CanvasFrame {
  return {
    subject_kind: "codex-entry",
    subject_id: ENTRY_ID,
    field: "body",
    text: CANVAS_BODY,
    ...overrides,
  };
}

function entryBufferKey(entryId: string = ENTRY_ID): string {
  return restoreBufferKey(BOOK_ID, "codex-entry", entryId);
}

/* ------------------------------------------------------------------- harness */

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

/**
 * Deliver one SSE event to the latest turn through the SAME generic path `sse.ts`
 * already uses for any non-`done` / non-`error` event name.
 */
function fireEventFrame(event: string, payload: unknown): void {
  lastPost().handlers.onEvent?.(event, payload);
}

/** Seed an active chat with a ready history and an idle turn (the shell's job in production). */
function primeActiveChat(state: ChatPaneState): void {
  runInAction(() => {
    state.chats = [CHAT];
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
async function openTurn(prompt = "Tell me about her"): Promise<ChatPaneState> {
  const state = new ChatPaneState();
  primeActiveChat(state);
  await sendChatTurn(state, BOOK_ID, prompt);
  return state;
}

/** Mount the codex entry page under both of its routes. */
function renderEntryPage(route: string): RenderResult {
  return renderWithProviders(
    <Routes>
      <Route path="/:bookId/codex/new" element={<CodexEntryPage mode="blank" />} />
      <Route path="/:bookId/codex/:id" element={<CodexEntryPage mode="existing" />} />
    </Routes>,
    { route },
  );
}

/** The three list routes, each fixed to its own kind (step 011's frozen wiring). */
const LIST_ROUTES: { kind: CodexKind; path: string; subjectKind: SubjectKind }[] = [
  { kind: "character", path: "characters", subjectKind: "characters" },
  { kind: "location", path: "locations", subjectKind: "locations" },
  { kind: "fact", path: "facts", subjectKind: "facts" },
];

function renderListPage(kind: CodexKind, path: string): RenderResult {
  return renderWithProviders(
    <Routes>
      <Route path={`/:bookId/${path}`} element={<CodexListPage kind={kind} />} />
    </Routes>,
    { route: `/${BOOK_ID}/${path}` },
  );
}

/** Whether `matcher` is visible anywhere — as a field's value or as rendered text. */
function pageShows(matcher: RegExp): boolean {
  if (screen.queryAllByDisplayValue(matcher).length > 0) return true;
  return matcher.test(document.body.textContent ?? "");
}

async function waitForPage(matcher: RegExp): Promise<void> {
  await waitFor(() => expect(pageShows(matcher)).toBe(true));
}

/** Mount the entry page and wait until its load has settled. */
async function mountLoadedEntry(entry: CodexEntryResponse = CHARACTER): Promise<RenderResult> {
  const result = renderEntryPage(`/${BOOK_ID}/codex/${entry.id}`);
  await waitFor(() => expect(vi.mocked(codexApi.getCodexEntry)).toHaveBeenCalled());
  await waitForPage(new RegExp(entry.body.slice(0, 20).replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
  return result;
}

/** A loaded entry-page state registered as the canvas target, as the page does on mount. */
async function registeredEntryState(
  entry: CodexEntryResponse = CHARACTER,
): Promise<CodexEntryPageState> {
  const state = new CodexEntryPageState(BOOK_ID, entry.id);
  await loadCodexEntry(state);
  const source: ContentSubjectSource = () => state.contentSubject;
  registerContentSubject(source, state.applyDraft);
  return state;
}

/** No write of any kind reached the server (US-086.AC-2 / US-087.AC-2 — nothing persists). */
function expectNoWriteCall(): void {
  expect(vi.mocked(codexApi.createCodexEntry)).not.toHaveBeenCalled();
  expect(vi.mocked(codexApi.updateCodexEntry)).not.toHaveBeenCalled();
}

/**
 * Clear the module-level registration through the frozen API alone: the newest
 * registration wins outright, so a sentinel is always clearable by its own identity.
 */
const RESET_SOURCE: ContentSubjectSource = () => ({ kind: "chats" });
function resetRegistry(): void {
  // Harness hygiene only — never an assertion, so a registry that cannot yet register
  // must not turn an unrelated case red. DoD-4's case asserts "nothing registered" itself.
  try {
    registerContentSubject(RESET_SOURCE);
    unregisterContentSubject(RESET_SOURCE);
  } catch {
    /* the registry is unavailable; the cases below will say so themselves */
  }
}

beforeEach(() => {
  resetRegistry();
  posts.length = 0;

  // `restoreMocks` / `clearMocks` wipe implementations between tests — re-arm every call
  // the mount + send paths touch.
  vi.mocked(client.refreshAuthToken).mockImplementation(async () => {});
  vi.mocked(sse.streamPost).mockImplementation(
    (url: string, body: object, handlers: SSEHandlers) => {
      posts.push({ url, body: body as TurnRequest, handlers });
      return new AbortController();
    },
  );
  vi.mocked(codexApi.getCodexEntry).mockImplementation(async (_bookId, entryId) => {
    const entry = ENTRIES[entryId];
    if (entry === undefined) throw new Error(`no fixture entry for ${entryId}`);
    return entry;
  });
  vi.mocked(codexApi.listCodexEntries).mockResolvedValue([]);
  vi.mocked(codexApi.updateCodexEntry).mockResolvedValue(CHARACTER);
  vi.mocked(codexApi.createCodexEntry).mockResolvedValue(CHARACTER);
});

afterEach(() => {
  resetRegistry();
  // Only the DoD-11 block stubs `fetch`; drop it so no other case can inherit it.
  vi.unstubAllGlobals();
});

/* ------------------------------- DoD-1: an open entry rides on the turn request */

describe("an open codex entry puts its subject on the turn request (DoD-1)", () => {
  it("DoD-1 (US-086.AC-1 / US-087.AC-1): the body carries the entry's subject kind, id and codex kind", async () => {
    await mountLoadedEntry(CHARACTER);

    await openTurn("Who is she?");

    const body = lastBody();
    expect(body.prompt).toBe("Who is she?");
    expect(body.subject_kind).toBe("codex-entry");
    expect(body.subject_id).toBe(ENTRY_ID);
    // The codex kind is the LOADED entry's, not a constant.
    expect(body.codex_kind).toBe("character");
  });

  it("DoD-1: a different entry's kind rides on the wire, proving the kind is the open row's", async () => {
    await mountLoadedEntry(LOCATION);

    await openTurn();

    expect(lastBody().subject_id).toBe(LOCATION.id);
    expect(lastBody().codex_kind).toBe("location");
  });

  it("DoD-1 (Interface intent): the subject is read at SEND time, so a retry carries the CURRENT subject", async () => {
    // The author sends on one entry, navigates to another, then retries the failed turn.
    const first = await mountLoadedEntry(CHARACTER);
    const state = await openTurn("first prompt");
    expect(lastBody().subject_id).toBe(ENTRY_ID);

    first.unmount();
    await mountLoadedEntry(FACT);
    runInAction(() => {
      state.turnStatus = "error";
      state.turnError = "boom";
    });

    await retryChatTurn(state, BOOK_ID);

    // The retry names the entry the author is looking at NOW, not the one it was sent from.
    expect(posts).toHaveLength(2);
    expect(lastBody().subject_id).toBe(FACT.id);
    expect(lastBody().codex_kind).toBe("fact");
  });
});

/* ------------------------------------ DoD-2: a blank entry sends a null subject id */

describe("a blank entry sends a null subject id and the route's kind (DoD-2)", () => {
  it("DoD-2 (UC-076): the body carries subject_id null and the kind chosen at /codex/new", async () => {
    renderEntryPage(`/${BOOK_ID}/codex/new?kind=location`);
    await waitFor(() => expect(screen.queryAllByRole("textbox").length).toBeGreaterThan(0));
    // A blank entry has no row to fetch.
    expect(vi.mocked(codexApi.getCodexEntry)).not.toHaveBeenCalled();

    await openTurn("Draft me a river crossing");

    const body = lastBody();
    expect(body.subject_kind).toBe("codex-entry");
    // Null, never an omitted id — an absent id must not be readable as one.
    expect(body.subject_id).toBeNull();
    expect(body.codex_kind).toBe("location");
  });

  it("DoD-2 (UC-076): the blank route's kind is the query param's, for each kind", async () => {
    renderEntryPage(`/${BOOK_ID}/codex/new?kind=fact`);
    await waitFor(() => expect(screen.queryAllByRole("textbox").length).toBeGreaterThan(0));

    await openTurn();

    expect(lastBody().subject_id).toBeNull();
    expect(lastBody().codex_kind).toBe("fact");
  });
});

/* ------------------------------------------ DoD-3: a list page is a subject too */

describe("a list page sends its subject kind and no id (DoD-3)", () => {
  for (const { kind, path, subjectKind } of LIST_ROUTES) {
    it(`DoD-3 (UC-090): the ${path} list sends subject kind "${subjectKind}" and no id`, async () => {
      renderListPage(kind, path);
      await waitFor(() => expect(vi.mocked(codexApi.listCodexEntries)).toHaveBeenCalled());

      await openTurn("What do I have here?");

      const body = lastBody();
      expect(body.subject_kind).toBe(subjectKind);
      // A list names no entity — there is no id to send.
      expect(body.subject_id ?? null).toBeNull();
    });
  }
});

/* -------------------------- DoD-4: nothing registered => no subject fields at all */

describe("with nothing registered the turn carries no subject fields (DoD-4)", () => {
  it("DoD-4 (011's shipped behaviour survives): the posted body is exactly { prompt }", async () => {
    // No content page is mounted at all — the chats view, or the shell before any subject
    // loads. The body itself is the evidence; the pane is asked for nothing else.
    await openTurn("hello");

    expect(Object.keys(lastBody())).toEqual(["prompt"]);
    expect(lastBody().prompt).toBe("hello");
  });

  it("DoD-4: the turn still runs — the stream opens and the author's message is shown", async () => {
    const state = await openTurn("hello");

    expect(posts).toHaveLength(1);
    expect(state.turnStatus).toBe("streaming");
    expect(
      state.renderedMessages.some((m) => m.role === "user" && m.content === "hello"),
    ).toBe(true);
  });
});

/* ---------------------- DoD-5: a matching canvas frame reaches the open entry */

describe("a matching canvas frame applies to the open entry's draft (DoD-5)", () => {
  it("DoD-5 (US-086.AC-1 / US-087.AC-1): the frame's text lands in the body field of the open entry", async () => {
    await mountLoadedEntry(CHARACTER);
    await openTurn();

    fireEventFrame("canvas", makeFrame({ field: "body", text: CANVAS_BODY }));

    await waitForPage(CANVAS_BODY_RE);
    // The server text it replaced is no longer what the author is editing.
    expect(screen.queryAllByDisplayValue(SERVER_BODY_RE)).toHaveLength(0);
  });

  it("DoD-5: a name frame lands in the NAME field, leaving the body alone", async () => {
    await mountLoadedEntry(CHARACTER);
    await openTurn();

    fireEventFrame("canvas", makeFrame({ field: "name", text: CANVAS_NAME }));

    await waitForPage(new RegExp(CANVAS_NAME));
    expect(pageShows(SERVER_BODY_RE)).toBe(true);
  });
});

/* ----------------- DoD-6: an applied draft is a hand edit, and never a save */

describe("applying a canvas draft is exactly a hand edit, and nothing persists (DoD-6)", () => {
  it("DoD-6 (US-086.AC-2 / US-087.AC-2 / US-103.AC-1 / US-107.AC-1): dirty + buffered + no save call", async () => {
    const state = await registeredEntryState(CHARACTER);
    expect(state.isDirty).toBe(false);

    dispatchCanvasFrame(BOOK_ID, makeFrame({ field: "body", text: CANVAS_BODY }));

    expect(state.bodyDraft).toBe(CANVAS_BODY);
    expect(state.isDirty).toBe(true);
    expect(readBuffer(entryBufferKey())?.draft).toBe(CANVAS_BODY);
    // The buffer's base version is the entry's loaded `modified_at`, as for any edit.
    expect(readBuffer(entryBufferKey())?.baseVersion).toBe(M1);
    // Nothing persists: there is no code path from a chat to the codex table.
    expectNoWriteCall();
  });

  it("DoD-6: the buffer record is indistinguishable from the one a keystroke writes", async () => {
    const viaCanvasState = await registeredEntryState(CHARACTER);
    dispatchCanvasFrame(BOOK_ID, makeFrame({ field: "body", text: CANVAS_BODY }));
    const viaCanvas = readBuffer(entryBufferKey());

    // The same text, typed by the author instead.
    const viaKeystrokeState = new CodexEntryPageState(BOOK_ID, ENTRY_ID);
    await loadCodexEntry(viaKeystrokeState);
    editCodexDraft(viaKeystrokeState, "body", CANVAS_BODY);
    const viaKeystroke = readBuffer(entryBufferKey());

    expect(viaCanvas?.draft).toBe(viaKeystroke?.draft);
    expect(viaCanvas?.baseVersion).toBe(viaKeystroke?.baseVersion);
    expect(viaCanvasState.bodyDraft).toBe(viaKeystrokeState.bodyDraft);
    expect(viaCanvasState.isDirty).toBe(viaKeystrokeState.isDirty);
    expectNoWriteCall();
  });

  it("DoD-6: a frame delivered through the chat pane still writes no save call", async () => {
    await mountLoadedEntry(CHARACTER);
    await openTurn();

    fireEventFrame("canvas", makeFrame({ field: "body", text: CANVAS_BODY }));

    await waitForPage(CANVAS_BODY_RE);
    await waitFor(() => expect(readBuffer(entryBufferKey())?.draft).toBe(CANVAS_BODY));
    expectNoWriteCall();
  });
});

/* -------- DoD-7: no target registered => buffered, and restored on return */

describe("a frame arriving after the author navigated away is buffered and restored (DoD-7)", () => {
  it("DoD-7 (US-107.AC-1): the draft lands at bookwriter.restore-buffer:<bookId>:codex-entry:<id>", async () => {
    const page = await mountLoadedEntry(CHARACTER);
    await openTurn();

    // The author navigates away mid-turn — the page unmounts and unregisters.
    page.unmount();
    expect(currentContentSubject()).toBeNull();

    fireEventFrame("canvas", makeFrame({ field: "body", text: CANVAS_BODY }));

    const expectedKey = `${RESTORE_BUFFER_KEY_PREFIX}:${BOOK_ID}:codex-entry:${ENTRY_ID}`;
    expect(entryBufferKey()).toBe(expectedKey);
    await waitFor(() => expect(readBuffer(expectedKey)?.draft).toBe(CANVAS_BODY));
    expectNoWriteCall();
  });

  it("DoD-7 (US-107.AC-1): returning to that entry surfaces the buffered draft", async () => {
    const page = await mountLoadedEntry(CHARACTER);
    await openTurn();
    page.unmount();

    fireEventFrame("canvas", makeFrame({ field: "body", text: CANVAS_BODY }));
    await waitFor(() => expect(readBuffer(entryBufferKey())?.draft).toBe(CANVAS_BODY));

    // The author comes back to the entry.
    renderEntryPage(`/${BOOK_ID}/codex/${ENTRY_ID}`);

    // The assistant's draft is in front of the author again, through the path that
    // already existed — and it was never saved.
    await waitForPage(CANVAS_BODY_RE);
    expectNoWriteCall();
  });
});

/* ------------------ DoD-8: a frame for another subject never crosses over */

describe("a frame whose subject id does not match never overwrites the open entry (DoD-8)", () => {
  it("DoD-8 (no cross-subject writes): the text is buffered for ITS entry and the open one is untouched", async () => {
    await mountLoadedEntry(CHARACTER);
    await openTurn();

    fireEventFrame(
      "canvas",
      makeFrame({ subject_id: OTHER_ENTRY_ID, field: "body", text: OTHER_BODY }),
    );

    // It fell back to the buffer, keyed for the entry it was written for.
    await waitFor(() =>
      expect(readBuffer(entryBufferKey(OTHER_ENTRY_ID))?.draft).toBe(OTHER_BODY),
    );
    // The open entry still shows its own text, and its own buffer was not written.
    expect(pageShows(SERVER_BODY_RE)).toBe(true);
    expect(pageShows(OTHER_BODY_RE)).toBe(false);
    expect(readBuffer(entryBufferKey(ENTRY_ID))).toBeNull();
    expectNoWriteCall();
  });

  it("DoD-8: the open entry's state stays clean — no draft change, not dirty", async () => {
    const state = await registeredEntryState(CHARACTER);

    dispatchCanvasFrame(
      BOOK_ID,
      makeFrame({ subject_id: OTHER_ENTRY_ID, field: "body", text: OTHER_BODY }),
    );

    expect(state.bodyDraft).toBe(CHARACTER.body);
    expect(state.isDirty).toBe(false);
    expect(readBuffer(entryBufferKey(OTHER_ENTRY_ID))?.draft).toBe(OTHER_BODY);
  });
});

/* --------------------- DoD-9: registration is a mount/unmount effect, guarded */

describe("a page registers on mount and unregisters on unmount (DoD-9)", () => {
  it("DoD-9: the entry page's registration appears on mount and is gone on unmount", async () => {
    const page = await mountLoadedEntry(CHARACTER);

    const subject = currentContentSubject();
    expect(subject?.kind).toBe("codex-entry");
    expect(subject?.entityId).toBe(ENTRY_ID);

    page.unmount();

    expect(currentContentSubject()).toBeNull();
  });

  it("DoD-9: a list page registers a kind-only subject and clears it on unmount", async () => {
    const page = renderListPage("location", "locations");
    await waitFor(() => expect(vi.mocked(codexApi.listCodexEntries)).toHaveBeenCalled());

    const subject = currentContentSubject();
    expect(subject?.kind).toBe("locations");
    // A list names no entity.
    expect(subject?.entityId ?? null).toBeNull();

    page.unmount();

    expect(currentContentSubject()).toBeNull();
  });

  it("DoD-9: a LATE unmount from the previous page does not clear the newer page's registration", async () => {
    // Two pages overlap across a route transition: the new one mounts first, then the
    // old one's cleanup finally runs.
    const oldPage = await mountLoadedEntry(CHARACTER);
    const newPage = renderListPage("fact", "facts");
    await waitFor(() => expect(currentContentSubject()?.kind).toBe("facts"));

    oldPage.unmount(); // the late cleanup

    // The newer page still owns the registration...
    expect(currentContentSubject()?.kind).toBe("facts");

    // ...and it is cleared only by the page that actually holds it.
    newPage.unmount();
    expect(currentContentSubject()).toBeNull();
  });
});

/* -------------------- DoD-10: the subject and the active chat are independent */

describe("the content subject and the active chat are independent (DoD-10)", () => {
  it("DoD-10 (UC-083): switching the content subject does not change which chat is active", async () => {
    const state = new ChatPaneState();
    primeActiveChat(state);
    pickChat(state, BOOK_ID, CHAT_ID);

    const entryPage = await mountLoadedEntry(CHARACTER);
    expect(state.activeChatId).toBe(CHAT_ID);
    expect(readActiveChatId(BOOK_ID)).toBe(CHAT_ID);

    // A real subject switch: the entry page goes, a list page arrives.
    entryPage.unmount();
    renderListPage("character", "characters");
    await waitFor(() => expect(vi.mocked(codexApi.listCodexEntries)).toHaveBeenCalled());

    // The conversation is untouched by the navigation.
    expect(state.activeChatId).toBe(CHAT_ID);
    expect(readActiveChatId(BOOK_ID)).toBe(CHAT_ID);
    expect(state.messagesStatus).toBe("ready");

    // ...and the subject really did switch, observed the way the app observes it.
    await sendChatTurn(state, BOOK_ID, "what do I have here?");
    expect(lastBody().subject_kind).toBe("characters");
    expect(lastPost().url).toContain(CHAT_ID);
  });

  it("DoD-10 (US-105.AC-3): switching chats does not change the content subject", async () => {
    await mountLoadedEntry(CHARACTER);
    const state = new ChatPaneState();
    primeActiveChat(state);
    runInAction(() => {
      state.chats = [CHAT, makeChat("c-2", "Chat two")];
    });

    // The subject as the app itself sees it: the body of a turn sent before the switch.
    await sendChatTurn(state, BOOK_ID, "about her");
    const beforeBody = lastBody();
    const before = {
      subject_kind: beforeBody.subject_kind,
      subject_id: beforeBody.subject_id,
      codex_kind: beforeBody.codex_kind,
    };
    expect(before.subject_id).toBe(ENTRY_ID);

    // A real chat switch, in the pane.
    pickChat(state, BOOK_ID, "c-2");

    expect(state.activeChatId).toBe("c-2");
    expect(readActiveChatId(BOOK_ID)).toBe("c-2");
    // The content pane still shows the same entry.
    expect(pageShows(SERVER_BODY_RE)).toBe(true);

    // ...and the next turn goes to the NEW chat while carrying the SAME subject.
    runInAction(() => {
      state.messages = [];
      state.messagesStatus = "ready";
      state.turnStatus = "idle";
    });
    await sendChatTurn(state, BOOK_ID, "still about her");

    expect(lastPost().url).toContain("c-2");
    const afterBody = lastBody();
    expect({
      subject_kind: afterBody.subject_kind,
      subject_id: afterBody.subject_id,
      codex_kind: afterBody.codex_kind,
    }).toEqual(before);
  });
});

/* ------------- DoD-11: the canvas event rides sse.ts's generic-event routing */

describe("the canvas event reaches onCanvas through sse.ts's REAL generic routing (DoD-11)", () => {
  /**
   * These three cases run `sse.ts` **for real** — the module mock above is replaced by
   * the actual implementation, and a raw `event: canvas` / `data: {…}` chunk is fed in
   * through a streamed fetch double, so `sse.ts`'s own frame splitting, `event:` / `data:`
   * parsing and its `done` / `error` / generic branching all execute. A hand-invoked
   * `onEvent` would prove nothing here: it would pass just as well against an `sse.ts`
   * that special-cased `canvas`, which is the distinction this clause exists to make.
   */
  async function useRealStreamPost(): Promise<void> {
    const actualSse = await vi.importActual<typeof import("../../src/api/sse")>(
      "../../src/api/sse",
    );
    vi.mocked(sse.streamPost).mockImplementation(actualSse.streamPost);
  }

  /** One SSE frame exactly as the backend's serializer writes it onto the wire. */
  function sseFrame(event: string, data: unknown): string {
    return `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
  }

  /**
   * A streamed response double: `sse.ts` reads `res.ok` and `res.body.getReader()` and
   * decodes the bytes itself. Frames are ASCII, so no `TextEncoder` is needed.
   */
  function stubFetchWithFrames(frames: string[]): void {
    const chunks = frames.map((frame) => Uint8Array.from(frame, (ch) => ch.charCodeAt(0)));
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        let index = 0;
        const reader = {
          read: async () =>
            index < chunks.length
              ? { done: false, value: chunks[index++] }
              : { done: true, value: undefined },
        };
        return { ok: true, status: 200, body: { getReader: () => reader } } as unknown as Response;
      }),
    );
  }

  it("DoD-11: sse.ts parses a raw `event: canvas` frame and routes it through its GENERIC onEvent branch", async () => {
    const actualSse = await vi.importActual<typeof import("../../src/api/sse")>(
      "../../src/api/sse",
    );
    const frame = makeFrame({ field: "body", text: CANVAS_BODY });
    stubFetchWithFrames([sseFrame("canvas", frame), sseFrame("done", {})]);

    const onEvent = vi.fn();
    const onDone = vi.fn();
    const onError = vi.fn();
    actualSse.streamPost("/api/books/bk-1/chats/c-1/turn", { prompt: "hello" }, {
      onEvent,
      onDone,
      onError,
    });

    await waitFor(() => expect(onDone).toHaveBeenCalledTimes(1));

    // `canvas` is not special-cased anywhere in `sse.ts`: it arrives at the generic
    // handler under its own event name, with its payload parsed and intact.
    expect(onEvent).toHaveBeenCalledTimes(1);
    expect(onEvent).toHaveBeenCalledWith("canvas", frame);
    expect(onError).not.toHaveBeenCalled();
  });

  it("DoD-11: a `canvas` frame on the wire reaches streamChatTurn's onCanvas handler, frame intact", async () => {
    await useRealStreamPost();
    const frame = makeFrame({ field: "body", text: CANVAS_BODY });
    stubFetchWithFrames([sseFrame("canvas", frame), sseFrame("done", {})]);

    const onCanvas = vi.fn();
    const onError = vi.fn();
    await chatsApi.streamChatTurn(BOOK_ID, CHAT_ID, "hello", {
      onThinking: () => {},
      onDelta: () => {},
      onDone: () => {},
      onError,
      onCanvas,
    });

    await waitFor(() => expect(onCanvas).toHaveBeenCalledTimes(1));
    expect(onCanvas).toHaveBeenCalledWith(frame);
    expect(onError).not.toHaveBeenCalled();
  });

  it("DoD-11: a canvas frame arriving on the wire reaches the registered page (end to end)", async () => {
    await useRealStreamPost();
    await mountLoadedEntry(CHARACTER);
    stubFetchWithFrames([
      sseFrame("canvas", makeFrame({ field: "body", text: CANVAS_BODY })),
      sseFrame("done", {}),
    ]);

    await openTurn();

    // Wire -> sse.ts's generic branch -> streamChatTurn's onCanvas -> the registry ->
    // the open entry's draft.
    await waitForPage(CANVAS_BODY_RE);
  });
});
