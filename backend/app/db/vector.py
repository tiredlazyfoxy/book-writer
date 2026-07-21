"""LanceDB sidecar connection stub.

A thin connect/init stub for the LanceDB semantic-search sidecar. Unused until
a vector-backed model exists (Decision 2) — it only needs to open a connection
to the configured LanceDB directory without error. LanceDB is a derived index,
rebuilt from SQLite source rows on import and never exported.

Skeleton (step 002): signature is frozen; body is UNIMPLEMENTED.
"""

import asyncio
import logging
from pathlib import Path
from typing import Any

import lancedb

logger = logging.getLogger(__name__)

# Module-level singletons — populated by ``init_vector``.
_vector_dir: Path | None = None
_db: Any = None


async def init_vector(vector_dir: Path) -> None:
    """Open a connection to the LanceDB directory at ``vector_dir``.

    Stores the connection and directory in the module-level singletons. Thin
    stub: it must initialize without error; no tables are created yet.
    """
    global _vector_dir, _db
    vector_dir.mkdir(parents=True, exist_ok=True)
    _vector_dir = vector_dir
    # ``lancedb.connect`` is blocking — run it off the event loop.
    _db = await asyncio.to_thread(lancedb.connect, str(vector_dir))
    logger.info("Vector store initialized at %s", vector_dir)
