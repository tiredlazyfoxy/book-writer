"""ModeSubagent data access. Session-free public API — one module per entity.

Every function opens and closes its own session internally via
``engine.get_standalone_session()``; ``AsyncSession``, ``select()``, and ORM
row types never leak past this module (see ``docs/architecture/backend.md`` —
layer separation). Public functions accept and return ``ModeSubagent`` or plain
types.

Covers the mode-to-sub-agent link rows: ``create``, ``get_by_id``, both lookup
directions (``list_by_mode`` / ``list_by_sub_agent``) and the two
count-returning bulk deletes (``delete_by_mode`` / ``delete_by_sub_agent``;
``0`` is a normal result).
"""

from sqlmodel import select

from app.db.engine import get_standalone_session
from app.models.mode_subagent import ModeSubagent


async def create(row: ModeSubagent) -> ModeSubagent:
    """Persist ``row`` and return it with its snowflake ``id`` populated."""
    session = await get_standalone_session()
    async with session:
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return row


async def get_by_id(id: int) -> ModeSubagent | None:
    """Return the ``ModeSubagent`` with primary key ``id``, or ``None``."""
    session = await get_standalone_session()
    async with session:
        result = await session.exec(
            select(ModeSubagent).where(ModeSubagent.id == id)
        )
        return result.one_or_none()


async def list_by_mode(mode_key: str) -> list[ModeSubagent]:
    """Return every ``ModeSubagent`` row whose ``mode_key`` equals ``mode_key``."""
    session = await get_standalone_session()
    async with session:
        result = await session.exec(
            select(ModeSubagent).where(ModeSubagent.mode_key == mode_key)
        )
        return list(result.all())


async def list_by_sub_agent(sub_agent_id: int) -> list[ModeSubagent]:
    """Return every ``ModeSubagent`` row whose ``sub_agent_id`` matches.

    The accessible-modes reverse lookup — the same one row set ``list_by_mode``
    reads from the mode side, read from the sub-agent side (US-112.AC-2).
    """
    session = await get_standalone_session()
    async with session:
        result = await session.exec(
            select(ModeSubagent).where(ModeSubagent.sub_agent_id == sub_agent_id)
        )
        return list(result.all())


async def delete_by_mode(mode_key: str) -> int:
    """Delete every ``ModeSubagent`` row for ``mode_key``; return the count removed.

    Count-returning bulk delete (zero is a normal result). Removes only this
    mode's slice — a sub-agent's links to other modes are untouched.
    """
    session = await get_standalone_session()
    async with session:
        result = await session.exec(
            select(ModeSubagent).where(ModeSubagent.mode_key == mode_key)
        )
        rows = list(result.all())
        for row in rows:
            await session.delete(row)
        await session.commit()
        return len(rows)


async def delete_by_sub_agent(sub_agent_id: int) -> int:
    """Delete every ``ModeSubagent`` row for ``sub_agent_id``; return the count removed.

    Count-returning bulk delete (zero is a normal result). Removes only this
    sub-agent's slice — a mode's links to other sub-agents are untouched. Also the
    primitive the disable cascade uses.
    """
    session = await get_standalone_session()
    async with session:
        result = await session.exec(
            select(ModeSubagent).where(ModeSubagent.sub_agent_id == sub_agent_id)
        )
        rows = list(result.all())
        for row in rows:
            await session.delete(row)
        await session.commit()
        return len(rows)
