/**
 * MessageList — side-chat groups in the transcript — 027.side-chats /
 * 006.side-chat-group-rendering, DoD-1 · DoD-7 · DoD-8 · DoD-9.
 * (DoD-2..DoD-6 are the group's own — `tests/work/SideChatGroup.test.tsx`.)
 *
 * Bound to the frozen step-006 skeleton (status.md -> `## Skeleton`):
 *   interface MessageListProps { state: ChatPaneState; bookId?: string }  -> MessageList
 * `MessageList` maps `state.renderedTranscript` (step 004) and branches on `kind`:
 * `message` -> `MessageRow`, `sideChat` -> `SideChatGroup`.
 *
 * Expected values come from the spec (`006.md` Interface intent + DoD; `context.md` D-B,
 * D-F, "Testing facts"; `006.context.md`), never from code:
 *   - a side-chat run is ONE element `role="group"` named `Side chat`; every message of the
 *     run renders INSIDE it, main-line messages OUTSIDE it (US-135.AC-1);
 *   - rows with a null `side_chat_id` — injected rows included — are ordinary rows: no
 *     group, no `Inject side chat` / `Delete side chat` control anywhere (US-139.AC-3);
 *   - with no side-chat rows the list renders as before: the user's text in a
 *     `data-role="user"` box, assistant markdown in a `data-role="assistant"` block, and
 *     the ThinkingBlock control for a row with reasoning (US-095.AC-2 — regression);
 *   - while streaming with a side chat active, the in-flight bubble renders INSIDE the
 *     active group (UC-110 step 3).
 *
 * Queries by role + accessible name and by text only — never by test id; `data-role` is
 * the existing regression handle the step keeps (006.context.md). `globals: false`.
 */
import { describe, expect, it, vi } from "vitest";
import { runInAction } from "mobx";
import { screen, within } from "@testing-library/react";
import type {
  ChatMessageResponse,
  ChatResponse,
  ChatSamplingParams,
} from "../../src/types/chats";
import { ChatPaneState } from "../../src/work/components/chat/chatPaneState";
import { MessageList } from "../../src/work/components/chat/MessageList";
import { renderWithProviders } from "../support/render";

// The api module the state layer imports: whole-module factory, EVERY export enumerated
// (the step-004 list — the four side-chat functions and `getChat` included). Mock
// completeness only; nothing in this file calls or asserts on it.
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

function makeChat(activeSideChatId: string | null): ChatResponse {
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
    active_side_chat_id: activeSideChatId,
  };
}

function makeMessage(
  id: string,
  role: string,
  content: string,
  position: number,
  sideChatId: string | null,
  reasoning: string | null = null,
): ChatMessageResponse {
  return {
    id,
    chat_id: CHAT_ID,
    role,
    content,
    reasoning,
    position,
    created_at: "2026-01-01T00:00:00Z",
    side_chat_id: sideChatId,
    tool_trace: null,
  };
}

/** Seed an active chat with a ready message history. */
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
    state.liveThinkingExpanded = false;
  });
}

describe("a side-chat run renders as one group with its messages inside (DoD-1)", () => {
  it("DoD-1: [main, main, A, A, main] renders exactly one role=group named Side chat; both A messages are inside it, the three main-line messages are outside it (US-135.AC-1)", () => {
    const state = new ChatPaneState();
    seed(
      state,
      [
        makeMessage("m-0", "user", "main-one", 0, null),
        makeMessage("m-1", "assistant", "main-two", 1, null),
        makeMessage("m-2", "user", "side-a-one", 2, SIDE_A),
        makeMessage("m-3", "assistant", "side-a-two", 3, SIDE_A),
        makeMessage("m-4", "user", "main-three", 4, null),
      ],
      // The active group is expanded (UC-110 step 3), so its messages are visible.
      SIDE_A,
    );

    renderWithProviders(<MessageList state={state} bookId={BOOK_ID} />);

    const groups = screen.getAllByRole("group", { name: "Side chat" });
    expect(groups).toHaveLength(1);
    const group = groups[0];

    // Every message of the run is inside the group.
    expect(within(group).getByText("side-a-one")).toBeInTheDocument();
    expect(within(group).getByText("side-a-two")).toBeInTheDocument();

    // Main-line messages are present, and NOT inside the group.
    for (const content of ["main-one", "main-two", "main-three"]) {
      const el = screen.getByText(content);
      expect(el).toBeInTheDocument();
      expect(group.contains(el)).toBe(false);
    }
  });

  it("DoD-1: a finished run is also one group named Side chat; expanded via its control, its messages are inside it and the main line stays outside (US-135.AC-1)", () => {
    const state = new ChatPaneState();
    seed(
      state,
      [
        makeMessage("m-0", "user", "main-one", 0, null),
        makeMessage("m-1", "user", "side-a-one", 1, SIDE_A),
        makeMessage("m-2", "assistant", "side-a-two", 2, SIDE_A),
        makeMessage("m-3", "user", "main-three", 3, null),
      ],
      null,
    );
    // Expand the finished group up front through its state slot (step 004's contract).
    runInAction(() => {
      state.expandedSideChats = { [SIDE_A]: true };
    });

    renderWithProviders(<MessageList state={state} bookId={BOOK_ID} />);

    const groups = screen.getAllByRole("group", { name: "Side chat" });
    expect(groups).toHaveLength(1);
    const group = groups[0];
    expect(within(group).getByText("side-a-one")).toBeInTheDocument();
    expect(within(group).getByText("side-a-two")).toBeInTheDocument();
    expect(group.contains(screen.getByText("main-one"))).toBe(false);
    expect(group.contains(screen.getByText("main-three"))).toBe(false);
  });
});

describe("null side_chat_id rows are ordinary rows (DoD-7)", () => {
  it("DoD-7: a transcript whose rows all carry side_chat_id null — as injected rows do — renders no group and no Inject / Delete control (US-139.AC-3)", () => {
    const state = new ChatPaneState();
    seed(
      state,
      [
        makeMessage("m-0", "user", "main-one", 0, null),
        makeMessage("m-1", "assistant", "formerly-side-one", 1, null),
        makeMessage("m-2", "user", "formerly-side-two", 2, null),
        makeMessage("m-3", "assistant", "main-four", 3, null),
      ],
      null,
    );

    renderWithProviders(<MessageList state={state} bookId={BOOK_ID} />);

    expect(screen.queryByRole("group", { name: "Side chat" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Inject side chat" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Delete side chat" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Expand side chat" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Collapse side chat" })).toBeNull();
    expect(screen.queryByText(/Side chat/)).toBeNull();

    // Every row is still rendered, in order.
    for (const content of ["main-one", "formerly-side-one", "formerly-side-two", "main-four"]) {
      expect(screen.getByText(content)).toBeInTheDocument();
    }
  });

  it("DoD-7: main-line rows beside a real group are not inside any group and carry no controls of their own (US-139.AC-3)", () => {
    const state = new ChatPaneState();
    seed(
      state,
      [
        makeMessage("m-0", "user", "main-one", 0, null),
        makeMessage("m-1", "user", "side-a-one", 1, SIDE_A),
        makeMessage("m-2", "assistant", "side-a-two", 2, SIDE_A),
        makeMessage("m-3", "user", "injected-back", 3, null),
      ],
      null,
    );

    renderWithProviders(<MessageList state={state} bookId={BOOK_ID} />);

    // Exactly one group, and exactly one pair of controls — the group's own.
    const groups = screen.getAllByRole("group", { name: "Side chat" });
    expect(groups).toHaveLength(1);
    const group = groups[0];
    expect(screen.getAllByRole("button", { name: "Inject side chat" })).toHaveLength(1);
    expect(screen.getAllByRole("button", { name: "Delete side chat" })).toHaveLength(1);
    expect(group.contains(screen.getByRole("button", { name: "Inject side chat" }))).toBe(true);
    expect(group.contains(screen.getByRole("button", { name: "Delete side chat" }))).toBe(true);

    // The main-line rows sit outside the group.
    expect(group.contains(screen.getByText("main-one"))).toBe(false);
    expect(group.contains(screen.getByText("injected-back"))).toBe(false);
  });
});

describe("a transcript with no side-chat rows renders exactly as before (DoD-8)", () => {
  it("DoD-8: the user's text is in a data-role=user box and the assistant's markdown in a data-role=assistant block (US-095.AC-2 — regression)", () => {
    const state = new ChatPaneState();
    seed(
      state,
      [
        makeMessage("m-0", "user", "**user-literal**", 0, null),
        makeMessage("m-1", "assistant", "**bold-reply**", 1, null),
      ],
      null,
    );

    const { container } = renderWithProviders(<MessageList state={state} bookId={BOOK_ID} />);

    const userBox = container.querySelector('[data-role="user"]');
    expect(userBox).not.toBeNull();
    // The author's own message is plain text: the literal asterisks survive.
    expect(userBox?.textContent ?? "").toContain("**user-literal**");

    const assistantBlock = container.querySelector('[data-role="assistant"]');
    expect(assistantBlock).not.toBeNull();
    // Assistant content goes through markdown: the emphasis becomes a <strong>.
    const strongs = Array.from(assistantBlock?.querySelectorAll("strong") ?? []).map(
      (s) => s.textContent,
    );
    expect(strongs).toContain("bold-reply");
    expect(strongs).not.toContain("user-literal");

    // Position order is kept: user (0) before assistant (1).
    const text = container.textContent ?? "";
    expect(text.indexOf("user-literal")).toBeLessThan(text.indexOf("bold-reply"));

    // And no side-chat chrome appears anywhere.
    expect(screen.queryByRole("group", { name: "Side chat" })).toBeNull();
  });

  it("DoD-8: an assistant row with reasoning shows the ThinkingBlock control (US-095.AC-2 — regression)", () => {
    const state = new ChatPaneState();
    seed(
      state,
      [
        makeMessage("m-0", "user", "the-question", 0, null),
        makeMessage("m-1", "assistant", "the-visible-answer", 1, null, "the-hidden-reasoning"),
      ],
      null,
    );

    const { container } = renderWithProviders(<MessageList state={state} bookId={BOOK_ID} />);

    expect(screen.getByText("the-visible-answer")).toBeInTheDocument();
    // The thinking control is present, inside the assistant block.
    const label = screen.getByText(/thinking/i);
    const control = label.closest("button") ?? label;
    expect(control).toBeInTheDocument();
    const assistantBlock = container.querySelector('[data-role="assistant"]');
    expect(assistantBlock).not.toBeNull();
    expect(assistantBlock?.contains(control)).toBe(true);
  });

  it("DoD-8: a row without reasoning shows no ThinkingBlock control (US-095.AC-2 — regression)", () => {
    const state = new ChatPaneState();
    seed(state, [makeMessage("m-0", "assistant", "plain-answer", 0, null)], null);

    renderWithProviders(<MessageList state={state} bookId={BOOK_ID} />);

    expect(screen.getByText("plain-answer")).toBeInTheDocument();
    expect(screen.queryByText(/thinking/i)).toBeNull();
  });
});

describe("the in-flight bubble renders inside the active group (DoD-9)", () => {
  it("DoD-9: while streaming with side chat A active, the streaming content is inside the Side chat group (UC-110 step 3)", () => {
    const state = new ChatPaneState();
    seed(
      state,
      [
        makeMessage("m-0", "user", "main-one", 0, null),
        makeMessage("m-1", "user", "side-a-question", 1, SIDE_A),
      ],
      SIDE_A,
      "streaming",
    );
    runInAction(() => {
      state.streamingContent = "partial-reply-so-far";
    });

    renderWithProviders(<MessageList state={state} bookId={BOOK_ID} />);

    const groups = screen.getAllByRole("group", { name: "Side chat" });
    expect(groups).toHaveLength(1);
    const group = groups[0];
    expect(within(group).getByText(/partial-reply-so-far/)).toBeInTheDocument();
    expect(within(group).getByText("side-a-question")).toBeInTheDocument();
    expect(group.contains(screen.getByText("main-one"))).toBe(false);
  });

  it("DoD-9: while streaming with side chat A active and no A rows yet, the bubble alone opens the group and renders inside it (UC-110 step 3)", () => {
    const state = new ChatPaneState();
    seed(state, [makeMessage("m-0", "user", "main-one", 0, null)], SIDE_A, "streaming");
    runInAction(() => {
      state.streamingContent = "first-side-words";
    });

    renderWithProviders(<MessageList state={state} bookId={BOOK_ID} />);

    const group = screen.getByRole("group", { name: "Side chat" });
    expect(within(group).getByText(/first-side-words/)).toBeInTheDocument();
    expect(group.contains(screen.getByText("main-one"))).toBe(false);
  });

  it("DoD-9: while streaming with NO side chat active, the bubble renders outside any group (UC-110 step 3 — the contrast)", () => {
    const state = new ChatPaneState();
    seed(
      state,
      [
        makeMessage("m-0", "user", "main-one", 0, null),
        makeMessage("m-1", "user", "side-a-question", 1, SIDE_A),
        makeMessage("m-2", "user", "main-two", 2, null),
      ],
      null,
      "streaming",
    );
    runInAction(() => {
      state.streamingContent = "main-line-reply";
    });

    renderWithProviders(<MessageList state={state} bookId={BOOK_ID} />);

    const group = screen.getByRole("group", { name: "Side chat" });
    const bubble = screen.getByText(/main-line-reply/);
    expect(group.contains(bubble)).toBe(false);
  });
});
