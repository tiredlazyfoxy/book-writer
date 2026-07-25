"""CodexEntry table + its kind enum — a book's codex record.

Declarative SQLModel table. No logic lives here (see ``docs/architecture/
backend.md`` — ``models/`` is tables + schemas only). The ``CodexEntry`` class
registers on ``SQLModel.metadata`` at import time (via the ``db/engine.py``
registration hook).

Realizes FEAT-017 (UC-069..075), FEAT-018 (save path); US-078..085
(``docs/architecture/domain-codex.md`` → "CodexEntry"). Three kinds
(character / location / fact) live in one table — a fixed taxonomy, not three
entities. ``name`` is nullable because a fact has no name (US-078.AC-2).

**No vector / LanceDB registration here** — codex vector indexing defers to
``013.codex``; this is an ordinary data table in feature 008.

Skeleton (008 step 008): the model shape is frozen. A table is a declarative
type, not behavior — there is nothing to leave unimplemented.
"""

import enum
from datetime import datetime

from sqlmodel import Field, SQLModel

from app.ids import generate_id


class CodexKind(str, enum.Enum):
    """The kind of codex entry. A fixed taxonomy (three kinds, one table)."""

    character = "character"
    location = "location"
    fact = "fact"


class CodexEntry(SQLModel, table=True):
    """A single codex entry within a book's codex.

    - ``id`` — application-generated 64-bit snowflake primary key.
    - ``book_id`` — FK → ``books.id`` (one codex per book).
    - ``kind`` — required ``CodexKind`` enum (no default).
    - ``name`` — nullable str; set for character/location, **null for fact**.
    - ``body`` — the entry's content (required).
    - ``archived`` — ``bool = False``; archived, never deleted (UC-072).
    - ``author_id`` — non-null FK → ``users.id`` (the original creator).
    - ``modified_by`` — nullable FK → ``users.id`` (author of the last version;
      maintained by the feature-013 service, round-tripped only here).
    - ``created_at`` / ``modified_at`` — nullable, app-set timestamps.
    """

    __tablename__ = "codex_entries"

    id: int = Field(default_factory=generate_id, primary_key=True)
    book_id: int = Field(foreign_key="books.id")
    kind: CodexKind
    name: str | None = Field(default=None)
    body: str
    archived: bool = False
    author_id: int = Field(foreign_key="users.id")
    modified_by: int | None = Field(default=None, foreign_key="users.id")
    created_at: datetime | None = Field(default=None)
    modified_at: datetime | None = Field(default=None)
