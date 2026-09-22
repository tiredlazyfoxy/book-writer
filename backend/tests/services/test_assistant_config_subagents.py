"""Tests for the sub-agent half of the assistant-config service (feature 012, step 003).

Bound to the frozen skeleton signatures (status.md -> Skeleton -> Step 003):
    app.models.schemas.assistant_config
        class SubAgentResponse(BaseModel)        id: str, name: str,
                                                system_prompt: str, disabled: bool,
                                                llm_server_id: str | None,
                                                model_name: str | None,
                                                tool_names: list[str],
                                                mode_keys: list[str],
                                                created_at / modified_at:
                                                datetime | None
        class SubAgentsListResponse(BaseModel)  items: list[SubAgentResponse]
        class CreateSubAgentRequest(BaseModel)  name: str, system_prompt: str,
                                                llm_server_id: str | None,
                                                model_name: str | None
        class UpdateSubAgentRequest(BaseModel)  the same four fields; NO `disabled`
    app.services.assistant_config
        class AssistantConfigErrorReason(str, enum.Enum) — six members appended by
            this step: sub_agent_not_found = "sub-agent-not-found",
            name_taken = "name-taken", blank_name = "blank-name",
            invalid_model_pair = "invalid-model-pair",
            unknown_or_inactive_server = "unknown-or-inactive-server",
            model_not_enabled = "model-not-enabled"
        class AssistantConfigError(Exception)   __init__(reason, message="")
        async def list_sub_agents() -> SubAgentsListResponse
        async def create_sub_agent(req: CreateSubAgentRequest) -> SubAgentResponse
        async def update_sub_agent(sub_agent_id: str, req: UpdateSubAgentRequest)
                                   -> SubAgentResponse

**Every request field is required — there are no defaults** (the frozen record:
"Every request field is required in the body"). The *inherit the main chat's
model* case is therefore expressed by passing `llm_server_id=None,
model_name=None` EXPLICITLY, never by omission; omitting either would be a
Pydantic ValidationError, which is not what any clause here is about.

`update_sub_agent` takes the id as a **`str`** and the service owns the parse: an
id that is not well-formed is a *missing* sub-agent (sub-agent-not-found), which
is what DoD-10 asserts. That is deliberately distinct from an unparsable id
inside a mode's `sub_agent_ids` body list, which is step 002's already-verified
`unknown-sub-agent` and is not this step's surface.

Arrangement uses the step-001 `db/` layer and the pre-existing 008 tables (both
implemented and green — `sub_agents.create / get_by_id / get_by_name / list_all`,
`subagent_tools.list_by_sub_agent`, `mode_subagents.list_by_sub_agent`,
`llm_servers.create / get_by_id`). Reading raw rows through `db/` is how "nothing
was written" is proved independently of the service under test, and it is also
the only way to arrange a `disabled` row — enable/disable is step 004's
operation, and the update request carries no `disabled` field.

Expected values come from the step spec (003.subagent-crud.md DoD + Interface
intent + 003.context.md + context.md), never from implementation internals:
    - DoD-1 (UC-096; US-113.AC-1): a create with a name, a prompt and no model
      stores the sub-agent and returns it with a STRING id, `disabled` false,
      both link lists EMPTY and both timestamps set;
    - DoD-2 (US-113.AC-6): a create with no model assignment records
      `llm_server_id` and `model_name` as NULL — that null/null pair *is* the
      recorded "re-use the main chat's model" state and is the default;
    - DoD-3 (US-113.AC-5): a create naming an ACTIVE server and a model listed in
      that server's `enabled_models` stores both fields, and the response carries
      `llm_server_id` as a STRING (`int` on the row, `str` on the wire);
    - DoD-4 (US-113.AC-5): a HALF-SET pair — server without model, or model
      without server — is refused with the invalid-model-pair reason, on create
      AND on update, and nothing is written ("All validation happens before any
      write");
    - DoD-5 (US-113.AC-5): a pair naming a non-existent server, or an existing
      server whose `is_active` is false, is refused with
      unknown-or-inactive-server; a pair naming an active server but a model
      ABSENT from its `enabled_models` is refused with model-not-enabled. The
      rule order the Interface intent fixes also makes an unparsable server id an
      unknown-or-inactive-server (rule 3), never a 500;
    - DoD-6 (US-113.AC-3; UC-097 exception flow): a name already held by ANOTHER
      sub-agent is refused with name-taken on create AND on update, and the
      existing rows are unchanged. The name is trimmed before the collision check
      (003.context.md -> Gotchas: "so `" x "` and `"x"` cannot both be stored"),
      so a padded duplicate collides and a padded unique name is stored trimmed;
    - DoD-7 (UC-096 exception flow; US-113.AC-1): a blank or whitespace-only name
      is refused with blank-name on create AND on update, and nothing is written;
    - DoD-8 (US-114.AC-1): updating a sub-agent WITHOUT changing its name
      succeeds — the uniqueness check excludes the row being updated, so saving a
      sub-agent unrenamed is not a self-collision;
    - DoD-9 (US-114.AC-1, US-114.AC-4): an update stores a changed name, prompt
      and model assignment, including switching a specific pair BACK to
      null/null (inherit the main chat's model) and from null/null to a specific
      pair; `modified_at` advances;
    - DoD-10 (UC-097 precondition): an id with no row is refused with
      sub-agent-not-found — both a well-formed-but-absent id and an ill-formed
      one;
    - DoD-11 (US-114.AC-3): the lister returns EVERY sub-agent ordered by name,
      INCLUDING disabled ones, each carrying its `disabled` flag — a disabled
      sub-agent must stay findable in order to be re-enabled.
    (DoD-12 is [manual/live] — no automated test.)

Not asserted, deliberately: anything about the two link lists beyond
present-and-empty (there is no write path for them until step 004 — the frozen
record: "Assert present-and-empty here; do not assert populated"), and anything
about the runtime that consumes this configuration (013.codex owns model
resolution — context.md -> "Out of scope"). A server deactivated *after* an
assignment was stored is an accepted consequence recorded in context.md ->
scope decision 3: nothing here re-validates or rewrites a stored assignment.

Async tests use asyncio_mode = "auto"; the `db` fixture (conftest) supplies an
initialized throwaway temp-SQLite engine (init_engine + init_db), so the schema
is present and each test is isolated. No network in any test.
"""

import asyncio
from datetime import datetime, timezone

import pytest

from app.db import llm_servers, mode_subagents, sub_agents, subagent_tools
from app.db.engine import DbConfig
from app.models.llm_server import LlmServer
from app.models.schemas.assistant_config import (
    CreateSubAgentRequest,
    SubAgentResponse,
    UpdateSubAgentRequest,
)
from app.models.sub_agent import SubAgent
from app.services import assistant_config as config_service

# An id no LlmServer / SubAgent row carries (asserted, not assumed, at point of
# use).
MISSING_ID = 424242424242

# Values that cannot be parsed as an id at all.
ILL_FORMED_IDS = ("not-an-id", "12x", "")


# ---------------------------------------------------------------------------
# helpers (module-local, per the suite convention: no shared fixtures)
# ---------------------------------------------------------------------------


def _create_req(
    name: str,
    system_prompt: str,
    llm_server_id: str | None,
    model_name: str | None,
) -> CreateSubAgentRequest:
    """The full-replace create body: all four fields always explicit."""
    return CreateSubAgentRequest(
        name=name,
        system_prompt=system_prompt,
        llm_server_id=llm_server_id,
        model_name=model_name,
    )


def _update_req(
    name: str,
    system_prompt: str,
    llm_server_id: str | None,
    model_name: str | None,
) -> UpdateSubAgentRequest:
    """The full-replace update body: all four fields always explicit, and there
    is no `disabled` field (step 004 owns enable/disable)."""
    return UpdateSubAgentRequest(
        name=name,
        system_prompt=system_prompt,
        llm_server_id=llm_server_id,
        model_name=model_name,
    )


async def _seed_server(
    *,
    name: str,
    enabled_models: str,
    is_active: bool = True,
) -> LlmServer:
    """An LlmServer row seeded straight through `db/`.

    `enabled_models` is a JSON-encoded `list[str]` in a TEXT column, decoded at
    the service edge (003.context.md), so it is arranged here as its JSON string
    — the established idiom in tests/services/test_chats.py.
    """
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


async def _seed_sub_agent_row(
    name: str,
    *,
    disabled: bool = False,
    llm_server_id: int | None = None,
    model_name: str | None = None,
) -> SubAgent:
    """A SubAgent row seeded straight through `db/`, bypassing the service.

    The only way to arrange a `disabled` sub-agent in this step: disable/enable
    is step 004's own operation and the update request carries no `disabled`
    field.
    """
    created = await sub_agents.create(
        SubAgent(
            name=name,
            system_prompt=f"System prompt for {name}.",
            disabled=disabled,
            llm_server_id=llm_server_id,
            model_name=model_name,
            created_at=datetime(2026, 7, 26, 8, 0, 0),
            modified_at=datetime(2026, 7, 26, 8, 0, 0),
        )
    )
    assert created.id is not None
    return created


def _naive_utc(value: datetime | None) -> datetime | None:
    """Normalize a timestamp to naive UTC so two readings are comparable.

    The service writes `datetime.now(timezone.utc)`; no column in this codebase
    is `TIMESTAMP(timezone=True)`, so a value read back from SQLite may be naive
    UTC while a freshly built one is aware. Normalizing keeps every assertion
    about the *instant*, never about the tzinfo representation.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


async def _snapshot() -> list[tuple[object, ...]]:
    """Every sub-agent row's complete stored state, read straight from `db/`.

    Id, name, prompt, disabled, the model pair, both timestamps and both link
    row sets, per row, id-sorted. This is the value the "nothing is written" /
    "the existing rows are unchanged" clauses of DoD-4, DoD-6 and DoD-7 compare
    before against after: it bites on a row that should not have been created,
    on a field that should not have changed, and on a refreshed `modified_at`.
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


async def _stored(sub_agent_id: str) -> SubAgent:
    """The stored row behind a DTO id."""
    row = await sub_agents.get_by_id(int(sub_agent_id))
    assert row is not None
    return row


async def _listed(sub_agent_id: str) -> SubAgentResponse:
    """The one SubAgentResponse for `sub_agent_id`, read through the lister."""
    listed = await config_service.list_sub_agents()
    matches = [item for item in listed.items if item.id == sub_agent_id]
    assert len(matches) == 1
    return matches[0]


# ---------------------------------------------------------------------------
# DoD-1 — create stores the sub-agent and returns the full DTO
#         (UC-096; US-113.AC-1)
# ---------------------------------------------------------------------------


# DoD-1 (UC-096; US-113.AC-1): creating a sub-agent with a name, a prompt and no
# model stores it and returns it with a STRING id, `disabled` false, both link
# lists empty, and both timestamps set. The link lists are read from the start so
# the response shape never changes after this step — they are empty because there
# is no write path for them until step 004.
async def test_create_stores_and_returns_sub_agent__DoD1_UC096_US113_AC1(
    db: DbConfig,
):
    created = await config_service.create_sub_agent(
        _create_req(
            "continuity-checker",
            "Check the manuscript for continuity errors.",
            None,
            None,
        )
    )

    assert isinstance(created, SubAgentResponse)

    # A string id at the JSON boundary, over a snowflake row id.
    assert isinstance(created.id, str)
    assert int(created.id) > 0

    assert created.name == "continuity-checker"
    assert created.system_prompt == "Check the manuscript for continuity errors."

    # A freshly created sub-agent is enabled.
    assert created.disabled is False

    # Both link lists are present and empty.
    assert created.tool_names == []
    assert created.mode_keys == []

    # Both timestamps are set.
    assert created.created_at is not None
    assert created.modified_at is not None

    # ...and it really is stored, with the same values on the row.
    row = await _stored(created.id)
    assert row.name == "continuity-checker"
    assert row.system_prompt == "Check the manuscript for continuity errors."
    assert row.disabled is False
    assert row.created_at is not None
    assert row.modified_at is not None

    # The lister finds it.
    listed = await _listed(created.id)
    assert listed.name == "continuity-checker"
    assert listed.system_prompt == "Check the manuscript for continuity errors."
    assert listed.disabled is False
    assert listed.tool_names == []
    assert listed.mode_keys == []
    assert listed.created_at is not None
    assert listed.modified_at is not None

    # An empty system prompt is a legal stored value — only the NAME is
    # blank-checked (003.context.md -> "`SubAgent` field notes").
    empty_prompt = await config_service.create_sub_agent(
        _create_req("terse-agent", "", None, None)
    )
    assert empty_prompt.system_prompt == ""
    assert (await _stored(empty_prompt.id)).system_prompt == ""


# ---------------------------------------------------------------------------
# DoD-2 — no model assignment is stored as null/null (US-113.AC-6)
# ---------------------------------------------------------------------------


# DoD-2 (US-113.AC-6): a created sub-agent with NO model assignment stores
# `llm_server_id` and `model_name` as null — the recorded state for "re-use the
# main chat's model", which is the default. Both fields are passed explicitly as
# None (the request has no defaults); null + null is a meaningful value, not an
# omission.
async def test_create_without_model_stores_nulls__DoD2_US113_AC6(db: DbConfig):
    created = await config_service.create_sub_agent(
        _create_req("inheriting-agent", "You inherit the model.", None, None)
    )

    # The response carries the inherit state as null/null.
    assert created.llm_server_id is None
    assert created.model_name is None

    # ...and so does the stored row.
    row = await _stored(created.id)
    assert row.llm_server_id is None
    assert row.model_name is None

    # ...and so does the lister's view of it.
    listed = await _listed(created.id)
    assert listed.llm_server_id is None
    assert listed.model_name is None


# ---------------------------------------------------------------------------
# DoD-3 — an active server + an enabled model is stored, id as a string
#         (US-113.AC-5)
# ---------------------------------------------------------------------------


# DoD-3 (US-113.AC-5): a create naming an ACTIVE server and a model listed in
# that server's `enabled_models` stores both fields, and the response returns
# `llm_server_id` as a STRING (the row column is an int FK; the wire is a str,
# both directions — 003.context.md -> Gotchas).
async def test_create_with_active_server_and_enabled_model__DoD3_US113_AC5(
    db: DbConfig,
):
    server = await _seed_server(
        name="Primary", enabled_models='["gpt-x", "gpt-y"]', is_active=True
    )
    assert server.is_active is True

    created = await config_service.create_sub_agent(
        _create_req("model-bound-agent", "You use a specific model.", str(server.id), "gpt-y")
    )

    # The response: server id as a STRING, model name verbatim.
    assert created.llm_server_id == str(server.id)
    assert isinstance(created.llm_server_id, str)
    assert created.model_name == "gpt-y"

    # The row: an int FK.
    row = await _stored(created.id)
    assert row.llm_server_id == server.id
    assert isinstance(row.llm_server_id, int)
    assert row.model_name == "gpt-y"

    # The lister agrees, string id and all.
    listed = await _listed(created.id)
    assert listed.llm_server_id == str(server.id)
    assert isinstance(listed.llm_server_id, str)
    assert listed.model_name == "gpt-y"


# ---------------------------------------------------------------------------
# DoD-4 — a half-set model pair is refused, on create and on update, and
#         nothing is written (US-113.AC-5)
# ---------------------------------------------------------------------------


# DoD-4 (US-113.AC-5): a half-set pair on CREATE — a server without a model, or a
# model without a server — is refused with the invalid-model-pair reason, and
# nothing is written: no new row appears and the pre-existing sub-agent is
# untouched ("All validation happens before any write"). The two model fields
# move together (assistant-config.md).
async def test_create_half_set_pair_refused_and_writes_nothing__DoD4_US113_AC5(
    db: DbConfig,
):
    server = await _seed_server(name="Primary", enabled_models='["gpt-x"]')

    # An existing, valid sub-agent whose state must survive every refusal.
    await config_service.create_sub_agent(
        _create_req("existing-agent", "I already exist.", str(server.id), "gpt-x")
    )
    before = await _snapshot()
    assert len(before) == 1

    half_set_bodies = (
        # A server without a model...
        _create_req("half-a", "Must not land.", str(server.id), None),
        # ...and a model without a server.
        _create_req("half-b", "Must not land.", None, "gpt-x"),
    )

    for body in half_set_bodies:
        with pytest.raises(config_service.AssistantConfigError) as exc:
            await config_service.create_sub_agent(body)

        assert (
            exc.value.reason
            == config_service.AssistantConfigErrorReason.invalid_model_pair
        )
        assert exc.value.reason.value == "invalid-model-pair"

        # Nothing was written by this attempt: no row for the refused name, and
        # the existing row is byte-for-byte as before.
        assert await sub_agents.get_by_name(body.name) is None
        assert await _snapshot() == before

    # The lister still shows exactly the one pre-existing sub-agent.
    listed = await config_service.list_sub_agents()
    assert [item.name for item in listed.items] == ["existing-agent"]


# DoD-4 (US-113.AC-5): the same half-set pair on UPDATE is refused with
# invalid-model-pair, and nothing is written — the sub-agent's name, prompt,
# stored pair and `modified_at` are all exactly as before the refused save.
async def test_update_half_set_pair_refused_and_writes_nothing__DoD4_US113_AC5(
    db: DbConfig,
):
    server = await _seed_server(name="Primary", enabled_models='["gpt-x"]')

    target = await config_service.create_sub_agent(
        _create_req("target-agent", "Original prompt.", str(server.id), "gpt-x")
    )
    before = await _snapshot()

    half_set_bodies = (
        _update_req("renamed-agent", "Must not land.", str(server.id), None),
        _update_req("renamed-agent", "Must not land.", None, "gpt-x"),
    )

    for body in half_set_bodies:
        with pytest.raises(config_service.AssistantConfigError) as exc:
            await config_service.update_sub_agent(target.id, body)

        assert (
            exc.value.reason
            == config_service.AssistantConfigErrorReason.invalid_model_pair
        )
        assert exc.value.reason.value == "invalid-model-pair"

        assert await _snapshot() == before

    # Read through the service too: the sub-agent is unchanged.
    listed = await _listed(target.id)
    assert listed.name == "target-agent"
    assert listed.system_prompt == "Original prompt."
    assert listed.llm_server_id == str(server.id)
    assert listed.model_name == "gpt-x"


# ---------------------------------------------------------------------------
# DoD-5 — unknown / inactive server and not-enabled model (US-113.AC-5)
# ---------------------------------------------------------------------------


# DoD-5 (US-113.AC-5): a pair naming a server that does not exist, or one that
# exists but whose `is_active` is false, is refused with the
# unknown-or-inactive-server reason. The Interface intent's rule 3 puts an
# unparsable server id under the same reason, so a malformed id is a refusal, not
# a 500.
async def test_create_unknown_or_inactive_server_refused__DoD5_US113_AC5(
    db: DbConfig,
):
    # 1. A server id no row carries.
    assert await llm_servers.get_by_id(MISSING_ID) is None

    with pytest.raises(config_service.AssistantConfigError) as missing_exc:
        await config_service.create_sub_agent(
            _create_req("agent-a", "p", str(MISSING_ID), "gpt-x")
        )
    assert (
        missing_exc.value.reason
        == config_service.AssistantConfigErrorReason.unknown_or_inactive_server
    )
    assert missing_exc.value.reason.value == "unknown-or-inactive-server"
    assert await sub_agents.get_by_name("agent-a") is None

    # 2. A server that EXISTS but is not active — the row is found and then
    #    rejected on `is_active`, which is the same reason, not a distinct one.
    inactive = await _seed_server(
        name="Down", enabled_models='["gpt-x"]', is_active=False
    )
    stored_server = await llm_servers.get_by_id(inactive.id)
    assert stored_server is not None
    assert stored_server.is_active is False

    with pytest.raises(config_service.AssistantConfigError) as inactive_exc:
        await config_service.create_sub_agent(
            _create_req("agent-b", "p", str(inactive.id), "gpt-x")
        )
    assert (
        inactive_exc.value.reason
        == config_service.AssistantConfigErrorReason.unknown_or_inactive_server
    )
    assert await sub_agents.get_by_name("agent-b") is None

    # 3. A server id that does not parse at all (Interface intent rule 3).
    with pytest.raises(config_service.AssistantConfigError) as unparsable_exc:
        await config_service.create_sub_agent(
            _create_req("agent-c", "p", "not-a-server-id", "gpt-x")
        )
    assert (
        unparsable_exc.value.reason
        == config_service.AssistantConfigErrorReason.unknown_or_inactive_server
    )
    assert await sub_agents.get_by_name("agent-c") is None

    # No sub-agent was created by any of the three refusals.
    assert await sub_agents.list_all() == []


# DoD-5 (US-113.AC-5): a pair naming an ACTIVE server but a model absent from
# that server's decoded `enabled_models` is refused with the model-not-enabled
# reason — a different reason from the server refusals, because the server itself
# is fine.
async def test_create_model_not_enabled_refused__DoD5_US113_AC5(db: DbConfig):
    server = await _seed_server(
        name="Primary", enabled_models='["only-this"]', is_active=True
    )

    with pytest.raises(config_service.AssistantConfigError) as exc:
        await config_service.create_sub_agent(
            _create_req("agent-d", "p", str(server.id), "not-there")
        )

    assert (
        exc.value.reason
        == config_service.AssistantConfigErrorReason.model_not_enabled
    )
    assert exc.value.reason.value == "model-not-enabled"
    assert await sub_agents.get_by_name("agent-d") is None
    assert await sub_agents.list_all() == []

    # An empty enabled list enables nothing: the same refusal.
    empty = await _seed_server(name="Empty", enabled_models="[]", is_active=True)
    with pytest.raises(config_service.AssistantConfigError) as empty_exc:
        await config_service.create_sub_agent(
            _create_req("agent-e", "p", str(empty.id), "gpt-x")
        )
    assert (
        empty_exc.value.reason
        == config_service.AssistantConfigErrorReason.model_not_enabled
    )


# DoD-5 (US-113.AC-5): the updater applies the same model-pair validation — an
# inactive server is refused with unknown-or-inactive-server, and a model absent
# from an active server's `enabled_models` with model-not-enabled.
async def test_update_server_and_model_validation__DoD5_US113_AC5(db: DbConfig):
    active = await _seed_server(name="Primary", enabled_models='["gpt-x"]')
    inactive = await _seed_server(
        name="Down", enabled_models='["gpt-x"]', is_active=False
    )

    target = await config_service.create_sub_agent(
        _create_req("target-agent", "Original prompt.", None, None)
    )
    before = await _snapshot()

    with pytest.raises(config_service.AssistantConfigError) as inactive_exc:
        await config_service.update_sub_agent(
            target.id,
            _update_req("target-agent", "Original prompt.", str(inactive.id), "gpt-x"),
        )
    assert (
        inactive_exc.value.reason
        == config_service.AssistantConfigErrorReason.unknown_or_inactive_server
    )

    with pytest.raises(config_service.AssistantConfigError) as not_enabled_exc:
        await config_service.update_sub_agent(
            target.id,
            _update_req("target-agent", "Original prompt.", str(active.id), "nope"),
        )
    assert (
        not_enabled_exc.value.reason
        == config_service.AssistantConfigErrorReason.model_not_enabled
    )

    # Validation precedes the write, so the sub-agent still has no assignment.
    assert await _snapshot() == before


# ---------------------------------------------------------------------------
# DoD-6 — a duplicate name is refused on create and on update, and the
#         existing rows are unchanged (US-113.AC-3; UC-097)
# ---------------------------------------------------------------------------


# DoD-6 (US-113.AC-3): a create whose name is already held by another sub-agent
# is refused with the name-taken reason, and the existing rows are unchanged. The
# name is trimmed BEFORE the collision check, so a padded duplicate collides too
# (003.context.md -> Gotchas: `" x "` and `"x"` cannot both be stored) — and a
# padded unique name is stored trimmed.
async def test_create_duplicate_name_refused_and_rows_unchanged__DoD6_US113_AC3(
    db: DbConfig,
):
    first = await config_service.create_sub_agent(
        _create_req("alpha-agent", "First prompt.", None, None)
    )
    await config_service.create_sub_agent(
        _create_req("beta-agent", "Second prompt.", None, None)
    )
    before = await _snapshot()
    assert len(before) == 2

    for colliding_name in ("alpha-agent", "  alpha-agent  "):
        with pytest.raises(config_service.AssistantConfigError) as exc:
            await config_service.create_sub_agent(
                _create_req(colliding_name, "Must not land.", None, None)
            )

        assert (
            exc.value.reason == config_service.AssistantConfigErrorReason.name_taken
        )
        assert exc.value.reason.value == "name-taken"

        # Nothing written: still two rows, both exactly as before.
        assert await _snapshot() == before

    # The original keeps its own prompt — the refused create did not overwrite it.
    assert (await _listed(first.id)).system_prompt == "First prompt."
    listed = await config_service.list_sub_agents()
    assert len(listed.items) == 2

    # A padded but unique name is accepted and stored TRIMMED, which is why the
    # padded duplicate above could not be a second row.
    padded = await config_service.create_sub_agent(
        _create_req("  gamma-agent  ", "Third prompt.", None, None)
    )
    assert padded.name == "gamma-agent"
    assert (await _stored(padded.id)).name == "gamma-agent"


# DoD-6 (UC-097 exception flow): an update that renames a sub-agent to a name
# another sub-agent already holds is refused with name-taken, and the existing
# rows are unchanged — neither the row being updated nor the one holding the name.
async def test_update_duplicate_name_refused_and_rows_unchanged__DoD6_UC097(
    db: DbConfig,
):
    holder = await config_service.create_sub_agent(
        _create_req("alpha-agent", "Holder prompt.", None, None)
    )
    target = await config_service.create_sub_agent(
        _create_req("beta-agent", "Target prompt.", None, None)
    )
    before = await _snapshot()

    for colliding_name in ("alpha-agent", "  alpha-agent  "):
        with pytest.raises(config_service.AssistantConfigError) as exc:
            await config_service.update_sub_agent(
                target.id,
                _update_req(colliding_name, "Must not land.", None, None),
            )

        assert (
            exc.value.reason == config_service.AssistantConfigErrorReason.name_taken
        )
        assert exc.value.reason.value == "name-taken"

        assert await _snapshot() == before

    # Both sub-agents kept their own name and prompt.
    assert (await _listed(holder.id)).name == "alpha-agent"
    assert (await _listed(holder.id)).system_prompt == "Holder prompt."
    assert (await _listed(target.id)).name == "beta-agent"
    assert (await _listed(target.id)).system_prompt == "Target prompt."


# ---------------------------------------------------------------------------
# DoD-7 — a blank or whitespace-only name is refused (UC-096; US-113.AC-1)
# ---------------------------------------------------------------------------


# DoD-7 (UC-096 exception flow; US-113.AC-1): a blank or whitespace-only name is
# refused on CREATE with the blank-name reason — the name is trimmed and an empty
# result is refused — and nothing is written.
async def test_create_blank_name_refused_and_writes_nothing__DoD7_UC096_US113_AC1(
    db: DbConfig,
):
    await config_service.create_sub_agent(
        _create_req("existing-agent", "I already exist.", None, None)
    )
    before = await _snapshot()
    assert len(before) == 1

    for blank_name in ("", "   ", "\t\n ", "  "):
        with pytest.raises(config_service.AssistantConfigError) as exc:
            await config_service.create_sub_agent(
                _create_req(blank_name, "Must not land.", None, None)
            )

        assert (
            exc.value.reason == config_service.AssistantConfigErrorReason.blank_name
        )
        assert exc.value.reason.value == "blank-name"

        # Nothing written by this attempt.
        assert await _snapshot() == before

    listed = await config_service.list_sub_agents()
    assert [item.name for item in listed.items] == ["existing-agent"]


# DoD-7 (UC-096 exception flow; US-113.AC-1): a blank or whitespace-only name is
# refused on UPDATE with the blank-name reason, and nothing is written — the
# sub-agent keeps its name, its prompt and its `modified_at`.
async def test_update_blank_name_refused_and_writes_nothing__DoD7_UC096_US113_AC1(
    db: DbConfig,
):
    target = await config_service.create_sub_agent(
        _create_req("alpha-agent", "Original prompt.", None, None)
    )
    before = await _snapshot()

    for blank_name in ("", "   ", "\t\n "):
        with pytest.raises(config_service.AssistantConfigError) as exc:
            await config_service.update_sub_agent(
                target.id, _update_req(blank_name, "Must not land.", None, None)
            )

        assert (
            exc.value.reason == config_service.AssistantConfigErrorReason.blank_name
        )
        assert exc.value.reason.value == "blank-name"

        assert await _snapshot() == before

    listed = await _listed(target.id)
    assert listed.name == "alpha-agent"
    assert listed.system_prompt == "Original prompt."


# ---------------------------------------------------------------------------
# DoD-8 — saving a sub-agent unrenamed is not a self-collision (US-114.AC-1)
# ---------------------------------------------------------------------------


# DoD-8 (US-114.AC-1): updating a sub-agent WITHOUT changing its name succeeds —
# the uniqueness check excludes the row being updated, so its own name is not a
# collision. A second sub-agent exists so the check has a real other row to look
# at, and the save is repeated to show it is not a one-time allowance.
async def test_update_same_name_is_not_self_collision__DoD8_US114_AC1(db: DbConfig):
    await config_service.create_sub_agent(
        _create_req("other-agent", "Another sub-agent.", None, None)
    )
    target = await config_service.create_sub_agent(
        _create_req("alpha-agent", "Original prompt.", None, None)
    )

    saved = await config_service.update_sub_agent(
        target.id, _update_req("alpha-agent", "A revised prompt.", None, None)
    )

    # Accepted: same id, same name, the new prompt.
    assert saved.id == target.id
    assert saved.name == "alpha-agent"
    assert saved.system_prompt == "A revised prompt."
    assert saved.disabled is False

    row = await _stored(target.id)
    assert row.name == "alpha-agent"
    assert row.system_prompt == "A revised prompt."

    # Saving the unchanged name again is still fine.
    saved_again = await config_service.update_sub_agent(
        target.id, _update_req("alpha-agent", "A third prompt.", None, None)
    )
    assert saved_again.name == "alpha-agent"
    assert saved_again.system_prompt == "A third prompt."

    # No duplicate row was created along the way.
    assert len(await sub_agents.list_all()) == 2


# ---------------------------------------------------------------------------
# DoD-9 — an update stores the changed scalars and the changed model pair,
#         and `modified_at` advances (US-114.AC-1, US-114.AC-4)
# ---------------------------------------------------------------------------


# DoD-9 (US-114.AC-1): an update stores a changed name and prompt, and
# `modified_at` advances. `created_at` is only set on create — the updater
# refreshes `modified_at` alone (003.context.md -> Gotchas).
async def test_update_stores_scalars_and_advances_modified_at__DoD9_US114_AC1(
    db: DbConfig,
):
    created = await config_service.create_sub_agent(
        _create_req("alpha-agent", "Original prompt.", None, None)
    )
    row_before = await _stored(created.id)
    assert row_before.modified_at is not None

    # Guarantee a measurable gap, so "advances" is a strict comparison.
    await asyncio.sleep(0.05)

    saved = await config_service.update_sub_agent(
        created.id, _update_req("renamed-agent", "A revised prompt.", None, None)
    )

    assert saved.id == created.id
    assert saved.name == "renamed-agent"
    assert saved.system_prompt == "A revised prompt."

    row_after = await _stored(created.id)
    assert row_after.name == "renamed-agent"
    assert row_after.system_prompt == "A revised prompt."

    # modified_at advanced...
    assert row_after.modified_at is not None
    assert created.modified_at is not None
    assert saved.modified_at is not None
    assert _naive_utc(row_after.modified_at) > _naive_utc(row_before.modified_at)
    assert _naive_utc(saved.modified_at) > _naive_utc(created.modified_at)
    # ...and created_at did not move.
    assert row_after.created_at == row_before.created_at

    # The lister reflects the new name; the old one is gone.
    listed = await config_service.list_sub_agents()
    assert [item.name for item in listed.items] == ["renamed-agent"]


# DoD-9 (US-114.AC-4): an update stores a changed model assignment in BOTH
# directions — from null/null (inherit the main chat's model) to a specific pair,
# and from a specific pair back to null/null. Writes are full-replace, so
# null/null really clears the stored pair rather than leaving it in place.
async def test_update_switches_model_pair_both_directions__DoD9_US114_AC4(
    db: DbConfig,
):
    server = await _seed_server(name="Primary", enabled_models='["gpt-x", "gpt-y"]')

    created = await config_service.create_sub_agent(
        _create_req("alpha-agent", "Original prompt.", None, None)
    )
    assert created.llm_server_id is None
    assert created.model_name is None

    # 1. null/null -> a specific pair.
    assigned = await config_service.update_sub_agent(
        created.id,
        _update_req("alpha-agent", "Original prompt.", str(server.id), "gpt-x"),
    )
    assert assigned.llm_server_id == str(server.id)
    assert isinstance(assigned.llm_server_id, str)
    assert assigned.model_name == "gpt-x"
    row = await _stored(created.id)
    assert row.llm_server_id == server.id
    assert row.model_name == "gpt-x"

    # 2. one specific pair -> another model on the same server.
    reassigned = await config_service.update_sub_agent(
        created.id,
        _update_req("alpha-agent", "Original prompt.", str(server.id), "gpt-y"),
    )
    assert reassigned.model_name == "gpt-y"
    assert (await _stored(created.id)).model_name == "gpt-y"

    # 3. a specific pair -> back to null/null: inherit the main chat's model.
    inherited = await config_service.update_sub_agent(
        created.id, _update_req("alpha-agent", "Original prompt.", None, None)
    )
    assert inherited.llm_server_id is None
    assert inherited.model_name is None
    cleared_row = await _stored(created.id)
    assert cleared_row.llm_server_id is None
    assert cleared_row.model_name is None

    # The lister agrees the assignment is gone.
    listed = await _listed(created.id)
    assert listed.llm_server_id is None
    assert listed.model_name is None


# ---------------------------------------------------------------------------
# DoD-10 — an id with no row is refused (UC-097 precondition)
# ---------------------------------------------------------------------------


# DoD-10 (UC-097 precondition — the sub-agent exists): updating a sub-agent id
# with no row is refused with the sub-agent-not-found reason. Both a well-formed
# id that no row carries and an ILL-FORMED id are "a sub-agent that is not
# there": the id crosses this boundary as a string and the service owns the
# parse, so a malformed id is a refusal with this reason, never an escaping
# ValueError. (An unparsable id inside a mode's `sub_agent_ids` body list is a
# different reason and a different surface — step 002's unknown-sub-agent.)
async def test_update_missing_or_ill_formed_id_refused__DoD10_UC097(db: DbConfig):
    # An untouched sub-agent, so "wrote nothing" has something to protect.
    await config_service.create_sub_agent(
        _create_req("existing-agent", "I already exist.", None, None)
    )
    before = await _snapshot()

    assert await sub_agents.get_by_id(MISSING_ID) is None

    bad_ids = (str(MISSING_ID), *ILL_FORMED_IDS)

    for bad_id in bad_ids:
        with pytest.raises(config_service.AssistantConfigError) as exc:
            await config_service.update_sub_agent(
                bad_id, _update_req("a-new-name", "A prompt.", None, None)
            )

        assert (
            exc.value.reason
            == config_service.AssistantConfigErrorReason.sub_agent_not_found
        )
        assert exc.value.reason.value == "sub-agent-not-found"

        # The refused update created nothing and changed nothing.
        assert await _snapshot() == before
        assert await sub_agents.get_by_name("a-new-name") is None

    listed = await config_service.list_sub_agents()
    assert [item.name for item in listed.items] == ["existing-agent"]


# ---------------------------------------------------------------------------
# DoD-11 — the lister returns every sub-agent, name-ordered, disabled included
#          (US-114.AC-3)
# ---------------------------------------------------------------------------


# DoD-11 (US-114.AC-3): the lister returns EVERY sub-agent ordered by name,
# INCLUDING disabled ones, each carrying its `disabled` flag — a disabled
# sub-agent must remain findable so that it can be re-enabled. Rows are arranged
# out of alphabetical order so insertion order cannot masquerade as name order,
# and the disabled one sorts in the middle so it cannot be silently filtered.
async def test_list_sub_agents_orders_by_name_including_disabled__DoD11_US114_AC3(
    db: DbConfig,
):
    # An instance with no sub-agents lists none.
    empty = await config_service.list_sub_agents()
    assert empty.items == []

    server = await _seed_server(name="Primary", enabled_models='["gpt-x"]')

    # Created out of order, through the service where possible.
    await config_service.create_sub_agent(
        _create_req("zeta-agent", "Last by name.", None, None)
    )
    await config_service.create_sub_agent(
        _create_req("alpha-agent", "First by name.", str(server.id), "gpt-x")
    )
    # `disabled` can only be arranged through `db/`: disable/enable is step 004's
    # operation and the update request carries no `disabled` field.
    disabled_row = await _seed_sub_agent_row("mid-agent", disabled=True)
    await config_service.create_sub_agent(
        _create_req("beta-agent", "Second by name.", None, None)
    )

    listed = await config_service.list_sub_agents()

    # Every sub-agent, name-ascending.
    assert [item.name for item in listed.items] == [
        "alpha-agent",
        "beta-agent",
        "mid-agent",
        "zeta-agent",
    ]
    assert len(listed.items) == 4

    # Each entry carries its own `disabled` flag, so the surface can mark it.
    assert {item.name: item.disabled for item in listed.items} == {
        "alpha-agent": False,
        "beta-agent": False,
        "mid-agent": True,
        "zeta-agent": False,
    }

    by_name = {item.name: item for item in listed.items}

    # The disabled sub-agent is findable and fully described.
    disabled_item = by_name["mid-agent"]
    assert disabled_item.id == str(disabled_row.id)
    assert isinstance(disabled_item.id, str)
    assert disabled_item.disabled is True
    assert disabled_item.tool_names == []
    assert disabled_item.mode_keys == []

    # An entry's model assignment is carried through the lister, id as a string.
    assigned_item = by_name["alpha-agent"]
    assert assigned_item.llm_server_id == str(server.id)
    assert isinstance(assigned_item.llm_server_id, str)
    assert assigned_item.model_name == "gpt-x"

    # ...and an unassigned one reports null/null.
    assert by_name["beta-agent"].llm_server_id is None
    assert by_name["beta-agent"].model_name is None
