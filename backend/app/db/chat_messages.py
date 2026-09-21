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

Feature 027 step 001: ``list_transcript``, ``side_chat_exists``,
``clear_side_chat`` and ``delete_by_side_chat`` are the module's first filtered
read beyond chat_id / role, its first update and its FIRST HARD DELETE. The two
mutators are bulk raw ``sqlalchemy.update()`` / ``sqlalchemy.delete()``
statements — the same sanctioned shape as ``db/llm_servers.py``'s
``clear_all_embedding`` (feature 006 decision D5): ``db/`` is exactly where
sessions and SQLAlchemy live, and a single scoped statement is the correct
primitive where per-row iteration would be wasteful and racier.

Why a hard delete is sanctioned here (027 → D-D): deleting a side chat is
FEAT-022's product rule (US-140 — its messages are removed permanently) and the
chat family's first exception to archive-only — the second sanctioned exception
in the project, alongside FEAT-011's destroy (``docs/product/glossary.md``,
FEAT-022 note, CS4). ``delete_by_side_chat`` touches ``chat_messages`` rows
ONLY, scoped by both ``chat_id`` and ``side_chat_id``; no other table is
written, so anything saved during the side chat (a codex entry, a chapter
change, a memo) is structurally untouched. Surviving rows are NOT renumbered —
``next_position`` is ``max + 1`` and tolerates gaps (the chapters-DELETE
precedent). The service that calls it (027 step 003) links back here rather
than restating this.
"""

from sqlalchemy import delete as sa_delete
from sqlalchemy import func, or_
from sqlalchemy import update as sa_update
from sqlmodel import col, select

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


async def list_transcript(
    chat_id: int, active_side_chat_id: int | None
) -> list[ChatMessage]:
    """Return the rows of ``chat_id`` the turn may see, ordered by ``position``
    ascending (027 → D-C, UC-115): every main-line row (``side_chat_id`` is
    ``NULL``) plus every row whose ``side_chat_id`` equals
    ``active_side_chat_id``. With ``None`` it returns main-line rows only —
    rows carrying ANY side-chat id are excluded. Rows of another chat never
    appear.

    This is a transcript filter over one column, not context assembly: nothing
    is retrieved, ranked or truncated. Same shape as :func:`list_by_chat_ordered`
    with one more ``WHERE`` clause.
    """
    session = await get_standalone_session()
    async with session:
        statement = (
            select(ChatMessage)
            .where(ChatMessage.chat_id == chat_id)
            .order_by(ChatMessage.position)
        )
        if active_side_chat_id is None:
            statement = statement.where(col(ChatMessage.side_chat_id).is_(None))
        else:
            statement = statement.where(
                or_(
                    col(ChatMessage.side_chat_id).is_(None),
                    ChatMessage.side_chat_id == active_side_chat_id,
                )
            )
        result = await session.exec(statement)
        return list(result.all())


async def side_chat_exists(chat_id: int, side_chat_id: int) -> bool:
    """Return whether at least one row of ``chat_id`` carries
    ``side_chat_id`` (027 → D-A, the ROW half of the existence rule).

    A side chat exists iff ``Chat.active_side_chat_id == side_chat_id`` OR a
    row of that chat carries the id; this function answers only the row half —
    the service adds the pointer half. A row with that id in a DIFFERENT chat
    does not count.
    """
    session = await get_standalone_session()
    async with session:
        result = await session.exec(
            select(func.count(ChatMessage.id))
            .where(ChatMessage.chat_id == chat_id)
            .where(ChatMessage.side_chat_id == side_chat_id)
        )
        total = result.one()
        return total is not None and int(total) > 0


async def clear_side_chat(chat_id: int, side_chat_id: int) -> int:
    """Set ``side_chat_id`` to ``NULL`` on exactly the rows of ``chat_id`` that
    carry ``side_chat_id`` and return the number of rows changed (the inject
    primitive — 027 → US-139, storage half).

    ``position`` and every other column stay untouched, so the messages become
    ordinary main-line messages in place, keeping order. Rows of other side
    chats, main-line rows and rows of other chats are never touched. Returns
    ``0`` and changes nothing when no row carries the id. The filter is on BOTH
    ``chat_id`` and ``side_chat_id`` — the chat scope is what makes this safe
    to call from an ownership-checked service without a second lookup.
    """
    session = await get_standalone_session()
    async with session:
        result = await session.execute(
            sa_update(ChatMessage)
            .where(ChatMessage.chat_id == chat_id)
            .where(ChatMessage.side_chat_id == side_chat_id)
            .values(side_chat_id=None)
        )
        await session.commit()
        return int(result.rowcount)


async def delete_by_side_chat(chat_id: int, side_chat_id: int) -> int:
    """Delete exactly the rows of ``chat_id`` that carry ``side_chat_id`` and
    return the number deleted (027 → US-140, storage half).

    The module's FIRST HARD DELETE — see the module docstring for why it is
    sanctioned (D-D). Touches ``chat_messages`` rows only; surviving rows keep
    their ``position`` (no renumbering — ``next_position`` tolerates gaps).
    Returns ``0`` and changes nothing when no row carries the id. The filter is
    on BOTH ``chat_id`` and ``side_chat_id``.
    """
    session = await get_standalone_session()
    async with session:
        result = await session.execute(
            sa_delete(ChatMessage)
            .where(ChatMessage.chat_id == chat_id)
            .where(ChatMessage.side_chat_id == side_chat_id)
        )
        await session.commit()
        return int(result.rowcount)
