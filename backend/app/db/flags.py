"""Flag data access. Session-free public API — one module per entity.

Every function opens and closes its own session internally via
``engine.get_standalone_session()``; ``AsyncSession``, ``select()``, and ORM
row types never leak past this module (see ``docs/architecture/backend.md`` —
layer separation). Public functions accept and return ``Flag`` or plain types.

Skeleton (008 step 007): signatures are frozen; bodies are UNIMPLEMENTED.
"""

from sqlmodel import select

from app.db.engine import get_standalone_session
from app.models.flag import Flag, FlagOrigin


async def create(row: Flag) -> Flag:
    """Persist ``row`` and return it with its snowflake ``id`` populated."""
    session = await get_standalone_session()
    async with session:
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return row


async def get_by_id(flag_id: int) -> Flag | None:
    """Return the ``Flag`` with primary key ``flag_id``, or ``None``."""
    session = await get_standalone_session()
    async with session:
        result = await session.exec(select(Flag).where(Flag.id == flag_id))
        return result.one_or_none()


async def list_by_chapter(chapter_id: int) -> list[Flag]:
    """Return every ``Flag`` row whose ``chapter_id`` equals ``chapter_id``."""
    session = await get_standalone_session()
    async with session:
        result = await session.exec(
            select(Flag).where(Flag.chapter_id == chapter_id)
        )
        return list(result.all())


async def update(row: Flag) -> Flag:
    """Persist changes to an already-existing ``Flag`` ``row`` and return it
    (feature 016).

    Follows ``db/chapters.py:update``'s add / commit / refresh body, returning
    the row because the resolve path maps the stored flag straight into a
    response. No timestamp (the service owns timestamp policy — ``resolved_at``
    is stamped there) and no not-found branch: the caller passes the
    already-mutated row.
    """
    session = await get_standalone_session()
    async with session:
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return row


async def delete_check_flags_by_chapter(chapter_id: int) -> None:
    """Remove every ``origin=check`` ``Flag`` of ``chapter_id``, leaving
    ``origin=person`` flags untouched (feature 016, decision D6).

    The origin filter is part of the **query**, not a policy the caller applies
    afterwards, so no ``Flag`` row ever leaves this module for a caller to sift.
    Deleting when there is nothing to delete is a no-op, never an error.
    Returns nothing.
    """
    session = await get_standalone_session()
    async with session:
        result = await session.exec(
            select(Flag)
            .where(Flag.chapter_id == chapter_id)
            .where(Flag.origin == FlagOrigin.check)
        )
        for row in result.all():
            await session.delete(row)
        await session.commit()
        return None
