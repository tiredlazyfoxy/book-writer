/**
 * Work navigator model — 010.working-page / 002.workspace-shell, DoD-1 · DoD-2 · DoD-3.
 *
 * Bound to the frozen signatures in status.md -> `## Skeleton` (step 002):
 *   type WorkPaneTarget = "content" | "chat"
 *   interface WorkNavItem { path; label; icon; extraActiveSegments?; paneTarget }
 *   const WORK_NAV_ITEMS: readonly WorkNavItem[]
 *   workNavHref(bookId: string, item: WorkNavItem): string
 *   isWorkNavItemActive(pathname: string, bookId: string, item: WorkNavItem): boolean
 *
 * Every expected value is taken from the spec, never from code:
 *   - The seven ordered author-facing labels come from the DoD-1 list and
 *     `frontend-workspace.md` -> "The working page" (Book state · Characters ·
 *     Locations · Facts · Chapters · Variants · Chats).
 *   - The subject path each entry links to comes from `context.md` -> "The `/work`
 *     route map" (`/work/:bookId/state`, `/characters`, `/locations`, `/facts`,
 *     `/chapters` + `/chapter/:id`, `/variants` + `/variants/:chapterId`, `/chats`).
 *     Basename-stripped (DoD-2), the href for book `bk-1` is `/bk-1/<segment>`.
 *   - The active-match rules come from the "Interface intent" + DoD-3: own path,
 *     a `/`-delimited descendant, and an item's extra active segment; never a
 *     sibling entry's path nor a bare string prefix.
 *
 * Items are looked up by their author-facing LABEL (pinned by DoD-1), not by the
 * `path` field, whose exact string form the skeleton does not freeze.
 *
 * `globals: false`: every primitive is imported explicitly.
 */
import { describe, expect, it } from "vitest";
import {
  WORK_NAV_ITEMS,
  workNavHref,
  isWorkNavItemActive,
  type WorkNavItem,
} from "../../src/work/components/shell/navItems";

/** The seven author-facing labels, in the UC-090 order the DoD pins. */
const EXPECTED_LABELS = [
  "Book state",
  "Characters",
  "Locations",
  "Facts",
  "Chapters",
  "Variants",
  "Chats",
] as const;

/** Label -> its basename-stripped subject href for book `bk-1` (from the route map). */
const EXPECTED_HREFS: Record<string, string> = {
  "Book state": "/bk-1/state",
  Characters: "/bk-1/characters",
  Locations: "/bk-1/locations",
  Facts: "/bk-1/facts",
  Chapters: "/bk-1/chapters",
  Variants: "/bk-1/variants",
  Chats: "/bk-1/chats",
};

/** Locate a declared nav item by its author-facing label. */
function itemByLabel(label: string): WorkNavItem {
  const item = WORK_NAV_ITEMS.find((candidate) => candidate.label === label);
  if (item === undefined) {
    throw new Error(`WORK_NAV_ITEMS has no entry labelled "${label}"`);
  }
  return item;
}

describe("WORK_NAV_ITEMS", () => {
  it("DoD-1: declares exactly seven entries", () => {
    expect(WORK_NAV_ITEMS).toHaveLength(7);
  });

  it("DoD-1: the labels are the UC-090 order Book state · Characters · Locations · Facts · Chapters · Variants · Chats", () => {
    expect(WORK_NAV_ITEMS.map((item) => item.label)).toEqual([...EXPECTED_LABELS]);
  });
});

describe("workNavHref", () => {
  it("DoD-2: each entry builds its own subject href under the given book id (basename-stripped)", () => {
    for (const label of EXPECTED_LABELS) {
      expect(workNavHref("bk-1", itemByLabel(label))).toBe(EXPECTED_HREFS[label]);
    }
  });

  it("DoD-2: the href tracks the book id it is built for", () => {
    expect(workNavHref("other-book", itemByLabel("Chapters"))).toBe("/other-book/chapters");
  });
});

describe("isWorkNavItemActive", () => {
  it("DoD-3: an entry is active for its own path", () => {
    expect(isWorkNavItemActive("/bk-1/state", "bk-1", itemByLabel("Book state"))).toBe(true);
    expect(isWorkNavItemActive("/bk-1/chapters", "bk-1", itemByLabel("Chapters"))).toBe(true);
  });

  it("DoD-3: an entry is active for a `/`-delimited descendant path", () => {
    expect(isWorkNavItemActive("/bk-1/chapters/list-mode", "bk-1", itemByLabel("Chapters"))).toBe(
      true,
    );
    expect(isWorkNavItemActive("/bk-1/facts/some-child", "bk-1", itemByLabel("Facts"))).toBe(true);
  });

  it("DoD-3: an entry is NOT active for a sibling entry's path", () => {
    expect(isWorkNavItemActive("/bk-1/facts", "bk-1", itemByLabel("Book state"))).toBe(false);
    expect(isWorkNavItemActive("/bk-1/variants", "bk-1", itemByLabel("Chapters"))).toBe(false);
    expect(isWorkNavItemActive("/bk-1/locations", "bk-1", itemByLabel("Facts"))).toBe(false);
  });

  it("DoD-3: an entry is NOT active for a bare string prefix of its path", () => {
    // `/chapters-archive` shares a prefix with `/chapters` but is not a
    // `/`-delimited descendant, so the Chapters entry must not match it.
    expect(isWorkNavItemActive("/bk-1/chapters-archive", "bk-1", itemByLabel("Chapters"))).toBe(
      false,
    );
  });

  it("DoD-3: the Chapters entry is active for a single-chapter path (its extra `/chapter` segment)", () => {
    // `/chapter/<id>` is a different segment from `/chapters`, so only the extra
    // active segment can mark Chapters active here.
    expect(isWorkNavItemActive("/bk-1/chapter/ch-1", "bk-1", itemByLabel("Chapters"))).toBe(true);
  });

  it("DoD-3: the Variants entry is active for a per-chapter variants path", () => {
    expect(isWorkNavItemActive("/bk-1/variants/ch-9", "bk-1", itemByLabel("Variants"))).toBe(true);
  });
});
