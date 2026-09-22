"""Process-wide logging configuration (console + optional dev file sink).

A cross-cutting top-level module alongside ``app/settings.py`` and
``app/ids.py``: it sits outside the ``routes`` / ``services`` / ``db`` /
``models`` layering by the same sanctioned exception
(``docs/architecture/backend.md`` -> "Layer separation").

The module exposes exactly one public symbol, :func:`configure_logging`, called
once at ``app.main`` import time. Console logging is always installed; the
rotating file sink is opt-in and activates only when a log directory is passed
(sourced from ``Settings.log_dir`` / ``BOOKWRITER_LOG_DIR``, default unset), so
pytest and the containers stay console-only.
"""

import logging
import logging.handlers
from pathlib import Path

#: Format shared by the console and file handlers (unchanged from the inline
#: ``logging.basicConfig`` block this module replaced).
_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

#: Fixed name of the live log file inside the log directory.
_LOG_FILENAME = "bookwriter.log"

#: Marker attribute stamped on every handler this module installs, so repeated
#: calls can find and drop their own predecessors without touching handlers
#: installed by anyone else (uvicorn, pytest, ...).
_MARKER_ATTR = "_bookwriter_managed"

#: Chatty third-party loggers pinned to ``WARNING``.
_QUIET_LOGGERS = ("aiosqlite", "httpx", "httpcore")

#: uvicorn sets ``propagate = False`` on its loggers, so the file handler must
#: be attached to them by name or the startup/shutdown/traceback lines never
#: reach the root handlers. ``uvicorn.access`` is deliberately excluded —
#: per-request noise would swamp the file.
_UVICORN_LOGGERS = ("uvicorn", "uvicorn.error")


def _detach_managed(logger: logging.Logger) -> list[logging.Handler]:
    """Remove and return the handlers this module previously installed."""
    detached: list[logging.Handler] = []
    for handler in list(logger.handlers):
        if getattr(handler, _MARKER_ATTR, False):
            logger.removeHandler(handler)
            detached.append(handler)
    return detached


def configure_logging(
    log_dir: Path | None = None,
    backup_count: int = 10,
    level: int = logging.DEBUG,
) -> None:
    """Install the root logging handlers for this process (idempotent).

    Always installs a console handler on the root logger and quiets the noisy
    third-party loggers. When ``log_dir`` is given, additionally installs a
    ``RotatingFileHandler`` on ``log_dir / "bookwriter.log"`` with size-based
    rotation disabled (``maxBytes=0``): the file is rolled exactly once here, at
    process start, so the previous run becomes ``bookwriter.log.1`` and older
    runs shift down the chain until ``backup_count`` prunes them. An absent or
    empty file is not rolled, and a rollover failure (e.g. another process holds
    the file open on Windows) is non-fatal — it is reported on the console and
    the handler appends to the existing file instead.

    Repeated calls in one process do not stack handlers: everything installed
    here is marked, and previously marked handlers are detached and closed
    before new ones go in.

    Args:
        log_dir: Directory for the file sink, or ``None`` for console only.
        backup_count: Number of rolled ``bookwriter.log.N`` backups to keep.
        level: Logging level applied to the root logger and both handlers.
    """
    root = logging.getLogger()
    uvicorn_loggers = [logging.getLogger(name) for name in _UVICORN_LOGGERS]

    # Drop what a previous call installed. The same handler instance may be
    # attached to several loggers, so close each one only once.
    stale: dict[int, logging.Handler] = {}
    for target in (root, *uvicorn_loggers):
        for handler in _detach_managed(target):
            stale.setdefault(id(handler), handler)
    for handler in stale.values():
        handler.close()

    formatter = logging.Formatter(_LOG_FORMAT)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)
    setattr(console_handler, _MARKER_ATTR, True)

    root.setLevel(level)
    root.addHandler(console_handler)

    for name in _QUIET_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)

    if log_dir is None:
        return

    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / _LOG_FILENAME

    # Decide before opening the handler: the constructor creates the file, so an
    # existence check afterwards would always be true.
    should_roll = log_path.exists() and log_path.stat().st_size > 0

    file_handler = logging.handlers.RotatingFileHandler(
        log_path,
        maxBytes=0,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)
    setattr(file_handler, _MARKER_ATTR, True)

    if should_roll:
        try:
            file_handler.doRollover()
        except OSError as exc:
            logging.getLogger(__name__).warning(
                "Could not roll log file %s (%s); appending to it instead.",
                log_path,
                exc,
            )

    root.addHandler(file_handler)
    for uvicorn_logger in uvicorn_loggers:
        uvicorn_logger.addHandler(file_handler)
