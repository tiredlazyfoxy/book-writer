"""Service-layer tests for the reader surface (feature 022, ultra track).

Covers exactly two of the plan's nine `[test]` items — DoD-1 and DoD-6. The five
HTTP-observable items (DoD-2, DoD-3, DoD-4, DoD-5, DoD-7) live in
`tests/routes/test_reader.py`.

Bound to the frozen skeleton (status.md -> `## Skeleton`):

    app.services.reader
        READER_VISIBLE_STATES: frozenset[ChapterState]
        async def get_reader_book(access: BookAccess) -> ReaderBookResponse
        async def get_reader_chapter(access: BookAccess, chapter_id: str)
            -> ReaderChapterResponse
        async def list_public_books(caller: User) -> PublicBookListResponse

    app.models.schemas.reader
        ReaderChapterRef        -- id: str, title: str
        ReaderBookResponse      -- title: str, chapters: list[ReaderChapterRef]
        PublicBookRef           -- id: str, title: str, description: str
        PublicBookListResponse  -- items: list[PublicBookRef]

    plus the frozen `authz.BookAccess` (a dataclass constructed directly here,
    as tests/services/test_book_author_prompts.py does) and the delivered
    `app.db.books` / `app.db.book_members` / `app.db.chapters` / `app.db.users`.

Expected values come from the SPEC ONLY -- `plan.md`'s Definition of done,
`## Decisions taken` (D2, D14) and `context.md` -- never from implementation
internals:

    - DoD-1 (US-030.AC-1, D2): the table of contents holds exactly the book's
      `open` and `closed` chapters, in ascending `ordinal` order; `planned` and
      `closing` chapters are absent. Rows are seeded in a scrambled insertion
      order so a wrong sort cannot pass by accident.
    - DoD-6 (UC-029, D14): `list_public_books` excludes the caller's own books,
      books they co-author, private books and non-`active` books, and includes
      another user's `active` `public` book.

Async tests use asyncio_mode = "auto"; the `db` fixture (conftest) supplies an
initialized throwaway temp-SQLite engine. No route, no HTTP client, no JWT at
this layer.
"""

from app.db import book_members, books, chapters as chapters_db, users
from app.db.engine import DbConfig
from app.models.book import Book, BookState, CollaborationMode, Visibility
from app.models.book_member import BookMember, MemberRole
from app.models.chapter import Chapter, ChapterState
from app.models.user import User, UserRole
from app.services import reader as reader_service
from app.services.authz import AccessRole, BookAccess


# ---------------------------------------------------------------------------
# Seeding helpers (services-test style: rows through the db layer, access
# context constructed directly).
# ---------------------------------------------------------------------------


async def _seed_user(username: str) -> User:
    return await users.create(User(username=username, role=UserRole.author))


async def _seed_book(
    *,
    title: str,
    owner_id: int,
    description: str = "desc",
    visibility: Visibility = Visibility.public,
    state: BookState = BookState.active,
) -> Book:
    return await books.create(
        Book(
            title=title,
            description=description,
            owner_id=owner_id,
            collaboration_mode=CollaborationMode.free,
            visibility=visibility,
            state=state,
            system_prompt="",
            active_notes="",
        )
    )


async def _seed_chapter(
    book_id: int,
    *,
    ordinal: int,
    title: str,
    state: ChapterState,
    text: str = "the saved body",
) -> Chapter:
    return await chapters_db.create(
        Chapter(
            book_id=book_id,
            ordinal=ordinal,
            title=title,
            state=state,
            sketch="working material a reader must never see",
            text=text,
            version=1,
        )
    )


async def _add_co_author(book_id: int, user_id: int) -> None:
    await book_members.create(
        BookMember(book_id=book_id, user_id=user_id, role=MemberRole.co_author)
    )


def _access(
    book_id: int,
    user_id: int,
    *,
    role: AccessRole = AccessRole.reader,
    visibility: Visibility = Visibility.public,
) -> BookAccess:
    """The access context the `book_access` dependency would have resolved."""
    return BookAccess(
        book_id=book_id,
        user_id=user_id,
        role=role,
        book_state=BookState.active,
        visibility=visibility,
        collaboration_mode=CollaborationMode.free,
    )


# ---------------------------------------------------------------------------
# DoD-1 — the TOC is exactly {open, closed}, ascending by ordinal
# ---------------------------------------------------------------------------


# DoD-1 (US-030.AC-1, D2): the table of contents contains exactly the book's
# `open` and `closed` chapters, in ascending `ordinal` order; `planned` and
# `closing` chapters are absent. The rows are inserted out of ordinal order
# (3, 5, 1, 4, 2) so insertion order and ordinal order disagree, and a missing
# sort cannot pass by accident.
async def test_toc_is_open_and_closed_in_ordinal_order__DoD1_US030_AC1(db: DbConfig):
    owner = await _seed_user("alice")
    caller = await _seed_user("bob")
    book = await _seed_book(title="The Winds of Winter", owner_id=owner.id)

    third_closed = await _seed_chapter(
        book.id, ordinal=3, title="The Long Retreat", state=ChapterState.closed
    )
    fifth_open = await _seed_chapter(
        book.id, ordinal=5, title="Dawn Over the Wall", state=ChapterState.open
    )
    first_open = await _seed_chapter(
        book.id, ordinal=1, title="The Ravens Depart", state=ChapterState.open
    )
    fourth_planned = await _seed_chapter(
        book.id, ordinal=4, title="An Unwritten Beat", state=ChapterState.planned
    )
    second_closing = await _seed_chapter(
        book.id, ordinal=2, title="Mid-Close At Castle Black", state=ChapterState.closing
    )

    result = await reader_service.get_reader_book(_access(book.id, caller.id))

    assert result.title == "The Winds of Winter"

    # Exactly the open + closed chapters, ascending by ordinal (1, 3, 5).
    assert [ref.title for ref in result.chapters] == [
        first_open.title,
        third_closed.title,
        fifth_open.title,
    ]
    assert [ref.id for ref in result.chapters] == [
        str(first_open.id),
        str(third_closed.id),
        str(fifth_open.id),
    ]

    # The author's working material is absent from the reader's TOC entirely.
    listed_titles = {ref.title for ref in result.chapters}
    listed_ids = {ref.id for ref in result.chapters}
    assert fourth_planned.title not in listed_titles
    assert second_closing.title not in listed_titles
    assert str(fourth_planned.id) not in listed_ids
    assert str(second_closing.id) not in listed_ids


# ---------------------------------------------------------------------------
# DoD-6 — the four exclusions of the public discovery list
# ---------------------------------------------------------------------------


# DoD-6 (UC-029, D14): `list_public_books` excludes the caller's own books, books
# they co-author, private books and non-`active` books, and includes another
# user's `active` `public` book. Each excluded row differs from the included one
# in exactly ONE of the four clauses, so a single wrong clause is caught.
async def test_list_public_books_applies_all_four_exclusions__DoD6_UC029(db: DbConfig):
    caller = await _seed_user("carol")
    stranger = await _seed_user("dave")

    own_public = await _seed_book(
        title="My Own Public Book", owner_id=caller.id, visibility=Visibility.public
    )
    co_authored_public = await _seed_book(
        title="A Book I Co-Author", owner_id=stranger.id, visibility=Visibility.public
    )
    await _add_co_author(co_authored_public.id, caller.id)
    strangers_private = await _seed_book(
        title="A Stranger's Private Book",
        owner_id=stranger.id,
        visibility=Visibility.private,
    )
    strangers_archived = await _seed_book(
        title="A Stranger's Archived Book",
        owner_id=stranger.id,
        visibility=Visibility.public,
        state=BookState.archived,
    )
    discoverable = await _seed_book(
        title="Open To All",
        owner_id=stranger.id,
        description="A saga for anyone.",
        visibility=Visibility.public,
        state=BookState.active,
    )

    result = await reader_service.list_public_books(caller)

    # Exactly one book is discoverable: another user's active, public, unshared one.
    assert [item.id for item in result.items] == [str(discoverable.id)]
    assert result.items[0].title == "Open To All"
    assert result.items[0].description == "A saga for anyone."

    # Named, per-clause exclusions — one clause wrong, one of these fails.
    excluded_ids = {
        str(own_public.id),
        str(co_authored_public.id),
        str(strangers_private.id),
        str(strangers_archived.id),
    }
    assert excluded_ids.isdisjoint({item.id for item in result.items})
