"""Health route — HTTP layer for ``GET /api/health``.

HTTP only: delegates to the health service and returns its
:class:`HealthResponse`. No business logic, no DB access here (see
``docs/architecture/backend.md`` — layer separation). The router owns its own
``/api`` prefix (Decision 7); mounted with a bare ``app.include_router(...)``.

Skeleton (step 003): the router object and route registration are frozen; the
handler body is UNIMPLEMENTED.
"""

from fastapi import APIRouter

from app.models.schemas.health import HealthResponse
from app.services import health as health_service

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def get_health() -> HealthResponse:
    """Return DB-readiness through all four layers.

    Delegates to :func:`app.services.health.check_health` and returns the
    resulting :class:`HealthResponse`.
    """
    return await health_service.check_health()
