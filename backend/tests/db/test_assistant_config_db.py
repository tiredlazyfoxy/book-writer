"""Tests for the nine new assistant-config `db/` functions (feature 012, step 001).

Bound to the frozen skeleton signatures (status.md -> Skeleton -> Step 001):
    async def update(row: AssistantMode) -> None            in app.db.assistant_modes
    async def list_all() -> list[SubAgent]                  in app.db.sub_agents
    async def get_by_name(name: str) -> SubAgent | None      in app.db.sub_agents
    async def update(row: SubAgent) -> None                 in app.db.sub_agents
    async def delete_by_mode(mode_key: str) -> int           in app.db.mode_tools
    async def delete_by_sub_agent(sub_agent_id: int) -> int   in app.db.subagent_tools
    async def list_by_sub_agent(sub_agent_id: int) -> list[ModeSubagent]
                                                             in app.db.mode_subagents
    async def delete_by_mode(mode_key: str) -> int           in app.db.mode_subagents
    async def delete_by_sub_agent(sub_agent_id: int) -> int   in app.db.mode_subagents

Supporting frozen signatures reused from feature 008 (unchanged by this step):
    assistant_modes.create / get_by_id, sub_agents.create / get_by_id,
    mode_tools.create / list_by_mode, subagent_tools.create / list_by_sub_agent,
    mode_subagents.create / list_by_mode

Expected values come from the step spec (001.db-layer-completion.md DoD +
Interface intent + 001.context.md + context.md), never from implementation
internals:
    - DoD-1 (US-110.AC-1): assistant_modes.update persists a changed
      system_prompt (including setting it back to None) and a changed
      modified_at; a later get_by_id reads the new values back. The contract is
      row-in / None-out (skeleton note), and `db/` never sets timestamps — the
      caller assigns modified_at before update (001.context.md -> Gotchas);
    - DoD-2 (US-114.AC-1): sub_agents.list_all returns every row ordered by
      `name` ASCENDING, including rows with disabled = True (the db layer filters
      nothing); sub_agents.update persists changed scalar fields and reads back;
    - DoD-3 (US-113.AC-3): sub_agents.get_by_name returns the matching row for an
      exact name and None for a name no row carries;
    - DoD-4 (US-111.AC-1): mode_tools.delete_by_mode removes exactly the rows for
      the named mode, leaves other modes' rows intact, returns the NUMBER removed,
      and returns 0 WITHOUT RAISING when the mode has no rows;
    - DoD-5 (US-113.AC-1): subagent_tools.delete_by_sub_agent behaves the same
      way, scoped to one sub-agent id;
    - DoD-6 (US-112.AC-2): mode_subagents.list_by_sub_agent returns exactly the
      link rows for that sub-agent, and the same link row created from the mode
      side is visible through it — one row set, read from both directions;
    - DoD-7 (US-114.AC-2): mode_subagents.delete_by_mode and
      delete_by_sub_agent each remove only their own slice of the same table.
    (DoD-8 / DoD-9 live in tests/services/test_setup_mode_seed.py; DoD-10 is
    [manual/live] — no automated test.)

Async tests use asyncio_mode = "auto"; the `db` fixture (conftest) supplies an
initialized throwaway temp-SQLite engine (init_engine + init_db), so the schema
is present and each test is isolated. SQLite does not enforce FKs here (see
tests/test_data_domain_assistant_links.py), so link rows and model-pair ids need
no parent rows.
"""

from datetime import datetime

from app.db import assistant_modes, mode_subagents, mode_tools, sub_agents, subagent_tools
from app.db.engine import DbConfig
from app.models.assistant_mode import AssistantMode
from app.models.mode_subagent import ModeSubagent
from app.models.mode_tool import ModeTool
from app.models.sub_agent import SubAgent
from app.models.subagent_tool import SubagentTool

# ---------------------------------------------------------------------------
# DoD-1 — assistant_modes.update persists prompt + modified_at (US-110.AC-1)
# ---------------------------------------------------------------------------


# DoD-1 (US-110.AC-1): update(row) persists a changed system_prompt and a changed
# modified_at, and a subsequent get_by_id reads the new values back. The row-in /
# None-out contract is asserted explicitly (skeleton note). created_at is left
# alone by the caller and must survive.
async def test_mode_update_persists_prompt_and_modified_at__DoD1_US110_AC1(
    db: DbConfig,
):
    created_at = datetime(2026, 7, 26, 9, 0, 0)
    first_modified = datetime(2026, 7, 26, 9, 0, 0)
    second_modified = datetime(2026, 7, 26, 10, 15, 0)

    await assistant_modes.create(
        AssistantMode(
            key="write-chapter",
            system_prompt=None,
            created_at=created_at,
            modified_at=first_modified,
        )
    )

    row = await assistant_modes.get_by_id("write-chapter")
    assert row is not None
    # The caller mutates the row and assigns modified_at itself — `db/` never
    # sets timestamps (001.context.md -> Gotchas).
    row.system_prompt = "You write chapters."
    row.modified_at = second_modified

    result = await assistant_modes.update(row)

    # Row-in / None-out contract.
    assert result is None

    fetched = await assistant_modes.get_by_id("write-chapter")
    assert fetched is not None
    assert fetched.key == "write-chapter"
    assert fetched.system_prompt == "You write chapters."
    assert fetched.modified_at == second_modified
    # created_at was not part of the change and is untouched.
    assert fetched.created_at == created_at


# DoD-1 (US-110.AC-1): the same update path must persist a system_prompt set back
# to None — clearing a stored prompt is a real, storable state (context.md ->
# US-110.AC-4 "the *stored* empty-prompt state").
async def test_mode_update_persists_prompt_cleared_to_none__DoD1_US110_AC1(
    db: DbConfig,
):
    created_at = datetime(2026, 7, 26, 8, 0, 0)
    cleared_at = datetime(2026, 7, 26, 11, 30, 0)

    await assistant_modes.create(
        AssistantMode(
            key="close-chapter",
            system_prompt="You close chapters.",
            created_at=created_at,
            modified_at=created_at,
        )
    )

    row = await assistant_modes.get_by_id("close-chapter")
    assert row is not None
    row.system_prompt = None
    row.modified_at = cleared_at

    result = await assistant_modes.update(row)
    assert result is None

    fetched = await assistant_modes.get_by_id("close-chapter")
    assert fetched is not None
    assert fetched.system_prompt is None
    assert fetched.modified_at == cleared_at


# ---------------------------------------------------------------------------
# DoD-2 — sub_agents.list_all ordering + unfiltered; update persists (US-114.AC-1)
# ---------------------------------------------------------------------------


# DoD-2 (US-114.AC-1): list_all returns EVERY SubAgent row ordered by `name`
# ascending — including rows whose `disabled` is True, because the db layer
# filters nothing. Rows are created in non-alphabetical order so insertion /
# snowflake-id order cannot masquerade as name order.
async def test_sub_agents_list_all_is_name_ordered_and_unfiltered__DoD2_US114_AC1(
    db: DbConfig,
):
    await sub_agents.create(
        SubAgent(
            name="zeta-agent",
            system_prompt="Last by name.",
            disabled=True,
            llm_server_id=None,
            model_name=None,
        )
    )
    await sub_agents.create(
        SubAgent(
            name="alpha-agent",
            system_prompt="First by name.",
            disabled=False,
            llm_server_id=None,
            model_name=None,
        )
    )
    await sub_agents.create(
        SubAgent(
            name="mid-agent",
            system_prompt="Middle by name.",
            disabled=True,
            llm_server_id=None,
            model_name=None,
        )
    )

    rows = await sub_agents.list_all()

    # Every row, ordered by name ascending.
    assert [row.name for row in rows] == ["alpha-agent", "mid-agent", "zeta-agent"]
    assert len(rows) == 3

    # Disabled rows are included — the db layer filters nothing.
    by_name = {row.name: row for row in rows}
    assert by_name["zeta-agent"].disabled is True
    assert by_name["mid-agent"].disabled is True
    assert by_name["alpha-agent"].disabled is False


# DoD-2 (US-114.AC-1): update(row) persists changed scalar fields and a later
# get_by_id reads them back. Row-in / None-out, same shape as
# assistant_modes.update (skeleton note).
async def test_sub_agents_update_persists_scalar_fields__DoD2_US114_AC1(
    db: DbConfig,
):
    created = await sub_agents.create(
        SubAgent(
            name="editor-helper",
            system_prompt="Help edit.",
            disabled=False,
            llm_server_id=None,
            model_name=None,
            created_at=datetime(2026, 7, 26, 7, 0, 0),
            modified_at=datetime(2026, 7, 26, 7, 0, 0),
        )
    )
    assert created.id is not None

    row = await sub_agents.get_by_id(created.id)
    assert row is not None
    row.name = "editor-helper-renamed"
    row.system_prompt = "Help edit, harder."
    row.disabled = True
    row.llm_server_id = 7
    row.model_name = "gpt-4o"
    row.modified_at = datetime(2026, 7, 26, 12, 45, 0)

    result = await sub_agents.update(row)

    assert result is None

    fetched = await sub_agents.get_by_id(created.id)
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.name == "editor-helper-renamed"
    assert fetched.system_prompt == "Help edit, harder."
    assert fetched.disabled is True
    assert fetched.llm_server_id == 7
    assert fetched.model_name == "gpt-4o"
    assert fetched.modified_at == datetime(2026, 7, 26, 12, 45, 0)


# ---------------------------------------------------------------------------
# DoD-3 — sub_agents.get_by_name exact match / None (US-113.AC-3)
# ---------------------------------------------------------------------------


# DoD-3 (US-113.AC-3): get_by_name returns the matching row for an exact name and
# None for a name no row carries. A prefix of an existing name is also a name no
# row carries — the lookup is on the exact `name`, not a partial match.
async def test_sub_agents_get_by_name_exact_match_or_none__DoD3_US113_AC3(
    db: DbConfig,
):
    created = await sub_agents.create(
        SubAgent(
            name="continuity-checker",
            system_prompt="Check continuity.",
            disabled=False,
            llm_server_id=None,
            model_name=None,
        )
    )
    # A second row so the lookup has to discriminate rather than return "the one".
    await sub_agents.create(
        SubAgent(
            name="prose-critic",
            system_prompt="Critique prose.",
            disabled=False,
            llm_server_id=None,
            model_name=None,
        )
    )

    found = await sub_agents.get_by_name("continuity-checker")
    assert found is not None
    assert found.id == created.id
    assert found.name == "continuity-checker"
    assert found.system_prompt == "Check continuity."

    # A name no row carries -> None.
    assert await sub_agents.get_by_name("no-such-agent") is None
    # A prefix of an existing name is still a name no row carries -> None.
    assert await sub_agents.get_by_name("continuity") is None


# ---------------------------------------------------------------------------
# DoD-4 — mode_tools.delete_by_mode: scoped, count-returning (US-111.AC-1)
# ---------------------------------------------------------------------------


# DoD-4 (US-111.AC-1): delete_by_mode removes exactly the rows for the named mode,
# returns the number removed, and leaves other modes' rows intact.
async def test_mode_tools_delete_by_mode_removes_only_that_mode__DoD4_US111_AC1(
    db: DbConfig,
):
    await mode_tools.create(ModeTool(mode_key="edit-character", tool_name="web_search"))
    await mode_tools.create(ModeTool(mode_key="edit-character", tool_name="write_text"))
    await mode_tools.create(ModeTool(mode_key="close-chapter", tool_name="web_search"))

    removed = await mode_tools.delete_by_mode("edit-character")

    # The count of rows removed, not a bool.
    assert removed == 2

    # That mode's set is cleared.
    assert len(await mode_tools.list_by_mode("edit-character")) == 0

    # The other mode's rows are intact.
    survivors = await mode_tools.list_by_mode("close-chapter")
    assert len(survivors) == 1
    assert survivors[0].mode_key == "close-chapter"
    assert survivors[0].tool_name == "web_search"


# DoD-4 (US-111.AC-1): a mode with no rows is a normal, non-error state (an
# unconfigured mode legitimately has none) — delete_by_mode returns 0 without
# raising, and touches nothing else.
async def test_mode_tools_delete_by_mode_returns_zero_when_empty__DoD4_US111_AC1(
    db: DbConfig,
):
    await mode_tools.create(ModeTool(mode_key="edit-fact", tool_name="web_search"))

    # No rows for this mode: 0, and no exception.
    removed = await mode_tools.delete_by_mode("write-chapter")
    assert removed == 0

    # Nothing else was removed.
    assert len(await mode_tools.list_by_mode("edit-fact")) == 1


# ---------------------------------------------------------------------------
# DoD-5 — subagent_tools.delete_by_sub_agent: scoped, count-returning
#         (US-113.AC-1)
# ---------------------------------------------------------------------------


# DoD-5 (US-113.AC-1): delete_by_sub_agent removes exactly the rows for the named
# sub-agent id, returns the number removed, and leaves another sub-agent's rows
# intact.
async def test_subagent_tools_delete_by_sub_agent_is_scoped__DoD5_US113_AC1(
    db: DbConfig,
):
    await subagent_tools.create(SubagentTool(sub_agent_id=100, tool_name="web_search"))
    await subagent_tools.create(SubagentTool(sub_agent_id=100, tool_name="write_text"))
    await subagent_tools.create(SubagentTool(sub_agent_id=200, tool_name="web_search"))

    removed = await subagent_tools.delete_by_sub_agent(100)

    assert removed == 2
    assert len(await subagent_tools.list_by_sub_agent(100)) == 0

    survivors = await subagent_tools.list_by_sub_agent(200)
    assert len(survivors) == 1
    assert survivors[0].sub_agent_id == 200
    assert survivors[0].tool_name == "web_search"


# DoD-5 (US-113.AC-1): a sub-agent with no tool rows is a normal, non-error state
# — delete_by_sub_agent returns 0 without raising and touches nothing else.
async def test_subagent_tools_delete_by_sub_agent_zero_when_empty__DoD5_US113_AC1(
    db: DbConfig,
):
    await subagent_tools.create(SubagentTool(sub_agent_id=300, tool_name="web_search"))

    removed = await subagent_tools.delete_by_sub_agent(999)
    assert removed == 0

    assert len(await subagent_tools.list_by_sub_agent(300)) == 1


# ---------------------------------------------------------------------------
# DoD-6 — mode_subagents.list_by_sub_agent: the reverse read (US-112.AC-2)
# ---------------------------------------------------------------------------


# DoD-6 (US-112.AC-2): list_by_sub_agent returns exactly the link rows for that
# sub-agent id, and a link row created from the mode side is visible through it —
# one row set, read from both directions.
async def test_mode_subagents_list_by_sub_agent_reads_one_row_set__DoD6_US112_AC2(
    db: DbConfig,
):
    # Created "from the mode side": the mode's sub-agent selection.
    from_mode_side = await mode_subagents.create(
        ModeSubagent(mode_key="edit-character", sub_agent_id=100)
    )
    await mode_subagents.create(ModeSubagent(mode_key="close-chapter", sub_agent_id=100))
    # A different sub-agent's link, which must not appear in the 100 read.
    await mode_subagents.create(ModeSubagent(mode_key="edit-character", sub_agent_id=200))

    listed = await mode_subagents.list_by_sub_agent(100)

    # Exactly this sub-agent's rows, both of them and only those.
    assert len(listed) == 2
    assert {row.sub_agent_id for row in listed} == {100}
    assert {row.mode_key for row in listed} == {"edit-character", "close-chapter"}

    # The very row written from the mode side is visible from the sub-agent side:
    # one row set, two editors.
    assert from_mode_side.id is not None
    assert from_mode_side.id in {row.id for row in listed}
    mode_side_read = await mode_subagents.list_by_mode("edit-character")
    assert from_mode_side.id in {row.id for row in mode_side_read}


# ---------------------------------------------------------------------------
# DoD-7 — mode_subagents bulk deletes each cut only their own slice (US-114.AC-2)
# ---------------------------------------------------------------------------


# DoD-7 (US-114.AC-2): delete_by_mode removes only that mode's slice — the
# sub-agent's links to OTHER modes stay intact.
async def test_mode_subagents_delete_by_mode_keeps_other_modes__DoD7_US114_AC2(
    db: DbConfig,
):
    await mode_subagents.create(ModeSubagent(mode_key="edit-character", sub_agent_id=100))
    await mode_subagents.create(ModeSubagent(mode_key="edit-character", sub_agent_id=200))
    await mode_subagents.create(ModeSubagent(mode_key="close-chapter", sub_agent_id=100))

    removed = await mode_subagents.delete_by_mode("edit-character")

    assert removed == 2
    assert len(await mode_subagents.list_by_mode("edit-character")) == 0

    # Sub-agent 100 keeps its link to the other mode.
    remaining = await mode_subagents.list_by_sub_agent(100)
    assert len(remaining) == 1
    assert remaining[0].mode_key == "close-chapter"
    assert remaining[0].sub_agent_id == 100


# DoD-7 (US-114.AC-2): delete_by_sub_agent removes only that sub-agent's slice —
# the mode's links to OTHER sub-agents stay intact.
async def test_mode_subagents_delete_by_sub_agent_keeps_other_agents__DoD7_US114_AC2(
    db: DbConfig,
):
    await mode_subagents.create(ModeSubagent(mode_key="edit-character", sub_agent_id=100))
    await mode_subagents.create(ModeSubagent(mode_key="edit-character", sub_agent_id=200))
    await mode_subagents.create(ModeSubagent(mode_key="close-chapter", sub_agent_id=100))

    removed = await mode_subagents.delete_by_sub_agent(100)

    assert removed == 2
    assert len(await mode_subagents.list_by_sub_agent(100)) == 0

    # The mode keeps its link to the other sub-agent.
    remaining = await mode_subagents.list_by_mode("edit-character")
    assert len(remaining) == 1
    assert remaining[0].sub_agent_id == 200
    assert remaining[0].mode_key == "edit-character"


# DoD-7 (US-114.AC-2): both mode_subagents bulk deletes share the count-returning,
# zero-is-not-an-error contract of the other two (status.md -> Skeleton, "the
# three bulk deletes return a count ... 0 is a normal, non-error result and must
# not raise").
async def test_mode_subagents_bulk_deletes_return_zero_when_empty__DoD7_US114_AC2(
    db: DbConfig,
):
    await mode_subagents.create(ModeSubagent(mode_key="edit-fact", sub_agent_id=500))

    assert await mode_subagents.delete_by_mode("write-chapter") == 0
    assert await mode_subagents.delete_by_sub_agent(999) == 0

    # Neither call touched the unrelated row.
    assert len(await mode_subagents.list_by_mode("edit-fact")) == 1
    assert len(await mode_subagents.list_by_sub_agent(500)) == 1
