// The content pane's subject model (010/004) — the single place the
// editable-vs-read-only rule lives (`frontend-workspace.md` → "Content pane —
// subject and editability"; UC-083 / US-097). A loaded subject is classified by
// `SubjectKind`, resolves to a pane target, and resolves to an `Editability`
// verdict. `checkWritePermission` is the one gate both the author's save path and
// (at Stage 5) the assistant's write path must call, so a read-only subject
// refuses writes identically regardless of the writer (US-097.AC-2 / US-059.AC-3).
//
// Pure module: no MobX, no React, no `src/api/` import. Type-only import of
// `WorkPaneTarget` carries no runtime dependency.
//
// SKELETON (004): signatures + shapes frozen; every resolver body throws until
// the coder fills them.

import type { WorkPaneTarget } from "./components/shell/navItems";

/**
 * The vocabulary of things the content pane can hold (`frontend-workspace.md` —
 * "either a list or a single item"). The three codex lists are distinct kinds
 * (`characters` / `locations` / `facts`); `codex-entry` is a single entry.
 * `chapter-variants` is one chapter's variants; `variants` is the whole list.
 */
export type SubjectKind =
  | "book-state"
  | "chapters"
  | "chapter"
  | "characters"
  | "locations"
  | "facts"
  | "codex-entry"
  | "variants"
  | "chapter-variants"
  | "chats";

/** A chapter's lifecycle state (`domain-chapter.md`): at most one `open` per book. */
export type ChapterState = "planned" | "open" | "closing" | "closed";

/**
 * A loaded content-pane subject: its kind, the entity id where the kind names one
 * (a single chapter, a codex entry, one chapter's variants; absent for lists and
 * book state), and the facts editability turns on — a chapter's `state` and
 * whether a codex entry is `archived`. Both editability facts are optional and
 * only meaningful for the kind that carries them.
 */
export interface LoadedSubject {
  kind: SubjectKind;
  /** Entity id for single-item kinds (`chapter`, `codex-entry`, `chapter-variants`); omitted otherwise. */
  entityId?: string;
  /** Present when `kind === "chapter"`; drives the chapter editability rows. */
  chapterState?: ChapterState;
  /** Present when `kind === "codex-entry"`; an archived entry is read-only. */
  codexArchived?: boolean;
}

/**
 * Which region of a subject is editable: nothing, the whole subject, (Book state
 * only) the state notes, or — for a `planned` chapter — its sketch and the
 * caller's own chapter system prompt. `frontend-workspace.md`'s editability table
 * maps a subject to exactly one of these, EXCEPT for the one partially editable
 * row this feature introduces (see {@link Editability.editableRegions}).
 *
 * The two `chapter-*` members below `"book-state-notes"` were added by feature
 * `014.chapter-skeleton` step 008, which makes a `planned` chapter editable in
 * exactly those two regions while its body text stays read-only.
 *
 * `"chapter-text"` is added by feature `015.chapter-writing-free-mode` step 011,
 * and it supersedes `014`'s note that no such member was needed. `014` declined it
 * because *"naming it separately would change the answer `open` gives today for no
 * behaviour that feature ships"* — `015` DOES ship that behaviour (the whole-body
 * Markdown editor on the `open` chapter), and the `open` verdict now has to say two
 * things `"whole"` alone cannot: the BODY TEXT is editable, and the SKETCH is NOT.
 * UC-033 confines sketch edits to `planned`, which is the exact OPPOSITE window
 * from the body, so the two cannot share one wholesale answer.
 *
 * `"whole"` keeps its meaning on a chapter — it is the body-text write region for
 * {@link checkWritePermission}, which is why {@link WriteRegion} needed no member
 * and `checkWritePermission` is byte-untouched by `015`.
 *
 * `"chapter-own-prompt"` says *own* on purpose: decision D1 made the chapter
 * system prompt per-author, so there is no shared chapter prompt for a region to
 * name (`014.chapter-skeleton/context.md`).
 */
export type EditableRegion =
  | "none"
  | "whole"
  | "book-state-notes"
  | "chapter-sketch"
  | "chapter-own-prompt"
  | "chapter-text";

/**
 * The editability verdict for a loaded subject: what is editable, plus an
 * author-facing read-only reason (a *warning*, never a *flag*, in the wording).
 * `readOnlyReason` is `null` when the whole subject is editable and a stated
 * reason otherwise.
 *
 * `editable` is the WHOLE-SUBJECT verdict and stays a single region: it answers
 * "what may be edited wholesale", and `readOnlyReason` is the reason the rest is
 * not. A subject that is editable only in *some* regions answers `"none"` there —
 * nothing about it is editable wholesale — and enumerates those regions in
 * {@link Editability.editableRegions}.
 */
export interface Editability {
  editable: EditableRegion;
  readOnlyReason: string | null;
  /**
   * The regions of a subject whose editability is stated REGION BY REGION rather
   * than by the single `editable` verdict. Absent for every verdict that does not
   * need it, whose editable set is exactly `editable === "none" ? [] : [editable]`.
   *
   * Two chapter states enumerate regions, and they are deliberately disjoint:
   *
   * - `planned` — `["chapter-sketch", "chapter-own-prompt"]` (feature `014` step
   *   008 — UC-033 / US-034.AC-1), with `editable: "none"`, because nothing about a
   *   planned chapter is editable wholesale; its `readOnlyReason` remains the reason
   *   its **body text** is read-only.
   * - `open` — the chapter's **body text** and the caller's **own prompt**, with
   *   `editable` still `"whole"` and `readOnlyReason` still `null` (feature `015`
   *   step 011). Here the list does NOT narrow a read-only subject; it spells out
   *   what `"whole"` means on an `open` chapter — the body, which is what `"whole"`
   *   has always been the write region for — and, by omission, says the SKETCH is
   *   not among them (UC-033's window is `planned` only).
   *
   * `closing` and `closed` enumerate nothing and are untouched by either feature.
   */
  editableRegions?: EditableRegion[];
}

/**
 * The region a write targets. Covers the writable regions only — the whole
 * subject, or Book state's state notes. Passed to {@link checkWritePermission}.
 *
 * DELIBERATELY UNCHANGED by feature `014` step 008. A chapter's **body text** is
 * `"whole"` here (that is what an `open` chapter's write is today), so DoD-13's
 * "still refuses a write to a `planned` chapter's body text" is
 * `checkWritePermission(plannedChapter, "whole")` and needs no new member. The
 * sketch and the own-prompt are NOT added: feature `014` routes neither save
 * through this gate — the sketch's refusal is the server's `409` on a
 * non-`planned` chapter and the prompt has no state gate at all — and a member the
 * gate could only ever refuse would be vocabulary for a write path nothing ships.
 * Whoever first routes a sketch or own-prompt write through this gate adds the
 * member together with the `editableRegions` lookup it needs.
 *
 * DELIBERATELY UNCHANGED AGAIN by feature `015` step 011, for the same reason and
 * with the same consequence: `015` widened {@link EditableRegion} with
 * `"chapter-text"`, but a chapter body write is still `checkWritePermission(chapter,
 * "whole")` — `"whole"` IS the body on a chapter — so an `open` chapter allows it
 * and `planned` / `closing` / `closed` refuse it exactly as they do today. No
 * `"chapter-text"` write region is minted, because nothing routes a write through
 * this gate under that name.
 */
export type WriteRegion = "whole" | "book-state-notes";

/**
 * The verdict of the write gate: whether the write is allowed, and (on denial) an
 * author-facing reason.
 */
export interface WriteDecision {
  allowed: boolean;
  reason?: string;
}

/**
 * Resolve which pane a subject drives: the chat list opens the chat pane, every
 * other kind renders into the content pane.
 *
 * SKELETON: unimplemented — body throws.
 */
export function resolveSubjectPaneTarget(subject: LoadedSubject): WorkPaneTarget {
  return subject.kind === "chats" ? "chat" : "content";
}

/**
 * Resolve a loaded subject to its editability verdict, implementing
 * `frontend-workspace.md`'s table exactly: the `open` chapter and a non-archived
 * codex entry are editable whole; Book state is `book-state-notes`-editable;
 * `closing` / `closed` chapters, archived codex entries and every list are
 * read-only with a stated reason.
 *
 * The one PARTIAL row (feature `014.chapter-skeleton` step 008): a `planned`
 * chapter is read-only in its body text — the reason it already carried, verbatim
 * — and editable in `editableRegions: ["chapter-sketch", "chapter-own-prompt"]`.
 * `open`, `closing` and `closed` are untouched by that amendment, wording
 * included, and so are the codex, Book-state and list rows.
 *
 * Feature `015.chapter-writing-free-mode` step 011 amends ONE more case — `open`,
 * and nothing else in this function. See the branch itself; `planned`, `closing`
 * and `closed` keep `014`'s answers with their author-facing reason strings
 * VERBATIM, and the codex, Book-state, list and fallback rows are untouched.
 */
export function resolveEditability(subject: LoadedSubject): Editability {
  switch (subject.kind) {
    case "chapter": {
      // Exactly the `open` chapter is editable; every other state is read-only,
      // and `closing`/`closed` both refuse all writes to `text` (member and
      // assistant alike) per `domain-chapter.md`.
      switch (subject.chapterState) {
        case "open":
          // The second partially-enumerated row (feature `015` step 011). Unlike
          // `planned`'s, this list does NOT narrow a read-only subject: `editable`
          // stays `"whole"` and `readOnlyReason` stays `null` — which is what keeps
          // `checkWritePermission(open, "whole")` allowing the body write — and the
          // list spells out what `"whole"` means on an OPEN chapter: the chapter's
          // BODY TEXT and the caller's OWN chapter prompt. `"chapter-sketch"` is
          // deliberately absent: UC-033 confines sketch edits to `planned`, the
          // exact OPPOSITE window from the body.
          return {
            editable: "whole",
            readOnlyReason: null,
            editableRegions: ["chapter-text", "chapter-own-prompt"],
          };
        case "closing":
          return {
            editable: "none",
            readOnlyReason:
              "This chapter is closing while its owner approves continuity for this body — it is read-only until the review completes.",
          };
        case "planned":
          // The ONE partially editable row (feature `014.chapter-skeleton` step
          // 008): a planned chapter's SKETCH and the caller's OWN chapter system
          // prompt are editable (UC-033 / US-034.AC-1), while its BODY TEXT stays
          // read-only with the reason it already carried, verbatim.
          //
          // `editable` stays `"none"` because nothing about a planned chapter is
          // editable WHOLESALE, and `readOnlyReason` is still the body text's
          // reason — which is exactly what keeps
          // `checkWritePermission(planned, "whole")` refusing the body write
          // (DoD-13) without that function being touched at all.
          return {
            editable: "none",
            readOnlyReason:
              "This chapter is still planned and cannot be edited until it is opened for writing.",
            editableRegions: ["chapter-sketch", "chapter-own-prompt"],
          };
        case "closed":
          return {
            editable: "none",
            readOnlyReason: "This chapter is closed and can no longer be edited.",
          };
        default:
          return {
            editable: "none",
            readOnlyReason: "This chapter cannot be edited in its current state.",
          };
      }
    }
    case "codex-entry":
      // Non-archived is editable whole here; the free/proposal collaboration-mode
      // nuance is `013.codex`'s to apply. An archived entry is read-only.
      return subject.codexArchived
        ? {
            editable: "none",
            readOnlyReason:
              "This codex entry is archived and read-only; restore it to make changes.",
          }
        : { editable: "whole", readOnlyReason: null };
    case "book-state":
      // Book state: the state notes are editable (UC-050); everything else is read-only.
      return {
        editable: "book-state-notes",
        readOnlyReason: "Only the state notes are editable on Book state; all other fields are read-only.",
      };
    case "chapters":
    case "characters":
    case "locations":
    case "facts":
    case "variants":
    case "chapter-variants":
    case "chats":
      // Every list kind is read-only.
      return {
        editable: "none",
        readOnlyReason: "This is a list view and cannot be edited.",
      };
    default:
      return {
        editable: "none",
        readOnlyReason: "This subject cannot be edited.",
      };
  }
}

/**
 * The single write gate. Given a subject and the region being written, return
 * allow/deny with the read-only reason on denial. This is the one call both the
 * author's save path and the Stage-5 assistant write path must route through, so a
 * read-only subject refuses writes identically regardless of the writer
 * (US-097.AC-2 / US-059.AC-3). Nothing calls it yet in this feature.
 *
 * SKELETON: unimplemented — body throws.
 */
export function checkWritePermission(
  subject: LoadedSubject,
  region: WriteRegion,
): WriteDecision {
  // Writer-agnostic by construction: the decision is derived solely from the
  // subject's editability and the region, with no writer parameter, so the
  // author's save path and the assistant's write path get identical answers for
  // the same `(subject, region)` (US-097.AC-2 / US-059.AC-3). A write is allowed
  // only into the region that editability marks editable for this subject.
  const editability = resolveEditability(subject);
  if (region === editability.editable) {
    return { allowed: true };
  }
  return {
    allowed: false,
    reason: editability.readOnlyReason ?? "This subject is read-only.",
  };
}
