"""ModeTool data access. Session-free public API — one module per entity.

Every function opens and closes its own session internally via
``engine.get_standalone_session()``; ``AsyncSession``, ``select()``, and ORM
row types never leak past this module (see ``docs/architecture/backend.md`` —
layer separation). Public functions accept and return ``ModeTool`` or plain
types.

Skeleton (008 step 002): signatures are frozen; bodies are UNIMPLEMENTED.
"""

from sqlmodel import select

from app.db.engine import get_standalone_session
from app.models.mode_tool import ModeTool


async def create(row: ModeTool) -> ModeTool:
    """Persist ``row`` and return it with its snowflake ``id`` populated."""
    session = await get_standalone_session()
    async with session:
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return row


async def get_by_id(id: int) -> ModeTool | None:
    """Return the ``ModeTool`` with primary key ``id``, or ``None``."""
    session = await get_standalone_session()
    async with session:
        result = await session.exec(select(ModeTool).where(ModeTool.id == id))
        return result.one_or_none()


async def list_by_mode(mode_key: str) -> list[ModeTool]:
    """Return every ``ModeTool`` row whose ``mode_key`` equals ``mode_key``."""
    session = await get_standalone_session()
    async with session:
        result = await session.exec(
            select(ModeTool).where(ModeTool.mode_key == mode_key)
        )
        return list(result.all())
