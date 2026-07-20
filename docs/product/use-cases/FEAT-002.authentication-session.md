<!-- product-spec:start -->
# Use Cases — FEAT-002 Authentication & session

### UC-003 — Log in
- **Feature:** FEAT-002 · **Actor:** ACT-001, ACT-002
- **Preconditions:** Instance configured; user holds valid credentials.
- **Main flow:**
  1. User submits username and password.
  2. System verifies credentials.
  3. System issues a session.
  4. User is authenticated for subsequent actions.
- **Alternate flow:** A signing-key rotation for the user invalidates any
  session issued before the rotation.
- **Exception flow:** Credentials invalid → login refused; repeated failures
  → further attempts rate-limited.
- **Postconditions:** Active session for the user, or a refusal with no
  session issued.
- **Source:** `[inferred]` interview 2026-07-20, "FEAT-002 authentication &
  session" — carried from reference project; not explicitly confirmed by the
  user.

### UC-004 — Log out / session expiry
- **Feature:** FEAT-002 · **Actor:** ACT-001, ACT-002
- **Preconditions:** User holds an active session.
- **Main flow:**
  1. User requests logout, or the session reaches its expiry.
  2. System ends the session.
  3. User must re-authenticate for further access.
- **Postconditions:** Session no longer valid.
- **Source:** `[inferred]` interview 2026-07-20, "FEAT-002 authentication &
  session" — carried from reference project; not explicitly confirmed by the
  user.
<!-- product-spec:end -->
