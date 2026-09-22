/**
 * Nav-item table + active matching — fast/002.admin-ui-retune, DoD-6, EXTENDED by
 * 012.assistant-config-editor / 006.frontend-api-and-nav, DoD-1.
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
 * 012/006 DoD-1 adds two entries — "Assistant modes" at `/assistant-modes` and
 * "Sub-agents" at `/sub-agents` (UC-095 step 1, UC-097 step 1) — **appended**
 * after the three pre-existing ones. The DoD requires the table pin be EXTENDED
 * to the new, longer list rather than weakened to a subset/`.some()` check, and
 * the pre-existing Users / LLM Servers / Database entries be asserted by name and
 * path, so the pin below is an exact length + an ordered full-table equality.
 * The two new entries' own `isNavItemActive` behaviour lives in the sibling spec
 * `assistantConfigNav.test.tsx` (006.context.md, "Testing notes for this step").
 *
 * `globals: false`: every primitive is imported explicitly.
 */
import { describe, expect, it } from "vitest";
import {
  ADMIN_NAV_ITEMS,
  isNavItemActive,
  type AdminNavItem,
} from "../../src/admin/components/shell/navItems";

/**
 * The admin nav table in display order: the three fast/002 entries followed by
 * 012/006's two appended ones. Every value is spec-given — the first three from
 * fast/002's plan (and pinned by `AdminNav.test.tsx`), the last two from
 * `006.frontend-api-and-nav.md` -> "Interface intent" + DoD-1.
 */
const EXPECTED_ITEMS: ReadonlyArray<{ path: string; label: string }> = [
  { path: "/", label: "Users" },
  { path: "/llm-servers", label: "LLM Servers" },
  { path: "/database", label: "Database" },
  { path: "/assistant-modes", label: "Assistant modes" },
  { path: "/sub-agents", label: "Sub-agents" },
];

/** Locate a declared nav item by its router-relative path. */
function itemAt(path: string): AdminNavItem {
  const item = ADMIN_NAV_ITEMS.find((candidate) => candidate.path === path);
  if (item === undefined) {
    throw new Error(`ADMIN_NAV_ITEMS has no entry with path "${path}"`);
  }
  return item;
}

describe("ADMIN_NAV_ITEMS", () => {
  it("DoD-1: declares exactly five entries", () => {
    expect(ADMIN_NAV_ITEMS).toHaveLength(EXPECTED_ITEMS.length);
  });

  it("DoD-1: the entries are Users / LLM Servers / Database / Assistant modes / Sub-agents, by name and path, in that order", () => {
    expect(ADMIN_NAV_ITEMS.map((item) => ({ path: item.path, label: item.label }))).toEqual([
      ...EXPECTED_ITEMS,
    ]);
  });

  it("DoD-1: every entry — including the two new ones — carries an icon", () => {
    for (const { path } of EXPECTED_ITEMS) {
      expect(itemAt(path).icon).toBeTruthy();
    }
  });
});

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
