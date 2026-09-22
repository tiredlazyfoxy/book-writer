/**
 * The composer's side-chat hint — 027.side-chats / 007.side-chat-pane-controls, DoD-10.
 *
 * Renders `Composer` the way `Composer.test.tsx` does (`primeState` -> an active chat
 * with a typed prompt and an idle turn) and toggles the active chat's
 * `active_side_chat_id` in `chats[]` between cases — that field is how a spec makes a
 * side chat active (`context.md` -> "Shared frontend facts").
 *
 * Bound to the frozen step-007 interface (status.md -> `## Skeleton` -> "Step 007"):
 *   interface ComposerProps { state: ChatPaneState; onSend; onStop; onRetry }  // unchanged
 *   the hint: exact text `Replying in the side chat` while `state.activeSideChatId !== null`
 *   the input: textbox named `Message the assistant`; the send control: button `Send`
 * and step 004's `activeSideChatId` computed over the active chat's pointer.
 *
 * Every expected value comes from the SPEC (`007.side-chat-pane-controls.md` -> DoD-10 +
 * Interface intent "The composer hint"; `context.md` D-F "Composer.tsx needs no gate
 * change"), never from code:
 *   - the text `Replying in the side chat` is shown when a side chat is active and not
 *     otherwise (UC-110 step 3);
 *   - in BOTH cases the input and its Send control are present and enabled — the gate
 *     is unchanged (US-137.AC-3 holds by construction; there is no composer for a
 *     finished group).
 *
 * `../../src/api/chats` is mocked module-factory form with EVERY export (step 004's
 * eleven). `globals: false`.
 */
import { describe, expect, it, vi } from "vitest";
import { runInAction } from "mobx";
import { act, screen } from "@testing-library/react";
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
  titleChat: vi.fn(),
  startSideChat: vi.fn(),
  finishSideChat: vi.fn(),
  injectSideChat: vi.fn(),
  deleteSideChat: vi.fn(),
  streamChatTurn: vi.fn(),
}));

const BOOK_ID = "bk-1";
const CHAT_ID = "c-1";
const SIDE_ID = "sc-9";

const HINT_TEXT = "Replying in the side chat";
const INPUT_NAME = "Message the assistant";
const SEND_NAME = "Send";

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

/** An active chat with a typed prompt and an idle turn; the pointer is the variable. */
function primeState(activeSideChatId: string | null): ChatPaneState {
  const state = new ChatPaneState();
  runInAction(() => {
    state.chats = [makeChat(activeSideChatId)];
    state.activeChatId = CHAT_ID;
    state.messages = [];
    state.messagesStatus = "ready";
    state.turnStatus = "idle";
    state.turnError = null;
    state.pendingPrompt = "a question worth sending";
  });
  return state;
}

function renderComposer(state: ChatPaneState): void {
  renderWithProviders(
    <Composer state={state} onSend={vi.fn()} onStop={vi.fn()} onRetry={vi.fn()} />,
  );
}

describe("the composer hint while a side chat is active (DoD-10)", () => {
  it("DoD-10: with a side chat active the composer shows 'Replying in the side chat', and the input and Send are present and enabled (UC-110 step 3)", () => {
    const state = primeState(SIDE_ID);
    expect(state.activeSideChatId).toBe(SIDE_ID);

    renderComposer(state);

    // Presence first: the hint, exact text.
    expect(screen.getByText(HINT_TEXT)).toBeInTheDocument();

    // The gate is unchanged: the author can still type and send.
    expect(screen.getByRole("textbox", { name: INPUT_NAME })).toBeEnabled();
    expect(screen.getByRole("button", { name: SEND_NAME })).toBeEnabled();
  });

  it("DoD-10: with no side chat active the composer shows no such hint, and the input and Send are present and enabled just the same", () => {
    const state = primeState(null);
    expect(state.activeSideChatId).toBeNull();

    renderComposer(state);

    // Presence first: the same two controls, in the same state...
    expect(screen.getByRole("textbox", { name: INPUT_NAME })).toBeEnabled();
    expect(screen.getByRole("button", { name: SEND_NAME })).toBeEnabled();
    // ...and only then the negative: nothing about a side chat is shown.
    expect(screen.queryByText(HINT_TEXT)).toBeNull();
  });

  it("DoD-10: the hint follows the server pointer — the same composer shows it once the active chat's active_side_chat_id is set, and drops it once it is cleared (US-137.AC-3 by construction)", () => {
    const state = primeState(null);

    renderComposer(state);
    expect(screen.queryByText(HINT_TEXT)).toBeNull();

    // A side chat becomes active on the chat itself (what a start / a reload yields).
    act(() => {
      runInAction(() => {
        state.chats = [makeChat(SIDE_ID)];
      });
    });
    expect(screen.getByText(HINT_TEXT)).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: INPUT_NAME })).toBeEnabled();
    expect(screen.getByRole("button", { name: SEND_NAME })).toBeEnabled();

    // Finished: the pointer is cleared, the hint goes, the gate is still open.
    act(() => {
      runInAction(() => {
        state.chats = [makeChat(null)];
      });
    });
    expect(screen.queryByText(HINT_TEXT)).toBeNull();
    expect(screen.getByRole("textbox", { name: INPUT_NAME })).toBeEnabled();
    expect(screen.getByRole("button", { name: SEND_NAME })).toBeEnabled();
  });
});
