"""ChatMessage data access. Session-free public API — one module per entity.

Every function opens and closes its own session internally via
``engine.get_standalone_session()``; ``AsyncSession``, ``select()``, and ORM
row types never leak past this module (see ``docs/architecture/backend.md`` —
layer separation). Public functions accept and return ``ChatMessage`` or plain
types.

Skeleton (008 step 009): the ``create`` / ``get_by_id`` / ``list_by_chat``
signatures are frozen (bodies real, delivered by 008). Skeleton (011 step 001):
``list_by_chat_ordered`` and ``next_position`` are frozen; their bodies are
UNIMPLEMENTED. Step 003 is the only writer of messages; this step adds the
ordered read and position allocation it will consume.
"""

from sqlalchemy import func
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


async def list_by_chat_ordered(chat_id: int) -> list[ChatMessage]:
    """Return a chat's messages ordered by ``position`` ascending (where
    :func:`list_by_chat` is unordered).

    Skeleton (011 step 001): UNIMPLEMENTED.
    """
    session = await get_standalone_session()
    async with session:
        result = await session.exec(
            select(ChatMessage)
            .where(ChatMessage.chat_id == chat_id)
            .order_by(ChatMessage.position)
        )
        return list(result.all())


async def count_by_chat_and_role(chat_id: int, role: str) -> int:
    """Count a chat's persisted messages whose ``role`` matches, without loading
    any of them (023).

    The auto-titler's trigger is derived from a LIVE count rather than a stored
    flag (023 → D3), so it needs "how many ``user`` messages does this chat have"
    as a scalar — never the transcript.

    A chat with no matching message counts ``0``; the count is never ``None``.
    """
    session = await get_standalone_session()
    async with session:
        result = await session.exec(
            select(func.count(ChatMessage.id))
            .where(ChatMessage.chat_id == chat_id)
            .where(ChatMessage.role == role)
        )
        total = result.one()
        return 0 if total is None else int(total)


async def next_position(chat_id: int) -> int:
    """Return the next free ordinal for ``chat_id`` — ``0`` for an empty chat and
    ``max(position) + 1`` otherwise.

    Skeleton (011 step 001): UNIMPLEMENTED.
    """
    session = await get_standalone_session()
    async with session:
        result = await session.exec(
            select(func.max(ChatMessage.position)).where(
                ChatMessage.chat_id == chat_id
            )
        )
        current_max = result.one()
        return 0 if current_max is None else current_max + 1
