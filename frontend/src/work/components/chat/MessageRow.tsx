import { observer } from "mobx-react-lite";
import { Box, Paper, Stack, Text } from "@mantine/core";
import Markdown from "react-markdown";
import { ThinkingBlock } from "./ThinkingBlock";
import { ToolCallTrace } from "./ToolCallTrace";
import { toggleToolCallRow } from "./chatPaneState";
import type { ChatPaneState, RenderedMessage } from "./chatPaneState";

/**
 * One rendered transcript message (027 → step 006). A PURE EXTRACTION of the
 * per-message JSX that lived inline in `MessageList`'s map — no visual or
 * behavioural change:
 *
 * - a `user` row is a `Box data-role="user"` (flex, `justifyContent: flex-end`)
 *   wrapping the filled, right-offset `Paper` bubble (`maxWidth: 70%`, theme
 *   `filled` / `contrast` tokens) with the content in a `pre-wrap` `Text`;
 * - an `assistant` row is a `Stack data-role="assistant"` holding, in order, the
 *   `ThinkingBlock` (only when `message.reasoning` is non-null and non-empty),
 *   the `ToolCallTrace` (always rendered; it returns `null` for an empty trace,
 *   expansion keyed by `expandedToolCallRows` with `rowKeyPrefix={message.key}`,
 *   toggled through `toggleToolCallRow`), and the `Box className="chat-markdown"`
 *   body around `<Markdown>`.
 *
 * The reasoning-expansion lookup is the existing one: a streaming row reads
 * `state.liveThinkingExpanded`, a persisted row reads
 * `state.expandedReasoning[message.key] ?? false`; the toggle writes the same
 * slot back. The `data-role` hooks are the delivered authorship contract
 * (US-095.AC-2) and stay on the wrapping element.
 *
 * Used by both `MessageList` (main-line rows) and `SideChatGroup` (the rows of
 * one side chat), so a message looks the same wherever it lands. Holds no
 * `useEffect` and no local state (frontend.md leaf rule); the parent supplies
 * the key.
 *
 * SKELETON (027/006): props frozen; body throws — the coder moves the JSX out
 * of `MessageList.tsx` verbatim.
 */
export interface MessageRowProps {
  /** The pane state — read for reasoning / tool-call expansion, written by the toggles. */
  state: ChatPaneState;
  /** The message to render (a persisted row or the in-flight bubble). */
  message: RenderedMessage;
}

export const MessageRow = observer(function MessageRow({ state, message }: MessageRowProps) {
  if (message.role === "user") {
    return (
      <Box
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
            {message.content}
          </Text>
        </Paper>
      </Box>
    );
  }

  const hasReasoning = message.reasoning !== null && message.reasoning !== "";
  const expanded = message.streaming
    ? state.liveThinkingExpanded
    : (state.expandedReasoning[message.key] ?? false);
  const toggle = () => {
    if (message.streaming) {
      state.liveThinkingExpanded = !state.liveThinkingExpanded;
    } else {
      state.expandedReasoning[message.key] = !(state.expandedReasoning[message.key] ?? false);
    }
  };

  // F3: no `Divider`, no "Assistant" label — the wrapping `Stack` and its
  // `data-role` stay, and the thinking region and markdown body are as
  // delivered.
  return (
    <Stack gap={4} data-role="assistant">
      {hasReasoning && (
        <ThinkingBlock text={message.reasoning ?? ""} expanded={expanded} onToggle={toggle} />
      )}
      {/* 024: the tool-call trace sits in the same per-message slot as the
          thinking region and above the body — what the assistant DID
          before it answered, in call order. It renders `null` when the
          message has no trace, so it needs no condition here, and its
          expansion map is keyed by (message key, row index), which the
          in-flight bubble's sentinel key serves unchanged. */}
      <ToolCallTrace
        rows={message.toolTrace}
        expanded={state.expandedToolCallRows}
        rowKeyPrefix={message.key}
        onToggle={(rowKey) => toggleToolCallRow(state, rowKey)}
      />
      <Box className="chat-markdown" fz="sm">
        <Markdown>{message.content}</Markdown>
      </Box>
    </Stack>
  );
});
