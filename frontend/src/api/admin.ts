import { request } from "./client";
import type {
  AdminCreateUserRequest,
  AdminSetPasswordRequest,
  AdminSetRoleRequest,
  AdminUserResponse,
} from "../types/admin";
import type { UserRole } from "../types/auth";

// Admin user-management resource module. All JSON HTTP goes through
// `client.request` (which injects Bearer when a token exists). Namespace-imported
// by callers (`import * as adminApi from "../../api/admin"`); `signal?` is always
// the trailing arg. The `{user_id}` PUT paths interpolate the STRING id directly.

const BASE = "/api/admin/users";

/** A role choice for admin `<Select>` inputs (create / set-role modals, step 004). */
export interface RoleOption {
  value: UserRole;
  label: string;
}

/**
 * Shared role options for admin selects. Runtime const, so it lives here in the
 * `.ts` api module rather than in `types/admin.d.ts` (a declaration file cannot
 * hold a runtime value). Mirrors the backend `UserRole` vocabulary 1:1.
 */
export const ROLE_OPTIONS: RoleOption[] = [
  { value: "admin", label: "Admin" },
  { value: "author", label: "Author" },
];

/** `GET /api/admin/users` — list all accounts (role / last-login / active per row). */
export async function listUsers(signal?: AbortSignal): Promise<AdminUserResponse[]> {
  return request<AdminUserResponse[]>(BASE, { signal });
}

/** `POST /api/admin/users` — create an account; returns the new user row. */
export async function createUser(
  body: AdminCreateUserRequest,
  signal?: AbortSignal,
): Promise<AdminUserResponse> {
  return request<AdminUserResponse>(BASE, { method: "POST", body, signal });
}

/** `PUT /api/admin/users/{user_id}/password` — reset a user's password (204 → void). */
export async function setUserPassword(
  userId: string,
  body: AdminSetPasswordRequest,
  signal?: AbortSignal,
): Promise<void> {
  return request<void>(`${BASE}/${userId}/password`, { method: "PUT", body, signal });
}

/** `PUT /api/admin/users/{user_id}/role` — change a user's role (204 → void). */
export async function setUserRole(
  userId: string,
  body: AdminSetRoleRequest,
  signal?: AbortSignal,
): Promise<void> {
  return request<void>(`${BASE}/${userId}/role`, { method: "PUT", body, signal });
}

/** `PUT /api/admin/users/{user_id}/disable` — disable a user (204 → void). */
export async function disableUser(userId: string, signal?: AbortSignal): Promise<void> {
  return request<void>(`${BASE}/${userId}/disable`, { method: "PUT", signal });
}
