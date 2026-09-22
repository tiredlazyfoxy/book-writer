import { makeAutoObservable, runInAction } from "mobx";
import * as booksApi from "../../../api/books";
import { ApiError } from "../../../api/client";
import type {
  CollaborationMode,
  CreateBookRequest,
  Visibility,
} from "../../../types/books";

/**
 * Component-local draft for the create-book modal — held via
 * `useState(() => new CreateBookDraft())`. Observable field-per-input plus pure
 * `get` computeds only (no effectful methods, per the MobX hard rules); the
 * effectful submit lives in the external `submitCreateBook` below. Template =
 * admin `CreateUserDraft`.
 *
 * `serverErrors` is a `Record<string, string>` keyed by field name (`title` /
 * `description` / `collaboration_mode` / `visibility`) plus a general `form` key
 * for non-field refusals; it is merged over the client-validation `clientErrors`
 * getter so server errors surface without wiping live client validation.
 *
 * Skeleton: fields + getter shapes are frozen; the getter bodies are placeholders
 * that typecheck (no real validation rules) and the submit body throws — the coder
 * fills both.
 */
export class CreateBookDraft {
  title = "";
  description = "";
  collaborationMode: CollaborationMode = "free";
  visibility: Visibility = "private";

  serverErrors: Record<string, string> = {};
  submitStatus: "idle" | "loading" | "ready" | "error" = "idle";

  constructor() {
    makeAutoObservable(this);
  }

  /** Client-side validation map keyed by field name: a book requires a title. */
  get clientErrors(): Record<string, string> {
    const e: Record<string, string> = {};
    if (!this.title.trim()) e.title = "Title is required.";
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
 * Submit the create-book draft (unimplemented — coder fills). Intent: build the
 * `CreateBookRequest` from the draft, set `submitStatus = "loading"`, await
 * `booksApi.createBook(body, signal)`, then invoke `onCreated` (the page reload)
 * on success. On `ApiError`: map the status + message into `draft.serverErrors`
 * (field key or the general `form` key). Abort-guarded via `signal`.
 */
export async function submitCreateBook(
  draft: CreateBookDraft,
  onCreated: () => void,
  signal?: AbortSignal,
): Promise<void> {
  const body: CreateBookRequest = {
    title: draft.title.trim(),
    description: draft.description,
    collaboration_mode: draft.collaborationMode,
    visibility: draft.visibility,
  };

  runInAction(() => {
    draft.serverErrors = {};
    draft.submitStatus = "loading";
  });

  try {
    await booksApi.createBook(body, signal);
  } catch (err) {
    if (err instanceof ApiError) {
      runInAction(() => {
        draft.serverErrors =
          err.status === 400 || err.status === 422
            ? { title: err.message || "Please check the book details." }
            : { form: err.message || "Could not create the book." };
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
