"""Tests for the system-prompt composer (feature 011, step 002).

Bound to the frozen skeleton signatures (status.md -> Skeleton -> Step 002):

    app.services.prompt_composition  (NEW):
        BASE_SYSTEM_PROMPT: str
            # populated, non-empty constant (exact text unpinned by any DoD).
        def compose_system_prompt(
            base: str | None = None,
            mode: str | None = None,
            book: str | None = None,
            chapter: str | None = None,
        ) -> str

Expected values come from the SPEC ONLY — the step DoD (DoD-1, DoD-2), the step
Interface intent, and `assistant-config.md` -> "System-prompt composition" — never
from implementation internals.

Key spec facts asserted here:
    - The composer emits the non-empty layers in the FIXED order
      base -> mode -> book -> chapter, each as its own section (DoD-1).
    - An empty, whitespace-only or absent layer contributes NOTHING — no section,
      no separator, no blank block; whitespace-only counts as empty (DoD-2).
    - Only base + book (this feature's only live case) yields exactly two
      sections; composing nothing yields the empty string (DoD-2).

The EXACT delimiter / label format is NOT pinned by the spec (the skeleton owns
it as declarative content), so these tests assert the *behaviour* the spec fixes
— ordering, presence/absence, and that a skipped layer leaves output identical to
omitting it — never a literal delimiter or header string.

The composer is pure (takes strings, reads no DB), so no fixtures are needed.
Sentinels are chosen so they cannot collide with any plausible label/delimiter.
"""

from app.services.prompt_composition import BASE_SYSTEM_PROMPT, compose_system_prompt

# Distinct sentinels — one per layer. Chosen to be improbable substrings of any
# section label or delimiter the composer might insert.
_BASE = "ZZBASELAYERZZ"
_MODE = "ZZMODELAYERZZ"
_BOOK = "ZZBOOKLAYERZZ"
_CHAP = "ZZCHAPTERLAYERZZ"


# DoD-1: the base prompt constant is populated and non-empty — it is the always-
# present layer this feature composes (context.md -> prompt layers table).
def test_base_system_prompt_is_nonempty__DoD1():
    assert isinstance(BASE_SYSTEM_PROMPT, str)
    assert BASE_SYSTEM_PROMPT.strip() != ""


# DoD-1: with all four layers non-empty, each appears in the output exactly once
# and in the fixed order base -> mode -> book -> chapter.
def test_composes_all_four_layers_in_fixed_order__DoD1():
    result = compose_system_prompt(
        base=_BASE, mode=_MODE, book=_BOOK, chapter=_CHAP
    )

    # Every layer is present...
    assert _BASE in result
    assert _MODE in result
    assert _BOOK in result
    assert _CHAP in result

    # ...each exactly once (its own single section, not duplicated).
    assert result.count(_BASE) == 1
    assert result.count(_MODE) == 1
    assert result.count(_BOOK) == 1
    assert result.count(_CHAP) == 1

    # ...and their first appearances are strictly ordered base < mode < book < chapter.
    assert (
        result.index(_BASE)
        < result.index(_MODE)
        < result.index(_BOOK)
        < result.index(_CHAP)
    )


# DoD-2: a whitespace-only layer contributes nothing — the output is byte-for-byte
# identical to omitting that layer entirely (no section, no separator, no blank
# block). Whitespace-only counts as empty.
def test_whitespace_layer_contributes_nothing__DoD2():
    with_whitespace = compose_system_prompt(
        base=_BASE, mode="   \t\n  ", book=_BOOK, chapter=None
    )
    without = compose_system_prompt(base=_BASE, mode=None, book=_BOOK, chapter=None)

    assert with_whitespace == without
    # The skipped layer left no trace.
    assert _MODE not in with_whitespace


# DoD-2: an empty-string layer likewise contributes nothing — identical to omitting it.
def test_empty_string_layer_contributes_nothing__DoD2():
    with_empty = compose_system_prompt(base=_BASE, mode="", book=_BOOK, chapter="")
    without = compose_system_prompt(base=_BASE, book=_BOOK)

    assert with_empty == without


# DoD-2: composing with only base and book (this feature's only live case) produces
# exactly two sections — the two given layers, in order, and nothing for the absent
# or empty mode/chapter slots.
def test_only_base_and_book_yields_exactly_two_sections__DoD2():
    result = compose_system_prompt(base=_BASE, book=_BOOK)

    # Both live layers present, in order, each once.
    assert _BASE in result and _BOOK in result
    assert result.count(_BASE) == 1
    assert result.count(_BOOK) == 1
    assert result.index(_BASE) < result.index(_BOOK)

    # The two unpopulated slots contributed nothing.
    assert _MODE not in result
    assert _CHAP not in result

    # Adding empty/whitespace mode and chapter changes nothing — no third or fourth
    # section, so the live case is exactly two sections.
    padded = compose_system_prompt(
        base=_BASE, mode="", book=_BOOK, chapter="   "
    )
    assert padded == result


# DoD-2: composing nothing (all layers absent) produces the empty string.
def test_all_absent_yields_empty_string__DoD2():
    assert compose_system_prompt() == ""


# DoD-2: composing with every layer empty or whitespace-only also produces the
# empty string — whitespace-only counts as empty across the board.
def test_all_empty_or_whitespace_yields_empty_string__DoD2():
    assert (
        compose_system_prompt(base="", mode="   ", book=None, chapter="\t\n") == ""
    )
