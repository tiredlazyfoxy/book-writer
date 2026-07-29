# Outcome — 009.books (intended doc changes after ship)

Planner-intended documentation updates, applied by the architect / product-spec at
finalization. The coder appends `## Observations` at the bottom.

## `docs/architecture/authorization.md`

- **Section "Not settled by this pass" → "Whether an archived book refuses writes".**
  Intended change: **keep it open** — record that 009 delivered the `BookAccess`
  resolver + `authz` spine and that `BookAccess` resolves `book_state`, but 009
  deliberately built **no** write-refusal capability; the question is deferred to
  the write feature (010/014). Reason: nothing in 009 writes book content, so the
  archived-write behaviour cannot be exercised or decided here.
- **Section "Enforcement — resolve in a dependency, decide in a service".**
  Intended change: add a delivery note pointing at `docs/plans/009.books/` as the
  first implementation of the `book_access` dependency + `services/authz.py`
  capability matrix (owner-only lifecycle/settings + reader `read_book` rows). Note
  that `admin` role resolution and the quarantined/destroyed gates remain deferred
  to FEAT-011. Reason: the doc should point to where the spine now lives.

## `docs/architecture/domain-book.md`

- **Section "Visibility".** Intended change: note that the reader path is delivered
  in 009 as an **access-controlled backend projection only** (public + logged-in →
  reader-safe DTO; TOC/chapter content is an empty placeholder until Stage 5), and
  that the dedicated reader Vite entry is **not** built yet. Reason: record the
  divergence between the designed reader entry and what 009 actually ships.

## `docs/architecture/frontend-workspace.md`

- **Section "Route map → Shell (`/`)".** Intended change: note that `/` (bookshelf)
  and `/books/:bookId/settings` are delivered by 009 on the existing `index.html`
  Shell entry; the `read/` reader entry and the `/books/:bookId` hub / codex /
  continuity routes remain unbuilt. Reason: mark which Shell routes now exist.

## `docs/product/features.md`

- **FEAT-006 block.** Intended change: add
  `**Delivered:** docs/plans/009.books/ (YYYY-MM-DD)` — noting UC-025 (US-026) and
  US-024.AC-3 / AC-4 remain deferred (see the plan's Deferred table). Reason: the
  delivery-record convention (`docs/product/CLAUDE.md` → "Citation convention").
- **FEAT-007 block.** Intended change: add
  `**Delivered:** docs/plans/009.books/ (YYYY-MM-DD)` — noting US-028.AC-2 / AC-3
  remain deferred (blocks/attribution land with chapters). Reason: same convention.

---
Status: Applied 2026-07-29
Applied items: 4
Rejected items: 0

All four architecture items applied **as written**, in `authorization.md` (2), `domain-book.md` → "Visibility" (1) and `frontend-workspace.md` → "Route map → Shell" (1). Additionally, the `/api/books` route family, its DTOs and its 401 / 404-existence-hiding / 403 / 409 taxonomy were indexed in `quick-reference.md`, sourced from this feature's `status.md` (`## Skeleton`); `backend/features.md` records the as-shipped section as **owed** rather than reconstructing it from source.

The two **`docs/product/features.md`** items are **`/product-spec`'s and were not applied** — product finalization has not run, so no `**Delivered:**` markers were written to `docs/product/`.
