# Feature 008 — data-domain (feature-wide context)

## Goal & scope

Stand up the **backend persistence data floor** for the whole book domain plus
the FEAT-020 assistant-config tables. Backend-only, data-layer-only. Nothing
user-visible ships; this is the floor every later domain feature stands on.

Deliverables across the steps:
1. **16 new SQLModel `table=True` models** — 5 FEAT-020 config + 11 book-domain
   — each drawn **whole** per the architecture (later-stage columns land now,
   nullable and unused).
2. **One session-free `db/` module per entity**, mirroring `db/users.py` /
   `db/llm_servers.py`. Minimal surface: `create(row)->row` and
   `get_by_id(id)->row|None`, plus a parent-scoped list read **only** where it
   is the obvious primary read (named per step). **No speculative
   update/archive/business-logic functions** — those belong to features 009+.
3. **A JSONL `to_dict`/`from_dict` codec pair per table** plus one
   `TABLE_REGISTRY` tuple per table, in `services/db_import_export.py`, in the
   canonical FK order below.
4. **Register every new model module** in `db/engine.py::_register_models()`.
5. **Seed the five `AssistantMode` rows** at first-run setup (idempotent),
   wired into `services/setup.py::create_database`.

## Out of scope (do not plan any of it)

- Any route, HTTP endpoint, DTO/schema under `models/schemas/`, or service
  business logic — **except the two sanctioned touch-points**:
  `services/setup.py` (the seed hook, step 003) and
  `services/db_import_export.py` (codecs + registry, every step).
- **All vector / LanceDB work.** `CodexEntry` is **NOT** registered as a vector
  source in this feature. No `VECTOR_SOURCE_REGISTRY` / `rebuild_index` /
  `services/embedding.py` / chunker work. The `codex_entries` **table** is still
  created (an ordinary data class); only its vector indexing defers to
  `013.codex`. **Do not touch `db/vector.py`.** (This narrows the wording in
  `brief.md`, which predates the user's deferral decision — the deferral is
  authoritative and recorded in `outcome.md`.)
- Incremental index maintenance, the FEAT-020 admin CRUD/editor (→ `012`), the
  `TOOL_REGISTRY` catalogue (code, not a table; belongs to `011`/`013`).

## Architecture ground truth (read these; cite the ids they attribute)

- `docs/architecture/domain-model.md` — index; conventions; "Two registry
  obligations"; "Stage-4 columns land at Stage 2".
- `docs/architecture/domain-book.md`, `domain-chapter.md`,
  `domain-continuity.md`, `domain-codex.md`, `domain-chat.md` — per-entity
  field tables. **Realizes** headers there carry the FEAT/UC ids to cite.
- `docs/architecture/assistant-config.md` — the five FEAT-020 tables (config
  model section only; the runtime slice is out of scope here). FEAT-020,
  UC-095/096/097, US-110..114.
- `docs/architecture/backend/book-domain.md` — the canonical `TABLE_REGISTRY`
  order, the Stage-4-columns rule, "no new drift code".
- `docs/architecture/backend/persistence.md` — codec mechanics, id-as-string,
  `init_db` lifecycle, import UPSERT.

## Exemplar files to replicate (the ONLY window into existing code)

Every step follows these live patterns exactly:

- **Model** — `backend/app/models/user.py`: `class X(SQLModel, table=True)`
  with explicit `__tablename__`. Snowflake PK
  `id: int = Field(default_factory=generate_id, primary_key=True)`
  (`from app.ids import generate_id`). Nullable `f: T | None = Field(default=None)`;
  required no-default = bare annotation; single-column unique
  `Field(unique=True, index=True)`; bool default `b: bool = False`; enums
  `class E(str, enum.Enum)`; timestamps `created_at: datetime | None = Field(default=None)`
  / `modified_at` (app-set, nullable). **No shared timestamp mixin — each table
  declares its own.**
- **DB module** — `backend/app/db/users.py`: every function `async`, opens its
  own session (`session = await get_standalone_session()` then
  `async with session:`; `from app.db.engine import get_standalone_session`,
  `from sqlmodel import select`). `create`: add / commit / refresh / return row.
  `get_by_id`: `select(...).where(X.id == id)` → `.one_or_none()`. `list`:
  `.where(X.<fk> == parent_id)` → `list(result.all())`. **No session / ORM type
  leaves the module.**
- **Codec** — `backend/app/services/db_import_export.py`: per table
  `_x_to_dict(row) -> dict[str, object]` and `_dict_to_x(data) -> X`. `to_dict`
  emits `"id": str(row.id)`, enums `e.value`, datetimes `dt.isoformat() if dt
  else None`, nullables pass through. `from_dict` parses
  `id=int(raw) if raw is not None else None` (string-or-legacy-number), enums
  `E(data["..."])`, datetimes `datetime.fromisoformat(x) if x else None`,
  optionals via `data.get(k, default)`. Register a tuple
  `("<tablename>", ModelClass, _x_to_dict, _dict_to_x)` (type alias
  `RegistryEntry`) in `TABLE_REGISTRY`. `export_all` / `import_all` iterate
  generically; `BATCH_SIZE=100`; `import_all` calls `init_db()` first and
  `run_vector_rebuild()` last (both unchanged — do not modify them).
- **Register seam** — `backend/app/db/engine.py::_register_models()`: currently
  imports `app.models.user`, `app.models.llm_server`. Add one import line per
  new model module (`# noqa: F401`). **Required in the same step the model is
  added**, or `create_all` / drift won't see the table.

## First-of-kind conventions (no existing precedent — these steps set them)

- **Foreign keys**: bare column with `Field(foreign_key="<tablename>.<col>")`
  on `int` (or nullable `int | None`). **Do NOT use SQLModel `Relationship()`** —
  the db layer is session-free with no ORM navigation.
- **Composite unique**:
  `__table_args__ = (UniqueConstraint("col_a", "col_b", name="uq_..."),)`
  (`from sqlalchemy import UniqueConstraint`).
- **`AssistantMode` natural-key PK**: `key: str = Field(primary_key=True)` — NOT
  a snowflake, no `generate_id`. Its codec emits/parses `key` **verbatim**
  (never through `int()`). A deliberate, documented exception
  (`assistant-config.md` → "Why the primary key is the `key` string").

## The canonical `TABLE_REGISTRY` order (backend/book-domain.md)

```
users, llm_servers,                                                        # existing
assistant_modes, sub_agents, mode_tools, subagent_tools, mode_subagents,   # FEAT-020 config
books, book_members,
chapters, chapter_changes, chapter_text_revisions, chapter_note_changesets,
codex_entries, codex_entry_versions,
flags,
chats, chat_messages
```

The FEAT-020 config block is **instance-global** (same class as
users/llm_servers) and goes **before `books`**. Note `flags` sits **after**
`codex_entry_versions` even though its only FK is to `chapters` — follow this
order exactly.

**Registry invariant every step's registry-order test asserts** (the
"canonical-restricted" rule): the sequence of tablenames in `TABLE_REGISTRY`
equals the canonical order **restricted to the tables registered so far** —
i.e. filtering the canonical list down to the currently-present names must
reproduce the current `TABLE_REGISTRY` sequence exactly. This holds at every
intermediate step (each new entry's FK-parents precede it, relative order
preserved) and equals the full 19-entry canonical order once step 009 lands.
The insertion **position** matters: a step must slot its tuples at their
canonical positions, not merely append (see step 007 / 008 context for the
`flags` ↔ codex interleave this forces).

## Stage-4-columns-land-now rule

Later-stage columns are created **with their tables**, nullable and unused:
`Chapter.state = closing`, `Chapter.summary_status`, `Book.moderation_reason` /
`moderated_by` / `moderated_at`, and the whole `chapter_note_changesets` table
with its `status`. Reason: SQLite `ADD COLUMN` cannot be `NOT NULL` without a
default on a populated table, so landing them now makes later stages pure
behaviour with no DDL. See `domain-model.md` / `domain-chapter.md`.

## Drift is free (no new code)

FEAT-005's consistency report (`db/schema.py` + `services/db_admin.py`) compares
the live DB against `SQLModel.metadata`. Newly-declared tables are covered with
**no new drift code** — a per-step DoD asserts the report is clean after
`init_db()`. These modules are read-only from this feature (tests may call the
report; steps never edit them).

## Files touched across steps

- `backend/app/models/*.py` — one model file per entity (`chat.py` holds both
  `Chat` and `ChatMessage`); step-local, disjoint across steps.
- `backend/app/db/*.py` — one db module per table; step-local.
- `backend/app/services/db_import_export.py` — **shared**: every step appends
  codec pairs + registry tuples at canonical positions.
- `backend/app/db/engine.py` — **shared**: every step adds `_register_models()`
  import lines.
- `backend/app/services/setup.py` — **step 003 only** (seed hook).

Overlapping shared-file scope across sequential steps is expected and allowed;
each step's Source list bounds *that* step's coder.

## Test harness

Backend tests: `cd backend && .venv/Scripts/python -m pytest`. No separate
backend typecheck. Tests mock nothing DB-wise beyond pointing at a throwaway DB
via the existing `DbConfig(db_path=...)` / `init_engine` harness pattern; the
`init_db()` lifecycle creates tables before use. The FEAT-005 consistency
report and `db/vector.py`'s `VECTOR_SOURCE_REGISTRY` are inspected read-only by
tests where a DoD calls for it.
