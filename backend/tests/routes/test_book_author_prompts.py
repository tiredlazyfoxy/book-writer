"""End-to-end tests for the per-author system-prompt HTTP surface (feature 021, step 003).

Exercised in-process against the real `app.main.app` via the `http_client`
fixture (httpx `ASGITransport`, no live server, no network). The app's startup
lifespan runs against a throwaway temp DB; each test seeds its own users, books,
members and prompt rows on the same process-global engine the app uses (schema
built with `init_db`, readiness flipped with `set_db_ready(True)`), mirroring
tests/routes/test_chats.py.

Bound to the frozen skeleton (status.md -> Skeleton -> Step 003), router
`app.routes.book_author_prompts` with prefix "/api/books", both endpoints gated
by `Depends(authz.book_access)` and neither re-declaring `book_id`:
    GET /{book_id}/system-prompt  -> 200 BookAuthorPromptResponse
    PUT /{book_id}/system-prompt  -> 200 BookAuthorPromptResponse
and the step-002 DTOs of `app.models.schemas.book_author_prompts`.

Wire contract (context.md -> "The wire contract"): the response body carries
`book_id` (snowflake as a string), `system_prompt` (`""` when the author has no
prompt) and `modified_at` (ISO timestamp or `null` when no row exists yet), and
**no** `user_id`. The PUT request body is `{"system_prompt": <str>}`. A missing
row is a 200 with an empty prompt, never a 404. PUT answers 200 on both the
create and the update path.

Status taxonomy (context.md, authorization.md -> "Failure modes"): no token ->
401; no relationship to a **private** book -> 404 (existence hiding, produced
upstream by the dependency); a logged-in non-member of a **public** book -> 403;
a member acting on their own prompt -> 200.

Expected values come from the SPEC ONLY -- the step DoD (DoD-1..DoD-10), the step
Interface intent, `003.context.md` and the feature `context.md` decisions --
never from implementation internals.

Async tests use asyncio_mode = "auto".
"""

import datetime

from app.db import book_author_prompts as prompts_db
from app.db import book_members, books, users
from app.db.engine import init_db, set_db_ready
from app.models.book import Book, BookState, CollaborationMode, Visibility
from app.models.book_author_prompt import BookAuthorPrompt
from app.models.book_member import BookMember, MemberRole
from app.models.schemas.book_author_prompts import BookAuthorPromptResponse
from app.models.user import User, UserRole
from app.services import auth

# ---------------------------------------------------------------------------
# Seed helpers -- copied verbatim from tests/routes/test_chats.py (auth is real)
# ---------------------------------------------------------------------------


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _seed_user(username: str, role: UserRole = UserRole.author) -> User:
    await init_db()
    user = await users.create(
        User(
            username=username,
            role=role,
            pwdhash=auth.hash_password("password123"),
            jwt_signing_key=auth.generate_signing_key(),
            last_key_update=_now(),
        )
    )
    set_db_ready(True)
    return user


async def _seed_author(username: str) -> tuple[User, str]:
    user = await _seed_user(username)
    return user, auth.create_access_token(user)


async def _seed_private_book(owner_id: int) -> Book:
    return await books.create(
        Book(
            title="A Book",
            description="d",
            owner_id=owner_id,
            collaboration_mode=CollaborationMode.free,
            visibility=Visibility.private,
            state=BookState.active,
            system_prompt="",
            active_notes="",
        )
    )


async def _add_co_author(book_id: int, user_id: int) -> None:
    await book_members.create(
        BookMember(
            book_id=book_id,
            user_id=user_id,
            role=MemberRole.co_author,
            created_at=_now(),
        )
    )


# --- step-003 addition (no `_seed_public_book` exists in test_chats.py) -----


async def _seed_public_book(owner_id: int) -> Book:
    """A book anyone logged in can see -- DoD-7's fixture."""
    return await books.create(
        Book(
            title="A Public Book",
            description="d",
            owner_id=owner_id,
            collaboration_mode=CollaborationMode.free,
            visibility=Visibility.public,
            state=BookState.active,
            system_prompt="",
            active_notes="",
        )
    )


# ---------------------------------------------------------------------------
# Local helpers
# ---------------------------------------------------------------------------


def _prompt_url(book_id: int) -> str:
    return f"/api/books/{book_id}/system-prompt"


async def _seed_prompt_row(book_id: int, user_id: int, text: str) -> BookAuthorPrompt:
    """Seed a stored prompt directly through the db layer (no route involved)."""
    stamp = _now()
    return await prompts_db.create(
        BookAuthorPrompt(
            book_id=book_id,
            user_id=user_id,
            system_prompt=text,
            created_at=stamp,
            modified_at=stamp,
        )
    )


async def _get_prompt(http_client, token: str, book_id: int) -> BookAuthorPromptResponse:
    resp = await http_client.get(_prompt_url(book_id), headers=_auth_header(token))
    assert resp.status_code == 200, resp.text
    return BookAuthorPromptResponse.model_validate(resp.json())


async def _put_prompt(
    http_client, token: str, book_id: int, text: str
) -> BookAuthorPromptResponse:
    resp = await http_client.put(
        _prompt_url(book_id),
        headers=_auth_header(token),
        json={"system_prompt": text},
    )
    assert resp.status_code == 200, resp.text
    return BookAuthorPromptResponse.model_validate(resp.json())


# ---------------------------------------------------------------------------
# DoD-1 — GET returns 200 and the caller's own stored prompt
# ---------------------------------------------------------------------------


# DoD-1: GET answers 200 with the caller's own stored text, the book id as a
# string, a real modified timestamp, and no user identifier on the wire
# (context.md -> "The wire contract").
async def test_get_returns_callers_own_stored_prompt__DoD1(http_client):
    owner, owner_token = await _seed_author("prompt_owner")
    co_author, _co_token = await _seed_author("prompt_co_author")
    book = await _seed_private_book(owner.id)
    await _add_co_author(book.id, co_author.id)

    await _seed_prompt_row(book.id, owner.id, "Write like the owner.")
    await _seed_prompt_row(book.id, co_author.id, "Write like the co-author.")

    resp = await http_client.get(
        _prompt_url(book.id), headers=_auth_header(owner_token)
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert isinstance(body["book_id"], str)
    assert "user_id" not in body

    prompt = BookAuthorPromptResponse.model_validate(body)
    assert prompt.book_id == str(book.id)
    assert prompt.system_prompt == "Write like the owner."
    assert prompt.modified_at is not None


# ---------------------------------------------------------------------------
# DoD-2 — no row yet is a 200 with an empty prompt, never a 404
# ---------------------------------------------------------------------------


# DoD-2 (context.md -> "A missing row is a 200 with an empty prompt, never a
# 404"): a member who has never written a prompt reads 200 / "" / null.
async def test_get_without_a_row_is_200_empty_and_null__DoD2(http_client):
    owner, owner_token = await _seed_author("empty_owner")
    co_author, co_token = await _seed_author("empty_co_author")
    book = await _seed_private_book(owner.id)
    await _add_co_author(book.id, co_author.id)

    for token in (owner_token, co_token):
        resp = await http_client.get(
            _prompt_url(book.id), headers=_auth_header(token)
        )
        assert resp.status_code == 200, resp.text
        prompt = BookAuthorPromptResponse.model_validate(resp.json())
        assert prompt.book_id == str(book.id)
        assert prompt.system_prompt == ""
        assert prompt.modified_at is None


# ---------------------------------------------------------------------------
# DoD-3 — PUT stores the text, echoes it, and a following GET agrees
# ---------------------------------------------------------------------------


# DoD-3 (context.md -> decision 6: PUT is the upsert and answers 200 on the
# create path): the response echoes what was stored and a following GET returns
# the same value.
async def test_put_stores_text_and_get_returns_it__DoD3(http_client):
    owner, owner_token = await _seed_author("writer_owner")
    book = await _seed_private_book(owner.id)

    resp = await http_client.put(
        _prompt_url(book.id),
        headers=_auth_header(owner_token),
        json={"system_prompt": "Keep the prose terse."},
    )
    assert resp.status_code == 200, resp.text
    written = BookAuthorPromptResponse.model_validate(resp.json())
    assert written.book_id == str(book.id)
    assert written.system_prompt == "Keep the prose terse."
    assert written.modified_at is not None

    read_back = await _get_prompt(http_client, owner_token, book.id)
    assert read_back.system_prompt == "Keep the prose terse."
    assert read_back.book_id == str(book.id)
    assert read_back.modified_at is not None


# ---------------------------------------------------------------------------
# DoD-4 — two members, two prompts, each reads only their own
# ---------------------------------------------------------------------------


# DoD-4 (context.md -> Goal; this is the behaviour that replaces UC-093's single
# book-wide prompt): two members of one book PUT different prompts and each GET
# returns their own text, never the other's.
async def test_two_members_each_read_their_own_prompt__DoD4(http_client):
    owner, owner_token = await _seed_author("per_author_owner")
    co_author, co_token = await _seed_author("per_author_co_author")
    book = await _seed_private_book(owner.id)
    await _add_co_author(book.id, co_author.id)

    await _put_prompt(http_client, owner_token, book.id, "OWNER VOICE")
    await _put_prompt(http_client, co_token, book.id, "CO-AUTHOR VOICE")

    owner_read = await _get_prompt(http_client, owner_token, book.id)
    co_read = await _get_prompt(http_client, co_token, book.id)

    assert owner_read.system_prompt == "OWNER VOICE"
    assert co_read.system_prompt == "CO-AUTHOR VOICE"
    assert owner_read.book_id == co_read.book_id == str(book.id)


# ---------------------------------------------------------------------------
# DoD-5 — a second PUT updates rather than duplicating
# ---------------------------------------------------------------------------


# DoD-5 (context.md -> decision 6: PUT creates when absent and updates when
# present, and 201 "would be a lie on the second call"): the value changes and
# the response still describes exactly one prompt.
async def test_second_put_updates_rather_than_duplicating__DoD5(http_client):
    owner, owner_token = await _seed_author("update_owner")
    book = await _seed_private_book(owner.id)

    first = await _put_prompt(http_client, owner_token, book.id, "First voice.")

    resp = await http_client.put(
        _prompt_url(book.id),
        headers=_auth_header(owner_token),
        json={"system_prompt": "Second voice."},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert isinstance(body, dict)
    second = BookAuthorPromptResponse.model_validate(body)

    assert second.system_prompt == "Second voice."
    assert second.book_id == str(book.id)
    assert second.modified_at is not None
    assert first.modified_at is not None
    assert second.modified_at >= first.modified_at

    read_back = await _get_prompt(http_client, owner_token, book.id)
    assert read_back.system_prompt == "Second voice."
    assert read_back.book_id == str(book.id)


# ---------------------------------------------------------------------------
# DoD-6 — a non-member of a private book gets 404 from both verbs
# ---------------------------------------------------------------------------


# DoD-6 (authorization.md -> "Failure modes"; the shape of
# test_chats.py::test_non_member_gets_404_from_every_route__DoD9): existence is
# hidden by the dependency, so both verbs answer 404.
async def test_non_member_of_private_book_gets_404_from_both_verbs__DoD6(http_client):
    owner, _owner_token = await _seed_author("private_owner")
    _stranger, stranger_token = await _seed_author("private_stranger")
    book = await _seed_private_book(owner.id)
    h = _auth_header(stranger_token)
    url = _prompt_url(book.id)

    assert (await http_client.get(url, headers=h)).status_code == 404
    assert (
        await http_client.put(url, headers=h, json={"system_prompt": "sneaky"})
    ).status_code == 404


# ---------------------------------------------------------------------------
# DoD-7 — a logged-in non-member of a public book gets 403 from both verbs
# ---------------------------------------------------------------------------


# DoD-7 (context.md -> "A reader is refused with 403, not 404"): the reader can
# legitimately see the public book, so the refusal names the permission rather
# than hiding the book. Nothing is stored for them either.
async def test_reader_on_public_book_gets_403_from_both_verbs__DoD7(http_client):
    owner, owner_token = await _seed_author("public_owner")
    _reader, reader_token = await _seed_author("public_reader")
    book = await _seed_public_book(owner.id)
    h = _auth_header(reader_token)
    url = _prompt_url(book.id)

    assert (await http_client.get(url, headers=h)).status_code == 403
    assert (
        await http_client.put(url, headers=h, json={"system_prompt": "not mine"})
    ).status_code == 403

    # the refused write reached no storage: the owner's own prompt is untouched
    owner_read = await _get_prompt(http_client, owner_token, book.id)
    assert owner_read.system_prompt == ""
    assert owner_read.modified_at is None


# ---------------------------------------------------------------------------
# DoD-8 — no token is 401 from both verbs
# ---------------------------------------------------------------------------


# DoD-8 (context.md -> "The wire contract": no valid token -> 401, produced by
# the authentication dependency behind book_access).
async def test_missing_token_gets_401_from_both_verbs__DoD8(http_client):
    owner, _owner_token = await _seed_author("anon_owner")
    book = await _seed_private_book(owner.id)
    url = _prompt_url(book.id)

    assert (await http_client.get(url)).status_code == 401
    assert (
        await http_client.put(url, json={"system_prompt": "anonymous"})
    ).status_code == 401


# ---------------------------------------------------------------------------
# DoD-9 — the path answers no DELETE
# ---------------------------------------------------------------------------


# DoD-9 (context.md -> decision 6: "there is no DELETE"): a delete attempt is
# refused by the framework (405 Method Not Allowed) rather than silently
# accepted, and the stored prompt survives it.
async def test_delete_is_refused_by_the_framework__DoD9(http_client):
    owner, owner_token = await _seed_author("delete_owner")
    book = await _seed_private_book(owner.id)
    await _put_prompt(http_client, owner_token, book.id, "Still here.")

    resp = await http_client.delete(
        _prompt_url(book.id), headers=_auth_header(owner_token)
    )
    assert resp.status_code == 405, resp.text

    survivor = await _get_prompt(http_client, owner_token, book.id)
    assert survivor.system_prompt == "Still here."


# ---------------------------------------------------------------------------
# DoD-10 — a malformed PUT body is a validation error and stores nothing
# ---------------------------------------------------------------------------


# DoD-10 (skeleton record: the PUT body is `UpdateBookAuthorPromptRequest` with
# `system_prompt` required and no default): a body missing the prompt field is
# refused as a validation error, and the caller's prompt is still unwritten.
async def test_malformed_put_body_is_refused_and_stores_nothing__DoD10(http_client):
    owner, owner_token = await _seed_author("malformed_owner")
    book = await _seed_private_book(owner.id)
    h = _auth_header(owner_token)
    url = _prompt_url(book.id)

    assert (await http_client.put(url, headers=h, json={})).status_code == 422
    assert (
        await http_client.put(url, headers=h, json={"prompt": "wrong field name"})
    ).status_code == 422

    after = await _get_prompt(http_client, owner_token, book.id)
    assert after.system_prompt == ""
    assert after.modified_at is None
