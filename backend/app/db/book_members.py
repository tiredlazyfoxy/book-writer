"""BookMember data access. Session-free public API — one module per entity.

Every function opens and closes its own session internally via
``engine.get_standalone_session()``; ``AsyncSession``, ``select()``, and ORM
row types never leak past this module (see ``docs/architecture/backend.md`` —
layer separation). Public functions accept and return ``BookMember`` or plain
types.

Skeleton (008 step 004): signatures are frozen; bodies are UNIMPLEMENTED.
"""

from sqlmodel import select

from app.db.engine import get_standalone_session
from app.models.book_member import BookMember


async def create(row: BookMember) -> BookMember:
    """Persist ``row`` and return it with its snowflake ``id`` populated."""
    session = await get_standalone_session()
    async with session:
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return row


async def get_by_id(member_id: int) -> BookMember | None:
    """Return the ``BookMember`` with primary key ``member_id``, or ``None``."""
    session = await get_standalone_session()
    async with session:
        result = await session.exec(
            select(BookMember).where(BookMember.id == member_id)
        )
        return result.one_or_none()


async def list_by_book(book_id: int) -> list[BookMember]:
    """Return every ``BookMember`` row whose ``book_id`` equals ``book_id``."""
    session = await get_standalone_session()
    async with session:
        result = await session.exec(
            select(BookMember).where(BookMember.book_id == book_id)
        )
        return list(result.all())
