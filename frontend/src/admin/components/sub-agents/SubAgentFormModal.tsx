import { useState } from "react";
import { observer } from "mobx-react-lite";
import {
  Alert,
  Button,
  Checkbox,
  Group,
  Modal,
  ScrollArea,
  Select,
  Stack,
  Text,
  TextInput,
  Textarea,
} from "@mantine/core";
import { modeLabel } from "../../../api/assistantConfig";
import type { AssistantMode, AssistantTool, SubAgent } from "../../../types/assistantConfig";
import type { LlmServer } from "../../../types/llmServers";
import { SubAgentFormDraft, applyModelOption, submitSubAgentForm } from "./subAgentFormDraft";

interface SubAgentFormModalProps {
  opened: boolean;
  /** null = create; non-null = edit (seeds the draft). */
  subAgent: SubAgent | null;
  /** The backend tool catalogue — may be empty (the registry has one entry today). */
  tools: AssistantTool[];
  /** The fixed five modes, for the accessible-modes picker (labelled via `modeLabel`). */
  modes: AssistantMode[];
  /** Every LLM server; only `is_active` ones contribute model options. */
  servers: LlmServer[];
  onClose: () => void;
  onSaved: () => void;
}

/**
 * Create/edit sub-agent form modal (`ServerFormModal.tsx:17-25` props shape). Mounted
 * **conditionally** by `SubAgentsPage`, so each open constructs a fresh
 * `SubAgentFormDraft`. Saves name, system prompt, the model assignment, the tool
 * selection and the accessible-mode selection in one full-replace call.
 *
 * Body order: the `form` `<Alert color="red">` first, the name `<TextInput>` bound to
 * `draft.errors.name`, the system-prompt `<Textarea>`, the model `<Select>` driven by
 * `draft.modelOptions` / `draft.modelValue` / `applyModelOption` with "Inherit the main
 * chat's model" as the default choice, then the two pickers in the established idiom
 * (`ScrollArea.Autosize mah={360}` → `Stack gap="xs"` → one `Checkbox` each; every
 * toggle reassigns a fresh `Set`, since a `Set` mutated in place is not observable to
 * MobX), then Cancel / Save. Both pickers render an explanatory line rather than a
 * blank box when they have nothing to offer — nothing here assumes the tool catalogue
 * has any particular size.
 *
 * There is deliberately **no `disabled` control here** — disable/enable is a row action
 * on the page, because it cascades (`008.context.md`).
 */
export const SubAgentFormModal = observer(function SubAgentFormModal({
  opened,
  subAgent,
  tools,
  modes,
  servers,
  onClose,
  onSaved,
}: SubAgentFormModalProps) {
  const [draft] = useState(() => new SubAgentFormDraft(subAgent, tools, modes, servers));

  const handleSubmit = async () => {
    const ctrl = new AbortController();
    await submitSubAgentForm(draft, subAgent ? subAgent.id : null, onSaved, ctrl.signal);
    if (draft.submitStatus === "ready") onClose();
  };

  const toggleTool = (name: string, checked: boolean) => {
    const next = new Set(draft.selectedTools);
    if (checked) next.add(name);
    else next.delete(name);
    draft.selectedTools = next;
  };

  const toggleMode = (key: string, checked: boolean) => {
    const next = new Set(draft.selectedModes);
    if (checked) next.add(key);
    else next.delete(key);
    draft.selectedModes = next;
  };

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={subAgent ? "Edit sub-agent" : "New sub-agent"}
      size="lg"
    >
      <Stack>
        {draft.errors.form && <Alert color="red">{draft.errors.form}</Alert>}

        <TextInput
          label="Name"
          placeholder="Continuity checker"
          value={draft.name}
          onChange={(e) => {
            draft.name = e.currentTarget.value;
          }}
          error={draft.errors.name}
        />

        <Textarea
          label="System prompt"
          description="Optional — the instructions this sub-agent runs with."
          placeholder="Instructions the sub-agent follows"
          autosize
          minRows={6}
          maxRows={16}
          value={draft.systemPrompt}
          onChange={(e) => {
            draft.systemPrompt = e.currentTarget.value;
          }}
          error={draft.errors.system_prompt}
        />

        {/* The model pair moves as one: `applyModelOption` is its only writer, so no
            interaction here can produce a half-set assignment. */}
        <Select
          label="Model"
          description="Only models enabled on an active LLM server can be assigned."
          data={draft.modelOptions}
          value={draft.modelValue}
          onChange={(value) => applyModelOption(draft, value)}
          error={draft.errors.model_name}
        />

        <Stack gap="xs">
          <Text size="sm" fw={500}>
            Tools
          </Text>
          {tools.length === 0 ? (
            <Text size="sm" c="dimmed">
              No tools are available to select. This sub-agent will run with no tools.
            </Text>
          ) : (
            <ScrollArea.Autosize mah={360}>
              <Stack gap="xs">
                {tools.map((tool) => (
                  <Checkbox
                    key={tool.name}
                    label={tool.name}
                    description={tool.description}
                    checked={draft.selectedTools.has(tool.name)}
                    onChange={(e) => toggleTool(tool.name, e.currentTarget.checked)}
                  />
                ))}
              </Stack>
            </ScrollArea.Autosize>
          )}
        </Stack>

        <Stack gap="xs">
          <Text size="sm" fw={500}>
            Accessible modes
          </Text>
          {modes.length === 0 ? (
            <Text size="sm" c="dimmed">
              No modes are available to select.
            </Text>
          ) : (
            <ScrollArea.Autosize mah={360}>
              <Stack gap="xs">
                {modes.map((mode) => (
                  <Checkbox
                    key={mode.key}
                    label={modeLabel(mode.key)}
                    checked={draft.selectedModes.has(mode.key)}
                    onChange={(e) => toggleMode(mode.key, e.currentTarget.checked)}
                  />
                ))}
              </Stack>
            </ScrollArea.Autosize>
          )}
        </Stack>

        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={!draft.canSubmit}>
            Save
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
});
