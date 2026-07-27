"""CodexEntryVersion data access. Session-free public API — one module per entity.

Every function opens and closes its own session internally via
``engine.get_standalone_session()``; ``AsyncSession``, ``select()``, and ORM
row types never leak past this module (see ``docs/architecture/backend.md`` —
layer separation). Public functions accept and return ``CodexEntryVersion`` or
plain types.

Skeleton (008 step 008): signatures are frozen; bodies are UNIMPLEMENTED.
Skeleton (013 step 001): ``next_generation`` is added. ``list_by_entry`` keeps
its signature — only its ordering changes, which is behavior, not interface.
"""

from sqlalchemy import func
from sqlmodel import col, select

from app.db.engine import get_standalone_session
from app.models.codex_entry_version import CodexEntryVersion


async def create(row: CodexEntryVersion) -> CodexEntryVersion:
    """Persist ``row`` and return it with its snowflake ``id`` populated."""
    session = await get_standalone_session()
    async with session:
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return row


async def get_by_id(version_id: int) -> CodexEntryVersion | None:
    """Return the ``CodexEntryVersion`` with primary key ``version_id``, or ``None``."""
    session = await get_standalone_session()
    async with session:
        result = await session.exec(
            select(CodexEntryVersion).where(CodexEntryVersion.id == version_id)
        )
        return result.one_or_none()


async def next_generation(entry_id: int) -> int:
    """Return the 1-based ``generation`` the *next* version row for ``entry_id``
    should carry: ``1`` when the entry has no version rows, otherwise one more
    than the highest existing ``generation`` (independent of insertion order).
    """
    session = await get_standalone_session()
    async with session:
        result = await session.exec(
            select(func.max(CodexEntryVersion.generation)).where(
                CodexEntryVersion.entry_id == entry_id
            )
        )
        current_max = result.one()
        return 1 if current_max is None else current_max + 1


async def list_by_entry(entry_id: int) -> list[CodexEntryVersion]:
    """Return every ``CodexEntryVersion`` row whose ``entry_id`` equals
    ``entry_id``, in **ascending ``generation``** order.
    """
    session = await get_standalone_session()
    async with session:
        result = await session.exec(
            select(CodexEntryVersion)
            .where(CodexEntryVersion.entry_id == entry_id)
            .order_by(col(CodexEntryVersion.generation))
        )
        return list(result.all())
