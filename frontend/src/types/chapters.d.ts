// Wire DTOs for the book-nested chapter endpoints
// (`/api/books/{book_id}/chapters`, plus the per-author chapter system prompt at
// `/api/books/{book_id}/chapters/{chapter_id}/system-prompt`) — pure shapes matching
// the backend Pydantic schemas (`backend/app/models/schemas/chapters.py` and
// `backend/app/models/schemas/chapter_author_prompts.py`, feature 014 steps 002 and
// 004) 1:1. No methods, no classes, no runtime validation (frontend.md —
// hand-written `.d.ts`, ids `string`, no `any`).
//
// Ids are **string**: the backend serializes the 64-bit snowflake id as a string
// (`id` / `book_id` / `chapter_id`, and every element of `chapter_ids`). Field names
// are wire-exact `snake_case`.
//
// Unlike `types/codex.d.ts`, the list envelope IS modelled here and is NOT unwrapped
// in `api/chapters.ts`: it carries `can_reorder`, which steps 006 and 007 consume
// (`docs/plans/014.chapter-skeleton/context.md` — cross-cutting frontend constraints).
//
// Skeleton (014/005): declarations, complete as written — there is nothing to leave
// unimplemented in a `.d.ts`.

import type { ISODateString } from "./common";
import type { ContinuityStatus } from "./continuity";

/**
 * A chapter's lifecycle state on the wire — mirrors backend `ChapterState`
 * (`domain-chapter.md`: at most one `open` chapter per book).
 *
 * NAMED `ChapterLifecycleState`, NOT `ChapterState`, deliberately. `src/work/subject.ts`
 * already declares an identically-valued `ChapterState` for the content pane's subject
 * model. The two belong to different layers — this one is the wire's vocabulary at
 * shared `src/` root, that one is the working page's pane model and is entry-local to
 * `work/` — and the pane model is allowed to diverge from the wire later (016 / 018).
 * Two same-named types meaning two different things would make every import site
 * ambiguous, so the wire type carries the distinguishing name. `work/subject.ts` is
 * neither edited nor imported from here.
 */
export type ChapterLifecycleState = "planned" | "open" | "closing" | "closed";

/**
 * One chapter as surfaced to a book member (list / get / create / sketch-update
 * results) — mirrors backend `ChapterResponse` field-for-field.
 *
 * Deliberately carries **no `text`**: the body belongs to
 * `015.chapter-writing-free-mode` and is its own sub-resource (D13). `version` tracks
 * the *body* and is never bumped by a sketch edit (decision D6). `ordinal` is
 * server-assigned and 1-based.
 *
 * **`016.chapter-close-continuity` adds `summary` and `summary_status`** — the two
 * fields this declaration previously reserved for it. They ride on the chapter DTO
 * rather than on a sub-resource of their own: a summary is a short field the chapter
 * view and the continuity roll-up both want, so it costs nothing on a list render.
 * Both are `null` on a chapter that has never been closed.
 */
export interface ChapterResponse {
  id: string;
  book_id: string;
  ordinal: number;
  title: string;
  state: ChapterLifecycleState;
  sketch: string;
  version: number;
  summary: string | null;
  summary_status: ContinuityStatus | null;
  created_at: ISODateString | null;
  modified_at: ISODateString | null;
}

/**
 * `GET /api/books/{book_id}/chapters` and `PUT /api/books/{book_id}/chapters/order`
 * result — mirrors backend `ChapterListResponse`. `chapters` is ordered by `ordinal`
 * ascending.
 *
 * `can_reorder` is a caller-relative **affordance hint**, true only for the book's
 * owner. It is never the enforcement — the server refuses a co-author's `PUT` with
 * `403` regardless of what the hint said. This envelope is what `api/chapters.ts`
 * resolves to; it is not unwrapped to a bare array.
 */
export interface ChapterListResponse {
  chapters: ChapterResponse[];
  can_reorder: boolean;
}

/**
 * `POST /api/books/{book_id}/chapters` body — mirrors backend `CreateChapterRequest`.
 * `title` must not be blank (server-side rule: a blank or whitespace-only title is a
 * `422`); `sketch` is required but `""` is legitimate. There is no `ordinal` — a new
 * chapter is appended, with the server assigning the next ordinal (UC-031).
 */
export interface CreateChapterRequest {
  title: string;
  sketch: string;
}

/**
 * `PATCH /api/books/{book_id}/chapters/{chapter_id}` body — mirrors backend
 * `UpdateChapterSketchRequest`. The sketch is the only editable field on this path,
 * and there is **no version token**: sketch edits are last-write-wins (decision D6),
 * so no `409` staleness path exists here (contrast `UpdateCodexEntryRequest`).
 */
export interface UpdateChapterSketchRequest {
  sketch: string;
}

/**
 * `PUT /api/books/{book_id}/chapters/order` body — mirrors backend
 * `ReorderChaptersRequest`. `chapter_ids` is the **full** ordered chapter-id list for
 * the book; the server rewrites ordinals `1..N` in one transaction and refuses (with
 * `400`) any list that is not exactly the book's current chapter set — missing, extra,
 * duplicated or foreign ids (decision D3). There is no per-chapter move endpoint.
 */
export interface ReorderChaptersRequest {
  chapter_ids: string[];
}

/**
 * `GET` / `PUT /api/books/{book_id}/chapters/{chapter_id}/system-prompt` result —
 * mirrors backend `ChapterAuthorPromptResponse`. The chapter-level counterpart of
 * `BookAuthorPromptResponse`, one level down: `chapter_id` in place of `book_id`.
 *
 * Always **the caller's own** prompt for that chapter; no other author's is
 * addressable, which is why the wire carries **no `user_id`** field. `system_prompt`
 * is never null — `""` means "this author has written no prompt", a normal starting
 * state rather than an error. `modified_at` is `null` when no row exists yet, so
 * "never written" and "deliberately cleared to empty" are distinguishable only by that
 * timestamp. A missing row is a `200`, never a `404`.
 */
export interface ChapterAuthorPromptResponse {
  chapter_id: string;
  system_prompt: string;
  modified_at: ISODateString | null;
}

/**
 * `PUT /api/books/{book_id}/chapters/{chapter_id}/system-prompt` body — mirrors
 * backend `UpdateChapterAuthorPromptRequest`. Upsert: the row is created when absent
 * and updated when present. `""` is valid input and means "no prompt" — there is no
 * DELETE verb, because an empty string already expresses that state.
 */
export interface UpdateChapterAuthorPromptRequest {
  system_prompt: string;
}

// ---------------------------------------------------------------------------
// The chapter BODY sub-resource (`…/chapters/{chapter_id}/text`) — feature 015
// step 004, mirroring backend `ChapterTextResponse` / `UpdateChapterTextRequest`
// (`backend/app/models/schemas/chapters.py`, 015 steps 001 + 003) 1:1.
//
// A SUB-RESOURCE, not a widening of `ChapterResponse` (015 decision D13): 014's
// response is served by a single mapper feeding both the list and the item, so a
// `text` field added for the item would drag every chapter body onto the wire for
// every list render. The seven DTOs above are untouched by this step.
//
// `state` REUSES `ChapterLifecycleState` declared above — no second union, and
// `src/work/subject.ts` is still neither imported nor edited from here.
//
// Skeleton (015/004): declarations, complete as written — there is nothing to
// leave unimplemented in a `.d.ts`.
// ---------------------------------------------------------------------------

/**
 * `GET` / `PUT /api/books/{book_id}/chapters/{chapter_id}/text` result — mirrors
 * backend `ChapterTextResponse` field-for-field. The book id is **not** repeated
 * here; it is already in the path.
 *
 * `state` rides along with the body so the page's body region can gate itself
 * without depending on which of its loads resolved first, and so the version and
 * the state that qualify a save always arrive together.
 *
 * `version` is the body's concurrency token and is a **`number`**, not a string:
 * the string-id rule exists because snowflakes exceed JavaScript's safe-integer
 * range, and an ordinary incremented counter does not. `restoreBuffer.ts`'s
 * `BufferBaseVersion` already accepts `number` for exactly this field.
 *
 * Carries **no `can_write`** affordance hint (decision D14) — a body
 * representation is a resource, not a caller-relative list envelope. `text` is
 * Markdown (D2) and `""` is a legitimate value.
 */
export interface ChapterTextResponse {
  chapter_id: string;
  state: ChapterLifecycleState;
  text: string;
  version: number;
  modified_at: ISODateString | null;
}

/**
 * `PUT /api/books/{book_id}/chapters/{chapter_id}/text` body — mirrors backend
 * `UpdateChapterTextRequest`. The **whole** body plus the version it was composed
 * against (decision D1: there is exactly one body write endpoint and it replaces
 * the whole text; append-vs-replace is a draft-side editing operation).
 *
 * `text` has no constraint — `""` is legitimate (the author clearing the
 * chapter). `expected_version` is required and there is **no force flag**: a value
 * that is not the chapter's current version is refused `409`, which is what makes
 * the concurrency contract a contract.
 */
export interface UpdateChapterTextRequest {
  text: string;
  expected_version: number;
}
