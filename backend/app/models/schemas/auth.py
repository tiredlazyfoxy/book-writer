"""Auth / first-run-bootstrap request & response schemas.

Declarative Pydantic schemas — the typed contracts for the ``/api/auth``
surface (step 004). Plain typed data shapes, no logic (see
``docs/architecture/backend.md`` — ``models/`` is tables + schemas only). Field
names/types are frozen by the skeleton (step 004).
"""

from pydantic import BaseModel

from app.models.user import UserRole


class AuthStatusResponse(BaseModel):
    """First-run readiness surfaced by ``GET /api/auth/status`` and returned by
    ``POST /api/auth/setup/import``.

    - ``needs_setup`` — ``True`` when the instance is unconfigured
      (``not is_db_ready()``); the frontend uses it to gate the first-run wizard.
    """

    needs_setup: bool


class CreateDBRequest(BaseModel):
    """Body of ``POST /api/auth/setup/create`` — the first-admin credentials.

    - ``admin_username`` — the first admin's login handle.
    - ``password`` — plaintext password (validated service-side, decision 3).
    - ``password_confirm`` — confirmation copy (must match ``password``).
    """

    admin_username: str
    password: str
    password_confirm: str


class LoginRequest(BaseModel):
    """Body of ``POST /api/auth/login`` — a user's login credentials.

    - ``username`` — the login handle.
    - ``password`` — plaintext password (verified service-side; bcrypt).
    """

    username: str
    password: str


class RefreshRequest(BaseModel):
    """Body of ``POST /api/auth/refresh`` — the refresh-token exchange request.

    - ``refresh_token`` — the per-user HS256 refresh JWT to exchange for a fresh
      access token.
    """

    refresh_token: str


class TokenResponse(BaseModel):
    """Token pair returned by ``POST /api/auth/login``, ``POST /api/auth/refresh``,
    and the auto-sign-in of ``POST /api/auth/setup/create`` (decision 8).

    Replaces the retired single-token ``LoginResponse``.

    - ``access_token`` — short-lived per-user HS256 access JWT.
    - ``refresh_token`` — long-lived per-user HS256 refresh JWT. On refresh this
      echoes the incoming refresh token (see ``context.md`` → Token model).
    """

    access_token: str
    refresh_token: str


class MeResponse(BaseModel):
    """Identity of the authenticated caller — returned by ``GET /api/auth/me``.

    - ``id`` — the caller's 64-bit snowflake id, serialized as a **string** on
      the wire (per the system-wide snowflake convention; ``User.id`` is an
      ``int`` in Python, so the coder must build ``MeResponse(id=str(user.id), …)``).
    - ``username`` — the caller's login handle.
    - ``role`` — the caller's ``UserRole`` (serializes to its string value).
    """

    id: str
    username: str
    role: UserRole
