"""System-prompt composition — the ``base → mode → author → chapter`` composer
(feature 011, step 002; third layer repointed by feature 021, step 004).

Pure and declarative: no I/O, no db reads. The composer takes four already-loaded
prompt strings and folds them into one system prompt; ``services/chat_turn.py`` is
what loads them and hands them in. Keeping it string-in/string-out is what makes
the composition unit-testable with no fixtures.

Ordering argument (``assistant-config.md`` → "Why this order"): chapter *narrows*
the layer above it, so it must read after it; base identity leads, mode scopes it,
the author's own instruction grounds it, chapter focuses it. The composer
implements all four positions and the skip rule regardless of which are populated
today (``chat_turn.py`` still passes no ``chapter``).

Feature 021, step 004 changed the third layer in exactly two ways and nothing
else: the parameter is named for the **author** (it carries that author's own
``BookAuthorPrompt.system_prompt``, never the retired book-wide
``Book.system_prompt``) and its section label is ``AUTHOR``. The rendering, the
join, the blank-skip rule, the other three layers and the purity are unchanged.
There is deliberately **no** ``book=`` compatibility alias: a call still passing
the old keyword must fail rather than silently bind, so a half-finished rename
cannot ship (021 step 004, DoD-3).

Skeleton (011 step 002): :data:`BASE_SYSTEM_PROMPT` is the frozen declarative
constant (non-empty, exact text unpinned).

Skeleton (021 step 004): :func:`compose_system_prompt`'s signature is frozen with
``author`` in the third position. The third section **label** is behaviour, not
signature, and was left to the coder.
"""

# The app-level assistant identity — the ``base`` layer, always populated. Its
# exact wording is not pinned by any DoD (only that it is non-empty); step 003
# passes it as the first layer to :func:`compose_system_prompt`.
BASE_SYSTEM_PROMPT = (
    "You are BookWriter's authoring assistant. You help the author develop, "
    "structure and refine long-form written works. Be precise, stay grounded in "
    "the material you are given, and defer to the author's intent."
)


def compose_system_prompt(
    base: str | None = None,
    mode: str | None = None,
    author: str | None = None,
    chapter: str | None = None,
) -> str:
    """Fold the four optional prompt layers into one system prompt.

    Renders each non-empty layer as its own delimited, labelled section in the
    fixed order base → mode → author → chapter. ``author`` is the calling
    author's own prompt for the book (``BookAuthorPrompt.system_prompt``, feature
    021), rendered under an ``AUTHOR`` heading. An empty, whitespace-only or
    absent layer contributes nothing at all — no section, no label, no separator,
    no blank block. All-empty (including no arguments) yields the empty string.

    Skeleton (021 step 004): the parameter rename is frozen.
    """
    layers: list[tuple[str, str | None]] = [
        ("BASE", base),
        ("MODE", mode),
        # Feature 021, step 004: the third layer is the calling author's own
        # prompt for the book, so it is labelled for the author — never the
        # retired book-wide ``Book.system_prompt`` this replaced.
        ("AUTHOR", author),
        ("CHAPTER", chapter),
    ]
    sections: list[str] = []
    for label, text in layers:
        if text is None or not text.strip():
            continue
        sections.append(f"### {label}\n{text.strip()}")
    return "\n\n".join(sections)
