# Feature 009 — books (FEAT-006 + FEAT-007)

Feature-wide context. Step-specific facts live in each `<SSS>.context.md`.

## Goal & scope

Deliver book lifecycle, membership and visibility: an author creates a book and
becomes its owner, lists the books they own and those shared with them, and
manages a book from its settings surface (archive/unarchive, transfer ownership,
add/remove co-authors, switch visibility). Plus the book-scoped **authorization
spine** every book endpoint is gated on, and a **read-access gate + reader-safe
projection** for logged-in readers of public books.

Delivers **FEAT-006** (UC-021..024) and **FEAT-007** (UC-026..030) — **UC-025 is
out** (see Deferred below). Depends on **008.data-domain**, which already built the
`Book` / `BookMember` tables, their `db/` modules, and their JSONL codecs.

Backend = the four enforced layers (`routes → services + db`, `services → db`,
`db → models`). Frontend = the existing **Shell** Vite entry (`index.html` →
`src/user/`); **no new Rollup input** — `/books/*` already falls through to the
Shell via `spaFallback()`.

## Architecture ground truth (read before planning against a step)

- `docs/architecture/authorization.md` — **the** blueprint for step 2. Roles
  (owner / co-author / reader / admin / none), the **resolve-in-a-dependency,
  decide-in-a-service** split, the `BookAccess` typed context, the capability ×
  role matrix, the state/visibility gates, and the **401 / 404 / 403
  existence-hiding taxonomy**.
- `docs/architecture/domain-book.md` — `Book` + `BookMember` fields, the lifecycle
  (`active ↔ archived`, plus admin-only `quarantined → destroyed` which is FEAT-011,
  not here), visibility rule (public = read-only to any *logged-in* user, never
  anonymous), and "the owner is not a `BookMember` row; readers have no row".
- `docs/architecture/frontend-workspace.md` — Shell route map: `/` bookshelf,
  `/books/:bookId/settings`. The reader entry (`read/`) is described there but is
  **not built in 009** (see Deferred).
- Product: `docs/product/use-cases/FEAT-006*.md`, `FEAT-007*.md` and the matching
  `stories/*.md` — the acceptance criteria that DoD `[test]` items cite.

## Authorization taxonomy (steps 2–5, the load-bearing invariant)

From `authorization.md` → "Failure modes", applied everywhere a book endpoint is
reached:

- **No valid token → 401.** Enforced by the existing `get_current_user` dependency;
  there is no anonymous book surface.
- **A private book the caller has no relationship to → 404, not 403.** Existence
  hiding: a 403 would confirm the private book exists. Produced in **exactly one
  place** — the `book_access` resolver.
- **A book the caller can legitimately see, but a capability they lack → 403.**
  E.g. a co-author or reader attempting an owner-only mutation.
- Quarantined / destroyed → removal notice — **FEAT-011, out of scope here.** The
  resolver still resolves `book_state`, but 009 builds no gate on those states.

## Enforcement spine (step 2, consumed by 3–5)

Two steps, deliberately split (`authorization.md` → "Enforcement"):

1. **`book_access(book_id)` FastAPI dependency** resolves a typed `BookAccess`
   context (identity relative to this one book: role, `book_state`, `visibility`,
   `collaboration_mode`). Reads through `db/books` + `db/book_members` (the
   `routes → db` edge is sanctioned). Raises 401 (no token, via `get_current_user`)
   and 404 (missing book, or private-with-no-relationship). Lives beside the
   existing `require_role` dependency pattern.
2. **`authz.require(access, capability)`** in `services/` decides "may I do this?"
   against the capability × role matrix and raises a typed authorization error the
   route maps to **403**.

Books are the **first author-owned (non-admin) resource** — routes use
`Depends(auth_service.get_current_user)`, not the admin `require_role` gate.

## Backend vertical-slice conventions (template = `llm_servers`)

- Slice = `routes/books.py` + `services/books.py` + `db/books.py` (from 008) +
  `models/schemas/books.py`. Router owns its `/api/books` prefix; registered in
  `main.py` with a bare `app.include_router(books.router)` + one import (step 3).
- **Static routes declared before `/{param}` routes** — ordering is load-bearing
  (`GET /api/books/shared` must precede `GET /api/books/{book_id}`).
- Service pattern: a typed error enum + exception (mirror `LlmServerErrorReason` /
  `LlmServerError`, carrying `reason` + `message`); a private `_to_response(orm)`
  hand-mapper that **never dumps ORM**; timestamps set via
  `datetime.now(timezone.utc)`; **no `session` / `select` / `session.add` in
  services**. Route handlers `try/except` and map the domain error via a
  module-level status dict + helper (mirror `_map_llm_server_error`).
- Schemas: plain `BaseModel`; `CreateXRequest` (required) / `UpdateXRequest`
  (all `X | None = None`); **Response DTO `id` is `str`** (snowflake serialised as
  string, mirroring `AdminUserResponse.id`) — this applies to every id-bearing
  field (`owner_id`, member `user_id`); list envelope `XListResponse { items: [...] }`;
  datetimes `datetime | None`.
- IDs: `app.ids.generate_id() -> int`; DB `create()` does not assign ids — the
  model sets them via `Field(default_factory=generate_id, primary_key=True)`.

## Data layer already delivered by 008 (steps 1–5 read facts)

- `db/books.py`: `create(row) -> Book`, `get_by_id(book_id) -> Book | None`.
  **No** `update` / `list` — step 1 adds them.
- `db/book_members.py`: `create(row)`, `get_by_id(member_id)`,
  `list_by_book(book_id) -> list`. **No** `get_by_book_and_user` / `delete` /
  `list_by_user` — step 1 adds them.
- `Book` table (`models/book.py`): `id, title, description, owner_id,
  collaboration_mode, visibility, state, moderation_reason, moderated_by,
  moderated_at, system_prompt, active_notes, created_at, modified_at`. Enums
  (`str, Enum`): `CollaborationMode{free, proposal}`, `Visibility{private, public}`,
  `BookState{active, archived, quarantined, destroyed}`.
- `BookMember` table (`models/book_member.py`): `id, book_id, user_id, role
  (plain str), created_at`; unique `(book_id, user_id)`. **Owner is not a member
  row; readers have no row.** Step 1 promotes `role` to a `MemberRole` enum.
- JSONL codecs for both already exist (`services/db_import_export.py`); touch only
  if the `MemberRole` enum needs `.value` / `MemberRole(...)` for round-trip
  (`CLAUDE.md` → "DB Import/Export": every persistent model round-trips).

## Auth facts (steps 2–5)

- `app.services.auth.get_current_user(...) -> User` (raises 401).
- `app.services.auth.require_role(min_role)` — **admin gate; not used for book
  routes** (books are author-owned). `UserRole{admin, author}`.

## Test harness (backend, steps 1–5)

- `pytest` + `pytest-asyncio` (`asyncio_mode="auto"`), tests under `backend/tests/`
  split `db/`, `services/`, `routes/`, plus top-level `test_data_domain_*.py`.
- `conftest.py` fixtures: `db` (temp SQLite), `http_client` (in-process httpx
  `AsyncClient` over the real app, temp DB via `BOOKWRITER_DB_PATH`),
  `_reset_db_ready` (autouse). **No prebuilt authed-client fixture** — seed inline
  with `_seed_user(*, username, password, role)`, `auth.create_access_token(user)`,
  `_auth_header(token)`. Route tests seed an **owner author**, a **second author
  (co-author)**, and a **third (non-member)** to exercise the matrix.

## Frontend conventions (steps 6–7; template = admin Users page)

- **MobX only**, `observer` on every component. Page-state class next to the page
  with the **async-resource trio** (`data` / `dataStatus: idle|loading|ready|error`
  / `dataError`); effectful ops are external `(state, args, signal)` functions using
  `runInAction`; one page-level `useEffect([state])` with an `AbortController`.
- **Page = route = fresh state instance.** `/books/:bookId/settings` is the
  codebase's **first URL-param route** — apply the documented `key={bookId}`
  remount rule (`frontend.md`).
- **All HTTP in `src/api/`**; DTO ids are `string`. Endpoint module mirrors
  `api/admin.ts` (`const BASE`, `signal?` trailing). Types are hand-written `.d.ts`
  interfaces mirroring the backend Pydantic exactly.
- Forms **without Mantine `useForm`**: a draft class (observable field-per-input,
  `serverErrors`, `submitStatus`, `get clientErrors` / `get errors` / `get
  canSubmit`) + external `submit...(draft, ..., signal?)` mapping `ApiError` by
  status into `draft.serverErrors`.
- `App.tsx` already gates: no token → redirect to `/login/`.

### Frontend test runner — open item

`CLAUDE.md` → "Build & Test Commands" lists **only** backend `pytest` and the
frontend **build** (`npm run build` = `tsc && vite build`); it names **no frontend
unit-test runner**, and the harvest shows no frontend test files. Accordingly,
steps 6–7 DoD items are **`[manual/live]`**, gated by the frontend
typecheck-and-build (`cd frontend && npm run build`) plus manual browser
verification. The book behaviours those steps surface are already covered
`[test]` at the backend layer (steps 3–5). If the orchestrator stands up a Vitest
runner, these can be promoted to `[test]` mocking the `api/` module — flagged in
the hand-back.

## Confirmed scope decisions (do not re-litigate)

- **Reader (UC-029 / US-030): backend access-control ONLY.** No `read/` Vite entry,
  no reader SPA — chapters do not exist until Stage 5. US-030.AC-1..4 covered at the
  access-control level (public + logged-in → 200 with a reader-safe projection;
  private non-member → 404; anonymous → 401). Reader-visible TOC/chapter content is
  an **empty placeholder**.
- **Transfer to a non-co-author (UC-024 `_TBD_`): REFUSE it.** US-025.AC-1 covers
  only transferring to an existing co-author.
- **`BookMember.role` → single-value `MemberRole` enum** (value `co_author`), for
  typing discipline (step 1).
- **Archived-refuses-writes (US-024.AC-3): DEFERRED.** `BookAccess` resolves
  `book_state` for the read gates and future use, but 009 builds **no** write-refusal
  capability. The `authorization.md` "archived refuses writes" open question **stays
  open**.
- **create_book creates no chapter skeleton** (UC-021 step 4) — no `Chapter` entity
  in 009; deferred to Stage 5.

## Deferred acceptance criteria (recorded, not built in 009)

| Id | What | Deferred to | Reason |
|---|---|---|---|
| US-024.AC-3 | Archived book refuses writes | write feature (010/014) | No write/chapter path in 009; `authorization.md` open question stays open |
| US-024.AC-4 | Archive freezes an open chapter; unarchive resumes it | chapters (Stage 5) | No `Chapter` entity yet. In scope: US-024.AC-1 (state→archived), AC-2 (content preserved) |
| US-028.AC-2 | Removed co-author's blocks survive | chapters / blocks | No blocks in 009; nothing to cascade. In scope: US-028.AC-1 (access ends) |
| US-028.AC-3 | Removed co-author's attribution survives | chapters / blocks | Attribution is a field on the change, not membership; nothing to cascade in 009 |
| UC-025 / US-026.AC-1, AC-2 | Admin reassigns a disabled owner's book | admin/moderation side (later) | Explicitly out per briefing; admin capability over the ownership record, not authoring |

## Step map

1. **DB-layer extensions** — session-free `db/` functions + `MemberRole` enum.
2. **Authorization spine** — `BookAccess`, `book_access` dependency, `authz.py`.
3. **Book create + list** — schemas, service create/list, `routes/books.py`, register.
4. **Book read projections** — member detail view + reader-safe gated projection.
5. **Book settings mutations** — all owner-only mutations.
6. **Bookshelf frontend** — `api/books.ts`, types, bookshelf page + create form, route.
7. **Book settings frontend** — `/books/:bookId/settings` page wired to steps 3–5.
