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
