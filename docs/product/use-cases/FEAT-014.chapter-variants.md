<!-- product-spec:start -->
# Use Cases — FEAT-014 Chapter variants & fixes

### UC-058 — Edit a reopened chapter, creating a variant
- **Feature:** FEAT-014 · **Actor:** ACT-004, ACT-005
- **Preconditions:** Chapter is open after being reopened (UC-037).
- **Main flow:**
  1. Member composes an edit to the reopened chapter, against its current
     body.
  2. Member applies the edit.
  3. System snapshots the chapter's previous body as a revision.
  4. System updates the chapter's text to the edit's result.
- **Alternate flow:** Member saves the edit without applying it → it
  remains a variant; the chapter's text is unchanged.
- **Exception flow:** The edit results in text identical to the original →
  `_TBD: whether an edit identical to the original still creates a new
  variant or is a no-op — not stated._`
- **Postconditions:** Chapter gains a revision (applied edit) or a variant
  (un-applied edit); following chapters are unaffected.
- **Source:** `[confirmed: user]` interview 2026-07-20, "Augment round 3 —
  variants, cloning & consistency", "chapter variants & fixes": "It becomes
  a fix, and the chapter keeps all its variants, shown to authors. Following
  chapters stay."; interview 2026-07-24, "augment round 7 — enforcing the
  architecture pass onto the spec", divergence 1: "a chapter has a single
  body; a variant is an un-applied change beside it... making it the
  chapter's text is applying it." (C-r7-3, term split).

### UC-059 — View and compare a chapter's variants
- **Feature:** FEAT-014 · **Actor:** ACT-004, ACT-005
- **Preconditions:** Chapter has one or more variants or revisions.
- **Main flow:**
  1. Member opens a chapter's variant list.
  2. System shows the chapter's un-applied variants and its revisions,
     each with author and date.
  3. Member selects two revisions, or a variant and the current body, to
     compare.
  4. System shows their differences.
- **Exception flow:** Chapter has no variants or revisions (never fixed) →
  nothing to compare; the view shows only the current body.
- **Postconditions:** None (read-only); all variants and revisions stay
  visible.
- **Source:** `[confirmed: user]` interview 2026-07-20, "chapter variants &
  fixes": "we need the easy way to 'see' the variants."; interview
  2026-07-24, "augment round 7", divergence 1 (C-r7-7): there is no active
  variant to mark — replaced by the variant/revision list.

### UC-060 — Apply a variant to the chapter
- **Feature:** FEAT-014 · **Actor:** ACT-004
- **Preconditions:** Chapter has one or more un-applied variants.
- **Main flow:**
  1. Owner opens the chapter's variant list.
  2. Owner selects an un-applied variant to apply.
  3. System snapshots the chapter's current body as a revision.
  4. System updates the chapter's text to the variant's result.
  5. System runs the same consistency-check path any other change to the
     chapter does (FEAT-016).
- **Exception flow:** The variant was composed against a body that has
  since changed → the apply is refused; the author redoes the change by
  hand (no automatic merge). Non-owner attempts to apply a variant →
  refused.
- **Postconditions:** The applied variant's result is now the chapter's
  text; the chapter's previous body is retained as a revision.
- **Source:** `[confirmed: user]` interview 2026-07-20, "chapter variants &
  fixes": "The owner picks one active variant... switching changes the
  chapter's text, so it takes the same path."; interview 2026-07-24,
  "augment round 7", divergence 1: "making it the chapter's text is
  applying it, through the same write path every other change takes... a
  variant composed against a body that has since moved is refused — the
  author redoes it. No merge mechanics at MVP." Retitled and rewritten;
  dissolves the switching-while-open `_TBD:` — there is no switch.
<!-- product-spec:end -->
