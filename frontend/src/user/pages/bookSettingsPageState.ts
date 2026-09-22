import { makeAutoObservable, runInAction } from "mobx";
import * as booksApi from "../../api/books";
import { ApiError } from "../../api/client";
import type {
  AddMemberRequest,
  BookAuthorPromptResponse,
  BookDetailResponse,
  SetVisibilityRequest,
  TransferOwnershipRequest,
  UpdateBookAuthorPromptRequest,
} from "../../types/books";

/**
 * Page state for `BookSettingsPage` (`/books/:bookId/settings`).
 *
 * Holds the single book-detail async-resource trio (`detail` / `detailStatus` /
 * `detailError`) plus `makeAutoObservable`. The `members` list and current
 * `visibility` / `state` all come from `GET /api/books/{id}` (`detail`); after any
 * mutation the detail is re-loaded rather than mutated locally (backend is the
 * source of truth). Per the MobX hard rules this class has NO effectful methods —
 * loading and every mutation action live in the external `(state, …, signal)`
 * functions below.
 *
 * Feature 021 adds a SECOND, independent trio for **the caller's own** system prompt
 * (`systemPrompt` / `systemPromptStatus` / `systemPromptError`) plus the editor's
 * draft state. It is a separate loadable with its own endpoint — the prompt is
 * per-author, so it can never ride on the book-shaped `detail`. The two trios never
 * interact: a prompt failure must not blank the settings page, and a detail reload
 * must not discard what the author has typed.
 */
export class BookSettingsPageState {
  detail: BookDetailResponse | null = null;
  detailStatus: "idle" | "loading" | "ready" | "error" = "idle";
  detailError: string | null = null;

  /**
   * The caller's own system prompt for this book, as last returned by the server —
   * the value the draft is compared against and re-seeded from. `null` until the
   * first successful load; a stored `system_prompt` of `""` is a normal loaded
   * value, NOT an absence.
   */
  systemPrompt: BookAuthorPromptResponse | null = null;
  systemPromptStatus: "idle" | "loading" | "ready" | "error" = "idle";
  systemPromptError: string | null = null;

  /**
   * The textarea draft, seeded from the server's `system_prompt` on load and
   * re-seeded from the PUT response on save. Every string is valid input, `""`
   * included — clearing the box and saving is how an author removes their prompt.
   */
  systemPromptDraft = "";

  /**
   * Server refusals for the save only, held separately from the load trio's
   * `systemPromptError`. Keyed by field name (`system_prompt`) plus the general
   * `form` key for non-field refusals, per `addCoAuthorDraft`'s split. There is NO
   * `clientErrors` counterpart: this field has no client-side validation, because
   * every string is valid.
   */
  systemPromptServerErrors: Record<string, string> = {};

  /** In-flight state of the save (the load has its own `systemPromptStatus`). */
  systemPromptSubmitStatus: "idle" | "loading" | "ready" | "error" = "idle";

  constructor() {
    makeAutoObservable(this);
  }

  /**
   * True when the draft differs from what the server last returned. A not-yet-loaded
   * prompt compares as `""`, so an author who has never had one still counts as dirty
   * once they type. Pure — no side effects, no I/O.
   */
  get systemPromptDirty(): boolean {
    return this.systemPromptDraft !== (this.systemPrompt?.system_prompt ?? "");
  }

  /**
   * True when saving is currently allowed: the draft is dirty, no save is in flight,
   * and the prompt has loaded (nothing may be written over a value that was never
   * read). Pure. Note there is no emptiness check — `""` is a legal save that clears
   * the prompt.
   */
  get canSaveSystemPrompt(): boolean {
    return (
      this.systemPromptStatus === "ready" &&
      this.systemPromptSubmitStatus !== "loading" &&
      this.systemPromptDirty
    );
  }
}

/**
 * Load the book detail into `state` (unimplemented — coder fills). Intent: set
 * `detailStatus = "loading"`, await `booksApi.getBookDetail(bookId, signal)`,
 * `runInAction` the trio to `ready` on success; guard `signal?.aborted`; map an
 * `ApiError` into `detailError` / `detailStatus = "error"`, else rethrow.
 */
export async function loadBookSettings(
  state: BookSettingsPageState,
  bookId: string,
  signal?: AbortSignal,
): Promise<void> {
  runInAction(() => {
    state.detailStatus = "loading";
    state.detailError = null;
  });
  try {
    const detail = await booksApi.getBookDetail(bookId, signal);
    if (signal?.aborted) return;
    runInAction(() => {
      state.detail = detail;
      state.detailStatus = "ready";
    });
  } catch (err) {
    if (signal?.aborted) return;
    if (err instanceof ApiError) {
      runInAction(() => {
        state.detailError = err.message;
        state.detailStatus = "error";
      });
      return;
    }
    throw err;
  }
}

/**
 * Archive the book then re-load the detail (unimplemented — coder fills). Intent:
 * await `booksApi.archiveBook(bookId, signal)` then `loadBookSettings(state,
 * bookId, signal)`; abort-guarded; `ApiError` surfaced into `detailError`.
 */
export async function archiveAction(
  state: BookSettingsPageState,
  bookId: string,
  signal?: AbortSignal,
): Promise<void> {
  try {
    await booksApi.archiveBook(bookId, signal);
    if (signal?.aborted) return;
    await loadBookSettings(state, bookId, signal);
  } catch (err) {
    if (signal?.aborted) return;
    if (err instanceof ApiError) {
      runInAction(() => {
        state.detailError = err.message;
      });
      return;
    }
    throw err;
  }
}

/**
 * Unarchive the book then re-load the detail (unimplemented — coder fills). Intent:
 * await `booksApi.unarchiveBook(bookId, signal)` then re-load; same error handling
 * as `archiveAction`.
 */
export async function unarchiveAction(
  state: BookSettingsPageState,
  bookId: string,
  signal?: AbortSignal,
): Promise<void> {
  try {
    await booksApi.unarchiveBook(bookId, signal);
    if (signal?.aborted) return;
    await loadBookSettings(state, bookId, signal);
  } catch (err) {
    if (signal?.aborted) return;
    if (err instanceof ApiError) {
      runInAction(() => {
        state.detailError = err.message;
      });
      return;
    }
    throw err;
  }
}

/**
 * Transfer ownership then re-load the detail (unimplemented — coder fills). Intent:
 * await `booksApi.transferOwnership(bookId, body, signal)` then re-load; abort-
 * guarded; `ApiError` surfaced into `detailError`.
 */
export async function transferAction(
  state: BookSettingsPageState,
  bookId: string,
  body: TransferOwnershipRequest,
  signal?: AbortSignal,
): Promise<void> {
  try {
    await booksApi.transferOwnership(bookId, body, signal);
    if (signal?.aborted) return;
    await loadBookSettings(state, bookId, signal);
  } catch (err) {
    if (signal?.aborted) return;
    if (err instanceof ApiError) {
      runInAction(() => {
        state.detailError = err.message;
      });
      return;
    }
    throw err;
  }
}

/**
 * Add a co-author then re-load the detail (unimplemented — coder fills). Intent:
 * await `booksApi.addMember(bookId, body, signal)` then re-load so the new member
 * appears; abort-guarded; `ApiError` surfaced into `detailError`.
 */
export async function addMemberAction(
  state: BookSettingsPageState,
  bookId: string,
  body: AddMemberRequest,
  signal?: AbortSignal,
): Promise<void> {
  try {
    await booksApi.addMember(bookId, body, signal);
    if (signal?.aborted) return;
    await loadBookSettings(state, bookId, signal);
  } catch (err) {
    if (signal?.aborted) return;
    if (err instanceof ApiError) {
      runInAction(() => {
        state.detailError = err.message;
      });
      return;
    }
    throw err;
  }
}

/**
 * Remove a co-author then re-load the detail (unimplemented — coder fills). Intent:
 * await `booksApi.removeMember(bookId, userId, signal)` then re-load so the member
 * list updates; abort-guarded; `ApiError` surfaced into `detailError`.
 */
export async function removeMemberAction(
  state: BookSettingsPageState,
  bookId: string,
  userId: string,
  signal?: AbortSignal,
): Promise<void> {
  try {
    await booksApi.removeMember(bookId, userId, signal);
    if (signal?.aborted) return;
    await loadBookSettings(state, bookId, signal);
  } catch (err) {
    if (signal?.aborted) return;
    if (err instanceof ApiError) {
      runInAction(() => {
        state.detailError = err.message;
      });
      return;
    }
    throw err;
  }
}

/**
 * Set visibility then re-load the detail (unimplemented — coder fills). Intent:
 * await `booksApi.setVisibility(bookId, body, signal)` then re-load; abort-guarded;
 * `ApiError` surfaced into `detailError`.
 */
export async function setVisibilityAction(
  state: BookSettingsPageState,
  bookId: string,
  body: SetVisibilityRequest,
  signal?: AbortSignal,
): Promise<void> {
  try {
    await booksApi.setVisibility(bookId, body, signal);
    if (signal?.aborted) return;
    await loadBookSettings(state, bookId, signal);
  } catch (err) {
    if (signal?.aborted) return;
    if (err instanceof ApiError) {
      runInAction(() => {
        state.detailError = err.message;
      });
      return;
    }
    throw err;
  }
}

/**
 * Load the caller's own system prompt and seed the draft from it. An empty
 * `system_prompt` is a normal loaded value, never an error. An `ApiError` lands in
 * `systemPromptError` / `systemPromptStatus = "error"`, leaving `systemPrompt` null so
 * no editor is bound to stale data; anything else rethrows. Touches nothing in the
 * `detail` trio.
 */
export async function loadSystemPrompt(
  state: BookSettingsPageState,
  bookId: string,
  signal?: AbortSignal,
): Promise<void> {
  runInAction(() => {
    state.systemPromptStatus = "loading";
    state.systemPromptError = null;
  });
  try {
    const prompt = await booksApi.getOwnSystemPrompt(bookId, signal);
    if (signal?.aborted) return;
    runInAction(() => {
      state.systemPrompt = prompt;
      state.systemPromptDraft = prompt.system_prompt;
      state.systemPromptStatus = "ready";
    });
  } catch (err) {
    if (signal?.aborted) return;
    if (err instanceof ApiError) {
      runInAction(() => {
        state.systemPromptError = err.message;
        state.systemPromptStatus = "error";
      });
      return;
    }
    throw err;
  }
}

/**
 * Save the draft as the caller's own system prompt. The body is
 * `{ system_prompt: state.systemPromptDraft }` verbatim — no trimming, no emptiness
 * check, because `""` is a legal value that clears the prompt (there is no DELETE).
 *
 * On success BOTH `systemPrompt` and `systemPromptDraft` are re-seeded **from the
 * response body directly**: the backend is the source of truth, and re-running
 * `loadSystemPrompt` here would open a window in which the editor shows neither the
 * draft nor the stored value.
 *
 * On `ApiError` the status + message map into `systemPromptServerErrors` (4xx → the
 * `system_prompt` key, 5xx → the general `form` key, per `addCoAuthorDraft`) and the
 * submit status goes to `"error"` — **leaving `systemPromptDraft` untouched**, so a
 * refused save loses nothing the author typed. Anything else rethrows.
 */
export async function saveSystemPrompt(
  state: BookSettingsPageState,
  bookId: string,
  signal?: AbortSignal,
): Promise<void> {
  const body: UpdateBookAuthorPromptRequest = { system_prompt: state.systemPromptDraft };

  runInAction(() => {
    state.systemPromptServerErrors = {};
    state.systemPromptSubmitStatus = "loading";
  });

  try {
    const saved = await booksApi.updateOwnSystemPrompt(bookId, body, signal);
    if (signal?.aborted) return;
    runInAction(() => {
      state.systemPrompt = saved;
      state.systemPromptDraft = saved.system_prompt;
      state.systemPromptSubmitStatus = "ready";
    });
  } catch (err) {
    if (signal?.aborted) return;
    if (err instanceof ApiError) {
      runInAction(() => {
        state.systemPromptServerErrors =
          err.status >= 400 && err.status < 500
            ? { system_prompt: err.message || "Could not save your system prompt." }
            : { form: err.message || "Could not save your system prompt." };
        state.systemPromptSubmitStatus = "error";
      });
      return;
    }
    throw err;
  }
}
