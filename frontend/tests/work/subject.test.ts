/**
 * Content-pane subject model — 010.working-page / 004.content-pane-subject-and-buffer,
 * DoD-1 · DoD-2 · DoD-3 · DoD-4 (subject/pane-target half).
 *
 * Bound to the frozen signatures in status.md -> `## Skeleton` (step 004):
 *   type SubjectKind = "book-state" | "chapters" | "chapter" | "characters"
 *                    | "locations" | "facts" | "codex-entry" | "variants"
 *                    | "chapter-variants" | "chats"
 *   type ChapterState = "planned" | "open" | "closing" | "closed"
 *   interface LoadedSubject { kind; entityId?; chapterState?; codexArchived? }
 *   type EditableRegion = "none" | "whole" | "book-state-notes"
 *   interface Editability { editable: EditableRegion; readOnlyReason: string | null }
 *   type WriteRegion = "whole" | "book-state-notes"
 *   interface WriteDecision { allowed: boolean; reason?: string }
 *   resolveSubjectPaneTarget(subject): WorkPaneTarget   // "content" | "chat"
 *   resolveEditability(subject): Editability
 *   checkWritePermission(subject, region): WriteDecision
 *
 * Every expected value comes from the spec, never from code:
 *   - the editable-vs-read-only outcomes are `004.context.md` -> "The editability
 *     table" (verbatim from `frontend-workspace.md` -> "Content pane — subject and
 *     editability"): the `open` chapter is editable; `closing` / `planned` / `closed`
 *     are read-only with a stated reason; a non-archived codex entry is editable and
 *     an archived one is not; Book state is state-notes-only editable; every list is
 *     read-only (US-097.AC-1 / AC-3, US-079, UC-050);
 *   - the write gate is a single writer-agnostic check (US-097.AC-2 / US-059.AC-3):
 *     its signature carries no writer argument, so the same subject+region yields the
 *     same decision no matter who asks;
 *   - the pane target is `frontend-workspace.md`'s rule: the chat list opens in the
 *     chat pane, every other kind in the content pane (US-105.AC-3).
 *
 * A pure module: no router, no `renderWithProviders`. `globals: false`.
 */
import { describe, expect, it } from "vitest";
import type { LoadedSubject, SubjectKind } from "../../src/work/subject";
import {
  checkWritePermission,
  resolveEditability,
  resolveSubjectPaneTarget,
} from "../../src/work/subject";

/** The whole subject-kind vocabulary the skeleton froze. */
const ALL_KINDS: SubjectKind[] = [
  "book-state",
  "chapters",
  "chapter",
  "characters",
  "locations",
  "facts",
  "codex-entry",
  "variants",
  "chapter-variants",
  "chats",
];

/** The kinds the editability table calls "Any list" — all read-only. */
const LIST_KINDS: SubjectKind[] = [
  "chapters",
  "characters",
  "locations",
  "facts",
  "variants",
  "chapter-variants",
  "chats",
];

/** The three chapter states the table pins as read-only (everything but `open`). */
const READ_ONLY_CHAPTER_STATES = ["closing", "planned", "closed"] as const;

describe("resolveEditability — chapters (DoD-1)", () => {
  it("DoD-1: a chapter in `open` state resolves as fully editable, with no read-only reason", () => {
    const subject: LoadedSubject = { kind: "chapter", entityId: "ch-1", chapterState: "open" };
    const result = resolveEditability(subject);
    expect(result.editable).toBe("whole");
    expect(result.readOnlyReason).toBeNull();
  });

  it("DoD-1: a chapter in `closing`, `planned` or `closed` resolves as read-only with a stated reason", () => {
    for (const chapterState of READ_ONLY_CHAPTER_STATES) {
      const subject: LoadedSubject = { kind: "chapter", entityId: "ch-9", chapterState };
      const result = resolveEditability(subject);
      expect(result.editable).toBe("none");
      // A stated reason: an author-facing, non-empty string (US-097.AC-1).
      expect(typeof result.readOnlyReason).toBe("string");
      expect((result.readOnlyReason ?? "").length).toBeGreaterThan(0);
    }
  });
});

describe("resolveEditability — codex, book state, lists (DoD-2)", () => {
  it("DoD-2: a non-archived codex entry resolves as editable", () => {
    const subject: LoadedSubject = { kind: "codex-entry", entityId: "ce-1", codexArchived: false };
    const result = resolveEditability(subject);
    expect(result.editable).toBe("whole");
    expect(result.readOnlyReason).toBeNull();
  });

  it("DoD-2: an archived codex entry resolves as read-only with a stated reason", () => {
    const subject: LoadedSubject = { kind: "codex-entry", entityId: "ce-1", codexArchived: true };
    const result = resolveEditability(subject);
    expect(result.editable).toBe("none");
    expect(typeof result.readOnlyReason).toBe("string");
    expect((result.readOnlyReason ?? "").length).toBeGreaterThan(0);
  });

  it("DoD-2: Book state resolves as state-notes-only editable", () => {
    const result = resolveEditability({ kind: "book-state" });
    expect(result.editable).toBe("book-state-notes");
  });

  it("DoD-2: every list kind resolves as read-only", () => {
    for (const kind of LIST_KINDS) {
      expect(resolveEditability({ kind }).editable).toBe("none");
    }
  });
});

describe("checkWritePermission — the single writer-agnostic gate (DoD-3)", () => {
  it("DoD-3: denies a write into a read-only subject, and denies identically on every call", () => {
    const closedChapter: LoadedSubject = {
      kind: "chapter",
      entityId: "ch-9",
      chapterState: "closed",
    };
    const first = checkWritePermission(closedChapter, "whole");
    const second = checkWritePermission(closedChapter, "whole");

    expect(first.allowed).toBe(false);
    expect(first.reason).toBeTruthy();
    // The signature carries no writer argument: the same subject+region returns the
    // same allow/deny+reason no matter who asks — the author's save path and the
    // assistant's write path get identical answers (US-097.AC-2 / US-059.AC-3).
    expect(second).toEqual(first);
  });

  it("DoD-3: allows a write into an editable subject (the `open` chapter)", () => {
    const openChapter: LoadedSubject = { kind: "chapter", entityId: "ch-1", chapterState: "open" };
    expect(checkWritePermission(openChapter, "whole").allowed).toBe(true);
  });

  it("DoD-3: an archived codex entry denies a whole-subject write", () => {
    const archived: LoadedSubject = { kind: "codex-entry", entityId: "ce-1", codexArchived: true };
    const decision = checkWritePermission(archived, "whole");
    expect(decision.allowed).toBe(false);
    expect(decision.reason).toBeTruthy();
  });

  it("DoD-3: Book state allows a state-notes write but denies a whole-subject write", () => {
    const bookState: LoadedSubject = { kind: "book-state" };
    // State notes are the editable region (UC-050).
    expect(checkWritePermission(bookState, "book-state-notes").allowed).toBe(true);
    // Everything else on Book state is read-only.
    const whole = checkWritePermission(bookState, "whole");
    expect(whole.allowed).toBe(false);
    expect(whole.reason).toBeTruthy();
  });
});

describe("resolveSubjectPaneTarget (DoD-4)", () => {
  it("DoD-4: the chat list resolves to the chat pane", () => {
    expect(resolveSubjectPaneTarget({ kind: "chats" })).toBe("chat");
  });

  it("DoD-4: every non-chat subject kind resolves to the content pane", () => {
    for (const kind of ALL_KINDS.filter((candidate) => candidate !== "chats")) {
      expect(resolveSubjectPaneTarget({ kind })).toBe("content");
    }
  });
});
