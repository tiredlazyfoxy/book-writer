# 015.chapter-writing-free-mode — feature context

Feature-wide context. Step-specific facts live in each `<SSS>.context.md`; nothing is repeated
between the two files.

`brief.md` (written by `/roadmap`) is the feature *definition* and is **read-only** here. Its Scope
In/Out bounds this plan — **except** that decision **D4** below deliberately **widens** it: the brief
scopes out "composing blocks by chatting with the assistant", and this feature builds exactly that.
Re-scoping the brief is `/roadmap`'s and is carried in `outcome.md`.

---

## CRITICAL — this is a plan-on-plan dependency

**`014.chapter-skeleton` is planned but entirely unimplemented.** All eight of its steps are
`pending`; no line of its code exists. Its DTOs, its service entry points, its `api/chapters.ts`
functions, its `ChapterPage` and its skeleton signatures are **not frozen** — they are a *plan*.

This feature is written against **014's planned contract**, as documented in
`docs/plans/014.chapter-skeleton/context.md` → "The wire contract" and in its step files. Every
signature 015 extends *on the chapter side* is therefore a *design intent*, not a harvested fact.

**014 must land first, end to end, before any step of 015 is executed.** If 014's shipped contract
differs from its plan — a renamed DTO field, a different service entry point, a different form of
`resolveEditability`'s region model — the affected 015 steps must be re-planned, not improvised
around. The skeleton agent is the gate: it reads the *shipped* 014 code and freezes the real
signatures.

**The assistant-runtime side is the opposite case**: it is shipped code, and the declaration sites and
signatures recorded below are **harvested ground truth**, not intent.

### What already exists in code today (built by `008.data-domain`)

- **`backend/app/models/chapter.py`** — the `Chapter` table: `id`, `book_id`, `ordinal`, `title`,
  `state: ChapterState`, `sketch`, `text`, `summary`, `summary_status`, `system_prompt`,
  `version: int = 1`, `created_at`, `modified_at`. The `ChapterState` (`planned` / `open` / `closing`
  / `closed`) and `SummaryStatus` enums are declared here.
- **`backend/app/models/chapter_change.py`** — the `ChapterChange` table plus `PlacementKind`
  (`append` / `range`) and `ChangeStatus` (`pending` / `applied` / `rejected`). Fields: `id`,
  `chapter_id`, `author_id`, `placement_kind`, `line_from`, `line_to`, `base_version`, `text`,
  `status`, `applied_at`, `applied_by`, `created_at`.
- **`backend/app/models/chapter_text_revision.py`** — `ChapterTextRevision`: `id`, `chapter_id`,
  `applied_change_id` (**non-null FK to `chapter_changes`**), `text_before`, `applied_by`
  (non-null), `applied_at`.
- **`backend/app/db/chapters.py`** — only `create`, `get_by_id`, `list_by_book`. **No `update`** —
  014 step 001 adds it. Depend on it; do not re-add it.
- **`backend/app/db/chapter_changes.py`** — `create`, `get_by_id`, `list_by_chapter`. No `update`.
- **`backend/app/db/chapter_text_revisions.py`** — `create`, `get_by_id`, `list_by_chapter`.
- All four models are registered in `db/engine.py:_register_models`; all four JSONL codecs are
  already in `TABLE_REGISTRY`. **This feature adds no table and no codec.**
- **`backend/app/ids.py::generate_id()`** mints snowflakes, used as
  `Field(default_factory=generate_id, primary_key=True)`.
- **The service layer sets `created_at` / `modified_at`, never `db/`.**
- Every `db/` function opens its own session (`session = await get_standalone_session()`;
  `async with session: …`). **No multi-table transaction primitive exists anywhere** — see D7.

### The assistant runtime as shipped — harvested, confirmed, ground truth

Every declaration site below is confirmed against source. Steps 009, 010, 011 and 012 bind to these
and to nothing inferred.

| Thing | Where |
|---|---|
| `CanvasField = Literal["name", "body"]` | `backend/app/models/schemas/chats.py:257` |
| `CanvasFrame(BaseModel)` — `subject_kind: SubjectKind`, `subject_id: str \| None`, `field: CanvasField`, `text: str` | `backend/app/models/schemas/chats.py:260-295` |
| `TurnRequest(BaseModel)` — `prompt: str \| None`, `subject_kind: SubjectKind \| None`, `subject_id: str \| None`, `codex_kind: CodexKind \| None` | `backend/app/models/schemas/chats.py:187-216` |
| `ToolContext` — **frozen dataclass**: `book_id: int`, `access: authz.BookAccess \| None`, `subject: ResolvedSubject \| None`, `emit_frame: FrameEmitter \| None` | `backend/app/services/tools.py:93-139` |
| `ToolBinder = Callable[[ToolContext], Callable[..., object]]` | `backend/app/services/tools.py:146` |
| `emit_frame` — a per-turn closure putting a `TurnFrame(event, data)` onto a queue | `backend/app/services/chat_turn.py:493-494`; `TurnFrame` at `chat_turn.py:286-299` |
| The SSE serializer, **generic over `frame.event`** | `backend/app/routes/chats.py:224-231` |
| The **only** current `canvas` emission | `backend/app/services/codex_tools.py:689-706`, inside `write_codex_draft` |
| `determine_mode(subject) -> str \| None` | `backend/app/services/assistant_runtime.py:195-218` |
| `_CODEX_KIND_MODES` — maps `character`/`location`/`fact` only | `backend/app/services/assistant_runtime.py:104-108` |
| `allowed_tool_names(mode_key)` — `BASE_TOOL_NAMES` when `mode_key is None`, else the mode's `mode_tool` rows | `backend/app/services/assistant_runtime.py:247-274` |
| `BASE_TOOL_NAMES = ("web_search",)` | `backend/app/services/assistant_runtime.py:62` |
| `resolve_turn_tools` — concatenates real tools with sub-agent delegation tools | `backend/app/services/assistant_runtime.py:277-305` |
| `ModeTool` — `mode_key` FK → `assistant_modes.key`, `tool_name`, unique pair | `backend/app/models/mode_tool.py:21-42` |
| `db/mode_tools.py::list_by_mode` | `backend/app/db/mode_tools.py:36-43` |
| Frontend twins — `CanvasField`, `CanvasFrame`, `TurnRequest`, and a **frontend-only** `TurnSubject` helper with no backend counterpart | `frontend/src/types/chats.d.ts:172`, `:191-196`, `:159-164`, `:144-148` |

**Five consequences that shape this plan and are not negotiable:**

1. **`determine_mode` has no chapter branch at all.** Its body is
   `if subject.entry is None: return None` / `return _mode_for_codex_kind(subject.entry.kind)`, and its
   own docstring says the `write-chapter` / `close-chapter` modes "belong to `015` / `016`". Step 009
   **adds** that branch; "already correct, no change" is not a possible outcome there.
2. **`TurnRequest` has no single subject field** — three flat optional fields. The selection joins them
   as a **fourth flat field**, not as a member of a subject object. The frontend's `TurnSubject` helper
   interface is a client-side convenience with **no backend counterpart** and gains nothing.
3. **`ToolContext` already carries `access: authz.BookAccess | None`** — so the chapter tools' refusal
   mirror gets the caller's role, the book's state and its collaboration mode with **no new plumbing**.
   D10's and D11's assistant-side mirrors cost one field read each.
4. **`CanvasField` needs no change.** A chapter's body **is** the `"body"` field — the same principal
   text field the codex entry uses and the same one the restore buffer's principal-text-field rule
   names. `"name"` never applies to a chapter. **Do not widen `CanvasField`.**
5. **`CanvasFrame` is declared in `models/schemas/chats.py`, not in `codex_tools.py`.** The single
   codex emission at `codex_tools.py:689-706` is therefore a **regression surface** for this feature,
   not a file it edits.

### What does not exist and is 014's to create (015 only extends it)

`services/chapters.py`, `routes/chapters.py`, `models/schemas/chapters.py`,
`frontend/src/api/chapters.ts`, `frontend/src/types/chapters.d.ts`, `ChapterPage.tsx`,
`chapterPageState.ts`, `ChaptersPage.tsx`, `chaptersPageState.ts`, `BookHubPage.tsx`,
`models/chapter_author_prompt.py`, `db/chapter_author_prompts.py`, and `db/chapters.py`'s
`update` / `delete`.

### Frontend facts that are harvested and real today

- **`frontend/src/work/restoreBuffer.ts`** is complete: `restoreBufferKey(bookId, subjectKind,
  subjectId)`, `readBuffer(key)`, `writeBuffer(key, draft, baseVersion)`, `clearBuffer(key)`.
  `BufferBaseVersion = number | string` — **the number case exists precisely for `Chapter.version`.**
  `WriteResult` carries `saved` / `saved-after-eviction` (with `evictedKeys`) / `failed`.
- **`frontend/src/work/subject.ts`** — `SubjectKind` already includes `"chapter"`; a `ChapterState`
  union is already declared; `LoadedSubject` carries `chapterState?` but **no body version field**.
  `resolveEditability`'s chapter branch today returns `editable: "whole"` for `open` only. 014 step
  008 widens it for `planned`; **015 widens it again for the body region.**
- **`frontend/src/work/contentSubject.ts`** — `registerContentSubject(source, applyDraft?)`,
  `unregisterContentSubject(source)`, `currentContentSubject()`, `dispatchCanvasFrame(bookId,
  frame)`. **`dispatchCanvasFrame` is hardcoded to codex**: it buffers dropped frames under
  `restoreBufferKey(bookId, "codex-entry", frame.subject_id)`, and its buffer fallback fires only for
  the `"body"` field. The **key** is what has to generalize; the field check does **not**, because a
  chapter's body is also the `"body"` field (consequence 4 above).
- **`frontend/src/api/client.ts`** — `ApiError { status, details }`; callers detect a 409 via
  `err instanceof ApiError && err.status === 409`. `CodexEntryPage` parses refusal text with a
  `serverRefusalText(err)` helper reading `err.details.detail.message` / `.reason`.
- **`frontend/src/work/pages/codexEntryPageState.ts` + `CodexEntryPage.tsx`** (262 lines) are the
  template for an editable subject: the async trio, a separate `saveStatus` / `saveError`,
  `conflictEntry` + `isReconciling`, `evictedBufferKeys`, a bound `applyDraft` excluded from
  `makeAutoObservable`, and external effects `loadCodexEntry` / `editCodexDraft` / `saveCodexEntry` /
  `discardCodexDraft` / `resolveCodexConflict(state, side, signal?)`.
- **`backend/app/services/tools.py`** — `ToolDef(name, description, args_schema, callable=None,
  binder=None)` and `TOOL_REGISTRY: list[ToolDef]`; exactly one of `callable` / `binder` per entry.
- **`backend/app/services/codex_tools.py::_refuse_write(context, field) -> str | None`** returns a
  **tool string the model reads**, never raises — a raising tool aborts the turn.
- **`backend/app/services/codex.py::update_entry`** is the concurrency template: compare the expected
  token, raise a typed `*Error`, **write the history row BEFORE mutating**, re-stamp `modified_at`.
  `routes/codex.py` holds a `_CODEX_ERROR_STATUS: dict[Reason, int]` + `_map_codex_error` + a
  try/except chain per handler.

---

## Goal

**The open chapter becomes writable — by the author, and by the assistant into the author's draft.**

An owner opens a planned chapter (only one open at a time), the book's members write its body as
Markdown in a rich-text editor in the content pane, save it whole against a version token with the
`409` + restore-buffer reconciliation contract, the owner closes it, and the owner reopens a closed
one. Alongside that, the assistant gets three chapter write tools and a read path that reach the
author's **draft** through `canvas` frames and never touch the database.

Delivers **FEAT-009**: UC-035, UC-036 (partly — see "The close seam"), UC-037, UC-038, UC-039;
US-036, US-037, US-038 (AC-1/AC-2/AC-4), US-039, US-040, US-041.

---

## Design decisions the user has locked — do not reopen

### D1 — two layers: versioning is whole-body and happens on SAVE; editing is where append/replace lives

This resolves the apparent conflict between UC-038 ("append a block") and UC-039 / US-041 ("edit a
body"). The server stores the current `Chapter.text` plus every previously saved state as
`ChapterTextRevision` snapshots. **A save carries the whole body plus `expected_version`; a stale one
is refused `409`.** The append-vs-replace distinction is an **editing operation on the draft**, before
any save — performed by the author typing, or by one of the assistant's tools.

Consequence: there is exactly **one** write endpoint for chapter bodies, and it takes the whole body.
No partial/placement-addressed write reaches HTTP.

### D2 — the content pane holds a whole-body Markdown editor for the `open` chapter

**`Chapter.text` is Markdown.** Migration cost is zero: the column exists and nothing writes it today.

**Markdown stops at chapter text.** The codex entry body is untouched and **`CodexEntryPage` is not
reworked by this feature.**

### D3 — the editor is `@mantine/tiptap`

Mantine's `RichTextEditor` over TipTap/ProseMirror, plus **`tiptap-markdown`** for serialize/parse.
This is a new frontend dependency set — the second in the project, after 014's `@dnd-kit`.

**Pin the TipTap major that `@mantine/tiptap` declares as its peer range for the Mantine version in
`frontend/package.json`. Read that range; do not assume it.** Step 005 makes this a checkable
criterion rather than a version string I guessed.

*Reasoning to keep:* TipTap is the dominant React rich-text editor and `@mantine/tiptap` inherits the
app's theme for free. **Milkdown** was the alternative — it is exact-Markdown by construction — and it
was rejected because its theming cost outweighs a round-trip whose **worst case is cosmetic**: the
whole body is re-saved every time (D1), so an imperfect slice round-trip cannot corrupt stored data,
and the author sees the rendered result before saving.

### D4 — the assistant tools ARE in scope; this feature absorbs them

The user was explicit: *"the editor has no sense without the tools."* Two things follow and both are
recorded in `outcome.md` rather than glossed:

1. This **widens `brief.md`**, which scopes out "composing blocks by chatting with the assistant"
   (`/roadmap`'s to re-scope).
2. This **designs the chapter shared-canvas write protocol**, which `docs/architecture/CLAUDE.md` and
   `assistant-runtime.md` → "Out of scope" both list as deliberately undesigned (`/architect`'s to
   absorb into `assistant-runtime.md`).

Three write tools plus a read path, registered as `ToolDef`s, emitting `canvas` frames that the
content pane applies to its **draft** — nothing reaches the server until the author saves, exactly as
`write_codex_draft` behaves:

| Tool | Does |
|---|---|
| `read_chapter_text` | returns the chapter's **saved** body to the model |
| `set_chapter_text` | replaces the whole body |
| `update_selection` | replaces the author's current selection |
| `add_text` | appends to the end |

Author flows designed against: *"rewrite the last paragraph, make it X"*; select text then *"rewrite
this as Y"*; *"the next paragraph is about Z"*; and the variant flow — *"give me 3 variants"* → the
model writes candidates **into the transcript** → *"use v2"* → the model calls `set_chapter_text` /
`update_selection`. **The variant flow needs no new persistence** — it is this tool set plus the
transcript. FEAT-014's stored variants remain `018`'s.

**Accepted limitation, stated rather than hidden: the assistant reads the SAVED body, not the draft.**
The draft is device-local and never leaves the browser until the author saves (US-107.AC-4). So after
unsaved edits the model's view of the chapter is stale. This is a direct consequence of
draft-until-saved, not an oversight; the author saves first for best results.

#### The tools ship unreachable, and that is the designed state — not a defect

`allowed_tool_names(mode_key)` (`assistant_runtime.py:247-274`) returns a mode's `mode_tool` rows, and
**zero rows is an empty allowlist** (`assistant-config.md`, settled). **This feature seeds no
`mode_tool` rows**, so a chapter tool sitting in `TOOL_REGISTRY` is **invisible to every turn** until
an admin selects it for the `write-chapter` mode in `012.assistant-config-editor`'s mode editor.

Stated plainly so it is not discovered later: **on a fresh install the chapter editor works and the
assistant cannot write into it** until that selection is made. This is exactly the position the codex
tools have been in since `013.codex`, so it is consistent rather than a regression; changing it would
be a FEAT-020 default-policy decision, not a chapter one, and it would point the default in the unsafe
direction the empty-allowlist rule exists to avoid. Step 010 carries a `[manual/live]` criterion over
the admin-selects-then-the-tool-fires path end to end.

**The `write-chapter` mode row itself IS seeded** — see "Mode seeding" below. Only the tool
*selections* are absent.

### D5 — selection is client-side only and never persisted

Only the finished body is saved, so a selection never has to survive a request. The page tracks it and
registers it alongside the content subject (`contentSubject.ts` grows a selection beside `applyDraft`),
and the turn request carries its text as a **fourth flat field** beside `subject_kind` / `subject_id` /
`codex_kind`. **`ChapterChange.line_from` / `line_to` never expresses it** — no lossy
character-offset-to-line snapping, ever.

### D6 — undo: a fourth module-tier member, in memory, 20 deep, assistant writes only

A new module beside `restoreBuffer.ts` / `activeChat.ts` / `contentSubject.ts`, holding up to **20**
body snapshots per `(book, chapter)`.

**In memory, session-lived — not `localStorage`**: 20 chapter bodies would blow the few-megabyte quota
the restore buffer already has an eviction policy for, and evicting *other items'* drafts to hold an
undo stack is the wrong trade.

A snapshot is pushed **before each assistant-originated write is applied**. **Manual typing is left to
the editor's own native undo** — ProseMirror has a real history plugin and duplicating it would give
the author two undo stacks that disagree.

`frontend-work-drafts.md` explicitly requires a fourth member of that tier to be added *"on purpose
rather than by precedent"*. The sanction is recorded in `outcome.md`.

### D7 — atomicity: sequential sessions, codex-style. Accepted, and recorded as a divergence

The save writes `ChapterChange` + `ChapterTextRevision` + the `Chapter` update as **separate ordered
`db/` calls from the service**, exactly as `services/codex.py::update_entry` orders its version
snapshot before its entry mutation. **No cross-entity `db/` module is created**; "one `db/` module per
entity" holds.

**Write order, and why it is the one that degrades most safely:**

```
1. ChapterChange       (status = applied, base_version = expected_version, author_id = caller)
2. ChapterTextRevision (applied_change_id = the change above, text_before = the loaded body)
3. Chapter             (text = the new body, version += 1, modified_at)
```

The change must precede the revision because `ChapterTextRevision.applied_change_id` is a **non-null
FK**. The chapter update must come **last** because a body that has moved with no history behind it is
the one failure that breaks revert irrecoverably. So the forced order is also the safest one — history
before mutation.

**Accepted failure modes, stated precisely:**

- a crash after (1) leaves an `applied` change row with no revision and an **unmoved** body;
- a crash after (2) leaves a change plus a revision whose `text_before` equals the current body — a
  no-op revision, harmless to revert through;
- no ordering can leave a moved body with no history.

**`domain-chapter.md` says the three steps "are one transaction". That is now aspirational relative to
the db-layer contract**, and `outcome.md` says so plainly.

**Second accepted limitation, same class:** the version check and the write are not one transaction
either, so two saves racing with the same `expected_version` can both pass the check. The window is
milliseconds and the exposure is identical to `services/codex.py`'s. Not worth a new `db/` primitive
here.

### D8 — close is `open → closed` directly. No closing mechanics at all

The user was explicit: *"we are not implementing a closing mechanics here, it will be in feature 16."*
**Nothing in this feature writes `ChapterState.closing`**, drafts continuity, approves, or abandons a
close. `domain-chapter.md` already sanctions this — "the close gate is a Stage-4 behaviour (Stage 2
ships an ungated close, per the roadmap's explicit close-gate seam)".

**One carve-out.** The one-open-chapter guard on **open** and **reopen** tests
`state in {open, closing}`, **not `open` alone**. That is one word in a condition, not close
mechanics, and omitting it would plant a bug for 016: a chapter parked in `closing` would let the
owner open a second one.

- **US-038.AC-3 is `016`'s. No DoD item in this feature may cite it.**
- **US-038.AC-4 IS covered here**, tested against a chapter seeded directly into `closing` through
  `db/chapters.py`.

### D9 — one `ChapterChange` row per save, with a computed placement

`ChapterTextRevision.applied_change_id` is non-null, so every revision needs a change row. Write
**exactly one per save**:

- **`placement_kind = append`** when the new body **starts with** the loaded body (pure growth at the
  end). `line_from` / `line_to` stay null. The change's `text` is the appended remainder.
- **`placement_kind = range`** otherwise, with **`line_from = 1`** and **`line_to` = the line count of
  the loaded body**. The change's `text` is the whole new body.

This exercises both enum members honestly and gives `018` a readable "appended" vs "revised" history.
`base_version` is the `expected_version` the client sent. `status = applied` immediately (free mode),
with `applied_at` / `applied_by` stamped. `author_id` is the caller — **this is where US-040.AC-2
attribution lives.**

**Degenerate cases, fixed here so no step invents its own answer:**

| Case | Result |
|---|---|
| loaded body is `""` | every string starts with `""` → **append**, change text = the whole new body. The first write into a chapter is an append, which is right. |
| new body is `""`, loaded body is not | does not start with the loaded body → **range**, `line_from = 1`, `line_to` = the loaded body's line count, change text `""`. The author cleared the chapter. |
| new body **equals** the loaded body | starts-with holds → **append** with change text `""`. The save still snapshots and still bumps the version. No "unchanged" short-circuit is added — one rule beats a special case, and the client already gates the control on dirtiness. |
| line count | `len(loaded_text.splitlines())`. The `range` branch is unreachable when the loaded body is `""`, so `line_to` is always ≥ 1 and **no clamp is needed** — do not add one. |

### D10 — archived books refuse writes

`authorization.md` → "Not settled by this pass" parks this explicitly for "the write features", and
**015 is the first feature that writes book content.**

Every **body save** and every **state transition** (open / close / reopen) is refused when
`BookAccess.book_state` is `archived`. **Reads still work.** UC-023 says archive preserves content and
is reversible — refusing writes is what makes "preserved" mean something.

**Status: `403`**, with its own typed reason. Reasoning: `authorization.md` puts the book-state gate
*before* the matrix, alongside visibility and quarantine, and defines `403` as "a book the caller can
legitimately see, but a capability they lack". Under archive **no member holds the write capability** —
that is an access answer, not a resource-state answer, which is why it is not `409`. **This closes the
open item; `outcome.md` records the closure.**

The assistant's mirror of the same rule costs one field read: `ToolContext.access` already carries
`book_state`.

### D11 — proposal mode mirrors codex

A co-author's **body write** in a `proposal`-mode book is refused **`403`** with a typed reason naming
FEAT-010 as unbuilt — exactly as `services/codex.py::_require_writable_mode` does. **The owner is
unaffected.** FEAT-010's proposal review surface stays unbuilt.

The **assistant's** mirror of this refusal is a **tool string**, not a status
(`codex_tools.py::_refuse_write`), because a raising tool aborts the turn. `ToolContext.access` carries
`collaboration_mode` and `role`, so the mirror needs no new plumbing either.

State transitions are **not** mode-qualified — they are owner-only, and an owner is never held for
review.

### D12 — the chapter system prompt's composition IS in scope, and this changes 014's expectation

014's `outcome.md` hands composition to 015 but assumed it was blocked on *"which chapter is this turn
about"* — undesigned FEAT-013 context assembly.

**That blocker is gone in this feature.** 015 registers the open chapter as the content-pane subject,
so the turn request already carries which chapter is in view (`TurnRequest.subject_kind` /
`subject_id`, `chats.py:187-216`). Step 013 wires the **caller's own** `ChapterAuthorPrompt` (014's
table) into `services/prompt_composition.py`'s existing fourth layer, for turns whose subject is a
chapter.

**Step 013 is last and is severable**: if 014's `ChapterAuthorPrompt` half slips, every other step of
015 stands without it.

`outcome.md` records that 014's stated blocker was dissolved by **015's subject registration**, not by
designing context assembly — **context assembly itself remains undesigned and out of scope.**

---

## Decisions this plan makes on top of the locked set

Each of these was an open question the briefing left to the planner. They are decisions, not
suggestions.

### D13 — the body is a sub-resource, not a widening of `ChapterResponse`

```
GET /api/books/{book_id}/chapters/{chapter_id}/text  → ChapterTextResponse
PUT /api/books/{book_id}/chapters/{chapter_id}/text  → ChapterTextResponse
```

014's `ChapterResponse` deliberately carries **no `text`**, because "a list render must not drag whole
chapter bodies onto the wire". Widening it would undo that in one line — 014 has a single
`_to_response` mapper serving both the list and the item, so a body added for the item is a body on
every list row. A sub-resource keeps 014's DTO frozen, and it puts the body's own concurrency token
(`version`) on the resource that actually has one.

**Cost, accepted:** the chapter page issues two GETs (the chapter, then its body). The working page
already does this deliberately elsewhere — "the Book-state landing view fetches the book again for
itself" (`frontend-workspace.md`).

### D14 — no caller-relative affordance hint on the body resource

`ChapterTextResponse` carries **no `can_write`** and `ChapterResponse` gains **no `can_manage_state`**.
014's `can_reorder` is justified precisely because a **list envelope** is "the answer to *this*
caller's request"; a body representation is not an envelope, and 021 refused a caller-relative field on
a resource representation for a reason that applies here unchanged.

Consequences the client lives with, both following `013.codex`'s shipped precedent (the collaboration
mode is applied **server-side** and `subject.ts` needed no change):

- the body editor is enabled on `state === "open"` alone;
- the open / close / reopen controls are rendered for every member, gated on **chapter state only**;
- a co-author's refused transition, a proposal-mode refusal and an archived-book refusal all arrive as
  a **`403` the page surfaces**, exactly as `CodexEntryPage` surfaces the proposal-mode refusal today.

Accepted cost: a co-author sees an Open control that will be refused. The alternative — a caller-role
field on a resource representation, or a third fetch — is worse on the rules this project already
enforces.

### D15 — the editor re-syncs by remount, not by an effect or an imperative handle

An assistant write, an undo, a buffer restore and a reconciliation choice all change the body draft
**from outside the editor**. TipTap owns its own document, so it must be told.

`frontend.md` forbids `useEffect` in leaf components and forbids prop-watching effects outright. The
answer is the repo's own idiom one level down: **the editor is keyed on a counter the page bumps on
every external draft write**, so React remounts it and TipTap re-initializes from the new content.
Keystrokes originate *inside* the editor and never bump the counter.

This costs **zero** effects, zero autoruns and zero imperative refs. Its one visible cost — the caret
position is lost when the assistant writes — is arguably correct: the author should look at what
changed.

### D16 — a read-only chapter body renders through `react-markdown`, not a disabled editor

`closing`, `closed` and `planned` chapters render their body with `react-markdown` (already a
dependency, already the repo's markdown renderer). The TipTap editor is mounted **only** when the
chapter is `open`.

This removes the entire `editable`-toggling problem from D15, keeps a heavy editor out of the read
path, and matches `frontend.md`'s note that `react-markdown` ships with **no plugins configured** —
that no-plugin default is inherited here, not re-decided.

### D17 — the `canvas` frame gains an `op` discriminator, defaulted to `replace`; `CanvasField` is untouched

Chapter tools express **relative** operations (`append`, `replace_selection`) that a whole-field frame
cannot encode. `CanvasFrame` (`chats.py:260-295`) therefore gains **`op: replace | append |
replace_selection`**, defaulted to `replace`.

The default is what makes this free: **every existing codex emission is unchanged** — there is exactly
one, at `codex_tools.py:689-706` — **and no codex emission site is edited.** On the client, the
registered `applyDraft` callback's *type* widens to a third optional parameter, and a two-parameter
implementation is assignable to a three-parameter type in TypeScript, so **`CodexEntryPage` needs no
change either** (D2).

**`CanvasField = Literal["name", "body"]` (`chats.py:257`) stays exactly as it is.** A chapter's body
**is** the `"body"` field — the same principal text field the codex entry uses. `"name"` never applies
to a chapter, and inventing a `"text"` member would give one concept two names across two subjects.

The alternative — encoding the operation inside `field` as `"text.append"` — was rejected for the same
reason `domain-chapter.md` gives for storing placement as a discriminator plus columns: a discriminator
keeps "which part is meaningful" answerable **without parsing**.

### D18 — a relative frame with no registered target is dropped, not buffered

`dispatchCanvasFrame`'s fallback writes a dropped frame into the restore buffer. That only works for a
**whole-field** write: `append` and `replace_selection` are relative to a draft the dispatcher does not
have, and the module never loaded the chapter, so there is nothing to relate them to.

Therefore: with no registered target, a chapter frame with `op = replace` is **buffered** (under
`restoreBufferKey(bookId, "chapter", subject_id)`, inheriting whatever base version already sits at
that key, `""` when there is none); `append` and `replace_selection` frames are **dropped and logged**.

This is the same shape as the existing sanctioned rule — "a non-principal field written while the
subject is not open is lost" (`frontend-work-drafts.md`) — and for the same reason: writing at a
location nobody chose is worse than not writing.

### D19 — open / close / reopen live on the chapter item page only

One surface per action, following 014's **D2** ("the Book hub READS, the working page EDITS"). The
controls go on `/work/:bookId/chapter/:id`, which already loads the chapter. The chapters **list** and
the Shell **book hub** stay exactly as 014 ships them — `ChaptersPage.tsx`, `chaptersPageState.ts`,
`BookHubPage.tsx` and the navigator are in **no** step's source list.

---

## Mode seeding — checked, not assumed

**The `write-chapter` `AssistantMode` row is already seeded. No step in this feature seeds a mode, and
no step may add one.**

`assistant-config.md` → "AssistantMode — the fixed five, seeded" and "Persistence and registry
obligations" are explicit and are recorded there as-built:

- `AssistantMode.key` is the **primary key**, a string in the fixed set
  `{edit-character, edit-location, edit-fact, write-chapter, close-chapter}` — *"a **fixed system set,
  not admin-creatable**"*, seeded once at instance setup;
- `seed_default_modes()` writes all five rows and is wired into **`services/setup.py::create_database`**
  and — added by `012.assistant-config-editor` — into **`import_database`**, so both first-run paths
  seed;
- it is **idempotent by `key`**, which is the whole reason the PK is a natural key rather than a
  snowflake.

`_CODEX_KIND_MODES` (`assistant_runtime.py:104-108`) mapping only three of the five is **not** evidence
that the other two are unseeded — it is the *codex* mapping, and `write-chapter` / `close-chapter` are
precisely the two the missing chapter branch (step 009) is for.

Because `determine_mode` returning a key with no matching row is a **silent** failure — the mode-prompt
lookup and the `mode_tool` lookup would both come back empty, the turn would run with base tools and no
mode prompt, and nothing would error — **step 009 carries a `[test]` DoD asserting that a freshly
initialised database has an `AssistantMode` row keyed `write-chapter`.** That converts the claim above
from documentation into a checked fact at the exact place it matters, for the cost of one assertion.

---

## The wire contract added by this feature

Ids are **`str` in every DTO**. **`version` is an ordinary small int and stays a JSON number** — it is
a counter, not a snowflake, so the string-id rule does not reach it.

### New DTOs (added to `backend/app/models/schemas/chapters.py`)

**`ChapterTextResponse`** — `chapter_id` (`str`), `state` (`planned|open|closing|closed`), `text`,
`version` (`int`), `modified_at`.

*Why `state` is on the body response:* the body region must be able to gate itself without depending
on which of the page's trios resolved first, and the version and the state that qualify a save must
arrive together or the client can compose a save against a chapter it believes is open and is not.

**`UpdateChapterTextRequest`** — `text` (required; `""` is valid), `expected_version` (`int`,
required).

State transitions reuse **014's `ChapterResponse`** and its `_to_response` mapper — they change
`state` and nothing else, and minting a transition DTO would give the same row two representations.

### Endpoints added

```
GET  /api/books/{book_id}/chapters/{chapter_id}/text     → 200 ChapterTextResponse
PUT  /api/books/{book_id}/chapters/{chapter_id}/text     → 200 ChapterTextResponse
POST /api/books/{book_id}/chapters/{chapter_id}/open     → 200 ChapterResponse
POST /api/books/{book_id}/chapters/{chapter_id}/close    → 200 ChapterResponse
POST /api/books/{book_id}/chapters/{chapter_id}/reopen   → 200 ChapterResponse
```

`POST` for the transitions because they are **commands with no body**, not representations to replace;
`PUT` for the body because it **replaces** the whole resource, which is exactly D1.

### Assistant-side wire changes

- `CanvasFrame` (`chats.py:260-295`) gains `op`, defaulted to replace. **`CanvasField` unchanged.**
- `TurnRequest` (`chats.py:187-216`) gains an optional selection text as a **fourth flat field**.
- `ToolContext` (`tools.py:93-139`) gains the selection text as a fifth field.
- `ResolvedSubject` gains a chapter member beside its existing `entry`, so `determine_mode` and the
  chapter tools can reach the resolved chapter row.
- Frontend twins in `frontend/src/types/chats.d.ts` mirror the frame (`:191-196`, **step 011**) and the
  turn request (`:159-164`, **step 012**). The frontend-only `TurnSubject` helper at `:144-148` **gains
  nothing** — the selection is not part of the subject.

### Capabilities added to `services/authz.py`

`authorization.md`'s chapter matrix already fixes the roles. 014 adds four members; these are the
**two** additional ones, one per matrix **row**:

| Capability | Owner | Co-author | Reader |
|---|---|---|---|
| **Open / close / reopen a chapter (UC-035..037)** | ✓ | — | — |
| **Write into the open chapter (UC-038)** | ✓ | ✓ *(mode)* | — |

Open, close and reopen are **one row in the matrix**, so they get **one** `Capability` member — the
same 1:1-with-the-matrix discipline 014 used.

**The `(mode)` qualifier is not expressible in `_CAPABILITY_MATRIX`** (it maps capability → role set
and has no vocabulary for the book's collaboration mode). It is layered in the **service**, the
established pattern from `013.codex` and `011.chat-panel`. The same is true of the archived-book gate:
`BookAccess` carries `book_state`, and the refusal is a service-level check, not a matrix row.

### Status taxonomy

Inheriting 014's and `authorization.md`'s:

| Situation | Status |
|---|---|
| No token | `401` |
| Private book, caller has no relationship | `404` — produced by `book_access`, **never re-derived** |
| Chapter that does not exist, or belongs to another book | `404` — the service's own resolver (014's D4) |
| Capability failure (reader; co-author on a transition) | `403` |
| Co-author body write in a `proposal`-mode book | `403` — typed reason naming FEAT-010 (D11) |
| Any write or transition on an `archived` book | `403` — typed reason (D10) |
| Stale `expected_version` | `409` |
| Body write to a chapter that is not `open` | `409` |
| Open while another chapter is `open` or `closing`; open a non-`planned` chapter | `409` |
| Reopen a chapter that is not `closed`; reopen while another is `open` or `closing` | `409` |
| Close a chapter that is not `open` | `409` |
| Malformed body | `422` |

**`409` and not `403` for every state-machine refusal**, for the reason 014 fixed: the caller *has*
the capability; the resource is in the wrong state. `domain-chapter.md` is explicit that the
one-open-chapter rule and the write-refusal rules are "state-machine constraints, not authorization",
and that being the owner does not bypass them.

### New service reason members (on 014's `services/chapters.py` error enum)

`chapter_not_open`, `chapter_not_closed`, `another_chapter_open`, `stale_version` → **409**;
`book_archived`, `proposal_mode_refused` → **403**.

014's existing `not_planned` reason is **reused** for the open transition (a chapter that is not
`planned` cannot be opened) — the error carries `(reason, message)`, so the message differs at each
call site while the status mapping stays in one place. Do not mint a second reason for it.

---

## The close seam, made explicit (`brief.md`'s open question)

`brief.md` asks the planner to keep the close seam explicit. It is:

- **Today (015):** `POST …/close` requires `state == open` and writes **`closed`** directly. Nothing
  reads or writes `closing`; no continuity is drafted; no approval is required.
- **016 changes exactly two things:** the transition's destination becomes `closing`, and a second
  approval endpoint moves `closing → closed` after the owner approves the drafted continuity
  (UC-047 / UC-048, US-038.AC-3).
- **What 015 deliberately builds now so 016 does not have to retrofit it:** every one-open-chapter
  guard already tests `state in {open, closing}` (D8); the body-write refusal already refuses a
  `closing` chapter through the same `chapter_not_open` reason; and step 009's chapter branch of
  `determine_mode` already maps a `closing` chapter to the seeded `close-chapter` mode.

## Known product gaps — stated, not papered over

- **US-038.AC-3** — `016`'s, per D8. **Cited nowhere in this plan.**
- **US-040.AC-4** — "both members' blocks end up in the chapter". Under whole-body saves this is
  satisfied by **the author reconciling**, not by an automatic merge. Precisely:
  - what the system guarantees automatically is (a) the later save is **refused** rather than
    overwriting, (b) the author is **shown** the server's body against their own draft, and (c) a save
    re-issued against the **current** version lands and becomes the body;
  - what the system does **not** do is merge. `domain-chapter.md` is explicit — "there is no automatic
    merge at MVP" and reconciliation "takes one side whole". So the criterion holds **when the author
    composes the merged body**, which is the reconciliation flow's designed outcome, not a side effect.
  - The DoD that cites US-040.AC-4 therefore tests the mechanism end to end: A's stale save is refused,
    A re-issues a body containing both members' text against the current version, and the stored body
    contains both. That is the honest scope of the criterion under this design.
- **The assistant tools and the chapter canvas protocol (D4)** have their product home in FEAT-013 /
  UC-054 / UC-055, which the roadmap parks under "Mapped later". Their DoD items are therefore
  **self-contained verifiable criteria citing no id** — the same convention `014` used for the
  chapter-prompt half and `021` for the book half.
- **UC-036 is only partly delivered** (its steps 3–5 pass through `closing`). US-038.AC-1 is delivered
  whole; US-038.AC-3 is not delivered at all.

---

## Out of scope — state it, do not build it

| Excluded | Owner |
|---|---|
| `closing` state, continuity drafting, the close approval gate | `016.chapter-close-continuity` |
| Summaries, `Chapter.summary`, `summary_status`, state notes, flags | `016` |
| Variants, the Variants view, reading `ChapterTextRevision` back, revert, diff | `018.chapter-history-variants` |
| Proposal review (holding a co-author's change as `pending`, applying it) | FEAT-010, unbuilt — D11 refuses instead |
| Any `ChapterChange` with `status = pending` or `rejected` | FEAT-010 / `018` |
| Vector-indexing chapter text | nobody yet — `retrieval.md`'s `VECTOR_SOURCE_REGISTRY` holds `CodexEntry` only; adding chapters is a retrieval decision, not a chapter one, and is not roadmapped here |
| Reworking `CodexEntryPage` or the codex body to Markdown | nobody — D2 |
| Widening `CanvasField`, or adding a `"text"` field member | nobody — D17; a chapter's body is the `"body"` field |
| Editing `services/codex_tools.py` at all | nobody — `CanvasFrame` is declared in `models/schemas/chats.py`; the codex emission is a regression surface, not a scope |
| Seeding an `AssistantMode` row | nobody — all five are already seeded; see "Mode seeding" |
| Seeding `mode_tool` rows for the chapter tools | nobody — D4; the admin selects them |
| Token-level canvas streaming, or a manual `chat`-in-a-loop driver | still deferred (`assistant-runtime.md`) |
| Context / content assembly (US-057, UC-085/086/078) | still undesigned — D12 dissolves only the *subject* question |
| The Reader SPA (`/read`) chapter view | UC-029; not roadmapped here |
| Editing a chapter's `sketch`, `title`, `ordinal`, or removing a chapter | `014` — shipped there, untouched here |
| A `chapter_access` dependency or any chapter→book resolver in `authz` | nobody — 014's D4 |
| A new table, a new JSONL codec, a migration statement | nobody — every table this feature writes already exists and is registered |
| Rewriting `docs/product/`, `docs/architecture/`, or `brief.md` | `/product-spec`, `/architect`, `/roadmap` — carried in `outcome.md` |

---

## Cross-cutting backend constraints (steps 001–003, 009, 010, 013)

- **Four-layer separation is enforced.** `routes/` is HTTP only — parse, call one service, return;
  `services/` holds logic and may never touch a session, `select()`, `session.add()` or
  `session.exec()`; `db/` is session-free, one module per entity, no ORM type leaking out; `models/` is
  tables plus `models/schemas/` DTOs with no logic. Direction: `routes → services + db`,
  `services → db`, `db → models`. Namespace imports throughout
  (`from app.db import chapter_changes` → `await chapter_changes.create(...)`).
- **`authz.require(access, Capability.X)` is the first line of a guarded service function**, before any
  db read — `services/books.py`'s idiom. The archived gate (D10) and the mode gate (D11) come
  immediately after it and before any db read. Both refusals are `403`, so the ordering between them is
  not observable in status; keeping `require` first keeps every guarded function in this codebase
  shaped the same way.
- **The error idiom**, copied from `routes/books.py` + `services/books.py` and already established by
  014: a `*ErrorReason(str, Enum)` and a `*Error(Exception)` carrying `(reason, message)` in the
  **service**; a module-scope `_*_ERROR_STATUS: dict[Reason, int]` and a `_map_*_error(err) ->
  HTTPException` in the **route**; every handler wraps its one service call in
  `try/except authz.BookAuthorizationError → _map_authz_error` then `except <Domain>Error →
  _map_*_error`.
- **DTOs are hand-mapped by a private `_to_response` in the service. ORM objects never reach a caller.**
- **Timestamps are the service's, not `db/`'s.**
- **No new table, no codec change, no migration statement.** The ADDITIVE MIGRATION SEAM stays `pass`.
- **Response models are the handler's return annotation, never `response_model=`.** The `{book_id}`
  path parameter is consumed entirely by `Depends(book_access)` and is not re-declared by handlers.
- **A tool never raises.** Every refusal and every failure inside a `ToolDef` callable comes back as a
  short string the model reads (`codex_tools.py`'s rule) — a raising tool aborts the turn.

## Cross-cutting frontend constraints (steps 004–008, 011, 012)

- **`observer` on every component**, no exceptions. State is observable data plus pure `get` computeds;
  every effectful operation is an external `(state, args, signal)` function using `runInAction`; every
  loadable is an async trio (`x` / `xStatus: "idle"|"loading"|"ready"|"error"` / `xError`).
- **No custom `useX` hooks**, no `useCallback` / `useMemo` / `useReducer`, no React context, no Mantine
  `useForm`, no runtime schema validation. `useState` only to own a stable state instance; `useEffect`
  only at page level, mount-load / unmount-abort. **A library's own hooks (`useEditor`) are not a
  breach** — the rule forbids authoring hooks, not consuming a library's API; 014 recorded the same
  reading for `@dnd-kit`.
- **All HTTP lives in `src/api/`**; `signal?: AbortSignal` is always the trailing argument. DTOs are
  hand-written `.d.ts` in `src/types/`, wire-exact `snake_case`, ids typed `string`, no `any`.
- **The backend is the source of truth** — after a save the surface shows what the server returned, not
  the optimistic draft. No optimistic mutation anywhere.
- **Form state shape:** the `021` shape — a draft field, a separate `…ServerErrors: Record<string,
  string>` holder, a `…SubmitStatus`, and pure `get` computeds for dirtiness and submittability. The
  body editor has **no client-side validation layer** (every string, `""` included, is a valid body),
  so it carries `…ServerErrors` with **no `clientErrors` and no `errors` union**.
- **The restore buffer is consumed, not modified.** `frontend/src/work/restoreBuffer.ts` is complete
  and unit-tested and appears in **no** step's source list.

## Testing facts shared by every step

**Backend (001–003, 009, 010, 013)** — tests live under `backend/tests/{db,services,routes}/`.
`asyncio_mode = "auto"`, so async tests need no decorator. `conftest.py` provides `_reset_db_ready`
(autouse), `db`, and `http_client` (the real `app.main.app` over `httpx.ASGITransport`, DB isolated via
`BOOKWRITER_DB_PATH` + `Settings.get_settings.cache_clear()`, real lifespan).

**Domain seeding helpers are per-file, not shared fixtures** — `_now()`, `_auth_header(token)`,
`_seed_user(...)`, `_seed_author(username) -> (User, token)`, `_create_book(http_client, token, …)`,
`_add_co_author(book_id, user_id)`. Copy them from `backend/tests/routes/test_book_settings.py`.
**Auth in route tests is real** — seed a user row and mint a real JWT. Service-layer specs construct
`BookAccess` directly (a frozen dataclass) and seed supporting rows through the sibling `db/` modules
with the `db` fixture. **No network in any test** — no LLM server is ever reached; the tool steps
exercise tool callables directly rather than through a live turn.

**A chapter in a given state is seeded by writing it through `db/chapters.py`.** 015 ships the
transitions, but a spec for the *body* path must not depend on the transition path to reach `open`, and
a `closing` chapter can only be produced this way at all (D8).

Test naming: `test_<behavior>__DoD<N>_<US-id>_<AC-id>`, with the product ids omitted where a DoD item
has none (the whole assistant-tools half).

**Frontend (004–008, 011, 012)** — `frontend/tests/` mirrors `src/` (`admin/`, `work/`, `user/`) plus
`support/render.tsx` (`renderWithProviders(ui, { route? })`, wrapping `MantineProvider theme env="test"`
+ `MemoryRouter`) and `support/sseFixture.ts`. `vitest.config.ts` is jsdom with **`globals: false`**, so
every spec imports `describe` / `it` / `expect` / `vi` from `"vitest"`.

The idiom: **whole-module `vi.mock("../../src/api/<mod>", () => ({ … }))` enumerating every export the
subject imports** — a missing export fails for the wrong reason. `beforeEach` re-arms `vi.mocked(...)`.
A local `renderPage(route)` wrapper around `renderWithProviders` supplies a `<Routes><Route path=… /></Routes>`
shim. **Queries are by role or label only, never test-ids.** `ApiError` is imported real from
`../../src/api/client`.

### The one testing decision this feature has to make

**Page specs mock the editor component, not just the api modules.** ProseMirror requires DOM APIs jsdom
does not implement (`Range.getClientRects`, layout rectangles), so driving real typing and selection
inside TipTap under Vitest is unreliable in a way that would make every page spec flaky for reasons
unrelated to the page.

Therefore:

- `frontend/src/work/components/chapter/ChapterBodyEditor.tsx` has a **frozen prop seam** (step 005),
  and steps 006 / 007 / 012 mock that module the same way they mock an `api/` module, substituting a
  trivial stub that renders a labelled control and calls `onChange` / `onSelectionChange`.
- The editor's own behaviour — real Markdown round-tripping, real selection, real toolbar — is covered
  by **`[manual/live]`** criteria in step 005, not by pretend assertions.
- `vitest.config.ts` and `frontend/tests/support/` are in **no** step's source or test list. A spec that
  needs a DOM stub installs it at the top of its own file.

This is a deliberate extension of the whole-module-mock idiom from api modules to one component, and it
is recorded in `outcome.md` so the next heavy-widget surface finds the precedent instead of rediscovering
the flakiness.

## Build and test gates (root `CLAUDE.md` — reference only, invent nothing)

- **Backend:** `cd backend && .venv/Scripts/python -m pytest`. **There is no backend typecheck.**
- **Frontend:** `cd frontend && npm run build` (= `tsc && vite build`), `cd frontend && npm test`,
  `cd frontend && npm run test:types`. `frontend/tsconfig.json` has `include: ["src"]`, so a broken spec
  can never break the bundle; `npm run test:types` is the only program covering `tests/`.

## Architecture sources

- `docs/architecture/domain-chapter.md` — the `Chapter` field table, the state machine, CF1, the one
  write path (snapshot → apply → bump), `ChapterChange`, `ChapterTextRevision`, and the three-rule
  concurrency contract this feature implements.
- `docs/architecture/authorization.md` — `BookAccess`, resolve-in-a-dependency / decide-in-a-service,
  the chapter capability matrix, the `(mode)` layering pattern, the book-state gates, the
  `401 / 404 / 403` taxonomy, and the archived-writes open item this feature closes (D10).
- `docs/architecture/frontend-workspace.md` — the working-page route map, the content-pane editability
  table (the `open` chapter's body row this feature fills in), and the two-vocabularies rule for the
  author's refusal vs the assistant's.
- `docs/architecture/frontend-work-drafts.md` — the restore buffer design, the module tier and its
  "a fourth member is added on purpose" rule (D6), the two entrances to reconciliation, and the
  explicit note that **chapter bodies are the tier's declared next consumer** and that 015 "adopts this
  tier rather than extending it".
- `docs/architecture/assistant-runtime.md` — mode determination, the `TurnRequest` fields, four-layer
  prompt composition, tool gating's three cases, the `chat_with_tools` seam, the five-frame SSE
  vocabulary, and the codex shared-canvas write this feature mirrors for chapters.
- `docs/architecture/assistant-config.md` — `ToolDef` / `TOOL_REGISTRY` / `binder` / `ToolContext`, the
  **fixed five seeded modes** behind "Mode seeding" above, and the empty-allowlist rule behind D4's "no
  seeded `mode_tool` rows".
- `docs/architecture/frontend.md`, `docs/architecture/backend.md` — the enforced conventions above.
- `docs/plans/014.chapter-skeleton/` — **the whole folder.** 015 builds directly on its planned
  contract.
- `docs/plans/013.codex/012.codex-entry-page.md` — the closest prior-art step for an editable subject;
  its shape is copied for the body half.

## Steps

| Step | File | Layer |
|---|---|---|
| 001 | `001.chapter-body-service.md` | backend — body DTOs, two capabilities, the read/save service with D9's placement and D7's ordering |
| 002 | `002.chapter-state-transitions.md` | backend — open / close / reopen in the service |
| 003 | `003.chapter-write-routes.md` | backend — the five new handlers and their status map |
| 004 | `004.chapter-write-api.md` | frontend — body DTOs and the five `api/chapters.ts` functions |
| 005 | `005.chapter-body-editor.md` | frontend — the dependency set and the `ChapterBodyEditor` component |
| 006 | `006.chapter-page-body.md` | frontend — the body trio, the draft, the save, the editor mount |
| 007 | `007.chapter-buffer-reconciliation.md` | frontend — the restore buffer, both reconciliation entrances, eviction |
| 008 | `008.chapter-state-controls.md` | frontend — open / close / reopen on the chapter page |
| 009 | `009.chapter-canvas-protocol.md` | backend — the `op` frame field, the selection on the wire, the **new** chapter branch of `determine_mode` |
| 010 | `010.chapter-tools.md` | backend — the four chapter tools and the refusal mirror |
| 011 | `011.work-module-tier-chapter.md` | frontend — `subject.ts`, generalized `contentSubject.ts`, the undo module, the frame twin |
| 012 | `012.chapter-canvas-wiring.md` | frontend — the page applies frames, pushes undo, sends its selection |
| 013 | `013.chapter-prompt-composition.md` | backend — the caller's own chapter prompt as composition layer 4 (severable) |

Dependency shape: `001 → 002 → 003 → 004`; `005` independent; `006` needs `004` + `005`; `007` needs
`006`; `008` needs `004` + `006`; `009` independent of the frontend; `010` needs `009`; `011` needs
`006`; `012` needs `010` + `011`; `013` needs 014's step 001 only and is severable from everything
else in 015.
