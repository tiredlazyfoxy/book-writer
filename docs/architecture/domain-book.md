# Domain — Book, membership and lifecycle

**Realizes:** FEAT-006 (UC-021..025), FEAT-007 (UC-026..030, UC-063), FEAT-010 (UC-042), FEAT-011 (UC-044..046), FEAT-012 (UC-091), FEAT-015 (UC-061..063)

Part of the book-domain model. **Index and cross-cutting conventions: `domain-model.md`.** Related: `domain-chapter.md` (chapters and the write path), `domain-continuity.md` (the note changesets `active_notes` accumulates), `authorization.md` (who may do any of this).

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
| `system_prompt` | book-wide prompt applied to **all** chats in the book |
| `active_notes` | the **materialised** live state-note set (free text) |
| `created_at` / `modified_at` | timestamps |

**One lifecycle column, not two.** FEAT-006's owner-facing archive (UC-023, reversible) and FEAT-011's admin quarantine → destroy (UC-044/UC-045, moderation) are different actors and different reversibility, but they are mutually exclusive states of the same book. Modelling them as one enum rather than two booleans means every read path answers "may this book be shown at all?" from one field and cannot get the two out of step (a book that is both archived and destroyed is unrepresentable).

`destroyed` is a **tombstone state, not a deleted row** — consistent with the system's archive-not-delete stance for users (FEAT-003), books (UC-023) and codex entries (UC-072), and it keeps `owner_id` available so UC-046's removal notice still has a book to point at.

**`active_notes` is materialised, not recomputed.** The alternative — replaying every chapter's changeset to derive the live set — was rejected because the live set is pushed into **every** chat's context baseline (US-057.AC-3), so it is read on every assistant turn and would be recomputed constantly for a value that changes only at chapter close. The cost is one denormalisation to keep honest: the chapter close path (UC-047/UC-048) is the **only** writer that must update both the chapter's changeset and `Book.active_notes`, and UC-050's direct note edits write `active_notes` alone. The changeset mechanics themselves are in `domain-continuity.md`.

**`system_prompt`** applies to every chat in the book. `Chapter.system_prompt` (`domain-chapter.md`) **appends to** it rather than replacing it. Neither field is covered by any product requirement — see `domain-model.md` → "Product divergences", item 3.

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

## BookMember

| Field | Type / notes |
|---|---|
| `id` | snowflake PK |
| `book_id` | FK → `Book.id` |
| `user_id` | FK → `User.id` |
| `role` | co-author role marker |
| `created_at` | timestamp |

A snowflake PK plus a **unique `(book_id, user_id)`** constraint, rather than a composite natural key, because the id convention is system-wide with no permanent exceptions (`backend.md`) and a surrogate id keeps the import/export codec identical in shape to every other table. The unique constraint carries the "one membership per user per book" semantics.

**The owner is not a `BookMember` row.** Ownership lives in `Book.owner_id`; membership is co-authorship. This keeps UC-024 (transfer) a single-field update and makes "exactly one owner" a structural guarantee rather than a rule some query must enforce. *Member*, across all the domain docs, means owner **or** co-author.

**Readers (ACT-006) have no row at all.** Reader access derives from `Book.visibility` — there is nothing to grant and nothing to revoke. See `authorization.md`.

Removing a co-author revokes access but leaves their content and attribution in the book (UC-027) — which is exactly what `ChapterChange.author_id` (`domain-chapter.md`) preserves, since attribution is a field on the change, not a join through membership.

## Cloning — no entity of its own

**Realizes:** FEAT-015, UC-061, UC-062, UC-063, US-067, US-094

A clone is a **new `Book` with new rows**, deep-copied from the source across chapters, changes, revisions, note changesets, codex entries, membership (per the cloner's selection, UC-063), collaboration mode and visibility. There is no clone link, no parent id, no sync — product is explicit that the two books are fully independent and drift apart permanently (US-067), so a parent pointer would model a relationship the product deliberately does not have, and would tempt later features to use it.

The cloner becomes the new book's owner regardless of which role they held on the source (UC-062, US-068).

Moderation does not reach clones (challenge C22, stated as a limitation in FEAT-011): an independent clone made before or after a book is quarantined or destroyed is unaffected, and an admin moderates each book separately. That falls out of the no-link design rather than needing to be enforced.
