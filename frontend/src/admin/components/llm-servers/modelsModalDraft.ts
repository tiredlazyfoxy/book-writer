import { makeAutoObservable, runInAction } from "mobx";
import * as llmServersApi from "../../../api/llmServers";
import { ApiError } from "../../../api/client";

/**
 * Component-local draft for the enable-models modal — held via
 * `useState(() => new ModelsModalDraft(server.enabled_models))`. Observable fields +
 * a pure `get canSubmit` only (no effectful methods); the effectful probe/save live
 * in the external functions below.
 *
 * `selected` is seeded from the server's already-enabled models so a failed probe
 * never loses prior selections. Toggling a model is a component `onChange` that
 * REASSIGNS a fresh `Set` (observability-safe) — there is no toggle method here.
 */
export class ModelsModalDraft {
  available: string[] = [];
  selected: Set<string>;
  filter = "";

  probeStatus: "idle" | "loading" | "ready" | "error" = "idle";
  probeError: string | null = null;
  saveStatus: "idle" | "loading" | "ready" | "error" = "idle";
  saveError: string | null = null;

  constructor(initialEnabled: string[]) {
    this.selected = new Set(initialEnabled);
    makeAutoObservable(this);
  }

  /** True when no save is in flight. */
  get canSubmit(): boolean {
    return this.saveStatus !== "loading";
  }
}

/**
 * Effect (unimplemented — coder fills). Probe on open: `probeModels(serverId)` sets
 * `draft.available` on success; on error sets `draft.probeError` and clears
 * `available` to `[]` but MUST NOT touch `draft.selected` (failed-probe resilience,
 * D9). Abort-guarded via `signal`.
 */
export async function probeModelsAction(
  draft: ModelsModalDraft,
  serverId: string,
  signal?: AbortSignal,
): Promise<void> {
  runInAction(() => {
    draft.probeStatus = "loading";
    draft.probeError = null;
  });

  try {
    const models = await llmServersApi.probeModels(serverId, signal);
    if (signal?.aborted) return;
    runInAction(() => {
      draft.available = models;
      draft.probeStatus = "ready";
    });
  } catch (err) {
    if (signal?.aborted) return;
    if (err instanceof ApiError) {
      runInAction(() => {
        draft.probeError = err.message || "Could not probe the server.";
        draft.probeStatus = "error";
        draft.available = [];
      });
      return;
    }
    throw err;
  }
}

/**
 * Effect (unimplemented — coder fills). Save the chosen subset via
 * `setEnabledModels(serverId, Array.from(draft.selected).sort())`; on success set
 * status "ready" and invoke `onSaved` (the page refresh). Abort-guarded via `signal`.
 */
export async function submitEnabledModels(
  draft: ModelsModalDraft,
  serverId: string,
  onSaved: () => void,
  signal?: AbortSignal,
): Promise<void> {
  runInAction(() => {
    draft.saveError = null;
    draft.saveStatus = "loading";
  });

  try {
    await llmServersApi.setEnabledModels(serverId, Array.from(draft.selected).sort(), signal);
  } catch (err) {
    if (err instanceof ApiError) {
      runInAction(() => {
        draft.saveError = err.message || "Could not save the enabled models.";
        draft.saveStatus = "error";
      });
      return;
    }
    if (signal?.aborted) return;
    runInAction(() => {
      draft.saveStatus = "error";
    });
    throw err;
  }

  runInAction(() => {
    draft.saveStatus = "ready";
  });
  onSaved();
}
