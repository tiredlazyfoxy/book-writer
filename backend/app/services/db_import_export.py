"""Import/export serialization — gzipped JSONL per table inside a zip archive.

This is the format/serialization layer (services). It owns ``TABLE_REGISTRY``
(the ordered, FK-respecting list of per-table codec entries) and streams rows
through gzip; all DB access is delegated to ``db.import_export_queries``, which
manages its own sessions. See ``docs/architecture/backend.md``.

The registry is **empty for now** (no persistent models exist yet). Adding a
model later = add its ``to_dict``/``from_dict`` codec pair plus one ordered
``TABLE_REGISTRY`` tuple, in FK dependency order.

Skeleton (step 004): signatures are frozen; bodies are UNIMPLEMENTED.
"""

import gzip
import io
import json
import logging
import zipfile
from collections.abc import Callable

from sqlmodel import SQLModel

from app.db import engine, import_export_queries

logger = logging.getLogger(__name__)

# One registry entry per persistent table, in FK dependency (import) order:
#   (zip_filename, model_class, to_dict_fn, from_dict_fn)
RegistryEntry = tuple[
    str,
    type[SQLModel],
    Callable[[SQLModel], dict[str, object]],
    Callable[[dict[str, object]], SQLModel],
]

# Empty for step 004 — no persistent models yet. The mechanism round-trips an
# empty archive; real models plug in here as they are introduced.
TABLE_REGISTRY: list[RegistryEntry] = []

# Max rows accumulated before a streaming UPSERT flush on import.
BATCH_SIZE = 100


async def export_all() -> bytes:
    """Export every registered table to a zip of ``<table>.jsonl.gz`` members.

    One gzip-JSONL member per ``TABLE_REGISTRY`` entry, each streamed per-row
    through gzip via ``export_table`` plus a serializing callback (rows are
    never collected into a large in-memory list). Over the empty registry this
    yields a valid, empty zip archive. Returns the zip archive as ``bytes``.
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
        for zip_filename, model_class, to_dict_fn, _from_dict_fn in TABLE_REGISTRY:
            gz_buf = io.BytesIO()
            with gzip.open(gz_buf, "wt", encoding="utf-8") as gz:

                def make_writer(
                    gz_file: gzip.GzipFile,
                    serializer: Callable[[SQLModel], dict[str, object]],
                ) -> Callable[[SQLModel], None]:
                    def write_row(row: SQLModel) -> None:
                        gz_file.write(json.dumps(serializer(row)) + "\n")

                    return write_row

                await import_export_queries.export_table(
                    model_class, make_writer(gz, to_dict_fn)
                )
            zf.writestr(zip_filename, gz_buf.getvalue())

    return buf.getvalue()


async def import_all(zip_bytes: bytes) -> None:
    """Import every registered table from a zip of ``<table>.jsonl.gz`` members.

    Calls ``init_db()`` first (creates/reshapes tables), then, for each registry
    entry, streams its JSONL lines, accumulates up to ``BATCH_SIZE`` rows, and
    flushes each batch via ``upsert_batch``; finally triggers
    ``run_vector_rebuild()``. UPSERT — idempotent. Over an empty registry /
    empty archive this is a no-op that still runs ``init_db()``.
    """
    await engine.init_db()

    with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
        member_names = set(zf.namelist())
        for zip_filename, _model_class, _to_dict_fn, from_dict_fn in TABLE_REGISTRY:
            if zip_filename not in member_names:
                continue

            batch: list[SQLModel] = []
            with gzip.open(
                io.BytesIO(zf.read(zip_filename)), "rt", encoding="utf-8"
            ) as gz:
                for raw_line in gz:
                    line = raw_line.strip()
                    if not line:
                        continue
                    batch.append(from_dict_fn(json.loads(line)))
                    if len(batch) >= BATCH_SIZE:
                        await import_export_queries.upsert_batch(batch)
                        batch.clear()
            if batch:
                await import_export_queries.upsert_batch(batch)

    await import_export_queries.run_vector_rebuild()
