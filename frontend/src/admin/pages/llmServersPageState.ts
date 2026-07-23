import { makeAutoObservable, runInAction } from "mobx";
import * as llmServersApi from "../../api/llmServers";
import { ApiError } from "../../api/client";
import type { LlmServer } from "../../types/llmServers";

/**
 * Page state for `LlmServersPage` (Admin SPA `/llm-servers`).
 *
 * Holds only the servers-list async trio (`servers` / `serversStatus` /
 * `serversError`) plus `makeAutoObservable`. Per the MobX hard rules it has NO
 * effectful methods — loading, delete, and clear-embedding live in the external
 * `(state, …, signal)` functions below. Modal open flags / targets are
 * component-local `useState` in the page (step 006), never page state.
 *
 * Skeleton: observable fields are fully declared; the external effect-fn signatures
 * are frozen with throwing stub bodies for the coder to implement.
 */
export class LlmServersPageState {
  servers: LlmServer[] = [];
  serversStatus: "idle" | "loading" | "ready" | "error" = "idle";
  serversError: string | null = null;

  constructor() {
    makeAutoObservable(this);
  }
}

/**
 * Load the servers list into `state`: set `serversStatus = "loading"`, await
 * `llmServersApi.listServers(signal)`, then `runInAction` the trio on success; on
 * error early-return when `signal.aborted`, else `runInAction` the error state.
 */
export async function loadServers(
  state: LlmServersPageState,
  signal?: AbortSignal,
): Promise<void> {
  runInAction(() => {
    state.serversStatus = "loading";
    state.serversError = null;
  });
  try {
    const servers = await llmServersApi.listServers(signal);
    if (signal?.aborted) return;
    runInAction(() => {
      state.servers = servers;
      state.serversStatus = "ready";
    });
  } catch (err) {
    if (signal?.aborted) return;
    if (err instanceof ApiError) {
      runInAction(() => {
        state.serversError = err.message;
        state.serversStatus = "error";
      });
      return;
    }
    throw err;
  }
}

/**
 * Delete a server, then refresh the list: await `llmServersApi.deleteServer(id,
 * signal)` then re-call `loadServers(state, signal)` so the row disappears (no
 * optimistic local edit). On error early-return when `signal.aborted`, else record
 * the error into the trio.
 */
export async function deleteServerAction(
  state: LlmServersPageState,
  id: string,
  signal?: AbortSignal,
): Promise<void> {
  try {
    await llmServersApi.deleteServer(id, signal);
    if (signal?.aborted) return;
    await loadServers(state, signal);
  } catch (err) {
    if (signal?.aborted) return;
    if (err instanceof ApiError) {
      runInAction(() => {
        state.serversError = err.message;
      });
      return;
    }
    throw err;
  }
}

/**
 * Clear the embedding designation, then refresh the list: await
 * `llmServersApi.clearEmbedding(signal)` then re-call `loadServers(state, signal)`
 * so the indicator updates. On error early-return when `signal.aborted`, else record
 * the error into the trio.
 */
export async function clearEmbeddingAction(
  state: LlmServersPageState,
  signal?: AbortSignal,
): Promise<void> {
  try {
    await llmServersApi.clearEmbedding(signal);
    if (signal?.aborted) return;
    await loadServers(state, signal);
  } catch (err) {
    if (signal?.aborted) return;
    if (err instanceof ApiError) {
      runInAction(() => {
        state.serversError = err.message;
      });
      return;
    }
    throw err;
  }
}
