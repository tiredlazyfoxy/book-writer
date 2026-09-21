/**
 * Side-chat grouping — 027.side-chats / 004.side-chat-api-and-grouping,
 * DoD-2 · DoD-3 · DoD-4 · DoD-5 · DoD-6 · DoD-7 · DoD-8 · DoD-9 · DoD-10.
 * (DoD-1 is the api module's — `tests/work/sideChatApi.test.ts`.)
 *
 * A state-only spec (no rendering): construct `ChatPaneState`, seed via `runInAction`
 * (`chats` with `active_side_chat_id`, `activeChatId`, `messages` with `side_chat_id`,
 * `messagesStatus`, `turnStatus`) and read the computeds — the pane specs' idiom
 * (`context.md` -> "Shared frontend facts").
 *
 * Bound to the frozen step-004 skeleton (status.md -> `## Skeleton`):
 *   RenderedMessage.sideChatId: string | null
 *   type RenderedTranscriptMessageItem  = { kind: "message"; message: RenderedMessage }
 *   type RenderedTranscriptSideChatItem = { kind: "sideChat"; sideChatId; messages; active; expanded }
 *   type RenderedTranscriptItem = RenderedTranscriptMessageItem | RenderedTranscriptSideChatItem
 *   ChatPaneState.expandedSideChats: Record<string, boolean>
 *   get activeSideChatId(): string | null
 *   get renderedTranscript(): RenderedTranscriptItem[]
 *   toggleSideChatGroup(state, sideChatId): void
 *
 * Expected values come from the spec (`004.md` Interface intent + DoD; `context.md`
 * D-B, D-F), never from code:
 *   - a row with a null `side_chat_id` is an ordinary `message` item (US-139.AC-1);
 *   - a contiguous run sharing a non-null `side_chat_id` is ONE `sideChat` item, its
 *     `messages` in position order (US-135.AC-1, D-B);
 *   - a run breaks on ANY change of id — `A -> B` with no main-line row between is two
 *     groups (FEAT-022 note D5);
 *   - the active group (`sideChatId === activeSideChatId`) is `active: true` and ALWAYS
 *     `expanded: true` (UC-110 step 3); a finished group is `active: false` and reads
 *     `expandedSideChats[id] ?? false` — collapsed by default (US-137.AC-1);
 *   - `toggleSideChatGroup` flips one group's `expanded`, others untouched
 *     (US-137.AC-2, UC-111 step 3);
 *   - the streaming placeholder carries `activeSideChatId`, so while a side chat is
 *     active the in-flight bubble is the LAST message INSIDE the active group; with no
 *     side chat active it stays a trailing `message` item (UC-110 step 3);
 *   - `activeSideChatId` is the active chat's `active_side_chat_id`, `null` with no
 *     active chat or a null field (D-F).
 *
 * `globals: false`: every primitive is imported explicitly.
 */
import { describe, expect, it, vi } from "vitest";
import { runInAction } from "mobx";
import type {
  ChatMessageResponse,
  ChatResponse,
  ChatSamplingParams,
} from "../../src/types/chats";
import type {
  RenderedTranscriptItem,
  RenderedTranscriptMessageItem,
  RenderedTranscriptSideChatItem,
} from "../../src/work/components/chat/chatPaneState";
import {
  ChatPaneState,
  toggleSideChatGroup,
} from "../../src/work/components/chat/chatPaneState";

// The api module the state layer imports: whole-module factory, EVERY export enumerated
// (the step-004 list — the four new side-chat functions included). Mock completeness
// only; nothing in this file calls or asserts on it.
vi.mock("../../src/api/chats", () => ({
  listChats: vi.fn(),
  createChat: vi.fn(),
  updateChat: vi.fn(),
  getChat: vi.fn(),
  listModelOptions: vi.fn(),
  titleChat: vi.fn(),
  startSideChat: vi.fn(),
  finishSideChat: vi.fn(),
  injectSideChat: vi.fn(),
  deleteSideChat: vi.fn(),
  streamChatTurn: vi.fn(),
}));

const BOOK_ID = "bk-1";
const CHAT_ID = "c-1";
const SIDE_A = "sc-A";
const SIDE_B = "sc-B";

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

function makeChat(activeSideChatId: string | null, id: string = CHAT_ID): ChatResponse {
  return {
    id,
    book_id: BOOK_ID,
    author_id: "u-1",
    title: "Chat one",
    llm_server_id: "s-1",
    model_name: "m-1",
    sampling: makeSampling(),
    archived: false,
    created_at: "2026-01-01T00:00:00Z",
    modified_at: "2026-01-01T00:00:00Z",
    active_side_chat_id: activeSideChatId,
  };
}

function makeMessage(
  id: string,
  position: number,
  sideChatId: string | null,
  role: string = position % 2 === 0 ? "user" : "assistant",
): ChatMessageResponse {
  return {
    id,
    chat_id: CHAT_ID,
    role,
    content: `content of ${id}`,
    reasoning: null,
    position,
    created_at: "2026-01-01T00:00:00Z",
    side_chat_id: sideChatId,
    tool_trace: null,
  };
}

/**
 * Build a position-ordered message list from a shorthand: each entry is the
 * `side_chat_id` of that row (`null` = main line). Ids are `m-0`, `m-1`, … in order.
 */
function messagesFrom(shape: Array<string | null>): ChatMessageResponse[] {
  return shape.map((sideChatId, index) => makeMessage(`m-${index}`, index, sideChatId));
}

/** Seed an active chat with a ready message history and an idle turn. */
function seed(
  state: ChatPaneState,
  messages: ChatMessageResponse[],
  activeSideChatId: string | null,
  turnStatus: "idle" | "streaming" = "idle",
): void {
  runInAction(() => {
    state.chats = [makeChat(activeSideChatId)];
    state.activeChatId = CHAT_ID;
    state.messages = messages;
    state.messagesStatus = "ready";
    state.turnStatus = turnStatus;
    state.turnError = null;
    state.streamingContent = "";
    state.streamingThinking = "";
  });
}

/** Narrow a transcript item to a group, failing loudly if it is not one. */
function asGroup(item: RenderedTranscriptItem): RenderedTranscriptSideChatItem {
  expect(item.kind).toBe("sideChat");
  if (item.kind !== "sideChat") throw new Error("expected a sideChat item");
  return item;
}

/** Narrow a transcript item to a main-line row, failing loudly if it is not one. */
function asMessage(item: RenderedTranscriptItem): RenderedTranscriptMessageItem {
  expect(item.kind).toBe("message");
  if (item.kind !== "message") throw new Error("expected a message item");
  return item;
}

/** The `kind` sequence of a transcript — the shape every grouping case asserts on. */
function kindsOf(items: RenderedTranscriptItem[]): string[] {
  return items.map((item) => item.kind);
}

describe("RenderedMessage.sideChatId mirrors the row's side_chat_id (DoD-2)", () => {
  it("DoD-2: a main-line row renders sideChatId null and a side-chat row renders the row's id", () => {
    const state = new ChatPaneState();
    seed(state, [makeMessage("m-0", 0, null), makeMessage("m-1", 1, SIDE_A)], null);

    const rendered = state.renderedMessages;
    expect(rendered).toHaveLength(2);
    expect(rendered[0].key).toBe("m-0");
    expect(rendered[0].sideChatId).toBeNull();
    expect(rendered[1].key).toBe("m-1");
    expect(rendered[1].sideChatId).toBe(SIDE_A);
  });
});

describe("renderedTranscript groups contiguous runs (DoD-3)", () => {
  it("DoD-3: [main, main, A, A, main, B, B, B] yields message, message, sideChat(A,2), message, sideChat(B,3) in order, each group's messages in position order (US-135.AC-1, US-139.AC-1)", () => {
    const state = new ChatPaneState();
    seed(state, messagesFrom([null, null, SIDE_A, SIDE_A, null, SIDE_B, SIDE_B, SIDE_B]), null);

    const items = state.renderedTranscript;
    expect(kindsOf(items)).toEqual(["message", "message", "sideChat", "message", "sideChat"]);

    expect(asMessage(items[0]).message.key).toBe("m-0");
    expect(asMessage(items[1]).message.key).toBe("m-1");

    const groupA = asGroup(items[2]);
    expect(groupA.sideChatId).toBe(SIDE_A);
    expect(groupA.messages).toHaveLength(2);
    expect(groupA.messages.map((m) => m.key)).toEqual(["m-2", "m-3"]);
    expect(groupA.messages.every((m) => m.sideChatId === SIDE_A)).toBe(true);

    expect(asMessage(items[3]).message.key).toBe("m-4");

    const groupB = asGroup(items[4]);
    expect(groupB.sideChatId).toBe(SIDE_B);
    expect(groupB.messages).toHaveLength(3);
    expect(groupB.messages.map((m) => m.key)).toEqual(["m-5", "m-6", "m-7"]);
    expect(groupB.messages.every((m) => m.sideChatId === SIDE_B)).toBe(true);
  });

  it("DoD-3: a group carries the SAME rendered entries renderedMessages yields (value-equal, every per-message derivation intact — not a reduced form)", () => {
    const state = new ChatPaneState();
    seed(state, messagesFrom([null, SIDE_A, SIDE_A]), null);

    // Two independent reads of MobX computeds: assert value equality, never object
    // identity — an unobserved computed recomputes per access, and DoD-3 constrains the
    // transcript's shape and ordering, not the lifetime of the objects in it.
    const rendered = state.renderedMessages;
    const items = state.renderedTranscript;
    expect(kindsOf(items)).toEqual(["message", "sideChat"]);
    expect(asMessage(items[0]).message).toEqual(rendered[0]);
    const group = asGroup(items[1]);
    expect(group.messages).toHaveLength(2);
    expect(group.messages[0]).toEqual(rendered[1]);
    expect(group.messages[1]).toEqual(rendered[2]);

    // The per-message fields a row is rendered from survive grouping, spelled out from
    // the seeded rows rather than by comparison alone.
    expect(group.messages.map((m) => m.key)).toEqual(["m-1", "m-2"]);
    expect(group.messages.map((m) => m.content)).toEqual([
      "content of m-1",
      "content of m-2",
    ]);
    expect(group.messages.map((m) => m.role)).toEqual(["assistant", "user"]);
    expect(group.messages.every((m) => m.streaming)).toBe(false);
    expect(group.messages.map((m) => m.sideChatId)).toEqual([SIDE_A, SIDE_A]);
  });
});

describe("adjacent runs with different ids are separate groups (DoD-4)", () => {
  it("DoD-4: [A, A, B, B] produces TWO sideChat items, not one (FEAT-022 note D5)", () => {
    const state = new ChatPaneState();
    seed(state, messagesFrom([SIDE_A, SIDE_A, SIDE_B, SIDE_B]), null);

    const items = state.renderedTranscript;
    expect(kindsOf(items)).toEqual(["sideChat", "sideChat"]);

    const first = asGroup(items[0]);
    expect(first.sideChatId).toBe(SIDE_A);
    expect(first.messages.map((m) => m.key)).toEqual(["m-0", "m-1"]);

    const second = asGroup(items[1]);
    expect(second.sideChatId).toBe(SIDE_B);
    expect(second.messages.map((m) => m.key)).toEqual(["m-2", "m-3"]);
  });

  it("DoD-4: [main, A, A, B, B, main] keeps the two groups apart between the main-line rows", () => {
    const state = new ChatPaneState();
    seed(state, messagesFrom([null, SIDE_A, SIDE_A, SIDE_B, SIDE_B, null]), null);

    const items = state.renderedTranscript;
    expect(kindsOf(items)).toEqual(["message", "sideChat", "sideChat", "message"]);
    expect(asGroup(items[1]).sideChatId).toBe(SIDE_A);
    expect(asGroup(items[1]).messages).toHaveLength(2);
    expect(asGroup(items[2]).sideChatId).toBe(SIDE_B);
    expect(asGroup(items[2]).messages).toHaveLength(2);
    expect(asMessage(items[3]).message.key).toBe("m-5");
  });
});

describe("the active group is active and always expanded (DoD-5)", () => {
  it("DoD-5: the group whose id is activeSideChatId has active: true and expanded: true when expandedSideChats has no entry for it (UC-110 step 3)", () => {
    const state = new ChatPaneState();
    seed(state, messagesFrom([null, SIDE_A, SIDE_A]), SIDE_A);

    const items = state.renderedTranscript;
    expect(kindsOf(items)).toEqual(["message", "sideChat"]);
    const group = asGroup(items[1]);
    expect(group.sideChatId).toBe(SIDE_A);
    expect(group.active).toBe(true);
    expect(group.expanded).toBe(true);
  });

  it("DoD-5: the active group stays expanded: true even when expandedSideChats[id] is explicitly false", () => {
    const state = new ChatPaneState();
    seed(state, messagesFrom([null, SIDE_A, SIDE_A]), SIDE_A);
    runInAction(() => {
      state.expandedSideChats = { [SIDE_A]: false };
    });

    const group = asGroup(state.renderedTranscript[1]);
    expect(group.active).toBe(true);
    expect(group.expanded).toBe(true);
  });

  it("DoD-5: with a finished group and the active group in the same transcript, only the active one is active", () => {
    const state = new ChatPaneState();
    seed(state, messagesFrom([SIDE_A, SIDE_A, null, SIDE_B, SIDE_B]), SIDE_B);

    const items = state.renderedTranscript;
    expect(kindsOf(items)).toEqual(["sideChat", "message", "sideChat"]);
    const finished = asGroup(items[0]);
    expect(finished.sideChatId).toBe(SIDE_A);
    expect(finished.active).toBe(false);
    const active = asGroup(items[2]);
    expect(active.sideChatId).toBe(SIDE_B);
    expect(active.active).toBe(true);
    expect(active.expanded).toBe(true);
  });
});

describe("a finished group is inactive and collapsed by default (DoD-6)", () => {
  it("DoD-6: a group whose id is not the active one has active: false and expanded: false with no toggle (US-137.AC-1)", () => {
    const state = new ChatPaneState();
    seed(state, messagesFrom([null, SIDE_A, SIDE_A, null]), null);

    const items = state.renderedTranscript;
    expect(kindsOf(items)).toEqual(["message", "sideChat", "message"]);
    const group = asGroup(items[1]);
    expect(group.sideChatId).toBe(SIDE_A);
    expect(group.active).toBe(false);
    expect(group.expanded).toBe(false);
  });

  it("DoD-6: a finished group stays collapsed by default while a different side chat is active", () => {
    const state = new ChatPaneState();
    seed(state, messagesFrom([SIDE_A, SIDE_A, null, SIDE_B]), SIDE_B);

    const finished = asGroup(state.renderedTranscript[0]);
    expect(finished.sideChatId).toBe(SIDE_A);
    expect(finished.active).toBe(false);
    expect(finished.expanded).toBe(false);
  });
});

describe("toggleSideChatGroup flips one group's expansion (DoD-7)", () => {
  it("DoD-7: one call expands the group, a second call collapses it again (US-137.AC-2, UC-111 step 3)", () => {
    const state = new ChatPaneState();
    seed(state, messagesFrom([null, SIDE_A, SIDE_A]), null);

    expect(asGroup(state.renderedTranscript[1]).expanded).toBe(false);

    toggleSideChatGroup(state, SIDE_A);
    expect(asGroup(state.renderedTranscript[1]).expanded).toBe(true);
    expect(state.expandedSideChats[SIDE_A]).toBe(true);

    toggleSideChatGroup(state, SIDE_A);
    expect(asGroup(state.renderedTranscript[1]).expanded).toBe(false);
    expect(state.expandedSideChats[SIDE_A]).toBe(false);
  });

  it("DoD-7: toggling one finished group leaves the other groups unaffected", () => {
    const state = new ChatPaneState();
    seed(state, messagesFrom([SIDE_A, SIDE_A, null, SIDE_B, SIDE_B]), null);

    toggleSideChatGroup(state, SIDE_A);

    const items = state.renderedTranscript;
    expect(kindsOf(items)).toEqual(["sideChat", "message", "sideChat"]);
    expect(asGroup(items[0]).sideChatId).toBe(SIDE_A);
    expect(asGroup(items[0]).expanded).toBe(true);
    expect(asGroup(items[2]).sideChatId).toBe(SIDE_B);
    expect(asGroup(items[2]).expanded).toBe(false);

    // Expanding B afterwards does not collapse A.
    toggleSideChatGroup(state, SIDE_B);
    expect(asGroup(state.renderedTranscript[0]).expanded).toBe(true);
    expect(asGroup(state.renderedTranscript[2]).expanded).toBe(true);

    // Collapsing A afterwards does not collapse B.
    toggleSideChatGroup(state, SIDE_A);
    expect(asGroup(state.renderedTranscript[0]).expanded).toBe(false);
    expect(asGroup(state.renderedTranscript[2]).expanded).toBe(true);
  });

  it("DoD-7: the toggle writes a new expandedSideChats object rather than mutating a key in place", () => {
    const state = new ChatPaneState();
    seed(state, messagesFrom([SIDE_A]), null);
    const before = state.expandedSideChats;

    toggleSideChatGroup(state, SIDE_A);

    expect(state.expandedSideChats).not.toBe(before);
    expect(state.expandedSideChats[SIDE_A]).toBe(true);
  });
});

describe("the streaming placeholder lands inside the active group (DoD-8)", () => {
  it("DoD-8: while streaming with a side chat active, the in-flight bubble is the LAST message inside the active group and there is no trailing message item (UC-110 step 3)", () => {
    const state = new ChatPaneState();
    seed(state, messagesFrom([null, SIDE_A, SIDE_A]), SIDE_A, "streaming");
    runInAction(() => {
      state.streamingContent = "partial";
    });

    const items = state.renderedTranscript;
    expect(kindsOf(items)).toEqual(["message", "sideChat"]);

    const group = asGroup(items[1]);
    expect(group.sideChatId).toBe(SIDE_A);
    expect(group.active).toBe(true);
    expect(group.messages).toHaveLength(3);
    expect(group.messages.map((m) => m.key).slice(0, 2)).toEqual(["m-1", "m-2"]);
    const last = group.messages[group.messages.length - 1];
    expect(last.streaming).toBe(true);
    expect(last.sideChatId).toBe(SIDE_A);
    expect(last.content).toBe("partial");
  });

  it("DoD-8: while streaming with a side chat active that has no rows yet, the in-flight bubble opens the active group on its own", () => {
    const state = new ChatPaneState();
    seed(state, messagesFrom([null, null]), SIDE_A, "streaming");

    const items = state.renderedTranscript;
    expect(kindsOf(items)).toEqual(["message", "message", "sideChat"]);
    const group = asGroup(items[2]);
    expect(group.sideChatId).toBe(SIDE_A);
    expect(group.active).toBe(true);
    expect(group.expanded).toBe(true);
    expect(group.messages).toHaveLength(1);
    expect(group.messages[0].streaming).toBe(true);
  });

  it("DoD-8: while streaming with NO side chat active, the in-flight bubble is a trailing message item, outside any group", () => {
    const state = new ChatPaneState();
    seed(state, messagesFrom([null, SIDE_A, SIDE_A, null]), null, "streaming");

    const items = state.renderedTranscript;
    expect(kindsOf(items)).toEqual(["message", "sideChat", "message", "message"]);
    const finished = asGroup(items[1]);
    expect(finished.messages).toHaveLength(2);
    expect(finished.messages.some((m) => m.streaming)).toBe(false);
    const trailing = asMessage(items[items.length - 1]).message;
    expect(trailing.streaming).toBe(true);
    expect(trailing.sideChatId).toBeNull();
  });

  it("DoD-8: while streaming with no side chat active and a finished group last, the bubble is NOT appended to that finished group", () => {
    const state = new ChatPaneState();
    seed(state, messagesFrom([null, SIDE_A, SIDE_A]), null, "streaming");

    const items = state.renderedTranscript;
    expect(kindsOf(items)).toEqual(["message", "sideChat", "message"]);
    expect(asGroup(items[1]).messages).toHaveLength(2);
    expect(asMessage(items[2]).message.streaming).toBe(true);
  });
});

describe("activeSideChatId follows the active chat (DoD-9)", () => {
  it("DoD-9: activeSideChatId is the active chat's active_side_chat_id (D-F)", () => {
    const state = new ChatPaneState();
    seed(state, [], SIDE_A);

    expect(state.activeSideChatId).toBe(SIDE_A);
  });

  it("DoD-9: activeSideChatId is null when the active chat's field is null", () => {
    const state = new ChatPaneState();
    seed(state, [], null);

    expect(state.activeSideChatId).toBeNull();
  });

  it("DoD-9: activeSideChatId is null when there is no active chat, even if some chat in the list has a side chat active", () => {
    const state = new ChatPaneState();
    runInAction(() => {
      state.chats = [makeChat(SIDE_A)];
      state.activeChatId = null;
      state.messages = [];
      state.messagesStatus = "ready";
    });

    expect(state.activeSideChatId).toBeNull();
  });

  it("DoD-9: activeSideChatId reads the ACTIVE chat's field, not another chat's", () => {
    const state = new ChatPaneState();
    runInAction(() => {
      state.chats = [makeChat(SIDE_A, "c-other"), makeChat(SIDE_B, CHAT_ID)];
      state.activeChatId = CHAT_ID;
      state.messages = [];
      state.messagesStatus = "ready";
    });

    expect(state.activeSideChatId).toBe(SIDE_B);
  });
});

describe("a transcript with no side-chat rows is unchanged (DoD-10)", () => {
  it("DoD-10: a list with no side-chat rows yields only message items, one per row, in order (US-095.AC-2)", () => {
    const state = new ChatPaneState();
    seed(state, messagesFrom([null, null, null, null]), null);

    const items = state.renderedTranscript;
    expect(items).toHaveLength(4);
    expect(kindsOf(items)).toEqual(["message", "message", "message", "message"]);
    expect(items.map((item) => asMessage(item).message.key)).toEqual(["m-0", "m-1", "m-2", "m-3"]);
    expect(items.every((item) => asMessage(item).message.sideChatId === null)).toBe(true);
  });

  it("DoD-10: an empty message list yields an empty transcript", () => {
    const state = new ChatPaneState();
    seed(state, [], null);

    expect(state.renderedTranscript).toEqual([]);
  });
});
