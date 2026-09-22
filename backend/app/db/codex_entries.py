"""CodexEntry data access. Session-free public API — one module per entity.

Every function opens and closes its own session internally via
``engine.get_standalone_session()``; ``AsyncSession``, ``select()``, and ORM
row types never leak past this module (see ``docs/architecture/backend.md`` —
layer separation). Public functions accept and return ``CodexEntry`` or plain
types.

Skeleton (008 step 008): signatures are frozen; bodies are UNIMPLEMENTED.
Skeleton (013 step 001): ``list_by_book`` is widened with the kind / archived /
needle filters and deterministic ordering, and ``update`` is added.
"""

from sqlalchemy import func, or_
from sqlmodel import col, select

from app.db.engine import get_standalone_session
from app.models.codex_entry import CodexEntry, CodexKind


async def create(row: CodexEntry) -> CodexEntry:
    """Persist ``row`` and return it with its snowflake ``id`` populated."""
    session = await get_standalone_session()
    async with session:
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return row


async def get_by_id(entry_id: int) -> CodexEntry | None:
    """Return the ``CodexEntry`` with primary key ``entry_id``, or ``None``."""
    session = await get_standalone_session()
    async with session:
        result = await session.exec(
            select(CodexEntry).where(CodexEntry.id == entry_id)
        )
        return result.one_or_none()


async def list_by_book(
    book_id: int,
    kind: CodexKind | None = None,
    include_archived: bool = False,
    needle: str | None = None,
) -> list[CodexEntry]:
    """Return ``book_id``'s ``CodexEntry`` rows, filtered and deterministically
    ordered.

    - ``kind`` — when given, only entries of that :class:`CodexKind`.
    - ``include_archived`` — archived rows are **excluded** unless this is true.
    - ``needle`` — case-insensitive substring matched against ``name`` **or**
      ``body``; a row with a null ``name`` is matched on ``body`` alone. ``None``
      or an empty needle is no filter at all.

    Ordering is explicit — ``name`` ascending with **null names last**, then
    ``id`` — so repeated calls are stable regardless of insertion order.
    Returns detached rows.
    """
    statement = select(CodexEntry).where(CodexEntry.book_id == book_id)

    if kind is not None:
        statement = statement.where(CodexEntry.kind == kind)

    if not include_archived:
        # Archived, never deleted — excluded unless explicitly asked for.
        statement = statement.where(col(CodexEntry.archived) == False)

    if needle:
        # Case-insensitive substring over ``name`` OR ``body``. ``lower(NULL)``
        # is NULL, so a null-named row simply falls through to the body arm
        # (NULL OR TRUE is TRUE) — a fact is matched on its body alone.
        pattern = needle.lower()
        statement = statement.where(
            or_(
                func.lower(col(CodexEntry.name)).contains(
                    pattern, autoescape=True
                ),
                func.lower(col(CodexEntry.body)).contains(
                    pattern, autoescape=True
                ),
            )
        )

    # SQLite sorts NULL *first* under a plain ``ORDER BY name``, so nulls-last is
    # stated explicitly: ``name IS NULL`` yields 0 for named rows and 1 for the
    # unnamed ones, which sorts the facts to the end. ``id`` breaks ties.
    statement = statement.order_by(
        col(CodexEntry.name).is_(None),
        col(CodexEntry.name),
        col(CodexEntry.id),
    )

    session = await get_standalone_session()
    async with session:
        result = await session.exec(statement)
        return list(result.all())


async def list_all_unarchived() -> list[CodexEntry]:
    """Return every non-archived ``CodexEntry`` across **all** books, by ``id``.

    The vector index's row selector (``db/vector.py`` →
    ``VECTOR_SOURCE_REGISTRY``): a full rebuild is instance-wide, not per book,
    so this deliberately takes no ``book_id``. Ordering by ``id`` makes a rebuild
    deterministic.

    Archived rows are excluded **here**, by the selector, rather than by a
    query-time predicate — ``retrieval.md`` is explicit that "an 'exclude
    archived' predicate is a rule every future consumer would have to remember
    and one of them would eventually forget". Returns detached rows.
    """
    statement = (
        select(CodexEntry)
        .where(col(CodexEntry.archived) == False)
        .order_by(col(CodexEntry.id))
    )

    session = await get_standalone_session()
    async with session:
        result = await session.exec(statement)
        return list(result.all())


async def update(row: CodexEntry) -> CodexEntry:
    """Persist an already-mutated ``CodexEntry`` and return the stored row.

    Row-in / row-out, following ``db/chats.py:update``: the caller mutates the
    fields it wants (including ``modified_at`` / ``modified_by`` — the codex
    service owns those, this layer sets no timestamps) and hands the whole row
    over. Session-free like every other function in the module; no ORM object
    leaks out.
    """
    session = await get_standalone_session()
    async with session:
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return row
