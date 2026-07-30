"""End-to-end tests for the chapter STATE-TRANSITION routes (feature 015, step 003).

Covers DoD-8..DoD-12 plus the transition half of DoD-7 and DoD-13..DoD-17. The
body half of DoD-1..DoD-7 and DoD-13..DoD-17 lives in
`tests/routes/test_chapter_text.py`.

Exercised in-process against the real `app.main.app` via the `http_client`
fixture (httpx `ASGITransport`, no live server, no network). Auth is REAL: each
test seeds its own user rows and mints real JWTs, so the whole request path --
`Depends(authz.book_access)` included -- runs. The `_now` / `_auth_header` /
`_seed_user` / `_seed_author` / `_create_book` / `_add_co_author` helpers are
copied per-file from `tests/routes/test_book_settings.py` rather than imported
(they are deliberately not shared fixtures). The `db` fixture is deliberately NOT
requested: it would repoint the process-global engine away from the one
`http_client`'s lifespan initialized.

Bound to the frozen skeleton (status.md -> Skeleton -> Step 003), three handlers
on 014's existing router (prefix "/api/books"), each gated by
`Depends(authz.book_access)` and each taking NO request body:

    POST "/{book_id}/chapters/{chapter_id}/open"   -> 200 ChapterResponse
    POST "/{book_id}/chapters/{chapter_id}/close"  -> 200 ChapterResponse
    POST "/{book_id}/chapters/{chapter_id}/reopen" -> 200 ChapterResponse

Expected values come from the SPEC ONLY -- `003.chapter-write-routes.md`'s
Definition of done and Interface intent, `003.context.md`, and the feature
`context.md` (the "Status taxonomy" table, D8, D10, "The close seam") -- never
from implementation internals. The taxonomy this module pins:

    no token                                    -> 401 (the dependency's)
    private book, no relationship               -> 404 (existence hiding, the
                                                        dependency's, never re-derived)
    public book, logged-in non-member (reader)  -> 403
    co-author on any transition                 -> 403 (transitions are owner-only)
    chapter of ANOTHER book                     -> 404 (the service's resolver)
    open a chapter that is not `planned`, close
      one that is not `open`, reopen one that is
      not `closed`, or open/reopen while another
      chapter is `open` or `closing`            -> 409 (state-machine, NOT 403)
    any transition on an `archived` book        -> 403 (D10)

A close writes `closed` DIRECTLY (D8, "The close seam"); the ONLY use of
`closing` here is as a SEEDED slot holder, written straight through
`app.db.chapters`, which is the only producer of that state in this feature.
US-038.AC-3 (the close gate) is `016`'s and is cited nowhere.

Async tests use asyncio_mode = "auto".
"""

import datetime

import pytest

from app.db import book_members, chapters as chapters_db, users
from app.db.engine import init_db, set_db_ready
from app.models.book_member import BookMember, MemberRole
from app.models.chapter import Chapter, ChapterState
from app.models.schemas.chapters import ChapterResponse
from app.models.user import User, UserRole
from app.services import auth

BASE = "/api/books"

# The precondition state each transition acts on (003.chapter-write-routes.md ->
# DoD-8 / DoD-10 / DoD-11). Used wherever a spec must exercise a refusal that is
# NOT a state-machine refusal, so the state can never mask the answer under test.
TRANSITION_PRECONDITIONS = (
    ("open", ChapterState.planned),
    ("close", ChapterState.open),
    ("reopen", ChapterState.closed),
)


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


def _action_url(book_id, chapter_id, action: str) -> str:
    """A transition path (003.context.md -> "Path shapes")."""
    return f"{BASE}/{book_id}/chapters/{chapter_id}/{action}"


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

    The transitions are the code under test, so they are never used to reach a
    starting state, and `closing` has no other producer in this feature (D8).
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


async def _stored(chapter_id) -> Chapter:
    row = await chapters_db.get_by_id(int(chapter_id))
    assert row is not None
    return row


async def _stored_state(chapter_id) -> ChapterState:
    return (await _stored(chapter_id)).state


# ---------------------------------------------------------------------------
# DoD-8 — the owner opens a planned chapter; a co-author may not
# ---------------------------------------------------------------------------


# DoD-8 (US-036.AC-1): POST /open as the OWNER on a `planned` chapter returns 200
# with state `open`.
async def test_owner_opens_planned_chapter__DoD8_US036_AC1(http_client):
    _owner, owner_token = await _seed_author("alice")
    book = await _create_book(http_client, owner_token)
    chapter = await _seed_chapter(
        book["id"], ordinal=1, title="First Beat", state=ChapterState.planned
    )

    resp = await http_client.post(
        _action_url(book["id"], chapter.id, "open"), headers=_auth_header(owner_token)
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    ChapterResponse.model_validate(body)
    assert body["id"] == str(chapter.id)
    assert body["state"] == "open"

    assert await _stored_state(chapter.id) == ChapterState.open


# DoD-8 (US-036.AC-2): POST /open as a CO-AUTHOR returns 403 and the state is
# unchanged.
async def test_co_author_open_refused_403__DoD8_US036_AC2(http_client):
    _owner, owner_token = await _seed_author("bob")
    co_author, co_token = await _seed_author("carol")
    book = await _create_book(http_client, owner_token)
    await _add_co_author(int(book["id"]), co_author.id)
    chapter = await _seed_chapter(book["id"], state=ChapterState.planned)

    resp = await http_client.post(
        _action_url(book["id"], chapter.id, "open"), headers=_auth_header(co_token)
    )
    assert resp.status_code == 403, resp.text

    assert await _stored_state(chapter.id) == ChapterState.planned


# ---------------------------------------------------------------------------
# DoD-9 — the one-open slot is held by `open` AND by `closing`
# ---------------------------------------------------------------------------


# DoD-9 (US-037.AC-2, US-038.AC-4): POST /open while another chapter is `open` or
# `closing` returns 409 and BOTH chapters keep their states.
@pytest.mark.parametrize(
    "holder_state",
    [
        pytest.param(ChapterState.open, id="holder_open"),
        pytest.param(ChapterState.closing, id="holder_closing"),
    ],
)
async def test_open_refused_while_slot_held__DoD9_US037_AC2_US038_AC4(
    http_client, holder_state
):
    _owner, owner_token = await _seed_author("dave")
    book = await _create_book(http_client, owner_token)
    holder = await _seed_chapter(
        book["id"], ordinal=1, title="Holder", state=holder_state
    )
    target = await _seed_chapter(
        book["id"], ordinal=2, title="Target", state=ChapterState.planned
    )

    resp = await http_client.post(
        _action_url(book["id"], target.id, "open"), headers=_auth_header(owner_token)
    )
    assert resp.status_code == 409, resp.text

    assert await _stored_state(holder.id) == holder_state
    assert await _stored_state(target.id) == ChapterState.planned


# ---------------------------------------------------------------------------
# DoD-10 — the owner closes the open chapter; a co-author may not
# ---------------------------------------------------------------------------


# DoD-10 (US-038.AC-1): POST /close as the OWNER on the `open` chapter returns 200
# with state `closed` -- written directly, never `closing` (D8, "The close seam").
async def test_owner_closes_open_chapter__DoD10_US038_AC1(http_client):
    _owner, owner_token = await _seed_author("erin")
    book = await _create_book(http_client, owner_token)
    chapter = await _seed_chapter(
        book["id"], state=ChapterState.open, text="the written body", version=2
    )

    resp = await http_client.post(
        _action_url(book["id"], chapter.id, "close"), headers=_auth_header(owner_token)
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    ChapterResponse.model_validate(body)
    assert body["id"] == str(chapter.id)
    assert body["state"] == "closed"

    assert await _stored_state(chapter.id) == ChapterState.closed


# DoD-10 (US-038.AC-2): POST /close as a CO-AUTHOR returns 403.
async def test_co_author_close_refused_403__DoD10_US038_AC2(http_client):
    _owner, owner_token = await _seed_author("frank")
    co_author, co_token = await _seed_author("grace")
    book = await _create_book(http_client, owner_token)
    await _add_co_author(int(book["id"]), co_author.id)
    chapter = await _seed_chapter(book["id"], state=ChapterState.open)

    resp = await http_client.post(
        _action_url(book["id"], chapter.id, "close"), headers=_auth_header(co_token)
    )
    assert resp.status_code == 403, resp.text

    assert await _stored_state(chapter.id) == ChapterState.open


# ---------------------------------------------------------------------------
# DoD-11 — reopen a closed chapter, unless the slot is held
# ---------------------------------------------------------------------------


# DoD-11 (US-039.AC-1): POST /reopen as the OWNER on a `closed` chapter with
# nothing else open returns 200 with state `open`.
async def test_owner_reopens_closed_chapter__DoD11_US039_AC1(http_client):
    _owner, owner_token = await _seed_author("heidi")
    book = await _create_book(http_client, owner_token)
    chapter = await _seed_chapter(
        book["id"], state=ChapterState.closed, text="the closed body", version=3
    )

    resp = await http_client.post(
        _action_url(book["id"], chapter.id, "reopen"), headers=_auth_header(owner_token)
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    ChapterResponse.model_validate(body)
    assert body["id"] == str(chapter.id)
    assert body["state"] == "open"

    assert await _stored_state(chapter.id) == ChapterState.open


# DoD-11 (US-039.AC-2): POST /reopen with a DIFFERENT chapter `open` returns 409
# and that chapter is unaffected.
async def test_reopen_refused_while_another_is_open__DoD11_US039_AC2(http_client):
    _owner, owner_token = await _seed_author("ivan")
    book = await _create_book(http_client, owner_token)
    holder = await _seed_chapter(
        book["id"],
        ordinal=1,
        title="Holder",
        state=ChapterState.open,
        text="holder body",
        version=2,
    )
    target = await _seed_chapter(
        book["id"], ordinal=2, title="Target", state=ChapterState.closed
    )

    resp = await http_client.post(
        _action_url(book["id"], target.id, "reopen"), headers=_auth_header(owner_token)
    )
    assert resp.status_code == 409, resp.text

    held = await _stored(holder.id)
    assert held.state == ChapterState.open
    assert held.text == "holder body"
    assert held.version == 2
    assert await _stored_state(target.id) == ChapterState.closed


# ---------------------------------------------------------------------------
# DoD-12 — the remaining precondition refusals are 409
# ---------------------------------------------------------------------------


# DoD-12: POST /reopen on a chapter that is not `closed` returns 409.
@pytest.mark.parametrize(
    "state",
    [
        pytest.param(ChapterState.planned, id="planned"),
        pytest.param(ChapterState.open, id="open"),
        pytest.param(ChapterState.closing, id="closing"),
    ],
)
async def test_reopen_refused_when_not_closed__DoD12(http_client, state):
    _owner, owner_token = await _seed_author("judy")
    book = await _create_book(http_client, owner_token)
    chapter = await _seed_chapter(book["id"], state=state)

    resp = await http_client.post(
        _action_url(book["id"], chapter.id, "reopen"), headers=_auth_header(owner_token)
    )
    assert resp.status_code == 409, resp.text

    assert await _stored_state(chapter.id) == state


# DoD-12: POST /close on a chapter that is not `open` returns 409.
@pytest.mark.parametrize(
    "state",
    [
        pytest.param(ChapterState.planned, id="planned"),
        pytest.param(ChapterState.closing, id="closing"),
        pytest.param(ChapterState.closed, id="closed"),
    ],
)
async def test_close_refused_when_not_open__DoD12(http_client, state):
    _owner, owner_token = await _seed_author("kevin")
    book = await _create_book(http_client, owner_token)
    chapter = await _seed_chapter(book["id"], state=state)

    resp = await http_client.post(
        _action_url(book["id"], chapter.id, "close"), headers=_auth_header(owner_token)
    )
    assert resp.status_code == 409, resp.text

    assert await _stored_state(chapter.id) == state


# ---------------------------------------------------------------------------
# DoD-7 — an archived book refuses every transition (the transition half)
# ---------------------------------------------------------------------------


# DoD-7 (D10): all three transitions return 403 on a book whose state is
# `archived`. Each case seeds the chapter in the state its transition REQUIRES,
# so the 403 can never be a state-machine 409 in disguise. The body half of this
# item is in tests/routes/test_chapter_text.py.
@pytest.mark.parametrize(
    ("action", "state"),
    [pytest.param(a, s, id=a) for a, s in TRANSITION_PRECONDITIONS],
)
async def test_transitions_refused_on_archived_book__DoD7(http_client, action, state):
    _owner, owner_token = await _seed_author("laura")
    book = await _create_book(http_client, owner_token)
    chapter = await _seed_chapter(book["id"], state=state)
    await _archive_book(http_client, owner_token, book["id"])

    resp = await http_client.post(
        _action_url(book["id"], chapter.id, action), headers=_auth_header(owner_token)
    )
    assert resp.status_code == 403, resp.text

    assert await _stored_state(chapter.id) == state


# ---------------------------------------------------------------------------
# DoD-13 — a logged-in non-member of a PUBLIC book gets 403 from every transition
# ---------------------------------------------------------------------------


# DoD-13: a logged-in non-member of a PUBLIC book resolves to the `reader` role,
# reaches the service and is refused 403 on all three transitions. (Its "200 from
# the body GET" half is in tests/routes/test_chapter_text.py.)
@pytest.mark.parametrize(
    ("action", "state"),
    [pytest.param(a, s, id=a) for a, s in TRANSITION_PRECONDITIONS],
)
async def test_public_book_non_member_transitions_403__DoD13(
    http_client, action, state
):
    _owner, owner_token = await _seed_author("mike")
    _stranger, stranger_token = await _seed_author("nina")
    book = await _create_book(http_client, owner_token, visibility="public")
    chapter = await _seed_chapter(book["id"], state=state)

    resp = await http_client.post(
        _action_url(book["id"], chapter.id, action),
        headers=_auth_header(stranger_token),
    )
    assert resp.status_code == 403, resp.text

    assert await _stored_state(chapter.id) == state


# ---------------------------------------------------------------------------
# DoD-14 — a PRIVATE book hides its existence from a stranger (404)
# ---------------------------------------------------------------------------


# DoD-14: a user with no relationship to a PRIVATE book gets 404 from all three
# transitions -- existence hiding inherited from the dependency, never
# re-derived.
@pytest.mark.parametrize(
    ("action", "state"),
    [pytest.param(a, s, id=a) for a, s in TRANSITION_PRECONDITIONS],
)
async def test_private_book_stranger_gets_404__DoD14(http_client, action, state):
    _owner, owner_token = await _seed_author("oscar")
    _stranger, stranger_token = await _seed_author("paula")
    book = await _create_book(http_client, owner_token, visibility="private")
    chapter = await _seed_chapter(book["id"], state=state)

    resp = await http_client.post(
        _action_url(book["id"], chapter.id, action),
        headers=_auth_header(stranger_token),
    )
    assert resp.status_code == 404, resp.text


# ---------------------------------------------------------------------------
# DoD-15 — no token at all is 401
# ---------------------------------------------------------------------------


# DoD-15: a request with no token gets 401 from all three transitions.
@pytest.mark.parametrize(
    ("action", "state"),
    [pytest.param(a, s, id=a) for a, s in TRANSITION_PRECONDITIONS],
)
async def test_no_token_gets_401__DoD15(http_client, action, state):
    _owner, owner_token = await _seed_author("quinn")
    book = await _create_book(http_client, owner_token, visibility="public")
    chapter = await _seed_chapter(book["id"], state=state)

    resp = await http_client.post(_action_url(book["id"], chapter.id, action))
    assert resp.status_code == 401, resp.text


# ---------------------------------------------------------------------------
# DoD-16 — a chapter of ANOTHER book is 404, not 403 and not 200
# ---------------------------------------------------------------------------


# DoD-16: addressing a chapter id that belongs to ANOTHER book returns 404 -- not
# 403, not 200 -- on all three transitions. The caller is a member (owner) of BOTH
# books and both are ACTIVE, so the 404 is provably the book-scoping check and not
# an authorization or archive failure.
@pytest.mark.parametrize(
    ("action", "state"),
    [pytest.param(a, s, id=a) for a, s in TRANSITION_PRECONDITIONS],
)
async def test_foreign_book_chapter_is_404__DoD16(http_client, action, state):
    _owner, owner_token = await _seed_author("rosa")
    book_a = await _create_book(http_client, owner_token, title="Book A")
    book_b = await _create_book(http_client, owner_token, title="Book B")
    foreign = await _seed_chapter(book_b["id"], state=state)

    resp = await http_client.post(
        _action_url(book_a["id"], foreign.id, action),
        headers=_auth_header(owner_token),
    )
    assert resp.status_code == 404, resp.text

    # The foreign chapter is untouched.
    assert await _stored_state(foreign.id) == state


# ---------------------------------------------------------------------------
# DoD-17 — the transitions accept a request with NO BODY at all
# ---------------------------------------------------------------------------


# DoD-17 (second half): the three transitions accept a request with no body at
# all -- no request body is declared, so a bodiless POST is never a validation
# failure. Asserted as "not 422": the transition's own outcome is DoD-8 / DoD-10 /
# DoD-11's subject, not this item's. (The malformed-body half is in
# tests/routes/test_chapter_text.py.)
@pytest.mark.parametrize(
    ("action", "state"),
    [pytest.param(a, s, id=a) for a, s in TRANSITION_PRECONDITIONS],
)
async def test_transitions_accept_a_bodiless_request__DoD17(
    http_client, action, state
):
    _owner, owner_token = await _seed_author("sam")
    book = await _create_book(http_client, owner_token)
    chapter = await _seed_chapter(book["id"], state=state)

    resp = await http_client.post(
        _action_url(book["id"], chapter.id, action), headers=_auth_header(owner_token)
    )
    assert resp.status_code != 422, resp.text
