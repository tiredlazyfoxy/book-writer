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
"""

import asyncio
import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

import aiohttp
from llm import LLMError
from pydantic import BaseModel

from app.db import books, chat_messages
from app.db import llm_servers as llm_servers_db
from app.models.chat import Chat, ChatMessage
from app.models.llm_server import LlmServer
from app.models.schemas.chats import (
    ChatSamplingParams,
    DeltaFrame,
    DoneFrame,
    ErrorFrame,
    ThinkingFrame,
)
from app.services import authz
from app.services import chats as chats_service
from app.services import llm_servers as llm_servers_service
from app.services import prompt_composition
from app.services import secrets
from app.services import tools as tools_service

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
    """

    chat: Chat
    server: LlmServer
    resolved_key: str | None


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


async def prepare_turn(access: authz.BookAccess, chat_id: str) -> TurnContext:
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
    return TurnContext(chat=chat, server=server, resolved_key=resolved_key)


async def run_turn(
    context: TurnContext, prompt: str | None
) -> AsyncGenerator[TurnFrame, None]:
    """Run one assistant turn over ``context``, yielding :class:`TurnFrame`s.

    Steps (``003.streaming-turn-endpoint.md`` → Interface intent):

    1. when ``prompt`` is present, **persist the user message first** — allocated
       position, role ``"user"`` — before any assistant work, so a failure leaves
       it stored exactly once and a retry (``prompt is None``) re-runs over the
       stored history without duplicating it;
    2. compose the system prompt from :data:`~app.services.prompt_composition.BASE_SYSTEM_PROMPT`
       and the book's ``system_prompt`` (mode and chapter layers null this feature);
    3. build the tool definitions + callable map from the whole ``TOOL_REGISTRY``
       (null mode);
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

    # 2. Compose the system prompt (base + book; mode/chapter null this feature).
    book = await books.get_by_id(chat.book_id)
    system = prompt_composition.compose_system_prompt(
        base=prompt_composition.BASE_SYSTEM_PROMPT,
        book=book.system_prompt if book is not None else None,
    )

    # 3. The whole registry under null mode (mode-tool gating is deferred to 013).
    tool_defs, tool_map = tools_service.build_tool_bindings(
        tools_service.resolve_tools(None)
    )

    # 4. The message history to replay (includes the just-persisted user message).
    history = await chat_messages.list_by_chat_ordered(chat.id)
    messages: list[dict[str, str]] = [
        {"role": m.role, "content": m.content} for m in history
    ]

    sampling = chats_service._parse_sampling(chat.sampling_params)
    options = build_sampling_options(sampling, server.backend_type)

    # The splitter routes each raw delta onto the thinking / content channels; the
    # persisted message is assembled from these accumulators — NOT from
    # ``chat_with_tools``'s return value, which is only the final round's content
    # while ``on_delta`` sees every round and is the only place thinking text
    # exists (``003.context.md`` → "on_delta vs the return value").
    splitter = ThinkSplitter()
    content_parts: list[str] = []
    thinking_parts: list[str] = []
    queue: asyncio.Queue[object] = asyncio.Queue()
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
                    tools=tool_map,
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
        yield TurnFrame(event="error", data=ErrorFrame(message=_ERROR_MESSAGE))
        return

    content = "".join(content_parts)
    # An empty result has no dedicated exception; UC-056 ("the LLM returns
    # nothing") treats it as a failure too.
    if not content:
        logger.warning("chat turn produced no content")
        yield TurnFrame(event="error", data=ErrorFrame(message=_ERROR_MESSAGE))
        return

    # 6. Success — persist ONE assistant message (content from the content deltas,
    #    reasoning from the thinking deltas) and emit the terminal ``done`` DTO.
    reasoning = "".join(thinking_parts) or None
    position = await chat_messages.next_position(chat.id)
    assistant = await chat_messages.create(
        ChatMessage(
            chat_id=chat.id,
            role="assistant",
            content=content,
            reasoning=reasoning,
            position=position,
            created_at=datetime.now(timezone.utc),
        )
    )
    yield TurnFrame(
        event="done",
        data=DoneFrame(message=chats_service._to_message_response(assistant)),
    )
