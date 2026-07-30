import { request } from "./client";
import type {
  ChapterAuthorPromptResponse,
  ChapterListResponse,
  ChapterResponse,
  CreateChapterRequest,
  ReorderChaptersRequest,
  UpdateChapterAuthorPromptRequest,
  UpdateChapterSketchRequest,
} from "../types/chapters";

// Chapter resource module (book-nested `/api/books/{book_id}/chapters` surface,
// backend feature 014 steps 003 + 004). Mirrors `api/codex.ts`: a module-level
// `/api/books` base, the STRING snowflake ids interpolated straight into the path,
// `signal?` as the trailing argument on every function, and all JSON HTTP through
// `client.request<T>` (Bearer injection, `ApiError` normalization, signal
// pass-through, `204` → `undefined`).
//
// ONE DELIBERATE DEPARTURE FROM `api/codex.ts`: the list envelope is **not**
// unwrapped. `listChapters` and `reorderChapters` resolve to the whole
// `ChapterListResponse`, because it carries `can_reorder` and steps 006 / 007 need
// that value (`context.md` — cross-cutting frontend constraints). Unwrapping to a
// bare array would discard it.
//
// Namespace-imported by callers (`import * as chaptersApi from "../../api/chapters"`).
//
// The two prompt calls address **the caller's own** prompt for a chapter — never the
// chapter's, and never another author's; the endpoint has no way to name a user, which
// is why they are `…OwnChapterSystemPrompt`, mirroring `api/books.ts`'s
// `getOwnSystemPrompt` / `updateOwnSystemPrompt` one level down. They carry the
// `Chapter` qualifier so that a module importing both pairs by name cannot be
// ambiguous about which level it is addressing.
//
const BASE = "/api/books";

/**
 * `GET /api/books/{bookId}/chapters` — the book's chapters, ordinal-ascending.
 *
 * Resolves to the WHOLE envelope (`{ chapters, can_reorder }`), not a bare array:
 * `can_reorder` is the owner-only reorder affordance hint that steps 006 and 007
 * consume. Do not "tidy" this into an unwrap.
 */
export async function listChapters(
  bookId: string,
  signal?: AbortSignal,
): Promise<ChapterListResponse> {
  return request<ChapterListResponse>(`${BASE}/${bookId}/chapters`, { signal });
}

/** `GET /api/books/{bookId}/chapters/{chapterId}` — one chapter. */
export async function getChapter(
  bookId: string,
  chapterId: string,
  signal?: AbortSignal,
): Promise<ChapterResponse> {
  return request<ChapterResponse>(`${BASE}/${bookId}/chapters/${chapterId}`, { signal });
}

/**
 * `POST /api/books/{bookId}/chapters` — append a chapter (the server assigns the
 * ordinal); answers `201` with the created chapter.
 */
export async function createChapter(
  bookId: string,
  body: CreateChapterRequest,
  signal?: AbortSignal,
): Promise<ChapterResponse> {
  return request<ChapterResponse>(`${BASE}/${bookId}/chapters`, {
    method: "POST",
    body,
    signal,
  });
}

/**
 * `PATCH /api/books/{bookId}/chapters/{chapterId}` — edit a planned chapter's sketch
 * (the body carries the sketch alone; no version token, D6). Returns the STORED
 * chapter, so callers re-seed from the response rather than from their draft.
 */
export async function updateChapterSketch(
  bookId: string,
  chapterId: string,
  body: UpdateChapterSketchRequest,
  signal?: AbortSignal,
): Promise<ChapterResponse> {
  return request<ChapterResponse>(`${BASE}/${bookId}/chapters/${chapterId}`, {
    method: "PATCH",
    body,
    signal,
  });
}

/**
 * `DELETE /api/books/{bookId}/chapters/{chapterId}` — remove a planned chapter.
 *
 * Resolves to nothing: the endpoint answers `204` with an EMPTY body, which
 * `client.request` already turns into `undefined` without parsing. Nothing here may
 * read a response body.
 */
export async function removeChapter(
  bookId: string,
  chapterId: string,
  signal?: AbortSignal,
): Promise<void> {
  return request<void>(`${BASE}/${bookId}/chapters/${chapterId}`, {
    method: "DELETE",
    signal,
  });
}

/**
 * `PUT /api/books/{bookId}/chapters/order` — set the book's chapter order from the
 * FULL ordered id list (owner-only; a co-author is refused with `403`, a list that is
 * not exactly the book's chapter set with `400`). Resolves to the refreshed list
 * envelope, `can_reorder` included.
 */
export async function reorderChapters(
  bookId: string,
  body: ReorderChaptersRequest,
  signal?: AbortSignal,
): Promise<ChapterListResponse> {
  return request<ChapterListResponse>(`${BASE}/${bookId}/chapters/order`, {
    method: "PUT",
    body,
    signal,
  });
}

/**
 * `GET /api/books/{bookId}/chapters/{chapterId}/system-prompt` — the caller's own
 * system prompt for that chapter. No row yet is a normal `200` with
 * `system_prompt: ""` — not a `404`.
 */
export async function getOwnChapterSystemPrompt(
  bookId: string,
  chapterId: string,
  signal?: AbortSignal,
): Promise<ChapterAuthorPromptResponse> {
  return request<ChapterAuthorPromptResponse>(
    `${BASE}/${bookId}/chapters/${chapterId}/system-prompt`,
    { signal },
  );
}

/**
 * `PUT /api/books/{bookId}/chapters/{chapterId}/system-prompt` — upsert the caller's
 * own system prompt for that chapter. Returns the **stored** prompt, so callers
 * re-seed from the response rather than re-reading. `system_prompt: ""` clears the
 * prompt — there is no DELETE.
 */
export async function updateOwnChapterSystemPrompt(
  bookId: string,
  chapterId: string,
  body: UpdateChapterAuthorPromptRequest,
  signal?: AbortSignal,
): Promise<ChapterAuthorPromptResponse> {
  return request<ChapterAuthorPromptResponse>(
    `${BASE}/${bookId}/chapters/${chapterId}/system-prompt`,
    { method: "PUT", body, signal },
  );
}
