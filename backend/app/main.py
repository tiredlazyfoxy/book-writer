"""FastAPI application factory / singleton.

Owns the module-level :data:`app`, configures logging at import, and mounts
routers (each router owns its own ``/api/...`` prefix — Decision 7). The
startup :func:`lifespan` builds a ``DbConfig`` from :class:`Settings`, opens
the engine and vector sidecar, and detects readiness (schema creation is
deferred to the setup flows).

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
from app.db import users
from app.db import vector
from app.routes import auth
from app.routes import book_author_prompts
from app.routes import books
from app.routes import chapter_author_prompts
from app.routes import chapters
from app.routes import chats
from app.routes import codex
from app.routes import health
from app.routes.admin import assistant_config as admin_assistant_config
from app.routes.admin import db as admin_db
from app.routes.admin import llm_servers as admin_llm_servers
from app.routes.admin import users as admin_users
from app.services import embedding as embedding_service
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

    On startup: build a ``DbConfig`` from :class:`Settings` (``db_path``), open
    the engine and vector sidecar, then perform **readiness detection** — a cold
    instance boots with zero tables (schema creation is deferred to the setup
    flows, feature 003.first-run-bootstrap), so the eager ``init_db``/
    ``create_all`` is gone. As the composition root, the lifespan queries
    ``db.users.admin_exists()`` directly (returns ``False`` gracefully on a
    missing table) and records the result via ``set_db_ready`` —
    ``needs_setup = not is_db_ready()``. No teardown beyond what the engine
    requires.
    """
    settings = get_settings()
    config = db_engine.DbConfig(db_path=settings.db_path)
    await db_engine.init_engine(config)
    # The composition root injects the embedding callables the sidecar needs:
    # ``db → services`` is forbidden, and one of ``rebuild_index``'s two callers
    # itself lives in ``db/`` (013 step 005).
    await vector.init_vector(
        settings.lancedb_dir,
        embed_batch=embedding_service.embed_batch,
        probe_dimension=embedding_service.probe_dimension,
    )
    ready = await users.admin_exists()
    db_engine.set_db_ready(ready)
    logger.info(
        "Application startup complete — engine and vector ready; db_ready=%s.",
        ready,
    )
    yield


app = FastAPI(title="BookWriter Backend", version="0.1.0", lifespan=lifespan)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(books.router)
app.include_router(chapters.router)
app.include_router(chats.router)
app.include_router(codex.router)
app.include_router(book_author_prompts.router)
app.include_router(chapter_author_prompts.router)
app.include_router(admin_users.router)
app.include_router(admin_llm_servers.router)
app.include_router(admin_db.router)
app.include_router(admin_assistant_config.router)
