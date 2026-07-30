/**
 * The chapter WRITE wire module — 015.chapter-writing-free-mode / 004.chapter-write-api,
 * DoD-1 · DoD-2 · DoD-3 · DoD-4 · DoD-5 · DoD-6.
 * (DoD-7 is [manual/live] — `npm run build` + `npm run test:types` — and has no test here.)
 *
 * Bound to the frozen signatures in status.md -> `## Skeleton` -> "Step 004":
 *   getChapterText(bookId, chapterId, signal?): Promise<ChapterTextResponse>
 *   updateChapterText(bookId, chapterId, body: UpdateChapterTextRequest, signal?)
 *                                                       : Promise<ChapterTextResponse>
 *   openChapterState(bookId, chapterId, signal?):   Promise<ChapterResponse>
 *   closeChapterState(bookId, chapterId, signal?):  Promise<ChapterResponse>
 *   reopenChapterState(bookId, chapterId, signal?): Promise<ChapterResponse>
 * and, from the shared api layer:
 *   class ApiError extends Error { constructor(status, message, details?) }
 *   request<T>(url, opts): Promise<T>            // opts: { method?; body?; signal? }
 *
 * The module under test IS the api layer, so `api/client` — never `fetch`, never the
 * chapters module itself — is mocked, exactly as the sibling `chaptersApi.test.ts` does.
 * The `importOriginal` spread keeps the REAL `ApiError` class for DoD-5.
 *
 * Expected values come from the spec, never from the module's code. Every path and method
 * below is `015.../context.md` -> "The wire contract added by this feature" -> "Endpoints
 * added", verbatim:
 *     GET  /api/books/{book_id}/chapters/{chapter_id}/text     -> ChapterTextResponse
 *     PUT  /api/books/{book_id}/chapters/{chapter_id}/text     -> ChapterTextResponse
 *     POST /api/books/{book_id}/chapters/{chapter_id}/open     -> ChapterResponse
 *     POST /api/books/{book_id}/chapters/{chapter_id}/close    -> ChapterResponse
 *     POST /api/books/{book_id}/chapters/{chapter_id}/reopen   -> ChapterResponse
 * `signal?` is the trailing argument of all five (cross-cutting frontend constraints);
 * only the body save carries a request body; `version` / `expected_version` are numbers.
 *
 * An omitted `method` IS a GET (fetch semantics), so the read assertion accepts either an
 * absent `method` or an explicit "GET" — and nothing else.
 *
 * `globals: false`: every primitive is imported explicitly.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import type {
  ChapterListResponse,
  ChapterResponse,
  ChapterTextResponse,
  UpdateChapterTextRequest,
} from "../../src/types/chapters";
import { ApiError, request } from "../../src/api/client";
import * as chaptersApi from "../../src/api/chapters";

// Module-factory mock with `importOriginal`: only `request` is replaced, so `ApiError`
// stays the real class the module under test lets propagate (DoD-5).
vi.mock("../../src/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../src/api/client")>();
  return { ...actual, request: vi.fn() };
});

/** The options bag `request` accepts — read off the frozen signature itself. */
type ClientOpts = Parameters<typeof request>[1];

/** Snowflake ids as they cross the wire: strings beyond 2^53. */
const BOOK_ID = "9007199254740993";
const CHAPTER_ID = "9007199254740995";

/** The chapter route family, straight from `context.md` -> "Endpoints added". */
const CHAPTER_BASE = `/api/books/${BOOK_ID}/chapters/${CHAPTER_ID}`;

/** The single `request` call the function under test must have made. */
function onlyCall(): { url: string; opts: ClientOpts } {
  const calls = vi.mocked(request).mock.calls;
  expect(calls).toHaveLength(1);
  const [url, opts] = calls[0];
  return { url, opts };
}

/** An absent `method` is a GET, per fetch semantics. */
function methodOf(opts: ClientOpts): string {
  return (opts?.method ?? "GET").toUpperCase();
}

function makeText(text: string, version: number, state: "planned" | "open" | "closing" | "closed"): ChapterTextResponse {
  return {
    chapter_id: CHAPTER_ID,
    state,
    text,
    version,
    modified_at: "2026-07-03T11:30:00Z",
  };
}

function makeChapter(state: "planned" | "open" | "closing" | "closed"): ChapterResponse {
  return {
    id: CHAPTER_ID,
    book_id: BOOK_ID,
    ordinal: 1,
    title: "The Ravens Depart",
    state,
    sketch: "Jon sends the ravens south.",
    version: 4,
    created_at: "2026-01-02T09:00:00Z",
    modified_at: "2026-07-03T11:30:00Z",
  };
}

const SAVE_BODY: UpdateChapterTextRequest = {
  text: "The ravens went south at first light.\n\nNobody watched them go.",
  expected_version: 7,
};

beforeEach(() => {
  // `restoreMocks` wipes implementations between tests; a benign default keeps a case
  // that forgets to arrange from hitting an undefined resolution.
  vi.mocked(request).mockResolvedValue(makeText("", 1, "open"));
});

describe("chapters write api — paths and methods (DoD-1)", () => {
  it("DoD-1: getChapterText GETs /api/books/{bookId}/chapters/{chapterId}/text", async () => {
    vi.mocked(request).mockResolvedValue(makeText("A body.", 3, "open"));

    await chaptersApi.getChapterText(BOOK_ID, CHAPTER_ID);

    const { url, opts } = onlyCall();
    expect(url).toBe(`${CHAPTER_BASE}/text`);
    expect(methodOf(opts)).toBe("GET");
  });

  it("DoD-1: updateChapterText PUTs the same /text path", async () => {
    vi.mocked(request).mockResolvedValue(makeText(SAVE_BODY.text, 8, "open"));

    await chaptersApi.updateChapterText(BOOK_ID, CHAPTER_ID, SAVE_BODY);

    const { url, opts } = onlyCall();
    expect(url).toBe(`${CHAPTER_BASE}/text`);
    // PUT, because the whole body replaces the resource — not PATCH, not POST.
    expect(methodOf(opts)).toBe("PUT");
  });

  it("DoD-1: openChapterState POSTs /api/books/{bookId}/chapters/{chapterId}/open", async () => {
    vi.mocked(request).mockResolvedValue(makeChapter("open"));

    await chaptersApi.openChapterState(BOOK_ID, CHAPTER_ID);

    const { url, opts } = onlyCall();
    expect(url).toBe(`${CHAPTER_BASE}/open`);
    expect(methodOf(opts)).toBe("POST");
  });

  it("DoD-1: closeChapterState POSTs /api/books/{bookId}/chapters/{chapterId}/close", async () => {
    vi.mocked(request).mockResolvedValue(makeChapter("closed"));

    await chaptersApi.closeChapterState(BOOK_ID, CHAPTER_ID);

    const { url, opts } = onlyCall();
    expect(url).toBe(`${CHAPTER_BASE}/close`);
    expect(methodOf(opts)).toBe("POST");
  });

  it("DoD-1: reopenChapterState POSTs /api/books/{bookId}/chapters/{chapterId}/reopen", async () => {
    vi.mocked(request).mockResolvedValue(makeChapter("open"));

    await chaptersApi.reopenChapterState(BOOK_ID, CHAPTER_ID);

    const { url, opts } = onlyCall();
    expect(url).toBe(`${CHAPTER_BASE}/reopen`);
    expect(methodOf(opts)).toBe("POST");
  });

  it("DoD-1: the ids given are interpolated into their own segments, not a remembered pair", async () => {
    const otherBook = "12345678901234567";
    const otherChapter = "76543210987654321";
    vi.mocked(request).mockResolvedValue(makeChapter("open"));

    await chaptersApi.openChapterState(otherBook, otherChapter);

    const { url } = onlyCall();
    expect(url).toBe(`/api/books/${otherBook}/chapters/${otherChapter}/open`);
  });
});

describe("chapters write api — the abort signal (DoD-2)", () => {
  it("DoD-2: getChapterText forwards the signal it is given", async () => {
    vi.mocked(request).mockResolvedValue(makeText("A body.", 3, "open"));
    const controller = new AbortController();

    await chaptersApi.getChapterText(BOOK_ID, CHAPTER_ID, controller.signal);

    expect(onlyCall().opts?.signal).toBe(controller.signal);
  });

  it("DoD-2: updateChapterText forwards the signal it is given", async () => {
    vi.mocked(request).mockResolvedValue(makeText(SAVE_BODY.text, 8, "open"));
    const controller = new AbortController();

    await chaptersApi.updateChapterText(BOOK_ID, CHAPTER_ID, SAVE_BODY, controller.signal);

    expect(onlyCall().opts?.signal).toBe(controller.signal);
  });

  it("DoD-2: openChapterState forwards the signal it is given", async () => {
    vi.mocked(request).mockResolvedValue(makeChapter("open"));
    const controller = new AbortController();

    await chaptersApi.openChapterState(BOOK_ID, CHAPTER_ID, controller.signal);

    expect(onlyCall().opts?.signal).toBe(controller.signal);
  });

  it("DoD-2: closeChapterState forwards the signal it is given", async () => {
    vi.mocked(request).mockResolvedValue(makeChapter("closed"));
    const controller = new AbortController();

    await chaptersApi.closeChapterState(BOOK_ID, CHAPTER_ID, controller.signal);

    expect(onlyCall().opts?.signal).toBe(controller.signal);
  });

  it("DoD-2: reopenChapterState forwards the signal it is given", async () => {
    vi.mocked(request).mockResolvedValue(makeChapter("open"));
    const controller = new AbortController();

    await chaptersApi.reopenChapterState(BOOK_ID, CHAPTER_ID, controller.signal);

    expect(onlyCall().opts?.signal).toBe(controller.signal);
  });

  it("DoD-2: the signal is optional — omitting it forwards none", async () => {
    vi.mocked(request).mockResolvedValue(makeText("A body.", 3, "open"));

    await chaptersApi.getChapterText(BOOK_ID, CHAPTER_ID);

    expect(onlyCall().opts?.signal).toBeUndefined();
  });
});

describe("chapters write api — the body save (DoD-3)", () => {
  it("DoD-3: updateChapterText sends the text and the expected version as the request body", async () => {
    vi.mocked(request).mockResolvedValue(makeText(SAVE_BODY.text, 8, "open"));

    await chaptersApi.updateChapterText(BOOK_ID, CHAPTER_ID, SAVE_BODY);

    const { opts } = onlyCall();
    expect(opts?.body).toEqual(SAVE_BODY);
    expect(opts?.body).toEqual({
      text: SAVE_BODY.text,
      expected_version: 7,
    });
  });

  it("DoD-3: expected_version crosses the wire as a NUMBER, never stringified", async () => {
    const body: UpdateChapterTextRequest = { text: "Rewritten.", expected_version: 12 };
    vi.mocked(request).mockResolvedValue(makeText(body.text, 13, "open"));

    await chaptersApi.updateChapterText(BOOK_ID, CHAPTER_ID, body);

    const sent = onlyCall().opts?.body as UpdateChapterTextRequest;
    expect(typeof sent.expected_version).toBe("number");
    expect(sent.expected_version).toBe(12);
  });

  it("DoD-3: an empty body text is a legitimate save and is sent as \"\"", async () => {
    const cleared: UpdateChapterTextRequest = { text: "", expected_version: 5 };
    vi.mocked(request).mockResolvedValue(makeText("", 6, "open"));

    await chaptersApi.updateChapterText(BOOK_ID, CHAPTER_ID, cleared);

    expect(onlyCall().opts?.body).toEqual({ text: "", expected_version: 5 });
  });

  it("DoD-3: the response is returned unmodified — not unwrapped, not reshaped", async () => {
    const saved = makeText(SAVE_BODY.text, 8, "open");
    vi.mocked(request).mockResolvedValue(saved);

    const result = await chaptersApi.updateChapterText(BOOK_ID, CHAPTER_ID, SAVE_BODY);

    expect(result).toEqual(saved);
    expect(result.chapter_id).toBe(CHAPTER_ID);
    expect(result.state).toBe("open");
    expect(result.text).toBe(SAVE_BODY.text);
    expect(result.version).toBe(8);
    expect(typeof result.version).toBe("number");
    expect(result.modified_at).toBe(saved.modified_at);
  });

  it("DoD-3: getChapterText likewise returns the whole body response unmodified", async () => {
    const loaded = makeText("The ravens went south.", 7, "open");
    vi.mocked(request).mockResolvedValue(loaded);

    const result = await chaptersApi.getChapterText(BOOK_ID, CHAPTER_ID);

    expect(result).toEqual(loaded);
    expect(result.version).toBe(7);
  });
});

describe("chapters write api — the transitions are bodiless (DoD-4)", () => {
  it("DoD-4: openChapterState sends no request body", async () => {
    vi.mocked(request).mockResolvedValue(makeChapter("open"));

    await chaptersApi.openChapterState(BOOK_ID, CHAPTER_ID);

    expect(onlyCall().opts?.body).toBeUndefined();
  });

  it("DoD-4: closeChapterState sends no request body", async () => {
    vi.mocked(request).mockResolvedValue(makeChapter("closed"));

    await chaptersApi.closeChapterState(BOOK_ID, CHAPTER_ID);

    expect(onlyCall().opts?.body).toBeUndefined();
  });

  it("DoD-4: reopenChapterState sends no request body", async () => {
    vi.mocked(request).mockResolvedValue(makeChapter("open"));

    await chaptersApi.reopenChapterState(BOOK_ID, CHAPTER_ID);

    expect(onlyCall().opts?.body).toBeUndefined();
  });

  it("DoD-4: a transition resolves to the chapter response, whose state is the server's", async () => {
    const closed = makeChapter("closed");
    vi.mocked(request).mockResolvedValue(closed);

    const result = await chaptersApi.closeChapterState(BOOK_ID, CHAPTER_ID);

    expect(result).toEqual(closed);
    expect(result.state).toBe("closed");
  });
});

describe("chapters write api — refusals surface as ApiError (DoD-5)", () => {
  it("DoD-5: a stale save surfaces the 409 ApiError, status intact", async () => {
    const err = new ApiError(409, "The chapter has changed since you loaded it");
    vi.mocked(request).mockRejectedValue(err);

    const caught: unknown = await chaptersApi
      .updateChapterText(BOOK_ID, CHAPTER_ID, SAVE_BODY)
      .then(() => undefined)
      .catch((reason: unknown) => reason);

    expect(caught).toBe(err);
    expect(caught).toBeInstanceOf(ApiError);
    expect((caught as ApiError).status).toBe(409);
  });

  it("DoD-5: a proposal-mode / archived refusal surfaces the 403 ApiError, distinguishable from 409", async () => {
    const err = new ApiError(403, "This book is archived");
    vi.mocked(request).mockRejectedValue(err);

    const caught: unknown = await chaptersApi
      .updateChapterText(BOOK_ID, CHAPTER_ID, SAVE_BODY)
      .then(() => undefined)
      .catch((reason: unknown) => reason);

    expect(caught).toBeInstanceOf(ApiError);
    expect((caught as ApiError).status).toBe(403);
    expect((caught as ApiError).status).not.toBe(409);
  });

  it("DoD-5: getChapterText propagates its ApiError rather than swallowing it", async () => {
    const err = new ApiError(404, "No such chapter");
    vi.mocked(request).mockRejectedValue(err);

    await expect(chaptersApi.getChapterText(BOOK_ID, CHAPTER_ID)).rejects.toBe(err);
  });

  it("DoD-5: openChapterState propagates a 409 when another chapter is already open", async () => {
    const err = new ApiError(409, "Another chapter is already open");
    vi.mocked(request).mockRejectedValue(err);

    const caught: unknown = await chaptersApi
      .openChapterState(BOOK_ID, CHAPTER_ID)
      .then(() => undefined)
      .catch((reason: unknown) => reason);

    expect(caught).toBeInstanceOf(ApiError);
    expect((caught as ApiError).status).toBe(409);
  });

  it("DoD-5: closeChapterState propagates a 403 for a co-author", async () => {
    const err = new ApiError(403, "Only the owner may close a chapter");
    vi.mocked(request).mockRejectedValue(err);

    const caught: unknown = await chaptersApi
      .closeChapterState(BOOK_ID, CHAPTER_ID)
      .then(() => undefined)
      .catch((reason: unknown) => reason);

    expect(caught).toBeInstanceOf(ApiError);
    expect((caught as ApiError).status).toBe(403);
  });

  it("DoD-5: reopenChapterState propagates a 409 for a chapter that is not closed", async () => {
    const err = new ApiError(409, "Only a closed chapter may be reopened");
    vi.mocked(request).mockRejectedValue(err);

    const caught: unknown = await chaptersApi
      .reopenChapterState(BOOK_ID, CHAPTER_ID)
      .then(() => undefined)
      .catch((reason: unknown) => reason);

    expect(caught).toBeInstanceOf(ApiError);
    expect((caught as ApiError).status).toBe(409);
  });
});

describe("chapters write api — 014's eight functions are untouched (DoD-6)", () => {
  const CHAPTERS_BASE = `/api/books/${BOOK_ID}/chapters`;

  function makeListEnvelope(canReorder: boolean): ChapterListResponse {
    return {
      chapters: [makeChapter("planned")],
      can_reorder: canReorder,
    };
  }

  it("DoD-6: all eight of 014's exports are still present on the module", () => {
    expect(typeof chaptersApi.listChapters).toBe("function");
    expect(typeof chaptersApi.getChapter).toBe("function");
    expect(typeof chaptersApi.createChapter).toBe("function");
    expect(typeof chaptersApi.updateChapterSketch).toBe("function");
    expect(typeof chaptersApi.removeChapter).toBe("function");
    expect(typeof chaptersApi.reorderChapters).toBe("function");
    expect(typeof chaptersApi.getOwnChapterSystemPrompt).toBe("function");
    expect(typeof chaptersApi.updateOwnChapterSystemPrompt).toBe("function");
  });

  it("DoD-6: listChapters resolves to the WHOLE envelope, reorder hint included — not a bare array", async () => {
    const envelope = makeListEnvelope(true);
    vi.mocked(request).mockResolvedValue(envelope);

    const result = await chaptersApi.listChapters(BOOK_ID);

    // The sanctioned departure from `api/codex.ts`'s unwrap: the hint must survive this step.
    expect(Array.isArray(result)).toBe(false);
    expect(result).toEqual(envelope);
    expect(result.can_reorder).toBe(true);
    expect(result.chapters).toEqual(envelope.chapters);
  });

  it("DoD-6: can_reorder false survives too — the field is carried, not derived", async () => {
    const envelope = makeListEnvelope(false);
    vi.mocked(request).mockResolvedValue(envelope);

    const result = await chaptersApi.listChapters(BOOK_ID);

    expect(result.can_reorder).toBe(false);
    expect(result.chapters).toHaveLength(1);
  });

  it("DoD-6: listChapters still GETs the unsuffixed chapters path", async () => {
    vi.mocked(request).mockResolvedValue(makeListEnvelope(true));

    await chaptersApi.listChapters(BOOK_ID);

    const { url, opts } = onlyCall();
    expect(url).toBe(CHAPTERS_BASE);
    expect(methodOf(opts)).toBe("GET");
  });

  it("DoD-6: getChapter still GETs the chapter item path, with no /text suffix", async () => {
    const chapter = makeChapter("planned");
    vi.mocked(request).mockResolvedValue(chapter);

    const result = await chaptersApi.getChapter(BOOK_ID, CHAPTER_ID);

    const { url, opts } = onlyCall();
    expect(url).toBe(`${CHAPTERS_BASE}/${CHAPTER_ID}`);
    expect(methodOf(opts)).toBe("GET");
    expect(result).toEqual(chapter);
  });

  it("DoD-6: updateChapterSketch still PATCHes the chapter item path with the sketch body", async () => {
    const chapter = makeChapter("planned");
    vi.mocked(request).mockResolvedValue(chapter);

    await chaptersApi.updateChapterSketch(BOOK_ID, CHAPTER_ID, {
      sketch: "Jon sends the ravens south, and one comes back.",
    });

    const { url, opts } = onlyCall();
    expect(url).toBe(`${CHAPTERS_BASE}/${CHAPTER_ID}`);
    expect(methodOf(opts)).toBe("PATCH");
    expect(opts?.body).toEqual({ sketch: "Jon sends the ravens south, and one comes back." });
  });

  it("DoD-6: reorderChapters still PUTs the /order path and answers the envelope", async () => {
    const envelope = makeListEnvelope(true);
    vi.mocked(request).mockResolvedValue(envelope);

    const result = await chaptersApi.reorderChapters(BOOK_ID, { chapter_ids: [CHAPTER_ID] });

    const { url, opts } = onlyCall();
    expect(url).toBe(`${CHAPTERS_BASE}/order`);
    expect(methodOf(opts)).toBe("PUT");
    expect(opts?.body).toEqual({ chapter_ids: [CHAPTER_ID] });
    expect(result.can_reorder).toBe(true);
    expect(result.chapters).toEqual(envelope.chapters);
  });
});
