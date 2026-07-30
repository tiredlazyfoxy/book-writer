"""Tests for the session-free db/chapter_author_prompts module (feature 014, step 001).

Bound to the frozen skeleton signatures (status.md -> Skeleton -> Step 001):
    class ChapterAuthorPrompt(SQLModel, table=True)
        __tablename__ = "chapter_author_prompts";
        UniqueConstraint(chapter_id, user_id);
        id: int (snowflake PK), chapter_id: int (FK chapters.id),
        user_id: int (FK users.id), system_prompt: str (required, NOT NULL),
        created_at: datetime | None, modified_at: datetime | None
                                          in app.models.chapter_author_prompt
    async def create(row: ChapterAuthorPrompt) -> ChapterAuthorPrompt
                                          in app.db.chapter_author_prompts
    async def get_by_chapter_and_user(chapter_id: int, user_id: int)
        -> ChapterAuthorPrompt | None     in app.db.chapter_author_prompts
    async def update(row: ChapterAuthorPrompt) -> ChapterAuthorPrompt
                                          in app.db.chapter_author_prompts

Expected values come from the step spec (001.chapter-author-prompt-table.md DoD +
001.context.md + context.md decision D1), never from implementation internals:
    - DoD-1: a row created for a (chapter, user) pair comes back intact from
      get_by_chapter_and_user — every column, INCLUDING an empty-string prompt,
      which D1 states is a value in its own right ("" means "no prompt") and must
      never be coerced to None;
    - DoD-2: get_by_chapter_and_user returns nothing when the pair has no row, and
      never returns a row belonging to a different chapter or a different user;
    - DoD-3: a second row for the same (chapter_id, user_id) pair is refused by
      the DATABASE — the unique constraint is real, not advisory. Asserted by
      letting the insert raise (001.context.md -> "Testing": do NOT pre-read and
      branch, which would test the test rather than the constraint);
    - DoD-4: two users on one chapter, and one user across two chapters, hold
      independent rows; writing one never changes the other;
    - DoD-5: update persists changed prompt text and the returned row reflects
      STORED state (it agrees with a fresh read) rather than merely echoing the
      in-memory argument.

DoD-6 (schema present), DoD-7/8 (codec + TABLE_REGISTRY) and DoD-12 (the chapters
codec preservation clause) live in the flat module
backend/tests/test_data_domain_chapter_author_prompts.py.
DoD-9..11 (db/chapters.py update + delete) live in backend/tests/db/test_chapters.py.

Async tests use asyncio_mode = "auto"; the `db` fixture (conftest) supplies an
initialized throwaway temp-SQLite engine with the registered tables created.
Supporting user/book/chapter rows are seeded through the sibling db/ modules
(there is no HTTP and no JWT in a db-layer spec).

The db/ layer holds NO timestamp policy (001.context.md -> "Timestamps are not
this layer's"): create does not stamp `created_at` and update does not stamp
`modified_at`, so every timestamp asserted here is one the test itself supplied.
"""

from datetime import datetime

import pytest
from sqlalchemy.exc import IntegrityError

from app.db import books, chapter_author_prompts, chapters, users
from app.db.engine import DbConfig
from app.models.book import Book, BookState, CollaborationMode, Visibility
from app.models.chapter import Chapter, ChapterState
from app.models.chapter_author_prompt import ChapterAuthorPrompt
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


async def _seed_chapter(*, book_id: int, ordinal: int, title: str) -> Chapter:
    """A persisted planned chapter with every required non-null field set."""
    return await chapters.create(
        Chapter(
            book_id=book_id,
            ordinal=ordinal,
            title=title,
            state=ChapterState.planned,
            sketch="",
            text="",
        )
    )


# ---------------------------------------------------------------------------
# DoD-1 — a created row is returned intact by get_by_chapter_and_user
# ---------------------------------------------------------------------------


# DoD-1: a row created for a (chapter, user) pair is returned intact — every
# column survives the round trip (snowflake PK populated on create; both FKs, the
# prompt text and both timestamps read back unchanged).
async def test_created_row_round_trips_every_column__DoD1(db: DbConfig):
    author = await _seed_user("chapter-author-one")
    book = await _seed_book(title="Round Trip", owner_id=author.id)
    chapter = await _seed_chapter(book_id=book.id, ordinal=1, title="Chapter One")

    created_at = datetime(2026, 7, 29, 9, 0, 0)
    modified_at = datetime(2026, 7, 29, 9, 30, 0)

    created = await chapter_author_prompts.create(
        ChapterAuthorPrompt(
            chapter_id=chapter.id,
            user_id=author.id,
            system_prompt="Write this chapter in a dry, factual register.",
            created_at=created_at,
            modified_at=modified_at,
        )
    )
    # Snowflake PK populated on the created row.
    assert created.id is not None

    fetched = await chapter_author_prompts.get_by_chapter_and_user(
        chapter.id, author.id
    )

    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.chapter_id == chapter.id
    assert fetched.user_id == author.id
    assert fetched.system_prompt == "Write this chapter in a dry, factual register."
    assert fetched.created_at == created_at
    assert fetched.modified_at == modified_at


# DoD-1: an EMPTY-STRING prompt is a value, not an absence (D1: `""` means "no
# prompt"). A row holding "" survives the round trip as "" — never coerced to
# None — and the row itself is genuinely present, which is distinct from the
# "no row at all" state of DoD-2.
async def test_empty_string_prompt_round_trips_as_empty_string__DoD1(db: DbConfig):
    author = await _seed_user("chapter-author-empty")
    book = await _seed_book(title="Empty Prompt", owner_id=author.id)
    chapter = await _seed_chapter(book_id=book.id, ordinal=1, title="Blank")

    await chapter_author_prompts.create(
        ChapterAuthorPrompt(
            chapter_id=chapter.id, user_id=author.id, system_prompt=""
        )
    )

    fetched = await chapter_author_prompts.get_by_chapter_and_user(
        chapter.id, author.id
    )

    # The row exists...
    assert fetched is not None
    # ...and its prompt is the empty string, not None.
    assert fetched.system_prompt == ""
    assert fetched.system_prompt is not None


# ---------------------------------------------------------------------------
# DoD-2 — nothing for an unwritten pair; never another chapter's or user's row
# ---------------------------------------------------------------------------


# DoD-2: get_by_chapter_and_user returns nothing when the pair has no row, and
# never returns a row belonging to a different chapter or a different user. One
# row exists for (chapter_one, author_one); every other combination resolves to
# None.
async def test_lookup_returns_none_and_never_crosses_pairs__DoD2(db: DbConfig):
    author_one = await _seed_user("chapter-author-a")
    author_two = await _seed_user("chapter-author-b")
    book = await _seed_book(title="Two Chapters", owner_id=author_one.id)
    chapter_one = await _seed_chapter(book_id=book.id, ordinal=1, title="One")
    chapter_two = await _seed_chapter(book_id=book.id, ordinal=2, title="Two")

    await chapter_author_prompts.create(
        ChapterAuthorPrompt(
            chapter_id=chapter_one.id,
            user_id=author_one.id,
            system_prompt="only one",
        )
    )

    # The written pair resolves.
    match = await chapter_author_prompts.get_by_chapter_and_user(
        chapter_one.id, author_one.id
    )
    assert match is not None
    assert match.system_prompt == "only one"

    # Same chapter, different user — no row.
    assert (
        await chapter_author_prompts.get_by_chapter_and_user(
            chapter_one.id, author_two.id
        )
        is None
    )
    # Same user, different chapter — no row.
    assert (
        await chapter_author_prompts.get_by_chapter_and_user(
            chapter_two.id, author_one.id
        )
        is None
    )
    # Neither — no row.
    assert (
        await chapter_author_prompts.get_by_chapter_and_user(
            chapter_two.id, author_two.id
        )
        is None
    )


# ---------------------------------------------------------------------------
# DoD-3 — the (chapter_id, user_id) unique constraint is enforced by the DATABASE
# ---------------------------------------------------------------------------


# DoD-3: a second row for the same (chapter_id, user_id) pair is refused by the
# database. The two rows differ only by their auto surrogate id and their prompt
# text, so nothing but the composite UNIQUE can reject the insert; the refusal is
# observed by letting the insert RAISE out of SQLite, not by a Python-side
# pre-check (001.context.md -> "Testing").
async def test_second_row_for_same_pair_is_refused_by_the_database__DoD3(
    db: DbConfig,
):
    author = await _seed_user("chapter-author-dup")
    book = await _seed_book(title="Duplicate Pair", owner_id=author.id)
    chapter = await _seed_chapter(book_id=book.id, ordinal=1, title="Dup")

    await chapter_author_prompts.create(
        ChapterAuthorPrompt(
            chapter_id=chapter.id, user_id=author.id, system_prompt="first"
        )
    )

    with pytest.raises(IntegrityError):
        await chapter_author_prompts.create(
            ChapterAuthorPrompt(
                chapter_id=chapter.id, user_id=author.id, system_prompt="second"
            )
        )


# ---------------------------------------------------------------------------
# DoD-4 — rows are independent per (chapter, user); writing one never moves another
# ---------------------------------------------------------------------------


# DoD-4: two different users on the SAME chapter hold independent rows — each
# keeps its own prompt, and updating one leaves the other untouched.
async def test_two_users_on_one_chapter_hold_independent_rows__DoD4(db: DbConfig):
    author_one = await _seed_user("shared-chapter-a")
    author_two = await _seed_user("shared-chapter-b")
    book = await _seed_book(title="Shared Book", owner_id=author_one.id)
    chapter = await _seed_chapter(book_id=book.id, ordinal=1, title="Shared Chapter")

    await chapter_author_prompts.create(
        ChapterAuthorPrompt(
            chapter_id=chapter.id, user_id=author_one.id, system_prompt="voice of one"
        )
    )
    await chapter_author_prompts.create(
        ChapterAuthorPrompt(
            chapter_id=chapter.id, user_id=author_two.id, system_prompt="voice of two"
        )
    )

    # Each pair reads back its own prompt.
    row_one = await chapter_author_prompts.get_by_chapter_and_user(
        chapter.id, author_one.id
    )
    row_two = await chapter_author_prompts.get_by_chapter_and_user(
        chapter.id, author_two.id
    )
    assert row_one is not None and row_two is not None
    assert row_one.system_prompt == "voice of one"
    assert row_two.system_prompt == "voice of two"
    assert row_one.id != row_two.id

    # Writing one never changes the other.
    row_one.system_prompt = "rewritten by one"
    await chapter_author_prompts.update(row_one)

    after_two = await chapter_author_prompts.get_by_chapter_and_user(
        chapter.id, author_two.id
    )
    assert after_two is not None
    assert after_two.system_prompt == "voice of two"


# DoD-4: the SAME user on two different chapters holds independent rows — each
# keeps its own prompt, and updating one leaves the other untouched.
async def test_one_user_across_two_chapters_holds_independent_rows__DoD4(
    db: DbConfig,
):
    author = await _seed_user("multi-chapter-author")
    book = await _seed_book(title="Novel", owner_id=author.id)
    chapter_one = await _seed_chapter(book_id=book.id, ordinal=1, title="Opening")
    chapter_two = await _seed_chapter(book_id=book.id, ordinal=2, title="Climax")

    await chapter_author_prompts.create(
        ChapterAuthorPrompt(
            chapter_id=chapter_one.id, user_id=author.id, system_prompt="quiet opening"
        )
    )
    await chapter_author_prompts.create(
        ChapterAuthorPrompt(
            chapter_id=chapter_two.id, user_id=author.id, system_prompt="loud climax"
        )
    )

    row_one = await chapter_author_prompts.get_by_chapter_and_user(
        chapter_one.id, author.id
    )
    row_two = await chapter_author_prompts.get_by_chapter_and_user(
        chapter_two.id, author.id
    )
    assert row_one is not None and row_two is not None
    assert row_one.system_prompt == "quiet opening"
    assert row_two.system_prompt == "loud climax"
    assert row_one.id != row_two.id

    # Writing the second chapter's row never changes the first chapter's.
    row_two.system_prompt = "very loud climax"
    await chapter_author_prompts.update(row_two)

    after_one = await chapter_author_prompts.get_by_chapter_and_user(
        chapter_one.id, author.id
    )
    assert after_one is not None
    assert after_one.system_prompt == "quiet opening"


# ---------------------------------------------------------------------------
# DoD-5 — update persists changed text; the returned row reflects stored state
# ---------------------------------------------------------------------------


# DoD-5: update(row) persists the changed prompt text — a subsequent
# get_by_chapter_and_user returns the new value — and the row update RETURNS
# agrees with that stored state on every column, rather than merely echoing the
# in-memory argument.
async def test_update_persists_changed_prompt_text__DoD5(db: DbConfig):
    author = await _seed_user("chapter-author-update")
    book = await _seed_book(title="Updatable", owner_id=author.id)
    chapter = await _seed_chapter(book_id=book.id, ordinal=1, title="Editable")

    created = await chapter_author_prompts.create(
        ChapterAuthorPrompt(
            chapter_id=chapter.id,
            user_id=author.id,
            system_prompt="original prompt",
            created_at=datetime(2026, 7, 29, 8, 0, 0),
            modified_at=datetime(2026, 7, 29, 8, 0, 0),
        )
    )

    created.system_prompt = "revised prompt"
    created.modified_at = datetime(2026, 7, 29, 11, 0, 0)
    returned = await chapter_author_prompts.update(created)

    stored = await chapter_author_prompts.get_by_chapter_and_user(
        chapter.id, author.id
    )
    assert stored is not None
    # The change is persisted.
    assert stored.system_prompt == "revised prompt"
    assert stored.modified_at == datetime(2026, 7, 29, 11, 0, 0)

    # The returned row reflects stored state: it agrees with a fresh read on
    # every column.
    assert returned.id == stored.id
    assert returned.chapter_id == stored.chapter_id
    assert returned.user_id == stored.user_id
    assert returned.system_prompt == stored.system_prompt
    assert returned.created_at == stored.created_at
    assert returned.modified_at == stored.modified_at

    # update() does not add a row: the pair still resolves to the same single row.
    assert stored.id == created.id


# DoD-5: clearing a prompt is an update to "" — there is no delete function on
# this module. The row remains present and holds the empty string; "" is never
# coerced to None, and the pair does NOT collapse into the "no row at all" state.
async def test_update_clears_prompt_to_empty_string_keeping_the_row__DoD5(
    db: DbConfig,
):
    author = await _seed_user("chapter-author-clear")
    book = await _seed_book(title="Clearable", owner_id=author.id)
    chapter = await _seed_chapter(book_id=book.id, ordinal=1, title="Clearable Chapter")

    created = await chapter_author_prompts.create(
        ChapterAuthorPrompt(
            chapter_id=chapter.id,
            user_id=author.id,
            system_prompt="something to clear",
        )
    )

    created.system_prompt = ""
    returned = await chapter_author_prompts.update(created)
    assert returned.system_prompt == ""

    stored = await chapter_author_prompts.get_by_chapter_and_user(
        chapter.id, author.id
    )
    # The row is still there (cleared != absent)...
    assert stored is not None
    assert stored.id == created.id
    # ...and holds "" rather than None.
    assert stored.system_prompt == ""
    assert stored.system_prompt is not None
