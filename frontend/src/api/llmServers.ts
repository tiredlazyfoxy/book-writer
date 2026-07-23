import { request } from "./client";
import type {
  AvailableModels,
  CreateLlmServerRequest,
  LlmBackendType,
  LlmServer,
  LlmServersListResponse,
  UpdateLlmServerRequest,
} from "../types/llmServers";

// Admin LLM-server resource module. All JSON HTTP goes through `client.request`
// (which injects Bearer when a token exists). Namespace-imported by callers
// (`import * as llmServersApi from "../../api/llmServers"`); `signal?` is always the
// trailing arg. The `{server_id}` paths interpolate the STRING snowflake id directly.
//
// Skeleton: exact signatures frozen; bodies throw. The coder fills the `request<T>`
// calls, including unwrapping `.items` (list) and `.models` (available-models).

const BASE = "/api/admin/llm-servers";

/** A backend-type choice for the server form `<Select>` (New / Edit modals, step 006). */
export interface BackendOption {
  value: LlmBackendType;
  label: string;
}

/**
 * Shared backend-type options for admin selects. Runtime const, so it lives here in
 * the `.ts` api module rather than in `types/llmServers.d.ts` (a declaration file
 * cannot hold a runtime value). Mirrors the backend `_VALID_BACKEND_TYPES` 1:1.
 */
export const BACKEND_OPTIONS: BackendOption[] = [
  { value: "openai", label: "OpenAI-compatible" },
  { value: "llama-swap", label: "llama-swap" },
];

/** `GET /api/admin/llm-servers` — list servers (unwrap `.items` from the envelope). */
export async function listServers(signal?: AbortSignal): Promise<LlmServer[]> {
  const res = await request<LlmServersListResponse>(BASE, { signal });
  return res.items;
}

/** `POST /api/admin/llm-servers` — create a server; returns the new row. */
export async function createServer(
  body: CreateLlmServerRequest,
  signal?: AbortSignal,
): Promise<LlmServer> {
  return request<LlmServer>(BASE, { method: "POST", body, signal });
}

/** `PUT /api/admin/llm-servers/{id}` — update a server; returns the updated row. */
export async function updateServer(
  id: string,
  body: UpdateLlmServerRequest,
  signal?: AbortSignal,
): Promise<LlmServer> {
  return request<LlmServer>(`${BASE}/${id}`, { method: "PUT", body, signal });
}

/** `DELETE /api/admin/llm-servers/{id}` — remove a server (204 → void). */
export async function deleteServer(id: string, signal?: AbortSignal): Promise<void> {
  return request<void>(`${BASE}/${id}`, { method: "DELETE", signal });
}

/** `GET /api/admin/llm-servers/{id}/available-models` — probe (unwrap `.models`). */
export async function probeModels(id: string, signal?: AbortSignal): Promise<string[]> {
  const res = await request<AvailableModels>(`${BASE}/${id}/available-models`, { signal });
  return res.models;
}

/** `PUT /api/admin/llm-servers/{id}/enabled-models` — set the enabled model list; returns the row. */
export async function setEnabledModels(
  id: string,
  models: string[],
  signal?: AbortSignal,
): Promise<LlmServer> {
  return request<LlmServer>(`${BASE}/${id}/enabled-models`, {
    method: "PUT",
    body: { enabled_models: models },
    signal,
  });
}

/** `PUT /api/admin/llm-servers/{id}/embedding` — designate the embedding provider (204 → void). */
export async function setEmbedding(
  id: string,
  model: string,
  signal?: AbortSignal,
): Promise<void> {
  return request<void>(`${BASE}/${id}/embedding`, {
    method: "PUT",
    body: { model },
    signal,
  });
}

/** `DELETE /api/admin/llm-servers/embedding` — clear the embedding designation (204 → void). */
export async function clearEmbedding(signal?: AbortSignal): Promise<void> {
  return request<void>(`${BASE}/embedding`, { method: "DELETE", signal });
}
