/**
 * The repo's FIRST SSE test fixture (011.chat-panel / 005).
 *
 * There is no real body stream in these tests: `../../src/api/chats` is mocked
 * (module-factory form) and its `streamChatTurn` is a `vi.fn()`. The state layer
 * calls `streamChatTurn(bookId, chatId, prompt, handlers)` and awaits the returned
 * `AbortController` (the frozen seam: `streamPost` owns the controller, so this one
 * api function returns it rather than taking a `signal`). This fixture installs an
 * implementation on that mock which:
 *   - captures each opened turn (its args + the four handler callbacks), and
 *   - resolves with a fresh `AbortController` whose `abort` is spied,
 * then lets a spec fire a scripted frame sequence (`thinking` / `delta` / `done` /
 * `error`) against the most-recently-opened turn's handlers — so specs can assert
 * frame-by-frame growth (DoD-2) and the auto-collapse transition (DoD-3) without a
 * real stream, and can assert the stored controller was aborted (DoD-10).
 *
 * Bound to the frozen step-005 skeleton: `interface TurnStreamHandlers`
 * ({ onThinking(text), onDelta(text), onDone(), onError(message) }) and
 * `streamChatTurn(bookId, chatId, prompt: string | null, handlers): Promise<AbortController>`.
 * `onDone` carries NO payload — the persisted DTO does not flow through the stream.
 */
import { vi, type Mock } from "vitest";
import type { TurnStreamHandlers } from "../../src/api/chats";

/** One opened turn, as the mocked `streamChatTurn` received it. */
export interface CapturedTurn {
  bookId: string;
  chatId: string;
  prompt: string | null;
  handlers: TurnStreamHandlers;
  /** The controller `streamChatTurn` resolves with; its `abort` is a spy. */
  controller: AbortController;
}

type StreamChatTurnFn = (
  bookId: string,
  chatId: string,
  prompt: string | null,
  handlers: TurnStreamHandlers,
) => Promise<AbortController>;

/** Drives a mocked turn stream's handlers with a scripted frame sequence. */
export interface TurnStreamFixture {
  /** Every turn opened so far, in call order. */
  turns: CapturedTurn[];
  /** The most-recently opened turn (throws if none has opened yet). */
  last(): CapturedTurn;
  /** Fire a `thinking` frame on the latest turn. */
  thinking(text: string): void;
  /** Fire a content `delta` frame on the latest turn. */
  delta(text: string): void;
  /** Fire the terminal `done` frame on the latest turn (no payload). */
  done(): void;
  /** Fire an `error` frame on the latest turn. */
  error(message: string): void;
}

/**
 * Install the capturing implementation on a mocked `streamChatTurn` and return a
 * driver. Call once per test (mock implementations are wiped between tests by the
 * harness's `restoreMocks` / `clearMocks`).
 */
export function installTurnStream(mockFn: Mock<StreamChatTurnFn>): TurnStreamFixture {
  const turns: CapturedTurn[] = [];

  mockFn.mockImplementation((bookId, chatId, prompt, handlers) => {
    const controller = new AbortController();
    vi.spyOn(controller, "abort");
    turns.push({ bookId, chatId, prompt, handlers, controller });
    return Promise.resolve(controller);
  });

  const last = (): CapturedTurn => {
    if (turns.length === 0) {
      throw new Error("sseFixture: no turn stream has been opened yet");
    }
    return turns[turns.length - 1];
  };

  return {
    turns,
    last,
    thinking: (text: string) => last().handlers.onThinking(text),
    delta: (text: string) => last().handlers.onDelta(text),
    done: () => last().handlers.onDone(),
    error: (message: string) => last().handlers.onError(message),
  };
}
