/**
 * Composer keyboard contract — 023.chat-ux-revision, DoD-6.
 *
 * Bound to the frozen signatures in status.md -> `## Skeleton` / `plan.md` ->
 * Interface (`Composer.tsx`'s props are unchanged by 023):
 *   interface ComposerProps { state: ChatPaneState; onSend; onStop; onRetry }
 *   const Composer = observer(...)
 *   ChatPaneState: pendingPrompt; turnStatus ("idle" | "streaming" | "error");
 *                  get canSend
 *
 * Every expected value comes from the SPEC -- `plan.md` -> DoD-6 and its Interface
 * note for `Composer.tsx` (decision D10) -- never from code:
 *   - `Ctrl+Enter` AND `Cmd+Enter` (metaKey, for macOS) send, but only when sending is
 *     allowed (`state.canSend`);
 *   - while a turn is streaming the combination does nothing;
 *   - plain `Enter` never sends (it stays a newline in the textarea).
 *
 * The events are dispatched with `fireEvent.keyDown` rather than `userEvent`, because
 * the contract is about a specific modifier+key COMBINATION and this makes the
 * modifier flags exact. `../../src/api/chats` is mocked module-factory form so the
 * observed state never reaches the network. `globals: false`.
 */
import { describe, expect, it, vi } from "vitest";
import { runInAction } from "mobx";
import { fireEvent, screen } from "@testing-library/react";
import type { ChatResponse, ChatSamplingParams } from "../../src/types/chats";
import { ChatPaneState } from "../../src/work/components/chat/chatPaneState";
import { Composer } from "../../src/work/components/chat/Composer";
import { renderWithProviders } from "../support/render";

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
};

/** An active chat with a typed prompt, in the given turn state. */
function primeState(turnStatus: "idle" | "streaming"): ChatPaneState {
  const state = new ChatPaneState();
  runInAction(() => {
    state.chats = [CHAT];
    state.activeChatId = CHAT_ID;
    state.messages = [];
    state.messagesStatus = "ready";
    state.turnStatus = turnStatus;
    state.turnError = null;
    state.pendingPrompt = "a question worth sending";
  });
  return state;
}

describe("Ctrl/Cmd+Enter sends when sending is allowed (DoD-6)", () => {
  // Both modifiers are spec'd: `metaKey` is macOS's Cmd, included even though
  // development is Windows-only (D10).
  for (const [name, modifier] of [
    ["Ctrl", { ctrlKey: true }],
    ["Cmd", { metaKey: true }],
  ] as const) {
    it(`DoD-6: ${name}+Enter sends on an idle chat with a non-empty prompt`, () => {
      const state = primeState("idle");
      expect(state.canSend).toBe(true);
      const onSend = vi.fn();

      renderWithProviders(
        <Composer state={state} onSend={onSend} onStop={vi.fn()} onRetry={vi.fn()} />,
      );

      fireEvent.keyDown(screen.getByRole("textbox"), { key: "Enter", ...modifier });

      expect(onSend).toHaveBeenCalledTimes(1);
    });
  }
});

describe("the combination is inert while a turn is in flight (DoD-6)", () => {
  it("DoD-6: Ctrl+Enter does nothing while the turn is streaming", () => {
    const state = primeState("streaming");
    // Sending is not allowed mid-turn (the 011 composer gate).
    expect(state.canSend).toBe(false);
    const onSend = vi.fn();

    renderWithProviders(
      <Composer state={state} onSend={onSend} onStop={vi.fn()} onRetry={vi.fn()} />,
    );

    fireEvent.keyDown(screen.getByRole("textbox"), { key: "Enter", ctrlKey: true });

    expect(onSend).not.toHaveBeenCalled();
  });
});

describe("plain Enter does not send (DoD-6)", () => {
  it("DoD-6: Enter without a modifier leaves the prompt alone — it is a newline, not a send", () => {
    const state = primeState("idle");
    const onSend = vi.fn();

    renderWithProviders(
      <Composer state={state} onSend={onSend} onStop={vi.fn()} onRetry={vi.fn()} />,
    );

    fireEvent.keyDown(screen.getByRole("textbox"), { key: "Enter" });

    expect(onSend).not.toHaveBeenCalled();
  });
});
