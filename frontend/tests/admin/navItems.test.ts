/**
 * Nav-item active matching — fast/002.admin-ui-retune, DoD-6.
 *
 * Bound to the frozen signatures in status.md -> `## Skeleton`:
 *   interface AdminNavItem { path; label; icon; exact? }
 *   const ADMIN_NAV_ITEMS: readonly AdminNavItem[]
 *   isNavItemActive(pathname: string, item: AdminNavItem): boolean
 *
 * The contract (plan.md, "Interface intent"): exact items match on string
 * equality only; non-exact items match the path itself OR a `/`-delimited
 * descendant — never a bare string prefix.
 *
 * `globals: false`: every primitive is imported explicitly.
 */
import { describe, expect, it } from "vitest";
import {
  ADMIN_NAV_ITEMS,
  isNavItemActive,
  type AdminNavItem,
} from "../../src/admin/components/shell/navItems";

/** Locate a declared nav item by its router-relative path. */
function itemAt(path: string): AdminNavItem {
  const item = ADMIN_NAV_ITEMS.find((candidate) => candidate.path === path);
  if (item === undefined) {
    throw new Error(`ADMIN_NAV_ITEMS has no entry with path "${path}"`);
  }
  return item;
}

describe("isNavItemActive", () => {
  it("DoD-6: the Users item (`/`, exact) is active at `/`", () => {
    expect(isNavItemActive("/", itemAt("/"))).toBe(true);
  });

  it("DoD-6: the Users item is not active at `/llm-servers` or `/database`", () => {
    const users = itemAt("/");

    expect(isNavItemActive("/llm-servers", users)).toBe(false);
    expect(isNavItemActive("/database", users)).toBe(false);
  });

  it("DoD-6: the Database item is active at `/database` and at `/database/anything`", () => {
    const database = itemAt("/database");

    expect(isNavItemActive("/database", database)).toBe(true);
    expect(isNavItemActive("/database/anything", database)).toBe(true);
  });

  it("DoD-6: the Database item is not active at `/`, `/llm-servers`, or `/database-export`", () => {
    const database = itemAt("/database");

    expect(isNavItemActive("/", database)).toBe(false);
    expect(isNavItemActive("/llm-servers", database)).toBe(false);
    expect(isNavItemActive("/database-export", database)).toBe(false);
  });

  it("DoD-6: a non-exact item matches a `/`-delimited descendant, never a bare prefix", () => {
    const llmServers = itemAt("/llm-servers");

    expect(isNavItemActive("/llm-servers", llmServers)).toBe(true);
    expect(isNavItemActive("/llm-servers/7", llmServers)).toBe(true);
    expect(isNavItemActive("/llm-servers-archive", llmServers)).toBe(false);
    expect(isNavItemActive("/", llmServers)).toBe(false);
  });
});
