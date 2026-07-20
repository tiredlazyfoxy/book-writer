<!-- product-spec:start -->
# Use Cases — FEAT-001 First-run bootstrap

### UC-001 — Create DB + first admin
- **Feature:** FEAT-001 · **Actor:** ACT-003
- **Preconditions:** No database exists (instance unconfigured).
- **Main flow:**
  1. Operator opens setup, instance reports itself unconfigured.
  2. Operator chooses "Create Database".
  3. Operator supplies first admin credentials (username, password, confirm).
  4. System creates the database and the first admin account.
  5. Operator is signed in as the new admin.
- **Exception flow:** Database already exists → creation refused; operator
  directed to the normal login instead.
- **Postconditions:** Database exists with exactly one admin user; operator
  is now ACT-001.
- **Source:** `[confirmed: user]` interview 2026-07-20, "FEAT-001 first-run
  bootstrap"

### UC-002 — Import DB to bootstrap
- **Feature:** FEAT-001 · **Actor:** ACT-003
- **Preconditions:** No database exists (instance unconfigured).
- **Main flow:**
  1. Operator opens setup, instance reports itself unconfigured.
  2. Operator chooses "Import Database".
  3. Operator supplies a database export.
  4. System restores the database from the export.
  5. Instance is now configured; operator can log in with a restored account.
- **Exception flow:** Export is invalid or corrupt → import refused, error
  shown, instance remains unconfigured.
- **Postconditions:** Database restored from the export; instance configured.
- **Source:** `[confirmed: user]` interview 2026-07-20, "FEAT-001 first-run
  bootstrap"
<!-- product-spec:end -->
