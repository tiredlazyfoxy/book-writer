"""The streaming assistant turn — the orchestrator, the think splitter, and the
per-backend sampling-options builder (feature 011, step 003).

Business-logic layer: **no** ``session`` / ``AsyncSession`` / ``select()`` /
``session.exec()`` / ``session.add()`` here (see ``docs/architecture/backend.md``
— layer separation). All persistence goes through the session-free ``app.db``
modules; the HTTP/SSE response is constructed one layer up in ``routes/chats.py``,
not here (this module only *yields* typed frames).

The turn is split across the "before the first frame" boundary that DoD-8 / DoD-10
pin:

- :func:`prepare_turn` runs the **pre-stream refusals** — ownership, a model pair
  actually set on the chat, an active server, a resolvable key — raising the
  step-001 typed :class:`~app.services.chats.ChatError` (or
  :class:`~app.services.llm_servers.LlmServerError` for an unset key env var)
  **before anything is persisted and before the first frame**, so the route maps
  them to ordinary 404 / 400 JSON errors.
- :func:`run_turn` is the **frame-yielding orchestrator**: it persists the user
  message first (so a retry never duplicates it), composes the prompt, drives
  ``chat_with_tools`` in streaming mode through the splitter, persists the
  assistant message from the streamed deltas, and yields the four frame kinds.
  Once it starts, every library failure surfaces as a single ``error`` frame — it
  never escapes as a 500 (:data:`_TURN_FAILURE_EXCEPTIONS`, plus the empty-result
  case which has no dedicated exception).

The whole ``chat_with_tools`` call is the **replaceable interior** the brief asks
to keep behind this boundary (``003.context.md`` → "Bounds and the deferred
interior"): swapping it for a manual ``chat``-in-a-loop driver when the
shared-canvas SSE protocol arrives should touch nothing outside :func:`run_turn`.

Skeleton (011 step 003): ``ThinkSplitter``'s method bodies, the sampling-options
builder, :func:`prepare_turn` and :func:`run_turn` are UNIMPLEMENTED; the
signatures, the frame envelope, the channel vocabulary, :data:`MAX_LOOPS` and
:data:`_TURN_FAILURE_EXCEPTIONS` are the frozen contract.

Skeleton (013 step 007): the turn becomes **subject-aware**. :func:`prepare_turn`
takes the whole :class:`~app.models.schemas.chats.TurnRequest` and resolves its
subject fields **before the stream opens** (the phase that already exists for
"resolve everything, refuse nothing later"), storing the result on
:class:`TurnContext` as ``subject``; :func:`run_turn` reads that subject's mode
key to populate ``compose_system_prompt``'s ``mode=`` layer and to replace 011's
``resolve_tools(None)`` seam with a real allowlist. Both new parameters/fields
default, so every 011 call shape still binds unchanged.

Skeleton (013 step 008): the turn's tools are resolved in **one** call —
:func:`app.services.assistant_runtime.resolve_turn_tools` returns the real
registry tools *and* the mode's synthetic sub-agent delegation tools, and the
combined list is handed to ``build_tool_bindings`` together (the ``llm`` client
pre-flights the two maps against each other). :func:`run_turn` builds the
:class:`~app.services.subagent_delegation.ParentTurn` value a delegation inherits
from — the parent's server, resolved key and model. Nothing else changes.

Skeleton (013 step 009): the turn also builds the
:class:`~app.services.tools.ToolContext` that **bound** tools are closed over —
this step, the turn's book id, which is the codex tools' hard filter — and hands
it to ``build_tool_bindings`` beside the resolved tool list. The ``llm`` client
passes no per-request context argument, so a bound tool can only receive it at
binding time.

Skeleton (013 step 010): that same tool context now also carries the turn's
:class:`~app.services.authz.BookAccess`, its already-resolved content-pane
subject and a **frame emitter** — a closure over the very queue :func:`run_turn`
pumps ``thinking`` / ``delta`` through, so the shared-canvas ``canvas`` frame a
tool emits is ordered naturally among the surrounding frames and there is no
second transport. The queue is therefore created **before** the tools are bound.
The same context rides on :class:`~app.services.subagent_delegation.ParentTurn`,
so a sub-agent whose ``subagent_tool`` rows select a bound tool can bind it too.
Nothing else about the turn changes, and ``routes/chats.py`` is untouched: its
serializer is generic over the event name, so a ``TurnFrame`` whose event is
``canvas`` is emitted correctly with no route edit.
"""

import asyncio
import functools
import inspect
import logging
from collections.abc import AsyncGenerator, Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

import aiohttp
from llm import LLMError
from pydantic import BaseModel

from app.db import book_author_prompts, chapter_author_prompts, chat_messages
from app.db import llm_servers as llm_servers_db
from app.models.chapter import ChapterState
from app.models.chat import Chat, ChatMessage
from app.models.llm_server import LlmServer
from app.models.schemas.chats import (
    ChatSamplingParams,
    DeltaFrame,
    DoneFrame,
    ErrorFrame,
    ThinkingFrame,
    ToolCallFrame,
    ToolResultFrame,
    ToolTrace,
    ToolTraceEntry,
    TurnRequest,
)
from app.services import assistant_runtime
from app.services import authz
from app.services import chapters as chapters_service
from app.services import chats as chats_service
from app.services import llm_servers as llm_servers_service
from app.services import prompt_composition
from app.services import secrets
from app.services import subagent_delegation
from app.services import tools as tools_service
from app.services.tools import FrameEmitter

logger = logging.getLogger(__name__)

# Bounded tool-call rounds per turn (``assistant-config.md`` → "The tool /
# function-call protocol"; ``003.context.md`` → "Bounds"). Kept small and named so
# an exhausted loop (which the library raises as ``RuntimeError``) is a deliberate,
# visible bound rather than a magic literal at the call site.
MAX_LOOPS = 4

# The failure-taxonomy surface: every exception class :func:`run_turn` converts
# into a single ``error`` frame once the stream has opened (never a 500 or a hung
# stream). ``aiohttp.ClientError`` — connection / DNS / timeout and streaming
# ``raise_for_status`` (connection failures are NOT wrapped in ``LLMError``);
# ``LLMError`` — non-2xx; ``ValueError`` — a tool-definition / callable mismatch at
# pre-flight; ``RuntimeError`` — a tool raised or ``MAX_LOOPS`` was exhausted. An
# **empty result** has no dedicated exception and must be treated as a failure too
# ("the LLM ... returns nothing", UC-056) — that check is behaviour, not a type.
_TURN_FAILURE_EXCEPTIONS: tuple[type[Exception], ...] = (
    aiohttp.ClientError,
    LLMError,
    ValueError,
    RuntimeError,
)

# The two channels the think splitter routes text onto. ``"thinking"`` text is
# emitted as ``thinking`` frames; ``"content"`` text as ``delta`` frames.
Channel = Literal["thinking", "content"]
CHANNEL_THINKING: Channel = "thinking"
CHANNEL_CONTENT: Channel = "content"

# The reasoning tags inlined into ``content`` by ``--reasoning-format none``
# (``context.md`` → decision 7). The splitter watches for the open tag on the
# content channel and the close tag on the thinking channel.
_THINK_OPEN = "<think>"
_THINK_CLOSE = "</think>"


def _partial_suffix_len(buffer: str, tag: str) -> int:
    """Longest ``k`` in ``[1, len(tag) - 1]`` for which ``buffer[-k:] == tag[:k]``
    — i.e. the length of a partial tag prefix sitting at the tail of ``buffer``
    that must be held back because the next chunk could still complete it. Returns
    ``0`` when no proper prefix of ``tag`` ends ``buffer`` (a full match is handled
    by the caller separately, so ``k`` stops one short of ``len(tag)``)."""
    max_k = min(len(buffer), len(tag) - 1)
    for k in range(max_k, 0, -1):
        if buffer[-k:] == tag[:k]:
            return k
    return 0


class ThinkSplitter:
    """Splits ``<think>`` / ``</think>`` reasoning out of a token stream into
    ``(channel, text)`` segments, correct across adversarial chunkings.

    Fed the raw text chunks from ``on_delta`` via :meth:`feed`; each call returns
    the ``(channel, text)`` segments decided so far (``channel`` is
    :data:`CHANNEL_THINKING` or :data:`CHANNEL_CONTENT`). It must be correct for a
    tag **glued to payload text inside one chunk** and for a tag **split across
    chunk boundaries** — which means holding back any trailing text that could
    still become a tag prefix, and never losing or duplicating a character. A naive
    per-chunk ``split()`` or substring check is wrong (DoD-1).

    :meth:`flush` closes the stream. End-of-stream rules are explicit: an unclosed
    ``<think>`` leaves the remaining buffered text on the **thinking** channel; a
    held-back partial that turns out not to be a tag is flushed **verbatim** on the
    channel that was current.

    Skeleton (011 step 003): construction establishes no frozen state; the two
    methods below are UNIMPLEMENTED.
    """

    def __init__(self) -> None:
        # ``_channel`` is the channel the current (undecided) text belongs to; a
        # stream starts on the content channel. ``_buffer`` holds text not yet
        # emitted — either because a tag boundary is still being sought or because
        # its tail could still become a tag prefix across the next chunk boundary.
        self._channel: Channel = CHANNEL_CONTENT
        self._buffer: str = ""

    def feed(self, chunk: str) -> list[tuple[Channel, str]]:
        """Consume one raw text ``chunk`` and return the ``(channel, text)``
        segments now decided. Trailing text that could still be a tag prefix is
        held back for the next :meth:`feed` / :meth:`flush`.
        """
        self._buffer += chunk
        segments: list[tuple[Channel, str]] = []
        while True:
            tag = (
                _THINK_CLOSE
                if self._channel == CHANNEL_THINKING
                else _THINK_OPEN
            )
            idx = self._buffer.find(tag)
            if idx != -1:
                # A full tag is present: emit everything before it on the current
                # channel, drop the tag itself, and flip channels.
                head = self._buffer[:idx]
                if head:
                    segments.append((self._channel, head))
                self._buffer = self._buffer[idx + len(tag):]
                self._channel = (
                    CHANNEL_CONTENT
                    if self._channel == CHANNEL_THINKING
                    else CHANNEL_THINKING
                )
                continue
            # No full tag: emit all text except a tail that could still be the
            # start of the tag on a later chunk; hold that tail back.
            hold = _partial_suffix_len(self._buffer, tag)
            emit_upto = len(self._buffer) - hold
            if emit_upto > 0:
                segments.append((self._channel, self._buffer[:emit_upto]))
                self._buffer = self._buffer[emit_upto:]
            break
        return segments

    def flush(self) -> list[tuple[Channel, str]]:
        """Close the stream and return any final ``(channel, text)`` segments held
        back: an unclosed ``<think>`` yields its remainder on
        :data:`CHANNEL_THINKING`; a non-tag partial is emitted verbatim on the
        channel that was current.
        """
        segments: list[tuple[Channel, str]] = []
        if self._buffer:
            segments.append((self._channel, self._buffer))
            self._buffer = ""
        return segments


def build_sampling_options(
    sampling: ChatSamplingParams, backend_type: str
) -> dict[str, object]:
    """Build the ``options`` mapping passed to ``chat_with_tools`` for a turn.

    Returns the sampling params **only for a ``"llama-swap"`` server**; an
    ``"openai"`` server gets **none** (an empty mapping) — user decision 4 /
    DoD-6. The ``llm`` library filters whatever is passed against its own
    allowlist, so ``top_k`` / ``repeat_penalty`` / ``min_p`` are dropped inside the
    dependency today even when emitted (``context.md`` → the option allowlist);
    they are still carried per decision 5 and go live the moment the dependency is
    patched.

    """
    if backend_type != "llama-swap":
        return {}
    return sampling.model_dump()


@dataclass(frozen=True)
class TurnContext:
    """The result of :func:`prepare_turn` — everything :func:`run_turn` needs, all
    already resolved and validated so no refusal can occur once the stream opens.

    - ``chat`` — the owned :class:`~app.models.chat.Chat` row (its ``model_name``
      is non-null past :func:`prepare_turn`).
    - ``server`` — the resolved active :class:`~app.models.llm_server.LlmServer`.
    - ``resolved_key`` — the api key with ``$ENV`` indirection already resolved
      (``None`` when the server carries no key).
    - ``subject`` — the turn's resolved content-pane subject and its FEAT-020
      mode key (013 step 007). Defaults to
      :data:`~app.services.assistant_runtime.NO_SUBJECT`, which is exactly what a
      ``TurnRequest`` carrying no subject fields resolves to, so every 011 call
      site that builds a context by keyword keeps binding unchanged.
    - ``access`` — the caller's :class:`~app.services.authz.BookAccess` for this
      book (013 step 010), carried through from :func:`prepare_turn` so
      :func:`run_turn` can put it on the turn's
      :class:`~app.services.tools.ToolContext`. The shared-canvas write needs the
      caller's role and the book's collaboration mode to mirror the client's
      write gate server-side (``context.md`` decision 3); no other turn concern
      reads it. **Defaulted** for the same reason ``subject`` is — 011's and
      013's shipped tests build this record by keyword.
    - ``selection_text`` — the author's current selection, straight off
      :attr:`~app.models.schemas.chats.TurnRequest.selection_text` (015 step
      009). This record is the **only** carrier between :func:`prepare_turn`,
      which parses the request, and :func:`run_turn`, which builds the turn's
      :class:`~app.services.tools.ToolContext`; a selection-write tool reads it
      from there. Text only, never persisted (``015/context.md`` → D5), and
      **defaulted** so every existing keyword construction keeps binding.
    """

    chat: Chat
    server: LlmServer
    resolved_key: str | None
    subject: assistant_runtime.ResolvedSubject = assistant_runtime.NO_SUBJECT
    access: authz.BookAccess | None = None
    selection_text: str | None = None


@dataclass(frozen=True)
class TurnFrame:
    """One SSE frame the orchestrator yields: an ``event`` name plus its typed
    ``data`` payload. The route serializes it as
    ``event: <event>\\ndata: <data.model_dump_json()>\\n\\n``.

    ``event`` is exactly one of ``"thinking"`` / ``"delta"`` / ``"done"`` /
    ``"error"`` — the names ``frontend/src/api/sse.ts:streamPost()`` special-cases.
    ``data`` is the matching frame payload model from ``models/schemas/chats.py``
    (``ThinkingFrame`` / ``DeltaFrame`` / ``DoneFrame`` / ``ErrorFrame``) so nothing
    serializes from a free dict.
    """

    event: str
    data: BaseModel


# Sentinel pushed onto the stream queue by the driving task when the
# ``chat_with_tools`` call (and the splitter flush) are finished, so the
# frame-yielding loop knows to stop awaiting more deltas.
_STREAM_DONE = object()

# The single author-facing failure message. Deliberately generic — internals /
# provider errors are logged, never surfaced (UC-056 / US-060: the turn failed,
# the user message stays stored, a retry is offered).
_ERROR_MESSAGE = (
    "The assistant could not complete this turn. Please try again."
)

# What a tool that RAISED returns to the model instead (024). Every tool module's
# contract is "a tool never raises" — this is the wrapper keeping that contract on
# behalf of one that broke it, so ``chat_with_tools`` sees an ordinary string
# result and the turn carries on rather than aborting on a ``RuntimeError``.
_TOOL_FAILED_MESSAGE = "Tool '{name}' failed: {error}"

# How many characters of a tool result the debug dump prints per call (D5). A tool
# result can be a whole chapter; the dump is a diagnostic, not an archive.
_DEBUG_RESULT_CHARS = 2000


async def _emit_trace_frame(
    emit_frame: FrameEmitter, event: str, data: BaseModel
) -> None:
    """Put one trace frame on the turn's stream, swallowing a delivery failure.

    The trace is a VISIBILITY channel: if a frame cannot be delivered the author
    loses sight of one call, but the tool call itself — and therefore the turn —
    must be entirely unaffected. So a failure here is logged and swallowed, never
    raised into :func:`_wrap_tool_with_trace`'s body, and never allowed to change
    what the model is told the tool returned. Mirrors the way
    ``services/codex_tools.py`` already guards its own ``canvas`` emission.
    """
    try:
        await emit_frame(event, data)
    except Exception:
        logger.warning(
            "the %s frame could not be delivered", event, exc_info=True
        )


def _wrap_tool_with_trace(
    name: str,
    func: Callable[..., object],
    emit_frame: FrameEmitter,
    trace: list[ToolTraceEntry],
) -> Callable[..., Awaitable[str]]:
    """Wrap one bound tool callable so every call it receives is announced,
    reported and recorded (024, D1).

    Returns an **async** wrapper closing over ``name`` / ``func`` / ``emit_frame``
    / ``trace``. On call it must:

    1. emit a ``tool_call`` frame
       (``ToolCallFrame(tool_name=name, arguments=kwargs)``) BEFORE invoking the
       tool;
    2. invoke ``func(**kwargs)``, awaiting the result if it is awaitable;
    3. emit a ``tool_result`` frame
       (``ToolResultFrame(tool_name=name, result=<str>, ok=<bool>)``) after;
    4. append exactly one :class:`ToolTraceEntry` to ``trace``, in call order.

    **It never raises, and always returns a ``str``.** That is load-bearing —
    every tool module's contract is "a tool never raises", and
    ``chat_with_tools`` re-raises an escaping exception as ``RuntimeError`` and
    aborts the whole turn. Three guards hold it:

    - an exception from ``func`` becomes an error-string result with ``ok=False``
      — the tool failed, and that is what the model and the trace are told;
    - an exception from **either** ``emit_frame`` call is caught inside
      :func:`_emit_trace_frame`, logged and swallowed, so a failed frame emission
      never aborts the tool call: the tool still runs and its REAL result is what
      the model, the trace and the caller receive. A lost visibility frame must
      not rewrite what the assistant was told a tool returned;
    - an outermost guard covers anything else (a non-serializable argument, a
      failed model construction), so nothing at all escapes into
      ``chat_with_tools``'s dispatch loop.

    Applied once per entry of the turn's existing ``tool_map``, immediately before
    the existing ``client.chat_with_tools(...)`` call; ``tools=`` then receives the
    wrapped dict and **every other argument is unchanged**.
    """

    @functools.wraps(func)
    async def traced_tool(**kwargs: object) -> str:
        # ``dict(kwargs)`` — the arguments as the model produced them, snapshotted
        # so the frame and the trace entry can never diverge from each other.
        arguments: dict[str, Any] = dict(kwargs)
        try:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("tool call: %s(%r)", name, arguments)
            await _emit_trace_frame(
                emit_frame,
                "tool_call",
                ToolCallFrame(tool_name=name, arguments=arguments),
            )

            ok = True
            try:
                raw = func(**kwargs)
                if inspect.isawaitable(raw):
                    raw = await raw
                result = raw if isinstance(raw, str) else str(raw)
            except Exception as exc:
                # The tool broke its own "never raises" contract. Converted here,
                # because an exception escaping into ``chat_with_tools`` is
                # re-raised as ``RuntimeError`` and aborts the WHOLE turn.
                ok = False
                result = _TOOL_FAILED_MESSAGE.format(name=name, error=exc)
                logger.warning("tool %s raised", name, exc_info=True)

            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(
                    "tool result: %s -> ok=%s %s",
                    name,
                    ok,
                    result[:_DEBUG_RESULT_CHARS],
                )
            await _emit_trace_frame(
                emit_frame,
                "tool_result",
                ToolResultFrame(tool_name=name, result=result, ok=ok),
            )
            trace.append(
                ToolTraceEntry(
                    tool_name=name, arguments=arguments, result=result, ok=ok
                )
            )
            return result
        except Exception as exc:
            # The backstop. Nothing above is expected to reach here — every known
            # failure is already converted — but "a tool never raises" is absolute,
            # so an unexpected one still leaves as a string.
            logger.warning(
                "the tool trace wrapper failed for %s", name, exc_info=True
            )
            return _TOOL_FAILED_MESSAGE.format(name=name, error=exc)

    return traced_tool


async def compose_turn_system_prompt(context: TurnContext) -> str:
    """Compose one turn's whole system prompt — the four layers, in order.

    The turn's side of :func:`~app.services.prompt_composition.compose_system_prompt`:
    that module is a **pure** function over four already-loaded strings, so
    somebody has to load them. This is that somebody, lifted out of
    :func:`run_turn` (015 step 013) so the composition is reachable — and
    testable — without opening a stream or calling ``chat_with_tools``.

    The four layers, in the composer's fixed order:

    1. ``base`` — :data:`~app.services.prompt_composition.BASE_SYSTEM_PROMPT`,
       always populated;
    2. ``mode`` — :func:`~app.services.assistant_runtime.mode_system_prompt` over
       ``context.subject.mode_key`` (013 step 007; ``None`` for every subject
       outside the three codex kinds and the two chapter states);
    3. ``author`` — the ``BookAuthorPrompt`` row for
       ``(chat.book_id, chat.author_id)``, read straight from
       :mod:`app.db.book_author_prompts` (021 step 004). ``Book.system_prompt``
       is **not** read: superseded and dormant;
    4. ``chapter`` — **015 step 013, the new layer**: when, and only when, the
       turn's resolved subject carries a chapter
       (``context.subject.chapter is not None``), the ``ChapterAuthorPrompt``
       row for ``(chapter.id, chat.author_id)``, read straight from
       :mod:`app.db.chapter_author_prompts`. ``Chapter.system_prompt`` is
       **not** read: superseded and dormant (014's D1).

    **The identity is the chat's own author for both prompt layers** — layer 4
    reuses layer 3's shape exactly: same identity, same direct ``db/`` read
    (``services → db`` is the sanctioned edge), and **no**
    :class:`~app.services.authz.BookAccess` is built for it. The reason is the
    one ``assistant-runtime.md`` states about layer 3: the turn is already
    scoped to the chat's author by ``services/chats.py``'s ownership guard, so a
    second access resolution would re-derive an identity that cannot differ.
    Another member's row for the same chapter is therefore never read — the
    book's owner included.

    The chapter layer is **not gated by the chapter's state**: a prompt is the
    author's instruction to their own assistant, not chapter content, so it
    applies to a ``planned`` and a ``closed`` chapter exactly as to an ``open``
    one.

    A missing row, and a stored prompt that is empty or blank, both contribute
    **nothing** — no section, no label, no separator, no blank block. That needs
    no code here: it is the composer's own skip rule for every layer.

    ``services/prompt_composition.py`` is **not** touched — its fourth parameter
    has been there since 011 and this only fills it.
    """
    chat = context.chat

    mode_prompt = await assistant_runtime.mode_system_prompt(context.subject.mode_key)

    author_prompt = await book_author_prompts.get_by_book_and_user(
        chat.book_id, chat.author_id
    )

    # Layer 4 — the caller's own chapter prompt, and only when the turn's
    # resolved subject IS a chapter. Same identity as layer 3 (the chat's own
    # author), same direct ``services → db`` read, no ``BookAccess``.
    chapter_prompt = None
    if context.subject.chapter is not None:
        chapter_prompt = await chapter_author_prompts.get_by_chapter_and_user(
            context.subject.chapter.id, chat.author_id
        )

    return prompt_composition.compose_system_prompt(
        base=prompt_composition.BASE_SYSTEM_PROMPT,
        mode=mode_prompt,
        author=author_prompt.system_prompt if author_prompt is not None else None,
        chapter=(
            chapter_prompt.system_prompt if chapter_prompt is not None else None
        ),
    )


async def _finalize_close_turn_if_needed(
    context: TurnContext, tool_context: tools_service.ToolContext
) -> None:
    """Run 016's deterministic post-turn step, when this turn was a close run.

    Called by :func:`run_turn` **once**, at the turn's natural completion —
    success **or** an ``error`` frame — and **before** the terminal frame is
    yielded, which is what makes a client cancellation skip it: a disconnect
    while the stream is still open never reaches this line, and the author's
    recovery is the ``POST …/close/cancel`` endpoint (``016/context.md``).

    A **close-chapter turn** is one whose already-resolved subject is a chapter in
    ``ChapterState.closing`` — exactly the condition
    ``assistant_runtime._CHAPTER_STATE_MODES`` maps to the ``close-chapter`` mode,
    read off the subject this turn was prepared with rather than re-derived.

    Two guards, and neither is a new rule:

    - **no chapter subject, or one that is not ``closing``** → this is an ordinary
      turn and nothing is finalized;
    - **a caller who does not hold** ``Capability.set_chapter_state`` → skipped.
      Mode determination is per-subject, not per-role, so a co-author's own chat
      also resolves to ``close-chapter`` while somebody else's chapter is
      ``closing``; finalizing there would discard the owner's in-flight run. It is
      the same capability ``services/close_tools.py``'s fourth refusal rule
      applies to that turn's tool calls, asked the same way.

    It never lets a finalize failure surface as a turn failure: the turn is over,
    its frames are decided, and there is no channel left to speak on — so an
    unexpected exception is logged and swallowed.
    """
    subject = context.subject
    chapter = subject.chapter
    if chapter is None or chapter.state != ChapterState.closing:
        return None

    access = context.access
    if access is None:
        return None
    try:
        authz.require(access, authz.Capability.set_chapter_state)
    except authz.BookAuthorizationError:
        return None

    try:
        # The SAME ``ToolContext`` instance the turn's tools were bound to, so the
        # held ``active_notes_proposal`` — which was never persisted (decision D7)
        # — is the one finalize reads.
        await chapters_service.finalize_close_turn(
            access, str(chapter.id), tool_context
        )
    except Exception:
        logger.warning(
            "finalize_close_turn failed for chapter %s", chapter.id, exc_info=True
        )
    return None


async def prepare_turn(
    access: authz.BookAccess,
    chat_id: str,
    request: TurnRequest | None = None,
) -> TurnContext:
    """Run the **pre-stream refusals** and return a :class:`TurnContext`.

    Raised **before anything is persisted and before the first frame**, so the
    route maps them to ordinary JSON HTTP errors (DoD-8 / DoD-10):

    - the chat is missing or not the caller's → :class:`~app.services.chats.ChatError`
      ``chat_not_found`` (→ 404, never 403 — reuses step 001's ownership rule);
    - no model pair set on the chat → ``ChatError`` ``invalid_model_pair`` (→ 400);
    - the server is missing or inactive → ``ChatError`` ``unknown_or_inactive_server``
      (→ 400);
    - the key's env var is unset →
      :class:`~app.services.llm_servers.LlmServerError` ``env_not_set`` (→ 400,
      UC-054 exception flow).

    ``request`` is the parsed turn body (013 step 007). Its three subject fields
    are resolved here — the phase that exists precisely to settle everything
    before the first frame — through
    :func:`app.services.assistant_runtime.resolve_subject`, and the result rides
    on the returned context. ``None`` (or a body with no subject fields) resolves
    to :data:`~app.services.assistant_runtime.NO_SUBJECT`: no subject, no mode,
    exactly the turn ``011.chat-panel`` shipped. Resolving a subject **never**
    refuses a turn — an unresolvable or cross-book subject is simply no subject
    (US-085.AC-1), so this adds no failure mode to the pre-stream contract above.

    The request's ``selection_text`` is carried onto the returned
    :class:`TurnContext` (and from there onto :func:`run_turn`'s
    :class:`~app.services.tools.ToolContext`, 015 step 009). It is turn context
    the client supplied and nothing more: it is never validated, never resolved
    against a row and never persisted (``015/context.md`` → D5).

    """
    chat = await chats_service._resolve_owned_chat(
        access, chats_service._parse_chat_id(chat_id)
    )
    if chat.llm_server_id is None or chat.model_name is None:
        raise chats_service.ChatError(
            chats_service.ChatErrorReason.invalid_model_pair,
            "This chat has no model configured.",
        )
    server = await llm_servers_db.get_by_id(chat.llm_server_id)
    if server is None or not server.is_active:
        raise chats_service.ChatError(
            chats_service.ChatErrorReason.unknown_or_inactive_server,
            "The chat's server is unknown or inactive.",
        )
    # Resolve the ``$ENV`` key ref here (the ``probe_models`` precedent) so an unset
    # env var surfaces as ``LlmServerError(env_not_set)`` → 400 before any frame.
    resolved_key = secrets.resolve_env_ref(server.api_key)
    subject = await assistant_runtime.resolve_subject(
        access,
        subject_kind=request.subject_kind if request is not None else None,
        subject_id=request.subject_id if request is not None else None,
        codex_kind=request.codex_kind if request is not None else None,
    )
    return TurnContext(
        chat=chat,
        server=server,
        resolved_key=resolved_key,
        subject=subject,
        # Carried, not re-resolved: the caller's role and the book's
        # collaboration mode are what the shared-canvas write gate reads (013
        # step 010), and this is the one place they are already in hand.
        access=access,
        # The author's current selection, straight off the request (015 step
        # 009). This record is the only carrier from here to ``run_turn``'s
        # ``ToolContext``; it is never stored.
        selection_text=request.selection_text if request is not None else None,
    )


async def run_turn(
    context: TurnContext, prompt: str | None
) -> AsyncGenerator[TurnFrame, None]:
    """Run one assistant turn over ``context``, yielding :class:`TurnFrame`s.

    Steps (``003.streaming-turn-endpoint.md`` → Interface intent):

    1. when ``prompt`` is present, **persist the user message first** — allocated
       position, role ``"user"`` — before any assistant work, so a failure leaves
       it stored exactly once and a retry (``prompt is None``) re-runs over the
       stored history without duplicating it;
    2. compose the system prompt through :func:`compose_turn_system_prompt` —
       base + the resolved subject's **mode** prompt (013 step 007) + the
       **author** layer + the **chapter** layer (015 step 013). Both prompt
       layers belong to *this chat's own author* (``chat.author_id``) and are
       read straight from their ``db/`` modules; ``Book.system_prompt`` and
       ``Chapter.system_prompt`` are **not** read — both are superseded and
       dormant;
    3. build the tool definitions + callable map from
       :func:`~app.services.assistant_runtime.resolve_turn_tools` — the mode's
       ``mode_tool`` allowlist (or
       :data:`~app.services.assistant_runtime.BASE_TOOL_NAMES` with no mode; 013
       step 007, ``context.md`` decision 6) **plus** the mode's synthetic
       sub-agent delegation tools (013 step 008), as one combined list bound in a
       single ``build_tool_bindings`` call — together with the turn's
       :class:`~app.services.tools.ToolContext`, which every **bound** tool is
       closed over (013 step 009);
    4. construct the model-bound client via
       :func:`app.services.llm_servers.create_model_client`, entered as an
       ``async with`` so its session closes on every path;
    5. call ``chat_with_tools(..., stream=True, on_delta=...)`` with
       :data:`MAX_LOOPS` and :func:`build_sampling_options`, feeding every delta
       through a :class:`ThinkSplitter` and emitting ``thinking`` / ``delta``
       frames;
    6. on success persist the assistant message — **content assembled from the
       streamed content deltas, ``reasoning`` from the thinking deltas**, not from
       the call's return value — then emit a single ``done`` carrying its DTO;
    7. on failure (:data:`_TURN_FAILURE_EXCEPTIONS`, or an empty result) emit a
       single ``error`` frame, leaving the user message stored and writing no
       assistant message.

    """
    chat = context.chat
    server = context.server
    now = datetime.now(timezone.utc)

    # 1. Persist the user message FIRST, so a failure leaves it stored exactly once
    #    and a retry (``prompt is None``) re-runs over the stored history without
    #    duplicating it.
    if prompt is not None:
        position = await chat_messages.next_position(chat.id)
        await chat_messages.create(
            ChatMessage(
                chat_id=chat.id,
                role="user",
                content=prompt,
                reasoning=None,
                position=position,
                created_at=now,
            )
        )

    # 1b. The subject's FEAT-020 mode also gates the turn's tools, so its key is
    #     read here for step 3 (013 step 007). ``context.subject`` was resolved
    #     before the stream opened; ``mode_key`` is ``None`` for every subject
    #     outside the three codex kinds and the two chapter states — and for a
    #     turn that carried no subject at all.
    mode_key = context.subject.mode_key

    # 2. Compose the system prompt — all four layers, loaded and composed by
    #    :func:`compose_turn_system_prompt` (015 step 013), which is where the
    #    base / mode / author reads now live and where the chapter layer joins
    #    them.
    system = await compose_turn_system_prompt(context)

    # 3. Real mode-tool gating (013 step 007) plus the mode's synthetic sub-agent
    #    delegation tools (013 step 008), resolved in ONE place and bound in ONE
    #    call: the ``llm`` client pre-flights every ``tools_definitions`` name
    #    against the ``tools`` map, so real and synthetic tools must be built
    #    together. ``parent_turn`` is what a sub-agent with no model assignment
    #    of its own inherits (US-113.AC-6) — the parent's server, its already
    #    ``$ENV``-resolved key and its model.
    #    ``tool_context`` is what a BOUND tool is closed over (013 step 009):
    #    the ``llm`` client dispatches ``func(**kwargs)`` with no per-request
    #    context argument, so everything a tool needs from the turn — the book
    #    (the codex tools' hard filter), the caller's access, the content-pane
    #    subject and the way to put a frame on this turn's stream (013 step 010)
    #    — has to be supplied at binding time.
    #
    #    The frame queue is created HERE, before the tools are bound, because
    #    ``emit_frame`` closes over it: a tool's ``canvas`` frame must travel the
    #    SAME put-onto-the-queue path ``thinking`` / ``delta`` already use, so it
    #    interleaves naturally with them and no second transport exists. The tool
    #    runs inside ``drive()`` below — the very task that pumps those frames.
    queue: asyncio.Queue[object] = asyncio.Queue()

    async def emit_frame(event: str, data: BaseModel) -> None:
        await queue.put(TurnFrame(event=event, data=data))

    #
    #    ``selection_text`` joins them (015 step 009): the author's current
    #    selection is client-supplied turn context carried through from
    #    ``prepare_turn``, and a selection-writing tool reads it off the bound
    #    context rather than re-deriving anything.
    tool_context = tools_service.ToolContext(
        book_id=chat.book_id,
        access=context.access,
        subject=context.subject,
        emit_frame=emit_frame,
        selection_text=context.selection_text,
    )
    parent_turn = subagent_delegation.ParentTurn(
        server=server,
        resolved_key=context.resolved_key,
        model=chat.model_name or "",
        # A delegated sub-agent binds its own tools; without the turn's context
        # a bound one would be silently dropped from its nested call (013 step
        # 009's flagged consequence, resolved here).
        tool_context=tool_context,
    )
    tool_defs, tool_map = tools_service.build_tool_bindings(
        await assistant_runtime.resolve_turn_tools(mode_key, parent_turn),
        tool_context,
    )

    # 3b. The tool-call trace (024, D1). ``chat_with_tools`` exposes no before /
    #     after hook, but the app supplies the callables it dispatches — so one
    #     generic wrapper around each bound callable sees every call, announces it
    #     on the SAME queue the other frames ride, and records it for persistence.
    #     ``tools=`` below receives this wrapped map; every OTHER argument to
    #     ``chat_with_tools`` is unchanged, and the library itself is untouched.
    tool_trace: list[ToolTraceEntry] = []
    traced_tool_map: dict[str, Callable[..., object]] = {
        tool_name: _wrap_tool_with_trace(tool_name, func, emit_frame, tool_trace)
        for tool_name, func in tool_map.items()
    }

    # 4. The message history to replay (includes the just-persisted user message).
    history = await chat_messages.list_by_chat_ordered(chat.id)
    messages: list[dict[str, str]] = [
        {"role": m.role, "content": m.content} for m in history
    ]

    sampling = chats_service._parse_sampling(chat.sampling_params)
    options = build_sampling_options(sampling, server.backend_type)

    # 4b. The context dump (024, D5) — everything actually put in front of the
    #     model this turn: the composed system prompt, the tools it may call and
    #     the replayed history. GATED ON LOG LEVEL: prompt text and message bodies
    #     are the author's book, so a default-level run must never write them to
    #     the log. The per-call tool arguments and results are dumped from
    #     :func:`_wrap_tool_with_trace`, under the same gate.
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            "chat turn context — chat=%s mode=%s tools=%s\n"
            "--- system prompt ---\n%s\n"
            "--- history (%d messages) ---\n%s",
            chat.id,
            mode_key,
            sorted(traced_tool_map),
            system,
            len(messages),
            "\n".join(f"[{m['role']}] {m['content']}" for m in messages),
        )

    # The splitter routes each raw delta onto the thinking / content channels; the
    # persisted message is assembled from these accumulators — NOT from
    # ``chat_with_tools``'s return value, which is only the final round's content
    # while ``on_delta`` sees every round and is the only place thinking text
    # exists (``003.context.md`` → "on_delta vs the return value").
    splitter = ThinkSplitter()
    content_parts: list[str] = []
    thinking_parts: list[str] = []
    failure: list[Exception] = []

    async def emit(channel: Channel, text: str) -> None:
        if channel == CHANNEL_THINKING:
            thinking_parts.append(text)
            await queue.put(TurnFrame(event="thinking", data=ThinkingFrame(text=text)))
        else:
            content_parts.append(text)
            await queue.put(TurnFrame(event="delta", data=DeltaFrame(text=text)))

    async def on_delta(text: str) -> None:
        for channel, seg in splitter.feed(text):
            await emit(channel, seg)

    async def drive() -> None:
        # The client is entered as an ``async with`` so its aiohttp session closes
        # on EVERY path, including failure (``context.md`` → the client contract).
        try:
            async with llm_servers_service.create_model_client(
                server, context.resolved_key, chat.model_name or ""
            ) as client:
                await client.chat_with_tools(
                    messages,
                    tools_definitions=tool_defs,
                    # 024: the ONLY changed argument — the same map, each callable
                    # wrapped so its call is announced, reported and recorded.
                    tools=traced_tool_map,
                    system=system,
                    max_loops=MAX_LOOPS,
                    options=options,
                    stream=True,
                    on_delta=on_delta,
                )
            for channel, seg in splitter.flush():
                await emit(channel, seg)
        except _TURN_FAILURE_EXCEPTIONS as exc:
            failure.append(exc)
        finally:
            await queue.put(_STREAM_DONE)

    task = asyncio.ensure_future(drive())
    while True:
        item = await queue.get()
        if item is _STREAM_DONE:
            break
        assert isinstance(item, TurnFrame)
        yield item
    await task

    # 7. Failure — one ``error`` frame, no assistant message, user message intact.
    if failure:
        logger.warning("chat turn failed: %s", failure[0])
        # 016: a close run that FAILED still ended naturally, so the server still
        # decides its outcome (which, with the artifacts incomplete, is the wipe
        # branch). Run BEFORE the terminal frame is yielded: a generator suspended
        # at a `yield` may never be resumed if the client has gone.
        await _finalize_close_turn_if_needed(context, tool_context)
        yield TurnFrame(event="error", data=ErrorFrame(message=_ERROR_MESSAGE))
        return

    content = "".join(content_parts)
    # An empty result has no dedicated exception; UC-056 ("the LLM returns
    # nothing") treats it as a failure too.
    if not content:
        logger.warning("chat turn produced no content")
        await _finalize_close_turn_if_needed(context, tool_context)
        yield TurnFrame(event="error", data=ErrorFrame(message=_ERROR_MESSAGE))
        return

    # 6. Success — persist ONE assistant message (content from the content deltas,
    #    reasoning from the thinking deltas) and emit the terminal ``done`` DTO.
    reasoning = "".join(thinking_parts) or None
    # 024: the trace assembled by the wrappers, written through its typed gate —
    # ``None`` when NO tool ran, exactly as ``reasoning`` is ``None`` when nothing
    # was thought. It is persisted for the same reason ``reasoning`` is: the client
    # discards its live buffers and re-reads the message once the turn ends, so a
    # live-only trace would erase itself at completion.
    trace_column = ToolTrace(entries=tool_trace).to_column() if tool_trace else None
    position = await chat_messages.next_position(chat.id)
    assistant = await chat_messages.create(
        ChatMessage(
            chat_id=chat.id,
            role="assistant",
            content=content,
            reasoning=reasoning,
            position=position,
            created_at=datetime.now(timezone.utc),
            tool_trace=trace_column,
        )
    )
    # 016: the deterministic post-turn step, run ONCE at natural completion and
    # BEFORE the terminal frame — so the chapter's outcome is already decided by
    # the time the client sees `done` and re-reads it.
    await _finalize_close_turn_if_needed(context, tool_context)
    yield TurnFrame(
        event="done",
        data=DoneFrame(message=chats_service._to_message_response(assistant)),
    )
