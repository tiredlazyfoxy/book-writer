"""Auth primitives + token core + the FastAPI auth dependency.

Business-logic layer: **no** ``session`` / ``AsyncSession`` / ``select()`` here
(see ``docs/architecture/backend.md`` — layer separation). The auth dependency
loads users only through the session-free ``app.db.users`` layer. Importing
``fastapi`` (``Depends`` / ``HTTPBearer`` / ``HTTPException``) is accepted here:
``get_current_user`` is a cross-cutting concern, not DB orchestration
(see ``docs/plans/004.authentication-session/001.context.md``).

Token model (see ``context.md`` → "Token model"):
- access token — HS256 per-user key, payload
  ``{user_id, username, role, type:"access", exp:+30min}``.
- refresh token — HS256 same per-user key, payload
  ``{user_id, type:"refresh", exp:+30days}``.
- the ``user_id`` claim is serialized as a **string** (``str(user.id)``) in both
  payloads (64-bit snowflake ids lose precision as JSON numbers); it is parsed
  back to an ``int`` on decode.

Skeleton (feature 004, step 001): the six new signatures below are frozen; their
bodies are UNIMPLEMENTED (raise ``NotImplementedError``). The three feature-003
primitives (``hash_password`` / ``verify_password`` / ``generate_signing_key``)
keep their real bodies. 003's single ``create_token`` is removed — replaced by
``create_access_token`` / ``create_refresh_token``.
"""

import secrets
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.db import users
from app.models.user import User, UserRole
from app.services import rate_limit

_bearer_scheme = HTTPBearer()


class AuthError(Exception):
    """Raised by the auth service for **every** login/refresh refusal.

    A single typed refusal covering bad credentials, unknown user, disabled user
    (``pwdhash is None``), rate-limited username, and invalid/expired/wrong-type
    refresh token. The step-003 route maps it to one generic **401**, so callers
    must not branch on any distinguishing detail — that would leak enumeration
    signal (see ``context.md`` → "Rate-limiting" / generic-refusal rule).

    Lives here in ``services/auth.py`` (not a separate errors module): the route
    already imports ``from app.services import auth as auth_service`` and reaches
    it as ``auth_service.AuthError``, so no new import path or layer boundary is
    introduced.
    """

# Token lifetimes and the per-user key rotation window (see context.md → "Token model").
ACCESS_TOKEN_TTL = timedelta(minutes=30)
REFRESH_TOKEN_TTL = timedelta(days=30)
KEY_ROTATION_WINDOW = timedelta(days=30)


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


# Minimum password length for admin create/reset — mirrors 003's setup policy
# (``services/setup.MIN_PASSWORD_LENGTH``). Feature 005 reuses this shared
# validator rather than inlining a third copy; converging 003's inline check
# onto it is a deferred observation (see 005/001.context.md), not this step.
MIN_PASSWORD_LENGTH = 8


class PasswordPolicyError(Exception):
    """Raised by :func:`validate_password_policy` when a candidate password is
    too short or its confirmation does not match.

    Neutral, transport-agnostic, and layer-safe: it lives beside the password
    primitives so the admin service (which imports ``auth``) can catch it and
    surface it as its own ``password-invalid`` taxonomy case (→ 400) without
    ``auth`` importing ``admin``. Carries a human-readable message.
    """


def validate_password_policy(password: str, password_confirm: str) -> None:
    """Enforce the shared password policy — min length
    ``MIN_PASSWORD_LENGTH`` **and** ``password == password_confirm`` — reused by
    the admin ``create_user`` / ``set_user_password`` flows (decision 4).

    Returns ``None`` when the password is acceptable; raises
    :class:`PasswordPolicyError` (with a reason message) when it is too short or
    the confirmation does not match.
    """
    if len(password) < MIN_PASSWORD_LENGTH:
        raise PasswordPolicyError(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters long."
        )
    if password != password_confirm:
        raise PasswordPolicyError("Password and confirmation do not match.")


def create_access_token(user: User) -> str:
    """Mint an HS256 **access** JWT for ``user``, signed with that user's own
    ``jwt_signing_key``.

    Payload carries ``user_id`` (as a **string**, ``str(user.id)``),
    ``username``, ``role``, ``type == "access"``, and an ``exp`` ~30 minutes out.
    Returns the encoded token string.
    """
    payload = {
        "user_id": str(user.id),
        "username": user.username,
        "role": user.role.value,
        "type": "access",
        "exp": datetime.now(timezone.utc) + ACCESS_TOKEN_TTL,
    }
    return jwt.encode(payload, user.jwt_signing_key, algorithm="HS256")


def create_refresh_token(user: User) -> str:
    """Mint an HS256 **refresh** JWT for ``user``, signed with the same per-user
    ``jwt_signing_key``.

    Payload carries ``user_id`` (as a **string**, ``str(user.id)``),
    ``type == "refresh"``, and an ``exp`` ~30 days out. Returns the encoded
    token string.
    """
    payload = {
        "user_id": str(user.id),
        "type": "refresh",
        "exp": datetime.now(timezone.utc) + REFRESH_TOKEN_TTL,
    }
    return jwt.encode(payload, user.jwt_signing_key, algorithm="HS256")


def decode_token_unverified(token: str) -> int:
    """Read ``token``'s ``user_id`` claim **without** verifying the signature,
    and return it parsed back to an ``int`` (so ``users.get_by_id`` receives an
    int; the two-stage decode needs the id before the per-user key is known).

    Signals a malformed/unreadable token or a missing/non-int ``user_id`` claim
    by raising (frozen contract: a PyJWT ``jwt.InvalidTokenError`` for an
    unreadable token / absent claim, or ``ValueError`` when the claim is not an
    integer string). ``get_current_user`` maps any such failure to 401.
    """
    claims = jwt.decode(token, options={"verify_signature": False})
    raw = claims.get("user_id")
    if raw is None:
        raise jwt.InvalidTokenError("missing user_id claim")
    return int(raw)


def verify_token_signature(token: str, signing_key: str) -> dict:
    """Verify ``token``'s signature **and** expiry against ``signing_key`` and
    return the decoded claims.

    Propagates the distinct PyJWT failures so callers can map them
    (frozen contract): ``jwt.ExpiredSignatureError`` on expiry versus
    ``jwt.InvalidTokenError`` (e.g. ``jwt.InvalidSignatureError``) on a bad or
    rotated-key signature. Does **not** convert to HTTP itself.
    """
    return jwt.decode(token, signing_key, algorithms=["HS256"])


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> User:
    """FastAPI auth dependency guarding protected routes.

    Reads ``user_id`` via ``decode_token_unverified``, loads the ``User`` via
    ``users.get_by_id``, verifies the signature + expiry with
    ``verify_token_signature`` against that user's key, requires the claim
    ``type == "access"``, and rejects a disabled user (``pwdhash is None``).
    Returns the ``User`` on success. **Any** failure — missing/malformed token,
    unknown user, bad/rotated signature, expired token, wrong ``type``, or
    disabled user — raises ``HTTPException`` **401**.
    """
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = credentials.credentials

    # Stage 1: read the claimed user id without verifying the signature.
    try:
        user_id = decode_token_unverified(token)
    except (jwt.InvalidTokenError, ValueError, TypeError):
        raise unauthorized

    # Stage 2: load the user; a null signing key cannot verify anything.
    user = await users.get_by_id(user_id)
    if user is None or user.jwt_signing_key is None:
        raise unauthorized

    # Stage 3: verify signature + expiry against that user's own key. Both
    # ExpiredSignatureError and InvalidSignatureError subclass InvalidTokenError.
    try:
        claims = verify_token_signature(token, user.jwt_signing_key)
    except jwt.InvalidTokenError:
        raise unauthorized

    # Only access tokens authenticate; a refresh token must not stand in.
    if claims.get("type") != "access":
        raise unauthorized

    # A user with a null pwdhash is disabled.
    if user.pwdhash is None:
        raise unauthorized

    return user


def require_role(min_role: UserRole) -> Callable[..., Awaitable[User]]:
    """Dependency **factory**: given a minimum ``UserRole``, return a FastAPI
    dependency that authorizes the caller by role (feature 005; first realization
    of the 004→005 deferral).

    The returned coroutine dependency resolves the caller via
    ``Depends(get_current_user)``, compares the caller's role against the numeric
    ladder ``{author: 0, admin: 1}``, and returns the caller ``User`` when the
    caller's level is **at least** ``min_role``'s level; otherwise it raises
    ``HTTPException`` **403** directly (the same sanctioned services-layer pattern
    ``get_current_user`` uses for 401). Admin routes call ``require_role(admin)``.

    Because the inner dependency takes the caller as a defaulted
    ``Depends(get_current_user)`` parameter, tests can build
    ``require_role(admin)`` and invoke the returned function directly with a
    ``User`` to assert the ladder without a live request (DoD-13).
    """

    ladder = {UserRole.author: 0, UserRole.admin: 1}

    async def dependency(user: User = Depends(get_current_user)) -> User:
        if ladder[user.role] >= ladder[min_role]:
            return user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient role",
        )

    return dependency


def maybe_rotate_signing_key(user: User) -> bool:
    """Rotate ``user``'s ``jwt_signing_key`` in memory if it is stale
    (``last_key_update`` older than the ~30-day rotation window, or unset),
    updating ``last_key_update``; return whether a rotation occurred.

    Does **not** persist — the caller persists via ``users.update`` (added in
    step 002). Rotation invalidates all of that user's prior tokens.
    """
    now = datetime.now(timezone.utc)
    last = user.last_key_update
    # Normalize a naive stored value to aware UTC so the comparison never raises.
    if last is not None and last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)

    if last is None or now - last >= KEY_ROTATION_WINDOW:
        user.jwt_signing_key = generate_signing_key()
        user.last_key_update = now
        return True
    return False


async def authenticate_user(username: str, password: str) -> User:
    """Full username/password login orchestration (decision 4 — no logic in the
    route). Returns the authenticated ``User`` on success; raises the generic
    ``AuthError`` on **any** refusal.

    Flow (see step file / ``context.md``): rate-limit gate
    (``rate_limit.is_locked`` → ``AuthError``, no lockout reveal); load via
    ``users.get_by_username`` and reject an unknown or disabled
    (``pwdhash is None``) user with a recorded failure; ``verify_password`` and
    reject a mismatch with a recorded failure; on success ``rate_limit.clear``,
    ``maybe_rotate_signing_key``, set ``last_login``, persist via
    ``users.update``, and return the ``User``. All refusals raise the identical
    ``AuthError`` (no enumeration).
    """
    # Rate-limit gate — refuse without revealing the lockout.
    if rate_limit.is_locked(username):
        raise AuthError

    user = await users.get_by_username(username)
    # Unknown user or disabled account (null pwdhash) → same generic refusal.
    if user is None or user.pwdhash is None:
        rate_limit.record_failure(username)
        raise AuthError

    if not verify_password(password, user.pwdhash):
        rate_limit.record_failure(username)
        raise AuthError

    # Success: reset the counter, rotate a stale key, stamp the login, persist.
    rate_limit.clear(username)
    maybe_rotate_signing_key(user)
    user.last_login = datetime.now(timezone.utc)
    return await users.update(user)


async def refresh_access_token(refresh_token: str) -> str:
    """Session-renewal orchestration (decision 4 — no logic in the route).
    Returns a **new access token** on success; raises the generic ``AuthError``
    on **any** refusal.

    Flow (see step file / ``context.md`` → "Token model"): read ``user_id`` via
    ``decode_token_unverified``, load the ``User``, verify the token against that
    user's key with ``verify_token_signature`` requiring ``type == "refresh"``,
    reject a disabled user (``pwdhash is None``), rotate + persist via
    ``maybe_rotate_signing_key`` / ``users.update`` **only if** the key is stale,
    then mint and return a new access token via ``create_access_token``. Any
    failure (malformed, bad/rotated signature, expired, wrong ``type``,
    unknown/disabled user) raises ``AuthError``.
    """
    # Stage 1: read the claimed user id without verifying the signature.
    try:
        user_id = decode_token_unverified(refresh_token)
    except (jwt.InvalidTokenError, ValueError, TypeError):
        raise AuthError

    # Stage 2: load the user; reject unknown, disabled, or keyless.
    user = await users.get_by_id(user_id)
    if user is None or user.pwdhash is None or user.jwt_signing_key is None:
        raise AuthError

    # Stage 3: verify signature + expiry against that user's own key.
    try:
        claims = verify_token_signature(refresh_token, user.jwt_signing_key)
    except jwt.InvalidTokenError:
        raise AuthError

    # Only a refresh token renews a session.
    if claims.get("type") != "refresh":
        raise AuthError

    # Rotate a stale key (invalidating the refresh token going forward) and
    # persist only when a rotation actually occurred.
    if maybe_rotate_signing_key(user):
        await users.update(user)

    return create_access_token(user)
