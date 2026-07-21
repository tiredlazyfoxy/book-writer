"""End-to-end tests for the health endpoint (step 003).

Exercised in-process against the real `app.main.app` via the `http_client`
fixture (httpx `ASGITransport`, no live server, no network). The app's startup
lifespan really runs (engine + DB + vector init) against a throwaway temp DB, so
`GET /api/health` flows through all four layers: route -> service ->
`db.health.ping()` -> `HealthResponse`.

Frozen interface (status.md -> Skeleton -> Step 003):
    GET /api/health                                     (routes/health.py)
    class HealthResponse(BaseModel): status: str; db: str   (models/schemas/health.py)

Expected values come from the step spec, never from implementation internals:
    - the endpoint returns HTTP 200 with body EXACTLY {"status": "ok", "db": "ready"}
      (003.app-factory-health-e2e.md DoD-1; HealthResponse shape in 003.context.md),
    - the response conforms to the HealthResponse schema (fields `status`/`db`) and
      the "ready" readiness is present on the happy path, where the DB/engine is
      actually initialized by the real lifespan (DoD-2).
"""

from app.models.schemas.health import HealthResponse


# DoD-1: GET /api/health returns HTTP 200 with body exactly
# {"status": "ok", "db": "ready"}, exercised in-process via http_client.
async def test_health_returns_200_and_exact_body__DoD1(http_client):
    resp = await http_client.get("/api/health")

    assert resp.status_code == 200
    # Exact body — no extra keys, no missing keys, exact spec values.
    assert resp.json() == {"status": "ok", "db": "ready"}


# DoD-2: the 200/ready result reflects the full flow — the response conforms to
# the HealthResponse schema (fields `status`, `db`) and readiness ("ready") is
# present because the real lifespan actually initialized the DB.
async def test_health_response_conforms_to_schema__DoD2(http_client):
    resp = await http_client.get("/api/health")
    body = resp.json()

    # The JSON is exactly the two frozen HealthResponse fields — nothing more,
    # nothing less — and re-validates cleanly through the schema contract.
    assert set(body.keys()) == {"status", "db"}
    model = HealthResponse.model_validate(body)
    assert isinstance(model.status, str)
    assert isinstance(model.db, str)
    # Happy-path spec values: status "ok", DB readiness "ready".
    assert model.status == "ok"
    assert model.db == "ready"


# DoD-2 (readiness reflects an actually-initialized DB, not an arbitrary value):
# within the running app lifespan the real readiness probe reports True, and the
# endpoint independently reports "ready" — tying the reported readiness to a
# genuinely initialized database as far as the public API allows black-box.
async def test_health_ready_reflects_initialized_db__DoD2(http_client):
    from app.db.health import ping

    # The lifespan (driven by the fixture) has initialized the engine + DB, so a
    # direct readiness probe succeeds.
    assert await ping() is True

    resp = await http_client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["db"] == "ready"
