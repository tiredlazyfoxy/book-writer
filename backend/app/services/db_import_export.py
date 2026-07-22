"""Import/export serialization — gzipped JSONL per table inside a zip archive.

This is the format/serialization layer (services). It owns ``TABLE_REGISTRY``
(the ordered, FK-respecting list of per-table codec entries) and streams rows
through gzip; all DB access is delegated to ``db.import_export_queries``, which
manages its own sessions. See ``docs/architecture/backend.md``.

Adding a model = add its ``to_dict``/``from_dict`` codec pair plus one ordered
``TABLE_REGISTRY`` tuple, in FK dependency order. ``users`` is the first
persistent model (step 003).

Skeleton (step 004): mechanism signatures frozen; bodies UNIMPLEMENTED.
Skeleton (step 003): ``User`` codec signatures frozen; codec bodies UNIMPLEMENTED.
"""

import gzip
import io
import json
import logging
import zipfile
from collections.abc import Callable
from datetime import datetime

from sqlmodel import SQLModel

from app.db import engine, import_export_queries
from app.models.user import User, UserRole

logger = logging.getLogger(__name__)

# One registry entry per persistent table, in FK dependency (import) order:
#   (zip_filename, model_class, to_dict_fn, from_dict_fn)
RegistryEntry = tuple[
    str,
    type[SQLModel],
    Callable[[SQLModel], dict[str, object]],
    Callable[[dict[str, object]], SQLModel],
]

def _user_to_dict(user: User) -> dict[str, object]:
    """Serialize a ``User`` row to a JSON-safe dict for export.

    Enum via ``.value``, datetimes via ``.isoformat()``, nullable fields emitted
    as ``None``. Includes credentials (``pwdhash``, ``jwt_signing_key``) so
    restored accounts can authenticate (security consideration flagged in
    ``outcome.md``).
    """
    return {
        "id": str(user.id),
        "username": user.username,
        "pwdhash": user.pwdhash,
        "role": user.role.value,
        "jwt_signing_key": user.jwt_signing_key,
        "last_login": user.last_login.isoformat() if user.last_login else None,
        "last_key_update": (
            user.last_key_update.isoformat() if user.last_key_update else None
        ),
    }


def _dict_to_user(data: dict[str, object]) -> User:
    """Restore a ``User`` row from an exported dict (inverse of ``_user_to_dict``).

    Role via ``UserRole(...)``, datetimes parsed from isoformat, nullable fields
    read with a ``.get``-style lookup. Explicit ``id`` is preserved so the UPSERT
    is idempotent on re-import (decision 6). ``id`` is accepted as **either** a
    JSON string (current snowflake serialization) **or** a legacy JSON number
    (pre-snowflake archives), parsed to ``int`` in both cases.
    """
    last_login = data.get("last_login")
    last_key_update = data.get("last_key_update")
    raw_id = data.get("id")
    return User(
        id=int(raw_id) if raw_id is not None else None,
        username=data["username"],
        pwdhash=data.get("pwdhash"),
        role=UserRole(data["role"]),
        jwt_signing_key=data.get("jwt_signing_key"),
        last_login=datetime.fromisoformat(last_login) if last_login else None,
        last_key_update=(
            datetime.fromisoformat(last_key_update) if last_key_update else None
        ),
    )


# One registry entry per persistent table, in FK (import) order. ``users`` is
# first — it precedes any dependent entity. Real codec functions are referenced
# here even while their bodies are unimplemented, so the registry is non-empty
# and importable.
TABLE_REGISTRY: list[RegistryEntry] = [
    ("users", User, _user_to_dict, _dict_to_user),
]

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
