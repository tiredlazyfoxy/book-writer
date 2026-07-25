"""Chapter table — the per-book chapter aggregate + its two lifecycle enums.

Declarative SQLModel table. No logic lives here (see ``docs/architecture/
backend.md`` — ``models/`` is tables + schemas only). The ``Chapter`` class
registers on ``SQLModel.metadata`` at import time (via the ``db/engine.py``
registration hook).

Realizes FEAT-008 (UC-031..034), FEAT-009 (UC-035..039), FEAT-012 (UC-047/048
states), FEAT-014 (``docs/architecture/domain-chapter.md`` → "Chapter").

Skeleton (008 step 005): the model shape is frozen. A table is a declarative
type, not behavior — there is nothing to leave unimplemented. ``state = closing``
and ``summary_status`` land now, nullable/unused (Stage-4 behaviour).
"""

import enum
from datetime import datetime

from sqlmodel import Field, SQLModel

from app.ids import generate_id


class ChapterState(str, enum.Enum):
    """Chapter lifecycle — a four-state machine. ``closing`` lands now, unused
    (Stage-4 behaviour)."""

    planned = "planned"
    open = "open"
    closing = "closing"
    closed = "closed"


class SummaryStatus(str, enum.Enum):
    """Continuity summary freshness. Nullable column lands now, unused
    (Stage-4 behaviour)."""

    draft = "draft"
    approved = "approved"
    stale = "stale"


class Chapter(SQLModel, table=True):
    """A chapter — one row per chapter in a book's skeleton.

    - ``id`` — application-generated 64-bit snowflake primary key
      (``default_factory=generate_id``), mirroring ``Book``.
    - ``book_id`` — FK → ``books.id``.
    - ``ordinal`` — required int, position in the skeleton (no default).
    - ``title`` — chapter title.
    - ``state`` — required ``ChapterState`` enum (no default).
    - ``sketch`` — forward-looking outline (required, product's word).
    - ``text`` — the single main body, one ``text`` not a block table (required).
    - ``summary`` — nullable backward-looking summary.
    - ``summary_status`` — nullable ``SummaryStatus`` enum (Stage-4, land now).
    - ``system_prompt`` — nullable, appends to the book's (divergence 3).
    - ``version`` — int, default 1; bumped on every applied change.
    - ``created_at`` / ``modified_at`` — nullable, app-set timestamps.
    """

    __tablename__ = "chapters"

    id: int = Field(default_factory=generate_id, primary_key=True)
    book_id: int = Field(foreign_key="books.id")
    ordinal: int
    title: str
    state: ChapterState
    sketch: str
    text: str
    summary: str | None = Field(default=None)
    summary_status: SummaryStatus | None = Field(default=None)
    system_prompt: str | None = Field(default=None)
    version: int = 1
    created_at: datetime | None = Field(default=None)
    modified_at: datetime | None = Field(default=None)
