"""Tests for the auth primitives retained after feature 004, step 001.

Feature 004 step 001 SPLIT feature-003's single `create_token(user)` into
`create_access_token` / `create_refresh_token` and REMOVED `create_token`. The
prior `create_token` decode test (feature-003 DoD-2) is therefore RETIRED here;
the split's minting + claim contract is covered by `test_tokens.py`
(004 DoD-1..DoD-5). This file keeps only the primitives that step 001 leaves
intact.

Bound to the frozen skeleton signatures (status.md -> Skeleton) in
`app.services.auth`:
    def hash_password(password: str) -> str
    def verify_password(password: str, pwdhash: str) -> bool
    def generate_signing_key() -> str

Expected values come from the feature-003 primitive spec (unchanged by 004):
    - hash_password then verify_password returns True for the correct password
      and False for a wrong one,
    - generate_signing_key returns a non-empty secret string and yields a fresh
      (distinct) value on each call — per-user HS256 key material.

These are pure primitives, so no DB fixture is needed.
"""

from app.services import auth


# Feature-003 primitive (unchanged by 004): hash_password then verify_password
# returns True for the correct password and False for a wrong one.
def test_hash_then_verify_password():
    password = "correct horse battery staple"
    pwdhash = auth.hash_password(password)

    # The correct password verifies against its own hash...
    assert auth.verify_password(password, pwdhash) is True
    # ...and a wrong password does not.
    assert auth.verify_password("wrong password", pwdhash) is False


# Feature-003 primitive (retained after create_token's removal took its only
# in-test caller): generate_signing_key returns a non-empty string and produces a
# distinct value per call (fresh per-user key material).
def test_generate_signing_key_nonempty_and_unique():
    key1 = auth.generate_signing_key()
    key2 = auth.generate_signing_key()

    assert isinstance(key1, str)
    assert key1 != ""
    assert key1 != key2
