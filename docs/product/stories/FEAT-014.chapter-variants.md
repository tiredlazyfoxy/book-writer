<!-- product-spec:start -->
# Stories — FEAT-014 Chapter variants & fixes

### US-062 — Editing a closed chapter creates a new variant
- **Feature:** FEAT-014 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-058
- **Status:** proposed
- **Story:** As a book member, I want applying an edit to a reopened
  chapter to keep the previous body as a recoverable revision, so that I
  can recover it if the fix doesn't work out.
- **Acceptance criteria:**
  - **US-062.AC-1** — Given a closed chapter is reopened and edited, when
    the edit is applied, then the chapter's previous body is retained as a
    revision.
  - **US-062.AC-2** — Given a chapter gains a revision from an applied
    edit, when the following chapters are inspected, then they remain
    unchanged.
- **Source:** `[confirmed: user]` interview 2026-07-20, "chapter variants &
  fixes": "the chapter keeps all its variants... Following chapters stay.";
  interview 2026-07-24, "augment round 7", divergence 1 (C-r7-3): the
  revision/variant term split.

### US-063 — Member views and compares a chapter's variants
- **Feature:** FEAT-014 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-059
- **Status:** proposed
- **Story:** As a book member, I want to see and compare a chapter's
  variants and revisions, so that I can judge whether a fix improved it.
- **Acceptance criteria:**
  - **US-063.AC-1** — Given a chapter with one or more variants or
    revisions, when a member opens the list, then all of them are shown.
  - **US-063.AC-2** — Given a chapter's variant list, when a member opens
    it, then each variant shows its author and date.
  - **US-063.AC-3** — Given two revisions selected, or a variant and the
    current body, when a member requests a comparison, then their
    differences are shown.
- **Source:** `[confirmed: user]` interview 2026-07-20, "chapter variants &
  fixes": "we need the easy way to 'see' the variants."; interview
  2026-07-24, "augment round 7", challenge C-r7-7: AC-2 replaced —
  "the active variant is marked as such" is untestable with no active
  variant.

### US-064 — Owner applies a variant to the chapter
- **Feature:** FEAT-014 · **Actor:** ACT-004 · **Realizes:** UC-060
- **Status:** proposed
- **Story:** As a book owner, I want to apply a variant to the chapter, so
  that its result becomes the chapter's text while the previous body stays
  recoverable.
- **Acceptance criteria:**
  - **US-064.AC-1** — Given a chapter with an un-applied variant, when the
    owner applies it, then the variant's result becomes the chapter's text
    and the chapter's previous body is retained as a revision.
  - **US-064.AC-2** — Given a co-author (not the owner), when they attempt
    to apply a variant, then the action is refused.
  - **US-064.AC-3** — Given a variant composed against a body that has
    since changed, when the owner attempts to apply it, then the apply is
    refused.
- **Source:** `[confirmed: user]` interview 2026-07-20, "chapter variants &
  fixes": "The owner picks one active variant."; interview 2026-07-24,
  "augment round 7", divergence 1: applying, not selecting; a stale
  variant is refused and redone by hand.

### US-065 — Applying a variant runs the chapter's consistency check
- **Feature:** FEAT-014 · **Actor:** ACT-004 · **Realizes:** UC-060
- **Status:** proposed
- **Story:** As a book owner, I want applying a variant to run the same
  consistency check any other change to the chapter does, so that
  inconsistencies it introduces are caught.
- **Acceptance criteria:**
  - **US-065.AC-1** — Given the owner applies a variant to the chapter,
    when the apply completes, then the chapter's consistency check runs
    (FEAT-016).
- **Source:** `[confirmed: user]` interview 2026-07-20, "chapter variants &
  fixes": "switching changes the chapter's text, so it takes the same
  path."; interview 2026-07-24, "augment round 7", divergence 1: an apply
  runs the consistency-check path necessarily — an apply is a change.
<!-- product-spec:end -->
