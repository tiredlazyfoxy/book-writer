"""Chapter data access. Session-free public API — one module per entity.

Every function opens and closes its own session internally via
``engine.get_standalone_session()``; ``AsyncSession``, ``select()``, and ORM
row types never leak past this module (see ``docs/architecture/backend.md`` —
layer separation). Public functions accept and return ``Chapter`` or plain
types.

Skeleton (008 step 005, 014 step 001): signatures are frozen.
"""

from sqlmodel import select

from app.db.engine import get_standalone_session
from app.models.chapter import Chapter


async def create(row: Chapter) -> Chapter:
    """Persist ``row`` and return it with its snowflake ``id`` populated."""
    session = await get_standalone_session()
    async with session:
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return row


async def get_by_id(chapter_id: int) -> Chapter | None:
    """Return the ``Chapter`` with primary key ``chapter_id``, or ``None``."""
    session = await get_standalone_session()
    async with session:
        result = await session.exec(
            select(Chapter).where(Chapter.id == chapter_id)
        )
        return result.one_or_none()


async def list_by_book(book_id: int) -> list[Chapter]:
    """Return every ``Chapter`` row whose ``book_id`` equals ``book_id``."""
    session = await get_standalone_session()
    async with session:
        result = await session.exec(
            select(Chapter).where(Chapter.book_id == book_id)
        )
        return list(result.all())


async def update(row: Chapter) -> None:
    """Persist changes to an already-existing ``Chapter`` ``row``. Returns
    nothing.

    Follows ``db/books.py:update`` exactly — add / commit / refresh, the whole
    body. No read-back, no timestamp (the service owns timestamp policy) and no
    not-found branch: the caller passes the already-mutated ``Chapter``.
    """
    session = await get_standalone_session()
    async with session:
        session.add(row)
        await session.commit()
        await session.refresh(row)


async def delete(chapter_id: int) -> bool:
    """Remove the ``Chapter`` with primary key ``chapter_id``.

    Returns ``True`` when a row was removed and ``False`` when no row matched.
    Deleting an id that is not there is **not** an error — it reports that
    nothing was removed. Follows ``db/book_members.py:delete``'s shape, keyed on
    the primary key rather than a natural pair.
    """
    session = await get_standalone_session()
    async with session:
        result = await session.exec(
            select(Chapter).where(Chapter.id == chapter_id)
        )
        chapter = result.one_or_none()
        if chapter is None:
            return False
        await session.delete(chapter)
        await session.commit()
        return True
