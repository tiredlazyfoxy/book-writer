"""Database-admin report DTOs (feature 007, step 001).

Declarative Pydantic schemas — the typed wire contracts for the admin database-
consistency surface (``/api/admin/db``, step 005). Plain typed data shapes, no
logic (see ``docs/architecture/backend.md`` — ``models/`` is tables + schemas
only). The frontend ``types/db.d.ts`` mirrors these 1:1 (step 006).

Skeleton (step 001): field names/types are frozen.
"""

from typing import Literal

from pydantic import BaseModel


class TableReportEntry(BaseModel):
    """The consistency status of one metadata-expected table.

    - ``name`` — the expected table name.
    - ``status`` — ``ok`` (column-name sets match), ``drift`` (present but sets
      differ), or ``missing`` (absent from the live DB).
    - ``missing_columns`` — columns in metadata but absent from the live table
      (expected − actual); empty unless ``drift``.
    - ``extra_columns`` — columns in the live table but absent from metadata
      (actual − expected); empty unless ``drift``.
    """

    name: str
    status: Literal["ok", "drift", "missing"]
    missing_columns: list[str]
    extra_columns: list[str]


class ConsistencyReport(BaseModel):
    """The per-table drift report — one :class:`TableReportEntry` per expected table."""

    tables: list[TableReportEntry]


class VectorRebuildResponse(BaseModel):
    """Result of a vector-index rebuild (``POST /api/admin/db/vector/rebuild``,
    step 005) — the count of source rows re-indexed into the vector sidecar.

    - ``indexed_rows`` — rows written to the sidecar by
      :func:`app.services.db_admin.rebuild_vector_index` (0 in Stage 1).
    """

    indexed_rows: int
