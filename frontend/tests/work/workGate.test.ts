/**
 * Work access gate — 010.working-page / 001.work-entry-scaffold, DoD-1..DoD-2.
 *
 * Bound to the frozen signatures in status.md -> `## Skeleton` (step 001):
 *   type WorkAccessDecision = { allowed: true } | { allowed: false; redirectTo: string }
 *   resolveWorkAccess(): WorkAccessDecision      // pure, auth-only
 *   enforceWorkAccess(): boolean
 *
 * Every expected value comes from the step spec ("Interface intent" + "Definition
 * of done") and the mirrored `adminGate` contract, never from the implementation.
 * The gate is **auth-only**: it decides on token presence alone — book membership
 * is not in the JWT — so no role/identity is consulted here. A missing token
 * denies with the login href "/login/" (the repo's single login entry, the same
 * href the admin gate denies an unauthenticated caller to).
 *
 * The `auth.ts` seam is module-mocked (the repo rule "mock the module, not
 * fetch", one layer over), and `utils/navigate.ts` is module-mocked so the
 * enforcer's navigation is assertable.
 *
 * `globals: false`: every primitive is imported explicitly.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as auth from "../../src/auth";
import { navigateTo } from "../../src/utils/navigate";
import { enforceWorkAccess, resolveWorkAccess } from "../../src/work/workGate";

vi.mock("../../src/auth", () => ({
  getToken: vi.fn(),
  getRefreshToken: vi.fn(),
  setTokens: vi.fn(),
  setAccessToken: vi.fn(),
  getCurrentUser: vi.fn(),
  logout: vi.fn(),
}));

vi.mock("../../src/utils/navigate", () => ({
  navigateTo: vi.fn(),
}));

/** The login entry href — mirrors the admin gate's unauthenticated deny target. */
const LOGIN_HREF = "/login/";

beforeEach(() => {
  // `restoreMocks` wipes implementations between tests — seed the fully
  // unauthenticated world; each test opts into a token when it needs one.
  vi.mocked(auth.getToken).mockReturnValue(null);
});

describe("resolveWorkAccess", () => {
  it("DoD-1: allows when an access token is present", () => {
    vi.mocked(auth.getToken).mockReturnValue("work.access.token");

    expect(resolveWorkAccess()).toEqual({ allowed: true });
  });

  it("DoD-1: denies with the login href when the token is absent", () => {
    vi.mocked(auth.getToken).mockReturnValue(null);

    expect(resolveWorkAccess()).toEqual({ allowed: false, redirectTo: LOGIN_HREF });
  });

  it("DoD-1: performs no navigation when it allows (it is pure)", () => {
    vi.mocked(auth.getToken).mockReturnValue("work.access.token");

    resolveWorkAccess();

    expect(vi.mocked(navigateTo)).not.toHaveBeenCalled();
  });

  it("DoD-1: performs no navigation when it denies (it is pure)", () => {
    vi.mocked(auth.getToken).mockReturnValue(null);

    resolveWorkAccess();

    expect(vi.mocked(navigateTo)).not.toHaveBeenCalled();
  });
});

describe("enforceWorkAccess", () => {
  it("DoD-2: on deny, returns false and navigates exactly once to the login href", () => {
    vi.mocked(auth.getToken).mockReturnValue(null);

    expect(enforceWorkAccess()).toBe(false);
    expect(vi.mocked(navigateTo)).toHaveBeenCalledTimes(1);
    expect(vi.mocked(navigateTo)).toHaveBeenCalledWith(LOGIN_HREF);
  });

  it("DoD-2: on allow, returns true and never navigates", () => {
    vi.mocked(auth.getToken).mockReturnValue("work.access.token");

    expect(enforceWorkAccess()).toBe(true);
    expect(vi.mocked(navigateTo)).not.toHaveBeenCalled();
  });
});
