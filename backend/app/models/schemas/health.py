"""Health/readiness response schema.

The typed contract returned by ``GET /api/health``. Declarative Pydantic
schema — a plain typed data shape, no logic. Field names/types are frozen by
the skeleton (step 003).
"""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Readiness result surfaced by the health endpoint.

    - ``status`` — overall service liveness marker (``"ok"``).
    - ``db`` — database readiness marker (``"ready"`` when
      ``db.health.ping()`` succeeds). Originates from the probe, never a
      route-level constant.
    """

    status: str
    db: str
