"""Application-level configuration (pydantic-settings).

``Settings`` is the app-level config object; it is distinct from the db-layer
``DbConfig`` dataclass (step 002). ``Settings`` may *supply* ``DbConfig``'s
``db_path`` value, but the two remain separate types.

Configuration is loaded from the process environment and an optional
``.env.local`` file. The SQLite database path honours the ``BOOKWRITER_DB_PATH``
environment override and otherwise falls back to the dev default
``backend/data/bookwriter.db``. The LanceDB sidecar directory defaults to a
``vector`` directory alongside the database file (``backend/data/vector``).
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# ``settings.py`` lives at ``backend/app/settings.py`` — two parents up is the
# ``backend/`` package root, so the dev defaults resolve to ``backend/data/…``.
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_DB_PATH = _BACKEND_ROOT / "data" / "bookwriter.db"
_DEFAULT_LANCEDB_DIR = _BACKEND_ROOT / "data" / "vector"


class Settings(BaseSettings):
    """App configuration loaded from the environment and ``.env.local``.

    - ``db_path`` — resolved SQLite database file path. Honors the
      ``BOOKWRITER_DB_PATH`` environment override; dev default is
      ``backend/data/bookwriter.db``.
    - ``lancedb_dir`` — LanceDB sidecar index directory (consumed by
      ``db/vector.py`` in step 002); defaults to ``backend/data/vector``.
    """

    model_config = SettingsConfigDict(
        env_file=".env.local",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    db_path: Path = Field(
        default=_DEFAULT_DB_PATH,
        validation_alias="BOOKWRITER_DB_PATH",
    )
    lancedb_dir: Path = Field(default=_DEFAULT_LANCEDB_DIR)


@lru_cache
def get_settings() -> Settings:
    """Return the shared, cached ``Settings`` instance.

    The app and tests share a single config object; ``lru_cache`` guarantees
    repeated calls return the same instance.
    """
    return Settings()
