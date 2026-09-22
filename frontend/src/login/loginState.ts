import { makeAutoObservable, runInAction } from "mobx";
import * as authApi from "../api/auth";
import { ApiError } from "../api/client";
import { setTokens } from "../auth";

// <Component>State for the login-entry first-run wizard (decision 9): the login
// entry is exempt from <Page>State/router machinery but still binds the MobX
// rules — observable fields + pure `get` computeds only, NO effectful methods.
// The loads/submits are the external `(state, signal?)` functions below.
//
// Skeleton: observable fields are fully declared; `get` computed and effect-fn
// SIGNATURES are frozen with stub bodies for the coder to implement.

export type SetupMode = "create" | "import";
export type LoadStatus = "idle" | "loading" | "ready" | "error";

export class LoginState {
  /** Active wizard tab. */
  mode: SetupMode = "create";

  // --- Create-tab drafts ---
  username = "";
  password = "";
  passwordConfirm = "";

  // --- Import-tab draft ---
  importFile: File | null = null;

  // --- Startup readiness (auth-status) trio ---
  needsSetup: boolean | null = null;
  needsSetupStatus: LoadStatus = "idle";
  needsSetupError: string | null = null;

  // --- Submit status pair (no stored payload: create navigates, import re-reads) ---
  submitStatus: LoadStatus = "idle";
  submitError: string | null = null;

  // --- Login-form drafts (needs_setup === false branch) ---
  loginUsername = "";
  loginPassword = "";

  // --- Login submit status trio (mirrors the wizard submit trio) ---
  loginStatus: LoadStatus = "idle";
  loginError: string | null = null;

  constructor() {
    makeAutoObservable(this);
  }

  /** True when the login form may be submitted (both fields non-empty, not mid-submit). */
  get canSubmitLogin(): boolean {
    return (
      this.loginStatus !== "loading" &&
      this.loginUsername.trim().length > 0 &&
      this.loginPassword.length > 0
    );
  }

  /** True when the create password is shorter than the 8-char minimum. */
  get passwordTooShort(): boolean {
    return this.password.length < 8;
  }

  /** True when `password` equals `passwordConfirm`. */
  get passwordsMatch(): boolean {
    return this.password === this.passwordConfirm;
  }

  /** True when the Create form may be submitted (valid drafts, not mid-submit). */
  get canSubmitCreate(): boolean {
    return (
      this.submitStatus !== "loading" &&
      this.username.trim().length > 0 &&
      !this.passwordTooShort &&
      this.passwordsMatch
    );
  }

  /** True when the Import form may be submitted (a file is selected, not mid-submit). */
  get canSubmitImport(): boolean {
    return this.submitStatus !== "loading" && this.importFile !== null;
  }
}

/**
 * Load the auth-status into `state`: sets the readiness trio to loading, awaits
 * `authApi.getAuthStatus(signal)`, records `needsSetup` on success, records the
 * error on failure (early-return when `signal.aborted`).
 */
export async function loadStatus(state: LoginState, signal?: AbortSignal): Promise<void> {
  runInAction(() => {
    state.needsSetupStatus = "loading";
    state.needsSetupError = null;
  });
  try {
    const res = await authApi.getAuthStatus(signal);
    if (signal?.aborted) return;
    runInAction(() => {
      state.needsSetup = res.needs_setup;
      state.needsSetupStatus = "ready";
    });
  } catch (err) {
    if (signal?.aborted) return;
    runInAction(() => {
      state.needsSetupStatus = "error";
      state.needsSetupError =
        err instanceof ApiError ? err.message : "Failed to reach the server.";
    });
  }
}

/**
 * Submit the Create form: `authApi.setupCreate(body, signal)`; on success
 * `setTokens(access, refresh)` then navigate to `/` via `window.location.href`; on refusal
 * record the server error into the submit pair.
 */
export async function submitCreate(state: LoginState, signal?: AbortSignal): Promise<void> {
  runInAction(() => {
    state.submitStatus = "loading";
    state.submitError = null;
  });
  try {
    const res = await authApi.setupCreate(
      {
        admin_username: state.username,
        password: state.password,
        password_confirm: state.passwordConfirm,
      },
      signal,
    );
    setTokens(res.access_token, res.refresh_token);
    window.location.href = "/";
  } catch (err) {
    if (signal?.aborted) return;
    runInAction(() => {
      state.submitStatus = "error";
      state.submitError =
        err instanceof ApiError ? err.message : "Setup failed. Please try again.";
    });
  }
}

/**
 * Submit the Import form: `authApi.setupImport(file, signal)`; on success record
 * the now-configured state (`needsSetup`); on refusal record the error and stay
 * on the setup screen.
 */
export async function submitImport(state: LoginState, signal?: AbortSignal): Promise<void> {
  if (!state.importFile) return;
  runInAction(() => {
    state.submitStatus = "loading";
    state.submitError = null;
  });
  try {
    const res = await authApi.setupImport(state.importFile, signal);
    if (signal?.aborted) return;
    runInAction(() => {
      state.needsSetup = res.needs_setup;
      state.submitStatus = "ready";
    });
  } catch (err) {
    if (signal?.aborted) return;
    runInAction(() => {
      state.submitStatus = "error";
      state.submitError =
        err instanceof ApiError ? err.message : "Import failed. Please try again.";
    });
  }
}

/**
 * Submit the Login form: `authApi.login({username, password}, signal)`; on success
 * store BOTH tokens via `setTokens(access, refresh)` then navigate to `/` via
 * `window.location.href`; on `ApiError` record the generic refusal into the login
 * trio and do NOT navigate (early-return when `signal.aborted`).
 */
export async function handleLogin(state: LoginState, signal?: AbortSignal): Promise<void> {
  runInAction(() => {
    state.loginStatus = "loading";
    state.loginError = null;
  });
  try {
    const res = await authApi.login(
      { username: state.loginUsername, password: state.loginPassword },
      signal,
    );
    setTokens(res.access_token, res.refresh_token);
    window.location.href = "/";
  } catch (err) {
    if (signal?.aborted) return;
    runInAction(() => {
      state.loginStatus = "error";
      state.loginError =
        err instanceof ApiError ? err.message : "Invalid username or password.";
    });
  }
}
