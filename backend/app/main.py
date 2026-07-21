"""FastAPI application factory / singleton.

Owns the module-level :data:`app`, configures logging at import, and mounts
routers (each router owns its own ``/api/...`` prefix — Decision 7). The
startup :func:`lifespan` builds a ``DbConfig`` from :class:`Settings` and
initializes the engine, schema, and vector sidecar.

``Settings`` (pydantic-settings) loads ``.env.local`` on instantiation, so no
separate dotenv call is needed here.

Skeleton (step 003): the module-level wiring (logging, ``app`` singleton, router
mount) is frozen so the app imports and the ``/api/health`` route is registered;
the :func:`lifespan` startup body is UNIMPLEMENTED.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from app.db import engine as db_engine
from app.db import vector
from app.routes import health
from app.settings import get_settings

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()],
)

# Silence noisy third-party loggers.
for _quiet in ("aiosqlite", "httpx", "httpcore"):
    logging.getLogger(_quiet).setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup/shutdown context.

    On startup: build a ``DbConfig`` from :class:`Settings` (``db_path``), then
    call ``db.engine.init_engine`` -> ``db.engine.init_db`` (runs ``create_all``
    — the recorded seam feature 003.first-run-bootstrap will later amend) ->
    ``db.vector.init_vector``. No teardown beyond what the engine requires.
    """
    settings = get_settings()
    config = db_engine.DbConfig(db_path=settings.db_path)
    await db_engine.init_engine(config)
    await db_engine.init_db()
    await vector.init_vector(settings.lancedb_dir)
    logger.info("Application startup complete — engine, schema, and vector ready.")
    yield


app = FastAPI(title="BookWriter Backend", version="0.1.0", lifespan=lifespan)

app.include_router(health.router)
