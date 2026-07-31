"""Continuity request & response schemas (feature 016).

Declarative Pydantic schemas — the typed contracts for the book's live state
notes (``/api/books/{book_id}/state-notes``), one chapter's note changeset
(``…/chapters/{chapter_id}/notes``) and the per-chapter continuity roll-up
(``/api/books/{book_id}/continuity``). Plain typed data shapes, no logic (see
``docs/architecture/backend.md`` — ``models/`` is tables + schemas only).

Conventions this file follows, inherited from ``models/schemas/chapters.py``:

- **Ids are ``str``** on the wire (snowflakes exceed the JS safe-integer range);
  the service is the single place a snowflake becomes a string.
- ``status`` / ``summary_status`` reuse the shared
  :class:`app.models.chapter_notes.NoteStatus` /
  :class:`app.models.chapter.SummaryStatus` taxonomies, which serialize to their
  string values. Both are three-valued and identical in vocabulary
  (``draft | approved | stale``); they are **not** merged into one enum here —
  each mirrors its own column.
- Timestamps are nullable, mirroring the columns.

:class:`ChapterNoteChangesetResponse` is served for a chapter that has **no
``ChapterNoteChangeset`` row yet** as a default-empty **200** (all three texts
``""``, ``status`` ``None``, both timestamps ``None``) rather than a **404** —
the ``ChapterAuthorPromptResponse`` "no row yet is a normal empty value"
convention, one level down.

Skeleton (016): field names / types / constraints are frozen. DTOs are
declarative — there is nothing to leave unimplemented.
"""

from datetime import datetime

from pydantic import BaseModel

from app.models.chapter import SummaryStatus
from app.models.chapter_notes import NoteStatus
from app.models.schemas.flags import FlagResponse


class UpdateBookStateNotesRequest(BaseModel):
    """Body of ``PUT /api/books/{book_id}/state-notes`` — the book's whole live
    note set (UC-050's direct-edit path / US-052.AC-1).

    One field, carrying the **whole** replacement text: ``Book.active_notes`` is
    free text and there is no per-note addressing, so a partial update has
    nothing to address. ``""`` is legitimate (an author clearing the set), so the
    field carries **no constraint** — a blank body must reach the service rather
    than be refused **422**.

    There is deliberately **no version token**: the note set carries none on the
    ``Book`` row, so this path is last-write-wins.
    """

    active_notes: str


class BookStateNotesResponse(BaseModel):
    """``GET`` / ``PUT /api/books/{book_id}/state-notes`` result — the book's live
    state notes (UC-049 / UC-050).

    - ``book_id`` — ``str``.
    - ``active_notes`` — the whole free-text note set. Never ``None``: ``""``
      means "nothing has been recorded yet", a normal starting state rather than
      an absence.
    - ``modified_at`` — the ``Book`` row's own timestamp, nullable, mirroring the
      column.
    """

    book_id: str
    active_notes: str
    modified_at: datetime | None


class ChapterNoteChangesetResponse(BaseModel):
    """One chapter's note changeset — ``GET …/chapters/{chapter_id}/notes``, and
    the ``changeset`` member of :class:`ChapterContinuityResponse` (UC-051 /
    US-054.AC-1).

    - ``chapter_id`` — ``str``. The book id is **not** repeated; it is already in
      the path.
    - ``added`` / ``modified`` / ``deleted`` — the three free-text deltas, one
      field per operation, exactly as the row stores them. There is deliberately
      **no merged view**: no correct mechanical merge of three free-text deltas
      exists (decision D7).
    - ``status`` — nullable :class:`~app.models.chapter_notes.NoteStatus`.
      ``None`` is what a chapter with **no row yet** answers with, which is why
      the field is nullable rather than defaulted to ``draft``.
    - ``created_at`` / ``modified_at`` — nullable, mirroring the columns.
    """

    chapter_id: str
    added: str
    modified: str
    deleted: str
    status: NoteStatus | None
    created_at: datetime | None
    modified_at: datetime | None


class ChapterContinuityResponse(BaseModel):
    """One chapter's continuity roll-up — an entry of
    :class:`BookContinuityResponse` (UC-089 / UC-091; US-104.AC-1,
    US-106.AC-2 / AC-3).

    It repeats ``title`` and ``ordinal`` so the per-chapter continuity view
    renders from **one** response rather than joining this against the chapter
    list client-side.

    - ``summary`` / ``summary_status`` — the chapter's backward-looking summary
      and its freshness, straight off the ``Chapter`` row. Both nullable: a
      chapter that has never been closed has neither.
    - ``changeset`` — the chapter's :class:`ChapterNoteChangesetResponse`, or
      ``None`` when no row exists. **Nullable here, unlike the dedicated
      endpoint's default-empty 200**: in a list, "this chapter has no changeset"
      is a fact worth carrying as ``None``, while a single-resource ``GET`` needs
      a body to answer with.
    - ``warnings`` — the chapter's **open** flags only, of **both** origins
      (``check`` and ``person``). Resolved flags are deliberately absent: this is
      the roll-up of what still needs attention, and the flag list endpoint is
      where the full history lives.
    """

    chapter_id: str
    title: str
    ordinal: int
    summary: str | None
    summary_status: SummaryStatus | None
    changeset: ChapterNoteChangesetResponse | None
    warnings: list[FlagResponse]


class BookContinuityResponse(BaseModel):
    """``GET /api/books/{book_id}/continuity`` result — one entry per chapter of
    the book, in **ordinal ascending** order (UC-089 / UC-091).

    A plain list envelope with no caller-relative hint: every read on this
    surface is gated by plain membership (decision D9), so there is no affordance
    to mirror.
    """

    items: list[ChapterContinuityResponse]
