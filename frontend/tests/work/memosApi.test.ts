/**
 * The memo wire module — 026.memos / 009.memos-api-and-navigator, DoD-8.
 * (DoD-1..3 are the navigator's — `tests/work/navItems.test.ts`; DoD-4 is the route
 * table's — `tests/work/routes.test.tsx`; DoD-5..7 are the subject model's —
 * `tests/work/subject.test.ts`. DoD-9 is [manual/live].)
 *
 * Placed by AREA, not by layer, following the repo's existing convention: an api spec
 * lives in its area folder under a `<resource>Api.test.ts` name
 * (`tests/user/chaptersApi.test.ts`, `tests/admin/assistantConfigApi.test.ts`). Memos
 * are a work-area resource, so this sits beside the other three step-009 specs.
 *
 * Bound to the frozen signatures in status.md -> `## Skeleton` (step 009):
 *   listMemos(bookId, includeArchived: boolean, signal?): Promise<MemoResponse[]>
 *   createMemo(bookId, body: CreateMemoRequest, signal?): Promise<MemoResponse>
 *   updateMemoBody(bookId, memoId, body: UpdateMemoRequest, signal?): Promise<MemoResponse>
 *   reorderMemos(bookId, body: ReorderMemosRequest, signal?)
 *                                              : Promise<{ items: MemoResponse[] }>
 *   activateMemo(bookId, memoId, signal?): Promise<MemoResponse>
 *   deactivateMemo(bookId, memoId, signal?): Promise<MemoResponse>
 *   archiveMemo(bookId, memoId, signal?): Promise<MemoResponse>
 *   restoreMemo(bookId, memoId, signal?): Promise<MemoResponse>
 * and, from the shared api layer:
 *   class ApiError extends Error { constructor(status, message, details?) }
 *   request<T>(url, opts): Promise<T>            // opts: { method?; body?; signal? }
 *
 * The module under test IS the api layer, so `api/client` — never `fetch`, never the
 * memos module itself — is mocked, and the URL / method / body / signal handed to
 * `request` are the observable contract (`009.context.md` -> "For DoD-8, an api-module
 * spec mocks `../../src/api/client` (not `fetch`)"). The `importOriginal` spread keeps
 * the REAL `ApiError` class for the propagation case.
 *
 * Expected values come from the spec, never from the module's code:
 *   - every path and method is `context.md` -> "The wire contract", verbatim:
 *       GET  /api/books/{book_id}/memos?include_archived=<flag>
 *       POST /api/books/{book_id}/memos
 *       PUT  /api/books/{book_id}/memos/order
 *       PUT  /api/books/{book_id}/memos/{memo_id}
 *       POST /api/books/{book_id}/memos/{memo_id}/activate
 *       POST /api/books/{book_id}/memos/{memo_id}/deactivate
 *       POST /api/books/{book_id}/memos/{memo_id}/archive
 *       POST /api/books/{book_id}/memos/{memo_id}/restore
 *     and `signal?` is the trailing argument of every one of them (`context.md` ->
 *     cross-cutting frontend constraints);
 *   - ids cross the wire as STRINGS (`context.md` -> "Ids are strings on the wire";
 *     snowflakes exceed 2^53), so every id fixture is a string beyond 2^53 and must
 *     reach the URL unmangled — no `Number(...)` on this surface;
 *   - the include-archived flag is SENT on the list call (`?include_archived=`), both
 *     values, because the caller always states which list it wants;
 *   - the `{ items: [...] }` envelope is unwrapped on the LIST CALL ONLY (DoD-8).
 *     `reorderMemos` therefore resolves to the envelope, exactly as
 *     `api/chapters.ts:reorderChapters` resolves to its own list envelope; envelopes
 *     are deliberately not modelled in `.d.ts` (`context.md` -> cross-cutting
 *     frontend constraints);
 *   - the four state verbs send NO request body — two independent axes, four verbs
 *     (`context.md` -> "Two axes, four verbs");
 *   - there is NO `DELETE` at any path (`context.md` -> decision 6, "No DELETE,
 *     anywhere, ever");
 *   - no error swallowing: an `ApiError` from the wrapper propagates to the caller.
 *
 * An omitted `method` IS a GET (fetch semantics), so the read assertion accepts either
 * an absent `method` or an explicit "GET" — and nothing else.
 *
 * `globals: false`: every primitive is imported explicitly. `restoreMocks` wipes
 * implementations between tests, so each case sets its own via `vi.mocked(...)`.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import type {
  CreateMemoRequest,
  MemoResponse,
  ReorderMemosRequest,
  UpdateMemoRequest,
} from "../../src/types/memos";
import { ApiError, request } from "../../src/api/client";
import * as memosApi from "../../src/api/memos";

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
const MEMO_ID = "9007199254740995";
const OTHER_MEMO_ID = "9007199254740997";

/** The endpoint family, straight from `context.md` -> "The wire contract". */
const BASE = `/api/books/${BOOK_ID}/memos`;

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

function makeMemo(id: string, ordinal: number, body: string): MemoResponse {
  return {
    id,
    book_id: BOOK_ID,
    body,
    ordinal,
    active: true,
    archived: false,
    created_at: "2026-09-01T09:00:00Z",
    modified_at: "2026-09-02T09:00:00Z",
  };
}

/** The list envelope the backend answers with — deliberately not modelled in `.d.ts`. */
function makeEnvelope(): { items: MemoResponse[] } {
  return {
    items: [
      makeMemo(MEMO_ID, 1, "Keep the prose plain."),
      makeMemo(OTHER_MEMO_ID, 2, "Never name the king."),
    ],
  };
}

const CREATE_BODY: CreateMemoRequest = { body: "" };

const UPDATE_BODY: UpdateMemoRequest = { body: "Keep the prose plain and cold." };

const REORDER_BODY: ReorderMemosRequest = { memo_ids: [OTHER_MEMO_ID, MEMO_ID] };

/** The four state verbs, each with the path segment the wire contract names. */
const STATE_VERBS: Array<[string, (bookId: string, memoId: string, signal?: AbortSignal) => Promise<MemoResponse>]> = [
  ["activate", memosApi.activateMemo],
  ["deactivate", memosApi.deactivateMemo],
  ["archive", memosApi.archiveMemo],
  ["restore", memosApi.restoreMemo],
];

beforeEach(() => {
  // `restoreMocks` wipes implementations between tests; a benign default keeps a case
  // that forgets to arrange from hitting an undefined resolution.
  vi.mocked(request).mockResolvedValue(makeEnvelope());
});

describe("memos api — the list call (DoD-8)", () => {
  it("DoD-8: listMemos GETs the memos path with include_archived=false and passes the signal", async () => {
    vi.mocked(request).mockResolvedValue(makeEnvelope());
    const controller = new AbortController();

    await memosApi.listMemos(BOOK_ID, false, controller.signal);

    const { url, opts } = onlyCall();
    expect(url).toBe(`${BASE}?include_archived=false`);
    expect(methodOf(opts)).toBe("GET");
    expect(opts?.signal).toBe(controller.signal);
  });

  it("DoD-8: listMemos sends include_archived=true when the archived list is asked for", async () => {
    vi.mocked(request).mockResolvedValue(makeEnvelope());

    await memosApi.listMemos(BOOK_ID, true);

    const { url, opts } = onlyCall();
    expect(url).toBe(`${BASE}?include_archived=true`);
    expect(opts?.signal).toBeUndefined();
  });

  it("DoD-8: listMemos UNWRAPS the items envelope and resolves to the memo array", async () => {
    const envelope = makeEnvelope();
    vi.mocked(request).mockResolvedValue(envelope);

    const result = await memosApi.listMemos(BOOK_ID, false);

    expect(Array.isArray(result)).toBe(true);
    expect(result).toEqual(envelope.items);
    expect(result).toHaveLength(2);
  });

  it("DoD-8: an empty memo list unwraps to an empty array, not to the envelope", async () => {
    vi.mocked(request).mockResolvedValue({ items: [] });

    const result = await memosApi.listMemos(BOOK_ID, false);

    expect(Array.isArray(result)).toBe(true);
    expect(result).toEqual([]);
  });
});

describe("memos api — create, update and reorder (DoD-8)", () => {
  it("DoD-8: createMemo POSTs the memos path with the create body and passes the signal", async () => {
    const created = makeMemo(MEMO_ID, 3, "");
    vi.mocked(request).mockResolvedValue(created);
    const controller = new AbortController();

    const result = await memosApi.createMemo(BOOK_ID, CREATE_BODY, controller.signal);

    const { url, opts } = onlyCall();
    expect(url).toBe(BASE);
    expect(methodOf(opts)).toBe("POST");
    // `""` is legitimate input on create — a new memo is created empty (UC-103).
    expect(opts?.body).toEqual(CREATE_BODY);
    expect(opts?.signal).toBe(controller.signal);
    expect(result).toEqual(created);
  });

  it("DoD-8: updateMemoBody PUTs the memo's own path with the body, id interpolated as a string", async () => {
    const updated = makeMemo(MEMO_ID, 1, UPDATE_BODY.body);
    vi.mocked(request).mockResolvedValue(updated);
    const controller = new AbortController();

    const result = await memosApi.updateMemoBody(BOOK_ID, MEMO_ID, UPDATE_BODY, controller.signal);

    const { url, opts } = onlyCall();
    // The snowflake id survives verbatim: no `Number(...)` mangling past 2^53.
    expect(url).toBe(`${BASE}/${MEMO_ID}`);
    expect(methodOf(opts)).toBe("PUT");
    expect(opts?.body).toEqual(UPDATE_BODY);
    expect(opts?.signal).toBe(controller.signal);
    expect(result).toEqual(updated);
  });

  it("DoD-8: reorderMemos PUTs the bulk `/order` path with the full ordered id list", async () => {
    const envelope = makeEnvelope();
    vi.mocked(request).mockResolvedValue(envelope);
    const controller = new AbortController();

    await memosApi.reorderMemos(BOOK_ID, REORDER_BODY, controller.signal);

    const { url, opts } = onlyCall();
    // The bulk-reorder path, NOT a `/{memo_id}` path.
    expect(url).toBe(`${BASE}/order`);
    expect(methodOf(opts)).toBe("PUT");
    expect(opts?.body).toEqual(REORDER_BODY);
    expect(opts?.signal).toBe(controller.signal);
  });

  it("DoD-8: reorderMemos does NOT unwrap — the envelope is unwrapped on the list call only", async () => {
    const envelope = makeEnvelope();
    vi.mocked(request).mockResolvedValue(envelope);

    const result = await memosApi.reorderMemos(BOOK_ID, REORDER_BODY);

    expect(Array.isArray(result)).toBe(false);
    expect(result).toEqual(envelope);
    expect(result.items).toEqual(envelope.items);
  });
});

describe("memos api — the four state verbs (DoD-8)", () => {
  for (const [verb, call] of STATE_VERBS) {
    it(`DoD-8: ${verb}Memo POSTs the memo's /${verb} path, with no request body`, async () => {
      const answered = makeMemo(MEMO_ID, 1, "Keep the prose plain.");
      vi.mocked(request).mockResolvedValue(answered);
      const controller = new AbortController();

      const result = await call(BOOK_ID, MEMO_ID, controller.signal);

      const { url, opts } = onlyCall();
      expect(url).toBe(`${BASE}/${MEMO_ID}/${verb}`);
      expect(methodOf(opts)).toBe("POST");
      // Two independent axes, four verbs: none of them carries a flag payload.
      expect(opts?.body).toBeUndefined();
      expect(opts?.signal).toBe(controller.signal);
      expect(result).toEqual(answered);
    });
  }

  it("DoD-8: the state verbs address the ids they were given, and the signal is optional", async () => {
    const otherBookId = "12345678901234567";
    vi.mocked(request).mockResolvedValue(makeMemo(OTHER_MEMO_ID, 2, "Never name the king."));

    await memosApi.archiveMemo(otherBookId, OTHER_MEMO_ID);

    const { url, opts } = onlyCall();
    expect(url).toBe(`/api/books/${otherBookId}/memos/${OTHER_MEMO_ID}/archive`);
    expect(opts?.signal).toBeUndefined();
  });
});

describe("memos api — the module swallows nothing (DoD-8)", () => {
  it("DoD-8: a refusal from the wrapper surfaces as the very same ApiError, status intact", async () => {
    // A memo that does not exist, belongs to another author, or belongs to another
    // book is ONE refusal, 404 (`context.md` -> decision 3).
    const err = new ApiError(404, "Memo not found");
    vi.mocked(request).mockRejectedValue(err);

    const caught: unknown = await memosApi
      .updateMemoBody(BOOK_ID, MEMO_ID, UPDATE_BODY)
      .then(() => undefined)
      .catch((reason: unknown) => reason);

    expect(caught).toBe(err);
    expect(caught).toBeInstanceOf(ApiError);
    expect((caught as ApiError).status).toBe(404);
  });

  it("DoD-8: a refused list also rejects rather than resolving to an empty array", async () => {
    const err = new ApiError(403, "Not a member of this book");
    vi.mocked(request).mockRejectedValue(err);

    await expect(memosApi.listMemos(BOOK_ID, false)).rejects.toBe(err);
  });
});
