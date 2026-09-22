<!-- product-spec:start -->
# Use Cases — FEAT-005 Database consistency & management

### UC-015 — View consistency report
- **Feature:** FEAT-005 · **Actor:** ACT-001
- **Preconditions:** Admin authenticated; database exists.
- **Main flow:**
  1. Admin opens the consistency page.
  2. System compares each table's actual structure to its expected
     structure.
  3. System reports per-table status (ok / drift / missing), with missing
     and extra columns listed for tables in drift.
- **Postconditions:** None (read-only).
- **Source:** `[confirmed: user]` interview 2026-07-20, "FEAT-005 DB
  check-consistency page"

### UC-016 — Create missing table
- **Feature:** FEAT-005 · **Actor:** ACT-001
- **Preconditions:** Consistency report shows a table as missing.
- **Main flow:**
  1. Admin requests creation for that table.
  2. System creates the table.
- **Postconditions:** Table present; report shows it as ok.
- **Source:** `[confirmed: user]` interview 2026-07-20, "FEAT-005 DB
  check-consistency page"

### UC-017 — Sync table schema
- **Feature:** FEAT-005 · **Actor:** ACT-001
- **Preconditions:** Consistency report shows a table with drift.
- **Main flow:**
  1. Admin requests a schema sync for that table.
  2. System reconciles missing and extra columns.
- **Postconditions:** Table structure matches expected structure; report
  shows it as ok.
- **Source:** `[confirmed: user]` interview 2026-07-20, "FEAT-005 DB
  check-consistency page"

### UC-018 — Export database
- **Feature:** FEAT-005 · **Actor:** ACT-001
- **Preconditions:** Admin authenticated.
- **Main flow:**
  1. Admin requests a database export.
  2. System produces a downloadable export.
- **Postconditions:** Export available to the admin.
- **Source:** `[confirmed: user]` interview 2026-07-20, "FEAT-005 DB
  check-consistency page"

### UC-019 — Import database (admin)
- **Feature:** FEAT-005 · **Actor:** ACT-001
- **Preconditions:** Admin authenticated; instance already configured
  (distinct from first-run import, UC-002).
- **Main flow:**
  1. Admin supplies a database export.
  2. System restores data from the export into the existing database.
- **Exception flow:** Export is invalid or corrupt → import refused.
- **Postconditions:** Database updated from the export; repeating the same
  import does not duplicate data.
- **Source:** `[confirmed: user]` interview 2026-07-20, "FEAT-005 DB
  check-consistency page"

### UC-020 — Rebuild vector index
- **Feature:** FEAT-005 · **Actor:** ACT-001
- **Preconditions:** Admin authenticated; database exists.
- **Main flow:**
  1. Admin requests a vector index rebuild.
  2. System rebuilds the index from the current source rows.
- **Postconditions:** Vector index reflects current source data.
- **Source:** `[confirmed: user]` interview 2026-07-20, "FEAT-005 DB
  check-consistency page"
<!-- product-spec:end -->
