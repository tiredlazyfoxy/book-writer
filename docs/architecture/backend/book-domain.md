# Backend — Book-Domain Impact

**Realizes:** FEAT-006..018 (backend-side consequences only)

Part of the backend architecture — see `../backend.md` for the index.

The entity definitions, their reasoning and their lifecycles live in `domain-model.md` (the index) and its area files — `domain-book.md`, `domain-chapter.md`, `domain-continuity.md`, `domain-codex.md`, `domain-chat.md`. This section records what the design costs *this* document's structures.

## Module map

The existing four-layer split absorbs the domain without change — one `db/` module per entity, one service per aggregate, routes under `/api`:

| Layer | Modules |
|---|---|
| `models/` | `book.py`, `book_member.py`, `chapter.py`, `chapter_change.py`, `chapter_text_revision.py`, `chapter_notes.py`, `codex_entry.py`, `codex_entry_version.py`, `flag.py`, `chat.py` (+ `models/schemas/` DTOs per resource) |
| `db/` | one module per table, session-free, same shape as `db/users.py` / `db/llm_servers.py` |
| `services/` | per aggregate — books (lifecycle, membership, visibility, mode), chapters (skeleton, state machine, the merge path), codex, continuity, flags — plus **`services/authz.py`** (the capability table) and **`services/embedding.py`** (text → vectors) |
| `routes/` | HTTP only, under `/api`; the book-access dependency resolves a typed `BookAccess`, the service decides the capability |

Two cross-cutting additions worth naming because they are shared rather than per-entity:

- **`services/authz.py`** — one `require(access, capability)` entry point so the capability × role matrix has a single implementation. See `authorization.md` → "Enforcement".
- **`services/embedding.py`** — the single point where text becomes vectors. See `retrieval.md`.

## The book-domain table registry

`TABLE_REGISTRY` (`services/db_import_export.py`) gains a codec pair per new table, appended **in FK dependency (import) order** after the two existing entries:

```
users, llm_servers,                       # existing
books, book_members,
chapters, chapter_changes, chapter_text_revisions, chapter_note_changesets,
codex_entries, codex_entry_versions,
flags,
chats, chat_messages
```

**Flag this plainly: that is roughly a dozen new codec pairs.** The rule in the root `CLAUDE.md` is not optional and not deferrable — "update the import/export logic in the **same change** whenever a model is added or altered". Every one of these tables owes its `to_dict` / `from_dict` pair (ids emitted as **strings**, accepted as string-or-legacy-number) and its ordered registry tuple in the change that introduces the model. Batching them up "for later" would leave an instance whose export silently loses a book.

Order matters because import is a streaming UPSERT with no transactional rollback: a child row arriving before its parent has nothing to attach to.

## Vector registry

`VECTOR_SOURCE_REGISTRY` is **no longer empty** — `CodexEntry` registers at Stage 2, with chapter text, summaries and notes following for UC-086. See "Vector storage" in `persistence.md` and `retrieval.md`.

## Stage-4 columns land at Stage 2

The book domain's later-stage **columns are created with their tables**, nullable and unused, rather than added when the behaviour ships: `Chapter.state = closing`, `Chapter.summary_status`, `Book.moderation_reason` / `moderated_by` / `moderated_at`, and the `ChapterNoteChangeset` table with its `status`.

The reason is the backend's own SQLite constraint, recorded in `features.md` → "Remediation": **`ADD COLUMN` cannot be `NOT NULL` without a default on a populated table**, so a column added later against live book data arrives nullable regardless of what the model declares, and reconciling nullability would need a table rebuild. Landing them now costs a wider `CREATE TABLE` that nothing queries and makes Stage 4 pure behaviour with **no DDL at all**. See `domain-chapter.md` → "Landing the continuity columns early".

## Chapter concurrency — the 409 rule

`Chapter.version` is bumped on every applied change, and a write carrying a stale `base_version` is **refused with 409**, never merged server-side. This is a service-layer rule (the merge is a single transaction: snapshot → apply placement → bump version), and it is what US-041's concurrent-edit warning is built from. Full reasoning, including why a uniform refusal was chosen over a placement-dependent one, is in `domain-chapter.md` → "Concurrency".

## Schema drift — no new code

FEAT-005's consistency report (`db/schema.py` + `services/db_admin.py`) compares the live database against `SQLModel.metadata`. Every table above lands in that metadata by being declared, so **the drift report covers the new tables with no change to the FEAT-005 code at all** — the ok / drift / missing report and the per-table create/sync remediation extend to the book domain for free. This is the payoff of having built drift detection against metadata rather than against a hand-maintained table list.
