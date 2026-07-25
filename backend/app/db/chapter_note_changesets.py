"""ChapterNoteChangeset data access. Session-free public API — one module per entity.

Every function opens and closes its own session internally via
``engine.get_standalone_session()``; ``AsyncSession``, ``select()``, and ORM
row types never leak past this module (see ``docs/architecture/backend.md`` —
layer separation). Public functions accept and return ``ChapterNoteChangeset``
or plain types.

Skeleton (008 step 007): signatures are frozen; bodies are UNIMPLEMENTED.
"""

from sqlmodel import select

from app.db.engine import get_standalone_session
from app.models.chapter_notes import ChapterNoteChangeset


async def create(row: ChapterNoteChangeset) -> ChapterNoteChangeset:
    """Persist ``row`` and return it with its snowflake ``id`` populated."""
    session = await get_standalone_session()
    async with session:
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return row


async def get_by_id(changeset_id: int) -> ChapterNoteChangeset | None:
    """Return the ``ChapterNoteChangeset`` with primary key ``changeset_id``, or ``None``."""
    session = await get_standalone_session()
    async with session:
        result = await session.exec(
            select(ChapterNoteChangeset).where(
                ChapterNoteChangeset.id == changeset_id
            )
        )
        return result.one_or_none()


async def get_by_chapter(chapter_id: int) -> ChapterNoteChangeset | None:
    """Return the single ``ChapterNoteChangeset`` for ``chapter_id``, or ``None``.

    ``chapter_id`` is unique on the table, so this returns exactly one row (via
    ``.one_or_none()``) — never a list.
    """
    session = await get_standalone_session()
    async with session:
        result = await session.exec(
            select(ChapterNoteChangeset).where(
                ChapterNoteChangeset.chapter_id == chapter_id
            )
        )
        return result.one_or_none()
