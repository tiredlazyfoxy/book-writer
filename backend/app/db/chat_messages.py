"""ChatMessage data access. Session-free public API — one module per entity.

Every function opens and closes its own session internally via
``engine.get_standalone_session()``; ``AsyncSession``, ``select()``, and ORM
row types never leak past this module (see ``docs/architecture/backend.md`` —
layer separation). Public functions accept and return ``ChatMessage`` or plain
types.

Skeleton (008 step 009): signatures are frozen; bodies are UNIMPLEMENTED.
"""

from sqlmodel import select

from app.db.engine import get_standalone_session
from app.models.chat import ChatMessage


async def create(row: ChatMessage) -> ChatMessage:
    """Persist ``row`` and return it with its snowflake ``id`` populated."""
    session = await get_standalone_session()
    async with session:
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return row


async def get_by_id(message_id: int) -> ChatMessage | None:
    """Return the ``ChatMessage`` with primary key ``message_id``, or ``None``."""
    session = await get_standalone_session()
    async with session:
        result = await session.exec(
            select(ChatMessage).where(ChatMessage.id == message_id)
        )
        return result.one_or_none()


async def list_by_chat(chat_id: int) -> list[ChatMessage]:
    """Return every ``ChatMessage`` row whose ``chat_id`` equals ``chat_id``."""
    session = await get_standalone_session()
    async with session:
        result = await session.exec(
            select(ChatMessage).where(ChatMessage.chat_id == chat_id)
        )
        return list(result.all())
