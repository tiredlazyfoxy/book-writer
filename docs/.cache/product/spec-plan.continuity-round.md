# Spec plan — continuity & block composition   (2026-07-20, augment round 2)

**Mode:** Workflow C (augment) · **Writer mode:** `changes` · **Layout:** large (already escalated)

Primary source for `product-spec-writer`. Ids below are **allocated by the orchestrator**; the
writer transcribes them and never mints, renumbers or reuses one.

Evidence: `docs/.cache/product/interview.md` § "Augment round 2 — continuity & block composition
(2026-07-20)" · Coherence: `docs/.cache/product/analysis.md` § round 2.

> Prior rounds are delivered and archived: `spec-plan.foundation-round.md` (FEAT-001..005),
> `spec-plan.book-round.md` (FEAT-006..011). Their record is `docs/product/*` itself.

---

## 1. File plan

Layout is already large. No new structural work.

| File | Action |
|---|---|
| `use-cases/FEAT-012.chapter-continuity.md` | **new** — UC-047..052 |
| `use-cases/FEAT-013.block-composition-chat.md` | **new** — UC-053..057 |
| `stories/FEAT-012.chapter-continuity.md` | **new** — US-049..055 |
| `stories/FEAT-013.block-composition-chat.md` | **new** — US-056..061 |
| `use-cases/FEAT-009.chapter-writing-blocks.md` | **amend UC-036 in place** (close gate) |
| `stories/FEAT-009.chapter-writing-blocks.md` | **amend US-038 in place** (close gate) |
| `features.md` | **amend** — FEAT-012/013 blocks, registry rows, Relationships updated |
| `quick-reference.md` | **amend** — new rows |
| `vision.md` | **amend** — Scope, Non-goals (C10 reversal), Success signals |
| `glossary.md` | **amend** — new terms |
| `actors.md` | **no change** — no new actors this round |

---

## 2. Allocated ids

**No new actors.** ACT-004 (Book owner) and ACT-005 (Co-author) cover both features. Do not
allocate an actor; do not amend existing actor blocks.

### Features

| id | name | priority | actors | realized by |
|---|---|---|---|---|
| FEAT-012 | Chapter summaries & state notes | must | ACT-004, ACT-005 | UC-047..052, US-049..055 |
| FEAT-013 | Block composition chat | must | ACT-004, ACT-005 | UC-053..057, US-056..061 |

Both: `Status: proposed`, `Source: [confirmed: user] interview 2026-07-20`, citing the round-2
interview headings.

### Use cases — UC-047..057

| id | title | feature |
|---|---|---|
| UC-047 | System drafts a chapter's summary and state-note changes on close | FEAT-012 |
| UC-048 | Owner reviews and approves a chapter's continuity data | FEAT-012 |
| UC-049 | View the book's current state notes | FEAT-012 |
| UC-050 | Edit state notes | FEAT-012 |
| UC-051 | View a chapter's state-note changeset | FEAT-012 |
| UC-052 | Reopening a chapter flags its continuity data stale | FEAT-012 |
| UC-053 | Start a composition chat | FEAT-013 |
| UC-054 | Iterate with the LLM on the next block | FEAT-013 |
| UC-055 | Produce a block from a composition chat | FEAT-013 |
| UC-056 | Composition request fails | FEAT-013 |
| UC-057 | End a composition chat | FEAT-013 |

### Stories — US-049..061

| id | title | feature | covers |
|---|---|---|---|
| US-049 | Continuity data is drafted when a chapter closes | FEAT-012 | UC-047 |
| US-050 | Owner approves a chapter's summary and state-note changes | FEAT-012 | UC-048 |
| US-051 | A chapter cannot close without approved continuity data | FEAT-012 | UC-048 |
| US-052 | Member views the book's current state notes | FEAT-012 | UC-049 |
| US-053 | Member edits state notes according to the collaboration mode | FEAT-012 | UC-050 |
| US-054 | Member views what a chapter changed in the state notes | FEAT-012 | UC-051 |
| US-055 | Reopening a chapter marks its continuity data stale | FEAT-012 | UC-052 |
| US-056 | Author starts and ends composition chats freely | FEAT-013 | UC-053, UC-057 |
| US-057 | The four continuity artifacts are available to a composition chat | FEAT-013 | UC-054 |
| US-058 | Author iterates with the LLM to refine the next block | FEAT-013 | UC-054 |
| US-059 | A produced block follows the book's collaboration mode | FEAT-013 | UC-055 |
| US-060 | A failed composition shows an error, offers retry, preserves the conversation | FEAT-013 | UC-056 |
| US-061 | A composition chat is visible only to its author | FEAT-013 | UC-057 |

Every `US-###` carries ≥1 `US-###.AC-#` in Given/When/Then form, one falsifiable outcome per
criterion, no implementation in the Then clause.

---

## 3. Per-file outlines

### FEAT-012 — Chapter summaries & state notes
Two artifacts, deliberately different:
- **Summary** — the condensed narrative of what a chapter contained. Backward-looking, per chapter.
- **State note** — **free text, no entity model**: what is currently true of characters and places
  ("changes or states of characters, some place conditions"). Not a shorter story — facts that must
  stay true going forward. The book has **one live set** of state notes.

**Changesets.** Each chapter records which state notes it **added, modified or deleted**. Current
state is what is true now; the per-chapter changeset preserves when a fact changed. Chapter N sees
current truth, never a contradictory accumulation.

**Production.** On closing a chapter the system **drafts** both the summary and the state-note
changes; the **owner reviews, edits and approves**. Approval is **required for the chapter to
close** — closing means continuity is complete.

**Editing.** State notes follow the **book's collaboration mode** (FEAT-010's mechanism): free mode
any member edits directly; proposal mode they propose and the owner applies. Note the interaction,
and state it in one line: members may edit notes freely, and the owner still signs off at the close
gate — a co-author's change can be revised by the owner at close.

**Staleness.** Reopening a closed chapter (UC-037) **flags its continuity data stale**; re-closing
requires re-approval. `_TBD:` the **cascade** — whether later chapters whose changesets built on the
edited chapter are also flagged. This is a user-confirmed deferral and a **named known hole**, not
an oversight; write it as such and do not solve it.

Exception flows: approving with the summary emptied; a state note deleted that a later chapter
modified; reopening a chapter whose continuity was never approved.

### FEAT-013 — Block composition chat
The author composes the next block by **chatting with the LLM**. A free-form prompt input; the
author creates, recreates and polishes until the block is right; the LLM then produces the block.

**Chats are started and ended freely** — not bound to one block or one chapter.

**The context guarantee** (this is the falsifiable replacement for "don't pollute the context" —
C11). A composition chat has all four available: **summaries of all prior chapters · the current
state notes · the full text of the open chapter · the sketches of upcoming chapters.** State them
as an observable guarantee; say nothing about how context is assembled, ordered, truncated or
budgeted — that is architecture's.

**Producing a block follows the book's collaboration mode** — it lands directly in free mode, and
becomes a **proposal** in proposal mode. One rule for how a block enters a chapter regardless of
origin.

**Editing a produced block is FEAT-009, not this feature.** Accepted overlap (C16) — state it in
one line and do not respec block editing.

**Failure:** the LLM being unreachable or returning nothing shows an **error with a retry action**,
and the **conversation is preserved** so nothing is retyped.

**Privacy:** a chat is **visible only to its author**. Only the produced block is shared. Note this
holds even for the owner — the owner approving a proposal sees the block, not how it was made.

`_TBD:` which enabled model a chat uses (may resolve as architecture's). `_TBD:` whether an open
chapter contributes state notes before it closes.
Exception flows: starting a chat with no chapter open; producing a block after the chapter closed
mid-session; composing when no LLM server is enabled (FEAT-004).

### FEAT-009 — amendments to existing ids (C17)
**Ids unchanged; text amended.**
- **UC-036** (Close the open chapter) — add the precondition that the chapter's summary and
  state-note changes are approved (UC-048). Add an exception flow: closing is refused while
  continuity data is unapproved.
- **US-038** (Owner closes the open chapter) — add an AC asserting a chapter with unapproved
  continuity data cannot reach closed.
Do not touch UC-037/US-039 (reopen) beyond what FEAT-012's UC-052 references. Change nothing else
in FEAT-009.

### `vision.md` — amendments
- **Scope** — add continuity (summaries + state notes) and LLM-assisted block composition.
- **Non-goals** — the **generation-pipeline deferral is lifted** (C10). This is the **third
  reversal in one session**; record it visibly, as with C1. Still deferred: prompt design, model
  selection strategy, context assembly, token budgets — and the character/place **entity model**,
  which this round explicitly declined to build.
- **Success signals** — add one: an author can write a chapter with LLM assistance that stays
  consistent with prior chapters without their full text being present.

### `glossary.md` — new terms
Summary (chapter) · State note · State-note changeset · Continuity data · Stale continuity ·
Composition chat · Produced block.
Distinguish explicitly: *summary vs state note* (narrative vs. fact that must stay true) ·
*state note vs sketch* (backward fact vs. forward outline) · *produced block vs proposal*.

---

## 4. Relationships

- New edges: **FEAT-012 → FEAT-009** (chapters must close) · **FEAT-013 → FEAT-012** (needs the
  artifacts) · **FEAT-013 → FEAT-010** (produced blocks become proposals) · **FEAT-013 → FEAT-009**
  (produces blocks) · **FEAT-013 → FEAT-004** (needs an enabled model). No cycles.
- **Build order is deliberately NOT prescribed this round** — the user delegated sequencing to
  `/roadmap`. Record the edges; do not write an order for FEAT-012/013 into `features.md`. The
  existing 006→007→008→009→011→010 order stands as previously recorded.
- Accepted overlaps: **FEAT-013 / FEAT-009** (composition ends at producing a block; editing it is
  FEAT-009) · **FEAT-012 / FEAT-008** (sketches are forward context, state notes are backward fact
  — both feed generation, neither replaces the other).
- Resolved conflict: **C17**, by amending UC-036/US-038 in place.

## 5. Deferrals → `_TBD:`

| `_TBD:` | Lives in |
|---|---|
| Staleness cascade through per-chapter changesets | FEAT-012 / UC-052 |
| Whether an open chapter contributes state notes before closing | FEAT-012 |
| Which enabled model a composition chat uses | FEAT-013 |
| Character/place entity model | `vision.md` non-goals |
| Prompt design, context assembly, token budgets | `vision.md` non-goals (architecture) |

Previously-recorded `_TBD:` markers are untouched — do not resolve, reword or remove any of them.

## 6. Writer constraints

- **Never allocate an id.** Every id is in §2. No new actors this round.
- **Amend UC-036 and US-038 in place** — ids keep their numbers; add only the close gate.
- **Do not touch any other FEAT-001..011 content.**
- **Merge fences** — edit only inside `<!-- product-spec:start -->` / `<!-- product-spec:end -->`.
- **No technical decisions.** The generation boundary is sharp: observable chat behaviour is
  product; prompts, model selection, context assembly, token budgets and storage are not.
- **Do not fill a `_TBD:`.** The cascade one especially — it is a named known hole.
- Keep the three registry surfaces (`features.md`, `quick-reference.md`, per-feature files) in
  agreement; last round they disagreed and it was the review's main finding.
