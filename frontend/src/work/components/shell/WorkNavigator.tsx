import { observer } from "mobx-react-lite";
import { NavLink, Stack } from "@mantine/core";
import { Link as RouterLink, useLocation } from "react-router-dom";
import { WORK_NAV_ITEMS, isWorkNavItemActive, workNavHref } from "./navItems";

export interface WorkNavigatorProps {
  /** The book id the entries are scoped to (from `/work/:bookId`). */
  bookId: string;
  /**
   * Opens the chat pane's list (011/004). The entry whose frozen `paneTarget` is
   * `"chat"` (Chats) renders a control that calls this instead of a router link;
   * the six `"content"` entries stay in-SPA links. Wired by the coder.
   */
  onShowChatList: () => void;
}

/**
 * The work SPA's left-hand navigator: renders the seven `WORK_NAV_ITEMS`. The six
 * `paneTarget: "content"` entries are in-SPA react-router links under the current
 * book id, marking the active one via `isWorkNavItemActive`; the sole
 * `paneTarget: "chat"` entry (Chats) renders a control that calls `onShowChatList`
 * and does NOT navigate (011/004). No data loading, no MobX fields (mirrors
 * `AdminNav`).
 *
 * `useLocation()` is react-router's own hook reading the URL it owns (not a custom
 * `useX` hook, not reactive app state), called once for the whole list — never one
 * per item, which would be a hook in a loop.
 *
 * SKELETON (011/004): the `onShowChatList` prop is frozen; the body still renders
 * every entry as a link (010 behaviour preserved) — routing the `"chat"` entry to
 * the control is the DoD-5 behaviour the coder fills.
 */
export const WorkNavigator = observer(function WorkNavigator({
  bookId,
  onShowChatList,
}: WorkNavigatorProps) {
  const { pathname } = useLocation();

  return (
    <Stack gap={4}>
      {WORK_NAV_ITEMS.map((item) => {
        const ItemIcon = item.icon;

        // The sole `paneTarget: "chat"` entry (Chats) is a control over the chat
        // pane, NOT a router link (US-105.AC-3 / DoD-5): a `<button>` NavLink that
        // opens the pane's list and leaves the URL untouched.
        if (item.paneTarget === "chat") {
          return (
            <NavLink
              key={item.path}
              component="button"
              type="button"
              label={item.label}
              leftSection={<ItemIcon size={18} stroke={1.5} />}
              onClick={onShowChatList}
            />
          );
        }

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
