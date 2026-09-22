// The close-turn registry (016) — the FIFTH member of the working page's module
// tier, beside `restoreBuffer.ts`, `activeChat.ts`, `contentSubject.ts` and
// `chapterUndo.ts`. Plain module functions matching its four siblings: no class, no
// MobX, no reactivity, no React, and NO import from `src/api/`.
//
// WHAT PROBLEM IT SOLVES. Closing a chapter is an ordinary assistant turn in the
// main chat (decision D1), but the control that starts it lives on `ChapterPage` in
// the CONTENT pane, while the thing that posts a turn lives in `ChatPaneState` in
// the CHAT pane. The two panes never call each other, and all three obvious
// alternatives are banned by `frontend.md` — React context (none in this repo), a
// cross-page callback up to the shell, and a custom `useX` hook. This is exactly the
// problem `contentSubject.ts` already solved for canvas writes, applied to "post a
// turn", so this module copies its idiom rather than inventing one.
//
// TWO REGISTRIES IN ONE MODULE, and they are independent on purpose:
//
//   1. THE CONTROLLER — the chat pane's `start` / `stop` / `setActive` seam, with
//      `contentSubject.ts`'s ownership discipline: newest registration wins outright,
//      and an unregister is a no-op unless the caller is still the registered owner
//      (a route transition mounts the new owner before the old one's cleanup runs).
//      `requestCloseTurnStart` / `requestCloseTurnStop` with NO controller registered
//      are no-ops (logged), never throws.
//
//   2. THE ACTIVE-CLOSE SIGNAL — `markCloseTurnActive` / `clearCloseTurnActive` /
//      `activeCloseTurn()`. This is the "a close is in progress" fact, and it is
//      stored in THIS module rather than only on the chat pane so it is readable at
//      any time, INDEPENDENT OF MOUNT ORDER. When a controller is registered, the
//      two writers also call its `setActive` SYNCHRONOUSLY, so the pane's own
//      observable state changes in the same tick — the paired-observable-bump idiom
//      `contentSubject.ts` / `chapterUndo.ts` already use, expressed here as a
//      controller callback rather than a second counter.
//
// WHY THE SIGNAL IS NOT "A STREAM IS RUNNING". `ChapterPage`'s load path calls
// `markCloseTurnActive` when the loaded chapter is `closing` and
// `clearCloseTurnActive` otherwise, so a RELOAD MID-CLOSE still renders the chat
// composer read-only with no stream running at all. `chapterPageState.ts`'s
// `requestChapterClose` / `cancelChapterCloseRequest` call the matching one on a
// successful response.
//
// NOTHING HERE IS OBSERVABLE and nothing here calls the server: it is a registry and a
// stored fact. The server side of the close is `api/chapters.ts`'s `closeChapterState` /
// `cancelChapterClose`, called from `pages/chapterPageState.ts`.

/**
 * What the chat pane offers the content pane: start a close turn, stop it, and be
 * told when a close is (or is no longer) in progress.
 *
 * `ChatPaneState` implements this and registers ITSELF in the shell's existing mount
 * effect, unregistering on unmount — so the implementation and its identity token are
 * the same object and nothing extra is threaded anywhere.
 *
 * - `start(bookId, chapterId)` — post the synthetic close prompt through the pane's
 *   existing turn pipeline, aimed at that chapter as the turn's subject;
 * - `stop()` — abort the live stream, reusing the pane's existing abort control;
 * - `setActive(active)` — the close-in-progress signal, pushed IN (never pulled): the
 *   pane stores it as its own observable, and page code never assigns it directly.
 */
export interface CloseTurnController {
  start(bookId: string, chapterId: string): void;
  stop(): void;
  setActive(active: { bookId: string; chapterId: string } | null): void;
}

/**
 * The single live controller — module-level, app-lifetime, deliberately NOT
 * observable: it is written from a mount/unmount effect and read at command time, and
 * nothing renders off it.
 */
let controller: CloseTurnController | null = null;

/**
 * The close currently in progress, or `null`. Held HERE and not only on the chat pane
 * so it is readable at any time regardless of which pane mounted first — that is what
 * makes a reload mid-close render read-only with no stream running.
 */
let activeClose: { bookId: string; chapterId: string } | null = null;

/**
 * Register the chat pane as the close-turn controller.
 *
 * The newest registration wins outright ({@link registerContentSubject}'s rule, and
 * for the same reason: during a route transition the pane mounting IS the one the
 * author is looking at). Returns nothing — the caller's token is the `controller` it
 * already holds.
 *
 */
export function registerCloseTurnController(c: CloseTurnController): void {
  // The newest registration wins outright: during a route transition the pane
  // mounting IS the one the author is looking at.
  controller = c;
}

/**
 * Clear the registration — but ONLY while it still belongs to `c`.
 *
 * The identity guard is the point: a late unmount whose registration has already been
 * superseded must clear nothing, or the newly-mounted pane would be left unreachable
 * (`unregisterContentSubject`'s rule verbatim).
 *
 */
export function unregisterCloseTurnController(c: CloseTurnController): void {
  // Identity guard: a late unmount whose registration has already been superseded
  // clears nothing, or the newly-mounted pane would be left unreachable.
  if (controller === c) controller = null;
}

/**
 * Ask the chat pane to post the close turn for `(bookId, chapterId)`.
 *
 * With NO controller registered this is a **no-op (logged)**, never a throw: the
 * server has already moved the chapter to `closing` by the time this is called, and
 * throwing into the page's effect would turn a recoverable state (the author can
 * cancel) into an error.
 *
 */
export function requestCloseTurnStart(bookId: string, chapterId: string): void {
  if (controller === null) {
    // A NO-OP, never a throw: the server has already moved the chapter to
    // `closing` by the time this is called, and throwing into the page's effect
    // would turn a recoverable state (the author can Stop) into an error.
    console.warn(
      `[closeTurn] no chat pane is registered, so the close turn for chapter ${chapterId} was not posted.`,
    );
    return;
  }
  controller.start(bookId, chapterId);
}

/**
 * Ask the chat pane to stop the live close turn. With no controller registered this
 * is a **no-op (logged)**, for the same reason as {@link requestCloseTurnStart}.
 *
 * Stopping the stream is only half of the Stop path — `chapterPageState.ts` also
 * calls `POST …/close/cancel`, which is what actually returns the chapter to `open`
 * and discards the run's artifacts (decision D4).
 *
 */
export function requestCloseTurnStop(): void {
  if (controller === null) {
    console.warn("[closeTurn] no chat pane is registered, so no close turn was stopped.");
    return;
  }
  controller.stop();
}

/**
 * Record that a close is in progress for `(bookId, chapterId)`.
 *
 * Writes this module's own stored value AND, when a controller is registered, calls
 * its `setActive` SYNCHRONOUSLY so the pane's observable changes in the same tick.
 * Both writers are unconditional — there is no ownership guard here, because the
 * value is about a CHAPTER, not about which pane happens to be mounted.
 *
 */
export function markCloseTurnActive(bookId: string, chapterId: string): void {
  activeClose = { bookId, chapterId };
  // SYNCHRONOUSLY, in the same tick, so the composer's read-only state changes with
  // the module's own value rather than a render later.
  if (controller !== null) controller.setActive(activeClose);
}

/**
 * Record that no close is in progress — the mirror of
 * {@link markCloseTurnActive}, clearing this module's value and pushing `null`
 * through the registered controller's `setActive` in the same tick.
 *
 * Called on a successful cancel, from the chat pane's own `done` / `error` handler,
 * and by `ChapterPage`'s load path whenever the loaded chapter is NOT `closing`.
 *
 */
export function clearCloseTurnActive(): void {
  activeClose = null;
  if (controller !== null) controller.setActive(null);
}

/**
 * The close currently in progress, read at call time — or `null` when there is none.
 *
 * Independent of mount order and of whether a stream is running, which is what lets a
 * page reload mid-close still render the composer read-only.
 *
 */
export function activeCloseTurn(): { bookId: string; chapterId: string } | null {
  return activeClose;
}
