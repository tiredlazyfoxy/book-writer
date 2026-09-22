# 005.user-management — User management
<!-- roadmap:start -->
- **Stage:** 1.foundation · **Track:** multi-step · **Size:** M
- **Delivers:** FEAT-003, UC-005, UC-006, UC-007, UC-008, UC-009, US-005, US-006, US-007, US-008, US-009
- **Depends on:** `004.authentication-session`

## Definition
Admin-gated account lifecycle in the Admin SPA: list, create, reset
password, change role, disable. No hard delete — disable is terminal.

## Scope
**In:** admin user list/create/reset/role-change/disable; admin-only guard;
admin SPA user pages.
**Out:** self-service profile; book moderation (Stage 6).

## Open questions for the planner
- Role set (admin/author only, or more)?
- Does disabling cascade to the user's live sessions immediately (ties to 004)?
<!-- roadmap:end -->
