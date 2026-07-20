<!-- product-spec:start -->
# Features

Spine of `docs/product/`: one block per `FEAT-###`, plus feature
relationships. Never splits. The id registry lives in
`quick-reference.md` — the sole canonical registry.

## Feature blocks

### FEAT-001 — First-run bootstrap
- **Purpose:** Bring an unconfigured instance to a usable state: create a new
  database with a first admin, or import an existing database export.
- **Actors:** ACT-003 · **Priority:** must
- **Status:** proposed
- **Realized by:** UC-001, UC-002, US-001, US-002
- **Source:** `[confirmed: user]` interview 2026-07-20, "FEAT-001 first-run
  bootstrap"

### FEAT-002 — Authentication & session
- **Purpose:** Let a created user log in, hold a session, and log out; expired
  or invalidated sessions require re-authentication.
- **Actors:** ACT-001, ACT-002 · **Priority:** must
- **Status:** proposed
- **Realized by:** UC-003, UC-004, US-003, US-004
- **Source:** `[inferred]` interview 2026-07-20, "FEAT-002 authentication &
  session" — carried from reference project, not explicitly confirmed by the
  user; to be confirmed at review.

### FEAT-003 — User management
- **Purpose:** Admin-gated account lifecycle: list, create, reset password,
  change role, disable. No hard delete.
- **Actors:** ACT-001 · **Priority:** must
- **Status:** proposed
- **Realized by:** UC-005, UC-006, UC-007, UC-008, UC-009, US-005, US-006,
  US-007, US-008, US-009
- **Source:** `[confirmed: user]` interview 2026-07-20, "FEAT-003 user
  management — roles & lifecycle"

### FEAT-004 — LLM server connections
- **Purpose:** Register, test, and manage LLM server connections; enable
  specific models; designate one embedding server + model.
- **Actors:** ACT-001 · **Priority:** must
- **Status:** proposed
- **Realized by:** UC-010, UC-011, UC-012, UC-013, UC-014, US-010, US-011,
  US-012, US-013, US-014, US-021
- **Source:** `[confirmed: user]` interview 2026-07-20, "features"

### FEAT-005 — Database consistency & management
- **Purpose:** Report per-table schema drift and let an admin remediate it
  (create missing tables, sync schema, export/import the database, rebuild
  the vector index).
- **Actors:** ACT-001 · **Priority:** must
- **Status:** proposed
- **Realized by:** UC-015, UC-016, UC-017, UC-018, UC-019, UC-020, US-015,
  US-016, US-017, US-018, US-019, US-020
- **Source:** `[confirmed: user]` interview 2026-07-20, "FEAT-005 DB
  check-consistency page"

### FEAT-006 — Book lifecycle & ownership
- **Purpose:** Create, list, archive and transfer a book; admin reassigns
  ownership when the owner's account is disabled.
- **Actors:** ACT-002, ACT-004, ACT-001 · **Priority:** must
- **Status:** proposed
- **Realized by:** UC-021, UC-022, UC-023, UC-024, UC-025, US-022, US-023,
  US-024, US-025, US-026
- **Note:** Archive is the owner's reversible action; a book is never
  destroyed here. The single sanctioned exception is FEAT-011's admin
  quarantine-then-destroy — archive (owner, reversible) and
  quarantine/destroy (admin, moderation) differ in actor and reversibility.
- **Source:** `[confirmed: user]` interview 2026-07-20, "ownership,
  membership & visibility"

### FEAT-007 — Membership & visibility
- **Purpose:** Owner manages co-author membership and book visibility;
  readers get read-only access to public books.
- **Actors:** ACT-004, ACT-005, ACT-006 · **Priority:** must
- **Status:** proposed
- **Realized by:** UC-026, UC-027, UC-028, UC-029, UC-030, US-027, US-028,
  US-029, US-030, US-031
- **Note:** Private = owner + co-authors only; public = read-only to any
  logged-in user, never anonymous. `_TBD: whether public books are
  discoverable (browsable) or reachable only by direct link._` Codex
  entries (FEAT-017) are members-only — ACT-006 never sees them, even on
  a public book.
- **Source:** `[confirmed: user]` interview 2026-07-20, "ownership,
  membership & visibility"; challenge C4; codex round 4

### FEAT-008 — Chapter skeleton & sketches
- **Purpose:** Build a book's ordered chapter skeleton with sketches ahead
  of writing.
- **Actors:** ACT-004, ACT-005 · **Priority:** must
- **Status:** proposed
- **Realized by:** UC-031, UC-032, UC-033, UC-034, US-032, US-033, US-034,
  US-035
- **Note:** Any member adds a chapter and edits any planned chapter's
  sketch, in parallel; only the owner sets chapter order. This is the
  parallel-work surface that makes FEAT-009's single-open-chapter rule
  workable.
- **Source:** `[confirmed: user]` interview 2026-07-20, "book structure —
  chapters, states, sketches"; challenge C3

### FEAT-009 — Chapter writing in blocks
- **Purpose:** Write the open chapter in blocks; enforce the
  planned→open→closed chapter state machine and per-block concurrency
  rules.
- **Actors:** ACT-004, ACT-005 · **Priority:** must
- **Status:** proposed
- **Realized by:** UC-035, UC-036, UC-037, UC-038, UC-039, US-036, US-037,
  US-038, US-039, US-040, US-041
- **Note:** At most one open chapter per book; only the owner opens, closes
  and reopens. Free mode applies a block on save; proposal mode (FEAT-010)
  holds it until the owner applies it — same block unit, different gate.
  `_TBD: what a block contains (format, length, structure)._`
- **Source:** `[confirmed: user]` interview 2026-07-20, "writing — blocks &
  concurrency"; challenge C8

### FEAT-010 — Proposal mode
- **Purpose:** Let a co-author submit proposed blocks for the open chapter
  instead of applying them directly; the owner reviews and applies
  selectively.
- **Actors:** ACT-004, ACT-005 · **Priority:** should
- **Status:** proposed
- **Realized by:** UC-040, UC-041, UC-042, US-042, US-043, US-044
- **Note:** Book-level property set by the owner at creation, changeable at
  any time. Free mode applies a block on save; proposal mode holds it until
  the owner applies it. Approval is a merge, not a binary accept — the
  owner may take blocks from several co-authors' proposals. Builds last in
  the roadmap build order (challenge C6); every book runs in free mode
  until it exists — nothing dropped. `_TBD: fate of pending proposals when
  the owner switches a book to free mode._`
- **Source:** `[confirmed: user]` interview 2026-07-20, "collaboration mode"

### FEAT-011 — Content moderation
- **Purpose:** Admin-only moderation read view; quarantine, then
  separately destroy, a book at whole-book granularity; the owner is
  notified with a reason.
- **Actors:** ACT-001, ACT-004 · **Priority:** must
- **Status:** proposed
- **Realized by:** UC-043, UC-044, UC-045, UC-046, US-045, US-046, US-047,
  US-048, US-093
- **Note:** Admin never participates in a book in the main authoring
  interface, in any mode, regardless of visibility. Destroy here is the
  single sanctioned exception to FEAT-006's archive-only, never-destroyed
  rule — scoped to admin moderation only. **Limitation, stated plainly:**
  moderation does not reach clones — a co-author's independent clone of a
  book (FEAT-015), made before or after that book is quarantined or
  destroyed, is unaffected; an admin moderates each book, including each
  clone, separately (challenge C22). `_TBD: whether a quarantined
  book can be released back to its members._` The moderation view reaches
  the book's codex (FEAT-017) too.
- **Source:** `[confirmed: user]` interview 2026-07-20, "admin access &
  moderation"; challenge C9, C22; codex round 4

### FEAT-012 — Chapter summaries & state notes
- **Purpose:** Draft and store per-chapter summaries and a live set of
  state notes so later chapters and generation see prior continuity
  without full chapter text.
- **Actors:** ACT-004, ACT-005 · **Priority:** must
- **Status:** proposed
- **Realized by:** UC-047, UC-048, UC-049, UC-050, UC-051, UC-052, UC-079,
  US-049, US-050, US-051, US-052, US-053, US-054, US-055, US-090
- **Note:** Two distinct artifacts: summary (narrative, backward-looking)
  and state notes (free text, facts that must stay true — no entity
  model). One live set of state notes; each chapter records its own
  added/modified/deleted changeset. Drafted by the system on chapter
  close, approved by the owner — approval is required to close (amends
  UC-036/US-038, FEAT-009, challenge C17). Editing follows the book's
  collaboration mode (FEAT-010): in free mode a member's state-note edits
  apply immediately, and the owner still reviews the chapter's state-note
  changeset at the close gate (UC-048) — a co-author's change can be
  revised by the owner before the chapter closes. Reopening flags
  continuity stale. The staleness cascade through later chapters'
  changesets (challenge C12) is closed by FEAT-016's consistency check —
  see FEAT-016. `_TBD: whether an open chapter contributes state notes
  before it closes._` A state note may name the codex entry (FEAT-017) it
  is about — identity (codex) vs. change (state note).
- **Source:** `[confirmed: user]` interview 2026-07-20, "Augment round 2 —
  continuity & block composition", "summaries & state notes"; codex round 4

### FEAT-013 — Block composition chat
- **Purpose:** Let an author compose the next block by chatting with the
  LLM, iterating freely, until the chat produces a block.
- **Actors:** ACT-004, ACT-005 · **Priority:** must
- **Status:** proposed
- **Realized by:** UC-053, UC-054, UC-055, UC-056, UC-057, UC-078, US-056,
  US-057, US-058, US-059, US-060, US-061, US-089
- **Note:** Chats are started and ended freely, not bound to one block or
  chapter. A composition chat has all four continuity artifacts available
  (prior-chapter summaries, current state notes, the open chapter's full
  text, upcoming sketches) — an observable guarantee, replacing the
  unfalsifiable "don't pollute the context" (challenge C11); how context
  is assembled, ordered, truncated or budgeted is architecture's, not
  specified here. A produced block follows the book's collaboration mode
  — lands directly in free mode, becomes a proposal in proposal mode
  (FEAT-010). Editing a produced block is FEAT-009, not this feature —
  accepted overlap (challenge C16). Chats are private to their author;
  only the produced block is shared, even with the owner. `_TBD: which
  enabled model a chat uses (may resolve as architecture's)._` A
  composition chat can also draw on the book's codex (FEAT-017) for
  context; generating or rewriting entries from the same chat is FEAT-018
  — accepted overlap: same surface, different output.
- **Source:** `[confirmed: user]` interview 2026-07-20, "Augment round 2 —
  continuity & block composition", "block composition chat" / "generation
  context"; codex round 4

### FEAT-014 — Chapter variants & fixes
- **Purpose:** Let an owner correct a chapter after reopening while
  keeping every previous version readable and recoverable.
- **Actors:** ACT-004, ACT-005 · **Priority:** must
- **Status:** proposed
- **Realized by:** UC-058, UC-059, UC-060, US-062, US-063, US-064, US-065
- **Note:** Editing a reopened chapter is a fix: the chapter keeps all its
  variants, shown to authors; following chapters stay unchanged. The
  owner selects one active variant — the chapter for reading, generation
  context and export; others are readable history. Switching the active
  variant is treated exactly as a fix — same consistency-check path
  (FEAT-016), since the chapter's text changed. Previous text stays
  recoverable; the storage form is `/architect`'s (challenge C20).
  `_TBD: whether an edit identical to the original text still creates a
  new variant or is a no-op — not stated._` `_TBD: whether switching the
  active variant is refused while the chapter is open elsewhere or
  applies once closed — not stated._`
- **Source:** `[confirmed: user]` interview 2026-07-20, "Augment round 3 —
  variants, cloning & consistency", "chapter variants & fixes"

### FEAT-015 — Book cloning
- **Purpose:** Let an owner or co-author create a fully independent copy
  of a book to explore an alternative storyline.
- **Actors:** ACT-004, ACT-005 · **Priority:** must
- **Status:** proposed
- **Realized by:** UC-061, UC-062, UC-063, US-066, US-067, US-068,
  US-069, US-070, US-071, US-094
- **Note:** A clone is fully independent — no link, no sync, no
  comparison with its source. It carries chapters, blocks and sketches,
  state notes and summaries, the codex (FEAT-017), membership (selectable
  — the cloner chooses which members carry over, or none), collaboration
  mode and visibility. Owner and co-authors may clone; a co-author's
  clone makes them its owner (challenge C23, accepted deliberately). Only
  the owner may clone a private book (challenge C21) — co-authors clone
  public books only; FEAT-007 states the same rule. **Limitation,
  accepted:** two clones drift apart permanently; a fix common to both
  must be made in each separately. `_TBD: whether cloning a book with an
  open chapter, unapproved continuity data, or an archived book is
  refused or proceeds — not stated._`
- **Source:** `[confirmed: user]` interview 2026-07-20, "Augment round 3 —
  variants, cloning & consistency", "book cloning"; challenges C21, C23;
  codex round 4

### FEAT-016 — Consistency check & chapter flags
- **Purpose:** LLM inspection of a book's chapters, summaries and state
  notes for contradictions; surfaces findings as flags rather than
  rewriting anything.
- **Actors:** ACT-004, ACT-005 · **Priority:** must
- **Status:** proposed
- **Realized by:** UC-064, UC-065, UC-066, UC-067, UC-068, UC-080, US-072,
  US-073, US-074, US-075, US-076, US-077, US-091, US-092
- **Note:** Runs on demand and as part of closing a fixed chapter
  (FEAT-014); a clean result needs no action, anything suspect becomes a
  flag. This closes FEAT-012's deferred staleness-cascade question
  (challenge C12) — the check inspects later chapters against changed
  text rather than tracking the cascade through changesets directly.
  Flags are a general chapter annotation, not consistency-only: members
  can raise their own with a comment, and each flag records its origin
  (check or person) since the two carry different weight. Requires an
  enabled LLM server (FEAT-004). `_TBD: behaviour when the check fails or
  is unavailable — not stated._` `_TBD: whether
  resolving a flag that a later check raises again reopens it, raises a
  new one, or something else — not stated._` `_TBD: whether flags on a
  chapter survive an active-variant change (FEAT-014) — not stated._` The
  check also covers the codex (FEAT-017) — it may flag content or a state
  note that names an entity with no codex entry behind it, or one that's
  archived. **Warns, never blocks** — codex coverage is explicitly
  optional.
- **Source:** `[confirmed: user]` interview 2026-07-20, "Augment round 3 —
  variants, cloning & consistency", "consistency check & chapter flags";
  challenge C12; codex round 4

### FEAT-017 — Codex
- **Purpose:** The book's reference volume — entries for characters,
  locations and lore facts, with authoring, archival, history and copying
  across books.
- **Actors:** ACT-004, ACT-005 · **Priority:** must
- **Status:** proposed
- **Realized by:** UC-069, UC-070, UC-071, UC-072, UC-073, UC-074, UC-075,
  US-078, US-079, US-080, US-081, US-082, US-083, US-084, US-085
- **Note:** Three kinds: character, location, fact. Character and location
  are **named** — a name buys state-note reference (FEAT-012) and
  name-addressing; a fact has neither. Follows the book's collaboration
  mode (FEAT-010), the same rule as state notes (US-053). Members-only —
  ACT-006 never sees it, even on a public book (FEAT-007). Archived,
  never deleted — consistent with books (UC-023) and users (FEAT-003).
  One codex per book; chapter variants (FEAT-014) share it. **Coverage is
  optional** — "not all the characters must be in the codex, but better
  to be" — the consistency check (FEAT-016) warns about a missing entry,
  never blocks.
- **Source:** `[confirmed: user]` interview 2026-07-20, "codex" round 4.

### FEAT-018 — Codex authoring from the composition chat
- **Purpose:** Generate a new codex entry or rewrite an existing one from
  the same composition chat that composes blocks.
- **Actors:** ACT-004, ACT-005 · **Priority:** should
- **Status:** proposed
- **Realized by:** UC-076, UC-077, US-086, US-087, US-088
- **Note:** Both generate and rewrite are shown in the chat first, saved
  only on explicit request — mirrors UC-055, not a diff view. Failure
  handling is not respecced: both use cases point at UC-056. Ships after
  FEAT-017.
- **Source:** `[confirmed: user]` interview 2026-07-20, "codex" round 4.

## Relationships

Id registry: `quick-reference.md` (sole canonical registry).

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
- FEAT-018 → FEAT-013 — same composition-chat surface.
- FEAT-018 → FEAT-017 — generates and rewrites codex entries.

Build order: FEAT-006 → FEAT-007 → FEAT-008 → FEAT-009 → FEAT-011 → FEAT-010
(FEAT-010 last per challenge C6; FEAT-011 may move earlier). No cycles.
FEAT-012..016 build order is deliberately not prescribed — delegated to
`/roadmap`; only the dependency edges above are recorded. Suggested order
for round 4 (not prescriptive, same delegation): FEAT-006 → FEAT-007 →
FEAT-017 → FEAT-012 → FEAT-013 → FEAT-018.

**Overlaps (accepted):**
- FEAT-009 / FEAT-010 — same block unit, different gate: free mode applies a
  block on save, proposal mode holds it until the owner applies it.
- FEAT-006 / FEAT-011 — archive (owner, reversible) vs quarantine/destroy
  (admin, moderation, terminal) — different actor, different reversibility.
- FEAT-013 / FEAT-009 — composition ends at producing a block; editing it
  is FEAT-009.
- FEAT-012 / FEAT-008 — sketches (forward outline) and state notes
  (backward fact) both feed generation; neither replaces the other.
- FEAT-014 / FEAT-009 — reopening is FEAT-009; what reopening produces is
  FEAT-014.
- FEAT-016 / FEAT-012 — FEAT-012 produces continuity data; FEAT-016
  checks it.
- FEAT-015 / FEAT-006 — a clone is a book; FEAT-006's lifecycle applies to
  it in full.
- FEAT-017 / FEAT-012 — identity vs. change: a codex entry is the stable
  thing; a state note is what a chapter changed.
- FEAT-018 / FEAT-013 — same chat surface, different output: FEAT-013
  composes blocks, FEAT-018 generates/rewrites codex entries.

**Conflicts:** None unresolved. Resolved: C17 — UC-036/US-038 amended in
place to gate closing on approved continuity data (FEAT-012). C21 — only
the owner may clone a private book (FEAT-015, FEAT-007). C22 — moderation
does not reach clones, stated as a limitation (FEAT-011). R4-2 —
members-only codex vs. cloning a public book: no conflict; UC-062's actor
is ACT-005, a member; ACT-006 has no clone use case.
<!-- product-spec:end -->
