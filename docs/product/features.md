<!-- product-spec:start -->
# Features

Spine of `docs/product/`: one block per `FEAT-###`. Never splits. The id
registry lives in `quick-reference.md` — the sole canonical registry.
Feature relationships (actor×feature, depends-on, overlaps, build order,
conflicts) live in `relationships.md`.

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
  **Round 7:** an archived book is read-only to all members until
  unarchived; archiving a book with an open (or closing) chapter leaves
  that chapter frozen in place rather than force-closing it — unarchiving
  resumes it as the book's one open chapter (force-closing would skip the
  FEAT-012 continuity gate, the incoherence CF1 avoids).
- **Source:** `[confirmed: user]` interview 2026-07-20, "ownership,
  membership & visibility"; interview 2026-07-24, "augment round 7 —
  archive+open-chapter follow-up"

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
  and reopens. **Round 7:** opening or reopening a chapter while another is
  open or closing is **refused** — the owner closes the current chapter
  through the continuity gate first; this **closes CF1**, product's own
  round-5 coherence finding, rather than merely restating it. Four chapter
  states: planned → open → **closing** (close requested, continuity
  awaiting the owner's approval; still holds the book's single open slot;
  refuses writes) → closed. Free mode applies a block on save; proposal
  mode (FEAT-010) holds it until the owner applies it — same block unit,
  different gate. **Round 7:** a block is free text of any length, no
  internal structure, appended to the chapter's body when applied; it is
  not separately addressable once appended — concurrency is per chapter,
  not per block (closes the block-contents `_TBD:`). The working page's
  content pane is the manual chapter-editing surface (FEAT-013 Note);
  edits are draft-until-saved; a read-only (closed) chapter refuses writes.
- **Source:** `[confirmed: user]` interview 2026-07-20, "writing — blocks &
  concurrency"; challenge C8; interview 2026-07-23, "Augment round 5", "the
  working page — two-pane, chat + content"; interview 2026-07-24, "augment
  round 7 — enforcing the architecture pass onto the spec", divergences
  4, 5, 6

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
  the owner switches a book to free mode._` `_TBD: how the owner reviews
  and applies pending state-note (UC-050) and codex (UC-069/070)
  proposals — proposal review lives on the main edit page, detail
  deferred; today only block proposals have a use case (UC-041)._`
- **Source:** `[confirmed: user]` interview 2026-07-20, "collaboration mode";
  interview 2026-07-23, "Augment round 5", "S2 proposal review — DEFERRED"

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
  UC-089, UC-091, US-049, US-050, US-051, US-052, US-053, US-054, US-055,
  US-090, US-104, US-106
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
  is about — identity (codex) vs. change (state note). UC-089/US-104 add a
  read-only view of a chapter's approved summary — a real gap until this
  round: summaries were only drafted (UC-047) and approved (UC-048), never
  viewable. All editing of summaries and state notes happens on the
  working SPA; the settings-side continuity view (UC-051, UC-089) is
  read-only, members-only. **Round 6:** Book state (UC-091) is the
  working-SPA landing view — the first thing shown on opening the book to
  work — aggregating this feature's continuity data (summary UC-089,
  state-note changeset UC-049/UC-051) with FEAT-016's warnings-in-context
  and the book's own fields (`_TBD: field list — deferred to /architect,
  book object; do not invent._`); state notes are edited here too
  (UC-050). Distinct from Chapters (FEAT-008/FEAT-009, read/write prose) —
  Book state is the continuity picture, an accepted overlap, not a
  duplicate surface. **Round 7:** the chapter's summary and state-note
  changes are drafted (UC-047) once the chapter enters FEAT-009's fourth
  state, **closing**; owner approval (UC-048) transitions it closing →
  closed.
- **Source:** `[confirmed: user]` interview 2026-07-20, "Augment round 2 —
  continuity & block composition", "summaries & state notes"; codex round 4;
  interview 2026-07-23, "Augment round 5", "SPA pages" / "RULE (per author
  only = members-only)"; interview 2026-07-23, "Augment round 6", "Book
  state — the landing view"; interview 2026-07-24, "augment round 7",
  divergence 6

### FEAT-013 — AI authoring assistant
- **Purpose:** Let an author write with an AI assistant that works
  alongside whatever they have open — chat and content co-equal — reading
  a mode-dependent context and, on request, writing into the open
  chapter or codex entry.
- **Actors:** ACT-004, ACT-005 · **Priority:** must
- **Status:** proposed
- **Realized by:** UC-053, UC-054, UC-055, UC-056, UC-057, UC-078, UC-081,
  UC-082, UC-083, UC-084, UC-085, UC-086, UC-087, UC-088, UC-090, UC-092,
  US-056, US-057, US-058, US-059, US-060, US-061, US-089, US-095, US-096,
  US-097, US-098, US-099, US-100, US-101, US-102, US-103, US-105, US-107
- **Note:** Chats are persistent and managed per author, per book — listed,
  picked, continued, and archived rather than ended (UC-081/UC-082, not
  destroyed, reversible); a chat is not bound to any one chapter, codex
  entry or content-pane subject — the pairing is spatial, not a data
  binding. Context is a mode-dependent hybrid baseline, always pushed:
  **chapter mode** = the focused chapter + current selection + all
  prior-chapter summaries + the state notes + all upcoming-chapter
  sketches (sharpens the round-2 C11 guarantee, US-057); **codex-entry
  mode** = the entry + selection only. Pulled on request in either mode:
  another chapter's full text (UC-085), the book's material by meaning
  (UC-086), the codex, and the web (UC-087) — web access is new scope
  this round. A scoped, on-demand consistency check (UC-088) returns a
  focused finding without dumping raw chapters into the chat; it is a
  conversational cousin to FEAT-016's mandatory check, not a replacement.
  `_TBD: whether an in-chat check finding can be promoted to a FEAT-016
  flag._` The former "produce a block" hand-off is gone: the assistant
  writes directly into whichever artifact is open in the content pane (a
  block into the open chapter, or a codex entry) as a draft on the shared
  canvas until the author explicitly saves — a read-only (closed) chapter
  refuses the write. Editing the result further is FEAT-009/FEAT-017, not
  this feature — accepted overlap: manual edit is 009/017, assistant-
  assisted is 013, same content-pane surface. Chats stay private to their
  author; only saved output is shared, even with the owner. `_TBD: which
  enabled model a chat uses (may resolve as architecture's)._`
  **Round 9:** resolved for sub-agents (FEAT-020: assigned a specific
  model, or inherit the main chat's) — still open for how the main chat
  itself picks a model. Generating or rewriting codex entries from the
  same assistant is FEAT-018 —
  accepted overlap: same surface, different output. **Round 6:** the
  working page carries a navigator — browse by kind: Characters /
  Locations / Facts / Chapters / Book state / Chats (UC-090); the content
  pane holds lists as well as single items, chats still open in the chat
  pane, not the content pane; unsaved content-pane edits are held in a
  device-local, private restore buffer, per item (UC-092). **Round 7:**
  the navigator gains a **Variants** entry, reconciling the architecture
  pass — Characters / Locations / Facts / Chapters / Variants / Book
  state / Chats — rendering the chapter's variant-and-revision view
  (FEAT-014, UC-059); not a new capability, the surface UC-059 lives on.
  **Round 8:** its assistant modes, per-mode tools and sub-agents are
  configured by FEAT-020, whose five granular modes are what this
  feature's coarser "chapter mode / codex-entry mode" language maps onto.
- **Source:** `[confirmed: user]` interview 2026-07-20, "Augment round 2 —
  continuity & block composition", "block composition chat" / "generation
  context"; codex round 4; interview 2026-07-23, "Augment round 5 —
  book-writer SPA layout & the working page", "the working page — two-pane,
  chat + content" / "context model — hybrid push/pull" / "boundaries
  recorded"; interview 2026-07-23, "Augment round 6", "the working-page
  navigator" / "the restore buffer — unsaved per-item edits"; interview
  2026-07-24, "augment round 7", divergence 2; interview 2026-07-24,
  "FEAT-020 — sub-agent model assignment (augment round 9)"

### FEAT-014 — Chapter variants & fixes
- **Purpose:** Let an owner correct a chapter after reopening while
  keeping every previous version readable and recoverable.
- **Actors:** ACT-004, ACT-005 · **Priority:** must
- **Status:** proposed
- **Realized by:** UC-058, UC-059, UC-060, US-062, US-063, US-064, US-065
- **Note:** Editing a reopened chapter is a fix: the chapter keeps all its
  variants and revisions, shown to authors; following chapters stay
  unchanged. **Round 7 (reconciling the architecture pass):** a
  **variant** is an un-applied proposed alternative; a **revision** is a
  superseded prior body, recoverable. There is no active-variant pointer
  and no switch — the owner **applies** a variant rather than selecting
  one; applying it snapshots the chapter's previous body as a revision
  and makes the variant's result the chapter's text. Applying runs the
  same consistency-check path any other change to the chapter does
  (FEAT-016). A variant composed against a body that has since changed is
  **refused** — the author redoes it by hand; **no merge mechanics at
  MVP.** Previous text stays recoverable; the storage form is
  `/architect`'s (challenge C20). Reached via the working page's
  **Variants** navigator entry (FEAT-013, UC-090). `_TBD: whether an edit
  identical to the original text still creates a new variant or is a
  no-op — not stated._`
- **Source:** `[confirmed: user]` interview 2026-07-20, "Augment round 3 —
  variants, cloning & consistency", "chapter variants & fixes"; interview
  2026-07-24, "augment round 7 — enforcing the architecture pass onto the
  spec", divergences 1, 2

### FEAT-015 — Book cloning
- **Purpose:** Let an owner or co-author create a fully independent copy
  of a book to explore an alternative storyline.
- **Actors:** ACT-004, ACT-005 · **Priority:** must
- **Status:** proposed
- **Realized by:** UC-061, UC-062, UC-063, US-066, US-067, US-068,
  US-069, US-070, US-071, US-094
- **Note:** A clone is fully independent — no link, no sync, no
  comparison with its source. It carries chapters, blocks and sketches,
  state notes and summaries, the codex (FEAT-017), the book's and its
  chapters' system prompts (FEAT-019, round 7), membership (selectable —
  the cloner chooses which members carry over, or none), collaboration
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
  codex round 4; interview 2026-07-24, "augment round 7", divergence 3

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
  optional. An ad-hoc, in-chat scoped check (FEAT-013 UC-088) is a
  conversational cousin to this mandatory check, not a substitute for it.
  `_TBD: whether an in-chat check finding can be promoted to a flag here._`
  All flag management (raise/resolve/run-check) happens on the working
  SPA; the settings-side flags view is read-only, members-only. **Round
  6:** "Warning" is the author-facing term for a flag — used on the
  working-page surfaces, e.g. FEAT-012's Book state shows a chapter's
  active warnings in context. This feature's own wording is reconciled
  later, alongside its already-parked rewrite (the flag-bridge `_TBD:`
  above) — not half-renamed this round. **Round 7:** the check does not
  inspect the book's or a chapter's system prompt (FEAT-019) — a prompt
  is an authoring instruction, not narrative content.
- **Source:** `[confirmed: user]` interview 2026-07-20, "Augment round 3 —
  variants, cloning & consistency", "consistency check & chapter flags";
  challenge C12; codex round 4; interview 2026-07-23, "Augment round 5",
  "boundaries recorded" / "SPA pages" / "RULE (per author only =
  members-only)"; interview 2026-07-23, "Augment round 6", "vocabulary —
  flag → warning"; interview 2026-07-24, "augment round 7", divergence 3

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
  never blocks. Entry editing happens on the working page's content pane
  too (FEAT-013 Note), draft-until-saved, same as chapter blocks. All
  codex management (create/edit/archive/history/restore/copy) happens on
  the working SPA; the settings-side codex browse (UC-071) is read-only,
  members-only.
- **Source:** `[confirmed: user]` interview 2026-07-20, "codex" round 4;
  interview 2026-07-23, "Augment round 5", "the working page" / "SPA
  pages" / "RULE (per author only = members-only)"

### FEAT-018 — Codex authoring from the composition chat
- **Purpose:** Generate a new codex entry or rewrite an existing one from
  the same composition chat that composes blocks.
- **Actors:** ACT-004, ACT-005 · **Priority:** should
- **Status:** proposed
- **Realized by:** UC-076, UC-077, US-086, US-087, US-088
- **Note:** Sourced from live chapter/entry text via the shared canvas: the
  assistant fills the open codex entry directly in the content pane, as a
  draft, saved only on explicit request — same draft-until-saved path as
  FEAT-013's block writes (UC-055), not a diff view. Failure handling is
  not respecced: both use cases point at UC-056. Ships after FEAT-017.
- **Source:** `[confirmed: user]` interview 2026-07-20, "codex" round 4;
  interview 2026-07-23, "Augment round 5", "the working page — two-pane,
  chat + content"

### FEAT-019 — Book & chapter system prompts
- **Purpose:** Standing authoring instructions that shape how the
  assistant writes for this book — set once, applied to every chat,
  instead of retyped into each one.
- **Actors:** ACT-004, ACT-005 · **Priority:** must
- **Status:** proposed
- **Realized by:** UC-093, UC-094, US-108, US-109
- **Note:** The **book** system prompt applies to every chat in the book;
  **owner only** — book-wide configuration, the same class as
  collaboration mode (UC-042) and visibility (UC-028). The **chapter**
  system prompt is **optional** and **narrows** the book's rather than
  replacing it — the book-wide voice always applies. Editable by **any
  member**, like the sketch it sits beside (UC-033). Both **carry over on
  clone** (FEAT-015) — the same class of book-shaping state as mode and
  visibility. The consistency check (FEAT-016) **does not inspect them**
  — a prompt is an authoring instruction, not narrative content. Accepted
  overlap with FEAT-013: FEAT-019 stores the instruction, FEAT-013
  applies it; an absent or empty prompt is valid, so FEAT-013 does not
  require FEAT-019. Not designed anywhere until this round — a book-wide
  system prompt and an optional per-chapter one were introduced in the
  architecture with no product requirement behind either; a new feature
  rather than a home in FEAT-013 because this is an owner-only, book-wide
  setting, distinct from the assistant feature that consumes it.
- **Source:** `[confirmed: user]` interview 2026-07-24, "augment round 7 —
  enforcing the architecture pass onto the spec", divergence 3

### FEAT-020 — Assistant modes & sub-agents
- **Purpose:** Let the admin configure how the AI assistant behaves per
  working mode and via reusable sub-agents — for each mode a system
  prompt, a set of available tools, and which sub-agents it may delegate
  to; and admin-created sub-agents (delegated workers) each with a name,
  prompt, tools and the modes that may invoke them.
- **Actors:** ACT-001 · **Priority:** must
- **Status:** proposed
- **Realized by:** UC-095, UC-096, UC-097, US-110, US-111, US-112, US-113,
  US-114
- **Note:** Modes are a **fixed system set of five** — edit-character,
  edit-location, edit-fact, write-chapter, close-chapter — extended only
  by the system, not at runtime; each maps to a working-page activity the
  assistant runs "in". Per mode the admin sets: an **optional system
  prompt** (empty → nothing added), the **available tools**, and the
  **accessible sub-agents**. A **sub-agent** is a delegated worker the
  admin creates freely: a **unique name**, system prompt, available
  tools, and which modes may invoke it — the mode↔sub-agent link is
  stored on the sub-agent but **editable from either view**. Sub-agents
  are **disabled, never deleted** (same pattern as user accounts,
  FEAT-003): disabling **detaches it from every mode** and stops it
  being invoked; reversible, and a re-enabled sub-agent stays unattached
  until modes select it again. **Tools ("MCPs")** are system-registered
  backend functions exposed to the assistant; the admin selects a subset
  per mode/sub-agent — the registry itself is code-defined
  (`/architect`). **Admin-only, system-wide** — the same configuration
  class as LLM servers (FEAT-004), distinct from configuring a specific
  book; authors never view this configuration, the same
  admin-interface-only pattern as FEAT-011's moderation view — not a
  breach of FEAT-011's "admin never participates in a book", since this
  is global assistant config, not book participation. **Accepted
  overlap:** FEAT-020 stores the mode/sub-agent configuration, FEAT-013
  applies it at runtime, FEAT-019 supplies the orthogonal per-book/
  per-chapter prompts; how the prompts combine and how tools/sub-agents
  are invoked is the deferred FEAT-013 assistant subsystem
  (`/architect`). `_TBD: whether a mode's tools default on or off before
  the admin configures it._` **Round 9:** a sub-agent may be **assigned a
  specific model** (one the configured LLM servers, FEAT-004, expose) or
  **re-use the main chat's model** (the default) — modes carry no model
  field. This partially resolves the model-selection `_TBD:` on
  FEAT-013: resolved for sub-agents, still open for the main chat's own
  model.
- **Source:** `[confirmed: user]` interview 2026-07-24, "FEAT-020 —
  assistant modes & sub-agents (augment round 8)"; challenges C-r8-1..
  C-r8-5; interview 2026-07-24, "FEAT-020 — sub-agent model assignment
  (augment round 9)"

<!-- product-spec:end -->
