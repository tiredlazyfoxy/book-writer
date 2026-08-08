// Wire DTOs for the admin database-management endpoints (`/api/admin/db`) — pure
// shapes matching the backend Pydantic schemas (`app/models/schemas/db_admin.py`)
// 1:1. No methods, no classes, no runtime validation.
// See docs/plans/007.database-consistency (FEAT-005).

/**
 * Per-table consistency status — mirrors backend `TableReportEntry.status`.
 * Schema outranks rows: `seed-missing` is only ever reported for a table that is
 * present *and* schema-clean but is missing required seed rows.
 */
export type TableStatus = "ok" | "drift" | "missing" | "seed-missing";

/** One table's drift report — mirrors backend `TableReportEntry`. */
export interface TableReportEntry {
  name: string;
  status: TableStatus;
  missing_columns: string[];
  extra_columns: string[];
  /** Required seed-row keys with no row; empty unless `status === "seed-missing"`. */
  missing_seed_keys: string[];
}

/** `GET /api/admin/db/report` response — mirrors backend `ConsistencyReport`. */
export interface ConsistencyReport {
  tables: TableReportEntry[];
}

/** `POST /api/admin/db/vector/rebuild` response — mirrors backend `VectorRebuildResponse`. */
export interface VectorRebuildResponse {
  indexed_rows: number;
}
