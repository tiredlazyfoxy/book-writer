"""End-to-end tests for the four memo state verbs (026, step 005) -- route half.

Exercised in-process against the real `app.main.app` via the `http_client`
fixture (httpx `ASGITransport`, no live server, no network), mirroring
tests/routes/test_memos.py and tests/routes/test_memos_order.py. Auth is real: a
seeded user row plus a minted JWT.

Bound to the frozen skeleton (status.md -> Skeleton -> Step 005):
    POST /api/books/{book_id}/memos/{memo_id}/activate    -> 200 MemoResponse
    POST /api/books/{book_id}/memos/{memo_id}/deactivate  -> 200 MemoResponse
    POST /api/books/{book_id}/memos/{memo_id}/archive     -> 200 MemoResponse
    POST /api/books/{book_id}/memos/{memo_id}/restore     -> 200 MemoResponse
    -- all four take NO request body, none declares `status_code=`, and
       `memo_id` is the wire string, passed through unparsed.
    `_MEMO_ERROR_STATUS` is UNCHANGED at three entries (403 / 404 / 400):
    this step adds no status and, in particular, NO 409.

Expected values come from the SPEC ONLY -- `005.memo-state-axes.md`
(DoD-1..DoD-12), `005.context.md` ("The flag each verb writes", "The precedent
to copy -- Book, not the codex" and its two deliberate differences) and the
feature `context.md` ("The wire contract", the status taxonomy, decision 4's
archived-book carve-out, decision 5 "no 409", decision 6 "No DELETE") -- never
from implementation internals:

    - DoD-1  (US-127.AC-1): a deactivated memo is still returned by the plain
      GET;
    - DoD-2  (US-127.AC-2): it comes back with `active` false;
    - DoD-3  (US-127.AC-4): activate sets `active` true again;
    - DoD-4  (US-127.AC-5): deactivating the caller's ONLY active memo answers
      200 -- the empty active set is a legitimate end state;
    - DoD-5  (US-128.AC-1): an archived memo is absent from the default read and
      present in `?include_archived=true`;
    - DoD-6  (US-128.AC-2): a restored memo is appended LAST, at one past the
      current highest ordinal -- never at the slot it held;
    - DoD-9  (US-124.AC-1): every verb answers 404, indistinguishably, for an
      unknown / non-numeric / another author's / another book's memo;
    - DoD-10 (context.md, repeat state calls): a verb applied to a memo already
      in that state answers **200** with the row unchanged -- this route family
      deliberately does NOT copy `POST /api/books/{id}/archive`'s 409.
      "Unchanged" has no carve-out: restore on a memo that is NOT archived
      leaves `ordinal` alone too (append-at-max+1 is the archived-memo path,
      DoD-6);
    - DoD-11 (US-128.AC-3): there is no DELETE on any memo path (the framework
      answers 405) and no call removes a memo from the include-archived read;
    - DoD-12 (the archived-book carve-out): all four verbs answer 200 on a book
      whose state is `archived`.

DoD-7 (the archive gap) and DoD-8 (archive preserves `active`) are pinned at the
service layer, in tests/services/test_memos_state.py.

Async tests use asyncio_mode = "auto".
"""

import datetime
import json

from app.db import book_members, books, users
from app.db import memos as memos_db
from app.db.engine import init_db, set_db_ready
from app.models.book import Book, BookState, CollaborationMode, Visibility
from app.models.book_member import BookMember, MemberRole
from app.models.memo import Memo
from app.models.schemas.memos import MemoListResponse, MemoResponse
from app.models.user import User, UserRole
from app.services import auth

# The four verb path segments, in the order the step file declares them.
VERBS = ("activate", "deactivate", "archive", "restore")


# ---------------------------------------------------------------------------
# Seed helpers -- copied from tests/routes/test_memos_order.py (there is no
# shared factory module)
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


async def _seed_book(
    owner_id: int,
    visibility: Visibility = Visibility.private,
    state: BookState = BookState.active,
    title: str = "A Book",
) -> Book:
    return await books.create(
        Book(
            title=title,
            description="d",
            owner_id=owner_id,
            collaboration_mode=CollaborationMode.free,
            visibility=visibility,
            state=state,
            system_prompt="",
            active_notes="",
        )
    )


async def _seed_private_book(owner_id: int, title: str = "A Book") -> Book:
    return await _seed_book(owner_id, Visibility.private, BookState.active, title)


async def _add_co_author(book_id: int, user_id: int) -> None:
    await book_members.create(
        BookMember(
            book_id=book_id,
            user_id=user_id,
            role=MemberRole.co_author,
            created_at=_now(),
        )
    )


async def _seed_memo(
    book_id: int,
    user_id: int,
    body: str,
    ordinal: int,
    *,
    active: bool = True,
    archived: bool = False,
) -> Memo:
    """Seed a stored memo directly through the db layer (no route involved)."""
    stamp = _now()
    return await memos_db.create(
        Memo(
            book_id=book_id,
            user_id=user_id,
            body=body,
            ordinal=ordinal,
            active=active,
            archived=archived,
            created_at=stamp,
            modified_at=stamp,
        )
    )


# ---------------------------------------------------------------------------
# Local URL / call helpers
# ---------------------------------------------------------------------------


def _list_url(book_id: int) -> str:
    return f"/api/books/{book_id}/memos"


def _memo_url(book_id: int, memo_id: object) -> str:
    return f"/api/books/{book_id}/memos/{memo_id}"


def _verb_url(book_id: int, memo_id: object, verb: str) -> str:
    return f"/api/books/{book_id}/memos/{memo_id}/{verb}"


async def _call_verb(http_client, token: str, book_id: int, memo_id: object, verb: str):
    """POST one of the four state verbs -- deliberately with NO request body."""
    return await http_client.post(
        _verb_url(book_id, memo_id, verb), headers=_auth_header(token)
    )


async def _list_memos(
    http_client, token: str, book_id: int, *, include_archived: bool | None = None
) -> MemoListResponse:
    url = _list_url(book_id)
    if include_archived is not None:
        url = f"{url}?include_archived={'true' if include_archived else 'false'}"
    resp = await http_client.get(url, headers=_auth_header(token))
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert "items" in payload, payload
    return MemoListResponse.model_validate(payload)


async def _stored(memo_id: int) -> Memo:
    row = await memos_db.get_by_id(memo_id)
    assert row is not None
    return row


# ---------------------------------------------------------------------------
# DoD-1 (US-127.AC-1) -- a deactivated memo stays in the list
# ---------------------------------------------------------------------------


# DoD-1: `POST .../deactivate` answers 200 and the plain GET still returns the
# memo -- switching a memo off is not the archive axis and does not remove it.
async def test_deactivated_memo_still_appears_in_the_plain_get__DoD1(http_client):
    owner, token = await _seed_author("memo_state_owner_1")
    book = await _seed_private_book(owner.id)
    first = await _seed_memo(book.id, owner.id, "A", 1)
    second = await _seed_memo(book.id, owner.id, "B", 2)

    resp = await _call_verb(http_client, token, book.id, first.id, "deactivate")
    assert resp.status_code == 200, resp.text

    listed = await _list_memos(http_client, token, book.id)
    assert [item.id for item in listed.items] == [str(first.id), str(second.id)]


# ---------------------------------------------------------------------------
# DoD-2 (US-127.AC-2) -- the response carries `active` false
# ---------------------------------------------------------------------------


# DoD-2: the deactivate response is a MemoResponse with `active` false, string
# ids and no `user_id`; `archived`, `ordinal` and `body` are unchanged, and the
# following GET agrees.
async def test_deactivate_answers_200_with_active_false__DoD2(http_client):
    owner, token = await _seed_author("memo_state_owner_2")
    book = await _seed_private_book(owner.id)
    memo = await _seed_memo(book.id, owner.id, "a standing note", 7)

    resp = await _call_verb(http_client, token, book.id, memo.id, "deactivate")

    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert "user_id" not in payload, payload
    body = MemoResponse.model_validate(payload)
    assert body.id == str(memo.id)
    assert body.book_id == str(book.id)
    assert body.active is False
    assert body.archived is False
    assert body.ordinal == 7
    assert body.body == "a standing note"

    listed = await _list_memos(http_client, token, book.id)
    assert [item.active for item in listed.items] == [False]

    row = await _stored(memo.id)
    assert row.active is False
    assert row.archived is False
    assert row.ordinal == 7


# ---------------------------------------------------------------------------
# DoD-3 (US-127.AC-4) -- activate switches it back on
# ---------------------------------------------------------------------------


# DoD-3: `POST .../activate` on an inactive memo answers 200 with `active` true
# and leaves `archived`, `ordinal` and `body` alone.
async def test_activate_answers_200_with_active_true__DoD3(http_client):
    owner, token = await _seed_author("memo_state_owner_3")
    book = await _seed_private_book(owner.id)
    memo = await _seed_memo(book.id, owner.id, "switched off", 4, active=False)

    resp = await _call_verb(http_client, token, book.id, memo.id, "activate")

    assert resp.status_code == 200, resp.text
    body = MemoResponse.model_validate(resp.json())
    assert body.active is True
    assert body.archived is False
    assert body.ordinal == 4
    assert body.body == "switched off"

    listed = await _list_memos(http_client, token, book.id)
    assert [item.active for item in listed.items] == [True]


# ---------------------------------------------------------------------------
# DoD-4 (US-127.AC-5) -- deactivating the only active memo is allowed
# ---------------------------------------------------------------------------


# DoD-4: deactivating the caller's ONLY active memo answers 200. Nothing
# refuses: the empty active set is a legitimate end state and there is no
# book-level memos-off switch to consult.
async def test_deactivating_the_only_active_memo_answers_200__DoD4(http_client):
    owner, token = await _seed_author("memo_state_owner_4")
    book = await _seed_private_book(owner.id)
    only = await _seed_memo(book.id, owner.id, "the only one", 1)

    resp = await _call_verb(http_client, token, book.id, only.id, "deactivate")

    assert resp.status_code == 200, resp.text
    assert MemoResponse.model_validate(resp.json()).active is False

    listed = await _list_memos(http_client, token, book.id)
    assert [item.id for item in listed.items] == [str(only.id)]
    assert [item.active for item in listed.items] == [False]


# ---------------------------------------------------------------------------
# DoD-5 (US-128.AC-1) -- archive leaves the working list
# ---------------------------------------------------------------------------


# DoD-5: after `POST .../archive` the memo is absent from the default read and
# present, flagged `archived`, in the include-archived read.
async def test_archived_memo_is_absent_by_default_present_with_the_flag__DoD5(
    http_client,
):
    owner, token = await _seed_author("memo_state_owner_5")
    book = await _seed_private_book(owner.id)
    kept = await _seed_memo(book.id, owner.id, "A", 1)
    gone = await _seed_memo(book.id, owner.id, "B", 2)

    resp = await _call_verb(http_client, token, book.id, gone.id, "archive")
    assert resp.status_code == 200, resp.text
    assert MemoResponse.model_validate(resp.json()).archived is True

    live = await _list_memos(http_client, token, book.id)
    assert [item.id for item in live.items] == [str(kept.id)]

    everything = await _list_memos(http_client, token, book.id, include_archived=True)
    assert [item.id for item in everything.items] == [str(kept.id), str(gone.id)]
    by_id = {item.id: item for item in everything.items}
    assert by_id[str(gone.id)].archived is True
    assert by_id[str(gone.id)].body == "B"


# ---------------------------------------------------------------------------
# DoD-6 (US-128.AC-2) -- restore appends LAST
# ---------------------------------------------------------------------------


# DoD-6: the restored memo returns to the working list appended last, at one
# past the current highest ordinal. The fixture makes "old slot" and "appended
# last" different answers: the memo is archived from ordinal 2 while a live memo
# sits at 3, so an old-slot restore would read 2 and an append-last restore
# reads 4.
async def test_restore_appends_last_not_to_the_old_slot__DoD6(http_client):
    owner, token = await _seed_author("memo_state_owner_6")
    book = await _seed_private_book(owner.id)
    first = await _seed_memo(book.id, owner.id, "A", 1)
    middle = await _seed_memo(book.id, owner.id, "B", 2)
    last = await _seed_memo(book.id, owner.id, "C", 3)

    archived = await _call_verb(http_client, token, book.id, middle.id, "archive")
    assert archived.status_code == 200, archived.text

    resp = await _call_verb(http_client, token, book.id, middle.id, "restore")

    assert resp.status_code == 200, resp.text
    body = MemoResponse.model_validate(resp.json())
    assert body.archived is False
    assert body.ordinal == 4
    assert body.ordinal != 2  # not the slot it held

    listed = await _list_memos(http_client, token, book.id)
    assert [item.id for item in listed.items] == [
        str(first.id),
        str(last.id),
        str(middle.id),
    ]
    assert [item.ordinal for item in listed.items] == [1, 3, 4]


# ---------------------------------------------------------------------------
# DoD-9 (US-124.AC-1) -- one 404 refusal, on all four verbs
# ---------------------------------------------------------------------------


# DoD-9: every verb answers 404 for an unknown id, a non-numeric id, another
# author's memo and another book's memo -- and answers them identically, so the
# route is no existence oracle. A non-numeric id is a 404, never FastAPI's 422:
# `memo_id` is the wire string and the route never parses it.
async def test_every_verb_answers_404_for_unreachable_ids__DoD9(http_client):
    owner, token = await _seed_author("memo_state_owner_9")
    co_author, _co_token = await _seed_author("memo_state_co_author_9")
    book = await _seed_private_book(owner.id)
    await _add_co_author(book.id, co_author.id)
    other_book = await _seed_private_book(owner.id, title="Another Book")

    foreign_author_memo = await _seed_memo(book.id, co_author.id, "theirs", 1)
    foreign_book_memo = await _seed_memo(other_book.id, owner.id, "elsewhere", 1)

    unreachable = [
        "not-a-number",
        "999999999999999",
        str(foreign_author_memo.id),
        str(foreign_book_memo.id),
    ]

    bodies = set()
    for verb in VERBS:
        for memo_id in unreachable:
            resp = await _call_verb(http_client, token, book.id, memo_id, verb)
            assert resp.status_code == 404, f"{verb} {memo_id}: {resp.text}"
            bodies.add(json.dumps(resp.json(), sort_keys=True))

    # Sameness, not merely "each is a 404": one response shape across all
    # sixteen (verb, id) combinations.
    assert len(bodies) == 1

    # Neither foreign row was written by any of the sixteen attempts.
    stored_foreign_author = await _stored(foreign_author_memo.id)
    stored_foreign_book = await _stored(foreign_book_memo.id)
    assert stored_foreign_author.active is True
    assert stored_foreign_author.archived is False
    assert stored_foreign_author.ordinal == 1
    assert stored_foreign_book.active is True
    assert stored_foreign_book.archived is False
    assert stored_foreign_book.ordinal == 1


# ---------------------------------------------------------------------------
# DoD-10 (context.md, repeat state calls) -- 200 no-ops, never a 409
# ---------------------------------------------------------------------------


# DoD-10: each verb applied to a memo ALREADY in that state answers 200 with the
# row unchanged. No 409 exists anywhere in this family -- this deliberately does
# not copy `POST /api/books/{id}/archive`'s 409.
async def test_activate_on_an_active_memo_answers_200_unchanged__DoD10(http_client):
    owner, token = await _seed_author("memo_state_owner_10a")
    book = await _seed_private_book(owner.id)
    memo = await _seed_memo(book.id, owner.id, "already on", 5, active=True)

    resp = await _call_verb(http_client, token, book.id, memo.id, "activate")

    assert resp.status_code == 200, resp.text
    assert resp.status_code != 409
    body = MemoResponse.model_validate(resp.json())
    assert body.id == str(memo.id)
    assert body.active is True
    assert body.archived is False
    assert body.ordinal == 5
    assert body.body == "already on"


# DoD-10: deactivate on an already-inactive memo -- 200, row unchanged.
async def test_deactivate_on_an_inactive_memo_answers_200_unchanged__DoD10(http_client):
    owner, token = await _seed_author("memo_state_owner_10b")
    book = await _seed_private_book(owner.id)
    memo = await _seed_memo(book.id, owner.id, "already off", 5, active=False)

    resp = await _call_verb(http_client, token, book.id, memo.id, "deactivate")

    assert resp.status_code == 200, resp.text
    assert resp.status_code != 409
    body = MemoResponse.model_validate(resp.json())
    assert body.active is False
    assert body.archived is False
    assert body.ordinal == 5
    assert body.body == "already off"


# DoD-10: archive on an already-archived memo -- 200, row unchanged, including
# its `active` flag and its ordinal.
async def test_archive_on_an_archived_memo_answers_200_unchanged__DoD10(http_client):
    owner, token = await _seed_author("memo_state_owner_10c")
    book = await _seed_private_book(owner.id)
    memo = await _seed_memo(
        book.id, owner.id, "already archived", 5, active=False, archived=True
    )

    resp = await _call_verb(http_client, token, book.id, memo.id, "archive")

    assert resp.status_code == 200, resp.text
    assert resp.status_code != 409
    body = MemoResponse.model_validate(resp.json())
    assert body.archived is True
    assert body.active is False
    assert body.ordinal == 5
    assert body.body == "already archived"

    row = await _stored(memo.id)
    assert row.archived is True
    assert row.active is False
    assert row.ordinal == 5


# DoD-10: restore on a memo that is NOT archived answers 200 with the row
# unchanged -- `ordinal` included. "Row unchanged" carries no carve-out for
# restore, so an idempotent-looking verb must not relocate a live memo in the
# author's list. Three live memos at 1, 2, 3 with the MIDDLE one restored make
# the assertion meaningful: "unchanged" reads 2, an unconditional append-last
# would read 4.
async def test_restore_on_a_live_memo_answers_200_unchanged__DoD10(http_client):
    owner, token = await _seed_author("memo_state_owner_10d")
    book = await _seed_private_book(owner.id)
    first = await _seed_memo(book.id, owner.id, "A", 1)
    memo = await _seed_memo(book.id, owner.id, "never archived", 2, active=False)
    last = await _seed_memo(book.id, owner.id, "C", 3)

    resp = await _call_verb(http_client, token, book.id, memo.id, "restore")

    assert resp.status_code == 200, resp.text
    assert resp.status_code != 409
    body = MemoResponse.model_validate(resp.json())
    assert body.id == str(memo.id)
    assert body.archived is False
    assert body.active is False
    assert body.body == "never archived"
    assert body.ordinal == 2

    row = await _stored(memo.id)
    assert row.archived is False
    assert row.active is False
    assert row.ordinal == 2

    # The bystanders are untouched -- one explicit await each.
    stored_first = await _stored(first.id)
    stored_last = await _stored(last.id)
    assert stored_first.ordinal == 1
    assert stored_last.ordinal == 3

    listed = await _list_memos(http_client, token, book.id)
    assert [item.id for item in listed.items] == [
        str(first.id),
        str(memo.id),
        str(last.id),
    ]
    assert [item.ordinal for item in listed.items] == [1, 2, 3]


# DoD-10: repeating a verb is a 200 every time -- the second call never becomes
# a refusal.
async def test_each_verb_repeated_answers_200_again__DoD10(http_client):
    owner, token = await _seed_author("memo_state_owner_10e")
    book = await _seed_private_book(owner.id)
    memo = await _seed_memo(book.id, owner.id, "A", 1)

    for verb in VERBS:
        first = await _call_verb(http_client, token, book.id, memo.id, verb)
        second = await _call_verb(http_client, token, book.id, memo.id, verb)
        assert first.status_code == 200, f"{verb} (1st): {first.text}"
        assert second.status_code == 200, f"{verb} (2nd): {second.text}"


# ---------------------------------------------------------------------------
# DoD-11 (US-128.AC-3) -- no DELETE anywhere, and nothing removes a memo
# ---------------------------------------------------------------------------


# DoD-11: there is no DELETE handler on any memo path -- the collection, the
# item, and each of the four verb paths all answer the framework's 405 -- and
# the memo survives every attempt.
async def test_no_delete_exists_on_any_memo_path__DoD11(http_client):
    owner, token = await _seed_author("memo_state_owner_11")
    book = await _seed_private_book(owner.id)
    memo = await _seed_memo(book.id, owner.id, "indestructible", 1)

    targets = [_list_url(book.id), _memo_url(book.id, memo.id)] + [
        _verb_url(book.id, memo.id, verb) for verb in VERBS
    ]
    for url in targets:
        resp = await http_client.delete(url, headers=_auth_header(token))
        assert resp.status_code == 405, f"DELETE {url}: {resp.status_code} {resp.text}"

    row = await _stored(memo.id)
    assert row.body == "indestructible"


# DoD-11: no call in this family removes a memo from the include-archived read.
# Archive is not delete: after every one of the four verbs the row is still
# there.
async def test_no_verb_removes_a_memo_from_the_include_archived_read__DoD11(
    http_client,
):
    owner, token = await _seed_author("memo_state_owner_11b")
    book = await _seed_private_book(owner.id)
    memo = await _seed_memo(book.id, owner.id, "indestructible", 1)

    for verb in VERBS:
        resp = await _call_verb(http_client, token, book.id, memo.id, verb)
        assert resp.status_code == 200, f"{verb}: {resp.text}"
        everything = await _list_memos(
            http_client, token, book.id, include_archived=True
        )
        assert [item.id for item in everything.items] == [str(memo.id)]
        assert everything.items[0].body == "indestructible"


# DoD-11: the published API document carries no `delete` operation on any memo
# path, verb paths included -- the absence is structural, not incidental.
async def test_no_memo_path_publishes_a_delete_operation__DoD11(http_client):
    from app.main import app

    paths = app.openapi()["paths"]
    memo_paths = [path for path in paths if "/memos" in path]
    assert memo_paths, paths.keys()
    for path in memo_paths:
        assert "delete" not in paths[path], path

    # The four verb paths exist, each as a `post`.
    for verb in VERBS:
        path = f"/api/books/{{book_id}}/memos/{{memo_id}}/{verb}"
        assert path in paths, sorted(memo_paths)
        assert "post" in paths[path], paths[path]


# ---------------------------------------------------------------------------
# DoD-12 (the archived-book carve-out) -- all four verbs work on an archived book
# ---------------------------------------------------------------------------


# DoD-12: a memo is the author's private note *about* a book they set aside, so
# all four verbs answer 200 while the book's state is `archived`.
async def test_all_four_verbs_succeed_on_an_archived_book__DoD12(http_client):
    owner, token = await _seed_author("memo_state_owner_12")
    book = await _seed_private_book(owner.id)
    memo = await _seed_memo(book.id, owner.id, "on a shelved book", 1)

    book.state = BookState.archived
    await books.update(book)

    deactivated = await _call_verb(http_client, token, book.id, memo.id, "deactivate")
    assert deactivated.status_code == 200, deactivated.text
    assert MemoResponse.model_validate(deactivated.json()).active is False

    activated = await _call_verb(http_client, token, book.id, memo.id, "activate")
    assert activated.status_code == 200, activated.text
    assert MemoResponse.model_validate(activated.json()).active is True

    archived = await _call_verb(http_client, token, book.id, memo.id, "archive")
    assert archived.status_code == 200, archived.text
    assert MemoResponse.model_validate(archived.json()).archived is True

    restored = await _call_verb(http_client, token, book.id, memo.id, "restore")
    assert restored.status_code == 200, restored.text
    assert MemoResponse.model_validate(restored.json()).archived is False
