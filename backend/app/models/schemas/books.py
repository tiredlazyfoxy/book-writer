"""Book request & response schemas (feature 009, step 003).

Declarative Pydantic schemas — the typed contracts for the author-owned book
surface (``/api/books``). Plain typed data shapes, no logic (see
``docs/architecture/backend.md`` — ``models/`` is tables + schemas only).

Ids are surfaced as ``str`` (snowflake serialized as a string — 64-bit ids exceed
the JS safe-integer range, mirroring ``AdminUserResponse.id``); this applies to
every id-bearing field (``id``, ``owner_id``). The collaboration/visibility/state
enums are reused from ``app.models.book`` (they serialize to their string values).

Skeleton (step 003): field names/types are frozen. This module is **extended** by
steps 004 (read projections) and 005 (settings mutations) — keep it open for the
member-detail / update request shapes those add.
"""

from datetime import datetime

from pydantic import BaseModel

from app.models.book import BookState, CollaborationMode, Visibility
from app.models.book_member import MemberRole


class CreateBookRequest(BaseModel):
    """Body of ``POST /api/books`` — the author's create input.

    Carries only ``title``, ``description``, ``collaboration_mode`` and
    ``visibility``; ``state`` / ``system_prompt`` / ``active_notes`` / moderation
    fields are defaulted server-side (UC-021).
    """

    title: str
    description: str
    collaboration_mode: CollaborationMode
    visibility: Visibility


class BookResponse(BaseModel):
    """A book summary DTO for list results and the create result.

    Built by hand in the service mapper — never dumped from the ORM. ``id`` and
    ``owner_id`` are ``str`` (snowflake serialized as a string). Carries no
    moderation internals (``moderation_reason`` / ``moderated_by`` /
    ``moderated_at``) and no ``system_prompt`` / ``active_notes``.

    The ``system_prompt`` omission is deliberate and is now structural (feature
    021): the assistant prompt is **per-author**, not per-book, and is served by
    its own endpoint (``GET`` / ``PUT /api/books/{book_id}/system-prompt``,
    returning the *caller's own* prompt). A book-shaped DTO cannot carry it
    honestly — two authors reading the same book would need different bytes in
    the same field.
    """

    id: str
    owner_id: str
    title: str
    description: str
    collaboration_mode: CollaborationMode
    visibility: Visibility
    state: BookState
    created_at: datetime | None
    modified_at: datetime | None


class BookListResponse(BaseModel):
    """List envelope for ``GET /api/books`` and ``GET /api/books/shared``."""

    items: list[BookResponse]


class BookMemberResponse(BaseModel):
    """One co-author in a book's member list (feature 009, step 004).

    ``user_id`` is a ``str`` (snowflake serialized as a string, mirroring the
    other id-bearing fields); ``role`` is the single-value ``MemberRole`` marker
    (co-author — the owner has no member row, readers have no row);
    ``created_at`` is the membership timestamp (nullable, app-set).
    """

    user_id: str
    role: MemberRole
    created_at: datetime | None


class BookDetailResponse(BookResponse):
    """Members-only book detail DTO (feature 009, step 004) — feeds step 7's
    settings page.

    Extends :class:`BookResponse` (so it carries ``id``, ``owner_id``, ``title``,
    ``description``, ``collaboration_mode``, ``visibility``, ``state`` and the
    timestamps) and adds the ``members`` co-author list. Deliberately omits
    ``system_prompt`` and ``active_notes``.

    ``system_prompt`` stays off this DTO permanently (feature 021): the assistant
    prompt is **per-author**, not per-book, and has its own endpoint (``GET`` /
    ``PUT /api/books/{book_id}/system-prompt``) that always answers with the
    *caller's own* prompt. Putting it on a book-shaped DTO would be dishonest —
    two authors reading the same book would need different bytes in the same
    field — so the settings page fetches it separately rather than from here.
    This DTO is members-only: readers never receive it (they get
    :class:`ReaderBookResponse`).
    """

    members: list[BookMemberResponse]


class ReaderBookResponse(BaseModel):
    """Reader-safe book projection (feature 009, step 004, UC-029 / US-030).

    The deliberately narrow reader view: the book ``title`` plus a placeholder
    table-of-contents / ``chapters`` field. No chapters exist until Stage 5, so
    ``chapters`` is an empty placeholder. Carries **none** of the members-only
    surface — no members, owner id, codex, notes, book state, visibility,
    settings, ``system_prompt`` or any mutation-bearing field. The exclusion is
    enforced structurally by this being a separate DTO from
    :class:`BookDetailResponse` (UC-029 exclusion list).

    ``system_prompt`` is doubly excluded (feature 021): beyond the reader
    exclusion list, there is no book-wide prompt left to project. The prompt is
    **per-author** and lives on its own endpoint (``GET`` / ``PUT
    /api/books/{book_id}/system-prompt``), which serves the caller their own
    prompt and is members-only — a reader has none, and no book-shaped DTO could
    carry a value that differs per caller.
    """

    title: str
    chapters: list[str]


class TransferOwnershipRequest(BaseModel):
    """Body of ``POST /api/books/{book_id}/transfer`` (feature 009, step 005).

    Carries the target author-account user id to become the new owner. The id is
    a ``str`` on the wire (snowflake serialized as a string, mirroring every other
    id-bearing field); the service resolves it to ``int`` and refuses a target
    that is not a current co-author (UC-024 / US-025.AC-1).
    """

    target_user_id: str


class AddMemberRequest(BaseModel):
    """Body of ``POST /api/books/{book_id}/members`` (feature 009, step 005).

    Carries the author-account user id to grant co-author access. The id is a
    ``str`` on the wire; the service resolves it to ``int`` and creates a
    ``BookMember(role = co_author)``, refusing a duplicate ``(book_id, user_id)``
    add (UC-026 / US-027.AC-1).
    """

    target_user_id: str


class SetVisibilityRequest(BaseModel):
    """Body of ``PATCH /api/books/{book_id}/visibility`` (feature 009, step 005).

    Carries the target :class:`~app.models.book.Visibility` value (UC-028 /
    US-029.AC-1, AC-2).
    """

    visibility: Visibility
