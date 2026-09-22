import { makeAutoObservable, runInAction } from "mobx";
import * as llmServersApi from "../../../api/llmServers";
import { ApiError } from "../../../api/client";
import type { LlmBackendType, LlmServer } from "../../../types/llmServers";

/**
 * Component-local draft for the create/edit LLM-server form modal — held via
 * `useState(() => new ServerFormDraft(server))`. Observable fields + pure `get`
 * computeds only (no effectful methods, per the MobX hard rules); the effectful
 * submit lives in the external `submitServerForm` below.
 *
 * Seeded from an existing server for EDIT (`server` non-null) or left at create
 * defaults (`server` null). `apiKey` is NEVER seeded from the DTO — the response
 * carries no key value (US-021.AC-2); an empty draft key means "leave unchanged" on
 * edit (per the omitted-`api_key` contract).
 */
export class ServerFormDraft {
  name = "";
  backendType: LlmBackendType = "openai";
  baseUrl = "";
  apiKey = "";
  isActive = true;

  serverErrors: Record<string, string> = {};
  submitStatus: "idle" | "loading" | "ready" | "error" = "idle";

  constructor(server: LlmServer | null) {
    if (server) {
      this.name = server.name;
      this.backendType = server.backend_type;
      this.baseUrl = server.base_url;
      this.isActive = server.is_active;
    }
    makeAutoObservable(this);
  }

  /** Client-side validation: required name and base URL. */
  get clientErrors(): Record<string, string> {
    const e: Record<string, string> = {};
    if (!this.name.trim()) e.name = "Name is required.";
    if (!this.baseUrl.trim()) e.base_url = "Base URL is required.";
    return e;
  }

  /** Displayed errors: client validation unioned with (overridden by) server errors. */
  get errors(): Record<string, string> {
    return { ...this.clientErrors, ...this.serverErrors };
  }

  /** True when client validation passes and no submit is in flight. */
  get canSubmit(): boolean {
    return this.submitStatus !== "loading" && Object.keys(this.clientErrors).length === 0;
  }
}

/**
 * Effect (unimplemented — coder fills). Create when `serverId` is null
 * (`createServer` with `api_key: draft.apiKey || null`); otherwise `updateServer`
 * (include `api_key` only when the draft key is non-empty, per the ""-clears /
 * omitted-unchanged contract). Map `ApiError` → `draft.serverErrors`; on success set
 * status "ready" and invoke `onSaved` (the page refresh). Abort-guarded via `signal`.
 */
export async function submitServerForm(
  draft: ServerFormDraft,
  serverId: string | null,
  onSaved: () => void,
  signal?: AbortSignal,
): Promise<void> {
  runInAction(() => {
    draft.serverErrors = {};
    draft.submitStatus = "loading";
  });

  try {
    if (serverId === null) {
      await llmServersApi.createServer(
        {
          name: draft.name,
          backend_type: draft.backendType,
          base_url: draft.baseUrl,
          api_key: draft.apiKey || null,
          is_active: draft.isActive,
        },
        signal,
      );
    } else {
      await llmServersApi.updateServer(
        serverId,
        {
          name: draft.name,
          backend_type: draft.backendType,
          base_url: draft.baseUrl,
          is_active: draft.isActive,
          ...(draft.apiKey ? { api_key: draft.apiKey } : {}),
        },
        signal,
      );
    }
  } catch (err) {
    if (err instanceof ApiError) {
      runInAction(() => {
        draft.serverErrors = { form: err.message || "Could not save the server." };
        draft.submitStatus = "error";
      });
      return;
    }
    if (signal?.aborted) return;
    runInAction(() => {
      draft.submitStatus = "error";
    });
    throw err;
  }

  runInAction(() => {
    draft.submitStatus = "ready";
  });
  onSaved();
}
