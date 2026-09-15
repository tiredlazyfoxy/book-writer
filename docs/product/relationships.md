<!-- product-spec:start -->
# Relationships

Feature relationships for `docs/product/`: actor×feature matrix,
depends-on edges, build order, accepted overlaps, conflicts. Extracted
from `features.md` in the 2026-07-23 augment round 5 to buy that file
permanent line-budget headroom (`features.md` never splits). Id registry:
`quick-reference.md` (sole canonical registry). This file never splits.

| Actor | Features |
|---|---|
| ACT-001 | FEAT-002, FEAT-003, FEAT-004, FEAT-005, FEAT-006, FEAT-011, FEAT-020 |
| ACT-002 | FEAT-002, FEAT-006 |
| ACT-003 | FEAT-001 |
| ACT-004 | FEAT-006, FEAT-007, FEAT-008, FEAT-009, FEAT-010, FEAT-011, FEAT-012, FEAT-013, FEAT-014, FEAT-015, FEAT-016, FEAT-017, FEAT-018, FEAT-019, FEAT-021 |
| ACT-005 | FEAT-007, FEAT-008, FEAT-009, FEAT-010, FEAT-012, FEAT-013, FEAT-014, FEAT-015, FEAT-016, FEAT-017, FEAT-018, FEAT-019, FEAT-021 |
| ACT-006 | FEAT-007 |

**Depends on:**
- FEAT-006 → FEAT-003 — a book needs an account to own it; disable-not-delete
  is what makes UC-025 necessary. Cross-layer edge.
- FEAT-007 → FEAT-006 — membership needs a book.
- FEAT-008 → FEAT-007 — any member adding a chapter needs membership defined.
- FEAT-009 → FEAT-008 — writing needs a chapter to open.
- FEAT-010 → FEAT-009 — proposals are proposed edits; the edit must exist
  as a concept first.
- FEAT-011 → FEAT-006 — moderation acts at book granularity only; no
  dependency on chapters, edits or membership.
- FEAT-012 → FEAT-009 — continuity is produced on chapter close.
- FEAT-013 → FEAT-012 — the context guarantee needs summaries and state
  notes to exist.
- FEAT-013 → FEAT-010 — a produced edit becomes a proposal in proposal
  mode.
- FEAT-013 → FEAT-009 — a produced edit is an edit; editing it is
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
  (UC-091) displays a chapter's active flags in context; distinct from
  the existing FEAT-016 → FEAT-012 check edge above (display, not
  inspection).
- FEAT-012 → book-object — **new, round 6, `_TBD:` deferred:** Book state
  surfaces the book's own fields; the book object itself is not yet
  designed — routed to `/architect`.
- FEAT-019 → FEAT-006 — **new, round 7:** a book must exist to carry each
  member's book-scoped system prompt (**finalization, 2026-07-30:**
  per-author, not book-wide).
- FEAT-019 → FEAT-008 — **new, round 7:** a chapter must exist to carry a
  chapter system prompt.
- FEAT-020 → FEAT-013 — **new, round 8:** configures the assistant it
  depends on.
- FEAT-020 → FEAT-004 — **new, round 8:** same admin-config class as LLM
  servers — sibling admin configuration.
- FEAT-020 → FEAT-017 — **new, round 8:** mode taxonomy — edit-character
  / edit-location / edit-fact mirror the codex kinds.
- FEAT-020 → FEAT-012 — **new, round 8:** mode taxonomy — close-chapter
  mode aligns with the clean close run (reworded 2026-07-31 — "the
  continuity gate" was stale approval-era phrasing; no behavioural
  change).
- FEAT-012 → FEAT-020 — **new, finalization 2026-07-31:** a real runtime
  dependency, distinct from the taxonomy-alignment edge above — the close
  procedure's tools are FEAT-020's to grant. **Reworded 2026-08-10:** they
  are now granted by default rather than awaiting an administrator, so the
  **build-order consequence is discharged** — FEAT-020 has landed and
  nothing blocks FEAT-012's and FEAT-016's assistant-driven use cases from
  being exercised. The dependency itself stands: those use cases still run
  only on what FEAT-020 configures, and an administrator who removes the
  tools removes the capability.
- FEAT-012 → FEAT-010 — **new, finalization 2026-07-31:** a co-author's
  proposal-mode state-note edit needs FEAT-010's proposal-holding
  mechanism; plan 016 refuses it because that mechanism does not
  exist. Mirrors the existing FEAT-013 → FEAT-010 edge.
- FEAT-021 → FEAT-006 — **new, memos round:** a book must exist to scope
  memos. Mirrors the existing FEAT-019 → FEAT-006 edge.
- FEAT-021 → FEAT-007 — **new, memos round:** memos follow membership —
  only a member of a book has memos in it. Mirrors FEAT-017 → FEAT-007.
- FEAT-021 → FEAT-013 — **new, memos round:** memos reach the
  assistant's context, and the memos list is a navigator entry on the
  working page.
- FEAT-021 → FEAT-020 — **new, memos round:** runtime edge, the
  FEAT-012 → FEAT-020 pattern — the create-memo tool is registered in
  FEAT-020's tool registry and granted per mode; without a grant the
  tool is unreachable.
- FEAT-015 → FEAT-021 — **new, memos round:** a clone carries the
  cloner's own memos. Edge runs clone-ward, unlike FEAT-019, whose
  prompts do NOT carry over.

**No new edge FEAT-011 → FEAT-021.** FEAT-011 acts at book granularity
only; memos die with a destroyed book by that existing rule, not by a
memo-specific dependency — consistent with FEAT-011's own note.

**Hosting (round 6, not a dependency edge):** the FEAT-013 navigator
(UC-090) hosts FEAT-017 (codex), FEAT-008/FEAT-009 (chapters) and
FEAT-012 (Book state) surfaces in the content pane — a UI hosting
relationship, recorded as a note only, not a build-order dependency.
**Extended 2026-08-10:** the navigator also hosts the author's own
**chats list** — every navigator entry now renders its list in the
content pane, and only a picked chat lands in the chat pane (UC-081,
UC-090). Still a hosting relationship, not a dependency edge.

**Note (round 7, not a dependency edge):** FEAT-013 *consumes* FEAT-019's
system prompts when present but does not require them — an empty prompt
is valid — so this is recorded as a note only, not an edge, and does not
distort build order.

Build order: FEAT-006 → FEAT-007 → FEAT-008 → FEAT-009 → FEAT-011 → FEAT-010
(FEAT-010 last per challenge C6; FEAT-011 may move earlier). No cycles.
FEAT-012..018 build order is deliberately not prescribed — delegated to
`/roadmap`; only the dependency edges above are recorded. Suggested order
for round 4 (not prescriptive, same delegation): FEAT-006 → FEAT-007 →
FEAT-017 → FEAT-012 → FEAT-013 → FEAT-018. FEAT-013's round-5 expansion
(the AI authoring assistant) does not reorder this graph.

**Overlaps (accepted):**
- FEAT-009 / FEAT-010 — same edit unit, different gate: free mode applies an
  edit on save, proposal mode holds it until the owner applies it.
- FEAT-006 / FEAT-011 — archive (owner, reversible) vs quarantine/destroy
  (admin, moderation, terminal) — different actor, different reversibility.
- FEAT-013 / FEAT-009, FEAT-013 / FEAT-017 — shared content-pane editing
  surface: manual edit is FEAT-009 (chapter edits) / FEAT-017 (codex
  entries), assistant-assisted editing of the same artifacts is FEAT-013.
  **Revised,
  round 5** — previously "composition ends at producing a block; editing
  it is FEAT-009", dissolved by the shared-canvas model (no more "produce"
  hand-off).
- FEAT-012 / FEAT-008 — sketches (forward outline) and state notes
  (backward fact) both feed generation; neither replaces the other.
- FEAT-014 / FEAT-009 — reopening is FEAT-009; what reopening produces is
  FEAT-014.
- FEAT-016 / FEAT-012 — FEAT-012 produces continuity data; FEAT-016
  checks it. **Finalization, 2026-07-31:** now realized in a single
  mechanism — the `close-chapter` turn both drafts and checks in the same
  run. Implementation fact, not a spec merge; the two features remain
  distinct capabilities and should not be merged.
- FEAT-013 / FEAT-016 — **accepted, round 5:** an ad-hoc, in-chat scoped
  check (FEAT-013 UC-088) vs. FEAT-016's mandatory, structured
  consistency check — conversational cousin, not a substitute; flag-bridge
  deferred (`_TBD:` on FEAT-016).
- FEAT-015 / FEAT-006 — a clone is a book; FEAT-006's lifecycle applies to
  it in full.
- FEAT-017 / FEAT-012 — identity vs. change: a codex entry is the stable
  thing; a state note is what a chapter changed.
- FEAT-018 / FEAT-013 — same shared-canvas surface, different output:
  FEAT-013 writes edits, FEAT-018 generates/rewrites codex entries.
  **2026-09-14:** US-121's immediate-create path (creating a new codex
  entry outright, on direct request) is **not a canvas write at all** —
  that is the difference between FEAT-018's two paths (draft-into-an-
  open-entry vs. immediate create), not a new overlap with FEAT-013.
- FEAT-012 (Book state) / FEAT-008, FEAT-009 (Chapters) — **accepted,
  round 6:** both list/show chapters, but distinct purpose — Chapters is
  read/write prose, Book state is the continuity picture; not a duplicate
  surface. The dropped flat Warnings page (round 6) is superseded by
  Book state's per-chapter flags-in-context.
- FEAT-012 (Book state) aggregates UC-049, UC-050, UC-089 — **round 6:**
  cross-reference within the same feature's existing continuity data, not
  duplicated capability.
- FEAT-019 / FEAT-013 — **round 7:** 019 stores the standing system
  prompt, 013 applies it in a chat. Storage vs. use of one artifact.
- FEAT-019 / FEAT-008 — **round 7:** the chapter system prompt sits
  beside the sketch and is edited by the same people; distinct — the
  sketch is *what happens*, the prompt is *how it should be written*.
  **Finalization, 2026-07-30:** the two now also differ in ownership —
  the sketch is **shared**, any member edits the one sketch; the chapter
  prompt is **per-author**, each member owns and reads only their own.
- FEAT-020 / FEAT-013 — **round 8:** 020 stores the mode/sub-agent
  configuration, 013 applies it at runtime — storage vs. use, the same
  shape as the FEAT-019/FEAT-013 overlap above.
- FEAT-020 / FEAT-019 — **round 8:** orthogonal prompt layers feeding
  the same assistant — 020 is admin-set and system-wide, 019 is
  author-set and per-author (**finalization, 2026-07-30:** corrected
  from "per-book" — every member owns their own book and chapter
  prompts).
- FEAT-006 (my books) / FEAT-007 (shared with me, public books) —
  **finalization 2026-07-31:** three list surfaces on one bookshelf,
  **disjoint by construction** — the public list excludes both books the
  caller owns and books they co-author. Ownership vs. membership vs.
  neither; not a duplicate surface.
- FEAT-006 / FEAT-007 — **finalization 2026-07-31:** archiving hides a
  book from public discovery (UC-100) without revoking read access
  (UC-029) — an archived public book is readable by direct link but
  unlisted. Deliberate, and consistent with UC-023's archive being
  preserved and reversible.
- FEAT-021 / FEAT-019 — **accepted, memos round:** both per-author,
  per-book, private, always applied. Stated difference: a memo records
  **what to remember**, a prompt shapes **how the assistant writes**;
  and the assistant can create a memo, never a prompt.
- FEAT-021 / FEAT-018 — **accepted, memos round:** both "the assistant
  creates an object outright, on direct request, no draft, no save
  step" (US-121 precedent) — different object, same guardrail.

**Conflicts:** None unresolved. Resolved: CP3 (memos round) — the vision
non-goal on context-assembly ordering (`vision.md`) vs. FEAT-021's
author-order guarantee: narrowed, not reversed — product states only that
active memos reach the assistant in the author's set order; where the
memo block sits relative to chapter text, summaries and state notes stays
`/architect`'s. **CP5 (memos round)** — FEAT-020's fixed set of five modes
vs. the memos list joining the working-page navigator: resolved by
resolving the memos list to no mode, alongside the 2026-09-14 non-goal
list; FEAT-020's set of five is unchanged. C17 — UC-036/US-038 amended in
place to gate closing on a clean close run (FEAT-012) (reworded
2026-07-31 — the gate is the shipped clean run, not an approval; the
conflict stays resolved). C21 — only the owner may clone a private book
(FEAT-015, FEAT-007). C22 — moderation does not reach clones, stated as a
limitation (FEAT-011). R4-2 — members-only codex vs. cloning a public
book: no conflict; UC-062's actor is ACT-005, a member; ACT-006 has no
clone use case. **CF1 (round 7, resolved):** product's own round-5
finding — UC-037 reopen silently auto-closed past the FEAT-012 approval
gate. Resolved by refusing the reopen while another chapter is open or
closing: an auto-close either skips a clean close run or strands a
chapter mid-close; refusing keeps both the one-open-chapter singleton and
the requirement that closing goes through a clean close run (FEAT-009).
(Reworded 2026-07-31 — "the continuity gate" was stale phrasing; no
behavioural change, CF1 stays resolved.) **CF2 (finalization 2026-07-31,
resolved):** UC-036's exception flow claimed an unapproved chapter stays
in `closing`; design-note D4 shipped a return to `open` with every draft
artifact discarded instead. Resolved in favour of what shipped — UC-036
and US-038.AC-3 amended (finalization of plan 016, challenge C-f16-3).
**C-r8-3 (round 8, resolved):** FEAT-011's "admin never participates in a
book" vs. FEAT-020's admin configuring the assistant — no conflict:
configuring global assistant behaviour is system config, the same class
as managing LLM servers (FEAT-004), not participating in a specific book.
**CF3 (finalization 2026-07-31, resolved):** UC-023's never-archive-gated
reads vs. the delivered discovery list's exclusion of non-active books —
an archived public book is readable but not discoverable. Resolved as a
**requirement, not a defect**: archiving withdraws a book from the feed
without revoking access; unarchiving restores it with no data change
(challenge C-f22-4).
<!-- product-spec:end -->
