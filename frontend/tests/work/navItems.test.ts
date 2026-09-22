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

/**
 * The seven labels feature 010 pinned, in the UC-090 order — the entries 026.memos
 * step 009 DoD-1 requires to be UNCHANGED in label and order.
 */
const LEGACY_LABELS = [
  "Book state",
  "Characters",
  "Locations",
  "Facts",
  "Chapters",
  "Variants",
  "Chats",
] as const;

/**
 * The eight author-facing labels as of 026.memos step 009: the seven above, plus
 * **Memos** as the eighth, after Chats (step file -> "Interface intent"; DoD-1).
 */
const EXPECTED_LABELS = [...LEGACY_LABELS, "Memos"] as const;

/** Label -> its basename-stripped subject href for book `bk-1` (from the route map). */
const EXPECTED_HREFS: Record<string, string> = {
  "Book state": "/bk-1/state",
  Characters: "/bk-1/characters",
  Locations: "/bk-1/locations",
  Facts: "/bk-1/facts",
  Chapters: "/bk-1/chapters",
  Variants: "/bk-1/variants",
  Chats: "/bk-1/chats",
  // `context.md` -> the `/work/:bookId/memos` route, basename-stripped.
  Memos: "/bk-1/memos",
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
  // AMENDED by 026.memos step 009 (DoD-1): the table declares an EIGHTH entry, so the
  // seven-entry count and the seven-label list this file used to assert are stale.
  // The 010 contract that survives is the order of the original seven, asserted below
  // and again in the 026 block at the end of this file.
  it("DoD-1 (010) / DoD-1 (026): declares exactly eight entries", () => {
    expect(WORK_NAV_ITEMS).toHaveLength(8);
  });

  it("DoD-1 (010) / DoD-1 (026): the labels are the UC-090 order Book state · Characters · Locations · Facts · Chapters · Variants · Chats · Memos", () => {
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

/* ------------------------------------------------------------------------------------
 * 026.memos / 009.memos-api-and-navigator — the EIGHTH navigator entry.
 * DoD-1 · DoD-2 · DoD-3.
 *
 * Bound to the frozen interface in status.md -> `## Skeleton` (026 step 009):
 *   WORK_NAV_ITEMS gains an eighth entry, LAST, after Chats; `workNavHref` and
 *   `isWorkNavItemActive` are UNCHANGED (an entry with no `extraActiveSegments` was
 *   already the common case).
 *
 * Every expected value comes from the spec, never from code:
 *   - DoD-1 (US-105.AC-7): the entry is labelled **Memos**, is the eighth, sits after
 *     Chats, and the seven existing entries are unchanged in label and order (step
 *     file -> "Interface intent" -> `navItems.ts`);
 *   - DoD-2 (US-105.AC-7): it is an ORDINARY content-pane link — `paneTarget` is
 *     `"content"`, no pane-control exception — and its href resolves under the book id
 *     to the memos segment, like every other entry (`context.md` -> the
 *     `/work/:bookId/memos` route; basename-stripped, `/bk-1/memos`);
 *   - DoD-3 (UC-090 / US-105.AC-7): it is active for the memos path and NOT active for
 *     any sibling entry's path — and no sibling lights up for the memos path either.
 *     There are no `extraActiveSegments`: `/memos` has no item route to light up for
 *     (`context.md` -> decision 12).
 *
 * Items are looked up by their author-facing LABEL, the idiom this file already uses:
 * the skeleton does not freeze the exact `path` string form.
 * ---------------------------------------------------------------------------------- */

describe("WORK_NAV_ITEMS — the Memos entry (026 DoD-1)", () => {
  it("DoD-1: Memos is the eighth entry, last, after Chats", () => {
    const labels = WORK_NAV_ITEMS.map((item) => item.label);

    expect(labels).toHaveLength(8);
    expect(labels[7]).toBe("Memos");
    expect(labels.indexOf("Memos")).toBe(labels.indexOf("Chats") + 1);
  });

  it("DoD-1: the seven existing entries are unchanged in label and order", () => {
    expect(WORK_NAV_ITEMS.slice(0, 7).map((item) => item.label)).toEqual([...LEGACY_LABELS]);
  });
});

describe("workNavHref / paneTarget — Memos is an ordinary content-pane link (026 DoD-2)", () => {
  it("DoD-2: the Memos entry targets the content pane", () => {
    // No pane-control exception: it is a router link like every other entry.
    expect(itemByLabel("Memos").paneTarget).toBe("content");
  });

  it("DoD-2: the Memos href resolves under the book id to the memos segment", () => {
    expect(workNavHref("bk-1", itemByLabel("Memos"))).toBe("/bk-1/memos");
    expect(workNavHref("other-book", itemByLabel("Memos"))).toBe("/other-book/memos");
  });
});

describe("isWorkNavItemActive — Memos (026 DoD-3)", () => {
  it("DoD-3: the Memos entry is active for the memos path", () => {
    expect(isWorkNavItemActive("/bk-1/memos", "bk-1", itemByLabel("Memos"))).toBe(true);
  });

  it("DoD-3: the Memos entry is NOT active for any sibling entry's path", () => {
    for (const label of LEGACY_LABELS) {
      expect(isWorkNavItemActive(EXPECTED_HREFS[label], "bk-1", itemByLabel("Memos"))).toBe(false);
    }
  });

  it("DoD-3: no sibling entry is marked active for the memos path", () => {
    for (const label of LEGACY_LABELS) {
      expect(isWorkNavItemActive("/bk-1/memos", "bk-1", itemByLabel(label))).toBe(false);
    }
  });
});
