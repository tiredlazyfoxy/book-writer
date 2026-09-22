/**
 * Chat icon tooltips — BUG FIX against 027.side-chats / step 007 (and step 006's group
 * icons). BF-1 … BF-10.
 *
 * The bug: every icon-only control in the chat UI ships with an `aria-label` and NO hint
 * — a mouse user sees a bare glyph. For the side-chat Start / Finish slot that is a direct
 * violation of the delivered contract: `007.side-chat-pane-controls.md` -> Interface intent
 * specifies it as "one `ActionIcon` (with `Tooltip`)". The remaining chat icons are the
 * same repair, extended.
 *
 * The contract these tests assert (from the fix brief + the step files, never from code):
 *   - each icon-only control is wrapped in a Mantine `Tooltip`;
 *   - the tooltip's label is the control's EXISTING `aria-label`, verbatim — accessible
 *     names do not change (so every control is still found by role + the same name);
 *   - the tooltip opens immediately on hover (no `openDelay`);
 *   - `position` / `withArrow` / icon choice are implementation details — NOT asserted;
 *   - the `disabled` prop mechanism is untouched. Mantine tooltips do not fire on a
 *     disabled button, so only controls in their ENABLED state are hovered here.
 *
 * Bound to the frozen interfaces (status.md -> `## Skeleton`, steps 004-007):
 *   interface ChatPaneProps { bookId: string; state: ChatPaneState }
 *   interface ComposerProps { state: ChatPaneState; onSend; onStop; onRetry }
 *   interface SideChatGroupProps { state: ChatPaneState; bookId: string | undefined;
 *                                  group: RenderedTranscriptSideChatItem }
 *   interface ChatListProps { state: ChatsListPageState; onPick; onSetArchived }
 *   ChatPaneState — no-arg ctor; observables chats / activeChatId / messages /
 *     turnStatus / expandedSideChats / closeTurnActive / openedPanel; computeds
 *     activeSideChatId / sideChatActionsEnabled / canStartSideChat / canFinishSideChat /
 *     renderedTranscript
 *   ChatsListPageState — no-arg ctor; chats / showArchived / get visibleChats
 *
 * Assertion technique (no precedent in this repo — this file establishes it): Mantine's
 * `Tooltip` defaults to `events: { hover: true, focus: false, touch: false }`, so FOCUS
 * does not open it — `userEvent.hover` is the only trigger. The open tooltip is located
 * with the polling `findByRole("tooltip")` so any animation is tolerated, and its text is
 * compared to the control's accessible name. The two query styles stay distinct: an
 * `aria-label` is an attribute, not a text node, so the name is NOT a `getByText`
 * collision, but it IS a `getByRole("button", { name })` collision.
 *
 * Every case renders fresh (one hover per render) so a tooltip left open by a previous
 * assertion can never be mistaken for the one under test.
 *
 * `../../src/api/chats` is mocked whole-module (never `fetch`). `globals: false`.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { runInAction } from "mobx";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type {
  ChatMessageResponse,
  ChatResponse,
  ChatSamplingParams,
} from "../../src/types/chats";
import type { RenderedTranscriptSideChatItem } from "../../src/work/components/chat/chatPaneState";
import { ChatPaneState } from "../../src/work/components/chat/chatPaneState";
import { ChatPane } from "../../src/work/components/chat/ChatPane";
import { Composer } from "../../src/work/components/chat/Composer";
import { SideChatGroup } from "../../src/work/components/chat/SideChatGroup";
import { ChatList } from "../../src/work/components/chat/ChatList";
import { ChatsListPageState } from "../../src/work/pages/chatsListPageState";
import { renderWithProviders } from "../support/render";

// The whole api module, every export enumerated (step 004's list, `getChat` included).
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

import * as chatsApi from "../../src/api/chats";

const BOOK_ID = "bk-1";
const CHAT_ID = "c-1";
const SIDE_ID = "sc-9";

/* The frozen accessible names. Each is ALSO the exact tooltip text the fix must show. */
const START = "Start side chat";
const FINISH = "Finish side chat";
const NEW_CHAT = "New chat";
const SETTINGS = "Chat settings";
const SEND = "Send";
const STOP = "Stop";
const EXPAND = "Expand side chat";
const COLLAPSE = "Collapse side chat";
const INJECT = "Inject side chat";
const DELETE = "Delete side chat";
const ARCHIVE = "Archive chat";
const RESTORE = "Restore chat";

/* ------------------------------------------------------------------ fixtures */

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

function makeChat(overrides: Partial<ChatResponse> = {}): ChatResponse {
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
    active_side_chat_id: null,
    ...overrides,
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

const MAIN_LINE: ChatMessageResponse[] = [
  makeMessage("m-0", "user", "main one", 0, null),
  makeMessage("m-1", "assistant", "main two", 1, null),
];

interface PrimeOptions {
  activeSideChatId?: string | null;
  turnStatus?: "idle" | "streaming";
  messages?: ChatMessageResponse[];
  pendingPrompt?: string;
}

/**
 * A pane / composer state with an active chat, a ready history, a ready (empty) model
 * catalogue and no close turn in flight — everything renders without a loader and the
 * composer is not read-only.
 */
function primeState(overrides: PrimeOptions = {}): ChatPaneState {
  const {
    activeSideChatId = null,
    turnStatus = "idle",
    messages = MAIN_LINE,
    pendingPrompt = "a question worth sending",
  } = overrides;
  const state = new ChatPaneState();
  runInAction(() => {
    state.chats = [makeChat({ active_side_chat_id: activeSideChatId })];
    state.chatsStatus = "ready";
    state.chatsError = null;
    state.activeChatId = CHAT_ID;
    state.modelOptions = [];
    state.modelOptionsStatus = "ready";
    state.modelOptionsError = null;
    state.messages = messages;
    state.messagesStatus = "ready";
    state.turnStatus = turnStatus;
    state.turnError = null;
    state.closeTurnActive = null;
    state.pendingPrompt = pendingPrompt;
  });
  return state;
}

/** The `sideChat` item for `sideChatId` out of `renderedTranscript`, narrowed. */
function findGroup(state: ChatPaneState, sideChatId: string): RenderedTranscriptSideChatItem {
  for (const item of state.renderedTranscript) {
    if (item.kind === "sideChat" && item.sideChatId === sideChatId) return item;
  }
  throw new Error(`no sideChat item for ${sideChatId} in renderedTranscript`);
}

/** Rows of one side chat, plus a main-line opener. */
function sideChatRows(): ChatMessageResponse[] {
  return [
    makeMessage("m-0", "user", "main-before", 0, null),
    makeMessage("m-1", "user", "side-question", 1, SIDE_ID),
    makeMessage("m-2", "assistant", "side-answer", 2, SIDE_ID),
  ];
}

/**
 * THE assertion under repair. Before any hover there must be no tooltip at all; hovering
 * the control must reveal one whose text is exactly `label` — the control's own
 * `aria-label`. Position / arrow / delay are deliberately not asserted.
 */
type User = ReturnType<typeof userEvent.setup>;

async function expectTooltip(user: User, control: HTMLElement, label: string): Promise<void> {
  // Negative first: nothing is showing until the pointer arrives.
  expect(screen.queryByRole("tooltip")).toBeNull();

  await user.hover(control);

  const tip = await screen.findByRole("tooltip");
  expect((tip.textContent ?? "").trim()).toBe(label);
}

beforeEach(() => {
  window.localStorage.clear();
  vi.mocked(chatsApi.listChats).mockResolvedValue([]);
  vi.mocked(chatsApi.listModelOptions).mockResolvedValue([]);
  vi.mocked(chatsApi.titleChat).mockResolvedValue({ title: "Chat one", changed: false });
  vi.mocked(chatsApi.streamChatTurn).mockResolvedValue(new AbortController());
});

/* ====================================================================== BF-1 */

describe("the Start side-chat control has a hint (BF-1)", () => {
  it("BF-1: hovering 'Start side chat' in an idle pane with no side chat active shows a tooltip reading exactly 'Start side chat' (007 DoD-1, 007 Interface intent)", async () => {
    const user = userEvent.setup();
    const state = primeState({ activeSideChatId: null, turnStatus: "idle" });

    renderWithProviders(<ChatPane bookId={BOOK_ID} state={state} />);

    const control = screen.getByRole("button", { name: START });
    // Only the enabled state is hovered — the disabled mechanism is untouched by the fix.
    expect(control).toBeEnabled();

    await expectTooltip(user, control, START);
  });
});

/* ====================================================================== BF-2 */

describe("the Finish side-chat control has a hint (BF-2)", () => {
  it("BF-2: hovering 'Finish side chat' in an idle pane with a side chat active shows a tooltip reading exactly 'Finish side chat' (007 DoD-2)", async () => {
    const user = userEvent.setup();
    const state = primeState({ activeSideChatId: SIDE_ID, turnStatus: "idle" });

    renderWithProviders(<ChatPane bookId={BOOK_ID} state={state} />);

    const control = screen.getByRole("button", { name: FINISH });
    expect(control).toBeEnabled();

    await expectTooltip(user, control, FINISH);
  });
});

/* ====================================================================== BF-3 */

describe("the New chat control has a hint (BF-3)", () => {
  it("BF-3: hovering 'New chat' shows a tooltip reading exactly 'New chat'", async () => {
    const user = userEvent.setup();
    const state = primeState();

    renderWithProviders(<ChatPane bookId={BOOK_ID} state={state} />);

    const control = screen.getByRole("button", { name: NEW_CHAT });

    await expectTooltip(user, control, NEW_CHAT);
  });
});

/* ====================================================================== BF-4 */

describe("the Chat settings control has a hint and still opens nothing on hover (BF-4)", () => {
  it("BF-4: hovering 'Chat settings' shows a tooltip reading exactly 'Chat settings', and the settings popover does not open", async () => {
    const user = userEvent.setup();
    const state = primeState();
    expect(state.openedPanel).toBeNull();

    renderWithProviders(<ChatPane bookId={BOOK_ID} state={state} />);

    const control = screen.getByRole("button", { name: SETTINGS });

    await expectTooltip(user, control, SETTINGS);

    // The control is a `Popover.Target`: wrapping it must not hijack the open mechanism
    // into firing on hover. Nothing opened.
    expect(state.openedPanel).toBeNull();
  });
});

/* ====================================================================== BF-5 */

describe("the composer's Send and Stop controls have hints (BF-5)", () => {
  it("BF-5: with an idle turn and a non-empty prompt, hovering 'Send' shows a tooltip reading exactly 'Send'", async () => {
    const user = userEvent.setup();
    const state = primeState({ turnStatus: "idle", pendingPrompt: "a question worth sending" });
    // Sending must be allowed, so the control is in its enabled state.
    expect(state.canSend).toBe(true);

    renderWithProviders(
      <Composer state={state} onSend={vi.fn()} onStop={vi.fn()} onRetry={vi.fn()} />,
    );

    const control = screen.getByRole("button", { name: SEND });
    expect(control).toBeEnabled();

    await expectTooltip(user, control, SEND);
  });

  it("BF-5: while the turn is streaming and the composer is not close-read-only, hovering 'Stop' shows a tooltip reading exactly 'Stop'", async () => {
    const user = userEvent.setup();
    const state = primeState({ turnStatus: "streaming" });
    // No close turn is in flight, so the composer is not read-only and Stop is the slot.
    expect(state.isComposerReadOnly).toBe(false);

    renderWithProviders(
      <Composer state={state} onSend={vi.fn()} onStop={vi.fn()} onRetry={vi.fn()} />,
    );

    const control = screen.getByRole("button", { name: STOP });
    expect(control).toBeEnabled();

    await expectTooltip(user, control, STOP);
  });
});

/* ====================================================================== BF-6 */

describe("the side-chat group's expand / collapse control has a hint (BF-6)", () => {
  it("BF-6: a collapsed finished group — hovering 'Expand side chat' shows a tooltip reading exactly 'Expand side chat'", async () => {
    const user = userEvent.setup();
    // A finished group (no active pointer) is collapsed by default — the only state in
    // which the expand control exists.
    const state = primeState({ activeSideChatId: null, messages: sideChatRows() });
    const group = findGroup(state, SIDE_ID);
    expect(group.expanded).toBe(false);

    renderWithProviders(<SideChatGroup state={state} bookId={BOOK_ID} group={group} />);

    const control = screen.getByRole("button", { name: EXPAND });

    await expectTooltip(user, control, EXPAND);
  });

  it("BF-6: the same group expanded — hovering 'Collapse side chat' shows a tooltip reading exactly 'Collapse side chat'", async () => {
    const user = userEvent.setup();
    const state = primeState({ activeSideChatId: null, messages: sideChatRows() });
    runInAction(() => {
      state.expandedSideChats = { [SIDE_ID]: true };
    });
    const group = findGroup(state, SIDE_ID);
    expect(group.expanded).toBe(true);

    renderWithProviders(<SideChatGroup state={state} bookId={BOOK_ID} group={group} />);

    const control = screen.getByRole("button", { name: COLLAPSE });

    await expectTooltip(user, control, COLLAPSE);
  });
});

/* ====================================================================== BF-7 */

describe("the side-chat group's Inject and Delete controls have hints (BF-7)", () => {
  // A standalone `SideChatGroup` render — no `ChatPane`, so no confirmation modal exists
  // and `Delete side chat` names exactly one thing in the tree.
  it("BF-7: with actions enabled and a book id, hovering 'Inject side chat' shows a tooltip reading exactly 'Inject side chat'", async () => {
    const user = userEvent.setup();
    const state = primeState({ activeSideChatId: null, messages: sideChatRows() });
    expect(state.sideChatActionsEnabled).toBe(true);
    const group = findGroup(state, SIDE_ID);

    renderWithProviders(<SideChatGroup state={state} bookId={BOOK_ID} group={group} />);

    const control = screen.getByRole("button", { name: INJECT });
    expect(control).toBeEnabled();

    await expectTooltip(user, control, INJECT);
  });

  it("BF-7: with actions enabled and a book id, hovering 'Delete side chat' shows a tooltip reading exactly 'Delete side chat'", async () => {
    const user = userEvent.setup();
    const state = primeState({ activeSideChatId: null, messages: sideChatRows() });
    expect(state.sideChatActionsEnabled).toBe(true);
    const group = findGroup(state, SIDE_ID);

    renderWithProviders(<SideChatGroup state={state} bookId={BOOK_ID} group={group} />);

    // No dialog anywhere in this render — the name is unambiguous.
    expect(screen.queryByRole("dialog")).toBeNull();
    const control = screen.getByRole("button", { name: DELETE });
    expect(control).toBeEnabled();

    await expectTooltip(user, control, DELETE);
  });
});

/* ====================================================================== BF-8 */

/** A list-page state holding one active and one archived chat. */
function primeListState(showArchived: boolean): ChatsListPageState {
  const state = new ChatsListPageState();
  runInAction(() => {
    state.chats = [
      makeChat({ id: "c-1", title: "Active chat", archived: false }),
      makeChat({ id: "c-9", title: "Retired chat", archived: true }),
    ];
    state.chatsStatus = "ready";
    state.chatsError = null;
    state.showArchived = showArchived;
  });
  return state;
}

describe("the chat list's archive / restore control has a hint (BF-8)", () => {
  it("BF-8: a non-archived row — hovering its control shows a tooltip reading exactly 'Archive chat'", async () => {
    const user = userEvent.setup();
    const state = primeListState(false);
    expect(state.visibleChats.map((chat) => chat.id)).toEqual(["c-1"]);

    renderWithProviders(
      <ChatList state={state} onPick={vi.fn()} onSetArchived={vi.fn()} />,
    );

    const control = screen.getByRole("button", { name: ARCHIVE });

    await expectTooltip(user, control, ARCHIVE);
  });

  it("BF-8: an archived row — hovering its control shows a tooltip reading exactly 'Restore chat'", async () => {
    const user = userEvent.setup();
    const state = primeListState(true);
    expect(state.visibleChats.map((chat) => chat.id)).toEqual(["c-9"]);

    renderWithProviders(
      <ChatList state={state} onPick={vi.fn()} onSetArchived={vi.fn()} />,
    );

    const control = screen.getByRole("button", { name: RESTORE });

    await expectTooltip(user, control, RESTORE);
  });
});

/* ====================================================================== BF-9 */

describe("wrapping in a Tooltip changes no accessible name, role or disabled state (BF-9)", () => {
  it("BF-9: the pane's header controls keep their names and roles, and 'Start side chat' is still disabled while streaming", () => {
    const idle = primeState({ activeSideChatId: null, turnStatus: "idle" });
    const { unmount } = renderWithProviders(<ChatPane bookId={BOOK_ID} state={idle} />);

    expect(screen.getByRole("button", { name: START })).toBeEnabled();
    expect(screen.getByRole("button", { name: NEW_CHAT })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: SETTINGS })).toBeInTheDocument();
    unmount();

    // The disabled mechanism is untouched: streaming still disables Start.
    const streaming = primeState({ activeSideChatId: null, turnStatus: "streaming" });
    renderWithProviders(<ChatPane bookId={BOOK_ID} state={streaming} />);
    expect(screen.getByRole("button", { name: START })).toBeDisabled();
  });

  it("BF-9: the pane's Finish slot keeps its name and role", () => {
    const state = primeState({ activeSideChatId: SIDE_ID, turnStatus: "idle" });

    renderWithProviders(<ChatPane bookId={BOOK_ID} state={state} />);

    expect(screen.getByRole("button", { name: FINISH })).toBeEnabled();
    expect(screen.queryByRole("button", { name: START })).toBeNull();
  });

  it("BF-9: the composer's Send and Stop keep their names and roles", () => {
    const idle = primeState({ turnStatus: "idle" });
    const { unmount } = renderWithProviders(
      <Composer state={idle} onSend={vi.fn()} onStop={vi.fn()} onRetry={vi.fn()} />,
    );
    expect(screen.getByRole("button", { name: SEND })).toBeEnabled();
    unmount();

    const streaming = primeState({ turnStatus: "streaming" });
    renderWithProviders(
      <Composer state={streaming} onSend={vi.fn()} onStop={vi.fn()} onRetry={vi.fn()} />,
    );
    expect(screen.getByRole("button", { name: STOP })).toBeEnabled();
  });

  it("BF-9: the group's controls keep their names, and Inject / Delete are still disabled when sideChatActionsEnabled is false", () => {
    const enabled = primeState({ activeSideChatId: null, messages: sideChatRows() });
    const { unmount } = renderWithProviders(
      <SideChatGroup state={enabled} bookId={BOOK_ID} group={findGroup(enabled, SIDE_ID)} />,
    );
    expect(screen.getByRole("button", { name: EXPAND })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: INJECT })).toBeEnabled();
    expect(screen.getByRole("button", { name: DELETE })).toBeEnabled();
    unmount();

    // Streaming turns the actions off — the fix must not have changed that.
    const blocked = primeState({
      activeSideChatId: null,
      messages: sideChatRows(),
      turnStatus: "streaming",
    });
    expect(blocked.sideChatActionsEnabled).toBe(false);
    renderWithProviders(
      <SideChatGroup state={blocked} bookId={BOOK_ID} group={findGroup(blocked, SIDE_ID)} />,
    );
    expect(screen.getByRole("button", { name: INJECT })).toBeDisabled();
    expect(screen.getByRole("button", { name: DELETE })).toBeDisabled();
  });

  it("BF-9: the chat list's archive / restore control keeps its two names and its role", () => {
    const active = primeListState(false);
    const { unmount } = renderWithProviders(
      <ChatList state={active} onPick={vi.fn()} onSetArchived={vi.fn()} />,
    );
    expect(screen.getByRole("button", { name: ARCHIVE })).toBeInTheDocument();
    unmount();

    const archived = primeListState(true);
    renderWithProviders(
      <ChatList state={archived} onPick={vi.fn()} onSetArchived={vi.fn()} />,
    );
    expect(screen.getByRole("button", { name: RESTORE })).toBeInTheDocument();
  });
});

/* ===================================================================== BF-10 */

describe("no tooltip is shown without a hover (BF-10)", () => {
  it("BF-10: a rendered ChatPane with no pointer interaction has no tooltip in the document", () => {
    const state = primeState();

    renderWithProviders(<ChatPane bookId={BOOK_ID} state={state} />);

    // The controls are there...
    expect(screen.getByRole("button", { name: START })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: NEW_CHAT })).toBeInTheDocument();
    // ...and not one of them is showing its hint yet.
    expect(screen.queryByRole("tooltip")).toBeNull();
  });
});
