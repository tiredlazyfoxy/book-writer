"""ChapterAuthorPrompt table — one system prompt per ``(chapter, author)`` pair.

Declarative SQLModel table. No logic lives here (see ``docs/architecture/
backend.md`` — ``models/`` is tables + schemas only). The ``ChapterAuthorPrompt``
class registers on ``SQLModel.metadata`` at import time (via the ``db/engine.py``
registration hook).

**Why a table rather than a column on ``Chapter``:** the prompt is **per-author**
— every member of a book keeps their own instruction for the same chapter — and a
single column on the chapter row can hold only one author's. The row shape is
``BookMember``'s (the system's precedent for a surrogate-PK-plus-unique-pair link
row), exactly as ``BookAuthorPrompt`` copied it one level up.

**This table supersedes ``Chapter.system_prompt``.** That column is dormant and
read by nothing (feature 014 decision D1): ``db/engine.py`` exposes only an
*additive* migration seam and the project has no Alembic, so there is no
supported DROP COLUMN path. The column is therefore kept and still exported by
the JSONL codec so pre-existing archives still import — it is simply no longer
the chapter prompt. No step in feature 014 reads or writes it.

Skeleton (014 step 001): the model shape is frozen. A table is a declarative
type, not behavior — there is nothing to leave unimplemented.
"""

from datetime import datetime

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

from app.ids import generate_id


class ChapterAuthorPrompt(SQLModel, table=True):
    """One author's own system prompt for one chapter.

    - ``id`` — application-generated 64-bit snowflake primary key
      (``default_factory=generate_id``), a surrogate PK over the natural pair.
    - ``chapter_id`` — FK → ``chapters.id``.
    - ``user_id`` — FK → ``users.id``.
    - ``system_prompt`` — **required** text, not nullable. ``""`` is a valid
      value meaning "this author has no prompt" and is **distinct** from having
      no row at all; nothing may coerce one into the other.
    - ``created_at`` / ``modified_at`` — nullable, app-set timestamps. The
      service owns timestamp policy; ``db/`` persists the row it is handed.

    The natural pair ``(chapter_id, user_id)`` is unique — one prompt per author
    per chapter, enforced by the database.
    """

    __tablename__ = "chapter_author_prompts"
    __table_args__ = (
        UniqueConstraint(
            "chapter_id",
            "user_id",
            name="uq_chapter_author_prompt_chapter_id_user_id",
        ),
    )

    id: int = Field(default_factory=generate_id, primary_key=True)
    chapter_id: int = Field(foreign_key="chapters.id")
    user_id: int = Field(foreign_key="users.id")
    system_prompt: str
    created_at: datetime | None = Field(default=None)
    modified_at: datetime | None = Field(default=None)
