"""Admin LLM-server route layer for ``/api/admin/llm-servers``.

HTTP only: parse the request, call one :mod:`app.services.llm_servers` function,
map the typed :class:`~app.services.llm_servers.LlmServerError` to a status (D7),
and return (see ``docs/architecture/backend.md`` — layer separation; no business
logic, no DB access here). Every endpoint is gated by ``require_role(admin)``
(feature 005), which authorizes the caller (non-admin → 403) and yields the
authenticated ``caller: User``; this feature does not thread the caller into the
service (the guard alone provides gating). The router owns its own
``/api/admin/llm-servers`` prefix and is mounted with a bare
``app.include_router(...)`` in the composition root.

Route ordering (D5) is load-bearing: FastAPI matches in declaration order, so the
static ``/embedding`` routes are declared **before** the ``/{server_id}`` param
routes — otherwise ``embedding`` is captured as a ``server_id``.

Typed-error → status map the handlers implement (D7): ``missing-field`` → 400,
``invalid-backend-type`` → 400, ``env-not-set`` → 400, ``not-found`` → 404,
``probe-failed`` → 502. (Non-admin → 403 is produced by ``require_role`` itself.)

Skeleton (feature 006, step 004): the router object, route registration, and
handler signatures (incl. ``response_model`` via return annotations, the
``server_id: int`` path params, the ``caller`` dependency, and the 201/204 status
codes) are frozen, and the error→status map + helper are real; the handler bodies
are UNIMPLEMENTED.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.models.schemas.llm_servers import (
    AvailableModelsResponse,
    CreateLlmServerRequest,
    EmbeddingConfigResponse,
    EnabledModelsRequest,
    LlmServerResponse,
    LlmServersListResponse,
    SetEmbeddingRequest,
    UpdateLlmServerRequest,
)
from app.models.user import User, UserRole
from app.services import auth as auth_service
from app.services import llm_servers as llm_servers_service

router = APIRouter(prefix="/api/admin/llm-servers", tags=["admin-llm-servers"])

_LLM_SERVER_ERROR_STATUS: dict[llm_servers_service.LlmServerErrorReason, int] = {
    llm_servers_service.LlmServerErrorReason.missing_field: status.HTTP_400_BAD_REQUEST,
    llm_servers_service.LlmServerErrorReason.invalid_backend_type: status.HTTP_400_BAD_REQUEST,
    llm_servers_service.LlmServerErrorReason.env_not_set: status.HTTP_400_BAD_REQUEST,
    llm_servers_service.LlmServerErrorReason.not_found: status.HTTP_404_NOT_FOUND,
    llm_servers_service.LlmServerErrorReason.probe_failed: status.HTTP_502_BAD_GATEWAY,
}


def _map_llm_server_error(err: llm_servers_service.LlmServerError) -> HTTPException:
    """Translate a typed :class:`~app.services.llm_servers.LlmServerError` to an
    :class:`HTTPException` per the decision-7 status map."""
    return HTTPException(
        status_code=_LLM_SERVER_ERROR_STATUS[err.reason],
        detail=err.message,
    )


@router.get("")
async def list_servers(
    caller: User = Depends(auth_service.require_role(UserRole.admin)),
) -> LlmServersListResponse:
    """List every LLM server (``GET /api/admin/llm-servers`` → 200, US-010)."""
    return await llm_servers_service.get_all_servers()


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_server(
    payload: CreateLlmServerRequest,
    caller: User = Depends(auth_service.require_role(UserRole.admin)),
) -> LlmServerResponse:
    """Create a server (``POST /api/admin/llm-servers`` → 201, US-010.AC-1/AC-2/AC-3)."""
    try:
        return await llm_servers_service.create_server(payload)
    except llm_servers_service.LlmServerError as err:
        raise _map_llm_server_error(err)


@router.get("/embedding")
async def get_embedding_config(
    caller: User = Depends(auth_service.require_role(UserRole.admin)),
) -> EmbeddingConfigResponse:
    """Report the current embedding designation (``GET .../embedding`` → 200, US-014)."""
    return await llm_servers_service.get_embedding_config()


@router.delete("/embedding", status_code=status.HTTP_204_NO_CONTENT)
async def clear_embedding_config(
    caller: User = Depends(auth_service.require_role(UserRole.admin)),
) -> None:
    """Clear the embedding designation (``DELETE .../embedding`` → 204, US-014)."""
    await llm_servers_service.clear_embedding_server()
    return None


@router.put("/{server_id}")
async def update_server(
    server_id: int,
    payload: UpdateLlmServerRequest,
    caller: User = Depends(auth_service.require_role(UserRole.admin)),
) -> LlmServerResponse:
    """Update a server (``PUT .../{server_id}`` → 200, 404 if missing, US-013.AC-1)."""
    try:
        return await llm_servers_service.update_server(server_id, payload)
    except llm_servers_service.LlmServerError as err:
        raise _map_llm_server_error(err)


@router.delete("/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_server(
    server_id: int,
    caller: User = Depends(auth_service.require_role(UserRole.admin)),
) -> None:
    """Delete a server (``DELETE .../{server_id}`` → 204, 404 if missing, US-013.AC-2)."""
    try:
        await llm_servers_service.delete_server(server_id)
    except llm_servers_service.LlmServerError as err:
        raise _map_llm_server_error(err)
    return None


@router.get("/{server_id}/available-models")
async def get_available_models(
    server_id: int,
    caller: User = Depends(auth_service.require_role(UserRole.admin)),
) -> AvailableModelsResponse:
    """Probe a server for the models it offers (``GET .../{server_id}/available-models``
    → 200, 502 on probe failure, US-011.AC-1/AC-2)."""
    try:
        models = await llm_servers_service.probe_models(server_id)
    except llm_servers_service.LlmServerError as err:
        raise _map_llm_server_error(err)
    return AvailableModelsResponse(models=models)


@router.put("/{server_id}/enabled-models")
async def set_enabled_models(
    server_id: int,
    payload: EnabledModelsRequest,
    caller: User = Depends(auth_service.require_role(UserRole.admin)),
) -> LlmServerResponse:
    """Set the enabled-models subset (``PUT .../{server_id}/enabled-models`` → 200,
    US-012.AC-1)."""
    try:
        return await llm_servers_service.set_enabled_models(
            server_id, payload.enabled_models
        )
    except llm_servers_service.LlmServerError as err:
        raise _map_llm_server_error(err)


@router.put("/{server_id}/embedding", status_code=status.HTTP_204_NO_CONTENT)
async def set_embedding_server(
    server_id: int,
    payload: SetEmbeddingRequest,
    caller: User = Depends(auth_service.require_role(UserRole.admin)),
) -> None:
    """Designate this server + model as the embedding provider
    (``PUT .../{server_id}/embedding`` → 204, US-014.AC-1/AC-2)."""
    try:
        await llm_servers_service.set_embedding_server(server_id, payload.model)
    except llm_servers_service.LlmServerError as err:
        raise _map_llm_server_error(err)
    return None
