"""The seed remediation's HTTP surface — `POST /api/admin/db/tables/{name}/seed`.

Feedback round 1, item **F1**. Reproduces: no admin endpoint exists that reseeds
the five assistant modes, so an instance bootstrapped before the seed call landed
has no operator-reachable path back — and the consistency report never says so.

Bound to the frozen signatures (status.md -> `## Skeleton` -> "Feedback round 1,
item F1 — re-freeze"):

    @router.post("/tables/{name}/seed", status_code=status.HTTP_204_NO_CONTENT)
    async def seed_table_rows(name: str,
                              caller: User = Depends(auth_service.require_role(UserRole.admin))) -> None
    _DB_ADMIN_ERROR_STATUS: ... not_seedable -> 400   (unknown_table -> 404 already)
    TableReportEntry.status: "ok" | "drift" | "missing" | "seed-missing"
    TableReportEntry.missing_seed_keys: list[str]

Exercised in-process against the real `app.main.app` via the `http_client`
fixture (httpx `ASGITransport`, no live server, no network), seeding its own
users on the process-global engine exactly as `tests/routes/admin/test_db.py`
does. That module is NOT edited by this round.

THE AIR GAP — no source is read. Every expected value comes from feedback.md ->
F1:

  - point 5: the new route sits in the existing `/tables/{name}/…` family, is
    admin-gated like every sibling, takes no request body and returns
    **204 No Content** with no response DTO (decision D-d);
  - point 6: a name not in the schema metadata is the existing `unknown_table`
    -> **404**; a real table with no registry entry is the new `not_seedable`
    -> **400**;
  - point 7: after pressing Seed the `assistant_modes` row reads `ok` — the
    reloaded report is the admin's confirmation.

Async tests use asyncio_mode = "auto".
"""

import datetime as _dt

import pytest

from app.db import users
from app.db.engine import init_db, set_db_ready
from app.models.user import User, UserRole
from app.services import auth

BASE = "/api/admin/db"
REPORT_URL = f"{BASE}/report"
MODES_TABLE = "assistant_modes"

# The fixed five (feedback.md F1 point 1 -> the members of DEFAULT_MODE_KEYS).
FIXED_FIVE_KEYS = {
    "edit-character",
    "edit-location",
    "edit-fact",
    "write-chapter",
    "close-chapter",
}


def _now() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc)


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _seed_url(name: str) -> str:
    return f"{BASE}/tables/{name}/seed"


async def _seed_user(
    *,
    username: str,
    role: UserRole = UserRole.admin,
    password: str = "password123",
) -> User:
    """Seed a persisted user on the app's engine and mark the instance configured."""
    await init_db()
    user = await users.create(
        User(
            username=username,
            role=role,
            pwdhash=auth.hash_password(password),
            jwt_signing_key=auth.generate_signing_key(),
            last_key_update=_now(),
        )
    )
    set_db_ready(True)
    return user


async def _seed_admin(username: str = "root") -> tuple[User, str]:
    """Seed an admin caller and return (user, access token)."""
    admin = await _seed_user(username=username, role=UserRole.admin)
    return admin, auth.create_access_token(admin)


def _entry_for(report_body: dict, name: str) -> dict:
    return next(e for e in report_body["tables"] if e["name"] == name)


# F1 points 1 + 5 + 7 — the whole operator loop over HTTP: the report tells the
# admin the modes are unseeded (and which keys), the seed action answers 204 with
# no body, and the reloaded report reads `ok` with nothing outstanding.
async def test_seed_endpoint_flips_the_row_to_ok__F1(http_client):
    _admin, token = await _seed_admin()
    headers = _auth_header(token)

    before = await http_client.get(REPORT_URL, headers=headers)
    assert before.status_code == 200, before.text
    entry = _entry_for(before.json(), MODES_TABLE)
    assert entry["status"] == "seed-missing"
    assert set(entry["missing_seed_keys"]) == FIXED_FIVE_KEYS

    seeded = await http_client.post(_seed_url(MODES_TABLE), headers=headers)
    assert seeded.status_code == 204, seeded.text
    assert seeded.content == b""  # 204: no body, no response DTO (D-d)

    after = await http_client.get(REPORT_URL, headers=headers)
    assert after.status_code == 200
    entry_after = _entry_for(after.json(), MODES_TABLE)
    assert entry_after["status"] == "ok"
    assert entry_after["missing_seed_keys"] == []


# F1 point 6 — refusals map to the family's existing vocabulary: a name not in
# the schema metadata is `unknown_table` -> 404; a real table with no registry
# entry is `not_seedable` -> 400.
@pytest.mark.parametrize(
    "name,expected_status",
    [("definitely_not_a_table", 404), ("users", 400)],
)
async def test_seed_endpoint_refusals__F1(http_client, name: str, expected_status: int):
    _admin, token = await _seed_admin()

    resp = await http_client.post(_seed_url(name), headers=_auth_header(token))

    assert resp.status_code == expected_status, resp.text


# F1 point 5 — the route is admin-gated exactly like its siblings: an author-role
# token is refused 403 by the per-endpoint guard, and nothing is seeded.
async def test_seed_endpoint_is_admin_gated__F1(http_client):
    _admin, _token = await _seed_admin()
    author = await _seed_user(username="scribe", role=UserRole.author)
    headers = _auth_header(auth.create_access_token(author))

    resp = await http_client.post(_seed_url(MODES_TABLE), headers=headers)

    assert resp.status_code == 403
