"""Snowflake entity-id generator — the system-wide primary-key id strategy.

Cross-cutting helper (``docs/architecture/backend.md`` — "Conventions — entity
ID strategy"): a single ``generate_id()`` produces 64-bit, node-aware,
roughly time-ordered ids for every persistent entity. This module is the
**sanctioned exception** to "one ``db/`` module per entity" — it is a shared,
domain-agnostic utility, deliberately not one of the four layers.

Layout (Twitter-style, 64-bit, high bit 0 so ids are always positive):

    | 1 unused (0) | 41-bit ms timestamp | 10-bit node id | 12-bit sequence |

Skeleton (fast/001): the bit-layout constants and ``EPOCH_MS`` are frozen and
real; ``generate_id`` is filled by the coder (fast/001).
"""

import threading
import time

from app.settings import get_settings

# Pinned project epoch: 2024-01-01T00:00:00Z in milliseconds. Fixed once and
# never changed — moving it re-collides historical ids.
EPOCH_MS = 1704067200000

# Bit widths of the three snowflake fields.
TIMESTAMP_BITS = 41
NODE_ID_BITS = 10
SEQUENCE_BITS = 12

# Left-shift offsets: sequence occupies the low bits, node id above it, and the
# timestamp above that.
SEQUENCE_SHIFT = 0
NODE_ID_SHIFT = SEQUENCE_BITS
TIMESTAMP_SHIFT = SEQUENCE_BITS + NODE_ID_BITS

# Field maxima (inclusive).
MAX_NODE_ID = (1 << NODE_ID_BITS) - 1  # 1023
MAX_SEQUENCE = (1 << SEQUENCE_BITS) - 1  # 4095

# In-process monotonic guard: the last timestamp we emitted an id for (ms since
# EPOCH_MS) and the sequence counter within that millisecond. A simple lock keeps
# the pair consistent even if generate_id is ever called from multiple threads.
_lock = threading.Lock()
_last_ms = -1
_sequence = 0


def _now_ms() -> int:
    """Return the current wall-clock time in milliseconds since ``EPOCH_MS``."""
    return time.time_ns() // 1_000_000 - EPOCH_MS


def generate_id() -> int:
    """Return a fresh 64-bit snowflake id as a positive Python ``int``.

    Composes (ms since ``EPOCH_MS``) into the 41-bit timestamp field, the
    configured ``get_settings().node_id`` (read at call time) into the 10-bit
    node field, and a per-millisecond sequence counter into the low 12 bits.
    The sequence increments for repeated same-millisecond calls and spins to the
    next millisecond on overflow past ``MAX_SEQUENCE``; an in-process guard keeps
    the stream monotonic and unique within the single async process.
    """
    global _last_ms, _sequence

    node_id = get_settings().node_id & MAX_NODE_ID

    with _lock:
        now = _now_ms()

        # Never emit a smaller timestamp than the last one: if the clock went
        # backwards, clamp to the last observed millisecond so ids stay
        # monotonically non-decreasing.
        if now < _last_ms:
            now = _last_ms

        if now == _last_ms:
            _sequence += 1
            if _sequence > MAX_SEQUENCE:
                # Sequence exhausted for this millisecond — spin-wait for the
                # clock to advance, then reset the sequence.
                while now <= _last_ms:
                    now = _now_ms()
                _sequence = 0
        else:
            _sequence = 0

        _last_ms = now
        sequence = _sequence

    return (
        (now << TIMESTAMP_SHIFT)
        | (node_id << NODE_ID_SHIFT)
        | (sequence << SEQUENCE_SHIFT)
    )
