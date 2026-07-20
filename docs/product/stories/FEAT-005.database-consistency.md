<!-- product-spec:start -->
# Stories — FEAT-005 Database consistency & management

### US-015 — View consistency report
- **Feature:** FEAT-005 · **Actor:** ACT-001 · **Realizes:** UC-015
- **Status:** proposed
- **Story:** As an admin, I want to view a per-table consistency report, so
  that I know whether the database matches its expected structure.
- **Acceptance criteria:**
  - **US-015.AC-1** — Given the database exists, when the admin opens the
    consistency page, then every table is shown with a status of ok, drift,
    or missing.
  - **US-015.AC-2** — Given a table is in drift, when the admin views its
    entry, then its missing and extra columns are listed.
- **Source:** `[confirmed: user]` interview 2026-07-20, "FEAT-005 DB
  check-consistency page"

### US-016 — Create missing table
- **Feature:** FEAT-005 · **Actor:** ACT-001 · **Realizes:** UC-016
- **Status:** proposed
- **Story:** As an admin, I want to create a table the report shows as
  missing, so that the database matches its expected structure.
- **Acceptance criteria:**
  - **US-016.AC-1** — Given a table reported as missing, when the admin
    requests its creation, then the table is created and the report shows
    it as ok.
- **Source:** `[confirmed: user]` interview 2026-07-20, "FEAT-005 DB
  check-consistency page"

### US-017 — Sync table schema
- **Feature:** FEAT-005 · **Actor:** ACT-001 · **Realizes:** UC-017
- **Status:** proposed
- **Story:** As an admin, I want to sync a table's schema when it's in
  drift, so that its columns match what's expected.
- **Acceptance criteria:**
  - **US-017.AC-1** — Given a table reported in drift with missing columns,
    when the admin requests a sync, then the missing columns are added.
  - **US-017.AC-2** — Given a table reported in drift with extra columns,
    when the admin requests a sync, then the extra columns are reconciled
    and the table reports ok.
- **Source:** `[confirmed: user]` interview 2026-07-20, "FEAT-005 DB
  check-consistency page"

### US-018 — Export database
- **Feature:** FEAT-005 · **Actor:** ACT-001 · **Realizes:** UC-018
- **Status:** proposed
- **Story:** As an admin, I want to export the database, so that I have a
  portable backup or transfer artifact.
- **Acceptance criteria:**
  - **US-018.AC-1** — Given the admin requests an export, when it completes,
    then a downloadable export is produced.
- **Source:** `[confirmed: user]` interview 2026-07-20, "FEAT-005 DB
  check-consistency page"

### US-019 — Import database (admin)
- **Feature:** FEAT-005 · **Actor:** ACT-001 · **Realizes:** UC-019
- **Status:** proposed
- **Story:** As an admin, I want to import a database export into a running
  instance, so that I can restore or merge prior data.
- **Acceptance criteria:**
  - **US-019.AC-1** — Given a valid database export, when the admin imports
    it, then the database is updated with the export's data.
  - **US-019.AC-2** — Given the same export is imported twice, when the
    second import runs, then no duplicate data results.
  - **US-019.AC-3** — Given an invalid or corrupt export, when the admin
    attempts to import it, then the import is refused.
- **Source:** `[confirmed: user]` interview 2026-07-20, "FEAT-005 DB
  check-consistency page"

### US-020 — Rebuild vector index
- **Feature:** FEAT-005 · **Actor:** ACT-001 · **Realizes:** UC-020
- **Status:** proposed
- **Story:** As an admin, I want to rebuild the vector index, so that
  semantic search reflects the current data.
- **Acceptance criteria:**
  - **US-020.AC-1** — Given the admin requests a rebuild, when it completes,
    then the vector index is regenerated from current source rows.
- **Source:** `[confirmed: user]` interview 2026-07-20, "FEAT-005 DB
  check-consistency page"
<!-- product-spec:end -->
