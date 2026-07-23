"""DB-layer import/export primitives. Session-free public API.

Generic, serialization-free building blocks for the streaming gzip-JSONL
import/export mechanism. All functions manage their own sessions internally
via ``engine.get_standalone_session()`` — callers never touch ``AsyncSession``,
``select()``, or any ORM primitive, and **no serialization happens here** (that
is the ``services/`` layer's job; see ``docs/architecture/backend.md``).

Skeleton (step 004): signatures are frozen; bodies are UNIMPLEMENTED.
"""

import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

from sqlmodel import SQLModel, select

from app.db import engine

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=SQLModel)


async def export_table(
    model_class: type[T],
    callback: Callable[[T], None | Awaitable[None]],
) -> None:
    """Iterate every row of ``model_class``, invoking ``callback(row)`` per row.

    Opens and closes its own session internally; streams row-by-row (no bulk
    ``SELECT *`` collected into memory). The callback — owned by the service
    layer — does any serialization. Callback may be sync or async; an awaitable
    return is awaited.
    """
    session = await engine.get_standalone_session()
    async with session:
        result = await session.stream(select(model_class))
        async for row in result.scalars():
            outcome = callback(row)
            if outcome is not None:
                await outcome


async def upsert_batch(items: list[SQLModel]) -> None:
    """UPSERT (merge) a batch of model instances in one committed transaction.

    ``session.merge`` per item plus a single commit for the whole batch —
    the streaming UPSERT primitive. Idempotent by primary key. Empty batch is
    a no-op. Session managed internally.
    """
    if not items:
        return

    session = await engine.get_standalone_session()
    async with session:
        for item in items:
            await session.merge(item)
        await session.commit()


async def run_vector_rebuild() -> None:
    """Rebuild the LanceDB sidecar index from SQLite source rows after import.

    Delegates to :func:`app.db.vector.rebuild_index` so the post-import rebuild
    and the admin rebuild button share one path (D6). The returned indexed-row
    count is discarded — this hook's signature is ``-> None``.
    """
    from app.db import vector

    await vector.rebuild_index()
