import { makeAutoObservable, runInAction } from "mobx";
import * as chaptersApi from "../../api/chapters";
import { ApiError } from "../../api/client";
import type {
  ChapterAuthorPromptResponse,
  ChapterLifecycleState,
  ChapterResponse,
  UpdateChapterAuthorPromptRequest,
  UpdateChapterSketchRequest,
} from "../../types/chapters";
import { resolveEditability } from "../subject";

// Page state for `ChapterPage` — one chapter in the working page's content pane
// (`/work/:bookId/chapter/:id`; FEAT-008 · UC-033 · US-034, plus the per-author
// chapter system prompt, which decision D1 defines and which has no product id
// yet — `014.chapter-skeleton/context.md` → "Product situation").
//
// `bookStatePageState.ts` is the DIRECT model and this module copies its grain
// field-for-field with a chapter id added: observable data + pure `get` computeds
// on the class, every effectful operation an external `(state, bookId, chapterId,
// signal?)` function using `runInAction`, and every loadable an async trio
// (`x` / `xStatus` / `xError`). Per the enforced MobX rules the class has NO
// effectful methods and NO setters.
//
// TWO INDEPENDENT TRIOS: the chapter, and the caller's OWN chapter system prompt.
// They load through different endpoints and fail independently — a prompt failure
// must not blank the chapter view, and a chapter failure must not hide the prompt
// section's own state (DoD-11).
//
// WHAT THIS MODULE DELIBERATELY HAS NOT GOT (`008.context.md`):
// - No restore-buffer wiring, no `baseVersion`, no stale-buffer detection, no
//   divergence/reconciliation view and no `409` path. Neither row carries a
//   version token: the sketch is last-write-wins (D6) and the prompt row has
//   exactly one writer.
// - No `clientErrors` and no `errors` union on EITHER editor. Every string, `""`
//   included, is a valid sketch and a valid prompt, so there is no client-side
//   validation layer to hold (the `021` shape). The one client-validated field in
//   feature 014 is the ADD form's title, and it lives in `chaptersPageState.ts`.
// - No `text` / body field of any kind. The chapter body is
//   `015.chapter-writing-free-mode`'s and `ChapterResponse` does not carry it.
// - No delete control for the prompt: `""` already means "no prompt" and the wire
//   has no DELETE verb.

/**
 * Author-facing labels for the chapter lifecycle union. Module-private and
 * deliberately NOT exported: no shared label map was frozen (step 006 and step 007
 * made the same call), and the wording contract on
 * {@link ChapterPageState.lifecycleStateLabel} is what keeps this page and
 * `ChapterOrderList`'s state badge word-for-word identical.
 */
const LIFECYCLE_STATE_LABELS: Record<ChapterLifecycleState, string> = {
  planned: "Planned",
  open: "Open",
  closing: "Closing",
  closed: "Closed",
};

/**
 * Page state for `ChapterPage`, held via `useState(() => new ChapterPageState())`.
 *
 * Holds four things:
 *
 * - **the chapter trio** — the loaded `ChapterResponse` (title, ordinal, lifecycle
 *   state, sketch), its status and its error;
 * - **the sketch editor** — a draft, a server-error map and a submit status, plus
 *   the computeds that answer *may this be edited at all* (only on a `planned`
 *   chapter — UC-033 / US-034.AC-1) and *may it be saved right now*;
 * - **the own-prompt trio** — the caller's own chapter system prompt, its status
 *   and its error. It is per-author (D1), so it can never ride on the chapter-
 *   shaped `chapter` response and always loads separately;
 * - **the prompt editor** — a draft, a server-error map and a submit status. It
 *   has NO editability gate: a member writes their own prompt on a chapter in
 *   every lifecycle state, `closed` included (DoD-10).
 *
 * The state owns NEITHER the book id NOR the chapter id: both arrive as arguments
 * on every external effect, and the page (which has them from `useParams`) is what
 * builds the content-pane subject. That is a deliberate departure from
 * `codexEntryPageState.ts`, whose constructor stores its ids because its restore-
 * buffer key needs them — this page has no buffer.
 */
export class ChapterPageState {
  /**
   * The chapter as the server last returned it — the value the sketch draft is
   * compared against and re-seeded from, and the source of the title, the ordinal
   * and the lifecycle state on screen. `null` until the first successful load.
   */
  chapter: ChapterResponse | null = null;
  chapterStatus: "idle" | "loading" | "ready" | "error" = "idle";
  chapterError: string | null = null;

  /**
   * The sketch editor's draft, seeded from the loaded chapter's `sketch` and
   * re-seeded from the PATCH response on save. Every string is valid input, `""`
   * included (DoD-5) — there is no client-side validation and no non-blank rule.
   * NOT mirrored into the working page's restore buffer.
   */
  sketchDraft = "";

  /**
   * Server refusals for the sketch SAVE only, held separately from the load trio's
   * `chapterError`. Keyed by field name (`sketch`) plus the general `form` key for
   * non-field refusals — including the `409` a non-`planned` chapter answers with,
   * which is the server's authority over the client's affordance (DoD-4). There is
   * NO `clientErrors` counterpart and no `errors` union.
   */
  sketchServerErrors: Record<string, string> = {};

  /** In-flight state of the sketch save (the load has its own `chapterStatus`). */
  sketchSubmitStatus: "idle" | "loading" | "ready" | "error" = "idle";

  /**
   * The caller's OWN system prompt for this chapter, as last returned by the
   * server. `null` until the first successful load; a stored `system_prompt` of
   * `""` is a normal loaded value, NOT an absence and NOT an error state (DoD-7).
   */
  systemPrompt: ChapterAuthorPromptResponse | null = null;
  systemPromptStatus: "idle" | "loading" | "ready" | "error" = "idle";
  systemPromptError: string | null = null;

  /**
   * The prompt editor's draft, seeded from the server's `system_prompt` on load and
   * re-seeded from the PUT response on save. `""` is a legal save that clears the
   * prompt (DoD-9), which is why there is no delete control anywhere on the page.
   */
  systemPromptDraft = "";

  /**
   * Server refusals for the prompt save only, held separately from the load trio's
   * `systemPromptError`. Keyed by field name (`system_prompt`) plus the general
   * `form` key. No `clientErrors`, no `errors` union — every string is valid.
   */
  systemPromptServerErrors: Record<string, string> = {};

  /** In-flight state of the prompt save. */
  systemPromptSubmitStatus: "idle" | "loading" | "ready" | "error" = "idle";

  constructor() {
    makeAutoObservable(this);
  }

  /**
   * The chapter's lifecycle state as author-facing text (DoD-1). The label is the
   * lifecycle word itself, capitalised — `planned` → `"Planned"`, `open` → `"Open"`,
   * `closing` → `"Closing"`, `closed` → `"Closed"` — so it agrees word-for-word with
   * the state badge `ChapterOrderList` already renders on the chapters list, and so
   * it is reachable as accessible text rather than as a colour. `""` before the
   * first successful load.
   */
  get lifecycleStateLabel(): string {
    const state = this.chapter?.state;
    if (!state) return "";
    return LIFECYCLE_STATE_LABELS[state] ?? "";
  }

  /**
   * Whether the sketch may be edited at all: `true` **only** when the loaded
   * chapter's state is `planned` (UC-033 — `domain-chapter.md`: only a planned
   * chapter may have its sketch edited). `false` before the first successful load,
   * on a failed load, and for `open` / `closing` / `closed` (DoD-3).
   *
   * This is a client AFFORDANCE and never substitutes for the server's answer: the
   * backend refuses a non-`planned` sketch edit with `409` regardless (DoD-4).
   */
  get canEditSketch(): boolean {
    return this.chapter?.state === "planned";
  }

  /**
   * Why the sketch editor is disabled, as author-facing READABLE TEXT — `null`
   * exactly when {@link ChapterPageState.canEditSketch} is `true`, and a non-empty
   * sentence otherwise (DoD-3: "disabled, with a stated reason"; the reason must be
   * text a screen reader and a role/label query can reach, never a visual state).
   *
   * Wording contract: for `closing` and `closed`, reuse `work/subject.ts`'s
   * `resolveEditability` reason VERBATIM — that module owns the chapter's
   * read-only copy and no new string is written here (the `codexEntryPageState.ts`
   * precedent). `open` has no `resolveEditability` reason to reuse (an `open`
   * chapter is editable whole, in its BODY), so that one sentence is this page's
   * own and must say that the sketch is fixed once the chapter has been opened for
   * writing. Before the first successful load there is nothing loaded to state a
   * reason about, so the sentence says exactly that rather than naming a state the
   * page does not have.
   */
  get sketchDisabledReason(): string | null {
    if (this.canEditSketch) return null;

    const chapterState = this.chapter?.state;
    if (chapterState === undefined) {
      return "This chapter has not loaded yet, so its sketch cannot be edited.";
    }
    if (chapterState === "open") {
      // The one sentence this page owns: an `open` chapter is editable WHOLE in
      // `resolveEditability` (its body is what is being written), so there is no
      // read-only reason there to reuse.
      return "This chapter has been opened for writing, so its sketch is fixed and can no longer be edited.";
    }
    // `closing` / `closed`: `work/subject.ts` owns the chapter's read-only copy, so
    // the reason is that module's string VERBATIM and nothing new is written here
    // (the `codexEntryPageState.ts` precedent).
    return (
      resolveEditability({
        kind: "chapter",
        entityId: this.chapter?.id,
        chapterState,
      }).readOnlyReason ?? "This chapter's sketch cannot be edited in its current state."
    );
  }

  /**
   * `true` when the sketch draft differs from what the server last returned. A
   * not-yet-loaded chapter compares as `""`. Pure — no side effects, no I/O.
   */
  get sketchDirty(): boolean {
    return this.sketchDraft !== (this.chapter?.sketch ?? "");
  }

  /**
   * `true` when saving the sketch is currently allowed: the chapter has loaded, its
   * sketch is editable ({@link ChapterPageState.canEditSketch}), the draft is dirty,
   * and no save is in flight (DoD-5). Deliberately NO emptiness check — `""` is a
   * legal sketch. Pure.
   */
  get canSaveSketch(): boolean {
    return (
      this.chapterStatus === "ready" &&
      this.canEditSketch &&
      this.sketchDirty &&
      this.sketchSubmitStatus !== "loading"
    );
  }

  /**
   * `true` when the prompt draft differs from what the server last returned. A
   * member who has never written one compares against `""`, so they count as dirty
   * once they type. Pure.
   */
  get systemPromptDirty(): boolean {
    return this.systemPromptDraft !== (this.systemPrompt?.system_prompt ?? "");
  }

  /**
   * `true` when saving the prompt is currently allowed: the prompt has loaded
   * (nothing may be written over a value that was never read), no save is in
   * flight, and the draft is dirty. Deliberately NO emptiness check (`""` clears
   * the prompt — DoD-9) and deliberately NO lifecycle-state gate: the prompt is the
   * caller's own instruction to their own assistant and is writable on a chapter in
   * EVERY state, `open` and `closed` included (DoD-10). Pure.
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
 * Load the chapter and SEED THE SKETCH DRAFT from it.
 *
 * The `bookStatePageState.ts:loadBookState` shape verbatim: set
 * `chapterStatus = "loading"` and clear `chapterError`, await
 * `chaptersApi.getChapter(bookId, chapterId, signal)`, then `runInAction` `chapter`
 * + `sketchDraft = chapter.sketch` + `chapterStatus = "ready"`; return silently when
 * `signal?.aborted`; map an `ApiError` into `chapterError` / `chapterStatus =
 * "error"` leaving `chapter` null so no editor binds to stale data, else rethrow.
 *
 * Touches NOTHING in the prompt trio — the two loadables fail independently
 * (DoD-11). Also the retry path behind the chapter error branch.
 */
export async function loadChapter(
  state: ChapterPageState,
  bookId: string,
  chapterId: string,
  signal?: AbortSignal,
): Promise<void> {
  runInAction(() => {
    state.chapterStatus = "loading";
    state.chapterError = null;
  });
  try {
    const chapter = await chaptersApi.getChapter(bookId, chapterId, signal);
    if (signal?.aborted) return;
    runInAction(() => {
      state.chapter = chapter;
      state.sketchDraft = chapter.sketch;
      state.chapterStatus = "ready";
    });
  } catch (err) {
    if (signal?.aborted) return;
    if (err instanceof ApiError) {
      runInAction(() => {
        state.chapterError = err.message;
        state.chapterStatus = "error";
      });
      return;
    }
    throw err;
  }
}

/**
 * Save the sketch draft.
 *
 * The body is `{ sketch: state.sketchDraft }` read off the state verbatim — no
 * trimming, no emptiness check, no `expected_version` (D6: the sketch path carries
 * no version token and has no `409`-on-conflict branch; the `409` this endpoint CAN
 * answer is the not-`planned` refusal, which is an ordinary server error here).
 *
 * Clears `sketchServerErrors`, sets `sketchSubmitStatus = "loading"`, awaits
 * `chaptersApi.updateChapterSketch(bookId, chapterId, body, signal)`, then RE-SEEDS
 * BOTH `chapter` and `sketchDraft` **from the response body directly** — the backend
 * is the source of truth, and the editor must then show the value the SERVER
 * returned, not the optimistic draft (DoD-2). Returns silently when
 * `signal?.aborted`. On `ApiError` the message lands in `sketchServerErrors` (4xx →
 * the `sketch` key, 5xx → the general `form` key) with `sketchSubmitStatus =
 * "error"`, **leaving `sketchDraft` untouched** so a refusal loses nothing the
 * author typed (DoD-4); anything else rethrows.
 *
 * Takes no argument beyond the two ids — the draft is read off `state`, so the
 * editor is the single source of the submitted value.
 */
export async function saveSketch(
  state: ChapterPageState,
  bookId: string,
  chapterId: string,
  signal?: AbortSignal,
): Promise<void> {
  const body: UpdateChapterSketchRequest = { sketch: state.sketchDraft };

  runInAction(() => {
    state.sketchServerErrors = {};
    state.sketchSubmitStatus = "loading";
  });

  try {
    const saved = await chaptersApi.updateChapterSketch(bookId, chapterId, body, signal);
    if (signal?.aborted) return;
    runInAction(() => {
      state.chapter = saved;
      state.sketchDraft = saved.sketch;
      state.sketchSubmitStatus = "ready";
    });
  } catch (err) {
    if (signal?.aborted) return;
    if (err instanceof ApiError) {
      runInAction(() => {
        state.sketchServerErrors =
          err.status >= 400 && err.status < 500
            ? { sketch: err.message || "Could not save the sketch." }
            : { form: err.message || "Could not save the sketch." };
        state.sketchSubmitStatus = "error";
      });
      return;
    }
    throw err;
  }
}

/**
 * Load the caller's OWN chapter system prompt and seed its draft. The
 * `bookStatePageState.ts:loadSystemPrompt` shape, one level down.
 *
 * Set `systemPromptStatus = "loading"` and clear `systemPromptError`, await
 * `chaptersApi.getOwnChapterSystemPrompt(bookId, chapterId, signal)`, then
 * `runInAction` `systemPrompt` + `systemPromptDraft = prompt.system_prompt` +
 * `systemPromptStatus = "ready"`; return silently when `signal?.aborted`; map an
 * `ApiError` into `systemPromptError` / `systemPromptStatus = "error"` leaving
 * `systemPrompt` null, else rethrow.
 *
 * An empty `system_prompt` is a NORMAL loaded value, never an error — a member who
 * has written no prompt for this chapter gets an empty, editable field (DoD-7); the
 * backend answers `200` with `""` rather than `404`. Touches nothing in the chapter
 * trio (DoD-11).
 */
export async function loadSystemPrompt(
  state: ChapterPageState,
  bookId: string,
  chapterId: string,
  signal?: AbortSignal,
): Promise<void> {
  runInAction(() => {
    state.systemPromptStatus = "loading";
    state.systemPromptError = null;
  });
  try {
    const prompt = await chaptersApi.getOwnChapterSystemPrompt(bookId, chapterId, signal);
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
 * Save the draft as the caller's own chapter system prompt. The
 * `bookStatePageState.ts:saveSystemPrompt` shape, one level down.
 *
 * Body `{ system_prompt: state.systemPromptDraft }`, verbatim — `""` is a legal
 * value that clears the prompt (DoD-9), which is why there is no DELETE verb and no
 * delete control. Clears `systemPromptServerErrors`, sets `systemPromptSubmitStatus
 * = "loading"`, awaits `chaptersApi.updateOwnChapterSystemPrompt(bookId, chapterId,
 * body, signal)`, then re-seeds BOTH `systemPrompt` and `systemPromptDraft` from the
 * RESPONSE body directly (DoD-8). Returns silently when `signal?.aborted`. On
 * `ApiError` the message lands in `systemPromptServerErrors` (4xx → the
 * `system_prompt` key, 5xx → the general `form` key) with `systemPromptSubmitStatus
 * = "error"` and `systemPromptDraft` UNTOUCHED; anything else rethrows. No `409`
 * path — this row carries no version token and has exactly one writer.
 */
export async function saveSystemPrompt(
  state: ChapterPageState,
  bookId: string,
  chapterId: string,
  signal?: AbortSignal,
): Promise<void> {
  const body: UpdateChapterAuthorPromptRequest = { system_prompt: state.systemPromptDraft };

  runInAction(() => {
    state.systemPromptServerErrors = {};
    state.systemPromptSubmitStatus = "loading";
  });

  try {
    const saved = await chaptersApi.updateOwnChapterSystemPrompt(bookId, chapterId, body, signal);
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
