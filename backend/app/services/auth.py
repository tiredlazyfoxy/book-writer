"""Auth primitives — bcrypt hashing + per-user HS256 JWT minting.

Business-logic layer: **no** ``session`` / ``AsyncSession`` / ``select()`` here
(see ``docs/architecture/backend.md`` — layer separation). This step provides
only the minimal subset needed to hash the first admin's password and mint its
first token; token verification, rotation-on-login, and logout are feature
004's and are deliberately absent.

Skeleton (step 001): signatures are frozen; bodies are UNIMPLEMENTED.
"""

import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.models.user import User


def hash_password(password: str) -> str:
    """Bcrypt-hash a plaintext ``password`` and return the hash string.

    Bcrypt embeds its own salt (decision 2) — no external salt argument.
    """
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, pwdhash: str) -> bool:
    """Return whether ``password`` matches the stored bcrypt ``pwdhash``."""
    return bcrypt.checkpw(password.encode("utf-8"), pwdhash.encode("utf-8"))


def generate_signing_key() -> str:
    """Return a fresh random per-user signing key (e.g. ``token_hex(32)``)."""
    return secrets.token_hex(32)


def create_token(user: User) -> str:
    """Mint a stateless HS256 JWT for ``user``, signed with that user's own
    ``jwt_signing_key``.

    Payload carries ``user_id``, ``username``, ``role``, and an ``exp`` roughly
    30 days out. Returns the encoded token string.
    """
    if user.jwt_signing_key is None:
        raise ValueError("User has no jwt_signing_key — cannot mint a token.")
    payload = {
        "user_id": user.id,
        "username": user.username,
        "role": user.role.value,
        "exp": datetime.now(timezone.utc) + timedelta(days=30),
    }
    return jwt.encode(payload, user.jwt_signing_key, algorithm="HS256")
