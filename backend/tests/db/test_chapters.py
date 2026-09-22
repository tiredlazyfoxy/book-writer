"""Tests for db/chapters.py's two new write functions (feature 014, step 001).

Bound to the frozen skeleton signatures (status.md -> Skeleton -> Step 001):
    async def update(row: Chapter) -> None       in app.db.chapters   (new)
    async def delete(chapter_id: int) -> bool    in app.db.chapters   (new)
and the three pre-existing functions this spec only uses to set up and observe:
    async def create(row: Chapter) -> Chapter
    async def get_by_id(chapter_id: int) -> Chapter | None
    async def list_by_book(book_id: int) -> list[Chapter]

Expected values come from the step spec (001.chapter-author-prompt-table.md DoD +
001.context.md), never from implementation internals:
    - DoD-9: update persists a changed `sketch`, a changed `ordinal` and a changed
      `title`, and a following get_by_id returns the STORED values;
    - DoD-10: delete removes the row — a following get_by_id finds nothing and
      list_by_book no longer includes it — and reports that it removed one;
    - DoD-11: delete on an id that does not exist reports that nothing was removed
      and raises nothing (a missing id is not an error).

The db/ layer holds NO timestamp policy (001.context.md -> "Timestamps are not
this layer's"): update does not stamp `modified_at`. `backend/app/models/chapter.py`
is untouched by this step, so `ordinal` and `state` remain required with no
default and every insert supplies both.

Async tests use asyncio_mode = "auto"; the `db` fixture (conftest) supplies an
initialized throwaway temp-SQLite engine with the registered tables created.
Supporting user/book rows are seeded through the sibling db/ modules (there is no
HTTP and no JWT in a db-layer spec).
"""

from app.db import books, chapters, users
from app.db.engine import DbConfig
from app.models.book import Book, BookState, CollaborationMode, Visibility
from app.models.chapter import Chapter, ChapterState
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


async def _seed_chapter(
    *, book_id: int, ordinal: int, title: str, sketch: str = ""
) -> Chapter:
    """A persisted planned chapter with every required non-null field set."""
    return await chapters.create(
        Chapter(
            book_id=book_id,
            ordinal=ordinal,
            title=title,
            state=ChapterState.planned,
            sketch=sketch,
            text="",
        )
    )


# ---------------------------------------------------------------------------
# DoD-9 — update persists a changed sketch, ordinal and title
# ---------------------------------------------------------------------------


# DoD-9: chapters.update(row) persists an already-mutated chapter — a changed
# `sketch`, a changed `ordinal` and a changed `title` all land, and a following
# get_by_id returns the STORED values. Fields the caller did not touch are
# unchanged, and no second row appears.
async def test_update_persists_sketch_ordinal_and_title__DoD9(db: DbConfig):
    author = await _seed_user("chapters-update-author")
    book = await _seed_book(title="Updatable Book", owner_id=author.id)
    chapter = await _seed_chapter(
        book_id=book.id, ordinal=1, title="Original Title", sketch="original sketch"
    )

    chapter.sketch = "a rewritten sketch"
    chapter.ordinal = 4
    chapter.title = "Rewritten Title"
    await chapters.update(chapter)

    stored = await chapters.get_by_id(chapter.id)
    assert stored is not None
    # All three changes are persisted.
    assert stored.sketch == "a rewritten sketch"
    assert stored.ordinal == 4
    assert stored.title == "Rewritten Title"
    # Untouched columns are unchanged.
    assert stored.book_id == book.id
    assert stored.state is ChapterState.planned
    assert stored.text == ""
    assert stored.version == 1

    # update() rewrites the row rather than adding one.
    listed = await chapters.list_by_book(book.id)
    assert [c.id for c in listed] == [chapter.id]


# DoD-9: a second update on the same row persists again — the stored state is
# always the latest write, not the first one.
async def test_update_is_repeatable__DoD9(db: DbConfig):
    author = await _seed_user("chapters-update-twice-author")
    book = await _seed_book(title="Twice Updated", owner_id=author.id)
    chapter = await _seed_chapter(
        book_id=book.id, ordinal=1, title="First", sketch="first sketch"
    )

    chapter.sketch = "second sketch"
    chapter.title = "Second"
    chapter.ordinal = 2
    await chapters.update(chapter)

    chapter.sketch = "third sketch"
    chapter.title = "Third"
    chapter.ordinal = 3
    await chapters.update(chapter)

    stored = await chapters.get_by_id(chapter.id)
    assert stored is not None
    assert stored.sketch == "third sketch"
    assert stored.title == "Third"
    assert stored.ordinal == 3


# ---------------------------------------------------------------------------
# DoD-10 — delete removes the row and reports that it removed one
# ---------------------------------------------------------------------------


# DoD-10: chapters.delete(chapter_id) removes the row — a following get_by_id
# finds nothing and list_by_book no longer includes it — and reports that it
# removed one. The book's other chapters are untouched.
async def test_delete_removes_the_row_and_reports_one__DoD10(db: DbConfig):
    author = await _seed_user("chapters-delete-author")
    book = await _seed_book(title="Deletable Book", owner_id=author.id)
    doomed = await _seed_chapter(book_id=book.id, ordinal=1, title="Doomed")
    survivor = await _seed_chapter(book_id=book.id, ordinal=2, title="Survivor")

    removed = await chapters.delete(doomed.id)

    # It reports that it removed one.
    assert removed is True

    # A following get_by_id finds nothing.
    assert await chapters.get_by_id(doomed.id) is None

    # list_by_book no longer includes it; the sibling chapter is untouched.
    listed = await chapters.list_by_book(book.id)
    assert [c.id for c in listed] == [survivor.id]
    assert listed[0].title == "Survivor"


# ---------------------------------------------------------------------------
# DoD-11 — deleting an id that is not there is not an error
# ---------------------------------------------------------------------------


# DoD-11: delete on an id that does not exist reports that nothing was removed and
# raises nothing. Asserted against a never-used id on a database that does hold
# other chapters, so "nothing matched" is a genuine miss rather than an empty table.
async def test_delete_missing_id_reports_nothing_removed__DoD11(db: DbConfig):
    author = await _seed_user("chapters-missing-delete-author")
    book = await _seed_book(title="Intact Book", owner_id=author.id)
    kept = await _seed_chapter(book_id=book.id, ordinal=1, title="Kept")

    removed = await chapters.delete(999999999999)

    # Nothing was removed, and no exception escaped.
    assert removed is False

    # The existing chapter is untouched.
    assert await chapters.get_by_id(kept.id) is not None
    assert [c.id for c in await chapters.list_by_book(book.id)] == [kept.id]


# DoD-11: deleting the SAME id twice — the second call finds nothing left to
# remove and reports so, still without raising.
async def test_delete_twice_reports_false_the_second_time__DoD11(db: DbConfig):
    author = await _seed_user("chapters-double-delete-author")
    book = await _seed_book(title="Twice Deleted", owner_id=author.id)
    chapter = await _seed_chapter(book_id=book.id, ordinal=1, title="Gone Soon")

    assert await chapters.delete(chapter.id) is True
    assert await chapters.delete(chapter.id) is False
    assert await chapters.get_by_id(chapter.id) is None
