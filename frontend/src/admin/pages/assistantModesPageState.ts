import { makeAutoObservable, runInAction } from "mobx";
import * as assistantConfigApi from "../../api/assistantConfig";
import { ApiError } from "../../api/client";
import type { AssistantMode, AssistantTool, SubAgent } from "../../types/assistantConfig";

/**
 * Page state for `AssistantModesPage` (Admin SPA `/assistant-modes`, feature 012
 * step 007).
 *
 * Exactly the `llmServersPageState.ts:18-26` shape — `makeAutoObservable` in the
 * constructor, **no methods and no computeds** — but with **three** async trios
 * instead of one:
 *
 * - `modes` — the fixed five `AssistantMode` rows, in the order the api returns them;
 * - `tools` — the backend tool catalogue, which the editor's tool picker renders;
 * - `subAgents` — the sub-agent list, needed because a mode DTO carries
 *   `sub_agent_ids` only and the picker must show **names** (`007.context.md` → "The
 *   sub-agent name problem").
 *
 * There is **no mutation action here**: a mode save runs from `ModeEditorDraft`, and
 * the page re-calls {@link loadModesPage} afterwards (no optimistic updates). Modal
 * targets live in the page's component-local `useState`, never here.
 *
 * Skeleton: the observable fields are fully declared; the external loader's signature
 * is frozen with a throwing stub body for the coder to implement.
 */
export class AssistantModesPageState {
  modes: AssistantMode[] = [];
  modesStatus: "idle" | "loading" | "ready" | "error" = "idle";
  modesError: string | null = null;

  tools: AssistantTool[] = [];
  toolsStatus: "idle" | "loading" | "ready" | "error" = "idle";
  toolsError: string | null = null;

  subAgents: SubAgent[] = [];
  subAgentsStatus: "idle" | "loading" | "ready" | "error" = "idle";
  subAgentsError: string | null = null;

  constructor() {
    makeAutoObservable(this);
  }
}

/**
 * Load all three resources **in parallel** and commit them, following the standard
 * loader body shape (`context.md` → frontend constraints, `llmServersPageState.ts:33`):
 *
 * `runInAction` set all three statuses to `"loading"` and clear all three errors →
 * await `assistantConfigApi.listModes` / `listTools` / `listSubAgents` together →
 * `if (signal?.aborted) return;` → `runInAction` commit the three trios. On error:
 * aborted-guard first, then `err instanceof ApiError` ? `runInAction` record the
 * error and status `"error"` : **rethrow**.
 *
 * The three calls are awaited as one `Promise.all`, so a single failure sinks the
 * whole page load: all three trios go to `"error"` with that message, which is what
 * the page's `modesError ?? toolsError ?? subAgentsError` renders (and what stops the
 * table rendering at all — the editor is unusable without the catalogue anyway).
 *
 * Also the page's refresh-after-save call — a mode save never mutates state directly.
 */
export async function loadModesPage(
  state: AssistantModesPageState,
  signal?: AbortSignal,
): Promise<void> {
  runInAction(() => {
    state.modesStatus = "loading";
    state.modesError = null;
    state.toolsStatus = "loading";
    state.toolsError = null;
    state.subAgentsStatus = "loading";
    state.subAgentsError = null;
  });

  try {
    const [modes, tools, subAgents] = await Promise.all([
      assistantConfigApi.listModes(signal),
      assistantConfigApi.listTools(signal),
      assistantConfigApi.listSubAgents(signal),
    ]);
    if (signal?.aborted) return;
    runInAction(() => {
      state.modes = modes;
      state.modesStatus = "ready";
      state.tools = tools;
      state.toolsStatus = "ready";
      state.subAgents = subAgents;
      state.subAgentsStatus = "ready";
    });
  } catch (err) {
    if (signal?.aborted) return;
    if (err instanceof ApiError) {
      const message = err.message || "Could not load the assistant configuration.";
      runInAction(() => {
        state.modesError = message;
        state.modesStatus = "error";
        state.toolsError = message;
        state.toolsStatus = "error";
        state.subAgentsError = message;
        state.subAgentsStatus = "error";
      });
      return;
    }
    throw err;
  }
}
