/**
 * The chapter undo stack — the module tier's FOURTH member —
 * 015.chapter-writing-free-mode / 011.work-module-tier-chapter, DoD-10 · DoD-11.
 *
 * Bound to the frozen signatures in status.md -> `## Skeleton` (015 step 011):
 *   pushChapterUndoSnapshot(bookId: string, chapterId: string, body: string): void
 *   popChapterUndoSnapshot(bookId: string, chapterId: string): string | null
 *   chapterUndoDepth(bookId: string, chapterId: string): number
 *   clearChapterUndo(bookId: string, chapterId: string): void
 *
 * The air gap: every expected value comes from the step file's Definition of done and
 * Interface intent, and from `context.md` -> D6 — never from code:
 *   - DoD-10: at most TWENTY snapshots are kept per `(book, chapter)` pair, dropping the
 *     OLDEST; popping returns them MOST-RECENT-FIRST and returns nothing when empty;
 *   - DoD-11: stacks for different chapters and different books are INDEPENDENT, and
 *     nothing the module holds is written to `localStorage` — D6 is explicit that this
 *     tier member is IN MEMORY only, because 20 chapter bodies would blow the quota the
 *     restore buffer already evicts against, and evicting other items' unsaved drafts to
 *     hold an undo stack is the wrong trade;
 *   - `null` vs `""` is why the pop is nullable: a popped EMPTY body is `""`, which is a
 *     legitimate snapshot, while `null` means "nothing to undo";
 *   - the depth never throws for a pair never pushed to — an undo control reads it to
 *     enable itself;
 *   - clearing a pair drops that pair's stack and leaves every other pair untouched.
 *
 * Pure module tests, matching the module's three siblings: no rendering, no MobX, no
 * router, no api mocks. Its state is MODULE-LEVEL and survives between tests in a file,
 * so every case clears the pairs it uses first. `tests/setup.ts` clears `localStorage`
 * after every test. `globals: false`: every primitive is imported explicitly.
 */
import { beforeEach, describe, expect, it } from "vitest";
import {
  chapterUndoDepth,
  clearChapterUndo,
  popChapterUndoSnapshot,
  pushChapterUndoSnapshot,
} from "../../src/work/chapterUndo";

/* ------------------------------------------------------------------ fixtures */

const BOOK_A = "bk-1";
const BOOK_B = "bk-2";
const CHAPTER_1 = "ch-1";
const CHAPTER_2 = "ch-2";

/** The cap the step file pins: "keeping at most 20, dropping the oldest". */
const MAX_SNAPSHOTS = 20;

/** Every pair these specs touch, cleared before each case. */
const PAIRS: Array<[string, string]> = [
  [BOOK_A, CHAPTER_1],
  [BOOK_A, CHAPTER_2],
  [BOOK_B, CHAPTER_1],
  [BOOK_B, CHAPTER_2],
];

/**
 * Harness hygiene only — never an assertion, so a module that cannot yet clear must not
 * turn an unrelated case red. Every case that depends on "this pair is empty" asserts
 * it for itself.
 */
beforeEach(() => {
  for (const [bookId, chapterId] of PAIRS) {
    try {
      clearChapterUndo(bookId, chapterId);
    } catch {
      /* the module is unavailable; the cases below will say so themselves */
    }
  }
});

/** Every `localStorage` key currently in the store. */
function storageKeys(): string[] {
  const keys: string[] = [];
  for (let i = 0; i < localStorage.length; i += 1) {
    const key = localStorage.key(i);
    if (key !== null) keys.push(key);
  }
  return keys;
}

/** Every `localStorage` value currently in the store. */
function storageValues(): string[] {
  return storageKeys().map((key) => localStorage.getItem(key) ?? "");
}

/* ------------------------------- DoD-10: the cap, the order and the empty answer */

describe("the undo stack keeps at most 20 snapshots per (book, chapter) (DoD-10)", () => {
  it("DoD-10: a pushed snapshot is held, and the depth reports it", () => {
    pushChapterUndoSnapshot(BOOK_A, CHAPTER_1, "the body before the assistant wrote");

    expect(chapterUndoDepth(BOOK_A, CHAPTER_1)).toBe(1);
    expect(popChapterUndoSnapshot(BOOK_A, CHAPTER_1)).toBe(
      "the body before the assistant wrote",
    );
  });

  it("DoD-10: popping returns the snapshots MOST-RECENT-FIRST", () => {
    pushChapterUndoSnapshot(BOOK_A, CHAPTER_1, "first");
    pushChapterUndoSnapshot(BOOK_A, CHAPTER_1, "second");
    pushChapterUndoSnapshot(BOOK_A, CHAPTER_1, "third");

    expect(chapterUndoDepth(BOOK_A, CHAPTER_1)).toBe(3);
    expect(popChapterUndoSnapshot(BOOK_A, CHAPTER_1)).toBe("third");
    expect(popChapterUndoSnapshot(BOOK_A, CHAPTER_1)).toBe("second");
    expect(popChapterUndoSnapshot(BOOK_A, CHAPTER_1)).toBe("first");
  });

  it("DoD-10: a pop REMOVES the snapshot it returns — the depth falls by one each time", () => {
    pushChapterUndoSnapshot(BOOK_A, CHAPTER_1, "first");
    pushChapterUndoSnapshot(BOOK_A, CHAPTER_1, "second");

    expect(chapterUndoDepth(BOOK_A, CHAPTER_1)).toBe(2);
    popChapterUndoSnapshot(BOOK_A, CHAPTER_1);
    expect(chapterUndoDepth(BOOK_A, CHAPTER_1)).toBe(1);
    popChapterUndoSnapshot(BOOK_A, CHAPTER_1);
    expect(chapterUndoDepth(BOOK_A, CHAPTER_1)).toBe(0);
  });

  it("DoD-10: popping an empty stack returns nothing, and a pair never pushed to has depth 0", () => {
    // An undo control reads the depth to enable itself, so neither call may throw.
    expect(chapterUndoDepth(BOOK_A, CHAPTER_2)).toBe(0);
    expect(popChapterUndoSnapshot(BOOK_A, CHAPTER_2)).toBeNull();
    // ...and it stays empty and answerable after being drained.
    expect(chapterUndoDepth(BOOK_A, CHAPTER_2)).toBe(0);
    expect(popChapterUndoSnapshot(BOOK_A, CHAPTER_2)).toBeNull();
  });

  it("DoD-10: an EMPTY body is a legitimate snapshot — `\"\"` pops back, not nothing", () => {
    // `null` means "nothing to undo"; `""` means "the body was empty". They are not the
    // same answer, which is the reason the return type is nullable at all.
    pushChapterUndoSnapshot(BOOK_A, CHAPTER_1, "");

    expect(chapterUndoDepth(BOOK_A, CHAPTER_1)).toBe(1);
    expect(popChapterUndoSnapshot(BOOK_A, CHAPTER_1)).toBe("");
    expect(popChapterUndoSnapshot(BOOK_A, CHAPTER_1)).toBeNull();
  });

  it("DoD-10: exactly 20 pushes are all kept", () => {
    for (let i = 1; i <= MAX_SNAPSHOTS; i += 1) {
      pushChapterUndoSnapshot(BOOK_A, CHAPTER_1, `snapshot-${i}`);
    }

    expect(chapterUndoDepth(BOOK_A, CHAPTER_1)).toBe(MAX_SNAPSHOTS);
    expect(popChapterUndoSnapshot(BOOK_A, CHAPTER_1)).toBe(`snapshot-${MAX_SNAPSHOTS}`);
  });

  it("DoD-10: the 21st push drops the OLDEST snapshot, never the newest", () => {
    for (let i = 1; i <= MAX_SNAPSHOTS + 5; i += 1) {
      pushChapterUndoSnapshot(BOOK_A, CHAPTER_1, `snapshot-${i}`);
    }

    // The cap holds...
    expect(chapterUndoDepth(BOOK_A, CHAPTER_1)).toBe(MAX_SNAPSHOTS);

    // ...and what survived is the 20 most recent, most-recent-first.
    const popped: Array<string | null> = [];
    for (let i = 0; i < MAX_SNAPSHOTS; i += 1) {
      popped.push(popChapterUndoSnapshot(BOOK_A, CHAPTER_1));
    }
    const expected: string[] = [];
    for (let i = MAX_SNAPSHOTS + 5; i > 5; i -= 1) expected.push(`snapshot-${i}`);

    expect(popped).toEqual(expected);
    // The five oldest were dropped, so the stack is now empty.
    expect(popChapterUndoSnapshot(BOOK_A, CHAPTER_1)).toBeNull();
  });
});

/* ------------------------ DoD-11: independence, and nothing reaches localStorage */

describe("undo stacks are independent and hold nothing in localStorage (DoD-11)", () => {
  it("DoD-11: two chapters in the same book keep separate stacks", () => {
    pushChapterUndoSnapshot(BOOK_A, CHAPTER_1, "chapter one's body");
    pushChapterUndoSnapshot(BOOK_A, CHAPTER_2, "chapter two's body");

    // PRESENCE FIRST: both pairs really hold what they were given...
    expect(chapterUndoDepth(BOOK_A, CHAPTER_1)).toBe(1);
    expect(chapterUndoDepth(BOOK_A, CHAPTER_2)).toBe(1);
    expect(popChapterUndoSnapshot(BOOK_A, CHAPTER_1)).toBe("chapter one's body");
    expect(popChapterUndoSnapshot(BOOK_A, CHAPTER_2)).toBe("chapter two's body");

    // ...and neither ever saw the other's.
    expect(chapterUndoDepth(BOOK_A, CHAPTER_1)).toBe(0);
    expect(chapterUndoDepth(BOOK_A, CHAPTER_2)).toBe(0);
  });

  it("DoD-11: the same chapter id in a DIFFERENT book is a different stack", () => {
    pushChapterUndoSnapshot(BOOK_A, CHAPTER_1, "book A's body");
    pushChapterUndoSnapshot(BOOK_B, CHAPTER_1, "book B's body");

    // PRESENCE FIRST: both pairs hold their own snapshot.
    expect(chapterUndoDepth(BOOK_A, CHAPTER_1)).toBe(1);
    expect(chapterUndoDepth(BOOK_B, CHAPTER_1)).toBe(1);
    expect(popChapterUndoSnapshot(BOOK_A, CHAPTER_1)).toBe("book A's body");
    expect(popChapterUndoSnapshot(BOOK_B, CHAPTER_1)).toBe("book B's body");
  });

  it("DoD-11: draining one pair leaves the other pair's depth and contents intact", () => {
    pushChapterUndoSnapshot(BOOK_A, CHAPTER_1, "a-1");
    pushChapterUndoSnapshot(BOOK_A, CHAPTER_1, "a-2");
    pushChapterUndoSnapshot(BOOK_B, CHAPTER_2, "b-1");

    expect(chapterUndoDepth(BOOK_A, CHAPTER_1)).toBe(2);
    expect(chapterUndoDepth(BOOK_B, CHAPTER_2)).toBe(1);

    popChapterUndoSnapshot(BOOK_A, CHAPTER_1);
    popChapterUndoSnapshot(BOOK_A, CHAPTER_1);

    expect(chapterUndoDepth(BOOK_A, CHAPTER_1)).toBe(0);
    expect(chapterUndoDepth(BOOK_B, CHAPTER_2)).toBe(1);
    expect(popChapterUndoSnapshot(BOOK_B, CHAPTER_2)).toBe("b-1");
  });

  it("DoD-11: clearing a pair drops that pair's stack and leaves every other pair untouched", () => {
    pushChapterUndoSnapshot(BOOK_A, CHAPTER_1, "a-1");
    pushChapterUndoSnapshot(BOOK_A, CHAPTER_2, "a-2");
    pushChapterUndoSnapshot(BOOK_B, CHAPTER_1, "b-1");

    expect(chapterUndoDepth(BOOK_A, CHAPTER_1)).toBe(1);

    clearChapterUndo(BOOK_A, CHAPTER_1);

    expect(chapterUndoDepth(BOOK_A, CHAPTER_1)).toBe(0);
    expect(popChapterUndoSnapshot(BOOK_A, CHAPTER_1)).toBeNull();
    expect(popChapterUndoSnapshot(BOOK_A, CHAPTER_2)).toBe("a-2");
    expect(popChapterUndoSnapshot(BOOK_B, CHAPTER_1)).toBe("b-1");
  });

  it("DoD-11: clearing a pair that was never pushed to is a no-op", () => {
    pushChapterUndoSnapshot(BOOK_A, CHAPTER_1, "a-1");

    expect(chapterUndoDepth(BOOK_A, CHAPTER_1)).toBe(1);
    expect(() => clearChapterUndo(BOOK_B, CHAPTER_2)).not.toThrow();
    expect(chapterUndoDepth(BOOK_B, CHAPTER_2)).toBe(0);
    expect(chapterUndoDepth(BOOK_A, CHAPTER_1)).toBe(1);
  });

  it("DoD-11: a held snapshot reaches no localStorage key — the tier member is IN MEMORY (D6)", () => {
    const keysBefore = storageKeys();
    const SNAPSHOT = "a body distinctive enough to find anywhere it was written";

    pushChapterUndoSnapshot(BOOK_A, CHAPTER_1, SNAPSHOT);
    pushChapterUndoSnapshot(BOOK_B, CHAPTER_2, SNAPSHOT);

    // PRESENCE FIRST: the pushes really happened and the module really holds them, so
    // "nothing is in localStorage" cannot be satisfied by a module that holds nothing.
    expect(chapterUndoDepth(BOOK_A, CHAPTER_1)).toBe(1);
    expect(chapterUndoDepth(BOOK_B, CHAPTER_2)).toBe(1);

    // Only then: the store gained no key and holds the snapshot nowhere.
    expect(storageKeys()).toEqual(keysBefore);
    for (const value of storageValues()) {
      expect(value).not.toContain(SNAPSHOT);
    }

    // ...and the snapshots are still there to be popped, from memory alone.
    expect(popChapterUndoSnapshot(BOOK_A, CHAPTER_1)).toBe(SNAPSHOT);
    expect(popChapterUndoSnapshot(BOOK_B, CHAPTER_2)).toBe(SNAPSHOT);
  });

  it("DoD-11: a full 20-deep stack still writes nothing to localStorage", () => {
    const keysBefore = storageKeys();

    for (let i = 1; i <= MAX_SNAPSHOTS; i += 1) {
      pushChapterUndoSnapshot(BOOK_A, CHAPTER_1, `snapshot-${i}`);
    }

    expect(chapterUndoDepth(BOOK_A, CHAPTER_1)).toBe(MAX_SNAPSHOTS);
    expect(storageKeys()).toEqual(keysBefore);
  });
});
