# Feature 026 — memos

| Step | File                            | Status  | Verifier | Date |
|------|---------------------------------|---------|----------|------|
| 001  | `001.memo-table.md`             | done    | PASS     | 2026-09-15 |
| 002  | `002.memo-service.md`           | done    | PASS     | 2026-09-15 |
| 003  | `003.memo-routes.md`            | done    | PASS     | 2026-09-15 |
| 004  | `004.memo-reorder.md`           | done    | PASS     | 2026-09-15 |
| 005  | `005.memo-state-axes.md`        | done    | PASS     | 2026-09-15 |
| 006  | `006.memos-prompt-layer.md`     | pending | —        | —    |
| 007  | `007.memos-in-delegation.md`    | pending | —        | —    |
| 008  | `008.create-memo-tool.md`       | pending | —        | —    |
| 009  | `009.memos-api-and-navigator.md`| pending | —        | —    |
| 010  | `010.memos-list-page.md`        | pending | —        | —    |
| 011  | `011.memos-list-reorder.md`     | pending | —        | —    |

## Files Changed

### Step 001 — the `memos` table, its `db/` module, registration and JSONL codec
- `backend/app/models/memo.py` — the `Memo` SQLModel table, no unique constraint (skeleton-written, unchanged)
- `backend/app/db/memos.py` — session-free `create` / `get_by_id` / `list_for_author` / `update`; no delete, no timestamp policy
- `backend/app/db/engine.py` — `Memo` added to the MODEL-REGISTRATION SEAM (skeleton-written, unchanged)
- `backend/app/services/db_import_export.py` — `_memo_to_dict` / `_dict_to_memo` codec pair and the `memos` registry entry at index 11

### Step 002 — the memo schemas and the read / create / update service
- `backend/app/models/schemas/memos.py` — the four memo DTOs (skeleton-written, unchanged)
- `backend/app/services/memos.py` — `_require_member` / `_to_memo_response` / `_resolve_memo` / `list_memos` / `create_memo` / `update_memo_body` implemented, plus a module-private `_next_ordinal` helper (the single append rule, reused by steps 005 and 008)

### Step 003 — the list / create / body-update memo routes
- `backend/app/routes/memos.py` — `_map_memo_error` plus the `list_memos` / `create_memo` / `update_memo_body` handler bodies implemented; the router, the two-entry reason→status map, the frozen signatures and the load-bearing declaration order (the `/{memo_id}` PUT last, with step 004's insertion-point comment above it) are skeleton-written and unchanged
- `backend/app/main.py` — router import and `include_router` (skeleton-written, unchanged)

### Step 004 — reorder: the whole-set service rule and `PUT …/memos/order`
- `backend/app/services/memos.py` — `reorder_memos` body implemented: loads the caller's non-archived set, refuses a wrong length / duplicate / absent id whole as one `invalid_reorder_set` before any write, then rewrites ordinals `1..N` per row through `db.memos.update`; no `authz.require`, no `Capability`, no `book_state` read, no bulk `db/` writer
- `backend/app/routes/memos.py` — `reorder_memos` handler body implemented: delegates and maps `MemoError` through `_map_memo_error` (HTTP only)
- `backend/app/models/schemas/memos.py` — `ReorderMemosRequest` skeleton-written, unchanged

### Step 005 — the two axes: activate / deactivate, archive / restore
- `backend/app/services/memos.py` — the four state-axis bodies implemented: each guards membership, resolves through the existing `_resolve_memo` (one `404`-shaped refusal), writes exactly one flag and stamps `modified_at`; archive leaves **both** `active` and `ordinal` alone (the gap is never renumbered), restore appends last through step 002's `_next_ordinal` and preserves `active`; all four are idempotent `200` no-ops that write nothing — not even `modified_at` — when the memo is already in the requested state (restore's no-op leaves `ordinal` alone too); no new reason, no `409`, no delete, no `book_state` read
- `backend/app/routes/memos.py` — the four no-body `POST` handler bodies implemented: delegate and map `MemoError` through the unchanged `_map_memo_error` / `_MEMO_ERROR_STATUS` (HTTP only); declaration order and signatures skeleton-written and unchanged

## Skeleton

### Step 001 — frozen interface (2026-09-15)

**`backend/app/models/memo.py`** — new module. Declarative table, written in full
(field declarations *are* the signature); no unimplemented body.

- `backend/app/models/memo.py` — `class Memo(SQLModel, table=True)`, `__tablename__ = "memos"`, **no `__table_args__`** — new
  - `id: int = Field(default_factory=generate_id, primary_key=True)`
  - `book_id: int = Field(foreign_key="books.id")`
  - `user_id: int = Field(foreign_key="users.id")`
  - `body: str`
  - `ordinal: int`
  - `active: bool = Field(default=True)`
  - `archived: bool = Field(default=False)`
  - `created_at: datetime | None = Field(default=None)`
  - `modified_at: datetime | None = Field(default=None)`

**`backend/app/db/memos.py`** — new module, four functions, no `delete`. Bodies
`raise NotImplementedError`.

- `backend/app/db/memos.py` — `async def create(row: Memo) -> Memo` — new
- `backend/app/db/memos.py` — `async def get_by_id(memo_id: int) -> Memo | None` — new
- `backend/app/db/memos.py` — `async def list_for_author(book_id: int, user_id: int, include_archived: bool = False) -> list[Memo]` — new
- `backend/app/db/memos.py` — `async def update(row: Memo) -> Memo` — new

**`backend/app/db/engine.py`** — registration only.

- `backend/app/db/engine.py` — `_register_models()` gains `import app.models.memo  # noqa: F401` as the last line of the MODEL-REGISTRATION SEAM — changed (import list only; `ADDITIVE_COLUMNS` and the ADDITIVE MIGRATION SEAM untouched)

**`backend/app/services/db_import_export.py`** — codec pair + one registry entry.
Codec bodies `raise NotImplementedError`.

- `backend/app/services/db_import_export.py` — `def _memo_to_dict(memo: Memo) -> dict[str, object]` — new
- `backend/app/services/db_import_export.py` — `def _dict_to_memo(data: dict[str, object]) -> Memo` — new
- `backend/app/services/db_import_export.py` — `TABLE_REGISTRY` gains `("memos", Memo, _memo_to_dict, _dict_to_memo)` at **index 11** (immediately after the `chapter_author_prompts` tuple, immediately before `("chapters", Chapter, …)`) — changed. Module-level `from app.models.memo import Memo` added.

Frozen export key set for the codec pair: `{"id", "book_id", "user_id", "body",
"ordinal", "active", "archived", "created_at", "modified_at"}` — ids emitted as
`str(...)` and parsed string-or-legacy-number; timestamps `.isoformat()` /
`datetime.fromisoformat`, both nullable.

- Caller-compile edits (out of Source-files scope): None. Nothing in `backend/app/` referenced any of these symbols before this step.

Verification: `cd backend && .venv/Scripts/python -c "import app.main"` clean;
`TABLE_REGISTRY` label list is 21 entries with exactly one `memos` at index 11,
between `chapter_author_prompts` and `chapters`. (Backend has no separate
typecheck — import is the gate.)

### Step 002 — frozen interface (2026-09-15)

**`backend/app/models/schemas/memos.py`** — new module. Declarative Pydantic
DTOs, written in full (field declarations *are* the signature); no unimplemented
body. **No reorder request DTO** — that is step 004's, added to this module when
it has a caller.

- `backend/app/models/schemas/memos.py` — `class CreateMemoRequest(BaseModel)` — new
  - `body: str` — no constraint of any kind (`""` is legitimate input, never a 422)
- `backend/app/models/schemas/memos.py` — `class UpdateMemoRequest(BaseModel)` — new
  - `body: str` — and nothing else: no `expected_modified_at`, no `active` / `archived` flags
- `backend/app/models/schemas/memos.py` — `class MemoResponse(BaseModel)` — new
  - `id: str`
  - `book_id: str`
  - `body: str`
  - `ordinal: int`
  - `active: bool`
  - `archived: bool`
  - `created_at: UtcDateTime | None`
  - `modified_at: UtcDateTime | None`
  - **no `user_id` field** — the subject is always the caller (`context.md` → "The wire contract")
- `backend/app/models/schemas/memos.py` — `class MemoListResponse(BaseModel)` — new
  - `items: list[MemoResponse]`

`UtcDateTime` is `app.models.schemas.common.UtcDateTime` (the `CodexEntryResponse`
timestamp precedent); both stamps are nullable because the `Memo` columns are.

**`backend/app/services/memos.py`** — new module. Eight frozen symbols; every
function body `raise NotImplementedError("026 step 002 — skeleton stub")`.

- `backend/app/services/memos.py` — `class MemoErrorReason(str, enum.Enum)` with exactly two members — new
  - `not_a_member = "not-a-member"`
  - `not_found = "not-found"` (one reason for all four sources; step 004 adds the third member)
- `backend/app/services/memos.py` — `class MemoError(Exception)` — new
  - `def __init__(self, reason: MemoErrorReason, message: str = "") -> None` — sets `self.reason` / `self.message`
- `backend/app/services/memos.py` — `def _require_member(access: authz.BookAccess) -> None` — new
- `backend/app/services/memos.py` — `def _to_memo_response(row: Memo) -> MemoResponse` — new
- `backend/app/services/memos.py` — `async def _resolve_memo(access: authz.BookAccess, memo_id: str) -> Memo` — new
- `backend/app/services/memos.py` — `async def list_memos(access: authz.BookAccess, include_archived: bool = False) -> MemoListResponse` — new
- `backend/app/services/memos.py` — `async def create_memo(access: authz.BookAccess, req: CreateMemoRequest) -> MemoResponse` — new
- `backend/app/services/memos.py` — `async def update_memo_body(access: authz.BookAccess, memo_id: str, req: UpdateMemoRequest) -> MemoResponse` — new

Frozen properties beyond the signatures:

- **`BookAccess` is the first parameter of every entry point**, and no entry
  point takes a user id or a book id as a separate parameter — the scoping is
  structural (`context.md` → decision 3).
- The wire `memo_id` is a **`str`** and is parsed inside `_resolve_memo`, not in
  the route: a non-numeric id is `not_found`, never FastAPI's `422`.
- The create/update entry points take the **request DTO**, not a bare string
  (the `codex_service.create_entry(access, CreateCodexEntryRequest(...))`
  precedent) — step 008's tool constructs a `CreateMemoRequest` the same way.
- No `authz.require`, no `Capability`, no `_CAPABILITY_MATRIX` row; module
  imports are `enum`, `from app.db import memos`, `app.models.memo.Memo`, the
  four DTOs, and `from app.services import authz`. **No `session` /
  `AsyncSession` / `select()` / `session.exec()` / `session.add()`** appears in
  the module (the only textual match is the layer-rule sentence in the
  docstring, copied from `services/book_author_prompts.py`).
- `BookAccess.book_state` and `BookAccess.collaboration_mode` are **not read**.
- No private `_next_ordinal` helper is frozen: the append rule is stated as
  `create_memo`'s contract, and factoring it into a private helper is the
  coder's call (step 005's restore reuses whatever this step's implementation
  lands, per `005.memo-state-axes.md`).

- Caller-compile edits (out of Source-files scope): None. Nothing in `backend/app/` referenced either module before this step; `backend/app/main.py` is untouched (the router is step 003's).

Verification: `cd backend && .venv/Scripts/python -c "import app.main"` clean,
and the eight service signatures plus the four DTO field lists were re-read back
through `inspect.signature` / `model_fields`. (Backend has no separate
typecheck — import is the gate.)

### Step 003 — frozen interface (2026-09-15)

**`backend/app/routes/memos.py`** — new module. Router, reason → status map, one
mapping helper and three handlers. The helper and all three handler bodies
`raise NotImplementedError("026 step 003 — skeleton stub")`.

- `backend/app/routes/memos.py` — `router = APIRouter(prefix="/api/books", tags=["memos"])` — new
- `backend/app/routes/memos.py` — `_MEMO_ERROR_STATUS: dict[memos_service.MemoErrorReason, int]` — new
  - `MemoErrorReason.not_a_member: status.HTTP_403_FORBIDDEN`
  - `MemoErrorReason.not_found: status.HTTP_404_NOT_FOUND`
  - exactly **two** entries at this step; step 004 adds the third (invalid reorder set → 400)
- `backend/app/routes/memos.py` — `def _map_memo_error(err: memos_service.MemoError) -> HTTPException` — new
- `backend/app/routes/memos.py` — `@router.get("/{book_id}/memos")` →
  `async def list_memos(include_archived: bool = False, access: authz.BookAccess = Depends(authz.book_access)) -> MemoListResponse` — new
- `backend/app/routes/memos.py` — `@router.post("/{book_id}/memos", status_code=status.HTTP_201_CREATED)` →
  `async def create_memo(payload: CreateMemoRequest, access: authz.BookAccess = Depends(authz.book_access)) -> MemoResponse` — new
- `backend/app/routes/memos.py` — `@router.put("/{book_id}/memos/{memo_id}")` →
  `async def update_memo_body(memo_id: str, payload: UpdateMemoRequest, access: authz.BookAccess = Depends(authz.book_access)) -> MemoResponse` — new

Frozen properties beyond the signatures:

- **Declaration order is load-bearing and frozen**: the `/{memo_id}` `PUT` is the
  **last** route in the module, and a comment above it marks the insertion point
  where step 004's `PUT /{book_id}/memos/order` goes — FastAPI matches in
  declaration order, so a literal `order` segment declared after `/{memo_id}`
  would be swallowed as a memo id (the `routes/chapters.py` comment convention).
  Step 005's four `/{memo_id}/<verb>` routes belong beside the last route.
- **No handler declares `book_id`** — `Depends(authz.book_access)` consumes the
  path param entirely; `book_id` still appears in OpenAPI as a path parameter,
  contributed by the dependency.
- **Response models are the return annotations**, never `response_model=`.
- `memo_id` is typed **`str`** and is passed to the service **verbatim**; the
  route performs no parsing, so a non-numeric id is the service's `not_found`
  → 404, never FastAPI's 422.
- `include_archived` is a **query** parameter, `bool`, **default `False`**, not
  required (the `routes/codex.py` list precedent).
- **No `authz.require`, no `Capability`, no `_map_authz_error`**, and **no
  archived-book refusal** (the named carve-out — unlike `routes/chapters.py`).
- **`401` and the private-book `404` are never re-derived here** — both come from
  the dependency. The only statuses this module produces are 403 and 404 (from
  the map), 200 and 201 (from the annotations / `status_code=`).
- **No `DELETE`** on any memo path; the framework's own 405 is the answer.
- Module imports are `fastapi` (`APIRouter`, `Depends`, `HTTPException`,
  `status`), the four DTOs from `app.models.schemas.memos`,
  `from app.services import authz` and `from app.services import memos as
  memos_service`. No `db` import, no `session` / `select()`.

**`backend/app/main.py`** — registration only, and **real, not stubbed**.

- `backend/app/main.py` — `from app.routes import memos` added to the route import
  block (alphabetical, between `health` and `reader`) — changed
- `backend/app/main.py` — `app.include_router(memos.router)` added after
  `app.include_router(chapter_author_prompts.router)`, beside the other
  book-scoped routers — changed. Include order is not load-bearing against the
  other `/api/books` routers: every memo path carries the literal `memos`
  segment.

- Caller-compile edits (out of Source-files scope): None. Nothing referenced
  `app.routes.memos` before this step.

Verification: `cd backend && .venv/Scripts/python -c "import app.main"` clean; the
live app's OpenAPI carries `/api/books/{book_id}/memos` with `get` + `post` (POST
declaring **201**) and `/api/books/{book_id}/memos/{memo_id}` with `put` (200),
`include_archived` present as an optional query param defaulting to `false`, and
the router's own declaration order ending with the `/{memo_id}` route. (Backend
has no separate typecheck — import is the gate.)

### Step 004 — frozen interface (2026-09-15)

Three existing modules, one addition each. Everything declarative is written in
full; the two added bodies `raise NotImplementedError("026 step 004 — skeleton stub")`.

**`backend/app/models/schemas/memos.py`** — one added DTO, declarative.

- `backend/app/models/schemas/memos.py` — `class ReorderMemosRequest(BaseModel)` — new
  - `memo_ids: list[str]` — the **full** ordered id list of the caller's non-archived memos
  - **no ordinals and no partial-move shape**: positions are the server's to write (`1..N`), so "move memo X to position k" is not expressible on this wire
  - declared **between `UpdateMemoRequest` and `MemoResponse`** (requests before responses — the `schemas/chapters.py` layout)

**`backend/app/services/memos.py`** — one added enum member + one added entry point.

- `backend/app/services/memos.py` — `MemoErrorReason` gains a **third** member — changed (was exactly two)
  - `invalid_reorder_set = "invalid-reorder-set"` — deliberately **not** `not_found`: the caller is told their *set* is wrong, not that a resource is missing. The enum is now exactly `[not_a_member, not_found, invalid_reorder_set]`.
- `backend/app/services/memos.py` — `async def reorder_memos(access: authz.BookAccess, req: ReorderMemosRequest) -> MemoListResponse` — new
- `backend/app/services/memos.py` — module-level import list gains `ReorderMemosRequest` — changed (import only)

**`backend/app/routes/memos.py`** — one added handler + one added map entry.

- `backend/app/routes/memos.py` — `_MEMO_ERROR_STATUS` gains a **third** entry — changed (was exactly two)
  - `MemoErrorReason.invalid_reorder_set: status.HTTP_400_BAD_REQUEST` — **400, not 422**
- `backend/app/routes/memos.py` — `@router.put("/{book_id}/memos/order")` →
  `async def reorder_memos(payload: ReorderMemosRequest, access: authz.BookAccess = Depends(authz.book_access)) -> MemoListResponse` — new
- `backend/app/routes/memos.py` — module-level import list gains `ReorderMemosRequest` — changed (import only)

Frozen properties beyond the signatures:

- **Declaration order is frozen and load-bearing.** The `order` route is declared
  at step 003's insertion point — after `POST /{book_id}/memos`, **before**
  `PUT /{book_id}/memos/{memo_id}`, which remains the **last** route in the
  module. The insertion-point comment was replaced by a permanent
  ordering-is-load-bearing comment in `routes/chapters.py`'s convention. Verified
  live: `router.routes` is `GET /memos`, `POST /memos`, `PUT /memos/order`,
  `PUT /memos/{memo_id}`.
- **No `authz.require`, no `Capability`, no `_CAPABILITY_MATRIX` row** — the one
  deliberate difference from `services/chapters.py::reorder_chapters`, which is
  owner-only via `Capability.set_chapter_order`. Memo order is the author's own:
  membership (`_require_member`) plus `access.user_id` scoping is the whole rule
  (`004.context.md` → "The one difference from the chapters precedent").
- **No bulk `db/` writer was added.** `db/memos.py` is untouched by this step; the
  `1..N` rewrite loops the ordinary per-row `db.memos.update`, keeping the rule in
  the service (`004.context.md`).
- The entry point takes the **request DTO**, not a bare `list[str]` — the
  `reorder_chapters(access, request)` precedent and step 002's frozen convention
  that every memo entry point takes `(access, …DTO)`.
- `BookAccess` remains the first parameter and no user id or book id is a separate
  parameter; `book_state` and `collaboration_mode` stay unread (the archived-book
  carve-out holds for reorder too).
- The handler declares **no `book_id`** (the dependency consumes it), the response
  model is the **return annotation**, and `400` joins `403` / `404` / `200` as the
  only statuses this module produces.

- Caller-compile edits (out of Source-files scope): **None** in `backend/app/`. One
  *existing test* now fails on the widened enum — see `## Notes & Issues` → "Step
  004 skeleton"; the skeleton agent may not edit test files, so it was left alone.

Verification: `cd backend && .venv/Scripts/python -c "import app.main"` clean; the
live app's `app.openapi()["paths"]` carries `/api/books/{book_id}/memos/order`
(`put`, 200 → `MemoListResponse`, `book_id` as its only path parameter) as a path
**distinct from** `/api/books/{book_id}/memos/{memo_id}` (`put`), so the literal
segment is not captured as a memo id; `MemoErrorReason` reads
`['not-a-member', 'not-found', 'invalid-reorder-set']` and `_MEMO_ERROR_STATUS`
reads `{403, 404, 400}` respectively. (Backend has no separate typecheck — import
is the gate.) `tests/routes/test_memos.py` and `tests/services/test_memos.py`:
44 passed, 1 failed — the single hard-coded-enum spec noted below.

### Step 005 — frozen interface (2026-09-15)

Two existing modules, four additions each. Everything declarative is written in
full; all eight added bodies `raise NotImplementedError("026 step 005 — skeleton stub")`.
**No schema module is touched** — all four verbs take no body and return the
existing `MemoResponse`.

**`backend/app/services/memos.py`** — four added entry points, no other change.

- `backend/app/services/memos.py` — `async def activate_memo(access: authz.BookAccess, memo_id: str) -> MemoResponse` — new
- `backend/app/services/memos.py` — `async def deactivate_memo(access: authz.BookAccess, memo_id: str) -> MemoResponse` — new
- `backend/app/services/memos.py` — `async def archive_memo(access: authz.BookAccess, memo_id: str) -> MemoResponse` — new
- `backend/app/services/memos.py` — `async def restore_memo(access: authz.BookAccess, memo_id: str) -> MemoResponse` — new
- Declared in that order, **after** `reorder_memos` (last in the module). No import
  change, no new helper, no new exception type.

**`backend/app/routes/memos.py`** — four added handlers, no other change.

- `backend/app/routes/memos.py` — `@router.post("/{book_id}/memos/{memo_id}/activate")` →
  `async def activate_memo(memo_id: str, access: authz.BookAccess = Depends(authz.book_access)) -> MemoResponse` — new
- `backend/app/routes/memos.py` — `@router.post("/{book_id}/memos/{memo_id}/deactivate")` →
  `async def deactivate_memo(memo_id: str, access: authz.BookAccess = Depends(authz.book_access)) -> MemoResponse` — new
- `backend/app/routes/memos.py` — `@router.post("/{book_id}/memos/{memo_id}/archive")` →
  `async def archive_memo(memo_id: str, access: authz.BookAccess = Depends(authz.book_access)) -> MemoResponse` — new
- `backend/app/routes/memos.py` — `@router.post("/{book_id}/memos/{memo_id}/restore")` →
  `async def restore_memo(memo_id: str, access: authz.BookAccess = Depends(authz.book_access)) -> MemoResponse` — new
- No `status_code=` on any of the four — the default **200** is the contract.

Frozen properties beyond the signatures:

- **`MemoErrorReason` is UNCHANGED at exactly three members**
  (`not_a_member` / `not_found` / `invalid_reorder_set`), and `_MEMO_ERROR_STATUS`
  is UNCHANGED at exactly three entries (403 / 404 / 400). This step adds **no
  reason, no map entry and no status**: every refusal these four verbs can produce
  already exists. In particular there is **no `409`** — a verb applied to a memo
  already in the requested state is a **200 no-op** returning the row unchanged
  (`context.md` → "Planner-derived: repeat state calls are 200 no-ops"). This
  deliberately does **not** copy `POST /api/books/{book_id}/archive`'s 409.
- **No request body on any of the four.** Verified live: the OpenAPI operation for
  each carries no `requestBody`, its only parameters are the two path params
  (`memo_id` plus the `book_id` the dependency declares), and its 200 content is
  `$ref: MemoResponse`.
- **`memo_id` is the wire `str`, passed through unparsed** — the route does not
  `int()` it, so a non-numeric id is the service's `not_found` → 404, never
  FastAPI's 422. Frozen from step 003.
- **The four service entry points take `(access, memo_id)` and nothing else** — no
  user id, no book id, no DTO, no flag argument. A flag parameter would make one
  function write both axes and re-open the enum-vs-two-booleans decision; the
  four-verb shape is the contract (`SubAgent`'s `disable` / `enable` precedent).
- **Every one resolves through the existing module-private `_resolve_memo`**, so
  the single `404`-shaped refusal (unknown / non-numeric / another author's /
  another book's) covers all four identically — US-124.AC-1 stays structural. No
  second resolver was added.
- **Restore reuses step 002's `_next_ordinal`** — the single append rule. No second
  next-ordinal computation exists anywhere.
- **No `DELETE` route, at any path**, and no delete function in `db/memos.py`.
  Verified live: no `/memos` path in the OpenAPI document carries a `delete`
  operation.
- **`book_state` and `collaboration_mode` stay unread** in the service — the
  archived-book carve-out holds for all four verbs.
- **Declaration order.** The four are declared **after** `PUT …/memos/order` and
  **immediately above** `PUT …/memos/{memo_id}`, which remains the **last** route in
  the module (step 004's frozen ordering property is preserved). Their extra path
  segment means they cannot collide with it either way.
- **`db/memos.py` is untouched** by this step: the flag writes go through the
  existing per-row `db.memos.update`.

Module-docstring corrections made with this step's additions (all three were false
statements, not scope creep):

- `backend/app/services/memos.py` — the skeleton marker said `reorder_memos` is
  UNIMPLEMENTED; it is implemented. Now names steps 002/004 as implemented and this
  step's four entry points as the unimplemented ones.
- `backend/app/routes/memos.py` — same correction for step 004's `reorder_memos`
  handler.
- `backend/app/routes/memos.py` — "**Only two statuses are this module's to
  produce**" followed by three (403 / 404 / 400) → "three", and the matching "the
  service's two typed reasons" → "three". The substantive rules those docstrings
  record (the archived-book carve-out, the no-capability rule, the append rule, the
  ordering rule, the one-refusal rule) are untouched.

- Caller-compile edits (out of Source-files scope): **None.** This step is purely
  additive — no existing signature changed, so no call site moved, and no
  previously-green test went red.

Verification: `cd backend && .venv/Scripts/python -c "import app.main"` clean. The
live app's `app.openapi()["paths"]` carries all four new verb paths as distinct
entries — `/api/books/{book_id}/memos/{memo_id}/activate`, `/deactivate`,
`/archive`, `/restore`, each `post` → 200 `MemoResponse`, each with no
`requestBody` — alongside `/api/books/{book_id}/memos` (`get`, `post`),
`/api/books/{book_id}/memos/order` (`put`) and `/api/books/{book_id}/memos/{memo_id}`
(`put`), which still resolve distinctly; no `/memos` path has a `delete`.
`MemoErrorReason` still reads `['not-a-member', 'not-found', 'invalid-reorder-set']`
and `_MEMO_ERROR_STATUS` still reads `{403, 404, 400}`. (Backend has no separate
typecheck — import is the gate.) The five existing memo suites
(`tests/db/test_memos.py`, `tests/services/test_memos.py`,
`tests/services/test_memos_order.py`, `tests/routes/test_memos.py`,
`tests/routes/test_memos_order.py`): **86 passed**, 0 failed.

## Tests

### Step 001 — tests (2026-09-15)

- `backend/tests/db/test_memos.py` — covers DoD-1..DoD-11 — many memos per `(book, author)` asserted
  at the database level (two/three successful inserts, no constraint to violate); create defaults
  (`active` true / `archived` false) and full column round trip through `create` → `get_by_id`;
  `body = ""` stored and returned as `""`; `list_for_author` scoped strictly to the requested
  `(book_id, user_id)` pair in both directions; the include-archived flag off by default and on by
  request; inactive rows listed exactly like active ones; ascending `ordinal` order including across
  gaps; `update` persisting a changed body, returning stored state and setting **no** timestamps of
  its own; the two flags persisted independently across deactivate / archive / restore / activate
  and all four combinations storable; and the structural absence of any delete function (public
  callables defined in the module are exactly `create`, `get_by_id`, `list_for_author`, `update`).
- `backend/tests/test_data_domain_memos.py` — covers DoD-12, DoD-13, DoD-14 — codec round trip over
  the frozen key set with ids emitted as strings and legacy numeric ids still parsing, the
  falsy-but-legal `""` / `False` / `False` values surviving as themselves, null timestamps
  round-tripping as null; exactly one `memos` entry in `TABLE_REGISTRY` immediately after
  `chapter_author_prompts` and immediately before `chapters`, bound to `Memo` + the codec pair; the
  `memos` table present and queryable on a freshly initialised database with an all-`ok` consistency
  report.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓,
  DoD-10 ✓, DoD-11 ✓, DoD-12 ✓, DoD-13 ✓, DoD-14 ✓ (no `[manual/live]` items in this step).

#### Re-bind of the eight registry-order specs (the `## Notes & Issues` gap below)

One line inserted per file — `    "memos",` between `"chapter_author_prompts",` and `"chapters",` in
the hard-coded canonical label list; nothing else changed in any of them:
`backend/tests/test_data_domain_assistant_core.py`, `…_assistant_links.py`, `…_book.py`,
`…_chapter.py`, `…_chapter_changes.py`, `…_chat.py` (`FULL_CANONICAL_ORDER`), `…_codex.py`,
`…_continuity.py`.

### Step 002 — tests (2026-09-15)

- `backend/tests/services/test_memos.py` — covers DoD-1..DoD-11 — one spec module, bound to the
  step-002 frozen skeleton (`MemoErrorReason` / `MemoError` / `_require_member` / `list_memos` /
  `create_memo` / `update_memo_body` and the four DTOs), using the `db` fixture with local
  `_seed_user` / `_seed_book` / `_seed_memo` / `_access` helpers and a directly constructed
  `BookAccess` (no HTTP at this layer). What it asserts, by item:
  - **DoD-1** — first memo is ordinal 1 and later ones append (1, 2, 3); the append rule computed
    over the caller's **non-archived** memos (live 1, 2 plus an archived 3 gives the next memo
    ordinal **3**, not 4); the ordinal scoped per `(book, author)` so another author's ordinal 9 in
    the same book and the caller's ordinal 7 in another book both leave the next at 1; an
    all-archived list giving 1.
  - **DoD-2** — a created memo is `active` / not `archived` on both the DTO and the stored row, with
    both timestamps stamped.
  - **DoD-3** — `body = ""` creates, stores and lists as `""`; `CreateMemoRequest(body="")`
    constructs; the body update may also clear to `""`.
  - **DoD-4** — both directions: a co-author sees none of the owner's memos, and the book's **owner**
    sees none of a co-author's two memos (US-124.AC-2); plus list scoping to `access.book_id`.
  - **DoD-5** — archived excluded by default, included with the flag (and flagged `archived` in the
    DTO); an **inactive** memo listed exactly like an active one (the two axes are independent).
  - **DoD-6** — rows stored 3/1/2 come back 1, 2, 3; ordinal order holds across an archive gap, both
    live-only (1, 4, 7) and archive-inclusive (1, 2, 4, 7).
  - **DoD-7** — body update writes the body, stamps `modified_at` past a fixed past anchor, leaves
    `created_at`, `ordinal` (7), `active` (False) and `archived` untouched on DTO and row; a second
    test shows an archived memo stays archived; `UpdateMemoRequest` has exactly `{"body"}`.
  - **DoD-8** — all four sources (non-numeric id, unknown id, another author's memo, another book's
    memo) collected in one loop: each `not_found`, and the set of
    `(type, reason, message)` fingerprints has length **1** — sameness, not merely "each raises";
    neither foreign row is written; a matching positive case shows the resolver admits the caller's
    own memo.
  - **DoD-9** — `reader` and `none` refused with `not_a_member` on **all three** entry points (with
    nothing created and the owner's memo untouched); `_require_member` called directly raises for
    both roles and admits owner and co-author; `list(MemoErrorReason)` is exactly
    `[not_a_member, not_found]`; a co-author is admitted on all three entry points.
  - **DoD-10** — `MemoResponse.model_fields` is exactly the eight wire fields with no `user_id` and
    no `user`-named field; on real create / update / list responses every `id` and `book_id` is a
    `str` and `user_id` is absent.
  - **DoD-11** — create **and** body-update both succeed with `book_state=BookState.archived` (the
    carve-out), and the list answers there too.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓,
  DoD-10 ✓, DoD-11 ✓ (no `[manual/live]` items in this step).

### Step 003 — tests (2026-09-15)

- `backend/tests/routes/test_memos.py` — covers DoD-1..DoD-13 — one spec module driving the real
  `app.main.app` in-process through the `http_client` fixture (httpx `ASGITransport`, no network),
  with local `_seed_user` / `_seed_author` / `_seed_book` / `_seed_public_book` / `_add_co_author` /
  `_seed_memo` / `_auth_header` helpers copied from `tests/routes/test_book_author_prompts.py`; auth
  is real (seeded user row + minted JWT). Bound to the step-003 frozen skeleton: `GET`/`POST`
  `/api/books/{book_id}/memos` and `PUT /api/books/{book_id}/memos/{memo_id}`, envelope key `items`,
  string ids, no `user_id`. What it asserts, by item:
  - **DoD-1** — both directions: a co-author sees only their own memo, and the book's **owner** sees
    none of the co-author's (US-124.AC-2).
  - **DoD-2** — no query parameter at all omits the archived memo while still listing an
    inactive-but-live one (the two axes are independent).
  - **DoD-3** — `include_archived=true` returns the archived row flagged `archived`, and an explicit
    `false` behaves like omitting it.
  - **DoD-4** — rows stored with ordinals 7 / 1 / 4 come back 1, 4, 7 — ordinal order across an
    archive gap.
  - **DoD-5** — `POST` answers **201** with string `id` / `book_id` and no `user_id`, and the created
    memo is **last** in the following list.
  - **DoD-6** — the created memo is `active` and not `archived`, on the 201 response and on read-back.
  - **DoD-7** — `POST {"body": ""}` is asserted **not 422** and **201**, with `""` stored and listed.
  - **DoD-8** — `PUT` answers 200 with the new body while `id`, `book_id`, `ordinal` (7), `active`
    (False), `archived` and `created_at` are unchanged (only `modified_at` may move).
  - **DoD-9** — all four unreachable ids (another author's memo, a memo of another book, an id
    belonging to nobody, a non-numeric id) in one loop: each **404**, and the set of JSON-normalised
    response bodies has length **1** — sameness, not merely "each is a 404"; neither foreign row was
    written.
  - **DoD-10** — three separate tests, three separate fixtures: no `Authorization` header → **401**
    on all three routes; a logged-in stranger to a **private** book → **404** from the dependency on
    all three; a logged-in reader on a **public** book → **403** on all three, with the owner's memo
    untouched.
  - **DoD-11** — the book's state is set to `archived` via `books.update` after seeding, then `POST`
    answers **201** and `PUT` answers **200** — the carve-out's route-level proof.
  - **DoD-12** — `DELETE` on both paths answers **405** and the memo survives.
  - **DoD-13** — path resolution read from `app.openapi()["paths"]` (the top-level `app.routes` list
    keeps included routers wrapped): the collection path carries `get` + `post`, the item path
    carries `put`, and neither carries `delete`.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓,
  DoD-10 ✓, DoD-11 ✓, DoD-12 ✓, DoD-13 ✓ (no `[manual/live]` items in this step).

### Step 004 — tests (2026-09-15)

- `backend/tests/services/test_memos_order.py` — covers DoD-1, DoD-2, DoD-3, DoD-4, DoD-5, DoD-8 —
  the service half, bound to the step-004 frozen skeleton (`ReorderMemosRequest(memo_ids: list[str])`,
  `MemoErrorReason.invalid_reorder_set`, `reorder_memos(access, req) -> MemoListResponse`), using the
  `db` fixture with local `_seed_user` / `_seed_book` / `_seed_memo` / `_access` helpers copied from
  `tests/services/test_memos.py` and a directly constructed `BookAccess` (no HTTP at this layer).
  Archived rows are seeded by writing the flag through `db/memos.py` — step 005's routes do not exist.
  By item:
  - **DoD-1** — a three-memo list submitted as C/A/B lands ordinals 1/2/3 on both the returned
    envelope and the stored rows; a four-memo full reversal lands 1..4.
  - **DoD-2** — `list_memos` after a reorder returns exactly the submitted sequence.
  - **DoD-3** — four separate refusals, one test each (too short, too long, a duplicated id, an id
    outside the caller's non-archived set): each raises `invalid_reorder_set`, and after each the
    stored ordinals are still 1/2/3 with `modified_at` still at the seeded past anchor — nothing
    written. A fifth test pins the reason as *not* `not_found`.
  - **DoD-4** — another author's id, another book's id and an id belonging to nobody collected in one
    loop: each `invalid_reorder_set`, and the set of `(type, reason, message)` fingerprints has length
    **1** — no existence oracle; plus a "too long" probe leaving the foreign row's ordinal and
    timestamp untouched.
  - **DoD-5** — both halves: an archived id inside the submitted list is refused; a successful reorder
    of the survivors renumbers only them while the archived row keeps its ordinal (the gap is not
    reclaimed) and stays archived; a third test shows the valid set is the live memos alone.
  - **DoD-8** — a reorder succeeds with `book_state=BookState.archived`.
- `backend/tests/routes/test_memos_order.py` — covers DoD-1..DoD-8 (route half) — one spec module
  driving the real `app.main.app` in-process through `http_client`, with local `_seed_user` /
  `_seed_author` / `_seed_book` / `_seed_public_book` / `_add_co_author` / `_seed_memo` /
  `_auth_header` helpers and a real JWT. By item:
  - **DoD-1** — `PUT …/memos/order` answers **200** with the `items` envelope, ordinals 1..N in the
    submitted order, string ids and no `user_id`; the stored rows confirm the rewrite.
  - **DoD-2** — the plain `GET` after the reorder returns the submitted order.
  - **DoD-3** — all four invalid sets in one loop, each **400**, and after each refusal both the
    stored ordinals and the author's listed order are unchanged.
  - **DoD-4** — a co-author's memo id, another book's memo id and a nobody id each **400** with
    JSON-normalised response bodies collapsing to a set of length **1**; the foreign rows unwritten.
  - **DoD-5** — the archived id in the list is 400; the survivors-only reorder is 200 and leaves the
    archived ordinal at 2 beside the new live 2.
  - **DoD-6** — a well-formed reorder body succeeds while the same path carrying the *body-update*
    shape is a **422** and explicitly neither 404 nor 200 (had `/{memo_id}` captured it, `{"body": …}`
    would have been a valid update of a memo named `order`); a real memo id on `/{memo_id}` still
    answers 200 with the new body; and `app.openapi()["paths"]` carries `…/memos/order` as a path
    distinct from `…/memos/{memo_id}`.
  - **DoD-7** — three fixtures: no `Authorization` header → **401**; a stranger to a **private** book
    → **404**; a logged-in non-member of a **public** book → **403**, with nothing written in either
    refusal.
  - **DoD-8** — the book's state set to `archived` via `books.update`, then the reorder answers 200.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓ (no
  `[manual/live]` items in this step).

#### Repair (2026-09-15) — Fault TEST, `backend/tests/services/test_memos_order.py`

The two DoD-3 specs for the **too-short** and **duplicated-id** shapes expressed the
"nothing is written" half as `all((await _stored(row.id)).modified_at == ANCHOR for row in …)`.
An `await` inside a generator expression makes it an *async* generator, so `all()` raised
`TypeError: 'async_generator' object is not iterable` inside the test body — the clause could
never evaluate, for any implementation. It was masked at the red gate because the stub's
`NotImplementedError` fired first. Both are now three explicit per-row awaits
(`assert (await _stored(first.id)).modified_at == ANCHOR`, and likewise for `second`/`third`),
the idiom already used successfully in the DoD-5 archived-ordinal spec. The clause is unchanged
in strength — same three rows, same anchor comparison — only made executable. No other file
touched.

#### Re-bind of the step-002 enum spec (the `## Notes & Issues` gap below)

One line added — `MemoErrorReason.invalid_reorder_set,` to the expected list in
`backend/tests/services/test_memos.py::test_service_reasons_are_membership_and_one_not_found__DoD9`.
Nothing else in that file changed; the test name is deliberately left alone so step 002's DoD-9 tag
stays intact.

### Step 005 — tests (2026-09-15)

- `backend/tests/services/test_memos_state.py` — covers DoD-1..DoD-12 except DoD-11's 405 half —
  the service half, bound to the step-005 frozen skeleton (`activate_memo` / `deactivate_memo` /
  `archive_memo` / `restore_memo`, each `(access, memo_id: str) -> MemoResponse`), using the `db`
  fixture with local `_seed_user` / `_seed_book` / `_seed_memo` / `_access` / `_stored` helpers
  copied from `tests/services/test_memos_order.py` and a directly constructed `BookAccess`. A
  module-level `VERBS` tuple drives the cross-verb specs. By item:
  - **DoD-1** — a deactivated memo is still returned by the ordinary (non-archived) `list_memos`,
    in place alongside its sibling.
  - **DoD-2** — deactivate writes `active` False on the DTO and the row while `archived`, `ordinal`
    (7) and `body` are untouched, `created_at` stays at the anchor and `modified_at` is stamped
    past it; a second spec shows the flag on the ordinary read.
  - **DoD-3** — activate writes `active` True with `archived` / `ordinal` (4) / `body` untouched
    and `modified_at` stamped; a second spec shows activate does **not** reach the archive axis
    (an archived memo switched on is still archived).
  - **DoD-4** — deactivating the caller's only active memo succeeds and leaves the memo listed with
    nothing active; a second spec deactivates the last *active* of two.
  - **DoD-5** — the archived memo is absent from the default list and present, flagged `archived`,
    in the include-archived list; plus archive writing `archived` and stamping `modified_at` with
    `body` intact.
  - **DoD-6** — three memos 1/2/3, the **middle** archived then restored: ordinal **4**, explicitly
    `!= 2`, so old-slot and append-last give different answers; survivors still 1 and 3 and the
    restored memo last in the list. Two more: the max is taken over **non-archived** memos only
    (live 1 and 5 beside a still-archived 9 gives **6**), and a restore into an empty working list
    gives **1**.
  - **DoD-7** — archiving the middle of three renumbers nothing (stored 1 / 2 / 3, each materialized
    with its own explicit `await`), the archived row keeps ordinal 2, and the working list reads
    `[1, 3]` with the gap visible; a second spec archives the **last** memo with the same result.
  - **DoD-8** — the four-memo case: one memo archived while ON and one while OFF, both restored,
    each returning with the flag it went in with (asserted on the archive response too, not only
    after restore), plus two bystanders whose flags never move; a second spec shows restore does not
    switch a memo back on.
  - **DoD-9** — all four verbs × four unreachable ids (non-numeric, unknown, another author's,
    another book's) in one loop: each raises `not_found`, and the set of
    `(type, reason, message)` fingerprints has length **1** — sameness across all sixteen; neither
    foreign row was written (`modified_at` still at the anchor). Plus a positive counterpart (each
    verb admits the caller's own memo) and a spec pinning `MemoErrorReason` at exactly the same
    three members step 004 left it at — this step adds none.
  - **DoD-10** — four per-verb no-op specs (activate on active, deactivate on inactive, archive on
    archived — each returning the row with `active` / `archived` / `ordinal` / `body` / `created_at`
    unchanged) plus a fifth showing every verb repeated twice never raises. The fourth, restore on a
    **non-archived** memo, is now a full no-op spec — `ordinal` included; see the note below.
  - **DoD-11** (service half) — after each of the four verbs in turn the memo is still the sole
    entry of the include-archived read and still stored: nothing removes a memo.
  - **DoD-12** — all four verbs succeed with `book_state=BookState.archived`.
- `backend/tests/routes/test_memos_state.py` — covers DoD-1..DoD-6, DoD-9, DoD-10, DoD-11, DoD-12 —
  the route half, driving the real `app.main.app` in-process through `http_client` (httpx
  `ASGITransport`, no network) with local `_seed_user` / `_seed_author` / `_seed_book` /
  `_seed_private_book` / `_add_co_author` / `_seed_memo` / `_auth_header` helpers and a real JWT.
  All four verbs are called with **no request body**. By item:
  - **DoD-1** — `POST …/deactivate` is 200 and the plain `GET` still lists the memo.
  - **DoD-2** — the 200 body is a `MemoResponse` with `active` false, string `id` / `book_id` and
    **no `user_id`**, `ordinal` 7 / `archived` / `body` unchanged; the following `GET` and the
    stored row agree.
  - **DoD-3** — `POST …/activate` on an inactive memo is 200 with `active` true and `archived` /
    `ordinal` / `body` unchanged.
  - **DoD-4** — deactivating the only active memo answers **200**, and the memo stays listed with
    `active` false.
  - **DoD-5** — after `POST …/archive` the memo is absent from the default `GET` and present,
    flagged `archived`, under `?include_archived=true`.
  - **DoD-6** — the same middle-of-three construction: archive then restore answers 200 with ordinal
    **4** (explicitly `!= 2`), and the `GET` reads ordinals `[1, 3, 4]` with the restored memo last.
  - **DoD-9** — four verbs × four unreachable ids: each **404** (a non-numeric id included — never a
    422), and the set of JSON-normalised response bodies has length **1**; neither foreign row was
    written.
  - **DoD-10** — four per-verb no-op specs, each asserting `200` and explicitly `!= 409` with the
    row unchanged (the restore-on-a-live-memo one now including `ordinal`), plus a fifth calling
    every verb twice and requiring 200 both times.
  - **DoD-11** — `DELETE` answers **405** on all six memo paths (collection, item and each of the
    four verb paths) with the memo surviving; no verb removes the memo from the include-archived
    read; and `app.openapi()["paths"]` carries no `delete` on any `/memos` path while all four verb
    paths exist as `post`.
  - **DoD-12** — the book's state set to `archived` via `books.update`, then all four verbs answer
    200 in sequence.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓ (service), DoD-8 ✓
  (service), DoD-9 ✓, DoD-10 ✓, DoD-11 ✓, DoD-12 ✓ (no `[manual/live]` items in this step).

#### Closed — the restore-on-a-live-memo ordinal (DoD-10) is now asserted (2026-09-15)

The previously-flagged non-assertion is **closed**. DoD-10 says a verb applied to a memo already in
that state returns "the row unchanged"; the restore contract says restore writes `ordinal = max + 1`.
The two readings collided only for **restore on a non-archived memo**. Resolution (orchestrator's
reading, reviewed by the red-gate verifier): that case is a **full no-op, `ordinal` included** —
DoD-10 carries no carve-out for restore, and the alternative would let an idempotent-looking verb
silently relocate a live memo in the author's list. DoD-6 continues to govern restore of a genuinely
archived memo (append last, `max + 1`).

Both DoD-10 restore specs were extended accordingly and renamed:
- `tests/services/test_memos_state.py::test_restore_on_a_live_memo_is_a_full_no_op__DoD10`
- `tests/routes/test_memos_state.py::test_restore_on_a_live_memo_answers_200_unchanged__DoD10`

Each now seeds **three** live memos at ordinals 1 / 2 / 3 and restores the **middle** one, so
"unchanged" (2) and "appended last" (4) give different answers and the assertion is meaningful; the
two bystanders are checked to still read 1 and 3 (each materialized with its own explicit `await`)
and the list still reads `[1, 2, 3]` in the original order. No prior assertion was removed or
weakened.

## Notes & Issues

### Step 005 — the idempotent no-op writes nothing

The planner left it open whether a repeat state call re-stamps `modified_at`. All four verbs
take the strict reading of DoD-10 ("the row unchanged") and return early without any write, so a
no-op leaves `modified_at` — and, for restore, `ordinal` — exactly as it was. Consistent across the
four.

### Step 004 skeleton — one step-002 spec hard-codes the two-member `MemoErrorReason`

Not an interface problem; a blast-radius gap, and the same shape as the step-001
note above. The step file mandates a **third** `MemoErrorReason` member
(`invalid_reorder_set`), and step 002's own frozen record anticipated it
("step 004 adds the third member") — but
`backend/tests/services/test_memos.py::test_service_reasons_are_membership_and_one_not_found__DoD9`
asserts the enum is **exactly** `[not_a_member, not_found]`, so widening it turns
that one previously-green test red:

| File | Test | Assertion |
|---|---|---|
| `backend/tests/services/test_memos.py` | `test_service_reasons_are_membership_and_one_not_found__DoD9` | `list(MemoErrorReason) == [not_a_member, not_found]` |

Nothing else is affected: the other 44 specs in `tests/services/test_memos.py`
and `tests/routes/test_memos.py` still pass, since the new reason is raised only
by the (unimplemented) reorder path and the new route is reached by no existing
spec.

The repair is one line — add `MemoErrorReason.invalid_reorder_set,` to that
expected list. The skeleton agent may not edit test files and this file is **not**
in step 004's Test files list, so the edit was **not** made. Whoever owns it next
(test-coder, if step 004's Test files list is widened to include it, or the
orchestrator) must apply it, or step 004's verify run will report one
pre-existing-test failure that is not the coder's fault. The alternative —
narrowing the enum back to two members — is not viable: the third reason is
mandated by the step file and by `context.md` → "The wire contract" (a reorder
list that is not exactly the caller's non-archived set is a `400`, which cannot
be carried by `not_found`).

### Step 001 skeleton — eight existing `test_data_domain_*.py` modules hard-code the registry label list

Not an interface problem; a blast-radius gap the plan does not name. Adding the
`memos` tuple to `TABLE_REGISTRY` (mandated by the step file and by
`docs/architecture/backend/book-domain.md`) makes **eight already-passing
registry-order tests fail**, because each of these modules defines its own
literal copy of the canonical label list:

| File | Symbol | Failing test |
|---|---|---|
| `backend/tests/test_data_domain_assistant_core.py` | `CANONICAL_ORDER` | `test_table_registry_order__DoD5` |
| `backend/tests/test_data_domain_assistant_links.py` | `CANONICAL_ORDER` | `test_table_registry_order__DoD6` |
| `backend/tests/test_data_domain_book.py` | `CANONICAL_ORDER` | `test_table_registry_order__DoD5` |
| `backend/tests/test_data_domain_chapter.py` | `CANONICAL_ORDER` | `test_table_registry_order__DoD3` |
| `backend/tests/test_data_domain_chapter_changes.py` | `CANONICAL_ORDER` | `test_table_registry_order__DoD4` |
| `backend/tests/test_data_domain_chat.py` | `FULL_CANONICAL_ORDER` | `test_full_table_registry_equals_canonical_order__DoD4` |
| `backend/tests/test_data_domain_codex.py` | `CANONICAL_ORDER` | `test_table_registry_order__DoD4` |
| `backend/tests/test_data_domain_continuity.py` | `CANONICAL_ORDER` | `test_table_registry_order__DoD5` |

The repair is one line per file — insert `    "memos",` between
`"chapter_author_prompts",` and `"chapters",` in that literal list. Nothing else
in those modules is affected (all other import/export tests still pass: export
and import iterate the registry per-row, so the unimplemented `_memo_to_dict` /
`_dict_to_memo` are never reached while no `memos` rows exist).

The skeleton agent may not edit test files, and these eight are **not** in step
001's Test files list, so the edits were **not** made. Whoever owns them next
(test-coder, given the step's Test files list is widened, or the orchestrator)
must apply the eight inserts, or the step-001 verify run will report eight
pre-existing-test failures that are not the coder's fault. Suggested resolution:
add the eight paths to step 001's Test files list; the alternative — leaving them
red — is not viable because the registry position is architecturally fixed and
cannot be changed to satisfy them.
