import { observer } from "mobx-react-lite";
import { ActionIcon, Alert, Button, Group, Stack, Textarea } from "@mantine/core";
import { IconPlayerStop, IconSend } from "@tabler/icons-react";
import type { ChatPaneState } from "./chatPaneState";

/**
 * The prompt composer at the foot of the conversation: a Mantine `Textarea` bound
 * to `state.pendingPrompt`, a send control (enabled only when `state.canSend`), a
 * stop control shown while `state.turnStatus === "streaming"`, and an error banner
 * (from `state.turnError`) carrying a retry action when `state.retryOffered`. The
 * input clears only once a send is accepted, so a failed send never eats the text.
 * `onSend` / `onStop` / `onRetry` are wired by `ChatPane` to the turn effect
 * functions (`sendChatTurn` / `stopChatTurn` / `retryChatTurn`).
 *
 * 023 ADDS THE KEYBOARD SEND (D10): `Ctrl`+`Enter` / `Cmd`+`Enter` sends exactly
 * when the Send button would, and PLAIN `Enter` is untouched — it still inserts a
 * newline, because this is a composer for prose, not a one-line input. `metaKey` is
 * there so the app works on macOS even though development is Windows-only. Follows
 * `ChatResizeHandle.tsx`, the repo's only other `onKeyDown`.
 *
 * THE SEND CONTROL LIVES INSIDE THE INPUT (feedback F4). It used to be a `Button` in
 * a `<Group justify="flex-end">` row of its own below the textarea — a full-width row
 * whose only content was one button, and a row of vertical height the transcript
 * wanted back (continuous with F1). It is now an icon in the textarea's
 * `rightSection`, anchored BOTTOM-RIGHT and staying there as the input autosizes 2→6
 * rows; Stop swaps into the same slot while streaming, so no control row survives for
 * it either. Nothing about what the controls DO changed — same handlers, same gates,
 * same swap condition.
 *
 * Three Mantine facts this arrangement depends on, none of them obvious:
 * - `rightSectionPointerEvents` defaults to **`"none"`**, so without the explicit
 *   `"all"` below the icon would render and be completely dead to the pointer — and
 *   `fireEvent`-based tests would not notice, because they dispatch without hit
 *   testing. Stop, in particular, must be clickable at exactly the moment the input
 *   itself is disabled.
 * - the section is `position: absolute` spanning `top: 1px` to `bottom: 1px` with
 *   `align-items: center`, so it RE-CENTRES as the textarea grows. `rightSectionProps`
 *   overrides that alignment to `flex-end`, which is what pins the icon to the corner
 *   at every height.
 * - Mantine's disabled-input styling targets the input element, not its sections, so
 *   the streaming Stop is neither dimmed nor blocked by `disabled` on the `Textarea`.
 *
 * Accessible names are the contract here: an icon control renders no text, so
 * `aria-label` IS its accessible name. Stop's must keep matching `/stop/i`.
 */
export interface ComposerProps {
  state: ChatPaneState;
  onSend: () => void;
  onStop: () => void;
  onRetry: () => void;
}

export const Composer = observer(function Composer({
  state,
  onSend,
  onStop,
  onRetry,
}: ComposerProps) {
  const streaming = state.turnStatus === "streaming";
  // 016: read-only for the WHOLE `closing` window, driven by `work/closeTurn.ts`'s
  // signal rather than by "a stream is running", so a page reload mid-close still
  // renders it read-only with no stream at all (DoD-9). The reason is READABLE TEXT
  // beside the input, never a visual state.
  const closeReadOnly = state.isComposerReadOnly;

  return (
    // F1: the composer keeps its natural height. `MessageList` grows from a zero
    // flex basis, so it absorbs no shrinkage — which makes this the item the column
    // would squeeze first when the pane is short or the retry / read-only banners are
    // showing. `flexShrink: 0` is what pins it to the bottom edge intact at any pane
    // height; nothing about its controls or gating changes.
    <Stack gap="xs" style={{ flexShrink: 0 }}>
      {closeReadOnly && state.composerReadOnlyReason !== null && (
        <Alert color="yellow" title="The assistant is closing a chapter">
          {state.composerReadOnlyReason}
        </Alert>
      )}

      {state.retryOffered && state.turnError !== null && (
        <Alert color="red" title="Turn failed">
          <Group justify="space-between" wrap="nowrap" gap="sm">
            <span>{state.turnError}</span>
            <Button size="xs" variant="light" onClick={onRetry}>
              Retry
            </Button>
          </Group>
        </Alert>
      )}

      <Textarea
        placeholder="Message the assistant…"
        aria-label="Message the assistant"
        autosize
        minRows={2}
        maxRows={6}
        value={state.pendingPrompt}
        disabled={streaming || closeReadOnly}
        // An explicit width makes the slot deterministic: the default derives from
        // `--input-height`, which an autosizing textarea does not have a fixed value
        // for. It also drives the input's own padding, so typed text never runs
        // underneath the icon.
        rightSectionWidth={40}
        // Without this the section is `pointer-events: none` (Mantine's default) and
        // the icon is inert — see the note above.
        rightSectionPointerEvents="all"
        // BOTTOM-RIGHT, not centred: the section spans the input's full height, so
        // aligning its content to the end is what keeps the icon in the corner as the
        // textarea grows from 2 rows to 6.
        rightSectionProps={{
          style: { alignItems: "flex-end", paddingBottom: 4 },
        }}
        rightSection={
          streaming && !closeReadOnly ? (
            <ActionIcon
              color="red"
              variant="light"
              onClick={onStop}
              // The accessible name Stop is queried by — an icon control has no text.
              aria-label="Stop"
            >
              <IconPlayerStop size={18} stroke={1.5} />
            </ActionIcon>
          ) : (
            // While a close runs the pane offers NO stop of its own: aborting the
            // stream alone would leave the chapter `closing` server-side, so the
            // author's exit is the chapter page's Stop, which also posts
            // `close/cancel` (decision D4). The composer shows Send, disabled.
            <ActionIcon
              variant="light"
              onClick={onSend}
              // `canSend` does NOT itself account for the close window — the pane
              // ANDs `closeReadOnly` in here, and the keyboard path below repeats the
              // same pair. Both must stay written out.
              disabled={!state.canSend || closeReadOnly}
              aria-label="Send"
            >
              <IconSend size={18} stroke={1.5} />
            </ActionIcon>
          )
        }
        onChange={(event) => {
          state.pendingPrompt = event.currentTarget.value;
        }}
        onKeyDown={(event) => {
          // PLAIN `Enter` falls through untouched and inserts a newline; only the
          // modifier combination is ours.
          if (event.key !== "Enter") return;
          if (!event.ctrlKey && !event.metaKey) return;
          event.preventDefault();
          // The SAME gate the Send button uses, so the shortcut can never do what
          // the button cannot: no send while a turn streams, none while the close
          // window holds the composer read-only, none with an empty prompt.
          if (!state.canSend || closeReadOnly) return;
          onSend();
        }}
      />
    </Stack>
  );
});
