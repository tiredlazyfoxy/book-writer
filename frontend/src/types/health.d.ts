// Wire DTO for the health endpoint — pure shape matching backend JSON 1:1.
// No methods, no classes, no runtime validation.

/**
 * `GET /api/health` response — matches the backend Pydantic `HealthResponse`
 * (`status: str; db: str`) 1:1. Runtime values are `"ok"` / `"ready"`, typed as `string`.
 */
export interface HealthResponse {
  status: string;
  db: string;
}
