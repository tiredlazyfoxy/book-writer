"""Tests for the session-free db/llm_servers access layer (feature 006, step 001).

Bound to the frozen skeleton signatures (status.md -> Skeleton -> Step 001):
    class LlmServer(SQLModel, table=True) __tablename__="llm_servers"; fields:
        id: int (snowflake PK, default_factory=generate_id), name: str, backend_type: str,
        base_url: str, api_key: str | None, enabled_models: str = "[]",
        is_active: bool = True, is_embedding: bool = False,
        embedding_model: str | None, created_at: datetime | None,
        modified_at: datetime | None                         in app.models.llm_server
    async def get_by_id(server_id: int) -> LlmServer | None    in app.db.llm_servers
    async def get_all() -> list[LlmServer]                     in app.db.llm_servers
    async def get_active() -> list[LlmServer]                  in app.db.llm_servers
    async def create(server: LlmServer) -> LlmServer          in app.db.llm_servers
    async def update(server: LlmServer) -> None               in app.db.llm_servers
    async def delete(server_id: int) -> bool                  in app.db.llm_servers
    async def clear_all_embedding() -> None                    in app.db.llm_servers
    async def get_embedding_server() -> LlmServer | None       in app.db.llm_servers
    @dataclass class DbConfig(db_path, echo=False)            in app.db.engine

Expected values come from the step spec (001.model-db-importexport.md DoD +
context decisions D1/D5/D6), never from implementation internals:
    - DoD-1 (US-010.AC-1): a server created with every field set round-trips
      through get_by_id and appears in get_all,
    - DoD-2 (US-013.AC-2): delete(id) removes the row and returns True; delete
      on a non-matching id returns False (the first delete pattern),
    - DoD-3 (D5): clear_all_embedding() clears is_embedding on every row;
      get_embedding_server() returns the single flagged row, or None,
    - DoD-4 (D1/D5): get_all is name-ordered; get_active returns only is_active
      rows (name-ordered), excluding inactive ones.

These are async tests (asyncio_mode = "auto"). The `db` fixture (conftest, from
feature 001/002) supplies an initialized throwaway temp-SQLite engine whose
schema — including the `llm_servers` table (registered via the engine hook in
this step) — is built via init_db().
"""

from datetime import datetime

from app.db import llm_servers
from app.db.engine import DbConfig
from app.models.llm_server import LlmServer


# DoD-1 (US-010.AC-1): a LlmServer created via create() with every field set is
# retrievable by get_by_id with every field round-tripped, and appears in
# get_all. `enabled_models` is stored/returned as its raw JSON string (db layer
# does not decode it); `api_key` is a stored `$ENV_VAR` token.
async def test_create_round_trips_every_field_and_appears_in_get_all__DoD1(
    db: DbConfig,
):
    created_at = datetime(2026, 7, 23, 12, 30, 0)
    modified_at = datetime(2026, 7, 23, 13, 45, 0)
    server = LlmServer(
        name="OpenAI Prod",
        backend_type="openai",
        base_url="https://api.openai.com/v1",
        api_key="$OPENAI_API_KEY",
        enabled_models='["gpt-4o", "gpt-4o-mini"]',
        is_active=True,
        is_embedding=True,
        embedding_model="text-embedding-3-small",
        created_at=created_at,
        modified_at=modified_at,
    )

    created = await llm_servers.create(server)

    # create() persists the row; the snowflake PK is assigned at construction
    # (default_factory=generate_id), so it is already populated (review R1).
    assert created.id is not None

    fetched = await llm_servers.get_by_id(created.id)

    # Every field round-trips through get_by_id.
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.name == "OpenAI Prod"
    assert fetched.backend_type == "openai"
    assert fetched.base_url == "https://api.openai.com/v1"
    assert fetched.api_key == "$OPENAI_API_KEY"
    assert fetched.enabled_models == '["gpt-4o", "gpt-4o-mini"]'
    assert fetched.is_active is True
    assert fetched.is_embedding is True
    assert fetched.embedding_model == "text-embedding-3-small"
    assert fetched.created_at == created_at
    assert fetched.modified_at == modified_at

    # The created row also appears in get_all.
    all_ids = [s.id for s in await llm_servers.get_all()]
    assert created.id in all_ids


# DoD-2 (US-013.AC-2): delete(id) removes the row — a subsequent get_by_id
# returns None — and returns True; delete on an id with no matching row returns
# False (the codebase's first delete pattern).
async def test_delete_removes_row_and_reports_match__DoD2(db: DbConfig):
    created = await llm_servers.create(
        LlmServer(
            name="ToDelete",
            backend_type="openai",
            base_url="https://api.openai.com/v1",
        )
    )
    assert created.id is not None

    # Deleting an existing row returns True...
    assert await llm_servers.delete(created.id) is True

    # ...and the row is gone afterwards.
    assert await llm_servers.get_by_id(created.id) is None


async def test_delete_nonmatching_id_returns_false__DoD2(db: DbConfig):
    # No row was ever created with this id, so delete matches nothing and must
    # return False (used by the route layer to distinguish 404).
    assert await llm_servers.delete(999999) is False


# DoD-3 (D5): get_embedding_server() returns None when no row is flagged, and
# returns the single flagged row when exactly one is; clear_all_embedding()
# clears is_embedding on every row (so get_embedding_server() then returns None).
async def test_embedding_flag_lifecycle__DoD3(db: DbConfig):
    # With no flagged row present, get_embedding_server() returns None.
    plain = await llm_servers.create(
        LlmServer(
            name="Plain",
            backend_type="openai",
            base_url="https://api.openai.com/v1",
            is_embedding=False,
        )
    )
    assert await llm_servers.get_embedding_server() is None

    # Flag exactly one server as the embedding provider.
    flagged = await llm_servers.create(
        LlmServer(
            name="Embedder",
            backend_type="openai",
            base_url="https://api.openai.com/v1",
            is_embedding=True,
            embedding_model="text-embedding-3-small",
        )
    )

    # get_embedding_server() returns that single flagged row.
    current = await llm_servers.get_embedding_server()
    assert current is not None
    assert current.id == flagged.id
    assert current.is_embedding is True

    # clear_all_embedding() clears is_embedding across every row.
    await llm_servers.clear_all_embedding()

    # The previously-flagged row is no longer flagged...
    cleared = await llm_servers.get_by_id(flagged.id)
    assert cleared is not None
    assert cleared.is_embedding is False
    # ...the already-unflagged row remains unflagged...
    still_plain = await llm_servers.get_by_id(plain.id)
    assert still_plain is not None
    assert still_plain.is_embedding is False
    # ...and no embedding server is reported.
    assert await llm_servers.get_embedding_server() is None


# DoD-4 (D1/D5): get_all returns rows ordered by name.
async def test_get_all_ordered_by_name__DoD4(db: DbConfig):
    # Insert out of alphabetical order.
    for name in ("Charlie", "Alpha", "Bravo"):
        await llm_servers.create(
            LlmServer(
                name=name,
                backend_type="openai",
                base_url="https://api.openai.com/v1",
            )
        )

    names = [s.name for s in await llm_servers.get_all()]
    assert names == ["Alpha", "Bravo", "Charlie"]


# DoD-4 (D1/D5): get_active returns only is_active rows, ordered by name,
# excluding inactive ones.
async def test_get_active_excludes_inactive_and_is_name_ordered__DoD4(db: DbConfig):
    await llm_servers.create(
        LlmServer(
            name="Zeta",
            backend_type="openai",
            base_url="https://api.openai.com/v1",
            is_active=True,
        )
    )
    await llm_servers.create(
        LlmServer(
            name="Yankee",
            backend_type="openai",
            base_url="https://api.openai.com/v1",
            is_active=False,
        )
    )
    await llm_servers.create(
        LlmServer(
            name="Xray",
            backend_type="openai",
            base_url="https://api.openai.com/v1",
            is_active=True,
        )
    )

    active = await llm_servers.get_active()

    # Only the two active rows are returned, and they are name-ordered.
    assert [s.name for s in active] == ["Xray", "Zeta"]
    # Every returned row is active (the inactive one is excluded).
    assert all(s.is_active is True for s in active)
