"""SubagentTool table — a FEAT-020 sub-agent ↔ tool selection link row.

Declarative SQLModel table. No logic lives here (see ``docs/architecture/
backend.md`` — ``models/`` is tables + schemas only). The ``SubagentTool`` class
registers on ``SQLModel.metadata`` at import time (via the ``db/engine.py``
registration hook).

Realizes FEAT-020, UC-096, US-112 (``docs/architecture/assistant-config.md`` →
"The three link tables").

Skeleton (008 step 002): the model shape is frozen. A table is a declarative
type, not behavior — there is nothing to leave unimplemented.
"""

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

from app.ids import generate_id


class SubagentTool(SQLModel, table=True):
    """One tool selected for a sub-agent — a FEAT-020 link row.

    - ``id`` — application-generated 64-bit snowflake primary key
      (``default_factory=generate_id``), a surrogate PK over the natural pair.
      Carries no timestamps.
    - ``sub_agent_id`` — int FK → ``sub_agents.id``.
    - ``tool_name`` — references the code-defined ``TOOL_REGISTRY`` **by string,
      not FK** (that catalogue is out of scope for this feature).

    The natural pair ``(sub_agent_id, tool_name)`` is unique (first-of-kind).
    """

    __tablename__ = "subagent_tool"
    __table_args__ = (
        UniqueConstraint(
            "sub_agent_id", "tool_name", name="uq_subagent_tool_sub_agent_id_tool_name"
        ),
    )

    id: int = Field(default_factory=generate_id, primary_key=True)
    sub_agent_id: int = Field(foreign_key="sub_agents.id")
    tool_name: str
