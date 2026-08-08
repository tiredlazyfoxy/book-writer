"""Tests for the book aggregate root: Book + BookMember (feature 008, step 004).

Bound to the frozen skeleton signatures (status.md -> Skeleton -> Step 004):
    three enums in app.models.book:
        class CollaborationMode(str, enum.Enum) {free, proposal}
        class Visibility(str, enum.Enum) {private, public}
        class BookState(str, enum.Enum) {active, archived, quarantined, destroyed}
    class Book(SQLModel, table=True) __tablename__="books";
        id: int (snowflake PK), title: str, description: str,
        owner_id: int (FK users.id), collaboration_mode: CollaborationMode,
        visibility: Visibility, state: BookState,
        moderation_reason: str | None, moderated_by: int | None (FK users.id),
        moderated_at: datetime | None, system_prompt: str, active_notes: str,
        created_at: datetime | None, modified_at: datetime | None
                                                          in app.models.book
    class BookMember(SQLModel, table=True) __tablename__="book_members";
        UniqueConstraint(book_id, user_id);
        id: int (snowflake PK), book_id: int (FK books.id),
        user_id: int (FK users.id), role: str,
        created_at: datetime | None (ONE timestamp)      in app.models.book_member
    async def create(row: Book) -> Book                   in app.db.books
    async def get_by_id(book_id: int) -> Book | None      in app.db.books
    async def create(row: BookMember) -> BookMember       in app.db.book_members
    async def get_by_id(member_id: int) -> BookMember | None  in app.db.book_members
    async def list_by_book(book_id: int) -> list[BookMember]  in app.db.book_members
    def _book_to_dict / _dict_to_book                     in app.services.db_import_export
    def _book_member_to_dict / _dict_to_book_member       in app.services.db_import_export
    TABLE_REGISTRY: ("books", Book, ...) then
        ("book_members", BookMember, ...) at positions 8, 9 (after
        mode_subagents, before chapters)                  in app.services.db_import_export
    build_consistency_report() -> report with .tables entries each carrying
        .name / .status                                   in app.services.db_admin

Expected values come from the step spec (004.book-and-membership.md DoD +
004.context.md + context.md), never from implementation internals:
    - Book codec emits `id`/`owner_id` as strings parsed back to the same ints;
      each enum emits its `.value` string and parses back to the enum member;
      the nullable moderation triple + timestamps round-trip in BOTH the all-null
      (active book) and all-set (moderated book) shapes (DoD-1);
    - BookMember codec emits `id`/`book_id`/`user_id` as strings parsed back to
      ints; `role` and the single isoformat `created_at` are preserved (DoD-2);
    - db round-trip: create -> get_by_id returns an equal row for both tables and
      list_by_book returns exactly a book's members (DoD-3);
    - composite unique enforced: a second BookMember with the same
      (book_id, user_id) is rejected by the DB (DoD-4);
    - TABLE_REGISTRY lists books + book_members, each after mode_subagents, and
      the label sequence equals the canonical order restricted to present tables
      (DoD-5);
    - after init_db(), both tables exist in SQLModel.metadata and the FEAT-005
      consistency report is clean (DoD-6).

Async tests use asyncio_mode = "auto"; the `db` fixture (conftest) supplies an
initialized throwaway temp-SQLite engine with the registered tables created.
Pure-codec tests (DoD-1, DoD-2) and the registry test (DoD-5) need no DB.
SQLite does NOT enforce FKs by default, so book/member rows need no parent rows;
the composite-UNIQUE constraint (DoD-4) is enforced regardless.
"""

from datetime import datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import SQLModel

from app.db import assistant_modes, book_members, books
from app.db.engine import DbConfig
from app.models.book import Book, BookState, CollaborationMode, Visibility
from app.models.book_member import BookMember, MemberRole
from app.services import db_admin
from app.services.db_import_export import (
    TABLE_REGISTRY,
    _book_member_to_dict,
    _book_to_dict,
    _dict_to_book,
    _dict_to_book_member,
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
# DoD-1 — Book codec round-trip (id/owner_id string<->int, enums via .value,
#         nullable moderation triple in both all-null and all-set shapes)
# ---------------------------------------------------------------------------


# DoD-1: an ACTIVE book (state=active, all three moderation fields None) round-
# trips. `id`/`owner_id` emit as strings and parse back to the same ints; each
# enum emits its `.value` string and parses back to the enum member; the
# moderation triple stays None; required strings and isoformat timestamps
# survive.
def test_book_codec_round_trips_active_shape__DoD1():
    created_at = datetime(2026, 7, 25, 9, 0, 0)
    modified_at = datetime(2026, 7, 25, 9, 30, 0)
    book = Book(
        id=111222333,
        title="My Book",
        description="A description",
        owner_id=444555666,
        collaboration_mode=CollaborationMode.free,
        visibility=Visibility.private,
        state=BookState.active,
        moderation_reason=None,
        moderated_by=None,
        moderated_at=None,
        system_prompt="Book-wide prompt",
        active_notes="Some active notes",
        created_at=created_at,
        modified_at=modified_at,
    )

    data = _book_to_dict(book)

    # `id` / `owner_id` emitted as strings.
    assert data["id"] == "111222333"
    assert isinstance(data["id"], str)
    assert data["owner_id"] == "444555666"
    assert isinstance(data["owner_id"], str)
    # Enums emitted via their `.value` strings.
    assert data["collaboration_mode"] == "free"
    assert data["visibility"] == "private"
    assert data["state"] == "active"
    # The moderation triple stays null on an active book.
    assert data["moderation_reason"] is None
    assert data["moderated_by"] is None
    assert data["moderated_at"] is None
    # Timestamps via isoformat strings.
    assert data["created_at"] == created_at.isoformat()
    assert data["modified_at"] == modified_at.isoformat()

    restored = _dict_to_book(data)

    # `id` / `owner_id` parse back to the same ints.
    assert restored.id == 111222333
    assert isinstance(restored.id, int)
    assert restored.owner_id == 444555666
    assert isinstance(restored.owner_id, int)
    assert restored.title == "My Book"
    assert restored.description == "A description"
    # Enums parse back to the enum members.
    assert restored.collaboration_mode is CollaborationMode.free
    assert restored.visibility is Visibility.private
    assert restored.state is BookState.active
    # Null moderation triple preserved.
    assert restored.moderation_reason is None
    assert restored.moderated_by is None
    assert restored.moderated_at is None
    assert restored.system_prompt == "Book-wide prompt"
    assert restored.active_notes == "Some active notes"
    assert restored.created_at == created_at
    assert restored.modified_at == modified_at


# DoD-1: a MODERATED book (state=quarantined, all three moderation fields set)
# round-trips. The `state` enum emits/parses as "quarantined"; the moderation
# reason string is preserved; the nullable FK `moderated_by` emits as a STRING
# (id-as-string, like owner_id) and parses back to the same int; the isoformat
# `moderated_at` is preserved; the other two enums still round-trip.
def test_book_codec_round_trips_moderated_shape__DoD1():
    moderated_at = datetime(2026, 7, 25, 12, 0, 0)
    book = Book(
        id=222333444,
        title="Flagged Book",
        description="Under review",
        owner_id=555666777,
        collaboration_mode=CollaborationMode.proposal,
        visibility=Visibility.public,
        state=BookState.quarantined,
        moderation_reason="Reported for spam",
        moderated_by=999888777,
        moderated_at=moderated_at,
        system_prompt="",
        active_notes="",
        created_at=None,
        modified_at=None,
    )

    data = _book_to_dict(book)

    # The second enum-value set.
    assert data["collaboration_mode"] == "proposal"
    assert data["visibility"] == "public"
    assert data["state"] == "quarantined"
    # The moderation triple is populated: reason string, `moderated_by` emitted
    # as a STRING (nullable FK to users.id — id-as-string, like owner_id),
    # isoformat moderated_at.
    assert data["moderation_reason"] == "Reported for spam"
    assert data["moderated_by"] == "999888777"
    assert isinstance(data["moderated_by"], str)
    assert data["moderated_at"] == moderated_at.isoformat()

    restored = _dict_to_book(data)

    assert restored.id == 222333444
    assert restored.collaboration_mode is CollaborationMode.proposal
    assert restored.visibility is Visibility.public
    assert restored.state is BookState.quarantined
    assert restored.moderation_reason == "Reported for spam"
    assert restored.moderated_by == 999888777
    assert isinstance(restored.moderated_by, int)
    assert restored.moderated_at == moderated_at


# ---------------------------------------------------------------------------
# DoD-2 — BookMember codec round-trip (ids string<->int, role + one timestamp)
# ---------------------------------------------------------------------------


# DoD-2: _book_member_to_dict emits `id`/`book_id`/`user_id` as STRINGS;
# _dict_to_book_member parses all three back to the SAME ints; `role` is
# preserved; the single `created_at` round-trips via isoformat.
def test_book_member_codec_round_trips_all_fields__DoD2():
    created_at = datetime(2026, 7, 25, 8, 15, 0)
    member = BookMember(
        id=101010101,
        book_id=202020202,
        user_id=303030303,
        role=MemberRole.co_author,
        created_at=created_at,
    )

    data = _book_member_to_dict(member)

    assert data["id"] == "101010101"
    assert isinstance(data["id"], str)
    assert data["book_id"] == "202020202"
    assert isinstance(data["book_id"], str)
    assert data["user_id"] == "303030303"
    assert isinstance(data["user_id"], str)
    assert data["role"] == MemberRole.co_author.value
    assert data["created_at"] == created_at.isoformat()

    restored = _dict_to_book_member(data)

    assert restored.id == 101010101
    assert isinstance(restored.id, int)
    assert restored.book_id == 202020202
    assert isinstance(restored.book_id, int)
    assert restored.user_id == 303030303
    assert isinstance(restored.user_id, int)
    assert restored.role == MemberRole.co_author
    assert restored.created_at == created_at


# ---------------------------------------------------------------------------
# DoD-3 — DB round-trip (create -> get_by_id + list_by_book filter)
# ---------------------------------------------------------------------------


# DoD-3: books.create(row) then get_by_id(row.id) returns an equal row. Required
# non-null fields (title, description, owner_id, the three enums, system_prompt,
# active_notes) are provided; the snowflake PK is populated on create.
async def test_books_db_round_trip__DoD3(db: DbConfig):
    row = Book(
        title="Persisted Book",
        description="Stored to SQLite",
        owner_id=42,
        collaboration_mode=CollaborationMode.proposal,
        visibility=Visibility.public,
        state=BookState.active,
        system_prompt="A prompt",
        active_notes="Notes",
    )

    created = await books.create(row)
    # Snowflake PK populated on the created row.
    assert created.id is not None

    fetched = await books.get_by_id(created.id)
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.title == "Persisted Book"
    assert fetched.description == "Stored to SQLite"
    assert fetched.owner_id == 42
    assert fetched.collaboration_mode is CollaborationMode.proposal
    assert fetched.visibility is Visibility.public
    assert fetched.state is BookState.active
    assert fetched.system_prompt == "A prompt"
    assert fetched.active_notes == "Notes"


# DoD-3: book_members.create(row) then get_by_id(row.id) returns an equal row;
# and list_by_book(book_id) returns exactly that book's members (members are
# inserted for two different book_ids and the filter selects only one book's).
async def test_book_members_db_round_trip_and_list__DoD3(db: DbConfig):
    member_a = BookMember(book_id=10, user_id=1, role=MemberRole.co_author)
    member_b = BookMember(book_id=10, user_id=2, role=MemberRole.co_author)
    member_other = BookMember(book_id=20, user_id=1, role=MemberRole.co_author)

    created_a = await book_members.create(member_a)
    await book_members.create(member_b)
    await book_members.create(member_other)

    # Snowflake PK populated on the created row.
    assert created_a.id is not None

    fetched = await book_members.get_by_id(created_a.id)
    assert fetched is not None
    assert fetched.id == created_a.id
    assert fetched.book_id == 10
    assert fetched.user_id == 1
    assert fetched.role == MemberRole.co_author

    # list_by_book returns exactly book 10's members (both, and only those).
    listed = await book_members.list_by_book(10)
    assert {m.book_id for m in listed} == {10}
    assert {m.user_id for m in listed} == {1, 2}
    assert len(listed) == 2


# ---------------------------------------------------------------------------
# DoD-4 — composite unique enforced (second same (book_id, user_id) rejected)
# ---------------------------------------------------------------------------


# DoD-4: a second BookMember with the same (book_id, user_id) pair is rejected by
# the DB. The two rows differ only by the auto surrogate id.
async def test_book_member_composite_unique_enforced__DoD4(db: DbConfig):
    await book_members.create(BookMember(book_id=10, user_id=1, role=MemberRole.co_author))

    with pytest.raises(IntegrityError):
        await book_members.create(BookMember(book_id=10, user_id=1, role=MemberRole.co_author))


# ---------------------------------------------------------------------------
# DoD-5 — TABLE_REGISTRY order (canonical-restricted invariant)
# ---------------------------------------------------------------------------


# DoD-5: books and book_members appear in TABLE_REGISTRY, each after
# mode_subagents, and the label sequence equals the canonical order restricted to
# the tables present so far.
def test_table_registry_order__DoD5():
    labels = [entry[0] for entry in TABLE_REGISTRY]

    # Both new book tables are registered.
    assert "books" in labels
    assert "book_members" in labels

    # Each appears after mode_subagents (end of the FEAT-020 config block).
    mode_subagents_idx = labels.index("mode_subagents")
    assert mode_subagents_idx < labels.index("books")
    assert mode_subagents_idx < labels.index("book_members")

    # Canonical order among the two: books, then book_members.
    assert labels.index("books") < labels.index("book_members")

    # The registry's label sequence equals the canonical order filtered down to
    # the tables actually present (canonical-restricted invariant).
    present = set(labels)
    expected_sequence = [name for name in CANONICAL_ORDER if name in present]
    assert labels == expected_sequence

    # The two new tuples bind the correct model classes.
    by_label = {entry[0]: entry for entry in TABLE_REGISTRY}
    assert by_label["books"][1] is Book
    assert by_label["book_members"][1] is BookMember


# ---------------------------------------------------------------------------
# DoD-6 — schema present + drift-clean consistency report
# ---------------------------------------------------------------------------


# DoD-6: after init_db() (the `db` fixture), books and book_members exist in
# SQLModel.metadata and the FEAT-005 consistency report is clean (every table
# entry has status "ok").
async def test_schema_present_and_drift_clean__DoD6(db: DbConfig):
    tables = SQLModel.metadata.tables
    assert "books" in tables
    assert "book_members" in tables

    # Feedback round 1, F1: `assistant_modes` is the seed registry's single
    # entry, so a present, schema-clean but rowless table now reports
    # `seed-missing` — init_db() alone leaves the DB schema-clean but not
    # row-complete. This test's subject is a fully consistent database, so the
    # required rows are arranged first; every per-table assertion below is
    # unchanged.
    await assistant_modes.seed_default_modes()

    report = await db_admin.build_consistency_report()
    by_name = {entry.name: entry for entry in report.tables}

    # The two new tables are reported and clean.
    assert by_name["books"].status == "ok"
    assert by_name["book_members"].status == "ok"

    # A freshly-created DB matches metadata: no table drifts.
    for entry in report.tables:
        assert entry.status == "ok", f"table {entry.name!r} not clean: {entry.status}"
