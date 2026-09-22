import { request } from "./client";
import type {
  FlagListResponse,
  FlagResponse,
  RaiseFlagRequest,
} from "../types/flags";

// Flag ("warning") resource module (feature 016) — the chapter-nested flag surface.
// Mirrors `api/chapters.ts` exactly: a module-level `/api/books` base, the STRING
// snowflake ids interpolated straight into the path, `signal?` as the trailing
// argument on every function, and all JSON HTTP through `client.request<T>`.
//
//   GET  /api/books/{bookId}/chapters/{chapterId}/flags                   -> FlagListResponse
//   POST /api/books/{bookId}/chapters/{chapterId}/flags                   -> FlagResponse (201)
//   POST /api/books/{bookId}/chapters/{chapterId}/flags/{flagId}/resolve  -> FlagResponse
//
// THE WIRE SAYS `flag`; THE UI SAYS "warning" — these functions are named for the
// endpoint they address, and the author-facing word stays in the components.
//
// NO error handling and NO refusal parsing here: `request<T>` normalizes a non-2xx
// into an `ApiError` carrying `status` (the page branches on `403` / `404` / `409`)
// and the server's plain-string reason text.
//
// Namespace-imported by callers (`import * as flagsApi from "../../api/flags"`).
//
const BASE = "/api/books";

/**
 * `GET /api/books/{bookId}/chapters/{chapterId}/flags` — the chapter's warnings, open
 * AND resolved, newest first.
 *
 * Resolves to the WHOLE envelope (`{ items }`), not a bare array — the `listChapters`
 * precedent. Members-only server-side.
 */
export async function listFlags(
  bookId: string,
  chapterId: string,
  signal?: AbortSignal,
): Promise<FlagListResponse> {
  return request<FlagListResponse>(
    `${BASE}/${bookId}/chapters/${chapterId}/flags`,
    { signal },
  );
}

/**
 * `POST /api/books/{bookId}/chapters/{chapterId}/flags` — raise a warning (UC-067 /
 * US-075.AC-1); answers `201` with the created flag.
 *
 * The stored flag is always `origin: "person"`, `status: "open"` and attributed to the
 * caller — the body carries no origin field, so a member cannot forge a check finding.
 * A blank `comment` comes back `422`.
 */
export async function raiseFlag(
  bookId: string,
  chapterId: string,
  body: RaiseFlagRequest,
  signal?: AbortSignal,
): Promise<FlagResponse> {
  return request<FlagResponse>(`${BASE}/${bookId}/chapters/${chapterId}/flags`, {
    method: "POST",
    body,
    signal,
  });
}

/**
 * `POST /api/books/{bookId}/chapters/{chapterId}/flags/{flagId}/resolve` — resolve an
 * open warning (UC-068 / US-076.AC-2, US-077.AC-1). Sends **no request body**: this is
 * a command, not a representation to replace.
 *
 * Owner-only server-side, so a co-author's call comes back `403`; an already-resolved
 * flag is `409`. Returns the STORED flag, carrying `resolved_by` / `resolved_at`.
 * There is no un-resolve call.
 */
export async function resolveFlag(
  bookId: string,
  chapterId: string,
  flagId: string,
  signal?: AbortSignal,
): Promise<FlagResponse> {
  return request<FlagResponse>(
    `${BASE}/${bookId}/chapters/${chapterId}/flags/${flagId}/resolve`,
    { method: "POST", signal },
  );
}
