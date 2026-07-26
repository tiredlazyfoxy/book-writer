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

  return (
    <Stack gap="xs">
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
        disabled={streaming}
        onChange={(event) => {
          state.pendingPrompt = event.currentTarget.value;
        }}
      />

      <Group justify="flex-end">
        {streaming ? (
          <Button color="red" variant="light" onClick={onStop}>
            Stop
          </Button>
        ) : (
          <Button onClick={onSend} disabled={!state.canSend}>
            Send
          </Button>
        )}
      </Group>
    </Stack>
  );
});
