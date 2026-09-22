"""End-to-end tests for the chapter BODY route pair (feature 015, step 003).

Covers the body half of the step's Definition of done: DoD-1..DoD-7 and the body
half of DoD-13..DoD-17. The transition half of DoD-13..DoD-17 (and DoD-8..DoD-12)
lives in `tests/routes/test_chapter_states.py`.

Exercised in-process against the real `app.main.app` via the `http_client`
fixture (httpx `ASGITransport`, no live server, no network). Auth is REAL: each
test seeds its own user rows and mints real JWTs, so the whole request path --
`Depends(authz.book_access)` included -- runs. The `_now` / `_auth_header` /
`_seed_user` / `_seed_author` / `_create_book` / `_add_co_author` helpers are
copied per-file from `tests/routes/test_book_settings.py` rather than imported
(they are deliberately not shared fixtures). The `db` fixture is deliberately NOT
requested: it would repoint the process-global engine away from the one
`http_client`'s lifespan initialized.

Bound to the frozen skeleton (status.md -> Skeleton -> Step 003), two handlers on
014's existing router (prefix "/api/books"), each gated by
`Depends(authz.book_access)`:

    GET "/{book_id}/chapters/{chapter_id}/text" -> 200 ChapterTextResponse
    PUT "/{book_id}/chapters/{chapter_id}/text" -> 200 ChapterTextResponse
        (request body: UpdateChapterTextRequest -- text, expected_version)

    ChapterTextResponse -- chapter_id (str), state, text, version (int),
                           modified_at        (feature context.md -> wire contract)

Expected values come from the SPEC ONLY -- `003.chapter-write-routes.md`'s
Definition of done and Interface intent, `003.context.md`, and the feature
`context.md` (the "Status taxonomy" table, the wire contract, D1, D10, D11) --
never from implementation internals. The taxonomy this module pins:

    no token                                    -> 401 (the dependency's)
    private book, no relationship               -> 404 (existence hiding, the
                                                        dependency's, never re-derived)
    public book, logged-in non-member (reader)  -> 403 on the write, 200 on the read
    chapter of ANOTHER book                     -> 404 (the service's resolver)
    stale expected_version                      -> 409
    write to a chapter that is not `open`       -> 409
    co-author write in a `proposal`-mode book   -> 403, reason naming FEAT-010 (D11)
    any write on an `archived` book             -> 403 (D10); READS still work
    malformed body                              -> 422 (framework validation)

A chapter is put into a starting state (and given a starting body/version) by
writing it straight through `app.db.chapters`. These specs deliberately do NOT
call `POST .../open` first: a body test that depended on the transition path
would fail for the wrong reason when a transition breaks, and `closing` is
reachable no other way (feature context.md -> D8).

Async tests use asyncio_mode = "auto".
"""

import datetime

import pytest

from app.db import book_members, chapters as chapters_db, users
from app.db.engine import init_db, set_db_ready
from app.models.book_member import BookMember, MemberRole
from app.models.chapter import Chapter, ChapterState
from app.models.schemas.chapters import ChapterTextResponse
from app.models.user import User, UserRole
from app.services import auth

BASE = "/api/books"


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _seed_user(
    *,
    username: str,
    password: str = "password123",
    role: UserRole = UserRole.author,
) -> User:
    """Seed a persisted author on the app's engine and mark the instance ready."""
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


async def _seed_author(username: str) -> tuple[User, str]:
    """Seed an author caller and return (user, access token)."""
    user = await _seed_user(username=username, role=UserRole.author)
    return user, auth.create_access_token(user)


async def _create_book(
    http_client,
    token: str,
    *,
    title: str = "A Book",
    description: str = "a description",
    collaboration_mode: str = "free",
    visibility: str = "private",
) -> dict:
    """POST a book via the route as the token's caller; return the 201 body."""
    resp = await http_client.post(
        BASE,
        headers=_auth_header(token),
        json={
            "title": title,
            "description": description,
            "collaboration_mode": collaboration_mode,
            "visibility": visibility,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _add_co_author(book_id: int, user_id: int) -> None:
    """Insert a co-author BookMember row directly through the db layer."""
    await book_members.create(
        BookMember(
            book_id=book_id,
            user_id=user_id,
            role=MemberRole.co_author,
            created_at=_now(),
        )
    )


async def _archive_book(http_client, token: str, book_id) -> None:
    """Archive a book through the owner-only route (tests/routes/test_book_settings.py)."""
    resp = await http_client.post(
        f"{BASE}/{book_id}/archive", headers=_auth_header(token)
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["state"] == "archived"


# ---------------------------------------------------------------------------
# Chapter-family helpers.
# ---------------------------------------------------------------------------


def _text_url(book_id, chapter_id) -> str:
    """The body sub-resource path (003.context.md -> "Path shapes")."""
    return f"{BASE}/{book_id}/chapters/{chapter_id}/text"


async def _seed_chapter(
    book_id,
    *,
    ordinal: int = 1,
    title: str = "Seeded",
    sketch: str = "seeded sketch",
    state: ChapterState = ChapterState.planned,
    text: str = "",
    version: int = 1,
) -> Chapter:
    """A Chapter inserted straight through db/chapters.py, bypassing the routes.

    The state, the body and the version are written directly -- the transition
    routes are never used to reach a body-test precondition.
    """
    return await chapters_db.create(
        Chapter(
            book_id=int(book_id),
            ordinal=ordinal,
            title=title,
            state=state,
            sketch=sketch,
            text=text,
            version=version,
        )
    )


async def _get_body(http_client, token: str, book_id, chapter_id) -> dict:
    """GET the body sub-resource and return the validated 200 payload."""
    resp = await http_client.get(
        _text_url(book_id, chapter_id), headers=_auth_header(token)
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    ChapterTextResponse.model_validate(body)
    return body


async def _stored(chapter_id) -> Chapter:
    row = await chapters_db.get_by_id(int(chapter_id))
    assert row is not None
    return row


# ---------------------------------------------------------------------------
# DoD-1 — GET returns text / state / version / string id; archived still reads
# ---------------------------------------------------------------------------


# DoD-1: GET on the body path returns 200 with the chapter's text, state, version
# and its id as a STRING.
async def test_get_returns_text_state_version_and_string_id__DoD1(http_client):
    _owner, owner_token = await _seed_author("alice")
    book = await _create_book(http_client, owner_token)
    chapter = await _seed_chapter(
        book["id"],
        title="First Beat",
        state=ChapterState.open,
        text="The opening paragraph.",
        version=3,
    )

    resp = await http_client.get(
        _text_url(book["id"], chapter.id), headers=_auth_header(owner_token)
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    ChapterTextResponse.model_validate(body)

    assert body["chapter_id"] == str(chapter.id)
    assert isinstance(body["chapter_id"], str)
    assert body["text"] == "The opening paragraph."
    assert body["state"] == "open"
    assert body["version"] == 3


# DoD-1 (D10 -- archive refuses WRITES; reads still work): a book whose state is
# `archived` still serves its chapter body.
async def test_get_serves_body_on_archived_book__DoD1(http_client):
    _owner, owner_token = await _seed_author("bob")
    book = await _create_book(http_client, owner_token)
    chapter = await _seed_chapter(
        book["id"],
        state=ChapterState.closed,
        text="Preserved by the archive.",
        version=5,
    )
    await _archive_book(http_client, owner_token, book["id"])

    body = await _get_body(http_client, owner_token, book["id"], chapter.id)

    assert body["chapter_id"] == str(chapter.id)
    assert body["text"] == "Preserved by the archive."
    assert body["state"] == "closed"
    assert body["version"] == 5


# ---------------------------------------------------------------------------
# DoD-2 — a save with the current version lands and bumps the version by one
# ---------------------------------------------------------------------------


# DoD-2 (US-040.AC-1, UC-038): PUT with the current version returns 200 and the
# new body, and a following GET returns the same text with the version
# incremented by exactly one.
async def test_put_with_current_version_saves_and_bumps__DoD2_US040_AC1(http_client):
    _owner, owner_token = await _seed_author("carol")
    book = await _create_book(http_client, owner_token)
    chapter = await _seed_chapter(
        book["id"], state=ChapterState.open, text="before", version=2
    )

    before = await _get_body(http_client, owner_token, book["id"], chapter.id)
    current = before["version"]

    resp = await http_client.put(
        _text_url(book["id"], chapter.id),
        headers=_auth_header(owner_token),
        json={"text": "A whole new body.", "expected_version": current},
    )
    assert resp.status_code == 200, resp.text
    saved = resp.json()
    ChapterTextResponse.model_validate(saved)
    assert saved["text"] == "A whole new body."
    assert saved["version"] == current + 1

    after = await _get_body(http_client, owner_token, book["id"], chapter.id)
    assert after["text"] == "A whole new body."
    assert after["version"] == current + 1


# ---------------------------------------------------------------------------
# DoD-3 — a stale version is refused 409 and changes nothing
# ---------------------------------------------------------------------------


# DoD-3 (US-041.AC-1, UC-039): a PUT carrying a stale version returns 409 and a
# following GET shows the body unchanged.
async def test_put_with_stale_version_conflicts__DoD3_US041_AC1(http_client):
    _owner, owner_token = await _seed_author("dave")
    book = await _create_book(http_client, owner_token)
    chapter = await _seed_chapter(
        book["id"], state=ChapterState.open, text="original", version=1
    )

    stale = (await _get_body(http_client, owner_token, book["id"], chapter.id))[
        "version"
    ]

    first = await http_client.put(
        _text_url(book["id"], chapter.id),
        headers=_auth_header(owner_token),
        json={"text": "the landed body", "expected_version": stale},
    )
    assert first.status_code == 200, first.text
    landed_version = first.json()["version"]

    conflict = await http_client.put(
        _text_url(book["id"], chapter.id),
        headers=_auth_header(owner_token),
        json={"text": "a body that must not land", "expected_version": stale},
    )
    assert conflict.status_code == 409, conflict.text

    after = await _get_body(http_client, owner_token, book["id"], chapter.id)
    assert after["text"] == "the landed body"
    assert after["version"] == landed_version


# ---------------------------------------------------------------------------
# DoD-4 — re-issuing the merged body against the CURRENT version lands
# ---------------------------------------------------------------------------


# DoD-4 (US-041.AC-2, US-040.AC-4): after a 409, a PUT carrying a body with BOTH
# members' text and the CURRENT version returns 200, and that body is what a
# following GET returns. (context.md -> "Known product gaps": the guarantee is
# refuse-then-reconcile, not an automatic merge.)
async def test_reissued_merged_body_lands__DoD4_US041_AC2_US040_AC4(http_client):
    _owner, owner_token = await _seed_author("erin")
    co_author, co_token = await _seed_author("frank")
    book = await _create_book(http_client, owner_token)
    await _add_co_author(int(book["id"]), co_author.id)
    chapter = await _seed_chapter(
        book["id"], state=ChapterState.open, text="", version=1
    )

    base = (await _get_body(http_client, owner_token, book["id"], chapter.id))["version"]

    # The co-author saves first against the shared base version.
    co_save = await http_client.put(
        _text_url(book["id"], chapter.id),
        headers=_auth_header(co_token),
        json={"text": "B's paragraph.", "expected_version": base},
    )
    assert co_save.status_code == 200, co_save.text
    current = co_save.json()["version"]

    # The owner's save against the now-stale base is refused rather than
    # overwriting the co-author's text.
    refused = await http_client.put(
        _text_url(book["id"], chapter.id),
        headers=_auth_header(owner_token),
        json={"text": "A's paragraph.", "expected_version": base},
    )
    assert refused.status_code == 409, refused.text

    # The owner reconciles by composing BOTH members' text and re-issuing it
    # against the current version.
    merged = "B's paragraph.\n\nA's paragraph."
    reissued = await http_client.put(
        _text_url(book["id"], chapter.id),
        headers=_auth_header(owner_token),
        json={"text": merged, "expected_version": current},
    )
    assert reissued.status_code == 200, reissued.text
    ChapterTextResponse.model_validate(reissued.json())
    assert reissued.json()["text"] == merged

    after = await _get_body(http_client, owner_token, book["id"], chapter.id)
    assert after["text"] == merged
    assert "B's paragraph." in after["text"]
    assert "A's paragraph." in after["text"]


# ---------------------------------------------------------------------------
# DoD-5 — only an `open` chapter accepts a body write
# ---------------------------------------------------------------------------


# DoD-5 (US-040.AC-3, and the "no longer editable" half of US-038.AC-1): a PUT on
# a chapter that is `planned`, `closing` or `closed` returns 409 and the body is
# unchanged. A state-machine refusal, NOT 403 -- the caller holds the capability.
@pytest.mark.parametrize(
    "state",
    [
        pytest.param(ChapterState.planned, id="planned"),
        pytest.param(ChapterState.closing, id="closing"),
        pytest.param(ChapterState.closed, id="closed"),
    ],
)
async def test_put_refused_when_chapter_not_open__DoD5_US040_AC3_US038_AC1(
    http_client, state
):
    _owner, owner_token = await _seed_author("grace")
    book = await _create_book(http_client, owner_token)
    chapter = await _seed_chapter(
        book["id"], state=state, text="the untouched body", version=4
    )

    resp = await http_client.put(
        _text_url(book["id"], chapter.id),
        headers=_auth_header(owner_token),
        json={"text": "an edit that must not land", "expected_version": 4},
    )
    assert resp.status_code == 409, resp.text

    after = await _get_body(http_client, owner_token, book["id"], chapter.id)
    assert after["text"] == "the untouched body"
    assert after["version"] == 4
    assert (await _stored(chapter.id)).text == "the untouched body"


# ---------------------------------------------------------------------------
# DoD-6 — proposal mode refuses the CO-AUTHOR's body write, naming FEAT-010
# ---------------------------------------------------------------------------


# DoD-6 (D11): a co-author's PUT in a FREE-mode book returns 200.
async def test_co_author_put_lands_in_free_mode__DoD6(http_client):
    _owner, owner_token = await _seed_author("heidi")
    co_author, co_token = await _seed_author("ivan")
    book = await _create_book(http_client, owner_token, collaboration_mode="free")
    await _add_co_author(int(book["id"]), co_author.id)
    chapter = await _seed_chapter(
        book["id"], state=ChapterState.open, text="", version=1
    )

    resp = await http_client.put(
        _text_url(book["id"], chapter.id),
        headers=_auth_header(co_token),
        json={"text": "the co-author's block", "expected_version": 1},
    )
    assert resp.status_code == 200, resp.text
    ChapterTextResponse.model_validate(resp.json())
    assert resp.json()["text"] == "the co-author's block"

    after = await _get_body(http_client, owner_token, book["id"], chapter.id)
    assert after["text"] == "the co-author's block"


# DoD-6 (D11): the same call in a PROPOSAL-mode book returns 403 with a reason
# naming FEAT-010, while the OWNER's write is unaffected and returns 200. DoD-6
# fixes the STATUS and the PRESENCE of FEAT-010 in the refusal reason, and fixes
# nothing about the payload's JSON structure -- so the reason is read as the flat
# refusal detail this route family puts on the wire, and no assertion here pins
# that shape.
async def test_proposal_mode_refuses_co_author_naming_feat010__DoD6(http_client):
    _owner, owner_token = await _seed_author("judy")
    co_author, co_token = await _seed_author("kevin")
    book = await _create_book(http_client, owner_token, collaboration_mode="proposal")
    await _add_co_author(int(book["id"]), co_author.id)
    chapter = await _seed_chapter(
        book["id"], state=ChapterState.open, text="untouched", version=1
    )

    refused = await http_client.put(
        _text_url(book["id"], chapter.id),
        headers=_auth_header(co_token),
        json={"text": "a proposal that cannot be reviewed", "expected_version": 1},
    )
    assert refused.status_code == 403, refused.text
    assert "FEAT-010" in str(refused.json()["detail"])

    unchanged = await _get_body(http_client, owner_token, book["id"], chapter.id)
    assert unchanged["text"] == "untouched"

    owner_save = await http_client.put(
        _text_url(book["id"], chapter.id),
        headers=_auth_header(owner_token),
        json={"text": "the owner writes freely", "expected_version": 1},
    )
    assert owner_save.status_code == 200, owner_save.text
    assert owner_save.json()["text"] == "the owner writes freely"


# ---------------------------------------------------------------------------
# DoD-7 — an archived book refuses the body write (the body half)
# ---------------------------------------------------------------------------


# DoD-7 (D10): PUT returns 403 on a book whose state is `archived`. The
# transition half of this item is in tests/routes/test_chapter_states.py.
async def test_put_refused_on_archived_book__DoD7(http_client):
    _owner, owner_token = await _seed_author("laura")
    book = await _create_book(http_client, owner_token)
    chapter = await _seed_chapter(
        book["id"], state=ChapterState.open, text="preserved", version=1
    )
    await _archive_book(http_client, owner_token, book["id"])

    resp = await http_client.put(
        _text_url(book["id"], chapter.id),
        headers=_auth_header(owner_token),
        json={"text": "a write into an archive", "expected_version": 1},
    )
    assert resp.status_code == 403, resp.text

    # Reads still work, and the body is untouched.
    after = await _get_body(http_client, owner_token, book["id"], chapter.id)
    assert after["text"] == "preserved"
    assert after["version"] == 1


# ---------------------------------------------------------------------------
# DoD-13 — a logged-in non-member of a PUBLIC book: 403 on write, 200 on read
# ---------------------------------------------------------------------------


# DoD-13: a logged-in non-member of a PUBLIC book resolves to the `reader` role,
# reaches the service and is refused 403 on the body PUT -- while the body GET
# answers 200. (The transition half is in test_chapter_states.py.)
async def test_public_book_non_member_reads_but_cannot_write__DoD13(http_client):
    _owner, owner_token = await _seed_author("mike")
    _stranger, stranger_token = await _seed_author("nina")
    book = await _create_book(http_client, owner_token, visibility="public")
    chapter = await _seed_chapter(
        book["id"], state=ChapterState.open, text="readable body", version=1
    )

    read = await http_client.get(
        _text_url(book["id"], chapter.id), headers=_auth_header(stranger_token)
    )
    assert read.status_code == 200, read.text
    ChapterTextResponse.model_validate(read.json())
    assert read.json()["text"] == "readable body"

    write = await http_client.put(
        _text_url(book["id"], chapter.id),
        headers=_auth_header(stranger_token),
        json={"text": "a reader must not write", "expected_version": 1},
    )
    assert write.status_code == 403, write.text
    assert (await _stored(chapter.id)).text == "readable body"


# ---------------------------------------------------------------------------
# DoD-14 — a PRIVATE book hides its existence from a stranger (404)
# ---------------------------------------------------------------------------


# DoD-14: a user with no relationship to a PRIVATE book gets 404 from both body
# routes -- existence hiding inherited from the dependency, never re-derived.
@pytest.mark.parametrize("method", [pytest.param("GET", id="get"), pytest.param("PUT", id="put")])
async def test_private_book_stranger_gets_404__DoD14(http_client, method):
    _owner, owner_token = await _seed_author("oscar")
    _stranger, stranger_token = await _seed_author("paula")
    book = await _create_book(http_client, owner_token, visibility="private")
    chapter = await _seed_chapter(
        book["id"], state=ChapterState.open, text="hidden", version=1
    )

    payload = (
        {"text": "no", "expected_version": 1} if method == "PUT" else None
    )
    resp = await http_client.request(
        method,
        _text_url(book["id"], chapter.id),
        headers=_auth_header(stranger_token),
        json=payload,
    )
    assert resp.status_code == 404, resp.text


# ---------------------------------------------------------------------------
# DoD-15 — no token at all is 401
# ---------------------------------------------------------------------------


# DoD-15: a request with no token gets 401 from both body routes.
@pytest.mark.parametrize("method", [pytest.param("GET", id="get"), pytest.param("PUT", id="put")])
async def test_no_token_gets_401__DoD15(http_client, method):
    _owner, owner_token = await _seed_author("quinn")
    book = await _create_book(http_client, owner_token, visibility="public")
    chapter = await _seed_chapter(
        book["id"], state=ChapterState.open, text="anything", version=1
    )

    payload = (
        {"text": "no", "expected_version": 1} if method == "PUT" else None
    )
    resp = await http_client.request(
        method, _text_url(book["id"], chapter.id), json=payload
    )
    assert resp.status_code == 401, resp.text


# ---------------------------------------------------------------------------
# DoD-16 — a chapter of ANOTHER book is 404, not 403 and not 200
# ---------------------------------------------------------------------------


# DoD-16: addressing a chapter id that belongs to ANOTHER book returns 404 --
# not 403, not 200 -- on both body routes. The caller is a member (owner) of BOTH
# books and both are ACTIVE, so the 404 is provably the book-scoping check and
# not an authorization or archive failure.
@pytest.mark.parametrize("method", [pytest.param("GET", id="get"), pytest.param("PUT", id="put")])
async def test_foreign_book_chapter_is_404__DoD16(http_client, method):
    _owner, owner_token = await _seed_author("rosa")
    book_a = await _create_book(http_client, owner_token, title="Book A")
    book_b = await _create_book(http_client, owner_token, title="Book B")
    foreign = await _seed_chapter(
        book_b["id"], state=ChapterState.open, text="belongs to B", version=1
    )

    payload = (
        {"text": "no", "expected_version": 1} if method == "PUT" else None
    )
    resp = await http_client.request(
        method,
        _text_url(book_a["id"], foreign.id),
        headers=_auth_header(owner_token),
        json=payload,
    )
    assert resp.status_code == 404, resp.text

    # The foreign chapter is untouched.
    assert (await _stored(foreign.id)).text == "belongs to B"


# ---------------------------------------------------------------------------
# DoD-17 — a malformed body is 422 and stores nothing (the body half)
# ---------------------------------------------------------------------------


# DoD-17: a malformed body on the body PUT (missing text, missing version, wrong
# type) returns 422 and nothing is stored. The "transitions accept no body at
# all" half is in tests/routes/test_chapter_states.py.
@pytest.mark.parametrize(
    "payload",
    [
        pytest.param({"expected_version": 1}, id="missing_text"),
        pytest.param({"text": "a body"}, id="missing_expected_version"),
        pytest.param(
            {"text": "a body", "expected_version": "not-a-number"},
            id="wrong_type_version",
        ),
        pytest.param(
            {"text": ["not", "a", "string"], "expected_version": 1},
            id="wrong_type_text",
        ),
    ],
)
async def test_malformed_body_is_422_and_stores_nothing__DoD17(http_client, payload):
    _owner, owner_token = await _seed_author("sam")
    book = await _create_book(http_client, owner_token)
    chapter = await _seed_chapter(
        book["id"], state=ChapterState.open, text="the stored body", version=1
    )

    resp = await http_client.put(
        _text_url(book["id"], chapter.id),
        headers=_auth_header(owner_token),
        json=payload,
    )
    assert resp.status_code == 422, resp.text

    after = await _get_body(http_client, owner_token, book["id"], chapter.id)
    assert after["text"] == "the stored body"
    assert after["version"] == 1
