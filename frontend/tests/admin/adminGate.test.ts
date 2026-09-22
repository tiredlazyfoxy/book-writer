/**
 * Admin role gate — fast/002.admin-ui-retune, DoD-1..DoD-5.
 *
 * Bound to the frozen signatures in status.md -> `## Skeleton`:
 *   type AdminAccessDecision = { allowed: true } | { allowed: false; redirectTo: string }
 *   resolveAdminAccess(): AdminAccessDecision      // pure
 *   enforceAdminAccess(): boolean                  // "mount the SPA"
 *
 * Every expected value comes from plan.md ("Interface intent" + "Definition of
 * done"), never from the implementation. The `auth.ts` seam is module-mocked
 * (the repo's rule "tests mock the api/ module, not fetch", one layer over), and
 * `utils/navigate.ts` is module-mocked so the enforcer's navigation is assertable.
 *
 * `globals: false`: every primitive is imported explicitly.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { CurrentUser } from "../../src/auth";
import * as auth from "../../src/auth";
import { navigateTo } from "../../src/utils/navigate";
import { enforceAdminAccess, resolveAdminAccess } from "../../src/admin/adminGate";

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

/** localStorage key names are ground truth from context.md ("Auth facts"). */
const ACCESS_TOKEN_KEY = "access_token";
const REFRESH_TOKEN_KEY = "refresh_token";

const adminUser: CurrentUser = { user_id: "u-admin", username: "root", role: "admin" };
const authorUser: CurrentUser = { user_id: "u-author", username: "penny", role: "author" };

beforeEach(() => {
  // `restoreMocks` wipes implementations between tests, so seed the default
  // (fully unauthenticated) world here.
  vi.mocked(auth.getToken).mockReturnValue(null);
  vi.mocked(auth.getCurrentUser).mockReturnValue(null);
});

describe("resolveAdminAccess", () => {
  it("DoD-1: denies with target \"/login/\" when there is no access token", () => {
    vi.mocked(auth.getToken).mockReturnValue(null);

    expect(resolveAdminAccess()).toEqual({ allowed: false, redirectTo: "/login/" });
  });

  it("DoD-1: never navigates — it is pure", () => {
    vi.mocked(auth.getToken).mockReturnValue(null);

    resolveAdminAccess();

    expect(vi.mocked(navigateTo)).not.toHaveBeenCalled();
  });

  it("DoD-2: denies with target \"/login/\" when the token carries no decodable identity", () => {
    vi.mocked(auth.getToken).mockReturnValue("an.undecodable.token");
    vi.mocked(auth.getCurrentUser).mockReturnValue(null);

    expect(resolveAdminAccess()).toEqual({ allowed: false, redirectTo: "/login/" });
  });

  it("DoD-3: denies an \"author\" identity with target \"/\" — not \"/login/\"", () => {
    vi.mocked(auth.getToken).mockReturnValue("author.access.token");
    vi.mocked(auth.getCurrentUser).mockReturnValue(authorUser);

    expect(resolveAdminAccess()).toEqual({ allowed: false, redirectTo: "/" });
  });

  it("DoD-3: denying an \"author\" does not clear the stored tokens", () => {
    localStorage.setItem(ACCESS_TOKEN_KEY, "author.access.token");
    localStorage.setItem(REFRESH_TOKEN_KEY, "author.refresh.token");
    vi.mocked(auth.getToken).mockReturnValue("author.access.token");
    vi.mocked(auth.getCurrentUser).mockReturnValue(authorUser);

    resolveAdminAccess();

    expect(vi.mocked(auth.logout)).not.toHaveBeenCalled();
    expect(localStorage.getItem(ACCESS_TOKEN_KEY)).toBe("author.access.token");
    expect(localStorage.getItem(REFRESH_TOKEN_KEY)).toBe("author.refresh.token");
  });

  it("DoD-4: allows an \"admin\" identity", () => {
    vi.mocked(auth.getToken).mockReturnValue("admin.access.token");
    vi.mocked(auth.getCurrentUser).mockReturnValue(adminUser);

    expect(resolveAdminAccess()).toEqual({ allowed: true });
  });
});

describe("enforceAdminAccess", () => {
  it("DoD-5: returns false and navigates exactly once to \"/login/\" with no token", () => {
    vi.mocked(auth.getToken).mockReturnValue(null);

    expect(enforceAdminAccess()).toBe(false);
    expect(vi.mocked(navigateTo)).toHaveBeenCalledTimes(1);
    expect(vi.mocked(navigateTo)).toHaveBeenCalledWith("/login/");
  });

  it("DoD-5: returns false and navigates exactly once to \"/\" for an \"author\"", () => {
    vi.mocked(auth.getToken).mockReturnValue("author.access.token");
    vi.mocked(auth.getCurrentUser).mockReturnValue(authorUser);

    expect(enforceAdminAccess()).toBe(false);
    expect(vi.mocked(navigateTo)).toHaveBeenCalledTimes(1);
    expect(vi.mocked(navigateTo)).toHaveBeenCalledWith("/");
  });

  it("DoD-5: returns true and never navigates for an \"admin\"", () => {
    vi.mocked(auth.getToken).mockReturnValue("admin.access.token");
    vi.mocked(auth.getCurrentUser).mockReturnValue(adminUser);

    expect(enforceAdminAccess()).toBe(true);
    expect(vi.mocked(navigateTo)).not.toHaveBeenCalled();
  });
});
