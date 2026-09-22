"""BookAuthorPrompt table — one system prompt per ``(book, author)`` pair.

Declarative SQLModel table. No logic lives here (see ``docs/architecture/
backend.md`` — ``models/`` is tables + schemas only). The ``BookAuthorPrompt``
class registers on ``SQLModel.metadata`` at import time (via the ``db/engine.py``
registration hook).

**Why a table rather than a column on ``BookMember``:** the owner has **no**
``BookMember`` row — ownership is ``Book.owner_id`` (``docs/architecture/
domain-book.md``, ``authorization.md`` → "Roles"). A prompt hung off membership
would be unreachable for exactly the author with the most reason to set one.
The row shape is otherwise ``BookMember``'s: a surrogate snowflake PK over a
unique natural ``(book_id, user_id)`` pair, plus the prompt text.

**This table supersedes ``Book.system_prompt``.** There is no book-wide prompt
any more — the prompt an assistant turn composes belongs to the author running
the turn. ``Book.system_prompt`` is kept (there is no DROP COLUMN path and no
Alembic), still written and still exported; feature 021 step 004 stops *reading*
it and marks it dormant.

Skeleton (021 step 001): the model shape is frozen. A table is a declarative
type, not behavior — there is nothing to leave unimplemented.
"""

from datetime import datetime

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

from app.ids import generate_id


class BookAuthorPrompt(SQLModel, table=True):
    """One author's own system prompt for one book.

    - ``id`` — application-generated 64-bit snowflake primary key
      (``default_factory=generate_id``), a surrogate PK over the natural pair.
    - ``book_id`` — FK → ``books.id``.
    - ``user_id`` — FK → ``users.id``.
    - ``system_prompt`` — **required** text, not nullable. ``""`` is a valid
      value meaning "this author has no prompt" and is **distinct** from having
      no row at all; nothing may coerce one into the other.
    - ``created_at`` / ``modified_at`` — nullable, app-set timestamps. The
      service owns timestamp policy; ``db/`` persists the row it is handed.

    The natural pair ``(book_id, user_id)`` is unique — one prompt per author
    per book, enforced by the database.
    """

    __tablename__ = "book_author_prompts"
    __table_args__ = (
        UniqueConstraint(
            "book_id", "user_id", name="uq_book_author_prompt_book_id_user_id"
        ),
    )

    id: int = Field(default_factory=generate_id, primary_key=True)
    book_id: int = Field(foreign_key="books.id")
    user_id: int = Field(foreign_key="users.id")
    system_prompt: str
    created_at: datetime | None = Field(default=None)
    modified_at: datetime | None = Field(default=None)
