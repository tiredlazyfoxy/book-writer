"""The close-chapter assistant tools — the five callables the ``close-chapter``
mode uses to draft a chapter's continuity and run the consistency check
(feature 016).

The **sibling** of ``services/chapter_tools.py`` and ``services/codex_tools.py``,
mirrored file for file: the callables behind ``services/tools.py:TOOL_REGISTRY``'s
close entries, their argument schemas, their binders and the private refusal
mirror they share. It deliberately imports nothing from either sibling, and
neither sibling is edited by this feature — two files with parallel structure is
the intended shape (``chapter_tools.py``'s module docstring states the rule).

Realizes FEAT-012 UC-047 and FEAT-016 UC-064, UC-065, UC-080; US-072, US-073,
US-091, US-092.

Business-logic layer: **no** ``session`` / ``AsyncSession`` / ``select()`` /
``session.exec()`` / ``session.add()`` here (``docs/architecture/backend.md`` —
layer separation).

The constraints ``chapter_tools.py`` enumerates hold here unchanged:

1. **No per-request context argument.** The ``llm`` client applies a decoded tool
   call as ``func(**kwargs)``, validated against ``inspect.signature``. Every
   callable therefore takes its :class:`~app.services.tools.ToolContext`
   **positionally first**, so ``functools.partial(fn, context)`` leaves exactly
   the ``args_schema`` field names free, and the five ``bind_*`` functions are the
   ``ToolDef.binder`` callables that perform that application.
2. **The chapter is never a model-supplied argument.** No chapter id, no book id
   and no subject field appears in any schema here: the chapter is the one
   ``assistant_runtime.resolve_subject`` settled before the stream opened
   (``ToolContext.subject.chapter``).
3. **No tool here ever raises.** Every refusal and every failure is an
   informative *string* the model reads — a raising tool is wrapped as
   ``RuntimeError`` by the ``llm`` client and **aborts the whole turn**.

and two are this module's own, where it parts company with ``chapter_tools.py``:

4. **These tools DO persist** — unlike every canvas tool shipped so far. A
   summary and a changeset are server-side continuity artifacts, not drafts in
   the author's editor, so :func:`draft_chapter_summary` and
   :func:`draft_chapter_notes` write through ``app.db`` and emit no canvas frame.
   The one exception is :func:`propose_active_notes`, which writes **nothing**:
   its value is held in the turn's context for
   ``services/chapters.py:finalize_close_turn`` to read (decision D7), which is
   what makes a discarded run free.
5. **The refusal chain has FOUR rules, in this order** — the counterpart of
   ``chapter_tools.py:_refuse_write``, whose private-helper shape this module
   copies (the helper itself is the coder's to write; it is not part of the
   frozen public interface):

   1. a **non-chapter subject** — nothing to close;
   2. a chapter **not in** ``closing`` — these tools exist only inside a close
      run, so ``planned`` / ``open`` / ``closed`` all refuse. This is the one
      state test that differs from ``chapter_tools.py``'s (which requires
      ``open``);
   3. an **archived book** (015 D10, read off ``context.access.book_state``);
   4. a caller who **does not hold** ``Capability.set_chapter_state`` — the very
      capability that gated the close request itself. This is the rule beyond
      the sibling's precedent, and it is what closes the co-author risk: mode
      determination is per-subject, not per-role, so a co-author's own chat also
      resolves to ``close-chapter`` while somebody else's chapter is ``closing``
      — and every close tool refuses them, with no run-ownership token and no new
      state. **No collaboration-mode rule** is layered on top: the capability is
      owner-only already, and an owner is never held for review.

   :func:`read_continuity_context` is **read-only** and is subject to rule 1
   alone — reading is not writing, exactly as ``chapter_tools.read_chapter_text``
   is.

**Import direction.** ``services/tools.py`` imports this module (the catalogue →
tool-module direction), so the :class:`~app.services.tools.ToolContext`
annotation is a ``TYPE_CHECKING``-only import and a quoted annotation.

The module's **declarative** half — the five argument schemas, every model-facing
description and every refusal / confirmation / error string — is the contract the
model reads, so the wording of a constant is as much a part of this module as its
control flow.

Skeleton (016): the five schemas, the five callable signatures and the five
binders are frozen. The schemas are declarative and complete; the callable bodies
are UNIMPLEMENTED (raise ``NotImplementedError``) and the coder replaces each
with the never-raise, string-returning implementation the docstrings specify.
"""

import functools
import logging
from collections.abc import Callable
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Annotated

from pydantic import BaseModel, Field, StringConstraints

from app.db import books as books_db
from app.db import chapter_note_changesets
from app.db import chapters as chapters_db
from app.db import flags as flags_db
from app.models.book import BookState
from app.models.chapter import Chapter, ChapterState, SummaryStatus
from app.models.chapter_notes import ChapterNoteChangeset, NoteStatus
from app.models.flag import Flag, FlagOrigin, FlagStatus
from app.services import authz

if TYPE_CHECKING:  # pragma: no cover - import cycle guard, see module docstring
    from app.services.tools import ToolContext

logger = logging.getLogger(__name__)


# Every string these tools return when they refuse or fail. Module-level
# constants for ``chapter_tools.py``'s reason: the never-raise contract makes them
# the ONLY signal the model gets, so the wording must not drift between call
# sites. The same two-vocabulary split applies — a **refusal** ("… refused: …")
# is a verdict that will read the same on every retry; an **error** ("… error:
# …") is a failure the model may reasonably try again.
_NOT_A_CHAPTER_MESSAGE = (
    "Close refused: there is no chapter being closed here, so there is nothing "
    "to write continuity for. These tools only work inside a chapter's close "
    "run — answer in the chat instead."
)
_CHAPTER_NOT_CLOSING_MESSAGE = (
    "Close refused: this chapter is {state}, not closing, so its continuity "
    "cannot be drafted. The author starts a close from the chapter's own page."
)
_BOOK_ARCHIVED_MESSAGE = (
    "Close refused: this book is archived and read-only. It has to be restored "
    "before anything can be written into it."
)
_NOT_THE_CLOSER_MESSAGE = (
    "Close refused: closing a chapter is the book owner's, and this "
    "conversation is not theirs. Nothing was written."
)

# The failure strings — one per write path plus the read path's.
_SUMMARY_FAILED_MESSAGE = (
    "Close error: the chapter summary could not be saved. Try again."
)
_NOTES_FAILED_MESSAGE = (
    "Close error: the chapter's state-note changeset could not be saved. Try "
    "again."
)
_PROPOSAL_FAILED_MESSAGE = (
    "Close error: the proposed state notes could not be recorded. Try again."
)
_FLAG_FAILED_MESSAGE = (
    "Close error: the consistency finding could not be recorded. Try again."
)
_READ_FAILED_MESSAGE = (
    "Close error: the book's continuity so far could not be read."
)

# The four confirmations. Short on purpose: a tool result is what tells
# ``chat_with_tools`` the round is not the end of the turn. Each states the one
# fact the model would otherwise get wrong — that the artifact is SAVED, and that
# the SERVER, not the model, decides whether the chapter closes.
_SUMMARY_WRITTEN_MESSAGE = (
    "The chapter summary was saved as a draft. It is not approved yet: the "
    "server decides whether this chapter closes once this conversation ends."
)
_NOTES_WRITTEN_MESSAGE = (
    "The chapter's state-note changeset was saved as a draft. Propose the "
    "resulting state notes before you finish, or the close cannot complete."
)
_PROPOSAL_RECORDED_MESSAGE = (
    "The proposed state notes were recorded for this close run. Nothing is "
    "written to the book yet — they only take effect if the chapter closes "
    "cleanly."
)
_FLAG_RAISED_MESSAGE = (
    "The finding was recorded on this chapter. While it is open the chapter "
    "will not close: a person has to deal with it first."
)

# The read tool's digest layout. Declarative, like every string above: the model
# reads it, so its shape is part of this module's contract.
_DIGEST_NOTES_HEADING = "The book's current state notes:"
_DIGEST_NO_NOTES = "(none recorded yet)"
_DIGEST_SUMMARIES_HEADING = "Summaries of the chapters already closed:"
_DIGEST_NO_SUMMARIES = "(no chapter of this book has been closed yet)"


# Arguments for ``draft_chapter_summary``. The class docstring is **model-facing**
# (``llm.pydantic_to_openai_tool`` renders it through ``model_json_schema()``), so
# the engineering notes live out here: one field, whose name is both the JSON
# property and the bound callable's only free parameter (constraint 1). No chapter
# field and no book field — constraint 2.
class DraftChapterSummaryArgs(BaseModel):
    """Arguments for writing the closing chapter's summary.

    Send the whole summary in one call; it replaces any summary already drafted
    for this chapter.
    """

    summary: str = Field(
        description=(
            "The chapter's backward-looking summary: what happened in it, as a "
            "later chapter would need to know. Send the complete text — it "
            "replaces the whole summary, not part of it."
        )
    )


# Arguments for ``draft_chapter_notes``. THREE fields, one per operation, and
# deliberately no merged field: there is no correct mechanical merge of three
# free-text deltas (decision D7), so the model states each separately.
class DraftChapterNotesArgs(BaseModel):
    """Arguments for the chapter's changeset against the book's state notes.

    Three separate lists — what this chapter added, what it changed, and what it
    made no longer true. Send all three every time; each replaces its own list.
    """

    added: str = Field(
        description=(
            "What this chapter ADDED to the book's state: facts, situations and "
            "standing conditions that are now true and were not before. Empty "
            "string if there is nothing."
        )
    )
    modified: str = Field(
        description=(
            "What this chapter CHANGED about the book's state: things that were "
            "already true and are now true differently. Empty string if there is "
            "nothing."
        )
    )
    deleted: str = Field(
        description=(
            "What this chapter made NO LONGER TRUE: state that has ended, been "
            "undone or been superseded. Empty string if there is nothing."
        )
    )


# Arguments for ``propose_active_notes``. ONE field carrying the WHOLE proposed
# live set — not a delta — because the tool's result is what replaces
# ``Book.active_notes`` wholesale if the run closes cleanly.
class ProposeActiveNotesArgs(BaseModel):
    """Arguments for proposing the book's resulting live state notes.

    Send the WHOLE note set as it should stand after this chapter: the previous
    set with this chapter's changeset applied. It replaces the book's notes
    entirely if the chapter closes.
    """

    active_notes: str = Field(
        description=(
            "The complete state notes for the book as they should read after "
            "this chapter closes — the previous notes with this chapter's "
            "additions, changes and deletions worked in. Send all of them, not "
            "just what moved: this text replaces the whole set."
        )
    )


# Arguments for ``raise_check_flag``. The comment is constrained non-blank at the
# SCHEMA level: a finding with no text says nothing, and the ``llm`` client
# validates the decoded arguments against this model before dispatch.
class RaiseCheckFlagArgs(BaseModel):
    """Arguments for recording one consistency-check finding on this chapter.

    One call per finding. A finding recorded here blocks the chapter from
    closing until a person deals with it.
    """

    comment: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)] = Field(
        description=(
            "What is inconsistent, stated so an author can act on it: what this "
            "chapter says, what it contradicts, and where. One finding per call."
        )
    )


# Arguments for ``read_continuity_context``. It has **no fields**, and that is the
# point: the book and the chapter are the ones the turn already resolved
# (constraint 2), so there is nothing for the model to supply. ``ToolDef.args_schema``
# is required, so the schema is declared rather than omitted, and the bound
# callable correspondingly has ZERO free parameters — which is exactly what the
# ``llm`` client's ``inspect.signature`` validation compares it against.
class ReadContinuityContextArgs(BaseModel):
    """Arguments for reading the book's continuity so far.

    There are none: it always reads the book this chapter belongs to.
    """


def _resolved_chapter(context: "ToolContext") -> Chapter | None:
    """The chapter the turn's subject resolved to, or ``None``.

    ``chapter_tools.py:_resolved_chapter`` verbatim in shape, and for the same
    reason: ``None`` when the turn carried no subject, when the subject is not a
    chapter, **and** when the subject named a chapter that did not resolve inside
    this book — the cross-book case is answered by
    ``assistant_runtime.resolve_subject`` returning ``NO_SUBJECT`` before this
    module ever sees it, which is why there is no book comparison here.

    Reads nothing but ``context.subject``: **no database access**.
    """
    subject = context.subject
    if subject is None:
        return None
    return subject.chapter


def _refuse_write(context: "ToolContext") -> str | None:
    """The close-run write verdict: a refusal string, or ``None`` to allow.

    The counterpart of ``services/chapter_tools.py:_refuse_write``, whose shape
    this copies. **It returns a string the model reads and it NEVER raises** — a
    raising tool is wrapped as ``RuntimeError`` by the ``llm`` client and aborts
    the whole turn.

    The four rules, in order:

    1. **the subject is not a chapter** — nothing is being closed. Refused with
       :data:`_NOT_A_CHAPTER_MESSAGE`;
    2. **the chapter is not** ``closing`` — these tools exist only inside a close
       run, so ``planned`` / ``open`` / ``closed`` all refuse. This is the one
       state test that differs from the sibling's (which requires ``open``).
       Refused with :data:`_CHAPTER_NOT_CLOSING_MESSAGE`, which **names the
       state**;
    3. **the book is** ``archived`` (015 D10), read straight off
       ``context.access.book_state``;
    4. **the caller does not hold** ``Capability.set_chapter_state`` — the very
       capability that gated the close request itself. This is the rule beyond
       the sibling's precedent and it is what closes the co-author risk: mode
       determination is per-subject, not per-role, so a co-author's own chat also
       resolves to ``close-chapter`` while somebody else's chapter is ``closing``
       — and every close tool refuses them, with no run-ownership token and no new
       state. **No collaboration-mode rule** is layered on top: the capability is
       owner-only already, and an owner is never held for review.

    Rules 3 and 4 are read off ``context.access``, which already carries the role
    and the book state: no new plumbing and no second ``BookAccess`` resolved. A
    context carrying **no** access is not refused by 3 or 4 — it can name neither
    an archived book nor a caller — which is ``chapter_tools.py``'s reading of the
    same situation, for the same reason: a real turn always carries one.
    """
    chapter = _resolved_chapter(context)
    if chapter is None:
        # Rule 1: no chapter subject at all.
        return _NOT_A_CHAPTER_MESSAGE

    state = chapter.state
    if state != ChapterState.closing:
        # Rule 2: the one state test that differs from the sibling's. The refusal
        # NAMES the state, so the model can tell the author what to do about it.
        # ``ChapterState`` is a ``str`` enum, so ``.value`` keeps the message
        # reading "open" rather than "ChapterState.open".
        return _CHAPTER_NOT_CLOSING_MESSAGE.format(
            state=state.value if isinstance(state, ChapterState) else str(state)
        )

    access = context.access
    if access is not None and access.book_state == BookState.archived:
        # Rule 3 (015 D10): one field read off the access the turn already carries.
        return _BOOK_ARCHIVED_MESSAGE

    if access is not None:
        try:
            # Rule 4: the SAME capability ``POST …/close`` requires, asked through
            # the same decision function — no role literal is re-spelled here, so
            # the tool cannot drift from the endpoint.
            authz.require(access, authz.Capability.set_chapter_state)
        except authz.BookAuthorizationError:
            return _NOT_THE_CLOSER_MESSAGE

    return None


async def draft_chapter_summary(context: "ToolContext", summary: str) -> str:
    """Write the closing chapter's summary (UC-047 / US-072).

    ``context`` is bound at build time by :func:`bind_draft_chapter_summary`,
    leaving ``summary`` — exactly :class:`DraftChapterSummaryArgs`' single field —
    as the only model-supplied argument.

    Runs the four-rule refusal chain first (a refusal returns its string and
    writes **nothing**), then persists on the resolved chapter:
    ``Chapter.summary = summary`` and ``Chapter.summary_status =
    SummaryStatus.draft``, and returns a short confirmation so
    ``chat_with_tools`` keeps looping.

    It is **repeatable within a run**: a second call replaces the first's text
    and leaves the status ``draft``. Nothing here closes the chapter —
    ``chapters.finalize_close_turn`` reads the ``draft`` status as one of its
    four facts and is the only thing that ever writes ``approved``.

    **It never raises**: every refusal and every failure is a returned string.
    """
    # The outer never-raise guard (constraint 3): a failure mode nobody enumerated
    # must still come back as a string. ``asyncio.CancelledError`` is a
    # ``BaseException`` and still propagates, so a cancelled turn is not swallowed.
    try:
        refusal = _refuse_write(context)
        if refusal is not None:
            # A refusal writes NOTHING.
            return refusal

        chapter = _resolved_chapter(context)
        if chapter is None:  # unreachable: ``_refuse_write`` already refused it
            return _NOT_A_CHAPTER_MESSAGE

        chapter.summary = summary
        # ``draft`` and only ``draft``: ``chapters.finalize_close_turn`` reads this
        # status as one of its four facts and is the only thing that ever writes
        # ``approved``.
        chapter.summary_status = SummaryStatus.draft
        chapter.modified_at = datetime.now(timezone.utc)
        await chapters_db.update(chapter)
        return _SUMMARY_WRITTEN_MESSAGE
    except Exception:
        logger.warning(
            "draft_chapter_summary: the summary could not be saved for book %s",
            getattr(context, "book_id", None),
            exc_info=True,
        )
        return _SUMMARY_FAILED_MESSAGE


async def draft_chapter_notes(
    context: "ToolContext", added: str, modified: str, deleted: str
) -> str:
    """Write the chapter's note changeset (UC-047 / US-073).

    ``context`` is bound at build time by :func:`bind_draft_chapter_notes`,
    leaving ``added`` / ``modified`` / ``deleted`` — exactly
    :class:`DraftChapterNotesArgs`' three fields — as the model-supplied
    arguments.

    Runs the four-rule refusal chain first, then **upserts** the chapter's single
    ``ChapterNoteChangeset`` row: created when none exists (``created_at``
    stamped here — timestamps are the service's, never ``db/``'s), updated when
    one does (``modified_at`` stamped here), with all three texts written and
    ``status = NoteStatus.draft`` in both cases. ``chapter_id`` is unique on the
    table, so there is exactly one row per chapter and no ordering question.

    Upsert rather than create-only because the row may already exist as a
    ``stale`` leftover of an earlier close, and because a second call within one
    run must replace the first rather than fail.

    **It never raises**: every refusal and every failure is a returned string.
    """
    try:
        refusal = _refuse_write(context)
        if refusal is not None:
            return refusal

        chapter = _resolved_chapter(context)
        if chapter is None:  # unreachable: ``_refuse_write`` already refused it
            return _NOT_A_CHAPTER_MESSAGE

        now = datetime.now(timezone.utc)
        existing = await chapter_note_changesets.get_by_chapter(chapter.id)
        if existing is None:
            await chapter_note_changesets.create(
                ChapterNoteChangeset(
                    chapter_id=chapter.id,
                    added=added,
                    modified=modified,
                    deleted=deleted,
                    status=NoteStatus.draft,
                    created_at=now,
                    modified_at=now,
                )
            )
        else:
            # UPSERT rather than create-only: the row may already exist as a
            # ``stale`` leftover of an earlier close, and a second call within one
            # run must replace the first rather than fail.
            existing.added = added
            existing.modified = modified
            existing.deleted = deleted
            existing.status = NoteStatus.draft
            existing.modified_at = now
            await chapter_note_changesets.update(existing)
        return _NOTES_WRITTEN_MESSAGE
    except Exception:
        logger.warning(
            "draft_chapter_notes: the changeset could not be saved for book %s",
            getattr(context, "book_id", None),
            exc_info=True,
        )
        return _NOTES_FAILED_MESSAGE


async def propose_active_notes(context: "ToolContext", active_notes: str) -> str:
    """Propose the book's resulting live note set — **held, not persisted**
    (decision D7; UC-047 / US-073).

    ``context`` is bound at build time by :func:`bind_propose_active_notes`,
    leaving ``active_notes`` — exactly :class:`ProposeActiveNotesArgs`' single
    field — as the only model-supplied argument.

    Runs the four-rule refusal chain first, then sets
    ``context.active_notes_proposal = active_notes`` **in place** and returns a
    confirmation. **It touches no database at all**: ``Book.active_notes`` is
    written by ``chapters.finalize_close_turn`` and by nothing else, only on the
    clean branch, and only from this held value. That is exactly what makes a
    stopped or failed run free to discard — nothing was ever applied.

    A repeated call **overwrites** the held value: the last proposal of the run
    is the one finalize reads.

    ``""`` is a legitimate proposal (an author's book may genuinely end up with
    no live notes) and is stored as ``""``. **Never calling this tool is not the
    same thing**: the field stays ``None``, and finalize routes a ``None``
    proposal to the wipe branch precisely so an uncalled tool can never erase the
    book's accumulated notes.

    **It never raises**: every refusal and every failure is a returned string.
    """
    try:
        refusal = _refuse_write(context)
        if refusal is not None:
            # A refusal records NOTHING: ``active_notes_proposal`` stays exactly
            # as it was, so a refused call can never make a run look clean.
            return refusal

        # IN PLACE, and NO DATABASE AT ALL (decision D7): the value is held on the
        # very context instance ``chat_turn`` will hand to
        # ``chapters.finalize_close_turn``, which is what makes a stopped or failed
        # run free to discard — nothing was ever applied. A repeated call
        # overwrites, so the LAST proposal of the run is the one finalize reads.
        context.active_notes_proposal = active_notes
        return _PROPOSAL_RECORDED_MESSAGE
    except Exception:
        logger.warning(
            "propose_active_notes: the proposal could not be recorded for book %s",
            getattr(context, "book_id", None),
            exc_info=True,
        )
        return _PROPOSAL_FAILED_MESSAGE


async def raise_check_flag(context: "ToolContext", comment: str) -> str:
    """Record one consistency-check finding on the closing chapter (UC-065 /
    UC-080; US-091, US-092).

    ``context`` is bound at build time by :func:`bind_raise_check_flag`, leaving
    ``comment`` — exactly :class:`RaiseCheckFlagArgs`' single field — as the only
    model-supplied argument.

    Runs the four-rule refusal chain first, then creates one ``Flag`` on the
    resolved chapter: ``origin = FlagOrigin.check``, ``status = FlagStatus.open``,
    ``comment`` as given, ``created_by = context.access.user_id``, ``created_at``
    stamped here, ``resolved_by`` / ``resolved_at`` ``None``. One call, one
    finding — there is no batch form.

    An open ``origin=check`` flag is what blocks the close:
    ``chapters.finalize_close_turn`` routes to ``open`` when it finds one, and
    ``chapters.close_chapter`` deletes the previous run's check flags when the
    next close starts (decision D6), so only **this** run's findings ever block.

    **It never raises**: every refusal and every failure is a returned string.
    """
    try:
        refusal = _refuse_write(context)
        if refusal is not None:
            return refusal

        chapter = _resolved_chapter(context)
        if chapter is None:  # unreachable: ``_refuse_write`` already refused it
            return _NOT_A_CHAPTER_MESSAGE

        access = context.access
        if access is None:
            # No caller to attribute the finding to. ``Flag.created_by`` is a
            # non-null FK, so this is a returned string rather than a raise.
            return _FLAG_FAILED_MESSAGE

        await flags_db.create(
            Flag(
                chapter_id=chapter.id,
                # ``check``, never ``person``: this is the close run's own finding.
                origin=FlagOrigin.check,
                comment=comment,
                status=FlagStatus.open,
                created_by=access.user_id,
                created_at=datetime.now(timezone.utc),
            )
        )
        return _FLAG_RAISED_MESSAGE
    except Exception:
        logger.warning(
            "raise_check_flag: the finding could not be recorded for book %s",
            getattr(context, "book_id", None),
            exc_info=True,
        )
        return _FLAG_FAILED_MESSAGE


async def read_continuity_context(context: "ToolContext") -> str:
    """Return the book's continuity so far, as a text digest for the model to
    check this chapter against (UC-064 / US-091).

    ``context`` is bound at build time by :func:`bind_read_continuity_context`,
    leaving **no** free parameters — :class:`ReadContinuityContextArgs` has no
    fields, so the model supplies nothing.

    **Read-only**, and therefore subject to rule 1 of the refusal chain alone (a
    non-chapter subject): a closing chapter, an archived book and a caller
    without ``set_chapter_state`` may all read, exactly as ``read_chapter_text``
    may. Reading is not writing.

    Returns a digest of the book's ``active_notes`` plus every
    **previously-closed** chapter's ``approved`` summary, in ordinal order, so
    the model can check the closing chapter against what the book already
    establishes. The closing chapter's own draft summary is not part of the
    digest — it is what is being checked, not what it is checked against.

    The chapter text, the codex and web search are reached through the tools that
    already exist; this one exists because nothing else surfaces the live notes
    or prior summaries.

    **It never raises**: every refusal and every failure is a returned string.
    """
    try:
        chapter = _resolved_chapter(context)
        if chapter is None:
            # RULE 1 ALONE — reading is not writing, exactly as
            # ``chapter_tools.read_chapter_text`` reads a chapter in any state.
            # A chapter of another book is refused by subject resolution rather
            # than by a check here, and comes back as this same string, so the
            # model learns nothing about what exists elsewhere.
            return _NOT_A_CHAPTER_MESSAGE

        book = await books_db.get_by_id(chapter.book_id)
        notes = "" if book is None else book.active_notes

        siblings = await chapters_db.list_by_book(chapter.book_id)
        summaries: list[str] = []
        for row in sorted(siblings, key=lambda item: item.ordinal):
            # PREVIOUSLY-CLOSED chapters only, and only their APPROVED summaries:
            # the closing chapter's own draft is what is being checked, not what it
            # is checked against, and a ``stale`` summary describes a chapter that
            # has moved on.
            if row.id == chapter.id:
                continue
            if row.state != ChapterState.closed:
                continue
            if row.summary_status != SummaryStatus.approved:
                continue
            if row.summary is None:
                continue
            summaries.append(f"{row.ordinal}. {row.title}\n{row.summary}")

        parts = [
            _DIGEST_NOTES_HEADING,
            notes if notes.strip() != "" else _DIGEST_NO_NOTES,
            "",
            _DIGEST_SUMMARIES_HEADING,
            "\n\n".join(summaries) if summaries else _DIGEST_NO_SUMMARIES,
        ]
        return "\n".join(parts)
    except Exception:
        logger.warning(
            "read_continuity_context: the continuity digest could not be read "
            "for book %s",
            getattr(context, "book_id", None),
            exc_info=True,
        )
        return _READ_FAILED_MESSAGE


def bind_draft_chapter_summary(context: "ToolContext") -> Callable[..., object]:
    """Bind ``context`` into :func:`draft_chapter_summary` — the
    ``ToolDef.binder``.

    Returns a callable whose only free parameter is
    :class:`DraftChapterSummaryArgs`' single field (``summary``), which is what
    the ``llm`` client's ``inspect.signature(func).parameters`` validation and its
    ``func(**kwargs)`` dispatch require, there being no per-request context
    argument.
    """
    return functools.partial(draft_chapter_summary, context)


def bind_draft_chapter_notes(context: "ToolContext") -> Callable[..., object]:
    """Bind ``context`` into :func:`draft_chapter_notes` — the ``ToolDef.binder``.

    Returns a callable whose free parameters are exactly
    :class:`DraftChapterNotesArgs`' three fields (``added`` / ``modified`` /
    ``deleted``), for the same reason as :func:`bind_draft_chapter_summary`.
    """
    return functools.partial(draft_chapter_notes, context)


def bind_propose_active_notes(context: "ToolContext") -> Callable[..., object]:
    """Bind ``context`` into :func:`propose_active_notes` — the
    ``ToolDef.binder``.

    Returns a callable whose only free parameter is
    :class:`ProposeActiveNotesArgs`' single field (``active_notes``). Binding is
    also what gives the tool the **very context instance** the turn will later
    hand to ``chapters.finalize_close_turn``, which is what lets a proposal be
    held in memory rather than persisted (decision D7).
    """
    return functools.partial(propose_active_notes, context)


def bind_raise_check_flag(context: "ToolContext") -> Callable[..., object]:
    """Bind ``context`` into :func:`raise_check_flag` — the ``ToolDef.binder``.

    Returns a callable whose only free parameter is :class:`RaiseCheckFlagArgs`'
    single field (``comment``), for the same reason as
    :func:`bind_draft_chapter_summary`.
    """
    return functools.partial(raise_check_flag, context)


def bind_read_continuity_context(context: "ToolContext") -> Callable[..., object]:
    """Bind ``context`` into :func:`read_continuity_context` — the
    ``ToolDef.binder``.

    Returns a callable with **no** free parameters, matching
    :class:`ReadContinuityContextArgs`' empty field set.
    """
    return functools.partial(read_continuity_context, context)
