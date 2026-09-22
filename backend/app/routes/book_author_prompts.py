"""Per-author system-prompt route pair for ``/api/books/{book_id}/system-prompt``
(feature 021, step 003).

HTTP only: parse the request, call one :mod:`app.services.book_author_prompts`
function, map the typed refusal to a status, and return (see
``docs/architecture/backend.md`` — layer separation; no business logic, no DB
access, and no capability check here). Both endpoints are gated by
``access: authz.BookAccess = Depends(authz.book_access)`` — the ``{book_id}`` path
param is consumed **entirely** by that dependency, so neither handler declares it,
and the 401-without-a-token / 404-for-a-book-you-cannot-see rules are inherited
for free (``routes/chats.py`` and ``routes/codex.py`` are the same shape).

**Only one status is this module's to produce.** ``401`` comes from the
authentication dependency behind ``book_access``; ``404`` comes from
``resolve_book_access`` — existence hiding lives in the resolution step in exactly
one place (``authorization.md`` → "Failure modes"), so there is deliberately **no**
404 branch here; ``403`` is this module's map of the service's single typed reason;
``200`` is the return annotations.

Typed-error → status map: ``not_a_member`` → 403 (the caller can legitimately see
the book — a reader on a public book — and is simply not allowed to hold a prompt
on it). There is **no** ``_map_authz_error`` here, unlike ``routes/chats.py``: the
service raises no :class:`~app.services.authz.BookAuthorizationError` because this
feature adds no ``Capability`` (``context.md`` → decision 4).

``PUT`` is the upsert and answers **200**, not 201, on both the create and the
update path: the addressed resource is "this caller's prompt for this book",
identified entirely by the URL plus the token, so there is no new location to
report (``context.md`` → decision 6). There is no ``POST`` and no ``DELETE`` on
this path.

Skeleton (021 step 003): the router object, route registration, handler signatures
(response models via return annotations, the ``access`` dependency, the request
body param) and the reason → status map are frozen; the mapping helper and both
handler bodies are UNIMPLEMENTED.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.models.schemas.book_author_prompts import (
    BookAuthorPromptResponse,
    UpdateBookAuthorPromptRequest,
)
from app.services import authz
from app.services import book_author_prompts as book_author_prompts_service

router = APIRouter(prefix="/api/books", tags=["book-author-prompts"])

_PROMPT_ERROR_STATUS: dict[
    book_author_prompts_service.BookAuthorPromptErrorReason, int
] = {
    book_author_prompts_service.BookAuthorPromptErrorReason.not_a_member: (
        status.HTTP_403_FORBIDDEN
    ),
}


def _map_prompt_error(
    err: book_author_prompts_service.BookAuthorPromptError,
) -> HTTPException:
    """Translate a typed
    :class:`~app.services.book_author_prompts.BookAuthorPromptError` to an
    :class:`HTTPException` per :data:`_PROMPT_ERROR_STATUS`, passing
    ``err.message`` straight through as the ``detail`` (the plain-string shape
    ``routes/chats.py`` uses — the client has one refusal to render, nothing to
    branch on).
    """
    return HTTPException(
        status_code=_PROMPT_ERROR_STATUS[err.reason],
        detail=err.message,
    )


@router.get("/{book_id}/system-prompt")
async def get_system_prompt(
    access: authz.BookAccess = Depends(authz.book_access),
) -> BookAuthorPromptResponse:
    """Return the caller's own system prompt for the book
    (``GET /api/books/{book_id}/system-prompt`` → 200).

    Delegates to ``book_author_prompts_service.get_prompt(access)``. **No row yet
    is an ordinary success**, not a 404: the response carries an empty
    ``system_prompt`` and a null ``modified_at``, which is the normal starting
    state of every book for every author (``context.md`` → "The wire contract").
    A non-member is refused through :func:`_map_prompt_error` → 403.
    """
    try:
        return await book_author_prompts_service.get_prompt(access)
    except book_author_prompts_service.BookAuthorPromptError as err:
        raise _map_prompt_error(err)


@router.put("/{book_id}/system-prompt")
async def update_system_prompt(
    payload: UpdateBookAuthorPromptRequest,
    access: authz.BookAccess = Depends(authz.book_access),
) -> BookAuthorPromptResponse:
    """Upsert the caller's own system prompt for the book
    (``PUT /api/books/{book_id}/system-prompt`` → **200**).

    Delegates to ``book_author_prompts_service.upsert_prompt(access, payload)``
    and returns the stored result. 200 on both the create and the update path
    (``context.md`` → decision 6); an empty string is stored as-is and means "no
    prompt", so there is no delete verb. A non-member is refused through
    :func:`_map_prompt_error` → 403.
    """
    try:
        return await book_author_prompts_service.upsert_prompt(access, payload)
    except book_author_prompts_service.BookAuthorPromptError as err:
        raise _map_prompt_error(err)
