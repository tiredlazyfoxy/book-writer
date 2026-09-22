"""Tests for the memos data-domain wiring (feature 026, step 001): the JSONL
codec pair, the TABLE_REGISTRY entry and its position, and schema creation on a
freshly initialised database.

Bound to the frozen skeleton signatures (status.md -> Skeleton -> Step 001):
    class Memo(SQLModel, table=True)
        __tablename__ = "memos"; NO __table_args__;
        id: int (snowflake PK), book_id: int (FK books.id),
        user_id: int (FK users.id), body: str, ordinal: int,
        active: bool = True, archived: bool = False,
        created_at: datetime | None, modified_at: datetime | None
                                                      in app.models.memo
    def _memo_to_dict(memo: Memo) -> dict[str, object]
    def _dict_to_memo(data: dict[str, object]) -> Memo
    TABLE_REGISTRY gains ("memos", Memo, _memo_to_dict, _dict_to_memo) at
        index 11 — immediately after the `chapter_author_prompts` tuple and
        immediately before ("chapters", Chapter, ...)
                                            in app.services.db_import_export

Frozen exported dict keys for the codec pair (status.md -> Skeleton -> Step 001):
    {"id", "book_id", "user_id", "body", "ordinal", "active", "archived",
     "created_at", "modified_at"}
with `id` / `book_id` / `user_id` emitted as STRINGS and parsed
string-or-legacy-number, timestamps `.isoformat()` / `datetime.fromisoformat`,
both nullable.

Expected values come from the step spec (001.memo-table.md DoD +
001.context.md + context.md decision 1), never from implementation internals:
    - DoD-12 (root CLAUDE.md's same-change JSONL rule): the codec pair
      round-trips a row through dict and back with every field preserved; ids
      emit as STRINGS, and a dict carrying a NUMERIC id still parses. The
      falsy-but-legal values body="", active=False and archived=False survive
      as themselves and are never treated as absent (001.context.md ->
      "Gotcha — `""` is a value, and so is `false`");
    - DoD-13 (backend/book-domain.md -> registry order): TABLE_REGISTRY
      contains EXACTLY ONE `memos` entry, and it sits immediately after
      `chapter_author_prompts` and immediately before `chapters`;
    - DoD-14 (additive-schema rule): on a freshly initialised database the
      `memos` table exists and is queryable, and the consistency report comes
      back all-`ok` — the MODEL-REGISTRATION SEAM alone creates it, with no
      migration statement (the ADDITIVE MIGRATION SEAM stays `pass`).

Async tests use asyncio_mode = "auto"; the `db` fixture (conftest) supplies an
initialized throwaway temp-SQLite engine built by the real `init_engine` +
`init_db` pair. The codec (DoD-12) and registry (DoD-13) tests need no DB.

DoD-14's queryability is asserted with a plain SQL SELECT against the temp
database file the fixture initialised, so it depends on the registration seam
alone and not on the db/ module.
"""

import sqlite3
from datetime import datetime

from sqlmodel import SQLModel

from app.db import assistant_modes
from app.db.engine import DbConfig
from app.models.memo import Memo
from app.services import db_admin
from app.services.db_import_export import (
    TABLE_REGISTRY,
    _dict_to_memo,
    _memo_to_dict,
)

# The frozen export dict shape for the codec pair (status.md -> Skeleton).
MEMO_EXPORT_KEYS = {
    "id",
    "book_id",
    "user_id",
    "body",
    "ordinal",
    "active",
    "archived",
    "created_at",
    "modified_at",
}


# ---------------------------------------------------------------------------
# DoD-12 — codec round-trip (string ids, every field, legacy numeric ids)
# ---------------------------------------------------------------------------


# DoD-12: a fully-populated row round-trips through dict and back with every
# field preserved. `id` / `book_id` / `user_id` are emitted as STRINGS and parse
# back to the same ints; the body, the ordinal and both booleans pass through as
# themselves; both timestamps survive via isoformat. The exported dict carries
# exactly the frozen key set — no field silently dropped, none invented.
def test_codec_round_trips_every_field__DoD12():
    created_at = datetime(2026, 9, 15, 9, 0, 0)
    modified_at = datetime(2026, 9, 15, 9, 45, 0)
    memo = Memo(
        id=111222333,
        book_id=444555666,
        user_id=777888999,
        body="Never open a chapter with the weather.",
        ordinal=4,
        active=True,
        archived=False,
        created_at=created_at,
        modified_at=modified_at,
    )

    data = _memo_to_dict(memo)

    # Exactly the frozen export shape.
    assert set(data) == MEMO_EXPORT_KEYS

    # ids emitted as strings.
    assert data["id"] == "111222333"
    assert isinstance(data["id"], str)
    assert data["book_id"] == "444555666"
    assert isinstance(data["book_id"], str)
    assert data["user_id"] == "777888999"
    assert isinstance(data["user_id"], str)
    # Body, ordinal and flags as themselves.
    assert data["body"] == "Never open a chapter with the weather."
    assert data["ordinal"] == 4
    assert data["active"] is True
    assert data["archived"] is False
    # Timestamps via isoformat strings.
    assert data["created_at"] == created_at.isoformat()
    assert data["modified_at"] == modified_at.isoformat()

    restored = _dict_to_memo(data)

    # ids parse back to the same ints.
    assert restored.id == 111222333
    assert isinstance(restored.id, int)
    assert restored.book_id == 444555666
    assert isinstance(restored.book_id, int)
    assert restored.user_id == 777888999
    assert isinstance(restored.user_id, int)
    assert restored.body == "Never open a chapter with the weather."
    assert restored.ordinal == 4
    assert restored.active is True
    assert restored.archived is False
    assert restored.created_at == created_at
    assert restored.modified_at == modified_at


# DoD-12: the three falsy-but-legal values survive the round trip as
# themselves — body="" is an empty memo (never null), active=False is a
# switched-off memo and archived=False is the default. Null timestamps
# round-trip as null.
def test_codec_round_trips_falsy_values_and_null_timestamps__DoD12():
    memo = Memo(
        id=222333444,
        book_id=555666777,
        user_id=888999000,
        body="",
        ordinal=0,
        active=False,
        archived=False,
        created_at=None,
        modified_at=None,
    )

    data = _memo_to_dict(memo)

    # "" is exported as "", not as null.
    assert data["body"] == ""
    assert data["body"] is not None
    # Both booleans exported as themselves.
    assert data["active"] is False
    assert data["archived"] is False
    assert data["ordinal"] == 0
    # Null timestamps emitted as None.
    assert data["created_at"] is None
    assert data["modified_at"] is None

    restored = _dict_to_memo(data)

    assert restored.body == ""
    assert restored.body is not None
    assert restored.active is False
    assert restored.archived is False
    assert restored.ordinal == 0
    assert restored.created_at is None
    assert restored.modified_at is None


# DoD-12: an archived, still-active memo round-trips with both flags intact —
# the two axes are independent and the codec conflates neither.
def test_codec_round_trips_archived_row__DoD12():
    memo = Memo(
        id=444555666,
        book_id=777888999,
        user_id=111222333,
        body="put away but still switched on",
        ordinal=9,
        active=True,
        archived=True,
    )

    data = _memo_to_dict(memo)
    assert data["active"] is True
    assert data["archived"] is True

    restored = _dict_to_memo(data)
    assert restored.active is True
    assert restored.archived is True
    assert restored.body == "put away but still switched on"
    assert restored.ordinal == 9


# DoD-12: a dict carrying NUMERIC ids (a legacy, pre-snowflake archive shape)
# still parses, and every id lands on the correct int. The dict shape is taken
# from a genuine export so only the id values differ.
def test_codec_accepts_legacy_numeric_ids__DoD12():
    data = _memo_to_dict(
        Memo(
            id=333444555,
            book_id=666777888,
            user_id=999000111,
            body="legacy row",
            ordinal=2,
        )
    )
    data["id"] = 42
    data["book_id"] = 7
    data["user_id"] = 9

    restored = _dict_to_memo(data)

    assert restored.id == 42
    assert isinstance(restored.id, int)
    assert restored.book_id == 7
    assert isinstance(restored.book_id, int)
    assert restored.user_id == 9
    assert isinstance(restored.user_id, int)
    assert restored.body == "legacy row"
    assert restored.ordinal == 2


# ---------------------------------------------------------------------------
# DoD-13 — exactly one registry entry, between chapter_author_prompts and chapters
# ---------------------------------------------------------------------------


# DoD-13: TABLE_REGISTRY contains EXACTLY ONE `memos` entry, and it sits
# immediately after `chapter_author_prompts` and immediately before `chapters`
# — the position `backend/book-domain.md` fixes (FK-correct and keeping the
# per-author tables adjacent). The tuple binds the Memo model to the codec pair.
def test_table_registry_entry_position__DoD13():
    labels = [entry[0] for entry in TABLE_REGISTRY]

    # Exactly one entry, no duplicate.
    assert labels.count("memos") == 1

    index = labels.index("memos")
    # Immediately after chapter_author_prompts, immediately before chapters.
    assert labels[index - 1] == "chapter_author_prompts"
    assert labels[index + 1] == "chapters"

    # The tuple binds the model and the codec pair.
    entry = TABLE_REGISTRY[index]
    assert entry[1] is Memo
    assert entry[2] is _memo_to_dict
    assert entry[3] is _dict_to_memo


# ---------------------------------------------------------------------------
# DoD-14 — registration alone creates the table on a fresh database
# ---------------------------------------------------------------------------


# DoD-14: after the ordinary init_db() path (the `db` fixture) on a fresh
# database, `memos` exists in SQLModel.metadata AND is genuinely queryable — a
# SELECT over the created table succeeds and reports the frozen columns — so
# the model-registration seam by itself created it, with no migration statement.
async def test_table_exists_and_is_queryable_on_fresh_db__DoD14(db: DbConfig):
    assert "memos" in SQLModel.metadata.tables

    connection = sqlite3.connect(str(db.db_path))
    try:
        cursor = connection.execute(
            "SELECT id, book_id, user_id, body, ordinal, active, archived, "
            "created_at, modified_at FROM memos"
        )
        # The table is real and queryable — an empty table, freshly created.
        assert cursor.fetchall() == []
        assert {column[0] for column in cursor.description} == MEMO_EXPORT_KEYS
    finally:
        connection.close()


# DoD-14: the created table matches SQLModel.metadata — the consistency report
# reports `memos` as clean, and no other table drifts. A migration statement was
# neither needed nor added.
async def test_schema_drift_clean_after_registration__DoD14(db: DbConfig):
    # `assistant_modes` is the seed registry's single entry, so a present,
    # schema-clean but rowless table reports `seed-missing`; init_db() alone
    # leaves the DB schema-clean but not row-complete. This test's subject is a
    # fully consistent database, so the required rows are arranged first.
    await assistant_modes.seed_default_modes()

    report = await db_admin.build_consistency_report()
    by_name = {entry.name: entry for entry in report.tables}

    assert by_name["memos"].status == "ok"

    for entry in report.tables:
        assert entry.status == "ok", f"table {entry.name!r} not clean: {entry.status}"
