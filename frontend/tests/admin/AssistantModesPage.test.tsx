/**
 * The five-mode editor surface — 012.assistant-config-editor / 007.modes-page,
 * DoD-1 · DoD-2 · DoD-3 · DoD-4 · DoD-5 · DoD-6 · DoD-7 · DoD-8 · DoD-9 · DoD-10
 * (UC-095 steps 1-4 + exception handling; US-110.AC-1, US-110.AC-4, US-111.AC-1,
 * US-112.AC-1, US-114.AC-2).
 *
 * Bound to the frozen signatures in status.md -> `## Skeleton` (step 007, and step
 * 006 for the api module):
 *   class AssistantModesPageState {
 *     modes / modesStatus / modesError;
 *     tools / toolsStatus / toolsError;
 *     subAgents / subAgentsStatus / subAgentsError }        // three async trios
 *   loadModesPage(state, signal?): Promise<void>            // the only loader
 *   class ModeEditorDraft(mode, tools, subAgents) {
 *     systemPrompt; selectedTools: Set<string>; selectedSubAgents: Set<string>;
 *     tools; subAgents; serverErrors; submitStatus;
 *     get clientErrors; get errors; get canSubmit }
 *   submitModeEditor(draft, modeKey, onSaved, signal?): Promise<void>
 *   const ModeEditorModal = observer(...)                   // props: opened, mode,
 *                          tools, subAgents, onClose, onSaved (the interface is
 *                          module-private — bind to the component, not the type)
 *   const AssistantModesPage = observer(...)                // no props
 *   api/assistantConfig: MODE_LABELS / modeLabel / listModes / listTools /
 *                        listSubAgents / saveMode (+ the sub-agent four)
 *
 * The air gap: every expected value comes from the step's Definition of done, the
 * Interface intent and `007.context.md` / `context.md` — never from source. Two
 * frozen handles the spec pins deliberately are used as such:
 *   - the row's edit control is an `ActionIcon` with `aria-label="Edit mode"`;
 *   - the `form` server error renders as a Mantine `<Alert>` (role="alert") at the
 *     top of the modal.
 * The rest is queried by role / accessible name, never by class or structure. Where
 * the spec pins no wording (the load error, the empty-catalogue copy) the assertion
 * is "readable text rendered, not blank" — the repo precedent
 * (`work/BookStatePage.test.tsx:227`, `work/ChatPane.test.tsx:534`).
 *
 * `../../src/api/assistantConfig` is mocked (never `fetch`, never `api/client`) with
 * the `importOriginal` spread so the module's runtime constants — `MODE_LABELS` and
 * `modeLabel`, which the rendered subtree reads — stay REAL: a module factory that
 * omitted them would make render throw (`user/BookshelfPage.test.tsx:34-41`), and a
 * factory that re-declared them would assert the fixture back to itself. The five
 * labels asserted here are step 006's frozen map.
 *
 * `globals: false`: every primitive is imported explicitly. `restoreMocks` wipes
 * implementations between tests, so `beforeEach` re-arms them.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { runInAction } from "mobx";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ApiError } from "../../src/api/client";
import type {
  AssistantMode,
  AssistantTool,
  SubAgent,
  UpdateAssistantModeRequest,
} from "../../src/types/assistantConfig";
import * as assistantConfigApi from "../../src/api/assistantConfig";
import {
  AssistantModesPageState,
  loadModesPage,
} from "../../src/admin/pages/assistantModesPageState";
import {
  ModeEditorDraft,
  submitModeEditor,
} from "../../src/admin/components/assistant-config/modeEditorDraft";
import { ModeEditorModal } from "../../src/admin/components/assistant-config/ModeEditorModal";
import { AssistantModesPage } from "../../src/admin/pages/AssistantModesPage";
import { renderWithProviders } from "../support/render";

// Only the eight endpoint functions are replaced; `MODE_LABELS` / `modeLabel` are
// the real frozen ones (see the header note).
vi.mock("../../src/api/assistantConfig", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../src/api/assistantConfig")>();
  return {
    ...actual,
    listTools: vi.fn(),
    listModes: vi.fn(),
    saveMode: vi.fn(),
    listSubAgents: vi.fn(),
    createSubAgent: vi.fn(),
    updateSubAgent: vi.fn(),
    disableSubAgent: vi.fn(),
    enableSubAgent: vi.fn(),
  };
});

/* ------------------------------------------------------------------ fixtures */

function makeTool(name: string, description: string): AssistantTool {
  return { name, description };
}

function makeMode(key: string, overrides: Partial<AssistantMode> = {}): AssistantMode {
  return {
    key,
    system_prompt: null,
    tool_names: [],
    sub_agent_ids: [],
    created_at: null,
    modified_at: null,
    ...overrides,
  };
}

function makeSubAgent(id: string, name: string, disabled = false): SubAgent {
  return {
    id,
    name,
    system_prompt: "Check continuity.",
    disabled,
    llm_server_id: null,
    model_name: null,
    tool_names: [],
    mode_keys: [],
    created_at: null,
    modified_at: null,
  };
}

const WEB_SEARCH = makeTool("web_search", "Search the open internet.");
const READ_CHAPTER = makeTool("read_chapter", "Read the text of a chapter.");
const LIST_CODEX = makeTool("list_codex", "List the entries of a codex.");

// Ids cross the wire as strings and exceed 2^53 (`context.md`: "Every id is a `str`
// at the JSON boundary").
const CONTINUITY = makeSubAgent("9007199254740993", "Continuity checker");
const NAMER = makeSubAgent("9007199254740995", "Namer");
const RETIRED = makeSubAgent("9007199254740997", "Retired helper", true);

// Mode labels are step 006's frozen `MODE_LABELS`.
const WRITE_CHAPTER_LABEL = "Write chapter";
const EDIT_CHARACTER_LABEL = "Edit character";
const CLOSE_CHAPTER_LABEL = "Close chapter";

/**
 * Three modes with pairwise-distinct (tool count, sub-agent count) pairs, returned
 * in an order that is neither the seeded key order nor alphabetical — so DoD-1's
 * "in the order the api returned them" has bite.
 */
const WRITE_MODE = makeMode("write-chapter", {
  system_prompt: "Write vividly.",
  tool_names: [WEB_SEARCH.name, READ_CHAPTER.name],
  sub_agent_ids: [CONTINUITY.id],
});
const EDIT_CHARACTER_MODE = makeMode("edit-character", {
  system_prompt: null,
  tool_names: [],
  sub_agent_ids: [CONTINUITY.id, NAMER.id],
});
const CLOSE_CHAPTER_MODE = makeMode("close-chapter", {
  system_prompt: "Wrap the chapter up.",
  tool_names: [LIST_CODEX.name],
  sub_agent_ids: [],
});

const ALL_MODES = [WRITE_MODE, EDIT_CHARACTER_MODE, CLOSE_CHAPTER_MODE];
const ALL_TOOLS = [WEB_SEARCH, READ_CHAPTER, LIST_CODEX];
const ALL_SUB_AGENTS = [CONTINUITY, NAMER];

/* ------------------------------------------------------------------- helpers */

type User = ReturnType<typeof userEvent.setup>;

function escapeForRegExp(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/** A picker checkbox, found by the name/label the spec says it carries. */
function checkboxNamed(text: string): HTMLElement {
  return screen.getByRole("checkbox", { name: new RegExp(escapeForRegExp(text)) });
}

function queryCheckboxNamed(text: string): HTMLElement | null {
  return screen.queryByRole("checkbox", { name: new RegExp(escapeForRegExp(text)) });
}

/** The modal's single free-text control: the system-prompt `Textarea`. */
function promptField(): HTMLElement {
  return screen.getByRole("textbox");
}

function saveButton(): HTMLElement {
  return screen.getByRole("button", { name: /save/i });
}

/** Body rows of the modes table (the header row carries columnheaders, not cells). */
async function bodyRows(): Promise<HTMLElement[]> {
  const table = await screen.findByRole("table");
  return within(table)
    .getAllByRole("row")
    .filter((row) => within(row).queryAllByRole("cell").length > 0);
}

async function rowFor(label: string): Promise<HTMLElement> {
  const rows = await bodyRows();
  const match = rows.find((row) => (row.textContent ?? "").includes(label));
  if (match === undefined) {
    throw new Error(`no table row showing the mode label "${label}"`);
  }
  return match;
}

/** Opens a mode's editor through the frozen `aria-label="Edit mode"` action. */
async function openEditorFor(user: User, label: string): Promise<void> {
  const row = await rowFor(label);
  await user.click(within(row).getByRole("button", { name: "Edit mode" }));
}

/** Asserts a cell shows the given count, whatever wording surrounds it. */
function expectCount(cell: HTMLElement, expected: number): void {
  expect(cell.textContent ?? "").toMatch(new RegExp(`(^|\\D)${expected}(\\D|$)`));
}

/**
 * Everything rendered except the headings — used where the spec pins no wording, to
 * prove a message was rendered rather than a blank surface.
 */
function textOutsideHeadings(): string {
  let text = document.body.textContent ?? "";
  for (const heading of screen.queryAllByRole("heading")) {
    text = text.replace(heading.textContent ?? "", "");
  }
  return text.trim();
}

/** The single `saveMode` call the surface under test must have made. */
function onlySaveCall(): { key: string; body: UpdateAssistantModeRequest } {
  const calls = vi.mocked(assistantConfigApi.saveMode).mock.calls;
  expect(calls).toHaveLength(1);
  const [key, body] = calls[0];
  return { key, body };
}

function renderPage(): void {
  renderWithProviders(<AssistantModesPage />, { route: "/assistant-modes" });
}

function renderModal(mode: AssistantMode, tools: AssistantTool[], subAgents: SubAgent[]): void {
  renderWithProviders(
    <ModeEditorModal
      opened
      mode={mode}
      tools={tools}
      subAgents={subAgents}
      onClose={vi.fn()}
      onSaved={vi.fn()}
    />,
  );
}

beforeEach(() => {
  // `restoreMocks` wipes implementations between tests — benign defaults, each case
  // arranges what it asserts on.
  vi.mocked(assistantConfigApi.listModes).mockResolvedValue([]);
  vi.mocked(assistantConfigApi.listTools).mockResolvedValue([]);
  vi.mocked(assistantConfigApi.listSubAgents).mockResolvedValue([]);
  vi.mocked(assistantConfigApi.saveMode).mockResolvedValue(makeMode("write-chapter"));
});

/* ---------------------------------------------------------------- DoD-1 -----*/

describe("the page loads all three resources and renders one row per mode (DoD-1)", () => {
  it("DoD-1: on mount it loads modes, tools and sub-agents (UC-095 step 1)", async () => {
    vi.mocked(assistantConfigApi.listModes).mockResolvedValue(ALL_MODES);
    vi.mocked(assistantConfigApi.listTools).mockResolvedValue(ALL_TOOLS);
    vi.mocked(assistantConfigApi.listSubAgents).mockResolvedValue(ALL_SUB_AGENTS);

    renderPage();

    await waitFor(() => expect(vi.mocked(assistantConfigApi.listModes)).toHaveBeenCalled());
    expect(vi.mocked(assistantConfigApi.listTools)).toHaveBeenCalled();
    expect(vi.mocked(assistantConfigApi.listSubAgents)).toHaveBeenCalled();
  });

  it("DoD-1: one row per mode, in the order the api returned them, each showing its label (US-110.AC-1)", async () => {
    vi.mocked(assistantConfigApi.listModes).mockResolvedValue(ALL_MODES);
    vi.mocked(assistantConfigApi.listTools).mockResolvedValue(ALL_TOOLS);
    vi.mocked(assistantConfigApi.listSubAgents).mockResolvedValue(ALL_SUB_AGENTS);

    renderPage();

    const rows = await bodyRows();
    expect(rows).toHaveLength(ALL_MODES.length);
    // The api order is write-chapter, edit-character, close-chapter — deliberately
    // neither the seeded order nor alphabetical.
    expect(rows[0]).toHaveTextContent(WRITE_CHAPTER_LABEL);
    expect(rows[1]).toHaveTextContent(EDIT_CHARACTER_LABEL);
    expect(rows[2]).toHaveTextContent(CLOSE_CHAPTER_LABEL);
  });

  it("DoD-1: each row shows its tool count and its sub-agent count", async () => {
    vi.mocked(assistantConfigApi.listModes).mockResolvedValue(ALL_MODES);
    vi.mocked(assistantConfigApi.listTools).mockResolvedValue(ALL_TOOLS);
    vi.mocked(assistantConfigApi.listSubAgents).mockResolvedValue(ALL_SUB_AGENTS);

    renderPage();

    const rows = await bodyRows();
    // Column order (Interface intent): label, prompt-set, tool count, sub-agent
    // count, action — so the two counts are the last two before the trailing action.
    const expected: Array<[number, number]> = [
      [WRITE_MODE.tool_names.length, WRITE_MODE.sub_agent_ids.length],
      [EDIT_CHARACTER_MODE.tool_names.length, EDIT_CHARACTER_MODE.sub_agent_ids.length],
      [CLOSE_CHAPTER_MODE.tool_names.length, CLOSE_CHAPTER_MODE.sub_agent_ids.length],
    ];
    rows.forEach((row, index) => {
      const cells = within(row).getAllByRole("cell");
      expect(cells.length).toBeGreaterThanOrEqual(4);
      const [tools, subAgents] = expected[index];
      expectCount(cells[cells.length - 3], tools);
      expectCount(cells[cells.length - 2], subAgents);
    });
  });
});

/* ---------------------------------------------------------------- DoD-2 -----*/

describe("a failing load degrades to a message with no table (DoD-2)", () => {
  it("DoD-2: the loader resolves (does not throw) and lands an author-facing error", async () => {
    const failure = new ApiError(500, "Server error");
    vi.mocked(assistantConfigApi.listModes).mockRejectedValue(failure);
    vi.mocked(assistantConfigApi.listTools).mockRejectedValue(failure);
    vi.mocked(assistantConfigApi.listSubAgents).mockRejectedValue(failure);
    const state = new AssistantModesPageState();

    await expect(loadModesPage(state)).resolves.toBeUndefined();

    expect(state.modes).toEqual([]);
    const message = state.modesError ?? state.toolsError ?? state.subAgentsError;
    expect(typeof message).toBe("string");
    expect((message ?? "").length).toBeGreaterThan(0);
  });

  it("DoD-2: the page renders an error message and NO table (UC-095 — degrade, don't crash)", async () => {
    const failure = new ApiError(500, "Server error");
    vi.mocked(assistantConfigApi.listModes).mockRejectedValue(failure);
    vi.mocked(assistantConfigApi.listTools).mockRejectedValue(failure);
    vi.mocked(assistantConfigApi.listSubAgents).mockRejectedValue(failure);

    renderPage();

    await waitFor(() => expect(vi.mocked(assistantConfigApi.listModes)).toHaveBeenCalled());
    // A message is rendered beside the heading (the spec pins no wording); a spinner
    // or a blank surface would leave nothing here.
    await waitFor(() => expect(textOutsideHeadings()).not.toBe(""));
    expect(screen.queryByRole("table")).toBeNull();
  });
});

/* ---------------------------------------------------------------- DoD-3 -----*/

describe("opening a mode's editor shows its stored configuration (DoD-3)", () => {
  it("DoD-3: the draft seeds the prompt and both selections from the mode (null prompt -> empty string)", () => {
    const draft = new ModeEditorDraft(
      WRITE_MODE,
      ALL_TOOLS,
      ALL_SUB_AGENTS,
    );

    expect(draft.systemPrompt).toBe("Write vividly.");
    expect(Array.from(draft.selectedTools).sort()).toEqual(
      [WEB_SEARCH.name, READ_CHAPTER.name].sort(),
    );
    expect(Array.from(draft.selectedSubAgents).sort()).toEqual([CONTINUITY.id]);

    const unconfigured = new ModeEditorDraft(EDIT_CHARACTER_MODE, ALL_TOOLS, ALL_SUB_AGENTS);
    expect(unconfigured.systemPrompt).toBe("");
    expect(Array.from(unconfigured.selectedTools)).toEqual([]);
  });

  it("DoD-3: the editor shows the stored prompt, selected boxes checked and unselected ones unchecked (UC-095 steps 2-4)", () => {
    renderModal(WRITE_MODE, ALL_TOOLS, ALL_SUB_AGENTS);

    expect(promptField()).toHaveValue("Write vividly.");
    // Tools: the mode's two are checked, the third is not (US-111.AC-1).
    expect(checkboxNamed(WEB_SEARCH.name)).toBeChecked();
    expect(checkboxNamed(READ_CHAPTER.name)).toBeChecked();
    expect(checkboxNamed(LIST_CODEX.name)).not.toBeChecked();
    // Sub-agents are shown by NAME while the mode carries ids (US-112.AC-1).
    expect(checkboxNamed(CONTINUITY.name)).toBeChecked();
    expect(checkboxNamed(NAMER.name)).not.toBeChecked();
  });

  it("DoD-3: the row's edit action opens THAT mode's editor", async () => {
    const user = userEvent.setup();
    vi.mocked(assistantConfigApi.listModes).mockResolvedValue(ALL_MODES);
    vi.mocked(assistantConfigApi.listTools).mockResolvedValue(ALL_TOOLS);
    vi.mocked(assistantConfigApi.listSubAgents).mockResolvedValue(ALL_SUB_AGENTS);
    renderPage();

    await openEditorFor(user, CLOSE_CHAPTER_LABEL);

    expect(promptField()).toHaveValue("Wrap the chapter up.");
    expect(checkboxNamed(LIST_CODEX.name)).toBeChecked();
    expect(checkboxNamed(WEB_SEARCH.name)).not.toBeChecked();
  });
});

/* ---------------------------------------------------------------- DoD-4 -----*/

describe("editing the prompt and saving (DoD-4)", () => {
  it("DoD-4: saves once with that mode's key and the new prompt, refreshes the list and closes the modal (US-110.AC-1)", async () => {
    const user = userEvent.setup();
    vi.mocked(assistantConfigApi.listModes).mockResolvedValue(ALL_MODES);
    vi.mocked(assistantConfigApi.listTools).mockResolvedValue(ALL_TOOLS);
    vi.mocked(assistantConfigApi.listSubAgents).mockResolvedValue(ALL_SUB_AGENTS);
    renderPage();

    await openEditorFor(user, WRITE_CHAPTER_LABEL);
    const loadsBeforeSave = vi.mocked(assistantConfigApi.listModes).mock.calls.length;

    await user.clear(promptField());
    await user.type(promptField(), "Third person.");
    await user.click(saveButton());

    await waitFor(() => expect(vi.mocked(assistantConfigApi.saveMode)).toHaveBeenCalledTimes(1));
    const { key, body } = onlySaveCall();
    expect(key).toBe(WRITE_MODE.key);
    expect(body.system_prompt).toBe("Third person.");

    // The list is re-loaded from the backend (no optimistic update) ...
    await waitFor(() =>
      expect(vi.mocked(assistantConfigApi.listModes).mock.calls.length).toBeGreaterThan(
        loadsBeforeSave,
      ),
    );
    // ... and the editor closes (its prompt field is gone; the page has none).
    await waitFor(() => expect(screen.queryByRole("textbox")).toBeNull());
  });
});

/* ---------------------------------------------------------------- DoD-5 -----*/

describe("an emptied prompt is a valid saved state, sent as null (DoD-5)", () => {
  it("DoD-5: an empty prompt submits system_prompt: null and is not blocked client-side (US-110.AC-4)", async () => {
    const draft = new ModeEditorDraft(WRITE_MODE, ALL_TOOLS, ALL_SUB_AGENTS);
    runInAction(() => {
      draft.systemPrompt = "";
      draft.selectedTools = new Set<string>();
      draft.selectedSubAgents = new Set<string>();
    });

    // A mode has no required field: empty prompt + empty selections are all valid.
    expect(draft.clientErrors).toEqual({});
    expect(draft.canSubmit).toBe(true);

    const onSaved = vi.fn();
    await submitModeEditor(draft, WRITE_MODE.key, onSaved);

    const { key, body } = onlySaveCall();
    expect(key).toBe(WRITE_MODE.key);
    expect(body.system_prompt).toBeNull();
    expect(body.system_prompt).not.toBe("");
    expect(onSaved).toHaveBeenCalledTimes(1);
  });

  it("DoD-5: clearing the prompt in the editor leaves Save enabled and sends null", async () => {
    const user = userEvent.setup();
    renderModal(WRITE_MODE, ALL_TOOLS, ALL_SUB_AGENTS);

    await user.clear(promptField());

    expect(promptField()).toHaveValue("");
    expect(saveButton()).toBeEnabled();

    await user.click(saveButton());

    await waitFor(() => expect(vi.mocked(assistantConfigApi.saveMode)).toHaveBeenCalledTimes(1));
    expect(onlySaveCall().body.system_prompt).toBeNull();
  });
});

/* ---------------------------------------------------------------- DoD-6 -----*/

describe("the tool selection is sent exactly as checked (DoD-6)", () => {
  it("DoD-6: checking one tool and unchecking another sends exactly the checked set (US-111.AC-1)", async () => {
    const user = userEvent.setup();
    renderModal(WRITE_MODE, ALL_TOOLS, ALL_SUB_AGENTS);

    // Seeded: web_search + read_chapter. Uncheck read_chapter, check list_codex.
    await user.click(checkboxNamed(READ_CHAPTER.name));
    await user.click(checkboxNamed(LIST_CODEX.name));
    await user.click(saveButton());

    await waitFor(() => expect(vi.mocked(assistantConfigApi.saveMode)).toHaveBeenCalledTimes(1));
    const { key, body } = onlySaveCall();
    expect(key).toBe(WRITE_MODE.key);
    expect([...body.tool_names].sort()).toEqual([WEB_SEARCH.name, LIST_CODEX.name].sort());
  });

  it("DoD-6: unchecking every tool sends an EMPTY ARRAY, not an omitted field (context.md scope decision 1)", async () => {
    const user = userEvent.setup();
    renderModal(WRITE_MODE, ALL_TOOLS, ALL_SUB_AGENTS);

    await user.click(checkboxNamed(WEB_SEARCH.name));
    await user.click(checkboxNamed(READ_CHAPTER.name));
    await user.click(saveButton());

    await waitFor(() => expect(vi.mocked(assistantConfigApi.saveMode)).toHaveBeenCalledTimes(1));
    const { body } = onlySaveCall();
    // Empty means *no tools* — the field must be present and `[]`.
    expect(Object.keys(body)).toContain("tool_names");
    expect(body.tool_names).toEqual([]);
  });

  it("DoD-6: a draft with no tools selected submits tool_names: []", async () => {
    const draft = new ModeEditorDraft(WRITE_MODE, ALL_TOOLS, ALL_SUB_AGENTS);
    runInAction(() => {
      draft.selectedTools = new Set<string>();
    });

    await submitModeEditor(draft, WRITE_MODE.key, vi.fn());

    const { body } = onlySaveCall();
    expect(Object.keys(body)).toContain("tool_names");
    expect(body.tool_names).toEqual([]);
  });
});

/* ---------------------------------------------------------------- DoD-7 -----*/

describe("the sub-agent selection is sent exactly as checked (DoD-7)", () => {
  it("DoD-7: toggling sub-agents sends exactly the checked set of ids (US-112.AC-1)", async () => {
    const user = userEvent.setup();
    renderModal(WRITE_MODE, ALL_TOOLS, ALL_SUB_AGENTS);

    // Seeded: the continuity checker. Add the namer.
    await user.click(checkboxNamed(NAMER.name));
    await user.click(saveButton());

    await waitFor(() => expect(vi.mocked(assistantConfigApi.saveMode)).toHaveBeenCalledTimes(1));
    const { key, body } = onlySaveCall();
    expect(key).toBe(WRITE_MODE.key);
    expect([...body.sub_agent_ids].sort()).toEqual([CONTINUITY.id, NAMER.id].sort());
  });

  it("DoD-7: unchecking a sub-agent drops exactly that id and sends [] when none remain", async () => {
    const user = userEvent.setup();
    renderModal(WRITE_MODE, ALL_TOOLS, ALL_SUB_AGENTS);

    await user.click(checkboxNamed(CONTINUITY.name));
    await user.click(saveButton());

    await waitFor(() => expect(vi.mocked(assistantConfigApi.saveMode)).toHaveBeenCalledTimes(1));
    const { body } = onlySaveCall();
    expect(Object.keys(body)).toContain("sub_agent_ids");
    expect(body.sub_agent_ids).toEqual([]);
  });
});

/* ---------------------------------------------------------------- DoD-8 -----*/

describe("a disabled sub-agent is not offered (DoD-8)", () => {
  it("DoD-8: the picker offers the enabled sub-agent and NOT the disabled one (US-114.AC-2)", () => {
    renderModal(EDIT_CHARACTER_MODE, ALL_TOOLS, [CONTINUITY, RETIRED]);

    expect(checkboxNamed(CONTINUITY.name)).toBeInTheDocument();
    expect(queryCheckboxNamed(RETIRED.name)).toBeNull();
  });

  it("DoD-8: a save from that picker cannot carry the disabled sub-agent's id", async () => {
    const user = userEvent.setup();
    const mode = makeMode("edit-character", { sub_agent_ids: [] });
    renderModal(mode, ALL_TOOLS, [CONTINUITY, RETIRED]);

    await user.click(checkboxNamed(CONTINUITY.name));
    await user.click(saveButton());

    await waitFor(() => expect(vi.mocked(assistantConfigApi.saveMode)).toHaveBeenCalledTimes(1));
    const { body } = onlySaveCall();
    expect(body.sub_agent_ids).toEqual([CONTINUITY.id]);
    expect(body.sub_agent_ids).not.toContain(RETIRED.id);
  });
});

/* ---------------------------------------------------------------- DoD-9 -----*/

describe("a failed save keeps the editor open with its edits (DoD-9)", () => {
  it("DoD-9: an ApiError becomes a form-level message; onSaved never runs (UC-095 exception handling)", async () => {
    vi.mocked(assistantConfigApi.saveMode).mockRejectedValue(new ApiError(400, "Unknown tool"));
    const draft = new ModeEditorDraft(WRITE_MODE, ALL_TOOLS, ALL_SUB_AGENTS);
    const onSaved = vi.fn();

    // Handled, not thrown.
    await expect(submitModeEditor(draft, WRITE_MODE.key, onSaved)).resolves.toBeUndefined();

    expect(draft.submitStatus).toBe("error");
    // Every server status maps to the single `form` key for this modal.
    expect(Object.keys(draft.serverErrors)).toEqual(["form"]);
    expect(draft.errors.form.length).toBeGreaterThan(0);
    expect(onSaved).not.toHaveBeenCalled();
  });

  it("DoD-9: the modal stays open with the admin's edits, shows the error at the top, and the list is NOT refreshed", async () => {
    const user = userEvent.setup();
    vi.mocked(assistantConfigApi.listModes).mockResolvedValue(ALL_MODES);
    vi.mocked(assistantConfigApi.listTools).mockResolvedValue(ALL_TOOLS);
    vi.mocked(assistantConfigApi.listSubAgents).mockResolvedValue(ALL_SUB_AGENTS);
    vi.mocked(assistantConfigApi.saveMode).mockRejectedValue(new ApiError(400, "Unknown tool"));
    renderPage();

    await openEditorFor(user, EDIT_CHARACTER_LABEL);
    const loadsBeforeSave = vi.mocked(assistantConfigApi.listModes).mock.calls.length;

    await user.type(promptField(), "Stay in character.");
    await user.click(checkboxNamed(WEB_SEARCH.name));
    await user.click(saveButton());

    // The error renders in the modal, above the prompt field.
    const alert = await screen.findByRole("alert");
    expect((alert.textContent ?? "").trim()).not.toBe("");
    expect(
      alert.compareDocumentPosition(promptField()) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).not.toBe(0);

    // The modal is still open and the edits survived.
    expect(promptField()).toHaveValue("Stay in character.");
    expect(checkboxNamed(WEB_SEARCH.name)).toBeChecked();

    // Nothing was re-loaded.
    expect(vi.mocked(assistantConfigApi.listModes).mock.calls.length).toBe(loadsBeforeSave);
  });
});

/* --------------------------------------------------------------- DoD-10 -----*/

describe("the tool picker is catalogue-driven at any size (DoD-10)", () => {
  it("DoD-10: an empty catalogue renders an explanatory state, not a blank box or a crash (UC-095 step 3)", () => {
    renderModal(makeMode("edit-fact"), [], ALL_SUB_AGENTS);

    // No tool is offered ...
    for (const tool of ALL_TOOLS) {
      expect(queryCheckboxNamed(tool.name)).toBeNull();
    }
    // ... and the modal still renders readable copy (the spec pins no wording).
    expect(textOutsideHeadings()).not.toBe("");
    // The rest of the editor is unaffected.
    expect(checkboxNamed(CONTINUITY.name)).toBeInTheDocument();
  });

  it("DoD-10: with an empty catalogue the modal still saves, sending tool_names: []", async () => {
    const user = userEvent.setup();
    renderModal(makeMode("edit-fact"), [], ALL_SUB_AGENTS);

    await user.click(saveButton());

    await waitFor(() => expect(vi.mocked(assistantConfigApi.saveMode)).toHaveBeenCalledTimes(1));
    const { key, body } = onlySaveCall();
    expect(key).toBe("edit-fact");
    expect(body.tool_names).toEqual([]);
  });

  it("DoD-10: the picker offers exactly the catalogue it is given — one entry, or many", () => {
    // One entry (the registry's size today) ...
    const single = renderWithProviders(
      <ModeEditorModal
        opened
        mode={makeMode("edit-fact")}
        tools={[WEB_SEARCH]}
        subAgents={[]}
        onClose={vi.fn()}
        onSaved={vi.fn()}
      />,
    );
    expect(checkboxNamed(WEB_SEARCH.name)).toBeInTheDocument();
    expect(queryCheckboxNamed(READ_CHAPTER.name)).toBeNull();
    single.unmount();

    // ... and three, with no count hard-coded anywhere.
    renderModal(makeMode("edit-fact"), ALL_TOOLS, []);
    for (const tool of ALL_TOOLS) {
      expect(checkboxNamed(tool.name)).toBeInTheDocument();
    }
  });
});
