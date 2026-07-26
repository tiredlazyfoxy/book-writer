"""Chat data access. Session-free public API — one module per entity.

Every function opens and closes its own session internally via
``engine.get_standalone_session()``; ``AsyncSession``, ``select()``, and ORM
row types never leak past this module (see ``docs/architecture/backend.md`` —
layer separation). Public functions accept and return ``Chat`` or plain types.

Skeleton (008 step 009): the ``create`` / ``get_by_id`` / ``list_by_book``
signatures are frozen (bodies real, delivered by 008). Skeleton (011 step 001):
``update`` and ``list_by_book_and_author`` are frozen; their bodies are
UNIMPLEMENTED.
"""

from datetime import datetime, timezone

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


async def update(row: Chat) -> Chat:
    """Persist changed columns on an existing ``row``, bumping ``modified_at``,
    and return the persisted row.

    Session-free like every other function in the module. The caller mutates the
    fields it wants changed; this layer owns the ``modified_at`` bump so an update
    always advances the most-recently-modified ordering used by
    :func:`list_by_book_and_author`.

    Skeleton (011 step 001): UNIMPLEMENTED.
    """
    row.modified_at = datetime.now(timezone.utc)
    session = await get_standalone_session()
    async with session:
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return row


async def list_by_book_and_author(
    book_id: int, author_id: int, archived: bool
) -> list[Chat]:
    """Return the ``Chat`` rows for ``book_id`` authored by ``author_id`` whose
    ``archived`` flag equals ``archived``, ordered most-recently-modified first.

    Skeleton (011 step 001): UNIMPLEMENTED.
    """
    session = await get_standalone_session()
    async with session:
        result = await session.exec(
            select(Chat)
            .where(Chat.book_id == book_id)
            .where(Chat.author_id == author_id)
            .where(Chat.archived == archived)
            .order_by(Chat.modified_at.desc())
        )
        return list(result.all())
