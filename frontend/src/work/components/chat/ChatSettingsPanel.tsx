import { observer } from "mobx-react-lite";
import { Alert, NumberInput, Select, Stack } from "@mantine/core";
import type { ModelOptionResponse } from "../../../types/chats";
import {
  MAX_TEMPERATURE,
  MIN_TEMPERATURE,
  modelOptionKey,
  type ChatModelSettingsDraft,
} from "./chatPaneState";

/**
 * The model-picker + temperature form, used TWICE: inside the new-chat form and
 * as the active chat's editable settings. Renders the model picker (options
 * grouped/labelled by server name) and a temperature control, plus validation
 * messages. NO other sampling param is rendered — the rest are persisted and
 * untouched (feature decision 4). Mutates the passed `draft` in place.
 *
 * SKELETON (011/004): props frozen; body throws.
 */
export interface ChatSettingsPanelProps {
  /** The `(server, model)` options from the model-options call. */
  options: ModelOptionResponse[];
  /** The draft edited in place (new-chat draft or the settings draft). */
  draft: ChatModelSettingsDraft;
  /** Merged client + server validation messages for this surface. */
  errors: Record<string, string>;
}

export const ChatSettingsPanel = observer(function ChatSettingsPanel({
  options,
  draft,
  errors,
}: ChatSettingsPanelProps) {
  // No enabled model on any server the author can reach → composing is refused
  // (UC-054 exception flow): show a message instead of an empty picker.
  if (options.length === 0) {
    return (
      <Alert color="yellow" variant="light">
        No models are available. An administrator must enable a model on a server
        before you can start a chat.
      </Alert>
    );
  }

  const data = options.map((option) => ({
    value: modelOptionKey(option),
    label: `${option.server_name} · ${option.model_name}`,
  }));

  return (
    <Stack gap="xs">
      <Select
        label="Model"
        placeholder="Choose a model"
        data={data}
        value={draft.optionKey}
        onChange={(value) => {
          draft.optionKey = value;
        }}
        error={errors.model}
      />
      <NumberInput
        label="Temperature"
        value={draft.temperature}
        min={MIN_TEMPERATURE}
        max={MAX_TEMPERATURE}
        step={0.1}
        decimalScale={2}
        onChange={(value) => {
          draft.temperature = typeof value === "number" ? value : Number(value);
        }}
        error={errors.temperature}
      />
    </Stack>
  );
});
