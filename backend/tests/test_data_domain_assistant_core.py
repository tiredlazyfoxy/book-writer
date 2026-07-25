"""Tests for the FEAT-020 config core: AssistantMode + SubAgent (feature 008,
step 001).

Bound to the frozen skeleton signatures (status.md -> Skeleton -> Step 001):
    class AssistantMode(SQLModel, table=True) __tablename__="assistant_modes";
        key: str (primary_key, natural key — NO snowflake),
        system_prompt: str | None, created_at: datetime | None,
        modified_at: datetime | None                     in app.models.assistant_mode
    class SubAgent(SQLModel, table=True) __tablename__="sub_agents";
        id: int (snowflake PK), name: str (unique/index), system_prompt: str,
        disabled: bool = False, llm_server_id: int | None (FK llm_servers.id),
        model_name: str | None, created_at/modified_at: datetime | None
                                                          in app.models.sub_agent
    async def create(row: AssistantMode) -> AssistantMode  in app.db.assistant_modes
    async def get_by_id(key: str) -> AssistantMode | None   in app.db.assistant_modes
    async def list_all() -> list[AssistantMode]             in app.db.assistant_modes
    async def create(row: SubAgent) -> SubAgent             in app.db.sub_agents
    async def get_by_id(sub_agent_id: int) -> SubAgent | None  in app.db.sub_agents
    def _assistant_mode_to_dict(mode) -> dict[str, object]  in app.services.db_import_export
    def _dict_to_assistant_mode(data) -> AssistantMode      in app.services.db_import_export
    def _sub_agent_to_dict(sub_agent) -> dict[str, object]  in app.services.db_import_export
    def _dict_to_sub_agent(data) -> SubAgent                in app.services.db_import_export
    TABLE_REGISTRY: ("assistant_modes", AssistantMode, ...) then
        ("sub_agents", SubAgent, ...) at positions 3, 4 (after llm_servers)
                                                          in app.services.db_import_export
    build_consistency_report() -> report with .tables entries each carrying
        .status                                             in app.services.db_admin

Expected values come from the step spec (001.feat020-config-core.md DoD +
001.context.md + context.md), never from implementation internals:
    - AssistantMode codec emits/parses `key` VERBATIM (never through int()) — a
      key like "edit-character" survives unchanged; nullable system_prompt (None
      and set) and isoformat timestamps preserved (DoD-1);
    - SubAgent codec emits `id` as a string parsed back to the same int,
      preserves `disabled`, and preserves nullable llm_server_id / model_name in
      both the both-null and both-set shapes (DoD-2);
    - db/assistant_modes create -> get_by_id(key) round-trips an equal row and
      list_all() includes it (DoD-3);
    - db/sub_agents create -> get_by_id(id) round-trips an equal row (DoD-4);
    - TABLE_REGISTRY lists assistant_modes + sub_agents, llm_servers precedes
      sub_agents, and the tablename sequence equals the canonical FK order
      restricted to the tables present so far (DoD-5);
    - after init_db(), both tables exist in SQLModel.metadata and the FEAT-005
      consistency report is clean (DoD-6).

Async tests use asyncio_mode = "auto"; the `db` fixture (conftest) supplies an
initialized throwaway temp-SQLite engine with the registered tables created.
Pure-codec tests (DoD-1, DoD-2) and the registry test (DoD-5) need no DB.
"""

from datetime import datetime

from sqlmodel import SQLModel

from app.db import assistant_modes, sub_agents
from app.db.engine import DbConfig
from app.models.assistant_mode import AssistantMode
from app.models.sub_agent import SubAgent
from app.services import db_admin
from app.services.db_import_export import (
    TABLE_REGISTRY,
    _assistant_mode_to_dict,
    _dict_to_assistant_mode,
    _dict_to_sub_agent,
    _sub_agent_to_dict,
)

# The canonical FK order (context.md -> "The canonical TABLE_REGISTRY order").
# The registry-order invariant is asserted by filtering this list down to the
# tables actually present, so it stays valid as later steps add entries.
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
# DoD-1 — AssistantMode codec round-trip (key verbatim, no int() coercion)
# ---------------------------------------------------------------------------


# DoD-1: _assistant_mode_to_dict -> _dict_to_assistant_mode reconstructs every
# field; `key` (e.g. "edit-character") is emitted and parsed VERBATIM; a set
# system_prompt and isoformat timestamps are preserved.
def test_assistant_mode_codec_round_trips_all_fields__DoD1():
    created_at = datetime(2026, 7, 24, 9, 15, 0)
    modified_at = datetime(2026, 7, 24, 10, 30, 0)
    mode = AssistantMode(
        key="edit-character",
        system_prompt="You edit characters.",
        created_at=created_at,
        modified_at=modified_at,
    )

    data = _assistant_mode_to_dict(mode)

    # `key` is emitted verbatim as the natural-key string.
    assert data["key"] == "edit-character"
    assert isinstance(data["key"], str)
    # Timestamps are emitted via isoformat strings.
    assert data["created_at"] == created_at.isoformat()
    assert data["modified_at"] == modified_at.isoformat()

    restored = _dict_to_assistant_mode(data)

    # Every field reconstructs.
    assert restored.key == "edit-character"
    assert restored.system_prompt == "You edit characters."
    assert restored.created_at == created_at
    assert restored.modified_at == modified_at


# DoD-1: the nullable `system_prompt` survives round-trip when None (null-or-empty
# is valid per 001.context.md); nullable timestamps also pass through as None.
def test_assistant_mode_codec_round_trips_null_prompt__DoD1():
    mode = AssistantMode(
        key="close-chapter",
        system_prompt=None,
        created_at=None,
        modified_at=None,
    )

    data = _assistant_mode_to_dict(mode)
    assert data["system_prompt"] is None
    assert data["created_at"] is None
    assert data["modified_at"] is None

    restored = _dict_to_assistant_mode(data)
    assert restored.key == "close-chapter"
    assert restored.system_prompt is None
    assert restored.created_at is None
    assert restored.modified_at is None


# DoD-1: `key` is NEVER coerced through int(). A key whose text happens to be
# all-digits must survive as the SAME string (not an int) through the codec —
# the guard against an int() round-trip that a natural-key like "edit-character"
# cannot itself exercise (int("edit-character") would raise).
def test_assistant_mode_codec_key_never_coerced_to_int__DoD1():
    mode = AssistantMode(key="123", system_prompt=None)

    data = _assistant_mode_to_dict(mode)
    assert data["key"] == "123"
    assert isinstance(data["key"], str)

    restored = _dict_to_assistant_mode(data)
    assert restored.key == "123"
    assert isinstance(restored.key, str)


# ---------------------------------------------------------------------------
# DoD-2 — SubAgent codec round-trip (id as string, nullable model pair)
# ---------------------------------------------------------------------------


# DoD-2: _sub_agent_to_dict emits `id` as a STRING; _dict_to_sub_agent parses it
# back to the same int. `disabled` is preserved; the both-null model pair
# (llm_server_id / model_name both None) is preserved; timestamps via isoformat.
def test_sub_agent_codec_round_trips_both_null_shape__DoD2():
    created_at = datetime(2026, 7, 24, 8, 0, 0)
    modified_at = datetime(2026, 7, 24, 8, 5, 0)
    agent = SubAgent(
        id=987654321,
        name="continuity-checker",
        system_prompt="Check continuity.",
        disabled=False,
        llm_server_id=None,
        model_name=None,
        created_at=created_at,
        modified_at=modified_at,
    )

    data = _sub_agent_to_dict(agent)

    # `id` is emitted as a string.
    assert data["id"] == "987654321"
    assert isinstance(data["id"], str)
    # Nullable model pair passes through as None on both halves.
    assert data["llm_server_id"] is None
    assert data["model_name"] is None
    # Timestamps via isoformat.
    assert data["created_at"] == created_at.isoformat()
    assert data["modified_at"] == modified_at.isoformat()

    restored = _dict_to_sub_agent(data)

    # `id` parses back to the same int.
    assert restored.id == 987654321
    assert isinstance(restored.id, int)
    assert restored.name == "continuity-checker"
    assert restored.system_prompt == "Check continuity."
    assert restored.disabled is False
    assert restored.llm_server_id is None
    assert restored.model_name is None
    assert restored.created_at == created_at
    assert restored.modified_at == modified_at


# DoD-2: the both-SET model pair (llm_server_id and model_name both provided) is
# preserved, and `disabled=True` round-trips as True.
def test_sub_agent_codec_round_trips_both_set_shape__DoD2():
    agent = SubAgent(
        id=42,
        name="prose-critic",
        system_prompt="Critique prose.",
        disabled=True,
        llm_server_id=7,
        model_name="gpt-4o",
        created_at=None,
        modified_at=None,
    )

    data = _sub_agent_to_dict(agent)
    assert data["id"] == "42"
    assert data["llm_server_id"] == 7
    assert data["model_name"] == "gpt-4o"

    restored = _dict_to_sub_agent(data)
    assert restored.id == 42
    assert restored.name == "prose-critic"
    assert restored.system_prompt == "Critique prose."
    assert restored.disabled is True
    assert restored.llm_server_id == 7
    assert restored.model_name == "gpt-4o"


# ---------------------------------------------------------------------------
# DoD-3 — db/assistant_modes create -> get_by_id round-trip
# ---------------------------------------------------------------------------


# DoD-3: assistant_modes.create(row) then get_by_id(row.key) returns an equal
# row, and list_all() includes it.
async def test_assistant_modes_db_round_trip__DoD3(db: DbConfig):
    row = AssistantMode(
        key="edit-location",
        system_prompt="You edit locations.",
        created_at=datetime(2026, 7, 24, 11, 0, 0),
        modified_at=datetime(2026, 7, 24, 11, 30, 0),
    )

    created = await assistant_modes.create(row)
    assert created.key == "edit-location"

    fetched = await assistant_modes.get_by_id("edit-location")
    assert fetched is not None
    assert fetched.key == "edit-location"
    assert fetched.system_prompt == "You edit locations."
    assert fetched.created_at == datetime(2026, 7, 24, 11, 0, 0)
    assert fetched.modified_at == datetime(2026, 7, 24, 11, 30, 0)

    all_modes = await assistant_modes.list_all()
    assert "edit-location" in [m.key for m in all_modes]


# ---------------------------------------------------------------------------
# DoD-4 — db/sub_agents create -> get_by_id round-trip
# ---------------------------------------------------------------------------


# DoD-4: sub_agents.create(row) then get_by_id(row.id) returns an equal row.
async def test_sub_agents_db_round_trip__DoD4(db: DbConfig):
    row = SubAgent(
        name="fact-verifier",
        system_prompt="Verify facts.",
        disabled=True,
        llm_server_id=None,
        model_name=None,
    )

    created = await sub_agents.create(row)
    # Snowflake PK is populated on the created row.
    assert created.id is not None

    fetched = await sub_agents.get_by_id(created.id)
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.name == "fact-verifier"
    assert fetched.system_prompt == "Verify facts."
    assert fetched.disabled is True
    assert fetched.llm_server_id is None
    assert fetched.model_name is None


# ---------------------------------------------------------------------------
# DoD-5 — TABLE_REGISTRY order (canonical-restricted invariant)
# ---------------------------------------------------------------------------


# DoD-5: assistant_modes and sub_agents appear in TABLE_REGISTRY, llm_servers
# precedes sub_agents, and the tablename sequence equals the canonical FK order
# restricted to the tables present so far.
def test_table_registry_order__DoD5():
    filenames = [entry[0] for entry in TABLE_REGISTRY]

    # Both new config tables are registered.
    assert "assistant_modes" in filenames
    assert "sub_agents" in filenames

    # llm_servers precedes both new config entries.
    assert filenames.index("llm_servers") < filenames.index("assistant_modes")
    assert filenames.index("llm_servers") < filenames.index("sub_agents")

    # The registry's tablename sequence equals the canonical order filtered down
    # to the tables actually present (canonical-restricted invariant).
    present = set(filenames)
    expected_sequence = [name for name in CANONICAL_ORDER if name in present]
    assert filenames == expected_sequence

    # The two new tuples bind the correct model classes.
    by_name = {entry[0]: entry for entry in TABLE_REGISTRY}
    assert by_name["assistant_modes"][1] is AssistantMode
    assert by_name["sub_agents"][1] is SubAgent


# ---------------------------------------------------------------------------
# DoD-6 — schema present + drift-clean consistency report
# ---------------------------------------------------------------------------


# DoD-6: after init_db() (the `db` fixture), assistant_modes and sub_agents exist
# in SQLModel.metadata and the FEAT-005 consistency report is clean (every table
# entry has status "ok").
async def test_schema_present_and_drift_clean__DoD6(db: DbConfig):
    tables = SQLModel.metadata.tables
    assert "assistant_modes" in tables
    assert "sub_agents" in tables

    report = await db_admin.build_consistency_report()
    by_name = {entry.name: entry for entry in report.tables}

    # The two new tables are reported and clean.
    assert by_name["assistant_modes"].status == "ok"
    assert by_name["sub_agents"].status == "ok"

    # A freshly-created DB matches metadata: no table drifts.
    for entry in report.tables:
        assert entry.status == "ok", f"table {entry.name!r} not clean: {entry.status}"
