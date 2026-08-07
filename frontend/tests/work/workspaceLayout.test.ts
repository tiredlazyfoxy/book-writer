/**
 * Workspace layout preference — fast/005.workspace-layout, DoD-1 … DoD-7.
 *
 * Bound to the frozen signatures in status.md -> `## Skeleton` (fast/005):
 *   const WORKSPACE_LAYOUT_KEY = "bookwriter.workspace-layout"
 *   const CHAT_WIDTH_CSS_VAR   = "--work-chat-width"
 *   const DEFAULT_CHAT_WIDTH_FRACTION / MIN_ / MAX_ / CHAT_WIDTH_KEYBOARD_STEP
 *   interface WorkspaceLayout { navCollapsed: boolean; chatWidth: number }
 *   clampChatWidth(fraction: number): number
 *   chatWidthFromPointer(clientX: number, viewportWidth: number): number
 *   chatWidthCss(fraction: number): string
 *   readWorkspaceLayout(): WorkspaceLayout
 *   writeWorkspaceLayout(layout: WorkspaceLayout): void
 *
 * Every expected value comes from `plan.md` -> Definition of done and Interface
 * intent, never from code:
 *   - defaults are `navCollapsed: false` / `chatWidth: 0.35`, bounds `[0.15, 0.6]`,
 *     keyboard step `0.02` (DoD-1);
 *   - one global key, written once per write (DoD-2);
 *   - the read is TOTAL — garbage of every shape resolves to defaults and never
 *     throws (DoD-3) — and its fallback is PER FIELD (DoD-4);
 *   - the width is clamped on read and by `clampChatWidth`, with a non-finite input
 *     yielding the default rather than a bound (DoD-5);
 *   - the drag geometry is right-anchored and clamped (DoD-6) — this is the drag's
 *     entire geometry, verified with no DOM, because jsdom has no layout engine;
 *   - the CSS length rounds to two decimals so a nudged value emits no float
 *     noise (DoD-7).
 *
 * A pure module in the `activeChat.ts` / `restoreBuffer.ts` tier: no class, no MobX,
 * no DOM, no render. `tests/setup.ts` runs `localStorage.clear()` in `afterEach`, so
 * each case starts on a clean store. `globals: false`.
 */
import { describe, expect, it } from "vitest";
import {
  CHAT_WIDTH_CSS_VAR,
  CHAT_WIDTH_KEYBOARD_STEP,
  DEFAULT_CHAT_WIDTH_FRACTION,
  MAX_CHAT_WIDTH_FRACTION,
  MIN_CHAT_WIDTH_FRACTION,
  WORKSPACE_LAYOUT_KEY,
  chatWidthCss,
  chatWidthFromPointer,
  clampChatWidth,
  readWorkspaceLayout,
  writeWorkspaceLayout,
} from "../../src/work/workspaceLayout";

/** Every key currently present in localStorage. */
function storedKeys(): string[] {
  const keys: string[] = [];
  for (let i = 0; i < localStorage.length; i += 1) {
    const key = localStorage.key(i);
    if (key !== null) {
      keys.push(key);
    }
  }
  return keys;
}

describe("defaults and constants (DoD-1)", () => {
  it("DoD-1: with empty storage the layout reads back as the documented defaults", () => {
    expect(readWorkspaceLayout()).toEqual({ navCollapsed: false, chatWidth: 0.35 });
  });

  it("DoD-1: the exported constants carry exactly the contracted literals", () => {
    expect(WORKSPACE_LAYOUT_KEY).toBe("bookwriter.workspace-layout");
    expect(CHAT_WIDTH_CSS_VAR).toBe("--work-chat-width");
    expect(DEFAULT_CHAT_WIDTH_FRACTION).toBe(0.35);
    expect(MIN_CHAT_WIDTH_FRACTION).toBe(0.15);
    expect(MAX_CHAT_WIDTH_FRACTION).toBe(0.6);
    expect(CHAT_WIDTH_KEYBOARD_STEP).toBe(0.02);
  });
});

describe("write / read round-trip under one global key (DoD-2)", () => {
  it("DoD-2: a written record round-trips both fields", () => {
    writeWorkspaceLayout({ navCollapsed: true, chatWidth: 0.5 });

    expect(readWorkspaceLayout()).toEqual({ navCollapsed: true, chatWidth: 0.5 });
  });

  it("DoD-2: a write touches exactly one storage key, and it is WORKSPACE_LAYOUT_KEY", () => {
    writeWorkspaceLayout({ navCollapsed: false, chatWidth: 0.42 });

    // One global key for the whole workspace — deliberately not per book.
    expect(storedKeys()).toEqual([WORKSPACE_LAYOUT_KEY]);
  });
});

describe("the read is total (DoD-3)", () => {
  const GARBAGE: Array<[string, string]> = [
    ["not JSON at all", "not json"],
    ["a JSON null", "null"],
    ["a JSON array", "[]"],
    ["a bare JSON string", '"str"'],
    ["a bare JSON number", "42"],
    ["an empty JSON object", "{}"],
    [
      "an object with wrong-typed fields",
      JSON.stringify({ navCollapsed: "yes", chatWidth: "wide" }),
    ],
  ];

  for (const [description, raw] of GARBAGE) {
    it(`DoD-3: ${description} reads back as the defaults without throwing`, () => {
      // Plant the value at the module's own key, bypassing the writer.
      localStorage.setItem(WORKSPACE_LAYOUT_KEY, raw);

      expect(() => readWorkspaceLayout()).not.toThrow();
      expect(readWorkspaceLayout()).toEqual({ navCollapsed: false, chatWidth: 0.35 });
    });
  }
});

describe("the fallback is per field (DoD-4)", () => {
  it("DoD-4: a valid navCollapsed beside a garbage chatWidth keeps the boolean and defaults the number", () => {
    localStorage.setItem(WORKSPACE_LAYOUT_KEY, '{"navCollapsed":true,"chatWidth":"wide"}');

    expect(readWorkspaceLayout()).toEqual({ navCollapsed: true, chatWidth: 0.35 });
  });
});

describe("clamping (DoD-5)", () => {
  it("DoD-5: chatWidth is clamped on read — above the max, below the min", () => {
    localStorage.setItem(WORKSPACE_LAYOUT_KEY, '{"navCollapsed":false,"chatWidth":0.95}');
    expect(readWorkspaceLayout().chatWidth).toBe(0.6);

    localStorage.setItem(WORKSPACE_LAYOUT_KEY, '{"navCollapsed":false,"chatWidth":0.01}');
    expect(readWorkspaceLayout().chatWidth).toBe(0.15);
  });

  it("DoD-5: a non-finite stored chatWidth reads back as the default, not as a bound", () => {
    // JSON has no NaN/Infinity literal, so both arrive as the strings JSON.stringify
    // would never emit — planted raw, exactly as a corrupted store would hold them.
    localStorage.setItem(WORKSPACE_LAYOUT_KEY, '{"navCollapsed":false,"chatWidth":NaN}');
    expect(readWorkspaceLayout().chatWidth).toBe(0.35);

    localStorage.setItem(WORKSPACE_LAYOUT_KEY, '{"navCollapsed":false,"chatWidth":Infinity}');
    expect(readWorkspaceLayout().chatWidth).toBe(0.35);
  });

  it("DoD-5: clampChatWidth passes the two bounds through unchanged", () => {
    expect(clampChatWidth(0.15)).toBe(0.15);
    expect(clampChatWidth(0.6)).toBe(0.6);
  });

  it("DoD-5: clampChatWidth bounds out-of-range input and defaults non-finite input", () => {
    expect(clampChatWidth(0.95)).toBe(0.6);
    expect(clampChatWidth(0.01)).toBe(0.15);
    expect(clampChatWidth(Number.NaN)).toBe(0.35);
    expect(clampChatWidth(Number.POSITIVE_INFINITY)).toBe(0.35);
    expect(clampChatWidth(Number.NEGATIVE_INFINITY)).toBe(0.35);
  });
});

describe("pointer geometry (DoD-6)", () => {
  it("DoD-6: the fraction is the distance from the pointer to the RIGHT edge over the viewport width", () => {
    // Right-anchored pane: (1000 - 700) / 1000.
    expect(chatWidthFromPointer(700, 1000)).toBeCloseTo(0.3, 10);
  });

  it("DoD-6: the pointer fraction is clamped at both bounds", () => {
    // 0.9 -> the max; 0.01 -> the min.
    expect(chatWidthFromPointer(100, 1000)).toBeCloseTo(0.6, 10);
    expect(chatWidthFromPointer(990, 1000)).toBeCloseTo(0.15, 10);
  });

  it("DoD-6: a non-positive viewport width yields the default", () => {
    expect(chatWidthFromPointer(500, 0)).toBeCloseTo(0.35, 10);
  });
});

describe("the CSS length (DoD-7)", () => {
  it("DoD-7: the default fraction becomes exactly 35vw", () => {
    expect(chatWidthCss(0.35)).toBe("35vw");
  });

  it("DoD-7: a keyboard-nudged fraction emits no float noise", () => {
    const nudged = DEFAULT_CHAT_WIDTH_FRACTION + CHAT_WIDTH_KEYBOARD_STEP;

    expect(chatWidthCss(nudged)).toBe("37vw");
    // Two decimal places at most — never "35.000000000000004vw".
    expect(chatWidthCss(nudged)).toMatch(/^\d+(\.\d{1,2})?vw$/);
  });

  it("DoD-7: repeated keyboard nudging never accumulates float noise in the emitted length", () => {
    let fraction = DEFAULT_CHAT_WIDTH_FRACTION;
    for (let i = 0; i < 5; i += 1) {
      fraction += CHAT_WIDTH_KEYBOARD_STEP;
      expect(chatWidthCss(fraction)).toMatch(/^\d+(\.\d{1,2})?vw$/);
    }
    expect(chatWidthCss(fraction)).toBe("45vw");
  });
});
