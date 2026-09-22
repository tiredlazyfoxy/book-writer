"""Per-author **chapter** system-prompt route pair for
``/api/books/{book_id}/chapters/{chapter_id}/system-prompt`` (feature 014,
step 004).

HTTP only: parse the request, call one
:mod:`app.services.chapter_author_prompts` function, map the typed refusal to a
status, and return (see ``docs/architecture/backend.md`` — layer separation; no
business logic, no DB access, and no capability check here). Both endpoints are
gated by ``access: authz.BookAccess = Depends(authz.book_access)`` — the
``{book_id}`` path param is consumed **entirely** by that dependency, so neither
handler declares it, and the 401-without-a-token / 404-for-a-book-you-cannot-see
rules are inherited for free. ``{chapter_id}`` **is** a handler parameter,
because the service needs it, and it is a ``str`` because the service parses it
(``routes/chapters.py`` is the same shape).

This is a separate module rather than a route family inside ``routes/chapters.py``
for three reasons: it mirrors ``routes/book_author_prompts.py``, which is the
sibling a reader will look for; it keeps this step's source list disjoint from
step 003's; and it has its own reason set and its own status map, which have
nothing to do with the skeleton's.

Typed-error → status map: ``not_a_member`` → **403** (the caller can legitimately
see the book — a reader on a public book — and is simply not allowed to hold a
prompt on it), ``not_found`` → **404** (the chapter is missing or belongs to
another book). ``401`` comes from the authentication dependency behind
``book_access``; ``404`` for a book the caller cannot see comes from
``resolve_book_access`` — existence hiding lives in the resolution step in
exactly one place (``authorization.md`` → "Failure modes"). There is **no**
``_map_authz_error`` here, unlike ``routes/chapters.py``: the service raises no
:class:`~app.services.authz.BookAuthorizationError` because this step adds no
``Capability`` (``context.md`` → the authorization section).

``PUT`` is the upsert and answers **200**, not 201, on both the create and the
update path: the addressed resource is "this caller's prompt for this chapter",
which exists conceptually from the moment the caller is a member of the book, and
the same URL answers before and after (``context.md`` → the wire contract). There
is **no** ``POST`` and **no** ``DELETE`` on this path — ``""`` already expresses
"no prompt", so a delete verb would add a second way to say one thing, and both
verbs are refused by the framework rather than by a handler.

Skeleton (014 step 004): the router object, both route registrations, the handler
signatures (response models via return annotations, the ``access`` dependency,
the ``chapter_id`` path param, the request body param) and the reason → status
map are frozen.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.models.schemas.chapter_author_prompts import (
    ChapterAuthorPromptResponse,
    UpdateChapterAuthorPromptRequest,
)
from app.services import authz
from app.services import chapter_author_prompts as chapter_author_prompts_service

router = APIRouter(prefix="/api/books", tags=["chapter-author-prompts"])

_PROMPT_ERROR_STATUS: dict[
    chapter_author_prompts_service.ChapterAuthorPromptErrorReason, int
] = {
    chapter_author_prompts_service.ChapterAuthorPromptErrorReason.not_a_member: (
        status.HTTP_403_FORBIDDEN
    ),
    chapter_author_prompts_service.ChapterAuthorPromptErrorReason.not_found: (
        status.HTTP_404_NOT_FOUND
    ),
}


def _map_prompt_error(
    err: chapter_author_prompts_service.ChapterAuthorPromptError,
) -> HTTPException:
    """Translate a typed
    :class:`~app.services.chapter_author_prompts.ChapterAuthorPromptError` to an
    :class:`HTTPException` per :data:`_PROMPT_ERROR_STATUS`, passing
    ``err.message`` straight through as the ``detail`` (the plain-string shape
    ``routes/chapters.py`` and ``routes/book_author_prompts.py`` use — the client
    has refusals to render, nothing to branch on).
    """
    return HTTPException(
        status_code=_PROMPT_ERROR_STATUS[err.reason],
        detail=err.message,
    )


@router.get("/{book_id}/chapters/{chapter_id}/system-prompt")
async def get_chapter_system_prompt(
    chapter_id: str,
    access: authz.BookAccess = Depends(authz.book_access),
) -> ChapterAuthorPromptResponse:
    """Return the caller's own system prompt for the chapter
    (``GET …/chapters/{chapter_id}/system-prompt`` → 200).

    Delegates to
    ``chapter_author_prompts_service.get_prompt(access, chapter_id)``. **No row
    yet is an ordinary success**, not a 404: the response carries an empty
    ``system_prompt`` and a null ``modified_at``, which is the normal starting
    state of every chapter for every author. A non-member is refused through
    :func:`_map_prompt_error` → 403; an unknown or foreign chapter → 404.
    """
    try:
        return await chapter_author_prompts_service.get_prompt(
            access, chapter_id
        )
    except chapter_author_prompts_service.ChapterAuthorPromptError as err:
        raise _map_prompt_error(err)


@router.put("/{book_id}/chapters/{chapter_id}/system-prompt")
async def update_chapter_system_prompt(
    chapter_id: str,
    payload: UpdateChapterAuthorPromptRequest,
    access: authz.BookAccess = Depends(authz.book_access),
) -> ChapterAuthorPromptResponse:
    """Upsert the caller's own system prompt for the chapter
    (``PUT …/chapters/{chapter_id}/system-prompt`` → **200**).

    Delegates to
    ``chapter_author_prompts_service.upsert_prompt(access, chapter_id, payload)``
    and returns the stored result. 200 on both the create and the update path; an
    empty string is stored as-is and means "no prompt", so there is no delete
    verb. A non-member is refused through :func:`_map_prompt_error` → 403; an
    unknown or foreign chapter → 404.
    """
    try:
        return await chapter_author_prompts_service.upsert_prompt(
            access, chapter_id, payload
        )
    except chapter_author_prompts_service.ChapterAuthorPromptError as err:
        raise _map_prompt_error(err)
