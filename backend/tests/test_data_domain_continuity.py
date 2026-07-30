"""Tests for the continuity tables: ChapterNoteChangeset + Flag (feature 008, step 007).

Bound to the frozen skeleton signatures (status.md -> Skeleton -> Step 007):
    one enum in app.models.chapter_notes:
        class NoteStatus(str, enum.Enum) {draft, approved, stale}
    class ChapterNoteChangeset(SQLModel, table=True)
        __tablename__="chapter_note_changesets";
        id: int (snowflake PK), chapter_id: int (SINGLE-COLUMN unique + FK chapters.id),
        added: str, modified: str, deleted: str,
        status: NoteStatus | None (nullable, Stage-4 land-now),
        created_at: datetime | None, modified_at: datetime | None
                                                        in app.models.chapter_notes
    two enums in app.models.flag:
        class FlagOrigin(str, enum.Enum) {check, person}
        class FlagStatus(str, enum.Enum) {open, resolved}
    class Flag(SQLModel, table=True) __tablename__="flags";
        id: int (snowflake PK), chapter_id: int (FK chapters.id),
        origin: FlagOrigin (required), comment: str, status: FlagStatus (required),
        created_by: int (NON-null FK users.id), created_at: datetime | None,
        resolved_by: int | None (nullable FK users.id), resolved_at: datetime | None
                                                        in app.models.flag
    async def create / get_by_id(changeset_id) / get_by_chapter(chapter_id)
        -> ChapterNoteChangeset | None (SINGLE row or None, NOT a list)
                                                  in app.db.chapter_note_changesets
    async def create / get_by_id(flag_id) / list_by_chapter(chapter_id) -> list[Flag]
                                                        in app.db.flags
    def _chapter_note_changeset_to_dict / _dict_to_chapter_note_changeset
                                                              in db_import_export
    def _flag_to_dict / _dict_to_flag                         in db_import_export
    TABLE_REGISTRY: ("chapter_note_changesets", ...) then ("flags", ...)
        (chapter_note_changesets after chapter_text_revisions; flags immediately
        after chapter_note_changesets — codex tables not present yet)
                                                              in db_import_export
    build_consistency_report() -> report with .tables entries each carrying
        .name / .status                                       in app.services.db_admin

Expected values come from the step spec (007.continuity.md DoD + 007.context.md +
context.md), never from implementation internals:
    - ChapterNoteChangeset codec emits `id`/`chapter_id` as strings parsed back to
      the same ints; `added`/`modified`/`deleted` pass through; the nullable
      `status` round-trips in BOTH the null shape (None -> None) and the set shape
      (member -> its `.value` -> member); isoformat timestamps (set and None) are
      preserved (DoD-1);
    - Flag codec emits `id`/`chapter_id`/`created_by` as strings parsed back to
      ints; `origin` and `status` emit their `.value` and parse back to the member;
      `comment` and isoformat `created_at` are preserved; the nullable FK
      `resolved_by` emits as a STRING when set and None when null, and the nullable
      `resolved_at` round-trips — null while OPEN, set once RESOLVED (DoD-2);
    - db round-trip: create -> get_by_id returns an equal row for both tables;
      get_by_chapter returns the single changeset (or None); list_by_chapter
      returns exactly a chapter's flags (two chapter_ids inserted) (DoD-3);
    - chapter_id unique on the changeset enforced: a second changeset for the same
      chapter is rejected by the DB (DoD-4);
    - TABLE_REGISTRY lists chapter_note_changesets after chapter_text_revisions and
      flags after chapter_note_changesets, label sequence equal to the canonical
      order restricted to present tables (codex absent at this step) (DoD-5);
    - after init_db(), both tables exist in SQLModel.metadata and the FEAT-005
      consistency report is clean (DoD-6).

Async tests use asyncio_mode = "auto"; the `db` fixture (conftest) supplies an
initialized throwaway temp-SQLite engine with the registered tables created.
Pure-codec tests (DoD-1, DoD-2) and the registry test (DoD-5) need no DB.
SQLite does NOT enforce FKs by default, so rows need no parent chapter/user row;
the single-column UNIQUE on the changeset's chapter_id (DoD-4) is enforced regardless.
"""

from datetime import datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import SQLModel

from app.db import chapter_note_changesets, flags
from app.db.engine import DbConfig
from app.models.chapter_notes import ChapterNoteChangeset, NoteStatus
from app.models.flag import Flag, FlagOrigin, FlagStatus
from app.services import db_admin
from app.services.db_import_export import (
    TABLE_REGISTRY,
    _chapter_note_changeset_to_dict,
    _dict_to_chapter_note_changeset,
    _dict_to_flag,
    _flag_to_dict,
)

# The canonical FK order (context.md -> "The canonical TABLE_REGISTRY order").
# The registry-order invariant is asserted by filtering this list down to the
# tables actually present, so it stays valid as later steps add entries. At THIS
# step the codex tables do not exist yet, so `flags` immediately follows
# `chapter_note_changesets` under the restriction.
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
# DoD-1 — ChapterNoteChangeset codec round-trip
# ---------------------------------------------------------------------------


# DoD-1 (status set shape): a changeset whose nullable `status` is set to an enum
# member (NoteStatus.approved) round-trips. `id`/`chapter_id` emit as strings and
# parse back to the same ints; `added`/`modified`/`deleted` pass through; `status`
# emits its `.value` and parses back to the member; the isoformat timestamps
# survive.
def test_chapter_note_changeset_codec_round_trips_status_set_shape__DoD1():
    created_at = datetime(2026, 7, 25, 9, 0, 0)
    modified_at = datetime(2026, 7, 25, 9, 30, 0)
    changeset = ChapterNoteChangeset(
        id=111222333,
        chapter_id=444555666,
        added="New facts introduced",
        modified="Amended facts",
        deleted="Retired facts",
        status=NoteStatus.approved,
        created_at=created_at,
        modified_at=modified_at,
    )

    data = _chapter_note_changeset_to_dict(changeset)

    # `id` / `chapter_id` emitted as strings.
    assert data["id"] == "111222333"
    assert isinstance(data["id"], str)
    assert data["chapter_id"] == "444555666"
    assert isinstance(data["chapter_id"], str)
    # Free-text operation fields pass through.
    assert data["added"] == "New facts introduced"
    assert data["modified"] == "Amended facts"
    assert data["deleted"] == "Retired facts"
    # Nullable `status` (set) emitted via its `.value` string.
    assert data["status"] == "approved"
    # Timestamps via isoformat strings.
    assert data["created_at"] == created_at.isoformat()
    assert data["modified_at"] == modified_at.isoformat()

    restored = _dict_to_chapter_note_changeset(data)

    # `id` / `chapter_id` parse back to the same ints.
    assert restored.id == 111222333
    assert isinstance(restored.id, int)
    assert restored.chapter_id == 444555666
    assert isinstance(restored.chapter_id, int)
    assert restored.added == "New facts introduced"
    assert restored.modified == "Amended facts"
    assert restored.deleted == "Retired facts"
    # Nullable `status` (set) parses back to the enum member.
    assert restored.status is NoteStatus.approved
    assert restored.created_at == created_at
    assert restored.modified_at == modified_at


# DoD-1 (status null shape): a changeset whose nullable `status` is None (the
# Stage-4 land-now default) round-trips. `status` emits as None and restores to
# None; None timestamps stay None.
def test_chapter_note_changeset_codec_round_trips_status_null_shape__DoD1():
    changeset = ChapterNoteChangeset(
        id=222333444,
        chapter_id=555666777,
        added="",
        modified="",
        deleted="",
        status=None,
        created_at=None,
        modified_at=None,
    )

    data = _chapter_note_changeset_to_dict(changeset)

    # Nullable `status` (None) emitted as None.
    assert data["status"] is None
    # None timestamps emitted as None.
    assert data["created_at"] is None
    assert data["modified_at"] is None
    assert data["added"] == ""
    assert data["modified"] == ""
    assert data["deleted"] == ""

    restored = _dict_to_chapter_note_changeset(data)

    assert restored.id == 222333444
    assert restored.chapter_id == 555666777
    # Nullable `status` restores to None.
    assert restored.status is None
    assert restored.added == ""
    assert restored.modified == ""
    assert restored.deleted == ""
    assert restored.created_at is None
    assert restored.modified_at is None


# DoD-1: EVERY one of the three `status` values (draft, approved, stale) emits its
# `.value` string and parses back to the exact enum member (the set shape).
@pytest.mark.parametrize(
    "status",
    [
        NoteStatus.draft,
        NoteStatus.approved,
        NoteStatus.stale,
    ],
)
def test_chapter_note_changeset_status_round_trips_every_value__DoD1(
    status: NoteStatus,
):
    changeset = ChapterNoteChangeset(
        id=333444555,
        chapter_id=666777888,
        added="a",
        modified="m",
        deleted="d",
        status=status,
    )

    data = _chapter_note_changeset_to_dict(changeset)
    assert data["status"] == status.value

    restored = _dict_to_chapter_note_changeset(data)
    assert restored.status is status


# ---------------------------------------------------------------------------
# DoD-2 — Flag codec round-trip
# ---------------------------------------------------------------------------


# DoD-2 (OPEN shape): an open flag with status=open, resolved_by=None,
# resolved_at=None round-trips. `id`/`chapter_id`/`created_by` emit as strings and
# parse back to the same ints; `origin` and `status` emit their `.value` and parse
# back to the member; `comment` and isoformat `created_at` survive; the nullable
# `resolved_by` emits as None and restores to None; `resolved_at` stays None.
def test_flag_codec_round_trips_open_shape__DoD2():
    created_at = datetime(2026, 7, 25, 9, 0, 0)
    flag = Flag(
        id=111222333,
        chapter_id=444555666,
        origin=FlagOrigin.check,
        comment="Continuity check failed here",
        status=FlagStatus.open,
        created_by=777888999,
        created_at=created_at,
        resolved_by=None,
        resolved_at=None,
    )

    data = _flag_to_dict(flag)

    # `id` / `chapter_id` / `created_by` emitted as strings.
    assert data["id"] == "111222333"
    assert isinstance(data["id"], str)
    assert data["chapter_id"] == "444555666"
    assert isinstance(data["chapter_id"], str)
    assert data["created_by"] == "777888999"
    assert isinstance(data["created_by"], str)
    # Both enums emitted via their `.value` strings.
    assert data["origin"] == "check"
    assert data["status"] == "open"
    # comment passes through.
    assert data["comment"] == "Continuity check failed here"
    # created_at via isoformat string.
    assert data["created_at"] == created_at.isoformat()
    # Nullable resolution fields (null while open) emitted as None.
    assert data["resolved_by"] is None
    assert data["resolved_at"] is None

    restored = _dict_to_flag(data)

    # `id` / `chapter_id` / `created_by` parse back to the same ints.
    assert restored.id == 111222333
    assert isinstance(restored.id, int)
    assert restored.chapter_id == 444555666
    assert isinstance(restored.chapter_id, int)
    assert restored.created_by == 777888999
    assert isinstance(restored.created_by, int)
    # Both enums parse back to the member.
    assert restored.origin is FlagOrigin.check
    assert restored.status is FlagStatus.open
    assert restored.comment == "Continuity check failed here"
    assert restored.created_at == created_at
    # Nullable resolution fields restore to None.
    assert restored.resolved_by is None
    assert restored.resolved_at is None


# DoD-2 (RESOLVED shape): a resolved flag with status=resolved, resolved_by set to
# an int, resolved_at set to a datetime round-trips. The `origin`=person and
# `status`=resolved enums round-trip; the nullable FK `resolved_by` (set) emits as
# a STRING (id-as-string, like created_by) and parses back to the same int; the
# isoformat `resolved_at` is preserved.
def test_flag_codec_round_trips_resolved_shape__DoD2():
    created_at = datetime(2026, 7, 25, 10, 0, 0)
    resolved_at = datetime(2026, 7, 25, 12, 0, 0)
    flag = Flag(
        id=222333444,
        chapter_id=555666777,
        origin=FlagOrigin.person,
        comment="Reader-reported inconsistency",
        status=FlagStatus.resolved,
        created_by=888999000,
        created_at=created_at,
        resolved_by=101112131,
        resolved_at=resolved_at,
    )

    data = _flag_to_dict(flag)

    # The second enum-value set.
    assert data["origin"] == "person"
    assert data["status"] == "resolved"
    assert data["comment"] == "Reader-reported inconsistency"
    assert data["created_at"] == created_at.isoformat()
    # Nullable FK `resolved_by` (set) emitted as a STRING (id-as-string).
    assert data["resolved_by"] == "101112131"
    assert isinstance(data["resolved_by"], str)
    # resolved_at via isoformat string.
    assert data["resolved_at"] == resolved_at.isoformat()

    restored = _dict_to_flag(data)

    assert restored.id == 222333444
    assert restored.chapter_id == 555666777
    assert restored.created_by == 888999000
    assert restored.origin is FlagOrigin.person
    assert restored.status is FlagStatus.resolved
    assert restored.comment == "Reader-reported inconsistency"
    assert restored.created_at == created_at
    # Nullable FK `resolved_by` (set) parses back to the int.
    assert restored.resolved_by == 101112131
    assert isinstance(restored.resolved_by, int)
    # resolved_at preserved.
    assert restored.resolved_at == resolved_at


# ---------------------------------------------------------------------------
# DoD-3 — DB round-trip (create -> get_by_id; get_by_chapter single/None;
#         list_by_chapter filter)
# ---------------------------------------------------------------------------


# DoD-3: chapter_note_changesets.create(row) then get_by_id(row.id) returns an
# equal row. Required non-null fields (chapter_id, added, modified, deleted) are
# provided; the snowflake PK is populated on create.
async def test_chapter_note_changesets_db_round_trip__DoD3(db: DbConfig):
    row = ChapterNoteChangeset(
        chapter_id=42,
        added="Introduced X",
        modified="Adjusted Y",
        deleted="Removed Z",
    )

    created = await chapter_note_changesets.create(row)
    # Snowflake PK populated on the created row.
    assert created.id is not None

    fetched = await chapter_note_changesets.get_by_id(created.id)
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.chapter_id == 42
    assert fetched.added == "Introduced X"
    assert fetched.modified == "Adjusted Y"
    assert fetched.deleted == "Removed Z"


# DoD-3: get_by_chapter(chapter_id) returns the SINGLE changeset for a chapter that
# has one, and None for a chapter that has none (chapter_id is unique — one
# changeset per chapter, so this returns a row or None, NOT a list).
async def test_chapter_note_changesets_get_by_chapter_single_or_none__DoD3(
    db: DbConfig,
):
    created = await chapter_note_changesets.create(
        ChapterNoteChangeset(chapter_id=77, added="a", modified="m", deleted="d")
    )

    # The chapter with a changeset yields exactly that single row.
    fetched = await chapter_note_changesets.get_by_chapter(77)
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.chapter_id == 77

    # A chapter with no changeset yields None.
    missing = await chapter_note_changesets.get_by_chapter(99)
    assert missing is None


# DoD-3: flags.create(row) then get_by_id(row.id) returns an equal row. Required
# non-null fields (chapter_id, origin, comment, status, created_by) are provided;
# the snowflake PK is populated on create.
async def test_flags_db_round_trip__DoD3(db: DbConfig):
    row = Flag(
        chapter_id=55,
        origin=FlagOrigin.check,
        comment="Persisted flag body",
        status=FlagStatus.open,
        created_by=8,
    )

    created = await flags.create(row)
    assert created.id is not None

    fetched = await flags.get_by_id(created.id)
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.chapter_id == 55
    assert fetched.origin is FlagOrigin.check
    assert fetched.comment == "Persisted flag body"
    assert fetched.status is FlagStatus.open
    assert fetched.created_by == 8


# DoD-3: flags.list_by_chapter(chapter_id) returns exactly that chapter's flags.
# Flags are inserted for two different chapter_ids and the filter selects only the
# matching chapter's rows.
async def test_flags_list_by_chapter_filters__DoD3(db: DbConfig):
    flag_a = Flag(
        chapter_id=10,
        origin=FlagOrigin.check,
        comment="a0",
        status=FlagStatus.open,
        created_by=1,
    )
    flag_b = Flag(
        chapter_id=10,
        origin=FlagOrigin.person,
        comment="a1",
        status=FlagStatus.resolved,
        created_by=2,
    )
    flag_other = Flag(
        chapter_id=20,
        origin=FlagOrigin.check,
        comment="b0",
        status=FlagStatus.open,
        created_by=3,
    )

    await flags.create(flag_a)
    await flags.create(flag_b)
    await flags.create(flag_other)

    listed = await flags.list_by_chapter(10)

    # Exactly chapter 10's flags (both, and only those).
    assert {f.chapter_id for f in listed} == {10}
    assert {f.comment for f in listed} == {"a0", "a1"}
    assert len(listed) == 2


# ---------------------------------------------------------------------------
# DoD-4 — changeset chapter_id single-column unique enforced
# ---------------------------------------------------------------------------


# DoD-4: a second ChapterNoteChangeset for the SAME chapter_id is rejected by the
# DB (single-column UNIQUE on chapter_id — one changeset per chapter). The two
# rows differ only by the auto surrogate id.
async def test_chapter_note_changeset_chapter_id_unique_enforced__DoD4(db: DbConfig):
    await chapter_note_changesets.create(
        ChapterNoteChangeset(chapter_id=10, added="a", modified="m", deleted="d")
    )

    with pytest.raises(IntegrityError):
        await chapter_note_changesets.create(
            ChapterNoteChangeset(
                chapter_id=10, added="a2", modified="m2", deleted="d2"
            )
        )


# ---------------------------------------------------------------------------
# DoD-5 — TABLE_REGISTRY order (canonical-restricted invariant)
# ---------------------------------------------------------------------------


# DoD-5: `chapter_note_changesets` appears after `chapter_text_revisions` and
# `flags` appears after `chapter_note_changesets`; the label sequence equals the
# canonical order restricted to the tables present so far. At this step the codex
# tables are absent, so `flags` immediately follows `chapter_note_changesets`.
def test_table_registry_order__DoD5():
    labels = [entry[0] for entry in TABLE_REGISTRY]

    # Both new tables are registered.
    assert "chapter_note_changesets" in labels
    assert "flags" in labels

    # chapter_note_changesets follows chapter_text_revisions; flags follows
    # chapter_note_changesets.
    assert labels.index("chapter_text_revisions") < labels.index(
        "chapter_note_changesets"
    )
    assert labels.index("chapter_note_changesets") < labels.index("flags")

    # The registry's label sequence equals the canonical order filtered down to
    # the tables actually present (canonical-restricted invariant). Codex tables
    # are not present yet, so they drop out of the restricted expectation and
    # `flags` immediately follows `chapter_note_changesets`.
    present = set(labels)
    expected_sequence = [name for name in CANONICAL_ORDER if name in present]
    assert labels == expected_sequence

    # The new tuples bind the correct model classes.
    by_label = {entry[0]: entry for entry in TABLE_REGISTRY}
    assert by_label["chapter_note_changesets"][1] is ChapterNoteChangeset
    assert by_label["flags"][1] is Flag


# ---------------------------------------------------------------------------
# DoD-6 — schema present + drift-clean consistency report
# ---------------------------------------------------------------------------


# DoD-6: after init_db() (the `db` fixture), both `chapter_note_changesets` and
# `flags` exist in SQLModel.metadata and the FEAT-005 consistency report is clean
# (every table entry has status "ok").
async def test_schema_present_and_drift_clean__DoD6(db: DbConfig):
    tables = SQLModel.metadata.tables
    assert "chapter_note_changesets" in tables
    assert "flags" in tables

    report = await db_admin.build_consistency_report()
    by_name = {entry.name: entry for entry in report.tables}

    # The new tables are reported and clean.
    assert by_name["chapter_note_changesets"].status == "ok"
    assert by_name["flags"].status == "ok"

    # A freshly-created DB matches metadata: no table drifts.
    for entry in report.tables:
        assert entry.status == "ok", f"table {entry.name!r} not clean: {entry.status}"
