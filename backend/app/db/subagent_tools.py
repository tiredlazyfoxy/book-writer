"""SubagentTool data access. Session-free public API — one module per entity.

Every function opens and closes its own session internally via
``engine.get_standalone_session()``; ``AsyncSession``, ``select()``, and ORM
row types never leak past this module (see ``docs/architecture/backend.md`` —
layer separation). Public functions accept and return ``SubagentTool`` or plain
types.

Skeleton (008 step 002): signatures are frozen; bodies are UNIMPLEMENTED.
"""

from sqlmodel import select

from app.db.engine import get_standalone_session
from app.models.subagent_tool import SubagentTool


async def create(row: SubagentTool) -> SubagentTool:
    """Persist ``row`` and return it with its snowflake ``id`` populated."""
    session = await get_standalone_session()
    async with session:
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return row


async def get_by_id(id: int) -> SubagentTool | None:
    """Return the ``SubagentTool`` with primary key ``id``, or ``None``."""
    session = await get_standalone_session()
    async with session:
        result = await session.exec(
            select(SubagentTool).where(SubagentTool.id == id)
        )
        return result.one_or_none()


async def list_by_sub_agent(sub_agent_id: int) -> list[SubagentTool]:
    """Return every ``SubagentTool`` row whose ``sub_agent_id`` matches."""
    session = await get_standalone_session()
    async with session:
        result = await session.exec(
            select(SubagentTool).where(SubagentTool.sub_agent_id == sub_agent_id)
        )
        return list(result.all())
