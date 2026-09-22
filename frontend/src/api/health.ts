import { request } from "./client";
import type { HealthResponse } from "../types/health";

const BASE = "/api/health";

/**
 * Fetch the backend readiness result via `request<HealthResponse>` against `/api/health`.
 * `signal` is forwarded for cancellation; it is the last argument. Namespace-imported
 * by state files as `import * as healthApi from "../../api/health"`.
 */
export async function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return request<HealthResponse>(BASE, { signal });
}
