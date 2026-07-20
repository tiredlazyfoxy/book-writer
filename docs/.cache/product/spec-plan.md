# Spec plan — augment round 4: the codex

**Mode:** Workflow C (augment) · **Layout:** large (already escalated) · **Date:** 2026-07-20
**Confirmed by the user:** yes ("affirmative")

Prior rounds archived as `spec-plan.foundation-round.md`, `spec-plan.book-round.md`,
`spec-plan.continuity-round.md`, `spec-plan.variants-round.md`.

Interview: `docs/.cache/product/interview.md`, heading `## codex (2026-07-20, round 4)`.
Coherence: `docs/.cache/product/analysis.md`, heading `# Coherence — round 4 (codex)`.

---

## The model, as settled in the interview

A **codex** is the book's reference volume — the set of things the book is *about*, as opposed to
the prose itself. One codex per book.

A **codex entry** has a **kind**: `character`, `location`, or `fact`. All three are lore; character
and location are distinguished because they are **named**, and per the user a name buys exactly two
things — state notes attach to named entries, and named entries are addressable by name. A `fact`
has no timeline and nothing attaches to it.

- Entries follow the book's **collaboration mode** (free = any member edits; proposal = co-authors
  propose, owner applies) — the same rule as state notes (US-053).
- The codex is **members-only**. ACT-006 Reader never sees it, even on a public book.
- Entries are **archived, never deleted** — consistent with books (UC-023) and users (FEAT-003).
- Every entry keeps an **edit history** that a member can **view and restore** from.
- Entries can be **copied from another book the member belongs to** (the sequel case).
- One codex per book — **chapter variants (FEAT-014) share it**. Divergent worlds are what cloning
  (FEAT-015) is for.
- **Codex coverage is optional.** The user, verbatim: "not all the characters must be in the codex,
  but better to be." The consistency check therefore **warns and never blocks**. This is the
  anchor that makes FEAT-016's codex extension falsifiable — do not spec a completeness rule.

From the composition chat (FEAT-018), an author can ask the LLM to **generate** a new entry or
**rewrite** an existing one. Both take the same path: **shown in the chat first, saved only on
explicit request** — mirroring UC-055, where producing a block is a deliberate act. The user did
NOT select the diff-on-edit variant; do not spec a diff view.

**Out of scope, explicitly:** codex file export/import — the user ruled it technical and deferred it
to `/roadmap`. Do not write it.

**Routed to `/architect`, not specced here:** vector indexing, tool exposure, and how entries reach
the model's context. The user raised all three; the requirement captured instead is that the codex
grows beyond what can be shown wholesale, so generation must reach relevant entries **without the
author hand-picking them**.

---

## Id allocation (orchestrator-allocated; the writer transcribes only)

Registry before: 167 ids. After: **198**. Nothing renumbered, nothing reused, no new actors.

| Kind | Range | Count |
|---|---|---|
| Features | FEAT-017..018 | 2 |
| Use cases | UC-069..080 | 12 |
| Stories | US-078..094 | 17 |

### FEAT-017 — Codex · priority **must**

The entries themselves: kinds, authoring, archival, history, copying, visibility.
Depends on FEAT-006 + FEAT-007.

| id | title | actor |
|---|---|---|
| UC-069 | Create a codex entry | ACT-004, ACT-005 |
| UC-070 | Edit a codex entry | ACT-004, ACT-005 |
| UC-071 | Browse and search the codex | ACT-004, ACT-005 |
| UC-072 | Archive a codex entry | ACT-004, ACT-005 |
| UC-073 | View an entry's edit history | ACT-004, ACT-005 |
| UC-074 | Restore an entry to an earlier version | ACT-004, ACT-005 |
| UC-075 | Copy codex entries from another book | ACT-004, ACT-005 |

| id | title |
|---|---|
| US-078 | Member creates a codex entry of a given kind |
| US-079 | Codex entries follow the book's collaboration mode |
| US-080 | Member browses and searches the codex |
| US-081 | Member archives a codex entry rather than deleting it |
| US-082 | Member views an entry's edit history |
| US-083 | Member restores an entry to an earlier version |
| US-084 | Member copies codex entries from another book they belong to |
| US-085 | The codex is invisible to readers and non-members |

### FEAT-018 — Codex authoring from the composition chat · priority **should**

Generating and rewriting entries from the same chat surface that composes blocks.
Depends on FEAT-013 + FEAT-017. Ships after FEAT-017.

| id | title | actor |
|---|---|---|
| UC-076 | Generate a codex entry from a composition chat | ACT-004, ACT-005 |
| UC-077 | Rewrite an existing codex entry from a composition chat | ACT-004, ACT-005 |

| id | title |
|---|---|
| US-086 | Author generates a codex entry from the composition chat |
| US-087 | Author rewrites an existing entry from the chat |
| US-088 | A chat-authored entry is saved only on explicit request |

Failure handling is **not** re-specced — UC-056 (composition request fails) already covers it.
Both UC-076 and UC-077 point at UC-056 rather than duplicating it.

### Amendment use cases (land inside existing features' files)

| id | title | lands in |
|---|---|---|
| UC-078 | Composition chat draws on the codex | FEAT-013 |
| UC-079 | State note references a named codex entry | FEAT-012 |
| UC-080 | Consistency check warns about content with no codex entry behind it | FEAT-016 |

| id | title | lands in |
|---|---|---|
| US-089 | A composition chat can draw on the book's codex | FEAT-013 |
| US-090 | A state note names the codex entry it is about | FEAT-012 |
| US-091 | The check warns when a chapter references something absent from the codex | FEAT-016 |
| US-092 | An archived codex entry does not silently break existing state notes | FEAT-016 |
| US-093 | The moderation view includes the codex | FEAT-011 |
| US-094 | A clone carries the source book's codex | FEAT-015 |

---

## Amendments to existing blocks — narrow, named, nothing else

| Target | Change |
|---|---|
| FEAT-012 block | Gains: a state note names the codex entry it is about. Add UC-079/US-090. State the one-line difference from FEAT-017 (change vs. identity). |
| FEAT-013 block | Gains: the chat can draw on the codex. Add UC-078/US-089. State the accepted overlap with FEAT-018 (same surface, different output). |
| FEAT-016 block | Gains: the check covers the codex and may flag an entry; warns about missing entities. **Warns, never blocks** — coverage is optional. Add UC-080/US-091/US-092. |
| FEAT-011 block | Moderation view reaches the codex. Amend UC-043; add US-093. |
| FEAT-015 block | A clone carries the codex. Amend UC-061; add US-094. |
| FEAT-007 block | Readers are excluded from the codex. Amend UC-029. |
| `features.md` Relationships | New edges + the FEAT-012 inversion (finding R4-1). |
| `quick-reference.md` | 31 new rows. Sole canonical registry. |
| `glossary.md` | codex, codex entry, character, location, fact (kind), named entry, edit history. Distinctions block for **codex entry vs. state note**. |

**No `vision.md` change.** The codex is inside the book-domain scope lifted in round 1 and is not the
generation pipeline, which remains the standing non-goal. Do not amend it.

**No `actors.md` change.**

---

## Relationships

- New edges: FEAT-017→{006,007} · FEAT-012→FEAT-017 · FEAT-018→{013,017}. **Acyclic.**
- Suggested order: `006 → 007 → 017 → 012 → 013 → 018`.
- **Finding R4-1 (build-order inversion):** FEAT-012 was specced in round 2 as self-contained and
  now requires FEAT-017. Must be recorded in the Relationships block — the round-2 edge list would
  otherwise read as current.
- **Finding R4-2 (conflict cleared):** members-only codex vs. cloning a public book — no conflict;
  UC-062's actor is ACT-005, a member. ACT-006 has no clone use case.
- Accepted overlaps: FEAT-017/FEAT-012 (identity vs. change) · FEAT-018/FEAT-013 (shared surface).

---

## Open `_TBD:` for this round

1. The relevance criterion for drawing codex entries into a composition chat (challenge C27 — no
   measurable criterion was offered; write `_TBD:`, never a vague AC).
2. Codex file export/import (C30) — deferred to `/roadmap` as technical.
3. Whether archiving a codex entry can be undone.
4. Whether copying entries between books carries their edit history.

---

## Writer instructions

- Mode `changes`. Merge fences protect user prose; edit only inside `product-spec` marker pairs.
- New files: `use-cases/FEAT-017.codex.md`, `use-cases/FEAT-018.codex-from-chat.md`,
  `stories/FEAT-017.codex.md`, `stories/FEAT-018.codex-from-chat.md`.
- Amendment UCs/USs go into the **existing** per-feature files named above — do not create new files
  for them, and do not move any existing id.
- Every id above is already allocated. **Transcribe; never mint, never renumber.**
- Provenance: everything in "The model" section is `[confirmed: user]` interview 2026-07-20 round 4.
  Anything not covered there is `[inferred]` with the basis stated, or `_TBD:`. Never invent.
- No technical decision anywhere — no vector/index/embedding/tool/storage language in `docs/product/`.
