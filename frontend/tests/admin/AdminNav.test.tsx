/**
 * Navbar link list — fast/002.admin-ui-retune, DoD-7 and DoD-8, EXTENDED by
 * 012.assistant-config-editor / 006.frontend-api-and-nav, DoD-2.
 *
 * Bound to the frozen signature in status.md -> `## Skeleton`:
 *   interface AdminNavProps { onNavigate?: () => void }
 *   const AdminNav: FunctionComponent<AdminNavProps>   // observer
 *
 * Mantine `NavLink` puts `data-active="true"` on the root `<a>` when active and
 * OMITS the attribute entirely when inactive, so `not.toHaveAttribute("data-active")`
 * is the valid negative assertion (plan.md, test notes). Routes are
 * basename-stripped: `/`, `/llm-servers`, `/database`, `/assistant-modes`,
 * `/sub-agents`.
 *
 * 012/006 DoD-2 requires the rendered-nav assertions to COVER the two new entries
 * alongside the existing ones and to stay **pinned rather than sampled** — so the
 * link count is extended 3 -> 5 and every label/href is still asserted by name,
 * never with a `.some()` or a subset match. Expected labels and hrefs come from
 * `006.frontend-api-and-nav.md` -> "Interface intent" + DoD-1 (UC-095 step 1,
 * UC-097 step 1), not from the component.
 *
 * `globals: false`: every primitive is imported explicitly.
 */
import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { AdminNav } from "../../src/admin/components/shell/AdminNav";
import { renderWithProviders } from "../support/render";

describe("AdminNav", () => {
  it("DoD-8 / 012-006 DoD-2: renders exactly five links labelled Users / LLM Servers / Database / Assistant modes / Sub-agents with their hrefs", () => {
    renderWithProviders(<AdminNav />, { route: "/" });

    expect(screen.getAllByRole("link")).toHaveLength(5);
    expect(screen.getByRole("link", { name: /users/i })).toHaveAttribute("href", "/");
    expect(screen.getByRole("link", { name: /llm servers/i })).toHaveAttribute(
      "href",
      "/llm-servers",
    );
    expect(screen.getByRole("link", { name: /database/i })).toHaveAttribute("href", "/database");
    expect(screen.getByRole("link", { name: /assistant modes/i })).toHaveAttribute(
      "href",
      "/assistant-modes",
    );
    expect(screen.getByRole("link", { name: /sub-agents/i })).toHaveAttribute(
      "href",
      "/sub-agents",
    );
  });

  it("DoD-7 / 012-006 DoD-2: at `/database` exactly the Database link is marked active", () => {
    renderWithProviders(<AdminNav />, { route: "/database" });

    expect(screen.getByRole("link", { name: /database/i })).toHaveAttribute("data-active", "true");
    expect(screen.getByRole("link", { name: /users/i })).not.toHaveAttribute("data-active");
    expect(screen.getByRole("link", { name: /llm servers/i })).not.toHaveAttribute("data-active");
    expect(screen.getByRole("link", { name: /assistant modes/i })).not.toHaveAttribute(
      "data-active",
    );
    expect(screen.getByRole("link", { name: /sub-agents/i })).not.toHaveAttribute("data-active");
    expect(
      screen.getAllByRole("link").filter((link) => link.hasAttribute("data-active")),
    ).toHaveLength(1);
  });

  it("DoD-7 / 012-006 DoD-2: at `/` exactly the Users link is marked active", () => {
    renderWithProviders(<AdminNav />, { route: "/" });

    expect(screen.getByRole("link", { name: /users/i })).toHaveAttribute("data-active", "true");
    expect(screen.getByRole("link", { name: /llm servers/i })).not.toHaveAttribute("data-active");
    expect(screen.getByRole("link", { name: /database/i })).not.toHaveAttribute("data-active");
    expect(screen.getByRole("link", { name: /assistant modes/i })).not.toHaveAttribute(
      "data-active",
    );
    expect(screen.getByRole("link", { name: /sub-agents/i })).not.toHaveAttribute("data-active");
    expect(
      screen.getAllByRole("link").filter((link) => link.hasAttribute("data-active")),
    ).toHaveLength(1);
  });

  it("012-006 DoD-2: at `/assistant-modes` exactly the Assistant modes link is marked active", () => {
    renderWithProviders(<AdminNav />, { route: "/assistant-modes" });

    expect(screen.getByRole("link", { name: /assistant modes/i })).toHaveAttribute(
      "data-active",
      "true",
    );
    expect(screen.getByRole("link", { name: /sub-agents/i })).not.toHaveAttribute("data-active");
    expect(screen.getByRole("link", { name: /users/i })).not.toHaveAttribute("data-active");
    expect(screen.getByRole("link", { name: /llm servers/i })).not.toHaveAttribute("data-active");
    expect(screen.getByRole("link", { name: /database/i })).not.toHaveAttribute("data-active");
    expect(
      screen.getAllByRole("link").filter((link) => link.hasAttribute("data-active")),
    ).toHaveLength(1);
  });

  it("012-006 DoD-2: at `/sub-agents` exactly the Sub-agents link is marked active", () => {
    renderWithProviders(<AdminNav />, { route: "/sub-agents" });

    expect(screen.getByRole("link", { name: /sub-agents/i })).toHaveAttribute(
      "data-active",
      "true",
    );
    expect(screen.getByRole("link", { name: /assistant modes/i })).not.toHaveAttribute(
      "data-active",
    );
    expect(screen.getByRole("link", { name: /users/i })).not.toHaveAttribute("data-active");
    expect(screen.getByRole("link", { name: /llm servers/i })).not.toHaveAttribute("data-active");
    expect(screen.getByRole("link", { name: /database/i })).not.toHaveAttribute("data-active");
    expect(
      screen.getAllByRole("link").filter((link) => link.hasAttribute("data-active")),
    ).toHaveLength(1);
  });
});
