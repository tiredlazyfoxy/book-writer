import { request } from "./client";
import type {
  AddMemberRequest,
  BookDetailResponse,
  BookListResponse,
  BookResponse,
  CollaborationMode,
  CreateBookRequest,
  SetVisibilityRequest,
  TransferOwnershipRequest,
  Visibility,
} from "../types/books";

// Book resource module (author-owned `/api/books` surface). All JSON HTTP goes
// through `client.request` (which injects Bearer when a token exists).
// Namespace-imported by callers (`import * as booksApi from "../../api/books"`);
// `signal?` is always the trailing arg.
//
// OPEN for step 7: the settings-mutation calls (archive / unarchive / transfer /
// add-member / remove-member / set-visibility, keyed by the `{book_id}` path)
// extend this module — keep the shape mirror-of-`api/admin.ts`.

const BASE = "/api/books";

/** A collaboration-mode choice for the create-book `<Select>` (step 006). */
export interface CollaborationModeOption {
  value: CollaborationMode;
  label: string;
}

/** A visibility choice for the create-book `<Select>` (step 006). */
export interface VisibilityOption {
  value: Visibility;
  label: string;
}

/**
 * Collaboration-mode options for the create-book select. Runtime const, so it lives
 * here in the `.ts` api module rather than in `types/books.d.ts` (a declaration file
 * cannot hold a runtime value). Mirrors the backend `CollaborationMode` vocabulary 1:1.
 */
export const COLLABORATION_MODE_OPTIONS: CollaborationModeOption[] = [
  { value: "free", label: "Free" },
  { value: "proposal", label: "Proposal" },
];

/** Visibility options for the create-book select. Mirrors the backend `Visibility` vocabulary 1:1. */
export const VISIBILITY_OPTIONS: VisibilityOption[] = [
  { value: "private", label: "Private" },
  { value: "public", label: "Public" },
];

/** `GET /api/books` — books the caller owns (owned list). */
export async function listOwnedBooks(signal?: AbortSignal): Promise<BookListResponse> {
  return request<BookListResponse>(BASE, { signal });
}

/** `GET /api/books/shared` — books shared with the caller (co-author, shared list). */
export async function listSharedBooks(signal?: AbortSignal): Promise<BookListResponse> {
  return request<BookListResponse>(`${BASE}/shared`, { signal });
}

/** `POST /api/books` — create a book; the caller becomes owner. Returns the new book. */
export async function createBook(
  body: CreateBookRequest,
  signal?: AbortSignal,
): Promise<BookResponse> {
  return request<BookResponse>(BASE, { method: "POST", body, signal });
}

/** `GET /api/books/{id}` — the members-only book detail (book fields + co-author list). */
export async function getBookDetail(
  bookId: string,
  signal?: AbortSignal,
): Promise<BookDetailResponse> {
  return request<BookDetailResponse>(`${BASE}/${bookId}`, { signal });
}

/** `POST /api/books/{id}/archive` — archive a book (owner-only). Returns the summary. */
export async function archiveBook(
  bookId: string,
  signal?: AbortSignal,
): Promise<BookResponse> {
  return request<BookResponse>(`${BASE}/${bookId}/archive`, { method: "POST", signal });
}

/** `POST /api/books/{id}/unarchive` — reverse an archive (owner-only). Returns the summary. */
export async function unarchiveBook(
  bookId: string,
  signal?: AbortSignal,
): Promise<BookResponse> {
  return request<BookResponse>(`${BASE}/${bookId}/unarchive`, { method: "POST", signal });
}

/** `POST /api/books/{id}/transfer` — transfer ownership to a co-author (owner-only). */
export async function transferOwnership(
  bookId: string,
  body: TransferOwnershipRequest,
  signal?: AbortSignal,
): Promise<BookResponse> {
  return request<BookResponse>(`${BASE}/${bookId}/transfer`, { method: "POST", body, signal });
}

/** `POST /api/books/{id}/members` — grant co-author access. Returns the refreshed detail. */
export async function addMember(
  bookId: string,
  body: AddMemberRequest,
  signal?: AbortSignal,
): Promise<BookDetailResponse> {
  return request<BookDetailResponse>(`${BASE}/${bookId}/members`, { method: "POST", body, signal });
}

/** `DELETE /api/books/{id}/members/{userId}` — revoke a co-author. Returns the refreshed detail. */
export async function removeMember(
  bookId: string,
  userId: string,
  signal?: AbortSignal,
): Promise<BookDetailResponse> {
  return request<BookDetailResponse>(`${BASE}/${bookId}/members/${userId}`, {
    method: "DELETE",
    signal,
  });
}

/** `PATCH /api/books/{id}/visibility` — switch a book between private and public (owner-only). */
export async function setVisibility(
  bookId: string,
  body: SetVisibilityRequest,
  signal?: AbortSignal,
): Promise<BookResponse> {
  return request<BookResponse>(`${BASE}/${bookId}/visibility`, { method: "PATCH", body, signal });
}
