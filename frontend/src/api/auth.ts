import { request, throwApiError } from "./client";
import { getToken } from "../auth";
import type {
  AuthStatusResponse,
  CreateDBRequest,
  LoginRequest,
  RefreshRequest,
  TokenResponse,
} from "../types/auth";

// Auth resource module. All JSON HTTP goes through `client.request` (which injects
// Bearer only when a token exists — cold-instance setup and login calls carry no
// Authorization automatically). The multipart `setupImport` bypasses `request` like
// `sse.ts` does, building its own `FormData` and reading the token via the `auth.ts`
// accessor (one-way dependency api/ -> auth.ts).
//
// The public `refresh()` below is the caller-facing refresh fn; the silent-refresh
// interceptor in `client.ts` uses its OWN direct `fetch` (import-cycle avoidance,
// see step context) and does not call this.

const BASE = "/api/auth";

/** `GET /api/auth/status` — reports whether the instance still needs first-run setup. */
export async function getAuthStatus(signal?: AbortSignal): Promise<AuthStatusResponse> {
  return request<AuthStatusResponse>(`${BASE}/status`, { signal });
}

/** `POST /api/auth/login` — exchange credentials for the access + refresh token pair. */
export async function login(body: LoginRequest, signal?: AbortSignal): Promise<TokenResponse> {
  return request<TokenResponse>(`${BASE}/login`, { method: "POST", body, signal });
}

/** `POST /api/auth/refresh` — exchange a refresh token for a fresh access token (echoes the refresh token). */
export async function refresh(body: RefreshRequest, signal?: AbortSignal): Promise<TokenResponse> {
  return request<TokenResponse>(`${BASE}/refresh`, { method: "POST", body, signal });
}

/** `POST /api/auth/setup/create` — create the DB + first admin; returns the auto-sign-in token pair. */
export async function setupCreate(
  body: CreateDBRequest,
  signal?: AbortSignal,
): Promise<TokenResponse> {
  return request<TokenResponse>(`${BASE}/setup/create`, {
    method: "POST",
    body,
    signal,
  });
}

/**
 * `POST /api/auth/setup/import` — bootstrap by importing a DB export. Multipart:
 * builds a `FormData` with the archive under field `file`, must NOT set a JSON
 * `Content-Type` (the browser supplies the multipart boundary), and attaches
 * `Authorization` from `getToken()` only when a token is present. Returns the
 * post-import status DTO (no token issued).
 */
export async function setupImport(
  file: File,
  signal?: AbortSignal,
): Promise<AuthStatusResponse> {
  const formData = new FormData();
  formData.append("file", file);

  // Multipart bypass of `request` (mirrors sse.ts): no JSON Content-Type so the
  // browser sets the multipart boundary; Authorization only when a token exists.
  const token = getToken();
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`${BASE}/setup/import`, {
    method: "POST",
    headers,
    body: formData,
    signal,
  });

  if (!res.ok) await throwApiError(res);
  return (await res.json()) as AuthStatusResponse;
}
