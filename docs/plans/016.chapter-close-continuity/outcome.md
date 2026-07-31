# Outcome — 016.chapter-close-continuity

Intended doc changes, grouped by target architecture file. Applied by
`/architect` at finalization; product-side items are `/product-spec`'s.

## `docs/plans/roadmap.md` and `docs/plans/016.chapter-close-continuity/brief.md` — flag for `/roadmap`

**Not edited by this plan** (roadmap files are `/roadmap`'s). Surfacing for a
re-shape:

- `brief.md`'s `## Scope` **Out** list says *"the LLM consistency check
  (FEAT-016 UC-064/065/080, mapped later)"*. Design-note D2 pulls it **in**,
  user-confirmed against this exact wording. `roadmap.md`'s "Mapped later"
  entry for the same ids is stale the moment this plan lands.
- Reason: mechanically the check is the `close-chapter` mode's own work (no
  second subsystem), which is what made pulling it in affordable inside the
  ultra band's overrun.

## `docs/product/` — flag for `/product-spec`, not edited here

- **UC-048** ("Owner reviews the drafted summary and state-note changeset /
  edits / approves") is not implemented as written — a clean run writes both
  artifacts `approved` and closes the chapter in one step, with no review
  surface. **US-050.AC-1 / AC-2** (edit-replaces-draft, approve-marks-
  approved) have no surface to be satisfied on. **US-051.AC-1** ("close
  refused until continuity approved") is vacuously true but not satisfied in
  the sense product means — a chapter never sits in `closing` awaiting
  approval; a stop/failure/blocking-flag all discard and return to `open`
  instead. **UC-047**'s postcondition ("pending owner approval") holds only
  for the duration of the turn.
  Reason: design-note D3, user's explicit rule — "the close only succeeds on
  a clean run"; the author's review is watching the procedure run with Stop
  available, not a form afterwards.
- **US-053.AC-2** ("held as a proposal until the owner applies it") is not
  satisfied — a co-author's state-note edit in a proposal-mode book is
  refused (403), not held. Reason: FEAT-010's proposal-holding mechanism
  does not exist yet; the refusal is the honest stand-in (design-note D9).
- **UC-066** ("apply flags from consistency warnings") as a distinct act is
  gone — flags are raised and resolved (UC-067/068) but there is no separate
  "apply" step, because D3 removed the review stage it belonged to.
  **US-074.AC-2** ("owner applies the flags instead, chapter closes carrying
  them") is therefore not satisfied; only AC-1's "return to open" survives,
  as the Stop/cancel path.
- **A chosen answer inside an open FEAT-016 `_TBD:`** —
  `domain-continuity.md` → "Open in product, not resolved here" lists
  *"whether resolving a flag that a later check raises again reopens it or
  raises a new one"* as undecided. This plan's answer (design-note D6):
  `POST /close` **deletes** every `origin=check` flag on the chapter before
  each run, rather than resolving them; `origin=person` flags are untouched
  and advisory. The `_TBD:` stays open for `/product-spec` to close formally;
  this is what the architecture chose to do meanwhile, recorded so a later
  reader does not re-derive it.

## `docs/architecture/domain-continuity.md`

- **New section: "The close procedure, as built."** Closing a chapter is an
  assistant turn in the `close-chapter` mode (not a hidden/direct call, D1);
  the turn drafts the summary (`draft_chapter_summary` tool), the state-note
  changeset (`draft_chapter_notes` tool), proposes the resulting live note
  set (`propose_active_notes` tool, held in-memory in `ToolContext`, D7), and
  runs the consistency check via `raise_check_flag` / `read_continuity_context`.
- **Finalize is a deterministic server-side post-turn step**
  (`services/chapters.py::finalize_close_turn`), not a model decision (D5):
  clean run (both artifacts `draft`, no open `origin=check` flag) → `closed`,
  both artifacts `approved`, `Book.active_notes` written from the in-run
  proposal; anything else → `open`, artifacts wiped.
- **`Book.active_notes` gets its first writer** — `finalize_close_turn` on a
  clean run, and `services/continuity.py::update_state_notes` for the direct
  UC-050 edit path. Both are now documented writers, matching the "exactly
  two writers" invariant this file already states.
- **`closing` exists only while the turn streams** (D4) — a stop, a failure,
  or a blocking flag all return the chapter to `open` with every artifact
  discarded; there is no "draft continuity sitting on an open chapter" state.
- **Flag deletion on close, not resolution** (D6) — record as the chosen
  behavior inside the still-open `_TBD:`, per the product note above.
- Reason for all of the above: `docs/plans/016.chapter-close-continuity/`
  (this plan), decisions D1–D7.

## `docs/architecture/domain-chapter.md`

- **"The close seam, as built" section is now closed out.** `POST …/close`
  now transitions `open → closing` (not `closed` directly); a second call
  path (`POST …/close/cancel` and the turn's own finalize step) moves
  `closing → closed` or `closing → open`. The `closing` state and the status
  columns, landed nullable at Stage 2, get their first real readers/writers.
- **Reopen now performs its stated effect** — `Chapter.summary_status` and
  `ChapterNoteChangeset.status` both set to `stale` on `closed → open`
  (US-055.AC-1), closing the gap this file left for it.
- Reason: `docs/plans/016.chapter-close-continuity/`, decisions D3–D5.

## `docs/architecture/assistant-runtime.md`

- **New tool set: the close-chapter tools** (`services/close_tools.py`) —
  `draft_chapter_summary`, `draft_chapter_notes`, `propose_active_notes`,
  `raise_check_flag`, `read_continuity_context`. Same shape as feature 015's
  chapter tools: context-bearing, mode-gated, registered in `TOOL_REGISTRY`,
  shipped unreachable until an admin assigns them to `close-chapter`.
- **`ToolContext` gains a sixth field**, `active_notes_proposal: str | None`,
  mutable in place — the mechanism behind D7's "proposal held in-memory,
  written only at finalize."
- **The post-turn finalize hook** — `services/chat_turn.py` calls
  `chapters.finalize_close_turn` once a close-chapter turn's generator
  reaches natural completion (a `done` or an `error` frame), skipped on
  cancellation. `run_turn`'s own signature is unchanged; this is a new
  interior call, not a new turn-runner.
- Reason: `docs/plans/016.chapter-close-continuity/`, decisions D1, D5, D7.

## `docs/architecture/quick-reference.md`

- **New endpoints** — `GET`/`PUT /api/books/{book_id}/state-notes`,
  `GET /api/books/{book_id}/continuity`,
  `GET /api/books/{book_id}/chapters/{chapter_id}/notes`,
  `GET`/`POST /api/books/{book_id}/chapters/{chapter_id}/flags`,
  `POST .../flags/{flag_id}/resolve`,
  `POST /api/books/{book_id}/chapters/{chapter_id}/close/cancel`.
- **New DTOs** — `BookStateNotesResponse`, `UpdateBookStateNotesRequest`,
  `ChapterNoteChangesetResponse`, `ChapterContinuityResponse`,
  `BookContinuityResponse`, `FlagResponse`, `FlagListResponse`,
  `RaiseFlagRequest`. **`ChapterResponse`** gains `summary` / `summary_status`.
- **Extended taxonomies** — `ContinuityErrorReason`, `FlagErrorReason` (new
  enums, this feature's own); no new `ChapterErrorReason` member was needed
  (`close_chapter`/`cancel_close` reuse `chapter_not_open`).
- **Three new `Capability` rows** — `raise_flag` {owner, co_author},
  `resolve_flag` {owner}, `edit_state_notes` {owner, co_author}.
- Reason: `docs/plans/016.chapter-close-continuity/`, the Interface section.

## `docs/architecture/authorization.md`

- **The three new capability rows land in code** — the "Members-only
  material" table's "Raise a flag" / "Resolve a flag" rows and the "Edit
  state notes" row gain the `Capability` enum members backing them, matching
  the pattern feature 013 and feature 015 used for their own matrix rows.
- **Viewing continuity data (state notes, a chapter's changeset, its
  summary, its flag list) is gated by plain membership, not a new
  capability** — recorded as a deliberate choice (design-note D9), consistent
  with the matrix's existing habit of layering non-role rules (mode,
  archived-book) outside the matrix rather than widening it further.
- Reason: `docs/plans/016.chapter-close-continuity/`, decision D9.

## `docs/architecture/frontend-workspace.md`

- **`BookStatePage`'s two stubs are filled** — "State notes" becomes the live
  set, viewable and editable per collaboration mode; "Per-chapter continuity"
  becomes title + summary + changeset + active warnings per chapter
  (US-106.AC-2/AC-3).
- **`ChapterPage` gains a Warnings section** (list, raise, resolve) and, for
  a closed chapter, read-only summary + changeset. The existing `close`
  transition control gains a confirmation dialog and becomes the close-
  procedure trigger; the verbatim `closing` placeholder sentence is replaced
  by an in-progress view plus the cancel control.
- **The settings-side mirror (`frontend/src/user/`) is deliberately not
  built** — out of scope, the working-page surfaces satisfy UC-089/UC-051.
- Reason: `docs/plans/016.chapter-close-continuity/`, decision D8.

## `docs/architecture/frontend-work-drafts.md`

- **A fifth module-tier sibling**: `closeTurn.ts` — a registration idiom
  identical in shape to `contentSubject.ts`'s canvas-target registry, applied
  to "post a turn" instead of "apply a draft." Recorded alongside the
  existing four (`restoreBuffer.ts`, `activeChat.ts`, `contentSubject.ts`,
  `chapterUndo.ts`) per this file's own "sanctioned on purpose, not by
  precedent" convention.
- **None of this feature's new surfaces enter the restore buffer** — state
  notes, summaries, changesets and warnings are all short round-trips with
  no version token comparable to a chapter body's, matching the sanctioned-
  exclusion shape this file already uses for the system prompt and the
  chapter sketch.
- Reason: `docs/plans/016.chapter-close-continuity/`, the Interface section.

## Observations

- `run_turn` now has a **post-turn deterministic step** — the first thing that
  runs after the tool loop and *before* the terminal frame is yielded, so a
  client disconnect mid-stream skips it while a `done` and an `error` ending
  both reach it. Possible impact: add to `docs/architecture/assistant-runtime.md`
  under the turn's lifecycle, beside the five SSE frames — the frame vocabulary
  is unchanged but the turn is no longer "stream, persist, done".
- That step is **gated on the caller holding `Capability.set_chapter_state`**, not
  only on the turn's mode. Mode determination is per-subject, so a co-author's own
  chat also resolves to `close-chapter` while somebody else's chapter is
  `closing`; without the gate their ordinary turn would finalize — and therefore
  discard — the owner's in-flight close run. The plan's risk list names this
  hazard only for the close *tools* (closed by their fourth refusal rule); the
  same hazard exists one layer up. Possible impact: state the rule once in
  `assistant-runtime.md` — "a per-subject mode is not a claim of ownership" — so
  the next mode-scoped post-turn hook inherits it rather than rediscovering it.
- `ChatPaneState` holds **no book id** and the shell remounts the pane per book
  (`key={bookId}`), so any pane-level predicate stated as "does X's book match the
  pane's" has nothing to compare against. Possible impact: note in
  `docs/architecture/frontend-workspace.md` that the pane is book-scoped by
  remount, not by a stored id, so future specs state such predicates as
  "is X active at all".

---
Status: Applied 2026-07-31
Applied items: 10
Rejected items: 0 (2 sections out of scope — notes below)

Notes:

- **Applied as written**, one section each into `domain-continuity.md`,
  `domain-chapter.md`, `assistant-runtime.md`, `quick-reference.md`,
  `authorization.md`, `frontend-workspace.md` and `frontend-work-drafts.md`,
  plus all three `## Observations`.
- **Applied with modification:** the seven doc sections above also required
  correcting stale prose this file did not name — the continuity-status
  transition table, the two-writers passage, the "approval gate" sentence
  under Summaries, the chapter state-machine diagram and its `closing`
  reasoning, the `015` close-seam prediction, and CF1's "continuity gate"
  phrase. Each said something the delivered design contradicts.
- **Not applied — out of scope, routed elsewhere, not rejected:** the
  `roadmap.md` / `brief.md` section (`/roadmap`'s) and the `docs/product/`
  section (already applied by `/product-spec`'s finalization of 2026-07-31;
  `docs/architecture/` never edits `docs/product/`).
- **Applied beyond this file, from the finalization briefing:** the round-6
  `flag` → "warning" vocabulary split was **reversed by product on
  2026-07-31** and the reversal is recorded in `domain-continuity.md` and
  `frontend-workspace.md`; `Realizes:` headers dropped UC-048 / US-050 /
  US-051 / UC-066; `domain-model.md` gained divergence item 6 and closed
  item 5.
