# Domain — Codex

**Realizes:** FEAT-017 (UC-069..075), FEAT-018 (UC-076, UC-077 — the save path only); US-078..085

Part of the book-domain model. **Index and cross-cutting conventions: `domain-model.md`.** Related: `retrieval.md` (`CodexEntry` is the first vector-backed model), `domain-continuity.md` (a state note names an entry), `authorization.md` (the codex is members-only), `frontend-workspace.md` (the navigator's Characters / Locations / Facts entries), `frontend-work-drafts.md` (the restore buffer that holds an unsaved entry), `assistant-runtime.md` (the assistant's mode-gated codex tools and the canvas write).

The codex is the book's reference volume — the things the book is *about*, as opposed to its prose. **One codex per book**, shared by all of a chapter's revisions; divergent worlds are what cloning is for (`domain-book.md`).

## CodexEntry

`CodexEntry` is the **first vector-backed model** in the system — see `retrieval.md`.

| Field | Type / notes |
|---|---|
| `id` | snowflake PK |
| `book_id` | FK → `Book.id`. One codex per book; a chapter's revisions share it |
| `kind` | `character` \| `location` \| `fact` |
| `name` | set for `character` / `location`; **null for `fact`** (US-078.AC-2) |
| `body` | the entry's content |
| `archived` | archived, never deleted (UC-072) |
| `author_id` | FK → `users.id`, **required** — the entry's original creator |
| `modified_by` | FK → `users.id`, **nullable** — author of the last version / most recent editor, maintained by the feature-013 codex service |
| `created_at` / `modified_at` | timestamps. `modified_at` doubles as the entry's **version token** — see "Concurrency" below |

**Three kinds, one table.** Characters / Locations / Facts are a fixed taxonomy, not three entities — the working page's navigator splits them by filtering `kind` (UC-090 note: "the round-4 fixed taxonomy, not a new entity"). Three tables would triplicate the history, archive, copy and indexing paths for rows that differ in one enum value.

**`name` is nullable because a fact does not have one.** Product is precise about what a name buys: a named entry carries state-note reference (`domain-continuity.md`, UC-079) and is name-addressable; a fact has neither. Modelling that as a nullable column rather than a separate table keeps the distinction where product put it — on the entry — instead of turning it into a structural split.

**Archived, never deleted** (UC-072), consistent with books (UC-023) and users (FEAT-003). Archiving is a semantic event, not a data one: because notes reference entries **by name**, archiving cannot break a note at the database level, and the resulting semantic gap is what FEAT-016's check warns about (UC-080, US-092). Whether archiving can be undone is an open `_TBD:` in product and is not answered here.

**Archived entries leave the vector index**, rather than being filtered out at query time — see `retrieval.md` for that reasoning.

**Archiving itself is not built.** Feature `013.codex` shipped create / read / list / search / edit and **no archive operation** — there is no `DELETE`, and no archive or restore endpoint; that is `017.codex-archive-restore`'s. What `013.codex` did ship for it is the *consequence*: the `archived` column exists and is honoured everywhere (an archived entry is excluded from the vector source selector, refused by the edit path with a `400`, and dropped by the assistant's search and read tools), and the index **drop operation** an archive will need is already exposed by `services/codex_index.py` (`retrieval.md`). Nothing in this document should be read as archiving having shipped.

**Collaboration mode applies** (US-079): in free mode a member's create or edit lands immediately; in proposal mode a co-author's is held for the owner. This is the same rule as state notes, and the same mechanism — see `authorization.md` for how it is enforced. Note that FEAT-010's own `_TBD:` records that only *block* proposals have a use case today; the review surface for codex proposals is undesigned.

### As built, only free mode exists — and why

**Feature `013.codex` implements free mode only.** An **owner's** write always applies, in either mode. A **co-author's** create or edit in a **`proposal`-mode book is refused with `403`**, carrying a typed reason that **names FEAT-010 as unbuilt**.

The reasoning is the same gap the paragraph above sees from the other side. **FEAT-010 has no proposal entity and no review surface** — there is nowhere to *hold* a codex proposal and nobody has a screen on which to approve one. Applying the write anyway would have been the worse option: it would **silently violate US-079.AC-2** (a co-author's change in proposal mode is held, not applied) while looking correct, and it would leave the book's owner with content they never reviewed and no record that review was skipped. A refusal is loud, reversible by the owner switching the book to free mode, and disappears the day FEAT-010 ships.

**US-079.AC-2 is knowingly unmet.** Architecture records this as a decision with an owner — a refusal that looks like a bug from the outside must be traceable to a choice. Recording the *product* status of that criterion is `/product-spec`'s job, not this document's; nothing in `docs/product/` may be edited from here to close it.

### Concurrency — `modified_at` is the version token

Mirroring `domain-chapter.md` → "Concurrency", with one field instead of a dedicated counter:

1. **A codex edit carries the entry's expected `modified_at`.** A mismatch means the row moved under the editor and the edit is **refused with `409`** — not merged, not last-write-wins.
2. **`modified_at` is therefore the entry's version token**, not merely an audit timestamp. Nothing may write it opportunistically or backdate it.
3. **A `409` becomes the reconciliation view, never an auto-merge.** The author is shown the server's entry against their own draft and reconciles it themselves, the same client contract chapters have.

It is the **same value the frontend restore buffer stores as its `baseVersion`** (`frontend-work-drafts.md`), which is what lets the buffer detect a divergence at load time — before any save is attempted — as well as on a refused save. A field that is a version token for one layer and a timestamp for another is exactly the kind of shared assumption that has to be written down once; the buffer design depends on it.

`Chapter.version` exists as a separate integer because a chapter body is written through `ChapterChange` rows that each name the version they were composed against, so "has this body moved" has to be answerable as an ordinal independently of any timestamp. A codex entry is saved whole, through one `PUT`, so the entry's own `modified_at` already distinguishes the row the editor loaded from the row on disk, and a second column would be a value to keep in step for no additional answer.

## CodexEntryVersion

| Field | Type / notes |
|---|---|
| `id` | snowflake PK |
| `entry_id` | FK → `CodexEntry.id` |
| `generation` | non-null `int` — 1-based sequence number of the version within its entry, maintained by the codex service |
| `name` / `body` / `kind` | the entry's content **as it stood** at that version |
| `author_id` | who produced that version |
| `created_at` | timestamp |

Version rows carry the **full prior content**, for the same reason `ChapterTextRevision` does (`domain-chapter.md`): restore (UC-074) must be exact and self-contained, and a chain of deltas fails silently when one link is wrong. Entries are small, so the storage argument that might favour deltas does not apply at all here.

A restore **writes a new version row** rather than rewinding the history, because UC-074 states the restore itself becomes a new point in the edit history. History is therefore append-only, which also makes UC-073's "view past versions" a plain ordered read.

### The rows are written by feature `013.codex`, not by the history feature

**Version rows are written from the day codex editing shipped.** Feature `013.codex`'s codex service writes one on **every edit**, carrying the **prior** `name` / `body` / `kind`, with a **1-based `generation`** and `author_id` set to the **editing** user, and it sets `CodexEntry.modified_by` alongside in the same operation.

**No version row is written on create**, so an entry that has never been edited has **no history at all** — an empty history is the normal state, not a fault, and a history view must render it as such.

`019.codex-history` therefore builds the **view and restore endpoints** (UC-073, UC-074) **on top of data that already exists**, rather than introducing the table's first writer.

This corrects an earlier statement in this document that the table was "drawn now but first built at Stage 5". The model docstrings already assigned the write to "the feature-013 service" while this design doc said Stage 5; the two disagreed, and the disagreement is resolved **in the direction the code already assumes**. (The Stage-5 plan folder named in the old wording, `018.codex-history-copy`, no longer exists either — the roadmap now carries `017.codex-archive-restore` and `019.codex-history`.)

## Copying between books (UC-075)

Copying selected entries from a source book the member also belongs to produces **new `CodexEntry` rows in the target**, independent of the source afterwards — the same no-link stance as cloning. Membership of *both* books is the precondition, which is an authorization rule (`authorization.md`), not a schema one.

Whether a copy carries the source entry's edit history is an open `_TBD:` in product. The schema permits either answer — copying version rows or not — and this pass does not choose one.

## Codex authoring from the chat (FEAT-018)

UC-076 and UC-077 add no entity and no field. The assistant writes a draft into the open entry on the shared canvas, and **the save path is exactly UC-069/UC-070's** — collaboration mode applies at save, nothing persists before it (US-088, US-103.AC-3).

**How the assistant produces that draft is now partly built** — the part that reaches a codex entry is designed and shipped, and lives in **`assistant-runtime.md`**, not here. As built: a **mode-gated `write_codex_draft` tool** validates editability **server-side**, emits **one `canvas` SSE frame**, and **persists nothing**. The frontend applies the frame to the open entry; the author saves it or does not.

The save-path statement above is unchanged by that: the draft becomes an entry only through **UC-069 / UC-070**, the same route an author's own edit takes, with collaboration mode applying at save (US-088, US-103.AC-3). Because there is no code path from a chat turn into `codex_entries`, "nothing persists before the save" is a **structural property, not a check that could be forgotten**.

What remains undesigned about the assistant is stated in `domain-chat.md` — context/content assembly, the same protocol for chapters (UC-055), token-level canvas streaming and token budgeting.
