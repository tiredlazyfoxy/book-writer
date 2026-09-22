"""The `tool_trace` Pydantic gate and its JSONL round trip (feature 024, DoD-3).

Bound to the frozen skeleton (`status.md` -> `## Skeleton`):

    app.models.schemas.chats:
        class ToolTraceEntry(BaseModel) { tool_name; arguments; result; ok }
        class ToolTrace(BaseModel)      { entries: list[ToolTraceEntry] }
            @classmethod parse_column(cls, raw: str | None)
                -> list[ToolTraceEntry] | None
            def to_column(self) -> str
    app.models.chat:
        ChatMessage.tool_trace: str | None

    (reused, unchanged) app.services.db_import_export.export_all / import_all,
    app.db.chat_messages.create / list_by_chat_ordered

Expected values come from the SPEC ONLY -- `plan.md` -> DoD-3 and -> Interface
("`ToolTrace.parse_column` reads the nullable `tool_trace` TEXT column into
entries (`None` in -> `None` out); `to_column` serializes an instance to the
column's JSON-in-TEXT form. This pair **is** DoD-3's Pydantic gate"), plus root
`CLAUDE.md`'s non-optional import/export rule and `context.md` -> "extend the
existing `chat_messages` codec pair ... in the same change".

The JSONL half is a REAL round trip: rows are exported with `export_all()`, then
imported into a PRISTINE database, so a value can only be read back if export
wrote it and import read it. SQLite does not enforce FKs here (see
tests/db/test_chat_messages.py), so messages need no parent chat row.
`asyncio_mode = "auto"`; the `db` fixture supplies an isolated temp database.
"""

import json
from pathlib import Path

from app.db import chat_messages
from app.db.engine import DbConfig, init_db, init_engine
from app.models.chat import ChatMessage
from app.models.schemas.chats import ToolTrace, ToolTraceEntry
from app.services.db_import_export import export_all, import_all

# A trace with two entries: one successful, one failed; arguments of mixed JSON
# types (string / int / bool / nested object) and a non-ASCII payload, so the
# serialization is exercised beyond flat ASCII strings.
ENTRIES = [
    ToolTraceEntry(
        tool_name="codex_search",
        arguments={"query": "Halden's oath", "limit": 5, "archived": False},
        result="3 hits: Halden, Northgate, the long winter.",
        ok=True,
    ),
    ToolTraceEntry(
        tool_name="write_codex_draft",
        arguments={"field": "body", "text": "Håldén keeps the gate", "meta": {"n": 1}},
        result="the tool failed: no subject bound",
        ok=False,
    ),
]


def _dumps(entries: list[ToolTraceEntry]) -> list[dict]:
    return [entry.model_dump() for entry in entries]


# ---------------------------------------------------------------------------
# DoD-3 (a) -- the Pydantic gate: to_column / parse_column round trip
# ---------------------------------------------------------------------------


def test_to_column_parse_column_round_trip__DoD3():
    # DoD-3: `to_column()` serializes to the column's JSON-in-TEXT form, and
    # `parse_column` reads that exact text back into equivalent entries -- every
    # field of every entry, in order.
    column = ToolTrace(entries=ENTRIES).to_column()

    assert isinstance(column, str)
    # JSON-in-TEXT: the column's payload is valid JSON.
    json.loads(column)

    parsed = ToolTrace.parse_column(column)

    assert parsed is not None
    assert len(parsed) == 2
    assert all(isinstance(entry, ToolTraceEntry) for entry in parsed)
    assert _dumps(parsed) == _dumps(ENTRIES)
    # Ordering is part of the contract, and the ok/False entry survives as False.
    assert [entry.tool_name for entry in parsed] == ["codex_search", "write_codex_draft"]
    assert [entry.ok for entry in parsed] == [True, False]
    assert parsed[0].arguments == {
        "query": "Halden's oath",
        "limit": 5,
        "archived": False,
    }
    assert parsed[1].arguments["meta"] == {"n": 1}


def test_parse_column_none_in_none_out__DoD3():
    # DoD-3 (Interface: "`None` in -> `None` out"): the nullable column's null
    # state parses to None -- not to an empty list.
    assert ToolTrace.parse_column(None) is None


def test_empty_trace_round_trips_as_empty_not_null__DoD3():
    # DoD-3: an empty trace is a distinct state from a null column -- it round
    # trips to an empty list, keeping "no tool ran" (null) distinguishable.
    parsed = ToolTrace.parse_column(ToolTrace(entries=[]).to_column())

    assert parsed == []
    assert parsed is not None


# ---------------------------------------------------------------------------
# DoD-3 (b) -- the `chat_messages` JSONL export/import round trip
# ---------------------------------------------------------------------------


async def test_jsonl_round_trip_preserves_tool_trace__DoD3(db: DbConfig, tmp_path: Path):
    # DoD-3 (root CLAUDE.md's import/export rule): a chat message's `tool_trace`
    # survives export and import end to end -- exported from one database,
    # imported into a PRISTINE one, and read back identical. A message with a
    # null trace stays null through the same cycle.
    chat_id = 90001
    column = ToolTrace(entries=ENTRIES).to_column()

    traced = await chat_messages.create(
        ChatMessage(
            chat_id=chat_id,
            role="assistant",
            content="I looked it up and drafted that.",
            reasoning="checking the codex first",
            position=1,
            tool_trace=column,
        )
    )
    untraced = await chat_messages.create(
        ChatMessage(
            chat_id=chat_id,
            role="assistant",
            content="no tools needed here",
            position=2,
            tool_trace=None,
        )
    )

    archive = await export_all()

    # A pristine database: neither row is present before the import.
    await init_engine(DbConfig(db_path=tmp_path / "restored.db"))
    await init_db()
    assert await chat_messages.list_by_chat_ordered(chat_id) == []

    await import_all(archive)

    restored = await chat_messages.list_by_chat_ordered(chat_id)
    by_id = {row.id: row for row in restored}
    assert traced.id in by_id
    assert untraced.id in by_id

    # The trace survived the round trip, and parses back to the same entries.
    restored_traced = by_id[traced.id]
    assert restored_traced.tool_trace is not None
    parsed = ToolTrace.parse_column(restored_traced.tool_trace)
    assert parsed is not None
    assert _dumps(parsed) == _dumps(ENTRIES)
    # The message's other columns are unharmed by the new one.
    assert restored_traced.content == "I looked it up and drafted that."
    assert restored_traced.reasoning == "checking the codex first"

    # A null trace round trips as null -- not "" and not an empty list.
    assert by_id[untraced.id].tool_trace is None
    assert ToolTrace.parse_column(by_id[untraced.id].tool_trace) is None
