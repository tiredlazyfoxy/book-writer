import type { KeyboardEvent } from "react";
import { observer } from "mobx-react-lite";
import {
  ActionIcon,
  Alert,
  Button,
  Combobox,
  Group,
  Loader,
  Modal,
  Popover,
  Stack,
  Text,
  Title,
  useCombobox,
} from "@mantine/core";
import {
  IconAdjustmentsHorizontal,
  IconArrowFork,
  IconMessageCheck,
  IconPlus,
} from "@tabler/icons-react";
import { ChatSettingsPanel } from "./ChatSettingsPanel";
import { MessageList } from "./MessageList";
import { Composer } from "./Composer";
import { ComposerResizeHandle } from "./ComposerResizeHandle";
import {
  createChatInstant,
  deleteSideChat,
  dismissDeleteSideChat,
  finishSideChat,
  modelOptionKey,
  pickChatModel,
  retryChatTurn,
  sendChatTurn,
  startSideChat,
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
 * BOTH HEADER SURFACES ARE DRIVEN BY ONE DISCRIMINATOR, `state.openedPanel` (D7):
 * opening either closes the other by construction, and `sendChatTurn` clears it, so
 * "options close when the author sends or opens the other panel" is one state
 * machine rather than two booleans that can disagree. This is the codebase's first
 * `Popover`; there is no in-repo idiom to copy for its open/close wiring, which is
 * exactly why the wiring is state and not component-local.
 *
 * FAST/009 DE-NESTS THE MODEL CONTROL. It used to be a `Popover` whose entire
 * dropdown was a collapsed `<Select>` — a dropdown inside a dropdown, three clicks
 * to change a model. It is now one `Combobox` in CONTROLLED mode (`useCombobox`
 * with `opened` / `onOpenedChange` bound to `openedPanel`, so the discriminator
 * survives): one click opens an already-rendered, searchable list, and the pick
 * PATCHes the chat at once through `pickChatModel` rather than parking in
 * `settingsDraft` until the next send.
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

  // THE MODEL DROPDOWN, CONTROLLED BY `openedPanel`. `frontend.md`'s controlled-
  // popover rule applies transitively (a `Combobox` IS a `Popover`): the target's
  // own click owns the toggle, and Mantine's dismissals — click-outside, Escape —
  // come back through `onOpenedChange`. Both directions are bound below, or the
  // dropdown becomes unclosable in one of them.
  const combobox = useCombobox({
    opened: state.openedPanel === "model",
    onOpenedChange: (opened) => {
      // A needle never survives a close/reopen (DoD-12).
      state.modelSearch = "";
      if (opened) {
        state.openedPanel = "model";
        return;
      }
      dismissPanel("model", opened);
    },
  });

  const handleModelButtonClick = () => {
    state.modelSearch = "";
    combobox.resetSelectedOption();
    togglePanel("model");
  };

  // ENTER PICKS THE FIRST OPTION OF THE FILTERED LIST (DoD-4) — but only while
  // nothing is highlighted. Once the author has moved the highlight with the arrow
  // keys, Mantine's own handler (which runs right after this one) clicks the
  // highlighted option, so bailing out here is what keeps a pick from firing twice.
  const handleModelSearchKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key !== "Enter") return;
    if (combobox.getSelectedOptionIndex() !== -1) return;
    event.preventDefault();
    const first = state.filteredModelOptions[0];
    if (first === undefined) return;
    void pickChatModel(state, bookId, modelOptionKey(first));
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

  // THE SIDE-CHAT SLOT (027). One control, two identities: `activeSideChatId` is
  // the SERVER's pointer on the active chat, so the slot shows Finish after a
  // reload with no client-side memory involved (US-141.AC-1). The D1 gating
  // (streaming / a close running / an action in flight / no active chat) lives
  // entirely in the `can…` computeds — the pane adds no gate of its own.
  const sideChatActive = state.activeSideChatId !== null;

  const handleStartSideChat = () => {
    void startSideChat(state, bookId);
  };
  const handleFinishSideChat = () => {
    void finishSideChat(state, bookId);
  };

  // The pending id is read AT CLICK TIME, never captured at render: the confirm
  // slot is the single source of which side chat is being deleted, and the delete
  // effect clears it itself on both outcomes.
  const handleConfirmDeleteSideChat = () => {
    const pendingSideChatId = state.sideChatDeleteConfirm;
    if (pendingSideChatId === null) return;
    void deleteSideChat(state, bookId, pendingSideChatId);
  };
  const handleDismissDeleteSideChat = () => {
    dismissDeleteSideChat(state);
  };

  const paneLoading = state.chatsStatus === "idle" || state.chatsStatus === "loading";

  return (
    // THE PANE'S VERTICAL CHAIN (feedback F1). `h="100%"` fills the fixed-height
    // `AppShell.Aside`; this `Stack` is the flex column, and `MessageList` is the one
    // child that grows (`flex: 1` + `minHeight: 0`, declared there), so the composer
    // is carried to the bottom edge by the transcript rather than by positioning of
    // its own. `mih={0}` keeps that true if this column ever becomes a flex item
    // itself — a flex item's automatic minimum is its content height, which would
    // otherwise let the column outgrow the aside.
    <Stack gap="sm" h="100%" mih={0}>
      {/* THE DELETE CONFIRMATION (027, US-140.AC-1). A plain `@mantine/core`
          `Modal` — `@mantine/modals` is not installed — following the
          `ChapterPage` close confirmation. Opened purely by the pending id, so the
          per-group Delete icon posts nothing at all: it only fills the slot.

          The affirmative is named "Delete side chat" and NOT the bare word
          "Delete", and the title names the action, because Mantine's own dismiss
          control is named "Close". */}
      <Modal
        opened={state.sideChatDeleteConfirm !== null}
        onClose={handleDismissDeleteSideChat}
        title="Delete this side chat?"
      >
        <Stack gap="sm">
          <Text size="sm">
            The side chat&apos;s messages are removed permanently. This cannot be
            undone.
          </Text>
          <Text size="sm" c="dimmed">
            Anything saved while it ran — codex entries, chapter edits, memos — is
            kept.
          </Text>
          <Group justify="flex-end">
            <Button variant="default" onClick={handleDismissDeleteSideChat}>
              Keep it
            </Button>
            <Button color="red" onClick={handleConfirmDeleteSideChat}>
              Delete side chat
            </Button>
          </Group>
        </Stack>
      </Modal>

      <Group justify="space-between" wrap="nowrap" gap="xs">
        <Title order={5} lineClamp={1}>
          {state.activeChat ? state.activeChat.title : "Chats"}
        </Title>

        <Group gap={4} wrap="nowrap">
          <Combobox
            store={combobox}
            onOptionSubmit={(value) => {
              void pickChatModel(state, bookId, value);
            }}
            position="bottom-end"
            shadow="md"
            width={260}
            withArrow
            // The dropdown renders INLINE (no portal) and MOUNTS ON OPEN: `keepMounted`
            // defaults to `true` on a `Combobox`, and a kept-mounted dropdown would
            // never re-fire the search field's `autoFocus`.
            withinPortal={false}
            keepMounted={false}
          >
            <Combobox.Target targetType="button">
              <Button
                variant="subtle"
                size="compact-xs"
                onClick={handleModelButtonClick}
                aria-label="Model"
                style={{ maxWidth: 160 }}
              >
                <Text size="xs" truncate>
                  {state.modelLabel}
                </Text>
              </Button>
            </Combobox.Target>
            <Combobox.Dropdown>
              <Combobox.Search
                value={state.modelSearch}
                onChange={(event) => {
                  state.modelSearch = event.currentTarget.value;
                  // A new needle invalidates the old highlight; dropping it puts
                  // Enter back on the first option of the newly filtered list.
                  combobox.resetSelectedOption();
                }}
                onKeyDown={handleModelSearchKeyDown}
                placeholder="Search models"
                aria-label="Search models"
                autoFocus
              />
              <Combobox.Options mah={240} style={{ overflowY: "auto" }}>
                {/*
                  A DEAD BUTTON IS WORSE THAN A LABELLED EMPTY STATE: the dropdown
                  opens in all three non-option cases and simply says why it has
                  nothing to offer. The error case is tested first — a failed load
                  also leaves `modelOptions` empty.
                */}
                {state.modelOptionsStatus === "error" ? (
                  <Combobox.Empty>{state.modelOptionsError}</Combobox.Empty>
                ) : state.modelOptions.length === 0 ? (
                  <Combobox.Empty>No models available</Combobox.Empty>
                ) : state.filteredModelOptions.length === 0 ? (
                  <Combobox.Empty>Nothing found</Combobox.Empty>
                ) : (
                  state.filteredModelOptions.map((option) => (
                    <Combobox.Option
                      value={modelOptionKey(option)}
                      key={modelOptionKey(option)}
                    >
                      {`${option.server_name} · ${option.model_name}`}
                    </Combobox.Option>
                  ))
                )}
              </Combobox.Options>
            </Combobox.Dropdown>
          </Combobox>

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

          {/*
            SWAP, DO NOT HIDE: one element whose accessible name, icon, disabled
            state and handler all switch. Rendering both and hiding one would leave
            both names in the accessibility tree, and "no control named Finish side
            chat" is a criterion (DoD-1/DoD-2). It stays OUT of the `openedPanel`
            discriminator — it opens no popover.
          */}
          <ActionIcon
            variant="subtle"
            onClick={sideChatActive ? handleFinishSideChat : handleStartSideChat}
            disabled={
              sideChatActive ? !state.canFinishSideChat : !state.canStartSideChat
            }
            aria-label={sideChatActive ? "Finish side chat" : "Start side chat"}
          >
            {sideChatActive ? (
              <IconMessageCheck size={18} stroke={1.5} />
            ) : (
              <IconArrowFork size={18} stroke={1.5} />
            )}
          </ActionIcon>

          <ActionIcon variant="light" onClick={handleNewChat} aria-label="New chat">
            <IconPlus size={18} stroke={1.5} />
          </ActionIcon>
        </Group>
      </Group>

      {/*
        A REJECTED PICK REPORTS IN THE HEADER REGION, not in the dropdown: the
        dropdown has already closed by the time the PATCH resolves, so a message
        inside it would never be seen (fast/009 DoD-7).
      */}
      {state.serverErrors.model && <Alert color="red">{state.serverErrors.model}</Alert>}

      {state.serverErrors.form && <Alert color="red">{state.serverErrors.form}</Alert>}

      {/*
        THE SIDE-CHAT ACTION ERROR ONLY (D-F). The turn's own error lives in the
        composer and the pane's load error is the `chatsStatus` branch below;
        neither is touched. A failed action leaves `chats` / `messages` as the
        server last described them, so the banner is the whole of the report.
      */}
      {state.sideChatActionStatus === "error" && (
        <Alert color="red">{state.sideChatActionError}</Alert>
      )}

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
          <MessageList state={state} bookId={bookId} />
          <ComposerResizeHandle state={state} />
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
