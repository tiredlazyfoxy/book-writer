// Module-level auth seam (decision 3): ships only what `api/client.ts` needs for
// Bearer injection — a localStorage-backed token accessor plus a minimal logout.
// getCurrentUser() / JWT-decode and the redirect flow are feature 004's.
// MUST NOT import from `src/api/` — dependency direction is one-way: api/ -> auth.ts.

/** Read the stored JWT (localStorage key `"token"`), or `null` when absent. */
export function getToken(): string | null {
  return localStorage.getItem("token");
}

/** Clear the stored token. (004 adds the real logout/redirect flow.) */
export function logout(): void {
  localStorage.removeItem("token");
}
