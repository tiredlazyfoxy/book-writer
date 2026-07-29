"""Book table — the book aggregate root + its three lifecycle enums.

Declarative SQLModel table. No logic lives here (see ``docs/architecture/
backend.md`` — ``models/`` is tables + schemas only). The ``Book`` class
registers on ``SQLModel.metadata`` at import time (via the ``db/engine.py``
registration hook).

Realizes FEAT-006 (UC-021..025), FEAT-007 (UC-026..030), FEAT-011 (UC-044),
FEAT-015 (``docs/architecture/domain-book.md`` → "Book").

Skeleton (008 step 004): the model shape is frozen. A table is a declarative
type, not behavior — there is nothing to leave unimplemented.
"""

import enum
from datetime import datetime

from sqlmodel import Field, SQLModel

from app.ids import generate_id


class CollaborationMode(str, enum.Enum):
    """How co-authors contribute — free edits vs. proposal review."""

    free = "free"
    proposal = "proposal"


class Visibility(str, enum.Enum):
    """Book visibility to non-members."""

    private = "private"
    public = "public"


class BookState(str, enum.Enum):
    """Book lifecycle. One column, not two booleans; ``destroyed`` is a
    tombstone state, not a deleted row. ``archived`` / ``quarantined`` /
    ``destroyed`` land now, unused (Stage-6 behaviour)."""

    active = "active"
    archived = "archived"
    quarantined = "quarantined"
    destroyed = "destroyed"


class Book(SQLModel, table=True):
    """A book — the domain aggregate root.

    - ``id`` — application-generated 64-bit snowflake primary key
      (``default_factory=generate_id``), mirroring ``User``.
    - ``title`` — display title.
    - ``description`` — free text, may be empty string (required, not nullable).
    - ``owner_id`` — FK → ``users.id``. Exactly one owner (structural, no extra
      constraint).
    - ``collaboration_mode`` / ``visibility`` / ``state`` — required enums.
    - ``moderation_reason`` / ``moderated_by`` / ``moderated_at`` — the nullable
      moderation triple; null on an ``active`` book (Stage-6 behaviour, land now).
    - ``system_prompt`` — **superseded and dormant** (feature 021, step 004).
      It once held the single book-wide assistant prompt; the prompt is now
      per-author (``BookAuthorPrompt``, one row per ``(book_id, user_id)``) and
      **nothing reads this column any more** — prompt composition takes the
      author's own row. It is retained rather than dropped because ``db/
      engine.py`` offers only an *additive* migration seam (``init_db()`` runs
      ``SQLModel.metadata.create_all``, which never alters an existing table) and
      there is **no Alembic in the repository**, so there is no supported DROP
      COLUMN path. It stays required (not nullable, no default), is still written
      ``""`` at book creation by ``services/books.py``, and is still exported and
      imported by the JSONL codec so existing archives keep round-tripping. Dead
      to the runtime, alive to the schema and the archive.
    - ``active_notes`` — materialised live state-note set, free text (required).
    - ``created_at`` / ``modified_at`` — nullable, app-set timestamps.
    """

    __tablename__ = "books"

    id: int = Field(default_factory=generate_id, primary_key=True)
    title: str
    description: str
    owner_id: int = Field(foreign_key="users.id")
    collaboration_mode: CollaborationMode
    visibility: Visibility
    state: BookState
    moderation_reason: str | None = Field(default=None)
    moderated_by: int | None = Field(default=None, foreign_key="users.id")
    moderated_at: datetime | None = Field(default=None)
    system_prompt: str
    active_notes: str
    created_at: datetime | None = Field(default=None)
    modified_at: datetime | None = Field(default=None)
