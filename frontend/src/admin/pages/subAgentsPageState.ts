import { makeAutoObservable, runInAction } from "mobx";
import * as assistantConfigApi from "../../api/assistantConfig";
import * as llmServersApi from "../../api/llmServers";
import { ApiError } from "../../api/client";
import type { AssistantMode, AssistantTool, SubAgent } from "../../types/assistantConfig";
import type { LlmServer } from "../../types/llmServers";

/**
 * Page state for `SubAgentsPage` (Admin SPA `/sub-agents`, feature 012 step 008).
 *
 * Exactly the `llmServersPageState.ts:18-26` / `assistantModesPageState.ts:27-43`
 * shape — `makeAutoObservable` in a zero-argument constructor, **no methods and no
 * computeds** — with **four** async trios:
 *
 * - `subAgents` — every sub-agent, **disabled ones included** (the api does not filter);
 * - `tools` — the backend tool catalogue the form's tool picker renders;
 * - `modes` — the fixed five modes, for the accessible-modes picker (the sub-agent-side
 *   editor of the same `mode_subagent` rows the modes page writes, US-112.AC-2);
 * - `servers` — the LLM servers, loaded through the **existing** `api/llmServers`
 *   module, which already carries decoded `enabled_models` and `is_active`
 *   (`context.md` → "No new model-options endpoint"). The `is_active` filter is applied
 *   where the options are built (`SubAgentFormDraft.modelOptions`), not here.
 *
 * The two mutation actions below are disable / enable — there is **no delete action**
 * anywhere in this module, and none may be added (`context.md` → scope decision 6).
 * A sub-agent *save* runs from `SubAgentFormDraft`, and the page re-calls
 * {@link loadSubAgentsPage} afterwards; no optimistic updates anywhere. Modal targets
 * live in the page's component-local `useState`, never here.
 */
export class SubAgentsPageState {
  subAgents: SubAgent[] = [];
  subAgentsStatus: "idle" | "loading" | "ready" | "error" = "idle";
  subAgentsError: string | null = null;

  tools: AssistantTool[] = [];
  toolsStatus: "idle" | "loading" | "ready" | "error" = "idle";
  toolsError: string | null = null;

  modes: AssistantMode[] = [];
  modesStatus: "idle" | "loading" | "ready" | "error" = "idle";
  modesError: string | null = null;

  servers: LlmServer[] = [];
  serversStatus: "idle" | "loading" | "ready" | "error" = "idle";
  serversError: string | null = null;

  constructor() {
    makeAutoObservable(this);
  }
}

/**
 * Load all **four** resources in parallel and commit them, in the standard loader body
 * shape (`context.md` → frontend constraints, `llmServersPageState.ts:33`,
 * `assistantModesPageState.ts:62`):
 *
 * `runInAction` set all four statuses to `"loading"` and clear all four errors → await
 * `assistantConfigApi.listSubAgents` / `listTools` / `listModes` **and**
 * `llmServersApi.listServers` together as one `Promise.all` (each passed `signal`) →
 * `if (signal?.aborted) return;` → `runInAction` commit the four trios. On error:
 * aborted-guard first, then `err instanceof ApiError` ? `runInAction` record the message
 * into all four error fields and set all four statuses `"error"` : **rethrow**.
 *
 * A single failure therefore sinks the whole page load — the page renders
 * `subAgentsError ?? toolsError ?? modesError ?? serversError` and suppresses the table.
 *
 * Also the page's refresh-after-mutation call.
 */
export async function loadSubAgentsPage(
  state: SubAgentsPageState,
  signal?: AbortSignal,
): Promise<void> {
  runInAction(() => {
    state.subAgentsStatus = "loading";
    state.subAgentsError = null;
    state.toolsStatus = "loading";
    state.toolsError = null;
    state.modesStatus = "loading";
    state.modesError = null;
    state.serversStatus = "loading";
    state.serversError = null;
  });

  try {
    const [subAgents, tools, modes, servers] = await Promise.all([
      assistantConfigApi.listSubAgents(signal),
      assistantConfigApi.listTools(signal),
      assistantConfigApi.listModes(signal),
      llmServersApi.listServers(signal),
    ]);
    if (signal?.aborted) return;
    runInAction(() => {
      state.subAgents = subAgents;
      state.subAgentsStatus = "ready";
      state.tools = tools;
      state.toolsStatus = "ready";
      state.modes = modes;
      state.modesStatus = "ready";
      state.servers = servers;
      state.serversStatus = "ready";
    });
  } catch (err) {
    if (signal?.aborted) return;
    if (err instanceof ApiError) {
      const message = err.message || "Could not load the sub-agents.";
      runInAction(() => {
        state.subAgentsError = message;
        state.subAgentsStatus = "error";
        state.toolsError = message;
        state.toolsStatus = "error";
        state.modesError = message;
        state.modesStatus = "error";
        state.serversError = message;
        state.serversStatus = "error";
      });
      return;
    }
    throw err;
  }
}

/**
 * Disable a sub-agent, then refresh: await `assistantConfigApi.disableSubAgent(subAgentId,
 * signal)` then re-call `loadSubAgentsPage(state, signal)` — **no optimistic update**, the
 * refreshed row is the truth (the backend also detaches it from every mode, US-114.AC-2).
 * The `llmServersPageState.ts:67 deleteServerAction` body shape, minus the deletion: on
 * error early-return when `signal.aborted`, else record `err.message` into
 * `state.subAgentsError` when `err instanceof ApiError`, otherwise rethrow.
 */
export async function disableSubAgentAction(
  state: SubAgentsPageState,
  subAgentId: string,
  signal?: AbortSignal,
): Promise<void> {
  try {
    await assistantConfigApi.disableSubAgent(subAgentId, signal);
    if (signal?.aborted) return;
    await loadSubAgentsPage(state, signal);
  } catch (err) {
    if (signal?.aborted) return;
    if (err instanceof ApiError) {
      runInAction(() => {
        state.subAgentsError = err.message || "Could not disable the sub-agent.";
      });
      return;
    }
    throw err;
  }
}

/**
 * Enable a sub-agent, then refresh: await `assistantConfigApi.enableSubAgent(subAgentId,
 * signal)` then re-call `loadSubAgentsPage(state, signal)`. Same body shape as
 * {@link disableSubAgentAction}; re-enabling restores no mode links (US-114.AC-3).
 */
export async function enableSubAgentAction(
  state: SubAgentsPageState,
  subAgentId: string,
  signal?: AbortSignal,
): Promise<void> {
  try {
    await assistantConfigApi.enableSubAgent(subAgentId, signal);
    if (signal?.aborted) return;
    await loadSubAgentsPage(state, signal);
  } catch (err) {
    if (signal?.aborted) return;
    if (err instanceof ApiError) {
      runInAction(() => {
        state.subAgentsError = err.message || "Could not enable the sub-agent.";
      });
      return;
    }
    throw err;
  }
}
