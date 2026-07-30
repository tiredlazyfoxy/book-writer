"""Import/export serialization — gzipped JSONL per table inside a zip archive.

This is the format/serialization layer (services). It owns ``TABLE_REGISTRY``
(the ordered, FK-respecting list of per-table codec entries) and streams rows
through gzip; all DB access is delegated to ``db.import_export_queries``, which
manages its own sessions. See ``docs/architecture/backend.md``.

Adding a model = add its ``to_dict``/``from_dict`` codec pair plus one ordered
``TABLE_REGISTRY`` tuple, in FK dependency order. ``users`` is the first
persistent model (step 003).

Skeleton (step 004): mechanism signatures frozen; bodies UNIMPLEMENTED.
Skeleton (step 003): ``User`` codec signatures frozen; codec bodies UNIMPLEMENTED.
"""

import gzip
import io
import json
import logging
import zipfile
from collections.abc import Callable
from datetime import datetime

from sqlmodel import SQLModel

from app.db import engine, import_export_queries
from app.models.assistant_mode import AssistantMode
from app.models.book import Book, BookState, CollaborationMode, Visibility
from app.models.book_author_prompt import BookAuthorPrompt
from app.models.book_member import BookMember, MemberRole
from app.models.chapter import Chapter, ChapterState, SummaryStatus
from app.models.chapter_author_prompt import ChapterAuthorPrompt
from app.models.chapter_change import ChangeStatus, ChapterChange, PlacementKind
from app.models.chapter_notes import ChapterNoteChangeset, NoteStatus
from app.models.chapter_text_revision import ChapterTextRevision
from app.models.chat import Chat, ChatMessage
from app.models.codex_entry import CodexEntry, CodexKind
from app.models.codex_entry_version import CodexEntryVersion
from app.models.flag import Flag, FlagOrigin, FlagStatus
from app.models.llm_server import LlmServer
from app.models.mode_subagent import ModeSubagent
from app.models.mode_tool import ModeTool
from app.models.sub_agent import SubAgent
from app.models.subagent_tool import SubagentTool
from app.models.user import User, UserRole

logger = logging.getLogger(__name__)

# One registry entry per persistent table, in FK dependency (import) order:
#   (zip_filename, model_class, to_dict_fn, from_dict_fn)
RegistryEntry = tuple[
    str,
    type[SQLModel],
    Callable[[SQLModel], dict[str, object]],
    Callable[[dict[str, object]], SQLModel],
]

def _user_to_dict(user: User) -> dict[str, object]:
    """Serialize a ``User`` row to a JSON-safe dict for export.

    Enum via ``.value``, datetimes via ``.isoformat()``, nullable fields emitted
    as ``None``. Includes credentials (``pwdhash``, ``jwt_signing_key``) so
    restored accounts can authenticate (security consideration flagged in
    ``outcome.md``).
    """
    return {
        "id": str(user.id),
        "username": user.username,
        "pwdhash": user.pwdhash,
        "role": user.role.value,
        "jwt_signing_key": user.jwt_signing_key,
        "last_login": user.last_login.isoformat() if user.last_login else None,
        "last_key_update": (
            user.last_key_update.isoformat() if user.last_key_update else None
        ),
    }


def _dict_to_user(data: dict[str, object]) -> User:
    """Restore a ``User`` row from an exported dict (inverse of ``_user_to_dict``).

    Role via ``UserRole(...)``, datetimes parsed from isoformat, nullable fields
    read with a ``.get``-style lookup. Explicit ``id`` is preserved so the UPSERT
    is idempotent on re-import (decision 6). ``id`` is accepted as **either** a
    JSON string (current snowflake serialization) **or** a legacy JSON number
    (pre-snowflake archives), parsed to ``int`` in both cases.
    """
    last_login = data.get("last_login")
    last_key_update = data.get("last_key_update")
    raw_id = data.get("id")
    return User(
        id=int(raw_id) if raw_id is not None else None,
        username=data["username"],
        pwdhash=data.get("pwdhash"),
        role=UserRole(data["role"]),
        jwt_signing_key=data.get("jwt_signing_key"),
        last_login=datetime.fromisoformat(last_login) if last_login else None,
        last_key_update=(
            datetime.fromisoformat(last_key_update) if last_key_update else None
        ),
    )


def _llm_server_to_dict(server: LlmServer) -> dict[str, object]:
    """Serialize an ``LlmServer`` row to a JSON-safe dict for export.

    ``enabled_models`` is kept as its stored JSON string; datetimes via
    ``.isoformat()`` inline; nullable fields emitted as ``None``.

    ``api_key`` is **redacted** on export: a ``$ENV_VAR`` token is a *pointer*,
    not a secret, so it is preserved verbatim; ``None`` stays ``None``; a raw
    literal key (anything not ``$``-prefixed) is replaced with ``None`` so no
    cleartext secret lands in the export file. (Reuses the ``$``-prefix
    distinction that ``services/secrets.py`` relies on, inlined here to avoid
    importing the resolver into the codec.) This supersedes the earlier
    verbatim-export behaviour (step-001 DoD-5 / D6).
    """
    api_key = server.api_key
    exported_api_key = api_key if (api_key is None or api_key.startswith("$")) else None
    return {
        "id": str(server.id),
        "name": server.name,
        "backend_type": server.backend_type,
        "base_url": server.base_url,
        "api_key": exported_api_key,
        "enabled_models": server.enabled_models,
        "is_active": server.is_active,
        "is_embedding": server.is_embedding,
        "embedding_model": server.embedding_model,
        "created_at": server.created_at.isoformat() if server.created_at else None,
        "modified_at": server.modified_at.isoformat() if server.modified_at else None,
    }


def _dict_to_llm_server(data: dict[str, object]) -> LlmServer:
    """Restore an ``LlmServer`` row from an exported dict (inverse of
    ``_llm_server_to_dict``; D6).

    ``is_active`` / ``is_embedding`` / ``enabled_models`` are read with
    ``.get(...)`` defaults; datetimes parsed from isoformat; explicit ``id``
    preserved so the UPSERT stays idempotent on re-import.

    Skeleton (step 001): signature frozen; body UNIMPLEMENTED.
    """
    created_at = data.get("created_at")
    modified_at = data.get("modified_at")
    raw_id = data.get("id")
    return LlmServer(
        id=int(raw_id) if raw_id is not None else None,
        name=data["name"],
        backend_type=data["backend_type"],
        base_url=data["base_url"],
        api_key=data.get("api_key"),
        enabled_models=data.get("enabled_models", "[]"),
        is_active=data.get("is_active", True),
        is_embedding=data.get("is_embedding", False),
        embedding_model=data.get("embedding_model"),
        created_at=datetime.fromisoformat(created_at) if created_at else None,
        modified_at=datetime.fromisoformat(modified_at) if modified_at else None,
    )


def _assistant_mode_to_dict(mode: AssistantMode) -> dict[str, object]:
    """Serialize an ``AssistantMode`` row to a JSON-safe dict for export.

    The ``key`` natural primary key is emitted **verbatim** — never coerced
    through ``str(int(...))``. Datetimes via ``.isoformat()``; nullable fields
    emitted as ``None``.

    Skeleton (008 step 001): signature frozen; body UNIMPLEMENTED.
    """
    return {
        "key": mode.key,
        "system_prompt": mode.system_prompt,
        "created_at": mode.created_at.isoformat() if mode.created_at else None,
        "modified_at": mode.modified_at.isoformat() if mode.modified_at else None,
    }


def _dict_to_assistant_mode(data: dict[str, object]) -> AssistantMode:
    """Restore an ``AssistantMode`` row from an exported dict (inverse of
    ``_assistant_mode_to_dict``).

    ``key`` is parsed **verbatim** (``data["key"]``) — never through ``int()``.
    Datetimes parsed from isoformat; nullable fields read with ``.get(...)``.

    Skeleton (008 step 001): signature frozen; body UNIMPLEMENTED.
    """
    created_at = data.get("created_at")
    modified_at = data.get("modified_at")
    return AssistantMode(
        key=data["key"],
        system_prompt=data.get("system_prompt"),
        created_at=datetime.fromisoformat(created_at) if created_at else None,
        modified_at=datetime.fromisoformat(modified_at) if modified_at else None,
    )


def _sub_agent_to_dict(sub_agent: SubAgent) -> dict[str, object]:
    """Serialize a ``SubAgent`` row to a JSON-safe dict for export.

    ``id`` emitted as ``str(...)`` (snowflake); ``disabled`` as bool; nullable
    ``llm_server_id`` / ``model_name`` passed through; datetimes via
    ``.isoformat()``.

    Skeleton (008 step 001): signature frozen; body UNIMPLEMENTED.
    """
    return {
        "id": str(sub_agent.id),
        "name": sub_agent.name,
        "system_prompt": sub_agent.system_prompt,
        "disabled": sub_agent.disabled,
        "llm_server_id": sub_agent.llm_server_id,
        "model_name": sub_agent.model_name,
        "created_at": sub_agent.created_at.isoformat() if sub_agent.created_at else None,
        "modified_at": (
            sub_agent.modified_at.isoformat() if sub_agent.modified_at else None
        ),
    }


def _dict_to_sub_agent(data: dict[str, object]) -> SubAgent:
    """Restore a ``SubAgent`` row from an exported dict (inverse of
    ``_sub_agent_to_dict``).

    ``id`` parsed as string-or-legacy-number to ``int``; ``disabled`` read with
    a ``.get(...)`` default; nullable ``llm_server_id`` / ``model_name`` read
    with ``.get(...)``; datetimes parsed from isoformat.

    Skeleton (008 step 001): signature frozen; body UNIMPLEMENTED.
    """
    created_at = data.get("created_at")
    modified_at = data.get("modified_at")
    raw_id = data.get("id")
    return SubAgent(
        id=int(raw_id) if raw_id is not None else None,
        name=data["name"],
        system_prompt=data["system_prompt"],
        disabled=data.get("disabled", False),
        llm_server_id=data.get("llm_server_id"),
        model_name=data.get("model_name"),
        created_at=datetime.fromisoformat(created_at) if created_at else None,
        modified_at=datetime.fromisoformat(modified_at) if modified_at else None,
    )


def _mode_tool_to_dict(mode_tool: ModeTool) -> dict[str, object]:
    """Serialize a ``ModeTool`` row to a JSON-safe dict for export.

    ``id`` emitted as ``str(...)`` (snowflake); ``mode_key`` emitted
    **verbatim** as a string (never coerced through ``int()``); ``tool_name``
    passed through. No timestamps on this link table.

    Skeleton (008 step 002): signature frozen; body UNIMPLEMENTED.
    """
    return {
        "id": str(mode_tool.id),
        "mode_key": mode_tool.mode_key,
        "tool_name": mode_tool.tool_name,
    }


def _dict_to_mode_tool(data: dict[str, object]) -> ModeTool:
    """Restore a ``ModeTool`` row from an exported dict (inverse of
    ``_mode_tool_to_dict``).

    ``id`` parsed as string-or-legacy-number to ``int``; ``mode_key`` read
    **verbatim** as a string; ``tool_name`` passed through.

    Skeleton (008 step 002): signature frozen; body UNIMPLEMENTED.
    """
    raw_id = data.get("id")
    return ModeTool(
        id=int(raw_id) if raw_id is not None else None,
        mode_key=data["mode_key"],
        tool_name=data["tool_name"],
    )


def _subagent_tool_to_dict(subagent_tool: SubagentTool) -> dict[str, object]:
    """Serialize a ``SubagentTool`` row to a JSON-safe dict for export.

    ``id`` and ``sub_agent_id`` emitted as ``str(...)``; ``tool_name`` passed
    through. No timestamps on this link table.

    Skeleton (008 step 002): signature frozen; body UNIMPLEMENTED.
    """
    return {
        "id": str(subagent_tool.id),
        "sub_agent_id": str(subagent_tool.sub_agent_id),
        "tool_name": subagent_tool.tool_name,
    }


def _dict_to_subagent_tool(data: dict[str, object]) -> SubagentTool:
    """Restore a ``SubagentTool`` row from an exported dict (inverse of
    ``_subagent_tool_to_dict``).

    ``id`` and ``sub_agent_id`` parsed as string-or-legacy-number to ``int``;
    ``tool_name`` passed through.

    Skeleton (008 step 002): signature frozen; body UNIMPLEMENTED.
    """
    raw_id = data.get("id")
    raw_sub_agent_id = data.get("sub_agent_id")
    return SubagentTool(
        id=int(raw_id) if raw_id is not None else None,
        sub_agent_id=int(raw_sub_agent_id) if raw_sub_agent_id is not None else None,
        tool_name=data["tool_name"],
    )


def _mode_subagent_to_dict(mode_subagent: ModeSubagent) -> dict[str, object]:
    """Serialize a ``ModeSubagent`` row to a JSON-safe dict for export.

    ``id`` and ``sub_agent_id`` emitted as ``str(...)``; ``mode_key`` emitted
    **verbatim** as a string (never coerced through ``int()``). No timestamps
    on this link table.

    Skeleton (008 step 002): signature frozen; body UNIMPLEMENTED.
    """
    return {
        "id": str(mode_subagent.id),
        "mode_key": mode_subagent.mode_key,
        "sub_agent_id": str(mode_subagent.sub_agent_id),
    }


def _dict_to_mode_subagent(data: dict[str, object]) -> ModeSubagent:
    """Restore a ``ModeSubagent`` row from an exported dict (inverse of
    ``_mode_subagent_to_dict``).

    ``id`` and ``sub_agent_id`` parsed as string-or-legacy-number to ``int``;
    ``mode_key`` read **verbatim** as a string.

    Skeleton (008 step 002): signature frozen; body UNIMPLEMENTED.
    """
    raw_id = data.get("id")
    raw_sub_agent_id = data.get("sub_agent_id")
    return ModeSubagent(
        id=int(raw_id) if raw_id is not None else None,
        mode_key=data["mode_key"],
        sub_agent_id=int(raw_sub_agent_id) if raw_sub_agent_id is not None else None,
    )


def _book_to_dict(book: Book) -> dict[str, object]:
    """Serialize a ``Book`` row to a JSON-safe dict for export.

    ``id`` / ``owner_id`` emitted as ``str(...)``; the three enums via
    ``.value``; nullable ``moderation_reason`` / ``moderated_by`` (as
    ``str(...)`` when set) / ``moderated_at`` passed through; required
    ``title`` / ``description`` / ``system_prompt`` / ``active_notes``
    passthrough; datetimes via ``.isoformat()``.

    Skeleton (008 step 004): signature frozen; body UNIMPLEMENTED.
    """
    return {
        "id": str(book.id),
        "title": book.title,
        "description": book.description,
        "owner_id": str(book.owner_id),
        "collaboration_mode": book.collaboration_mode.value,
        "visibility": book.visibility.value,
        "state": book.state.value,
        "moderation_reason": book.moderation_reason,
        "moderated_by": (
            str(book.moderated_by) if book.moderated_by is not None else None
        ),
        "moderated_at": book.moderated_at.isoformat() if book.moderated_at else None,
        "system_prompt": book.system_prompt,
        "active_notes": book.active_notes,
        "created_at": book.created_at.isoformat() if book.created_at else None,
        "modified_at": book.modified_at.isoformat() if book.modified_at else None,
    }


def _dict_to_book(data: dict[str, object]) -> Book:
    """Restore a ``Book`` row from an exported dict (inverse of ``_book_to_dict``).

    ``id`` / ``owner_id`` parsed as string-or-legacy-number to ``int``; the
    three enums via ``CollaborationMode(...)`` / ``Visibility(...)`` /
    ``BookState(...)``; nullable ``moderated_by`` parsed to ``int`` when set;
    datetimes parsed from isoformat; required strings read directly.

    Skeleton (008 step 004): signature frozen; body UNIMPLEMENTED.
    """
    raw_id = data.get("id")
    raw_owner_id = data["owner_id"]
    raw_moderated_by = data.get("moderated_by")
    moderated_at = data.get("moderated_at")
    created_at = data.get("created_at")
    modified_at = data.get("modified_at")
    return Book(
        id=int(raw_id) if raw_id is not None else None,
        title=data["title"],
        description=data["description"],
        owner_id=int(raw_owner_id),
        collaboration_mode=CollaborationMode(data["collaboration_mode"]),
        visibility=Visibility(data["visibility"]),
        state=BookState(data["state"]),
        moderation_reason=data.get("moderation_reason"),
        moderated_by=int(raw_moderated_by) if raw_moderated_by is not None else None,
        moderated_at=datetime.fromisoformat(moderated_at) if moderated_at else None,
        system_prompt=data["system_prompt"],
        active_notes=data["active_notes"],
        created_at=datetime.fromisoformat(created_at) if created_at else None,
        modified_at=datetime.fromisoformat(modified_at) if modified_at else None,
    )


def _book_member_to_dict(member: BookMember) -> dict[str, object]:
    """Serialize a ``BookMember`` row to a JSON-safe dict for export.

    ``id`` / ``book_id`` / ``user_id`` emitted as ``str(...)``; ``role``
    serialised via ``MemberRole(...).value``; one timestamp (``created_at``)
    via ``.isoformat()``.
    """
    return {
        "id": str(member.id),
        "book_id": str(member.book_id),
        "user_id": str(member.user_id),
        "role": MemberRole(member.role).value,
        "created_at": member.created_at.isoformat() if member.created_at else None,
    }


def _dict_to_book_member(data: dict[str, object]) -> BookMember:
    """Restore a ``BookMember`` row from an exported dict (inverse of
    ``_book_member_to_dict``).

    ``id`` / ``book_id`` / ``user_id`` parsed as string-or-legacy-number to
    ``int``; ``role`` rebuilt via ``MemberRole(...)`` (``table=True`` skips
    validation, so a plain-``str`` restore is coerced to a true enum member);
    ``created_at`` parsed from isoformat.
    """
    raw_id = data.get("id")
    created_at = data.get("created_at")
    return BookMember(
        id=int(raw_id) if raw_id is not None else None,
        book_id=int(data["book_id"]),
        user_id=int(data["user_id"]),
        role=MemberRole(data["role"]),
        created_at=datetime.fromisoformat(created_at) if created_at else None,
    )


def _book_author_prompt_to_dict(prompt: BookAuthorPrompt) -> dict[str, object]:
    """Serialize a ``BookAuthorPrompt`` row to a JSON-safe dict for export.

    ``id`` / ``book_id`` / ``user_id`` emitted as ``str(...)``; the required
    ``system_prompt`` passed through verbatim (``""`` is a value, never
    ``None``); ``created_at`` / ``modified_at`` via ``.isoformat()`` or ``None``.
    """
    return {
        "id": str(prompt.id),
        "book_id": str(prompt.book_id),
        "user_id": str(prompt.user_id),
        "system_prompt": prompt.system_prompt,
        "created_at": prompt.created_at.isoformat() if prompt.created_at else None,
        "modified_at": (
            prompt.modified_at.isoformat() if prompt.modified_at else None
        ),
    }


def _dict_to_book_author_prompt(data: dict[str, object]) -> BookAuthorPrompt:
    """Restore a ``BookAuthorPrompt`` row from an exported dict (inverse of
    ``_book_author_prompt_to_dict``).

    ``id`` / ``book_id`` / ``user_id`` parsed as string-or-legacy-number to
    ``int``; ``system_prompt`` read directly (``""`` stays ``""``); datetimes
    parsed from isoformat.
    """
    raw_id = data.get("id")
    created_at = data.get("created_at")
    modified_at = data.get("modified_at")
    return BookAuthorPrompt(
        id=int(raw_id) if raw_id is not None else None,
        book_id=int(data["book_id"]),
        user_id=int(data["user_id"]),
        system_prompt=data["system_prompt"],
        created_at=datetime.fromisoformat(created_at) if created_at else None,
        modified_at=datetime.fromisoformat(modified_at) if modified_at else None,
    )


def _chapter_author_prompt_to_dict(
    prompt: ChapterAuthorPrompt,
) -> dict[str, object]:
    """Serialize a ``ChapterAuthorPrompt`` row to a JSON-safe dict for export.

    ``id`` / ``chapter_id`` / ``user_id`` emitted as ``str(...)``; the required
    ``system_prompt`` passed through verbatim (``""`` is a value, never
    ``None``); ``created_at`` / ``modified_at`` via ``.isoformat()`` or ``None``.
    Exported key set (frozen):
    ``{"id", "chapter_id", "user_id", "system_prompt", "created_at",
    "modified_at"}``.
    """
    return {
        "id": str(prompt.id),
        "chapter_id": str(prompt.chapter_id),
        "user_id": str(prompt.user_id),
        "system_prompt": prompt.system_prompt,
        "created_at": prompt.created_at.isoformat() if prompt.created_at else None,
        "modified_at": (
            prompt.modified_at.isoformat() if prompt.modified_at else None
        ),
    }


def _dict_to_chapter_author_prompt(
    data: dict[str, object],
) -> ChapterAuthorPrompt:
    """Restore a ``ChapterAuthorPrompt`` row from an exported dict (inverse of
    ``_chapter_author_prompt_to_dict``).

    ``id`` / ``chapter_id`` / ``user_id`` parsed as string-or-legacy-number to
    ``int``; ``system_prompt`` read directly (``""`` stays ``""``); datetimes
    parsed from isoformat.
    """
    raw_id = data.get("id")
    created_at = data.get("created_at")
    modified_at = data.get("modified_at")
    return ChapterAuthorPrompt(
        id=int(raw_id) if raw_id is not None else None,
        chapter_id=int(data["chapter_id"]),
        user_id=int(data["user_id"]),
        system_prompt=data["system_prompt"],
        created_at=datetime.fromisoformat(created_at) if created_at else None,
        modified_at=datetime.fromisoformat(modified_at) if modified_at else None,
    )


def _chapter_to_dict(chapter: Chapter) -> dict[str, object]:
    """Serialize a ``Chapter`` row to a JSON-safe dict for export.

    ``id`` / ``book_id`` emitted as ``str(...)``; ``state`` via ``.value``;
    nullable ``summary_status`` emitted as ``e.value if e else None``; nullable
    ``summary`` / ``system_prompt`` passed through; ``version`` int and
    ``ordinal`` int passthrough; ``title`` / ``sketch`` / ``text`` passthrough;
    datetimes via ``.isoformat()`` or ``None``.

    Skeleton (008 step 005): signature frozen; body UNIMPLEMENTED.
    """
    return {
        "id": str(chapter.id),
        "book_id": str(chapter.book_id),
        "ordinal": chapter.ordinal,
        "title": chapter.title,
        "state": chapter.state.value,
        "sketch": chapter.sketch,
        "text": chapter.text,
        "summary": chapter.summary,
        "summary_status": (
            chapter.summary_status.value if chapter.summary_status else None
        ),
        "system_prompt": chapter.system_prompt,
        "version": chapter.version,
        "created_at": chapter.created_at.isoformat() if chapter.created_at else None,
        "modified_at": (
            chapter.modified_at.isoformat() if chapter.modified_at else None
        ),
    }


def _dict_to_chapter(data: dict[str, object]) -> Chapter:
    """Restore a ``Chapter`` row from an exported dict (inverse of
    ``_chapter_to_dict``).

    ``id`` / ``book_id`` parsed as string-or-legacy-number to ``int``; ``state``
    via ``ChapterState(...)``; nullable ``summary_status`` parsed as
    ``SummaryStatus(x) if x else None``; nullable ``summary`` / ``system_prompt``
    read with ``.get(...)``; ``version`` int and ``ordinal`` int passthrough;
    required strings read directly; datetimes parsed from isoformat.

    Skeleton (008 step 005): signature frozen; body UNIMPLEMENTED.
    """
    raw_id = data.get("id")
    summary_status_raw = data.get("summary_status")
    created_at = data.get("created_at")
    modified_at = data.get("modified_at")
    return Chapter(
        id=int(raw_id) if raw_id is not None else None,
        book_id=int(data["book_id"]),
        ordinal=data["ordinal"],
        title=data["title"],
        state=ChapterState(data["state"]),
        sketch=data["sketch"],
        text=data["text"],
        summary=data.get("summary"),
        summary_status=(
            SummaryStatus(summary_status_raw) if summary_status_raw else None
        ),
        system_prompt=data.get("system_prompt"),
        version=data.get("version", 1),
        created_at=datetime.fromisoformat(created_at) if created_at else None,
        modified_at=datetime.fromisoformat(modified_at) if modified_at else None,
    )


def _chapter_change_to_dict(chapter_change: ChapterChange) -> dict[str, object]:
    """Serialize a ``ChapterChange`` row to a JSON-safe dict for export.

    ``id`` / ``chapter_id`` / ``author_id`` emitted as ``str(...)``; nullable
    ``applied_by`` emitted as ``str(...)`` when set, else ``None``; both enums
    (``placement_kind`` / ``status``) via ``.value``; nullable ``line_from`` /
    ``line_to`` ints passed through; ``base_version`` int and ``text``
    passthrough; nullable ``applied_at`` / ``created_at`` via ``.isoformat()``
    or ``None``.

    Skeleton (008 step 006): signature frozen; body UNIMPLEMENTED.
    """
    return {
        "id": str(chapter_change.id),
        "chapter_id": str(chapter_change.chapter_id),
        "author_id": str(chapter_change.author_id),
        "placement_kind": chapter_change.placement_kind.value,
        "line_from": chapter_change.line_from,
        "line_to": chapter_change.line_to,
        "base_version": chapter_change.base_version,
        "text": chapter_change.text,
        "status": chapter_change.status.value,
        "applied_at": (
            chapter_change.applied_at.isoformat()
            if chapter_change.applied_at
            else None
        ),
        "applied_by": (
            str(chapter_change.applied_by)
            if chapter_change.applied_by is not None
            else None
        ),
        "created_at": (
            chapter_change.created_at.isoformat()
            if chapter_change.created_at
            else None
        ),
    }


def _dict_to_chapter_change(data: dict[str, object]) -> ChapterChange:
    """Restore a ``ChapterChange`` row from an exported dict (inverse of
    ``_chapter_change_to_dict``).

    ``id`` / ``chapter_id`` / ``author_id`` parsed as string-or-legacy-number to
    ``int``; nullable ``applied_by`` parsed to ``int`` when set; both enums via
    ``PlacementKind(...)`` / ``ChangeStatus(...)``; nullable ``line_from`` /
    ``line_to`` read with ``.get(...)``; ``base_version`` int and ``text`` read
    directly; datetimes parsed from isoformat.

    Skeleton (008 step 006): signature frozen; body UNIMPLEMENTED.
    """
    raw_id = data.get("id")
    applied_at = data.get("applied_at")
    applied_by_raw = data.get("applied_by")
    created_at = data.get("created_at")
    return ChapterChange(
        id=int(raw_id) if raw_id is not None else None,
        chapter_id=int(data["chapter_id"]),
        author_id=int(data["author_id"]),
        placement_kind=PlacementKind(data["placement_kind"]),
        line_from=data.get("line_from"),
        line_to=data.get("line_to"),
        base_version=data["base_version"],
        text=data["text"],
        status=ChangeStatus(data["status"]),
        applied_at=datetime.fromisoformat(applied_at) if applied_at else None,
        applied_by=int(applied_by_raw) if applied_by_raw is not None else None,
        created_at=datetime.fromisoformat(created_at) if created_at else None,
    )


def _chapter_text_revision_to_dict(revision: ChapterTextRevision) -> dict[str, object]:
    """Serialize a ``ChapterTextRevision`` row to a JSON-safe dict for export.

    ``id`` / ``chapter_id`` / ``applied_change_id`` / ``applied_by`` emitted as
    ``str(...)``; ``text_before`` passthrough; nullable ``applied_at`` via
    ``.isoformat()`` or ``None``.

    Skeleton (008 step 006): signature frozen; body UNIMPLEMENTED.
    """
    return {
        "id": str(revision.id),
        "chapter_id": str(revision.chapter_id),
        "applied_change_id": str(revision.applied_change_id),
        "applied_by": str(revision.applied_by),
        "text_before": revision.text_before,
        "applied_at": (
            revision.applied_at.isoformat() if revision.applied_at else None
        ),
    }


def _dict_to_chapter_text_revision(data: dict[str, object]) -> ChapterTextRevision:
    """Restore a ``ChapterTextRevision`` row from an exported dict (inverse of
    ``_chapter_text_revision_to_dict``).

    ``id`` / ``chapter_id`` / ``applied_change_id`` / ``applied_by`` parsed as
    string-or-legacy-number to ``int``; ``text_before`` read directly;
    ``applied_at`` parsed from isoformat.

    Skeleton (008 step 006): signature frozen; body UNIMPLEMENTED.
    """
    raw_id = data.get("id")
    applied_at = data.get("applied_at")
    return ChapterTextRevision(
        id=int(raw_id) if raw_id is not None else None,
        chapter_id=int(data["chapter_id"]),
        applied_change_id=int(data["applied_change_id"]),
        text_before=data["text_before"],
        applied_by=int(data["applied_by"]),
        applied_at=datetime.fromisoformat(applied_at) if applied_at else None,
    )


def _chapter_note_changeset_to_dict(
    changeset: ChapterNoteChangeset,
) -> dict[str, object]:
    """Serialize a ``ChapterNoteChangeset`` row to a JSON-safe dict for export.

    ``id`` / ``chapter_id`` emitted as ``str(...)``; ``added`` / ``modified`` /
    ``deleted`` passthrough; nullable ``status`` emitted as
    ``e.value if e else None``; nullable ``created_at`` / ``modified_at`` via
    ``.isoformat()`` or ``None``.

    Skeleton (008 step 007): signature frozen; body UNIMPLEMENTED.
    """
    return {
        "id": str(changeset.id),
        "chapter_id": str(changeset.chapter_id),
        "added": changeset.added,
        "modified": changeset.modified,
        "deleted": changeset.deleted,
        "status": changeset.status.value if changeset.status else None,
        "created_at": (
            changeset.created_at.isoformat() if changeset.created_at else None
        ),
        "modified_at": (
            changeset.modified_at.isoformat() if changeset.modified_at else None
        ),
    }


def _dict_to_chapter_note_changeset(data: dict[str, object]) -> ChapterNoteChangeset:
    """Restore a ``ChapterNoteChangeset`` row from an exported dict (inverse of
    ``_chapter_note_changeset_to_dict``).

    ``id`` / ``chapter_id`` parsed as string-or-legacy-number to ``int``;
    ``added`` / ``modified`` / ``deleted`` read directly; nullable ``status`` via
    ``NoteStatus(x) if x else None``; datetimes parsed from isoformat.

    Skeleton (008 step 007): signature frozen; body UNIMPLEMENTED.
    """
    raw_id = data.get("id")
    status_raw = data.get("status")
    created_at = data.get("created_at")
    modified_at = data.get("modified_at")
    return ChapterNoteChangeset(
        id=int(raw_id) if raw_id is not None else None,
        chapter_id=int(data["chapter_id"]),
        added=data["added"],
        modified=data["modified"],
        deleted=data["deleted"],
        status=NoteStatus(status_raw) if status_raw else None,
        created_at=datetime.fromisoformat(created_at) if created_at else None,
        modified_at=datetime.fromisoformat(modified_at) if modified_at else None,
    )


def _flag_to_dict(flag: Flag) -> dict[str, object]:
    """Serialize a ``Flag`` row to a JSON-safe dict for export.

    ``id`` / ``chapter_id`` / ``created_by`` emitted as ``str(...)``; both enums
    (``origin`` / ``status``) via ``.value``; ``comment`` passthrough; nullable
    ``resolved_by`` emitted as ``str(...)`` when set, else ``None``; nullable
    ``created_at`` / ``resolved_at`` via ``.isoformat()`` or ``None``.

    Skeleton (008 step 007): signature frozen; body UNIMPLEMENTED.
    """
    return {
        "id": str(flag.id),
        "chapter_id": str(flag.chapter_id),
        "origin": flag.origin.value,
        "comment": flag.comment,
        "status": flag.status.value,
        "created_by": str(flag.created_by),
        "created_at": flag.created_at.isoformat() if flag.created_at else None,
        "resolved_by": (
            str(flag.resolved_by) if flag.resolved_by is not None else None
        ),
        "resolved_at": flag.resolved_at.isoformat() if flag.resolved_at else None,
    }


def _dict_to_flag(data: dict[str, object]) -> Flag:
    """Restore a ``Flag`` row from an exported dict (inverse of ``_flag_to_dict``).

    ``id`` / ``chapter_id`` / ``created_by`` parsed as string-or-legacy-number to
    ``int``; both enums via ``FlagOrigin(...)`` / ``FlagStatus(...)``;
    ``comment`` read directly; nullable ``resolved_by`` parsed to ``int`` when
    set; datetimes parsed from isoformat.

    Skeleton (008 step 007): signature frozen; body UNIMPLEMENTED.
    """
    raw_id = data.get("id")
    created_at = data.get("created_at")
    resolved_by_raw = data.get("resolved_by")
    resolved_at = data.get("resolved_at")
    return Flag(
        id=int(raw_id) if raw_id is not None else None,
        chapter_id=int(data["chapter_id"]),
        origin=FlagOrigin(data["origin"]),
        comment=data["comment"],
        status=FlagStatus(data["status"]),
        created_by=int(data["created_by"]),
        created_at=datetime.fromisoformat(created_at) if created_at else None,
        resolved_by=int(resolved_by_raw) if resolved_by_raw is not None else None,
        resolved_at=datetime.fromisoformat(resolved_at) if resolved_at else None,
    )


def _codex_entry_to_dict(entry: CodexEntry) -> dict[str, object]:
    """Serialize a ``CodexEntry`` row to a JSON-safe dict for export.

    ``id`` / ``book_id`` emitted as ``str(...)``; ``kind`` via ``.value``;
    nullable ``name`` passed through (including the null-for-fact case);
    ``archived`` bool passthrough; ``body`` passthrough; ``author_id`` emitted
    as ``str(...)`` (required); nullable ``modified_by`` emitted as ``str(...)``
    when set, else ``None``; nullable ``created_at`` / ``modified_at`` via
    ``.isoformat()`` or ``None``.

    Skeleton (008 step 008): signature frozen; body UNIMPLEMENTED.
    """
    return {
        "id": str(entry.id),
        "book_id": str(entry.book_id),
        "kind": entry.kind.value,
        "name": entry.name,
        "body": entry.body,
        "archived": entry.archived,
        "author_id": str(entry.author_id),
        "modified_by": (
            str(entry.modified_by) if entry.modified_by is not None else None
        ),
        "created_at": (
            entry.created_at.isoformat() if entry.created_at else None
        ),
        "modified_at": (
            entry.modified_at.isoformat() if entry.modified_at else None
        ),
    }


def _dict_to_codex_entry(data: dict[str, object]) -> CodexEntry:
    """Restore a ``CodexEntry`` row from an exported dict (inverse of
    ``_codex_entry_to_dict``).

    ``id`` / ``book_id`` parsed as string-or-legacy-number to ``int``; ``kind``
    via ``CodexKind(...)``; nullable ``name`` read with ``.get(...)`` (None for
    fact); ``archived`` bool via ``.get(...)``; ``body`` read directly;
    ``author_id`` parsed to ``int`` (required); nullable ``modified_by`` parsed
    to ``int`` when set; datetimes parsed from isoformat.

    Skeleton (008 step 008): signature frozen; body UNIMPLEMENTED.
    """
    raw_id = data.get("id")
    modified_by_raw = data.get("modified_by")
    created_at = data.get("created_at")
    modified_at = data.get("modified_at")
    return CodexEntry(
        id=int(raw_id) if raw_id is not None else None,
        book_id=int(data["book_id"]),
        kind=CodexKind(data["kind"]),
        name=data.get("name"),
        body=data["body"],
        archived=data.get("archived", False),
        author_id=int(data["author_id"]),
        modified_by=int(modified_by_raw) if modified_by_raw is not None else None,
        created_at=datetime.fromisoformat(created_at) if created_at else None,
        modified_at=datetime.fromisoformat(modified_at) if modified_at else None,
    )


def _codex_entry_version_to_dict(version: CodexEntryVersion) -> dict[str, object]:
    """Serialize a ``CodexEntryVersion`` row to a JSON-safe dict for export.

    ``id`` / ``entry_id`` / ``author_id`` emitted as ``str(...)``; nullable
    ``name`` passed through; ``body`` passthrough; ``kind`` via ``.value``;
    ``generation`` plain int passthrough; nullable ``created_at`` via
    ``.isoformat()`` or ``None``.

    Skeleton (008 step 008): signature frozen; body UNIMPLEMENTED.
    """
    return {
        "id": str(version.id),
        "entry_id": str(version.entry_id),
        "author_id": str(version.author_id),
        "name": version.name,
        "body": version.body,
        "kind": version.kind.value,
        "generation": version.generation,
        "created_at": (
            version.created_at.isoformat() if version.created_at else None
        ),
    }


def _dict_to_codex_entry_version(data: dict[str, object]) -> CodexEntryVersion:
    """Restore a ``CodexEntryVersion`` row from an exported dict (inverse of
    ``_codex_entry_version_to_dict``).

    ``id`` / ``entry_id`` / ``author_id`` parsed as string-or-legacy-number to
    ``int``; nullable ``name`` read with ``.get(...)``; ``body`` read directly;
    ``kind`` via ``CodexKind(...)``; ``generation`` plain int passthrough;
    ``created_at`` parsed from isoformat.

    Skeleton (008 step 008): signature frozen; body UNIMPLEMENTED.
    """
    raw_id = data.get("id")
    created_at = data.get("created_at")
    return CodexEntryVersion(
        id=int(raw_id) if raw_id is not None else None,
        entry_id=int(data["entry_id"]),
        author_id=int(data["author_id"]),
        name=data.get("name"),
        body=data["body"],
        kind=CodexKind(data["kind"]),
        generation=data["generation"],
        created_at=datetime.fromisoformat(created_at) if created_at else None,
    )


def _chat_to_dict(chat: Chat) -> dict[str, object]:
    """Serialize a ``Chat`` row to a JSON-safe dict for export.

    ``id`` / ``book_id`` / ``author_id`` emitted as ``str(...)``; ``title``
    passthrough; ``archived`` bool passthrough; nullable ``created_at`` /
    ``modified_at`` via ``.isoformat()`` or ``None``.

    Skeleton (008 step 009): signature frozen; body UNIMPLEMENTED.
    """
    return {
        "id": str(chat.id),
        "book_id": str(chat.book_id),
        "author_id": str(chat.author_id),
        "title": chat.title,
        "llm_server_id": (
            str(chat.llm_server_id) if chat.llm_server_id is not None else None
        ),
        "model_name": chat.model_name,
        "sampling_params": chat.sampling_params,
        "archived": chat.archived,
        "created_at": chat.created_at.isoformat() if chat.created_at else None,
        "modified_at": (
            chat.modified_at.isoformat() if chat.modified_at else None
        ),
    }


def _dict_to_chat(data: dict[str, object]) -> Chat:
    """Restore a ``Chat`` row from an exported dict (inverse of ``_chat_to_dict``).

    ``id`` / ``book_id`` / ``author_id`` parsed as string-or-legacy-number to
    ``int``; ``title`` read directly; ``archived`` bool via ``.get(...)``;
    datetimes parsed from isoformat.

    Skeleton (008 step 009): signature frozen; body UNIMPLEMENTED.
    """
    raw_id = data.get("id")
    raw_server_id = data.get("llm_server_id")
    created_at = data.get("created_at")
    modified_at = data.get("modified_at")
    chat = Chat(
        id=int(raw_id) if raw_id is not None else None,
        book_id=int(data["book_id"]),
        author_id=int(data["author_id"]),
        title=data["title"],
        llm_server_id=int(raw_server_id) if raw_server_id is not None else None,
        model_name=data.get("model_name"),
        archived=data.get("archived", False),
        created_at=datetime.fromisoformat(created_at) if created_at else None,
        modified_at=datetime.fromisoformat(modified_at) if modified_at else None,
    )
    sampling_params = data.get("sampling_params")
    if sampling_params is not None:
        chat.sampling_params = sampling_params
    return chat


def _chat_message_to_dict(message: ChatMessage) -> dict[str, object]:
    """Serialize a ``ChatMessage`` row to a JSON-safe dict for export.

    ``id`` / ``chat_id`` emitted as ``str(...)``; ``role`` / ``content`` passed
    through; ``position`` plain int passthrough; nullable ``created_at`` via
    ``.isoformat()`` or ``None``.

    Skeleton (008 step 009): signature frozen; body UNIMPLEMENTED.
    """
    return {
        "id": str(message.id),
        "chat_id": str(message.chat_id),
        "role": message.role,
        "content": message.content,
        "reasoning": message.reasoning,
        "position": message.position,
        "created_at": (
            message.created_at.isoformat() if message.created_at else None
        ),
    }


def _dict_to_chat_message(data: dict[str, object]) -> ChatMessage:
    """Restore a ``ChatMessage`` row from an exported dict (inverse of
    ``_chat_message_to_dict``).

    ``id`` / ``chat_id`` parsed as string-or-legacy-number to ``int``; ``role``
    / ``content`` read directly; ``position`` plain int passthrough;
    ``created_at`` parsed from isoformat.

    Skeleton (008 step 009): signature frozen; body UNIMPLEMENTED.
    """
    raw_id = data.get("id")
    created_at = data.get("created_at")
    return ChatMessage(
        id=int(raw_id) if raw_id is not None else None,
        chat_id=int(data["chat_id"]),
        role=data["role"],
        content=data["content"],
        reasoning=data.get("reasoning"),
        position=data["position"],
        created_at=datetime.fromisoformat(created_at) if created_at else None,
    )


# One registry entry per persistent table, in FK (import) order. ``users`` is
# first — it precedes any dependent entity. ``llm_servers`` follows (no FK to
# users; order just needs to be deterministic, D6). The FEAT-020 config block
# (``assistant_modes``, ``sub_agents``) is instance-global and slots in
# immediately after ``llm_servers``, before any book-domain entry (canonical
# order, backend/book-domain.md). The three link tables (``mode_tools``,
# ``subagent_tools``, ``mode_subagents``) follow ``sub_agents`` — their FK
# parents (``assistant_modes`` / ``sub_agents``) precede them. Note the plural
# registry labels deliberately differ from the singular ``__tablename__`` of
# each link table. Real codec functions are referenced here even while their
# bodies are unimplemented, so the registry is non-empty and importable.
TABLE_REGISTRY: list[RegistryEntry] = [
    ("users", User, _user_to_dict, _dict_to_user),
    ("llm_servers", LlmServer, _llm_server_to_dict, _dict_to_llm_server),
    ("assistant_modes", AssistantMode, _assistant_mode_to_dict, _dict_to_assistant_mode),
    ("sub_agents", SubAgent, _sub_agent_to_dict, _dict_to_sub_agent),
    ("mode_tools", ModeTool, _mode_tool_to_dict, _dict_to_mode_tool),
    ("subagent_tools", SubagentTool, _subagent_tool_to_dict, _dict_to_subagent_tool),
    ("mode_subagents", ModeSubagent, _mode_subagent_to_dict, _dict_to_mode_subagent),
    ("books", Book, _book_to_dict, _dict_to_book),
    ("book_members", BookMember, _book_member_to_dict, _dict_to_book_member),
    (
        "book_author_prompts",
        BookAuthorPrompt,
        _book_author_prompt_to_dict,
        _dict_to_book_author_prompt,
    ),
    (
        "chapter_author_prompts",
        ChapterAuthorPrompt,
        _chapter_author_prompt_to_dict,
        _dict_to_chapter_author_prompt,
    ),
    ("chapters", Chapter, _chapter_to_dict, _dict_to_chapter),
    (
        "chapter_changes",
        ChapterChange,
        _chapter_change_to_dict,
        _dict_to_chapter_change,
    ),
    (
        "chapter_text_revisions",
        ChapterTextRevision,
        _chapter_text_revision_to_dict,
        _dict_to_chapter_text_revision,
    ),
    (
        "chapter_note_changesets",
        ChapterNoteChangeset,
        _chapter_note_changeset_to_dict,
        _dict_to_chapter_note_changeset,
    ),
    (
        "codex_entries",
        CodexEntry,
        _codex_entry_to_dict,
        _dict_to_codex_entry,
    ),
    (
        "codex_entry_versions",
        CodexEntryVersion,
        _codex_entry_version_to_dict,
        _dict_to_codex_entry_version,
    ),
    ("flags", Flag, _flag_to_dict, _dict_to_flag),
    ("chats", Chat, _chat_to_dict, _dict_to_chat),
    ("chat_messages", ChatMessage, _chat_message_to_dict, _dict_to_chat_message),
]

# Max rows accumulated before a streaming UPSERT flush on import.
BATCH_SIZE = 100


async def export_all() -> bytes:
    """Export every registered table to a zip of ``<table>.jsonl.gz`` members.

    One gzip-JSONL member per ``TABLE_REGISTRY`` entry, each streamed per-row
    through gzip via ``export_table`` plus a serializing callback (rows are
    never collected into a large in-memory list). Over the empty registry this
    yields a valid, empty zip archive. Returns the zip archive as ``bytes``.
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
        for zip_filename, model_class, to_dict_fn, _from_dict_fn in TABLE_REGISTRY:
            gz_buf = io.BytesIO()
            with gzip.open(gz_buf, "wt", encoding="utf-8") as gz:

                def make_writer(
                    gz_file: gzip.GzipFile,
                    serializer: Callable[[SQLModel], dict[str, object]],
                ) -> Callable[[SQLModel], None]:
                    def write_row(row: SQLModel) -> None:
                        gz_file.write(json.dumps(serializer(row)) + "\n")

                    return write_row

                await import_export_queries.export_table(
                    model_class, make_writer(gz, to_dict_fn)
                )
            zf.writestr(zip_filename, gz_buf.getvalue())

    return buf.getvalue()


async def import_all(zip_bytes: bytes) -> None:
    """Import every registered table from a zip of ``<table>.jsonl.gz`` members.

    Calls ``init_db()`` first (creates/reshapes tables), then, for each registry
    entry, streams its JSONL lines, accumulates up to ``BATCH_SIZE`` rows, and
    flushes each batch via ``upsert_batch``; finally triggers
    ``run_vector_rebuild()``. UPSERT — idempotent. Over an empty registry /
    empty archive this is a no-op that still runs ``init_db()``.
    """
    await engine.init_db()

    with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
        member_names = set(zf.namelist())
        for zip_filename, _model_class, _to_dict_fn, from_dict_fn in TABLE_REGISTRY:
            if zip_filename not in member_names:
                continue

            batch: list[SQLModel] = []
            with gzip.open(
                io.BytesIO(zf.read(zip_filename)), "rt", encoding="utf-8"
            ) as gz:
                for raw_line in gz:
                    line = raw_line.strip()
                    if not line:
                        continue
                    batch.append(from_dict_fn(json.loads(line)))
                    if len(batch) >= BATCH_SIZE:
                        await import_export_queries.upsert_batch(batch)
                        batch.clear()
            if batch:
                await import_export_queries.upsert_batch(batch)

    await import_export_queries.run_vector_rebuild()
