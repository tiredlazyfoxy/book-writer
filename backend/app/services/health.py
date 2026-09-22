"""Health service — readiness orchestration.

Business logic for the walking-skeleton health check: probe DB readiness via
``db.health.ping()`` and assemble a :class:`HealthResponse`. No ``session`` /
``select()`` / ORM access here (see ``docs/architecture/backend.md`` — layer
separation).

Skeleton (step 003): signature is frozen; body is UNIMPLEMENTED.
"""

from app.db import health
from app.models.schemas.health import HealthResponse


async def check_health() -> HealthResponse:
    """Assemble the readiness response.

    Calls :func:`app.db.health.ping` and maps the boolean readiness signal onto
    a :class:`HealthResponse` (``status``/``db`` markers). Readiness must
    originate from the probe, not a hardcoded literal.
    """
    ready = await health.ping()
    return HealthResponse(
        status="ok" if ready else "error",
        db="ready" if ready else "unavailable",
    )
