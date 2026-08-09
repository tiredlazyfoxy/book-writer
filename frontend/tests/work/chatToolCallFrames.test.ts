/**
 * Tool-call frame narrowing — 024.chat-agent-loop, DoD-5.
 *
 * Bound to the frozen skeleton (`status.md` -> `## Skeleton`):
 *   types/chats.d.ts:
 *     interface ToolCallFrame   { tool_name: string; arguments: Record<string, unknown> }
 *     interface ToolResultFrame { tool_name: string; result: string; ok: boolean }
 *   api/chats.ts:
 *     function toolCallFrame(data: unknown): ToolCallFrame | null       (module-private)
 *     function toolResultFrame(data: unknown): ToolResultFrame | null   (module-private)
 *     TurnStreamHandlers gains `onToolCall?` / `onToolResult?`
 *     streamChatTurn(bookId, chatId, prompt, handlers, subject?, selectionText?)  UNCHANGED
 *
 * The two narrowing functions are module-private, so the observation point the DoD
 * itself names is used: "malformed payloads ... are dropped (return `null`), NEVER
 * FORWARDED TO A HANDLER". The REAL `streamChatTurn` runs with `api/sse`'s
 * `streamPost` mocked (the seam that owns the `AbortController`), and each frame is
 * delivered through `sse.ts`'s generic `onEvent(name, payload)` routing — the same
 * path `canvasWiring.test.tsx` uses for the `canvas` frame, and the path
 * `context.md` -> "Frontend shape" states new event names arrive on with zero
 * transport changes.
 *
 * The air gap: expected values come from the spec alone — `plan.md` -> DoD-5 and ->
 * Interface (`api/chats.ts`: "narrow field-by-field from `unknown`, return `null`
 * (drop the whole frame) on any type mismatch or missing required field — never
 * default a bad or absent field"), and `context.md` -> "Standing constraints"
 * ("Frame narrowing on the client **drops malformed payloads** rather than
 * defaulting them"). Never from implementation internals. `globals: false`.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ToolCallFrame, ToolResultFrame } from "../../src/types/chats";
import type { SSEHandlers } from "../../src/api/sse";
import * as sse from "../../src/api/sse";
import * as client from "../../src/api/client";
import { streamChatTurn } from "../../src/api/chats";

// The stream transport: `streamPost` owns the AbortController, so mocking it makes
// the turn's SSE handlers observable without any network.
vi.mock("../../src/api/sse", () => ({
  streamPost: vi.fn(),
}));

// The token refresh `streamChatTurn` awaits before opening the stream; everything
// else in the client module stays real.
vi.mock("../../src/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../src/api/client")>();
  return { ...actual, refreshAuthToken: vi.fn(async () => {}) };
});

const BOOK_ID = "bk-1";
const CHAT_ID = "c-1";

/** One opened turn: its SSE handlers plus the tool-frame spies it was given. */
interface OpenedTurn {
  fire: (event: string, data: unknown) => void;
  onToolCall: ReturnType<typeof vi.fn>;
  onToolResult: ReturnType<typeof vi.fn>;
}

const captured: SSEHandlers[] = [];

beforeEach(() => {
  captured.length = 0;
  vi.mocked(client.refreshAuthToken).mockImplementation(async () => {});
  vi.mocked(sse.streamPost).mockImplementation(
    (_url: string, _body: object, handlers: SSEHandlers) => {
      captured.push(handlers);
      return new AbortController();
    },
  );
});

/** Open a real turn and return a driver for its generic-event routing. */
async function openTurn(): Promise<OpenedTurn> {
  const onToolCall = vi.fn();
  const onToolResult = vi.fn();

  await streamChatTurn(BOOK_ID, CHAT_ID, "hello", {
    onThinking: () => {},
    onDelta: () => {},
    onDone: () => {},
    onError: () => {},
    onToolCall,
    onToolResult,
  });

  const handlers = captured[captured.length - 1];
  if (handlers === undefined) {
    throw new Error("no turn stream was opened");
  }

  return {
    fire: (event: string, data: unknown) => handlers.onEvent?.(event, data),
    onToolCall,
    onToolResult,
  };
}

/* ------------------------------------------------- well-formed frames parse */

describe("a well-formed tool frame reaches its handler intact (DoD-5)", () => {
  const callCases: Array<[string, ToolCallFrame]> = [
    [
      "arguments with several value kinds",
      {
        tool_name: "codex_search",
        arguments: { query: "Halden", limit: 5, archived: false },
      },
    ],
    ["empty arguments", { tool_name: "web_search", arguments: {} }],
    [
      "nested arguments",
      { tool_name: "write_codex_draft", arguments: { field: "body", meta: { n: 1 } } },
    ],
  ];

  it.each(callCases)("DoD-5: tool_call parses — %s", async (_label, frame) => {
    const turn = await openTurn();

    turn.fire("tool_call", frame);

    expect(turn.onToolCall).toHaveBeenCalledTimes(1);
    const received = turn.onToolCall.mock.calls[0][0] as ToolCallFrame;
    expect(received.tool_name).toBe(frame.tool_name);
    expect(received.arguments).toEqual(frame.arguments);
    // A tool_call is never mistaken for a tool_result.
    expect(turn.onToolResult).not.toHaveBeenCalled();
  });

  const resultCases: Array<[string, ToolResultFrame]> = [
    [
      "a successful result",
      { tool_name: "codex_search", result: "3 hits: Halden, Northgate", ok: true },
    ],
    // `ok: false` and an empty `result` are FALSY but perfectly well-formed — a
    // narrowing that defaulted or dropped on falsiness would lose the failure the
    // trace exists to show.
    [
      "a failed result (ok false)",
      { tool_name: "write_codex_draft", result: "the tool failed: no subject", ok: false },
    ],
    ["an empty result string", { tool_name: "web_search", result: "", ok: true }],
  ];

  it.each(resultCases)("DoD-5: tool_result parses — %s", async (_label, frame) => {
    const turn = await openTurn();

    turn.fire("tool_result", frame);

    expect(turn.onToolResult).toHaveBeenCalledTimes(1);
    const received = turn.onToolResult.mock.calls[0][0] as ToolResultFrame;
    expect(received.tool_name).toBe(frame.tool_name);
    expect(received.result).toBe(frame.result);
    expect(received.ok).toBe(frame.ok);
    expect(turn.onToolCall).not.toHaveBeenCalled();
  });
});

/* ------------------------------------------------ malformed frames are dropped */

describe("a malformed tool frame is dropped, never forwarded (DoD-5)", () => {
  const malformedCalls: Array<[string, unknown]> = [
    ["not an object (null)", null],
    ["not an object (string)", "tool_call"],
    ["not an object (number)", 42],
    ["empty object", {}],
    ["missing tool_name", { arguments: { query: "x" } }],
    ["missing arguments", { tool_name: "codex_search" }],
    ["tool_name of the wrong type", { tool_name: 7, arguments: {} }],
    ["arguments of the wrong type", { tool_name: "codex_search", arguments: "query=x" }],
    ["null arguments", { tool_name: "codex_search", arguments: null }],
  ];

  it.each(malformedCalls)(
    "DoD-5: a malformed tool_call is dropped — %s",
    async (_label, payload) => {
      const turn = await openTurn();

      turn.fire("tool_call", payload);

      // Dropped whole: no partially-narrowed, no defaulted frame reaches a handler.
      expect(turn.onToolCall).not.toHaveBeenCalled();
      expect(turn.onToolResult).not.toHaveBeenCalled();
    },
  );

  const malformedResults: Array<[string, unknown]> = [
    ["not an object (null)", null],
    ["not an object (string)", "tool_result"],
    ["empty object", {}],
    ["missing tool_name", { result: "ok", ok: true }],
    ["missing result", { tool_name: "codex_search", ok: true }],
    ["missing ok", { tool_name: "codex_search", result: "3 hits" }],
    ["tool_name of the wrong type", { tool_name: null, result: "3 hits", ok: true }],
    ["result of the wrong type", { tool_name: "codex_search", result: 3, ok: true }],
    ["ok of the wrong type", { tool_name: "codex_search", result: "3 hits", ok: "true" }],
  ];

  it.each(malformedResults)(
    "DoD-5: a malformed tool_result is dropped — %s",
    async (_label, payload) => {
      const turn = await openTurn();

      turn.fire("tool_result", payload);

      expect(turn.onToolResult).not.toHaveBeenCalled();
      expect(turn.onToolCall).not.toHaveBeenCalled();
    },
  );

  it("DoD-5: dropping a malformed frame does not disturb the frames around it", async () => {
    const turn = await openTurn();

    turn.fire("tool_call", { tool_name: "codex_search", arguments: { query: "a" } });
    turn.fire("tool_call", { tool_name: 7, arguments: {} }); // dropped
    turn.fire("tool_result", { tool_name: "codex_search", result: "3 hits", ok: true });

    // The two well-formed frames still arrived, exactly once each; the malformed
    // one simply never happened.
    expect(turn.onToolCall).toHaveBeenCalledTimes(1);
    expect(turn.onToolResult).toHaveBeenCalledTimes(1);
  });
});
