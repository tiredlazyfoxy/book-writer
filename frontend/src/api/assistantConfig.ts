import { request } from "./client";
import type {
  AssistantMode,
  AssistantTool,
  CreateSubAgentRequest,
  SubAgent,
  UpdateAssistantModeRequest,
  UpdateSubAgentRequest,
} from "../types/assistantConfig";

// Admin assistant-configuration resource module (feature 012). All JSON HTTP goes
// through `client.request` (which injects Bearer when a token exists and normalizes
// non-2xx into `ApiError` — this module neither swallows nor re-wraps it, so callers
// can branch on 409 vs 400). Namespace-imported by callers
// (`import * as assistantConfigApi from "../../api/assistantConfig"`); `signal?` is
// always the trailing arg. The `{mode_key}` / `{sub_agent_id}` paths interpolate the
// STRING id directly — no parse, no coercion.
//
// The three list calls unwrap the `{ items: [...] }` envelope here via an INLINE
// response type — the envelope is deliberately not modelled in
// `types/assistantConfig.d.ts`.

const BASE = "/api/admin/assistant-config";

/**
 * Human-readable labels for the fixed five system mode keys. Runtime const, so it
 * lives here in the `.ts` api module rather than in `types/assistantConfig.d.ts` (a
 * declaration file cannot hold a runtime value — the `BACKEND_OPTIONS` precedent in
 * `api/llmServers.ts`). Total over the backend's `DEFAULT_MODE_KEYS`; it is the one
 * place these labels are spelled, so no page invents its own.
 */
export const MODE_LABELS: Record<string, string> = {
  "edit-character": "Edit character",
  "edit-location": "Edit location",
  "edit-fact": "Edit fact",
  "write-chapter": "Write chapter",
  "close-chapter": "Close chapter",
};

/**
 * Label lookup for a mode key. Degrades to the **raw key** for anything not in
 * {@link MODE_LABELS}, so an unexpected key renders rather than crashing.
 */
export function modeLabel(key: string): string {
  const label = MODE_LABELS[key];
  return typeof label === "string" ? label : key;
}

/** `GET /api/admin/assistant-config/tools` — the tool catalogue (unwrap `.items`). */
export async function listTools(signal?: AbortSignal): Promise<AssistantTool[]> {
  const res = await request<{ items: AssistantTool[] }>(`${BASE}/tools`, { signal });
  return res.items;
}

/** `GET /api/admin/assistant-config/modes` — list the fixed five modes (unwrap `.items`). */
export async function listModes(signal?: AbortSignal): Promise<AssistantMode[]> {
  const res = await request<{ items: AssistantMode[] }>(`${BASE}/modes`, { signal });
  return res.items;
}

/**
 * `PUT /api/admin/assistant-config/modes/{mode_key}` — full-replace save of one
 * mode's prompt, tool selection and sub-agent selection; returns the updated mode.
 */
export async function saveMode(
  modeKey: string,
  body: UpdateAssistantModeRequest,
  signal?: AbortSignal,
): Promise<AssistantMode> {
  return request<AssistantMode>(`${BASE}/modes/${modeKey}`, { method: "PUT", body, signal });
}

/** `GET /api/admin/assistant-config/sub-agents` — list every sub-agent, disabled ones included (unwrap `.items`). */
export async function listSubAgents(signal?: AbortSignal): Promise<SubAgent[]> {
  const res = await request<{ items: SubAgent[] }>(`${BASE}/sub-agents`, { signal });
  return res.items;
}

/** `POST /api/admin/assistant-config/sub-agents` — create a sub-agent (201); returns the new row. */
export async function createSubAgent(
  body: CreateSubAgentRequest,
  signal?: AbortSignal,
): Promise<SubAgent> {
  return request<SubAgent>(`${BASE}/sub-agents`, { method: "POST", body, signal });
}

/** `PUT /api/admin/assistant-config/sub-agents/{id}` — full-replace save; returns the updated row. */
export async function updateSubAgent(
  id: string,
  body: UpdateSubAgentRequest,
  signal?: AbortSignal,
): Promise<SubAgent> {
  return request<SubAgent>(`${BASE}/sub-agents/${id}`, { method: "PUT", body, signal });
}

/**
 * `POST /api/admin/assistant-config/sub-agents/{id}/disable` — **zero-body** POST
 * (200); detaches the sub-agent from every mode and returns the updated row.
 */
export async function disableSubAgent(id: string, signal?: AbortSignal): Promise<SubAgent> {
  return request<SubAgent>(`${BASE}/sub-agents/${id}/disable`, { method: "POST", signal });
}

/**
 * `POST /api/admin/assistant-config/sub-agents/{id}/enable` — **zero-body** POST
 * (200); returns the updated row. Restores no mode links.
 */
export async function enableSubAgent(id: string, signal?: AbortSignal): Promise<SubAgent> {
  return request<SubAgent>(`${BASE}/sub-agents/${id}/enable`, { method: "POST", signal });
}
