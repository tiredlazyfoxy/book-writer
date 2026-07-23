import { makeAutoObservable, runInAction } from "mobx";
import * as llmServersApi from "../../../api/llmServers";
import { ApiError } from "../../../api/client";

/**
 * Component-local draft for the embedding-designation modal — held via
 * `useState(() => new EmbeddingModalDraft(server.embedding_model))`. Observable
 * fields + a pure `get canSubmit` only (no effectful methods); the effectful
 * probe/save live in the external functions below.
 *
 * `selected` is a single model (or null) seeded from the server's current embedding
 * model so a failed probe never loses the prior designation.
 */
export class EmbeddingModalDraft {
  available: string[] = [];
  selected: string | null;
  filter = "";

  probeStatus: "idle" | "loading" | "ready" | "error" = "idle";
  probeError: string | null = null;
  saveStatus: "idle" | "loading" | "ready" | "error" = "idle";
  saveError: string | null = null;

  constructor(initialModel: string | null) {
    this.selected = initialModel;
    makeAutoObservable(this);
  }

  /** True when a model is chosen and no save is in flight. */
  get canSubmit(): boolean {
    return this.selected !== null && this.saveStatus !== "loading";
  }
}

/**
 * Effect (unimplemented — coder fills). Probe on open: `probeModels(serverId)` sets
 * `draft.available` on success; on error sets `draft.probeError` and clears
 * `available` to `[]` but MUST NOT touch `draft.selected` (failed-probe resilience,
 * D9). Abort-guarded via `signal`.
 */
export async function probeModelsAction(
  draft: EmbeddingModalDraft,
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
 * Effect (unimplemented — coder fills). Guard `draft.selected !== null`, then
 * `setEmbedding(serverId, draft.selected)` (replaces any prior designation, US-014);
 * on success set status "ready" and invoke `onSaved` (the page refresh).
 * Abort-guarded via `signal`.
 */
export async function submitEmbedding(
  draft: EmbeddingModalDraft,
  serverId: string,
  onSaved: () => void,
  signal?: AbortSignal,
): Promise<void> {
  if (draft.selected === null) return;
  const model = draft.selected;

  runInAction(() => {
    draft.saveError = null;
    draft.saveStatus = "loading";
  });

  try {
    await llmServersApi.setEmbedding(serverId, model, signal);
  } catch (err) {
    if (err instanceof ApiError) {
      runInAction(() => {
        draft.saveError = err.message || "Could not set the embedding model.";
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
