/**
 * The vertically adjustable composer — fast/008.composer-resize, DoD-7 … DoD-11.
 *
 * Bound to the frozen signatures in status.md -> `## Skeleton`:
 *   new ChatPaneState()                       // no arguments; HYDRATES in the ctor
 *   ChatPaneState.composerHeight: number      // observable, PIXELS
 *   interface ComposerResizeHandleProps { state: ChatPaneState }
 *   const ComposerResizeHandle = observer(...)  // <ComposerResizeHandle state={state} />
 *   interface ComposerProps { state; onSend; onStop; onRetry }   // unchanged
 *   readWorkspaceLayout(): WorkspaceLayout    // { navCollapsed, chatWidth, composerHeight }
 *   const WORKSPACE_LAYOUT_KEY = "bookwriter.workspace-layout"
 *
 * Every expected value comes from `plan.md` -> Definition of done and Interface
 * intent, never from code:
 *   - the state seeds its height from storage, clamped against the CURRENT viewport
 *     (DoD-7) — that is where the viewport-dependent maximum is first applied;
 *   - the handle is a `separator` named "Resize composer" carrying the value triple
 *     in pixels (DoD-8);
 *   - ArrowUp GROWS and ArrowDown SHRINKS by exactly 24px, bounded by the same
 *     rules as `clampComposerHeight` (DoD-9), and each nudge persists as a partial
 *     patch that leaves the shell's two fields alone (DoD-10);
 *   - the `<textarea>` is exactly `state.composerHeight` pixels tall and does NOT
 *     autosize, while 023's Send/Stop and Ctrl/Cmd+Enter contract still holds
 *     (DoD-11).
 *
 * DELIBERATELY ABSENT, per `plan.md` -> "Deliberately not automated": the pointer
 * drag (jsdom has no PointerEvent, no setPointerCapture and no layout engine — the
 * geometry is covered as a pure function and the persistence wiring through the
 * keyboard path), the flex chain, breakpoint behaviour, `resize: "none"` /
 * internal scrolling, and mounting `ChatPane` to prove the handle's position.
 *
 * Turn state and prompt text are always primed BEFORE the render (a second render
 * with a fresh state rather than a post-mount mutation) — that is how the repo's
 * existing chat specs exercise the Send/Stop swap, and it is what makes the
 * "does not autosize" assertion able to fail.
 *
 * Both surfaces take the state instance as a prop, so they render in isolation with
 * no load path; `../../src/api/chats` is mocked module-factory form purely so no
 * import reaches the network. `window.innerHeight` is pinned explicitly (800, so
 * the maximum is 400) rather than relying on jsdom's default. `globals: false`.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { runInAction } from "mobx";
import { fireEvent, screen } from "@testing-library/react";
import type { ChatResponse, ChatSamplingParams } from "../../src/types/chats";
import { ChatPaneState } from "../../src/work/components/chat/chatPaneState";
import { Composer } from "../../src/work/components/chat/Composer";
import { ComposerResizeHandle } from "../../src/work/components/chat/ComposerResizeHandle";
import { WORKSPACE_LAYOUT_KEY, readWorkspaceLayout } from "../../src/work/workspaceLayout";
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

/** Viewport height under test: half of it — the composer maximum — is 400. */
const VIEWPORT_HEIGHT = 800;

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

/** jsdom's `innerHeight` is assignable; pin it rather than inherit the default 768. */
function setViewportHeight(height: number): void {
  Object.defineProperty(window, "innerHeight", {
    writable: true,
    configurable: true,
    value: height,
  });
}

/**
 * Plant a layout record at the module's own key, bypassing the writer — the state
 * hydrates in its CONSTRUCTOR, so this must run before `new ChatPaneState()`.
 */
function seedStoredLayout(layout: {
  navCollapsed: boolean;
  chatWidth: number;
  composerHeight: number;
}): void {
  localStorage.setItem(WORKSPACE_LAYOUT_KEY, JSON.stringify(layout));
}

/**
 * An active chat in the given turn state, with a prompt already typed.
 *
 * Everything is primed BEFORE the component renders: this suite asserts rendered
 * DOM, and the surrounding specs establish that priming-then-rendering is how the
 * turn state is exercised here.
 */
function primeState(
  turnStatus: "idle" | "streaming",
  prompt = "a question worth sending",
): ChatPaneState {
  const state = new ChatPaneState();
  runInAction(() => {
    state.chats = [CHAT];
    state.activeChatId = CHAT_ID;
    state.messages = [];
    state.messagesStatus = "ready";
    state.turnStatus = turnStatus;
    state.turnError = null;
    state.pendingPrompt = prompt;
  });
  return state;
}

/** The handle, by its contracted role + accessible name. */
function handle(): HTMLElement {
  return screen.getByRole("separator", { name: "Resize composer" });
}

/** The rendered `aria-valuenow`, as a number. */
function valueNow(): number {
  return Number(handle().getAttribute("aria-valuenow"));
}

beforeEach(() => {
  setViewportHeight(VIEWPORT_HEIGHT);
});

describe("the state seeds its height from storage, clamped to the viewport (DoD-7)", () => {
  it("DoD-7: with empty storage a fresh ChatPaneState starts at the 96px default", () => {
    expect(localStorage.getItem(WORKSPACE_LAYOUT_KEY)).toBeNull();

    const state = new ChatPaneState();

    expect(state.composerHeight).toBe(96);
  });

  it("DoD-7: a stored height far above half the viewport is corrected on construction", () => {
    // Chosen on a bigger monitor: 5000px is not corrupt data, it is out of place
    // here. 0.5 * 800 = 400.
    seedStoredLayout({ navCollapsed: false, chatWidth: 0.35, composerHeight: 5000 });

    const state = new ChatPaneState();

    expect(state.composerHeight).toBe(400);
  });

  it("DoD-7: a stored height that fits the viewport is seeded unchanged", () => {
    seedStoredLayout({ navCollapsed: false, chatWidth: 0.35, composerHeight: 180 });

    const state = new ChatPaneState();

    expect(state.composerHeight).toBe(180);
  });
});

describe("the handle's accessibility contract (DoD-8)", () => {
  it("DoD-8: the handle is a horizontal separator named 'Resize composer' carrying the pixel value triple", () => {
    seedStoredLayout({ navCollapsed: false, chatWidth: 0.35, composerHeight: 180 });
    const state = new ChatPaneState();

    renderWithProviders(<ComposerResizeHandle state={state} />);

    const separator = handle();
    expect(separator).toBeInTheDocument();
    expect(separator).toHaveAttribute("aria-orientation", "horizontal");
    // Pixels, not a fraction: min 64, max 0.5 * 800 rounded, now the current height.
    expect(separator).toHaveAttribute("aria-valuemin", "64");
    expect(separator).toHaveAttribute("aria-valuemax", "400");
    expect(separator).toHaveAttribute("aria-valuenow", "180");
  });

  it("DoD-8: aria-valuemax tracks the viewport it is rendered against", () => {
    setViewportHeight(1000);
    seedStoredLayout({ navCollapsed: false, chatWidth: 0.35, composerHeight: 180 });
    const state = new ChatPaneState();

    renderWithProviders(<ComposerResizeHandle state={state} />);

    expect(handle()).toHaveAttribute("aria-valuemax", "500");
  });
});

describe("the handle is keyboard operable (DoD-9)", () => {
  function renderHandleAt(height: number): ChatPaneState {
    seedStoredLayout({ navCollapsed: false, chatWidth: 0.35, composerHeight: height });
    const state = new ChatPaneState();
    renderWithProviders(<ComposerResizeHandle state={state} />);
    handle().focus();
    return state;
  }

  it("DoD-9: ArrowUp GROWS the composer by exactly one 24px step", () => {
    // Up grows, because the composer grows upward from the pane's bottom.
    const state = renderHandleAt(180);

    fireEvent.keyDown(handle(), { key: "ArrowUp" });

    expect(state.composerHeight).toBe(204);
    expect(valueNow()).toBe(204);
  });

  it("DoD-9: ArrowDown SHRINKS the composer by exactly one 24px step", () => {
    const state = renderHandleAt(180);

    fireEvent.keyDown(handle(), { key: "ArrowDown" });

    expect(state.composerHeight).toBe(156);
    expect(valueNow()).toBe(156);
  });

  it("DoD-9: repeated ArrowDown stops at the 64px minimum", () => {
    const state = renderHandleAt(180);

    for (let i = 0; i < 20; i += 1) {
      fireEvent.keyDown(handle(), { key: "ArrowDown" });
    }

    expect(state.composerHeight).toBe(64);
    expect(valueNow()).toBe(64);
  });

  it("DoD-9: repeated ArrowUp stops at half the viewport height", () => {
    const state = renderHandleAt(180);

    for (let i = 0; i < 30; i += 1) {
      fireEvent.keyDown(handle(), { key: "ArrowUp" });
    }

    expect(state.composerHeight).toBe(400);
    expect(valueNow()).toBe(400);
  });

  it("DoD-9: any other key leaves the height alone", () => {
    const state = renderHandleAt(180);

    fireEvent.keyDown(handle(), { key: "ArrowLeft" });
    fireEvent.keyDown(handle(), { key: "Enter" });
    fireEvent.keyDown(handle(), { key: "a" });

    expect(state.composerHeight).toBe(180);
    expect(valueNow()).toBe(180);
  });
});

describe("each keyboard nudge persists without clobbering the shell's fields (DoD-10)", () => {
  it("DoD-10: a nudge writes the new height while a seeded navCollapsed and chatWidth survive", () => {
    // Two owners, one key: WorkspaceShellState owns the first two fields,
    // ChatPaneState owns the third, and the merging write keeps both.
    seedStoredLayout({ navCollapsed: true, chatWidth: 0.5, composerHeight: 180 });
    const state = new ChatPaneState();
    renderWithProviders(<ComposerResizeHandle state={state} />);
    handle().focus();

    fireEvent.keyDown(handle(), { key: "ArrowUp" });

    expect(state.composerHeight).toBe(204);
    expect(readWorkspaceLayout()).toEqual({
      navCollapsed: true,
      chatWidth: 0.5,
      composerHeight: 204,
    });
  });

  it("DoD-10: every nudge persists, including one that lands on a bound", () => {
    seedStoredLayout({ navCollapsed: true, chatWidth: 0.5, composerHeight: 80 });
    const state = new ChatPaneState();
    renderWithProviders(<ComposerResizeHandle state={state} />);
    handle().focus();

    fireEvent.keyDown(handle(), { key: "ArrowDown" });
    expect(readWorkspaceLayout().composerHeight).toBe(64);

    fireEvent.keyDown(handle(), { key: "ArrowUp" });
    expect(readWorkspaceLayout().composerHeight).toBe(88);

    expect(readWorkspaceLayout().navCollapsed).toBe(true);
    expect(readWorkspaceLayout().chatWidth).toBe(0.5);
  });
});

describe("the composer is a fixed-height box that does not autosize (DoD-11)", () => {
  function renderComposer(
    state: ChatPaneState,
    handlers: { onSend?: () => void; onStop?: () => void; onRetry?: () => void } = {},
  ): void {
    renderWithProviders(
      <Composer
        state={state}
        onSend={handlers.onSend ?? vi.fn()}
        onStop={handlers.onStop ?? vi.fn()}
        onRetry={handlers.onRetry ?? vi.fn()}
      />,
    );
  }

  it("DoD-11: the textarea is rendered at exactly state.composerHeight pixels", () => {
    seedStoredLayout({ navCollapsed: false, chatWidth: 0.35, composerHeight: 180 });
    const state = primeState("idle");
    expect(state.composerHeight).toBe(180);

    renderComposer(state);

    const textarea = screen.getByRole("textbox") as HTMLTextAreaElement;
    expect(textarea.style.height).toBe("180px");
  });

  it("DoD-11: a prompt far longer than the old six-row maximum is still rendered at that exact height", () => {
    seedStoredLayout({ navCollapsed: false, chatWidth: 0.35, composerHeight: 180 });
    // Forty lines — well past the six rows `autosize` used to grow to. Typed BEFORE
    // the render, so an autosizing input would have had every chance to size itself
    // to the content and this assertion can genuinely fail.
    const longPrompt = Array.from({ length: 40 }, (_, i) => `line ${i}`).join("\n");
    const state = primeState("idle", longPrompt);

    renderComposer(state);

    // Fixed height: the box is exactly as tall as the state says, whatever it holds.
    const textarea = screen.getByRole("textbox") as HTMLTextAreaElement;
    expect(textarea.value).toBe(longPrompt);
    expect(textarea.style.height).toBe("180px");
  });

  it("DoD-11: the 023 Send control is present while the turn is idle", () => {
    seedStoredLayout({ navCollapsed: false, chatWidth: 0.35, composerHeight: 180 });
    const state = primeState("idle");

    renderComposer(state);

    // One slot: Send while idle.
    expect(screen.getByRole("button", { name: /^send$/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^stop$/i })).toBeNull();
  });

  it("DoD-11: the same slot carries Stop while a turn is streaming", () => {
    seedStoredLayout({ navCollapsed: false, chatWidth: 0.35, composerHeight: 180 });
    const state = primeState("streaming");

    renderComposer(state);

    expect(screen.getByRole("button", { name: /^stop$/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^send$/i })).toBeNull();
    // ...and the fixed height holds in the streaming render too.
    expect((screen.getByRole("textbox") as HTMLTextAreaElement).style.height).toBe("180px");
  });

  // Both modifiers are spec'd: `metaKey` is macOS's Cmd.
  for (const [name, modifier] of [
    ["Ctrl", { ctrlKey: true }],
    ["Cmd", { metaKey: true }],
  ] as const) {
    it(`DoD-11: ${name}+Enter still sends from the fixed-height input`, () => {
      seedStoredLayout({ navCollapsed: false, chatWidth: 0.35, composerHeight: 180 });
      const state = primeState("idle");
      const onSend = vi.fn();

      renderComposer(state, { onSend });

      fireEvent.keyDown(screen.getByRole("textbox"), { key: "Enter", ...modifier });

      expect(onSend).toHaveBeenCalledTimes(1);
    });
  }

  it("DoD-11: plain Enter still does not send — it stays a newline", () => {
    seedStoredLayout({ navCollapsed: false, chatWidth: 0.35, composerHeight: 180 });
    const state = primeState("idle");
    const onSend = vi.fn();

    renderComposer(state, { onSend });

    fireEvent.keyDown(screen.getByRole("textbox"), { key: "Enter" });

    expect(onSend).not.toHaveBeenCalled();
  });
});
