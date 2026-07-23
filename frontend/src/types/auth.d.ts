// Wire DTOs for the auth / first-run endpoints — pure shapes matching the backend
// Pydantic schemas (`app/models/schemas/auth.py`) 1:1. No methods, no classes, no
// runtime validation. See docs/plans/004.authentication-session.

/** Account role — mirrors backend `UserRole` (feature 003 decision 5: exactly two). */
export type UserRole = "admin" | "author";

/** `GET /api/auth/status` response — mirrors backend `AuthStatusResponse`. */
export interface AuthStatusResponse {
  needs_setup: boolean;
}

/** `POST /api/auth/setup/create` request body — mirrors backend `CreateDBRequest`. */
export interface CreateDBRequest {
  admin_username: string;
  password: string;
  password_confirm: string;
}

/** `POST /api/auth/login` request body — mirrors backend `LoginRequest`. */
export interface LoginRequest {
  username: string;
  password: string;
}

/** `POST /api/auth/refresh` request body — mirrors backend `RefreshRequest`. */
export interface RefreshRequest {
  refresh_token: string;
}

/**
 * Token pair returned by `POST /api/auth/login`, `POST /api/auth/refresh`, and the
 * auto-sign-in of `POST /api/auth/setup/create` — mirrors backend `TokenResponse`.
 * Replaces the retired single-token `LoginResponse`.
 */
export interface TokenResponse {
  access_token: string;
  refresh_token: string;
}

/**
 * Identity of the authenticated caller — `GET /api/auth/me`, mirrors backend
 * `MeResponse`. `id` is a **string**: the backend serializes the 64-bit snowflake
 * id as a string (frontend.md — "Entity ids are `string`, not `number`").
 */
export interface MeResponse {
  id: string;
  username: string;
  role: UserRole;
}
