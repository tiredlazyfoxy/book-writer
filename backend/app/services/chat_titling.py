"""Chat auto-titling (feature 023).

A chat names itself from its own opening exchange: after the author's **1st** and
**5th** user message the client fires ``POST /{book_id}/chats/{chat_id}/title``
and this service decides whether anything happens. The **policy lives here**, not
on the client — the client only fires the call (023 → D2).

Design facts this module is built on (``docs/plans/023.chat-ux-revision/plan.md``
→ Decisions taken):

- **D2 — an ordinary route + service, not background work.** This backend has no
  background-task infrastructure at all (no ``BackgroundTasks``, no queue, no
  registry), so "background" is achieved by firing the call *after* the turn's
  terminal frame rather than by detaching a task. Nothing here is scheduled.
- **D3 — the trigger is derived from a LIVE count, not a stored flag.** No
  ``Chat`` column records "titling already ran"; :func:`_is_titling_trigger` reads
  ``db.chat_messages.count_by_chat_and_role(chat.id, "user")`` on every call and
  fires only at **exactly** 1 or 5 (never ``>=``). No column is added, so
  ``services/db_import_export.py`` is untouched.
- **D4 — the chat's OWN model pair titles it.** There is no "utility"/"small"
  model designation anywhere in the schema; this mirrors
  ``subagent_delegation.ParentTurn``'s inherit-the-parent's-pair precedent. The
  client is resolved exactly the way ``services/embedding.py`` resolves one —
  server row → ``secrets.resolve_env_ref``'d key →
  ``llm_servers.create_model_client(...)`` entered ``async with`` — but the
  failure handling is ``_finalize_close_turn_if_needed``'s **swallow**, not
  ``embedding.py``'s re-raise.

**Failures are invisible to the author.** A missing model pair, any member of the
turn failure taxonomy (``aiohttp.ClientError``, ``LLMError``, ``ValueError``,
``RuntimeError``) and a blank sanitized result are all swallowed identically: the
existing title stands, ``changed=False`` comes back, nothing is persisted and
nothing is raised. The **only** exception allowed out of :func:`maybe_title_chat`
is the ``ChatError(chat_not_found)`` that ``chats._resolve_owned_chat`` raises for
a chat that does not exist or is not the caller's — the route maps it to a 404.

Layer discipline: this is a service, so it holds no session, no ``select()`` and
no ORM query; it reads through ``app.db`` modules and writes through
``db.chats.update``. It reuses ``services/chats.py``'s ``_resolve_owned_chat`` /
``_parse_chat_id`` privates, exactly as ``chat_turn.prepare_turn`` already does.

NOTE (import path): the plan's Risks section expected
``from llm import LLMMessage``. That symbol is **not** re-exported by the ``llm``
package's ``__init__``; it is a ``TypedDict`` declared in ``llm/message.py``
(``role: str`` / ``content: str``). The verified import is therefore
``from llm.message import LLMMessage`` — a same-file import fix, no frozen
signature changed.
"""

import logging

import aiohttp
from llm import LLMError
from llm.message import LLMMessage

from app.db import chat_messages
from app.db import chats as chats_db
from app.db import llm_servers as llm_servers_db
from app.models.chat import ChatMessage
from app.models.schemas.chats import ChatTitleResponse
from app.services import authz
from app.services import chats as chats_service
from app.services import llm_servers as llm_servers_service
from app.services import secrets

logger = logging.getLogger(__name__)

# The user-message counts at which a chat is (re)titled — the **1st** message
# names a brand-new chat, the **5th** improves that name once the conversation has
# a shape. A ``frozenset`` and not a ``>=`` bound: titling must fire at exactly
# these two counts and at no other, or every subsequent message would re-title
# (023 → D3).
_TITLE_TRIGGER_COUNTS: frozenset[int] = frozenset({1, 5})

# The sanitizer's hard cap on a generated title's length. Planner-owned — no DoD
# pins the number; it exists so a model that answers with a paragraph cannot write
# a paragraph into ``Chat.title``.
_TITLE_MAX_LENGTH = 80

# The failure taxonomy a titling call may produce, defined **locally** rather than
# imported from ``chat_turn``'s private ``_TURN_FAILURE_EXCEPTIONS``: the same four
# classes for the same reason (``aiohttp.ClientError`` — connection / DNS / timeout,
# NOT wrapped by the ``llm`` library; ``LLMError`` — non-2xx; ``ValueError`` /
# ``RuntimeError`` — the library's own argument / protocol failures), but no new
# cross-service coupling to another module's private constant
# (``context.md`` → Backend ground truth).
_TITLE_FAILURE_EXCEPTIONS: tuple[type[Exception], ...] = (
    aiohttp.ClientError,
    LLMError,
    ValueError,
    RuntimeError,
)

# The quote characters :func:`_sanitize_title` unwraps when a model answers with a
# quoted title (``"Kestrel's last run"``). Only a MATCHING PAIR at both ends is
# removed, so an inner quotation survives.
_TITLE_QUOTE_CHARS = "\"'“”‘’`«»"

# The one-shot instruction appended AFTER the conversation transcript. It is a real
# user turn in the request (never persisted — the chat's own transcript is
# untouched), which is what makes this a plain ``chat`` call with no system layer
# and no options. Its wording is deliberately not pinned by any DoD (``plan.md`` →
# Test plan: "the titling prompt's wording … covered as ``[manual/live]``").
_TITLE_INSTRUCTION = (
    "Name this conversation. Reply with a short title of at most a few words that "
    "says what it is about — plain text on a single line, no quotes, no prefix, no "
    "punctuation at the end, and nothing else."
)


def _is_titling_trigger(user_message_count: int) -> bool:
    """Whether ``user_message_count`` is one of the two counts that title a chat.

    True for **exactly** 1 and **exactly** 5, false for everything else — 0, 2, 3,
    4, 6 and up (023 → D3; DoD-1). Pure.
    """
    # Membership, NOT a ``>=`` bound: every count outside the frozen set — including
    # every count above 5 — leaves the chat's title alone.
    return user_message_count in _TITLE_TRIGGER_COUNTS


def _build_title_transcript(messages: list[ChatMessage]) -> list[LLMMessage]:
    """Map persisted messages onto the ``llm`` client's chat-message shape for the
    one-shot summarization prompt — role + content, **oldest first**.

    Pure: it reads the rows it is handed and builds the request transcript; it
    neither queries nor calls a model.

    Exactly one ``LLMMessage`` per persisted row, in the order given — the caller
    passes ``list_by_chat_ordered``'s ``position``-ascending rows, so the result is
    oldest first. The titling INSTRUCTION is not a persisted row and is therefore
    not built here; :func:`maybe_title_chat` appends it to the returned list.
    """
    return [
        LLMMessage(role=message.role, content=message.content)
        for message in messages
    ]


def _sanitize_title(raw: str) -> str:
    """Reduce a model's raw answer to a storable one-line title.

    Strips wrapping quotes and surrounding whitespace, collapses newlines so the
    result is a single line, and caps the length at :data:`_TITLE_MAX_LENGTH`.
    Returns ``""`` when nothing usable remains — **an empty result is a failure**,
    handled by the caller exactly like an exception (DoD-2). Pure.
    """
    # ``str.split()`` with no argument splits on ANY run of whitespace, so this one
    # step collapses newlines, tabs and repeated spaces into a single line at once.
    title = " ".join(raw.split())

    # Unwrap only a MATCHING PAIR of quote characters, repeatedly (a model that
    # answers ``"'Title'"`` is unwrapped twice) — never a lone quote at one end, so
    # ``He said "no`` keeps whatever it has.
    while (
        len(title) >= 2
        and title[0] in _TITLE_QUOTE_CHARS
        and title[-1] in _TITLE_QUOTE_CHARS
    ):
        title = title[1:-1].strip()

    if title == "":
        return ""

    if len(title) > _TITLE_MAX_LENGTH:
        # Hard cap, then drop a dangling space so the truncation never ends mid-gap.
        title = title[:_TITLE_MAX_LENGTH].rstrip()

    return title


async def maybe_title_chat(
    access: authz.BookAccess, chat_id: str
) -> ChatTitleResponse:
    """Title the chat when it is at a trigger count, otherwise do nothing (023).

    Resolves the caller's own chat through ``chats._resolve_owned_chat`` /
    ``chats._parse_chat_id`` — the ``ChatError(chat_not_found)`` that raises is the
    **only** exception this function lets out — then counts the chat's ``"user"``
    messages via ``db.chat_messages.count_by_chat_and_role``.

    **Off-trigger** (:func:`_is_titling_trigger` false): returns
    ``ChatTitleResponse(title=chat.title, changed=False)`` and makes **no** LLM
    call at all (DoD-1).

    **On-trigger**: resolves the chat's own ``(llm_server_id, model_name)`` pair
    (D4) to a server row plus a ``secrets.resolve_env_ref``-resolved key, opens
    ``llm_servers.create_model_client(...)`` as an ``async with``, calls
    ``client.chat(transcript)`` over :func:`_build_title_transcript`'s messages,
    runs :func:`_sanitize_title` over the answer, and — for a **non-empty** result
    — mutates ``chat.title`` and persists through ``db.chats.update`` before
    returning ``changed=True`` (DoD-3).

    **Every failure is swallowed identically** and reported as the existing title
    with ``changed=False``, persisting nothing and raising nothing: a chat with no
    model pair, any of ``(aiohttp.ClientError, LLMError, ValueError,
    RuntimeError)``, and a blank sanitized result (DoD-2).
    """
    # The ONLY exception this function lets out: a chat that does not exist or is
    # not the caller's raises ``ChatError(chat_not_found)`` here, and the route maps
    # it to 404 (never 403 — US-061.AC-1).
    chat = await chats_service._resolve_owned_chat(
        access, chats_service._parse_chat_id(chat_id)
    )
    # The unchanged answer, built once: every refusal and every swallowed failure
    # below returns exactly this.
    unchanged = ChatTitleResponse(title=chat.title, changed=False)

    user_message_count = await chat_messages.count_by_chat_and_role(chat.id, "user")
    if not _is_titling_trigger(user_message_count):
        # OFF-TRIGGER: no server lookup, no key resolution, NO CLIENT AT ALL — the
        # common case is the one that must cost nothing (DoD-1).
        return unchanged

    # D4: the chat's OWN pair titles it. A chat with no model configured is a
    # swallowed failure like any other, not a refusal — the author asked for a
    # message, not for a title.
    if chat.llm_server_id is None or chat.model_name is None:
        logger.warning(
            "Chat %s has no model pair, so it was not auto-titled.", chat.id
        )
        return unchanged

    server = await llm_servers_db.get_by_id(chat.llm_server_id)
    if server is None or not server.is_active:
        logger.warning(
            "Chat %s's server is unknown or inactive, so it was not auto-titled.",
            chat.id,
        )
        return unchanged

    try:
        # The ``$ENV`` ref is resolved at USE time (never at rest) and an unset
        # variable raises ``LlmServerError(env_not_set)`` — which is a titling
        # failure like the four library ones, so it is swallowed here rather than
        # reaching the route as ``prepare_turn``'s 400 does.
        resolved_key = secrets.resolve_env_ref(server.api_key)
        messages = await chat_messages.list_by_chat_ordered(chat.id)
        transcript = _build_title_transcript(messages)
        transcript.append(
            LLMMessage(role="user", content=_TITLE_INSTRUCTION)
        )
        # ``async with`` is what closes the client's aiohttp session on EVERY path,
        # including failure — :class:`~llm.LLMClient` has no standalone ``close()``
        # (the ``embedding.py`` resolution shape, with a swallow in place of its
        # re-raise).
        async with llm_servers_service.create_model_client(
            server, resolved_key, chat.model_name
        ) as client:
            raw = await client.chat(transcript)
    except (
        llm_servers_service.LlmServerError,
        *_TITLE_FAILURE_EXCEPTIONS,
    ) as exc:
        # SWALLOW-AND-LOG, mirroring ``chat_turn._finalize_close_turn_if_needed``:
        # a title is a nicety, and its failure must never surface to the author as
        # a failed request or a failed turn.
        logger.warning("Auto-titling chat %s failed: %s", chat.id, exc)
        return unchanged

    title = _sanitize_title(raw)
    if title == "":
        # A blank result is a failure, handled identically to an exception (DoD-2):
        # nothing is persisted and the existing title stands.
        logger.warning(
            "Auto-titling chat %s produced no usable title.", chat.id
        )
        return unchanged

    chat.title = title
    # ``db.chats.update`` persists the changed column and bumps ``modified_at``
    # itself; the service holds no session.
    updated = await chats_db.update(chat)
    return ChatTitleResponse(title=updated.title, changed=True)
