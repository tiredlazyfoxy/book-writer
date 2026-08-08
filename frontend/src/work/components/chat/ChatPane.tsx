import { observer } from "mobx-react-lite";
import {
  ActionIcon,
  Alert,
  Button,
  Group,
  Loader,
  Popover,
  Select,
  Stack,
  Text,
  Title,
} from "@mantine/core";
import { IconAdjustmentsHorizontal, IconPlus } from "@tabler/icons-react";
import { ChatSettingsPanel } from "./ChatSettingsPanel";
import { MessageList } from "./MessageList";
import { Composer } from "./Composer";
import {
  createChatInstant,
  modelOptionKey,
  retryChatTurn,
  sendChatTurn,
  stopChatTurn,
  type ChatPaneState,
} from "./chatPaneState";

/**
 * The workspace's right-hand chat pane. Takes the book id and the shared
 * `ChatPaneState` (owned by `WorkspaceShell`) as props — it creates NO state
 * instance of its own and runs NO effect.
 *
 * 023 REDUCES THIS PANE TO THE CONVERSATION. The chat list, the new-chat form and
 * the "Save settings" button are gone: chat management lives on the content-pane
 * `ChatsListPage` (D1/D5), a "+" creates a chat instantly with no form (D6), and
 * settings are persisted by the send itself (D8). What is left is the header (the
 * active chat's title, the model control, the settings control and "+"), the
 * transcript ({@link import("./MessageList").MessageList}) and the composer
 * ({@link import("./Composer").Composer}).
 *
 * BOTH HEADER POPOVERS ARE DRIVEN BY ONE DISCRIMINATOR, `state.openedPanel` (D7):
 * opening either closes the other by construction, and `sendChatTurn` clears it, so
 * "options close when the author sends or opens the other panel" is one state
 * machine rather than two booleans that can disagree. This is the codebase's first
 * `Popover`; there is no in-repo idiom to copy for its open/close wiring, which is
 * exactly why the wiring is state and not component-local.
 */
export interface ChatPaneProps {
  bookId: string;
  state: ChatPaneState;
}

export const ChatPane = observer(function ChatPane({ bookId, state }: ChatPaneProps) {
  /** Toggle one popover open; opening either closes the other by construction (D7). */
  const togglePanel = (panel: "model" | "settings") => {
    state.openedPanel = state.openedPanel === panel ? null : panel;
  };

  /** Close `panel` when Mantine dismisses it (click outside / Escape). */
  const dismissPanel = (panel: "model" | "settings", opened: boolean) => {
    if (!opened && state.openedPanel === panel) state.openedPanel = null;
  };

  // "+" creates immediately — no form, no title, the active chat's model pair by
  // default (D6). The refusal when no model exists is `createChatInstant`'s, and it
  // surfaces through the `serverErrors.form` alert below.
  const handleNewChat = () => {
    void createChatInstant(state, bookId);
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

  const paneLoading = state.chatsStatus === "idle" || state.chatsStatus === "loading";

  const modelData = state.modelOptions.map((option) => ({
    value: modelOptionKey(option),
    label: `${option.server_name} · ${option.model_name}`,
  }));

  return (
    // THE PANE'S VERTICAL CHAIN (feedback F1). `h="100%"` fills the fixed-height
    // `AppShell.Aside`; this `Stack` is the flex column, and `MessageList` is the one
    // child that grows (`flex: 1` + `minHeight: 0`, declared there), so the composer
    // is carried to the bottom edge by the transcript rather than by positioning of
    // its own. `mih={0}` keeps that true if this column ever becomes a flex item
    // itself — a flex item's automatic minimum is its content height, which would
    // otherwise let the column outgrow the aside.
    <Stack gap="sm" h="100%" mih={0}>
      <Group justify="space-between" wrap="nowrap" gap="xs">
        <Title order={5} lineClamp={1}>
          {state.activeChat ? state.activeChat.title : "Chats"}
        </Title>

        <Group gap={4} wrap="nowrap">
          <Popover
            opened={state.openedPanel === "model"}
            onChange={(opened) => dismissPanel("model", opened)}
            position="bottom-end"
            shadow="md"
            width={260}
            withArrow
          >
            <Popover.Target>
              <Button
                variant="subtle"
                size="compact-xs"
                onClick={() => togglePanel("model")}
                aria-label="Model"
                style={{ maxWidth: 160 }}
              >
                <Text size="xs" truncate>
                  {state.modelLabel}
                </Text>
              </Button>
            </Popover.Target>
            <Popover.Dropdown>
              {modelData.length === 0 ? (
                <Text size="sm" c="dimmed">
                  No models are available.
                </Text>
              ) : (
                <Select
                  label="Model"
                  data={modelData}
                  value={state.settingsDraft.optionKey}
                  onChange={(value) => {
                    state.settingsDraft.optionKey = value;
                  }}
                  comboboxProps={{ withinPortal: false }}
                  allowDeselect={false}
                />
              )}
            </Popover.Dropdown>
          </Popover>

          <Popover
            opened={state.openedPanel === "settings"}
            onChange={(opened) => dismissPanel("settings", opened)}
            position="bottom-end"
            shadow="md"
            width={260}
            withArrow
          >
            <Popover.Target>
              <ActionIcon
                variant="subtle"
                onClick={() => togglePanel("settings")}
                aria-label="Chat settings"
              >
                <IconAdjustmentsHorizontal size={18} stroke={1.5} />
              </ActionIcon>
            </Popover.Target>
            <Popover.Dropdown>
              <ChatSettingsPanel draft={state.settingsDraft} errors={state.errors} />
            </Popover.Dropdown>
          </Popover>

          <ActionIcon variant="light" onClick={handleNewChat} aria-label="New chat">
            <IconPlus size={18} stroke={1.5} />
          </ActionIcon>
        </Group>
      </Group>

      {state.serverErrors.form && <Alert color="red">{state.serverErrors.form}</Alert>}

      {/*
        023: the chat LIST is gone from this pane — `ChatList` now belongs to the
        content-pane `ChatsListPage` and reads `ChatsListPageState` (D1/D5), so
        this slot keeps only the pane's own load error / loading indicator.
      */}
      {state.chatsStatus === "error" ? (
        <Alert color="red">{state.chatsError}</Alert>
      ) : paneLoading ? (
        <Group justify="center" py="sm">
          <Loader size="sm" />
        </Group>
      ) : null}

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
