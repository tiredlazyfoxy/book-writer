/**
 * The two assistant-config nav entries' own active-matching behaviour —
 * 012.assistant-config-editor / 006.frontend-api-and-nav, DoD-2
 * (UC-095 step 1, UC-097 step 1).
 *
 * Bound to the frozen signatures in status.md -> `## Skeleton` (step 006, and
 * unchanged from fast/002):
 *   interface AdminNavItem { path; label; icon; exact? }
 *   const ADMIN_NAV_ITEMS: readonly AdminNavItem[]
 *   isNavItemActive(pathname: string, item: AdminNavItem): boolean
 *
 * Scope split, per `006.context.md` -> "Testing notes for this step": this spec
 * covers ONLY what the two pre-existing specs do not — the new entries' own
 * behaviour under `isNavItemActive`. The table pin lives in `navItems.test.ts`
 * and the rendered-nav pin in `AdminNav.test.tsx`; neither is duplicated here.
 *
 * Expected values come from DoD-2: each new entry is active for its own path,
 * and not for the other's, nor for `/`. Paths are the spec's `/assistant-modes`
 * and `/sub-agents` (basename-stripped, as everywhere in the admin specs).
 *
 * `globals: false`: every primitive is imported explicitly.
 */
import { describe, expect, it } from "vitest";
import {
  ADMIN_NAV_ITEMS,
  isNavItemActive,
  type AdminNavItem,
} from "../../src/admin/components/shell/navItems";

const ASSISTANT_MODES_PATH = "/assistant-modes";
const SUB_AGENTS_PATH = "/sub-agents";

/** Locate a declared nav item by its router-relative path. */
function itemAt(path: string): AdminNavItem {
  const item = ADMIN_NAV_ITEMS.find((candidate) => candidate.path === path);
  if (item === undefined) {
    throw new Error(`ADMIN_NAV_ITEMS has no entry with path "${path}"`);
  }
  return item;
}

describe("isNavItemActive — the assistant-config entries", () => {
  it("DoD-2: the Assistant modes entry is active at `/assistant-modes`", () => {
    expect(isNavItemActive(ASSISTANT_MODES_PATH, itemAt(ASSISTANT_MODES_PATH))).toBe(true);
  });

  it("DoD-2: the Assistant modes entry is NOT active at `/sub-agents` nor at `/`", () => {
    const assistantModes = itemAt(ASSISTANT_MODES_PATH);

    expect(isNavItemActive(SUB_AGENTS_PATH, assistantModes)).toBe(false);
    expect(isNavItemActive("/", assistantModes)).toBe(false);
  });

  it("DoD-2: the Sub-agents entry is active at `/sub-agents`", () => {
    expect(isNavItemActive(SUB_AGENTS_PATH, itemAt(SUB_AGENTS_PATH))).toBe(true);
  });

  it("DoD-2: the Sub-agents entry is NOT active at `/assistant-modes` nor at `/`", () => {
    const subAgents = itemAt(SUB_AGENTS_PATH);

    expect(isNavItemActive(ASSISTANT_MODES_PATH, subAgents)).toBe(false);
    expect(isNavItemActive("/", subAgents)).toBe(false);
  });
});
