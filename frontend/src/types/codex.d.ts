// Wire DTOs for the book-nested codex endpoints (`/api/books/{book_id}/codex`) —
// pure shapes matching the backend Pydantic schemas
// (`backend/app/models/schemas/codex.py`, feature 013 step 002) 1:1. No methods,
// no classes, no runtime validation (frontend.md — hand-written `.d.ts`, ids
// `string`, no `any`).
//
// Ids are **string**: the backend serializes the 64-bit snowflake id as a string
// (`id` / `book_id` / `author_id` / `modified_by`). Field names are wire-exact
// `snake_case`. The list envelope (`CodexEntryListResponse` = `{ items: [...] }`)
// is NOT modelled here — it is unwrapped in `api/codex.ts`.
//
// Skeleton (013/011): declarations, complete as written — there is nothing to
// leave unimplemented in a `.d.ts`.

import type { ISODateString } from "./common";

/**
 * The codex taxonomy — mirrors backend `CodexKind` (character / location / fact:
 * three kinds, one table). Written as the backend's enum *values*, per the
 * `types/` union convention.
 */
export type CodexKind = "character" | "location" | "fact";

/**
 * `POST /api/books/{book_id}/codex` body — mirrors backend
 * `CreateCodexEntryRequest`. `kind` is required and is set only at creation (an
 * entry's kind is not updatable). `name` is optional here: the kind/name rule
 * (character / location require a non-blank name, a fact refuses one) is a
 * server-side rule and is deliberately not modelled on the client.
 */
export interface CreateCodexEntryRequest {
  kind: CodexKind;
  name?: string | null;
  body: string;
}

/**
 * `PUT /api/books/{book_id}/codex/{entry_id}` body — mirrors backend
 * `UpdateCodexEntryRequest`. `kind` is absent by design (not updatable).
 * `expected_modified_at` is the optimistic-concurrency token and is **required
 * but nullable**: it carries the `modified_at` the client loaded the entry at
 * (`null` for an entry never edited since creation), and a disagreeing value is
 * refused with 409. An omitted field must not silently pass the staleness check,
 * so it is not marked optional.
 */
export interface UpdateCodexEntryRequest {
  name?: string | null;
  body: string;
  expected_modified_at: ISODateString | null;
}

/**
 * A single codex entry as surfaced to a member (create / get / list / update
 * results) — mirrors backend `CodexEntryResponse` field-for-field. `name` is
 * `null` for a fact; `author_id` is the original creator and never changes;
 * `modified_by` is the author of the most recent edit (`null` until the first).
 */
export interface CodexEntryResponse {
  id: string;
  book_id: string;
  kind: CodexKind;
  name: string | null;
  body: string;
  archived: boolean;
  author_id: string;
  modified_by: string | null;
  created_at: ISODateString | null;
  modified_at: ISODateString | null;
}
