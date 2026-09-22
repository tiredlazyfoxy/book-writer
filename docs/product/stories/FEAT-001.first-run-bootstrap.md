<!-- product-spec:start -->
# Stories — FEAT-001 First-run bootstrap

### US-001 — First-run: create DB + admin
- **Feature:** FEAT-001 · **Actor:** ACT-003 · **Realizes:** UC-001
- **Status:** delivered
- **Story:** As a first-run operator, I want to create a new database with a
  first admin account, so that I can start using an otherwise empty instance.
- **Acceptance criteria:**
  - **US-001.AC-1** — Given no database exists, when the operator submits
    valid admin credentials via "Create Database", then a database is
    created and a first admin account exists.
  - **US-001.AC-2** — Given a database already exists, when the operator
    attempts "Create Database", then creation is refused.
  - **US-001.AC-3** — Given the operator submits a password below the
    minimum length, when they submit "Create Database", then creation is
    refused. `_TBD: minimum length value not specified in interview_`
  - **US-001.AC-4** — Given the operator's password and confirmation don't
    match, when they submit "Create Database", then creation is refused.
- **Source:** `[confirmed: user]` interview 2026-07-20, "FEAT-001 first-run
  bootstrap"

### US-002 — First-run: import DB
- **Feature:** FEAT-001 · **Actor:** ACT-003 · **Realizes:** UC-002
- **Status:** delivered
- **Story:** As a first-run operator, I want to import an existing database
  export during first-run, so that I can restore a prior instance's data
  instead of starting empty.
- **Acceptance criteria:**
  - **US-002.AC-1** — Given no database exists, when the operator submits a
    valid database export via "Import Database", then the database is
    restored and the instance becomes configured.
  - **US-002.AC-2** — Given no database exists, when the operator submits an
    invalid or corrupt export, then import is refused and the instance
    remains unconfigured.
- **Source:** `[confirmed: user]` interview 2026-07-20, "FEAT-001 first-run
  bootstrap"
<!-- product-spec:end -->
