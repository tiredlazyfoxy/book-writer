/**
 * Navbar link list — fast/002.admin-ui-retune, DoD-7 and DoD-8.
 *
 * Bound to the frozen signature in status.md -> `## Skeleton`:
 *   interface AdminNavProps { onNavigate?: () => void }
 *   const AdminNav: FunctionComponent<AdminNavProps>   // observer
 *
 * Mantine `NavLink` puts `data-active="true"` on the root `<a>` when active and
 * OMITS the attribute entirely when inactive, so `not.toHaveAttribute("data-active")`
 * is the valid negative assertion (plan.md, test notes). Routes are
 * basename-stripped: `/`, `/llm-servers`, `/database`.
 *
 * `globals: false`: every primitive is imported explicitly.
 */
import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { AdminNav } from "../../src/admin/components/shell/AdminNav";
import { renderWithProviders } from "../support/render";

describe("AdminNav", () => {
  it("DoD-8: renders exactly three links labelled Users / LLM Servers / Database with their hrefs", () => {
    renderWithProviders(<AdminNav />, { route: "/" });

    expect(screen.getAllByRole("link")).toHaveLength(3);
    expect(screen.getByRole("link", { name: /users/i })).toHaveAttribute("href", "/");
    expect(screen.getByRole("link", { name: /llm servers/i })).toHaveAttribute(
      "href",
      "/llm-servers",
    );
    expect(screen.getByRole("link", { name: /database/i })).toHaveAttribute("href", "/database");
  });

  it("DoD-7: at `/database` exactly the Database link is marked active", () => {
    renderWithProviders(<AdminNav />, { route: "/database" });

    expect(screen.getByRole("link", { name: /database/i })).toHaveAttribute("data-active", "true");
    expect(screen.getByRole("link", { name: /users/i })).not.toHaveAttribute("data-active");
    expect(screen.getByRole("link", { name: /llm servers/i })).not.toHaveAttribute("data-active");
    expect(
      screen.getAllByRole("link").filter((link) => link.hasAttribute("data-active")),
    ).toHaveLength(1);
  });

  it("DoD-7: at `/` exactly the Users link is marked active", () => {
    renderWithProviders(<AdminNav />, { route: "/" });

    expect(screen.getByRole("link", { name: /users/i })).toHaveAttribute("data-active", "true");
    expect(screen.getByRole("link", { name: /llm servers/i })).not.toHaveAttribute("data-active");
    expect(screen.getByRole("link", { name: /database/i })).not.toHaveAttribute("data-active");
    expect(
      screen.getAllByRole("link").filter((link) => link.hasAttribute("data-active")),
    ).toHaveLength(1);
  });
});
