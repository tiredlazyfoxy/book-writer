# 026.memos — intended documentation changes

Written by the planner; applied by the architect at finalization. Grouped by target architecture file.
The coder appends `## Observations` at the bottom.

**This file is deliberately short.** FEAT-021 was designed by an `/architect` round on 2026-09-15,
**before** this plan existed, so the architecture is already aligned to the feature: there is no entity
to record, no authorization rule to add and no route table to write. What follows is therefore mostly
**drift found during planning**, plus the two status flips a finalization pass owes.

---

## `docs/architecture/assistant-config.md`

### 1. `ToolContext`'s field count is stale — say **seven**, not six

- **Section:** "Tool registry — code-defined, not a table", the `create_memo` paragraph ("…so the
  context stays **six** fields").
- **Change:** `ToolContext` has **seven** fields today — feature `025` added `codex_creates_this_turn`
  after this sentence was written. Correct the count. **The substantive claim is unaffected and must be
  kept:** `create_memo` needs **no new field**, because `book_id` and `access.user_id` are already
  there; only the number is wrong.
- **Reason:** Pre-existing drift, caused by `025` and not by this feature. The sentence is written as a
  precise structural claim ("the last three tool features each widened it; there is none here"), so a
  wrong count reads as a description of the code rather than as a stale number, and the next tool
  feature will copy it.

## `docs/architecture/quick-reference.md`

### 2. The same stale `ToolContext` count, in the `TOOL_REGISTRY` row

- **Section:** "Tables & enums" → the `TOOL_REGISTRY` row (the FEAT-021 sentence, "…so the context stays
  **six** fields, where 015 and 016 each widened it").
- **Change:** Same correction: seven fields today, and `create_memo` still adds none.
- **Reason:** Same pre-existing `025` drift, in the file agents read first for concrete shapes.

### 3. `ToolDef`'s field list omits `group`

- **Section:** "Tables & enums" → the `TOOL_REGISTRY` row, the inline `ToolDef` definition
  (`name` / `description` / `args_schema` / `callable` / `binder`).
- **Change:** Add **`group: str`**, which feature `025` added and which is now load-bearing: there is a
  test asserting that **every registry entry declares a valid group**, and this feature's `create_memo`
  entry takes the existing **`"book"`** group (user decision — no new group, no widening of the valid
  set).
- **Reason:** A reader adding a tool from this field list will omit `group` and fail a test whose
  existence the documentation never mentions. Pre-existing `025` drift, surfaced here.

## `docs/architecture/domain-book.md`

### 4. Say which memos `max + 1` is computed over

- **Section:** `## Memo` → "**`ordinal` is scoped per `(book, author)`, and gaps are left alone**".
- **Change:** State that the `max` a new memo (and a restore) appends past is taken over the author's
  **non-archived** memos in that book — the working list — and that an archived row may therefore share
  an ordinal with a live one, inertly, because an archived row is never in the list. Record that this
  is what preserves the section's own stated invariant (**no two live rows share an ordinal**, so the
  list read needs no `(ordinal, id)` tiebreak) while leaving the archive gap unreclaimed.
- **Reason:** The section fixes three rules — append at `max + 1`, archive leaves a gap, restore appends
  last — but never says whether `max` ranges over archived rows. Both readings preserve the invariant,
  and **three call sites converge here** (manual create, restore, `create_memo`), so an unstated choice
  is how two of them end up disagreeing. The plan resolved it (`context.md` → decision 2) and the
  resolution belongs in the doc, not only in a plan folder.

## `docs/architecture/assistant-runtime.md`

### 5. Record the repeat-state-call answer beside the memo routes' taxonomy

- **Section:** none in this file — this item belongs to **`quick-reference.md`** → the memos route
  table, and is recorded here only so the pair of status decisions stays together. Applier: put it on
  the memos route table's status-taxonomy bullet.
- **Change:** Record that **activating an already-active memo, or archiving an already-archived one,
  answers `200` with the row unchanged** — there is no `409` anywhere in this family. Reasoning: the
  memo taxonomy names no `409` at all, these four verbs are idempotent state assertions rather than
  lifecycle transitions, and the shipped precedent for the reading is `POST …/close/cancel`'s
  deliberate `200` no-op. Note explicitly that this **does not** copy `POST /books/{id}/archive`'s
  `409`, whose subject has a state machine behind it.
- **Reason:** The route table lists the four verbs and the "no `409`" absence separately; a reader
  reconciling them against `books.py`'s `409` will guess, and the two guesses are observably different
  behaviours.

---

## Status flips a finalization pass owes

- **`docs/architecture/quick-reference.md`** — the header says the memo rows "describe a design with no
  plan folder behind it yet, and are marked as such", and the memos route table, DTO subsection and
  `Memo` row are each tagged **designed**. Once this feature ships, the tag becomes as-built and the
  header sentence goes.
- **`docs/architecture/backend/book-domain.md`** — the FEAT-021 module list is marked
  **"Designed-only"**; the registry count prose ("**plus `memos` as designed for FEAT-021**") becomes
  as-shipped.
- **`docs/architecture/CLAUDE.md`** — "**Also covered, since 2026-09-15 — FEAT-021 (memos)**, designed as
  a round of its own and **not yet carried by a plan folder**" — the trailing clause becomes this
  folder's name.
- **`docs/architecture/frontend-workspace.md`** — the navigator section table already reads
  "Memos | **has data** … (FEAT-021; owner: this feature)"; "this feature" should name the plan folder.

## Operating notes — record, do not fix

- **No backfill for existing installs, by user decision (2026-09-15).** `create_memo` reaches a mode's
  `mode_tool` rows only through `DEFAULT_MODE_TOOL_NAMES` on a **fresh** install, because
  `seed_default_modes()` / `seed_default_mode_tools()` are idempotent by key. On an **existing**
  instance an administrator must add `create_memo` to the five modes **by hand** in the assistant-config
  editor; `BASE_TOOL_NAMES` covers every mode-less surface meanwhile, so the feature works there, but
  **inside the five modes it is absent until an admin acts**. `assistant-config.md` already states this
  as a known consequence of idempotent seeding rather than a defect — no re-seed, backfill or migration
  step was planned, and none should be added later without a decision. It is the same shape as
  FEAT-020's open `_TBD:` about default prompts reaching existing installs.
- **Test files this feature rewrites rather than extends.** Recorded so a reviewer reading the diff does
  not treat a changed assertion as a regression:
  - `backend/tests/services/test_prompt_composition.py` — "all **four** layers in fixed order" becomes
    five, memos fourth. Its third-positional-`author` assertion **survives**.
  - `backend/tests/services/test_chapter_prompt_composition.py` — the chapter prompt is the **fifth**
    layer now, not the fourth.
  - `backend/tests/services/test_subagent_delegation.py` — the nested system is the sub-agent's prompt
    **plus the `MEMOS` section**, not the prompt alone. The surviving half is that no mode, author or
    chapter layer threads through.
- **`docs/plans/roadmap.md` carries no row for this feature**, and this plan did not add one — the
  roadmap is `/roadmap`'s file. Whoever runs `/roadmap` next should place `026.memos` in a stage with
  its track, size and the FEAT-021 ids it delivers. There is also no `brief.md` in this folder, by the
  same ownership rule.
- **Two FEAT-021 stories are deliberately undelivered here** and will need citing by the features that
  own them: **US-133** (a clone carries the cloner's memos) by **FEAT-015**, and **US-134** (the
  moderation view excludes memos) by **FEAT-011**. Both designs already exist —
  `domain-book.md` → "The clone copies the cloner's memos" and `authorization.md` → "The admin
  boundary" — and neither feature is built, so neither is drift.
- **`docs/product/` FEAT-021's status stays `proposed` until `/product-spec` finalizes it.** Writing the
  `**Delivered:**` marker is `/product-spec`'s alone, per `docs/product/CLAUDE.md` → "Citation
  convention"; nothing in this plan edits `docs/product/`.

---

## Observations

- Step 008: **`ToolContext`'s field count is stale in two architecture documents.**
  `docs/architecture/assistant-config.md` and `docs/architecture/quick-reference.md` both state that
  `ToolContext` "stays **six** fields", but `backend/app/services/tools.py` has **seven** —
  `codex_creates_this_turn` was added by a later fast feature and never recorded. Step 008 does not
  change the count (it needed no new field: `book_id` and `access` were already there) and did not
  touch the docs, `docs/architecture/` being the architect's domain. Possible impact: a finalization
  pass should correct "six" to "seven" in both files and name `codex_creates_this_turn` in the field
  list, so the next reader counting fields against the code does not read the mismatch as this
  feature's doing.

- Step 011: **an alert cannot be named by an `aria-label` and a Mantine `title` at once — pick one.**
  The `## Skeleton` record for step 011 and `MemosListPage.tsx`'s docstring both described the
  list-level reorder alert as carrying a `title` headline **plus** an `aria-label` `Reorder error`.
  Those two are not jointly satisfiable: Mantine's `Alert` renders `title` as a headline and wires
  `aria-labelledby` to it, and `aria-labelledby` wins the accessible-name computation, so the
  `aria-label` is inert and the surface is unreachable under its contracted name — which is what
  produced the first DoD-6 failure. The implementation follows step 010's `MemoRow` shape
  (`aria-label`, **no** `title`, the headline rendered as the alert's own first line); the headline
  wording, the author-facing content and every frozen signature are unchanged, so this is
  **record-vs-code wording drift, not a contract breach**, and the `## Skeleton` record was left as
  the skeleton wrote it. Both coherent shapes exist in the codebase and the next author should pick
  deliberately: `MemoRow` / this alert are named by `aria-label` with no `title`, while
  `ChaptersPage`'s reorder alert is named by its `title` headline with no `aria-label`. Possible
  impact: a line in `docs/architecture/frontend.md` (or `frontend-workspace.md`'s accessible-name
  guidance) stating that an alert with a contracted accessible name uses exactly ONE naming
  mechanism, never both.

