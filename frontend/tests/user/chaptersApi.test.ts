/**
 * The chapter wire module — 014.chapter-skeleton / 005.chapters-api-and-book-hub,
 * DoD-7 · DoD-8 · DoD-9.
 * (DoD-1..6 are the hub page's — `BookHubPage.test.tsx`. DoD-10 is [manual/live].)
 *
 * Bound to the frozen signatures in status.md -> `## Skeleton` (step 005):
 *   listChapters(bookId, signal?): Promise<ChapterListResponse>
 *   getChapter(bookId, chapterId, signal?): Promise<ChapterResponse>
 *   createChapter(bookId, body: CreateChapterRequest, signal?): Promise<ChapterResponse>
 *   updateChapterSketch(bookId, chapterId, body: UpdateChapterSketchRequest, signal?)
 *                                                            : Promise<ChapterResponse>
 *   removeChapter(bookId, chapterId, signal?): Promise<void>
 *   reorderChapters(bookId, body: ReorderChaptersRequest, signal?)
 *                                                        : Promise<ChapterListResponse>
 *   getOwnChapterSystemPrompt(bookId, chapterId, signal?)
 *                                                : Promise<ChapterAuthorPromptResponse>
 *   updateOwnChapterSystemPrompt(bookId, chapterId, body: UpdateChapterAuthorPromptRequest,
 *                                signal?)        : Promise<ChapterAuthorPromptResponse>
 * and, from the shared api layer:
 *   class ApiError extends Error { constructor(status, message, details?) }
 *   request<T>(url, opts): Promise<T>            // opts: { method?; body?; signal? }
 *
 * The module under test IS the api layer, so `api/client` — never `fetch`, never the
 * chapters module itself — is mocked, and the URL / method / body / signal handed to
 * `request` are the observable contract. The `importOriginal` spread keeps the REAL
 * `ApiError` class for the failure branch.
 *
 * Expected values come from the spec, never from the module's code:
 *   - every path and method is `context.md` -> "Endpoints", verbatim:
 *       GET    /api/books/{book_id}/chapters
 *       POST   /api/books/{book_id}/chapters
 *       GET    /api/books/{book_id}/chapters/{chapter_id}
 *       PATCH  /api/books/{book_id}/chapters/{chapter_id}
 *       DELETE /api/books/{book_id}/chapters/{chapter_id}
 *       PUT    /api/books/{book_id}/chapters/order
 *       GET    /api/books/{book_id}/chapters/{chapter_id}/system-prompt
 *       PUT    /api/books/{book_id}/chapters/{chapter_id}/system-prompt
 *     and `signal?` is the trailing argument of every one of them (`context.md` ->
 *     cross-cutting frontend constraints) — DoD-7;
 *   - the list call returns the WHOLE envelope, `can_reorder` included — the deliberate
 *     departure from `api/codex.ts`'s unwrap, because steps 006 and 007 need the hint
 *     (`context.md`) — DoD-8;
 *   - `DELETE` answers 204 with an empty body, so the remove call must tolerate a
 *     response there is nothing to parse — DoD-9;
 *   - ids cross the wire as strings (`context.md` -> "The wire contract"), so the id
 *     fixtures are strings beyond 2^53.
 *
 * An omitted `method` IS a GET (fetch semantics), so the read assertions accept either
 * an absent `method` or an explicit "GET" — and nothing else.
 *
 * `globals: false`: every primitive is imported explicitly. `restoreMocks` wipes
 * implementations between tests, so each case sets its own via `vi.mocked(...)`.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import type {
  ChapterAuthorPromptResponse,
  ChapterListResponse,
  ChapterResponse,
  CreateChapterRequest,
  ReorderChaptersRequest,
  UpdateChapterAuthorPromptRequest,
  UpdateChapterSketchRequest,
} from "../../src/types/chapters";
import { ApiError, request } from "../../src/api/client";
import * as chaptersApi from "../../src/api/chapters";

// Module-factory mock with `importOriginal`: only `request` is replaced, so `ApiError`
// stays the real class the module under test lets propagate.
vi.mock("../../src/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../src/api/client")>();
  return { ...actual, request: vi.fn() };
});

/** The options bag `request` accepts — read off the frozen signature itself. */
type ClientOpts = Parameters<typeof request>[1];

/** Snowflake ids as they cross the wire: strings beyond 2^53. */
const BOOK_ID = "9007199254740993";
const CHAPTER_ID = "9007199254740995";
const OTHER_CHAPTER_ID = "9007199254740997";

/** The endpoint family, straight from `context.md` -> "Endpoints". */
const BASE = `/api/books/${BOOK_ID}/chapters`;

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

function makeChapter(id: string, ordinal: number, title: string): ChapterResponse {
  return {
    id,
    book_id: BOOK_ID,
    ordinal,
    title,
    state: "planned",
    sketch: `A sketch for ${title}.`,
    version: 1,
    created_at: "2026-01-02T09:00:00Z",
    modified_at: "2026-01-03T09:00:00Z",
    summary: null,
    summary_status: null,
  };
}

function makeList(canReorder: boolean): ChapterListResponse {
  return {
    chapters: [
      makeChapter(CHAPTER_ID, 1, "The Ravens Depart"),
      makeChapter(OTHER_CHAPTER_ID, 2, "Winter at Castle Black"),
    ],
    can_reorder: canReorder,
  };
}

function makePrompt(systemPrompt: string): ChapterAuthorPromptResponse {
  return {
    chapter_id: CHAPTER_ID,
    system_prompt: systemPrompt,
    modified_at: "2026-07-01T12:00:00Z",
  };
}

const CREATE_BODY: CreateChapterRequest = {
  title: "The Ravens Depart",
  sketch: "Jon sends the ravens south.",
};

const SKETCH_BODY: UpdateChapterSketchRequest = {
  sketch: "Jon sends the ravens south, and one comes back.",
};

const REORDER_BODY: ReorderChaptersRequest = {
  chapter_ids: [OTHER_CHAPTER_ID, CHAPTER_ID],
};

const PROMPT_BODY: UpdateChapterAuthorPromptRequest = {
  system_prompt: "Keep this chapter in Jon's point of view.",
};

beforeEach(() => {
  // `restoreMocks` wipes implementations between tests; a benign default keeps a case
  // that forgets to arrange from hitting an undefined resolution.
  vi.mocked(request).mockResolvedValue(makeList(false));
});

describe("chapters api — the chapter route family (DoD-7)", () => {
  it("DoD-7: listChapters GETs /api/books/{id}/chapters and passes the signal", async () => {
    const envelope = makeList(true);
    vi.mocked(request).mockResolvedValue(envelope);
    const controller = new AbortController();

    const result = await chaptersApi.listChapters(BOOK_ID, controller.signal);

    const { url, opts } = onlyCall();
    expect(url).toBe(BASE);
    expect(methodOf(opts)).toBe("GET");
    expect(opts?.signal).toBe(controller.signal);
    expect(result).toEqual(envelope);
  });

  it("DoD-7: getChapter GETs /api/books/{id}/chapters/{chapterId} and passes the signal", async () => {
    const chapter = makeChapter(CHAPTER_ID, 1, "The Ravens Depart");
    vi.mocked(request).mockResolvedValue(chapter);
    const controller = new AbortController();

    const result = await chaptersApi.getChapter(BOOK_ID, CHAPTER_ID, controller.signal);

    const { url, opts } = onlyCall();
    expect(url).toBe(`${BASE}/${CHAPTER_ID}`);
    expect(methodOf(opts)).toBe("GET");
    expect(opts?.signal).toBe(controller.signal);
    expect(result).toEqual(chapter);
  });

  it("DoD-7: createChapter POSTs /api/books/{id}/chapters with the create body and passes the signal", async () => {
    const created = makeChapter(CHAPTER_ID, 1, CREATE_BODY.title);
    vi.mocked(request).mockResolvedValue(created);
    const controller = new AbortController();

    const result = await chaptersApi.createChapter(BOOK_ID, CREATE_BODY, controller.signal);

    const { url, opts } = onlyCall();
    expect(url).toBe(BASE);
    expect(methodOf(opts)).toBe("POST");
    expect(opts?.body).toEqual(CREATE_BODY);
    expect(opts?.signal).toBe(controller.signal);
    expect(result).toEqual(created);
  });

  it("DoD-7: updateChapterSketch PATCHes /api/books/{id}/chapters/{chapterId} with the sketch body", async () => {
    const updated = makeChapter(CHAPTER_ID, 1, "The Ravens Depart");
    vi.mocked(request).mockResolvedValue(updated);
    const controller = new AbortController();

    const result = await chaptersApi.updateChapterSketch(
      BOOK_ID,
      CHAPTER_ID,
      SKETCH_BODY,
      controller.signal,
    );

    const { url, opts } = onlyCall();
    expect(url).toBe(`${BASE}/${CHAPTER_ID}`);
    expect(methodOf(opts)).toBe("PATCH");
    expect(opts?.body).toEqual(SKETCH_BODY);
    expect(opts?.signal).toBe(controller.signal);
    expect(result).toEqual(updated);
  });

  it("DoD-7: removeChapter DELETEs /api/books/{id}/chapters/{chapterId} and passes the signal", async () => {
    vi.mocked(request).mockResolvedValue(undefined);
    const controller = new AbortController();

    await chaptersApi.removeChapter(BOOK_ID, CHAPTER_ID, controller.signal);

    const { url, opts } = onlyCall();
    expect(url).toBe(`${BASE}/${CHAPTER_ID}`);
    expect(methodOf(opts)).toBe("DELETE");
    expect(opts?.signal).toBe(controller.signal);
  });

  it("DoD-7: reorderChapters PUTs /api/books/{id}/chapters/order with the ordered id list", async () => {
    const envelope = makeList(true);
    vi.mocked(request).mockResolvedValue(envelope);
    const controller = new AbortController();

    const result = await chaptersApi.reorderChapters(BOOK_ID, REORDER_BODY, controller.signal);

    const { url, opts } = onlyCall();
    // The bulk-reorder path, NOT a `/{chapter_id}` path.
    expect(url).toBe(`${BASE}/order`);
    expect(methodOf(opts)).toBe("PUT");
    expect(opts?.body).toEqual(REORDER_BODY);
    expect(opts?.signal).toBe(controller.signal);
    // Reorder answers with the list envelope, exactly as the list call does.
    expect(result).toEqual(envelope);
    expect(result.can_reorder).toBe(true);
  });

  it("DoD-7: getOwnChapterSystemPrompt GETs the chapter's system-prompt path and passes the signal", async () => {
    const prompt = makePrompt("Keep this chapter in Jon's point of view.");
    vi.mocked(request).mockResolvedValue(prompt);
    const controller = new AbortController();

    const result = await chaptersApi.getOwnChapterSystemPrompt(
      BOOK_ID,
      CHAPTER_ID,
      controller.signal,
    );

    const { url, opts } = onlyCall();
    expect(url).toBe(`${BASE}/${CHAPTER_ID}/system-prompt`);
    expect(methodOf(opts)).toBe("GET");
    expect(opts?.signal).toBe(controller.signal);
    expect(result).toEqual(prompt);
  });

  it("DoD-7: updateOwnChapterSystemPrompt PUTs the chapter's system-prompt path with the prompt body", async () => {
    const stored = makePrompt(PROMPT_BODY.system_prompt);
    vi.mocked(request).mockResolvedValue(stored);
    const controller = new AbortController();

    const result = await chaptersApi.updateOwnChapterSystemPrompt(
      BOOK_ID,
      CHAPTER_ID,
      PROMPT_BODY,
      controller.signal,
    );

    const { url, opts } = onlyCall();
    expect(url).toBe(`${BASE}/${CHAPTER_ID}/system-prompt`);
    // PUT is the upsert — there is no POST and no DELETE on this path.
    expect(methodOf(opts)).toBe("PUT");
    expect(opts?.body).toEqual(PROMPT_BODY);
    expect(opts?.signal).toBe(controller.signal);
    expect(result).toEqual(stored);
  });

  it("DoD-7: every function addresses the book id it was given, and the signal is optional", async () => {
    const otherBookId = "12345678901234567";
    vi.mocked(request).mockResolvedValue(makeList(false));

    await chaptersApi.listChapters(otherBookId);

    const { url, opts } = onlyCall();
    expect(url).toBe(`/api/books/${otherBookId}/chapters`);
    expect(opts?.signal).toBeUndefined();
  });

  it("DoD-7: a refusal from the wrapper surfaces as the very same ApiError, status intact", async () => {
    const err = new ApiError(403, "Only the owner may set chapter order");
    vi.mocked(request).mockRejectedValue(err);

    const caught: unknown = await chaptersApi
      .reorderChapters(BOOK_ID, REORDER_BODY)
      .then(() => undefined)
      .catch((reason: unknown) => reason);

    expect(caught).toBe(err);
    expect(caught).toBeInstanceOf(ApiError);
    expect((caught as ApiError).status).toBe(403);
  });
});

describe("chapters api — the list envelope survives (DoD-8)", () => {
  it("DoD-8: listChapters resolves to the ENVELOPE, not a bare array, with can_reorder true", async () => {
    const envelope = makeList(true);
    vi.mocked(request).mockResolvedValue(envelope);

    const result = await chaptersApi.listChapters(BOOK_ID);

    // Not unwrapped the way `api/codex.ts` unwraps its list — the hint must survive.
    expect(Array.isArray(result)).toBe(false);
    expect(result).toEqual(envelope);
    expect(result.can_reorder).toBe(true);
    expect(result.chapters).toEqual(envelope.chapters);
    expect(result.chapters).toHaveLength(2);
  });

  it("DoD-8: can_reorder false also survives — the field is carried, not derived", async () => {
    const envelope = makeList(false);
    vi.mocked(request).mockResolvedValue(envelope);

    const result = await chaptersApi.listChapters(BOOK_ID);

    expect(result.can_reorder).toBe(false);
    expect(result.chapters).toHaveLength(2);
  });

  it("DoD-8: an empty book still resolves to the envelope, with can_reorder intact", async () => {
    const empty: ChapterListResponse = { chapters: [], can_reorder: true };
    vi.mocked(request).mockResolvedValue(empty);

    const result = await chaptersApi.listChapters(BOOK_ID);

    expect(Array.isArray(result)).toBe(false);
    expect(result).toEqual(empty);
    expect(result.chapters).toEqual([]);
    expect(result.can_reorder).toBe(true);
  });
});

describe("chapters api — the empty 204 body (DoD-9)", () => {
  it("DoD-9: removeChapter resolves against an empty 204 response, parsing nothing", async () => {
    // `DELETE` answers 204: the wrapper resolves with no value at all, and the remove
    // call must neither read nor parse a body from it.
    vi.mocked(request).mockResolvedValue(undefined);

    const result = await chaptersApi.removeChapter(BOOK_ID, CHAPTER_ID);

    expect(result).toBeUndefined();
    expect(vi.mocked(request)).toHaveBeenCalledTimes(1);
  });

  it("DoD-9: removeChapter sends no body and still resolves without a signal", async () => {
    vi.mocked(request).mockResolvedValue(undefined);

    await expect(chaptersApi.removeChapter(BOOK_ID, CHAPTER_ID)).resolves.toBeUndefined();

    const { url, opts } = onlyCall();
    expect(url).toBe(`${BASE}/${CHAPTER_ID}`);
    expect(methodOf(opts)).toBe("DELETE");
    expect(opts?.body).toBeUndefined();
    expect(opts?.signal).toBeUndefined();
  });

  it("DoD-9: a refused delete still surfaces its ApiError rather than an empty resolution", async () => {
    const err = new ApiError(409, "Only a planned chapter may be removed");
    vi.mocked(request).mockRejectedValue(err);

    await expect(chaptersApi.removeChapter(BOOK_ID, CHAPTER_ID)).rejects.toBe(err);
  });
});
