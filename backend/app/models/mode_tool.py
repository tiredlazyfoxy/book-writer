"""ModeTool table — a FEAT-020 assistant-mode ↔ tool selection link row.

Declarative SQLModel table. No logic lives here (see ``docs/architecture/
backend.md`` — ``models/`` is tables + schemas only). The ``ModeTool`` class
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


class ModeTool(SQLModel, table=True):
    """One tool selected for an assistant mode — a FEAT-020 link row.

    - ``id`` — application-generated 64-bit snowflake primary key
      (``default_factory=generate_id``), a surrogate PK over the natural pair
      (``BookMember`` reasoning). Carries no timestamps.
    - ``mode_key`` — string FK → ``assistant_modes.key`` (the natural-key PK).
    - ``tool_name`` — references the code-defined ``TOOL_REGISTRY`` **by string,
      not FK** (that catalogue is out of scope for this feature).

    The natural pair ``(mode_key, tool_name)`` is unique (first-of-kind) — one
    selection per (mode, tool).
    """

    __tablename__ = "mode_tool"
    __table_args__ = (
        UniqueConstraint("mode_key", "tool_name", name="uq_mode_tool_mode_key_tool_name"),
    )

    id: int = Field(default_factory=generate_id, primary_key=True)
    mode_key: str = Field(foreign_key="assistant_modes.key")
    tool_name: str
