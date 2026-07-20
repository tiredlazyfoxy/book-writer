# Spec plan — book domain & multi-author collaboration   (2026-07-20)

**Mode:** Workflow C (augment) · **Writer mode:** `changes` · **Layout:** escalate small → large

Primary source for `product-spec-writer`. Ids below are **allocated by the orchestrator**; the
writer transcribes them and never mints, renumbers or reuses one.

Evidence: `docs/.cache/product/interview.md` (§ "Augment round — the book domain & multi-author
collaboration", 2026-07-20) · Coherence: `docs/.cache/product/analysis.md`.

> The previous round (foundation layer, FEAT-001..005) is **delivered** — its plan is preserved at
> `spec-plan.foundation-round.md`, and its real record is `docs/product/*` itself. This file covers
> the augment round only.

---

## 1. File plan

**Layout escalates to large.** `stories.md` is 309 lines and `use-cases.md` 251; six new features
would breach the ~400-line budget set in `docs/product/CLAUDE.md`.

| File | Action |
|---|---|
| `use-cases.md` | **split** → `use-cases/<FEAT-###>.<slug>.md`, then the flat file is removed |
| `stories.md` | **split** → `stories/<FEAT-###>.<slug>.md`, then the flat file is removed |
| `quick-reference.md` | **new** — dense id registry (large-layout lookup surface) |
| `features.md` | **amend** — six new FEAT blocks + registry rebuilt. Never splits. |
| `actors.md` | **amend** — ACT-004..006 appended; ACT-001 block amended in place |
| `vision.md` | **amend** — Scope, Non-goals, Success signals, Who has it |
| `glossary.md` | **amend** — new domain terms appended |

**Split rule — content moves, ids do not change.** Existing FEAT-001..005 use cases and stories are
relocated **verbatim**. Any reworded, merged, renumbered or dropped entry is a defect. Slugs:

```
FEAT-001.first-run-bootstrap      FEAT-007.membership-visibility
FEAT-002.authentication-session   FEAT-008.chapter-skeleton-sketches
FEAT-003.user-management          FEAT-009.chapter-writing-blocks
FEAT-004.llm-server-connections   FEAT-010.proposal-mode
FEAT-005.database-consistency     FEAT-011.content-moderation
FEAT-006.book-lifecycle-ownership
```

Existing UC→FEAT and US→FEAT ownership is already recorded in `features.md`'s registry — use it as
the split key.

---

## 2. Allocated ids

### Actors — ACT-004..006 (new), ACT-001 (amended)

| id | name | one-liner |
|---|---|---|
| ACT-004 | Book owner | The author who created a book (or received it by transfer); controls its skeleton, membership, mode and visibility. |
| ACT-005 | Co-author | An author granted access to someone else's book; writes within the rules the owner sets. |
| ACT-006 | Reader | A logged-in user reading a public book they are not a member of. |

- **ACT-001 Administrator — amend in place.** Add to Goal: moderate book content through the admin
  interface, and restore ownership of books whose owner is disabled. Add to Constraints: **cannot
  participate in a book** — no authoring access in the main interface; admin access to book content
  exists only as the moderation view (FEAT-011).
- **ACT-004/005 are relationships to a book, not account roles.** ACT-002 Author remains the
  account; one author account may be owner of some books and co-author of others at the same time.
  State this in both blocks so they never collide with FEAT-003's `admin`/`author` role values.

### Features — FEAT-006..011

| id | name | priority | actors | realized by |
|---|---|---|---|---|
| FEAT-006 | Book lifecycle & ownership | must | ACT-002, ACT-004, ACT-001 | UC-021..025, US-022..026 |
| FEAT-007 | Membership & visibility | must | ACT-004, ACT-005, ACT-006 | UC-026..030, US-027..031 |
| FEAT-008 | Chapter skeleton & sketches | must | ACT-004, ACT-005 | UC-031..034, US-032..035 |
| FEAT-009 | Chapter writing in blocks | must | ACT-004, ACT-005 | UC-035..039, US-036..041 |
| FEAT-010 | Proposal mode | should — build last | ACT-004, ACT-005 | UC-040..042, US-042..044 |
| FEAT-011 | Content moderation | must | ACT-001, ACT-004 | UC-043..046, US-045..048 |

All six: `Status: proposed`, `Source: [confirmed: user] interview 2026-07-20`, citing the named
interview heading.

### Use cases — UC-021..046

| id | title | feature |
|---|---|---|
| UC-021 | Create a book | FEAT-006 |
| UC-022 | List my books | FEAT-006 |
| UC-023 | Archive a book | FEAT-006 |
| UC-024 | Transfer ownership | FEAT-006 |
| UC-025 | Admin reassigns ownership of a book whose owner is disabled | FEAT-006 |
| UC-026 | Add a co-author | FEAT-007 |
| UC-027 | Remove a co-author | FEAT-007 |
| UC-028 | Set book visibility (private / public) | FEAT-007 |
| UC-029 | Read a public book | FEAT-007 |
| UC-030 | List books shared with me | FEAT-007 |
| UC-031 | Add a chapter | FEAT-008 |
| UC-032 | Reorder chapters | FEAT-008 |
| UC-033 | Edit a chapter sketch | FEAT-008 |
| UC-034 | Remove a planned chapter | FEAT-008 |
| UC-035 | Open a chapter for writing | FEAT-009 |
| UC-036 | Close the open chapter | FEAT-009 |
| UC-037 | Reopen a closed chapter | FEAT-009 |
| UC-038 | Add a block to the open chapter (free mode) | FEAT-009 |
| UC-039 | Edit a block that changed underneath | FEAT-009 |
| UC-040 | Submit proposed blocks | FEAT-010 |
| UC-041 | Owner reviews and applies proposals | FEAT-010 |
| UC-042 | Change the book's collaboration mode | FEAT-010 |
| UC-043 | Admin opens a book in the moderation view | FEAT-011 |
| UC-044 | Quarantine a book | FEAT-011 |
| UC-045 | Destroy a quarantined book | FEAT-011 |
| UC-046 | Owner sees a removal notice | FEAT-011 |

### Stories — US-022..048

| id | title | feature | covers |
|---|---|---|---|
| US-022 | Author creates a book and becomes its owner | FEAT-006 | UC-021 |
| US-023 | Author sees the books they own | FEAT-006 | UC-022 |
| US-024 | Owner archives a book | FEAT-006 | UC-023 |
| US-025 | Owner transfers a book to a co-author | FEAT-006 | UC-024 |
| US-026 | Admin restores ownership of an orphaned book | FEAT-006 | UC-025 |
| US-027 | Owner adds a co-author | FEAT-007 | UC-026 |
| US-028 | Owner removes a co-author, content and attribution survive | FEAT-007 | UC-027 |
| US-029 | Owner switches a book between private and public | FEAT-007 | UC-028 |
| US-030 | Logged-in reader opens a public book read-only | FEAT-007 | UC-029 |
| US-031 | Co-author sees books shared with them | FEAT-007 | UC-030 |
| US-032 | Member adds a chapter to the skeleton | FEAT-008 | UC-031 |
| US-033 | Owner reorders chapters | FEAT-008 | UC-032 |
| US-034 | Member edits the sketch of a planned chapter | FEAT-008 | UC-033 |
| US-035 | Member removes a planned chapter | FEAT-008 | UC-034 |
| US-036 | Owner opens a chapter for writing | FEAT-009 | UC-035 |
| US-037 | Only one chapter can be open at a time | FEAT-009 | UC-035 |
| US-038 | Owner closes the open chapter | FEAT-009 | UC-036 |
| US-039 | Owner reopens a closed chapter | FEAT-009 | UC-037 |
| US-040 | Co-author adds a block in free mode | FEAT-009 | UC-038 |
| US-041 | Concurrent edits to the same block warn the second author | FEAT-009 | UC-039 |
| US-042 | Co-author submits proposed blocks | FEAT-010 | UC-040 |
| US-043 | Owner applies proposals selectively | FEAT-010 | UC-041 |
| US-044 | Owner changes the collaboration mode | FEAT-010 | UC-042 |
| US-045 | Admin reads a book in the moderation view only | FEAT-011 | UC-043 |
| US-046 | Admin quarantines a book | FEAT-011 | UC-044 |
| US-047 | Admin destroys a quarantined book | FEAT-011 | UC-045 |
| US-048 | Owner is told their book was removed and why | FEAT-011 | UC-046 |

Every `US-###` carries ≥1 `US-###.AC-#` in Given/When/Then form, one falsifiable outcome per
criterion, no implementation in the Then clause.

---

## 3. Per-file outlines

### FEAT-006 — Book lifecycle & ownership
Create a book: the creator becomes its owner and chooses **collaboration mode** (free / proposal)
and **visibility** (private / public) at creation. Owner lists their books; archives a book
(reversible shelving, **never destroyed** — consistent with FEAT-003's no-hard-delete rule);
transfers ownership to a co-author. An admin can reassign ownership when the current owner's
account is disabled — FEAT-003 disables rather than deletes, so books outlive their owner.
**Must cross-reference FEAT-011:** archive is the owner's reversible action; only admin moderation
destroys a book. Exception flows: archiving a book with an open chapter; transferring to a
non-member; reassigning a book whose owner is still active.

### FEAT-007 — Membership & visibility
Owner adds and removes co-authors. **Removal preserves both the removed author's blocks and their
attribution** — they lose access, their text stays credited to them (mirrors FEAT-003). Visibility
is the owner's choice: *private* = owner + co-authors only; *public* = **read-only to any
logged-in user**, never anonymous. Reader (ACT-006) can open but not modify a public book, and
cannot see a private one. Co-authors list books shared with them. Exception flows: removing the
last co-author; removing a co-author with pending proposals; a public book being made private
while a reader has it open. `_TBD:` whether public books are discoverable or link-only.

### FEAT-008 — Chapter skeleton & sketches
A book holds an **ordered set of chapters**. Any member may add a chapter; **only the owner sets
the order**. A *planned* chapter carries a **sketch** — the idea/outline used to build the book's
skeleton before writing. **Any member may edit the sketch of any planned chapter, in parallel** —
this is the parallel-work surface that makes the single-open-chapter rule workable (see challenge
C3). Removing a planned chapter. Exception flows: editing the sketch of an open or closed chapter;
reordering while a chapter is open; two members editing the same sketch.

### FEAT-009 — Chapter writing in blocks
Chapter state machine: **planned → open → closed**, with reopen returning closed → open. **At most
one open chapter per book**; **only the owner** opens, closes and reopens. Opening a chapter while
another is open must state its outcome (refused, or closes the other — write what the interview
supports and mark the rest `_TBD:`). A chapter is written in **blocks**, the unit of authorship.
In free mode any member adds blocks directly; **concurrent adds of different blocks both land**.
Editing the **same** block warns the second saver, who may then overwrite or abandon — later write
wins. `_TBD:` what a block contains (format, length, structure) — a user-confirmed deferral, do
not fill it. Exception flows: adding a block when no chapter is open; a non-owner attempting to
open/close; the warned author abandoning their edit.

### FEAT-010 — Proposal mode
The book's collaboration mode is a **book-level property set by the owner at creation and
changeable at any time**. In proposal mode a co-author submits **proposed blocks** for the open
chapter rather than applying them. The owner reviews and **applies selectively — approval is a
merge, not a binary accept**: they may take some proposed blocks and not others, across several
co-authors' proposals. One line stating the difference from FEAT-009: *free mode applies a block on
save; proposal mode holds it until the owner applies it.* `_TBD:` fate of pending proposals when
the owner switches a book to free mode. Exception flows: proposing when no chapter is open;
proposing in free mode; the owner applying nothing.

### FEAT-011 — Content moderation
**Admin-interface only.** An admin can open any book in a **moderation read view** whose purpose is
finding unwanted or illegal content. An admin **never participates** in a book — no authoring
access in the main interface, in any mode, regardless of the book's visibility. Removal is two
distinct steps: **quarantine** (book becomes invisible to everyone including its members —
immediate takedown, recoverable from mistakes) and, separately, **destroy** (permanent). Book-level
granularity only — never per chapter or per block. **The owner sees a removal notice with a
reason.** **Must cross-reference FEAT-006:** this is the single sanctioned exception to
archive-only, and it exists because illegal content has to actually leave the instance.
`_TBD:` whether a quarantined book can be released back to its members. Exception flows:
quarantining a book with an open chapter; destroying a book that was never quarantined; the owner
opening a quarantined book.

### `vision.md` — amendments (mandatory; the doc set self-contradicts without them)
- **Scope** — add the book layer: books owned and shared, chapters with sketches, block writing in
  two collaboration modes, admin moderation. Note the foundation layer stands unchanged.
- **Non-goals** — the existing blanket deferral of the authoring domain is **narrowed**, not
  deleted. Deferred now: what a block contains, and the LLM generation pipeline. Record that the
  deferral was lifted deliberately for this slice (challenge C1), so the reversal is visible.
- **Success signals** — add one book-layer signal (C5): an author can create a book, invite
  co-authors, build a chapter skeleton with sketches, write a chapter in blocks in either mode,
  and an admin can remove illegal content.
- **Who has it** — add ACT-004..006.
- **What happens without it** — honest per C2: this is greenfield and no workaround exists; do not
  invent a cost.

### `glossary.md` — new terms
Book · Book owner · Co-author · Chapter · Chapter states (planned / open / closed) · Sketch ·
Block · Collaboration mode · Free mode · Proposal mode · Proposal (proposed block) · Private book ·
Public book · Archive (book) · Quarantine · Moderation view.

Distinguish explicitly, because each pair is confusable: *archive vs quarantine vs destroy* ·
*private vs public* · *free vs proposal mode* · *sketch vs block* · *owner/co-author (per book) vs
admin/author (account role)*.

### `quick-reference.md` — new
Dense registry: every ACT / FEAT / UC / US id with one-liner, status and owning feature.
Exempt from the line budget. `features.md` stays the canonical registry.

---

## 4. Relationships

Full matrix, goal closure, overlaps, dependency edges and conflicts:
`docs/.cache/product/analysis.md`. Summary for the `features.md` Relationships block:

- Build order: **FEAT-006 → 007 → 008 → 009 → 011 → 010** (FEAT-010 last per C6; FEAT-011 may move
  earlier — it depends only on FEAT-006). No cycles.
- Cross-layer edge: **FEAT-006 → FEAT-003** (accounts own books; disable-not-delete is what makes
  UC-025 necessary).
- Accepted overlaps: FEAT-009/FEAT-010 (same block unit, different gate) · FEAT-006/FEAT-011
  (archive vs quarantine — different actor, different reversibility).
- No orphan actors, no orphan features, no structural orphans, no unresolved conflicts.

## 5. Deferrals → `_TBD:`

| `_TBD:` | Lives in |
|---|---|
| What a block contains (format, length, structure) | FEAT-009 |
| Fate of pending proposals when switching to free mode | FEAT-010 / UC-042 |
| Whether public books are discoverable or link-only | FEAT-007 |
| Whether a quarantined book can be released to its members | FEAT-011 |
| The LLM generation pipeline | `vision.md` non-goals |

## 6. Writer constraints

- **Never allocate an id.** Every id is in this file. Nothing else gets one.
- **Never renumber or reword an existing id** during the split. Content moves verbatim.
- **Merge fences** — edit only inside `<!-- product-spec:start -->` / `<!-- product-spec:end -->`.
- **No technical decisions.** No schema, endpoint, storage, library or layering anywhere.
- **Do not fill a `_TBD:`.** They are user-confirmed deferrals, not gaps to close.
- Amend `vision.md` in this same pass — omitting it leaves the doc set self-contradicting.
