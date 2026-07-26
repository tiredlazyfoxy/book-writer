"""Tests for the new session-free db/chats primitives (feature 011, step 001).

Bound to the frozen skeleton signatures (status.md -> Skeleton -> Step 001), in
`app.db.chats` (existing `create`/`get_by_id`/`list_by_book` unchanged):
    async def update(row: Chat) -> Chat
        -- persists changed columns, bumps `modified_at`, returns the row
    async def list_by_book_and_author(
        book_id: int, author_id: int, archived: bool
    ) -> list[Chat]
        -- most-recently-modified first

Expected values come from the step spec (001.chat-crud-model-sampling.md DoD +
001.context.md), never from implementation internals:
    - update persists changed columns and advances `modified_at` (DoD-5 / DoD-6 /
      DoD-7 persistence primitive);
    - the per-author listing returns only the given (book, author) pair's rows,
      filtered by `archived`, ordered most-recently-modified first (DoD-2, DoD-5).

Async tests use asyncio_mode = "auto"; the `db` fixture (conftest) supplies an
initialized throwaway temp-SQLite engine. SQLite does not enforce FKs by default,
so chats need no parent book/author rows.
"""

from datetime import datetime

from app.db import chats
from app.db.engine import DbConfig
from app.models.chat import Chat


# DoD-5/DoD-6/DoD-7 primitive: update persists changed columns (archived, the
# model pair, sampling_params) and returns the row; get_by_id reflects them.
async def test_update_persists_changed_columns__DoD5(db: DbConfig):
    created = await chats.create(
        Chat(book_id=1, author_id=1, title="Draft", archived=False)
    )

    created.title = "Renamed"
    created.archived = True
    created.llm_server_id = 424242
    created.model_name = "some-model"
    created.sampling_params = '{"temperature": 0.3}'
    await chats.update(created)

    fetched = await chats.get_by_id(created.id)
    assert fetched is not None
    assert fetched.title == "Renamed"
    assert fetched.archived is True
    assert fetched.llm_server_id == 424242
    assert fetched.model_name == "some-model"
    assert fetched.sampling_params == '{"temperature": 0.3}'


# DoD-5: update bumps `modified_at` -- the stored value differs from the
# pre-update value and is populated after the update.
async def test_update_bumps_modified_at__DoD5(db: DbConfig):
    old = datetime(2020, 1, 1, 0, 0, 0)
    created = await chats.create(
        Chat(book_id=1, author_id=1, title="T", modified_at=old)
    )

    created.title = "T2"
    await chats.update(created)

    fetched = await chats.get_by_id(created.id)
    assert fetched is not None
    assert fetched.modified_at is not None
    assert fetched.modified_at != old


# DoD-2: list_by_book_and_author returns only the given (book, author) pair's
# non-archived chats, most-recently-modified first -- excluding another author's
# chat in the same book, the same author's chat in another book, and archived
# rows.
async def test_list_by_book_and_author_filters_and_orders__DoD2(db: DbConfig):
    book = 100
    author = 7
    # Two of the caller's own active chats in the book, distinct modified_at.
    await chats.create(
        Chat(
            book_id=book,
            author_id=author,
            title="older",
            modified_at=datetime(2026, 7, 25, 9, 0, 0),
        )
    )
    await chats.create(
        Chat(
            book_id=book,
            author_id=author,
            title="newer",
            modified_at=datetime(2026, 7, 25, 10, 0, 0),
        )
    )
    # An archived chat of the caller's (must be excluded when archived=False).
    await chats.create(
        Chat(
            book_id=book,
            author_id=author,
            title="archived-one",
            archived=True,
            modified_at=datetime(2026, 7, 25, 11, 0, 0),
        )
    )
    # Another author's chat in the same book (must be excluded).
    await chats.create(
        Chat(book_id=book, author_id=999, title="other-author", archived=False)
    )
    # The caller's chat in a different book (must be excluded).
    await chats.create(
        Chat(book_id=200, author_id=author, title="other-book", archived=False)
    )

    listed = await chats.list_by_book_and_author(book, author, False)

    # Exactly the caller's two active chats in this book, newest first.
    assert [c.title for c in listed] == ["newer", "older"]


# DoD-5: filtering by archived=True returns only the caller's archived chats in
# the book (the active ones are excluded).
async def test_list_by_book_and_author_archived_filter__DoD5(db: DbConfig):
    book = 300
    author = 8
    await chats.create(
        Chat(book_id=book, author_id=author, title="active", archived=False)
    )
    await chats.create(
        Chat(book_id=book, author_id=author, title="gone", archived=True)
    )

    archived = await chats.list_by_book_and_author(book, author, True)

    assert [c.title for c in archived] == ["gone"]
