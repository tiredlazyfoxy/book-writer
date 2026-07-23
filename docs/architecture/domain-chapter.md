# Domain — Chapter, the write path, and concurrency

**Realizes:** FEAT-008 (UC-031..034), FEAT-009 (UC-035..039), FEAT-010 (UC-040, UC-041), FEAT-012 (UC-047, UC-048, UC-052 — the close gate's states), FEAT-013 (UC-055 — the save path only), FEAT-014 (UC-058..060); US-037, US-040, US-041, US-049..051, US-055, US-059, US-062..065, US-103

Part of the book-domain model. **Index and cross-cutting conventions: `domain-model.md`.** Related: `domain-book.md` (the book a chapter belongs to), `domain-continuity.md` (a chapter's note changeset and its flags), `domain-codex.md`, `frontend-workspace.md` (the editor these writes come from).

## Chapter

| Field | Type / notes |
|---|---|
| `id` | snowflake PK |
| `book_id` | FK → `Book.id` |
| `ordinal` | position in the skeleton; the owner sets it (UC-032) |
| `title` | chapter title |
| `state` | `planned` \| `open` \| `closing` \| `closed` (UC-035/036/037, UC-047/048) |
| `sketch` | the forward-looking outline (FEAT-008) |
| `text` | **the single main body** |
| `summary` | the backward-looking summary (FEAT-012, drafted on close request, owner-approved) |
| `summary_status` | `draft` \| `approved` \| `stale` — the summary's own continuity status |
| `system_prompt` | optional; **appends to** the book's, narrowing it |
| `version` | int, bumped on every applied change |
| `created_at` / `modified_at` | timestamps |

**`sketch` is one field, and it is called `sketch`.** The user's working word for it was "idea"; `docs/product/` says *sketch* throughout (FEAT-008, UC-033, US-034), so the product vocabulary wins — an architecture doc that renames a product term forces every reader to hold two names for one thing.

**One `text`, not a block table.** See `ChapterChange` below: blocks are *changes applied into* a body, not rows the body is assembled from.

**The chapter system prompt appends to the book's, it does not replace it.** The book-wide voice always applies; a chapter prompt narrows it. Replacing would let one chapter silently escape the book's voice, which is the opposite of what a book-level prompt is for. Neither prompt field has a product requirement behind it — see `domain-model.md` → "Product divergences", item 3.

`summary` lives on the chapter but belongs to the continuity story; how it is drafted, approved and viewed is `domain-continuity.md`.

## State machine

```
                                       close requested (owner, UC-036)
planned ──open (owner)──► open ──────────────────────────────► closing
   │                        ▲                                     │
   └── removed (UC-034)     │                    owner approves   │
                            │                    continuity       │
                            │                    (UC-048)         ▼
                            └────── reopen (owner, UC-037) ───► closed
                                    marks continuity stale
```

- At most **one** `open` chapter per book (US-037). **`closing` still holds that slot** — the chapter has not been released, it is waiting on the owner.
- Only `planned` chapters may have their sketch edited (UC-033) or be removed (UC-034).
- **`closing` and `closed` both refuse all writes to `text`** — from a member and from the assistant alike (US-097.AC-2, US-059.AC-3).
- Editing after a **reopen** is a *fix*, and produces variant history — see `ChapterTextRevision` below.

### Why `closing` is a named state

`closing` means *close requested, continuity awaiting owner approval* (UC-047 drafts it, UC-048 approves it, US-051 refuses the close until then). The window has its own rules — it holds the open slot, and it refuses writes — and a window with distinct rules is better named than inferred. The alternative was to leave the chapter `open` and derive "we are mid-close" from the existence of a draft summary; that makes the rule "an open chapter is writable **unless** a draft summary exists", which every write path would have to remember, and which breaks the moment a summary exists for any other reason.

**Writes are refused in `closing` for a specific reason:** the owner is approving continuity data that describes a particular body. Letting anyone edit that body while it is being approved would produce an approved summary of text that no longer exists — exactly the failure FEAT-016's check is meant to catch, manufactured by the workflow itself.

The close gate is a **Stage-4 behaviour** (Stage 2 ships an ungated close, per the roadmap's explicit close-gate seam), but the `closing` value and the status columns below **land at Stage 2**. See "Landing the continuity columns early".

### CF1 — reopen is refused while another chapter is open

**A reopen (UC-037) is refused if any chapter in the book is `open` or `closing`.** The owner must close the currently-open chapter properly, through the continuity gate, first.

Product's UC-037 says reopening *auto-closes* whichever chapter is open. Taken together with FEAT-012's gate that is incoherent: an auto-close either skips the approval the gate exists to require, or silently strands a chapter mid-`closing`. Product round 5 recorded this as coherence finding **CF1** and left it unresolved. Refusing is the resolution that keeps both invariants — the one-open-chapter singleton **and** the approval gate — with no silent data loss, and it turns an invisible side effect into an explainable error the owner can act on. Recorded as a divergence from product's current wording in `domain-model.md` → "Product divergences", item 4.

### Landing the continuity columns early

`state = closing`, `Chapter.summary_status`, and `ChapterNoteChangeset.status` (`domain-continuity.md`) are **created at Stage 2, nullable and unused**, even though nothing reads them before Stage 4.

This is the same reasoning that justifies drawing the entity map whole (`domain-model.md`): additive nullable columns are the cheap migration case, and adding them now costs a wider `CREATE TABLE` that nothing queries. Doing it now buys something specific — **Stage 4 becomes pure behaviour with no DDL at all**. That matters more here than elsewhere because `backend.md` records the constraint: SQLite cannot `ADD COLUMN … NOT NULL` to a populated table without a default, so a column added later against live book data arrives nullable regardless of what the model declares. Landing it early keeps the schema honest instead of accumulating retroactively-nullable columns.

## ChapterChange — the unified write record

**Every write into a chapter body is one row of one table.** A block, a proposal, a variant-producing fix, an assistant's saved draft and a post-close correction are the same record with different field values.

| Field | Type / notes |
|---|---|
| `id` | snowflake PK |
| `chapter_id` | FK → `Chapter.id` |
| `author_id` | FK → `User.id` — who wrote it (US-040.AC-2 attribution) |
| `placement_kind` | `append` \| `range` |
| `line_from` / `line_to` | nullable ints; set only when `placement_kind = range` |
| `base_version` | the `Chapter.version` this change was composed against |
| `text` | the change's text |
| `status` | `pending` \| `applied` \| `rejected` |
| `applied_at` / `applied_by` | null until applied |
| `created_at` | timestamp |

`placement` is stored as a discriminator plus two nullable ints rather than a union column, because SQLite has no union type and a discriminator keeps the "which columns are meaningful" question answerable without parsing.

### Why one record and not four

Each alternative was worse in a specific way:

- **A `Block` table plus a `Proposal` table** duplicates the merge logic and guarantees the two drift; proposal mode becomes a second code path rather than a status value.
- **A separate variant/fix record** means FEAT-014 has to re-derive authorship and placement that a block already carries.
- **A separate assistant-output record** would make "who wrote this" depend on provenance, when product is explicit that a saved assistant draft enters the chapter *exactly as a manual block does* (US-059, US-103.AC-2).

Unified, every change carries **author, date and placement for free**, proposal mode is a status flag, and the Variants view (FEAT-014) has real content from the first chapter written rather than only from the first reopen.

**This answers FEAT-009's open `_TBD:` "what a block contains (format, length, structure)."** A block is a `ChapterChange` with `placement_kind = append`: free text, no length rule, no internal structure, placed at the end of the body. The `_TBD:` lives in `docs/product/` and is not this document's to close there — but the architecture no longer has a hole where it was.

### The one write path

Both collaboration modes converge on a single merge:

```
compose change (base_version = chapter.version)
        │
   free mode ──────────────► status = applied ──┐
        │                                       │
 proposal mode ─► status = pending              │
        │                                       │
   owner applies (UC-041) ──► status = applied ─┤
                                                ▼
                                    ┌────── merge ──────┐
                                    │ 1. snapshot text  │ → ChapterTextRevision
                                    │ 2. apply placement│
                                    │ 3. version += 1   │
                                    └───────────────────┘
```

1. **Snapshot** the chapter's current `text` into a `ChapterTextRevision` row.
2. **Apply the placement** — `append` concatenates onto the end of the body; `range` replaces lines `line_from..line_to` with the change's text.
3. **Bump `Chapter.version`** and stamp `applied_at` / `applied_by`.

All three steps are one transaction: a snapshot without an applied change, or an applied change without a snapshot, would break revert.

**Free mode reaches step 1 immediately; proposal mode reaches it when the owner applies.** There is no second merge implementation for proposals, and no third for the assistant.

### Stale pending changes are refused, not rebased

A `pending` change's `base_version` goes stale as other changes apply to the chapter. **Applying a stale change is refused**, the same rule and the same reasoning as the 409 below: a `range` placement is expressed in line numbers that no longer address the text they were written against. The author redoes the change by hand against the current body.

**There is no automatic merge at MVP** — no rebase, no three-way reconcile, no heuristic re-anchoring. Merge mechanics are explicitly post-MVP. Guessing where a stale change now belongs would write text into a location nobody chose, and the failure would be silent; a refusal is loud, and redoing a change by hand is work the author can actually verify.

An `append` change is placement-independent, so in principle it could still apply cleanly. It is refused anyway, uniformly — see the accepted limitation under "Concurrency" for why one rule beats a placement-dependent one.

## ChapterTextRevision

**Realizes:** FEAT-014 (UC-058, UC-059, UC-060), challenge C20

| Field | Type / notes |
|---|---|
| `id` | snowflake PK |
| `chapter_id` | FK → `Chapter.id` |
| `applied_change_id` | FK → `ChapterChange.id` — the change this snapshot precedes |
| `text_before` | the **full** chapter body as it stood before that change |
| `applied_by` / `applied_at` | who applied it, when |

**Full snapshots, not reverse patches.** Reverse patches store less, but reverting to revision *N* means replaying *N* patches in order, every one of which must be correct; a single missing or malformed patch breaks the whole chain irrecoverably, and the failure is silent until someone tries to revert. A full snapshot makes revert exact, self-contained, and verifiable on its own. Storage is trivial at book scale — a chapter body is kilobytes, and the number of applied changes per chapter is bounded by how much a human writes.

This is what satisfies FEAT-014's "previous text stays recoverable" (challenge C20), and it is what the Variants view reads alongside the chapter's un-applied changes.

### Variants and UC-060 — apply, not select

**A variant is an un-applied `ChapterChange`.** There is no active-variant pointer, and there is no "switch".

An un-applied variant is **not selectable as the chapter's text** — it is a proposed alternative sitting beside the body, not a parallel body competing to be live. Making it the chapter's text *is* **applying** it, through the one write path above: snapshot → apply placement → bump version. Nothing else happens, and nothing new is needed: apply is the operation the model already has.

Three things fall out of this and are worth stating:

- **US-065 survives unchanged.** Product requires that making a variant the chapter's text runs the same consistency-check path a fix does. It does, necessarily — an apply *is* a change, so it takes the change path.
- **UC-059's "view and compare" is served.** The Variants view lists a chapter's un-applied changes and its prior revisions; revisions are full bodies, so any two diff cleanly without reconstruction.
- **A stale variant is refused, not merged** — the rule above. **Merge mechanics are explicitly post-MVP.**

Product's FEAT-014 wording — "select the active variant", "which variant *is* the chapter" — describes a pointer among parallel texts. That is what this design diverges from: not the *notion* of variants, but the selection mechanism. Recorded in `domain-model.md` → "Product divergences", item 1.

## Concurrency — the chapter version contract

**Realizes:** FEAT-009 (UC-039), US-041; closes the parked `/architect` item **CF-r6** (UC-092 exception flow)

Three rules, and they work as a set:

1. **`Chapter.version` is bumped on every applied change.** It is the single authority on "has this body moved".
2. **A save carrying a stale `base_version` is refused with `409`.** Not merged, not last-write-wins at the server. A `range` placement is expressed in line numbers, and line numbers cannot resolve against text that has moved — silently applying them would corrupt the body at a location nobody chose.
3. **A version mismatch on returning to a buffered draft is a visible merge problem — never an auto-merge.** The author is shown the server's version against their buffered draft and reconciles it themselves. An LLM-assisted merge is available as a Stage-5 capability (it needs the assistant subsystem); the **manual path ships with the buffer** and is not optional.

The restore buffer (UC-092) records the `Chapter.version` it forked from, so the mismatch is detectable on return without a server round-trip beyond the normal load. Buffer mechanics — storage, scoping, lifetime — are `frontend-workspace.md`'s.

**This is the same mechanism US-041 needs.** The product's "warn the second author, then later-write-wins" is exactly rules 2 + 3 seen from the author's side: the second save is refused, the author is shown the divergence, and if they choose to overwrite, their reconciled text becomes the next applied change against the current version. The system never silently discards either side.

**Accepted limitation:** two authors appending to the same chapter simultaneously will make one of them re-issue their save even though appends do not actually conflict. Refusing uniformly was chosen over a placement-dependent rule because "sometimes your save is refused and sometimes it isn't, depending on where you put it" is harder to reason about than "your save is refused when the chapter moved", and an append re-issue is a one-click retry with no content loss.
