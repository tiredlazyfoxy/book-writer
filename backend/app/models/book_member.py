"""BookMember table — a co-author membership row (composite unique).

Declarative SQLModel table. No logic lives here (see ``docs/architecture/
backend.md`` — ``models/`` is tables + schemas only). The ``BookMember`` class
registers on ``SQLModel.metadata`` at import time (via the ``db/engine.py``
registration hook).

Realizes FEAT-006/FEAT-007 (``docs/architecture/domain-book.md`` →
"BookMember").

Skeleton (008 step 004): the model shape is frozen. A table is a declarative
type, not behavior — there is nothing to leave unimplemented.
"""

from datetime import datetime

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

from app.ids import generate_id


class BookMember(SQLModel, table=True):
    """One co-author's membership in a book — carries "one membership per user
    per book".

    - ``id`` — application-generated 64-bit snowflake primary key
      (``default_factory=generate_id``), a surrogate PK over the natural pair.
    - ``book_id`` — FK → ``books.id``.
    - ``user_id`` — FK → ``users.id``.
    - ``role`` — co-author role marker (a plain string, not an enum).
    - ``created_at`` — nullable, app-set timestamp. This entity carries only one
      timestamp (no ``modified_at``).

    The owner is **not** a ``BookMember`` row (ownership is ``Book.owner_id``);
    readers have no row at all. The natural pair ``(book_id, user_id)`` is
    unique.
    """

    __tablename__ = "book_members"
    __table_args__ = (
        UniqueConstraint(
            "book_id", "user_id", name="uq_book_member_book_id_user_id"
        ),
    )

    id: int = Field(default_factory=generate_id, primary_key=True)
    book_id: int = Field(foreign_key="books.id")
    user_id: int = Field(foreign_key="users.id")
    role: str
    created_at: datetime | None = Field(default=None)
