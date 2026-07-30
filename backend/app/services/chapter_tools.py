"""The chapter assistant tools — the read path and the three shared-canvas
writes (feature 015, step 010).

The **sibling** of ``services/codex_tools.py``, mirrored file for file: the four
callables behind ``services/tools.py:TOOL_REGISTRY``'s chapter entries, their
argument schemas, their binders and the private refusal mirror they share.

**It deliberately imports nothing from ``codex_tools.py`` and that module is not
edited by this feature.** Two files with parallel structure is the intended
shape: the two subjects refuse for overlapping but not identical reasons (a codex
entry refuses when the *entry* is archived and when a fact is given a name; a
chapter refuses on three chapter states and on a *book-level* archive), and a
shared abstraction over two members would be premature.

Business-logic layer: **no** ``session`` / ``AsyncSession`` / ``select()`` /
``session.exec()`` / ``session.add()`` here (``docs/architecture/backend.md`` —
layer separation). In fact this module reads **no ``app.db`` module at all** —
see constraint 5 below.

Six constraints shape every signature in this module. The first four are
``codex_tools.py``'s, unchanged:

1. **No per-request context argument.** The ``llm`` client decodes a tool call's
   JSON arguments and applies them as ``func(**kwargs)``, validated against
   ``inspect.signature(func).parameters``. A tool callable therefore accepts
   **exactly** the ``args_schema`` field names as keyword parameters and nothing
   else — so the turn's :class:`~app.services.tools.ToolContext` is bound at
   *binding* time. All four callables take that context **positionally first**,
   precisely so ``functools.partial(fn, context)`` leaves the schema's fields as
   the only free parameters, and the four ``bind_*`` functions are the
   ``ToolDef.binder`` callables that perform exactly that application. Every one
   of these tools is therefore **context-bearing**: it needs the book, the
   resolved chapter subject, the caller's access and the frame emitter, none of
   which a plain module function can know.
2. **The chapter is never a model-supplied argument.** There is no chapter id,
   no book id and no subject argument anywhere in this module's schemas: the
   chapter is the one ``services/assistant_runtime.py:resolve_subject`` settled
   before the stream opened (``ToolContext.subject.chapter``). A subject argument
   would let the model aim a draft at something the author is not looking at, and
   would be a second source of truth beside the resolved turn subject.
3. **No tool here ever raises.** Every refusal and every failure returns an
   informative *string* the model reads (``services/web_search.py:web_search``'s
   contract, copied exactly): a raising tool is wrapped as ``RuntimeError`` by
   the ``llm`` client and **aborts the whole turn**, with the error never
   reaching the model.
4. **Nothing is persisted by any of them.** A write reaches the author's
   *editor*, not the server; the author keeps, edits or discards it and saves
   through the ordinary ``PUT …/chapters/{id}/text`` endpoint (015 D1 / D4).

and two are this module's own:

5. **None of them touches the database.** No read of ``chapters``, no write, no
   ``ChapterChange``, no ``ChapterTextRevision``. **There is no code path from a
   chat turn to any of those three tables**, and that absence — not a check — is
   the guarantee (``assistant-runtime.md``'s structural-property argument for the
   codex tools, which holds here unchanged). Even the read tool touches nothing:
   it returns the body off the row the turn already resolved.
6. **The author's four refusal rules are mirrored server-side.**
   ``frontend-workspace.md`` requires a read-only subject to refuse writes "from
   a member and from the assistant alike", with the author refused in HTTP
   statuses and the assistant in tool strings ("Two implementations, two
   vocabularies, on purpose"). :func:`_refuse_write` is that mirror: the same
   four rules ``services/chapters.py:save_chapter_text`` enforces for the
   author's save, spoken in the other vocabulary.

**Import direction.** ``services/tools.py`` imports this module (the catalogue →
tool-module direction ``web_search`` and ``codex_tools`` already established), so
the :class:`~app.services.tools.ToolContext` annotation is a
``TYPE_CHECKING``-only import and a quoted annotation.

The module's **declarative** half — the four argument schemas, every
model-facing description and every refusal / confirmation / error string — is
the contract the model reads, so the wording of a constant is as much a part of
this module as its control flow.

The never-raise guard of constraint 3 is an outer ``except Exception`` around
each of the four callables (``codex_tools.py:write_codex_draft``'s shape), and
it is the **last** line of defence, not the mechanism: every enumerated refusal
and every enumerated failure — no chapter subject, a chapter that is not
``open``, an archived book, a co-author in proposal mode, a context with no
emitter, a broken queue — is a returned string on its own named branch, so the
guard only ever catches something nobody enumerated. ``asyncio.CancelledError``
is a ``BaseException`` and still propagates, so a cancelled turn is not
swallowed.
"""

import functools
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from app.models.book import BookState, CollaborationMode
from app.models.chapter import Chapter, ChapterState
from app.models.schemas.chats import CanvasFrame
from app.services import authz

if TYPE_CHECKING:  # pragma: no cover - import cycle guard, see module docstring
    from app.services.tools import ToolContext

logger = logging.getLogger(__name__)


# The event name every canvas write in this module puts on the stream — the same
# one ``codex_tools.py:write_codex_draft`` uses, because it is the *frame's*
# name, not the tool's: ``routes/chats.py``'s serializer is generic over
# ``frame.event`` and the client dispatches by ``(subject_kind, subject_id)``.
_CANVAS_EVENT = "canvas"

# The subject kind and the field every chapter frame carries. The field is
# ``"body"`` and **``CanvasField`` was not widened** (``015/context.md`` → D17):
# a chapter's body IS the same principal text field a codex entry's is, and
# inventing a ``"text"`` member would give one concept two names across two
# subjects.
_CANVAS_SUBJECT_KIND = "chapter"
_CANVAS_FIELD = "body"


# Every string these tools return when they refuse or fail. They are module-level
# constants for the reason ``codex_tools.py`` gives: the never-raise contract
# makes them the *only* signal the model gets, so the wording must not drift
# between call sites. The same two-vocabulary split applies — a **refusal**
# ("Chapter draft refused: …") is a verdict about what the author has open and
# what the caller may do to it and will read the same on every retry; an
# **error** ("Chapter draft error: …" / "Chapter error: …") is a failure the model
# may reasonably try again.
_NOT_A_CHAPTER_MESSAGE = (
    "Chapter draft refused: the author does not have a chapter open, so there is "
    "nothing to write into. Only a chapter can be written this way — write your "
    "answer in the chat instead, or ask the author to open the chapter."
)
_CHAPTER_NOT_OPEN_MESSAGE = (
    "Chapter draft refused: this chapter is {state}, and only an open chapter can "
    "be written into. Ask the author to open it first."
)
_BOOK_ARCHIVED_MESSAGE = (
    "Chapter draft refused: this book is archived and read-only. It has to be "
    "restored before anything can be written into it."
)
_PROPOSAL_MODE_MESSAGE = (
    "Chapter draft refused: this book is in proposal mode, so a co-author's "
    "chapter change must be held for the owner's review. That review surface is "
    "FEAT-010, which is not built yet, so the draft cannot be offered. Ask the "
    "owner to switch the book to free mode."
)
_NO_STREAM_MESSAGE = (
    "Chapter draft error: this turn has no open editor to write into, so the "
    "draft could not be delivered."
)
_DELIVERY_FAILED_MESSAGE = (
    "Chapter draft error: the draft could not be delivered to the author's editor."
)
_WRITE_FAILED_MESSAGE = "Chapter draft error: the draft could not be written."

# The read path's strings. It is refused by **subject resolution only** — a
# ``closed`` chapter can be read, and so can a ``planned`` or ``closing`` one —
# so it has exactly one refusal and one error.
_NO_CHAPTER_TO_READ_MESSAGE = (
    "Chapter error: the author does not have a chapter of this book open, so "
    "there is no chapter body to read."
)
_READ_FAILED_MESSAGE = "Chapter error: the chapter body could not be read."

# The three confirmations. Short on purpose: a tool result is what tells
# ``chat_with_tools`` the round is not the end of the turn.
_WHOLE_BODY_WRITTEN_MESSAGE = (
    "The chapter body was replaced in the author's editor. Nothing is saved: the "
    "author reads it, edits it and decides whether to keep it."
)
_SELECTION_WRITTEN_MESSAGE = (
    "The author's selected text was replaced in their editor. Nothing is saved: "
    "the author reads it, edits it and decides whether to keep it."
)
_APPENDED_MESSAGE = (
    "The text was added to the end of the chapter body in the author's editor. "
    "Nothing is saved: the author reads it, edits it and decides whether to keep "
    "it."
)


# Arguments for ``read_chapter_text``. The class docstring below is
# **model-facing** — ``llm.pydantic_to_openai_tool`` renders the schema through
# ``model_json_schema()``, which carries it as the parameter object's
# ``description`` — so the engineering notes live here instead:
#
# - it has **no fields**, and that is the point. The chapter is the one the
#   author has open (constraint 2), so there is nothing for the model to supply;
#   a chapter-id or book-id field would be the second source of truth constraint
#   2 exists to prevent. ``ToolDef.args_schema`` is required, so the schema is
#   declared rather than omitted, and the bound callable correspondingly has
#   **zero** free parameters — which is exactly what the ``llm`` client's
#   ``inspect.signature`` validation compares it against;
# - the schema lives here rather than in ``models/schemas/tools.py`` for the
#   reason ``codex_tools.py`` gives (that module is outside this step's Source
#   files); it is a declarative Pydantic schema either way.
class ReadChapterTextArgs(BaseModel):
    """Arguments for reading the open chapter's saved body.

    There are none: the chapter is the one the author currently has open.
    """


# Arguments for ``set_chapter_text``. The field name is the JSON-schema property
# name AND the bound callable's only free parameter (constraint 1). No subject
# field, no id field — see constraint 2.
class SetChapterTextArgs(BaseModel):
    """Arguments for replacing the whole body of the chapter the author has open.

    Send the complete new body in one call; it replaces everything that is there.
    """

    text: str = Field(
        description=(
            "The complete new body of the chapter. It replaces the whole body, "
            "so send all of it, not just the part you changed."
        )
    )


# Arguments for ``update_selection``. One text field, same two rules as above.
# **The selection itself is NOT an argument**: it is the author's own, it rides
# on the turn (``ToolContext.selection_text``), and the model is told in the
# tool's description not to try to describe, anchor or address it
# (``015/context.md`` → D5 — no offsets, no line numbers, ever).
class UpdateSelectionArgs(BaseModel):
    """Arguments for replacing the author's current selection.

    Send only the replacement text. Where it goes is decided by what the author
    has selected, not by anything you send.
    """

    text: str = Field(
        description=(
            "The text to put in place of the author's current selection. Send "
            "only the replacement itself — no surrounding text, no quotes of "
            "what is being replaced and no description of where it goes."
        )
    )


# Arguments for ``add_text``. One text field, same two rules again. There is
# deliberately no position, anchor or "after which paragraph" field: the
# operation is append-only and the protocol supports no other placement.
class AddTextArgs(BaseModel):
    """Arguments for adding text to the end of the open chapter's body."""

    text: str = Field(
        description=(
            "The text to add at the end of the chapter's body. It is appended "
            "as-is; it cannot be placed anywhere else."
        )
    )


def _resolved_chapter(context: "ToolContext") -> Chapter | None:
    """The chapter the turn's subject resolved to, or ``None``.

    ``None`` when the turn carried no subject, when the subject is not a chapter
    (a codex entry, a list view, the chats view, book state) **and when the
    subject named a chapter that did not resolve inside this book** — the
    cross-book case is answered by ``resolve_subject`` returning ``NO_SUBJECT``
    before this module ever sees it, which is why there is no book comparison
    here and must not be one (DoD-9: refused by subject resolution, not by a
    check inside the tool).

    Reads nothing but :attr:`~app.services.tools.ToolContext.subject`: **no
    database access**.
    """
    subject = context.subject
    if subject is None:
        # No subject at all — the author is looking at nothing the tools can
        # write into (the chats view with no content pane, a turn taken without
        # one).
        return None
    # ``ResolvedSubject.chapter`` is populated **only** by ``resolve_subject``'s
    # chapter branch, and only for a chapter that resolved inside this book: a
    # codex entry, any list kind, book state and a chapter subject carrying no
    # id all leave it ``None``, and another book's chapter never reaches here at
    # all (``resolve_subject`` answered ``NO_SUBJECT``). So there is no book
    # comparison here — DoD-9 is subject resolution's, not this module's.
    return subject.chapter


def _refuse_write(context: "ToolContext") -> str | None:
    """The server-side write verdict: a refusal string, or ``None`` to allow.

    The chapter counterpart of ``services/codex_tools.py:_refuse_write``, and the
    assistant-side mirror of the four rules ``services/chapters.py`` enforces for
    the author's own save. **It returns a string the model reads and it NEVER
    raises** — a raising tool aborts the turn.

    The four rules, in order, and where each comes from:

    1. **the subject is not a chapter** (:func:`_resolved_chapter` is ``None``) —
       subject resolution plus ``determine_mode``'s chapter branch (015 step
       009). Refused with :data:`_NOT_A_CHAPTER_MESSAGE`;
    2. **the chapter is not** ``open`` — ``domain-chapter.md``: "``closing`` and
       ``closed`` both refuse all writes to ``text`` — from a member and from the
       assistant alike (US-097.AC-2, US-059.AC-3)", and ``planned`` has no body
       yet. Refused with :data:`_CHAPTER_NOT_OPEN_MESSAGE`, which **names the
       state**;
    3. **the book is** ``archived`` — 015 D10, read straight off
       ``context.access.book_state``. Refused with
       :data:`_BOOK_ARCHIVED_MESSAGE`;
    4. **the caller is a co-author in a** ``proposal``-**mode book** — 015 D11,
       read off ``context.access.role`` + ``context.access.collaboration_mode``,
       the same ``role == co_author`` branch (never "not owner") that
       ``services/chapters.py:_require_writable_mode`` applies to the author's
       save. The **owner is never refused for mode**. Refused with
       :data:`_PROPOSAL_MODE_MESSAGE`, which **names FEAT-010** as the unbuilt
       mechanism, so the gap stays visible instead of silently violated.

    Rules 3 and 4 are **field reads off** :attr:`~app.services.tools.ToolContext.access`,
    which already carries ``role``, ``book_state`` and ``collaboration_mode``:
    no new plumbing, no second ``BookAccess`` resolved, and no role / mode /
    book-state field added to the context. A context carrying **no** access is
    not refused by 3 or 4 — it can name neither an archived book nor a
    co-author — which is ``codex_tools.py:_refuse_write``'s reading of the same
    situation, for the same reason: a real turn always carries one.

    **It reads nothing but the tool context**, so no code path from here reaches
    the ``chapters`` table.

    There is deliberately **no fifth rule**. In particular an absent
    ``context.selection_text`` is *not* a refusal: the selection frame is applied
    to the author's live selection by the client, which knows it better than the
    turn does, and no criterion of this step gates on it.
    """
    chapter = _resolved_chapter(context)
    if chapter is None:
        # Rule 1: no chapter subject. A codex entry, a list view, the chats
        # view, book state, or no subject at all — none of them is a chapter,
        # and there is no id to aim a frame at either.
        return _NOT_A_CHAPTER_MESSAGE

    state = chapter.state
    if state != ChapterState.open:
        # Rule 2: ``planned`` has no body yet; ``closing`` and ``closed`` both
        # refuse all writes to ``text``, from a member and from the assistant
        # alike. The refusal **names the state**, so the model can tell the
        # author what to do about it. ``ChapterState`` is a ``str`` enum, so a
        # raw string compares equal above; ``.value`` keeps the message reading
        # "planned" rather than "ChapterState.planned".
        return _CHAPTER_NOT_OPEN_MESSAGE.format(
            state=state.value if isinstance(state, ChapterState) else str(state)
        )

    access = context.access
    if access is not None and access.book_state == BookState.archived:
        # Rule 3 (D10): one field read off the access the turn already carries.
        return _BOOK_ARCHIVED_MESSAGE

    if (
        access is not None
        and access.role == authz.AccessRole.co_author
        and access.collaboration_mode == CollaborationMode.proposal
    ):
        # Rule 4 (D11): the same ``role == co_author`` branch — never "not
        # owner" — that ``services/chapters.py:_require_writable_mode`` applies
        # to the author's own save, so the **owner** is never refused for mode.
        return _PROPOSAL_MODE_MESSAGE
    # A context carrying **no** access can name neither an archived book nor a
    # co-author, so rules 3 and 4 do not fire for it — ``codex_tools.py``'s
    # reading of the same situation. A real turn always carries one.

    return None


async def read_chapter_text(context: "ToolContext") -> str:
    """Return the **saved** body of the chapter the author has open.

    ``context`` is bound at build time by :func:`bind_read_chapter_text`, leaving
    **no** free parameters — :class:`ReadChapterTextArgs` has no fields, so the
    model supplies nothing.

    Subject to the same subject-resolution rule as the writes
    (:func:`_resolved_chapter`) but **not** to :func:`_refuse_write`: a
    ``planned``, ``closing`` or ``closed`` chapter can be read, an archived
    book's chapter can be read, and a co-author in a proposal-mode book can read.
    Reading is not writing.

    A chapter of **another book** is refused by subject resolution rather than by
    a check here (DoD-9), and comes back as :data:`_NO_CHAPTER_TO_READ_MESSAGE` —
    the same string as "no chapter open at all", so the model learns nothing
    about what does or does not exist elsewhere.

    **It touches no database**: the body comes off the row the turn already
    resolved, which is exactly why the description tells the model this is the
    **saved** text and may lag the author's unsaved draft (015 D4's accepted
    limitation).

    **It never raises** — every refusal and every failure is a string.
    """
    # The outer never-raise guard (constraint 3): a failure mode nobody
    # enumerated must still come back as a string. ``Exception`` is deliberately
    # broad; ``asyncio.CancelledError`` is a ``BaseException`` and still
    # propagates, so a cancelled turn is not swallowed.
    try:
        chapter = _resolved_chapter(context)
        if chapter is None:
            # No chapter open, and another book's chapter — indistinguishable
            # from out here on purpose, so the model learns nothing about what
            # does or does not exist elsewhere.
            return _NO_CHAPTER_TO_READ_MESSAGE

        # The SAVED body, straight off the row the turn already resolved: no
        # database read, and no knowledge of the author's unsaved draft, which
        # is exactly what the tool's description tells the model.
        return chapter.text
    except Exception:
        logger.warning(
            "read_chapter_text: the chapter body could not be read for book %s",
            getattr(context, "book_id", None),
            exc_info=True,
        )
        return _READ_FAILED_MESSAGE


async def set_chapter_text(context: "ToolContext", text: str) -> str:
    """Replace the whole body of the open chapter in the author's editor.

    ``context`` is bound at build time by :func:`bind_set_chapter_text`, leaving
    ``text`` — exactly :class:`SetChapterTextArgs`' single field — as the only
    model-supplied argument.

    In order: :func:`_refuse_write` (a refusal returns its string and emits
    **nothing**), then **exactly one** frame through ``context.emit_frame`` —
    event ``"canvas"``, payload a
    :class:`~app.models.schemas.chats.CanvasFrame` carrying
    ``subject_kind="chapter"``, the resolved chapter's id **as a string**,
    ``field="body"``, the given ``text`` and ``op="replace"`` — then a short
    confirmation (:data:`_WHOLE_BODY_WRITTEN_MESSAGE`) so ``chat_with_tools``
    keeps looping.

    That emitter is a closure over the very ``asyncio.Queue`` ``run_turn``
    already pumps ``thinking`` / ``delta`` through, so the draft is ordered
    naturally among the surrounding content frames and **no second transport
    exists** — which is why the shared-canvas write does not force the
    ``chat_with_tools`` seam open here any more than it did for the codex.

    **It touches no database** and **never raises**: a missing emitter and a
    failure inside the emitter each return their own string.
    """
    try:
        refusal = _refuse_write(context)
        if refusal is not None:
            # A refusal emits NOTHING: the author's editor is left exactly as it
            # was, and the model is told why in a string it can act on.
            return refusal

        emit_frame = context.emit_frame
        if emit_frame is None:
            # A context built without a stream (a bound tool outside a real
            # turn): there is nowhere to put the frame, so this is a returned
            # string, not a raise.
            return _NO_STREAM_MESSAGE

        chapter = _resolved_chapter(context)
        if chapter is None:  # unreachable: ``_refuse_write`` already refused it
            return _NOT_A_CHAPTER_MESSAGE
        frame = CanvasFrame(
            subject_kind=_CANVAS_SUBJECT_KIND,
            # The id crosses as a **string** (the house rule — snowflakes exceed
            # the JS safe-integer range).
            subject_id=str(chapter.id),
            field=_CANVAS_FIELD,
            text=text,
            op="replace",
        )
        try:
            # EXACTLY ONE frame, through the turn's own emitter — the same
            # put-onto-the-queue path ``thinking`` / ``delta`` travel, so the
            # draft interleaves naturally with the surrounding content frames
            # and no second transport exists.
            await emit_frame(_CANVAS_EVENT, frame)
        except Exception:
            # A closed or broken queue: still a string, never a raise.
            logger.warning(
                "set_chapter_text: the canvas frame could not be delivered for "
                "book %s",
                context.book_id,
                exc_info=True,
            )
            return _DELIVERY_FAILED_MESSAGE

        return _WHOLE_BODY_WRITTEN_MESSAGE
    except Exception:
        logger.warning(
            "set_chapter_text: the draft could not be written for book %s",
            getattr(context, "book_id", None),
            exc_info=True,
        )
        return _WRITE_FAILED_MESSAGE


async def update_selection(context: "ToolContext", text: str) -> str:
    """Replace the author's current selection in the open chapter's editor.

    ``context`` is bound at build time by :func:`bind_update_selection`, leaving
    ``text`` — exactly :class:`UpdateSelectionArgs`' single field — as the only
    model-supplied argument. **The selection is never an argument**: it is the
    author's own, it was supplied with the turn
    (``ToolContext.selection_text``), and the client applies the frame to it.

    Identical in shape to :func:`set_chapter_text` — the same refusal mirror, the
    same one frame carrying the resolved chapter's id and ``field="body"``, the
    same never-raise contract — differing only in ``op="replace_selection"`` and
    in its confirmation (:data:`_SELECTION_WRITTEN_MESSAGE`).
    """
    try:
        refusal = _refuse_write(context)
        if refusal is not None:
            # The same four rules and nothing more: an absent
            # ``context.selection_text`` is deliberately **not** a fifth one —
            # the client applies this frame to the author's live selection,
            # which it knows better than the turn does.
            return refusal

        emit_frame = context.emit_frame
        if emit_frame is None:
            return _NO_STREAM_MESSAGE

        chapter = _resolved_chapter(context)
        if chapter is None:  # unreachable: ``_refuse_write`` already refused it
            return _NOT_A_CHAPTER_MESSAGE
        frame = CanvasFrame(
            subject_kind=_CANVAS_SUBJECT_KIND,
            subject_id=str(chapter.id),
            field=_CANVAS_FIELD,
            text=text,
            # The placement is the author's own selection, resolved entirely on
            # the client: the wire carries no offsets and no anchor (D5).
            op="replace_selection",
        )
        try:
            await emit_frame(_CANVAS_EVENT, frame)
        except Exception:
            logger.warning(
                "update_selection: the canvas frame could not be delivered for "
                "book %s",
                context.book_id,
                exc_info=True,
            )
            return _DELIVERY_FAILED_MESSAGE

        return _SELECTION_WRITTEN_MESSAGE
    except Exception:
        logger.warning(
            "update_selection: the draft could not be written for book %s",
            getattr(context, "book_id", None),
            exc_info=True,
        )
        return _WRITE_FAILED_MESSAGE


async def add_text(context: "ToolContext", text: str) -> str:
    """Add text to the **end** of the open chapter's body in the author's editor.

    ``context`` is bound at build time by :func:`bind_add_text`, leaving ``text``
    — exactly :class:`AddTextArgs`' single field — as the only model-supplied
    argument.

    Identical in shape to :func:`set_chapter_text` — the same refusal mirror, the
    same one frame carrying the resolved chapter's id and ``field="body"``, the
    same never-raise contract — differing only in ``op="append"`` and in its
    confirmation (:data:`_APPENDED_MESSAGE`).

    Append is the **only** placement it can express, and the description says so:
    the protocol supports no addressed placement at all, and a model that tries
    to negotiate one gets nowhere.
    """
    try:
        refusal = _refuse_write(context)
        if refusal is not None:
            return refusal

        emit_frame = context.emit_frame
        if emit_frame is None:
            return _NO_STREAM_MESSAGE

        chapter = _resolved_chapter(context)
        if chapter is None:  # unreachable: ``_refuse_write`` already refused it
            return _NOT_A_CHAPTER_MESSAGE
        frame = CanvasFrame(
            subject_kind=_CANVAS_SUBJECT_KIND,
            subject_id=str(chapter.id),
            field=_CANVAS_FIELD,
            text=text,
            # The end of the draft, and the only placement this protocol can
            # express at all.
            op="append",
        )
        try:
            await emit_frame(_CANVAS_EVENT, frame)
        except Exception:
            logger.warning(
                "add_text: the canvas frame could not be delivered for book %s",
                context.book_id,
                exc_info=True,
            )
            return _DELIVERY_FAILED_MESSAGE

        return _APPENDED_MESSAGE
    except Exception:
        logger.warning(
            "add_text: the draft could not be written for book %s",
            getattr(context, "book_id", None),
            exc_info=True,
        )
        return _WRITE_FAILED_MESSAGE


def bind_read_chapter_text(context: "ToolContext") -> Callable[..., object]:
    """Bind ``context`` into :func:`read_chapter_text` — the ``ToolDef.binder``.

    Returns a callable with **no** free parameters, matching
    :class:`ReadChapterTextArgs`' empty field set, which is what the ``llm``
    client's ``inspect.signature(func).parameters`` validation and its
    ``func(**kwargs)`` dispatch require, there being no per-request context
    argument.
    """
    return functools.partial(read_chapter_text, context)


def bind_set_chapter_text(context: "ToolContext") -> Callable[..., object]:
    """Bind ``context`` into :func:`set_chapter_text` — the ``ToolDef.binder``.

    Returns a callable whose only free parameter is :class:`SetChapterTextArgs`'
    single field (``text``). Binding is also what carries the turn's resolved
    chapter, the caller's access and the frame emitter into the tool: the model
    supplies none of them, and cannot.
    """
    return functools.partial(set_chapter_text, context)


def bind_update_selection(context: "ToolContext") -> Callable[..., object]:
    """Bind ``context`` into :func:`update_selection` — the ``ToolDef.binder``.

    Returns a callable whose only free parameter is :class:`UpdateSelectionArgs`'
    single field (``text``), for the same reason as :func:`bind_set_chapter_text`.
    """
    return functools.partial(update_selection, context)


def bind_add_text(context: "ToolContext") -> Callable[..., object]:
    """Bind ``context`` into :func:`add_text` — the ``ToolDef.binder``.

    Returns a callable whose only free parameter is :class:`AddTextArgs`' single
    field (``text``), for the same reason as :func:`bind_set_chapter_text`.
    """
    return functools.partial(add_text, context)
