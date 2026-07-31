<!-- product-spec:start -->
# Stories — FEAT-002 Authentication & session

### US-003 — Log in
- **Feature:** FEAT-002 · **Actor:** ACT-001, ACT-002 · **Realizes:** UC-003
- **Status:** delivered
- **Story:** As a user, I want to log in with my username and password, so
  that I can access the system as myself.
- **Acceptance criteria:**
  - **US-003.AC-1** — Given a user with valid credentials, when they submit
    username and password, then a session is issued and they are
    authenticated.
  - **US-003.AC-2** — Given a user submits invalid credentials, when they
    attempt to log in, then the login is refused and no session is issued.
  - **US-003.AC-3** — Given a user has exceeded the login rate limit, when
    they attempt to log in again, then the attempt is refused regardless of
    credential validity. `_TBD: exact rate-limit threshold not specified_`
- **Source:** `[inferred]` interview 2026-07-20, "FEAT-002 authentication &
  session" — carried from reference project, not explicitly confirmed.

### US-004 — Log out / session expiry
- **Feature:** FEAT-002 · **Actor:** ACT-001, ACT-002 · **Realizes:** UC-004
- **Status:** delivered
- **Story:** As a user, I want to log out or have my session expire, so that
  access ends when I'm done or inactive.
- **Acceptance criteria:**
  - **US-004.AC-1** — Given a user has an active session, when they log out,
    then the session ends and further requests require re-authentication.
  - **US-004.AC-2** — Given a user's session has passed its expiry, when
    they make a request, then the request is refused and re-authentication
    is required.
- **Source:** `[inferred]` interview 2026-07-20, "FEAT-002 authentication &
  session" — carried from reference project, not explicitly confirmed.
<!-- product-spec:end -->
