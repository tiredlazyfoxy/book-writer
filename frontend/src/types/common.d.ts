// Shared wire DTO seed — pure shapes matching backend JSON 1:1. No methods, no classes.
// Resource-specific DTOs live in their own `types/<resource>.d.ts`.

/** FastAPI error body — `{ "detail": "..." }`. Source for the `ApiError` message. */
export interface ApiErrorBody {
  detail?: string;
}

/**
 * ISO-8601 timestamp string as serialized by the backend (e.g. "2026-07-21T12:00:00Z").
 *
 * ALWAYS carries an explicit UTC designator — `app/models/schemas/common.py`
 * `UtcDateTime` guarantees it, because SQLite returns stamps tz-naive and JS
 * parses a tz-less ISO string as LOCAL time. Render it with `utils/date.ts`
 * `formatDate`, never with `toLocaleString()`.
 */
export type ISODateString = string;
