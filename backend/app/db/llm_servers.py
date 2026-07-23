"""LlmServer data access. Session-free public API — one module per entity.

Every function opens and closes its own session internally via
``engine.get_standalone_session()``; ``AsyncSession``, ``select()``, and ORM
row types never leak past this module (see ``docs/architecture/backend.md`` —
layer separation). Public functions accept and return ``LlmServer`` or plain
types.

This module establishes the codebase's **first DELETE** (returns ``bool``) and
the **one sanctioned raw ``sqlalchemy.update()``** spot inside ``db/`` —
``clear_all_embedding`` — legitimate because ``db/`` is exactly where sessions
and SQLAlchemy live (feature 006 decision D5).

Skeleton (step 001): signatures are frozen; bodies are UNIMPLEMENTED.
"""

from sqlalchemy import update as sa_update
from sqlmodel import select

from app.db.engine import get_standalone_session
from app.models.llm_server import LlmServer


async def get_by_id(server_id: int) -> LlmServer | None:
    """Return the ``LlmServer`` with ``server_id``, or ``None`` if none exists."""
    session = await get_standalone_session()
    async with session:
        result = await session.exec(select(LlmServer).where(LlmServer.id == server_id))
        return result.one_or_none()


async def get_all() -> list[LlmServer]:
    """Return every ``LlmServer`` row, ordered by ``name``."""
    session = await get_standalone_session()
    async with session:
        result = await session.exec(select(LlmServer).order_by(LlmServer.name))
        return list(result.all())


async def get_active() -> list[LlmServer]:
    """Return only ``is_active`` ``LlmServer`` rows, ordered by ``name``."""
    session = await get_standalone_session()
    async with session:
        result = await session.exec(
            select(LlmServer)
            .where(LlmServer.is_active == True)  # noqa: E712
            .order_by(LlmServer.name)
        )
        return list(result.all())


async def create(server: LlmServer) -> LlmServer:
    """Persist a new ``server`` and return the persisted row with its assigned id."""
    session = await get_standalone_session()
    async with session:
        session.add(server)
        await session.commit()
        await session.refresh(server)
        return server


async def update(server: LlmServer) -> None:
    """Persist changes to an already-existing ``server``. Returns nothing."""
    session = await get_standalone_session()
    async with session:
        session.add(server)
        await session.commit()
        await session.refresh(server)


async def delete(server_id: int) -> bool:
    """Remove the row for ``server_id``.

    Returns ``True`` when a row was removed and ``False`` when no row matched —
    the codebase's first delete pattern (step 004's route uses the ``False`` case
    to distinguish a 404).
    """
    session = await get_standalone_session()
    async with session:
        result = await session.exec(select(LlmServer).where(LlmServer.id == server_id))
        server = result.one_or_none()
        if server is None:
            return False
        await session.delete(server)
        await session.commit()
        return True


async def clear_all_embedding() -> None:
    """Clear ``is_embedding`` (and ``embedding_model``) on **every** row.

    A bulk raw ``sqlalchemy.update()`` — the one sanctioned raw-SQLAlchemy spot
    inside ``db/`` (D5).
    """
    session = await get_standalone_session()
    async with session:
        await session.execute(
            sa_update(LlmServer).values(is_embedding=False, embedding_model=None)
        )
        await session.commit()


async def get_embedding_server() -> LlmServer | None:
    """Return the single row currently flagged ``is_embedding``, or ``None``."""
    session = await get_standalone_session()
    async with session:
        result = await session.exec(
            select(LlmServer).where(LlmServer.is_embedding == True)  # noqa: E712
        )
        return result.one_or_none()
