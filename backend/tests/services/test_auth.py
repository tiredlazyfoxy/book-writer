"""Tests for the minimal auth primitives (feature 003, step 001).

Bound to the frozen skeleton signatures (status.md -> Skeleton -> Step 001):
    class UserRole(str, enum.Enum)  {admin="admin", author="author"}  in app.models.user
    class User(SQLModel, table=True) with id, username, role,
        jwt_signing_key, ...                                          in app.models.user
    def hash_password(password: str) -> str                          in app.services.auth
    def verify_password(password: str, pwdhash: str) -> bool          in app.services.auth
    def generate_signing_key() -> str                                in app.services.auth
    def create_token(user: User) -> str                              in app.services.auth

Expected values come from the step spec (001.user-model-auth-primitives.md DoD +
context) and the feature-wide auth scheme, never from implementation internals:
    - hash_password then verify_password returns True for the correct password
      and False for a wrong one (DoD-1),
    - create_token(user) mints a per-user HS256 JWT signed with THAT user's own
      jwt_signing_key, whose payload carries that user's user_id and role (DoD-2).

These are pure (non-DB) primitives, so no `db` fixture is needed. The JWT is
decoded here with PyJWT (HS256, per the feature auth scheme) using the user's own
signing key — the spec's stated way to read the token back.
"""

import jwt

from app.services import auth
from app.models.user import User, UserRole


# DoD-1: hash_password then verify_password returns True for the correct
# password and False for a wrong one.
def test_hash_then_verify_password__DoD1():
    password = "correct horse battery staple"
    pwdhash = auth.hash_password(password)

    # The correct password verifies against its own hash...
    assert auth.verify_password(password, pwdhash) is True
    # ...and a wrong password does not.
    assert auth.verify_password("wrong password", pwdhash) is False


# DoD-2: create_token(user) produces a JWT that decodes with the user's own
# jwt_signing_key to a payload carrying that user's user_id and role.
def test_create_token_decodes_with_user_key_to_user_claims__DoD2():
    signing_key = auth.generate_signing_key()
    user = User(
        id=42,
        username="alice",
        role=UserRole.admin,
        jwt_signing_key=signing_key,
    )

    token = auth.create_token(user)

    # The token decodes with THAT user's own signing key (per-user HS256), per
    # the feature auth scheme.
    payload = jwt.decode(token, user.jwt_signing_key, algorithms=["HS256"])

    # The payload carries that user's user_id and role.
    assert payload["user_id"] == user.id
    assert payload["role"] == user.role.value
