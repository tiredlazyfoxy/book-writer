import { request } from "./client";
import type {
  PublicBookListResponse,
  ReaderBookResponse,
  ReaderChapterResponse,
} from "../types/reader";

// Reader resource module (the `/api/books` reader surface — feature 022). All
// JSON HTTP goes through `client.request` (which injects Bearer when a token
// exists). Namespace-imported by callers
// (`import * as readerApi from "../../api/reader"`); `signal?` is always the
// trailing arg, matching `api/books.ts` / `api/chapters.ts`.
//
// Deliberately three functions wide and closed: no codex, state-notes, flags,
// book-state, settings or chat call may ever be added here (UC-029's exclusion
// list is what this module exists to make legible).

const BASE = "/api/books";

/**
 * `GET /api/books/{bookId}/read` — the reader-safe table of contents.
 *
 * Refusals surface as `ApiError` (404 for a book the caller cannot read, 401
 * without a token); this module never maps them — the page's load function does
 * (decision D9).
 */
export async function getReaderBook(
  bookId: string,
  signal?: AbortSignal,
): Promise<ReaderBookResponse> {
  return request<ReaderBookResponse>(`${BASE}/${bookId}/read`, { signal });
}

/**
 * `GET /api/books/{bookId}/read/chapters/{chapterId}` — one chapter's saved text.
 *
 * Every refusal is an indistinguishable 404 (decision D5).
 */
export async function getReaderChapter(
  bookId: string,
  chapterId: string,
  signal?: AbortSignal,
): Promise<ReaderChapterResponse> {
  return request<ReaderChapterResponse>(
    `${BASE}/${bookId}/read/chapters/${chapterId}`,
    { signal },
  );
}

/**
 * `GET /api/books/public` — public books the caller can discover but is not part
 * of (feeds the bookshelf's third section).
 *
 * Lives here rather than in `api/books.ts` because the payload is a reader DTO
 * (decision D15's client-side counterpart).
 */
export async function listPublicBooks(
  signal?: AbortSignal,
): Promise<PublicBookListResponse> {
  return request<PublicBookListResponse>(`${BASE}/public`, { signal });
}
