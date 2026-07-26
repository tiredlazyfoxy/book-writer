"""Tests for the sub-agent link sets and disable/enable (feature 012, step 004).

Bound to the frozen skeleton signatures (status.md -> Skeleton -> Step 004, which
extends the Step 002 and Step 003 records):
    app.models.schemas.assistant_config
        class CreateSubAgentRequest(BaseModel)  name: str, system_prompt: str,
                                                llm_server_id: str | None,
                                                model_name: str | None,
                                                tool_names: list[str] = [],
                                                mode_keys: list[str] = []
        class UpdateSubAgentRequest(BaseModel)  the same six fields; NO `disabled`
        class SubAgentResponse(BaseModel)       UNCHANGED — already carries
                                                `tool_names` and `mode_keys`
        class UpdateAssistantModeRequest(BaseModel)  system_prompt: str | None,
                                                tool_names: list[str],
                                                sub_agent_ids: list[str]
                                                (all three required — step 002)
    app.services.assistant_config
        async def create_sub_agent(req: CreateSubAgentRequest) -> SubAgentResponse
        async def update_sub_agent(sub_agent_id: str, req: UpdateSubAgentRequest)
                                   -> SubAgentResponse
        async def set_sub_agent_disabled(sub_agent_id: str, disabled: bool)
                                   -> SubAgentResponse
        async def list_sub_agents() -> SubAgentsListResponse
        async def list_modes() -> AssistantModesListResponse            (step 002)
        async def save_mode(mode_key: str, req: UpdateAssistantModeRequest)
                                   -> AssistantModeResponse             (step 002)
        class AssistantConfigError(Exception)   __init__(reason, message="")
        class AssistantConfigErrorReason(str, enum.Enum) — NO new member in this
            step: `mode_not_found` (step 002) is REUSED for an unknown `mode_key`
            in a sub-agent's mode selection, alongside `unknown_tool`,
            `sub_agent_disabled` (step 002) and `sub_agent_not_found` (step 003).

The two new request fields DEFAULT TO EMPTY on both create and update — the only
defaulted fields in this feature — so a caller may omit them entirely and gets a
sub-agent with no selections. That default is exercised directly in the DoD-5
test by constructing a request without them.

`set_sub_agent_disabled` takes the id as a **`str`** and reuses the step-003
parse, exactly as `update_sub_agent` does: an ill-formed id and a missing row are
both `sub-agent-not-found`, never an escaping ValueError (DoD-13).

The two internal replace-set helpers (`_replace_sub_agent_tools` /
`_replace_sub_agent_modes`) WRITE but do not VALIDATE — validation is hoisted
into the create/update paths — so nothing here calls them; every clause is
exercised through the public surface, which is also what the DoD describes.

Arrangement uses the step-001 `db/` layer and the 008 tables (implemented and
green): `assistant_modes.seed_default_modes / get_by_id`, `sub_agents.create /
get_by_id / get_by_name / list_all`, `subagent_tools.create / list_by_sub_agent`,
`mode_subagents.create / list_by_mode / list_by_sub_agent`, `llm_servers.create`.
Reading raw rows through `db/` is how "nothing was written" is proved
independently of the service under test, and seeding a `SubAgent` row directly is
how a `disabled` sub-agent is arranged without depending on the setter that is
itself under test.

Expected values come from the step spec (004.subagent-links-and-disable.md DoD +
Interface intent + 004.context.md + context.md), never from implementation
internals:
    - DoD-1 (UC-096 steps 4-5; US-113.AC-1): a create carrying a tool selection
      and a mode selection STORES BOTH and the returned DTO carries them;
    - DoD-2 (US-113.AC-2, US-112.AC-2): a sub-agent created as accessible from a
      mode appears in that MODE's accessible sub-agent set when the mode is read
      back through the mode surface — one row set, two editors;
    - DoD-3 (US-112.AC-2): a link written from the MODE side is visible in that
      sub-agent's `mode_keys`, and re-saving from the SUB-AGENT side replaces the
      whole set FOR THAT SUB-AGENT while leaving other sub-agents' links to the
      same mode intact;
    - DoD-4 (US-114.AC-1): an update REPLACES the tool selection and the mode
      selection rather than merging — a value present before and absent after is
      gone;
    - DoD-5 (US-114.AC-1; context.md -> scope decision 1): an empty tool
      selection and an empty mode selection are both ACCEPTED and result in zero
      link rows of that kind — empty means none, omitted means empty;
    - DoD-6 (US-113.AC-1, US-114.AC-1): a tool absent from TOOL_REGISTRY is
      refused with unknown-tool and a `mode_key` with no AssistantMode row with
      mode-not-found (the REUSED step-002 reason); in both cases the sub-agent's
      stored scalars AND its existing links are unchanged, because every
      validation runs before any write;
    - DoD-7 (US-114.AC-1): a repeated tool name / repeated mode key produces one
      link row per DISTINCT value — uq_subagent_tool_sub_agent_id_tool_name and
      uq_mode_subagent_mode_key_sub_agent_id are never violated;
    - DoD-8 (UC-097 alternate flow; US-114.AC-2): disabling a sub-agent that two
      modes reference sets `disabled` true and removes its link rows from BOTH
      modes; the sub-agent's own row still exists;
    - DoD-9 (UC-097 — disabling is reversible): disabling KEEPS the sub-agent's
      `subagent_tool` rows;
    - DoD-10 (US-114.AC-3): re-enabling sets `disabled` false and leaves it
      attached to NO mode — the links deleted at disable time are not restored,
      and nothing else about the sub-agent moves;
    - DoD-11 (US-114.AC-3): after re-enabling, a mode may select it again and the
      link is stored;
    - DoD-12 (US-114.AC-2, US-114.AC-1): a NON-EMPTY mode selection on a
      currently disabled sub-agent is refused with sub-agent-disabled and writes
      nothing, while the same save with an EMPTY mode selection succeeds and
      still updates name, prompt, model and tools;
    - DoD-13 (UC-097 precondition): disabling or enabling an id with no row is
      refused with sub-agent-not-found.
    (DoD-14 is [manual/live] — no automated test.)

Registry independence: TOOL_REGISTRY has exactly one entry today (`web_search`),
but nothing here hard-codes that count (context.md -> "Inbound dependency").
Every tool-name expectation is DERIVED from the imported registry; the two cases
that need at least one valid name to have any bite are skipped when the registry
is empty. Where a stored `subagent_tool` row is only needed as data to survive an
operation, it is seeded through `db/` with an arbitrary name, so that clause
keeps its bite for zero, one or many registry entries.

Not asserted, deliberately: the ORDER within `tool_names` / `mode_keys` (the spec
fixes no order for a sub-agent's selections), and anything about the runtime that
consumes this configuration (013.codex owns tool gating and delegation —
context.md -> "Out of scope"). There is no hard delete anywhere in this feature,
so nothing here deletes a sub-agent.

Async tests use asyncio_mode = "auto"; the `db` fixture (conftest) supplies an
initialized throwaway temp-SQLite engine (init_engine + init_db), so the schema
is present and each test is isolated. No network in any test.
"""

import asyncio
from datetime import datetime, timezone

import pytest

from app.db import (
    assistant_modes,
    llm_servers,
    mode_subagents,
    sub_agents,
    subagent_tools,
)
from app.db.engine import DbConfig
from app.models.llm_server import LlmServer
from app.models.schemas.assistant_config import (
    AssistantModeResponse,
    CreateSubAgentRequest,
    SubAgentResponse,
    UpdateAssistantModeRequest,
    UpdateSubAgentRequest,
)
from app.models.sub_agent import SubAgent
from app.models.subagent_tool import SubagentTool
from app.services import assistant_config as config_service
from app.services.tools import TOOL_REGISTRY

# Four of the fixed five seeded modes (their existence is asserted by
# `_seed_modes`, never assumed).
MODE_A = "edit-fact"
MODE_B = "write-chapter"
MODE_C = "close-chapter"
MODE_D = "edit-character"

# A mode key no AssistantMode row carries (asserted at point of use).
MISSING_MODE_KEY = "no-such-mode"

# A tool name TOOL_REGISTRY does not contain (asserted at point of use).
UNKNOWN_TOOL_NAME = "definitely-not-a-registered-tool"

# Every tool name the catalogue can offer, DERIVED from the registry — never a
# literal, never a count.
ALL_TOOL_NAMES = [tool.name for tool in TOOL_REGISTRY]

# Stored `subagent_tool` names that are deliberately NOT registry entries: a
# `tool_name` is "a string reference into TOOL_REGISTRY, never an FK", so rows
# like these are arrangeable through `db/` and give the survive-a-disable clause
# bite whatever the registry currently holds.
STORED_TOOL_NAMES = ["retired-tool-from-an-earlier-release", "another-stored-tool"]

# An id no SubAgent row carries (asserted at point of use).
MISSING_ID = 424242424242

# Values that cannot be parsed as an id at all.
ILL_FORMED_IDS = ("not-an-id", "12x", "")

# Needs at least one real tool name to demonstrate anything.
requires_a_tool = pytest.mark.skipif(
    len(TOOL_REGISTRY) == 0,
    reason="the clause needs at least one valid TOOL_REGISTRY name to have bite",
)


# ---------------------------------------------------------------------------
# helpers (module-local, per the suite convention: no shared fixtures)
# ---------------------------------------------------------------------------


def _create_req(
    name: str,
    system_prompt: str,
    *,
    llm_server_id: str | None = None,
    model_name: str | None = None,
    tool_names: list[str] | None = None,
    mode_keys: list[str] | None = None,
) -> CreateSubAgentRequest:
    """The create body. The four scalars are required and always passed
    explicitly; the two selections are the feature's only defaulted fields and
    are passed explicitly here so each test states its own selection."""
    return CreateSubAgentRequest(
        name=name,
        system_prompt=system_prompt,
        llm_server_id=llm_server_id,
        model_name=model_name,
        tool_names=list(tool_names or []),
        mode_keys=list(mode_keys or []),
    )


def _update_req(
    name: str,
    system_prompt: str,
    *,
    llm_server_id: str | None = None,
    model_name: str | None = None,
    tool_names: list[str] | None = None,
    mode_keys: list[str] | None = None,
) -> UpdateSubAgentRequest:
    """The full-replace update body; there is no `disabled` field on it —
    enable/disable is `set_sub_agent_disabled`'s alone."""
    return UpdateSubAgentRequest(
        name=name,
        system_prompt=system_prompt,
        llm_server_id=llm_server_id,
        model_name=model_name,
        tool_names=list(tool_names or []),
        mode_keys=list(mode_keys or []),
    )


def _mode_req(
    system_prompt: str | None,
    tool_names: list[str],
    sub_agent_ids: list[str],
) -> UpdateAssistantModeRequest:
    """The step-002 mode-side body: all three fields always explicit."""
    return UpdateAssistantModeRequest(
        system_prompt=system_prompt,
        tool_names=tool_names,
        sub_agent_ids=sub_agent_ids,
    )


async def _seed_modes() -> None:
    """The fixed five seeded modes, with the four keys this suite uses proven
    present (so an absent key can never be mistaken for a refusal reason)."""
    await assistant_modes.seed_default_modes()
    for key in (MODE_A, MODE_B, MODE_C, MODE_D):
        assert await assistant_modes.get_by_id(key) is not None


async def _seed_server(
    *,
    name: str = "Primary",
    enabled_models: str = '["gpt-x"]',
    is_active: bool = True,
) -> LlmServer:
    """An LlmServer row seeded through `db/`; `enabled_models` is the JSON string
    the TEXT column holds (the tests/services/test_chats.py idiom)."""
    return await llm_servers.create(
        LlmServer(
            name=name,
            backend_type="openai",
            base_url="https://api.example.com/v1",
            api_key="$SECRET_KEY_VALUE",
            enabled_models=enabled_models,
            is_active=is_active,
        )
    )


async def _seed_sub_agent_row(name: str, *, disabled: bool = False) -> SubAgent:
    """A SubAgent row seeded straight through `db/`, bypassing the service.

    Used to arrange a `disabled` sub-agent WITHOUT going through
    `set_sub_agent_disabled`, so the clauses about saving onto a disabled
    sub-agent do not depend on the setter that is itself under test.
    """
    created = await sub_agents.create(
        SubAgent(
            name=name,
            system_prompt=f"System prompt for {name}.",
            disabled=disabled,
            llm_server_id=None,
            model_name=None,
            created_at=datetime(2026, 7, 26, 8, 0, 0),
            modified_at=datetime(2026, 7, 26, 8, 0, 0),
        )
    )
    assert created.id is not None
    return created


async def _seed_tool_rows(sub_agent_id: int, tool_names: list[str]) -> None:
    """`subagent_tool` rows written straight through `db/`."""
    for tool_name in tool_names:
        await subagent_tools.create(
            SubagentTool(sub_agent_id=sub_agent_id, tool_name=tool_name)
        )


def _naive_utc(value: datetime | None) -> datetime | None:
    """Normalize a timestamp to naive UTC so two readings are comparable.

    The service writes `datetime.now(timezone.utc)`; no column in this codebase
    is `TIMESTAMP(timezone=True)`, so a value read back from SQLite may be naive
    while a freshly built one is aware.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


async def _stored_tools(sub_agent_id: str) -> list[str]:
    """The sub-agent's stored `subagent_tool` names, sorted (so a duplicate row
    would change the value)."""
    rows = await subagent_tools.list_by_sub_agent(int(sub_agent_id))
    return sorted(row.tool_name for row in rows)


async def _stored_modes(sub_agent_id: str) -> list[str]:
    """The sub-agent's stored `mode_subagent` keys, sorted."""
    rows = await mode_subagents.list_by_sub_agent(int(sub_agent_id))
    return sorted(row.mode_key for row in rows)


async def _mode_side_ids(mode_key: str) -> set[str]:
    """The mode's accessible sub-agent ids, read through the MODE surface —
    `list_modes`, step 002's already-implemented reader. This is the read that
    proves a sub-agent-side write landed in the one shared row set."""
    listed = await config_service.list_modes()
    matches = [mode for mode in listed.items if mode.key == mode_key]
    assert len(matches) == 1
    return set(matches[0].sub_agent_ids)


async def _mode_side_rows(mode_key: str) -> list[int]:
    """The mode's `mode_subagent` row ids, read straight from `db/`, sorted."""
    rows = await mode_subagents.list_by_mode(mode_key)
    return sorted(row.sub_agent_id for row in rows)


async def _listed(sub_agent_id: str) -> SubAgentResponse:
    """The one SubAgentResponse for `sub_agent_id`, read through the lister."""
    listed = await config_service.list_sub_agents()
    matches = [item for item in listed.items if item.id == sub_agent_id]
    assert len(matches) == 1
    return matches[0]


async def _stored(sub_agent_id: str) -> SubAgent:
    """The stored row behind a DTO id."""
    row = await sub_agents.get_by_id(int(sub_agent_id))
    assert row is not None
    return row


async def _snapshot() -> list[tuple[object, ...]]:
    """Every sub-agent row's complete stored state, read straight from `db/`.

    Id, name, prompt, disabled, the model pair, both timestamps and both link
    row sets, per row, id-sorted. This is the value the "writes nothing" /
    "stored scalars and existing links are unchanged" clauses of DoD-6, DoD-12
    and DoD-13 compare before against after: it bites on a row that should not
    have been created, a scalar that should not have moved, a link row added or
    removed, and a refreshed `modified_at` alike.
    """
    rows = await sub_agents.list_all()
    snapshot: list[tuple[object, ...]] = []
    for row in sorted(rows, key=lambda candidate: candidate.id):
        tool_rows = await subagent_tools.list_by_sub_agent(row.id)
        mode_rows = await mode_subagents.list_by_sub_agent(row.id)
        snapshot.append(
            (
                row.id,
                row.name,
                row.system_prompt,
                row.disabled,
                row.llm_server_id,
                row.model_name,
                row.created_at,
                row.modified_at,
                sorted(tool_row.tool_name for tool_row in tool_rows),
                sorted(mode_row.mode_key for mode_row in mode_rows),
            )
        )
    return snapshot


# ---------------------------------------------------------------------------
# DoD-1 — a create carrying both selections stores both and returns them
#         (UC-096 steps 4-5; US-113.AC-1)
# ---------------------------------------------------------------------------


# DoD-1 (UC-096 steps 4-5; US-113.AC-1): creating a sub-agent with a tool
# selection and a mode selection stores BOTH, and the returned DTO carries them.
# Verified three ways: on the returned DTO, on the stored link rows read through
# `db/`, and through the lister — a selection that only existed in the response
# would not survive the last two.
async def test_create_stores_tool_and_mode_selection__DoD1_UC096_US113_AC1(
    db: DbConfig,
):
    await _seed_modes()

    created = await config_service.create_sub_agent(
        _create_req(
            "continuity-checker",
            "Check the manuscript for continuity errors.",
            tool_names=list(ALL_TOOL_NAMES),
            mode_keys=[MODE_A, MODE_B],
        )
    )

    # The returned DTO carries both selections.
    assert sorted(created.tool_names) == sorted(ALL_TOOL_NAMES)
    assert len(created.tool_names) == len(ALL_TOOL_NAMES)
    assert sorted(created.mode_keys) == sorted([MODE_A, MODE_B])
    assert len(created.mode_keys) == 2

    # ...and both are really stored as link rows.
    assert await _stored_tools(created.id) == sorted(ALL_TOOL_NAMES)
    assert await _stored_modes(created.id) == sorted([MODE_A, MODE_B])

    # ...and the lister reports the same sub-agent with the same selections.
    listed = await _listed(created.id)
    assert sorted(listed.tool_names) == sorted(ALL_TOOL_NAMES)
    assert sorted(listed.mode_keys) == sorted([MODE_A, MODE_B])

    # The rest of the sub-agent is unaffected by the new fields.
    assert listed.name == "continuity-checker"
    assert listed.system_prompt == "Check the manuscript for continuity errors."
    assert listed.disabled is False

    # A mode that was NOT selected gained nothing.
    assert await _stored_modes(created.id) == sorted([MODE_A, MODE_B])
    assert await _mode_side_rows(MODE_C) == []


# ---------------------------------------------------------------------------
# DoD-2 — a sub-agent-side write is visible from the MODE-side read
#         (US-113.AC-2, US-112.AC-2)
# ---------------------------------------------------------------------------


# DoD-2 (US-113.AC-2, US-112.AC-2): a sub-agent created as accessible from a mode
# APPEARS IN THAT MODE'S accessible sub-agent set when the mode is read back
# through the mode surface (`list_modes`). One row set, two editors: the
# sub-agent-side write lands in the same `mode_subagent` rows the mode-side
# editor reads.
async def test_sub_agent_side_link_is_visible_from_the_mode__DoD2_US113_AC2(
    db: DbConfig,
):
    await _seed_modes()

    created = await config_service.create_sub_agent(
        _create_req("alpha-agent", "A prompt.", mode_keys=[MODE_A])
    )

    # The MODE surface lists it as accessible — ids as strings, per the mode DTO.
    assert str(created.id) in await _mode_side_ids(MODE_A)
    assert await _mode_side_ids(MODE_A) == {created.id}

    # ...and it is the shared row set that carries it.
    assert await _mode_side_rows(MODE_A) == [int(created.id)]

    # No other mode gained the sub-agent.
    for other_key in (MODE_B, MODE_C, MODE_D):
        assert await _mode_side_ids(other_key) == set()

    # A second sub-agent-side write adds to the same mode's set without
    # disturbing the first sub-agent's link.
    second = await config_service.create_sub_agent(
        _create_req("beta-agent", "A prompt.", mode_keys=[MODE_A])
    )
    assert await _mode_side_ids(MODE_A) == {created.id, second.id}
    assert await _mode_side_rows(MODE_A) == sorted([int(created.id), int(second.id)])


# ---------------------------------------------------------------------------
# DoD-3 — a mode-side link is visible in the sub-agent's `mode_keys`, and a
#         sub-agent-side re-save replaces only that sub-agent's slice
#         (US-112.AC-2)
# ---------------------------------------------------------------------------


# DoD-3 (US-112.AC-2): a link written from the MODE side is visible in that
# sub-agent's `mode_keys`; re-saving from the SUB-AGENT side replaces the whole
# set FOR THAT SUB-AGENT while leaving other sub-agents' links to the same mode
# intact. Neither editor may clear more than its own slice of the one row set.
async def test_mode_side_link_visible_and_sub_agent_save_replaces_own_slice__DoD3_US112_AC2(
    db: DbConfig,
):
    await _seed_modes()

    target = await config_service.create_sub_agent(
        _create_req("alpha-agent", "Target prompt.")
    )
    other = await config_service.create_sub_agent(
        _create_req("beta-agent", "Other prompt.")
    )

    # Written from the MODE side: both sub-agents accessible from MODE_A, and
    # only the target from MODE_B.
    await config_service.save_mode(MODE_A, _mode_req(None, [], [target.id, other.id]))
    await config_service.save_mode(MODE_B, _mode_req(None, [], [target.id]))

    # ...and the sub-agent surface sees those links in its `mode_keys`.
    assert sorted((await _listed(target.id)).mode_keys) == sorted([MODE_A, MODE_B])
    assert (await _listed(other.id)).mode_keys == [MODE_A]

    # Now re-save from the SUB-AGENT side with a completely different set.
    resaved = await config_service.update_sub_agent(
        target.id,
        _update_req("alpha-agent", "Target prompt.", mode_keys=[MODE_C]),
    )

    # The target's whole set was replaced: MODE_A and MODE_B are gone, MODE_C is in.
    assert resaved.mode_keys == [MODE_C]
    assert await _stored_modes(target.id) == [MODE_C]
    assert MODE_A not in resaved.mode_keys
    assert MODE_B not in resaved.mode_keys

    # The OTHER sub-agent's link to the same mode survived untouched — the
    # sub-agent-side replace clears only its own slice.
    assert (await _listed(other.id)).mode_keys == [MODE_A]
    assert await _stored_modes(other.id) == [MODE_A]

    # Read from the mode side: MODE_A now lists only the other sub-agent, MODE_B
    # lists nobody, MODE_C lists the target.
    assert await _mode_side_ids(MODE_A) == {other.id}
    assert await _mode_side_ids(MODE_B) == set()
    assert await _mode_side_ids(MODE_C) == {target.id}


# ---------------------------------------------------------------------------
# DoD-4 — an update REPLACES each selection rather than merging (US-114.AC-1)
# ---------------------------------------------------------------------------


# DoD-4 (US-114.AC-1): updating a sub-agent's MODE selection replaces it rather
# than merging — a mode present before and absent after is gone, one retained
# across the save proves the replace is not simply a wipe.
async def test_update_replaces_mode_selection_not_merges__DoD4_US114_AC1(
    db: DbConfig,
):
    await _seed_modes()

    created = await config_service.create_sub_agent(
        _create_req("alpha-agent", "A prompt.", mode_keys=[MODE_A, MODE_B])
    )
    assert await _stored_modes(created.id) == sorted([MODE_A, MODE_B])

    saved = await config_service.update_sub_agent(
        created.id,
        _update_req("alpha-agent", "A prompt.", mode_keys=[MODE_B, MODE_C]),
    )

    # Exactly the new set — a replace, not a merge.
    assert sorted(saved.mode_keys) == sorted([MODE_B, MODE_C])
    assert len(saved.mode_keys) == 2
    # The mode present before and absent after is gone.
    assert MODE_A not in saved.mode_keys
    assert await _stored_modes(created.id) == sorted([MODE_B, MODE_C])

    listed = await _listed(created.id)
    assert sorted(listed.mode_keys) == sorted([MODE_B, MODE_C])
    assert MODE_A not in listed.mode_keys

    # The mode side agrees the dropped link is gone.
    assert await _mode_side_ids(MODE_A) == set()
    assert await _mode_side_ids(MODE_B) == {created.id}
    assert await _mode_side_ids(MODE_C) == {created.id}


# DoD-4 (US-114.AC-1): updating a sub-agent's TOOL selection replaces it rather
# than merging — a tool present before and absent after is gone. Both selections
# are derived from TOOL_REGISTRY (the second drops the first name), so the clause
# holds for one or many registry entries.
@requires_a_tool
async def test_update_replaces_tool_selection_not_merges__DoD4_US114_AC1(
    db: DbConfig,
):
    await _seed_modes()

    first_selection = list(ALL_TOOL_NAMES)
    dropped_name = first_selection[0]
    second_selection = first_selection[1:]

    created = await config_service.create_sub_agent(
        _create_req("alpha-agent", "A prompt.", tool_names=first_selection)
    )
    assert await _stored_tools(created.id) == sorted(first_selection)

    saved = await config_service.update_sub_agent(
        created.id,
        _update_req("alpha-agent", "A prompt.", tool_names=second_selection),
    )

    assert sorted(saved.tool_names) == sorted(second_selection)
    assert len(saved.tool_names) == len(second_selection)
    # The tool present before and absent after is gone.
    assert dropped_name not in saved.tool_names
    assert await _stored_tools(created.id) == sorted(second_selection)

    listed = await _listed(created.id)
    assert sorted(listed.tool_names) == sorted(second_selection)
    assert dropped_name not in listed.tool_names


# ---------------------------------------------------------------------------
# DoD-5 — an empty selection is accepted and writes no link rows
#         (US-114.AC-1; context.md -> scope decision 1)
# ---------------------------------------------------------------------------


# DoD-5 (US-114.AC-1; context.md -> scope decision 1 — empty means none): an
# empty tool selection and an empty mode selection are both ACCEPTED (no error)
# and result in zero link rows of that kind. Exercised three ways: OMITTING both
# fields (they default to empty — the feature's only defaulted fields), passing
# them explicitly empty on create, and passing them explicitly empty on update.
# The clause bites on a regression where an empty selection raised, or wrote a
# row for "nothing".
async def test_empty_selections_accepted_and_write_no_links__DoD5_US114_AC1(
    db: DbConfig,
):
    await _seed_modes()

    # 1. Both fields OMITTED entirely: a caller that passes only the four scalars
    #    gets a sub-agent with no selections.
    omitted = await config_service.create_sub_agent(
        CreateSubAgentRequest(
            name="omitting-agent",
            system_prompt="A prompt.",
            llm_server_id=None,
            model_name=None,
        )
    )
    assert omitted.tool_names == []
    assert omitted.mode_keys == []
    assert await _stored_tools(omitted.id) == []
    assert await _stored_modes(omitted.id) == []

    # 2. Both fields passed EXPLICITLY empty on create.
    explicit = await config_service.create_sub_agent(
        _create_req("explicit-agent", "A prompt.", tool_names=[], mode_keys=[])
    )
    assert explicit.tool_names == []
    assert explicit.mode_keys == []
    assert await _stored_tools(explicit.id) == []
    assert await _stored_modes(explicit.id) == []

    # 3. Both fields passed EXPLICITLY empty on update.
    saved = await config_service.update_sub_agent(
        explicit.id,
        _update_req("explicit-agent", "A revised prompt.", tool_names=[], mode_keys=[]),
    )
    assert saved.tool_names == []
    assert saved.mode_keys == []
    assert await _stored_tools(explicit.id) == []
    assert await _stored_modes(explicit.id) == []
    # The rest of the save still landed.
    assert saved.system_prompt == "A revised prompt."

    # The lister reports both link lists as empty for each of them.
    for sub_agent_id in (omitted.id, explicit.id):
        listed = await _listed(sub_agent_id)
        assert listed.tool_names == []
        assert listed.mode_keys == []

    # ...and no mode gained a sub-agent from any of it.
    modes = await config_service.list_modes()
    assert len(modes.items) == 5
    for mode in modes.items:
        assert isinstance(mode, AssistantModeResponse)
        assert mode.sub_agent_ids == []


# ---------------------------------------------------------------------------
# DoD-6 — an unknown tool / unknown mode key is refused and nothing changes
#         (US-113.AC-1, US-114.AC-1)
# ---------------------------------------------------------------------------


# DoD-6 (US-114.AC-1): a save naming a tool absent from TOOL_REGISTRY is refused
# with unknown-tool, and one naming a `mode_key` with no AssistantMode row with
# mode-not-found — the REUSED step-002 reason, not a new enum member. In both
# cases the sub-agent's stored SCALARS and its EXISTING LINKS are unchanged: every
# validation runs before any write, so a replace-set may not clear first and fail
# after. Each refused body also carries a new name, a new prompt and an otherwise
# valid selection, so a partial write would be caught.
async def test_update_unknown_tool_or_mode_refused_and_nothing_changes__DoD6_US114_AC1(
    db: DbConfig,
):
    await _seed_modes()

    target = await config_service.create_sub_agent(
        _create_req(
            "target-agent",
            "Original prompt.",
            tool_names=list(ALL_TOOL_NAMES),
            mode_keys=[MODE_A, MODE_B],
        )
    )
    # Another sub-agent sharing one of the modes, so a stray wipe is visible.
    other = await config_service.create_sub_agent(
        _create_req("other-agent", "Other prompt.", mode_keys=[MODE_A])
    )

    before = await _snapshot()
    assert len(before) == 2

    # 1. An unknown tool name — the mode selection in the same body is valid.
    assert UNKNOWN_TOOL_NAME not in ALL_TOOL_NAMES
    with pytest.raises(config_service.AssistantConfigError) as tool_exc:
        await config_service.update_sub_agent(
            target.id,
            _update_req(
                "renamed-agent",
                "Must not land.",
                tool_names=[UNKNOWN_TOOL_NAME],
                mode_keys=[MODE_C],
            ),
        )
    assert (
        tool_exc.value.reason == config_service.AssistantConfigErrorReason.unknown_tool
    )
    assert tool_exc.value.reason.value == "unknown-tool"
    assert await _snapshot() == before

    # 2. A mode key no AssistantMode row carries — the tool selection in the same
    #    body is valid, and so is the other mode key beside it.
    assert await assistant_modes.get_by_id(MISSING_MODE_KEY) is None
    with pytest.raises(config_service.AssistantConfigError) as mode_exc:
        await config_service.update_sub_agent(
            target.id,
            _update_req(
                "renamed-agent",
                "Must not land.",
                tool_names=list(ALL_TOOL_NAMES),
                mode_keys=[MODE_A, MISSING_MODE_KEY],
            ),
        )
    assert (
        mode_exc.value.reason == config_service.AssistantConfigErrorReason.mode_not_found
    )
    assert mode_exc.value.reason.value == "mode-not-found"
    assert await _snapshot() == before

    # Read through the service too: scalars and both selections are as they were.
    listed = await _listed(target.id)
    assert listed.name == "target-agent"
    assert listed.system_prompt == "Original prompt."
    assert sorted(listed.tool_names) == sorted(ALL_TOOL_NAMES)
    assert sorted(listed.mode_keys) == sorted([MODE_A, MODE_B])

    # ...and neither the other sub-agent's link nor the untouched modes moved.
    assert (await _listed(other.id)).mode_keys == [MODE_A]
    assert await _mode_side_ids(MODE_A) == {target.id, other.id}
    assert await _mode_side_ids(MODE_C) == set()


# DoD-6 (US-113.AC-1): the same two refusals apply on CREATE — an unknown tool
# name is unknown-tool and an unknown mode key is mode-not-found — and nothing is
# written: no sub-agent row appears for the refused name and the existing
# sub-agent keeps its scalars and its links.
async def test_create_unknown_tool_or_mode_refused_and_nothing_written__DoD6_US113_AC1(
    db: DbConfig,
):
    await _seed_modes()

    await config_service.create_sub_agent(
        _create_req(
            "existing-agent",
            "Original prompt.",
            tool_names=list(ALL_TOOL_NAMES),
            mode_keys=[MODE_A],
        )
    )
    before = await _snapshot()
    assert len(before) == 1

    assert UNKNOWN_TOOL_NAME not in ALL_TOOL_NAMES
    with pytest.raises(config_service.AssistantConfigError) as tool_exc:
        await config_service.create_sub_agent(
            _create_req(
                "tool-refused-agent",
                "Must not land.",
                tool_names=[UNKNOWN_TOOL_NAME],
                mode_keys=[MODE_B],
            )
        )
    assert (
        tool_exc.value.reason == config_service.AssistantConfigErrorReason.unknown_tool
    )
    assert await sub_agents.get_by_name("tool-refused-agent") is None
    assert await _snapshot() == before

    assert await assistant_modes.get_by_id(MISSING_MODE_KEY) is None
    with pytest.raises(config_service.AssistantConfigError) as mode_exc:
        await config_service.create_sub_agent(
            _create_req(
                "mode-refused-agent",
                "Must not land.",
                tool_names=list(ALL_TOOL_NAMES),
                mode_keys=[MISSING_MODE_KEY],
            )
        )
    assert (
        mode_exc.value.reason == config_service.AssistantConfigErrorReason.mode_not_found
    )
    assert await sub_agents.get_by_name("mode-refused-agent") is None
    assert await _snapshot() == before

    # Only the pre-existing sub-agent exists, and no mode gained a link.
    listed = await config_service.list_sub_agents()
    assert [item.name for item in listed.items] == ["existing-agent"]
    assert await _mode_side_rows(MODE_B) == []


# ---------------------------------------------------------------------------
# DoD-7 — repeated values produce one link row per distinct value (US-114.AC-1)
# ---------------------------------------------------------------------------


# DoD-7 (US-114.AC-1): a request repeating the same MODE KEY twice is ACCEPTED
# (no error) and produces one `mode_subagent` row per distinct key —
# uq_mode_subagent_mode_key_sub_agent_id is never violated. Checked on create and
# again on update, since both paths write the same replace-set.
async def test_repeated_mode_key_yields_one_row_per_distinct_value__DoD7_US114_AC1(
    db: DbConfig,
):
    await _seed_modes()

    requested = [MODE_A, MODE_B, MODE_A, MODE_B, MODE_A]
    distinct = sorted({MODE_A, MODE_B})

    created = await config_service.create_sub_agent(
        _create_req("alpha-agent", "A prompt.", mode_keys=requested)
    )

    assert sorted(created.mode_keys) == distinct
    assert len(created.mode_keys) == len(distinct)
    assert await _stored_modes(created.id) == distinct
    assert len(await mode_subagents.list_by_sub_agent(int(created.id))) == len(distinct)

    # The mode side sees exactly one link per mode, not two.
    assert await _mode_side_rows(MODE_A) == [int(created.id)]
    assert await _mode_side_rows(MODE_B) == [int(created.id)]

    # The same on update.
    saved = await config_service.update_sub_agent(
        created.id,
        _update_req("alpha-agent", "A prompt.", mode_keys=[MODE_C, MODE_C, MODE_C]),
    )
    assert saved.mode_keys == [MODE_C]
    assert await _stored_modes(created.id) == [MODE_C]
    assert await _mode_side_rows(MODE_C) == [int(created.id)]


# DoD-7 (US-114.AC-1): a request repeating the same TOOL NAME twice is ACCEPTED
# and produces one `subagent_tool` row per distinct name —
# uq_subagent_tool_sub_agent_id_tool_name is never violated. The requested list is
# built from the registry, so it stays correct for one or many entries.
@requires_a_tool
async def test_repeated_tool_name_yields_one_row_per_distinct_value__DoD7_US114_AC1(
    db: DbConfig,
):
    await _seed_modes()

    repeated = ALL_TOOL_NAMES[0]
    requested = [repeated, *ALL_TOOL_NAMES, repeated]
    distinct = sorted(set(requested))

    created = await config_service.create_sub_agent(
        _create_req("alpha-agent", "A prompt.", tool_names=requested)
    )

    assert sorted(created.tool_names) == distinct
    assert len(created.tool_names) == len(distinct)
    assert await _stored_tools(created.id) == distinct
    assert len(await subagent_tools.list_by_sub_agent(int(created.id))) == len(distinct)

    # The same on update.
    saved = await config_service.update_sub_agent(
        created.id,
        _update_req("alpha-agent", "A prompt.", tool_names=requested),
    )
    assert sorted(saved.tool_names) == distinct
    assert await _stored_tools(created.id) == distinct


# ---------------------------------------------------------------------------
# DoD-8 — disabling detaches the sub-agent from every mode, and the row stays
#         (UC-097 alternate flow; US-114.AC-2)
# ---------------------------------------------------------------------------


# DoD-8 (UC-097 alternate flow; US-114.AC-2): disabling a sub-agent that TWO modes
# reference sets `disabled` true and REMOVES ITS LINK ROWS FROM BOTH — neither
# mode lists it as accessible any more — while the sub-agent's own row still
# exists (disable-not-delete). A second sub-agent linked to the same two modes
# proves the deletion is scoped to the disabled sub-agent's slice. The Interface
# intent also fixes that disabling refreshes `modified_at`.
async def test_disable_detaches_from_every_mode_and_keeps_the_row__DoD8_US114_AC2(
    db: DbConfig,
):
    await _seed_modes()

    target = await config_service.create_sub_agent(
        _create_req(
            "target-agent",
            "Target prompt.",
            tool_names=list(ALL_TOOL_NAMES),
            mode_keys=[MODE_A, MODE_B],
        )
    )
    other = await config_service.create_sub_agent(
        _create_req("other-agent", "Other prompt.", mode_keys=[MODE_A, MODE_B])
    )

    # Both modes reference both sub-agents to begin with.
    assert await _mode_side_ids(MODE_A) == {target.id, other.id}
    assert await _mode_side_ids(MODE_B) == {target.id, other.id}

    row_before = await _stored(target.id)
    assert row_before.disabled is False
    # Guarantee a measurable gap, so "refreshed" is a strict comparison.
    await asyncio.sleep(0.05)

    result = await config_service.set_sub_agent_disabled(target.id, True)

    # The rebuilt DTO reports the sub-agent as disabled and attached to nothing.
    assert isinstance(result, SubAgentResponse)
    assert result.id == target.id
    assert result.disabled is True
    assert result.mode_keys == []

    # The flag is on the row, and the row still exists.
    row_after = await _stored(target.id)
    assert row_after.disabled is True
    assert row_after.name == "target-agent"
    assert await sub_agents.get_by_name("target-agent") is not None

    # Its link rows are gone from BOTH modes.
    assert await _stored_modes(target.id) == []
    assert target.id not in await _mode_side_ids(MODE_A)
    assert target.id not in await _mode_side_ids(MODE_B)

    # The OTHER sub-agent's links to the very same modes are intact.
    assert await _mode_side_ids(MODE_A) == {other.id}
    assert await _mode_side_ids(MODE_B) == {other.id}
    assert sorted((await _listed(other.id)).mode_keys) == sorted([MODE_A, MODE_B])

    # The disabled sub-agent is still listed, so it can be re-enabled later.
    listed = await _listed(target.id)
    assert listed.disabled is True
    assert listed.mode_keys == []

    # `modified_at` was refreshed; `created_at` did not move.
    assert _naive_utc(row_after.modified_at) > _naive_utc(row_before.modified_at)
    assert row_after.created_at == row_before.created_at


# ---------------------------------------------------------------------------
# DoD-9 — disabling KEEPS the sub-agent's tool rows (UC-097 is reversible)
# ---------------------------------------------------------------------------


# DoD-9 (UC-097 — disabling is reversible): disabling KEEPS the sub-agent's
# `subagent_tool` rows — its own tool configuration survives so re-enabling
# restores a usable worker. Only the mode links go. Two stored rows are seeded
# through `db/` with names that are deliberately not registry entries
# (`tool_name` is a string reference, never an FK), so the clause has bite
# whatever TOOL_REGISTRY currently holds.
async def test_disable_keeps_the_sub_agent_tool_rows__DoD9_UC097(db: DbConfig):
    await _seed_modes()

    target = await config_service.create_sub_agent(
        _create_req(
            "target-agent",
            "Target prompt.",
            tool_names=list(ALL_TOOL_NAMES),
            mode_keys=[MODE_A],
        )
    )
    for stored_name in STORED_TOOL_NAMES:
        assert stored_name not in ALL_TOOL_NAMES
    await _seed_tool_rows(int(target.id), STORED_TOOL_NAMES)

    tools_before = await _stored_tools(target.id)
    assert tools_before == sorted({*ALL_TOOL_NAMES, *STORED_TOOL_NAMES})
    assert len(tools_before) >= len(STORED_TOOL_NAMES)

    await config_service.set_sub_agent_disabled(target.id, True)

    # Every `subagent_tool` row survived the disable, unchanged.
    assert await _stored_tools(target.id) == tools_before

    # ...and the mode links did not — the deletion is scoped to modes only.
    assert await _stored_modes(target.id) == []
    assert await _mode_side_ids(MODE_A) == set()

    # The rebuilt DTO still carries the selected tools.
    result = await _listed(target.id)
    assert result.disabled is True
    assert set(ALL_TOOL_NAMES) <= set(result.tool_names)
    assert result.mode_keys == []


# ---------------------------------------------------------------------------
# DoD-10 — re-enabling restores no links and changes nothing else (US-114.AC-3)
# ---------------------------------------------------------------------------


# DoD-10 (US-114.AC-3): re-enabling a disabled sub-agent sets `disabled` false and
# leaves it ATTACHED TO NO MODE — the links deleted at disable time are NOT
# restored, because they were deleted rather than suppressed. Enabling refreshes
# `modified_at` and nothing else: name, prompt, model pair, tools and `created_at`
# are all where they were.
async def test_enable_restores_no_links_and_changes_nothing_else__DoD10_US114_AC3(
    db: DbConfig,
):
    await _seed_modes()
    server = await _seed_server()

    target = await config_service.create_sub_agent(
        _create_req(
            "target-agent",
            "Target prompt.",
            llm_server_id=str(server.id),
            model_name="gpt-x",
            tool_names=list(ALL_TOOL_NAMES),
            mode_keys=[MODE_A, MODE_B],
        )
    )
    other = await config_service.create_sub_agent(
        _create_req("other-agent", "Other prompt.", mode_keys=[MODE_A])
    )
    await _seed_tool_rows(int(target.id), STORED_TOOL_NAMES)
    tools_before = await _stored_tools(target.id)

    await config_service.set_sub_agent_disabled(target.id, True)
    row_disabled = await _stored(target.id)
    assert row_disabled.disabled is True
    assert await _stored_modes(target.id) == []

    await asyncio.sleep(0.05)

    result = await config_service.set_sub_agent_disabled(target.id, False)

    # Enabled again...
    assert result.id == target.id
    assert result.disabled is False
    assert (await _stored(target.id)).disabled is False

    # ...and attached to no mode: the deleted links are not restored.
    assert result.mode_keys == []
    assert await _stored_modes(target.id) == []
    assert await _mode_side_ids(MODE_A) == {other.id}
    assert await _mode_side_ids(MODE_B) == set()
    assert (await _listed(target.id)).mode_keys == []

    # Nothing else moved: scalars, model pair and tools are as they were.
    row_enabled = await _stored(target.id)
    assert row_enabled.name == "target-agent"
    assert row_enabled.system_prompt == "Target prompt."
    assert row_enabled.llm_server_id == server.id
    assert row_enabled.model_name == "gpt-x"
    assert await _stored_tools(target.id) == tools_before
    assert result.llm_server_id == str(server.id)
    assert result.model_name == "gpt-x"

    # `modified_at` was refreshed; `created_at` did not move.
    assert _naive_utc(row_enabled.modified_at) > _naive_utc(row_disabled.modified_at)
    assert row_enabled.created_at == row_disabled.created_at


# ---------------------------------------------------------------------------
# DoD-11 — after re-enabling, a mode may select it again (US-114.AC-3)
# ---------------------------------------------------------------------------


# DoD-11 (US-114.AC-3): after re-enabling, a mode may select the sub-agent again
# and the link is stored — the sub-agent is usable once more. Shown from the MODE
# editor (`save_mode`) and, because the same invariant is enforced on both sides,
# from the SUB-AGENT editor's own mode selection.
async def test_reenabled_sub_agent_can_be_selected_again__DoD11_US114_AC3(
    db: DbConfig,
):
    await _seed_modes()

    target = await config_service.create_sub_agent(
        _create_req("target-agent", "Target prompt.", mode_keys=[MODE_A])
    )
    await config_service.set_sub_agent_disabled(target.id, True)
    await config_service.set_sub_agent_disabled(target.id, False)
    assert (await _listed(target.id)).disabled is False
    assert await _stored_modes(target.id) == []

    # 1. The MODE editor may select it again, and the link is stored.
    saved_mode = await config_service.save_mode(
        MODE_A, _mode_req(None, [], [target.id])
    )
    assert target.id in saved_mode.sub_agent_ids
    assert await _mode_side_ids(MODE_A) == {target.id}
    assert await _stored_modes(target.id) == [MODE_A]
    assert (await _listed(target.id)).mode_keys == [MODE_A]

    # 2. The SUB-AGENT editor may select modes again too.
    saved = await config_service.update_sub_agent(
        target.id,
        _update_req("target-agent", "Target prompt.", mode_keys=[MODE_B, MODE_C]),
    )
    assert sorted(saved.mode_keys) == sorted([MODE_B, MODE_C])
    assert await _stored_modes(target.id) == sorted([MODE_B, MODE_C])
    assert await _mode_side_ids(MODE_B) == {target.id}
    assert await _mode_side_ids(MODE_C) == {target.id}


# ---------------------------------------------------------------------------
# DoD-12 — a disabled sub-agent refuses a non-empty mode selection but stays
#          otherwise editable (US-114.AC-2, US-114.AC-1)
# ---------------------------------------------------------------------------


# DoD-12 (US-114.AC-2): saving a NON-EMPTY mode selection onto a currently
# disabled sub-agent is refused with the sub-agent-disabled reason (the same
# reason the mode-side editor uses — there is no second reason) and WRITES
# NOTHING; while saving that sub-agent's name, prompt, model and tools with an
# EMPTY mode selection SUCCEEDS. Disabling is defined as being detached from every
# mode, so granting an attachment in the same breath contradicts the invariant,
# but an empty selection agrees with it and keeps the rest editable (UC-097).
# The disabled row is arranged through `db/` so this clause does not depend on
# the disable setter.
async def test_disabled_sub_agent_refuses_non_empty_mode_selection__DoD12_US114_AC2(
    db: DbConfig,
):
    await _seed_modes()
    server = await _seed_server(enabled_models='["gpt-x", "gpt-y"]')

    row = await _seed_sub_agent_row("disabled-agent", disabled=True)
    sub_agent_id = str(row.id)
    await _seed_tool_rows(row.id, STORED_TOOL_NAMES)

    before = await _snapshot()
    assert len(before) == 1

    # 1. A NON-EMPTY mode selection is refused, and nothing is written — not the
    #    name, not the prompt, not the model pair, not the tool selection that
    #    shared the request, and not a link row.
    with pytest.raises(config_service.AssistantConfigError) as exc:
        await config_service.update_sub_agent(
            sub_agent_id,
            _update_req(
                "renamed-agent",
                "Must not land.",
                llm_server_id=str(server.id),
                model_name="gpt-x",
                tool_names=list(ALL_TOOL_NAMES),
                mode_keys=[MODE_A],
            ),
        )

    assert (
        exc.value.reason == config_service.AssistantConfigErrorReason.sub_agent_disabled
    )
    assert exc.value.reason.value == "sub-agent-disabled"
    assert await _snapshot() == before
    assert await _mode_side_ids(MODE_A) == set()

    # 2. The SAME save with an EMPTY mode selection succeeds and still updates
    #    name, prompt, model and tools.
    saved = await config_service.update_sub_agent(
        sub_agent_id,
        _update_req(
            "renamed-agent",
            "A revised prompt.",
            llm_server_id=str(server.id),
            model_name="gpt-y",
            tool_names=list(ALL_TOOL_NAMES),
            mode_keys=[],
        ),
    )

    assert saved.name == "renamed-agent"
    assert saved.system_prompt == "A revised prompt."
    assert saved.llm_server_id == str(server.id)
    assert saved.model_name == "gpt-y"
    assert sorted(saved.tool_names) == sorted(ALL_TOOL_NAMES)
    # It is still disabled — the update request carries no `disabled` field — and
    # still attached to nothing.
    assert saved.disabled is True
    assert saved.mode_keys == []

    stored_row = await _stored(sub_agent_id)
    assert stored_row.name == "renamed-agent"
    assert stored_row.system_prompt == "A revised prompt."
    assert stored_row.llm_server_id == server.id
    assert stored_row.model_name == "gpt-y"
    assert stored_row.disabled is True
    # The tool selection was replaced by the save.
    assert await _stored_tools(sub_agent_id) == sorted(ALL_TOOL_NAMES)
    assert await _stored_modes(sub_agent_id) == []
    assert await _mode_side_ids(MODE_A) == set()


# ---------------------------------------------------------------------------
# DoD-13 — disabling or enabling an unknown id is refused (UC-097 precondition)
# ---------------------------------------------------------------------------


# DoD-13 (UC-097 precondition — the sub-agent exists): disabling OR enabling a
# sub-agent id with no row is refused with the sub-agent-not-found reason. Both a
# well-formed id that no row carries and an ILL-FORMED id are "a sub-agent that is
# not there": the id crosses this boundary as a `str` and the service owns the
# parse, so a malformed id is a refusal with this reason, never an escaping
# ValueError. Nothing is written by any of the refusals.
async def test_disable_or_enable_unknown_id_refused__DoD13_UC097(db: DbConfig):
    await _seed_modes()

    # An untouched sub-agent, so "wrote nothing" has something to protect.
    await config_service.create_sub_agent(
        _create_req(
            "existing-agent",
            "Original prompt.",
            tool_names=list(ALL_TOOL_NAMES),
            mode_keys=[MODE_A],
        )
    )
    before = await _snapshot()
    assert len(before) == 1

    assert await sub_agents.get_by_id(MISSING_ID) is None

    for bad_id in (str(MISSING_ID), *ILL_FORMED_IDS):
        for desired in (True, False):
            with pytest.raises(config_service.AssistantConfigError) as exc:
                await config_service.set_sub_agent_disabled(bad_id, desired)

            assert (
                exc.value.reason
                == config_service.AssistantConfigErrorReason.sub_agent_not_found
            )
            assert exc.value.reason.value == "sub-agent-not-found"

            # The refused call created nothing and changed nothing.
            assert await _snapshot() == before

    # The existing sub-agent is untouched, links and all.
    listed = await config_service.list_sub_agents()
    assert [item.name for item in listed.items] == ["existing-agent"]
    assert listed.items[0].disabled is False
    assert listed.items[0].mode_keys == [MODE_A]
    assert await _mode_side_ids(MODE_A) == {listed.items[0].id}
