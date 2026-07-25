// Work SPA admission gate (feature 010): a pure decision function plus the one
// impure enforcer that acts on it. Mirrors `src/admin/adminGate.ts` in shape and
// rationale, differing in exactly one way — it is **auth-only**. Imported by
// `main.tsx` only; see `enforceWorkAccess` for why the gate lives outside React.
//
import { getToken } from "../auth";
import { navigateTo } from "../utils/navigate";

/**
 * Admission verdict for mounting the Work SPA — a discriminated union on `allowed`.
 *
 * - `{ allowed: true }` — mount.
 * - `{ allowed: false, redirectTo }` — do not mount; send the **browser** to
 *   `redirectTo` (an absolute, cross-SPA href such as `"/login/"`).
 */
export type WorkAccessDecision =
  | { allowed: true }
  | { allowed: false; redirectTo: string };

/**
 * Pure admission decision — reads the stored access token and returns a verdict.
 * No navigation, no localStorage writes, no token clearing.
 *
 * **Auth-only.** Unlike `resolveAdminAccess`, there is no role check: book
 * membership is not decidable from the JWT, so a non-member is surfaced later by
 * the API's 403/404 on the workspace's own load, never here. A missing access
 * token denies with the login href; a present token allows.
 */
export function resolveWorkAccess(): WorkAccessDecision {
  // Auth-only: a missing access token means never signed in (or signed out).
  // No role check — book membership is not in the JWT and is enforced by the API.
  if (!getToken()) {
    return { allowed: false, redirectTo: "/login/" };
  }

  return { allowed: true };
}

/**
 * Impure enforcer. Calls {@link resolveWorkAccess}; on deny calls `navigateTo`
 * **exactly once** with `decision.redirectTo` and returns `false`; on allow returns
 * `true` and never navigates. The boolean means **"mount the SPA"**.
 *
 * **Gate placement.** This runs in `main.tsx` *before* `createRoot` — outside React
 * entirely. Rejected alternatives, exactly as `adminGate.ts` records them:
 *   - a render-phase check: render-phase mutation, StrictMode double-invoke,
 *     unmockable, and it makes `App` unrenderable in a test;
 *   - a `useEffect` gate: violates "useEffect only at page level", fires after first
 *     paint so unauthorized content flashes, and StrictMode double-mounts it;
 *   - a `<WorkGate>` component inside the router: still needs a side effect
 *     somewhere, inheriting one of the above; re-checking on route change is
 *     worthless here because auth cannot change without a new token.
 *
 * Splitting pure `resolveWorkAccess` from impure `enforceWorkAccess` puts all the
 * branching under unit test and leaves a single untested `if` in the entry file.
 */
export function enforceWorkAccess(): boolean {
  const decision = resolveWorkAccess();

  if (!decision.allowed) {
    navigateTo(decision.redirectTo);
    return false;
  }

  return true;
}
