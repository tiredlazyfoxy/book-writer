"""System-prompt composition — the ``base → mode → book → chapter`` composer
(feature 011, step 002).

Pure and declarative: no I/O, no db reads. The composer takes four already-loaded
prompt strings and folds them into one system prompt; step 003 is what loads
``Book.system_prompt`` and hands it in. Keeping it string-in/string-out is what
makes the composition unit-testable with no fixtures.

Ordering argument (``assistant-config.md`` → "Why this order"): chapter *narrows*
book, so it must read after it; base identity leads, mode scopes it, book grounds
it, chapter focuses it. Only ``base`` and ``book`` are ever populated in this
feature (``context.md`` → "Prompt layers"); the composer still implements all four
positions and the skip rule because ``013.codex`` populates mode and the chapter
features populate chapter.

Skeleton (011 step 002): :data:`BASE_SYSTEM_PROMPT` is the frozen declarative
constant (non-empty, exact text unpinned); :func:`compose_system_prompt`'s
signature is frozen and its body is UNIMPLEMENTED.
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
    book: str | None = None,
    chapter: str | None = None,
) -> str:
    """Fold the four optional prompt layers into one system prompt.

    Renders each non-empty layer as its own delimited, labelled section in the
    fixed order base → mode → book → chapter. An empty, whitespace-only or absent
    layer contributes nothing at all — no section, no label, no separator, no
    blank block. All-empty (including no arguments) yields the empty string.

    Skeleton (011 step 002): UNIMPLEMENTED.
    """
    layers: list[tuple[str, str | None]] = [
        ("BASE", base),
        ("MODE", mode),
        ("BOOK", book),
        ("CHAPTER", chapter),
    ]
    sections: list[str] = []
    for label, text in layers:
        if text is None or not text.strip():
            continue
        sections.append(f"### {label}\n{text.strip()}")
    return "\n\n".join(sections)
