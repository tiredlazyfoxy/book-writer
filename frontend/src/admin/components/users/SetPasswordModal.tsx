import { useState } from "react";
import { makeAutoObservable, runInAction } from "mobx";
import { observer } from "mobx-react-lite";
import { Alert, Button, Modal, PasswordInput, Stack, Text } from "@mantine/core";
import * as adminApi from "../../../api/admin";
import { ApiError } from "../../../api/client";
import type { AdminSetPasswordRequest } from "../../../types/admin";

/**
 * Component-local draft for the reset-password modal — held via
 * `useState(() => new SetPasswordDraft())`. Observable fields + pure `get`
 * computeds only; the effectful submit is the external `submitSetPassword` below.
 *
 * `serverErrors` is a `Record<string, string>` keyed by field name (`password` /
 * `password_confirm`) plus a general `form` key, merged over the client-validation
 * `errors` getter.
 */
class SetPasswordDraft {
  password = "";
  passwordConfirm = "";

  serverErrors: Record<string, string> = {};
  submitStatus: "idle" | "loading" | "ready" | "error" = "idle";

  constructor() {
    makeAutoObservable(this);
  }

  /** Client-side validation: min-length-8 password, confirm match. */
  get clientErrors(): Record<string, string> {
    const e: Record<string, string> = {};
    if (this.password.length < 8) e.password = "Password must be at least 8 characters.";
    if (this.password !== this.passwordConfirm) e.password_confirm = "Passwords do not match.";
    return e;
  }

  /** Displayed errors: client validation unioned with (overridden by) server errors. */
  get errors(): Record<string, string> {
    return { ...this.clientErrors, ...this.serverErrors };
  }

  /** True when client validation passes and no submit is in flight. */
  get canSubmit(): boolean {
    return this.submitStatus !== "loading" && Object.keys(this.clientErrors).length === 0;
  }
}

/**
 * Effect (unimplemented — coder fills). On success: `adminApi.setUserPassword(userId, …)`,
 * then invoke `onSaved` (the page refresh) and let the modal close. On `ApiError`:
 * populate `draft.serverErrors` (400 password policy). Abort-guarded via `signal`.
 */
export async function submitSetPassword(
  draft: SetPasswordDraft,
  userId: string,
  onSaved: () => void,
  signal?: AbortSignal,
): Promise<void> {
  const body: AdminSetPasswordRequest = {
    password: draft.password,
    password_confirm: draft.passwordConfirm,
  };

  runInAction(() => {
    draft.serverErrors = {};
    draft.submitStatus = "loading";
  });

  try {
    await adminApi.setUserPassword(userId, body, signal);
  } catch (err) {
    if (err instanceof ApiError) {
      runInAction(() => {
        draft.serverErrors =
          err.status === 400
            ? { password: err.message || "Password does not meet the policy." }
            : { form: err.message || "Could not reset the password." };
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

interface SetPasswordModalProps {
  opened: boolean;
  userId: string;
  username: string;
  onClose: () => void;
  onSaved: () => void;
}

export const SetPasswordModal = observer(function SetPasswordModal({
  opened,
  userId,
  username,
  onClose,
  onSaved,
}: SetPasswordModalProps) {
  const [draft] = useState(() => new SetPasswordDraft());

  const handleSubmit = async () => {
    const ctrl = new AbortController();
    await submitSetPassword(draft, userId, onSaved, ctrl.signal);
    if (draft.submitStatus === "ready") onClose();
  };

  return (
    <Modal opened={opened} onClose={onClose} title="Reset password" size="sm">
      <Stack>
        <Text size="sm" c="dimmed">
          Resetting password for <strong>{username}</strong>
        </Text>
        {draft.errors.form && <Alert color="red">{draft.errors.form}</Alert>}
        <PasswordInput
          label="New password"
          value={draft.password}
          onChange={(e) => {
            draft.password = e.currentTarget.value;
          }}
          error={draft.errors.password}
        />
        <PasswordInput
          label="Confirm password"
          value={draft.passwordConfirm}
          onChange={(e) => {
            draft.passwordConfirm = e.currentTarget.value;
          }}
          error={draft.errors.password_confirm}
        />
        <Button onClick={handleSubmit} disabled={!draft.canSubmit}>
          Reset password
        </Button>
      </Stack>
    </Modal>
  );
});
