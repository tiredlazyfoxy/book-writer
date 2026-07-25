"""ChapterTextRevision table — the pre-apply full-body snapshot.

Declarative SQLModel table. No logic lives here (see ``docs/architecture/
backend.md`` — ``models/`` is tables + schemas only). The ``ChapterTextRevision``
class registers on ``SQLModel.metadata`` at import time (via the ``db/engine.py``
registration hook).

Realizes FEAT-014 (UC-058..060), challenge C20 (``docs/architecture/
domain-chapter.md`` → "ChapterTextRevision"). Full snapshots, not reverse
patches. First *built* at Stage 3, drawn now.

Skeleton (008 step 006): the model shape is frozen. A table is a declarative
type, not behavior — there is nothing to leave unimplemented.
"""

from datetime import datetime

from sqlmodel import Field, SQLModel

from app.ids import generate_id


class ChapterTextRevision(SQLModel, table=True):
    """A pre-apply snapshot of a chapter's full body.

    - ``id`` — application-generated 64-bit snowflake primary key.
    - ``chapter_id`` — FK → ``chapters.id``.
    - ``applied_change_id`` — FK → ``chapter_changes.id`` — the change this
      snapshot precedes.
    - ``text_before`` — the **full** chapter body before that change (required).
    - ``applied_by`` — FK → ``users.id`` (non-null, unlike
      ``ChapterChange.applied_by``).
    - ``applied_at`` — nullable, app-set timestamp (this entity's single
      timestamp; nullable per the feature timestamp convention).
    """

    __tablename__ = "chapter_text_revisions"

    id: int = Field(default_factory=generate_id, primary_key=True)
    chapter_id: int = Field(foreign_key="chapters.id")
    applied_change_id: int = Field(foreign_key="chapter_changes.id")
    text_before: str
    applied_by: int = Field(foreign_key="users.id")
    applied_at: datetime | None = Field(default=None)
