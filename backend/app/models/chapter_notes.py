"""ChapterNoteChangeset table — the 1:1-per-chapter continuity notes + its enum.

Declarative SQLModel table. No logic lives here (see ``docs/architecture/
backend.md`` — ``models/`` is tables + schemas only). The ``ChapterNoteChangeset``
class registers on ``SQLModel.metadata`` at import time (via the ``db/engine.py``
registration hook).

Realizes FEAT-012 (UC-047..052), FEAT-016 (``docs/architecture/
domain-continuity.md`` → "Notes"). A separate 1:1 table (not three columns on
``Chapter``) keeps the hot chapter row narrow.

Skeleton (008 step 007): the model shape is frozen. A table is a declarative
type, not behavior — there is nothing to leave unimplemented. The whole table
and its nullable ``status`` land now, unused (Stage-4 behaviour).
"""

import enum
from datetime import datetime

from sqlmodel import Field, SQLModel

from app.ids import generate_id


class NoteStatus(str, enum.Enum):
    """Continuity-notes freshness. Nullable column lands now, unused
    (Stage-4 behaviour)."""

    draft = "draft"
    approved = "approved"
    stale = "stale"


class ChapterNoteChangeset(SQLModel, table=True):
    """A chapter's continuity-notes changeset — one row per chapter.

    - ``id`` — application-generated 64-bit snowflake primary key.
    - ``chapter_id`` — FK → ``chapters.id`` with single-column ``unique=True``
      (one changeset per chapter — not a composite constraint).
    - ``added`` / ``modified`` / ``deleted`` — required free text, one field per
      operation.
    - ``status`` — nullable ``NoteStatus`` enum (Stage-4, land now).
    - ``created_at`` / ``modified_at`` — nullable, app-set timestamps.
    """

    __tablename__ = "chapter_note_changesets"

    id: int = Field(default_factory=generate_id, primary_key=True)
    chapter_id: int = Field(unique=True, foreign_key="chapters.id")
    added: str
    modified: str
    deleted: str
    status: NoteStatus | None = Field(default=None)
    created_at: datetime | None = Field(default=None)
    modified_at: datetime | None = Field(default=None)
