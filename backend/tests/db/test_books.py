"""Tests for the session-free db/books extensions (feature 009, step 001).

Bound to the frozen skeleton signatures (status.md -> Skeleton -> Step 001):
    async def update(row: Book) -> None                    in app.db.books
    async def list_by_owner(owner_id: int) -> list[Book]   in app.db.books
    async def list_shared(user_id: int) -> list[Book]      in app.db.books
    async def create(row: Book) -> Book                    in app.db.books (008)
    async def get_by_id(book_id: int) -> Book | None       in app.db.books (008)
    async def create(row: BookMember) -> BookMember        in app.db.book_members (008)
    class Book(SQLModel, table=True)                       in app.models.book
    class BookMember(SQLModel, table=True)                 in app.models.book_member
    class MemberRole(str, enum.Enum) {co_author}           in app.models.book_member

Expected values come from the step spec (001.db-layer-extensions.md DoD +
001.context.md + context.md), never from implementation internals:
    - DoD-3: update(row) persists field changes to an existing row; a subsequent
      get_by_id returns the new values;
    - DoD-4: list_by_owner returns exactly the books whose owner_id matches the
      given user and none owned by others;
    - DoD-5: list_shared returns exactly the books where the user is a co-author
      and NOT the owner — excluding books they own (even if a membership row
      exists for one) and books they have no membership in.

Async tests use asyncio_mode = "auto"; the `db` fixture (conftest) supplies an
initialized throwaway temp-SQLite engine with the registered tables created.
SQLite does not enforce FKs by default, so book/member rows need no parent rows.
"""

from app.db import book_members, books
from app.db.engine import DbConfig
from app.models.book import Book, BookState, CollaborationMode, Visibility
from app.models.book_member import BookMember, MemberRole


def _make_book(
    *,
    title: str,
    owner_id: int,
    description: str = "desc",
    visibility: Visibility = Visibility.private,
    state: BookState = BookState.active,
    collaboration_mode: CollaborationMode = CollaborationMode.free,
) -> Book:
    """A Book with every required non-null field set (id assigned on construct)."""
    return Book(
        title=title,
        description=description,
        owner_id=owner_id,
        collaboration_mode=collaboration_mode,
        visibility=visibility,
        state=state,
        system_prompt="",
        active_notes="",
    )


# ---------------------------------------------------------------------------
# DoD-3 — update persists field changes; get_by_id returns the new values
# ---------------------------------------------------------------------------


# DoD-3: books.update(row) persists changes to an existing Book row, and a
# subsequent get_by_id returns the new values (title, description, visibility,
# state all changed on the caller-mutated row).
async def test_update_persists_field_changes__DoD3(db: DbConfig):
    created = await books.create(
        _make_book(
            title="Original",
            owner_id=42,
            description="Original description",
            visibility=Visibility.private,
            state=BookState.active,
        )
    )
    assert created.id is not None

    # The caller mutates the existing row and hands it to update().
    created.title = "Renamed"
    created.description = "New description"
    created.visibility = Visibility.public
    created.state = BookState.archived
    await books.update(created)

    fetched = await books.get_by_id(created.id)
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.title == "Renamed"
    assert fetched.description == "New description"
    assert fetched.visibility is Visibility.public
    assert fetched.state is BookState.archived


# ---------------------------------------------------------------------------
# DoD-4 — list_by_owner returns exactly the given owner's books
# ---------------------------------------------------------------------------


# DoD-4: list_by_owner(owner_id) returns exactly the books whose owner_id matches
# the given user, and none owned by others.
async def test_list_by_owner_returns_only_that_owners_books__DoD4(db: DbConfig):
    a1 = await books.create(_make_book(title="A1", owner_id=100))
    a2 = await books.create(_make_book(title="A2", owner_id=100))
    other = await books.create(_make_book(title="B1", owner_id=200))

    owned = await books.list_by_owner(100)
    owned_ids = {b.id for b in owned}

    # Exactly the owner-100 books, and none owned by 200.
    assert owned_ids == {a1.id, a2.id}
    assert other.id not in owned_ids
    assert all(b.owner_id == 100 for b in owned)


# ---------------------------------------------------------------------------
# DoD-5 — list_shared returns exactly co-author-not-owner books
# ---------------------------------------------------------------------------


# DoD-5: list_shared(user_id) returns exactly the books where the user is a
# co-author and NOT the owner. It excludes: (a) a book the user owns even when a
# membership row exists for it, (b) a book the user has no membership in, and
# (c) a book whose only member is someone else.
async def test_list_shared_returns_only_comember_nonowned_books__DoD5(db: DbConfig):
    user = 42
    owner_one = 100
    owner_two = 200

    shared = await books.create(_make_book(title="Shared", owner_id=owner_one))
    owned_by_user = await books.create(_make_book(title="OwnedByUser", owner_id=user))
    no_membership = await books.create(_make_book(title="NoMembership", owner_id=owner_two))
    other_member = await books.create(_make_book(title="OtherMember", owner_id=owner_one))

    # The user co-authors `shared` -> must appear.
    await book_members.create(
        BookMember(book_id=shared.id, user_id=user, role=MemberRole.co_author)
    )
    # A membership row also exists for a book the user OWNS -> must be excluded.
    await book_members.create(
        BookMember(book_id=owned_by_user.id, user_id=user, role=MemberRole.co_author)
    )
    # `other_member` has a member who is not the user -> must be excluded for the user.
    await book_members.create(
        BookMember(book_id=other_member.id, user_id=99, role=MemberRole.co_author)
    )

    result = await books.list_shared(user)
    result_ids = {b.id for b in result}

    # Exactly the book the user co-authors and does not own.
    assert result_ids == {shared.id}
    assert owned_by_user.id not in result_ids
    assert no_membership.id not in result_ids
    assert other_member.id not in result_ids
