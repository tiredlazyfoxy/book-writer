/**
 * Chat conversation — component-level rendering — 011.chat-panel / 005,
 * DoD-1 · DoD-2 · DoD-3 · DoD-4 · DoD-6 · DoD-8.
 *
 * Bound to the frozen step-005 skeleton (status.md -> `## Skeleton`):
 *   interface MessageListProps { state: ChatPaneState }         -> MessageList
 *   interface ThinkingBlockProps { text; expanded; onToggle }   -> ThinkingBlock (controlled)
 *   interface ComposerProps { state; onSend; onStop; onRetry }  -> Composer
 *   ChatPaneState fields: messages/messagesStatus; streamingContent; streamingThinking;
 *     turnStatus ("idle"|"streaming"|"error"); turnError; liveThinkingExpanded;
 *     expandedReasoning; pendingPrompt; get renderedMessages; get retryOffered
 *
 * The air gap: expected values come from the spec (`005.md` DoD + Interface intent,
 * `005.context.md` react-markdown note + frame->state map, UC-081 / US-095.AC-2 /
 * US-058 / UC-056), never from code. `../../src/api/chats` is mocked module-factory
 * form; these render tests set observable state directly and never hit the network.
 * Assistant content renders as markdown (react-markdown, first use repo-wide);
 * the author's own messages are plain text. `globals: false`.
 */
import { describe, expect, it, vi } from "vitest";
import { runInAction } from "mobx";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type {
  ChatMessageResponse,
  ChatResponse,
  ChatSamplingParams,
} from "../../src/types/chats";
import { ChatPaneState } from "../../src/work/components/chat/chatPaneState";
import { MessageList } from "../../src/work/components/chat/MessageList";
import { ThinkingBlock } from "../../src/work/components/chat/ThinkingBlock";
import { Composer } from "../../src/work/components/chat/Composer";
import { renderWithProviders } from "../support/render";

// `titleChat` added by 023.chat-ux-revision so the whole-module factory keeps the
// module's shape intact (the pane state now imports it for the post-turn title
// refresh). MOCK COMPLETENESS ONLY — nothing in this file asserts on it, and no
// assertion here changed.
vi.mock("../../src/api/chats", () => ({
  listChats: vi.fn(),
  createChat: vi.fn(),
  updateChat: vi.fn(),
  getChat: vi.fn(),
  listModelOptions: vi.fn(),
  streamChatTurn: vi.fn(),
  titleChat: vi.fn(),
}));

const BOOK_ID = "bk-1";
const CHAT_ID = "c-1";

function makeSampling(overrides: Partial<ChatSamplingParams> = {}): ChatSamplingParams {
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
    ...overrides,
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

function makeMessage(
  id: string,
  role: string,
  content: string,
  position: number,
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
  };
}

const CHAT = makeChat();

/** True only if the text is present in the DOM *and* not hidden by an ancestor. */
function reasoningShown(text: string): boolean {
  const el = screen.queryByText(text);
  let node: HTMLElement | null = el;
  while (node) {
    if (node.hidden) return false;
    const style = window.getComputedStyle(node);
    if (style.display === "none" || style.visibility === "hidden") return false;
    node = node.parentElement;
  }
  return el !== null;
}

describe("a reopened chat renders stored messages, ordered, user vs assistant distinguishable (DoD-1)", () => {
  it("DoD-1: assistant content is markdown, user content is plain, and they render in position order (UC-081, US-095.AC-2, US-058.AC-2)", () => {
    const state = new ChatPaneState();
    const userMsg = makeMessage("m-1", "user", "**user-literal**", 0);
    const assistantMsg = makeMessage("m-2", "assistant", "**bold-reply**", 1);
    runInAction(() => {
      state.chats = [CHAT];
      state.activeChatId = CHAT_ID;
      state.messages = [userMsg, assistantMsg];
      state.messagesStatus = "ready";
      state.turnStatus = "idle";
    });

    const { container } = renderWithProviders(<MessageList state={state} />);

    const strongs = Array.from(container.querySelectorAll("strong")).map((s) => s.textContent);
    // Assistant content is rendered THROUGH react-markdown -> its emphasis becomes a <strong>.
    expect(strongs).toContain("bold-reply");
    // The author's own message is PLAIN text — its markdown syntax is NOT processed...
    expect(strongs).not.toContain("user-literal");
    // ...so the literal asterisks survive in the rendered output.
    expect(container.textContent ?? "").toContain("**user-literal**");

    // Position order: the user (position 0) renders before the assistant (position 1).
    const text = container.textContent ?? "";
    expect(text.indexOf("user-literal")).toBeLessThan(text.indexOf("bold-reply"));
  });
});

describe("the in-flight assistant bubble is rendered from the streaming buffer (DoD-2)", () => {
  it("DoD-2: MessageList shows the author's message and the streaming content buffer while a turn is in flight (UC-054, US-058.AC-1)", () => {
    const state = new ChatPaneState();
    runInAction(() => {
      state.chats = [CHAT];
      state.activeChatId = CHAT_ID;
      state.messages = [makeMessage("m-1", "user", "the-question", 0)];
      state.messagesStatus = "ready";
      state.turnStatus = "streaming";
      state.streamingContent = "Roses are red";
      state.streamingThinking = "";
      state.liveThinkingExpanded = false;
    });

    renderWithProviders(<MessageList state={state} />);

    expect(screen.getByText("the-question")).toBeInTheDocument();
    expect(screen.getByText(/Roses are red/)).toBeInTheDocument();
  });
});

describe("the live Thinking region reflects the expanded flag (DoD-3)", () => {
  it("DoD-3: the live thinking text is shown while the region is expanded", () => {
    const state = new ChatPaneState();
    runInAction(() => {
      state.chats = [CHAT];
      state.activeChatId = CHAT_ID;
      state.messages = [];
      state.turnStatus = "streaming";
      state.streamingThinking = "live-pondering-text";
      state.liveThinkingExpanded = true;
    });

    renderWithProviders(<MessageList state={state} />);

    expect(reasoningShown("live-pondering-text")).toBe(true);
  });

  it("DoD-3: once the region has collapsed the live thinking text is no longer shown (context.md decisions 7/8)", () => {
    const state = new ChatPaneState();
    runInAction(() => {
      state.chats = [CHAT];
      state.activeChatId = CHAT_ID;
      state.messages = [];
      state.turnStatus = "streaming";
      state.streamingContent = "Here is the answer";
      state.streamingThinking = "live-pondering-text";
      state.liveThinkingExpanded = false;
    });

    renderWithProviders(<MessageList state={state} />);

    // Collapsed: the reasoning is hidden, while the content is shown.
    expect(reasoningShown("live-pondering-text")).toBe(false);
    expect(screen.getByText(/Here is the answer/)).toBeInTheDocument();
  });
});

describe("a persisted message's reasoning is collapsed by default, expandable on demand (DoD-4)", () => {
  it("DoD-4: on reopen the stored reasoning is hidden and a thinking toggle reveals it (context.md decision 8)", async () => {
    const user = userEvent.setup();
    const state = new ChatPaneState();
    const assistantMsg = makeMessage("m-1", "assistant", "the-visible-answer", 0, "the-hidden-reasoning");
    runInAction(() => {
      state.chats = [CHAT];
      state.activeChatId = CHAT_ID;
      state.messages = [assistantMsg];
      state.messagesStatus = "ready";
      state.turnStatus = "idle";
      // expandedReasoning starts empty -> collapsed by default.
    });

    renderWithProviders(<MessageList state={state} />);

    // Collapsed by default: the answer is shown, the reasoning is not.
    expect(screen.getByText("the-visible-answer")).toBeInTheDocument();
    expect(reasoningShown("the-hidden-reasoning")).toBe(false);

    // Expandable on demand: activate the labelled thinking control.
    const label = screen.getByText(/thinking/i);
    await user.click(label.closest("button") ?? label);

    await waitFor(() => expect(reasoningShown("the-hidden-reasoning")).toBe(true));
  });

  it("DoD-4: ThinkingBlock hides its text when collapsed and calls onToggle when activated", async () => {
    const user = userEvent.setup();
    const onToggle = vi.fn();

    renderWithProviders(<ThinkingBlock text="reasoning-detail" expanded={false} onToggle={onToggle} />);

    expect(reasoningShown("reasoning-detail")).toBe(false);

    const label = screen.getByText(/thinking/i);
    await user.click(label.closest("button") ?? label);
    expect(onToggle).toHaveBeenCalledTimes(1);
  });

  it("DoD-4: ThinkingBlock shows its text when expanded", () => {
    renderWithProviders(<ThinkingBlock text="reasoning-shown" expanded={true} onToggle={vi.fn()} />);

    expect(reasoningShown("reasoning-shown")).toBe(true);
  });
});

describe("the Composer surfaces the error banner + retry (DoD-6)", () => {
  it("DoD-6: a failed turn shows an error banner and a retry control that invokes onRetry (UC-056, US-060.AC-1)", async () => {
    const user = userEvent.setup();
    const state = new ChatPaneState();
    runInAction(() => {
      state.chats = [CHAT];
      state.activeChatId = CHAT_ID;
      state.turnStatus = "error";
      state.turnError = "Model exploded";
    });
    const onRetry = vi.fn();

    renderWithProviders(
      <Composer state={state} onSend={vi.fn()} onStop={vi.fn()} onRetry={onRetry} />,
    );

    // The error message is surfaced to the author.
    expect(screen.getByText(/Model exploded/)).toBeInTheDocument();

    // A retry control is offered and drives onRetry.
    const retry = screen.getByRole("button", { name: /retry/i });
    await user.click(retry);
    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});

describe("the Composer is disabled while a turn is in flight (DoD-8)", () => {
  it("DoD-8: the prompt input is disabled while streaming and a stop control invokes onStop (US-058.AC-2)", async () => {
    const user = userEvent.setup();
    const state = new ChatPaneState();
    runInAction(() => {
      state.chats = [CHAT];
      state.activeChatId = CHAT_ID;
      state.pendingPrompt = "in progress";
      state.turnStatus = "streaming";
    });
    const onStop = vi.fn();

    renderWithProviders(
      <Composer state={state} onSend={vi.fn()} onStop={onStop} onRetry={vi.fn()} />,
    );

    expect(screen.getByRole("textbox")).toBeDisabled();

    const stop = screen.getByRole("button", { name: /stop/i });
    await user.click(stop);
    expect(onStop).toHaveBeenCalledTimes(1);
  });

  it("DoD-8: the prompt input is enabled again once the turn is idle", () => {
    const state = new ChatPaneState();
    runInAction(() => {
      state.chats = [CHAT];
      state.activeChatId = CHAT_ID;
      state.pendingPrompt = "ready to send";
      state.turnStatus = "idle";
    });

    renderWithProviders(
      <Composer state={state} onSend={vi.fn()} onStop={vi.fn()} onRetry={vi.fn()} />,
    );

    expect(screen.getByRole("textbox")).not.toBeDisabled();
  });
});
