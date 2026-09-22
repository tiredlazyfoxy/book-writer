"""ChapterAuthorPrompt data access. Session-free public API — one module per
entity.

Every function opens and closes its own session internally via
``engine.get_standalone_session()``; ``AsyncSession``, ``select()``, and ORM row
types never leak past this module (see ``docs/architecture/backend.md`` — layer
separation). Public functions accept and return ``ChapterAuthorPrompt`` or plain
types.

Timestamps are the **service's** policy, not this layer's: ``db/`` persists the
row it is handed. ``system_prompt`` is required and ``""`` is a real value — no
function here coerces ``""`` to ``None`` or the reverse.

Deliberately three functions only (``create`` / ``get_by_chapter_and_user`` /
``update``): nothing in feature 014 reads this table any other way, and ``db/``
modules are not speculatively widened — no list, no delete, no ``get_by_id``.

Skeleton (014 step 001): signatures are frozen.
"""

from sqlmodel import select

from app.db.engine import get_standalone_session
from app.models.chapter_author_prompt import ChapterAuthorPrompt


async def create(row: ChapterAuthorPrompt) -> ChapterAuthorPrompt:
    """Persist ``row`` and return it with its snowflake ``id`` populated."""
    session = await get_standalone_session()
    async with session:
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return row


async def get_by_chapter_and_user(
    chapter_id: int, user_id: int
) -> ChapterAuthorPrompt | None:
    """Return the ``ChapterAuthorPrompt`` row for the ``(chapter_id, user_id)``
    pair, or ``None`` when that pair has no row. Keys on the natural unique
    pair, not the surrogate ``id``.
    """
    session = await get_standalone_session()
    async with session:
        result = await session.exec(
            select(ChapterAuthorPrompt)
            .where(ChapterAuthorPrompt.chapter_id == chapter_id)
            .where(ChapterAuthorPrompt.user_id == user_id)
        )
        return result.one_or_none()


async def update(row: ChapterAuthorPrompt) -> ChapterAuthorPrompt:
    """Persist an already-mutated ``row`` and return the stored row.

    Row-in / row-out, following ``db/book_author_prompts.py:update``: the caller
    mutates the fields it wants (including ``modified_at`` — this layer sets no
    timestamps) and hands the whole row over.
    """
    session = await get_standalone_session()
    async with session:
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return row
