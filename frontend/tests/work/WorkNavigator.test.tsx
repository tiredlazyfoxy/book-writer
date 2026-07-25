/**
 * Work navigator render — 010.working-page / 002.workspace-shell, DoD-1 · DoD-2.
 *
 * Bound to the frozen signatures in status.md -> `## Skeleton` (step 002):
 *   interface WorkNavigatorProps { bookId: string }
 *   const WorkNavigator: FunctionComponent<WorkNavigatorProps>   // observer
 *
 * `WorkNavigator` reads the current pathname from the router to mark the active
 * entry, so it is rendered under a router (the `route` option seeds a
 * MemoryRouter). Routes are basename-stripped — production's `basename="/work"`
 * never appears — so the entry hrefs are `/bk-1/<segment>` (DoD-2), the same
 * subject paths the route map declares.
 *
 * Expected labels + hrefs come from the spec (DoD-1 list / `context.md` route
 * map), never from code.
 *
 * `globals: false`: every primitive is imported explicitly.
 */
import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { WorkNavigator } from "../../src/work/components/shell/WorkNavigator";
import { renderWithProviders } from "../support/render";

/** The seven author-facing labels, in UC-090 order. */
const EXPECTED_LABELS = [
  "Book state",
  "Characters",
  "Locations",
  "Facts",
  "Chapters",
  "Variants",
  "Chats",
];

/** Label -> its basename-stripped subject href for book `bk-1`. */
const EXPECTED_HREFS: Record<string, string> = {
  "Book state": "/bk-1/state",
  Characters: "/bk-1/characters",
  Locations: "/bk-1/locations",
  Facts: "/bk-1/facts",
  Chapters: "/bk-1/chapters",
  Variants: "/bk-1/variants",
  Chats: "/bk-1/chats",
};

describe("WorkNavigator", () => {
  it("DoD-1: renders exactly seven entries in UC-090 order with their author-facing labels", () => {
    renderWithProviders(<WorkNavigator bookId="bk-1" />, { route: "/bk-1/state" });

    const links = screen.getAllByRole("link");
    expect(links).toHaveLength(7);
    expect(links.map((link) => link.textContent?.trim())).toEqual(EXPECTED_LABELS);
  });

  it("DoD-2: each entry is an in-SPA router link to its own subject path under the book id", () => {
    renderWithProviders(<WorkNavigator bookId="bk-1" />, { route: "/bk-1/state" });

    for (const label of EXPECTED_LABELS) {
      expect(screen.getByRole("link", { name: label })).toHaveAttribute("href", EXPECTED_HREFS[label]);
    }
  });
});
