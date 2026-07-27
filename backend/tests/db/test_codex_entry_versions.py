"""Tests for db/codex_entry_versions' generation lookup + ordering (013, step 001).

Bound to the frozen skeleton signatures (status.md -> Skeleton -> Step 001), in
`app.db.codex_entry_versions` (existing `create` / `get_by_id` unchanged):
    async def next_generation(entry_id: int) -> int
    async def list_by_entry(entry_id: int) -> list[CodexEntryVersion]
        -- signature unchanged; ascending-`generation` ordering is new behaviour

Expected values come from the step spec (001.codex-db-authz.md -> Interface
intent + Definition of done, plus 001.context.md), never from implementation
internals:
    - next_generation returns 1 when the entry has no version rows (DoD-7);
    - otherwise it returns one more than the highest existing generation for
      that entry, including when the version rows were created out of order
      (DoD-8);
    - list_by_entry returns rows in ascending `generation` order, and only for
      the given entry (DoD-9).

Async tests use asyncio_mode = "auto"; the `db` fixture (conftest) supplies an
initialized throwaway temp-SQLite engine. SQLite does not enforce FKs by
default, so version rows need no parent entry/user rows. No HTTP, no network.
"""

from app.db import codex_entry_versions
from app.db.engine import DbConfig
from app.models.codex_entry import CodexKind
from app.models.codex_entry_version import CodexEntryVersion


def _version(
    entry_id: int,
    generation: int,
    *,
    name: str | None = "A name",
    body: str = "a body",
    kind: CodexKind = CodexKind.character,
    author_id: int = 1,
) -> CodexEntryVersion:
    """A CodexEntryVersion with the model's required non-null fields set."""
    return CodexEntryVersion(
        entry_id=entry_id,
        name=name,
        body=body,
        kind=kind,
        author_id=author_id,
        generation=generation,
    )


# ---------------------------------------------------------------------------
# DoD-7 — next_generation on an entry with no version rows
# ---------------------------------------------------------------------------


# DoD-7 (UC-070 postcondition): next_generation returns 1 for an entry that has
# no version rows -- generations are 1-based, so the first version to be written
# is generation 1.
async def test_next_generation_is_one_without_versions__DoD7_UC070(db: DbConfig):
    assert await codex_entry_versions.next_generation(1000) == 1


# DoD-7 (UC-070 postcondition): the "no rows" answer is per entry -- an entry
# with no versions still gets 1 even while another entry already has versions.
async def test_next_generation_is_one_for_a_fresh_sibling_entry__DoD7_UC070(
    db: DbConfig,
):
    await codex_entry_versions.create(_version(1001, 1))
    await codex_entry_versions.create(_version(1001, 2))

    assert await codex_entry_versions.next_generation(1002) == 1


# ---------------------------------------------------------------------------
# DoD-8 — next_generation is highest + 1, insertion order irrelevant
# ---------------------------------------------------------------------------


# DoD-8 (UC-070 postcondition): next_generation returns one more than the
# highest existing generation for the entry.
async def test_next_generation_is_highest_plus_one__DoD8_UC070(db: DbConfig):
    entry = 1100
    await codex_entry_versions.create(_version(entry, 1))
    await codex_entry_versions.create(_version(entry, 2))

    assert await codex_entry_versions.next_generation(entry) == 3


# DoD-8 (UC-070 postcondition): the answer is driven by the highest generation,
# not by insertion order or row count -- version rows created out of order
# (3, then 1, then 2) still yield 4.
async def test_next_generation_ignores_insertion_order__DoD8_UC070(db: DbConfig):
    entry = 1101
    await codex_entry_versions.create(_version(entry, 3))
    await codex_entry_versions.create(_version(entry, 1))
    await codex_entry_versions.create(_version(entry, 2))

    assert await codex_entry_versions.next_generation(entry) == 4


# DoD-8 (UC-070 postcondition): a gap in the generation sequence does not lower
# the answer, and another entry's higher generation does not raise it.
async def test_next_generation_is_scoped_to_the_entry__DoD8_UC070(db: DbConfig):
    entry = 1102
    other_entry = 1103
    await codex_entry_versions.create(_version(entry, 1))
    await codex_entry_versions.create(_version(entry, 5))
    await codex_entry_versions.create(_version(other_entry, 99))

    assert await codex_entry_versions.next_generation(entry) == 6
    assert await codex_entry_versions.next_generation(other_entry) == 100


# ---------------------------------------------------------------------------
# DoD-9 — list_by_entry is ascending by generation and entry-scoped
# ---------------------------------------------------------------------------


# DoD-9 (UC-073 groundwork): list_by_entry returns the entry's versions in
# ascending `generation` order, whatever order they were inserted in, and only
# for that entry.
async def test_list_by_entry_is_ascending_by_generation__DoD9_UC073(db: DbConfig):
    entry = 1200
    other_entry = 1201
    # Inserted out of generation order on purpose.
    await codex_entry_versions.create(_version(entry, 3, body="third"))
    await codex_entry_versions.create(_version(entry, 1, body="first"))
    await codex_entry_versions.create(_version(entry, 2, body="second"))
    await codex_entry_versions.create(_version(other_entry, 1, body="elsewhere"))

    listed = await codex_entry_versions.list_by_entry(entry)

    assert [v.generation for v in listed] == [1, 2, 3]
    assert [v.body for v in listed] == ["first", "second", "third"]
    # Only this entry's rows.
    assert {v.entry_id for v in listed} == {entry}


# DoD-9 (UC-073 groundwork): a non-contiguous generation sequence is still
# returned in ascending order, and an entry with no versions returns an empty
# list.
async def test_list_by_entry_ordering_with_gaps_and_empty__DoD9_UC073(db: DbConfig):
    entry = 1202
    await codex_entry_versions.create(_version(entry, 7, body="seven"))
    await codex_entry_versions.create(_version(entry, 2, body="two"))
    await codex_entry_versions.create(_version(entry, 11, body="eleven"))

    listed = await codex_entry_versions.list_by_entry(entry)
    assert [v.generation for v in listed] == [2, 7, 11]

    assert await codex_entry_versions.list_by_entry(1203) == []
