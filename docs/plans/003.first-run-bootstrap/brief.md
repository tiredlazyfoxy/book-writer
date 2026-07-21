# 003.first-run-bootstrap — First-run bootstrap
<!-- roadmap:start -->
- **Stage:** 1.foundation · **Track:** multi-step · **Size:** M
- **Delivers:** FEAT-001, UC-001, UC-002, US-001, US-002
- **Depends on:** `001.backend-scaffold`, `002.frontend-scaffold`

## Definition
Bring an unconfigured instance to a usable state. On first run with no
database, an operator either creates a fresh DB with a first admin, or
imports an existing database export to bootstrap. Afterwards the instance has
a usable admin and the normal login flow applies.

## Scope
**In:** detect unconfigured state; create-DB + first-admin flow;
import-DB-export flow; the first-run UI surface.
**Out:** ongoing user management (005); the export side (007); session
mechanics beyond issuing the first admin (004).

## Open questions for the planner
- What signals "unconfigured" — no DB file, or empty users table?
- Is the import format the same gzipped-JSONL as 007's export?
- Does bootstrap run behind a one-time setup route or a CLI step?
<!-- roadmap:end -->
