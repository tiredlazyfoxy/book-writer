// Admin navbar declaration table + the pure active-path matcher (fast/002).
//
// No JSX in this module — it holds icon component *references*, not elements, so
// the table stays testable without a renderer.

import {
  IconDatabase,
  IconRobot,
  IconServer2,
  IconSparkles,
  IconUsers,
  type Icon,
} from "@tabler/icons-react";

/** One admin navbar entry. */
export interface AdminNavItem {
  /** Router-relative path (basename-stripped), e.g. `"/llm-servers"`. */
  path: string;
  /** Visible label, e.g. `"LLM Servers"`. */
  label: string;
  /** `@tabler` icon component *reference* (not an element). */
  icon: Icon;
  /**
   * When `true`, {@link isNavItemActive} matches on **string equality only** —
   * no descendant match. Required for the root item `/`, which would otherwise
   * be active everywhere.
   */
  exact?: boolean;
}

/** The five admin sections, in display order. */
export const ADMIN_NAV_ITEMS: readonly AdminNavItem[] = [
  { path: "/", label: "Users", icon: IconUsers, exact: true },
  { path: "/llm-servers", label: "LLM Servers", icon: IconServer2 },
  { path: "/database", label: "Database", icon: IconDatabase },
  { path: "/assistant-modes", label: "Assistant modes", icon: IconSparkles },
  { path: "/sub-agents", label: "Sub-agents", icon: IconRobot },
];

/**
 * Pure active-path match for one nav item against the current pathname.
 *
 * - `exact` items match **only** on string equality.
 * - non-exact items match the path itself **or** a `/`-delimited descendant —
 *   never a bare string prefix, so `/database` must NOT light up for
 *   `/database-export`.
 *
 * This is deliberately the repo's own contract rather than a delegation to
 * react-router's `end` prop, so the rule is unit-testable in isolation.
 */
export function isNavItemActive(pathname: string, item: AdminNavItem): boolean {
  if (item.exact) {
    return pathname === item.path;
  }

  if (pathname === item.path) {
    return true;
  }

  // Descendant match must be `/`-delimited, never a bare string prefix: compare
  // against the path with a single trailing slash, so `/database` matches
  // `/database/anything` but not `/database-export`.
  const prefix = item.path.endsWith("/") ? item.path : `${item.path}/`;
  return pathname.startsWith(prefix);
}
