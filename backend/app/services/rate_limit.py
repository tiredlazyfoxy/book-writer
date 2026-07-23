"""In-memory, per-username login rate-limit store (feature 004, decision 3).

Business-logic layer companion to ``services/auth.py``: a session-free,
module-global (per-worker) failure counter. Policy: **5 failed attempts within a
15-minute window** locks a username out; further attempts are refused regardless
of credential validity until the window rolls off or the counter is cleared on a
successful login (see ``context.md`` → "Rate-limiting").

Accepted caveats (recorded in ``outcome.md``): per-username not per-IP,
in-memory / per-worker, not persisted.

Skeleton (feature 004, step 002): the four signatures below are frozen; their
bodies are UNIMPLEMENTED (raise ``NotImplementedError``). The policy constants
are frozen here.
"""

from datetime import datetime, timedelta, timezone

# Frozen rate-limit policy (context.md → "Rate-limiting").
MAX_FAILURES = 5
FAILURE_WINDOW = timedelta(minutes=15)

# Module-global (per-worker) store: username → recent failure timestamps
# (timezone-aware UTC). In-memory, not persisted (accepted caveat).
_failures: dict[str, list[datetime]] = {}


def _prune(username: str, now: datetime) -> list[datetime]:
    """Drop ``username``'s failure timestamps older than the trailing window and
    return the surviving (recent) list, removing the key entirely if it empties.
    """
    cutoff = now - FAILURE_WINDOW
    recent = [ts for ts in _failures.get(username, []) if ts > cutoff]
    if recent:
        _failures[username] = recent
    else:
        _failures.pop(username, None)
    return recent


def is_locked(username: str) -> bool:
    """Return whether ``username`` is currently locked out — i.e. it has
    accumulated at least ``MAX_FAILURES`` failed attempts inside the trailing
    ``FAILURE_WINDOW``.
    """
    recent = _prune(username, datetime.now(timezone.utc))
    return len(recent) >= MAX_FAILURES


def record_failure(username: str) -> None:
    """Record one failed login attempt for ``username`` at "now", pruning that
    username's attempts older than ``FAILURE_WINDOW``.
    """
    now = datetime.now(timezone.utc)
    recent = _prune(username, now)
    recent.append(now)
    _failures[username] = recent


def clear(username: str) -> None:
    """Drop ``username``'s failure record entirely (called on a successful
    login).
    """
    _failures.pop(username, None)


def reset() -> None:
    """Clear the whole store — a test-isolation seam (the store is module-global
    / per-worker).
    """
    _failures.clear()
