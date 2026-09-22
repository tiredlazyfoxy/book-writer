"""Memo data access. Session-free public API — one module per entity.

Every function opens and closes its own session internally via
``engine.get_standalone_session()``; ``AsyncSession``, ``select()``, and ORM row
types never leak past this module (see ``docs/architecture/backend.md`` — layer
separation). Public functions accept and return ``Memo`` or plain types.

Timestamps are the **service's** policy, not this layer's: ``db/`` persists the
row it is handed. ``body`` is required and ``""`` is a real value — no function
here coerces ``""`` to ``None`` or the reverse. ``active=False`` and
``archived=False`` are likewise real values, never "absent".

``get_by_id`` performs **no ownership check**: scoping a read to its author is
``services/memos.py``'s job, and a ``db/`` module that silently filtered would
put the privacy rule in two places.

Deliberately four functions only (``create`` / ``get_by_id`` /
``list_for_author`` / ``update``): nothing in feature 026 reads this table any
other way, and ``db/`` modules are not speculatively widened.

**There is no delete function, and there never will be one.** Archive-not-delete
(UC-107, US-128.AC-3) is structural at the data layer, not merely an absent
route.

Skeleton (026 step 001): signatures are frozen.
"""

from sqlmodel import col, select

from app.db.engine import get_standalone_session
from app.models.memo import Memo


async def create(row: Memo) -> Memo:
    """Persist ``row`` and return the stored row.

    The snowflake ``id`` comes from the model's ``default_factory``; this layer
    never mints one. Sets no timestamps.
    """
    session = await get_standalone_session()
    async with session:
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return row


async def get_by_id(memo_id: int) -> Memo | None:
    """Return the ``Memo`` row with primary key ``memo_id``, or ``None``.

    No ownership check and no book scoping: the caller (the service) decides
    whose memo it is allowed to see.
    """
    session = await get_standalone_session()
    async with session:
        result = await session.exec(select(Memo).where(Memo.id == memo_id))
        return result.one_or_none()


async def list_for_author(
    book_id: int, user_id: int, include_archived: bool = False
) -> list[Memo]:
    """Return every memo for the ``(book_id, user_id)`` pair, ascending by
    ``ordinal``.

    ``include_archived`` defaults to ``False``, which excludes rows with
    ``archived is True``. When ``True``, archived rows come back alongside the
    live ones.

    **Never filters on ``active``** — inactive memos are listed exactly like
    active ones (US-127.AC-1); "reaches the assistant" is a derived reading the
    caller applies.
    """
    statement = (
        select(Memo)
        .where(Memo.book_id == book_id)
        .where(Memo.user_id == user_id)
    )

    if not include_archived:
        # Archived, never deleted — excluded unless explicitly asked for.
        statement = statement.where(col(Memo.archived) == False)  # noqa: E712

    statement = statement.order_by(col(Memo.ordinal))

    session = await get_standalone_session()
    async with session:
        result = await session.exec(statement)
        return list(result.all())


async def update(row: Memo) -> Memo:
    """Persist an already-mutated ``row`` and return the stored row.

    Row-in / row-out: the caller mutates the fields it wants (including
    ``modified_at`` — this layer sets no timestamps) and hands the whole row
    over.
    """
    session = await get_standalone_session()
    async with session:
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return row
