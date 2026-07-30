"""Chapter request & response schemas (feature 014, step 002).

Declarative Pydantic schemas — the typed contracts for the book-nested chapter
skeleton surface (``/api/books/{book_id}/chapters``). Plain typed data shapes,
no logic (see ``docs/architecture/backend.md`` — ``models/`` is tables +
schemas only).

Conventions this file follows:

- **Ids are ``str``** on the wire (snowflakes exceed the JS safe-integer range,
  mirroring ``BookResponse.id`` / ``CodexEntryResponse.id``). The service is the
  single place a snowflake becomes a string.
- ``state`` is the shared :class:`app.models.chapter.ChapterState` taxonomy
  (``planned | open | closing | closed``), which serializes to its string value.
- :class:`ChapterResponse` carries **no ``text``, no ``summary`` and no
  ``summary_status``** (``014/context.md`` → "The wire contract"): the body is
  ``015.chapter-writing-free-mode``'s and the summary is
  ``016.chapter-close-continuity``'s. Shipping them here would put a whole
  chapter body on the wire for every list render and would fix their shape
  before the feature that owns them exists.
- :attr:`UpdateChapterSketchRequest` carries **no version token** — sketch edits
  are last-write-wins and never bump ``Chapter.version`` (decision D6).
- ``ordinal`` is **server-assigned**: a new chapter is appended (UC-031), so
  :class:`CreateChapterRequest` has no ordinal field.

Skeleton (014 step 002): field names / types / constraints are frozen. DTOs are
declarative — there is nothing to leave unimplemented.
"""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, StringConstraints

from app.models.chapter import ChapterState


class CreateChapterRequest(BaseModel):
    """Body of ``POST /api/books/{book_id}/chapters`` — a new planned chapter
    (UC-031 / US-032.AC-1).

    - ``title`` — required and **non-blank**. The constraint is declared on the
      field (``strip_whitespace`` + ``min_length=1``), so a blank or
      whitespace-only title is refused by the framework as **422** and never
      reaches the service; the stored title is the stripped value.
    - ``sketch`` — required, and ``""`` is legitimate: an author may plan a
      chapter before they know what is in it, so this field carries **no**
      constraint.
    """

    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    sketch: str


class UpdateChapterSketchRequest(BaseModel):
    """Body of ``PATCH /api/books/{book_id}/chapters/{chapter_id}`` — the sketch
    of a ``planned`` chapter (UC-033 / US-034.AC-1).

    One field only. There is deliberately **no ``expected_version``** token and
    no ``409``-on-stale path: sketch edits are last-write-wins (decision D6), and
    ``Chapter.version`` tracks the *body*, which this request never touches.
    """

    sketch: str


class ReorderChaptersRequest(BaseModel):
    """Body of ``PUT /api/books/{book_id}/chapters/order`` — the **full** ordered
    chapter-id list (UC-032 / US-033.AC-1, decision D3).

    ``chapter_ids`` are ``str`` ids in their intended order; the server rewrites
    ordinals ``1..N`` from their positions. A list that is not exactly the book's
    current chapter set (missing, extra, duplicated or foreign ids) is refused by
    the **service** — the body is structurally valid, so that refusal is a
    ``400``, not a framework ``422``.
    """

    chapter_ids: list[str]


class ChapterResponse(BaseModel):
    """One chapter of a book's skeleton (list / create / read / sketch-edit
    results).

    Built by hand in the service mapper — never dumped from the ORM. ``id`` and
    ``book_id`` are ``str``. Carries **no ``text``, no ``summary`` and no
    ``summary_status``** by design (see the module docstring), and no
    ``system_prompt``: the chapter prompt is **per-author** and lives on its own
    endpoint (decision D1), while the dormant ``Chapter.system_prompt`` column is
    read and written by nothing in this feature.
    """

    id: str
    book_id: str
    ordinal: int
    title: str
    state: ChapterState
    sketch: str
    version: int
    created_at: datetime | None
    modified_at: datetime | None


class ChapterListResponse(BaseModel):
    """List envelope for ``GET /api/books/{book_id}/chapters`` and for the
    reorder result.

    - ``chapters`` — the book's chapters ordered by ``ordinal`` **ascending**.
    - ``can_reorder`` — a caller-relative **affordance hint**, computed by the
      service from ``access.role`` and true only for the owner (US-033.AC-2). It
      is honest on this envelope — a list response is the answer to *this*
      caller's request, not a resource representation — and it never substitutes
      for enforcement, which stays on the ``PUT`` in the service.
    """

    chapters: list[ChapterResponse]
    can_reorder: bool
