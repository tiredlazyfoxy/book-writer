import { makeAutoObservable, runInAction } from "mobx";
import * as memosApi from "../../api/memos";
import { ApiError } from "../../api/client";
import type { MemoResponse } from "../../types/memos";

/**
 * Which way an arrow control moves a memo — the `ChapterMoveDirection` shape, kept
 * identical so the two reorder surfaces read the same. FROZEN (skeleton 026/011).
 */
export type MemoMoveDirection = "up" | "down";

/**
 * Page state for `MemosListPage` — the author's own memos at `/work/:bookId/memos`
 * (FEAT-021, UC-103..UC-107), held via `useState(() => new MemosListPageState())`.
 *
 * `chatsListPageState.ts` is the precedent for every shape here: one async-resource
 * trio, a client-side `showArchived` filter over an already-merged list, pure `get`
 * computeds, a per-row status map replaced as a WHOLE NEW OBJECT, and external
 * `(state, bookId, …, signal?)` effect functions below — the class itself holds
 * observable data plus pure computeds ONLY (no effectful methods, no setters).
 *
 * The one thing this page does that no other page does: **the list IS the editor**
 * (`026/context.md` decision 12). There is no `/memos/:id`, creation appends into the
 * list in place, and the body saves on focus loss — so the draft map, the focus
 * target and the per-row error surface all live here rather than on an item page.
 *
 * Deliberately absent, and not to be added: a `baseVersion` / version token, a restore
 * buffer write, a divergence view, a `409` path (a memo has one writer — decision 5),
 * a delete path (archive-not-delete — decision 6). The reorder slots below are step
 * 011's and are the ONLY optimistic state on the class — a rendering optimism, never a
 * state optimism.
 */
export class MemosListPageState {
  /**
   * EVERY memo the caller owns in this book — archived and non-archived together,
   * merged by the ONE load, so that toggling {@link showArchived} is a client-side
   * filter and never a refetch (UC-107 step 3; `loadChats`'s shape, kept identical).
   */
  memos: MemoResponse[] = [];
  memosStatus: "idle" | "loading" | "ready" | "error" = "idle";
  memosError: string | null = null;

  /** Whether the archived section is revealed. A pure filter — it fetches nothing. */
  showArchived = false;

  /**
   * What the author has typed but not yet blurred, keyed by memo id. A row with no
   * entry shows the server's `body` by absence; the entry is dropped once the save
   * round trip settles (success OR failure — a failed save falls back to server truth,
   * UC-104). Replaced as a whole new object, never mutated.
   */
  bodyDrafts: Record<string, string> = {};

  /**
   * The id of the memo whose body field should take focus on its next render
   * (US-123.AC-2), set by {@link createMemo} from the row the SERVER returned and
   * cleared when the row reports the focus through its `onBodyFocus` prop. This is
   * why no `useEffect` and no ref-chasing is needed in the row.
   */
  focusMemoId: string | null = null;

  /**
   * Per-row write status keyed by memo id — save, on/off, archive and restore all
   * report here, so one row's in-flight call disables and reports on that row alone.
   * A row with no entry is `"idle"` by absence. Whole new object on every change:
   * `state.actionStatus = { ...state.actionStatus, [id]: "loading" }`.
   */
  actionStatus: Record<string, "idle" | "loading" | "error"> = {};

  /**
   * Per-row author-facing failure message keyed by memo id (UC-104 exception
   * handling). Separate from {@link memosError}, which belongs to the load trio: a
   * failed save must never blank the list. Whole new object on every change.
   */
  actionError: Record<string, string | null> = {};

  /**
   * In-flight state of a REORDER (UC-105 / US-126), held apart from
   * {@link memosStatus} and {@link actionStatus} so a refused reorder disturbs neither
   * the load nor any row's own save / toggle / archive status.
   *
   * `"loading"` is what disables every arrow control and the drag sensor, so a second
   * reorder cannot interleave into an order nobody chose (DoD-8).
   *
   * FROZEN (skeleton 026/011).
   */
  reorderStatus: "idle" | "loading" | "ready" | "error" = "idle";

  /**
   * The server's refusal of a reorder, or `null` when there is none — a LIST-level
   * error surface, rendered by the page beside the list rather than on a row, because
   * a reorder concerns the whole list. Never shares a holder with {@link memosError}
   * (the load trio) or {@link actionError} (per row).
   *
   * FROZEN (skeleton 026/011).
   */
  reorderError: string | null = null;

  /**
   * The memo-id sequence currently being arranged — what the working list RENDERS
   * while a reorder is in flight — or `null` whenever no reorder is running.
   *
   * A RENDERING optimism, never a state optimism: {@link memos} is not touched until
   * the server answers, so **discarding this array is the whole rollback** (DoD-6) —
   * the view snaps back to the order the server still holds with no refetch. Discarded
   * on success too, where the re-seeded rows carry the server's new ordinals (DoD-2).
   * Non-`null` exactly while `reorderStatus === "loading"`. Holds ids, not rows.
   *
   * FROZEN (skeleton 026/011).
   */
  pendingOrder: string[] | null = null;

  constructor() {
    makeAutoObservable(this);
  }

  /**
   * The working list — the non-archived memos in `ordinal` order (ascending), which
   * is what makes a created or restored memo appear LAST (US-123.AC-1 / US-128.AC-2)
   * and an archived one disappear from it (US-128.AC-1). Ordinals carry gaps by
   * design; nothing here renumbers.
   */
  get workingMemos(): MemoResponse[] {
    return this.memos.filter((memo) => !memo.archived).sort((a, b) => a.ordinal - b.ordinal);
  }

  /**
   * The archived memos, `ordinal`-ordered — the content of the archived section the
   * {@link showArchived} toggle reveals, filtered client-side out of {@link memos}.
   */
  get archivedMemos(): MemoResponse[] {
    return this.memos.filter((memo) => memo.archived).sort((a, b) => a.ordinal - b.ordinal);
  }

  /**
   * Each loaded memo's DISPLAYED body, keyed by id: the draft when one exists,
   * otherwise the value the server last returned. One computed rather than a per-row
   * method, so the class stays observable data plus pure `get` computeds. `""` is a
   * legitimate displayed body (UC-103) and is never treated as absent.
   */
  get displayedBodies(): Record<string, string> {
    const bodies: Record<string, string> = {};
    for (const memo of this.memos) {
      const draft = this.bodyDrafts[memo.id];
      // `undefined` — not falsiness — is what "no draft" means: an empty string is a
      // legitimate typed value and must not fall back to the server's body.
      bodies[memo.id] = draft !== undefined ? draft : memo.body;
    }
    return bodies;
  }

  /** `true` when {@link workingMemos} is empty — the page's labelled empty state. */
  get isEmpty(): boolean {
    return this.workingMemos.length === 0;
  }

  /**
   * The working list AS DISPLAYED — the one list `MemoOrderList` renders and the one
   * whose ids a reorder submits. FROZEN (skeleton 026/011).
   *
   * Resolves to {@link pendingOrder} while a reorder is in flight — the arranged
   * sequence mapped back onto the loaded rows, so the new order is on screen BEFORE
   * the call resolves (DoD-5) — and to {@link workingMemos} (the server's ordinal
   * order) whenever `pendingOrder` is `null`, which is every other moment including
   * immediately after a refusal (DoD-6) and after a success, where the rows have been
   * re-seeded with the server's ordinals (DoD-2).
   *
   * **Never contains an archived memo**, in either branch: it is built from
   * {@link workingMemos}, and {@link showArchived} — a pure view filter — cannot widen
   * it (DoD-7). A memo the pending sequence does not name (it arrived from a
   * concurrent load) keeps its ordinal place at the end rather than vanishing.
   * Pure: it reads state and writes none.
   */
  get displayedWorkingMemos(): MemoResponse[] {
    // Built from the WORKING list in both branches, so an archived memo can never
    // appear here and `showArchived` cannot widen it (DoD-7).
    const working = this.workingMemos;
    if (this.pendingOrder === null) return working;

    const remaining = new Map(working.map((memo) => [memo.id, memo]));
    const rendered: MemoResponse[] = [];
    for (const id of this.pendingOrder) {
      const memo = remaining.get(id);
      if (memo !== undefined) {
        rendered.push(memo);
        remaining.delete(id);
      }
    }
    // A memo the pending sequence does not name keeps its ordinal place at the end
    // rather than vanishing.
    for (const memo of working) {
      if (remaining.has(memo.id)) rendered.push(memo);
    }
    return rendered;
  }
}

/**
 * Put the row the server returned in place of the local one — the backend is the
 * source of truth after every write, never the optimistic draft.
 */
function replaceMemo(state: MemosListPageState, updated: MemoResponse): void {
  state.memos = state.memos.map((memo) => (memo.id === updated.id ? updated : memo));
}

/**
 * Drop one row's draft entry, as a WHOLE NEW object — the field then shows the
 * server's value by absence.
 */
function dropDraft(state: MemosListPageState, memoId: string): void {
  const drafts = { ...state.bodyDrafts };
  delete drafts[memoId];
  state.bodyDrafts = drafts;
}

/**
 * Load the caller's memos into the trio — ONCE, with the include-archived flag ON
 * (`memosApi.listMemos(bookId, true, signal)`), so `showArchived` filters what is
 * already loaded and toggling it refetches nothing (UC-107 step 3).
 *
 * The call carries NO user id: the only identity in it is the book from the URL, and
 * the server scopes the read to the caller (US-124.AC-1, `context.md` decision 3).
 * Abort-guarded; an `ApiError` becomes an author-facing `memosError`, anything else
 * rethrows.
 */
export async function loadMemos(
  state: MemosListPageState,
  bookId: string,
  signal?: AbortSignal,
): Promise<void> {
  runInAction(() => {
    state.memosStatus = "loading";
    state.memosError = null;
  });

  try {
    // ONE call, archived included — the toggle filters what this returned.
    const items = await memosApi.listMemos(bookId, true, signal);
    if (signal?.aborted) return;
    runInAction(() => {
      state.memos = items;
      state.memosStatus = "ready";
    });
  } catch (err) {
    if (signal?.aborted) return;
    if (err instanceof ApiError) {
      runInAction(() => {
        state.memosError = err.message;
        state.memosStatus = "error";
      });
      return;
    }
    throw err;
  }
}

/**
 * Create a memo (UC-103 / US-123) — `memosApi.createMemo(bookId, { body: "" }, signal)`.
 *
 * The new memo is created EMPTY and active, appended to `state.memos` from what the
 * server returned (never a locally minted row), which puts it LAST in
 * {@link MemosListPageState.workingMemos}; its id is then written to
 * `state.focusMemoId` so the row takes focus on its next render with no further author
 * action. An empty body is not an error and is never withheld.
 *
 * An `ApiError` is swallowed into the page's `memosError` (there is no row to blame
 * when the create itself failed); anything else rethrows.
 */
export async function createMemo(
  state: MemosListPageState,
  bookId: string,
  signal?: AbortSignal,
): Promise<void> {
  runInAction(() => {
    state.memosError = null;
  });

  try {
    const created = await memosApi.createMemo(bookId, { body: "" }, signal);
    if (signal?.aborted) return;
    runInAction(() => {
      // The SERVER's row, appended: the ordinal it carries is what puts it last.
      state.memos = [...state.memos, created];
      state.focusMemoId = created.id;
    });
  } catch (err) {
    if (signal?.aborted) return;
    if (err instanceof ApiError) {
      runInAction(() => {
        // The trio's STATUS is left alone: a failed create must not blank a list
        // that loaded perfectly well.
        state.memosError = err.message;
      });
      return;
    }
    throw err;
  }
}

/**
 * Save one memo's body on focus loss (UC-104 / US-125.AC-1) —
 * `memosApi.updateMemoBody(bookId, memoId, { body }, signal)`.
 *
 * Called from the row's ordinary `onBlur` handler and ONLY when the draft differs from
 * the server's value; there is no Save control (US-125.AC-2), no debounce, no autosave
 * timer and no beforeunload flush — one write path, and this is it.
 *
 * On success the returned row REPLACES the local one and the row's draft entry is
 * dropped, so the field shows what the server returned. On `ApiError` the draft entry
 * is dropped TOO — the row falls back to server truth rather than keeping an unsaved
 * optimistic value — and the message lands in `actionError[memoId]` (DoD-16). Anything
 * that is not an `ApiError` rethrows.
 */
export async function saveMemoBody(
  state: MemosListPageState,
  bookId: string,
  memoId: string,
  body: string,
  signal?: AbortSignal,
): Promise<void> {
  runInAction(() => {
    state.actionStatus = { ...state.actionStatus, [memoId]: "loading" };
    state.actionError = { ...state.actionError, [memoId]: null };
  });

  try {
    const updated = await memosApi.updateMemoBody(bookId, memoId, { body }, signal);
    if (signal?.aborted) return;
    runInAction(() => {
      replaceMemo(state, updated);
      dropDraft(state, memoId);
      state.actionStatus = { ...state.actionStatus, [memoId]: "idle" };
      state.actionError = { ...state.actionError, [memoId]: null };
    });
  } catch (err) {
    if (signal?.aborted) return;
    if (err instanceof ApiError) {
      runInAction(() => {
        // The draft goes too: the row falls back to SERVER TRUTH and says so, rather
        // than keeping an unsaved optimistic value (DoD-16).
        dropDraft(state, memoId);
        state.actionStatus = { ...state.actionStatus, [memoId]: "error" };
        state.actionError = { ...state.actionError, [memoId]: err.message };
      });
      return;
    }
    throw err;
  }
}

/**
 * Switch one memo on or off (UC-106 / US-127) — `memosApi.activateMemo` when `active`
 * is `true`, `memosApi.deactivateMemo` when it is `false`. Two verbs, one axis: the
 * focus-loss `PUT` never carries state it did not mean to write.
 *
 * The memo STAYS in the working list either way (US-127.AC-1) and the returned row
 * replaces the local one, so the switch shows server truth. Switching off the caller's
 * only active memo is an ordinary success — nothing refuses and nothing is restored
 * behind the author's back (US-127.AC-5). `ApiError` → `actionError[memoId]` with the
 * row left showing the server's flag; anything else rethrows.
 */
export async function setMemoActive(
  state: MemosListPageState,
  bookId: string,
  memoId: string,
  active: boolean,
  signal?: AbortSignal,
): Promise<void> {
  runInAction(() => {
    state.actionStatus = { ...state.actionStatus, [memoId]: "loading" };
    state.actionError = { ...state.actionError, [memoId]: null };
  });

  try {
    const updated = active
      ? await memosApi.activateMemo(bookId, memoId, signal)
      : await memosApi.deactivateMemo(bookId, memoId, signal);
    if (signal?.aborted) return;
    runInAction(() => {
      replaceMemo(state, updated);
      state.actionStatus = { ...state.actionStatus, [memoId]: "idle" };
      state.actionError = { ...state.actionError, [memoId]: null };
    });
  } catch (err) {
    if (signal?.aborted) return;
    if (err instanceof ApiError) {
      runInAction(() => {
        state.actionStatus = { ...state.actionStatus, [memoId]: "error" };
        state.actionError = { ...state.actionError, [memoId]: err.message };
      });
      return;
    }
    throw err;
  }
}

/**
 * Archive one memo (UC-107 / US-128.AC-1) — `memosApi.archiveMemo(bookId, memoId,
 * signal)`. The returned row replaces the local one, which moves it out of
 * {@link MemosListPageState.workingMemos} and into
 * {@link MemosListPageState.archivedMemos} with no refetch. Its `active` flag is
 * untouched, its ordinal leaves a gap, and there is NO delete path anywhere
 * (US-128.AC-3). `ApiError` → `actionError[memoId]`; anything else rethrows.
 */
export async function archiveMemo(
  state: MemosListPageState,
  bookId: string,
  memoId: string,
  signal?: AbortSignal,
): Promise<void> {
  runInAction(() => {
    state.actionStatus = { ...state.actionStatus, [memoId]: "loading" };
    state.actionError = { ...state.actionError, [memoId]: null };
  });

  try {
    const updated = await memosApi.archiveMemo(bookId, memoId, signal);
    if (signal?.aborted) return;
    runInAction(() => {
      replaceMemo(state, updated);
      state.actionStatus = { ...state.actionStatus, [memoId]: "idle" };
      state.actionError = { ...state.actionError, [memoId]: null };
    });
  } catch (err) {
    if (signal?.aborted) return;
    if (err instanceof ApiError) {
      runInAction(() => {
        state.actionStatus = { ...state.actionStatus, [memoId]: "error" };
        state.actionError = { ...state.actionError, [memoId]: err.message };
      });
      return;
    }
    throw err;
  }
}

/**
 * Restore one archived memo (UC-107 / US-128.AC-2) — `memosApi.restoreMemo(bookId,
 * memoId, signal)`. The returned row replaces the local one and carries the server's
 * new ordinal, so the memo reappears LAST in the working list rather than in its old
 * slot, with the `active` flag it had when it was archived.
 * `ApiError` → `actionError[memoId]`; anything else rethrows.
 */
export async function restoreMemo(
  state: MemosListPageState,
  bookId: string,
  memoId: string,
  signal?: AbortSignal,
): Promise<void> {
  runInAction(() => {
    state.actionStatus = { ...state.actionStatus, [memoId]: "loading" };
    state.actionError = { ...state.actionError, [memoId]: null };
  });

  try {
    const updated = await memosApi.restoreMemo(bookId, memoId, signal);
    if (signal?.aborted) return;
    runInAction(() => {
      replaceMemo(state, updated);
      state.actionStatus = { ...state.actionStatus, [memoId]: "idle" };
      state.actionError = { ...state.actionError, [memoId]: null };
    });
  } catch (err) {
    if (signal?.aborted) return;
    if (err instanceof ApiError) {
      runInAction(() => {
        state.actionStatus = { ...state.actionStatus, [memoId]: "error" };
        state.actionError = { ...state.actionError, [memoId]: err.message };
      });
      return;
    }
    throw err;
  }
}

/**
 * Move ONE memo ONE position up or down — what the arrow controls call (UC-105 /
 * US-126.AC-2). FROZEN (skeleton 026/011).
 *
 * Intent: read {@link MemosListPageState.displayedWorkingMemos}, find `memoId`, compute
 * the NEW FULL ordered id sequence locally by swapping it with its neighbour in
 * `direction`, and persist through {@link applyMemoOrder} — **the single persist path
 * both affordances funnel into**. A move that cannot happen (the memo is absent from
 * the working list, or it is already at that end) is a no-op that persists NOTHING, so
 * a disabled control clicked anyway cannot produce a pointless write.
 *
 * **It never calls an api function itself**, and it does not re-implement the pending
 * order, the re-seed or the error handling — all of that is {@link applyMemoOrder}'s,
 * which is what makes an arrow move and a drag provably the same single write (DoD-1,
 * and DoD-4's `[manual/live]` drag check rides on it).
 */
export async function moveMemo(
  state: MemosListPageState,
  bookId: string,
  memoId: string,
  direction: MemoMoveDirection,
  signal?: AbortSignal,
): Promise<void> {
  // The COMPLETE working list in the order the author sees it — never a partial one
  // and never an archived id. The new sequence is computed here; the write is
  // `applyMemoOrder`'s, the single persist path (DoD-1).
  const memoIds = state.displayedWorkingMemos.map((memo) => memo.id);
  const index = memoIds.indexOf(memoId);
  if (index === -1) return;

  const neighbour = direction === "up" ? index - 1 : index + 1;
  // Already at that end (or the list is empty): a no-op that persists NOTHING, so a
  // disabled control clicked anyway cannot produce a pointless write.
  if (neighbour < 0 || neighbour >= memoIds.length) return;

  const next = [...memoIds];
  next[index] = memoIds[neighbour];
  next[neighbour] = memoIds[index];

  await applyMemoOrder(state, bookId, next, signal);
}

/**
 * Apply an ARBITRARY new order — the full ordered id list — and re-seed from the
 * server. The drag-end handler's target and the one function {@link moveMemo} persists
 * through: **the only memo write a reorder triggers, called ONCE per reorder, with the
 * whole ordered id list** (DoD-1). FROZEN (skeleton 026/011).
 *
 * Intent: `runInAction` `pendingOrder = [...memoIds]`, `reorderStatus = "loading"` and
 * `reorderError = null` — so the list renders the arranged order while the `PUT` is in
 * flight (DoD-5) and every arrow goes disabled (DoD-8) — then await
 * `memosApi.reorderMemos(bookId, { memo_ids: memoIds }, signal)` ONCE and re-seed from
 * the envelope the SERVER returned (DoD-2).
 *
 * **What `memoIds` must be**: the complete ordered id list of the caller's
 * **non-archived** memos — the ids of {@link MemosListPageState.displayedWorkingMemos},
 * nothing added and nothing left out. Backend step 004 answers **400** to a short list,
 * a long one, a duplicate, an archived id or another author's id, and the archived
 * section's ids never belong here even when {@link MemosListPageState.showArchived} is
 * on (the filter is a view concern — DoD-7). This function submits what it is handed;
 * it does not filter, pad or dedupe.
 *
 * **The re-seed is a MERGE, not a replacement**: `reorderMemos` returns the working
 * memos only, so each returned row replaces its local twin (carrying the server's new
 * ordinal) while the archived rows in `state.memos` are kept untouched — an archived
 * memo must not vanish from the list because a reorder happened. `pendingOrder` is then
 * `null` and `reorderStatus = "ready"`, so the list renders the SERVER's order, not the
 * local computation.
 *
 * **On `ApiError`**: `reorderError = err.message || "Could not reorder the memos."`,
 * `reorderStatus = "error"`, and `pendingOrder` discarded — which IS the rollback
 * (DoD-6): `state.memos` was never mutated, so dropping the pending sequence snaps the
 * view back to server truth with no refetch and no partial order surviving. Anything
 * that is not an `ApiError` rethrows. `pendingOrder` is left `null` on EVERY exit path,
 * including an abort. Abort-guarded before every write.
 *
 * Touches only the reorder slots and `state.memos`: `bodyDrafts`, `focusMemoId`,
 * `actionStatus`, `actionError`, `showArchived` and the load trio's status are never
 * written here, so a refused reorder leaves every row's own state alone.
 */
export async function applyMemoOrder(
  state: MemosListPageState,
  bookId: string,
  memoIds: string[],
  signal?: AbortSignal,
): Promise<void> {
  runInAction(() => {
    // A RENDERING optimism only: `state.memos` is NOT touched here, so the arranged
    // order is on screen before the call resolves (DoD-5) without becoming state.
    state.pendingOrder = [...memoIds];
    state.reorderStatus = "loading";
    state.reorderError = null;
  });

  try {
    // The ONE memo write a reorder triggers, called ONCE, with the whole ordered id
    // list (DoD-1) — the same call a drag-end reaches through this same function.
    const envelope = await memosApi.reorderMemos(bookId, { memo_ids: memoIds }, signal);
    if (signal?.aborted) return;
    runInAction(() => {
      // A MERGE, not a replacement: the envelope carries the WORKING memos only, so
      // each returned row replaces its local twin (with the server's new ordinal)
      // while the archived rows are kept — an archived memo must not vanish because
      // a reorder happened. What the SERVER returned, never the local computation
      // (DoD-2).
      const returned = new Map(envelope.items.map((memo) => [memo.id, memo]));
      state.memos = state.memos.map((memo) => returned.get(memo.id) ?? memo);
      state.reorderStatus = "ready";
      state.pendingOrder = null;
    });
  } catch (err) {
    if (signal?.aborted) return;
    if (err instanceof ApiError) {
      runInAction(() => {
        state.reorderError = err.message || "Could not reorder the memos.";
        state.reorderStatus = "error";
        // Discarding the pending sequence IS the rollback (DoD-6): `state.memos` was
        // never mutated, so the view snaps back to server truth with no refetch and
        // no partial order surviving.
        state.pendingOrder = null;
      });
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
