/**
 * Admin AppShell chrome — fast/002.admin-ui-retune, DoD-9..DoD-12 and DoD-15.
 *
 * Bound to the frozen signature in status.md -> `## Skeleton`:
 *   class AdminShellState { navbarOpened = false }
 *   interface AdminShellProps { children: ReactNode }
 *   const AdminShell: FunctionComponent<AdminShellProps>   // observer
 *
 * `AdminShell` is the only new module importing `auth.ts`, so `auth.ts` is the
 * mocked seam here (never `window.location`, never `fetch`). Landmarks come from
 * Mantine: `AppShell.Header` -> `<header>` (banner), `AppShell.Navbar` -> `<nav>`
 * (navigation), `AppShell.Main` -> `<main>` (main).
 *
 * The burger's `data-opened` lives on an inner `<Box>`, so the assertable signal
 * is the `aria-expanded` the component sets on the button (plan.md, test notes).
 *
 * `globals: false`: every primitive is imported explicitly.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { CurrentUser } from "../../src/auth";
import * as auth from "../../src/auth";
import { AdminShell } from "../../src/admin/components/shell/AdminShell";
import { renderWithProviders } from "../support/render";

vi.mock("../../src/auth", () => ({
  getToken: vi.fn(),
  getRefreshToken: vi.fn(),
  setTokens: vi.fn(),
  setAccessToken: vi.fn(),
  getCurrentUser: vi.fn(),
  logout: vi.fn(),
}));

const adminUser: CurrentUser = { user_id: "u-admin", username: "root", role: "admin" };

beforeEach(() => {
  // `restoreMocks` wipes implementations between tests — seed the signed-in admin.
  vi.mocked(auth.getToken).mockReturnValue("admin.access.token");
  vi.mocked(auth.getCurrentUser).mockReturnValue(adminUser);
});

/** Renders the shell around an identifiable child at the router root. */
function renderShell(): void {
  renderWithProviders(
    <AdminShell>
      <div data-testid="page-body">page body</div>
    </AdminShell>,
    { route: "/" },
  );
}

/** The burger, found by the accessible label the plan pins on it. */
function burger(): HTMLElement {
  return screen.getByRole("button", { name: /toggle navigation/i });
}

describe("AdminShell", () => {
  it("DoD-9: exposes exactly one banner, one navigation and one main landmark", () => {
    renderShell();

    expect(screen.getAllByRole("banner")).toHaveLength(1);
    expect(screen.getAllByRole("navigation")).toHaveLength(1);
    expect(screen.getAllByRole("main")).toHaveLength(1);
  });

  it("DoD-9: renders its children inside the main landmark", () => {
    renderShell();

    expect(screen.getByRole("main")).toContainElement(screen.getByTestId("page-body"));
  });

  it("DoD-10: the header shows the `BookWriter — Admin` title", () => {
    renderShell();

    expect(screen.getByText("BookWriter — Admin")).toBeInTheDocument();
  });

  it("DoD-10: the Main site control is a link whose href is exactly `/`", () => {
    renderShell();

    // Regression guard: react-router's basename would have made this `/admin/`.
    expect(screen.getByRole("link", { name: /main site/i })).toHaveAttribute("href", "/");
  });

  it("DoD-11: the burger has an accessible label and starts collapsed", () => {
    renderShell();

    expect(burger()).toBeInTheDocument();
    expect(burger()).toHaveAttribute("aria-expanded", "false");
  });

  it("DoD-11: clicking the burger opens the navbar, clicking again closes it", async () => {
    const user = userEvent.setup();
    renderShell();

    await user.click(burger());
    expect(burger()).toHaveAttribute("aria-expanded", "true");

    await user.click(burger());
    expect(burger()).toHaveAttribute("aria-expanded", "false");
  });

  it("DoD-12: activating a navbar link closes the mobile drawer", async () => {
    const user = userEvent.setup();
    renderShell();

    await user.click(burger());
    expect(burger()).toHaveAttribute("aria-expanded", "true");

    await user.click(screen.getByRole("link", { name: /llm servers/i }));

    expect(burger()).toHaveAttribute("aria-expanded", "false");
  });

  it("DoD-15: activating Logout calls auth.logout() exactly once", async () => {
    const user = userEvent.setup();
    renderShell();

    await user.click(screen.getByRole("button", { name: /root/i }));
    await user.click(screen.getByRole("menuitem", { name: /logout/i }));

    expect(vi.mocked(auth.logout)).toHaveBeenCalledTimes(1);
  });
});
