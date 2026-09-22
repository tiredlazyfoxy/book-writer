import { useEffect, useState } from "react";
import { observer } from "mobx-react-lite";
import { useParams } from "react-router-dom";
import {
  Alert,
  Container,
  Group,
  Loader,
  Stack,
  Switch,
  Text,
  Title,
} from "@mantine/core";
import { ChatList } from "../components/chat/ChatList";
import { requestOpenChat } from "../chatPaneController";
import {
  ChatsListPageState,
  archiveListChat,
  loadChats,
} from "./chatsListPageState";

/**
 * The book's chat list, rendered into the CONTENT pane at `/work/:bookId/chats`
 * (023, UC-081 / UC-082 / US-095 / US-096).
 *
 * 023 knowingly inverts `011.chat-panel`'s shipped arrangement (D1): the list
 * lived in the chat pane and `/chats` was redirect-only; it is now an ordinary
 * content-pane page and the Chats navigator entry is an ordinary router link. The
 * product-doc reconciliation is `outcome.md`'s obligation.
 *
 * NO PROPS — the book id comes from `useParams()`, like every other subject page.
 * Owns a `ChatsListPageState` via `useState(() => new ChatsListPageState())` and
 * runs ONE page-level mount `useEffect` (deps `[state]`) that calls
 * `loadChats(state, bookId, ctrl.signal)` and aborts on cleanup.
 *
 * It renders `ChatList`, whose props 023 retargets onto `ChatsListPageState`.
 * Picking a row calls `requestOpenChat(chatId)` and **does not navigate** — the
 * chat opens in the chat pane while the URL stays on `/chats` (D5); the row's
 * archive/restore action calls `archiveListChat`.
 */
export const ChatsListPage = observer(function ChatsListPage() {
  const { bookId } = useParams();
  const [state] = useState(() => new ChatsListPageState());

  useEffect(() => {
    const ctrl = new AbortController();
    void loadChats(state, bookId ?? "", ctrl.signal);
    return () => {
      ctrl.abort();
    };
  }, [state]);

  /**
   * Row activation — the chat opens in the CHAT pane through the module registry
   * and the URL stays on `/chats` (D5). NOTHING here navigates, and a click with
   * no pane mounted is a silent no-op rather than an error.
   */
  const handlePick = (chatId: string) => {
    requestOpenChat(chatId);
  };

  const handleSetArchived = (chatId: string, archived: boolean) => {
    void archiveListChat(state, bookId ?? "", chatId, archived);
  };

  const actionFailed = Object.values(state.actionStatus).some((s) => s === "error");

  const renderBody = () => {
    if (state.chatsStatus === "error") {
      return (
        <Alert color="red" title="Could not load">
          <Text size="sm">{state.chatsError}</Text>
        </Alert>
      );
    }

    if (state.chatsStatus === "idle" || state.chatsStatus === "loading") {
      return (
        <Group justify="center" py="md" gap="xs">
          <Loader size="sm" />
          <Text size="sm" c="dimmed">
            Loading…
          </Text>
        </Group>
      );
    }

    // `ChatList` renders its own empty state for both views, so `isEmpty` needs no
    // branch of its own here.
    return <ChatList state={state} onPick={handlePick} onSetArchived={handleSetArchived} />;
  };

  return (
    <Container size="lg" py="md">
      <Stack gap="md">
        <Group justify="space-between">
          <Title order={3}>Chats</Title>
          <Switch
            label="Show archived"
            checked={state.showArchived}
            onChange={(event) => {
              state.showArchived = event.currentTarget.checked;
            }}
          />
        </Group>

        {actionFailed && (
          <Alert color="red">Could not update the chat. Please try again.</Alert>
        )}

        {renderBody()}
      </Stack>
    </Container>
  );
});
