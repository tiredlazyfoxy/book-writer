<!-- product-spec:start -->
# Stories — FEAT-014 Chapter variants & fixes

### US-062 — Editing a closed chapter creates a new variant
- **Feature:** FEAT-014 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-058
- **Status:** proposed
- **Story:** As a book member, I want editing a reopened chapter to keep
  the previous text as a variant, so that I can recover it if the fix
  doesn't work out.
- **Acceptance criteria:**
  - **US-062.AC-1** — Given a closed chapter is reopened and edited, when
    the edit is saved, then the chapter's previous text is retained as a
    variant.
  - **US-062.AC-2** — Given a chapter gains a variant from an edit, when
    the following chapters are inspected, then they remain unchanged.
- **Source:** `[confirmed: user]` interview 2026-07-20, "chapter variants &
  fixes": "the chapter keeps all its variants... Following chapters stay."

### US-063 — Member views and compares a chapter's variants
- **Feature:** FEAT-014 · **Actor:** ACT-004, ACT-005 · **Realizes:** UC-059
- **Status:** proposed
- **Story:** As a book member, I want to see and compare a chapter's
  variants, so that I can judge whether a fix improved it.
- **Acceptance criteria:**
  - **US-063.AC-1** — Given a chapter with two or more variants, when a
    member opens the variant list, then all variants are shown.
  - **US-063.AC-2** — Given a chapter with two or more variants, when a
    member opens the variant list, then the active variant is marked as
    such.
  - **US-063.AC-3** — Given two variants selected, when a member requests a
    comparison, then their differences are shown.
- **Source:** `[confirmed: user]` interview 2026-07-20, "chapter variants &
  fixes": "we need the easy way to 'see' the variants."

### US-064 — Owner selects which variant is the chapter
- **Feature:** FEAT-014 · **Actor:** ACT-004 · **Realizes:** UC-060
- **Status:** proposed
- **Story:** As a book owner, I want to choose which variant is the
  chapter's active text, so that I control what readers, generation and
  export use.
- **Acceptance criteria:**
  - **US-064.AC-1** — Given a chapter with multiple variants, when the
    owner selects a non-active variant, then it becomes the active
    variant.
  - **US-064.AC-2** — Given a co-author (not the owner), when they attempt
    to select the active variant, then the action is refused.
- **Source:** `[confirmed: user]` interview 2026-07-20, "chapter variants &
  fixes": "The owner picks one active variant."

### US-065 — Switching the active variant is treated as a fix
- **Feature:** FEAT-014 · **Actor:** ACT-004 · **Realizes:** UC-060
- **Status:** proposed
- **Story:** As a book owner, I want switching the active variant to run
  the same checks as a fix, so that inconsistencies the switch introduces
  are caught.
- **Acceptance criteria:**
  - **US-065.AC-1** — Given the owner switches the chapter's active
    variant, when the switch completes, then the chapter's consistency
    check runs the same as it would after a fix (FEAT-016).
- **Source:** `[confirmed: user]` interview 2026-07-20, "chapter variants &
  fixes": "switching changes the chapter's text, so it takes the same
  path."
<!-- product-spec:end -->
