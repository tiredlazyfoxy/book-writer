// Wire DTOs for the continuity endpoints — the book's live state notes
// (`/api/books/{book_id}/state-notes`), one chapter's note changeset
// (`…/chapters/{chapter_id}/notes`) and the per-chapter roll-up
// (`/api/books/{book_id}/continuity`) — pure shapes matching the backend Pydantic
// schemas (`backend/app/models/schemas/continuity.py`, feature 016) 1:1. No methods,
// no classes, no runtime validation (frontend.md — hand-written `.d.ts`, ids `string`,
// no `any`).
//
// Ids are **string**; field names are wire-exact `snake_case`.
//
// Skeleton (016): declarations, complete as written — there is nothing to leave
// unimplemented in a `.d.ts`.

import type { ISODateString } from "./common";
import type { FlagResponse } from "./flags";

/**
 * The freshness of a continuity artifact — mirrors the backend's `SummaryStatus`
 * (a chapter's summary) **and** `NoteStatus` (a chapter's changeset), which are two
 * enums with one identical three-value vocabulary.
 *
 * ONE union for both, deliberately: the backend keeps two enums because each mirrors
 * its own column, but on the wire they are the same three strings meaning the same
 * three things, and two identical unions here would make every label map and every
 * badge choose between them for no reason.
 *
 * - `"draft"` — written during a close run, not yet accepted;
 * - `"approved"` — accepted when the chapter closed cleanly (both artifacts flip to
 *   this in the same step the chapter closes — there is no approval gate, D3);
 * - `"stale"` — the chapter was reopened after it closed, so the artifact describes a
 *   chapter that has moved on (US-055.AC-1).
 */
export type ContinuityStatus = "draft" | "approved" | "stale";

/**
 * `GET` / `PUT /api/books/{book_id}/state-notes` result — mirrors backend
 * `BookStateNotesResponse`.
 *
 * `active_notes` is never null: `""` means "nothing has been recorded yet", a normal
 * starting state rather than an absence. `modified_at` is the book row's own
 * timestamp.
 */
export interface BookStateNotesResponse {
  book_id: string;
  active_notes: string;
  modified_at: ISODateString | null;
}

/**
 * `PUT /api/books/{book_id}/state-notes` body — mirrors backend
 * `UpdateBookStateNotesRequest`.
 *
 * Carries the **whole** note set: the notes are free text with no per-note
 * addressing, so there is nothing for a partial update to address. `""` is a legal
 * value (an author clearing the set) and there is **no version token** — this path is
 * last-write-wins, so no `409` staleness branch exists.
 */
export interface UpdateBookStateNotesRequest {
  active_notes: string;
}

/**
 * `GET /api/books/{book_id}/chapters/{chapter_id}/notes` result, and the `changeset`
 * member of {@link ChapterContinuityResponse} — mirrors backend
 * `ChapterNoteChangesetResponse`.
 *
 * THREE SEPARATE FREE-TEXT DELTAS and no merged view: there is no correct mechanical
 * merge of three free-text deltas (backend decision D7), so the three are rendered as
 * they are stored.
 *
 * A chapter with **no changeset row yet** is a normal `200` carrying `""` in all
 * three fields with `status: null` — not a `404` (the `ChapterAuthorPromptResponse`
 * "no row yet" convention). `status` is therefore nullable rather than defaulted.
 */
export interface ChapterNoteChangesetResponse {
  chapter_id: string;
  added: string;
  modified: string;
  deleted: string;
  status: ContinuityStatus | null;
  created_at: ISODateString | null;
  modified_at: ISODateString | null;
}

/**
 * One chapter's continuity roll-up — an entry of {@link BookContinuityResponse};
 * mirrors backend `ChapterContinuityResponse`.
 *
 * It repeats `title` and `ordinal` so the per-chapter continuity view renders from
 * ONE response instead of joining this against the chapter list client-side.
 *
 * - `summary` / `summary_status` — `null` on a chapter that has never been closed;
 * - `changeset` — `null` when the chapter has no row. **Nullable here, unlike the
 *   dedicated endpoint's default-empty body**: in a list, "no changeset" is a fact
 *   worth carrying as `null`;
 * - `warnings` — the chapter's **open** flags only, of BOTH origins. Resolved flags
 *   are the flag-list endpoint's.
 */
export interface ChapterContinuityResponse {
  chapter_id: string;
  title: string;
  ordinal: number;
  summary: string | null;
  summary_status: ContinuityStatus | null;
  changeset: ChapterNoteChangesetResponse | null;
  warnings: FlagResponse[];
}

/**
 * `GET /api/books/{book_id}/continuity` result — mirrors backend
 * `BookContinuityResponse`. One entry per chapter, **ordinal ascending**.
 */
export interface BookContinuityResponse {
  items: ChapterContinuityResponse[];
}
