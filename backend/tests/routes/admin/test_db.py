"""End-to-end tests for the admin DB-management HTTP surface (feature 007, step 005).

Exercised in-process against the real `app.main.app` via the `http_client`
fixture (httpx `ASGITransport`, no live server, no network). The app's startup
lifespan runs against a throwaway temp DB but does NOT build the schema, so each
test seeds its own users on the same process-global engine (schema built with
`init_db`, readiness flipped with `set_db_ready(True)`) mirroring
tests/routes/admin/test_llm_servers.py's `_seed_user` / `_seed_admin` helpers.
The autouse `_reset_db_ready` fixture (conftest) restores the cold-boot readiness
default before each test.

Bound to the frozen skeleton (status.md -> Skeleton -> "Step 005 — frozen
interface"): the `app.routes.admin.db` router, prefix "/api/admin/db", every
endpoint gated by `Depends(auth_service.require_role(UserRole.admin))`, static
paths declared before `/tables/{name}/...` param paths:

    GET  /api/admin/db/report              -> 200, ConsistencyReport
                                              {tables:[{name,status,
                                               missing_columns,extra_columns}]}
    GET  /api/admin/db/export              -> 200, application/zip download
                                              (Content-Disposition: attachment)
    POST /api/admin/db/import              -> 204 (multipart `file`);
                                              invalid_archive -> 400
    POST /api/admin/db/vector/rebuild      -> 200, {indexed_rows:int};
                                              no_embedding_provider -> 400
    POST /api/admin/db/tables/{name}/create -> 204;
                                              not_in_metadata/table_not_missing -> 400
    POST /api/admin/db/tables/{name}/sync   -> 204; unknown_table -> 404

Non-admin -> 403 from the per-endpoint guard.

THE AIR GAP — this module never reads route handler bodies or any source. Every
expected value comes from the SPEC ONLY: the step DoD (DoD-1..DoD-9), the step
Interface intent, and decisions D5 (admin gating + error->status map) / D7 from
context.md, plus the cited US-###.AC-# acceptance criteria. The vector-rebuild
endpoint is isolated from the real on-disk LanceDB dir by monkeypatching the
service seams `app.db.llm_servers.get_embedding_server` (returns a designated
embedding server) and `app.db.vector.rebuild_index` (no-op returning 0), so no
network and no on-disk vector store is touched.

Async tests use asyncio_mode = "auto".
"""

import datetime as _dt
import io
import zipfile

import app.db.engine as engine_module
from app.db import users
from app.db.engine import init_db, set_db_ready
from app.models.llm_server import LlmServer
from app.models.user import User, UserRole
from app.services import auth

BASE = "/api/admin/db"
REPORT_URL = f"{BASE}/report"
EXPORT_URL = f"{BASE}/export"
IMPORT_URL = f"{BASE}/import"
REBUILD_URL = f"{BASE}/vector/rebuild"


def _now() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc)


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_url(name: str) -> str:
    return f"{BASE}/tables/{name}/create"


def _sync_url(name: str) -> str:
    return f"{BASE}/tables/{name}/sync"


async def _seed_user(
    *,
    username: str,
    role: UserRole = UserRole.admin,
    password: str = "password123",
) -> User:
    """Seed a persisted user on the app's engine and mark the instance configured.

    Builds the schema (`init_db`, idempotent) on the process-global engine, then
    creates the user with a real bcrypt pwdhash and a per-user signing key, then
    flips readiness True. Returns the created `User` so the caller can mint a token.
    """
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


async def _exec_ddl(sql: str) -> None:
    """Run a raw DDL statement against the app's process-global engine."""
    async with engine_module._engine.begin() as conn:
        await conn.run_sync(lambda c: c.exec_driver_sql(sql))


async def _fake_embedding_server() -> LlmServer:
    """A designated embedding server with `embedding_model` set (rebuild passes the check)."""
    return LlmServer(
        name="emb",
        backend_type="openai",
        base_url="http://x",
        is_embedding=True,
        embedding_model="text-embedding-3-small",
    )


async def _fake_rebuild_index() -> int:
    """Stand-in for `db.vector.rebuild_index`: a no-op reset that indexes 0 rows."""
    return 0


def _entry_for(report_body: dict, name: str) -> dict:
    return next(e for e in report_body["tables"] if e["name"] == name)


# DoD-1 (US-015.AC-1/AC-2): GET /api/admin/db/report with an admin token returns
# 200 and a per-table report; after seeding drift on `users` (an extra column not
# in metadata), that table's entry is `status == "drift"` and the added column is
# reported in `extra_columns`.
async def test_report_returns_drift__DoD1_US015(http_client):
    _admin, token = await _seed_admin()
    await _exec_ddl("ALTER TABLE users ADD COLUMN drift_probe TEXT")

    resp = await http_client.get(REPORT_URL, headers=_auth_header(token))
    assert resp.status_code == 200, resp.text

    body = resp.json()
    entry = _entry_for(body, "users")
    assert entry["status"] == "drift"
    assert "drift_probe" in entry["extra_columns"]


# DoD-2 (US-016.AC-1): POST /api/admin/db/tables/{name}/create on a currently-
# missing registered table returns 204 and a subsequent GET /report shows it `ok`;
# a name not in metadata returns 400 (not_in_metadata -> 400, D5).
async def test_create_missing_table_then_ok__DoD2_US016(http_client):
    _admin, token = await _seed_admin()
    headers = _auth_header(token)
    await _exec_ddl("DROP TABLE llm_servers")

    created = await http_client.post(_create_url("llm_servers"), headers=headers)
    assert created.status_code == 204, created.text

    report = await http_client.get(REPORT_URL, headers=headers)
    assert report.status_code == 200
    entry = _entry_for(report.json(), "llm_servers")
    assert entry["status"] == "ok"

    bogus = await http_client.post(
        _create_url("definitely_not_a_table"), headers=headers
    )
    assert bogus.status_code == 400


# DoD-3 (US-017.AC-1/AC-2): POST /api/admin/db/tables/{name}/sync on a drifted
# table returns 204 and a subsequent GET /report shows it `ok`.
async def test_sync_drifted_table_then_ok__DoD3_US017(http_client):
    _admin, token = await _seed_admin()
    headers = _auth_header(token)
    await _exec_ddl("ALTER TABLE users ADD COLUMN drift_probe TEXT")

    synced = await http_client.post(_sync_url("users"), headers=headers)
    assert synced.status_code == 204, synced.text

    report = await http_client.get(REPORT_URL, headers=headers)
    assert report.status_code == 200
    entry = _entry_for(report.json(), "users")
    assert entry["status"] == "ok"


# DoD-4 (US-018.AC-1): GET /api/admin/db/export returns 200, an application/zip
# media type, a `Content-Disposition: attachment` header, and non-empty bytes that
# open as a valid ZIP.
async def test_export_downloadable_zip__DoD4_US018(http_client):
    _admin, token = await _seed_admin()

    resp = await http_client.get(EXPORT_URL, headers=_auth_header(token))
    assert resp.status_code == 200, resp.text
    assert "application/zip" in resp.headers["content-type"]
    assert "attachment" in resp.headers["content-disposition"]
    assert resp.content  # non-empty
    zipfile.ZipFile(io.BytesIO(resp.content))  # opens as a valid ZIP


# DoD-5 (US-019.AC-1): POST /api/admin/db/import with a valid multipart `file`
# export returns 204 and its data is present afterward (seeded "alice" restored).
async def test_import_restores_data__DoD5_US019(http_client):
    _admin, token = await _seed_admin()
    await _seed_user(username="alice", role=UserRole.author)
    headers = _auth_header(token)

    exported = await http_client.get(EXPORT_URL, headers=headers)
    assert exported.status_code == 200

    imported = await http_client.post(
        IMPORT_URL,
        headers=headers,
        files={"file": ("export.zip", exported.content, "application/zip")},
    )
    assert imported.status_code == 204, imported.text

    assert await users.get_by_username("alice") is not None


# DoD-6 (US-019.AC-2): importing the same export twice via the endpoint produces
# no duplicate rows (idempotent UPSERT — the single seeded user stays a single row).
async def test_import_is_idempotent__DoD6_US019(http_client):
    _admin, token = await _seed_admin()
    headers = _auth_header(token)

    exported = await http_client.get(EXPORT_URL, headers=headers)
    assert exported.status_code == 200
    archive = exported.content

    for _ in range(2):
        imported = await http_client.post(
            IMPORT_URL,
            headers=headers,
            files={"file": ("export.zip", archive, "application/zip")},
        )
        assert imported.status_code == 204, imported.text

    assert len(await users.get_all()) == 1


# DoD-7 (US-019.AC-3): POST /api/admin/db/import with corrupt (non-zip) `file`
# bytes returns 400 (invalid_archive -> 400, D5) and leaves the DB unchanged.
async def test_import_corrupt_archive_rejected__DoD7_US019(http_client):
    _admin, token = await _seed_admin()
    headers = _auth_header(token)

    before = len(await users.get_all())

    imported = await http_client.post(
        IMPORT_URL,
        headers=headers,
        files={"file": ("broken", b"not a zip archive", "application/octet-stream")},
    )
    assert imported.status_code == 400

    after = len(await users.get_all())
    assert after == before


# DoD-8 (US-020.AC-1): POST /api/admin/db/vector/rebuild with a valid embedding
# designation returns 200 and the count wrapper {indexed_rows: 0} (Stage-1 empty
# source registry). The embedding-server resolution and the rebuild are
# monkeypatched so no on-disk LanceDB store is touched.
async def test_vector_rebuild_returns_indexed_rows__DoD8_US020(http_client, monkeypatch):
    _admin, token = await _seed_admin()
    monkeypatch.setattr(
        "app.db.llm_servers.get_embedding_server", _fake_embedding_server
    )
    monkeypatch.setattr("app.db.vector.rebuild_index", _fake_rebuild_index)

    resp = await http_client.post(REBUILD_URL, headers=_auth_header(token))
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"indexed_rows": 0}


# DoD-9 (D5/D7 gating): each of the six endpoints with an author-role token is
# refused 403 by the per-endpoint admin guard (ladder author < admin). A valid
# `file` field is supplied on the import call so the ONLY failure is the guard.
async def test_gating_author_forbidden_all_endpoints__DoD9(http_client):
    _admin, _token = await _seed_admin()
    author = await _seed_user(username="scribe", role=UserRole.author)
    headers = _auth_header(auth.create_access_token(author))

    report = await http_client.get(REPORT_URL, headers=headers)
    assert report.status_code == 403

    export = await http_client.get(EXPORT_URL, headers=headers)
    assert export.status_code == 403

    imported = await http_client.post(
        IMPORT_URL,
        headers=headers,
        files={"file": ("export.zip", b"PK\x03\x04", "application/zip")},
    )
    assert imported.status_code == 403

    rebuild = await http_client.post(REBUILD_URL, headers=headers)
    assert rebuild.status_code == 403

    create = await http_client.post(_create_url("users"), headers=headers)
    assert create.status_code == 403

    sync = await http_client.post(_sync_url("users"), headers=headers)
    assert sync.status_code == 403


# DoD-9 (D5/D7 gating): each of the six endpoints with an admin-role token returns
# its documented success status, with each call set up to genuinely succeed:
# report 200, export 200, import 204 (valid archive), sync 204 (existing table),
# create 204 (dropped -> missing table), vector/rebuild 200 (monkeypatched).
async def test_gating_admin_success_all_endpoints__DoD9(http_client, monkeypatch):
    _admin, token = await _seed_admin()
    headers = _auth_header(token)

    report = await http_client.get(REPORT_URL, headers=headers)
    assert report.status_code == 200

    export = await http_client.get(EXPORT_URL, headers=headers)
    assert export.status_code == 200

    imported = await http_client.post(
        IMPORT_URL,
        headers=headers,
        files={"file": ("export.zip", export.content, "application/zip")},
    )
    assert imported.status_code == 204

    sync = await http_client.post(_sync_url("users"), headers=headers)
    assert sync.status_code == 204

    await _exec_ddl("DROP TABLE llm_servers")
    create = await http_client.post(_create_url("llm_servers"), headers=headers)
    assert create.status_code == 204

    monkeypatch.setattr(
        "app.db.llm_servers.get_embedding_server", _fake_embedding_server
    )
    monkeypatch.setattr("app.db.vector.rebuild_index", _fake_rebuild_index)
    rebuild = await http_client.post(REBUILD_URL, headers=headers)
    assert rebuild.status_code == 200
    assert rebuild.json() == {"indexed_rows": 0}
