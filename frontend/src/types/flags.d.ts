// Wire DTOs for the chapter-nested flag endpoints
// (`/api/books/{book_id}/chapters/{chapter_id}/flags`) — pure shapes matching the
// backend Pydantic schemas (`backend/app/models/schemas/flags.py`, feature 016) 1:1.
// No methods, no classes, no runtime validation (frontend.md — hand-written `.d.ts`,
// ids `string`, no `any`).
//
// Ids are **string**: the backend serializes every 64-bit snowflake as a string
// (`id`, `chapter_id`, `created_by`, `resolved_by`). Field names are wire-exact
// `snake_case`.
//
// THE WIRE SAYS `flag`; THE UI SAYS "warning". The backend entity is `Flag` and the
// endpoints are `…/flags`, so these declarations keep that name — the author-facing
// word is a rendering decision that belongs in the components, not in the wire type.
//
// There is deliberately **no `book_id`**: the backend row has none either (the book is
// resolved through the chapter), and it is already in the request path.
//
// Skeleton (016): declarations, complete as written — there is nothing to leave
// unimplemented in a `.d.ts`.

import type { ISODateString } from "./common";

/**
 * Where a flag came from — mirrors backend `FlagOrigin`.
 *
 * `"check"` is one the close run's consistency check raised (and only that run's
 * check flags block a close — the previous run's are deleted when the next close
 * starts, decision D6); `"person"` is one a member raised (UC-067), which is advisory
 * and never blocks.
 */
export type FlagOrigin = "check" | "person";

/** A flag's lifecycle — mirrors backend `FlagStatus`. `open` until someone resolves it. */
export type FlagStatus = "open" | "resolved";

/**
 * One flag on one chapter (list / raise / resolve results, and each entry of a
 * chapter's `warnings` in `ChapterContinuityResponse`) — mirrors backend
 * `FlagResponse` field-for-field.
 *
 * `resolved_by` / `resolved_at` are `null` until the flag is resolved (UC-068 /
 * US-077.AC-1), so "has this been dealt with" is answerable from `status` and the
 * attribution from the other two.
 */
export interface FlagResponse {
  id: string;
  chapter_id: string;
  origin: FlagOrigin;
  comment: string;
  status: FlagStatus;
  created_by: string;
  created_at: ISODateString | null;
  resolved_by: string | null;
  resolved_at: ISODateString | null;
}

/**
 * `GET /api/books/{book_id}/chapters/{chapter_id}/flags` result — mirrors backend
 * `FlagListResponse`. Carries **every** flag of the chapter, open and resolved,
 * newest first.
 *
 * No caller-relative affordance hint rides here: raising and resolving are
 * capability-gated server-side, and a client control is never the enforcement.
 */
export interface FlagListResponse {
  items: FlagResponse[];
}

/**
 * `POST /api/books/{book_id}/chapters/{chapter_id}/flags` body — mirrors backend
 * `RaiseFlagRequest`.
 *
 * `comment` must not be blank (server-side rule: a blank or whitespace-only comment
 * is a `422`, and the stored value is stripped). There is deliberately **no `origin`
 * field**: a flag raised this way is always `origin: "person"` — the `"check"` origin
 * belongs to the close run's own tool and is not client-settable.
 */
export interface RaiseFlagRequest {
  comment: string;
}
