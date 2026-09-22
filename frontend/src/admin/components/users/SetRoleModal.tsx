import { useState } from "react";
import { makeAutoObservable, runInAction } from "mobx";
import { observer } from "mobx-react-lite";
import { Alert, Button, Modal, Select, Stack, Text } from "@mantine/core";
import * as adminApi from "../../../api/admin";
import { ROLE_OPTIONS } from "../../../api/admin";
import { ApiError } from "../../../api/client";
import type { AdminSetRoleRequest, UserRole } from "../../../types/admin";

/**
 * Component-local draft for the change-role modal — held via
 * `useState(() => new SetRoleDraft(currentRole))`. Observable fields + pure `get`
 * computeds only; the effectful submit is the external `submitSetRole` below.
 *
 * `serverErrors` is a `Record<string, string>` keyed by field name (`role`) plus a
 * general `form` key for the self-target refusal, merged over the `errors` getter.
 */
class SetRoleDraft {
  role: UserRole;

  serverErrors: Record<string, string> = {};
  submitStatus: "idle" | "loading" | "ready" | "error" = "idle";

  constructor(initialRole: UserRole) {
    this.role = initialRole;
    makeAutoObservable(this);
  }

  /** No client-side validation (any role is valid); server errors are the only source. */
  get errors(): Record<string, string> {
    return { ...this.serverErrors };
  }

  /** True when no submit is in flight. */
  get canSubmit(): boolean {
    return this.submitStatus !== "loading";
  }
}

/**
 * Effect (unimplemented — coder fills). On success: `adminApi.setUserRole(userId, …)`,
 * then invoke `onSaved` (the page refresh) and let the modal close. On `ApiError`:
 * populate `draft.serverErrors` (400 self-target refusal, or any other refusal).
 * Abort-guarded via `signal`.
 */
export async function submitSetRole(
  draft: SetRoleDraft,
  userId: string,
  onSaved: () => void,
  signal?: AbortSignal,
): Promise<void> {
  const body: AdminSetRoleRequest = { role: draft.role };

  runInAction(() => {
    draft.serverErrors = {};
    draft.submitStatus = "loading";
  });

  try {
    await adminApi.setUserRole(userId, body, signal);
  } catch (err) {
    if (err instanceof ApiError) {
      runInAction(() => {
        draft.serverErrors =
          err.status === 400
            ? { form: err.message || "You cannot change your own role." }
            : { form: err.message || "Could not change the role." };
        draft.submitStatus = "error";
      });
      return;
    }
    if (signal?.aborted) return;
    runInAction(() => {
      draft.submitStatus = "error";
    });
    throw err;
  }

  runInAction(() => {
    draft.submitStatus = "ready";
  });
  onSaved();
}

interface SetRoleModalProps {
  opened: boolean;
  userId: string;
  username: string;
  currentRole: UserRole;
  onClose: () => void;
  onSaved: () => void;
}

export const SetRoleModal = observer(function SetRoleModal({
  opened,
  userId,
  username,
  currentRole,
  onClose,
  onSaved,
}: SetRoleModalProps) {
  const [draft] = useState(() => new SetRoleDraft(currentRole));

  const handleSubmit = async () => {
    const ctrl = new AbortController();
    await submitSetRole(draft, userId, onSaved, ctrl.signal);
    if (draft.submitStatus === "ready") onClose();
  };

  return (
    <Modal opened={opened} onClose={onClose} title="Change role" size="sm">
      <Stack>
        <Text size="sm" c="dimmed">
          Changing role for <strong>{username}</strong>
        </Text>
        {draft.errors.form && <Alert color="red">{draft.errors.form}</Alert>}
        <Select
          label="Role"
          data={ROLE_OPTIONS}
          value={draft.role}
          onChange={(v) => {
            if (v) draft.role = v as UserRole;
          }}
          error={draft.errors.role}
        />
        <Button onClick={handleSubmit} disabled={!draft.canSubmit}>
          Save
        </Button>
      </Stack>
    </Modal>
  );
});
