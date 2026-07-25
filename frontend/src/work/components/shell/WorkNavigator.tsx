import { observer } from "mobx-react-lite";
import { NavLink, Stack } from "@mantine/core";
import { Link as RouterLink, useLocation } from "react-router-dom";
import { WORK_NAV_ITEMS, isWorkNavItemActive, workNavHref } from "./navItems";

export interface WorkNavigatorProps {
  /** The book id the entries are scoped to (from `/work/:bookId`). */
  bookId: string;
}

/**
 * The work SPA's left-hand navigator: renders the seven `WORK_NAV_ITEMS` as
 * in-SPA react-router links under the current book id, marking the active one via
 * `isWorkNavItemActive`. No data loading, no MobX fields (mirrors `AdminNav`).
 *
 * `useLocation()` is react-router's own hook reading the URL it owns (not a custom
 * `useX` hook, not reactive app state), called once for the whole list — never one
 * per item, which would be a hook in a loop.
 */
export const WorkNavigator = observer(function WorkNavigator({ bookId }: WorkNavigatorProps) {
  const { pathname } = useLocation();

  return (
    <Stack gap={4}>
      {WORK_NAV_ITEMS.map((item) => {
        const ItemIcon = item.icon;
        return (
          <NavLink
            key={item.path}
            component={RouterLink}
            to={workNavHref(bookId, item)}
            label={item.label}
            leftSection={<ItemIcon size={18} stroke={1.5} />}
            active={isWorkNavItemActive(pathname, bookId, item)}
          />
        );
      })}
    </Stack>
  );
});
