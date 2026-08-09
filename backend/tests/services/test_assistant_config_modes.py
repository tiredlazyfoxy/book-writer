"""Tests for the mode half of the assistant-config service (feature 012, step 002).

Bound to the frozen skeleton signatures (status.md -> Skeleton -> Step 002):
    app.models.schemas.assistant_config
        class ToolResponse(BaseModel)                 name, description
        class ToolsListResponse(BaseModel)            items: list[ToolResponse]
        class AssistantModeResponse(BaseModel)        key, system_prompt, tool_names,
                                                      sub_agent_ids, created_at, modified_at
        class AssistantModesListResponse(BaseModel)   items: list[AssistantModeResponse]
        class UpdateAssistantModeRequest(BaseModel)   system_prompt: str | None,
                                                      tool_names: list[str],
                                                      sub_agent_ids: list[str]
    app.services.assistant_config
        class AssistantConfigErrorReason(str, enum.Enum)
            mode_not_found = "mode-not-found", unknown_tool = "unknown-tool",
            unknown_sub_agent = "unknown-sub-agent",
            sub_agent_disabled = "sub-agent-disabled"
        class AssistantConfigError(Exception)         __init__(reason, message="")
        async def list_tools() -> ToolsListResponse
        async def list_modes() -> AssistantModesListResponse
        async def save_mode(mode_key: str, req: UpdateAssistantModeRequest)
                            -> AssistantModeResponse

Arrangement uses the step-001 `db/` layer (already implemented and green, its own
frozen record in status.md -> Skeleton -> Step 001): `assistant_modes.
seed_default_modes / get_by_id / list_all / create / update`, `sub_agents.create
/ get_by_id`, `mode_tools.create / list_by_mode`, `mode_subagents.create /
list_by_mode`. Reading raw rows through `db/` is how "wrote nothing" is proved
independently of the service under test.

Expected values come from the step spec (002.mode-config-service.md DoD +
Interface intent + 002.context.md + context.md), never from implementation
internals:
    - DoD-1 (UC-095; US-110.AC-1): list_modes returns exactly the five seeded
      modes in DEFAULT_MODE_KEYS order — the tuple the spec names is
      ("edit-character", "edit-location", "edit-fact", "write-chapter",
      "close-chapter") (002.context.md -> "Mode ordering"); each mode carries its
      system_prompt, its selected tool names, its selected sub-agent ids AS
      STRINGS, and both timestamps. Interface intent also fixes the import-only
      edge case: a row whose key is not in DEFAULT_MODE_KEYS "sorts last, by key,
      rather than being dropped or raising";
    - DoD-2 (US-110.AC-1): a saved system_prompt is stored and read back by the
      next list_modes;
    - DoD-3 (US-110.AC-4, storage side): both `null` and "" are accepted and
      round-trip AS THE STORED VALUE — an unset prompt is a valid configured
      state, so "" must not be coerced to None nor rejected;
    - DoD-4 (US-111.AC-1): a saved tool selection is stored exactly, and a second
      save REPLACES rather than merges — a tool present before and absent after is
      gone (replace-set semantics, context.md -> "Replace-set semantics");
    - DoD-5 (US-111.AC-1; context.md -> scope decision 1): an empty tool list is
      accepted and yields zero mode_tool rows; an unconfigured mode reports zero
      tools, NEVER the whole registry — empty means *no tools*;
    - DoD-6 (US-112.AC-1): a saved sub-agent selection is stored exactly and a
      later save replaces it;
    - DoD-7 (US-111.AC-1, US-112.AC-1): an unknown tool name is refused with
      reason unknown-tool, a non-existent sub-agent id with unknown-sub-agent, and
      in both cases the mode's previously stored prompt, tool set and sub-agent set
      are UNCHANGED ("All validation happens before any write");
    - DoD-8 (US-114.AC-2): a `disabled` sub-agent is refused with reason
      sub-agent-disabled and nothing is written;
    - DoD-9 (UC-095 precondition): a mode key with no row is refused with reason
      mode-not-found; the mode load is step 1 of the saver's fixed order, so it
      wins over a tool-validation failure in the same request;
    - DoD-10 (US-111.AC-1, US-112.AC-1): a repeated tool name / sub-agent id is
      accepted and produces one link row per DISTINCT value — the unique
      constraints uq_mode_tool_mode_key_tool_name and
      uq_mode_subagent_mode_key_sub_agent_id are never violated;
    - DoD-11 (UC-095 step 3): the catalogue returns one entry per TOOL_REGISTRY
      ToolDef, in registry order, carrying only `name` and `description` — no
      args_schema, no callable, no key derived from either.
    (DoD-12 is [manual/live] — no automated test.)

Registry independence: TOOL_REGISTRY has exactly one entry today (`web_search`),
but nothing here hard-codes that count (context.md -> "Inbound dependency").
Every tool-name expectation is DERIVED from the imported registry, so these tests
stay correct for zero, one or many entries; the two cases that need at least one
valid tool name to have any bite are skipped when the registry is empty.

Not asserted, deliberately: the ORDER of `tool_names` / `sub_agent_ids` within one
mode (the spec fixes the order of the mode LIST only, from DEFAULT_MODE_KEYS), and
anything about the runtime that consumes this config (013.codex owns tool gating
and prompt composition — context.md -> "Out of scope").

Async tests use asyncio_mode = "auto"; the `db` fixture (conftest) supplies an
initialized throwaway temp-SQLite engine (init_engine + init_db), so the schema is
present and each test is isolated. The catalogue tests need no database at all.
SQLite does not enforce FKs here (see tests/test_data_domain_assistant_links.py),
so link rows need no parent rows. No network in any test.
"""

from datetime import datetime

import pytest

from app.db import assistant_modes, mode_subagents, mode_tools, sub_agents
from app.db.engine import DbConfig
from app.models.assistant_mode import AssistantMode
from app.models.mode_subagent import ModeSubagent
from app.models.mode_tool import ModeTool
from app.models.schemas.assistant_config import ToolResponse, UpdateAssistantModeRequest
from app.models.sub_agent import SubAgent
from app.services import assistant_config as config_service
from app.services.tools import TOOL_REGISTRY

# The fixed five, in the presentation order the spec names
# (002.context.md -> "Mode ordering"). Written out here rather than read from
# DEFAULT_MODE_KEYS so the ordering assertion is anchored in the spec, not in the
# constant it is supposed to follow; the two are cross-checked in the DoD-1 test.
EXPECTED_MODE_ORDER = (
    "edit-character",
    "edit-location",
    "edit-fact",
    "write-chapter",
    "close-chapter",
)

# Every tool name the catalogue can offer, DERIVED from the registry — never a
# literal, never a count.
ALL_TOOL_NAMES = [tool.name for tool in TOOL_REGISTRY]

# A name the registry does not contain (asserted, not assumed, at point of use).
UNKNOWN_TOOL_NAME = "definitely-not-a-registered-tool"

# Needs at least one real tool name to demonstrate anything.
requires_a_tool = pytest.mark.skipif(
    len(TOOL_REGISTRY) == 0,
    reason="the clause needs at least one valid TOOL_REGISTRY name to have bite",
)


# ---------------------------------------------------------------------------
# helpers (module-local, per the suite convention: no shared fixtures)
# ---------------------------------------------------------------------------


def _req(
    system_prompt: str | None,
    tool_names: list[str],
    sub_agent_ids: list[str],
) -> UpdateAssistantModeRequest:
    """The full-replace request body: all three fields always explicit."""
    return UpdateAssistantModeRequest(
        system_prompt=system_prompt,
        tool_names=tool_names,
        sub_agent_ids=sub_agent_ids,
    )


async def _create_sub_agent(name: str, *, disabled: bool = False) -> SubAgent:
    created = await sub_agents.create(
        SubAgent(
            name=name,
            system_prompt=f"System prompt for {name}.",
            disabled=disabled,
            llm_server_id=None,
            model_name=None,
        )
    )
    assert created.id is not None
    return created


async def _listed_mode(mode_key: str):
    """The one AssistantModeResponse for `mode_key`, read through list_modes."""
    listed = await config_service.list_modes()
    matches = [mode for mode in listed.items if mode.key == mode_key]
    assert len(matches) == 1
    return matches[0]


async def _stored_state(
    mode_key: str,
) -> tuple[str | None, datetime | None, list[str], list[int]]:
    """The mode's stored configuration, read straight from `db/`.

    Prompt, modified_at, tool names and sub-agent ids as SORTED LISTS (so a
    duplicate row would change the value) — the snapshot the "a rejected save
    wrote nothing" clauses of DoD-7 / DoD-8 compare before against after.
    """
    row = await assistant_modes.get_by_id(mode_key)
    assert row is not None
    tool_rows = await mode_tools.list_by_mode(mode_key)
    link_rows = await mode_subagents.list_by_mode(mode_key)
    return (
        row.system_prompt,
        row.modified_at,
        sorted(tool_row.tool_name for tool_row in tool_rows),
        sorted(link_row.sub_agent_id for link_row in link_rows),
    )


# ---------------------------------------------------------------------------
# DoD-1 — list_modes: the fixed five, in order, with their selections
# ---------------------------------------------------------------------------


# DoD-1 (UC-095; US-110.AC-1): list_modes returns exactly the five seeded modes in
# DEFAULT_MODE_KEYS order, each carrying its stored system_prompt, its selected
# tool names, its selected sub-agent ids as STRINGS, and both timestamps.
# Arranged entirely through `db/` so the lister is what is under test.
async def test_list_modes_returns_fixed_five_in_order__DoD1_UC095_US110_AC1(
    db: DbConfig,
):
    await assistant_modes.seed_default_modes()

    # The constant the service orders by is the fixed five the spec names.
    assert tuple(assistant_modes.DEFAULT_MODE_KEYS) == EXPECTED_MODE_ORDER

    created_at = datetime(2026, 7, 26, 8, 0, 0)
    modified_at = datetime(2026, 7, 26, 9, 30, 0)

    # One mode gets a full configuration: prompt + tools + sub-agents + explicit
    # timestamps.
    configured_key = "edit-fact"
    row = await assistant_modes.get_by_id(configured_key)
    assert row is not None
    row.system_prompt = "You edit facts."
    row.created_at = created_at
    row.modified_at = modified_at
    await assistant_modes.update(row)

    # The lister hand-maps the stored mode_tool rows; it does not validate them
    # against the catalogue (validation is the SAVER's job, Interface intent step
    # 2), and `tool_name` is "a string reference into TOOL_REGISTRY, never an FK"
    # whose tool may since have been retired (assistant-config.md -> "Tool
    # registry"). Two arbitrary stored names therefore both exercise multiplicity
    # and keep this test independent of how many entries the registry has.
    stored_tool_names = ["retired-tool-from-an-earlier-release", "another-stored-tool"]
    for tool_name in stored_tool_names:
        await mode_tools.create(ModeTool(mode_key=configured_key, tool_name=tool_name))

    agent_a = await _create_sub_agent("alpha-agent")
    agent_b = await _create_sub_agent("beta-agent")
    for agent in (agent_a, agent_b):
        assert agent.id is not None
        await mode_subagents.create(
            ModeSubagent(mode_key=configured_key, sub_agent_id=agent.id)
        )

    # A second mode carries a prompt but no selections at all.
    other_key = "close-chapter"
    other_row = await assistant_modes.get_by_id(other_key)
    assert other_row is not None
    other_row.system_prompt = "You close chapters."
    await assistant_modes.update(other_row)

    listed = await config_service.list_modes()

    # Exactly the five seeded modes, in DEFAULT_MODE_KEYS order.
    assert [mode.key for mode in listed.items] == list(EXPECTED_MODE_ORDER)
    assert len(listed.items) == 5

    by_key = {mode.key: mode for mode in listed.items}

    configured = by_key[configured_key]
    assert configured.system_prompt == "You edit facts."
    # The stored selections, hand-mapped from the link rows (order within a mode
    # is not part of the contract).
    assert sorted(configured.tool_names) == sorted(stored_tool_names)
    assert set(configured.sub_agent_ids) == {str(agent_a.id), str(agent_b.id)}
    # Sub-agent ids cross the wire as strings (context.md -> "Every id is a `str`
    # at the JSON boundary").
    assert all(isinstance(value, str) for value in configured.sub_agent_ids)
    # Both timestamps are carried through.
    assert configured.created_at == created_at
    assert configured.modified_at == modified_at

    # The prompt-only mode: its prompt, and empty selections.
    other = by_key[other_key]
    assert other.system_prompt == "You close chapters."
    assert other.tool_names == []
    assert other.sub_agent_ids == []

    # A seeded, never-configured mode is listed with the prompt the SEED gave it,
    # rather than being dropped from the list.
    #
    # Amended by feature 024 (chat-agent-loop), decision D4: seed_default_modes()
    # now writes a real non-blank system_prompt for a key with no existing row
    # instead of None (024/plan.md -> DoD-4 / DoD-12), so "never configured by an
    # admin" no longer means "null prompt". The clause this case exists for — an
    # unconfigured mode is still LISTED, with empty selections — is unchanged; only
    # the prompt's expected value moved. The prompt text itself stays untested
    # (024/plan.md -> Test plan -> "Not tested").
    untouched = by_key["write-chapter"]
    assert untouched.system_prompt is not None
    assert untouched.system_prompt.strip() != ""
    assert untouched.tool_names == []
    assert untouched.sub_agent_ids == []


# DoD-1 (UC-095): the presentation order is imposed by the service, not by the
# unordered db read, and a row whose key is NOT in DEFAULT_MODE_KEYS (seeding
# cannot produce one, but an import can) "sorts last, by key, rather than being
# dropped or raising" (Interface intent -> "A mode lister"). The two foreign rows
# are created in reverse-alphabetical order so insertion order cannot masquerade
# as key order.
async def test_list_modes_sorts_unknown_keys_last_by_key__DoD1_UC095(db: DbConfig):
    await assistant_modes.seed_default_modes()

    foreign_at = datetime(2026, 7, 26, 7, 0, 0)
    for foreign_key in ("zz-imported-mode", "aa-imported-mode"):
        assert foreign_key not in assistant_modes.DEFAULT_MODE_KEYS
        await assistant_modes.create(
            AssistantMode(
                key=foreign_key,
                system_prompt=None,
                created_at=foreign_at,
                modified_at=foreign_at,
            )
        )

    listed = await config_service.list_modes()

    assert [mode.key for mode in listed.items] == [
        *EXPECTED_MODE_ORDER,
        "aa-imported-mode",
        "zz-imported-mode",
    ]


# ---------------------------------------------------------------------------
# DoD-2 — a saved prompt is stored and read back (US-110.AC-1)
# ---------------------------------------------------------------------------


# DoD-2 (US-110.AC-1): save_mode stores the mode's system_prompt; the returned DTO
# carries it (the saver returns the freshly rebuilt mode) and the next list_modes
# reads it back.
async def test_save_mode_stores_prompt_and_lists_it_back__DoD2_US110_AC1(db: DbConfig):
    await assistant_modes.seed_default_modes()

    saved = await config_service.save_mode(
        "write-chapter",
        _req("You write the next chapter.", [], []),
    )

    assert saved.key == "write-chapter"
    assert saved.system_prompt == "You write the next chapter."

    listed = await _listed_mode("write-chapter")
    assert listed.system_prompt == "You write the next chapter."

    # ...and it really is on the row.
    prompt, _modified_at, _tools, _agents = await _stored_state("write-chapter")
    assert prompt == "You write the next chapter."

    # Saving a different prompt replaces the stored one.
    await config_service.save_mode("write-chapter", _req("A different prompt.", [], []))
    assert (await _listed_mode("write-chapter")).system_prompt == "A different prompt."


# ---------------------------------------------------------------------------
# DoD-3 — an unset prompt is a valid stored state (US-110.AC-4, storage side)
# ---------------------------------------------------------------------------


# DoD-3 (US-110.AC-4): a mode's prompt may be cleared. Saving `null` and saving an
# empty string are BOTH accepted (no error) and BOTH round-trip as the stored
# value — "" is stored as "" and must not be coerced to None, None is stored as
# None. An unset prompt is a configured state, not an error.
async def test_save_mode_accepts_null_and_empty_prompt__DoD3_US110_AC4(db: DbConfig):
    await assistant_modes.seed_default_modes()

    # Start from a non-empty stored prompt so each clearing has something to clear.
    await config_service.save_mode("edit-character", _req("Original prompt.", [], []))

    # 1. Saving an empty string: accepted, stored verbatim as "".
    saved_empty = await config_service.save_mode("edit-character", _req("", [], []))
    assert saved_empty.system_prompt == ""
    assert saved_empty.system_prompt is not None
    listed_empty = await _listed_mode("edit-character")
    assert listed_empty.system_prompt == ""
    assert listed_empty.system_prompt is not None
    prompt, _modified_at, _tools, _agents = await _stored_state("edit-character")
    assert prompt == ""

    # 2. Saving null: accepted, stored as None.
    saved_null = await config_service.save_mode("edit-character", _req(None, [], []))
    assert saved_null.system_prompt is None
    assert (await _listed_mode("edit-character")).system_prompt is None
    prompt, _modified_at, _tools, _agents = await _stored_state("edit-character")
    assert prompt is None

    # 3. ...and back to an empty string from null, so neither direction is a
    #    one-way trip.
    saved_empty_again = await config_service.save_mode(
        "edit-character", _req("", [], [])
    )
    assert saved_empty_again.system_prompt == ""


# ---------------------------------------------------------------------------
# DoD-4 — tool selection is stored exactly and REPLACED, not merged (US-111.AC-1)
# ---------------------------------------------------------------------------


# DoD-4 (US-111.AC-1): saving a tool selection stores exactly that set on the mode,
# and saving again with a different set REPLACES it — a tool present before and
# absent after is gone. Both selections are derived from TOOL_REGISTRY (the second
# drops the first name), so the clause holds for one or many registry entries.
@requires_a_tool
async def test_save_mode_tool_selection_replaces_not_merges__DoD4_US111_AC1(
    db: DbConfig,
):
    await assistant_modes.seed_default_modes()

    first_selection = list(ALL_TOOL_NAMES)
    dropped_name = first_selection[0]
    second_selection = first_selection[1:]

    saved = await config_service.save_mode(
        "edit-location", _req(None, first_selection, [])
    )
    assert set(saved.tool_names) == set(first_selection)
    assert len(saved.tool_names) == len(first_selection)
    _prompt, _modified_at, stored_tools, _agents = await _stored_state("edit-location")
    assert stored_tools == sorted(first_selection)

    resaved = await config_service.save_mode(
        "edit-location", _req(None, second_selection, [])
    )

    # Exactly the new set — a replace, not a merge.
    assert set(resaved.tool_names) == set(second_selection)
    assert len(resaved.tool_names) == len(second_selection)
    # The tool present before and absent after is gone.
    assert dropped_name not in resaved.tool_names

    listed = await _listed_mode("edit-location")
    assert set(listed.tool_names) == set(second_selection)
    assert dropped_name not in listed.tool_names

    _prompt, _modified_at, stored_tools, _agents = await _stored_state("edit-location")
    assert stored_tools == sorted(second_selection)


# ---------------------------------------------------------------------------
# DoD-5 — empty means NO tools, and an unconfigured mode has none (US-111.AC-1)
# ---------------------------------------------------------------------------


# DoD-5 (US-111.AC-1; context.md -> scope decision 1): saving an EMPTY tool list is
# accepted and leaves the mode with zero mode_tool rows.
@requires_a_tool
async def test_save_mode_empty_tool_list_clears_all_rows__DoD5_US111_AC1(db: DbConfig):
    await assistant_modes.seed_default_modes()

    # Something to clear first.
    await config_service.save_mode(
        "edit-location", _req(None, list(ALL_TOOL_NAMES), [])
    )
    _prompt, _modified_at, stored_tools, _agents = await _stored_state("edit-location")
    assert stored_tools == sorted(ALL_TOOL_NAMES)

    saved = await config_service.save_mode("edit-location", _req(None, [], []))

    # Accepted, and zero tools on the mode.
    assert saved.tool_names == []
    assert (await _listed_mode("edit-location")).tool_names == []
    # Zero mode_tool rows — not "everything".
    assert await mode_tools.list_by_mode("edit-location") == []


# DoD-5 (US-111.AC-1; context.md -> scope decision 1): an UNCONFIGURED mode reports
# zero tools, never the whole registry — an empty allowlist means *no tools*, and
# the "never saved" and "saved empty" states are indistinguishable by design.
async def test_unconfigured_mode_reports_zero_tools_not_registry__DoD5_US111_AC1(
    db: DbConfig,
):
    await assistant_modes.seed_default_modes()

    listed = await config_service.list_modes()

    # No save has happened on any mode: every one reports an empty tool list.
    for mode in listed.items:
        assert mode.tool_names == []

    # An explicit empty save is indistinguishable from never having been
    # configured.
    saved = await config_service.save_mode("edit-fact", _req(None, [], []))
    assert saved.tool_names == []
    assert (await _listed_mode("edit-fact")).tool_names == []
    assert (await _listed_mode("edit-location")).tool_names == []


# ---------------------------------------------------------------------------
# DoD-6 — sub-agent selection is stored exactly and replaced (US-112.AC-1)
# ---------------------------------------------------------------------------


# DoD-6 (US-112.AC-1): saving a sub-agent selection stores exactly that set as
# accessible from the mode, and a later save replaces it. Ids go in as strings and
# come back as strings.
async def test_save_mode_sub_agent_selection_replaces__DoD6_US112_AC1(db: DbConfig):
    await assistant_modes.seed_default_modes()

    agent_a = await _create_sub_agent("alpha-agent")
    agent_b = await _create_sub_agent("beta-agent")
    agent_c = await _create_sub_agent("gamma-agent")

    saved = await config_service.save_mode(
        "edit-character",
        _req(None, [], [str(agent_a.id), str(agent_b.id)]),
    )

    assert set(saved.sub_agent_ids) == {str(agent_a.id), str(agent_b.id)}
    assert len(saved.sub_agent_ids) == 2
    assert all(isinstance(value, str) for value in saved.sub_agent_ids)

    # Accessible from the mode in the shared link table.
    _prompt, _modified_at, _tools, stored_ids = await _stored_state("edit-character")
    assert stored_ids == sorted([agent_a.id, agent_b.id])

    resaved = await config_service.save_mode(
        "edit-character",
        _req(None, [], [str(agent_b.id), str(agent_c.id)]),
    )

    # Exactly the new set: `a` is gone, `c` is in, `b` stayed.
    assert set(resaved.sub_agent_ids) == {str(agent_b.id), str(agent_c.id)}
    assert len(resaved.sub_agent_ids) == 2
    assert str(agent_a.id) not in resaved.sub_agent_ids

    listed = await _listed_mode("edit-character")
    assert set(listed.sub_agent_ids) == {str(agent_b.id), str(agent_c.id)}

    _prompt, _modified_at, _tools, stored_ids = await _stored_state("edit-character")
    assert stored_ids == sorted([agent_b.id, agent_c.id])

    # An empty selection is accepted and clears the set.
    cleared = await config_service.save_mode("edit-character", _req(None, [], []))
    assert cleared.sub_agent_ids == []
    assert await mode_subagents.list_by_mode("edit-character") == []


# ---------------------------------------------------------------------------
# DoD-7 — unknown tool / unknown sub-agent refused, and NOTHING is written
#         (US-111.AC-1, US-112.AC-1)
# ---------------------------------------------------------------------------


# DoD-7 (US-111.AC-1): a save naming a tool absent from TOOL_REGISTRY is refused
# with the unknown-tool reason, and the mode's previously stored prompt, tool set
# and sub-agent set are UNCHANGED — "All validation happens before any write", so
# the refused request must not have landed its prompt, its (valid) tool names, its
# sub-agent ids, or a new modified_at.
async def test_save_mode_unknown_tool_refused_and_writes_nothing__DoD7_US111_AC1(
    db: DbConfig,
):
    await assistant_modes.seed_default_modes()

    agent = await _create_sub_agent("alpha-agent")

    # A committed, non-empty starting configuration to protect.
    await config_service.save_mode(
        "write-chapter",
        _req("Original prompt.", list(ALL_TOOL_NAMES), [str(agent.id)]),
    )
    before = await _stored_state("write-chapter")
    before_listed = await _listed_mode("write-chapter")

    # The offending name really is absent from the catalogue.
    assert UNKNOWN_TOOL_NAME not in ALL_TOOL_NAMES

    with pytest.raises(config_service.AssistantConfigError) as exc:
        await config_service.save_mode(
            "write-chapter",
            _req("A prompt that must not land.", [UNKNOWN_TOOL_NAME], []),
        )

    assert exc.value.reason == config_service.AssistantConfigErrorReason.unknown_tool
    assert exc.value.reason.value == "unknown-tool"

    # Nothing was written: prompt, tool set, sub-agent set (and modified_at) are
    # exactly as before.
    assert await _stored_state("write-chapter") == before

    after_listed = await _listed_mode("write-chapter")
    assert after_listed.system_prompt == before_listed.system_prompt
    assert sorted(after_listed.tool_names) == sorted(before_listed.tool_names)
    assert sorted(after_listed.sub_agent_ids) == sorted(before_listed.sub_agent_ids)


# DoD-7 (US-112.AC-1): a save naming a sub-agent id no row carries is refused with
# the unknown-sub-agent reason and writes nothing. A value that does not parse as
# an id is likewise an id no row carries (Interface intent step 3: "it must parse
# as an id, name an existing SubAgent (else unknown-sub-agent)") — never a 500.
async def test_save_mode_unknown_sub_agent_refused_and_writes_nothing__DoD7_US112_AC1(
    db: DbConfig,
):
    await assistant_modes.seed_default_modes()

    agent = await _create_sub_agent("alpha-agent")

    await config_service.save_mode(
        "write-chapter",
        _req("Original prompt.", list(ALL_TOOL_NAMES), [str(agent.id)]),
    )
    before = await _stored_state("write-chapter")
    before_listed = await _listed_mode("write-chapter")

    # An id no SubAgent row carries.
    missing_id = 424242424242
    assert await sub_agents.get_by_id(missing_id) is None

    for bad_id in (str(missing_id), "not-an-id", ""):
        with pytest.raises(config_service.AssistantConfigError) as exc:
            await config_service.save_mode(
                "write-chapter",
                _req("A prompt that must not land.", [], [bad_id]),
            )
        assert (
            exc.value.reason
            == config_service.AssistantConfigErrorReason.unknown_sub_agent
        )
        assert exc.value.reason.value == "unknown-sub-agent"

        # Nothing written by this attempt.
        assert await _stored_state("write-chapter") == before

    after_listed = await _listed_mode("write-chapter")
    assert after_listed.system_prompt == before_listed.system_prompt
    assert sorted(after_listed.tool_names) == sorted(before_listed.tool_names)
    assert sorted(after_listed.sub_agent_ids) == sorted(before_listed.sub_agent_ids)


# ---------------------------------------------------------------------------
# DoD-8 — a disabled sub-agent cannot be attached (US-114.AC-2)
# ---------------------------------------------------------------------------


# DoD-8 (US-114.AC-2): a save naming a `disabled` sub-agent is refused with the
# sub-agent-disabled reason (distinct from unknown-sub-agent: the row exists) and
# writes nothing — a disabled sub-agent is detached from every mode and cannot be
# re-attached while disabled.
async def test_save_mode_disabled_sub_agent_refused_and_writes_nothing__DoD8_US114_AC2(
    db: DbConfig,
):
    await assistant_modes.seed_default_modes()

    enabled = await _create_sub_agent("alpha-agent")
    disabled = await _create_sub_agent("zeta-agent", disabled=True)

    await config_service.save_mode(
        "close-chapter",
        _req("Original prompt.", list(ALL_TOOL_NAMES), [str(enabled.id)]),
    )
    before = await _stored_state("close-chapter")
    before_listed = await _listed_mode("close-chapter")

    # The row exists — this is not an unknown id.
    existing = await sub_agents.get_by_id(disabled.id)
    assert existing is not None
    assert existing.disabled is True

    with pytest.raises(config_service.AssistantConfigError) as exc:
        await config_service.save_mode(
            "close-chapter",
            _req(
                "A prompt that must not land.",
                [],
                [str(enabled.id), str(disabled.id)],
            ),
        )

    assert (
        exc.value.reason
        == config_service.AssistantConfigErrorReason.sub_agent_disabled
    )
    assert exc.value.reason.value == "sub-agent-disabled"

    # Nothing was written — including the valid sub-agent id that shared the
    # request.
    assert await _stored_state("close-chapter") == before

    after_listed = await _listed_mode("close-chapter")
    assert after_listed.system_prompt == before_listed.system_prompt
    assert sorted(after_listed.tool_names) == sorted(before_listed.tool_names)
    assert sorted(after_listed.sub_agent_ids) == sorted(before_listed.sub_agent_ids)
    assert str(disabled.id) not in after_listed.sub_agent_ids


# ---------------------------------------------------------------------------
# DoD-9 — a mode key with no row is refused (UC-095 precondition)
# ---------------------------------------------------------------------------


# DoD-9 (UC-095 precondition): a save for a mode key that has no row is refused
# with the mode-not-found reason — the mode is one of the fixed system set of five,
# so an arbitrary key is not creatable through this path. Loading the mode is step 1
# of the saver's fixed order, so a request that is ALSO invalid on its tool names
# still fails with mode-not-found.
async def test_save_mode_missing_mode_key_refused__DoD9_UC095(db: DbConfig):
    await assistant_modes.seed_default_modes()

    missing_key = "no-such-mode"
    assert missing_key not in assistant_modes.DEFAULT_MODE_KEYS
    assert await assistant_modes.get_by_id(missing_key) is None

    with pytest.raises(config_service.AssistantConfigError) as exc:
        await config_service.save_mode(missing_key, _req("A prompt.", [], []))

    assert exc.value.reason == config_service.AssistantConfigErrorReason.mode_not_found
    assert exc.value.reason.value == "mode-not-found"

    # The refused save created nothing: no row, and the list is still the five.
    assert await assistant_modes.get_by_id(missing_key) is None
    listed = await config_service.list_modes()
    assert [mode.key for mode in listed.items] == list(EXPECTED_MODE_ORDER)

    # The mode load happens before tool validation, so mode-not-found wins over
    # an unknown tool name in the same request.
    with pytest.raises(config_service.AssistantConfigError) as exc:
        await config_service.save_mode(
            missing_key, _req(None, [UNKNOWN_TOOL_NAME], [])
        )
    assert exc.value.reason == config_service.AssistantConfigErrorReason.mode_not_found


# ---------------------------------------------------------------------------
# DoD-10 — duplicates are accepted, one link row per distinct value
#          (US-111.AC-1, US-112.AC-1)
# ---------------------------------------------------------------------------


# DoD-10 (US-111.AC-1): a request repeating the same tool name twice is ACCEPTED
# (no error) and produces one mode_tool row per distinct name — the
# uq_mode_tool_mode_key_tool_name constraint is never violated.
@requires_a_tool
async def test_save_mode_deduplicates_repeated_tool_name__DoD10_US111_AC1(
    db: DbConfig,
):
    await assistant_modes.seed_default_modes()

    repeated = ALL_TOOL_NAMES[0]
    requested = [repeated, *ALL_TOOL_NAMES, repeated]
    distinct = sorted(set(requested))

    saved = await config_service.save_mode("edit-fact", _req(None, requested, []))

    # One entry per distinct name, no duplicates in the payload.
    assert sorted(saved.tool_names) == distinct
    assert len(saved.tool_names) == len(distinct)

    rows = await mode_tools.list_by_mode("edit-fact")
    assert len(rows) == len(distinct)
    assert sorted(row.tool_name for row in rows) == distinct

    listed = await _listed_mode("edit-fact")
    assert sorted(listed.tool_names) == distinct


# DoD-10 (US-112.AC-1): a request repeating the same sub-agent id twice is ACCEPTED
# and produces one mode_subagent row per distinct id — the
# uq_mode_subagent_mode_key_sub_agent_id constraint is never violated.
async def test_save_mode_deduplicates_repeated_sub_agent_id__DoD10_US112_AC1(
    db: DbConfig,
):
    await assistant_modes.seed_default_modes()

    agent_a = await _create_sub_agent("alpha-agent")
    agent_b = await _create_sub_agent("beta-agent")
    requested = [
        str(agent_a.id),
        str(agent_b.id),
        str(agent_a.id),
        str(agent_b.id),
    ]

    saved = await config_service.save_mode("edit-fact", _req(None, [], requested))

    assert set(saved.sub_agent_ids) == {str(agent_a.id), str(agent_b.id)}
    assert len(saved.sub_agent_ids) == 2

    rows = await mode_subagents.list_by_mode("edit-fact")
    assert len(rows) == 2
    assert sorted(row.sub_agent_id for row in rows) == sorted(
        [agent_a.id, agent_b.id]
    )

    listed = await _listed_mode("edit-fact")
    assert set(listed.sub_agent_ids) == {str(agent_a.id), str(agent_b.id)}
    assert len(listed.sub_agent_ids) == 2


# ---------------------------------------------------------------------------
# DoD-11 — the tool catalogue: one entry per ToolDef, registry order,
#          name + description ONLY (UC-095 step 3)
# ---------------------------------------------------------------------------


# DoD-11 (UC-095 step 3): list_tools returns one entry per TOOL_REGISTRY ToolDef,
# in registry declaration order, with `name` and `description` taken from the
# registry. The expectation is DERIVED from the imported registry, so this holds
# for zero, one or many entries — nothing here knows the count.
async def test_list_tools_mirrors_registry_in_order__DoD11_UC095():
    catalogue = await config_service.list_tools()

    assert [item.name for item in catalogue.items] == [
        tool.name for tool in TOOL_REGISTRY
    ]
    assert len(catalogue.items) == len(TOOL_REGISTRY)

    for item, tool in zip(catalogue.items, TOOL_REGISTRY):
        assert item.name == tool.name
        assert item.description == tool.description


# DoD-11 (UC-095 step 3): a catalogue entry carries ONLY `name` and
# `description` — no args_schema, no callable, and no key derived from either
# anywhere in the payload. Asserted on the serialized payload (the wire shape) and
# on the DTO itself, so an extra field cannot hide behind an alias or a private
# attribute.
async def test_list_tools_payload_exposes_only_name_and_description__DoD11_UC095():
    catalogue = await config_service.list_tools()

    # The DTO's declared surface is exactly the two fields.
    assert set(ToolResponse.model_fields) == {"name", "description"}

    payload = catalogue.model_dump(mode="json")

    # A list envelope keyed `items`, per the codebase convention.
    assert set(payload) == {"items"}

    for entry in payload["items"]:
        assert set(entry) == {"name", "description"}
        assert isinstance(entry["name"], str)
        assert isinstance(entry["description"], str)

    for item in catalogue.items:
        assert not hasattr(item, "args_schema")
        assert not hasattr(item, "callable")


# DoD-11 (UC-095 step 3): the catalogue is a pure read of the registry — the same
# call made twice yields the same entries, and it never mutates the registry it
# maps (this step reads TOOL_REGISTRY; it never defines, extends or re-declares
# it — context.md -> "Inbound dependency").
async def test_list_tools_is_a_pure_read_of_the_registry__DoD11_UC095():
    registry_before = [(tool.name, tool.description) for tool in TOOL_REGISTRY]

    first = await config_service.list_tools()
    second = await config_service.list_tools()

    assert [(item.name, item.description) for item in first.items] == [
        (item.name, item.description) for item in second.items
    ]
    assert [
        (tool.name, tool.description) for tool in TOOL_REGISTRY
    ] == registry_before
    assert [(item.name, item.description) for item in first.items] == registry_before
