"""ChapterTextRevision data access. Session-free API — one module per entity.

Every function opens and closes its own session internally via
``engine.get_standalone_session()``; ``AsyncSession``, ``select()``, and ORM
row types never leak past this module (see ``docs/architecture/backend.md`` —
layer separation). Public functions accept and return ``ChapterTextRevision`` or
plain types.

Skeleton (008 step 006): signatures are frozen; bodies are UNIMPLEMENTED.
"""

from sqlmodel import select

from app.db.engine import get_standalone_session
from app.models.chapter_text_revision import ChapterTextRevision


async def create(row: ChapterTextRevision) -> ChapterTextRevision:
    """Persist ``row`` and return it with its snowflake ``id`` populated."""
    session = await get_standalone_session()
    async with session:
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return row


async def get_by_id(revision_id: int) -> ChapterTextRevision | None:
    """Return the ``ChapterTextRevision`` with PK ``revision_id``, or ``None``."""
    session = await get_standalone_session()
    async with session:
        result = await session.exec(
            select(ChapterTextRevision).where(ChapterTextRevision.id == revision_id)
        )
        return result.one_or_none()


async def list_by_chapter(chapter_id: int) -> list[ChapterTextRevision]:
    """Return every ``ChapterTextRevision`` whose ``chapter_id`` equals ``chapter_id``."""
    session = await get_standalone_session()
    async with session:
        result = await session.exec(
            select(ChapterTextRevision).where(
                ChapterTextRevision.chapter_id == chapter_id
            )
        )
        return list(result.all())
