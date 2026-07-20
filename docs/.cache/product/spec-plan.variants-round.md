# Spec plan — variants, cloning & consistency   (2026-07-20, augment round 3)

**Mode:** Workflow C (augment) · **Writer mode:** `changes` · **Layout:** large + registry move

Primary source for `product-spec-writer`. Ids are **allocated by the orchestrator**; the writer
transcribes and never mints, renumbers or reuses one.

Evidence: `docs/.cache/product/interview.md` § "Augment round 3 — variants, cloning & consistency
(2026-07-20)" · Coherence: `docs/.cache/product/analysis.md` § "Round 3".

> Prior rounds archived: `spec-plan.foundation-round.md`, `spec-plan.book-round.md`,
> `spec-plan.continuity-round.md`. Their record is `docs/product/*`.

---

## 0. Carried-over fix from the round-3 review (apply first, do not skip)

The previous round closed CHANGES_REQUESTED with **one blocking item**, deliberately folded into
this round instead of a dedicated pass:

- **`features.md` FEAT-012 Note (or `use-cases/FEAT-012...md` UC-050 — one of the two).** State the
  free-mode-edit / close-gate interaction, which is currently unstated anywhere: *in free mode a
  member's state-note edits apply immediately, and the owner still reviews the chapter's
  state-note changeset at the close gate (UC-048) — a co-author's change can be revised by the
  owner before the chapter closes.* Without it a reader concludes a co-author's edit is final.

Two cosmetic fixes from the same review, also apply:
- `features.md` FEAT-012 Note: two `_TBD:` deferrals share one backtick span with mismatched
  italic delimiters. Split into two properly-closed spans.
- `features.md` FEAT-013 Note: `_TBD:` about model choice is missing its closing underscore.

---

## 1. File plan

| File | Action |
|---|---|
| `use-cases/FEAT-014.chapter-variants.md` | **new** — UC-058..060 |
| `use-cases/FEAT-015.book-cloning.md` | **new** — UC-061..063 |
| `use-cases/FEAT-016.consistency-flags.md` | **new** — UC-064..068 |
| `stories/FEAT-014.chapter-variants.md` | **new** — US-062..065 |
| `stories/FEAT-015.book-cloning.md` | **new** — US-066..071 |
| `stories/FEAT-016.consistency-flags.md` | **new** — US-072..077 |
| `features.md` | **amend + registry removed** (see §6) |
| `quick-reference.md` | **amend — becomes the sole canonical registry** |
| `docs/product/CLAUDE.md` | **amend — contract change** (see §6) |
| `use-cases/FEAT-012...md`, `stories/FEAT-012...md` | **amend** — C12 `_TBD:` closed |
| `use-cases/FEAT-009...md`, `stories/FEAT-009...md` | **amend** — UC-037/US-039 cross-ref only |
| `use-cases/FEAT-011...md` | **amend** — moderation does not reach clones |
| `use-cases/FEAT-007...md` | **amend** — private books: owner-only cloning |
| `vision.md`, `glossary.md` | **amend** |
| `actors.md` | **no change** — no new actors |

---

## 2. Allocated ids

**No new actors.** ACT-004 and ACT-005 cover everything. ACT-006 Reader gains nothing — readers
cannot clone; this was put to the user and declined.

### Features

| id | name | priority | actors | realized by |
|---|---|---|---|---|
| FEAT-014 | Chapter variants & fixes | must | ACT-004, ACT-005 | UC-058..060, US-062..065 |
| FEAT-015 | Book cloning | must | ACT-004, ACT-005 | UC-061..063, US-066..071 |
| FEAT-016 | Consistency check & chapter flags | must | ACT-004, ACT-005 | UC-064..068, US-072..077 |

All three: `Status: proposed`, `Source: [confirmed: user] interview 2026-07-20`, citing the round-3
interview headings.

### Use cases — UC-058..068

| id | title | feature |
|---|---|---|
| UC-058 | Edit a reopened chapter, creating a variant | FEAT-014 |
| UC-059 | View and compare a chapter's variants | FEAT-014 |
| UC-060 | Select the active variant | FEAT-014 |
| UC-061 | Owner clones a book | FEAT-015 |
| UC-062 | Co-author clones a public book | FEAT-015 |
| UC-063 | Choose which members carry over to a clone | FEAT-015 |
| UC-064 | Run a consistency check on demand | FEAT-016 |
| UC-065 | Run the consistency check when closing a fixed chapter | FEAT-016 |
| UC-066 | Apply flags from consistency warnings | FEAT-016 |
| UC-067 | Member raises a flag on a chapter | FEAT-016 |
| UC-068 | Resolve a flag | FEAT-016 |

### Stories — US-062..077

| id | title | feature | covers |
|---|---|---|---|
| US-062 | Editing a closed chapter creates a new variant | FEAT-014 | UC-058 |
| US-063 | Member views and compares a chapter's variants | FEAT-014 | UC-059 |
| US-064 | Owner selects which variant is the chapter | FEAT-014 | UC-060 |
| US-065 | Switching the active variant is treated as a fix | FEAT-014 | UC-060 |
| US-066 | Owner clones a book | FEAT-015 | UC-061 |
| US-067 | A clone is fully independent of its source | FEAT-015 | UC-061 |
| US-068 | Co-author clones a public book and becomes its owner | FEAT-015 | UC-062 |
| US-069 | Only the owner may clone a private book | FEAT-015 | UC-062 |
| US-070 | The cloner chooses which members carry over | FEAT-015 | UC-063 |
| US-071 | A clone carries content, continuity, mode and visibility | FEAT-015 | UC-061 |
| US-072 | Owner runs a consistency check on demand | FEAT-016 | UC-064 |
| US-073 | Closing a fixed chapter runs the consistency check | FEAT-016 | UC-065 |
| US-074 | Owner responds to warnings by re-fixing or applying flags | FEAT-016 | UC-066 |
| US-075 | Member raises a flag with a comment | FEAT-016 | UC-067 |
| US-076 | A flag records whether it came from a check or a person | FEAT-016 | UC-067 |
| US-077 | Owner resolves a flag | FEAT-016 | UC-068 |

Every `US-###` carries ≥1 `US-###.AC-#` as Given/When/Then, one falsifiable outcome per criterion.

---

## 3. Per-file outlines

### FEAT-014 — Chapter variants & fixes
Editing a **reopened** chapter is a **fix**: the chapter **keeps all its variants** and authors can
see them. Following chapters stay. The **owner selects one active variant** — that is the chapter
for every purpose (reading, generation context, export); the others are readable history the owner
can switch back to. **Switching the active variant is treated exactly as a fix** — same
consistency-check path — because the chapter's text changed. The user explicitly asked for "an easy
way to see the variants", so viewing and comparing them is a first-class use case, not a footnote.

Do **not** spec how a variant is stored. "Even on fix we create a copy of the chapter" was the
user's phrasing of a mechanism (C20); the requirement is that **previous text stays recoverable**.

Exception flows: switching variants while a chapter is open elsewhere; editing a reopened chapter
and reverting to the original text; a non-owner attempting to select the active variant.

### FEAT-015 — Book cloning
Cloning produces a **new, fully independent book** — no link, no sync, no comparison with its
source. A clone carries: **chapters, blocks and sketches · state notes and summaries · membership ·
collaboration mode and visibility.** Member carry-over is **selectable** — the cloner chooses which
members come across, or none.

**Who may clone:** the owner, and co-authors. A **co-author's clone makes them its owner** (C23 —
deliberately accepted: co-authors are trusted, and forking is how creative variation happens).
**Only the owner may clone a private book** (C21) — this closes the privacy leak where a co-author
could clone a private book and publish the copy. FEAT-007 carries the same rule; both must state it.

Record the accepted cost in one line: two clones drift apart permanently, and a fix common to both
must be made twice. This was put to the user and accepted.

Exception flows: a co-author attempting to clone a private book; cloning a book with an open
chapter; cloning a book with unapproved continuity data; cloning an archived book.

### FEAT-016 — Consistency check & chapter flags
**This feature closes C12**, the staleness cascade deferred in two prior rounds.

**The check:** an LLM inspection of the book's chapters, summaries and state notes for
contradictions. It **reports to the owner and never rewrites anything.** A clean result requires no
action. Anything suspect becomes a **flag**.

**When it runs:** **on demand**, and **as part of closing a fixed chapter**. The user's flow, to be
specced as written: the owner closing a fixed chapter runs the check, reads the warnings, and then
either **fixes the chapter again** or **applies the flags** and closes.

**Flags** are a general chapter annotation, not a consistency-only artifact: a flag carries a
**comment**, **members can raise their own**, and **each flag records its origin** — consistency
check or person — because the two carry different weight. Flags are resolved.

Exception flows: the check failing or being unavailable (an LLM server is required — cross-ref
FEAT-004); closing a fixed chapter without running the check; resolving a flag that a later check
raises again; flags on a chapter whose active variant then changes.

### Amendments to delivered ids (ids unchanged, text amended)

- **FEAT-012** (`features.md` Note + `use-cases`/`stories` files): the **C12 cascade `_TBD:` is
  CLOSED**. Replace the marker with a cross-reference to FEAT-016 — do not leave a deferral
  standing for a question that has been answered. **Also apply §0's blocking fix here.**
- **FEAT-009 UC-037 / US-039** (reopen a closed chapter): add a cross-reference that editing after
  reopening produces a variant (FEAT-014). **Cross-reference only** — do not restate variant
  behaviour, and change nothing else in FEAT-009.
- **FEAT-011** (`use-cases/FEAT-011...md`, and the FEAT-011 block): state **plainly** that
  moderation does **not** reach clones — an admin moderates each book separately (C22). This is a
  real, permanent limitation of a feature whose purpose is removing illegal content. Write it as a
  stated limitation, not a hedge.
- **FEAT-007** (`use-cases/FEAT-007...md`): private books may be cloned **only by their owner**
  (C21), cross-referencing FEAT-015.

### `vision.md`
- **Scope** — add variations and corrections: chapter variants, whole-book cloning, LLM consistency
  checking with flags.
- **Success signals** — add one (C24): an author can correct an earlier chapter and be told what it
  broke, and can explore an alternative storyline without disturbing the original.
- **Non-goals** — unchanged. Do not reopen any existing deferral this round.

### `glossary.md`
Variant (chapter) · Active variant · Fix · Clone (book) · Consistency check · Flag · Flag origin ·
Resolve (a flag).
Distinguish explicitly: *variant vs clone* (one chapter's alternative text vs. a whole independent
book) · *fix vs clone* (correct this book vs. start a separate one) · *flag vs proposal* (a note
about a problem vs. proposed content).

---

## 4. Relationships

New edges: **FEAT-014 → FEAT-009** · **FEAT-016 → FEAT-014** · **FEAT-016 → FEAT-012** ·
**FEAT-016 → FEAT-004** (needs an LLM server) · **FEAT-015 → FEAT-006** · **FEAT-015 → FEAT-007**.
No cycles. **Build order remains unprescribed** — delegated to `/roadmap` by the user; do not write
one for FEAT-012..016.

New accepted overlaps: FEAT-014/FEAT-009 (reopening vs. what it produces) · FEAT-016/FEAT-012
(producing continuity vs. checking it) · FEAT-015/FEAT-006 (a clone is a book).

Resolved conflicts: **C21** (owner-only cloning of private books) · **C22** (moderation does not
reach clones, stated as a limitation).

## 5. Deferrals

**Closed this round:** the C12 cascade. Replace, don't leave.

**Still open and untouched** — do not resolve, reword or remove: whether an open chapter
contributes state notes before closing · which enabled model a chat uses · the five FEAT-012/013
exception-flow outcomes · everything deferred in earlier rounds.

## 6. The registry move — a contract change

`features.md` reached 393 of ~400 lines and never splits by rule. The user chose:

- **`quick-reference.md` becomes the SOLE canonical id registry.** It already holds every id; it
  keeps that role and is explicitly named canonical.
- **`features.md` keeps its FEAT blocks and Relationships, and its registry tables are removed** —
  the Actors / Features / Use cases / Stories tables move out entirely.
- **`docs/product/CLAUDE.md` must be amended in the same pass.** It currently states the registry
  lives in `features.md` (small layout) or `quick-reference.md` (large), and that `features.md`
  "remains the canonical registry either way". That sentence is now false — amend it so the
  contract matches reality. Amend **only** the registry-location rules; leave the id scheme,
  provenance tags, AC shape, merge-fence protocol and write-rules untouched.

Before removing anything from `features.md`, verify every id in its registry tables already appears
in `quick-reference.md`. **An id that exists only in the table being deleted would be lost** — that
is the one irreversible risk in this round.

## 7. Writer constraints

- **Never allocate an id.** Every id is in §2. No new actors.
- Amend delivered ids **only** where §3 names them, and only as described.
- **Merge fences only.** New files get one fenced block.
- **No technical decisions** — variant storage, clone mechanics, how the check is performed, and
  prompt/model detail are all `/architect`'s.
- **Do not fill any `_TBD:`** except C12's, which is closed by cross-reference to FEAT-016.
- Never invent a requirement. No answer behind an exception flow → write `_TBD:` and flag it.
- Verify the registry move loses nothing (§6).
