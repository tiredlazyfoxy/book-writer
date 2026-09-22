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


async def update(row: ChapterNoteChangeset) -> ChapterNoteChangeset:
    """Persist changes to an already-existing ``ChapterNoteChangeset`` ``row``
    and return it (feature 016).

    Follows ``db/chapters.py:update``'s add / commit / refresh body, with one
    deliberate difference: it **returns the row**, because every caller here
    maps the stored changeset straight into a response and would otherwise have
    to re-read it. No timestamp (the service owns timestamp policy) and no
    not-found branch: the caller passes the already-mutated row.

    """
    session = await get_standalone_session()
    async with session:
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return row


async def delete_by_chapter(chapter_id: int) -> None:
    """Remove the ``ChapterNoteChangeset`` row for ``chapter_id``, if any
    (feature 016).

    ``chapter_id`` is unique on the table, so this removes at most one row.
    Deleting for a chapter that has no changeset is **not** an error — it is a
    no-op, which is what makes the close-run wipe idempotent. Returns nothing:
    the caller never needs to know whether a row was there.
    """
    session = await get_standalone_session()
    async with session:
        result = await session.exec(
            select(ChapterNoteChangeset).where(
                ChapterNoteChangeset.chapter_id == chapter_id
            )
        )
        row = result.one_or_none()
        if row is None:
            return None
        await session.delete(row)
        await session.commit()
        return None
