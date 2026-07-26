"""SubAgent data access. Session-free public API — one module per entity.

Every function opens and closes its own session internally via
``engine.get_standalone_session()``; ``AsyncSession``, ``select()``, and ORM
row types never leak past this module (see ``docs/architecture/backend.md`` —
layer separation). Public functions accept and return ``SubAgent`` or plain
types.

Skeleton (008 step 001): signatures are frozen; bodies are UNIMPLEMENTED.
"""

from sqlmodel import select

from app.db.engine import get_standalone_session
from app.models.sub_agent import SubAgent


async def create(row: SubAgent) -> SubAgent:
    """Persist ``row`` and return it with its snowflake ``id`` populated."""
    session = await get_standalone_session()
    async with session:
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return row


async def get_by_id(sub_agent_id: int) -> SubAgent | None:
    """Return the ``SubAgent`` with ``sub_agent_id``, or ``None``."""
    session = await get_standalone_session()
    async with session:
        result = await session.exec(select(SubAgent).where(SubAgent.id == sub_agent_id))
        return result.one_or_none()


async def list_all() -> list[SubAgent]:
    """Return every ``SubAgent`` row, ordered by ``name`` ascending.

    Filters nothing — ``disabled`` rows are included; hiding is a caller concern.
    """
    session = await get_standalone_session()
    async with session:
        result = await session.exec(select(SubAgent).order_by(SubAgent.name))
        return list(result.all())


async def get_by_name(name: str) -> SubAgent | None:
    """Return the ``SubAgent`` whose ``name`` matches exactly, or ``None``.

    The pre-write uniqueness lookup behind feature 020's 409 refusal.
    """
    session = await get_standalone_session()
    async with session:
        result = await session.exec(select(SubAgent).where(SubAgent.name == name))
        return result.one_or_none()


async def update(row: SubAgent) -> None:
    """Persist changes to an already-existing ``row``. Returns nothing.

    Row-in / ``None``-out, mirroring ``db/llm_servers.py:62 update(server)``.
    """
    session = await get_standalone_session()
    async with session:
        session.add(row)
        await session.commit()
        await session.refresh(row)
