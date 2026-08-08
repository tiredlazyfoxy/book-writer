"""The admin DB-import path must leave the five assistant modes seeded.

Feedback round 1, item **F2** — "The admin DB-import path leaves modes unseeded,
reproducing the same dead end". Reproduces: `services/db_admin.import_database`
(the admin surface, a *different* function from the first-run
`services/setup.import_database`) validates and imports but never seeds, so an
instance restored from an archive without mode rows lands on the same empty
`/admin/assistant-modes` page.

Bound to the frozen signature (feedback.md F2 -> Constraints, "Signature —
**frozen**"; status.md -> `## Skeleton`):

    app.services.db_admin:
        async def import_database(archive_bytes: bytes) -> None
        class DbAdminError(Exception)      # .case: DbAdminErrorCase
        DbAdminErrorCase.invalid_archive
    app.db.assistant_modes:
        async def list_all() / get_by_id(key) / create(row)
    app.services.db_import_export:
        async def export_all() -> bytes

THE AIR GAP — no source is read. Every expected value comes from feedback.md ->
F2's `Expected` and `Constraints`:

  - importing an archive whose `assistant_modes` rows are ABSENT leaves the
    instance with all five keys present;
  - importing an archive that ALREADY carries mode rows leaves those rows exactly
    as archived: prompts preserved, no duplicates, no extra rows beyond the fixed
    five;
  - a REFUSED import must not seed — `validate_archive`'s refusal contract for a
    corrupt archive is unchanged (`invalid_archive`), and nothing is written.

The five keys are the product's fixed system set: edit-character, edit-location,
edit-fact, write-chapter, close-chapter.

Archives are produced with the real `export_all()` — the idiom
`tests/services/test_setup_mode_seed.py` uses — so no archive format is invented
here. Async tests use asyncio_mode = "auto"; the `db` fixture supplies an
initialized throwaway temp-SQLite engine.
"""

from datetime import datetime

import pytest

from app.db import assistant_modes
from app.db.engine import DbConfig
from app.models.assistant_mode import AssistantMode
from app.services import db_admin
from app.services.db_import_export import export_all

FIXED_FIVE_KEYS = {
    "edit-character",
    "edit-location",
    "edit-fact",
    "write-chapter",
    "close-chapter",
}

# Prompt-bearing rows the archive carries. A PARTIAL set, so "exactly five
# afterwards" is only reachable when the admin import path seeds, while the three
# archived rows keep biting as the non-destructiveness assertions.
ARCHIVED_PROMPTS = {
    "edit-character": "Archived prompt for edit-character.",
    "edit-location": "Archived prompt for edit-location.",
    "edit-fact": "Archived prompt for edit-fact.",
}
ABSENT_FROM_ARCHIVE = FIXED_FIVE_KEYS - set(ARCHIVED_PROMPTS)


# F2 — reproduces the dead end: an archive with no `assistant_modes` rows must
# still leave all five keys present after the ADMIN import completes.
async def test_admin_import_seeds_the_fixed_five__F2(db: DbConfig):
    assert len(await assistant_modes.list_all()) == 0
    archive_bytes = await export_all()

    await db_admin.import_database(archive_bytes)

    rows = await assistant_modes.list_all()
    assert {row.key for row in rows} == FIXED_FIVE_KEYS
    assert len(rows) == 5
    for key in FIXED_FIVE_KEYS:
        assert await assistant_modes.get_by_id(key) is not None


# F2 — an archive that already carries mode rows keeps them exactly as archived:
# the stored prompts survive, no duplicate row appears, and there are exactly the
# fixed five afterwards (the archive's missing keys are the seed's, promptless).
async def test_admin_import_preserves_archived_mode_rows__F2(db: DbConfig):
    created_at = datetime(2026, 8, 8, 6, 0, 0)
    for key, prompt in ARCHIVED_PROMPTS.items():
        await assistant_modes.create(
            AssistantMode(
                key=key,
                system_prompt=prompt,
                created_at=created_at,
                modified_at=created_at,
            )
        )
    archive_bytes = await export_all()
    assert len(ABSENT_FROM_ARCHIVE) == 2

    await db_admin.import_database(archive_bytes)

    rows = await assistant_modes.list_all()
    assert {row.key for row in rows} == FIXED_FIVE_KEYS
    assert len(rows) == 5  # no duplicates, no extra rows beyond the fixed five

    by_key = {row.key: row for row in rows}
    for key, prompt in ARCHIVED_PROMPTS.items():
        assert by_key[key].system_prompt == prompt
        fetched = await assistant_modes.get_by_id(key)
        assert fetched is not None
        assert fetched.system_prompt == prompt

    for key in ABSENT_FROM_ARCHIVE:
        seeded = await assistant_modes.get_by_id(key)
        assert seeded is not None
        assert seeded.system_prompt is None


# F2 (Constraints) — a REFUSED import must not seed: the corrupt-archive refusal
# contract is unchanged and no mode row exists afterwards.
async def test_refused_admin_import_does_not_seed__F2(db: DbConfig):
    assert len(await assistant_modes.list_all()) == 0

    with pytest.raises(db_admin.DbAdminError) as excinfo:
        await db_admin.import_database(b"not a zip archive")

    assert excinfo.value.case is db_admin.DbAdminErrorCase.invalid_archive
    assert await assistant_modes.list_all() == []
