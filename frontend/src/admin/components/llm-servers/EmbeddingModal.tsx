import { useEffect, useState } from "react";
import { observer } from "mobx-react-lite";
import { Alert, Button, Modal, Radio, Stack } from "@mantine/core";
import type { LlmServer } from "../../../types/llmServers";
import {
  EmbeddingModalDraft,
  probeModelsAction,
  submitEmbedding,
} from "./embeddingModalDraft";

interface EmbeddingModalProps {
  opened: boolean;
  server: LlmServer;
  onClose: () => void;
  onSaved: () => void;
}

/**
 * Embedding-designation modal. Fresh seeded draft per open; PROBES ON OPEN via a
 * mount-load `useEffect`. Renders `available ∪ current-model` as a single-select
 * radio list so a failed probe keeps the prior designation visible. Submit calls
 * `setEmbedding` designating the server + model (replaces any prior, US-014). This
 * skeleton renders the wired shell and compiles — the coder fills the effect fns.
 */
export const EmbeddingModal = observer(function EmbeddingModal({
  opened,
  server,
  onClose,
  onSaved,
}: EmbeddingModalProps) {
  const [draft] = useState(() => new EmbeddingModalDraft(server.embedding_model));

  useEffect(() => {
    const ctrl = new AbortController();
    void probeModelsAction(draft, server.id, ctrl.signal);
    return () => ctrl.abort();
  }, [draft, server.id]);

  const current = server.embedding_model ? [server.embedding_model] : [];
  const models = Array.from(new Set([...draft.available, ...current])).sort();

  const handleSubmit = async () => {
    const ctrl = new AbortController();
    await submitEmbedding(draft, server.id, onSaved, ctrl.signal);
    if (draft.saveStatus === "ready") onClose();
  };

  return (
    <Modal opened={opened} onClose={onClose} title={`Set embedding — ${server.name}`} size="md">
      <Stack>
        {draft.probeError && <Alert color="red">{draft.probeError}</Alert>}
        {draft.saveError && <Alert color="red">{draft.saveError}</Alert>}
        <Radio.Group
          value={draft.selected ?? ""}
          onChange={(v) => {
            draft.selected = v || null;
          }}
        >
          <Stack gap="xs">
            {models.map((m) => (
              <Radio key={m} value={m} label={m} />
            ))}
          </Stack>
        </Radio.Group>
        <Button onClick={handleSubmit} disabled={!draft.canSubmit}>
          Save
        </Button>
      </Stack>
    </Modal>
  );
});
