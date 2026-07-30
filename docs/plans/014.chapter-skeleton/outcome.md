# 014.chapter-skeleton — intended documentation changes

Written by the planner; applied by the architect at finalization. Grouped by target architecture file.
The coder appends `## Observations` at the bottom.

> **Read the last section first.** Feature `021.per-author-system-prompt`'s `outcome.md` has **never
> been applied**, and this feature's items 1 and 2 edit the same paragraphs it does. Sequence matters.

---

## `docs/architecture/domain-chapter.md`

### 1. `Chapter.system_prompt` is dormant — the chapter prompt is now `ChapterAuthorPrompt`

- **Section:** the `Chapter` field table (the `system_prompt` row, currently "optional; **appends to**
  the book's, narrowing it") **and** the whole paragraph built on it ("**The chapter system prompt
  appends to the book's, it does not replace it.** … Neither prompt field has a product requirement
  behind it — see `domain-model.md` → 'Product divergences', item 3.").
- **Change:** Retire both. The field row becomes: **superseded and read by nothing**, retained rather
  than dropped because `db/engine.py` exposes only an *additive* migration seam and the project has no
  Alembic, so there is no supported `DROP COLUMN` path; it still round-trips through the JSONL codec so
  pre-existing archives import. Replace the paragraph with the new model: **the per-chapter prompt is
  `ChapterAuthorPrompt`, one row per `(chapter, author)`**, snowflake PK, `chapter_id`, `user_id`,
  required `system_prompt` (`""` means "no prompt"), `created_at` / `modified_at`, unique
  `(chapter_id, user_id)` — `BookMember`'s surrogate-PK-plus-unique-pair shape, mirroring
  `BookAuthorPrompt` exactly one level down. State plainly that there is **no book-wide layer left to
  append to**, and that **composition is still not wired**: storing and serving the prompt shipped
  here, but reading it into a turn needs "which chapter is this turn about", which is undesigned
  FEAT-013 context assembly, and is `015.chapter-writing-free-mode`'s.
- **Reason:** The row and the paragraph describe a base layer feature `021` removed. Left as they are,
  the next reader designing `015`'s composition will build on a layer that does not exist.

### 1b. The in-code docstring flagged by `021` is **still stale**

- **Section:** the same place, as a note.
- **Change:** Record that `Chapter.system_prompt`'s docstring in `backend/app/models/chapter.py` still
  says it appends to the book's. Feature `021` flagged it and deliberately did not edit it; **feature
  `014` did not edit it either** — `backend/app/models/chapter.py` was out of scope for every step,
  because the skeleton half needed no schema change and the prompt half went to a new table. The flag
  stands open.
- **Reason:** Two features in a row have now left the same one-line lie in the code. Recording that it
  is deliberate, twice over, is what stops a third reader assuming the column is live.

## `docs/architecture/domain-model.md`

### 2. Extend divergence 5 — the chapter half of FEAT-019 goes per-author too

- **Section:** "Product divergences", the entry feature `021` adds as item 5 (the per-author
  replacement of FEAT-019's book-wide prompt), which is **still open, still awaiting
  `/product-spec`**, and distinct from the four reconciled entries.
- **Change:** Extend it: the **chapter** half is now per-author as well. **UC-094 and every criterion
  of US-109 (AC-1, AC-2, AC-3) are superseded** — they describe a chapter prompt that "narrows the
  book's rather than replacing it", and AC-3 says that with no chapter prompt "only the book's system
  prompt applies". There is no book's. What shipped instead: any book **member** owns exactly one
  prompt per chapter and reads and writes only their own. Record that no `[test]` DoD item in feature
  `014` cites UC-094 or any US-109 criterion as met, the same convention `021` used, and that the
  entry stays **awaiting `/product-spec`** until FEAT-019 is rewritten whole.
- **Reason:** The divergence list is where a reader checks whether `docs/product/` can be trusted on a
  topic. Half an open divergence is worse than none — a reader who saw `021`'s entry could reasonably
  assume the chapter half was untouched.

## `docs/architecture/authorization.md`

### 3. Close the second half of the open item

- **Section:** "Not settled by this pass", the bullet **"Who may edit the book- and chapter-level
  system prompts."** Feature `021` closes the book half; this feature closes the chapter half.
- **Change:** Remove the bullet entirely and move the answer into the body: **every member owns
  exactly one prompt per chapter and may read and write only their own**; nobody — including the
  book's owner — reads or writes another author's. Note that the chapter's **state machine does not
  gate it**: a prompt is readable and writable on a chapter in `planned`, `open`, `closing` or
  `closed`, because it is the author's instruction to their own assistant, not chapter content. Note
  that **collaboration mode does not apply** for the same reason — there is nothing for an owner to
  review.
- **Reason:** The doc names this as undecided. It is now decided on both halves, and leaving it listed
  invites a second, different answer.

### 4. A **third** row-ownership rule, beside Chats and `BookAuthorPrompt`

- **Section:** "Chats" (the paragraph explaining that a chat's privacy "is not a matrix row but an
  ownership rule on `Chat.author_id`"), which feature `021` extends with `BookAuthorPrompt`.
- **Change:** Add `ChapterAuthorPrompt` as the **third** rule of that kind. Membership is established
  by the `book_access` dependency; the service then scopes every read and write to `access.user_id`,
  and separately verifies `chapter.book_id == access.book_id`. Record explicitly that **no
  `Capability` member and no `_CAPABILITY_MATRIX` row was added for it**, for the reason this section
  already states — the matrix maps capability → roles and has no notion of row ownership. Record the
  status taxonomy the route pair produces: `401` no token; `404` for a private book the caller has no
  relationship to (produced by `resolve_book_access`, not re-derived) **and** for a chapter that does
  not exist or belongs to another book; `403` for a logged-in non-member of a book they can see; `200`
  for a member acting on their own prompt, including when no row exists yet.
- **Reason:** Two rules read as a pattern; three make it the house shape. The next feature needing one
  should find it here rather than inventing a matrix concept for it.

### 5. The chapter matrix rows finally have an enum behind them

- **Section:** "Capability × role matrix" → "Chapters".
- **Change:** Record that this feature added the **four `Capability` members** that back the existing
  rows — add a chapter (UC-031), edit a planned chapter's sketch (UC-033), remove a planned chapter
  (UC-034) all `{owner, co_author}`; **set chapter order (UC-032) owner-only**, which is what
  **US-033.AC-2** requires. Until now those rows were a matrix on paper with no enum behind them.
  Record that **the two read paths reuse the existing `read_book` capability unchanged** rather than
  minting a new one, because "Read chapter text" is already that row. Record the two additions to the
  "state-machine constraints, not authorization" note: a **non-`planned` chapter refuses a sketch edit
  and a removal with `409`, not `403`** — the caller has the capability, the resource is in the wrong
  state — and **reordering is allowed while a chapter is `open`**, because it touches `ordinal` only
  (closing UC-032's `_TBD`).
- **Reason:** A matrix with no implementation is a promise; this records which promises are now
  code, and pins the `409`-vs-`403` choice so a later feature does not "fix" it to `403`.

### 6. No `chapter_access` dependency — deliberately

- **Section:** "Enforcement — resolve in a dependency, decide in a service", as a note.
- **Change:** Record that the chapter routes nest under `/api/books/{book_id}/chapters/…` **precisely
  so that `book_access` binds unchanged** to the `{book_id}` path parameter, and that **no
  chapter-level access resolver was built**. Each service verifies `chapter.book_id ==
  access.book_id` itself and raises its own not-found reason. Reason: a second resolver would
  duplicate the existence-hiding rule the document is explicit about producing in exactly one place.
- **Reason:** `brief.md`'s open question asked for a chapter → `book_id` resolution. The answer is
  "don't build one, nest the route" — and that answer needs to be findable, or every later chapter
  feature will ask it again.

## `docs/architecture/frontend-workspace.md`

### 7. The Shell book hub becomes read-only; the skeleton moves to the working page

- **Section:** the Shell route map (the `/books/:bookId` row, currently "Book hub — chapter skeleton
  (UC-031..034), open / close / reopen (UC-035..037)") **and** the working-page route map (the
  `/chapters` and `/chapter/:id` rows, currently bare "chapter list" / "one chapter").
- **Change:** The Shell row becomes a **read-only** ordered chapter list with state badges and links
  into the working page; **UC-031..034 move off it**. The working-page `/chapters` row gains add,
  remove and reorder; the `/chapter/:id` row gains the sketch editor and the caller's own chapter
  system prompt. Record that this **diverges from this document's own Shell route table but agrees
  with this document's own stated rule** — "all *management* of codex entries, state notes, summaries
  and flags happens on the working page … there is exactly one editing surface per artifact". The
  chapter skeleton was the one row that broke that rule; it no longer does. **The divergence is
  internal to this document, not with `docs/product/`** — no UC or US says which SPA the skeleton is
  built from.
- **Reason:** Two surfaces claiming to edit one artifact is exactly what the one-editing-surface rule
  exists to prevent, and the route table was the last place still saying so.

### 8. The content-pane editability table gains a partial row

- **Section:** "Content pane — subject and editability" (the row "Any `planned` or `closed` chapter |
  **read-only** (US-097.AC-1)").
- **Change:** Split it. A **`closed`** chapter stays read-only. A **`planned`** chapter becomes
  **editable in its `sketch` and in the caller's own chapter system prompt, and read-only in its
  `text`**. Record why the table needed a partial row at all: US-097.AC-1's read-only rule is about
  the chapter's **body**, and the sketch is editable in exactly the opposite window from the body
  (UC-033 — `planned` only; the body — `open` only). Record that `checkWritePermission` still refuses
  a body write on a `planned` chapter, so the shared-canvas symmetry (US-097.AC-2, US-059.AC-3)
  is untouched. Record that **neither new field enters the draft-until-saved restore buffer** — the
  buffer exists for large artifacts with a version token, the sketch is explicitly last-write-wins with
  no version, and the prompt row has exactly one writer; consequently there is no stale-buffer
  detection, no divergence view and no `409` path on either.
- **Reason:** The table is enforced as a single rule set; an editable region not in it is drift, and
  the buffer exclusion needs sanctioning the same way `021`'s did.

## `docs/architecture/backend/persistence.md` and `docs/architecture/backend/book-domain.md`

### 9. The table registry and codec obligations

- **Section:** `book-domain.md` → "The book-domain table registry"; `persistence.md` → the codec rules.
- **Change:** Add `chapter_author_prompts` to the registry list, **immediately after
  `book_author_prompts`**, and record why that position: `TABLE_REGISTRY` is FK import order and the
  row references `chapters` and `users`, both already earlier; keeping the two per-author-prompt
  tables adjacent is where a reader will look for the second one. Record that the new table needed
  **model registration only** — `init_db()`'s `create_all` is additive, so the **ADDITIVE MIGRATION
  SEAM stayed `pass`**. Record that **`Chapter.system_prompt` keeps its codec** despite being dormant,
  so archives written before this feature still import — the same treatment `Book.system_prompt`
  received in `021`.
- **Reason:** These files are the persistence inventory; a table absent from them will be added twice
  or exported never.

## `docs/architecture/backend/features.md`

### 10. The chapter route family and the chapter system-prompt pair, as shipped

- **Section:** a new entry beside the other shipped route families.
- **Change:** Record the subsystem: `models/schemas/chapters.py`, `services/chapters.py`,
  `routes/chapters.py`, plus `db/chapters.py`'s new `update` / `delete`; and
  `models/chapter_author_prompt.py`, `db/chapter_author_prompts.py`,
  `models/schemas/chapter_author_prompts.py`, `services/chapter_author_prompts.py`,
  `routes/chapter_author_prompts.py`.

  The six skeleton endpoints — `GET` / `POST` on `/api/books/{book_id}/chapters`, `GET` / `PATCH` /
  `DELETE` on `/{chapter_id}`, and `PUT` on `/order` — with `201` on create, `204` on delete, and the
  literal `/order` segment declared before the parameterised one. The prompt pair —
  `GET` / `PUT /api/books/{book_id}/chapters/{chapter_id}/system-prompt`.

  DTO shapes: `ChapterResponse` (ids as strings; **no `text`, no `summary`, no `summary_status`** —
  the body is `015`'s, the summary `016`'s), `ChapterListResponse` (the ordered array **plus
  `can_reorder`**, a caller-relative affordance hint the client mirrors and never enforces on),
  `CreateChapterRequest` (server-assigned ordinal — a new chapter is appended),
  `UpdateChapterSketchRequest` (**no version token** — sketch edits are last-write-wins and do not bump
  `Chapter.version`, which tracks the body only), `ReorderChaptersRequest` (the **full** ordered id
  list; the server rewrites ordinals `1..N` and refuses a list that is not exactly the book's current
  chapter set), and `ChapterAuthorPromptResponse` (no `user_id` — it is always the caller).

  The error taxonomy: `401` / `404` / `403` from `authorization.md`, plus **`409`** for a
  non-`planned` chapter on the sketch and remove paths and **`400`** for an invalid reorder set
  (structurally valid body, failed cross-row invariant — `422` would misreport where validation
  happened).

  The deliberate **absences**: **no `chapter_access` dependency** (the route nests under `{book_id}`);
  **no `DELETE` and no `POST` on the prompt path** (`""` is "no prompt", `PUT` is the upsert answering
  `200` on both paths); **no chapter field on any book DTO**; **no per-chapter move endpoint** (one
  bulk `PUT`, so two concurrent callers cannot interleave into an ordinal set nobody chose); and **no
  ordinal renumbering on delete** — removal leaves a gap, only reorder rewrites `1..N`, because
  renumbering would silently move every later chapter for an operation the author framed as removing
  one.
- **Reason:** This file is the shipped-route inventory, and the absences are the part a later feature
  would otherwise re-litigate.

## `docs/architecture/frontend.md`

### 11. `@dnd-kit` joins the dependency set

- **Section:** the dependency / stack list, and the conventions section.
- **Change:** Add **`@dnd-kit/core` + `@dnd-kit/sortable`** — the first drag-and-drop dependency in
  the project (`react-beautiful-dnd` and `@hello-pangea/dnd` were never present). Record why both
  affordances exist: the user asked for **move buttons *and* dragging**, so the chapter order list
  offers both, and **both funnel into one persist path** — a single bulk order `PUT` — which is what
  makes testing only one of them sufficient. Record that the **button path is the tested one** and the
  drag gesture is a `[manual/live]` criterion, because `@dnd-kit`'s pointer sensor needs real element
  geometry and jsdom reports zero-sized rectangles for everything; faking the library's callbacks
  would test the test. Record that a library's own hooks are not a breach of the no-custom-`useX` rule
  — the rule forbids authoring hooks, not consuming a library's API — and that they are called
  directly in the row component rather than wrapped in a local hook.
- **Reason:** A new runtime dependency and a new interaction pattern both need a recorded reason, and
  "why is only half of this tested" is the first question a reader will have.

### 12. `…ServerErrors` without an `errors` union recurs

- **Section:** "Forms".
- **Change:** `021` recorded an observation that the rule as written — "server-side field errors are
  stored separately and unioned with client errors in the `errors` getter" — assumes every form has a
  client-validation layer, and that its system-prompt editor had none. **This feature hit it three
  more times**: the chapter sketch editor and the chapter prompt editor both accept every string
  including `""`, so both carry a `…ServerErrors` map with no `clientErrors` and no `errors` union.
  The chapter **add form** is the counter-example — its title must be non-blank, so it does compute
  client errors and does union them. Add the sentence `021` proposed: the `errors` union is the shape
  *when* client validation exists; a field with no client rules binds the server-error map directly.
- **Reason:** Four instances across two features is a pattern, not an exception, and the rule as
  written reads as mandatory.

---

## Follow-ups that are NOT architecture's

### `/architect` — sequence this feature **after** finalizing `021`

**Feature `021.per-author-system-prompt`'s `outcome.md` has never been applied.**
`docs/architecture/` still describes `Book.system_prompt` as the live book-wide prompt, still has
`domain-book.md`'s "appends to it" sentence, still lists divergence 4 as the last one, and still has
`authorization.md`'s open bullet naming **both** prompt levels.

Items **1**, **2**, **3** and **4** above edit the *same paragraphs* `021`'s items 3, 4, 7, 8 and 9
edit. Applying `014`'s outcome first — or applying only one of the two — will produce a document that
contradicts itself about whether a book-wide prompt exists. **Run `/architect` finalization on `021`
first, then on `014`.**

### `/product-spec` — three things

1. **Rewrite FEAT-019 whole, both halves.** `021` already flagged the book half (UC-093 / US-108).
   This feature supersedes the chapter half: **UC-094** and **US-109 (AC-1, AC-2, AC-3)** describe a
   chapter prompt narrowing a book-wide prompt that no longer exists. What shipped is a **per-author**
   chapter prompt: any book member owns exactly one prompt per chapter and reads and writes only their
   own; nobody, including the owner, reads another author's; the chapter's state machine does not gate
   it. The new ids, once minted, are what a later planner will cite — **feature `014`'s `[test]` DoD
   items deliberately cite none of the old ones.**
2. **Transcribe the closure of UC-032's `_TBD`.** Reordering **is** allowed while a chapter is open,
   because reorder touches `ordinal` only — it never reads or writes a body, never changes a `state`
   and never bumps `version`.
3. **Transcribe the closure of UC-033's `_TBD`.** Sketch edits are **last-write-wins**: no
   `expected_version`, no `409`, and `Chapter.version` is **not** bumped by a sketch edit because it
   tracks the body only. Product's own UC-033 says co-authors edit sketches "in parallel"; the
   concurrency contract in `domain-chapter.md` is written for `text` and its line-addressed
   placements, which a sketch has none of.

This is `/product-spec`'s alone (`docs/product/CLAUDE.md` → "Who writes, who reads"); neither
architecture nor this plan may edit `docs/product/`.

### `/roadmap` — four things

1. **Re-scope `docs/plans/014.chapter-skeleton/brief.md`.** Its `**Delivers:**` line names "FEAT-019
   (chapter half), UC-094, US-109", and its Definition says a member sets a chapter prompt "which
   narrows the book's". The first clause survives, the second does not, and the two ids are
   superseded. Its "Open questions for the planner" are all now answered (`context.md` → D1, D4, and
   `outcome.md` item 6) and can be retired. **This plan did not edit the brief** — it is `/roadmap`'s
   file.
2. **Retire or rewrite `docs/plans/fast/003.book-system-prompt/brief.md`** — `021` already flagged it;
   it still defines a book-wide, owner-only prompt.
3. **Fix `roadmap.md`'s Stage-3 exit criterion**, which still reads "the book owner sets the
   book-wide system prompt" — `021` flagged this too and it is still there.
4. **Note the surface shift for downstream briefs.** `015`, `016` and `018` all assume chapter
   surfaces; this feature put the skeleton's editing on the **working page**, not the book hub
   (`context.md` → D2). Any brief that says "from the book hub" needs the same correction.

### `015.chapter-writing-free-mode` inherits one thing explicitly

**Composition of the chapter system prompt.** This feature stores and serves it; nothing reads it.
Wiring it into `services/prompt_composition.py` / `services/chat_turn.py` needs an answer to "which
chapter is this turn about", which is undesigned FEAT-013 context assembly. `021` left the composer's
`chapter` layer in place, untouched and unpassed; it is still unpassed.

## Observations

- Step 008: outcome item 8 (the content-pane editability table's partial row) is now backed by a
  concrete API shape worth naming when the doc is written — `Editability` gained an **optional**
  `editableRegions?: EditableRegion[]`, `EditableRegion` gained `"chapter-sketch"` and
  `"chapter-own-prompt"`, and `WriteRegion` was **not** widened, so a chapter's body write is still
  `checkWritePermission(subject, "whole")`. The documented invariant is that when `editableRegions`
  is absent the editable set is `editable === "none" ? [] : [editable]`. Possible impact: state it in
  `frontend-workspace.md` → "Content pane — subject and editability" so a later partial row copies
  the shape instead of turning `editable` into an array.
