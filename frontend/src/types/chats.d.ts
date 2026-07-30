// Wire DTOs for the author-owned chat endpoints (`/api/books/{book_id}/chats`) —
// pure shapes matching the backend Pydantic schemas
// (`backend/app/models/schemas/chats.py`, feature 011 step 001) 1:1. No methods,
// no classes, no runtime validation (frontend.md — hand-written `.d.ts`, ids
// `string`, no `any`).
//
// Ids are **string**: the backend serializes the 64-bit snowflake id as a string
// (`id` / `book_id` / `author_id` / `chat_id` / `server_id`). Field names are
// wire-exact `snake_case`. List envelopes (`{ items: [...] }`) are NOT modelled
// here — they are unwrapped in `api/chats.ts`.

import type { ISODateString } from "./common";
import type { CodexKind } from "./codex";

/**
 * The typed sampling set stored per chat — mirrors backend `ChatSamplingParams`.
 * Only `temperature` is surfaced in the UI (feature decision 4); every other
 * param is carried through unchanged on an update. `max_tokens` / `seed` are
 * optional-and-unset (`null`).
 */
export interface ChatSamplingParams {
  temperature: number;
  top_p: number;
  top_k: number;
  repeat_penalty: number;
  min_p: number;
  max_tokens: number | null;
  seed: number | null;
  presence_penalty: number;
  frequency_penalty: number;
  enable_thinking: boolean;
}

/**
 * `POST /api/books/{book_id}/chats` body — mirrors backend `CreateChatRequest`.
 * All fields optional; the model pair moves together (both-null or both-set,
 * validated server-side).
 */
export interface CreateChatRequest {
  title?: string | null;
  llm_server_id?: string | null;
  model_name?: string | null;
  sampling?: ChatSamplingParams | null;
}

/**
 * `PATCH /api/books/{book_id}/chats/{chat_id}` body — mirrors backend
 * `UpdateChatRequest`. All fields optional so one body doubles as
 * archive/restore (`archived`) and settings-edit (model pair / `sampling`).
 */
export interface UpdateChatRequest {
  title?: string | null;
  archived?: boolean | null;
  llm_server_id?: string | null;
  model_name?: string | null;
  sampling?: ChatSamplingParams | null;
}

/** A single chat as surfaced to its author — mirrors backend `ChatResponse`. */
export interface ChatResponse {
  id: string;
  book_id: string;
  author_id: string;
  title: string;
  llm_server_id: string | null;
  model_name: string | null;
  sampling: ChatSamplingParams;
  archived: boolean;
  created_at: ISODateString | null;
  modified_at: ISODateString | null;
}

/**
 * A single message within a chat — mirrors backend `ChatMessageResponse`.
 * `reasoning` is the assistant's thinking (`null` for user messages and
 * assistants that produced none); step 005 renders it.
 */
export interface ChatMessageResponse {
  id: string;
  chat_id: string;
  role: string;
  content: string;
  reasoning: string | null;
  position: number;
  created_at: ISODateString | null;
}

/**
 * `GET /api/books/{book_id}/chats/{chat_id}` result — mirrors backend
 * `ChatDetailResponse`: the chat plus its position-ordered messages.
 */
export interface ChatDetailResponse {
  chat: ChatResponse;
  messages: ChatMessageResponse[];
}

/**
 * One selectable `(server, model)` option for the author's model picker —
 * mirrors backend `ModelOptionResponse`. Carries the server id + display name
 * and one model enabled on it; never an api key.
 */
export interface ModelOptionResponse {
  server_id: string;
  server_name: string;
  model_name: string;
}

/**
 * Which content-pane subject a turn (or a `canvas` frame) is about — a wire-exact
 * mirror of the backend's `SubjectKind` literal union
 * (`backend/app/models/schemas/chats.py`, 013 step 007/010). A literal union, not
 * a free string: an unknown kind is refused at the schema boundary.
 *
 * Structurally identical to `work/subject.ts:SubjectKind` (same ten members, same
 * order) but deliberately declared here: `src/types/` models the WIRE and must
 * not import from an entry's domain modules. TypeScript's structural typing makes
 * the two interchangeable, and a member added to one and not the other stops
 * compiling at the mapping site.
 */
export type SubjectKind =
  | "book-state"
  | "chapters"
  | "chapter"
  | "characters"
  | "locations"
  | "facts"
  | "codex-entry"
  | "variants"
  | "chapter-variants"
  | "chats";

/**
 * The three subject fields a turn request may carry, supplied together by the
 * caller of `streamChatTurn`.
 *
 * - `subject_kind` — the kind of subject the author had open.
 * - `subject_id` — its entity id as a string, or `null` for a list / book-state
 *   subject AND for UC-076's blank codex entry, which has no row yet.
 * - `codex_kind` — the kind of a blank codex entry. Only consulted by the backend
 *   when the subject is a codex entry with no `subject_id`; for an existing entry
 *   the stored row's kind wins and this is ignored. `null` for every non-codex
 *   subject.
 */
export interface TurnSubject {
  subject_kind: SubjectKind;
  subject_id: string | null;
  codex_kind: CodexKind | null;
}

/**
 * `POST /api/books/{book_id}/chats/{chat_id}/turn` body — mirrors backend
 * `TurnRequest`. `prompt` is the author's text for a fresh turn, or `null` for a
 * retry (the user message is already persisted server-side).
 *
 * The three subject fields are OPTIONAL and are omitted entirely when no content
 * subject is registered, so `011.chat-panel`'s shipped body (`{ prompt }`) is
 * still a complete request.
 *
 * `selection_text` (`015` step 012) mirrors the backend field `015` step 009 added
 * (`models/schemas/chats.py` → `TurnRequest.selection_text: str | None = None`) and is
 * a **FIFTH FLAT FIELD**, beside `subject_kind` / `subject_id` / `codex_kind` and not
 * inside any object: this request has no subject object on either side of the wire, and
 * the frontend-only {@link TurnSubject} helper gains NOTHING — a selection is not part
 * of the subject's identity (the same chapter can be in view with any selection or
 * none), and putting it there would give the client a shape the wire does not have
 * (`015/context.md` → D5, `012.context.md`).
 *
 * It is **text and only text** — no offsets, no line numbers, no range, no anchor id.
 * OPTIONAL and OMITTED ENTIRELY when nothing is selected, so a turn sent with no
 * selection posts a body with no `selection_text` key at all.
 */
export interface TurnRequest {
  prompt: string | null;
  subject_kind?: SubjectKind | null;
  subject_id?: string | null;
  codex_kind?: CodexKind | null;
  selection_text?: string | null;
}

/**
 * Which part of a subject an assistant draft targets — wire-exact with the
 * backend's `CanvasField`, and identical to
 * `work/pages/codexEntryPageState.ts:CodexDraftField`, so a frame's `field` binds
 * to the page's apply-draft callback with no translation.
 */
export type CanvasField = "name" | "body";

/**
 * WHICH OPERATION a `canvas` frame performs on its `field` — wire-exact with the
 * backend's `CanvasOp` (`models/schemas/chats.py`, declared immediately below
 * `CanvasField` there too; feature `015` step 009), same three values in the same
 * order:
 *
 * - `"replace"` — the text IS the whole field. Every codex emission means this,
 *   and so does the chapter's `set_chapter_text`.
 * - `"append"` — the text goes at the END of the current draft.
 * - `"replace_selection"` — the text replaces the author's current selection.
 *
 * The last two are RELATIVE to a draft, so they are only meaningful to a page that
 * holds one; a relative frame with no registered target is dropped rather than
 * buffered (`015` → D18).
 *
 * `CanvasField` is NOT widened alongside this: a chapter's body IS the `"body"`
 * field, and there is no `"text"` member on either side of the wire (`015` → D17).
 */
export type CanvasOp = "replace" | "append" | "replace_selection";

/**
 * `data:` payload of a `canvas` SSE frame — the assistant's draft for the subject
 * open in the working page's content pane (013 step 010; UC-076 / UC-077,
 * US-086.AC-1 / US-087.AC-1). Wire-exact with backend `CanvasFrame`, field for
 * field and in the same order.
 *
 * The fifth frame kind beside `thinking` / `delta` / `done` / `error`. It reaches
 * the client through `api/sse.ts`'s EXISTING generic-event routing (any event
 * name that is not `done` or `error` goes to `onEvent`), so `sse.ts` is unchanged.
 *
 * - `subject_kind` / `subject_id` — which subject the draft is for; the client
 *   dispatches on the pair. `subject_id` is nullable, never omitted: `null` is
 *   UC-076's blank entry, and an absent id must never be read as one.
 * - `field` — which part of the subject `text` is.
 * - `text` — the draft itself, WHOLE: it arrives in one frame, not streamed token
 *   by token, so the entry fills in one jump while the chat's prose streams on.
 * - `op` — which operation `text` performs on `field` (`015` step 011).
 *   **OPTIONAL on this twin, and that is the mirror of the backend's default**:
 *   `CanvasFrame.op: CanvasOp = "replace"` is a Pydantic field with a default, so
 *   it is always present on the wire, and an OMITTED `op` MEANS `"replace"` —
 *   exactly what every pre-`015` emission meant. A `.d.ts` carries no runtime
 *   default, so the default is applied at the single place that reads the field:
 *   `work/contentSubject.ts`'s dispatcher resolves `frame.op ?? "replace"` before
 *   routing. No other field of this interface changed, and the field order still
 *   mirrors the backend's declaration order.
 */
export interface CanvasFrame {
  subject_kind: SubjectKind;
  subject_id: string | null;
  field: CanvasField;
  text: string;
  op?: CanvasOp;
}
