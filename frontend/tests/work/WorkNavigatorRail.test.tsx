/**
 * Work navigator — collapsed icon-only rail. fast/005.workspace-layout, DoD-8 … DoD-11.
 * Retargeted by 023.chat-ux-revision (design-note D12's category), 023 DoD-8.
 *
 * WHAT CHANGED, AND WHAT DID NOT. fast/005 shipped this spec against 011's
 * arrangement: six router links plus a Chats CONTROL that revealed the pane's list in
 * both modes. 023 makes the Chats entry a plain content-pane link in EVERY state
 * (`plan.md` -> Interface -> `WorkNavigator.tsx`: "all seven entries render identically
 * as `<NavLink component={RouterLink} to={workNavHref(bookId, item)}/>` — no
 * `paneTarget`-based branching left in the body"; `navItems.ts`: the Chats entry's
 * `paneTarget` becomes `"content"`). So the entry counts become seven and the
 * Chats-opens-the-aside expectation flips to a link + href assertion. Everything this
 * spec says about THE RAIL ITSELF — accessible-name reachability while collapsed,
 * href parity between the two modes, and the `classNames` wiring — is preserved
 * unchanged; that is fast/005's own behaviour and 023 does not touch it.
 *
 * Bound to the frozen signatures in status.md -> `## Skeleton` (023):
 *   interface WorkNavigatorProps { bookId: string; collapsed?: boolean }
 *                                  // `onShowChatList` is GONE; `collapsed` defaults false
 *   const WorkNavigator = observer(...)
 *
 * Every expected value comes from the spec — fast/005's `plan.md` -> Definition of
 * done + Interface intent for the rail, and 023's `plan.md` -> DoD-8 + Interface for
 * the entry set — never from code:
 *   - expanded (the default, `collapsed` omitted) renders the seven entries as router
 *     links with their visible labels (DoD-8);
 *   - collapsed keeps the same seven links reachable BY ACCESSIBLE NAME with the same
 *     hrefs, because every NavLink carries an unconditional `aria-label` (DoD-9);
 *   - collapsed, the Chats entry is a link to `/:bookId/chats` like every sibling —
 *     023 DoD-8 inverts US-105.AC-3 by design, and it holds in both modes (DoD-10);
 *   - the rail `classNames` are wired only when collapsed (DoD-11).
 *
 * DoD-11 is a DOM CLASS assertion, not a visual one: `vitest.config.ts` leaves
 * `css: false`, so `global.css` resolves to an empty module and the
 * `@media (min-width: 48em)` rules that actually hide the labels never evaluate.
 * The visual rail is `[manual/live]` (DoD-19) by construction.
 *
 * Routes are basename-stripped (`/bk-1/state`, not `/work/bk-1/state`). `globals: false`.
 */
import { describe, expect, it } from "vitest";
import { cleanup, screen } from "@testing-library/react";
import { WorkNavigator } from "../../src/work/components/shell/WorkNavigator";
import { renderWithProviders } from "../support/render";

/** The seven navigator labels, in UC-090 order — Chats is now among the links. */
const NAV_LABELS = [
  "Book state",
  "Characters",
  "Locations",
  "Facts",
  "Chapters",
  "Variants",
  "Chats",
];

/** Label -> its basename-stripped subject href for book `bk-1`. */
const NAV_HREFS: Record<string, string> = {
  "Book state": "/bk-1/state",
  Characters: "/bk-1/characters",
  Locations: "/bk-1/locations",
  Facts: "/bk-1/facts",
  Chapters: "/bk-1/chapters",
  Variants: "/bk-1/variants",
  Chats: "/bk-1/chats",
};

/** The three rail slot class names the collapsed mode wires through `classNames`. */
const RAIL_CLASS_NAMES = ["work-nav-rail-root", "work-nav-rail-section", "work-nav-rail-body"];

/** Accessible-name -> href for every link currently rendered. */
function linkHrefsByName(): Record<string, string | null> {
  const map: Record<string, string | null> = {};
  for (const label of NAV_LABELS) {
    map[label] = screen.getByRole("link", { name: label }).getAttribute("href");
  }
  return map;
}

describe("expanded navigator renders every entry as a link (DoD-8)", () => {
  it("DoD-8: with `collapsed` omitted, the seven router-link entries render with their visible labels", () => {
    renderWithProviders(<WorkNavigator bookId="bk-1" />, {
      route: "/bk-1/state",
    });

    const links = screen.getAllByRole("link");
    expect(links).toHaveLength(7);
    // The visible label text is untouched in expanded mode — the 010/002 regression guard.
    expect(links.map((link) => link.textContent?.trim())).toEqual(NAV_LABELS);
  });
});

describe("collapsed navigator keeps its links (DoD-9)", () => {
  it("DoD-9: collapsed, exactly seven links are findable by accessible name", () => {
    renderWithProviders(<WorkNavigator bookId="bk-1" collapsed />, {
      route: "/bk-1/state",
    });

    expect(screen.getAllByRole("link")).toHaveLength(7);
    for (const label of NAV_LABELS) {
      expect(screen.getByRole("link", { name: label })).toBeInTheDocument();
    }
  });

  it("DoD-9: collapsed, each link points at the same subject href as in expanded mode", () => {
    renderWithProviders(<WorkNavigator bookId="bk-1" />, {
      route: "/bk-1/state",
    });
    const expandedHrefs = linkHrefsByName();
    cleanup();

    renderWithProviders(<WorkNavigator bookId="bk-1" collapsed />, {
      route: "/bk-1/state",
    });
    const collapsedHrefs = linkHrefsByName();

    expect(collapsedHrefs).toEqual(expandedHrefs);
    // ...and both agree with the spec's route map.
    expect(collapsedHrefs).toEqual(NAV_HREFS);
  });
});

describe("collapsed Chats entry is a content-pane link too (DoD-10, retargeted by 023 DoD-8)", () => {
  it("DoD-10: collapsed, the Chats entry is a link to /:bookId/chats, reachable by accessible name", () => {
    renderWithProviders(<WorkNavigator bookId="bk-1" collapsed />, { route: "/bk-1/state" });

    // Reachable by accessible name even though the visible label is hidden by CSS...
    const chats = screen.getByRole("link", { name: "Chats" });
    // ...and it is a router link like every sibling: no pane-reveal control survives
    // in either mode (023 DoD-8 inverts 011's US-105.AC-3 arrangement by design).
    expect(chats).toHaveAttribute("href", "/bk-1/chats");
    expect(screen.queryByRole("button", { name: "Chats" })).toBeNull();
  });
});

describe("rail class wiring (DoD-11)", () => {
  it("DoD-11: collapsed, the three rail class names are present on the entries", () => {
    const { container } = renderWithProviders(
      <WorkNavigator bookId="bk-1" collapsed />,
      { route: "/bk-1/state" },
    );

    for (const className of RAIL_CLASS_NAMES) {
      expect(container.querySelectorAll(`.${className}`).length).toBeGreaterThan(0);
    }
  });

  it("DoD-11: expanded, none of the three rail class names appears", () => {
    const { container } = renderWithProviders(
      <WorkNavigator bookId="bk-1" />,
      { route: "/bk-1/state" },
    );

    for (const className of RAIL_CLASS_NAMES) {
      expect(container.querySelectorAll(`.${className}`).length).toBe(0);
    }
  });
});
