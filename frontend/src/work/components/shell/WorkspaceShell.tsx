import { useEffect, useState } from "react";
import { observer } from "mobx-react-lite";
import { Outlet, useParams } from "react-router-dom";
import { Alert, AppShell, Burger, Group, Loader, Title } from "@mantine/core";
import { WorkNavigator } from "./WorkNavigator";
import { ChatPaneSlot } from "./ChatPaneSlot";
import { WorkspaceShellState, loadWorkspaceBook } from "./workspaceShellState";
import { ChatPaneState, loadChatPane, stopChatTurn } from "../chat/chatPaneState";

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
 */
export const WorkspaceShell = observer(function WorkspaceShell() {
  const { bookId } = useParams();
  const [state] = useState(() => new WorkspaceShellState());
  const [chatPaneState] = useState(() => new ChatPaneState());

  useEffect(() => {
    const ctrl = new AbortController();
    void loadWorkspaceBook(state, bookId ?? "", ctrl.signal);
    void loadChatPane(chatPaneState, bookId ?? "", ctrl.signal);
    return () => {
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
      navbar={{
        width: 220,
        breakpoint: "sm",
        // `collapsed.mobile` is "is collapsed" — the NEGATION of "is open".
        collapsed: { mobile: !state.navbarOpened },
      }}
      aside={{ width: 320, breakpoint: "md", collapsed: { desktop: false, mobile: true } }}
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
          {loading ? <Loader size="sm" /> : <Title order={4}>{state.bookDetail?.title}</Title>}
        </Group>
      </AppShell.Header>

      <AppShell.Navbar p="xs">
        <WorkNavigator
          bookId={id}
          onShowChatList={() => {
            // The Chats navigator entry is a pane-state control, not a link: it
            // reveals the chat pane's active-chats list (the aside is always
            // mounted). Mirrors the direct-mutation pattern used for `navbarOpened`.
            chatPaneState.showArchived = false;
          }}
        />
      </AppShell.Navbar>

      <AppShell.Aside p="xs">
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
