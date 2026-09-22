# 013.codex — feature context

Feature-wide context. Step-specific facts live in each `<SSS>.context.md`; nothing is repeated
between the two files. The feature definition is `brief.md` (read-only, never edited by this plan).

## Goal

Make the codex real, end to end, and build the FEAT-020 mode runtime on top of it.

**Backend:** codex entries (characters / locations / facts) with create / list / get / edit, version
rows on every edit, collaboration-mode enforcement, and a book-scoped route family. The embedding
pipeline `retrieval.md` designed but nothing built — `services/embedding.py`, the LanceDB sidecar
table, the widened `VECTOR_SOURCE_REGISTRY`, the codex chunker, and incremental delete-then-reinsert
maintenance on every save. The FEAT-020 runtime: mode determination from the turn's subject, the mode
prompt layer, real `mode_tool` gating replacing `011.chat-panel`'s `resolve_tools(None)` seam, and
sub-agent delegation as synthetic tools. Two codex tools for the assistant, plus a shared-canvas
write tool and a new `canvas` SSE frame.

**Frontend:** the codex API module and DTOs, the three list pages behind the navigator entries
`010.working-page` already shipped, the codex entry page with draft-until-saved / restore buffer /
409 reconciliation, and the wiring that carries the content-pane subject into the chat turn and the
assistant's canvas draft back into the open entry.

## Scope decisions (user-confirmed — do not reopen)

1. **One feature, thirteen steps.** No split into sub-features and no roadmap re-shape, despite the
   brief flagging this as a split candidate. The three arcs share one subject model (the codex
   entry), one authorization surface and one SSE stream; splitting them would mean three plans
   negotiating the same seams.

2. **Lexical search for the author, semantic for the assistant.** The codex list endpoint filters by
   `kind` and an optional substring `q` over `name` / `body` — deterministic, testable, and working
   when no embedding server is configured. The vector index is queried **only** by the assistant's
   `codex_search` tool. Reason: it keeps the author's browse surface independent of an optional
   subsystem, and it leaves UC-078's open `_TBD:` (challenge C27 — "what makes an entry *relevant*
   enough") unresolved rather than closing it by design.

3. **Free mode only.** An owner's write always applies. A **co-author's** create or edit in a
   `proposal`-mode book is **refused** with a typed error that names FEAT-010 as unbuilt. Reason:
   FEAT-010 is roadmapped at 021+ with no proposal entity and no review surface; applying the write
   anyway would silently violate US-079.AC-2. **US-079.AC-2 is therefore knowingly unmet by this
   feature** — the gap traces to FEAT-010 and is carried into `outcome.md` so it does not read as an
   oversight. US-079.AC-1 (free mode) is met in full.

4. **The assistant's canvas write is a mode-gated tool plus a new `canvas` SSE frame.** Full design
   below.

5. **`CodexEntryVersion` rows are written by THIS feature**, not by `019.codex-history`. Reason: the
   model docstrings already assign `generation` and `modified_by` to "the feature-013 service", and
   `019` (view + restore) needs data to read on the day it ships. History *endpoints* and the history
   *view* stay out of scope.

6. **A null mode gets a base allowlist, not the whole registry.** With gating in place: a
   mode-bearing subject gets exactly its `mode_tool` rows (**zero rows ⇒ zero tools**, per
   `012.assistant-config-editor`'s settled rule,
   `docs/plans/012.assistant-config-editor/outcome.md` item 1); a subject with **no** mode (book
   state, any list, the chats view) gets a code-defined `BASE_TOOL_NAMES = ("web_search",)`.
   Reason: without this, wiring gating would silently strip web search from the chats view that
   feature `011.chat-panel` shipped. **This is a new decision not in `assistant-config.md`** and
   appears in `outcome.md` as an architecture reconciliation.

## The shared-canvas write design (settled — steps 010 + 013 implement it)

This is the design for the previously-undesigned FEAT-013 shared-canvas slice.

1. **The turn carries the subject.** `TurnRequest` gains `subject_kind`, `subject_id` and
   `codex_kind`. `codex_kind` exists because UC-076 opens a *blank* entry that has no row yet
   (`subject_id` null) — mode determination still needs the kind to resolve `edit-character` /
   `edit-location` / `edit-fact`. For an **existing** entry the backend reads `kind` off the row and
   the request's `codex_kind` is ignored.

2. **`write_codex_draft` is an ordinary `TOOL_REGISTRY` entry**, mode-gated like any other, whose
   callable is bound per turn to a tool context holding `(book_id, subject, frame queue)`. When
   invoked it:
   - validates **server-side** that the subject is an editable codex entry — mirroring
     `frontend/src/work/subject.ts:checkWritePermission`, because `frontend-workspace.md` requires a
     read-only subject to refuse the author and the assistant identically;
   - **touches no database**;
   - pushes a frame onto the same `asyncio.Queue` `run_turn` already pumps `thinking` / `delta`
     through, emitted by the existing serializer as `event: canvas`;
   - returns a short confirmation string so `chat_with_tools` keeps looping.

   Like `web_search`, it **never raises** — every failure path returns a string. A raising tool
   aborts the whole loop.

3. **New schema `CanvasFrame(subject_kind, subject_id, field, text)`** beside `ThinkingFrame` /
   `DeltaFrame` / `DoneFrame` / `ErrorFrame`. `field` exists because a character entry has both a
   `name` and a `body`.

4. **Frontend delivery uses a module-level registry** in the `work` entry — the same state tier as
   `restoreBuffer.ts` and `activeChat.ts`, which `frontend.md`'s state ladder sanctions for
   app-lifetime state. The codex entry page's state class exposes an apply-draft method; the page
   **registers itself as the canvas target on mount and unregisters on unmount** (page-level
   `useEffect`, mount/unmount only — the one sanctioned use). `streamChatTurn` gains an `onCanvas`
   handler; `ChatPaneState` forwards the frame to the registry, which dispatches to the registered
   target by `(subjectKind, subjectId)`.
   **Fallback when nothing is registered** (the author navigated away mid-turn): the draft is written
   straight into the restore buffer at `bookwriter.restore-buffer:<bookId>:codex-entry:<id>`, so
   returning to the entry surfaces it through the path that already exists.
   This avoids React Context, cross-page callbacks and custom `useX` hooks — all three banned by
   `frontend.md`.

5. **Nothing persists.** The author hand-edits if they wish, then saves through the ordinary
   UC-069 / UC-070 endpoint. There is **no code path from a chat to the `codex_entries` table at
   all** — which is what makes US-086.AC-2 / US-087.AC-2 / US-088.AC-2 true by construction rather
   than by a check.

6. **The draft arrives whole, not streamed.** `chat_with_tools` hands a tool its arguments only once
   the model has finished emitting them, so the entry fills in one jump while the chat's own prose
   streams normally. Token-level canvas streaming would require driving the loop manually, which
   `assistant-config.md` explicitly names as the later swap — **out of scope here**.

## Planner-derived decisions (recorded with reasoning)

- **Proposal-mode refusal answers `403`.** The caller can legitimately see the book, so
  `authorization.md`'s failure taxonomy gives `403` ("you are looking at the right thing and are not
  allowed to do that to it"), with the typed reason in the body naming FEAT-010. `404` would hide a
  book the co-author demonstrably belongs to; `501` would be truthful about the cause but useless to
  the author.
- **A blank entry has its own route: `/work/:bookId/codex/new?kind=<character|location|fact>`.**
  UC-076 requires a blank entry of a chosen kind to be openable before any row exists, and
  `/codex/:id` cannot express "no id yet". The kind rides in a query param because it is view state
  chosen at the moment of navigation, and the route stays deep-linkable.
- **`ToolDef` gains an optional binder; `build_tool_bindings` gains a per-turn context.** The `llm`
  client dispatches `func(**kwargs)` with no context argument, so anything a tool needs (book id,
  subject, frame queue) must be closed over. A binder field keeps `web_search`'s context-free entry
  unchanged while letting codex tools be bound per turn.
- **`db/vector.py` receives its embedder as an injected callable at `init_vector`.** `rebuild_index`
  has two callers, one of which (`db/import_export_queries.py:run_vector_rebuild`) lives in `db/`,
  and `db → services` is forbidden by the layer rule. Injecting the embedder from `app/main.py` (the
  composition root, which may import both) keeps both existing call sites' signatures intact and the
  dependency direction clean.
- **Sub-agent clients are constructed per delegation, not cached.** `assistant-config.md` leaves this
  to the planner. `LLMClient` must be entered as `async with` and has no standalone `close()`, so a
  cache would have to own client lifetimes across a whole turn and close them on every exit path —
  real bookkeeping for a call that happens at most a handful of times per turn (bounded by
  `max_loops`). Construction cost is one `aiohttp` session; correctness is worth more here.
- **`frontend/src/work/subject.ts` is consumed, not modified.** Its in-code note at line 141 says the
  free/proposal collaboration-mode nuance is `013.codex`'s to apply; decision 3 applies that nuance
  **server-side** (the save is refused with a typed 403), so the client-side subject model needs no
  change. Recorded in `outcome.md`.

## This feature does NOT depend on feature 012's code

`012.assistant-config-editor` is planned but unbuilt (all 8 steps `pending`). It does not block any
step here. The FEAT-020 tables and their thin `db/` modules landed with feature `008.data-domain`
(`db/assistant_modes.py`, `db/sub_agents.py`, `db/mode_tools.py`, `db/subagent_tools.py`,
`db/mode_subagents.py`), and the five `AssistantMode` rows are seeded at first run by
`services/setup.py`. **The mode runtime reads those `db/` modules directly**; it never touches
`services/assistant_config.py` (which is `012.assistant-config-editor`'s to create). Where the
runtime needs a read helper that does not exist yet, the step adds **only that helper** — never
`012.assistant-config-editor`'s CRUD.

The one contract this plan inherits from `012.assistant-config-editor` is its settled rule, recorded
in `docs/plans/012.assistant-config-editor/outcome.md` item 1: **zero `mode_tool` rows is an empty
allowlist, not the whole registry.**

## Out of scope — state it, do not build it

| Excluded | Owner |
|---|---|
| UC-072 archive / restore of a codex entry (US-081) | `017.codex-archive-restore` |
| UC-073 / UC-074 history view + restore endpoints (US-082, US-083) — this feature *writes* the version rows but exposes no history surface | `019.codex-history` |
| UC-075 cross-book copy (US-084) | later stage |
| Chapter / summary / state-note corpora in the vector index | later stages |
| `write-chapter` / `close-chapter` mode behaviours | `015` / `016` |
| Token budgeting, general context assembly (US-057, UC-084/085/086) | the deferred assistant session |
| Token-level canvas streaming and the manual-loop swap of `chat_with_tools` | later |
| A proposal entity or review surface (US-079.AC-2) | FEAT-010, roadmapped 021+ |
| Any new table, column or JSONL codec — the codex codecs and `TABLE_REGISTRY` are already correct and stay untouched | — |

## Cross-cutting backend constraints (steps 001–010)

- **Four-layer separation is enforced.** `routes/` is HTTP only; `services/` holds logic and may
  never touch a session, `select()`, `session.add()` or `session.exec()`; `db/` is session-free with
  one module per entity and no ORM type leaking out; `models/` is tables plus `models/schemas/` DTOs
  with no logic. Dependency direction `routes → services + db`, `services → db`, `db → models`.
  Namespace imports throughout (`from app.db import codex_entries` → `await
  codex_entries.get_by_id(...)`).
- **Route shape.** A router owns its own `/api/...` prefix and is mounted bare in `main.py`.
  Every codex route is nested under `/api/books/{book_id}/…` so `Depends(authz.book_access)` resolves
  membership for free and the 404-for-a-book-you-cannot-see rule is inherited unchanged. **The
  `{book_id}` path param is consumed entirely by the dependency — handlers do not declare it.**
  Response models are declared as the **return annotation**, never `response_model=`. Each router
  carries a module-level `_<X>_ERROR_STATUS: dict[ReasonEnum, int]` plus a `_map_<x>_error`, maps
  `authz.BookAuthorizationError` → 403, uses `status.HTTP_201_CREATED` on create, and declares
  **static path segments before `/{param}` routes**.
- **Services take `access: authz.BookAccess` as their first argument** and call
  `authz.require(access, Capability.X)` themselves. The capability check never lives in a route.
- **Typed errors, never bare exceptions.** Each service owns a reason enum plus one exception class,
  following `services/chats.py:ChatErrorReason`. No free dictionaries anywhere; Pydantic `BaseModel`
  for every API and tool schema, `TypedDict` for internal passing.
- **DTO conventions.** `CreateXRequest` / `UpdateXRequest` / `XResponse` / `XListResponse { items }`
  in `models/schemas/`; **every id is `str` in a DTO** (snowflakes exceed the JS safe-integer range);
  DTOs are hand-built by a service mapper, never dumped from the ORM; new rows need no explicit id.
- **Tools never raise.** `services/web_search.py:web_search` returns an error *string* rather than
  raising, because a raising tool aborts the whole `chat_with_tools` loop. Every tool this feature
  adds copies that contract exactly.
- **Index maintenance never blocks a save.** SQLite commits first; the index update is attempted
  afterwards and any failure is logged (`retrieval.md`). No background queue is introduced.

## Cross-cutting frontend constraints (steps 011–013)

- **`observer` on every component**, no exceptions. State is observable data plus pure `get`
  computeds; every effectful operation is an external `(state, args, signal)` function using
  `runInAction`; every loadable is an async trio (`x` / `xStatus: "idle"|"loading"|"ready"|"error"` /
  `xError`).
- **No custom `useX` hooks**, no `useCallback` / `useMemo` / `useReducer`, no React context, no
  Mantine `useForm`, no runtime schema validation. `useState` only to own a stable state instance;
  `useEffect` only at page level with mount/unmount semantics.
- **Page = route = fresh state instance.** The subject route inside the workspace shell remounts on
  path-param change (`key={id}`); the shell itself is keyed on `:bookId` and survives.
- **All HTTP lives in `src/api/`**; `signal?: AbortSignal` is always the trailing argument; list
  envelopes (`{items: […]}`) are unwrapped in the api module and are **not** modelled in the `.d.ts`.
  DTOs are hand-written `.d.ts` in `src/types/`, wire-exact `snake_case`, **ids typed `string`**, no
  `any`.
- **Query params are the filter/sort/mode persistence layer**, handled *in the event handler that
  changed them* — never a `useEffect` watching the query string (`frontend.md`:192). This feature is
  the **first consumer of query params anywhere in the repo**; there is no precedent to copy.
- **Draft-until-saved.** Content-pane edits never reach the server until an explicit save. The
  restore buffer is keyed `(bookId, subjectKind, subjectId)` and its `baseVersion` for a codex entry
  is the entry's `modified_at` ISO string.
- **A stale buffer is a visible merge problem, never an auto-merge.** A save carrying a stale base
  version is refused by the server with **409**; the client turns that refusal into a reconciliation
  view showing the server's current text against the buffered draft.
- **Module-level state is the sanctioned tier for app-lifetime state** in the `work` entry —
  `restoreBuffer.ts` and `activeChat.ts` are the existing examples; the canvas-target registry joins
  them as plain functions, not a reactive store.
- **The navigator entries already exist.** `010.working-page` shipped Characters / Locations / Facts
  with their paths, icons and `paneTarget: "content"`. This feature fills their pages; it adds no nav
  item.

## Testing facts shared by every step

**Backend (001–010)** — tests live under `backend/tests/{db,services,routes,routes/admin}/` plus flat
`test_data_domain_*.py`. `asyncio_mode="auto"`, so async tests need no decorator. `conftest.py`
provides `_reset_db_ready` (autouse), `db(tmp_path)` and `http_client(tmp_path, monkeypatch)` (which
drives the app lifespan manually). Seed helpers are copied verbatim from
`backend/tests/routes/test_chats.py`: `_now()`, `_auth_header(token)`, `_seed_user`, `_seed_author`,
`_seed_private_book`, `_add_co_author`. **Auth in route tests is real** — seed a user row and mint a
real JWT. Assertions validate responses through the DTO (`SomeResponse.model_validate(body)`).
**No network in any test**: the LLM client, the embedding client and LanceDB access are mocked.
`backend/tests/routes/test_chats.py:test_non_member_gets_404_from_every_route__DoD9` is the canonical
book-scoped-authz test shape to copy. Test naming: `test_<behaviour>__DoD<N>_<US###_AC#>`.

**Frontend (011–013)** — `frontend/vitest.config.ts` is jsdom with **`globals: false`**, so every
spec imports `describe` / `it` / `expect` / `vi` from `"vitest"`; `restoreMocks` / `clearMocks` are
true. `frontend/tests/setup.ts` adds jest-dom, stubs `matchMedia` / `ResizeObserver` /
`scrollIntoView`, and in `afterEach` runs `cleanup()` + `localStorage.clear()`.
`frontend/tests/support/render.tsx` exports `renderWithProviders(ui, { route? })`.
Specs **mock the `api/` module, never `fetch`**, in module-factory form enumerating every export the
subject imports. `ApiError` is imported real from `../../src/api/client`.
**Any spec mounting `WorkRoutes` or `WorkspaceShell` must also mock `../../src/api/chats`**
(`listChats` / `listModelOptions` → `[]`), re-armed in `beforeEach`.

## Build and test gates (root `CLAUDE.md`)

- **Backend steps 001–010:** `cd backend && .venv/Scripts/python -m pytest`. There is **no separate
  backend typecheck** — do not invent one.
- **Frontend steps 011–013:** `cd frontend && npm run build` (= `tsc && vite build`),
  `cd frontend && npm test`, `cd frontend && npm run test:types`.
  `frontend/tsconfig.json` has `include: ["src"]`, so a broken spec can never break the bundle;
  `npm run test:types` is the only program covering `tests/`.

## Architecture sources

- `docs/architecture/domain-codex.md` — `CodexEntry` / `CodexEntryVersion`, three-kinds-one-table,
  nullable `name`, archived-never-deleted, version rows carry full prior content.
- `docs/architecture/retrieval.md` — the embedding pipeline, the one-table discriminated sidecar,
  chunking, the widened registry, the two maintenance paths, the failure table, the query surface.
- `docs/architecture/assistant-config.md` — the mode-determination mapping table, prompt composition
  order, tool gating, the `chat_with_tools` seam, sub-agent delegation, model resolution.
- `docs/architecture/authorization.md` — `BookAccess`, the dependency/service split, the members-only
  codex rows in the capability matrix, and the `401 / 404 / 403` taxonomy.
- `docs/architecture/frontend-workspace.md` — working-page routes, the content-pane editability
  table, draft-until-saved, the restore buffer, and stale-buffer reconciliation.
- `docs/plans/011.chat-panel/context.md` + `outcome.md` — the verified `llm` v0.1.4 constraints and
  the seams `011.chat-panel` deliberately left here.

## Steps

| Step | File | Arc | Layer |
|---|---|---|---|
| 001 | `001.codex-db-authz.md` | A — codex authoring | backend |
| 002 | `002.codex-schemas-service.md` | A | backend |
| 003 | `003.codex-routes.md` | A | backend |
| 004 | `004.embedding-service.md` | B — retrieval | backend |
| 005 | `005.vector-sidecar.md` | B | backend |
| 006 | `006.incremental-index.md` | B | backend |
| 007 | `007.mode-runtime-gating.md` | C — FEAT-020 runtime | backend |
| 008 | `008.subagent-delegation.md` | C | backend |
| 009 | `009.codex-assistant-tools.md` | C | backend |
| 010 | `010.shared-canvas-write.md` | D — codex from chat | backend |
| 011 | `011.codex-api-list-pages.md` | E — working page | frontend |
| 012 | `012.codex-entry-page.md` | E | frontend |
| 013 | `013.subject-chat-canvas-wiring.md` | E | frontend |

Arcs A and B are independent of each other up to step 006; arc C is independent of both up to step
009. Steps 004 and 007 can start the moment 001 exists.

## Product ids

**Delivered here.**
FEAT-017 core — UC-069, UC-070, UC-071; US-078.AC-1, US-078.AC-2, US-079.AC-1, US-080.AC-1,
US-085.AC-1.
FEAT-018 — UC-076, UC-077; US-086.AC-1/AC-2, US-087.AC-1/AC-2, US-088.AC-1/AC-2.
FEAT-013 slice — UC-078 (pull-only; the relevance `_TBD:` stays open), UC-083, UC-090 (the three
codex entries), UC-092 / US-107.
FEAT-020 runtime — the runtime halves of UC-095 / UC-096 / UC-097; US-110.AC-3, US-110.AC-4,
US-111.AC-2, US-112.AC-3, US-113.AC-6.

**Knowingly unmet:** US-079.AC-2 (proposal mode holds a co-author's codex change) — see decision 3.

**Not delivered:** US-081, US-082, US-083, US-084 (UC-072/073/074/075); US-057, US-098, US-099,
US-100, US-102.
