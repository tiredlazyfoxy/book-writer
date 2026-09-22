"""Admin user-management route layer for ``/api/admin/users``.

HTTP only: parse the request, call an :mod:`app.services.admin` function, map the
typed :class:`~app.services.admin.AdminError` to a status (decision 2), and
return (see ``docs/architecture/backend.md`` — layer separation; no business
logic, no DB access, no password checks here — those live in the service,
decision 4). Every endpoint is gated by ``require_role(admin)`` (step 001), which
both authorizes the caller (non-admin → 403) and yields the authenticated
``caller: User`` that the self-guarded endpoints (role / disable) thread into the
service (decision 9). The router owns its own ``/api/admin/users`` prefix and is
mounted with a bare ``app.include_router(...)`` in the composition root.

Typed-error → status map the handlers implement (decision 2):
``username-taken`` → 409, ``not-found`` → 404, ``self-target`` → 400,
``already-disabled`` → 400, ``password-invalid`` → 400. (Non-admin → 403 is
produced by ``require_role`` itself.)

Skeleton (feature 005, step 002): the router object, route registration, and
handler signatures (incl. ``response_model`` via return annotations, the
``user_id: int`` path params, the ``caller`` dependency, and the 201/204 status
codes) are frozen; the handler bodies are UNIMPLEMENTED.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.models.schemas.admin import (
    AdminCreateUserRequest,
    AdminSetPasswordRequest,
    AdminSetRoleRequest,
    AdminUserResponse,
)
from app.models.user import User, UserRole
from app.services import admin as admin_service
from app.services import auth as auth_service

router = APIRouter(prefix="/api/admin/users", tags=["admin-users"])

_ADMIN_ERROR_STATUS: dict[admin_service.AdminErrorReason, int] = {
    admin_service.AdminErrorReason.username_taken: status.HTTP_409_CONFLICT,
    admin_service.AdminErrorReason.not_found: status.HTTP_404_NOT_FOUND,
    admin_service.AdminErrorReason.self_target: status.HTTP_400_BAD_REQUEST,
    admin_service.AdminErrorReason.already_disabled: status.HTTP_400_BAD_REQUEST,
    admin_service.AdminErrorReason.password_invalid: status.HTTP_400_BAD_REQUEST,
}


def _map_admin_error(err: admin_service.AdminError) -> HTTPException:
    """Translate a typed :class:`~app.services.admin.AdminError` to an
    :class:`HTTPException` per the decision-2 status map."""
    return HTTPException(
        status_code=_ADMIN_ERROR_STATUS[err.reason],
        detail=err.message,
    )


@router.get("")
async def list_users(
    caller: User = Depends(auth_service.require_role(UserRole.admin)),
) -> list[AdminUserResponse]:
    """List every account (``GET /api/admin/users`` → 200).

    Delegates to :func:`app.services.admin.list_users` and returns the account
    list (US-005.AC-1/AC-2/AC-3).
    """
    return await admin_service.list_users()


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: AdminCreateUserRequest,
    caller: User = Depends(auth_service.require_role(UserRole.admin)),
) -> AdminUserResponse:
    """Create an account (``POST /api/admin/users`` → 201).

    Delegates to :func:`app.services.admin.create_user`; maps the typed
    ``AdminError`` (``username-taken`` → 409, ``password-invalid`` → 400) to its
    status (US-006.AC-1/AC-2).
    """
    try:
        return await admin_service.create_user(payload)
    except admin_service.AdminError as err:
        raise _map_admin_error(err)


@router.put("/{user_id}/password", status_code=status.HTTP_204_NO_CONTENT)
async def set_user_password(
    user_id: int,
    payload: AdminSetPasswordRequest,
    caller: User = Depends(auth_service.require_role(UserRole.admin)),
) -> None:
    """Reset a target's password (``PUT /api/admin/users/{user_id}/password`` → 204).

    Delegates to :func:`app.services.admin.set_user_password`; maps the typed
    ``AdminError`` (``not-found`` → 404, ``password-invalid`` → 400) to its status
    (US-007.AC-1/AC-2).
    """
    try:
        await admin_service.set_user_password(user_id, payload)
    except admin_service.AdminError as err:
        raise _map_admin_error(err)


@router.put("/{user_id}/role", status_code=status.HTTP_204_NO_CONTENT)
async def set_user_role(
    user_id: int,
    payload: AdminSetRoleRequest,
    caller: User = Depends(auth_service.require_role(UserRole.admin)),
) -> None:
    """Change a target's role (``PUT /api/admin/users/{user_id}/role`` → 204).

    Threads ``caller`` into :func:`app.services.admin.set_user_role` for the
    self-guard (decision 9); maps the typed ``AdminError`` (``self-target`` → 400,
    ``not-found`` → 404) to its status (US-008.AC-1/AC-2).
    """
    try:
        await admin_service.set_user_role(caller, user_id, payload)
    except admin_service.AdminError as err:
        raise _map_admin_error(err)


@router.put("/{user_id}/disable", status_code=status.HTTP_204_NO_CONTENT)
async def disable_user(
    user_id: int,
    caller: User = Depends(auth_service.require_role(UserRole.admin)),
) -> None:
    """Disable a target account (``PUT /api/admin/users/{user_id}/disable`` → 204).

    Threads ``caller`` into :func:`app.services.admin.disable_user` for the
    self-guard (decision 9); maps the typed ``AdminError`` (``self-target`` → 400,
    ``not-found`` → 404, ``already-disabled`` → 400) to its status
    (US-009.AC-1/AC-3).
    """
    try:
        await admin_service.disable_user(caller, user_id)
    except admin_service.AdminError as err:
        raise _map_admin_error(err)
