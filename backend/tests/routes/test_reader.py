"""End-to-end tests for the reader HTTP surface (feature 022, ultra track).

Covers five of the plan's nine `[test]` items — DoD-2, DoD-3, DoD-4, DoD-5 and
DoD-7. The two service-layer items (DoD-1, DoD-6) live in
`tests/services/test_reader.py`.

Exercised in-process against the real `app.main.app` via the `http_client`
fixture (httpx `ASGITransport`, no live server, no network). Auth is REAL: each
test seeds its own user rows and mints real JWTs, so the whole request path --
`Depends(authz.book_access)` included -- runs. The `_now` / `_auth_header` /
`_seed_user` / `_seed_author` / `_create_book` helpers are copied per-file from
`tests/routes/test_chapter_text.py` rather than imported (they are deliberately
not shared fixtures). The `db` fixture is deliberately NOT requested: it would
repoint the process-global engine away from the one `http_client`'s lifespan
initialized.

Bound to the frozen skeleton (status.md -> `## Skeleton`):

    app.routes.reader   (router prefix "/api/books", both gated by
                         Depends(authz.book_access))
        GET "/{book_id}/read"                          -> ReaderBookResponse
        GET "/{book_id}/read/chapters/{chapter_id}"    -> ReaderChapterResponse

    app.routes.books    (delivered router, one route added)
        GET "/public"                                  -> PublicBookListResponse
                         (authenticated, NOT book-scoped -- D14)

    app.models.schemas.reader
        ReaderChapterRef        -- id: str, title: str
        ReaderBookResponse      -- title: str, chapters: list[ReaderChapterRef]
        ReaderChapterResponse   -- id: str, title: str, text: str
        PublicBookRef           -- id: str, title: str, description: str
        PublicBookListResponse  -- items: list[PublicBookRef]

Expected values come from the SPEC ONLY -- `plan.md`'s Definition of done, its
`## Decisions taken` (D2, D5, D14) and `context.md`'s status taxonomy -- never
from implementation internals:

    - DoD-2 (UC-029): the book projection's keys are exactly {title, chapters}
      and each chapter ref's keys are exactly {id, title}.
    - DoD-3 (UC-029, D5): a reader-visible chapter answers 200 with exactly
      {id, title, text}; a `planned` chapter, a `closing` chapter, an unknown id,
      a non-numeric id and a chapter of ANOTHER book all answer the same 404 --
      indistinguishable, so a reader cannot walk the id space to reconstruct the
      author's unwritten skeleton.
    - DoD-4 (US-030.AC-3): a logged-in non-member is refused 404 by both reader
      routes on a PRIVATE book and served 200 by both on a PUBLIC one.
    - DoD-5 (US-030.AC-4): no token is 401 on all three routes.
    - DoD-7 (UC-029, D14): each discovery item's keys are exactly
      {id, title, description}.

A chapter is put into its starting state by writing it straight through
`app.db.chapters` -- the transition routes are never used to reach a
precondition (`closing` is reachable no other way).

Async tests use asyncio_mode = "auto".
"""

import datetime

import pytest

from app.db import chapters as chapters_db, users
from app.db.engine import init_db, set_db_ready
from app.models.chapter import Chapter, ChapterState
from app.models.schemas.reader import (
    PublicBookListResponse,
    ReaderBookResponse,
    ReaderChapterResponse,
)
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


async def _seed_chapter(
    book_id,
    *,
    ordinal: int = 1,
    title: str = "Seeded",
    state: ChapterState = ChapterState.open,
    text: str = "the saved body",
) -> Chapter:
    """A Chapter inserted straight through db/chapters.py, bypassing the routes."""
    return await chapters_db.create(
        Chapter(
            book_id=int(book_id),
            ordinal=ordinal,
            title=title,
            state=state,
            sketch="working material a reader must never see",
            text=text,
            version=1,
            summary="an author-facing summary",
        )
    )


def _toc_url(book_id) -> str:
    return f"{BASE}/{book_id}/read"


def _chapter_url(book_id, chapter_id) -> str:
    return f"{BASE}/{book_id}/read/chapters/{chapter_id}"


# ---------------------------------------------------------------------------
# DoD-2 — the book projection is exactly {title, chapters} / {id, title}
# ---------------------------------------------------------------------------


# DoD-2 (UC-029): GET /{book_id}/read answers with EXACTLY {title, chapters},
# and each chapter ref carries EXACTLY {id, title} -- no `sketch`, `summary`,
# `state`, `ordinal` or `version`. The exclusion is structural, not a filter.
async def test_read_projection_keys_are_exactly_title_and_refs__DoD2_UC029(http_client):
    _owner, owner_token = await _seed_author("alice")
    _reader, reader_token = await _seed_author("bob")

    book = await _create_book(
        http_client, owner_token, title="Reader Safe", visibility="public"
    )
    chapter = await _seed_chapter(
        book["id"], ordinal=1, title="The Ravens Depart", state=ChapterState.open
    )

    resp = await http_client.get(
        _toc_url(book["id"]), headers=_auth_header(reader_token)
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    ReaderBookResponse.model_validate(body)

    assert set(body.keys()) == {"title", "chapters"}
    assert body["title"] == "Reader Safe"

    assert len(body["chapters"]) == 1
    ref = body["chapters"][0]
    assert set(ref.keys()) == {"id", "title"}
    assert ref["id"] == str(chapter.id)
    assert ref["title"] == "The Ravens Depart"

    for forbidden in (
        "sketch",
        "summary",
        "summary_status",
        "state",
        "ordinal",
        "version",
        "text",
        "book_id",
        "created_at",
        "modified_at",
    ):
        assert forbidden not in ref

    for forbidden in (
        "id",
        "owner_id",
        "description",
        "visibility",
        "state",
        "collaboration_mode",
        "members",
        "system_prompt",
        "active_notes",
    ):
        assert forbidden not in body


# ---------------------------------------------------------------------------
# DoD-3 — one 200 shape, five refusal sources collapsed onto the same 404
# ---------------------------------------------------------------------------


# DoD-3 (UC-029, D5): a reader-visible chapter answers 200 with EXACTLY
# {id, title, text}; a `planned` chapter, a `closing` chapter, an unknown id, a
# non-numeric id and a chapter belonging to ANOTHER book all answer 404. The 200
# baseline is asserted on every parameterization: it proves the 404 is the
# refusal under test and not a route that refuses everything.
@pytest.mark.parametrize(
    "refusal",
    [
        pytest.param("planned_chapter", id="planned_chapter"),
        pytest.param("closing_chapter", id="closing_chapter"),
        pytest.param("unknown_id", id="unknown_id"),
        pytest.param("non_numeric_id", id="non_numeric_id"),
        pytest.param("other_books_chapter", id="other_books_chapter"),
    ],
)
async def test_chapter_route_collapses_refusals_onto_404__DoD3_UC029(
    http_client, refusal
):
    _owner, owner_token = await _seed_author("carol")
    _reader, reader_token = await _seed_author("dave")

    book = await _create_book(
        http_client, owner_token, title="Open To All", visibility="public"
    )
    visible = await _seed_chapter(
        book["id"],
        ordinal=1,
        title="Dawn Over the Wall",
        state=ChapterState.closed,
        text="The lantern guttered in the wind.",
    )

    served = await http_client.get(
        _chapter_url(book["id"], visible.id), headers=_auth_header(reader_token)
    )
    assert served.status_code == 200, served.text
    payload = served.json()
    ReaderChapterResponse.model_validate(payload)
    assert set(payload.keys()) == {"id", "title", "text"}
    assert payload["id"] == str(visible.id)
    assert payload["title"] == "Dawn Over the Wall"
    assert payload["text"] == "The lantern guttered in the wind."

    if refusal == "planned_chapter":
        target = str(
            (
                await _seed_chapter(
                    book["id"],
                    ordinal=2,
                    title="An Unwritten Beat",
                    state=ChapterState.planned,
                    text="",
                )
            ).id
        )
    elif refusal == "closing_chapter":
        target = str(
            (
                await _seed_chapter(
                    book["id"],
                    ordinal=3,
                    title="Mid-Close At Castle Black",
                    state=ChapterState.closing,
                )
            ).id
        )
    elif refusal == "unknown_id":
        target = "9007199254740993"
    elif refusal == "non_numeric_id":
        target = "not-a-chapter-id"
    else:
        other_book = await _create_book(
            http_client, owner_token, title="Another Book", visibility="public"
        )
        target = str(
            (
                await _seed_chapter(
                    other_book["id"],
                    ordinal=1,
                    title="Belongs Elsewhere",
                    state=ChapterState.open,
                )
            ).id
        )

    refused = await http_client.get(
        _chapter_url(book["id"], target), headers=_auth_header(reader_token)
    )
    assert refused.status_code == 404, refused.text


# ---------------------------------------------------------------------------
# DoD-4 — private refuses the non-member on both routes; public serves them
# ---------------------------------------------------------------------------


# DoD-4 (US-030.AC-3): the SAME logged-in non-member gets 404 from both reader
# routes on a PRIVATE book and 200 from both on a PUBLIC one -- so the refusal is
# provably the visibility boundary and not the caller.
async def test_private_refuses_public_serves_same_caller__DoD4_US030_AC3(http_client):
    _owner, owner_token = await _seed_author("erin")
    _reader, reader_token = await _seed_author("frank")

    private_book = await _create_book(
        http_client, owner_token, title="Hidden", visibility="private"
    )
    private_chapter = await _seed_chapter(
        private_book["id"], ordinal=1, title="Hidden Beat", state=ChapterState.open
    )

    public_book = await _create_book(
        http_client, owner_token, title="Shown", visibility="public"
    )
    public_chapter = await _seed_chapter(
        public_book["id"], ordinal=1, title="Shown Beat", state=ChapterState.open
    )

    for url in (
        _toc_url(private_book["id"]),
        _chapter_url(private_book["id"], private_chapter.id),
    ):
        refused = await http_client.get(url, headers=_auth_header(reader_token))
        assert refused.status_code == 404, f"{url}: {refused.text}"

    for url in (
        _toc_url(public_book["id"]),
        _chapter_url(public_book["id"], public_chapter.id),
    ):
        served = await http_client.get(url, headers=_auth_header(reader_token))
        assert served.status_code == 200, f"{url}: {served.text}"


# ---------------------------------------------------------------------------
# DoD-5 — no token is 401 on all three routes
# ---------------------------------------------------------------------------


# DoD-5 (US-030.AC-4): a request with no token gets 401 from the TOC route, the
# chapter route and the public discovery route alike -- there is no anonymous
# reader surface anywhere in this feature.
@pytest.mark.parametrize(
    "route",
    [
        pytest.param("toc", id="toc"),
        pytest.param("chapter", id="chapter"),
        pytest.param("public_list", id="public_list"),
    ],
)
async def test_no_token_is_401_on_all_three_routes__DoD5_US030_AC4(http_client, route):
    _owner, owner_token = await _seed_author("grace")
    book = await _create_book(
        http_client, owner_token, title="Open To All", visibility="public"
    )
    chapter = await _seed_chapter(
        book["id"], ordinal=1, title="Dawn Over the Wall", state=ChapterState.open
    )

    if route == "toc":
        url = _toc_url(book["id"])
    elif route == "chapter":
        url = _chapter_url(book["id"], chapter.id)
    else:
        url = f"{BASE}/public"

    resp = await http_client.get(url)
    assert resp.status_code == 401, resp.text


# ---------------------------------------------------------------------------
# DoD-7 — the discovery item is exactly {id, title, description}
# ---------------------------------------------------------------------------


# DoD-7 (UC-029, D14): each GET /api/books/public item carries EXACTLY
# {id, title, description} -- no `owner_id`, `visibility`, `state`,
# `collaboration_mode` and no timestamps.
async def test_public_list_item_keys_are_exactly_three__DoD7_UC029(http_client):
    _owner, owner_token = await _seed_author("heidi")
    _reader, reader_token = await _seed_author("ivan")

    book = await _create_book(
        http_client,
        owner_token,
        title="Open To All",
        description="A saga for anyone.",
        visibility="public",
    )

    resp = await http_client.get(
        f"{BASE}/public", headers=_auth_header(reader_token)
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    PublicBookListResponse.model_validate(body)

    items = body["items"]
    assert [item["id"] for item in items] == [book["id"]]

    item = items[0]
    assert set(item.keys()) == {"id", "title", "description"}
    assert item["title"] == "Open To All"
    assert item["description"] == "A saga for anyone."

    for forbidden in (
        "owner_id",
        "visibility",
        "state",
        "collaboration_mode",
        "created_at",
        "modified_at",
        "system_prompt",
        "active_notes",
        "members",
    ):
        assert forbidden not in item
