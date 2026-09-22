import { useState } from "react";
import { observer } from "mobx-react-lite";
import {
  Alert,
  Button,
  Modal,
  Select,
  Stack,
  Textarea,
  TextInput,
} from "@mantine/core";
import { COLLABORATION_MODE_OPTIONS, VISIBILITY_OPTIONS } from "../../../api/books";
import type { CollaborationMode, Visibility } from "../../../types/books";
import { CreateBookDraft, submitCreateBook } from "./createBookDraft";

interface CreateBookModalProps {
  opened: boolean;
  onClose: () => void;
  onCreated: () => void;
}

/**
 * Create-book modal (Shell bookshelf). `observer`; holds the draft via
 * `useState(() => new CreateBookDraft())`. Inputs bind `value` / `onChange` to the
 * draft fields and read `error` from `draft.errors`; the submit routes through the
 * external `submitCreateBook` and closes the modal on success. Open/target flags
 * are the parent page's component-local `useState`, passed in as props. Template =
 * admin `CreateUserModal`.
 */
export const CreateBookModal = observer(function CreateBookModal({
  opened,
  onClose,
  onCreated,
}: CreateBookModalProps) {
  const [draft] = useState(() => new CreateBookDraft());

  const handleSubmit = async () => {
    const ctrl = new AbortController();
    await submitCreateBook(draft, onCreated, ctrl.signal);
    if (draft.submitStatus === "ready") onClose();
  };

  return (
    <Modal opened={opened} onClose={onClose} title="Create book" size="md">
      <Stack>
        {draft.errors.form && <Alert color="red">{draft.errors.form}</Alert>}
        <TextInput
          label="Title"
          value={draft.title}
          onChange={(e) => {
            draft.title = e.currentTarget.value;
          }}
          error={draft.errors.title}
        />
        <Textarea
          label="Description"
          value={draft.description}
          onChange={(e) => {
            draft.description = e.currentTarget.value;
          }}
          error={draft.errors.description}
        />
        <Select
          label="Collaboration mode"
          data={COLLABORATION_MODE_OPTIONS}
          value={draft.collaborationMode}
          onChange={(v) => {
            if (v) draft.collaborationMode = v as CollaborationMode;
          }}
          error={draft.errors.collaboration_mode}
        />
        <Select
          label="Visibility"
          data={VISIBILITY_OPTIONS}
          value={draft.visibility}
          onChange={(v) => {
            if (v) draft.visibility = v as Visibility;
          }}
          error={draft.errors.visibility}
        />
        <Button onClick={handleSubmit} disabled={!draft.canSubmit}>
          Create
        </Button>
      </Stack>
    </Modal>
  );
});
