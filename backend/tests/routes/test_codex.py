"""End-to-end tests for the codex HTTP surface (feature 013, step 003).

Exercised in-process against the real `app.main.app` via the `http_client`
fixture (httpx `ASGITransport`, no live server, no network). The app's startup
lifespan runs against a throwaway temp DB; each test seeds its own users, books
and members on the same process-global engine the app uses (schema built with
`init_db`, readiness flipped with `set_db_ready(True)`), mirroring
tests/routes/test_chats.py.

Bound to the frozen skeleton (status.md -> Skeleton -> Step 003), router
`app.routes.codex` with prefix "/api/books", every endpoint gated by
`Depends(authz.book_access)` and never declaring `book_id`:
    POST /{book_id}/codex             -> 201 CodexEntryResponse
    GET  /{book_id}/codex             -> 200 CodexEntryListResponse
                                         (query params: kind / q / include_archived)
    GET  /{book_id}/codex/{entry_id}  -> 200 CodexEntryResponse
    PUT  /{book_id}/codex/{entry_id}  -> 200 CodexEntryResponse
and the DTOs of `app.models.schemas.codex`.

Error wire shapes, per the step spec + skeleton record:
    - a codex service refusal answers `{"detail": {"reason": <wire value>,
      "message": <text>}}` with status 404 (entry-not-found), 400
      (name-required / name-not-allowed / entry-archived), 409
      (stale-modified-at) or 403 (proposal-mode-unsupported);
    - the authorization denial answers 403 with a **plain string** detail --
      same status, different detail body.

Expected values come from the SPEC ONLY -- the step DoD (DoD-1..DoD-14), the
step Interface intent, `003.context.md`, the feature `context.md` decisions and
the cited UC-### / US-###.AC-# ids -- never from implementation internals.

Async tests use asyncio_mode = "auto".
"""

import datetime

from app.db import book_members, books, codex_entries, users
from app.db.engine import init_db, set_db_ready
from app.models.book import Book, BookState, CollaborationMode, Visibility
from app.models.book_member import BookMember, MemberRole
from app.models.schemas.codex import CodexEntryListResponse, CodexEntryResponse
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


# --- step-003 additions (no `_seed_public_book` exists in test_chats.py) ----


async def _seed_public_book(owner_id: int) -> Book:
    """A book anyone logged in can see -- DoD-13's fixture."""
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


async def _seed_proposal_book(owner_id: int) -> Book:
    """A private book in `proposal` collaboration mode -- DoD-11's fixture."""
    return await books.create(
        Book(
            title="A Proposal Book",
            description="d",
            owner_id=owner_id,
            collaboration_mode=CollaborationMode.proposal,
            visibility=Visibility.private,
            state=BookState.active,
            system_prompt="",
            active_notes="",
        )
    )


# ---------------------------------------------------------------------------
# Wire helpers
# ---------------------------------------------------------------------------


def _codex_url(book_id: int) -> str:
    return f"/api/books/{book_id}/codex"


def _parse_dt(value: str) -> datetime.datetime:
    """Parse a wire timestamp, normalized to naive UTC so aware and naive
    serializations of the same instant compare on equal footing."""
    parsed = datetime.datetime.fromisoformat(value)
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(datetime.timezone.utc).replace(tzinfo=None)
    return parsed


async def _create_entry(
    http_client, token: str, book_id: int, **body
) -> dict:
    payload = {"kind": "character", "name": "Aragorn", "body": "a ranger", **body}
    resp = await http_client.post(
        _codex_url(book_id), headers=_auth_header(token), json=payload
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _archive_entry(entry_id: str) -> None:
    """Flip `archived` straight through the db layer -- this feature exposes no
    archive route (UC-072 belongs to `017.codex-archive-restore`)."""
    row = await codex_entries.get_by_id(int(entry_id))
    assert row is not None
    row.archived = True
    await codex_entries.update(row)


# ---------------------------------------------------------------------------
# DoD-1 — POST a valid character returns 201 and the entry DTO with string ids
# ---------------------------------------------------------------------------


# DoD-1 (UC-069 / US-078.AC-1): POST with a valid character payload answers 201
# with a body that validates as the entry response DTO, whose ids are strings.
async def test_post_character_returns_201_entry_dto__DoD1_US078_AC1(http_client):
    author, token = await _seed_author("alice")
    book = await _seed_private_book(author.id)

    resp = await http_client.post(
        _codex_url(book.id),
        headers=_auth_header(token),
        json={"kind": "character", "name": "Aragorn", "body": "a ranger"},
    )

    assert resp.status_code == 201, resp.text
    created = resp.json()
    CodexEntryResponse.model_validate(created)

    assert created["kind"] == "character"
    assert created["name"] == "Aragorn"
    assert created["body"] == "a ranger"
    assert created["archived"] is False
    assert type(created["id"]) is str
    assert created["book_id"] == str(book.id)
    assert created["author_id"] == str(author.id)


# ---------------------------------------------------------------------------
# DoD-2 — a fact carrying a name is refused 400 name-not-allowed
# ---------------------------------------------------------------------------


# DoD-2 (US-078.AC-2): a fact has no name; POSTing one answers 400 with the
# name-not-allowed reason in the detail body.
async def test_post_fact_with_name_is_400_name_not_allowed__DoD2_US078_AC2(
    http_client,
):
    author, token = await _seed_author("factist")
    book = await _seed_private_book(author.id)

    resp = await http_client.post(
        _codex_url(book.id),
        headers=_auth_header(token),
        json={"kind": "fact", "name": "Not allowed", "body": "a recorded fact"},
    )

    assert resp.status_code == 400, resp.text
    assert resp.json()["detail"]["reason"] == "name-not-allowed"


# ---------------------------------------------------------------------------
# DoD-3 — a character with no name is refused 400 name-required
# ---------------------------------------------------------------------------


# DoD-3 (US-078.AC-1): a character requires a non-blank name; omitting it -- and
# supplying a whitespace-only one, which counts as absent -- answers 400 with the
# name-required reason.
async def test_post_character_without_name_is_400_name_required__DoD3_US078_AC1(
    http_client,
):
    author, token = await _seed_author("namer")
    book = await _seed_private_book(author.id)

    omitted = await http_client.post(
        _codex_url(book.id),
        headers=_auth_header(token),
        json={"kind": "character", "body": "a ranger"},
    )
    assert omitted.status_code == 400, omitted.text
    assert omitted.json()["detail"]["reason"] == "name-required"

    blank = await http_client.post(
        _codex_url(book.id),
        headers=_auth_header(token),
        json={"kind": "character", "name": "   ", "body": "a ranger"},
    )
    assert blank.status_code == 400, blank.text
    assert blank.json()["detail"]["reason"] == "name-required"


# ---------------------------------------------------------------------------
# DoD-4 — the `kind` query param narrows the list; omitting it returns all kinds
# ---------------------------------------------------------------------------


# DoD-4 (UC-071 / US-080.AC-1): GET list with `kind` returns only entries of that
# kind; with the parameter omitted every kind comes back.
async def test_list_filters_by_kind_and_returns_all_when_omitted__DoD4_US080_AC1(
    http_client,
):
    author, token = await _seed_author("lister")
    book = await _seed_private_book(author.id)
    await _create_entry(http_client, token, book.id)
    await _create_entry(
        http_client, token, book.id, kind="location", name="Rivendell", body="a valley"
    )
    await _create_entry(
        http_client, token, book.id, kind="fact", name=None, body="the Ring was forged"
    )

    characters = await http_client.get(
        f"{_codex_url(book.id)}?kind=character", headers=_auth_header(token)
    )
    assert characters.status_code == 200, characters.text
    CodexEntryListResponse.model_validate(characters.json())
    assert [e["name"] for e in characters.json()["items"]] == ["Aragorn"]
    assert {e["kind"] for e in characters.json()["items"]} == {"character"}

    locations = await http_client.get(
        f"{_codex_url(book.id)}?kind=location", headers=_auth_header(token)
    )
    assert locations.status_code == 200
    assert [e["name"] for e in locations.json()["items"]] == ["Rivendell"]

    facts = await http_client.get(
        f"{_codex_url(book.id)}?kind=fact", headers=_auth_header(token)
    )
    assert facts.status_code == 200
    assert [e["kind"] for e in facts.json()["items"]] == ["fact"]

    everything = await http_client.get(
        _codex_url(book.id), headers=_auth_header(token)
    )
    assert everything.status_code == 200
    CodexEntryListResponse.model_validate(everything.json())
    assert {e["kind"] for e in everything.json()["items"]} == {
        "character",
        "location",
        "fact",
    }
    assert len(everything.json()["items"]) == 3


# ---------------------------------------------------------------------------
# DoD-5 — the `q` needle matches name or body, case-insensitively
# ---------------------------------------------------------------------------


# DoD-5 (US-080.AC-1): GET list with `q` returns only entries whose name OR body
# contains the needle, case-insensitively.
async def test_list_q_matches_name_or_body_case_insensitively__DoD5_US080_AC1(
    http_client,
):
    author, token = await _seed_author("seeker")
    book = await _seed_private_book(author.id)
    await _create_entry(
        http_client, token, book.id, name="Aragorn", body="a ranger of the north"
    )
    await _create_entry(
        http_client,
        token,
        book.id,
        kind="location",
        name="Rivendell",
        body="a hidden valley refuge",
    )
    await _create_entry(
        http_client,
        token,
        book.id,
        kind="fact",
        name=None,
        body="The Ring was forged in Mount Doom",
    )

    # Matched on `name`, needle in a different case than the stored value.
    by_name = await http_client.get(
        f"{_codex_url(book.id)}?q=ARAGORN", headers=_auth_header(token)
    )
    assert by_name.status_code == 200, by_name.text
    CodexEntryListResponse.model_validate(by_name.json())
    assert [e["name"] for e in by_name.json()["items"]] == ["Aragorn"]

    # Matched on `body`, again case-insensitively.
    by_body = await http_client.get(
        f"{_codex_url(book.id)}?q=HIDDEN valley", headers=_auth_header(token)
    )
    assert by_body.status_code == 200
    assert [e["name"] for e in by_body.json()["items"]] == ["Rivendell"]

    # A null-named fact is still matched on its body alone.
    null_named = await http_client.get(
        f"{_codex_url(book.id)}?q=mount doom", headers=_auth_header(token)
    )
    assert null_named.status_code == 200
    items = null_named.json()["items"]
    assert len(items) == 1
    assert items[0]["kind"] == "fact"
    assert items[0]["name"] is None

    # A needle matching nothing narrows to the empty list.
    nothing = await http_client.get(
        f"{_codex_url(book.id)}?q=zzz-nothing-here", headers=_auth_header(token)
    )
    assert nothing.status_code == 200
    assert nothing.json()["items"] == []


# ---------------------------------------------------------------------------
# DoD-6 — archived excluded by default, included when the flag is set
# ---------------------------------------------------------------------------


# DoD-6 (UC-071): GET list omits archived entries by default and includes them
# when `include_archived` is set.
async def test_list_excludes_archived_unless_flag_set__DoD6_UC071(http_client):
    author, token = await _seed_author("archivist")
    book = await _seed_private_book(author.id)
    active = await _create_entry(http_client, token, book.id, name="Active")
    retired = await _create_entry(http_client, token, book.id, name="Retired")
    await _archive_entry(retired["id"])

    default = await http_client.get(_codex_url(book.id), headers=_auth_header(token))
    assert default.status_code == 200, default.text
    CodexEntryListResponse.model_validate(default.json())
    assert [e["id"] for e in default.json()["items"]] == [active["id"]]

    included = await http_client.get(
        f"{_codex_url(book.id)}?include_archived=true", headers=_auth_header(token)
    )
    assert included.status_code == 200
    CodexEntryListResponse.model_validate(included.json())
    ids = [e["id"] for e in included.json()["items"]]
    assert active["id"] in ids
    assert retired["id"] in ids

    explicitly_false = await http_client.get(
        f"{_codex_url(book.id)}?include_archived=false", headers=_auth_header(token)
    )
    assert explicitly_false.status_code == 200
    assert [e["id"] for e in explicitly_false.json()["items"]] == [active["id"]]


# ---------------------------------------------------------------------------
# DoD-7 — GET one; unknown id and another book's entry both 404
# ---------------------------------------------------------------------------


# DoD-7 (US-085.AC-1): GET one returns the entry; an unknown entry id and an id
# belonging to a different book both answer 404 -- another book's content is
# never returned and its existence is not disclosed.
async def test_get_one_and_404s__DoD7_US085_AC1(http_client):
    author, token = await _seed_author("fetcher")
    book = await _seed_private_book(author.id)
    other_book = await _seed_private_book(author.id)
    entry = await _create_entry(http_client, token, book.id, name="Findable")
    foreign = await _create_entry(
        http_client, token, other_book.id, name="Elsewhere"
    )

    found = await http_client.get(
        f"{_codex_url(book.id)}/{entry['id']}", headers=_auth_header(token)
    )
    assert found.status_code == 200, found.text
    CodexEntryResponse.model_validate(found.json())
    assert found.json()["id"] == entry["id"]
    assert found.json()["name"] == "Findable"
    assert found.json()["book_id"] == str(book.id)

    unknown = await http_client.get(
        f"{_codex_url(book.id)}/99999999", headers=_auth_header(token)
    )
    assert unknown.status_code == 404, unknown.text
    assert unknown.json()["detail"]["reason"] == "entry-not-found"

    cross_book = await http_client.get(
        f"{_codex_url(book.id)}/{foreign['id']}", headers=_auth_header(token)
    )
    assert cross_book.status_code == 404, cross_book.text
    assert cross_book.json()["detail"]["reason"] == "entry-not-found"


# ---------------------------------------------------------------------------
# DoD-8 — PUT with the current modified_at applies the edit, bumps modified_at
# ---------------------------------------------------------------------------


# DoD-8 (UC-070 / US-079.AC-1): PUT carrying the entry's current `modified_at`
# applies the edit and returns the updated DTO, whose `modified_at` is LATER than
# the one sent.
async def test_put_applies_edit_and_bumps_modified_at__DoD8_US079_AC1(http_client):
    author, token = await _seed_author("editor")
    book = await _seed_private_book(author.id)
    created = await _create_entry(
        http_client, token, book.id, name="Old Name", body="old body"
    )

    resp = await http_client.put(
        f"{_codex_url(book.id)}/{created['id']}",
        headers=_auth_header(token),
        json={
            "name": "New Name",
            "body": "new body",
            "expected_modified_at": created["modified_at"],
        },
    )

    assert resp.status_code == 200, resp.text
    updated = resp.json()
    CodexEntryResponse.model_validate(updated)
    assert updated["id"] == created["id"]
    assert updated["name"] == "New Name"
    assert updated["body"] == "new body"
    assert _parse_dt(updated["modified_at"]) > _parse_dt(created["modified_at"])

    # The edit is what a subsequent read sees.
    reread = await http_client.get(
        f"{_codex_url(book.id)}/{created['id']}", headers=_auth_header(token)
    )
    assert reread.status_code == 200
    assert reread.json()["name"] == "New Name"
    assert reread.json()["body"] == "new body"


# ---------------------------------------------------------------------------
# DoD-9 — a stale modified_at is refused 409 and changes nothing
# ---------------------------------------------------------------------------


# DoD-9 (frontend-workspace.md -> stale buffer): PUT carrying an out-of-date
# `modified_at` answers 409 with the stale reason and leaves the entry unchanged.
async def test_put_with_stale_modified_at_is_409_and_no_op__DoD9_UC070(http_client):
    author, token = await _seed_author("staler")
    book = await _seed_private_book(author.id)
    created = await _create_entry(
        http_client, token, book.id, name="Untouched", body="original body"
    )

    resp = await http_client.put(
        f"{_codex_url(book.id)}/{created['id']}",
        headers=_auth_header(token),
        json={
            "name": "Overwritten",
            "body": "overwritten body",
            "expected_modified_at": "2020-01-01T00:00:00",
        },
    )

    assert resp.status_code == 409, resp.text
    assert resp.json()["detail"]["reason"] == "stale-modified-at"

    # The entry is unchanged -- content and version token both.
    reread = await http_client.get(
        f"{_codex_url(book.id)}/{created['id']}", headers=_auth_header(token)
    )
    assert reread.status_code == 200, reread.text
    CodexEntryResponse.model_validate(reread.json())
    assert reread.json()["name"] == "Untouched"
    assert reread.json()["body"] == "original body"
    assert _parse_dt(reread.json()["modified_at"]) == _parse_dt(
        created["modified_at"]
    )


# ---------------------------------------------------------------------------
# DoD-10 — an archived entry is read-only: PUT answers 400
# ---------------------------------------------------------------------------


# DoD-10 (UC-070 precondition): an archived entry cannot be edited -- PUT answers
# 400 with the archived reason, even when the `modified_at` token is current.
async def test_put_on_archived_entry_is_400__DoD10_UC070(http_client):
    author, token = await _seed_author("frozen")
    book = await _seed_private_book(author.id)
    created = await _create_entry(
        http_client, token, book.id, name="Retired", body="put away"
    )
    await _archive_entry(created["id"])

    resp = await http_client.put(
        f"{_codex_url(book.id)}/{created['id']}",
        headers=_auth_header(token),
        json={
            "name": "Revived",
            "body": "new body",
            "expected_modified_at": created["modified_at"],
        },
    )

    assert resp.status_code == 400, resp.text
    assert resp.json()["detail"]["reason"] == "entry-archived"


# ---------------------------------------------------------------------------
# DoD-11 — proposal mode refuses a co-author's writes with 403; the owner's apply
# ---------------------------------------------------------------------------


# DoD-11 (context.md decision 3; US-079.AC-2 knowingly unmet): in a
# proposal-mode book a co-author's POST and PUT answer 403 carrying the
# proposal-unsupported reason, while the owner's writes still apply.
async def test_proposal_mode_refuses_co_author_writes__DoD11_US079_AC2(http_client):
    owner, owner_token = await _seed_author("proposal_owner")
    co_author, co_token = await _seed_author("proposal_co")
    book = await _seed_proposal_book(owner.id)
    await _add_co_author(book.id, co_author.id)

    # The owner's create applies.
    created = await http_client.post(
        _codex_url(book.id),
        headers=_auth_header(owner_token),
        json={"kind": "character", "name": "Owned", "body": "owner body"},
    )
    assert created.status_code == 201, created.text
    entry = created.json()

    # The co-author's create is refused.
    co_create = await http_client.post(
        _codex_url(book.id),
        headers=_auth_header(co_token),
        json={"kind": "character", "name": "Proposed", "body": "co-author body"},
    )
    assert co_create.status_code == 403, co_create.text
    assert co_create.json()["detail"]["reason"] == "proposal-mode-unsupported"

    # The co-author's edit is refused the same way, and changes nothing.
    co_edit = await http_client.put(
        f"{_codex_url(book.id)}/{entry['id']}",
        headers=_auth_header(co_token),
        json={
            "name": "Proposed edit",
            "body": "co-author edit",
            "expected_modified_at": entry["modified_at"],
        },
    )
    assert co_edit.status_code == 403, co_edit.text
    assert co_edit.json()["detail"]["reason"] == "proposal-mode-unsupported"

    unchanged = await http_client.get(
        f"{_codex_url(book.id)}/{entry['id']}", headers=_auth_header(owner_token)
    )
    assert unchanged.status_code == 200
    assert unchanged.json()["name"] == "Owned"
    assert unchanged.json()["body"] == "owner body"

    # The owner's edit still applies.
    owner_edit = await http_client.put(
        f"{_codex_url(book.id)}/{entry['id']}",
        headers=_auth_header(owner_token),
        json={
            "name": "Owned again",
            "body": "owner second body",
            "expected_modified_at": entry["modified_at"],
        },
    )
    assert owner_edit.status_code == 200, owner_edit.text
    CodexEntryResponse.model_validate(owner_edit.json())
    assert owner_edit.json()["name"] == "Owned again"
    assert owner_edit.json()["body"] == "owner second body"


# ---------------------------------------------------------------------------
# DoD-12 — a non-member of a private book gets 404 from every route
# ---------------------------------------------------------------------------


# DoD-12 (US-085.AC-1; authorization.md): a logged-in caller who is not a member
# of the private book gets 404 from every codex route (existence hidden by
# book_access) -- the canonical shape of
# test_chats.py:test_non_member_gets_404_from_every_route__DoD9.
async def test_non_member_gets_404_from_every_route__DoD12_US085_AC1(http_client):
    owner, _owner_token = await _seed_author("codex_owner")
    _stranger, stranger_token = await _seed_author("codex_stranger")
    book = await _seed_private_book(owner.id)
    h = _auth_header(stranger_token)
    base = _codex_url(book.id)
    create_body = {"kind": "character", "name": "x", "body": "b"}
    update_body = {"name": "x", "body": "b", "expected_modified_at": None}

    assert (
        await http_client.post(base, headers=h, json=create_body)
    ).status_code == 404
    assert (await http_client.get(base, headers=h)).status_code == 404
    assert (await http_client.get(f"{base}/123", headers=h)).status_code == 404
    assert (
        await http_client.put(f"{base}/123", headers=h, json=update_body)
    ).status_code == 404


# ---------------------------------------------------------------------------
# DoD-13 — a reader of a public book gets 403 from every route
# ---------------------------------------------------------------------------


# DoD-13 (US-085.AC-1): a logged-in non-member reader of a PUBLIC book gets 403
# from every codex route -- the book is visible, the codex is not. This is the
# authorization denial, whose detail is a plain string rather than the codex
# reason object.
async def test_public_book_reader_gets_403_from_every_route__DoD13_US085_AC1(
    http_client,
):
    owner, _owner_token = await _seed_author("public_owner")
    _reader, reader_token = await _seed_author("public_reader")
    book = await _seed_public_book(owner.id)
    h = _auth_header(reader_token)
    base = _codex_url(book.id)
    create_body = {"kind": "character", "name": "x", "body": "b"}
    update_body = {"name": "x", "body": "b", "expected_modified_at": None}

    responses = [
        await http_client.post(base, headers=h, json=create_body),
        await http_client.get(base, headers=h),
        await http_client.get(f"{base}/123", headers=h),
        await http_client.put(f"{base}/123", headers=h, json=update_body),
    ]

    for resp in responses:
        assert resp.status_code == 403, resp.text
        # The authorization refusal, not the proposal-mode one: its detail is a
        # plain string, never the {"reason": ..., "message": ...} object.
        assert not isinstance(resp.json()["detail"], dict)


# ---------------------------------------------------------------------------
# DoD-14 — no bearer token gets 401 from every route
# ---------------------------------------------------------------------------


# DoD-14 (authorization.md -> Failure modes): an unauthenticated request gets 401
# from every codex route, before any book or entry is resolved.
async def test_missing_token_gets_401_from_every_route__DoD14(http_client):
    owner, _owner_token = await _seed_author("anon_owner")
    book = await _seed_private_book(owner.id)
    base = _codex_url(book.id)
    create_body = {"kind": "character", "name": "x", "body": "b"}
    update_body = {"name": "x", "body": "b", "expected_modified_at": None}

    assert (await http_client.post(base, json=create_body)).status_code == 401
    assert (await http_client.get(base)).status_code == 401
    assert (await http_client.get(f"{base}/123")).status_code == 401
    assert (
        await http_client.put(f"{base}/123", json=update_body)
    ).status_code == 401
