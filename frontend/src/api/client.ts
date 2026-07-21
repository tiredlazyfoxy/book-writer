import type { ApiErrorBody } from "../types/common";
import { getToken } from "../auth";

/** Normalized non-2xx error: carries the HTTP status, a message, and the raw body. */
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public details?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "DELETE";
  /** Plain JS value — `request` JSON-stringifies it. Leave undefined for bodyless calls. */
  body?: unknown;
  signal?: AbortSignal;
}

/** Headers for raw `fetch()` callers (streaming / multipart) — JSON content type + Bearer when present. */
export function authHeaders(): HeadersInit {
  const token = getToken();
  return {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

/**
 * Authenticated JSON request: default GET; sets `Content-Type: application/json`;
 * injects `Authorization: Bearer <getToken()>` when a token exists; JSON-stringifies
 * a defined `body`; forwards `signal`. Non-2xx -> `throwApiError`; 204 -> `undefined`;
 * otherwise parsed JSON as `T`.
 */
export async function request<T>(url: string, opts: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(url, {
    method: opts.method ?? "GET",
    headers,
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
    signal: opts.signal,
  });

  if (!res.ok) await throwApiError(res);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

/** Throw `ApiError(status, message, body)` from a non-OK response, preferring a `{ detail }` message. */
export async function throwApiError(res: Response): Promise<never> {
  const body = (await res.json().catch(() => null)) as ApiErrorBody | null;
  const message =
    body && typeof body === "object" && typeof body.detail === "string"
      ? body.detail
      : res.statusText;
  throw new ApiError(res.status, message, body);
}
