"""Tests for the FEAT-020 link tables: ModeTool + SubagentTool + ModeSubagent
(feature 008, step 002).

Bound to the frozen skeleton signatures (status.md -> Skeleton -> Step 002):
    class ModeTool(SQLModel, table=True) __tablename__="mode_tool" (SINGULAR);
        UniqueConstraint(mode_key, tool_name);
        id: int (snowflake PK), mode_key: str (FK assistant_modes.key),
        tool_name: str                              in app.models.mode_tool
    class SubagentTool(SQLModel, table=True) __tablename__="subagent_tool"
        (SINGULAR); UniqueConstraint(sub_agent_id, tool_name);
        id: int (snowflake PK), sub_agent_id: int (FK sub_agents.id),
        tool_name: str                              in app.models.subagent_tool
    class ModeSubagent(SQLModel, table=True) __tablename__="mode_subagent"
        (SINGULAR); UniqueConstraint(mode_key, sub_agent_id);
        id: int (snowflake PK), mode_key: str (FK assistant_modes.key),
        sub_agent_id: int (FK sub_agents.id)        in app.models.mode_subagent
    async def create(row: ModeTool) -> ModeTool               in app.db.mode_tools
    async def get_by_id(id: int) -> ModeTool | None           in app.db.mode_tools
    async def list_by_mode(mode_key: str) -> list[ModeTool]   in app.db.mode_tools
    async def create(row: SubagentTool) -> SubagentTool       in app.db.subagent_tools
    async def get_by_id(id: int) -> SubagentTool | None       in app.db.subagent_tools
    async def list_by_sub_agent(sub_agent_id: int) -> list[SubagentTool]
                                                              in app.db.subagent_tools
    async def create(row: ModeSubagent) -> ModeSubagent       in app.db.mode_subagents
    async def get_by_id(id: int) -> ModeSubagent | None       in app.db.mode_subagents
    async def list_by_mode(mode_key: str) -> list[ModeSubagent]
                                                              in app.db.mode_subagents
    def _mode_tool_to_dict / _dict_to_mode_tool               in app.services.db_import_export
    def _subagent_tool_to_dict / _dict_to_subagent_tool       in app.services.db_import_export
    def _mode_subagent_to_dict / _dict_to_mode_subagent       in app.services.db_import_export
    TABLE_REGISTRY: ("mode_tools", ModeTool, ...),
        ("subagent_tools", SubagentTool, ...),
        ("mode_subagents", ModeSubagent, ...) at positions 5, 6, 7 (after
        sub_agents) — PLURAL labels deliberately differ from the SINGULAR
        __tablename__ values                        in app.services.db_import_export
    build_consistency_report() -> report with .tables entries each carrying
        .status                                     in app.services.db_admin

Expected values come from the step spec (002.feat020-link-tables.md DoD +
002.context.md + context.md), never from implementation internals:
    - each codec emits `id` (and FK int ids `sub_agent_id`) as a string parsed
      back to the same int; `mode_key` is emitted/parsed VERBATIM as a string
      (never through int(), guarded with an all-digit key); `tool_name`
      preserved (DoD-1, DoD-2, DoD-3);
    - db round-trip each table: create -> get_by_id returns an equal row, and the
      parent-scoped list functions return exactly the rows for a given parent
      (DoD-4);
    - composite unique enforced: a second row with the same natural pair is
      rejected by the DB (DoD-5);
    - TABLE_REGISTRY lists the three link labels in canonical order, each after
      sub_agents, and the label sequence equals the canonical order restricted to
      the tables present so far (DoD-6);
    - after init_db(), the three SINGULAR tablenames exist in SQLModel.metadata
      and the FEAT-005 consistency report is clean (DoD-7).

Async tests use asyncio_mode = "auto"; the `db` fixture (conftest) supplies an
initialized throwaway temp-SQLite engine with the registered tables created.
Pure-codec tests (DoD-1, DoD-2, DoD-3) and the registry test (DoD-6) need no DB.
SQLite does NOT enforce FKs by default, so link rows need no parent rows; the
composite-UNIQUE constraint (DoD-5) is enforced regardless.
"""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import SQLModel

from app.db import mode_subagents, mode_tools, subagent_tools
from app.db.engine import DbConfig
from app.models.mode_subagent import ModeSubagent
from app.models.mode_tool import ModeTool
from app.models.subagent_tool import SubagentTool
from app.services import db_admin
from app.services.db_import_export import (
    TABLE_REGISTRY,
    _dict_to_mode_subagent,
    _dict_to_mode_tool,
    _dict_to_subagent_tool,
    _mode_subagent_to_dict,
    _mode_tool_to_dict,
    _subagent_tool_to_dict,
)

# The canonical FK order (context.md -> "The canonical TABLE_REGISTRY order").
# The registry-order invariant is asserted by filtering this list down to the
# tables actually present, so it stays valid as later steps add entries. Note
# these are the PLURAL registry labels, which differ from the SINGULAR
# __tablename__ values used for the metadata check in DoD-7.
CANONICAL_ORDER = [
    "users",
    "llm_servers",
    "assistant_modes",
    "sub_agents",
    "mode_tools",
    "subagent_tools",
    "mode_subagents",
    "books",
    "book_members",
    "book_author_prompts",
    "chapter_author_prompts",
    "chapters",
    "chapter_changes",
    "chapter_text_revisions",
    "chapter_note_changesets",
    "codex_entries",
    "codex_entry_versions",
    "flags",
    "chats",
    "chat_messages",
]


# ---------------------------------------------------------------------------
# DoD-1 — ModeTool codec round-trip (id string<->int, mode_key verbatim)
# ---------------------------------------------------------------------------


# DoD-1: _mode_tool_to_dict emits `id` as a STRING and `mode_key`/`tool_name` as
# strings; _dict_to_mode_tool parses `id` back to the SAME int, `mode_key`
# verbatim (never int()), `tool_name` preserved.
def test_mode_tool_codec_round_trips_all_fields__DoD1():
    row = ModeTool(id=123456789, mode_key="edit-character", tool_name="write_text")

    data = _mode_tool_to_dict(row)

    # `id` emitted as a string.
    assert data["id"] == "123456789"
    assert isinstance(data["id"], str)
    # `mode_key` emitted verbatim as the natural-key string.
    assert data["mode_key"] == "edit-character"
    assert isinstance(data["mode_key"], str)
    # `tool_name` preserved.
    assert data["tool_name"] == "write_text"

    restored = _dict_to_mode_tool(data)

    # `id` parses back to the same int.
    assert restored.id == 123456789
    assert isinstance(restored.id, int)
    assert restored.mode_key == "edit-character"
    assert restored.tool_name == "write_text"


# DoD-1: `mode_key` is NEVER coerced through int(). A key whose text happens to
# be all-digits must survive as the SAME string through the codec — the guard an
# ordinary key like "edit-character" cannot itself exercise.
def test_mode_tool_codec_mode_key_never_coerced_to_int__DoD1():
    row = ModeTool(id=1, mode_key="123", tool_name="search")

    data = _mode_tool_to_dict(row)
    assert data["mode_key"] == "123"
    assert isinstance(data["mode_key"], str)

    restored = _dict_to_mode_tool(data)
    assert restored.mode_key == "123"
    assert isinstance(restored.mode_key, str)


# ---------------------------------------------------------------------------
# DoD-2 — SubagentTool codec round-trip (id + sub_agent_id string<->int)
# ---------------------------------------------------------------------------


# DoD-2: _subagent_tool_to_dict emits `id` and `sub_agent_id` as STRINGS;
# _dict_to_subagent_tool parses both back to the SAME ints; `tool_name`
# preserved.
def test_subagent_tool_codec_round_trips_all_fields__DoD2():
    row = SubagentTool(id=987654321, sub_agent_id=42, tool_name="lookup_codex")

    data = _subagent_tool_to_dict(row)

    assert data["id"] == "987654321"
    assert isinstance(data["id"], str)
    assert data["sub_agent_id"] == "42"
    assert isinstance(data["sub_agent_id"], str)
    assert data["tool_name"] == "lookup_codex"

    restored = _dict_to_subagent_tool(data)

    assert restored.id == 987654321
    assert isinstance(restored.id, int)
    assert restored.sub_agent_id == 42
    assert isinstance(restored.sub_agent_id, int)
    assert restored.tool_name == "lookup_codex"


# ---------------------------------------------------------------------------
# DoD-3 — ModeSubagent codec round-trip (id + sub_agent_id string<->int,
#         mode_key verbatim)
# ---------------------------------------------------------------------------


# DoD-3: _mode_subagent_to_dict emits `id` and `sub_agent_id` as STRINGS and
# `mode_key` verbatim; _dict_to_mode_subagent parses the two ints back and keeps
# `mode_key` as the same string.
def test_mode_subagent_codec_round_trips_all_fields__DoD3():
    row = ModeSubagent(id=555, mode_key="edit-character", sub_agent_id=77)

    data = _mode_subagent_to_dict(row)

    assert data["id"] == "555"
    assert isinstance(data["id"], str)
    assert data["sub_agent_id"] == "77"
    assert isinstance(data["sub_agent_id"], str)
    assert data["mode_key"] == "edit-character"
    assert isinstance(data["mode_key"], str)

    restored = _dict_to_mode_subagent(data)

    assert restored.id == 555
    assert isinstance(restored.id, int)
    assert restored.sub_agent_id == 77
    assert isinstance(restored.sub_agent_id, int)
    assert restored.mode_key == "edit-character"


# DoD-3: `mode_key` is NEVER coerced through int() — an all-digit key survives
# as the same string through the codec.
def test_mode_subagent_codec_mode_key_never_coerced_to_int__DoD3():
    row = ModeSubagent(id=1, mode_key="456", sub_agent_id=2)

    data = _mode_subagent_to_dict(row)
    assert data["mode_key"] == "456"
    assert isinstance(data["mode_key"], str)

    restored = _dict_to_mode_subagent(data)
    assert restored.mode_key == "456"
    assert isinstance(restored.mode_key, str)


# ---------------------------------------------------------------------------
# DoD-4 — DB round-trip each table (create -> get_by_id + parent-scoped list)
# ---------------------------------------------------------------------------


# DoD-4: mode_tools.create(row) then get_by_id(row.id) returns an equal row; and
# list_by_mode(mode_key) returns exactly that mode's rows (filters out another
# mode's rows).
async def test_mode_tools_db_round_trip_and_list__DoD4(db: DbConfig):
    row_a = ModeTool(mode_key="edit-character", tool_name="write_text")
    row_b = ModeTool(mode_key="edit-character", tool_name="search")
    row_other = ModeTool(mode_key="close-chapter", tool_name="write_text")

    created_a = await mode_tools.create(row_a)
    await mode_tools.create(row_b)
    await mode_tools.create(row_other)

    # Snowflake PK populated on the created row.
    assert created_a.id is not None

    fetched = await mode_tools.get_by_id(created_a.id)
    assert fetched is not None
    assert fetched.id == created_a.id
    assert fetched.mode_key == "edit-character"
    assert fetched.tool_name == "write_text"

    # list_by_mode returns exactly this mode's rows (both, and only those).
    listed = await mode_tools.list_by_mode("edit-character")
    assert {r.mode_key for r in listed} == {"edit-character"}
    assert {r.tool_name for r in listed} == {"write_text", "search"}
    assert len(listed) == 2


# DoD-4: subagent_tools.create(row) then get_by_id(row.id) returns an equal row;
# and list_by_sub_agent(sub_agent_id) returns exactly that sub-agent's rows.
async def test_subagent_tools_db_round_trip_and_list__DoD4(db: DbConfig):
    row_a = SubagentTool(sub_agent_id=100, tool_name="write_text")
    row_b = SubagentTool(sub_agent_id=100, tool_name="search")
    row_other = SubagentTool(sub_agent_id=200, tool_name="write_text")

    created_a = await subagent_tools.create(row_a)
    await subagent_tools.create(row_b)
    await subagent_tools.create(row_other)

    assert created_a.id is not None

    fetched = await subagent_tools.get_by_id(created_a.id)
    assert fetched is not None
    assert fetched.id == created_a.id
    assert fetched.sub_agent_id == 100
    assert fetched.tool_name == "write_text"

    listed = await subagent_tools.list_by_sub_agent(100)
    assert {r.sub_agent_id for r in listed} == {100}
    assert {r.tool_name for r in listed} == {"write_text", "search"}
    assert len(listed) == 2


# DoD-4: mode_subagents.create(row) then get_by_id(row.id) returns an equal row;
# and list_by_mode(mode_key) returns exactly that mode's rows.
async def test_mode_subagents_db_round_trip_and_list__DoD4(db: DbConfig):
    row_a = ModeSubagent(mode_key="edit-character", sub_agent_id=100)
    row_b = ModeSubagent(mode_key="edit-character", sub_agent_id=200)
    row_other = ModeSubagent(mode_key="close-chapter", sub_agent_id=100)

    created_a = await mode_subagents.create(row_a)
    await mode_subagents.create(row_b)
    await mode_subagents.create(row_other)

    assert created_a.id is not None

    fetched = await mode_subagents.get_by_id(created_a.id)
    assert fetched is not None
    assert fetched.id == created_a.id
    assert fetched.mode_key == "edit-character"
    assert fetched.sub_agent_id == 100

    listed = await mode_subagents.list_by_mode("edit-character")
    assert {r.mode_key for r in listed} == {"edit-character"}
    assert {r.sub_agent_id for r in listed} == {100, 200}
    assert len(listed) == 2


# ---------------------------------------------------------------------------
# DoD-5 — composite unique enforced (second same-natural-pair row rejected)
# ---------------------------------------------------------------------------


# DoD-5: a second mode_tool row with the same (mode_key, tool_name) pair is
# rejected by the DB (the surrogate id differs automatically).
async def test_mode_tool_composite_unique_enforced__DoD5(db: DbConfig):
    await mode_tools.create(ModeTool(mode_key="edit-character", tool_name="write_text"))

    with pytest.raises(IntegrityError):
        await mode_tools.create(
            ModeTool(mode_key="edit-character", tool_name="write_text")
        )


# DoD-5: a second subagent_tool row with the same (sub_agent_id, tool_name) pair
# is rejected by the DB.
async def test_subagent_tool_composite_unique_enforced__DoD5(db: DbConfig):
    await subagent_tools.create(SubagentTool(sub_agent_id=100, tool_name="search"))

    with pytest.raises(IntegrityError):
        await subagent_tools.create(SubagentTool(sub_agent_id=100, tool_name="search"))


# DoD-5: a second mode_subagent row with the same (mode_key, sub_agent_id) pair
# is rejected by the DB.
async def test_mode_subagent_composite_unique_enforced__DoD5(db: DbConfig):
    await mode_subagents.create(ModeSubagent(mode_key="edit-character", sub_agent_id=100))

    with pytest.raises(IntegrityError):
        await mode_subagents.create(
            ModeSubagent(mode_key="edit-character", sub_agent_id=100)
        )


# ---------------------------------------------------------------------------
# DoD-6 — TABLE_REGISTRY order (canonical-restricted invariant, PLURAL labels)
# ---------------------------------------------------------------------------


# DoD-6: the three link labels (mode_tools, subagent_tools, mode_subagents)
# appear in TABLE_REGISTRY in canonical order, each after sub_agents, and the
# label sequence equals the canonical order restricted to the tables present so
# far. The registry labels are PLURAL (deliberately unlike the SINGULAR
# __tablename__ values).
def test_table_registry_order__DoD6():
    labels = [entry[0] for entry in TABLE_REGISTRY]

    # All three new link labels are registered.
    assert "mode_tools" in labels
    assert "subagent_tools" in labels
    assert "mode_subagents" in labels

    # Each appears after sub_agents.
    sub_agents_idx = labels.index("sub_agents")
    assert sub_agents_idx < labels.index("mode_tools")
    assert sub_agents_idx < labels.index("subagent_tools")
    assert sub_agents_idx < labels.index("mode_subagents")

    # Canonical order among the three: mode_tools, then subagent_tools, then
    # mode_subagents.
    assert labels.index("mode_tools") < labels.index("subagent_tools")
    assert labels.index("subagent_tools") < labels.index("mode_subagents")

    # The registry's label sequence equals the canonical order filtered down to
    # the tables actually present (canonical-restricted invariant).
    present = set(labels)
    expected_sequence = [name for name in CANONICAL_ORDER if name in present]
    assert labels == expected_sequence

    # The three new tuples bind the correct model classes.
    by_label = {entry[0]: entry for entry in TABLE_REGISTRY}
    assert by_label["mode_tools"][1] is ModeTool
    assert by_label["subagent_tools"][1] is SubagentTool
    assert by_label["mode_subagents"][1] is ModeSubagent


# ---------------------------------------------------------------------------
# DoD-7 — schema present (SINGULAR tablenames) + drift-clean report
# ---------------------------------------------------------------------------


# DoD-7: after init_db() (the `db` fixture), the three SINGULAR tablenames exist
# in SQLModel.metadata and the FEAT-005 consistency report is clean (every table
# entry has status "ok").
async def test_schema_present_and_drift_clean__DoD7(db: DbConfig):
    tables = SQLModel.metadata.tables
    # Metadata keys use the SINGULAR __tablename__ values.
    assert "mode_tool" in tables
    assert "subagent_tool" in tables
    assert "mode_subagent" in tables

    report = await db_admin.build_consistency_report()
    by_name = {entry.name: entry for entry in report.tables}

    # The three new link tables are reported and clean.
    assert by_name["mode_tool"].status == "ok"
    assert by_name["subagent_tool"].status == "ok"
    assert by_name["mode_subagent"].status == "ok"

    # A freshly-created DB matches metadata: no table drifts.
    for entry in report.tables:
        assert entry.status == "ok", f"table {entry.name!r} not clean: {entry.status}"
