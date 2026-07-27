import { request } from "./client";
import type {
  CodexEntryResponse,
  CodexKind,
  CreateCodexEntryRequest,
  UpdateCodexEntryRequest,
} from "../types/codex";

// Codex resource module (book-nested `/api/books/{book_id}/codex` surface,
// backend feature 013 step 003). Mirrors `api/chats.ts`: a module-level `/api/books`
// base, the STRING snowflake ids interpolated straight into the path, `signal?` as
// the trailing argument on every function, and the list envelope (`{ items: [...] }`)
// unwrapped HERE rather than modelled in `types/codex.d.ts`.
//
// Namespace-imported by callers (`import * as codexApi from "../../api/codex"`).
// All JSON HTTP goes through `client.request<T>` (Bearer injection, `ApiError`
// normalization, signal pass-through).
//
// The wire query params for the list route are `kind` / `q` / `include_archived`.

const BASE = "/api/books";

/**
 * `GET /api/books/{bookId}/codex?kind=<kind>&q=<needle>&include_archived=<flag>` —
 * the book's entries of one kind, name-ascending with unnamed rows last, filtered
 * by an optional case-insensitive substring needle over name/body. Unwraps
 * `.items` from the list envelope and resolves to the plain array.
 *
 * `needle` omitted (or empty) means no filter; `includeArchived` omitted means
 * `false` (archived entries are excluded).
 */
export async function listCodexEntries(
  bookId: string,
  kind: CodexKind,
  needle?: string,
  includeArchived?: boolean,
  signal?: AbortSignal,
): Promise<CodexEntryResponse[]> {
  const params = new URLSearchParams({ kind });
  if (needle) params.set("q", needle);
  params.set("include_archived", String(includeArchived ?? false));

  const res = await request<{ items: CodexEntryResponse[] }>(
    `${BASE}/${bookId}/codex?${params.toString()}`,
    { signal },
  );
  return res.items;
}

/** `GET /api/books/{bookId}/codex/{entryId}` — one codex entry. */
export async function getCodexEntry(
  bookId: string,
  entryId: string,
  signal?: AbortSignal,
): Promise<CodexEntryResponse> {
  return request<CodexEntryResponse>(`${BASE}/${bookId}/codex/${entryId}`, { signal });
}

/** `POST /api/books/{bookId}/codex` — create an entry; returns the created entry. */
export async function createCodexEntry(
  bookId: string,
  body: CreateCodexEntryRequest,
  signal?: AbortSignal,
): Promise<CodexEntryResponse> {
  return request<CodexEntryResponse>(`${BASE}/${bookId}/codex`, {
    method: "POST",
    body,
    signal,
  });
}

/**
 * `PUT /api/books/{bookId}/codex/{entryId}` — full-replace edit of an entry,
 * carrying `expected_modified_at` for the staleness check (a disagreeing value
 * comes back as an `ApiError` with status 409). Returns the updated entry.
 */
export async function updateCodexEntry(
  bookId: string,
  entryId: string,
  body: UpdateCodexEntryRequest,
  signal?: AbortSignal,
): Promise<CodexEntryResponse> {
  return request<CodexEntryResponse>(`${BASE}/${bookId}/codex/${entryId}`, {
    method: "PUT",
    body,
    signal,
  });
}
