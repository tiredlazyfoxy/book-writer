"""Codex request & response schemas (feature 013, step 002).

Declarative Pydantic schemas — the typed contracts for the book-nested codex
surface (``/api/books/{book_id}/codex``). Plain typed data shapes, no logic
(see ``docs/architecture/backend.md`` — ``models/`` is tables + schemas only).

Conventions this file follows:

- **Ids are ``str``** on the wire (snowflakes exceed the JS safe-integer range,
  mirroring ``ChatResponse.id`` / ``BookResponse.id``).
- ``kind`` is the shared :class:`app.models.codex_entry.CodexKind` taxonomy
  (character / location / fact — three kinds, one table).
- **``kind`` is not updatable**: changing an entry's kind would move it between
  navigator lists and invalidate its name rule, so it appears on the create
  request only (``002.codex-schemas-service.md`` → Interface intent).
- ``name`` is nullable everywhere because a fact has no name (US-078.AC-2). The
  kind/name rule itself (required for character/location, refused for fact) is a
  **service** rule (``services/codex.py``), deliberately not modelled here.
- :attr:`UpdateCodexEntryRequest.expected_modified_at` is the optimistic-
  concurrency token: the ``modified_at`` the client loaded the entry at, echoed
  back on save. It is **required but nullable** — an entry never edited since
  creation may legitimately carry ``null``, and an omitted field must not
  silently pass the staleness check. The value is the same serialization the
  response emits, because the frontend restore buffer uses it verbatim as its
  ``baseVersion`` (``frontend/src/work/restoreBuffer.ts``).

Skeleton (013 step 002): field names / types / defaults are frozen. DTOs are
declarative — there is nothing to leave unimplemented.
"""

from datetime import datetime

from pydantic import BaseModel

from app.models.codex_entry import CodexKind


class CreateCodexEntryRequest(BaseModel):
    """Body of ``POST /api/books/{book_id}/codex`` — a new codex entry (UC-069).

    - ``kind`` — required; the entry's :class:`CodexKind`.
    - ``name`` — optional here; the service applies the kind/name rule
      (character / location **require** a non-blank name, fact **refuses** one).
    - ``body`` — the entry's content.
    """

    kind: CodexKind
    name: str | None = None
    body: str


class UpdateCodexEntryRequest(BaseModel):
    """Body of ``PUT /api/books/{book_id}/codex/{entry_id}`` — a full-replace
    edit of an entry's content (UC-070).

    - ``name`` — optional; validated against the entry's **stored** kind.
    - ``body`` — the replacement content.
    - ``expected_modified_at`` — the ``modified_at`` the client loaded the entry
      at. A value that disagrees with the stored one is refused as stale (→ 409);
      ``kind`` is absent by design (not updatable).
    """

    name: str | None = None
    body: str
    expected_modified_at: datetime | None


class CodexEntryResponse(BaseModel):
    """A single codex entry as surfaced to a member (create / get / list /
    update results).

    Built by hand in the service mapper (never dumped from the ORM). Ids are
    ``str``. ``author_id`` is the **original creator** and never changes;
    ``modified_by`` is the author of the most recent edit (``null`` until the
    first one).
    """

    id: str
    book_id: str
    kind: CodexKind
    name: str | None
    body: str
    archived: bool
    author_id: str
    modified_by: str | None
    created_at: datetime | None
    modified_at: datetime | None


class CodexEntryListResponse(BaseModel):
    """List envelope for ``GET /api/books/{book_id}/codex`` — the book's entries
    matching the kind / needle / include-archived filters, name-ascending with
    unnamed rows last (UC-071)."""

    items: list[CodexEntryResponse]
