import { request } from "./client";
import type {
  CreateMemoRequest,
  MemoResponse,
  ReorderMemosRequest,
  UpdateMemoRequest,
} from "../types/memos";

// Memo resource module (book-nested `/api/books/{book_id}/memos` surface, backend
// feature 026 steps 003 / 004 / 005). Mirrors `api/codex.ts` and `api/chats.ts`: a
// module-level `/api/books` base, the STRING snowflake ids interpolated straight
// into the path, `signal?` as the trailing argument on every function, and the list
// envelope (`{ items: [...] }`) handled HERE rather than modelled in
// `types/memos.d.ts`.
//
// Namespace-imported by callers (`import * as memosApi from "../../api/memos"`).
// All JSON HTTP goes through `client.request<T>` (Bearer injection, `ApiError`
// normalization, signal pass-through). NO state, NO MobX, and NO error swallowing:
// an `ApiError` propagates to the caller, whose state class decides what to show.
//
// Two axes, four verbs (`026/context.md`): `active` and `archived` are independent,
// so activate / deactivate / archive / restore each get their own bodyless `POST`
// rather than sharing a `PATCH`. Each is an idempotent `200` no-op when the memo is
// already in the requested state — there is no `409` anywhere on this surface, and
// there is NO `DELETE` verb at any path (archive-not-delete, UC-107).
//
// Every body is a thin `request<T>` forwarder (the `api/chats.ts` precedent): the
// method and path stated in each docstring, and nothing else.

const BASE = "/api/books";

/**
 * `GET /api/books/{bookId}/memos?include_archived=<flag>` — the caller's own memos
 * for a book, in `ordinal` order. Nobody else's memos are reachable on this route:
 * the server scopes every read to the caller (`026/context.md` decision 3).
 *
 * Unwraps `.items` from the list envelope and resolves to the plain array — the
 * ONLY function in this module that unwraps.
 */
export async function listMemos(
  bookId: string,
  includeArchived: boolean,
  signal?: AbortSignal,
): Promise<MemoResponse[]> {
  const res = await request<{ items: MemoResponse[] }>(
    `${BASE}/${bookId}/memos?include_archived=${includeArchived}`,
    { signal },
  );
  return res.items;
}

/**
 * `POST /api/books/{bookId}/memos` — create a memo, appended last; returns the
 * created memo. A body of `""` is legitimate (UC-103 creates an empty memo and
 * focuses it), so this is never withheld for a blank draft.
 */
export async function createMemo(
  bookId: string,
  body: CreateMemoRequest,
  signal?: AbortSignal,
): Promise<MemoResponse> {
  return request<MemoResponse>(`${BASE}/${bookId}/memos`, {
    method: "POST",
    body,
    signal,
  });
}

/**
 * `PUT /api/books/{bookId}/memos/{memoId}` — write a memo's body (the focus-loss
 * save, UC-104). Carries the body and nothing else: no version token, no state
 * flags. Returns the updated memo.
 */
export async function updateMemoBody(
  bookId: string,
  memoId: string,
  body: UpdateMemoRequest,
  signal?: AbortSignal,
): Promise<MemoResponse> {
  return request<MemoResponse>(`${BASE}/${bookId}/memos/${memoId}`, {
    method: "PUT",
    body,
    signal,
  });
}

/**
 * `PUT /api/books/{bookId}/memos/order` — set the caller's memo order from the FULL
 * ordered id list of their non-archived memos (a list that is not exactly that set
 * comes back as an `ApiError` with status `400`). Resolves to the refreshed list
 * envelope — deliberately NOT unwrapped (`009` DoD-8: the `items` envelope is
 * unwrapped on the LIST call only), matching `api/chapters.ts:reorderChapters`,
 * which also resolves to its envelope.
 */
export async function reorderMemos(
  bookId: string,
  body: ReorderMemosRequest,
  signal?: AbortSignal,
): Promise<{ items: MemoResponse[] }> {
  return request<{ items: MemoResponse[] }>(`${BASE}/${bookId}/memos/order`, {
    method: "PUT",
    body,
    signal,
  });
}

/**
 * `POST /api/books/{bookId}/memos/{memoId}/activate` — switch a memo ON, so it
 * reaches the assistant again (UC-106). No request body; returns the memo.
 */
export async function activateMemo(
  bookId: string,
  memoId: string,
  signal?: AbortSignal,
): Promise<MemoResponse> {
  return request<MemoResponse>(`${BASE}/${bookId}/memos/${memoId}/activate`, {
    method: "POST",
    signal,
  });
}

/**
 * `POST /api/books/{bookId}/memos/{memoId}/deactivate` — switch a memo OFF: it stays
 * in the list and leaves the assistant's prompt (UC-106). No request body; returns
 * the memo.
 */
export async function deactivateMemo(
  bookId: string,
  memoId: string,
  signal?: AbortSignal,
): Promise<MemoResponse> {
  return request<MemoResponse>(`${BASE}/${bookId}/memos/${memoId}/deactivate`, {
    method: "POST",
    signal,
  });
}

/**
 * `POST /api/books/{bookId}/memos/{memoId}/archive` — archive a memo (UC-107): it
 * leaves the working list and the prompt, keeps its `active` flag, and leaves a gap
 * in the ordinals that is never renumbered. No request body; returns the memo.
 */
export async function archiveMemo(
  bookId: string,
  memoId: string,
  signal?: AbortSignal,
): Promise<MemoResponse> {
  return request<MemoResponse>(`${BASE}/${bookId}/memos/${memoId}/archive`, {
    method: "POST",
    signal,
  });
}

/**
 * `POST /api/books/{bookId}/memos/{memoId}/restore` — bring an archived memo back,
 * appended LAST rather than into its old slot, with the `active` flag it carried
 * when it was archived (UC-107). No request body; returns the memo.
 */
export async function restoreMemo(
  bookId: string,
  memoId: string,
  signal?: AbortSignal,
): Promise<MemoResponse> {
  return request<MemoResponse>(`${BASE}/${bookId}/memos/${memoId}/restore`, {
    method: "POST",
    signal,
  });
}
