# Feature 021 — per-author-system-prompt

| Step | File                            | Status  | Verifier | Date |
|------|---------------------------------|---------|----------|------|
| 001  | `001.author-prompt-table.md`    | done    | PASS     | 2026-07-29 |
| 002  | `002.author-prompt-service.md`  | done    | PASS     | 2026-07-29 |
| 003  | `003.author-prompt-routes.md`   | done    | PASS     | 2026-07-29 |
| 004  | `004.composition-switch.md`     | done    | PASS     | 2026-07-29 |
| 005  | `005.settings-page-editor.md`   | done    | PASS     | 2026-07-29 |
| 006  | `006.book-state-editor.md`      | done    | PASS     | 2026-07-29 |

## Files Changed

### Step 001 — the `BookAuthorPrompt` table, its `db/` module, registration and JSONL codec

- `backend/app/models/book_author_prompt.py` — the `book_author_prompts` table (surrogate snowflake PK, unique `(book_id, user_id)`, required `system_prompt`); arrived complete from the skeleton, declarative only
- `backend/app/db/book_author_prompts.py` — session-free `create` / `get_by_book_and_user` / `update` bodies filled, `chapters.py` idiom
- `backend/app/db/engine.py` — MODEL-REGISTRATION SEAM carries `app.models.book_author_prompt`; ADDITIVE MIGRATION SEAM still `pass`
- `backend/app/services/db_import_export.py` — `_book_author_prompt_to_dict` / `_dict_to_book_author_prompt` bodies filled; `TABLE_REGISTRY` entry sits at index 9, after `book_members`

### Step 002 — prompt DTOs and the per-author service

- `backend/app/models/schemas/book_author_prompts.py` — `UpdateBookAuthorPromptRequest` / `BookAuthorPromptResponse`; arrived complete from the skeleton (declarative DTOs), untouched by this pass
- `backend/app/services/book_author_prompts.py` — the four bodies filled: `_require_member` (role in `{owner, co_author}`, else `not_a_member`), `_to_prompt_response` (sole DTO construction site; `None` row → `""` + `None`), `get_prompt`, `upsert_prompt` (create stamps both timestamps, update stamps `modified_at` only); `datetime`/`timezone` import added

### Step 003 — the `/api/books/{book_id}/system-prompt` route pair

- `backend/app/routes/book_author_prompts.py` — the three bodies filled: `_map_prompt_error` (`HTTPException(status_code=_PROMPT_ERROR_STATUS[err.reason], detail=err.message)`, plain-string detail), `get_system_prompt` → `service.get_prompt(access)`, `update_system_prompt` → `service.upsert_prompt(access, payload)`; each handler wraps its one service call in a single `except BookAuthorPromptError` → `raise _map_prompt_error(err)`. No `404` branch, no `except authz.BookAuthorizationError`, no `_map_authz_error`, no imports added
- `backend/app/main.py` — no change needed: the import line and `app.include_router(book_author_prompts.router)` after `codex.router` arrived complete from the skeleton

### Step 004 — the composition switch (`BOOK` → `AUTHOR`)

- `backend/app/services/prompt_composition.py` — third layer's section label changed from `"BOOK"` to `"AUTHOR"` (the one behaviour item the skeleton left); rendering, `"\n\n"` join, None-or-whitespace skip rule, the other three pairs, the signature and the purity all untouched
- `backend/app/services/chat_turn.py` — `run_turn`'s author layer repointed onto the chat's own author: `await book_author_prompts.get_by_book_and_user(chat.book_id, chat.author_id)`, passing `row.system_prompt` when a row exists and `None` when it does not (no blank special-case); `books.get_by_id` call dropped and the import line became `from app.db import book_author_prompts, chat_messages`. `chapter=` still not passed; nothing else in the file changed
- `backend/app/models/book.py` — no change needed: the `Book.system_prompt` "superseded and dormant" docstring arrived complete from the skeleton; the column keeps its type and required-ness
- `backend/app/models/schemas/books.py` — no change needed: all three omission docstrings (`BookResponse`, `BookDetailResponse`, `ReaderBookResponse`) arrived complete from the skeleton, revised in place with the per-author/own-endpoint reason, none deleted and no field added to any DTO

### Step 005 — frontend DTOs, api functions and the book-settings prompt editor

- `frontend/src/types/books.d.ts` — no change needed: `BookAuthorPromptResponse` / `UpdateBookAuthorPromptRequest` and the revised `BookDetailResponse` omission docstring (per-author, own endpoint) arrived complete from the skeleton; no `system_prompt` field added to any book DTO
- `frontend/src/api/books.ts` — the two bodies filled: both call `request<BookAuthorPromptResponse>` against the `${BASE}/${bookId}/system-prompt` template literal — `getOwnSystemPrompt` with `{ signal }` (default GET), `updateOwnSystemPrompt` with `{ method: "PUT", body, signal }`; no import added
- `frontend/src/user/pages/bookSettingsPageState.ts` — additive only: `systemPromptDirty` (draft vs `systemPrompt?.system_prompt ?? ""`), `canSaveSystemPrompt` (status `ready` AND submit not `loading` AND dirty), `loadSystemPrompt` (seeds `systemPrompt` + draft, `ApiError` → trio error), `saveSystemPrompt` (re-seeds both from the PUT response body, `ApiError` → `systemPromptServerErrors` 4xx `system_prompt` / 5xx `form`, draft untouched); `UpdateBookAuthorPromptRequest` added to the type import. The `detail` trio and its six effects are byte-unchanged
- `frontend/src/user/components/books/SystemPromptCard.tsx` — the JSX written: loading branch, error branch with a `Retry` button and no editor, otherwise a `form`-keyed `Alert`, an autosize `Textarea` bound to `systemPromptDraft` (field error from the `system_prompt` key), and a `Save` button gated on `canSaveSystemPrompt`; plus the per-author copy line. Two inner handlers, no hooks, no delete control
- `frontend/src/user/pages/BookSettingsPage.tsx` — no change needed: the extra `void loadSystemPrompt(...)` line in the existing mount effect and the `<SystemPromptCard …/>` in the render tree arrived complete from the skeleton

### Step 006 — the working page's Book-state prompt editor

- `frontend/src/work/pages/bookStatePageState.ts` — additive only, the four bodies filled: `systemPromptDirty` (draft vs `systemPrompt?.system_prompt ?? ""`), `canSaveSystemPrompt` (status `ready` AND submit not `loading` AND dirty), `loadSystemPrompt` (seeds `systemPrompt` + draft, `ApiError` → trio error, `""` is a normal ready value), `saveSystemPrompt` (body read off the draft verbatim, re-seeds both from the PUT response body directly without re-running the loader, `ApiError` → `systemPromptServerErrors` 4xx `system_prompt` / 5xx `form` with the draft untouched); `UpdateBookAuthorPromptRequest` added to the existing type import. The `bookDetail` trio, its five computeds and `loadBookState` are byte-unchanged
- `frontend/src/work/pages/BookStatePage.tsx` — the "Your system prompt" section's JSX written: the always-visible per-author copy line, the trio's loading branch, its own error branch (an `Alert`, so a prompt failure leaves every other section rendering as before), and otherwise a `form`-keyed `Alert`, an autosize `Textarea` bound to `systemPromptDraft` (field error from the `system_prompt` key) and a `Save` button gated on `canSaveSystemPrompt`. One inner `handleSavePrompt` handler; `Button` / `Textarea` and `saveSystemPrompt` added to the existing imports. The mount effect, its deps array and every read-only section above are unchanged

## Skeleton

### Step 001 — frozen interface (2026-07-29)

Model (declarative — a table is a type, not behavior; nothing left unimplemented):

- `backend/app/models/book_author_prompt.py` — `class BookAuthorPrompt(SQLModel, table=True)` — new
  - `__tablename__ = "book_author_prompts"`
  - `__table_args__ = (UniqueConstraint("book_id", "user_id", name="uq_book_author_prompt_book_id_user_id"),)`
  - `id: int = Field(default_factory=generate_id, primary_key=True)`
  - `book_id: int = Field(foreign_key="books.id")`
  - `user_id: int = Field(foreign_key="users.id")`
  - `system_prompt: str` — required, NOT NULL; `""` is a value, never coerced to `None`
  - `created_at: datetime | None = Field(default=None)`
  - `modified_at: datetime | None = Field(default=None)`

`db/` module (session-free, three functions only — bodies raise `NotImplementedError`):

- `backend/app/db/book_author_prompts.py` — `async def create(row: BookAuthorPrompt) -> BookAuthorPrompt` — new
- `backend/app/db/book_author_prompts.py` — `async def get_by_book_and_user(book_id: int, user_id: int) -> BookAuthorPrompt | None` — new
- `backend/app/db/book_author_prompts.py` — `async def update(row: BookAuthorPrompt) -> BookAuthorPrompt` — new

Registration:

- `backend/app/db/engine.py` — `_register_models()` gains `import app.models.book_author_prompt  # noqa: F401`, placed after `app.models.book_member` — changed (signature unchanged). ADDITIVE MIGRATION SEAM left `pass`, untouched.

JSONL codec (bodies raise `NotImplementedError`):

- `backend/app/services/db_import_export.py` — `def _book_author_prompt_to_dict(prompt: BookAuthorPrompt) -> dict[str, object]` — new
- `backend/app/services/db_import_export.py` — `def _dict_to_book_author_prompt(data: dict[str, object]) -> BookAuthorPrompt` — new
- `backend/app/services/db_import_export.py` — `TABLE_REGISTRY` gains `("book_author_prompts", BookAuthorPrompt, _book_author_prompt_to_dict, _dict_to_book_author_prompt)` at index 9, immediately after `book_members` and before `chapters` — changed
- `Book`'s codec untouched: `_book_to_dict` still emits `system_prompt` and `_dict_to_book` still reads it.

Exported dict keys frozen for the codec pair (`id`, `book_id`, `user_id` as `str`; ids parse string-or-legacy-number):
`{"id", "book_id", "user_id", "system_prompt", "created_at", "modified_at"}`.

- Caller-compile edits (out of Source-files scope): None.

### Step 002 — frozen interface (2026-07-29)

DTOs (declarative — field names / types / defaults are the contract; nothing left unimplemented):

- `backend/app/models/schemas/book_author_prompts.py` — `class UpdateBookAuthorPromptRequest(BaseModel)` — new
  - `system_prompt: str` — required, no default; `""` is valid input
- `backend/app/models/schemas/book_author_prompts.py` — `class BookAuthorPromptResponse(BaseModel)` — new
  - `book_id: str` — stringified snowflake
  - `system_prompt: str` — never nullable; `""` means "no prompt"
  - `modified_at: datetime | None` — `None` when the author has no row yet
  - **no `user_id` field** — and no other field a caller could vary

Service (typed-error shape from `services/chats.py`; all four function bodies raise `NotImplementedError`):

- `backend/app/services/book_author_prompts.py` — `class BookAuthorPromptErrorReason(str, enum.Enum)` — new
  - exactly one member: `not_a_member = "not-a-member"` (step 003 maps it to **403**)
- `backend/app/services/book_author_prompts.py` — `class BookAuthorPromptError(Exception)` — new
  - `def __init__(self, reason: BookAuthorPromptErrorReason, message: str = "") -> None` — sets `.reason` / `.message`
- `backend/app/services/book_author_prompts.py` — `def _require_member(access: authz.BookAccess) -> None` — new (private guard; `owner` / `co_author` pass, anything else raises `not_a_member`; no capability check, no matrix row, no collaboration-mode check)
- `backend/app/services/book_author_prompts.py` — `def _to_prompt_response(book_id: int, row: BookAuthorPrompt | None) -> BookAuthorPromptResponse` — new (the single DTO construction site; `row is None` → `""` + `None`)
- `backend/app/services/book_author_prompts.py` — `async def get_prompt(access: authz.BookAccess) -> BookAuthorPromptResponse` — new
- `backend/app/services/book_author_prompts.py` — `async def upsert_prompt(access: authz.BookAccess, req: UpdateBookAuthorPromptRequest) -> BookAuthorPromptResponse` — new

Structural notes that are part of the freeze:

- Neither entry point takes a user id: it comes only from `access.user_id`, so another author's prompt is unaddressable.
- Timestamp policy lives here (create stamps `created_at` + `modified_at`; update stamps `modified_at` only), matching step 001's timestamp-free `db/` layer.
- `backend/app/services/authz.py` is untouched — no `Capability` member, no `_CAPABILITY_MATRIX` row.

- Caller-compile edits (out of Source-files scope): None.

### Step 003 — frozen interface (2026-07-29)

Router object and module-level declarations (`routes/chats.py` / `routes/codex.py` idiom — the prefix
lives on the `APIRouter`, never on the decorators):

- `backend/app/routes/book_author_prompts.py` — `router = APIRouter(prefix="/api/books", tags=["book-author-prompts"])` — new
  - the tag follows the module-name-with-hyphens convention (`admin-llm-servers` ← `llm_servers`)
- `backend/app/routes/book_author_prompts.py` — `_PROMPT_ERROR_STATUS: dict[book_author_prompts_service.BookAuthorPromptErrorReason, int]` — new
  - **exactly one entry**: `not_a_member` → `status.HTTP_403_FORBIDDEN`. Declarative, and complete as frozen.
- `backend/app/routes/book_author_prompts.py` — `def _map_prompt_error(err: book_author_prompts_service.BookAuthorPromptError) -> HTTPException` — new (body raises `NotImplementedError`; returns `HTTPException(status_code=_PROMPT_ERROR_STATUS[err.reason], detail=err.message)` — plain-string detail, `chats.py` shape, **no** `TypedDict`)

Handlers (bodies raise `NotImplementedError`; response models are the **return annotation**, never
`response_model=`; `{book_id}` is consumed entirely by the dependency and re-declared by neither):

- `backend/app/routes/book_author_prompts.py` — `@router.get("/{book_id}/system-prompt")` · `async def get_system_prompt(access: authz.BookAccess = Depends(authz.book_access)) -> BookAuthorPromptResponse` — new
- `backend/app/routes/book_author_prompts.py` — `@router.put("/{book_id}/system-prompt")` · `async def update_system_prompt(payload: UpdateBookAuthorPromptRequest, access: authz.BookAccess = Depends(authz.book_access)) -> BookAuthorPromptResponse` — new
  - **no `status_code=` kwarg** — the PUT answers the FastAPI default **200** on both the create and the update path (`context.md` → decision 6). There is no `POST` and no `DELETE` on this path; a `DELETE` is refused by the framework as `405`.

Mount:

- `backend/app/main.py` — `from app.routes import book_author_prompts` (import block, before `books`) and `app.include_router(book_author_prompts.router)` immediately after `codex.router` — changed (no prefix at the call site; nothing else in the file changed).

Structural notes that are part of the freeze:

- The router has **no `_map_authz_error`** and **no `except authz.BookAuthorizationError`** branch: step 002 raises no capability error because this feature adds no `Capability` (`context.md` → decision 4). If one ever appears here, something upstream went wrong.
- The router has **no `404` branch**. Existence hiding is produced once, upstream, by `resolve_book_access` (`authorization.md` → "Failure modes"); `401` comes from the auth dependency behind `book_access`. Only `403` (the map) and `200` (the return annotations) are this module's to produce.
- Verified against the generated OpenAPI: `/api/books/{book_id}/system-prompt` exposes exactly `get` + `put`, both declaring `200` (plus FastAPI's `422`), with `BookAuthorPromptResponse` as the response model.

- Caller-compile edits (out of Source-files scope): None.

### Step 004 — frozen interface (2026-07-29)

The composer (the only signature change in this step):

- `backend/app/services/prompt_composition.py` — `def compose_system_prompt(base: str | None = None, mode: str | None = None, author: str | None = None, chapter: str | None = None) -> str` — changed (was `compose_system_prompt(base: str | None = None, mode: str | None = None, book: str | None = None, chapter: str | None = None) -> str`)
  - Positional order unchanged, so every positional call binds as before; **only the third keyword's name changed**. There is **no `book=` alias, no `**kwargs`, no deprecation shim** — `compose_system_prompt(book=...)` now raises `TypeError: compose_system_prompt() got an unexpected keyword argument 'book'` (verified; DoD-3).
  - `BASE_SYSTEM_PROMPT` untouched. Purity untouched — no I/O, no db, no clock.

What is deliberately **left unimplemented** (the coder's, per DoD):

- `backend/app/services/prompt_composition.py` — the third section **label** still renders `BOOK`. A rendered label is output, i.e. behaviour, not signature, so the skeleton did not change it; the body reads `("BOOK", author)` under an explicit `# Skeleton (021 step 004): UNIMPLEMENTED` comment. The coder changes the literal to `"AUTHOR"` (DoD-1). Nothing else in the body may move: the `### {label}\n{text.strip()}` rendering, the `"\n\n"` join, the None-or-whitespace skip and the other three pairs are frozen as-is.
- `backend/app/services/chat_turn.py` — `run_turn`'s call site now passes the frozen `author=` keyword but **still passes the retired book-wide value** (`book.system_prompt if book is not None else None`). That is the minimal mechanical edit that keeps the caller binding; repointing the value is the coder's (DoD-4, DoD-5, DoD-6).

Resolved for the coder — the two locals the plan left to the skeleton (`004.context.md` → "The single production call site"):

- `run_turn` binds `chat = context.chat` (a `Chat` row) at its top, so the pair is **`chat.book_id`** and **`chat.author_id`** — the same `author_id` `services/chats.py:_resolve_owned_chat` compares against `access.user_id`. `context.access.book_id` is the same book, but `access.user_id` is *not* interchangeable with `chat.author_id` at this layer: the chat row is the identity the turn belongs to, so read the row.
- The read is `await book_author_prompts.get_by_book_and_user(chat.book_id, chat.author_id)` (frozen in step 001: `-> BookAuthorPrompt | None`), imported namespace-style as `from app.db import book_author_prompts`. Pass `row.system_prompt` when there is a row and `None` when there is not — **no blank special-case**, the composer skips blank layers already.
- Consequence the coder owns: `book = await books.get_by_id(chat.book_id)` becomes the file's only remaining use of `books`, so both the call and `books` in the `from app.db import books, chat_messages` import line go. No other line in `chat_turn.py` changes; `chapter=` is still not passed.

Docstrings — revised and complete as frozen (declarative; DoD-8 is `[manual/live]`, nothing left to implement):

- `backend/app/models/book.py` — `Book.system_prompt` — **type and required-ness unchanged** (`system_prompt: str`, no `Field(default=...)`). Class-docstring bullet rewritten: superseded by `BookAuthorPrompt` and read by nothing; retained because `db/engine.py` offers only an additive seam (`create_all` never alters a table) and there is no Alembic, so no DROP COLUMN path exists; still written `""` at creation by `services/books.py` and still exported/imported by the JSONL codec.
- `backend/app/models/schemas/books.py` — all **three** omission docstrings revised in place, **none deleted, no field added to any DTO**: `BookResponse` (was "no `system_prompt` / `active_notes`"), `BookDetailResponse` (was "the book-wide prompt is FEAT-020 assistant-config territory (undesigned)"), `ReaderBookResponse` (was the UC-029 exclusion list alone). All three now give the new reason — the prompt is per-author and served by `GET`/`PUT /api/books/{book_id}/system-prompt`, so a book-shaped DTO cannot carry it honestly (two authors reading one book would need different bytes in the same field).

Structural notes that are part of the freeze:

- `backend/app/services/books.py` untouched — the `""` write at creation stays (`context.md` → decision 2). `AssistantMode.system_prompt` / the `MODE` layer untouched — FEAT-020's, not this feature's.
- No new module, class, function or constant was created by this step: the entire frozen surface is one renamed parameter.

Compile gate (root `CLAUDE.md` declares **no backend typecheck**, so the gate is import + smoke, `routes/book_author_prompts.py`'s step-003 precedent): all four Source files byte-compile, `import app.main` succeeds (so the one call site binds), `inspect.signature(compose_system_prompt)` reports the frozen signature, `compose_system_prompt(base=..., book=...)` raises `TypeError`, and the blank-skip rule still holds.

Expected red at the red gate (`.venv/Scripts/python -m pytest` → **11 failed, 774 passed**) — every failure is the old `book=` keyword in the two modules that are in **this step's Test files** list, and nothing else in the suite moved:

- `tests/services/test_prompt_composition.py` — 5 failures (`__DoD1`, four `__DoD2`).
- `tests/services/test_assistant_runtime.py` — 6 failures (`__DoD7_US110_AC3`, four `__DoD8_US110_AC4`, `__DoD13`).
- `tests/services/test_chat_turn.py` and `tests/routes/test_chats.py` are **green**, confirming the turn's existing behaviour was preserved rather than stubbed out.
- Red-gate profile to expect from the *new* tests: DoD-1 / DoD-4 / DoD-6 must be RED. **DoD-2, DoD-3, DoD-5 and DoD-7 will be GREEN against these stubs by construction** — DoD-2 and DoD-7 are preservation clauses, DoD-3 is the signature freeze itself, and DoD-5 (no row → no author layer) passes spuriously because the stale value is a book created with `system_prompt = ""`, which the skip rule already drops. None of those four is evidence the step is done.

- Caller-compile edits (out of Source-files scope): None — `chat_turn.py` is the sole caller and is itself a Source file.

### Step 005 — frozen interface (2026-07-29)

DTOs (declarative — wire-exact `snake_case`, ids `string`, no `any`; nothing left unimplemented). Both
are **shared with step 006 and consumed there unchanged**:

- `frontend/src/types/books.d.ts` — `export interface BookAuthorPromptResponse` — new
  - `book_id: string` — snowflake serialized as a string
  - `system_prompt: string` — never nullable; `""` = "this author has no prompt"
  - `modified_at: ISODateString | null` — `null` when no row exists yet
  - **no `user_id` field** — mirrors backend `BookAuthorPromptResponse` (step 002) 1:1
- `frontend/src/types/books.d.ts` — `export interface UpdateBookAuthorPromptRequest` — new
  - `system_prompt: string` — required; `""` is valid and clears the prompt (no DELETE verb)
- `frontend/src/types/books.d.ts` — `BookDetailResponse`'s omission docstring — changed (was
  "Deliberately omits `system_prompt` / `active_notes` (not rendered by the settings page)"). Revised
  in place, **not deleted, and no field added to any book DTO**: the prompt is per-author and served by
  its own endpoint, so a book-shaped DTO cannot carry it honestly — two authors reading one book would
  need different bytes in the same field. `active_notes` keeps its original reason. This is the fourth
  of the four omission docstrings; the other three were step 004's. **Complete as frozen** (a comment
  has no body to leave unimplemented). `BookResponse`'s own mention is deliberately untouched —
  `005.context.md` scopes this step to the lines 69-74 docstring only.

Api functions (`frontend/src/api/books.ts`, appended after `setVisibility`; both route through the
shared `request<T>`, both trail `signal?: AbortSignal`; bodies **throw** — the coder writes the
`request` call, so DoD-9 is genuinely red):

- `frontend/src/api/books.ts` — `export async function getOwnSystemPrompt(bookId: string, signal?: AbortSignal): Promise<BookAuthorPromptResponse>` — new
  - `GET` (the `request` default verb) against `` `${BASE}/${bookId}/system-prompt` ``, `BASE = "/api/books"`
- `frontend/src/api/books.ts` — `export async function updateOwnSystemPrompt(bookId: string, body: UpdateBookAuthorPromptRequest, signal?: AbortSignal): Promise<BookAuthorPromptResponse>` — new
  - `{ method: "PUT", body, signal }` against the same path; returns the **stored** prompt
- The names are `…OwnSystemPrompt`, not `…BookSystemPrompt`: the endpoint has no way to name a user, so
  both calls address **the caller's own** prompt by construction. Verb prefixes `get` / `update` follow
  `frontend.md` → "`api/<resource>.ts`".

Page state (`frontend/src/user/pages/bookSettingsPageState.ts`) — **purely additive**; the existing
`detail` trio and all six existing effect functions are byte-unchanged. New observable fields are
declared complete (a field declaration has no body); the two computeds and the two effects **throw**:

- `BookSettingsPageState.systemPrompt: BookAuthorPromptResponse | null = null` — new
- `BookSettingsPageState.systemPromptStatus: "idle" | "loading" | "ready" | "error" = "idle"` — new
- `BookSettingsPageState.systemPromptError: string | null = null` — new
  - the trio follows `frontend.md`'s `<name>` / `<name>Status` / `<name>Error` rule and the file's
    existing `detail*` naming; it is a **second, independent loadable** — a prompt failure never
    touches the `detail` trio and vice versa
- `BookSettingsPageState.systemPromptDraft = ""` (inferred `string`) — new — the textarea draft
- `BookSettingsPageState.systemPromptServerErrors: Record<string, string> = {}` — new — save refusals
  only, keyed `system_prompt` (4xx) / `form` (5xx), held separately from `systemPromptError`.
  **There is deliberately no `clientErrors` and no `errors` union** — this field has no client-side
  validation because every string, `""` included, is valid (`context.md` → decision 6). That is the
  first of the two departures from the `addCoAuthorDraft` precedent; the second is that the draft
  lives in the page state rather than in its own draft class, because the editor shares the page mount.
- `BookSettingsPageState.systemPromptSubmitStatus: "idle" | "loading" | "ready" | "error" = "idle"` — new
- `BookSettingsPageState.get systemPromptDirty(): boolean` — new (pure computed; draft vs
  `systemPrompt?.system_prompt`, a not-yet-loaded prompt compared as `""`)
- `BookSettingsPageState.get canSaveSystemPrompt(): boolean` — new (pure computed; dirty AND no save in
  flight AND the prompt has loaded)
- `frontend/src/user/pages/bookSettingsPageState.ts` — `export async function loadSystemPrompt(state: BookSettingsPageState, bookId: string, signal?: AbortSignal): Promise<void>` — new
- `frontend/src/user/pages/bookSettingsPageState.ts` — `export async function saveSystemPrompt(state: BookSettingsPageState, bookId: string, signal?: AbortSignal): Promise<void>` — new
  - **no body parameter**: the payload is `{ system_prompt: state.systemPromptDraft }`, read off the
    state, matching the file's `(state, bookId, …, signal?)` effect shape.
  - Frozen behavioural contract the coder must honour (recorded here because it is what distinguishes
    this effect from every other one in the file): on success it re-seeds `systemPrompt` **and**
    `systemPromptDraft` **from the PUT response body directly**, and does **not** re-run
    `loadSystemPrompt` — a second round trip would open a window showing neither the draft nor the
    stored value. On `ApiError` it leaves `systemPromptDraft` untouched, so a refusal loses nothing the
    author typed.

Component (`frontend/src/user/components/books/SystemPromptCard.tsx`, new file — props frozen, body
throws):

- `frontend/src/user/components/books/SystemPromptCard.tsx` — `export interface SystemPromptCardProps { state: BookSettingsPageState; bookId: string }` — new
- `frontend/src/user/components/books/SystemPromptCard.tsx` — `export const SystemPromptCard = observer(function SystemPromptCard({ state, bookId }: SystemPromptCardProps) { … })` — new
  - `bookId` is a prop because the page owns the route param and both effect functions are keyed by it;
    the state class carries no book id. Handlers are inner functions closing over `state` / `bookId`
    (`frontend.md` → "Components"); **no hooks of any kind in this component**, no extracted callbacks.
  - **Not shared with step 006** — `BookStatePage` gets its own state additions and its own rendering
    (`005.context.md`); only the DTOs and the two api functions cross.

Page wiring (`frontend/src/user/pages/BookSettingsPage.tsx`) — declarative composition, so it arrives
**complete**, matching the step-003 `main.py`-mount precedent; there is nothing here for the coder to
fill:

- `frontend/src/user/pages/BookSettingsPage.tsx` — the **existing** mount `useEffect([state])` gains one
  line, `void loadSystemPrompt(state, bookId ?? "", ctrl.signal);`, sharing the same `AbortController`
  — changed. **No second `useEffect`**, and the effect's deps array is untouched.
- `frontend/src/user/pages/BookSettingsPage.tsx` — `<SystemPromptCard state={state} bookId={id} />`
  rendered inside the `detail`-present branch's `<Stack gap="xl">`, between the `State` section and the
  `<Divider />` that precedes `Co-authors` — changed. Two import lines added; nothing else in the file
  moved.

Structural notes that are part of the freeze:

- **No `system_prompt` field was added to any book DTO**, and no book api function changed. The prompt
  reaches the frontend only through the two new functions.
- **No client-side validation surface exists anywhere in this step** — no `clientErrors`, no `errors`
  union, no emptiness check, no trimming. Saving an empty editor is a legal save, and there is no
  delete control to render.
- MobX rules held: `observer` on the new component, no `useX` hook / `useCallback` / `useMemo` /
  `useReducer` / React context / Mantine `useForm` / runtime validation introduced, `useState` still
  only owns stable instances, and the state class still has **no effectful methods** — both new effects
  are external `(state, bookId, signal?)` functions.

Compile gate: `cd frontend && npm run build` (= `tsc && vite build`) — **clean**, 7201 modules
transformed, 0 errors. `npm test` was not run (skeleton does not run tests).

Expected red-gate profile: the two api functions, the two computeds, the two effects and the card body
all throw, so **every `[test]` DoD item (1-9) must be RED**. In particular the page itself throws while
rendering (the card is in its tree) and the mount effect's `void loadSystemPrompt(...)` produces a
rejected promise — both are the intended true-red, not a harness fault. Nothing in this step can pass
by construction.

- Caller-compile edits (out of Source-files scope): None — the only additions are new symbols plus two
  in-file wiring lines, and the whole bundle typechecks.

### Step 006 — frozen interface (2026-07-29)

**Consumed unchanged from step 005, nothing re-declared:** `BookAuthorPromptResponse` /
`UpdateBookAuthorPromptRequest` (`frontend/src/types/books.d.ts`) and `getOwnSystemPrompt` /
`updateOwnSystemPrompt` (`frontend/src/api/books.ts`). **Neither file was opened for edit**, no api
function and no DTO was added, and the two page-state files share no code and no component — the
trio-plus-draft shape is repeated here deliberately (`006.context.md` → "Reuse, not re-declaration").

Page state (`frontend/src/work/pages/bookStatePageState.ts`) — **purely additive**; the existing
`bookDetail` trio, its five computeds and `loadBookState` are byte-unchanged. New observable fields are
declared complete (a field declaration has no body); the two computeds and the two effects **throw**:

- `BookStatePageState.systemPrompt: BookAuthorPromptResponse | null = null` — new
- `BookStatePageState.systemPromptStatus: "idle" | "loading" | "ready" | "error" = "idle"` — new
- `BookStatePageState.systemPromptError: string | null = null` — new
  - the trio follows `frontend.md`'s `<name>` / `<name>Status` / `<name>Error` rule and the file's own
    `bookDetail*` shape; it is a **second, independent loadable** — DoD-7 depends on a prompt failure
    never touching the `bookDetail` trio and vice versa
- `BookStatePageState.systemPromptDraft = ""` (inferred `string`) — new — the editor draft
- `BookStatePageState.systemPromptServerErrors: Record<string, string> = {}` — new — save refusals
  only, keyed `system_prompt` (4xx) / `form` (5xx), held separately from `systemPromptError`. **No
  `clientErrors` and no `errors` union** — this field has no client-side validation, every string
  including `""` is valid.
- `BookStatePageState.systemPromptSubmitStatus: "idle" | "loading" | "ready" | "error" = "idle"` — new
- `BookStatePageState.get systemPromptDirty(): boolean` — new (pure computed; draft vs
  `systemPrompt?.system_prompt`, a not-yet-loaded prompt compared as `""`)
- `BookStatePageState.get canSaveSystemPrompt(): boolean` — new (pure computed; dirty AND no save in
  flight AND the prompt has loaded)
- `frontend/src/work/pages/bookStatePageState.ts` — `export async function loadSystemPrompt(state: BookStatePageState, bookId: string, signal?: AbortSignal): Promise<void>` — new
- `frontend/src/work/pages/bookStatePageState.ts` — `export async function saveSystemPrompt(state: BookStatePageState, bookId: string, signal?: AbortSignal): Promise<void>` — new
  - **no body parameter**: the payload is `{ system_prompt: state.systemPromptDraft }`, read off the
    state, matching the file's `(state, bookId, signal?)` effect shape.
  - The names deliberately match step 005's two effects; they are different modules bound to different
    state classes, and the parallel naming is the point (`006.context.md` — same shape, no sharing).
  - Frozen behavioural contract the coder must honour: on success `saveSystemPrompt` re-seeds
    `systemPrompt` **and** `systemPromptDraft` **from the PUT response body directly** and does **not**
    re-run `loadSystemPrompt`; on `ApiError` it leaves `systemPromptDraft` untouched. `loadSystemPrompt`
    treats `system_prompt: ""` / `modified_at: null` as a normal `ready` value, never an error.
  - The two `void <param>;` lines in each stub body exist only to satisfy `noUnusedParameters` under the
    throwing body; the coder deletes them when filling the body.

Page (`frontend/src/work/pages/BookStatePage.tsx`):

- `frontend/src/work/pages/BookStatePage.tsx` — the **existing** mount `useEffect([state])` gains one
  line, `void loadSystemPrompt(state, bookId ?? "", ctrl.signal);`, sharing the same `AbortController`
  and the same `return () => ctrl.abort()` cleanup — changed. **No second `useEffect`**, the deps array
  is untouched, and the existing `void loadBookState(...)` line is unmoved. One import line changed
  (`loadSystemPrompt` added to the existing `./bookStatePageState` import).
- `frontend/src/work/pages/BookStatePage.tsx` — a new `<Stack gap="xs">` section carrying
  `<Title order={5}>Your system prompt</Title>` and a `Skeleton (021 step 006): UNIMPLEMENTED` comment,
  placed between the `State notes` section and the `Per-chapter continuity` section, each separated by
  the existing `<Divider />` rhythm — changed. **The section body is the coder's**: trio loading branch,
  trio error branch, multi-line editor bound to `systemPromptDraft`, save control gated on
  `canSaveSystemPrompt`, server-error surface from `systemPromptServerErrors`, and the one line of copy
  stating the prompt is the caller's own and invisible to co-authors. Handlers are inner functions of
  this component closing over `state` / `bookId`.

Structural notes that are part of the freeze:

- **The section renders no editable control and no copy line as frozen.** Unlike step 005, the new
  region is *inside* an existing page whose read-only rendering is pre-existing behaviour, so the stub
  must not throw during render — a throwing render would take the whole Book-state view down and turn
  every pre-existing assertion in `frontend/tests/work/BookStatePage.test.tsx` red for the wrong reason.
  Emitting a heading and nothing else keeps the existing view byte-identical while leaving DoD-1 … DoD-8
  genuinely unsatisfiable (no textarea exists, no save control exists, no per-author copy exists).
- **No restore buffer anywhere**: `restoreBuffer.ts` is not imported, there is no buffer key, no
  keystroke persistence, no `baseVersion`, no stale-buffer detection, no divergence view and no 409
  path (`006.context.md`). No delete control and no client-side validation surface exist.
- **No other Book-state field became editable.** The five read-only rows, the members table, the state
  notes placeholder and the continuity placeholder are untouched; the state-notes section was **not**
  repurposed — it is about book *state notes*, a different thing from the author's prompt.
- MobX rules held: the state class still has **no effectful methods and no setters** (both new effects
  are external `(state, bookId, signal?)` functions), `observer` still wraps the page, `useState` still
  only owns the stable instance, and no `useX` hook / `useCallback` / `useMemo` / `useReducer` / React
  context / Mantine `useForm` / runtime validation was introduced. No `any`; `bookId` is `string`.

Compile gate: `cd frontend && npm run build` (= `tsc && vite build`) — **clean**, 7201 modules
transformed, 0 errors. `npm test` was not run (skeleton does not run tests).

Expected red-gate profile: the two computeds and the two effects throw and the section renders no
controls, so **every `[test]` DoD item (1-9) must be RED**. Two caveats for the red-gate verifier: the
mount effect's `void loadSystemPrompt(...)` produces a **rejected promise** (intended true-red, not a
harness fault — the step-005 precedent), and a DoD-9 test phrased purely as "no *other* region is
editable" would pass by construction, since this stub adds no editable region at all; only the
"exactly one editable region" reading of DoD-9 is genuinely red.

- Caller-compile edits (out of Source-files scope): None — both changed files are Source files, the
  additions are new symbols plus two in-file wiring lines, and the whole bundle typechecks.

## Tests

### Step 001 — tests (2026-07-29)

- `backend/tests/db/test_book_author_prompts.py` — covers DoD-1, DoD-2, DoD-3, DoD-4, DoD-5 —
  db-layer behaviour: full-column round trip (incl. `""` prompt kept distinct from `None`), miss and
  cross-pair isolation for `get_by_book_and_user`, the `(book_id, user_id)` unique constraint refused
  **by SQLite** (`IntegrityError` out of the second insert, not a Python pre-check), per-pair row
  independence across two users / two books, and `update` persisting changed text (incl. clearing to
  `""` without deleting the row) with the returned row agreeing with a fresh read.
- `backend/tests/test_data_domain_book_author_prompts.py` — covers DoD-6, DoD-7, DoD-8, DoD-9 —
  the table exists and is queryable on a freshly initialised DB (registration seam alone) and reports
  drift-clean; the codec pair round-trips every field with `id`/`book_id`/`user_id` as strings, keeps
  `""` as `""` and nulls as null, and still parses legacy numeric ids; exactly one
  `book_author_prompts` `TABLE_REGISTRY` entry, immediately after `book_members` and before
  `chapters`, bound to the model and codec pair; `Book`'s codec still round-trips `system_prompt`.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓.

#### Superseded-guard updates (scope extension — caused by this step's `TABLE_REGISTRY` insert)

Each of these locked in the registry sequence as it stood when written; this step legitimately changes
that sequence. No assertion logic rewritten, no coverage weakened.

- `backend/tests/test_data_domain_assistant_core.py` — `test_table_registry_order__DoD5` — superseded
  guard: inserted `"book_author_prompts"` between `"book_members"` and `"chapters"` in `CANONICAL_ORDER`.
- `backend/tests/test_data_domain_assistant_links.py` — `test_table_registry_order__DoD6` — same
  one-line `CANONICAL_ORDER` insert.
- `backend/tests/test_data_domain_book.py` — `test_table_registry_order__DoD5` — same one-line
  `CANONICAL_ORDER` insert.
- `backend/tests/test_data_domain_chapter.py` — `test_table_registry_order__DoD3` — same one-line
  `CANONICAL_ORDER` insert.
- `backend/tests/test_data_domain_chapter_changes.py` — `test_table_registry_order__DoD4` — same
  one-line `CANONICAL_ORDER` insert.
- `backend/tests/test_data_domain_codex.py` — `test_table_registry_order__DoD4` — same one-line
  `CANONICAL_ORDER` insert.
- `backend/tests/test_data_domain_continuity.py` — `test_table_registry_order__DoD5` — same one-line
  `CANONICAL_ORDER` insert.
- `backend/tests/test_data_domain_chat.py` — `test_full_table_registry_equals_canonical_order__DoD4` —
  inserted `"book_author_prompts"` between `"book_members"` and `"chapters"` in `FULL_CANONICAL_ORDER`
  (that test's exact full-registry equality is unchanged, and remains correct as the feature-008 final
  FK-order guard).
- `backend/tests/test_data_domain_chat.py` — `test_registry_order_unchanged_no_table_added__DoD10` —
  **re-scoped**, not merely updated. DoD-10 meant "feature 011 step 001 added columns, not a table",
  but the guard was written as whole-registry equality and so broke on any future table anywhere. It
  now asserts (a) the chat domain's registry footprint is still exactly one `chats` entry immediately
  followed by one `chat_messages` entry — the "no table added" claim itself — and (b) the registry
  restricted to `REGISTRY_AS_OF_FEATURE_011` (the frozen list of tables that existed when that step
  ran) still equals that list in order. Same verification, no longer freezing the registry forever.

### Step 002 — tests (2026-07-29)

- `backend/tests/services/test_book_author_prompts.py` — covers DoD-1 … DoD-9 — the DTOs and the
  per-author prompt service: an owner and a co-author of the same book each read back only their own
  text; a pair with no row reads `""` + `modified_at is None` and creates nothing; the write entry
  point creates the row and stamps **both** timestamps, and a later write updates **in place** (one
  row for the pair, same surrogate id, `created_at` preserved against a backdated anchor,
  `modified_at` advanced past it); `""` is accepted, read back empty, keeps the row, and stays
  distinguishable from "no row" *only* by `modified_at` (real vs null); a `reader` and a caller with
  `AccessRole.none` are refused on **both** entry points with `BookAuthorPromptErrorReason.not_a_member`
  and store nothing, and the reason enum has exactly that one member; a **co-author is not refused**
  on the write path (DoD-7, the deliberate reversal of US-108.AC-2); the response DTO's field set is
  exactly `{book_id, system_prompt, modified_at}` with no user identifier, the request DTO carries
  only `system_prompt`, and neither entry point takes a user id (`get_prompt(access)` /
  `upsert_prompt(access, req)`); a write leaves the other author's row in the same book and the same
  author's row in another book byte-identical (text + both timestamps).
- Rows are seeded through the sibling `db/` modules with the `db` fixture and `BookAccess` is
  constructed directly (frozen dataclass) — no route, client or JWT at this layer.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓.

### Step 003 — tests (2026-07-29)

- `backend/tests/routes/test_book_author_prompts.py` — covers DoD-1 … DoD-10 — the
  `/api/books/{book_id}/system-prompt` pair driven end-to-end through `http_client` with **real auth**
  (seeded user rows + minted JWTs, no stubbed dependency), every body validated through step 002's
  `BookAuthorPromptResponse`: `GET` returns the caller's own stored text with `book_id` as a **string**
  and **no `user_id`** key; a member with no row reads `200` / `""` / `modified_at is None` rather than
  `404`; `PUT` answers `200`, echoes what it stored and a following `GET` agrees; an owner and a
  co-author of one book each `PUT` different text and each reads back only their own (the replacement
  for UC-093's book-wide prompt); a second `PUT` changes the value, still answers `200` with a single
  prompt object and a non-regressing `modified_at`; a stranger to a **private** book gets `404` from
  both verbs (existence hiding, `test_chats.py::…__DoD9` shape) and a logged-in reader of a **public**
  book gets `403` from both with nothing stored; no token gets `401` from both; `DELETE` is refused by
  the framework as `405` and the stored prompt survives; a `PUT` body missing `system_prompt` (empty
  object and wrong key) is `422` and leaves the caller's prompt unwritten.
- Seed helpers `_now` / `_auth_header` / `_seed_user` / `_seed_author` / `_seed_private_book` /
  `_add_co_author` are copied verbatim from `backend/tests/routes/test_chats.py`; `_seed_public_book`
  (DoD-7's fixture, `visibility=Visibility.public`) is copied from `backend/tests/routes/test_codex.py`.
  DoD-1's stored rows are seeded through `db/book_author_prompts.create` so the read path is tested
  independently of the write path.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓, DoD-10 ✓.

### Step 004 — tests (2026-07-29)

- `backend/tests/services/test_prompt_composition.py` — covers DoD-1, DoD-2, DoD-3 — the composer's
  renamed third layer: the four-layer render is pinned exactly
  (`### BASE\n… \n\n### MODE\n… \n\n### AUTHOR\n… \n\n### CHAPTER\n…`), the heading is `AUTHOR` and
  `BOOK` appears nowhere, the author section sits strictly between the mode and chapter sections, the
  author's text is stripped like every other layer; a `None` / empty / whitespace-only author prompt
  renders byte-identically to omitting the argument (no heading, no section, no trailing separator,
  surrounding layers untouched) and alone yields `""`; the retired `book=` keyword raises `TypeError`
  (both with and without other layers), `inspect.signature` reports exactly
  `["base", "mode", "author", "chapter"]` with no `**kwargs` catch-all, and the third **positional**
  argument still binds to the third layer.
- `backend/tests/services/test_chat_turn.py` — covers DoD-4, DoD-5, DoD-6, DoD-7 — the turn: two
  authors of one book, each with a different stored prompt, compose two different system prompts,
  each exactly `compose_system_prompt(base=BASE_SYSTEM_PROMPT, author=<own text>)` and carrying
  nothing of the other's (the deliberate reversal of UC-093 / US-108); the lookup is per
  `(book_id, author_id)`, so the same author's prompt in another book never reaches this book's turn;
  an author with **no** row composes with no `### AUTHOR` heading at all and a base layer identical to
  the no-author-argument composition, as does a stored-but-blank row; a distinctive
  `Book.system_prompt` reaches nothing — neither alongside an author prompt nor alone, where two books
  differing only in that column compose byte-identical prompts; and the column is still alive — a book
  created through `POST /api/books` (real JWT, `http_client`) still carries it as a non-null `str`,
  and a seeded distinctive value survives `export_all()` → `import_all()` **into a fresh database**.
  No network: the `create_model_client` seam is monkeypatched with the module's existing fake client.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓,
  DoD-8 [manual/live, no test], DoD-9 [manual/live, no test].

#### Rename + superseded-guard updates (the pre-existing coverage moved off `book=`)

The 11 red tests the skeleton predicted were all the retired keyword. They were **moved, not
rewritten** — no assertion dropped or weakened; only the keyword, the section label and the row the
third-layer sentinel is seeded into changed.

- `backend/tests/services/test_prompt_composition.py` — feature 011 step 002's six tests
  (`__DoD1`, `__DoD2`) now pass `author=`; the sentinel `_BOOK` became `_AUTHOR` and
  `test_only_base_and_book_yields_exactly_two_sections__DoD2` was renamed
  `test_only_base_and_author_yields_exactly_two_sections__DoD2`. Same assertions throughout.
- `backend/tests/services/test_assistant_runtime.py` — feature 013 step 007's
  `__DoD7_US110_AC3`, the four `__DoD8_US110_AC4` cases and `__DoD13` now pass `author=` **and** seed
  their third-layer sentinel into a `BookAuthorPrompt` row for the chat's author instead of
  `Book.system_prompt` (the helper's `book_prompt=` became `author_prompt=`) — otherwise the rename
  alone would leave them asserting the retired source of truth. Mode resolution, the mode layer and
  tool gating (that module's own subject) are untouched.
- `backend/tests/services/test_chat_turn.py` — feature 011 step 003's
  `test_system_prompt_and_whole_registry_offered__DoD11` superseded in place: the sentinel moved from
  `Book.system_prompt` to the chat author's own prompt row. Its `BASE_SYSTEM_PROMPT` /
  third-layer-present / `BASE_TOOL_NAMES` assertions are unchanged. The shared `_context` helper gained
  `author_prompt=` and `username=`; `system_prompt=` is retained because DoD-6 needs to set the dormant
  column to a distinctive value.

### Step 005 — tests (2026-07-29)

- `frontend/tests/user/bookSettingsPageState.test.ts` — covers DoD-1, DoD-2, DoD-3, DoD-4, DoD-5,
  DoD-6, DoD-7, DoD-9 — the two api functions and the prompt half of the page state. `api/client`'s
  `request` is the mocked seam (the `assistantConfigApi.test.ts` precedent: the wire module is itself
  the subject for DoD-9, and the same seam observes the effects), `ApiError` kept real via an
  `importOriginal` spread, `fetch` never touched. Asserts: `getOwnSystemPrompt` GETs
  `/api/books/<id>/system-prompt` and `updateOwnSystemPrompt` PUTs the same path with
  `{ system_prompt }` (`""` sent verbatim), both forwarding the trailing `signal` and propagating an
  `ApiError`; `loadSystemPrompt` seeds the trio + draft from the response, reports `loading`
  in flight, treats `""` + `modified_at: null` as `ready` (never `error`), and on failure lands in
  `error` with a non-empty message, **no** stale `systemPrompt`, the `detail` trio untouched, and a
  second call recovering; the gate computeds (`idle` → false, clean draft → false, edited → true,
  reverted → false, in-flight save → false); the save sends the draft, then adopts the **server's**
  differing value into both `systemPrompt` and `systemPromptDraft` with exactly one `PUT` and no
  follow-up read, forwards its signal, accepts an empty draft as a legal clearing save, and on
  `ApiError` resolves with the draft intact, `submitStatus: "error"`, the server's message in
  `systemPromptServerErrors` and the load trio still `ready`.
- `frontend/tests/user/BookSettingsPage.test.tsx` — covers DoD-1, DoD-2, DoD-3, DoD-4, DoD-5, DoD-6,
  DoD-7, DoD-8 — the rendered surface, page mounted under `/books/:bookId/settings`. `api/books` is
  mocked as an `importOriginal` spread with `vi.fn()` overrides for every call the page can make (a
  spread cannot strip an export the page needs, the overrides keep every call off the network);
  `../../src/auth` stubbed as the signed-in owner; `ApiError` real. Asserts: the mount load addresses
  the URL's book and its text lands in the editor; an empty prompt renders an empty, enabled,
  non-readonly, genuinely typeable field with no failure copy and no retry; typing then saving sends
  the draft and the editor ends showing the **server's** different value; the save control is
  absent-or-disabled while clean and while a save is in flight, and enabled only in between; an
  emptied editor saves `{ system_prompt: "" }` and clears; **no** delete/remove/clear/discard button
  exists in the card, nor any prompt-named destructive button anywhere; a refused save shows the
  server's message with the typed draft still in the field; a failed load shows a retry control, no
  editor at all, and a retry that really re-reads; and the copy states the prompt is the author's own
  while the card never frames it as book-wide or shared.
- Locators are spec-shaped, not DOM-shaped: the editor is the prompt-labelled `<textarea>` (or the
  page's sole one) and the save control is the nearest `save`-named button above it, so no test id or
  markup structure is asserted. "Unavailable" accepts either a disabled or an absent control, since
  the DoD says only that saving cannot happen.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓,
  DoD-10 [manual/live, no test].

### Step 006 — tests (2026-07-29)

- `frontend/tests/work/BookStatePage.test.tsx` — covers DoD-1 … DoD-9 — **extended, not
  replaced**: the six pre-existing feature-010 cases are byte-unchanged, and the file's existing
  `api/books` module factory was widened with `getOwnSystemPrompt` / `updateOwnSystemPrompt`
  (`vi.fn()`, every prior entry kept) with both re-armed in `beforeEach` alongside `getBookDetail`,
  since `restoreMocks` wipes implementations between tests. Nine new cases, page mounted under
  `/:bookId/state` exactly as the existing ones are. Asserts: the mount load addresses the URL's
  book **alongside** `getBookDetail` and its text lands in the editor while the book-state content
  renders; an empty prompt (`""` + `modified_at: null`) renders an empty, enabled, non-readonly,
  genuinely typeable field with no failure copy and no retry; typing then saving sends
  `{ system_prompt: <draft> }` to the URL's book and the editor ends showing the **server's**
  different value; the save control is absent-or-disabled while clean, enabled once edited, closed
  again when the loaded value is restored, and unavailable while a save is in flight (exactly one
  `PUT`); an emptied editor saves `{ system_prompt: "" }` and clears, and no delete/remove/clear/
  discard control exists in the section nor any prompt-named destructive button on the page; a
  refused save (real `ApiError(403, …)`) shows the server's message with the typed draft still in
  the field; a rejected prompt load shows failure copy and binds no editor **while** title,
  description, both labels, both timestamps, owner, co-author, state-notes and the
  `016.chapter-close-continuity` region all still render (the two trios failing independently);
  and the copy states the prompt is the caller's own without framing it as book-wide or shared.
- **DoD-9 is asserted in two halves** so it cannot pass by construction against a stub that adds no
  editable region: the prompt editor *is* editable (enabled, not readonly, accepts typed text)
  **and** `editableControls()` — every non-disabled, non-readonly `input`/`textarea`/`select`/
  `contenteditable`, buttons excluded — equals exactly `[promptEditor()]`.
- Locators are spec-shaped, not DOM-shaped (copied from the step-005 page spec): the editor is the
  prompt-labelled `<textarea>` (or the page's sole one) and the save control the nearest
  `save`-named button above it; no test id and no markup structure is asserted. "Unavailable"
  accepts either a disabled or an absent control, since the DoD says only that saving cannot happen.
  Nothing asserts a restore buffer, `baseVersion`, stale-buffer detection or a 409 path — all out of
  scope by decision.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓,
  DoD-10 [manual/live, no test].

#### Stale-module-factory repairs (scope extension — caused by this step's mount-effect prompt load)

Three pre-existing feature-010/011/013 `work` specs replace `api/books` **wholesale** with a
`vi.mock` module factory. A whole-module factory strips any export it omits, so this step's new
`getOwnSystemPrompt` call from `BookStatePage`'s mount effect resolved to `undefined` and produced
unhandled rejections (`npm test` exited 1 with 0 failed assertions). Mock repair only — **no test
added, removed, weakened or restructured** in any of the three files, and every pre-existing factory
entry kept verbatim. Each file uses `restoreMocks` + a `beforeEach` re-arm, so the new mocks are
re-armed there too; a bare `vi.fn()` would resolve `undefined` and merely change the rejection's
shape, so the read mock resolves the "no stored prompt" wire value
`{ book_id, system_prompt: "", modified_at: null }` (step 005's `BookAuthorPromptResponse`).

- `frontend/tests/work/subjectRoutes.test.tsx` — added `getOwnSystemPrompt` / `updateOwnSystemPrompt`
  to the `api/books` factory and re-armed both in `beforeEach` with a resolved prompt-shaped value
  (`book_id: "bk-1"`).
- `frontend/tests/work/chatsNavigatorEntry.test.tsx` — same two factory entries and the same
  `beforeEach` re-arm (`book_id: "bk-1"`); this file mounts `WorkRoutes` at `/bk-1/chats`, whose
  redirect target is the Book-state page.
- `frontend/tests/work/codexListPage.test.tsx` — same two factory entries and the same `beforeEach`
  re-arm (`book_id: BOOK_ID`). Green today only because no case mounts the Book-state route; repaired
  so the fix is durable rather than accidental.
- `frontend/tests/work/BookStatePage.test.tsx` was **not** touched here — its own factory was already
  widened as part of step 006's tests above.

## Notes & Issues

_populated by the coder when worth saying_

### Step 001 (coder, 2026-07-29) — only five bodies were left to fill

The model, the `db/engine.py` registration import and the `TABLE_REGISTRY` entry were already complete
and correct when the skeleton froze them (a table and a registry tuple are declarative — nothing to
leave unimplemented). This pass therefore changed exactly five function bodies: the three in
`db/book_author_prompts.py` and the codec pair in `services/db_import_export.py`. The skeleton's note
below about the eight pre-existing `CANONICAL_ORDER` lists still stands unaddressed — those are test
files and out of every coder scope.

### Step 001 (skeleton, 2026-07-29) — the new `TABLE_REGISTRY` entry breaks 9 pre-existing tests

**What intent asked for:** step 001 → Interface intent — "One `TABLE_REGISTRY` entry,
`book_author_prompts`, placed **immediately after `book_members`**". Done, and correct.

**What conflicts:** eight existing `backend/tests/test_data_domain_*.py` modules each hardcode a
`CANONICAL_ORDER` / `FULL_CANONICAL_ORDER` list of registry labels and assert
`labels == expected_sequence` (the "canonical-restricted invariant") or, in `test_data_domain_chat.py`,
exact equality with the full list. None of those lists contains `book_author_prompts` — it is the
first table added since they were written, and the first ever inserted *mid-list*. Every earlier
table addition was appended at a position the lists already anticipated, so this is the first time
the invariant bites. Result on `.venv/Scripts/python -m pytest`: **9 failed, 737 passed** — all 9
failures are this one cause, none is in feature 021's own scope:

- `test_data_domain_assistant_core.py::test_table_registry_order__DoD5`
- `test_data_domain_assistant_links.py::test_table_registry_order__DoD6`
- `test_data_domain_book.py::test_table_registry_order__DoD5`
- `test_data_domain_chapter.py::test_table_registry_order__DoD3`
- `test_data_domain_chapter_changes.py::test_table_registry_order__DoD4`
- `test_data_domain_codex.py::test_table_registry_order__DoD4`
- `test_data_domain_continuity.py::test_table_registry_order__DoD5`
- `test_data_domain_chat.py::test_full_table_registry_equals_canonical_order__DoD4`
- `test_data_domain_chat.py::test_registry_order_unchanged_no_table_added__DoD10`

**Why the skeleton did not fix it:** those are test files, and they are not in step 001's Test files
list (`backend/tests/db/test_book_author_prompts.py`,
`backend/tests/test_data_domain_book_author_prompts.py`). The skeleton may not write tests at all,
and the test-coder's scope is the two listed files — so no role in the current step plan owns the
repair. Left failing deliberately rather than silently widened.

**The fix is mechanical:** insert the string `"book_author_prompts"` between `"book_members"` and
`"chapters"` in the seven `CANONICAL_ORDER` lists and in `test_data_domain_chat.py`'s
`FULL_CANONICAL_ORDER` — one line per file, no assertion logic changes. `test_data_domain_chat.py`'s
`test_registry_order_unchanged_no_table_added__DoD10` is worth a second look: it asserts the registry
is *unchanged*, so it breaks by construction on every future table and may want re-scoping rather
than updating.

**Suggested resolutions (orchestrator's call):**
1. *(recommended)* Amend step 001's Test files list to include the eight modules, and let the
   test-coder make the one-line insert in each. Cheapest, keeps the air gap, and the red-gate run
   then reports only genuine step-001 red.
2. Treat it as a plan-level bug fix outside the step and have a fixer touch the eight lists before
   the red-gate run. Same edit, different owner.
3. Leave them red and have the verifier whitelist them as known-collateral. Not recommended — it
   trains the pipeline to ignore red, and step 002-004 will inherit the noise.

### Step 001 (orchestrator, 2026-07-29) — resolution of the above, and a correction

**Resolution: option 1.** Step 001's Test files scope was extended to the eight modules and the
test-coder made the repairs. Seven were one-line `CANONICAL_ORDER` inserts; `test_data_domain_chat.py`'s
`FULL_CANONICAL_ORDER` likewise. `test_registry_order_unchanged_no_table_added__DoD10` was **re-scoped
rather than line-edited** — it now asserts the chat domain's own footprint (one `chats` entry
immediately followed by one `chat_messages` entry) plus order-preservation over a
`REGISTRY_AS_OF_FEATURE_011` snapshot, so it still tests what its DoD-10 meant without freezing the
registry against every future table. Both verifiers checked the re-scope and found it sound.

**Correction:** the coder's entry above ("still stand unaddressed") is **stale** — the coder cannot
read test files and so could not see the repair. All eight are green; the verify run is
**761 passed, 0 failed**.

### Step 002 (coder, 2026-07-29) — air-gap slip, disclosed

`status.md` was opened whole rather than section-by-section, so the `## Tests` block for steps 001–002
was read incidentally. No test file was opened and no test was run; the implementation follows the step
file, `002.context.md` and the frozen skeleton only. Flagged so the orchestrator can weigh it.

### Step 002 (coder, 2026-07-29) — only the service had bodies to fill

`models/schemas/book_author_prompts.py` arrived complete from the skeleton — two declarative Pydantic
DTOs have nothing to leave unimplemented — so this pass changed exactly the four function bodies in
`services/book_author_prompts.py` plus one import line. `services/authz.py` untouched: no `Capability`
member, no `_CAPABILITY_MATRIX` row, no collaboration-mode check.

### Step 003 (coder, 2026-07-29) — `main.py` needed no edit, and how the build gate was run

Only one of the two Source files changed. `main.py`'s mount (`from app.routes import book_author_prompts`
in the import block and `app.include_router(book_author_prompts.router)` immediately after
`codex.router`) arrived complete from the skeleton — a two-line wiring change is declarative, with no
body to leave unimplemented — so this pass changed exactly the three function bodies in
`routes/book_author_prompts.py` and added no import to it.

Root `CLAUDE.md` declares **no backend typecheck** and the coder may not run the test suite, so the
build gate for this layer was: import `app.main` and read the **generated OpenAPI**. Result —
`/api/books/{book_id}/system-prompt` exposes exactly `get` + `put`, both declaring `200` (plus
FastAPI's `422`) with `BookAuthorPromptResponse` as the response model, `book_id` supplied by the
dependency and re-declared by neither handler. `_map_prompt_error` was smoke-called directly and
returns `403` with `err.message` as a plain-string `detail`; `hasattr(module, "_map_authz_error")` is
`False`, as the freeze requires.

### Step 003 (coder, 2026-07-29) — air-gap note, disclosed

`status.md` was read section-by-section this time and the `## Tests` block was **not** opened, nor was
any file under `backend/tests/` opened directly. However, the self-review diff was run as
`git diff -- backend/` rather than scoped to the two Source files, so the **pre-existing**
`test_data_domain_*.py` edits made during step 001 (the `CANONICAL_ORDER` inserts and the
`test_registry_order_unchanged_no_table_added__DoD10` re-scope) scrolled past as diff hunks. **Step
003's own test file, `backend/tests/routes/test_book_author_prompts.py`, is untracked and therefore
appeared in no diff — nothing about this step's tests was seen**, and no test was run. Flagged so the
orchestrator can weigh it; the lesson for the next pass is to scope the review diff to the step's
Source files.

### Step 004 (coder, 2026-07-29) — two files changed, two arrived complete, and how the gate was run

Only `prompt_composition.py` and `chat_turn.py` had anything to implement; `models/book.py` and
`models/schemas/books.py` are pure docstring revisions and arrived complete and correct from the
skeleton (DoD-8 is `[manual/live]`, and all four docstrings were verified present and unrevised).

Root `CLAUDE.md` declares **no backend typecheck** and the coder may not run the suite, so the gate was
byte-compile of all four Source files + `import app.main` (so the sole call site binds) + a direct
composer smoke: signature still `(base, mode, author, chapter)`; a populated author renders
`### AUTHOR` **between** `### MODE` and `### CHAPTER`; blank / whitespace-only / `None` author is
byte-identical to omitting the argument; `compose_system_prompt(book=...)` still raises `TypeError`;
no-args still yields `""`. On the turn: `chat_turn.books` is gone, `chat_turn.book_author_prompts` is
present, `run_turn`'s source contains neither `chapter=` nor `book.system_prompt`.

The three stale skeleton scaffolding notes in `prompt_composition.py` (module docstring, function
docstring, inline) said the label "still reads `BOOK`" — present-tense claims that this pass falsified,
so they were trimmed to the historical statement that the label was left to the coder. The
`Skeleton (021 step 00N):` records themselves were kept, matching the steps 001–003 precedent.

Air gap held: `status.md` was read section-by-section (`## Tests` never opened), no file under
`backend/tests/` was opened, no test was run, and the self-review diff was scoped to the four Source
files.

### Step 005 (coder, 2026-07-29) — three files had bodies, two arrived complete

`types/books.d.ts` (two declarative DTOs + a revised docstring) and `BookSettingsPage.tsx` (one line in
the existing mount effect + one element in the render tree) arrived complete and correct from the
skeleton, so this pass filled exactly the six throwing bodies plus the card's JSX. Two stale
present-tense skeleton notes were trimmed because this pass falsified them (the "throwing stub bodies
for the coder to implement" line in the `BookSettingsPageState` docstring and the `SKELETON (021/005)`
line on `SystemPromptCard`), matching the step-004 precedent.

Two judgement calls worth recording, both inside the freeze:

- **`canSaveSystemPrompt` reads "the prompt has loaded" as `systemPromptStatus === "ready"`**, not
  `systemPrompt !== null`. They differ only mid-retry — after a failed reload the previous value is
  still on the state — and the stricter reading refuses a save while a load is in flight, which is what
  "nothing may be written over a value that was never read" is protecting.
- **The two server-error keys render in two different places, never both**: the `form` key (5xx) in an
  `Alert` above the editor, the `system_prompt` key (4xx) as the `Textarea`'s field error. Rendering
  the union in both surfaces would print a refusal message twice.

Gate: `cd frontend && npm run build` clean (7201 modules, 0 errors). Air gap held — `status.md` was read
section-by-section (`## Tests` never opened), no file under `frontend/tests/` was opened, no test was
run, and the self-review diff was scoped to the five Source files.

### Step 006 (coder, 2026-07-29) — four bodies, one JSX section, and three judgement calls

The mount-effect line and the empty, heading-only section arrived complete from the skeleton, so this
pass filled exactly the two computeds, the two effects and the section body. One stale present-tense
skeleton note was trimmed from the `BookStatePageState` docstring (the "Skeleton (021 step 006): … frozen
with throwing bodies" paragraph), matching the step-004/005 precedent; feature 010's older skeleton
paragraph above it was left alone.

Three judgement calls, all inside the freeze:

- **The section renders no `Retry` control**, unlike step 005's `SystemPromptCard`. The step file and the
  skeleton both enumerate the section's contents as loading branch, error branch, editor, save control,
  server-error surface and the copy line — a retry was in neither list, so it was not added.
- **The copy line renders in all three branches** (it sits above the trio branch), so the "yours alone,
  not shared with co-authors" statement stands even when the prompt fails to load.
- **`canSaveSystemPrompt` reads "the prompt has loaded" as `systemPromptStatus === "ready"`**, the same
  reading step 005 recorded — a save is refused while a load is in flight.

Gate: `cd frontend && npm run build` clean (7201 modules, 0 errors). Air gap held — `status.md` was read
by offset into `## Skeleton` → Step 006, `## Files Changed` and `## Notes & Issues` only (`## Tests`
never opened), no file under `frontend/tests/` was opened or diffed, and no test was run. Nothing under
`docs/architecture/` needed a new observation: `outcome.md` § 12 already carries the
`frontend-workspace.md` editability-table change this step makes real.

### Step 006 (orchestrator, 2026-07-29) — Test-files scope extended after a FAIL / Fault SPEC

The first verify run returned **FAIL / Fault SPEC**. Every assertion in the frontend suite passed
(384 passed, 0 failed), but `npm test` exited **1** with two unhandled rejections:
`No "getOwnSystemPrompt" export is defined on the "../../src/api/books" mock`.

Cause: this step makes `BookStatePage`'s mount effect call a newly added `api/books` export, and three
pre-existing `work` specs replace `api/books` **wholesale** with a module factory enumerating only the
exports the page needed before this feature. A whole-module factory strips what it omits. Two of the
three mount the page. No role's original scope owned the repair — the coder's Source list holds no test
file, and the test-coder's Test list held only this step's own spec; both stayed correctly inside their
lists and both produced spec-faithful work.

**Resolution: the same precedent step 001 set** for the `TABLE_REGISTRY` insert — the orchestrator
extended step 006's Test files list to the three specs, and the test-coder widened each factory with
`getOwnSystemPrompt` / `updateOwnSystemPrompt`, keeping every prior entry verbatim and re-arming both in
each file's existing `beforeEach` with the wire-shaped no-prompt value `{ book_id, system_prompt: "",
modified_at: null }` (a bare `vi.fn()` resolves `undefined`, which would only change the rejection's
shape). `codexListPage.test.tsx` carried the same stale factory and was green only because it does not
mount the page; it was included so the repair is durable rather than accidental. No test was added,
removed, weakened or restructured — `it(` counts are identical to `HEAD` in all three files, and
`BookStatePage.test.tsx` was not touched.

**The red gate was not re-run** for this repair. Its purpose is to prove new tests fail against stubs;
there were no stubs left, the step's own coverage was already red-then-green, and the change was mock
plumbing carrying no assertion. Re-verify: **384 passed, 0 failed, exit 0, zero unhandled errors.**
