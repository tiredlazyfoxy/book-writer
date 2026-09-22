import { makeAutoObservable, runInAction } from "mobx";
import * as codexApi from "../../api/codex";
import { ApiError } from "../../api/client";
import type { CodexEntryResponse, CodexKind } from "../../types/codex";
import type { ISODateString } from "../../types/common";
import type { ContentSubject } from "../contentSubject";
import { clearBuffer, readBuffer, restoreBufferKey, writeBuffer } from "../restoreBuffer";
import { resolveEditability } from "../subject";
import type { Editability } from "../subject";

// Page state for `CodexEntryPage` — one codex entry in the content pane
// (UC-069 / UC-070 / UC-092 / US-107), held via
// `useState(() => new CodexEntryPageState(bookId, entryId, initialKind))`.
//
// The class shape, the computed contract and the external effect functions are
// the step's frozen interface (013/012).
//
// Per the enforced MobX rules this class holds observable data + pure `get`
// computeds only. The effects live in the external `(state, args, signal)`
// functions below, which are the ONLY place `api/codex.ts` and
// `work/restoreBuffer.ts` are touched.
//
// The one exception to "no methods" is `applyDraft`, and it is deliberate: it is
// a bound adapter (not an effect of its own) that forwards to `editCodexDraft`,
// so step 013 can hand `state.applyDraft` to the module-level canvas registry as
// a callback without the page knowing where the text came from.

/**
 * Which entry the page serves.
 *
 * - `"existing"` — `/work/:bookId/codex/:id`, an entry that has a row.
 * - `"blank"` — `/work/:bookId/codex/new?kind=<character|location|fact>` (UC-076).
 *   A blank entry has NO loaded server entry and NO buffer base version until its
 *   first save creates the row.
 */
export type CodexEntryPageMode = "existing" | "blank";

/**
 * The two editable fields of a codex entry. Wire-identical to the backend's
 * `CanvasField` (`models/schemas/chats.py`), so a `canvas` frame's `field` binds
 * to {@link CodexEntryPageState.applyDraft} unchanged in step 013.
 *
 * NOTE: only the BODY is buffered. `restoreBuffer.ts`'s `BufferedDraft.draft` is a
 * single string, and the body is the substantive content the buffer exists to
 * protect; the name is small and always visible (`012.context.md`).
 */
export type CodexDraftField = "name" | "body";

/**
 * Which side the author takes when reconciling a divergence — never an auto-merge
 * (`frontend-workspace.md` → "Returning to a stale buffer").
 *
 * - `"server"` — discard the draft and adopt the server's current entry.
 * - `"draft"` — keep the draft and re-save it against the server's NEW
 *   `modified_at`.
 */
export type ReconciliationSide = "server" | "draft";

/** The codex taxonomy as a runtime list, for {@link parseCodexKind}. */
const CODEX_KINDS: readonly CodexKind[] = ["character", "location", "fact"];

/**
 * LOCAL validation wording (US-078.AC-1 / US-078.AC-2) — never a server message.
 * A character or a location must carry a non-blank name; a fact must carry none
 * (`domain-codex.md`: `name` is null for a fact).
 */
const NAME_REQUIRED_MESSAGE = "A name is required before this entry can be saved.";
const NAME_NOT_ALLOWED_MESSAGE = "A fact has no name — clear the name before saving.";

/**
 * The blank route reached without a usable `?kind=` — nothing can be created
 * without a kind, and the page will not guess one.
 */
const MISSING_KIND_MESSAGE =
  "This new entry has no kind. Open it from Characters, Locations or Facts.";

/**
 * The author-facing text of a refused save, read out of the wire body rather than
 * parsed out of the message string.
 *
 * `client.ts:throwApiError` puts the WHOLE JSON body into `ApiError.details`, and
 * FastAPI wraps a handler's `detail` in a `{"detail": …}` envelope — so a codex
 * refusal (`routes/codex.py`, which raises `HTTPException(detail=CodexErrorDetail(
 * reason=…, message=…))`) arrives as `details.detail.message` / `.reason`, nested.
 * An authorization denial's detail is a plain string instead (`_map_authz_error`),
 * which is why both shapes are read here. The CALLER branches on `status`; this
 * helper only decides where the text lives.
 */
function serverRefusalText(err: ApiError): string {
  const details = err.details;
  if (typeof details === "object" && details !== null) {
    const detail = (details as { detail?: unknown }).detail;
    if (typeof detail === "string" && detail.trim() !== "") return detail;
    if (typeof detail === "object" && detail !== null) {
      const message = (detail as { message?: unknown }).message;
      if (typeof message === "string" && message.trim() !== "") return message;
      const reason = (detail as { reason?: unknown }).reason;
      if (typeof reason === "string" && reason.trim() !== "") return reason;
    }
  }
  return err.message;
}

/**
 * Narrow the `/codex/new?kind=` query-param value to a `CodexKind`, or `null` when
 * it is absent or not one of the three kinds. Pure and total — the page reads the
 * query string ONCE at mount to seed the state (`frontend.md`:192: the query
 * string is never watched by an effect).
 *
 * Declarative and complete; there is no behaviour here to leave unimplemented.
 */
export function parseCodexKind(value: string | null): CodexKind | null {
  return CODEX_KINDS.find((kind) => kind === value) ?? null;
}

export class CodexEntryPageState {
  /** The book the entry belongs to — the restore-buffer key's first segment. */
  readonly bookId: string;

  /**
   * Which entry this page serves. Derived from the constructor's `entryId` (a
   * route with no id IS the blank route) and fixed for the instance's life: a
   * blank entry that saves adopts an id but stays the instance that was created
   * blank — the navigation to `/codex/:id` remounts a fresh `"existing"` page.
   */
  readonly mode: CodexEntryPageMode;

  /**
   * The kind chosen at the `/codex/new` route (`?kind=`), or `null` on the
   * existing-entry route where the loaded row is authoritative. Read once at
   * mount; see {@link CodexEntryPageState.kind}.
   */
  readonly initialKind: CodexKind | null;

  /**
   * The entry's id: the route's for an existing entry, `null` for a blank one
   * until the first save creates the row and the state adopts the created id.
   * Drives {@link CodexEntryPageState.bufferKey}.
   */
  entryId: string | null;

  /** The loaded entry async trio. `entry` stays `null` for a blank entry. */
  entry: CodexEntryResponse | null = null;
  entryStatus: "idle" | "loading" | "ready" | "error" = "idle";
  entryError: string | null = null;

  /**
   * The save's own status, separate from the load's trio so a failed save never
   * blanks the editor the author is still looking at.
   */
  saveStatus: "idle" | "saving" | "saved" | "error" = "idle";

  /**
   * The SERVER's refusal text for the last save — the 403 reason (the
   * proposal-mode refusal naming FEAT-010, or a lost capability) and any other
   * non-409 failure. Merged into the UI SEPARATELY from local validation
   * ({@link CodexEntryPageState.nameError}): a server error never masquerades as
   * a field-validation message and never clears the draft or its buffer.
   */
  saveError: string | null = null;

  /** The name the author is editing. Not buffered (see {@link CodexDraftField}). */
  nameDraft = "";

  /** The body the author is editing. This is what the restore buffer holds. */
  bodyDraft = "";

  /**
   * The server's current entry, re-fetched after a 409 (or the just-loaded entry
   * when a buffer's `baseVersion` no longer matches it), held BESIDE the author's
   * draft so the page can show both. Never merged into the draft automatically.
   */
  conflictEntry: CodexEntryResponse | null = null;

  /**
   * When `true` the page renders the reconciliation view INSTEAD of the editor.
   * Set by the two divergence paths — a stale buffer detected at load, and a 409
   * from save — and cleared by {@link resolveCodexConflict}.
   */
  isReconciling = false;

  /**
   * The keys the most recent buffer write had to evict to fit
   * (`WriteResult.status === "saved-after-eviction"`), so the page can tell the
   * author WHICH drafts were dropped. Empty after a plain `"saved"`. Eviction
   * itself is `restoreBuffer.ts`'s and is already implemented — this field only
   * surfaces it.
   */
  evictedBufferKeys: string[] = [];

  /**
   * @param bookId the route's `:bookId`.
   * @param entryId the route's `:id`, or `null` on `/codex/new` — which is what
   *   makes this page blank.
   * @param initialKind the `?kind=` query param, parsed once at mount by
   *   {@link parseCodexKind}; `null` on the existing-entry route.
   */
  constructor(bookId: string, entryId: string | null, initialKind: CodexKind | null = null) {
    this.bookId = bookId;
    this.entryId = entryId;
    this.mode = entryId === null ? "blank" : "existing";
    this.initialKind = initialKind;
    makeAutoObservable(this, {
      bookId: false,
      mode: false,
      initialKind: false,
      applyDraft: false,
    });
  }

  /**
   * The entry's kind: the LOADED row's for an existing entry (authoritative), the
   * `?kind=` query param's for a blank one. `null` while an existing entry is
   * still loading — the name field and the kind/name rule are unknown until then.
   */
  get kind(): CodexKind | null {
    // The loaded row wins for an existing entry — the server's kind is the only
    // authoritative one; the `?kind=` param only answers for a row that has none yet.
    if (this.mode === "existing") return this.entry?.kind ?? null;
    return this.initialKind;
  }

  /**
   * Whether this kind must carry a non-blank name: `true` for `character` and
   * `location`, `false` for a `fact` (which must have NONE — US-078.AC-1 /
   * US-078.AC-2). Also the render gate for the name field: a fact shows none.
   * `false` while the kind is unknown.
   */
  get requiresName(): boolean {
    return this.kind === "character" || this.kind === "location";
  }

  /**
   * Whether the drafts diverge from the loaded entry — for a blank entry, whether
   * either draft is non-empty. Drives the unsaved-changes affordance and the
   * discard action. Nothing derived is stored.
   */
  get isDirty(): boolean {
    if (this.entry === null) {
      // A blank entry (or one whose load has not settled) forked from nothing:
      // any text at all is unsaved work.
      return this.nameDraft !== "" || this.bodyDraft !== "";
    }
    return this.nameDraft !== (this.entry.name ?? "") || this.bodyDraft !== this.entry.body;
  }

  /**
   * LOCAL name validation only, never a server error: a message when a
   * character/location has a blank name, or when a fact carries one; `null` when
   * the name is acceptable (including while the kind is unknown).
   */
  get nameError(): string | null {
    if (this.kind === null) return null;
    if (this.requiresName) {
      return this.nameDraft.trim() === "" ? NAME_REQUIRED_MESSAGE : null;
    }
    return this.nameDraft.trim() === "" ? null : NAME_NOT_ALLOWED_MESSAGE;
  }

  /** `true` when no local validation message is outstanding. */
  get isValid(): boolean {
    return this.nameError === null;
  }

  /**
   * The editability verdict for this entry, from `work/subject.ts`'s
   * `resolveEditability` — consumed unchanged, so an archived entry's read-only
   * reason is that module's exact wording and no new string is written here.
   * A blank entry is editable (it has no row to be archived).
   */
  get editability(): Editability {
    // `work/subject.ts` owns the wording: an archived entry's read-only reason is
    // that module's string, verbatim, and nothing new is written here.
    return resolveEditability({
      kind: "codex-entry",
      entityId: this.entryId ?? undefined,
      codexArchived: this.entry?.archived ?? false,
    });
  }

  /** `true` when the entry may not be edited (an archived entry). */
  get isReadOnly(): boolean {
    return this.editability.editable === "none";
  }

  /**
   * Whether the Save action is available: not read-only, locally valid, not
   * already saving, and not reconciling. Dirtiness deliberately does NOT gate it.
   */
  get canSave(): boolean {
    return !this.isReadOnly && this.isValid && this.saveStatus !== "saving" && !this.isReconciling;
  }

  /**
   * This entry's restore-buffer key —
   * `restoreBufferKey(bookId, "codex-entry", entryId)` — or `null` for a blank
   * entry, which has no id to key on until its first save.
   */
  get bufferKey(): string | null {
    if (this.entryId === null) return null;
    return restoreBufferKey(this.bookId, "codex-entry", this.entryId);
  }

  /**
   * The version the draft forked from — the loaded entry's `modified_at`. It is
   * BOTH the buffer's `baseVersion` and the update request's
   * `expected_modified_at`, which is why it is derived from `entry` and not
   * stored: adopting a save response (`state.entry = saved`) adopts the new base
   * version in one assignment, so the NEXT save cannot 409 against a value the
   * client itself produced. `null` for a blank entry and for an entry never
   * edited since creation; the buffer, whose `BufferBaseVersion` admits no null,
   * records `""` in that case.
   */
  get baseVersion(): ISODateString | null {
    return this.entry?.modified_at ?? null;
  }

  /**
   * This page as the content pane's subject, for `work/contentSubject.ts` — the
   * value the registered source function returns, read at SEND time rather than
   * snapshotted at mount, which is why the page registers `() => state.contentSubject`
   * and not a record: an existing entry's kind and archived flag are unknown until
   * the load resolves (013 step 013; UC-083 / US-086.AC-1 / US-087.AC-1).
   *
   * Contract: kind `"codex-entry"` always; `entityId` the entry's id, ABSENT for a
   * blank entry (UC-076 — no row yet, which is what puts a null `subject_id` on the
   * wire); `codexArchived` the loaded row's `archived`; `codexKind` this page's
   * {@link CodexEntryPageState.kind} — the loaded row's for an existing entry, the
   * `?kind=` query param's for a blank one.
   */
  get contentSubject(): ContentSubject {
    const subject: ContentSubject = {
      kind: "codex-entry",
      codexArchived: this.entry?.archived ?? false,
      codexKind: this.kind,
    };
    // A blank entry has NO id at all — the key is left absent rather than set to
    // `undefined`, which is what puts a null `subject_id` on the wire (UC-076).
    if (this.entryId !== null) subject.entityId = this.entryId;
    return subject;
  }

  /**
   * Apply draft text to one field from an EXTERNAL source, running exactly the
   * same dirty/buffer path a keystroke does by forwarding to
   * {@link editCodexDraft} — so the assistant's write and the author's are
   * indistinguishable downstream (US-086.AC-2 / US-087.AC-2: nothing is saved).
   *
   * A bound arrow property, and excluded from `makeAutoObservable`'s annotations,
   * so step 013 can register `state.applyDraft` with the module-level canvas
   * registry directly — no `useCallback` (banned), no wrapper, and the page never
   * learns where the text came from.
   */
  readonly applyDraft = (field: CodexDraftField, text: string): void => {
    editCodexDraft(this, field, text);
  };
}

/**
 * Load the page's entry and restore a matching buffer. Contract:
 *
 * - `mode === "blank"`: contact nothing. Settle the trio at `"ready"` with
 *   `entry === null` and the drafts empty — a blank entry has no server entry and
 *   no base version until its first save.
 * - `mode === "existing"`: drive the trio around `codexApi.getCodexEntry`, seed
 *   `nameDraft` / `bodyDraft` from the loaded row, then read the restore buffer at
 *   `state.bufferKey`:
 *   - no buffer → the server text stands;
 *   - `buffer.baseVersion === entry.modified_at` → RESTORE the buffered body over
 *     the server's (US-107.AC-1 / US-107.AC-2);
 *   - a MISMATCH → a stale buffer: put the buffered body in `bodyDraft`, hold the
 *     loaded entry in `conflictEntry`, set `isReconciling` — and attempt NO save
 *     (`frontend-workspace.md`).
 * - Return silently when `signal?.aborted`; map an `ApiError` to `entryError` /
 *   `entryStatus = "error"`, else rethrow.
 */
export async function loadCodexEntry(
  state: CodexEntryPageState,
  signal?: AbortSignal,
): Promise<void> {
  if (state.mode === "blank" || state.entryId === null) {
    // UC-076: a blank entry has no row, so there is nothing to fetch and nothing
    // to key a buffer on. It settles ready with empty drafts, having contacted
    // neither the server nor `localStorage`.
    runInAction(() => {
      state.entry = null;
      state.entryStatus = "ready";
      state.entryError = null;
      state.nameDraft = "";
      state.bodyDraft = "";
    });
    return;
  }

  runInAction(() => {
    state.entryStatus = "loading";
    state.entryError = null;
  });

  try {
    const entry = await codexApi.getCodexEntry(state.bookId, state.entryId, signal);
    if (signal?.aborted) return;

    const key = state.bufferKey;
    const buffered = key === null ? null : readBuffer(key);
    // The buffer's base version is the entry's `modified_at` ISO string; an entry
    // never edited since creation buffers `""` (see `editCodexDraft`).
    const stale = buffered !== null && buffered.baseVersion !== (entry.modified_at ?? "");

    runInAction(() => {
      state.entry = entry;
      state.entryStatus = "ready";
      state.nameDraft = entry.name ?? "";
      state.bodyDraft = buffered === null ? entry.body : buffered.draft;
      if (stale) {
        // A stale buffer is a visible merge problem: hold the server's entry
        // beside the buffered draft and let the author choose. NO save is
        // attempted (`frontend-workspace.md` → "Returning to a stale buffer").
        state.conflictEntry = entry;
        state.isReconciling = true;
      }
    });
  } catch (err) {
    if (signal?.aborted) return;
    if (err instanceof ApiError) {
      runInAction(() => {
        state.entryError = err.message;
        state.entryStatus = "error";
      });
      return;
    }
    throw err;
  }
}

/**
 * Edit one draft field. The single keystroke path, and the single path
 * {@link CodexEntryPageState.applyDraft} forwards to:
 * set the field's draft under `runInAction`; then, for the BODY of an entry that
 * has a key (`state.bufferKey !== null`), write the restore buffer with
 * `state.baseVersion ?? ""` as its `baseVersion` and record a
 * `"saved-after-eviction"` result's keys in `state.evictedBufferKeys`.
 *
 * Synchronous and server-free: NOTHING reaches the server until Save
 * (US-107.AC-4 / US-088.AC-2 / US-103.AC-3), so there is no `signal`.
 */
export function editCodexDraft(
  state: CodexEntryPageState,
  field: CodexDraftField,
  text: string,
): void {
  runInAction(() => {
    if (field === "name") {
      state.nameDraft = text;
    } else {
      state.bodyDraft = text;
    }
  });

  // Only the body is buffered: `BufferedDraft.draft` is a single string and the
  // body is the content the buffer exists to protect (`012.context.md`).
  if (field !== "body") return;

  const key = state.bufferKey;
  if (key === null) return;

  const result = writeBuffer(key, text, state.baseVersion ?? "");
  runInAction(() => {
    // Surfacing only — eviction itself is `restoreBuffer.ts`'s, and it never
    // evicts the key being written, so this entry's own buffer is never the
    // victim (US-107 quota limitation).
    state.evictedBufferKeys = result.status === "saved-after-eviction" ? result.evictedKeys : [];
  });
}

/**
 * Save the entry. Contract:
 *
 * - `mode === "blank"` → `codexApi.createCodexEntry` with the `?kind=` kind, then
 *   adopt the created entry (`entry`, `entryId`) and RETURN the created entry's
 *   route path for the caller to navigate to.
 * - `mode === "existing"` → `codexApi.updateCodexEntry` carrying
 *   `expected_modified_at: state.baseVersion` — the LOADED `modified_at`. On
 *   success adopt the response (`state.entry = saved`, so the new `modified_at`
 *   becomes the base version) and CLEAR the buffer.
 * - `ApiError` with `status === 409` → re-fetch the entry into `conflictEntry`
 *   and set `isReconciling`; never auto-merge, never overwrite.
 * - `ApiError` with `status === 403` → surface the server's reason text (read out
 *   of `err.details`, not the message string — step 003 puts a
 *   `{reason, message}` object in the detail body) into `saveError` and leave the
 *   draft AND its buffer intact.
 * - Any other `ApiError` → `saveError` / `saveStatus = "error"`; else rethrow.
 *
 * @returns the route path to navigate to after a successful CREATE
 *   (`/${bookId}/codex/${id}`, basename-stripped — `/work` is the router
 *   basename), or `null` for an update and for every failure. Returned rather
 *   than navigated so the state stays router-free and the URL write happens in
 *   the handler that caused it (`submitCodexSearch`'s precedent, step 011).
 */
export async function saveCodexEntry(
  state: CodexEntryPageState,
  signal?: AbortSignal,
): Promise<string | null> {
  // The name the wire carries: a fact has none by design, so it is sent as null
  // rather than as the empty string (`domain-codex.md`).
  const nameForWire = state.requiresName ? state.nameDraft : null;

  runInAction(() => {
    state.saveStatus = "saving";
    state.saveError = null;
  });

  try {
    if (state.mode === "blank" && state.entryId === null) {
      const kind = state.initialKind;
      if (kind === null) {
        runInAction(() => {
          state.saveStatus = "error";
          state.saveError = MISSING_KIND_MESSAGE;
        });
        return null;
      }

      const created = await codexApi.createCodexEntry(
        state.bookId,
        { kind, name: nameForWire, body: state.bodyDraft },
        signal,
      );
      if (signal?.aborted) return null;

      runInAction(() => {
        // Adopting the created entry adopts its `modified_at` as the base
        // version, and its id as the buffer key's last segment.
        state.entry = created;
        state.entryId = created.id;
        state.nameDraft = created.name ?? "";
        state.bodyDraft = created.body;
        state.saveStatus = "saved";
        state.evictedBufferKeys = [];
      });
      return `/${state.bookId}/codex/${created.id}`;
    }

    const updated = await codexApi.updateCodexEntry(
      state.bookId,
      state.entryId ?? "",
      {
        name: nameForWire,
        body: state.bodyDraft,
        // The LOADED `modified_at` — the version the draft forked from. The
        // server answers 409 when it no longer matches.
        expected_modified_at: state.baseVersion,
      },
      signal,
    );
    if (signal?.aborted) return null;

    const key = state.bufferKey;
    runInAction(() => {
      // `state.entry = updated` is the whole adoption: `baseVersion` is derived
      // from it, so the NEXT save carries the value this one produced.
      state.entry = updated;
      state.nameDraft = updated.name ?? "";
      state.bodyDraft = updated.body;
      state.saveStatus = "saved";
      state.evictedBufferKeys = [];
    });
    if (key !== null) clearBuffer(key);
    return null;
  } catch (err) {
    if (signal?.aborted) return null;
    if (!(err instanceof ApiError)) throw err;

    if (err.status === 409) {
      // Stale base version: re-read the server's current entry and hold it
      // BESIDE the draft. Never a merge, never a silent overwrite — the draft
      // and its buffer are left exactly as they are.
      try {
        const current = await codexApi.getCodexEntry(state.bookId, state.entryId ?? "", signal);
        if (signal?.aborted) return null;
        runInAction(() => {
          state.conflictEntry = current;
          state.isReconciling = true;
          state.saveStatus = "idle";
          state.saveError = null;
        });
      } catch (refetchErr) {
        if (signal?.aborted) return null;
        if (!(refetchErr instanceof ApiError)) throw refetchErr;
        runInAction(() => {
          state.saveStatus = "error";
          state.saveError = serverRefusalText(refetchErr);
        });
      }
      return null;
    }

    // Every other refusal — chiefly the 403 proposal-mode refusal naming
    // FEAT-010, and a lost capability — surfaces the SERVER's own text, read out
    // of the response body (never parsed out of the message). The draft and its
    // buffer are untouched, so nothing the author wrote is lost.
    runInAction(() => {
      state.saveStatus = "error";
      state.saveError = serverRefusalText(err);
    });
    return null;
  }
}

/**
 * Discard the unsaved draft: clear this entry's restore buffer, reset
 * `nameDraft` / `bodyDraft` to the loaded entry (empty for a blank one), and
 * clear `evictedBufferKeys` and `saveError`. The server is not contacted — a
 * discard is a local act.
 */
export function discardCodexDraft(state: CodexEntryPageState): void {
  const key = state.bufferKey;
  if (key !== null) clearBuffer(key);
  runInAction(() => {
    state.nameDraft = state.entry?.name ?? "";
    state.bodyDraft = state.entry?.body ?? "";
    state.evictedBufferKeys = [];
    state.saveError = null;
    state.saveStatus = "idle";
  });
}

/**
 * Resolve a divergence by taking one side. The author reconciles manually;
 * there is no merge.
 *
 * - `"server"` → discard the draft, adopt `conflictEntry` as `entry`, reseed the
 *   drafts from it, CLEAR the buffer, leave the reconciliation view.
 * - `"draft"` → adopt `conflictEntry` as `entry` FIRST (so `baseVersion` is the
 *   server's new `modified_at`), keep the drafts, leave the reconciliation view,
 *   then re-save through {@link saveCodexEntry} — which now succeeds.
 */
export async function resolveCodexConflict(
  state: CodexEntryPageState,
  side: ReconciliationSide,
  signal?: AbortSignal,
): Promise<void> {
  const current = state.conflictEntry;

  if (side === "server") {
    const key = state.bufferKey;
    if (key !== null) clearBuffer(key);
    runInAction(() => {
      if (current !== null) state.entry = current;
      state.nameDraft = state.entry?.name ?? "";
      state.bodyDraft = state.entry?.body ?? "";
      state.conflictEntry = null;
      state.isReconciling = false;
      state.evictedBufferKeys = [];
      state.saveError = null;
      state.saveStatus = "idle";
    });
    return;
  }

  // Taking the draft's side: adopt the server's entry FIRST so `baseVersion` is
  // its NEW `modified_at`, keep the drafts, leave the view — then re-save, which
  // now carries a version the server agrees with.
  runInAction(() => {
    if (current !== null) state.entry = current;
    state.conflictEntry = null;
    state.isReconciling = false;
    state.saveError = null;
  });
  await saveCodexEntry(state, signal);
}
