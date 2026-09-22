"""Tests for the AssistantMode first-run seed (feature 008, step 003).

Bound to the frozen skeleton signatures (status.md -> Skeleton -> Step 003):
    async def seed_default_modes() -> None                    in app.db.assistant_modes
    async def create_database(admin_username: str, password: str,
        password_confirm: str) -> User                        in app.services.setup

Supporting frozen signatures reused from earlier steps:
    async def list_all() -> list[AssistantMode]               in app.db.assistant_modes
    def is_db_ready() -> bool                                 in app.db.engine

Expected values come from the step spec (003.assistant-mode-seed.md DoD +
Interface intent + 003.context.md), never from implementation internals:
    - The fixed five mode keys are exactly `edit-character`, `edit-location`,
      `edit-fact`, `write-chapter`, `close-chapter`; each seeded row has
      `system_prompt = None` (003.context.md -> "The fixed five modes");
    - DoD-1: on a fresh throwaway DB, seed_default_modes() creates exactly five
      AssistantMode rows whose keys are exactly the fixed five;
    - DoD-2: seed_default_modes() is idempotent — a second call leaves exactly
      five rows (no duplicates) and raises no error;
    - DoD-3: create_database threads the seed through the setup path, so after it
      completes on a fresh instance the five mode rows exist.
    (DoD-4 is [manual/live] — no automated test.)

These are async tests (asyncio_mode = "auto"). The `db` fixture (conftest)
supplies an initialized throwaway temp-SQLite engine (init_engine + init_db), so
the schema is present. The autouse `_reset_db_ready` fixture resets the
process-global readiness flag to False before each test.
"""

from app.db import assistant_modes
from app.db.engine import DbConfig, is_db_ready
from app.services import setup

# The fixed five mode keys — the system set, from the spec
# (003.assistant-mode-seed.md Interface intent + 003.context.md).
FIXED_FIVE_KEYS = {
    "edit-character",
    "edit-location",
    "edit-fact",
    "write-chapter",
    "close-chapter",
}


# ---------------------------------------------------------------------------
# DoD-1 — seed creates exactly the fixed five rows on a fresh DB
# ---------------------------------------------------------------------------


# DoD-1: on a fresh throwaway DB (init_db already ran via the fixture), calling
# seed_default_modes() creates exactly five AssistantMode rows, whose keys are
# exactly the fixed five; each seeded row carries a real system_prompt.
#
# Amended by feature 024 (chat-agent-loop), decision D4: the seed now writes
# `DEFAULT_MODE_SYSTEM_PROMPTS[key]` for a key with no existing row, in place of
# the `system_prompt=None` this clause originally pinned (024/plan.md -> DoD-4 and
# DoD-12: "Each of the five seeded AssistantMode rows carries a non-blank
# system_prompt on a fresh database"). The prompt TEXT is deliberately not
# asserted (024/plan.md -> Test plan -> "Not tested"): only its non-blankness,
# which is what D4 changed this clause into. The row count and the exact key set
# above are untouched.
async def test_seed_creates_exactly_the_fixed_five__DoD1(db: DbConfig):
    await assistant_modes.seed_default_modes()

    rows = await assistant_modes.list_all()

    # Exactly five rows, no more, no fewer.
    assert len(rows) == 5
    # The set of keys equals exactly the fixed five.
    assert {row.key for row in rows} == FIXED_FIVE_KEYS
    # Each seeded row is created with a real, non-blank system_prompt.
    for row in rows:
        assert row.system_prompt is not None
        assert row.system_prompt.strip() != ""


# ---------------------------------------------------------------------------
# DoD-2 — seed is idempotent (second call adds no duplicates, no error)
# ---------------------------------------------------------------------------


# DoD-2: calling seed_default_modes() a second time leaves exactly five rows
# (no duplicates) and raises no error.
async def test_seed_is_idempotent__DoD2(db: DbConfig):
    await assistant_modes.seed_default_modes()
    # A second call must not raise and must not add duplicate rows.
    await assistant_modes.seed_default_modes()

    rows = await assistant_modes.list_all()

    assert len(rows) == 5
    assert {row.key for row in rows} == FIXED_FIVE_KEYS


# ---------------------------------------------------------------------------
# DoD-3 — wiring: create_database reaches the seed through the setup path
# ---------------------------------------------------------------------------


# DoD-3: after create_database completes on a fresh instance, the five
# AssistantMode rows exist — the seed is reachable through the setup path.
# A password >= the minimum length with a matching confirmation is used so
# create_database does not raise a SetupError.
async def test_create_database_seeds_the_fixed_five__DoD3(db: DbConfig):
    # Precondition: the instance is unconfigured (autouse reset -> False).
    assert is_db_ready() is False

    await setup.create_database("root", "password123", "password123")

    rows = await assistant_modes.list_all()

    # The five modes are present through the setup path.
    assert len(rows) == 5
    assert {row.key for row in rows} == FIXED_FIVE_KEYS

    # Sanity check: create_database also flips the instance to configured.
    assert is_db_ready() is True
