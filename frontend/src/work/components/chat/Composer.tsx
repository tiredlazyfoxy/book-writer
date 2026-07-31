import { observer } from "mobx-react-lite";
import { Alert, Button, Group, Stack, Textarea } from "@mantine/core";
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
 * SKELETON (011/005): props frozen; body throws (the DoD-asserted controls are the
 * coder's).
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
    <Stack gap="xs">
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
        onChange={(event) => {
          state.pendingPrompt = event.currentTarget.value;
        }}
      />

      <Group justify="flex-end">
        {streaming && !closeReadOnly ? (
          <Button color="red" variant="light" onClick={onStop}>
            Stop
          </Button>
        ) : (
          // While a close runs the pane offers NO stop of its own: aborting the
          // stream alone would leave the chapter `closing` server-side, so the
          // author's exit is the chapter page's Stop, which also posts
          // `close/cancel` (decision D4).
          <Button onClick={onSend} disabled={!state.canSend || closeReadOnly}>
            Send
          </Button>
        )}
      </Group>
    </Stack>
  );
});
