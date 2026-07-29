# 021.per-author-system-prompt — intended documentation changes

Written by the planner; applied by the architect at finalization. Grouped by target architecture file.
The coder appends `## Observations` at the bottom.

---

## `docs/architecture/domain-book.md`

### 1. `Book.system_prompt` is dormant — say so in the field table

- **Section:** the `Book` field table (the `system_prompt` row, currently "book-wide prompt applied to
  **all** chats in the book").
- **Change:** Reword the row: the column is **superseded and read by nothing**. It is retained rather
  than dropped because `db/engine.py` exposes only an *additive* migration seam and the project has no
  Alembic, so there is no supported DROP COLUMN path; it is still required, still written `""` at book
  creation, and still round-trips through the JSONL codec so pre-existing archives import. A
  dead-but-documented column beats an unsupported migration.
- **Reason:** The row currently describes behaviour the system no longer has, and a reader who deletes
  the column on that basis will break every existing database file.

### 2. A new entity — `BookAuthorPrompt`

- **Section:** a new subsection beside `BookMember`.
- **Change:** Record the table: snowflake PK, `book_id`, `user_id`, required `system_prompt` (`""`
  means "no prompt"), `created_at` / `modified_at`, and a **unique `(book_id, user_id)`** constraint —
  `BookMember`'s surrogate-PK-plus-unique-pair shape, for `BookMember`'s stated reasons. Carry the
  load-bearing reasoning: **the prompt cannot hang off `BookMember`, because the owner has no
  `BookMember` row** (ownership is `Book.owner_id`), so a membership-hosted prompt would be
  unreachable for exactly the author most likely to write one.
- **Reason:** It is a new first-class row in the book domain and the entity map is the index for it.

### 3. Rewrite the `system_prompt` paragraph

- **Section:** the paragraph beginning "**`system_prompt`** applies to every chat in the book.
  `Chapter.system_prompt` … **appends to** it rather than replacing it."
- **Change:** Replace it. The composed author layer is now the prompt of **the author running the
  turn**, from `BookAuthorPrompt`; there is no book-wide layer. State plainly that
  `Chapter.system_prompt` therefore **has nothing left to append to**, that what a chapter prompt
  narrows is now an open question, and that it is `014.chapter-skeleton`'s to answer once
  `/product-spec` has rewritten FEAT-019. Do not invent an answer here.
- **Reason:** The paragraph is the single sentence linking the two FEAT-019 halves; leaving it would
  make the chapter half look designed when its foundation has been removed.

## `docs/architecture/domain-chapter.md`

### 4. The chapter prompt's base layer is gone

- **Section:** wherever `Chapter.system_prompt` is described (the field's "appends to the book's"
  wording, divergence 3).
- **Change:** Record that the book-wide layer it appends to **no longer exists**, that the column is
  untouched and still unread by the composer, and that redefining it is `014.chapter-skeleton`'s work
  after the FEAT-019 rewrite. Note the in-code docstring on the column says "appends to the book's"
  and is now stale — flagged, deliberately not edited by this feature.
- **Reason:** A downstream feature is about to be planned against this field; the doc must not hand it
  a base layer that was removed.

## `docs/architecture/assistant-config.md`

### 5. Composition order — `BOOK` becomes `AUTHOR`

- **Section:** "System-prompt composition — the named prompts only" (the numbered four-layer block and
  the "Why this order" paragraph beneath it).
- **Change:** Layer 3 becomes **`author prompt — BookAuthorPrompt.system_prompt` (the author running
  the turn; per-author, not per-book)**, and the section label the runtime renders becomes `AUTHOR`.
  The empty-contributes-nothing rule is unchanged. In "Why this order", **remove the clause that the
  chapter prompt must follow the book prompt because it narrows it** — that justification no longer
  holds; the ordering survives on the surviving argument (most-general → most-specific, admin →
  author, the most-specific layer nearest the task). Record that the parameter was renamed rather than
  merely repointed, because a parameter named `book` carrying an author's prompt is a trap for the next
  reader.
- **Reason:** This block is what the runtime is written from; a stale layer name here would be copied
  into every later assistant feature.

### 6. The turn resolves the prompt by chat author, not by book

- **Section:** the same composition section, or beside it.
- **Change:** Record how the runtime obtains the layer: `services/chat_turn.py` reads the
  `(book_id, author_id)` row through the `db/` module directly (`services → db`), using the chat's own
  author — the same identity `services/chats.py`'s ownership guard scopes every chat read and write to.
  Note that no `BookAccess` is built for this, and why: the turn is already scoped to the chat's author
  by construction.
- **Reason:** "Whose prompt?" is now a real question with a non-obvious answer, and it is the answer
  every future runtime slice must reuse.

## `docs/architecture/authorization.md`

### 7. Close the open item — who may edit a system prompt

- **Section:** "Not settled by this pass" (the bullet "Who may edit the book- and chapter-level system
  prompts").
- **Change:** The **book-level** half is settled: **every member owns exactly one prompt per book and
  may read and write only their own**; nobody — including the owner — reads or writes another
  author's. Move it out of the open list and into the body. The **chapter-level** half stays open, and
  should now be recorded as open *for a different reason than before*: it lost the layer it narrowed.
- **Reason:** The doc names this as undecided; it is decided, and leaving it listed would invite a
  second, different answer.

### 8. A second row-ownership rule, beside Chats

- **Section:** "Chats" (the paragraph explaining that a chat's privacy "is not a matrix row but an
  ownership rule on `Chat.author_id`").
- **Change:** Add `BookAuthorPrompt` as the **second** rule of that kind: membership is established by
  the `book_access` dependency, then the service scopes every read and write to `access.user_id`.
  Record explicitly that **no `Capability` member and no `_CAPABILITY_MATRIX` row was added**, for the
  reason this section already states — the matrix maps capability → roles and has no notion of row
  ownership. Record the status taxonomy the route pair produces: `401` no token, `404` for a private
  book the caller has no relationship to (produced by `resolve_book_access`, not re-derived),
  **`403`** for a logged-in non-member of a book they can see, `200` for a member acting on their own
  prompt. Note that **collaboration mode does not apply** — a prompt is an author's instruction to
  their own assistant, never book content, so there is nothing for an owner to review.
- **Reason:** One row-ownership rule reads as a special case; two read as a pattern, and the next
  feature needing one should find the shape here rather than inventing a matrix concept for it.

## `docs/architecture/domain-model.md`

### 9. A fifth product divergence — and this one is not a reconciliation

- **Section:** "Product divergences".
- **Change:** Add the divergence: **FEAT-019's book-wide, owner-only system prompt is replaced by a
  per-author prompt**, by explicit user decision during triage of `fast/003.book-system-prompt`
  (2026-07-27..29). Record what it contradicts — UC-093 and every criterion of US-108, including
  **US-108.AC-2** (the co-author refusal, which is now reversed) — and that it removes the base layer
  UC-094 / US-109 narrow, **US-109.AC-3** in particular. Record it as **awaiting `/product-spec`**,
  unlike the four existing divergences which are reconciled decision history.
- **Reason:** The four existing entries are all closed; this one is open, and the difference matters —
  a reader must not assume `docs/product/` already carries this wording.

## `docs/architecture/backend/persistence.md` and `docs/architecture/backend/book-domain.md`

### 10. The table registry and codec obligations

- **Section:** `book-domain.md` → "The book-domain table registry"; `persistence.md` → the codec rules.
- **Change:** Add `book_author_prompts` to the registry list, **immediately after `book_members`**, and
  record why that position (FK import order: it references `books` and `users`, both already earlier;
  keeping the two `(book_id, user_id)` link tables adjacent is where a reader looks). Record that the
  new table needed **model registration only** — `init_db()`'s `create_all` is additive, so the
  ADDITIVE MIGRATION SEAM stayed `pass`. Record that **`Book.system_prompt` keeps its codec** despite
  being dormant, so archives written before this feature still import.
- **Reason:** These files are the persistence inventory; a table absent from them will be added twice
  or exported never.

## `docs/architecture/backend/features.md`

### 11. The per-author system-prompt route pair, as shipped

- **Section:** a new entry beside the other shipped route families.
- **Change:** Record the subsystem: `models/book_author_prompt.py`, `db/book_author_prompts.py`,
  `models/schemas/book_author_prompts.py`, `services/book_author_prompts.py`,
  `routes/book_author_prompts.py`; the two endpoints `GET` / `PUT
  /api/books/{book_id}/system-prompt`; the response shape (`book_id`, `system_prompt`, nullable
  `modified_at` — and **no `user_id`**, because it is always the caller); the error taxonomy
  (401/404/403); and the deliberate absences: **no DELETE** (empty string is "no prompt"), **no
  `POST`** (`PUT` is the upsert and answers `200` on both paths), and **no field on
  `BookDetailResponse`** — a per-caller value cannot ride on a book-shaped DTO.
- **Reason:** This file is the shipped-route inventory, and the absences are the part a later feature
  would otherwise re-litigate.

## `docs/architecture/frontend-workspace.md`

### 12. Book state gains exactly one editable region

- **Section:** "Content pane — subject and editability" (the Book state row, "state notes editable
  (UC-050); everything else read-only").
- **Change:** Add the caller's **own system prompt** as editable on the Book-state subject, and record
  that it is the *only* addition — the rest of the view stays read-only. Record that this field is
  deliberately **outside the draft-until-saved restore buffer**: the buffer exists for large
  content-pane artifacts whose loss is expensive, while this is a short settings field edited from two
  surfaces, and buffering it on one but not the other would be incoherent. Consequently there is no
  `baseVersion`, no stale-buffer detection, no divergence view and no 409 path — the row has exactly
  one writer, its owner.
- **Reason:** The editability table is enforced as a single rule set; an editable field that is not in
  it is drift, and the buffer exclusion needs sanctioning the same way the buffer's inclusions were.

### 13. Why the same editor exists on two surfaces

- **Section:** the Shell route map (`/books/:bookId/settings`) or beside the working-page description.
- **Change:** Record that the prompt editor exists on **both** `BookSettingsPage` and the working
  page's Book state view, deliberately: the settings page aggregates owner-only capabilities, while
  every author now owns a prompt, so the editor must also live where **every member** lands
  (UC-091's Book-state landing view). Record that the two surfaces share the DTOs and the api
  functions at `src/` root but **not** a state class or a component — crossing from the `work` entry
  into the `user` entry would break the folder layout, and each page owns its own state per the
  page-is-a-route rule.
- **Reason:** Two editors for one value looks like duplication unless the reason is written down.

---

## Follow-ups that are NOT architecture's

- **`/product-spec` must rewrite FEAT-019.** `docs/product/use-cases/FEAT-019.system-prompts.md` and
  `docs/product/stories/FEAT-019.system-prompts.md` are `[confirmed: user]` from the 2026-07-24
  interview and now describe a system that does not exist:
  - **UC-093 / US-108** — a book-wide, owner-only prompt applied to every chat. Replaced wholesale by
    a per-author prompt. **US-108.AC-2** (a co-author attempting to edit it is refused) is
    **deliberately reversed** — a co-author has their own prompt and may edit it.
  - **UC-094 / US-109** — the chapter prompt "narrows the book's rather than replacing it — the
    book-wide voice always applies", and **US-109.AC-3** says that with no chapter prompt "only the
    book's system prompt applies". The layer both criteria rest on no longer exists.

  This is `/product-spec`'s alone (`docs/product/CLAUDE.md` → "Who writes, who reads"); neither
  architecture nor this plan may edit `docs/product/`. The new ids, once minted, are what a later
  planner will cite — **this feature's `[test]` DoD items deliberately cite none of the old ones as
  met.**

- **`/roadmap` must re-shape two things.**
  1. **`docs/plans/fast/003.book-system-prompt/brief.md` is superseded by this feature** and describes
     the replaced model (book-wide, owner-only, FEAT-019 book half, UC-093, US-108). It is
     `/roadmap`'s file; this plan did not edit it. It should be retired or rewritten, and
     `roadmap.md`'s Stage-3 row and build-order line for it updated.
  2. **`roadmap.md`'s `014.chapter-skeleton` row** delivers "FEAT-019 (chapter half), UC-094, US-109 …
     any member sets/clears the chapter's own system prompt". Its base layer is gone. That folder is
     **roadmapped only** (`brief.md`, no `status.md`), so no plan is invalidated — but the brief and
     the row need re-scoping before `/planner` runs on it, and it should be sequenced **after**
     `/product-spec` rewrites FEAT-019.
  Also worth `/roadmap`'s attention: `roadmap.md`'s Stage-3 exit criterion still reads "the book owner
  sets the book-wide system prompt".

- **`docs/product/features.md`'s `**Delivered:**` marker** for FEAT-019's book half is
  `/product-spec`'s to write, per `docs/product/CLAUDE.md` → "Citation convention" — and only once
  FEAT-019 has been rewritten to describe what was actually built.

## Observations

- Step 005: `frontend.md` → "Forms" states the rule as "server-side field errors are stored separately
  and unioned with client errors in the `errors` getter", which assumes every form has a client-side
  validation layer. The system-prompt editor has none — every string, `""` included, is valid — so it
  carries `systemPromptServerErrors` with no `clientErrors` and no `errors` union, and the server-error
  surface is the only error surface. Possible impact: add a sentence to `frontend.md` → "Forms" saying
  the `errors` union is the shape *when* client validation exists, and that a field with no client rules
  binds the server-error map directly.
