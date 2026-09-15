"""The `create_memo` assistant tool — the first tool with a database write
behind it (feature 026, step 008).

The **sibling** of ``services/chapter_tools.py`` in shape and nothing else: one
callable behind ``services/tools.py:TOOL_REGISTRY``'s ``create_memo`` entry, its
argument schema and its binder. Tool modules define callables, schemas and
binders only; the ``ToolDef(...)`` entry itself is constructed in ``tools.py``,
which imports this module.

Business-logic layer: **no** ``session`` / ``AsyncSession`` / ``select()`` /
``session.exec()`` / ``session.add()`` here (``docs/architecture/backend.md`` —
layer separation). The row is written by ``services/memos.py``, which this module
calls; it reaches no ``app.db`` module itself.

The binding constraints are ``chapter_tools.py``'s, unchanged:

1. **No per-request context argument.** The ``llm`` client decodes a tool call's
   JSON arguments and applies them as ``func(**kwargs)``, validated against
   ``inspect.signature(func).parameters``. The callable therefore takes the
   turn's :class:`~app.services.tools.ToolContext` **positionally first**, so
   ``functools.partial(fn, context)`` leaves :class:`CreateMemoArgs`' single
   field as the only free parameter, and :func:`bind_create_memo` is the
   ``ToolDef.binder`` that performs exactly that application.
2. **No subject field and no id field on the schema.** See "It reads no subject"
   below.
3. **It never raises.** Every refusal and every failure comes back as a **string
   the model reads** — a raising tool aborts the whole turn.
4. **The import of** ``ToolContext`` **is** ``TYPE_CHECKING``-**only**:
   ``tools.py`` imports this module, so a runtime import here would be a cycle.

Two things a reader copying the neighbouring module would get wrong, stated
explicitly because that copy is the failure they exist to prevent:

**The refusal chain is ``access`` absent, and that is all.**
``chapter_tools.py:_refuse_write`` runs four links — chapter resolved → chapter
``open`` → book ``archived`` → co-author in ``proposal`` mode. This tool has
**none of them**. In particular there is **NO archived-book link**: per
``docs/architecture/authorization.md`` → "The one named exception: memos stay
writable on an archived book", a memo is not book content but the author's
private note *about* a book they have deliberately set aside, so the assistant is
refused by exactly the same rule as the author — which here means **not refused
at all** (``026/context.md`` → decision 4; step 008 DoD-9 is the test that
catches a copied chain). There is **no proposal-mode link** either: collaboration
mode governs shared book content, and a memo has no second reader. The only
verdict this module reaches on its own is that the context carries **no**
``access`` at all, and everything else — membership, and any other domain
refusal — is ``services/memos.py``'s, surfaced by catching
:class:`~app.services.memos.MemoError` and returning its message-bearing string.

**It reads no subject.** ``context.subject`` is never consulted:
:attr:`~app.services.tools.ToolContext.book_id` comes from the tool context
(which the route built), and the memo's author from
``context.access.user_id`` — **never** from the resolved subject. The two are
the same book by construction: ``services/chat_turn.py:run_turn`` builds
``book_id`` and ``access`` from one resolved turn. That is what keeps the
cross-book rule untouched (no subject means no cross-book question to ask) and
what makes widening ``assistant_runtime.BASE_TOOL_NAMES`` to this tool safe: with
no subject, with the memos list as the subject, and with an unrelated subject,
the tool behaves identically and always writes into the book the route named
(DoD-4).

The ordinal is **not computed here.** ``services/memos.py:create_memo`` owns the
append-at-``max + 1`` rule and the ``active`` default, so the assistant's create
and the author's own create go through one implementation and can never drift
(DoD-3).
"""

import functools
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from app.models.schemas.memos import CreateMemoRequest
from app.services import memos as memo_service

if TYPE_CHECKING:  # pragma: no cover - import cycle guard, see module docstring
    from app.services.tools import ToolContext

logger = logging.getLogger(__name__)


# Every string this tool returns when it refuses or fails. Module-level constants
# for ``chapter_tools.py``'s reason: the never-raise contract makes them the
# *only* signal the model gets, so the wording must not drift between call
# sites. The same two-vocabulary split applies — a **refusal** ("Memo refused:
# …") is a verdict about what the caller may do and reads the same on every
# retry; an **error** ("Memo error: …") is a failure the model may reasonably
# try again.
_NO_ACCESS_MESSAGE = (
    "Memo refused: this conversation carries no book access, so there is no "
    "author to hold the memo. Ask the author to try again from the book."
)
_REFUSED_MESSAGE = "Memo refused: {message}"
_CREATE_FAILED_MESSAGE = "Memo error: the memo could not be created."
_CREATED_MESSAGE = "Memo created. It is active and at the end of your memo list."


class CreateMemoArgs(BaseModel):
    """Arguments for creating one memo for the author of this conversation.

    Send the memo's whole text. It is saved immediately, as a standing note the
    author keeps for this book.
    """

    body: str = Field(
        description=(
            "The complete text of the memo to save — the standing note itself, "
            "as the author wants to keep it. Send it whole; there is nothing to "
            "add to it afterwards."
        )
    )


async def create_memo(context: "ToolContext", body: str) -> str:
    """Create one memo for the turn's author in the turn's book (US-129).

    ``context`` is bound at build time by :func:`bind_create_memo`, leaving
    :class:`CreateMemoArgs`' single ``body`` field as the only free parameter.

    Calls ``services/memos.py:create_memo`` with ``context.access`` and a
    :class:`~app.models.schemas.memos.CreateMemoRequest`, so the memo is
    appended at ``max + 1`` and created ``active`` by the same code path the
    author's own create uses — **no ordinal is computed here** (DoD-1..DoD-3).

    Reads **no subject** and applies **no archived-book and no proposal-mode
    check** — see the module docstring for both, and for the refusal chain, which
    is an absent ``context.access`` and nothing else (DoD-4, DoD-9).

    **It never raises** (DoD-8): an absent access, a caller who is not a member
    and any other service-level refusal each come back as a refusal string, and
    an unexpected failure as an error string.

    Returns a short confirmation on success.
    """
    # The outer never-raise guard (constraint 3), ``chapter_tools.py``'s shape:
    # a failure mode nobody enumerated must still come back as a string.
    # ``Exception`` is deliberately broad; ``asyncio.CancelledError`` is a
    # ``BaseException`` and still propagates, so a cancelled turn is not
    # swallowed.
    try:
        access = context.access
        if access is None:
            # The ONLY verdict this module reaches on its own. There is no
            # archived-book link and no proposal-mode link after it — see the
            # module docstring. ``context.subject`` is not consulted here or
            # anywhere below.
            return _NO_ACCESS_MESSAGE

        try:
            # ``services/memos.py`` owns the append-at-``max + 1`` rule, the
            # ``active`` default and the membership guard, so none of the three
            # is recomputed here; the book is ``access.book_id`` and the author
            # ``access.user_id``, both carried by the access the route built.
            # The request DTO is constructed, not a bare string (step 002's
            # entry-point contract).
            await memo_service.create_memo(
                access, CreateMemoRequest(body=body)
            )
        except memo_service.MemoError as err:
            # Every other refusal is the service's — a caller who is not a
            # member, today, and whatever it grows later. It is surfaced as a
            # string the model reads, never re-raised.
            return _REFUSED_MESSAGE.format(message=err.message)

        return _CREATED_MESSAGE
    except Exception:
        logger.warning(
            "create_memo: the memo could not be created for book %s",
            getattr(context, "book_id", None),
            exc_info=True,
        )
        return _CREATE_FAILED_MESSAGE


def bind_create_memo(context: "ToolContext") -> Callable[..., object]:
    """Bind ``context`` into :func:`create_memo` — the ``ToolDef.binder``.

    Returns a callable whose only free parameter is :class:`CreateMemoArgs`'
    single field (``body``), which is what the ``llm`` client's
    ``inspect.signature(func).parameters`` validation and its ``func(**kwargs)``
    dispatch require, there being no per-request context argument. Binding is
    also what carries the turn's book and the caller's access into the tool: the
    model supplies neither, and cannot.
    """
    return functools.partial(create_memo, context)
