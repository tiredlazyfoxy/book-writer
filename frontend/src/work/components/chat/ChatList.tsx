import { observer } from "mobx-react-lite";
import {
  ActionIcon,
  Group,
  ScrollArea,
  Stack,
  Text,
  UnstyledButton,
} from "@mantine/core";
import { IconArchive, IconArchiveOff } from "@tabler/icons-react";
import type { ISODateString } from "../../../types/common";
import type { ChatPaneState } from "./chatPaneState";

/** Render a chat's last-modified stamp for the author, or an em dash when absent. */
function formatStamp(value: ISODateString | null): string {
  if (!value) return "—";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
}

/**
 * The chat pane's list of visible chats (`state.visibleChats`): title,
 * last-modified stamp, the active one marked, a per-row archive (or restore, in
 * the archived view) action, and an empty state. Picking a row calls `onPick`;
 * NOTHING here navigates. Reads `state.activeChatId` / `state.showArchived`.
 *
 * SKELETON (011/004): props frozen; body throws.
 */
export interface ChatListProps {
  state: ChatPaneState;
  /** Called with a chat id when a row is picked. */
  onPick: (chatId: string) => void;
  /** Called with a chat id and the target archived flag by the per-row action. */
  onSetArchived: (chatId: string, archived: boolean) => void;
}

export const ChatList = observer(function ChatList({
  state,
  onPick,
  onSetArchived,
}: ChatListProps) {
  const chats = state.visibleChats;

  if (chats.length === 0) {
    return (
      <Text c="dimmed" size="sm" py="sm">
        {state.showArchived ? "No archived chats." : "No chats yet."}
      </Text>
    );
  }

  return (
    <ScrollArea.Autosize mah={320}>
      <Stack gap={4}>
        {chats.map((chat) => {
          const active = chat.id === state.activeChatId;
          return (
            <Group
              key={chat.id}
              justify="space-between"
              wrap="nowrap"
              gap="xs"
              px="xs"
              py={4}
              data-active={active || undefined}
              style={{
                borderRadius: "var(--mantine-radius-sm)",
                borderLeft: active
                  ? "3px solid var(--mantine-primary-color-filled)"
                  : "3px solid transparent",
                background: active ? "var(--mantine-color-default-hover)" : undefined,
              }}
            >
              <UnstyledButton
                onClick={() => onPick(chat.id)}
                style={{ flex: 1, minWidth: 0 }}
              >
                <Text size="sm" fw={active ? 600 : 400} truncate>
                  {chat.title}
                </Text>
                <Text c="dimmed" size="xs">
                  {formatStamp(chat.modified_at)}
                </Text>
              </UnstyledButton>
              <ActionIcon
                variant="subtle"
                color="gray"
                onClick={() => onSetArchived(chat.id, !chat.archived)}
                aria-label={chat.archived ? "Restore chat" : "Archive chat"}
              >
                {chat.archived ? (
                  <IconArchiveOff size={16} stroke={1.5} />
                ) : (
                  <IconArchive size={16} stroke={1.5} />
                )}
              </ActionIcon>
            </Group>
          );
        })}
      </Stack>
    </ScrollArea.Autosize>
  );
});
