# Domain — Continuity: notes, summaries and flags

**Realizes:** FEAT-012 (UC-047..052, UC-079, UC-089, UC-091), FEAT-016 (UC-066, UC-067, UC-068, UC-080); US-049..055, US-076, US-090, US-104, US-106

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

- the **chapter close path** (UC-047/UC-048) writes the chapter's changeset **and** `Book.active_notes`;
- a **direct note edit** (UC-050) writes `active_notes` alone.

Members see current truth (UC-049), not a historical accumulation; a chapter's own delta is read from its changeset row (UC-051).

### UC-079 — a note references a codex entry by name, not by foreign key

Named entries (character, location) are *name-addressable* by product's own account of what a name buys (US-078); a note naming "Marek" is resolved against `CodexEntry.name` (`domain-codex.md`) at the point of use. This keeps notes genuinely free text — a link table would be the entity model product declined to build — and it is what makes FEAT-016's UC-080 check possible: an unresolvable or archived name is exactly the warning the check is asked to raise.

Because the reference is by name and not by key, **archiving an entry cannot break a note** at the database level. The breakage is semantic, and semantic breakage is precisely what the check is for (UC-072 postcondition, US-092).

## Summaries

`Chapter.summary` is a field on the chapter (`domain-chapter.md`), not a table of its own — one chapter has exactly one summary, and it is read on the same paths the chapter is.

Once approved it is viewable read-only (UC-089, US-104) on Book state (UC-091) and on the settings-side continuity view (`frontend-workspace.md`). Editing it is part of the approval gate, not a separate capability.

## Continuity status

**The two continuity artifacts each carry their own status: `draft` | `approved` | `stale`** — `Chapter.summary_status` for the summary, `ChapterNoteChangeset.status` for the changeset.

| Transition | Trigger | Result |
|---|---|---|
| → `draft` | owner requests the close; the system drafts both artifacts (UC-047). Chapter enters `closing` | both artifacts `draft` |
| `draft` → `approved` | owner reviews, edits and approves **both together** at the gate (UC-048) | chapter may become `closed` (US-051) |
| `approved` → `stale` | owner reopens the chapter (UC-052, US-055) | re-closing requires re-approval |

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

**The internal name stays `flag`.** Round 6 adopted **"warning"** as the *author-facing* term (used on Book state and the working-page surfaces), and FEAT-016's own product wording is recorded as **pending reconciliation** alongside its already-parked rewrite. Renaming the entity now would half-apply a rename that `docs/product/` has not finished — the table, the `db/` module and the DTOs stay `flag`; the UI string is "warning". `frontend-workspace.md` states the same mapping from the other side.

Flags are raised, never auto-applied: the check surfaces findings and **nothing is silently rewritten** (UC-066). Codex coverage is optional, so the check **warns and never blocks** (UC-080).

### Open in product, not resolved here

Several FEAT-016 questions carry `_TBD:` in `docs/product/` and are deliberately left alone: what happens when the check itself fails or is unavailable; whether resolving a flag that a later check raises again reopens it or raises a new one; whether flags survive a chapter's text changing under them; and whether an in-chat scoped finding (UC-088) can be promoted to a flag here. The schema above does not presuppose an answer to any of them.

## What is *not* modelled

**No character/place entity model.** State notes are free text, by explicit product decision, and the direct consequence product records — that staleness cannot be flagged per subject — stands. The codex (`domain-codex.md`) is the stable-identity half of that story; a note is the change half. Identity vs. change is the distinction, and collapsing them into one entity would undo it.
