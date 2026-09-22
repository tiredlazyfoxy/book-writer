"""Memo table — one author's standing notes for one book (FEAT-021).

Declarative SQLModel table. No logic lives here (see ``docs/architecture/
backend.md`` — ``models/`` is tables + schemas only). The ``Memo`` class
registers on ``SQLModel.metadata`` at import time (via the ``db/engine.py``
MODEL-REGISTRATION SEAM).

**There is NO unique constraint of any kind — read this before copying the
field list.** ``BookAuthorPrompt`` and ``BookMember`` both carry a unique
``(book_id, user_id)``, and this table's columns look almost exactly like
``BookAuthorPrompt``'s, so the omission reads as a mistake. It is not: **an
author has many memos per book** — that is the entire feature
(``docs/architecture/domain-book.md`` → ``## Memo``). One prompt per author per
book; *many* memos per author per book. Nothing here may be "fixed" by adding a
uniqueness rule.

**Two booleans, not one state enum** — the deliberate opposite of ``Book.state``.
``active`` (the on/off switch) and ``archived`` (the put-away axis) are two
*independent* axes. Two flags are the only shape that remembers whether a
restored memo was switched on or off before it was archived; a single state enum
would forget it.

**Context membership is derived, never stored.** A memo reaches the assistant
iff ``archived is False and active is True``. That is a **reading rule applied by
the caller**, not a constraint to enforce here: there is no invalid combination
of the two flags, only one (archived *and* active) that has no effect on the
composed prompt.

``ordinal`` is a plain non-null int scoped per ``(book, author)`` — not a key,
not unique. An archived row may legitimately share an ordinal with a live one
(ordinals are never renumbered on archive); that is inert, because an archived
row is never in the working list.

Skeleton (026 step 001): the model shape is frozen. A table is a declarative
type, not behavior — there is nothing to leave unimplemented.
"""

from datetime import datetime

from sqlmodel import Field, SQLModel

from app.ids import generate_id


class Memo(SQLModel, table=True):
    """One standing note written by one author about one book.

    - ``id`` — application-generated 64-bit snowflake primary key
      (``default_factory=generate_id``). ``db/`` never mints one.
    - ``book_id`` — FK → ``books.id``.
    - ``user_id`` — FK → ``users.id``, the memo's author. Nobody else —
      **including the book's owner** — ever reads it.
    - ``body`` — **required** text, not nullable. ``""`` is a valid value
      meaning "an empty memo" and is the normal state of a freshly created one
      (UC-103); nothing may coerce it to ``None``.
    - ``ordinal`` — non-null int, scoped per ``(book, author)``. Not unique.
    - ``active`` — bool, default ``True``. The author's on/off switch.
    - ``archived`` — bool, default ``False``. Archive-not-delete: there is no
      delete path at any layer.
    - ``created_at`` / ``modified_at`` — nullable, app-set timestamps. The
      service owns timestamp policy; ``db/`` persists the row it is handed.

    No ``__table_args__``: see the module docstring for why there is no unique
    constraint on ``(book_id, user_id)``.
    """

    __tablename__ = "memos"

    id: int = Field(default_factory=generate_id, primary_key=True)
    book_id: int = Field(foreign_key="books.id")
    user_id: int = Field(foreign_key="users.id")
    body: str
    ordinal: int
    active: bool = Field(default=True)
    archived: bool = Field(default=False)
    created_at: datetime | None = Field(default=None)
    modified_at: datetime | None = Field(default=None)
