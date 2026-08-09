"""Tests for the mode seed on the DB-import bootstrap path (feature 012, step 001).

Bound to the frozen signatures (status.md -> Skeleton -> Step 001):
    async def import_database(archive_bytes: bytes) -> None   in app.services.setup
        (signature UNCHANGED by this step — the change is behavioral only: the
         existing idempotent seed is called on the import bootstrap path)
    async def seed_default_modes() -> None                    in app.db.assistant_modes
    DEFAULT_MODE_KEYS: tuple[str, ...]                        in app.db.assistant_modes
    async def list_all() -> list[AssistantMode]               in app.db.assistant_modes
    async def create(row: AssistantMode) -> AssistantMode      in app.db.assistant_modes
    async def get_by_id(key: str) -> AssistantMode | None      in app.db.assistant_modes
    async def export_all() -> bytes                           in app.services.db_import_export
    def is_db_ready() -> bool                                 in app.db.engine

Expected values come from the step spec (001.db-layer-completion.md DoD +
Interface intent + 001.context.md + context.md), never from implementation
internals:
    - The fixed five mode keys are exactly `edit-character`, `edit-location`,
      `edit-fact`, `write-chapter`, `close-chapter` (001.context.md ->
      "DEFAULT_MODE_KEYS is the tuple ...");
    - DoD-8: after services/setup.py:import_database completes on a fresh
      instance, all five DEFAULT_MODE_KEYS rows exist — an instance bootstrapped
      by DB import is no longer missing its modes (UC-095 precondition);
    - DoD-9: the seed on the import path is idempotent and non-destructive —
      importing an archive whose `assistant_modes` rows already carry
      system_prompt values leaves those values intact, creates no duplicate row,
      and leaves exactly five modes (UC-095 precondition; assistant-config.md ->
      "Seeding"). The clause requires the archive's mode rows to CARRY PROMPTS,
      not to carry all five, so the archive here is a prompt-bearing PARTIAL set:
      "exactly five afterwards" is then reachable only when the seed runs on the
      import path, while the archived rows still test non-destructiveness. Rows
      the seed creates carried `system_prompt = None` (001.context.md ->
      "seed_default_modes and the gap being closed") until feature 024's decision
      D4, which makes the seed write a real non-blank default prompt for a key
      with no existing row (024/plan.md -> DoD-4 / DoD-12); DoD-9's own clause is
      otherwise unchanged.
    (DoD-1..DoD-7 live in tests/db/test_assistant_config_db.py; DoD-10 is
    [manual/live] — no automated test.)

Scope note (001.context.md): only the *bootstrap* import path
(`services/setup.py:import_database`) is covered here. The admin import surface
(`services/db_admin.py`) is deliberately out of scope, and the existing
`tests/test_data_domain_mode_seed.py` coverage of `seed_default_modes` /
`create_database` is not duplicated.

Async tests use asyncio_mode = "auto"; the `db` fixture (conftest) supplies an
initialized throwaway temp-SQLite engine (init_engine + init_db), so the schema
is present and the instance starts with zero AssistantMode rows. The autouse
`_reset_db_ready` fixture resets the process-global readiness flag to False
before each test, so each test starts unconfigured — the first-run bootstrap
state `import_database` requires. Archives are produced with the real
`export_all()`; no network, no live server.
"""

from datetime import datetime

from app.db import assistant_modes
from app.db.engine import DbConfig, is_db_ready
from app.models.assistant_mode import AssistantMode
from app.services import setup
from app.services.db_import_export import export_all

# The fixed five mode keys — the system set, from the spec
# (001.context.md -> "DEFAULT_MODE_KEYS is the tuple ...").
FIXED_FIVE_KEYS = {
    "edit-character",
    "edit-location",
    "edit-fact",
    "write-chapter",
    "close-chapter",
}


# ---------------------------------------------------------------------------
# DoD-8 — import_database seeds the five modes on a fresh instance
# ---------------------------------------------------------------------------


# DoD-8: on a fresh, unconfigured instance whose archive carries NO
# assistant_modes rows, import_database must still leave all five
# DEFAULT_MODE_KEYS rows behind — the first-run gap this step closes.
async def test_import_database_seeds_the_fixed_five__DoD8(db: DbConfig):
    # A fresh instance: no modes yet (the seed has not run on this DB).
    assert len(await assistant_modes.list_all()) == 0
    # ...and an archive taken from it therefore carries no assistant_modes rows.
    archive_bytes = await export_all()

    # Precondition: unconfigured (autouse reset -> False) — the bootstrap path.
    assert is_db_ready() is False

    await setup.import_database(archive_bytes)

    rows = await assistant_modes.list_all()

    # The five modes exist after the import bootstrap.
    assert len(rows) == 5
    assert {row.key for row in rows} == FIXED_FIVE_KEYS
    # Every key is individually reachable (UC-095's "fixed system set of five").
    for key in FIXED_FIVE_KEYS:
        assert await assistant_modes.get_by_id(key) is not None

    # The seeded constant is the fixed five the spec names.
    assert set(assistant_modes.DEFAULT_MODE_KEYS) == FIXED_FIVE_KEYS


# ---------------------------------------------------------------------------
# DoD-9 — the seed on the import path is idempotent and non-destructive
# ---------------------------------------------------------------------------


# The mode rows the archive carries: PROMPT-BEARING but a PARTIAL set. The clause
# requires the archive's mode rows to carry system_prompt values; it does not
# require the archive to carry all five. Two of the fixed five are deliberately
# absent, so "exactly five afterwards" is only reachable when the seed runs on
# the import bootstrap path, while the three present rows keep biting as the
# non-destructiveness / no-duplicate assertions.
ARCHIVED_PROMPTS = {
    "edit-character": "Stored prompt for edit-character.",
    "edit-location": "Stored prompt for edit-location.",
    "edit-fact": "Stored prompt for edit-fact.",
}
ABSENT_FROM_ARCHIVE = FIXED_FIVE_KEYS - set(ARCHIVED_PROMPTS)


# DoD-9: importing an archive whose assistant_modes rows already carry
# system_prompt values must converge, not collide — the stored prompts survive
# untouched, no duplicate row is created for a key the archive already had, and
# there are exactly five modes afterwards (the keys the archive lacked are the
# seed's, created with a null system_prompt per 001.context.md ->
# "seed_default_modes and the gap being closed").
async def test_import_database_seed_is_non_destructive__DoD9(db: DbConfig):
    created_at = datetime(2026, 7, 26, 6, 0, 0)

    for key, prompt in ARCHIVED_PROMPTS.items():
        await assistant_modes.create(
            AssistantMode(
                key=key,
                system_prompt=prompt,
                created_at=created_at,
                modified_at=created_at,
            )
        )

    # The archive carries three prompt-bearing modes; two of the fixed five are
    # absent from it.
    archive_bytes = await export_all()
    assert len(ABSENT_FROM_ARCHIVE) == 2
    for key in ABSENT_FROM_ARCHIVE:
        assert await assistant_modes.get_by_id(key) is None

    assert is_db_ready() is False

    await setup.import_database(archive_bytes)

    rows = await assistant_modes.list_all()

    # Exactly five modes afterwards: the seed supplied the keys the archive
    # lacked, and created no duplicate for the keys it already had.
    assert len(rows) == 5
    assert {row.key for row in rows} == FIXED_FIVE_KEYS

    # The archive's stored system_prompt values are intact — the seed did not
    # blank or re-create them.
    by_key = {row.key: row for row in rows}
    for key, prompt in ARCHIVED_PROMPTS.items():
        assert by_key[key].system_prompt == prompt
        # ...and readable one-by-one, so no shadow row displaced them.
        fetched = await assistant_modes.get_by_id(key)
        assert fetched is not None
        assert fetched.system_prompt == prompt

    # The keys the archive lacked exist as freshly seeded rows, carrying the
    # seed's own default prompt.
    #
    # Amended by feature 024 (chat-agent-loop), decision D4: seed_default_modes()
    # now writes `DEFAULT_MODE_SYSTEM_PROMPTS[key]` for a key with no existing row
    # in place of `system_prompt=None` (024/plan.md -> DoD-4 / DoD-12), which is
    # exactly the "(null prompt)" this loop pinned. DoD-9's own property — the
    # archive's stored prompts survive untouched, no duplicate row, exactly five
    # modes afterwards — is asserted above and is unchanged.
    for key in ABSENT_FROM_ARCHIVE:
        seeded = await assistant_modes.get_by_id(key)
        assert seeded is not None
        assert seeded.system_prompt is not None
        assert seeded.system_prompt.strip() != ""
        # Never an archived row's text: a seeded row must not displace an
        # imported one.
        assert seeded.system_prompt not in set(ARCHIVED_PROMPTS.values())
