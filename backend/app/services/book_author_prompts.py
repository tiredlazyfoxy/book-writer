"""Per-author system-prompt service — reads and upserts **the caller's own**
prompt for one book (feature 021, step 002).

Business-logic layer: **no** ``session`` / ``AsyncSession`` / ``select()`` /
``session.exec()`` / ``session.add()`` here (see ``docs/architecture/backend.md``
— layer separation). All persistence goes through the session-free
``app.db.book_author_prompts`` module (namespace import). The domain refusal
raises the typed :class:`BookAuthorPromptError`, discriminated by
:class:`BookAuthorPromptErrorReason` so the step-003 route maps it to its HTTP
status; the route stays HTTP-only.

**The ownership rule.** The user id is taken from ``BookAccess.user_id`` and
never from an argument or a path segment, so it is structurally impossible to
ask this service for another author's prompt — there is no not-found case and
nothing to hide. This copies the *shape* of ``services/chats.py``'s
:func:`_resolve_owned_chat` (a reason enum, one exception class, one private
guard) but **not** its status: a chat hides a row that exists but is not yours
with a 404 (US-061.AC-1), whereas the only refusal reachable here is "you are not
a member of this book" → **403**. Every other refusal on this path (no token, an
invisible book, a missing book) is produced upstream by the ``book_access``
dependency and never reaches this service.

The rule is **not** a ``Capability`` / ``_CAPABILITY_MATRIX`` entry — that table
maps capability → roles and has no notion of row ownership
(``context.md`` → decision 4). ``services/authz.py`` gains nothing for this
feature; the membership test is ``access.role in {owner, co_author}``, written
here.

**No collaboration-mode check.** ``BookAccess`` carries ``collaboration_mode``
and ``services/codex.py`` refuses a co-author's write in ``proposal`` mode — that
rule does **not** reach this table. A system prompt is not book content: it is
the author's own instruction to their own assistant, never seen by a co-author,
with nothing for an owner to review.

**Timestamps are this layer's policy.** ``db/book_author_prompts`` persists the
row it is handed and sets no timestamps, so the create path stamps both
``created_at`` and ``modified_at`` and the update path stamps ``modified_at``
only (``created_at`` is preserved).

Skeleton (021 step 002): the error taxonomy and the function signatures are
frozen; every function body is UNIMPLEMENTED.
"""

import enum
from datetime import datetime, timezone

from app.db import book_author_prompts
from app.models.book_author_prompt import BookAuthorPrompt
from app.models.schemas.book_author_prompts import (
    BookAuthorPromptResponse,
    UpdateBookAuthorPromptRequest,
)
from app.services import authz


class BookAuthorPromptErrorReason(str, enum.Enum):
    """Discriminator for :class:`BookAuthorPromptError` — the per-author prompt
    refusal taxonomy.

    Mirrors the shape of :class:`app.services.chats.ChatErrorReason`, with
    exactly **one** member: the step-003 route maps ``not_a_member`` → **403**
    (the caller can legitimately see the book — a reader on a public book — and
    is simply not allowed to hold a prompt on it; ``authorization.md`` →
    "Failure modes"). Do not widen this enum: a missing row is a success, and
    every other refusal is produced upstream by the ``book_access`` dependency.
    """

    not_a_member = "not-a-member"


class BookAuthorPromptError(Exception):
    """Raised by the per-author prompt service for its domain refusal.

    Carries a :class:`BookAuthorPromptErrorReason` discriminator (``reason``)
    plus a human-readable ``message``; the route branches on ``reason`` to pick
    the status. Mirrors :class:`app.services.chats.ChatError`.
    """

    def __init__(
        self, reason: BookAuthorPromptErrorReason, message: str = ""
    ) -> None:
        self.reason = reason
        self.message = message
        super().__init__(message)


def _require_member(access: authz.BookAccess) -> None:
    """The membership guard both entry points call first.

    Returns ``None`` for an ``owner`` or a ``co_author`` — the two roles that
    author in a book and therefore may hold a prompt for it. Any other role (a
    ``reader``, or no relationship) raises :class:`BookAuthorPromptError` with
    the ``not_a_member`` reason. Makes **no** capability check and adds **no**
    ``_CAPABILITY_MATRIX`` row, and makes **no** collaboration-mode check.
    """
    if access.role not in (authz.AccessRole.owner, authz.AccessRole.co_author):
        raise BookAuthorPromptError(
            BookAuthorPromptErrorReason.not_a_member,
            "You are not a member of this book.",
        )


def _to_prompt_response(
    book_id: int, row: BookAuthorPrompt | None
) -> BookAuthorPromptResponse:
    """Map a stored row **or its absence** to a :class:`BookAuthorPromptResponse`
    by hand (never dump the ORM). ``book_id`` is stringified.

    **This is the only place the DTO is constructed**, so the read and write
    entry points cannot drift. ``row is None`` renders an empty ``system_prompt``
    and a ``None`` ``modified_at``; a row renders its stored text as-is. The two
    "no prompt" states stay distinguishable — a row holding ``""`` keeps its real
    ``modified_at`` and is **not** normalised into the absent case, nor the
    reverse.
    """
    if row is None:
        return BookAuthorPromptResponse(
            book_id=str(book_id),
            system_prompt="",
            modified_at=None,
        )
    return BookAuthorPromptResponse(
        book_id=str(book_id),
        system_prompt=row.system_prompt,
        modified_at=row.modified_at,
    )


async def get_prompt(access: authz.BookAccess) -> BookAuthorPromptResponse:
    """Return the caller's own prompt for ``access.book_id``.

    Guards membership, then looks the row up for the
    ``(access.book_id, access.user_id)`` pair through
    ``db.book_author_prompts.get_by_book_and_user`` and maps it through
    :func:`_to_prompt_response`. **No row is not an error** — the response
    carries an empty prompt and a ``None`` timestamp, which is the normal
    starting state of every book for every author.
    """
    _require_member(access)
    row = await book_author_prompts.get_by_book_and_user(
        access.book_id, access.user_id
    )
    return _to_prompt_response(access.book_id, row)


async def upsert_prompt(
    access: authz.BookAccess, req: UpdateBookAuthorPromptRequest
) -> BookAuthorPromptResponse:
    """Store ``req.system_prompt`` as the caller's own prompt for
    ``access.book_id`` and return the stored result.

    Guards membership, then upserts on the ``(access.book_id, access.user_id)``
    pair: creates the row when absent (stamping both ``created_at`` and
    ``modified_at``), or updates the text and advances ``modified_at`` when
    present, preserving ``created_at``. Returns the same DTO the read path
    returns, built by :func:`_to_prompt_response` from what was stored. An empty
    string is stored as-is — there is no deletion path (``context.md`` →
    decision 6).
    """
    _require_member(access)
    now = datetime.now(timezone.utc)
    row = await book_author_prompts.get_by_book_and_user(
        access.book_id, access.user_id
    )
    if row is None:
        # Create: this layer owns both stamps — ``db/`` sets none.
        row = BookAuthorPrompt(
            book_id=access.book_id,
            user_id=access.user_id,
            system_prompt=req.system_prompt,
            created_at=now,
            modified_at=now,
        )
        row = await book_author_prompts.create(row)
    else:
        # Update in place: ``created_at`` is preserved, ``modified_at`` advances.
        row.system_prompt = req.system_prompt
        row.modified_at = now
        row = await book_author_prompts.update(row)
    return _to_prompt_response(access.book_id, row)
