import { observer } from "mobx-react-lite";
import { Stack, Text } from "@mantine/core";

/**
 * The workspace's right-hand region placeholder. The chat pane itself is owned by
 * `011.chat-panel` and stays empty until Stage 5 (`frontend-workspace.md` → "The
 * working page"); this slot only renders a short notice naming that owner. No
 * chat behaviour, no state, no props.
 *
 */
export const ChatPaneSlot = observer(function ChatPaneSlot() {
  return (
    <Stack gap="xs" p="md">
      <Text size="sm" fw={500}>
        Chat
      </Text>
      <Text size="sm" c="dimmed">
        The chat pane is delivered by 011.chat-panel.
      </Text>
    </Stack>
  );
});
