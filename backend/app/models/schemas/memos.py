"""Memo request & response schemas (feature 026, step 002).

Declarative Pydantic schemas — the typed contract for
``/api/books/{book_id}/memos`` (the route family is step 003). Plain typed data
shapes, no logic (see ``docs/architecture/backend.md`` — ``models/`` is tables
plus schemas only).

The field sets are fixed by ``docs/plans/026.memos/context.md`` → "The wire
contract":

- **Ids are ``str``** on the wire — snowflakes exceed the JS safe-integer range
  (the ``CodexEntryResponse`` / ``ChatResponse`` precedent).
- **No ``user_id`` field on the response.** A memo's subject is always the
  caller: the user id comes from ``BookAccess.user_id`` inside
  ``services/memos.py`` and never from an argument, a body field or a path
  segment. Echoing it here would invite the reading that another author's memo
  is addressable on this surface — nobody, **including the book's owner**, ever
  reads someone else's memo (``domain-book.md`` → ``## Memo``).
- **``body`` carries no constraint of any kind.** ``""`` is legitimate input and
  a legitimate stored value — a memo is created empty and typed into afterwards
  (UC-103). No ``min_length``, no ``strip_whitespace``, no validator: an empty
  body must never surface as a 422.
- **The update request carries the body and nothing else** — no
  ``expected_modified_at``, no ``409`` path (``context.md`` → decision 5), and
  no flag fields: ``active`` and ``archived`` are two independent axes with four
  verbs of their own (step 005), so the focus-loss ``PUT`` cannot write state it
  did not mean to.
- **No ordinal on the create request.** A new memo is appended at ``max + 1`` by
  the service; the client never chooses a position (``context.md`` →
  decision 2).

The **reorder** request (step 004) carries the **full ordered id list** and no
ordinals: positions are the server's to write (``1..N``), and a partial move is
not expressible on this wire.

Skeleton (026 steps 002 and 004): field names / types / defaults are frozen. DTOs
are declarative — there is nothing to leave unimplemented.
"""

from pydantic import BaseModel

from app.models.schemas.common import UtcDateTime


class CreateMemoRequest(BaseModel):
    """Body of ``POST /api/books/{book_id}/memos`` — a new memo for the caller.

    - ``body`` — **required**, unconstrained, and ``""`` is valid input: the
      normal shape of a freshly created memo is an empty one that the author
      then types into (UC-103). A body missing the field is a 422 at the schema
      boundary; a body holding ``""`` is a success.

    No ``ordinal``: the service appends the memo at one past the highest ordinal
    among the caller's non-archived memos in that book.
    """

    body: str


class UpdateMemoRequest(BaseModel):
    """Body of ``PUT /api/books/{book_id}/memos/{memo_id}`` — the memo's text,
    and nothing else (UC-104, US-125.AC-1).

    - ``body`` — **required**, unconstrained; ``""`` clears the memo's text and
      is not a validation failure. There is no DELETE verb at any layer
      (``context.md`` → decision 6): an emptied memo is still a memo.

    Deliberately carries **no version token** (one writer, saved within moments
    of being typed — ``context.md`` → decision 5) and **no ``active`` /
    ``archived`` flags (each axis has its own verb pair — step 005).
    """

    body: str


class ReorderMemosRequest(BaseModel):
    """Body of ``PUT /api/books/{book_id}/memos/order`` — the **full** ordered id
    list of the caller's non-archived memos (UC-106, US-126.AC-2).

    - ``memo_ids`` — ``str`` ids in their intended order. The server rewrites
      ordinals ``1..N`` from their **positions**, so the request carries **no
      ordinals**: the ``1..N`` rule is the service's (``context.md`` →
      decision 2), never the client's to assert.
    - **The whole set, never a partial move.** There is no "move this memo to
      position k" shape here: the list must be exactly the caller's non-archived
      memos for this book, each exactly once. Archived memos are deliberately
      outside it — archiving leaves a gap and never renumbers, and a reorder does
      not reclaim it (``004.context.md`` → "Which rows are 'the current set'").

    A list that is not exactly that set — a different length, a duplicate, or any
    id not in it (an unknown id, an archived memo's id, another author's memo,
    another book's memo) — is refused by the **service** as **one** reason. The
    body is structurally valid, so that refusal is a ``400``, not a framework
    ``422``, and the single reason keeps the existence-hiding property: the shape
    of the refusal never tells a caller whether some id exists.
    """

    memo_ids: list[str]


class MemoResponse(BaseModel):
    """A single memo as surfaced to its author (create / list / update /
    state-verb results).

    Built by hand in the service mapper (never dumped from the ORM).

    - ``id`` / ``book_id`` — stringified snowflakes.
    - ``body`` — the stored text; ``""`` is a real value, never an absence.
    - ``ordinal`` — the memo's position in its author's working list for this
      book. Archiving leaves a gap and never renumbers, so the ordinals of a
      returned list are ascending but not necessarily contiguous.
    - ``active`` — the author's on/off switch: an inactive memo is still listed,
      it simply does not reach the assistant.
    - ``archived`` — the put-away axis, independent of ``active``. The two flags
      are what lets a restore return the memo in the state its author chose.
    - ``created_at`` / ``modified_at`` — the stored stamps, nullable because the
      columns are (the service stamps both on create).

    Deliberately carries **no user identifier** and no field a caller could vary
    to reach another author's memo.
    """

    id: str
    book_id: str
    body: str
    ordinal: int
    active: bool
    archived: bool
    created_at: UtcDateTime | None
    modified_at: UtcDateTime | None


class MemoListResponse(BaseModel):
    """List envelope for ``GET /api/books/{book_id}/memos`` and for the reorder
    result (step 004) — **the caller's own** memos for the book, ordinal
    ascending (US-131.AC-2), archived rows excluded unless asked for
    (US-128.AC-1 / US-128.AC-2)."""

    items: list[MemoResponse]
