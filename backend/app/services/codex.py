"""Codex service — every codex business rule lives here (feature 013, step 002).

Business-logic layer: **no** ``session`` / ``AsyncSession`` / ``select()`` /
``session.exec()`` / ``session.add()`` here (see ``docs/architecture/backend.md``
— layer separation). All persistence goes through the session-free
``app.db.codex_entries`` / ``app.db.codex_entry_versions`` layers (namespace
imports, signatures frozen by 013 step 001). Domain refusals raise the typed
:class:`CodexError`, discriminated by :class:`CodexErrorReason` so the route
(step 003) maps each case to its HTTP status through a module-level dict; the
route stays HTTP-only.

The four rules this service owns:

1. **Capability** — every entry point calls ``authz.require`` itself:
   ``Capability.browse_codex`` for the read paths, ``Capability.edit_codex_entry``
   for create and update. A reader or non-member never reaches a rule below.
2. **The kind/name rule** (US-078.AC-1 / AC-2) — ``character`` and ``location``
   require a non-blank name (whitespace-only counts as absent →
   ``name_required``); ``fact`` refuses one (→ ``name_not_allowed``) and stores
   ``name`` as ``None``.
3. **The collaboration-mode rule** (``context.md`` → decision 3) — the owner's
   write always applies; a **co-author** writing to a book whose
   ``collaboration_mode`` is ``proposal`` is refused with
   ``proposal_mode_unsupported`` (the message names FEAT-010 as unbuilt); free
   mode applies a co-author's write immediately. The branch is on
   ``role == co_author``, not "not owner", so a future admin/reader path cannot
   slip through. ``BookAccess.collaboration_mode`` is already resolved by the
   route dependency — the book is **not** re-read here.
4. **Optimistic concurrency** — an update carrying an ``expected_modified_at``
   that disagrees with the stored ``CodexEntry.modified_at`` is refused as
   ``stale_modified_at`` (→ 409); nothing is written.

**Version rows.** No version row is written on create — the first version row
records the state *before* the first edit, so a never-edited entry has no
history. On update the ``CodexEntryVersion`` carrying the entry's **prior**
``name`` / ``body`` / ``kind`` is written **before** the entry row is mutated
(writing it afterwards would capture the new content), with ``author_id`` set to
the acting user of that edit and ``generation`` from
``codex_entry_versions.next_generation``.

**Index maintenance (step 006).** After — never before — the db-layer write
returns, :func:`create_entry` and :func:`update_entry` hand the freshly stored
row to ``services/codex_index.py``, which chunks, embeds and replaces that
entry's chunks in the vector sidecar. The call is awaited inside the request (no
queue — ``retrieval.md``), it **never raises**, and its outcome is ignored: a
failed index leaves a successful save (``retrieval.md`` → "Index maintenance
never blocks the author's save"). Nothing embedding-shaped is called from this
module directly; the edge is one-way (``codex`` → ``codex_index``, never back).

Skeleton (013 step 002): the error taxonomy and the function signatures below are
frozen.
"""

import enum
from datetime import datetime, timezone

from app.db import codex_entries, codex_entry_versions
from app.models.book import CollaborationMode
from app.models.codex_entry import CodexEntry, CodexKind
from app.models.codex_entry_version import CodexEntryVersion
from app.models.schemas.codex import (
    CodexEntryListResponse,
    CodexEntryResponse,
    CreateCodexEntryRequest,
    UpdateCodexEntryRequest,
)
from app.models.user import User
from app.services import authz
from app.services import codex_index


class CodexErrorReason(str, enum.Enum):
    """Discriminator for :class:`CodexError` — the codex refusal taxonomy.

    Mirrors the shape of :class:`app.services.chats.ChatErrorReason`. The step-003
    route maps each case to its HTTP status (``_CODEX_ERROR_STATUS``):
    ``entry_not_found`` → **404** (an entry in another book is treated exactly
    like a missing one — US-085.AC-1); ``name_required`` / ``name_not_allowed`` /
    ``entry_archived`` → **400**; ``stale_modified_at`` → **409**;
    ``proposal_mode_unsupported`` → **403** (the caller can legitimately see the
    book — ``context.md`` → "Planner-derived decisions").
    """

    entry_not_found = "entry-not-found"
    name_required = "name-required"
    name_not_allowed = "name-not-allowed"
    entry_archived = "entry-archived"
    stale_modified_at = "stale-modified-at"
    proposal_mode_unsupported = "proposal-mode-unsupported"


class CodexError(Exception):
    """Raised by the codex service for every domain refusal.

    Carries a :class:`CodexErrorReason` discriminator (``reason``) plus a
    human-readable ``message``; the route branches on ``reason`` to pick the
    status. Mirrors :class:`app.services.chats.ChatError`.
    """

    def __init__(self, reason: CodexErrorReason, message: str = "") -> None:
        self.reason = reason
        self.message = message
        super().__init__(message)


def _to_entry_response(entry: CodexEntry) -> CodexEntryResponse:
    """Map a ``CodexEntry`` row to a :class:`CodexEntryResponse` by hand (never
    dump the ORM). Ids stringified; ``modified_by`` stays ``None`` when unset.
    **This is the only place the DTO is constructed.**
    """
    return CodexEntryResponse(
        id=str(entry.id),
        book_id=str(entry.book_id),
        kind=entry.kind,
        name=entry.name,
        body=entry.body,
        archived=entry.archived,
        author_id=str(entry.author_id),
        modified_by=(
            str(entry.modified_by) if entry.modified_by is not None else None
        ),
        created_at=entry.created_at,
        modified_at=entry.modified_at,
    )


def _resolve_name(kind: CodexKind, name: str | None) -> str | None:
    """Apply the kind/name rule (US-078.AC-1 / AC-2) and return the ``name`` to
    store.

    A whitespace-only name counts as **absent**. ``character`` / ``location``
    therefore require a name that is non-blank (else ``name_required``), and
    ``fact`` refuses one (``name_not_allowed``) and stores ``None``. The stored
    value is the name exactly as supplied — only the *rule* looks past the
    surrounding whitespace.
    """
    supplied = name.strip() if name is not None else ""
    if kind == CodexKind.fact:
        if supplied:
            raise CodexError(
                CodexErrorReason.name_not_allowed,
                "A fact has no name — leave it empty.",
            )
        return None
    if not supplied:
        raise CodexError(
            CodexErrorReason.name_required,
            f"A {kind.value} entry requires a name.",
        )
    return name


def _require_writable_mode(access: authz.BookAccess) -> None:
    """Apply the collaboration-mode rule (``context.md`` → decision 3).

    The owner's write always applies. A **co-author** writing to a book whose
    ``collaboration_mode`` is ``proposal`` is refused with
    ``proposal_mode_unsupported``, whose message names FEAT-010 as unbuilt so the
    author learns *why*, not just that. Free mode applies a co-author's write
    immediately. The branch is on ``role == co_author`` rather than "not owner",
    so no future role slips through it.
    """
    if (
        access.role == authz.AccessRole.co_author
        and access.collaboration_mode == CollaborationMode.proposal
    ):
        raise CodexError(
            CodexErrorReason.proposal_mode_unsupported,
            "This book is in proposal mode, so a co-author's codex change must "
            "be held for the owner's review. That review surface is FEAT-010, "
            "which is not built yet, so the change cannot be accepted. Ask the "
            "owner to switch the book to free mode.",
        )


def _comparable(value: datetime | None) -> datetime | None:
    """Normalize a ``modified_at`` for the staleness comparison.

    Stored timestamps come back from SQLite naive (UTC wall clock), while a
    caller may hand over the same instant tz-aware. Both sides are reduced to a
    naive UTC value so that only a genuine *difference* reads as stale — a
    ``None`` (an entry never edited since it was seeded) compares as itself.
    """
    if value is None or value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


async def _resolve_entry(access: authz.BookAccess, entry_id: str) -> CodexEntry:
    """Return the entry ``entry_id`` **within** ``access.book_id``.

    An unknown id, a non-numeric id and an entry belonging to a different book
    all raise ``entry_not_found`` — another book's content is never returned and
    its existence is never confirmed (US-085.AC-1).
    """
    try:
        parsed_id = int(entry_id)
    except (ValueError, TypeError):
        raise CodexError(CodexErrorReason.entry_not_found, "Codex entry not found.")
    entry = await codex_entries.get_by_id(parsed_id)
    if entry is None or entry.book_id != access.book_id:
        raise CodexError(CodexErrorReason.entry_not_found, "Codex entry not found.")
    return entry


async def create_entry(
    access: authz.BookAccess, user: User, req: CreateCodexEntryRequest
) -> CodexEntryResponse:
    """Create a codex entry in ``access.book_id`` and return its
    :class:`CodexEntryResponse` (UC-069, US-078).

    Requires ``Capability.edit_codex_entry``, applies the collaboration-mode rule
    and the kind/name rule, then stores the row with ``author_id`` set to
    ``user`` (the original creator, never rewritten), ``modified_by`` unset and
    ``archived`` false. **No version row is written on create.** A refused create
    writes nothing at all.
    """
    authz.require(access, authz.Capability.edit_codex_entry)
    _require_writable_mode(access)
    name = _resolve_name(req.kind, req.name)
    now = datetime.now(timezone.utc)
    entry = await codex_entries.create(
        CodexEntry(
            book_id=access.book_id,
            kind=req.kind,
            name=name,
            body=req.body,
            archived=False,
            author_id=user.id,
            modified_by=None,
            created_at=now,
            modified_at=now,
        )
    )
    # Index maintenance, AFTER the SQLite write returns: the indexer sees the
    # stored row. Best-effort — it never raises, and its outcome is ignored.
    await codex_index.index_entry(entry)
    return _to_entry_response(entry)


async def list_entries(
    access: authz.BookAccess,
    kind: CodexKind | None = None,
    needle: str | None = None,
    include_archived: bool = False,
) -> CodexEntryListResponse:
    """Return ``access.book_id``'s entries as a :class:`CodexEntryListResponse`
    (UC-071, US-080.AC-1).

    Requires ``Capability.browse_codex``. ``kind`` absent means every kind;
    ``needle`` is the optional case-insensitive substring over ``name`` or
    ``body``; archived entries are excluded unless ``include_archived``. Filtering
    and ordering are the db layer's (``codex_entries.list_by_book``) — this
    function forwards the filters and maps the rows.
    """
    authz.require(access, authz.Capability.browse_codex)
    rows = await codex_entries.list_by_book(
        access.book_id,
        kind=kind,
        include_archived=include_archived,
        needle=needle,
    )
    return CodexEntryListResponse(items=[_to_entry_response(row) for row in rows])


async def get_entry(
    access: authz.BookAccess, entry_id: str
) -> CodexEntryResponse:
    """Return one entry of ``access.book_id`` (UC-070 step 1).

    Requires ``Capability.browse_codex``. An unknown id, a non-numeric id, and an
    entry belonging to a **different book** all raise
    :class:`CodexError` with ``entry_not_found`` — another book's content is never
    returned and its existence is never confirmed (US-085.AC-1).
    """
    authz.require(access, authz.Capability.browse_codex)
    entry = await _resolve_entry(access, entry_id)
    return _to_entry_response(entry)


async def update_entry(
    access: authz.BookAccess,
    user: User,
    entry_id: str,
    req: UpdateCodexEntryRequest,
) -> CodexEntryResponse:
    """Full-replace edit of one entry, returning its refreshed
    :class:`CodexEntryResponse` (UC-070, US-079.AC-1).

    Requires ``Capability.edit_codex_entry``, resolves the entry the same way as
    :func:`get_entry` (another book's entry is ``entry_not_found``), applies the
    collaboration-mode rule, refuses an archived entry (``entry_archived``),
    compares ``req.expected_modified_at`` against the stored ``modified_at`` and
    raises ``stale_modified_at`` on any disagreement, and validates the kind/name
    rule against the entry's **stored** ``kind``.

    Then, **in this order**: write a ``CodexEntryVersion`` carrying the entry's
    PRIOR ``name`` / ``body`` / ``kind`` (``author_id`` = ``user``, ``generation``
    from ``codex_entry_versions.next_generation``), **then** apply the new
    content, set ``modified_by`` to ``user`` and bump ``modified_at``. A refused
    update writes neither a version row nor a change to the entry.
    """
    authz.require(access, authz.Capability.edit_codex_entry)
    entry = await _resolve_entry(access, entry_id)
    _require_writable_mode(access)
    if entry.archived:
        raise CodexError(
            CodexErrorReason.entry_archived,
            "This entry is archived and read-only.",
        )
    if _comparable(req.expected_modified_at) != _comparable(entry.modified_at):
        raise CodexError(
            CodexErrorReason.stale_modified_at,
            "This entry changed since it was loaded — reload it and reconcile.",
        )
    # Validated against the entry's STORED kind: ``kind`` is not updatable.
    name = _resolve_name(entry.kind, req.name)

    now = datetime.now(timezone.utc)
    # The version row carries the entry's PRIOR content and is written BEFORE the
    # entry is mutated — writing it afterwards would capture the new content
    # (``domain-codex.md``: content "as it stood" at that version).
    generation = await codex_entry_versions.next_generation(entry.id)
    await codex_entry_versions.create(
        CodexEntryVersion(
            entry_id=entry.id,
            name=entry.name,
            body=entry.body,
            kind=entry.kind,
            author_id=user.id,
            generation=generation,
            created_at=now,
        )
    )

    entry.name = name
    entry.body = req.body
    entry.modified_by = user.id
    entry.modified_at = now
    entry = await codex_entries.update(entry)
    # Index maintenance, AFTER both the version row and the entry mutation have
    # committed, so the indexer sees the new content. Best-effort as on create.
    await codex_index.index_entry(entry)
    return _to_entry_response(entry)
