<!-- product-spec:start -->
# Relationships

Feature relationships for `docs/product/`: actor×feature matrix,
depends-on edges, build order, accepted overlaps, conflicts. Extracted
from `features.md` in the 2026-07-23 augment round 5 to buy that file
permanent line-budget headroom (`features.md` never splits). Id registry:
`quick-reference.md` (sole canonical registry). This file never splits.

| Actor | Features |
|---|---|
| ACT-001 | FEAT-002, FEAT-003, FEAT-004, FEAT-005, FEAT-006, FEAT-011 |
| ACT-002 | FEAT-002, FEAT-006 |
| ACT-003 | FEAT-001 |
| ACT-004 | FEAT-006, FEAT-007, FEAT-008, FEAT-009, FEAT-010, FEAT-011, FEAT-012, FEAT-013, FEAT-014, FEAT-015, FEAT-016, FEAT-017, FEAT-018 |
| ACT-005 | FEAT-007, FEAT-008, FEAT-009, FEAT-010, FEAT-012, FEAT-013, FEAT-014, FEAT-015, FEAT-016, FEAT-017, FEAT-018 |
| ACT-006 | FEAT-007 |

**Depends on:**
- FEAT-006 → FEAT-003 — a book needs an account to own it; disable-not-delete
  is what makes UC-025 necessary. Cross-layer edge.
- FEAT-007 → FEAT-006 — membership needs a book.
- FEAT-008 → FEAT-007 — any member adding a chapter needs membership defined.
- FEAT-009 → FEAT-008 — writing needs a chapter to open.
- FEAT-010 → FEAT-009 — proposals are proposed blocks; the block must exist
  as a concept first.
- FEAT-011 → FEAT-006 — moderation acts at book granularity only; no
  dependency on chapters, blocks or membership.
- FEAT-012 → FEAT-009 — continuity is produced on chapter close.
- FEAT-013 → FEAT-012 — the context guarantee needs summaries and state
  notes to exist.
- FEAT-013 → FEAT-010 — a produced block becomes a proposal in proposal
  mode.
- FEAT-013 → FEAT-009 — a produced block is a block; editing it is
  FEAT-009.
- FEAT-013 → FEAT-008 — the always-pushed chapter-mode baseline includes
  all upcoming-chapter sketches. **New edge, round 5.**
- FEAT-013 → FEAT-004 — composition needs an enabled model.
- FEAT-014 → FEAT-009 — variants arise from reopening and editing a
  chapter.
- FEAT-016 → FEAT-014 — the check runs when a fixed chapter closes.
- FEAT-016 → FEAT-012 — the check inspects state notes and summaries; it
  is what replaces C12's deferred cascade.
- FEAT-016 → FEAT-004 — the check needs an enabled LLM server.
- FEAT-015 → FEAT-006 — a clone is a new book.
- FEAT-015 → FEAT-007 — cloning rights depend on visibility (C21).
- FEAT-017 → FEAT-006 — a codex belongs to a book.
- FEAT-017 → FEAT-007 — codex access follows membership; the codex is
  members-only.
- FEAT-012 → FEAT-017 — a state note can name a codex entry. **Finding
  R4-1 (build-order inversion):** FEAT-012 was specced in round 2 as
  self-contained; this edge is new as of round 4 — the round-2 edge list
  no longer describes it alone.
- FEAT-018 → FEAT-013 — same shared-canvas assistant surface.
- FEAT-018 → FEAT-017 — generates and rewrites codex entries.
- FEAT-012 → FEAT-016 — **new display edge, round 6:** Book state
  (UC-091) displays a chapter's active warnings in context; distinct from
  the existing FEAT-016 → FEAT-012 check edge above (display, not
  inspection).
- FEAT-012 → book-object — **new, round 6, `_TBD:` deferred:** Book state
  surfaces the book's own fields; the book object itself is not yet
  designed — routed to `/architect`.

**Hosting (round 6, not a dependency edge):** the FEAT-013 navigator
(UC-090) hosts FEAT-017 (codex), FEAT-008/FEAT-009 (chapters) and
FEAT-012 (Book state) surfaces in the content pane — a UI hosting
relationship, recorded as a note only, not a build-order dependency.

Build order: FEAT-006 → FEAT-007 → FEAT-008 → FEAT-009 → FEAT-011 → FEAT-010
(FEAT-010 last per challenge C6; FEAT-011 may move earlier). No cycles.
FEAT-012..018 build order is deliberately not prescribed — delegated to
`/roadmap`; only the dependency edges above are recorded. Suggested order
for round 4 (not prescriptive, same delegation): FEAT-006 → FEAT-007 →
FEAT-017 → FEAT-012 → FEAT-013 → FEAT-018. FEAT-013's round-5 expansion
(the AI authoring assistant) does not reorder this graph.

**Overlaps (accepted):**
- FEAT-009 / FEAT-010 — same block unit, different gate: free mode applies a
  block on save, proposal mode holds it until the owner applies it.
- FEAT-006 / FEAT-011 — archive (owner, reversible) vs quarantine/destroy
  (admin, moderation, terminal) — different actor, different reversibility.
- FEAT-013 / FEAT-009, FEAT-013 / FEAT-017 — shared content-pane editing
  surface: manual edit is FEAT-009 (blocks) / FEAT-017 (codex entries),
  assistant-assisted editing of the same artifacts is FEAT-013. **Revised,
  round 5** — previously "composition ends at producing a block; editing
  it is FEAT-009", dissolved by the shared-canvas model (no more "produce"
  hand-off).
- FEAT-012 / FEAT-008 — sketches (forward outline) and state notes
  (backward fact) both feed generation; neither replaces the other.
- FEAT-014 / FEAT-009 — reopening is FEAT-009; what reopening produces is
  FEAT-014.
- FEAT-016 / FEAT-012 — FEAT-012 produces continuity data; FEAT-016
  checks it.
- FEAT-013 / FEAT-016 — **accepted, round 5:** an ad-hoc, in-chat scoped
  check (FEAT-013 UC-088) vs. FEAT-016's mandatory, structured
  consistency check — conversational cousin, not a substitute; flag-bridge
  deferred (`_TBD:` on FEAT-016).
- FEAT-015 / FEAT-006 — a clone is a book; FEAT-006's lifecycle applies to
  it in full.
- FEAT-017 / FEAT-012 — identity vs. change: a codex entry is the stable
  thing; a state note is what a chapter changed.
- FEAT-018 / FEAT-013 — same shared-canvas surface, different output:
  FEAT-013 writes blocks, FEAT-018 generates/rewrites codex entries.
- FEAT-012 (Book state) / FEAT-008, FEAT-009 (Chapters) — **accepted,
  round 6:** both list/show chapters, but distinct purpose — Chapters is
  read/write prose, Book state is the continuity picture; not a duplicate
  surface. The dropped flat Warnings page (round 6) is superseded by
  Book state's per-chapter warnings-in-context.
- FEAT-012 (Book state) aggregates UC-049, UC-050, UC-089 — **round 6:**
  cross-reference within the same feature's existing continuity data, not
  duplicated capability.

**Conflicts:** None unresolved. Resolved: C17 — UC-036/US-038 amended in
place to gate closing on approved continuity data (FEAT-012). C21 — only
the owner may clone a private book (FEAT-015, FEAT-007). C22 — moderation
does not reach clones, stated as a limitation (FEAT-011). R4-2 —
members-only codex vs. cloning a public book: no conflict; UC-062's actor
is ACT-005, a member; ACT-006 has no clone use case.
<!-- product-spec:end -->
