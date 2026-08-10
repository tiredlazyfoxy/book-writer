# Domain — Continuity: notes, summaries and flags

**Realizes:** FEAT-012 — UC-047, UC-049, UC-050, UC-051, UC-052, UC-079, UC-089, UC-091; US-049, US-052, US-053, US-054, US-055, US-090, US-104, US-106. FEAT-016 — UC-067, UC-068, UC-080; US-076

**Four ids left this header at feature `016.chapter-close-continuity`'s finalization (2026-07-31): UC-048, US-050, US-051 and UC-066.** All four describe the owner-approval gate this design does not build — a review surface between drafting and closing, plus the separate "apply flags" act that belonged to it. Citing them would claim satisfaction of criteria the design contradicts, which is the convention `domain-model.md` already uses for FEAT-019. **Product deferred them rather than withdrawing them**, so the ids still exist and are future work; the divergence is recorded in `domain-model.md` → "Product divergences", item 6.

**UC-047, US-049 and UC-080 are cited although `docs/product/` records them `deferred`.** The design realizes them and the code shipped; what has not happened is a *run*. **Since feature `024.chat-agent-loop` the five close-chapter tools are seeded and reachable on a fresh install** (`assistant-runtime.md`) — they were previously registered but unreachable until an administrator assigned them — so "deferred" here now means **built and reachable, not yet exercised**: the missing thing is a *run*, not a configuration act. `/product-spec` reworded the product-side reason to match on 2026-08-10.

Part of the book-domain model. **Index and cross-cutting conventions: `domain-model.md`.** Related: `domain-chapter.md` (`Chapter.summary`, `summary_status` and the `closing` state live there), `domain-book.md` (`Book.active_notes`), `domain-codex.md` (what a note references by name).

The two artifacts FEAT-012 produces are deliberately different, and product says so directly: a **summary** is the condensed narrative of what a chapter contained (backward-looking, per chapter), while **state notes** are free-text facts that must stay true going forward. Neither replaces the other. **Flags** (FEAT-016) are the third continuity artifact — annotations raised against a chapter, by a check or by a person.

## Notes — `ChapterNoteChangeset`

A chapter's notes are the **invisible-to-the-reader outcomes of that chapter** — what is true afterwards that was not true before. Product is explicit that they are **free text with no entity model** behind them, and this design does not add one.

| Field | Type / notes |
|---|---|
| `id` | snowflake PK |
| `chapter_id` | FK → `Chapter.id`, unique — one changeset row per chapter |
| `added` / `modified` / `deleted` | free text, one field per operation |
| `status` | `draft` \| `approved` \| `stale` — see "Continuity status" below |
| `created_at` / `modified_at` | timestamps |

A **separate 1:1 table rather than three more columns on `Chapter`**, because chapter-body reads are the hot path (every content-pane load, every context push) and continuity reads are not; keeping the changeset out of `Chapter` keeps the hot row narrow.

### The active note set

The **accumulation** across all chapters is the live set, materialised as **`Book.active_notes`** (`domain-book.md`) rather than recomputed by replaying every changeset. The reasoning — the live set is pushed into every chat's context baseline (US-057.AC-3), so it is read constantly for a value that changes rarely — is recorded with the field.

The denormalisation has exactly two writers, and they must stay in step:

- the **close procedure's clean-run branch** — `services/chapters.py::finalize_close_turn` — writes `Book.active_notes` from the run's in-memory proposal, in the same deterministic step that marks the chapter's changeset `approved` (the changeset *row* is written earlier in the run, by `draft_chapter_notes`; see "The close procedure, as built" below);
- the **direct note edit** (UC-050) — `services/continuity.py::update_state_notes` — writes `active_notes` alone.

Both writers landed with feature `016.chapter-close-continuity`; before it, `Book.active_notes` had none. The invariant is unchanged — **exactly two writers** — and naming the two functions rather than two use cases is what makes it checkable.

Members see current truth (UC-049), not a historical accumulation; a chapter's own delta is read from its changeset row (UC-051).

### UC-079 — a note references a codex entry by name, not by foreign key

Named entries (character, location) are *name-addressable* by product's own account of what a name buys (US-078); a note naming "Marek" is resolved against `CodexEntry.name` (`domain-codex.md`) at the point of use. This keeps notes genuinely free text — a link table would be the entity model product declined to build — and it is what makes FEAT-016's UC-080 check possible: an unresolvable or archived name is exactly the warning the check is asked to raise.

Because the reference is by name and not by key, **archiving an entry cannot break a note** at the database level. The breakage is semantic, and semantic breakage is precisely what the check is for (UC-072 postcondition, US-092).

## Summaries

`Chapter.summary` is a field on the chapter (`domain-chapter.md`), not a table of its own — one chapter has exactly one summary, and it is read on the same paths the chapter is.

Once approved it is viewable read-only (UC-089, US-104) on Book state (UC-091), on the chapter's own page, and on the settings-side continuity view (`frontend-workspace.md` — designed, and deliberately not built by feature `016`).

**There is no summary editor and no approval gate.** The summary is written by the close run and read afterwards; its only writer is `services/close_tools.py::draft_chapter_summary`, and its only status change after that is `finalize_close_turn`'s (`approved`) or a reopen's (`stale`). No capability edits it, because an edit surface would need a rule for what happens to the `approved` status the text carries, and nothing in `docs/product/` asks for one. The earlier wording here — that editing was "part of the approval gate" — described a gate that does not ship.

## Continuity status

**The two continuity artifacts each carry their own status: `draft` | `approved` | `stale`** — `Chapter.summary_status` for the summary, `ChapterNoteChangeset.status` for the changeset.

| Transition | Trigger | Result |
|---|---|---|
| → `draft` | owner requests the close (`POST …/close`; chapter enters `closing`), and the close-chapter turn's tools draft both artifacts (UC-047) | both artifacts `draft` |
| `draft` → `approved` | the close run's **deterministic finalize step**, on a clean run (`finalize_close_turn`) | both artifacts `approved` **in the same step** as `Chapter.state = closed` |
| `approved` → `stale` | owner reopens the chapter (UC-052, US-055) | re-closing re-runs the close procedure, which redrafts both artifacts from scratch |

**No transition is performed by a person reviewing anything** (feature `016`, design-note D3). `approved` is not a judgement recorded by the owner; it is what a clean run marks its own output, in the same step that closes the chapter. The status still means what it always meant — *this artifact can be trusted about the body it describes* — but what establishes the trust is the run completing without a blocking finding, not a signature.

The chapter's own `state` (`domain-chapter.md`) carries the *workflow* — is this chapter open, mid-close, or done. The status above carries the *artifact's* trustworthiness, and the two answer different questions.

### Why the status lives on the artifacts, not only on the chapter

Because **a stale summary is otherwise indistinguishable from an approved one**. The text of a summary does not change when the chapter it describes is reopened and rewritten — only its truthfulness does, and nothing about the string records that.

That distinction is load-bearing rather than tidy:

- The summary is exactly what FEAT-013 pushes into **every** chat's context baseline (US-057.AC-2 — summaries of all prior chapters). Feeding generation a summary that describes since-changed text is a silent correctness failure, and it compounds: every subsequent block is written against a false premise.
- It is also what FEAT-016's consistency check inspects. A check that cannot tell an approved summary from a stale one cannot raise the flag it exists to raise.

Marking the artifact means both consumers can ask the artifact directly, rather than inferring trust from the chapter's state and hoping the inference holds.

**These columns land at Stage 2, nullable and unused**, so Stage 4 is pure behaviour with no schema change — see `domain-chapter.md` → "Landing the continuity columns early" for the migration reasoning.

### The cascade is checked, not tracked

Whether staleness *cascades* to later chapters' changesets is deliberately not modelled: product closes challenge C12 by having FEAT-016's consistency check inspect later chapters against the changed text instead. That is why there is no cascade flag anywhere here — the check is the mechanism, and a cascade flag would be a second, weaker answer to the same question.

## Flag

| Field | Type / notes |
|---|---|
| `id` | snowflake PK |
| `chapter_id` | FK → `Chapter.id` — flags are chapter-scoped |
| `origin` | `check` \| `person` (US-076 — the two carry different weight) |
| `comment` | the flag's text |
| `status` | open / resolved (UC-068) |
| `created_by` / `created_at` | who raised it, when |
| `resolved_by` / `resolved_at` | null until resolved |

Flags are a **general chapter annotation, not consistency-only**: a member may raise one with a comment (UC-067), and `origin` records whether it came from the automated check or from a person, because the two are weighted differently by whoever reads them.

**The term is `flag`, everywhere.** The entity, the table, the `db/` module, the DTOs and every string the author reads all say *flag*.

Round 6 had adopted **"warning"** as an author-facing synonym, and this document carried the resulting split — internal `flag`, UI "warning" — with FEAT-016's own product wording parked as pending reconciliation. **Product reversed that decision on 2026-07-31** (`docs/product/features.md` → FEAT-016, *"Reversed 2026-07-31"*, `[confirmed: user]`): one term, and the parked reconciliation is resolved by not renaming at all. The reversal is recorded rather than quietly applied, because the split was a deliberate decision and its removal is another one. `frontend-workspace.md` states the same from the UI side.

**The verb is untouched.** The consistency check *warns* and never blocks — that is an ordinary English verb about what the check does, not a name for the record it leaves.

Flags are raised, never auto-applied: the check surfaces findings and **nothing is silently rewritten**. UC-066's *separate* "apply flags" act does not exist here — it belonged to the review stage this design does not build (see the header note) — but the guarantee underneath it survives intact, because no step of the close procedure rewrites content. Codex coverage is optional, so the check **warns and never blocks** (UC-080).

### Open in product, not resolved here

Several FEAT-016 questions carry `_TBD:` in `docs/product/` and are deliberately left alone: what happens when the check itself fails or is unavailable; whether resolving a flag that a later check raises again reopens it or raises a new one; whether flags survive a chapter's text changing under them; and whether an in-chat scoped finding (UC-088) can be promoted to a flag here. The schema above does not presuppose an answer to any of them.

**One of them now has a chosen answer in the architecture, and the `_TBD:` stays open.** For *"whether resolving a flag that a later check raises again reopens it or raises a new one"*, feature `016` chose neither: **`POST …/close` deletes every `origin = check` flag on the chapter before each run**, so a run's findings are that run's alone. `origin = person` flags are never touched — somebody wrote them deliberately, and they are advisory.

Deleting rather than resolving is the honest form. **Resolving would claim an act nobody performed**: a resolved flag carries `resolved_by` and `resolved_at`, and there is no truthful value for either. The rejected alternatives were comparing timestamps (fragile — the summary write re-stamps the chapter) and a per-run correlation id (new schema for a value that lives exactly one turn).

**This does not close the `_TBD:`.** Product owns that, and on 2026-07-31 it recorded the same behaviour under UC-068 while deliberately keeping the question open. What is recorded here is what the architecture does meanwhile, so a later reader does not re-derive it.

## The close procedure, as built

**Realizes:** feature `016.chapter-close-continuity` (2026-07-31). This is the mechanism behind UC-047 and behind the `draft → approved` row above. The chapter-state half is `domain-chapter.md`; the runtime half is `assistant-runtime.md`.

**Closing a chapter is an ordinary assistant turn, not a hidden call** (design-note D1). `POST …/close` moves the chapter `open → closing`, deletes its `origin = check` flags (above), and writes nothing else. The working page then posts a turn into the author's own chat with that chapter as its subject, and `determine_mode` resolves it to the seeded `close-chapter` mode. Five mode-gated tools in `services/close_tools.py` do the work:

| Tool | Writes |
|---|---|
| `draft_chapter_summary` | `Chapter.summary`, `summary_status = draft` |
| `draft_chapter_notes` | upserts the chapter's `ChapterNoteChangeset`, `status = draft` |
| `propose_active_notes` | nothing — proposes the resulting **live** note set, held in memory (below) |
| `raise_check_flag` | one `origin = check` flag per finding |
| `read_continuity_context` | nothing — returns `Book.active_notes` plus every previously-closed chapter's approved summary |

**A direct, non-streaming call was rejected.** It would have been shaped like sub-agent delegation (`assistant-runtime.md`) and it is more code, leaves **no transcript** of a procedure the author is meant to be watching, and adds a second prompt-composition path.

### Finalize is deterministic and server-side

**The model never decides whether the chapter closes** (D5). When the turn's generator reaches natural completion, `services/chapters.py::finalize_close_turn` runs **once** and decides from four independent facts:

| Fact | Required for a clean run |
|---|---|
| `Chapter.summary_status` | `draft` — the summary tool was called |
| the chapter's `ChapterNoteChangeset.status` | a row exists, and it is `draft` |
| the in-run active-notes proposal | **not `None`** — the proposal tool was called at least once |
| open `origin = check` flags on the chapter | none |

A clean run sets `Chapter.state = closed`, marks **both** artifacts `approved`, and writes `Book.active_notes` from the proposal. Anything else returns the chapter to `open` and wipes the run's artifacts. It never raises for a business-rule outcome — a refused close is an *outcome*, not an error, and raising would put the decision back on the caller.

**A `None` proposal routes to the wipe branch deliberately, and this is the one branch worth remembering.** Treating an uncalled tool as an implicit `""` would overwrite every accumulated note in the book — the single failure `Book.active_notes` exists to prevent. So the proposal is a **required** artifact of a clean run, exactly like the summary and the changeset. `""` is a legitimate proposal ("the live set becomes empty"); `None` is "nobody proposed anything".

### The proposal is held in memory until finalize

`propose_active_notes` writes no row. It sets `active_notes_proposal` on the per-turn `ToolContext`, and `finalize_close_turn` reads it (D7).

That is what makes discarding free: **nothing was ever applied**, so a stop or a failure needs no undo and no stashed prior value. Two alternatives were rejected for reasons worth keeping — **appending `added` to `active_notes` on close** is silently wrong, because three free-text deltas have no correct mechanical merge; **writing during the run** would need the old value stashed to honour a discard, which is a transaction by another name in a `db/` layer that has none (`domain-chapter.md` → "As built there is no transaction").

### `closing` exists only while the turn streams

A stop, a failure and a blocking flag all return the chapter to `open` with every artifact discarded (D4). There is no state in which draft continuity sits on an open chapter waiting for somebody: `closing` is a **window, not a resting place**. `POST …/close/cancel` is the explicit exit and performs the same wipe the failure branch does.

Keeping partial drafts as `draft` for the next run was rejected because it produces an `open` chapter carrying continuity that describes a body still being written — precisely the condition the `draft` / `approved` / `stale` split exists to make impossible.

**Accepted limitation, stated plainly.** The wipe is uniform, not history-aware: on a *re*-close that fails, the chapter's prior (stale) changeset row is deleted along with this run's draft, so the last-known changeset text is gone until the chapter closes cleanly. No history mechanism exists for changesets the way `ChapterTextRevision` exists for bodies, and building one was out of scope. Accepted rather than solved.

### The consistency check is this mode's own work

The check (UC-064, UC-065, UC-080) is **not a second subsystem**. It is the `close-chapter` turn reading the chapter's text, the prior summaries, the live notes and the codex through tools that already exist, and raising a flag per finding — which is what made pulling it into feature `016` affordable at all (D2).

A **deterministic** checker was rejected outright: state notes are free text, so there is nothing to check deterministically. That is the same fact "no entity model" has consequences for throughout this document.

## What is *not* modelled

**No character/place entity model.** State notes are free text, by explicit product decision, and the direct consequence product records — that staleness cannot be flagged per subject — stands. The codex (`domain-codex.md`) is the stable-identity half of that story; a note is the change half. Identity vs. change is the distinction, and collapsing them into one entity would undo it.
