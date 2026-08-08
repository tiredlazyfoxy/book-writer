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
import type { ChatsListPageState } from "../../pages/chatsListPageState";

/** Render a chat's last-modified stamp for the author, or an em dash when absent. */
function formatStamp(value: ISODateString | null): string {
  if (!value) return "—";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
}

/**
 * The book's list of visible chats (`state.visibleChats`): title, last-modified
 * stamp, a per-row archive (or restore, in the archived view) action, and an
 * empty state. Picking a row calls `onPick`; NOTHING here navigates. Reads
 * `state.showArchived`.
 *
 * 023 RETARGETS THE PROPS onto `ChatsListPageState`: the list moved out of the
 * chat pane and onto the content-pane `ChatsListPage` (D1/D5), which owns its own
 * chats. The ACTIVE-CHAT MARKER is gone with it — the list page has no notion of
 * "active"; that fact belongs to the pane, which the page reaches only through
 * `work/chatPaneController.ts`.
 *
 * SKELETON (023): props frozen; the row shape is 011's, preserved unchanged
 * except for the dropped active marker.
 */
export interface ChatListProps {
  state: ChatsListPageState;
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
          return (
            <Group
              key={chat.id}
              justify="space-between"
              wrap="nowrap"
              gap="xs"
              px="xs"
              py={4}
              style={{
                borderRadius: "var(--mantine-radius-sm)",
              }}
            >
              <UnstyledButton
                onClick={() => onPick(chat.id)}
                style={{ flex: 1, minWidth: 0 }}
              >
                <Text size="sm" truncate>
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
