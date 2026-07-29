"""Tests for the book_author_prompts data-domain wiring (feature 021, step 001):
schema registration, the JSONL codec pair, and the TABLE_REGISTRY entry.

Bound to the frozen skeleton signatures (status.md -> Skeleton -> Step 001):
    class BookAuthorPrompt(SQLModel, table=True)
        __tablename__ = "book_author_prompts";
        UniqueConstraint(book_id, user_id);
        id: int (snowflake PK), book_id: int (FK books.id),
        user_id: int (FK users.id), system_prompt: str (required, NOT NULL),
        created_at: datetime | None, modified_at: datetime | None
                                             in app.models.book_author_prompt
    async def create(row: BookAuthorPrompt) -> BookAuthorPrompt
    async def get_by_book_and_user(book_id: int, user_id: int)
        -> BookAuthorPrompt | None           in app.db.book_author_prompts
    def _book_author_prompt_to_dict(prompt: BookAuthorPrompt) -> dict[str, object]
    def _dict_to_book_author_prompt(data: dict[str, object]) -> BookAuthorPrompt
    TABLE_REGISTRY gains
        ("book_author_prompts", BookAuthorPrompt, to_dict, from_dict)
        immediately after `book_members`, before `chapters`
                                             in app.services.db_import_export
    def _book_to_dict / _dict_to_book (UNTOUCHED by this step)
                                             in app.services.db_import_export

Frozen exported dict keys for the codec pair (status.md -> Skeleton -> Step 001):
    {"id", "book_id", "user_id", "system_prompt", "created_at", "modified_at"}
with `id` / `book_id` / `user_id` emitted as STRINGS and parsed
string-or-legacy-number.

Expected values come from the step spec (001.author-prompt-table.md DoD +
001.context.md + context.md), never from implementation internals:
    - DoD-6: on a freshly initialised database the `book_author_prompts` table
      exists and is queryable — the MODEL-REGISTRATION SEAM alone creates it,
      with no migration statement (the ADDITIVE MIGRATION SEAM stays `pass`);
    - DoD-7: the codec pair round-trips a row through dict and back with every
      field preserved; ids emit as strings; a dict carrying a NUMERIC id still
      parses (legacy archives); an empty-string prompt round-trips as "" and is
      never coerced to None (001.context.md -> "Gotcha");
    - DoD-8: TABLE_REGISTRY contains exactly ONE `book_author_prompts` entry and
      it sits after `book_members` (immediately after it, before `chapters` —
      context.md -> "TABLE_REGISTRY — the shape and the position");
    - DoD-9: Book's own codec still round-trips `system_prompt` unchanged — the
      dormant column stays exportable and importable (context.md -> decision 2).

Async tests use asyncio_mode = "auto"; the `db` fixture (conftest) supplies an
initialized throwaway temp-SQLite engine with the registered tables created.
The codec (DoD-7, DoD-9) and registry (DoD-8) tests need no DB.
"""

from datetime import datetime

from sqlmodel import SQLModel

from app.db import book_author_prompts
from app.db.engine import DbConfig
from app.models.book import Book, BookState, CollaborationMode, Visibility
from app.models.book_author_prompt import BookAuthorPrompt
from app.services import db_admin
from app.services.db_import_export import (
    TABLE_REGISTRY,
    _book_author_prompt_to_dict,
    _book_to_dict,
    _dict_to_book,
    _dict_to_book_author_prompt,
)

# The frozen export dict shape for the codec pair (status.md -> Skeleton).
PROMPT_EXPORT_KEYS = {
    "id",
    "book_id",
    "user_id",
    "system_prompt",
    "created_at",
    "modified_at",
}


# ---------------------------------------------------------------------------
# DoD-6 — registration alone creates the table on a fresh database
# ---------------------------------------------------------------------------


# DoD-6: after init_db() on a fresh database (the `db` fixture),
# `book_author_prompts` exists in SQLModel.metadata AND is genuinely queryable —
# a row inserted through the db/ module is read back — so the registration seam
# by itself created the table, with no migration statement needed.
async def test_table_exists_and_is_queryable_on_fresh_db__DoD6(db: DbConfig):
    tables = SQLModel.metadata.tables
    assert "book_author_prompts" in tables

    # Queryable: an empty lookup succeeds against a real, present table...
    assert await book_author_prompts.get_by_book_and_user(1, 2) is None

    # ...and a row inserted into it is read back.
    await book_author_prompts.create(
        BookAuthorPrompt(book_id=1, user_id=2, system_prompt="seam check")
    )
    fetched = await book_author_prompts.get_by_book_and_user(1, 2)
    assert fetched is not None
    assert fetched.system_prompt == "seam check"


# DoD-6: the created table matches SQLModel.metadata — the FEAT-005 consistency
# report reports `book_author_prompts` as clean, and no other table drifts.
async def test_schema_drift_clean_after_registration__DoD6(db: DbConfig):
    report = await db_admin.build_consistency_report()
    by_name = {entry.name: entry for entry in report.tables}

    assert by_name["book_author_prompts"].status == "ok"

    for entry in report.tables:
        assert entry.status == "ok", f"table {entry.name!r} not clean: {entry.status}"


# ---------------------------------------------------------------------------
# DoD-7 — codec pair round-trip (string ids, every field, legacy numeric ids)
# ---------------------------------------------------------------------------


# DoD-7: a fully-populated row round-trips through dict and back with every
# field preserved. `id` / `book_id` / `user_id` are emitted as STRINGS and parse
# back to the same ints; `system_prompt` passes through verbatim; both
# timestamps survive via isoformat. The exported dict carries exactly the frozen
# key set — no field silently dropped, none invented.
def test_codec_round_trips_every_field__DoD7():
    created_at = datetime(2026, 7, 29, 9, 0, 0)
    modified_at = datetime(2026, 7, 29, 9, 45, 0)
    prompt = BookAuthorPrompt(
        id=111222333,
        book_id=444555666,
        user_id=777888999,
        system_prompt="Keep the prose terse.",
        created_at=created_at,
        modified_at=modified_at,
    )

    data = _book_author_prompt_to_dict(prompt)

    # Exactly the frozen export shape.
    assert set(data) == PROMPT_EXPORT_KEYS

    # ids emitted as strings.
    assert data["id"] == "111222333"
    assert isinstance(data["id"], str)
    assert data["book_id"] == "444555666"
    assert isinstance(data["book_id"], str)
    assert data["user_id"] == "777888999"
    assert isinstance(data["user_id"], str)
    # prompt text verbatim.
    assert data["system_prompt"] == "Keep the prose terse."
    # timestamps via isoformat strings.
    assert data["created_at"] == created_at.isoformat()
    assert data["modified_at"] == modified_at.isoformat()

    restored = _dict_to_book_author_prompt(data)

    # ids parse back to the same ints.
    assert restored.id == 111222333
    assert isinstance(restored.id, int)
    assert restored.book_id == 444555666
    assert isinstance(restored.book_id, int)
    assert restored.user_id == 777888999
    assert isinstance(restored.user_id, int)
    assert restored.system_prompt == "Keep the prose terse."
    assert restored.created_at == created_at
    assert restored.modified_at == modified_at


# DoD-7: an EMPTY-STRING prompt round-trips as "" — the codec never coerces it
# to None (or the reverse). Null timestamps round-trip as null.
def test_codec_round_trips_empty_prompt_and_null_timestamps__DoD7():
    prompt = BookAuthorPrompt(
        id=222333444,
        book_id=555666777,
        user_id=888999000,
        system_prompt="",
        created_at=None,
        modified_at=None,
    )

    data = _book_author_prompt_to_dict(prompt)

    # "" is exported as "", not as null.
    assert data["system_prompt"] == ""
    assert data["system_prompt"] is not None
    # Null timestamps emitted as None.
    assert data["created_at"] is None
    assert data["modified_at"] is None

    restored = _dict_to_book_author_prompt(data)

    # "" is imported as "", not as None.
    assert restored.system_prompt == ""
    assert restored.system_prompt is not None
    assert restored.created_at is None
    assert restored.modified_at is None


# DoD-7: a dict carrying NUMERIC ids (a legacy, pre-snowflake archive shape)
# still parses, and every id lands on the correct int. The dict shape is taken
# from a genuine export so only the id values differ.
def test_codec_accepts_legacy_numeric_ids__DoD7():
    data = _book_author_prompt_to_dict(
        BookAuthorPrompt(
            id=333444555,
            book_id=666777888,
            user_id=999000111,
            system_prompt="legacy row",
        )
    )
    data["id"] = 42
    data["book_id"] = 7
    data["user_id"] = 9

    restored = _dict_to_book_author_prompt(data)

    assert restored.id == 42
    assert isinstance(restored.id, int)
    assert restored.book_id == 7
    assert isinstance(restored.book_id, int)
    assert restored.user_id == 9
    assert isinstance(restored.user_id, int)
    assert restored.system_prompt == "legacy row"


# ---------------------------------------------------------------------------
# DoD-8 — exactly one registry entry, positioned after book_members
# ---------------------------------------------------------------------------


# DoD-8: TABLE_REGISTRY contains EXACTLY ONE `book_author_prompts` entry, it
# sits after `book_members` (immediately after it and before `chapters` — the
# FK/import order position fixed by context.md), and the tuple binds the
# BookAuthorPrompt model together with the codec pair.
def test_table_registry_entry_position__DoD8():
    labels = [entry[0] for entry in TABLE_REGISTRY]

    # Exactly one entry, no duplicate.
    assert labels.count("book_author_prompts") == 1

    # It sits after book_members — immediately after, and before chapters.
    assert labels.index("book_members") < labels.index("book_author_prompts")
    assert labels.index("book_author_prompts") == labels.index("book_members") + 1
    assert labels.index("book_author_prompts") < labels.index("chapters")

    # The tuple binds the model and the codec pair.
    entry = TABLE_REGISTRY[labels.index("book_author_prompts")]
    assert entry[1] is BookAuthorPrompt
    assert entry[2] is _book_author_prompt_to_dict
    assert entry[3] is _dict_to_book_author_prompt


# ---------------------------------------------------------------------------
# DoD-9 — Book's codec still round-trips system_prompt (the dormant column)
# ---------------------------------------------------------------------------


def _make_book(system_prompt: str) -> Book:
    """A fully-populated Book differing only in `system_prompt`."""
    return Book(
        id=101010101,
        title="Dormant Column Book",
        description="A description",
        owner_id=202020202,
        collaboration_mode=CollaborationMode.free,
        visibility=Visibility.private,
        state=BookState.active,
        system_prompt=system_prompt,
        active_notes="notes",
    )


# DoD-9: Book's codec is untouched by this step — `_book_to_dict` still emits
# `system_prompt` and `_dict_to_book` still reads it back, so archives written
# before this feature keep importing. Both a populated prompt and "" round-trip.
def test_book_codec_still_round_trips_system_prompt__DoD9():
    populated = _book_to_dict(_make_book("A legacy book-wide prompt"))
    assert populated["system_prompt"] == "A legacy book-wide prompt"
    assert _dict_to_book(populated).system_prompt == "A legacy book-wide prompt"

    blank = _book_to_dict(_make_book(""))
    assert blank["system_prompt"] == ""
    assert _dict_to_book(blank).system_prompt == ""
