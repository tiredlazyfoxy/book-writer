"""CodexEntryVersion table — a codex entry's history row.

Declarative SQLModel table. No logic lives here (see ``docs/architecture/
backend.md`` — ``models/`` is tables + schemas only). The
``CodexEntryVersion`` class registers on ``SQLModel.metadata`` at import time
(via the ``db/engine.py`` registration hook).

Stores full prior content per version (same reasoning as
``ChapterTextRevision``). First *built* at Stage 5; drawn now. Reuses the
``CodexKind`` enum declared on ``CodexEntry`` — a single, shared taxonomy.

Skeleton (008 step 008): the model shape is frozen. A table is a declarative
type, not behavior — there is nothing to leave unimplemented.
"""

from datetime import datetime

from sqlmodel import Field, SQLModel

from app.ids import generate_id
from app.models.codex_entry import CodexKind


class CodexEntryVersion(SQLModel, table=True):
    """A single historical version of a ``CodexEntry``.

    - ``id`` — application-generated 64-bit snowflake primary key.
    - ``entry_id`` — FK → ``codex_entries.id``.
    - ``name`` — nullable str; the entry's name as it stood.
    - ``body`` — content as it stood (required).
    - ``kind`` — required ``CodexKind`` enum; the kind as it stood.
    - ``author_id`` — non-null FK → ``users.id``.
    - ``generation`` — required non-null int; 1-based generation number of this
      version within its entry (maintained by the feature-013 service,
      round-tripped only here).
    - ``created_at`` — nullable, app-set timestamp (single timestamp).
    """

    __tablename__ = "codex_entry_versions"

    id: int = Field(default_factory=generate_id, primary_key=True)
    entry_id: int = Field(foreign_key="codex_entries.id")
    name: str | None = Field(default=None)
    body: str
    kind: CodexKind
    author_id: int = Field(foreign_key="users.id")
    generation: int
    created_at: datetime | None = Field(default=None)
