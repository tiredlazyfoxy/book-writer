"""Tests for the Chapter table (feature 008, step 005).

Bound to the frozen skeleton signatures (status.md -> Skeleton -> Step 005):
    two enums in app.models.chapter:
        class ChapterState(str, enum.Enum) {planned, open, closing, closed}
        class SummaryStatus(str, enum.Enum) {draft, approved, stale}
    class Chapter(SQLModel, table=True) __tablename__="chapters";
        id: int (snowflake PK), book_id: int (FK books.id),
        ordinal: int (required, no default), title: str,
        state: ChapterState (required, no default), sketch: str, text: str,
        summary: str | None, summary_status: SummaryStatus | None,
        system_prompt: str | None, version: int = 1,
        created_at: datetime | None, modified_at: datetime | None
                                                          in app.models.chapter
    async def create(row: Chapter) -> Chapter             in app.db.chapters
    async def get_by_id(chapter_id: int) -> Chapter | None  in app.db.chapters
    async def list_by_book(book_id: int) -> list[Chapter]   in app.db.chapters
    def _chapter_to_dict / _dict_to_chapter               in app.services.db_import_export
    TABLE_REGISTRY: ("chapters", Chapter, ...) at position 10 (after
        book_members, before chapter_changes)            in app.services.db_import_export
    build_consistency_report() -> report with .tables entries each carrying
        .name / .status                                   in app.services.db_admin

Expected values come from the step spec (005.chapter.md DoD + 005.context.md +
context.md), never from implementation internals:
    - Chapter codec emits `id`/`book_id` as strings parsed back to the same ints;
      `state` emits its `.value` string and parses back to the enum member (all
      four states — planned, open, closing, closed — round-trip); the nullable
      `summary_status` round-trips in BOTH the null shape (None -> None) and the
      set shape (member -> its `.value` -> member); nullable `summary` /
      `system_prompt` round-trip in both None and set shapes; `version` and
      `ordinal` ints and isoformat timestamps are preserved (DoD-1);
    - db round-trip: create -> get_by_id returns an equal row and list_by_book
      returns exactly a book's chapters (two book_ids inserted) (DoD-2);
    - TABLE_REGISTRY lists chapters after book_members and the label sequence
      equals the canonical order restricted to present tables (DoD-3);
    - after init_db(), `chapters` exists in SQLModel.metadata and the FEAT-005
      consistency report is clean (DoD-4).

Async tests use asyncio_mode = "auto"; the `db` fixture (conftest) supplies an
initialized throwaway temp-SQLite engine with the registered tables created.
Pure-codec tests (DoD-1) and the registry test (DoD-3) need no DB.
SQLite does NOT enforce FKs by default, so chapter rows need no parent book row.
"""

from datetime import datetime

import pytest
from sqlmodel import SQLModel

from app.db import chapters
from app.db.engine import DbConfig
from app.models.chapter import Chapter, ChapterState, SummaryStatus
from app.services import db_admin
from app.services.db_import_export import (
    TABLE_REGISTRY,
    _chapter_to_dict,
    _dict_to_chapter,
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
# DoD-1 — Chapter codec round-trip
# ---------------------------------------------------------------------------


# DoD-1: a fully-populated chapter (summary + summary_status + system_prompt all
# set, version=3) round-trips. `id`/`book_id` emit as strings and parse back to
# the same ints; `state` emits its `.value` and parses back to the member;
# `summary_status` emits its `.value` and parses back to the member; the nullable
# summary/system_prompt strings, the version and ordinal ints and the isoformat
# timestamps survive.
def test_chapter_codec_round_trips_populated_shape__DoD1():
    created_at = datetime(2026, 7, 25, 9, 0, 0)
    modified_at = datetime(2026, 7, 25, 9, 30, 0)
    chapter = Chapter(
        id=111222333,
        book_id=444555666,
        ordinal=7,
        title="Chapter Seven",
        state=ChapterState.open,
        sketch="Forward-looking outline",
        text="The main body prose",
        summary="Backward-looking summary",
        summary_status=SummaryStatus.approved,
        system_prompt="Chapter-scoped prompt",
        version=3,
        created_at=created_at,
        modified_at=modified_at,
    )

    data = _chapter_to_dict(chapter)

    # `id` / `book_id` emitted as strings.
    assert data["id"] == "111222333"
    assert isinstance(data["id"], str)
    assert data["book_id"] == "444555666"
    assert isinstance(data["book_id"], str)
    # `state` emitted via its `.value` string.
    assert data["state"] == "open"
    # `summary_status` (set) emitted via its `.value` string.
    assert data["summary_status"] == "approved"
    # Nullable strings (set) pass through.
    assert data["summary"] == "Backward-looking summary"
    assert data["system_prompt"] == "Chapter-scoped prompt"
    # version + ordinal ints pass through.
    assert data["version"] == 3
    assert data["ordinal"] == 7
    assert data["title"] == "Chapter Seven"
    assert data["sketch"] == "Forward-looking outline"
    assert data["text"] == "The main body prose"
    # Timestamps via isoformat strings.
    assert data["created_at"] == created_at.isoformat()
    assert data["modified_at"] == modified_at.isoformat()

    restored = _dict_to_chapter(data)

    # `id` / `book_id` parse back to the same ints.
    assert restored.id == 111222333
    assert isinstance(restored.id, int)
    assert restored.book_id == 444555666
    assert isinstance(restored.book_id, int)
    assert restored.ordinal == 7
    assert restored.title == "Chapter Seven"
    # `state` parses back to the enum member.
    assert restored.state is ChapterState.open
    assert restored.sketch == "Forward-looking outline"
    assert restored.text == "The main body prose"
    # Nullable summary/system_prompt (set) preserved.
    assert restored.summary == "Backward-looking summary"
    assert restored.system_prompt == "Chapter-scoped prompt"
    # `summary_status` (set) parses back to the enum member.
    assert restored.summary_status is SummaryStatus.approved
    assert restored.version == 3
    assert restored.created_at == created_at
    assert restored.modified_at == modified_at


# DoD-1: a minimal chapter (nullable summary / summary_status / system_prompt all
# None, default version=1) round-trips. The three nullables emit as None and
# restore to None; version defaults to 1 and is preserved; None timestamps stay
# None.
def test_chapter_codec_round_trips_null_shape__DoD1():
    chapter = Chapter(
        id=222333444,
        book_id=555666777,
        ordinal=0,
        title="Chapter One",
        state=ChapterState.planned,
        sketch="",
        text="",
        summary=None,
        summary_status=None,
        system_prompt=None,
        version=1,
        created_at=None,
        modified_at=None,
    )

    data = _chapter_to_dict(chapter)

    # Nullable summary_status (None) emitted as None.
    assert data["summary_status"] is None
    # Nullable summary/system_prompt (None) emitted as None.
    assert data["summary"] is None
    assert data["system_prompt"] is None
    # version default 1 emitted.
    assert data["version"] == 1
    assert data["ordinal"] == 0
    # None timestamps emitted as None.
    assert data["created_at"] is None
    assert data["modified_at"] is None

    restored = _dict_to_chapter(data)

    assert restored.id == 222333444
    assert restored.book_id == 555666777
    assert restored.ordinal == 0
    assert restored.title == "Chapter One"
    assert restored.state is ChapterState.planned
    # The three nullables restore to None.
    assert restored.summary is None
    assert restored.summary_status is None
    assert restored.system_prompt is None
    # version default 1 preserved.
    assert restored.version == 1
    assert restored.created_at is None
    assert restored.modified_at is None


# DoD-1: EVERY one of the four `state` values (planned, open, closing, closed)
# emits its `.value` string and parses back to the exact enum member — including
# `closing`, which lands now but is unused until Stage 4.
@pytest.mark.parametrize(
    "state",
    [
        ChapterState.planned,
        ChapterState.open,
        ChapterState.closing,
        ChapterState.closed,
    ],
)
def test_chapter_state_round_trips_every_value__DoD1(state: ChapterState):
    chapter = Chapter(
        id=333444555,
        book_id=666777888,
        ordinal=1,
        title="A chapter",
        state=state,
        sketch="s",
        text="t",
    )

    data = _chapter_to_dict(chapter)
    # Emitted as the enum's `.value` string.
    assert data["state"] == state.value

    restored = _dict_to_chapter(data)
    # Parsed back to the same enum member.
    assert restored.state is state


# DoD-1: EVERY one of the three `summary_status` values (draft, approved, stale)
# emits its `.value` string and parses back to the exact enum member (the set
# shape); complements the null shape covered above.
@pytest.mark.parametrize(
    "summary_status",
    [
        SummaryStatus.draft,
        SummaryStatus.approved,
        SummaryStatus.stale,
    ],
)
def test_chapter_summary_status_round_trips_every_value__DoD1(
    summary_status: SummaryStatus,
):
    chapter = Chapter(
        id=444555666,
        book_id=777888999,
        ordinal=2,
        title="Another chapter",
        state=ChapterState.closed,
        sketch="s",
        text="t",
        summary_status=summary_status,
    )

    data = _chapter_to_dict(chapter)
    assert data["summary_status"] == summary_status.value

    restored = _dict_to_chapter(data)
    assert restored.summary_status is summary_status


# ---------------------------------------------------------------------------
# DoD-2 — DB round-trip (create -> get_by_id + list_by_book filter)
# ---------------------------------------------------------------------------


# DoD-2: chapters.create(row) then get_by_id(row.id) returns an equal row.
# Required non-null fields (book_id, ordinal, title, state, sketch, text) are
# provided; version defaults to 1; the snowflake PK is populated on create.
async def test_chapters_db_round_trip__DoD2(db: DbConfig):
    row = Chapter(
        book_id=42,
        ordinal=3,
        title="Persisted Chapter",
        state=ChapterState.open,
        sketch="A sketch",
        text="Some body text",
    )

    created = await chapters.create(row)
    # Snowflake PK populated on the created row.
    assert created.id is not None

    fetched = await chapters.get_by_id(created.id)
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.book_id == 42
    assert fetched.ordinal == 3
    assert fetched.title == "Persisted Chapter"
    assert fetched.state is ChapterState.open
    assert fetched.sketch == "A sketch"
    assert fetched.text == "Some body text"
    # version defaults to 1.
    assert fetched.version == 1


# DoD-2: list_by_book(book_id) returns exactly that book's chapters. Chapters are
# inserted for two different book_ids and the filter selects only the matching
# book's rows.
async def test_chapters_list_by_book_filters__DoD2(db: DbConfig):
    ch_a = Chapter(
        book_id=10, ordinal=0, title="A0", state=ChapterState.planned, sketch="", text=""
    )
    ch_b = Chapter(
        book_id=10, ordinal=1, title="A1", state=ChapterState.open, sketch="", text=""
    )
    ch_other = Chapter(
        book_id=20, ordinal=0, title="B0", state=ChapterState.planned, sketch="", text=""
    )

    await chapters.create(ch_a)
    await chapters.create(ch_b)
    await chapters.create(ch_other)

    listed = await chapters.list_by_book(10)

    # Exactly book 10's chapters (both, and only those).
    assert {c.book_id for c in listed} == {10}
    assert {c.ordinal for c in listed} == {0, 1}
    assert len(listed) == 2


# ---------------------------------------------------------------------------
# DoD-3 — TABLE_REGISTRY order (canonical-restricted invariant)
# ---------------------------------------------------------------------------


# DoD-3: `chapters` appears in TABLE_REGISTRY, after `book_members`, and the label
# sequence equals the canonical order restricted to the tables present so far.
def test_table_registry_order__DoD3():
    labels = [entry[0] for entry in TABLE_REGISTRY]

    # The new chapters table is registered.
    assert "chapters" in labels

    # It appears after book_members (its FK parent block).
    assert labels.index("book_members") < labels.index("chapters")

    # The registry's label sequence equals the canonical order filtered down to
    # the tables actually present (canonical-restricted invariant).
    present = set(labels)
    expected_sequence = [name for name in CANONICAL_ORDER if name in present]
    assert labels == expected_sequence

    # The new tuple binds the correct model class.
    by_label = {entry[0]: entry for entry in TABLE_REGISTRY}
    assert by_label["chapters"][1] is Chapter


# ---------------------------------------------------------------------------
# DoD-4 — schema present + drift-clean consistency report
# ---------------------------------------------------------------------------


# DoD-4: after init_db() (the `db` fixture), `chapters` exists in
# SQLModel.metadata and the FEAT-005 consistency report is clean (every table
# entry has status "ok").
async def test_schema_present_and_drift_clean__DoD4(db: DbConfig):
    tables = SQLModel.metadata.tables
    assert "chapters" in tables

    report = await db_admin.build_consistency_report()
    by_name = {entry.name: entry for entry in report.tables}

    # The new table is reported and clean.
    assert by_name["chapters"].status == "ok"

    # A freshly-created DB matches metadata: no table drifts.
    for entry in report.tables:
        assert entry.status == "ok", f"table {entry.name!r} not clean: {entry.status}"
