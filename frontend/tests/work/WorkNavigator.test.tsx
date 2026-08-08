/**
 * Work navigator — all seven entries are content-pane links.
 * Retargeted by 023.chat-ux-revision (design-note D12), DoD-8.
 *
 * This spec previously asserted 011's arrangement — six router links plus a Chats
 * CONTROL that revealed the pane's list without navigating. 023 inverts that
 * deliberately, so the file is rewritten against the new contract rather than
 * weakened to keep the old one passing.
 *
 * Bound to the frozen signatures in status.md -> `## Skeleton` (023):
 *   interface WorkNavigatorProps { bookId: string; collapsed?: boolean }
 *   const WorkNavigator = observer(...)   // `onShowChatList` is GONE
 *
 * Expected values come from the SPEC -- `plan.md` -> DoD-8 and its Interface section
 * for `WorkNavigator.tsx` / `navItems.ts` ("all seven entries render identically as
 * `<NavLink component={RouterLink} to={workNavHref(bookId, item)}/>`", the Chats
 * entry's `paneTarget` becomes `"content"`) plus the 010 route map for the seven
 * labels and hrefs -- never from code. `plan.md` -> DoD-8 records that this
 * knowingly contradicts US-105.AC-3 / US-095.AC-1 / UC-081 step 1; `outcome.md`
 * item 1 carries the reconciliation.
 *
 * Routes are basename-stripped (`/bk-1/state`, not `/work/bk-1/state`); a
 * `LocationProbe` makes the router path observable so the Chats entry's NAVIGATION is
 * asserted directly. `globals: false`.
 */
import type { ReactElement } from "react";
import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useLocation } from "react-router-dom";
import { WorkNavigator } from "../../src/work/components/shell/WorkNavigator";
import { renderWithProviders } from "../support/render";

/** The seven author-facing labels, in UC-090 order — Chats is now among the links. */
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

/** Reports the router's current pathname, so navigation is observable. */
function LocationProbe(): ReactElement {
  const location = useLocation();
  return <span data-testid="pathname">{location.pathname}</span>;
}

describe("every navigator entry is a content-pane link (DoD-8)", () => {
  it("DoD-8: renders all seven entries as links in UC-090 order — Chats included", () => {
    renderWithProviders(<WorkNavigator bookId="bk-1" />, { route: "/bk-1/state" });

    const links = screen.getAllByRole("link");
    expect(links).toHaveLength(7);
    expect(links.map((link) => link.textContent?.trim())).toEqual(NAV_LABELS);
  });

  it("DoD-8: each entry is an in-SPA router link to its own subject path under the book id", () => {
    renderWithProviders(<WorkNavigator bookId="bk-1" />, { route: "/bk-1/state" });

    for (const label of NAV_LABELS) {
      expect(screen.getByRole("link", { name: label })).toHaveAttribute("href", NAV_HREFS[label]);
    }
  });
});

describe("the Chats entry navigates to the chats route (DoD-8)", () => {
  it("DoD-8: activating Chats moves the content route to /:bookId/chats (the inversion of 011's contract)", async () => {
    const user = userEvent.setup();

    renderWithProviders(
      <>
        <WorkNavigator bookId="bk-1" />
        <LocationProbe />
      </>,
      { route: "/bk-1/state" },
    );

    expect(screen.getByTestId("pathname").textContent).toBe("/bk-1/state");

    await user.click(screen.getByRole("link", { name: "Chats" }));

    // Chats is no longer a pane-state reveal: it is a route change like every sibling.
    expect(screen.getByTestId("pathname").textContent).toBe("/bk-1/chats");
  });
});
