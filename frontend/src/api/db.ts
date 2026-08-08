import { request, throwApiError } from "./client";
import { getToken } from "../auth";
import type { ConsistencyReport, VectorRebuildResponse } from "../types/db";

// Admin database-management resource module for `/api/admin/db`. JSON endpoints
// (report / create / sync / rebuild) go through the shared `client.request` (which
// injects Bearer from the token accessor and maps `204 -> undefined`). Export
// (blob download) and import (multipart upload) bypass `request` — that wrapper is
// JSON-only — building their own `fetch` and reading the token via the `auth.ts`
// accessor (one-way dependency api/ -> auth.ts), mirroring `api/auth.ts::setupImport`.
// See docs/plans/007.database-consistency (FEAT-005).

const BASE = "/api/admin/db";

/** `GET /api/admin/db/report` — per-table schema-drift report. */
export async function getConsistencyReport(signal?: AbortSignal): Promise<ConsistencyReport> {
  return request<ConsistencyReport>(`${BASE}/report`, { signal });
}

/** `POST /api/admin/db/tables/{name}/create` — create a missing table (204, no body). */
export async function createTable(name: string, signal?: AbortSignal): Promise<void> {
  return request<void>(`${BASE}/tables/${encodeURIComponent(name)}/create`, {
    method: "POST",
    signal,
  });
}

/** `POST /api/admin/db/tables/{name}/sync` — sync a drifted table's schema (204, no body). */
export async function syncTable(name: string, signal?: AbortSignal): Promise<void> {
  return request<void>(`${BASE}/tables/${encodeURIComponent(name)}/sync`, {
    method: "POST",
    signal,
  });
}

/**
 * `POST /api/admin/db/tables/{name}/seed` — seed a table's missing required rows
 * (204, no body). Mirrors `createTable` / `syncTable`.
 */
export async function seedTable(name: string, signal?: AbortSignal): Promise<void> {
  return request<void>(`${BASE}/tables/${encodeURIComponent(name)}/seed`, {
    method: "POST",
    signal,
  });
}

/** `POST /api/admin/db/vector/rebuild` — rebuild the LanceDB vector index; returns the indexed-row count. */
export async function rebuildIndex(signal?: AbortSignal): Promise<VectorRebuildResponse> {
  return request<VectorRebuildResponse>(`${BASE}/vector/rebuild`, {
    method: "POST",
    signal,
  });
}

/**
 * `GET /api/admin/db/export` — downloads the database export (gzipped-JSONL zip).
 * Net-new blob-download plumbing: bypasses `request` (which is JSON-only), reads the
 * response as a blob, and triggers a browser file save via an object URL + a
 * programmatic anchor click, then revokes the URL. Bearer from the auth accessor.
 */
export async function exportDatabase(): Promise<void> {
  const token = getToken();
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`${BASE}/export`, { method: "GET", headers });
  if (!res.ok) await throwApiError(res);

  const blob = await res.blob();
  const filename = filenameFromDisposition(res.headers.get("Content-Disposition"));

  const url = URL.createObjectURL(blob);
  try {
    const anchor: HTMLAnchorElement = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
  } finally {
    URL.revokeObjectURL(url);
  }
}

/** Derive a download filename from a `Content-Disposition` header, falling back to a constant. */
function filenameFromDisposition(disposition: string | null): string {
  const fallback = "bookwriter-export.zip";
  if (!disposition) return fallback;
  const match = /filename="?([^"]+)"?/.exec(disposition);
  return match ? match[1] : fallback;
}

/**
 * `POST /api/admin/db/import` — uploads a database export for streaming UPSERT.
 * Net-new multipart plumbing mirroring `api/auth.ts::setupImport`: builds a
 * `FormData` with the archive under field `file`, sets NO JSON `Content-Type`
 * (the browser supplies the multipart boundary), and attaches Bearer from the auth
 * accessor. Rejects on a non-2xx (e.g. a 400 `invalid-archive` refusal) so the
 * caller can surface it. Endpoint returns 204 — no body to parse.
 */
export async function importDatabase(file: File, signal?: AbortSignal): Promise<void> {
  const formData = new FormData();
  formData.append("file", file);

  const token = getToken();
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`${BASE}/import`, {
    method: "POST",
    headers,
    body: formData,
    signal,
  });

  if (!res.ok) await throwApiError(res);
}
