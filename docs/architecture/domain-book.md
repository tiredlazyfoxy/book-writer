# Domain — Book, membership and lifecycle

**Realizes:** FEAT-006 (UC-021..025), FEAT-007 (UC-026..030, UC-063), FEAT-010 (UC-042), FEAT-011 (UC-044..046), FEAT-012 (UC-091), FEAT-015 (UC-061..063, US-133), FEAT-021 (UC-103..UC-107; US-123, US-124, US-127, US-128)

Part of the book-domain model. **Index and cross-cutting conventions: `domain-model.md`.** Related: `domain-chapter.md` (chapters and the write path), `domain-continuity.md` (the note changesets `active_notes` accumulates), `authorization.md` (who may do any of this), `assistant-runtime.md` (where `BookAuthorPrompt` and the author's active memos land in the composed system prompt).

## Book

| Field | Type / notes |
|---|---|
| `id` | snowflake PK |
| `title` | display title |
| `description` | free text, may be empty |
| `owner_id` | FK → `User.id`. Exactly one owner at all times (UC-021, UC-024, UC-025) |
| `collaboration_mode` | `free` \| `proposal` (FEAT-010, UC-042) |
| `visibility` | `private` \| `public` (UC-028). Public = read-only to any **logged-in** user, never anonymous |
| `state` | `active` \| `archived` \| `quarantined` \| `destroyed` |
| `moderation_reason` | the admin's stated reason for quarantine / destroy (UC-044); null until moderated |
| `moderated_by` | FK → `User.id` — which admin acted; null until moderated |
| `moderated_at` | when; null until moderated |
| `system_prompt` | **dormant** — superseded by `BookAuthorPrompt` and read by nothing. Still non-null, still written `""` at creation, still exported. See "`Book.system_prompt` is dormant" below **before** deleting it |
| `active_notes` | the **materialised** live state-note set (free text). Not exposed on the wire — see below |
| `created_at` / `modified_at` | timestamps |

**One lifecycle column, not two.** FEAT-006's owner-facing archive (UC-023, reversible) and FEAT-011's admin quarantine → destroy (UC-044/UC-045, moderation) are different actors and different reversibility, but they are mutually exclusive states of the same book. Modelling them as one enum rather than two booleans means every read path answers "may this book be shown at all?" from one field and cannot get the two out of step (a book that is both archived and destroyed is unrepresentable).

`destroyed` is a **tombstone state, not a deleted row** — consistent with the system's archive-not-delete stance for users (FEAT-003), books (UC-023) and codex entries (UC-072), and it keeps `owner_id` available so UC-046's removal notice still has a book to point at.

**`active_notes` is materialised, not recomputed.** The alternative — replaying every chapter's changeset to derive the live set — was rejected because the live set is pushed into **every** chat's context baseline (US-057.AC-3), so it is read on every assistant turn and would be recomputed constantly for a value that changes only at chapter close. The cost is one denormalisation to keep honest: the chapter close path (UC-047/UC-048) is the **only** writer that must update both the chapter's changeset and `Book.active_notes`, and UC-050's direct note edits write `active_notes` alone. The changeset mechanics themselves are in `domain-continuity.md`.

### `active_notes` is not on the wire

`active_notes` is an entity field with **no exposure on the wire**: neither `BookResponse` nor `BookDetailResponse` carries it. UC-091's Book-state landing view is its first consumer and hit the gap directly (feature `010.working-page`), so that view ships a **labelled empty state** for the state notes rather than rendering them. Whichever feature first needs the value must extend the books API response schema and `frontend/src/types/books.d.ts` **together** — the two are hand-kept in step (root `CLAUDE.md` → "API Typing — Full Stack"), and widening one alone is the failure that convention exists to prevent.

`system_prompt` was the other half of this same gap when features `010.working-page` and `011.chat-panel` recorded it. **That half is dissolved rather than closed:** feature `021.per-author-system-prompt` replaced the field instead of exposing it. The per-author prompt has its own route pair — `GET` / `PUT /api/books/{book_id}/system-prompt` (`backend/features.md`) — and deliberately no field on `BookDetailResponse`, because a **per-caller** value cannot ride on a book-shaped DTO: two authors reading the same book would need two different values in one response.

### `Book.system_prompt` is dormant

**`Book.system_prompt` is superseded and read by nothing.** Feature `021.per-author-system-prompt` replaced the book-wide prompt with a per-author one (`BookAuthorPrompt`, below). The author layer the assistant composes is now the prompt of **the author running the turn**; **there is no book-wide layer at all.** Composition order lives in `assistant-runtime.md` → system-prompt composition, not here.

**The column is retained rather than dropped, deliberately.** `db/engine.py` exposes only an *additive* migration seam and the project has no Alembic, so there is **no supported DROP COLUMN path**. The column is therefore still required, still written `""` at book creation, and still round-trips through the JSONL codec so that archives written before the replacement still import. A dead-but-documented column beats an unsupported migration — but it has to be documented, because a reader who deletes it on the strength of "nothing reads it" breaks every existing database file.

**`Chapter.system_prompt` had nothing left to append to, and went the same way.** It was defined as narrowing the book-wide prompt (`domain-chapter.md`); that base layer is gone. Feature `014.chapter-skeleton` answered the question this paragraph used to leave open by **replacing the field rather than redefining it** — the per-chapter prompt is now `ChapterAuthorPrompt`, one row per `(chapter, author)`, on exactly the terms below. `Chapter.system_prompt` is dormant on the same terms as this column: retained, unread, still exported. See `domain-chapter.md` → "The chapter prompt moved off `Chapter.system_prompt`".

Recorded as the fifth — and the only **open** — product divergence in `domain-model.md` → "Product divergences", which also annotates item 3 as partly reversed.

### Fields deliberately *not* invented

No `genre`, `target_length`, `language`, or cover art. No requirement in `docs/product/` asks for any of them, and UC-091/US-106.AC-4 explicitly leaves the Book-state field list `_TBD:` rather than naming fields. The list above is exactly what a stated requirement needs, and nothing else.

### The moderation fields

UC-044 requires an admin to quarantine **with a reason**, and UC-046 requires the owner to be shown it — "the owner sees a removal notice, with a reason. Not silent." That notice is the *only* thing the owner gets in place of their book, so the reason is not decoration: it is the entire content of the response.

`moderated_by` and `moderated_at` are carried alongside it because a moderation action is an **exercise of admin power over someone else's work**, and an unattributed one is not reviewable. `state` alone records that a book was taken down; the three fields together record who did it, when, and why — which is what makes the action auditable after the fact and what lets a later release decision (product's open `_TBD:`) be made by someone other than the admin who acted.

All three are **nullable and null on an `active` book**. They are written together, by the quarantine path only, and they land at Stage 2 with the rest of the table even though FEAT-011 is Stage 6 — the same additive-nullable reasoning recorded in `domain-model.md`.

## Book lifecycle

```
                  archive (owner, UC-023)
        active ──────────────────────────► archived
          │   ◄──────────────────────────      │
          │        unarchive (owner)           │
          │                                    │
          │  quarantine (admin, UC-044)        │
          └────────────┬───────────────────────┘
                       ▼
                 quarantined ──destroy (admin, UC-045)──► destroyed
```

- **Archive is the owner's reversible action** (UC-023). A book is never destroyed on the owner-facing path; content and history are preserved.
- **Quarantine → destroy is the single sanctioned exception**, admin-only and scoped to FEAT-011 moderation. Destroy **requires** the quarantine step first (UC-045 exception flow) — an admin cannot skip straight to it.
- A quarantined book is invisible to **everyone including its members**; the owner is shown the removal notice instead of the content (UC-046).
- `_TBD:` in product: whether a quarantined book can be released back to its members. Not resolved here.

Where each state leaves the capability matrix, including which roles see what, is `authorization.md` → "Book state and visibility gates".

## Visibility

`visibility` is a two-value field with one rule behind it: **public means read-only to any *logged-in* user, never anonymous** (UC-028, UC-029, challenge C4). There is no anonymous surface anywhere in the system.

Visibility also gates one non-read capability: **only the owner may clone a private book** (challenge C21, stated in both FEAT-007 and FEAT-015); a co-author may clone a public one. See `authorization.md`.

What a reader actually gets is deliberately narrow — the table of contents and chapter text, and nothing else (UC-029's exclusion list). That exclusion is enforced at build time by giving the reader its own frontend entry; see `frontend-workspace.md`.

**As delivered, the reader path is an access-controlled backend projection only** (feature `009.books`). A public book reached by a logged-in non-member resolves to a **reader-safe DTO**, and the TOC / chapter content inside it is an **empty placeholder until Stage 5**, because no chapter content exists to project yet. **The dedicated reader Vite entry is not built:** feature `010.working-page` shipped `read/` as a stub — no router, no gate.

The divergence is recorded rather than smoothed over: the build-time exclusion above is still the *design*, but what enforces UC-029's exclusion list today is the backend projection alone. Whoever builds the reader entry inherits both halves and must not assume the frontend gate already exists.

## BookMember

| Field | Type / notes |
|---|---|
| `id` | snowflake PK |
| `book_id` | FK → `Book.id` |
| `user_id` | FK → `User.id` |
| `role` | co-author role marker |
| `created_at` | timestamp |

A snowflake PK plus a **unique `(book_id, user_id)`** constraint, rather than a composite natural key, because the id convention is system-wide with no permanent exceptions (`backend/auth-ids.md`) and a surrogate id keeps the import/export codec identical in shape to every other table. The unique constraint carries the "one membership per user per book" semantics.

**The owner is not a `BookMember` row.** Ownership lives in `Book.owner_id`; membership is co-authorship. This keeps UC-024 (transfer) a single-field update and makes "exactly one owner" a structural guarantee rather than a rule some query must enforce. *Member*, across all the domain docs, means owner **or** co-author.

**Readers (ACT-006) have no row at all.** Reader access derives from `Book.visibility` — there is nothing to grant and nothing to revoke. See `authorization.md`.

Removing a co-author revokes access but leaves their content and attribution in the book (UC-027) — which is exactly what `ChapterChange.author_id` (`domain-chapter.md`) preserves, since attribution is a field on the change, not a join through membership.

## BookAuthorPrompt

| Field | Type / notes |
|---|---|
| `id` | snowflake PK |
| `book_id` | FK → `Book.id` |
| `user_id` | FK → `User.id` |
| `system_prompt` | required; `""` means "no prompt" |
| `created_at` / `modified_at` | timestamps |

One row per `(book, author)`, holding that author's own standing instruction to the assistant inside that book. It is what replaced `Book.system_prompt` (above), delivered by feature `021.per-author-system-prompt`.

**A surrogate snowflake PK plus a unique `(book_id, user_id)`** — `BookMember`'s shape, adopted for `BookMember`'s stated reasons: the id convention is system-wide with no permanent exceptions (`backend/auth-ids.md`), and a surrogate id keeps the import/export codec identical in shape to every other table. The unique constraint carries the "exactly one prompt per author per book" semantics.

**The prompt cannot hang off `BookMember`, and that is the load-bearing reason this is a table of its own.** The owner has **no `BookMember` row** — ownership lives in `Book.owner_id` — so a membership-hosted prompt would be unreachable for exactly the author most likely to write one. Keying on `(book_id, user_id)` instead reaches owner and co-author alike, without making ownership a membership row and undoing the "exactly one owner" structural guarantee above.

**`""` rather than a nullable column** so that "no prompt" has one representation and not two; the composer's empty-contributes-nothing rule then needs no null branch.

Who may read and write a row is a **row-ownership rule, not a capability** — see `authorization.md` → "Chats, per-author prompts and memos — four row-ownership rules" (retitled from "three" when FEAT-021 added the fourth). Where the value lands in the composed prompt, and which author's row the turn resolves, is `assistant-runtime.md`'s. Its per-chapter sibling, `ChapterAuthorPrompt`, is in `domain-chapter.md`.

**No product id is cited for this entity, deliberately.** `BookAuthorPrompt` realizes a *replacement* for FEAT-019's book half, and FEAT-019's current ids (UC-093, US-108) describe a book-wide, owner-only prompt that no longer exists — US-108.AC-2 is reversed outright rather than superseded. Citing them here would claim satisfaction of criteria this design contradicts, which is why feature `021`'s own plan cited none of them as met. `/product-spec` must rewrite FEAT-019 first; the ids it mints are what a later feature will cite. Recorded as the open fifth divergence in `domain-model.md` → "Product divergences".

## Memo

**Realizes:** FEAT-021 — UC-103..UC-107; US-123, US-124, US-127, US-128. Where an active memo lands in the composed system prompt, and the `create_memo` tool that writes one, are `assistant-runtime.md`'s; the routes and DTOs are `quick-reference.md`'s.

| Field | Type / notes |
|---|---|
| `id` | snowflake PK |
| `book_id` | FK → `Book.id` |
| `user_id` | FK → `User.id` — the memo's author. Nobody else, **including the book's owner**, ever reads it (US-124) |
| `body` | required text; **`""` is legal** — a new memo is created empty and focused (UC-103, US-123) |
| `ordinal` | non-null int — the memo's position **within that author's list in that book** |
| `active` | bool, default `true` — the everyday on/off switch (UC-106, US-127) |
| `archived` | bool, default `false` — out of the working list, restorable (UC-107, US-128) |
| `created_at` / `modified_at` | timestamps |

One author's standing notes for one book: what they want the assistant to remember, in the order they want it delivered.

**There is no unique constraint on `(book_id, user_id)`, and this is the thing a reader will get wrong.** The field list above is `BookAuthorPrompt`'s shape almost exactly, and both `BookAuthorPrompt` and `BookMember` carry a unique `(book_id, user_id)`. A memo must not: **an author has many memos per book** — that is the whole feature. The surrogate snowflake PK is kept for the usual reason (`backend/auth-ids.md`): the id convention is system-wide with no permanent exceptions, and a surrogate id keeps the import/export codec identical in shape to every other table.

**Two booleans, not one state enum — the deliberate opposite of `Book.state`.** `Book` models archive and destroy as **one** enum precisely because they are mutually exclusive states of one book. Product states the opposite here: inactive and archived are **two axes, not one mechanism**. Two flags are the only shape that remembers whether a restored memo was switched *on* or *off* before it was archived; a three-value enum (`active` | `inactive` | `archived`) would lose that, and the author would come back from the archive to a memo in a state they never chose.

**Context membership is derived, not stored.** A memo reaches the assistant iff `archived == false AND active == true` (US-131.AC-3). `active` is only *meaningful* when the memo is not archived — an archived memo is out of context regardless of its flag — and that is a **derived reading rule, not a constraint to enforce**. There is no invalid combination to refuse, only one that has no effect on the prompt.

**No version token, no `409`, no optimistic concurrency.** This follows the `BookAuthorPrompt` / `ChapterAuthorPrompt` precedent rather than the `CodexEntry` one, where `modified_at` *is* the version token: a memo is short, saved on focus loss within moments of being typed, and has **exactly one writer — its owner**. The non-obvious half is that the assistant does not break that property: the `create_memo` tool only ever **creates** a row and never edits an existing one (`assistant-runtime.md`), so "one writer per existing row" holds even with the tool in play.

**`ordinal` is scoped per `(book, author)`, and gaps are left alone.** A new memo is appended at `max + 1` (US-123.AC-1, US-129.AC-3). Archiving **leaves a gap and does not renumber** — the `chapters` DELETE precedent (`quick-reference.md`). **A restore appends last, at `max + 1`, rather than returning to its old slot** (US-128.AC-2). That was chosen so one rule covers every way a memo arrives in the list — manual create, assistant create, restore — and so no stale ordinal can collide with an order the author rewrote while the memo was archived. The consequence is worth stating because it is what makes the list read simple: **no `(ordinal, id)` tiebreak is needed**, since no two live rows in one author's list can share an ordinal.

**Not vector-backed, deliberately.** No `VECTOR_SOURCE_REGISTRY` entry: every active memo is pushed whole into every turn, so there is nothing to retrieve and no relevance question to answer (`retrieval.md`, `domain-model.md` → "Two registry obligations").

Who may read and write a row is a **row-ownership rule, not a capability** — `authorization.md` → "Chats, per-author prompts and memos — four row-ownership rules".

## Cloning — no entity of its own

**Realizes:** FEAT-015, UC-061, UC-062, UC-063, US-067, US-094, US-133

A clone is a **new `Book` with new rows**, deep-copied from the source across chapters, changes, revisions, note changesets, codex entries, membership (per the cloner's selection, UC-063), collaboration mode and visibility. There is no clone link, no parent id, no sync — product is explicit that the two books are fully independent and drift apart permanently (US-067), so a parent pointer would model a relationship the product deliberately does not have, and would tempt later features to use it.

The cloner becomes the new book's owner regardless of which role they held on the source (UC-062, US-068).

Moderation does not reach clones (challenge C22, stated as a limitation in FEAT-011): an independent clone made before or after a book is quarantined or destroyed is unaffected, and an admin moderates each book separately. That falls out of the no-link design rather than needing to be enforced.

### The clone copies the cloner's memos (US-133)

A clone copies **the cloner's own memos**, as of clone time, and **no other member's** (US-133.AC-1/AC-2) — nobody can read another member's memos, so there is nothing to copy. The copies are ordinary independent rows: **no clone link and no parent pointer**, unchanged from the rule above.

**Memos are the first per-author row a clone copies**, and the contrast is deliberate rather than an oversight: **`BookAuthorPrompt` is not copied** — the deep-copy list above does not include it, and FEAT-019 states outright that prompts do not carry over.

**The divergence between the two is coherent, and product states the reasoning.** A memo records **book-shaped knowledge** — what to remember about this book — so it travels with the book. A system prompt is **personal style** — how the assistant should write for this author — so it does not. Written down here because a later reader comparing the two per-author tables will find the same shape, the same key and the opposite clone behaviour, and will otherwise read it as an inconsistency to be fixed.
