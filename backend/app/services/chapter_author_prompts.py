"""Per-author **chapter** system-prompt service — reads and upserts **the
caller's own** prompt for one chapter (feature 014, step 004).

Business-logic layer: **no** ``session`` / ``AsyncSession`` / ``select()`` /
``session.exec()`` / ``session.add()`` here (see ``docs/architecture/backend.md``
— layer separation). All persistence goes through the session-free
``app.db.chapter_author_prompts`` and ``app.db.chapters`` modules (namespace
imports). Domain refusals raise the typed :class:`ChapterAuthorPromptError`,
discriminated by :class:`ChapterAuthorPromptErrorReason` so the route maps each
case to its HTTP status; the route stays HTTP-only.

The chapter-level mirror of ``services/book_author_prompts.py`` (feature 021),
**with one structural difference**: 021 had nothing to look up before the prompt
row, because the ``book_access`` dependency had already resolved the book. Here
the chapter id is an unresolved path parameter, so this service adds a private
resolve-and-check step (:func:`_resolve_chapter`) and a **second** reason.

**The ownership rule.** The user id is taken from ``BookAccess.user_id`` and
never from an argument or a path segment, so it is structurally impossible to ask
this service for another author's prompt. The rule is **not** a ``Capability`` /
``_CAPABILITY_MATRIX`` entry — that table maps capability → roles and has no
notion of row ownership (``context.md`` → the authorization section; this is the
third rule of its kind after ``Chat.author_id`` and ``BookAuthorPrompt``).
``services/authz.py`` gains nothing for this step; the membership test is
``access.role in {owner, co_author}``, written here.

**Exactly two reasons, and no more.** ``not_a_member`` → 403 and ``not_found``
→ 404. No token, an invisible book and a missing book are all produced upstream
by the ``book_access`` dependency and never reach this service.

**No collaboration-mode check** — a system prompt is the author's own instruction
to their own assistant, never book content, never seen by a co-author, with
nothing for an owner to review. ``services/codex.py``'s proposal refusal is
deliberately not copied.

**No chapter-state check either.** A prompt is readable and writable on a chapter
in *any* state. The ``planned``-only rule gates the chapter's *content* (UC-033,
UC-034, step 002's ``not_planned`` refusal); an author's instruction to their own
assistant is not chapter content and is not gated by the state machine.

**Timestamps are this layer's policy.** ``db/chapter_author_prompts`` persists
the row it is handed and sets no timestamps, so the create path stamps both
``created_at`` and ``modified_at`` and the update path stamps ``modified_at``
only (``created_at`` is preserved).

Nothing here reads or writes the dormant ``Chapter.system_prompt`` column (D1),
and nothing here is read by ``services/prompt_composition.py`` or
``services/chat_turn.py`` — composition is deferred (D7).

Skeleton (014 step 004): the error taxonomy and the function signatures are
frozen.
"""

import enum
from datetime import datetime, timezone

from app.db import chapter_author_prompts
from app.db import chapters
from app.models.chapter import Chapter
from app.models.chapter_author_prompt import ChapterAuthorPrompt
from app.models.schemas.chapter_author_prompts import (
    ChapterAuthorPromptResponse,
    UpdateChapterAuthorPromptRequest,
)
from app.services import authz


class ChapterAuthorPromptErrorReason(str, enum.Enum):
    """Discriminator for :class:`ChapterAuthorPromptError` — the per-author
    chapter-prompt refusal taxonomy, and it is **exactly two wide**.

    Mirrors the shape of
    :class:`app.services.book_author_prompts.BookAuthorPromptErrorReason`, plus
    the one member the chapter level needs. The route status map
    (``_PROMPT_ERROR_STATUS``): ``not_a_member`` → **403** (the caller can
    legitimately see the book — a reader on a public book — and is simply not
    allowed to hold a prompt on it), ``not_found`` → **404** (the chapter is
    missing, or belongs to another book).

    Do not widen this enum: a missing prompt *row* is a success, and every other
    refusal is produced upstream by the ``book_access`` dependency.
    """

    not_a_member = "not-a-member"
    not_found = "chapter-not-found"


class ChapterAuthorPromptError(Exception):
    """Raised by the per-author chapter-prompt service for its domain refusals.

    Carries a :class:`ChapterAuthorPromptErrorReason` discriminator (``reason``)
    plus a human-readable ``message``; the route branches on ``reason`` to pick
    the status. Mirrors
    :class:`app.services.book_author_prompts.BookAuthorPromptError`.
    """

    def __init__(
        self, reason: ChapterAuthorPromptErrorReason, message: str = ""
    ) -> None:
        self.reason = reason
        self.message = message
        super().__init__(message)


def _require_member(access: authz.BookAccess) -> None:
    """The membership guard both entry points call first.

    Returns ``None`` for an ``owner`` or a ``co_author`` — the two roles that
    author in a book and therefore may hold a prompt on its chapters. Any other
    role (a ``reader``, or no relationship) raises
    :class:`ChapterAuthorPromptError` with the ``not_a_member`` reason. Makes
    **no** capability check and adds **no** ``_CAPABILITY_MATRIX`` row, and makes
    **no** collaboration-mode check.

    Runs **before** :func:`_resolve_chapter`, so a caller who is not a member is
    refused before any chapter row is read and cannot learn whether a chapter id
    exists.
    """
    if access.role not in (authz.AccessRole.owner, authz.AccessRole.co_author):
        raise ChapterAuthorPromptError(
            ChapterAuthorPromptErrorReason.not_a_member,
            "You are not a member of this book.",
        )


async def _resolve_chapter(access: authz.BookAccess, chapter_id: str) -> Chapter:
    """Return the chapter ``chapter_id`` **within** ``access.book_id``.

    An unknown id and a chapter whose ``book_id`` differs from
    ``access.book_id`` both raise ``ChapterAuthorPromptError(not_found)`` —
    another book's chapter is never returned and its existence is never
    confirmed. The same rule as ``services/chapters.py:_resolve_chapter``,
    expressed here rather than shared: a cross-service helper would make this
    service depend on the chapter service for a two-line invariant and would blur
    which module owns the refusal (``004.context.md``).
    """
    try:
        parsed_id = int(chapter_id)
    except (ValueError, TypeError):
        raise ChapterAuthorPromptError(
            ChapterAuthorPromptErrorReason.not_found, "Chapter not found."
        )
    chapter = await chapters.get_by_id(parsed_id)
    if chapter is None or chapter.book_id != access.book_id:
        raise ChapterAuthorPromptError(
            ChapterAuthorPromptErrorReason.not_found, "Chapter not found."
        )
    return chapter


def _to_prompt_response(
    chapter_id: int, row: ChapterAuthorPrompt | None
) -> ChapterAuthorPromptResponse:
    """Map a stored row **or its absence** to a
    :class:`ChapterAuthorPromptResponse` by hand (never dump the ORM).
    ``chapter_id`` is stringified.

    **This is the only place the DTO is constructed**, so the read and write
    entry points cannot drift. ``row is None`` renders an empty ``system_prompt``
    and a ``None`` ``modified_at``; a row renders its stored text as-is. The two
    "no prompt" states stay distinguishable — a row holding ``""`` keeps its real
    ``modified_at`` and is **not** normalised into the absent case, nor the
    reverse.
    """
    if row is None:
        return ChapterAuthorPromptResponse(
            chapter_id=str(chapter_id),
            system_prompt="",
            modified_at=None,
        )
    return ChapterAuthorPromptResponse(
        chapter_id=str(chapter_id),
        system_prompt=row.system_prompt,
        modified_at=row.modified_at,
    )


async def get_prompt(
    access: authz.BookAccess, chapter_id: str
) -> ChapterAuthorPromptResponse:
    """Return the caller's own prompt for ``chapter_id``.

    Guards membership (:func:`_require_member`), resolves the chapter
    (:func:`_resolve_chapter`), then looks the row up for the
    ``(chapter.id, access.user_id)`` pair through
    ``db.chapter_author_prompts.get_by_chapter_and_user`` and maps it through
    :func:`_to_prompt_response`. **No row is not an error** — the response
    carries an empty prompt and a ``None`` timestamp, which is the normal
    starting state of every chapter for every author.
    """
    _require_member(access)
    chapter = await _resolve_chapter(access, chapter_id)
    row = await chapter_author_prompts.get_by_chapter_and_user(
        chapter.id, access.user_id
    )
    return _to_prompt_response(chapter.id, row)


async def upsert_prompt(
    access: authz.BookAccess,
    chapter_id: str,
    req: UpdateChapterAuthorPromptRequest,
) -> ChapterAuthorPromptResponse:
    """Store ``req.system_prompt`` as the caller's own prompt for ``chapter_id``
    and return the stored result.

    Guards membership, resolves the chapter, then upserts on the
    ``(chapter.id, access.user_id)`` pair: creates the row when absent (stamping
    both ``created_at`` and ``modified_at``), or updates the text and advances
    ``modified_at`` when present, preserving ``created_at``. Returns the same DTO
    the read path returns, built by :func:`_to_prompt_response` from what was
    stored. An empty string is stored as-is — there is no deletion path.
    """
    _require_member(access)
    chapter = await _resolve_chapter(access, chapter_id)
    now = datetime.now(timezone.utc)
    row = await chapter_author_prompts.get_by_chapter_and_user(
        chapter.id, access.user_id
    )
    if row is None:
        # Create: this layer owns both stamps — ``db/`` sets none.
        row = ChapterAuthorPrompt(
            chapter_id=chapter.id,
            user_id=access.user_id,
            system_prompt=req.system_prompt,
            created_at=now,
            modified_at=now,
        )
        row = await chapter_author_prompts.create(row)
    else:
        # Update in place: ``created_at`` is preserved, ``modified_at`` advances.
        row.system_prompt = req.system_prompt
        row.modified_at = now
        row = await chapter_author_prompts.update(row)
    return _to_prompt_response(chapter.id, row)
