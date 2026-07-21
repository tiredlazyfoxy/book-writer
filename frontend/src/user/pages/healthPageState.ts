import { makeAutoObservable, runInAction } from "mobx";
import * as healthApi from "../../api/health";
import type { HealthResponse } from "../../types/health";

/**
 * Page state for `HealthPage` (User SPA root `/`).
 *
 * Holds only the async-resource trio (`health` / `healthStatus` / `healthError`)
 * plus `makeAutoObservable`. Per the MobX hard rules it has NO effectful methods —
 * loading lives in the external `loadHealth(state, signal)` function below.
 */
export class HealthPageState {
  health: HealthResponse | null = null;
  healthStatus: "idle" | "loading" | "ready" | "error" = "idle";
  healthError: string | null = null;

  constructor() {
    makeAutoObservable(this);
  }
}

/**
 * Load the health result into `state`: set `healthStatus = 'loading'`, await
 * `healthApi.getHealth(signal)`, then `runInAction` the trio on success; on error
 * early-return when `signal.aborted`, else `runInAction` the error state.
 */
export async function loadHealth(state: HealthPageState, signal: AbortSignal): Promise<void> {
  state.healthStatus = "loading";
  state.healthError = null;
  try {
    const health = await healthApi.getHealth(signal);
    runInAction(() => {
      state.health = health;
      state.healthStatus = "ready";
    });
  } catch (err) {
    if (signal.aborted) return;
    runInAction(() => {
      state.healthStatus = "error";
      state.healthError = err instanceof Error ? err.message : String(err);
    });
  }
}
