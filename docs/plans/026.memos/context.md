# 026.memos — feature context

Feature-wide context. Step-specific facts live in each `<SSS>.context.md`; nothing is repeated
between the two files.

**This feature has no `brief.md`, and none is to be written.** `brief.md` is `/roadmap`'s file and
this feature was not roadmapped — `docs/plans/roadmap.md` carries no row for it either, which is
`/roadmap`'s to add (recorded in `outcome.md`). `context.md` is therefore the feature definition as
well as the shared context.

## Goal

**FEAT-021 — Memos.** An author's own standing notes for one book: private to them, ordered by them,
and carried into every run of their assistant without being retyped.

Backend: a `memos` table with its session-free `db/` module and JSONL codec; a service and a route
family that read and write **only the caller's own** memos; reorder; the on/off and archive axes; a
fourth `MEMOS` layer in the composed system prompt, threaded into sub-agent delegation; and a
`create_memo` tool.

Frontend: DTOs and an api module, the eighth navigator entry, the `/work/:bookId/memos` route, the
`memos` subject kind, and the memos list page — the content pane's **first editable list**, with
create-and-focus, save on focus loss, an on/off switch, archive/restore and drag-plus-arrow reorder.

## The architecture is already written — this plan does not re-derive it

FEAT-021 was designed in an `/architect` round on **2026-09-15**, before this plan existed. Every
design decision below is quoted from that round, not invented here. The binding sections:

| Document | Sections |
|---|---|
| `docs/architecture/domain-book.md` | `## Memo` (the entity and the reasoning for each field); `## Cloning` → the memos subsection |
| `docs/architecture/authorization.md` | `### Chats, per-author prompts and memos — four row-ownership rules`; `#### The one named exception: memos stay writable on an archived book` |
| `docs/architecture/assistant-runtime.md` | `### Layer 4 — the author's active memos`; `#### Memos are not context assembly`; `#### BASE_TOOL_NAMES widens to two entries`; `### The parked question is answered, narrowly`; `## create_memo — the first tool with a database write behind it`; the `SubjectKind` paragraph |
| `docs/architecture/assistant-config.md` | the `create_memo` catalogue entry; the seeding bullet and its existing-install caveat |
| `docs/architecture/quick-reference.md` | the `/api/books/{book_id}/memos` route table; the Memos DTO subsection; the `Memo` row and the `SubjectKind` row in Tables & enums |
| `docs/architecture/frontend-workspace.md` | the `/work/:bookId/memos` route row; the "`/memos` has no item route" paragraph; the Memos navigator bullet; the editability table's memos rows and the `resolveEditability` paragraph |
| `docs/architecture/frontend-work-drafts.md` | `Memos are outside the buffer too` |
| `docs/architecture/backend/book-domain.md` | the designed-only FEAT-021 module list; `### memos sits immediately after chapter_author_prompts (index 11)` |

**`docs/architecture/` is read-only from a plan.** Where the code contradicts a doc, record it in
`outcome.md` — never edit the doc. Two such contradictions are already known and seeded there; both
predate this feature.

## Product ids

**Delivered here:** FEAT-021 — UC-103, UC-104, UC-105, UC-106, UC-107, UC-108, UC-109; US-123,
US-124, US-125, US-126, US-127, US-128, US-129, US-130, US-131, US-132. Plus **US-105.AC-7** (FEAT-013's
navigator gains a Memos entry).

**Deliberately out of scope — not this feature's work:**

| Id | Belongs to | Why not here |
|---|---|---|
| **US-133** — a clone carries the cloner's memos | **FEAT-015 book cloning** | Cloning is unbuilt: there is no clone path to extend. `domain-book.md` → "The clone copies the cloner's memos" is the design whoever builds FEAT-015 inherits |
| **US-134** — the moderation view excludes memos | **FEAT-011 content moderation** | The moderation surface is unbuilt, and the exclusion is **the absence of a field on a DTO that does not exist yet** (`authorization.md` → "The admin boundary"). There is nothing to build and nothing to filter |

Neither feature is built; neither story is this feature's work. Say so plainly rather than leaving
the reader to wonder why two of FEAT-021's twelve stories carry no DoD item.

## Citation convention in this plan's DoD items

Every `[test]` DoD item cites the `US-###.AC-#` it verifies. **Three kinds of item cannot**, and they
say so inline instead of citing a criterion they do not verify:

- items realizing a **use-case postcondition with no separate AC** (e.g. UC-103's "empty" memo) cite
  the `UC-###`;
- items enforcing an **architecture-only rule** (the archived-book carve-out, the registry position,
  the layer's label and position) name the architecture section instead;
- items discharging an **infrastructural obligation** (the JSONL codec, drift-clean schema) name the
  root `CLAUDE.md` rule.

This is deliberate and recorded once here, so that a missing citation reads as a decision rather than
an omission.

## Design decisions from the architecture round — do not reopen

### 1. The `Memo` row, and the one thing a reader gets wrong

| Column | Notes |
|---|---|
| `id` | snowflake PK |
| `book_id` | FK → `books.id` |
| `user_id` | FK → `users.id` — the memo's author; nobody else, **including the book's owner**, ever reads it |
| `body` | required text; **`""` is legal** — a new memo is created empty |
| `ordinal` | non-null int, scoped **per `(book, author)`** |
| `active` | bool, default `true` |
| `archived` | bool, default `false` |
| `created_at` / `modified_at` | timestamps |

**There is NO unique constraint on `(book_id, user_id)`** — an author has **many** memos per book;
that is the whole feature. The field list is `BookAuthorPrompt`'s almost exactly, and both
`BookAuthorPrompt` and `BookMember` do carry that constraint, so the model docstring must say why this
one does not.

**Two booleans, not one state enum** — the deliberate opposite of `Book.state`. Inactive and archived
are two independent axes; two flags are the only shape that remembers whether a restored memo was
switched on or off before it was archived.

**Context membership is derived, never stored:** a memo reaches the assistant iff
`archived == false AND active == true`. There is no invalid combination to refuse.

### 2. Ordinals — append, gap, append again

- A new memo is **appended at `max + 1`** (manual create, assistant create and restore alike).
- **Archiving leaves a gap and never renumbers** (the `chapters` DELETE precedent).
- **A restore appends last, at `max + 1`** — never back to its old slot.
- A reorder rewrites ordinals **`1..N` over the caller's non-archived memos only**; archived rows keep
  the ordinals they had.

**Planner resolution, recorded because the architecture does not qualify it:** `max` is taken over the
caller's **non-archived** memos in that book. The invariant the architecture states is that *no two
live rows in one author's list share an ordinal* and that the list therefore needs **no `(ordinal, id)`
tiebreak*; taking `max` over the working list preserves exactly that, and matches "appended last **in
the list**". An archived row may share an ordinal with a live one; that is inert, because an archived
row is never in the list. Carried to `outcome.md` as a clarification for `domain-book.md`.

### 3. Authorization is the fourth row-ownership rule — not a capability

`book_access` establishes **membership**; `services/memos.py` then scopes **every read and every
write** to `access.user_id`. **No `Capability` member and no `_CAPABILITY_MATRIX` row is added**
(`authorization.md` is explicit). There is no route shape in which a caller can name another author's
row.

A memo that does not exist, **belongs to another author**, or **belongs to another book** is **one
refusal, `404`** — no existence oracle. US-124 is therefore satisfied *structurally*, by the shape of
the service, not by a check a later feature could bypass.

### 4. An archived book does NOT refuse memo writes — the one named carve-out

Create, edit, reorder, activate, deactivate, archive and restore all succeed while
`BookAccess.book_state == archived`. A memo is not book content; it is the author's private note
*about* a book they have deliberately set aside. `quarantined` and `destroyed` are unchanged.

Consequently **`services/memo_tools.py`'s refusal chain has no archived-book link**, unlike
`chapter_tools.py`'s — the module docstring must say so, because the neighbouring chain has that link
and a reader will copy it.

### 5. No version token, no `409`, no optimistic concurrency

A memo is short, saved on focus loss within moments of being typed, and has exactly **one writer — its
owner**. `create_memo` does not break that: it only ever **creates** a row and never edits an existing
one. So: no `expected_modified_at`, no `409`, no restore buffer, no divergence view.

### 6. No DELETE, anywhere, ever

Archive-not-delete (UC-107, US-128.AC-3). There is **no delete function in `db/memos.py`**, **no
`DELETE` route**, and **no delete control in the UI**.

### 7. The `MEMOS` prompt layer is fourth, and the chapter prompt moves to fifth

```
1 BASE    2 MODE    3 AUTHOR    4 MEMOS    5 CHAPTER
```

A memo is per-author-per-book — the same scope as the AUTHOR layer — so it sits beside it, while the
chapter prompt stays the most-specific layer nearest the task. **`author` remains the third
positional parameter**; the existing frozen-signature property is preserved, not broken.

The set is rendered into **one section string before** the pure composer, which gains a fifth optional
**string** layer and never learns what a memo is. The section is rendered **exactly once per turn** in
`services/chat_turn.py` and passed to **both** the composer and delegation — it is never re-read in
`services/subagent_delegation.py`. One DB read, and — the load-bearing half — parent and every
sub-agent see an **identical** set even if `create_memo` adds one mid-turn.

**This feature changes two existing composition test files rather than extending them** (step 006) and
one delegation test file (step 007). Named in those steps.

### 8. Memos are NOT context assembly

Context / content assembly (US-057, UC-085/086/078 internals), token budgeting and token-level canvas
streaming stay exactly as deferred as they were. A memo is **authored**, standing, and selected by
nobody — no retrieval, no ranking, no relevance question, no truncation. Nothing in this feature
removes an entry from `assistant-runtime.md` → "Out of scope — still deferred".

### 9. `create_memo` takes the existing `"book"` group — user decision, this session

No new tool group is introduced and the valid-group set is not widened.

### 10. No backfill for existing installs — user decision, this session

Adding `create_memo` to `DEFAULT_MODE_TOOL_NAMES` reaches **fresh installs only**, because
`seed_default_modes()` / `seed_default_mode_tools()` are idempotent by key. On an existing instance an
administrator adds `create_memo` to the five modes **by hand** in the assistant-config editor, and
`BASE_TOOL_NAMES` covers every mode-less surface meanwhile.

**Do not plan a re-seed, a backfill or a migration step.** The architecture calls this a known
consequence of idempotent seeding, not a defect; it is recorded as an operating note in `outcome.md`.

### 11. `SubjectKind` gains `memos` — wire honesty, not routing

`memos` joins `SubjectKind` in **both** `backend/app/models/schemas/chats.py` and its wire-exact twins
`frontend/src/work/subject.ts` and `frontend/src/types/chats.d.ts`. It is **mode-less**, like
`chapters` / `variants` / `chats`: nothing keys a mode off it and behaviour is identical either way
(tool-gating case 2). **`ResolvedSubject` is NOT widened and `determine_mode` gains NO branch** — a
`SubjectKind` member and a `ResolvedSubject` member are different things, and this feature adds only
the first.

### 12. The memos list is the content pane's first **editable list**, and the list *is* the editor

There is **no memo page**, no `/memos/:id` and no `/memos/new` — creation appends into the list in
place. "Any list is read-only" was always a rule about **book-content** lists, whose items have their
own pages and their own write paths; memos have neither.

`resolveEditability` gains a memos branch returning a **constant** editable verdict using the
**existing `"whole"` region** — **no new `EditableRegion` member and no `WriteRegion` widening**. The
branch decides nothing; it exists so the editability table stays the single enforcement point. There
is no author/assistant symmetry to enforce here: `create_memo` creates a **new** row and never writes
into a displayed memo.

### 13. Save on focus loss — the SPA's first blur-save

UC-104 / US-125.AC-1 require the body to save when focus leaves, and **US-125.AC-2 requires that no
explicit save control exist**. An exhaustive grep of `frontend/src` found **zero `onBlur` handlers**:
every editable field in the app today uses an explicit Save button bound to a `canSaveX` computed.
This feature departs from that house shape **because the product requires the absence of the control**,
and `frontend-workspace.md` fixes the mechanism: **an ordinary event handler, not a `useEffect`
watching the draft**. Step 010 states the departure in its own file too.

## The wire contract (steps 002–005, consumed by 009–011)

Routes, all under `Depends(authz.book_access)`:

| Method | Path | Success | Body → Response |
|---|---|---|---|
| `GET` | `/api/books/{book_id}/memos` | `200` | `?include_archived=false` → `MemoListResponse` |
| `POST` | `/api/books/{book_id}/memos` | `201` | `CreateMemoRequest` → `MemoResponse` |
| `PUT` | `/api/books/{book_id}/memos/order` | `200` | `ReorderMemosRequest` → `MemoListResponse` |
| `PUT` | `/api/books/{book_id}/memos/{memo_id}` | `200` | `UpdateMemoRequest` → `MemoResponse` |
| `POST` | `/api/books/{book_id}/memos/{memo_id}/activate` | `200` | no body → `MemoResponse` |
| `POST` | `/api/books/{book_id}/memos/{memo_id}/deactivate` | `200` | no body → `MemoResponse` |
| `POST` | `/api/books/{book_id}/memos/{memo_id}/archive` | `200` | no body → `MemoResponse` |
| `POST` | `/api/books/{book_id}/memos/{memo_id}/restore` | `200` | no body → `MemoResponse` |

`MemoResponse` carries `id`, `book_id`, `body`, `ordinal`, `active`, `archived`, `created_at`,
`modified_at` — **and no `user_id`**: the subject is always the caller, and echoing an id would invite
the reading that another author's memo is addressable here. Ids are **strings** on the wire.

Status taxonomy, inherited from `authorization.md` → "Failure modes":

| Situation | Status |
|---|---|
| No token | `401` |
| A private book the caller has no relationship to | `404` — from `resolve_book_access`, **never re-derived** |
| A logged-in non-member of a book they can see | `403` |
| A memo that does not exist, belongs to another author, or belongs to another book | `404` — one refusal |
| A reorder list that is not exactly the caller's non-archived set | `400` |
| A member acting on their own memo | `200` (`201` on create) |

**Planner-derived: repeat state calls are `200` no-ops, not `409`.** Activating an already-active memo,
or archiving an already-archived one, answers `200` with the row unchanged. The memo taxonomy names
**no `409` at all** (`quick-reference.md`: "no `expected_modified_at` and no `409`"), these verbs are
idempotent state assertions rather than lifecycle transitions, and the precedent is
`POST …/close/cancel`'s deliberate `200` no-op. This deliberately does **not** copy
`POST /books/{id}/archive`'s `409`, whose subject is a book lifecycle with a state machine behind it.

## Two axes, four verbs — why not one `PATCH`

The on/off switch and the archive axis are **two independent axes in the model**, and each gets its own
verb pair so the wire says so, while the focus-loss `PUT` never carries state it did not mean to write.
Mirrors `SubAgent`'s `disable` / `enable`.

## Cross-cutting backend constraints (steps 001–008)

- **Four-layer separation is enforced.** `routes/` is HTTP only; `services/` holds logic and may never
  touch `session`, `AsyncSession`, `select()`, `session.exec()` or `session.add()`; `db/` is
  session-free with one module per entity and no ORM type leaking out; `models/` is tables plus
  `models/schemas/` DTOs with no logic. Direction: `routes → services + db`, `services → db`,
  `db → models`. Namespace imports throughout (`from app.db import memos` →
  `await memos.list_for_author(...)`).
- **Ids are minted by the model's `default_factory`**, never by `db/`.
- **Timestamps are the service's policy, not `db/`'s.** `db/` persists the row it is handed; services
  stamp `datetime.now(timezone.utc)` inline.
- **Typed errors, never bare exceptions.** One module-level `MemoErrorReason(str, enum.Enum)` plus one
  `MemoError` exception for the service; the route owns a `_MEMO_ERROR_STATUS` map and a
  `_map_memo_error` helper. `services/book_author_prompts.py` + `routes/book_author_prompts.py` are the
  shape to copy.
- **Pydantic `BaseModel` for every request/response schema**; no free dictionaries anywhere.
- **Every id is `str` in a DTO** — snowflakes exceed the JS safe-integer range. DTOs are built by a
  service mapper, never dumped from the ORM.
- **Route shape.** The router owns its own `/api/books` prefix and is mounted in `main.py`; `{book_id}`
  is consumed entirely by `Depends(authz.book_access)` and is not re-declared by handlers; response
  models are the **return annotation**, never `response_model=`.
- **Additive schema only.** `init_db()` runs `SQLModel.metadata.create_all`, so a new table needs the
  MODEL-REGISTRATION SEAM and **no migration statement**: the ADDITIVE MIGRATION SEAM stays `pass` and
  `ADDITIVE_COLUMNS` is untouched (that seam is for a new column on an existing table).
- **Every DB-persistent model owes its JSONL codec in the same change** (root `CLAUDE.md`). Step 001's
  job, and not optional.

## Cross-cutting frontend constraints (steps 009–011)

- **MobX only.** `observer` on **every** component, no exceptions. State is observable data plus pure
  `get` computeds; every effectful operation is an external `(state, args, signal?)` function using
  `runInAction` before and after each await; every loadable is an async trio
  (`x` / `xStatus: "idle"|"loading"|"ready"|"error"` / `xError`).
- **No custom `useX` hooks**, no `useCallback` / `useMemo` / `useReducer`, no React context, no Mantine
  `useForm`, no runtime schema validation. `useState` only to own a stable state instance; `useEffect`
  **only at page level**, mount-load / unmount-abort. Calling a **library's own** hook (`@dnd-kit`'s
  `useSortable`) is not a breach — the rule forbids *authoring* hooks.
- **Per-row status is a whole new object**, never a mutation:
  `state.actionStatus = { ...state.actionStatus, [id]: "loading" }`.
- **All HTTP lives in `src/api/`**, forwarding through `client.ts`'s `request<T>`; list envelopes
  (`{ items: [...] }`) are unwrapped at the call site and deliberately not modelled in `.d.ts`.
  `signal?: AbortSignal` is the trailing argument. Hand-written `.d.ts` in `src/types/`, wire-exact
  `snake_case`, **ids typed `string`**, **no `any`**.
- **The backend is the source of truth** — after any write the surface shows what the server returned,
  not the optimistic draft. `ApiError` is swallowed into the state's error field; anything else
  rethrows.
- **Memos never enter the restore buffer** (`frontend-work-drafts.md` → "Sanctioned exclusions"):
  short, saved on focus loss, one writer, and no version token to compare a `baseVersion` against. No
  `baseVersion`, no stale-buffer detection, no divergence view, no `409` path.

## Testing facts shared by every step

**Backend (001–008)** — tests live under `backend/tests/db/`, `backend/tests/services/`,
`backend/tests/routes/`, plus a flat top-level `backend/tests/test_data_domain_<x>.py` for a JSONL
codec. `asyncio_mode="auto"`, so async tests need no decorator. `backend/tests/conftest.py` provides
the `db` and `http_client` fixtures; **there is no shared factory module** — every test module defines
its own local `_seed_user` / `_seed_book` / `_auth_header` helpers, copied from a sibling. Auth in
route tests is real: seed a user row and mint a real JWT. **No network in any test** — the LLM client
is mocked. Naming: `test_<behaviour>__DoD<N>`.

**Frontend (009–011)** — `frontend/vitest.config.ts` is jsdom with **`globals: false`**, so every spec
imports `describe` / `it` / `expect` / `vi` from `"vitest"`. Specs **mock the `api/` module wholesale,
never `fetch`** — `vi.mock("../../src/api/memos", () => ({ <every export>: vi.fn() }))` — and render
through `renderWithProviders` from `frontend/tests/support/render.tsx` (pass a `route` option for
router cases). Query **by role and accessible name only; never test ids**. `ApiError` is imported real
from `../../src/api/client`.

**jsdom cannot drive `@dnd-kit`'s pointer sensor.** `ChaptersPageReorder.test.tsx` marks the drag
gesture `[manual/live]` and tests only the arrow buttons, on the premise that both affordances funnel
into one persist call. Step 011 does the same: **US-126.AC-2 (arrows) is `[test]`, US-126.AC-1 (drag)
is `[manual/live]`.**

## Build and test gates (root `CLAUDE.md` — referenced, not duplicated)

- **Backend steps 001–008:** `cd backend && .venv/Scripts/python -m pytest`. There is **no separate
  backend typecheck** — do not invent one.
- **Frontend steps 009–011:** `cd frontend && npm run build` (= `tsc && vite build`),
  `cd frontend && npm test`, `cd frontend && npm run test:types`. `frontend/tsconfig.json` keeps
  `include: ["src"]`, so a broken spec can never break the bundle; `npm run test:types` is the only
  program covering `tests/`.

## Steps

| Step | File | Layer |
|---|---|---|
| 001 | `001.memo-table.md` | backend — model, `db/`, registration, JSONL codec |
| 002 | `002.memo-service.md` | backend — schemas + the read/create/update service |
| 003 | `003.memo-routes.md` | backend — the list / create / update routes |
| 004 | `004.memo-reorder.md` | backend — reorder, service + `PUT …/memos/order` |
| 005 | `005.memo-state-axes.md` | backend — activate / deactivate / archive / restore |
| 006 | `006.memos-prompt-layer.md` | backend — the `MEMOS` composition layer |
| 007 | `007.memos-in-delegation.md` | backend — the section rides on `ParentTurn` |
| 008 | `008.create-memo-tool.md` | backend — the `create_memo` tool, BASE + seeding |
| 009 | `009.memos-api-and-navigator.md` | frontend — types, api, nav entry, route, subject |
| 010 | `010.memos-list-page.md` | frontend — the memos list page |
| 011 | `011.memos-list-reorder.md` | frontend — reorder in the list |

Dependency order is the numeric order, with two notes: steps 006 / 007 / 008 all need 001–002 but
**not** each other's UI, and steps 004 / 005 are independent of one another (both need 003 for the
router module). Step 011 needs 010.

## One mechanical note on step 009 vs 010

`frontend/src/work/routes.tsx` (step 009) cannot reference a page component that does not exist yet, so
**step 009 creates `MemosListPage.tsx` as a minimal placeholder** — an `observer` component rendering a
labelled empty state naming step 010 as its owner, the repo's established convention for a navigator
section not yet filled. **Step 010 replaces that body with the real page.** The file therefore appears
in both steps' Source lists, forward-only; nothing else is shared between them.

## Out of scope — state it, do not build it

| Excluded | Owner |
|---|---|
| **US-133** — a clone carries the cloner's memos | FEAT-015 book cloning (unbuilt) |
| **US-134** — the moderation view excludes memos | FEAT-011 content moderation (unbuilt) |
| A sixth assistant mode for the memos list | nobody — product puts memos on FEAT-020's non-goal list |
| A `get_memos` tool or an `edit_memo` tool | nobody — every active memo is already in the prompt; a fetch tool would be a second path to bytes the model already has |
| Widening `ResolvedSubject` or adding a `determine_mode` branch | nobody — decision 11 |
| Any `Capability` member or `_CAPABILITY_MATRIX` row | nobody — decision 3 |
| A `DELETE` verb, at any layer | nobody — decision 6 |
| A version token, `expected_modified_at` or a `409` path | nobody — decision 5 |
| A `VECTOR_SOURCE_REGISTRY` entry for memos | nobody — every active memo is pushed whole; there is nothing to retrieve |
| The restore buffer, draft reconciliation, divergence view | not applicable — `frontend-work-drafts.md` excludes memos |
| A re-seed / backfill of `create_memo` for existing installs | nobody — decision 10 |
| Editing `docs/product/`, `docs/architecture/` or `docs/plans/roadmap.md` | `/product-spec`, `/architect`, `/roadmap` |
