/**
 * Work navigator — collapsed icon-only rail. fast/005.workspace-layout, DoD-8 … DoD-11.
 *
 * Bound to the frozen signatures in status.md -> `## Skeleton` (fast/005):
 *   interface WorkNavigatorProps { bookId: string; onShowChatList: () => void;
 *                                  collapsed?: boolean }   // optional, defaults false
 *   const WorkNavigator = observer(...)
 *
 * Every expected value comes from `plan.md` -> Definition of done + Interface intent,
 * never from code:
 *   - expanded (the default, `collapsed` omitted) is UNCHANGED 010/002 behaviour —
 *     six router-link entries with their visible labels (DoD-8);
 *   - collapsed keeps the same six links reachable BY ACCESSIBLE NAME with the same
 *     hrefs, because every NavLink carries an unconditional `aria-label` (DoD-9);
 *   - collapsed, the Chats entry is still not a link and still invokes
 *     `onShowChatList` — US-105.AC-3 holds in both modes (DoD-10);
 *   - the rail `classNames` are wired only when collapsed (DoD-11).
 *
 * DoD-11 is a DOM CLASS assertion, not a visual one: `vitest.config.ts` leaves
 * `css: false`, so `global.css` resolves to an empty module and the
 * `@media (min-width: 48em)` rules that actually hide the labels never evaluate.
 * The visual rail is `[manual/live]` (DoD-19) by construction.
 *
 * Routes are basename-stripped (`/bk-1/state`, not `/work/bk-1/state`). `globals: false`.
 */
import { describe, expect, it, vi } from "vitest";
import { cleanup, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { WorkNavigator } from "../../src/work/components/shell/WorkNavigator";
import { renderWithProviders } from "../support/render";

/** The six content-pane labels, in UC-090 order — Chats is not among the links. */
const CONTENT_PANE_LABELS = [
  "Book state",
  "Characters",
  "Locations",
  "Facts",
  "Chapters",
  "Variants",
];

/** Label -> its basename-stripped subject href for book `bk-1`. */
const CONTENT_PANE_HREFS: Record<string, string> = {
  "Book state": "/bk-1/state",
  Characters: "/bk-1/characters",
  Locations: "/bk-1/locations",
  Facts: "/bk-1/facts",
  Chapters: "/bk-1/chapters",
  Variants: "/bk-1/variants",
};

/** The three rail slot class names the collapsed mode wires through `classNames`. */
const RAIL_CLASS_NAMES = ["work-nav-rail-root", "work-nav-rail-section", "work-nav-rail-body"];

/** Accessible-name -> href for every link currently rendered. */
function linkHrefsByName(): Record<string, string | null> {
  const map: Record<string, string | null> = {};
  for (const label of CONTENT_PANE_LABELS) {
    map[label] = screen.getByRole("link", { name: label }).getAttribute("href");
  }
  return map;
}

describe("expanded navigator is unchanged (DoD-8)", () => {
  it("DoD-8: with `collapsed` omitted, the six router-link entries render with their visible labels", () => {
    renderWithProviders(<WorkNavigator bookId="bk-1" onShowChatList={vi.fn()} />, {
      route: "/bk-1/state",
    });

    const links = screen.getAllByRole("link");
    expect(links).toHaveLength(6);
    // The visible label text is untouched in expanded mode — the 010/002 regression guard.
    expect(links.map((link) => link.textContent?.trim())).toEqual(CONTENT_PANE_LABELS);
  });
});

describe("collapsed navigator keeps its links (DoD-9)", () => {
  it("DoD-9: collapsed, exactly six links are findable by accessible name", () => {
    renderWithProviders(<WorkNavigator bookId="bk-1" onShowChatList={vi.fn()} collapsed />, {
      route: "/bk-1/state",
    });

    expect(screen.getAllByRole("link")).toHaveLength(6);
    for (const label of CONTENT_PANE_LABELS) {
      expect(screen.getByRole("link", { name: label })).toBeInTheDocument();
    }
  });

  it("DoD-9: collapsed, each link points at the same subject href as in expanded mode", () => {
    renderWithProviders(<WorkNavigator bookId="bk-1" onShowChatList={vi.fn()} />, {
      route: "/bk-1/state",
    });
    const expandedHrefs = linkHrefsByName();
    cleanup();

    renderWithProviders(<WorkNavigator bookId="bk-1" onShowChatList={vi.fn()} collapsed />, {
      route: "/bk-1/state",
    });
    const collapsedHrefs = linkHrefsByName();

    expect(collapsedHrefs).toEqual(expandedHrefs);
    // ...and both agree with the spec's route map.
    expect(collapsedHrefs).toEqual(CONTENT_PANE_HREFS);
  });
});

describe("collapsed Chats entry is still a control (DoD-10)", () => {
  it("DoD-10: collapsed, the Chats entry is not a link and invokes onShowChatList when activated", async () => {
    const user = userEvent.setup();
    const onShowChatList = vi.fn();

    renderWithProviders(
      <WorkNavigator bookId="bk-1" onShowChatList={onShowChatList} collapsed />,
      { route: "/bk-1/state" },
    );

    // Still not a seventh router link, in either mode.
    expect(screen.queryByRole("link", { name: "Chats" })).toBeNull();

    // Reachable by accessible name even though the visible label is hidden by CSS.
    const chats = screen.getByRole("button", { name: "Chats" });
    await user.click(chats);

    expect(onShowChatList).toHaveBeenCalledTimes(1);
  });
});

describe("rail class wiring (DoD-11)", () => {
  it("DoD-11: collapsed, the three rail class names are present on the entries", () => {
    const { container } = renderWithProviders(
      <WorkNavigator bookId="bk-1" onShowChatList={vi.fn()} collapsed />,
      { route: "/bk-1/state" },
    );

    for (const className of RAIL_CLASS_NAMES) {
      expect(container.querySelectorAll(`.${className}`).length).toBeGreaterThan(0);
    }
  });

  it("DoD-11: expanded, none of the three rail class names appears", () => {
    const { container } = renderWithProviders(
      <WorkNavigator bookId="bk-1" onShowChatList={vi.fn()} />,
      { route: "/bk-1/state" },
    );

    for (const className of RAIL_CLASS_NAMES) {
      expect(container.querySelectorAll(`.${className}`).length).toBe(0);
    }
  });
});
