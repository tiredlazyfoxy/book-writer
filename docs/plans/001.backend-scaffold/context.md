# Feature 001 — backend-scaffold (feature-wide context)

## Goal & scope

Stand up the BookWriter FastAPI backend as a **runnable, testable 4-layer skeleton**. Greenfield: `backend/` does not exist yet. When done, a developer can start uvicorn, hit `GET /api/health` which flows through all four layers (routes → services → db → models), and run `pytest` green.

This is **Stage 0 scaffold**. Deliberately out of scope: auth, any real entity/table, the book domain, LLM client wiring. The feature delivers **no product ids** — DoD `[test]` items cite the brief's behavioural scope, not `US/AC` ids.

The settled boundary is `brief.md` (Definition + Scope In/Out). Do not widen it.

## Authoritative sources

- `docs/architecture/backend.md` — the enforced 4-layer rules, dependency direction, typing discipline, the **verbatim `pyproject.toml` dependency block** (lines ~54–72), async SQLite engine (`sqlite+aiosqlite`, `create_all`, in-code `ALTER` migrations, no Alembic), the `DbConfig` dataclass shape (lines ~82–87), `BOOKWRITER_DB_PATH` override, streaming gzip-JSONL import/export mechanism, the pytest+httpx ASGITransport harness.
- `docs/architecture/system-overview.md` — topology, `/api/...` router convention, backend uvicorn port 8185.
- Root `CLAUDE.md` — Build & Test commands.

## Reference project (mirror its scaffold patterns)

A sibling project `D:/GitRoot/_TextGens/LLMRPTextOnlyProject/backend` implements the same stack; BookWriter's foundation mirrors it. Step-specific context files cite concrete `path:line` anchors. Two deliberate **divergences** from the reference:

1. **Health route** — the reference's `/api/health` is liveness-only; BookWriter's is **DB-readiness through all four layers** (see decisions).
2. **Settings class** — the reference lacks a `pydantic-settings` `Settings` class; BookWriter introduces one (net-new). Do **not** copy the reference's deprecated `event_loop` fixture override — rely on `asyncio_mode="auto"`.

## Cross-cutting rules (apply in every step)

- **4-layer separation** (`backend/app/`): `routes/` (HTTP only), `services/` (business logic — no `session`/`AsyncSession`/`select()`/`session.exec()`/`session.add()`), `db/` (session-free; sessions created and closed internally; ORM types never leak out), `models/` + `models/schemas/` (SQLModel tables + Pydantic schemas, no logic).
- **Dependency direction**: `routes → services + db`; `services → db`; `db → models`. Never upward.
- **Namespace import style**: `from app.db import health` then `await health.ping()`; `from app.services import health as health_service`.
- **Typing discipline**: Pydantic `BaseModel` for all API I/O; `SQLModel` for tables; `TypedDict` for internal data passing. No free dictionaries, no untyped data.
- **Router mounting**: each `APIRouter` owns its own `prefix="/api/..."`; mounted with a bare `app.include_router(...)`. (Decision 7.)
- **Python invocation**: always `.venv/Scripts/python` (Windows venv layout). **No static typecheck is configured for the backend** — the coder verifies by import smoke / editable install only; the verifier runs `pytest`.
- **Test harness**: pytest + pytest-asyncio in `asyncio_mode="auto"` (no per-test decorator); tests exercise the app in-process via `httpx.AsyncClient` over `ASGITransport` — no live server, no network; a temp-SQLite `DbConfig` fixture gives each run an isolated throwaway DB.

## Settings vs DbConfig (two separate objects — do not fold)

- **`Settings`** (pydantic-settings, step 001) loads `.env.local` and honors the `BOOKWRITER_DB_PATH` environment override. It is the app-level config object.
- **`DbConfig`** (dataclass, step 002) is the injectable db-layer config (`db_path`, `echo`). `Settings` can *supply* `DbConfig`'s `db_path`, but they remain distinct types. Tests inject a throwaway `DbConfig` directly without touching `Settings`.

## Files touched across the feature

```
backend/
  pyproject.toml                         (001)
  .gitignore                             (001)
  app/
    __init__.py                          (001)
    settings.py                          (001)
    main.py                              (003)
    routes/__init__.py                   (001)
    routes/health.py                     (003)
    services/__init__.py                 (001)
    services/health.py                   (003)
    services/db_import_export.py         (004)
    db/__init__.py                       (001)
    db/engine.py                         (002)
    db/health.py                         (002)
    db/vector.py                         (002)
    db/import_export_queries.py          (004)
    models/__init__.py                   (001)
    models/schemas/__init__.py           (001)
    models/schemas/health.py             (003)
  tests/
    test_settings.py                     (001, test-coder)
    conftest.py                          (002 create, 003 extend — see note)
    db/test_engine.py                    (002, test-coder)
    routes/test_health.py                (003, test-coder)
    services/test_db_import_export.py    (004, test-coder)
```

## conftest.py is extended across two steps (not a scope violation)

`tests/conftest.py` legitimately appears in the Test-files list of **both step 002 and step 003**. Step 002 **creates** it with the temp-DB `DbConfig` fixture; step 003 **extends** it with the `http_client` ASGITransport fixture. This is the same test-coder role editing one file incrementally across dependent steps — it is intended, not a cross-role scope breach.

## Known seam — `create_all` in the startup lifespan (003 will be amended later)

For this greenfield scaffold (no data), the startup lifespan runs `SQLModel.metadata.create_all` so the health DB-readiness check passes (Decision 6). Feature **003.first-run-bootstrap (FEAT-001)** will later change startup to defer table creation to a first-run wizard. This is a recorded seam: 003 expects to amend the lifespan. Do **not** build any bootstrap logic here.

## Deferred past 001 (record, do not build)

prod nginx + docker-compose are **deferred** (Decision 4). The backend runs via the uvicorn dev server only in this feature.
