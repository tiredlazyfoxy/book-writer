"""Per-author **chapter** system-prompt request & response schemas (feature 014,
step 004).

Declarative Pydantic schemas — the typed contract for
``/api/books/{book_id}/chapters/{chapter_id}/system-prompt``. Plain typed data
shapes, no logic (see ``docs/architecture/backend.md`` — ``models/`` is tables +
schemas only). The chapter-level mirror of
``models/schemas/book_author_prompts.py`` (feature 021).

The field sets are fixed by ``docs/plans/014.chapter-skeleton/context.md`` → "The
wire contract" → "Chapter-prompt DTOs":

- **Ids are ``str``** on the wire — snowflakes exceed the JS safe-integer range
  (``ChapterResponse.id`` / ``BookAuthorPromptResponse.book_id`` precedent).
- **No ``user_id`` field.** The prompt is always the caller's own: the user id
  comes from ``BookAccess.user_id`` inside the service and never from an argument
  or a path segment. Echoing it would invite the belief that the endpoint can
  serve another author's prompt.
- ``system_prompt`` is **never nullable**. ``""`` is the value meaning "this
  author has no prompt"; it is a real value, not an absence, both on the wire and
  in storage.
- ``modified_at`` **is** nullable — ``None`` is how "this author has no row yet"
  is distinguished from "this author cleared their prompt" (which carries a real
  timestamp and an empty ``system_prompt``).

Skeleton (014 step 004): field names / types / defaults are frozen. DTOs are
declarative — there is nothing to leave unimplemented.
"""

from datetime import datetime

from pydantic import BaseModel


class UpdateChapterAuthorPromptRequest(BaseModel):
    """Body of ``PUT /api/books/{book_id}/chapters/{chapter_id}/system-prompt``
    — the caller's own prompt text for that chapter and nothing else.

    - ``system_prompt`` — **required**, and ``""`` is valid input: an empty
      string is how an author clears their prompt (``context.md`` → the wire
      contract — there is no DELETE verb on this path). A body missing the field
      is a 422 at the schema boundary, not a silent no-op.
    """

    system_prompt: str


class ChapterAuthorPromptResponse(BaseModel):
    """Response body for **both** verbs of
    ``/api/books/{book_id}/chapters/{chapter_id}/system-prompt``.

    - ``chapter_id`` — the chapter the prompt belongs to, stringified.
    - ``system_prompt`` — the caller's stored text; ``""`` when the author has no
      prompt (whether because no row exists yet or because they cleared it).
    - ``modified_at`` — the stored row's last-modified timestamp, or ``None``
      when the author has no row yet. This is the **only** field that separates
      "never written" from "written, then cleared".

    Deliberately carries **no user identifier** and no field a caller could vary
    to reach another author's prompt.
    """

    chapter_id: str
    system_prompt: str
    modified_at: datetime | None
