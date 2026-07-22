"""User data access. Session-free public API — one module per entity.

Every function opens and closes its own session internally via
``engine.get_standalone_session()``; ``AsyncSession``, ``select()``, and ORM
row types never leak past this module (see ``docs/architecture/backend.md`` —
layer separation). Public functions accept and return ``User`` or plain types.

Skeleton (step 001): signatures are frozen; bodies are UNIMPLEMENTED.
"""

from sqlalchemy.exc import OperationalError
from sqlmodel import select

from app.db.engine import get_standalone_session
from app.models.user import User, UserRole


async def create(user: User) -> User:
    """Persist ``user`` and return it with its generated ``id`` populated.

    The ``id`` is an application-generated snowflake, already populated at
    construction (``default_factory=generate_id``) before the insert — it is
    persisted as-is, never DB-assigned. Adds and commits inside its own session;
    the ``refresh`` re-loads the row's attributes (expired on commit), not to
    learn the id.
    """
    session = await get_standalone_session()
    async with session:
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


async def get_by_username(username: str) -> User | None:
    """Return the ``User`` with ``username``, or ``None`` if none exists."""
    session = await get_standalone_session()
    async with session:
        result = await session.exec(select(User).where(User.username == username))
        return result.one_or_none()


async def get_by_id(user_id: int) -> User | None:
    """Return the ``User`` with ``user_id``, or ``None`` if none exists."""
    session = await get_standalone_session()
    async with session:
        result = await session.exec(select(User).where(User.id == user_id))
        return result.one_or_none()


async def admin_exists() -> bool:
    """Return whether at least one user with the ``admin`` role exists.

    Returns ``False`` **gracefully** on a cold instance where the ``users``
    table has not yet been created — the missing-table error is caught, not
    propagated (backs first-run detection, DoD-5).
    """
    session = await get_standalone_session()
    try:
        async with session:
            result = await session.exec(
                select(User).where(User.role == UserRole.admin).limit(1)
            )
            return result.first() is not None
    except OperationalError:
        # ``users`` table does not exist yet (cold instance) — treat as "no admin".
        return False
