"""Flag (author-facing "warning") request & response schemas (feature 016).

Declarative Pydantic schemas — the typed contracts for the chapter-nested flag
surface (``/api/books/{book_id}/chapters/{chapter_id}/flags``). Plain typed data
shapes, no logic (see ``docs/architecture/backend.md`` — ``models/`` is tables +
schemas only).

Conventions this file follows, all inherited from ``models/schemas/chapters.py``:

- **Ids are ``str``** on the wire (snowflakes exceed the JS safe-integer range).
  ``id`` / ``chapter_id`` / ``created_by`` / ``resolved_by`` are all ``str``; the
  service is the single place a snowflake becomes a string.
- ``origin`` / ``status`` are the shared :class:`app.models.flag.FlagOrigin` /
  :class:`app.models.flag.FlagStatus` taxonomies, which serialize to their string
  values. No second vocabulary is minted for the wire.
- There is **no ``book_id``** field: the ``Flag`` row has none either (the book is
  resolved through the chapter), and it is already in the request path.

The internal name stays ``flag`` — the author-facing UI term "warning" is the
frontend's word and never reaches the wire.

Skeleton (016): field names / types / constraints are frozen. DTOs are
declarative — there is nothing to leave unimplemented.
"""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, StringConstraints

from app.models.flag import FlagOrigin, FlagStatus


class FlagResponse(BaseModel):
    """One flag on one chapter (list / raise / resolve results, and each entry of
    a chapter's ``warnings`` in :class:`~app.models.schemas.continuity.ChapterContinuityResponse`).

    Built by hand in the service mapper — never dumped from the ORM.

    - ``origin`` — ``check`` for one the consistency check raised during a close
      run, ``person`` for one a member raised (UC-067).
    - ``created_at`` / ``resolved_by`` / ``resolved_at`` are nullable, mirroring
      the columns: the last two stay ``None`` until the flag is resolved
      (UC-068 / US-077.AC-1).
    """

    id: str
    chapter_id: str
    origin: FlagOrigin
    comment: str
    status: FlagStatus
    created_by: str
    created_at: datetime | None
    resolved_by: str | None
    resolved_at: datetime | None


class FlagListResponse(BaseModel):
    """List envelope for ``GET …/chapters/{chapter_id}/flags``.

    Carries **every** flag of the chapter — open *and* resolved — newest first.
    No caller-relative affordance hint rides here: raising and resolving are
    capability-gated server-side (``raise_flag`` / ``resolve_flag``) and the
    client's controls are never the enforcement.
    """

    items: list[FlagResponse]


class RaiseFlagRequest(BaseModel):
    """Body of ``POST …/chapters/{chapter_id}/flags`` — a member-raised warning
    (UC-067 / US-075.AC-1).

    ``comment`` is required and **non-blank**: the constraint is declared on the
    field (``strip_whitespace`` + ``min_length=1``), so a blank or whitespace-only
    comment is refused by the framework as **422** and never reaches the service;
    the stored comment is the stripped value. A flag with no text says nothing.

    There is deliberately **no ``origin`` field**: a flag raised through this
    endpoint is always ``origin=person`` — the ``check`` origin belongs to the
    close run's own tool and is not client-settable.
    """

    comment: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
