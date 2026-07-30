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
import type { CanvasField, CanvasOp } from "../../types/chats";
import { popChapterUndoSnapshot, pushChapterUndoSnapshot } from "../chapterUndo";
import { setContentSelection } from "../contentSubject";
import type { ContentSubjectSource } from "../contentSubject";
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
// - No second write path for an assistant canvas frame: `applyDraft` (015/012)
//   routes its result through `editBodyDraft` below, which is the single entry
//   point EVERY body-draft change takes — a keystroke, a buffer restore, a
//   reconciliation choice, an assistant write and an undo alike.
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
 * The ONE lifecycle transition a chapter may be offered right now (015/008).
 *
 * The chapter state machine admits exactly one transition per state — `planned` →
 * open, `open` → close, `closed` → reopen, `closing` → none — so the page renders
 * ONE control, never three with two disabled: a disabled control invites the
 * question "why", an absent one with the state shown beside it does not.
 *
 * Gated on the chapter's STATE alone and offered to every member (D14): the page
 * has no caller-role signal, a co-author's attempt is refused `403` by the server,
 * and that refusal text is what the author reads. No caller-relative field is added
 * to any DTO and the chapter LIST (with 014's `can_reorder` hint) is never fetched
 * here.
 */
export type ChapterTransition = "open" | "close" | "reopen";

/**
 * Page state for `ChapterPage`, held via
 * `useState(() => new ChapterPageState(bookId, chapterId))`.
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
 *   every lifecycle state, `closed` included (DoD-10);
 * - **the state transition** (015/008) — a status and a server-error holder of its
 *   own, plus the two computeds that answer *which single transition is offered*
 *   and *why none is*. Separate from the body's and the sketch's holders, so a
 *   refused transition never touches either editor's draft.
 *
 * Both ids arrive as arguments on **every external effect** — 014's deliberate
 * departure from `codexEntryPageState.ts`, kept intact: the body's buffer key is built
 * inside each effect from the `(bookId, chapterId)` pair it already carries, and there
 * is no `bufferKey` computed on this class. Since 015 step 012 the constructor ALSO
 * stores the pair, for the two bound members the module tier holds
 * ({@link ChapterPageState.subjectSource} / {@link ChapterPageState.applyDraft}), which
 * `work/contentSubject.ts` calls with a fixed argument list carrying no ids.
 */
export class ChapterPageState {
  /**
   * THE BOOK AND CHAPTER IDS this instance is about (015/012) — plain, NON-observable
   * fields, assigned once in the constructor and never written again. `codexEntryPageState.ts`
   * is the template (it stores `bookId` / `entryId` and excludes `bookId` from
   * `makeAutoObservable`); a `key={id}` on `ChapterItemRoute` already forces a FRESH
   * instance whenever the route's chapter changes, so they cannot go stale.
   *
   * **Why they exist at all, given that every external effect already takes the pair as
   * arguments** (014's deliberate departure, kept intact below): the two members the
   * MODULE TIER holds — {@link ChapterPageState.subjectSource} and
   * {@link ChapterPageState.applyDraft} — are handed across the module boundary and are
   * then called by `work/contentSubject.ts` with a FIXED argument list that carries no
   * ids at all. A bound callback can only reach the pair through `this`.
   *
   * The external effects are NOT re-shaped to read them: `loadChapter`, `saveSketch`,
   * `loadChapterBody`, `editBodyDraft`, `saveChapterBody`, `resolveBodyConflict` and the
   * three transitions keep the frozen `(state, bookId, chapterId, …)` signatures steps
   * 006 / 007 / 008 shipped, and the page keeps passing the pair to them.
   */
  readonly bookId: string;
  readonly chapterId: string;

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

  /**
   * In-flight state of the ONE offered lifecycle transition (015/008) — open,
   * close or reopen. Its OWN status, separate from `chapterStatus`,
   * `sketchSubmitStatus`, `bodyStatus` and `bodySubmitStatus`: a transition is a
   * command against the chapter row, not a save of either editor's draft, and it
   * must never make an editor look like it is loading or saving.
   */
  transitionStatus: "idle" | "loading" | "ready" | "error" = "idle";

  /**
   * The SERVER's refusal message for the most recent transition attempt, held on
   * its own so it can never be mistaken for a body or sketch refusal — and, more
   * importantly, so that surfacing it costs nothing anywhere else: **a refused
   * transition never clears the body draft, the restore buffer, the sketch draft or
   * the prompt draft** (015/008 DoD-8).
   *
   * `null` when there is nothing to say. A single string, not a
   * `Record<string, string>`: a transition is a bodiless `POST` with no fields, so
   * there is no field to key a refusal by (the `…ServerErrors` shape exists for
   * forms; this is a command).
   *
   * The text is `err.message`. `routes/chapters.py:_map_chapter_error` puts the
   * chapter family's refusal on the wire as a **plain-string `detail`**, which
   * `client.ts:throwApiError` already prefers, so `CodexEntryPage`'s
   * `serverRefusalText` / `details.detail.message` object path is the CODEX
   * family's and must NOT be copied here (steps 003 / 004 / 006 / 007 freeze notes).
   *
   * This is where D14's accepted cost is paid: a co-author sees a control that the
   * server will refuse `403`, and THIS is what makes that refusal legible rather
   * than mysterious. The same holder carries the archived-book `403` (D10) and the
   * `409` another chapter already holds the open slot.
   */
  transitionError: string | null = null;

  /**
   * THE AUTHOR'S CURRENT SELECTION in the body editor (015/012; D5) — the selected
   * TEXT, or `null` when nothing is selected. Written by exactly one function,
   * {@link setChapterSelection}, from the editor's `onSelectionChange` callback, which
   * reports `""` for an empty selection; **that `""` is stored here as `null`**, so a
   * single `=== null` test answers "is there a selection" everywhere.
   *
   * **CLIENT-SIDE ONLY, and never persisted (D5).** It is not written to the restore
   * buffer, never reaches `localStorage`, never joins a save payload, and
   * `ChapterChange.line_from` / `line_to` never express it — no character-offset-to-line
   * snapping, ever. It rides on a turn request as text and nothing else, and the chat
   * pane reads it from the module-level registry at SEND time rather than from here.
   *
   * Held on the state as well as in the registry because
   * {@link ChapterPageState.applyDraft} needs it to resolve a `replace_selection`
   * frame against the draft it is holding.
   */
  selectedText: string | null = null;

  /**
   * THE ONE ASSISTANT WRITE THAT WAS NOT APPLIED (015/012) — the text a
   * `replace_selection` frame carried when there was **no active selection** to replace,
   * held so the page can tell the author that the assistant wrote something and it did
   * not land. `null` when there is nothing to report.
   *
   * A refused frame changes **nothing else**: the draft, the restore buffer, the base
   * version, the editor generation and the undo stack are all left exactly as they are.
   * There is **no fallback to append and no write at position zero** — writing at a
   * location nobody chose is the silent wrong placement `domain-chapter.md` refuses, and
   * a refusal is loud. The check lives HERE and not in the tool because at tool-call time
   * the selection may have existed and the author may have cleared it while the model was
   * writing; the server cannot know that.
   *
   * Cleared by the next frame that DOES apply, so it always describes the most recent
   * assistant write rather than accumulating.
   */
  unappliedSelectionWrite: string | null = null;

  constructor(bookId: string, chapterId: string) {
    this.bookId = bookId;
    this.chapterId = chapterId;
    // The two ids and the two bound members handed to the module tier are excluded:
    // the ids never change, and MobX would otherwise try to make a bound method
    // observable — `codexEntryPageState.ts`'s `{ bookId: false, …, applyDraft: false }`
    // verbatim, one page down.
    makeAutoObservable(this, {
      bookId: false,
      chapterId: false,
      subjectSource: false,
      applyDraft: false,
    });
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

  /**
   * WHICH SINGLE TRANSITION IS OFFERED (015/008), derived from **the loaded
   * CHAPTER's state alone** (D14) — `this.chapter?.state`, never `body.state` and
   * never a caller-role signal, because the control is rendered beside the chapter's
   * own state badge and the two must never disagree.
   *
   * The state machine admits exactly one transition per state:
   *
   * | loaded state | offered |
   * |---|---|
   * | `planned` | `"open"` (UC-035 / US-036.AC-1) |
   * | `open` | `"close"` (UC-036 / US-038.AC-1) |
   * | `closed` | `"reopen"` (UC-037 / US-039.AC-1) |
   * | `closing` | **`null`** — see {@link ChapterPageState.transitionUnavailableReason} |
   *
   * `null` before the first successful chapter load and on a failed one, too: there
   * is no state to derive an offer from, and the chapter section is showing its own
   * loading / error branch there.
   *
   * **Exactly ONE control is ever rendered — never three with two disabled.** A
   * disabled control invites the question "why"; an absent one, with the state shown
   * beside it, does not.
   *
   * A client AFFORDANCE that never substitutes for the server's answer: the control
   * is offered to EVERY member (D14 — no caller-role signal exists on this page, and
   * none is manufactured), a non-owner's attempt is refused `403`, and the message
   * lands in {@link ChapterPageState.transitionError}. Pure — no side effects, no I/O.
   */
  get offeredTransition(): ChapterTransition | null {
    switch (this.chapter?.state) {
      case "planned":
        return "open";
      case "open":
        return "close";
      case "closed":
        return "reopen";
      default:
        // `closing` — nothing in this feature can change it (D8) — and the
        // not-yet-loaded / failed-load case, where there is no state to derive an
        // offer from at all.
        return null;
    }
  }

  /**
   * Why NO transition is offered, as author-facing READABLE TEXT (015/008 DoD-4) —
   * non-`null` **exactly** when the chapter has loaded and
   * {@link ChapterPageState.offeredTransition} is `null`, which the state machine
   * makes exactly the `closing` case.
   *
   * `closing` is the ONE state that gets a stated reason rather than silence,
   * because it is a state the author cannot currently produce (D8 — nothing in this
   * feature writes it) and will not recognise; every other state either offers its
   * one control or has not loaded yet. The sentence must name **the close gate as
   * not yet built** (`016.chapter-close-continuity`'s), not merely restate the state.
   *
   * `null` for `planned` / `open` / `closed` (a control IS offered there, so there is
   * nothing to explain) and `null` before the first successful chapter load.
   *
   * This page's OWN sentence, deliberately: `work/subject.ts`'s `closing` reason is
   * about the BODY being read-only while continuity is reviewed, which is a different
   * claim and promises a review flow that does not exist yet. The precedent for a
   * page-owned sentence is {@link ChapterPageState.sketchDisabledReason}'s `open`
   * case. Pure.
   */
  get transitionUnavailableReason(): string | null {
    // Nothing has loaded: the chapter section is showing its own loading or error
    // branch, and there is no state to explain.
    if (this.chapter === null) return null;
    // A control IS offered, so there is nothing to explain either.
    if (this.offeredTransition !== null) return null;
    // The one remaining case the state machine admits: `closing`. The sentence names
    // the close gate as NOT YET BUILT rather than merely restating the state.
    return "This chapter is closing. The close approval step is not built yet, so its state cannot be changed here.";
  }

  /**
   * WHAT THIS PAGE DECLARES ITSELF TO BE to the content-pane registry (015/012) — the
   * `ContentSubjectSource` the page registers, unregisters and stamps its selection with.
   *
   * It must return the subject **as it is right now**, so it reads `this.chapter?.state`
   * at CALL time: the chapter's lifecycle state is only known once the load resolves, and
   * the chat pane calls this while composing a turn. `entityId` is the ROUTE's chapter id
   * ({@link ChapterPageState.chapterId}), not `chapter?.id`, so a turn sent before the
   * load resolves still names the right chapter.
   *
   * **It is also the identity token**, and that is why it moved out of `ChapterPage.tsx`'s
   * mount effect and onto the instance: `registerContentSubject`,
   * `unregisterContentSubject`, `setContentSelection` and `clearContentSelection` are ALL
   * guarded on the same reference, and the selection is pushed from the editor's callback
   * during RENDER, where the effect's local closure is not in scope. A bound property on
   * a per-route instance gives every one of those call sites the same stable token with no
   * `useCallback` (banned) and no second registry.
   *
   * A bound arrow property, excluded from `makeAutoObservable`'s annotations — the
   * `codexEntryPageState.ts:applyDraft` precedent, for the same reason: the module tier
   * holds the function itself across the module boundary.
   *
   * Contract (the object 014 already built inline, unchanged):
   * `{ kind: "chapter", entityId: this.chapterId, chapterState: this.chapter?.state }`.
   */
  readonly subjectSource: ContentSubjectSource = () => ({
    kind: "chapter",
    // The ROUTE's chapter id, never `chapter?.id`: a turn sent before the load
    // resolves still names the right chapter.
    entityId: this.chapterId,
    // Read at CALL time, so the pane model's editability answer follows the load.
    chapterState: this.chapter?.state,
  });

  /**
   * APPLY ONE ASSISTANT `canvas` FRAME to the body draft (015/012) — the callback this
   * page registers alongside its subject, making the open chapter a **writable** canvas
   * target where 014 registered it as a subject only.
   *
   * A bound arrow property, excluded from `makeAutoObservable`'s annotations, exactly as
   * `codexEntryPageState.ts:applyDraft` is: MobX would otherwise try to make a bound
   * method observable, and `work/contentSubject.ts` holds the function itself across the
   * module boundary. It takes the frame's `field`, its `text` and its `op` and nothing
   * else — the dispatcher passes no ids, which is why
   * {@link ChapterPageState.bookId} / {@link ChapterPageState.chapterId} live on the
   * instance.
   *
   * `op` is optional only because {@link CanvasDraftApplier} declares it so (a
   * two-parameter codex applier must stay assignable). `dispatchCanvasFrame` ALWAYS
   * passes a real `CanvasOp`, having resolved an omitted `frame.op` to `"replace"`, so an
   * absent `op` means `"replace"` here too.
   *
   * **A `"name"` frame is ignored.** `CanvasField` is `"name" | "body"` and a chapter has
   * no name on the canvas: its body IS the `"body"` field (D17). Nothing is changed and
   * nothing is reported.
   *
   * **THE REFUSAL, FIRST — a `"replace_selection"` frame with no active selection is NOT
   * APPLIED.** {@link ChapterPageState.selectedText} is `null`, or it is a string the
   * draft no longer contains: record the frame's text in
   * {@link ChapterPageState.unappliedSelectionWrite} and **return, having changed nothing
   * — no undo push, no draft write, no buffer write, no generation bump.** There is **no
   * fallback to append, ever**, and the text is **never applied at position zero**. This
   * check is page-level, not tool-level, on purpose: at tool-call time the selection may
   * have existed and the author may have cleared it while the model was writing.
   *
   * **THE APPLY ORDER IS NOT ARBITRARY. Four steps, in this order:**
   *
   * 1. **SNAPSHOT FIRST** — `pushChapterUndoSnapshot(this.bookId, this.chapterId,
   *    this.bodyDraft)`, the draft **as it is about to be overwritten**, BEFORE anything
   *    is applied. Applying first would store the post-write text and make undo a no-op.
   * 2. **APPLY THE OPERATION** to {@link ChapterPageState.bodyDraft}: `"replace"` → the
   *    frame's text becomes the whole draft; `"append"` → the text goes at the END of the
   *    current draft; `"replace_selection"` → the text replaces the FIRST occurrence of
   *    {@link ChapterPageState.selectedText} within the draft.
   * 3. **ROUTE THE RESULT THROUGH THE SINGLE DRAFT-EDIT PATH** — `editBodyDraft(this,
   *    this.bookId, this.chapterId, next)` — so the restore buffer is written exactly as a
   *    keystroke writes it, and an eviction is surfaced exactly as a keystroke's is.
   *    Bypassing it would lose the assistant's draft on a reload — precisely the "writer
   *    with no base version" `frontend-work-drafts.md` expects to land in the buffer.
   * 4. **BUMP {@link ChapterPageState.bodyEditorGeneration}** so TipTap remounts on the
   *    NEW draft (D15). Bumping before applying would remount the editor on the old one.
   *
   * Then clear {@link ChapterPageState.unappliedSelectionWrite}: a frame that landed
   * supersedes the report of one that did not.
   *
   * **NOTHING REACHES THE SERVER** — an assistant write is a draft edit and nothing else
   * (D4). The author saves.
   */
  readonly applyDraft = (field: CanvasField, text: string, op?: CanvasOp): void => {
    // A `"name"` frame is IGNORED: `CanvasField` is `"name" | "body"` and a chapter
    // has no name on the canvas — its body IS the `"body"` field (D17). Nothing is
    // changed and nothing is reported.
    if (field !== "body") return;

    // `dispatchCanvasFrame` always passes a real operation, having resolved an
    // omitted `frame.op` to `"replace"` first; the fallback here exists only because
    // `CanvasDraftApplier` declares the parameter optional.
    const operation: CanvasOp = op ?? "replace";

    // The draft AS IT IS ABOUT TO BE OVERWRITTEN — read once, so the snapshot, the
    // operation and the result all see the same text.
    const draft = this.bodyDraft;
    const selected = this.selectedText;

    // THE REFUSAL COMES FIRST, before the snapshot and before anything is written: a
    // `"replace_selection"` frame with no active selection — or one whose selection
    // the draft no longer contains — is NOT APPLIED. There is no fallback to append,
    // ever, and the text is never applied at position zero. The check lives here and
    // not in the tool because the author may have cleared the selection while the
    // model was writing, which the server cannot know.
    let selectionAt = -1;
    if (operation === "replace_selection") {
      selectionAt = selected === null ? -1 : draft.indexOf(selected);
      if (selectionAt === -1) {
        runInAction(() => {
          // Reported, and NOTHING else changes: no undo push, no draft write, no
          // buffer write, no generation bump.
          this.unappliedSelectionWrite = text;
        });
        return;
      }
    }

    // 1. SNAPSHOT FIRST — the pre-write draft, BEFORE anything is applied. Applying
    //    first would store the post-write text and make undo a no-op.
    pushChapterUndoSnapshot(this.bookId, this.chapterId, draft);

    // 2. APPLY THE OPERATION to the draft: the whole draft, the end of it, or the
    //    FIRST occurrence of the current selection within it.
    let next: string;
    if (operation === "append") {
      next = draft + text;
    } else if (operation === "replace_selection") {
      next =
        draft.slice(0, selectionAt) + text + draft.slice(selectionAt + (selected?.length ?? 0));
    } else {
      next = text;
    }

    // 3. ROUTE THE RESULT THROUGH THE SINGLE DRAFT-EDIT PATH, so the restore buffer
    //    is written exactly as a keystroke writes it and an eviction surfaces exactly
    //    as a keystroke's does. Bypassing it would lose the assistant's draft on a
    //    reload.
    editBodyDraft(this, this.bookId, this.chapterId, next);

    runInAction(() => {
      // 4. BUMP THE GENERATION so TipTap remounts on the NEW draft (D15). Bumping
      //    before applying would remount the editor on the old one.
      this.bodyEditorGeneration += 1;
      // A frame that landed supersedes the report of one that did not.
      this.unappliedSelectionWrite = null;
    });
  };
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

// ---------------------------------------------------------------------------
// THE THREE LIFECYCLE TRANSITIONS (`015.chapter-writing-free-mode` step 008)
//
// One external effect per transition, all three with the module's
// `(state, bookId, chapterId, signal?)` shape and all three sharing ONE contract,
// which differs only in the api function called:
//
//   1. `transitionStatus = "loading"`, `transitionError = null`;
//   2. await the api call — `openChapterState` / `closeChapterState` /
//      `reopenChapterState` — which resolves to 014's `ChapterResponse`;
//   3. return silently when `signal?.aborted`;
//   4. ON SUCCESS, RE-SEED THE CHAPTER TRIO **AND** THE BODY TRIO FROM THE SERVER
//      (see below), then `transitionStatus = "ready"`;
//   5. on `ApiError`, `transitionError = err.message` (falling back to
//      `"Could not change the chapter state."` on an empty message) and
//      `transitionStatus = "error"` — AND NOTHING ELSE CHANGES ANYWHERE. Anything
//      that is not an `ApiError` rethrows, as everywhere else in this module.
//
// THE RE-SEED, and why it is not a local patch. A successful transition changes the
// chapter's `state`, and four things follow from it: `resolveEditability`'s verdict
// for the body, whether the editor is mounted at all (D16), which transition control
// is offered next, and 014's sketch editor's enablement. Re-seeding is what makes all
// four follow AT ONCE, with no navigation and no manual reload (DoD-7):
//
// - the CHAPTER trio takes the transition's OWN `ChapterResponse` whole
//   (`state.chapter = response`) — the server's representation, exactly as
//   `saveSketch` adopts its PATCH response. **Never patch `state.chapter.state`
//   locally**: the backend is the source of truth, and a locally patched state would
//   leave the BODY response's own `state` field disagreeing with it;
// - the BODY trio is re-read from the server (`chaptersApi.getChapterText`) and
//   `state.body` / `state.bodyStatus` are set from THAT response, so `canEditBody`
//   (which reads `body.state`) follows the new state too.
//
// WHAT THE RE-SEED MUST **NOT** TOUCH — DoD-8, and the reason the body trio is
// re-read by hand here instead of through `loadChapterBody`:
//
// - **`bodyDraft`** — a successful transition must no more destroy unsaved work than
//   a refused one. The draft is left exactly as it is;
// - **the restore buffer** — not written, not cleared. Steps 006's and 007's rules
//   own it;
// - **`bodyBaseVersion`** — a transition touches `state` and `modified_at` only and
//   never bumps `Chapter.version` (step 002's freeze), so there is nothing to move;
// - **`bodyEditorGeneration`** — nothing wrote the draft from outside the editor, so
//   there is nothing for TipTap to be remounted to see;
// - **`bodyConflict` / `isReconcilingBody` / `evictedBufferKeys`**, and the sketch and
//   prompt drafts and their `…ServerErrors` holders.
//
// `loadChapterBody` would break every one of those: it re-seeds the draft, bumps the
// generation counter and re-runs the load-time buffer entrance, which could open the
// divergence view for a body nobody re-read. **Do not call it from here.**
//
// If the body re-read itself fails with an `ApiError`, that is a BODY load failure and
// it lands in the body trio's own surface (`bodyError` / `bodyStatus = "error"`) — the
// page already has one. The transition itself succeeded, so `transitionStatus` is
// still `"ready"` and `transitionError` stays `null`.
//
// NO CONFIRMATION DIALOG anywhere: closing is reversible by reopening, and the
// approval gate is `016`'s (D8).
// ---------------------------------------------------------------------------

/**
 * THE ONE SHARED CONTRACT the three transitions run — module-private, not exported,
 * and not a fourth effect: the three differ ONLY in which api call they issue, so the
 * call arrives as a thunk and everything else is written once. The thunk defers the
 * `chaptersApi` lookup to call time, so the namespace is read exactly where the three
 * exported effects would read it.
 *
 * Steps 1–5 of the block comment above, in order.
 */
async function runChapterTransition(
  state: ChapterPageState,
  bookId: string,
  chapterId: string,
  transition: () => Promise<ChapterResponse>,
  signal?: AbortSignal,
): Promise<void> {
  runInAction(() => {
    state.transitionStatus = "loading";
    state.transitionError = null;
  });

  let chapter: ChapterResponse;
  try {
    chapter = await transition();
    if (signal?.aborted) return;
  } catch (err) {
    if (signal?.aborted) return;
    if (!(err instanceof ApiError)) throw err;
    runInAction(() => {
      // A co-author's `403` (D14), an archived book's `403` (D10) and the `409`
      // another chapter already holds the slot (CF1) all land here, as the SERVER's
      // own plain-string message — never the codex family's `details.detail.message`
      // object path. AND NOTHING ELSE CHANGES ANYWHERE: not the chapter, not the body,
      // not the body draft, not the restore buffer, not either other editor.
      state.transitionError = err.message || "Could not change the chapter state.";
      state.transitionStatus = "error";
    });
    return;
  }

  runInAction(() => {
    // The CHAPTER trio takes the transition's own response WHOLE, exactly as
    // `saveSketch` adopts its PATCH response. Never a local patch of
    // `state.chapter.state`: the backend is the source of truth, and a patched state
    // would leave the BODY response's own `state` field disagreeing with it.
    state.chapter = chapter;
  });

  // THE BODY TRIO IS RE-READ BY HAND — deliberately NOT through `loadChapterBody`,
  // which would re-seed the draft, bump the editor generation and re-run the load-time
  // buffer entrance (DoD-8). Only `body` and `bodyStatus` move, so `canEditBody`
  // (which reads `body.state`) follows the new state with no navigation and no manual
  // reload, while the draft, the buffer, `bodyBaseVersion`, the generation counter and
  // the reconciliation fields are all left exactly as they are.
  try {
    const body = await chaptersApi.getChapterText(bookId, chapterId, signal);
    if (signal?.aborted) return;
    runInAction(() => {
      state.body = body;
      state.bodyStatus = "ready";
      state.transitionStatus = "ready";
    });
  } catch (err) {
    if (signal?.aborted) return;
    if (!(err instanceof ApiError)) throw err;
    runInAction(() => {
      // A failed re-read is a BODY load failure and lands in the body trio's own
      // surface. The TRANSITION itself succeeded, so its status is still `"ready"` and
      // `transitionError` stays `null`.
      state.bodyError = err.message;
      state.bodyStatus = "error";
      state.transitionStatus = "ready";
    });
  }
}

/**
 * OPEN the chapter — the only transition a `planned` chapter is offered (UC-035 /
 * US-036.AC-1). Calls `chaptersApi.openChapterState(bookId, chapterId, signal)`.
 *
 * The full contract is the block comment above: re-seed the chapter trio from the
 * response and the body trio from a fresh `getChapterText` on success, so the body
 * editor is mounted without a navigation; on `ApiError` store the server's message in
 * {@link ChapterPageState.transitionError} and change nothing — a co-author's `403`
 * (D14), an archived book's `403` (D10) and the `409` another chapter already holds
 * the open slot (CF1 / US-037.AC-2) all arrive here and all leave the chapter's state
 * on screen, the body region and the body DRAFT exactly as they were.
 */
export async function openChapterState(
  state: ChapterPageState,
  bookId: string,
  chapterId: string,
  signal?: AbortSignal,
): Promise<void> {
  await runChapterTransition(
    state,
    bookId,
    chapterId,
    () => chaptersApi.openChapterState(bookId, chapterId, signal),
    signal,
  );
}

/**
 * CLOSE the chapter — the only transition an `open` chapter is offered (US-038.AC-1).
 * Calls `chaptersApi.closeChapterState(bookId, chapterId, signal)`, which the server
 * answers by writing **`closed`** directly: nothing in this feature produces or drafts
 * a `closing` chapter (D8), and there is **no confirmation dialog** — a close is
 * reversible by a reopen, and the approval gate is `016`'s.
 *
 * Same contract as {@link openChapterState}: re-seed both trios on success, so the
 * body region becomes read-only and its save control disappears without a navigation;
 * on `ApiError` surface the message and change nothing (US-038.AC-2).
 */
export async function closeChapterState(
  state: ChapterPageState,
  bookId: string,
  chapterId: string,
  signal?: AbortSignal,
): Promise<void> {
  await runChapterTransition(
    state,
    bookId,
    chapterId,
    () => chaptersApi.closeChapterState(bookId, chapterId, signal),
    signal,
  );
}

/**
 * REOPEN the chapter — the only transition a `closed` chapter is offered (UC-037 /
 * US-039.AC-1). Calls `chaptersApi.reopenChapterState(bookId, chapterId, signal)`.
 *
 * Same contract as {@link openChapterState}: re-seed both trios on success, so the
 * editor mounts again; on `ApiError` surface the message and change nothing — the
 * `409` another chapter is `open` or `closing` (US-039.AC-2) reads exactly like every
 * other refusal.
 */
export async function reopenChapterState(
  state: ChapterPageState,
  bookId: string,
  chapterId: string,
  signal?: AbortSignal,
): Promise<void> {
  await runChapterTransition(
    state,
    bookId,
    chapterId,
    () => chaptersApi.reopenChapterState(bookId, chapterId, signal),
    signal,
  );
}

// ---------------------------------------------------------------------------
// THE CANVAS WIRING (`015.chapter-writing-free-mode` step 012)
//
// Two external effects beside the two bound members on the class above. Both are
// SYNCHRONOUS and SERVER-FREE — an assistant write and an undo are draft edits and
// nothing else (D4 / DoD-4 / DoD-10) — so neither takes a `signal` and neither
// returns a `Promise`.
// ---------------------------------------------------------------------------

/**
 * Record the author's current selection and PUSH IT INTO THE MODULE-LEVEL SELECTION
 * REGISTRY (015/012; D5) — the single path the editor's `onSelectionChange` callback
 * takes.
 *
 * `selectedText` is the editor's own value verbatim: `ChapterBodyEditor` reports the
 * selected plain text and **`""` for an empty selection**, and `""` is stored as
 * `null` on {@link ChapterPageState.selectedText} and pushed to the registry as
 * `null`, so "nothing is selected" has ONE representation everywhere.
 *
 * Contract:
 *
 * - `runInAction`: `state.selectedText = selectedText === "" ? null : selectedText`;
 * - `setContentSelection(state.subjectSource, state.selectedText)` — stamped with
 *   {@link ChapterPageState.subjectSource}, the SAME token the page registers and
 *   unregisters its subject with, so `unregisterContentSubject` on unmount clears the
 *   selection too (its shipped one-line `clearContentSelection(source)`) and a
 *   superseded page's trailing selection event is a no-op (DoD-8).
 *
 * **NEVER PERSISTED AND NEVER SAVED**: no restore-buffer write, no `localStorage`, no
 * HTTP, no `expected_version` interaction. The turn request carries the selection as
 * text and only text, read from the registry at send time.
 *
 * Takes NO ids, deliberately, unlike every other effect in this module: a selection is
 * keyed by nothing, buffered under nothing and stored nowhere that needs a key, and the
 * registry's identity token is `state.subjectSource`.
 */
export function setChapterSelection(state: ChapterPageState, selectedText: string): void {
  runInAction(() => {
    // `""` — the editor's report of an empty selection — is stored as `null`, so
    // "nothing is selected" has ONE representation everywhere.
    state.selectedText = selectedText === "" ? null : selectedText;
  });
  // Stamped with the SAME token the page registers and unregisters its subject
  // with, so the unmount's `clearContentSelection(source)` lands and a superseded
  // page's trailing selection event is a no-op (DoD-8).
  setContentSelection(state.subjectSource, state.selectedText);
}

/**
 * UNDO THE ASSISTANT'S LAST WRITE to this chapter's body (015/012; D6) — pop the most
 * recent snapshot for `(bookId, chapterId)` and put it back in the draft.
 *
 * Contract, and the mirror image of {@link ChapterPageState.applyDraft}'s four steps:
 *
 * 1. `popChapterUndoSnapshot(bookId, chapterId)`; `null` means the stack is empty —
 *    **return, changing nothing**;
 * 2. set the popped text as the body draft **through the same single draft-edit path**,
 *    `editBodyDraft(state, bookId, chapterId, snapshot)`, so the restore buffer is
 *    written exactly as a keystroke would write it;
 * 3. bump {@link ChapterPageState.bodyEditorGeneration}, so TipTap remounts on the
 *    restored draft (D15).
 *
 * **IT PUSHES NOTHING.** An undo is not an assistant write, and re-snapshotting here
 * would make the stack un-walkable: repeated undos step back through the twenty most
 * recent states, oldest-dropped-first (DoD-3 / DoD-7).
 *
 * Nothing reaches the server, and the stack is NOT cleared by a save — an author may
 * want to undo an assistant write after saving, and the restored draft then re-saves as
 * an ordinary save against the current version.
 *
 * Carries the `(state, bookId, chapterId)` shape every other effect in this module
 * carries, so the page passes the pair here exactly as it does everywhere else; the
 * instance's own copies exist for the module-tier CALLBACKS, which are handed no
 * arguments at all.
 */
export function undoAssistantBodyWrite(
  state: ChapterPageState,
  bookId: string,
  chapterId: string,
): void {
  const snapshot = popChapterUndoSnapshot(bookId, chapterId);
  // An empty stack means there is nothing to undo: return, changing nothing. A
  // popped `""` is a legitimate snapshot and is restored like any other.
  if (snapshot === null) return;

  // THE SAME single draft-edit path an assistant write and a keystroke take, so the
  // restore buffer is written exactly as a keystroke would write it. IT PUSHES
  // NOTHING — re-snapshotting would make the stack un-walkable.
  editBodyDraft(state, bookId, chapterId, snapshot);

  runInAction(() => {
    // The draft was written from OUTSIDE the editor, so TipTap remounts on the
    // restored text (D15).
    state.bodyEditorGeneration += 1;
  });
}
