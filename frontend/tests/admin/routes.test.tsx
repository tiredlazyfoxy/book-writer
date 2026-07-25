/**
 * Admin route table — fast/002.admin-ui-retune, DoD-16.
 *
 * Bound to the frozen signatures in status.md -> `## Skeleton`:
 *   const AdminRoutes   (gained the terminal <Route path="*" element={<NotFoundPage />} />)
 *   const NotFoundPage: FunctionComponent
 *
 * Only the catch-all branch is exercised. The three real pages fetch on mount, so
 * this spec never navigates to `/`, `/llm-servers` or `/database` (plan.md, test
 * notes). Per "Interface intent", `NotFoundPage` holds a heading, a dimmed
 * explanation and exactly one link — a router `Button` back to `/` — so the
 * counts below also prove no route page's content leaked in alongside it.
 *
 * `globals: false`: every primitive is imported explicitly.
 */
import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { AdminRoutes } from "../../src/admin/routes";
import { renderWithProviders } from "../support/render";

describe("AdminRoutes", () => {
  it("DoD-16: an unknown path renders the not-found page and nothing else", () => {
    renderWithProviders(<AdminRoutes />, { route: "/nope" });

    // A heading is present (the not-found page rendered) ...
    expect(screen.getAllByRole("heading").length).toBeGreaterThan(0);
    // ... and the only link in the tree is its own back link, so no route page's
    // content is on screen beside it.
    expect(screen.getAllByRole("link")).toHaveLength(1);
  });

  it("DoD-16: the not-found page offers a link back to `/`", () => {
    renderWithProviders(<AdminRoutes />, { route: "/nope" });

    expect(screen.getByRole("link")).toHaveAttribute("href", "/");
  });
});
