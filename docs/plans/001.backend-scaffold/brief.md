# 001.backend-scaffold — Backend scaffold
<!-- roadmap:start -->
- **Stage:** 0.scaffold · **Track:** multi-step · **Size:** M
- **Depends on:** none

## Definition
Stand up the FastAPI backend as a runnable, testable skeleton on the enforced
4-layer structure. A developer can start uvicorn, hit a health endpoint that
flows through all four layers, and run the pytest suite green. Establishes
`app/{routes,services,db,models}/`, the async SQLite engine (SQLModel +
aiosqlite, `create_all`), pydantic-settings config (`.env.local`,
`BOOKWRITER_DB_PATH`), and the httpx test harness. No user-facing feature, no
real table.

## Scope
**In:** pyproject.toml + `.venv`; app factory + uvicorn entry; 4-layer package
skeleton with dependency-direction respected; async SQLite engine +
`create_all` bootstrap; settings/config loader; one health route end-to-end;
pytest + pytest-asyncio + httpx harness with one passing test; the JSONL
import/export *mechanism* hook (no models yet).
**Out:** auth, any real entity/table, book domain, LLM client wiring.

## Open questions for the planner
- Health endpoint = liveness only, or DB-readiness?
- Is the LanceDB sidecar stubbed now or deferred to the first vector-backed feature?
- Are bcrypt/PyJWT deps added here or with 004?
- Do prod nginx + docker-compose land here, in 002, or a later deployment feature?
<!-- roadmap:end -->
