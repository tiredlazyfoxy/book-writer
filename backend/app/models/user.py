"""User table + role enum — the first persistent entity.

Declarative SQLModel table and its string role enum. No logic lives here (see
``docs/architecture/backend.md`` — ``models/`` is tables + schemas only). The
``User`` class registers on ``SQLModel.metadata`` at import time.

Skeleton (step 001): the model shape is frozen. A table is a declarative type,
not behavior — there is nothing to leave unimplemented.
"""

import enum
from datetime import datetime

from sqlmodel import Field, SQLModel

from app.ids import generate_id


class UserRole(str, enum.Enum):
    """Account role. Exactly two members (feature 003 decision 5)."""

    admin = "admin"
    author = "author"


class User(SQLModel, table=True):
    """A user account — the first persistent entity.

    - ``id`` — application-generated 64-bit snowflake primary key (system-wide
      entity-id strategy). Populated at construction via
      ``default_factory=generate_id`` *before* insert — not DB-assigned, and no
      reliance on a post-insert ``refresh()`` to learn it.
    - ``username`` — unique, indexed login handle.
    - ``pwdhash`` — bcrypt hash; **nullable, and null means the account is
      disabled** (decision 2 — no separate ``disabled`` boolean; bcrypt embeds
      its own salt, so there is no ``salt`` column).
    - ``role`` — ``UserRole``.
    - ``jwt_signing_key`` — per-user HS256 signing key (nullable).
    - ``last_login`` / ``last_key_update`` — auth timestamps (nullable).
    """

    __tablename__ = "users"

    id: int = Field(default_factory=generate_id, primary_key=True)
    username: str = Field(unique=True, index=True)
    pwdhash: str | None = Field(default=None)
    role: UserRole
    jwt_signing_key: str | None = Field(default=None)
    last_login: datetime | None = Field(default=None)
    last_key_update: datetime | None = Field(default=None)
