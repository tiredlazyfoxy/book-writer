# Feature 009 — books

| Step | File                              | Status  | Verifier | Date |
|------|-----------------------------------|---------|----------|------|
| 001  | `001.db-layer-extensions.md`      | done    | PASS     | 2026-07-25 |
| 002  | `002.authorization-spine.md`      | done    | PASS     | 2026-07-25 |
| 003  | `003.book-create-list.md`         | done    | PASS     | 2026-07-25 |
| 004  | `004.book-read-projections.md`    | done    | PASS     | 2026-07-25 |
| 005  | `005.book-settings-mutations.md`  | done    | PASS     | 2026-07-25 |
| 006  | `006.bookshelf-frontend.md`       | done    | PASS     | 2026-07-25 |
| 007  | `007.book-settings-frontend.md`   | done    | PASS     | 2026-07-25 |

## Files Changed

### Step 001 — DB-layer extensions
- `backend/app/db/books.py` — implemented `update` (add/commit/refresh), `list_by_owner` (owner filter, ordered by id), `list_shared` (join through `book_members`, exclude owned); import `BookMember` for the join
- `backend/app/db/book_members.py` — implemented `get_by_book_and_user` (pair key), `delete` (pair key, returns bool), `list_by_user`
- `backend/app/services/db_import_export.py` — codec touched for DoD-2: `role` now serialised via `MemberRole(member.role).value` and rebuilt via `MemberRole(data["role"])` so the JSONL round-trip yields a true `MemberRole.co_author` instance (`table=True` skips validation, so the plain-`str` restore needed the explicit rebuild); imported `MemberRole`
- `backend/app/models/book_member.py` — unchanged by the coder (`MemberRole` enum + `role: MemberRole` retype were frozen by the skeleton)

### Step 002 — Authorization spine
- `backend/app/services/authz.py` — filled the three frozen bodies: `resolve_book_access` (reads `db/books.get_by_id` → 404 if missing; role = owner/co_author/reader/none; `role==none` → 404 existence hiding; returns `BookAccess` carrying `book_state`/`visibility`/`collaboration_mode` from the row); `book_access` dependency delegates to the resolver; `require` raises `BookAuthorizationError` when the role is outside `_CAPABILITY_MATRIX[capability]`, else returns `None`. Added imports `HTTPException` and `from app.db import book_members, books`. Frozen signatures, enums, matrix, and exception shape untouched.

### Step 003 — Book create + list
- `backend/app/services/books.py` — filled the four frozen bodies: `_to_response` hand-maps `Book` → `BookResponse` (`id`/`owner_id` as `str(...)`, no ORM dump, no moderation/prompt/notes); `create_book` builds a `Book` with `owner_id=caller.id`, requested mode/visibility, defaults `state=BookState.active`/`system_prompt=""`/`active_notes=""`/moderation triple `None`/`created_at`=`modified_at`=`datetime.now(timezone.utc)` (id via model default_factory), persists via `db/books.create`, returns `_to_response`; `list_owned` → `db/books.list_by_owner`, `list_shared` → `db/books.list_shared`, each wrapped in `BookListResponse`. Added imports `datetime, timezone`, `BookState`, and `from app.db import books`. Frozen signatures/enum/error shape untouched.
- `backend/app/models/schemas/books.py` — unchanged (schema shapes frozen by skeleton)
- `backend/app/routes/books.py` — unchanged (router wiring + error map already real in skeleton)
- `backend/app/main.py` — unchanged (import + `include_router(books.router)` already wired by skeleton; confirmed real)

### Step 004 — Book read projections
- `backend/app/services/books.py` — filled the two frozen bodies: `get_book_detail` calls `authz.require(access, Capability.view_book_detail)`, loads the book via `db/books.get_by_id` (raises `BookError(not_found)` if gone), loads members via `db/book_members.list_by_book`, reuses `_to_response` and spreads its `model_dump()` into `BookDetailResponse` plus a hand-mapped `members` list (`user_id` as `str`, `role`, `created_at`); `get_reader_book` calls `authz.require(access, Capability.read_book)`, loads the book, returns `ReaderBookResponse(title=..., chapters=[])` (empty placeholder TOC, no members-only surface). Added imports `book_members`, `BookMemberResponse`, `authz`, `Capability`. Frozen signatures untouched.
- `backend/app/models/schemas/books.py` — unchanged (DTO shapes frozen and already real in skeleton)
- `backend/app/routes/books.py` — unchanged (both GET routes, `_map_authz_error`, and error mapping already real in skeleton; confirmed)

### Step 005 — Book settings mutations
- `backend/app/services/books.py` — filled the six frozen bodies. Each function's first act is `authz.require(access, <its Capability>)` (owner-only gate → 403 before any load/mutation). `archive_book` (require `archive_book`; load; already-archived → `BookError(already_archived, 409)`; else `state=archived`, `modified_at=now(utc)`, `db/books.update`, return `_to_response`); `unarchive_book` (require `archive_book`; not-archived → `BookError(not_archived, 409)`; else `state=active`); `transfer_ownership` (require `transfer_ownership`; resolve `target_user_id` str→int; missing `book_members.get_by_book_and_user` → `BookError(transfer_target_not_member, 409)` with NO change; else `owner_id=target`); `add_member` (require `add_member`; duplicate `get_by_book_and_user` → `BookError(duplicate_member, 409)`; else `book_members.create(BookMember(role=co_author))`, return `get_book_detail(access)`); `remove_member` (require `remove_member`; `book_members.delete` False → `BookError(remove_target_not_member, 404)`; else `get_book_detail(access)`); `set_visibility` (require `set_visibility`; set `visibility`+`modified_at`). Added import `from app.models.book_member import BookMember, MemberRole`. Frozen signatures/enum/error shape untouched.
- `backend/app/models/schemas/books.py` — unchanged (the three request DTOs were frozen and already real in the skeleton)
- `backend/app/routes/books.py` — unchanged (six route handlers, `_BOOK_ERROR_STATUS` members, and error mapping already real in the skeleton; confirmed `BookAuthorizationError`→403 / `BookError`→status try/except on each)

### Step 006 — Bookshelf frontend
- `frontend/src/user/pages/bookshelfPageState.ts` — filled the two frozen effect bodies. `loadBookshelf` sets both trios to `loading`, loads the owned then shared list via `booksApi.listOwnedBooks`/`listSharedBooks`, `runInAction`s each `{ items }` → its trio (`ready`), guards `signal?.aborted`, maps `ApiError` into the matching (`ownedError`/`sharedError`) trio else rethrows (independent per-list try/catch so one list's failure doesn't blank the other). `createBookAction` awaits `booksApi.createBook` then re-calls `loadBookshelf` (create-then-reload, mirrors `disableUserAction`); abort-guarded, `ApiError` → `ownedError`. Added imports `runInAction`, `* as booksApi`, `ApiError`.
- `frontend/src/user/components/books/createBookDraft.ts` — filled `get clientErrors` (title required, trimmed) and the frozen `submitCreateBook` body (builds `CreateBookRequest` with trimmed title, sets `submitStatus=loading`, awaits `booksApi.createBook`, maps `ApiError` by status into `draft.serverErrors` — 400/422 → `title`, else `form` — calls `onCreated` on success). Added imports `runInAction`, `* as booksApi`, `ApiError`, `CreateBookRequest`.
- `frontend/src/types/books.d.ts` — unchanged (DTO shapes real in skeleton)
- `frontend/src/api/books.ts` — unchanged (endpoint calls + select-option consts real in skeleton)
- `frontend/src/user/pages/BookshelfPage.tsx` — unchanged (page wiring + list render real in skeleton)
- `frontend/src/user/components/books/CreateBookModal.tsx` — unchanged (observer modal + bound inputs real in skeleton)
- `frontend/src/user/routes.tsx` — unchanged (`/`→BookshelfPage, `/health`→HealthPage already wired by skeleton)

### Step 007 — Book settings frontend
- `frontend/src/user/pages/bookSettingsPageState.ts` — filled `loadBookSettings` (detail trio → loading, `booksApi.getBookDetail`, abort-guarded, `ApiError`→`detailError`/`error` else rethrow — mirrors `loadUsers`) and the six frozen action bodies (`archiveAction`/`unarchiveAction`/`transferAction`/`addMemberAction`/`removeMemberAction`/`setVisibilityAction`), each awaiting its mutation then re-calling `loadBookSettings` (abort-guarded, `ApiError`→`detailError`, else rethrow — mirrors `disableUserAction`). Added imports `runInAction`, `* as booksApi`, `ApiError`.
- `frontend/src/user/components/books/addCoAuthorDraft.ts` — filled `get clientErrors` (`target_user_id` required, trimmed) and `submitAddCoAuthor` (builds `AddMemberRequest`, `submitStatus=loading`, `booksApi.addMember`, maps `ApiError` 4xx→`target_user_id` else `form`, `onDone` on success). Added imports `runInAction`, `* as booksApi`, `ApiError`.
- `frontend/src/user/components/books/transferOwnershipDraft.ts` — filled `get clientErrors` (`target_user_id` required) and `submitTransferOwnership` (builds `TransferOwnershipRequest`, `booksApi.transferOwnership`, maps `ApiError` 4xx→`target_user_id` field so a server refusal of a non-co-author surfaces there, else `form`, `onDone` on success). Same imports added.
- `frontend/src/user/pages/BookSettingsPage.tsx` — built the interactive surface behind the frozen `observer`/`useParams`/`useState`/`useEffect([state])` mount-load wiring: visibility badge + toggle (`setVisibilityAction`), state badge + archive/unarchive keyed on `detail.state`, co-authors `Table` with per-row remove (`removeMemberAction`), add-co-author form (`AddCoAuthorDraft`/`submitAddCoAuthor`), transfer form (`TransferOwnershipDraft`/`submitTransferOwnership`, `Select` offering only current `detail.members`). Each control spins a fresh `AbortController`; forms re-load via `refresh` (`onDone`).
- `frontend/src/types/books.d.ts` — unchanged (DTO shapes real in skeleton)
- `frontend/src/api/books.ts` — unchanged (all seven mutation/detail calls were real `request<T>` bodies in the skeleton)
- `frontend/src/user/routes.tsx` — unchanged (`/books/:bookId/settings` + `key={bookId}` wrapper already wired by skeleton)

## Skeleton

### Step 001 — frozen interface (2026-07-25)

- `backend/app/models/book_member.py` — `class MemberRole(str, enum.Enum)` with sole member `co_author = "co_author"` — new
- `backend/app/models/book_member.py` — `BookMember.role: MemberRole` — changed (was `role: str`)
- `backend/app/db/books.py` — `async def update(row: Book) -> None` — new (add/commit/refresh convention; caller passes the mutated `Book`)
- `backend/app/db/books.py` — `async def list_by_owner(owner_id: int) -> list[Book]` — new
- `backend/app/db/books.py` — `async def list_shared(user_id: int) -> list[Book]` — new
- `backend/app/db/book_members.py` — `async def get_by_book_and_user(book_id: int, user_id: int) -> BookMember | None` — new
- `backend/app/db/book_members.py` — `async def delete(book_id: int, user_id: int) -> bool` — new (keys on the `(book_id, user_id)` pair, not the surrogate `id`; returns `True` when a row was removed, `False` on no-op)
- `backend/app/db/book_members.py` — `async def list_by_user(user_id: int) -> list[BookMember]` — new
- JSONL codec (`backend/app/services/db_import_export.py`): `_book_member_to_dict` / `_dict_to_book_member` signatures **unchanged** (frozen by 008); left untouched by the skeleton. NB for the coder: SQLModel `table=True` skips validation, so `_dict_to_book_member(...).role` restores as a plain `str` (equal to `MemberRole.co_author` by `==`, but not an instance). If DoD-2 requires a true `MemberRole` instance, rebuild via `MemberRole(data["role"])` and serialise via `.value` per the step's intent — body-only change, signature stays frozen.
- Caller-compile edits (out of Source-files scope): None. No production caller constructs `BookMember`; the sole non-test `.role` references are in the codec (a Source file). See Notes & Issues for a test-file ripple.

### Step 002 — frozen interface (2026-07-25)

New module `backend/app/services/authz.py`. All symbols new.

- `class AccessRole(str, enum.Enum)` — members `owner`, `co_author`, `reader`, `none` — new
- `class Capability(str, enum.Enum)` — members `read_book`, `view_book_detail`, `archive_book`, `transfer_ownership`, `add_member`, `remove_member`, `set_visibility` — new
- `@dataclass(frozen=True) class BookAccess` — fields `book_id: int`, `user_id: int`, `role: AccessRole`, `book_state: BookState`, `visibility: Visibility`, `collaboration_mode: CollaborationMode` — new (frozen dataclass = the "typed structure, not a dict"; enum types imported from `app.models.book`)
- `_CAPABILITY_MATRIX: dict[Capability, frozenset[AccessRole]]` — frozen policy table: `read_book`→{owner,co_author,reader}; `view_book_detail`→{owner,co_author}; `archive_book`/`transfer_ownership`/`add_member`/`remove_member`/`set_visibility`→{owner} — new (module-private; the coder must not change contents)
- `class BookAuthorizationError(Exception)` — `__init__(self, capability: Capability, role: AccessRole) -> None`; stores `.capability` and `.role`, sets a message — new (typed denial, NOT an `HTTPException`; route maps to 403)
- `async def resolve_book_access(book_id: int, user: User) -> BookAccess` — new (reads `db/books.get_by_id` + `db/book_members.get_by_book_and_user`; raises `HTTPException` 404 on missing book or `role == none`; body UNIMPLEMENTED — raises `NotImplementedError`)
- `async def book_access(book_id: int, user: User = Depends(auth_service.get_current_user)) -> BookAccess` — new (FastAPI dependency wrapper; `get_current_user` supplies 401; body UNIMPLEMENTED)
- `def require(access: BookAccess, capability: Capability) -> None` — new (raises `BookAuthorizationError` when `access.role not in _CAPABILITY_MATRIX[capability]`, else returns `None`; body UNIMPLEMENTED)
- Caller-compile edits (out of Source-files scope): None. `authz.py` is a new module with no callers yet (routes are steps 3–5).

### Step 003 — frozen interface (2026-07-25)

Three new modules + one `main.py` edit. Slice mirrors the `llm_servers` template
(typed error taxonomy, private `_to_response`, module-level status dict + `_map`
helper, `str` ids). All bodies UNIMPLEMENTED except the route wiring (which
delegates to the UNIMPLEMENTED service) and the real error→status map. Module
structure left OPEN for steps 004 (read) and 005 (mutations) to extend the shared
`BookErrorReason` enum, `_to_response`, and the router.

Schemas — `backend/app/models/schemas/books.py` (new):
- `class CreateBookRequest(BaseModel)` — fields `title: str`, `description: str`, `collaboration_mode: CollaborationMode`, `visibility: Visibility` — new (enums imported from `app.models.book`)
- `class BookResponse(BaseModel)` — fields `id: str`, `owner_id: str`, `title: str`, `description: str`, `collaboration_mode: CollaborationMode`, `visibility: Visibility`, `state: BookState`, `created_at: datetime | None`, `modified_at: datetime | None` — new (ids as strings; no moderation/prompt/notes internals)
- `class BookListResponse(BaseModel)` — field `items: list[BookResponse]` — new

Service — `backend/app/services/books.py` (new):
- `class BookErrorReason(str, enum.Enum)` — sole member `not_found = "not-found"` — new (shared taxonomy; steps 004/005 extend. Mirrors `LlmServerErrorReason`)
- `class BookError(Exception)` — `__init__(self, reason: BookErrorReason, message: str = "") -> None`; stores `.reason` + `.message` — new (mirrors `LlmServerError`)
- `def _to_response(book: Book) -> BookResponse` — new (private hand-mapper, never dumps ORM; UNIMPLEMENTED)
- `async def create_book(request: CreateBookRequest, caller: User) -> BookResponse` — new (caller becomes owner; UC-021; UNIMPLEMENTED)
- `async def list_owned(caller: User) -> BookListResponse` — new (UC-022; UNIMPLEMENTED)
- `async def list_shared(caller: User) -> BookListResponse` — new (UC-030; UNIMPLEMENTED)

Routes — `backend/app/routes/books.py` (new):
- `router = APIRouter(prefix="/api/books", tags=["books"])` — new
- `_BOOK_ERROR_STATUS: dict[books_service.BookErrorReason, int]` — `{not_found: 404}` — new (real, module-level)
- `def _map_book_error(err: books_service.BookError) -> HTTPException` — new (real)
- `POST /api/books` → `create_book(payload: CreateBookRequest, caller: User = Depends(auth_service.get_current_user)) -> BookResponse`, `status_code=201` — new
- `GET /api/books` → `list_owned(caller: User = Depends(auth_service.get_current_user)) -> BookListResponse` — new
- `GET /api/books/shared` → `list_shared(caller: User = Depends(auth_service.get_current_user)) -> BookListResponse` — new. Declared **after** the two `/api/books` routes but **before** any `/{book_id}` param route (none yet — step 004 adds it and must keep it after `/shared`); registration order confirmed `POST ""`, `GET ""`, `GET "/shared"`.
- Gate is `Depends(auth_service.get_current_user)` (author-scoped), **not** the admin `require_role` gate.

Registration — `backend/app/main.py` (edit):
- Added `from app.routes import books` and `app.include_router(books.router)` (after `auth.router`) — mechanical, in-scope Source file.

Caller-compile edits (out of Source-files scope): None. All new modules; no existing caller references these symbols.

Compile gate: `.venv/Scripts/python -c "import app.main"` → OK.

### Step 004 — frozen interface (2026-07-25)

Extends the step-3 slice — three existing Source modules. New response DTOs +
two read-projection service functions + two GET routes + a 403 authz-error
mapper. All service bodies UNIMPLEMENTED (`raise NotImplementedError`); the route
wiring is real and delegates to the UNIMPLEMENTED service.

**Settings-field decision (`BookDetailResponse`):** exposes exactly the
`BookResponse` field set (`id`, `owner_id`, `title`, `description`,
`collaboration_mode`, `visibility`, `state`, `created_at`, `modified_at`) plus
`members`. `BookDetailResponse` **subclasses** `BookResponse` (inherits all its
fields). Deliberately EXCLUDES `system_prompt` and `active_notes`: neither the
settings page (step 7 — renders visibility/state/members/transfer/add-remove) nor
the settings mutations (step 5 — archive/transfer/members/visibility) render or
mutate them; the book-wide prompt is FEAT-020 assistant-config territory, not
designed. If a later step surfaces the prompt, add it there, not retroactively.

Schemas — `backend/app/models/schemas/books.py` (extended):
- `class BookMemberResponse(BaseModel)` — fields `user_id: str`, `role: MemberRole`, `created_at: datetime | None` — new (`MemberRole` imported from `app.models.book_member`; `user_id` as string per the id convention; `created_at` = membership timestamp)
- `class BookDetailResponse(BookResponse)` — adds field `members: list[BookMemberResponse]`; inherits all `BookResponse` fields — new (members-only detail; excludes `system_prompt`/`active_notes` per decision above)
- `class ReaderBookResponse(BaseModel)` — fields `title: str`, `chapters: list[str]` — new (reader-safe UC-029 projection; `chapters` is the empty placeholder TOC — no chapters until Stage 5; carries NO members/owner/state/visibility/settings/prompt/mutation fields; exclusion enforced structurally by being a separate DTO)

Service — `backend/app/services/books.py` (extended):
- `async def get_book_detail(access: BookAccess) -> BookDetailResponse` — new (intent: `require(view_book_detail)` → load book + `db/book_members.list_by_book` → map; body UNIMPLEMENTED). `BookAccess` imported from `app.services.authz`.
- `async def get_reader_book(access: BookAccess) -> ReaderBookResponse` — new (intent: `require(read_book)` → load book → placeholder TOC; body UNIMPLEMENTED)

Routes — `backend/app/routes/books.py` (extended):
- `def _map_authz_error(err: authz.BookAuthorizationError) -> HTTPException` — new (real; maps a capability denial to **403**). `from app.services import authz` added.
- `GET /api/books/{book_id}` → `get_book_detail(access: authz.BookAccess = Depends(authz.book_access)) -> BookDetailResponse` — new. Try/except maps `BookAuthorizationError` → 403 and `BookError` → its status. Declared **after** `GET /api/books/shared` (ordering preserved).
- `GET /api/books/{book_id}/read` → `get_reader_book(access: authz.BookAccess = Depends(authz.book_access)) -> ReaderBookResponse` — new. Same error mapping. `book_access` supplies 401 (no token) / 404 (missing or private non-member) upstream.

Caller-compile edits (out of Source-files scope): None. All additions; no existing caller references the new symbols.

Compile gate: `.venv/Scripts/python -c "import app.main"` → OK.

### Step 005 — frozen interface (2026-07-25)

Extends the step-3/4 slice — the same three Source modules. Three request schemas
+ five new `BookErrorReason` members + six service functions + six routes. All
service bodies UNIMPLEMENTED (`raise NotImplementedError`); the route wiring is
real and delegates to the UNIMPLEMENTED service.

**Return-type decision:** `archive_book` / `unarchive_book` /
`transfer_ownership` / `set_visibility` → `BookResponse` (a summary suffices).
`add_member` / `remove_member` → `BookDetailResponse` (carries the updated
`members` list so the caller sees membership after the mutation).

**Target-id decision:** the target user id crosses the wire as `str` (id
convention) in `TransferOwnershipRequest.target_user_id` /
`AddMemberRequest.target_user_id` and in the `DELETE .../members/{user_id}` path
param; the **service** takes `target_user_id: str` and resolves it to `int`
(routes stay HTTP-only — they pass the raw string through). `SetVisibilityRequest`
carries a typed `Visibility` (no id resolution).

**Error-status decision** (`_BOOK_ERROR_STATUS`, new members):
- `already_archived` ("already-archived") → **409** (archive of an already-archived book)
- `not_archived` ("not-archived") → **409** (unarchive of a non-archived book)
- `transfer_target_not_member` ("transfer-target-not-a-member") → **409** (transfer to a non-co-author; DoD-5's "4xx")
- `duplicate_member` ("duplicate-add-member") → **409** (re-add of an existing member — no DB 500)
- `remove_target_not_member` ("remove-target-not-a-member") → **404** (removing a non-member — the membership resource does not exist; step intent + DoD-7)

Schemas — `backend/app/models/schemas/books.py` (extended):
- `class TransferOwnershipRequest(BaseModel)` — field `target_user_id: str` — new
- `class AddMemberRequest(BaseModel)` — field `target_user_id: str` — new
- `class SetVisibilityRequest(BaseModel)` — field `visibility: Visibility` — new (`Visibility` from `app.models.book`)

Service — `backend/app/services/books.py` (extended):
- `BookErrorReason` — added members `already_archived`, `not_archived`, `transfer_target_not_member`, `duplicate_member`, `remove_target_not_member` — changed (was sole member `not_found`)
- `async def archive_book(access: BookAccess) -> BookResponse` — new (require `archive_book`; `state=archived`; refuse `already_archived`; UNIMPLEMENTED)
- `async def unarchive_book(access: BookAccess) -> BookResponse` — new (require `archive_book`; `state=active`; refuse `not_archived`; UNIMPLEMENTED)
- `async def transfer_ownership(access: BookAccess, target_user_id: str) -> BookResponse` — new (require `transfer_ownership`; target must be a co-author else `transfer_target_not_member`; UNIMPLEMENTED)
- `async def add_member(access: BookAccess, target_user_id: str) -> BookDetailResponse` — new (require `add_member`; create `BookMember(co_author)`; duplicate → `duplicate_member`; UNIMPLEMENTED)
- `async def remove_member(access: BookAccess, target_user_id: str) -> BookDetailResponse` — new (require `remove_member`; delete membership; non-member → `remove_target_not_member` 404; UNIMPLEMENTED)
- `async def set_visibility(access: BookAccess, visibility: Visibility) -> BookResponse` — new (require `set_visibility`; UNIMPLEMENTED). Added import `Visibility` to `from app.models.book import Book, BookState, Visibility`.

Routes — `backend/app/routes/books.py` (extended):
- `_BOOK_ERROR_STATUS` — added the five members above (409×4, 404×1) — changed (was `{not_found: 404}`)
- Imports extended: `AddMemberRequest`, `SetVisibilityRequest`, `TransferOwnershipRequest` added to the schemas import block
- `POST /api/books/{book_id}/archive` → `archive_book(access: authz.BookAccess = Depends(authz.book_access)) -> BookResponse` — new
- `POST /api/books/{book_id}/unarchive` → `unarchive_book(access: authz.BookAccess = Depends(authz.book_access)) -> BookResponse` — new
- `POST /api/books/{book_id}/transfer` → `transfer_ownership(payload: TransferOwnershipRequest, access: authz.BookAccess = Depends(authz.book_access)) -> BookResponse` — new
- `POST /api/books/{book_id}/members` → `add_member(payload: AddMemberRequest, access: authz.BookAccess = Depends(authz.book_access)) -> BookDetailResponse` — new
- `DELETE /api/books/{book_id}/members/{user_id}` → `remove_member(user_id: str, access: authz.BookAccess = Depends(authz.book_access)) -> BookDetailResponse` — new (`user_id` path param typed `str`; `book_access` picks up `book_id`)
- `PATCH /api/books/{book_id}/visibility` → `set_visibility(payload: SetVisibilityRequest, access: authz.BookAccess = Depends(authz.book_access)) -> BookResponse` — new
- All six declared **after** the step-3/4 routes; each maps `BookAuthorizationError` → 403 and `BookError` → its status via the existing helpers. Distinct suffixes (`/archive`, `/unarchive`, `/transfer`, `/members`, `/members/{user_id}`, `/visibility`) don't collide with `/{book_id}` or `/{book_id}/read`.

Caller-compile edits (out of Source-files scope): None. All additions; no existing caller references the new symbols.

Compile gate: `.venv/Scripts/python -c "import app.main"` → OK.

### Step 006 — frozen interface (2026-07-25)

Frontend Shell bookshelf (`/`). Six new files + one `routes.tsx` edit. NO test
files (no frontend unit-test runner). Shapes mirror the admin Users slice
(`api/admin.ts`, `types/admin.d.ts`, `UsersPage`/`usersPageState`,
`CreateUserModal`/`CreateUserDraft`). Data shapes + component/effect-fn signatures
are frozen; the effect bodies (`loadBookshelf`, `createBookAction`,
`submitCreateBook`) throw `new Error("not implemented")`, and the draft getter
bodies are typecheck-only placeholders — the coder fills all of them. `api/books.ts`
and `routes.tsx` left OPEN for step 7.

Types — `frontend/src/types/books.d.ts` (new):
- `type CollaborationMode = "free" | "proposal"` — new (mirrors backend `CollaborationMode`)
- `type Visibility = "private" | "public"` — new (mirrors backend `Visibility`)
- `type BookState = "active" | "archived" | "quarantined" | "destroyed"` — new
- `interface BookResponse` — fields `id: string`, `owner_id: string`, `title: string`, `description: string`, `collaboration_mode: CollaborationMode`, `visibility: Visibility`, `state: BookState`, `created_at: ISODateString | null`, `modified_at: ISODateString | null` — new (mirrors backend `BookResponse`; ids as strings)
- `interface BookListResponse` — field `items: BookResponse[]` — new
- `interface CreateBookRequest` — fields `title: string`, `description: string`, `collaboration_mode: CollaborationMode`, `visibility: Visibility` — new

API — `frontend/src/api/books.ts` (new; `const BASE = "/api/books"`, `signal?` trailing):
- `async function listOwnedBooks(signal?: AbortSignal): Promise<BookListResponse>` — new → `GET /api/books`
- `async function listSharedBooks(signal?: AbortSignal): Promise<BookListResponse>` — new → `GET /api/books/shared`
- `async function createBook(body: CreateBookRequest, signal?: AbortSignal): Promise<BookResponse>` — new → `POST /api/books`
- `interface CollaborationModeOption { value: CollaborationMode; label: string }` + `const COLLABORATION_MODE_OPTIONS: CollaborationModeOption[]` — new (Select data, mirrors `ROLE_OPTIONS` placement)
- `interface VisibilityOption { value: Visibility; label: string }` + `const VISIBILITY_OPTIONS: VisibilityOption[]` — new

Page state — `frontend/src/user/pages/bookshelfPageState.ts` (new):
- `class BookshelfPageState` — two async trios: `ownedBooks: BookResponse[]`, `ownedStatus: "idle"|"loading"|"ready"|"error"`, `ownedError: string | null`; `sharedBooks`/`sharedStatus`/`sharedError` (same types); `makeAutoObservable` in ctor — new (no aggregation type)
- `async function loadBookshelf(state: BookshelfPageState, signal?: AbortSignal): Promise<void>` — new (loads both lists; body throws)
- `async function createBookAction(state: BookshelfPageState, body: CreateBookRequest, signal?: AbortSignal): Promise<void>` — new (create-then-reload; body throws)

Create draft — `frontend/src/user/components/books/createBookDraft.ts` (new):
- `class CreateBookDraft` — fields `title = ""`, `description = ""`, `collaborationMode: CollaborationMode = "free"`, `visibility: Visibility = "private"`, `serverErrors: Record<string, string> = {}`, `submitStatus: "idle"|"loading"|"ready"|"error" = "idle"`; getters `get clientErrors(): Record<string, string>`, `get errors(): Record<string, string>`, `get canSubmit(): boolean`; `makeAutoObservable` in ctor — new (getter bodies are placeholders — `clientErrors` returns `{}`; coder fills the rules)
- `async function submitCreateBook(draft: CreateBookDraft, onCreated: () => void, signal?: AbortSignal): Promise<void>` — new (body throws)

Components (React, `observer`):
- `frontend/src/user/components/books/CreateBookModal.tsx` — `const CreateBookModal` with props `{ opened: boolean; onClose: () => void; onCreated: () => void }` — new
- `frontend/src/user/pages/BookshelfPage.tsx` — `const BookshelfPage` (no props) — new

Routes — `frontend/src/user/routes.tsx` (edit):
- `UserRoutes()` — `/` now renders `<BookshelfPage />` (was `<HealthPage />`); `HealthPage` relocated to `/health` (preserved) — changed. OPEN for step 7's `/books/:bookId/settings`.

Caller-compile edits (out of Source-files scope): None. All new modules; the only edited caller is `routes.tsx` (an in-scope Source file). `App.tsx` token gate unchanged; `main.tsx` unchanged.

Compile gate: `cd frontend && npx tsc --noEmit` → clean (no errors, no `any`).

### Step 007 — frozen interface (2026-07-25)

Frontend Shell book-settings page (`/books/:bookId/settings` — the repo's first
URL-param route). Extends three step-6 Source files + four new files + one
`routes.tsx` edit. NO test files (no frontend unit-test runner). DTOs mirror the
step-4/5 Pydantic (`BookDetailResponse`, `BookMemberResponse`, the three request
bodies). Data shapes + api-call signatures + component/effect-fn/draft signatures
are frozen; the effect bodies (`loadBookSettings` + the six `*Action` fns) and the
two draft `submit*` fns throw `new Error("not implemented")`, and the draft getter
bodies are typecheck-only placeholders (`clientErrors` → `{}`) — the coder fills
all of them. The page renders a read-only async-trio scaffold; the coder adds the
visibility toggle / archive control / members-remove / add + transfer forms.

Types — `frontend/src/types/books.d.ts` (extended):
- `type MemberRole = "co_author"` — new (mirrors backend `MemberRole`, single value)
- `interface BookMemberResponse` — fields `user_id: string`, `role: MemberRole`, `created_at: ISODateString | null` — new
- `interface BookDetailResponse extends BookResponse` — adds `members: BookMemberResponse[]` — new (members-only detail; excludes `system_prompt`/`active_notes` per step-4 decision)
- `interface TransferOwnershipRequest` — field `target_user_id: string` — new
- `interface AddMemberRequest` — field `target_user_id: string` — new
- `interface SetVisibilityRequest` — field `visibility: Visibility` — new

API — `frontend/src/api/books.ts` (extended; ids interpolated into paths, `signal?` trailing):
- `async function getBookDetail(bookId: string, signal?: AbortSignal): Promise<BookDetailResponse>` — new → `GET /api/books/{id}`
- `async function archiveBook(bookId: string, signal?: AbortSignal): Promise<BookResponse>` — new → `POST /api/books/{id}/archive`
- `async function unarchiveBook(bookId: string, signal?: AbortSignal): Promise<BookResponse>` — new → `POST /api/books/{id}/unarchive`
- `async function transferOwnership(bookId: string, body: TransferOwnershipRequest, signal?: AbortSignal): Promise<BookResponse>` — new → `POST /api/books/{id}/transfer`
- `async function addMember(bookId: string, body: AddMemberRequest, signal?: AbortSignal): Promise<BookDetailResponse>` — new → `POST /api/books/{id}/members`
- `async function removeMember(bookId: string, userId: string, signal?: AbortSignal): Promise<BookDetailResponse>` — new → `DELETE /api/books/{id}/members/{userId}`
- `async function setVisibility(bookId: string, body: SetVisibilityRequest, signal?: AbortSignal): Promise<BookResponse>` — new → `PATCH /api/books/{id}/visibility`
- **Return-type decision** mirrors step 5: archive/unarchive/transfer/set-visibility → `BookResponse`; add/remove-member → `BookDetailResponse`. Actions re-load the detail regardless, so all seven results feed the same re-load path.

Page state — `frontend/src/user/pages/bookSettingsPageState.ts` (new):
- `class BookSettingsPageState` — one async trio: `detail: BookDetailResponse | null`, `detailStatus: "idle"|"loading"|"ready"|"error"`, `detailError: string | null`; `makeAutoObservable` in ctor — new
- `async function loadBookSettings(state: BookSettingsPageState, bookId: string, signal?: AbortSignal): Promise<void>` — new (body throws)
- `async function archiveAction(state: BookSettingsPageState, bookId: string, signal?: AbortSignal): Promise<void>` — new (body throws)
- `async function unarchiveAction(state: BookSettingsPageState, bookId: string, signal?: AbortSignal): Promise<void>` — new (body throws)
- `async function transferAction(state: BookSettingsPageState, bookId: string, body: TransferOwnershipRequest, signal?: AbortSignal): Promise<void>` — new (body throws)
- `async function addMemberAction(state: BookSettingsPageState, bookId: string, body: AddMemberRequest, signal?: AbortSignal): Promise<void>` — new (body throws)
- `async function removeMemberAction(state: BookSettingsPageState, bookId: string, userId: string, signal?: AbortSignal): Promise<void>` — new (body throws)
- `async function setVisibilityAction(state: BookSettingsPageState, bookId: string, body: SetVisibilityRequest, signal?: AbortSignal): Promise<void>` — new (body throws)

Drafts (create shape; template = `CreateUserDraft` / `serverFormDraft.ts`):
- `frontend/src/user/components/books/addCoAuthorDraft.ts` (new) — `class AddCoAuthorDraft` (field `targetUserId = ""`, `serverErrors: Record<string, string> = {}`, `submitStatus: "idle"|"loading"|"ready"|"error" = "idle"`; getters `get clientErrors(): Record<string, string>` (placeholder `{}`), `get errors(): Record<string, string>`, `get canSubmit(): boolean`; `makeAutoObservable`); `async function submitAddCoAuthor(draft: AddCoAuthorDraft, bookId: string, onDone: () => void, signal?: AbortSignal): Promise<void>` — new (body throws)
- `frontend/src/user/components/books/transferOwnershipDraft.ts` (new) — `class TransferOwnershipDraft` (same field/getter shape, `targetUserId`); `async function submitTransferOwnership(draft: TransferOwnershipDraft, bookId: string, onDone: () => void, signal?: AbortSignal): Promise<void>` — new (body throws)

Component — `frontend/src/user/pages/BookSettingsPage.tsx` (new):
- `const BookSettingsPage` — `observer`, no props; reads `bookId` via `useParams`; `useState(() => new BookSettingsPageState())`; page-level `useEffect([state])` with an `AbortController` calling `void loadBookSettings(state, bookId ?? "", ctrl.signal)`; renders a read-only async-trio scaffold — new

Routes — `frontend/src/user/routes.tsx` (edit):
- Added `function BookSettingsRoute()` — reads `bookId` via `useParams`, renders `<BookSettingsPage key={bookId} />` (the `key`-remount wrapper: the key must sit on a parent that knows the param). Added `<Route path="/books/:bookId/settings" element={<BookSettingsRoute />} />` and `useParams` import — changed.

Caller-compile edits (out of Source-files scope): `frontend/src/api/client.ts` — added `"PATCH"` to the `RequestOptions.method` union (`"GET" | "POST" | "PUT" | "PATCH" | "DELETE"`). Minimal type-only edit required so `setVisibility` (a `PATCH`) typechecks; the `fetch` call already forwards `opts.method` unchanged, so no behavior change and no existing caller is affected.

Compile gate: `cd frontend && npx tsc --noEmit` → clean (no errors, no `any`).

## Tests

### Step 001 — tests (2026-07-25)

- `backend/tests/db/test_book_members.py` — covers DoD-1, DoD-6, DoD-7, DoD-8 — MemberRole is a single-value `(str, Enum)` co_author + role value preserved through the DB; `get_by_book_and_user` match/None; `delete` keys on the pair, reports removal, no-ops on second call; `list_by_user` returns every membership for a user.
- `backend/tests/db/test_books.py` — covers DoD-3, DoD-4, DoD-5 — `update` persists field changes (get_by_id returns new values); `list_by_owner` returns only that owner's books; `list_shared` returns only co-author-not-owner books (excludes owned even with a membership row, no-membership, and other-member books).
- `backend/tests/test_data_domain_member_role_codec.py` — covers DoD-2 — Book + BookMember JSONL codec round-trip preserves `role` as `MemberRole.co_author` (value equality).
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 [manual/live, no test].
- Sanctioned repair: `backend/tests/test_data_domain_book.py` (008 file, out of step Test-files) — `test_book_members_db_round_trip_and_list__DoD3` and `test_book_member_composite_unique_enforced__DoD4` re-seeded to `MemberRole.co_author`; imported `MemberRole`. In DoD3 the now-stale `assert fetched.role == "co-author"` was updated to `== MemberRole.co_author` (the retype makes the value `co_author`, so leaving the hyphen assertion would fail the suite).

### Step 002 — tests (2026-07-25)

- `backend/tests/services/test_authz.py` — covers DoD-1..DoD-7 — resolver role resolution + existence-hiding 404s against the seeded temp DB, and the capability×role matrix via `require` on directly-built `BookAccess`. Specifically:
  - DoD-1: `resolve_book_access` → `owner` for owner, `co_author` for a membership-row holder on a private book.
  - DoD-2: `resolve_book_access` → `reader` for a logged-in non-member on a public book.
  - DoD-3: `resolve_book_access` raises `HTTPException` with `status_code == 404` for a non-member on a private book (existence hiding).
  - DoD-4: `resolve_book_access` raises `HTTPException` 404 for a non-existent `book_id`.
  - DoD-5: returned `BookAccess` carries `book_state` / `visibility` / `collaboration_mode` from the book row (distinct non-default values seeded).
  - DoD-6: `require` returns `None` for owner+mutation and reader+`read_book`; raises `BookAuthorizationError` for co_author/reader on an owner-only cap.
  - DoD-7: `require(..., view_book_detail)` raises `BookAuthorizationError` for reader; returns `None` for owner and co_author.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 [manual/live, no test].

### Step 003 — tests (2026-07-25)

- `backend/tests/routes/test_books.py` — covers DoD-1..DoD-7 — in-process HTTP over the real app (`http_client`), authors seeded inline via a local `_seed_user(role=UserRole.author)` + `auth.create_access_token` + `_auth_header`; shared books seeded by inserting a `MemberRole.co_author` `BookMember` via `db/book_members.create`. Specifically:
  - DoD-1: `POST /api/books` with `collaboration_mode="proposal"` + `visibility="public"` → 201; response reflects both.
  - DoD-2: create response `owner_id == str(caller.id)`.
  - DoD-3: create defaults `state == "active"`.
  - DoD-4: `POST /api/books` with no token → 401.
  - DoD-5: `GET /api/books` (author A) contains A's book, excludes B-owned book; every returned item owned by A.
  - DoD-6: `GET /api/books/shared` (author B, co-author of A's book X) contains X, excludes B's own book Y and unrelated A-owned Z; no returned item owned by B.
  - DoD-7: create result and list items have `id` / `owner_id` as JSON `str`.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 [manual/live, no test].

### Step 004 — tests (2026-07-25)

- `backend/tests/routes/test_book_read.py` — covers DoD-1..DoD-7 — in-process HTTP over the real app (`http_client`), authors seeded inline via a local `_seed_user(role=UserRole.author)` + `auth.create_access_token` + `_auth_header`; visibility chosen at POST-create time; co-author seeded by inserting a `MemberRole.co_author` `BookMember` via `db/book_members.create`. Specifically:
  - DoD-1: `GET /api/books/{book_id}` → 200 + `members` list (contains the co-author, `user_id == str(co_author.id)`) for the owner AND the co-author of a **private** book (two tests); response validates against `BookDetailResponse`.
  - DoD-2: `GET /api/books/{book_id}` → 404 for a logged-in non-member of a **private** book (existence hiding).
  - DoD-3: `GET /api/books/{book_id}` → 403 for a logged-in non-member reader of a **public** book.
  - DoD-4: `GET /api/books/{book_id}/read` → 200 for a logged-in non-member of a **public** book; validates `ReaderBookResponse`, `title` matches the created book.
  - DoD-5: `/read` JSON keys are EXACTLY `{"title", "chapters"}`; asserts each members-only field (`members`, `owner_id`, `id`, `state`, `visibility`, `collaboration_mode`, `description`, `system_prompt`, `active_notes`, `moderation_reason`, `moderated_by`, `moderated_at`) is ABSENT; `chapters` is a list (placeholder shape only).
  - DoD-6: `GET /api/books/{book_id}/read` → 404 for a logged-in non-member of a **private** book.
  - DoD-7: `GET /api/books/{book_id}/read` without a token → 401.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 [manual/live, no test].

### Step 005 — tests (2026-07-25)

- `backend/tests/routes/test_book_settings.py` — covers DoD-1..DoD-10 — in-process HTTP over the real app (`http_client`), owner author + co-author (BookMember row via `db/book_members.create`, `MemberRole.co_author`) + third non-member author seeded inline via `_seed_author` (`auth.create_access_token` + `_auth_header`); target user ids cross the wire as STRING per the frozen request DTOs. Specifically:
  - DoD-1: `POST /{book_id}/archive` (owner) → 200 + `state == "archived"`; validates `BookResponse`.
  - DoD-2: after archive, the exposed content fields `title` / `description` are unchanged (BookResponse excludes `system_prompt`/`active_notes`, so preservation asserted over the exposed content surface per the DoD-2 note).
  - DoD-3: `POST /{book_id}/archive` then `/unarchive` (owner) round-trip → `state == "active"` with `title`/`description` intact.
  - DoD-4: `POST /{book_id}/transfer` `{target_user_id: str(co_author.id)}` (owner) → 200 + `owner_id == str(co_author.id)`.
  - DoD-5: `POST /{book_id}/transfer` to a non-member → **409** (frozen `transfer_target_not_member`); ownership unchanged (owner detail still `owner_id == str(owner.id)`).
  - DoD-6: `POST /{book_id}/members` `{target_user_id: str(target.id)}` (owner) → 200 `BookDetailResponse` whose `members` contains the target; target can then open `GET /{book_id}` (200).
  - DoD-7: `DELETE /{book_id}/members/{user_id}` (owner) → 200; removed co-author (who could open the private book before) now gets **404** on `GET /{book_id}`.
  - DoD-8: `PATCH /{book_id}/visibility` `{visibility:"public"}` (owner) → 200; a logged-in non-member then gets **200** on `GET /{book_id}/read` (404 before the flip).
  - DoD-9: `PATCH /{book_id}/visibility` `{visibility:"private"}` (owner) → 200; the same non-member then gets **404** on `GET /{book_id}/read` (200 before the flip).
  - DoD-10: parametrized over archive / transfer / add-member / remove-member / set-visibility — a CO-AUTHOR caller (member of the private book) is refused **403** on every one (owner-only matrix).
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓, DoD-10 ✓, DoD-11 [manual/live, no test].

## Notes & Issues

_populated by the coder when worth saying_

### Step 001 (skeleton, 2026-07-25) — `MemberRole` retype ripples into an out-of-scope 008 test file

The `BookMember.role` → `MemberRole` retype turns the `role` column into a SQLAlchemy `Enum` with the single valid value `co_author`. Two previously-passing 008 tests in `backend/tests/test_data_domain_book.py` seed invalid literal roles and now fail at DB read/write with `LookupError: '<x>' is not among the defined enum values`:

- `test_book_members_db_round_trip_and_list__DoD3` — seeds `role="co-author"` (hyphen).
- `test_book_member_composite_unique_enforced__DoD4` — seeds `role="co-author"` and `role="editor"`.

This file is **not** in step 001's Test-files list and is a test file outside the skeleton's write scope, so the skeleton did not modify it. The retype is unambiguously demanded by the step (Interface intent + DoD-1) and the frozen interface compiles cleanly, so the interface was frozen as specified. Resolution needed from the orchestrator: update those two 008 tests to use `MemberRole.co_author` (the `role="editor"` case no longer has a valid value — the test asserts composite-`(book_id, user_id)`-uniqueness, so both rows can use `co_author`; uniqueness is on the pair, not the role). Options: (a) route the fix to the test-coder as a scope addition, or (b) fold `test_data_domain_book.py` into step 001's Test files. Either keeps the full suite green.
