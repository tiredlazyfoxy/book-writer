"""Reader-surface request & response schemas (feature 022, UC-029 / US-030).

Declarative Pydantic schemas — the typed contracts for everything ACT-006 (a
logged-in non-member) can reach: the reader-safe book projection, the reader-safe
chapter body, and the public-book discovery list. Plain typed data shapes, no
logic (see ``docs/architecture/backend.md`` — ``models/`` is tables + schemas
only).

**Why a module of its own** (decision D3): UC-029 is an *exclusion list*, and
"what can a reader reach?" must be answerable by reading two files
(``models/schemas/reader.py`` + ``services/reader.py``), not by auditing a
twelve-route book module. Every exclusion here is **structural** — a separate DTO
rather than a filtered :class:`~app.models.schemas.books.BookResponse` — so a
field cannot leak by someone forgetting a filter.

:class:`ReaderBookResponse` **moved here** from ``models/schemas/books.py``
(feature 009, step 004) and its ``chapters`` field widened from ``list[str]`` to
``list[ReaderChapterRef]`` (D4): the reader needs chapter **ids** to follow a
link, and the old placeholder carried none. The widening breaks zero consumers —
no frontend type or call site for the old shape ever existed.

Ids are surfaced as ``str`` (snowflake serialized as a string — 64-bit ids exceed
the JS safe-integer range), matching every other id-bearing field in the schema
layer.

Skeleton (feature 022): field names/types are frozen; these are declarations, so
there is nothing left unimplemented here.
"""

from pydantic import BaseModel


class ReaderChapterRef(BaseModel):
    """One table-of-contents entry — the *only* chapter facts a reader gets
    before opening a chapter.

    Exactly ``id`` + ``title``. Deliberately absent, and structurally so:
    ``sketch`` and ``summary`` (author working material), ``state`` and
    ``ordinal`` (the author's skeleton — ordering is expressed by the list order
    instead), ``book_id`` and ``version``. Contrast
    :class:`~app.models.schemas.chapters.ChapterResponse`, which carries all of
    them and must never reach a reader.
    """

    id: str
    title: str


class ReaderBookResponse(BaseModel):
    """Reader-safe book projection (``GET /api/books/{book_id}/read``).

    Exactly ``title`` + ``chapters``. Carries **none** of the members-only
    surface — no members, owner id, book id, description, codex, notes, book
    state, visibility, collaboration mode, settings, ``system_prompt``,
    timestamps or any mutation-bearing field (UC-029 exclusion list). The
    exclusion is enforced by this being a separate DTO, not a filtered
    :class:`~app.models.schemas.books.BookDetailResponse`.

    ``chapters`` carries only the reader-visible chapters
    (``services.reader.READER_VISIBLE_STATES``), in ascending ``ordinal`` order —
    the ordinal itself is not on the wire, the list order *is* the reading order
    (US-030.AC-1).

    ``system_prompt`` is doubly excluded (feature 021): beyond the reader
    exclusion list there is no book-wide prompt left to project — the prompt is
    **per-author** and lives on its own members-only endpoint.
    """

    title: str
    chapters: list[ReaderChapterRef]


class ReaderChapterResponse(BaseModel):
    """Reader-safe chapter body (``GET /api/books/{book_id}/read/chapters/{id}``).

    Exactly ``id`` + ``title`` + ``text``. A purpose-built DTO rather than a
    reuse of :class:`~app.models.schemas.chapters.ChapterTextResponse` (which
    carries no title, plus ``state`` and ``version``) or
    :class:`~app.models.schemas.chapters.ChapterResponse` (which leaks ``sketch``
    and ``summary``) — decision D4. ``state`` is deliberately absent: which of the
    reader-visible states a chapter is in is the author's business.
    """

    id: str
    title: str
    text: str


class PublicBookRef(BaseModel):
    """One row of the public-book discovery list (``GET /api/books/public``).

    Exactly ``id`` + ``title`` + ``description`` — enough to recognize a book and
    open it. Deliberately absent (D14): ``owner_id`` (and any owner display
    name — a question nobody has asked), ``visibility`` (every row is public by
    construction), ``state`` (every row is active by construction),
    ``collaboration_mode`` (an authoring concern) and both timestamps.
    """

    id: str
    title: str
    description: str


class PublicBookListResponse(BaseModel):
    """List envelope for ``GET /api/books/public``.

    Mirrors :class:`~app.models.schemas.books.BookListResponse`'s ``items``
    envelope shape so the three bookshelf sections read alike client-side, while
    carrying the narrower :class:`PublicBookRef` row.
    """

    items: list[PublicBookRef]
