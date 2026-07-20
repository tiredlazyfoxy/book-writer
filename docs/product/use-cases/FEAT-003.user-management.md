<!-- product-spec:start -->
# Use Cases — FEAT-003 User management

### UC-005 — List users
- **Feature:** FEAT-003 · **Actor:** ACT-001
- **Preconditions:** Admin authenticated.
- **Main flow:**
  1. Admin opens user management.
  2. System returns the account list with role and last-login per user,
     excluding credential secrets.
- **Exception flow:** Non-admin attempts access → refused.
- **Postconditions:** None (read-only).
- **Source:** `[confirmed: user]` interview 2026-07-20, "FEAT-003 user
  management — roles & lifecycle"

### UC-006 — Create user
- **Feature:** FEAT-003 · **Actor:** ACT-001
- **Preconditions:** Admin authenticated.
- **Main flow:**
  1. Admin submits a new username, password, and role.
  2. System checks the username is not already taken.
  3. System creates the account with the given role.
- **Exception flow:** Username already taken → creation refused.
- **Postconditions:** New user account exists, able to log in.
- **Source:** `[confirmed: user]` interview 2026-07-20, "FEAT-003 user
  management — roles & lifecycle"

### UC-007 — Reset user password
- **Feature:** FEAT-003 · **Actor:** ACT-001
- **Preconditions:** Admin authenticated; target account exists (may be
  disabled).
- **Main flow:**
  1. Admin selects the target account.
  2. Admin submits a new password.
  3. System sets the new credentials.
  4. If the account was disabled, it is re-enabled.
- **Postconditions:** User can log in with the new password; disabled state
  cleared if it applied.
- **Source:** `[confirmed: user]` interview 2026-07-20, "FEAT-003 user
  management — roles & lifecycle": "reversible via password reset"

### UC-008 — Change user role
- **Feature:** FEAT-003 · **Actor:** ACT-001
- **Preconditions:** Admin authenticated; target account exists and is not
  the admin's own account.
- **Main flow:**
  1. Admin selects the target account and a new role.
  2. System updates the account's role.
- **Exception flow:** Admin attempts to change their own role → refused.
- **Postconditions:** Target account's role updated.
- **Source:** `[confirmed: user]` interview 2026-07-20, "FEAT-003 user
  management — roles & lifecycle"

### UC-009 — Disable user
- **Feature:** FEAT-003 · **Actor:** ACT-001
- **Preconditions:** Admin authenticated; target account exists and is not
  the admin's own account.
- **Main flow:**
  1. Admin selects the target account.
  2. Admin confirms the disable action.
  3. System nulls the account's credentials; account data is preserved.
- **Exception flow:** Admin attempts to disable their own account → refused.
- **Postconditions:** Account cannot log in until its password is reset;
  data and attribution preserved.
- **Source:** `[confirmed: user]` interview 2026-07-20, "FEAT-003 user
  management — roles & lifecycle": "Disable only. No hard delete."
<!-- product-spec:end -->
