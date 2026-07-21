"""Session-free DB readiness probe.

``ping`` opens and closes its own session via ``engine.get_standalone_session``
and returns a plain readiness signal. No ``AsyncSession``, ``select()``, or ORM
row type leaks past this module (see ``docs/architecture/backend.md``).

Skeleton (step 002): signature is frozen; body is UNIMPLEMENTED.
"""

from sqlalchemy import text

from app.db import engine


async def ping() -> bool:
    """Return ``True`` when the database answers a trivial readiness probe.

    Opens its own session via ``get_standalone_session()``, runs a
    ``SELECT 1``-style probe, and returns a plain bool. No session or ORM type
    escapes.
    """
    session = await engine.get_standalone_session()
    try:
        result = await session.execute(text("SELECT 1"))
        return result.scalar_one() == 1
    finally:
        await session.close()
