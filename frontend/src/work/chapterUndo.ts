// The assistant-write undo stack (015 step 011) — the FOURTH member of the
// working page's module tier, beside `restoreBuffer.ts`, `activeChat.ts` and
// `contentSubject.ts`. Plain module functions matching its three siblings: no
// class, no MobX, no reactivity, no React, and NO import from `src/api/`.
//
// `frontend-work-drafts.md` → "The module tier — three members" requires a fourth
// to be added ON PURPOSE rather than by precedent. It is: `015/context.md` → D6
// carries the sanction, and `outcome.md` records it.
//
// TWO PROPERTIES THAT ARE THE DESIGN, NOT AN OMISSION:
//
// 1. **In memory only.** Nothing is written to `localStorage`, and nothing survives
//    a reload. Twenty chapter bodies would blow the few-megabyte origin quota the
//    restore buffer already has an eviction policy for, and an undo stack that
//    evicts OTHER items' unsaved drafts is strictly worse than one that does not
//    survive a reload (D6). The module survives page NAVIGATION because it is
//    module-level, which is the whole point.
// 2. **Assistant writes only.** ProseMirror ships a real history plugin, so the
//    author's typing already has undo inside the editor. A second stack over the
//    same keystrokes would give the author two undo affordances that disagree about
//    what "one step back" means (D6). The caller pushes exactly once, immediately
//    before an assistant-originated write is applied — the snapshot is of what the
//    author is about to lose.
//
// The stack is NOT cleared on save: an author may want to undo an assistant write
// after saving, and the pop just sets the draft, which re-saves as an ordinary save
// against the current version.

/**
 * The most snapshots kept per `(book, chapter)` pair. Pushing onto a full stack
 * drops the OLDEST, so the twenty most recent states stay reachable and older ones
 * are gone for good (D6).
 *
 * Module-private on purpose: nothing outside needs it, and an exported constant
 * would invite a spec to assert the constant instead of the behaviour.
 */
const MAX_SNAPSHOTS = 20;

/**
 * Every pair's snapshots, oldest first — a plain module-level `Map`. It lives as
 * long as the document (so it survives page NAVIGATION, which is the point) and
 * dies with a reload. Nothing here reaches `localStorage`.
 */
const stacks = new Map<string, string[]>();

/**
 * The map key for a `(bookId, chapterId)` pair. The separator is a NUL, which no
 * id can contain, so two distinct pairs can never collide onto one stack: the same
 * chapter number in another book is a different stack.
 */
function pairKey(bookId: string, chapterId: string): string {
  return `${bookId}\u0000${chapterId}`;
}

/**
 * Push one body snapshot onto the stack for a `(bookId, chapterId)` pair.
 *
 * `body` is the draft AS IT IS ABOUT TO BE OVERWRITTEN — the caller snapshots
 * before applying, never after. The empty string is a legitimate snapshot (an
 * author may clear a chapter) and is pushed like any other value.
 *
 * At most {@link MAX_SNAPSHOTS} are kept per pair; a push onto a full stack drops
 * the oldest. Pairs are independent: pushing for one chapter, or for the same
 * chapter number in another book, never touches another pair's stack.
 */
export function pushChapterUndoSnapshot(
  bookId: string,
  chapterId: string,
  body: string,
): void {
  const key = pairKey(bookId, chapterId);
  const stack = stacks.get(key);
  if (stack === undefined) {
    stacks.set(key, [body]);
    return;
  }
  stack.push(body);
  // A push onto a full stack drops the OLDEST, so the cap holds for any number of
  // pushes and the twenty most recent states stay reachable.
  if (stack.length > MAX_SNAPSHOTS) {
    stack.splice(0, stack.length - MAX_SNAPSHOTS);
  }
}

/**
 * Pop the MOST RECENT snapshot for a `(bookId, chapterId)` pair, removing it, or
 * `null` when that pair's stack is empty.
 *
 * `null` means "nothing to undo" and is distinguishable from a popped empty body,
 * which comes back as `""` — which is why the return is `string | null` and not a
 * bare `string`. Repeated pops walk back most-recent-first.
 */
export function popChapterUndoSnapshot(
  bookId: string,
  chapterId: string,
): string | null {
  const key = pairKey(bookId, chapterId);
  const stack = stacks.get(key);
  if (stack === undefined) return null;
  const snapshot = stack.pop();
  if (snapshot === undefined) {
    // An emptied stack holds nothing worth keeping around.
    stacks.delete(key);
    return null;
  }
  if (stack.length === 0) stacks.delete(key);
  return snapshot;
}

/**
 * How many snapshots a `(bookId, chapterId)` pair currently holds — `0` for a pair
 * that has never been pushed to. This is what an undo control reads to enable
 * itself, so it must never throw for an unknown pair.
 */
export function chapterUndoDepth(bookId: string, chapterId: string): number {
  return stacks.get(pairKey(bookId, chapterId))?.length ?? 0;
}

/**
 * Drop every snapshot held for a `(bookId, chapterId)` pair, leaving every other
 * pair untouched. Clearing a pair that holds nothing is a no-op, never an error.
 */
export function clearChapterUndo(bookId: string, chapterId: string): void {
  stacks.delete(pairKey(bookId, chapterId));
}
