"""Admin database-consistency route layer for ``/api/admin/db``.

HTTP only: parse the request, call one :mod:`app.services.db_admin` function,
map the typed :class:`~app.services.db_admin.DbAdminError` to a status (D5), and
return (see ``docs/architecture/backend.md`` — layer separation; no business
logic, no DB access here). Every endpoint is gated by ``require_role(admin)``
(feature 005/006), which authorizes the caller (non-admin → 403) and yields the
authenticated ``caller: User``; this feature does not thread the caller into the
service (the guard alone provides gating). The router owns its own
``/api/admin/db`` prefix and is mounted with a bare ``app.include_router(...)``
in the composition root.

Route ordering (D5) is load-bearing: FastAPI matches in declaration order, so the
static ``/report``, ``/export``, ``/import`` and ``/vector/rebuild`` routes are
declared **before** the ``/tables/{name}/...`` param routes — otherwise a static
segment could be captured as a ``{name}``.

Typed-error → status map the handlers implement (D5): ``not-in-metadata`` → 400,
``table-not-missing`` → 400, ``invalid-archive`` → 400, ``no-embedding-provider``
→ 400, ``not-seedable`` → 400, ``unknown-table`` → 404. (Non-admin → 403 is
produced by ``require_role`` itself.)

Skeleton (feature 007, step 005): the router object, route registration, and
handler signatures (incl. ``response_model`` via return annotations, the
``name: str`` path params, the ``caller`` dependency, the multipart ``file``
field, the ``Response`` zip download, and the 200/204 status codes) are frozen,
and the error→status map + helper are real; the handler bodies are UNIMPLEMENTED.
"""

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Response,
    UploadFile,
    status,
)

from app.models.schemas.db_admin import ConsistencyReport, VectorRebuildResponse
from app.models.user import User, UserRole
from app.services import auth as auth_service
from app.services import db_admin

router = APIRouter(prefix="/api/admin/db", tags=["admin-db"])

_DB_ADMIN_ERROR_STATUS: dict[db_admin.DbAdminErrorCase, int] = {
    db_admin.DbAdminErrorCase.not_in_metadata: status.HTTP_400_BAD_REQUEST,
    db_admin.DbAdminErrorCase.table_not_missing: status.HTTP_400_BAD_REQUEST,
    db_admin.DbAdminErrorCase.invalid_archive: status.HTTP_400_BAD_REQUEST,
    db_admin.DbAdminErrorCase.no_embedding_provider: status.HTTP_400_BAD_REQUEST,
    db_admin.DbAdminErrorCase.not_seedable: status.HTTP_400_BAD_REQUEST,
    db_admin.DbAdminErrorCase.unknown_table: status.HTTP_404_NOT_FOUND,
}


def _map_db_admin_error(err: db_admin.DbAdminError) -> HTTPException:
    """Translate a typed :class:`~app.services.db_admin.DbAdminError` to an
    :class:`HTTPException` per the decision-5 status map (branch on ``.case``)."""
    return HTTPException(
        status_code=_DB_ADMIN_ERROR_STATUS[err.case],
        detail=err.message,
    )


@router.get("/report")
async def get_report(
    caller: User = Depends(auth_service.require_role(UserRole.admin)),
) -> ConsistencyReport:
    """Per-table drift report (``GET /api/admin/db/report`` → 200, US-015)."""
    return await db_admin.build_consistency_report()


@router.get("/export")
async def export_database(
    caller: User = Depends(auth_service.require_role(UserRole.admin)),
) -> Response:
    """Download the full database export as a zip
    (``GET /api/admin/db/export`` → 200, US-018)."""
    data = await db_admin.export_database()
    return Response(
        content=data,
        media_type="application/zip",
        headers={
            "Content-Disposition": 'attachment; filename="bookwriter-export.zip"'
        },
    )


@router.post("/import", status_code=status.HTTP_204_NO_CONTENT)
async def import_database(
    file: UploadFile = File(...),
    caller: User = Depends(auth_service.require_role(UserRole.admin)),
) -> None:
    """Restore from a multipart ``file`` export
    (``POST /api/admin/db/import`` → 204, 400 on ``invalid-archive``, US-019)."""
    archive_bytes = await file.read()
    try:
        await db_admin.import_database(archive_bytes)
    except db_admin.DbAdminError as err:
        raise _map_db_admin_error(err)


@router.post("/vector/rebuild")
async def rebuild_vector_index(
    caller: User = Depends(auth_service.require_role(UserRole.admin)),
) -> VectorRebuildResponse:
    """Rebuild the vector sidecar index
    (``POST /api/admin/db/vector/rebuild`` → 200, 400 on
    ``no-embedding-provider``, US-020)."""
    try:
        count = await db_admin.rebuild_vector_index()
    except db_admin.DbAdminError as err:
        raise _map_db_admin_error(err)
    return VectorRebuildResponse(indexed_rows=count)


@router.post("/tables/{name}/create", status_code=status.HTTP_204_NO_CONTENT)
async def create_missing_table(
    name: str,
    caller: User = Depends(auth_service.require_role(UserRole.admin)),
) -> None:
    """Create a missing metadata-expected table
    (``POST /api/admin/db/tables/{name}/create`` → 204, 400 on
    ``not-in-metadata``/``table-not-missing``, US-016)."""
    try:
        await db_admin.create_missing_table(name)
    except db_admin.DbAdminError as err:
        raise _map_db_admin_error(err)


@router.post("/tables/{name}/sync", status_code=status.HTTP_204_NO_CONTENT)
async def sync_table_schema(
    name: str,
    caller: User = Depends(auth_service.require_role(UserRole.admin)),
) -> None:
    """Reconcile a drifted table's columns
    (``POST /api/admin/db/tables/{name}/sync`` → 204, 404 on ``unknown-table``,
    US-017)."""
    try:
        await db_admin.sync_table_schema(name)
    except db_admin.DbAdminError as err:
        raise _map_db_admin_error(err)


@router.post("/tables/{name}/seed", status_code=status.HTTP_204_NO_CONTENT)
async def seed_table_rows(
    name: str,
    caller: User = Depends(auth_service.require_role(UserRole.admin)),
) -> None:
    """Seed a table's missing required rows
    (``POST /api/admin/db/tables/{name}/seed`` → 204, 404 on ``unknown-table``,
    400 on ``not-seedable``; feedback round 1, F1)."""
    try:
        await db_admin.seed_table_rows(name)
    except db_admin.DbAdminError as err:
        raise _map_db_admin_error(err)
