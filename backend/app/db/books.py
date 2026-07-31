"""Book data access. Session-free public API — one module per entity.

Every function opens and closes its own session internally via
``engine.get_standalone_session()``; ``AsyncSession``, ``select()``, and ORM
row types never leak past this module (see ``docs/architecture/backend.md`` —
layer separation). Public functions accept and return ``Book`` or plain types.

Skeleton (008 step 004): signatures are frozen; bodies are UNIMPLEMENTED.
"""

from sqlalchemy import exists
from sqlmodel import select

from app.db.engine import get_standalone_session
from app.models.book import Book, BookState, Visibility
from app.models.book_member import BookMember


async def create(row: Book) -> Book:
    """Persist ``row`` and return it with its snowflake ``id`` populated."""
    session = await get_standalone_session()
    async with session:
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return row


async def get_by_id(book_id: int) -> Book | None:
    """Return the ``Book`` with primary key ``book_id``, or ``None``."""
    session = await get_standalone_session()
    async with session:
        result = await session.exec(select(Book).where(Book.id == book_id))
        return result.one_or_none()


async def update(row: Book) -> None:
    """Persist changes to an already-existing ``Book`` ``row``. Returns nothing.

    Follows the ``llm_servers`` add/commit/refresh convention; the caller passes
    the already-mutated ``Book``.

    Skeleton (009 step 001): signature frozen.
    """
    session = await get_standalone_session()
    async with session:
        session.add(row)
        await session.commit()
        await session.refresh(row)


async def list_by_owner(owner_id: int) -> list[Book]:
    """Return every ``Book`` whose ``owner_id`` matches, deterministically
    ordered.

    Skeleton (009 step 001): signature frozen.
    """
    session = await get_standalone_session()
    async with session:
        result = await session.exec(
            select(Book).where(Book.owner_id == owner_id).order_by(Book.id)
        )
        return list(result.all())


async def list_shared(user_id: int) -> list[Book]:
    """Return every ``Book`` where ``user_id`` is a ``BookMember`` (co-author)
    and is **not** the owner, deterministically ordered.

    Skeleton (009 step 001): signature frozen.
    """
    session = await get_standalone_session()
    async with session:
        result = await session.exec(
            select(Book)
            .join(BookMember, BookMember.book_id == Book.id)
            .where(BookMember.user_id == user_id)
            .where(Book.owner_id != user_id)
            .order_by(Book.id)
        )
        return list(result.all())


async def list_public_for_reader(user_id: int) -> list[Book]:
    """Return the public books ``user_id`` can discover but is not part of —
    the reader's discovery feed (feature 022, UC-029 / D14).

    Intent: every ``Book`` for which **all four** hold, ordered by ``Book.id``:

    - ``Book.visibility == Visibility.public``,
    - ``Book.state == BookState.active`` (an archived book stays readable by
      direct link — this changes no authorization — but listing it in a discovery
      feed would contradict UC-023's "preserved and reversible"; filtering on
      ``active`` excludes ``quarantined`` / ``destroyed`` for free),
    - ``Book.owner_id != user_id`` (the caller's own books are already in "My
      books"),
    - **no** ``BookMember`` row for ``(Book.id, user_id)`` — a ``NOT EXISTS``,
      the exact negative of :func:`list_shared`'s join, so the three bookshelf
      sections stay disjoint.

    Skeleton (feature 022): signature frozen.
    """
    session = await get_standalone_session()
    async with session:
        # Correlated ``NOT EXISTS`` over ``book_members`` — the exact negative of
        # ``list_shared``'s join. A join + ``IS NULL`` would work too, but an
        # anti-join reads as what it means and cannot duplicate a row if the
        # membership pair ever stopped being unique.
        is_member = exists().where(
            BookMember.book_id == Book.id,
            BookMember.user_id == user_id,
        )
        result = await session.exec(
            select(Book)
            .where(Book.visibility == Visibility.public)
            .where(Book.state == BookState.active)
            .where(Book.owner_id != user_id)
            .where(~is_member)
            .order_by(Book.id)
        )
        return list(result.all())
