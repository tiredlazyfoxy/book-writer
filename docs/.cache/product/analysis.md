# Coherence analysis — book domain augment   (2026-07-20)

Findings from the coherence pass over the augmented spec (FEAT-001..011). Disposable working
artifact; the durable record is `docs/product/features.md`.

## 1. Coverage matrix — actor × feature

| | FEAT-001 | FEAT-002 | FEAT-003 | FEAT-004 | FEAT-005 | FEAT-006 | FEAT-007 | FEAT-008 | FEAT-009 | FEAT-010 | FEAT-011 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ACT-001 Administrator | | ✓ | ✓ | ✓ | ✓ | ✓ (reassign) | | | | | ✓ |
| ACT-002 Author | | ✓ | | | | ✓ | ✓ | ✓ | ✓ | ✓ | |
| ACT-003 First-run operator | ✓ | | | | | | | | | | |
| ACT-004 Book owner | | | | | | ✓ | ✓ | ✓ | ✓ | ✓ | |
| ACT-005 Co-author | | | | | | | ✓ | ✓ | ✓ | ✓ | |
| ACT-006 Reader | | | | | | | ✓ | | | | |

**No orphan actors. No orphan features.**

Notable: `ACT-002 Author` was a near-orphan before this round — it appeared only in FEAT-002
(login) and as the object of FEAT-003's admin actions, with no feature of its own. The book layer
gives it the goal the vision always claimed for it. This is the strongest coherence improvement of
the round.

`ACT-004 Book owner` and `ACT-005 Co-author` are **relationships to a book**, not account roles.
`ACT-002 Author` remains the account; a single author account is owner of some books and co-author
of others simultaneously. Recorded explicitly so they never collide with FEAT-003's `admin`/`author`
role values.

`ACT-006 Reader` is a thin actor by construction — one feature, one use case (UC-029). It is not
merged into ACT-002 because its access basis is different: it reaches a book it is *not a member of*.

## 2. Goal closure

Each actor's goal is reachable end-to-end through the feature set:

- **ACT-004 Book owner** — create (UC-021) → build skeleton (UC-031/032) → invite (UC-026) →
  open a chapter (UC-035) → write blocks (UC-038) → close (UC-036) → archive (UC-023). Closed.
- **ACT-005 Co-author** — invited (UC-026) → sees the book (UC-030) → edits sketches ahead of the
  open chapter (UC-033) → contributes blocks directly (UC-038) or by proposal (UC-040). Closed.
- **ACT-006 Reader** — a public book is readable (UC-029) once the owner sets visibility (UC-028). Closed.
- **ACT-001 Administrator** — moderation reachable end-to-end: open a book in the moderation view
  (UC-043) → quarantine (UC-044) → destroy (UC-045), with the owner notified (UC-046). Closed.
  Ownership recovery for a disabled owner's book: UC-025. Closed.

**No breaks.** No missing feature implied by an unreachable goal.

## 3. Overlap

- **FEAT-009 (free mode) vs FEAT-010 (proposal mode)** — both produce blocks in the open chapter.
  Not merged; the difference stated in one line in both blocks: *free mode applies a block on save;
  proposal mode holds it until the owner applies it.* Same unit (block), different gate. This is an
  **accepted overlap** and it is deliberate — it is why proposal mode can ship last without
  reworking FEAT-009.
- **FEAT-006 archive vs FEAT-011 quarantine/destroy** — both remove a book from view. Distinguished
  by actor and reversibility: archive is the **owner's** reversible shelving in the authoring
  interface; quarantine/destroy is the **admin's** moderation action, and destroy is terminal.
  Stated in one line in each block. **Accepted overlap.**

## 4. Dependencies

```
FEAT-003 ──→ FEAT-006 ──→ FEAT-007 ──→ FEAT-008 ──→ FEAT-009 ──→ FEAT-010
(accounts)     (book)      (members)    (chapters)    (blocks)    (proposals)
                 │
                 └────────→ FEAT-011 (moderation — acts on whole books only)
```

- FEAT-006 → FEAT-003: a book needs an account to own it, and UC-025 depends on FEAT-003's
  disable-not-delete rule (a disabled owner's books must outlive the account). **Cross-layer edge.**
- FEAT-007 → FEAT-006: membership needs a book.
- FEAT-008 → FEAT-007: "any member adds a chapter" needs membership defined.
- FEAT-009 → FEAT-008: writing needs a chapter to open.
- FEAT-010 → FEAT-009: proposals are proposed *blocks*; the block must exist as a concept first.
- FEAT-011 → FEAT-006: moderation acts at book granularity only; it does **not** depend on
  chapters, blocks or membership, so it can be built any time after FEAT-006.

**No cycles.** Suggested build order: **006 → 007 → 008 → 009 → 011 → 010**, with FEAT-010 last
per C6 and FEAT-011 free to move earlier if moderation becomes urgent.

## 5. Conflicts

- **Resolved (C9):** FEAT-006 says books are archived and never destroyed; FEAT-011 destroys them.
  Reconciled by scoping destruction to the admin moderation surface and naming it in both feature
  blocks as the single sanctioned exception. Both blocks must carry the cross-reference or the
  contradiction reappears — **flagged to the writer as mandatory.**
- **Resolved (C7/C9):** "private book" vs "admin reads all books". Admin reading moved out of
  FEAT-007 into FEAT-011, so the two surfaces are disjoint and `private` needs no qualifier in
  the authoring interface.
- **Resolved (C4):** "public" no longer conflicts with the instance-wide auth gate — public means
  logged-in users only.
- **Amended, not conflicting (C1/C5):** `vision.md`'s non-goal ("the fiction-authoring domain is
  deferred") is narrowed in this same pass to content-format + generation pipeline. If the writer
  adds FEAT-006..011 **without** amending vision.md, the doc set self-contradicts. **Mandatory.**

**No unresolved conflicts.**

## 6. Vision alignment

Every new feature must trace to a success signal. `vision.md` currently has none for the book
layer, so all six would be unjustified as written — resolved by C5: vision gains a book-layer
signal covering owned/shared books, the chapter skeleton with sketches, block writing in both
collaboration modes, and admin moderation.

## 7. Structural orphans

Checked ahead of writing: every FEAT-006..011 has ≥1 UC; every UC has ≥1 US; every US carries ≥1
Given/When/Then AC. **No structural orphans in the plan.** The reviewer re-checks after the write.

## 8. Notes carried into the write

- The `_TBD:` on **block contents** sits inside FEAT-009, the feature that depends on it most. It
  is a deliberate, user-confirmed deferral — not a gap the writer may fill.
- The `_TBD:` on **pending proposals during a mode switch** sits in FEAT-010/UC-042. It is a real
  behavioural hole and should be closed before FEAT-010 is planned, not before it is specced.
- The **file split** (flat → per-feature) moves existing FEAT-001..005 content unchanged. Any id
  appearing in a different file with different text is a defect, not an improvement.

---

# Round 2 — continuity & block composition   (2026-07-20)

Coherence pass over FEAT-012 and FEAT-013 against the delivered set (FEAT-001..011).

## Coverage

No new actors. ACT-004 (Book owner) and ACT-005 (Co-author) gain both features; ACT-006 (Reader)
and ACT-001 (Administrator) are untouched — correct, since a reader does not compose and an admin
does not participate (FEAT-011's constraint holds).

Check performed: does the actor set still explain the feature set? Yes. Both new features are
author-facing; neither introduces a role that has no home.

## Goal closure

**ACT-004 Book owner** — writes a chapter with LLM assistance (UC-053..055) → approves its
continuity data (UC-048) → closes it (UC-036, amended) → the next chapter's generation sees the
summary and state notes (UC-054). **Closed loop, and it is the loop the product exists for.**

**ACT-005 Co-author** — composes in a private chat (UC-053, UC-061), produces a block that lands
directly or becomes a proposal per mode (UC-055), edits state notes per mode (UC-050). Closed.

## Dependency edges (new)

```
FEAT-004 ──────────────┐
FEAT-009 ──→ FEAT-012 ─┼─→ FEAT-013
FEAT-010 ──────────────┘
```

- FEAT-012 → FEAT-009 — continuity is produced on chapter close.
- FEAT-013 → FEAT-012 — the context guarantee needs summaries and state notes to exist.
- FEAT-013 → FEAT-010 — a produced block becomes a proposal in proposal mode.
- FEAT-013 → FEAT-009 — a produced block is a block; editing it is FEAT-009.
- FEAT-013 → FEAT-004 — composition needs an enabled model.

**No cycles.** Build order deliberately unprescribed — delegated to `/roadmap` by the user.

## Overlaps

- **FEAT-013 / FEAT-009** — "author can edit the produced block manually" is FEAT-009 block
  editing. **Accepted overlap**; composition's responsibility ends at producing a block. Stated in
  one line in FEAT-013, not respecced. (C16)
- **FEAT-012 / FEAT-008** — sketches (forward outline) and state notes (backward fact) both feed
  generation. Distinct and complementary: neither replaces the other. **Accepted overlap.** Note
  sketches now serve double duty — coordination (their original purpose) and forward context.

## Conflicts

- **C17, resolved by amendment.** UC-036/US-038 specify closing a chapter with no continuity
  precondition; FEAT-012 requires approval to close. Resolved by amending both in place — ids
  unchanged, text gains the gate — on the user's reasoning that closing *means* continuity is
  complete. **This is the first time this spec has amended a delivered id**, so the reviewer should
  weigh it: the amendment must add the precondition and change nothing else.
- **No unresolved conflicts.**

## Known hole, recorded not solved

**The staleness cascade (C12).** State is a live set built from per-chapter changesets, so the
state at chapter N depends on the changesets of 1..N-1. Editing a reopened chapter can invalidate
every later changeset — the same class of continuity bug the feature exists to prevent. The user
deferred it explicitly to `_TBD:` after it was surfaced. Recording it here so it is not rediscovered
as a defect later: **local flagging ships; the downstream chain is a known open hole.** It should be
closed before FEAT-012 is planned, not before it is specced.

## Structural orphans

Every FEAT ≥1 UC; every UC ≥1 US; every US ≥1 AC. None in the plan. Reviewer re-checks after write.

## Scope-boundary note (round 2)

This round lifted the generation-pipeline deferral — the **third reversal in one session** (C1
domain, C10 generation, plus the chapter-substrate widening in round 1). Each was deliberate and
recorded, but the pattern is worth stating plainly: `vision.md`'s non-goals have moved three times.
The remaining deferrals — character/place entity model, prompt design, context assembly, token
budgets — should be treated as genuinely open questions rather than settled boundaries.

---

# Round 3 — variants, cloning & consistency   (2026-07-20)

Coherence pass over FEAT-014..016 against the delivered set (FEAT-001..013).

## Coverage

No new actors. ACT-004 (Book owner) gains all three; ACT-005 (Co-author) gains cloning (public
books only) and flag-raising; ACT-001 (Administrator) gains nothing — correct, and see C22 below.
ACT-006 (Reader) gains nothing: readers cannot clone, which was put to the user and declined.

## Goal closure

**Correct a mistake safely:** reopen (UC-037) → edit, creating a variant (UC-058) → close, running
the consistency check (UC-065) → re-fix or apply flags (UC-066) → closed. **Closed loop, and it is
the loop that closes C12.**

**Explore an alternative storyline:** clone the book (UC-061/062) → rewrite freely in an
independent book. Closed.

**Recover an earlier version:** view variants (UC-059) → select the active one (UC-060) → treated
as a fix, so the same check runs (US-065). Closed.

## Dependency edges (new)

```
FEAT-009 ──→ FEAT-014 ──→ FEAT-016 ←── FEAT-012
FEAT-006 ──→ FEAT-015
FEAT-007 ──→ FEAT-015   (private books: owner-only cloning)
```

- FEAT-014 → FEAT-009 — variants arise from reopening and editing a chapter.
- FEAT-016 → FEAT-014 — the check runs when a fixed chapter closes.
- FEAT-016 → FEAT-012 — the check inspects state notes and summaries; it is what replaces C12's
  deferred cascade.
- FEAT-015 → FEAT-006 — a clone is a new book.
- FEAT-015 → FEAT-007 — cloning rights depend on visibility (C21).

**No cycles.** Build order still unprescribed — delegated to `/roadmap`.

## Overlaps

- **FEAT-014 / FEAT-009** — reopening is FEAT-009; what reopening *produces* is FEAT-014. Accepted
  overlap; FEAT-009's UC-037/US-039 gain a cross-reference and nothing more.
- **FEAT-016 / FEAT-012** — FEAT-012 produces continuity data; FEAT-016 checks it. Accepted
  overlap: neither respecs the other.
- **FEAT-015 / FEAT-006** — a clone is a book, so FEAT-006's lifecycle applies to it in full.

## Conflicts

- **C21, resolved by restriction.** Cloning defeated privacy: a co-author could clone a private
  book and publish the clone. Resolved — **only the owner may clone a private book.** FEAT-015 and
  FEAT-007 must both carry it or the hole reopens.
- **C22, resolved by accepting and stating the limitation.** Cloning defeats moderation: an admin
  destroys a book, a co-author's independent clone still carries the content. The user chose
  **admins moderate each book separately**. This is a real, permanent limitation of FEAT-011 —
  whose stated purpose is getting illegal content off the instance — and FEAT-011 must **say so
  plainly**. A limitation that is written down is a decision; one that isn't is a defect waiting to
  be found.
- **No unresolved conflicts.**

## Closed hole

**C12 (staleness cascade) is CLOSED** after being deferred twice. FEAT-016's consistency check is
the mechanism: the LLM inspects following chapters against changed text, surfaces inconsistencies
to the owner, and anything suspect is flagged rather than silently rewritten. FEAT-012's `_TBD:`
must be **replaced with a cross-reference to FEAT-016**, not left standing — a stale deferral that
has actually been answered is worse than one that hasn't, because it invites someone to re-solve it.

## Structural orphans

Every FEAT ≥1 UC; every UC ≥1 US; every US ≥1 AC. None in the plan.

## Layout note

`features.md` reached 393 of ~400 lines and never splits by rule. The user chose to make
`quick-reference.md` the **sole canonical registry**, leaving `features.md` as feature blocks only.
This is a **contract change**: `docs/product/CLAUDE.md` currently names `features.md` canonical and
must be amended in the same pass, or the doc set contradicts its own contract.

## Recorded rejection

The **branch-tree model** was designed, reduced to two axes, and then dropped by the user in favour
of chapter variants + cloning. Recorded in the interview rather than discarded: a future round
proposing branching should read C18/C19 first and know it was considered and rejected on
interface-complexity grounds, not overlooked.

---

# Coherence — round 4 (codex), 2026-07-20

## Coverage
No new actors. FEAT-017 belongs to ACT-004 + ACT-005; FEAT-018 likewise. ACT-006 Reader is
explicitly EXCLUDED from both — an exclusion, not an orphan. No orphan features, no orphan actors.

## Dependency edges (new)
- FEAT-017 requires FEAT-006 (a book exists) + FEAT-007 (membership + collaboration mode)
- FEAT-012 requires FEAT-017   <-- NEW, and it inverts round 2's assumption
- FEAT-018 requires FEAT-013 + FEAT-017

Full chain: 006 -> 007 -> 017 -> 012 -> 013 -> 018.  **Acyclic** (verified: 018 depends on 017,
017 never depends on 018).

## Finding R4-1 — build-order inversion (surfaced to user, accepted)
FEAT-012 was specced in round 2 as self-contained. It now requires FEAT-017. If state notes are
built first they ship as free text and must be retro-attached to codex entries later. Not a spec
defect — an ordering constraint /roadmap must honour. Recorded here because the round-2 edge list
would otherwise still read as current.

## Finding R4-2 — conflict chased and CLEARED
Codex is members-only, yet UC-062 permits cloning a *public* book. Would a cloner receive a codex
they were never entitled to read? **No.** UC-062's actor is ACT-005 (a member); ACT-006 Reader has
no clone use case at all. Cloners are always members. Recorded as checked, not as open risk.

## Overlap check vs. existing features
- FEAT-017 vs FEAT-012 — resolved by C25; the one-line difference (identity vs. change) is stated
  in both feature blocks, not just one.
- FEAT-018 vs FEAT-013 — FEAT-013 produces *blocks*, FEAT-018 produces *codex entries*, from the
  same chat surface. Distinct outputs; accepted overlap of surface, stated in both blocks.
- FEAT-017 vs FEAT-015 — cloning carries the codex; no duplicate ownership of the rule (FEAT-015
  owns what a clone carries, FEAT-017 owns what an entry is).

## Vision alignment
No vision amendment required. The codex sits inside the book-domain scope already lifted in round 1;
it is not the generation pipeline, which remains the standing non-goal.

## Structural check
FEAT-017: 7 UC / 8 US. FEAT-018: 2 UC / 3 US. Amendment UCs: 3 (UC-078/079/080) landing in
FEAT-013 / FEAT-012 / FEAT-016 respectively. Every US carries at least one Given/When/Then AC.
No FEAT without UC, no UC without US, no US without AC.
