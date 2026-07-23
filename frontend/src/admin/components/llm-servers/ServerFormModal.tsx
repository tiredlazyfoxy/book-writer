import { useState } from "react";
import { observer } from "mobx-react-lite";
import {
  Alert,
  Button,
  Modal,
  PasswordInput,
  Select,
  Stack,
  Switch,
  TextInput,
} from "@mantine/core";
import { BACKEND_OPTIONS } from "../../../api/llmServers";
import type { LlmBackendType, LlmServer } from "../../../types/llmServers";
import { ServerFormDraft, submitServerForm } from "./serverFormDraft";

interface ServerFormModalProps {
  opened: boolean;
  /** null = create; non-null = edit (seeds the draft). */
  server: LlmServer | null;
  onClose: () => void;
  onSaved: () => void;
  /** Edit-mode only: hand off to the models modal for the target server. */
  onSelectModels: (server: LlmServer) => void;
}

/**
 * Create/edit LLM-server form modal. Fresh seeded draft per open (conditional mount
 * from the page). Fields wired to the draft; the effectful submit is
 * `submitServerForm`. This skeleton renders the wired shell and compiles — the coder
 * fills `submitServerForm` (currently throws).
 */
export const ServerFormModal = observer(function ServerFormModal({
  opened,
  server,
  onClose,
  onSaved,
  onSelectModels,
}: ServerFormModalProps) {
  const [draft] = useState(() => new ServerFormDraft(server));

  const handleSubmit = async () => {
    const ctrl = new AbortController();
    await submitServerForm(draft, server ? server.id : null, onSaved, ctrl.signal);
    if (draft.submitStatus === "ready") onClose();
  };

  const handleSelectModels = () => {
    onClose();
    if (server) onSelectModels(server);
  };

  return (
    <Modal opened={opened} onClose={onClose} title={server ? "Edit server" : "Add server"} size="md">
      <Stack>
        {draft.errors.form && <Alert color="red">{draft.errors.form}</Alert>}
        <TextInput
          label="Name"
          value={draft.name}
          onChange={(e) => {
            draft.name = e.currentTarget.value;
          }}
          error={draft.errors.name}
        />
        <Select
          label="Backend type"
          data={BACKEND_OPTIONS}
          value={draft.backendType}
          onChange={(v) => {
            if (v) draft.backendType = v as LlmBackendType;
          }}
        />
        <TextInput
          label="Base URL"
          value={draft.baseUrl}
          onChange={(e) => {
            draft.baseUrl = e.currentTarget.value;
          }}
          error={draft.errors.base_url}
        />
        <PasswordInput
          label="API key"
          value={draft.apiKey}
          onChange={(e) => {
            draft.apiKey = e.currentTarget.value;
          }}
          error={draft.errors.api_key}
        />
        <Switch
          label="Active"
          checked={draft.isActive}
          onChange={(e) => {
            draft.isActive = e.currentTarget.checked;
          }}
        />
        {server && (
          <Button variant="default" onClick={handleSelectModels}>
            Select Models
          </Button>
        )}
        <Button onClick={handleSubmit} disabled={!draft.canSubmit}>
          Save
        </Button>
      </Stack>
    </Modal>
  );
});
