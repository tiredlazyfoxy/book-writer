"""Tests for the session-free db/book_members extensions + MemberRole enum
(feature 009, step 001).

Bound to the frozen skeleton signatures (status.md -> Skeleton -> Step 001):
    class MemberRole(str, enum.Enum) with sole member co_author = "co_author"
                                                          in app.models.book_member
    class BookMember(SQLModel, table=True); role: MemberRole
                                                          in app.models.book_member
    async def get_by_book_and_user(book_id: int, user_id: int) -> BookMember | None
                                                          in app.db.book_members
    async def delete(book_id: int, user_id: int) -> bool  in app.db.book_members
    async def list_by_user(user_id: int) -> list[BookMember]
                                                          in app.db.book_members
    async def create(row: BookMember) -> BookMember       in app.db.book_members (008)
    async def get_by_id(member_id: int) -> BookMember | None
                                                          in app.db.book_members (008)

Expected values come from the step spec (001.db-layer-extensions.md DoD +
context), never from implementation internals:
    - DoD-1: MemberRole is a (str, Enum) with the single value co_author, and a
      member row created and read back preserves the enum value;
    - DoD-6: get_by_book_and_user returns the matching row for a member pair and
      None for a non-member pair;
    - DoD-7: delete removes the membership for a (book_id, user_id) pair and
      reports removal; a second delete of the same pair reports no-op (and it
      keys on the pair, not the surrogate id — other members survive);
    - DoD-8: list_by_user returns every membership row for a user.

Per the step brief: role round-trip is asserted by VALUE equality against
MemberRole.co_author (the enum member is a str subclass equal to "co_author").

Async tests use asyncio_mode = "auto"; the `db` fixture (conftest) supplies an
initialized throwaway temp-SQLite engine with the registered tables created.
SQLite does not enforce FKs by default, so member rows need no parent rows.
"""

import enum

from app.db import book_members
from app.db.engine import DbConfig
from app.models.book_member import BookMember, MemberRole


# ---------------------------------------------------------------------------
# DoD-1 — MemberRole shape + role enum value preserved through the DB
# ---------------------------------------------------------------------------


# DoD-1: MemberRole is a (str, Enum) whose sole value is co_author.
def test_member_role_is_str_enum_with_single_value__DoD1():
    assert issubclass(MemberRole, str)
    assert issubclass(MemberRole, enum.Enum)
    assert MemberRole.co_author.value == "co_author"
    # The enum carries exactly one member.
    assert [m.value for m in MemberRole] == ["co_author"]


# DoD-1: a BookMember created with role=MemberRole.co_author and read back
# preserves the role value (value equality against MemberRole.co_author).
async def test_member_row_preserves_role_enum_value__DoD1(db: DbConfig):
    created = await book_members.create(
        BookMember(book_id=10, user_id=1, role=MemberRole.co_author)
    )
    assert created.id is not None

    fetched = await book_members.get_by_id(created.id)
    assert fetched is not None
    assert fetched.role == MemberRole.co_author


# ---------------------------------------------------------------------------
# DoD-6 — get_by_book_and_user: match for a member pair, None otherwise
# ---------------------------------------------------------------------------


# DoD-6: get_by_book_and_user(book_id, user_id) returns the matching BookMember
# for a member pair, and None for a non-member pair.
async def test_get_by_book_and_user_returns_match_and_none__DoD6(db: DbConfig):
    await book_members.create(
        BookMember(book_id=10, user_id=1, role=MemberRole.co_author)
    )

    match = await book_members.get_by_book_and_user(10, 1)
    assert match is not None
    assert match.book_id == 10
    assert match.user_id == 1
    assert match.role == MemberRole.co_author

    # Non-member pairs (wrong user, wrong book) both resolve to None.
    assert await book_members.get_by_book_and_user(10, 999) is None
    assert await book_members.get_by_book_and_user(999, 1) is None


# ---------------------------------------------------------------------------
# DoD-7 — delete removes the pair, reports removal, no-ops on second delete
# ---------------------------------------------------------------------------


# DoD-7: delete(book_id, user_id) removes the membership for that pair and returns
# True; it keys on the pair (a different member of the same book survives); a
# second delete of the same pair returns False (no-op).
async def test_delete_removes_pair_reports_and_noops__DoD7(db: DbConfig):
    await book_members.create(
        BookMember(book_id=10, user_id=1, role=MemberRole.co_author)
    )
    # A different member of the SAME book — must survive the targeted delete.
    await book_members.create(
        BookMember(book_id=10, user_id=2, role=MemberRole.co_author)
    )

    # Deleting the existing pair reports removal...
    assert await book_members.delete(10, 1) is True
    # ...and that pair is gone afterwards.
    assert await book_members.get_by_book_and_user(10, 1) is None
    # ...while the other member (keyed on its own pair) is untouched.
    survivor = await book_members.get_by_book_and_user(10, 2)
    assert survivor is not None

    # A second delete of the same pair is a no-op.
    assert await book_members.delete(10, 1) is False


# ---------------------------------------------------------------------------
# DoD-8 — list_by_user returns every membership row for a user
# ---------------------------------------------------------------------------


# DoD-8: list_by_user(user_id) returns every membership row for that user, and
# none belonging to other users.
async def test_list_by_user_returns_every_membership_for_user__DoD8(db: DbConfig):
    await book_members.create(
        BookMember(book_id=10, user_id=1, role=MemberRole.co_author)
    )
    await book_members.create(
        BookMember(book_id=20, user_id=1, role=MemberRole.co_author)
    )
    # A membership for a different user — must not appear in user 1's list.
    await book_members.create(
        BookMember(book_id=10, user_id=2, role=MemberRole.co_author)
    )

    listed = await book_members.list_by_user(1)

    assert {m.book_id for m in listed} == {10, 20}
    assert all(m.user_id == 1 for m in listed)
    assert len(listed) == 2
