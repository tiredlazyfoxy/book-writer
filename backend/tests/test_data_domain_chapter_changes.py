"""Tests for the ChapterChange + ChapterTextRevision tables (feature 008, step 006).

Bound to the frozen skeleton signatures (status.md -> Skeleton -> Step 006):
    two enums in app.models.chapter_change:
        class PlacementKind(str, enum.Enum) {append, range}
        class ChangeStatus(str, enum.Enum) {pending, applied, rejected}
    class ChapterChange(SQLModel, table=True) __tablename__="chapter_changes";
        id: int (snowflake PK), chapter_id: int (FK chapters.id),
        author_id: int (FK users.id), placement_kind: PlacementKind (required),
        line_from: int | None, line_to: int | None, base_version: int (required),
        text: str, status: ChangeStatus (required), applied_at: datetime | None,
        applied_by: int | None (nullable FK users.id), created_at: datetime | None
                                                        in app.models.chapter_change
    class ChapterTextRevision(SQLModel, table=True)
        __tablename__="chapter_text_revisions";
        id: int (snowflake PK), chapter_id: int (FK chapters.id),
        applied_change_id: int (FK chapter_changes.id), text_before: str,
        applied_by: int (NON-null FK users.id), applied_at: datetime | None
                                                  in app.models.chapter_text_revision
    async def create / get_by_id(change_id) / list_by_chapter(chapter_id)
                                                        in app.db.chapter_changes
    async def create / get_by_id(revision_id) / list_by_chapter(chapter_id)
                                                  in app.db.chapter_text_revisions
    def _chapter_change_to_dict / _dict_to_chapter_change      in db_import_export
    def _chapter_text_revision_to_dict / _dict_to_chapter_text_revision
                                                              in db_import_export
    TABLE_REGISTRY: ("chapter_changes", ...) then ("chapter_text_revisions", ...)
        at positions 11, 12 (after chapters)                 in db_import_export
    build_consistency_report() -> report with .tables entries each carrying
        .name / .status                                       in app.services.db_admin

Expected values come from the step spec (006.chapter-changes.md DoD +
006.context.md + context.md), never from implementation internals:
    - ChapterChange codec emits `id`/`chapter_id`/`author_id` as strings parsed
      back to the same ints; the nullable FK `applied_by` emits as a STRING when
      set (id-as-string convention) and as None when null, parsing back to the
      int or None; both enums emit their `.value` string and parse back to the
      member; nullable `line_from`/`line_to` round-trip (ints in the range shape,
      None in the append shape); `base_version` int, `text`, and isoformat
      `created_at`/`applied_at` (set and None) are preserved (DoD-1);
    - ChapterTextRevision codec emits `id`/`chapter_id`/`applied_change_id`/
      `applied_by` as strings parsed back to ints; `text_before` and isoformat
      `applied_at` preserved (DoD-2);
    - db round-trip: for each table create -> get_by_id returns an equal row and
      list_by_chapter returns exactly a chapter's rows (two chapter_ids inserted)
      (DoD-3);
    - TABLE_REGISTRY lists chapter_changes then chapter_text_revisions after
      chapters, and the label sequence equals the canonical order restricted to
      present tables (DoD-4);
    - after init_db(), both tables exist in SQLModel.metadata and the FEAT-005
      consistency report is clean (DoD-5).

Async tests use asyncio_mode = "auto"; the `db` fixture (conftest) supplies an
initialized throwaway temp-SQLite engine with the registered tables created.
Pure-codec tests (DoD-1/DoD-2) and the registry test (DoD-4) need no DB.
SQLite does NOT enforce FKs by default, so rows need no parent chapter/user row.
"""

from datetime import datetime

from sqlmodel import SQLModel

from app.db import chapter_changes, chapter_text_revisions
from app.db.engine import DbConfig
from app.models.chapter_change import ChangeStatus, ChapterChange, PlacementKind
from app.models.chapter_text_revision import ChapterTextRevision
from app.services import db_admin
from app.services.db_import_export import (
    TABLE_REGISTRY,
    _chapter_change_to_dict,
    _chapter_text_revision_to_dict,
    _dict_to_chapter_change,
    _dict_to_chapter_text_revision,
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
# DoD-1 — ChapterChange codec round-trip
# ---------------------------------------------------------------------------


# DoD-1 (range + applied shape): placement_kind=range with line_from/line_to set
# to ints, status=applied, applied_at set to a datetime, applied_by set to an
# int. `id`/`chapter_id`/`author_id` emit as strings and parse back to the same
# ints; the nullable FK `applied_by` (set) emits as a STRING and parses back to
# the int; both enums emit their `.value` and parse back to the member;
# line_from/line_to survive as ints; base_version int, text, and the isoformat
# created_at/applied_at survive.
def test_chapter_change_codec_round_trips_range_applied_shape__DoD1():
    created_at = datetime(2026, 7, 25, 9, 0, 0)
    applied_at = datetime(2026, 7, 25, 9, 30, 0)
    change = ChapterChange(
        id=111222333,
        chapter_id=444555666,
        author_id=777888999,
        placement_kind=PlacementKind.range,
        line_from=12,
        line_to=34,
        base_version=5,
        text="A ranged edit body",
        status=ChangeStatus.applied,
        applied_at=applied_at,
        applied_by=101112131,
        created_at=created_at,
    )

    data = _chapter_change_to_dict(change)

    # `id` / `chapter_id` / `author_id` emitted as strings.
    assert data["id"] == "111222333"
    assert isinstance(data["id"], str)
    assert data["chapter_id"] == "444555666"
    assert isinstance(data["chapter_id"], str)
    assert data["author_id"] == "777888999"
    assert isinstance(data["author_id"], str)
    # Nullable FK `applied_by` (set) emitted as a STRING (id-as-string).
    assert data["applied_by"] == "101112131"
    assert isinstance(data["applied_by"], str)
    # Both enums emitted via their `.value` strings.
    assert data["placement_kind"] == "range"
    assert data["status"] == "applied"
    # Nullable line ints (set) pass through.
    assert data["line_from"] == 12
    assert data["line_to"] == 34
    # base_version int + text pass through.
    assert data["base_version"] == 5
    assert data["text"] == "A ranged edit body"
    # Timestamps via isoformat strings.
    assert data["created_at"] == created_at.isoformat()
    assert data["applied_at"] == applied_at.isoformat()

    restored = _dict_to_chapter_change(data)

    # `id` / `chapter_id` / `author_id` parse back to the same ints.
    assert restored.id == 111222333
    assert isinstance(restored.id, int)
    assert restored.chapter_id == 444555666
    assert isinstance(restored.chapter_id, int)
    assert restored.author_id == 777888999
    assert isinstance(restored.author_id, int)
    # Nullable FK `applied_by` (set) parses back to the int.
    assert restored.applied_by == 101112131
    assert isinstance(restored.applied_by, int)
    # Both enums parse back to the member.
    assert restored.placement_kind is PlacementKind.range
    assert restored.status is ChangeStatus.applied
    # Nullable line ints preserved.
    assert restored.line_from == 12
    assert restored.line_to == 34
    # base_version int + text preserved.
    assert restored.base_version == 5
    assert restored.text == "A ranged edit body"
    # Timestamps preserved.
    assert restored.created_at == created_at
    assert restored.applied_at == applied_at


# DoD-1 (append + pending shape): placement_kind=append with line_from/line_to
# both None, status=pending, applied_at None, applied_by None. The nullable FK
# `applied_by` (null) emits as None and restores to None; the nullable
# line_from/line_to emit as None and restore to None; applied_at None stays None;
# both enums round-trip; created_at (set) survives.
def test_chapter_change_codec_round_trips_append_pending_shape__DoD1():
    created_at = datetime(2026, 7, 25, 10, 0, 0)
    change = ChapterChange(
        id=222333444,
        chapter_id=555666777,
        author_id=888999000,
        placement_kind=PlacementKind.append,
        line_from=None,
        line_to=None,
        base_version=1,
        text="An appended paragraph",
        status=ChangeStatus.pending,
        applied_at=None,
        applied_by=None,
        created_at=created_at,
    )

    data = _chapter_change_to_dict(change)

    # Nullable FK `applied_by` (null) emitted as None.
    assert data["applied_by"] is None
    # Nullable line ints (null) emitted as None.
    assert data["line_from"] is None
    assert data["line_to"] is None
    # applied_at None emitted as None.
    assert data["applied_at"] is None
    # Both enums via their `.value` strings.
    assert data["placement_kind"] == "append"
    assert data["status"] == "pending"
    assert data["base_version"] == 1
    assert data["text"] == "An appended paragraph"
    assert data["created_at"] == created_at.isoformat()

    restored = _dict_to_chapter_change(data)

    assert restored.id == 222333444
    assert restored.chapter_id == 555666777
    assert restored.author_id == 888999000
    # Nullable FK `applied_by` restores to None.
    assert restored.applied_by is None
    # Nullable line ints restore to None.
    assert restored.line_from is None
    assert restored.line_to is None
    # applied_at stays None.
    assert restored.applied_at is None
    # Both enums restore to their members.
    assert restored.placement_kind is PlacementKind.append
    assert restored.status is ChangeStatus.pending
    assert restored.base_version == 1
    assert restored.text == "An appended paragraph"
    assert restored.created_at == created_at


# ---------------------------------------------------------------------------
# DoD-2 — ChapterTextRevision codec round-trip
# ---------------------------------------------------------------------------


# DoD-2: ChapterTextRevision round-trips. `id`/`chapter_id`/`applied_change_id`/
# `applied_by` emit as strings and parse back to the same ints; `text_before`
# passes through; isoformat `applied_at` (set) is preserved.
def test_chapter_text_revision_codec_round_trips__DoD2():
    applied_at = datetime(2026, 7, 25, 11, 15, 0)
    revision = ChapterTextRevision(
        id=121314151,
        chapter_id=161718192,
        applied_change_id=202122232,
        text_before="The full chapter body before the change.",
        applied_by=242526272,
        applied_at=applied_at,
    )

    data = _chapter_text_revision_to_dict(revision)

    # All four id fields emitted as strings.
    assert data["id"] == "121314151"
    assert isinstance(data["id"], str)
    assert data["chapter_id"] == "161718192"
    assert isinstance(data["chapter_id"], str)
    assert data["applied_change_id"] == "202122232"
    assert isinstance(data["applied_change_id"], str)
    assert data["applied_by"] == "242526272"
    assert isinstance(data["applied_by"], str)
    # text_before passes through.
    assert data["text_before"] == "The full chapter body before the change."
    # applied_at via isoformat string.
    assert data["applied_at"] == applied_at.isoformat()

    restored = _dict_to_chapter_text_revision(data)

    # All four id fields parse back to the same ints.
    assert restored.id == 121314151
    assert isinstance(restored.id, int)
    assert restored.chapter_id == 161718192
    assert isinstance(restored.chapter_id, int)
    assert restored.applied_change_id == 202122232
    assert isinstance(restored.applied_change_id, int)
    assert restored.applied_by == 242526272
    assert isinstance(restored.applied_by, int)
    # text_before preserved.
    assert restored.text_before == "The full chapter body before the change."
    # applied_at preserved.
    assert restored.applied_at == applied_at


# DoD-2: ChapterTextRevision with a null applied_at round-trips — applied_at
# emits as None and restores to None (nullable per the timestamp convention).
def test_chapter_text_revision_codec_null_applied_at__DoD2():
    revision = ChapterTextRevision(
        id=313233343,
        chapter_id=353637383,
        applied_change_id=394041424,
        text_before="Body snapshot",
        applied_by=434445464,
        applied_at=None,
    )

    data = _chapter_text_revision_to_dict(revision)
    assert data["applied_at"] is None

    restored = _dict_to_chapter_text_revision(data)
    assert restored.applied_at is None
    assert restored.applied_by == 434445464


# ---------------------------------------------------------------------------
# DoD-3 — DB round-trip (create -> get_by_id + list_by_chapter filter)
# ---------------------------------------------------------------------------


# DoD-3: chapter_changes.create(row) then get_by_id(row.id) returns an equal row.
# Required non-null fields (chapter_id, author_id, placement_kind, base_version,
# text, status) are provided; the snowflake PK is populated on create.
async def test_chapter_changes_db_round_trip__DoD3(db: DbConfig):
    row = ChapterChange(
        chapter_id=42,
        author_id=7,
        placement_kind=PlacementKind.append,
        base_version=2,
        text="Persisted change body",
        status=ChangeStatus.pending,
    )

    created = await chapter_changes.create(row)
    # Snowflake PK populated on the created row.
    assert created.id is not None

    fetched = await chapter_changes.get_by_id(created.id)
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.chapter_id == 42
    assert fetched.author_id == 7
    assert fetched.placement_kind is PlacementKind.append
    assert fetched.base_version == 2
    assert fetched.text == "Persisted change body"
    assert fetched.status is ChangeStatus.pending


# DoD-3: chapter_changes.list_by_chapter(chapter_id) returns exactly that
# chapter's rows. Rows are inserted for two different chapter_ids and the filter
# selects only the matching chapter's rows.
async def test_chapter_changes_list_by_chapter_filters__DoD3(db: DbConfig):
    ch_a = ChapterChange(
        chapter_id=10,
        author_id=1,
        placement_kind=PlacementKind.append,
        base_version=1,
        text="a0",
        status=ChangeStatus.pending,
    )
    ch_b = ChapterChange(
        chapter_id=10,
        author_id=2,
        placement_kind=PlacementKind.range,
        line_from=1,
        line_to=3,
        base_version=1,
        text="a1",
        status=ChangeStatus.applied,
    )
    ch_other = ChapterChange(
        chapter_id=20,
        author_id=3,
        placement_kind=PlacementKind.append,
        base_version=1,
        text="b0",
        status=ChangeStatus.pending,
    )

    await chapter_changes.create(ch_a)
    await chapter_changes.create(ch_b)
    await chapter_changes.create(ch_other)

    listed = await chapter_changes.list_by_chapter(10)

    # Exactly chapter 10's changes (both, and only those).
    assert {c.chapter_id for c in listed} == {10}
    assert {c.text for c in listed} == {"a0", "a1"}
    assert len(listed) == 2


# DoD-3: chapter_text_revisions.create(row) then get_by_id(row.id) returns an
# equal row. Required non-null fields (chapter_id, applied_change_id,
# text_before, applied_by) are provided; the snowflake PK is populated on create.
async def test_chapter_text_revisions_db_round_trip__DoD3(db: DbConfig):
    row = ChapterTextRevision(
        chapter_id=55,
        applied_change_id=99,
        text_before="Snapshot before apply",
        applied_by=8,
    )

    created = await chapter_text_revisions.create(row)
    assert created.id is not None

    fetched = await chapter_text_revisions.get_by_id(created.id)
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.chapter_id == 55
    assert fetched.applied_change_id == 99
    assert fetched.text_before == "Snapshot before apply"
    assert fetched.applied_by == 8


# DoD-3: chapter_text_revisions.list_by_chapter(chapter_id) returns exactly that
# chapter's rows. Rows are inserted for two different chapter_ids and the filter
# selects only the matching chapter's rows.
async def test_chapter_text_revisions_list_by_chapter_filters__DoD3(db: DbConfig):
    rev_a = ChapterTextRevision(
        chapter_id=30,
        applied_change_id=1,
        text_before="a-before",
        applied_by=1,
    )
    rev_b = ChapterTextRevision(
        chapter_id=30,
        applied_change_id=2,
        text_before="b-before",
        applied_by=1,
    )
    rev_other = ChapterTextRevision(
        chapter_id=40,
        applied_change_id=3,
        text_before="c-before",
        applied_by=2,
    )

    await chapter_text_revisions.create(rev_a)
    await chapter_text_revisions.create(rev_b)
    await chapter_text_revisions.create(rev_other)

    listed = await chapter_text_revisions.list_by_chapter(30)

    # Exactly chapter 30's revisions (both, and only those).
    assert {r.chapter_id for r in listed} == {30}
    assert {r.text_before for r in listed} == {"a-before", "b-before"}
    assert len(listed) == 2


# ---------------------------------------------------------------------------
# DoD-4 — TABLE_REGISTRY order (canonical-restricted invariant)
# ---------------------------------------------------------------------------


# DoD-4: `chapter_changes` then `chapter_text_revisions` appear in TABLE_REGISTRY,
# each after `chapters`, and the label sequence equals the canonical order
# restricted to the tables present so far.
def test_table_registry_order__DoD4():
    labels = [entry[0] for entry in TABLE_REGISTRY]

    # Both new tables are registered.
    assert "chapter_changes" in labels
    assert "chapter_text_revisions" in labels

    # Each appears after chapters (their FK parent block); chapter_changes
    # precedes chapter_text_revisions (which FKs chapter_changes.id).
    assert labels.index("chapters") < labels.index("chapter_changes")
    assert labels.index("chapters") < labels.index("chapter_text_revisions")
    assert labels.index("chapter_changes") < labels.index("chapter_text_revisions")

    # The registry's label sequence equals the canonical order filtered down to
    # the tables actually present (canonical-restricted invariant).
    present = set(labels)
    expected_sequence = [name for name in CANONICAL_ORDER if name in present]
    assert labels == expected_sequence

    # The new tuples bind the correct model classes.
    by_label = {entry[0]: entry for entry in TABLE_REGISTRY}
    assert by_label["chapter_changes"][1] is ChapterChange
    assert by_label["chapter_text_revisions"][1] is ChapterTextRevision


# ---------------------------------------------------------------------------
# DoD-5 — schema present + drift-clean consistency report
# ---------------------------------------------------------------------------


# DoD-5: after init_db() (the `db` fixture), both `chapter_changes` and
# `chapter_text_revisions` exist in SQLModel.metadata and the FEAT-005
# consistency report is clean (every table entry has status "ok").
async def test_schema_present_and_drift_clean__DoD5(db: DbConfig):
    tables = SQLModel.metadata.tables
    assert "chapter_changes" in tables
    assert "chapter_text_revisions" in tables

    report = await db_admin.build_consistency_report()
    by_name = {entry.name: entry for entry in report.tables}

    # The new tables are reported and clean.
    assert by_name["chapter_changes"].status == "ok"
    assert by_name["chapter_text_revisions"].status == "ok"

    # A freshly-created DB matches metadata: no table drifts.
    for entry in report.tables:
        assert entry.status == "ok", f"table {entry.name!r} not clean: {entry.status}"
