import { makeAutoObservable, runInAction } from "mobx";
import * as booksApi from "../../api/books";
import { COLLABORATION_MODE_OPTIONS, VISIBILITY_OPTIONS } from "../../api/books";
import { ApiError } from "../../api/client";
import type {
  BookAuthorPromptResponse,
  BookDetailResponse,
  BookMemberResponse,
  BookState,
  UpdateBookAuthorPromptRequest,
} from "../../types/books";

/** Author-facing labels for the `BookState` union (no exported map exists — see `003.context.md`). */
const LIFECYCLE_STATE_LABELS: Record<BookState, string> = {
  active: "Active",
  archived: "Archived",
  quarantined: "Quarantined",
  destroyed: "Destroyed",
};

/**
 * Page state for `BookStatePage` (`/work/:bookId/state`, the working page's
 * landing view — UC-091 / US-106.AC-1), held via `useState(() => new
 * BookStatePageState())`.
 *
 * Holds the book-detail async-resource trio (`bookDetail` / `bookDetailStatus` /
 * `bookDetailError`) plus `makeAutoObservable`. This page loads the book again by
 * URL id rather than warm-starting from the shell's copy (frontend.md — every page
 * is deep-linkable; `useOutletContext` is banned React context); see
 * `003.context.md`. Per the MobX hard rules the class has NO effectful methods and
 * NO setters — the load lives in the external `loadBookState(state, bookId, signal)`
 * function below. Every derivation is a `get` computed:
 *   - `collaborationModeLabel` / `visibilityLabel` — author-facing labels, reusing
 *     `COLLABORATION_MODE_OPTIONS` / `VISIBILITY_OPTIONS` from `api/books.ts`.
 *   - `lifecycleStateLabel` — author-facing `BookState` label (no exported map
 *     exists; the coder derives it here — `003.context.md`).
 *   - `memberList` / `memberCount` — the co-author members to render and their count.
 *
 * Skeleton: the observable trio is fully declared; the computed getters and the
 * external loader are frozen with throwing stub bodies for the coder to implement.
 * (That paragraph is feature 010's note and is now historical — the book-detail
 * trio, its five computeds and `loadBookState` are all implemented.)
 *
 * Feature 021 step 006 adds a SECOND, independent loadable: **the caller's own**
 * system prompt for this book (`systemPrompt` / `systemPromptStatus` /
 * `systemPromptError`) plus the editor's draft, its server-error holder and its
 * submit status. It is a separate trio with its own endpoint — the prompt is
 * per-author, so it can never ride on the book-shaped `bookDetail`. The two trios
 * never interact: a prompt failure must not blank the Book-state view, and a
 * detail load must not touch what the author has typed. Nothing about the
 * book-detail trio, its computeds or its loader changes in this step.
 */
export class BookStatePageState {
  bookDetail: BookDetailResponse | null = null;
  bookDetailStatus: "idle" | "loading" | "ready" | "error" = "idle";
  bookDetailError: string | null = null;

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
   * The editor draft, seeded from the server's `system_prompt` on load and re-seeded
   * from the PUT response on save. Every string is valid input, `""` included —
   * clearing the box and saving is how an author removes their prompt. This draft is
   * deliberately NOT mirrored into the working page's restore buffer (`context.md` →
   * "Planner-derived decisions"): no buffer key, no write on keystroke, no
   * `baseVersion`, no stale-buffer reconciliation.
   */
  systemPromptDraft = "";

  /**
   * Server refusals for the save only, held separately from the load trio's
   * `systemPromptError`. Keyed by field name (`system_prompt`) plus the general
   * `form` key for non-field refusals. There is NO `clientErrors` counterpart and no
   * `errors` union: this field has no client-side validation, because every string
   * is valid.
   */
  systemPromptServerErrors: Record<string, string> = {};

  /** In-flight state of the save (the load has its own `systemPromptStatus`). */
  systemPromptSubmitStatus: "idle" | "loading" | "ready" | "error" = "idle";

  constructor() {
    makeAutoObservable(this);
  }

  /** Author-facing collaboration-mode label, reusing `COLLABORATION_MODE_OPTIONS`. */
  get collaborationModeLabel(): string {
    const mode = this.bookDetail?.collaboration_mode;
    if (!mode) return "";
    return COLLABORATION_MODE_OPTIONS.find((o) => o.value === mode)?.label ?? "";
  }

  /** Author-facing visibility label, reusing `VISIBILITY_OPTIONS`. */
  get visibilityLabel(): string {
    const visibility = this.bookDetail?.visibility;
    if (!visibility) return "";
    return VISIBILITY_OPTIONS.find((o) => o.value === visibility)?.label ?? "";
  }

  /** Author-facing lifecycle-state label. */
  get lifecycleStateLabel(): string {
    const state = this.bookDetail?.state;
    if (!state) return "";
    return LIFECYCLE_STATE_LABELS[state] ?? "";
  }

  /** The co-author member rows to render. */
  get memberList(): BookMemberResponse[] {
    return this.bookDetail?.members ?? [];
  }

  /** The count of members to render. */
  get memberCount(): number {
    return this.memberList.length;
  }

  /**
   * True when the draft differs from what the server last returned. A not-yet-loaded
   * prompt compares as `""`, so an author who never had one still counts as dirty
   * once they type. Pure — no side effects, no I/O.
   */
  get systemPromptDirty(): boolean {
    return this.systemPromptDraft !== (this.systemPrompt?.system_prompt ?? "");
  }

  /**
   * True when saving is currently allowed: the draft is dirty, no save is in flight,
   * and the prompt has loaded — nothing may be written over a value that was never
   * read. Pure. There is deliberately NO emptiness check: `""` is a legal save that
   * clears the prompt.
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
 * `bookDetailStatus = "loading"`, await `booksApi.getBookDetail(bookId, signal)`,
 * `runInAction` the trio to `ready` on success; return silently when
 * `signal?.aborted`; map an `ApiError` into an author-facing `bookDetailError` with
 * `bookDetailStatus = "error"`, else rethrow.
 */
export async function loadBookState(
  state: BookStatePageState,
  bookId: string,
  signal?: AbortSignal,
): Promise<void> {
  runInAction(() => {
    state.bookDetailStatus = "loading";
    state.bookDetailError = null;
  });
  try {
    const detail = await booksApi.getBookDetail(bookId, signal);
    if (signal?.aborted) return;
    runInAction(() => {
      state.bookDetail = detail;
      state.bookDetailStatus = "ready";
    });
  } catch (err) {
    if (signal?.aborted) return;
    if (err instanceof ApiError) {
      runInAction(() => {
        state.bookDetailError = err.message;
        state.bookDetailStatus = "error";
      });
      return;
    }
    throw err;
  }
}

/**
 * Load the caller's own system prompt and seed the draft from it: set
 * `systemPromptStatus = "loading"` and clear `systemPromptError`, await
 * `booksApi.getOwnSystemPrompt(bookId, signal)`, then `runInAction` `systemPrompt` +
 * `systemPromptDraft` + `systemPromptStatus = "ready"`; return silently when
 * `signal?.aborted`; map an `ApiError` into `systemPromptError` /
 * `systemPromptStatus = "error"` leaving `systemPrompt` null so no editor binds to
 * stale data, else rethrow.
 *
 * An empty `system_prompt` is a normal loaded value, never an error — a member who
 * has written no prompt gets an empty, editable field. Touches nothing in the
 * `bookDetail` trio: the two loadables fail independently.
 */
export async function loadSystemPrompt(
  state: BookStatePageState,
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
 * `{ system_prompt: state.systemPromptDraft }` read off the state verbatim — no
 * trimming, no emptiness check, because `""` is a legal value that clears the prompt
 * (there is no DELETE verb and no delete control).
 *
 * Clears `systemPromptServerErrors` and sets `systemPromptSubmitStatus = "loading"`,
 * awaits `booksApi.updateOwnSystemPrompt(bookId, body, signal)`, then re-seeds BOTH
 * `systemPrompt` and `systemPromptDraft` **from the response body directly** — the
 * backend is the source of truth, and re-running `loadSystemPrompt` here would open a
 * window showing neither the draft nor the stored value. Returns silently when
 * `signal?.aborted`. On `ApiError` the message lands in `systemPromptServerErrors`
 * (4xx → the `system_prompt` key, 5xx → the general `form` key) with
 * `systemPromptSubmitStatus = "error"`, **leaving `systemPromptDraft` untouched** so a
 * refusal loses nothing the author typed; anything else rethrows. There is no 409 path
 * — this row carries no version token and has exactly one writer.
 */
export async function saveSystemPrompt(
  state: BookStatePageState,
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
