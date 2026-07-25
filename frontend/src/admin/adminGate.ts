// Admin SPA admission gate (fast/002): a pure decision function plus the one impure
// enforcer that acts on it. Imported by `main.tsx` only — see `enforceAdminAccess`
// for why the gate lives outside React.

import { getCurrentUser, getToken } from "../auth";
import { navigateTo } from "../utils/navigate";

/**
 * Admission verdict for mounting the Admin SPA — a discriminated union on
 * `allowed`.
 *
 * - `{ allowed: true }` — mount.
 * - `{ allowed: false, redirectTo }` — do not mount; send the **browser** to
 *   `redirectTo` (an absolute, cross-SPA href such as `"/login/"` or `"/"`).
 */
export type AdminAccessDecision =
  | { allowed: true }
  | { allowed: false; redirectTo: string };

/**
 * Pure admission decision — reads `getToken()` / `getCurrentUser()` and returns a
 * verdict. No navigation, no localStorage writes, no token clearing.
 *
 * Rules, in order:
 *   1. no access token                          -> deny, `redirectTo: "/login/"`
 *   2. token present but `getCurrentUser()` null -> deny, `redirectTo: "/login/"`
 *      (a session we cannot decode is a broken session)
 *   3. `role !== "admin"`                        -> deny, `redirectTo: "/"`
 *   4. otherwise                                 -> allow
 *
 * Case 3 must **not** clear the tokens: an author's token is perfectly valid for
 * the user SPA. `/` (not `/login/`) is the non-admin target because the author
 * *is* authenticated — bouncing them to login would be a lie and would loop
 * (log in, get bounced, repeat). `/` is the surface they are entitled to, and it
 * matches the header's "Main site" exit, so the admin SPA has exactly one
 * non-admin exit.
 */
export function resolveAdminAccess(): AdminAccessDecision {
  // 1. No access token at all — never signed in (or signed out).
  if (!getToken()) {
    return { allowed: false, redirectTo: "/login/" };
  }

  // 2. A token we cannot decode into an identity is a broken session.
  const user = getCurrentUser();
  if (!user) {
    return { allowed: false, redirectTo: "/login/" };
  }

  // 3. Authenticated but not an admin: send them to the surface they *are*
  //    entitled to. Deliberately no token clearing — it is valid for the user SPA.
  if (user.role !== "admin") {
    return { allowed: false, redirectTo: "/" };
  }

  // 4. Admin.
  return { allowed: true };
}

/**
 * Impure enforcer. Calls {@link resolveAdminAccess}; on deny calls `navigateTo`
 * **exactly once** with `decision.redirectTo` and returns `false`; on allow
 * returns `true` and never navigates. The boolean means **"mount the SPA"**.
 *
 * **Gate placement.** This runs in `main.tsx` *before* `createRoot` — outside
 * React entirely. Rejected alternatives:
 *   - `App`'s render body (today's bug): render-phase mutation, StrictMode
 *     double-invoke, unmockable, and it makes `App` unrenderable in a test;
 *   - a `useEffect`: violates "useEffect only at page level", fires after first
 *     paint so unauthorized content flashes, and StrictMode double-mounts it —
 *     strictly worse than today;
 *   - an `<AdminGate>` component inside the router: still needs a side effect
 *     somewhere, inheriting one of the above. Its only advantage — re-checking on
 *     route change — is worthless: the role cannot change without a new token,
 *     and server-side 401s are already handled by `client.ts`'s refresh ->
 *     `logout()` path.
 *
 * In `main.tsx` there is no render phase, no effect, no StrictMode
 * double-invocation (module bodies run once), and it fires before first paint —
 * so no flash of admin content. Splitting pure `resolveAdminAccess` from impure
 * `enforceAdminAccess` puts 100% of the branching under unit test and leaves a
 * single untested `if` in an entry file. Consequence: `App.tsx` becomes
 * gate-free and therefore renderable in tests, which is what makes the shell
 * testable at all; nothing tests `main.tsx` itself (importing it calls
 * `createRoot`) — accepted, covered by a `[manual/live]` DoD.
 */
export function enforceAdminAccess(): boolean {
  const decision = resolveAdminAccess();

  if (!decision.allowed) {
    navigateTo(decision.redirectTo);
    return false;
  }

  return true;
}
