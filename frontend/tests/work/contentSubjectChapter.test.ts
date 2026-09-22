/**
 * The content-subject registry learns about chapters —
 * 015.chapter-writing-free-mode / 011.work-module-tier-chapter,
 * DoD-4 · DoD-5 · DoD-6 · DoD-7 · DoD-8 · DoD-9 · DoD-12.
 *
 * (DoD-1/2/3 — the editability half — live in `subject.test.ts`; DoD-10/11 — the undo
 * stack — live in `chapterUndo.test.ts`; DoD-13 is `[manual/live]` and has no test.)
 *
 * Bound to the frozen signatures in status.md -> `## Skeleton` (015 step 011):
 *   types/chats: type CanvasOp = "replace" | "append" | "replace_selection"
 *   types/chats: interface CanvasFrame { subject_kind; subject_id; field; text; op? }
 *   types/chats: type CanvasField = "name" | "body"          // UNCHANGED, deliberately
 *   type CanvasDraftApplier = (field: CanvasField, text: string, op?: CanvasOp) => void
 *   registerContentSubject(source, applyDraft?): void
 *   unregisterContentSubject(source): void        // also clears the selection
 *   dispatchCanvasFrame(bookId: string, frame: CanvasFrame): void
 *   setContentSelection(source: ContentSubjectSource, selection: string | null): void
 *   currentContentSelection(): string | null
 *   clearContentSelection(source: ContentSubjectSource): void
 *   work/restoreBuffer: restoreBufferKey(bookId, subjectKind, subjectId) /
 *                       readBuffer(key) / writeBuffer(key, draft, baseVersion)
 *
 * The air gap: every expected value comes from the step file's Definition of done and
 * Interface intent, and from `context.md` -> D17 / D18 — never from code:
 *   - DoD-4: a chapter frame with a MATCHING registered target reaches that target's
 *     applier with its text, its FIELD and its OPERATION;
 *   - DoD-5: a frame whose subject does not match the registered target is not
 *     delivered to it;
 *   - DoD-6: a codex frame behaves exactly as it does today — delivered to a matching
 *     target, buffered under the `"codex-entry"` key when there is none — and a
 *     two-parameter applier still satisfies the registry (D17: the type widens by one
 *     OPTIONAL parameter precisely so `CodexEntryPage` needs no edit);
 *   - DoD-7 (D18): a chapter frame with the REPLACE operation and no registered target
 *     is written to the restore buffer under the CHAPTER's key, inheriting the base
 *     version already at that key and the empty string when there is none;
 *   - DoD-8 (D18): a chapter frame with the APPEND or REPLACE-SELECTION operation and no
 *     registered target is dropped — nothing is written to any buffer key, because both
 *     are relative to a draft this module does not have;
 *   - DoD-9: the selection registry inherits the subject registry's ownership discipline
 *     verbatim (`frontend-work-drafts.md`, quoted in `011.context.md`) — newest wins, a
 *     clear only lands from the still-registered owner, and unregistering the subject
 *     clears the selection too;
 *   - DoD-12: the frame DTO carries the operation with the same three values and the
 *     same REPLACE DEFAULT as the backend model (a `.d.ts` carries no runtime default,
 *     so an omitted `op` MEANS `"replace"`), and `CanvasField` still admits exactly
 *     `"name"` and `"body"` (D17 — no `"text"` member on either side of the wire).
 *     It is a TYPE-LEVEL claim: the literals below are gated by `npm run test:types`,
 *     and nothing is imported as a runtime value from a declaration file.
 *
 * A pure module in the `restoreBuffer.ts` / `activeChat.ts` tier: no rendering, no
 * `renderWithProviders`, no api mocks. `restoreBuffer.ts` is used FOR REAL (jsdom
 * provides `localStorage`), so DoD-7 / DoD-8 assert against real buffer state rather
 * than a mock's call log; `tests/setup.ts` clears `localStorage` after every test.
 * The registry's state is MODULE-LEVEL, so every case resets it through the frozen API.
 * `globals: false`: every primitive is imported explicitly.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { CanvasField, CanvasFrame, CanvasOp } from "../../src/types/chats";
import {
  RESTORE_BUFFER_KEY_PREFIX,
  readBuffer,
  restoreBufferKey,
  writeBuffer,
} from "../../src/work/restoreBuffer";
import type {
  CanvasDraftApplier,
  ContentSubject,
  ContentSubjectSource,
} from "../../src/work/contentSubject";
import {
  clearContentSelection,
  currentContentSelection,
  dispatchCanvasFrame,
  registerContentSubject,
  setContentSelection,
  unregisterContentSubject,
} from "../../src/work/contentSubject";

/* ------------------------------------------------------------------ fixtures */

const BOOK_ID = "bk-1";
const OTHER_BOOK_ID = "bk-2";
const CHAPTER_ID = "ch-1";
const OTHER_CHAPTER_ID = "ch-other-7";
const ENTRY_ID = "ce-1";

/** The assistant's drafted chapter body — the distinctive word is "harbour". */
const CHAPTER_BODY = "The harbour was empty by the time she reached it.";
/** A second, distinguishable draft. */
const OTHER_TEXT = "A different sentence entirely.";
/** The assistant's drafted codex body. */
const CODEX_BODY = "A sellsword carrying a shuttered lantern.";

/** A canvas frame for the open chapter's body, unless overridden. */
function chapterFrame(overrides: Partial<CanvasFrame> = {}): CanvasFrame {
  return {
    subject_kind: "chapter",
    subject_id: CHAPTER_ID,
    field: "body",
    text: CHAPTER_BODY,
    ...overrides,
  };
}

/** A canvas frame for an open codex entry's body, unless overridden. */
function codexFrame(overrides: Partial<CanvasFrame> = {}): CanvasFrame {
  return {
    subject_kind: "codex-entry",
    subject_id: ENTRY_ID,
    field: "body",
    text: CODEX_BODY,
    ...overrides,
  };
}

/** The subject the open chapter page declares. */
function chapterSubject(entityId: string = CHAPTER_ID): ContentSubject {
  return { kind: "chapter", entityId };
}

/** The subject an open codex entry page declares. */
function entrySubject(entityId: string = ENTRY_ID): ContentSubject {
  return { kind: "codex-entry", entityId, codexArchived: false, codexKind: "character" };
}

/** The buffer key D18 names for a chapter's fallback write. */
function chapterBufferKey(bookId: string = BOOK_ID, chapterId: string = CHAPTER_ID): string {
  return restoreBufferKey(bookId, "chapter", chapterId);
}

/** The buffer key the codex fallback has always used. */
function entryBufferKey(entryId: string = ENTRY_ID): string {
  return restoreBufferKey(BOOK_ID, "codex-entry", entryId);
}

/** Every restore-buffer key currently in storage (the module's own prefix only). */
function bufferKeys(): string[] {
  const keys: string[] = [];
  for (let i = 0; i < localStorage.length; i += 1) {
    const key = localStorage.key(i);
    if (key !== null && key.startsWith(RESTORE_BUFFER_KEY_PREFIX)) keys.push(key);
  }
  return keys;
}

/**
 * Clear the module-level registration and selection through the frozen API alone: the
 * newest registration wins outright, so a sentinel can always clear itself. Harness
 * hygiene only — never an assertion, so a registry that cannot yet register or select
 * must not turn an unrelated case red. Every case that depends on "nothing is
 * registered / nothing is selected" asserts it for itself.
 */
const RESET_SOURCE: ContentSubjectSource = () => ({ kind: "chats" });
function quiet(run: () => void): void {
  try {
    run();
  } catch {
    /* the registry is unavailable; the cases below will say so themselves */
  }
}
function resetRegistry(): void {
  quiet(() => registerContentSubject(RESET_SOURCE));
  quiet(() => clearContentSelection(RESET_SOURCE));
  quiet(() => unregisterContentSubject(RESET_SOURCE));
}

beforeEach(resetRegistry);
afterEach(resetRegistry);

/* ---------------------------------- DoD-4: a matching chapter frame reaches the page */

describe("a chapter frame whose subject matches is handed to the registered target (DoD-4)", () => {
  it("DoD-4: the frame's field, text and operation all reach the apply-draft callback", () => {
    const applyDraft = vi.fn();
    registerContentSubject(() => chapterSubject(), applyDraft);

    dispatchCanvasFrame(
      BOOK_ID,
      chapterFrame({ field: "body", text: CHAPTER_BODY, op: "replace" }),
    );

    expect(applyDraft).toHaveBeenCalledTimes(1);
    expect(applyDraft).toHaveBeenCalledWith("body", CHAPTER_BODY, "replace");
  });

  it("DoD-4: an APPEND frame reaches the target carrying its append operation", () => {
    const applyDraft = vi.fn();
    registerContentSubject(() => chapterSubject(), applyDraft);

    dispatchCanvasFrame(BOOK_ID, chapterFrame({ text: CHAPTER_BODY, op: "append" }));

    expect(applyDraft).toHaveBeenCalledWith("body", CHAPTER_BODY, "append");
  });

  it("DoD-4: a REPLACE-SELECTION frame reaches the target carrying its own operation", () => {
    const applyDraft = vi.fn();
    registerContentSubject(() => chapterSubject(), applyDraft);

    dispatchCanvasFrame(
      BOOK_ID,
      chapterFrame({ text: CHAPTER_BODY, op: "replace_selection" }),
    );

    expect(applyDraft).toHaveBeenCalledWith("body", CHAPTER_BODY, "replace_selection");
  });

  it("DoD-4: a delivered frame goes to the target INSTEAD of the buffer, not as well as", () => {
    const applyDraft = vi.fn();
    registerContentSubject(() => chapterSubject(), applyDraft);

    dispatchCanvasFrame(BOOK_ID, chapterFrame({ op: "replace" }));

    expect(applyDraft).toHaveBeenCalledTimes(1);
    expect(bufferKeys()).toEqual([]);
  });
});

/* ------------------------ DoD-5: a frame for another subject never reaches the target */

describe("a frame whose subject does not match the registered target is not delivered (DoD-5)", () => {
  it("DoD-5: another chapter's id does not reach the open chapter's applier", () => {
    const applyDraft = vi.fn();
    registerContentSubject(() => chapterSubject(CHAPTER_ID), applyDraft);

    dispatchCanvasFrame(
      BOOK_ID,
      chapterFrame({ subject_id: OTHER_CHAPTER_ID, text: OTHER_TEXT, op: "replace" }),
    );

    expect(applyDraft).not.toHaveBeenCalled();
  });

  it("DoD-5: a codex frame does not reach a registered CHAPTER target", () => {
    const applyDraft = vi.fn();
    // A subject of another kind that happens to share the frame's entity id.
    registerContentSubject(() => chapterSubject(ENTRY_ID), applyDraft);

    dispatchCanvasFrame(BOOK_ID, codexFrame({ subject_id: ENTRY_ID }));

    expect(applyDraft).not.toHaveBeenCalled();
  });

  it("DoD-5: an unregistered previous target receives nothing, even for its own chapter", () => {
    const applyDraft = vi.fn();
    const source: ContentSubjectSource = () => chapterSubject(CHAPTER_ID);
    registerContentSubject(source, applyDraft);
    unregisterContentSubject(source);

    dispatchCanvasFrame(BOOK_ID, chapterFrame({ op: "replace" }));

    expect(applyDraft).not.toHaveBeenCalled();
  });
});

/* ------------------------------------------- DoD-6: the codex path pays nothing (D17) */

describe("a codex frame still behaves exactly as it does today (DoD-6)", () => {
  it("DoD-6: a codex frame reaches a matching registered target with its field and text", () => {
    const applyDraft = vi.fn();
    registerContentSubject(() => entrySubject(), applyDraft);

    dispatchCanvasFrame(BOOK_ID, codexFrame({ field: "body", text: CODEX_BODY }));

    expect(applyDraft).toHaveBeenCalledTimes(1);
    // The operation is resolved to the default before it is passed on (D17).
    expect(applyDraft).toHaveBeenCalledWith("body", CODEX_BODY, "replace");
  });

  it("DoD-6: with no target registered, a codex frame is still buffered under the codex-entry key", () => {
    dispatchCanvasFrame(BOOK_ID, codexFrame({ subject_id: ENTRY_ID, text: CODEX_BODY }));

    expect(readBuffer(entryBufferKey())?.draft).toBe(CODEX_BODY);
    expect(bufferKeys()).toEqual([entryBufferKey()]);
  });

  it("DoD-6: an applier taking only TWO parameters still satisfies the registry", () => {
    // The registry's callback type widened by one OPTIONAL parameter precisely so a
    // two-parameter implementation stays assignable (D17) — this is what leaves
    // `CodexEntryPage`'s existing applier valid and unedited. The assignment below is
    // the claim; `npm run test:types` is its gate. The dispatch proves it also works.
    const received: Array<[CanvasField, string]> = [];
    const twoParameterApplier: CanvasDraftApplier = (field, text) => {
      received.push([field, text]);
    };

    registerContentSubject(() => entrySubject(), twoParameterApplier);
    dispatchCanvasFrame(BOOK_ID, codexFrame({ field: "name", text: "Aria of the Reach" }));

    expect(received).toEqual([["name", "Aria of the Reach"]]);
  });
});

/* ---------------- DoD-7: a targetless REPLACE chapter frame goes to the chapter's key */

describe("a targetless chapter frame with the replace operation is buffered (DoD-7, D18)", () => {
  it("DoD-7: the text lands under the CHAPTER's own restore-buffer key, not the codex one", () => {
    // The author navigated away mid-turn: nothing is registered.
    dispatchCanvasFrame(BOOK_ID, chapterFrame({ text: CHAPTER_BODY, op: "replace" }));

    expect(readBuffer(chapterBufferKey())?.draft).toBe(CHAPTER_BODY);
    expect(bufferKeys()).toEqual([chapterBufferKey()]);
  });

  it("DoD-7: with no base version already at that key, the empty string is inherited", () => {
    dispatchCanvasFrame(BOOK_ID, chapterFrame({ text: CHAPTER_BODY, op: "replace" }));

    expect(readBuffer(chapterBufferKey())?.baseVersion).toBe("");
  });

  it("DoD-7: a base version already sitting at that key is inherited, not overwritten", () => {
    // The page buffered a draft against version 4 before it unmounted.
    writeBuffer(chapterBufferKey(), "the author's earlier draft", 4);

    dispatchCanvasFrame(BOOK_ID, chapterFrame({ text: CHAPTER_BODY, op: "replace" }));

    const buffered = readBuffer(chapterBufferKey());
    expect(buffered?.draft).toBe(CHAPTER_BODY);
    expect(buffered?.baseVersion).toBe(4);
  });

  it("DoD-7: a frame with NO operation is buffered too — an omitted operation means replace", () => {
    dispatchCanvasFrame(BOOK_ID, chapterFrame({ text: CHAPTER_BODY }));

    expect(readBuffer(chapterBufferKey())?.draft).toBe(CHAPTER_BODY);
  });

  it("DoD-7: the buffer write is scoped to the frame's own book and chapter", () => {
    dispatchCanvasFrame(
      BOOK_ID,
      chapterFrame({ subject_id: OTHER_CHAPTER_ID, text: CHAPTER_BODY, op: "replace" }),
    );

    expect(bufferKeys()).toEqual([chapterBufferKey(BOOK_ID, OTHER_CHAPTER_ID)]);
    expect(readBuffer(chapterBufferKey(OTHER_BOOK_ID, OTHER_CHAPTER_ID))).toBeNull();
  });

  it("DoD-7: a list registration carries no canvas target, so a chapter frame is buffered", () => {
    // A list page registers a kind-only subject with no apply-draft callback.
    registerContentSubject(() => ({ kind: "chapters" }));

    dispatchCanvasFrame(BOOK_ID, chapterFrame({ text: CHAPTER_BODY, op: "replace" }));

    expect(readBuffer(chapterBufferKey())?.draft).toBe(CHAPTER_BODY);
  });
});

/* --------- DoD-8: a targetless RELATIVE chapter frame is dropped, not buffered (D18) */

describe("a targetless chapter frame with a relative operation is dropped (DoD-8, D18)", () => {
  it("DoD-8: an APPEND frame with no registered target writes to no buffer key at all", () => {
    expect(() =>
      dispatchCanvasFrame(BOOK_ID, chapterFrame({ text: CHAPTER_BODY, op: "append" })),
    ).not.toThrow();

    // Not the chapter's key, not the codex key, not any other key.
    expect(bufferKeys()).toEqual([]);
    expect(readBuffer(chapterBufferKey())).toBeNull();
  });

  it("DoD-8: a REPLACE-SELECTION frame with no registered target writes to no buffer key at all", () => {
    expect(() =>
      dispatchCanvasFrame(
        BOOK_ID,
        chapterFrame({ text: CHAPTER_BODY, op: "replace_selection" }),
      ),
    ).not.toThrow();

    expect(bufferKeys()).toEqual([]);
    expect(readBuffer(chapterBufferKey())).toBeNull();
  });

  it("DoD-8: a dropped relative frame leaves a draft already in the buffer untouched", () => {
    writeBuffer(chapterBufferKey(), "the author's earlier draft", 4);

    dispatchCanvasFrame(BOOK_ID, chapterFrame({ text: CHAPTER_BODY, op: "append" }));
    dispatchCanvasFrame(
      BOOK_ID,
      chapterFrame({ text: OTHER_TEXT, op: "replace_selection" }),
    );

    const buffered = readBuffer(chapterBufferKey());
    expect(buffered?.draft).toBe("the author's earlier draft");
    expect(buffered?.baseVersion).toBe(4);
    expect(bufferKeys()).toEqual([chapterBufferKey()]);
  });

  it("DoD-8: a relative frame IS delivered when a target is registered — only the targetless case drops", () => {
    const applyDraft = vi.fn();
    registerContentSubject(() => chapterSubject(), applyDraft);

    dispatchCanvasFrame(BOOK_ID, chapterFrame({ text: CHAPTER_BODY, op: "append" }));

    expect(applyDraft).toHaveBeenCalledWith("body", CHAPTER_BODY, "append");
    expect(bufferKeys()).toEqual([]);
  });
});

/* ------------------------------------------------- DoD-9: the selection registry */

describe("the selection registry (DoD-9)", () => {
  const SELECTION = "she reached it";
  const OTHER_SELECTION = "the harbour was empty";

  it("DoD-9: with nothing set there is no current selection", () => {
    expect(currentContentSelection()).toBeNull();
  });

  it("DoD-9: the registry returns what the current owner set", () => {
    const owner: ContentSubjectSource = () => chapterSubject();
    registerContentSubject(owner);

    setContentSelection(owner, SELECTION);

    expect(currentContentSelection()).toBe(SELECTION);
  });

  it("DoD-9: a later set from the same owner replaces the earlier one", () => {
    const owner: ContentSubjectSource = () => chapterSubject();
    registerContentSubject(owner);

    setContentSelection(owner, SELECTION);
    setContentSelection(owner, OTHER_SELECTION);

    expect(currentContentSelection()).toBe(OTHER_SELECTION);
  });

  it("DoD-9: the owner clearing its own selection leaves nothing selected", () => {
    const owner: ContentSubjectSource = () => chapterSubject();
    registerContentSubject(owner);
    setContentSelection(owner, SELECTION);

    clearContentSelection(owner);

    expect(currentContentSelection()).toBeNull();
  });

  it("DoD-9: setting null is how the page reports that nothing is selected", () => {
    const owner: ContentSubjectSource = () => chapterSubject();
    registerContentSubject(owner);
    setContentSelection(owner, SELECTION);

    setContentSelection(owner, null);

    expect(currentContentSelection()).toBeNull();
  });

  it("DoD-9: the newest setter wins outright", () => {
    const oldPage: ContentSubjectSource = () => chapterSubject(CHAPTER_ID);
    const newPage: ContentSubjectSource = () => chapterSubject(OTHER_CHAPTER_ID);

    registerContentSubject(oldPage);
    setContentSelection(oldPage, SELECTION);

    registerContentSubject(newPage);
    setContentSelection(newPage, OTHER_SELECTION);

    expect(currentContentSelection()).toBe(OTHER_SELECTION);
  });

  it("DoD-9: a clear from a SUPERSEDED owner is a no-op — a selection setter fires constantly", () => {
    const oldPage: ContentSubjectSource = () => chapterSubject(CHAPTER_ID);
    const newPage: ContentSubjectSource = () => chapterSubject(OTHER_CHAPTER_ID);

    registerContentSubject(oldPage);
    setContentSelection(oldPage, SELECTION);
    registerContentSubject(newPage);
    setContentSelection(newPage, OTHER_SELECTION);

    clearContentSelection(oldPage); // the superseded page's late cleanup

    expect(currentContentSelection()).toBe(OTHER_SELECTION);

    // ...and the page that actually owns the selection can still clear it.
    clearContentSelection(newPage);
    expect(currentContentSelection()).toBeNull();
  });

  it("DoD-9: unregistering the subject clears the selection too", () => {
    const owner: ContentSubjectSource = () => chapterSubject();
    registerContentSubject(owner);
    setContentSelection(owner, SELECTION);
    // The selection is really held before the unmount runs.
    expect(currentContentSelection()).toBe(SELECTION);

    unregisterContentSubject(owner);

    expect(currentContentSelection()).toBeNull();
  });

  it("DoD-9: a LATE unregister from a superseded page does not clear the newer page's selection", () => {
    const oldPage: ContentSubjectSource = () => chapterSubject(CHAPTER_ID);
    const newPage: ContentSubjectSource = () => chapterSubject(OTHER_CHAPTER_ID);

    registerContentSubject(oldPage);
    registerContentSubject(newPage);
    setContentSelection(newPage, OTHER_SELECTION);

    unregisterContentSubject(oldPage); // identity-guarded, a no-op

    expect(currentContentSelection()).toBe(OTHER_SELECTION);
  });

  it("DoD-9: an empty selection string is stored as given, not turned into nothing", () => {
    const owner: ContentSubjectSource = () => chapterSubject();
    registerContentSubject(owner);

    setContentSelection(owner, "");

    expect(currentContentSelection()).toBe("");
  });
});

/* ------------------------------------------- DoD-12: the frame DTO, at the type level */

describe("the frontend CanvasFrame DTO mirrors the backend model (DoD-12)", () => {
  it("DoD-12: a frame literal compiles for each of the three operations, and with none at all", () => {
    // TYPE-LEVEL: the gate on these four literals is `npm run test:types`. Nothing is
    // imported as a runtime value from a declaration file.
    const replaceFrame: CanvasFrame = {
      subject_kind: "chapter",
      subject_id: CHAPTER_ID,
      field: "body",
      text: CHAPTER_BODY,
      op: "replace",
    };
    const appendFrame: CanvasFrame = { ...replaceFrame, op: "append" };
    const replaceSelectionFrame: CanvasFrame = { ...replaceFrame, op: "replace_selection" };
    const defaultedFrame: CanvasFrame = {
      subject_kind: "chapter",
      subject_id: CHAPTER_ID,
      field: "body",
      text: CHAPTER_BODY,
    };

    expect([replaceFrame.op, appendFrame.op, replaceSelectionFrame.op]).toEqual([
      "replace",
      "append",
      "replace_selection",
    ]);
    // A `.d.ts` carries no runtime default, so the field is simply absent...
    expect(defaultedFrame.op).toBeUndefined();
  });

  it("DoD-12: an omitted operation MEANS replace — the same default the backend model carries", () => {
    // ...and the default is applied where the frame is read.
    const applyDraft = vi.fn();
    registerContentSubject(() => chapterSubject(), applyDraft);

    dispatchCanvasFrame(BOOK_ID, chapterFrame({ text: CHAPTER_BODY }));

    expect(applyDraft).toHaveBeenCalledWith("body", CHAPTER_BODY, "replace");
  });

  it("DoD-12: the operation admits exactly the backend model's three values", () => {
    const ops: CanvasOp[] = ["replace", "append", "replace_selection"];
    // @ts-expect-error a fourth operation does not exist on either side of the wire
    const notAnOp: CanvasOp = "prepend";

    expect(ops).toHaveLength(3);
    expect(notAnOp).toBe("prepend");
  });

  it("DoD-12: CanvasField still admits exactly `name` and `body` — no `text` member (D17)", () => {
    const fields: CanvasField[] = ["name", "body"];
    // @ts-expect-error a chapter's body IS the `"body"` field; `"text"` was never added
    const notAField: CanvasField = "text";

    expect(fields).toEqual(["name", "body"]);
    expect(notAField).toBe("text");
  });
});
