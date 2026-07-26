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
