"""The wire contract for timestamps: every JSON stamp carries an explicit UTC designator.

Services always write ``datetime.now(timezone.utc)``, but the SQLite columns are
declared without ``timezone=True``, so a value **read back from the database**
returns tz-naive. Before ``app.models.schemas.common.UtcDateTime`` that naive
value serialized as ``"2026-09-14T15:04:00"`` — no ``Z``, no offset — and
JavaScript parses a tz-less ISO string as LOCAL time, silently shifting every
rendered instant by the viewer's offset.

**The second request is the whole point of these tests.** A value returned in the
same request that created it is still aware in memory and would serialize with a
timezone regardless, so asserting only on a POST response proves nothing.

Exercised in-process against the real ``app.main.app`` via the ``http_client``
fixture, seeding on the process-global engine the way tests/routes/test_books.py
does.
"""

import datetime

from app.db import users
from app.db.engine import init_db, set_db_ready
from app.models.user import User, UserRole
from app.services import auth

BOOKS_URL = "/api/books"
USERS_URL = "/api/admin/users"
LOGIN_URL = "/api/auth/login"
PASSWORD = "password123"


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _seed_user(username: str, role: UserRole) -> User:
    """Seed a persisted user on the app's engine and mark the instance ready."""
    await init_db()
    user = await users.create(
        User(
            username=username,
            role=role,
            pwdhash=auth.hash_password(PASSWORD),
            jwt_signing_key=auth.generate_signing_key(),
            last_key_update=datetime.datetime.now(datetime.timezone.utc),
        )
    )
    set_db_ready(True)
    return user


def _assert_utc(value: str | None, *, field: str) -> None:
    """A serialized timestamp must name its timezone, and that timezone is UTC."""
    assert value is not None, f"{field} unexpectedly null"
    assert value.endswith("Z"), f"{field} carries no UTC designator: {value!r}"
    # Round-trips as an aware instant — the frontend's `new Date(...)` equivalent.
    parsed = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    assert parsed.utcoffset() == datetime.timedelta(0)


async def test_book_timestamps_read_from_db_serialize_as_utc(http_client):
    """A book listed in a LATER request — value out of SQLite, hence naive — still ends in Z."""
    author = await _seed_user("author-tz", UserRole.author)
    token = auth.create_access_token(author)

    created = await http_client.post(
        BOOKS_URL,
        headers=_auth_header(token),
        json={
            "title": "A Book",
            "description": "a description",
            "collaboration_mode": "free",
            "visibility": "private",
        },
    )
    assert created.status_code == 201, created.text

    listed = await http_client.get(BOOKS_URL, headers=_auth_header(token))
    assert listed.status_code == 200, listed.text
    (book,) = listed.json()["items"]

    _assert_utc(book["created_at"], field="created_at")
    _assert_utc(book["modified_at"], field="modified_at")


async def test_last_login_serializes_as_utc(http_client):
    """`last_login` is stamped by the login route and read back by the admin list."""
    await _seed_user("admin-tz", UserRole.admin)

    logged_in = await http_client.post(
        LOGIN_URL, json={"username": "admin-tz", "password": PASSWORD}
    )
    assert logged_in.status_code == 200, logged_in.text
    token = logged_in.json()["access_token"]

    listed = await http_client.get(USERS_URL, headers=_auth_header(token))
    assert listed.status_code == 200, listed.text
    (user,) = [u for u in listed.json() if u["username"] == "admin-tz"]

    _assert_utc(user["last_login"], field="last_login")
