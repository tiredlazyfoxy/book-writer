"""Tests for the book-scoped authorization spine (feature 009, step 002).

Bound to the frozen skeleton signatures (status.md -> Skeleton -> Step 002),
in `app.services.authz`:
    class AccessRole(str, enum.Enum)  {owner, co_author, reader, none}
    class Capability(str, enum.Enum)  {read_book, view_book_detail,
        archive_book, transfer_ownership, add_member, remove_member,
        set_visibility}
    @dataclass(frozen=True) class BookAccess  fields:
        book_id: int, user_id: int, role: AccessRole, book_state: BookState,
        visibility: Visibility, collaboration_mode: CollaborationMode
    class BookAuthorizationError(Exception)  __init__(capability, role)
    async def resolve_book_access(book_id: int, user: User) -> BookAccess
        (raises HTTPException 404 on missing book or role == none)
    def require(access: BookAccess, capability: Capability) -> None
        (raises BookAuthorizationError when role not permitted)

Expected values come from the step spec (002.authorization-spine.md DoD +
002.context.md + context.md), never from implementation internals:
    - resolve resolves owner (owner_id == user.id) and co_author (a membership
      row exists) on a private book (DoD-1);
    - resolve resolves reader for a logged-in non-member on a PUBLIC book
      (DoD-2);
    - resolve raises 404 for a logged-in non-member on a PRIVATE book — existence
      hiding, not 403 (DoD-3);
    - resolve raises 404 for a non-existent book_id (DoD-4);
    - resolve carries book_state / visibility / collaboration_mode through from
      the book row onto the returned BookAccess (DoD-5);
    - require returns None when the role is in the matrix's allowed set and
      raises BookAuthorizationError otherwise. Matrix (frozen policy):
      read_book -> {owner, co_author, reader}; view_book_detail ->
      {owner, co_author}; every mutation (archive_book, transfer_ownership,
      add_member, remove_member, set_visibility) -> {owner} only
      (DoD-6, DoD-7).

Async resolve tests use asyncio_mode = "auto"; the `db` fixture (conftest)
supplies an initialized throwaway temp-SQLite engine. Book / BookMember rows are
seeded directly (008 test_data_domain style) and a seeded User is passed — no
HTTP round-trip. The `require` tests construct BookAccess directly (frozen
dataclass) with a chosen role, so they do not depend on resolve.
"""

import pytest
from fastapi import HTTPException

from app.db import book_members, books, users
from app.db.engine import DbConfig
from app.models.book import Book, BookState, CollaborationMode, Visibility
from app.models.book_member import BookMember, MemberRole
from app.models.user import User, UserRole
from app.services.authz import (
    AccessRole,
    BookAccess,
    BookAuthorizationError,
    Capability,
    require,
    resolve_book_access,
)


# ---------------------------------------------------------------------------
# Seeding helpers (008 test_data_domain style: construct rows directly).
# ---------------------------------------------------------------------------


async def _seed_user(username: str) -> User:
    """Create and return a persisted author User (populated snowflake id)."""
    return await users.create(User(username=username, role=UserRole.author))


async def _seed_book(
    owner_id: int,
    *,
    visibility: Visibility,
    state: BookState = BookState.active,
    collaboration_mode: CollaborationMode = CollaborationMode.free,
) -> Book:
    """Create and return a persisted Book owned by `owner_id`."""
    return await books.create(
        Book(
            title="A Book",
            description="Its description",
            owner_id=owner_id,
            collaboration_mode=collaboration_mode,
            visibility=visibility,
            state=state,
            system_prompt="",
            active_notes="",
        )
    )


def _access(role: AccessRole) -> BookAccess:
    """A BookAccess with the given role, built directly (no resolve).

    The non-role fields are spec-required BookAccess members but are irrelevant
    to the capability decision, which keys only on `role`.
    """
    return BookAccess(
        book_id=1,
        user_id=2,
        role=role,
        book_state=BookState.active,
        visibility=Visibility.private,
        collaboration_mode=CollaborationMode.free,
    )


# ---------------------------------------------------------------------------
# DoD-1 — owner and co_author resolve on a PRIVATE book
# ---------------------------------------------------------------------------


# DoD-1: resolve_book_access returns role == owner for the book's owner and
# role == co_author for a co-author (a membership row exists), on a PRIVATE
# book. (US-029.AC-2.)
async def test_resolve_owner_and_co_author_on_private_book__DoD1(db: DbConfig):
    owner = await _seed_user("owner_user")
    coauthor = await _seed_user("coauthor_user")
    book = await _seed_book(owner.id, visibility=Visibility.private)
    await book_members.create(
        BookMember(book_id=book.id, user_id=coauthor.id, role=MemberRole.co_author)
    )

    owner_access = await resolve_book_access(book.id, owner)
    assert owner_access.role == AccessRole.owner

    coauthor_access = await resolve_book_access(book.id, coauthor)
    assert coauthor_access.role == AccessRole.co_author


# ---------------------------------------------------------------------------
# DoD-2 — reader resolves for a logged-in non-member on a PUBLIC book
# ---------------------------------------------------------------------------


# DoD-2: resolve_book_access returns role == reader for a logged-in non-member
# on a PUBLIC book. (US-030.AC-1.)
async def test_resolve_reader_on_public_book_for_non_member__DoD2(db: DbConfig):
    owner = await _seed_user("owner_user")
    stranger = await _seed_user("stranger_user")
    book = await _seed_book(owner.id, visibility=Visibility.public)

    access = await resolve_book_access(book.id, stranger)
    assert access.role == AccessRole.reader


# ---------------------------------------------------------------------------
# DoD-3 — 404 for a logged-in non-member on a PRIVATE book (existence hiding)
# ---------------------------------------------------------------------------


# DoD-3: resolve_book_access raises 404 (HTTPException.status_code == 404) for a
# logged-in non-member on a PRIVATE book — existence hiding, not 403.
# (US-030.AC-3.)
async def test_resolve_raises_404_for_non_member_on_private_book__DoD3(db: DbConfig):
    owner = await _seed_user("owner_user")
    stranger = await _seed_user("stranger_user")
    book = await _seed_book(owner.id, visibility=Visibility.private)

    with pytest.raises(HTTPException) as exc_info:
        await resolve_book_access(book.id, stranger)

    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# DoD-4 — 404 for a non-existent book_id
# ---------------------------------------------------------------------------


# DoD-4: resolve_book_access raises 404 for a non-existent book_id.
# (authorization.md -> "Failure modes"; existence hiding.)
async def test_resolve_raises_404_for_missing_book__DoD4(db: DbConfig):
    user = await _seed_user("some_user")
    missing_book_id = 999999999

    with pytest.raises(HTTPException) as exc_info:
        await resolve_book_access(missing_book_id, user)

    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# DoD-5 — BookAccess carries book_state / visibility / collaboration_mode
# ---------------------------------------------------------------------------


# DoD-5: resolve_book_access populates book_state, visibility and
# collaboration_mode on the returned BookAccess from the book row. Distinct
# non-default values are seeded so a carried-through value cannot be confused
# with a default.
async def test_resolve_carries_book_fields_through__DoD5(db: DbConfig):
    owner = await _seed_user("owner_user")
    book = await _seed_book(
        owner.id,
        visibility=Visibility.public,
        state=BookState.archived,
        collaboration_mode=CollaborationMode.proposal,
    )

    access = await resolve_book_access(book.id, owner)

    assert access.book_state == BookState.archived
    assert access.visibility == Visibility.public
    assert access.collaboration_mode == CollaborationMode.proposal


# ---------------------------------------------------------------------------
# DoD-6 — require permits permitted roles, denies the rest
# ---------------------------------------------------------------------------


# DoD-6: require returns None when the role is permitted — owner for a mutation
# capability (owner-only row), reader for read_book — and raises
# BookAuthorizationError when it is not: a co-author or a reader attempting an
# owner-only capability. (Guards US-024.AC-1, US-025.AC-1, US-027.AC-1,
# US-028.AC-1, US-029.AC-1.)
def test_require_owner_permitted_for_mutation__DoD6():
    assert require(_access(AccessRole.owner), Capability.archive_book) is None


def test_require_reader_permitted_for_read_book__DoD6():
    assert require(_access(AccessRole.reader), Capability.read_book) is None


def test_require_co_author_denied_owner_only_capability__DoD6():
    with pytest.raises(BookAuthorizationError):
        require(_access(AccessRole.co_author), Capability.archive_book)


def test_require_reader_denied_owner_only_capability__DoD6():
    with pytest.raises(BookAuthorizationError):
        require(_access(AccessRole.reader), Capability.archive_book)


# ---------------------------------------------------------------------------
# DoD-7 — view_book_detail is members-only (denies reader, permits owner/co_author)
# ---------------------------------------------------------------------------


# DoD-7: require(access, Capability.view_book_detail) denies a reader
# (members-only detail) and permits owner and co_author. (US-030.AC-2 — a reader
# is given no members/settings surface.)
def test_require_view_book_detail_denies_reader__DoD7():
    with pytest.raises(BookAuthorizationError):
        require(_access(AccessRole.reader), Capability.view_book_detail)


def test_require_view_book_detail_permits_owner_and_co_author__DoD7():
    assert require(_access(AccessRole.owner), Capability.view_book_detail) is None
    assert require(_access(AccessRole.co_author), Capability.view_book_detail) is None
