# Outcome — 022.reader-mode

Intended doc changes, applied at finalization. Planner records intent only; `docs/architecture/` is not
edited from here.

## `docs/architecture/quick-reference.md`

- **Endpoints table (`/api/books`)** — add `GET /api/books/public` (declared after `GET /shared`, before
  `GET /{book_id}`); update `GET /{book_id}/read` row — response is still `ReaderBookResponse` but
  `chapters` is now `list[ReaderChapterRef]`, not an empty placeholder; add
  `GET /{book_id}/read/chapters/{chapter_id}` → `ReaderChapterResponse`.
- **DTOs section** — `ReaderBookResponse` row (currently `chapters: list[str]`, line 227) changes to
  `chapters: list[ReaderChapterRef]`; the "empty placeholder TOC" note at line 64 retires; add
  `ReaderChapterRef`, `ReaderChapterResponse`, `PublicBookRef`, `PublicBookListResponse` — all now living in
  `models/schemas/reader.py`, a new module.
- **Tables & enums / module index** — `db/books.py` gains `list_public_for_reader(user_id: int) -> list[Book]`.
- Record the new `routes/reader.py` + `services/reader.py` module pair and that the delivered `/read` route
  + service moved out of `routes/books.py` / `services/books.py` into it.

## `docs/architecture/authorization.md`

- The reader surface's status taxonomy: a chapter that is not reader-visible (`planned`, `closing`, unknown
  id, non-numeric id, another book's chapter) answers **404, not 403** — indistinguishable across all five
  sources — with the enumeration-oracle reasoning (D5), same family as the existing private-book and codex
  entries.
- `GET /api/books/public` is gated by **authentication alone** — no `book_access`, no matrix row — because
  there is no book to resolve a role against (D14). Record it explicitly so the absence of a `BookAccess`
  dependency on this route reads as a match to the FEAT-020 admin-config precedent, not an oversight.

## `docs/architecture/frontend-workspace.md`

- The `/read` route table's "**Neither route is built**" line and its stub note (lines 103-112) retire —
  both routes are now built.
- Add the `src/read/` layout: `readGate.ts`, `main.tsx`, `App.tsx`, `routes.tsx`, `pages/` (TOC page,
  chapter page, not-found page).
- The Shell's bookshelf gains a third "Public books" section (D13, D16) — record it alongside the existing
  "My books" / "Shared with me" description.

## `docs/architecture/frontend.md`

- Folder layout: `src/read/` is no longer a stub — update its description to match the built SPA.

## Root `CLAUDE.md`

- Project Structure block: retire the "`src/read/` is a STUB" parenthetical note.

## Observations

_populated by the coder — the two below are seeded by the planner from the design notes as required
follow-ups; the coder appends further observations below them, never above._

1. **UC-029's `_TBD:` on discoverability was resolved by implementation, without a product id.** This
   feature makes public books browsable by every logged-in user (excluding their own and co-authored
   books), via a new `GET /api/books/public` route and a third bookshelf section. `docs/product/` was
   deliberately **not** edited to close the `_TBD:`. `/product-spec` must mint a use case and story for book
   discovery retroactively, or withdraw the behaviour. This was raised with the user as a divergence from
   `docs/architecture/CLAUDE.md`'s "raise it, don't resolve it by choosing a design" rule and **reaffirmed
   by the user** (design-note D13).
2. **UC-028's `_TBD:` on the public→private flip** is answered with the minimum behaviour: the next request
   refuses (404 from `resolve_book_access`); nothing already rendered is invalidated; there is no polling
   and no push channel (design-note D10). This is a decision about the gap, not a resolution of the
   `_TBD:` — closing the `_TBD:` itself is `/product-spec`'s.
3. **D2's accepted cost.** With the reader-visible set strictly `{open, closed}`, a chapter disappears from
   the table of contents and its link 404s for the duration of every close run (`open → closing → closed`),
   then reappears. Raised with the user and accepted in favour of the brief's stated wording over a set
   that would remove the flicker (`open + closing + closed`).

---
Status: Applied 2026-07-31
Applied items: 11 (all of them; two applied with the modification the orchestrator specified) + 3 additions authorized in the briefing
Rejected items: 0

Notes:

- **Modified — `quick-reference.md`'s "empty placeholder TOC" note.** Deleting the sentence was not enough: the
  reader surface is now three DTOs rather than one, so the whole bullet was rewritten. The structural-exclusion
  claim (separate DTOs, not a field filter) was preserved as the load-bearing part; the exact field sets of
  `ReaderBookResponse` / `ReaderChapterRef` / `ReaderChapterResponse` / `PublicBookRef` were added, and the
  placeholder claim removed.
- **Modified — `frontend-workspace.md`'s "there must never be a third route".** As built there is a third
  `<Route>` (a terminal `*` catch-all). The rule was rewritten as **no third content surface**, with the
  catch-all recorded as required rather than as an exception; UC-029's exclusion list is kept as the spec.
- **Additions (authorized in the briefing, beyond this file):** a new "The reader surface" subsection in
  `authorization.md` (reader-visible set, the accepted close-run gap, the service-side filter, the
  public→private flip, and the no-authorization-change record); `022.reader-mode` added to
  `docs/architecture/CLAUDE.md`'s covered list with the reader surface named; and the root `CLAUDE.md`
  product-layer counts refreshed (see the finalization hand-back for how the id count was restated).
- Product ids cited come from the 2026-07-31 `/product-spec` finalization: UC-029, UC-100, US-029.AC-3,
  US-030, US-118. `docs/product/` was not edited.
