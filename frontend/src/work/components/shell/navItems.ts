// Work navigator declaration table + pure href / active-path helpers (010/002).
//
// Mirrors `src/admin/components/shell/navItems.ts`: no JSX here, only icon
// component *references*, so the table and its matchers stay renderer-free and
// unit-testable. The work version drops `exact` (there is no root entry — Book
// state is `/state`) and adds a book-id parameter, optional extra active
// segments, and a content-vs-chat pane-target discriminator.

import {
  IconBook2,
  IconFileText,
  IconGitBranch,
  IconInfoCircle,
  IconMapPin,
  IconMessage,
  IconUsers,
  type Icon,
} from "@tabler/icons-react";

/** Which region a navigator entry drives — the content pane or the chat pane. */
export type WorkPaneTarget = "content" | "chat";

/** One work-navigator entry, scoped under `/work/:bookId`. */
export interface WorkNavItem {
  /** Path segment under `/work/:bookId`, basename-stripped, e.g. `"/state"`. */
  path: string;
  /** Author-facing label, e.g. `"Book state"`. */
  label: string;
  /** `@tabler` icon component *reference* (not an element). */
  icon: Icon;
  /**
   * Additional path segments (basename- and book-id-stripped) that also mark
   * this item active — e.g. Chapters (`/chapters`) also lights up for the
   * singular single-chapter segment `/chapter`. Omitted when there are none.
   */
  extraActiveSegments?: readonly string[];
  /** The region this entry renders into: the content pane, or (Chats) the chat pane. */
  paneTarget: WorkPaneTarget;
}

/**
 * The seven navigator entries in UC-090 order — Book state · Characters ·
 * Locations · Facts · Chapters · Variants · Chats.
 *
 * Book state · Characters · Locations · Facts · Chapters · Variants · Chats.
 * Chapters also lights up for the singular single-chapter segment `/chapter`;
 * Chats is the sole entry whose target is the chat pane, the rest render into the
 * content pane. (Variants' per-chapter path `/variants/:chapterId` needs no extra
 * segment — it is a `/`-delimited descendant of `/variants`, which
 * {@link isWorkNavItemActive} already matches.)
 */
export const WORK_NAV_ITEMS: readonly WorkNavItem[] = [
  { path: "/state", label: "Book state", icon: IconBook2, paneTarget: "content" },
  { path: "/characters", label: "Characters", icon: IconUsers, paneTarget: "content" },
  { path: "/locations", label: "Locations", icon: IconMapPin, paneTarget: "content" },
  { path: "/facts", label: "Facts", icon: IconInfoCircle, paneTarget: "content" },
  {
    path: "/chapters",
    label: "Chapters",
    icon: IconFileText,
    extraActiveSegments: ["/chapter"],
    paneTarget: "content",
  },
  { path: "/variants", label: "Variants", icon: IconGitBranch, paneTarget: "content" },
  { path: "/chats", label: "Chats", icon: IconMessage, paneTarget: "chat" },
];

/**
 * Build the router-relative (basename-stripped) href for a navigator entry under
 * a given book id, e.g. `("42", { path: "/state", … })` → `/42/state`.
 *
 * SKELETON: unimplemented — body throws.
 */
export function workNavHref(bookId: string, item: WorkNavItem): string {
  return `/${bookId}${item.path}`;
}

/**
 * Pure active-path match for one navigator entry against the current pathname,
 * scoped to a book id: true for the entry's own path and its `/`-delimited
 * descendants, and for any of its `extraActiveSegments`; false for a sibling
 * entry's path, and false for a bare string prefix that is not a `/`-delimited
 * boundary (so `/state` never lights up for `/statelike`).
 */
export function isWorkNavItemActive(
  pathname: string,
  bookId: string,
  item: WorkNavItem,
): boolean {
  const segments = [item.path, ...(item.extraActiveSegments ?? [])];
  return segments.some((segment) => matchesUnderBook(pathname, `/${bookId}${segment}`));
}

/**
 * Match `pathname` against a fully-resolved base path: exact equality, or a
 * `/`-delimited descendant. Compares against the base plus a single trailing
 * slash so a bare string prefix (`/state` vs `/statelike`) never matches — the
 * same segment-boundary rule as admin's `isNavItemActive`.
 */
function matchesUnderBook(pathname: string, base: string): boolean {
  if (pathname === base) {
    return true;
  }
  const prefix = base.endsWith("/") ? base : `${base}/`;
  return pathname.startsWith(prefix);
}
