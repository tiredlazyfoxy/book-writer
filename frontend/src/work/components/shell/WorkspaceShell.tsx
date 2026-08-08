import { useEffect, useState } from "react";
import { observer } from "mobx-react-lite";
import { autorun } from "mobx";
import { Outlet, useParams } from "react-router-dom";
import { ActionIcon, Alert, AppShell, Burger, Group, Loader, Title, Tooltip } from "@mantine/core";
import { IconPinned, IconPinnedOff } from "@tabler/icons-react";
import { WorkNavigator } from "./WorkNavigator";
import { ChatPaneSlot } from "./ChatPaneSlot";
import { ChatResizeHandle } from "./ChatResizeHandle";
import {
  WorkspaceShellState,
  endChatResize,
  loadWorkspaceBook,
  toggleNavCollapsed,
} from "./workspaceShellState";
import {
  ChatPaneState,
  loadChatMessages,
  loadChatPane,
  pickChat,
  stopChatTurn,
} from "../chat/chatPaneState";
import {
  registerCloseTurnController,
  unregisterCloseTurnController,
} from "../../closeTurn";
import {
  registerChatPaneController,
  unregisterChatPaneController,
  type ChatPaneController,
} from "../../chatPaneController";
import { CHAT_WIDTH_CSS_VAR } from "../../workspaceLayout";

/**
 * The three-region working page for `/work/:bookId`. Reads `:bookId` from the
 * router (`useParams`), owns a `WorkspaceShellState` via `useState`, runs a single
 * mount-only `useEffect` that starts `loadWorkspaceBook` and aborts on unmount,
 * and lays out the regions with Mantine `AppShell`: `WorkNavigator` on the left,
 * the content pane in the centre containing the repo's first `<Outlet/>`, and
 * `ChatPaneSlot` on the right. Renders the book title plus the loading and error
 * states of its own book trio. No props (mirrors the admin shell pattern, but
 * with `<Outlet/>` in place of `children`).
 *
 * The book load runs once per mount (empty-deps effect); because `routes.tsx`
 * keys this element on `:bookId`, a subject-route change under the same book does
 * NOT remount, so `loadWorkspaceBook` fires exactly once across such navigation.
 *
 * fast/005: this component MUST NEVER read `state.chatWidthFraction` in its JSX —
 * only `ChatResizeHandle` may observe the live fraction. The aside's width prop is
 * a CONSTANT string and the drag travels through the `--work-chat-width` custom
 * property, set imperatively by the single `autorun` inside the existing mount
 * effect. Observing the fraction here would re-render the whole content pane on
 * every pointer move, which is the one thing this design exists to avoid.
 */
export const WorkspaceShell = observer(function WorkspaceShell() {
  const { bookId } = useParams();
  const [state] = useState(() => new WorkspaceShellState());
  const [chatPaneState] = useState(() => new ChatPaneState());

  useEffect(() => {
    const ctrl = new AbortController();
    // 016: the pane IS the close-turn controller (`ChatPaneState implements
    // CloseTurnController`), so the implementation and its identity token are the
    // same object and nothing extra is threaded anywhere. Registered in the effect
    // that already owns the pane's lifecycle — no new effect and no new component.
    registerCloseTurnController(chatPaneState);
    // 023 / D5: the SAME effect also publishes the pane's one-verb open-a-chat
    // seam, so the content-pane `ChatsListPage` can open a chat in the aside
    // without a route change, a context or a cross-page callback. A small object
    // rather than the pane state itself (unlike the close-turn controller): it has
    // to close over `bookId`, which `ChatPaneState` deliberately does not hold. It
    // doubles as its own unregister identity token.
    const chatPaneController: ChatPaneController = {
      openChat: (chatId: string) => {
        pickChat(chatPaneState, bookId ?? "", chatId);
        // Opening a chat means showing ITS conversation: without this the pane
        // would swap its title and settings while still rendering the previous
        // chat's transcript.
        void loadChatMessages(chatPaneState, bookId ?? "", chatId);
      },
    };
    registerChatPaneController(chatPaneController);
    void loadWorkspaceBook(state, bookId ?? "", ctrl.signal);
    void loadChatPane(chatPaneState, bookId ?? "", ctrl.signal);
    // `frontend.md`'s sanctioned "a single `autorun` started in the mount
    // `useEffect` and disposed on cleanup" — here it pushes the live width onto a
    // CSS custom property so a pointer drag bypasses React entirely. NO second
    // effect, deps unchanged, and re-creation under StrictMode is idempotent.
    const disposeChatWidthVar = autorun(() => {
      document.documentElement.style.setProperty(CHAT_WIDTH_CSS_VAR, state.chatWidthCssValue);
    });
    return () => {
      disposeChatWidthVar();
      document.documentElement.style.removeProperty(CHAT_WIDTH_CSS_VAR);
      // Unconditional and idempotent — detaches a drag still in flight at unmount.
      endChatResize(state);
      // Identity-guarded inside the registry, so a late unmount whose registration
      // has already been superseded clears nothing.
      unregisterCloseTurnController(chatPaneState);
      // Identity-guarded in the same way, in the SAME cleanup — no second effect
      // (DoD-15).
      unregisterChatPaneController(chatPaneController);
      ctrl.abort();
      // Unmount also aborts any live turn stream (a separate AbortController owned
      // by the pane state, not the load signal) — the unmount half of DoD-10.
      stopChatTurn(chatPaneState);
    };
  }, [state, chatPaneState]);

  const id = bookId ?? "";
  const loading = state.bookDetailStatus === "idle" || state.bookDetailStatus === "loading";

  return (
    <AppShell
      header={{ height: 56 }}
      // `AppShell.Main` animates `transition-property: padding`, which would
      // rubber-band 200ms behind the pointer during a drag.
      transitionDuration={state.resizing ? 0 : 200}
      navbar={{
        width: state.navbarWidth,
        breakpoint: "sm",
        // `collapsed.mobile` is "is collapsed" — the NEGATION of "is open".
        collapsed: { mobile: !state.navbarOpened },
      }}
      aside={{
        // A CONSTANT string frozen at construction from the STORED width — never
        // the live fraction. Keep the `calc(...)` wrapper: Mantine's `rem()` passes
        // a string through verbatim only when it starts with `calc(`, `clamp(` or
        // `rgba(`, and splits every other comma-bearing string on its commas.
        width: state.asideWidthCss,
        breakpoint: "md",
        collapsed: { desktop: false, mobile: true },
      }}
    >
      <AppShell.Header>
        <Group h="100%" px="md" gap="sm" wrap="nowrap">
          <Burger
            opened={state.navbarOpened}
            onClick={() => {
              state.navbarOpened = !state.navbarOpened;
            }}
            hiddenFrom="sm"
            size="sm"
            aria-label="Toggle navigation"
            aria-expanded={state.navbarOpened}
          />
          <Tooltip
            label={state.navCollapsed ? "Pin navigator open" : "Collapse navigator"}
            position="bottom"
            withArrow
          >
            <ActionIcon
              variant="subtle"
              visibleFrom="sm"
              aria-label={state.navCollapsed ? "Pin navigator open" : "Collapse navigator"}
              aria-pressed={!state.navCollapsed}
              onClick={() => toggleNavCollapsed(state)}
            >
              {state.navCollapsed ? (
                <IconPinnedOff size={18} stroke={1.5} />
              ) : (
                <IconPinned size={18} stroke={1.5} />
              )}
            </ActionIcon>
          </Tooltip>
          {loading ? <Loader size="sm" /> : <Title order={4}>{state.bookDetail?.title}</Title>}
        </Group>
      </AppShell.Header>

      <AppShell.Navbar p="xs">
        {/*
          023: `onShowChatList` is GONE from both sides — the Chats entry is an
          ordinary route link to `/:bookId/chats` now, and the chat list lives on
          that content-pane page (D1). No dead prop is left on either side (DoD-12).
        */}
        <WorkNavigator bookId={id} collapsed={state.navCollapsed} />
      </AppShell.Navbar>

      <AppShell.Aside p="xs">
        {/* Shell chrome on the aside's left edge, NOT pane content —
            `ChatPaneSlot`'s props stay untouched (011.chat-panel owns the pane). */}
        <ChatResizeHandle state={state} />
        <ChatPaneSlot bookId={id} state={chatPaneState} />
      </AppShell.Aside>

      <AppShell.Main>
        {state.bookDetailStatus === "error" ? (
          <Alert color="red" m="md">
            {state.bookDetailError}
          </Alert>
        ) : (
          <Outlet />
        )}
      </AppShell.Main>
    </AppShell>
  );
});
