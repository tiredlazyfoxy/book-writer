import { useState } from "react";
import { makeAutoObservable, runInAction } from "mobx";
import { observer } from "mobx-react-lite";
import {
  Alert,
  Button,
  Modal,
  PasswordInput,
  Select,
  Stack,
  TextInput,
} from "@mantine/core";
import * as adminApi from "../../../api/admin";
import { ROLE_OPTIONS } from "../../../api/admin";
import { ApiError } from "../../../api/client";
import type { AdminCreateUserRequest, UserRole } from "../../../types/admin";

/**
 * Component-local draft for the create-user modal — held via
 * `useState(() => new CreateUserDraft())`. Observable fields + pure `get`
 * computeds only (no effectful methods, per the MobX hard rules); the effectful
 * submit lives in the external `submitCreate` below.
 *
 * `serverErrors` is a `Record<string, string>` keyed by field name
 * (`username` / `password` / `password_confirm`) plus a general `form` key for
 * non-field refusals; it is merged over the client-validation `errors` getter so
 * server errors surface without wiping live client validation.
 */
class CreateUserDraft {
  username = "";
  password = "";
  passwordConfirm = "";
  role: UserRole = "author";

  serverErrors: Record<string, string> = {};
  submitStatus: "idle" | "loading" | "ready" | "error" = "idle";

  constructor() {
    makeAutoObservable(this);
  }

  /** Client-side validation: required username, min-length-8 password, confirm match. */
  get clientErrors(): Record<string, string> {
    const e: Record<string, string> = {};
    if (!this.username.trim()) e.username = "Username is required.";
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
 * Effect (unimplemented — coder fills). On success: `adminApi.createUser` with the
 * draft body, then invoke `onCreated` (the page refresh) and let the modal close.
 * On `ApiError`: populate `draft.serverErrors` from the status + message (409 taken
 * username, 400 password policy). Abort-guarded via `signal`.
 */
export async function submitCreate(
  draft: CreateUserDraft,
  onCreated: () => void,
  signal?: AbortSignal,
): Promise<void> {
  const body: AdminCreateUserRequest = {
    username: draft.username.trim(),
    password: draft.password,
    password_confirm: draft.passwordConfirm,
    role: draft.role,
  };

  runInAction(() => {
    draft.serverErrors = {};
    draft.submitStatus = "loading";
  });

  try {
    await adminApi.createUser(body, signal);
  } catch (err) {
    if (err instanceof ApiError) {
      runInAction(() => {
        draft.serverErrors =
          err.status === 409
            ? { username: "That username is already taken." }
            : err.status === 400
              ? { password: err.message || "Password does not meet the policy." }
              : { form: err.message || "Could not create the user." };
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
  onCreated();
}

interface CreateUserModalProps {
  opened: boolean;
  onClose: () => void;
  onCreated: () => void;
}

export const CreateUserModal = observer(function CreateUserModal({
  opened,
  onClose,
  onCreated,
}: CreateUserModalProps) {
  const [draft] = useState(() => new CreateUserDraft());

  const handleSubmit = async () => {
    const ctrl = new AbortController();
    await submitCreate(draft, onCreated, ctrl.signal);
    if (draft.submitStatus === "ready") onClose();
  };

  return (
    <Modal opened={opened} onClose={onClose} title="Create user" size="sm">
      <Stack>
        {draft.errors.form && <Alert color="red">{draft.errors.form}</Alert>}
        <TextInput
          label="Username"
          value={draft.username}
          onChange={(e) => {
            draft.username = e.currentTarget.value;
          }}
          error={draft.errors.username}
        />
        <PasswordInput
          label="Password"
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
        <Select
          label="Role"
          data={ROLE_OPTIONS}
          value={draft.role}
          onChange={(v) => {
            if (v) draft.role = v as UserRole;
          }}
        />
        <Button onClick={handleSubmit} disabled={!draft.canSubmit}>
          Create
        </Button>
      </Stack>
    </Modal>
  );
});
