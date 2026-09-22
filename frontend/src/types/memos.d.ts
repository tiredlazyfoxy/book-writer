// Wire DTOs for the book-nested memo endpoints (`/api/books/{book_id}/memos`) —
// pure shapes matching the backend Pydantic schemas
// (`backend/app/models/schemas/memos.py`, feature 026 steps 002 / 004) 1:1. No
// methods, no classes, no runtime validation (frontend.md — hand-written `.d.ts`,
// ids `string`, no `any`).
//
// Ids are **string**: the backend serializes the 64-bit snowflake id as a string
// (`id` / `book_id` / every id in `memo_ids`). Field names are wire-exact
// `snake_case`. The list envelope (backend `MemoListResponse` = `{ items: [...] }`)
// is NOT modelled here — it is handled in `api/memos.ts`, the convention every
// other resource module follows.
//
// Skeleton (026/009): declarations, complete as written — there is nothing to
// leave unimplemented in a `.d.ts`.

import type { ISODateString } from "./common";

/**
 * `POST /api/books/{book_id}/memos` body — mirrors backend `CreateMemoRequest`.
 * `body` carries no constraint of any kind: `""` is legitimate input (UC-103
 * creates an EMPTY memo and focuses it), never a 422.
 */
export interface CreateMemoRequest {
  body: string;
}

/**
 * `PUT /api/books/{book_id}/memos/{memo_id}` body — mirrors backend
 * `UpdateMemoRequest`. `body` and nothing else: there is no
 * `expected_modified_at` (a memo has exactly one writer, so no optimistic
 * concurrency and no `409` — `026/context.md` decision 5) and no `active` /
 * `archived` flag (each axis has its own verb pair, so the focus-loss `PUT`
 * cannot write state it did not mean to).
 */
export interface UpdateMemoRequest {
  body: string;
}

/**
 * `PUT /api/books/{book_id}/memos/order` body — mirrors backend
 * `ReorderMemosRequest`. The **full** ordered id list of the caller's
 * non-archived memos; the server rewrites ordinals `1..N` over it and refuses a
 * list that is not exactly that set with `400`. There is no partial-move shape:
 * positions are the server's to write.
 */
export interface ReorderMemosRequest {
  memo_ids: string[];
}

/**
 * One of the caller's own memos — mirrors backend `MemoResponse` field for field
 * (create / list / update / reorder / the four state verbs all return this).
 *
 * **No `user_id`**: the subject is always the caller, and echoing an id would
 * invite the reading that another author's memo is addressable here
 * (`026/context.md` → "The wire contract").
 *
 * `active` and `archived` are two INDEPENDENT axes, not one state enum: a memo
 * reaches the assistant iff `archived === false && active === true`, and the
 * pair is what remembers whether a restored memo was switched on or off before
 * it was archived. `ordinal` is scoped per (book, author) and may carry gaps —
 * archiving never renumbers.
 */
export interface MemoResponse {
  id: string;
  book_id: string;
  body: string;
  ordinal: number;
  active: boolean;
  archived: boolean;
  created_at: ISODateString | null;
  modified_at: ISODateString | null;
}
