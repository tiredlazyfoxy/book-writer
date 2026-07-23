import type { ApiErrorBody } from "../types/common";
import type { TokenResponse } from "../types/auth";
import { getToken, getRefreshToken, setAccessToken, logout } from "../auth";

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

  // Silent-refresh-on-401 seam (step 004): when the request carried a token and the
  // server rejected it, hand off to the interceptor, which attempts one refresh and
  // one retry. Requests with no token fall through to normal error handling below,
  // preserving existing behavior. Loop guard: skip while a refresh-driven retry is in
  // flight (`isRefreshing`) and never for the refresh endpoint itself.
  if (
    res.status === 401 &&
    token &&
    !isRefreshing &&
    !url.endsWith(`${REFRESH_PATH}`)
  ) {
    return silentRefreshRetry<T>(url, opts);
  }

  if (!res.ok) await throwApiError(res);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

/**
 * Silent-refresh-on-401 interceptor seam (step 004) — CODER IMPLEMENTS THE BODY.
 *
 * Reached only for a 401 on a request that carried an access token. Contract:
 * attempt exactly ONE refresh via a DIRECT `fetch` to `/api/auth/refresh` with body
 * `{ refresh_token: getRefreshToken() }` — NOT `api/auth.refresh`, which would create
 * a `client -> api/auth -> client` import cycle (`frontend.md` sanctions `fetch`
 * inside `client.ts`). On refresh success: store the new access token via
 * `setAccessToken(...)` and RETRY `request<T>(url, opts)` exactly once (the retry must
 * not re-enter this seam — guard against loops; never refresh the refresh call
 * itself). On refresh failure or no refresh token: call `logout()` and surface the
 * original `ApiError` (401). The `getRefreshToken` / `setAccessToken` / `logout`
 * imports from `../auth` are the coder's to add.
 */
const REFRESH_PATH = "/api/auth/refresh";

/** Set while a refresh-driven retry is in flight, so the retry cannot re-enter this seam. */
let isRefreshing = false;

async function silentRefreshRetry<T>(url: string, opts: RequestOptions): Promise<T> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) {
    logout();
    throw new ApiError(401, "Unauthorized");
  }

  // Direct `fetch` (the sanctioned location — NOT `api/auth.refresh`, which would
  // create a `client -> api/auth -> client` import cycle). Never routed through
  // `request`, so it can never re-enter this interceptor.
  let refreshRes: Response;
  try {
    refreshRes = await fetch(REFRESH_PATH, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
  } catch {
    logout();
    throw new ApiError(401, "Unauthorized");
  }

  if (!refreshRes.ok) {
    logout();
    throw new ApiError(401, "Unauthorized");
  }

  const tokens = (await refreshRes.json()) as TokenResponse;
  setAccessToken(tokens.access_token);

  // Retry the original request exactly once, with the loop guard set so a repeat 401
  // falls through to normal error handling instead of triggering another refresh.
  isRefreshing = true;
  try {
    return await request<T>(url, opts);
  } finally {
    isRefreshing = false;
  }
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
