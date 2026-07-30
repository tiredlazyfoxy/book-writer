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
| `system_prompt` | **superseded and read by nothing** — retained rather than dropped; the per-chapter prompt is `ChapterAuthorPrompt`, below |
| `version` | int, bumped on every applied change |
| `created_at` / `modified_at` | timestamps |

**`sketch` is one field, and it is called `sketch`.** The user's working word for it was "idea"; `docs/product/` says *sketch* throughout (FEAT-008, UC-033, US-034), so the product vocabulary wins — an architecture doc that renames a product term forces every reader to hold two names for one thing.

**One `text`, not a block table.** See `ChapterChange` below: blocks are *changes applied into* a body, not rows the body is assembled from.

### The chapter prompt moved off `Chapter.system_prompt`

**`Chapter.system_prompt` is superseded and read by nothing.** It was designed to *append to* the book-wide prompt rather than replace it — the book's voice always applies, a chapter prompt narrows it. Feature `021.per-author-system-prompt` removed that base layer by replacing `Book.system_prompt` with a per-author prompt (`domain-book.md` → `BookAuthorPrompt`). Feature `014.chapter-skeleton` then replaced the chapter field itself rather than redefining what it narrows: the per-chapter prompt is now a row of its own, **`ChapterAuthorPrompt`**.

**The column is retained rather than dropped, deliberately.** `db/engine.py` exposes only an *additive* migration seam and the project has no Alembic, so there is **no supported `DROP COLUMN` path**. It is still declared, and it still round-trips through its JSONL codec so that archives written before `014` still import — the same treatment `Book.system_prompt` received in `021` (`backend/persistence.md` → "A superseded column keeps its codec").

**The in-code docstring on the column is still stale, and three features have now left it that way.** `backend/app/models/chapter.py` still says the field appends to the book's. Feature `021` flagged it and deliberately did not edit it, because the field's replacement wording was a design decision rather than a comment fix. Feature `014` did not edit it either — `models/chapter.py` was outside every step's Source files, since the skeleton half needed no schema change and the prompt half went to a new table. Feature `015.chapter-writing-free-mode` did not edit it either; that module never entered its Source files. The flag stands open across all three, recorded here so that a fourth reader does not take the docstring for the column's meaning.

### ChapterAuthorPrompt

| Field | Type / notes |
|---|---|
| `id` | snowflake PK |
| `chapter_id` | FK → `Chapter.id` |
| `user_id` | FK → `User.id` |
| `system_prompt` | required; `""` means "no prompt" |
| `created_at` / `modified_at` | timestamps |

One row per `(chapter, author)`, holding that author's own standing instruction to the assistant for that chapter. Delivered by feature `014.chapter-skeleton`.

**A surrogate snowflake PK plus a unique `(chapter_id, user_id)`** — `BookMember`'s shape, adopted for `BookMember`'s stated reasons (`domain-book.md`): the id convention is system-wide with no permanent exceptions, and a surrogate id keeps the import/export codec identical in shape to every other table. The unique constraint carries "exactly one prompt per author per chapter". This mirrors `BookAuthorPrompt` exactly one level down. **`""` rather than a nullable column** so that "no prompt" has one representation and not two.

**There is no book-wide layer left to append to.** The prompt a chapter row holds is not a narrowing of anything — the book-wide prompt is gone, and what this value combines with, if anything, is composition's question and is not answered here.

Who may read and write a row is a **row-ownership rule, not a capability** — see `authorization.md` → "Chats and per-author prompts — three row-ownership rules".

**Composition is wired (feature `015.chapter-writing-free-mode`).** `014` shipped storing and serving the prompt and deferred reading it into a turn, because that needed an answer to "which chapter is this turn about" — which it took to be undesigned FEAT-013 context assembly. **`015` dissolved the blocker without designing context assembly**: it registers the open chapter as the content-pane subject, so the turn request itself names the chapter, and the row is passed as **layer 4** of the system-prompt composition, read for the chat's own author. See `assistant-runtime.md` → "System-prompt composition". Context assembly remains undesigned.

**No product id is cited for this entity, deliberately.** UC-094 and every criterion of US-109 describe a chapter prompt that narrows a book-wide prompt which no longer exists, so citing them would claim satisfaction of criteria this design contradicts — the same convention feature `021` used for `BookAuthorPrompt`. Recorded as part of the open fifth divergence in `domain-model.md` → "Product divergences", which also annotates item 3 as partly reversed.

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

### The close seam, as built (feature `015.chapter-writing-free-mode`)

The seam is now concrete rather than a roadmap note. As shipped, `POST …/close` requires `state == open` and writes **`closed` directly**: nothing reads or writes `closing`, no continuity is drafted, and no approval is required.

**`016.chapter-close-continuity` changes exactly two things** — the destination becomes `closing`, and a second endpoint moves `closing → closed` after the owner approves. Everything else `016` might expect to build **already exists**, and `015` built it that way deliberately so `016` does not retrofit it:

- every **one-open-chapter guard already tests `state in {open, closing}`**, on **both** the open and the reopen path;
- the **body-write refusal already refuses a `closing` chapter**;
- **`determine_mode` already maps a `closing` chapter to the seeded `close-chapter` mode** (`assistant-runtime.md`).

**US-038.AC-3 is cited by nothing in `015`.** Its steps belong to the gated close, which is `016`'s. This is staging, not divergence.

### CF1 — reopen is refused while another chapter is open

**A reopen (UC-037) is refused if any chapter in the book is `open` or `closing`.** The owner must close the currently-open chapter properly, through the continuity gate, first.

Product's UC-037 says reopening *auto-closes* whichever chapter is open. Taken together with FEAT-012's gate that is incoherent: an auto-close either skips the approval the gate exists to require, or silently strands a chapter mid-`closing`. Product round 5 recorded this as coherence finding **CF1** and left it unresolved. Refusing is the resolution that keeps both invariants — the one-open-chapter singleton **and** the approval gate — with no silent data loss, and it turns an invisible side effect into an explainable error the owner can act on. Recorded as a divergence from product's current wording in `domain-model.md` → "Product divergences", item 4.

### Landing the continuity columns early

`state = closing`, `Chapter.summary_status`, and `ChapterNoteChangeset.status` (`domain-continuity.md`) are **created at Stage 2, nullable and unused**, even though nothing reads them before Stage 4.

This is the same reasoning that justifies drawing the entity map whole (`domain-model.md`): additive nullable columns are the cheap migration case, and adding them now costs a wider `CREATE TABLE` that nothing queries. Doing it now buys something specific — **Stage 4 becomes pure behaviour with no DDL at all**. That matters more here than elsewhere because `backend/features.md` records the constraint: SQLite cannot `ADD COLUMN … NOT NULL` to a populated table without a default, so a column added later against live book data arrives nullable regardless of what the model declares. Landing it early keeps the schema honest instead of accumulating retroactively-nullable columns.

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

### What a Stage-2 row actually contains — placement is computed, not chosen

**Realizes:** feature `015.chapter-writing-free-mode`. `018` reads these rows back and FEAT-010 writes `pending` ones, so what a free-mode row holds — and which fields are never populated yet — is the first thing either will need.

A free-mode save is **one `PUT` carrying the whole body plus `expected_version`**, producing **one `ChapterChange` row per save whose placement is computed server-side**:

- **`append`** when the new body **starts with** the loaded body — the appended remainder is the change's text, and the line bounds are null;
- **`range`** otherwise — `line_from = 1`, `line_to = len(loaded_text.splitlines())`, and the **whole new body** as the change's text.

Three degenerate cases have fixed answers, so nobody has to re-derive them:

- an **empty prior body** is always an `append` carrying the whole body — the first write into a chapter;
- **clearing a body to `""`** is a `range` carrying `""`;
- an **unchanged re-save** is an `append` carrying `""`, and it **still snapshots and still bumps the version**. No "unchanged" short-circuit was added: one rule beats a special case, and the client already gates the save on dirtiness.

**Why the placement is computed rather than transmitted — the two layers.** Versioning is **whole-body and happens on save**; append-vs-replace is an **editing operation on the draft**, before any save, performed by the author typing or by the assistant's tools (`assistant-runtime.md`). That is what reconciles UC-038's "append a block" with UC-039 / US-041's "edit a body", and it is why **no partial or line-addressed write reaches HTTP at all**.

Consequently `ChapterChange.status = pending` and `rejected` are **still unreached** — they are FEAT-010's and `018`'s.

The remaining fields, as written in free mode: **`base_version` is the client's `expected_version`**, **`status` is `applied` immediately**, and **`author_id` is the caller — this is where US-040.AC-2's attribution lives.**

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

**Free mode reaches step 1 immediately; proposal mode reaches it when the owner applies.** There is no second merge implementation for proposals, and no third for the assistant.

#### As built there is no transaction — the real ordering, and what it accepts

This section used to assert that all three steps are one transaction. **They are not, and the architecture cannot currently make them so.** `db/` is session-free with one module per entity, and **no multi-table transaction primitive exists anywhere in the codebase**. Correcting the claim matters: a reader relying on it would design revert, variants (`018`) or proposal application (FEAT-010) on a promise that is not kept, and would go looking for a bug class the schema makes unrepresentable.

As shipped by feature `015.chapter-writing-free-mode`, the save issues **three ordered `db/` calls from `services/chapters.py`**, exactly as `services/codex.py::update_entry` orders its version snapshot before its entry mutation. **No cross-entity `db/` module was created** — "one module per entity" was kept.

**The order is `ChapterChange` → `ChapterTextRevision` → `Chapter`**, and it is the safest one available:

- the **change must precede the revision**, because `ChapterTextRevision.applied_change_id` is a **non-null FK**;
- the **chapter update must come last**, because a body that has moved with no history behind it is the one failure that breaks revert irrecoverably.

**History before mutation.**

The accepted failure modes, stated precisely — the sentence this replaces named one that cannot happen:

- a crash **after step 1** leaves an `applied` change with no revision and an **unmoved** body;
- a crash **after step 2** leaves a change plus a **no-op revision** whose `text_before` equals the current body;
- **no ordering can leave a moved body with no history**, and **a snapshot with no applied change is impossible** under the FK direction.

**A second limitation of the same class:** the **version check and the write are not one transaction either**, so two saves racing on the same `expected_version` can both pass the check. The window is milliseconds and the exposure is identical to `services/codex.py`'s.

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

**How US-040.AC-4 is actually satisfied — read it as a flow, not as a merge.** It is satisfied automatically by the three rules above: the system **refuses the later save**, **shows the author the server's body against their draft**, and lets a save **re-issued against the current version** land. **The merging is the author's** — reconciliation takes one side whole and there is **no automatic merge at MVP**. "Both members' blocks end up in the chapter" is therefore true of the *flow*, not of a merge algorithm, and the criterion should be read that way. The wording invites the other reading, which is why it is pinned here; whether product re-words it is `/product-spec`'s.

**Accepted limitation:** two authors appending to the same chapter simultaneously will make one of them re-issue their save even though appends do not actually conflict. Refusing uniformly was chosen over a placement-dependent rule because "sometimes your save is refused and sometimes it isn't, depending on where you put it" is harder to reason about than "your save is refused when the chapter moved", and an append re-issue is a one-click retry with no content loss.
