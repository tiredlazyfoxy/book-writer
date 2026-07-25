import { makeAutoObservable, runInAction } from "mobx";
import * as booksApi from "../../../api/books";
import { ApiError } from "../../../api/client";
import type { TransferOwnershipRequest } from "../../../types/books";

/**
 * Component-local draft for the transfer-ownership form on the settings page — held
 * via `useState(() => new TransferOwnershipDraft())`. Observable field-per-input
 * plus pure `get` computeds only (no effectful methods, per the MobX hard rules);
 * the effectful submit lives in the external `submitTransferOwnership` below.
 * Template = admin `CreateUserDraft` / `serverFormDraft.ts` (create shape).
 *
 * `targetUserId` is the co-author id to become the new owner (string id). The UI
 * offers only current co-authors as transfer targets; a server refusal of a
 * non-co-author surfaces as a field error (UC-024). `serverErrors` is keyed by
 * field name (`target_user_id`) plus a general `form` key.
 *
 * Skeleton: fields + getter shapes are frozen; the getter bodies are placeholders
 * that typecheck (no real validation rules) and the submit body throws — the coder
 * fills both.
 */
export class TransferOwnershipDraft {
  targetUserId = "";

  serverErrors: Record<string, string> = {};
  submitStatus: "idle" | "loading" | "ready" | "error" = "idle";

  constructor() {
    makeAutoObservable(this);
  }

  /** Client-side validation map keyed by field name: a target co-author is required. */
  get clientErrors(): Record<string, string> {
    const e: Record<string, string> = {};
    if (!this.targetUserId.trim()) e.target_user_id = "A target co-author is required.";
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
 * Submit the transfer-ownership draft (unimplemented — coder fills). Intent: build
 * the `TransferOwnershipRequest` from the draft, set `submitStatus = "loading"`,
 * await `booksApi.transferOwnership(bookId, body, signal)`, then invoke `onDone`
 * (the page reload) on success. On `ApiError`: map the status + message into
 * `draft.serverErrors` (field key for a refused non-co-author target, or the
 * general `form` key). Abort-guarded.
 */
export async function submitTransferOwnership(
  draft: TransferOwnershipDraft,
  bookId: string,
  onDone: () => void,
  signal?: AbortSignal,
): Promise<void> {
  const body: TransferOwnershipRequest = { target_user_id: draft.targetUserId.trim() };

  runInAction(() => {
    draft.serverErrors = {};
    draft.submitStatus = "loading";
  });

  try {
    await booksApi.transferOwnership(bookId, body, signal);
  } catch (err) {
    if (err instanceof ApiError) {
      runInAction(() => {
        draft.serverErrors =
          err.status >= 400 && err.status < 500
            ? { target_user_id: err.message || "That user cannot receive ownership." }
            : { form: err.message || "Could not transfer ownership." };
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
  onDone();
}
