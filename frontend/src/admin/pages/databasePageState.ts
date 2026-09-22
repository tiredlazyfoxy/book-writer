import { makeAutoObservable, runInAction } from "mobx";
import * as dbApi from "../../api/db";
import { ApiError } from "../../api/client";
import type { ConsistencyReport, VectorRebuildResponse } from "../../types/db";

/**
 * Page state for `DatabasePage` (Admin SPA `/database`).
 *
 * Holds only the consistency-report async trio (`report` / `reportStatus` /
 * `reportError`) plus transient action feedback (`actionError`, `rebuildResult`)
 * and `makeAutoObservable`. Per the MobX hard rules it has NO effectful methods —
 * loading, create/sync, import, rebuild, and export live in the external
 * `(state, …, signal)` functions below. File-picker / modal flags are
 * component-local `useState` in the page, never page state.
 */
export class DatabasePageState {
  report: ConsistencyReport | null = null;
  reportStatus: "idle" | "loading" | "ready" | "error" = "idle";
  reportError: string | null = null;
  actionError: string | null = null;
  rebuildResult: VectorRebuildResponse | null = null;

  constructor() {
    makeAutoObservable(this);
  }
}

/**
 * Load the consistency report into `state`: set `reportStatus = "loading"`, await
 * `dbApi.getConsistencyReport(signal)`, then `runInAction` the trio on success; on
 * error early-return when `signal.aborted`, else `runInAction` the error state.
 */
export async function loadReport(
  state: DatabasePageState,
  signal?: AbortSignal,
): Promise<void> {
  runInAction(() => {
    state.reportStatus = "loading";
    state.reportError = null;
  });
  try {
    const report = await dbApi.getConsistencyReport(signal);
    if (signal?.aborted) return;
    runInAction(() => {
      state.report = report;
      state.reportStatus = "ready";
    });
  } catch (err) {
    if (signal?.aborted) return;
    if (err instanceof ApiError) {
      runInAction(() => {
        state.reportError = err.message;
        state.reportStatus = "error";
      });
      return;
    }
    throw err;
  }
}

/**
 * Create a missing table, then reload the report so the row flips to `ok`. Friendly
 * fallback catch (no rethrow) so `void`-invoked effects never leak an unhandled
 * rejection; the failure lands in `actionError`.
 */
export async function createTableAction(
  state: DatabasePageState,
  name: string,
  signal?: AbortSignal,
): Promise<void> {
  runInAction(() => {
    state.actionError = null;
  });
  try {
    await dbApi.createTable(name, signal);
    if (signal?.aborted) return;
    await loadReport(state, signal);
  } catch (err) {
    if (signal?.aborted) return;
    runInAction(() => {
      state.actionError = err instanceof ApiError ? err.message : String(err);
    });
  }
}

/**
 * Sync a drifted table's schema, then reload the report so the row flips to `ok`.
 * Friendly fallback catch → `actionError`.
 */
export async function syncTableAction(
  state: DatabasePageState,
  name: string,
  signal?: AbortSignal,
): Promise<void> {
  runInAction(() => {
    state.actionError = null;
  });
  try {
    await dbApi.syncTable(name, signal);
    if (signal?.aborted) return;
    await loadReport(state, signal);
  } catch (err) {
    if (signal?.aborted) return;
    runInAction(() => {
      state.actionError = err instanceof ApiError ? err.message : String(err);
    });
  }
}

/**
 * Seed a table's missing required rows, then reload the report so the row flips to
 * `ok`. Same shape as `createTableAction` / `syncTableAction`: clear `actionError` →
 * call → reload the report → friendly fallback catch (no rethrow) so `void`-invoked
 * effects never leak an unhandled rejection; the failure lands in `actionError`. Adds
 * no state field — the reloaded report is the confirmation (F1 decision D-d).
 */
export async function seedTableAction(
  state: DatabasePageState,
  name: string,
  signal?: AbortSignal,
): Promise<void> {
  runInAction(() => {
    state.actionError = null;
  });
  try {
    await dbApi.seedTable(name, signal);
    if (signal?.aborted) return;
    await loadReport(state, signal);
  } catch (err) {
    if (signal?.aborted) return;
    runInAction(() => {
      state.actionError = err instanceof ApiError ? err.message : String(err);
    });
  }
}

/**
 * Import a database export, then reload the report on success. A 400 refusal
 * (US-019.AC-3) is caught and written to `actionError` so the page shows it and
 * does NOT claim success.
 */
export async function importAction(
  state: DatabasePageState,
  file: File,
  signal?: AbortSignal,
): Promise<void> {
  runInAction(() => {
    state.actionError = null;
  });
  try {
    await dbApi.importDatabase(file, signal);
    if (signal?.aborted) return;
    await loadReport(state, signal);
  } catch (err) {
    if (signal?.aborted) return;
    runInAction(() => {
      state.actionError = err instanceof ApiError ? err.message : String(err);
    });
  }
}

/**
 * Rebuild the LanceDB vector index and surface the resulting count/status into
 * `rebuildResult`. Friendly fallback catch → `actionError`.
 */
export async function rebuildAction(
  state: DatabasePageState,
  signal?: AbortSignal,
): Promise<void> {
  runInAction(() => {
    state.actionError = null;
    state.rebuildResult = null;
  });
  try {
    const result = await dbApi.rebuildIndex(signal);
    if (signal?.aborted) return;
    runInAction(() => {
      state.rebuildResult = result;
    });
  } catch (err) {
    if (signal?.aborted) return;
    runInAction(() => {
      state.actionError = err instanceof ApiError ? err.message : String(err);
    });
  }
}

/**
 * Trigger a database export download (fire-and-forget browser save). Takes no
 * signal — `dbApi.exportDatabase()` has none. Failures land in `actionError`.
 */
export async function exportAction(state: DatabasePageState): Promise<void> {
  try {
    await dbApi.exportDatabase();
  } catch (err) {
    runInAction(() => {
      state.actionError = err instanceof ApiError ? err.message : String(err);
    });
  }
}
