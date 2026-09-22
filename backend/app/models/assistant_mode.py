"""AssistantMode table — a FEAT-020 admin-editable assistant mode config.

Declarative SQLModel table. No logic lives here (see ``docs/architecture/
backend.md`` — ``models/`` is tables + schemas only). The ``AssistantMode``
class registers on ``SQLModel.metadata`` at import time (via the
``db/engine.py`` registration hook).

Realizes FEAT-020, UC-095, US-110 (``docs/architecture/assistant-config.md``).

Skeleton (008 step 001): the model shape is frozen. A table is a declarative
type, not behavior — there is nothing to leave unimplemented.
"""

from datetime import datetime

from sqlmodel import Field, SQLModel


class AssistantMode(SQLModel, table=True):
    """An admin-editable assistant mode — a FEAT-020 config row.

    - ``key`` — **natural-key primary key** (``str``), NOT a snowflake and NOT
      ``generate_id``-populated. The fixed five values (``edit-character``,
      ``edit-location``, ``edit-fact``, ``write-chapter``, ``close-chapter``)
      are enforced by the step-003 seed, not by a DB constraint here. The codec
      emits/parses this value **verbatim**, never through ``int()`` (see
      ``assistant-config.md`` — "Why the primary key is the ``key`` string").
    - ``system_prompt`` — nullable text; null-or-empty is valid.
    - ``created_at`` / ``modified_at`` — nullable, app-set timestamps.
    """

    __tablename__ = "assistant_modes"

    key: str = Field(primary_key=True)
    system_prompt: str | None = Field(default=None)
    created_at: datetime | None = Field(default=None)
    modified_at: datetime | None = Field(default=None)
