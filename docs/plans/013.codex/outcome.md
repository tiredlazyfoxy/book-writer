# 013.codex — intended documentation changes

Written by the planner; applied by the architect at finalization. Grouped by target architecture
file. The coder appends `## Observations` at the bottom.

---

## `docs/architecture/assistant-config.md`

### 1. The runtime slice is now built — record where it lives

- **Section:** "Runtime consumption — the FEAT-020 slice" (the paragraph that says "exact runtime
  module boundaries are the planner's to finalise").
- **Change:** Record the as-built modules: `services/assistant_runtime.py` (mode determination, mode
  prompt lookup, tool allowlist resolution), `services/subagent_delegation.py` (synthetic tools and
  the nested loop), `services/codex_tools.py` (the first mode-gated tools), with
  `services/chat_turn.py` as the single call site that composes them. Note that the runtime reads the
  five FEAT-020 `db/` modules **directly** and never touches `services/assistant_config.py`, so it
  carries no dependency on feature `012.assistant-config-editor`.
- **Reason:** The doc left the boundaries open; they are now real and are what `015`/`016` will
  extend.

### 2. Mode determination — record the wire shape it derives from

- **Section:** "Mode determination — from the workspace activity".
- **Change:** Record that the workspace activity reaches the backend as **three optional fields on
  `TurnRequest`** — `subject_kind`, `subject_id`, `codex_kind` — and why `codex_kind` exists at all:
  UC-076 opens a *blank* entry with no row, so the kind cannot be read off a row and mode
  determination would otherwise be impossible for the exact case FEAT-018 is about. For an existing
  entry the row's `kind` wins and the request's `codex_kind` is ignored. Record also that a
  `subject_id` naming an entry in another book resolves to **no subject**, so mode determination
  cannot be used as a cross-book read.
- **Reason:** The doc describes the mapping but not how the runtime learns the subject; the blank-entry
  case is a genuine design constraint, not an implementation detail.

### 3. Tool gating — the null-mode rule, and the seam is closed

- **Section:** "Tool gating" (and the matching note `012.assistant-config-editor`'s outcome adds
  there).
- **Change:** Record the settled rule as three cases, not two:
  - a mode-bearing subject gets **exactly its `mode_tool` rows** — zero rows is an empty allowlist
    (`012.assistant-config-editor`'s settled rule, unchanged);
  - a subject with **no mode** (book state, any list, the chats view) gets a code-defined
    **`BASE_TOOL_NAMES`**, holding `web_search` as shipped;
  - `services/tools.py:resolve_tools`'s `None ⇒ whole registry` branch is **no longer reached by the
    turn** — `011.chat-panel`'s seam is closed by this feature, as `011.chat-panel`'s `outcome.md`
    item 6 and `012.assistant-config-editor`'s item 2 both predicted.

  Carry the reasoning: without a base allowlist, wiring gating would have silently stripped web
  search from the chats view feature `011.chat-panel` shipped, since a null mode would then mean "no
  tools". This is a **new decision made during this plan**, not previously in the doc.
- **Reason:** Two features already point at this seam from opposite sides; the third case is the one
  neither of them named, and it changes what "unconfigured" means at runtime.

### 4. Sub-agent delegation — as built, plus the planner's cache decision

- **Section:** "Sub-agent delegation" and "Model resolution → Planner note".
- **Change:** Record the as-built shape: synthetic tools derived one per non-disabled sub-agent of the
  mode, names **derived and sanitised** from `SubAgent.name` (not stored), with a **collision guard**
  against real registry names and against each other (skip-and-log, the real tool always wins); the
  nested `chat_with_tools` receives the sub-agent's `system_prompt` alone, its `subagent_tool`
  allowlist only, and its own `max_loops` constant, separate from `chat_turn.MAX_LOOPS`. Resolve the
  doc's open planner note: **clients are constructed per delegation, not cached**, because `LLMClient`
  must be entered as `async with` and has no standalone `close()`, so a cache would have to own client
  lifetimes across a whole turn — real bookkeeping for a call bounded by `max_loops`.
- **Reason:** The doc explicitly hands the cache question to the planner and asks for the answer back.

### 5. The `chat_with_tools` seam survives — with the canvas exception recorded

- **Section:** "The tool / function-call protocol — built on `chat_with_tools`".
- **Change:** Record that the shared-canvas write **did not** force the manual-loop swap the doc
  anticipated. The tool emits its frame onto the queue `run_turn` already pumps, so per-step
  visibility was not needed. State the accepted consequence: **the draft arrives whole, not
  streamed**, because `chat_with_tools` hands a tool its arguments only after the model finishes
  emitting them. Token-level canvas streaming remains the later manual-loop swap, and the seam is
  still replaceable.
- **Reason:** The doc predicts the swap would be needed for exactly this feature; it was not, and the
  reason it was not is the design's load-bearing part.

### 6. The `canvas` frame joins the event vocabulary

- **Section:** a new subsection beside the protocol section, or wherever the frame vocabulary is
  recorded once `011.chat-panel`'s outcome item 21 is applied.
- **Change:** Record `canvas` as the fifth SSE frame — `CanvasFrame(subject_kind, subject_id, field,
  text)` — and the two properties that make it safe: the tool **touches no database**, and
  `routes/chats.py`'s serializer is generic over the event name so no route changed. Note that `field`
  exists because a character entry has both a `name` and a `body`.
- **Reason:** `011.chat-panel` recorded four frames as "a floor, not the design"; this is the first
  widening and should not be re-derived.

## `docs/architecture/domain-chat.md`

### 7. The shared-canvas write protocol narrows the deferred boundary

- **Section:** "Assistant subsystem — one slice now designed, the rest deferred" → *Still deferred*.
- **Change:** Move **the shared-canvas write protocol for codex entries** out of the deferred list and
  record the design: the turn carries the content-pane subject; a mode-gated `write_codex_draft` tool
  validates editability server-side, emits one `canvas` frame, and persists **nothing**; the frontend
  applies it through a module-level target registry with the restore buffer as the fallback; the save
  path is unchanged UC-069/UC-070. State plainly what is **still** deferred: the same protocol for
  **chapters** (UC-055, `015`), token-level streaming, context assembly, and token budgeting.
- **Reason:** The doc's boundary paragraph is the index of what is undesigned; leaving the codex half
  in it after this ships would be wrong, and moving the whole item out would be wronger.

### 8. There is no chat → codex write path, by construction

- **Section:** the same boundary section, or beside the privacy rule.
- **Change:** Record that US-086.AC-2 / US-087.AC-2 / US-088.AC-2 hold **by construction, not by a
  check**: no code path exists from a chat turn to the `codex_entries` table. The canvas tool reads
  the resolved subject and writes a frame; the only writer is the ordinary codex route the author
  calls on save.
- **Reason:** "Nothing persists until saved" is normally an assertion about a check; here it is a
  structural property and that is worth more than the check would be.

## `docs/architecture/retrieval.md`

### 9. As-built chunker parameters

- **Section:** "Chunking" (the paragraph that declines to pin numbers).
- **Change:** Keep the reasoning and add the as-built values for the codex chunker: **chunk size 1200
  characters, overlap 200 characters, single-chunk threshold equal to the chunk size**, with the name
  prefix included in the size budget. Record them as *tuning parameters set at the chunker*, named
  module constants, adjustable without touching anything else — not as architecture.
- **Reason:** The doc's rule is right and should survive; a reader still needs to know what the first
  corpus actually chose.

### 10. The widened registry entry's as-built shape

- **Section:** "Registry — widening the feature-007 seam".
- **Change:** Record the concrete entry shape as built — `source_kind` discriminator, model class, row
  selector (in `db/codex_entries.py`, returning non-archived entries across all books, ordered by id
  for determinism), and chunker — and that `VECTOR_SOURCE_REGISTRY` now holds exactly one entry,
  `codex_entry`. Record that feature `008.data-domain`'s guard test asserting codex's **absence** from
  the registry was superseded by its inverse in the same change.
- **Reason:** The doc designs the widening; this pins what the first entry looks like for the chapter
  corpora that follow.

### 11. The search surface, narrowed at the layer boundary

- **Section:** "Query surface" and the placement paragraph beneath it.
- **Change:** Record that the db-level function is `search(book_id, query_vector, kinds, limit)` — a
  **query vector**, not a query text — because `db/` may not embed, and that a service
  (`services/codex_tools.py` for UC-078) composes `services/embedding.py` with it. Record the sidecar
  helper set as built: `upsert_chunks` (delete-then-insert for one source), `delete_by_source`,
  `delete_by_book`, `search`, plus a table-dimension accessor.
- **Reason:** The doc's written signature cannot exist as written under the layer rule; the narrowing
  is deliberate and should not read as drift.

### 12. The embedder is injected into `db/vector.py`, not imported

- **Section:** the placement paragraph under "Query surface", or beside "Full rebuild".
- **Change:** Record that `init_vector` now receives the batch embedder and dimension probe as
  **injected callables from `app/main.py`** (the composition root), because `rebuild_index` must embed,
  `db → services` is forbidden, and one of `rebuild_index`'s two callers
  (`db/import_export_queries.py:run_vector_rebuild`) itself lives in `db/`. Both existing
  `rebuild_index()` call sites kept their signatures. Record also that `run_vector_rebuild` now
  **logs and swallows** a rebuild failure, so importing a database into an instance with no embedding
  provider still completes — the deliberate gate bypass now has a matching failure contract.
- **Reason:** A layer-rule workaround at the composition root is exactly the kind of thing that reads
  as a violation unless the reasoning is written down once.

### 13. Incremental maintenance as built

- **Section:** "Incremental maintenance — new at Stage 2".
- **Change:** Record `services/codex_index.py` as the composer, its **never-raise** contract (every
  failure logged, the author's save always succeeds), that the call is awaited **inside the request**
  after the SQLite commit with no task and no queue, and that the archive drop-operation is exposed
  here for `017.codex-archive-restore` rather than re-derived there.
- **Reason:** The doc states the policy; the module that owns it and the contract it exposes to the
  next feature are the parts a reader needs.

## `docs/architecture/domain-codex.md`

### 14. Version rows are written by feature 013, not 019

- **Section:** "CodexEntryVersion" (the sentence "drawn now but first *built* at Stage 5").
- **Change:** Correct it: the **version rows are written by this feature's codex service** — every
  edit writes one carrying the prior `name` / `body` / `kind`, with a 1-based `generation` and
  `author_id` set to the editing user, and `CodexEntry.modified_by` set alongside. `019.codex-history`
  builds the **view and restore endpoints** on top of data that already exists. Record that **no
  version row is written on create**, so an entry never edited has no history.
- **Reason:** The model docstrings already assign this to "the feature-013 service"; the design doc
  says Stage 5, and the two disagree. This resolves it in the direction the code already assumes.

### 15. Optimistic concurrency on `modified_at`

- **Section:** a new short subsection beside "CodexEntry", mirroring `domain-chapter.md` →
  "Concurrency".
- **Change:** Record that a codex edit carries the expected `modified_at` and a mismatch is refused
  with **409**, that `modified_at` is therefore the entry's version token, and that it is the same
  value the frontend restore buffer stores as its `baseVersion`. Note the client contract: a 409
  becomes the reconciliation view, never an auto-merge.
- **Reason:** `domain-codex.md` has no concurrency section at all, yet the buffer design in
  `frontend-workspace.md` depends on this field being a version token.

### 16. Collaboration mode — free only, and why

- **Section:** "Collaboration mode applies (US-079)".
- **Change:** Record that this feature implements **free mode only**: an owner's write always applies;
  a **co-author's** create or edit in a `proposal`-mode book is **refused with 403** and a typed
  reason naming FEAT-010 as unbuilt. Carry the reasoning: FEAT-010 has no proposal entity and no
  review surface, and applying the write anyway would silently violate US-079.AC-2. The doc's own note
  — that FEAT-010's `_TBD:` records only *block* proposals having a use case today — is the same gap
  seen from the other side.
- **Reason:** A refusal that looks like a bug from the outside must be recorded as a decision with an
  owner.

## `docs/architecture/authorization.md`

### 17. The codex capabilities, as built

- **Section:** "Members-only material — codex, notes, summaries, flags".
- **Change:** Record the two `Capability` members added and their matrix rows (browse/search: owner ✓,
  co-author ✓, reader —, none —; create/edit: the same set of roles), and that the `(mode)` qualifier
  in the co-author cell is **not expressible in `_CAPABILITY_MATRIX`** — it maps capability → role set
  and has no vocabulary for the book's collaboration mode, so the mode rule lives in
  `services/codex.py`, the same layering `011.chat-panel` used for chat row-ownership. Record the
  status codes the codex routes produce: **404** for a non-member of a private book (existence hiding,
  all four routes), **403** for a reader of a public book and for the proposal-mode refusal, **409**
  for a stale `modified_at`, **400** for a kind/name violation or an archived-entry edit. Note that
  archive (UC-072) is **not** added here — it is `017.codex-archive-restore`'s.
- **Reason:** The matrix rows exist on paper with no code behind them; the enforcement point and the
  status taxonomy are what later codex features will copy.

## `docs/architecture/frontend-workspace.md`

### 18. The content pane has its first real pages

- **Section:** "Content pane — subject and editability", and the working-page diagram's note that the
  pane holds "a LIST — or — an ITEM".
- **Change:** Record the as-built pages: one parameterized `CodexListPage` serving `/characters`,
  `/locations` and `/facts` (kind fixed by the route), and `CodexEntryPage` serving `/codex/:id`. Note
  that the pane remains `<AppShell.Main><Outlet/></AppShell.Main>` — no content-pane state class was
  introduced; each page owns its own state, per the page-is-a-route rule.
- **Reason:** The doc describes the pane abstractly; this is the first concrete realization and the
  pattern chapters will follow.

### 19. A new route: the blank codex entry

- **Section:** Route map → Working page.
- **Change:** Add `/work/:bookId/codex/new?kind=<character|location|fact>` to the table, with the
  reasoning: UC-076 requires a blank entry of a chosen kind to be openable before any row exists, and
  `/codex/:id` cannot express "no id yet". The kind rides in a query param because it is view state
  chosen at navigation time, and the route stays deep-linkable.
- **Reason:** The route table is the index of the working page's surface; a route absent from it will
  be re-invented differently.

### 20. Query params — the repo's first use, and the rule held

- **Section:** the paragraph beginning "Query params keep their existing job inside this page".
- **Change:** Record that this feature is the **first consumer of query params anywhere in the
  frontend** (there were zero uses of `useSearchParams` / `URLSearchParams` before it), that the codex
  list's search needle is the first such param, and that `frontend.md`:192's rule was honoured — the
  query string is written in the submit handler and read once on mount, never watched by a
  `useEffect`.
- **Reason:** A rule with no precedent gets its first worked example here; the next list surface should
  copy it rather than re-litigate it.

### 21. The restore buffer's codex realization

- **Section:** "Draft-until-saved and the restore buffer" and "Returning to a stale buffer".
- **Change:** Record that a codex entry's `baseVersion` is its **`modified_at` ISO string**, that
  `BufferedDraft.draft` holds the **body only** (the name is small, always visible, and not buffered —
  `restoreBuffer.ts`'s single-string shape was not widened), and that the reconciliation view is
  reached from **two** directions: a 409 on save, and a base-version mismatch detected at load before
  any save is attempted. Record that the `saved-after-eviction` result is surfaced to the author.
- **Reason:** The doc designs the buffer generically; the first item type pins the concrete answers,
  and the load-time reconciliation path is not obvious from the doc's save-centred wording.

### 22. The canvas target registry joins the module tier

- **Section:** "Where the buffer lives in the state ladder" / "The active-chat pointer lives in the
  same module tier".
- **Change:** Add `src/work/contentSubject.ts` as the third module-tier member beside
  `restoreBuffer.ts` and `activeChat.ts`: plain functions, not a reactive store, holding the current
  `LoadedSubject` and the open entry's apply-draft callback. Record what it exists to avoid — React
  context, a cross-page callback and a custom `useX` hook, all three banned — and its fallback rule:

  a canvas frame with no registered target is written into the restore buffer, so returning to the
  entry surfaces it through the path that already exists. Record that `ChatPaneState` gained **no**
  subject field: it reads the registry at send time.
- **Reason:** A third exception to the state ladder needs the same explicit sanction the first two got.

### 23. `subject.ts` is finally wired, and its open note is closed

- **Section:** Content pane — subject and editability.
- **Change:** Record that `src/work/subject.ts` — written by `010.working-page` and until now imported
  only by `restoreBuffer.ts` — is now the live subject model: `resolveEditability` drives the entry
  page's read-only banner, and `LoadedSubject` is what the registry holds and what the turn request is
  built from. Close its in-code note at line 141 ("the free/proposal collaboration-mode nuance is
  `013.codex`'s to apply"): the nuance is applied **server-side** — a co-author's write in a
  proposal-mode book is refused with 403 — so `subject.ts` needed no change, and the assistant and the
  author are refused by the same rule at the same place, which is what the symmetry requirement asked
  for.
- **Reason:** A file written for a future feature and then satisfied differently should say so, or the
  note reads as unfinished work forever.

## `docs/architecture/backend/features.md`

### 24. The codex route family, as shipped

- **Section:** a new top-level section beside "LLM server connections" and "Database consistency &
  management".
- **Change:** Record the codex subsystem as shipped: the layers it spans
  (`db/{codex_entries,codex_entry_versions}.py`, `services/codex.py`, `services/codex_index.py`,
  `models/schemas/codex.py`, `routes/codex.py`), the four endpoints (`GET` / `POST`
  `/api/books/{book_id}/codex`, `GET` / `PUT` `/api/books/{book_id}/codex/{entry_id}`), the
  error→status taxonomy (400 / 403 / 404 / 409), and the deliberate absences: **no DELETE** (archive,
  not delete — and archive itself is `017.codex-archive-restore`'s), **no history endpoints**
  (`019.codex-history`'s, though the rows are written here), and **no cross-book copy**. Cross-link
  `domain-codex.md` and `retrieval.md` rather than duplicating them.
- **Change (second entry):** Record the retrieval subsystem as shipped — `services/embedding.py` and
  the widened `db/vector.py` — closing the "bridge deferred to the first vector-backed domain model"
  note feature `007` left in this file.
- **Reason:** This file is the route/DTO inventory of shipped backend features; the codex is the
  fifth family and the first with a 409 outside user administration.

## Follow-ups that are NOT architecture's

- **`docs/product/features.md`** — the
  `**Delivered:** docs/plans/013.codex/ (YYYY-MM-DD)` markers for FEAT-017 (core), FEAT-018 and the
  FEAT-020 runtime half are **`/product-spec`'s to write**, per `docs/product/CLAUDE.md` →
  "Citation convention". Do not add them from the architecture or planning side.
- **US-079.AC-2 is knowingly unmet.** In proposal mode, a co-author's codex create or edit is
  **refused**, not held as a proposal, because FEAT-010 has no proposal entity and no review surface
  (roadmapped 021+). This is a deliberate decision recorded in `context.md` decision 3 and enforced by
  a typed 403. Surfacing the gap in `docs/product/` — as a status note on US-079, or as an
  implementation-state annotation — is **`/product-spec`'s**, not architecture's. Architecture records
  it as decision history (item 16 above); product records that the criterion is not yet satisfied.
- **UC-078's relevance `_TBD:` stays open** (challenge C27). This feature ships **pull-only** codex
  search with a result limit and **no score threshold**, deliberately, so the product question is not
  closed by a design choice. Nothing for `/product-spec` to do unless the user decides a criterion.

---

## Observations

- Step 005: item 9's "with the name prefix included in the size budget" is true of the **split**
  path only, as built. The single-chunk threshold is measured on the entry's **body** (DoD-8's
  wording), so a 1200-character body with a name is one chunk slightly over 1200 characters; once a
  body does overflow, the prefix comes out of the first window's budget and every chunk is within
  `CHUNK_SIZE_CHARS`. Possible impact: word `retrieval.md` → "Chunking" as "the threshold is
  measured on the body; the prefix is charged to the first window when a body is split".
- Step 005: the overlap as built is **paragraph-aligned**: a window opens with the shortest run of
  whole trailing paragraphs of the previous window that reaches ~`CHUNK_OVERLAP_CHARS`, so the
  configured overlap is a target, not an exact figure, and every chunk consists only of complete
  paragraphs. A body whose paragraphs each exceed half a window gets no overlap (it cannot have any
  without breaking the size bound), and a single paragraph longer than a whole window is still cut
  mid-paragraph. Possible impact: `retrieval.md` → "Chunking" should say the paragraph boundary is
  the rule and the overlap is the tuning quantity, rather than implying an exact character overlap.
- Step 005: the name prefix as built lands on the **first chunk only** of a split body — repeating it
  on every chunk would put text that is not in the body into every window. Consequence for
  retrieval: a name-only query reaches a long entry through its first chunk only. Possible impact:
  one clause in `retrieval.md` → "Chunking" so a later corpus chunker copies the same rule.
- Step 006: `retrieval.md` → "Failure modes" row 3 says a dimension mismatch on an incremental write
  is "refused with a typed error". As built the incremental path **never raises**: every failure
  (no provider, unreachable, dimension mismatch, sidecar error) is a typed *return value*
  (`services/codex_index.py:IndexOutcome`), logged at warning level, because the caller is
  `services/codex.py`'s save path, which must not see an exception at all. Possible impact: reword
  that row as "the write is refused and reported as a typed outcome; a full rebuild is required",
  so the never-raise contract reads as design rather than as leniency.
- Step 006: the incremental path's mis-sized-embed-batch guard reports **`unreachable`**, mirroring
  the rebuild path's refusal to `zip`-truncate a short batch. Possible impact: if `retrieval.md` →
  "Chunking" gains a line about positional pairing, it can say both maintenance paths refuse a batch
  whose vector count disagrees with its chunk count, rather than pairing what they got.
- Step 008: `assistant-config.md` → "Model resolution" defines only the two *happy* cases (a set
  assignment, and inherit-main for a null one). It says nothing about a sub-agent whose assigned
  `LlmServer` has been deleted, deactivated, or carries an unresolvable `$ENV` key. As built the
  delegation **does not silently fall back to the parent's model** in those cases — it returns a
  short error string to the parent loop, because a sub-agent explicitly assigned a model is not the
  same worker when run on someone else's. Possible impact: one clause under "Model resolution"
  recording "a set-but-unusable assignment is a delegation failure, not an inherit-main fallback".
- Step 005: `retrieval.md` → "Failure modes" has no row for the post-import rebuild. As built,
  `db/import_export_queries.py:run_vector_rebuild` logs and swallows **every** rebuild failure (no
  designated provider, an unreachable one, a sidecar error) so an import into an instance with no
  embedding provider still completes, leaving the index empty until an admin rebuild. Possible
  impact: add that row beside the existing "No embedding server designated" one.
- Step 009: `retrieval.md` says a hit "carries its `source_id` so a consumer can load the
  authoritative row rather than trusting the indexed copy", but names no rule for the case where that
  load comes back **empty or archived** — the visible face of a stale index. As built,
  `services/codex_tools.py:codex_search` **drops** such a hit (it has no kind or name to render, and
  the read tool refuses exactly those entries, so the two tools present one world), and a search whose
  every hit is stale returns the ordinary "nothing found" string rather than an error. Possible
  impact: one clause under "Query surface" or "Failure modes" — "a hit whose source row is gone or
  archived is dropped by the consumer; an all-stale result is *no results*, not a failure".
- Step 010: `frontend-workspace.md`'s content-pane editability table now has a **second**
  implementation — `services/codex_tools.py:_refuse_write`, the assistant's server-side mirror of
  `frontend/src/work/subject.ts:checkWritePermission` — and its refusals are **tool strings, not HTTP
  statuses**: the assistant's canvas write is refused with a message the model reads, while the
  author's save is refused with the 403 / 400 / 409 taxonomy `services/codex.py` owns. Item 23 above
  records the collaboration-mode nuance as "applied server-side with a 403", which is true of the
  save path only. Possible impact: extend the "a read-only subject refuses the author and the
  assistant alike" paragraph to say **where** each refusal lives and that the two speak different
  languages by design (a status for the author, a string for the model — a raising tool would abort
  the turn).
- Step 011: `frontend.md`:192 states the query-param *rule* but names no mechanism, and the enforced
  MobX split (all effects are external `(state, args, signal)` functions) makes the obvious one
  illegal — the effect function cannot call `setSearchParams`, which is a React hook binding owned by
  the component. As built the seam is: the effect function **returns the new search string**
  (`"q=…"`, or `""` to drop the param) and the submit handler pushes it with `setSearchParams(...)`,
  so the commit-and-reload stays in the state layer and the URL write stays in the event handler.
  Possible impact: one clause under `frontend.md` → "Routes and pages", beside the rule, recording
  the returned-search-string convention so the next list surface copies it instead of reaching for a
  hook inside a state module. (Item 20 above records *that* the rule held; this records *how*.)
- Step 012: **the restore buffer holds the codex entry's BODY only.** `restoreBuffer.ts`'s
  `BufferedDraft.draft` is a single string, and a codex entry has two editable fields; the body is
  the substantive content the buffer exists to protect, while the name is small and always visible.
  `restoreBuffer.ts` was deliberately **not** widened to a `(name, body)` pair. Consequence: an
  unsaved *name* is lost on an unload, and the reconciliation view compares bodies only. Possible
  impact: one clause in `frontend-workspace.md` → "Keyed per item, not per pane" recording that a
  multi-field subject buffers its principal text field, so the chapter and book-state surfaces copy
  the rule rather than each inventing an encoding.
- Step 012: `frontend-workspace.md` → "Returning to a stale buffer" describes the divergence view as
  reached from a **save** refusal, but the client reaches it from **two** places: a 409 from Save,
  and a buffer whose `baseVersion` no longer matches the entry the page just loaded — the second
  detected **at load time, with no save attempted at all**. Both land in the same view. Possible
  impact: state both entrances in that section, since the load-time one is what makes "the author
  never overwrites silently" true for the author who simply comes back to the page.
- Step 013: the restore buffer now has a **second writer with no base version to record** — the canvas
  dispatcher. Every buffer written by the author's own keystrokes carries the `modified_at` the page
  loaded; a canvas frame that arrives with no registered target is written by a module that never
  loaded the entry, so it can only inherit the base version already at that key (and `""` when there
  is none). Since a codex row always has a non-null `modified_at`, an assistant draft buffered for an
  entry the author was *not* editing therefore reads as **stale on return by construction** and opens
  the divergence view rather than restoring silently — deliberate (`013.context.md`), but it means the
  divergence view is the *normal* landing for the navigated-away-mid-turn path, not an edge case.
  Possible impact: one clause in `frontend-workspace.md` → "Returning to a stale buffer", beside the
  two entrances the step-012 observation names, recording the writer-without-a-version case.
- Step 013: the assistant can draft **either** field, but the fallback buffer can hold only the body
  (step 012's observation above), so a `canvas` frame for the **name** that arrives with no registered
  target is **dropped**, not buffered — writing it would surface a name where the body belongs.
  Possible impact: if `frontend-workspace.md` records the "principal text field" buffering rule, state
  its corollary — a non-principal field written while the subject is not open is lost, which is a
  reason to keep the buffer's shape per-item rather than per-field only until a subject needs more.
