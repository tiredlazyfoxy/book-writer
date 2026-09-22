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
    - ``node_id`` — 10-bit snowflake node id (0–1023). Honors the
      ``BOOKWRITER_NODE_ID`` environment override; defaults to ``0`` for the
      single-node deployment. Consumed by ``app.ids.generate_id``.
    - ``google_search_api_key`` — Google Custom Search JSON API credential,
      stored as a ``$ENV_VAR`` pointer (never a plaintext key) and resolved
      through ``services/secrets.py:resolve_env_ref`` at call time. Defaults to
      unset so the app boots without web search configured (feature 011).
    - ``google_search_engine_id`` — the Custom Search engine id (``cx``) passed
      to the same resolver. Defaults to unset (feature 011).
    - ``log_dir`` — directory for the development log file sink. Honors the
      ``BOOKWRITER_LOG_DIR`` environment override; defaults to unset, which
      keeps logging console-only (pytest, Docker). ``start.ps1 -app`` points it
      at the git-ignored repo-root ``logs/``. Consumed by
      ``app.logging_config.configure_logging``.
    - ``log_backup_count`` — how many rolled ``bookwriter.log.N`` backups the
      file sink keeps. Honors the ``BOOKWRITER_LOG_BACKUP_COUNT`` environment
      override; defaults to ``10``.
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
    node_id: int = Field(
        default=0,
        ge=0,
        le=1023,
        validation_alias="BOOKWRITER_NODE_ID",
    )
    google_search_api_key: str | None = Field(
        default=None,
        validation_alias="BOOKWRITER_GOOGLE_SEARCH_API_KEY",
    )
    google_search_engine_id: str | None = Field(
        default=None,
        validation_alias="BOOKWRITER_GOOGLE_SEARCH_ENGINE_ID",
    )
    log_dir: Path | None = Field(
        default=None,
        validation_alias="BOOKWRITER_LOG_DIR",
    )
    log_backup_count: int = Field(
        default=10,
        ge=0,
        validation_alias="BOOKWRITER_LOG_BACKUP_COUNT",
    )


@lru_cache
def get_settings() -> Settings:
    """Return the shared, cached ``Settings`` instance.

    The app and tests share a single config object; ``lru_cache`` guarantees
    repeated calls return the same instance.
    """
    return Settings()
