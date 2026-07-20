# Product-spec interview — BookWriter admin / foundation layer

Distilled Q&A per round. Source of record for the writer. Not a transcript.

## vision   (2026-07-20)
- Q: What are we building?
  A: A tool to write **fiction books** — LLM-assisted authoring of long-form texts. Multi-user web app (FastAPI + SQLModel backend, React/Mantine/MobX SPAs).
- Q: What must exist before the authoring domain?
  A: The **system foundation** — set the platform up. All of it lives in the **admin section**: define users, create the database, create LLM server connections.
- Q: What is explicitly NOT part of this spec?
  A: The fiction-authoring domain itself (books, chapters, characters, generation pipeline). Deferred by the repo's own rule ("Do not invent domain entities"). This pass is the admin/foundation only.
- Q: Is there a reference?
  A: Yes — the sibling project `D:/GitRoot/_TextGens/LLMRPTextOnlyProject` (referred to as "llm-rp-server"). It already implements all four foundation capabilities on a near-identical stack. Behaviour is a reference/baseline, not requirements-of-record; carry-overs not explicitly confirmed are tagged `[inferred]`.

## features — the four capabilities, in order   (2026-07-20)
- Q: What is the ordered scope of the foundation?
  A: 1) If there is no DB or no users → create the DB and add an admin. 2) User (management) interface. 3) LLM server interface. 4) DB "check consistency" page.

## FEAT-001 first-run bootstrap   (2026-07-20)
- Q: Besides creating the first admin, should first-run bootstrap also allow importing an existing database?
  A: **Create + Import.** First-run wizard offers "Create Database" (new DB + first admin) OR "Import Database" (restore from a DB export). [confirmed: user]

## FEAT-003 user management — roles & lifecycle   (2026-07-20)
- Q: What user roles should BookWriter define? (reference uses admin/editor/player)
  A: **admin + author.** 'admin' manages the system (users, LLM servers, DB); 'author' writes books. [confirmed: user]
- Q: What is the terminal action on a user account?
  A: **Disable only.** No hard delete. Disabling nulls credentials so the account can't log in; data/attribution preserved; reversible via password reset. [confirmed: user]

## FEAT-005 DB check-consistency page   (2026-07-20)
- Q: How much should the DB "check consistency" page do?
  A: **Report + remediate.** Per-table schema-drift report (ok / drift / missing, missing & extra columns) PLUS actions: create missing table, sync schema, export/import DB, rebuild vector index. [confirmed: user]

## FEAT-002 authentication & session   (2026-07-20)
- Q: How does session/auth work?
  A: [inferred, from reference] JWT session with a **per-user signing key** (disabling a user or rotating their key instantly invalidates their tokens), bcrypt password hashing, login rate-limiting. Carried over from the reference and BookWriter's own architecture docs; to be confirmed at review.

## Reference mapping (behavioural baseline — LLMRPTextOnlyProject)   (2026-07-20)
- Bootstrap: server boots without a DB; `GET /api/auth/status → {needs_setup}`; first-run wizard `POST /api/auth/setup/create` (create DB + admin) and `.../setup/import` (restore ZIP).
- Users: admin-gated CRUD-minus-delete — list, create, reset password, change role, disable (disable = null credentials). Cannot change own role or disable self.
- LLM servers: DB-stored server records (name, `backend_type` ∈ {llama-swap, openai}, base_url, api_key, enabled_models, embedding flags). `$ENV` api-key indirection; secrets never returned (only `has_api_key`). Live connection probe lists models; one designated embedding server+model.
- DB consistency: per-table schema-drift status vs SQLModel models; remediation via create-table / sync-schema (ALTER ADD COLUMN, recreate to drop); DB export/import ZIP; rebuild LanceDB vector index.
- Divergences BookWriter adopts by decision: roles are admin/author (not admin/editor/player); disable-only terminal action (matches reference); create+import bootstrap (matches reference); report+remediate DB page (matches reference).

---

# Augment round — the book domain & multi-author collaboration   (2026-07-20)

Workflow C (augment). Scope of this round confirmed by the user: **the book as an owned,
shareable object plus the collaboration rules**. Content formatting and the LLM generation
pipeline remain deferred. This round deliberately **lifts** the domain deferral recorded in
`vision.md` and root `CLAUDE.md` for this slice only — see C1.

## book — scope & purpose   (2026-07-20)
- Q: How far does this augment reach?
  A: **Book + collaboration only.** Internal structure and content editing stay `_TBD:`. [confirmed: user]
- Q: What do co-authors do today instead, and what does it cost them?
  A: **Nothing — greenfield, no workaround exists.** Asked three times; the user chose the
  "no current workaround" option explicitly rather than have a justification invented. Recorded
  honestly: this feature set has **no pain evidence**, it is how the user wants the product to work. [confirmed: user]

## book structure — chapters, states, sketches   (2026-07-20)
- Q: What is a book from the author's side?
  A: A **set of chapters**. Structural detail deferred to a later session. [confirmed: user]
- Q: What states does a chapter have?
  A: **Three states** — *planned* (sketch only, not yet written) → *open* (being written) →
  *closed* (written, not editable). [confirmed: user]
- Q: How many chapters may be open at once?
  A: **At most one open chapter per book.** [confirmed: user]
- Q: Who controls a chapter's state, and is closing terminal?
  A: **Owner only, and reopenable.** Only the book owner opens, closes and reopens chapters.
  Reopening a chapter implies closing the currently-open one, since only one may be open. [confirmed: user]
- Q: Who creates chapters and sets their order?
  A: **Any member adds, owner orders.** Co-authors can add chapters into the skeleton; the
  sequence is the owner's call. [confirmed: user]
- Q: What are sketches, and who may edit them?
  A: A **sketch** is the idea/outline for a not-yet-written chapter — used to build the book's
  skeleton first. **Any co-author may edit the sketch of any unwritten chapter**, in parallel.
  This is the parallel-work surface. [confirmed: user]

## writing — blocks & concurrency   (2026-07-20)
- Q: Is a chapter written in one piece?
  A: **No — in blocks.** "The process of the chapter writing is not 'full chapter in once', it's
  by some 'blocks'." Block is the write unit; what a block contains is `_TBD:`. [confirmed: user]
- Q: Two co-authors editing the open chapter at the same time?
  A: **Last write wins, with warning — but at block granularity.** Because writing is by blocks,
  two concurrent additions both land ("both 'blocks' will be added"). The warn-then-later-write-wins
  rule applies only when two co-authors edit the *same* block. [confirmed: user]

## collaboration mode   (2026-07-20)
- Q: What is the PR-like mode called?
  A: **Proposal mode.** (Options offered: variant / proposal / suggestion / review.) Free mode is
  the other option: co-authors edit directly. [confirmed: user]
- Q: What is a proposal made of — a whole alternative chapter, or blocks?
  A: **Proposed blocks.** A co-author proposes one or more blocks for the open chapter; the owner
  applies the ones they want. Same unit as free mode — the only difference between the two modes
  is whether a gate exists. [confirmed: user]
- Q: When the owner approves, what happens to competing proposals?
  A: **The owner merges freely** — they may take parts of several proposals rather than picking
  one whole. Approval is a merge, not a binary accept. [confirmed: user]
- Q: Is the mode per chapter or per book?
  A: **Per book, set by the owner at creation** — "on book creation the owner set the mode".
  It applies to whichever chapter is open. [confirmed: user]
- Q: Can the mode change later?
  A: **Yes, the owner can change it at any time.** The fate of pending proposals when switching
  to free mode is `_TBD:`. [confirmed: user]

## ownership, membership & visibility   (2026-07-20)
- Q: Who manages membership, and can a book change hands?
  A: **Owner adds/removes co-authors, and ownership can be transferred.** Covers an owner leaving
  or a book changing lead author. [confirmed: user]
- Q: A co-author is removed — what happens to their blocks?
  A: **Content and attribution both stay.** They lose access; their text remains, still credited
  to them. Mirrors FEAT-003's disable-preserves-attribution rule. [confirmed: user]
- Q: Who can see a book's contents?
  A: **The owner decides: private or public.** Private = members only. Public = **read-only to any
  logged-in user**; explicitly *not* anonymous — the instance stays fully auth-gated. [confirmed: user]
- Q: Can a book be deleted?
  A: **Archive only, no hard delete** by the owner — consistent with FEAT-003's no-hard-delete
  precedent for accounts. [confirmed: user]

## admin access & moderation   (2026-07-20)
- Q: Can an admin read books?
  A: **Yes — but only in the admin interface.** The user's refinement, verbatim in substance:
  admins can read all books, but do **not** "participate" in books in the main authoring
  interface; there is a **special read mode in the admin interface** whose purpose is to remove
  unwanted/illegal content. Admin access is a moderation surface, never an authoring one. [confirmed: user]
- Q: What can an admin remove, and is it destructive?
  A: **Quarantine a whole book, then destroy it as a separate action.** Two steps: quarantine
  makes the book invisible to everyone including its members (fast takedown, reversible mistake);
  a second explicit action destroys it permanently. Book-level granularity only — not per block or
  per chapter. [confirmed: user]
- Q: Does the owner learn that content was removed?
  A: **Yes — the owner sees a removal notice**, with a reason. Not silent. [confirmed: user]

## challenges   (2026-07-20)
- C1 Scope creep · domain deferral in root `CLAUDE.md` + `vision.md` non-goal — the book domain is
  a recorded non-goal; specifying it now reverses a written decision.
  → **accepted**: the deferral is lifted deliberately for this slice. `vision.md` Scope and
  Non-goals are amended in the same pass so the docs never contradict each other. Root
  `CLAUDE.md` is outside the product layer's write scope — flagged to the user as stale.
- C2 No pain evidence · book collaboration — the feature set is justified by no named workaround
  or cost; asked three times.
  → **rejected**, user's reasoning: greenfield — nothing exists yet and this is simply how the
  product should work. Recorded as `[confirmed: user]` with **no pain evidence**, rather than
  fabricating a justification. If this layer is ever cut for scope, this is the weakest defence
  in the spec.
- C3 Conflict · one-open-chapter rule vs. the multi-author premise — with one writable chapter per
  book, co-authors cannot work different chapters in parallel; "collaboration" would mean many
  authors crowding one chapter.
  → **rejected**, user's reasoning: **serial by design** — the book is written front-to-back and
  the single open chapter *is* the coordination mechanism. The user resolved the tension by
  introducing **sketches**: co-authors not working the open chapter build the skeleton ahead of it.
  This challenge produced the sketch concept; it is the most productive exchange in the round.
- C4 Unfalsifiable · "public" book — public to whom, and does it break the auth gate?
  → **accepted**: public = **read-only to any logged-in user**. No anonymous surface; the
  instance remains fully auth-gated. Now falsifiable.
- C5 Vision alignment · new features trace to no success signal — `vision.md`'s six-month signals
  cover only the foundation layer.
  → **accepted**: `vision.md` gains a book-layer success signal.
- C6 Priority inflation · every new feature reads "must".
  → **accepted**: **proposal mode builds last**; every book runs in free mode until it exists.
  Nothing is dropped — this is build order for `/roadmap`, not scope reduction. (First phrasing
  as "cut one" was misread by the user; re-asked as build order.)
- C7 Conflict · "private" book vs. "admin can read all books".
  → **superseded by C9**: admin access is moderation-only and lives in a separate interface, so
  "private" means members-only in the authoring surface without qualification.
- C8 Unstated assumption · last-write-wins assumes co-authors rarely touch the same text.
  → **accepted**: the rule is **per block**. Concurrent adds of different blocks both land; a
  same-block collision **warns the second saver**, then the later write wins.
- C9 Conflict · archive-only vs. destroying illegal content — the user's moderation refinement
  requires real destruction, but the book lifecycle was settled as archive-only, never destroyed.
  Archiving illegal content leaves it on the instance.
  → **accepted**: **quarantine-then-destroy at book level, admin interface only**, stated
  explicitly in the spec as the single sanctioned exception to archive-only. Owner-facing
  lifecycle (archive, no delete) is unchanged.

## deferred / `_TBD:`   (2026-07-20)
- What a **block** contains — text format, length, internal structure.
- Fate of **pending proposals** when a book switches from proposal mode to free.
- Whether public books are **discoverable** (browsable list) or reachable only by direct link.
- Whether a quarantined book can be **released** back to its members (appeal path), or whether
  quarantine only ever ends in destruction.
- The **LLM generation pipeline** — deferred entirely, as before.

---

# Augment round 2 — continuity & block composition   (2026-07-20)

Workflow C. Trigger: the user asked to discuss book structure and "what is needed", motivated by
**LLM context**: prior chapters must inform generation without their full text being present.
This round lifts the **generation-pipeline deferral** (challenge C10).

## why continuity exists   (2026-07-20)
- Q: Why is a book a set of chapters, beyond open/closed?
  A: **LLM context.** "We don't need to pollute the context when generating a block, but we
  definitely need some information from the previous chapters." [confirmed: user]
- Q: What information must survive a chapter?
  A: Two distinct artifacts. A **summary** — the short content of the chapter. And **state notes**
  (the user's "memorable points") — "changes or states of characters, some place conditions,
  something like this ... out of main summary but important for the next chapters." [confirmed: user]
- Q: What is the falsifiable form of "don't pollute the context"?
  A: Replaced by an explicit guarantee of what generation receives — see "generation context"
  below. "Not polluted" is not checkable; the four-artifact guarantee is. [confirmed: user]

## summaries & state notes   (2026-07-20)
- Q: Who produces the summary and state notes?
  A: **LLM proposes, owner approves.** On closing a chapter the system drafts them; the owner
  reviews, edits and accepts. Continuity stays human-checked. [confirmed: user]
- Q: How does a state note stop being true? (character injured ch3, healed ch7)
  A: **Current state, plus per-chapter history.** There is one live set of state notes; each
  chapter records which notes it **added, modified or deleted**. Chapter N sees current truth; the
  changeset preserves when a fact changed. [confirmed: user]
- Q: What is a state note attached to — a character/place record, a subject label, or nothing?
  A: **Free text, no entities.** The character/place entity model stays deferred. Consequence,
  stated at the time: subject-targeted staleness flagging becomes impossible. [confirmed: user]
- Q: Can a chapter close without approved continuity data?
  A: **Approval required to close.** Later: "The closed chapter is closed. All summaries are done,
  all notes are taken. No continuation for it — we are moving to the new chapter." Closing *means*
  continuity is complete. [confirmed: user]
- Q: Reopening a closed chapter (US-039) makes its summary and notes describe changed text?
  A: **Flagged stale, owner must re-confirm.** [confirmed: user]
- Q: The cascade — chapter 3 is edited, and chapters 4+ built state on top of its deltas?
  A: **Not decided yet → `_TBD:`.** Acknowledged at the time as a known hole, not an oversight:
  local flagging ships, the downstream chain is unresolved. [confirmed: user]
- Q: Who may change state notes?
  A: **Follows the book's collaboration mode** — free mode any member edits directly, proposal
  mode they propose and the owner applies. Reuses FEAT-010's mechanism. [confirmed: user]

## generation context   (2026-07-20)
- Q: What must be available when a block is generated?
  A: **All four** — summaries of all prior chapters · current state notes · full text of the open
  chapter · sketches of upcoming chapters. Sketches therefore serve double duty: coordination
  (FEAT-008) and forward context. [confirmed: user]

## block composition chat   (2026-07-20)
- Q: Does this round spec generating a block, or only the artifacts?
  A: **Generation is included, as a chat.** "The block generation is the chat with LLM where all
  artifacts are added to the context and then author chats and is creating/recreating/polishing the
  next block. When it's ready LLM produces the block, author can edit it manually." The author has
  a free-form prompt input. Similar in shape to the reference project. [confirmed: user]
- Q: Mine the reference project's chat surface with product-scout?
  A: **No — interview instead.** Offered and declined; behaviour here is user-stated, not
  scout-evidenced. [confirmed: user]
- Q: What is a composition chat's lifetime?
  A: **The author starts and ends chats freely** — not bound to a block or a chapter. [confirmed: user]
- Q: In proposal mode, what does a co-author's generated block become?
  A: **A proposal.** One rule for how blocks enter a chapter regardless of origin. [confirmed: user]
- Q: What happens when the LLM is unreachable or returns nothing?
  A: **Error shown, retry offered**, conversation preserved so nothing is retyped. [confirmed: user]
- Q: Can co-authors see each other's chats?
  A: **Private to their author.** Only the produced block is shared. [confirmed: user]
- Q: Build order for the two new features?
  A: **Split them** — continuity early, composition chat later. Exact position: **let `/roadmap`
  decide**; record dependency edges without prescribing an order. [confirmed: user]

## challenges   (2026-07-20, round 2)
- C10 Scope creep · the generation-pipeline non-goal in `vision.md` — a third deferral reversal in
  one session.
  → **accepted**: recorded explicitly in `vision.md` so the reversal is visible, not drift. The
  boundary held: the chat's observable behaviour is product; prompts, model selection, context
  assembly and token budgets remain architecture's.
- C11 Unfalsifiable · "don't pollute the context" — a mechanism-flavoured goal with no checkable
  outcome.
  → **accepted**: replaced by the four-artifact guarantee, which acceptance criteria can assert.
- C12 Unstated assumption · staleness cascades through the delta chain — editing chapter 3 can
  invalidate every later chapter's state changeset, which is the same class of continuity bug the
  feature exists to prevent.
  → **deferred** to `_TBD:` by explicit user decision, with the hole named rather than hidden.
- C13 Solution in disguise · "some summary stored along the chapters" names a storage mechanism.
  → **accepted**: captured as the requirement underneath (what must survive a chapter, and who
  approves it); storage left to `/architect`.
- C14 Vocabulary drift · "memorable points" is vague between event and ongoing state.
  → **accepted**: the domain's word is **state note**.
- C15 Priority · continuity vs. proposal mode for build position.
  → **accepted**: split — continuity early, chat late; final sequencing delegated to `/roadmap`.
- C16 Overlap · "author can edit the produced block manually" duplicates FEAT-009 block editing.
  → **accepted as an overlap, not respecced**: the chat's responsibility ends at producing a block.
- C17 Conflict · the close gate vs. the already-approved UC-036 / US-038, which specify closing a
  chapter with no continuity precondition.
  → **accepted**: UC-036 and US-038 are **amended in place** (ids unchanged) to carry the
  precondition, on the user's reasoning that closing *means* continuity is complete. Reopen
  (UC-037/US-039) survives and flags the data stale. The "no continuation" phrasing is read as *no
  further writing while closed*, not a removal of reopen — **the one inference in this round**,
  flagged to the user.

## deferred / `_TBD:`   (2026-07-20, round 2)
- The **staleness cascade** through the per-chapter state changesets (C12).
- Whether an **open** chapter contributes state notes before it closes.
- Which enabled model a composition chat uses — may resolve as architecture's, not product's.
- Prompts, context assembly, token budgets, chat storage — architecture, never product.

---

# Augment round 3 — variants, cloning & consistency   (2026-07-20)

Workflow C. Trigger: the user opened the reopening mechanics and reframed them as **branching**,
then mid-discussion replaced branching with a simpler model — **chapter variants + whole-book
cloning**. Both the rejected and the adopted models are recorded; the rejection is spec evidence.

## the rejected branching model   (2026-07-20)
- Q: What are the reopening mechanics?
  A: Initially framed as branching: "when we reopen the chapter and it has the chapters after it —
  we create the branch of it, if we really change any block... but not always. We can also must be
  able not to branch, but to 'fix' the chapter." On close the owner would decide fix vs branch,
  with a possible third way (branch whose later content is rewritten). [confirmed: user]
- Orchestrator's reduction, presented back: two independent axes — same line vs new line, and
  following chapters carried vs not. Three of the four combinations are the user's three cases;
  the fourth (same line, following chapters discarded) is excluded by the archive-only principle.
- First set of answers under the branching model (**superseded**, kept for the record): branching
  is for creative variations kept and compared · one active line at a time · owner can copy a
  chapter across lines · the domain's word is **variant**.
- Q: (superseding) Is there something cleaner?
  A: **Yes — cloning.** "We can 'clone' the book if we want new variation to not overload the
  interface. So the fix, when we edit some in the chapter (but still we keep all the variants of
  the chapter and show it to authors). And if we need fully new storyline — we can 'clone' and
  then re-do the story." [confirmed: user]
  → **The branch tree is dropped.** No active-line concept, no per-line state notes, no merge. A
  book stays linear, so FEAT-007, FEAT-011 and export keep working unchanged. The word **variant**
  survives, now meaning a *chapter* variant.
  → Cost recorded and accepted: two clones drift apart forever; a fix common to both is done twice.

## chapter variants & fixes   (2026-07-20)
- Q: What happens when a closed chapter is edited?
  A: It becomes a **fix**, and the chapter **keeps all its variants**, shown to authors. Following
  chapters stay. [confirmed: user]
- Q: Which variant is the chapter?
  A: **The owner picks one active variant.** Others remain readable history the owner can switch
  back to. [confirmed: user]
- Q: What follows a variant switch?
  A: **The same as a fix** — switching changes the chapter's text, so it takes the same path. Plus:
  "we need the easy way to 'see' the variants." [confirmed: user]
- Q: Is "even on fix we create a copy of the chapter" a requirement?
  A: Treated as a **mechanism**, not a requirement (challenge C20). The requirement underneath is
  that previous text stays recoverable; the storage form is `/architect`'s.

## book cloning   (2026-07-20)
- Q: Is a clone connected to its source?
  A: **Fully independent.** No link, no sync, no comparison. [confirmed: user]
- Q: What does a clone copy?
  A: **Chapters, blocks and sketches · state notes and summaries · membership · collaboration mode
  and visibility.** Plus: "if it clones by owner — it clones the members (optional, or not all)" —
  so member carry-over is **selectable**, not automatic. [confirmed: user]
- Q: Who can clone?
  A: **Owner and co-authors.** "We can also give the member the ability to create his own clone, in
  this case they become the owner and can copy or not copy members." A co-author's clone makes them
  its owner. [confirmed: user]
- Q: A co-author clones a private book and makes the clone public — the owner's private content
  escapes (conflict C21)?
  A: **Only the owner can clone a private book.** Co-authors may clone public books. [confirmed: user]

## consistency check & chapter flags   (2026-07-20)
- Q: The cascade (C12, deferred twice) — chapter 3 is fixed, chapters 4+ have notes built on the
  old text. What happens?
  A: **An LLM consistency check that produces flags.** "LLM checks the consistency and shows to the
  owner inconsistent notes or chapter content. If all is clear — nothing to do, if something is
  wrong, it must be flagged. So we need some flags (with comment/data) on chapters." Nothing is
  silently rewritten. **This closes C12.** [confirmed: user]
- Q: When does the check run?
  A: **On demand, and as part of closing a fixed chapter.** "When owner is closing the chapter they
  need to run the consistency check 'kind of on demand' and, after the warnings, or fix the chapter
  again or apply the flags." [confirmed: user]
- Q: Are flags only consistency findings?
  A: **General — members can flag too**, with a comment. [confirmed: user]
- Q: Does a flag record its origin?
  A: **Yes** — a flag shows whether it came from a consistency check or a person; they carry
  different weight. [confirmed: user]

## layout   (2026-07-20)
- Q: `features.md` is at 393 of ~400 lines and never splits by rule; three more features breach it.
  A: **Move the registry to `quick-reference.md` only.** `features.md` keeps its feature blocks;
  `quick-reference.md` becomes the sole canonical id registry. **This is a contract change** —
  `docs/product/CLAUDE.md` currently names `features.md` the canonical registry and must be amended
  in the same pass. [confirmed: user]

## challenges   (2026-07-20, round 3)
- C18 Solution in disguise · "branching", modelled on chat-app branching — a mechanism proposed as
  a requirement.
  → **accepted, and superseded by the user**: reduced to two axes, then dropped entirely in favour
  of chapter variants + cloning. The requirement underneath — *make book variations and fixes
  possible* — survives; the tree does not.
- C19 Scope · a branch tree would have redefined "the book" for reading, export and moderation.
  → **rejected as unnecessary** by the user's cloning model: a book stays linear, so FEAT-007,
  FEAT-011 and export need no change.
- C20 Solution in disguise · "even on fix we create the copy of chapter".
  → **accepted**: captured as *previous text stays recoverable*; storage form left to `/architect`.
- C21 Conflict · cloning defeats privacy — a co-author clones a private book and publishes the
  clone, and the owner has no say.
  → **accepted**: **only the owner may clone a private book.** Co-authors clone public books.
- C22 Conflict · cloning defeats moderation — an admin destroys a book for illegal content, but a
  co-author's independent clone still carries it, so the takedown takes nothing down.
  → **accepted, with the limitation made visible**: **an admin moderates each book separately.**
  Clones are independent books dealt with on their own merits. FEAT-011 must state plainly that
  moderation does not reach clones, rather than leaving it to be discovered.
- C23 Unstated assumption · a co-author can take a complete copy of the owner's work and own it.
  → **accepted deliberately** after being put to the user: co-authors are trusted collaborators and
  forking is how creative variation happens. Bounded by C21 for private books.
- C24 Vision alignment · three new features trace to no success signal.
  → **accepted**: `vision.md` gains a variations-and-corrections signal.

## deferred / `_TBD:`   (2026-07-20, round 3)
- The **C12 cascade `_TBD:` is now CLOSED** by FEAT-016 — FEAT-012's marker must be replaced with a
  cross-reference, not left standing.
- Still open from earlier rounds and untouched: whether an open chapter contributes state notes
  before closing · which enabled model a chat uses · the five FEAT-012/013 exception-flow outcomes.

## codex   (2026-07-20, round 4)

- Q: What are the book "helpers"?
  A: "the characters, locations, and just lore facts. The same way they do exist in the reference
     project." Editable directly, and — the better thing — generatable/editable from the block
     composition chat. "So when I'm chatting and write the block - i can ask LLM to generate the
     cahracter or rewrite/edit the character, or location or some lore fact (kind or memory)."
- Q: How do these relate to FEAT-012 state notes, which were defined in round 2 as "changes or
     states of characters, some place conditions"?
  A: Separate. Identity vs. change. A codex entry is the stable thing (who Elen is); a state note
     is what a chapter changed about the world. A state note may reference a codex entry.
- Q: Are the kinds fixed or author-defined?
  A: "Characters and locations are seperated because they have 'names', lore facts just facts.
     Honestly all is lore fact but character and location are 'special' by nature."
- Q: What does "having a name" buy them functionally?
  A: Both — named entries carry state-note history AND are name-addressable. Facts do neither.
- Q: Per book, or an author-level library across books?
  A: "Per book, but we can copy/import/export - kind of for sequels etc"
- Q: Which of copy / import / export?
  A: Copy between books, yes. "import/export to files functionality will be discussed on roadmap,
     it's technical" — OUT of this round.
- Q: Who may create and edit them?
  A: Follows the book's collaboration mode (same rule as state notes, US-053).
- Q: What do we call them?
  A: **Codex entry.** ("helper" was the user's working word, not a domain word.)
- Q: When the chat generates a character, where does it land?
  A: Shown in the chat first, saved only on explicit request. Mirrors UC-055.
- Q: Does editing an existing entry from the chat take the same path?
  A: Yes — same review-then-save. (User did NOT choose the diff variant.)
- Q: Does the consistency check (FEAT-016) look at the codex?
  A: Yes — lore is checked too; the check can flag a contradiction with an entry.
- Q: Does the admin moderation view (FEAT-011) show the codex?
  A: "Yes — it's book content." Illegal material can sit in a codex entry as easily as in a block;
     the moderation view must reach it or the surface has a hole.
     [Recorded late — this Q&A was omitted from the first write of this round's notes, which caused
     the writer to tag UC-043/US-093 `[inferred]`. Corrected to `[confirmed: user]`.]
- Q: Can a Reader (ACT-006) of a public book see the codex?
  A: No — members only.
- Q: Does each chapter variant (FEAT-014) get its own codex?
  A: "No, one codex per book but we keep edit history of every entity."
- Q: What can a member do with an entry's edit history?
  A: View and restore.
- Q: What happens when a member deletes an entry that state notes reference?
  A: "Archine not delete, but consistency check on chapter must at least warn about missin entity
     (honestly not all the characters must be in the codex, but better to be)."
     → archive-not-delete; the check WARNS and never blocks; codex coverage is explicitly OPTIONAL.

## challenges   (2026-07-20, round 4)
- C25 vocabulary drift · codex vs. FEAT-012 state notes — one concept under two names, or two?
  → accepted: split as identity vs. change. Drove the FEAT-012 amendment (a state note names the
    entry it is about). Without this the domain ships the same idea twice.
- C26 solution in disguise · "Those items are vector indexed and allowed using tools, not sure for
  now how we will inject them to context" — mechanism, not requirement.
  → accepted: routed to /architect. Requirement kept as the need underneath — the codex grows
    beyond what can be shown wholesale, so generation must reach relevant entries without the
    author hand-picking them.
- C27 unfalsifiable · what makes an entry "relevant" enough to reach a composition chat?
  → deferred: no measurable criterion offered. `_TBD:` rather than a vague AC.
- C28 happy path only · "we keep edit history" with no read/restore story.
  → accepted: user specified view AND restore.
- C29 priority inflation · both new features arrived as must.
  → accepted: FEAT-017 must, FEAT-018 should (it is the enhancement, not the capability).
- C30 scope creep · codex file export/import.
  → deferred: user ruled it technical, for /roadmap. Not specced here.
- C31 unstated assumption · deleting an entry that state notes reference.
  → accepted: entries archive rather than delete (consistent with UC-023 books, FEAT-003 users),
    and the consistency check warns about a missing entity.

## deferred / `_TBD:`   (2026-07-20, round 4)
- The relevance criterion for drawing codex entries into a composition chat (C27).
- Codex file export/import (C30) — technical, deferred to /roadmap.
- Whether archiving a codex entry can be undone.
- Whether copying entries between books carries their edit history.
