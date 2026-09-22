// Wire DTOs for the reader surface — pure shapes matching the backend Pydantic
// schemas (`backend/app/models/schemas/reader.py`) 1:1. No methods, no classes,
// no runtime validation. See docs/plans/022.reader-mode.
//
// This is everything ACT-006 (a logged-in non-member) can receive. UC-029 is an
// exclusion list, so these types are deliberately NARROWER than their authoring
// counterparts in `books.d.ts` / `chapters.d.ts` and must never be widened to
// match them: `ReaderChapterRef` carries no `sketch`, `summary`, `state`,
// `ordinal` or `version`; `ReaderBookResponse` carries no id, owner, visibility,
// state or description; `PublicBookRef` carries no owner or timestamps.
//
// Ids are **string** (the backend serializes the 64-bit snowflake as a string —
// frontend.md, "Entity ids are `string`, not `number`").

/** One table-of-contents entry — mirrors backend `ReaderChapterRef`. */
export interface ReaderChapterRef {
  id: string;
  title: string;
}

/**
 * `GET /api/books/{bookId}/read` result — mirrors backend `ReaderBookResponse`.
 *
 * `chapters` holds only the reader-visible chapters, already in reading order:
 * the backend sorts by ordinal and does not put the ordinal on the wire, so the
 * array order **is** the order and must not be re-sorted client-side.
 */
export interface ReaderBookResponse {
  title: string;
  chapters: ReaderChapterRef[];
}

/**
 * `GET /api/books/{bookId}/read/chapters/{chapterId}` result — mirrors backend
 * `ReaderChapterResponse`. `text` is the chapter's saved body (markdown).
 */
export interface ReaderChapterResponse {
  id: string;
  title: string;
  text: string;
}

/** One row of the public-book discovery list — mirrors backend `PublicBookRef`. */
export interface PublicBookRef {
  id: string;
  title: string;
  description: string;
}

/** List envelope for `GET /api/books/public` — mirrors backend `PublicBookListResponse`. */
export interface PublicBookListResponse {
  items: PublicBookRef[];
}
