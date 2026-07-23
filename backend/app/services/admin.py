"""Admin user-management service — the account lifecycle (feature 005).

Business-logic layer: **no** ``session`` / ``AsyncSession`` / ``select()`` /
``session.exec()`` / ``session.add()`` here (see ``docs/architecture/backend.md``
— layer separation). All persistence goes through the session-free
``app.db.users`` layer; mutations mutate the ``User`` object and call
``users.update``. Credential minting and the shared password policy come from
``app.services.auth``.

Orchestrates: list / create / reset-password / change-role / disable, with
self-guards, credential minting/nulling, and the secret-excluding response
mapping (US-005..009). Domain refusals raise the typed :class:`AdminError`,
discriminated by :class:`AdminErrorReason` so step 002's route maps each case to
its HTTP status (decision 2); the route stays HTTP-only.

Skeleton (feature 005, step 001): signatures are frozen; the error taxonomy and
its shape are declared; the function bodies are UNIMPLEMENTED.
"""

import enum
from datetime import datetime, timezone

from app.db import users
from app.models.schemas.admin import (
    AdminCreateUserRequest,
    AdminSetPasswordRequest,
    AdminSetRoleRequest,
    AdminUserResponse,
)
from app.models.user import User
from app.services import auth as auth_service


class AdminErrorReason(str, enum.Enum):
    """Discriminator for :class:`AdminError` — the admin service refusal taxonomy.

    Step 002's route maps each case to its HTTP status (decision 2):
    ``username_taken`` → 409, ``not_found`` → 404, ``self_target`` → 400,
    ``already_disabled`` → 400, ``password_invalid`` → 400.
    """

    username_taken = "username-taken"
    not_found = "not-found"
    self_target = "self-target"
    already_disabled = "already-disabled"
    password_invalid = "password-invalid"


class AdminError(Exception):
    """Raised by the admin service for every domain refusal.

    Carries a :class:`AdminErrorReason` discriminator (``reason``) plus a
    human-readable ``message``; the route branches on ``reason`` to pick the
    status (decision 2). Password-policy failures surface here as
    ``AdminErrorReason.password_invalid`` — the service catches
    ``auth.PasswordPolicyError`` from :func:`auth.validate_password_policy` and
    re-raises this.

    Lives here in ``services/admin.py`` (mirroring ``AuthError`` in
    ``services/auth.py``): step 002's route already imports
    ``from app.services import admin as admin_service`` and reaches it as
    ``admin_service.AdminError`` / ``admin_service.AdminErrorReason``.
    """

    def __init__(self, reason: AdminErrorReason, message: str = "") -> None:
        self.reason = reason
        self.message = message
        super().__init__(message)


def _to_response(user: User) -> AdminUserResponse:
    """Map a ``User`` to an :class:`AdminUserResponse` by hand (never dump the ORM).

    Copies only non-secret fields and derives ``active = user.pwdhash is not
    None`` (decision 3); builds ``id=str(user.id)`` (snowflake serialized as a
    string on the wire). Excludes ``pwdhash`` / ``jwt_signing_key`` (US-005.AC-2).
    """
    return AdminUserResponse(
        id=str(user.id),
        username=user.username,
        role=user.role,
        last_login=user.last_login,
        active=user.pwdhash is not None,
    )


async def list_users() -> list[AdminUserResponse]:
    """Return every account (via ``users.get_all``) mapped to
    :class:`AdminUserResponse`, ordered by username (US-005.AC-1)."""
    all_users = await users.get_all()
    return [_to_response(user) for user in all_users]


async def create_user(req: AdminCreateUserRequest) -> AdminUserResponse:
    """Create a new account with the requested role and return its
    :class:`AdminUserResponse` (``active`` true).

    Validates the password policy via ``auth.validate_password_policy`` (raising
    :class:`AdminError` ``password_invalid`` on failure), refuses a taken
    username (:class:`AdminError` ``username_taken``), hashes the password, mints
    a fresh signing key + ``last_key_update``, and persists via ``users.create``
    (US-006.AC-1/AC-2, decision 4).
    """
    try:
        auth_service.validate_password_policy(req.password, req.password_confirm)
    except auth_service.PasswordPolicyError as exc:
        raise AdminError(AdminErrorReason.password_invalid, str(exc))

    if await users.get_by_username(req.username) is not None:
        raise AdminError(
            AdminErrorReason.username_taken,
            f"Username '{req.username}' is already taken.",
        )

    user = User(
        username=req.username,
        pwdhash=auth_service.hash_password(req.password),
        role=req.role,
        jwt_signing_key=auth_service.generate_signing_key(),
        last_key_update=datetime.now(timezone.utc),
    )
    user = await users.create(user)
    return _to_response(user)


async def set_user_password(
    user_id: int, req: AdminSetPasswordRequest
) -> AdminUserResponse:
    """Reset the target account's password and return its
    :class:`AdminUserResponse`.

    Refuses a missing target (:class:`AdminError` ``not_found``), validates the
    password policy (:class:`AdminError` ``password_invalid``), then sets a new
    ``pwdhash`` + fresh ``jwt_signing_key`` + ``last_key_update`` via
    ``users.update`` — re-enabling a disabled account (the sole re-enable path,
    US-007.AC-1/AC-2, decision 6).
    """
    try:
        auth_service.validate_password_policy(req.password, req.password_confirm)
    except auth_service.PasswordPolicyError as exc:
        raise AdminError(AdminErrorReason.password_invalid, str(exc))

    user = await users.get_by_id(user_id)
    if user is None:
        raise AdminError(AdminErrorReason.not_found, "User not found.")

    user.pwdhash = auth_service.hash_password(req.password)
    user.jwt_signing_key = auth_service.generate_signing_key()
    user.last_key_update = datetime.now(timezone.utc)
    user = await users.update(user)
    return _to_response(user)


async def set_user_role(
    caller: User, user_id: int, req: AdminSetRoleRequest
) -> AdminUserResponse:
    """Change the target account's role and return its :class:`AdminUserResponse`.

    Refuses a self-target (``caller.id == user_id`` → :class:`AdminError`
    ``self_target``) and a missing target (:class:`AdminError` ``not_found``),
    then updates the role via ``users.update`` (US-008.AC-1/AC-2, decision 9).
    """
    if caller.id == user_id:
        raise AdminError(
            AdminErrorReason.self_target, "Cannot change your own role."
        )

    user = await users.get_by_id(user_id)
    if user is None:
        raise AdminError(AdminErrorReason.not_found, "User not found.")

    user.role = req.role
    user = await users.update(user)
    return _to_response(user)


async def disable_user(caller: User, user_id: int) -> AdminUserResponse:
    """Disable the target account and return its :class:`AdminUserResponse`
    (``active`` false).

    Refuses a self-target (:class:`AdminError` ``self_target``), a missing target
    (:class:`AdminError` ``not_found``), and an already-disabled target
    (``pwdhash is None`` → :class:`AdminError` ``already_disabled``). Nulls
    ``pwdhash`` **and** ``jwt_signing_key`` via ``users.update`` (no ``salt``),
    preserving id/username/role/last_login (US-009.AC-1/AC-2/AC-3, decision 5).
    """
    if caller.id == user_id:
        raise AdminError(
            AdminErrorReason.self_target, "Cannot disable your own account."
        )

    user = await users.get_by_id(user_id)
    if user is None:
        raise AdminError(AdminErrorReason.not_found, "User not found.")

    if user.pwdhash is None:
        raise AdminError(
            AdminErrorReason.already_disabled, "User is already disabled."
        )

    user.pwdhash = None
    user.jwt_signing_key = None
    user = await users.update(user)
    return _to_response(user)
