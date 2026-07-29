# 021.per-author-system-prompt — feature context

Feature-wide context. Step-specific facts live in each `<SSS>.context.md`; nothing is repeated
between the two files.

**This feature has no `brief.md`.** It was not produced by `/roadmap`; it grew out of a triage
redirect against a roadmapped brief that is now stale (below). `context.md` is therefore the feature
definition as well as the shared context.

## Goal

**Every author of a book keeps their own system prompt for that book.** The prompt an assistant turn
composes is the prompt belonging to *the author running the turn* — not a single book-wide prompt
shared by everyone.

Backend: a new `BookAuthorPrompt` table with a session-free `db/` module and a JSONL codec, a service
that reads and upserts **the caller's own** row, a dedicated route pair, and the composition switch
that repoints `services/prompt_composition.py` and `services/chat_turn.py` off `Book.system_prompt`
and onto the caller's row.

Frontend: shared DTOs and two api functions, plus **two writable surfaces** — the book settings page
in the Shell entry and the Book-state view in the working page — each editing the caller's own prompt.

## `fast/003.book-system-prompt` is superseded by this feature

`docs/plans/fast/003.book-system-prompt/brief.md` defines a **book-wide, owner-only** prompt
(FEAT-019 book half, UC-093, US-108). During triage the user redirected the feature to **per-author**,
and — asked explicitly whether per-author replaces or sits alongside the book-wide prompt — chose
**replace: there is no book-wide prompt, only per-author ones**. Asked again once it was surfaced that
this also breaks the chapter half, the user confirmed: **proceed, FEAT-019 gets rewritten.**

That brief is now stale. It is `/roadmap`'s file — **this plan never edits it**. Re-shaping or
retiring it, and re-scoping `roadmap.md`'s `014.chapter-skeleton` row, is a **`/roadmap` task**,
carried in `outcome.md` under "Follow-ups that are NOT architecture's".

The number `021` is used because `roadmap.md` → "Build order" retires `020` explicitly and reserves
"numbers 021+ when mapped".

## Product situation — recorded honestly, not papered over

`docs/product/` is read-only here. FEAT-019
(`docs/product/use-cases/FEAT-019.system-prompts.md`,
`docs/product/stories/FEAT-019.system-prompts.md`) is `[confirmed: user]` from the 2026-07-24
interview and says:

- **UC-093 / US-108** — the book prompt is **owner-only**, stored on the book, applied to **every**
  chat. **US-108.AC-2:** a co-author attempting to edit it is refused.
- **UC-094 / US-109** — the chapter prompt **"narrows the book's rather than replacing it — the
  book-wide voice always applies"**. **US-109.AC-3:** with no chapter prompt, "only the book's system
  prompt applies".

**This feature contradicts all of that.** Consequences, stated so they cannot read as oversight:

1. **UC-093 / US-108 no longer describe the system.** There is no book-wide prompt to own, and a
   co-author is not refused — they have their own prompt and may edit it.
2. **UC-094 / US-109 lose the layer they narrow.** `Chapter.system_prompt` already exists as a column
   whose docstring says "appends to the book's"; there is no longer a book's. What a chapter prompt
   narrows now is an open product question this feature does **not** answer.
3. **`014.chapter-skeleton` is affected.** Its `roadmap.md` row delivers "FEAT-019 (chapter half),
   UC-094, US-109 … any member sets/clears the chapter's own system prompt". That folder is
   **roadmapped only** (`brief.md`, no `status.md`), so there is no plan to invalidate — but the brief
   and the roadmap row need re-shaping before it is planned.

**Because the acceptance criteria are contradicted rather than satisfied, no `[test]` DoD item in this
feature cites `US-108.AC-*` or `US-109.AC-*` as met.** DoD items are written against the behaviour
specified here, and where a clause deliberately reverses a criterion it says so inline.

Rewriting FEAT-019 is **`/product-spec`'s**, per `docs/product/CLAUDE.md` → "Who writes, who reads".
Re-planning `014.chapter-skeleton` is `/roadmap`'s then `/planner`'s. Both are carried in `outcome.md`
with owners.

## Design decisions the user has locked — do not reopen

### 1. A new table, `BookAuthorPrompt`

| Column | Notes |
|---|---|
| `id` | snowflake PK |
| `book_id` | FK → `books.id` |
| `user_id` | FK → `users.id` |
| `system_prompt` | required text; `""` means "no prompt" |
| `created_at` / `modified_at` | timestamps |
| — | **unique `(book_id, user_id)`** |

Row shape copied from `BookMember`, which is the system's precedent for a surrogate-PK-plus-unique-pair
link row (`domain-book.md` → "BookMember").

**Why a new table and not a column on `BookMember`:** the **owner has no `BookMember` row** —
ownership is `Book.owner_id` (`domain-book.md`, `authorization.md` → "Roles"). A prompt hung off
membership would be unreachable for exactly the author who has the most reason to set one.

### 2. `Book.system_prompt` goes dormant — it is **not** dropped

`db/engine.py` offers only an **additive** migration seam and there is no Alembic anywhere, so there
is no DROP COLUMN path. Therefore: **keep the column**, **keep it required and still written `""` at
book creation**, **keep its JSONL codec** so existing exports still import, **stop reading it**, and
mark it superseded in the model docstring. A dead-but-documented column beats an unsupported
migration.

**`backend/app/services/books.py` is out of scope for every step.** The `""` write at creation stays
exactly as it is; removing it would break inserts against a bare required column.

### 3. Composition renames the layer

`compose_system_prompt`'s `book=` parameter becomes `author=` and its section label `BOOK` becomes
`AUTHOR`. The order becomes **`base → mode → author → chapter`**.

**Why rename rather than just repoint:** a parameter named `book` carrying an author's prompt is a
trap for the next reader, and the next reader is `014`/`015`/`016` deciding what the chapter layer
narrows.

### 4. Authorization is per-row ownership, not a capability

Membership is established through `BookAccess` (the existing `Depends(book_access(book_id))`
dependency), then the service scopes every read and write to **`access.user_id`**. This copies the
guard *shape* of `services/chats.py`, whose own docstring records that the rule "is **not** a
`Capability` / `_CAPABILITY_MATRIX` entry — that table maps capability → roles and has no notion of
row ownership."

**No `Capability` member is added.** `authorization.md` → "Chats" states row ownership is not
expressible in the matrix, and `authorization.md` → "Not settled by this pass" lists "who may edit the
book- and chapter-level system prompts" as still open — this feature answers it (each author edits
their own, nobody else's) and `outcome.md` carries the reconciliation.

### 5. A dedicated route pair, not a field on `BookDetailResponse`

```
GET  /api/books/{book_id}/system-prompt   → the caller's own prompt
PUT  /api/books/{book_id}/system-prompt   → upsert the caller's own prompt
```

**Why not ride on the book DTO:** the value is per-caller, so it cannot honestly live on
`BookDetailResponse`, which is a book-shaped DTO — two authors reading the same book would get
different bytes for the same field.

This means the **four docstrings that currently declare `system_prompt` deliberately omitted** —
three in `backend/app/models/schemas/books.py` (around lines 39-46, 79-90, 95-105) and one in
`frontend/src/types/books.d.ts` (around lines 69-74) — are **revised to state the new reason** (the
prompt is per-author and lives on its own endpoint), never deleted and never worked around. The three
backend ones are step 004's; the frontend one is step 005's.

### 6. PUT is an upsert; there is no DELETE

PUT creates the row when absent and updates it when present. An **empty string means "no prompt"**,
and the composer already skips blank layers — so a delete verb would add a second way to express a
state that already has one.

### 7. Both surfaces are writable

`BookSettingsPage` (Shell entry, `/books/:bookId/settings`) **and** `BookStatePage` (working page,
`/work/:bookId/state`), each editing the caller's own prompt.

Whether `BookSettingsPage` is reachable by a co-author is a property of that existing page and is
**unchanged by this feature** — it aggregates owner-only capabilities today. The working page's Book
state view is the surface that reaches **every** member, which is why "both surfaces" matters rather
than being redundant.

## The wire contract (shared by steps 002, 003, 005, 006)

Response body, for both verbs:

| Field | Type | Notes |
|---|---|---|
| `book_id` | `str` | snowflake as string |
| `system_prompt` | `str` | `""` when the author has no prompt |
| `modified_at` | ISO timestamp or `null` | `null` when no row exists yet |

Request body for `PUT`: `{ "system_prompt": <str> }`.

**No `user_id` field.** It is always the caller; echoing it would invite the belief that the endpoint
can serve another user's prompt.

**A missing row is a `200` with an empty prompt, never a `404`.** "This author has not written one
yet" is the normal starting state of every book for every author, not a missing resource; a `404`
would force every client to special-case the common case.

Status codes, inherited from `authorization.md` → "Failure modes":

| Situation | Status |
|---|---|
| No valid token | `401` |
| A private book the caller has no relationship to | `404` (existence hiding) |
| A book the caller can see, but is not a member of (a reader on a public book) | `403` |
| Member (owner or co-author) acting on their own prompt | `200` |

## Planner-derived decisions (recorded with reasoning)

- **A reader is refused with `403`, not `404`.** A reader of a public book can legitimately see the
  book, so `authorization.md` → "Failure modes" gives `403` ("you are looking at the right thing and
  are not allowed to do that to it"). Existence hiding (`404`) is already produced upstream by the
  `book_access` dependency for a private book, and is not re-derived in the service.
- **The refusal is a typed service reason, not `BookAuthorizationError`.** No `Capability` exists to
  raise it with (decision 4), so the service owns its own reason enum plus one exception class —
  `services/chats.py`'s shape — and the route maps the reason to `403`.
- **`services/chat_turn.py` reads the prompt row through the `db/` module directly.** `services → db`
  is the sanctioned edge (`backend.md`); routing it through the prompt service would require a
  `BookAccess` the turn does not exist to build, and the turn is already scoped to the chat's author
  by `services/chats.py`'s ownership guard.
- **The prompt is not put in the working page's restore buffer.** The buffer (UC-092,
  `frontend-workspace.md`) exists for large content-pane artifacts whose loss is expensive; a system
  prompt is a short settings field edited from two different surfaces, and buffering it in one but not
  the other would be incoherent. Save is explicit on both surfaces.
- **The two frontend surfaces do not share a state class or a component.** Each page owns its own
  state, per `frontend.md`'s page-is-a-route rule; sharing would create a dependency from the `work`
  entry into the `user` entry, which the folder layout forbids (only `src/` root is shared). What
  *is* shared is what belongs at `src/` root: the DTOs in `types/books.d.ts` and the two functions in
  `api/books.ts`, both added in step 005 and consumed by step 006.
- **The `chapter` layer of the composer is left in place, untouched and still unpassed.**
  `chat_turn.py` does not pass `chapter=` today and does not start. What the chapter prompt now
  narrows is `014.chapter-skeleton`'s question, after `/product-spec` rewrites FEAT-019.

## Out of scope — state it, do not build it

| Excluded | Owner |
|---|---|
| The chapter system prompt (`Chapter.system_prompt`), and what it narrows now | `014.chapter-skeleton`, after FEAT-019 is rewritten |
| Dropping `Book.system_prompt`, or any migration machinery | nobody — decision 2 |
| Any change to `backend/app/services/books.py` | — |
| The five admin assistant mode prompts | `012.assistant-config-editor` |
| Any `Capability` enum member or `_CAPABILITY_MATRIX` row | — decision 4 |
| A DELETE verb for the prompt | — decision 6 |
| Editing another author's prompt, or an owner viewing a co-author's | — the endpoint is per-caller by construction |
| Rewriting `docs/product/` FEAT-019 | `/product-spec` |
| Re-shaping `fast/003.book-system-prompt` and `roadmap.md`'s `014` row | `/roadmap` |
| The restore buffer, draft-until-saved reconciliation, 409 handling | not applicable — no version token on this row |

## Cross-cutting backend constraints (steps 001–004)

- **Four-layer separation is enforced.** `routes/` is HTTP only; `services/` holds logic and may never
  touch a session, `select()`, `session.add()` or `session.exec()`; `db/` is session-free with one
  module per entity and no ORM type leaking out; `models/` is tables plus `models/schemas/` DTOs with
  no logic. Dependency direction `routes → services + db`, `services → db`, `db → models`. Namespace
  imports throughout (`from app.db import book_author_prompts` →
  `await book_author_prompts.get_by_book_and_user(...)`).
- **Timestamps are the service's, not the db layer's.** `db/` persists the row it is handed.
- **Typed errors, never bare exceptions.** One reason enum plus one exception class per service,
  following `services/chats.py`. No free dictionaries; Pydantic `BaseModel` for every API schema.
- **Every id is `str` in a DTO** — snowflakes exceed the JS safe-integer range. DTOs are hand-built by
  a service mapper, never dumped from the ORM.
- **Route shape.** The router owns its own `/api/...` path and is mounted in `main.py`; the
  `{book_id}` path parameter is consumed entirely by `Depends(book_access)` and is not re-declared by
  handlers; response models are declared as the **return annotation**, never `response_model=`.
- **Additive schema only.** `db/engine.py`'s `init_db()` runs `SQLModel.metadata.create_all`, so a new
  table needs registration and **no migration statement**. The ADDITIVE MIGRATION SEAM stays `pass`.
- **Every DB-persistent model owes its JSONL codec in the same change** (root `CLAUDE.md`).

## Cross-cutting frontend constraints (steps 005–006)

- **`observer` on every component**, no exceptions. State is observable data plus pure `get`
  computeds; every effectful operation is an external `(state, args, signal)` function using
  `runInAction`; every loadable is an async trio (`x` / `xStatus: "idle"|"loading"|"ready"|"error"` /
  `xError`).
- **No custom `useX` hooks**, no `useCallback` / `useMemo` / `useReducer`, no React context, no
  Mantine `useForm`, no runtime schema validation. `useState` only to own a stable state instance;
  `useEffect` only at page level, mount-load / unmount-abort.
- **Forms are drafts in state + computed validation**, with server-side errors held separately from
  client ones.
- **All HTTP lives in `src/api/`**; `signal?: AbortSignal` is always the trailing argument. DTOs are
  hand-written `.d.ts` in `src/types/`, wire-exact `snake_case`, **ids typed `string`**, no `any`.
- **The backend is the source of truth** — after a save the surface shows what the server returned, not
  the optimistic draft.

## Testing facts shared by every step

**Backend (001–004)** — tests live under `backend/tests/{db,services,routes}/`. `asyncio_mode="auto"`,
so async tests need no decorator. `conftest.py` provides `_reset_db_ready` (autouse), `db(tmp_path)`
and `http_client(tmp_path, monkeypatch)` (which drives the app lifespan manually). Route-test seed
helpers (`_now`, `_auth_header`, `_seed_user`, `_seed_author`, `_seed_private_book`, `_add_co_author`)
are copied verbatim from `backend/tests/routes/test_chats.py`, which is also the canonical
book-scoped-authz test shape. **Auth in route tests is real** — seed a user row and mint a real JWT.
Assertions validate responses through the DTO. **No network in any test**: the LLM client is mocked.
Test naming: `test_<behaviour>__DoD<N>`.

**Frontend (005–006)** — `frontend/vitest.config.ts` is jsdom with **`globals: false`**, so every spec
imports `describe` / `it` / `expect` / `vi` from `"vitest"`. `frontend/tests/setup.ts` adds jest-dom,
stubs `matchMedia` / `ResizeObserver` / `scrollIntoView`, and in `afterEach` runs `cleanup()` +
`localStorage.clear()`. `frontend/tests/support/render.tsx` exports
`renderWithProviders(ui, { route? })`. Specs **mock the `api/` module, never `fetch`**, in
module-factory form enumerating every export the subject imports; `ApiError` is imported real from
`../../src/api/client`. `frontend/tests/work/BookStatePage.test.tsx` is the working reference for the
module-factory pattern.

## Build and test gates (root `CLAUDE.md`)

- **Backend steps 001–004:** `cd backend && .venv/Scripts/python -m pytest`. There is **no separate
  backend typecheck** — do not invent one.
- **Frontend steps 005–006:** `cd frontend && npm run build` (= `tsc && vite build`),
  `cd frontend && npm test`, `cd frontend && npm run test:types`.
  `frontend/tsconfig.json` has `include: ["src"]`, so a broken spec can never break the bundle;
  `npm run test:types` is the only program covering `tests/`.

## Architecture sources

- `docs/architecture/domain-book.md` — `Book` fields (including `system_prompt` as the book-wide
  prompt this feature retires), `BookMember`'s surrogate-PK-plus-unique-pair shape, and the rule that
  **the owner is not a `BookMember` row**.
- `docs/architecture/authorization.md` — `BookAccess`, the resolve-in-a-dependency /
  decide-in-a-service split, the "Chats" row-ownership rule that is deliberately not a matrix row,
  the `401 / 404 / 403` failure taxonomy, and the open item this feature closes.
- `docs/architecture/assistant-config.md` — "System-prompt composition — the named prompts only": the
  four-layer order and the empty-contributes-nothing rule.
- `docs/architecture/frontend.md` — the MobX rules, the state ladder, the api/types conventions.
- `docs/architecture/frontend-workspace.md` — the working page's regions, the content-pane editability
  table (Book state: "state notes editable; everything else read-only" — this feature changes that
  row), and the Shell route map.

## Steps

| Step | File | Layer |
|---|---|---|
| 001 | `001.author-prompt-table.md` | backend — model, `db/`, registration, JSONL codec |
| 002 | `002.author-prompt-service.md` | backend — schemas + service |
| 003 | `003.author-prompt-routes.md` | backend — the route pair |
| 004 | `004.composition-switch.md` | backend — the switch that delivers "replace" |
| 005 | `005.settings-page-editor.md` | frontend — types, api, `BookSettingsPage` |
| 006 | `006.book-state-editor.md` | frontend — `BookStatePage` |

Steps 003 and 004 are independent of each other; both need 002. Step 006 needs 005 for the shared
DTOs and api functions.

## Product ids

**Delivered here:** FEAT-019's book half **as redefined by this feature** — a per-author prompt
applied to that author's chats. No `UC-###` or `US-###.AC-#` currently describes it; the ids will
exist once `/product-spec` rewrites FEAT-019.

**Knowingly contradicted, by user decision:**
UC-093, US-108 (all criteria — including **US-108.AC-2**, the co-author refusal, which this feature
deliberately reverses); and the premise of UC-094 / US-109 (**US-109.AC-3** in particular), which
depend on a book-wide layer that no longer exists.

**Not delivered:** the FEAT-019 chapter half (UC-094, US-109) — `014.chapter-skeleton`.
