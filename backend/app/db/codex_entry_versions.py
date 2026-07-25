"""CodexEntryVersion data access. Session-free public API — one module per entity.

Every function opens and closes its own session internally via
``engine.get_standalone_session()``; ``AsyncSession``, ``select()``, and ORM
row types never leak past this module (see ``docs/architecture/backend.md`` —
layer separation). Public functions accept and return ``CodexEntryVersion`` or
plain types.

Skeleton (008 step 008): signatures are frozen; bodies are UNIMPLEMENTED.
"""

from sqlmodel import select

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


async def list_by_entry(entry_id: int) -> list[CodexEntryVersion]:
    """Return every ``CodexEntryVersion`` row whose ``entry_id`` equals ``entry_id``."""
    session = await get_standalone_session()
    async with session:
        result = await session.exec(
            select(CodexEntryVersion).where(CodexEntryVersion.entry_id == entry_id)
        )
        return list(result.all())
