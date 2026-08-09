"""Tests for app.logging_config — the opt-in development file sink (fast/006).

Bound to the frozen skeleton signatures:
    configure_logging(log_dir: Path | None = None,
                      backup_count: int = 10,
                      level: int = logging.DEBUG) -> None
    Settings.log_dir: Path | None            (alias BOOKWRITER_LOG_DIR, default None)
    Settings.log_backup_count: int           (alias BOOKWRITER_LOG_BACKUP_COUNT, default 10)

Every expected value comes from the plan's Definition of done and Interface
intent, not from the implementation:
    - no log directory  -> no file handler, no filesystem touched (DoD-1);
    - a log directory   -> directory created, records land in `bookwriter.log` (DoD-2);
    - a second call over a non-empty log rolls it to `bookwriter.log.1` and
      starts a fresh `bookwriter.log` (DoD-3);
    - rolling more often than `backup_count` never leaves more than
      `backup_count` numbered backups (DoD-4);
    - repeated calls are idempotent w.r.t. the root handler list (DoD-5);
    - `Settings` reads both env vars and carries the documented defaults (DoD-6).

`configure_logging` mutates process-global logging state, so an autouse fixture
snapshots and restores the handler lists / levels of the root logger and of the
`uvicorn` and `uvicorn.error` loggers around every case; nothing may leak into
the rest of the suite. File handlers hold the file open on Windows, so handlers
are always detached and closed before file contents are asserted on.

`get_settings()` is `@lru_cache`d, so the env-sensitive case constructs
`Settings()` directly, as `backend/tests/test_settings.py` already does.
"""

import logging
from pathlib import Path

import pytest

from app.logging_config import configure_logging
from app.settings import Settings

LOG_FILE_NAME = "bookwriter.log"

# The loggers the module is specified to install handlers on.
_MANAGED_LOGGERS = ("", "uvicorn", "uvicorn.error")

# The third-party loggers the module is specified to quiet.
_QUIETED_LOGGERS = ("aiosqlite", "httpx", "httpcore")


def _snapshot() -> dict[str, list[logging.Handler]]:
    """Current handler lists of every logger `configure_logging` may touch."""
    return {name: list(logging.getLogger(name).handlers) for name in _MANAGED_LOGGERS}


def _detach_new_handlers(baseline: dict[str, list[logging.Handler]]) -> None:
    """Flush, remove and close every handler added since `baseline`.

    Releases the OS handle on the log file so its contents can be read (and so
    `tmp_path` teardown can delete it) on Windows.
    """
    for name in _MANAGED_LOGGERS:
        logger = logging.getLogger(name)
        for handler in list(logger.handlers):
            if any(handler is kept for kept in baseline[name]):
                continue
            try:
                handler.flush()
            except Exception:  # pragma: no cover - defensive teardown
                pass
            logger.removeHandler(handler)
            try:
                handler.close()
            except Exception:  # pragma: no cover - defensive teardown
                pass


def _emit(message: str, logger_name: str) -> None:
    """Emit one record through a plain logger that propagates to the root."""
    logger = logging.getLogger(logger_name)
    logger.propagate = True
    logger.setLevel(logging.DEBUG)
    logger.info(message)
    for name in _MANAGED_LOGGERS:
        for handler in logging.getLogger(name).handlers:
            try:
                handler.flush()
            except Exception:  # pragma: no cover - defensive
                pass


@pytest.fixture(autouse=True)
def _restore_global_logging_state():
    """Snapshot/restore process-global logging state around every case."""
    saved = {
        name: (
            list(logging.getLogger(name).handlers),
            logging.getLogger(name).level,
            logging.getLogger(name).propagate,
        )
        for name in _MANAGED_LOGGERS
    }
    saved_quiet = {name: logging.getLogger(name).level for name in _QUIETED_LOGGERS}
    try:
        yield
    finally:
        for name in _MANAGED_LOGGERS:
            logger = logging.getLogger(name)
            handlers, level, propagate = saved[name]
            for handler in list(logger.handlers):
                if any(handler is kept for kept in handlers):
                    continue
                logger.removeHandler(handler)
                try:
                    handler.close()
                except Exception:  # pragma: no cover - defensive teardown
                    pass
            logger.handlers[:] = handlers
            logger.setLevel(level)
            logger.propagate = propagate
        for name, level in saved_quiet.items():
            logging.getLogger(name).setLevel(level)


# DoD-1: with no log directory, no file handler is installed and nothing is
# created on disk.
def test_no_log_dir_installs_no_file_handler__DoD1(tmp_path):
    baseline = _snapshot()
    root = logging.getLogger()

    try:
        configure_logging(log_dir=None)

        added = [h for h in root.handlers if not any(h is kept for kept in baseline[""])]
        assert not any(isinstance(handler, logging.FileHandler) for handler in added), (
            "configure_logging(log_dir=None) must install no file handler"
        )
        # Console-only: the run must touch no filesystem at all.
        assert list(tmp_path.iterdir()) == [], (
            "configure_logging(log_dir=None) must create no directory on disk"
        )
    finally:
        _detach_new_handlers(baseline)


# DoD-2: with a log directory, the directory is created and emitted records land
# in <log_dir>/bookwriter.log.
def test_log_dir_created_and_records_written__DoD2(tmp_path):
    baseline = _snapshot()
    log_dir = tmp_path / "nested" / "logs"
    assert not log_dir.exists()

    try:
        configure_logging(log_dir=log_dir)

        assert log_dir.is_dir(), "the log directory must be created (parents=True)"

        _emit("dod2-marker-message", "bookwriter.tests.dod2")
    finally:
        _detach_new_handlers(baseline)

    log_file = log_dir / LOG_FILE_NAME
    assert log_file.is_file(), f"{LOG_FILE_NAME} must exist inside the log directory"
    assert "dod2-marker-message" in log_file.read_text(encoding="utf-8", errors="replace")


# DoD-3: a second call against a non-empty bookwriter.log rolls the previous
# content into bookwriter.log.1 and starts a fresh bookwriter.log.
def test_second_call_rolls_previous_run__DoD3(tmp_path):
    baseline = _snapshot()
    log_dir = tmp_path / "logs"
    log_file = log_dir / LOG_FILE_NAME
    rolled_file = log_dir / f"{LOG_FILE_NAME}.1"

    # First run.
    try:
        configure_logging(log_dir=log_dir)
        _emit("first-run-marker", "bookwriter.tests.dod3")
    finally:
        _detach_new_handlers(baseline)

    assert "first-run-marker" in log_file.read_text(encoding="utf-8", errors="replace")

    # Second run over the now non-empty file.
    try:
        configure_logging(log_dir=log_dir)
        _emit("second-run-marker", "bookwriter.tests.dod3")
    finally:
        _detach_new_handlers(baseline)

    assert rolled_file.is_file(), "the previous run must be preserved as bookwriter.log.1"
    rolled_text = rolled_file.read_text(encoding="utf-8", errors="replace")
    current_text = log_file.read_text(encoding="utf-8", errors="replace")

    assert "first-run-marker" in rolled_text, (
        "the first run's content must move into bookwriter.log.1"
    )
    assert "first-run-marker" not in current_text, (
        "bookwriter.log must start fresh after the roll"
    )
    assert "second-run-marker" in current_text, (
        "the second run must write into the fresh bookwriter.log"
    )
    assert "second-run-marker" not in rolled_text


# DoD-4: rolling more times than the configured backup count never leaves more
# than backup_count numbered backup files.
def test_backups_bounded_by_backup_count__DoD4(tmp_path):
    baseline = _snapshot()
    log_dir = tmp_path / "logs"
    backup_count = 2
    runs = 6

    for run in range(runs):
        try:
            configure_logging(log_dir=log_dir, backup_count=backup_count)
            _emit(f"run-{run}-marker", "bookwriter.tests.dod4")
        finally:
            _detach_new_handlers(baseline)

        backups = sorted(p.name for p in log_dir.glob(f"{LOG_FILE_NAME}.*"))
        assert len(backups) <= backup_count, (
            f"after {run + 1} runs the numbered backups {backups} exceed "
            f"backup_count={backup_count}"
        )

    final_backups = sorted(p.name for p in log_dir.glob(f"{LOG_FILE_NAME}.*"))
    assert len(final_backups) <= backup_count
    assert set(final_backups) <= {f"{LOG_FILE_NAME}.1", f"{LOG_FILE_NAME}.2"}
    assert (log_dir / LOG_FILE_NAME).is_file()


# DoD-5: repeated configure_logging calls do not accumulate handlers on the root
# logger.
def test_repeated_calls_do_not_accumulate_root_handlers__DoD5(tmp_path):
    baseline = _snapshot()
    root = logging.getLogger()
    log_dir = tmp_path / "logs"

    try:
        configure_logging(log_dir=log_dir)
        after_first = len(root.handlers)

        configure_logging(log_dir=log_dir)
        after_second = len(root.handlers)

        configure_logging(log_dir=log_dir)
        after_third = len(root.handlers)
    finally:
        _detach_new_handlers(baseline)

    assert after_second == after_first, (
        "a second configure_logging call must not add root handlers"
    )
    assert after_third == after_first, (
        "further configure_logging calls must not add root handlers"
    )


# DoD-6: Settings reads BOOKWRITER_LOG_DIR / BOOKWRITER_LOG_BACKUP_COUNT from the
# environment.
def test_settings_read_logging_env_vars__DoD6(monkeypatch, tmp_path):
    log_dir = tmp_path / "custom" / "logdir"
    monkeypatch.setenv("BOOKWRITER_LOG_DIR", str(log_dir))
    monkeypatch.setenv("BOOKWRITER_LOG_BACKUP_COUNT", "3")

    settings = Settings()

    assert settings.log_dir is not None
    assert Path(settings.log_dir).as_posix().endswith("custom/logdir")
    assert settings.log_backup_count == 3


# DoD-6: Settings defaults to None / 10 when the logging env vars are unset.
def test_settings_logging_defaults_when_unset__DoD6(monkeypatch):
    monkeypatch.delenv("BOOKWRITER_LOG_DIR", raising=False)
    monkeypatch.delenv("BOOKWRITER_LOG_BACKUP_COUNT", raising=False)

    settings = Settings()

    assert settings.log_dir is None, (
        "log_dir must default to None so the file sink stays off"
    )
    assert settings.log_backup_count == 10
