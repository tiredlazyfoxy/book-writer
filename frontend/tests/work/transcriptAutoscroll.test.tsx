/**
 * The transcript follows the newest message — fast/010.transcript-autoscroll,
 * DoD-5 … DoD-13.
 *
 * Bound to the frozen signatures in status.md -> `## Skeleton`:
 *   new ChatPaneState()                                   // NO arguments
 *   ChatPaneState.transcriptViewport: HTMLDivElement | null   // non-observable, init null
 *   ChatPaneState.get transcriptGrowthSignature(): string     // a STRING, never a sum
 *   attachTranscriptViewport(state, element | null): void
 *   noteTranscriptScroll(state): void                     // takes NO position argument
 *   scrollTranscriptToBottom(state): void                 // the synchronous one
 *   followTranscript(state): void                         // deferred + coalesced (rAF)
 *   repinTranscript(state): void                          // forces pinned, then follows
 *   releaseTranscriptViewport(state): void
 *   loadChatMessages(state, bookId, chatId, signal?): Promise<void>   // unchanged
 *   interface MessageListProps { state: ChatPaneState }   // unchanged
 *
 * Every expected value comes from `plan.md` -> Definition of done and Interface
 * intent, never from code:
 *   - the attach stores the element and the release clears it; with nothing
 *     attached the synchronous scroll is a silent no-op (DoD-5);
 *   - the pinned flag starts TRUE, so a fresh pane follows from its first render
 *     with no scroll event at all (DoD-6);
 *   - the note-scroll operation measures the LIVE element and re-answers the
 *     predicate, so a scrolled-up author's position is preserved — zero writes,
 *     not a write of the same value (DoD-7);
 *   - the re-pin operation overrides an unpinned viewport, and because it routes
 *     through the deferred follow it needs a frame flush (DoD-8);
 *   - the follow writes NOTHING synchronously and coalesces N rapid calls into
 *     exactly one write per frame (DoD-9), and writes nothing at all while
 *     unpinned (DoD-10);
 *   - the growth signature CHANGES for each of the four growth sources, and for
 *     the appended-message-while-streamingContent-cleared mutation that a sum
 *     would cancel (DoD-11) — the separator is explicitly NOT part of the
 *     contract, so nothing here asserts the value itself;
 *   - `loadChatMessages` re-pins, which is the automated half of "on reload,
 *     always to bottom" and covers chat switch / `chatPaneController.openChat`
 *     too (DoD-12);
 *   - `MessageList` hands over the ScrollArea's VIEWPORT, not its root wrapper
 *     (DoD-13) — asserted as "a strict ancestor of the rendered transcript that
 *     is NOT the outermost element of the component's subtree", with no Mantine
 *     class name and no dependence on where the provider injects its styles.
 *
 * THE STUB ELEMENT. jsdom computes no layout: `scrollHeight` and `clientHeight`
 * are 0 on every real element, so every geometric assertion below runs against a
 * hand-made `document.createElement("div")` whose two read-only metrics are
 * installed with `Object.defineProperty` (the repo's idiom —
 * `ChapterBodyEditor.test.tsx:99`, `composerResize.test.tsx:98`) and whose
 * `scrollTop` is a getter/setter pair over a local, so writes can be COUNTED.
 * Counting matters: DoD-7 and DoD-10 assert zero writes and DoD-9 asserts exactly
 * one, none of which a bare value property could express. `place()` moves the
 * viewport the way a user would, without recording a write.
 *
 * FRAMES. This feature is the repo's first `requestAnimationFrame` use. jsdom's
 * rAF is real and timer-backed, so fake timers are deliberately avoided; a
 * pending frame is flushed by scheduling one of our own behind it.
 *
 * DELIBERATELY ABSENT, per `plan.md` -> "Deliberately not automated": real
 * pinning during a live stream and the pane's flex chain, a genuine user scroll
 * arriving through Mantine's `onScrollPositionChange`, the full send / retry
 * path, the absence of a jump-to-latest affordance, and scroll smoothness.
 * `globals: false`.
 */
import { describe, expect, it, vi } from "vitest";
import { runInAction } from "mobx";
import { within } from "@testing-library/react";
import type {
  ChatDetailResponse,
  ChatMessageResponse,
  ChatResponse,
  ChatSamplingParams,
} from "../../src/types/chats";
import {
  ChatPaneState,
  attachTranscriptViewport,
  followTranscript,
  loadChatMessages,
  noteTranscriptScroll,
  releaseTranscriptViewport,
  repinTranscript,
  scrollTranscriptToBottom,
  type ToolTraceRow,
} from "../../src/work/components/chat/chatPaneState";
import { MessageList } from "../../src/work/components/chat/MessageList";
import * as chatsApi from "../../src/api/chats";
import { renderWithProviders } from "../support/render";

// Whole-module factory, the specifier every spec under `tests/work/` uses. The
// pane state imports this module as a namespace, so the factory replaces it
// wholesale; `getChat` is the only member DoD-12 drives, the rest are here for
// mock completeness so no import can reach the network.
vi.mock("../../src/api/chats", () => ({
  listChats: vi.fn(),
  createChat: vi.fn(),
  updateChat: vi.fn(),
  getChat: vi.fn(),
  listModelOptions: vi.fn(),
  titleChat: vi.fn(),
  streamChatTurn: vi.fn(),
}));

const BOOK_ID = "bk-1";
const CHAT_ID = "c-1";

/** The spec's worked geometry: a 2000px transcript in a 500px viewport... */
const SCROLL_HEIGHT = 2000;
const CLIENT_HEIGHT = 500;
/** ...whose bottom is scrollTop 1500. */
const BOTTOM = 1500;

interface StubViewport {
  /** The element handed to `attachTranscriptViewport`. */
  el: HTMLDivElement;
  /** Every value written THROUGH the `scrollTop` setter, in order. */
  writes: number[];
  /** The current position. */
  position(): number;
  /** Move the viewport as a user's own scroll would — recorded as no write. */
  place(value: number): void;
}

/**
 * A div with layout. jsdom gives every real element `scrollHeight === 0` and
 * `clientHeight === 0`, so the geometry has to be installed by hand.
 */
function makeStubViewport(
  scrollHeight = SCROLL_HEIGHT,
  clientHeight = CLIENT_HEIGHT,
): StubViewport {
  const el = document.createElement("div");
  let position = 0;
  const writes: number[] = [];

  Object.defineProperty(el, "scrollHeight", {
    value: scrollHeight,
    writable: true,
    configurable: true,
  });
  Object.defineProperty(el, "clientHeight", {
    value: clientHeight,
    writable: true,
    configurable: true,
  });
  Object.defineProperty(el, "scrollTop", {
    configurable: true,
    get: () => position,
    set: (value: number) => {
      writes.push(value);
      position = value;
    },
  });

  return {
    el,
    writes,
    position: () => position,
    place: (value: number) => {
      position = value;
    },
  };
}

/**
 * Let any pending animation frame run. Ours is queued behind whatever the code
 * under test scheduled, and the trailing macrotask lets the resulting promise
 * jobs drain. Real timers throughout — jsdom drives rAF from its own timer loop.
 */
async function flushFrame(): Promise<void> {
  await new Promise<void>((resolve) => {
    requestAnimationFrame(() => resolve());
  });
  await new Promise<void>((resolve) => {
    setTimeout(resolve, 0);
  });
}

/** A fresh pane with a stub viewport already attached. */
function attachedPane(): { state: ChatPaneState; viewport: StubViewport } {
  const state = new ChatPaneState();
  const viewport = makeStubViewport();
  attachTranscriptViewport(state, viewport.el);
  return { state, viewport };
}

/** Scroll to the top and tell the state about it — the author has read back. */
function scrollUpAndNote(state: ChatPaneState, viewport: StubViewport): void {
  viewport.place(0);
  noteTranscriptScroll(state);
  viewport.writes.length = 0;
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

const CHAT: ChatResponse = {
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
  active_side_chat_id: null,
};

function makeMessage(id: string, role: string, content: string, position: number): ChatMessageResponse {
  return {
    id,
    chat_id: CHAT_ID,
    role,
    content,
    reasoning: null,
    position,
    created_at: "2026-01-01T00:00:00Z",
    side_chat_id: null,
    tool_trace: null,
  };
}

function makeToolTraceRow(toolName: string): ToolTraceRow {
  return { toolName, arguments: {}, result: null, ok: true };
}

describe("attach and release own the viewport slot (DoD-5)", () => {
  it("DoD-5: with no viewport attached the synchronous scroll is a silent no-op", () => {
    const state = new ChatPaneState();

    // Nothing attached yet — the pane renders before it scrolls, and a pane that
    // is never rendered must still be safe to drive.
    expect(state.transcriptViewport).toBeNull();
    expect(() => scrollTranscriptToBottom(state)).not.toThrow();
  });

  it("DoD-5: after attaching, the synchronous scroll writes to that element", () => {
    const { state, viewport } = attachedPane();

    expect(state.transcriptViewport).toBe(viewport.el);

    scrollTranscriptToBottom(state);

    expect(viewport.writes).toEqual([BOTTOM]);
  });

  it("DoD-5: after releasing, the synchronous scroll no longer writes to it", () => {
    const { state, viewport } = attachedPane();
    scrollTranscriptToBottom(state);
    viewport.writes.length = 0;

    releaseTranscriptViewport(state);

    expect(state.transcriptViewport).toBeNull();
    expect(() => scrollTranscriptToBottom(state)).not.toThrow();
    expect(viewport.writes).toEqual([]);
  });
});

describe("a fresh pane is pinned before any scroll event exists (DoD-6)", () => {
  it("DoD-6: a freshly constructed state scrolls to the bottom with no prior scroll notification", () => {
    // The flag is initialised true precisely so the very first render follows —
    // there is no scroll event to learn it from at that point.
    const state = new ChatPaneState();
    const viewport = makeStubViewport();
    attachTranscriptViewport(state, viewport.el);

    expect(viewport.position()).toBe(0);

    scrollTranscriptToBottom(state);

    expect(viewport.position()).toBe(BOTTOM);
  });
});

describe("the note-scroll operation unpins and re-pins from live geometry (DoD-7)", () => {
  it("DoD-7: scrolled to the top, the position is preserved — zero writes occur", () => {
    const { state, viewport } = attachedPane();

    viewport.place(0);
    noteTranscriptScroll(state);
    viewport.writes.length = 0;

    scrollTranscriptToBottom(state);

    // Not "writes 0 back", but writes NOTHING: the author is reading and the
    // viewport must not be touched at all.
    expect(viewport.writes).toEqual([]);
    expect(viewport.position()).toBe(0);
  });

  it("DoD-7: scrolling back to the bottom and noting it re-engages the follow", () => {
    const { state, viewport } = attachedPane();
    scrollUpAndNote(state, viewport);

    viewport.place(BOTTOM);
    noteTranscriptScroll(state);
    viewport.writes.length = 0;

    scrollTranscriptToBottom(state);

    expect(viewport.writes).toEqual([BOTTOM]);
    expect(viewport.position()).toBe(BOTTOM);
  });
});

describe("the force-re-pin path overrides a scrolled-up viewport (DoD-8)", () => {
  it("DoD-8: re-pinning an unpinned pane lands at the bottom after a frame", async () => {
    const { state, viewport } = attachedPane();
    scrollUpAndNote(state, viewport);
    expect(viewport.position()).toBe(0);

    repinTranscript(state);
    await flushFrame();

    // This is the operation send, retry and the chat load all invoke.
    expect(viewport.position()).toBe(BOTTOM);
  });
});

describe("the follow operation is deferred and coalesced (DoD-9)", () => {
  it("DoD-9: it writes nothing synchronously, and N rapid calls collapse into exactly one write", async () => {
    const { state, viewport } = attachedPane();

    followTranscript(state);
    followTranscript(state);
    followTranscript(state);
    followTranscript(state);

    // Deferral is mandatory: a MobX autorun fires BEFORE React re-renders, so a
    // synchronous measurement would read the pre-update height.
    expect(viewport.writes).toEqual([]);

    await flushFrame();

    // Coalescing: a fast token stream must not queue one frame per delta.
    expect(viewport.writes).toEqual([BOTTOM]);
    expect(viewport.position()).toBe(BOTTOM);
  });
});

describe("the follow operation respects a scrolled-up author (DoD-10)", () => {
  it("DoD-10: while unpinned it writes nothing at all, even after a frame", async () => {
    const { state, viewport } = attachedPane();
    scrollUpAndNote(state, viewport);

    followTranscript(state);
    await flushFrame();

    // A scrolled-up author schedules nothing — that IS "the position is preserved".
    expect(viewport.writes).toEqual([]);
    expect(viewport.position()).toBe(0);
  });
});

describe("the transcript growth signature changes whenever the transcript grows (DoD-11)", () => {
  // The separator is explicitly NOT part of the contract, so every assertion
  // here is about CHANGE, never about the value.
  it("DoD-11: appending a message changes it", () => {
    const state = new ChatPaneState();
    const before = state.transcriptGrowthSignature;

    runInAction(() => {
      state.messages = [...state.messages, makeMessage("m-1", "user", "hello", 0)];
    });

    expect(state.transcriptGrowthSignature).not.toBe(before);
  });

  it("DoD-11: appending to streamingContent changes it", () => {
    const state = new ChatPaneState();
    const before = state.transcriptGrowthSignature;

    runInAction(() => {
      state.streamingContent = `${state.streamingContent}token`;
    });

    expect(state.transcriptGrowthSignature).not.toBe(before);
  });

  it("DoD-11: appending to streamingThinking changes it", () => {
    const state = new ChatPaneState();
    const before = state.transcriptGrowthSignature;

    runInAction(() => {
      state.streamingThinking = `${state.streamingThinking}pondering`;
    });

    expect(state.transcriptGrowthSignature).not.toBe(before);
  });

  it("DoD-11: appending to streamingToolTrace changes it", () => {
    const state = new ChatPaneState();
    const before = state.transcriptGrowthSignature;

    runInAction(() => {
      state.streamingToolTrace = [...state.streamingToolTrace, makeToolTraceRow("search")];
    });

    expect(state.transcriptGrowthSignature).not.toBe(before);
  });

  it("DoD-11: it changes when one message is appended while streamingContent is cleared in the same mutation", () => {
    // The whole reason the value is a string rather than a sum. `finishTurn`
    // appends the persisted answer and clears the live buffer together; with the
    // lengths chosen below a sum nets to the same number, MobX would not re-run
    // the autorun, and the transcript would fail to follow at exactly the moment
    // the final answer lands.
    const state = new ChatPaneState();
    runInAction(() => {
      state.messages = [makeMessage("m-1", "user", "hello", 0)];
      state.streamingContent = "x";
    });
    const before = state.transcriptGrowthSignature;

    runInAction(() => {
      state.messages = [...state.messages, makeMessage("m-2", "assistant", "an answer", 1)];
      state.streamingContent = "";
    });

    expect(state.transcriptGrowthSignature).not.toBe(before);
  });
});

describe("loading a chat's messages re-pins the transcript (DoD-12)", () => {
  it("DoD-12: a completed load leaves a scrolled-up viewport at the bottom", async () => {
    const detail: ChatDetailResponse = {
      chat: CHAT,
      messages: [
        makeMessage("m-1", "user", "first", 0),
        makeMessage("m-2", "assistant", "second", 1),
      ],
    };
    vi.mocked(chatsApi.getChat).mockResolvedValue(detail);

    const { state, viewport } = attachedPane();
    scrollUpAndNote(state, viewport);
    expect(viewport.position()).toBe(0);

    await loadChatMessages(state, BOOK_ID, CHAT_ID);
    await flushFrame();

    // Mount, reload and chat switch all run through here — including
    // `chatPaneController.openChat`, which is why that file needs no change.
    expect(state.messages).toHaveLength(2);
    expect(viewport.position()).toBe(BOTTOM);
  });
});

describe("MessageList hands its scrolling viewport to the pane state (DoD-13)", () => {
  function primedState(): ChatPaneState {
    const state = new ChatPaneState();
    runInAction(() => {
      state.chats = [CHAT];
      state.activeChatId = CHAT_ID;
      state.messages = [makeMessage("m-1", "user", "a transcribed line", 0)];
      state.messagesStatus = "ready";
      state.turnStatus = "idle";
      state.turnError = null;
    });
    return state;
  }

  /**
   * The outermost element of the COMPONENT's own subtree, derived from rendered
   * content rather than from the container's child order.
   *
   * `container.firstElementChild` is NOT this element and must not be used:
   * `renderWithProviders` wraps everything in a `MantineProvider`, which emits
   * its own `<style>` elements as the container's first children, ahead of the
   * caller's tree. Anchoring on it would ask whether a style tag contains a div
   * — false for every implementation, right or wrong, and therefore decides
   * nothing. Walking UP from a node the transcript actually rendered is immune
   * to whatever the provider injects alongside.
   */
  function outermostRenderedElement(container: HTMLElement, from: Element): Element {
    let node: Element = from;
    while (node.parentElement !== null && node.parentElement !== container) {
      node = node.parentElement;
    }
    expect(node.parentElement).toBe(container);
    return node;
  }

  it("DoD-13: rendering attaches the scroll container — a strict ancestor of the transcript, and not the component's outer wrapper", () => {
    const state = primedState();

    const { container } = renderWithProviders(<MessageList state={state} />);

    const viewport = state.transcriptViewport;
    expect(viewport).not.toBeNull();

    // A node the transcript genuinely rendered, found by its visible text.
    const line = within(container).getByText("a transcribed line");
    const outer = outermostRenderedElement(container, line);

    // Clause one: the attached node WRAPS the transcript — it is a strict
    // ancestor of the rendered content, so it is a container, not a leaf.
    expect(viewport).not.toBe(line);
    expect(viewport?.contains(line)).toBe(true);

    // Clause two, the discriminating one: it is NOT the outermost element of the
    // component's own subtree. The `ScrollArea`'s `ref` targets that root, which
    // does not scroll; only the internal viewport does. A handover of the root
    // wrapper would satisfy clause one and fail here. Stated through the DOM's
    // own ancestry — no Mantine class name, no container child order.
    expect(viewport).not.toBe(container);
    expect(viewport).not.toBe(outer);
    expect(outer.contains(viewport as Node)).toBe(true);
  });

  it("DoD-13: unmounting leaves no viewport attached", () => {
    const state = primedState();
    const { unmount } = renderWithProviders(<MessageList state={state} />);
    expect(state.transcriptViewport).not.toBeNull();

    unmount();

    expect(state.transcriptViewport).toBeNull();
  });
});
