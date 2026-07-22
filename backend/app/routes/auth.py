"""Auth / first-run-bootstrap route layer for ``/api/auth``.

HTTP only: parse the request, call a service, return a typed schema (see
``docs/architecture/backend.md`` — layer separation; no business logic, no DB
access here). Validation lives in the service (decision 3); these handlers only
map ``SetupError`` → HTTP 400. The router owns its own ``/api/auth`` prefix
(Decision 7) and is mounted with a bare ``app.include_router(...)``.

Skeleton (step 004): the router object, route registration, and handler
signatures (incl. ``response_model`` via return annotations) are frozen; the
handler bodies are UNIMPLEMENTED.
"""

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.db.engine import is_db_ready
from app.models.schemas.auth import (
    AuthStatusResponse,
    CreateDBRequest,
    LoginResponse,
)
from app.services import auth as auth_service
from app.services import setup as setup_service

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/status")
async def get_status() -> AuthStatusResponse:
    """Report first-run readiness: ``needs_setup = not is_db_ready()``.

    Detection surface for the frontend first-run wizard.
    """
    return AuthStatusResponse(needs_setup=not is_db_ready())


@router.post("/setup/create")
async def create_db(payload: CreateDBRequest) -> LoginResponse:
    """Create the DB + first admin, then auto-sign-in (decision 8).

    Calls :func:`app.services.setup.create_database`, mints the first token via
    :func:`app.services.auth.create_token`, and returns the ``LoginResponse``.
    A ``SetupError`` from the service maps to HTTP 400 with its message.
    """
    try:
        admin = await setup_service.create_database(
            payload.admin_username, payload.password, payload.password_confirm
        )
    except setup_service.SetupError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
    return LoginResponse(token=auth_service.create_token(admin))


@router.post("/setup/import")
async def import_db(file: UploadFile = File(...)) -> AuthStatusResponse:
    """Bootstrap from a multipart-uploaded export archive (no token, decision 8).

    Reads the uploaded ``file`` bytes and calls
    :func:`app.services.setup.import_database`, returning the resulting
    ``AuthStatusResponse``. A ``SetupError`` maps to HTTP 400 and the instance
    stays unconfigured.
    """
    archive_bytes = await file.read()
    try:
        await setup_service.import_database(archive_bytes)
    except setup_service.SetupError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
    return AuthStatusResponse(needs_setup=not is_db_ready())
