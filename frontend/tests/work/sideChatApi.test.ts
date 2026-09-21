/**
 * Side-chat api functions — 027.side-chats / 004.side-chat-api-and-grouping, DoD-1.
 * (DoD-2..DoD-10 are the grouping computed's — `tests/work/sideChatGrouping.test.ts`.)
 *
 * Placed by AREA, like `tests/work/memosApi.test.ts` and `tests/user/chaptersApi.test.ts`:
 * an api spec lives in its area folder under a `<resource>Api.test.ts` name.
 *
 * Bound to the frozen signatures in status.md -> `## Skeleton` -> "Step 004":
 *   startSideChat(bookId, chatId, signal?): Promise<ChatResponse>
 *   finishSideChat(bookId, chatId, sideChatId, signal?): Promise<ChatResponse>
 *   injectSideChat(bookId, chatId, sideChatId, signal?): Promise<ChatDetailResponse>
 *   deleteSideChat(bookId, chatId, sideChatId, signal?): Promise<void>
 * and, from the shared api layer:
 *   request<T>(url, opts): Promise<T>            // opts: { method?; body?; signal? }
 *   class ApiError extends Error { constructor(status, message, details?) }
 *
 * The module under test IS the api layer, so `api/client` — never `fetch`, never the
 * chats module itself — is mocked (`004.context.md` -> "Test shape for this step"), with
 * the `importOriginal` passthrough so `ApiError` / `refreshAuthToken` stay real. The
 * `(url, init)` pair handed to `request` is the observable contract.
 *
 * Expected values come from the spec, never from the module's code:
 *   - every method and path is `context.md` -> D-D, verbatim:
 *       POST   /api/books/{book_id}/chats/{chat_id}/side-chats
 *       POST   /api/books/{book_id}/chats/{chat_id}/side-chats/{side_chat_id}/finish
 *       POST   /api/books/{book_id}/chats/{chat_id}/side-chats/{side_chat_id}/inject
 *       DELETE /api/books/{book_id}/chats/{chat_id}/side-chats/{side_chat_id}
 *   - each function issues EXACTLY ONE request (DoD-1);
 *   - the trailing `signal?: AbortSignal` is forwarded (D-F);
 *   - start / finish / inject POST with NO body (D-F: "POST, no body");
 *   - each resolves with what `request` returned (DoD-1); delete resolves `void`, i.e.
 *     `undefined`, because `request<T>` resolves `undefined` on a 204 (D-F, D-D).
 *
 * `globals: false`: every primitive is imported explicitly. `restoreMocks` wipes
 * implementations between tests, so each case sets its own via `vi.mocked(...)`.
 */
import { describe, expect, it, vi } from "vitest";
import type {
  ChatDetailResponse,
  ChatMessageResponse,
  ChatResponse,
  ChatSamplingParams,
} from "../../src/types/chats";
import * as client from "../../src/api/client";
import * as chatsApi from "../../src/api/chats";

// Module-factory mock with `importOriginal`: only `request` is replaced, so `ApiError`
// and `refreshAuthToken` stay the real exports the module under test imports.
vi.mock("../../src/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../src/api/client")>();
  return { ...actual, request: vi.fn() };
});

/** The options bag `request` accepts — read off the frozen signature itself. */
type ClientOpts = Parameters<typeof client.request>[1];

const BOOK_ID = "bk-1";
const CHAT_ID = "c-1";
const SIDE_CHAT_ID = "sc-9";

/** The endpoint family, straight from `context.md` -> D-D. */
const SIDE_CHATS_URL = `/api/books/${BOOK_ID}/chats/${CHAT_ID}/side-chats`;

/** The single `request` call the function under test must have made (DoD-1: exactly one). */
function onlyCall(): { url: string; opts: ClientOpts } {
  const calls = vi.mocked(client.request).mock.calls;
  expect(calls).toHaveLength(1);
  const [url, opts] = calls[0];
  return { url, opts };
}

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

function makeMessage(id: string, position: number, sideChatId: string | null): ChatMessageResponse {
  return {
    id,
    chat_id: CHAT_ID,
    role: "user",
    content: `message ${id}`,
    reasoning: null,
    position,
    created_at: "2026-01-01T00:00:00Z",
    side_chat_id: sideChatId,
    tool_trace: null,
  };
}

describe("side-chat api — startSideChat (DoD-1)", () => {
  it("DoD-1: startSideChat POSTs …/chats/{chatId}/side-chats once, with no body, forwarding the signal, and resolves with the ChatResponse request returned", async () => {
    const started = makeChat(SIDE_CHAT_ID);
    vi.mocked(client.request).mockResolvedValue(started);
    const controller = new AbortController();

    const result = await chatsApi.startSideChat(BOOK_ID, CHAT_ID, controller.signal);

    const { url, opts } = onlyCall();
    expect(url).toBe(SIDE_CHATS_URL);
    expect(opts).toEqual(expect.objectContaining({ method: "POST", signal: controller.signal }));
    // D-F: POST with NO body.
    expect(opts?.body).toBeUndefined();
    expect(result).toBe(started);
  });
});

describe("side-chat api — finishSideChat (DoD-1)", () => {
  it("DoD-1: finishSideChat POSTs …/side-chats/{sideChatId}/finish once, with no body, forwarding the signal, and resolves with the ChatResponse request returned", async () => {
    const finished = makeChat(null);
    vi.mocked(client.request).mockResolvedValue(finished);
    const controller = new AbortController();

    const result = await chatsApi.finishSideChat(BOOK_ID, CHAT_ID, SIDE_CHAT_ID, controller.signal);

    const { url, opts } = onlyCall();
    expect(url).toBe(`${SIDE_CHATS_URL}/${SIDE_CHAT_ID}/finish`);
    expect(opts).toEqual(expect.objectContaining({ method: "POST", signal: controller.signal }));
    expect(opts?.body).toBeUndefined();
    expect(result).toBe(finished);
  });
});

describe("side-chat api — injectSideChat (DoD-1)", () => {
  it("DoD-1: injectSideChat POSTs …/side-chats/{sideChatId}/inject once, with no body, forwarding the signal, and resolves with the ChatDetailResponse request returned", async () => {
    const detail: ChatDetailResponse = {
      chat: makeChat(null),
      messages: [makeMessage("m-1", 0, null), makeMessage("m-2", 1, null)],
    };
    vi.mocked(client.request).mockResolvedValue(detail);
    const controller = new AbortController();

    const result = await chatsApi.injectSideChat(BOOK_ID, CHAT_ID, SIDE_CHAT_ID, controller.signal);

    const { url, opts } = onlyCall();
    expect(url).toBe(`${SIDE_CHATS_URL}/${SIDE_CHAT_ID}/inject`);
    expect(opts).toEqual(expect.objectContaining({ method: "POST", signal: controller.signal }));
    expect(opts?.body).toBeUndefined();
    expect(result).toBe(detail);
  });
});

describe("side-chat api — deleteSideChat (DoD-1)", () => {
  it("DoD-1: deleteSideChat DELETEs …/side-chats/{sideChatId} once, forwarding the signal, and resolves undefined (the 204 has no body)", async () => {
    vi.mocked(client.request).mockResolvedValue(undefined);
    const controller = new AbortController();

    const result = await chatsApi.deleteSideChat(BOOK_ID, CHAT_ID, SIDE_CHAT_ID, controller.signal);

    const { url, opts } = onlyCall();
    expect(url).toBe(`${SIDE_CHATS_URL}/${SIDE_CHAT_ID}`);
    expect(opts).toEqual(expect.objectContaining({ method: "DELETE", signal: controller.signal }));
    expect(opts?.body).toBeUndefined();
    expect(result).toBeUndefined();
  });
});

describe("side-chat api — the signal is optional and ids reach the URL verbatim (DoD-1)", () => {
  it("DoD-1: every function works without a signal and interpolates the ids it was given", async () => {
    const otherBook = "9007199254740993";
    const otherChat = "9007199254740995";
    const otherSide = "9007199254740997";
    const base = `/api/books/${otherBook}/chats/${otherChat}/side-chats`;

    vi.mocked(client.request).mockResolvedValue(makeChat(otherSide));
    await chatsApi.startSideChat(otherBook, otherChat);
    expect(onlyCall().url).toBe(base);
    expect(onlyCall().opts?.signal).toBeUndefined();
    vi.mocked(client.request).mockClear();

    vi.mocked(client.request).mockResolvedValue(makeChat(null));
    await chatsApi.finishSideChat(otherBook, otherChat, otherSide);
    expect(onlyCall().url).toBe(`${base}/${otherSide}/finish`);
    expect(onlyCall().opts?.signal).toBeUndefined();
    vi.mocked(client.request).mockClear();

    vi.mocked(client.request).mockResolvedValue({ chat: makeChat(null), messages: [] });
    await chatsApi.injectSideChat(otherBook, otherChat, otherSide);
    expect(onlyCall().url).toBe(`${base}/${otherSide}/inject`);
    expect(onlyCall().opts?.signal).toBeUndefined();
    vi.mocked(client.request).mockClear();

    vi.mocked(client.request).mockResolvedValue(undefined);
    await chatsApi.deleteSideChat(otherBook, otherChat, otherSide);
    expect(onlyCall().url).toBe(`${base}/${otherSide}`);
    expect(onlyCall().opts?.signal).toBeUndefined();
  });

  it("DoD-1: a refusal from the wrapper propagates as the very same ApiError, status intact", async () => {
    // A side chat that does not exist is ONE refusal, 404 (`context.md` -> D-D).
    const err = new client.ApiError(404, "Side chat not found.");
    vi.mocked(client.request).mockRejectedValue(err);

    await expect(chatsApi.finishSideChat(BOOK_ID, CHAT_ID, SIDE_CHAT_ID)).rejects.toBe(err);
  });
});
