/**
 * The assistant-config wire module — 012.assistant-config-editor /
 * 006.frontend-api-and-nav, DoD-3 · DoD-4 · DoD-5 · DoD-6 · DoD-7
 * (US-110.AC-1, US-111.AC-1, US-113.AC-1, US-113.AC-3, US-114.AC-1, US-114.AC-2,
 * UC-095 steps 1 + 3, UC-095 precondition).
 *
 * Bound to the frozen signatures in status.md -> `## Skeleton` (step 006):
 *   MODE_LABELS: Record<string, string>
 *   modeLabel(key: string): string                                    // sync
 *   listTools(signal?): Promise<AssistantTool[]>
 *   listModes(signal?): Promise<AssistantMode[]>
 *   saveMode(modeKey, body: UpdateAssistantModeRequest, signal?): Promise<AssistantMode>
 *   listSubAgents(signal?): Promise<SubAgent[]>
 *   createSubAgent(body: CreateSubAgentRequest, signal?): Promise<SubAgent>
 *   updateSubAgent(id, body: UpdateSubAgentRequest, signal?): Promise<SubAgent>
 *   disableSubAgent(id, signal?): Promise<SubAgent>
 *   enableSubAgent(id, signal?): Promise<SubAgent>
 * and, from `006.context.md` -> "The api layer":
 *   class ApiError extends Error { constructor(status, message, details?) }
 *   request<T>(url, opts): Promise<T>          // opts: { method?; body?; signal? }
 *
 * This is the one spec in the feature that legitimately tests the HTTP boundary
 * rather than mocking `api/` (`006.context.md` -> "Testing notes"): the module
 * under test IS the api layer, so `api/client` — never `fetch` — is mocked, and
 * the URL / method / body / signal handed to `request` are the observable
 * contract. The `importOriginal` spread keeps the REAL `ApiError` class, which
 * DoD-6 is about.
 *
 * Expected values come from the spec, never from code:
 *   - the URL family and every path is `005.admin-routes.md`'s frozen route table
 *     under `BASE = "/api/admin/assistant-config"` (the step's Interface intent);
 *   - the methods are that same table (GET reads, PUT saves, POST create +
 *     disable/enable, the last two ZERO-body);
 *   - list calls return the UNWRAPPED `.items` array — the envelope is not
 *     modelled on the frontend at all (`context.md` -> frontend constraints);
 *   - ids cross the wire as strings (`context.md`: "Every id is a `str` at the
 *     JSON boundary"), so the id fixtures are strings beyond 2^53;
 *   - the five mode keys are the product's fixed system set (features.md
 *     FEAT-020 note / assistant-config.md: edit-character, edit-location,
 *     edit-fact, write-chapter, close-chapter), and "Edit character" is the
 *     step's own worked example of a human-readable label.
 *
 * An omitted `method` IS a GET (fetch semantics), so the read assertions accept
 * either an absent `method` or an explicit "GET" — and nothing else.
 *
 * `globals: false`: every primitive is imported explicitly. `restoreMocks` wipes
 * implementations between tests, so each case sets its own via `vi.mocked(...)`.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import type {
  AssistantMode,
  AssistantTool,
  CreateSubAgentRequest,
  SubAgent,
  UpdateAssistantModeRequest,
  UpdateSubAgentRequest,
} from "../../src/types/assistantConfig";
import { ApiError, request } from "../../src/api/client";
import * as assistantConfigApi from "../../src/api/assistantConfig";

// Module-factory mock with `importOriginal`: only `request` is replaced, so
// `ApiError` stays the real class the module under test lets propagate (DoD-6).
vi.mock("../../src/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../src/api/client")>();
  return { ...actual, request: vi.fn() };
});

/** The options bag `request` accepts — read off the frozen signature itself. */
type ClientOpts = Parameters<typeof request>[1];

/** The api family's base path (`006.frontend-api-and-nav.md` -> Interface intent). */
const BASE = "/api/admin/assistant-config";

/** A snowflake id as it crosses the wire: a string beyond 2^53. */
const SUB_AGENT_ID = "9007199254740993";

/** The fixed system set of five mode keys (FEAT-020 / assistant-config.md). */
const MODE_KEYS = [
  "edit-character",
  "edit-location",
  "edit-fact",
  "write-chapter",
  "close-chapter",
] as const;

/** The single `request` call the function under test must have made. */
function onlyCall(): { url: string; opts: ClientOpts } {
  const calls = vi.mocked(request).mock.calls;
  expect(calls).toHaveLength(1);
  const [url, opts] = calls[0];
  return { url, opts };
}

/** An absent `method` is a GET, per fetch semantics. */
function methodOf(opts: ClientOpts): string {
  return (opts?.method ?? "GET").toUpperCase();
}

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

const MODE_BODY: UpdateAssistantModeRequest = {
  system_prompt: "Stay in third person.",
  tool_names: ["web_search"],
  sub_agent_ids: [SUB_AGENT_ID],
};

const CREATE_BODY: CreateSubAgentRequest = {
  name: "Continuity checker",
  system_prompt: "Check the chapter for continuity errors.",
  llm_server_id: null,
  model_name: null,
  tool_names: ["web_search"],
  mode_keys: ["close-chapter"],
};

const UPDATE_BODY: UpdateSubAgentRequest = {
  name: "Continuity checker v2",
  system_prompt: "Re-check the chapter for continuity errors.",
  llm_server_id: "7",
  model_name: "gpt-4o-mini",
  tool_names: [],
  mode_keys: [],
};

beforeEach(() => {
  // `restoreMocks` wipes implementations between tests; a benign default keeps a
  // case that forgets to arrange from hitting an undefined resolution.
  vi.mocked(request).mockResolvedValue({ items: [] });
});

describe("assistantConfig api — modes (DoD-3)", () => {
  it("DoD-3: listModes GETs /modes, unwraps the items envelope and passes the signal", async () => {
    const modes = [makeMode("edit-character"), makeMode("write-chapter")];
    vi.mocked(request).mockResolvedValue({ items: modes });
    const controller = new AbortController();

    const result = await assistantConfigApi.listModes(controller.signal);

    const { url, opts } = onlyCall();
    expect(url).toBe(`${BASE}/modes`);
    expect(methodOf(opts)).toBe("GET");
    expect(opts?.signal).toBe(controller.signal);
    expect(Array.isArray(result)).toBe(true);
    expect(result).toEqual(modes);
  });

  it("DoD-3: listModes resolves to a plain empty array for an empty envelope, with no signal supplied", async () => {
    vi.mocked(request).mockResolvedValue({ items: [] });

    const result = await assistantConfigApi.listModes();

    expect(onlyCall().url).toBe(`${BASE}/modes`);
    expect(result).toEqual([]);
  });

  it("DoD-3: saveMode PUTs /modes/<key> with the update payload, returns the updated mode and passes the signal", async () => {
    const updated: AssistantMode = {
      ...makeMode("edit-fact"),
      system_prompt: MODE_BODY.system_prompt,
      tool_names: [...MODE_BODY.tool_names],
      sub_agent_ids: [...MODE_BODY.sub_agent_ids],
    };
    vi.mocked(request).mockResolvedValue(updated);
    const controller = new AbortController();

    const result = await assistantConfigApi.saveMode("edit-fact", MODE_BODY, controller.signal);

    const { url, opts } = onlyCall();
    expect(url).toBe(`${BASE}/modes/edit-fact`);
    expect(methodOf(opts)).toBe("PUT");
    expect(opts?.body).toEqual(MODE_BODY);
    expect(opts?.signal).toBe(controller.signal);
    expect(result).toEqual(updated);
  });

  it("DoD-3: saveMode addresses the mode key it was given", async () => {
    vi.mocked(request).mockResolvedValue(makeMode("close-chapter"));

    await assistantConfigApi.saveMode("close-chapter", MODE_BODY);

    expect(onlyCall().url).toBe(`${BASE}/modes/close-chapter`);
  });
});

describe("assistantConfig api — sub-agents (DoD-4)", () => {
  it("DoD-4: listSubAgents GETs /sub-agents, unwraps the items envelope and passes the signal", async () => {
    const subAgents = [makeSubAgent(SUB_AGENT_ID, "Continuity checker"), makeSubAgent("42", "Namer")];
    vi.mocked(request).mockResolvedValue({ items: subAgents });
    const controller = new AbortController();

    const result = await assistantConfigApi.listSubAgents(controller.signal);

    const { url, opts } = onlyCall();
    expect(url).toBe(`${BASE}/sub-agents`);
    expect(methodOf(opts)).toBe("GET");
    expect(opts?.signal).toBe(controller.signal);
    expect(Array.isArray(result)).toBe(true);
    expect(result).toEqual(subAgents);
  });

  it("DoD-4: createSubAgent POSTs /sub-agents with the payload and returns the created sub-agent", async () => {
    const created = makeSubAgent(SUB_AGENT_ID, CREATE_BODY.name);
    vi.mocked(request).mockResolvedValue(created);
    const controller = new AbortController();

    const result = await assistantConfigApi.createSubAgent(CREATE_BODY, controller.signal);

    const { url, opts } = onlyCall();
    expect(url).toBe(`${BASE}/sub-agents`);
    expect(methodOf(opts)).toBe("POST");
    expect(opts?.body).toEqual(CREATE_BODY);
    expect(opts?.signal).toBe(controller.signal);
    expect(result).toEqual(created);
    expect(result.id).toBe(SUB_AGENT_ID);
  });

  it("DoD-4: updateSubAgent PUTs /sub-agents/<id> with the payload and returns the updated sub-agent", async () => {
    const updated: SubAgent = {
      ...makeSubAgent(SUB_AGENT_ID, UPDATE_BODY.name),
      llm_server_id: UPDATE_BODY.llm_server_id,
      model_name: UPDATE_BODY.model_name,
    };
    vi.mocked(request).mockResolvedValue(updated);
    const controller = new AbortController();

    const result = await assistantConfigApi.updateSubAgent(
      SUB_AGENT_ID,
      UPDATE_BODY,
      controller.signal,
    );

    const { url, opts } = onlyCall();
    expect(url).toBe(`${BASE}/sub-agents/${SUB_AGENT_ID}`);
    expect(methodOf(opts)).toBe("PUT");
    expect(opts?.body).toEqual(UPDATE_BODY);
    expect(opts?.signal).toBe(controller.signal);
    expect(result).toEqual(updated);
  });

  it("DoD-4: disableSubAgent POSTs /sub-agents/<id>/disable with no body and returns the disabled sub-agent", async () => {
    const disabled = makeSubAgent(SUB_AGENT_ID, "Continuity checker", true);
    vi.mocked(request).mockResolvedValue(disabled);
    const controller = new AbortController();

    const result = await assistantConfigApi.disableSubAgent(SUB_AGENT_ID, controller.signal);

    const { url, opts } = onlyCall();
    expect(url).toBe(`${BASE}/sub-agents/${SUB_AGENT_ID}/disable`);
    expect(methodOf(opts)).toBe("POST");
    expect(opts?.body).toBeUndefined();
    expect(opts?.signal).toBe(controller.signal);
    expect(result).toEqual(disabled);
    expect(result.disabled).toBe(true);
  });

  it("DoD-4: enableSubAgent POSTs /sub-agents/<id>/enable with no body and returns the enabled sub-agent", async () => {
    const enabled = makeSubAgent(SUB_AGENT_ID, "Continuity checker", false);
    vi.mocked(request).mockResolvedValue(enabled);
    const controller = new AbortController();

    const result = await assistantConfigApi.enableSubAgent(SUB_AGENT_ID, controller.signal);

    const { url, opts } = onlyCall();
    expect(url).toBe(`${BASE}/sub-agents/${SUB_AGENT_ID}/enable`);
    expect(methodOf(opts)).toBe("POST");
    expect(opts?.body).toBeUndefined();
    expect(opts?.signal).toBe(controller.signal);
    expect(result).toEqual(enabled);
    expect(result.disabled).toBe(false);
  });
});

describe("assistantConfig api — the tool catalogue (DoD-5)", () => {
  it("DoD-5: listTools GETs /tools and unwraps to a plain array of { name, description }", async () => {
    const tools = [
      makeTool("web_search", "Search the web."),
      makeTool("read_chapter", "Read a chapter's text."),
    ];
    vi.mocked(request).mockResolvedValue({ items: tools });
    const controller = new AbortController();

    const result = await assistantConfigApi.listTools(controller.signal);

    const { url, opts } = onlyCall();
    expect(url).toBe(`${BASE}/tools`);
    expect(methodOf(opts)).toBe("GET");
    expect(opts?.signal).toBe(controller.signal);
    expect(Array.isArray(result)).toBe(true);
    expect(result).toEqual(tools);
    expect(result[0].name).toBe("web_search");
    expect(result[0].description).toBe("Search the web.");
  });

  it("DoD-5: listTools resolves to a plain empty array when the catalogue is empty", async () => {
    vi.mocked(request).mockResolvedValue({ items: [] });

    const result = await assistantConfigApi.listTools();

    expect(result).toEqual([]);
  });
});

describe("assistantConfig api — error propagation (DoD-6)", () => {
  it("DoD-6: a 409 from createSubAgent surfaces as the very same ApiError, status intact", async () => {
    const err = new ApiError(409, "Sub-agent name already taken");
    vi.mocked(request).mockRejectedValue(err);

    await expect(assistantConfigApi.createSubAgent(CREATE_BODY)).rejects.toBe(err);

    const caught: unknown = await assistantConfigApi
      .createSubAgent(CREATE_BODY)
      .then(() => undefined)
      .catch((reason: unknown) => reason);
    expect(caught).toBeInstanceOf(ApiError);
    expect((caught as ApiError).status).toBe(409);
  });

  it("DoD-6: a 400 surfaces with status 400, so a caller can branch 409 vs 400", async () => {
    const err = new ApiError(400, "Unknown tool");
    vi.mocked(request).mockRejectedValue(err);

    const caught: unknown = await assistantConfigApi
      .saveMode("edit-character", MODE_BODY)
      .then(() => undefined)
      .catch((reason: unknown) => reason);

    expect(caught).toBe(err);
    expect(caught).toBeInstanceOf(ApiError);
    expect((caught as ApiError).status).toBe(400);
  });

  it("DoD-6: an error from a list call is not swallowed into an empty array", async () => {
    const err = new ApiError(403, "Forbidden");
    vi.mocked(request).mockRejectedValue(err);

    await expect(assistantConfigApi.listSubAgents()).rejects.toBe(err);
  });
});

describe("assistantConfig api — mode labels (DoD-7)", () => {
  it("DoD-7: MODE_LABELS is total over exactly the five system mode keys", () => {
    expect(Object.keys(assistantConfigApi.MODE_LABELS).sort()).toEqual([...MODE_KEYS].sort());
  });

  it("DoD-7: modeLabel returns a human-readable label for each of the five keys", () => {
    for (const key of MODE_KEYS) {
      const label = assistantConfigApi.modeLabel(key);

      expect(typeof label).toBe("string");
      expect(label.length).toBeGreaterThan(0);
      expect(label).not.toBe(key);
      expect(label).toBe(assistantConfigApi.MODE_LABELS[key]);
    }
  });

  it("DoD-7: the label for `edit-character` is `Edit character`", () => {
    expect(assistantConfigApi.modeLabel("edit-character")).toBe("Edit character");
  });

  it("DoD-7: modeLabel degrades to the raw key for an unknown one", () => {
    expect(assistantConfigApi.modeLabel("not-a-mode")).toBe("not-a-mode");
    expect(assistantConfigApi.modeLabel("edit-charactr")).toBe("edit-charactr");
  });
});
