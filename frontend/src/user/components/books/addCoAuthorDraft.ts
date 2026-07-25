import { makeAutoObservable, runInAction } from "mobx";
import * as booksApi from "../../../api/books";
import { ApiError } from "../../../api/client";
import type { AddMemberRequest } from "../../../types/books";

/**
 * Component-local draft for the add-co-author form on the settings page — held via
 * `useState(() => new AddCoAuthorDraft())`. Observable field-per-input plus pure
 * `get` computeds only (no effectful methods, per the MobX hard rules); the
 * effectful submit lives in the external `submitAddCoAuthor` below. Template =
 * admin `CreateUserDraft` / `serverFormDraft.ts` (create shape).
 *
 * `targetUserId` is the author-account id to grant co-author access (string id,
 * per the DTO boundary). `serverErrors` is a `Record<string, string>` keyed by
 * field name (`target_user_id`) plus a general `form` key for non-field refusals.
 *
 * Skeleton: fields + getter shapes are frozen; the getter bodies are placeholders
 * that typecheck (no real validation rules) and the submit body throws — the coder
 * fills both.
 */
export class AddCoAuthorDraft {
  targetUserId = "";

  serverErrors: Record<string, string> = {};
  submitStatus: "idle" | "loading" | "ready" | "error" = "idle";

  constructor() {
    makeAutoObservable(this);
  }

  /** Client-side validation map keyed by field name: a target account is required. */
  get clientErrors(): Record<string, string> {
    const e: Record<string, string> = {};
    if (!this.targetUserId.trim()) e.target_user_id = "A target account is required.";
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
 * Submit the add-co-author draft (unimplemented — coder fills). Intent: build the
 * `AddMemberRequest` from the draft, set `submitStatus = "loading"`, await
 * `booksApi.addMember(bookId, body, signal)`, then invoke `onDone` (the page
 * reload) on success. On `ApiError`: map the status + message into
 * `draft.serverErrors` (field key or the general `form` key). Abort-guarded.
 */
export async function submitAddCoAuthor(
  draft: AddCoAuthorDraft,
  bookId: string,
  onDone: () => void,
  signal?: AbortSignal,
): Promise<void> {
  const body: AddMemberRequest = { target_user_id: draft.targetUserId.trim() };

  runInAction(() => {
    draft.serverErrors = {};
    draft.submitStatus = "loading";
  });

  try {
    await booksApi.addMember(bookId, body, signal);
  } catch (err) {
    if (err instanceof ApiError) {
      runInAction(() => {
        draft.serverErrors =
          err.status >= 400 && err.status < 500
            ? { target_user_id: err.message || "Could not add that co-author." }
            : { form: err.message || "Could not add the co-author." };
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
