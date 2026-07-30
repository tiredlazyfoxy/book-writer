"""Tests for the codex tables: CodexEntry + CodexEntryVersion (feature 008, step 008).

Bound to the frozen skeleton signatures (status.md -> Skeleton -> Step 008):
    one enum in app.models.codex_entry:
        class CodexKind(str, enum.Enum) {character, location, fact}
    class CodexEntry(SQLModel, table=True) __tablename__="codex_entries";
        id: int (snowflake PK), book_id: int (FK books.id),
        kind: CodexKind (required), name: str | None (nullable, null for fact),
        body: str, archived: bool = False,
        author_id: int (NON-null FK users.id, original creator),
        modified_by: int | None (nullable FK users.id, last editor),
        created_at: datetime | None, modified_at: datetime | None
                                                        in app.models.codex_entry
    class CodexEntryVersion(SQLModel, table=True) __tablename__="codex_entry_versions";
        reuses CodexKind from app.models.codex_entry (NO second enum);
        id: int (snowflake PK), entry_id: int (FK codex_entries.id),
        name: str | None (nullable), body: str, kind: CodexKind (required),
        author_id: int (NON-null FK users.id),
        generation: int (REQUIRED non-null, no default, 1-based),
        created_at: datetime | None (single timestamp)
                                                in app.models.codex_entry_version
    async def create / get_by_id(entry_id) / list_by_book(book_id) -> list[CodexEntry]
                                                              in app.db.codex_entries
    async def create / get_by_id(version_id) / list_by_entry(entry_id)
        -> list[CodexEntryVersion]                    in app.db.codex_entry_versions
    def _codex_entry_to_dict / _dict_to_codex_entry           in db_import_export
    def _codex_entry_version_to_dict / _dict_to_codex_entry_version
                                                              in db_import_export
    TABLE_REGISTRY: ("codex_entries", ...) then ("codex_entry_versions", ...)
        slotted BETWEEN chapter_note_changesets and flags        in db_import_export
    VECTOR_SOURCE_REGISTRY: list[VectorSource]                 in app.db.vector
        (013.codex step 005 widened the tuple into a typed `VectorSource`
         carrying source_kind / model_class / row_selector / chunker)
    build_consistency_report() -> report with .tables entries each carrying
        .name / .status                                       in app.services.db_admin

Expected values come from the step spec (008.codex.md DoD + 008.context.md +
context.md), never from implementation internals:
    - CodexEntry codec emits `id`/`book_id`/`author_id` as strings parsed back to
      the same ints; `kind` emits its `.value` and parses back to the member for
      ALL THREE kinds (character, location, fact); the nullable `name` round-trips
      in BOTH the set shape (string) and the null-for-fact shape (None); the
      `archived` bool round-trips (True and False); the nullable FK `modified_by`
      emits as a STRING when set and None when null; isoformat timestamps (set and
      None) survive (DoD-1);
    - CodexEntryVersion codec emits `id`/`entry_id`/`author_id` as strings parsed
      back to ints; nullable `name` in both shapes; `body` preserved; `kind` enum
      round-trips; `generation` plain int (1 and 3) round-trips; isoformat
      `created_at` preserved (DoD-2);
    - db round-trip: create -> get_by_id returns an equal row for both tables;
      list_by_book returns exactly a book's entries; list_by_entry returns exactly
      an entry's versions (two ids inserted per filter) (DoD-3);
    - TABLE_REGISTRY slots `codex_entries` then `codex_entry_versions` BETWEEN
      `chapter_note_changesets` and `flags`; label sequence equals the canonical
      order restricted to present tables (DoD-4);
    - SUPERSEDED by 013.codex step 005 DoD-15: `codex_entries` IS a registered
      vector source — VECTOR_SOURCE_REGISTRY holds exactly one typed
      `VectorSource` (fields read BY NAME), discriminated `codex_entry` and
      bound to CodexEntry (was feature-008 DoD-5's "codex-free" deferral guard);
    - after init_db(), both tables exist in SQLModel.metadata and the FEAT-005
      consistency report is clean (DoD-6).

Async tests use asyncio_mode = "auto"; the `db` fixture (conftest) supplies an
initialized throwaway temp-SQLite engine with the registered tables created.
Pure-codec tests (DoD-1, DoD-2), the registry test (DoD-4) and the vector-guard
test (DoD-5) need no DB. SQLite does NOT enforce FKs by default, so rows need no
parent book/entry/user row.
"""

from datetime import datetime

import pytest
from sqlmodel import SQLModel

from app.db import codex_entries, codex_entry_versions
from app.db.engine import DbConfig
from app.db.vector import VECTOR_SOURCE_REGISTRY
from app.models.codex_entry import CodexEntry, CodexKind
from app.models.codex_entry_version import CodexEntryVersion
from app.services import db_admin
from app.services.db_import_export import (
    TABLE_REGISTRY,
    _codex_entry_to_dict,
    _codex_entry_version_to_dict,
    _dict_to_codex_entry,
    _dict_to_codex_entry_version,
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
    "book_author_prompts",
    "chapter_author_prompts",
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
# DoD-1 — CodexEntry codec round-trip
# ---------------------------------------------------------------------------


# DoD-1 (named + set shape): a character entry with `name` set, `archived=True`,
# and the nullable FK `modified_by` set to an int round-trips. `id`/`book_id`/
# `author_id` emit as strings and parse back to the same ints; `kind` emits its
# `.value` and parses back to the member; `name` (set) passes through; `archived`
# True survives; `modified_by` (set) emits as a STRING and parses back to the int;
# the isoformat timestamps survive.
def test_codex_entry_codec_round_trips_named_set_shape__DoD1():
    created_at = datetime(2026, 7, 25, 9, 0, 0)
    modified_at = datetime(2026, 7, 25, 9, 30, 0)
    entry = CodexEntry(
        id=111222333,
        book_id=444555666,
        kind=CodexKind.character,
        name="Alice",
        body="A brave protagonist.",
        archived=True,
        author_id=777888999,
        modified_by=101112131,
        created_at=created_at,
        modified_at=modified_at,
    )

    data = _codex_entry_to_dict(entry)

    # `id` / `book_id` / `author_id` emitted as strings.
    assert data["id"] == "111222333"
    assert isinstance(data["id"], str)
    assert data["book_id"] == "444555666"
    assert isinstance(data["book_id"], str)
    assert data["author_id"] == "777888999"
    assert isinstance(data["author_id"], str)
    # `kind` emitted via its `.value` string.
    assert data["kind"] == "character"
    # Nullable `name` (set) passes through.
    assert data["name"] == "Alice"
    assert data["body"] == "A brave protagonist."
    # `archived` bool (True) preserved.
    assert data["archived"] is True
    # Nullable FK `modified_by` (set) emitted as a STRING (id-as-string).
    assert data["modified_by"] == "101112131"
    assert isinstance(data["modified_by"], str)
    # Timestamps via isoformat strings.
    assert data["created_at"] == created_at.isoformat()
    assert data["modified_at"] == modified_at.isoformat()

    restored = _dict_to_codex_entry(data)

    # `id` / `book_id` / `author_id` parse back to the same ints.
    assert restored.id == 111222333
    assert isinstance(restored.id, int)
    assert restored.book_id == 444555666
    assert isinstance(restored.book_id, int)
    assert restored.author_id == 777888999
    assert isinstance(restored.author_id, int)
    # `kind` parses back to the enum member.
    assert restored.kind is CodexKind.character
    # Nullable `name` (set) preserved.
    assert restored.name == "Alice"
    assert restored.body == "A brave protagonist."
    # `archived` bool (True) preserved.
    assert restored.archived is True
    # Nullable FK `modified_by` (set) parses back to the int.
    assert restored.modified_by == 101112131
    assert isinstance(restored.modified_by, int)
    assert restored.created_at == created_at
    assert restored.modified_at == modified_at


# DoD-1 (fact + null shape): a fact entry with `name=None` (null-for-fact),
# `archived=False`, and the nullable FK `modified_by=None` round-trips. `name`
# emits as None and restores to None; `archived` False survives; `modified_by`
# emits as None and restores to None; None timestamps stay None.
def test_codex_entry_codec_round_trips_fact_null_shape__DoD1():
    entry = CodexEntry(
        id=222333444,
        book_id=555666777,
        kind=CodexKind.fact,
        name=None,
        body="The war ended in the third age.",
        archived=False,
        author_id=888999000,
        modified_by=None,
        created_at=None,
        modified_at=None,
    )

    data = _codex_entry_to_dict(entry)

    # `kind` for a fact.
    assert data["kind"] == "fact"
    # Nullable `name` (None, the null-for-fact case) emitted as None.
    assert data["name"] is None
    assert data["body"] == "The war ended in the third age."
    # `archived` bool (False) preserved.
    assert data["archived"] is False
    # Required `author_id` still emitted as a string.
    assert data["author_id"] == "888999000"
    assert isinstance(data["author_id"], str)
    # Nullable FK `modified_by` (None) emitted as None.
    assert data["modified_by"] is None
    # None timestamps emitted as None.
    assert data["created_at"] is None
    assert data["modified_at"] is None

    restored = _dict_to_codex_entry(data)

    assert restored.id == 222333444
    assert restored.book_id == 555666777
    assert restored.kind is CodexKind.fact
    # Nullable `name` restores to None.
    assert restored.name is None
    assert restored.body == "The war ended in the third age."
    # `archived` bool (False) preserved.
    assert restored.archived is False
    assert restored.author_id == 888999000
    assert isinstance(restored.author_id, int)
    # Nullable FK `modified_by` restores to None.
    assert restored.modified_by is None
    assert restored.created_at is None
    assert restored.modified_at is None


# DoD-1: EVERY one of the three `kind` values (character, location, fact) emits
# its `.value` string and parses back to the exact enum member.
@pytest.mark.parametrize(
    "kind",
    [
        CodexKind.character,
        CodexKind.location,
        CodexKind.fact,
    ],
)
def test_codex_entry_kind_round_trips_every_value__DoD1(kind: CodexKind):
    entry = CodexEntry(
        id=333444555,
        book_id=666777888,
        kind=kind,
        name="A name",
        body="some body",
        author_id=1,
    )

    data = _codex_entry_to_dict(entry)
    # Emitted as the enum's `.value` string.
    assert data["kind"] == kind.value

    restored = _dict_to_codex_entry(data)
    # Parsed back to the same enum member.
    assert restored.kind is kind


# ---------------------------------------------------------------------------
# DoD-2 — CodexEntryVersion codec round-trip
# ---------------------------------------------------------------------------


# DoD-2 (named + set shape): a version with `name` set, `generation=3`,
# `kind=location`, and an isoformat `created_at` round-trips. `id`/`entry_id`/
# `author_id` emit as strings and parse back to the same ints; `name` (set) passes
# through; `body` survives; `kind` emits its `.value` and parses back to the
# member; `generation` is a plain int; the isoformat `created_at` survives.
def test_codex_entry_version_codec_round_trips_named_set_shape__DoD2():
    created_at = datetime(2026, 7, 25, 11, 0, 0)
    version = CodexEntryVersion(
        id=111222333,
        entry_id=444555666,
        name="Rivendell",
        body="A hidden valley refuge.",
        kind=CodexKind.location,
        author_id=777888999,
        generation=3,
        created_at=created_at,
    )

    data = _codex_entry_version_to_dict(version)

    # `id` / `entry_id` / `author_id` emitted as strings.
    assert data["id"] == "111222333"
    assert isinstance(data["id"], str)
    assert data["entry_id"] == "444555666"
    assert isinstance(data["entry_id"], str)
    assert data["author_id"] == "777888999"
    assert isinstance(data["author_id"], str)
    # Nullable `name` (set) passes through.
    assert data["name"] == "Rivendell"
    assert data["body"] == "A hidden valley refuge."
    # `kind` emitted via its `.value` string.
    assert data["kind"] == "location"
    # `generation` a plain int passes through unchanged.
    assert data["generation"] == 3
    assert isinstance(data["generation"], int)
    # created_at via isoformat string.
    assert data["created_at"] == created_at.isoformat()

    restored = _dict_to_codex_entry_version(data)

    # `id` / `entry_id` / `author_id` parse back to the same ints.
    assert restored.id == 111222333
    assert isinstance(restored.id, int)
    assert restored.entry_id == 444555666
    assert isinstance(restored.entry_id, int)
    assert restored.author_id == 777888999
    assert isinstance(restored.author_id, int)
    # Nullable `name` (set) preserved.
    assert restored.name == "Rivendell"
    assert restored.body == "A hidden valley refuge."
    # `kind` parses back to the enum member.
    assert restored.kind is CodexKind.location
    # `generation` a plain int preserved.
    assert restored.generation == 3
    assert isinstance(restored.generation, int)
    assert restored.created_at == created_at


# DoD-2 (fact + null shape): a version with `name=None`, `generation=1`,
# `kind=fact`, and `created_at=None` round-trips. The nullable `name` emits as
# None and restores to None; `generation` 1 survives; the None timestamp stays
# None.
def test_codex_entry_version_codec_round_trips_null_shape__DoD2():
    version = CodexEntryVersion(
        id=222333444,
        entry_id=555666777,
        name=None,
        body="A recorded fact as it stood.",
        kind=CodexKind.fact,
        author_id=888999000,
        generation=1,
        created_at=None,
    )

    data = _codex_entry_version_to_dict(version)

    # Nullable `name` (None) emitted as None.
    assert data["name"] is None
    assert data["body"] == "A recorded fact as it stood."
    assert data["kind"] == "fact"
    # `generation` int passes through.
    assert data["generation"] == 1
    # None timestamp emitted as None.
    assert data["created_at"] is None

    restored = _dict_to_codex_entry_version(data)

    assert restored.id == 222333444
    assert restored.entry_id == 555666777
    # Nullable `name` restores to None.
    assert restored.name is None
    assert restored.body == "A recorded fact as it stood."
    assert restored.kind is CodexKind.fact
    assert restored.generation == 1
    assert restored.created_at is None


# DoD-2: EVERY one of the three `kind` values (character, location, fact) emits
# its `.value` string and parses back to the exact enum member on a version.
@pytest.mark.parametrize(
    "kind",
    [
        CodexKind.character,
        CodexKind.location,
        CodexKind.fact,
    ],
)
def test_codex_entry_version_kind_round_trips_every_value__DoD2(kind: CodexKind):
    version = CodexEntryVersion(
        id=333444555,
        entry_id=666777888,
        name="a name",
        body="a body",
        kind=kind,
        author_id=1,
        generation=2,
    )

    data = _codex_entry_version_to_dict(version)
    assert data["kind"] == kind.value

    restored = _dict_to_codex_entry_version(data)
    assert restored.kind is kind


# ---------------------------------------------------------------------------
# DoD-3 — DB round-trip (create -> get_by_id; list_by_book / list_by_entry filter)
# ---------------------------------------------------------------------------


# DoD-3: codex_entries.create(row) then get_by_id(row.id) returns an equal row.
# Required non-null fields (book_id, kind, body, author_id) are provided;
# `archived` defaults to False; the snowflake PK is populated on create.
async def test_codex_entries_db_round_trip__DoD3(db: DbConfig):
    row = CodexEntry(
        book_id=42,
        kind=CodexKind.character,
        name="Persisted Alice",
        body="Persisted body text.",
        author_id=7,
    )

    created = await codex_entries.create(row)
    # Snowflake PK populated on the created row.
    assert created.id is not None

    fetched = await codex_entries.get_by_id(created.id)
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.book_id == 42
    assert fetched.kind is CodexKind.character
    assert fetched.name == "Persisted Alice"
    assert fetched.body == "Persisted body text."
    assert fetched.author_id == 7
    # `archived` defaults to False.
    assert fetched.archived is False


# DoD-3: codex_entries.list_by_book(book_id) returns exactly that book's entries.
# Entries are inserted for two different book_ids and the filter selects only the
# matching book's rows.
async def test_codex_entries_list_by_book_filters__DoD3(db: DbConfig):
    e_a = CodexEntry(
        book_id=10, kind=CodexKind.character, name="A", body="a", author_id=1
    )
    e_b = CodexEntry(
        book_id=10, kind=CodexKind.location, name="B", body="b", author_id=1
    )
    e_other = CodexEntry(
        book_id=20, kind=CodexKind.fact, name=None, body="c", author_id=1
    )

    await codex_entries.create(e_a)
    await codex_entries.create(e_b)
    await codex_entries.create(e_other)

    listed = await codex_entries.list_by_book(10)

    # Exactly book 10's entries (both, and only those).
    assert {e.book_id for e in listed} == {10}
    assert {e.body for e in listed} == {"a", "b"}
    assert len(listed) == 2


# DoD-3: codex_entry_versions.create(row) then get_by_id(row.id) returns an equal
# row. Required non-null fields (entry_id, body, kind, author_id, generation) are
# provided; the snowflake PK is populated on create.
async def test_codex_entry_versions_db_round_trip__DoD3(db: DbConfig):
    row = CodexEntryVersion(
        entry_id=55,
        name="Version name",
        body="Version body as it stood.",
        kind=CodexKind.location,
        author_id=8,
        generation=1,
    )

    created = await codex_entry_versions.create(row)
    assert created.id is not None

    fetched = await codex_entry_versions.get_by_id(created.id)
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.entry_id == 55
    assert fetched.name == "Version name"
    assert fetched.body == "Version body as it stood."
    assert fetched.kind is CodexKind.location
    assert fetched.author_id == 8
    assert fetched.generation == 1


# DoD-3: codex_entry_versions.list_by_entry(entry_id) returns exactly that entry's
# versions. Versions are inserted for two different entry_ids and the filter
# selects only the matching entry's rows.
async def test_codex_entry_versions_list_by_entry_filters__DoD3(db: DbConfig):
    v_a = CodexEntryVersion(
        entry_id=10, name="A", body="a", kind=CodexKind.character, author_id=1, generation=1
    )
    v_b = CodexEntryVersion(
        entry_id=10, name="A", body="a2", kind=CodexKind.character, author_id=1, generation=2
    )
    v_other = CodexEntryVersion(
        entry_id=20, name="B", body="b", kind=CodexKind.location, author_id=1, generation=1
    )

    await codex_entry_versions.create(v_a)
    await codex_entry_versions.create(v_b)
    await codex_entry_versions.create(v_other)

    listed = await codex_entry_versions.list_by_entry(10)

    # Exactly entry 10's versions (both, and only those).
    assert {v.entry_id for v in listed} == {10}
    assert {v.generation for v in listed} == {1, 2}
    assert len(listed) == 2


# ---------------------------------------------------------------------------
# DoD-4 — TABLE_REGISTRY order (the codex interleave; canonical-restricted)
# ---------------------------------------------------------------------------


# DoD-4: `codex_entries` then `codex_entry_versions` are slotted BETWEEN
# `chapter_note_changesets` and `flags` (flags now follows the codex tables); the
# label sequence equals the canonical order restricted to the tables present so
# far.
def test_table_registry_order__DoD4():
    labels = [entry[0] for entry in TABLE_REGISTRY]

    # Both new codex tables are registered.
    assert "codex_entries" in labels
    assert "codex_entry_versions" in labels

    # The codex interleave: chapter_note_changesets < codex_entries <
    # codex_entry_versions < flags (flags displaced forward, now AFTER codex).
    assert labels.index("chapter_note_changesets") < labels.index("codex_entries")
    assert labels.index("codex_entries") < labels.index("codex_entry_versions")
    assert labels.index("codex_entry_versions") < labels.index("flags")

    # The registry's label sequence equals the canonical order filtered down to
    # the tables actually present (canonical-restricted invariant).
    present = set(labels)
    expected_sequence = [name for name in CANONICAL_ORDER if name in present]
    assert labels == expected_sequence

    # The new tuples bind the correct model classes.
    by_label = {entry[0]: entry for entry in TABLE_REGISTRY}
    assert by_label["codex_entries"][1] is CodexEntry
    assert by_label["codex_entry_versions"][1] is CodexEntryVersion


# ---------------------------------------------------------------------------
# DoD-5 SUPERSEDED — codex IS a vector source (013.codex step 005, DoD-15)
# ---------------------------------------------------------------------------


# 013.codex step 005 DoD-15 (supersedes feature-008 DoD-5): the deferral this
# file locked in is discharged — `codex_entries` IS now a registered vector
# source. VECTOR_SOURCE_REGISTRY holds exactly one entry, a typed `VectorSource`
# (no longer a `(model_class, text_extractor)` tuple, so its fields are read BY
# NAME), discriminated `codex_entry` and bound to the CodexEntry model class.
# CodexEntryVersion is not a source — history rows are not indexed.
def test_codex_registered_as_vector_source__DoD15():
    assert len(VECTOR_SOURCE_REGISTRY) == 1

    source = VECTOR_SOURCE_REGISTRY[0]
    assert source.source_kind == "codex_entry"
    assert source.model_class is CodexEntry

    model_classes = [entry.model_class for entry in VECTOR_SOURCE_REGISTRY]
    assert CodexEntry in model_classes
    assert CodexEntryVersion not in model_classes


# ---------------------------------------------------------------------------
# DoD-6 — schema present + drift-clean consistency report
# ---------------------------------------------------------------------------


# DoD-6: after init_db() (the `db` fixture), both `codex_entries` and
# `codex_entry_versions` exist in SQLModel.metadata and the FEAT-005 consistency
# report is clean (every table entry has status "ok").
async def test_schema_present_and_drift_clean__DoD6(db: DbConfig):
    tables = SQLModel.metadata.tables
    assert "codex_entries" in tables
    assert "codex_entry_versions" in tables

    report = await db_admin.build_consistency_report()
    by_name = {entry.name: entry for entry in report.tables}

    # The new tables are reported and clean.
    assert by_name["codex_entries"].status == "ok"
    assert by_name["codex_entry_versions"].status == "ok"

    # A freshly-created DB matches metadata: no table drifts.
    for entry in report.tables:
        assert entry.status == "ok", f"table {entry.name!r} not clean: {entry.status}"
