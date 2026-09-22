"""Memo route family for ``/api/books/{book_id}/memos`` (feature 026, step 003;
extended by step 004 with reorder and by step 005 with the two state axes).

HTTP only: parse the request, call **one** :mod:`app.services.memos` function, map
the typed refusal to a status, and return (see ``docs/architecture/backend.md`` —
layer separation; no business logic, no capability check and no DB access here).
Every endpoint is gated by ``access: authz.BookAccess = Depends(authz.book_access)``
— the ``{book_id}`` path param is consumed **entirely** by that dependency, so no
handler re-declares it, and the 401-without-a-token / 404-for-a-book-you-cannot-see
rules are inherited for free (``routes/book_author_prompts.py`` and
``routes/codex.py`` are the same shape). Response models are the handlers' **return
annotations**, never ``response_model=``.

**Only three statuses are this module's to produce.** ``401`` comes from the
authentication dependency behind ``book_access``; the private-book ``404`` comes
from ``resolve_book_access`` — existence hiding lives in the resolution step in
exactly one place (``authorization.md`` → "Failure modes"), so it is deliberately
**never re-derived here**. What this module maps is the service's three typed
reasons: ``not_a_member`` → **403** (the caller can legitimately see the book — a
reader on a public book — and is simply not allowed to hold memos on it),
``not_found`` → **404** (a memo that does not exist, belongs to another author, or
belongs to another book — **one** refusal, no existence oracle; ``context.md`` →
decision 3) and ``invalid_reorder_set`` → **400** (the reorder body is
structurally valid, so the refusal is a business-rule one and not a ``422``).

There is **no** ``_map_authz_error`` here, unlike ``routes/chapters.py``: the
service raises no :class:`~app.services.authz.BookAuthorizationError` because this
feature adds no ``Capability`` and no ``_CAPABILITY_MATRIX`` row (``context.md`` →
decision 3), and membership arrives with the access context.

**No archived-book refusal**, unlike ``routes/chapters.py``: memos are the one named
carve-out (``authorization.md`` → "The one named exception: memos stay writable on
an archived book"), so create, update, reorder and all four state verbs succeed
while ``BookAccess.book_state == archived``. A reader copying the chapter family
would get exactly this wrong.

``memo_id`` is taken from the path as the wire **string** and handed to the service
verbatim — the route does **not** parse it, so a non-numeric id is the service's
``not_found`` → 404 rather than FastAPI's 422 (step 002's context).

There is **no** ``DELETE`` on any memo path, at any layer: archive-not-delete
(UC-107 / US-128.AC-3), so the framework's own 405 is the answer.

Route ordering is load-bearing: FastAPI matches in declaration order, so
``PUT .../memos/order`` (step 004) is declared **before**
``PUT .../memos/{memo_id}`` — otherwise ``order`` would be captured as a
``memo_id``. The parameterised ``PUT`` is therefore kept **last** in this module,
with step 005's four ``/{memo_id}/<verb>`` routes declared immediately above it;
any further literal-segment route under ``/memos`` goes above it too. The same
rule ``routes/chapters.py`` documents for ``/chapters/order``.

**The two axes are four no-body ``POST`` verbs** (step 005): ``activate`` /
``deactivate`` and ``archive`` / ``restore``, each answering **200** with a
:class:`~app.models.schemas.memos.MemoResponse` and each reusing
:data:`_MEMO_ERROR_STATUS` unchanged — **no new reason and no new map entry**.
``routes/books.py``'s ``POST /{book_id}/archive`` / ``unarchive`` is the shape
precedent, with two deliberate differences: the verb is ``restore``, not
``unarchive``, and a repeated call is a **200 no-op** rather than that family's
**409** (``context.md`` → "Planner-derived: repeat state calls are 200 no-ops").

Skeleton (026 steps 003, 004 and 005): the router object, route registration and
declaration order, the handler signatures (response models via return
annotations, the ``access`` dependency, the query param, the body params, the
string ``memo_id``, the 201 on create) and the reason → status map are frozen.
Steps 003, 004 and 005 are implemented.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.models.schemas.memos import (
    CreateMemoRequest,
    MemoListResponse,
    MemoResponse,
    ReorderMemosRequest,
    UpdateMemoRequest,
)
from app.services import authz
from app.services import memos as memos_service

router = APIRouter(prefix="/api/books", tags=["memos"])

_MEMO_ERROR_STATUS: dict[memos_service.MemoErrorReason, int] = {
    memos_service.MemoErrorReason.not_a_member: status.HTTP_403_FORBIDDEN,
    memos_service.MemoErrorReason.not_found: status.HTTP_404_NOT_FOUND,
    # 400, **not** 422: the reorder body is structurally valid — a well-formed
    # list of strings — and the refusal is a business rule about the *set*. A 422
    # would misreport where validation happened (``routes/chapters.py`` maps
    # ``invalid_reorder_set`` the same way).
    memos_service.MemoErrorReason.invalid_reorder_set: (
        status.HTTP_400_BAD_REQUEST
    ),
}


def _map_memo_error(err: memos_service.MemoError) -> HTTPException:
    """Translate a typed :class:`~app.services.memos.MemoError` to an
    :class:`HTTPException` per :data:`_MEMO_ERROR_STATUS`, passing ``err.message``
    straight through as the ``detail`` (the plain-string shape
    ``routes/book_author_prompts.py`` uses — the client has one refusal to render,
    nothing to branch on).

    All four ``not_found`` sources arrive here as the *same* reason with the same
    message, so the four 404s are indistinguishable on the wire — that sameness is
    the point (US-124.AC-1).
    """
    return HTTPException(
        status_code=_MEMO_ERROR_STATUS[err.reason],
        detail=err.message,
    )


@router.get("/{book_id}/memos")
async def list_memos(
    include_archived: bool = False,
    access: authz.BookAccess = Depends(authz.book_access),
) -> MemoListResponse:
    """List the caller's **own** memos for the book
    (``GET /api/books/{book_id}/memos`` → 200, UC-105 / US-124.AC-1, US-131.AC-2).

    Delegates to ``memos_service.list_memos(access, include_archived)``, which
    scopes the read to ``access.user_id`` — nobody, **including the book's owner**,
    ever sees another author's memos. Archived memos are excluded unless
    ``include_archived`` is set (US-128.AC-1 / AC-2); the envelope's ``items`` are
    ordinal-ordered. A non-member is refused through :func:`_map_memo_error` → 403.
    """
    try:
        return await memos_service.list_memos(access, include_archived)
    except memos_service.MemoError as err:
        raise _map_memo_error(err)


@router.post("/{book_id}/memos", status_code=status.HTTP_201_CREATED)
async def create_memo(
    payload: CreateMemoRequest,
    access: authz.BookAccess = Depends(authz.book_access),
) -> MemoResponse:
    """Append a new memo to the caller's own list for the book
    (``POST /api/books/{book_id}/memos`` → **201**, UC-103 / US-123.AC-1, AC-3).

    Delegates to ``memos_service.create_memo(access, payload)``. ``ordinal`` is
    server-assigned (appended last over the caller's non-archived memos) and the
    memo comes back active and not archived. ``body: ""`` is **legitimate input**,
    never a 422 — a new memo is created empty (UC-103's postcondition). Succeeds on
    an ``archived`` book — the carve-out. A non-member is refused through
    :func:`_map_memo_error` → 403.
    """
    try:
        return await memos_service.create_memo(access, payload)
    except memos_service.MemoError as err:
        raise _map_memo_error(err)


# Declaration order is load-bearing: FastAPI matches in order, so this
# literal-segment route MUST stay ahead of the ``/{memo_id}`` route below —
# declared after it, the ``order`` segment would be swallowed as a memo id.
# The rule ``routes/chapters.py`` documents for ``PUT /{book_id}/chapters/order``.


@router.put("/{book_id}/memos/order")
async def reorder_memos(
    payload: ReorderMemosRequest,
    access: authz.BookAccess = Depends(authz.book_access),
) -> MemoListResponse:
    """Rewrite the caller's memo order in one bulk call
    (``PUT /api/books/{book_id}/memos/order`` → 200, UC-106 / US-126.AC-2,
    US-131.AC-2).

    Delegates to ``memos_service.reorder_memos(access, payload)``, which takes the
    **full ordered id list** of the caller's non-archived memos, refuses a list
    that is not exactly that set with ``invalid_reorder_set`` → **400** (not a
    ``422``: the body is structurally valid and the refusal is a business rule)
    and otherwise rewrites ordinals ``1..N``, answering with the reordered list
    envelope. Scoped to ``access.user_id``: nobody reorders another author's
    memos, and **this is not owner-only** — no capability is checked, unlike
    ``PUT /{book_id}/chapters/order``. A non-member is refused through
    :func:`_map_memo_error` → 403. Succeeds on an ``archived`` book — the
    carve-out.

    **Declared before the ``/{memo_id}`` route below** so the literal ``order``
    segment can never be captured as a memo id (DoD-6).
    """
    try:
        return await memos_service.reorder_memos(access, payload)
    except memos_service.MemoError as err:
        raise _map_memo_error(err)


# The two state axes (step 005): four no-body ``POST`` verbs, declared after the
# literal ``order`` route and beside the parameterised ``PUT``, which stays the
# last route in the module. Their paths carry an extra segment
# (``/{memo_id}/<verb>``), so they can never collide with it — but keeping them
# above it preserves the one ordering rule this module documents.
#
# ``POST /books/{book_id}/archive`` / ``unarchive`` in ``routes/books.py`` is the
# shipped precedent for the shape (no body, ``access`` the only parameter, the row
# as the response). **Two deliberate differences**: the verb here is ``restore``,
# not ``unarchive`` (``quick-reference.md`` → the memos route table); and that
# family answers **409** when the book is already archived while these four answer
# a plain **200** — they are idempotent state assertions, not lifecycle
# transitions, and the memo taxonomy names no 409 at all (``context.md`` →
# "Planner-derived: repeat state calls are 200 no-ops"). Do not copy the 409.


@router.post("/{book_id}/memos/{memo_id}/activate")
async def activate_memo(
    memo_id: str,
    access: authz.BookAccess = Depends(authz.book_access),
) -> MemoResponse:
    """Switch a memo on (``POST /api/books/{book_id}/memos/{memo_id}/activate``
    → 200, UC-107 / US-127.AC-4).

    **No request body.** Delegates to ``memos_service.activate_memo(access,
    memo_id)``, which writes ``active`` alone — ``archived``, ``ordinal`` and
    ``body`` do not move. Already active is a **200 no-op**, not a 409. ``memo_id``
    is passed through as the wire **string**; a non-numeric, unknown, other-author
    or other-book id is one identical :func:`_map_memo_error` → **404**
    (US-124.AC-1). Succeeds on an ``archived`` book — the carve-out.
    """
    try:
        return await memos_service.activate_memo(access, memo_id)
    except memos_service.MemoError as err:
        raise _map_memo_error(err)


@router.post("/{book_id}/memos/{memo_id}/deactivate")
async def deactivate_memo(
    memo_id: str,
    access: authz.BookAccess = Depends(authz.book_access),
) -> MemoResponse:
    """Switch a memo off (``POST
    /api/books/{book_id}/memos/{memo_id}/deactivate`` → 200, UC-107 /
    US-127.AC-2).

    **No request body.** Delegates to ``memos_service.deactivate_memo(access,
    memo_id)``, which writes ``active`` alone, so the memo **stays in the working
    list** (US-127.AC-1) and merely stops reaching the assistant. Refuses
    nothing — deactivating the caller's last active memo is allowed
    (US-127.AC-5). Already inactive is a **200 no-op**. Unknown / foreign ids are
    one identical **404**. Succeeds on an ``archived`` book.
    """
    try:
        return await memos_service.deactivate_memo(access, memo_id)
    except memos_service.MemoError as err:
        raise _map_memo_error(err)


@router.post("/{book_id}/memos/{memo_id}/archive")
async def archive_memo(
    memo_id: str,
    access: authz.BookAccess = Depends(authz.book_access),
) -> MemoResponse:
    """Archive a memo (``POST /api/books/{book_id}/memos/{memo_id}/archive`` →
    200, UC-107 / US-128.AC-1).

    **No request body.** Delegates to ``memos_service.archive_memo(access,
    memo_id)``, which writes ``archived`` alone: ``active`` is **preserved** (so a
    restore returns the memo in the state its author chose) and ``ordinal`` is
    **left as a gap** (nothing is renumbered). The memo leaves the default read and
    appears in the include-archived one; it is never deleted (US-128.AC-3).
    Already archived is a **200 no-op** — deliberately **not** the 409 that
    ``POST /api/books/{book_id}/archive`` answers. Unknown / foreign ids are one
    identical **404**. Succeeds on an ``archived`` book.
    """
    try:
        return await memos_service.archive_memo(access, memo_id)
    except memos_service.MemoError as err:
        raise _map_memo_error(err)


@router.post("/{book_id}/memos/{memo_id}/restore")
async def restore_memo(
    memo_id: str,
    access: authz.BookAccess = Depends(authz.book_access),
) -> MemoResponse:
    """Restore an archived memo, appended last (``POST
    /api/books/{book_id}/memos/{memo_id}/restore`` → 200, UC-107 /
    US-128.AC-2).

    **No request body.** Delegates to ``memos_service.restore_memo(access,
    memo_id)``, which clears ``archived`` and rewrites ``ordinal`` to one past the
    caller's highest non-archived memo — the memo returns to the **end** of the
    list, never to its old slot — while ``active`` is preserved. The verb is
    ``restore``, **not** ``unarchive``. Already un-archived is a **200 no-op**.
    Unknown / foreign ids are one identical **404**. Succeeds on an ``archived``
    book.
    """
    try:
        return await memos_service.restore_memo(access, memo_id)
    except memos_service.MemoError as err:
        raise _map_memo_error(err)


@router.put("/{book_id}/memos/{memo_id}")
async def update_memo_body(
    memo_id: str,
    payload: UpdateMemoRequest,
    access: authz.BookAccess = Depends(authz.book_access),
) -> MemoResponse:
    """Write a memo's body and return the updated memo
    (``PUT /api/books/{book_id}/memos/{memo_id}`` → 200, UC-104 / US-125.AC-1).

    Delegates to ``memos_service.update_memo_body(access, memo_id, payload)``.
    Body-only: no other field moves — not ``ordinal``, not ``active``, not
    ``archived`` — and there is no version token, so no 409 (``context.md`` →
    decision 5). ``memo_id`` is passed through as the wire **string**; a
    non-numeric, unknown, other-author or other-book id is one identical
    :func:`_map_memo_error` → **404**. Succeeds on an ``archived`` book — the
    carve-out.

    **Keep this handler last in the module**: ``PUT .../memos/order`` is declared
    above it for exactly this reason, step 005's four ``/{memo_id}/<verb>`` routes
    sit immediately above it, and any future literal-segment route under
    ``/memos`` must be declared above it too.
    """
    try:
        return await memos_service.update_memo_body(access, memo_id, payload)
    except memos_service.MemoError as err:
        raise _map_memo_error(err)
