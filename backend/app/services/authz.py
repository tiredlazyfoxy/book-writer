"""Book-scoped authorization spine — the resolve-in-a-dependency, decide-in-a-
service enforcement pair consumed by the book slices (steps 3–5).

Two halves (see ``docs/architecture/authorization.md`` → "Enforcement"):

1. **Resolution** — :func:`resolve_book_access` reads through ``db/books`` +
   ``db/book_members`` and produces a typed :class:`BookAccess` context (identity
   relative to one book). ``role == none`` on a private book collapses to the same
   **404** as a missing book (existence hiding, produced in exactly one place).
   The thin :func:`book_access` FastAPI dependency wraps it, pulling the caller via
   the existing ``get_current_user`` dependency (which raises **401** with no token).
   Raising ``HTTPException`` from this resolver mirrors ``get_current_user`` — a
   sanctioned cross-cutting concern, not DB orchestration.
2. **Decision** — :func:`require` checks ``access.role`` against the
   ``_CAPABILITY_MATRIX`` capability × role table and raises the typed
   :class:`BookAuthorizationError` (which routes map to **403** via their
   error-mapping helper). No DB/session access and no HTTP framework types beyond
   the raised exception live in :func:`require` (layer separation).

Skeleton (009 step 002): the signatures below are frozen; the three function
bodies are UNIMPLEMENTED (raise ``NotImplementedError``). The enums, the
:class:`BookAccess` structure, the :class:`BookAuthorizationError` shape, and the
``_CAPABILITY_MATRIX`` policy table are the frozen contract.
"""

import enum
from dataclasses import dataclass

from fastapi import Depends, HTTPException

from app.db import book_members, books
from app.models.book import BookState, CollaborationMode, Visibility
from app.models.user import User
from app.services import auth as auth_service


class AccessRole(str, enum.Enum):
    """A caller's role relative to one book. ``admin`` as a book-access role is
    deferred to FEAT-011's moderation view — not populated here; an admin hitting
    an authoring endpoint resolves by the ordinary rules and is refused exactly as
    a stranger (``authorization.md`` → "The admin boundary")."""

    owner = "owner"
    co_author = "co_author"
    reader = "reader"
    none = "none"


class Capability(str, enum.Enum):
    """The 009 book capabilities gated by the matrix."""

    read_book = "read_book"
    view_book_detail = "view_book_detail"
    archive_book = "archive_book"
    transfer_ownership = "transfer_ownership"
    add_member = "add_member"
    remove_member = "remove_member"
    set_visibility = "set_visibility"


@dataclass(frozen=True)
class BookAccess:
    """A caller's identity relative to one book and nothing else. A typed
    structure (not a dict), carried from the resolver to :func:`require`.

    - ``book_id`` / ``user_id`` — the resolved pair.
    - ``role`` — the resolved :class:`AccessRole`.
    - ``book_state`` / ``visibility`` / ``collaboration_mode`` — carried through
      as-resolved from the ``Book`` row (feed the read/state gates).
    """

    book_id: int
    user_id: int
    role: AccessRole
    book_state: BookState
    visibility: Visibility
    collaboration_mode: CollaborationMode


# Capability × role policy (``authorization.md`` → "Book lifecycle and settings —
# owner only"). Frozen contract: read is open to any resolvable role, member
# detail excludes readers, and every mutation is owner-only.
_CAPABILITY_MATRIX: dict[Capability, frozenset[AccessRole]] = {
    Capability.read_book: frozenset(
        {AccessRole.owner, AccessRole.co_author, AccessRole.reader}
    ),
    Capability.view_book_detail: frozenset(
        {AccessRole.owner, AccessRole.co_author}
    ),
    Capability.archive_book: frozenset({AccessRole.owner}),
    Capability.transfer_ownership: frozenset({AccessRole.owner}),
    Capability.add_member: frozenset({AccessRole.owner}),
    Capability.remove_member: frozenset({AccessRole.owner}),
    Capability.set_visibility: frozenset({AccessRole.owner}),
}


class BookAuthorizationError(Exception):
    """Typed denial raised by :func:`require`. Carries the attempted
    ``capability`` and the caller's ``role`` so a route maps it to **403** via its
    error-mapping helper (same shape as the ``LlmServerError`` mapping). Not an
    ``HTTPException`` — the capability decision stays in ``services/``."""

    def __init__(self, capability: Capability, role: AccessRole) -> None:
        self.capability = capability
        self.role = role
        super().__init__(
            f"Role {role.value} may not {capability.value}"
        )


async def resolve_book_access(book_id: int, user: User) -> BookAccess:
    """Resolve the caller ``user``'s :class:`BookAccess` for ``book_id``.

    Reads ``db/books.get_by_id`` and ``db/book_members.get_by_book_and_user``;
    determines role (owner if ``owner_id == user.id``; else co-author if a
    membership row exists; else reader if ``visibility == public``; else none).
    Raises **404** (``HTTPException``) when the book is missing **or** the resolved
    role is ``none`` (existence hiding); otherwise returns the populated
    :class:`BookAccess`. Testable without HTTP — callers seed rows and pass a
    ``User`` directly.

    Skeleton (009 step 002): UNIMPLEMENTED.
    """
    book = await books.get_by_id(book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Book not found")

    if book.owner_id == user.id:
        role = AccessRole.owner
    elif await book_members.get_by_book_and_user(book_id, user.id) is not None:
        role = AccessRole.co_author
    elif book.visibility == Visibility.public:
        role = AccessRole.reader
    else:
        role = AccessRole.none

    if role == AccessRole.none:
        raise HTTPException(status_code=404, detail="Book not found")

    return BookAccess(
        book_id=book.id,
        user_id=user.id,
        role=role,
        book_state=book.state,
        visibility=book.visibility,
        collaboration_mode=book.collaboration_mode,
    )


async def book_access(
    book_id: int,
    user: User = Depends(auth_service.get_current_user),
) -> BookAccess:
    """Thin FastAPI dependency: pull the caller via ``get_current_user`` (raising
    **401** with no valid token) and delegate to :func:`resolve_book_access`. This
    is what routes declare as ``Depends(book_access)``.

    Skeleton (009 step 002): UNIMPLEMENTED.
    """
    return await resolve_book_access(book_id, user)


def require(access: BookAccess, capability: Capability) -> None:
    """The single capability guard every book service calls. Returns ``None`` when
    ``access.role`` is in ``_CAPABILITY_MATRIX[capability]``; raises
    :class:`BookAuthorizationError` otherwise. No DB/session access, no HTTP
    framework types beyond the raised exception.

    Skeleton (009 step 002): UNIMPLEMENTED.
    """
    if access.role not in _CAPABILITY_MATRIX[capability]:
        raise BookAuthorizationError(capability, access.role)
    return None
