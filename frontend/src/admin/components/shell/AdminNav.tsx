import { observer } from "mobx-react-lite";
import { NavLink, Stack } from "@mantine/core";
import { Link as RouterLink, useLocation } from "react-router-dom";
import { ADMIN_NAV_ITEMS, isNavItemActive } from "./navItems";

export interface AdminNavProps {
  /**
   * Fired when a nav item is activated. `AdminShell` passes a callback that
   * closes the mobile drawer; standalone renders may omit it.
   */
  onNavigate?: () => void;
}

/**
 * The navbar's Mantine `NavLink` list — the **only** `useLocation()` call in the
 * shell. Maps `ADMIN_NAV_ITEMS` to `NavLink`s rendered `component={RouterLink}`
 * with `to` / `label` / `leftSection` / `active={isNavItemActive(pathname, item)}`
 * and an `onClick` that fires `onNavigate`. No state, no MobX fields.
 *
 * `useLocation()` is react-router's own hook reading router context (the URL,
 * which react-router owns) — not a custom `useX` hook and not reactive app
 * state, so it does not violate the no-custom-hooks rule. It is required:
 * without it nothing re-renders on navigation. `useMatch` is rejected (one call
 * per item = a hook in a loop); `component={RouterNavLink}` is rejected (it
 * cannot set Mantine's `active` prop, gives zero visual change since no
 * `.active` CSS exists, and would create two sources of truth for one boolean).
 */
export const AdminNav = observer(function AdminNav({ onNavigate }: AdminNavProps) {
  // One call for the whole list (never one per item — that would be a hook in a loop).
  const { pathname } = useLocation();

  return (
    <Stack gap={4}>
      {ADMIN_NAV_ITEMS.map((item) => {
        const ItemIcon = item.icon;
        return (
          <NavLink
            key={item.path}
            component={RouterLink}
            to={item.path}
            label={item.label}
            leftSection={<ItemIcon size={18} stroke={1.5} />}
            active={isNavItemActive(pathname, item)}
            onClick={onNavigate}
          />
        );
      })}
    </Stack>
  );
});
