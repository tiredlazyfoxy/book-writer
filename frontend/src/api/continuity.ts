import { request } from "./client";
import type {
  BookContinuityResponse,
  BookStateNotesResponse,
  ChapterNoteChangesetResponse,
  UpdateBookStateNotesRequest,
} from "../types/continuity";

// Continuity resource module (feature 016) — the book's live state notes, one
// chapter's note changeset and the per-chapter continuity roll-up. Mirrors
// `api/chapters.ts` exactly: a module-level `/api/books` base, the STRING snowflake
// ids interpolated straight into the path, `signal?` as the trailing argument on
// every function, and all JSON HTTP through `client.request<T>` (Bearer injection,
// `ApiError` normalization, signal pass-through, `204` → `undefined`).
//
//   GET /api/books/{bookId}/state-notes                        -> BookStateNotesResponse
//   PUT /api/books/{bookId}/state-notes                        -> BookStateNotesResponse
//   GET /api/books/{bookId}/continuity                          -> BookContinuityResponse
//   GET /api/books/{bookId}/chapters/{chapterId}/notes          -> ChapterNoteChangesetResponse
//
// Nothing is unwrapped or reshaped here: `getBookContinuity` resolves to the whole
// `{ items }` envelope, exactly as `listChapters` resolves to its whole envelope.
//
// NO error handling, NO retry and NO refusal parsing live here: `request<T>` already
// normalizes a non-2xx into an `ApiError` carrying `status` (the pages branch on
// `403` vs `404`) and the server's plain-string reason text.
//
// Namespace-imported by callers (`import * as continuityApi from "../../api/continuity"`).
//
const BASE = "/api/books";

/**
 * `GET /api/books/{bookId}/state-notes` — the book's live state notes (UC-049 /
 * US-052.AC-1).
 *
 * Members-only server-side: a reader is refused `403`. An empty `active_notes` is a
 * normal `200`, never a `404`.
 */
export async function getStateNotes(
  bookId: string,
  signal?: AbortSignal,
): Promise<BookStateNotesResponse> {
  return request<BookStateNotesResponse>(`${BASE}/${bookId}/state-notes`, { signal });
}

/**
 * `PUT /api/books/{bookId}/state-notes` — replace the whole note set (UC-050's
 * direct-edit path / US-053.AC-1).
 *
 * Carries no version token — last write wins, so there is no `409` branch. An
 * archived book and a co-author in a proposal-mode book both come back `403` with the
 * server's own message. Returns the STORED notes, so callers re-seed from the
 * response rather than from their draft.
 */
export async function updateStateNotes(
  bookId: string,
  body: UpdateBookStateNotesRequest,
  signal?: AbortSignal,
): Promise<BookStateNotesResponse> {
  return request<BookStateNotesResponse>(`${BASE}/${bookId}/state-notes`, {
    method: "PUT",
    body,
    signal,
  });
}

/**
 * `GET /api/books/{bookId}/continuity` — one entry per chapter, ordinal ascending,
 * each with its summary, its changeset (or `null`) and its OPEN warnings (UC-089 /
 * UC-091; US-104.AC-1, US-106.AC-2 / AC-3).
 *
 * Resolves to the WHOLE envelope (`{ items }`), not a bare array — the
 * `listChapters` precedent.
 */
export async function getBookContinuity(
  bookId: string,
  signal?: AbortSignal,
): Promise<BookContinuityResponse> {
  return request<BookContinuityResponse>(`${BASE}/${bookId}/continuity`, { signal });
}

/**
 * `GET /api/books/{bookId}/chapters/{chapterId}/notes` — one chapter's note changeset
 * (UC-051 / US-054.AC-1).
 *
 * A chapter with no changeset row yet is a normal `200` carrying `""` in all three
 * fields with `status: null` — not a `404`, exactly as `getOwnChapterSystemPrompt`
 * answers for a prompt nobody has written.
 */
export async function getChapterChangeset(
  bookId: string,
  chapterId: string,
  signal?: AbortSignal,
): Promise<ChapterNoteChangesetResponse> {
  return request<ChapterNoteChangesetResponse>(
    `${BASE}/${bookId}/chapters/${chapterId}/notes`,
    { signal },
  );
}
