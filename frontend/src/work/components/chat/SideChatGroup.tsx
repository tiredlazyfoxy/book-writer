import { observer } from "mobx-react-lite";
import { ActionIcon, Group, Paper, Stack, Text } from "@mantine/core";
import {
  IconArrowBackUp,
  IconChevronDown,
  IconChevronRight,
  IconTrash,
} from "@tabler/icons-react";
import { MessageRow } from "./MessageRow";
import {
  injectSideChat,
  requestDeleteSideChat,
  toggleSideChatGroup,
} from "./chatPaneState";
import type { ChatPaneState, RenderedTranscriptSideChatItem } from "./chatPaneState";

/**
 * One side chat in the transcript (027 → FEAT-022; UC-110, UC-111, UC-112,
 * UC-113; US-135, US-137, US-139, US-140) — a contiguous run of messages sharing
 * a `sideChatId`, rendered as ONE visibly set-apart block.
 *
 * Contract (every name below is a test handle — `context.md` → D-F):
 *
 * - Container: a bordered `Paper` / `Box` with `role="group"` and
 *   `aria-label="Side chat"` for BOTH an active and a finished group. Specs find
 *   it by role and accessible name, never by test id.
 * - Header `Group`, holding:
 *   - a label `Text` reading `Side chat` when `group.active`, and
 *     `Side chat · N messages` (N = `group.messages.length`; the product-D7
 *     placeholder) when finished;
 *   - an expand / collapse control (`ActionIcon` or `UnstyledButton`) rendered
 *     ONLY for a finished group (`!group.active`). It is ONE control whose
 *     `aria-label` SWAPS with state — `Expand side chat` while collapsed,
 *     `Collapse side chat` while expanded — like Send / Stop; never two controls
 *     with one hidden. Click → `toggleSideChatGroup(state, group.sideChatId)`.
 *   - two `ActionIcon`s, `aria-label="Inject side chat"` and
 *     `aria-label="Delete side chat"`, both `disabled` when
 *     `!state.sideChatActionsEnabled` OR `bookId` is `undefined` (D1 — actions
 *     unavailable while the assistant is answering, a close is active, or an
 *     action is already in flight). Inject →
 *     `injectSideChat(state, bookId, group.sideChatId)`; Delete →
 *     `requestDeleteSideChat(state, group.sideChatId)` (opens step 007's
 *     confirmation; calls no api).
 * - Body: one {@link import("./MessageRow").MessageRow} per `group.messages`
 *   entry, keyed by `message.key`, rendered ONLY when `group.expanded`.
 *   Collapsed renders the header alone — conditional rendering, NO Mantine
 *   `Collapse`, NO `Accordion` (the Mantine inventory rule). The active group is
 *   always `expanded`, so the in-flight bubble lands inside it (UC-110 step 3).
 *
 * Holds no `useEffect`, no local state, no hooks (frontend.md leaf rule):
 * expansion lives in `state.expandedSideChats`, the actions are the external
 * effect functions of `chatPaneState.ts`.
 *
 * SKELETON (027/006): props frozen; body throws.
 */
export interface SideChatGroupProps {
  /** The pane state — read for `sideChatActionsEnabled`; the actions write to it. */
  state: ChatPaneState;
  /**
   * The current book id, needed by `injectSideChat`. `undefined` until step 007
   * wires it through `ChatPane` → `MessageList`; while absent the Inject and
   * Delete controls render disabled.
   */
  bookId: string | undefined;
  /** The side-chat transcript item from `state.renderedTranscript`. */
  group: RenderedTranscriptSideChatItem;
}

export const SideChatGroup = observer(function SideChatGroup({
  state,
  bookId,
  group,
}: SideChatGroupProps) {
  // D1 plus the forward-only book-id split: an action is unavailable while the
  // assistant is answering / a close is active / an action is in flight, and
  // equally while the book id has not been wired through yet (step 007).
  const actionsDisabled = !state.sideChatActionsEnabled || bookId === undefined;

  return (
    <Paper
      role="group"
      // The accessible name is the SAME for an active and a finished group — the
      // differing wording lives in the visible header label below.
      aria-label="Side chat"
      withBorder
      radius="md"
      p="xs"
      // Set apart from the main line: the border plus a recessed surface, so a
      // group reads as one block even when collapsed to its header.
      bg="var(--mantine-color-default)"
    >
      <Stack gap="sm">
        <Group gap={4} wrap="nowrap" justify="space-between">
          <Text size="xs" c="dimmed" fw={600}>
            {group.active ? "Side chat" : `Side chat · ${group.messages.length} messages`}
          </Text>
          <Group gap={4} wrap="nowrap">
            {/* ONE control whose name swaps with state (the Send / Stop idiom),
                and only for a finished group — an active one is always
                expanded, so it has nothing to collapse. */}
            {!group.active && (
              <ActionIcon
                variant="subtle"
                size="sm"
                aria-label={group.expanded ? "Collapse side chat" : "Expand side chat"}
                aria-expanded={group.expanded}
                onClick={() => toggleSideChatGroup(state, group.sideChatId)}
              >
                {group.expanded ? (
                  <IconChevronDown size={14} stroke={1.5} />
                ) : (
                  <IconChevronRight size={14} stroke={1.5} />
                )}
              </ActionIcon>
            )}
            <ActionIcon
              variant="subtle"
              size="sm"
              aria-label="Inject side chat"
              disabled={actionsDisabled}
              onClick={() => {
                if (bookId === undefined) {
                  return;
                }
                void injectSideChat(state, bookId, group.sideChatId);
              }}
            >
              <IconArrowBackUp size={14} stroke={1.5} />
            </ActionIcon>
            {/* Delete only ASKS here — the confirmation `Modal` is step 007's,
                and this call reaches no api. */}
            <ActionIcon
              variant="subtle"
              size="sm"
              color="red"
              aria-label="Delete side chat"
              disabled={actionsDisabled}
              onClick={() => requestDeleteSideChat(state, group.sideChatId)}
            >
              <IconTrash size={14} stroke={1.5} />
            </ActionIcon>
          </Group>
        </Group>

        {/* Plain conditional rendering — no `Collapse`, no `Accordion`
            (the Mantine inventory rule). A collapsed group's messages are
            genuinely absent from the tree, not merely hidden. */}
        {group.expanded &&
          group.messages.map((message) => (
            <MessageRow key={message.key} state={state} message={message} />
          ))}
      </Stack>
    </Paper>
  );
});
