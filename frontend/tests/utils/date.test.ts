import { describe, expect, it } from "vitest";
import { formatDate } from "../../src/utils/date";

/**
 * The shared timestamp renderer. Asserts the FORMAT contract the UI depends on —
 * `YYYY-MM-DD HH:MM UTC`, locale-independent — plus the two fallback branches
 * carried over from the three page-local helpers it replaced.
 */
describe("formatDate", () => {
  it("renders a UTC stamp in ISO field order, to the minute", () => {
    expect(formatDate("2026-09-14T15:04:00Z")).toBe("2026-09-14 15:04 UTC");
  });

  it("converts an offset stamp to the same UTC instant", () => {
    // 17:04+02:00 IS 15:04Z — the rendered string must not vary with the offset
    // the wire happened to use.
    expect(formatDate("2026-09-14T17:04:00+02:00")).toBe("2026-09-14 15:04 UTC");
  });

  it("does not shift with the viewer's local timezone", () => {
    // The output is derived from toISOString(), never from local getters, so it
    // is identical on every machine. A local-time render would differ here.
    expect(formatDate("2026-01-01T00:30:00Z")).toBe("2026-01-01 00:30 UTC");
  });

  it("drops seconds rather than rounding them", () => {
    expect(formatDate("2026-09-14T15:04:59Z")).toBe("2026-09-14 15:04 UTC");
  });

  it("renders an em dash when the stamp is absent", () => {
    expect(formatDate(null)).toBe("—");
    expect(formatDate(undefined)).toBe("—");
    expect(formatDate("")).toBe("—");
  });

  it("echoes an unparseable string back instead of 'Invalid Date'", () => {
    expect(formatDate("not-a-date")).toBe("not-a-date");
  });
});
