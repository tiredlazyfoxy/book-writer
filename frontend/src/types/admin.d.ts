// Wire DTOs for the admin user-management endpoints (`/api/admin/users`) — pure
// shapes matching the backend Pydantic schemas (`app/models/schemas/admin.py`)
// 1:1. No methods, no classes, no runtime validation. See
// docs/plans/005.user-management.

import type { UserRole } from "./auth";
import type { ISODateString } from "./common";

/**
 * Re-export of the account role union (`"admin" | "author"`) so admin consumers
 * can import the role vocabulary alongside the DTOs. Single source of truth stays
 * `types/auth` — no duplicate union declared here.
 */
export type { UserRole } from "./auth";

/**
 * `GET /api/admin/users` row / `POST /api/admin/users` result — mirrors backend
 * `AdminUserResponse`. Secret-excluding (no `pwdhash`/`jwt_signing_key`). `id` is a
 * **string**: the backend serializes the 64-bit snowflake id as a string
 * (frontend.md — "Entity ids are `string`, not `number`"). `active` is a
 * response-time derived flag (`pwdhash is not None`), read directly by the UI.
 */
export interface AdminUserResponse {
  id: string;
  username: string;
  role: UserRole;
  last_login: ISODateString | null;
  active: boolean;
}

/** `POST /api/admin/users` request body — mirrors backend `AdminCreateUserRequest`. */
export interface AdminCreateUserRequest {
  username: string;
  password: string;
  password_confirm: string;
  role: UserRole;
}

/** `PUT /api/admin/users/{user_id}/password` request body — mirrors backend `AdminSetPasswordRequest`. */
export interface AdminSetPasswordRequest {
  password: string;
  password_confirm: string;
}

/** `PUT /api/admin/users/{user_id}/role` request body — mirrors backend `AdminSetRoleRequest`. */
export interface AdminSetRoleRequest {
  role: UserRole;
}
