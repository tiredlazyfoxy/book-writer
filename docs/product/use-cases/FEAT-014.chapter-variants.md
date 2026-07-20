<!-- product-spec:start -->
# Use Cases — FEAT-014 Chapter variants & fixes

### UC-058 — Edit a reopened chapter, creating a variant
- **Feature:** FEAT-014 · **Actor:** ACT-004, ACT-005
- **Preconditions:** Chapter is open after being reopened (UC-037).
- **Main flow:**
  1. Member edits the reopened chapter's blocks.
  2. Member saves the edit.
  3. System keeps the chapter's previous text as a variant, readable by
     authors.
  4. Owner closes the chapter again, completing the fix (UC-065).
- **Exception flow:** The edit results in text identical to the original →
  `_TBD: whether an edit identical to the original still creates a new
  variant or is a no-op — not stated._`
- **Postconditions:** Chapter has an additional variant; following chapters
  are unaffected.
- **Source:** `[confirmed: user]` interview 2026-07-20, "Augment round 3 —
  variants, cloning & consistency", "chapter variants & fixes": "It becomes
  a fix, and the chapter keeps all its variants, shown to authors. Following
  chapters stay."

### UC-059 — View and compare a chapter's variants
- **Feature:** FEAT-014 · **Actor:** ACT-004, ACT-005
- **Preconditions:** Chapter has one or more variants.
- **Main flow:**
  1. Member opens a chapter's variant list.
  2. System shows all variants, marking the active one.
  3. Member selects two variants to compare.
  4. System shows their differences.
- **Exception flow:** Chapter has only one variant (never fixed) → nothing
  to compare; the single variant is shown.
- **Postconditions:** None (read-only); all variants stay visible regardless
  of which is active.
- **Source:** `[confirmed: user]` interview 2026-07-20, "chapter variants &
  fixes": "we need the easy way to 'see' the variants."

### UC-060 — Select the active variant
- **Feature:** FEAT-014 · **Actor:** ACT-004
- **Preconditions:** Chapter has two or more variants.
- **Main flow:**
  1. Owner opens the chapter's variant list.
  2. Owner selects a non-active variant.
  3. System makes it the active variant — the chapter for reading,
     generation context and export.
  4. System runs the same consistency-check path as a fix (FEAT-016), since
     the chapter's text changed.
- **Exception flow:** Chapter is open elsewhere at the time of the switch →
  `_TBD: whether the switch is refused while the chapter is open or applies
  once closed — not stated._` Non-owner attempts to select the active
  variant → refused.
- **Postconditions:** Selected variant is now the active one; the
  previously active variant remains readable history.
- **Source:** `[confirmed: user]` interview 2026-07-20, "chapter variants &
  fixes": "The owner picks one active variant... switching changes the
  chapter's text, so it takes the same path."
<!-- product-spec:end -->
