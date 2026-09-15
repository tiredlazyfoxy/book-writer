"""Tests for the system-prompt composer.

Originally feature 011, step 002. **Feature 021, step 004 renames the third
layer**: the composer's book parameter becomes ``author`` and its section label
becomes ``AUTHOR``. **Feature 026, step 006 inserts a FIFTH layer**: the author's
active memos render as a ``MEMOS`` section at position 4, so the order is now
base -> mode -> author -> memos -> chapter and the chapter layer is fifth.

Bound to the frozen skeleton signature (status.md -> Skeleton -> Step 006):

    app.services.prompt_composition:
        BASE_SYSTEM_PROMPT: str
            # populated, non-empty constant (exact text unpinned by any DoD).
        def compose_system_prompt(
            base: str | None = None,
            mode: str | None = None,
            author: str | None = None,
            memos: str | None = None,
            chapter: str | None = None,
        ) -> str

Expected values come from the SPEC ONLY — feature 011 step 002's DoD-1/DoD-2 (for
the pre-existing coverage), feature 021 step 004's DoD-1/DoD-2/DoD-3, feature 026
step 006's Interface intent + DoD-4/DoD-5, `021/context.md` decision 3,
`026/context.md` decision 7 and `assistant-config.md` -> "System-prompt
composition" — never from implementation internals.

Key spec facts asserted here:
    - The composer emits the non-empty layers in the FIXED order
      base -> mode -> author -> memos -> chapter, each as its own section.
    - Each surviving layer renders as ``### {LABEL}\\n{text.strip()}`` and the
      survivors are joined by a blank line; the third label is ``AUTHOR``.
    - An empty, whitespace-only or absent layer contributes NOTHING — no section,
      no separator, no blank block; whitespace-only counts as empty. The rule
      extends to the new memos layer unchanged.
    - There is no compatibility alias: the retired ``book=`` keyword raises
      ``TypeError`` rather than silently binding (021 step 004, DoD-3) — and 026
      adds no alias for the inserted or the moved layer either.
    - ``author`` is still the THIRD positional parameter (026 step 006, DoD-5) —
      a property this feature preserves rather than breaks.

The composer is pure (takes strings, reads no DB), so no fixtures are needed.
Sentinels are chosen so they cannot collide with any plausible label/delimiter.

NOTE on DoD ids: this file keeps its own historical numbering. Names ending
``__DoD1``/``__DoD2`` carry feature 011 step 002's ids and ``__DoD3`` carries
feature 021 step 004's id, including where feature 026 step 006 rewrote the
assertion to the five-layer fact. Step 006's own numbering lives in
``tests/services/test_memo_prompt_composition.py``.
"""

import inspect

import pytest

from app.services.prompt_composition import BASE_SYSTEM_PROMPT, compose_system_prompt

# Distinct sentinels — one per layer. Chosen to be improbable substrings of any
# section label or delimiter the composer might insert.
_BASE = "ZZBASELAYERZZ"
_MODE = "ZZMODELAYERZZ"
_AUTHOR = "ZZAUTHORLAYERZZ"
_MEMOS = "ZZMEMOSLAYERZZ"
_CHAP = "ZZCHAPTERLAYERZZ"


# DoD-1 (feature 011 step 002): the base prompt constant is populated and
# non-empty — it is the always-present layer this feature composes.
def test_base_system_prompt_is_nonempty__DoD1():
    assert isinstance(BASE_SYSTEM_PROMPT, str)
    assert BASE_SYSTEM_PROMPT.strip() != ""


# DoD-1 (feature 011 step 002): with all layers non-empty, each appears in the
# output exactly once and in the fixed order. (The third layer was `book=` until
# feature 021 step 004 renamed it; feature 026 step 006 inserted `memos` at
# position 4, so there are now FIVE layers and `chapter` is last.)
def test_composes_all_five_layers_in_fixed_order__DoD1():
    result = compose_system_prompt(
        base=_BASE, mode=_MODE, author=_AUTHOR, memos=_MEMOS, chapter=_CHAP
    )

    # Every layer is present...
    assert _BASE in result
    assert _MODE in result
    assert _AUTHOR in result
    assert _MEMOS in result
    assert _CHAP in result

    # ...each exactly once (its own single section, not duplicated).
    assert result.count(_BASE) == 1
    assert result.count(_MODE) == 1
    assert result.count(_AUTHOR) == 1
    assert result.count(_MEMOS) == 1
    assert result.count(_CHAP) == 1

    # ...and their first appearances are strictly ordered base < mode < author <
    # memos < chapter.
    assert (
        result.index(_BASE)
        < result.index(_MODE)
        < result.index(_AUTHOR)
        < result.index(_MEMOS)
        < result.index(_CHAP)
    )


# DoD-2 (feature 011 step 002): a whitespace-only layer contributes nothing — the
# output is byte-for-byte identical to omitting that layer entirely (no section,
# no separator, no blank block). Whitespace-only counts as empty.
def test_whitespace_layer_contributes_nothing__DoD2():
    with_whitespace = compose_system_prompt(
        base=_BASE, mode="   \t\n  ", author=_AUTHOR, chapter=None
    )
    without = compose_system_prompt(base=_BASE, mode=None, author=_AUTHOR, chapter=None)

    assert with_whitespace == without
    # The skipped layer left no trace.
    assert _MODE not in with_whitespace


# DoD-2 (feature 011 step 002): an empty-string layer likewise contributes
# nothing — identical to omitting it.
def test_empty_string_layer_contributes_nothing__DoD2():
    with_empty = compose_system_prompt(base=_BASE, mode="", author=_AUTHOR, chapter="")
    without = compose_system_prompt(base=_BASE, author=_AUTHOR)

    assert with_empty == without


# DoD-2 (feature 011 step 002): composing with only base and the author layer
# produces exactly two sections — the two given layers, in order, and nothing for
# the absent or empty mode/chapter slots.
def test_only_base_and_author_yields_exactly_two_sections__DoD2():
    result = compose_system_prompt(base=_BASE, author=_AUTHOR)

    # Both live layers present, in order, each once.
    assert _BASE in result and _AUTHOR in result
    assert result.count(_BASE) == 1
    assert result.count(_AUTHOR) == 1
    assert result.index(_BASE) < result.index(_AUTHOR)

    # The unpopulated slots contributed nothing.
    assert _MODE not in result
    assert _MEMOS not in result
    assert _CHAP not in result

    # Adding empty/whitespace mode, memos and chapter changes nothing — no third,
    # fourth or fifth section, so the live case is exactly two sections.
    padded = compose_system_prompt(
        base=_BASE, mode="", author=_AUTHOR, memos="\t", chapter="   "
    )
    assert padded == result


# DoD-2 (feature 011 step 002): composing nothing (all layers absent) produces the
# empty string.
def test_all_absent_yields_empty_string__DoD2():
    assert compose_system_prompt() == ""


# DoD-2 (feature 011 step 002): composing with every layer empty or
# whitespace-only also produces the empty string — whitespace-only counts as
# empty across the board.
def test_all_empty_or_whitespace_yields_empty_string__DoD2():
    assert (
        compose_system_prompt(
            base="", mode="   ", author=None, memos="  \n ", chapter="\t\n"
        )
        == ""
    )


# ---------------------------------------------------------------------------
# 021 step 004, DoD-1 — the author layer renders under an `AUTHOR` heading,
# after the mode layer and before the chapter layer
# ---------------------------------------------------------------------------


# 021 step 004 DoD-1 (Interface intent; context.md decision 3): the author's text
# renders as its own section under an `AUTHOR` heading, positioned after the mode
# layer and before the chapter layer. The rendering is
# `### {LABEL}\n{text.strip()}`, survivors joined by a blank line.
def test_author_layer_renders_under_author_heading__DoD1():
    result = compose_system_prompt(
        base="B TEXT", mode="M TEXT", author="A TEXT", chapter="C TEXT"
    )

    assert result == (
        "### BASE\nB TEXT\n\n"
        "### MODE\nM TEXT\n\n"
        "### AUTHOR\nA TEXT\n\n"
        "### CHAPTER\nC TEXT"
    )


# 021 step 004 DoD-1: the heading is `AUTHOR` and the retired `BOOK` heading is
# gone — a half-finished rename that still emits the old label is caught here.
def test_author_heading_replaces_the_book_heading__DoD1():
    result = compose_system_prompt(base=_BASE, mode=_MODE, author=_AUTHOR, chapter=_CHAP)

    assert "### AUTHOR" in result
    assert "BOOK" not in result
    # The heading immediately precedes the author's own text.
    assert f"### AUTHOR\n{_AUTHOR}" in result


# 021 step 004 DoD-1: the author section sits between the mode section and the
# chapter section, and the other three layers keep their labels and order.
def test_author_section_sits_between_mode_and_chapter__DoD1():
    result = compose_system_prompt(base=_BASE, mode=_MODE, author=_AUTHOR, chapter=_CHAP)

    assert (
        result.index("### BASE")
        < result.index("### MODE")
        < result.index("### AUTHOR")
        < result.index("### CHAPTER")
    )


# 021 step 004 DoD-1: the author's text is stripped before rendering, exactly as
# every other layer is — surrounding whitespace never leaks into the section.
def test_author_text_is_stripped_in_its_section__DoD1():
    padded = compose_system_prompt(base="B TEXT", author="  \n A TEXT \t ")
    tight = compose_system_prompt(base="B TEXT", author="A TEXT")

    assert padded == tight
    assert padded == "### BASE\nB TEXT\n\n### AUTHOR\nA TEXT"


# ---------------------------------------------------------------------------
# 021 step 004, DoD-2 — a blank / whitespace-only / absent author prompt
# contributes no heading, no section and no extra separator
# ---------------------------------------------------------------------------


# 021 step 004 DoD-2: a blank, whitespace-only or absent author prompt leaves the
# surrounding layers rendering exactly as they would with the argument omitted —
# no heading, no section, no extra separator.
@pytest.mark.parametrize(
    "author_value",
    [None, "", "   ", "\t", "\n\t  \n"],
    ids=["none", "empty", "spaces", "tab", "mixed_ws"],
)
def test_blank_author_contributes_nothing__DoD2(author_value):
    with_blank = compose_system_prompt(
        base=_BASE, mode=_MODE, author=author_value, chapter=_CHAP
    )
    omitted = compose_system_prompt(base=_BASE, mode=_MODE, chapter=_CHAP)

    assert with_blank == omitted
    assert "AUTHOR" not in with_blank
    # The surviving layers are untouched, in order, each once.
    assert with_blank.count(_MODE) == 1
    assert with_blank.count(_CHAP) == 1
    assert with_blank.index(_MODE) < with_blank.index(_CHAP)


# 021 step 004 DoD-2: with only the base layer alive, a blank author prompt adds
# no trailing separator — the output is exactly the base section.
def test_blank_author_adds_no_trailing_separator__DoD2():
    assert compose_system_prompt(base="B TEXT", author="   ") == "### BASE\nB TEXT"
    assert compose_system_prompt(base="B TEXT", author=None) == "### BASE\nB TEXT"


# 021 step 004 DoD-2: an author prompt that is the only argument and is blank
# composes to the empty string.
def test_blank_author_alone_yields_empty_string__DoD2():
    assert compose_system_prompt(author="") == ""
    assert compose_system_prompt(author="  \n ") == ""


# ---------------------------------------------------------------------------
# 021 step 004, DoD-3 — the parameter is named for the author; the old keyword
# fails rather than silently binding
# ---------------------------------------------------------------------------


# 021 step 004 DoD-3 (the anti-half-rename guard): the retired `book=` keyword
# raises TypeError instead of binding — there is deliberately no compatibility
# alias, so a half-finished rename cannot ship.
def test_old_book_keyword_raises_type_error__DoD3():
    with pytest.raises(TypeError):
        compose_system_prompt(base=_BASE, book=_AUTHOR)

    with pytest.raises(TypeError):
        compose_system_prompt(book=_AUTHOR)


# 021 step 004 DoD-3: the third parameter is named `author`, is keyword-bindable,
# and no `book` parameter (nor a **kwargs catch-all that would swallow it)
# survives. Feature 026 step 006 inserted `memos` fourth and moved `chapter` to
# fifth; `author` stays third, and there is still no alias of any kind.
def test_third_parameter_is_named_author__DoD3():
    params = inspect.signature(compose_system_prompt).parameters

    assert "author" in params
    assert "book" not in params
    assert list(params) == ["base", "mode", "author", "memos", "chapter"]
    assert not any(
        p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values()
    )

    # Binding by the new keyword works and reaches the third layer.
    assert compose_system_prompt(author="A TEXT") == "### AUTHOR\nA TEXT"


# 021 step 004 DoD-3, preserved by 026 step 006: the third positional argument is
# still the author's layer. `base` and `mode` keep positions 1 and 2; the fourth
# positional is now the memos layer and the fifth is the chapter layer.
def test_third_positional_argument_is_the_author_layer__DoD3():
    positional = compose_system_prompt("B TEXT", "M TEXT", "A TEXT")

    assert positional == compose_system_prompt(
        base="B TEXT", mode="M TEXT", author="A TEXT"
    )
    assert positional == "### BASE\nB TEXT\n\n### MODE\nM TEXT\n\n### AUTHOR\nA TEXT"
    assert "### AUTHOR\nA TEXT" in positional

    full = compose_system_prompt("B TEXT", "M TEXT", "A TEXT", "ME TEXT", "C TEXT")

    assert full == compose_system_prompt(
        base="B TEXT",
        mode="M TEXT",
        author="A TEXT",
        memos="ME TEXT",
        chapter="C TEXT",
    )
    assert "### AUTHOR\nA TEXT" in full
