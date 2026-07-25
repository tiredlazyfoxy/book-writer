# Feature 008 — data-domain

| Step | File                          | Status  | Verifier | Date |
|------|-------------------------------|---------|----------|------|
| 001  | `001.feat020-config-core.md`  | done    | PASS     | 2026-07-25 |
| 002  | `002.feat020-link-tables.md`  | done    | PASS     | 2026-07-25 |
| 003  | `003.assistant-mode-seed.md`  | done    | PASS     | 2026-07-25 |
| 004  | `004.book-and-membership.md`  | done    | PASS     | 2026-07-25 |
| 005  | `005.chapter.md`              | done    | PASS     | 2026-07-25 |
| 006  | `006.chapter-changes.md`      | done    | PASS     | 2026-07-25 |
| 007  | `007.continuity.md`           | done    | PASS     | 2026-07-25 |
| 008  | `008.codex.md`                | done    | PASS     | 2026-07-25 |
| 009  | `009.chat.md`                 | done    | PASS     | 2026-07-25 |

## Files Changed

### Step 001 — FEAT-020 config core (AssistantMode + SubAgent)
- `backend/app/db/assistant_modes.py` — filled `create` / `get_by_id(key)` / `list_all` bodies
- `backend/app/db/sub_agents.py` — filled `create` / `get_by_id(id)` bodies
- `backend/app/services/db_import_export.py` — filled the AssistantMode + SubAgent codec pair bodies
- `backend/app/models/assistant_mode.py` — verified (skeleton-complete, unchanged)
- `backend/app/models/sub_agent.py` — verified (skeleton-complete, unchanged)
- `backend/app/db/engine.py` — verified registration present (skeleton-complete, unchanged)

### Step 002 — FEAT-020 link tables (ModeTool + SubagentTool + ModeSubagent)
- `backend/app/db/mode_tools.py` — filled `create` / `get_by_id(id)` / `list_by_mode(mode_key)` bodies
- `backend/app/db/subagent_tools.py` — filled `create` / `get_by_id(id)` / `list_by_sub_agent(sub_agent_id)` bodies
- `backend/app/db/mode_subagents.py` — filled `create` / `get_by_id(id)` / `list_by_mode(mode_key)` bodies
- `backend/app/services/db_import_export.py` — filled the three link-table codec pair bodies (no timestamps)
- `backend/app/models/mode_tool.py` — verified (skeleton-complete, unchanged)
- `backend/app/models/subagent_tool.py` — verified (skeleton-complete, unchanged)
- `backend/app/models/mode_subagent.py` — verified (skeleton-complete, unchanged)
- `backend/app/db/engine.py` — verified registration present (skeleton-complete, unchanged)

### Step 003 — AssistantMode seed at first-run setup
- `backend/app/db/assistant_modes.py` — added `DEFAULT_MODE_KEYS` constant + filled `seed_default_modes()` (check-then-create over the fixed five via own `get_by_id`/`create`, `system_prompt=None`, idempotent)
- `backend/app/services/setup.py` — verified skeleton wiring intact (seed call after `init_db()`, before `set_db_ready(True)`); no change

### Step 004 — Book + BookMember
- `backend/app/db/books.py` — filled `create` (add/commit/refresh) / `get_by_id(book_id)` (select→one_or_none) bodies
- `backend/app/db/book_members.py` — filled `create` / `get_by_id(member_id)` / `list_by_book(book_id)` (select→list(all)) bodies
- `backend/app/services/db_import_export.py` — filled the Book + BookMember codec pair bodies (three enums via `.value`/`E(...)`, nullable moderation triple + timestamps passthrough, ids as string↔int)
- `backend/app/models/book.py` — verified against field table (skeleton-complete, unchanged)
- `backend/app/models/book_member.py` — verified composite unique + single timestamp (skeleton-complete, unchanged)
- `backend/app/db/engine.py` — verified both registration imports present (skeleton-complete, unchanged)

### Step 005 — Chapter
- `backend/app/db/chapters.py` — filled `create` (add/commit/refresh) / `get_by_id(chapter_id)` (select→one_or_none) / `list_by_book(book_id)` (select→list(all)) bodies
- `backend/app/services/db_import_export.py` — filled the Chapter codec pair bodies (`state` via `.value`/`ChapterState(...)`, nullable `summary_status` as `e.value if e else None`/`SummaryStatus(x) if x else None`, nullable `summary`/`system_prompt` + `version`/`ordinal` int passthrough, ids string↔int, isoformat timestamps)
- `backend/app/models/chapter.py` — verified against field table (skeleton-complete, unchanged)
- `backend/app/db/engine.py` — verified `import app.models.chapter` registration present (skeleton-complete, unchanged)

### Step 006 — ChapterChange + ChapterTextRevision
- `backend/app/db/chapter_changes.py` — filled `create` (add/commit/refresh) / `get_by_id(change_id)` (select→one_or_none) / `list_by_chapter(chapter_id)` (select→list(all)) bodies
- `backend/app/db/chapter_text_revisions.py` — filled `create` / `get_by_id(revision_id)` / `list_by_chapter(chapter_id)` bodies
- `backend/app/services/db_import_export.py` — filled the ChapterChange + ChapterTextRevision codec pair bodies (ids string↔int, both enums via `.value`/`E(...)`, nullable `line_from`/`line_to`/`applied_at`/`applied_by` passthrough on change, non-null FKs as string on revision, isoformat timestamps)
- `backend/app/models/chapter_change.py` — verified against field table (skeleton-complete, unchanged)
- `backend/app/models/chapter_text_revision.py` — verified against field table (skeleton-complete, unchanged)
- `backend/app/db/engine.py` — verified both registration imports present (skeleton-complete, unchanged)

### Step 007 — ChapterNoteChangeset + Flag
- `backend/app/db/chapter_note_changesets.py` — filled `create` (add/commit/refresh) / `get_by_id(changeset_id)` (select→one_or_none) / `get_by_chapter(chapter_id)` (select→one_or_none, single row since chapter_id unique) bodies
- `backend/app/db/flags.py` — filled `create` / `get_by_id(flag_id)` (select→one_or_none) / `list_by_chapter(chapter_id)` (select→list(all)) bodies
- `backend/app/services/db_import_export.py` — filled the ChapterNoteChangeset + Flag codec pair bodies (ids string↔int, nullable `status` via `e.value if e else None`/`NoteStatus(x) if x else None`, both Flag enums via `.value`/`FlagOrigin`/`FlagStatus`, nullable `resolved_by` as string/`int`-when-set + isoformat timestamps)
- `backend/app/models/chapter_notes.py` — verified against field table (skeleton-complete, unchanged)
- `backend/app/models/flag.py` — verified against field table (skeleton-complete, unchanged)
- `backend/app/db/engine.py` — verified both registration imports present (skeleton-complete, unchanged)

### Step 008 — CodexEntry + CodexEntryVersion
- `backend/app/db/codex_entries.py` — filled `create` (add/commit/refresh) / `get_by_id(entry_id)` (select→one_or_none) / `list_by_book(book_id)` (select→list(all)) bodies
- `backend/app/db/codex_entry_versions.py` — filled `create` / `get_by_id(version_id)` / `list_by_entry(entry_id)` bodies
- `backend/app/services/db_import_export.py` — filled the CodexEntry + CodexEntryVersion codec pair bodies (ids/`book_id`/`author_id`/`entry_id` string↔int, `kind` via `.value`/`CodexKind(...)`, nullable `name` passthrough incl. null-for-fact, `archived` bool via `.get(..., False)`, nullable `modified_by` as string/`int`-when-set, `generation` plain int passthrough, isoformat timestamps)
- `backend/app/models/codex_entry.py` — verified against field table (skeleton-complete, unchanged)
- `backend/app/models/codex_entry_version.py` — verified against field table (skeleton-complete, unchanged)
- `backend/app/db/engine.py` — verified both registration imports present (skeleton-complete, unchanged)

### Step 009 — Chat + ChatMessage
- `backend/app/db/chats.py` — filled `create` (add/commit/refresh) / `get_by_id(chat_id)` (select→one_or_none) / `list_by_book(book_id)` (select→list(all)) bodies
- `backend/app/db/chat_messages.py` — filled `create` / `get_by_id(message_id)` / `list_by_chat(chat_id)` bodies
- `backend/app/services/db_import_export.py` — filled the Chat + ChatMessage codec pair bodies (ids/`book_id`/`author_id`/`chat_id` string↔int, `title`/`role`/`content` passthrough, `archived` bool via `.get(..., False)`, `position` plain int passthrough, isoformat timestamps)
- `backend/app/models/chat.py` — verified both classes against field tables (skeleton-complete, unchanged)
- `backend/app/db/engine.py` — verified single `import app.models.chat` registration present (skeleton-complete, unchanged)

## Skeleton

### Step 001 — frozen interface (2026-07-25)

Models (declarative tables — full field shape frozen, no behavior to stub):
- `backend/app/models/assistant_mode.py` — `class AssistantMode(SQLModel, table=True)`, `__tablename__ = "assistant_modes"`; `key: str = Field(primary_key=True)` (natural PK, no snowflake), `system_prompt: str | None = Field(default=None)`, `created_at: datetime | None = Field(default=None)`, `modified_at: datetime | None = Field(default=None)` — new
- `backend/app/models/sub_agent.py` — `class SubAgent(SQLModel, table=True)`, `__tablename__ = "sub_agents"`; `id: int = Field(default_factory=generate_id, primary_key=True)`, `name: str = Field(unique=True, index=True)`, `system_prompt: str`, `disabled: bool = False`, `llm_server_id: int | None = Field(default=None, foreign_key="llm_servers.id")`, `model_name: str | None = Field(default=None)`, `created_at: datetime | None = Field(default=None)`, `modified_at: datetime | None = Field(default=None)` — new

DB modules (session-free; bodies raise `NotImplementedError`):
- `backend/app/db/assistant_modes.py` — `async def create(row: AssistantMode) -> AssistantMode` — new
- `backend/app/db/assistant_modes.py` — `async def get_by_id(key: str) -> AssistantMode | None` (lookup by `key` PK) — new
- `backend/app/db/assistant_modes.py` — `async def list_all() -> list[AssistantMode]` — new
- `backend/app/db/sub_agents.py` — `async def create(row: SubAgent) -> SubAgent` — new
- `backend/app/db/sub_agents.py` — `async def get_by_id(sub_agent_id: int) -> SubAgent | None` — new

Codecs in `backend/app/services/db_import_export.py` (bodies raise `NotImplementedError`):
- `def _assistant_mode_to_dict(mode: AssistantMode) -> dict[str, object]` — new (emits `key` verbatim)
- `def _dict_to_assistant_mode(data: dict[str, object]) -> AssistantMode` — new (parses `key` verbatim, never `int()`)
- `def _sub_agent_to_dict(sub_agent: SubAgent) -> dict[str, object]` — new (`id` as `str`)
- `def _dict_to_sub_agent(data: dict[str, object]) -> SubAgent` — new (`id` string-or-legacy-number → `int`)

Registry (`TABLE_REGISTRY` in `db_import_export.py`) — inserted at positions 3, 4, immediately after `llm_servers`:
- `("assistant_modes", AssistantMode, _assistant_mode_to_dict, _dict_to_assistant_mode)` — new
- `("sub_agents", SubAgent, _sub_agent_to_dict, _dict_to_sub_agent)` — new

Model registration (`backend/app/db/engine.py::_register_models()`):
- Added `import app.models.assistant_mode  # noqa: F401` and `import app.models.sub_agent  # noqa: F401`

Caller-compile edits (out of Source-files scope): None.

### Step 002 — frozen interface (2026-07-25)

Models (declarative tables — full field shape frozen, no behavior to stub; no timestamps on any link table):
- `backend/app/models/mode_tool.py` — `class ModeTool(SQLModel, table=True)`, `__tablename__ = "mode_tool"` (SINGULAR); `__table_args__ = (UniqueConstraint("mode_key", "tool_name", name="uq_mode_tool_mode_key_tool_name"),)`; `id: int = Field(default_factory=generate_id, primary_key=True)`, `mode_key: str = Field(foreign_key="assistant_modes.key")`, `tool_name: str` — new
- `backend/app/models/subagent_tool.py` — `class SubagentTool(SQLModel, table=True)`, `__tablename__ = "subagent_tool"` (SINGULAR); `__table_args__ = (UniqueConstraint("sub_agent_id", "tool_name", name="uq_subagent_tool_sub_agent_id_tool_name"),)`; `id: int = Field(default_factory=generate_id, primary_key=True)`, `sub_agent_id: int = Field(foreign_key="sub_agents.id")`, `tool_name: str` — new
- `backend/app/models/mode_subagent.py` — `class ModeSubagent(SQLModel, table=True)`, `__tablename__ = "mode_subagent"` (SINGULAR); `__table_args__ = (UniqueConstraint("mode_key", "sub_agent_id", name="uq_mode_subagent_mode_key_sub_agent_id"),)`; `id: int = Field(default_factory=generate_id, primary_key=True)`, `mode_key: str = Field(foreign_key="assistant_modes.key")`, `sub_agent_id: int = Field(foreign_key="sub_agents.id")` — new

DB modules (session-free; bodies raise `NotImplementedError`):
- `backend/app/db/mode_tools.py` — `async def create(row: ModeTool) -> ModeTool` — new
- `backend/app/db/mode_tools.py` — `async def get_by_id(id: int) -> ModeTool | None` — new
- `backend/app/db/mode_tools.py` — `async def list_by_mode(mode_key: str) -> list[ModeTool]` (filter `ModeTool.mode_key == mode_key`) — new
- `backend/app/db/subagent_tools.py` — `async def create(row: SubagentTool) -> SubagentTool` — new
- `backend/app/db/subagent_tools.py` — `async def get_by_id(id: int) -> SubagentTool | None` — new
- `backend/app/db/subagent_tools.py` — `async def list_by_sub_agent(sub_agent_id: int) -> list[SubagentTool]` (filter `SubagentTool.sub_agent_id == sub_agent_id`) — new
- `backend/app/db/mode_subagents.py` — `async def create(row: ModeSubagent) -> ModeSubagent` — new
- `backend/app/db/mode_subagents.py` — `async def get_by_id(id: int) -> ModeSubagent | None` — new
- `backend/app/db/mode_subagents.py` — `async def list_by_mode(mode_key: str) -> list[ModeSubagent]` (filter `ModeSubagent.mode_key == mode_key`) — new

Codecs in `backend/app/services/db_import_export.py` (bodies raise `NotImplementedError`):
- `def _mode_tool_to_dict(mode_tool: ModeTool) -> dict[str, object]` — new (`id` as `str`; `mode_key` verbatim string; `tool_name` passthrough)
- `def _dict_to_mode_tool(data: dict[str, object]) -> ModeTool` — new (`id` string-or-number → `int`; `mode_key` verbatim, never `int()`)
- `def _subagent_tool_to_dict(subagent_tool: SubagentTool) -> dict[str, object]` — new (`id` + `sub_agent_id` as `str`)
- `def _dict_to_subagent_tool(data: dict[str, object]) -> SubagentTool` — new (`id` + `sub_agent_id` string-or-number → `int`)
- `def _mode_subagent_to_dict(mode_subagent: ModeSubagent) -> dict[str, object]` — new (`id` + `sub_agent_id` as `str`; `mode_key` verbatim string)
- `def _dict_to_mode_subagent(data: dict[str, object]) -> ModeSubagent` — new (`id` + `sub_agent_id` string-or-number → `int`; `mode_key` verbatim)

Registry (`TABLE_REGISTRY` in `db_import_export.py`) — inserted at positions 5, 6, 7, immediately after `sub_agents` (plural labels deliberately differ from the singular `__tablename__`):
- `("mode_tools", ModeTool, _mode_tool_to_dict, _dict_to_mode_tool)` — new
- `("subagent_tools", SubagentTool, _subagent_tool_to_dict, _dict_to_subagent_tool)` — new
- `("mode_subagents", ModeSubagent, _mode_subagent_to_dict, _dict_to_mode_subagent)` — new

Model registration (`backend/app/db/engine.py::_register_models()`):
- Added `import app.models.mode_tool  # noqa: F401`, `import app.models.subagent_tool  # noqa: F401`, `import app.models.mode_subagent  # noqa: F401` (after the step-001 imports)

Caller-compile edits (out of Source-files scope): None.

### Step 003 — frozen interface (2026-07-25)

New DB helper (session-free; body raises `NotImplementedError`):
- `backend/app/db/assistant_modes.py` — `async def seed_default_modes() -> None` — new (reuses `get_by_id` + `create`; check-then-create over the fixed five keys `edit-character`, `edit-location`, `edit-fact`, `write-chapter`, `close-chapter`, each created with `system_prompt=None` if absent; idempotent, never clobbers an existing row)

Modified service (signature UNCHANGED; existing behavior preserved, one call threaded in):
- `backend/app/services/setup.py` — `async def create_database(admin_username: str, password: str, password_confirm: str) -> User` — changed (was identical signature; added `from app.db import assistant_modes` import and `await assistant_modes.seed_default_modes()` call placed after `await init_db()` and before `set_db_ready(True)`)

Caller-compile edits (out of Source-files scope): None.

### Step 004 — frozen interface (2026-07-25)

Models (declarative tables — full field shape frozen, no behavior to stub):
- `backend/app/models/book.py` — three enums `class CollaborationMode(str, enum.Enum)` (`free`/`proposal`), `class Visibility(str, enum.Enum)` (`private`/`public`), `class BookState(str, enum.Enum)` (`active`/`archived`/`quarantined`/`destroyed`); `class Book(SQLModel, table=True)`, `__tablename__ = "books"`; fields in order: `id: int = Field(default_factory=generate_id, primary_key=True)`, `title: str`, `description: str`, `owner_id: int = Field(foreign_key="users.id")`, `collaboration_mode: CollaborationMode`, `visibility: Visibility`, `state: BookState`, `moderation_reason: str | None = Field(default=None)`, `moderated_by: int | None = Field(default=None, foreign_key="users.id")`, `moderated_at: datetime | None = Field(default=None)`, `system_prompt: str`, `active_notes: str`, `created_at: datetime | None = Field(default=None)`, `modified_at: datetime | None = Field(default=None)` — new
- `backend/app/models/book_member.py` — `class BookMember(SQLModel, table=True)`, `__tablename__ = "book_members"`; `__table_args__ = (UniqueConstraint("book_id", "user_id", name="uq_book_member_book_id_user_id"),)`; `id: int = Field(default_factory=generate_id, primary_key=True)`, `book_id: int = Field(foreign_key="books.id")`, `user_id: int = Field(foreign_key="users.id")`, `role: str`, `created_at: datetime | None = Field(default=None)` (ONE timestamp, no `modified_at`) — new

DB modules (session-free; bodies raise `NotImplementedError`):
- `backend/app/db/books.py` — `async def create(row: Book) -> Book` — new
- `backend/app/db/books.py` — `async def get_by_id(book_id: int) -> Book | None` — new
- `backend/app/db/book_members.py` — `async def create(row: BookMember) -> BookMember` — new
- `backend/app/db/book_members.py` — `async def get_by_id(member_id: int) -> BookMember | None` — new
- `backend/app/db/book_members.py` — `async def list_by_book(book_id: int) -> list[BookMember]` (filter `BookMember.book_id == book_id`) — new

Codecs in `backend/app/services/db_import_export.py` (bodies raise `NotImplementedError`):
- `def _book_to_dict(book: Book) -> dict[str, object]` — new (`id`/`owner_id` as `str`; three enums via `.value`; nullable moderation triple + timestamps passthrough; required strings passthrough)
- `def _dict_to_book(data: dict[str, object]) -> Book` — new (`id`/`owner_id` string-or-number → `int`; enums via `CollaborationMode`/`Visibility`/`BookState`; nullable `moderated_by` → `int` when set)
- `def _book_member_to_dict(member: BookMember) -> dict[str, object]` — new (`id`/`book_id`/`user_id` as `str`; `role` passthrough; one timestamp)
- `def _dict_to_book_member(data: dict[str, object]) -> BookMember` — new (`id`/`book_id`/`user_id` string-or-number → `int`; `role` passthrough)

Registry (`TABLE_REGISTRY` in `db_import_export.py`) — inserted at positions 8, 9, immediately after `mode_subagents` (both plural labels match `__tablename__`):
- `("books", Book, _book_to_dict, _dict_to_book)` — new
- `("book_members", BookMember, _book_member_to_dict, _dict_to_book_member)` — new

Model registration (`backend/app/db/engine.py::_register_models()`):
- Added `import app.models.book  # noqa: F401` and `import app.models.book_member  # noqa: F401` (after the step-002 imports)

Caller-compile edits (out of Source-files scope): None.

### Step 005 — frozen interface (2026-07-25)

Model (declarative table — full field shape frozen, no behavior to stub; `state = closing` + nullable `summary_status` land now, unused per Stage-4-columns rule):
- `backend/app/models/chapter.py` — two enums `class ChapterState(str, enum.Enum)` (`planned`/`open`/`closing`/`closed`), `class SummaryStatus(str, enum.Enum)` (`draft`/`approved`/`stale`); `class Chapter(SQLModel, table=True)`, `__tablename__ = "chapters"`; fields in order: `id: int = Field(default_factory=generate_id, primary_key=True)`, `book_id: int = Field(foreign_key="books.id")`, `ordinal: int` (required, no default), `title: str`, `state: ChapterState` (required, no default), `sketch: str`, `text: str`, `summary: str | None = Field(default=None)`, `summary_status: SummaryStatus | None = Field(default=None)`, `system_prompt: str | None = Field(default=None)`, `version: int = 1` (literal default 1), `created_at: datetime | None = Field(default=None)`, `modified_at: datetime | None = Field(default=None)` — new

DB module (session-free; bodies raise `NotImplementedError`):
- `backend/app/db/chapters.py` — `async def create(row: Chapter) -> Chapter` — new
- `backend/app/db/chapters.py` — `async def get_by_id(chapter_id: int) -> Chapter | None` — new
- `backend/app/db/chapters.py` — `async def list_by_book(book_id: int) -> list[Chapter]` (filter `Chapter.book_id == book_id`) — new

Codecs in `backend/app/services/db_import_export.py` (bodies raise `NotImplementedError`):
- `def _chapter_to_dict(chapter: Chapter) -> dict[str, object]` — new (`id`/`book_id` as `str`; `state` via `.value`; `summary_status` as `e.value if e else None`; nullable `summary`/`system_prompt` + `version` int + `ordinal` int passthrough; timestamps isoformat-or-None)
- `def _dict_to_chapter(data: dict[str, object]) -> Chapter` — new (`id`/`book_id` string-or-number → `int`; `state` via `ChapterState(...)`; `summary_status` via `SummaryStatus(x) if x else None`; nullable `summary`/`system_prompt` via `.get(...)`; `version`/`ordinal` int passthrough)

Registry (`TABLE_REGISTRY` in `db_import_export.py`) — inserted at position 10, immediately after `book_members`:
- `("chapters", Chapter, _chapter_to_dict, _dict_to_chapter)` — new

Model registration (`backend/app/db/engine.py::_register_models()`):
- Added `import app.models.chapter  # noqa: F401` (after the step-004 imports)

Caller-compile edits (out of Source-files scope): None.

### Step 006 — frozen interface (2026-07-25)

Models (declarative tables — full field shape frozen, no behavior to stub; ALL timestamps nullable per the feature convention):
- `backend/app/models/chapter_change.py` — two enums `class PlacementKind(str, enum.Enum)` (`append`/`range`), `class ChangeStatus(str, enum.Enum)` (`pending`/`applied`/`rejected`); `class ChapterChange(SQLModel, table=True)`, `__tablename__ = "chapter_changes"`; fields in order: `id: int = Field(default_factory=generate_id, primary_key=True)`, `chapter_id: int = Field(foreign_key="chapters.id")`, `author_id: int = Field(foreign_key="users.id")`, `placement_kind: PlacementKind` (required enum, no default), `line_from: int | None = Field(default=None)`, `line_to: int | None = Field(default=None)`, `base_version: int` (required, no default), `text: str`, `status: ChangeStatus` (required enum, no default), `applied_at: datetime | None = Field(default=None)`, `applied_by: int | None = Field(default=None, foreign_key="users.id")` (nullable FK), `created_at: datetime | None = Field(default=None)` — new
- `backend/app/models/chapter_text_revision.py` — `class ChapterTextRevision(SQLModel, table=True)`, `__tablename__ = "chapter_text_revisions"`; no enums, no composite unique; fields in order: `id: int = Field(default_factory=generate_id, primary_key=True)`, `chapter_id: int = Field(foreign_key="chapters.id")`, `applied_change_id: int = Field(foreign_key="chapter_changes.id")`, `text_before: str`, `applied_by: int = Field(foreign_key="users.id")` (NON-null FK — differs from `ChapterChange.applied_by`), `applied_at: datetime | None = Field(default=None)` (nullable per timestamp convention) — new

DB modules (session-free; bodies raise `NotImplementedError`):
- `backend/app/db/chapter_changes.py` — `async def create(row: ChapterChange) -> ChapterChange` — new
- `backend/app/db/chapter_changes.py` — `async def get_by_id(change_id: int) -> ChapterChange | None` — new
- `backend/app/db/chapter_changes.py` — `async def list_by_chapter(chapter_id: int) -> list[ChapterChange]` (filter `ChapterChange.chapter_id == chapter_id`) — new
- `backend/app/db/chapter_text_revisions.py` — `async def create(row: ChapterTextRevision) -> ChapterTextRevision` — new
- `backend/app/db/chapter_text_revisions.py` — `async def get_by_id(revision_id: int) -> ChapterTextRevision | None` — new
- `backend/app/db/chapter_text_revisions.py` — `async def list_by_chapter(chapter_id: int) -> list[ChapterTextRevision]` (filter `ChapterTextRevision.chapter_id == chapter_id`) — new

Codecs in `backend/app/services/db_import_export.py` (bodies raise `NotImplementedError`):
- `def _chapter_change_to_dict(chapter_change: ChapterChange) -> dict[str, object]` — new (`id`/`chapter_id`/`author_id` as `str`; nullable `applied_by` as `str`-or-`None`; both enums via `.value`; nullable `line_from`/`line_to` int passthrough; `base_version` int + `text` passthrough; nullable `applied_at`+`created_at` isoformat-or-None)
- `def _dict_to_chapter_change(data: dict[str, object]) -> ChapterChange` — new (`id`/`chapter_id`/`author_id` string-or-number → `int`; nullable `applied_by` → `int` when set; enums via `PlacementKind`/`ChangeStatus`; nullable `line_from`/`line_to` via `.get(...)`; `base_version` int + `text` direct)
- `def _chapter_text_revision_to_dict(revision: ChapterTextRevision) -> dict[str, object]` — new (`id`/`chapter_id`/`applied_change_id`/`applied_by` as `str`; `text_before` passthrough; nullable `applied_at` isoformat-or-None)
- `def _dict_to_chapter_text_revision(data: dict[str, object]) -> ChapterTextRevision` — new (`id`/`chapter_id`/`applied_change_id`/`applied_by` string-or-number → `int`; `text_before` direct; `applied_at` from isoformat)

Registry (`TABLE_REGISTRY` in `db_import_export.py`) — inserted at positions 11, 12, immediately after `chapters` (`chapter_changes` FIRST because `chapter_text_revisions.applied_change_id` FKs `chapter_changes.id`):
- `("chapter_changes", ChapterChange, _chapter_change_to_dict, _dict_to_chapter_change)` — new
- `("chapter_text_revisions", ChapterTextRevision, _chapter_text_revision_to_dict, _dict_to_chapter_text_revision)` — new

Model registration (`backend/app/db/engine.py::_register_models()`):
- Added `import app.models.chapter_change  # noqa: F401` and `import app.models.chapter_text_revision  # noqa: F401` (after the step-005 import; chapter_change before chapter_text_revision so the FK target table is registered first)

Caller-compile edits (out of Source-files scope): None.

### Step 007 — frozen interface (2026-07-25)

Models (declarative tables — full field shape frozen, no behavior to stub; ALL timestamps nullable per the feature convention):
- `backend/app/models/chapter_notes.py` — one enum `class NoteStatus(str, enum.Enum)` (`draft`/`approved`/`stale`); `class ChapterNoteChangeset(SQLModel, table=True)`, `__tablename__ = "chapter_note_changesets"`; fields in order: `id: int = Field(default_factory=generate_id, primary_key=True)`, `chapter_id: int = Field(unique=True, foreign_key="chapters.id")` (SINGLE-COLUMN unique AND FK on the same Field — one changeset per chapter, no `__table_args__`/composite unique), `added: str`, `modified: str`, `deleted: str`, `status: NoteStatus | None = Field(default=None)` (nullable enum, Stage-4 land-now), `created_at: datetime | None = Field(default=None)`, `modified_at: datetime | None = Field(default=None)` — new
- `backend/app/models/flag.py` — two enums `class FlagOrigin(str, enum.Enum)` (`check`/`person`), `class FlagStatus(str, enum.Enum)` (`open`/`resolved`); `class Flag(SQLModel, table=True)`, `__tablename__ = "flags"`; fields in order: `id: int = Field(default_factory=generate_id, primary_key=True)`, `chapter_id: int = Field(foreign_key="chapters.id")`, `origin: FlagOrigin` (required enum, no default), `comment: str`, `status: FlagStatus` (required enum, no default), `created_by: int = Field(foreign_key="users.id")` (NON-null FK), `created_at: datetime | None = Field(default=None)`, `resolved_by: int | None = Field(default=None, foreign_key="users.id")` (nullable FK), `resolved_at: datetime | None = Field(default=None)` (nullable) — new

DB modules (session-free; bodies raise `NotImplementedError`):
- `backend/app/db/chapter_note_changesets.py` — `async def create(row: ChapterNoteChangeset) -> ChapterNoteChangeset` — new
- `backend/app/db/chapter_note_changesets.py` — `async def get_by_id(changeset_id: int) -> ChapterNoteChangeset | None` — new
- `backend/app/db/chapter_note_changesets.py` — `async def get_by_chapter(chapter_id: int) -> ChapterNoteChangeset | None` (select where `ChapterNoteChangeset.chapter_id == chapter_id` → `.one_or_none()`; returns the SINGLE row or None, NOT a list — chapter_id is unique) — new
- `backend/app/db/flags.py` — `async def create(row: Flag) -> Flag` — new
- `backend/app/db/flags.py` — `async def get_by_id(flag_id: int) -> Flag | None` — new
- `backend/app/db/flags.py` — `async def list_by_chapter(chapter_id: int) -> list[Flag]` (filter `Flag.chapter_id == chapter_id` → list) — new

Codecs in `backend/app/services/db_import_export.py` (bodies raise `NotImplementedError`):
- `def _chapter_note_changeset_to_dict(changeset: ChapterNoteChangeset) -> dict[str, object]` — new (`id`/`chapter_id` as `str`; `added`/`modified`/`deleted` passthrough; nullable `status` as `e.value if e else None`; timestamps isoformat-or-None)
- `def _dict_to_chapter_note_changeset(data: dict[str, object]) -> ChapterNoteChangeset` — new (`id`/`chapter_id` string-or-number → `int`; `added`/`modified`/`deleted` direct; `status` via `NoteStatus(x) if x else None`; timestamps from isoformat)
- `def _flag_to_dict(flag: Flag) -> dict[str, object]` — new (`id`/`chapter_id`/`created_by` as `str`; both enums via `.value`; `comment` passthrough; nullable `resolved_by` as `str`-or-`None`; `created_at`+`resolved_at` isoformat-or-None)
- `def _dict_to_flag(data: dict[str, object]) -> Flag` — new (`id`/`chapter_id`/`created_by` string-or-number → `int`; both enums via `FlagOrigin`/`FlagStatus`; `comment` direct; nullable `resolved_by` → `int` when set; datetimes from isoformat)

Registry (`TABLE_REGISTRY` in `db_import_export.py`) — the `flags` interleave: `chapter_note_changesets` inserted immediately after `chapter_text_revisions`; `flags` inserted IMMEDIATELY AFTER `chapter_note_changesets` (current end of the registry). Canonical `flags` position is after `codex_entry_versions`, but codex tables don't exist yet (step 008 adds them and will slot the codex tuples BETWEEN `chapter_note_changesets` and `flags`). Verified live order: `... chapter_text_revisions, chapter_note_changesets, flags`.
- `("chapter_note_changesets", ChapterNoteChangeset, _chapter_note_changeset_to_dict, _dict_to_chapter_note_changeset)` — new
- `("flags", Flag, _flag_to_dict, _dict_to_flag)` — new

Model registration (`backend/app/db/engine.py::_register_models()`):
- Added `import app.models.chapter_notes  # noqa: F401` and `import app.models.flag  # noqa: F401` (after the step-006 imports)

Caller-compile edits (out of Source-files scope): None.

### Step 008 — frozen interface (2026-07-25)

Models (declarative tables — full field shape frozen, no behavior to stub; ALL timestamps nullable per the feature convention; NO vector/LanceDB registration — deferred to `013.codex`):
- `backend/app/models/codex_entry.py` — one enum `class CodexKind(str, enum.Enum)` (`character`/`location`/`fact`); `class CodexEntry(SQLModel, table=True)`, `__tablename__ = "codex_entries"`; fields in order: `id: int = Field(default_factory=generate_id, primary_key=True)`, `book_id: int = Field(foreign_key="books.id")`, `kind: CodexKind` (required enum, no default), `name: str | None = Field(default=None)` (nullable — null for fact), `body: str`, `archived: bool = False` (bool literal default), `author_id: int = Field(foreign_key="users.id")` (NON-null FK — original creator), `modified_by: int | None = Field(default=None, foreign_key="users.id")` (nullable FK — last editor), `created_at: datetime | None = Field(default=None)`, `modified_at: datetime | None = Field(default=None)` — new
- `backend/app/models/codex_entry_version.py` — reuses `CodexKind` via `from app.models.codex_entry import CodexKind` (NO second enum); `class CodexEntryVersion(SQLModel, table=True)`, `__tablename__ = "codex_entry_versions"`; fields in order: `id: int = Field(default_factory=generate_id, primary_key=True)`, `entry_id: int = Field(foreign_key="codex_entries.id")`, `name: str | None = Field(default=None)` (nullable), `body: str`, `kind: CodexKind` (required enum, no default), `author_id: int = Field(foreign_key="users.id")` (NON-null FK), `generation: int` (REQUIRED non-null int, no default — 1-based), `created_at: datetime | None = Field(default=None)` (single timestamp) — new

DB modules (session-free; bodies raise `NotImplementedError`):
- `backend/app/db/codex_entries.py` — `async def create(row: CodexEntry) -> CodexEntry` — new
- `backend/app/db/codex_entries.py` — `async def get_by_id(entry_id: int) -> CodexEntry | None` — new
- `backend/app/db/codex_entries.py` — `async def list_by_book(book_id: int) -> list[CodexEntry]` (filter `CodexEntry.book_id == book_id`) — new
- `backend/app/db/codex_entry_versions.py` — `async def create(row: CodexEntryVersion) -> CodexEntryVersion` — new
- `backend/app/db/codex_entry_versions.py` — `async def get_by_id(version_id: int) -> CodexEntryVersion | None` — new
- `backend/app/db/codex_entry_versions.py` — `async def list_by_entry(entry_id: int) -> list[CodexEntryVersion]` (filter `CodexEntryVersion.entry_id == entry_id`) — new

Codecs in `backend/app/services/db_import_export.py` (bodies raise `NotImplementedError`):
- `def _codex_entry_to_dict(entry: CodexEntry) -> dict[str, object]` — new (`id`/`book_id` as `str`; `kind` via `.value`; nullable `name` passthrough incl. null-for-fact; `archived` bool; `body` passthrough; `author_id` as `str` required; nullable `modified_by` as `str`-or-`None`; timestamps isoformat-or-None)
- `def _dict_to_codex_entry(data: dict[str, object]) -> CodexEntry` — new (`id`/`book_id` string-or-number → `int`; `kind` via `CodexKind(...)`; nullable `name` via `.get(...)`; `archived` bool via `.get(...)`; `author_id` → `int` required; nullable `modified_by` → `int` when set; timestamps from isoformat)
- `def _codex_entry_version_to_dict(version: CodexEntryVersion) -> dict[str, object]` — new (`id`/`entry_id`/`author_id` as `str`; nullable `name` passthrough; `body` passthrough; `kind` via `.value`; `generation` plain int passthrough; `created_at` isoformat-or-None)
- `def _dict_to_codex_entry_version(data: dict[str, object]) -> CodexEntryVersion` — new (`id`/`entry_id`/`author_id` string-or-number → `int`; nullable `name` via `.get(...)`; `body` direct; `kind` via `CodexKind(...)`; `generation` plain int passthrough; `created_at` from isoformat)

Registry (`TABLE_REGISTRY` in `db_import_export.py`) — the codex interleave: the two codex tuples slotted BETWEEN `chapter_note_changesets` and the existing `flags` tuple (`flags` NOT moved, just displaced forward), `codex_entries` before `codex_entry_versions` (FK: `codex_entry_versions.entry_id` → `codex_entries.id`). Verified live order tail: `... chapter_text_revisions, chapter_note_changesets, codex_entries, codex_entry_versions, flags`. No `VECTOR_SOURCE_REGISTRY` entry (deferred).
- `("codex_entries", CodexEntry, _codex_entry_to_dict, _dict_to_codex_entry)` — new
- `("codex_entry_versions", CodexEntryVersion, _codex_entry_version_to_dict, _dict_to_codex_entry_version)` — new

Model registration (`backend/app/db/engine.py::_register_models()`):
- Added `import app.models.codex_entry  # noqa: F401` and `import app.models.codex_entry_version  # noqa: F401` (after the step-007 `chapter_notes` import, before `flag`; codex_entry before codex_entry_version so the FK target table is registered first)

Caller-compile edits (out of Source-files scope): None.

### Step 009 — frozen interface (2026-07-25)

Models (declarative tables — full field shape frozen, no behavior to stub; BOTH classes in ONE module `models/chat.py`; ALL timestamps nullable per the feature convention; `role` is a FREE STRING, NO enum):
- `backend/app/models/chat.py` — `class Chat(SQLModel, table=True)`, `__tablename__ = "chats"`; fields in order: `id: int = Field(default_factory=generate_id, primary_key=True)`, `book_id: int = Field(foreign_key="books.id")`, `author_id: int = Field(foreign_key="users.id")`, `title: str` (required), `archived: bool = False` (bool literal default), `created_at: datetime | None = Field(default=None)`, `modified_at: datetime | None = Field(default=None)` — new
- `backend/app/models/chat.py` — `class ChatMessage(SQLModel, table=True)` (SAME module), `__tablename__ = "chat_messages"`; fields in order: `id: int = Field(default_factory=generate_id, primary_key=True)`, `chat_id: int = Field(foreign_key="chats.id")`, `role: str` (required — free string, NO enum), `content: str` (required), `position: int` (REQUIRED non-null int, no default — ordinal within the chat), `created_at: datetime | None = Field(default=None)` (single timestamp — no `modified_at`) — new

DB modules (session-free; bodies raise `NotImplementedError`):
- `backend/app/db/chats.py` — `async def create(row: Chat) -> Chat` — new
- `backend/app/db/chats.py` — `async def get_by_id(chat_id: int) -> Chat | None` — new
- `backend/app/db/chats.py` — `async def list_by_book(book_id: int) -> list[Chat]` (filter `Chat.book_id == book_id`) — new
- `backend/app/db/chat_messages.py` — `async def create(row: ChatMessage) -> ChatMessage` — new
- `backend/app/db/chat_messages.py` — `async def get_by_id(message_id: int) -> ChatMessage | None` — new
- `backend/app/db/chat_messages.py` — `async def list_by_chat(chat_id: int) -> list[ChatMessage]` (filter `ChatMessage.chat_id == chat_id`) — new

Codecs in `backend/app/services/db_import_export.py` (bodies raise `NotImplementedError`):
- `def _chat_to_dict(chat: Chat) -> dict[str, object]` — new (`id`/`book_id`/`author_id` as `str`; `title` passthrough; `archived` bool; timestamps isoformat-or-None)
- `def _dict_to_chat(data: dict[str, object]) -> Chat` — new (`id`/`book_id`/`author_id` string-or-number → `int`; `title` direct; `archived` bool via `.get(...)`; timestamps from isoformat)
- `def _chat_message_to_dict(message: ChatMessage) -> dict[str, object]` — new (`id`/`chat_id` as `str`; `role`/`content` passthrough; `position` plain int passthrough; `created_at` isoformat-or-None)
- `def _dict_to_chat_message(data: dict[str, object]) -> ChatMessage` — new (`id`/`chat_id` string-or-number → `int`; `role`/`content` direct; `position` plain int passthrough; `created_at` from isoformat)

Registry (`TABLE_REGISTRY` in `db_import_export.py`) — the FINAL two entries, appended after the `flags` tuple (`chats` before `chat_messages` — FK: `chat_messages.chat_id` → `chats.id`). Verified full live order (18 entries): `users, llm_servers, assistant_modes, sub_agents, mode_tools, subagent_tools, mode_subagents, books, book_members, chapters, chapter_changes, chapter_text_revisions, chapter_note_changesets, codex_entries, codex_entry_versions, flags, chats, chat_messages` — equals the full canonical order exactly.
- `("chats", Chat, _chat_to_dict, _dict_to_chat)` — new
- `("chat_messages", ChatMessage, _chat_message_to_dict, _dict_to_chat_message)` — new

Model registration (`backend/app/db/engine.py::_register_models()`):
- Added a SINGLE `import app.models.chat  # noqa: F401` (after the step-008 imports; the one module declares BOTH `chats` and `chat_messages` tables)

Caller-compile edits (out of Source-files scope): None.

## Tests

### Step 001 — tests (2026-07-25)
- `backend/tests/test_data_domain_assistant_core.py` — covers DoD-1..DoD-6:
  - DoD-1: AssistantMode codec round-trip — `key` emitted/parsed verbatim (incl. all-digit-key guard against `int()` coercion), nullable `system_prompt` (None + set), isoformat timestamps.
  - DoD-2: SubAgent codec round-trip — `id` as string→int, `disabled` bool, nullable model pair in both-null and both-set shapes, isoformat timestamps.
  - DoD-3: `db/assistant_modes` create→get_by_id(key) equal row + list_all() includes it.
  - DoD-4: `db/sub_agents` create→get_by_id(id) equal row.
  - DoD-5: TABLE_REGISTRY has assistant_modes + sub_agents, llm_servers precedes them, tablename sequence = canonical order restricted to present tables.
  - DoD-6: after init_db(), both tables in SQLModel.metadata + consistency report all-`ok`.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓

### Step 002 — tests (2026-07-25)
- `backend/tests/test_data_domain_assistant_links.py` — covers DoD-1..DoD-7:
  - DoD-1: ModeTool codec round-trip — `id` string→int, `mode_key` verbatim string (incl. all-digit-key guard against `int()`), `tool_name` preserved.
  - DoD-2: SubagentTool codec round-trip — `id` + `sub_agent_id` string→int, `tool_name` preserved.
  - DoD-3: ModeSubagent codec round-trip — `id` + `sub_agent_id` string→int, `mode_key` verbatim string (incl. all-digit-key guard).
  - DoD-4: each `db/` module create→get_by_id equal row + parent-scoped list (`list_by_mode` / `list_by_sub_agent`) filters to exactly the parent's rows (two parents inserted).
  - DoD-5: composite-unique enforced per table — second row with the same natural pair raises `IntegrityError`.
  - DoD-6: TABLE_REGISTRY has PLURAL labels `mode_tools`/`subagent_tools`/`mode_subagents` in canonical order, each after `sub_agents`, label sequence = canonical order restricted to present tables.
  - DoD-7: after init_db(), the three SINGULAR tablenames (`mode_tool`/`subagent_tool`/`mode_subagent`) in SQLModel.metadata + consistency report all-`ok`.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓

### Step 003 — tests (2026-07-25)
- `backend/tests/test_data_domain_mode_seed.py` — covers DoD-1, DoD-2, DoD-3:
  - DoD-1: seed_default_modes() on a fresh DB creates exactly five rows whose keys equal the fixed five; each seeded row `system_prompt is None`.
  - DoD-2: idempotent — a second seed_default_modes() call raises no error and leaves exactly five rows (keys still the fixed five, no duplicates).
  - DoD-3: wiring — create_database("root", "password123", "password123") on a fresh instance leaves the five mode rows present (keys = fixed five); readiness flipped to True as a sanity check.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 [manual/live, no test]

### Step 004 — tests (2026-07-25)
- `backend/tests/test_data_domain_book.py` — covers DoD-1..DoD-6:
  - DoD-1: Book codec round-trip — `id`/`owner_id` string↔int, three enums via `.value`↔member, both the active shape (state=active, moderation triple None) and the moderated shape (state=quarantined, reason string + nullable FK `moderated_by` emitted as STRING (id-as-string) parsing back to the same int + isoformat `moderated_at`), required strings + isoformat timestamps.
  - DoD-2: BookMember codec round-trip — `id`/`book_id`/`user_id` string↔int, `role` preserved, single `created_at` via isoformat.
  - DoD-3: `db/books` create→get_by_id equal row; `db/book_members` create→get_by_id equal row + `list_by_book` filters to exactly one book's members (two book_ids inserted).
  - DoD-4: composite unique enforced — second BookMember with same (book_id, user_id) raises `IntegrityError` (differs only by surrogate id).
  - DoD-5: TABLE_REGISTRY has `books` then `book_members`, each after `mode_subagents`, label sequence = canonical order restricted to present tables.
  - DoD-6: after init_db(), `books` and `book_members` in SQLModel.metadata + consistency report all-`ok`.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓

### Step 005 — tests (2026-07-25)
- `backend/tests/test_data_domain_chapter.py` — covers DoD-1..DoD-4:
  - DoD-1: Chapter codec round-trip — `id`/`book_id` string↔int; `state` via `.value`↔member for ALL FOUR values (planned/open/closing/closed, parametrized); `summary_status` in both the null shape (None↔None) and the set shape (all three of draft/approved/stale via `.value`↔member, parametrized); nullable `summary`/`system_prompt` in both None and set shapes; `version` int (default 1 and =3) and `ordinal` int preserved; isoformat timestamps (set and None) preserved.
  - DoD-2: `db/chapters` create→get_by_id equal row (version defaults to 1); `list_by_book` filters to exactly one book's chapters (two book_ids inserted).
  - DoD-3: TABLE_REGISTRY has `chapters` after `book_members`, label sequence = canonical order restricted to present tables, tuple binds `Chapter`.
  - DoD-4: after init_db(), `chapters` in SQLModel.metadata + consistency report all-`ok`.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓

### Step 006 — tests (2026-07-25)
- `backend/tests/test_data_domain_chapter_changes.py` — covers DoD-1..DoD-5:
  - DoD-1: ChapterChange codec round-trip in BOTH shapes — (a) range+applied (line_from/line_to ints, applied_at datetime, nullable FK `applied_by` set → emitted as STRING → int) and (b) append+pending (line_from/line_to None, applied_at None, `applied_by` None → emitted None → None); `id`/`chapter_id`/`author_id` string↔int, both enums via `.value`↔member, base_version int + text + isoformat created_at/applied_at preserved.
  - DoD-2: ChapterTextRevision codec round-trip — `id`/`chapter_id`/`applied_change_id`/`applied_by` string↔int, text_before preserved, isoformat applied_at in both set and None shapes.
  - DoD-3: each `db/` module create→get_by_id equal row + `list_by_chapter` filters to exactly one chapter's rows (two chapter_ids inserted per table).
  - DoD-4: TABLE_REGISTRY has `chapter_changes` then `chapter_text_revisions`, each after `chapters`, chapter_changes before chapter_text_revisions, label sequence = canonical order restricted to present tables, tuples bind the correct model classes.
  - DoD-5: after init_db(), both tables in SQLModel.metadata + consistency report all-`ok`.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓

### Step 007 — tests (2026-07-25)
- `backend/tests/test_data_domain_continuity.py` — covers DoD-1..DoD-6:
  - DoD-1: ChapterNoteChangeset codec round-trip — `id`/`chapter_id` string↔int, `added`/`modified`/`deleted` preserved, nullable `status` in BOTH the null shape (None↔None) and the set shape (all three of draft/approved/stale via `.value`↔member, parametrized), isoformat timestamps (set and None).
  - DoD-2: Flag codec round-trip in BOTH shapes — (a) OPEN (status=open, `resolved_by`/`resolved_at` None → emitted None → None) and (b) RESOLVED (status=resolved, `resolved_by` set → emitted as STRING → int, `resolved_at` datetime); `id`/`chapter_id`/`created_by` string↔int, `origin`+`status` via `.value`↔member, `comment` + isoformat `created_at` preserved.
  - DoD-3: `db/chapter_note_changesets` create→get_by_id equal row + get_by_chapter returns the SINGLE row or None; `db/flags` create→get_by_id equal row + list_by_chapter filters to exactly one chapter's flags (two chapter_ids inserted).
  - DoD-4: single-column unique enforced — second changeset with the same `chapter_id` raises `IntegrityError`.
  - DoD-5: TABLE_REGISTRY has `chapter_note_changesets` after `chapter_text_revisions` then `flags` after `chapter_note_changesets`, label sequence = canonical order restricted to present tables (codex absent → flags immediately follows), tuples bind correct models.
  - DoD-6: after init_db(), both tables in SQLModel.metadata + consistency report all-`ok`.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓

### Step 008 — tests (2026-07-25)
- `backend/tests/test_data_domain_codex.py` — covers DoD-1..DoD-6:
  - DoD-1: CodexEntry codec round-trip — `id`/`book_id`/`author_id` string↔int; `kind` via `.value`↔member for ALL THREE values (character/location/fact, parametrized); nullable `name` in BOTH the set shape (character, "Alice") and the null-for-fact shape (fact, None); `archived` bool (True in named shape, False in fact shape); nullable FK `modified_by` in both the set shape (→ emitted STRING → int) and null shape (None↔None); isoformat timestamps (set and None).
  - DoD-2: CodexEntryVersion codec round-trip — `id`/`entry_id`/`author_id` string↔int; nullable `name` (set and null shapes); `body` preserved; `kind` via `.value`↔member for all three (parametrized); `generation` plain int (3 in named shape, 1 in null shape) round-trips; isoformat `created_at` (set and None).
  - DoD-3: `db/codex_entries` create→get_by_id equal row (archived defaults False) + `list_by_book` filters to exactly one book's entries (two book_ids); `db/codex_entry_versions` create→get_by_id equal row + `list_by_entry` filters to exactly one entry's versions (two entry_ids).
  - DoD-4: the codex interleave — `codex_entries` then `codex_entry_versions` slotted BETWEEN `chapter_note_changesets` and `flags`; explicit ordering `chapter_note_changesets` < `codex_entries` < `codex_entry_versions` < `flags`; label sequence = canonical order restricted to present tables; tuples bind correct model classes.
  - DoD-5: vector deferral guard — `CodexEntry`/`CodexEntryVersion` not in VECTOR_SOURCE_REGISTRY model classes; no registered source's `__tablename__`/class-name is codex-related (trivially satisfied while registry is empty).
  - DoD-6: after init_db(), both tables in SQLModel.metadata + consistency report all-`ok`.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓

### Step 009 — tests (2026-07-25)
- `backend/tests/test_data_domain_chat.py` — covers DoD-1..DoD-5:
  - DoD-1: Chat codec round-trip — `id`/`book_id`/`author_id` string↔int, `title` preserved, `archived` bool in BOTH shapes (False in the active/populated-timestamp shape, True in the archived/None-timestamp shape), isoformat timestamps (set and None).
  - DoD-2: ChatMessage codec round-trip — `id`/`chat_id` string↔int, `role` a FREE STRING round-tripping verbatim (parametrized user/assistant/system/tool, no enum coercion), `content` preserved, `position` a plain int round-tripping as-is (parametrized 0/1/5, incl. boundary 0), isoformat `created_at` (set and None).
  - DoD-3: `db/chats` create→get_by_id equal row (archived defaults False) + `list_by_book` filters to exactly one book's chats (two book_ids); `db/chat_messages` create→get_by_id equal row + `list_by_chat` filters to exactly one chat's messages (two chat_ids).
  - DoD-4: FULL registry guard — `[e[0] for e in TABLE_REGISTRY]` equals the full 18-entry canonical order EXACTLY (order-sensitive), `len(set(labels)) == len(labels)` proves no duplicates, and the `chats`/`chat_messages` tuples bind the correct model classes.
  - DoD-5: after init_db(), `chats` and `chat_messages` in SQLModel.metadata + consistency report all-`ok`.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓

## Notes & Issues

_populated by the coder when worth saying_
