import { makeAutoObservable, runInAction } from "mobx";
import * as chaptersApi from "../../api/chapters";
import { ApiError } from "../../api/client";
import type {
  ChapterListResponse,
  ChapterResponse,
  CreateChapterRequest,
} from "../../types/chapters";

// Page state for `ChaptersPage` — the working page's chapter list
// (`/work/:bookId/chapters`; FEAT-008 · UC-031 / UC-034 · US-032 / US-035).
//
// Follows `bookStatePageState.ts`'s grain exactly: observable data + pure `get`
// computeds on the class, every effectful operation an external
// `(state, bookId, …, signal?)` function using `runInAction`, and every loadable an
// async trio (`x` / `xStatus` / `xError`).
//
// The five `get` computeds and the three external effect functions of step 006 are
// FROZEN SIGNATURES (skeleton 014/006) and are implemented; nothing of step 006's is a
// stub.
//
// STEP 007 HAS NOW ADDED ITS REORDER SURFACE ALONGSIDE (skeleton 014/007): the reorder
// state (`reorderStatus` / `reorderError` / `pendingOrder`), the
// `canMoveUp` / `canMoveDown` computeds, and the `moveChapter` / `applyChapterOrder`
// effects. **Step 007 is ADDITIONS ONLY**: the list trio, the add-form state, the
// remove state, all five step-006 computeds and all three step-006 effects are
// untouched.

/** The author-facing message for a blank / whitespace-only chapter title. */
const BLANK_TITLE_MESSAGE = "Give the chapter a title.";

/**
 * Which way a single-position move goes — the ↑ and ↓ controls' only difference.
 *
 * There is NO per-chapter move endpoint (`context.md` → D3): a move computes the new
 * FULL ordered id sequence locally and persists it through the one bulk
 * `PUT …/chapters/order`, exactly as a drag does.
 */
export type ChapterMoveDirection = "up" | "down";

/**
 * Page state for `ChaptersPage`, held via `useState(() => new ChaptersPageState())`.
 *
 * Holds:
 *
 * - **the chapter-list trio** — the WHOLE `ChapterListResponse` envelope, never a bare
 *   array. `can_reorder` rides on the envelope and step 007 reads it off
 *   {@link ChaptersPageState.canReorder} without a second load;
 * - **the add-form state** — a title draft, a sketch draft, a `…ServerErrors` map and a
 *   submit status. This is the ONE form in feature 014 with a client-validation layer
 *   (the title must not be blank), so it carries {@link ChaptersPageState.addClientErrors}
 *   alongside `addServerErrors` and combines the two in
 *   {@link ChaptersPageState.canSubmitAdd}. The sketch has NO client rule — an empty
 *   sketch is a legitimate starting state;
 * - **the remove state** — which chapter id is currently being removed, and a per-chapter
 *   map of the server's refusal messages so a refusal renders BESIDE the chapter it
 *   concerns rather than as a page-level banner.
 *
 * Per the MobX hard rules the class has NO effectful methods and NO setters: loading,
 * adding and removing all live in the external functions below.
 */
export class ChaptersPageState {
  /**
   * The WHOLE chapter list envelope as returned by `GET /api/books/{id}/chapters` —
   * `{ chapters, can_reorder }`, not a bare array (`context.md` → cross-cutting frontend
   * constraints; step 005's `listChapters` deliberately does not unwrap it). `null`
   * until the first successful load; an EMPTY `chapters` array is a normal loaded value
   * and never an error.
   */
  chapterList: ChapterListResponse | null = null;
  chapterListStatus: "idle" | "loading" | "ready" | "error" = "idle";
  chapterListError: string | null = null;

  /** The add form's title draft. Bound to the title field; cleared on a successful add ONLY. */
  addTitleDraft = "";

  /** The add form's sketch draft. Bound to the multi-line sketch field; cleared on a successful add ONLY. */
  addSketchDraft = "";

  /**
   * Server refusals for the ADD submit only, held separately from the list trio's
   * `chapterListError` and from `removeServerErrors`. Keyed by field name (`title` /
   * `sketch`) plus the general `form` key for non-field refusals — the `021`
   * `…ServerErrors` shape. A refusal here leaves BOTH drafts intact.
   */
  addServerErrors: Record<string, string> = {};

  /** In-flight state of the add submit (the load has its own `chapterListStatus`). */
  addSubmitStatus: "idle" | "loading" | "ready" | "error" = "idle";

  /**
   * The id of the chapter whose removal is currently in flight, or `null` when no
   * removal is running. Doubles as the per-row "removing…" indicator; there is
   * deliberately no separate remove submit status, because at most one removal runs at
   * a time and the id already says which row it belongs to.
   */
  removingChapterId: string | null = null;

  /**
   * The server's removal refusals, **keyed by chapter id** (not by field name — this is
   * the one `…ServerErrors` map in the feature that is keyed by row). The keying is the
   * point: a page-level banner would leave the author guessing which chapter a refusal
   * concerned in a long list (`006.context.md`). An entry is cleared when that chapter's
   * removal is retried and on a successful removal.
   */
  removeServerErrors: Record<string, string> = {};

  /**
   * In-flight state of a REORDER submit — its own status, held apart from
   * `chapterListStatus`, `addSubmitStatus` and `removingChapterId` so a reorder can be
   * refused without disturbing the load, the add form or a per-chapter removal (DoD-8).
   *
   * FROZEN (skeleton 014/007).
   */
  reorderStatus: "idle" | "loading" | "ready" | "error" = "idle";

  /**
   * The server's refusal of a reorder — the `403` a co-author earns when the
   * `can_reorder` hint went stale, above all — or `null` when there is none.
   *
   * A THIRD, independent error surface beside `chapterListError` (the load),
   * `addServerErrors` (the add form) and `removeServerErrors` (per chapter). The three
   * never share a holder: DoD-8 asserts a reorder failure leaves the add drafts and the
   * per-chapter removal messages alone. Rendered by `ChaptersPage` as a list-level
   * message, because a reorder concerns the whole list rather than one row.
   *
   * FROZEN (skeleton 014/007).
   */
  reorderError: string | null = null;

  /**
   * The chapter-id sequence currently being arranged — what `ChapterOrderList` renders
   * WHILE a reorder is in flight — or `null` whenever no reorder is running.
   *
   * This is a RENDERING optimism, never a state optimism (`007.context.md`): nothing in
   * the list trio is mutated until the server answers, and this array is **discarded and
   * the list re-seeded from the server on BOTH success AND failure**. A refused `PUT`
   * must snap the rendered order back to the order the server still holds (DoD-5,
   * US-033.AC-2) — keeping the attempted order would leave the author looking at an
   * order the server does not have, with no way to tell.
   *
   * Non-`null` exactly while `reorderStatus === "loading"`. Holds ids, not chapters, so
   * it cannot drift from the envelope's chapter rows.
   *
   * FROZEN (skeleton 014/007).
   */
  pendingOrder: string[] | null = null;

  constructor() {
    makeAutoObservable(this);
  }

  /**
   * The chapters to render, in **ordinal-ascending** order — a SORTED COPY, never a
   * mutation of the observable envelope. `[]` before the first successful load and on
   * an error, so the view never binds to stale data.
   *
   * Ordinal order is what the page promises (DoD-1) and it must not depend on the order
   * the envelope happened to arrive in.
   */
  get orderedChapters(): ChapterResponse[] {
    if (this.chapterList === null || this.chapterListStatus === "error") return [];
    return [...this.chapterList.chapters].sort((a, b) => a.ordinal - b.ordinal);
  }

  /**
   * Whether the caller may reorder this book's chapters — read straight off the loaded
   * envelope's `can_reorder`, `false` until it has loaded.
   *
   * **Step 007 is what consumes this.** Nothing in step 006 renders off it; it lives
   * here so the reorder step needs no second load. It is an affordance HINT and never
   * the enforcement — the server refuses a co-author's `PUT` with `403` regardless.
   */
  get canReorder(): boolean {
    return this.chapterList?.can_reorder ?? false;
  }

  /**
   * The add form's CLIENT validation, in the `…ServerErrors` map's shape so the view
   * merges the two the same way: `{ title: <message> }` when the title draft is blank
   * or whitespace-only, `{}` otherwise.
   *
   * The whitespace-only case is explicit (DoD-5): a bare truthiness check would let
   * `"   "` through, and the server would answer a `422` the author cannot act on. The
   * SKETCH contributes nothing — an empty sketch is legitimate and the backend accepts
   * it. Pure.
   */
  get addClientErrors(): Record<string, string> {
    // `.trim()`, not truthiness: `"   "` must NOT count as filled (DoD-5).
    return this.addTitleDraft.trim() === "" ? { title: BLANK_TITLE_MESSAGE } : {};
  }

  /**
   * Whether the add form may be submitted right now: no client errors AND no submit in
   * flight (`addSubmitStatus !== "loading"`).
   *
   * Deliberately NOT gated on `chapterListStatus`: "no add form bound to stale data
   * after a failed load" (DoD-10) is the PAGE's render branch — the form is not rendered
   * at all in the error branch — not a condition of this computed. Pure.
   */
  get canSubmitAdd(): boolean {
    return Object.keys(this.addClientErrors).length === 0 && this.addSubmitStatus !== "loading";
  }

  /**
   * The removal affordance predicate: `true` only for a chapter whose `state` is
   * `"planned"` (`domain-chapter.md` — only a planned chapter may be removed).
   *
   * A `get` returning a predicate rather than a method, so it stays a pure computed
   * derivation while still answering a per-chapter question. It drives the affordance
   * ONLY (DoD-8) and **never substitutes for the server's answer** (DoD-9): a co-author
   * can open a chapter from another session between this page's load and the click, so
   * the `409` refusal is what actually makes US-035.AC-2 true. Pure.
   */
  get canRemoveChapter(): (chapter: ChapterResponse) => boolean {
    return (chapter: ChapterResponse) => chapter.state === "planned";
  }

  /**
   * Whether a given chapter may move one position UP right now — the ↑ control's
   * `disabled` answer.
   *
   * `false` for the FIRST chapter of {@link ChaptersPageState.orderedChapters} (DoD-3),
   * `false` for a chapter that is not in the list at all, `false` before the first
   * successful load, and `false` while a reorder is in flight
   * (`reorderStatus === "loading"`) so a second move cannot race the first (DoD-7).
   *
   * It deliberately does NOT fold in {@link ChaptersPageState.canReorder}: when the
   * caller may not reorder, the control is ABSENT rather than disabled (DoD-4,
   * US-033.AC-2 client affordance), and absence is `ChapterOrderList`'s branch, not a
   * disabled flag. Nor does it substitute for the server's answer — a stale hint still
   * earns a `403`, which is what {@link ChaptersPageState.reorderError} carries.
   *
   * A `get` returning a predicate rather than a method, matching
   * {@link ChaptersPageState.canRemoveChapter}: a per-chapter question needs a parameter
   * and the rules allow only observable data plus pure `get` computeds. Call site reads
   * `state.canMoveUp(chapter)`. Pure.
   */
  get canMoveUp(): (chapter: ChapterResponse) => boolean {
    const chapters = this.orderedChapters;
    // A second move must not race the first: while the `PUT` is in flight EVERY row's
    // control is disabled, whichever end of the list it sits at (DoD-7).
    const inFlight = this.reorderStatus === "loading";
    return (chapter: ChapterResponse) => {
      if (inFlight) return false;
      // `-1` (not in the list, or nothing loaded yet) and `0` (the first chapter) are
      // both `false` — the two cases collapse into one comparison.
      return chapters.findIndex((row) => row.id === chapter.id) > 0;
    };
  }

  /**
   * Whether a given chapter may move one position DOWN right now — the ↓ control's
   * `disabled` answer, the mirror image of {@link ChaptersPageState.canMoveUp}.
   *
   * `false` for the LAST chapter of {@link ChaptersPageState.orderedChapters} (DoD-3),
   * and `false` under exactly the same three other conditions. A one-chapter book
   * therefore offers neither direction, and a zero-chapter book has nothing to ask.
   * Pure.
   */
  get canMoveDown(): (chapter: ChapterResponse) => boolean {
    const chapters = this.orderedChapters;
    const inFlight = this.reorderStatus === "loading";
    return (chapter: ChapterResponse) => {
      if (inFlight) return false;
      const index = chapters.findIndex((row) => row.id === chapter.id);
      return index !== -1 && index < chapters.length - 1;
    };
  }
}

/**
 * Load the book's chapters into the list trio, storing the WHOLE envelope returned by
 * `chaptersApi.listChapters` — never `.chapters` alone, so `can_reorder` survives.
 *
 * Intent: `runInAction` the trio to `"loading"` and clear `chapterListError`, await the
 * api call, abort-guard before every write, `runInAction` the envelope + `"ready"` on
 * success; an `ApiError` lands in `chapterListError` with `chapterListStatus = "error"`
 * and leaves `chapterList` as it was, anything else rethrows. An empty `chapters` array
 * is a SUCCESSFUL load, never an error (DoD-2).
 *
 * Also the retry path behind the error branch (DoD-10) and the re-seed path both writes
 * below call.
 */
export async function loadChapters(
  state: ChaptersPageState,
  bookId: string,
  signal?: AbortSignal,
): Promise<void> {
  runInAction(() => {
    state.chapterListStatus = "loading";
    state.chapterListError = null;
  });

  try {
    const envelope = await chaptersApi.listChapters(bookId, signal);
    if (signal?.aborted) return;
    runInAction(() => {
      // The WHOLE envelope — never `.chapters`, so `can_reorder` survives for step 007.
      // An empty `chapters` array is a successful load, never an error (DoD-2).
      state.chapterList = envelope;
      state.chapterListStatus = "ready";
    });
  } catch (err) {
    if (signal?.aborted) return;
    if (err instanceof ApiError) {
      runInAction(() => {
        state.chapterListError = err.message || "Could not load the chapters.";
        state.chapterListStatus = "error";
      });
      return;
    }
    throw err;
  }
}

/**
 * Add a chapter from the add-form drafts, then RE-SEED THE LIST FROM THE SERVER.
 *
 * Intent: build the body from the drafts (`{ title, sketch }`) read off the state, clear
 * `addServerErrors` and set `addSubmitStatus = "loading"`, await
 * `chaptersApi.createChapter(bookId, body, signal)`, then re-seed the rendered list from
 * the server — the create response plus a reload, or the reload alone. **Never an
 * optimistic splice** (`006.context.md`): DoD-3 asserts the rendered chapter came from
 * the SERVER, and a splice would satisfy it for the wrong reason. The server appends,
 * so the new chapter lands LAST in ordinal order (DoD-4, UC-031).
 *
 * Clears BOTH drafts on success ONLY. On an `ApiError` the message lands in
 * `addServerErrors` (4xx → the `title` key or the general `form` key as fits, 5xx → the
 * `form` key) with `addSubmitStatus = "error"`, and **both drafts are left untouched**
 * so nothing the author typed is lost (DoD-6); anything else rethrows. Abort-guarded
 * before every write.
 */
export async function addChapter(
  state: ChaptersPageState,
  bookId: string,
  signal?: AbortSignal,
): Promise<void> {
  // Read off the state VERBATIM: the drafts are the submitted values (DoD-3). The
  // non-blank rule gates submission; it does not rewrite what the author typed.
  const body: CreateChapterRequest = {
    title: state.addTitleDraft,
    sketch: state.addSketchDraft,
  };

  runInAction(() => {
    state.addServerErrors = {};
    state.addSubmitStatus = "loading";
  });

  try {
    const created = await chaptersApi.createChapter(bookId, body, signal);
    if (signal?.aborted) return;
    runInAction(() => {
      // The SERVER's chapter, not the draft — no optimistic splice. The row is
      // seeded from the create response and then re-seeded wholesale by the reload
      // below, which is the authoritative source of the rendered order (DoD-3, DoD-4).
      if (state.chapterList !== null) {
        state.chapterList = {
          ...state.chapterList,
          chapters: [...state.chapterList.chapters, created],
        };
      }
      // Success ONLY — a refusal leaves both drafts alone (DoD-6).
      state.addTitleDraft = "";
      state.addSketchDraft = "";
      state.addSubmitStatus = "ready";
    });
    await loadChapters(state, bookId, signal);
  } catch (err) {
    if (signal?.aborted) return;
    if (err instanceof ApiError) {
      runInAction(() => {
        const message = err.message || "Could not add the chapter.";
        state.addServerErrors =
          err.status >= 400 && err.status < 500 ? { title: message } : { form: message };
        state.addSubmitStatus = "error";
      });
      return;
    }
    throw err;
  }
}

/**
 * Remove one chapter, then re-seed the list from the server the same way {@link addChapter}
 * does.
 *
 * Intent: `runInAction` `removingChapterId = chapterId` and drop that chapter's entry
 * from `removeServerErrors`, await `chaptersApi.removeChapter(bookId, chapterId, signal)`
 * (which resolves to nothing — the endpoint answers `204`), then re-seed the list from a
 * fresh load; clear `removingChapterId` in every exit path. **No optimistic splice.**
 *
 * On an `ApiError` — the `409` a non-`planned` chapter earns, above all — the server's
 * message is stored in `removeServerErrors` **under `chapterId`** so it renders beside
 * that chapter, and **the list is LEFT UNTOUCHED**: the chapter stays where it is
 * (DoD-9, US-035.AC-2). Anything else rethrows. Abort-guarded before every write.
 */
export async function removeChapter(
  state: ChaptersPageState,
  bookId: string,
  chapterId: string,
  signal?: AbortSignal,
): Promise<void> {
  runInAction(() => {
    state.removingChapterId = chapterId;
    // This chapter's previous refusal is dropped as the retry starts; every other
    // chapter's stays, because the map is keyed by row.
    const remaining = { ...state.removeServerErrors };
    delete remaining[chapterId];
    state.removeServerErrors = remaining;
  });

  try {
    // Resolves to nothing — the endpoint answers `204`.
    await chaptersApi.removeChapter(bookId, chapterId, signal);
    if (signal?.aborted) return;
    // Re-seed from the server; never splice the row out locally.
    await loadChapters(state, bookId, signal);
  } catch (err) {
    if (signal?.aborted) return;
    if (err instanceof ApiError) {
      runInAction(() => {
        // Keyed by CHAPTER ID so the refusal renders beside the chapter it concerns,
        // and the list is left exactly as it was (DoD-9).
        state.removeServerErrors = {
          ...state.removeServerErrors,
          [chapterId]: err.message || "Could not remove this chapter.",
        };
      });
      return;
    }
    throw err;
  } finally {
    runInAction(() => {
      if (state.removingChapterId === chapterId) state.removingChapterId = null;
    });
  }
}

/**
 * Move ONE chapter ONE position up or down — what the ↑ / ↓ controls call.
 *
 * Intent: read {@link ChaptersPageState.orderedChapters}, find `chapterId`, compute the
 * NEW FULL ordered id sequence locally by swapping it with its neighbour in
 * `direction`, and then persist through {@link applyChapterOrder} — **the single persist
 * path both affordances funnel into** (DoD-6). There is no per-chapter move endpoint
 * (`context.md` → D3): the wire always carries the complete, current id set, never a
 * partial one (DoD-2). A move that cannot happen (the chapter is absent, or it is
 * already at that end) is a no-op that persists nothing.
 *
 * Does NOT re-implement the persist, the pending order, the re-seed or the error
 * handling — all of that is {@link applyChapterOrder}'s, so a button move and a drag are
 * provably the same write (DoD-6, and DoD-10's manual drag check rides on it).
 */
export async function moveChapter(
  state: ChaptersPageState,
  bookId: string,
  chapterId: string,
  direction: ChapterMoveDirection,
  signal?: AbortSignal,
): Promise<void> {
  // The COMPLETE current id set, in the order the author sees — never a partial one
  // (DoD-2). The new sequence is computed here; the write is `applyChapterOrder`'s.
  const chapterIds = state.orderedChapters.map((chapter) => chapter.id);
  const index = chapterIds.indexOf(chapterId);
  if (index === -1) return;

  const neighbour = direction === "up" ? index - 1 : index + 1;
  // Already at that end (or the list is empty): a no-op that persists NOTHING, so a
  // disabled control that was clicked anyway cannot produce a pointless write.
  if (neighbour < 0 || neighbour >= chapterIds.length) return;

  const next = [...chapterIds];
  next[index] = chapterIds[neighbour];
  next[neighbour] = chapterIds[index];

  await applyChapterOrder(state, bookId, next, signal);
}

/**
 * Apply an ARBITRARY new order — the full ordered id list — and re-seed from the server.
 * The drag-end handler's target, and the one function {@link moveChapter} persists
 * through: **the only chapter write a move triggers, called ONCE per move, with the
 * whole ordered id list** (DoD-6).
 *
 * Intent: `runInAction` `pendingOrder = chapterIds`, `reorderStatus = "loading"` and
 * `reorderError = null` — so the list renders the arranged order while the `PUT` is in
 * flight and every move control goes disabled (DoD-7) — then await
 * `chaptersApi.reorderChapters(bookId, { chapter_ids: chapterIds }, signal)` and re-seed
 * the list trio from the envelope the SERVER returned (DoD-1). On an `ApiError` the
 * server's message lands in {@link ChaptersPageState.reorderError} with
 * `reorderStatus = "error"` and the list is re-seeded from a FRESH {@link loadChapters},
 * so the rendered order matches the server's again (DoD-5, US-033.AC-2); anything else
 * rethrows. `pendingOrder` is discarded on EVERY exit path — success and failure alike —
 * never left holding the attempted order. Abort-guarded before every write.
 *
 * Touches only the reorder state and the list trio: `addTitleDraft`, `addSketchDraft`,
 * `addServerErrors`, `addSubmitStatus`, `removingChapterId` and `removeServerErrors` are
 * never read or written here, which is what makes the three error surfaces independent
 * (DoD-8).
 */
export async function applyChapterOrder(
  state: ChaptersPageState,
  bookId: string,
  chapterIds: string[],
  signal?: AbortSignal,
): Promise<void> {
  runInAction(() => {
    // A RENDERING optimism only: the list trio is NOT touched here, so nothing the
    // author sees becomes state until the server answers.
    state.pendingOrder = [...chapterIds];
    state.reorderStatus = "loading";
    state.reorderError = null;
  });

  try {
    // The ONE chapter write a move triggers, called ONCE, with the whole ordered id
    // list (DoD-6) — the same call a drag-end reaches through this same function.
    const envelope = await chaptersApi.reorderChapters(
      bookId,
      { chapter_ids: chapterIds },
      signal,
    );
    if (signal?.aborted) return;
    runInAction(() => {
      // What the SERVER returned, not the attempted order (DoD-1).
      state.chapterList = envelope;
      state.reorderStatus = "ready";
      state.pendingOrder = null;
    });
  } catch (err) {
    if (signal?.aborted) return;
    if (err instanceof ApiError) {
      runInAction(() => {
        state.reorderError = err.message || "Could not reorder the chapters.";
        state.reorderStatus = "error";
        // Discarded on FAILURE too — keeping it would leave the author looking at an
        // order the server does not have, with no way to tell (DoD-5).
        state.pendingOrder = null;
      });
      // Snap back to the server's order (DoD-5, US-033.AC-2). A read, not a write —
      // the reorder `PUT` above is still the only chapter write this path made.
      await loadChapters(state, bookId, signal);
      return;
    }
    throw err;
  } finally {
    // Every remaining exit path — an abort, or a rethrown non-`ApiError` — leaves no
    // pending order behind either.
    runInAction(() => {
      state.pendingOrder = null;
    });
  }
}
