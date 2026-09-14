/**
 * Workspace layout preference — fast/005.workspace-layout (DoD-1 … DoD-7) and
 * fast/008.composer-resize (DoD-1 … DoD-6).
 *
 * TWO GENERATIONS OF DoD IDS LIVE IN THIS FILE. The cases under the
 * "chat width / the read is total / the CSS length" describes carry
 * **fast/005**'s ids; every case whose name mentions the **composer** carries
 * **fast/008**'s. The 005 cases are extended here — never weakened — because
 * `WorkspaceLayout` gained a third field (`composerHeight`) and the writer became
 * a partial patch, so every total-record assertion now names three fields.
 *
 * fast/008 bindings, from status.md -> `## Skeleton`:
 *   const MIN_COMPOSER_HEIGHT_PX / DEFAULT_COMPOSER_HEIGHT_PX
 *   const MAX_COMPOSER_HEIGHT_FRACTION / COMPOSER_HEIGHT_KEYBOARD_STEP
 *   interface WorkspaceLayout { navCollapsed: boolean; chatWidth: number;
 *                               composerHeight: number }   // composerHeight is PIXELS
 *   clampComposerHeight(candidate: number, viewportHeight: number): number
 *   composerHeightFromDrag(startHeight: number, startY: number, clientY: number,
 *                          viewportHeight: number): number
 *   readWorkspaceLayout(): WorkspaceLayout
 *   writeWorkspaceLayout(patch: Partial<WorkspaceLayout>): void
 *
 * Every fast/008 expected value comes from `plan.md` -> Definition of done and
 * Interface intent, never from code:
 *   - the literals are 64 / 96 / 0.5 / 24 and the key is unchanged (008 DoD-1);
 *   - the drag geometry is DELTA-based and directional — upward grows (008 DoD-2)
 *     — and clamped at both ends (008 DoD-3);
 *   - the clamp's floor is always the minimum, its ceiling is
 *     `0.5 × viewportHeight` EXCEPT when that product falls below the minimum, in
 *     which case the minimum wins; a nonsense viewport means "ceiling unknown", so
 *     only the floor applies (008 DoD-4);
 *   - the writer MERGES a partial patch over the read record, so two owners of one
 *     key cannot clobber each other (008 DoD-5);
 *   - the read clamps `composerHeight` to the MINIMUM ONLY — the viewport-dependent
 *     maximum is applied at use, not at read, because this function stays DOM-free
 *     (008 DoD-6).
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
  COMPOSER_HEIGHT_KEYBOARD_STEP,
  DEFAULT_CHAT_WIDTH_FRACTION,
  DEFAULT_COMPOSER_HEIGHT_PX,
  MAX_CHAT_WIDTH_FRACTION,
  MAX_COMPOSER_HEIGHT_FRACTION,
  MIN_CHAT_WIDTH_FRACTION,
  MIN_COMPOSER_HEIGHT_PX,
  WORKSPACE_LAYOUT_KEY,
  chatWidthCss,
  chatWidthFromPointer,
  clampChatWidth,
  clampComposerHeight,
  composerHeightFromDrag,
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
    // Three fields since fast/008: the composer height defaults to 96px.
    expect(readWorkspaceLayout()).toEqual({
      navCollapsed: false,
      chatWidth: 0.35,
      composerHeight: 96,
    });
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

    // The shell's two fields round-trip; the untouched third field defaults.
    expect(readWorkspaceLayout()).toEqual({
      navCollapsed: true,
      chatWidth: 0.5,
      composerHeight: 96,
    });
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
      JSON.stringify({ navCollapsed: "yes", chatWidth: "wide", composerHeight: "tall" }),
    ],
  ];

  for (const [description, raw] of GARBAGE) {
    it(`DoD-3: ${description} reads back as the defaults without throwing`, () => {
      // Plant the value at the module's own key, bypassing the writer.
      localStorage.setItem(WORKSPACE_LAYOUT_KEY, raw);

      expect(() => readWorkspaceLayout()).not.toThrow();
      expect(readWorkspaceLayout()).toEqual({
        navCollapsed: false,
        chatWidth: 0.35,
        composerHeight: 96,
      });
    });
  }
});

describe("the fallback is per field (DoD-4)", () => {
  it("DoD-4: a valid navCollapsed beside a garbage chatWidth keeps the boolean and defaults the number", () => {
    localStorage.setItem(WORKSPACE_LAYOUT_KEY, '{"navCollapsed":true,"chatWidth":"wide"}');

    expect(readWorkspaceLayout()).toEqual({
      navCollapsed: true,
      chatWidth: 0.35,
      composerHeight: 96,
    });
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

// ---------------------------------------------------------------------------
// fast/008.composer-resize — DoD-1 … DoD-6. Ids below belong to fast/008.
// ---------------------------------------------------------------------------

describe("the composer constants (DoD-1)", () => {
  it("DoD-1: the new composer constants carry exactly the contracted literals", () => {
    expect(MIN_COMPOSER_HEIGHT_PX).toBe(64);
    expect(DEFAULT_COMPOSER_HEIGHT_PX).toBe(96);
    expect(MAX_COMPOSER_HEIGHT_FRACTION).toBe(0.5);
    expect(COMPOSER_HEIGHT_KEYBOARD_STEP).toBe(24);
  });

  it("DoD-1: the storage key is still the single workspace-layout key", () => {
    // A third field joins the record — it does NOT get a key of its own.
    expect(WORKSPACE_LAYOUT_KEY).toBe("bookwriter.workspace-layout");
  });
});

describe("the composer drag geometry is delta-based and directional (DoD-2)", () => {
  // Viewport 800 -> maximum 400. Start: 200px tall, pointer down at clientY 500.
  it("DoD-2: dragging UPWARD grows the composer by the pointer's delta", () => {
    // 200 + (500 - 400) = 300.
    expect(composerHeightFromDrag(200, 500, 400, 800)).toBe(300);
  });

  it("DoD-2: dragging DOWNWARD shrinks the composer by the pointer's delta", () => {
    // 200 + (500 - 600) = 100.
    expect(composerHeightFromDrag(200, 500, 600, 800)).toBe(100);
  });
});

describe("the composer drag geometry is clamped at both ends (DoD-3)", () => {
  it("DoD-3: an upward drag past half the viewport stops at the maximum", () => {
    // 200 + (500 - 100) = 600 -> 0.5 * 800 = 400.
    expect(composerHeightFromDrag(200, 500, 100, 800)).toBe(400);
  });

  it("DoD-3: a downward drag past the floor stops at the minimum", () => {
    // 200 + (500 - 700) = 0 -> 64.
    expect(composerHeightFromDrag(200, 500, 700, 800)).toBe(64);
  });
});

describe("clampComposerHeight bounds a candidate against the viewport (DoD-4)", () => {
  it("DoD-4: anything below the minimum becomes the minimum", () => {
    expect(clampComposerHeight(10, 800)).toBe(64);
    expect(clampComposerHeight(0, 800)).toBe(64);
    expect(clampComposerHeight(-500, 800)).toBe(64);
  });

  it("DoD-4: anything above half the viewport becomes exactly that product", () => {
    expect(clampComposerHeight(1000, 800)).toBe(400);
    expect(clampComposerHeight(701, 1400)).toBe(700);
  });

  it("DoD-4: a non-finite candidate yields the default height", () => {
    expect(clampComposerHeight(Number.NaN, 800)).toBe(96);
    expect(clampComposerHeight(Number.POSITIVE_INFINITY, 800)).toBe(96);
    expect(clampComposerHeight(Number.NEGATIVE_INFINITY, 800)).toBe(96);
  });

  it("DoD-4: a nonsense viewport height clamps against the MINIMUM alone — a stored preference is not shrunk", () => {
    // Ceiling unknown: a large candidate passes straight through.
    expect(clampComposerHeight(1000, 0)).toBe(1000);
    expect(clampComposerHeight(1000, -800)).toBe(1000);
    expect(clampComposerHeight(1000, Number.NaN)).toBe(1000);
    expect(clampComposerHeight(1000, Number.POSITIVE_INFINITY)).toBe(1000);
    // The floor still applies.
    expect(clampComposerHeight(10, 0)).toBe(64);
  });

  it("DoD-4: on a very short viewport the MINIMUM wins over the computed maximum", () => {
    // 0.5 * 100 = 50, which is below the 64px floor: a composer thinner than two
    // lines is unusable, so the minimum wins.
    expect(clampComposerHeight(1000, 100)).toBe(64);
    expect(clampComposerHeight(10, 100)).toBe(64);
  });
});

describe("persistence is one key and a MERGING patch (DoD-5)", () => {
  it("DoD-5: all three fields round-trip through exactly one key, and it is WORKSPACE_LAYOUT_KEY", () => {
    writeWorkspaceLayout({ navCollapsed: true, chatWidth: 0.5, composerHeight: 150 });

    expect(readWorkspaceLayout()).toEqual({
      navCollapsed: true,
      chatWidth: 0.5,
      composerHeight: 150,
    });
    expect(storedKeys()).toEqual([WORKSPACE_LAYOUT_KEY]);
  });

  it("DoD-5: writing only composerHeight leaves a stored navCollapsed and chatWidth intact", () => {
    writeWorkspaceLayout({ navCollapsed: true, chatWidth: 0.5, composerHeight: 150 });

    // ChatPaneState's write — it holds neither of the shell's fields.
    writeWorkspaceLayout({ composerHeight: 200 });

    expect(readWorkspaceLayout()).toEqual({
      navCollapsed: true,
      chatWidth: 0.5,
      composerHeight: 200,
    });
    expect(storedKeys()).toEqual([WORKSPACE_LAYOUT_KEY]);
  });

  it("DoD-5: writing only the shell's pair leaves a stored composerHeight intact", () => {
    writeWorkspaceLayout({ navCollapsed: true, chatWidth: 0.5, composerHeight: 150 });

    // WorkspaceShellState's existing call shape — unchanged by this feature.
    writeWorkspaceLayout({ navCollapsed: false, chatWidth: 0.42 });

    expect(readWorkspaceLayout()).toEqual({
      navCollapsed: false,
      chatWidth: 0.42,
      composerHeight: 150,
    });
  });
});

describe("the read's per-field fallback across three fields (DoD-6)", () => {
  it("DoD-6: a MISSING composerHeight keeps the other two fields and defaults to 96", () => {
    localStorage.setItem(WORKSPACE_LAYOUT_KEY, '{"navCollapsed":true,"chatWidth":0.5}');

    expect(() => readWorkspaceLayout()).not.toThrow();
    expect(readWorkspaceLayout()).toEqual({
      navCollapsed: true,
      chatWidth: 0.5,
      composerHeight: 96,
    });
  });

  it("DoD-6: a GARBAGE composerHeight keeps the other two fields and defaults to 96", () => {
    localStorage.setItem(
      WORKSPACE_LAYOUT_KEY,
      '{"navCollapsed":true,"chatWidth":0.5,"composerHeight":"tall"}',
    );
    expect(() => readWorkspaceLayout()).not.toThrow();
    expect(readWorkspaceLayout()).toEqual({
      navCollapsed: true,
      chatWidth: 0.5,
      composerHeight: 96,
    });

    // `null` is JSON-legal and non-numeric: same per-field fallback.
    localStorage.setItem(
      WORKSPACE_LAYOUT_KEY,
      '{"navCollapsed":true,"chatWidth":0.5,"composerHeight":null}',
    );
    expect(readWorkspaceLayout()).toEqual({
      navCollapsed: true,
      chatWidth: 0.5,
      composerHeight: 96,
    });

    // NON-FINITE, expressed the only way JSON can express it: an exponent past
    // Number.MAX_VALUE parses to Infinity. (A bare `NaN` / `Infinity` token is not
    // JSON at all — such an entry is unparseable and falls under fast/005's
    // all-fields-default totality contract, asserted separately above.)
    localStorage.setItem(
      WORKSPACE_LAYOUT_KEY,
      '{"navCollapsed":true,"chatWidth":0.5,"composerHeight":1e999}',
    );
    expect(readWorkspaceLayout()).toEqual({
      navCollapsed: true,
      chatWidth: 0.5,
      composerHeight: 96,
    });
  });

  it("DoD-6: a stored height below the floor reads back clamped to the minimum", () => {
    localStorage.setItem(
      WORKSPACE_LAYOUT_KEY,
      '{"navCollapsed":false,"chatWidth":0.35,"composerHeight":10}',
    );

    expect(readWorkspaceLayout().composerHeight).toBe(64);
  });

  it("DoD-6: a stored height far above any viewport reads back UNCHANGED — the maximum is applied at use, not at read", () => {
    // readWorkspaceLayout touches no DOM, so it cannot know the viewport. A height
    // chosen on a bigger monitor is not corrupt data; it is corrected on first use.
    localStorage.setItem(
      WORKSPACE_LAYOUT_KEY,
      '{"navCollapsed":false,"chatWidth":0.35,"composerHeight":5000}',
    );

    expect(readWorkspaceLayout().composerHeight).toBe(5000);
  });
});
