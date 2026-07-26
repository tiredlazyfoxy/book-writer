"""Tests for the ``<think>`` splitter (feature 011, step 003, DoD-1).

Bound to the frozen skeleton (status.md -> Skeleton -> Step 003), in
``app.services.chat_turn``:
    class ThinkSplitter  __init__(self) -> None
        def feed(self, chunk: str) -> list[tuple[Channel, str]]
        def flush(self) -> list[tuple[Channel, str]]
    CHANNEL_THINKING: Channel = "thinking"
    CHANNEL_CONTENT:  Channel = "content"

The splitter is a plain stateful object; it is exercised directly (no turn, no
db, no network -- 003.context.md -> "Testing this step without a network").

Expected values come from the SPEC ONLY: the step DoD-1 adversarial-chunking
list and the Interface intent's end-of-stream rules -- "an unclosed ``<think>``
leaves the remaining text on the thinking channel, and a held-back partial that
turns out not to be a tag is flushed verbatim" -- never from implementation
internals. The two invariants under test in every case: each surviving segment is
on the correct channel, and **no character of the payload is lost or duplicated**
(the concatenation of all emitted text equals the original stream with the tag
markers removed).

These are synchronous tests; ``asyncio_mode = "auto"`` is irrelevant here.
"""

from app.services.chat_turn import (
    CHANNEL_CONTENT as C,
    CHANNEL_THINKING as T,
    ThinkSplitter,
)


# ---------------------------------------------------------------------------
# Helpers: drive the splitter and normalise its output for assertion.
# ---------------------------------------------------------------------------


def _collect(chunks: list[str]) -> list[tuple[str, str]]:
    """Feed every chunk then flush; return non-empty ``(channel, text)`` pairs.

    Empty-text emissions (harmless, format-dependent) are dropped so the test
    couples to *what* is emitted on *which* channel, not to per-chunk emission
    granularity.
    """
    splitter = ThinkSplitter()
    out: list[tuple[str, str]] = []
    for chunk in chunks:
        out.extend(splitter.feed(chunk))
    out.extend(splitter.flush())
    return [(ch, txt) for (ch, txt) in out if txt != ""]


def _merge(pairs: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Coalesce consecutive same-channel segments (segmentation is not pinned)."""
    merged: list[tuple[str, str]] = []
    for ch, txt in pairs:
        if merged and merged[-1][0] == ch:
            merged[-1] = (ch, merged[-1][1] + txt)
        else:
            merged.append((ch, txt))
    return merged


def _assert_lossless(chunks: list[str], collected: list[tuple[str, str]]) -> None:
    """No character lost or duplicated: emitted text == original minus tag markers."""
    original = "".join(chunks)
    expected_text = original.replace("<think>", "").replace("</think>", "")
    assert "".join(txt for _ch, txt in collected) == expected_text


# ---------------------------------------------------------------------------
# DoD-1 — adversarial chunkings; correct channel routing, no loss/duplication
# ---------------------------------------------------------------------------


# DoD-1 (UC-054): an opening tag split across two deltas is still recognised;
# the reasoning payload lands on the thinking channel and the surrounding text on
# content, with nothing lost across the boundary.
def test_tag_split_across_two_deltas__DoD1_UC054():
    chunks = ["Hello <thi", "nk>secret</think>bye"]
    collected = _collect(chunks)
    assert _merge(collected) == [(C, "Hello "), (T, "secret"), (C, "bye")]
    _assert_lossless(chunks, collected)


# DoD-1 (UC-054): a tag glued to payload text on BOTH sides inside a single delta
# (a naive per-chunk split() would mis-handle this) routes each side correctly.
def test_tag_glued_to_payload_within_one_delta__DoD1_UC054():
    chunks = ["a<think>b</think>c"]
    collected = _collect(chunks)
    assert _merge(collected) == [(C, "a"), (T, "b"), (C, "c")]
    _assert_lossless(chunks, collected)


# DoD-1 (UC-054): several think blocks in one stream alternate channels correctly.
def test_several_think_blocks_in_one_stream__DoD1_UC054():
    chunks = ["x<think>1</think>y<think>2</think>z"]
    collected = _collect(chunks)
    assert _merge(collected) == [
        (C, "x"),
        (T, "1"),
        (C, "y"),
        (T, "2"),
        (C, "z"),
    ]
    _assert_lossless(chunks, collected)


# DoD-1 (UC-054): a stream that opens directly with a think block emits the
# reasoning on the thinking channel and the trailing text on content.
def test_stream_opens_with_thinking__DoD1_UC054():
    chunks = ["<think>only</think>tail"]
    collected = _collect(chunks)
    assert _merge(collected) == [(T, "only"), (C, "tail")]
    _assert_lossless(chunks, collected)


# DoD-1 (UC-054): a stream with no tags at all is entirely content, unchanged.
def test_no_tags_is_all_content__DoD1_UC054():
    chunks = ["just plain content, no markers"]
    collected = _collect(chunks)
    assert _merge(collected) == [(C, "just plain content, no markers")]
    _assert_lossless(chunks, collected)


# DoD-1 (UC-054; Interface intent end-of-stream rule): an unclosed <think> at end
# of stream leaves the remaining text on the thinking channel after flush.
def test_unclosed_tag_at_end_of_stream__DoD1_UC054():
    chunks = ["before<think>after"]
    collected = _collect(chunks)
    assert _merge(collected) == [(C, "before"), (T, "after")]
    _assert_lossless(chunks, collected)


# DoD-1 (Interface intent end-of-stream rule): a held-back trailing partial that
# turns out NOT to be a tag is flushed verbatim -- the "<" survives on content.
def test_held_back_partial_not_a_tag_flushed_verbatim__DoD1_UC054():
    chunks = ["abc<"]
    collected = _collect(chunks)
    assert _merge(collected) == [(C, "abc<")]
    _assert_lossless(chunks, collected)


# DoD-1 (UC-054): a false tag-prefix straddling a chunk boundary ("<t" then "bc")
# is not a tag; the held-back text is released verbatim, nothing lost.
def test_false_prefix_across_boundary_flushed_verbatim__DoD1_UC054():
    chunks = ["a<t", "bc"]
    collected = _collect(chunks)
    assert _merge(collected) == [(C, "a<tbc")]
    _assert_lossless(chunks, collected)
