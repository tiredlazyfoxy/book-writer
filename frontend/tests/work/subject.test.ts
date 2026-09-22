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
import type {
  EditableRegion,
  LoadedSubject,
  SubjectKind,
  WriteRegion,
} from "../../src/work/subject";
// The wire-exact twin, pinned against the work-module union by 026.memos step 009 DoD-5.
import type { SubjectKind as WireSubjectKind } from "../../src/types/chats";
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

/* ------------------------------------------------------------------------------------
 * 014.chapter-skeleton / 008.work-chapter-item — the `planned` chapter becomes
 * PARTIALLY editable.  DoD-12 · DoD-13.
 *
 * Bound to the frozen signatures in status.md -> `## Skeleton` (step 008), which records
 * the two decisions the plan delegated:
 *   type EditableRegion = "none" | "whole" | "book-state-notes"
 *                       | "chapter-sketch" | "chapter-own-prompt"        // widened
 *   interface Editability { editable: EditableRegion; readOnlyReason: string | null;
 *                           editableRegions?: EditableRegion[] }         // NEW, optional
 *   type WriteRegion = "whole" | "book-state-notes"                      // NOT widened
 *   resolveEditability(subject): Editability          // only the `planned` case changes
 *   checkWritePermission(subject, region): WriteDecision   // byte-untouched
 * On a chapter the body IS the whole subject, so the body-text write region is `"whole"`.
 *
 * Every expected value comes from the spec, never from code:
 *   - the skeleton feature makes a `planned` chapter's SKETCH editable (UC-033 /
 *     US-034.AC-1) and every member's OWN chapter prompt editable (decision D1), while
 *     its BODY TEXT stays read-only with the reason it already carried
 *     (`008.context.md` -> "Why the subject model changes at all");
 *   - the `planned` verdict's `readOnlyReason` is the string the branch already carried,
 *     recorded verbatim in the step-008 skeleton freeze — it is copy the author reads;
 *   - `open`, `closing` and `closed` keep the answers they give today, and none of them
 *     becomes partially editable (`008` Interface intent: "open, closing and closed are
 *     untouched");
 *   - widening editability is not widening the write path: a write into a `planned`
 *     chapter's body is still refused (DoD-13, `008.context.md`).
 * ---------------------------------------------------------------------------------- */

/** The reason the `planned` branch already carried, kept verbatim for the body text. */
const PLANNED_READ_ONLY_REASON =
  "This chapter is still planned and cannot be edited until it is opened for writing.";

const PLANNED_CHAPTER: LoadedSubject = {
  kind: "chapter",
  entityId: "ch-1",
  chapterState: "planned",
};

describe("resolveEditability — a `planned` chapter is editable by REGION (DoD-12)", () => {
  it("DoD-12: a `planned` chapter is editable in its sketch and in the caller's own prompt", () => {
    const result = resolveEditability(PLANNED_CHAPTER);

    // The two regions this feature ships, and only those two.
    expect(result.editableRegions).toEqual(
      expect.arrayContaining(["chapter-sketch", "chapter-own-prompt"]),
    );
    expect(result.editableRegions).toHaveLength(2);
  });

  it("DoD-12: a `planned` chapter's BODY TEXT stays read-only, with the reason it already carried", () => {
    const result = resolveEditability(PLANNED_CHAPTER);

    // Nothing about the chapter is editable wholesale: the body is what `editable`
    // answers for, and it is still read-only.
    expect(result.editable).toBe("none");
    expect(result.readOnlyReason).toBe(PLANNED_READ_ONLY_REASON);
  });

  it("DoD-12: `open` keeps the answer it gives today — editable whole, no reason, no region list", () => {
    const result = resolveEditability({ kind: "chapter", entityId: "ch-2", chapterState: "open" });

    expect(result.editable).toBe("whole");
    expect(result.readOnlyReason).toBeNull();
    // SUPERSEDED by 015.chapter-writing-free-mode step 011, DoD-1/DoD-2: the `open`
    // verdict now enumerates its regions BESIDE `editable: "whole"`, because it has to
    // say two things `"whole"` alone cannot — the body text is editable and the sketch
    // is not (UC-033 confines sketch edits to `planned`). The title's "no region list"
    // clause no longer holds; the first two assertions above are unchanged and still do.
    expect(result.editableRegions).toHaveLength(2);
  });

  it("DoD-12: `closing` and `closed` keep the answers they give today — read-only, each with its own stated reason, and no editable region", () => {
    const closing = resolveEditability({
      kind: "chapter",
      entityId: "ch-3",
      chapterState: "closing",
    });
    const closed = resolveEditability({
      kind: "chapter",
      entityId: "ch-4",
      chapterState: "closed",
    });

    for (const result of [closing, closed]) {
      expect(result.editable).toBe("none");
      // A stated, author-facing reason (US-097.AC-1) — unchanged by this amendment.
      expect(typeof result.readOnlyReason).toBe("string");
      expect((result.readOnlyReason ?? "").length).toBeGreaterThan(0);
      // Neither state gained a partially-editable region.
      expect(result.editableRegions ?? []).toEqual([]);
    }

    // The two reasons stay distinct from each other and from the `planned` one: each
    // state's own author-facing copy survives the amendment.
    expect(closing.readOnlyReason).not.toBe(PLANNED_READ_ONLY_REASON);
    expect(closed.readOnlyReason).not.toBe(PLANNED_READ_ONLY_REASON);
  });
});

describe("checkWritePermission — the body write path is unchanged (DoD-13)", () => {
  it("DoD-13: a write into a `planned` chapter's body text is still refused, with a reason", () => {
    // The body IS the whole subject on a chapter, so `"whole"` is the body-text region.
    const decision = checkWritePermission(PLANNED_CHAPTER, "whole");

    // The amendment widened EDITABILITY, not the write path.
    expect(decision.allowed).toBe(false);
    // Refused with a stated reason, exactly as every other read-only subject is.
    expect(decision.reason).toBeTruthy();
    expect((decision.reason ?? "").length).toBeGreaterThan(0);
  });
});

/* ------------------------------------------------------------------------------------
 * 015.chapter-writing-free-mode / 011.work-module-tier-chapter — the `open` chapter
 * becomes editable BY REGION too.  DoD-1 · DoD-2 · DoD-3.
 *
 * Bound to the frozen signatures in status.md -> `## Skeleton` (015 step 011):
 *   type EditableRegion = "none" | "whole" | "book-state-notes" | "chapter-sketch"
 *                       | "chapter-own-prompt" | "chapter-text"          // widened by one
 *   interface Editability { editable; readOnlyReason; editableRegions? } // shape unchanged
 *   type WriteRegion = "whole" | "book-state-notes"                      // NOT widened
 *   resolveEditability(subject): Editability        // only the `open` case changes
 *   checkWritePermission(subject, region): WriteDecision   // byte-untouched
 *
 * Every expected value comes from the spec, never from code:
 *   - DoD-1: an `open` chapter is editable in its BODY TEXT, and `planned` / `closing` /
 *     `closed` keep the answers 014 gives them, author-facing reason strings included
 *     (step file -> Interface intent, "`subject.ts`");
 *   - DoD-2: an `open` chapter's SKETCH is NOT editable — UC-033 confines sketch edits to
 *     `planned`, which is the exact opposite window from the body;
 *   - the caller's own chapter prompt stays editable in every state (step file: "the
 *     caller's own prompt stays editable, as it is in every state"), so the `open`
 *     verdict names exactly the body text and the own prompt — two regions, no more;
 *   - DoD-3: a chapter body write is `checkWritePermission(subject, "whole")` — `"whole"`
 *     IS the body on a chapter — allowed on `open` and refused on the other three
 *     (`frontend-workspace.md`: the assistant and the author are refused by the same rule).
 * ---------------------------------------------------------------------------------- */

const OPEN_CHAPTER: LoadedSubject = {
  kind: "chapter",
  entityId: "ch-open-1",
  chapterState: "open",
};

/** The three states in which a chapter body may not be written. */
const NON_OPEN_CHAPTER_STATES = ["planned", "closing", "closed"] as const;

describe("resolveEditability — an `open` chapter is editable in its BODY TEXT (015 DoD-1)", () => {
  it("DoD-1: the `open` verdict names the chapter's body text as an editable region", () => {
    const result = resolveEditability(OPEN_CHAPTER);

    // The whole-subject answer 014 gives is unchanged...
    expect(result.editable).toBe("whole");
    expect(result.readOnlyReason).toBeNull();
    // ...and the body text is now named explicitly.
    expect(result.editableRegions ?? []).toContain("chapter-text");
  });

  it("DoD-1: the caller's own chapter prompt stays editable while the chapter is `open`", () => {
    const result = resolveEditability(OPEN_CHAPTER);

    expect(result.editableRegions ?? []).toContain("chapter-own-prompt");
  });

  it("DoD-1: `planned` keeps 014's answer — its two regions and its reason string, verbatim", () => {
    const result = resolveEditability(PLANNED_CHAPTER);

    expect(result.editable).toBe("none");
    expect(result.readOnlyReason).toBe(PLANNED_READ_ONLY_REASON);
    expect(result.editableRegions).toEqual(
      expect.arrayContaining(["chapter-sketch", "chapter-own-prompt"]),
    );
    expect(result.editableRegions).toHaveLength(2);
  });

  it("DoD-1: `closing` and `closed` keep 014's answers — read-only, each with its own stated reason", () => {
    const closing = resolveEditability({
      kind: "chapter",
      entityId: "ch-3",
      chapterState: "closing",
    });
    const closed = resolveEditability({
      kind: "chapter",
      entityId: "ch-4",
      chapterState: "closed",
    });

    for (const result of [closing, closed]) {
      expect(result.editable).toBe("none");
      expect(typeof result.readOnlyReason).toBe("string");
      expect((result.readOnlyReason ?? "").length).toBeGreaterThan(0);
      // Neither state gained a region — the widening is the `open` case alone.
      expect(result.editableRegions ?? []).toEqual([]);
    }

    // Each state's own author-facing copy survives, distinct from the others'.
    expect(closing.readOnlyReason).not.toBe(closed.readOnlyReason);
    expect(closing.readOnlyReason).not.toBe(PLANNED_READ_ONLY_REASON);
    expect(closed.readOnlyReason).not.toBe(PLANNED_READ_ONLY_REASON);
  });
});

describe("resolveEditability — an `open` chapter's SKETCH is not editable (015 DoD-2)", () => {
  it("DoD-2: the `open` verdict enumerates exactly the body text and the own prompt — and not the sketch", () => {
    const result = resolveEditability(OPEN_CHAPTER);

    // PRESENCE FIRST: the verdict exists and reports the BODY editable. "The sketch is
    // not editable" is trivially true of a verdict that names no region at all, so the
    // enumeration is pinned exactly before anything is denied.
    const regions = result.editableRegions;
    expect(regions).toEqual(
      expect.arrayContaining(["chapter-text", "chapter-own-prompt"]),
    );
    expect(regions).toHaveLength(2);

    // Only then: UC-033 confines sketch edits to `planned`, so the sketch is absent here.
    expect(regions ?? []).not.toContain("chapter-sketch");
  });

  it("DoD-2: the sketch region belongs to `planned` and to `planned` alone", () => {
    // The window for the sketch is the exact opposite of the window for the body.
    expect(resolveEditability(PLANNED_CHAPTER).editableRegions ?? []).toContain(
      "chapter-sketch",
    );
    expect(resolveEditability(OPEN_CHAPTER).editableRegions ?? []).not.toContain(
      "chapter-sketch",
    );
  });
});

describe("checkWritePermission — the body write follows the chapter's state (015 DoD-3)", () => {
  it("DoD-3: a body write into an `open` chapter is allowed", () => {
    // `"whole"` IS the body-text write region on a chapter — no write region was minted.
    expect(checkWritePermission(OPEN_CHAPTER, "whole").allowed).toBe(true);
  });

  it("DoD-3: a body write into a `planned`, `closing` or `closed` chapter is refused, with a reason", () => {
    for (const chapterState of NON_OPEN_CHAPTER_STATES) {
      const decision = checkWritePermission(
        { kind: "chapter", entityId: "ch-x", chapterState },
        "whole",
      );

      expect(decision.allowed).toBe(false);
      expect((decision.reason ?? "").length).toBeGreaterThan(0);
    }
  });
});

/* ------------------------------------------------------------------------------------
 * 026.memos / 009.memos-api-and-navigator — the memos subject kind.
 * DoD-5 · DoD-6 · DoD-7.
 *
 * Bound to the frozen interface in status.md -> `## Skeleton` (026 step 009):
 *   type SubjectKind = … | "chats" | "memos"      // widened by ONE, eleventh and last
 *   type SubjectKind (src/types/chats.d.ts)       // the wire twin, widened identically
 *   type EditableRegion = "none" | "whole" | "book-state-notes" | "chapter-sketch"
 *                       | "chapter-own-prompt" | "chapter-text"   // NOT widened
 *   type WriteRegion = "whole" | "book-state-notes"                // NOT widened
 *   resolveEditability(subject): Editability      // gains a `memos` case only
 *   checkWritePermission(subject, region): WriteDecision           // untouched
 *
 * Every expected value comes from the spec, never from code:
 *   - DoD-5 (`quick-reference.md` -> the `SubjectKind` row; `context.md` -> decision 11):
 *     `"memos"` joins BOTH unions and the two lists stay value-for-value identical. The
 *     two exhaustive `Record<Union, true>` tables below are the assertion's teeth: a
 *     missing member or an extra one fails to compile under `npm run test:types`, and
 *     the cross-assignments pin the two unions as mutually assignable — i.e. equal;
 *   - DoD-6 (`frontend-workspace.md` -> the `resolveEditability` paragraph;
 *     `context.md` -> decision 12): the memos kind answers a CONSTANT editable verdict —
 *     the existing `"whole"` region, no read-only reason — because the memos list is the
 *     content pane's first editable list and the branch decides nothing. And the other
 *     half, which is what stops the branch being written too broadly: every OTHER list
 *     kind still answers its read-only verdict, reason string verbatim
 *     (`009.context.md` -> "Every list kind today returns …");
 *   - DoD-7 (same paragraph): `EditableRegion` gains NO member — the memos verdict reuses
 *     `"whole"` — and `checkWritePermission`'s behaviour is unchanged for every existing
 *     subject kind. `WriteRegion` is not widened either.
 * ---------------------------------------------------------------------------------- */

/** The read-only verdict's wording, carried verbatim by every list kind but memos. */
const LIST_READ_ONLY_REASON = "This is a list view and cannot be edited.";

/**
 * The ELEVEN subject kinds, exhaustively. `Record<SubjectKind, true>` fails to compile
 * if a member is missing OR if one is named that the union does not carry.
 */
const SUBJECT_KIND_TABLE: Record<SubjectKind, true> = {
  "book-state": true,
  chapters: true,
  chapter: true,
  characters: true,
  locations: true,
  facts: true,
  "codex-entry": true,
  variants: true,
  "chapter-variants": true,
  chats: true,
  memos: true,
};

/** The same eleven, against the wire twin in `src/types/chats.d.ts`. */
const WIRE_SUBJECT_KIND_TABLE: Record<WireSubjectKind, true> = {
  "book-state": true,
  chapters: true,
  chapter: true,
  characters: true,
  locations: true,
  facts: true,
  "codex-entry": true,
  variants: true,
  "chapter-variants": true,
  chats: true,
  memos: true,
};

/** The SIX editable regions — unchanged by this feature. */
const EDITABLE_REGION_TABLE: Record<EditableRegion, true> = {
  none: true,
  whole: true,
  "book-state-notes": true,
  "chapter-sketch": true,
  "chapter-own-prompt": true,
  "chapter-text": true,
};

/** The TWO write regions — unchanged by this feature. */
const WRITE_REGION_TABLE: Record<WriteRegion, true> = {
  whole: true,
  "book-state-notes": true,
};

describe("SubjectKind carries `memos`, in both copies (026 DoD-5)", () => {
  it("DoD-5: `memos` is a member of the work-module union and of the wire twin", () => {
    expect(Object.keys(SUBJECT_KIND_TABLE)).toContain("memos");
    expect(Object.keys(WIRE_SUBJECT_KIND_TABLE)).toContain("memos");
  });

  it("DoD-5: the two lists are value-for-value identical — same members, no more, no fewer", () => {
    expect([...Object.keys(SUBJECT_KIND_TABLE)].sort()).toEqual(
      [...Object.keys(WIRE_SUBJECT_KIND_TABLE)].sort(),
    );
    // Eleven members: the ten that existed plus `memos`.
    expect(Object.keys(SUBJECT_KIND_TABLE)).toHaveLength(11);
    expect(Object.keys(WIRE_SUBJECT_KIND_TABLE)).toHaveLength(11);
  });

  it("DoD-5: the two unions are mutually assignable, so neither can drift from the other", () => {
    // Compile-time teeth (`npm run test:types` is the only program covering `tests/`):
    // each assignment requires one union to be assignable to the other, and the pair of
    // them requires the two to be the same set. Runtime only witnesses the value.
    const asWire: WireSubjectKind = "memos";
    const asWork: SubjectKind = asWire;
    const backToWire: WireSubjectKind = asWork;

    expect(asWork).toBe("memos");
    expect(backToWire).toBe("memos");
  });
});

describe("resolveEditability — the memos list is editable (026 DoD-6)", () => {
  it("DoD-6: the memos kind resolves as editable in the existing `whole` region, with no read-only reason", () => {
    const result = resolveEditability({ kind: "memos" });

    expect(result.editable).toBe("whole");
    expect(result.readOnlyReason).toBeNull();
  });

  it("DoD-6: the verdict is CONSTANT — nothing about the loaded subject changes it", () => {
    // The branch decides nothing: no state machine, no collaboration-mode gate, no
    // archived-book gate (`context.md` -> decision 12; decision 4's carve-out).
    const subjects: LoadedSubject[] = [
      { kind: "memos" },
      { kind: "memos", entityId: "m-1" },
      { kind: "memos", chapterState: "closed" },
      { kind: "memos", codexArchived: true },
    ];

    for (const subject of subjects) {
      const result = resolveEditability(subject);
      expect(result.editable).toBe("whole");
      expect(result.readOnlyReason).toBeNull();
    }
  });

  it("DoD-6: every OTHER list kind still answers its read-only verdict, reason verbatim", () => {
    // The half that stops the branch from being written too broadly: memos is the only
    // list that became editable.
    for (const kind of LIST_KINDS) {
      const result = resolveEditability({ kind });
      expect(result.editable).toBe("none");
      expect(result.readOnlyReason).toBe(LIST_READ_ONLY_REASON);
    }
  });

  it("DoD-6: the chapter, codex and book-state verdicts are untouched by the memos branch", () => {
    expect(resolveEditability(OPEN_CHAPTER).editable).toBe("whole");
    expect(resolveEditability(PLANNED_CHAPTER).readOnlyReason).toBe(PLANNED_READ_ONLY_REASON);
    expect(
      resolveEditability({ kind: "codex-entry", entityId: "ce-1", codexArchived: false }).editable,
    ).toBe("whole");
    expect(
      resolveEditability({ kind: "codex-entry", entityId: "ce-1", codexArchived: true }).editable,
    ).toBe("none");
    expect(resolveEditability({ kind: "book-state" }).editable).toBe("book-state-notes");
  });
});

describe("no region was minted, and the write gate is unchanged (026 DoD-7)", () => {
  it("DoD-7: `EditableRegion` still carries exactly its six members — memos reuses `whole`", () => {
    // `Record<EditableRegion, true>` above fails to compile if a seventh member exists
    // and is unnamed here; the count keeps a rename from slipping through silently.
    expect(Object.keys(EDITABLE_REGION_TABLE)).toHaveLength(6);
    expect(Object.keys(EDITABLE_REGION_TABLE)).toContain("whole");
    expect(Object.keys(EDITABLE_REGION_TABLE)).not.toContain("memos");
  });

  it("DoD-7: `WriteRegion` is not widened either — still `whole` and `book-state-notes`", () => {
    expect([...Object.keys(WRITE_REGION_TABLE)].sort()).toEqual(["book-state-notes", "whole"]);
  });

  it("DoD-7: checkWritePermission answers unchanged for every existing chapter state", () => {
    expect(checkWritePermission(OPEN_CHAPTER, "whole").allowed).toBe(true);
    for (const chapterState of NON_OPEN_CHAPTER_STATES) {
      const decision = checkWritePermission(
        { kind: "chapter", entityId: "ch-x", chapterState },
        "whole",
      );
      expect(decision.allowed).toBe(false);
      expect((decision.reason ?? "").length).toBeGreaterThan(0);
    }
  });

  it("DoD-7: checkWritePermission answers unchanged for codex entries and for Book state", () => {
    expect(
      checkWritePermission({ kind: "codex-entry", entityId: "ce-1", codexArchived: false }, "whole")
        .allowed,
    ).toBe(true);
    expect(
      checkWritePermission({ kind: "codex-entry", entityId: "ce-1", codexArchived: true }, "whole")
        .allowed,
    ).toBe(false);
    expect(checkWritePermission({ kind: "book-state" }, "book-state-notes").allowed).toBe(true);
    expect(checkWritePermission({ kind: "book-state" }, "whole").allowed).toBe(false);
  });

  it("DoD-7: checkWritePermission still refuses a write into every existing read-only list kind", () => {
    for (const kind of LIST_KINDS) {
      const decision = checkWritePermission({ kind }, "whole");
      expect(decision.allowed).toBe(false);
      expect((decision.reason ?? "").length).toBeGreaterThan(0);
    }
  });
});
