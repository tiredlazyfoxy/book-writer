/**
 * User chip + menu — fast/002.admin-ui-retune, DoD-13 and DoD-14.
 *
 * Bound to the frozen signature in status.md -> `## Skeleton`:
 *   interface AdminUserMenuProps { user: CurrentUser | null; onLogout: () => void }
 *   const AdminUserMenu: FunctionComponent<AdminUserMenuProps>   // observer
 *
 * Pure props, so this spec needs no module mock at all — a `vi.fn()` is the whole
 * logout seam. `MantineProvider env="test"` means the opened dropdown renders
 * inline and synchronously: no portal lookup, no `waitFor`. Interactions go
 * through `user-event` because Mantine's `Popover` target needs the full pointer
 * sequence.
 *
 * `globals: false`: every primitive is imported explicitly.
 */
import { describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { CurrentUser } from "../../src/auth";
import { AdminUserMenu } from "../../src/admin/components/shell/AdminUserMenu";
import { renderWithProviders } from "../support/render";

const adminUser: CurrentUser = { user_id: "u-admin", username: "root", role: "admin" };

describe("AdminUserMenu", () => {
  it("DoD-13: shows the username and the role in the menu target", () => {
    renderWithProviders(<AdminUserMenu user={adminUser} onLogout={vi.fn()} />);

    const target = screen.getByRole("button", { name: /root/i });
    expect(target).toHaveTextContent(/root/);
    expect(target).toHaveTextContent(/admin/i);
  });

  it("DoD-13: renders nothing when the user prop is null", () => {
    renderWithProviders(
      <div data-testid="user-menu-host">
        <AdminUserMenu user={null} onLogout={vi.fn()} />
      </div>,
    );

    expect(screen.getByTestId("user-menu-host")).toBeEmptyDOMElement();
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("DoD-14: opening the menu reveals Logout and a disabled Change password", async () => {
    const user = userEvent.setup();
    renderWithProviders(<AdminUserMenu user={adminUser} onLogout={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: /root/i }));

    expect(screen.getByRole("menuitem", { name: /logout/i })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: /change password/i })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: /change password/i })).toBeDisabled();
  });

  it("DoD-14: clicking Logout invokes the onLogout callback exactly once", async () => {
    const user = userEvent.setup();
    const onLogout = vi.fn();
    renderWithProviders(<AdminUserMenu user={adminUser} onLogout={onLogout} />);

    await user.click(screen.getByRole("button", { name: /root/i }));
    await user.click(screen.getByRole("menuitem", { name: /logout/i }));

    expect(onLogout).toHaveBeenCalledTimes(1);
  });

  it("DoD-14: clicking the disabled Change password item invokes nothing", async () => {
    const user = userEvent.setup();
    const onLogout = vi.fn();
    renderWithProviders(<AdminUserMenu user={adminUser} onLogout={onLogout} />);

    await user.click(screen.getByRole("button", { name: /root/i }));
    await user.click(screen.getByRole("menuitem", { name: /change password/i }));

    expect(onLogout).not.toHaveBeenCalled();
  });
});
