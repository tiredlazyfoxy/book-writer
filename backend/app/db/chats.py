"""Chat data access. Session-free public API — one module per entity.

Every function opens and closes its own session internally via
``engine.get_standalone_session()``; ``AsyncSession``, ``select()``, and ORM
row types never leak past this module (see ``docs/architecture/backend.md`` —
layer separation). Public functions accept and return ``Chat`` or plain types.

Skeleton (008 step 009): signatures are frozen; bodies are UNIMPLEMENTED.
"""

from sqlmodel import select

from app.db.engine import get_standalone_session
from app.models.chat import Chat


async def create(row: Chat) -> Chat:
    """Persist ``row`` and return it with its snowflake ``id`` populated."""
    session = await get_standalone_session()
    async with session:
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return row


async def get_by_id(chat_id: int) -> Chat | None:
    """Return the ``Chat`` with primary key ``chat_id``, or ``None``."""
    session = await get_standalone_session()
    async with session:
        result = await session.exec(select(Chat).where(Chat.id == chat_id))
        return result.one_or_none()


async def list_by_book(book_id: int) -> list[Chat]:
    """Return every ``Chat`` row whose ``book_id`` equals ``book_id``."""
    session = await get_standalone_session()
    async with session:
        result = await session.exec(select(Chat).where(Chat.book_id == book_id))
        return list(result.all())
