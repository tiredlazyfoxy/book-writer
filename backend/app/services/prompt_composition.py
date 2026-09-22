"""System-prompt composition — the ``base → mode → author → memos → chapter``
composer (feature 011, step 002; third layer repointed by feature 021, step 004;
fourth layer inserted by feature 026, step 006).

Pure and declarative: no I/O, no db reads. The composer takes five already-loaded
prompt strings and folds them into one system prompt; ``services/chat_turn.py`` is
what loads them and hands them in. Keeping it string-in/string-out is what makes
the composition unit-testable with no fixtures.

Ordering argument (``assistant-config.md`` → "Why this order"): chapter *narrows*
the layer above it, so it must read after it; base identity leads, mode scopes it,
the author's own instruction grounds it, the author's standing memos stand beside
that instruction at the same per-author-per-book scope, and chapter focuses it.
The composer implements all five positions and the skip rule regardless of which
are populated today.

Feature 021, step 004 changed the third layer in exactly two ways and nothing
else: the parameter is named for the **author** (it carries that author's own
``BookAuthorPrompt.system_prompt``, never the retired book-wide
``Book.system_prompt``) and its section label is ``AUTHOR``. The rendering, the
join, the blank-skip rule, the other three layers and the purity are unchanged.
There is deliberately **no** ``book=`` compatibility alias: a call still passing
the old keyword must fail rather than silently bind, so a half-finished rename
cannot ship (021 step 004, DoD-3).

Feature 026, step 006 added a **fifth** layer, ``memos``, at the **fourth**
position — between ``author`` and ``chapter`` — so the rendered order is ``BASE``,
``MODE``, ``AUTHOR``, ``MEMOS``, ``CHAPTER``. A memo is per-author-per-book, the
same scope as the ``AUTHOR`` layer, so it sits beside it, while the chapter prompt
stays the most-specific layer nearest the task. The layer is an **already-rendered
string** — one section's worth of text, composed by
``services/chat_turn.py:render_memos_section`` — so this module never receives a
list of memos and never learns what a memo is. The existing skip rule extends to
it unchanged, and the ``author`` parameter keeps its third position: the frozen
signature property is preserved, not broken (026 step 006, DoD-5).

Skeleton (011 step 002): :data:`BASE_SYSTEM_PROMPT` is the frozen declarative
constant (non-empty, exact text unpinned).

Skeleton (021 step 004): :func:`compose_system_prompt`'s signature is frozen with
``author`` in the third position. The third section **label** is behaviour, not
signature, and was left to the coder.

Skeleton (026 step 006): the signature is frozen again — ``author`` **still**
third, ``memos`` fourth, ``chapter`` fifth. There is still deliberately no
compatibility alias of any kind, for the new parameter or the moved one. The
fourth section's **label** and its rendered position are behaviour, not
signature, and are left to the coder.
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
    memos: str | None = None,
    chapter: str | None = None,
) -> str:
    """Fold the five optional prompt layers into one system prompt.

    Renders each non-empty layer as its own delimited, labelled section in the
    fixed order base → mode → author → memos → chapter. ``author`` is the calling
    author's own prompt for the book (``BookAuthorPrompt.system_prompt``, feature
    021), rendered under an ``AUTHOR`` heading. ``memos`` is that author's active
    memos for the book **already rendered into one section's text** by
    ``services/chat_turn.py`` (feature 026) — a plain string like every other
    layer. An empty, whitespace-only or absent layer contributes nothing at all —
    no section, no label, no separator, no blank block. All-empty (including no
    arguments) yields the empty string.

    Skeleton (021 step 004): the parameter rename is frozen.
    Skeleton (026 step 006): the signature is frozen with ``author`` third and
    ``memos`` fourth.
    """
    layers: list[tuple[str, str | None]] = [
        ("BASE", base),
        ("MODE", mode),
        # Feature 021, step 004: the third layer is the calling author's own
        # prompt for the book, so it is labelled for the author — never the
        # retired book-wide ``Book.system_prompt`` this replaced.
        ("AUTHOR", author),
        # Feature 026, step 006: the author's active memos, already rendered
        # into one section's text by ``services/chat_turn.py``. Same
        # per-author-per-book scope as the layer above, so it sits beside it and
        # before the most-specific chapter layer.
        ("MEMOS", memos),
        ("CHAPTER", chapter),
    ]
    sections: list[str] = []
    for label, text in layers:
        if text is None or not text.strip():
            continue
        sections.append(f"### {label}\n{text.strip()}")
    return "\n\n".join(sections)
