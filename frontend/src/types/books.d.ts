// Wire DTOs for the author-owned book endpoints (`/api/books`) — pure shapes
// matching the backend Pydantic schemas (`backend/app/models/schemas/books.py`)
// 1:1. No methods, no classes, no runtime validation. See docs/plans/009.books.
//
// Ids are **string**: the backend serializes the 64-bit snowflake id as a string
// (frontend.md — "Entity ids are `string`, not `number`"); this applies to `id`
// and `owner_id`. The collaboration-mode / visibility / state unions are the same
// string literals the backend enums serialize to (`app.models.book`).

import type { ISODateString } from "./common";

/** `Book.collaboration_mode` — mirrors backend `CollaborationMode` (`free` | `proposal`). */
export type CollaborationMode = "free" | "proposal";

/** `Book.visibility` — mirrors backend `Visibility` (`private` | `public`). */
export type Visibility = "private" | "public";

/** `Book.state` — mirrors backend `BookState`. */
export type BookState = "active" | "archived" | "quarantined" | "destroyed";

/**
 * `GET /api/books` row / `GET /api/books/shared` row / `POST /api/books` result —
 * mirrors backend `BookResponse`. `id` / `owner_id` are **string** (snowflake
 * serialized as a string). Carries no moderation internals and no
 * `system_prompt` / `active_notes`. Timestamps are ISO strings or null.
 */
export interface BookResponse {
  id: string;
  owner_id: string;
  title: string;
  description: string;
  collaboration_mode: CollaborationMode;
  visibility: Visibility;
  state: BookState;
  created_at: ISODateString | null;
  modified_at: ISODateString | null;
}

/** List envelope for `GET /api/books` and `GET /api/books/shared` — mirrors backend `BookListResponse`. */
export interface BookListResponse {
  items: BookResponse[];
}

/** `POST /api/books` request body — mirrors backend `CreateBookRequest`. */
export interface CreateBookRequest {
  title: string;
  description: string;
  collaboration_mode: CollaborationMode;
  visibility: Visibility;
}

/**
 * `BookMember.role` — mirrors backend `MemberRole`. Single value today: a member
 * row exists only for co-authors (the owner has no row, readers have no row).
 */
export type MemberRole = "co_author";

/**
 * One co-author in a book's member list — mirrors backend `BookMemberResponse`.
 * `user_id` is **string** (snowflake serialized as a string); `role` is the
 * single-value `MemberRole` marker; `created_at` is the membership timestamp.
 */
export interface BookMemberResponse {
  user_id: string;
  role: MemberRole;
  created_at: ISODateString | null;
}

/**
 * `GET /api/books/{id}` result — mirrors backend `BookDetailResponse`. Extends the
 * `BookResponse` summary (all its fields) and adds the co-author `members` list.
 * Members-only: readers never receive it. Deliberately omits `system_prompt` /
 * `active_notes` (not rendered by the settings page).
 */
export interface BookDetailResponse extends BookResponse {
  members: BookMemberResponse[];
}

/**
 * `POST /api/books/{id}/transfer` request body — mirrors backend
 * `TransferOwnershipRequest`. `target_user_id` is the string id of the co-author
 * to become the new owner (server refuses a non-co-author).
 */
export interface TransferOwnershipRequest {
  target_user_id: string;
}

/**
 * `POST /api/books/{id}/members` request body — mirrors backend `AddMemberRequest`.
 * `target_user_id` is the string id of the author-account to grant co-author access.
 */
export interface AddMemberRequest {
  target_user_id: string;
}

/**
 * `PATCH /api/books/{id}/visibility` request body — mirrors backend
 * `SetVisibilityRequest`.
 */
export interface SetVisibilityRequest {
  visibility: Visibility;
}
