"""ChapterChange table — the unified chapter write record + its two enums.

Declarative SQLModel table. No logic lives here (see ``docs/architecture/
backend.md`` — ``models/`` is tables + schemas only). The ``ChapterChange`` class
registers on ``SQLModel.metadata`` at import time (via the ``db/engine.py``
registration hook).

Realizes FEAT-009, FEAT-010 (UC-040/041), FEAT-013 (UC-055 save path),
FEAT-014; US-040, US-041 (``docs/architecture/domain-chapter.md`` →
"ChapterChange — the unified write record"). All lifecycle behaviour (the one
write path, 409, stale-refusal) is feature 015's — this step lands only the
table shape.

Skeleton (008 step 006): the model shape is frozen. A table is a declarative
type, not behavior — there is nothing to leave unimplemented.
"""

import enum
from datetime import datetime

from sqlmodel import Field, SQLModel

from app.ids import generate_id


class PlacementKind(str, enum.Enum):
    """Where a change lands: appended to the body, or over a line range.

    ``range`` sets ``line_from`` / ``line_to``; ``append`` leaves both null.
    """

    append = "append"
    range = "range"


class ChangeStatus(str, enum.Enum):
    """Change lifecycle. ``pending`` until applied or rejected."""

    pending = "pending"
    applied = "applied"
    rejected = "rejected"


class ChapterChange(SQLModel, table=True):
    """A single chapter write record — the unified change entity.

    - ``id`` — application-generated 64-bit snowflake primary key.
    - ``chapter_id`` — FK → ``chapters.id``.
    - ``author_id`` — FK → ``users.id`` (attribution, US-040.AC-2).
    - ``placement_kind`` — required ``PlacementKind`` enum (no default).
    - ``line_from`` / ``line_to`` — nullable ints, set only when
      ``placement_kind = range``.
    - ``base_version`` — required int, the ``Chapter.version`` this change was
      composed against (no default).
    - ``text`` — the change's text (required).
    - ``status`` — required ``ChangeStatus`` enum (no default).
    - ``applied_at`` — nullable datetime, null until applied.
    - ``applied_by`` — nullable FK → ``users.id``, null until applied.
    - ``created_at`` — nullable, app-set timestamp.
    """

    __tablename__ = "chapter_changes"

    id: int = Field(default_factory=generate_id, primary_key=True)
    chapter_id: int = Field(foreign_key="chapters.id")
    author_id: int = Field(foreign_key="users.id")
    placement_kind: PlacementKind
    line_from: int | None = Field(default=None)
    line_to: int | None = Field(default=None)
    base_version: int
    text: str
    status: ChangeStatus
    applied_at: datetime | None = Field(default=None)
    applied_by: int | None = Field(default=None, foreign_key="users.id")
    created_at: datetime | None = Field(default=None)
