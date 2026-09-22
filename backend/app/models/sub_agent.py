"""SubAgent table — a FEAT-020 admin-editable sub-agent config.

Declarative SQLModel table. No logic lives here (see ``docs/architecture/
backend.md`` — ``models/`` is tables + schemas only). The ``SubAgent`` class
registers on ``SQLModel.metadata`` at import time (via the ``db/engine.py``
registration hook).

Realizes FEAT-020, UC-096, US-113, US-114
(``docs/architecture/assistant-config.md``).

Skeleton (008 step 001): the model shape is frozen. A table is a declarative
type, not behavior — there is nothing to leave unimplemented.
"""

from datetime import datetime

from sqlmodel import Field, SQLModel

from app.ids import generate_id


class SubAgent(SQLModel, table=True):
    """An admin-editable sub-agent — a FEAT-020 config row.

    - ``id`` — application-generated 64-bit snowflake primary key
      (``default_factory=generate_id``), mirroring ``User`` / ``LlmServer``.
    - ``name`` — unique, indexed. Non-blank is a service rule (feature 020),
      not a DB constraint.
    - ``system_prompt`` — required text.
    - ``disabled`` — bool, defaults false.
    - ``llm_server_id`` — nullable FK → ``llm_servers.id``.
    - ``model_name`` — nullable model id string.
    - ``created_at`` / ``modified_at`` — nullable, app-set timestamps.

    The ``llm_server_id`` / ``model_name`` "move together" invariant is a
    feature-020 service rule, **not** enforced at this data layer — both columns
    are declared nullable independently.
    """

    __tablename__ = "sub_agents"

    id: int = Field(default_factory=generate_id, primary_key=True)
    name: str = Field(unique=True, index=True)
    system_prompt: str
    disabled: bool = False
    llm_server_id: int | None = Field(default=None, foreign_key="llm_servers.id")
    model_name: str | None = Field(default=None)
    created_at: datetime | None = Field(default=None)
    modified_at: datetime | None = Field(default=None)
