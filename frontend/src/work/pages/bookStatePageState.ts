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
import * as continuityApi from "../../api/continuity";
import type {
  BookContinuityResponse,
  BookStateNotesResponse,
  UpdateBookStateNotesRequest,
} from "../../types/continuity";

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

  // --- Continuity (016) ---
  //
  // TWO MORE INDEPENDENT TRIOS, filling the page's two stubs that already name
  // `016.chapter-close-continuity` as their owner (decision D8 — no new route and no
  // new navigator entry). They follow the two shipped trios field-for-field and
  // interact with neither: a continuity failure must not blank the book-state view or
  // the prompt editor, and neither of those may hide a continuity error.

  /**
   * THE PER-CHAPTER CONTINUITY ROLL-UP (`GET …/continuity`) — one entry per chapter
   * with its summary, its changeset and its OPEN warnings (UC-089 / UC-091;
   * US-104.AC-1, US-106.AC-2 / AC-3). `null` until the first successful load.
   *
   * READ-ONLY on this page: nothing here is edited, so there is no draft, no
   * server-error holder and no submit status beside it.
   */
  continuity: BookContinuityResponse | null = null;
  continuityStatus: "idle" | "loading" | "ready" | "error" = "idle";
  continuityError: string | null = null;

  /**
   * THE BOOK'S LIVE STATE NOTES (`GET …/state-notes`) as the server last returned
   * them — the value {@link BookStatePageState.stateNotesDraft} is compared against
   * and re-seeded from (UC-049). `null` until the first successful load; an
   * `active_notes` of `""` is a NORMAL loaded value, not an absence.
   */
  stateNotes: BookStateNotesResponse | null = null;
  stateNotesStatus: "idle" | "loading" | "ready" | "error" = "idle";
  stateNotesError: string | null = null;

  /**
   * The state-notes editor's draft, seeded from the server on load and re-seeded from
   * the PUT response on save (UC-050's direct-edit path / US-053.AC-1). Every string
   * is valid input, `""` included — there is no client-side validation layer and no
   * `clientErrors` counterpart.
   *
   * Deliberately NOT mirrored into the working page's restore buffer: the notes are a
   * short server round-trip through their own trio, not a large content-pane artifact
   * with a version token (`016/context.md`).
   */
  stateNotesDraft = "";

  /**
   * Server refusals for the state-notes SAVE only, held separately from the load
   * trio's `stateNotesError` so a refusal never blanks what the author typed. Keyed by
   * field name (`active_notes`) plus the general `form` key — the shape
   * `systemPromptServerErrors` uses. The proposal-mode `403` (which names FEAT-010 as
   * unbuilt) and the archived-book `403` both land here.
   */
  stateNotesServerErrors: Record<string, string> = {};

  /** In-flight state of the state-notes save (the load has its own `stateNotesStatus`). */
  stateNotesSubmitStatus: "idle" | "loading" | "ready" | "error" = "idle";

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

  /**
   * True when the state-notes draft differs from what the server last returned (016).
   * A not-yet-loaded note set compares as `""`, so a book that has never had notes
   * still counts as dirty once the author types. Pure — no side effects, no I/O.
   */
  get stateNotesDirty(): boolean {
    return this.stateNotesDraft !== (this.stateNotes?.active_notes ?? "");
  }

  /**
   * True when saving the state notes is currently allowed (016): the notes have
   * loaded (nothing may be written over a value that was never read), no save is in
   * flight, and the draft is dirty.
   *
   * Deliberately NO emptiness check — `""` is a legal save that clears the set — and
   * deliberately NO role or mode gate: the page has no caller-role signal, the server
   * refuses a co-author's proposal-mode edit `403`, and that refusal text is what the
   * author reads (the `ChapterPageState` D14 precedent). Pure.
   */
  get canSaveStateNotes(): boolean {
    return (
      this.stateNotesStatus === "ready" &&
      this.stateNotesSubmitStatus !== "loading" &&
      this.stateNotesDirty
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

// ---------------------------------------------------------------------------
// CONTINUITY (`016.chapter-close-continuity`) — three more external effects, in the
// module's existing `(state, bookId, signal?)` shape. Each touches ONLY its own trio:
// the four loadables on this page fail independently, in every direction.
// ---------------------------------------------------------------------------

/**
 * Load the book's per-chapter continuity roll-up (016; UC-089 / UC-091).
 *
 * The {@link loadBookState} shape verbatim: `continuityStatus = "loading"` and clear
 * `continuityError`, await `continuityApi.getBookContinuity(bookId, signal)`, then
 * `runInAction` `continuity` + `continuityStatus = "ready"`; return silently when
 * `signal?.aborted`; map an `ApiError` into `continuityError` / `continuityStatus =
 * "error"` leaving `continuity` null so nothing renders off data that never arrived,
 * else rethrow.
 *
 * Also the retry path behind the continuity error branch. Touches nothing in the
 * other three trios.
 *
 */
export async function loadBookContinuity(
  state: BookStatePageState,
  bookId: string,
  signal?: AbortSignal,
): Promise<void> {
  runInAction(() => {
    state.continuityStatus = "loading";
    state.continuityError = null;
  });
  try {
    const continuity = await continuityApi.getBookContinuity(bookId, signal);
    if (signal?.aborted) return;
    runInAction(() => {
      state.continuity = continuity;
      state.continuityStatus = "ready";
    });
  } catch (err) {
    if (signal?.aborted) return;
    if (err instanceof ApiError) {
      runInAction(() => {
        state.continuityError = err.message;
        state.continuityStatus = "error";
      });
      return;
    }
    throw err;
  }
}

/**
 * Load the book's live state notes and SEED THE DRAFT from them (016; UC-049 /
 * US-052.AC-1).
 *
 * The {@link loadSystemPrompt} shape one resource across: `stateNotesStatus =
 * "loading"` and clear `stateNotesError`, await
 * `continuityApi.getStateNotes(bookId, signal)`, then `runInAction` `stateNotes` +
 * `stateNotesDraft = notes.active_notes` + `stateNotesStatus = "ready"`; abort-guarded;
 * an `ApiError` becomes `stateNotesError` / `stateNotesStatus = "error"` leaving
 * `stateNotes` null, else rethrow.
 *
 * An empty `active_notes` is a NORMAL loaded value, never an error — a book nobody has
 * written notes for gets an empty, editable field.
 *
 */
export async function loadStateNotes(
  state: BookStatePageState,
  bookId: string,
  signal?: AbortSignal,
): Promise<void> {
  runInAction(() => {
    state.stateNotesStatus = "loading";
    state.stateNotesError = null;
  });
  try {
    const notes = await continuityApi.getStateNotes(bookId, signal);
    if (signal?.aborted) return;
    runInAction(() => {
      state.stateNotes = notes;
      // `""` is a NORMAL loaded value — a book nobody has written notes for gets
      // an empty, editable field, not an error.
      state.stateNotesDraft = notes.active_notes;
      state.stateNotesStatus = "ready";
    });
  } catch (err) {
    if (signal?.aborted) return;
    if (err instanceof ApiError) {
      runInAction(() => {
        state.stateNotesError = err.message;
        state.stateNotesStatus = "error";
      });
      return;
    }
    throw err;
  }
}

/**
 * Save the draft as the book's live state notes (016; UC-050's direct-edit path /
 * US-053.AC-1).
 *
 * The {@link saveSystemPrompt} shape verbatim: body `{ active_notes:
 * state.stateNotesDraft }` read off the state — no trimming and no emptiness check,
 * because `""` legitimately clears the set. Clear `stateNotesServerErrors`, set
 * `stateNotesSubmitStatus = "loading"`, await
 * `continuityApi.updateStateNotes(bookId, body, signal)`, then re-seed BOTH
 * `stateNotes` and `stateNotesDraft` **from the response body directly** — the backend
 * is the source of truth. Abort-guarded. On `ApiError` the message lands in
 * `stateNotesServerErrors` (4xx → the `active_notes` key, 5xx → the general `form`
 * key) with `stateNotesSubmitStatus = "error"` and **`stateNotesDraft` untouched**, so
 * a refusal loses nothing the author typed; anything else rethrows.
 *
 * The proposal-mode `403` (a co-author in a proposal-mode book, whose message names
 * FEAT-010 as unbuilt — US-053.AC-2 is NOT satisfied) and the archived-book `403`
 * arrive through that same branch. There is **no `409` path**: the note set carries no
 * version token and this write is last-write-wins.
 *
 */
export async function saveStateNotes(
  state: BookStatePageState,
  bookId: string,
  signal?: AbortSignal,
): Promise<void> {
  // Read off the state verbatim — no trimming and no emptiness check, because `""`
  // legitimately clears the set.
  const body: UpdateBookStateNotesRequest = { active_notes: state.stateNotesDraft };

  runInAction(() => {
    state.stateNotesServerErrors = {};
    state.stateNotesSubmitStatus = "loading";
  });

  try {
    const saved = await continuityApi.updateStateNotes(bookId, body, signal);
    if (signal?.aborted) return;
    runInAction(() => {
      // RE-SEEDED FROM THE RESPONSE, never from the optimistic draft: the backend
      // is the source of truth.
      state.stateNotes = saved;
      state.stateNotesDraft = saved.active_notes;
      state.stateNotesSubmitStatus = "ready";
    });
  } catch (err) {
    if (signal?.aborted) return;
    if (err instanceof ApiError) {
      runInAction(() => {
        // The proposal-mode `403` (whose message names FEAT-010 as unbuilt) and
        // the archived-book `403` arrive through this same branch, and the draft
        // is left exactly as the author typed it. There is no `409` path.
        state.stateNotesServerErrors =
          err.status >= 400 && err.status < 500
            ? { active_notes: err.message || "Could not save the state notes." }
            : { form: err.message || "Could not save the state notes." };
        state.stateNotesSubmitStatus = "error";
      });
      return;
    }
    throw err;
  }
}
