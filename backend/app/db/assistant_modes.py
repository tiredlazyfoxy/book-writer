"""AssistantMode data access. Session-free public API — one module per entity.

Every function opens and closes its own session internally via
``engine.get_standalone_session()``; ``AsyncSession``, ``select()``, and ORM
row types never leak past this module (see ``docs/architecture/backend.md`` —
layer separation). Public functions accept and return ``AssistantMode`` or
plain types.

Lookups are by the natural ``key`` primary key (not a snowflake id).

Skeleton (008 step 001): signatures are frozen; bodies are UNIMPLEMENTED.
(Step 003 adds ``seed_default_modes`` to this same module.)
"""

from sqlmodel import select

from app.db.engine import get_standalone_session
from app.models.assistant_mode import AssistantMode

# The fixed five system modes (assistant-config.md — not admin-creatable).
DEFAULT_MODE_KEYS: tuple[str, ...] = (
    "edit-character",
    "edit-location",
    "edit-fact",
    "write-chapter",
    "close-chapter",
)


async def create(row: AssistantMode) -> AssistantMode:
    """Persist ``row`` and return it. The ``key`` natural PK is caller-supplied."""
    session = await get_standalone_session()
    async with session:
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return row


async def get_by_id(key: str) -> AssistantMode | None:
    """Return the ``AssistantMode`` with primary key ``key``, or ``None``."""
    session = await get_standalone_session()
    async with session:
        result = await session.exec(
            select(AssistantMode).where(AssistantMode.key == key)
        )
        return result.one_or_none()


async def list_all() -> list[AssistantMode]:
    """Return every ``AssistantMode`` row."""
    session = await get_standalone_session()
    async with session:
        result = await session.exec(select(AssistantMode))
        return list(result.all())


async def update(row: AssistantMode) -> None:
    """Persist changes to an already-existing ``row``. Returns nothing.

    Row-in / ``None``-out, mirroring ``db/llm_servers.py:62 update(server)``: the
    caller mutates the fields it wants (including ``modified_at`` — ``db/`` never
    sets timestamps) and hands the whole row over.
    """
    session = await get_standalone_session()
    async with session:
        session.add(row)
        await session.commit()
        await session.refresh(row)


async def seed_default_modes() -> None:
    """Idempotently ensure the fixed five ``AssistantMode`` rows exist.

    Check-then-create over ``get_by_id`` + ``create`` for each fixed key
    (``edit-character``, ``edit-location``, ``edit-fact``, ``write-chapter``,
    ``close-chapter``): a present key is left untouched (never clobber an
    admin-edited ``system_prompt``); a missing key is created with
    ``system_prompt = None``. Safe to call any number of times.
    """
    for key in DEFAULT_MODE_KEYS:
        if await get_by_id(key) is None:
            await create(AssistantMode(key=key, system_prompt=None))
