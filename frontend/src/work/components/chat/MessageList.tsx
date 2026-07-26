import { observer } from "mobx-react-lite";
import { Box, ScrollArea, Stack, Text } from "@mantine/core";
import Markdown from "react-markdown";
import { ThinkingBlock } from "./ThinkingBlock";
import type { ChatPaneState } from "./chatPaneState";

/**
 * The conversation transcript for the active chat. Renders
 * `state.renderedMessages`: user messages as plain text, assistant messages
 * through `react-markdown`, each assistant message that carries reasoning preceded
 * by a {@link import("./ThinkingBlock").ThinkingBlock}, plus the in-flight
 * assistant bubble fed from the streaming buffers. Owns its own bounded, scrollable
 * height.
 *
 * Holds NO `useEffect` (frontend.md leaf rule): the one sanctioned imperative
 * side-effect — auto-scroll while streaming — belongs, if shipped, in a single
 * pane-level mount `autorun`, never in this leaf.
 *
 * SKELETON (011/005): props frozen; body throws (the DoD-asserted rendering is the
 * coder's).
 */
export interface MessageListProps {
  state: ChatPaneState;
}

export const MessageList = observer(function MessageList({ state }: MessageListProps) {
  return (
    <ScrollArea.Autosize mah={320} type="auto">
      <Stack gap="sm" p="xs">
        {state.renderedMessages.map((msg) => {
          if (msg.role === "user") {
            return (
              <Text
                key={msg.key}
                size="sm"
                data-role="user"
                style={{ whiteSpace: "pre-wrap" }}
              >
                {msg.content}
              </Text>
            );
          }

          const hasReasoning = msg.reasoning !== null && msg.reasoning !== "";
          const expanded = msg.streaming
            ? state.liveThinkingExpanded
            : (state.expandedReasoning[msg.key] ?? false);
          const toggle = () => {
            if (msg.streaming) {
              state.liveThinkingExpanded = !state.liveThinkingExpanded;
            } else {
              state.expandedReasoning[msg.key] = !(state.expandedReasoning[msg.key] ?? false);
            }
          };

          return (
            <Stack key={msg.key} gap={4} data-role="assistant">
              {hasReasoning && (
                <ThinkingBlock
                  text={msg.reasoning ?? ""}
                  expanded={expanded}
                  onToggle={toggle}
                />
              )}
              <Box className="chat-markdown" fz="sm">
                <Markdown>{msg.content}</Markdown>
              </Box>
            </Stack>
          );
        })}
      </Stack>
    </ScrollArea.Autosize>
  );
});
