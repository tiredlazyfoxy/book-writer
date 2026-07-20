<!-- product-spec:start -->
# Stories — FEAT-003 User management

### US-005 — Admin lists users
- **Feature:** FEAT-003 · **Actor:** ACT-001 · **Realizes:** UC-005
- **Status:** proposed
- **Story:** As an admin, I want to list all user accounts, so that I can see
  who has access and in what role.
- **Acceptance criteria:**
  - **US-005.AC-1** — Given the admin is authenticated, when they open the
    user list, then every account is shown with its role and last-login
    time.
  - **US-005.AC-2** — Given the admin opens the user list, when the response
    is returned, then no account's password or other secret is included.
  - **US-005.AC-3** — Given a non-admin user, when they attempt to open the
    user list, then access is refused.
- **Source:** `[confirmed: user]` interview 2026-07-20, "FEAT-003 user
  management — roles & lifecycle"

### US-006 — Admin creates user
- **Feature:** FEAT-003 · **Actor:** ACT-001 · **Realizes:** UC-006
- **Status:** proposed
- **Story:** As an admin, I want to create a new user account with a role, so
  that new admins or authors can access the system.
- **Acceptance criteria:**
  - **US-006.AC-1** — Given a username not already taken, when the admin
    submits it with a password and a role of admin or author, then the
    account is created with that role.
  - **US-006.AC-2** — Given a username already taken, when the admin
    attempts to create an account with it, then creation is refused.
- **Source:** `[confirmed: user]` interview 2026-07-20, "FEAT-003 user
  management — roles & lifecycle"

### US-007 — Admin resets password
- **Feature:** FEAT-003 · **Actor:** ACT-001 · **Realizes:** UC-007
- **Status:** proposed
- **Story:** As an admin, I want to reset a user's password, so that they can
  regain access or I can recover from a lost credential.
- **Acceptance criteria:**
  - **US-007.AC-1** — Given a target account, when the admin sets a new
    password for it, then the account's credentials are updated to the new
    password.
  - **US-007.AC-2** — Given a target account is disabled, when the admin
    resets its password, then the account is re-enabled and able to log in.
- **Source:** `[confirmed: user]` interview 2026-07-20, "FEAT-003 user
  management — roles & lifecycle": "reversible via password reset"

### US-008 — Admin changes role
- **Feature:** FEAT-003 · **Actor:** ACT-001 · **Realizes:** UC-008
- **Status:** proposed
- **Story:** As an admin, I want to change another user's role, so that I can
  move accounts between admin and author.
- **Acceptance criteria:**
  - **US-008.AC-1** — Given a target account that is not the admin's own,
    when the admin sets a new role for it, then the account's role is
    updated.
  - **US-008.AC-2** — Given the admin attempts to change their own role,
    when they submit the change, then it is refused.
- **Source:** `[confirmed: user]` interview 2026-07-20, "FEAT-003 user
  management — roles & lifecycle"

### US-009 — Admin disables user
- **Feature:** FEAT-003 · **Actor:** ACT-001 · **Realizes:** UC-009
- **Status:** proposed
- **Story:** As an admin, I want to disable a user account, so that it can no
  longer log in while its data is preserved.
- **Acceptance criteria:**
  - **US-009.AC-1** — Given a target account that is not the admin's own,
    when the admin disables it, then its credentials are nulled and it can
    no longer log in.
  - **US-009.AC-2** — Given a disabled account, when its data is queried,
    then its associated data and attribution remain intact.
  - **US-009.AC-3** — Given the admin attempts to disable their own account,
    when they submit the action, then it is refused.
- **Source:** `[confirmed: user]` interview 2026-07-20, "FEAT-003 user
  management — roles & lifecycle": "Disable only. No hard delete."
<!-- product-spec:end -->
