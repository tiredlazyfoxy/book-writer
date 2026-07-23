"""Admin user-management request & response schemas.

Declarative Pydantic schemas — the typed contracts for the admin users surface
(``/api/admin/users``, step 002). Plain typed data shapes, no logic (see
``docs/architecture/backend.md`` — ``models/`` is tables + schemas only). Field
names/types are frozen by the skeleton (feature 005, step 001).
"""

from datetime import datetime

from pydantic import BaseModel

from app.models.user import UserRole


class AdminUserResponse(BaseModel):
    """A single account as surfaced to an admin (list + mutation results).

    Secret-excluding (US-005.AC-2): carries **no** ``pwdhash``,
    ``jwt_signing_key``, or ``salt``. Built by hand in the service response
    mapper from a ``User`` — never dumped from the ORM.

    - ``id`` — the account's 64-bit snowflake id, serialized as a **string** on
      the wire (per the system-wide snowflake convention; ``User.id`` is an
      ``int`` in Python, so the service mapper must build
      ``AdminUserResponse(id=str(user.id), …)``).
    - ``username`` — the login handle.
    - ``role`` — the account's ``UserRole`` (serializes to its string value).
    - ``last_login`` — last successful login timestamp, or ``None``.
    - ``active`` — **derived** ``pwdhash is not None`` (decision 3); computed in
      the response mapper only, never a ``User``-table column.
    """

    id: str
    username: str
    role: UserRole
    last_login: datetime | None
    active: bool


class AdminCreateUserRequest(BaseModel):
    """Body of ``POST /api/admin/users`` — new-account credentials + role.

    - ``username`` — the new account's login handle.
    - ``password`` — plaintext password (validated service-side, decision 4).
    - ``password_confirm`` — confirmation copy (must match ``password``).
    - ``role`` — the role the new account is created with.
    """

    username: str
    password: str
    password_confirm: str
    role: UserRole


class AdminSetPasswordRequest(BaseModel):
    """Body of the reset-password endpoint — the replacement password.

    - ``password`` — plaintext password (validated service-side, decision 4).
    - ``password_confirm`` — confirmation copy (must match ``password``).
    """

    password: str
    password_confirm: str


class AdminSetRoleRequest(BaseModel):
    """Body of the change-role endpoint — the target account's new role.

    - ``role`` — the ``UserRole`` to assign to the target account.
    """

    role: UserRole
