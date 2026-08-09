"""The additive migration seam — `init_db()` reaches an EXISTING database (F1).

Feedback round 1, item **F1** (`docs/plans/024.chat-agent-loop/feedback.md`),
defending feature 024's DoD-2 (the assistant `ChatMessage` carries a persisted
`tool_trace` column).

Bound to the harvested signatures (implementation source deliberately unread):

    app.db.engine:
        async def init_engine(config: DbConfig) -> None
        async def init_db() -> None
    (reused, unchanged) app.db.chat_messages.create / list_by_chat_ordered
    (reused, unchanged) app.models.chat.ChatMessage

Expected behaviour comes from the SPEC ONLY — F1's `Expected` clause:

    "adding a column to a model must also reach databases that already exist ...
     After the fix, `init_db()` run against a database whose `chat_messages`
     table predates 024 must leave that table carrying a nullable `tool_trace`
     column, and running it again must change nothing."

plus F1's `Constraints`: `async def init_db() -> None` is frozen, first-run
behaviour on a fresh database is preserved, and the seam is **idempotent** — a
second run is a no-op, never an error.

The reported user-visible symptom is that EVERY `chat_messages` insert fails
against a pre-024 database (`table chat_messages has no column named
tool_trace`), on a plain **user** message — so the symptom, not merely the DDL,
is what these tests assert.

The pre-024 database is built by creating today's schema and then removing the
`tool_trace` column with plain SQL through the stdlib `sqlite3` driver — no
implementation internal is touched, only the on-disk shape a database created
before feature 024 has.

`asyncio_mode = "auto"`; these tests build their own temp databases (rather than
leaning on the `db` fixture) because the point of the exercise is what happens on
a *second* boot against a file that already exists.
"""

import sqlite3
from pathlib import Path

import pytest

from app.db import chat_messages
from app.db.engine import DbConfig, init_db, init_engine
from app.models.chat import ChatMessage

TABLE = "chat_messages"
COLUMN = "tool_trace"


# --- helpers: on-disk inspection and pre-024 database construction -----------


def _columns(db_path: Path) -> list[str]:
    """Column names of `chat_messages`, read straight from the SQLite file."""
    connection = sqlite3.connect(db_path)
    try:
        rows = connection.execute(f"PRAGMA table_info({TABLE})").fetchall()
    finally:
        connection.close()
    return [row[1] for row in rows]


def _column_is_nullable(db_path: Path) -> bool:
    """True when `chat_messages.tool_trace` carries no NOT NULL constraint."""
    connection = sqlite3.connect(db_path)
    try:
        rows = connection.execute(f"PRAGMA table_info({TABLE})").fetchall()
    finally:
        connection.close()
    matches = [row for row in rows if row[1] == COLUMN]
    assert len(matches) == 1, f"expected exactly one {COLUMN} column, got {matches}"
    # PRAGMA table_info columns: (cid, name, type, notnull, dflt_value, pk)
    return matches[0][3] == 0


async def _make_pre_024_database(tmp_path: Path, name: str) -> DbConfig:
    """Build a database whose `chat_messages` table predates feature 024.

    Creates today's schema, then drops `tool_trace` back off the table, which is
    exactly the shape a database created before 024 has on disk. Returns the
    `DbConfig` pointing at it, with the engine freshly bound to that file — i.e.
    the state a process boot against a pre-existing database starts from.
    """
    config = DbConfig(db_path=tmp_path / name)
    await init_engine(config)
    await init_db()

    # Sanity on the fixture itself (not on behaviour under test): today's model
    # emits the column, and after this surgery the file genuinely lacks it.
    assert COLUMN in _columns(config.db_path)

    assert sqlite3.sqlite_version_info >= (3, 35, 0), (
        "ALTER TABLE ... DROP COLUMN requires SQLite 3.35+; "
        f"this interpreter bundles {sqlite3.sqlite_version}"
    )
    connection = sqlite3.connect(config.db_path)
    try:
        connection.execute(f"ALTER TABLE {TABLE} DROP COLUMN {COLUMN}")
        connection.commit()
    finally:
        connection.close()

    assert COLUMN not in _columns(config.db_path), (
        "the pre-024 fixture database still carries the column it must lack"
    )

    # Re-bind the engine to the now-pre-024 file: a fresh process booting
    # against an existing database is precisely the reported scenario.
    await init_engine(config)
    return config


async def _insert_user_message(chat_id: int, content: str) -> None:
    """The plain-user-message insert F1 reports as failing end to end."""
    await chat_messages.create(
        ChatMessage(chat_id=chat_id, role="user", content=content, position=0)
    )


# ---------------------------------------------------------------------------
# F1 — init_db() must carry an added column onto an existing database
# ---------------------------------------------------------------------------


async def test_init_db_adds_tool_trace_to_pre_024_database__F1(tmp_path: Path):
    # F1 (Expected): init_db() run against a database whose chat_messages table
    # predates 024 must leave that table carrying a NULLABLE tool_trace column...
    config = await _make_pre_024_database(tmp_path, "pre024_add.db")

    await init_db()

    assert COLUMN in _columns(config.db_path)
    assert _column_is_nullable(config.db_path)

    # ...and the reported symptom must be gone: a plain user message inserts
    # through the normal path instead of raising OperationalError.
    await _insert_user_message(9101, "hello from an existing database")

    listed = await chat_messages.list_by_chat_ordered(9101)
    assert [m.content for m in listed] == ["hello from an existing database"]
    # The migrated column is real storage, not merely a name in the schema: it
    # reads back as NULL for a message that carried no trace...
    assert listed[0].tool_trace is None

    # ...and round-trips a written value.
    await chat_messages.create(
        ChatMessage(
            chat_id=9101,
            role="assistant",
            content="answer",
            position=1,
            tool_trace='{"entries": []}',
        )
    )
    reloaded = await chat_messages.list_by_chat_ordered(9101)
    assert [m.tool_trace for m in reloaded] == [None, '{"entries": []}']


async def test_migration_seam_is_idempotent__F1(tmp_path: Path):
    # F1 (Expected + Constraints): "running it again must change nothing" — the
    # seam must be a no-op on a second run, never an error.
    config = await _make_pre_024_database(tmp_path, "pre024_idempotent.db")

    await init_db()
    await _insert_user_message(9201, "written after the first migration")

    # A second and third run raise nothing...
    await init_db()
    await init_db()

    # ...leave the column present exactly once, still nullable...
    assert _columns(config.db_path).count(COLUMN) == 1
    assert _column_is_nullable(config.db_path)

    # ...leave already-written data intact...
    listed = await chat_messages.list_by_chat_ordered(9201)
    assert [m.content for m in listed] == ["written after the first migration"]

    # ...and leave inserts working.
    await chat_messages.create(
        ChatMessage(chat_id=9201, role="assistant", content="still fine", position=1)
    )
    assert len(await chat_messages.list_by_chat_ordered(9201)) == 2


async def test_fresh_database_first_run_still_carries_tool_trace__F1(tmp_path: Path):
    # F1 (Constraints): "Preserve first-run behaviour on a fresh database" — the
    # seam must not disturb the path that already worked.
    config = DbConfig(db_path=tmp_path / "fresh.db")
    await init_engine(config)

    await init_db()

    assert config.db_path.is_file()
    columns = _columns(config.db_path)
    assert columns != [], f"{TABLE} table was not created on a fresh database"
    assert columns.count(COLUMN) == 1
    assert _column_is_nullable(config.db_path)

    await _insert_user_message(9301, "hello from a fresh database")
    listed = await chat_messages.list_by_chat_ordered(9301)
    assert [m.content for m in listed] == ["hello from a fresh database"]
    assert listed[0].tool_trace is None


@pytest.mark.parametrize("run_count", [1, 2])
async def test_pre_024_insert_succeeds_after_n_init_db_runs__F1(
    tmp_path: Path, run_count: int
):
    # F1: the end-to-end contract, stated as the symptom alone — after one OR
    # two init_db() runs against a pre-024 database, chat is usable.
    await _make_pre_024_database(tmp_path, f"pre024_runs_{run_count}.db")

    for _ in range(run_count):
        await init_db()

    await _insert_user_message(9400 + run_count, "chat is usable again")

    listed = await chat_messages.list_by_chat_ordered(9400 + run_count)
    assert [m.content for m in listed] == ["chat is usable again"]
