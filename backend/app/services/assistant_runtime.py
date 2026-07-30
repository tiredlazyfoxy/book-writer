"""FEAT-020 runtime policy — subject → mode → prompt layer + tool allowlist
(feature 013, step 007).

Business-logic layer: **no** ``session`` / ``AsyncSession`` / ``select()`` /
``session.exec()`` / ``session.add()`` here (``docs/architecture/backend.md`` —
layer separation). Everything is read through the session-free ``app.db``
modules the FEAT-020 tables already ship
(:mod:`app.db.assistant_modes`, :mod:`app.db.mode_tools`,
:mod:`app.db.codex_entries`).

**This module never touches ``services/assistant_config.py``** — that module is
``012.assistant-config-editor``'s to create and is deliberately unbuilt
(``013.codex/context.md`` → "This feature does NOT depend on feature 012's
code"). The one contract inherited from ``012`` is its settled rule: **zero
``mode_tool`` rows is an empty allowlist, not the whole registry.**

The policy, in one place:

- a turn carries the working page's content-pane subject (``TurnRequest``'s
  ``subject_kind`` / ``subject_id`` / ``codex_kind``);
- :func:`resolve_subject` turns that into a :class:`ResolvedSubject` — loading
  the codex row when the subject names one, loading the **chapter** row when it
  names one (015 step 009), and refusing to look at either belonging to another
  book (US-085.AC-1);
- :func:`determine_mode` maps the resolved subject onto one of FEAT-020's mode
  keys (``assistant-config.md`` → "Mode determination"): the three codex kinds,
  plus — as of 015 step 009 — an ``open`` chapter to ``write-chapter`` and a
  ``closing`` chapter to ``close-chapter``. Every other subject resolves to
  **no mode**;
- :func:`mode_system_prompt` is the ``mode=`` layer
  ``services/prompt_composition.py`` already composes but nothing populated
  before this step (US-110.AC-3 / US-110.AC-4);
- :func:`allowed_tool_names` is the gate that replaces ``011.chat-panel``'s
  ``resolve_tools(None)`` seam (US-111.AC-2), with :data:`BASE_TOOL_NAMES` as
  the no-mode allowlist per ``context.md`` decision 6;
- :func:`resolve_turn_tools` is tool resolution's **second half** (013 step
  008): the real ``TOOL_REGISTRY`` tools the allowlist selects **plus** the
  mode's synthetic sub-agent delegation tools, so ``chat_turn`` has exactly one
  place to ask "what tools does this turn have" and hands one combined list to
  ``build_tool_bindings``.

The functions' no-subject / no-mode branches are *preserved existing behaviour* —
they are the path every ``011.chat-panel`` turn takes and answer exactly as it
shipped (DoD-13).
"""

from dataclasses import dataclass, replace

from app.db import assistant_modes, chapters, codex_entries, mode_tools
from app.models.chapter import Chapter, ChapterState
from app.models.codex_entry import CodexEntry, CodexKind
from app.models.schemas.chats import SubjectKind
from app.services import authz
from app.services import subagent_delegation
from app.services import tools as tools_service
from app.services.tools import ToolDef

# The allowlist for a subject that has **no** mode — book state, any of the
# lists, and the chats view (``context.md`` decision 6: a null mode is NOT "the
# whole registry"). Code-defined, never persisted: without it, wiring real
# ``mode_tool`` gating would silently strip web search from the chats view that
# ``011.chat-panel`` shipped. Today it happens to equal the whole
# ``services/tools.py:TOOL_REGISTRY``, which is why 011's turns are unaffected;
# it stops being equal the moment step 009 adds registry entries.
BASE_TOOL_NAMES: tuple[str, ...] = ("web_search",)


@dataclass(frozen=True)
class ResolvedSubject:
    """The turn's content-pane subject, resolved.

    A frozen typed record (no free dictionaries — the
    ``services/tools.py:ToolDef`` / ``db/vector.py:ChunkHit`` precedent):

    - ``kind`` — the subject kind the request named, or ``None`` when the turn
      carried no subject at all (also the result of naming a codex entry that
      does not resolve inside this book — see :func:`resolve_subject`).
    - ``entry`` — the loaded :class:`~app.models.codex_entry.CodexEntry` row when
      the subject is an **existing** codex entry; ``None`` otherwise, including
      for UC-076's blank entry that has no row yet.
    - ``chapter`` — the loaded :class:`~app.models.chapter.Chapter` row when the
      subject is a chapter of **this** book (015 step 009); ``None`` otherwise.
      The chapter twin of ``entry``, and it is loaded by the same resolution
      step for the same reason: a ``subject_id`` naming a chapter in another
      book must resolve to **no subject at all**, refused by resolution rather
      than by a later check, so no cross-book row is ever read. Its ``state`` is
      what :func:`determine_mode` maps onto the chapter modes.
    - ``mode_key`` — the FEAT-020 :class:`~app.models.assistant_mode.AssistantMode`
      key this subject resolves to, or ``None`` for a subject outside the mode
      set. Populated from :func:`determine_mode`.

    Every field defaults to ``None`` so :data:`NO_SUBJECT` and the two-phase
    build inside :func:`resolve_subject` (resolve the subject, then attach the
    mode) both read plainly.
    """

    kind: SubjectKind | None = None
    entry: CodexEntry | None = None
    chapter: Chapter | None = None
    mode_key: str | None = None


# The "this turn has no subject" value. A shared frozen instance, used as
# ``chat_turn.TurnContext``'s default so a ``TurnRequest`` carrying no subject
# fields (every 011 turn) needs no null handling downstream.
NO_SUBJECT: ResolvedSubject = ResolvedSubject()


# ``assistant-config.md``'s mode-determination table, the half this feature owns:
# the three codex kinds. Keyed by the enum's **wire value** so a row whose
# ``kind`` came back as a bare string rather than an enum member still maps
# (``services/codex_index.py``'s precedent). The chapter rows of that table —
# ``write-chapter`` / ``close-chapter`` — belong to ``015`` / ``016`` and are
# deliberately absent, so a chapter subject resolves to no mode here.
_CODEX_KIND_MODES: dict[str, str] = {
    CodexKind.character.value: "edit-character",
    CodexKind.location.value: "edit-location",
    CodexKind.fact.value: "edit-fact",
}


# ``assistant-config.md``'s mode-determination table, the **chapter** half (015
# step 009). The two mode keys live here as a constant beside
# :data:`_CODEX_KIND_MODES` rather than inline in :func:`determine_mode`, for the
# same reason the codex mapping does: the table is data, and both halves of it
# should read the same way.
#
# Keyed by the enum's **wire value** (the ``_CODEX_KIND_MODES`` precedent) so a
# row whose ``state`` came back as a bare string still maps.
#
# ``planned`` and ``closed`` are **deliberately absent** — a missing key is *no
# mode*, because FEAT-020's five modes name five activities and neither
# "planned" nor "closed" is one of them. The consequence is
# :data:`BASE_TOOL_NAMES`, not an empty allowlist (see
# :func:`allowed_tool_names`).
#
# Both keys are already seeded rows: ``db/assistant_modes.py``'s fixed five are
# written by ``seed_default_modes()``. **This module seeds nothing.**
_CHAPTER_STATE_MODES: dict[str, str] = {
    ChapterState.open.value: "write-chapter",
    ChapterState.closing.value: "close-chapter",
}


def _mode_for_codex_kind(kind: CodexKind | None) -> str | None:
    """The mode key for a codex ``kind``, or ``None`` (absent / unmapped kind)."""
    if kind is None:
        return None
    value = kind.value if isinstance(kind, CodexKind) else str(kind)
    return _CODEX_KIND_MODES.get(value)


def _mode_for_chapter_state(state: ChapterState | str | None) -> str | None:
    """The mode key for a chapter ``state``, or ``None``.

    ``open`` → ``"write-chapter"``, ``closing`` → ``"close-chapter"``, and
    ``planned`` / ``closed`` / an absent state → ``None`` (:data:`_CHAPTER_STATE_MODES`).
    The enum-or-string tolerance is ``_mode_for_codex_kind``'s, for the same
    reason.
    """
    if state is None:
        return None
    value = state.value if isinstance(state, ChapterState) else str(state)
    return _CHAPTER_STATE_MODES.get(value)


async def _entry_within_book(
    access: authz.BookAccess, subject_id: str
) -> CodexEntry | None:
    """Load ``subject_id``'s codex row **if** it lives in ``access.book_id``.

    A non-numeric id, an unknown id and an entry belonging to a different book
    are all ``None`` — the same three-way rule as
    ``services/codex.py:_resolve_entry``, except that here it is not an error:
    the turn simply has no subject, and no cross-book content is ever loaded
    (US-085.AC-1).
    """
    try:
        entry_id = int(subject_id)
    except (TypeError, ValueError):
        return None
    entry = await codex_entries.get_by_id(entry_id)
    if entry is None or entry.book_id != access.book_id:
        return None
    return entry


async def _chapter_within_book(
    access: authz.BookAccess, subject_id: str
) -> Chapter | None:
    """Load ``subject_id``'s chapter row **if** it lives in ``access.book_id``.

    The chapter twin of :func:`_entry_within_book`, and deliberately the **same
    three-way rule**: a non-numeric id, an unknown id and a chapter belonging to
    a different book are all ``None``. It is not an error — the turn simply has
    no subject, and no cross-book row is ever read
    (``assistant-runtime.md``: *"a ``subject_id`` naming an entry in another book
    resolves to no subject, not to that entry's mode"*, applied to chapters).
    Read through ``db/chapters.get_by_id``.
    """
    try:
        chapter_id = int(subject_id)
    except (TypeError, ValueError):
        return None
    chapter = await chapters.get_by_id(chapter_id)
    if chapter is None or chapter.book_id != access.book_id:
        return None
    return chapter


async def resolve_subject(
    access: authz.BookAccess,
    subject_kind: SubjectKind | None = None,
    subject_id: str | None = None,
    codex_kind: CodexKind | None = None,
) -> ResolvedSubject:
    """Resolve a turn's three subject fields into a :class:`ResolvedSubject`.

    Rules (``context.md`` → "The shared-canvas write design" point 1; the step
    file's Interface intent):

    - a codex-entry subject **with** an id loads the row through
      ``db/codex_entries.get_by_id``; an entry belonging to a **different** book
      than ``access.book_id`` — like an unknown or non-numeric id — is treated as
      **no subject at all**, so no cross-book content is ever loaded
      (US-085.AC-1);
    - a codex-entry subject with **no** id is UC-076's blank entry: there is no
      row, so ``codex_kind`` from the request supplies the kind;
    - for an **existing** entry the **row's** ``kind`` wins and the request's
      ``codex_kind`` is ignored;
    - a **chapter** subject with an id loads the row through
      ``db/chapters.get_by_id`` (015 step 009); a chapter belonging to a
      **different** book — like an unknown or non-numeric id — is likewise **no
      subject at all**, so a cross-book chapter can never route a turn into a
      chapter mode. A chapter subject with **no** id keeps its pre-015
      behaviour: it resolves to itself with no row and therefore no mode;
    - every other kind resolves to itself with no row;
    - ``mode_key`` is filled from :func:`determine_mode`, except for the blank
      entry — it has no row for that pure function to read, so its mode comes
      straight off the request's ``codex_kind``.

    The no-subject branch below is **preserved behaviour** — a turn with no
    ``subject_kind`` has no subject and no mode, and that is the path every 011
    turn takes.
    """
    if subject_kind is None:
        return NO_SUBJECT

    entry: CodexEntry | None = None
    chapter: Chapter | None = None
    blank_kind: CodexKind | None = None
    if subject_kind == "codex-entry":
        if subject_id is None:
            # UC-076's blank entry: there is no row yet, so the request's
            # ``codex_kind`` is the only thing that can name the kind.
            blank_kind = codex_kind
        else:
            entry = await _entry_within_book(access, subject_id)
            if entry is None:
                # Another book's entry (or none at all) is no subject at all —
                # not this book's subject with a null row (US-085.AC-1).
                return NO_SUBJECT
    elif subject_kind == "chapter" and subject_id is not None:
        chapter = await _chapter_within_book(access, subject_id)
        if chapter is None:
            # Another book's chapter (or none at all) is no subject at all —
            # the cross-book read is refused by RESOLUTION, not by a later
            # check, exactly as the codex branch above refuses it.
            return NO_SUBJECT

    subject = ResolvedSubject(kind=subject_kind, entry=entry, chapter=chapter)
    if entry is None and blank_kind is not None:
        # A blank entry has no row for :func:`determine_mode` to read; its mode
        # comes off the request instead. For an **existing** entry this branch is
        # not taken, so the row's kind wins and ``codex_kind`` is ignored.
        return replace(subject, mode_key=_mode_for_codex_kind(blank_kind))
    return replace(subject, mode_key=determine_mode(subject))


def determine_mode(subject: ResolvedSubject) -> str | None:
    """Map a resolved ``subject`` onto a FEAT-020 mode key, or ``None``.

    ``assistant-config.md``'s mode-determination table, **both** halves as of 015
    step 009:

    - a codex entry of kind ``character`` → ``"edit-character"``, ``location`` →
      ``"edit-location"``, ``fact`` → ``"edit-fact"`` (:data:`_CODEX_KIND_MODES`);
    - a resolved **chapter** by its ``state``: ``open`` → ``"write-chapter"``,
      ``closing`` → ``"close-chapter"`` (:data:`_CHAPTER_STATE_MODES`), and
      ``planned`` / ``closed`` → **no mode**, because neither is an activity
      FEAT-020 names.

    **Every other subject, and the absence of a subject, resolves to no mode.**
    No mode means :data:`BASE_TOOL_NAMES` — *not* an empty allowlist — which is
    the load-bearing half of tool gating's three cases.

    Synchronous and pure: it reads only the record it is handed (an existing
    entry's kind comes off ``subject.entry``, a resolved chapter's state off
    ``subject.chapter``; a blank entry's kind comes off what
    :func:`resolve_subject` recorded). The returned key is one of
    ``db/assistant_modes.py:DEFAULT_MODE_KEYS`` — every one of them an
    **already-seeded** row; nothing here seeds anything.

    The final fall-through is "this subject resolved to **nothing at all**", not
    "this subject has no codex entry": ``entry`` and ``chapter`` are twins and a
    chapter subject carries a null ``entry`` by construction, so keying the
    guard off ``entry`` alone would make the chapter branch unreachable while
    every codex case still answered correctly. (UC-076's blank entry has neither
    row; :func:`resolve_subject` attaches its mode from the request's
    ``codex_kind`` before this function could help.)
    """
    if subject.entry is not None:
        return _mode_for_codex_kind(subject.entry.kind)
    if subject.chapter is not None:
        return _mode_for_chapter_state(subject.chapter.state)
    return None


async def mode_system_prompt(mode_key: str | None) -> str | None:
    """Return ``mode_key``'s ``AssistantMode.system_prompt``, or ``None``.

    ``None`` — meaning *this turn contributes no mode layer* — when ``mode_key``
    is absent, when no row carries that key, or when the stored prompt is null,
    empty or whitespace-only (US-110.AC-4: an empty prompt contributes **no
    section**, no header and no blank block; the composer's own skip rule agrees,
    so both ends are safe). Read through ``db/assistant_modes.get_by_id``.

    The ``mode_key is None`` branch is **preserved behaviour** — 011's turns
    compose with no mode layer and keep doing so (DoD-13).
    """
    if mode_key is None:
        return None
    mode = await assistant_modes.get_by_id(mode_key)
    if mode is None:
        return None
    prompt = mode.system_prompt
    if prompt is None or not prompt.strip():
        # A stored prompt that is null, empty or whitespace-only contributes no
        # section at all (US-110.AC-4) — reported as "no layer", never as a
        # blank one.
        return None
    return prompt


async def allowed_tool_names(mode_key: str | None) -> tuple[str, ...]:
    """Return the tool names allowed for ``mode_key``.

    - **With** a mode: exactly that mode's ``mode_tool`` rows' ``tool_name``
      values, read through ``db/mode_tools.list_by_mode`` — **including the empty
      case**: zero rows is zero tools, not the whole registry
      (``012.assistant-config-editor``'s settled rule). A name with no
      ``TOOL_REGISTRY`` entry is not filtered here; ``services/tools.py:
      resolve_tools`` already skips-and-logs it, which is what
      ``assistant-config.md`` prescribes.
    - **With no** mode: :data:`BASE_TOOL_NAMES` (decision 6).

    The result feeds ``resolve_tools(allowed_names)`` directly — a ``tuple`` is a
    ``Collection[str]``, and it is never ``None``, so the turn no longer takes
    that function's whole-registry branch.

    The ``mode_key is None`` branch is **preserved behaviour** — it is 011's
    shipped tool set (:data:`BASE_TOOL_NAMES` equals the whole registry today)
    and DoD-13 requires it to stay that way.
    """
    if mode_key is None:
        return BASE_TOOL_NAMES
    rows = await mode_tools.list_by_mode(mode_key)
    # Zero rows is an EMPTY allowlist, not the whole registry — 012's settled
    # rule. Nothing is filtered against ``TOOL_REGISTRY`` here: an unknown name
    # is ``resolve_tools``' skip-and-log, which is what ``assistant-config.md``
    # prescribes.
    return tuple(row.tool_name for row in rows)


async def resolve_turn_tools(
    mode_key: str | None, parent: subagent_delegation.ParentTurn
) -> list[ToolDef]:
    """Return **every** tool this turn may call — real and synthetic.

    Tool resolution's two halves in one place (013 step 008):

    - the **real** ``TOOL_REGISTRY`` entries :func:`allowed_tool_names` selects
      (a mode's ``mode_tool`` rows, or :data:`BASE_TOOL_NAMES` with no mode),
      resolved through ``services/tools.py:resolve_tools`` — which is still the
      single place an allowed name with no registry entry is skipped and logged;
    - the mode's **synthetic** sub-agent delegation tools from
      :func:`app.services.subagent_delegation.build_delegation_tools`, with
      ``parent`` carrying what a nested call inherits when a sub-agent has no
      model assignment of its own. With **no** mode there are none at all.

    Returning one list is the point: ``chat_turn`` hands it to
    ``build_tool_bindings`` in a single call, so ``tools_definitions`` and
    ``tools`` are built **together** and always carry identical key sets — the
    ``llm`` client raises ``ValueError`` at pre-flight for any definition name
    with no callable, and a synthetic tool must never be able to cause that.

    Real tools come first and synthetic ones after; a synthetic name that would
    collide with a real one is already dropped by the builder (the registry is
    the source of truth), so the combined list carries no duplicate names.
    """
    real = tools_service.resolve_tools(await allowed_tool_names(mode_key))
    synthetic = await subagent_delegation.build_delegation_tools(mode_key, parent)
    return [*real, *synthetic]
