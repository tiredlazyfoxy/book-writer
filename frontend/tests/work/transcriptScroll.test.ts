/**
 * The transcript's pure scroll geometry — fast/010.transcript-autoscroll,
 * DoD-1 … DoD-4.
 *
 * Bound to the frozen signatures in status.md -> `## Skeleton`:
 *   TRANSCRIPT_PIN_THRESHOLD_PX: number
 *   isTranscriptPinned(scrollTop, scrollHeight, clientHeight): boolean
 *   transcriptBottomScrollTop(scrollHeight, clientHeight): number
 *
 * NOTE THE TWO DIFFERENT ARGUMENT ORDERS — the predicate takes
 * `(scrollTop, scrollHeight, clientHeight)`, the bottom helper takes
 * `(scrollHeight, clientHeight)`. Both are frozen.
 *
 * Every expected value comes from `plan.md` -> Definition of done and Interface
 * intent, never from code:
 *   - the threshold is the user-locked literal `64` (DoD-1);
 *   - the pin distance is `scrollHeight − clientHeight − scrollTop` and the
 *     boundary is INCLUSIVE — exactly 64 is pinned, 65 is not (DoD-2);
 *   - degenerate input resolves to PINNED, never to unpinned, because the failure
 *     mode of a wrong `true` is one unwanted scroll while the failure mode of a
 *     wrong `false` is a feature that looks broken (DoD-3);
 *   - the bottom position is `scrollHeight − clientHeight` floored at 0, and a
 *     non-finite argument yields 0 (DoD-4).
 *
 * This module is pure by design: no DOM, no MobX, no rendering, no mocks — which
 * is the only way the 64px contract can be verified at all, jsdom having no
 * layout engine. `globals: false`.
 */
import { describe, expect, it } from "vitest";
import {
  TRANSCRIPT_PIN_THRESHOLD_PX,
  isTranscriptPinned,
  transcriptBottomScrollTop,
} from "../../src/work/components/chat/transcriptScroll";

/** The spec's worked example: a 2000px transcript in a 500px viewport. */
const SCROLL_HEIGHT = 2000;
const CLIENT_HEIGHT = 500;
/** ...so the bottom sits at scrollTop 1500. */
const BOTTOM = 1500;

describe("the pin threshold constant (DoD-1)", () => {
  it("DoD-1: TRANSCRIPT_PIN_THRESHOLD_PX is exactly 64", () => {
    // The user-locked value — roughly one line of prose of slack. Not ~0
    // (brittle against fractional scroll heights) and not ~200 (would override a
    // deliberate scroll back).
    expect(TRANSCRIPT_PIN_THRESHOLD_PX).toBe(64);
  });
});

describe("the pinned predicate answers on both sides of an INCLUSIVE threshold (DoD-2)", () => {
  it("DoD-2: sitting exactly at the bottom is pinned", () => {
    expect(isTranscriptPinned(BOTTOM, SCROLL_HEIGHT, CLIENT_HEIGHT)).toBe(true);
  });

  it("DoD-2: a distance of exactly 64 is pinned — the boundary is inclusive", () => {
    // 2000 − 500 − 1436 = 64.
    expect(isTranscriptPinned(1436, SCROLL_HEIGHT, CLIENT_HEIGHT)).toBe(true);
  });

  it("DoD-2: a distance of 65 is NOT pinned — one pixel past the boundary", () => {
    // 2000 − 500 − 1435 = 65.
    expect(isTranscriptPinned(1435, SCROLL_HEIGHT, CLIENT_HEIGHT)).toBe(false);
  });

  it("DoD-2: sitting at the very top is NOT pinned", () => {
    expect(isTranscriptPinned(0, SCROLL_HEIGHT, CLIENT_HEIGHT)).toBe(false);
  });
});

describe("degenerate geometry resolves to PINNED, never to unpinned (DoD-3)", () => {
  // A non-finite value in ANY of the three arguments. Enumerated one argument at
  // a time so a partial guard (only checking scrollTop, say) fails here.
  const nonFinite: readonly number[] = [Number.NaN, Number.POSITIVE_INFINITY, Number.NEGATIVE_INFINITY];

  for (const value of nonFinite) {
    it(`DoD-3: scrollTop of ${String(value)} is pinned`, () => {
      expect(isTranscriptPinned(value, SCROLL_HEIGHT, CLIENT_HEIGHT)).toBe(true);
    });

    it(`DoD-3: scrollHeight of ${String(value)} is pinned`, () => {
      expect(isTranscriptPinned(0, value, CLIENT_HEIGHT)).toBe(true);
    });

    it(`DoD-3: clientHeight of ${String(value)} is pinned`, () => {
      expect(isTranscriptPinned(0, SCROLL_HEIGHT, value)).toBe(true);
    });
  }

  it("DoD-3: all three zero — jsdom's real, layout-free geometry — is pinned", () => {
    // The correct default for a fresh pane: an unreadable measurement must not
    // strand the author away from a reply that is streaming in.
    expect(isTranscriptPinned(0, 0, 0)).toBe(true);
  });

  it("DoD-3: a viewport taller than its content has nothing to scroll and is pinned", () => {
    expect(isTranscriptPinned(0, 300, CLIENT_HEIGHT)).toBe(true);
  });
});

describe("the bottom-position helper (DoD-4)", () => {
  it("DoD-4: (2000, 500) is 1500", () => {
    expect(transcriptBottomScrollTop(SCROLL_HEIGHT, CLIENT_HEIGHT)).toBe(BOTTOM);
  });

  it("DoD-4: a viewport as tall as its content yields 0", () => {
    expect(transcriptBottomScrollTop(500, 500)).toBe(0);
  });

  it("DoD-4: a viewport taller than its content yields 0, never a negative scrollTop", () => {
    expect(transcriptBottomScrollTop(300, 500)).toBe(0);
  });

  it("DoD-4: a non-finite scrollHeight yields 0", () => {
    expect(transcriptBottomScrollTop(Number.NaN, CLIENT_HEIGHT)).toBe(0);
    expect(transcriptBottomScrollTop(Number.POSITIVE_INFINITY, CLIENT_HEIGHT)).toBe(0);
  });

  it("DoD-4: a non-finite clientHeight yields 0", () => {
    expect(transcriptBottomScrollTop(SCROLL_HEIGHT, Number.NaN)).toBe(0);
    expect(transcriptBottomScrollTop(SCROLL_HEIGHT, Number.NEGATIVE_INFINITY)).toBe(0);
  });
});
