// Wire DTOs for the admin LLM-server endpoints (`/api/admin/llm-servers`) — pure
// shapes matching the backend Pydantic schemas (`app/models/schemas/llm_servers.py`)
// 1:1. No methods, no classes, no runtime validation. See
// docs/plans/006.llm-server-connections.
//
// NOTE ON id TYPE — `LlmServer.id` is a `string`: the backend PK is a 64-bit
// snowflake (mirroring `User`), serialized as a string on the wire because 64-bit
// ids exceed the JS safe-integer range (same as `AdminUserResponse.id`).

import type { ISODateString } from "./common";

/**
 * Backend adapter kind for an LLM server (feature 006, D2). Mirrors the backend
 * `_VALID_BACKEND_TYPES` vocabulary 1:1. The runtime option list for form selects
 * lives in `api/llmServers.ts` (`BACKEND_OPTIONS`) — a `.d.ts` cannot hold values.
 */
export type LlmBackendType = "openai" | "llama-swap";

/**
 * `GET /api/admin/llm-servers` row / create/update result — mirrors backend
 * `LlmServerResponse`. Secret-excluding: there is **no `api_key`** field; key
 * presence is exposed only via `has_api_key`. `id` is a `string` (snowflake PK
 * serialized as a string). `enabled_models` arrives already-decoded as a `string[]`.
 */
export interface LlmServer {
  id: string;
  name: string;
  backend_type: LlmBackendType;
  base_url: string;
  has_api_key: boolean;
  enabled_models: string[];
  is_active: boolean;
  is_embedding: boolean;
  embedding_model: string | null;
  created_at: ISODateString | null;
  modified_at: ISODateString | null;
}

/** `GET /api/admin/llm-servers` envelope — mirrors backend `LlmServersListResponse`. */
export interface LlmServersListResponse {
  items: LlmServer[];
}

/** `POST /api/admin/llm-servers` request body — mirrors backend `CreateLlmServerRequest`. */
export interface CreateLlmServerRequest {
  name: string;
  backend_type: LlmBackendType;
  base_url: string;
  api_key?: string | null;
  is_active?: boolean;
}

/**
 * `PUT /api/admin/llm-servers/{id}` request body — mirrors backend
 * `UpdateLlmServerRequest`. All fields optional (partial update). An empty-string
 * `api_key` clears the stored key; omitting `api_key` leaves it unchanged.
 */
export interface UpdateLlmServerRequest {
  name?: string;
  backend_type?: LlmBackendType;
  base_url?: string;
  api_key?: string | null;
  is_active?: boolean;
}

/** `GET /api/admin/llm-servers/{id}/available-models` result — mirrors backend `AvailableModelsResponse`. */
export interface AvailableModels {
  models: string[];
}

/** `PUT /api/admin/llm-servers/{id}/enabled-models` request body — mirrors backend `EnabledModelsRequest`. */
export interface EnabledModelsRequest {
  enabled_models: string[];
}

/** `PUT /api/admin/llm-servers/{id}/embedding` request body — mirrors backend `SetEmbeddingRequest`. */
export interface SetEmbeddingRequest {
  model: string;
}

/**
 * `GET /api/admin/llm-servers/embedding` result — mirrors backend
 * `EmbeddingConfigResponse`. All fields are `null` when no embedding server is
 * designated (the all-`None` indicator).
 */
export interface EmbeddingConfig {
  server_id: string | null;
  server_name: string | null;
  base_url: string | null;
  backend_type: string | null;
  model: string | null;
  has_api_key: boolean;
}
