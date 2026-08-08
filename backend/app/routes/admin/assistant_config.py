"""Admin assistant-config route layer for ``/api/admin/assistant-config``.

HTTP only: parse the request, call one :mod:`app.services.assistant_config`
function, map the typed
:class:`~app.services.assistant_config.AssistantConfigError` to a status, and
return (see ``docs/architecture/backend.md`` — layer separation; no business
logic, no DB access and no conditional about configuration state here). Every
endpoint is gated by ``require_role(admin)``
(``docs/architecture/authorization.md`` → "Global assistant configuration
(FEAT-020) — admin only"), which authorizes the caller (non-admin → 403) and
yields the authenticated ``caller: User``; this feature does not thread the
caller into the service (the guard alone provides gating). The router owns its
own ``/api/admin/assistant-config`` prefix and is mounted with a bare
``app.include_router(...)`` in the composition root, the
``routes/admin/llm_servers.py:44`` / ``main.py:82`` precedent.

Route ordering is load-bearing: FastAPI matches in declaration order, so within
each family the static segments are declared **before** the ``{param}`` routes —
``GET /modes`` before ``PUT /modes/{mode_key}``, and ``GET``/``POST
/sub-agents`` before ``PUT /sub-agents/{sub_agent_id}``. The two ``/disable`` /
``/enable`` segments sit *after* the param, so nothing can swallow them; no
``/sub-agents/{sub_agent_id}/{anything}`` route exists and none may be added.

``sub_agent_id`` is a **``str``** path param, handed to the service as-is: the
service owns the parse (``_parse_sub_agent_id``) and answers
``sub-agent-not-found`` → 404 for a value that is not an id. Declaring it
``int`` would make FastAPI answer 422 where the spec requires 404, and would put
the "what does a malformed id mean" decision in ``routes/``. This deliberately
overrides the ``routes/admin/llm_servers.py:103 server_id: int`` precedent for
this feature. ``mode_key`` is a plain string (the mode's natural primary key).

Typed-error → status map the handlers implement — **every** reason the service
can raise appears, so an unmapped reason can never fall through to a 500:
``mode-not-found`` → 404, ``sub-agent-not-found`` → 404, ``name-taken`` → 409,
``blank-name`` / ``invalid-model-pair`` / ``unknown-or-inactive-server`` /
``model-not-enabled`` / ``unknown-tool`` / ``unknown-sub-agent`` /
``sub-agent-disabled`` → 400. (Non-admin → 403 is produced by ``require_role``
itself; no handler here raises it.)

There is deliberately **no single-mode GET** (the editor loads all five in one
call) and deliberately **no DELETE anywhere** — disable-not-delete
(``context.md`` → scope decision 6).

The eight handlers are the tool catalogue read, the mode list and mode save, and
the sub-agent list / create (201) / update / disable / enable — each one call
into :mod:`app.services.assistant_config` wrapped in the error→status mapping
above.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.models.schemas.assistant_config import (
    AssistantModeResponse,
    AssistantModesListResponse,
    CreateSubAgentRequest,
    SubAgentResponse,
    SubAgentsListResponse,
    ToolsListResponse,
    UpdateAssistantModeRequest,
    UpdateSubAgentRequest,
)
from app.models.user import User, UserRole
from app.services import assistant_config as assistant_config_service
from app.services import auth as auth_service

router = APIRouter(
    prefix="/api/admin/assistant-config", tags=["admin-assistant-config"]
)

_ASSISTANT_CONFIG_ERROR_STATUS: dict[
    assistant_config_service.AssistantConfigErrorReason, int
] = {
    assistant_config_service.AssistantConfigErrorReason.mode_not_found: (
        status.HTTP_404_NOT_FOUND
    ),
    assistant_config_service.AssistantConfigErrorReason.sub_agent_not_found: (
        status.HTTP_404_NOT_FOUND
    ),
    assistant_config_service.AssistantConfigErrorReason.name_taken: (
        status.HTTP_409_CONFLICT
    ),
    assistant_config_service.AssistantConfigErrorReason.blank_name: (
        status.HTTP_400_BAD_REQUEST
    ),
    assistant_config_service.AssistantConfigErrorReason.invalid_model_pair: (
        status.HTTP_400_BAD_REQUEST
    ),
    assistant_config_service.AssistantConfigErrorReason.unknown_or_inactive_server: (
        status.HTTP_400_BAD_REQUEST
    ),
    assistant_config_service.AssistantConfigErrorReason.model_not_enabled: (
        status.HTTP_400_BAD_REQUEST
    ),
    assistant_config_service.AssistantConfigErrorReason.unknown_tool: (
        status.HTTP_400_BAD_REQUEST
    ),
    assistant_config_service.AssistantConfigErrorReason.unknown_sub_agent: (
        status.HTTP_400_BAD_REQUEST
    ),
    assistant_config_service.AssistantConfigErrorReason.sub_agent_disabled: (
        status.HTTP_400_BAD_REQUEST
    ),
}


def _map_assistant_config_error(
    err: assistant_config_service.AssistantConfigError,
) -> HTTPException:
    """Translate a typed
    :class:`~app.services.assistant_config.AssistantConfigError` to an
    :class:`HTTPException` per this module's status map."""
    return HTTPException(
        status_code=_ASSISTANT_CONFIG_ERROR_STATUS[err.reason],
        detail=err.message,
    )


@router.get("/tools")
async def list_tools(
    caller: User = Depends(auth_service.require_role(UserRole.admin)),
) -> ToolsListResponse:
    """Return the read-only tool catalogue
    (``GET /api/admin/assistant-config/tools`` → 200, UC-095 step 3,
    UC-096 step 4)."""
    try:
        return await assistant_config_service.list_tools()
    except assistant_config_service.AssistantConfigError as err:
        raise _map_assistant_config_error(err)


@router.get("/modes")
async def list_modes(
    caller: User = Depends(auth_service.require_role(UserRole.admin)),
) -> AssistantModesListResponse:
    """List every assistant mode with its configuration
    (``GET .../modes`` → 200, UC-095 step 1; US-110.AC-1)."""
    try:
        return await assistant_config_service.list_modes()
    except assistant_config_service.AssistantConfigError as err:
        raise _map_assistant_config_error(err)


@router.put("/modes/{mode_key}")
async def save_mode(
    mode_key: str,
    payload: UpdateAssistantModeRequest,
    caller: User = Depends(auth_service.require_role(UserRole.admin)),
) -> AssistantModeResponse:
    """Full-replace one mode's prompt, tools and sub-agents
    (``PUT .../modes/{mode_key}`` → 200, 404 if the mode is unknown,
    UC-095 steps 2–5; US-110.AC-1, US-111.AC-1, US-112.AC-1)."""
    try:
        return await assistant_config_service.save_mode(mode_key, payload)
    except assistant_config_service.AssistantConfigError as err:
        raise _map_assistant_config_error(err)


@router.get("/sub-agents")
async def list_sub_agents(
    caller: User = Depends(auth_service.require_role(UserRole.admin)),
) -> SubAgentsListResponse:
    """List every sub-agent, disabled ones included
    (``GET .../sub-agents`` → 200, UC-097 step 1; US-113.AC-1)."""
    try:
        return await assistant_config_service.list_sub_agents()
    except assistant_config_service.AssistantConfigError as err:
        raise _map_assistant_config_error(err)


@router.post("/sub-agents", status_code=status.HTTP_201_CREATED)
async def create_sub_agent(
    payload: CreateSubAgentRequest,
    caller: User = Depends(auth_service.require_role(UserRole.admin)),
) -> SubAgentResponse:
    """Create a sub-agent (``POST .../sub-agents`` → 201, UC-096;
    US-113.AC-1, US-113.AC-3, US-113.AC-5)."""
    try:
        return await assistant_config_service.create_sub_agent(payload)
    except assistant_config_service.AssistantConfigError as err:
        raise _map_assistant_config_error(err)


@router.put("/sub-agents/{sub_agent_id}")
async def update_sub_agent(
    sub_agent_id: str,
    payload: UpdateSubAgentRequest,
    caller: User = Depends(auth_service.require_role(UserRole.admin)),
) -> SubAgentResponse:
    """Full-replace one sub-agent's editable fields and both selection sets
    (``PUT .../sub-agents/{sub_agent_id}`` → 200, 404 if the id is unknown or
    ill-formed, UC-097 steps 2–3; US-114.AC-1, US-114.AC-4)."""
    try:
        return await assistant_config_service.update_sub_agent(
            sub_agent_id, payload
        )
    except assistant_config_service.AssistantConfigError as err:
        raise _map_assistant_config_error(err)


@router.post("/sub-agents/{sub_agent_id}/disable")
async def disable_sub_agent(
    sub_agent_id: str,
    caller: User = Depends(auth_service.require_role(UserRole.admin)),
) -> SubAgentResponse:
    """Disable a sub-agent, detaching it from every mode
    (``POST .../sub-agents/{sub_agent_id}/disable`` → 200, 404 if the id is
    unknown or ill-formed, UC-097 alternate flow; US-114.AC-2). There is no
    hard delete."""
    try:
        return await assistant_config_service.set_sub_agent_disabled(
            sub_agent_id, True
        )
    except assistant_config_service.AssistantConfigError as err:
        raise _map_assistant_config_error(err)


@router.post("/sub-agents/{sub_agent_id}/enable")
async def enable_sub_agent(
    sub_agent_id: str,
    caller: User = Depends(auth_service.require_role(UserRole.admin)),
) -> SubAgentResponse:
    """Re-enable a sub-agent, restoring no mode links
    (``POST .../sub-agents/{sub_agent_id}/enable`` → 200, 404 if the id is
    unknown or ill-formed, UC-097 alternate flow; US-114.AC-3)."""
    try:
        return await assistant_config_service.set_sub_agent_disabled(
            sub_agent_id, False
        )
    except assistant_config_service.AssistantConfigError as err:
        raise _map_assistant_config_error(err)
