"""Shared schema primitives — annotated types every response schema reuses.

Plain typed data shapes, no logic (see ``docs/architecture/backend.md`` —
``models/`` is tables + schemas only).
"""

from datetime import datetime, timezone
from typing import Annotated

from pydantic import PlainSerializer


def _as_utc(value: datetime) -> datetime:
    """Normalize a stored timestamp to an **aware UTC** value for the wire.

    Services always write ``datetime.now(timezone.utc)``, but the SQLite columns
    carry no ``timezone=True``, so a value read back from the database comes home
    tz-naive — the same instant, just unlabelled. Attaching UTC is therefore a
    restoration, not a guess. An already-aware value (one returned in the same
    request that created it) is converted rather than stamped.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


#: A response-schema timestamp. Serializes with an explicit UTC designator so the
#: frontend never has to guess whose clock an unlabelled stamp belongs to — JS
#: parses a tz-less ISO string as LOCAL time, which silently shifts every
#: rendered instant by the viewer's offset.
#:
#: ``when_used="json-unless-none"`` confines the conversion to JSON dumps: an
#: in-process ``model_dump()`` still yields a real ``datetime``. ``return_type``
#: stays ``datetime`` so Pydantic does the formatting and the OpenAPI
#: ``format: date-time`` survives.
UtcDateTime = Annotated[
    datetime,
    PlainSerializer(_as_utc, return_type=datetime, when_used="json-unless-none"),
]
