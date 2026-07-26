/**
 * The sub-agent management surface — 012.assistant-config-editor / 008.subagents-page,
 * DoD-1 … DoD-13 (UC-096, UC-097; US-112.AC-2, US-113.AC-1/AC-3/AC-5/AC-6,
 * US-114.AC-1/AC-2/AC-3/AC-4).
 *
 * Bound to the frozen signatures in status.md -> `## Skeleton` (step 008, plus step
 * 006 for the api module and step 005/006 for the wire types):
 *   class SubAgentsPageState {
 *     subAgents / subAgentsStatus / subAgentsError;
 *     tools     / toolsStatus     / toolsError;
 *     modes     / modesStatus     / modesError;
 *     servers   / serversStatus   / serversError }          // FOUR async trios
 *   loadSubAgentsPage(state, signal?): Promise<void>        // the only loader
 *   disableSubAgentAction(state, subAgentId, signal?): Promise<void>
 *   enableSubAgentAction(state, subAgentId, signal?): Promise<void>
 *   interface ModelOption { value: string; label: string }
 *   class SubAgentFormDraft(subAgent | null, tools, modes, servers) {
 *     name; systemPrompt; selectedTools: Set<string>; selectedModes: Set<string>;
 *     llmServerId: string | null; modelName: string | null;
 *     tools; modes; servers; serverErrors; submitStatus;
 *     get modelOptions; get modelValue; get clientErrors; get errors; get canSubmit }
 *   applyModelOption(draft, value: string | null): void      // sync, the ONLY writer
 *   submitSubAgentForm(draft, subAgentId | null, onSaved, signal?): Promise<void>
 *   const SubAgentFormModal = observer(...)   // props: opened, subAgent, tools,
 *                             modes, servers, onClose, onSaved (the props interface
 *                             is module-private — bind to the component, not the type)
 *   const SubAgentsPage = observer(...)                      // no props
 *
 * The air gap: every expected value comes from the step's Definition of done, the
 * Interface intent and `008.context.md` / `context.md` — never from source. The
 * accessibility handles the skeleton froze are used as such, and only those:
 *   - each row's trailing `ActionIcon` carries `aria-label="Sub-agent actions"`;
 *   - the row `Menu` offers `Edit` plus exactly one of `Disable` / `Enable`, and no
 *     Delete item at all (DoD-12);
 *   - the header action button reads `New sub-agent`; the modal title reads
 *     `New sub-agent` (create) / `Edit sub-agent` (edit);
 *   - the inherit choice's label is `Inherit the main chat's model`.
 * The `<Select>`'s value encoding is PRIVATE to `subAgentFormDraft.ts`, so nothing
 * here ever writes or asserts an option `value` literal: options are identified by
 * label, and the (server id, model name) pair an option carries is discovered by
 * applying it through the frozen `applyModelOption` on a throwaway draft.
 *
 * TWO api modules are mocked (never `fetch`, never `api/client`), both with the
 * `importOriginal` spread so their runtime constants stay REAL — `MODE_LABELS` /
 * `modeLabel` (the mode picker's labels) and `api/llmServers`' option constants. A
 * bare module factory that omitted one would make render throw
 * (`user/BookshelfPage.test.tsx:34-41`).
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
  CreateSubAgentRequest,
  SubAgent,
  UpdateSubAgentRequest,
} from "../../src/types/assistantConfig";
import type { LlmServer } from "../../src/types/llmServers";
import * as assistantConfigApi from "../../src/api/assistantConfig";
import * as llmServersApi from "../../src/api/llmServers";
import * as subAgentsPageStateModule from "../../src/admin/pages/subAgentsPageState";
import {
  SubAgentsPageState,
  disableSubAgentAction,
  enableSubAgentAction,
  loadSubAgentsPage,
} from "../../src/admin/pages/subAgentsPageState";
import type { ModelOption } from "../../src/admin/components/sub-agents/subAgentFormDraft";
import {
  SubAgentFormDraft,
  applyModelOption,
  submitSubAgentForm,
} from "../../src/admin/components/sub-agents/subAgentFormDraft";
import { SubAgentFormModal } from "../../src/admin/components/sub-agents/SubAgentFormModal";
import { SubAgentsPage } from "../../src/admin/pages/SubAgentsPage";
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

// The model picker feeds off the EXISTING servers endpoint (`context.md` -> "No new
// model-options endpoint"), so this module is mocked too — again spread, so its
// runtime option constants survive.
vi.mock("../../src/api/llmServers", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../src/api/llmServers")>();
  return { ...actual, listServers: vi.fn() };
});

/* ------------------------------------------------------------------ fixtures */

function makeTool(name: string, description: string): AssistantTool {
  return { name, description };
}

function makeMode(key: string): AssistantMode {
  return {
    key,
    system_prompt: null,
    tool_names: [],
    sub_agent_ids: [],
    created_at: null,
    modified_at: null,
  };
}

function makeSubAgent(id: string, name: string, overrides: Partial<SubAgent> = {}): SubAgent {
  return {
    id,
    name,
    system_prompt: "",
    disabled: false,
    llm_server_id: null,
    model_name: null,
    tool_names: [],
    mode_keys: [],
    created_at: null,
    modified_at: null,
    ...overrides,
  };
}

function makeServer(
  id: string,
  name: string,
  enabledModels: string[],
  isActive: boolean,
): LlmServer {
  return {
    id,
    name,
    backend_type: "openai",
    base_url: "http://localhost:9000/v1",
    has_api_key: false,
    enabled_models: enabledModels,
    is_active: isActive,
    is_embedding: false,
    embedding_model: null,
    created_at: null,
    modified_at: null,
  };
}

const WEB_SEARCH = makeTool("web_search", "Search the open internet.");
const READ_CHAPTER = makeTool("read_chapter", "Read the text of a chapter.");
const LIST_CODEX = makeTool("list_codex", "List the entries of a codex.");
const ALL_TOOLS = [WEB_SEARCH, READ_CHAPTER, LIST_CODEX];

// The five seeded mode keys and their frozen `MODE_LABELS` labels (step 006).
const EDIT_CHARACTER = "edit-character";
const EDIT_LOCATION = "edit-location";
const EDIT_FACT = "edit-fact";
const WRITE_CHAPTER = "write-chapter";
const CLOSE_CHAPTER = "close-chapter";
const MODE_LABEL: Record<string, string> = {
  [EDIT_CHARACTER]: "Edit character",
  [EDIT_LOCATION]: "Edit location",
  [EDIT_FACT]: "Edit fact",
  [WRITE_CHAPTER]: "Write chapter",
  [CLOSE_CHAPTER]: "Close chapter",
};
const ALL_MODE_KEYS = [EDIT_CHARACTER, EDIT_LOCATION, EDIT_FACT, WRITE_CHAPTER, CLOSE_CHAPTER];
const ALL_MODES = ALL_MODE_KEYS.map(makeMode);

// Ids cross the wire as strings and exceed 2^53 (`context.md`: "Every id is a `str`
// at the JSON boundary").
const LOCAL = makeServer("9007199254740993", "Local Llama", ["qwen-72b", "llama-8b"], true);
const CLOUD = makeServer("9007199254740995", "Cloud box", ["gpt-4o"], true);
// DoD-6's real negative: an INACTIVE server that carries enabled models.
const RETIRED_SERVER = makeServer("9007199254740997", "Retired box", ["ghost-model"], false);
const ALL_SERVERS = [LOCAL, RETIRED_SERVER, CLOUD];

const CONTINUITY = makeSubAgent("9007199254741001", "Continuity checker", {
  system_prompt: "Check every chapter for contradictions.",
  llm_server_id: LOCAL.id,
  model_name: "qwen-72b",
  tool_names: [WEB_SEARCH.name],
  mode_keys: [WRITE_CHAPTER, EDIT_FACT],
});
// NAMER and RETIRED are configured IDENTICALLY (no model, no tools, no modes) so the
// only difference their rows may show is the disabled marking — DoD-1's differential.
const NAMER = makeSubAgent("9007199254741003", "Namer");
const RETIRED = makeSubAgent("9007199254741005", "Retired helper", { disabled: true });
const ALL_SUB_AGENTS = [CONTINUITY, NAMER, RETIRED];

/* ------------------------------------------------------------------- helpers */

type UserEvt = ReturnType<typeof userEvent.setup>;

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

/**
 * The form's single-line name `TextInput` (Interface intent: "`TextInput` for the
 * name"). It is the only single-line textbox that is not the model `Select`'s
 * combobox target (Mantine marks that one `aria-haspopup="listbox"`).
 */
function nameField(): HTMLElement {
  const candidates = screen
    .getAllByRole("textbox")
    .filter(
      (element) =>
        element.tagName === "INPUT" && element.getAttribute("aria-haspopup") !== "listbox",
    );
  expect(candidates).toHaveLength(1);
  return candidates[0];
}

/** The system-prompt `Textarea` — the form's only multi-line control. */
function promptField(): HTMLElement {
  const candidates = screen
    .getAllByRole("textbox")
    .filter((element) => element.tagName === "TEXTAREA");
  expect(candidates).toHaveLength(1);
  return candidates[0];
}

/** The model `Select`'s target input. */
function modelSelect(): HTMLElement {
  const candidates = Array.from(
    document.querySelectorAll<HTMLElement>('input[aria-haspopup="listbox"]'),
  );
  expect(candidates).toHaveLength(1);
  return candidates[0];
}

function saveButton(): HTMLElement {
  return screen.getByRole("button", { name: /save/i });
}

function cancelButton(): HTMLElement {
  return screen.getByRole("button", { name: /cancel/i });
}

/** Opens the model picker so its options mount. */
async function openModelPicker(user: UserEvt): Promise<void> {
  await user.click(modelSelect());
}

function optionTexts(): string[] {
  return screen.getAllByRole("option").map((option) => (option.textContent ?? "").trim());
}

/** The offered option whose visible label names this model. */
function optionShowing(model: string): HTMLElement {
  const match = screen
    .getAllByRole("option")
    .find((option) => (option.textContent ?? "").includes(model));
  if (match === undefined) {
    throw new Error(`the model picker offers no option naming "${model}"`);
  }
  return match;
}

const INHERIT_LABEL = "Inherit the main chat's model";

/** Body rows of the sub-agent table (the header row carries columnheaders). */
async function bodyRows(): Promise<HTMLElement[]> {
  const table = await screen.findByRole("table");
  return within(table)
    .getAllByRole("row")
    .filter((row) => within(row).queryAllByRole("cell").length > 0);
}

async function rowFor(name: string): Promise<HTMLElement> {
  const rows = await bodyRows();
  const match = rows.find((row) => (row.textContent ?? "").includes(name));
  if (match === undefined) {
    throw new Error(`no table row showing the sub-agent "${name}"`);
  }
  return match;
}

/** Opens a row's menu through the frozen `aria-label="Sub-agent actions"` control. */
async function openRowMenu(user: UserEvt, name: string): Promise<void> {
  const row = await rowFor(name);
  await user.click(within(row).getByRole("button", { name: "Sub-agent actions" }));
}

function menuItemTexts(): string[] {
  return screen.getAllByRole("menuitem").map((item) => (item.textContent ?? "").trim());
}

async function clickMenuItem(user: UserEvt, text: string): Promise<void> {
  await user.click(screen.getByRole("menuitem", { name: text }));
}

function newSubAgentButton(): HTMLElement {
  return screen.getByRole("button", { name: "New sub-agent" });
}

function modalTitle(text: string): HTMLElement | null {
  return screen.queryByRole("heading", { name: text });
}

/** The single `createSubAgent` body the surface under test must have sent. */
function onlyCreateBody(): CreateSubAgentRequest {
  const calls = vi.mocked(assistantConfigApi.createSubAgent).mock.calls;
  expect(calls).toHaveLength(1);
  return calls[0][0];
}

function createBodyAt(index: number): CreateSubAgentRequest {
  const calls = vi.mocked(assistantConfigApi.createSubAgent).mock.calls;
  expect(calls.length).toBeGreaterThan(index);
  return calls[index][0];
}

function onlyUpdateCall(): { id: string; body: UpdateSubAgentRequest } {
  const calls = vi.mocked(assistantConfigApi.updateSubAgent).mock.calls;
  expect(calls).toHaveLength(1);
  const [id, body] = calls[0];
  return { id, body };
}

/** Lower-cased word tokens of everything currently rendered. */
function bodyWords(): string[] {
  return (document.body.textContent ?? "").toLowerCase().match(/[a-z]+/g) ?? [];
}

/**
 * Everything rendered except the page chrome (headings and buttons) — used where the
 * spec pins no wording, so that "a message is on screen" cannot be satisfied by the
 * always-present title and the "New sub-agent" button. A bare `Loader` leaves this
 * empty.
 */
function textOutsideChrome(): string {
  let text = document.body.textContent ?? "";
  for (const element of [...screen.queryAllByRole("heading"), ...screen.queryAllByRole("button")]) {
    const chrome = element.textContent ?? "";
    if (chrome !== "") {
      text = text.split(chrome).join("");
    }
  }
  return text.trim();
}

function stripAll(text: string, needle: string): string {
  return text.split(needle).join("").replace(/\s+/g, " ").trim();
}

function newDraft(
  subAgent: SubAgent | null,
  tools: AssistantTool[] = ALL_TOOLS,
  modes: AssistantMode[] = ALL_MODES,
  servers: LlmServer[] = ALL_SERVERS,
): SubAgentFormDraft {
  return new SubAgentFormDraft(subAgent, tools, modes, servers);
}

/**
 * The (server id, model name) pair each offered option carries, discovered through
 * the frozen `applyModelOption` on throwaway drafts — the option `value` encoding is
 * private to the draft module and is never asserted here.
 */
function offeredPairs(servers: LlmServer[] = ALL_SERVERS): Array<[string | null, string | null]> {
  const source = newDraft(null, ALL_TOOLS, ALL_MODES, servers);
  return source.modelOptions.map((option: ModelOption): [string | null, string | null] => {
    const probe = newDraft(null, ALL_TOOLS, ALL_MODES, servers);
    applyModelOption(probe, option.value);
    return [probe.llmServerId, probe.modelName];
  });
}

function pairKey(pair: [string | null, string | null]): string {
  return JSON.stringify(pair);
}

function renderPage(): void {
  renderWithProviders(<SubAgentsPage />, { route: "/sub-agents" });
}

interface ModalOverrides {
  tools?: AssistantTool[];
  modes?: AssistantMode[];
  servers?: LlmServer[];
}

function renderModal(subAgent: SubAgent | null, overrides: ModalOverrides = {}) {
  return renderWithProviders(
    <SubAgentFormModal
      opened
      subAgent={subAgent}
      tools={overrides.tools ?? ALL_TOOLS}
      modes={overrides.modes ?? ALL_MODES}
      servers={overrides.servers ?? ALL_SERVERS}
      onClose={vi.fn()}
      onSaved={vi.fn()}
    />,
  );
}

function mockAllLoaded(): void {
  vi.mocked(assistantConfigApi.listSubAgents).mockResolvedValue(ALL_SUB_AGENTS);
  vi.mocked(assistantConfigApi.listTools).mockResolvedValue(ALL_TOOLS);
  vi.mocked(assistantConfigApi.listModes).mockResolvedValue(ALL_MODES);
  vi.mocked(llmServersApi.listServers).mockResolvedValue(ALL_SERVERS);
}

beforeEach(() => {
  // `restoreMocks` wipes implementations between tests — benign defaults; each case
  // arranges what it asserts on.
  vi.mocked(assistantConfigApi.listSubAgents).mockResolvedValue([]);
  vi.mocked(assistantConfigApi.listTools).mockResolvedValue([]);
  vi.mocked(assistantConfigApi.listModes).mockResolvedValue([]);
  vi.mocked(llmServersApi.listServers).mockResolvedValue([]);
  vi.mocked(assistantConfigApi.createSubAgent).mockResolvedValue(makeSubAgent("1", "Created"));
  vi.mocked(assistantConfigApi.updateSubAgent).mockResolvedValue(CONTINUITY);
  vi.mocked(assistantConfigApi.disableSubAgent).mockResolvedValue(
    makeSubAgent(CONTINUITY.id, CONTINUITY.name, { disabled: true }),
  );
  vi.mocked(assistantConfigApi.enableSubAgent).mockResolvedValue(
    makeSubAgent(RETIRED.id, RETIRED.name),
  );
});

/* ---------------------------------------------------------------- DoD-1 -----*/

describe("the page loads all four resources and lists every sub-agent (DoD-1)", () => {
  it("DoD-1: on mount it loads sub-agents, tools, modes and servers (UC-097 step 1)", async () => {
    mockAllLoaded();

    renderPage();

    await waitFor(() =>
      expect(vi.mocked(assistantConfigApi.listSubAgents)).toHaveBeenCalled(),
    );
    expect(vi.mocked(assistantConfigApi.listTools)).toHaveBeenCalled();
    expect(vi.mocked(assistantConfigApi.listModes)).toHaveBeenCalled();
    expect(vi.mocked(llmServersApi.listServers)).toHaveBeenCalled();
  });

  it("DoD-1: one row per sub-agent, disabled ones included (US-114.AC-3)", async () => {
    mockAllLoaded();

    renderPage();

    const rows = await bodyRows();
    expect(rows).toHaveLength(ALL_SUB_AGENTS.length);
    for (const subAgent of ALL_SUB_AGENTS) {
      expect((await rowFor(subAgent.name)).textContent ?? "").toContain(subAgent.name);
    }
  });

  it("DoD-1: the disabled sub-agent's name cell is visibly marked, the enabled one's is not", async () => {
    mockAllLoaded();

    renderPage();

    // NAMER and RETIRED carry identical configuration (no model, no tools, no modes),
    // so with their names removed the two name cells can differ ONLY by the disabled
    // marking the spec requires. An unmarked row renders identically -> fails.
    const namerCell = within(await rowFor(NAMER.name)).getAllByRole("cell")[0];
    const retiredCell = within(await rowFor(RETIRED.name)).getAllByRole("cell")[0];

    expect(stripAll(retiredCell.innerHTML, RETIRED.name)).not.toBe(
      stripAll(namerCell.innerHTML, NAMER.name),
    );
  });
});

/* ---------------------------------------------------------------- DoD-2 -----*/

describe("a failing load degrades to a message with no table (DoD-2)", () => {
  it("DoD-2: the loader resolves (does not throw) and lands an author-facing error", async () => {
    const failure = new ApiError(500, "Server error");
    vi.mocked(assistantConfigApi.listSubAgents).mockRejectedValue(failure);
    vi.mocked(assistantConfigApi.listTools).mockRejectedValue(failure);
    vi.mocked(assistantConfigApi.listModes).mockRejectedValue(failure);
    vi.mocked(llmServersApi.listServers).mockRejectedValue(failure);
    const state = new SubAgentsPageState();

    await expect(loadSubAgentsPage(state)).resolves.toBeUndefined();

    expect(state.subAgents).toEqual([]);
    const message =
      state.subAgentsError ?? state.toolsError ?? state.modesError ?? state.serversError;
    expect(typeof message).toBe("string");
    expect((message ?? "").length).toBeGreaterThan(0);
  });

  it("DoD-2: the page renders an error message and NO table", async () => {
    const failure = new ApiError(500, "Server error");
    vi.mocked(assistantConfigApi.listSubAgents).mockRejectedValue(failure);
    vi.mocked(assistantConfigApi.listTools).mockRejectedValue(failure);
    vi.mocked(assistantConfigApi.listModes).mockRejectedValue(failure);
    vi.mocked(llmServersApi.listServers).mockRejectedValue(failure);

    renderPage();

    await waitFor(() =>
      expect(vi.mocked(assistantConfigApi.listSubAgents)).toHaveBeenCalled(),
    );
    // Something readable is on screen beside the heading and the header button (the
    // spec pins no wording); a spinner or a blank surface would leave nothing here.
    await waitFor(() => expect(textOutsideChrome()).not.toBe(""));
    expect(screen.queryByRole("table")).toBeNull();
  });
});

/* ---------------------------------------------------------------- DoD-3 -----*/

describe("creating a sub-agent from an empty form (DoD-3)", () => {
  it('DoD-3: "New sub-agent" opens an empty create form (UC-096)', async () => {
    const user = userEvent.setup();
    mockAllLoaded();
    renderPage();

    await waitFor(() =>
      expect(vi.mocked(assistantConfigApi.listSubAgents)).toHaveBeenCalled(),
    );
    await user.click(newSubAgentButton());

    expect(modalTitle("New sub-agent")).not.toBeNull();
    expect(nameField()).toHaveValue("");
    expect(promptField()).toHaveValue("");
    for (const checkbox of screen.getAllByRole("checkbox")) {
      expect(checkbox).not.toBeChecked();
    }
  });

  it("DoD-3: saving name + prompt + tool + mode calls create ONCE with exactly those values, then refreshes (US-113.AC-1)", async () => {
    const user = userEvent.setup();
    mockAllLoaded();
    renderPage();

    await waitFor(() =>
      expect(vi.mocked(assistantConfigApi.listSubAgents)).toHaveBeenCalled(),
    );
    const loadsBeforeSave = vi.mocked(assistantConfigApi.listSubAgents).mock.calls.length;

    await user.click(newSubAgentButton());
    await user.type(nameField(), "Fact keeper");
    await user.type(promptField(), "Guard the facts.");
    await user.click(checkboxNamed(READ_CHAPTER.name));
    await user.click(checkboxNamed(MODE_LABEL[EDIT_FACT]));
    await user.click(saveButton());

    await waitFor(() =>
      expect(vi.mocked(assistantConfigApi.createSubAgent)).toHaveBeenCalledTimes(1),
    );
    const body = onlyCreateBody();
    expect(body.name).toBe("Fact keeper");
    expect(body.system_prompt).toBe("Guard the facts.");
    expect(body.tool_names).toEqual([READ_CHAPTER.name]);
    expect(body.mode_keys).toEqual([EDIT_FACT]);
    expect(vi.mocked(assistantConfigApi.updateSubAgent)).not.toHaveBeenCalled();

    // The list is re-loaded from the backend (no optimistic update) ...
    await waitFor(() =>
      expect(vi.mocked(assistantConfigApi.listSubAgents).mock.calls.length).toBeGreaterThan(
        loadsBeforeSave,
      ),
    );
    // ... and the form closes.
    await waitFor(() => expect(modalTitle("New sub-agent")).toBeNull());
  });
});

/* ---------------------------------------------------------------- DoD-4 -----*/

describe("creating without choosing a model inherits the main chat's model (DoD-4)", () => {
  it("DoD-4: a fresh create draft starts with BOTH model fields null (US-113.AC-6)", () => {
    const draft = newDraft(null);

    expect(draft.llmServerId).toBeNull();
    expect(draft.modelName).toBeNull();
  });

  it("DoD-4: creating without touching the picker sends llm_server_id AND model_name as null", async () => {
    const user = userEvent.setup();
    renderModal(null);

    await user.type(nameField(), "Fact keeper");
    await user.click(saveButton());

    await waitFor(() =>
      expect(vi.mocked(assistantConfigApi.createSubAgent)).toHaveBeenCalledTimes(1),
    );
    const body = onlyCreateBody();
    // Both fields are explicitly PRESENT and null — the full-replace shape; an
    // omitted key is not the inherit state.
    expect(Object.keys(body)).toContain("llm_server_id");
    expect(Object.keys(body)).toContain("model_name");
    expect(body.llm_server_id).toBeNull();
    expect(body.model_name).toBeNull();
  });
});

/* ---------------------------------------------------------------- DoD-5 -----*/

describe("the model pair moves as one — never half-set (DoD-5)", () => {
  it("DoD-5: choosing a concrete model sets both fields; inherit clears both (US-113.AC-5)", async () => {
    const draft = newDraft(null);
    runInAction(() => {
      draft.name = "Fact keeper";
    });

    const concrete = draft.modelOptions.find((option: ModelOption) =>
      option.label.includes("qwen-72b"),
    );
    expect(concrete).toBeDefined();
    applyModelOption(draft, (concrete as ModelOption).value);

    expect(draft.llmServerId).toBe(LOCAL.id);
    expect(draft.modelName).toBe("qwen-72b");

    await submitSubAgentForm(draft, null, vi.fn());
    const withModel = createBodyAt(0);
    expect(withModel.llm_server_id).toBe(LOCAL.id);
    expect(withModel.model_name).toBe("qwen-72b");

    // ... and back to inherit clears BOTH.
    const inherit = draft.modelOptions.find(
      (option: ModelOption) => option.label === INHERIT_LABEL,
    );
    expect(inherit).toBeDefined();
    applyModelOption(draft, (inherit as ModelOption).value);

    expect(draft.llmServerId).toBeNull();
    expect(draft.modelName).toBeNull();

    await submitSubAgentForm(draft, null, vi.fn());
    const inherited = createBodyAt(1);
    expect(inherited.llm_server_id).toBeNull();
    expect(inherited.model_name).toBeNull();
  });

  it("DoD-5: EVERY offered option — and a cleared picker — leaves the pair coupled (US-114.AC-4)", () => {
    const draft = newDraft(null);
    expect(draft.modelOptions.length).toBeGreaterThan(1);

    for (const option of draft.modelOptions) {
      const probe = newDraft(null);
      applyModelOption(probe, option.value);
      // Both null (inherit) or both set (a concrete model) — never one of the two.
      expect(probe.llmServerId === null).toBe(probe.modelName === null);
    }

    // Mantine's own "clear" hands the writer a null value; that is the inherit state.
    const cleared = newDraft(CONTINUITY);
    expect(cleared.llmServerId).not.toBeNull();
    applyModelOption(cleared, null);
    expect(cleared.llmServerId).toBeNull();
    expect(cleared.modelName).toBeNull();
  });

  it("DoD-5: picking a model in the form sends both wire fields together", async () => {
    const user = userEvent.setup();
    renderModal(null);

    await user.type(nameField(), "Fact keeper");
    await openModelPicker(user);
    await user.click(optionShowing("qwen-72b"));
    await user.click(saveButton());

    await waitFor(() =>
      expect(vi.mocked(assistantConfigApi.createSubAgent)).toHaveBeenCalledTimes(1),
    );
    const body = onlyCreateBody();
    expect(body.llm_server_id).toBe(LOCAL.id);
    expect(body.model_name).toBe("qwen-72b");
  });

  it("DoD-5: switching back to inherit in the form clears both wire fields", async () => {
    const user = userEvent.setup();
    renderModal(null);

    await user.type(nameField(), "Fact keeper");
    await openModelPicker(user);
    await user.click(optionShowing("qwen-72b"));
    await openModelPicker(user);
    await user.click(screen.getByRole("option", { name: INHERIT_LABEL }));
    await user.click(saveButton());

    await waitFor(() =>
      expect(vi.mocked(assistantConfigApi.createSubAgent)).toHaveBeenCalledTimes(1),
    );
    const body = onlyCreateBody();
    expect(body.llm_server_id).toBeNull();
    expect(body.model_name).toBeNull();
  });
});

/* ---------------------------------------------------------------- DoD-6 -----*/

describe("the picker offers models from ACTIVE servers only (DoD-6)", () => {
  it("DoD-6: the offered options are exactly inherit + every active server's enabled models (US-113.AC-5)", () => {
    const offered = offeredPairs().map(pairKey).sort();

    const expected = [
      pairKey([null, null]),
      pairKey([LOCAL.id, "qwen-72b"]),
      pairKey([LOCAL.id, "llama-8b"]),
      pairKey([CLOUD.id, "gpt-4o"]),
    ].sort();
    expect(offered).toEqual(expected);
    // The inactive server contributes nothing at all.
    expect(offered).not.toContain(pairKey([RETIRED_SERVER.id, "ghost-model"]));
  });

  it("DoD-6: with no servers at all, inherit is still the one offered choice", () => {
    expect(offeredPairs([]).map(pairKey)).toEqual([pairKey([null, null])]);
  });

  it("DoD-6: the opened picker shows the active servers' models and NOT the inactive server's", async () => {
    const user = userEvent.setup();
    renderModal(null);

    await openModelPicker(user);

    const texts = optionTexts();
    expect(texts).toContain(INHERIT_LABEL);
    expect(texts.some((text) => text.includes("qwen-72b"))).toBe(true);
    expect(texts.some((text) => text.includes("gpt-4o"))).toBe(true);
    expect(texts.some((text) => text.includes("ghost-model"))).toBe(false);
  });
});

/* ---------------------------------------------------------------- DoD-7 -----*/

describe("a duplicate name is refused on the name field (DoD-7)", () => {
  it("DoD-7: a 409 lands on the NAME key alone and onSaved never runs (US-113.AC-3)", async () => {
    vi.mocked(assistantConfigApi.createSubAgent).mockRejectedValue(
      new ApiError(409, "A sub-agent with that name already exists"),
    );
    const draft = newDraft(null);
    runInAction(() => {
      draft.name = CONTINUITY.name;
    });
    const onSaved = vi.fn();

    // Handled, not thrown.
    await expect(submitSubAgentForm(draft, null, onSaved)).resolves.toBeUndefined();

    expect(draft.submitStatus).toBe("error");
    expect(Object.keys(draft.serverErrors)).toEqual(["name"]);
    expect(draft.errors.name.length).toBeGreaterThan(0);
    expect(draft.errors.form).toBeUndefined();
    expect(onSaved).not.toHaveBeenCalled();
  });

  it("DoD-7: the form stays open with the typed input intact, the error on the name field, and the list NOT refreshed (UC-096 exception flow)", async () => {
    const user = userEvent.setup();
    mockAllLoaded();
    vi.mocked(assistantConfigApi.createSubAgent).mockRejectedValue(
      new ApiError(409, "A sub-agent with that name already exists"),
    );
    renderPage();

    await waitFor(() =>
      expect(vi.mocked(assistantConfigApi.listSubAgents)).toHaveBeenCalled(),
    );
    const loadsBeforeSave = vi.mocked(assistantConfigApi.listSubAgents).mock.calls.length;

    await user.click(newSubAgentButton());
    await user.type(nameField(), CONTINUITY.name);
    await user.type(promptField(), "Guard the facts.");
    await user.click(saveButton());

    await waitFor(() =>
      expect(vi.mocked(assistantConfigApi.createSubAgent)).toHaveBeenCalledTimes(1),
    );

    // The error is reported on the name field, not on the prompt.
    await waitFor(() => expect(nameField()).toBeInvalid());
    expect(promptField()).not.toBeInvalid();

    // The modal is still open and the admin's input survived.
    expect(modalTitle("New sub-agent")).not.toBeNull();
    expect(nameField()).toHaveValue(CONTINUITY.name);
    expect(promptField()).toHaveValue("Guard the facts.");

    // Nothing was re-loaded.
    expect(vi.mocked(assistantConfigApi.listSubAgents).mock.calls.length).toBe(loadsBeforeSave);
  });
});

/* ---------------------------------------------------------------- DoD-8 -----*/

describe("a blank name is blocked client-side (DoD-8)", () => {
  it("DoD-8: a blank or whitespace name is the draft's one client error; a real name clears it", () => {
    const draft = newDraft(null);

    // Fresh create draft: the name is empty.
    expect(Object.keys(draft.clientErrors)).toEqual(["name"]);
    expect(draft.canSubmit).toBe(false);

    runInAction(() => {
      draft.name = "   ";
    });
    expect(Object.keys(draft.clientErrors)).toEqual(["name"]);
    expect(draft.canSubmit).toBe(false);

    // Nothing else is required: no prompt, no tools, no modes, inherit model.
    runInAction(() => {
      draft.name = "Fact keeper";
      draft.systemPrompt = "";
      draft.selectedTools = new Set<string>();
      draft.selectedModes = new Set<string>();
    });
    expect(draft.clientErrors).toEqual({});
    expect(draft.canSubmit).toBe(true);
  });

  it("DoD-8: Save is disabled and NO api call is made while the name is blank (UC-096 exception flow)", async () => {
    const user = userEvent.setup();
    renderModal(null);

    expect(saveButton()).toBeDisabled();
    await user.click(saveButton());
    expect(vi.mocked(assistantConfigApi.createSubAgent)).not.toHaveBeenCalled();

    // Whitespace only is still blank.
    await user.type(nameField(), "   ");
    expect(saveButton()).toBeDisabled();
    await user.click(saveButton());
    expect(vi.mocked(assistantConfigApi.createSubAgent)).not.toHaveBeenCalled();

    // A real name unblocks it — the control is not simply always disabled.
    await user.clear(nameField());
    await user.type(nameField(), "Fact keeper");
    expect(saveButton()).toBeEnabled();
  });
});

/* ---------------------------------------------------------------- DoD-9 -----*/

describe("editing an existing sub-agent (DoD-9)", () => {
  it("DoD-9: the draft seeds name, prompt, model pair, tools and modes from the row (US-114.AC-1)", () => {
    const draft = newDraft(CONTINUITY);

    expect(draft.name).toBe(CONTINUITY.name);
    expect(draft.systemPrompt).toBe(CONTINUITY.system_prompt);
    expect(draft.llmServerId).toBe(LOCAL.id);
    expect(draft.modelName).toBe("qwen-72b");
    expect(Array.from(draft.selectedTools).sort()).toEqual([WEB_SEARCH.name]);
    expect(Array.from(draft.selectedModes).sort()).toEqual(
      [WRITE_CHAPTER, EDIT_FACT].sort(),
    );
  });

  it("DoD-9: the row's Edit action opens THAT sub-agent's form, seeded (UC-097 step 2)", async () => {
    const user = userEvent.setup();
    mockAllLoaded();
    renderPage();

    await openRowMenu(user, CONTINUITY.name);
    await clickMenuItem(user, "Edit");

    expect(modalTitle("Edit sub-agent")).not.toBeNull();
    expect(nameField()).toHaveValue(CONTINUITY.name);
    expect(promptField()).toHaveValue(CONTINUITY.system_prompt);
    expect((modelSelect() as HTMLInputElement).value).toContain("qwen-72b");
    expect(checkboxNamed(WEB_SEARCH.name)).toBeChecked();
    expect(checkboxNamed(LIST_CODEX.name)).not.toBeChecked();
    expect(checkboxNamed(MODE_LABEL[WRITE_CHAPTER])).toBeChecked();
    expect(checkboxNamed(MODE_LABEL[EDIT_LOCATION])).not.toBeChecked();
  });

  it("DoD-9: saving the edits calls update with that id and the edited values, then refreshes (UC-097 step 3)", async () => {
    const user = userEvent.setup();
    mockAllLoaded();
    renderPage();

    await openRowMenu(user, CONTINUITY.name);
    await clickMenuItem(user, "Edit");
    const loadsBeforeSave = vi.mocked(assistantConfigApi.listSubAgents).mock.calls.length;

    await user.clear(nameField());
    await user.type(nameField(), "Continuity guard");
    await user.clear(promptField());
    await user.type(promptField(), "Watch the timeline.");
    await user.click(checkboxNamed(LIST_CODEX.name)); // add a tool
    await user.click(checkboxNamed(MODE_LABEL[EDIT_FACT])); // drop a mode
    await user.click(saveButton());

    await waitFor(() =>
      expect(vi.mocked(assistantConfigApi.updateSubAgent)).toHaveBeenCalledTimes(1),
    );
    const { id, body } = onlyUpdateCall();
    expect(id).toBe(CONTINUITY.id);
    expect(body.name).toBe("Continuity guard");
    expect(body.system_prompt).toBe("Watch the timeline.");
    expect([...(body.tool_names ?? [])].sort()).toEqual(
      [WEB_SEARCH.name, LIST_CODEX.name].sort(),
    );
    expect(body.mode_keys).toEqual([WRITE_CHAPTER]);
    expect(vi.mocked(assistantConfigApi.createSubAgent)).not.toHaveBeenCalled();

    await waitFor(() =>
      expect(vi.mocked(assistantConfigApi.listSubAgents).mock.calls.length).toBeGreaterThan(
        loadsBeforeSave,
      ),
    );
  });
});

/* --------------------------------------------------------------- DoD-10 -----*/

describe("the accessible-modes picker is the other end of the mode<->sub-agent link (DoD-10)", () => {
  it("DoD-10: all five modes are offered by label, with the stored mode_keys checked (US-112.AC-2)", () => {
    renderModal(CONTINUITY);

    for (const key of ALL_MODE_KEYS) {
      expect(checkboxNamed(MODE_LABEL[key])).toBeInTheDocument();
    }
    // CONTINUITY is accessible from write-chapter + edit-fact and nothing else.
    expect(checkboxNamed(MODE_LABEL[WRITE_CHAPTER])).toBeChecked();
    expect(checkboxNamed(MODE_LABEL[EDIT_FACT])).toBeChecked();
    expect(checkboxNamed(MODE_LABEL[EDIT_CHARACTER])).not.toBeChecked();
    expect(checkboxNamed(MODE_LABEL[EDIT_LOCATION])).not.toBeChecked();
    expect(checkboxNamed(MODE_LABEL[CLOSE_CHAPTER])).not.toBeChecked();
  });

  it("DoD-10: the mode selection is editable here and saved as mode_keys", async () => {
    const user = userEvent.setup();
    renderModal(NAMER);

    await user.click(checkboxNamed(MODE_LABEL[CLOSE_CHAPTER]));
    await user.click(saveButton());

    await waitFor(() =>
      expect(vi.mocked(assistantConfigApi.updateSubAgent)).toHaveBeenCalledTimes(1),
    );
    const { id, body } = onlyUpdateCall();
    expect(id).toBe(NAMER.id);
    expect(body.mode_keys).toEqual([CLOSE_CHAPTER]);
  });
});

/* --------------------------------------------------------------- DoD-11 -----*/

describe("disable and enable are row actions that refresh the list (DoD-11)", () => {
  it("DoD-11: an enabled row offers Disable, which calls the disable api for that sub-agent and refreshes (US-114.AC-2)", async () => {
    const user = userEvent.setup();
    mockAllLoaded();
    renderPage();

    await openRowMenu(user, CONTINUITY.name);
    expect(menuItemTexts()).toContain("Disable");
    expect(menuItemTexts()).not.toContain("Enable");
    const loadsBefore = vi.mocked(assistantConfigApi.listSubAgents).mock.calls.length;

    await clickMenuItem(user, "Disable");

    await waitFor(() =>
      expect(vi.mocked(assistantConfigApi.disableSubAgent)).toHaveBeenCalledTimes(1),
    );
    expect(vi.mocked(assistantConfigApi.disableSubAgent).mock.calls[0][0]).toBe(CONTINUITY.id);
    expect(vi.mocked(assistantConfigApi.enableSubAgent)).not.toHaveBeenCalled();
    await waitFor(() =>
      expect(vi.mocked(assistantConfigApi.listSubAgents).mock.calls.length).toBeGreaterThan(
        loadsBefore,
      ),
    );
  });

  it("DoD-11: a disabled row offers Enable instead, which calls the enable api and refreshes (US-114.AC-3)", async () => {
    const user = userEvent.setup();
    mockAllLoaded();
    renderPage();

    await openRowMenu(user, RETIRED.name);
    expect(menuItemTexts()).toContain("Enable");
    expect(menuItemTexts()).not.toContain("Disable");
    const loadsBefore = vi.mocked(assistantConfigApi.listSubAgents).mock.calls.length;

    await clickMenuItem(user, "Enable");

    await waitFor(() =>
      expect(vi.mocked(assistantConfigApi.enableSubAgent)).toHaveBeenCalledTimes(1),
    );
    expect(vi.mocked(assistantConfigApi.enableSubAgent).mock.calls[0][0]).toBe(RETIRED.id);
    expect(vi.mocked(assistantConfigApi.disableSubAgent)).not.toHaveBeenCalled();
    await waitFor(() =>
      expect(vi.mocked(assistantConfigApi.listSubAgents).mock.calls.length).toBeGreaterThan(
        loadsBefore,
      ),
    );
  });

  it("DoD-11: each action calls its endpoint and then re-runs the loader — the list comes back from the backend", async () => {
    const state = new SubAgentsPageState();
    vi.mocked(assistantConfigApi.listSubAgents)
      .mockResolvedValueOnce([CONTINUITY])
      .mockResolvedValueOnce([{ ...CONTINUITY, disabled: true }]);
    await loadSubAgentsPage(state);
    expect(state.subAgents.map((row) => row.disabled)).toEqual([false]);

    await disableSubAgentAction(state, CONTINUITY.id);

    expect(vi.mocked(assistantConfigApi.disableSubAgent)).toHaveBeenCalledTimes(1);
    expect(vi.mocked(assistantConfigApi.disableSubAgent).mock.calls[0][0]).toBe(CONTINUITY.id);
    // Re-loaded, not patched in place.
    expect(vi.mocked(assistantConfigApi.listSubAgents).mock.calls.length).toBeGreaterThan(1);
    expect(state.subAgents.map((row) => row.disabled)).toEqual([true]);

    const loadsBeforeEnable = vi.mocked(assistantConfigApi.listSubAgents).mock.calls.length;
    await enableSubAgentAction(state, CONTINUITY.id);

    expect(vi.mocked(assistantConfigApi.enableSubAgent)).toHaveBeenCalledTimes(1);
    expect(vi.mocked(assistantConfigApi.enableSubAgent).mock.calls[0][0]).toBe(CONTINUITY.id);
    expect(vi.mocked(assistantConfigApi.listSubAgents).mock.calls.length).toBeGreaterThan(
      loadsBeforeEnable,
    );
  });
});

/* --------------------------------------------------------------- DoD-12 -----*/

type MockLike = { mock: { calls: readonly unknown[] } };

function apiSurface(): Array<[string, MockLike]> {
  return [
    ["listSubAgents", vi.mocked(assistantConfigApi.listSubAgents)],
    ["listTools", vi.mocked(assistantConfigApi.listTools)],
    ["listModes", vi.mocked(assistantConfigApi.listModes)],
    ["listServers", vi.mocked(llmServersApi.listServers)],
    ["createSubAgent", vi.mocked(assistantConfigApi.createSubAgent)],
    ["updateSubAgent", vi.mocked(assistantConfigApi.updateSubAgent)],
    ["disableSubAgent", vi.mocked(assistantConfigApi.disableSubAgent)],
    ["enableSubAgent", vi.mocked(assistantConfigApi.enableSubAgent)],
    ["saveMode", vi.mocked(assistantConfigApi.saveMode)],
  ];
}

function calledApiNames(): string[] {
  return apiSurface()
    .filter(([, fn]) => fn.mock.calls.length > 0)
    .map(([name]) => name);
}

describe("there is no delete anywhere (DoD-12)", () => {
  it("DoD-12: the row menu offers exactly Edit + Disable (or Enable) — no destructive item (UC-097 'No hard delete')", async () => {
    const user = userEvent.setup();
    mockAllLoaded();
    renderPage();

    await openRowMenu(user, CONTINUITY.name);
    expect(menuItemTexts().sort()).toEqual(["Disable", "Edit"]);
    for (const text of menuItemTexts()) {
      expect(text).not.toMatch(/delete|remove|destroy/i);
    }
  });

  it("DoD-12: a disabled row's menu is Edit + Enable — still no destructive item", async () => {
    const user = userEvent.setup();
    mockAllLoaded();
    renderPage();

    await openRowMenu(user, RETIRED.name);
    expect(menuItemTexts().sort()).toEqual(["Edit", "Enable"]);
  });

  it("DoD-12: no destructive control is rendered on the page, and no delete-shaped function exists to call", async () => {
    mockAllLoaded();
    renderPage();
    await bodyRows();

    for (const control of screen.getAllByRole("button")) {
      const label =
        `${control.textContent ?? ""} ${control.getAttribute("aria-label") ?? ""}`.trim();
      expect(label).not.toMatch(/delete|remove|destroy/i);
    }
    // The wire module and the page-state module expose no removal at all
    // (`context.md` -> scope decision 6).
    expect(
      Object.keys(assistantConfigApi).filter((name) => /delete|remove|destroy/i.test(name)),
    ).toEqual([]);
    expect(
      Object.keys(subAgentsPageStateModule).filter((name) =>
        /delete|remove|destroy/i.test(name),
      ),
    ).toEqual([]);
  });

  it("DoD-12: a full interaction sweep calls only the page's own endpoints", async () => {
    const user = userEvent.setup();
    mockAllLoaded();
    renderPage();

    // Edit ... and back out.
    await openRowMenu(user, CONTINUITY.name);
    await clickMenuItem(user, "Edit");
    await user.click(cancelButton());
    // Disable.
    await openRowMenu(user, CONTINUITY.name);
    await clickMenuItem(user, "Disable");
    // Create ... and back out.
    await user.click(newSubAgentButton());
    await user.click(cancelButton());

    const allowed = [
      "listSubAgents",
      "listTools",
      "listModes",
      "listServers",
      "disableSubAgent",
    ];
    for (const name of calledApiNames()) {
      expect(allowed).toContain(name);
    }
  });
});

/* --------------------------------------------------------------- DoD-13 -----*/

describe("the tool picker is catalogue-driven at any size (DoD-13)", () => {
  it("DoD-13: an empty catalogue offers no tool and renders copy a one-entry catalogue does not", () => {
    // Empty catalogue ...
    const empty = renderModal(NAMER, { tools: [] });
    for (const tool of ALL_TOOLS) {
      expect(queryCheckboxNamed(tool.name)).toBeNull();
    }
    const emptyWords = bodyWords();
    empty.unmount();

    // ... versus the same form with one tool. Everything else is identical, so an
    // explanatory empty state is exactly the wording present only in the first
    // render. A blank box would render nothing of its own and fail here.
    const single = renderModal(NAMER, { tools: [WEB_SEARCH] });
    expect(checkboxNamed(WEB_SEARCH.name)).toBeInTheDocument();
    const populatedWords = new Set(bodyWords());
    single.unmount();

    expect(emptyWords.filter((word) => !populatedWords.has(word))).not.toHaveLength(0);
  });

  it("DoD-13: with an empty catalogue the form still submits, sending tool_names: []", async () => {
    const user = userEvent.setup();
    renderModal(null, { tools: [] });

    await user.type(nameField(), "Fact keeper");
    // The rest of the form is unaffected by the empty catalogue.
    expect(checkboxNamed(MODE_LABEL[EDIT_FACT])).toBeInTheDocument();
    await user.click(saveButton());

    await waitFor(() =>
      expect(vi.mocked(assistantConfigApi.createSubAgent)).toHaveBeenCalledTimes(1),
    );
    const body = onlyCreateBody();
    expect(Object.keys(body)).toContain("tool_names");
    expect(body.tool_names).toEqual([]);
  });

  it("DoD-13: the picker offers exactly the catalogue it is given — one entry, or many", () => {
    const single = renderModal(NAMER, { tools: [WEB_SEARCH] });
    expect(checkboxNamed(WEB_SEARCH.name)).toBeInTheDocument();
    expect(queryCheckboxNamed(READ_CHAPTER.name)).toBeNull();
    single.unmount();

    renderModal(NAMER, { tools: ALL_TOOLS });
    for (const tool of ALL_TOOLS) {
      expect(checkboxNamed(tool.name)).toBeInTheDocument();
    }
  });
});
