"""Database-admin service — consistency report + typed error (feature 007, step 001).

Business-logic layer: **no** ``session`` / ``AsyncSession`` / ``select()`` /
``session.exec()`` / ``session.add()`` here (see ``docs/architecture/backend.md``
— layer separation; feature 007 decision D1). The **expected** structure is read
from ``SQLModel.metadata`` (a models-layer read, not a session); the **actual**
structure comes from the session-free ``app.db.schema`` layer (namespace import).
Domain refusals raise the typed :class:`DbAdminError`, discriminated by
:class:`DbAdminErrorCase` so step 005's route maps each case to its HTTP status
(D5); the route stays HTTP-only.

The error taxonomy is the feature's single closed, stable set — established here
in full so later steps (002 remediation, 003 import validation, 004 rebuild) reuse
it. This step only raises the report/validation-relevant cases; the remaining
cases exist for those later steps.

Skeleton (step 001): the error taxonomy and ``build_consistency_report()``
signature are frozen; the body is UNIMPLEMENTED.
"""

import enum
import gzip
import io
import json
import zipfile
from collections.abc import Awaitable, Callable
from typing import TypedDict

from sqlmodel import SQLModel

from app.db import assistant_modes, llm_servers, schema, vector
from app.models.schemas.db_admin import ConsistencyReport, TableReportEntry
from app.services import db_import_export


class DbAdminErrorCase(str, enum.Enum):
    """Discriminator for :class:`DbAdminError` — the database-admin refusal taxonomy.

    Frozen here (shared across steps 001–004). Step 005's route maps each case to
    its HTTP status (D5): ``not_in_metadata`` / ``table_not_missing`` /
    ``invalid_archive`` → 400, ``unknown_table`` → 404, ``no_embedding_provider``
    → 400.

    - ``not_in_metadata`` — a named table is not in ``SQLModel.metadata`` (step 002).
    - ``unknown_table`` — a named table is neither expected nor live (step 002).
    - ``table_not_missing`` — a create was asked for a table that already exists
      (step 002).
    - ``invalid_archive`` — an import archive failed pre-validation (step 003).
    - ``no_embedding_provider`` — a vector rebuild was asked with no embedding
      server / ``embedding_model`` configured (step 004).
    - ``not_seedable`` — a named table is real but has no seed registry entry, or
      its schema is ``missing``/``drift`` and therefore cannot receive rows
      (feedback round 1, F1) → 400.
    """

    not_in_metadata = "not-in-metadata"
    unknown_table = "unknown-table"
    table_not_missing = "table-not-missing"
    invalid_archive = "invalid-archive"
    no_embedding_provider = "no-embedding-provider"
    not_seedable = "not-seedable"


class DbAdminError(Exception):
    """Raised by the database-admin service for every domain refusal.

    Carries a :class:`DbAdminErrorCase` discriminator (``case``) plus a
    human-readable ``message``; step 005's route branches on ``case`` to pick the
    status (D5). Mirrors :class:`app.services.llm_servers.LlmServerError`.
    """

    def __init__(self, case: DbAdminErrorCase, message: str = "") -> None:
        self.case = case
        self.message = message
        super().__init__(message)


class SeedSpec(TypedDict):
    """What a seedable table needs: its required row keys and its seeder.

    - ``required_keys`` — every key that must have a row for the table to count
      as fully seeded. A row carrying an *unrecognised* key is not an error and
      is never reported or removed (F1 point 3).
    - ``seeder`` — the zero-argument, idempotent ``db/`` coroutine that creates
      the absent rows. It is **called, not reimplemented**.
    """

    required_keys: tuple[str, ...]
    seeder: Callable[[], Awaitable[None]]


_SEEDABLE_TABLES: dict[str, SeedSpec] = {
    "assistant_modes": SeedSpec(
        required_keys=assistant_modes.DEFAULT_MODE_KEYS,
        seeder=assistant_modes.seed_default_modes,
    ),
}
"""The seed-row registry (feedback round 1, F1 point 4).

Maps a table name to its required seed keys and its seeder. Exactly **one**
entry today. A table with no entry here is never reported ``seed-missing`` and
refuses :func:`seed_table_rows` with ``not_seedable``. The registry exists so
``024.chat-agent-loop`` and later features can add an entry rather than re-open
this design; it is not a plugin system.
"""


async def _missing_seed_keys(name: str) -> list[str]:
    """Which of ``name``'s required seed-row keys have no row (F1 points 3-4).

    Returns the :data:`_SEEDABLE_TABLES` entry's ``required_keys`` that are
    absent from the live table, in registry order; an empty list means the table
    is fully seeded, or has no registry entry at all. Presence of keys, never a
    row count: a row carrying an *unrecognised* key is not an error and is never
    reported (nor removed).

    The read is per-table by construction — :class:`SeedSpec` carries a seeder,
    not a reader, and each entity has its own ``db/`` module. The registry holds
    exactly one entry, so this is one branch; a future entry adds its own.
    A registered table with no branch here is treated as "nothing to report", so
    a table is never reported ``seed-missing`` on a guess.

    Callers must only reach this for a table that is present and schema-clean —
    schema outranks rows (F1 point 2).
    """
    spec = _SEEDABLE_TABLES.get(name)
    if spec is None:
        return []

    if name == "assistant_modes":
        present = {row.key for row in await assistant_modes.list_all()}
    else:
        return []

    return [key for key in spec["required_keys"] if key not in present]


async def build_consistency_report() -> ConsistencyReport:
    """Compute the per-table drift report (D1 / US-015).

    Reads the **expected** structure from ``SQLModel.metadata`` (table names +
    column names per table), calls :func:`app.db.schema.introspect` for the
    **actual** structure, and computes each expected table's status: ``missing``
    if absent from the live DB; else ``drift`` if the expected and actual
    column-name sets differ; else — for a table with a :data:`_SEEDABLE_TABLES`
    entry whose required rows are not all present — ``seed-missing``; else
    ``ok``. For a drifted table, populates ``missing_columns = expected −
    actual`` and ``extra_columns = actual − expected``; every other entry carries
    empty lists. ``missing_seed_keys`` is populated only for a ``seed-missing``
    entry and is empty everywhere else, including for every table without a
    registry entry.

    Precedence is absolute — schema outranks rows (F1 point 2): row health is
    only ever consulted for a table that is present *and* schema-clean, so the
    four statuses stay mutually exclusive and seeding is never offered against a
    table that cannot receive rows.
    """
    actual = await schema.introspect()

    entries: list[TableReportEntry] = []
    for table_name in sorted(SQLModel.metadata.tables):
        expected_columns = {
            column.name for column in SQLModel.metadata.tables[table_name].columns
        }

        if table_name not in actual["tables"]:
            entries.append(
                TableReportEntry(
                    name=table_name,
                    status="missing",
                    missing_columns=[],
                    extra_columns=[],
                )
            )
            continue

        actual_columns = set(actual["tables"][table_name]["columns"])

        if expected_columns == actual_columns:
            missing_seed_keys = await _missing_seed_keys(table_name)
            entries.append(
                TableReportEntry(
                    name=table_name,
                    status="seed-missing" if missing_seed_keys else "ok",
                    missing_columns=[],
                    extra_columns=[],
                    missing_seed_keys=missing_seed_keys,
                )
            )
        else:
            entries.append(
                TableReportEntry(
                    name=table_name,
                    status="drift",
                    missing_columns=sorted(expected_columns - actual_columns),
                    extra_columns=sorted(actual_columns - expected_columns),
                )
            )

    return ConsistencyReport(tables=entries)


async def create_missing_table(name: str) -> None:
    """Create a table reported ``missing`` (D2 / US-016).

    Preconditions: ``name`` must be in ``SQLModel.metadata`` (else
    :class:`DbAdminError` with case ``not_in_metadata``) and currently absent
    from the live DB per :func:`app.db.schema.introspect` (else
    :class:`DbAdminError` with case ``table_not_missing``); in either refusal the
    DB is left unchanged. On success calls :func:`app.db.schema.create_table`, so
    the table then exists and a fresh report shows it ``ok``.
    """
    if name not in SQLModel.metadata.tables:
        raise DbAdminError(
            DbAdminErrorCase.not_in_metadata,
            f"Table '{name}' is not defined in SQLModel.metadata.",
        )

    actual = await schema.introspect()
    if name in actual["tables"]:
        raise DbAdminError(
            DbAdminErrorCase.table_not_missing,
            f"Table '{name}' already exists in the live database.",
        )

    await schema.create_table(name)


async def sync_table_schema(name: str) -> None:
    """Reconcile a drifted table's columns to match ``SQLModel.metadata`` (D2 / US-017).

    Recomputes the per-table diff for ``name`` by reusing the step-001 report
    logic (:func:`build_consistency_report`, selecting the entry for ``name``),
    then calls :func:`app.db.schema.add_columns` with the entry's
    ``missing_columns`` and :func:`app.db.schema.drop_columns` with its
    ``extra_columns``, so the table subsequently reports ``ok``. Raises
    :class:`DbAdminError` with case ``unknown_table`` if ``name`` is not in
    ``SQLModel.metadata`` or is missing entirely from the live DB.
    """
    report = await build_consistency_report()
    entry = next((e for e in report.tables if e.name == name), None)
    if entry is None or entry.status == "missing":
        raise DbAdminError(
            DbAdminErrorCase.unknown_table,
            f"Table '{name}' is not defined in metadata or is missing from "
            "the live database.",
        )

    await schema.add_columns(name, entry.missing_columns)
    await schema.drop_columns(name, entry.extra_columns)


async def seed_table_rows(name: str) -> None:
    """Seed a table reported ``seed-missing`` (feedback round 1, F1 points 5-6).

    The admin-gated remediation paired with the ``seed-missing`` status, mirroring
    :func:`create_missing_table` / :func:`sync_table_schema`: looks ``name`` up in
    :data:`_SEEDABLE_TABLES` and calls that entry's ``seeder``, which creates only
    the absent rows and never touches an existing one (an admin-edited
    ``system_prompt`` and any link rows survive untouched).

    **Idempotent**: seeding an already-complete table is a no-op that still
    succeeds — this deliberately does *not* copy :func:`create_missing_table`'s
    ``table_not_missing`` refusal, because refusing would add ceremony with no
    user value.

    Refusals (DB left unchanged in each): :class:`DbAdminError` with case
    ``unknown_table`` when ``name`` is not in ``SQLModel.metadata`` (→ 404); with
    case ``not_seedable`` when ``name`` is a real table with no registry entry, or
    when its schema status is ``missing`` / ``drift`` and it therefore cannot
    receive rows (→ 400).

    MUST NOT call ``set_db_ready`` (first-run-only, owned by ``services.setup``).
    """
    if name not in SQLModel.metadata.tables:
        raise DbAdminError(
            DbAdminErrorCase.unknown_table,
            f"Table '{name}' is not defined in metadata or is missing from "
            "the live database.",
        )

    spec = _SEEDABLE_TABLES.get(name)
    if spec is None:
        raise DbAdminError(
            DbAdminErrorCase.not_seedable,
            f"Table '{name}' has no required seed rows; there is nothing to seed.",
        )

    report = await build_consistency_report()
    entry = next((e for e in report.tables if e.name == name), None)
    if entry is None or entry.status in ("missing", "drift"):
        raise DbAdminError(
            DbAdminErrorCase.not_seedable,
            f"Table '{name}' cannot receive rows while its schema is not clean; "
            "create or sync it first.",
        )

    await spec["seeder"]()


async def export_database() -> bytes:
    """Return the database export archive bytes (D3 / US-018).

    Passthrough to :func:`app.services.db_import_export.export_all` — a
    ``ZIP_STORED`` archive whose members are per-table gzipped-JSONL blobs (one
    per ``TABLE_REGISTRY`` entry, streamed per-row). No transformation here; the
    step-005 route adds the download headers.
    """
    return await db_import_export.export_all()


async def validate_archive(archive_bytes: bytes) -> None:
    """Pre-validate an import archive BEFORE any mutation (D4 / US-019.AC-3).

    Opens ``archive_bytes`` as a zip (:mod:`zipfile`); for each
    ``app.services.db_import_export.TABLE_REGISTRY`` entry confirms its member
    (name = ``entry[0]``, the bare table name — never hardcoded or extension-
    appended) is present, gzip-decodable, and JSONL-parseable. On ANY failure
    raises :class:`DbAdminError` with case
    :attr:`DbAdminErrorCase.invalid_archive`. Performs NO writes, so a refusal
    leaves the DB untouched by construction.
    """
    try:
        zf = zipfile.ZipFile(io.BytesIO(archive_bytes))
    except zipfile.BadZipFile as exc:
        raise DbAdminError(
            DbAdminErrorCase.invalid_archive,
            f"Archive is not a valid zip file: {exc}",
        ) from exc

    with zf:
        member_names = set(zf.namelist())
        for entry in db_import_export.TABLE_REGISTRY:
            member = entry[0]
            if member not in member_names:
                raise DbAdminError(
                    DbAdminErrorCase.invalid_archive,
                    f"Archive is missing expected member '{member}'.",
                )

            try:
                decoded = gzip.decompress(zf.read(member)).decode("utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                raise DbAdminError(
                    DbAdminErrorCase.invalid_archive,
                    f"Member '{member}' is not gzip-decodable UTF-8 text: {exc}",
                ) from exc

            for raw_line in decoded.splitlines():
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    json.loads(line)
                except json.JSONDecodeError as exc:
                    raise DbAdminError(
                        DbAdminErrorCase.invalid_archive,
                        f"Member '{member}' contains a non-JSON line: {exc}",
                    ) from exc


async def import_database(archive_bytes: bytes) -> None:
    """Validate then UPSERT-import an export archive (D4 / US-019.AC-1/AC-2).

    Calls :func:`validate_archive` first (raising on failure, DB untouched), then
    on success delegates to :func:`app.services.db_import_export.import_all`
    (``init_db()`` → streaming per-table UPSERT → vector rebuild) and finally
    seeds the fixed five assistant modes — idempotent throughout. MUST NOT call
    ``set_db_ready`` (first-run-only, owned by ``services.setup``; D4).

    The seed sits where the bootstrap path puts it (``services/setup.py`` —
    after the schema and rows exist), so an instance restored through the admin
    surface is not left without its modes (feedback round 1, F2). It is
    check-then-create keyed on ``key``, so modes carried by the archive keep
    their stored ``system_prompt`` and gain no duplicate row. A **refused**
    archive raises out of :func:`validate_archive` above and seeds nothing.
    """
    await validate_archive(archive_bytes)
    await db_import_export.import_all(archive_bytes)
    await assistant_modes.seed_default_modes()


async def rebuild_vector_index() -> int:
    """Reset+rebuild the LanceDB vector index for the admin action (D6 / US-020).

    No-provider contract (FROZEN — OPTION (a) RAISE): resolves the designated
    embedding server via ``app.db.llm_servers.get_embedding_server()``; if that
    is ``None`` OR its ``embedding_model`` is falsy (``None`` / empty), raises
    :class:`DbAdminError` with case
    :attr:`DbAdminErrorCase.no_embedding_provider` (the admin gets meaningful
    feedback). On a valid designation, delegates to
    :func:`app.db.vector.rebuild_index` and returns the indexed-row count. In
    Stage 1 (empty ``VECTOR_SOURCE_REGISTRY``) this resets the index and returns
    ``0``.

    Rationale (record): post-import reset flows through
    ``run_vector_rebuild → vector.rebuild_index`` DIRECTLY, not this gated
    method, so raising here does not harm post-import correctness.

    Skeleton (step 004): signature frozen; body UNIMPLEMENTED. The coder adds
    ``from app.db import vector`` and ``from app.db import llm_servers``.
    """
    server = await llm_servers.get_embedding_server()
    if server is None or not server.embedding_model:
        raise DbAdminError(
            DbAdminErrorCase.no_embedding_provider,
            "No embedding provider is designated (or its embedding model is "
            "unset); designate an embedding server before rebuilding the index.",
        )

    return await vector.rebuild_index()
