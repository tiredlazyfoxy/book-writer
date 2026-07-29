"""Tests for the session-free db/book_author_prompts module (feature 021, step 001).

Bound to the frozen skeleton signatures (status.md -> Skeleton -> Step 001):
    class BookAuthorPrompt(SQLModel, table=True)
        __tablename__ = "book_author_prompts";
        UniqueConstraint(book_id, user_id);
        id: int (snowflake PK), book_id: int (FK books.id),
        user_id: int (FK users.id), system_prompt: str (required, NOT NULL),
        created_at: datetime | None, modified_at: datetime | None
                                             in app.models.book_author_prompt
    async def create(row: BookAuthorPrompt) -> BookAuthorPrompt
                                             in app.db.book_author_prompts
    async def get_by_book_and_user(book_id: int, user_id: int)
        -> BookAuthorPrompt | None           in app.db.book_author_prompts
    async def update(row: BookAuthorPrompt) -> BookAuthorPrompt
                                             in app.db.book_author_prompts

Expected values come from the step spec (001.author-prompt-table.md DoD +
001.context.md + context.md), never from implementation internals:
    - DoD-1: a row created for a (book, user) pair comes back intact from
      get_by_book_and_user — every column, INCLUDING an empty-string prompt,
      which is a value in its own right and must never be coerced to None;
    - DoD-2: get_by_book_and_user returns nothing when the pair has no row, and
      never returns a row belonging to a different book or a different user;
    - DoD-3: a second row for the same (book_id, user_id) pair is refused by the
      DATABASE (the unique constraint is real, not advisory) — asserted as an
      IntegrityError raised out of the insert, not as a Python-side pre-check;
    - DoD-4: two users in one book, and one user across two books, hold
      independent rows; writing one never changes the other;
    - DoD-5: update persists changed prompt text and the returned row reflects
      stored state (it agrees with a fresh read), including clearing a prompt to
      "" — the state "row holding empty string" is distinct from "no row at all"
      and both must survive (001.context.md -> "Gotcha").

DoD-6 (schema present) and DoD-7..9 (codec + TABLE_REGISTRY) live in the flat
module backend/tests/test_data_domain_book_author_prompts.py, per
001.context.md -> "Test seeding".

Async tests use asyncio_mode = "auto"; the `db` fixture (conftest) supplies an
initialized throwaway temp-SQLite engine with the registered tables created.
Supporting book/user rows are seeded through the sibling db/ modules (there is
no HTTP in a db-layer spec).
"""

from datetime import datetime

import pytest
from sqlalchemy.exc import IntegrityError

from app.db import book_author_prompts, books, users
from app.db.engine import DbConfig
from app.models.book import Book, BookState, CollaborationMode, Visibility
from app.models.book_author_prompt import BookAuthorPrompt
from app.models.user import User, UserRole


async def _seed_user(username: str) -> User:
    """A persisted author user, seeded through the sibling db/ module."""
    return await users.create(User(username=username, role=UserRole.author))


async def _seed_book(*, title: str, owner_id: int) -> Book:
    """A persisted book with every required non-null field set."""
    return await books.create(
        Book(
            title=title,
            description="desc",
            owner_id=owner_id,
            collaboration_mode=CollaborationMode.free,
            visibility=Visibility.private,
            state=BookState.active,
            system_prompt="",
            active_notes="",
        )
    )


# ---------------------------------------------------------------------------
# DoD-1 — a created row is returned intact by get_by_book_and_user
# ---------------------------------------------------------------------------


# DoD-1: a row created for a (book, user) pair is returned intact — every
# column survives the round trip (snowflake PK populated on create; both FKs,
# the prompt text and both timestamps read back unchanged).
async def test_created_row_round_trips_every_column__DoD1(db: DbConfig):
    author = await _seed_user("author-one")
    book = await _seed_book(title="Round Trip", owner_id=author.id)

    created_at = datetime(2026, 7, 29, 9, 0, 0)
    modified_at = datetime(2026, 7, 29, 9, 30, 0)

    created = await book_author_prompts.create(
        BookAuthorPrompt(
            book_id=book.id,
            user_id=author.id,
            system_prompt="Write in a dry, factual register.",
            created_at=created_at,
            modified_at=modified_at,
        )
    )
    # Snowflake PK populated on the created row.
    assert created.id is not None

    fetched = await book_author_prompts.get_by_book_and_user(book.id, author.id)

    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.book_id == book.id
    assert fetched.user_id == author.id
    assert fetched.system_prompt == "Write in a dry, factual register."
    assert fetched.created_at == created_at
    assert fetched.modified_at == modified_at


# DoD-1: an EMPTY-STRING prompt is a value, not an absence. A row holding ""
# survives the round trip as "" — never coerced to None, and the row itself is
# genuinely present (distinct from the "no row at all" state of DoD-2).
async def test_empty_string_prompt_round_trips_as_empty_string__DoD1(db: DbConfig):
    author = await _seed_user("author-empty")
    book = await _seed_book(title="Empty Prompt", owner_id=author.id)

    await book_author_prompts.create(
        BookAuthorPrompt(book_id=book.id, user_id=author.id, system_prompt="")
    )

    fetched = await book_author_prompts.get_by_book_and_user(book.id, author.id)

    # The row exists...
    assert fetched is not None
    # ...and its prompt is the empty string, not None.
    assert fetched.system_prompt == ""
    assert fetched.system_prompt is not None


# ---------------------------------------------------------------------------
# DoD-2 — nothing for an unwritten pair; never another book's or user's row
# ---------------------------------------------------------------------------


# DoD-2: get_by_book_and_user returns nothing when the pair has no row, and
# never returns a row belonging to a different book or a different user. One
# row exists for (book_one, author_one); every other combination resolves to
# None.
async def test_lookup_returns_none_and_never_crosses_pairs__DoD2(db: DbConfig):
    author_one = await _seed_user("author-a")
    author_two = await _seed_user("author-b")
    book_one = await _seed_book(title="Book One", owner_id=author_one.id)
    book_two = await _seed_book(title="Book Two", owner_id=author_two.id)

    await book_author_prompts.create(
        BookAuthorPrompt(
            book_id=book_one.id, user_id=author_one.id, system_prompt="only one"
        )
    )

    # The written pair resolves.
    match = await book_author_prompts.get_by_book_and_user(book_one.id, author_one.id)
    assert match is not None
    assert match.system_prompt == "only one"

    # Same book, different user — no row.
    assert (
        await book_author_prompts.get_by_book_and_user(book_one.id, author_two.id)
        is None
    )
    # Same user, different book — no row.
    assert (
        await book_author_prompts.get_by_book_and_user(book_two.id, author_one.id)
        is None
    )
    # Neither — no row.
    assert (
        await book_author_prompts.get_by_book_and_user(book_two.id, author_two.id)
        is None
    )


# ---------------------------------------------------------------------------
# DoD-3 — the (book_id, user_id) unique constraint is enforced by the DATABASE
# ---------------------------------------------------------------------------


# DoD-3: a second row for the same (book_id, user_id) pair is refused by the
# database. The two rows differ only by their auto surrogate id and their prompt
# text, so nothing but the composite UNIQUE can reject the insert; the refusal
# surfaces as an IntegrityError out of SQLite, not as a Python-side pre-check.
async def test_second_row_for_same_pair_is_refused_by_the_database__DoD3(db: DbConfig):
    author = await _seed_user("author-dup")
    book = await _seed_book(title="Duplicate Pair", owner_id=author.id)

    await book_author_prompts.create(
        BookAuthorPrompt(book_id=book.id, user_id=author.id, system_prompt="first")
    )

    with pytest.raises(IntegrityError):
        await book_author_prompts.create(
            BookAuthorPrompt(book_id=book.id, user_id=author.id, system_prompt="second")
        )


# ---------------------------------------------------------------------------
# DoD-4 — rows are independent per (book, user); writing one never moves another
# ---------------------------------------------------------------------------


# DoD-4: two different users in the SAME book hold independent rows — each keeps
# its own prompt, and updating one leaves the other untouched.
async def test_two_users_in_one_book_hold_independent_rows__DoD4(db: DbConfig):
    author_one = await _seed_user("shared-a")
    author_two = await _seed_user("shared-b")
    book = await _seed_book(title="Shared Book", owner_id=author_one.id)

    await book_author_prompts.create(
        BookAuthorPrompt(
            book_id=book.id, user_id=author_one.id, system_prompt="voice of one"
        )
    )
    await book_author_prompts.create(
        BookAuthorPrompt(
            book_id=book.id, user_id=author_two.id, system_prompt="voice of two"
        )
    )

    # Each pair reads back its own prompt.
    row_one = await book_author_prompts.get_by_book_and_user(book.id, author_one.id)
    row_two = await book_author_prompts.get_by_book_and_user(book.id, author_two.id)
    assert row_one is not None and row_two is not None
    assert row_one.system_prompt == "voice of one"
    assert row_two.system_prompt == "voice of two"
    assert row_one.id != row_two.id

    # Writing one never changes the other.
    row_one.system_prompt = "rewritten by one"
    await book_author_prompts.update(row_one)

    after_two = await book_author_prompts.get_by_book_and_user(book.id, author_two.id)
    assert after_two is not None
    assert after_two.system_prompt == "voice of two"


# DoD-4: the SAME user in two different books holds independent rows — each keeps
# its own prompt, and updating one leaves the other untouched.
async def test_one_user_across_two_books_holds_independent_rows__DoD4(db: DbConfig):
    author = await _seed_user("multi-book-author")
    book_one = await _seed_book(title="Novel", owner_id=author.id)
    book_two = await _seed_book(title="Manual", owner_id=author.id)

    await book_author_prompts.create(
        BookAuthorPrompt(
            book_id=book_one.id, user_id=author.id, system_prompt="novelistic"
        )
    )
    await book_author_prompts.create(
        BookAuthorPrompt(
            book_id=book_two.id, user_id=author.id, system_prompt="technical"
        )
    )

    row_one = await book_author_prompts.get_by_book_and_user(book_one.id, author.id)
    row_two = await book_author_prompts.get_by_book_and_user(book_two.id, author.id)
    assert row_one is not None and row_two is not None
    assert row_one.system_prompt == "novelistic"
    assert row_two.system_prompt == "technical"
    assert row_one.id != row_two.id

    # Writing the second book's row never changes the first book's.
    row_two.system_prompt = "very technical"
    await book_author_prompts.update(row_two)

    after_one = await book_author_prompts.get_by_book_and_user(book_one.id, author.id)
    assert after_one is not None
    assert after_one.system_prompt == "novelistic"


# ---------------------------------------------------------------------------
# DoD-5 — update persists changed text; the returned row reflects stored state
# ---------------------------------------------------------------------------


# DoD-5: update(row) persists the changed prompt text — a subsequent
# get_by_book_and_user returns the new value — and the row update RETURNS agrees
# with that stored state on every column (rather than merely echoing the
# in-memory argument).
async def test_update_persists_changed_prompt_text__DoD5(db: DbConfig):
    author = await _seed_user("author-update")
    book = await _seed_book(title="Updatable", owner_id=author.id)

    created = await book_author_prompts.create(
        BookAuthorPrompt(
            book_id=book.id,
            user_id=author.id,
            system_prompt="original prompt",
            created_at=datetime(2026, 7, 29, 8, 0, 0),
            modified_at=datetime(2026, 7, 29, 8, 0, 0),
        )
    )

    created.system_prompt = "revised prompt"
    created.modified_at = datetime(2026, 7, 29, 11, 0, 0)
    returned = await book_author_prompts.update(created)

    stored = await book_author_prompts.get_by_book_and_user(book.id, author.id)
    assert stored is not None
    # The change is persisted.
    assert stored.system_prompt == "revised prompt"
    assert stored.modified_at == datetime(2026, 7, 29, 11, 0, 0)

    # The returned row reflects stored state: it agrees with a fresh read on
    # every column.
    assert returned.id == stored.id
    assert returned.book_id == stored.book_id
    assert returned.user_id == stored.user_id
    assert returned.system_prompt == stored.system_prompt
    assert returned.created_at == stored.created_at
    assert returned.modified_at == stored.modified_at

    # update() does not add a row: the pair still resolves to the same single row.
    assert stored.id == created.id


# DoD-5: clearing a prompt is an update to "" — there is no DELETE. The row
# remains present and holds the empty string; "" is never coerced to None, and
# the pair does NOT collapse into the "no row at all" state.
async def test_update_clears_prompt_to_empty_string_keeping_the_row__DoD5(db: DbConfig):
    author = await _seed_user("author-clear")
    book = await _seed_book(title="Clearable", owner_id=author.id)

    created = await book_author_prompts.create(
        BookAuthorPrompt(
            book_id=book.id, user_id=author.id, system_prompt="something to clear"
        )
    )

    created.system_prompt = ""
    returned = await book_author_prompts.update(created)
    assert returned.system_prompt == ""

    stored = await book_author_prompts.get_by_book_and_user(book.id, author.id)
    # The row is still there (cleared != absent)...
    assert stored is not None
    assert stored.id == created.id
    # ...and holds "" rather than None.
    assert stored.system_prompt == ""
    assert stored.system_prompt is not None
