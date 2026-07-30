/**
 * The content-subject registry — 013.codex / 013.subject-chat-canvas-wiring,
 * DoD-4 · DoD-5 · DoD-7 · DoD-8 · DoD-9 (the module-tier half; the wiring half —
 * DoD-1/2/3/4/6/10/11 — lives in `canvasWiring.test.tsx`).
 *
 * Bound to the frozen signatures in status.md -> `## Skeleton` (step 013):
 *   interface ContentSubject extends LoadedSubject { codexKind?: CodexKind | null }
 *   type ContentSubjectSource = () => ContentSubject
 *   type CanvasDraftApplier = (field: CanvasField, text: string) => void
 *   registerContentSubject(source: ContentSubjectSource, applyDraft?: CanvasDraftApplier): void
 *   unregisterContentSubject(source: ContentSubjectSource): void
 *   currentContentSubject(): ContentSubject | null
 *   dispatchCanvasFrame(bookId: string, frame: CanvasFrame): void
 *   types/chats: interface CanvasFrame { subject_kind; subject_id; field; text }
 *   work/restoreBuffer: restoreBufferKey(bookId, subjectKind, subjectId) / readBuffer / writeBuffer
 *
 * The air gap: every expected value comes from the step file's Definition of done and
 * Interface intent (and `context.md` -> "The shared-canvas write design", point 4),
 * never from code:
 *   - DoD-5: a frame whose subject MATCHES the registered target is handed to that
 *     target's apply-draft callback, with the frame's field and text;
 *   - DoD-7: a frame arriving with NO target registered goes into the restore buffer at
 *     `bookwriter.restore-buffer:<bookId>:codex-entry:<id>` — a list registration, which
 *     carries no callback, is "no target" for this purpose;
 *   - DoD-8: a frame whose subject id does not match the registered target falls back to
 *     the buffer and does NOT reach the open entry;
 *   - DoD-9: register / unregister, identity-guarded — a late unmount from a superseded
 *     page must not clear a newer page's registration;
 *   - DoD-4: with nothing registered there is no subject at all;
 *   - the blank-entry drop rule (Interface intent): a frame for a blank entry (null
 *     subject id) with no registered target is dropped — no key to buffer it under.
 *
 * A pure module in the `restoreBuffer.ts` / `activeChat.ts` tier: no class, no MobX, no
 * router, no `renderWithProviders`. Its state is MODULE-LEVEL, so every test resets the
 * registry through the frozen API (register a sentinel, then unregister it — the newest
 * registration wins outright, so the sentinel is always clearable). `tests/setup.ts`
 * runs `localStorage.clear()` in `afterEach`, so each case starts on a clean store.
 * `globals: false`: every primitive is imported explicitly.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { CanvasFrame } from "../../src/types/chats";
import {
  RESTORE_BUFFER_KEY_PREFIX,
  readBuffer,
  restoreBufferKey,
} from "../../src/work/restoreBuffer";
import type { ContentSubject, ContentSubjectSource } from "../../src/work/contentSubject";
import {
  currentContentSubject,
  dispatchCanvasFrame,
  registerContentSubject,
  unregisterContentSubject,
} from "../../src/work/contentSubject";

/* ------------------------------------------------------------------ fixtures */

const BOOK_ID = "bk-1";
const ENTRY_ID = "ce-1";
const OTHER_ENTRY_ID = "ce-other-7";

/** The assistant's drafted body — the distinctive word is "lantern". */
const CANVAS_BODY = "A sellsword carrying a shuttered lantern.";
/** The assistant's drafted name. */
const CANVAS_NAME = "Aria of the Reach";

/** A canvas frame for the open character entry's body, unless overridden. */
function makeFrame(overrides: Partial<CanvasFrame> = {}): CanvasFrame {
  return {
    subject_kind: "codex-entry",
    subject_id: ENTRY_ID,
    field: "body",
    text: CANVAS_BODY,
    ...overrides,
  };
}

/** The subject an open (existing) codex entry page declares. */
function entrySubject(
  entityId: string = ENTRY_ID,
  codexKind: ContentSubject["codexKind"] = "character",
): ContentSubject {
  return { kind: "codex-entry", entityId, codexArchived: false, codexKind };
}

/** The buffer key the spec names for a codex entry's fallback write. */
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
 * Clear the module-level registration through the frozen API alone: the newest
 * registration wins outright, so a sentinel registration can always be unregistered
 * by its own identity, leaving nothing registered.
 */
const RESET_SOURCE: ContentSubjectSource = () => ({ kind: "chats" });
function resetRegistry(): void {
  // Harness hygiene only — never an assertion, so a registry that cannot yet register
  // must not turn an unrelated case red. Every case that depends on "nothing is
  // registered" asserts it for itself.
  try {
    registerContentSubject(RESET_SOURCE);
    unregisterContentSubject(RESET_SOURCE);
  } catch {
    /* the registry is unavailable; the cases below will say so themselves */
  }
}

beforeEach(resetRegistry);
afterEach(resetRegistry);

/* ------------------------------------------- DoD-9 / DoD-4: register + unregister */

describe("registering and unregistering the content subject (DoD-9)", () => {
  it("DoD-4: with nothing registered there is no current subject at all", () => {
    expect(currentContentSubject()).toBeNull();
  });

  it("DoD-9: a registration makes the page's subject the current one; unregistering clears it", () => {
    const source: ContentSubjectSource = () => entrySubject();

    registerContentSubject(source);
    expect(currentContentSubject()).toEqual(entrySubject());

    unregisterContentSubject(source);
    expect(currentContentSubject()).toBeNull();
  });

  it("DoD-9: the newest registration wins outright", () => {
    const first: ContentSubjectSource = () => entrySubject(ENTRY_ID);
    const second: ContentSubjectSource = () => ({ kind: "characters" });

    registerContentSubject(first);
    registerContentSubject(second);

    expect(currentContentSubject()).toEqual({ kind: "characters" });
  });

  it("DoD-9: a LATE unmount from a superseded page does not clear the newer page's registration", () => {
    // Two pages briefly overlap during a route transition: the new page mounts and
    // registers, then the OLD page's cleanup finally runs.
    const oldPage: ContentSubjectSource = () => entrySubject(ENTRY_ID);
    const newPage: ContentSubjectSource = () => ({ kind: "locations" });

    registerContentSubject(oldPage);
    registerContentSubject(newPage);

    unregisterContentSubject(oldPage); // the late cleanup — identity-guarded, a no-op

    expect(currentContentSubject()).toEqual({ kind: "locations" });

    // ...and the page that actually owns the registration can still clear it.
    unregisterContentSubject(newPage);
    expect(currentContentSubject()).toBeNull();
  });

  it("DoD-1: the subject is read at CALL time, so a value unknown at mount is still carried", () => {
    // The registration happens in a mount effect, before an entry's load resolves; the
    // codex kind only becomes known afterwards. A source is therefore re-read on every
    // read, never snapshotted at registration.
    let loadedKind: ContentSubject["codexKind"] = null;
    const source: ContentSubjectSource = () => ({
      kind: "codex-entry",
      entityId: ENTRY_ID,
      codexKind: loadedKind,
    });

    registerContentSubject(source);
    expect(currentContentSubject()?.codexKind ?? null).toBeNull();

    loadedKind = "fact"; // the entry's load resolves

    expect(currentContentSubject()?.codexKind).toBe("fact");
  });
});

/* ------------------------------------ DoD-5: a matching frame reaches the target */

describe("a canvas frame whose subject matches is handed to the registered target (DoD-5)", () => {
  it("DoD-5 (US-086.AC-1 / US-087.AC-1): the frame's field and text reach the apply-draft callback", () => {
    const applyDraft = vi.fn();
    registerContentSubject(() => entrySubject(), applyDraft);

    dispatchCanvasFrame(BOOK_ID, makeFrame({ field: "body", text: CANVAS_BODY }));

    expect(applyDraft).toHaveBeenCalledTimes(1);
    expect(applyDraft).toHaveBeenCalledWith("body", CANVAS_BODY, "replace");
  });

  it("DoD-5: a name frame targets the name field, not the body", () => {
    const applyDraft = vi.fn();
    registerContentSubject(() => entrySubject(), applyDraft);

    dispatchCanvasFrame(BOOK_ID, makeFrame({ field: "name", text: CANVAS_NAME }));

    expect(applyDraft).toHaveBeenCalledWith("name", CANVAS_NAME, "replace");
  });

  it("DoD-5: a dispatched frame goes to the target INSTEAD of the buffer, not as well as", () => {
    const applyDraft = vi.fn();
    registerContentSubject(() => entrySubject(), applyDraft);

    dispatchCanvasFrame(BOOK_ID, makeFrame());

    expect(applyDraft).toHaveBeenCalledTimes(1);
    // The fallback is the "otherwise" branch — the dispatcher itself buffered nothing.
    expect(bufferKeys()).toEqual([]);
  });

  it("DoD-5 (UC-076): a blank entry's target matches a frame with a null subject id", () => {
    const applyDraft = vi.fn();
    // A blank entry has no row yet, so its subject carries no entityId.
    registerContentSubject(() => ({ kind: "codex-entry", codexKind: "location" }), applyDraft);

    dispatchCanvasFrame(BOOK_ID, makeFrame({ subject_id: null, text: CANVAS_BODY }));

    expect(applyDraft).toHaveBeenCalledWith("body", CANVAS_BODY, "replace");
  });
});

/* -------------------------- DoD-7: no target registered => the restore buffer */

describe("a frame arriving with no target registered is buffered (DoD-7)", () => {
  it("DoD-7 (US-107.AC-1): the text lands at bookwriter.restore-buffer:<bookId>:codex-entry:<id>", () => {
    // The author navigated away mid-turn: nothing is registered.
    dispatchCanvasFrame(BOOK_ID, makeFrame({ subject_id: ENTRY_ID, text: CANVAS_BODY }));

    const expectedKey = `${RESTORE_BUFFER_KEY_PREFIX}:${BOOK_ID}:codex-entry:${ENTRY_ID}`;
    // The literal key the DoD names, and the key the existing buffer path builds.
    expect(entryBufferKey()).toBe(expectedKey);
    expect(readBuffer(expectedKey)?.draft).toBe(CANVAS_BODY);
  });

  it("DoD-7: a list registration carries no canvas target, so a codex frame is buffered", () => {
    // A list page registers a kind-only subject with no apply-draft callback.
    registerContentSubject(() => ({ kind: "characters" }));

    dispatchCanvasFrame(BOOK_ID, makeFrame({ subject_id: ENTRY_ID, text: CANVAS_BODY }));

    expect(readBuffer(entryBufferKey())?.draft).toBe(CANVAS_BODY);
  });

  it("DoD-7: the buffer write is scoped to the frame's book and entry only", () => {
    dispatchCanvasFrame(BOOK_ID, makeFrame({ subject_id: ENTRY_ID, text: CANVAS_BODY }));

    expect(bufferKeys()).toEqual([entryBufferKey(ENTRY_ID)]);
  });

  it("DoD-7 (Interface intent): a frame for a BLANK entry with no target is dropped", () => {
    // A null subject id has no key to buffer under and no row to return to.
    expect(() =>
      dispatchCanvasFrame(BOOK_ID, makeFrame({ subject_id: null, text: CANVAS_BODY })),
    ).not.toThrow();

    expect(bufferKeys()).toEqual([]);
  });
});

/* ------------------- DoD-8: a non-matching frame never touches the open entry */

describe("a frame for another subject falls back to the buffer (DoD-8)", () => {
  it("DoD-8: a different entry id is buffered under ITS OWN key and never applied to the open entry", () => {
    const applyDraft = vi.fn();
    registerContentSubject(() => entrySubject(ENTRY_ID), applyDraft);

    dispatchCanvasFrame(
      BOOK_ID,
      makeFrame({ subject_id: OTHER_ENTRY_ID, field: "body", text: CANVAS_BODY }),
    );

    // The open entry is untouched...
    expect(applyDraft).not.toHaveBeenCalled();
    expect(readBuffer(entryBufferKey(ENTRY_ID))).toBeNull();
    // ...and the draft is held for the entry it was actually written for.
    expect(readBuffer(entryBufferKey(OTHER_ENTRY_ID))?.draft).toBe(CANVAS_BODY);
  });

  it("DoD-8: a frame for a blank entry does not overwrite an OPEN existing entry", () => {
    const applyDraft = vi.fn();
    registerContentSubject(() => entrySubject(ENTRY_ID), applyDraft);

    dispatchCanvasFrame(BOOK_ID, makeFrame({ subject_id: null, text: CANVAS_BODY }));

    expect(applyDraft).not.toHaveBeenCalled();
    expect(readBuffer(entryBufferKey(ENTRY_ID))).toBeNull();
  });

  it("DoD-8: a frame does not reach a target registered under a different subject kind", () => {
    const applyDraft = vi.fn();
    // A subject of another kind that happens to share the frame's entity id.
    registerContentSubject(() => ({ kind: "chapter", entityId: ENTRY_ID }), applyDraft);

    dispatchCanvasFrame(BOOK_ID, makeFrame({ subject_id: ENTRY_ID, text: CANVAS_BODY }));

    expect(applyDraft).not.toHaveBeenCalled();
    expect(readBuffer(entryBufferKey(ENTRY_ID))?.draft).toBe(CANVAS_BODY);
  });

  it("DoD-8: an unregistered previous target receives nothing, even for its own entry", () => {
    const applyDraft = vi.fn();
    const source: ContentSubjectSource = () => entrySubject(ENTRY_ID);
    registerContentSubject(source, applyDraft);
    unregisterContentSubject(source);

    dispatchCanvasFrame(BOOK_ID, makeFrame({ subject_id: ENTRY_ID, text: CANVAS_BODY }));

    expect(applyDraft).not.toHaveBeenCalled();
    expect(readBuffer(entryBufferKey(ENTRY_ID))?.draft).toBe(CANVAS_BODY);
  });
});
