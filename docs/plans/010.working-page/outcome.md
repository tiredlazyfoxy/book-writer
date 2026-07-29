# 010.working-page — outcome

Intended documentation changes once this feature ships, grouped by target file, for the architect to
apply at finalization. The planner writes this section; the coder appends `## Observations` below.

## `docs/architecture/frontend.md`

1. **Section:** `vite.config.ts` shape.
   **Change:** the `work` and `read` Rollup inputs are no longer future tense — the config has five
   inputs, and `spaFallback` branches `/work` and `/read` before its catch-all `else`. Update the
   code block and drop "three inputs today; five once the book domain lands".
   **Reason:** step 001 lands them; the doc's hedged wording would otherwise read as pending work.

2. **Section:** Folder layout.
   **Change:** record `src/work/` (`main.tsx`, `App.tsx`, `routes.tsx`, `workGate.ts`, `pages/`,
   `components/shell/`, plus the two root modules `subject.ts` and `restoreBuffer.ts`) and `src/read/`
   as real. State that the **`read` entry is a stub** — a table-of-contents placeholder with no router
   and no gate; the reader's real build is still out.
   **Reason:** the five-entry layout is now partly built, and the stub's shallowness must not be read
   as the designed reader.

3. **Section:** Persisted-state exception — the working page's restore buffer.
   **Change:** point the paragraph at the real module (`src/work/restoreBuffer.ts`) and note that it
   ships as a pure module with no editable subject wired to it yet.
   **Reason:** the exception is now concrete; naming the module keeps the sanction attached to one
   file rather than to a concept.

4. **Section:** Testing.
   **Change:** the line "No frontend test runner is configured in the scaffold today" is stale (Vitest
   is configured). Additionally record the convention this feature establishes: specs mock **`api/`
   resource modules** (first done in `tests/user/BookshelfPage.test.tsx`), never `fetch`.
   **Reason:** the doc's guidance is written as future tense for something now in daily use.

## `docs/architecture/frontend-workspace.md`

5. **Section:** Build and serving changes.
   **Change:** mark the `vite.config.ts` and `spaFallback` items done, and mark the nginx item
   **pending with a reason**: `nginx/` and both `docker-compose*.yml` do not exist in this repository
   yet, so `/work` and `/read` static serving must be added when that serving layer is first created.
   The same pending item applies wherever `dev-environment.md` / `system-overview.md` describe nginx
   static roots.
   **Reason:** the doc implies an nginx change this feature would make; there is nothing to change.

6. **Section:** The working page.
   **Change:** record that the workspace shell renders the repository's **first `<Outlet/>`**, and that
   the precedent is now deliberately split — `AdminShell` keeps `children` (and its comment about a
   repo with no `<Outlet/>` should be re-worded), while `WorkspaceShell` uses `<Outlet/>` because it is
   keyed on `:bookId` and must not remount when the subject route changes.
   **Reason:** an in-code comment currently asserts a repo-wide property that stops being true here.

7. **Section:** The working page / Route map.
   **Change:** record that **subject pages load their own data by URL id**, so the shell's
   `getBookDetail` load serves navigator and header chrome only and the landing view fetches the book
   again; `useOutletContext` was rejected because it is React context, which `frontend.md` bans.
   Record alongside it that the shell keyed on `:bookId` is treated as the page-level mount for
   `frontend.md`'s "`useEffect` only at page level" rule.
   **Reason:** both are non-obvious readings of existing rules that later features will copy.

8. **Section:** Content pane — subject and editability.
   **Change:** name `src/work/subject.ts` as the single enforcement point the table lives in, and
   state that no editable subject is wired to it yet — the first writers are `013.codex` and
   `015.chapter-writing-free-mode`, and both must route their saves through its write check, as the
   Stage-5 assistant will.
   **Reason:** the symmetry in US-097.AC-2 only holds if every later writer knows where the gate is.

9. **Section:** Draft-until-saved and the restore buffer → "Returning to a stale buffer".
   **Change:** the sentence "the **manual path ships with the buffer** and is not optional" needs
   re-wording: the buffer ships here as a pure module, and the reconciliation/divergence view ships
   with the **first editable subject** (`013.codex` / `015.chapter-writing-free-mode`). "Not optional"
   stays true; "ships with the buffer" does not.
   **Reason:** a user-confirmed scope decision for this feature that contradicts the doc's current
   wording — recorded rather than silently diverged from.

10. **Section:** Navigator (UC-090) — Book state.
    **Change:** record that the landing view currently aggregates the **book's own fields only**;
    US-106.AC-2/AC-3 (per chapter: title, summary, after-chapter note changeset, active warnings) are
    deferred to `016.chapter-close-continuity` and ship as a labelled empty state. Record likewise
    that every other navigator section is an empty state naming its owner (`013.codex`,
    `014.chapter-skeleton`, `018.chapter-history-variants`, `011.chat-panel`), because no chapter,
    codex, continuity, variants or chat endpoint exists.
    **Reason:** the navigator is built but only one section has data; the doc should say which.

## `docs/architecture/domain-book.md`

11. **Section:** Book (the field table).
    **Change:** note that `system_prompt` and `active_notes` are entity fields **not exposed on the
    wire** — `BookResponse` / `BookDetailResponse` carry neither — so the Book-state landing view
    cannot render them and ships a labelled empty state for the state notes. Whichever feature first
    needs them must extend the books API response and `src/types/books.d.ts` together.
    **Reason:** UC-091's landing view is the first consumer of both fields and hits the gap directly.

---
Status: Applied 2026-07-29
Applied items: 11
Rejected items: 0 (3 modified — notes below)

Landed in `frontend.md`, `frontend-workspace.md`, `frontend-work-drafts.md` (the draft-tier items moved there when the file was split) and `domain-book.md`.

Modifications, all because later features overtook the wording:

- **Item 11 (the wire gap) narrowed to `active_notes` only.** Feature `021.per-author-system-prompt` made `Book.system_prompt` **dormant**, so documenting how to expose it would point the next reader at a dead column. `domain-book.md` records the `system_prompt` half as **dissolved rather than closed** — replaced, not exposed.
- **Item 10 (navigator empty states) updated to current state.** Features 011 and 013 filled the Chats and Characters/Locations/Facts sections it described as empty; only the chapter, variants and continuity sections remain empty states naming their owners.
- **Item 8's "no editable subject wired yet" superseded by feature `013.codex`**, which shipped the codex entry page as the content pane's first real editor.

`/product-spec` finalization has **not** run for this feature, so no `**Delivered:**` markers were written to `docs/product/`.

## Observations
