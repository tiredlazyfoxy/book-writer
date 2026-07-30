# 015.chapter-writing-free-mode — intended documentation changes

Written by the planner; applied by the architect at finalization. Grouped by target architecture file.
The coder appends `## Observations` at the bottom.

> **Read the sequencing warning at the bottom first.** Two earlier outcomes are unapplied and this one
> edits paragraphs both of them touch. The order is `021` → `014` → `015`.

---

## `docs/architecture/assistant-runtime.md`

### 1. The shared-canvas write protocol for **chapters** — no longer deferred

- **Section:** "Out of scope — still deferred" (the bullet *"The shared-canvas write protocol for
  chapters (UC-055) — the codex half shipped; the chapter half has not."*), and a new section beside
  "The shared-canvas write for codex, as built".
- **Change:** Remove the bullet and record the protocol as built:
  - **Four tools in `services/chapter_tools.py`** — a read path returning the chapter's **saved** body,
    and three writes: whole body, the author's current selection, and append-to-end. All four are
    **context-bearing** (bound from the per-turn `ToolContext`, `services/tools.py:93-139`), mode-gated,
    and registered in `TOOL_REGISTRY`.
  - **`CanvasFrame` (`models/schemas/chats.py:260-295`) gained an operation discriminator** — replace /
    append / replace-selection — **defaulted to replace**. Record that the default is what made the
    widening free: there is exactly **one** canvas emission in the codebase
    (`services/codex_tools.py:689-706`), it is unchanged, and **no codex file was edited at all**. On
    the client the registered apply-draft callback's **type** widened by one optional parameter, which a
    two-parameter implementation still satisfies, so `CodexEntryPage` was not modified either.
  - **`CanvasField` (`models/schemas/chats.py:257`) was deliberately NOT widened.** It stays
    `Literal["name", "body"]`: **a chapter's body is the `"body"` field** — the same principal text
    field a codex entry uses. Adding a `"text"` member would give one concept two names across two
    subjects. Record it, because it is the first thing a reader will expect to have changed.
  - Record the rejected alternative for the operation: encoding it into `field` as `"text.append"`,
    refused for the reason `domain-chapter.md` gives for storing placement as a discriminator plus
    columns — a discriminator keeps "which part is meaningful" answerable **without parsing**.
  - **`TurnRequest` (`models/schemas/chats.py:187-216`) gained an optional selection text** — a
    **fourth flat field** beside `subject_kind` / `subject_id` / `codex_kind`; there is no subject
    object on the request and none was introduced. **Text only, no offsets and no line numbers**, never
    persisted. Record why: only the finished body is saved, so a selection never has to survive a
    request; and `ChapterChange.line_from` / `line_to` deliberately never expresses it, because snapping
    character offsets onto line numbers is lossy in exactly the way the stale-change rule refuses.
    `ToolContext` gained the same text as a fifth field.
  - **The refusal mirror** — `chapter_tools.py`'s `_refuse_write` counterpart refuses a non-chapter
    subject, a chapter not in `open`, an **archived** book and a **co-author in proposal mode**, each as
    a **tool string**, never an exception. Record that the last two are **field reads off
    `ToolContext.access`**, which already carries `book_state`, `collaboration_mode` and `role` — the
    assistant-side mirrors of D10 and D11 needed no new plumbing. Add the chapter row to the
    two-implementations / two-vocabularies table this document and `frontend-workspace.md` share.
  - **The `chat_with_tools` seam survived again.** The chapter canvas write did not force a manual loop
    any more than the codex one did — the frame goes onto the queue `run_turn` already pumps
    (`chat_turn.py:493-494`). **The draft still arrives whole, not streamed**; token-level canvas
    streaming stays deferred.
  - **Accepted limitation to record plainly:** the assistant reads the **saved** body, not the author's
    draft. The draft is device-local and never leaves the browser until the author saves (US-107.AC-4),
    so after unsaved edits the model's view is stale. This is a consequence of draft-until-saved, not a
    gap.
  - **The tools ship unreachable, by design.** **No `mode_tool` rows were seeded**, so a registered
    chapter tool is invisible to every turn until an admin selects it for the `write-chapter` mode in
    the FEAT-020 editor. On a fresh install the chapter editor works and the assistant cannot write into
    it until then. Same stance `013.codex` took for the codex tools; changing it would be a FEAT-020
    default-policy decision and would point the default in the unsafe direction the empty-allowlist rule
    exists to avoid.
- **Reason:** This document lists the chapter protocol as undesigned in three places (here, `backend.md`
  and `docs/architecture/CLAUDE.md`). It is now designed and built, and a reader who trusts the
  "deferred" list will otherwise build a second one.

### 2. Mode determination gets its chapter branch — it genuinely had none

- **Section:** "Mode determination — from the workspace activity", the mapping table.
- **Change:** Record that the chapter rows of that table were **design only** until this feature.
  `determine_mode` (`services/assistant_runtime.py:195-218`) was, verbatim,
  `if subject.entry is None: return None` / `return _mode_for_codex_kind(subject.entry.kind)`, with
  `_CODEX_KIND_MODES` (`:104-108`) mapping only the three codex kinds — **no chapter handling existed**,
  and the function's own docstring assigned the two chapter modes to `015` / `016`.

  As built now: an `open` chapter subject resolves to **`write-chapter`**, a `closing` chapter to
  **`close-chapter`**, and a chapter in `planned` or `closed` resolves to **no mode** — therefore
  `BASE_TOOL_NAMES`, which is **exactly `("web_search",)`** (`:62`), not an empty allowlist. Record that
  `ResolvedSubject` gained a chapter member beside its `entry`, and that the early return had to move
  from "no codex entry" to "no subject at all" — the one change that could otherwise make the chapter
  branch unreachable while every codex test still passed.

  Record that the cross-book rule already stated for codex entries (*"a `subject_id` naming an entry in
  another book resolves to no subject"*) applies unchanged to chapters and is implemented by the same
  resolution step rather than by a second check.

  Record that **`allowed_tool_names` and `resolve_turn_tools` were not touched** — the three-case gating
  already handled everything once a mode key existed.
- **Reason:** The table read as as-built. Half of it was aspirational, and which half matters to the next
  feature that adds a mode-bearing subject.

### 2b. The five seeded modes are load-bearing for a silent failure

- **Section:** "Mode determination", as a short note; cross-reference `assistant-config.md`'s seeding
  section.
- **Change:** Record that `determine_mode` returning a mode **key with no `AssistantMode` row** fails
  **silently** — the mode-prompt lookup and the `mode_tool` lookup (`db/mode_tools.py:36-43`) both come
  back empty, the turn runs with base tools and no mode prompt, and nothing errors. The five rows are
  seeded by `seed_default_modes()` on both first-run paths and are idempotent by `key`, which is why the
  chapter branch could be added without any seeding work — but the coupling is worth naming, and this
  feature added a regression assertion that a freshly initialised database carries the `write-chapter`
  and `close-chapter` rows.
- **Reason:** A returned key and a stored row are two different things, and nothing currently connects
  them in prose. The next mode-bearing subject will hit the same silent path.

### 3. Layer 4 of the prompt composition is finally passed — and its caveat resolves

- **Section:** "System-prompt composition" → the **Layer 4 caveat** and the decision-history paragraph.
- **Change:** The caveat (*"`Chapter.system_prompt` now has nothing to append to … it is
  `014.chapter-skeleton`'s to answer"*) is answered and closed: 014 replaced the field's meaning with a
  **per-author `ChapterAuthorPrompt`** row and left the column dormant; **this feature passes that row
  as layer 4**, for turns whose subject is a chapter, read for **the chat's own author** through
  `db/chapter_author_prompts.py` directly — **no `BookAccess`**, the identical reasoning layer 3 already
  carries. Record that **`Chapter.system_prompt` is read by nothing, still.**

  Record the non-obvious part: **014's stated blocker was dissolved by 015's subject registration, not
  by designing context assembly.** 014 deferred composition because it needed "which chapter is this
  turn about"; 015 registers the open chapter as the content-pane subject, so the **turn request**
  answers it. **Context assembly itself remains undesigned and out of scope** — nothing about US-057 or
  UC-085/086/078 changed, and the "Out of scope — still deferred" entry for it stays.
- **Reason:** Two documents currently tell a reader that layer 4 is unpassable. It is passed, and the
  reason it became passable is a piece of design logic another feature will want to reuse.

## `docs/architecture/domain-chapter.md`

### 4. "All three steps are one transaction" is aspirational — record the divergence and the real ordering

- **Section:** "The one write path", the sentence *"All three steps are one transaction: a snapshot
  without an applied change, or an applied change without a snapshot, would break revert."*
- **Change:** Record that **as built there is no transaction**. `db/` is session-free with one module
  per entity and **no multi-table transaction primitive exists anywhere** in the codebase; the save
  therefore issues three ordered `db/` calls from `services/chapters.py`, exactly as
  `services/codex.py::update_entry` orders its version snapshot before its entry mutation. **No
  cross-entity `db/` module was created** — "one module per entity" was kept.

  Record the order and why it is the safest available: **`ChapterChange` → `ChapterTextRevision` →
  `Chapter`.** The change must precede the revision because `ChapterTextRevision.applied_change_id` is a
  **non-null FK**; the chapter update must come last because a body that has moved with no history
  behind it is the one failure that breaks revert irrecoverably. **History before mutation.**

  Record the accepted failure modes **precisely**, because the sentence being replaced names one that
  cannot happen: a crash after step 1 leaves an `applied` change with no revision and an **unmoved**
  body; a crash after step 2 leaves a change plus a no-op revision whose `text_before` equals the
  current body; **no ordering can leave a moved body with no history.** A "snapshot with no applied
  change" is impossible under the FK direction.

  Record the second, same-class limitation: the **version check and the write are not one transaction
  either**, so two saves racing on the same `expected_version` can both pass the check. The window is
  milliseconds and the exposure is identical to `services/codex.py`'s.
- **Reason:** The document asserts an atomicity guarantee the architecture cannot currently provide. A
  reader relying on it would design revert, variants (`018`) or proposal application (FEAT-010) on a
  promise that is not kept — and would look for a bug class that the FK makes unrepresentable.

### 5. The Stage-2 write path, as built — placement is computed, not chosen

- **Section:** "The one write path" and "ChapterChange — the unified write record".
- **Change:** Record what a free-mode save actually is as of this feature: **one `PUT` carrying the
  whole body plus `expected_version`**, and **one `ChapterChange` row per save whose placement is
  computed**:
  - `append` when the new body **starts with** the loaded body, with the appended remainder as the
    change's text and null line bounds;
  - `range` otherwise, with `line_from = 1`, `line_to = len(loaded_text.splitlines())`, and the whole
    new body as the change's text.

  Record the three degenerate cases and their fixed answers: an empty prior body is always an `append`
  carrying the whole body (the first write into a chapter); clearing a body to `""` is a `range` carrying
  `""`; an unchanged re-save is an `append` carrying `""` and still snapshots and bumps the version — no
  "unchanged" short-circuit was added, because one rule beats a special case and the client already
  gates on dirtiness.

  Record **why the placement is computed rather than transmitted**: the *two layers* decision — versioning
  is whole-body and happens on save; append-vs-replace is an **editing operation on the draft**, before
  any save, performed by the author typing or by the assistant's tools. This is what reconciles UC-038's
  "append a block" with UC-039 / US-041's "edit a body", and it is why **no partial or line-addressed
  write reaches HTTP at all**. Record that this makes `ChapterChange.status = pending` and `rejected`
  still unreached — FEAT-010's and `018`'s.

  Record that `base_version` is the client's `expected_version`, `status` is `applied` immediately in
  free mode, and **`author_id` is the caller — this is where US-040.AC-2's attribution lives.**
- **Reason:** `018` reads these rows back and FEAT-010 writes `pending` ones. What a Stage-2 row actually
  contains, and which fields are never populated yet, is the first thing either will need.

### 6. The close seam is now concrete, and US-040.AC-4's real scope

- **Section:** "State machine" (the note that Stage 2 ships an ungated close), and "Concurrency — the
  chapter version contract".
- **Change:** Record the seam as built: `POST …/close` requires `state == open` and writes **`closed`
  directly**; nothing reads or writes `closing`; no continuity is drafted and no approval is required.
  **016 changes exactly two things** — the destination becomes `closing`, and a second endpoint moves
  `closing → closed` after approval. Record what 015 built *now* so 016 does not retrofit it: every
  one-open-chapter guard already tests `state in {open, closing}` on **both** open and reopen; the
  body-write refusal already refuses a `closing` chapter; and `determine_mode` already maps a `closing`
  chapter to the seeded `close-chapter` mode. **US-038.AC-3 is cited by nothing in 015.**

  In "Concurrency", record how **US-040.AC-4** is actually satisfied: automatically, the system refuses
  the later save, shows the author the server's body against their draft, and lets a save re-issued
  against the current version land. **The merging is the author's** — reconciliation takes one side
  whole and there is no automatic merge at MVP. "Both members' blocks end up in the chapter" is
  therefore true of the flow, not of a merge algorithm, and the criterion should be read that way.
- **Reason:** The seam is the brief's one open question for the planner, and the AC-4 reading is the sort
  of thing a later reader will assume was implemented as an automatic merge because the criterion sounds
  like one.

## `docs/architecture/authorization.md`

### 7. **Closed:** an archived book refuses writes

- **Section:** "Not settled by this pass", the bullet *"Whether an archived book refuses writes"* —
  including its "Still open after feature `009.books`, deliberately" paragraph, which defers the answer
  to *"the write features (`010` / `014`), which are the first to have something to refuse."*
- **Change:** **Remove the bullet** and move the answer into "Book state and visibility gates". As
  built: **every body save and every state transition (open / close / reopen) is refused when
  `BookAccess.book_state` is `archived`; reads still work.** Record the status: **`403`**, with its own
  typed reason — not `409` — because this document places the book-state gate *before* the matrix,
  alongside visibility and quarantine, and defines `403` as "a book the caller can legitimately see, but
  a capability they lack"; under archive **no member holds the write capability**, which is an access
  answer, not a resource-state answer. Record the product basis: UC-023 says archive preserves content
  and is reversible, and refusing writes is what makes "preserved" mean something.

  Record that **no `Capability` member and no `_CAPABILITY_MATRIX` row was added for it** — the gate is a
  service-level check over `BookAccess.book_state`, the same layering the `(mode)` qualifier uses. Record
  that the **assistant is refused by the same rule in the other vocabulary**, reading
  `ToolContext.access.book_state` and returning a tool string. Correct the deferral's naming while you
  are there: it named `010` / `014` as the first write features; in fact **`014` writes no book
  *content*** (a skeleton row and a per-author prompt), and **`015` is the first feature that writes into
  a book's text.**
- **Reason:** The document names this as undecided and points at two features that turned out not to
  need it. It is now decided and implemented; leaving it listed invites a second, different answer.

### 8. The last two chapter matrix rows get an enum behind them

- **Section:** "Capability × role matrix" → "Chapters", and the "state-machine constraints, not
  authorization" note beneath it.
- **Change:** Record that this feature added the **two** remaining `Capability` members: **open / close /
  reopen a chapter (UC-035..037), owner only** — **one member for the one matrix row**, matching the
  1:1-with-the-matrix discipline 014 used — and **write into the open chapter (UC-038), owner and
  co-author**. Record that the **`(mode)` qualifier on the write row is layered in
  `services/chapters.py`**, not in the matrix, which is now the **third** feature to do so after
  `011.chat-panel` and `013.codex`; the pattern this document already calls "a pattern rather than a
  one-off" is now the house shape.

  Extend the state-machine note with the refusals this feature adds, all **`409` and not `403`** because
  the caller has the capability and the resource is in the wrong state: a body write to a chapter that is
  not `open`; a stale `expected_version`; opening a non-`planned` chapter; reopening a chapter that is
  not `closed`; closing a chapter that is not `open`; and **opening or reopening while any chapter is
  `open` or `closing`** — CF1's rule, applied to **both** transitions by the symmetry product's UC-035
  exception flow states.

  Record the status table the five new routes produce, mirroring the codex table already in this
  document: `401` no token; `404` for a private book with no relationship (produced by `book_access`,
  **not re-derived**) and for a chapter that does not exist or belongs to another book; `403` for a
  capability failure, for a reader, for the **proposal-mode co-author refusal naming FEAT-010**, and for
  the **archived-book refusal**; `409` for every state-machine and version refusal; `422` for a
  malformed body.
- **Reason:** The chapter matrix is now fully backed by code, and the `409`-vs-`403` split is exactly the
  thing a later feature would "fix" in the wrong direction if the reasoning is not pinned here.

## `docs/architecture/frontend-workspace.md`

### 9. The content-pane editability table gains the `open` chapter's body region

- **Section:** "Content pane — subject and editability", the row *"The book's **`open`** chapter |
  editable (US-097.AC-3)"*, which 014 has just made region-based for `planned`.
- **Change:** Make the `open` row region-explicit in the same vocabulary: the chapter's **body text** is
  editable and the caller's own chapter prompt stays editable; the **sketch is not** — UC-033 confines
  sketch edits to `planned`, which is the exact opposite window from the body. Record that `subject.ts`
  remains the **single enforcement point** and that `checkWritePermission` now **allows** a body write on
  `open` while still refusing one on `planned`, `closing` and `closed`, so the shared-canvas symmetry
  (US-097.AC-2, US-059.AC-3) is preserved with the assistant refused by the same rule as the author.

  Record that a **read-only** chapter body renders through **`react-markdown`**, not through a disabled
  editor: the heavy editor is mounted only when the chapter is `open`, which removes editable-toggling
  entirely and keeps the read path light. `react-markdown`'s **no-plugin default** was inherited, not
  re-decided.
- **Reason:** The table is enforced as one rule set; an editable region not in it is drift, and "the
  open chapter is editable" without a region is now ambiguous next to 014's partial `planned` row.

### 10. The Shell route table's last stale chapter claim

- **Section:** the Shell route map, `/books/:bookId` — *"Book hub — chapter skeleton (UC-031..034), open
  / close / reopen (UC-035..037)"*.
- **Change:** 014's item 7 already moves UC-031..034 off this row; finish it — **UC-035..037 are not on
  the Shell either.** Open, close and reopen live on the **working page's chapter item**
  (`/work/:bookId/chapter/:id`), one surface per action, per 014's "the Book hub READS, the working page
  EDITS". The Shell hub stays a read-only ordered chapter list. Record that the working-page
  `/chapter/:id` row now carries: the sketch editor (`planned`), the caller's own chapter prompt (all
  states), the **body editor** (`open`), the transition control, the divergence view, and the undo
  control.
- **Reason:** Two surfaces claiming one action is what the one-editing-surface rule exists to prevent,
  and this row is the last place still claiming it.

### 11. The chapter surfaces, as built

- **Section:** "The pane's first real pages (feature 013)" — extend it, or add a sibling.
- **Change:** Record that the chapter item page is the **second** editable subject and the **first with a
  numeric version token**, and that it carries **three** trios (chapter, its body, the caller's own
  prompt) plus three editable regions. Record the **remount-by-key** idiom it introduced for external
  draft writes (see item 16) and that it registers itself as a **writable** canvas target where 014
  registered it as a subject only.
- **Reason:** The next content-pane surface copies from here, and "three trios, no aggregation type" plus
  a version-token subject is a different template from the codex entry's.

## `docs/architecture/frontend-work-drafts.md`

### 12. The tier's **fourth** member, sanctioned on purpose

- **Section:** "The module tier — three members" (the table, and the sentence *"They are recorded
  together so a fourth is added on purpose rather than by precedent"*).
- **Change:** Add **`src/work/chapterUndo.ts`** as the fourth row — *"assistant-write undo snapshots per
  `(book, chapter)`, capped at 20"*, **persisted: in memory only**. Rename the section accordingly.
  Record both halves of the sanction:
  - **not `localStorage`** — 20 chapter bodies against a few-megabyte origin quota, competing with the
    restore buffer that already evicts and already reports eviction as data loss on other items. An undo
    stack that evicts someone's unsaved draft is strictly worse than one that does not survive a reload.
  - **assistant writes only** — ProseMirror ships a real history plugin, so the author's typing already
    has undo inside the editor; a second stack over the same keystrokes would give the author two undo
    affordances that disagree about what "one step back" means. A snapshot is pushed **before** each
    assistant-originated write is applied.
- **Reason:** The document asks for exactly this sanction, by name, before a fourth member exists.

### 13. Chapter bodies stop being "out of scope" — the buffer's declared consumer arrived

- **Section:** "Out of scope" (the bullet *"Chapter bodies. The buffer's design covers them
  (`BufferBaseVersion` carries the numeric `Chapter.version` for exactly this reason) but no chapter
  surface exists yet; `015.chapter-writing-free-mode` is the first, and it adopts this tier rather than
  extending it."*), plus "The codex realization (feature 013)".
- **Change:** Remove the bullet and add a **chapter realization** beside the codex one:
  - `baseVersion` is the **numeric `Chapter.version`** — the first writer of `BufferBaseVersion`'s number
    branch. It is taken from the **body response** and from nowhere else, so the version and the payload
    it qualifies always arrive together.
  - the key is `(bookId, "chapter", chapterId)`;
  - `BufferedDraft.draft` holds **the body only** — the principal-text-field rule, applied to a subject
    with **three** editable regions. Accepted consequences: an unsaved **sketch** is lost on an unload,
    and the divergence view **compares bodies only**;
  - **both entrances are implemented** — a `409` from save re-fetches into the conflict slot, and a
    load-time version mismatch opens the divergence view with **no save attempted**;
  - **reconciliation takes one side whole**, with the codex's exact sequencing: keeping the draft adopts
    the server's **version first**, then re-saves — getting that backwards produces an infinite 409 loop
    that reads as a server bug;
  - `saved-after-eviction` is surfaced with the evicted keys.
  - **`restoreBuffer.ts` was not modified.** The tier was adopted, exactly as the bullet predicted.
- **Reason:** The bullet names this feature as its resolver. Leaving it in "Out of scope" after it ships
  is the same failure mode as an open divergence that has been closed.

### 14. The canvas target registry is no longer codex-shaped

- **Section:** "The canvas target registry (feature 013)".
- **Change:** Record the generalization: `dispatchCanvasFrame` routes on the frame's **own
  `subject_kind`** instead of assuming `"codex-entry"` in its buffer key. **That literal was the only
  codex-specific thing that had to change** — the fallback's `"body"`-field condition stayed as it is,
  because `CanvasField` was not widened and a chapter's body **is** the `"body"` field. The applier's
  **type** gained a third optional parameter (the frame operation) and **every existing two-parameter
  applier still satisfies it**, so no codex code changed.

  Record the new fallback rule and its reasoning: with **no registered target**, a **whole-field replace**
  frame is still buffered under the subject's own key (inheriting whatever base version sits there, `""`
  when none), but an **append** or **replace-selection** frame is **dropped and logged** — both are
  relative to a draft the module does not have, and writing them at position zero would be a silent wrong
  placement in the author's own document. This is the same shape as the existing "a non-principal field
  written while the subject is not open is lost" rule.

  Record the **selection registry** added beside the subject registry: the open page sets the author's
  current selection, the chat pane reads it **at send time** and puts its text on the turn request as a
  **flat field** (the request has no subject object; the frontend-only `TurnSubject` helper gains
  nothing). **`ChatPaneState` gained no selection field**, exactly as it gained no subject field — the
  panes stay independent because nothing links them but a function call. The selection is **text only**
  and is never persisted.

  Record the **page-level** refusal that pairs with it: a replace-selection frame arriving when no
  selection is active is **not applied** and is reported to the author — never appended, never applied at
  position zero. The check lives on the page because the author can clear a selection while the model is
  writing, which the server cannot know.
- **Reason:** The registry is documented as a codex mechanism; it is now the general one, and its
  fallback rules are the part a third subject will get wrong.

## `docs/architecture/frontend.md`

### 15. `@mantine/tiptap` + `tiptap-markdown` join the stack, and chapter text is Markdown

- **Section:** the stack table, and the "Markdown rendering" note under SSE/streaming.
- **Change:** Add **`@mantine/tiptap`** over TipTap/ProseMirror plus **`tiptap-markdown`** — the second
  frontend runtime dependency decision in the project, after 014's `@dnd-kit`. Record:
  - **`Chapter.text` is Markdown.** Migration cost was zero — the column existed and nothing wrote it.
    **Markdown stops at chapter text**: the codex entry body is untouched and `CodexEntryPage` was not
    reworked.
  - **Why TipTap and not Milkdown.** TipTap is the dominant React rich-text editor and `@mantine/tiptap`
    inherits the app theme for free. Milkdown's exact-Markdown round-trip was the alternative and was
    rejected because its theming cost outweighs a round-trip whose **worst case is cosmetic** — the
    whole body is re-saved every time, so an imperfect slice round-trip cannot corrupt stored data, and
    the author sees the rendered result before saving.
  - **The TipTap major is pinned to `@mantine/tiptap`'s declared peer range** for the Mantine major in
    `package.json`, and `tiptap-markdown` to a release targeting that same major. Record it as a rule,
    not as a version string, because the range moves with Mantine.
  - The library's stylesheet is imported **from the component**, not from an entry `main.tsx`, so it
    ships with the only bundle that uses it. This is not a CSS-module/styled-component breach; it is a
    vendored stylesheet for a vendored widget.
  - `react-markdown` renders the **read-only** chapter body, still with **no plugins configured** —
    that default was inherited, not re-decided.
- **Reason:** A new runtime dependency and a new content format both need a recorded reason, and "why is
  the chapter Markdown but the codex not" is the first question a reader will have.

### 16. Two new conventions a heavy widget forced

- **Section:** "React hook rules" (the remount idiom) and "Testing" (the component mock).
- **Change:** Record both, because both will recur:
  1. **External writes into a controlled third-party editor are applied by remount, not by an effect.**
     The editor reads its initial content **once**; the page keys it on a counter bumped by every
     *external* draft write (assistant apply, undo, buffer restore, reconciliation) and never by a
     keystroke. This costs **zero** effects, zero `autorun`s and zero imperative refs — all of which
     `frontend.md` either forbids in leaf components or reserves for page level — and it is the same
     "force a fresh instance" idiom the router already uses with `key={id}`. Its one visible cost is a
     lost caret on an assistant write, which is arguably correct.
  2. **A heavy third-party widget is mocked in page specs the same way an `api/` module is.** ProseMirror
     needs DOM APIs jsdom does not implement (`Range.getClientRects`, real layout rectangles), so driving
     real typing and selection under Vitest would make every page spec flaky for reasons unrelated to the
     page. The editor therefore has a **frozen four-prop seam** (initial Markdown, change callback,
     selection callback, accessible label), the page specs substitute a trivial stub, and the editor's
     own behaviour — real Markdown round-trip, real selection, real theming — is covered by
     `[manual/live]` criteria. This is the same reasoning 014 used to leave `@dnd-kit`'s drag gesture
     manual: faking the library's callbacks would test the test.
  3. Record that **a library's own hooks (`useEditor`) are not a breach of the no-custom-`useX` rule** —
     the rule forbids authoring hooks, not consuming a library's API. 014 recorded the same reading for
     `@dnd-kit`; two features is a pattern.
- **Reason:** Both are non-obvious readings of existing rules, and the next feature to embed a
  third-party editor, canvas or chart will meet all three on day one.

## `docs/architecture/backend/features.md`

### 17. The chapter writing surface, as shipped

- **Section:** a new entry beside the other shipped route families (extending 014's).
- **Change:** Record the subsystem: `services/chapters.py`'s body and transition entry points,
  `routes/chapters.py`'s five new handlers, `models/schemas/chapters.py`'s two new DTOs,
  `services/chapter_tools.py`, and the four `TOOL_REGISTRY` additions.

  The five endpoints — `GET` / `PUT` on `/api/books/{book_id}/chapters/{chapter_id}/text`, and `POST` on
  `/open`, `/close`, `/reopen` under the same chapter — all `200`. **`POST` for the transitions because
  they are commands with no body**, not representations to replace; **`PUT` for the body because it
  replaces the whole resource**.

  DTO shapes: **`ChapterTextResponse`** (`chapter_id` as a string, `state`, `text`, **`version` as a JSON
  number**, `modified_at`) and **`UpdateChapterTextRequest`** (`text`, `expected_version`). Record why
  `version` stays a number while ids are strings — the string-id rule exists because snowflakes exceed
  JS's 2^53, and a counter does not. Record why `state` rides on the body response: the version and the
  state that qualify a save must arrive with the payload they qualify.

  The deliberate **absences**, which are the part a later feature would re-litigate:
  - **the body is a sub-resource, not a field on `ChapterResponse`** — 014 excluded `text` so a list
    render would not drag bodies onto the wire, and 014 has one `_to_response` serving both the list and
    the item, so a body added for the item is a body on every row;
  - **no `can_write` on the body response and no `can_manage_state` on the chapter response** — 014's
    `can_reorder` is justified because a **list envelope** is "the answer to this caller's request"; a
    resource representation is not, and `021` refused a caller-relative field on one. The client gates on
    chapter state alone and surfaces the server's `403`, which is `013.codex`'s shipped precedent;
  - **no partial or line-addressed write endpoint** — placement is computed server-side from the whole
    body (item 5);
  - **no `chapter_access` dependency** — 014's rule, unchanged;
  - **no new table, no new JSONL codec and no migration statement** — `chapter_changes` and
    `chapter_text_revisions` shipped with `008.data-domain` and got their first writer here; the ADDITIVE
    MIGRATION SEAM stayed `pass`;
  - **chapter text is not vector-indexed.** `VECTOR_SOURCE_REGISTRY` still holds `CodexEntry` only.
    Indexing chapter bodies is a retrieval decision, not a chapter one, and is not roadmapped.
- **Reason:** This file is the shipped-route inventory, and the six absences are each a question a later
  feature will otherwise answer differently.

## `docs/architecture/CLAUDE.md` and `docs/architecture/backend.md`

### 18. Shorten the "still uncovered" lists by one item each

- **Section:** `CLAUDE.md` → "Still not covered — do not infer it"; `backend.md` → the book-domain
  coverage paragraph.
- **Change:** Remove **"the shared-canvas write protocol for chapters (UC-055)"** from both lists; it is
  now covered by `assistant-runtime.md` (item 1). **Leave context/content assembly, token-level canvas
  streaming and token budgeting in place** — none of them moved, and item 3 explains why the chapter
  prompt became composable without them.
- **Reason:** Both files are the first thing an agent reads to decide what it may design. A stale
  "uncovered" entry causes a second design; a stale absence causes an invented one.

---

## Follow-ups that are NOT architecture's

### `/architect` — sequence: `021`, then `014`, then `015`

**Neither `021.per-author-system-prompt`'s nor `014.chapter-skeleton`'s `outcome.md` has been applied.**
`docs/architecture/` still describes `Book.system_prompt` as the live book-wide prompt, still lists
divergence 4 as the last one, and still carries `authorization.md`'s open bullet naming both prompt
levels.

014's own outcome already warns that its items 1–4 edit the same paragraphs `021`'s items 3, 4, 7, 8 and
9 edit. **This feature's items 3, 7 and 8 edit those same paragraphs again**, and items 9, 10, 12 and 13
edit sections 014 is mid-way through changing. Applying them out of order produces a document that
contradicts itself about whether a book-wide prompt exists, whether the Shell hub edits chapters, and how
many members the module tier has.

**Run `/architect` finalization on `021` first, then on `014`, then on `015`.**

### `/roadmap` — three things

1. **Re-scope `docs/plans/015.chapter-writing-free-mode/brief.md`.** Its Scope **Out** says *"composing
   blocks by chatting with the assistant (mapped later)"*. **This feature builds exactly that** — the
   user's decision, on the grounds that "the editor has no sense without the tools". The brief's
   `**Delivers:**` line (FEAT-009) is still right; its Out list is not, and the feature additionally
   delivers a slice of FEAT-013 / UC-055 that no brief currently claims. **This plan did not edit the
   brief** — it is `/roadmap`'s file.
2. **Note the surface shift for `016` and `018`.** Any brief that says open/close/reopen happen "from the
   book hub" needs the same correction 014 already needed: all chapter editing and all chapter state
   transitions live on the working page's chapter item.
3. **Check `016.chapter-close-continuity`'s brief against the close seam** as recorded in item 6: 016
   changes a destination constant and adds an approval endpoint; it does not rebuild the transition, the
   one-open-chapter guard, or the `close-chapter` mode branch, all three of which already handle
   `closing`.

### `/product-spec` — four things

1. **UC-036 is only partly deliverable at Stage 2** and this feature delivers it partly, by the roadmap's
   own close-gate seam. Its steps 3–5 (drafting continuity, the owner's approval, `closing → closed`) are
   `016`'s. **US-038.AC-3 is cited by nothing in this feature.** No product edit is required — this is
   staging, not divergence — but a `Delivered:` note on FEAT-009 should say which criteria landed when.
2. **US-040.AC-4's wording invites a merge reading.** As designed (`domain-chapter.md`, and item 6 above)
   the system refuses the later save, shows the divergence, and lets a re-issued save land; **the merging
   is the author's**. Consider wording that names the reconciliation flow rather than the outcome, so a
   reader does not expect an automatic merge the architecture explicitly refuses.
3. **FEAT-013's UC-054 / UC-055 now have an implementation** — three chapter write tools plus a read
   path, with the frame protocol in item 1. The roadmap parks them under "Mapped later"; the ids that
   describe what shipped do not exist yet, which is why **every assistant-half DoD item in this feature
   cites none**. The same convention `014` used for the chapter-prompt half and `021` for the book half.
4. **The chapter prompt's ids are still `/product-spec`'s to mint.** 014 asked for FEAT-019 to be
   rewritten whole; this feature now **composes** the per-author chapter prompt into a turn, so whatever
   ids replace UC-094 / US-109 will have a consumer as well as a store.

### Nothing here may be closed by editing `docs/product/`

`docs/product/` is read-only from plans and from architecture alike. Surfacing is the orchestrator's;
closing is `/product-spec`'s.

## Observations

- Step 007: the two entrances leave one case unnamed by `frontend-work-drafts.md` → "Two entrances, not
  one" — the **re-fetch that follows a `409` can itself fail**, and then there is no server body to place
  beside the draft. The chapter page falls back to the ordinary refusal surface and does **not** open a
  half-populated divergence view, keeping the draft, its buffer and the base version untouched. Possible
  impact: add one sentence to `frontend-work-drafts.md` under "Two entrances, not one" so the next
  consumer of the tier does not invent a different answer (`CodexEntryPage` already behaves this way).
- Step 007: a buffer carrying the `""` no-base-version marker reads as **stale against a numeric
  `Chapter.version` by construction**, so D18's dropped-canvas-frame fallback always lands the author in
  the divergence view rather than restoring silently. Possible impact: `frontend-work-drafts.md`'s
  base-version paragraph could state that the marker is deliberately unequal to every real chapter
  version, since that is what makes the fallback safe rather than lossy.
