/**
 * The grouped tool picker — 025.codex-listing-tools, DoD-8 · DoD-9 (+ DoD-10's
 * toggle-callback clause, which is this component's prop contract).
 *
 * Bound to the frozen signatures in
 * `docs/plans/025.codex-listing-tools/status.md` -> `## Skeleton`:
 *   interface ToolPickerProps {          // module-PRIVATE — bind to the component
 *     tools: AssistantTool[];
 *     selected: Set<string>;
 *     onToggle: (name: string, checked: boolean) => void;
 *     emptyMessage: string }
 *   export const ToolPicker = observer(function ToolPicker({ ... }: ToolPickerProps))
 *   api/assistantConfig: TOOL_GROUP_LABELS
 *     { codex: "Codex access", book: "Book access", web: "Web access" }
 *   types/assistantConfig: AssistantTool { name; description; group }
 *
 * The air gap: every expected value comes from `plan.md` -> Interface
 * (`ToolPicker.tsx`) and Definition of done, and from `context.md` -> "Shared
 * vocabulary" -> **group**. Never from source.
 *
 * The spec pins the group DISPLAY ORDER (Codex -> Book -> Web -> Other), the
 * "Other" heading literal, the three `TOOL_GROUP_LABELS` values, and that a group
 * with no tools renders NOTHING. It pins no markup for the headings, so nothing
 * here asserts an element type or a class: order is read off the rendered text and
 * the document order of the checkboxes themselves.
 *
 * `TOOL_GROUP_LABELS` is imported REAL — this is the contract the component reads,
 * and re-declaring it here would assert the fixture back to itself.
 *
 * `globals: false`: every primitive is imported explicitly.
 */
import { describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { AssistantTool } from "../../src/types/assistantConfig";
import { TOOL_GROUP_LABELS } from "../../src/api/assistantConfig";
import { ToolPicker } from "../../src/admin/components/assistant-config/ToolPicker";
import { renderWithProviders } from "../support/render";

/* ------------------------------------------------------------------ fixtures */

function makeTool(name: string, group: string): AssistantTool {
  return { name, description: `What ${name} does.`, group };
}

// Names are pairwise non-substrings, and none of them contains a heading word, so
// an accessible-name lookup can never be satisfied by the wrong control.
const CODEX_ONE = makeTool("codex_search", "codex");
const CODEX_TWO = makeTool("alpha_codex_read", "codex");
const BOOK_ONE = makeTool("read_chapter_text", "book");
const BOOK_TWO = makeTool("zzz_set_chapter", "book");
const WEB_ONE = makeTool("web_search", "web");
// An `AssistantTool.group` the frontend label map does not know — the trailing
// catch-all case. The wire type is `string`, so this is a legal value.
const STRANGER = makeTool("mystery_probe", "delegation");

const CODEX_LABEL = TOOL_GROUP_LABELS.codex;
const BOOK_LABEL = TOOL_GROUP_LABELS.book;
const WEB_LABEL = TOOL_GROUP_LABELS.web;
const OTHER_LABEL = "Other";

/* ------------------------------------------------------------------- helpers */

function escapeForRegExp(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function renderPicker(
  tools: AssistantTool[],
  options: { selected?: string[]; onToggle?: (name: string, checked: boolean) => void } = {},
) {
  return renderWithProviders(
    <ToolPicker
      tools={tools}
      selected={new Set<string>(options.selected ?? [])}
      onToggle={options.onToggle ?? vi.fn()}
      emptyMessage="No tools are available to select."
    />,
  );
}

function bodyText(): string {
  return document.body.textContent ?? "";
}

/** A tool checkbox, found by the accessible name the spec says it carries. */
function checkboxNamed(name: string): HTMLElement {
  return screen.getByRole("checkbox", { name: new RegExp(escapeForRegExp(name)) });
}

/** The tool checkbox's position in DOCUMENT order among all checkboxes. */
function checkboxIndex(name: string): number {
  const index = screen.getAllByRole("checkbox").indexOf(checkboxNamed(name));
  expect(index).toBeGreaterThanOrEqual(0);
  return index;
}

/** The rendered order of the given tools, as checkbox positions. */
function orderOf(tools: AssistantTool[]): number[] {
  return tools.map((tool) => checkboxIndex(tool.name));
}

function isSorted(values: number[]): boolean {
  return values.every((value, index) => index === 0 || values[index - 1] < value);
}

/* ---------------------------------------------------------------- DoD-8 -----*/

describe("the picker groups in a fixed order and drops nothing (DoD-8)", () => {
  it("DoD-8: groups render Codex -> Book -> Web -> Other, whatever order the catalogue arrives in", () => {
    // Deliberately scrambled: the catalogue order is neither the display order nor
    // grouped at all, so a picker that simply rendered the array would fail.
    renderPicker([WEB_ONE, BOOK_ONE, STRANGER, CODEX_ONE, BOOK_TWO, CODEX_TWO]);

    // The four headings appear, in the fixed display order.
    const text = bodyText();
    for (const label of [CODEX_LABEL, BOOK_LABEL, WEB_LABEL, OTHER_LABEL]) {
      expect(text).toContain(label);
    }
    expect(text.indexOf(CODEX_LABEL)).toBeLessThan(text.indexOf(BOOK_LABEL));
    expect(text.indexOf(BOOK_LABEL)).toBeLessThan(text.indexOf(WEB_LABEL));
    expect(text.indexOf(WEB_LABEL)).toBeLessThan(text.indexOf(OTHER_LABEL));

    // And the checkboxes themselves are in that grouped order — one per tool, in
    // the catalogue's own order within each group.
    expect(screen.getAllByRole("checkbox")).toHaveLength(6);
    expect(orderOf([CODEX_ONE, CODEX_TWO, BOOK_ONE, BOOK_TWO, WEB_ONE, STRANGER])).toEqual(
      [0, 1, 2, 3, 4, 5],
    );
  });

  it("DoD-8: an unrecognised group renders under Other and is never dropped", () => {
    const unknownA = makeTool("probe_alpha", "delegation");
    const unknownB = makeTool("probe_beta", "brand_new_group");
    renderPicker([unknownA, CODEX_ONE, unknownB]);

    // Both survive, reachable by name ...
    expect(checkboxNamed(unknownA.name)).toBeInTheDocument();
    expect(checkboxNamed(unknownB.name)).toBeInTheDocument();
    // ... under the trailing "Other" heading, after the known groups.
    expect(bodyText()).toContain(OTHER_LABEL);
    expect(bodyText().indexOf(CODEX_LABEL)).toBeLessThan(bodyText().indexOf(OTHER_LABEL));
    expect(checkboxIndex(CODEX_ONE.name)).toBeLessThan(checkboxIndex(unknownA.name));
    expect(checkboxIndex(CODEX_ONE.name)).toBeLessThan(checkboxIndex(unknownB.name));
    // Two unrecognised groups fall into the ONE trailing catch-all, in catalogue
    // order.
    expect(checkboxIndex(unknownA.name)).toBeLessThan(checkboxIndex(unknownB.name));
  });

  it("DoD-8: a group with no tools renders nothing at all — no heading, no container", () => {
    renderPicker([CODEX_ONE, CODEX_TWO]);

    expect(bodyText()).toContain(CODEX_LABEL);
    // The three empty groups contribute no heading and no copy of their own.
    expect(bodyText()).not.toContain(BOOK_LABEL);
    expect(bodyText()).not.toContain(WEB_LABEL);
    expect(bodyText()).not.toContain(OTHER_LABEL);
    expect(screen.getAllByRole("checkbox")).toHaveLength(2);
  });

  it("DoD-8: Other is suppressed when every tool's group is recognised", () => {
    renderPicker([CODEX_ONE, BOOK_ONE, WEB_ONE]);

    expect(bodyText()).toContain(CODEX_LABEL);
    expect(bodyText()).toContain(BOOK_LABEL);
    expect(bodyText()).toContain(WEB_LABEL);
    expect(bodyText()).not.toContain(OTHER_LABEL);
  });

  it("DoD-8: catalogue order is preserved WITHIN a group", () => {
    // Reverse-alphabetical within each group, so an alphabetical sort would fail.
    const first = makeTool("zeta_codex_tool", "codex");
    const second = makeTool("mid_codex_tool", "codex");
    const third = makeTool("alpha_codex_tool", "codex");
    renderPicker([first, second, third, BOOK_TWO, BOOK_ONE]);

    expect(isSorted(orderOf([first, second, third]))).toBe(true);
    expect(isSorted(orderOf([BOOK_TWO, BOOK_ONE]))).toBe(true);
  });
});

/* ---------------------------------------------------------------- DoD-9 -----*/

describe("accessible names survive the grouping (DoD-9)", () => {
  const EVERY_TOOL = [CODEX_ONE, CODEX_TWO, BOOK_ONE, BOOK_TWO, WEB_ONE, STRANGER];

  it("DoD-9: every tool checkbox is reachable, unambiguously, by its accessible name", () => {
    renderPicker(EVERY_TOOL);

    for (const tool of EVERY_TOOL) {
      // `getByRole` throws on BOTH zero matches and more than one — so this fails
      // if grouping dropped a control or made two names collide.
      expect(checkboxNamed(tool.name)).toBeInTheDocument();
    }
    expect(screen.getAllByRole("checkbox")).toHaveLength(EVERY_TOOL.length);
  });

  it("DoD-9: no group heading is folded into a checkbox's accessible name, and no heading is itself a checkbox", () => {
    renderPicker(EVERY_TOOL);

    for (const label of [CODEX_LABEL, BOOK_LABEL, WEB_LABEL, OTHER_LABEL]) {
      // The heading IS on screen ...
      expect(bodyText()).toContain(label);
      // ... and NO checkbox answers to it — neither as its whole name (a heading
      // that is a checkbox) nor as part of one (a heading folded into a label).
      expect(
        screen.queryAllByRole("checkbox", { name: new RegExp(escapeForRegExp(label)) }),
      ).toHaveLength(0);
    }
  });

  it("DoD-9: there is no select-all control of any kind", () => {
    renderPicker(EVERY_TOOL);

    // Exactly one checkbox per tool leaves no room for a group- or picker-level one.
    expect(screen.getAllByRole("checkbox")).toHaveLength(EVERY_TOOL.length);

    const selectAll = /select all|all tools|check all|toggle all/i;
    for (const control of [
      ...screen.queryAllByRole("checkbox"),
      ...screen.queryAllByRole("button"),
      ...screen.queryAllByRole("switch"),
    ]) {
      const label =
        `${control.textContent ?? ""} ${control.getAttribute("aria-label") ?? ""}`.trim();
      expect(label).not.toMatch(selectAll);
    }
  });
});

/* --------------------------------------------------------------- DoD-10 -----*/

describe("the toggle callback contract (DoD-10)", () => {
  it("DoD-10: checking an unselected tool fires onToggle(name, true) once, for THAT tool", async () => {
    const user = userEvent.setup();
    const onToggle = vi.fn();
    renderPicker([CODEX_ONE, BOOK_ONE, STRANGER], { onToggle });

    await user.click(checkboxNamed(BOOK_ONE.name));

    expect(onToggle).toHaveBeenCalledTimes(1);
    expect(onToggle).toHaveBeenCalledWith(BOOK_ONE.name, true);
  });

  it("DoD-10: unchecking a selected tool fires onToggle(name, false)", async () => {
    const user = userEvent.setup();
    const onToggle = vi.fn();
    renderPicker([CODEX_ONE, BOOK_ONE], { selected: [CODEX_ONE.name], onToggle });

    // The seeded selection is what the checkbox shows ...
    expect(checkboxNamed(CODEX_ONE.name)).toBeChecked();
    expect(checkboxNamed(BOOK_ONE.name)).not.toBeChecked();

    await user.click(checkboxNamed(CODEX_ONE.name));

    expect(onToggle).toHaveBeenCalledTimes(1);
    expect(onToggle).toHaveBeenCalledWith(CODEX_ONE.name, false);
  });
});
