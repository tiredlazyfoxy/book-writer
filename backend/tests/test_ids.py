"""Tests for app.ids — the cross-cutting snowflake id generator (fast/001).

Bound to the frozen skeleton signatures (status.md -> Skeleton):
    EPOCH_MS = 1704067200000                              in app.ids
    TIMESTAMP_BITS = 41, NODE_ID_BITS = 10, SEQUENCE_BITS = 12   in app.ids
    SEQUENCE_SHIFT = 0, NODE_ID_SHIFT = 12, TIMESTAMP_SHIFT = 22 in app.ids
    MAX_NODE_ID = 1023, MAX_SEQUENCE = 4095              in app.ids
    def generate_id() -> int                             in app.ids
    class Settings(...) node_id field                    in app.settings
    get_settings() -> Settings  (lru_cache-wrapped)      in app.settings

Expected values come from the spec (plan DoD-1..DoD-3 + context "Settled design
facts"), never from implementation internals:
    - DoD-1: generate_id() returns strictly-positive 64-bit ids (high bit 0) and
      a large batch of rapid calls are all unique.
    - DoD-2: the 10-bit node field decoded (using the FROZEN bit-layout
      constants) from a generated id equals the configured BOOKWRITER_NODE_ID.
    - DoD-3: successive ids are monotonically non-decreasing and roughly
      time-ordered, and same-millisecond calls are all distinct (the sequence
      field distinguishes them).

These are synchronous tests (mirroring tests/test_settings.py): app.ids is a
domain-agnostic utility with no async surface. `get_settings()` is
lru_cache-wrapped, so the node-id case sets the env, clears the cache before
generating, and clears it again afterwards (the cache-clear idiom from
tests/test_startup_detection.py).
"""

import app.settings as settings_module
from app.ids import (
    NODE_ID_BITS,
    NODE_ID_SHIFT,
    generate_id,
)


def _decode_node_id(snowflake: int) -> int:
    """Extract the 10-bit node field from a snowflake id using the FROZEN
    bit-layout constants (no hardcoded shift values)."""
    return (snowflake >> NODE_ID_SHIFT) & ((1 << NODE_ID_BITS) - 1)


# DoD-1: generate_id() returns strictly positive ids (high/sign bit 0) that fit
# in 64 bits, and a large batch of rapid successive calls are all unique.
def test_generate_id_positive_64bit_and_unique__DoD1():
    ids = [generate_id() for _ in range(2000)]

    # Every id is strictly positive and fits in a signed 64-bit int (high bit 0).
    for value in ids:
        assert isinstance(value, int)
        assert value > 0
        assert value < 2**63

    # A large batch of rapid successive calls is all unique.
    assert len(set(ids)) == len(ids)


# DoD-2: with BOOKWRITER_NODE_ID set (and the settings cache cleared), the 10-bit
# node-id field decoded from a generated id equals the configured node id.
def test_node_id_field_matches_configured_node__DoD2(monkeypatch):
    chosen_node_id = 7
    monkeypatch.setenv("BOOKWRITER_NODE_ID", str(chosen_node_id))

    # Clear the lru_cache so the override is picked up before generating.
    settings_module.get_settings.cache_clear()
    try:
        snowflake = generate_id()
    finally:
        # Restore: drop the cache holding the overridden Settings instance so
        # later tests see the default node id again.
        settings_module.get_settings.cache_clear()

    # The node field decoded from the id (via the frozen constants) equals the
    # configured node id.
    assert _decode_node_id(snowflake) == chosen_node_id


# DoD-3: successive generate_id() calls are monotonically non-decreasing and
# roughly time-ordered, and two calls within the same millisecond produce
# different ids (the sequence field distinguishes them).
def test_ids_monotonic_and_same_ms_distinct__DoD3():
    ids = [generate_id() for _ in range(1000)]

    # Monotonically non-decreasing: each id is >= the previous one, so an id
    # generated later is >= one generated earlier (roughly time-ordered).
    for previous, current in zip(ids, ids[1:]):
        assert current >= previous

    # Even calls landing in the same millisecond are all distinct — the
    # per-millisecond sequence field distinguishes them.
    assert len(set(ids)) == len(ids)
