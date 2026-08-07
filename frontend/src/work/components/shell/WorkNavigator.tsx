import { observer } from "mobx-react-lite";
import { NavLink, Stack, Tooltip } from "@mantine/core";
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
  /**
   * Desktop icon-rail mode (fast/005). OPTIONAL, defaulting to `false` — making it
   * required would break the existing call sites and `npm run test:types`. When
   * set, each entry is wrapped in a right-positioned `Tooltip` carrying its label
   * and the `NavLink` gets the `work-nav-rail-*` `classNames`; the label hiding
   * itself is CSS (`global.css`, inside `@media (min-width: 48em)`), never JS, so
   * the full-width mobile drawer keeps its labels.
   */
  collapsed?: boolean;
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
 * fast/005: `collapsed` turns the list into an icon-only rail. The labels are
 * hidden by CSS (`global.css`, inside `@media (min-width: 48em)`) via the
 * `work-nav-rail-*` `classNames`, never by dropping the `label` prop — Mantine's
 * `NavLink` always renders the body span, so dropping the label would leave an
 * empty flex spacer that left-shifts the icon, and a JS boolean cannot be
 * breakpoint-aware without the repo-wide-banned `useMediaQuery`, which would blank
 * the full-width mobile drawer too.
 */
export const WorkNavigator = observer(function WorkNavigator({
  bookId,
  onShowChatList,
  collapsed = false,
}: WorkNavigatorProps) {
  const { pathname } = useLocation();

  return (
    <Stack gap={4}>
      {WORK_NAV_ITEMS.map((item) => {
        const ItemIcon = item.icon;
        const railClassNames = collapsed
          ? {
              root: "work-nav-rail-root",
              section: "work-nav-rail-section",
              body: "work-nav-rail-body",
            }
          : undefined;

        // `aria-label` is set UNCONDITIONALLY, in both modes: Mantine spreads
        // unknown props onto the root element, so it keeps the entry findable by
        // accessible name once CSS hides the visible label, and leaves
        // `textContent` untouched when the label is visible.
        const entry =
          // The sole `paneTarget: "chat"` entry (Chats) is a control over the chat
          // pane, NOT a router link (US-105.AC-3 / DoD-5): a `<button>` NavLink
          // that opens the pane's list and leaves the URL untouched.
          item.paneTarget === "chat" ? (
            <NavLink
              key={item.path}
              component="button"
              type="button"
              label={item.label}
              aria-label={item.label}
              leftSection={<ItemIcon size={18} stroke={1.5} />}
              onClick={onShowChatList}
              classNames={railClassNames}
            />
          ) : (
            <NavLink
              key={item.path}
              component={RouterLink}
              to={workNavHref(bookId, item)}
              label={item.label}
              aria-label={item.label}
              leftSection={<ItemIcon size={18} stroke={1.5} />}
              active={isWorkNavItemActive(pathname, bookId, item)}
              classNames={railClassNames}
            />
          );

        if (!collapsed) return entry;

        // In the rail the label is the only thing identifying the icon, so it
        // comes back on hover.
        return (
          <Tooltip key={item.path} label={item.label} position="right" withArrow openDelay={200}>
            {entry}
          </Tooltip>
        );
      })}
    </Stack>
  );
});
