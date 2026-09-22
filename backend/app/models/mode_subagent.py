"""ModeSubagent table — a FEAT-020 assistant-mode ↔ sub-agent link row.

Declarative SQLModel table. No logic lives here (see ``docs/architecture/
backend.md`` — ``models/`` is tables + schemas only). The ``ModeSubagent`` class
registers on ``SQLModel.metadata`` at import time (via the ``db/engine.py``
registration hook).

Realizes FEAT-020, UC-096, US-111 (``docs/architecture/assistant-config.md`` →
"The three link tables").

Skeleton (008 step 002): the model shape is frozen. A table is a declarative
type, not behavior — there is nothing to leave unimplemented.
"""

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

from app.ids import generate_id


class ModeSubagent(SQLModel, table=True):
    """One sub-agent attached to an assistant mode — a FEAT-020 link row.

    - ``id`` — application-generated 64-bit snowflake primary key
      (``default_factory=generate_id``), a surrogate PK over the natural pair.
      Carries no timestamps.
    - ``mode_key`` — string FK → ``assistant_modes.key`` (the natural-key PK).
    - ``sub_agent_id`` — int FK → ``sub_agents.id``.

    The natural pair ``(mode_key, sub_agent_id)`` is unique (first-of-kind).
    """

    __tablename__ = "mode_subagent"
    __table_args__ = (
        UniqueConstraint(
            "mode_key", "sub_agent_id", name="uq_mode_subagent_mode_key_sub_agent_id"
        ),
    )

    id: int = Field(default_factory=generate_id, primary_key=True)
    mode_key: str = Field(foreign_key="assistant_modes.key")
    sub_agent_id: int = Field(foreign_key="sub_agents.id")
