"""Tests for app.settings — the pydantic-settings config object (step 001).

Bound to the frozen skeleton signatures:
    class Settings(BaseSettings)  with fields  db_path: Path, lancedb_dir: Path
    get_settings() -> Settings    (returns the shared cached instance)

Expected values come from the spec (step DoD + 001.context.md + feature context):
    - the DB path honors the BOOKWRITER_DB_PATH env override, and
    - falls back to the documented dev default `backend/data/bookwriter.db`.

`get_settings()` is cached, so env-sensitive cases construct `Settings()`
directly (the constructor the accessor wraps) per the step's guidance, rather
than fighting an unknown cache mechanism.
"""

from pathlib import Path

from app.settings import Settings, get_settings


# DoD-1: Settings resolves the DB path from BOOKWRITER_DB_PATH when it is set.
def test_db_path_resolved_from_env_override__DoD1(monkeypatch):
    monkeypatch.setenv("BOOKWRITER_DB_PATH", "custom/override/location.db")

    settings = Settings()

    resolved = Path(settings.db_path).as_posix()
    assert resolved.endswith("custom/override/location.db")
    assert Path(settings.db_path).name == "location.db"


# DoD-2: Settings falls back to the documented dev default when the env var is unset.
def test_db_path_falls_back_to_dev_default__DoD2(monkeypatch):
    monkeypatch.delenv("BOOKWRITER_DB_PATH", raising=False)

    settings = Settings()

    resolved = Path(settings.db_path).as_posix()
    assert resolved.endswith("backend/data/bookwriter.db")


# DoD-3: get_settings() returns the same instance on repeated calls
# (a single shared config object).
def test_get_settings_returns_shared_instance__DoD3():
    first = get_settings()
    second = get_settings()

    assert first is second
