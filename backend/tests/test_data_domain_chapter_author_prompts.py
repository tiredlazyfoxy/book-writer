"""Tests for the chapter_author_prompts data-domain wiring (feature 014, step 001):
schema registration, the JSONL codec pair, the TABLE_REGISTRY entry, and the
preservation of the untouched `chapters` codec.

Bound to the frozen skeleton signatures (status.md -> Skeleton -> Step 001):
    class ChapterAuthorPrompt(SQLModel, table=True)
        __tablename__ = "chapter_author_prompts";
        UniqueConstraint(chapter_id, user_id);
        id: int (snowflake PK), chapter_id: int (FK chapters.id),
        user_id: int (FK users.id), system_prompt: str (required, NOT NULL),
        created_at: datetime | None, modified_at: datetime | None
                                        in app.models.chapter_author_prompt
    def _chapter_author_prompt_to_dict(prompt: ChapterAuthorPrompt) -> dict[str, object]
    def _dict_to_chapter_author_prompt(data: dict[str, object]) -> ChapterAuthorPrompt
    TABLE_REGISTRY gains
        ("chapter_author_prompts", ChapterAuthorPrompt, to_dict, from_dict)
        immediately after `book_author_prompts`
                                        in app.services.db_import_export
    def _chapter_to_dict / _dict_to_chapter (UNTOUCHED by this step)
                                        in app.services.db_import_export

Frozen exported dict keys for the new codec pair (status.md -> Skeleton -> Step 001):
    {"id", "chapter_id", "user_id", "system_prompt", "created_at", "modified_at"}
with `id` / `chapter_id` / `user_id` emitted as STRINGS and parsed
string-or-legacy-number.

Expected values come from the step spec (001.chapter-author-prompt-table.md DoD +
001.context.md + context.md decision D1), never from implementation internals:
    - DoD-6: on a freshly initialised database the `chapter_author_prompts` table
      exists and is queryable — the MODEL-REGISTRATION SEAM alone creates it, with
      no migration statement (the ADDITIVE MIGRATION SEAM stays `pass`). Asserted
      through the ordinary init_db() path (the `db` fixture), never a hand-built
      create_all over a hand-picked metadata subset (001.context.md -> "Testing");
    - DoD-7: the codec pair round-trips a row through dict and back with every
      field preserved; ids emit as strings; a dict carrying a NUMERIC id still
      parses (legacy archives); an empty-string prompt round-trips as "" and is
      never coerced to None (D1: `""` means "no prompt");
    - DoD-8: TABLE_REGISTRY contains exactly ONE `chapter_author_prompts` entry
      and it sits AFTER the `book_author_prompts` entry (asserted relative, not by
      absolute index — 001.context.md -> "TABLE_REGISTRY — the position and why");
    - DoD-12: the existing `chapters` codec still round-trips `system_prompt`
      unchanged — the dormant column stays exportable and importable (D1), so
      archives written before this feature still import.

Async tests use asyncio_mode = "auto"; the `db` fixture (conftest) supplies an
initialized throwaway temp-SQLite engine built by the real `init_engine` +
`init_db` pair. The codec (DoD-7, DoD-12) and registry (DoD-8) tests need no DB.

DoD-6's queryability is asserted with a plain SQL SELECT against the temp
database file the fixture initialised, so it depends on the registration seam
alone and not on the db/ module.
"""

import sqlite3
from datetime import datetime

from sqlmodel import SQLModel

from app.db import assistant_modes
from app.db.engine import DbConfig
from app.models.chapter import Chapter, ChapterState
from app.models.chapter_author_prompt import ChapterAuthorPrompt
from app.services import db_admin
from app.services.db_import_export import (
    TABLE_REGISTRY,
    _chapter_author_prompt_to_dict,
    _chapter_to_dict,
    _dict_to_chapter,
    _dict_to_chapter_author_prompt,
)

# The frozen export dict shape for the codec pair (status.md -> Skeleton).
PROMPT_EXPORT_KEYS = {
    "id",
    "chapter_id",
    "user_id",
    "system_prompt",
    "created_at",
    "modified_at",
}


# ---------------------------------------------------------------------------
# DoD-6 — registration alone creates the table on a fresh database
# ---------------------------------------------------------------------------


# DoD-6: after the ordinary init_db() path (the `db` fixture) on a fresh database,
# `chapter_author_prompts` exists in SQLModel.metadata AND is genuinely queryable
# — a SELECT over the created table succeeds and reports the frozen columns — so
# the model-registration seam by itself created it, with no migration statement.
async def test_table_exists_and_is_queryable_on_fresh_db__DoD6(db: DbConfig):
    assert "chapter_author_prompts" in SQLModel.metadata.tables

    connection = sqlite3.connect(str(db.db_path))
    try:
        cursor = connection.execute(
            "SELECT id, chapter_id, user_id, system_prompt, created_at, modified_at "
            "FROM chapter_author_prompts"
        )
        # The table is real and queryable — an empty table, freshly created.
        assert cursor.fetchall() == []
        assert {column[0] for column in cursor.description} == PROMPT_EXPORT_KEYS
    finally:
        connection.close()


# DoD-6: the created table matches SQLModel.metadata — the FEAT-005 consistency
# report reports `chapter_author_prompts` as clean, and no other table drifts.
# A migration statement was neither needed nor added.
async def test_schema_drift_clean_after_registration__DoD6(db: DbConfig):
    # Feedback round 1, F1: `assistant_modes` is the seed registry's single
    # entry, so a present, schema-clean but rowless table now reports
    # `seed-missing` — init_db() alone leaves the DB schema-clean but not
    # row-complete. This test's subject is a fully consistent database, so the
    # required rows are arranged first; every per-table assertion below is
    # unchanged.
    await assistant_modes.seed_default_modes()

    report = await db_admin.build_consistency_report()
    by_name = {entry.name: entry for entry in report.tables}

    assert by_name["chapter_author_prompts"].status == "ok"

    for entry in report.tables:
        assert entry.status == "ok", f"table {entry.name!r} not clean: {entry.status}"


# ---------------------------------------------------------------------------
# DoD-7 — codec pair round-trip (string ids, every field, legacy numeric ids)
# ---------------------------------------------------------------------------


# DoD-7: a fully-populated row round-trips through dict and back with every field
# preserved. `id` / `chapter_id` / `user_id` are emitted as STRINGS and parse back
# to the same ints; `system_prompt` passes through verbatim; both timestamps
# survive via isoformat. The exported dict carries exactly the frozen key set — no
# field silently dropped, none invented.
def test_codec_round_trips_every_field__DoD7():
    created_at = datetime(2026, 7, 29, 9, 0, 0)
    modified_at = datetime(2026, 7, 29, 9, 45, 0)
    prompt = ChapterAuthorPrompt(
        id=111222333,
        chapter_id=444555666,
        user_id=777888999,
        system_prompt="Keep this chapter's prose terse.",
        created_at=created_at,
        modified_at=modified_at,
    )

    data = _chapter_author_prompt_to_dict(prompt)

    # Exactly the frozen export shape.
    assert set(data) == PROMPT_EXPORT_KEYS

    # ids emitted as strings.
    assert data["id"] == "111222333"
    assert isinstance(data["id"], str)
    assert data["chapter_id"] == "444555666"
    assert isinstance(data["chapter_id"], str)
    assert data["user_id"] == "777888999"
    assert isinstance(data["user_id"], str)
    # prompt text verbatim.
    assert data["system_prompt"] == "Keep this chapter's prose terse."
    # timestamps via isoformat strings.
    assert data["created_at"] == created_at.isoformat()
    assert data["modified_at"] == modified_at.isoformat()

    restored = _dict_to_chapter_author_prompt(data)

    # ids parse back to the same ints.
    assert restored.id == 111222333
    assert isinstance(restored.id, int)
    assert restored.chapter_id == 444555666
    assert isinstance(restored.chapter_id, int)
    assert restored.user_id == 777888999
    assert isinstance(restored.user_id, int)
    assert restored.system_prompt == "Keep this chapter's prose terse."
    assert restored.created_at == created_at
    assert restored.modified_at == modified_at


# DoD-7: an EMPTY-STRING prompt round-trips as "" — the codec never coerces it to
# None (or the reverse), because "" is the value D1 gives to "no prompt". Null
# timestamps round-trip as null.
def test_codec_round_trips_empty_prompt_and_null_timestamps__DoD7():
    prompt = ChapterAuthorPrompt(
        id=222333444,
        chapter_id=555666777,
        user_id=888999000,
        system_prompt="",
        created_at=None,
        modified_at=None,
    )

    data = _chapter_author_prompt_to_dict(prompt)

    # "" is exported as "", not as null.
    assert data["system_prompt"] == ""
    assert data["system_prompt"] is not None
    # Null timestamps emitted as None.
    assert data["created_at"] is None
    assert data["modified_at"] is None

    restored = _dict_to_chapter_author_prompt(data)

    # "" is imported as "", not as None.
    assert restored.system_prompt == ""
    assert restored.system_prompt is not None
    assert restored.created_at is None
    assert restored.modified_at is None


# DoD-7: a dict carrying NUMERIC ids (a legacy, pre-snowflake archive shape) still
# parses, and every id lands on the correct int. The dict shape is taken from a
# genuine export so only the id values differ.
def test_codec_accepts_legacy_numeric_ids__DoD7():
    data = _chapter_author_prompt_to_dict(
        ChapterAuthorPrompt(
            id=333444555,
            chapter_id=666777888,
            user_id=999000111,
            system_prompt="legacy row",
        )
    )
    data["id"] = 42
    data["chapter_id"] = 7
    data["user_id"] = 9

    restored = _dict_to_chapter_author_prompt(data)

    assert restored.id == 42
    assert isinstance(restored.id, int)
    assert restored.chapter_id == 7
    assert isinstance(restored.chapter_id, int)
    assert restored.user_id == 9
    assert isinstance(restored.user_id, int)
    assert restored.system_prompt == "legacy row"


# ---------------------------------------------------------------------------
# DoD-8 — exactly one registry entry, positioned after book_author_prompts
# ---------------------------------------------------------------------------


# DoD-8: TABLE_REGISTRY contains EXACTLY ONE `chapter_author_prompts` entry and it
# sits AFTER the `book_author_prompts` entry (a relative assertion, so a later
# insertion elsewhere in the list cannot fail it for the wrong reason). The tuple
# binds the ChapterAuthorPrompt model together with the codec pair.
def test_table_registry_entry_position__DoD8():
    labels = [entry[0] for entry in TABLE_REGISTRY]

    # Exactly one entry, no duplicate.
    assert labels.count("chapter_author_prompts") == 1

    # It sits after book_author_prompts.
    assert labels.index("book_author_prompts") < labels.index("chapter_author_prompts")

    # The tuple binds the model and the codec pair.
    entry = TABLE_REGISTRY[labels.index("chapter_author_prompts")]
    assert entry[1] is ChapterAuthorPrompt
    assert entry[2] is _chapter_author_prompt_to_dict
    assert entry[3] is _dict_to_chapter_author_prompt


# ---------------------------------------------------------------------------
# DoD-12 — the chapters codec still round-trips system_prompt (dormant column)
# ---------------------------------------------------------------------------


def _make_chapter(system_prompt: str | None) -> Chapter:
    """A fully-populated Chapter differing only in `system_prompt`."""
    return Chapter(
        id=101010101,
        book_id=202020202,
        ordinal=1,
        title="Dormant Column Chapter",
        state=ChapterState.planned,
        sketch="a sketch",
        text="",
        system_prompt=system_prompt,
    )


# DoD-12: the `chapters` codec is untouched by this step — `_chapter_to_dict`
# still emits `system_prompt` and `_dict_to_chapter` still reads it back, so
# archives written before this feature keep importing (D1). A populated prompt,
# "" and None all round-trip.
def test_chapter_codec_still_round_trips_system_prompt__DoD12():
    populated = _chapter_to_dict(_make_chapter("A legacy chapter-scoped prompt"))
    assert populated["system_prompt"] == "A legacy chapter-scoped prompt"
    assert (
        _dict_to_chapter(populated).system_prompt == "A legacy chapter-scoped prompt"
    )

    blank = _chapter_to_dict(_make_chapter(""))
    assert blank["system_prompt"] == ""
    assert _dict_to_chapter(blank).system_prompt == ""

    absent = _chapter_to_dict(_make_chapter(None))
    assert absent["system_prompt"] is None
    assert _dict_to_chapter(absent).system_prompt is None
