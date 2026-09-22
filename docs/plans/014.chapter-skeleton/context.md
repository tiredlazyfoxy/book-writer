# 014.chapter-skeleton — feature context

Feature-wide context. Step-specific facts live in each `<SSS>.context.md`; nothing is repeated
between the two files.

`brief.md` (written by `/roadmap`) is the feature *definition* and is read-only here. Its Scope In/Out
is the boundary this plan works inside — **except** for its FEAT-019 sentence, which describes a model
that no longer exists (see "Product situation" below). Re-scoping the brief is `/roadmap`'s, and is
carried in `outcome.md`.

## Goal

**A book gets a chapter skeleton, and it is built on the working page.**

An author adds a chapter with a sketch, reorders the chapters, edits a planned chapter's sketch, and
removes a planned chapter (FEAT-008 · UC-031..034 · US-032..035). Alongside that, **every member of
a book keeps their own system prompt per chapter** — the chapter-level counterpart of what feature
`021.per-author-system-prompt` shipped for the book level.

Backend: `db/chapters.py` grows the two write functions it lacks; a new `ChapterAuthorPrompt` table
with its own `db/` module and JSONL codec; DTOs, a service and a route family under
`/api/books/{book_id}/chapters`; four new `Capability` members; and a separate route pair for the
per-author chapter prompt.

Frontend: shared chapter DTOs and one `api/chapters.ts` module; a **read-only** book-hub page in the
Shell; and the working page's two chapter surfaces — the list (add / remove / reorder) and the item
(sketch editor + the caller's own chapter prompt).

## Product situation — FEAT-019's chapter half is superseded, FEAT-008 is intact

`docs/product/` is read-only here.

**FEAT-008 (UC-031..034, US-032..035) is authoritative and is cited freely.** Every skeleton `[test]`
DoD item in this plan that has a criterion behind it names it inline.

**FEAT-019's chapter half is not.** `docs/product/use-cases/FEAT-019.system-prompts.md` (UC-094) and
`docs/product/stories/FEAT-019.system-prompts.md` (US-109) say the chapter prompt *"narrows the
book's rather than replacing it — the book-wide voice always applies"*, and **US-109.AC-3** says that
with no chapter prompt "only the book's system prompt applies". Feature `021` shipped on 2026-07-29
and **removed the book-wide prompt entirely**, replacing it with a per-author one
(`BookAuthorPrompt`). There is no book layer left for a chapter prompt to narrow.

Consequences, stated so they cannot read as oversight:

1. **No `[test]` DoD item in this feature cites UC-094 or any criterion of US-109.** The chapter-prompt
   half (step 004, and step 008's prompt region) is specified by decision **D1** below and its DoD
   items are written as **self-contained verifiable criteria**. This is the same convention feature
   `021` used for the book half.
2. `brief.md`'s line *"Any book member can also set or clear a chapter's own system prompt, which
   narrows the book's"* — the first clause survives, the second does not.
3. Rewriting FEAT-019 is **`/product-spec`'s** (`docs/product/CLAUDE.md` → "Who writes, who reads").
   Re-scoping `brief.md` and `roadmap.md` is **`/roadmap`'s**. Both are carried in `outcome.md` →
   "Follow-ups that are NOT architecture's".

### `docs/architecture/` is stale on two points and this plan does not edit it

- **`domain-chapter.md`** still lists `Chapter.system_prompt` as *"optional; **appends to** the
  book's, narrowing it"*, and carries a whole paragraph built on that. That base layer is gone. Treat
  the field row and the paragraph as **stale**; the correction is recorded in `outcome.md`.
- **`frontend-workspace.md`**'s Shell route table puts the skeleton (UC-031..034) on `/books/:bookId`.
  Decision **D2** moves the mutations to the working page. This diverges from that table but
  **agrees with the same document's own stated rule** that all management/editing happens only on the
  working SPA. Also recorded in `outcome.md`.

**Critically: feature `021`'s own `outcome.md` has never been applied.** `docs/architecture/` still
describes the book-wide prompt as live. An `/architect` finalization on `021` should run **before**
this feature's outcome is applied, or the two passes collide on the same paragraphs. Flagged again at
the bottom of `outcome.md`.

## Design decisions the user has locked — do not reopen

### D1 — the chapter system prompt is PER-AUTHOR

A new table, `ChapterAuthorPrompt`, mirroring `BookAuthorPrompt`:

| Column | Notes |
|---|---|
| `id` | snowflake PK |
| `chapter_id` | FK → `chapters.id` |
| `user_id` | FK → `users.id` |
| `system_prompt` | required text; `""` means "no prompt" |
| `created_at` / `modified_at` | timestamps |
| — | **unique `(chapter_id, user_id)`** |

Row shape copied from `BookMember` — the system's precedent for a surrogate-PK-plus-unique-pair link
row — exactly as `BookAuthorPrompt` copied it.

Any book **member** owns exactly one prompt per chapter and may read and write **only their own**.
Nobody — including the book's owner — reads another author's.

**The existing `Chapter.system_prompt` column goes dormant, exactly as `Book.system_prompt` did.**
`db/engine.py` exposes only an *additive* migration seam and the project has no Alembic, so there is
no supported `DROP COLUMN` path. Therefore: keep the column, keep its JSONL codec so pre-existing
archives still import, and stop treating it as the chapter prompt. **No step in this feature reads or
writes it**, and no step drops it.

### D2 — the Book hub READS, the working page EDITS

- Shell `/books/:bookId` renders a **read-only** ordered chapter list (step 005).
- **All** skeleton mutation lives on `/work/:bookId/chapters` (steps 006, 007) and
  `/work/:bookId/chapter/:id` (step 008).

See "Product situation" above for how this sits against `frontend-workspace.md`.

### D3 — reorder is one bulk `PUT`, with both move-buttons and drag-and-drop

The endpoint takes the **full ordered chapter-id list**; the server rewrites ordinals `1..N` in one
transaction and **refuses a list that is not exactly the book's current chapter set** (missing,
extra, duplicated, or foreign ids). There is no per-chapter "move" endpoint — a partial reorder API
would let two concurrent callers interleave into an ordinal set nobody chose.

The UI offers **↑/↓ buttons and dragging** (`@dnd-kit/core` + `@dnd-kit/sortable`, a new frontend
dependency). `[test]` coverage targets the **buttons** — they are role-queryable and jsdom-friendly;
the drag interaction is a `[manual/live]` DoD item.

### D4 — chapter routes nest under `/api/books/{book_id}/chapters`

This reuses the existing `authz.book_access` dependency **unchanged**: it binds to the `{book_id}`
path parameter, which is present on every one of these paths.

**Build no `chapter_access` resolver.** Each service function verifies `chapter.book_id ==
access.book_id` itself and raises its own not-found reason otherwise. A second resolver would
duplicate the existence-hiding rule that `authorization.md` deliberately produces in exactly one
place.

### D5 — closes UC-032's `_TBD`: reorder IS allowed while a chapter is open

Reorder touches `ordinal` only. It never reads or writes a body, never changes a `state`, and never
bumps `version`, so none of the write-refusal rules in `domain-chapter.md` are engaged.

### D6 — closes UC-033's `_TBD`: sketch edits are last-write-wins

No `expected_version` on the request, no `409` on the sketch path. **`Chapter.version` tracks the
*body* only and is not bumped by a sketch edit.** Product's UC-033 says co-authors edit sketches "in
parallel"; the concurrency contract in `domain-chapter.md` is written for `text` and its line-addressed
placements, which a sketch has none of.

### D7 — chapter-prompt COMPOSITION is out of scope

Storing and serving the prompt lands here. **Wiring it into `services/chat_turn.py` does not.** Doing
so needs an answer to "which chapter is this turn about", which is FEAT-013 context assembly — still
undesigned by deliberate choice (root `CLAUDE.md`). Deferred to `015.chapter-writing-free-mode`.

No step touches `services/chat_turn.py` or `services/prompt_composition.py`.

## Authorization — settled, no new decision needed

`authorization.md`'s chapter matrix already fixes the skeleton rules; this feature puts a
`Capability` enum member behind each row that needed one (they were a matrix on paper with no enum
behind them):

| Action | Owner | Co-author | Reader |
|---|---|---|---|
| List / read chapters | ✓ | ✓ | ✓ *(public only)* — the existing `read_book` capability, reused unchanged |
| Add a chapter (UC-031) | ✓ | ✓ | — |
| Edit a planned chapter's sketch (UC-033) | ✓ | ✓ | — |
| Remove a planned chapter (UC-034) | ✓ | ✓ | — |
| **Set chapter order (UC-032)** | ✓ | — | — |

The owner-only reorder row is what **US-033.AC-2** requires.

**The per-author chapter prompt is a row-ownership rule, not a capability.** It is the **third** of
its kind, beside `Chat.author_id` and `BookAuthorPrompt`. `authorization.md` → "Chats" states that row
ownership "is not a matrix row"; `021` established the shape (its `outcome.md`, item 8).
**No `Capability` member and no `_CAPABILITY_MATRIX` row is added for it.** Membership is established
by the `book_access` dependency; the service then scopes every read and write to `access.user_id`.

Collaboration mode does **not** apply to the prompt: it is an author's instruction to their own
assistant, never book content, so there is nothing for an owner to review.

## The wire contract (shared by steps 002–008)

Ids are **`str` in every DTO** — snowflakes exceed the JS safe-integer range.

### Chapter DTOs

**`ChapterResponse`** — `id`, `book_id`, `ordinal`, `title`, `state`
(`planned|open|closing|closed`), `sketch`, `version`, `created_at`, `modified_at`.

**It deliberately carries no `text`, no `summary` and no `summary_status`.** The body is
`015.chapter-writing-free-mode`'s and the summary is `016.chapter-close-continuity`'s; shipping them
in the skeleton DTO would put a whole chapter body on the wire for every list render and would fix
their shape before the feature that owns them exists.

**`ChapterListResponse`** — `chapters` (ordered by `ordinal` ascending) **and `can_reorder`**, a
boolean the service computes from `access.role`, true only for the owner.

*Why a caller-relative field on this envelope is honest, when `021` refused one on
`BookDetailResponse`:* a list envelope is not a resource representation — it is the answer to **this**
caller's request — and `can_reorder` is an **affordance hint**, not content. `021`'s objection was
that two authors reading the same book-shaped resource would get different bytes for the same field.
Two authors listing chapters are asking two different questions. Enforcement stays where
`authorization.md` puts it: in the service, on the `PUT`. The hint never substitutes for it.

**`CreateChapterRequest`** — `title` (required, must not be blank), `sketch` (required, may be `""`).
`ordinal` is **server-assigned**: a new chapter is appended (UC-031).

**`UpdateChapterSketchRequest`** — `sketch` only. No version token (D6).

**`ReorderChaptersRequest`** — `chapter_ids`, the full ordered list (D3).

### Chapter-prompt DTOs

**`ChapterAuthorPromptResponse`** — `chapter_id` (`str`), `system_prompt` (`""` when the author has
none), `modified_at` (ISO timestamp or `null`). **No `user_id`** — it is always the caller, and
echoing it would invite the belief that the endpoint can serve someone else's prompt.

**`UpdateChapterAuthorPromptRequest`** — `system_prompt` only.

**A missing row is a `200` with an empty prompt, never a `404`.** "This author has not written one
yet" is the normal starting state.

### Endpoints

```
GET    /api/books/{book_id}/chapters                              → ChapterListResponse
POST   /api/books/{book_id}/chapters                              → 201 ChapterResponse
GET    /api/books/{book_id}/chapters/{chapter_id}                 → ChapterResponse
PATCH  /api/books/{book_id}/chapters/{chapter_id}                 → ChapterResponse   (sketch only)
DELETE /api/books/{book_id}/chapters/{chapter_id}                 → 204
PUT    /api/books/{book_id}/chapters/order                        → ChapterListResponse

GET    /api/books/{book_id}/chapters/{chapter_id}/system-prompt   → ChapterAuthorPromptResponse
PUT    /api/books/{book_id}/chapters/{chapter_id}/system-prompt   → 200 ChapterAuthorPromptResponse
```

**No `POST` and no `DELETE` on the prompt path.** `PUT` is the upsert and answers `200` on both
paths; `""` already expresses "no prompt", so a delete verb would add a second way to say one thing.

### Status taxonomy

Inherited from `authorization.md` → "Failure modes", plus one addition:

| Situation | Status |
|---|---|
| No valid token | `401` |
| A private book the caller has no relationship to | `404` — produced by `book_access`, never re-derived |
| A book the caller can see, but lacks the capability for (incl. a reader; a co-author reordering) | `403` |
| A chapter id that does not exist, **or belongs to another book** | `404` |
| A chapter that is **not `planned`**, on the sketch-edit or remove path | **`409`** |
| A reorder list that is not exactly the book's current chapter set | `400` |
| A malformed body | `422` (framework validation) |
| Success | `200`, `201` on create, `204` on delete |

**Why `409` and not `403` for a non-`planned` chapter.** The caller *has* the capability — a
co-author may edit sketches. What refuses them is a **state-machine constraint**, which
`domain-chapter.md` is explicit is "not authorization" and applies even to the owner. `403` would
tell the author they lack a permission they in fact hold; `409` tells them the truth — the resource is
in the wrong state. This is the status **US-034.AC-2** and **US-035.AC-2** are satisfied by.

## Out of scope — state it, do not build it

| Excluded | Owner |
|---|---|
| Opening / writing a chapter, `Chapter.text`, `ChapterChange` | `015.chapter-writing-free-mode` |
| Close, continuity, summaries, `summary_status` | `016.chapter-close-continuity` |
| Variants, `ChapterTextRevision` | `018.chapter-history-variants` |
| Wiring the chapter prompt into prompt composition or the chat turn | `015` — decision D7 |
| Reading, writing or dropping `Chapter.system_prompt` | nobody — decision D1 |
| A `chapter_access` dependency or any chapter→book resolver in `authz` | nobody — decision D4 |
| A `Capability` member or matrix row for the chapter prompt | nobody — the authorization section above |
| A `DELETE` or `POST` verb on the prompt path | nobody — the wire contract above |
| An `expected_version` / `409` path on the sketch edit | nobody — decision D6 |
| The restore buffer and draft-until-saved reconciliation | not applicable — no version token on either row this feature writes |
| The Reader SPA (`/read`) table of contents | `docs/product/` UC-029; not roadmapped here |
| Rewriting `docs/product/` FEAT-019 | `/product-spec` |
| Re-scoping `brief.md`, `roadmap.md`, `fast/003.book-system-prompt` | `/roadmap` |

## Cross-cutting backend constraints (steps 001–004)

- **Four-layer separation is enforced.** `routes/` is HTTP only — parse, call one service, return;
  `services/` holds logic and may never touch a session, `select()`, `session.add()` or
  `session.exec()`; `db/` is session-free, one module per entity, no ORM type leaking out; `models/`
  is tables plus `models/schemas/` DTOs with no logic. Dependency direction `routes → services + db`,
  `services → db`, `db → models`. Namespace imports throughout
  (`from app.db import chapters` → `await chapters.get_by_id(...)`).
- **`authz.require(access, Capability.X)` is the first line of a guarded service function**, before
  any db read. This is the existing idiom in `services/books.py` and it is what makes the `403`
  answer independent of whether a row happens to exist.
- **The error idiom, copied from `routes/books.py` + `services/books.py`:** a `*ErrorReason(str, Enum)`
  and a `*Error(Exception)` carrying `(reason, message)` in the **service**; a module-scope
  `_*_ERROR_STATUS: dict[Reason, int]` and a `_map_*_error(err) -> HTTPException` helper in the
  **route** file; every handler wraps its one service call in
  `try/except authz.BookAuthorizationError → _map_authz_error` then `except <Domain>Error → _map_*_error`.
- **DTOs are hand-mapped by a private `_to_response` in the service. ORM objects are never dumped.**
- **Timestamps are the service's, not the db layer's.** `db/` persists the row it is handed.
- **Additive schema only.** `init_db()` runs `SQLModel.metadata.create_all`, so a new table needs
  model registration and **no migration statement**; the ADDITIVE MIGRATION SEAM stays `pass`.
- **Every DB-persistent model owes its JSONL codec in the same change** (root `CLAUDE.md`).
- **Response models are the handler's return annotation, never `response_model=`.** The `{book_id}`
  path parameter is consumed entirely by `Depends(book_access)` and is not re-declared by handlers.

## Cross-cutting frontend constraints (steps 005–008)

- **`observer` on every component**, no exceptions. State is observable data plus pure `get`
  computeds; every effectful operation is an external `(state, args, signal)` function using
  `runInAction`; every loadable is an async trio (`x` / `xStatus: "idle"|"loading"|"ready"|"error"` /
  `xError`).
- **No custom `useX` hooks**, no `useCallback` / `useMemo` / `useReducer`, no React context, no
  Mantine `useForm`, no runtime schema validation. `useState` only to own a stable state instance;
  `useEffect` only at page level, mount-load / unmount-abort.
- **Page = route = fresh state instance.** New routes are keyed on their path param so React Router
  remounts them.
- **All HTTP lives in `src/api/`**; `signal?: AbortSignal` is always the trailing argument. DTOs are
  hand-written `.d.ts` in `src/types/`, wire-exact `snake_case`, **ids typed `string`**, no `any`.
- **`listChapters` returns the whole `ChapterListResponse` envelope, not a bare array** — a deliberate
  departure from `api/codex.ts`, which unwraps its list envelope. The envelope carries `can_reorder`,
  and unwrapping would discard it. Recorded here so all of steps 005–007 agree.
- **The backend is the source of truth** — after a save the surface shows what the server returned,
  not the optimistic draft.
- **Form state shape for both prompt editors and the sketch editor:** the `021` shape — a draft field,
  a separate `…ServerErrors: Record<string, string>` holder, a `…SubmitStatus`, and pure `get`
  computeds for dirtiness and submittability. `021` recorded an observation that this editor family
  has **no client-side validation layer**, so it carries `…ServerErrors` with **no `clientErrors` and
  no `errors` union**. Keep that shape. (The chapter *title* on the add form is the one field with a
  client rule — non-blank — so its form does compute one.)

## Testing facts shared by every step

**Backend (001–004)** — tests live under `backend/tests/{db,services,routes}/` plus top-level
`backend/tests/test_data_domain_*.py` for codec/registry coverage. `asyncio_mode = "auto"`, so async
tests need no decorator. `conftest.py` provides `_reset_db_ready` (autouse), `db` and `http_client`
(which wraps the real `app.main.app` over `httpx.ASGITransport`, isolates the DB via
`BOOKWRITER_DB_PATH` + `Settings.get_settings.cache_clear()`, and drives the real lifespan).

**Domain seeding helpers are per-file, not shared fixtures** — `_now()`, `_auth_header(token)`,
`_seed_user(*, username, password, role)`, `_seed_author(username) -> (User, token)`,
`_create_book(http_client, token, …) -> dict`, `_add_co_author(book_id, user_id)`. Copy them from
`backend/tests/routes/test_book_settings.py`, which is the model for a book-scoped authz route spec.
**Auth in route tests is real** — seed a user row and mint a real JWT. Service-layer specs construct
`BookAccess` directly (it is a frozen dataclass) and seed supporting rows through the sibling `db/`
modules with the `db` fixture. **No network in any test.**

Test naming: `test_<behavior>__DoD<N>_<US-id>_<AC-id>`, with the product ids omitted where a DoD item
has none (the whole chapter-prompt half).

**Frontend (005–008)** — `frontend/tests/` mirrors `src/` (`admin/`, `work/`, `user/`) plus
`support/render.tsx` (`renderWithProviders(ui, { route? })`, wrapping `MantineProvider theme env="test"`
+ `MemoryRouter`) and `support/sseFixture.ts`. `vitest.config.ts` is jsdom with **`globals: false`**,
so every spec imports `describe` / `it` / `expect` / `vi` from `"vitest"`.

The idiom: **whole-module `vi.mock("../../src/api/<mod>", () => ({ … }))` enumerating every export the
subject imports** — a missing export fails for the wrong reason. `beforeEach` re-arms
`vi.mocked(...)`. A local `renderPage(route)` wrapper around `renderWithProviders` supplies a
`<Routes><Route path=… /></Routes>` shim. **Queries are by role or label only, never test-ids.**
`ApiError` is imported real from `../../src/api/client`.
`frontend/tests/work/BookStatePage.test.tsx` is the working reference.

## Build and test gates (root `CLAUDE.md`)

- **Backend (001–004):** `cd backend && .venv/Scripts/python -m pytest`. There is **no separate
  backend typecheck** — do not invent one.
- **Frontend (005–008):** `cd frontend && npm run build` (= `tsc && vite build`),
  `cd frontend && npm test`, `cd frontend && npm run test:types`.
  `frontend/tsconfig.json` has `include: ["src"]`, so a broken spec can never break the bundle;
  `npm run test:types` is the only program covering `tests/`.

## Architecture sources

- `docs/architecture/domain-chapter.md` — the `Chapter` field table, the `planned|open|closing|closed`
  state machine, "only `planned` chapters may have their sketch edited or be removed", the
  version/concurrency contract that this feature deliberately does **not** engage (D6), and the
  `system_prompt` row that is now stale (see "Product situation").
- `docs/architecture/authorization.md` — `BookAccess`, resolve-in-a-dependency /
  decide-in-a-service, the chapter capability matrix, the "Chats" row-ownership rule that is
  deliberately not a matrix row, the `401 / 404 / 403` failure taxonomy, and the half-open item this
  feature closes.
- `docs/architecture/frontend-workspace.md` — the five Vite entries, the Shell and working-page route
  maps, the navigator, the content-pane editability table (the `planned` chapter row this feature
  amends), and the draft-until-saved / restore-buffer design this feature does not use.
- `docs/architecture/frontend.md` — the MobX rules, the state ladder, the `api/` and `types/`
  conventions.
- `docs/plans/021.per-author-system-prompt/` — the per-author-prompt quartet this feature mirrors,
  end to end. Its `outcome.md` is **not yet applied**; read it, do not assume `docs/architecture/`
  reflects it.

## Steps

| Step | File | Layer |
|---|---|---|
| 001 | `001.chapter-author-prompt-table.md` | backend — prompt model, `db/`, registration, codec; `db/chapters.py` write functions |
| 002 | `002.chapter-service.md` | backend — chapter DTOs, the chapter service, the four new capabilities |
| 003 | `003.chapter-routes.md` | backend — the `/api/books/{book_id}/chapters` route family |
| 004 | `004.chapter-prompt-service-routes.md` | backend — the per-author chapter prompt, DTOs → service → routes |
| 005 | `005.chapters-api-and-book-hub.md` | frontend — DTOs, `api/chapters.ts`, the read-only Shell book hub |
| 006 | `006.work-chapters-list.md` | frontend — the working page's chapter list: add and remove |
| 007 | `007.chapter-reorder.md` | frontend — reorder, buttons + drag |
| 008 | `008.work-chapter-item.md` | frontend — the chapter item: sketch editor, own prompt editor, subject editability |

Dependency shape: `001 → 002 → 003`; `004` needs `001` (the table) and `002` (the chapter service's
book-scoping idiom); `005` needs `003` and `004`; `006` needs `005`; `007` needs `006`; `008` needs
`005`.

## Product ids

**Delivered here:** FEAT-008 — UC-031, UC-032, UC-033, UC-034; US-032, US-033, US-034, US-035 (all
criteria). UC-032's `_TBD` is closed by D5 and UC-033's `_TBD` by D6; **transcribing those closures
into `docs/product/` is `/product-spec`'s**, carried in `outcome.md`.

**Delivered but with no id yet:** FEAT-019's chapter half **as redefined by D1** — a per-author
chapter prompt. No `UC-###` or `US-###.AC-#` currently describes it; the ids will exist once
`/product-spec` rewrites FEAT-019.

**Knowingly superseded, and cited by nothing here:** UC-094 and every criterion of US-109 — they rest
on a book-wide layer feature `021` removed.

**Not delivered:** UC-035..037 (open / close / reopen) — `015` and `016`.
