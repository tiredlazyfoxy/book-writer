/**
 * SideChatGroup — the side-chat block — 027.side-chats / 006.side-chat-group-rendering,
 * DoD-2 · DoD-3 · DoD-4 · DoD-5 · DoD-6.
 * (DoD-1, DoD-7, DoD-8, DoD-9 are the list's — `tests/work/MessageListSideChats.test.tsx`.)
 *
 * Bound to the frozen step-006 skeleton (status.md -> `## Skeleton`):
 *   interface SideChatGroupProps { state: ChatPaneState; bookId: string | undefined;
 *                                  group: RenderedTranscriptSideChatItem }  -> SideChatGroup
 * and to steps 004 / 005 for the state it reads and the effects it binds:
 *   get renderedTranscript(): RenderedTranscriptItem[]     (the `group` prop is taken from here)
 *   get sideChatActionsEnabled(): boolean                  (false while turnStatus === "streaming")
 *   sideChatDeleteConfirm: string | null                   (set by requestDeleteSideChat)
 *   chatsApi.injectSideChat(bookId, chatId, sideChatId, signal?)
 *
 * Expected values come from the spec (`006.md` Interface intent + DoD; `context.md` D-F,
 * "Shared frontend facts", "Testing facts"; `006.context.md`), never from code:
 *   - the container is `role="group"` named `Side chat` for BOTH active and finished groups;
 *   - an ACTIVE group's header label reads `Side chat`, its messages are rendered, and it
 *     offers NO expand / collapse control (UC-110 step 3);
 *   - a FINISHED group is collapsed by default: label `Side chat · N messages`, ONE control
 *     `Expand side chat`, none of its message contents in the document (US-137.AC-1);
 *   - `Expand side chat` reveals the messages and the control becomes `Collapse side chat`;
 *     that hides them again (US-137.AC-2, UC-111 step 3);
 *   - `Inject side chat` / `Delete side chat` are present on every group; both disabled
 *     while `sideChatActionsEnabled` is false (streaming) or with no book id, enabled
 *     otherwise (UC-112 / UC-113 exception flows — D1);
 *   - Inject calls the inject api ONCE with (bookId, chatId, sideChatId) (US-139.AC-1);
 *     Delete sets `sideChatDeleteConfirm` to the group's id and calls NO api (US-140.AC-1).
 *
 * Queries by role + accessible name and by text only — never by test id.
 * `globals: false`: every primitive is imported explicitly.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { runInAction } from "mobx";
import { observer } from "mobx-react-lite";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type {
  ChatMessageResponse,
  ChatResponse,
  ChatSamplingParams,
} from "../../src/types/chats";
import type { RenderedTranscriptSideChatItem } from "../../src/work/components/chat/chatPaneState";
import { ChatPaneState } from "../../src/work/components/chat/chatPaneState";
import { SideChatGroup } from "../../src/work/components/chat/SideChatGroup";
import * as chatsApi from "../../src/api/chats";
import { renderWithProviders } from "../support/render";

// The api module the state layer imports: whole-module factory, EVERY export enumerated
// (the step-004 list — the four side-chat functions and `getChat` included). DoD-6 drives
// `injectSideChat` through `vi.mocked(...)` and asserts nothing else was called.
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
): ChatMessageResponse {
  return {
    id,
    chat_id: CHAT_ID,
    role,
    content,
    reasoning: null,
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
  });
}

/** A two-message side chat A: contents are distinct sentinels for presence / absence checks. */
function sideChatARows(): ChatMessageResponse[] {
  return [
    makeMessage("m-0", "user", "main-before", 0, null),
    makeMessage("m-1", "user", "side-a-question", 1, SIDE_A),
    makeMessage("m-2", "assistant", "side-a-answer", 2, SIDE_A),
  ];
}

/** The `sideChat` item for `sideChatId` out of `renderedTranscript`, narrowed by the type guard. */
function findGroup(state: ChatPaneState, sideChatId: string): RenderedTranscriptSideChatItem {
  for (const item of state.renderedTranscript) {
    if (item.kind === "sideChat" && item.sideChatId === sideChatId) return item;
  }
  throw new Error(`no sideChat item for ${sideChatId} in renderedTranscript`);
}

/**
 * Test-land host for the toggle case (DoD-4): the component takes `group` as a plain prop,
 * and `renderedTranscript` yields a fresh item after a toggle, so the host re-reads it on
 * every observer render — exactly what the list does. No source involved.
 */
const GroupHost = observer(function GroupHost({
  state,
  bookId,
  sideChatId,
}: {
  state: ChatPaneState;
  bookId: string | undefined;
  sideChatId: string;
}) {
  return <SideChatGroup state={state} bookId={bookId} group={findGroup(state, sideChatId)} />;
});

beforeEach(() => {
  vi.resetAllMocks();
});

describe("an active group: label, messages rendered, no expand / collapse control (DoD-2)", () => {
  it("DoD-2: an active group is a role=group named Side chat whose header reads 'Side chat' and whose messages are visible (UC-110 step 3)", () => {
    const state = new ChatPaneState();
    seed(state, sideChatARows(), SIDE_A);
    const item = findGroup(state, SIDE_A);

    renderWithProviders(<SideChatGroup state={state} bookId={BOOK_ID} group={item} />);

    const group = screen.getByRole("group", { name: "Side chat" });
    expect(within(group).getByText("Side chat")).toBeInTheDocument();
    expect(within(group).getByText("side-a-question")).toBeInTheDocument();
    expect(within(group).getByText("side-a-answer")).toBeInTheDocument();
  });

  it("DoD-2: an active group offers neither 'Expand side chat' nor 'Collapse side chat' (UC-110 step 3)", () => {
    const state = new ChatPaneState();
    seed(state, sideChatARows(), SIDE_A);
    const item = findGroup(state, SIDE_A);

    renderWithProviders(<SideChatGroup state={state} bookId={BOOK_ID} group={item} />);

    expect(screen.queryByRole("button", { name: "Expand side chat" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Collapse side chat" })).toBeNull();
    // The label is the plain active form, not the finished placeholder.
    expect(screen.queryByText(/Side chat · \d+ messages/)).toBeNull();
  });
});

describe("a finished group renders collapsed by default (DoD-3)", () => {
  it("DoD-3: a finished two-message group shows 'Side chat · 2 messages', an 'Expand side chat' control, and none of its contents (US-137.AC-1)", () => {
    const state = new ChatPaneState();
    seed(state, sideChatARows(), null);
    const item = findGroup(state, SIDE_A);

    renderWithProviders(<SideChatGroup state={state} bookId={BOOK_ID} group={item} />);

    const group = screen.getByRole("group", { name: "Side chat" });
    expect(within(group).getByText("Side chat · 2 messages")).toBeInTheDocument();
    expect(within(group).getByRole("button", { name: "Expand side chat" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Collapse side chat" })).toBeNull();
    expect(screen.queryByText("side-a-question")).toBeNull();
    expect(screen.queryByText("side-a-answer")).toBeNull();
  });

  it("DoD-3: N is the group's own message count — a three-message finished group reads 'Side chat · 3 messages' (US-137.AC-1)", () => {
    const state = new ChatPaneState();
    seed(
      state,
      [
        makeMessage("m-0", "user", "side-a-one", 0, SIDE_A),
        makeMessage("m-1", "assistant", "side-a-two", 1, SIDE_A),
        makeMessage("m-2", "user", "side-a-three", 2, SIDE_A),
        makeMessage("m-3", "user", "main-after", 3, null),
      ],
      null,
    );
    const item = findGroup(state, SIDE_A);

    renderWithProviders(<SideChatGroup state={state} bookId={BOOK_ID} group={item} />);

    expect(screen.getByText("Side chat · 3 messages")).toBeInTheDocument();
    expect(screen.queryByText("side-a-one")).toBeNull();
    expect(screen.queryByText("side-a-two")).toBeNull();
    expect(screen.queryByText("side-a-three")).toBeNull();
  });
});

describe("expand / collapse on demand (DoD-4)", () => {
  it("DoD-4: clicking 'Expand side chat' reveals the messages and swaps the control to 'Collapse side chat'; clicking that hides them again (US-137.AC-2, UC-111 step 3)", async () => {
    const user = userEvent.setup();
    const state = new ChatPaneState();
    seed(state, sideChatARows(), null);

    renderWithProviders(<GroupHost state={state} bookId={BOOK_ID} sideChatId={SIDE_A} />);

    // Collapsed by default.
    expect(screen.queryByText("side-a-question")).toBeNull();
    await user.click(screen.getByRole("button", { name: "Expand side chat" }));

    // Expanded: the contents are rendered inside the group and the control has swapped.
    const group = await screen.findByRole("group", { name: "Side chat" });
    await waitFor(() => expect(within(group).getByText("side-a-question")).toBeInTheDocument());
    expect(within(group).getByText("side-a-answer")).toBeInTheDocument();
    const collapse = await screen.findByRole("button", { name: "Collapse side chat" });
    expect(screen.queryByRole("button", { name: "Expand side chat" })).toBeNull();

    // Collapse again: the contents leave the document, the control swaps back.
    await user.click(collapse);
    await waitFor(() => expect(screen.queryByText("side-a-question")).toBeNull());
    expect(screen.queryByText("side-a-answer")).toBeNull();
    expect(await screen.findByRole("button", { name: "Expand side chat" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Collapse side chat" })).toBeNull();
  });

  it("DoD-4: only ONE expand-or-collapse control exists at a time — never both names in the tree (006.context.md)", async () => {
    const user = userEvent.setup();
    const state = new ChatPaneState();
    seed(state, sideChatARows(), null);

    renderWithProviders(<GroupHost state={state} bookId={BOOK_ID} sideChatId={SIDE_A} />);

    expect(screen.getAllByRole("button", { name: /(Expand|Collapse) side chat/ })).toHaveLength(1);
    await user.click(screen.getByRole("button", { name: "Expand side chat" }));
    await screen.findByRole("button", { name: "Collapse side chat" });
    expect(screen.getAllByRole("button", { name: /(Expand|Collapse) side chat/ })).toHaveLength(1);
  });
});

describe("Inject and Delete controls follow sideChatActionsEnabled (DoD-5)", () => {
  it("DoD-5: a finished group with an idle turn renders 'Inject side chat' and 'Delete side chat', both enabled (D1)", () => {
    const state = new ChatPaneState();
    seed(state, sideChatARows(), null, "idle");
    const item = findGroup(state, SIDE_A);

    renderWithProviders(<SideChatGroup state={state} bookId={BOOK_ID} group={item} />);

    const group = screen.getByRole("group", { name: "Side chat" });
    expect(within(group).getByRole("button", { name: "Inject side chat" })).toBeEnabled();
    expect(within(group).getByRole("button", { name: "Delete side chat" })).toBeEnabled();
  });

  it("DoD-5: an active group with an idle turn renders both controls enabled too (D1)", () => {
    const state = new ChatPaneState();
    seed(state, sideChatARows(), SIDE_A, "idle");
    const item = findGroup(state, SIDE_A);

    renderWithProviders(<SideChatGroup state={state} bookId={BOOK_ID} group={item} />);

    expect(screen.getByRole("button", { name: "Inject side chat" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Delete side chat" })).toBeEnabled();
  });

  it("DoD-5: while turnStatus === 'streaming' both controls are present but disabled (UC-112 / UC-113 exception flows — D1)", () => {
    const state = new ChatPaneState();
    seed(state, sideChatARows(), null, "streaming");
    const item = findGroup(state, SIDE_A);

    renderWithProviders(<SideChatGroup state={state} bookId={BOOK_ID} group={item} />);

    expect(screen.getByRole("button", { name: "Inject side chat" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Delete side chat" })).toBeDisabled();
  });

  it("DoD-5: with no book id (the forward-only split before step 007 wires it) both controls render disabled (006.context.md)", () => {
    const state = new ChatPaneState();
    seed(state, sideChatARows(), null, "idle");
    const item = findGroup(state, SIDE_A);

    renderWithProviders(<SideChatGroup state={state} bookId={undefined} group={item} />);

    expect(screen.getByRole("button", { name: "Inject side chat" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Delete side chat" })).toBeDisabled();
  });
});

describe("Inject triggers the api; Delete asks first (DoD-6)", () => {
  it("DoD-6: clicking 'Inject side chat' on an enabled group calls the inject api once with the book id, the chat id and that group's side-chat id (US-139.AC-1)", async () => {
    const user = userEvent.setup();
    const state = new ChatPaneState();
    seed(state, sideChatARows(), null, "idle");
    const item = findGroup(state, SIDE_A);
    vi.mocked(chatsApi.injectSideChat).mockResolvedValue({ chat: makeChat(null), messages: [] });

    renderWithProviders(<SideChatGroup state={state} bookId={BOOK_ID} group={item} />);

    await user.click(screen.getByRole("button", { name: "Inject side chat" }));

    await waitFor(() => expect(chatsApi.injectSideChat).toHaveBeenCalledTimes(1));
    const args = vi.mocked(chatsApi.injectSideChat).mock.calls[0];
    expect(args.slice(0, 3)).toEqual([BOOK_ID, CHAT_ID, SIDE_A]);
    // Inject never goes through the delete path.
    expect(chatsApi.deleteSideChat).not.toHaveBeenCalled();
  });

  it("DoD-6: clicking 'Delete side chat' sets sideChatDeleteConfirm to that group's id and calls NO api (US-140.AC-1 — asks first)", async () => {
    const user = userEvent.setup();
    const state = new ChatPaneState();
    seed(state, sideChatARows(), null, "idle");
    const item = findGroup(state, SIDE_A);
    expect(state.sideChatDeleteConfirm).toBeNull();

    renderWithProviders(<SideChatGroup state={state} bookId={BOOK_ID} group={item} />);

    await user.click(screen.getByRole("button", { name: "Delete side chat" }));

    await waitFor(() => expect(state.sideChatDeleteConfirm).toBe(SIDE_A));
    expect(chatsApi.deleteSideChat).not.toHaveBeenCalled();
    expect(chatsApi.injectSideChat).not.toHaveBeenCalled();
    expect(chatsApi.getChat).not.toHaveBeenCalled();
    expect(chatsApi.startSideChat).not.toHaveBeenCalled();
    expect(chatsApi.finishSideChat).not.toHaveBeenCalled();
    // Asking is not deleting: the rows are still there.
    expect(state.messages).toHaveLength(3);
  });
});
