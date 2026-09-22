"""End-to-end tests for the per-author CHAPTER system-prompt HTTP surface
(feature 014, step 004).

Exercised in-process against the real `app.main.app` via the `http_client`
fixture (httpx `ASGITransport`, no live server, no network). Each test seeds its
own users, books, chapters and member rows on the same process-global engine the
app uses (schema built with `init_db`, readiness flipped with
`set_db_ready(True)`), with the `_now` / `_auth_header` / `_seed_user` /
`_seed_author` / `_create_book` / `_add_co_author` helpers copied per-file from
tests/routes/test_book_settings.py (context.md -> "Testing facts shared by every
step").

Bound to the frozen skeleton (status.md -> Skeleton -> Step 004), router
`app.routes.chapter_author_prompts` with prefix "/api/books", both handlers
gated by `Depends(authz.book_access)`, neither re-declaring `book_id`, and
`chapter_id` the only path parameter:
    GET /{book_id}/chapters/{chapter_id}/system-prompt -> 200 ChapterAuthorPromptResponse
    PUT /{book_id}/chapters/{chapter_id}/system-prompt -> 200 ChapterAuthorPromptResponse
and the step-004 DTOs of `app.models.schemas.chapter_author_prompts`
(`UpdateChapterAuthorPromptRequest.system_prompt`; response fields `chapter_id`
as a STRING, `system_prompt`, `modified_at`, and NO `user_id`).

Expected values come from the SPEC ONLY -- 004.chapter-prompt-service-routes.md
(Interface intent + DoD-1..DoD-15), 004.context.md and the feature context.md
("Chapter-prompt DTOs", "Endpoints", "Status taxonomy") -- never from
implementation internals:
    - DoD-1: GET is 200 with the caller's own stored prompt;
    - DoD-2: no row yet is 200 with an empty prompt and a NULL timestamp, never
      a 404 -- "this author has not written one yet" is the normal starting
      state (context.md -> "A missing row is a 200 ... never a 404");
    - DoD-3: PUT stores the body's text, echoes it, and a following GET agrees;
      PUT answers 200 (not 201) on both the create and the update path;
    - DoD-9: a logged-in non-member of a PUBLIC book -> 403 from both verbs,
      nothing stored;
    - DoD-10: a stranger to a PRIVATE book -> 404 from both verbs (existence
      hiding, inherited from the dependency);
    - DoD-11: no token -> 401 from both verbs;
    - DoD-12: an unknown chapter id, or one belonging to ANOTHER book -> 404
      from both verbs, and the PUT stores nothing;
    - DoD-13: the response body exposes no user identifier and no field a
      caller could vary to reach another author's prompt;
    - DoD-14: no DELETE and no POST on the path -- both refused by the
      framework (405), not by a handler;
    - DoD-15: a PUT body missing the prompt field is a validation error (422)
      and stores nothing.

Harness note (mirroring tests/routes/test_chapters.py): the `db` fixture is
deliberately NOT requested anywhere in this module. Both it and `http_client`
initialize the process-global engine, so requesting both would repoint the
engine away from the one the app's lifespan built. The places that must reach
past the routes -- seeding chapters and reading stored prompt rows -- call
`app.db.*` directly against the app's own engine, exactly as the inherited
`_add_co_author` helper already calls `app.db.book_members`.

Async tests use asyncio_mode = "auto".
"""

import datetime

import pytest

from app.db import book_members, users
from app.db import chapter_author_prompts as prompts_db
from app.db import chapters as chapters_db
from app.db.engine import init_db, set_db_ready
from app.models.book_member import BookMember, MemberRole
from app.models.chapter import Chapter, ChapterState
from app.models.schemas.chapter_author_prompts import (
    ChapterAuthorPromptResponse,
    UpdateChapterAuthorPromptRequest,
)
from app.models.user import User, UserRole
from app.services import auth

BASE = "/api/books"

# The exact ChapterAuthorPromptResponse field set, from context.md ->
# "Chapter-prompt DTOs": no `user_id`, no `created_at`, no `book_id`.
WIRE_FIELDS = {"chapter_id", "system_prompt", "modified_at"}


# ---------------------------------------------------------------------------
# Seed helpers -- copied per-file from tests/routes/test_book_settings.py.
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Local helpers.
# ---------------------------------------------------------------------------


def _prompt_url(book_id, chapter_id) -> str:
    return f"{BASE}/{book_id}/chapters/{chapter_id}/system-prompt"


async def _seed_chapter_row(
    book_id,
    *,
    ordinal: int = 1,
    title: str = "A Chapter",
    sketch: str = "a sketch",
    state: ChapterState = ChapterState.planned,
) -> Chapter:
    """A Chapter inserted straight through db/chapters.py, bypassing the routes."""
    return await chapters_db.create(
        Chapter(
            book_id=int(book_id),
            ordinal=ordinal,
            title=title,
            state=state,
            sketch=sketch,
            text="",
        )
    )


async def _get_prompt(
    http_client, token: str, book_id, chapter_id
) -> ChapterAuthorPromptResponse:
    resp = await http_client.get(
        _prompt_url(book_id, chapter_id), headers=_auth_header(token)
    )
    assert resp.status_code == 200, resp.text
    return ChapterAuthorPromptResponse.model_validate(resp.json())


async def _put_prompt(
    http_client, token: str, book_id, chapter_id, text: str
) -> ChapterAuthorPromptResponse:
    resp = await http_client.put(
        _prompt_url(book_id, chapter_id),
        headers=_auth_header(token),
        json={"system_prompt": text},
    )
    assert resp.status_code == 200, resp.text
    return ChapterAuthorPromptResponse.model_validate(resp.json())


# ---------------------------------------------------------------------------
# DoD-1 — GET returns 200 and the caller's own stored prompt
# ---------------------------------------------------------------------------


# DoD-1: GET answers 200 with the caller's own text for that chapter, the
# chapter id as a string and a real modified timestamp -- while a co-author of
# the same book holds a different prompt on the same chapter.
async def test_get_returns_the_callers_own_prompt__DoD1(http_client):
    owner, owner_token = await _seed_author("alice")
    co_author, co_token = await _seed_author("bob")
    book = await _create_book(http_client, owner_token)
    await _add_co_author(int(book["id"]), co_author.id)
    chapter = await _seed_chapter_row(book["id"])

    await _put_prompt(http_client, owner_token, book["id"], chapter.id, "OWNER VOICE")
    await _put_prompt(http_client, co_token, book["id"], chapter.id, "CO VOICE")

    resp = await http_client.get(
        _prompt_url(book["id"], chapter.id), headers=_auth_header(owner_token)
    )
    assert resp.status_code == 200, resp.text
    prompt = ChapterAuthorPromptResponse.model_validate(resp.json())

    assert prompt.chapter_id == str(chapter.id)
    assert prompt.system_prompt == "OWNER VOICE"
    assert prompt.modified_at is not None

    # The co-author's GET on the same URL answers with THEIR text, never the
    # owner's.
    co_read = await _get_prompt(http_client, co_token, book["id"], chapter.id)
    assert co_read.system_prompt == "CO VOICE"
    assert co_read.chapter_id == str(chapter.id)


# ---------------------------------------------------------------------------
# DoD-2 — no row yet is 200 with an empty prompt and a null timestamp
# ---------------------------------------------------------------------------


# DoD-2 (context.md -> "A missing row is a 200 with an empty prompt, never a
# 404"): a member who has never written a prompt for this chapter reads
# 200 / "" / null -- for the owner and for a co-author alike.
async def test_get_without_a_row_is_200_empty_and_null__DoD2(http_client):
    owner, owner_token = await _seed_author("carol")
    co_author, co_token = await _seed_author("dave")
    book = await _create_book(http_client, owner_token)
    await _add_co_author(int(book["id"]), co_author.id)
    chapter = await _seed_chapter_row(book["id"])

    for token in (owner_token, co_token):
        resp = await http_client.get(
            _prompt_url(book["id"], chapter.id), headers=_auth_header(token)
        )
        assert resp.status_code == 200, resp.text
        prompt = ChapterAuthorPromptResponse.model_validate(resp.json())
        assert prompt.chapter_id == str(chapter.id)
        assert prompt.system_prompt == ""
        assert prompt.modified_at is None


# ---------------------------------------------------------------------------
# DoD-3 — PUT stores the text, echoes it, and a following GET agrees
# ---------------------------------------------------------------------------


# DoD-3 (context.md -> "Endpoints": PUT is the upsert and answers 200 on the
# create path, not 201): the response echoes what was stored and a following
# GET returns the same value.
async def test_put_stores_text_and_get_returns_it__DoD3(http_client):
    _owner, owner_token = await _seed_author("erin")
    book = await _create_book(http_client, owner_token)
    chapter = await _seed_chapter_row(book["id"])

    resp = await http_client.put(
        _prompt_url(book["id"], chapter.id),
        headers=_auth_header(owner_token),
        json={"system_prompt": "Keep the prose terse."},
    )
    assert resp.status_code == 200, resp.text
    written = ChapterAuthorPromptResponse.model_validate(resp.json())
    assert written.chapter_id == str(chapter.id)
    assert written.system_prompt == "Keep the prose terse."
    assert written.modified_at is not None

    read_back = await _get_prompt(http_client, owner_token, book["id"], chapter.id)
    assert read_back.system_prompt == "Keep the prose terse."
    assert read_back.chapter_id == str(chapter.id)
    assert read_back.modified_at is not None


# DoD-3: the UPDATE path answers 200 too -- the same URL answers before and
# after, and the later value is what a following GET returns.
async def test_second_put_answers_200_and_wins__DoD3(http_client):
    _owner, owner_token = await _seed_author("frank")
    book = await _create_book(http_client, owner_token)
    chapter = await _seed_chapter_row(book["id"])

    await _put_prompt(http_client, owner_token, book["id"], chapter.id, "First voice.")

    resp = await http_client.put(
        _prompt_url(book["id"], chapter.id),
        headers=_auth_header(owner_token),
        json={"system_prompt": "Second voice."},
    )
    assert resp.status_code == 200, resp.text
    second = ChapterAuthorPromptResponse.model_validate(resp.json())
    assert second.system_prompt == "Second voice."

    read_back = await _get_prompt(http_client, owner_token, book["id"], chapter.id)
    assert read_back.system_prompt == "Second voice."


# ---------------------------------------------------------------------------
# DoD-9 — a logged-in non-member of a PUBLIC book gets 403 from both verbs
# ---------------------------------------------------------------------------


# DoD-9 (context.md -> "Status taxonomy"): the caller can legitimately see the
# public book, so the refusal names the missing relationship (403) rather than
# hiding the book -- and the refused write reaches no storage.
async def test_non_member_of_public_book_gets_403_from_both_verbs__DoD9(http_client):
    _owner, owner_token = await _seed_author("grace")
    non_member, nm_token = await _seed_author("heidi")
    book = await _create_book(http_client, owner_token, visibility="public")
    chapter = await _seed_chapter_row(book["id"])
    url = _prompt_url(book["id"], chapter.id)
    h = _auth_header(nm_token)

    assert (await http_client.get(url, headers=h)).status_code == 403
    put = await http_client.put(url, headers=h, json={"system_prompt": "not mine"})
    assert put.status_code == 403, put.text

    # Nothing was stored for the refused caller.
    assert (
        await prompts_db.get_by_chapter_and_user(chapter.id, non_member.id) is None
    )
    # ...and the owner's own prompt is still unwritten.
    owner_read = await _get_prompt(http_client, owner_token, book["id"], chapter.id)
    assert owner_read.system_prompt == ""
    assert owner_read.modified_at is None


# ---------------------------------------------------------------------------
# DoD-10 — a stranger to a PRIVATE book gets 404 from both verbs
# ---------------------------------------------------------------------------


# DoD-10 (context.md -> "Status taxonomy": existence hiding, produced by
# `book_access` and never re-derived): a user with no relationship to a private
# book is answered 404 on both verbs.
async def test_stranger_to_private_book_gets_404_from_both_verbs__DoD10(http_client):
    _owner, owner_token = await _seed_author("ivan")
    stranger, stranger_token = await _seed_author("judy")
    book = await _create_book(http_client, owner_token, visibility="private")
    chapter = await _seed_chapter_row(book["id"])
    url = _prompt_url(book["id"], chapter.id)
    h = _auth_header(stranger_token)

    assert (await http_client.get(url, headers=h)).status_code == 404
    put = await http_client.put(url, headers=h, json={"system_prompt": "sneaky"})
    assert put.status_code == 404, put.text

    assert await prompts_db.get_by_chapter_and_user(chapter.id, stranger.id) is None


# ---------------------------------------------------------------------------
# DoD-11 — no token is 401 from both verbs
# ---------------------------------------------------------------------------


# DoD-11 (context.md -> "Status taxonomy": no valid token -> 401). Asserted
# against a PUBLIC book so the refusal cannot be existence hiding.
async def test_missing_token_gets_401_from_both_verbs__DoD11(http_client):
    _owner, owner_token = await _seed_author("kevin")
    book = await _create_book(http_client, owner_token, visibility="public")
    chapter = await _seed_chapter_row(book["id"])
    url = _prompt_url(book["id"], chapter.id)

    assert (await http_client.get(url)).status_code == 401
    assert (
        await http_client.put(url, json={"system_prompt": "anonymous"})
    ).status_code == 401


# ---------------------------------------------------------------------------
# DoD-12 — an unknown or foreign chapter id is 404 from both verbs
# ---------------------------------------------------------------------------


# DoD-12: a chapter id that does not exist answers 404 on both verbs, and the
# PUT stores nothing.
async def test_unknown_chapter_id_gets_404_from_both_verbs__DoD12(http_client):
    _owner, owner_token = await _seed_author("laura")
    book = await _create_book(http_client, owner_token)
    url = _prompt_url(book["id"], 999999999999)
    h = _auth_header(owner_token)

    assert (await http_client.get(url, headers=h)).status_code == 404
    put = await http_client.put(url, headers=h, json={"system_prompt": "nowhere"})
    assert put.status_code == 404, put.text


# DoD-12: a chapter that exists but belongs to ANOTHER book answers 404 on both
# verbs, and the PUT stores nothing. The caller is a member of BOTH books, so
# the refusal is provably book-scoping rather than authorization -- and the
# foreign chapter keeps having no prompt row for them.
async def test_foreign_chapter_id_gets_404_from_both_verbs__DoD12(http_client):
    owner, owner_token = await _seed_author("mike")
    book_one = await _create_book(http_client, owner_token, title="Book One")
    book_two = await _create_book(http_client, owner_token, title="Book Two")
    foreign_chapter = await _seed_chapter_row(book_two["id"], title="Elsewhere")

    # Addressed through book ONE, but the chapter belongs to book TWO.
    url = _prompt_url(book_one["id"], foreign_chapter.id)
    h = _auth_header(owner_token)

    assert (await http_client.get(url, headers=h)).status_code == 404
    put = await http_client.put(url, headers=h, json={"system_prompt": "crossed over"})
    assert put.status_code == 404, put.text

    # Nothing was stored -- neither under the foreign chapter...
    assert (
        await prompts_db.get_by_chapter_and_user(foreign_chapter.id, owner.id) is None
    )
    # ...nor when the chapter is addressed through its OWN book.
    own_book_read = await _get_prompt(
        http_client, owner_token, book_two["id"], foreign_chapter.id
    )
    assert own_book_read.system_prompt == ""
    assert own_book_read.modified_at is None


# ---------------------------------------------------------------------------
# DoD-13 — the response offers no handle on another author's prompt
# ---------------------------------------------------------------------------


# DoD-13 (context.md -> "Chapter-prompt DTOs": no `user_id`, "it is always the
# caller"): the wire body carries exactly the three contract fields and no user
# identifier, on both the read and the write path.
async def test_response_body_exposes_no_user_identifier__DoD13(http_client):
    _owner, owner_token = await _seed_author("nina")
    book = await _create_book(http_client, owner_token)
    chapter = await _seed_chapter_row(book["id"])
    url = _prompt_url(book["id"], chapter.id)
    h = _auth_header(owner_token)

    put = await http_client.put(url, headers=h, json={"system_prompt": "mine"})
    assert put.status_code == 200, put.text
    get = await http_client.get(url, headers=h)
    assert get.status_code == 200, get.text

    for body in (put.json(), get.json()):
        assert set(body) == WIRE_FIELDS
        assert not [name for name in body if "user" in name.lower()]
        assert isinstance(body["chapter_id"], str)

    # The request DTO offers exactly one field, and it is the prompt text.
    assert set(UpdateChapterAuthorPromptRequest.model_fields) == {"system_prompt"}


# DoD-13: no field a caller could vary reaches another author's prompt -- a PUT
# body carrying an extra user identifier writes only the caller's own row and
# leaves the other member's untouched.
async def test_no_caller_supplied_field_selects_another_author__DoD13(http_client):
    owner, owner_token = await _seed_author("oscar")
    co_author, co_token = await _seed_author("paula")
    book = await _create_book(http_client, owner_token)
    await _add_co_author(int(book["id"]), co_author.id)
    chapter = await _seed_chapter_row(book["id"])

    await _put_prompt(http_client, co_token, book["id"], chapter.id, "CO VOICE")

    resp = await http_client.put(
        _prompt_url(book["id"], chapter.id),
        headers=_auth_header(owner_token),
        json={"system_prompt": "OWNER VOICE", "user_id": str(co_author.id)},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body) == WIRE_FIELDS

    # The co-author's prompt is untouched; the owner wrote only their own.
    co_read = await _get_prompt(http_client, co_token, book["id"], chapter.id)
    assert co_read.system_prompt == "CO VOICE"
    owner_read = await _get_prompt(http_client, owner_token, book["id"], chapter.id)
    assert owner_read.system_prompt == "OWNER VOICE"


# ---------------------------------------------------------------------------
# DoD-14 — the path answers no DELETE and no POST
# ---------------------------------------------------------------------------


# DoD-14 (context.md -> "Endpoints": "No POST and no DELETE on the prompt
# path"): both are refused by the FRAMEWORK -- 405 Method Not Allowed, the
# answer of a path that exists but does not serve the verb -- and the stored
# prompt survives the attempt.
@pytest.mark.parametrize("method", [pytest.param("DELETE", id="delete"),
                                    pytest.param("POST", id="post")])
async def test_path_answers_no_delete_and_no_post__DoD14(http_client, method: str):
    _owner, owner_token = await _seed_author(f"quinn_{method.lower()}")
    book = await _create_book(http_client, owner_token)
    chapter = await _seed_chapter_row(book["id"])
    url = _prompt_url(book["id"], chapter.id)

    await _put_prompt(http_client, owner_token, book["id"], chapter.id, "Still here.")

    resp = await http_client.request(
        method,
        url,
        headers=_auth_header(owner_token),
        json={"system_prompt": "should not be accepted"},
    )
    assert resp.status_code == 405, resp.text

    survivor = await _get_prompt(http_client, owner_token, book["id"], chapter.id)
    assert survivor.system_prompt == "Still here."


# ---------------------------------------------------------------------------
# DoD-15 — a malformed PUT body is a validation error and stores nothing
# ---------------------------------------------------------------------------


# DoD-15 (the frozen request DTO: `system_prompt` is required with no default):
# a body missing the prompt field is refused as a validation error, and the
# caller's prompt is still unwritten afterwards.
async def test_malformed_put_body_is_refused_and_stores_nothing__DoD15(http_client):
    owner, owner_token = await _seed_author("rosa")
    book = await _create_book(http_client, owner_token)
    chapter = await _seed_chapter_row(book["id"])
    url = _prompt_url(book["id"], chapter.id)
    h = _auth_header(owner_token)

    assert (await http_client.put(url, headers=h, json={})).status_code == 422
    assert (
        await http_client.put(url, headers=h, json={"prompt": "wrong field name"})
    ).status_code == 422

    after = await _get_prompt(http_client, owner_token, book["id"], chapter.id)
    assert after.system_prompt == ""
    assert after.modified_at is None
    assert await prompts_db.get_by_chapter_and_user(chapter.id, owner.id) is None
