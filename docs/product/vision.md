<!-- product-spec:start -->
# Vision

## Problem

Authors need LLM-assisted tooling for writing long-form fiction. Before that
domain can be built, the platform must be able to stand itself up: create its
own database, authenticate its users, manage accounts, connect to LLM
servers, and keep its data model healthy. Without this foundation there is no
instance to author on. `[confirmed: user]` interview 2026-07-20, "vision"

## Who has it

- **Administrator** (`ACT-001`) — needs to bring up a new instance, manage
  accounts, and keep the database and LLM connections working; now also
  moderates book content.
- **Author** (`ACT-002`) — needs an account and a session to log in; the
  account behind `ACT-004` (book owner) and `ACT-005` (co-author) roles.
- **First-run operator** (`ACT-003`) — faces an unconfigured instance with no
  database and no users yet.
- **Book owner** (`ACT-004`) — an author who created or received a book;
  controls its skeleton, membership, mode and visibility.
- **Co-author** (`ACT-005`) — an author granted access to someone else's
  book; writes within the rules the owner sets.
- **Reader** (`ACT-006`) — a logged-in user browsing and reading public
  books they aren't a member of.

`[confirmed: user]` interview 2026-07-20, "vision" / augment round,
2026-07-20

## What happens without it

No database exists and no admin can log in, so no user — admin or author —
can reach the system at all. `[inferred]` — consequence of first-run bootstrap
being the entry point; not stated directly in the interview.

For the book layer: greenfield, no workaround exists today. `[confirmed:
user]` augment round, 2026-07-20, "book — scope & purpose" — asked three
times; the user chose "no current workaround" explicitly over having a cost
invented. No pain evidence backs this layer; it is how the user wants the
product to work (challenge C2).

## Success signals (6 months)

- An operator can bootstrap a fresh instance: create a new database with a
  first admin, or import an existing database export.
- An admin can list, create, and manage user accounts (roles, password
  resets, disabling).
- An admin can register LLM server connections, test them, and enable models.
- An admin can view a database consistency report and remediate drift
  (create missing tables, sync schema, export/import, rebuild the vector
  index).
- An author can create a book, invite co-authors, build a chapter skeleton
  with sketches, write a chapter in edits in either collaboration mode
  (free or proposal), and an admin can remove illegal content. `[confirmed:
  user]` augment round, 2026-07-20 (challenge C5).
- An author can write a chapter with LLM assistance that stays consistent
  with prior chapters without their full text being present. `[confirmed:
  user]` augment round 2, 2026-07-20, "why continuity exists" / "generation
  context".
- An author can correct an earlier chapter and be told what it broke, and
  can explore an alternative storyline without disturbing the original.
  `[confirmed: user]` augment round 3, 2026-07-20, challenge C24.
- An author can write with an AI assistant side by side with the chapter
  or codex entry they're working on — directing it to a text selection,
  another chapter, the book's own material, or the web — and review its
  writes as a draft before anything is saved. `[confirmed: user]` interview
  2026-07-23, "Augment round 5 — book-writer SPA layout & the working
  page", "the working page" / "context model — hybrid push/pull".

`[confirmed: user]` interview 2026-07-20, "features — the four capabilities, in order"

## Scope

The four ordered foundation capabilities `[confirmed: user]` interview
2026-07-20, "features":

1. First-run bootstrap (create DB + first admin, or import a DB export).
2. User management interface.
3. LLM server connection interface.
4. Database consistency ("check consistency") page.

The book layer, added in the 2026-07-20 augment round `[confirmed: user]`:
books owned and shared between authors, a chapter skeleton built from
sketches, chapter writing in edits under two collaboration modes (free and
proposal), and admin moderation (quarantine/destroy). The foundation layer
above stands unchanged.

Continuity and LLM-assisted composition, added in the 2026-07-20 augment
round 2 `[confirmed: user]`: per-chapter summaries and a live set of state
notes drafted on chapter close and approved by the owner, and a
composition chat in which an author iterates with the LLM to produce a
chapter's next edit. `[confirmed: user]` interview 2026-07-20, "Augment
round 2 — continuity & block composition".

Variations and corrections, added in the 2026-07-20 augment round 3
`[confirmed: user]`: chapter variants (a reopened chapter's edit is a fix,
kept alongside its prior text), whole-book cloning (a fully independent
copy of a book), and an LLM consistency check that surfaces contradictions
as owner-reviewed flags rather than rewriting anything. `[confirmed: user]`
interview 2026-07-20, "Augment round 3 — variants, cloning & consistency".

The authoring workspace, added in the 2026-07-23 augment round 5
`[confirmed: user]`: one working surface where an author edits a chapter
or codex entry by hand or with an AI assistant side by side — the
assistant reads context that matches what's open (a chapter or a codex
entry), can be handed a narrower text selection, can pull in another
chapter, the book's own material, or the web on request, and writes into
whatever is open as a draft the author must explicitly save. The web
joins the book's own material as a new source the assistant may consult.
`[confirmed: user]` interview 2026-07-23, "Augment round 5 — book-writer
SPA layout & the working page".

## Non-goals

- **Narrowed, not deleted, by the 2026-07-20 augment round (challenge C1).**
  The blanket deferral below previously covered the whole fiction-authoring
  domain; the book-as-owned-shareable-object and its collaboration rules are
  now specified (FEAT-006..011) and this non-goal no longer covers them. The
  reversal is deliberate, scoped to this slice, and recorded here so the doc
  set doesn't silently contradict itself. `docs/architecture/CLAUDE.md` and
  root `CLAUDE.md` still describe the domain as deferred repo-wide — flagged
  to the user as stale outside this layer's write scope.
- **Reversed by the 2026-07-24 augment round 7 (challenge C-r7-1) — the
  fourth non-goal reversal in this doc set's life, after C1, C10 and the
  round-1 chapter-substrate widening.** This non-goal previously read
  "still deferred: what a chapter block contains (text format, length,
  internal structure)." Enforcing the architecture pass onto the spec
  closes it: an edit is free text, any length, no internal structure,
  appended to the chapter's body when applied, and not separately
  addressable afterwards. Recorded here so the reversal is visible, not
  drift. `[confirmed: user]` interview 2026-07-24, "augment round 7 —
  enforcing the architecture pass onto the spec", divergence 5.
- **Narrowed a second time by the 2026-07-20 augment round 2 (challenge
  C10) — the third non-goal reversal in one session, after C1 (domain) and
  the round-1 chapter-substrate widening.** The LLM generation pipeline was
  a blanket non-goal; it is now specified as far as observable chat
  behaviour goes (FEAT-012, FEAT-013): a composition chat, the four
  continuity artifacts it's guaranteed, and how a produced edit enters a
  chapter. The reversal is deliberate and recorded here, not drift.
  `[confirmed: user]` interview 2026-07-20, "Augment round 2", challenge
  C10. **Round 5 sharpened this:** the four-artifact guarantee became the
  mode-dependent hybrid baseline (US-057), and the "produced block" hand-off
  dissolved into a shared-canvas write.
- Still deferred within generation, and treated as genuinely open, not
  settled: **prompt design, model-selection strategy, context assembly
  (ordering/truncation), token budgets, and chat storage** — architecture's
  job, not this layer's. Also still deferred: the **character/place entity
  model** — state notes are free text with no entity backing this round;
  a direct consequence is that staleness cannot be flagged per subject.
  `[confirmed: user]` interview 2026-07-20, "Augment round 2", "summaries &
  state notes" / "deferred / `_TBD:`".
- Any technical/design decision (schema, storage, library, API shape) — that
  is `docs/architecture/`'s job, not this layer's.
- The working page's layout mechanics — pane orientation, resize/divider
  behaviour, ratio persistence — and the AI assistant's tools (retrieval
  and ranking, web-search wiring, model selection, the agent/sub-agent
  call loop) are `/architect`'s, not this layer's; this layer records only
  the observable behaviour they exist to serve. `[confirmed: user]`
  interview 2026-07-23, "Augment round 5 — book-writer SPA layout & the
  working page", "/architect notes (parked — NOT written as
  requirements)".
<!-- product-spec:end -->
