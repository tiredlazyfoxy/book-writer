import { useEffect, useState } from "react";
import { observer } from "mobx-react-lite";
import { Alert, Button, Checkbox, Modal, ScrollArea, Stack } from "@mantine/core";
import type { LlmServer } from "../../../types/llmServers";
import { ModelsModalDraft, probeModelsAction, submitEnabledModels } from "./modelsModalDraft";

interface ModelsModalProps {
  opened: boolean;
  server: LlmServer;
  onClose: () => void;
  onSaved: () => void;
}

/**
 * Enable-models modal. Fresh seeded draft per open; PROBES ON OPEN via a mount-load
 * `useEffect`. Renders `available ∪ already-enabled` as a checkbox list so a failed
 * probe keeps prior selections; the probe error is shown in-modal without clearing
 * the selection (D9). Save calls `submitEnabledModels` (US-012). This skeleton
 * renders the wired shell and compiles — the coder fills the effect fns.
 */
export const ModelsModal = observer(function ModelsModal({
  opened,
  server,
  onClose,
  onSaved,
}: ModelsModalProps) {
  const [draft] = useState(() => new ModelsModalDraft(server.enabled_models));

  useEffect(() => {
    const ctrl = new AbortController();
    void probeModelsAction(draft, server.id, ctrl.signal);
    return () => ctrl.abort();
  }, [draft, server.id]);

  const models = Array.from(new Set([...draft.available, ...server.enabled_models])).sort();

  const handleSave = async () => {
    const ctrl = new AbortController();
    await submitEnabledModels(draft, server.id, onSaved, ctrl.signal);
    if (draft.saveStatus === "ready") onClose();
  };

  return (
    <Modal opened={opened} onClose={onClose} title={`Select models — ${server.name}`} size="md">
      <Stack>
        {draft.probeError && <Alert color="red">{draft.probeError}</Alert>}
        {draft.saveError && <Alert color="red">{draft.saveError}</Alert>}
        <ScrollArea.Autosize mah={360}>
          <Stack gap="xs">
            {models.map((m) => (
              <Checkbox
                key={m}
                label={m}
                checked={draft.selected.has(m)}
                onChange={(e) => {
                  const next = new Set(draft.selected);
                  if (e.currentTarget.checked) next.add(m);
                  else next.delete(m);
                  draft.selected = next;
                }}
              />
            ))}
          </Stack>
        </ScrollArea.Autosize>
        <Button onClick={handleSave} disabled={!draft.canSubmit}>
          Save
        </Button>
      </Stack>
    </Modal>
  );
});
