import { observer } from "mobx-react-lite";
import { NumberInput, Stack } from "@mantine/core";
import {
  MAX_TEMPERATURE,
  MIN_TEMPERATURE,
  type ChatModelSettingsDraft,
} from "./chatPaneState";

/**
 * The active chat's editable SAMPLING settings — temperature and nothing else.
 * NO other sampling param is rendered; the rest are persisted and carried through
 * untouched (011's decision 4). Mutates the passed `draft` in place.
 *
 * 023 NARROWS THIS COMPONENT: the `options` prop and the model `<Select>` are
 * GONE. Model selection moved to `ChatPane`'s own "model" popover — a plain
 * `<Select>` over `state.modelOptions` bound to `state.settingsDraft.optionKey`,
 * not this component — so the two header popovers each own one concern and the
 * empty-options refusal (UC-054's exception flow) now lives with the "+" control
 * that creates a chat, where it is actually actionable.
 *
 * SKELETON (023): props frozen (`options` dropped); the temperature control is
 * 011's, preserved unchanged.
 */
export interface ChatSettingsPanelProps {
  /** The draft edited in place (the pane's settings draft). */
  draft: ChatModelSettingsDraft;
  /** Merged client + server validation messages for this surface. */
  errors: Record<string, string>;
}

export const ChatSettingsPanel = observer(function ChatSettingsPanel({
  draft,
  errors,
}: ChatSettingsPanelProps) {
  return (
    <Stack gap="xs">
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
