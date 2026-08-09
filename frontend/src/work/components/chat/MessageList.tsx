import { observer } from "mobx-react-lite";
import { Box, Paper, ScrollArea, Stack, Text } from "@mantine/core";
import Markdown from "react-markdown";
import { ThinkingBlock } from "./ThinkingBlock";
import { ToolCallTrace } from "./ToolCallTrace";
import { toggleToolCallRow } from "./chatPaneState";
import type { ChatPaneState } from "./chatPaneState";

/**
 * The conversation transcript for the active chat. Renders
 * `state.renderedMessages`: user messages as a bubble, assistant messages
 * through `react-markdown`, each assistant message that carries reasoning preceded
 * by a {@link import("./ThinkingBlock").ThinkingBlock}, plus the in-flight
 * assistant bubble fed from the streaming buffers.
 *
 * IT FILLS, IT DOES NOT CAP (feedback F1). This region consumes whatever vertical
 * space is left between `ChatPane`'s header and its composer and scrolls INSIDE
 * that space. The previous `<ScrollArea.Autosize mah={320}>` was a hard 320px
 * ceiling — it capped the transcript instead of filling the pane, so the composer
 * flowed directly after 320px of content and the rest of the column was left blank.
 * Both that cap and `ChatPane`'s root `h="100%"` are 011-era; 011's in-pane chat
 * list, new-chat form and Save-settings block had been occupying the slack, which is
 * why removing them in 023 is what made the gap visible.
 *
 * AUTHORSHIP IS CARRIED BY THE USER BUBBLE ALONE (D9, narrowed by feedback F2/F3).
 * A user message is a filled, right-offset bubble capped at 70% of the width — the
 * pane is a narrow, resizable aside, where the previous 85% cap was almost
 * indistinguishable from full width and read as a slightly-inset paragraph. The
 * assistant stays FULL WIDTH and now carries no role label and no per-turn divider:
 * with the bubble doing the work they were redundant chrome, and in a narrow column
 * they spent the vertical space F1 exists to reclaim. Assistant output is markdown
 * prose in a writing app, so bubbling it would shorten every line of the content the
 * author actually works with.
 *
 * The `data-role="user"` / `data-role="assistant"` hooks stay exactly where they
 * were — on the element wrapping each message — since they are the delivered
 * authorship contract.
 *
 * Holds NO `useEffect` (frontend.md leaf rule): the one sanctioned imperative
 * side-effect — auto-scroll while streaming — belongs, if shipped, in a single
 * pane-level mount `autorun`, never in this leaf. It is deliberately NOT shipped
 * here: the transcript did not auto-scroll before this reshape either, and adding it
 * would be new behaviour rather than the layout repair F1 asked for.
 */
export interface MessageListProps {
  state: ChatPaneState;
}

export const MessageList = observer(function MessageList({ state }: MessageListProps) {
  return (
    <ScrollArea
      type="auto"
      style={{
        // F1's fill: the ONLY child of `ChatPane`'s column that grows, so it takes
        // every pixel the header and composer do not.
        flex: 1,
        // The `minHeight: 0` trap: a flex item's automatic minimum size is its
        // CONTENT height, so without this the region refuses to shrink below the
        // conversation's length — it would grow the column and push the composer off
        // the pane's bottom edge instead of scrolling internally. Mantine's
        // `ScrollArea` root is `overflow: hidden` with a `height: 100%` viewport, so
        // a flex-resolved definite height here is exactly what makes it scroll.
        minHeight: 0,
      }}
    >
      <Stack gap="sm" p="xs">
        {state.renderedMessages.map((msg) => {
          if (msg.role === "user") {
            return (
              <Box
                key={msg.key}
                data-role="user"
                // The right-offset mechanism F2 preserves: the row is the flex
                // container, the bubble is the item pushed to its end.
                style={{ display: "flex", justifyContent: "flex-end" }}
              >
                <Paper
                  // Theme tokens, never a hard-coded colour: `filled` resolves to a
                  // different shade per colour scheme and `contrast` is the text
                  // colour Mantine itself pairs with it, so the bubble stays legible
                  // in both light and dark.
                  bg="var(--mantine-primary-color-filled)"
                  c="var(--mantine-primary-color-contrast)"
                  px="sm"
                  py={6}
                  radius="md"
                  // 70%, not 85%: in a narrow aside the bubble has to be visibly
                  // narrower than the assistant's full-width body to read as one.
                  style={{ maxWidth: "70%" }}
                >
                  <Text size="sm" style={{ whiteSpace: "pre-wrap" }}>
                    {msg.content}
                  </Text>
                </Paper>
              </Box>
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

          // F3: no `Divider`, no "Assistant" label — the wrapping `Stack` and its
          // `data-role` stay, and the thinking region and markdown body are as
          // delivered.
          return (
            <Stack key={msg.key} gap={4} data-role="assistant">
              {hasReasoning && (
                <ThinkingBlock
                  text={msg.reasoning ?? ""}
                  expanded={expanded}
                  onToggle={toggle}
                />
              )}
              {/* 024: the tool-call trace sits in the same per-message slot as the
                  thinking region and above the body — what the assistant DID
                  before it answered, in call order. It renders `null` when the
                  message has no trace, so it needs no condition here, and its
                  expansion map is keyed by (message key, row index), which the
                  in-flight bubble's sentinel key serves unchanged. */}
              <ToolCallTrace
                rows={msg.toolTrace}
                expanded={state.expandedToolCallRows}
                rowKeyPrefix={msg.key}
                onToggle={(rowKey) => toggleToolCallRow(state, rowKey)}
              />
              <Box className="chat-markdown" fz="sm">
                <Markdown>{msg.content}</Markdown>
              </Box>
            </Stack>
          );
        })}
      </Stack>
    </ScrollArea>
  );
});
