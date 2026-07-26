import { observer } from "mobx-react-lite";
import { Box, Group, Text, UnstyledButton } from "@mantine/core";
import { IconChevronDown, IconChevronRight } from "@tabler/icons-react";

/**
 * A labelled, collapsible region showing the assistant's thinking. Fully
 * controlled and STATELESS: the parent supplies the reasoning `text`, the current
 * `expanded` flag, and an `onToggle` handler. Used for both the live stream
 * (expanded while thinking, auto-collapsed on the first content delta) and a
 * persisted message's reasoning (collapsed by default on reopen). The label makes
 * clear to the author that this is the assistant's thinking.
 *
 * SKELETON (011/005): props frozen; body throws (the DoD-asserted collapse
 * rendering is the coder's).
 */
export interface ThinkingBlockProps {
  /** The reasoning text to show when expanded. */
  text: string;
  /** Whether the region is currently expanded. */
  expanded: boolean;
  /** Toggle the expanded state (parent-owned; this component holds none). */
  onToggle: () => void;
}

export const ThinkingBlock = observer(function ThinkingBlock({
  text,
  expanded,
  onToggle,
}: ThinkingBlockProps) {
  return (
    <Box>
      <UnstyledButton
        onClick={onToggle}
        aria-expanded={expanded}
        aria-label="Toggle assistant thinking"
      >
        <Group gap={4} wrap="nowrap">
          {expanded ? (
            <IconChevronDown size={14} stroke={1.5} />
          ) : (
            <IconChevronRight size={14} stroke={1.5} />
          )}
          <Text size="xs" c="dimmed" fw={600}>
            Thinking
          </Text>
        </Group>
      </UnstyledButton>
      {expanded && (
        <Text size="xs" c="dimmed" mt={2} style={{ whiteSpace: "pre-wrap" }}>
          {text}
        </Text>
      )}
    </Box>
  );
});
