"""Auth / first-run-bootstrap request & response schemas.

Declarative Pydantic schemas — the typed contracts for the ``/api/auth``
surface (step 004). Plain typed data shapes, no logic (see
``docs/architecture/backend.md`` — ``models/`` is tables + schemas only). Field
names/types are frozen by the skeleton (step 004).
"""

from pydantic import BaseModel


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


class LoginResponse(BaseModel):
    """Auto-sign-in result of ``POST /api/auth/setup/create`` (decision 8).

    - ``token`` — the minted per-user HS256 JWT for the freshly created admin.
    """

    token: str
