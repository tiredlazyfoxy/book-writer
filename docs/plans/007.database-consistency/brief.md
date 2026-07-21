# 007.database-consistency — Database consistency & management
<!-- roadmap:start -->
- **Stage:** 1.foundation · **Track:** multi-step · **Size:** M/L
- **Delivers:** FEAT-005, UC-015, UC-016, UC-017, UC-018, UC-019, UC-020, US-015, US-016, US-017, US-018, US-019, US-020
- **Depends on:** `006.llm-server-connections`

## Definition
Report per-table schema drift and let an admin remediate: create missing
tables, sync table schema, export/import the database (gzipped JSONL), and
rebuild the LanceDB vector index from source rows.

## Scope
**In:** schema-drift report; create-missing-table; sync-schema (ALTER); DB
export (streaming per-row `.jsonl.gz`); DB import (streaming UPSERT);
rebuild vector index; admin SPA DB page.
**Out:** first-run import (003, shares format).

## Open questions for the planner
- Is import/export the same code path 003 reuses?
- How is schema drift computed against SQLModel metadata?
- Index rebuild depends on the embedding designation (006) — hard dep.
- Size may split — flag to planner.
<!-- roadmap:end -->
