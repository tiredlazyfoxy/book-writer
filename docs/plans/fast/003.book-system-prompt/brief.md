# fast/003.book-system-prompt — Book-wide system prompt

<!-- roadmap:start -->
> **RETIRED 2026-07-31 — do not plan or build this.** Superseded by
> `docs/plans/021.per-author-system-prompt/` (delivered 2026-07-29). FEAT-019
> pivoted from a book-wide prompt to a **per-author** one: UC-093 and US-108,
> which this brief delivers, are tombstoned `withdrawn` in
> `docs/product/quick-reference.md` (→ UC-098 / → US-115), and
> `Book.system_prompt` is no longer read by
> `backend/app/services/prompt_composition.py` — it composes
> `BookAuthorPrompt.system_prompt` instead. The definition below is kept as
> decision history only; every "Open question" in it was answered differently
> by `021`. See `roadmap.md` → "Retired features".

- **Stage:** 3.workspace · **Track:** fast · **Size:** S/M
- **Delivers:** FEAT-019 (book half), UC-093, US-108
- **Depends on:** `009.books`

## Definition
The book owner can read and edit the book-wide system prompt that every chat
in the book inherits. Today the field is persisted but has no surface at
all: it is set to `""` at creation and never editable afterwards. This
closes the FEAT-019 book half so the prompt the assistant already composes
into every chat is actually authorable. Owner-only, per FEAT-019's
owner-only/any-member split.

## Scope
**In:**
- Expose `Book.system_prompt` on the book read path and add an owner-only
  update path for it.
- The edit surface itself in the user SPA.
- Frontend api/type wiring for both.

**Out:**
- The chapter system prompt — `014.chapter-skeleton`.
- The five admin assistant mode prompts — `012.assistant-config-editor`.
- How prompts are assembled into a chat — `prompt_composition.py` already
  composes `base → mode → book → chapter` and already reads this field.
- Whether the prompt reaches the FEAT-016 consistency check (it does not —
  instructions, not content).

## Open questions for the planner
- Which surface(s) — candidates: the existing owner-only `BookSettingsPage`
  (`/books/:bookId/settings`) as the edit surface, and/or the working-page
  book hub (`BookStatePage`) as a read-only display. Either way
  `BookDetailResponse` (or a dedicated GET) must carry the value so the
  surface can read it.
- Three schema docstrings in `backend/app/models/schemas/books.py` and the
  `frontend/src/types/books.d.ts` wire type currently declare
  `system_prompt` **deliberately omitted** from the response DTOs. Those
  comments and the decision behind them must be revised, not worked around.
- FEAT-019's authorization rule is a known documentation gap:
  `docs/architecture/authorization.md` still lists "who may edit the book-
  and chapter-level system prompts" as an open item, and `domain-model.md`
  divergence 3 records the `**Realizes:** FEAT-019` headers as a deferred
  follow-up. Reconcile as part of this feature's `outcome.md`.
<!-- roadmap:end -->
