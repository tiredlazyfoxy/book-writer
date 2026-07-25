"""Book data access. Session-free public API — one module per entity.

Every function opens and closes its own session internally via
``engine.get_standalone_session()``; ``AsyncSession``, ``select()``, and ORM
row types never leak past this module (see ``docs/architecture/backend.md`` —
layer separation). Public functions accept and return ``Book`` or plain types.

Skeleton (008 step 004): signatures are frozen; bodies are UNIMPLEMENTED.
"""

from sqlmodel import select

from app.db.engine import get_standalone_session
from app.models.book import Book
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
