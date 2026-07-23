import { makeAutoObservable, runInAction } from "mobx";
import * as adminApi from "../../api/admin";
import { ApiError } from "../../api/client";
import type { AdminUserResponse } from "../../types/admin";

/**
 * Page state for `UsersPage` (Admin SPA root `/`).
 *
 * Holds only the users-list async trio (`users` / `usersStatus` / `usersError`)
 * plus `makeAutoObservable`. Per the MobX hard rules it has NO effectful methods —
 * loading and the disable action live in the external `(state, …, signal)`
 * functions below. Modal open flags / targets are component-local `useState` in the
 * page (decision 10), never page state.
 *
 * Skeleton: observable fields are fully declared; the external effect-fn signatures
 * are frozen with throwing stub bodies for the coder to implement.
 */
export class UsersPageState {
  users: AdminUserResponse[] = [];
  usersStatus: "idle" | "loading" | "ready" | "error" = "idle";
  usersError: string | null = null;

  constructor() {
    makeAutoObservable(this);
  }
}

/**
 * Load the users list into `state`: set `usersStatus = "loading"`, await
 * `adminApi.listUsers(signal)`, then `runInAction` the trio on success; on error
 * early-return when `signal.aborted`, else `runInAction` the error state.
 */
export async function loadUsers(state: UsersPageState, signal?: AbortSignal): Promise<void> {
  runInAction(() => {
    state.usersStatus = "loading";
    state.usersError = null;
  });
  try {
    const users = await adminApi.listUsers(signal);
    if (signal?.aborted) return;
    runInAction(() => {
      state.users = users;
      state.usersStatus = "ready";
    });
  } catch (err) {
    if (signal?.aborted) return;
    if (err instanceof ApiError) {
      runInAction(() => {
        state.usersError = err.message;
        state.usersStatus = "error";
      });
      return;
    }
    throw err;
  }
}

/**
 * Disable a user, then refresh the list: await `adminApi.disableUser(userId, signal)`
 * then re-call `loadUsers(state, signal)` (the local `refresh`) so the row reflects
 * the now-inactive backend state (no optimistic local edit). On error early-return
 * when `signal.aborted`, else record the error into the trio.
 */
export async function disableUserAction(
  state: UsersPageState,
  userId: string,
  signal?: AbortSignal,
): Promise<void> {
  try {
    await adminApi.disableUser(userId, signal);
    if (signal?.aborted) return;
    await loadUsers(state, signal);
  } catch (err) {
    if (signal?.aborted) return;
    if (err instanceof ApiError) {
      runInAction(() => {
        state.usersError = err.message;
      });
      return;
    }
    throw err;
  }
}
