import { makeAutoObservable, runInAction } from "mobx";
import * as chaptersApi from "../../api/chapters";
import { ApiError } from "../../api/client";
import type {
  ChapterAuthorPromptResponse,
  ChapterLifecycleState,
  ChapterResponse,
  ChapterTextResponse,
  UpdateChapterAuthorPromptRequest,
  UpdateChapterSketchRequest,
  UpdateChapterTextRequest,
} from "../../types/chapters";
import { clearBuffer, readBuffer, restoreBufferKey, writeBuffer } from "../restoreBuffer";
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
// THREE INDEPENDENT TRIOS: the chapter, the caller's OWN chapter system prompt,
// and — added by `015.chapter-writing-free-mode` step 006 — the chapter BODY.
// All three load through different endpoints and fail independently: a prompt
// failure must not blank the chapter view, a chapter failure must not hide the
// prompt section's own state (014 DoD-11), and the body failing must not take
// either of the other two down (015/006 DoD-1). `frontend.md` is explicit that
// three loadables means three trios and NO aggregation type — there is none here.
//
// WHAT THIS MODULE DELIBERATELY HAS NOT GOT (`008.context.md`, amended by 015/006):
// - No `clientErrors` and no `errors` union on ANY of the three editors. Every
//   string, `""` included, is a valid sketch, a valid prompt and a valid BODY, so
//   there is no client-side validation layer to hold (the `021` shape). The one
//   client-validated field in feature 014 is the ADD form's title, and it lives in
//   `chaptersPageState.ts`.
// - No restore buffer, no divergence view and no `409` reconciliation for the
//   SKETCH or the PROMPT, ever: neither carries a version token at all (the sketch
//   is last-write-wins — D6 — and the prompt row has exactly one writer), and only
//   the BODY is buffered (the principal-text-field rule, `frontend-work-drafts.md`).
//   `BufferedDraft.draft` is a single string and is NOT widened to a multi-field
//   shape; an unsaved sketch is lost on an unload, and the divergence view compares
//   BODIES only. The body's buffer, its two reconciliation entrances and its
//   take-one-side resolution are step 007's, at the bottom of this module.
// - No `applyDraft` and no canvas hook — step 012's. `editBodyDraft` below is the
//   single entry point every body-draft change routes through, so 007 and 012 have
//   exactly one place to hook.
// - No delete control for the prompt: `""` already means "no prompt" and the wire
//   has no DELETE verb.
//
// THE BODY (015/006): the body trio, the body draft state, the editor generation
// counter, the three body computeds and the three body effects live at the bottom of
// this module, appended after 014's members and changing none of them.

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
 * Which side the author takes when reconciling a diverged chapter body — ONE SIDE
 * WHOLE, never an auto-merge and never a third, system-produced merged outcome
 * (`domain-chapter.md`: "there is no automatic merge at MVP"; a merged body is
 * something the author types).
 *
 * - `"server"` — discard the draft and adopt the server's current body.
 * - `"draft"` — keep the draft and re-save it against the server's NEW `version`.
 *
 * Declared locally rather than imported from `codexEntryPageState.ts`: that union
 * lives in another PAGE's state module, and importing it would drag the codex page
 * (and `api/codex`) into this page's module graph for two string literals.
 */
export type ChapterReconciliationSide = "server" | "draft";

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
 * buffer key needs them; here the body's buffer key is built inside each effect from
 * the `(bookId, chapterId)` arguments it already carries, so there is no `bufferKey`
 * computed on this class.
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

  /**
   * THE BODY TRIO (015/006) — the chapter body as the server last returned it:
   * its `text`, the `state` that qualifies it and the `version` a save must carry.
   * `null` until the first successful load.
   *
   * It is a THIRD trio, not a widening of the chapter trio: the two come from
   * different endpoints (D13) and must fail independently in BOTH directions
   * (DoD-1). There is deliberately no aggregation type over the three.
   */
  body: ChapterTextResponse | null = null;
  bodyStatus: "idle" | "loading" | "ready" | "error" = "idle";
  bodyError: string | null = null;

  /**
   * The body editor's MARKDOWN draft (D2 — `Chapter.text` is Markdown), seeded from
   * the loaded body and re-seeded from the PUT response on save. Every string is a
   * valid body, `""` included (DoD-5), so there is no client-side validation layer
   * and no `clientErrors` counterpart.
   *
   * Written by exactly one function — {@link editBodyDraft} — whichever the source
   * of the change is (a keystroke today; an assistant canvas frame, an undo pop, a
   * buffer restore or a reconciliation choice in steps 007 / 012).
   */
  bodyDraft = "";

  /**
   * Server refusals for the body SAVE only, held separately from the load trio's
   * `bodyError` so a refused save never blanks the editor the author is looking at.
   * Keyed by field name (`text`) plus the general `form` key, exactly as
   * `sketchServerErrors` is.
   *
   * A `409` lands here like any other refusal (`006.context.md`): this step adds NO
   * reconciliation, no re-fetch and no divergence view — step 007 does, with its
   * consumer.
   */
  bodyServerErrors: Record<string, string> = {};

  /** In-flight state of the body save (the load has its own `bodyStatus`). */
  bodySubmitStatus: "idle" | "loading" | "ready" | "error" = "idle";

  /**
   * The version the draft was composed against — **the `version` the BODY response
   * carried, and nothing else.**
   *
   * 014's `ChapterResponse` also carries a `version`; it is IGNORED for the save.
   * The body and its version arrive together, and a save composed against a version
   * that came with a different payload is exactly the stale-write bug the contract
   * exists to prevent — one field, one source (`006.context.md`). Seeded by
   * {@link loadChapterBody} and re-seeded from the PUT response by
   * {@link saveChapterBody}, so two sequential saves both succeed (DoD-4).
   *
   * `null` before the first successful body load; a save is not issuable then.
   * A `number`, not an ISO string — that is the one deliberate difference from the
   * `codexEntryPageState.ts` template, and it is what `restoreBuffer.ts`'s
   * `BufferBaseVersion = number | string` has always had a number case for (step 007).
   */
  bodyBaseVersion: number | null = null;

  /**
   * THE EDITOR GENERATION COUNTER (D15) — a plain observable number the VIEW keys
   * `ChapterBodyEditor` on, and reads for NOTHING else: it is never rendered, never
   * compared and never persisted.
   *
   * TipTap owns its own document and is told about an external change by being
   * REMOUNTED, so every write to {@link ChapterPageState.bodyDraft} that did not
   * originate inside the editor bumps this; a keystroke never does. This step bumps
   * it in exactly ONE place — {@link loadChapterBody}, where the body load seeds the
   * draft (DoD-10). A SAVE does not bump it either: the draft it re-seeds is the
   * one the editor already holds, and remounting there would throw away the author's
   * caret for nothing. Steps 007 and 012 bump it from their own external writes.
   */
  bodyEditorGeneration = 0;

  /**
   * THE SERVER'S CURRENT BODY (015/007), re-fetched after a `409` — or the body
   * that just loaded, when the restore buffer's base version no longer matches it —
   * and held **BESIDE** {@link ChapterPageState.bodyDraft} so the page can show both.
   *
   * NEVER merged into the draft automatically and never written over it: the two
   * reconciliation entrances only ever put a value HERE and raise
   * {@link ChapterPageState.isReconcilingBody}. `null` whenever the page is not
   * reconciling.
   */
  bodyConflict: ChapterTextResponse | null = null;

  /**
   * When `true` the body section renders the DIVERGENCE VIEW instead of the editor
   * (015/007). Raised by BOTH entrances — a stale buffer detected at load (the
   * load-bearing one, and no save is attempted there) and a `409` from the save —
   * and lowered by {@link resolveBodyConflict}, whichever side is taken.
   *
   * The divergence view is the NORMAL landing for the navigated-away-mid-turn path,
   * not an error state (`frontend-work-drafts.md`): it is not a modal, is not styled
   * as a failure, and does not block the rest of the page.
   */
  isReconcilingBody = false;

  /**
   * The buffer keys the most recent body-draft buffer write had to evict to fit
   * (`WriteResult.status === "saved-after-eviction"`), so the page can tell the
   * author WHICH other items' drafts were dropped — an eviction is data loss on some
   * other item and is never silent (015/007). Empty after a plain `"saved"`.
   *
   * Surfacing only: the eviction policy is `restoreBuffer.ts`'s and is already
   * implemented and unit-tested. It never evicts the key currently being written, so
   * THIS chapter's own buffer is never the victim.
   */
  evictedBufferKeys: string[] = [];

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

  /**
   * `true` when the body draft differs from the body the server last returned. A
   * not-yet-loaded body compares as `""`. Pure — no side effects, no I/O.
   */
  get bodyDirty(): boolean {
    return this.bodyDraft !== (this.body?.text ?? "");
  }

  /**
   * Whether the body may be edited at all: `true` **only** when the loaded BODY
   * RESPONSE's state is `open` (D2 / D16 — the editor is mounted for the open
   * chapter and for nothing else). `false` before the first successful body load,
   * on a failed one, and for `planned` / `closing` / `closed` (DoD-8).
   *
   * It reads `body.state`, NOT `chapter.state`: the body region must be able to gate
   * itself without depending on which trio resolved first, which is precisely why
   * `ChapterTextResponse` carries the state (`context.md` → the wire contract).
   *
   * A client AFFORDANCE that never substitutes for the server's answer — a write to
   * a non-`open` chapter is refused `409` regardless.
   */
  get canEditBody(): boolean {
    return this.body?.state === "open";
  }

  /**
   * `true` when a body save may be issued right now: the body has loaded
   * (`bodyStatus === "ready"`, so there IS a base version to compose against), it is
   * editable ({@link ChapterPageState.canEditBody}), the draft is dirty, and no save
   * is in flight (DoD-5). Deliberately NO emptiness check — saving an empty body is
   * allowed, `""` is a legitimate chapter body. Pure.
   */
  get canSaveBody(): boolean {
    return (
      this.bodyStatus === "ready" &&
      this.canEditBody &&
      this.bodyDirty &&
      this.bodySubmitStatus !== "loading"
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

/**
 * Load the chapter BODY and seed the draft, the base version and the editor
 * generation from it (015/006). The third load the page starts on mount.
 *
 * Contract, the `loadChapter` shape one field down:
 *
 * - `bodyStatus = "loading"`, `bodyError = null`;
 * - await `chaptersApi.getChapterText(bookId, chapterId, signal)`;
 * - return silently when `signal?.aborted`;
 * - `runInAction`: `body = response`, `bodyDraft = response.text`,
 *   **`bodyBaseVersion = response.version`** — the version comes from THIS response
 *   and from nowhere else; 014's `chapter.version` is not read here or anywhere —
 *   `bodyEditorGeneration += 1` (the ONE bump this step makes: the draft was written
 *   from OUTSIDE the editor, so TipTap must be remounted to see it — D15 / DoD-10),
 *   `bodyStatus = "ready"`;
 * - on `ApiError`: `bodyError = err.message`, `bodyStatus = "error"`, leaving `body`
 *   null so nothing binds to a body that never arrived; anything else rethrows.
 *
 * Touches NOTHING in the chapter trio or the prompt trio — the three loadables fail
 * independently, in every direction (DoD-1). Also the retry path behind the body
 * error branch.
 *
 * **THE LOAD-TIME ENTRANCE — the LOAD-BEARING one (015/007)** ("entrance 2
 * protects the author who simply comes back to the page, which is the far commoner
 * case and the one a save-centred design misses"). After the body arrives, read
 * `readBuffer(restoreBufferKey(bookId, "chapter", chapterId))` — reads are TOTAL, so
 * an absent, non-JSON or wrong-shaped entry is `null`, never a throw — and branch:
 *
 * - **no buffer** → exactly the behaviour above, unchanged;
 * - **`buffer.baseVersion === response.version`** → RESTORE the buffered draft over
 *   the server's text (`bodyDraft = buffer.draft`) and BUMP
 *   {@link ChapterPageState.bodyEditorGeneration} — the draft was written from
 *   outside the editor (US-107.AC-1 / US-107.AC-2);
 * - **a MISMATCH** → the buffered draft is stale: put it in `bodyDraft`, hold the
 *   just-loaded response in {@link ChapterPageState.bodyConflict}, raise
 *   {@link ChapterPageState.isReconcilingBody} — and attempt **NO SAVE**. The
 *   mismatch is detected BEFORE anything is sent.
 *
 * `bodyBaseVersion` stays the SERVER's `version` in every branch: it is the version
 * the next save must carry, not the version the draft forked from.
 */
export async function loadChapterBody(
  state: ChapterPageState,
  bookId: string,
  chapterId: string,
  signal?: AbortSignal,
): Promise<void> {
  runInAction(() => {
    state.bodyStatus = "loading";
    state.bodyError = null;
  });
  try {
    const body = await chaptersApi.getChapterText(bookId, chapterId, signal);
    if (signal?.aborted) return;

    // THE LOAD-TIME ENTRANCE. Reads are TOTAL — an absent, non-JSON or wrong-shaped
    // entry comes back `null`, so there is no defensive parsing to do here.
    const buffered = readBuffer(restoreBufferKey(bookId, "chapter", chapterId));
    // A buffer whose base version is no longer the server's is STALE: the body moved
    // under the draft. The numeric `Chapter.version` is compared as it was written;
    // a buffer carrying the `""` no-base-version marker (D18) can never match one,
    // so it reads as stale by construction.
    const stale = buffered !== null && buffered.baseVersion !== body.version;

    runInAction(() => {
      state.body = body;
      // No buffer → the server's text, exactly as before. A buffer → the author's
      // buffered draft, whether it matches (a restore) or not (a divergence).
      state.bodyDraft = buffered === null ? body.text : buffered.draft;
      // THE version — this response's, never 014's `chapter.version` — and the
      // SERVER's in every branch: it is the version the next save must carry, not
      // the one the draft forked from.
      state.bodyBaseVersion = body.version;
      // The draft was just written from OUTSIDE the editor — the server's text, or
      // the restored buffered draft — so TipTap has to be remounted to see it
      // (D15 / DoD-10 of step 006, and US-107.AC-1 / US-107.AC-2 here).
      state.bodyEditorGeneration += 1;
      if (stale) {
        // NO SAVE IS ATTEMPTED: the mismatch is detected before anything is sent.
        // The server's body is held BESIDE the buffered draft and the author picks
        // a side.
        state.bodyConflict = body;
        state.isReconcilingBody = true;
      }
      state.bodyStatus = "ready";
    });
  } catch (err) {
    if (signal?.aborted) return;
    if (err instanceof ApiError) {
      runInAction(() => {
        state.bodyError = err.message;
        state.bodyStatus = "error";
      });
      return;
    }
    throw err;
  }
}

/**
 * Edit the body draft — **the single entry point every body-draft change routes
 * through** (015/006).
 *
 * Today it has exactly one caller, the editor's `onChange`; it exists as its own
 * function so steps 007 (restore buffer) and 012 (assistant canvas writes, undo)
 * have ONE place to hook rather than three call sites to find. That is also why it
 * carries the two ids step 006 did not read: the buffer key below is
 * `restoreBufferKey(bookId, "chapter", chapterId)`, and a signature that has to grow
 * later is a frozen signature broken later.
 *
 * Contract: set `state.bodyDraft = text` under `runInAction`, and **do not bump**
 * {@link ChapterPageState.bodyEditorGeneration} — a keystroke originates INSIDE the
 * editor, and remounting it on every character would destroy the caret (D15 /
 * DoD-10). Synchronous and server-free: nothing reaches the server until the save
 * control is used (DoD-6), which is why there is no `signal` and no `Promise`.
 *
 * **THE BUFFER WRITE (015/007) — and this is where the two ids are finally read.**
 * On EVERY body-draft change, write
 * `writeBuffer(restoreBufferKey(bookId, "chapter", chapterId), text, state.bodyBaseVersion)`
 * and INSPECT the `WriteResult`: `"saved-after-eviction"` puts its `evictedKeys` into
 * {@link ChapterPageState.evictedBufferKeys} (an eviction is data loss on some other
 * item and is never silent), anything else clears that holder. The base version
 * written is the NUMERIC `Chapter.version` the body response carried — the case
 * `BufferBaseVersion = number | string` has always had and that no writer has used
 * until now — i.e. `state.bodyBaseVersion ?? ""`, where the `""` fallback is the
 * project's established no-base-version marker for a chapter buffer (D18, and
 * `editCodexDraft`'s `?? ""`) and is unreachable through the view, since the editor
 * mounts only for a body that HAS loaded. Still server-free: `localStorage` only,
 * nothing crosses the network (US-107.AC-4 / US-103.AC-3).
 */
export function editBodyDraft(
  state: ChapterPageState,
  bookId: string,
  chapterId: string,
  text: string,
): void {
  runInAction(() => {
    // No generation bump — a keystroke originates INSIDE the editor (D15 / DoD-10).
    state.bodyDraft = text;
  });

  // ONLY THE BODY IS BUFFERED (the principal-text-field rule): `BufferedDraft.draft`
  // is a single string and is not widened, and the sketch and the caller's own prompt
  // carry no version token at all. `localStorage` only — nothing crosses the network
  // (US-107.AC-4 / US-103.AC-3).
  const result = writeBuffer(
    restoreBufferKey(bookId, "chapter", chapterId),
    text,
    // The NUMERIC `Chapter.version` the body response carried — the case
    // `BufferBaseVersion = number | string` has always had. The `""` fallback is the
    // project's no-base-version marker (D18, `editCodexDraft`'s `?? ""`) and is
    // unreachable through the view: the editor mounts only for a body that HAS loaded.
    state.bodyBaseVersion ?? "",
  );
  runInAction(() => {
    // Surfacing only — the eviction policy is `restoreBuffer.ts`'s, and it never
    // evicts the key being written, so THIS chapter's buffer is never the victim. An
    // eviction is data loss on some other item and is never silent.
    state.evictedBufferKeys = result.status === "saved-after-eviction" ? result.evictedKeys : [];
  });
}

/**
 * Save the body draft against the version the BODY response carried (015/006).
 *
 * Contract:
 *
 * - the request body is `{ text: state.bodyDraft, expected_version:
 *   state.bodyBaseVersion }` — the draft verbatim (no trimming, no emptiness check:
 *   `""` is a legal body) and the LOADED base version, never 014's
 *   `chapter.version`. `bodyBaseVersion === null` means nothing has loaded, so the
 *   effect returns without contacting the server;
 * - clear `bodyServerErrors`, `bodySubmitStatus = "loading"`;
 * - await `chaptersApi.updateChapterText(bookId, chapterId, body, signal)`; return
 *   silently when `signal?.aborted`;
 * - on success RE-SEED `body`, `bodyDraft` and `bodyBaseVersion` **from the response
 *   directly** — the backend is the source of truth, so the surface afterwards shows
 *   what the SERVER returned, not the optimistic draft (DoD-3), and the next save
 *   carries the NEW version, so two sequential saves both succeed (DoD-4).
 *   `bodySubmitStatus = "ready"`. The generation counter is **not** bumped;
 * - on `ApiError` the SERVER's message lands in `bodyServerErrors` (4xx → the `text`
 *   key, 5xx → the general `form` key) with `bodySubmitStatus = "error"` and
 *   **`bodyDraft`, `body` and `bodyBaseVersion` all left untouched**, so a refusal
 *   loses nothing the author wrote and overwrites nothing on screen (DoD-7, DoD-9).
 *   Anything that is not an `ApiError` rethrows.
 *
 * **STEP 007 ADDS TWO THINGS HERE — and only these two:**
 *
 * - **on success, CLEAR the buffer** (`clearBuffer(restoreBufferKey(bookId,
 *   "chapter", chapterId))`) and empty {@link ChapterPageState.evictedBufferKeys},
 *   so a later return shows the server's body with no restore. The re-seeding above
 *   is unchanged;
 * - **a `409` becomes the SAVE-TIME ENTRANCE**: re-fetch the body
 *   (`chaptersApi.getChapterText`), hold the response in
 *   {@link ChapterPageState.bodyConflict}, raise
 *   {@link ChapterPageState.isReconcilingBody} and leave the draft, the buffer and
 *   `bodyBaseVersion` untouched. **Never an auto-merge, never a silent overwrite.**
 *   Every OTHER `ApiError` — the `403`s of D10 / D11 included — keeps the ordinary
 *   `bodyServerErrors` surface below, unchanged.
 *
 * The refusal text is `err.message`: `client.ts:throwApiError` already prefers a
 * string `detail`, and `routes/chapters.py:_map_chapter_error` puts the chapter
 * family's refusal on the wire as a **plain-string `detail`**. `CodexEntryPage`'s
 * `serverRefusalText` / `details.detail.message` object path is the CODEX family's
 * and must NOT be copied here (step 004's freeze note).
 *
 * Takes no argument beyond the two ids — the draft and the base version are read off
 * `state`, so the editor is the single source of the submitted value.
 */
export async function saveChapterBody(
  state: ChapterPageState,
  bookId: string,
  chapterId: string,
  signal?: AbortSignal,
): Promise<void> {
  const baseVersion = state.bodyBaseVersion;
  // Nothing has loaded, so there is no version to compose the save against and
  // nothing may be sent — the body the server holds is unknown here.
  if (baseVersion === null) return;

  const body: UpdateChapterTextRequest = {
    text: state.bodyDraft,
    expected_version: baseVersion,
  };

  runInAction(() => {
    state.bodyServerErrors = {};
    state.bodySubmitStatus = "loading";
  });

  try {
    const saved = await chaptersApi.updateChapterText(bookId, chapterId, body, signal);
    if (signal?.aborted) return;
    runInAction(() => {
      // RE-SEEDED FROM THE RESPONSE, never from the optimistic draft: the backend is
      // the source of truth (DoD-3), and the next save carries the NEW version so two
      // sequential saves both succeed (DoD-4). No generation bump — the draft this
      // writes is the one the editor already holds.
      state.body = saved;
      state.bodyDraft = saved.text;
      state.bodyBaseVersion = saved.version;
      state.bodySubmitStatus = "ready";
      state.evictedBufferKeys = [];
    });
    // The draft is now the server's body, so the buffer has nothing left to protect:
    // a later return shows the server's body with NO restore (015/007).
    clearBuffer(restoreBufferKey(bookId, "chapter", chapterId));
  } catch (err) {
    if (signal?.aborted) return;
    if (!(err instanceof ApiError)) throw err;

    if (err.status === 409) {
      // THE SAVE-TIME ENTRANCE. The version the draft forked from is no longer the
      // server's: re-read the current body and hold it BESIDE the draft. Never an
      // auto-merge, never a silent overwrite — the draft, the buffer and
      // `bodyBaseVersion` are all left exactly as they are.
      try {
        const current = await chaptersApi.getChapterText(bookId, chapterId, signal);
        if (signal?.aborted) return;
        runInAction(() => {
          state.bodyConflict = current;
          state.isReconcilingBody = true;
          state.bodyServerErrors = {};
          state.bodySubmitStatus = "idle";
        });
      } catch (refetchErr) {
        if (signal?.aborted) return;
        if (!(refetchErr instanceof ApiError)) throw refetchErr;
        // The re-fetch itself failed, so there is no server body to show against the
        // draft: fall back to the ordinary refusal surface, still overwriting nothing.
        runInAction(() => {
          state.bodyServerErrors = {
            form: refetchErr.message || "Could not save the chapter body.",
          };
          state.bodySubmitStatus = "error";
        });
      }
      return;
    }

    runInAction(() => {
      // Every OTHER refusal — the `403`s of D10 / D11 included — leaves `bodyDraft`,
      // `body` and `bodyBaseVersion` untouched, so it loses nothing the author wrote
      // and overwrites nothing on screen (DoD-7, DoD-9).
      state.bodyServerErrors =
        err.status >= 400 && err.status < 500
          ? { text: err.message || "Could not save the chapter body." }
          : { form: err.message || "Could not save the chapter body." };
      state.bodySubmitStatus = "error";
    });
  }
}

/**
 * Resolve a diverged chapter body by taking **ONE SIDE WHOLE** (015/007). The author
 * reconciles; the system never merges, and there is no third, merged outcome — a
 * merged body is something the author types (`domain-chapter.md`: "no rebase, no
 * three-way reconcile, no heuristic re-anchoring").
 *
 * Reached from BOTH entrances, which raise the same
 * {@link ChapterPageState.isReconcilingBody} flag: the stale buffer detected at load,
 * and the `409` from the save.
 *
 * - **`"server"`** → discard the draft: CLEAR the buffer
 *   (`clearBuffer(restoreBufferKey(bookId, "chapter", chapterId))`), adopt
 *   {@link ChapterPageState.bodyConflict} as `body`, re-seed `bodyDraft` and
 *   `bodyBaseVersion` from it, **BUMP {@link ChapterPageState.bodyEditorGeneration}**
 *   (the draft was replaced from outside the editor — D15), clear `bodyConflict`,
 *   `evictedBufferKeys` and `bodyServerErrors`, and lower the flag. Nothing of the
 *   abandoning author's text is written anywhere (US-041.AC-3).
 * - **`"draft"`** → keep the draft: adopt the server's **VERSION FIRST**
 *   (`bodyBaseVersion` — and `body` — become `bodyConflict`'s, so the base version is
 *   now the CURRENT one), leave the view (`bodyConflict = null`,
 *   `isReconcilingBody = false`), and only THEN re-save through
 *   {@link saveChapterBody}, which now carries a version the server agrees with
 *   (US-041.AC-2). `bodyDraft` is NOT re-seeded and the generation is NOT bumped —
 *   the editor already holds this text.
 *
 *   **THE ORDERING IS THE POINT.** Re-saving before adopting the server's version
 *   sends the stale version again, the server refuses `409` again, and the page walks
 *   straight back into this view — an infinite loop that reads as a server bug.
 *
 * `(state, side, …, signal?)` mirrors `resolveCodexConflict(state, side, signal?)`;
 * the two ids sit in the middle because this state owns neither (014's deliberate
 * departure) and the buffer key needs both — the same reason `editBodyDraft` carries
 * them.
 */
export async function resolveBodyConflict(
  state: ChapterPageState,
  side: ChapterReconciliationSide,
  bookId: string,
  chapterId: string,
  signal?: AbortSignal,
): Promise<void> {
  const current = state.bodyConflict;

  if (side === "server") {
    // Discard the draft. The buffer goes with it, so nothing of the abandoning
    // author's text survives anywhere — and nothing of it is written to the server
    // either: this branch contacts nothing (US-041.AC-3).
    clearBuffer(restoreBufferKey(bookId, "chapter", chapterId));
    runInAction(() => {
      if (current !== null) {
        state.body = current;
        state.bodyBaseVersion = current.version;
      }
      // Re-seeded from the SERVER's body, and the editor remounted to see it — the
      // draft was replaced from outside it (D15).
      state.bodyDraft = state.body?.text ?? "";
      state.bodyEditorGeneration += 1;
      state.bodyConflict = null;
      state.isReconcilingBody = false;
      state.evictedBufferKeys = [];
      state.bodyServerErrors = {};
      state.bodySubmitStatus = "idle";
    });
    return;
  }

  // Keep the draft. ADOPT THE SERVER'S VERSION FIRST — `bodyBaseVersion` becomes the
  // CURRENT one — then leave the view, and only THEN re-save. THE ORDERING IS THE
  // POINT: re-saving before adopting sends the stale version again, the server
  // refuses `409` again, and the page walks straight back into this view — an
  // infinite loop that reads as a server bug.
  //
  // `bodyDraft` is NOT re-seeded and the generation is NOT bumped: the editor
  // already holds this text, and remounting would throw the caret away for nothing.
  runInAction(() => {
    if (current !== null) {
      state.body = current;
      state.bodyBaseVersion = current.version;
    }
    state.bodyConflict = null;
    state.isReconcilingBody = false;
    state.bodyServerErrors = {};
  });
  await saveChapterBody(state, bookId, chapterId, signal);
}
