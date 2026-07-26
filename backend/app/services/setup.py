"""First-run bootstrap service — create-DB-and-first-admin and import-DB.

Business-logic layer: **no** ``session`` / ``AsyncSession`` / ``select()`` here
(see ``docs/architecture/backend.md`` — layer separation). Persistence goes
through ``db.users`` and the import/export mechanism; the readiness flag lives in
``db.engine``. Service-side validation (min length, confirm match, already-
configured refusal) raises the typed ``SetupError`` (feature 003 decisions 3 & 4)
that the route layer (step 004) maps to an HTTP 4xx — no HTTP concerns here.

Skeleton (step 003): signatures are frozen; bodies are UNIMPLEMENTED.
"""

from app.db import assistant_modes
from app.db import users
from app.db.engine import init_db, is_db_ready, set_db_ready
from app.models.user import User, UserRole
from app.services import auth as auth_service
from app.services import db_import_export

# Minimum admin password length (feature 003 decision 7 — resolves US-001.AC-3).
MIN_PASSWORD_LENGTH = 8


class SetupError(Exception):
    """Raised for every setup refusal — already-configured, password too short,
    password mismatch, or a corrupt/invalid import.

    Carries a human-readable message the route layer maps to an HTTP 4xx. Not an
    HTTP concern in itself; the service stays transport-agnostic.
    """


async def create_database(
    admin_username: str, password: str, password_confirm: str
) -> User:
    """Orchestrate first-admin creation; return the created admin ``User``.

    Refuses (raises ``SetupError``) when the instance is already configured
    (``is_db_ready()`` true — US-001.AC-2), when ``password`` is shorter than
    ``MIN_PASSWORD_LENGTH`` (US-001.AC-3), or when ``password`` and
    ``password_confirm`` differ (US-001.AC-4). Otherwise creates the schema
    (``init_db``), mints credentials via the auth primitives, persists an
    ``admin``-role ``User`` through ``db.users.create``, flips ``set_db_ready``,
    and returns it. No ``session``/``select()`` here; the token is minted at the
    route (step 004).
    """
    if is_db_ready():
        raise SetupError("The instance is already configured.")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise SetupError(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters long."
        )
    if password != password_confirm:
        raise SetupError("Password and confirmation do not match.")

    await init_db()
    await assistant_modes.seed_default_modes()
    admin = User(
        username=admin_username,
        pwdhash=auth_service.hash_password(password),
        role=UserRole.admin,
        jwt_signing_key=auth_service.generate_signing_key(),
    )
    admin = await users.create(admin)
    set_db_ready(True)
    return admin


async def import_database(archive_bytes: bytes) -> None:
    """Bootstrap from an export archive; return ``None``.

    Wraps the import in error handling: on a corrupt/invalid archive or parse
    failure raises ``SetupError`` and does **not** call ``set_db_ready`` (the
    instance stays unconfigured — US-002.AC-2, decision 4). On success runs the
    import via ``db_import_export.import_all`` (which itself runs ``init_db``
    first and rebuilds the vector index after), seeds the fixed five assistant
    modes, then flips ``set_db_ready(True)`` (US-002.AC-1). Full transactional
    rollback of a partial import is not required.

    The seed sits in the same relative position ``create_database`` uses it —
    after the schema exists, before readiness is flipped — so an instance
    bootstrapped by import is not left without its modes (feature 012 step 001).
    It is idempotent and check-then-create keyed on ``key``, so modes carried by
    the archive keep their stored ``system_prompt`` and gain no duplicate row.
    """
    try:
        await db_import_export.import_all(archive_bytes)
    except SetupError:
        raise
    except Exception as exc:
        raise SetupError(f"The import archive is invalid or corrupt: {exc}") from exc

    await assistant_modes.seed_default_modes()
    set_db_ready(True)
