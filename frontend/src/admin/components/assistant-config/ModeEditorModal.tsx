import { useState } from "react";
import { observer } from "mobx-react-lite";
import {
  Alert,
  Button,
  Checkbox,
  Group,
  Modal,
  ScrollArea,
  Stack,
  Text,
  Textarea,
} from "@mantine/core";
import { modeLabel } from "../../../api/assistantConfig";
import type { AssistantMode, AssistantTool, SubAgent } from "../../../types/assistantConfig";
import { ModeEditorDraft, submitModeEditor } from "./modeEditorDraft";

interface ModeEditorModalProps {
  opened: boolean;
  /** The mode being edited. Modes are never created, so there is no `null` case. */
  mode: AssistantMode;
  /** The backend tool catalogue — may be empty (the registry has one entry today). */
  tools: AssistantTool[];
  /** Every sub-agent; `disabled` ones must NOT be offered in the picker. */
  subAgents: SubAgent[];
  onClose: () => void;
  onSaved: () => void;
}

/**
 * Per-mode editor modal (`ServerFormModal.tsx:17-25` props shape). Mounted
 * **conditionally** by `AssistantModesPage`, so each open constructs a fresh
 * `ModeEditorDraft`. Saves the system prompt, the tool selection and the
 * accessible-sub-agent selection in one full-replace call.
 *
 * Body order: the `form` `<Alert color="red">` first (server errors are whole-form
 * here), the read-only mode label, the optional system-prompt `<Textarea>`, then the
 * two pickers (`ScrollArea.Autosize mah={360}` → `Stack gap="xs"` → one `Checkbox`
 * per entry; every toggle reassigns a fresh `Set`, since a `Set` mutated in place is
 * not observable to MobX). Both pickers render an explanatory line rather than a
 * blank box when they have nothing to offer — nothing here assumes the catalogue has
 * any particular size.
 */
export const ModeEditorModal = observer(function ModeEditorModal({
  opened,
  mode,
  tools,
  subAgents,
  onClose,
  onSaved,
}: ModeEditorModalProps) {
  const [draft] = useState(() => new ModeEditorDraft(mode, tools, subAgents));

  const handleSubmit = async () => {
    const ctrl = new AbortController();
    await submitModeEditor(draft, mode.key, onSaved, ctrl.signal);
    if (draft.submitStatus === "ready") onClose();
  };

  // A disabled sub-agent may not be attached to a mode, so it is never offered.
  const offeredSubAgents = subAgents.filter((subAgent) => !subAgent.disabled);
  // A selected id with no entry in the loaded list is still shown — as the raw id —
  // so a stale cache is visible instead of silently dropping the selection.
  const knownSubAgentIds = new Set(subAgents.map((subAgent) => subAgent.id));
  const orphanSubAgentIds = Array.from(draft.selectedSubAgents).filter(
    (id) => !knownSubAgentIds.has(id),
  );

  const toggleTool = (name: string, checked: boolean) => {
    const next = new Set(draft.selectedTools);
    if (checked) next.add(name);
    else next.delete(name);
    draft.selectedTools = next;
  };

  const toggleSubAgent = (id: string, checked: boolean) => {
    const next = new Set(draft.selectedSubAgents);
    if (checked) next.add(id);
    else next.delete(id);
    draft.selectedSubAgents = next;
  };

  return (
    <Modal opened={opened} onClose={onClose} title="Edit mode" size="lg">
      <Stack>
        {draft.errors.form && <Alert color="red">{draft.errors.form}</Alert>}

        {/* Read-only heading — the mode's human label, from the api module's map. */}
        <Text fw={600}>{modeLabel(mode.key)}</Text>

        <Textarea
          label="System prompt"
          description="Optional — leave empty for no mode-specific prompt."
          placeholder="Instructions the assistant follows in this mode"
          autosize
          minRows={6}
          maxRows={16}
          value={draft.systemPrompt}
          onChange={(e) => {
            draft.systemPrompt = e.currentTarget.value;
          }}
          error={draft.errors.system_prompt}
        />

        <Stack gap="xs">
          <Text size="sm" fw={500}>
            Tools
          </Text>
          {tools.length === 0 ? (
            <Text size="sm" c="dimmed">
              No tools are available to select. This mode will run with no tools.
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
            Sub-agents
          </Text>
          {offeredSubAgents.length === 0 && orphanSubAgentIds.length === 0 ? (
            <Text size="sm" c="dimmed">
              No sub-agents are available to select. This mode may delegate to none.
            </Text>
          ) : (
            <ScrollArea.Autosize mah={360}>
              <Stack gap="xs">
                {offeredSubAgents.map((subAgent) => (
                  <Checkbox
                    key={subAgent.id}
                    label={subAgent.name}
                    checked={draft.selectedSubAgents.has(subAgent.id)}
                    onChange={(e) => toggleSubAgent(subAgent.id, e.currentTarget.checked)}
                  />
                ))}
                {orphanSubAgentIds.map((id) => (
                  <Checkbox
                    key={id}
                    label={id}
                    checked={draft.selectedSubAgents.has(id)}
                    onChange={(e) => toggleSubAgent(id, e.currentTarget.checked)}
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
