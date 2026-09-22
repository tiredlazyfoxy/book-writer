// Module-level auth seam (frontend.md — plain module state, not a class): dual-token
// (access + refresh) localStorage storage, client-side identity decode of the access
// token for display, and a real logout/redirect. MUST NOT import from `src/api/` —
// dependency direction is one-way: api/ -> auth.ts. (Type-only imports from
// `src/types/` are fine — they carry no runtime dependency.)
//
// Skeleton (004): signatures + the dual-key storage scheme are frozen; bodies throw
// until the coder fills them.

import type { UserRole } from "./types/auth";

/** localStorage keys for the token pair (replaces the single 002/003 `"token"` key). */
export const ACCESS_TOKEN_KEY = "access_token";
export const REFRESH_TOKEN_KEY = "refresh_token";

/**
 * Decoded access-token identity for client-side display only (no signature check —
 * the server validates via `get_current_user`). `user_id` is kept a **string**: the
 * backend serializes the snowflake id as a string in the JWT `user_id` claim; the
 * coder must NOT apply `Number()`/`parseInt` coercion (would truncate ids > 2^53).
 */
export interface CurrentUser {
  user_id: string;
  username: string;
  role: UserRole;
}

/** Store both tokens (login / setup auto-sign-in) under the pair keys. */
export function setTokens(accessToken: string, refreshToken: string): void {
  localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
  localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
}

/** Store only the access token (after a silent refresh) — leaves the refresh token intact. */
export function setAccessToken(accessToken: string): void {
  localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
}

/** The access token (what `client.ts` sends as Bearer), or `null` when absent. */
export function getToken(): string | null {
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

/** The refresh token, or `null` when absent. */
export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_TOKEN_KEY);
}

/**
 * Client-side JWT-decode of the access token to the caller's identity for display;
 * `null` when no access token is present or it cannot be decoded. `user_id` stays a
 * string (see `CurrentUser`).
 */
export function getCurrentUser(): CurrentUser | null {
  const token = getToken();
  if (!token) return null;

  const parts = token.split(".");
  if (parts.length !== 3) return null;

  try {
    // Middle segment = base64url-encoded JSON payload. Convert base64url -> base64
    // and restore `=` padding to a multiple of 4 before `atob`. No signature check —
    // display only; the server validates via `get_current_user`.
    const base64 = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    const padded = base64.padEnd(base64.length + ((4 - (base64.length % 4)) % 4), "=");
    const claims = JSON.parse(atob(padded)) as {
      user_id?: unknown;
      username?: unknown;
      role?: unknown;
    };

    if (
      typeof claims.user_id !== "string" ||
      typeof claims.username !== "string" ||
      typeof claims.role !== "string"
    ) {
      return null;
    }

    // Keep `user_id` a string — no Number()/parseInt (snowflake ids exceed 2^53).
    return {
      user_id: claims.user_id,
      username: claims.username,
      role: claims.role as UserRole,
    };
  } catch {
    return null;
  }
}

/** Clear both tokens and redirect to `/login/` via `window.location.href`. */
export function logout(): void {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  window.location.href = "/login/";
}
