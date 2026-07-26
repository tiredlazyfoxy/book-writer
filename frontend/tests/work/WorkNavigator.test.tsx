/**
 * Work navigator — six content entries stay links, the Chats entry becomes a
 * pane control. 011.chat-panel / 004.chat-pane-list-and-settings, DoD-5.
 *
 * Originally a 010.working-page test (seven router links). DoD-5 changes the
 * contract, so this test is re-bound to the frozen step-004 skeleton
 * (status.md -> `## Skeleton`, step 004):
 *   interface WorkNavigatorProps { bookId: string; onShowChatList: () => void }
 *   const WorkNavigator = observer(...)   // reads the pathname to mark the active entry
 * `onShowChatList` is REQUIRED, so every render supplies it. The entry whose
 * frozen `paneTarget` is `"chat"` (Chats) stops being a router link and becomes a
 * control that reveals the pane's list.
 *
 * Expected values come from the spec — `004.md` DoD-5, `004.context.md` -> "Why the
 * navigator entry is a control, not a link" (US-095.AC-1 / UC-081 step 1 /
 * US-105.AC-3), and the 010 route map for the six content-pane labels + hrefs that
 * remain true — never from code:
 *   - the six content-pane entries (Book state, Characters, Locations, Facts,
 *     Chapters, Variants) still render as in-SPA router links to their subject paths,
 *     in UC-090 order;
 *   - the Chats entry is NOT a seventh router link — it is a control that, when
 *     activated, calls `onShowChatList` and does not navigate.
 *
 * Routes are basename-stripped (`/bk-1/state`, not `/work/bk-1/state`); a
 * `LocationProbe` makes the router path observable so the lack of navigation on the
 * Chats control is asserted directly. `globals: false`.
 */
import type { ReactElement } from "react";
import { describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useLocation } from "react-router-dom";
import { WorkNavigator } from "../../src/work/components/shell/WorkNavigator";
import { renderWithProviders } from "../support/render";

/** The six content-pane labels, in UC-090 order — Chats is no longer among the links. */
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

/** Reports the router's current pathname, so navigation (or the lack of it) is observable. */
function LocationProbe(): ReactElement {
  const location = useLocation();
  return <span data-testid="pathname">{location.pathname}</span>;
}

describe("WorkNavigator content-pane entries (DoD-5)", () => {
  it("DoD-5: renders exactly the six content-pane entries as links in UC-090 order — Chats is not among them", () => {
    renderWithProviders(<WorkNavigator bookId="bk-1" onShowChatList={vi.fn()} />, {
      route: "/bk-1/state",
    });

    const links = screen.getAllByRole("link");
    expect(links).toHaveLength(6);
    expect(links.map((link) => link.textContent?.trim())).toEqual(CONTENT_PANE_LABELS);
  });

  it("DoD-5: each content-pane entry is an in-SPA router link to its own subject path under the book id", () => {
    renderWithProviders(<WorkNavigator bookId="bk-1" onShowChatList={vi.fn()} />, {
      route: "/bk-1/state",
    });

    for (const label of CONTENT_PANE_LABELS) {
      expect(screen.getByRole("link", { name: label })).toHaveAttribute(
        "href",
        CONTENT_PANE_HREFS[label],
      );
    }
  });
});

describe("WorkNavigator Chats entry is a control, not a link (DoD-5)", () => {
  it("DoD-5: the Chats entry is a control — not a router link — that reveals the list without navigating (US-105.AC-3)", async () => {
    const user = userEvent.setup();
    const onShowChatList = vi.fn();

    renderWithProviders(
      <>
        <WorkNavigator bookId="bk-1" onShowChatList={onShowChatList} />
        <LocationProbe />
      </>,
      { route: "/bk-1/state" },
    );

    // The Chats entry exists in the navigator but is NOT a seventh router link.
    expect(screen.getByText("Chats")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Chats" })).toBeNull();
    expect(screen.getByTestId("pathname").textContent).toBe("/bk-1/state");

    await user.click(screen.getByText("Chats"));

    // Activating it reveals the pane's list (a pane-state call), not a route change.
    expect(onShowChatList).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId("pathname").textContent).toBe("/bk-1/state");
  });
});
