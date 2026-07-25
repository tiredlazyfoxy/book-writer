"""Flag table — the chapter annotation record + its two enums.

Declarative SQLModel table. No logic lives here (see ``docs/architecture/
backend.md`` — ``models/`` is tables + schemas only). The ``Flag`` class
registers on ``SQLModel.metadata`` at import time (via the ``db/engine.py``
registration hook).

Realizes FEAT-016 (UC-066..068, UC-080); US-076 (``docs/architecture/
domain-continuity.md`` → "Flag"). The internal name stays ``flag`` — the
author-facing UI term "warning" is not this feature's concern.

Skeleton (008 step 007): the model shape is frozen. A table is a declarative
type, not behavior — there is nothing to leave unimplemented.
"""

import enum
from datetime import datetime

from sqlmodel import Field, SQLModel

from app.ids import generate_id


class FlagOrigin(str, enum.Enum):
    """Where a flag came from: an automated check, or a person."""

    check = "check"
    person = "person"


class FlagStatus(str, enum.Enum):
    """Flag lifecycle. ``open`` until resolved."""

    open = "open"
    resolved = "resolved"


class Flag(SQLModel, table=True):
    """A single chapter annotation flag.

    - ``id`` — application-generated 64-bit snowflake primary key.
    - ``chapter_id`` — FK → ``chapters.id``.
    - ``origin`` — required ``FlagOrigin`` enum (no default).
    - ``comment`` — the flag's text (required).
    - ``status`` — required ``FlagStatus`` enum (no default).
    - ``created_by`` — non-null FK → ``users.id``.
    - ``created_at`` — nullable, app-set timestamp.
    - ``resolved_by`` — nullable FK → ``users.id``, null until resolved.
    - ``resolved_at`` — nullable datetime, null until resolved.
    """

    __tablename__ = "flags"

    id: int = Field(default_factory=generate_id, primary_key=True)
    chapter_id: int = Field(foreign_key="chapters.id")
    origin: FlagOrigin
    comment: str
    status: FlagStatus
    created_by: int = Field(foreign_key="users.id")
    created_at: datetime | None = Field(default=None)
    resolved_by: int | None = Field(default=None, foreign_key="users.id")
    resolved_at: datetime | None = Field(default=None)
