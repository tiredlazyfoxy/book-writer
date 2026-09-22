import type { ISODateString } from "../types/common";

/**
 * Render a backend timestamp for display as `YYYY-MM-DD HH:MM UTC`.
 *
 * ISO field order, locale-independent, sorts lexicographically, and the zone is
 * named so a reader never has to guess whose clock a bare stamp belongs to. The
 * backend guarantees an explicit UTC designator on the wire (see
 * `app/models/schemas/common.py` — `UtcDateTime`), so the instant is read, not
 * assumed.
 *
 * Absent → an em dash. Unparseable → the raw string echoed back, which surfaces
 * a wire-shape problem instead of hiding it behind "Invalid Date".
 */
export function formatDate(value: ISODateString | null | undefined): string {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  const iso = parsed.toISOString(); // 2026-09-14T15:04:00.000Z
  return `${iso.slice(0, 10)} ${iso.slice(11, 16)} UTC`;
}
