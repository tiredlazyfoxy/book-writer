// Reader SPA admission gate (feature 022): a pure decision function plus the one
// impure enforcer that acts on it. A structural mirror of `src/work/workGate.ts`
// (itself mirroring `src/admin/adminGate.ts`), auth-only for the same reason —
// and here the reason is doubly true: a reader is by definition a NON-member, so
// there is nothing about book access the client could decide. Imported by
// `main.tsx` only; see `enforceReadAccess` for why the gate lives outside React.
//
import { getToken } from "../auth";
import { navigateTo } from "../utils/navigate";

/**
 * Admission verdict for mounting the Reader SPA — a discriminated union on
 * `allowed`.
 *
 * - `{ allowed: true }` — mount.
 * - `{ allowed: false, redirectTo }` — do not mount; send the **browser** to
 *   `redirectTo` (an absolute, cross-SPA href such as `"/login/"`).
 */
export type ReadAccessDecision =
  | { allowed: true }
  | { allowed: false; redirectTo: string };

/**
 * Pure admission decision — reads the stored access token and returns a verdict.
 * No navigation, no localStorage writes, no token clearing.
 *
 * **Auth-only.** There is no anonymous reader surface (US-030.AC-4): a missing
 * access token denies with the login href, a present token allows. Whether the
 * book is public and whether the caller may read it is the API's answer alone
 * (404 from `resolve_book_access`), never re-derived here.
 *
 */
export function resolveReadAccess(): ReadAccessDecision {
  if (!getToken()) {
    return { allowed: false, redirectTo: "/login/" };
  }
  return { allowed: true };
}

/**
 * Impure enforcer. Calls {@link resolveReadAccess}; on deny calls `navigateTo`
 * **exactly once** with `decision.redirectTo` and returns `false`; on allow
 * returns `true` and never navigates. The boolean means **"mount the SPA"**.
 *
 * **Gate placement.** This runs in `main.tsx` *before* `createRoot` — outside
 * React entirely (DoD-14), for the reasons `workGate.ts` / `adminGate.ts` record:
 * a render-phase check mutates during render and is unmockable, a `useEffect`
 * gate violates "useEffect only at page level" and flashes content before it
 * fires, and a `<ReadGate>` component inside the router still needs a side effect
 * somewhere.
 */
export function enforceReadAccess(): boolean {
  const decision = resolveReadAccess();
  if (!decision.allowed) {
    navigateTo(decision.redirectTo);
    return false;
  }
  return true;
}
