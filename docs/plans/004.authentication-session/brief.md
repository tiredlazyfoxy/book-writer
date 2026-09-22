# 004.authentication-session — Authentication & session
<!-- roadmap:start -->
- **Stage:** 1.foundation · **Track:** multi-step · **Size:** M
- **Delivers:** FEAT-002, UC-003, UC-004, US-003, US-004
- **Depends on:** `003.first-run-bootstrap`

## Definition
Let a created user log in, hold a session, and log out; expired or
invalidated sessions force re-authentication. Establishes JWT (HS256,
per-user signing key) issue/verify, bcrypt password checking, and the Login
page that produces the token both SPAs carry.

## Scope
**In:** login endpoint + bcrypt verify; per-user-key JWT issue/verify;
logout/expiry; the auth dependency guarding protected routes; Login page
form → token.
**Out:** user creation/roles/reset (005).

## Open questions for the planner
- Token lifetime + refresh strategy?
- Where the per-user signing key lives and how disabling a user invalidates live sessions?
- FEAT-002 is `[inferred]` in the spec — confirm the requirement at planning.
<!-- roadmap:end -->
