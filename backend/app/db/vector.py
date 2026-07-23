"""LanceDB sidecar connection stub.

A thin connect/init stub for the LanceDB semantic-search sidecar. Unused until
a vector-backed model exists (Decision 2) — it only needs to open a connection
to the configured LanceDB directory without error. LanceDB is a derived index,
rebuilt from SQLite source rows on import and never exported.

Skeleton (step 002): signature is frozen; body is UNIMPLEMENTED.
"""

import asyncio
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

import lancedb

logger = logging.getLogger(__name__)

# Module-level singletons — populated by ``init_vector``.
_vector_dir: Path | None = None
_db: Any = None

# ---------------------------------------------------------------------------
# Stage-2 embedding seam (feature 007, step 004 / D6).
#
# ``VECTOR_SOURCE_REGISTRY`` is the list of ``(model_class, text_extractor)``
# entries that :func:`rebuild_index` iterates to embed+write source rows.
# ``text_extractor`` maps a model row to the text to embed.
#
# **Empty in Stage 1** — there are NO vector-backed domain tables yet
# (users/llm_servers are not searchable content). The first entry (Stage-2
# codex) is added behind the architect gate. Do NOT append users/llm_servers.
# With an empty registry, :func:`rebuild_index` resets the index and returns 0.
VECTOR_SOURCE_REGISTRY: list[tuple[type, Callable[..., str]]] = []


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


async def rebuild_index() -> int:
    """Reset the LanceDB sidecar index and re-embed every registered source.

    Connection contract (FROZEN — step 004 / D6): ensure a live connection by
    reusing the module ``_db`` if already initialized, else lazily establish it
    via ``init_vector(get_settings().lancedb_dir)`` (``from app.settings import
    get_settings``). This lets a test point LanceDB at a throwaway directory by
    calling ``await vector.init_vector(tmp_path / "vector")`` BEFORE
    ``rebuild_index()``.

    Behavior: drops/recreates the sidecar index tables (a full reset, valid
    regardless of prior state — idempotent), then iterates
    :data:`VECTOR_SOURCE_REGISTRY`, embedding+writing each source's rows.
    Returns the number of rows indexed. With the Stage-1 empty registry the
    reset completes and the count is ``0``.

    Skeleton (step 004): signature frozen; body UNIMPLEMENTED.
    """
    global _db

    # Connection contract (frozen): reuse the live ``_db`` if already
    # initialized, else lazily connect via the configured settings dir.
    if _db is None:
        from app.settings import get_settings

        await init_vector(get_settings().lancedb_dir)

    # Reset the sidecar: drop every existing table (idempotent — drop-if-exists
    # semantics, no error if a table is already absent). Keep blocking lancedb
    # calls off the event loop, mirroring ``init_vector``.
    table_names = await asyncio.to_thread(_db.table_names)
    for name in table_names:
        await asyncio.to_thread(_db.drop_table, name, ignore_missing=True)

    # Re-embed+write every registered source. Empty registry (Stage 1) → no
    # iterations, so the reset completes at zero rows indexed.
    indexed = 0
    for _model_class, _text_extractor in VECTOR_SOURCE_REGISTRY:
        # Stage-2 embedding seam — no sources exist yet in Stage 1.
        pass

    return indexed
