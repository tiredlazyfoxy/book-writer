# 014.chapter-skeleton — Chapter skeleton & sketches
<!-- roadmap:start -->
- **Stage:** 5.chapters · **Track:** multi-step · **Size:** M/L
- **Delivers:** FEAT-008, FEAT-019 (chapter half), UC-094, US-109
- **Depends on:** `009.books`

## Definition
Build a book's chapter skeleton from the book hub: add a chapter, reorder
chapters, edit a planned chapter's sketch, and remove a planned chapter. Any
book member can also set or clear a chapter's own system prompt, which
narrows the book's.

## Scope
**In:** UC-031..034; US-032..035. Chapter placement/ordering; the
`planned` state. UC-094 / US-109 — set and clear `Chapter.system_prompt`
(**any book member**, per FEAT-019).
**Out:** opening/writing a chapter (`015.chapter-writing-free-mode`);
close/continuity (`016.chapter-close-continuity`); variants
(`018.chapter-history-variants`).

## Open questions for the planner
- The chapter layer above the db is greenfield: there is no
  `services/chapters.py`, `routes/chapters.py` or `models/schemas/chapters.py`,
  and `db/chapters.py` has no `update`. This feature creates that column.
- Chapter authorization does not exist yet — `authz.Capability` has no chapter
  member and `BookAccess` is book-scoped, so a chapter → `book_id` resolution
  is needed. FEAT-019's chapter rule is **any member**, a role set the current
  matrix does not have (mutations there are owner-only).
- `domain-chapter.md` covers placement; the FEAT-019 chapter rule is *not*
  yet in `authorization.md` (`domain-model.md` divergence 3 defers it).
<!-- roadmap:end -->
