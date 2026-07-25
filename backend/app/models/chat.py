"""Chat + ChatMessage tables — the assistant conversation entities.

Declarative SQLModel tables. No logic lives here (see ``docs/architecture/
backend.md`` — ``models/`` is tables + schemas only). Both classes register on
``SQLModel.metadata`` at import time (via the ``db/engine.py`` registration
hook — a single ``import app.models.chat`` covers both tables).

These two tables exist so the schema is drawn whole (FEAT-013 entities only —
UC-053, UC-081, UC-082); the assistant subsystem that makes them useful is not
built here. Per ``domain-chat.md``: ``role`` is a free string (no enum), and a
chat carries no subject FK (privacy is a service rule, not modelled here).

Skeleton (008 step 009): the model shapes are frozen. A table is a declarative
type, not behavior — there is nothing to leave unimplemented.
"""

from datetime import datetime

from sqlmodel import Field, SQLModel

from app.ids import generate_id


class Chat(SQLModel, table=True):
    """A per-book assistant chat, private to its author.

    - ``id`` — application-generated 64-bit snowflake primary key.
    - ``book_id`` — FK → ``books.id`` (chats are per book).
    - ``author_id`` — FK → ``users.id`` (a plain FK; privacy is a service rule,
      not modelled here).
    - ``title`` — display label (required).
    - ``archived`` — ``bool = False``; archived, not destroyed (UC-082).
    - ``created_at`` / ``modified_at`` — nullable, app-set timestamps.
    """

    __tablename__ = "chats"

    id: int = Field(default_factory=generate_id, primary_key=True)
    book_id: int = Field(foreign_key="books.id")
    author_id: int = Field(foreign_key="users.id")
    title: str
    archived: bool = False
    created_at: datetime | None = Field(default=None)
    modified_at: datetime | None = Field(default=None)


class ChatMessage(SQLModel, table=True):
    """A single message within a ``Chat``.

    - ``id`` — application-generated 64-bit snowflake primary key.
    - ``chat_id`` — FK → ``chats.id``.
    - ``role`` — who spoke (required free string; no enum).
    - ``content`` — the message body (required).
    - ``position`` — required non-null int; the message number / order of the
      message within its chat (an explicit ordinal alongside ``created_at``).
    - ``created_at`` — nullable, app-set timestamp (single timestamp).
    """

    __tablename__ = "chat_messages"

    id: int = Field(default_factory=generate_id, primary_key=True)
    chat_id: int = Field(foreign_key="chats.id")
    role: str
    content: str
    position: int
    created_at: datetime | None = Field(default=None)
