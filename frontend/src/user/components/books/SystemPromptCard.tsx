import { observer } from "mobx-react-lite";
import { Alert, Button, Group, Loader, Stack, Text, Textarea, Title } from "@mantine/core";
import {
  loadSystemPrompt,
  saveSystemPrompt,
  type BookSettingsPageState,
} from "../../pages/bookSettingsPageState";

/**
 * The per-author system-prompt editor on `BookSettingsPage`. A page-aware `observer`
 * component taking the page-state slice it edits (frontend.md — "page-aware
 * components take state slices"); it owns no state of its own, and the draft it binds
 * to lives in `BookSettingsPageState` because this editor shares the page's mount.
 *
 * Renders, from the `systemPrompt` trio: the loading branch, the error branch **with a
 * retry** (and no editor bound to stale data), and otherwise a multi-line editor bound
 * to `state.systemPromptDraft`, a save control gated on `state.canSaveSystemPrompt`, a
 * server-error surface fed from `state.systemPromptServerErrors` (distinct from the
 * load trio's `systemPromptError`), and one line of copy telling the author **this
 * prompt is theirs alone — every author of the book keeps their own**. An empty prompt
 * is a normal, editable state, not an error state, and there is **no delete control**:
 * saving an empty editor is how a prompt is cleared.
 *
 * Handlers are inner functions closing over `state` and props — no extracted callbacks,
 * no `useCallback`, no hooks of any kind in this component.
 *
 * `bookId` is a prop rather than state because the page owns the route param and the
 * two effect functions are keyed by it; the card spins its own `AbortController` per
 * action, exactly as the page's other controls do.
 */
export interface SystemPromptCardProps {
  /** The settings-page state whose `systemPrompt*` slice this card reads and edits. */
  state: BookSettingsPageState;
  /** The book whose prompt is being edited — the route param, `""` when absent. */
  bookId: string;
}

export const SystemPromptCard = observer(function SystemPromptCard({
  state,
  bookId,
}: SystemPromptCardProps) {
  // Inner handlers closing over `state` / `bookId`; each spins its own controller,
  // exactly as the page's other controls do.
  const handleRetry = () => {
    const ctrl = new AbortController();
    void loadSystemPrompt(state, bookId, ctrl.signal);
  };

  const handleSave = () => {
    const ctrl = new AbortController();
    void saveSystemPrompt(state, bookId, ctrl.signal);
  };

  const loading =
    state.systemPromptStatus === "idle" || state.systemPromptStatus === "loading";

  return (
    <Stack gap="xs">
      <Title order={5}>Your system prompt</Title>
      <Text size="sm" c="dimmed">
        This prompt is per-author: it is yours alone. Every author of this book keeps their
        own, and yours is used only in your own chats — never in another author's.
      </Text>

      {loading ? (
        <Group py="xs">
          <Loader size="sm" />
        </Group>
      ) : state.systemPromptStatus === "error" ? (
        <Alert color="red">
          <Stack gap="xs" align="flex-start">
            <Text size="sm">
              {state.systemPromptError ?? "Could not load your system prompt."}
            </Text>
            <Button size="xs" variant="light" onClick={handleRetry}>
              Retry
            </Button>
          </Stack>
        </Alert>
      ) : (
        <>
          {state.systemPromptServerErrors.form && (
            <Alert color="red">{state.systemPromptServerErrors.form}</Alert>
          )}
          <Textarea
            label="System prompt"
            placeholder="Write the instructions your assistant should follow for this book."
            value={state.systemPromptDraft}
            autosize
            minRows={6}
            error={state.systemPromptServerErrors.system_prompt}
            onChange={(event) => {
              state.systemPromptDraft = event.currentTarget.value;
            }}
          />
          <Group>
            <Button onClick={handleSave} disabled={!state.canSaveSystemPrompt}>
              Save
            </Button>
          </Group>
        </>
      )}
    </Stack>
  );
});
