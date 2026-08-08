/**
 * The `Seed` remediation on the Database page — feedback round 1, item **F1**.
 *
 * Reproduces: the consistency report has no way to say "this table's seed rows
 * are missing", `api/db` has no seed call, `databasePageState` has no seed
 * action, and the Actions column offers nothing for a `seed-missing` row — so an
 * operator on an empty `/admin/assistant-modes` has no path back.
 *
 * Bound to the frozen signatures (status.md -> `## Skeleton` -> "Feedback round
 * 1, item F1 — re-freeze"), plus the pre-existing ones this round preserves:
 *   types/db.d.ts:
 *     type TableStatus = "ok" | "drift" | "missing" | "seed-missing"
 *     interface TableReportEntry { name; status; missing_columns;
 *                                  extra_columns; missing_seed_keys: string[] }
 *   api/db.ts:
 *     seedTable(name: string, signal?: AbortSignal): Promise<void>
 *     getConsistencyReport / createTable / syncTable / rebuildIndex /
 *     exportDatabase / importDatabase
 *   admin/pages/databasePageState.ts:
 *     class DatabasePageState { report; reportStatus; reportError; actionError;
 *                               rebuildResult }        // unchanged, no new field
 *     seedTableAction(state, name, signal?): Promise<void>
 *   admin/pages/DatabasePage.tsx: the named `DatabasePage` observer, no props.
 *   api/client: class ApiError extends Error { constructor(status, message) }
 *
 * THE AIR GAP — no source is read. Every expected value comes from
 * `docs/plans/012.assistant-config-editor/feedback.md` -> F1, points 5 + 6:
 *   - `seedTable` posts to `/api/admin/db/tables/{name}/seed` with no body (the
 *     route family is `POST /tables/{name}/…`, 204, no request body);
 *   - `seedTableAction` follows `createTableAction`'s idiom exactly: clear
 *     `actionError` -> call -> reload the report -> friendly-catch (an `ApiError`
 *     lands in `actionError` and is never thrown);
 *   - `DatabasePage` renders a `Seed` button in the Actions column for a
 *     `seed-missing` row and for no other status, while the existing
 *     `missing` -> `Create` and `drift` -> `Sync` rules keep holding (F1
 *     Constraints: "the report's existing three statuses keep their exact
 *     present meaning").
 *
 * Mocking: `../../src/api/db` is mocked — the api MODULE, never `fetch`. The one
 * exception is the URL assertion for `seedTable` itself: the module under test
 * there IS the api layer, so that single test imports the REAL `api/db` through
 * `vi.importActual` and asserts against a mocked `api/client::request` — the
 * repo's own api-layer precedent (`tests/admin/assistantConfigApi.test.ts`,
 * `tests/user/chaptersApi.test.ts`). The `importOriginal` spread keeps the REAL
 * `ApiError` class, which the friendly-catch is about.
 *
 * `globals: false`: every primitive is imported explicitly. `restoreMocks` wipes
 * implementations between tests, so `beforeEach` re-arms them.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { runInAction } from "mobx";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ApiError, request } from "../../src/api/client";
import type { ConsistencyReport, TableReportEntry } from "../../src/types/db";
import * as dbApi from "../../src/api/db";
import {
  DatabasePageState,
  seedTableAction,
} from "../../src/admin/pages/databasePageState";
import { DatabasePage } from "../../src/admin/pages/DatabasePage";
import { renderWithProviders } from "../support/render";

vi.mock("../../src/api/db", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../src/api/db")>();
  return {
    ...actual,
    getConsistencyReport: vi.fn(),
    createTable: vi.fn(),
    syncTable: vi.fn(),
    seedTable: vi.fn(),
    rebuildIndex: vi.fn(),
    exportDatabase: vi.fn(),
    importDatabase: vi.fn(),
  };
});

// Only `request` is replaced; `ApiError` stays the real class.
vi.mock("../../src/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../src/api/client")>();
  return { ...actual, request: vi.fn() };
});

/* ------------------------------------------------------------------ fixtures */

const MODES_TABLE = "assistant_modes";

/** The fixed five mode keys (F1 point 1 -> the members of `DEFAULT_MODE_KEYS`). */
const FIXED_FIVE_KEYS = [
  "edit-character",
  "edit-location",
  "edit-fact",
  "write-chapter",
  "close-chapter",
];

function makeEntry(
  name: string,
  status: TableReportEntry["status"],
  overrides: Partial<TableReportEntry> = {},
): TableReportEntry {
  return {
    name,
    status,
    missing_columns: [],
    extra_columns: [],
    missing_seed_keys: [],
    ...overrides,
  };
}

/** One row per status, so each visibility rule is asserted against the others. */
const SEED_MISSING_ROW = makeEntry(MODES_TABLE, "seed-missing", {
  missing_seed_keys: FIXED_FIVE_KEYS,
});
const OK_ROW = makeEntry("users", "ok");
const DRIFT_ROW = makeEntry("llm_servers", "drift", {
  missing_columns: ["is_active"],
});
const MISSING_ROW = makeEntry("books", "missing");

const REPORT: ConsistencyReport = {
  tables: [SEED_MISSING_ROW, OK_ROW, DRIFT_ROW, MISSING_ROW],
};

/* ------------------------------------------------------------------- helpers */

type ClientOpts = Parameters<typeof request>[1];

async function bodyRows(): Promise<HTMLElement[]> {
  const table = await screen.findByRole("table");
  return within(table)
    .getAllByRole("row")
    .filter((row) => within(row).queryAllByRole("cell").length > 0);
}

async function rowFor(tableName: string): Promise<HTMLElement> {
  const rows = await bodyRows();
  const match = rows.find((row) => (row.textContent ?? "").includes(tableName));
  if (match === undefined) {
    throw new Error(`no report row for the table "${tableName}"`);
  }
  return match;
}

function queryButton(row: HTMLElement, name: RegExp): HTMLElement | null {
  return within(row).queryByRole("button", { name });
}

const SEED = /^seed$/i;
const CREATE = /^create$/i;
const SYNC = /^sync$/i;

function renderPage(): void {
  renderWithProviders(<DatabasePage />, { route: "/database" });
}

beforeEach(() => {
  vi.mocked(dbApi.getConsistencyReport).mockResolvedValue(REPORT);
  vi.mocked(dbApi.seedTable).mockResolvedValue(undefined);
  vi.mocked(dbApi.createTable).mockResolvedValue(undefined);
  vi.mocked(dbApi.syncTable).mockResolvedValue(undefined);
});

/* ------------------------------------------------------------- the api call --*/

describe("the seed api call (F1 point 5)", () => {
  it("F1: seedTable POSTs to /api/admin/db/tables/{name}/seed with no body", async () => {
    const realDbApi = await vi.importActual<typeof import("../../src/api/db")>(
      "../../src/api/db",
    );
    vi.mocked(request).mockResolvedValue(undefined);

    await realDbApi.seedTable(MODES_TABLE);

    const calls = vi.mocked(request).mock.calls;
    expect(calls).toHaveLength(1);
    const [url, opts] = calls[0] as [string, ClientOpts];
    expect(url).toBe(`/api/admin/db/tables/${MODES_TABLE}/seed`);
    expect((opts?.method ?? "GET").toUpperCase()).toBe("POST");
    expect(opts?.body).toBeUndefined();
  });
});

/* ---------------------------------------------------------- the page action --*/

describe("the seed page action (F1 point 5)", () => {
  it("F1: seedTableAction clears actionError, seeds, then reloads the report", async () => {
    const state = new DatabasePageState();
    runInAction(() => {
      state.actionError = "a stale error from an earlier action";
    });

    await seedTableAction(state, MODES_TABLE);

    expect(vi.mocked(dbApi.seedTable)).toHaveBeenCalledTimes(1);
    expect(vi.mocked(dbApi.seedTable).mock.calls[0][0]).toBe(MODES_TABLE);
    expect(state.actionError).toBeNull();

    // The reloaded report is the admin's confirmation (decision D-d): no
    // optimistic patch, the backend is re-read.
    expect(vi.mocked(dbApi.getConsistencyReport)).toHaveBeenCalled();
    await waitFor(() => expect(state.reportStatus).toBe("ready"));
    expect(state.report).toEqual(REPORT);
  });

  it("F1: a refused seed lands in actionError and is never thrown", async () => {
    vi.mocked(dbApi.seedTable).mockRejectedValue(
      new ApiError(400, "Table 'users' cannot be seeded."),
    );
    const state = new DatabasePageState();

    await expect(seedTableAction(state, "users")).resolves.toBeUndefined();

    expect(typeof state.actionError).toBe("string");
    expect((state.actionError ?? "").length).toBeGreaterThan(0);
  });
});

/* ------------------------------------------------------------- the page row --*/

describe("the Seed button in the Actions column (F1 point 5)", () => {
  it("F1: only the seed-missing row offers Seed; ok / drift / missing rows do not", async () => {
    renderPage();

    const seedMissing = await rowFor(MODES_TABLE);
    expect(queryButton(seedMissing, SEED)).not.toBeNull();

    for (const entry of [OK_ROW, DRIFT_ROW, MISSING_ROW]) {
      const row = await rowFor(entry.name);
      expect(queryButton(row, SEED)).toBeNull();
    }
  });

  it("F1 (regression guard): Create still shows only for missing and Sync only for drift", async () => {
    renderPage();

    const missing = await rowFor(MISSING_ROW.name);
    expect(queryButton(missing, CREATE)).not.toBeNull();
    expect(queryButton(missing, SYNC)).toBeNull();

    const drift = await rowFor(DRIFT_ROW.name);
    expect(queryButton(drift, SYNC)).not.toBeNull();
    expect(queryButton(drift, CREATE)).toBeNull();

    const ok = await rowFor(OK_ROW.name);
    expect(queryButton(ok, CREATE)).toBeNull();
    expect(queryButton(ok, SYNC)).toBeNull();

    // ... and the seed-missing row offers neither of the two schema actions:
    // it is schema-clean (F1 point 2 — the four values are mutually exclusive).
    const seedMissing = await rowFor(MODES_TABLE);
    expect(queryButton(seedMissing, CREATE)).toBeNull();
    expect(queryButton(seedMissing, SYNC)).toBeNull();
  });

  it("F1: pressing Seed seeds THAT table and re-reads the report", async () => {
    const user = userEvent.setup();
    renderPage();

    const row = await rowFor(MODES_TABLE);
    const button = queryButton(row, SEED);
    expect(button).not.toBeNull();
    const loadsBefore = vi.mocked(dbApi.getConsistencyReport).mock.calls.length;

    await user.click(button as HTMLElement);

    await waitFor(() => expect(vi.mocked(dbApi.seedTable)).toHaveBeenCalledTimes(1));
    expect(vi.mocked(dbApi.seedTable).mock.calls[0][0]).toBe(MODES_TABLE);
    await waitFor(() =>
      expect(
        vi.mocked(dbApi.getConsistencyReport).mock.calls.length,
      ).toBeGreaterThan(loadsBefore),
    );
  });
});
