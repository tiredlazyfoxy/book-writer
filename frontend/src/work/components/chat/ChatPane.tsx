import { useState } from "react";
import { observer } from "mobx-react-lite";
import {
  ActionIcon,
  Alert,
  Button,
  Group,
  Loader,
  Stack,
  Switch,
  Text,
  TextInput,
  Title,
} from "@mantine/core";
import { IconList, IconPlus } from "@tabler/icons-react";
import { ChatList } from "./ChatList";
import { ChatSettingsPanel } from "./ChatSettingsPanel";
import { MessageList } from "./MessageList";
import { Composer } from "./Composer";
import {
  createChatFromDraft,
  loadChatMessages,
  pickChat,
  retryChatTurn,
  saveChatSettings,
  sendChatTurn,
  setChatArchived,
  stopChatTurn,
  type ChatPaneState,
} from "./chatPaneState";

/**
 * The workspace's right-hand chat pane. Takes the book id and the shared
 * `ChatPaneState` (owned by `WorkspaceShell`) as props — it creates NO state
 * instance of its own and runs NO effect. Renders the header (active chat title,
 * a New-chat control, a show-the-list control, an archived-view toggle), the list
 * ({@link import("./ChatList").ChatList}), the new-chat form and the settings
 * panel ({@link import("./ChatSettingsPanel").ChatSettingsPanel}), and — for an
 * active chat — the conversation region ({@link import("./MessageList").MessageList}
 * + {@link import("./Composer").Composer}).
 */
export interface ChatPaneProps {
  bookId: string;
  state: ChatPaneState;
}

export const ChatPane = observer(function ChatPane({ bookId, state }: ChatPaneProps) {
  // Whether the new-chat form is open — an ephemeral UI flag, so component-local
  // `useState` (the BookshelfPage `createOpen` precedent), never pane state. This
  // is not a state instance and drives no effect: the shell owns both.
  const [showNewChat, setShowNewChat] = useState(false);

  const handlePick = (chatId: string) => {
    pickChat(state, bookId, chatId);
    void loadChatMessages(state, bookId, chatId);
    setShowNewChat(false);
  };

  const handleSetArchived = (chatId: string, archived: boolean) => {
    const ctrl = new AbortController();
    void setChatArchived(state, bookId, chatId, archived, ctrl.signal);
  };

  const handleCreate = async () => {
    const ctrl = new AbortController();
    await createChatFromDraft(state, bookId, ctrl.signal);
    if (state.createStatus === "ready") setShowNewChat(false);
  };

  const handleSaveSettings = () => {
    const ctrl = new AbortController();
    void saveChatSettings(state, bookId, ctrl.signal);
  };

  // Conversation controls — wired to the turn effect fns. `streamChatTurn` owns and
  // returns its own AbortController (stored on the state), so these pass no signal.
  const handleSend = () => {
    void sendChatTurn(state, bookId, state.pendingPrompt);
  };
  const handleRetry = () => {
    void retryChatTurn(state, bookId);
  };
  const handleStop = () => {
    stopChatTurn(state);
  };

  const listLoading = state.chatsStatus === "idle" || state.chatsStatus === "loading";

  return (
    <Stack gap="sm" h="100%">
      <Group justify="space-between" wrap="nowrap">
        <Title order={5} lineClamp={1}>
          {state.activeChat ? state.activeChat.title : "Chats"}
        </Title>
        <Group gap={4} wrap="nowrap">
          <ActionIcon
            variant="subtle"
            onClick={() => setShowNewChat(false)}
            aria-label="Show chat list"
          >
            <IconList size={18} stroke={1.5} />
          </ActionIcon>
          <ActionIcon
            variant="light"
            onClick={() => setShowNewChat((open) => !open)}
            aria-label="New chat"
          >
            <IconPlus size={18} stroke={1.5} />
          </ActionIcon>
        </Group>
      </Group>

      <Switch
        label="Show archived"
        checked={state.showArchived}
        onChange={(event) => {
          state.showArchived = event.currentTarget.checked;
        }}
      />

      {state.serverErrors.form && <Alert color="red">{state.serverErrors.form}</Alert>}

      {showNewChat && (
        <Stack gap="xs">
          <Text fw={600} size="sm">
            New chat
          </Text>
          <TextInput
            label="Title"
            placeholder="New chat"
            value={state.newChatDraft.title}
            onChange={(event) => {
              state.newChatDraft.title = event.currentTarget.value;
            }}
          />
          <ChatSettingsPanel
            options={state.modelOptions}
            draft={state.newChatDraft}
            errors={state.errors}
          />
          <Button onClick={handleCreate} disabled={!state.canCreateChat}>
            Create chat
          </Button>
        </Stack>
      )}

      {state.chatsStatus === "error" ? (
        <Alert color="red">{state.chatsError}</Alert>
      ) : listLoading ? (
        <Group justify="center" py="sm">
          <Loader size="sm" />
        </Group>
      ) : (
        <ChatList state={state} onPick={handlePick} onSetArchived={handleSetArchived} />
      )}

      {state.activeChat && (
        <Stack gap="xs">
          <Text fw={600} size="sm">
            Settings
          </Text>
          <ChatSettingsPanel
            options={state.modelOptions}
            draft={state.settingsDraft}
            errors={state.errors}
          />
          <Button
            variant="light"
            onClick={handleSaveSettings}
            disabled={state.settingsStatus === "loading"}
          >
            Save settings
          </Button>
        </Stack>
      )}

      {/*
        Conversation region (step 005): the message transcript (with a collapsible
        Thinking region and markdown-rendered assistant content) and the composer
        with its send / stop / retry controls. Rendered only for an active chat.
      */}
      {state.activeChat && (
        <>
          <MessageList state={state} />
          <Composer
            state={state}
            onSend={handleSend}
            onStop={handleStop}
            onRetry={handleRetry}
          />
        </>
      )}
    </Stack>
  );
});
